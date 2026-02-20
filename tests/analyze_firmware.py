"""Fetch and analyze jsonrpc.go and video.go from the JetKVM firmware repo."""
import urllib.request
import re

for filename in ["jsonrpc.go", "video.go", "webrtc.go"]:
    url = f"https://raw.githubusercontent.com/jetkvm/kvm/main/{filename}"
    print(f"\n{'='*60}")
    print(f"=== {filename} ===")
    print(f"{'='*60}")

    try:
        r = urllib.request.urlopen(url, timeout=15)
        content = r.read().decode()
        print(f"Size: {len(content)} bytes")
    except Exception as e:
        print(f"Error: {e}")
        continue

    # Find RPC method registrations
    # Patterns: rpc.Register("method", ...), rpcServer.Register("method", ...)
    methods = re.findall(r'\.Register\w*\(\s*"([^"]+)"', content)
    if methods:
        print(f"\n  Registered RPC methods:")
        for m in methods:
            print(f"    {m}")

    # Find function definitions
    funcs = re.findall(r'func\s+(\w+)', content)
    if funcs:
        print(f"\n  Functions ({len(funcs)}):")
        for f in funcs:
            marker = ""
            fl = f.lower()
            if any(k in fl for k in ["screen", "snap", "image", "jpeg", "capture", "frame", "video"]):
                marker = " <<<< VIDEO RELATED"
            if marker or any(k in fl for k in ["rpc", "handle", "get", "set"]):
                print(f"    {f}{marker}")

    # Find screenshot/video related content
    for term in ["screenshot", "jpeg", "JPEG", "snapshot", "captureFrame", "getFrame",
                  "mjpeg", "MJPEG", "v4l2", "/dev/video", "image/jpeg", "image/png"]:
        matches = list(re.finditer(re.escape(term), content, re.IGNORECASE))
        if matches:
            print(f"\n  '{term}' found {len(matches)} time(s):")
            for m in matches[:5]:
                start = max(0, m.start() - 60)
                end = min(len(content), m.start() + 80)
                ctx = content[start:end].replace('\n', '\\n')
                print(f"    ...{ctx}...")

print("\nDone.")

