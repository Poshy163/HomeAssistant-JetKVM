"""
Test authenticated WebSocket JSON-RPC on JetKVM.

Usage:
    python test_ws_auth.py <host> <password>
"""
import asyncio
import json
import sys
import urllib.request
import urllib.parse
import http.cookiejar

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""

async def main():
    import websockets

    # Step 1: Authenticate via HTTP to get session cookie
    print("=== Authenticating ===")
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
        body = resp.read().decode()
        print(f"Response: {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"Login failed: {e.code}: {body}")
        print("Please provide the correct password as the second argument.")
        return

    cookies = {c.name: c.value for c in cj}
    print(f"Cookies: {cookies}")

    # Step 2: Try GET /device with auth
    print("\n=== GET /device (authenticated) ===")
    req2 = urllib.request.Request(f"http://{HOST}/device", method="GET")
    try:
        resp2 = opener.open(req2, timeout=5)
        body2 = resp2.read().decode()
        data2 = json.loads(body2)
        print(json.dumps(data2, indent=2))
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"Error: {e}")

    # Step 3: Connect WebSocket with cookie
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    print(f"\n=== WebSocket RPC (with cookie) ===")
    url = f"ws://{HOST}/webrtc/signaling/client"
    print(f"Connecting to {url} ...")

    try:
        async with websockets.connect(
            url,
            additional_headers={"Cookie": cookie_header},
            open_timeout=5,
            close_timeout=2,
        ) as ws:
            print("Connected!\n")

            methods = [
                "getDeviceInfo",
                "getLocalVersion",
                "getNetworkSettings",
                "getNetworkState",
                "getDeviceID",
                "getTemperature",
                "getSystemInfo",
                "getHardwareInfo",
                "getStreamQualityFactor",
                "getEDID",
                "getVideoState",
            ]

            for i, method in enumerate(methods, 1):
                msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": method,
                    "params": {},
                })
                print(f">>> {method}")
                await ws.send(msg)

                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=3)
                    data = json.loads(resp)
                    if "result" in data:
                        print(f"  result: {json.dumps(data['result'], indent=4)}")
                    elif "error" in data:
                        print(f"  error: {data['error']}")
                    else:
                        print(f"  raw: {resp[:300]}")
                except asyncio.TimeoutError:
                    print("  (no response / timeout)")
                print()

    except Exception as e:
        print(f"WebSocket error: {e}")

asyncio.run(main())

