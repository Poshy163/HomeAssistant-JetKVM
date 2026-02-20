"""
End-to-end test: start mock server, then exercise the JetKVMClient against it.

Usage:
    python tests/test_client_e2e.py
"""
import asyncio
import sys
import os

# Fix for aiodns on Windows — needs SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add the repo root so we can import custom_components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aiohttp import web

# ---- inline mock handlers (same as mock_jetkvm.py) ----
import random, time, json

def _temp():
    return round(45.0 + random.uniform(-7, 7), 1)

async def h_health(r):
    return web.json_response({"status": "ok"})

async def h_temp(r):
    return web.json_response({"temperature": _temp()})

async def h_info(r):
    mem_total = 262144
    mem_avail = 131072
    disk_total = 524288
    disk_used = 200000
    return web.json_response({
        "deviceModel": "JetKVM",
        "serial_number": "18cb28a5431d2479",
        "hostname": "jetkvm-mock",
        "ip_address": "127.0.0.1",
        "mac_address": "44:b7:d0:e3:a9:24",
        "network_state": "up",
        "kernel_version": "5.10.160",
        "kernel_build": "#1 Thu Jan 29 12:20:45 CET 2026",
        "temperature": _temp(),
        "uptime_seconds": round(time.monotonic(), 1),
        "load_average": 0.42,
        "mem_total_kb": mem_total,
        "mem_available_kb": mem_avail,
        "mem_used_pct": round((mem_total - mem_avail) / mem_total * 100, 1),
        "disk_total_kb": disk_total,
        "disk_used_kb": disk_used,
        "disk_available_kb": disk_total - disk_used,
        "disk_used_pct": round(disk_used / disk_total * 100, 1),
    })

async def run_tests():
    # ---- start mock server on a random free port ----
    app = web.Application()
    app.router.add_get("/health", h_health)
    app.router.add_get("/temperature", h_temp)
    app.router.add_get("/device_info", h_info)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)   # port 0 = OS picks a free port
    await site.start()

    # fish out the actual port
    port = site._server.sockets[0].getsockname()[1]
    print(f"Mock server started on port {port}\n")

    # ---- now test the client ----
    # Import the client module directly to avoid pulling in homeassistant
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "client",
        os.path.join(os.path.dirname(__file__), "..", "custom_components", "jetkvm", "client.py"),
    )
    client_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client_mod)
    JetKVMClient = client_mod.JetKVMClient
    JetKVMConnectionError = client_mod.JetKVMConnectionError

    client = JetKVMClient(host="127.0.0.1", port=port)

    passed = 0
    failed = 0

    def ok(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}  {detail}")

    # Test 1: health check
    print("--- check_health ---")
    result = await client.check_health()
    ok("returns True", result is True, f"got {result!r}")

    # Test 2: get_temperature
    print("--- get_temperature ---")
    temp = await client.get_temperature()
    ok("returns float", isinstance(temp, float), f"got {type(temp)}")
    ok("range 30-60", 30 <= temp <= 60, f"got {temp}")

    # Test 3: get_device_info
    print("--- get_device_info ---")
    info = await client.get_device_info()
    ok("returns dict", isinstance(info, dict))
    ok("has deviceModel", info.get("deviceModel") == "JetKVM", f"got {info.get('deviceModel')}")
    ok("has hostname", "hostname" in info)
    ok("has temperature", "temperature" in info)
    ok("has serial_number", "serial_number" in info)
    ok("has mac_address", "mac_address" in info)
    ok("has network_state", "network_state" in info)
    ok("has kernel_version", "kernel_version" in info)
    ok("has load_average", "load_average" in info)
    ok("has mem_used_pct", "mem_used_pct" in info)
    ok("has disk_used_pct", "disk_used_pct" in info)

    # Test 4: get_all_data (used by coordinator)
    print("--- get_all_data ---")
    data = await client.get_all_data()
    ok("returns dict", isinstance(data, dict))
    ok("has temperature key", "temperature" in data)
    ok("has load_average key", "load_average" in data)
    ok("has mem_used_pct key", "mem_used_pct" in data)
    ok("has disk_used_pct key", "disk_used_pct" in data)

    # Test 5: validate_connection
    print("--- validate_connection ---")
    vc = await client.validate_connection()
    ok("returns dict", isinstance(vc, dict))
    ok("has deviceModel", vc.get("deviceModel") == "JetKVM")

    # Test 6: connection to wrong port fails correctly
    print("--- connection error handling ---")
    bad_client = JetKVMClient(host="127.0.0.1", port=1)
    try:
        await bad_client.check_health()
        ok("raises on bad port", False, "no exception raised")
    except JetKVMConnectionError:
        ok("raises JetKVMConnectionError", True)
    except Exception as e:
        ok("raises JetKVMConnectionError", False, f"got {type(e).__name__}: {e}")
    finally:
        await bad_client.close()

    await client.close()
    await runner.cleanup()

    # ---- summary ----
    print(f"\n{'='*40}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'='*40}")
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)



