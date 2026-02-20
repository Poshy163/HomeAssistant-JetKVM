"""Camera platform for JetKVM integration — WebRTC live video stream.

The JetKVM device streams H.264 video over WebRTC.  This camera entity
uses Home Assistant's native WebRTC support to proxy the SDP offer/answer
through the JetKVM's ``POST /webrtc/session`` endpoint (port 80).

Authentication is done via a session cookie obtained from
``POST /auth/login-local``.  A password **must** be configured in the
integration to enable the camera entity.
"""
import logging

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import JetKVMClient, JetKVMAuthError, JetKVMError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up JetKVM camera from a config entry."""
    client: JetKVMClient = hass.data[DOMAIN][entry.entry_id]["client"]

    # Only add the camera if a password is configured
    if not client.has_password:
        _LOGGER.debug(
            "JetKVM camera: no password configured, skipping camera entity. "
            "To enable the video stream, reconfigure the integration with "
            "the JetKVM device password."
        )
        return

    async_add_entities([JetKVMCamera(entry, client)])


class JetKVMCamera(Camera):
    """JetKVM WebRTC camera entity."""

    _attr_has_entity_name = True
    _attr_name = "Video stream"
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "JetKVM"

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

    @property
    def frontend_stream_type(self) -> str | None:
        """Tell the HA frontend to use WebRTC for this camera."""
        return "web_rtc"

    async def async_handle_web_rtc_offer(
        self, offer_sdp: str
    ) -> str | None:
        """Handle a WebRTC offer and return the SDP answer.

        This proxies the SDP exchange through the JetKVM device's
        native ``POST /webrtc/session`` endpoint.
        """
        try:
            answer_sdp = await self._client.async_webrtc_offer(offer_sdp)
            _LOGGER.debug("JetKVM camera: WebRTC offer/answer exchange successful")
            return answer_sdp
        except JetKVMAuthError as err:
            _LOGGER.error("JetKVM camera: authentication failed: %s", err)
            return None
        except JetKVMError as err:
            _LOGGER.error("JetKVM camera: WebRTC session error: %s", err)
            return None
        except Exception as err:
            _LOGGER.exception("JetKVM camera: unexpected error during WebRTC offer: %s", err)
            return None

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle async WebRTC offer (HA 2024.9+)."""
        try:
            answer_sdp = await self._client.async_webrtc_offer(offer_sdp)
            _LOGGER.debug("JetKVM camera: async WebRTC offer/answer exchange successful")
            send_message(WebRTCAnswer(answer=answer_sdp))
        except JetKVMAuthError as err:
            _LOGGER.error("JetKVM camera: authentication failed: %s", err)
        except JetKVMError as err:
            _LOGGER.error("JetKVM camera: WebRTC session error: %s", err)
        except Exception as err:
            _LOGGER.exception("JetKVM camera: unexpected error during WebRTC offer: %s", err)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera.

        The JetKVM has no screenshot endpoint, so we return None.
        The WebRTC stream is the only way to view the video.
        """
        return None

