#!/usr/bin/env python3
"""Tiny REPL for controlling keyboard LEDs (Caps Lock / Scroll Lock).

Commands:
  ls                                   list connected keyboards, numbered as $1, $2, ...
  blink $1 capslk on [-every 1s]       turn caps lock LED on, blinking every 1s by default
  blink $1 scrlk on [-every 500ms]     turn scroll lock LED on, blinking every 1s by default
  blink $1 numlk on [-every 1s]        turn num lock LED on, blinking every 1s by default
  blink $1 capslk off                  turn caps lock LED off
  status                               list currently running blink schedules
  help | ?                             show this help
  quit | exit                          exit

Devices can be targeted either by their $N shortcut (from the last 'ls') or
by their full "<manufacturer> <product>" name (quote it if it has spaces,
e.g. "Apple Inc. Apple Internal Keyboard / Trackpad"). If a $N shortcut is
unknown, the device table is refreshed automatically before giving up (so
you can blind-fire commands without running 'ls' first).

Operations run in a persistent background thread keyed by device name, so if
a keyboard disconnects and reconnects the target device keeps blinking.
"""

import os
import re
import readline
import shlex
import sys
import threading
import time

import hid

HISTORY_FILE = os.path.expanduser("~/.blink_keyboard_leds_history")
HISTORY_SIZE = 1000

NUM_LOCK = 0x01
CAPS_LOCK = 0x02
SCROLL_LOCK = 0x04

LEDS = {
    "numlk": NUM_LOCK,
    "capslk": CAPS_LOCK,
    "scrlk": SCROLL_LOCK,
}
LED_NAMES = {v: k for k, v in LEDS.items()}

TICK = 0.05
DEFAULT_INTERVAL = 1.0


def find_keyboards():
    return [d for d in hid.enumerate() if d["usage_page"] == 1 and d["usage"] == 6]


def device_name(d):
    return f"{d['manufacturer_string']} {d['product_string']}"


def parse_duration(s):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s)?", s)
    if not m:
        raise ValueError(f"bad duration: {s!r}")
    value, unit = m.groups()
    value = float(value)
    return value / 1000.0 if unit == "ms" else value


class LedController:
    def __init__(self):
        self._lock = threading.Lock()
        # (name, led) -> {blinking, interval, state, next_toggle}
        self._ops = {}
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set(self, led, name, on, interval=None):
        with self._lock:
            key = (name, led)
            if not on:
                self._ops.pop(key, None)
            else:
                self._ops[key] = {
                    "blinking": interval is not None,
                    "interval": interval,
                    "state": True,
                    "next_toggle": time.monotonic() + (interval or 0),
                }
            self._flush(name)

    def active(self):
        with self._lock:
            return [
                (name, led, op["blinking"], op["interval"])
                for (name, led), op in self._ops.items()
            ]

    def _flush(self, name):
        mask = 0x00
        for (op_name, led), op in self._ops.items():
            if op_name == name and op["state"]:
                mask |= led
        if not self._write(name, mask):
            dead_keys = [k for k in self._ops if k[0] == name]
            for k in dead_keys:
                del self._ops[k]
            if dead_keys:
                print(f"[blink] deactivated all schedules for {name!r}")

    def _write(self, name, mask):
        for d in find_keyboards():
            if device_name(d) == name:
                try:
                    dev = hid.Device(path=d["path"])
                    dev.write(bytes([0x00, mask]))
                    dev.close()
                    return True
                except Exception as e:
                    print(f"[blink] write failed for {name!r}: {e}")
                    return False
        print(f"[blink] device not found: {name!r}")
        return False

    def _run(self):
        while True:
            now = time.monotonic()
            with self._lock:
                dirty_names = set()
                for (name, _led), op in self._ops.items():
                    if not op["blinking"]:
                        continue
                    if now >= op["next_toggle"]:
                        op["state"] = not op["state"]
                        op["next_toggle"] = now + op["interval"]
                        dirty_names.add(name)
                for name in dirty_names:
                    self._flush(name)
            time.sleep(TICK)


def cmd_help():
    print(__doc__.strip())


def cmd_ls(shortcuts):
    shortcuts.clear()
    for i, d in enumerate(find_keyboards(), start=1):
        name = device_name(d)
        shortcuts[f"${i}"] = name
        print(f"  ${i} - {name}  (path={d['path']})")


def cmd_status(controller):
    ops = controller.active()
    if not ops:
        print("  (no active schedules)")
        return
    for name, led, blinking, interval in ops:
        led_name = LED_NAMES.get(led, hex(led))
        detail = f"blinking every {interval}s" if blinking else "solid on"
        print(f"  {name}  {led_name}  {detail}")


def cmd_blink(controller, shortcuts, args):
    if len(args) < 3:
        print("usage: blink <name|$N> <capslk|scrlk|numlk> <on|off> [-every <duration>]")
        return
    name, led_name, state = args[0], args[1], args[2]
    rest = args[3:]

    if name.startswith("$"):
        if name not in shortcuts:
            cmd_ls(shortcuts)
        if name not in shortcuts:
            print(f"unknown shortcut: {name!r} (no such device after refresh)")
            return
        name = shortcuts[name]

    if led_name not in LEDS:
        print(f"unknown led: {led_name!r} (expected capslk, scrlk, or numlk)")
        return
    if state not in ("on", "off"):
        print(f"unknown state: {state!r} (expected on or off)")
        return

    interval = DEFAULT_INTERVAL if state == "on" else None
    if rest:
        if len(rest) != 2 or rest[0] != "-every":
            print("usage: blink <name|$N> <capslk|scrlk|numlk> on [-every <duration>]")
            return
        try:
            interval = parse_duration(rest[1])
        except ValueError as e:
            print(e)
            return

    controller.set(LEDS[led_name], name, state == "on", interval)


def main():
    readline.set_history_length(HISTORY_SIZE)
    try:
        readline.read_history_file(HISTORY_FILE)
    except FileNotFoundError:
        pass

    controller = LedController()
    shortcuts = {}
    print("blink_keyboard_leds: type 'help' for commands, 'quit' to exit")
    try:
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            try:
                parts = shlex.split(line)
            except ValueError as e:
                print(f"parse error: {e}")
                continue
            if not parts:
                continue
            cmd, args = parts[0], parts[1:]
            if cmd in ("help", "?"):
                cmd_help()
            elif cmd == "ls":
                cmd_ls(shortcuts)
            elif cmd == "status":
                cmd_status(controller)
            elif cmd == "blink":
                cmd_blink(controller, shortcuts, args)
            elif cmd in ("quit", "exit"):
                break
            else:
                print(f"unknown command: {cmd!r}")
    finally:
        readline.write_history_file(HISTORY_FILE)


if __name__ == "__main__":
    sys.exit(main())
