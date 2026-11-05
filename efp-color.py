import argparse
import os
import sys
import time

import hid

VID, PID = 0x30FA, 0x1440
INTERFACE = 1

LED_MODE_ADDR = 0x1C
STATIC_MODE = 0xA6  # LED Mode For Full Static Color

G_ADDR, R_ADDR, B_ADDR = 0x23, 0x24, 0x25  # Color Byte Addresses To Support RGB Values
INVERT = True

NAMES = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "yellow": (255, 255, 0),
    "magenta": (255, 0, 255),
    "purple": (160, 32, 240),
    "white": (255, 255, 255),
    "off": (0, 0, 0),
}

here = os.path.dirname(os.path.realpath(__file__))
bundle = getattr(sys, "_MEIPASS", here)

PROFILES = [
    os.path.join(bundle, "efp-1440-profile.hex"),
    os.path.join(here, "efp-1440-profile.hex"),
    "/usr/local/share/evofox-phantom/efp-1440-profile.hex",
]

# Terminal Styling ( Plain Text When Output Is Not A Terminal )
if os.name == "nt":
    os.system(
        ""
    )  # Constant Empty Command, Only Turns On ANSI Escapes In The Windows Console
PLAIN = not sys.stdout.isatty() or "NO_COLOR" in os.environ

RESET, BOLD = "\033[0m", "\033[1m"
ACCENT, GOOD, BAD, MUTED = (
    (200, 120, 255),
    (90, 220, 140),
    (255, 90, 90),
    (140, 140, 150),
)


def fg(rgb):
    r, g, b = rgb

    return "" if PLAIN else f"\033[38;2;{r};{g};{b}m"


def paint(text, rgb=None, bold=False):
    if PLAIN:
        return text

    return (BOLD if bold else "") + (fg(rgb) if rgb else "") + text + RESET


def swatch(rgb, width=4):
    if PLAIN:
        return "#" * width

    r, g, b = rgb

    return f"\033[48;2;{r};{g};{b}m{' ' * width}{RESET}"


def load_profile():
    for path in PROFILES:
        if os.path.exists(path):
            with open(path) as f:
                return [
                    bytes.fromhex(l.strip())
                    for l in f
                    if l.strip() and not l.startswith("#")
                ]

    sys.exit("Profile File ( efp-1440-profile.hex ) Not Found")


def parse_color(s):
    s = s.strip().lower().lstrip("#")

    if s in NAMES:
        return NAMES[s]

    if len(s) == 6 and "," not in s:
        try:
            return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None

    try:
        parts = [int(x, 0) for x in s.split(",")]
    except ValueError:
        return None

    if len(parts) == 3 and all(0 <= x <= 255 for x in parts):
        return tuple(parts)

    return None


def encode(rgb):
    r, g, b = rgb
    f = (lambda v: 255 - v) if INVERT else (lambda v: v)

    return {G_ADDR: f(g), R_ADDR: f(r), B_ADDR: f(b), LED_MODE_ADDR: STATIC_MODE}


def is_write(c):
    return c[1] == 0x18 and c[2] == 0x03


def is_commit(c):
    return c[1] == 0x18 and c[2] in (0x00, 0x09)


def table_addr(c):
    return (c[5] << 8) | (c[4] + c[3])


def patch(cmds, patches):
    # Only The Table Bytes Were Sent.
    # Mouse Keeps It's Own Settings Intact.
    rows = {(a & 0xF8, a >> 8) for a in patches}

    out = []
    seen = set()

    for c in cmds:
        if is_write(c):
            addr = table_addr(c)

            if addr not in patches:
                continue

            c = c[:6] + bytes([patches[addr]]) + c[7:]
            seen.add(addr)

        elif is_commit(c) and (c[4], c[5]) not in rows and (c[4], c[5]) != (0, 0):
            continue

        out.append(c)

    if set(patches) - seen:
        sys.exit("Address Not In Profile ( Profile File Looks Wrong )")

    return out


def mouse_paths():
    # Windows Exposes Every Collection Separately, Settings Channel Is Vendor Page 0xFF01
    devs = [d for d in hid.enumerate(VID, PID) if d["interface_number"] == INTERFACE]
    devs.sort(key=lambda d: d.get("usage_page") != 0xFF01)

    return [d["path"] for d in devs]


def wait_for_mouse(timeout=20):
    end = time.time() + timeout

    while time.time() < end:
        if mouse_paths():
            time.sleep(1.0)
            return

        time.sleep(0.3)

    sys.exit("Mouse Not Found ( Please Connect The Mouse / Check The Connection )")


def send(cmds, delay=0.003):
    h = hid.device()

    for path in mouse_paths():
        try:
            h.open_path(path)
            break
        except OSError:
            continue
    else:
        sys.exit(
            "Failed To Open The Mouse ( Please Check The Connection )\n"
            "If You Are Using Windows, Please Run As Administrator. If On Linux, Please Run As Root."
        )

    try:
        h.get_feature_report(0x07, 8)  # The Vendor App Does This First

        for c in cmds:
            if h.send_feature_report(list(c)) < 0:
                sys.exit("Write Failed : " + h.error())

            time.sleep(delay)
    finally:
        h.close()


def apply(rgb, dry=False):
    patches = encode(rgb)
    cmds = patch(load_profile(), patches)

    if dry:
        shown = {hex(a): hex(v) for a, v in sorted(patches.items())}
        return f"[Dry-Run] {len(cmds)} Packets, Patches {shown}"

    wait_for_mouse()
    send(cmds)

    time.sleep(3.0)  # Mouse Re-Enumerates After A Write
    wait_for_mouse()

    return "Done"


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def draw(current, status):
    names = list(NAMES)
    width = 44

    print("\033[2J\033[H" if not PLAIN else "")
    print(paint("  ╭" + "─" * width + "╮", ACCENT))
    print(
        paint("  │", ACCENT)
        + paint("  ◆  EFP COLORS".ljust(width), bold=True)
        + paint("│", ACCENT)
    )
    print(
        paint("  │", ACCENT)
        + paint("  30fa:1440 · Static Color".ljust(width), MUTED)
        + paint("│", ACCENT)
    )
    print(paint("  ╰" + "─" * width + "╯", ACCENT))

    shown = next((n for n, c in NAMES.items() if c == current), None)
    label = shown or f"custom {current[0]},{current[1]},{current[2]}"

    print(f"\n  Now  {swatch(current, 8)}  {paint(label, bold=True)}\n")

    for i in range(0, len(names), 3):
        row = ""

        for j, n in enumerate(names[i : i + 3], i + 1):
            row += f"  {paint(str(j), ACCENT, True)} {swatch(NAMES[n], 2)} {n:<9}"

        print(row)

    print(
        f"\n  {paint('c', ACCENT, True)} Custom ( R,G,B or Hex )    {paint('q', ACCENT, True)} Quit"
    )
    print(f"\n  {status}\n")


def menu(dry):
    names = list(NAMES)
    current, status = NAMES["white"], paint("Pick A Color To Apply It", MUTED)

    while True:
        draw(current, status)
        s = ask(paint("  ❯ ", ACCENT, True))

        if s in ("q", "quit", "exit"):
            return

        if s == "c":
            s = ask("  Color ( e.g. 255,128,0 or ff8800 ) ❯ ")

        if s.isdigit() and 1 <= int(s) <= len(names):
            s = names[int(s) - 1]

        rgb = parse_color(s) if s else None

        if rgb is None:
            status = paint(
                "✗ Color Not Determined ( Pick A Number, Name Or Custom )", BAD
            )
            continue

        print(
            f"\n  {paint('Applying', ACCENT)} {swatch(rgb, 4)} ...  ( Takes A Few Seconds )"
        )

        try:
            result = apply(rgb, dry)
        except SystemExit as e:
            status = paint(f"✗ {e}", BAD)
            continue

        current = rgb
        status = paint(f"✓ {result}", GOOD)


def main():
    p = argparse.ArgumentParser(
        description="Set A Static LED Color On The 30fa:1440 Mouse ( No Arguments Opens The Menu )"
    )
    p.add_argument(
        "color",
        nargs="?",
        help=f"Name, R,G,B Or Hex ( Supported : {', '.join(NAMES)} )",
    )
    p.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show What Would Be Sent To The Mouse, But Don't Actually Send It",
    )
    args = p.parse_args()

    if not args.color:
        return menu(args.dry_run)

    rgb = parse_color(args.color)

    if rgb is None:
        sys.exit("Color Not Determined ( Please Try A Color From The Supported List )")

    print(apply(rgb, args.dry_run))


if __name__ == "__main__":
    main()
