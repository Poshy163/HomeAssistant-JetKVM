"""Probe a real JetKVM device to discover its API endpoints."""
import urllib.request
import json
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"
BASE = f"http://{HOST}"

def try_get(path):
    try:
        req = urllib.request.Request(f"{BASE}{path}", method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        body = resp.read().decode(errors="replace")
        ct = resp.headers.get("Content-Type", "")
        # Skip HTML pages (the SPA)
        if "text/html" in ct or body.strip().startswith("<!"):
            return f"GET {path} -> {resp.status} [HTML SPA, {len(body)}b]"
        return f"GET {path} -> {resp.status} CT={ct}\n    {body[:300]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace") if e.fp else ""
        return f"GET {path} -> {e.code}: {body[:200]}"
    except Exception as e:
        return f"GET {path} -> ERR: {e}"

def try_post(path, payload):
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{BASE}{path}", data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        resp = urllib.request.urlopen(req, timeout=5)
        body = resp.read().decode(errors="replace")
        ct = resp.headers.get("Content-Type", "")
        return f"POST {path} -> {resp.status} CT={ct}\n    {body[:300]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace") if e.fp else ""
        return f"POST {path} -> {e.code}: {body[:200]}"
    except Exception as e:
        return f"POST {path} -> ERR: {e}"

print(f"=== Probing JetKVM at {BASE} ===\n")

# GET probes
get_paths = [
    "/", "/rpc", "/api", "/api/v1", "/api/device",
    "/device", "/device/info", "/device/status",
    "/webrtc", "/webrtc/signaling",
    "/static", "/config",
    "/metrics", "/system", "/system/info",
]
print("--- GET requests ---")
for p in get_paths:
    print(try_get(p))

# POST probes with JSON-RPC
rpc_payload = {"jsonrpc": "2.0", "id": 1, "method": "getDeviceInfo"}
post_paths = ["/rpc", "/api", "/jsonrpc", "/api/rpc", "/device/jsonrpc", "/webrtc/signaling"]
print("\n--- POST JSON-RPC requests ---")
for p in post_paths:
    print(try_post(p, rpc_payload))

# Try some alternate RPC method names
print("\n--- POST /rpc with different methods ---")
methods = ["getDeviceInfo", "get_device_info", "system.info", "device.info", "getSystemInfo", "ping"]
for m in methods:
    payload = {"jsonrpc": "2.0", "id": 1, "method": m}
    print(try_post("/rpc", payload))

print("\nDone.")

