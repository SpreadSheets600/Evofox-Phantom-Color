# Evofox-phantom

This is a small python script that can be used to toggle LED
modes of an Amkette Evofox Phantom Gaming mouse. 

I wrote this because the configuration tool that shipped with the 
mouse was only available (in binary form) for Microsoft Windows.

```
$ evofox-phantom -h
usage: evofox-phantom [-h] [--vid VID] [--pid PID]
					  [-l [{off,static,slow,fast}]]

Toggle LED modes in Amkette Evofox Gaming Mouse

options:
  -h, --help            show this help message and exit
  --vid VID             Vendor ID; lsusb(8)
  --pid PID             Product ID; lsusb(8)
  -l [{off,static,slow,fast}], --led [{off,static,slow,fast}]
```

Phantom supports four modes: off, static, slow and fast. This program,
at present only supports toggling LEDs.

Here's a demo [video](https://youtu.be/1RXHDZS5G4I):

# Install

**Dependencies**: hidapi

```
$ sudo pip install hidpi
```

or alternatively on arch linux systems, 

```
$ sudo pacman -S python-hidapi
```

Install 

```
$ git clone https://github.com/bojle/evofox-phantom.git
$ cd evofox-phantom
$ make install
```

# Other mouse: INSTANT / Anko RGB Gaming Mouse (USB 30fa:1440)

Sold under names like "Anko Gaming RGB Mouse" (Kmart). Its vendor app is
Windows-only, so these scripts let Linux (and, untested, macOS) users set the
LEDs without it. The protocol was worked out from the vendor app's USB
capture ([OpenRGB issue #3551](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3551)).
This is separate from the Evofox Phantom script above: different USB ID,
different protocol.

**Status:**

| Feature | State |
|---|---|
| LED mode (static / breathing / flicker / rainbow / off) via `anko-mouse.py --led` | works, confirmed on real hardware (Linux) |
| Custom static colour via `anko-color.py` | experimental: the colour model is inferred, run `--calibrate` to check it on your mouse |
| DPI, polling rate | not found, not supported |
| Windows / macOS | untested |

See "Research notes" below for what is known about the protocol.

```
$ pip install hidapi            # or: sudo pacman -S python-hidapi
$ sudo make install-anko        # installs anko-color and anko-mouse
$ sudo make install-udev        # optional: use them without sudo (re-plug the mouse)
```

Set a constant colour (name, `#rrggbb` or `r,g,b`):

```
$ anko-color red
$ anko-color "#ff8800"
$ anko-color --calibrate        # short interactive check of the colour model
```

Without installing, run `python anko-color.py ...` from this directory.
`anko-mouse.py` is the low-level tool (`--led BYTE`, `--set ADDR=VAL`,
`--dry-run`). It rewrites the mouse's whole settings table from
`anko-1440-profile.hex` (captured from the vendor app), changing only the
bytes you ask for, so any custom button/DPI settings stored on the mouse are
reset to that profile. The mouse reboots for ~3 seconds after each change.

**Windows without Python:** download `anko-color.exe` from the repo's
Releases page (or the latest "build-windows-exe" run under Actions ->
Artifacts) and run it from Command Prompt / PowerShell, no install needed:

```
> anko-color.exe red
> anko-color.exe #ff8800
```

(The .exe is built by `.github/workflows/build-windows.yml`. To build it
yourself on Windows: `pip install hidapi pyinstaller`, then
`pyinstaller --onefile --name anko-color --add-data "anko-mouse.py;." --add-data "anko-1440-profile.hex;." anko-color.py`.)

Prefer Python? `winget install Python.Python.3.12`, then `pip install hidapi`
and `python anko-color.py red`. No admin rights are needed for the mouse.
All of this is untested on Windows, and macOS is untested too.

## Research notes (30fa:1440)

How this was worked out: the vendor app's USB capture attached to
[OpenRGB issue #3551](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3551)
(plus the labelled captures for the sibling 30fa:1030 mouse in
[issue #2496](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2496)) was
parsed to extract the control transfers, and the findings were then tested
on a real 30fa:1440 mouse.

**Transport.** Two HID interfaces: 0 is a plain boot mouse (report ID 1),
1 carries keyboard/consumer collections plus vendor pages. Settings are sent
as 8-byte HID *feature* reports with report ID 7 on interface 1 (vendor
usage page `0xFF01`), not as output reports like the Evofox Phantom.

**Writing the settings table.**

| Packet | Meaning |
|---|---|
| `07 18 03 IDX ROW PAGE VAL 07` | write `VAL` at address `PAGE<<8 \| (ROW+IDX)` (`ROW` is a multiple of 8, `IDX` 0-7) |
| `07 18 09 ...`, `07 18 00 ...` | commit packets after each row |
| `07 18 10 ...`, `07 18 00 ...`, `07 20 00 ...` | end of transfer; the mouse then reboots and re-enumerates (~3 s) |

The vendor app rewrites the whole table (addresses `0x08`-`0x2cf`, 870
packets here) on every Apply, so `anko-1440-profile.hex` replays that
sequence with chosen bytes patched. Its interleaved `07 13 ff ...` packets
are not needed and are skipped. Rows `0x78`-`0x7f` end in a different byte
and cannot be patched. Reading back (`07 18 05 IDX ROW 00 00 07` + GET_REPORT)
did not return the stored settings on our unit (the values drift between
calls), so the table cannot be read back.

**Known table bytes.**

| Address | Meaning | Evidence |
|---|---|---|
| `0x1c` | LED mode | tested on a 30fa:1440, values below |
| `0x23`, `0x24`, `0x25` | static colour, apparently G, R, B with `0x00` = full on, `0xff` = off | single-byte tests in mode `0xa5`: `0x23=ff` gave purple, `0x24=ff` cyan, `0x25=ff` yellow |
| `0x2b` | `0xff` turned the LEDs off | single-byte test |
| `0x20`-`0x22`, `0x26`-`0x2a` | no visible effect in static mode | single-byte tests |
| `0x3f`, low nibble of `0x1c` | brightness, speed | only seen on the sibling 30fa:1030; unverified here |

LED mode byte `0x1c` as seen by eye (the low nibble was 5 for all of them):

| Value | Result | Value | Result |
|---|---|---|---|
| `0x85` | green | `0xd5` | medium flickering blue |
| `0x95` | blue | `0xe5` | rainbow |
| `0xa5` | **constant green (static)** | `0xf5` | fast rainbow |
| `0xb5` | flickering blue | `0x87`, `0x97` | off |
| `0xc5` | fast flickering blue | | |

Caveats: with all 7 colour slots set to the same RGB bytes in mode `0xa5`,
red gave purple and blue gave yellow (matching the inverted model), but
green and white gave a slow rainbow instead of cyan / off, which is
unexplained. The colour model in `anko-color.py` is therefore unverified.

**Not found.** DPI and polling rate. The vendor config names them
(`DPI_SET0-5`, `USB_SPEED`) but no table offset was located, and the
planned byte-by-byte measurement was never completed.

**Side effect.** Every write replaces the mouse's saved table with the
captured profile, so previously stored button/DPI settings are overwritten.

# TODO

* Add toggling DPI values
* Add re-configuring mouse buttons.
* Hack and see if the LEDs can be illuminated individually to a color
of choice.

