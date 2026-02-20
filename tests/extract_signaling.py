import re
import sys
import urllib.request

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"
url = f"http://{host}/static/assets/immutable/index-DKjkQpfy.js"
js = urllib.request.urlopen(url, timeout=20).read().decode(errors="replace")

terms = [
    "Device is using new signaling",
    "Device is using legacy signaling",
    "Legacy signaling. Waiting for ICE Gathering to complete",
    "/webrtc/session",
    "new-ice-candidate",
    "setRemoteDescription",
    "onicecandidate",
]

for term in terms:
    print(f"\n=== {term} ===")
    matches = list(re.finditer(re.escape(term), js))
    if not matches:
        print("not found")
        continue
    for idx, m in enumerate(matches[:3], 1):
        p = m.start()
        ctx = js[max(0, p - 300): p + 300].replace("\n", " ")
        print(f"[{idx}] ...{ctx}...")

