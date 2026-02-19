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
    print("[CGI] /cgi-bin/health")
    return web.json_response({"status": "ok"})


async def cgi_temperature(request: web.Request) -> web.Response:
    temp = get_temperature()
    print(f"[CGI] /cgi-bin/temperature -> {temp}")
    return web.json_response({"temperature": temp})


async def cgi_device_info(request: web.Request) -> web.Response:
    temp = get_temperature()
    info = {
        "deviceModel": "JetKVM",
        "hostname": "jetkvm-mock",
        "ip_address": "127.0.0.1",
        "temperature": temp,
        "uptime_seconds": round(time.monotonic(), 1),
        "mem_total_kb": 262144,
        "mem_available_kb": 131072,
    }
    print(f"[CGI] /cgi-bin/device_info -> temp={temp}")
    return web.json_response(info)


def main():
    app = web.Application()
    app.router.add_get("/cgi-bin/health", cgi_health)
    app.router.add_get("/cgi-bin/temperature", cgi_temperature)
    app.router.add_get("/cgi-bin/device_info", cgi_device_info)

    print("=" * 55)
    print("  Mock JetKVM API Server")
    print("=" * 55)
    print()
    print(f"  Listening on http://127.0.0.1:{PORT}")
    print()
    print(f"  http://127.0.0.1:{PORT}/cgi-bin/health")
    print(f"  http://127.0.0.1:{PORT}/cgi-bin/temperature")
    print(f"  http://127.0.0.1:{PORT}/cgi-bin/device_info")
    print()
    print("=" * 55)
    print()

    web.run_app(app, host="127.0.0.1", port=PORT, print=None)


if __name__ == "__main__":
    main()

