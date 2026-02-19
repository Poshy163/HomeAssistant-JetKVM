"""Test authenticated access to the JetKVM /device endpoint and WebSocket RPC."""
import urllib.request
import urllib.parse
import json
import sys
import http.cookiejar

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""
BASE = f"http://{HOST}"

# Set up a cookie jar for session management
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def fetch(path, method="GET", data=None, content_type=None):
    try:
        req = urllib.request.Request(f"{BASE}{path}", method=method)
        if data is not None:
            if isinstance(data, dict):
                data = json.dumps(data).encode()
                req.add_header("Content-Type", "application/json")
            req.data = data
        if content_type:
            req.add_header("Content-Type", content_type)
        resp = opener.open(req, timeout=5)
        ct = resp.headers.get("Content-Type", "")
        body = resp.read().decode(errors="replace")
        if "text/html" in ct or body.strip().startswith("<!"):
            return f"{method} {path} -> {resp.status} [HTML SPA]", None
        try:
            d = json.loads(body)
            return f"{method} {path} -> {resp.status}", d
        except:
            return f"{method} {path} -> {resp.status} CT={ct}: {body[:500]}", None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300] if e.fp else ""
        return f"{method} {path} -> {e.code}: {body}", None
    except Exception as e:
        return f"{method} {path} -> ERR: {e}", None

# Step 1: Check device status (no auth needed)
print("=== Step 1: Device Status ===")
msg, data = fetch("/device/status")
print(msg)
if data:
    print(json.dumps(data, indent=2))

# Step 2: Try to login
print("\n=== Step 2: Login ===")
if PASSWORD:
    msg, data = fetch("/auth/login-local", method="POST", data={"password": PASSWORD})
    print(msg)
    if data:
        print(json.dumps(data, indent=2))
    print(f"Cookies: {[c.name for c in cj]}")
else:
    # Try empty password
    msg, data = fetch("/auth/login-local", method="POST", data={"password": ""})
    print(f"(empty password) {msg}")
    if data:
        print(json.dumps(data, indent=2))
    print(f"Cookies: {[c.name for c in cj]}")

    # Try no password field
    msg, data = fetch("/auth/login-local", method="POST", data={})
    print(f"(no password) {msg}")
    if data:
        print(json.dumps(data, indent=2))

# Step 3: Try /device with whatever auth we have
print("\n=== Step 3: GET /device (with cookies) ===")
msg, data = fetch("/device")
print(msg)
if data:
    print(json.dumps(data, indent=2))

# Step 4: Try /cloud/state
print("\n=== Step 4: GET /cloud/state ===")
msg, data = fetch("/cloud/state")
print(msg)
if data:
    print(json.dumps(data, indent=2))

print("\nDone.")

