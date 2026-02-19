"""Find auth patterns and more HTTP API endpoints in the JetKVM JS bundle."""
import urllib.request
import re
import json
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

# Fetch the main JS bundle
url = f"http://{HOST}/static/assets/immutable/index-DKjkQpfy.js"
resp = urllib.request.urlopen(url, timeout=15)
js = resp.read().decode(errors="replace")

# Find all URL-like patterns used with ae.GET, ae.POST, etc.
# The code uses: ae.GET(`${fe}/device/status`)
# So 'fe' is likely the base URL variable. Let's find what fe is.
print("=== Looking for base URL variable (fe) ===")
fe_patterns = re.findall(r'fe\s*=\s*["\']([^"\']*)["\']', js)
for p in fe_patterns[:5]:
    print(f"  fe = '{p}'")

# Find all endpoint patterns with the base URL
print("\n=== All ae.GET/POST/PUT/DELETE patterns ===")
api_calls = re.findall(r'ae\.(GET|POST|PUT|DELETE)\(\s*`?\$\{fe\}(/[^`"\')\s]+)', js)
for method, path in sorted(set(api_calls)):
    print(f"  {method} {path}")

# Also find non-template patterns
api_calls2 = re.findall(r'ae\.(GET|POST|PUT|DELETE)\(\s*["\']([^"\']+)["\']', js)
for method, path in sorted(set(api_calls2)):
    print(f"  {method} {path}")

# Find auth-related patterns
print("\n=== Auth patterns ===")
auth_patterns = re.findall(r'(auth|login|password|token|bearer|cookie|session|Authorization)[^;]{0,100}', js, re.IGNORECASE)
for p in auth_patterns[:20]:
    clean = p.replace('\n', ' ')[:120]
    print(f"  ...{clean}...")

# Find all RPC method names more broadly - look for quoted strings near "method"
print("\n=== All RPC method strings ===")
rpc_all = re.findall(r'method:\s*["\']([^"\']+)["\']', js)
for m in sorted(set(rpc_all)):
    if m not in ("GET", "POST", "PUT", "DELETE"):
        print(f"  {m}")

# Find temperature anywhere
print("\n=== Temperature in JS ===")
for m in re.finditer(r'[tT]emp', js):
    pos = m.start()
    ctx = js[max(0,pos-30):pos+50].replace('\n',' ')
    print(f"  ...{ctx}...")

print("\nDone.")

