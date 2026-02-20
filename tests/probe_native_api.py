"""Probe JetKVM's authenticated native API for video/screenshot capabilities.

Usage:
    python tests/probe_native_api.py <host> <password>
"""
import asyncio
import json
import sys
import urllib.request
import urllib.parse
import http.cookiejar

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""

if not PASSWORD:
    print("Usage: python tests/probe_native_api.py <host> <password>")
    print("Password is required to access the JetKVM native API.")
    sys.exit(1)


def main():
    # Authenticate
    print(f"=== Authenticating to {HOST} ===")
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    login_data = json.dumps({"password": PASSWORD}).encode()
    req = urllib.request.Request(
        f"http://{HOST}/auth/login-local",
        data=login_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = opener.open(req, timeout=5)
        print(f"Login: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.code}: {e.read().decode()[:200]}")
        return
    except Exception as e:
        print(f"Login failed: {e}")
        return

    cookies = {c.name: c.value for c in cj}
    print(f"Cookies: {list(cookies.keys())}")

    # Try various authenticated endpoints
    print("\n--- GET /device (authenticated) ---")
    try:
        resp = opener.open(f"http://{HOST}/device", timeout=5)
        body = resp.read().decode()
        data = json.loads(body)
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"  Error: {e}")

    # Try WebRTC session with a minimal SDP offer
    print("\n--- POST /webrtc/session ---")
    import base64
    # Create a minimal SDP offer (won't actually establish a connection but tests the endpoint)
    fake_sdp = {
        "type": "offer",
        "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
    }
    sd_b64 = base64.b64encode(json.dumps(fake_sdp).encode()).decode()
    try:
        data = json.dumps({"sd": sd_b64}).encode()
        req = urllib.request.Request(
            f"http://{HOST}/webrtc/session",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = opener.open(req, timeout=5)
        body = resp.read().decode()
        print(f"  Status: {resp.status}")
        print(f"  Response: {body[:500]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  HTTP {e.code}: {body}")
    except Exception as e:
        print(f"  Error: {e}")

    # Try screenshot/snapshot endpoints with auth
    print("\n--- Testing screenshot endpoints (authenticated) ---")
    for path in ["/screenshot", "/snapshot", "/device/screenshot", "/api/screenshot",
                 "/capture", "/screen.jpg", "/device/screen", "/video/snapshot.jpg"]:
        url = f"http://{HOST}{path}"
        try:
            resp = opener.open(url, timeout=3)
            ct = resp.headers.get("Content-Type", "")
            length = resp.headers.get("Content-Length", "?")
            if "image" in ct or "jpeg" in ct or "png" in ct:
                print(f"  {url} -> {resp.status} Content-Type: {ct} Length: {length} <<<< FOUND!")
            elif "html" not in ct:
                print(f"  {url} -> {resp.status} Content-Type: {ct} Length: {length}")
        except urllib.error.HTTPError as e:
            if e.code != 404 and e.code != 200:
                print(f"  {url} -> HTTP {e.code}")
        except Exception:
            pass

    print("\nDone.")


main()

