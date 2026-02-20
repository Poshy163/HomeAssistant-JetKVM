"""Small regression tests for WebRTC candidate normalization helpers.

Usage:
    python tests/test_webrtc_candidate_utils.py
"""
from __future__ import annotations

import importlib.util
import os


ROOT = os.path.join(os.path.dirname(__file__), "..")
CLIENT_PATH = os.path.join(ROOT, "custom_components", "jetkvm", "client.py")


class _DummyCandidate:
    def __init__(self) -> None:
        self.candidate = "candidate:1 1 UDP 2122252543 192.168.1.2 5000 typ host"
        self.sdpMid = "0"
        self.sdpMLineIndex = 0


def _load_client_module():
    spec = importlib.util.spec_from_file_location("jetkvm_client", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_candidate_to_dict_passthrough(module) -> None:
    payload = {"candidate": "abc", "sdpMid": "0", "sdpMLineIndex": 0}
    out = module.JetKVMClient._candidate_to_dict(payload)
    assert out == payload


def test_candidate_to_dict_object(module) -> None:
    out = module.JetKVMClient._candidate_to_dict(_DummyCandidate())
    assert out["candidate"].startswith("candidate:")
    assert out["sdpMid"] == "0"
    assert out["sdpMLineIndex"] == 0


def main() -> None:
    module = _load_client_module()
    test_candidate_to_dict_passthrough(module)
    test_candidate_to_dict_object(module)
    print("PASS: test_webrtc_candidate_utils")


if __name__ == "__main__":
    main()
