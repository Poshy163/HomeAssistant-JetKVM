"""Find the API endpoints used by the JetKVM SPA frontend."""
import urllib.request
import re
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

# Get the SPA HTML
resp = urllib.request.urlopen(f"http://{HOST}/", timeout=5)
html = resp.read().decode(errors="replace")

# Find all script/css references
scripts = re.findall(r'src="(.*?)"', html)
links = re.findall(r'href="(.*?)"', html)
print("Scripts:", scripts)
print("Links:", links)

# Find the main JS bundle and search for API endpoints
for src in scripts:
    if src.endswith(".js"):
        print(f"\n--- Fetching {src} ---")
        js_resp = urllib.request.urlopen(f"http://{HOST}{src}", timeout=10)
        js = js_resp.read().decode(errors="replace")
        print(f"  Size: {len(js)} bytes")

        # Search for RPC / WebSocket / API patterns
        patterns = [
            r'["\'](/rpc[^"\']*)["\']',
            r'["\'](/api[^"\']*)["\']',
            r'["\'](/jsonrpc[^"\']*)["\']',
            r'["\']ws[s]?://[^"\']*["\']',
            r'["\']wss?["\']',
            r'(/webrtc/signaling)',
            r'(getDeviceInfo|getTemperature|get_temperature|deviceInfo)',
            r'(jsonrpc|json-rpc)',
            r'["\'](/device[^"\']*)["\']',
            r'["\'](/metrics[^"\']*)["\']',
            r'(temperature|Temperature|thermal)',
        ]
        for pat in patterns:
            matches = re.findall(pat, js)
            if matches:
                unique = list(set(matches))[:10]
                print(f"  Pattern {pat}: {unique}")

