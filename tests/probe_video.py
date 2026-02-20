"""Probe the JetKVM for video/screenshot capabilities.

Usage:
    python tests/probe_video.py [host]
"""
import urllib.request
import re
import json
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

print(f"=== Probing JetKVM at {HOST} ===\n")

# 1. Try to find the JS bundle URL
print("--- Finding JS bundle ---")
try:
    resp = urllib.request.urlopen(f"http://{HOST}/", timeout=10)
    html = resp.read().decode(errors="replace")
    # Find script src
    scripts = re.findall(r'src=["\']([^"\']*\.js)["\']', html)
    print(f"  Scripts found: {scripts}")
except Exception as e:
    print(f"  Error: {e}")
    scripts = []

# 2. Parse JS bundle for RPC methods
for script_path in scripts:
    if script_path.startswith("/"):
        js_url = f"http://{HOST}{script_path}"
    elif script_path.startswith("http"):
        js_url = script_path
    else:
        js_url = f"http://{HOST}/{script_path}"

    print(f"\n--- Parsing {js_url} ---")
    try:
        resp = urllib.request.urlopen(js_url, timeout=15)
        js = resp.read().decode(errors="replace")
        print(f"  Size: {len(js)} bytes")

        # Find RPC method names
        methods = re.findall(r'method:\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', js)
        unique_methods = sorted(set(methods))
        skip = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        rpc_methods = [m for m in unique_methods if m not in skip]

        print(f"\n  RPC methods ({len(rpc_methods)}):")
        for m in rpc_methods:
            marker = ""
            lower = m.lower()
            if any(k in lower for k in ["screen", "snap", "image", "jpeg", "png", "capture", "frame", "video", "stream", "screenshot"]):
                marker = " <<<< VIDEO/SCREENSHOT RELATED"
            print(f"    {m}{marker}")

        # Find HTTP API endpoints
        api_calls = re.findall(r'(GET|POST|PUT|DELETE)\s*[,\(]\s*[`"\']([^`"\']+)[`"\']', js)
        api_calls2 = re.findall(r'\$\{[a-zA-Z]+\}(/[a-zA-Z0-9_/\-]+)', js)
        all_paths = sorted(set(p for _, p in api_calls) | set(api_calls2))

        if all_paths:
            print(f"\n  HTTP API paths ({len(all_paths)}):")
            for p in all_paths:
                marker = ""
                lower = p.lower()
                if any(k in lower for k in ["screen", "snap", "image", "jpeg", "png", "capture", "frame", "video", "stream"]):
                    marker = " <<<< VIDEO/SCREENSHOT RELATED"
                print(f"    {p}{marker}")

        # Search for screenshot/video-related strings
        video_terms = ["screenshot", "snapshot", "capture", "frame", "jpeg", "mjpeg",
                       "rtsp", "stream_source", "video_url", "camera_image",
                       "getScreen", "getSnap", "getFrame", "getImage", "getJPEG"]
        print(f"\n  Video-related string search:")
        for term in video_terms:
            matches = [(m.start(), m.group()) for m in re.finditer(re.escape(term), js, re.IGNORECASE)]
            if matches:
                print(f"    '{term}' found {len(matches)} time(s):")
                for pos, match in matches[:3]:
                    ctx = js[max(0, pos-40):pos+60].replace('\n', ' ')
                    print(f"      ...{ctx}...")

        # Search for WebRTC related
        print(f"\n  WebRTC patterns:")
        webrtc_terms = ["RTCPeerConnection", "createOffer", "createAnswer", "setLocalDescription",
                        "setRemoteDescription", "addIceCandidate", "ontrack", "getReceivers",
                        "signaling", "webrtc"]
        for term in webrtc_terms:
            count = len(re.findall(re.escape(term), js, re.IGNORECASE))
            if count:
                print(f"    {term}: {count} references")

    except Exception as e:
        print(f"  Error: {e}")

# 3. Try known screenshot/snapshot endpoints directly
print("\n--- Testing snapshot endpoints ---")
snapshot_urls = [
    f"http://{HOST}/screenshot",
    f"http://{HOST}/snapshot",
    f"http://{HOST}/device/screenshot",
    f"http://{HOST}/device/snapshot",
    f"http://{HOST}/api/screenshot",
    f"http://{HOST}/api/snapshot",
    f"http://{HOST}/capture",
    f"http://{HOST}/screen",
    f"http://{HOST}/video/snapshot",
]

for url in snapshot_urls:
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        ct = resp.headers.get("Content-Type", "")
        length = resp.headers.get("Content-Length", "?")
        print(f"  {url} -> {resp.status} Content-Type: {ct} Length: {length}")
        if "image" in ct:
            print(f"    ^^^^ FOUND SCREENSHOT ENDPOINT! ^^^^")
    except urllib.error.HTTPError as e:
        print(f"  {url} -> HTTP {e.code}")
    except Exception as e:
        print(f"  {url} -> Error: {e}")

# 4. Try known device API endpoints
print("\n--- Testing device info endpoints ---")
info_urls = [
    f"http://{HOST}/device",
    f"http://{HOST}/device/status",
    f"http://{HOST}/api/device",
    f"http://{HOST}/device/state",
]
for url in info_urls:
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        body = resp.read().decode()[:500]
        print(f"  {url} -> {resp.status}: {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"  {url} -> HTTP {e.code}: {body}")
    except Exception as e:
        print(f"  {url} -> Error: {e}")

print("\nDone.")

