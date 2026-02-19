"""Deep-dive into the JetKVM JS bundle to extract all RPC method names and API patterns."""
import urllib.request
import re
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

# Fetch the main JS bundle
url = f"http://{HOST}/static/assets/immutable/index-DKjkQpfy.js"
print(f"Fetching {url} ...")
resp = urllib.request.urlopen(url, timeout=15)
js = resp.read().decode(errors="replace")
print(f"Size: {len(js)} bytes\n")

# 1. Find all quoted strings that look like RPC method names (camelCase words)
#    JSON-RPC methods are typically passed as strings to some send/call function
rpc_methods = re.findall(r'method:\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', js)
if rpc_methods:
    print("=== RPC methods (method:\"...\") ===")
    for m in sorted(set(rpc_methods)):
        print(f"  {m}")

# 2. Also look for method names passed as first arg to a call-like function
rpc_calls = re.findall(r'\.call\(\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', js)
if rpc_calls:
    print("\n=== .call(\"...\") patterns ===")
    for m in sorted(set(rpc_calls)):
        print(f"  {m}")

# 3. Look for send-style patterns
send_patterns = re.findall(r'\.send\(\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', js)
if send_patterns:
    print("\n=== .send(\"...\") patterns ===")
    for m in sorted(set(send_patterns)):
        print(f"  {m}")

# 4. Search for any string containing "temperature", "temp", "thermal"
temp_context = [(m.start(), m.group()) for m in re.finditer(r'[tT]emperature|thermal|temp_|\.temp\b', js)]
if temp_context:
    print(f"\n=== Temperature references ({len(temp_context)} found) ===")
    for pos, match in temp_context[:20]:
        ctx = js[max(0, pos-60):pos+60].replace('\n', ' ')
        print(f"  ...{ctx}...")

# 5. Search for /device/status and surrounding context
device_status = [(m.start(), m.group()) for m in re.finditer(r'/device/status', js)]
if device_status:
    print(f"\n=== /device/status references ===")
    for pos, match in device_status:
        ctx = js[max(0, pos-80):pos+80].replace('\n', ' ')
        print(f"  ...{ctx}...")

# 6. Search for WebSocket connection patterns
ws_patterns = [(m.start(), m.group()) for m in re.finditer(r'new WebSocket|WebSocket\(|\.onmessage|signaling', js)]
if ws_patterns:
    print(f"\n=== WebSocket patterns ({len(ws_patterns)} found) ===")
    for pos, match in ws_patterns[:10]:
        ctx = js[max(0, pos-40):pos+80].replace('\n', ' ')
        print(f"  ...{ctx}...")

# 7. Look for all camelCase strings that could be RPC methods in jsonrpc context
jsonrpc_ctx = [(m.start(),) for m in re.finditer(r'jsonrpc', js)]
if jsonrpc_ctx:
    print(f"\n=== jsonrpc context ({len(jsonrpc_ctx)} found) ===")
    for (pos,) in jsonrpc_ctx[:5]:
        ctx = js[max(0, pos-100):pos+200].replace('\n', ' ')
        print(f"  ...{ctx}...")

# 8. Look for fetch/GET calls to device endpoints
fetch_patterns = re.findall(r'fetch\(\s*["`\']([^"`\']+)["`\']', js)
if fetch_patterns:
    print(f"\n=== fetch() URLs ===")
    for u in sorted(set(fetch_patterns)):
        print(f"  {u}")

# 9. Also try template literals
fetch_template = re.findall(r'fetch\(\s*`([^`]+)`', js)
if fetch_template:
    print(f"\n=== fetch() template URLs ===")
    for u in sorted(set(fetch_template)):
        print(f"  {u}")

print("\nDone.")

