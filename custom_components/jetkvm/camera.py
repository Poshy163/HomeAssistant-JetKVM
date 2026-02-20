"""Camera platform for JetKVM integration — WebRTC live video stream.

The JetKVM device streams H.264 video over WebRTC.  This camera entity
implements *native* WebRTC by overriding ``async_handle_async_webrtc_offer``
and ``async_on_webrtc_candidate`` directly on the Camera entity.

The native approach is required because:
  - If ``async_handle_async_webrtc_offer`` IS overridden, HA marks the
    camera as ``_supports_native_async_webrtc = True``, which adds ONLY
    ``StreamType.WEB_RTC`` to capabilities (no HLS fallback).
  - If we used a ``CameraWebRTCProvider`` instead, HA would add BOTH
    ``WEB_RTC`` and ``HLS``, then try to open ``stream_source()`` with
    FFmpeg — which fails because JetKVM has no RTSP/HLS endpoint.

The JetKVM gathers all ICE candidates server-side before returning the
SDP answer, so browser trickle ICE candidates are silently accepted.

Authentication is done via a session cookie obtained from
``POST /auth/login-local``.  A password **must** be configured in the
integration to enable the camera entity.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import JetKVMClient, JetKVMAuthError, JetKVMError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Import WebRTC message types with fallback.
try:
    from homeassistant.components.camera import (
        WebRTCAnswer,
        WebRTCCandidate,
        WebRTCError,
        WebRTCSendMessage,
    )
except ImportError:
    WebRTCAnswer = None  # type: ignore[assignment,misc]
    WebRTCCandidate = None  # type: ignore[assignment,misc]
    WebRTCError = None  # type: ignore[assignment,misc]
    WebRTCSendMessage = None  # type: ignore[assignment,misc]

# RTCIceCandidateInit — the type HA passes to async_on_webrtc_candidate.
try:
    from webrtc_models import RTCIceCandidateInit  # shipped with HA
except ImportError:
    RTCIceCandidateInit = Any  # type: ignore[assignment,misc]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up JetKVM camera from a config entry."""
    client: JetKVMClient = hass.data[DOMAIN][entry.entry_id]["client"]

    if not client.has_password:
        _LOGGER.debug(
            "JetKVM camera: no password configured — skipping camera entity. "
            "To enable the video stream, reconfigure with the JetKVM password."
        )
        return

    async_add_entities([JetKVMCamera(entry, client)])


class JetKVMCamera(Camera):
    """JetKVM WebRTC camera entity (native WebRTC implementation).

    Overrides ``async_handle_async_webrtc_offer`` so HA treats this as a
    native WebRTC camera (WebRTC-only, no HLS).  Also overrides
    ``async_on_webrtc_candidate`` to silently accept browser ICE candidates
    (the JetKVM gathers all ICE server-side).
    """

    _attr_has_entity_name = True
    _attr_name = "Video stream"
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "JetKVM"

    class _CandidateCompat:
        """Compat candidate object that exposes to_dict() for HA serializers."""

        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def to_dict(self) -> dict[str, Any]:
            return self._data

    def __init__(self, entry: ConfigEntry, client: JetKVMClient) -> None:
        """Initialize the camera."""
        super().__init__()
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._attr_is_streaming = True

    @property
    def device_info(self) -> DeviceInfo:
        """Link this entity to the JetKVM device."""
        data = self._entry.data
        serial = data.get("serial_number", "")
        identifiers = set()
        if serial:
            identifiers.add((DOMAIN, serial))
        else:
            identifiers.add((DOMAIN, self._entry.entry_id))
        return DeviceInfo(identifiers=identifiers)

    # -- Native WebRTC implementation ----------------------------------------

    async def async_handle_async_webrtc_offer(
        self,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle a WebRTC offer — proxy through the JetKVM native API.

        By overriding this, HA marks us as ``_supports_native_async_webrtc``
        which adds ONLY ``StreamType.WEB_RTC`` (no HLS) to capabilities.
        """
        try:
            async def _on_remote_candidate(candidate_data: dict[str, Any]) -> None:
                if WebRTCCandidate is None:
                    return

                if "candidate" in candidate_data and isinstance(candidate_data["candidate"], dict):
                    normalized = candidate_data["candidate"]
                else:
                    normalized = candidate_data

                candidate_obj: Any
                try:
                    candidate_obj = RTCIceCandidateInit(**normalized)
                except Exception:
                    candidate_obj = JetKVMCamera._CandidateCompat(normalized)
                send_message(WebRTCCandidate(candidate=candidate_obj))

            answer_sdp = await self._client.async_webrtc_offer(
                offer_sdp,
                session_id=session_id,
                on_remote_candidate=_on_remote_candidate,
            )
            _LOGGER.debug(
                "JetKVM camera: WebRTC OK (session %s, %d bytes)",
                session_id,
                len(answer_sdp),
            )
            send_message(WebRTCAnswer(answer=answer_sdp))
        except (JetKVMAuthError, JetKVMError) as err:
            _LOGGER.error("JetKVM camera: WebRTC error: %s", err)
            if WebRTCError is not None:
                send_message(WebRTCError("webrtc_offer_failed", str(err)))
        except Exception as err:
            _LOGGER.exception("JetKVM camera: unexpected error: %s", err)
            if WebRTCError is not None:
                send_message(WebRTCError("webrtc_offer_failed", str(err)))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a WebRTC ICE candidate from the browser.

        Newer JetKVM firmware uses WebSocket signaling and expects
        trickle ICE candidates as ``new-ice-candidate`` messages.
        Older firmware can ignore them safely.
        """
        await self._client.async_webrtc_candidate(session_id, candidate)

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        self.hass.async_create_task(self._client.async_close_webrtc_session(session_id))

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """The JetKVM has no screenshot endpoint."""
        return None
