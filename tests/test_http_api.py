"""Test the actual HTTP API endpoints on the JetKVM device."""
import urllib.request
import json
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"
BASE = f"http://{HOST}"

def fetch(path, method="GET"):
    try:
        req = urllib.request.Request(f"{BASE}{path}", method=method)
        resp = urllib.request.urlopen(req, timeout=5)
        ct = resp.headers.get("Content-Type", "")
        body = resp.read().decode(errors="replace")
        if "text/html" in ct or body.strip().startswith("<!"):
            return f"{method} {path} -> {resp.status} [HTML SPA]"
        try:
            data = json.loads(body)
            return f"{method} {path} -> {resp.status}\n  {json.dumps(data, indent=2)}"
        except:
            return f"{method} {path} -> {resp.status} CT={ct}\n  {body[:500]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200] if e.fp else ""
        return f"{method} {path} -> {e.code}: {body}"
    except Exception as e:
        return f"{method} {path} -> ERR: {e}"

# Test the endpoints we found in the JS
endpoints = [
    "/device/status",
    "/device",
    "/device/state",
    "/auth/login-local",
    "/me",
    "/cloud/state",
]

for ep in endpoints:
    print(fetch(ep))
    print()

