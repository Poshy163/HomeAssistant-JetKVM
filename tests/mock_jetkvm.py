"""
Mock JetKVM API Server for local testing.

Simulates the BusyBox httpd CGI endpoints installed by api-setup.sh.

Usage:
    pip install aiohttp
    python mock_jetkvm.py [port]

Default port is 8800.  Then configure the HA integration with host: 127.0.0.1
"""
import json
import random
import sys
import time
from aiohttp import web

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8800


def get_temperature():
    """Simulate a fluctuating SoC temperature between 38-52°C."""
    base = 45.0
    noise = random.uniform(-7.0, 7.0)
    return round(base + noise, 1)


async def cgi_health(request: web.Request) -> web.Response:
    print("[API] /health")
    return web.json_response({"status": "ok"})


async def cgi_temperature(request: web.Request) -> web.Response:
    temp = get_temperature()
    print(f"[API] /temperature -> {temp}")
    return web.json_response({"temperature": temp})


async def cgi_device_info(request: web.Request) -> web.Response:
    temp = get_temperature()
    mem_total = 262144
    mem_avail = random.randint(100000, 200000)
    mem_used_pct = round((mem_total - mem_avail) / mem_total * 100, 1)
    disk_total = 524288
    disk_used = random.randint(100000, 400000)
    disk_avail = disk_total - disk_used
    disk_used_pct = round(disk_used / disk_total * 100, 1)
    info = {
        "api_version": "1.0.0",
        "deviceModel": "JetKVM",
        "serial_number": "18cb28a5431d2479",
        "hostname": "jetkvm-mock",
        "ip_address": "127.0.0.1",
        "mac_address": "44:b7:d0:e3:a9:24",
        "network_state": "up",
        "kernel_version": "5.10.160",
        "kernel_build": "#1 Thu Jan 29 12:20:45 CET 2026",
        "temperature": temp,
        "uptime_seconds": round(time.monotonic(), 1),
        "load_average": round(random.uniform(0.0, 2.0), 2),
        "mem_total_kb": mem_total,
        "mem_available_kb": mem_avail,
        "mem_used_pct": mem_used_pct,
        "disk_total_kb": disk_total,
        "disk_used_kb": disk_used,
        "disk_available_kb": disk_avail,
        "disk_used_pct": disk_used_pct,
    }
    print(f"[API] /device_info -> temp={temp}")
    return web.json_response(info)


def main():
    app = web.Application()
    app.router.add_get("/health", cgi_health)
    app.router.add_get("/temperature", cgi_temperature)
    app.router.add_get("/device_info", cgi_device_info)

    print("=" * 55)
    print("  Mock JetKVM API Server")
    print("=" * 55)
    print()
    print(f"  Listening on http://127.0.0.1:{PORT}")
    print()
    print(f"  http://127.0.0.1:{PORT}/health")
    print(f"  http://127.0.0.1:{PORT}/temperature")
    print(f"  http://127.0.0.1:{PORT}/device_info")
    print()
    print("=" * 55)
    print()

    web.run_app(app, host="127.0.0.1", port=PORT, print=None)


if __name__ == "__main__":
    main()

