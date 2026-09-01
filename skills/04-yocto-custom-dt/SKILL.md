---
name: yocto-custom-dt
version: "1.0.0"
description: >
  Add a custom device tree source file (.dts) to the Yocto build for TI
  Processor SDK Linux. Covers the bbappend pattern, KERNEL_DEVICETREE,
  U-Boot default_device_tree, and FIT image vs standalone DTB boot mode.
tags: [yocto, device-tree, bbappend, kernel, custom-board, am62x]
related_context:
  - context/yocto-workflow.md
  - context/device-tree-system.md
  - context/boot-chain.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html
  - https://dev.ti.com/tirex/explore/node?node=A__AWde9U3fyhQwPQrzBeP7QA__AM62-ACADEMY__uiYMDcq__LATEST
---

# Skill: Custom Device Tree in Yocto Build

## Overview

Adding a custom device tree to the SDK Yocto build requires changes in three places:
1. **The DTS file** — your custom board description
2. **Kernel bbappend** — tells Yocto to include your DTS and build the DTB
3. **U-Boot selection** — makes the board boot with your DTB (method depends on boot mode)

This skill walks through all three steps and explains when you need each.

## Prerequisites

- Yocto workspace set up (see skill 09 if not done yet)
- A reference DTS file to start from (e.g., `k3-am625-sk.dts`)
- Custom layer created (or use existing `meta-custom`)
- MACHINE set to `am62xx-evm` (or your custom machine)

## Step 1: Create Your Custom DTS File

Start by copying the closest reference board DTS:

```bash
cd board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/
cp k3-am625-sk.dts k3-am625-myboard.dts
```

Edit `k3-am625-myboard.dts` to match your hardware. At minimum, update:
```dts
/dts-v1/;

#include "k3-am625.dtsi"           /* SoC-level peripherals */
#include "k3-am62x-sk-common.dtsi" /* Common SK features, or replace entirely */

/ {
    model = "My Custom AM625 Board";
    compatible = "mycompany,am625-myboard", "ti,am625";

    /* Add/override peripherals here */
};

/* Enable only peripherals your board uses */
&main_uart0 {
    status = "okay";
};
```

See [context/device-tree-system.md](../../context/device-tree-system.md) for
GPIO, I2C, SPI, and pinmux node patterns.

## Step 2: Create a Custom Yocto Layer (if not done)

```bash
# From the oe-layersetup directory
source build/conf/setenv
bitbake-layers create-layer sources/meta-myboard
bitbake-layers add-layer sources/meta-myboard
```

Verify layer was added:
```bash
bitbake-layers show-layers | grep meta-myboard
```

## Step 3: Write the Kernel bbappend

Create the directory structure:
```bash
mkdir -p sources/meta-myboard/recipes-kernel/linux/files/
```

Copy your DTS into the layer's files directory:
```bash
cp board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/k3-am625-myboard.dts \
   sources/meta-myboard/recipes-kernel/linux/files/
```

Create the bbappend:
```bash
cat > sources/meta-myboard/recipes-kernel/linux/linux-ti-staging_%.bbappend << 'EOF'
# Tell bitbake to look in this recipe's files/ directory
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Add DTS file to source fetching
SRC_URI:append = " file://k3-am625-myboard.dts"

# Copy DTS into kernel source tree before build
do_configure:append() {
    cp ${WORKDIR}/k3-am625-myboard.dts \
       ${S}/arch/arm64/boot/dts/ti/
}

# Add the new DTB to the list of DTBs to build
KERNEL_DEVICETREE:append:am62xx-evm = " \
    ti/k3-am625-myboard.dtb \
"
EOF
```

**Note:** The `ti/` prefix in `KERNEL_DEVICETREE` is the path relative to
`arch/arm64/boot/dts/`. The leading `ti/` is required.

## Step 4: Build the DTB

```bash
cd oe-layersetup
source build/conf/setenv
MACHINE=am62xx-evm bitbake linux-ti-staging
```

On success, the DTB appears at:
```
build/arago-tmp-default-glibc/deploy/images/am62xx-evm/k3-am625-myboard.dtb
```

Also in the Yocto deploy directory (symlinked):
```
build/arago-tmp-default-glibc/deploy/images/am62xx-evm/
```

## Step 5: Select the DTB at Boot

### Method A: FIT Image Boot (default SDK behavior)

Edit `extlinux.conf` on the SD card boot partition (or generate it in Yocto):

```
LABEL linux
    KERNEL /boot/fitImage
    APPEND root=/dev/mmcblk1p2 rw rootwait earlycon
    FDT /boot/k3-am625-myboard.dtb
```

Or for FIT image with embedded DTBs, add the DTB name to the FIT config.
The default SDK `fitImage` contains multiple DTBs — you can add yours
by also adding to `KERNEL_DEVICETREE` in the bbappend above.

### Method B: U-Boot environment variable (standalone DTB boot)

On the target at U-Boot prompt or from Linux:
```bash
# From U-Boot prompt:
setenv fdtfile k3-am625-myboard.dtb
setenv boot_fit 0
saveenv

# From Linux (writes to eMMC/SD U-Boot env partition):
fw_setenv fdtfile k3-am625-myboard.dtb
fw_setenv boot_fit 0
```

### Method C: Set default in U-Boot Kconfig (for production)

Add a U-Boot bbappend to set the compile-time default:
```bash
mkdir -p sources/meta-myboard/recipes-bsp/u-boot/
cat > sources/meta-myboard/recipes-bsp/u-boot/u-boot-ti-staging_%.bbappend << 'EOF'
do_configure:append() {
    # Set default DTB file name (without path or .dtb extension)
    sed -i 's/CONFIG_DEFAULT_FDT_FILE=.*/CONFIG_DEFAULT_FDT_FILE="k3-am625-myboard.dtb"/' \
        ${B}/.config || true
}
EOF
```

## Verification

```bash
# On target after booting with new DTB:
cat /proc/device-tree/model
# Should print: "My Custom AM625 Board"

cat /proc/device-tree/compatible
# Should show: "mycompany,am625-myboard\0ti,am625"

# Check which DTB was loaded by U-Boot:
dmesg | grep "Machine model:"
```

## Troubleshooting

### DTB not generated after build (missing from deploy dir)
- **Cause:** `KERNEL_DEVICETREE` path is wrong (missing `ti/` prefix, wrong filename).
- **Fix:** Run `MACHINE=am62xx-evm bitbake-getvar -r linux-ti-staging KERNEL_DEVICETREE --value`
  to see the full list. Verify your entry is present.

### DTS file not found during compile
- **Cause:** `do_configure:append` didn't copy the file, or `FILESEXTRAPATHS` is wrong.
- **Fix:** Check `FILESEXTRAPATHS` ends with `:` (colon). Verify `files/` directory exists
  at the same level as the bbappend file. Run `bitbake linux-ti-staging -c configure -f`
  and check for file not found errors.

### Board still boots with old DTB after rebuild
- **Cause:** Yocto sstate cache returns old result. Or SD card still has old DTB.
- **Fix:** `bitbake linux-ti-staging -c cleansstate && bitbake linux-ti-staging`
  Then copy the new `.dtb` to the SD boot partition manually.

### "include file not found" compile error in DTS
- **Cause:** Your DTS includes a `.dtsi` that depends on another. The Yocto build
  uses `-I` flags for the DT include search path. Verify all included files exist
  in the kernel source tree.
- **Fix:** Use only files present in the kernel source. If adding new `.dtsi` files,
  add them to `SRC_URI` and copy them in `do_configure:append` too.

### FIT image boot still uses old DTB despite setting `fdtfile`
- **Cause:** FIT image boot mode ignores `fdtfile`. It uses the FIT config, not
  individual DTB files.
- **Fix:** Either add your DTB to the FIT image (via `KERNEL_DEVICETREE` bbappend
  and rebuilding `fitImage`) or disable FIT boot with `setenv boot_fit 0`.

## Scripts

- `scripts/gen-bbappend.sh` — Generate bbappend and directory structure for a new DTS

## Reference

- Yocto Build SDK: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html
- AM62x Academy Custom Board: https://dev.ti.com/tirex/explore/node?node=A__AWde9U3fyhQwPQrzBeP7QA__AM62-ACADEMY__uiYMDcq__LATEST
- Yocto custom layer guide: https://docs.yoctoproject.org/dev/dev-manual/layers.html
