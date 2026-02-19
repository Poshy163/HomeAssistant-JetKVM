"""Test the real JetKVM using the actual JetKVMClient (aiohttp-based)."""
import asyncio
import sys
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import client directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "client",
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "jetkvm", "client.py"),
)
client_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_mod)
JetKVMClient = client_mod.JetKVMClient

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.178"

async def main():
    client = JetKVMClient(host=HOST)

    print("--- check_health ---")
    try:
        ok = await client.check_health()
        print(f"  Result: {ok}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print("--- validate_connection (health + device_info) ---")
    try:
        info = await client.validate_connection()
        print(f"  Result: {info}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print("--- get_temperature ---")
    try:
        temp = await client.get_temperature()
        print(f"  Result: {temp}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print("--- get_all_data ---")
    try:
        data = await client.get_all_data()
        print(f"  Result: {data}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    await client.close()
    print("\nDone.")

asyncio.run(main())

