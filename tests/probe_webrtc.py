"""Probe WebRTC signaling WebSocket for all available RPC methods on JetKVM.

Also attempts to find screenshot/snapshot-related RPC methods.

Usage:
    python tests/probe_webrtc.py [host] [password]
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
    try:
        import websockets
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets

    # Authenticate if password provided
    cookies = {}
    if PASSWORD:
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
            cookies = {c.name: c.value for c in cj}
            print(f"Cookies: {cookies}")
        except Exception as e:
            print(f"Login failed: {e}")
            return

    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items()) if cookies else ""

    # Connect to WebSocket
    url = f"ws://{HOST}/webrtc/signaling/client"
    print(f"\n=== Connecting to {url} ===")

    extra_headers = {}
    if cookie_header:
        extra_headers["Cookie"] = cookie_header

    try:
        async with websockets.connect(
            url,
            additional_headers=extra_headers,
            open_timeout=5,
            close_timeout=2,
        ) as ws:
            print("Connected!\n")

            # Comprehensive list of RPC methods to try
            methods = [
                # Device info
                "getDeviceInfo",
                "getDeviceID",
                "getLocalVersion",
                "getSystemInfo",
                "getHardwareInfo",
                "getTemperature",

                # Network
                "getNetworkSettings",
                "getNetworkState",

                # Video/Stream
                "getVideoState",
                "getVideoSettings",
                "getStreamQualityFactor",
                "getEDID",
                "getResolution",
                "getDisplayInfo",
                "getDisplaySettings",
                "getVideoStreamState",
                "getFrameRate",

                # Screenshot/Snapshot (probing)
                "getScreenshot",
                "getSnapshot",
                "captureScreen",
                "captureFrame",
                "getFrame",
                "getImage",
                "getJPEGSnapshot",
                "takeScreenshot",
                "getScreenImage",
                "requestScreenshot",
                "getVideoFrame",
                "captureImage",

                # Stream control
                "startStream",
                "stopStream",
                "getStreamUrl",
                "getStreamSource",
                "getMJPEGUrl",
                "getRTSPUrl",

                # USB/HID
                "getUSBState",
                "getHIDState",
                "getHidProtocolVersion",

                # Update
                "getUpdateStatus",
                "checkUpdateComponents",

                # Cloud
                "getCloudState",

                # Other
                "getConfig",
                "getSettings",
                "getStatus",
                "getCapabilities",
                "listMethods",
                "system.listMethods",
                "rpc.discover",
                "help",
            ]

            for i, method in enumerate(methods, 1):
                msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": method,
                    "params": {},
                })
                await ws.send(msg)

                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(resp)
                    if "result" in data:
                        result_str = json.dumps(data["result"], indent=2)
                        marker = ""
                        if any(k in method.lower() for k in ["screen", "snap", "image", "frame", "capture", "stream", "video", "jpeg"]):
                            marker = " <<<< VIDEO RELATED"
                        print(f"✓ {method}{marker}")
                        print(f"  {result_str[:300]}")
                    elif "error" in data:
                        err = data["error"]
                        if isinstance(err, dict):
                            code = err.get("code", "?")
                            msg_str = err.get("message", str(err))
                        else:
                            code = "?"
                            msg_str = str(err)
                        # Only print if it's not "method not found" type error
                        if "not found" not in str(msg_str).lower() and "unknown" not in str(msg_str).lower():
                            print(f"✗ {method} -> error {code}: {msg_str}")
                    else:
                        print(f"? {method} -> {resp[:200]}")
                except asyncio.TimeoutError:
                    pass  # Method likely doesn't exist

                # Small delay between requests
                await asyncio.sleep(0.1)

            print("\n=== Done ===")

    except Exception as e:
        print(f"WebSocket error: {e}")

asyncio.run(main())

