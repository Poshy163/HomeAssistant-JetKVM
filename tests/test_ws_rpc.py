"""Test WebSocket JSON-RPC on the JetKVM device."""
import asyncio
import json
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

async def test_ws_rpc():
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets

    url = f"ws://{HOST}/webrtc/signaling/client"
    print(f"Connecting to {url} ...")

    try:
        async with websockets.connect(url, open_timeout=5, close_timeout=2) as ws:
            print(f"Connected!\n")

            # Try various RPC methods
            methods = [
                "getDeviceInfo",
                "getLocalVersion",
                "getNetworkSettings",
                "getNetworkState",
                "getUpdateStatus",
                "getDeviceID",
                "getTemperature",
                "getSystemInfo",
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
                    print(f"  (no response / timeout)")
                print()

    except Exception as e:
        print(f"WebSocket error: {e}")

asyncio.run(test_ws_rpc())

