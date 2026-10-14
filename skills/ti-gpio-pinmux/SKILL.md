---
name: ti-gpio-pinmux
description: >-
  Configure and debug pin multiplexing and GPIO on a TI K3 Linux board: write
  pinctrl-single IOPAD entries in device tree, read live pad registers from
  debugfs, decode pad values, and test lines from user space with libgpiod v2.
  Use when a pin needs a different function/pull/direction, a peripheral does
  not get its pins, a pin conflict is suspected, or a GPIO must be read or driven.
---

# TI GPIO and pinmux

## Docs (MCP)
Follow [../../context/mcp-usage.md](../../context/mcp-usage.md). Always pass
`device=$TI_DOCS_DEVICE os="linux" version=$TI_SDK_VERSION_DOCS`; never rely on defaults (the MCP default device is not yours).
If `$TI_DOCS_DEVICE` is empty, take the docs key from `$TI_KB` or pick it with `ti_processor_sdk_docs_list_variants`.
If `$TI_SDK_VERSION_DOCS` is missing from `ti_processor_sdk_docs_list_versions(device)`, use `version="latest"` and say the page may differ.
Fetch on demand, and cite the doc `path` you used in your answer:
- `ti_processor_sdk_docs_search(query="GPIO driver gpiochip libgpiod", ...)` then read `linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html`
  (e.g. on AM64X the shorter query "GPIO kernel driver" returned PRU pages).
- `ti_processor_sdk_docs_search(query="Pin Mux Tools", ...)` (PinMux tool output must be hand-merged into the board DTS).
- `ti_processor_sdk_docs_search(query="check some device tree information from user-space", ...)`.
- Pad register field layout and mux-mode width: the SoC TRM (not in the MCP); the header parsed by `decode-iopad.py` gives the bit names.
If search returns no page, say so and rely on the SDK kernel tree; do not answer from memory.

## Prerequisites
- SDK on the host and `source lib/ti-sdk-env.sh` (exports `TI_SDK_ROOT`, `TI_KERNEL_SRC_DIR`, `TI_SOC`, `TI_KB`, `TI_FACTS_JSON`, ...).
  Per-device facts (pinmux macro name, default board DTS, pinctrl and GPIO node labels): read `$TI_KB` / `$TI_FACTS_JSON`;
  if they are unset or the file is missing, run skill `ti-generate-kb` first.
- Live checks need a booted board over ssh as root. `/sys/kernel/debug` must be mounted (it was on the verified board).
- libgpiod v2 command-line tools on the target (`gpioinfo --version` must report v2 or later; e.g. an AM62P board image had v2.2.4).

## Steps

### 1. Find the pinmux macro for this SoC
Each SoC has its own macro in the kernel header; do not reuse another SoC's macro.
```bash
H=$TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/k3-pinctrl.h
grep -n "define .*_IOPAD(" "$H"   # one macro per SoC family, plus *_MCU_* / *_WKUP_* variants
grep -n "IOPAD(" $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/<your-board>.dts | head   # which one your board DTS uses
```
Use the macro the SoC's own board DTS and `.dtsi` files use. Main-domain and MCU/WKUP-domain pads use different
macros and different pinctrl nodes.

Syntax (from the header and board DTS): `<SOC>_IOPAD(offset, flags, muxmode)`; flags are the `PIN_*` macros
(`PIN_OUTPUT`, `PIN_INPUT`, `PIN_INPUT_PULLUP`, `PIN_INPUT_PULLDOWN`, `PIN_OUTPUT_PULLUP`, `*_NOST` variants,
drive-strength, debounce, wake-up). List them: `python3 scripts/decode-iopad.py --macros`.
Offset, ball name and mux number come from the SoC datasheet/TRM or the PinMux tool, never from memory. Existing
DTS lines carry the ball and signal in a trailing comment; copy that convention.

### 2. Put it in device tree
Pad entries live in a child node of the pinctrl node (`pinctrl-single,pins`), referenced from the consumer:
```dts
&<pinctrl-label> {
	my_pins_default: my-pins-default {
		pinctrl-single,pins = <
			<SOC>_IOPAD(<offset>, PIN_INPUT, 7) /* (<ball>) <PAD>.GPIOx_y */
		>;
	};
};
&<gpio-controller-label> {
	pinctrl-names = "default";
	pinctrl-0 = <&my_pins_default>;
};
```
Example from AM62P SDK 12.02.00.01.01; yours will differ: `k3-am62p5-sk-rpi-hdr-ehrpwm.dtso` in the SDK kernel does
exactly this (`AM62PX_IOPAD(0x0038, PIN_INPUT, 7) /* (L23) OSPI0_CSn3.GPIO0_14 */`: GPIO is mux 7 there, and in the AM62P, AM62x, AM62A,
AM62L, AM62D and AM64x board DTS; still confirm per pad in the TRM/PinMux tool). `gpio-hog` nodes under an I2C GPIO expander are also shown in that file. For delivering this as
an overlay see `ti-device-tree-overlay`; for a full board DTS see `ti-custom-board-port`.
Before enabling a pad, search the board DTS and its includes for the same offset to find conflicts:
`grep -rn "<offset>" $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/<board>*.dts*`. The SDK overlay above disables
`&dss0` and `&ecap2` with "Conflict:" comments for pads it takes.

### 3. Read live pad state (target)
```bash
ls /sys/kernel/debug/pinctrl/                              # one directory per pin controller (main, MCU, ...)
D=/sys/kernel/debug/pinctrl/<controller-dir>
cat $D/pins            # per pin: owner, register address, raw 32-bit pad value
cat $D/pinmux-pins     # per pin: mux owner (device) and group/function currently applied
cat $D/gpio-ranges     # GPIO number range to pin number map
cat /sys/kernel/debug/pinctrl/pinctrl-maps                 # every pinctrl state the kernel registered
```
Pin number = `(register address - controller base) / 4`; the DTS `offset` is the same register offset.
Example from the AM62P SK board (SDK 12.02.00.01.01; yours will differ): pin 120 (DTS
`AM62PX_IOPAD(0x01e0, PIN_INPUT_PULLUP, 0)` = I2C0_SCL) read `00064000` in `pins`, register address `f41e0` in the controller
whose base is `f4000`; `pinmux-pins` showed owner `20000000.i2c`. The board had two controllers (34 MCU-domain and 172 main-domain pins).

### 4. Decode a pad value
```bash
python3 scripts/decode-iopad.py 0x00064000                   # values (use 0x prefix)
ssh root@<board> cat $D/pins | python3 scripts/decode-iopad.py --pins-file -
python3 scripts/decode-iopad.py --macros                     # PIN_* names and values from the SDK header
```
Bit positions and `PIN_*` values are parsed from `k3-pinctrl.h` at run time (lookup via `TI_KERNEL_SRC_DIR` or
`--header`). Zero-valued fields are omitted; `PULLUDEN=1` means pull disabled (header: `PULL_DISABLE`).
Bits that the header does not name are printed as `unnamed_bits`. The mux-mode field is taken as the low nibble
(`--mux-mask`, default 0xf); confirm the width in the TRM. Tested: `0x00064000` decodes to `PIN_INPUT_PULLUP`,
matching the DTS line above; (example) all 206 pins of the AM62P board (both controllers) decode without error. Bits the header does not
name (for example bit 21 in the reset value `08214007`) show as `unnamed_bits`; zero-valued PIN_* macros are only reported when
they are a direction/pull combination.

### 5. Test a GPIO from user space (target)
`scripts/gpio-test.sh` wraps libgpiod v2 (`list`, `info`, `find`, `read`, `write`, `watch`); copy it to the
board or run `ssh root@<board> 'bash -s -- read gpiochip1 14' < scripts/gpio-test.sh`.
```bash
gpiodetect                         # chips: gpiochipN [label] (lines)
gpioinfo -c gpiochip1              # per line: name, direction, consumer
gpioget --numeric -c gpiochip1 14  # read
gpioset -c gpiochip1 14=1          # drive; held only while gpioset runs (do not use -z in scripts: it detaches)
gpiomon -c gpiochip1 -n 5 14       # wait for 5 edge events
```
Chip numbering is assigned at probe and the SoC GPIO chips are labelled by controller address (for example
`600000.gpio`); always map DTS `&gpio_label` to the chip label with `gpiodetect`, do not assume gpiochip numbers.
`gpioinfo` lists the line name and direction for each offset (names come from DTS `line-name`/`gpio-line-names`).

## Verify
1. `dtc` accepts the DTS/DTSO (`ti-device-tree-overlay/scripts/build-dtbo.sh`).
2. After boot: `pinmux-pins` shows your device as owner of the pad and `pins` decodes to the intended macro.
3. `gpioinfo` shows the line (and `gpio-hog` name if used); `gpioget` / `gpiomon` behave as wired.

## Troubleshooting (verified)
- `pinmux-pins` prints `(MUX UNCLAIMED)` for a pad: no device has applied a pinctrl state containing it. Check
  `pinctrl-names`/`pinctrl-0` on the consumer and its `status` in the live tree under `/proc/device-tree`.
- This skill covers the libgpiod v2 CLI only; `gpio-test.sh` exits if the tools do not report v2 or later (v1 path untested).
- `decode-iopad.py: k3-pinctrl.h not found`: source `lib/ti-sdk-env.sh` or pass `--header`.
- Bare numbers on the decoder command line are decimal; prefix hex with `0x` (`--pins-file` input is hex as printed by debugfs).
- `gpio-test.sh write` releases the line on exit, Ctrl-C or a dropped ssh session, and fails at once if the
  line is busy. Tested against a libgpiod v2 stub, not yet on live hardware.
