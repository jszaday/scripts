import hid
import time

SCROLL_LOCK = 0x04
BLINK_COUNT = 4
BLINK_INTERVAL = 0.3

devices = [d for d in hid.enumerate() if d['usage_page'] == 1 and d['usage'] == 6]

for d in devices:
    name = f"{d['manufacturer_string']} {d['product_string']}"
    path = d['path']
    print(f"\nTrying: {name} (path={path})")
    try:
        dev = hid.Device(path=path)
        for i in range(BLINK_COUNT):
            dev.write(bytes([0x00, SCROLL_LOCK]))
            time.sleep(BLINK_INTERVAL)
            dev.write(bytes([0x00, 0x00]))
            time.sleep(BLINK_INTERVAL)
        dev.close()
        print("  Done (no error)")
    except Exception as e:
        print(f"  Error: {e}")
