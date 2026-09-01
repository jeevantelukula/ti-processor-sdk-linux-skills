# Device Tree System for K3 / AM62x

## Overview

All hardware configuration on AM62x is described in the Device Tree (DT).
The kernel, U-Boot, and OP-TEE all parse device tree. Understanding the
DT structure is required for GPIO, peripheral configuration, and custom board work.

## DT File Hierarchy

```
arch/arm64/boot/dts/ti/
├── k3-am62.dtsi             — AM625/AM623/AM620 shared peripherals (base hardware)
├── k3-am625-sk.dts          — AM625 SK EVM top-level (includes k3-am625-sk.dtsi)
├── k3-am62x-sk-common.dtsi  — Common SK board configuration
├── k3-am625-beagleplay.dts  — BeaglePlay board
├── k3-am62-mcu.dtsi         — MCU domain peripherals
├── k3-am62-main.dtsi        — MAIN domain peripherals
├── k3-am62-wakeup.dtsi      — WKUP domain peripherals
└── k3-am62-*.dtso           — Device tree overlay sources
```

For a custom board: copy the closest reference `.dts` (e.g., `k3-am625-sk.dts`),
rename it, and modify it to match custom hardware. Never edit upstream `.dtsi` files.

## Pinmux (pinctrl) System

### How It Works

Every pin on the SoC has a PADCONFIG register in the Control Module (CTRL_MMR0).
The pinctrl driver maps these registers to Linux pin groups.

The K3 pinctrl binding uses:
```dts
&main_pmx0 {
    custom_uart0_pins: custom-uart0-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x01c8, PIN_INPUT,  0)   /* UART0_RXD */
            AM625_IOPAD(0x01cc, PIN_OUTPUT, 0)   /* UART0_TXD */
        >;
    };
};
```

Then reference the group in the peripheral node:
```dts
&main_uart0 {
    pinctrl-names = "default";
    pinctrl-0 = <&custom_uart0_pins>;
    status = "okay";
};
```

### AM625_IOPAD Macro

```c
AM625_IOPAD(offset, value, mux_mode)
```

- `offset`: PADCONFIG register offset from CTRL_MMR0 base (find in TRM Table 5.x or SysConfig)
- `value`: bitfield controlling input/pull behavior
- `mux_mode`: 0–7 selects the pin function (GPIO = mode 7 for most pins)

Common `value` macros (from `include/dt-bindings/pinctrl/k3.h`):
```
PIN_OUTPUT          = 0x0         output, pull disabled
PIN_OUTPUT_PULLUP   = PULL_ENABLE | PULL_UP
PIN_OUTPUT_PULLDOWN = PULL_ENABLE
PIN_INPUT           = RXACTIVE               input buffer enabled, pull disabled
PIN_INPUT_PULLUP    = RXACTIVE | PULL_ENABLE | PULL_UP
PIN_INPUT_PULLDOWN  = RXACTIVE | PULL_ENABLE
```

Key bits in the PADCONFIG register:
- Bit 16 (`PULLUDDIS`): 0 = pull enabled, 1 = pull disabled
- Bit 17 (`PULLTYPESEL`): 0 = pull-down, 1 = pull-up
- Bit 18 (`RXACTIVE`): 0 = input buffer disabled, 1 = input buffer enabled (required for inputs)
- Bits [5:0] (`MUXMODE`): select pin function (0–7)

**Common mistake:** Using `PIN_OUTPUT` for a GPIO input. `PIN_OUTPUT` has RXACTIVE=0,
so reading the GPIO always returns 0. Use `PIN_INPUT` for any pin you read.

### SysConfig for Pinmux

TI provides the SysConfig tool to generate pinmux DT snippets:
- Web: https://dev.ti.com/sysconfig
- Select device → Pinmux → assign functions → export DT fragment

The output is the `pinctrl-single,pins` array ready to paste into your DTS.

## GPIO Configuration

### Two-Step Pattern (most common source of confusion)

Configuring a GPIO always requires two edits:

**Step 1 — Pinmux:** Set pin to GPIO function (mode 7) in the pinctrl node:
```dts
&main_pmx0 {
    my_gpio_pins: my-gpio-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x01e8, PIN_INPUT, 7)   /* GPIO1_14 */
        >;
    };
};
```

**Step 2 — GPIO reference:** Reference the GPIO controller and line number:
```dts
/ {
    my_led: my-led {
        compatible = "gpio-leds";
        led-0 {
            label = "my-led";
            gpios = <&main_gpio1 14 GPIO_ACTIVE_HIGH>;
            pinctrl-names = "default";
            pinctrl-0 = <&my_gpio_pins>;
        };
    };
};
```

### GPIO Controller Numbering

AM62x has multiple GPIO banks:
- `main_gpio0` — MAIN domain GPIO bank 0 (GPIO0_0 to GPIO0_87)
- `main_gpio1` — MAIN domain GPIO bank 1 (GPIO1_0 to GPIO1_xx)
- `mcu_gpio0`  — MCU domain GPIO bank (MCU_GPIO0_0 to MCU_GPIO0_22)

The Linux `gpiochip` number assigned to each bank changes between kernel versions
because it depends on probe order. **Always use `gpiodetect` and `gpioinfo` to
find the current chip number** rather than hardcoding it.

```bash
# On target:
gpiodetect                        # lists all GPIO chips
gpioinfo gpiochip0                # lists all lines in chip0
gpioinfo gpiochip0 | grep line14  # find line by name if labeled in DT
```

## Device Tree Overlays

Overlays (`.dtso` source → `.dtbo` binary) allow loading additional DT fragments
at runtime without rebuilding the full DTB.

### Overlay Structure

```dts
// k3-am625-sk-custom-peripheral.dtso
/dts-v1/;
/plugin/;

#include <dt-bindings/gpio/gpio.h>
#include "k3-pinctrl.h"

&main_pmx0 {
    custom_i2c3_pins: custom-i2c3-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x01d0, PIN_INPUT_PULLUP, 2)   /* I2C3_SCL */
            AM625_IOPAD(0x01d4, PIN_INPUT_PULLUP, 2)   /* I2C3_SDA */
        >;
    };
};

&main_i2c3 {
    pinctrl-names = "default";
    pinctrl-0 = <&custom_i2c3_pins>;
    clock-frequency = <100000>;
    status = "okay";
};
```

### Compiling and Loading Overlays

```bash
# Compile (on host, needs kernel DT includes):
dtc -@ -I dts -O dtb -o custom.dtbo custom.dtso

# Load in U-Boot (add to uEnv.txt or extlinux.conf):
# name_overlays=custom.dtbo

# Or load at runtime from Linux (if CONFIG_OF_OVERLAY=y):
mkdir -p /sys/kernel/config/device-tree/overlays/custom
cat custom.dtbo > /sys/kernel/config/device-tree/overlays/custom/dtbo
```

## Status Property

Every peripheral node has `status`. Set to `"okay"` to enable, `"disabled"` to
disable. Peripheral nodes in `.dtsi` files are `disabled` by default; board `.dts`
files enable only the peripherals used by that board.

## Reference

- DT bindings: `Documentation/devicetree/bindings/` in kernel source
- K3 pinctrl binding: `Documentation/devicetree/bindings/pinctrl/ti,k3-pinctrl.yaml`
- AM625 PADCONFIG table: AM62x TRM, Section 5 (Control Module)
- SDK DT how-to: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/devices/AM62X/linux/index.html
