---
name: gpio-pinmux
version: "1.0.0"
description: >
  Configure GPIO pins and pinmux on TI K3 SoCs (AM62x, AM64x) in device tree.
  Covers IOPAD macros, PIN_INPUT/PIN_OUTPUT, libgpiod userspace API, and
  MCU-domain GPIO access.
tags: [gpio, pinmux, device-tree, libgpiod, am62x, k3]
related_context:
  - context/device-tree-system.md
  - context/k3-architecture.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Drivers_GPIO.html
  - https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1407433/faq-am62x-how-to-test-gpio-on-am62xx-sk-evm
---

# Skill: GPIO and Pinmux Configuration

## Overview

Configuring a GPIO on AM62x requires two coordinated device tree changes:
1. **Pinmux** — set the PADCONFIG register to select GPIO function and input/output behavior
2. **GPIO reference** — reference the GPIO controller and line number in the consumer node

This skill covers both steps, explains common failure modes (wrong PIN_INPUT/PIN_OUTPUT,
wrong gpiochip number), and shows how to use the `libgpiod` userspace tools.

## Prerequisites

- Device tree source for your board (in `board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/`)
- Knowledge of which physical pin you want to use (from board schematic or TRM)
- SDK devkit toolchain sourced (for rebuilding DTS on host), OR
- Direct target access (for libgpiod testing)

## Step 1: Find the Pin's PADCONFIG Offset and GPIO Line Number

### Using SysConfig (recommended)
Open https://dev.ti.com/sysconfig, select AM625, click Pinmux.
Select your target peripheral or "GPIO" for the pin. SysConfig shows:
- The PADCONFIG register offset (hex)
- The GPIO bank and line number

### Using the TRM
AM62x TRM Table 5-1 lists every pin with its PADCONFIG offset, function table,
and default GPIO assignment.

### Using kernel DTS as reference
Search for a nearby peripheral in the existing board DTS to confirm the offsets:
```bash
grep -n "0x01e8" board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/k3-am62x-sk-common.dtsi
```

## Step 2: Add Pinmux Configuration in DTS

Edit your board DTS (or create an overlay — see skill 03):

```dts
/* In your board .dts or .dtso overlay */

&main_pmx0 {
    /* Input GPIO — e.g., a button on GPIO1_14 */
    my_button_pins: my-button-pins {
        pinctrl-single,pins = <
            /* offset=0x01e8, value=PIN_INPUT (RXACTIVE, pull disabled), mode=7 (GPIO) */
            AM625_IOPAD(0x01e8, PIN_INPUT, 7)
        >;
    };

    /* Output GPIO — e.g., an LED on GPIO0_22 */
    my_led_pins: my-led-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x0058, PIN_OUTPUT, 7)
        >;
    };
};
```

**Critical:** For any pin you read, use `PIN_INPUT` (enables RXACTIVE bit).
Using `PIN_OUTPUT` for an input pin causes reads to always return 0.

**PIN_INPUT with pull-up** (for open-drain buttons or I2C-style signals):
```dts
AM625_IOPAD(0x01e8, PIN_INPUT_PULLUP, 7)
```

## Step 3: Add GPIO Consumer Node in DTS

### For an LED (gpio-leds driver):
```dts
/ {
    leds {
        compatible = "gpio-leds";
        pinctrl-names = "default";
        pinctrl-0 = <&my_led_pins>;

        my-led {
            label = "board:green:user0";
            gpios = <&main_gpio0 22 GPIO_ACTIVE_HIGH>;
            default-state = "off";
        };
    };
};
```

### For a button (gpio-keys driver):
```dts
/ {
    gpio-keys {
        compatible = "gpio-keys";
        pinctrl-names = "default";
        pinctrl-0 = <&my_button_pins>;

        user-button {
            label = "User Button";
            gpios = <&main_gpio1 14 GPIO_ACTIVE_LOW>;
            linux,code = <KEY_PROG1>;
        };
    };
};
```

### For MCU domain GPIO (MCU_GPIO0):
```dts
/* Use mcu_pmx0 for pinmux, mcu_gpio0 for the controller */
&mcu_pmx0 {
    mcu_gpio_pins: mcu-gpio-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x0004, PIN_INPUT, 7)   /* MCU_GPIO0_2 */
        >;
    };
};

/ {
    mcu-gpio-consumer {
        pinctrl-names = "default";
        pinctrl-0 = <&mcu_gpio_pins>;
        my-gpio = <&mcu_gpio0 2 GPIO_ACTIVE_HIGH>;
    };
};
```

## Step 4: Rebuild the DTB

```bash
# On host — rebuild only the kernel DTS (fast)
source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux
cd board-support/ti-linux-kernel-*/
make ARCH=arm64 CROSS_COMPILE="${CROSS_COMPILE}" \
     k3-am625-sk.dtb     # replace with your board DTB name

# Copy to SD card boot partition
cp arch/arm64/boot/dts/ti/k3-am625-sk.dtb /media/$USER/boot/
```

Or with Yocto (rebuilds and deploys everything):
```bash
MACHINE=am62xx-evm bitbake linux-ti-staging -c compile -f
MACHINE=am62xx-evm bitbake linux-ti-staging -c deploy
```

## Step 5: Test GPIO with libgpiod (on target)

After booting with the new DTB:

```bash
# List all GPIO chips and their line counts
gpiodetect

# List all lines in a chip with their names and state
gpioinfo gpiochip0
gpioinfo gpiochip1

# Find a GPIO by the label you set in DT
gpioinfo | grep -A1 "my-led"

# Read an input GPIO (gpiochip N, line M)
gpioget gpiochip1 14

# Set an output GPIO high
gpioset gpiochip0 22=1

# Set output low
gpioset gpiochip0 22=0

# Monitor GPIO events (waits for edge)
gpiomon --num-events=5 gpiochip1 14
```

## Validation

```bash
# On target: verify GPIO chip exists and line is named correctly
gpioinfo | grep "my-led\|my-button"
# Should show the labels from your DTS

# Verify LED sysfs interface (if using gpio-leds)
ls /sys/class/leds/
echo 1 > /sys/class/leds/board\:green\:user0/brightness

# Verify button appears as input event
cat /proc/bus/input/devices | grep -A5 "User Button"
```

## Troubleshooting

### GPIO reads always return 0 (input not working)
- **Cause:** Pin configured as `PIN_OUTPUT` but used as input. `PIN_OUTPUT` disables
  the RXACTIVE (input buffer) bit.
- **Fix:** Change to `PIN_INPUT` or `PIN_INPUT_PULLUP` in the IOPAD line.

### "gpiochip number changed" after SDK upgrade
- **Cause:** Linux assigns gpiochip numbers dynamically based on probe order.
  Numbers change between kernel versions.
- **Fix:** Use `gpiodetect` to find current numbers. In userspace applications,
  open `/dev/gpiochipN` by searching for the chip's label, not by hardcoded number.
  ```bash
  gpiodetect   # shows label, e.g. "600000.gpio" = main_gpio0
  ```

### "pinctrl: pin ... already requested"
- **Cause:** Two nodes both request the same pin (conflict).
- **Fix:** Check if the pin is already used by another peripheral in the base `.dtsi`.
  Disable the conflicting node: add `status = "disabled";` to it.

### GPIO line shows "used" in gpioinfo but you didn't request it
- **Cause:** Another kernel driver (e.g., `gpio-hog`, `gpio-leds`) has claimed the line.
- **Fix:** Find which DT node claims it with:
  ```bash
  gpioinfo gpiochipN | grep "line M"
  ```

### MCU domain GPIO not accessible
- **Cause:** MCU GPIO requires `mcu_pmx0` pinmux (not `main_pmx0`) and `mcu_gpio0`
  controller (not `main_gpio0`).
- **Fix:** Verify you used the correct pinmux node prefix. MCU PADCONFIG offsets
  are also different — check TRM Section 5 (MCU_PADCONFIG table).

## Scripts

- `scripts/gpio-test.sh` — Interactive GPIO test using libgpiod
- `scripts/decode-iopad.py` — Decode raw PADCONFIG register value to human-readable fields

## Reference

- SDK GPIO driver doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Drivers_GPIO.html
- E2E GPIO FAQ: https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1407433/faq-am62x-how-to-test-gpio-on-am62xx-sk-evm
- E2E Pinmux FAQ: https://e2e.ti.com/support/processors-group/processors/f/processors-forum (search "pinmux AM62x FAQ")
- k3.h pinctrl macros: `board-support/ti-linux-kernel-*/include/dt-bindings/pinctrl/k3.h`
- SysConfig pinmux tool: https://dev.ti.com/sysconfig
