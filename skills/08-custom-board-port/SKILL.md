---
name: custom-board-port
version: "1.0.0"
description: >
  Port TI Processor SDK Linux to a custom AM62x-based board. Covers creating a
  new board DTS from the SK reference, U-Boot board configuration, SysConfig
  pinmux export, enabling UART/I2C/SPI/GPIO peripherals, and Yocto MACHINE setup.
tags: [custom-board, porting, device-tree, u-boot, yocto, uart, i2c, spi, am62x]
related_context:
  - context/device-tree-system.md
  - context/boot-chain.md
  - context/yocto-workflow.md
  - context/k3-architecture.md
references:
  - https://dev.ti.com/tirex/explore/node?node=A__AWde9U3fyhQwPQrzBeP7QA__AM62-ACADEMY__uiYMDcq__LATEST
  - https://www.ti.com/lit/an/spradd1a/spradd1a.pdf
---

# Skill: Custom Board Porting

## Overview

Porting the SDK to a custom board requires device tree changes for hardware
differences. The SK-AM62x EVM DTS is the starting point — you remove what
your board doesn't have, add what it does have, and adjust pinmux for your
schematic.

This skill walks through the minimal viable port (UART console working) and
then extends to common peripherals.

## Prerequisites

- Board schematic (to identify which SoC pins connect to which board components)
- TI AM62x TRM (for PADCONFIG offsets) and/or SysConfig tool
- SDK installed with kernel source at `board-support/ti-linux-kernel-*/`
- Yocto workspace set up (see skill 09)

## Step 1: Create Board DTS from Reference

```bash
DTS_DIR="board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti"

# Copy closest reference DTS for your SoC variant:
# AM625 (4× A53):
cp ${DTS_DIR}/k3-am625-sk.dts ${DTS_DIR}/k3-am625-myboard.dts

# AM623 (2× A53) or AM620 (1× A53):
# cp ${DTS_DIR}/k3-am62x-sk-common.dtsi ... (use AM625 as base, adjust core count)
```

Edit the new DTS header:
```dts
/dts-v1/;

/* Include the SoC-level DTSI (DO NOT modify these) */
#include "k3-am625.dtsi"

/ {
    model = "MyCompany AM625 Custom Board Rev A";
    compatible = "mycompany,am625-myboard", "ti,am625";

    /* Board-level memory (same as SK for standard 2 GB config) */
    memory@80000000 {
        device_type = "memory";
        reg = <0x00000000 0x80000000 0x00000000 0x80000000>;   /* 2 GB */
    };

    /* Reserved memory for remote cores (keep same as SK unless changing M4F DDR) */
    reserved-memory {
        #address-cells = <2>;
        #size-cells = <2>;
        ranges;

        secure_ddr: optee@9e800000 {
            reg = <0x00 0x9e800000 0x00 0x01800000>;
            alignment = <0x1000>;
            no-map;
        };

        mcu_m4fss0_core0_dma_memory_region: m4f-dma-memory@9cb00000 {
            compatible = "shared-dma-pool";
            reg = <0x00 0x9cb00000 0x00 0x100000>;
            no-map;
        };

        mcu_m4fss0_core0_memory_region: m4f-memory@9cc00000 {
            compatible = "shared-dma-pool";
            reg = <0x00 0x9cc00000 0x00 0xe00000>;
            no-map;
        };

        rtos_ipc_memory_region: ipc-memories@9d000000 {
            reg = <0x00 0x9d000000 0x00 0x1c00000>;
            alignment = <0x1000>;
            no-map;
        };
    };
};
```

## Step 2: Configure UART Console

The console UART is the first peripheral you need working.

Use SysConfig (https://dev.ti.com/sysconfig) to find the PADCONFIG offsets for
your board's UART pins. For AM62x MAIN_UART0 (default console):

```dts
&main_pmx0 {
    /* Verify these offsets match YOUR board schematic */
    main_uart0_pins_default: main-uart0-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x01c8, PIN_INPUT,  0)   /* (D14) UART0_RXD */
            AM625_IOPAD(0x01cc, PIN_OUTPUT, 0)   /* (E14) UART0_TXD */
        >;
    };
};

&main_uart0 {
    pinctrl-names = "default";
    pinctrl-0 = <&main_uart0_pins_default>;
    status = "okay";
};
```

**Finding PADCONFIG offsets for your pins:**
1. Find the ball name from your schematic (e.g., "D14")
2. Look up ball D14 in AM62x TRM Package Table (Section 6)
3. The table maps ball → signal name → PADCONFIG offset
4. Or use SysConfig: Pin Mux → select UART0 → RXD/TXD → SysConfig shows the offset

## Step 3: Disable Unused SK Peripherals

The SK DTS enables many peripherals your custom board may not have. Disabling
them prevents probe errors and reduces boot time.

Common peripherals to review:
```dts
/* Disable if your board has no SD/MMC slot */
&sdhci1 {
    status = "disabled";
};

/* Disable if your board has no Ethernet */
&cpsw3g {
    status = "disabled";
};

/* Disable if your board has no DSI display */
&dss {
    status = "disabled";
};

/* Disable PWM expansion connector if not used */
&epwm0 { status = "disabled"; };
```

Keep only what your board implements. Unnecessary `status = "okay"` nodes cause
driver probe attempts that may log errors or slow boot.

## Step 4: Add Common Peripheral Nodes

### I2C (MAIN_I2C0, I2C1, I2C2, I2C3)

```dts
&main_pmx0 {
    main_i2c1_pins: main-i2c1-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x01e8, PIN_INPUT_PULLUP, 1)   /* I2C1_SCL */
            AM625_IOPAD(0x01ec, PIN_INPUT_PULLUP, 1)   /* I2C1_SDA */
        >;
    };
};

&main_i2c1 {
    pinctrl-names = "default";
    pinctrl-0 = <&main_i2c1_pins>;
    clock-frequency = <400000>;   /* 400 kHz fast mode; use 100000 for standard */
    status = "okay";

    /* Example: I2C device on address 0x48 */
    my_sensor: my-sensor@48 {
        compatible = "ti,tmp100";
        reg = <0x48>;
    };
};
```

### SPI (MAIN_SPI0, SPI1, SPI2)

```dts
&main_pmx0 {
    main_spi0_pins: main-spi0-pins {
        pinctrl-single,pins = <
            AM625_IOPAD(0x01bc, PIN_INPUT,  0)   /* SPI0_CLK */
            AM625_IOPAD(0x01b8, PIN_OUTPUT, 0)   /* SPI0_D0 (MOSI) */
            AM625_IOPAD(0x01c4, PIN_INPUT,  0)   /* SPI0_D1 (MISO) */
            AM625_IOPAD(0x01b4, PIN_OUTPUT, 0)   /* SPI0_CS0 */
        >;
    };
};

&main_spi0 {
    pinctrl-names = "default";
    pinctrl-0 = <&main_spi0_pins>;
    status = "okay";

    /* SPI device example: SPI NOR flash */
    flash@0 {
        compatible = "jedec,spi-nor";
        reg = <0>;
        spi-max-frequency = <50000000>;
    };
};
```

### GPIO (see skill 02 for details)

```dts
&main_pmx0 {
    board_gpios: board-gpios {
        pinctrl-single,pins = <
            AM625_IOPAD(0x0058, PIN_OUTPUT,     7)  /* USER_LED — GPIO0_22 */
            AM625_IOPAD(0x01e8, PIN_INPUT_PULLUP, 7)  /* USER_BTN — GPIO1_14 */
        >;
    };
};

/ {
    leds {
        compatible = "gpio-leds";
        pinctrl-names = "default";
        pinctrl-0 = <&board_gpios>;
        user-led {
            label = "board:green:user";
            gpios = <&main_gpio0 22 GPIO_ACTIVE_HIGH>;
        };
    };
};
```

## Step 5: OSPI/SD/eMMC Storage Configuration

If your board uses a different storage media than the SK:

### eMMC (SDHCI0):
```dts
&sdhci0 {
    pinctrl-names = "default";
    pinctrl-0 = <&emmc_pins_default>;   /* define in pinmux */
    ti,driver-strength-ohm = <50>;
    disable-wp;
    bus-width = <8>;
    non-removable;
    ti,clkbuf-sel = <0x7>;
    status = "okay";
};
```

### SD card (SDHCI1):
```dts
&sdhci1 {
    pinctrl-names = "default";
    pinctrl-0 = <&sd_pins_default>;
    ti,driver-strength-ohm = <50>;
    cd-gpios = <&main_gpio1 48 GPIO_ACTIVE_LOW>;  /* card detect pin */
    bus-width = <4>;
    status = "okay";
};
```

## Step 6: Create Yocto MACHINE for Custom Board

For a production workflow, create a custom MACHINE:

```bash
mkdir -p sources/meta-myboard/conf/machine/
cat > sources/meta-myboard/conf/machine/am625-myboard.conf << 'EOF'
#@TYPE: Machine
#@NAME: AM625 MyBoard
#@DESCRIPTION: MyCompany custom AM625 board

require conf/machine/am62xx-evm.conf

MACHINE_EXTRA_RRECOMMENDS += ""

# Set your board DTB as the default
KERNEL_DEVICETREE:am625-myboard = " \
    ti/k3-am625-myboard.dtb \
"
EOF
```

Build with your custom MACHINE:
```bash
MACHINE=am625-myboard bitbake tisdk-base-image
```

## Step 7: Incremental Bring-Up Verification

Verify each subsystem in order. Fix one before adding the next:

```bash
# 1. UART console working?
# → Can you type at the login prompt?

# 2. Correct board model identified?
cat /proc/device-tree/model
# → "MyCompany AM625 Custom Board Rev A"

# 3. I2C bus accessible?
i2cdetect -y 1   # scan I2C bus 1 (main_i2c1)
# → Shows device addresses

# 4. SPI accessible?
ls /dev/spidev*

# 5. GPIO accessible?
gpiodetect && gpioinfo

# 6. Ethernet (if applicable)?
ip link show
# → eth0 or eth1 up

# 7. Storage?
lsblk
# → mmcblk0 (eMMC or SD) detected
```

## Common Porting Mistakes

### Wrong pinmux node prefix
MCU domain peripherals (MCU_UART0, MCU_I2C0, MCU_GPIO0) use `mcu_pmx0`.
Main domain peripherals use `main_pmx0`. Mixing them causes "pinctrl: pin not found".

### Wrong PADCONFIG offset
Always verify from schematic → TRM Package Table → PADCONFIG offset.
SysConfig is the most reliable way to get correct offsets.

### Using UART0 when it's reserved for DM/TIFS
WKUP_UART0 is reserved for system firmware debug output — do not use it for
your console. Use MAIN_UART0 or MAIN_UART1.

### Kernel DTS doesn't match U-Boot DTS
U-Boot has its own DTS tree. For a custom board, update U-Boot DTS too
(especially for early console, eMMC, and boot media config).

## Reference

- TI Application Note — Minimal Platform Development AM62x: https://www.ti.com/lit/an/spradd1a/spradd1a.pdf
- AM62x Academy Custom Board: https://dev.ti.com/tirex/explore/node?node=A__AWde9U3fyhQwPQrzBeP7QA__AM62-ACADEMY__uiYMDcq__LATEST
- SysConfig: https://dev.ti.com/sysconfig
- AM62x TRM: https://www.ti.com/lit/pdf/spruiv7
