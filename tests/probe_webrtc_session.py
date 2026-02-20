"""Probe the /webrtc/session endpoint on the JetKVM native API.

Usage:
    python tests/probe_webrtc_session.py [host]
"""
import urllib.request
import json
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

print(f"=== Probing {HOST} ===\n")

# 1. Check /device/status (no auth needed)
print("--- /device/status ---")
try:
    resp = urllib.request.urlopen(f"http://{HOST}/device/status", timeout=5)
    print(f"  {resp.read().decode()}")
except Exception as e:
    print(f"  Error: {e}")

# 2. Check /webrtc/session
print("\n--- POST /webrtc/session ---")
try:
    # WebRTC session negotiation - try posting an empty SDP offer
    data = json.dumps({}).encode()
    req = urllib.request.Request(
        f"http://{HOST}/webrtc/session",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=5)
    body = resp.read().decode()
    print(f"  Status: {resp.status}")
    print(f"  Response: {body[:500]}")
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    print(f"  HTTP {e.code}: {body}")
except Exception as e:
    print(f"  Error: {e}")

# 3. Check /webrtc/turn_activity
print("\n--- GET /webrtc/turn_activity ---")
try:
    resp = urllib.request.urlopen(f"http://{HOST}/webrtc/turn_activity", timeout=5)
    print(f"  {resp.read().decode()[:300]}")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# 4. Try MJPEG-style URLs
print("\n--- Trying MJPEG/stream URLs ---")
mjpeg_urls = [
    f"http://{HOST}/video",
    f"http://{HOST}/video/stream",
    f"http://{HOST}/stream",
    f"http://{HOST}/mjpeg",
    f"http://{HOST}/live",
]
for url in mjpeg_urls:
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=3)
        ct = resp.headers.get("Content-Type", "")
        print(f"  {url} -> {resp.status} Content-Type: {ct}")
    except urllib.error.HTTPError as e:
        print(f"  {url} -> HTTP {e.code}")
    except Exception as e:
        err_str = str(e)[:80]
        print(f"  {url} -> {err_str}")

# 5. Dig deeper into the JS bundle for WebRTC session creation
print("\n--- Analyzing WebRTC session creation in JS ---")
try:
    resp = urllib.request.urlopen(f"http://{HOST}/static/assets/immutable/index-DKjkQpfy.js", timeout=15)
    js = resp.read().decode(errors="replace")

    import re

    # Find the WebRTC session creation code
    for term in ["/webrtc/session", "webrtc/session", "createOffer", "setRemoteDescription", "signaling/client"]:
        for m in re.finditer(re.escape(term), js):
            pos = m.start()
            ctx = js[max(0, pos-120):pos+120].replace('\n', ' ')
            print(f"  [{term}] ...{ctx}...")
            print()

    # Find what data is sent to /webrtc/session
    for m in re.finditer(r'webrtc/session', js):
        pos = m.start()
        ctx = js[max(0, pos-300):pos+300].replace('\n', ' ')
        print(f"  [session context] ...{ctx}...")
        print()

except Exception as e:
    print(f"  Error: {e}")

print("Done.")

