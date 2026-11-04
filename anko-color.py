#!/usr/bin/env python3

##
## Set a constant (static) LED colour on the 30fa:1440 "INSTANT USB Gaming
## Mouse" (Anko / Kmart RGB mouse). Works on Linux and Windows.
##
##   python anko-color.py red
##   python anko-color.py "#ff8800"
##   python anko-color.py 255,128,0
##   python anko-color.py --calibrate      # short interactive check
##
## Only the LED mode byte (-> static) and the colour bytes are changed; the
## rest of the settings table is replayed as-is (see anko-mouse.py).
##
## Requirements: Python 3 + the `hid` module (pip install hidapi).
## Linux: run as root (sudo) or add a udev rule. Windows: no admin needed.
##

import argparse
import importlib.util
import json
import os
import sys
import time
from datetime import datetime

import hid

here = getattr(sys, "_MEIPASS", os.path.dirname(os.path.realpath(__file__)))
spec = importlib.util.spec_from_file_location(
    "ankomouse", os.path.join(here, "anko-mouse.py"))
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)

REPORT = os.path.join(
    os.path.dirname(os.path.realpath(sys.argv[0])), "anko-color-report.json")

STATIC_MODE = 0xa5          # "constant colour" (confirmed by eye)

# Colour model, inferred from byte-by-byte tests (each byte = one channel,
# inverted: 0x00 = full on, 0xff = off). Check it with --calibrate.
G_ADDR, R_ADDR, B_ADDR = 0x23, 0x24, 0x25
INVERT = True

NAMES = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255),
    "purple": (160, 32, 240), "orange": (255, 128, 0),
    "pink": (255, 80, 160), "off": (0, 0, 0),
}


def parse_color(s):
    s = s.strip().lower()
    if s in NAMES:
        return NAMES[s]
    if "," in s:
        parts = [int(x, 0) for x in s.split(",")]
        if len(parts) == 3 and all(0 <= x <= 255 for x in parts):
            return tuple(parts)
    else:
        h = s.lstrip("#")
        if len(h) == 6:
            try:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                pass
    sys.exit("don't understand colour %r (try red, #ff8800 or 255,128,0)" % s)


def encode(rgb):
    """RGB -> {table address: value} for the static colour."""
    r, g, b = rgb
    f = (lambda v: 255 - v) if INVERT else (lambda v: v)
    return {G_ADDR: f(g), R_ADDR: f(r), B_ADDR: f(b)}


# ---------------------------------------------------------------- device ----

def have_mouse():
    return any(d["interface_number"] == am.INTERFACE
               for d in hid.enumerate(am.VID, am.PID))


def wait_for_mouse(timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if have_mouse():
            time.sleep(1.0)
            return
        time.sleep(0.3)
    sys.exit("mouse did not (re)appear; check the cable")


def apply(patches, dry=False):
    cmds = am.patch(am.load_profile(), patches)
    if dry:
        print("[dry-run] %d packets, patches: %s" % (
            len(cmds), {hex(a): hex(v) for a, v in sorted(patches.items())}))
        return
    wait_for_mouse()
    try:
        am.send(cmds, am.VID, am.PID, 0.003)
    except OSError as e:
        sys.exit("cannot open the mouse (%s). Linux: run with sudo." % e)
    time.sleep(3.0)               # the mouse reboots after a write
    wait_for_mouse()


# ------------------------------------------------------------- calibrate ----

def zeroed_colors():
    return {a: 0 for a in range(0x20, 0x35)}


def calibrate(dry):
    rep = {"started": datetime.now().isoformat(timespec="seconds"),
           "raw": [], "verify": []}

    def save():
        with open(REPORT, "w") as f:
            json.dump(rep, f, indent=1)
        try:
            os.chmod(REPORT, 0o666)
        except OSError:
            pass

    def ask(q):
        if dry:
            print(q + " [dry-run]")
            return ""
        try:
            return input(q).strip()
        except EOFError:
            return ""

    print("Type what the LEDs show after each change, in a few words "
          "(colour + dim/bright), e.g. 'bright blue', 'off'.\n")
    raw = [
        ("00,00,00", (0, 0, 0), 0),
        ("ff,ff,00", (255, 255, 0), 0),
        ("ff,00,ff", (255, 0, 255), 0),
        ("00,ff,ff", (0, 255, 255), 0),
        ("ff,ff,ff", (255, 255, 255), 0),
        ("ff,ff,80", (255, 255, 0x80), 0),
        ("ff,ff,f0", (255, 255, 0xf0), 0),
        ("ff,ff,0f", (255, 255, 0x0f), 0),
        ("ff,ff,00 + byte 0x2b=0xbf", (255, 255, 0), 0xbf),
    ]
    print("--- raw bytes (0x23, 0x24, 0x25) ---")
    for name, (b23, b24, b25), gate in raw:
        p = zeroed_colors()
        p.update({0x23: b23, 0x24: b24, 0x25: b25, 0x2b: gate,
                  am.LED_MODE_ADDR: STATIC_MODE})
        apply(p, dry)
        seen = ask("  %-26s -> you see? " % name)
        rep["raw"].append({"name": name, "bytes": {"0x23": b23, "0x24": b24,
                                                   "0x25": b25, "0x2b": gate},
                           "seen": seen})
        save()

    print("\n--- model check (real colours; other colour bytes untouched) ---")
    for name in ("red", "green", "orange", "white", "pink"):
        p = {am.LED_MODE_ADDR: STATIC_MODE}
        p.update(encode(NAMES[name]))
        apply(p, dry)
        seen = ask("  asked for %-7s -> you see? " % name)
        rep["verify"].append({"color": name, "rgb": list(NAMES[name]),
                              "seen": seen})
        save()

    print("\nRestoring default colours...")
    apply({am.LED_MODE_ADDR: STATIC_MODE}, dry)
    print("Done. Report:", REPORT)


# ------------------------------------------------------------------ main ----

def main():
    p = argparse.ArgumentParser(
        description="Set a static LED colour on the 30fa:1440 mouse")
    p.add_argument("color", nargs="?",
                   help="name, #rrggbb or r,g,b (e.g. red, '#ff8800', 255,0,0)")
    p.add_argument("--calibrate", action="store_true",
                   help="interactive check of the colour model")
    p.add_argument("--keep-mode", action="store_true",
                   help="don't switch the LED mode to static")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="show what would be written, send nothing")
    args = p.parse_args()

    if args.calibrate:
        calibrate(args.dry_run)
        return
    if not args.color:
        if getattr(sys, "frozen", False) and os.name == "nt":
            # double-clicked .exe: show help and keep the window open
            p.print_help()
            input("\nPress Enter to close...")
            return
        p.error("give a colour (or --calibrate)")

    rgb = parse_color(args.color)
    patches = encode(rgb)
    if not args.keep_mode:
        patches[am.LED_MODE_ADDR] = STATIC_MODE
    print("colour %s -> %s" % (rgb, {hex(a): hex(v)
                                     for a, v in sorted(patches.items())}))
    apply(patches, args.dry_run)
    if not args.dry_run:
        print("done")


if __name__ == "__main__":
    main()
