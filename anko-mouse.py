#!/usr/bin/python

##
## Control the LEDs of an "INSTANT USB Gaming Mouse" (Anko / Kmart RGB mouse),
## USB ID 30fa:1440, over HID. Same idea as evofox-phantom.py, different protocol.
##
## Protocol (from the vendor app's capture, OpenRGB issue #3551):
##   Everything is an 8-byte HID *feature* report, report ID 7, interface 1.
##   The mouse keeps its settings in a small table. The vendor app rewrites
##   the whole table on every "Apply": 07 18 03 <idx> <row> <page> <value> 07
##   writes one byte at address <page><row+idx>, with 09/00 commit packets
##   after each row and 10/00/20 packets at the end.
##   anko-1440-profile.hex holds that exact sequence; this script replays it,
##   patching the bytes you ask for.
##
## Known table bytes (from the sibling 30fa:1030 mouse; verify on yours):
##   0x1c  LED mode (high nibble) / speed (low nibble)
##   0x3f  brightness
##

import os
import sys
import time
import argparse
import hid

VID = 0x30fa
PID = 0x1440
INTERFACE = 1
LED_MODE_ADDR = 0x1c

here = os.path.dirname(os.path.realpath(__file__))
bundle = getattr(sys, "_MEIPASS", here)   # PyInstaller unpack dir (Windows .exe)
profile_candidates = [os.path.join(bundle, "anko-1440-profile.hex"),
                      os.path.join(here, "anko-1440-profile.hex"),
                      "/usr/local/share/evofox-phantom/anko-1440-profile.hex"]


def load_profile():
    for path in profile_candidates:
        if os.path.exists(path):
            with open(path) as f:
                return [bytes.fromhex(l.strip()) for l in f
                        if l.strip() and not l.startswith("#")]
    sys.exit("anko-1440-profile.hex not found")


def patch(cmds, patches):
    """Apply {address: value} to the byte-write packets of the profile."""
    seen = set()
    out = []
    for c in cmds:
        if c[1] == 0x18 and c[2] == 0x03 and c[7] == 0x07:
            addr = (c[5] << 8) | (c[4] + c[3])
            if addr in patches:
                c = c[:6] + bytes([patches[addr]]) + c[7:]
                seen.add(addr)
        out.append(c)
    missing = set(patches) - seen
    if missing:
        sys.exit("address(es) not in profile: " +
                 ", ".join(hex(a) for a in sorted(missing)))
    return out


def open_mouse(vid, pid):
    # Linux exposes interface 1 as one hidraw node. Windows exposes each of
    # its top-level collections separately (keyboard, consumer, vendor...);
    # the settings channel (report ID 7) is the vendor page 0xFF01.
    cands = [d for d in hid.enumerate(vid, pid)
             if d["interface_number"] == INTERFACE]
    cands.sort(key=lambda d: d.get("usage_page") != 0xFF01)
    for d in cands:
        h = hid.device()
        try:
            h.open_path(d["path"])
        except OSError:
            continue
        return h
    if cands:
        raise OSError("could not open the mouse's HID interface")
    sys.exit("Mouse %04x:%04x not found (is it plugged in?)" % (vid, pid))


def send(cmds, vid, pid, delay):
    try:
        h = open_mouse(vid, pid)
    except OSError:
        sys.exit("Cannot open the HID device: run as root or add a udev rule")
    try:
        h.get_feature_report(0x07, 8)  # the vendor app does this first
        for c in cmds:
            if h.send_feature_report(list(c)) < 0:
                sys.exit("write failed: " + h.error())
            time.sleep(delay)
    finally:
        h.close()


def auto_int(s):
    return int(s, 0)


def main():
    p = argparse.ArgumentParser(description="Set LED options on 30fa:1440 mouse")
    p.add_argument("--vid", type=auto_int, default=VID)
    p.add_argument("--pid", type=auto_int, default=PID)
    p.add_argument("-l", "--led", type=auto_int, metavar="BYTE",
                   help="value for table byte 0x1c (LED mode<<4 | speed)")
    p.add_argument("-b", "--brightness", type=auto_int, metavar="BYTE",
                   help="value for table byte 0x3f")
    p.add_argument("--set", action="append", default=[], metavar="ADDR=VAL",
                   help="patch any table byte, e.g. --set 0x20=0xf0 (repeatable)")
    p.add_argument("--delay", type=float, default=0.003,
                   help="seconds between packets (default 0.003)")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="show what would change, send nothing")
    args = p.parse_args()

    patches = {}
    if args.led is not None:
        patches[LED_MODE_ADDR] = args.led
    if args.brightness is not None:
        patches[0x3f] = args.brightness
    for item in args.set:
        a, v = item.split("=")
        patches[auto_int(a)] = auto_int(v)
    if any(not 0 <= v <= 0xff for v in patches.values()):
        sys.exit("values must be 0..255")

    cmds = patch(load_profile(), patches)
    print("patches:", {hex(a): hex(v) for a, v in sorted(patches.items())} or "none",
          "| packets:", len(cmds))
    if args.dry_run:
        return
    send(cmds, args.vid, args.pid, args.delay)
    print("done")


if __name__ == "__main__":
    main()
