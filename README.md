# Evofox-Phantom-Color (EFP Color)

> The original script now lives in [`archive/`](archive/evofox-phantom.py); `make install` still installs it. The active tool in this repo is [EFP Colors](#efp-colors-instant--anko-rgb-gaming-mouse-usb-30fa1440) below.

This is a small python script that can be used to toggle LED modes of an Amkette Evofox Phantom Gaming mouse.

https://github.com/user-attachments/assets/acca0d2a-3564-4e87-ab82-af991ddd2b97

I wrote this because the configuration tool that shipped with the mouse was only available (in binary form) for Microsoft Windows. Also it did not had the option to keep a constant color on the mouse. This script allows you to set a constant color on the mouse, and also to toggle between different colors.

The `.exe` release of this script is available in the [releases](https://github.com/SpreadSheets600/Evofox-Phantom-Color/releases)

<img width="941" height="436" alt="dms_capture_1793814383315" src="https://github.com/user-attachments/assets/2be70233-7fa1-4505-b71d-72c7cf0eaefb" />

> [!NOTE]
> Based on your permissions, you may need to run this script with `sudo` or add a udev rule for the mouse. Or if you are on windows then you might need to run the script as administrator.

Phantom supports four modes: off, static, slow and fast. This program,
at present only supports toggling LEDs.

## Install

**Dependencies**: hidapi

```
sudo pip install hidpi
```

or alternatively on arch linux systems,

```
sudo pacman -S python-hidapi
```

Install

``` bash
git clone https://github.com/SpreadSheets600/Evofox-Phantom-Color.git
cd Evofox-Phantom-Color
```

``` bash
sudo make install
```

or

``` bash
sudo make install-efp        # installs the `efp-color` command
```

## EFP Colors: INSTANT (USB 30fa:1440)

EFP Colors (`efp-color.py`, formerly `anko-color.py`) is the colour tool for this mouse. It is sold under names like "Anko Gaming RGB Mouse" (Kmart). Its vendor app is Windows-only, so `efp-color.py` lets Linux (and, untested, macOS) users set the LED colour without it. The protocol was worked out from the vendor app's USB capture ([OpenRGB issue #3551](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3551)).

This is separate from the Evofox Phantom script above: different USB ID, different protocol. Everything lives in one file, `efp-color.py`, plus the captured profile `efp-1440-profile.hex`.

**Status:**

| Feature | State |
| --- | --- |
| Static LED colour (named, `r,g,b` or hex) via `efp-color.py` | works; colour model inferred from single-byte tests (see research notes) |
| LED effects (beats / pulse / rainbow / off) | researched but removed from the tool, see "Research log" |
| DPI, polling rate | not found, not supported |
| Windows / macOS | untested by hand, the Windows build is smoke-tested in CI |

## Usage

Run it with no arguments for the menu. Pick a colour by number and it is
applied immediately; `c` takes a custom `R,G,B` or hex value, `q` quits.

``` bash

python efp-color.py              # menu
python efp-color.py red          # apply directly
python efp-color.py "#ff8800"
python efp-color.py 255,128,0
python efp-color.py red -n       # dry run: show what would be sent

```

Named colours: red, green, blue, cyan, yellow, magenta, purple, white, off.
The mouse reboots for about 3 seconds after each change.

Every apply rewrites the mouse's whole settings table from `efp-1440-profile.hex` (captured from the vendor app), changing only the colour and mode bytes, so any custom button/DPI settings stored on the mouse are reset to that profile.

Linux needs permission to open the hidraw device: run with `sudo`, or add a
udev rule for `30fa:1440` that tags it `uaccess` and re-plug the mouse.

**Prebuilt binaries (no Python needed):** download from the repo's Releases
page, one for each OS. They are built by `.github/workflows/release.yml`.

``` bash

$ chmod +x efp-color-linux-x86_64 && sudo ./efp-color-linux-x86_64 red
> efp-color-windows-x86_64.exe red

```

Each release also has a `SHA256SUMS.txt`. Pull requests and manual workflow
runs build both binaries as Actions artifacts without publishing.

**Cutting a release:** push a tag, and the workflow builds both binaries,
smoke-tests them with `--dry-run`, and publishes the release.

``` bash

git tag v0.1.0 && git push origin v0.1.0

```

Build by hand with `pip install hidapi pyinstaller`, then
`pyinstaller --onefile --name efp-color --add-data "efp-1440-profile.hex:." efp-color.py`
(use `;` instead of `:` on Windows).

## Research log

How this was worked out: the vendor app's USB capture attached to [OpenRGB issue #3551](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3551) (plus the labelled captures for the sibling 30fa:1030 mouse in [issue #2496](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2496)) was parsed to extract the control transfers, and the findings were then tested
on a real 30fa:1440 mouse.

**Transport.** Two HID interfaces: 0 is a plain boot mouse (report ID 1), 1 carries keyboard/consumer collections plus vendor pages. Settings are sent as 8-byte HID *feature* reports with report ID 7 on interface 1 (vendor usage page `0xFF01`), not as output reports like the Evofox Phantom. On Linux interface 1 is a single hidraw node; Windows exposes each collection separately, so the tool prefers the `0xFF01` one.

**Writing the settings table.**

| Packet | Meaning |
| --- | --- |
| `07 18 03 IDX ROW PAGE VAL 07` | write `VAL` at address `PAGE<<8 \| (ROW+IDX)` (`ROW` is a multiple of 8, `IDX` 0-7) |
| `07 18 09 ...`, `07 18 00 ...` | commit packets after each row |
| `07 18 10 ...`, `07 18 00 ...`, `07 20 00 ...` | end of transfer; the mouse then reboots and re-enumerates (~3 s) |

The vendor app rewrites the whole table (addresses `0x08`-`0x2cf`, 870 packets here) on every Apply, so `efp-1440-profile.hex` replays that sequence with chosen bytes patched. Its interleaved `07 13 ff ...` packets are not needed and are skipped. Rows `0x78`-`0x7f` end in a different byte and cannot be patched. Reading back (`07 18 05 IDX ROW 00 00 07` + GET_REPORT)
did not return the stored settings on our unit (the values drift between calls), so the table cannot be read back.

**Known table bytes.**

| Address | Meaning | Evidence |
| --- | --- | --- |
| `0x1c` | LED mode (high nibble) and effect level (low nibble) | tested on a 30fa:1440, values below |
| `0x23`, `0x24`, `0x25` | static colour, G, R, B, inverted: `0x00` = full on, `0xff` = off | single-byte tests in mode `0xa5`: `0x23=ff` gave purple, `0x24=ff` cyan, `0x25=ff` yellow |
| `0x2b` | `0xff` turned the LEDs off | single-byte test |
| `0x20`-`0x22`, `0x26`-`0x2a` | no visible effect in static mode | single-byte tests |
| `0x3f` | brightness | only seen on the sibling 30fa:1030; unverified here, not used |

Mode byte `0x1c`, values from the early by-eye tests (low nibble was 5 for
all of them):

| Value | Result | Value | Result |
| --- | --- | --- | --- |
| `0x85` | green | `0xd5` | medium flickering blue |
| `0x95` | blue | `0xe5` | rainbow |
| `0xa5` | constant green | `0xf5` | fast rainbow |
| `0xb5` | flickering blue | `0x87`, `0x97` | off |
| `0xc5` | fast flickering blue | | |

Later finding: within the `0xa_` family the low nibble is an effect level, `0xa1` (slow beats) up to `0xa6` (full static). The tool now writes `0xa6`.

Caveats: with all 7 colour slots set to the same RGB bytes in mode `0xa5`, red gave purple and blue gave yellow (matching the inverted model), but green and white gave a slow rainbow instead of cyan / off. This was unexplained at the time; since `0xa5` turned out not to be full static, the effect level may be the cause, but that has not been re-tested.

**Not found.** DPI and polling rate. The vendor config names them
(`DPI_SET0-5`, `USB_SPEED`) but no table offset was located, and the
planned byte-by-byte measurement was never completed.

**Side effect.** Every write replaces the mouse's saved table with the
captured profile, so previously stored button/DPI settings are overwritten.

## TODO

* Add toggling DPI values
* Add re-configuring mouse buttons.
* Hack and see if the LEDs can be illuminated individually to a color
of choice.

### Credits

> Original script by [@bojle](https://github.com/bojle/evofox-phantom)
