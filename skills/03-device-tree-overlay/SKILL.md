---
name: device-tree-overlay
version: "1.0.0"
description: >
  Create and apply device tree overlays (.dtso source compiled to .dtbo binary)
  for runtime peripheral configuration on K3/AM62x. Covers overlay fragment
  syntax, dtc compilation, U-Boot loading, and the prebuilt overlay files in SDK.
tags: [device-tree, overlay, dtbo, dtso, peripheral, runtime, am62x, k3]
related_context:
  - context/device-tree-system.md
  - context/boot-chain.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Drivers_Device_Tree_Overlays.html
---

# Skill: Device Tree Overlays

## Overview

Device tree overlays let you modify the base DTB at runtime without recompiling
the full kernel DTB. They are `.dtso` source files compiled to `.dtbo` binaries.

The SDK ships prebuilt overlays for common expansion options (RPi header
peripherals, OLDI display, USB boot, etc.). You can also write custom overlays.

## Prebuilt Overlays in SDK

```bash
ls board-support/prebuilt-images/am62xx-evm/*.dtbo
```

Common prebuilt overlays:
```
k3-am625-sk-csi2-ov5640.dtbo           Camera (CSI2 OV5640)
k3-am625-sk-rpi-hdr-brkout.dtbo        RPi header breakout
k3-am625-sk-ext-sd.dtbo                External SD via RPi header
k3-am62-lp-sk-nand.dtbo                NAND storage
k3-am625-sk-oldi-rpi7inch-display.dtbo OLDI display (RPi 7" panel)
```

## Overlay File Structure

```dts
/dts-v1/;
/plugin/;   /* ← required for overlay files */

/* Include necessary bindings */
#include <dt-bindings/gpio/gpio.h>
#include <dt-bindings/interrupt-controller/arm-gic.h>
#include "k3-pinctrl.h"    /* provides AM625_IOPAD, PIN_INPUT, etc. */

/* Each fragment patches one node in the base DTB */
&main_pmx0 {
    /* Add new pinmux group */
    my_spi1_pins: my-spi1-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x0020, PIN_INPUT,  1)   /* SPI1_CLK */
            AM625_IOPAD(0x0024, PIN_OUTPUT, 1)   /* SPI1_D0 */
            AM625_IOPAD(0x0028, PIN_INPUT,  1)   /* SPI1_D1 */
            AM625_IOPAD(0x001c, PIN_OUTPUT, 1)   /* SPI1_CS0 */
        >;
    };
};

&main_spi1 {
    pinctrl-names = "default";
    pinctrl-0 = <&my_spi1_pins>;
    status = "okay";

    my_device@0 {
        compatible = "my,spi-device";
        reg = <0>;
        spi-max-frequency = <1000000>;
    };
};
```

## Compiling an Overlay

```bash
# Method A: Using dtc directly (requires kernel DT include path)
source linux-devkit/environment-setup-aarch64-oe-linux

DTS_DIR="board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti"
INCLUDE_DIR="board-support/ti-linux-kernel-*/include"

dtc -@ \                       # -@ enables symbols (required for overlays)
    -I dts \
    -O dtb \
    -o my-overlay.dtbo \
    -i "${DTS_DIR}" \          # DT include search path for k3-pinctrl.h etc.
    -i "${INCLUDE_DIR}" \
    my-overlay.dtso

# Method B: Build via kernel Makefile (handles include paths automatically)
cd board-support/ti-linux-kernel-*/
# Add your overlay to arch/arm64/boot/dts/ti/Makefile:
#   dtb-y += k3-am625-sk-my-overlay.dtbo
make ARCH=arm64 CROSS_COMPILE="${CROSS_COMPILE}" k3-am625-sk-my-overlay.dtbo
```

## Loading Overlays at Boot via U-Boot (extlinux.conf)

Edit the `extlinux.conf` on the SD/eMMC boot partition:

```
DEFAULT linux
TIMEOUT 1

LABEL linux
    KERNEL /fitImage
    FDTOVERLAYS /k3-am625-sk-my-overlay.dtbo
    APPEND console=ttyS2,115200n8 root=/dev/mmcblk1p2 rw rootwait earlycon
    FDT /k3-am625-sk.dtb
```

Multiple overlays:
```
    FDTOVERLAYS /k3-am625-sk-rpi-hdr-brkout.dtbo /k3-am625-sk-my-overlay.dtbo
```

U-Boot loads and applies overlays in order before passing the merged DTB to Linux.

## Loading Overlays at Runtime from Linux

Requires `CONFIG_OF_OVERLAY=y` in the kernel config (enabled in TI kernel):

```bash
# Create overlay entry in configfs
mkdir -p /sys/kernel/config/device-tree/overlays/my-overlay

# Load the overlay binary
cat my-overlay.dtbo > /sys/kernel/config/device-tree/overlays/my-overlay/dtbo

# Verify it applied (no error output = success)
# Check that the new peripheral appeared:
ls /dev/spidev*   # if SPI overlay
dmesg | tail -20  # check for driver probe messages

# Remove overlay
rmdir /sys/kernel/config/device-tree/overlays/my-overlay
```

## Overlay for GPIO Pin Configuration

Simple overlay to configure a GPIO as an LED:

```dts
/dts-v1/;
/plugin/;
#include <dt-bindings/gpio/gpio.h>
#include "k3-pinctrl.h"

&main_pmx0 {
    ext_led_pins: ext-led-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x0058, PIN_OUTPUT, 7)   /* GPIO0_22 */
        >;
    };
};

/ {
    fragment@0 {
        target-path = "/";
        __overlay__ {
            ext-leds {
                compatible = "gpio-leds";
                pinctrl-names = "default";
                pinctrl-0 = <&ext_led_pins>;
                expansion-led {
                    label = "expansion:green:ext";
                    gpios = <&main_gpio0 22 GPIO_ACTIVE_HIGH>;
                    default-state = "off";
                };
            };
        };
    };
};
```

## Adding Custom Overlay to Yocto Build

To include a custom overlay in the Yocto-built SD image:

```bitbake
# meta-custom/recipes-kernel/linux/linux-ti-staging_%.bbappend

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append = " file://k3-am625-sk-my-overlay.dtso"

do_configure:append() {
    cp ${WORKDIR}/k3-am625-sk-my-overlay.dtso \
       ${S}/arch/arm64/boot/dts/ti/
    # Add to Makefile so it gets built:
    echo "dtb-y += k3-am625-sk-my-overlay.dtbo" \
        >> ${S}/arch/arm64/boot/dts/ti/Makefile
}
```

## Troubleshooting

### "OF: overlay: WARNING: target node not found"
- **Cause:** The overlay references a node label (e.g., `&main_spi1`) that doesn't
  exist in the base DTB, or the label is spelled differently.
- **Fix:** Verify the label in the base DTB: `grep -r "main_spi1" arch/arm64/boot/dts/ti/`

### "OF: overlay: apply failed"
- **Cause:** Conflict with the base DTB (e.g., node already has a property the
  overlay tries to set differently).
- **Fix:** Use `/delete-property/` before reassigning, or `/delete-node/` to
  remove conflicting child nodes first.

### dtc error: "undefined symbol"
- **Cause:** The overlay uses a label (e.g., `&main_pmx0`) that dtc can't resolve
  because it's in the base DTS, not in the overlay file.
- **Fix:** Build with `-@` flag AND also build the base DTB with `-@`. When using
  the kernel Makefile, this is handled automatically.

### Overlay loaded but peripheral not found
- **Cause:** The driver for the device is a loadable module and isn't loaded.
- **Fix:** `modprobe <driver_module>` or add to `/etc/modules`.

## Scripts

- `scripts/apply-overlay.sh` — Build and load an overlay (host compile + target deploy)

## Reference

- SDK DT Overlays doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Drivers_Device_Tree_Overlays.html
- Prebuilt overlays: `board-support/prebuilt-images/am62xx-evm/*.dtbo`
- Kernel overlay docs: `Documentation/devicetree/overlay-notes.rst`
