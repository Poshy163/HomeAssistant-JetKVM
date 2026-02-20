"""Fetch and analyze key Go source files from the JetKVM firmware repo."""
import urllib.request
import re
import sys

files_to_check = ["jsonrpc.go", "video.go", "webrtc.go", "web.go", "native.go", "native_linux.go"]

for filename in files_to_check:
    url = f"https://raw.githubusercontent.com/jetkvm/kvm/main/{filename}"
    print(f"\n{'='*60}")
    print(f"=== {filename} ===")
    print(f"{'='*60}")

    try:
        r = urllib.request.urlopen(url, timeout=15)
        content = r.read().decode()
        print(f"Size: {len(content)} bytes")
    except Exception as e:
        print(f"Error fetching: {e}")
        continue

    # Find RPC method registrations
    methods = re.findall(r'\.Register\w*\(\s*"([^"]+)"', content)
    if methods:
        print(f"\n  Registered RPC methods ({len(methods)}):")
        for m in sorted(set(methods)):
            print(f"    {m}")

    # Find func definitions that look interesting
    funcs = re.findall(r'func\s+(?:\([^)]+\)\s+)?(\w+)', content)
    interesting = []
    for f in funcs:
        fl = f.lower()
        if any(k in fl for k in ["screen", "snap", "image", "jpeg", "capture", "frame", "video", "stream", "rpc", "handle"]):
            interesting.append(f)
    if interesting:
        print(f"\n  Interesting functions:")
        for f in sorted(set(interesting)):
            print(f"    {f}")

    # Search for screenshot/JPEG/snapshot patterns
    search_terms = ["screenshot", "jpeg", "JPEG", "snapshot", "mjpeg", "v4l2",
                    "/dev/video", "image/jpeg", "image/png", "getFrame", "captureFrame"]
    for term in search_terms:
        matches = list(re.finditer(re.escape(term), content, re.IGNORECASE))
        if matches:
            print(f"\n  '{term}' found {len(matches)} time(s):")
            for m in matches[:3]:
                s = max(0, m.start() - 80)
                e = min(len(content), m.end() + 80)
                ctx = content[s:e].replace('\n', ' | ')
                print(f"    ...{ctx}...")

print("\n\nDone.")
sys.stdout.flush()

