---
name: boot-chain
version: "1.0.0"
description: >
  Understand, build, and debug the K3 5-stage boot chain for TI Processor SDK Linux.
  Covers tiboot3.bin, tispl.bin, u-boot.img, fitImage — building each, creating
  a bootable SD card, and diagnosing boot failures.
tags: [boot, u-boot, tiboot3, tispl, fitimage, sd-card, am62x, k3]
related_context:
  - context/boot-chain.md
  - context/sdk-structure.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_U-Boot.html
  - https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
---

# Skill: Boot Chain — Build and Debug

## Overview

K3 boot is a 5-stage chain. Each binary is built from a different source component.
This skill covers using the prebuilt binaries (fastest path) and building each
component from source when needed.

Read [context/boot-chain.md](../../context/boot-chain.md) first for architecture.

## Fastest Path: Use Prebuilt Binaries

For evaluation or initial board bring-up, use the prebuilt binaries from the SDK:

```bash
ls board-support/prebuilt-images/am62xx-evm/
# tiboot3.bin   tiboot3-hs-fs.bin   tiboot3-gp.bin
# tispl.bin     u-boot.img          fitImage
# k3-am625-sk.dtb   k3-am625-beagleplay.dtb   *.dtbo
```

Select the correct `tiboot3.bin` for your board security type:
- **SK-AM62x EVM** → `tiboot3-hs-fs.bin` (copy to `tiboot3.bin` on SD)
- **GP board** → `tiboot3-gp.bin`
- **HS-SE board** → requires customer-signed binary (contact TI)

## Create a Bootable SD Card

### Method A: Flash prebuilt WIC image (simplest)

```bash
# Flash complete SD card image (partitioned + filesystem + boot files)
sudo dd if=filesystem/am62xx-evm/tisdk-default-image-am62xx-evm.rootfs.wic \
        of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Replace `/dev/sdX` with your SD card device (verify with `lsblk`).

### Method B: Manual SD card setup (for custom configurations)

```bash
# Partition SD card
# Partition 1: FAT32, 256 MB, bootable
# Partition 2: ext4, remainder
sudo parted -s /dev/sdX mklabel msdos
sudo parted -s /dev/sdX mkpart primary fat32 8MiB 264MiB
sudo parted -s /dev/sdX mkpart primary ext4 264MiB 100%
sudo parted -s /dev/sdX set 1 boot on
sudo mkfs.vfat -F 32 -n "boot" /dev/sdX1
sudo mkfs.ext4 -L "rootfs" /dev/sdX2

# Populate boot partition
sudo mount /dev/sdX1 /mnt
sudo cp board-support/prebuilt-images/am62xx-evm/tiboot3.bin  /mnt/
sudo cp board-support/prebuilt-images/am62xx-evm/tispl.bin    /mnt/
sudo cp board-support/prebuilt-images/am62xx-evm/u-boot.img   /mnt/
sudo cp board-support/prebuilt-images/am62xx-evm/fitImage     /mnt/
sudo cp board-support/prebuilt-images/am62xx-evm/*.dtb        /mnt/
sudo cp board-support/prebuilt-images/am62xx-evm/*.dtbo       /mnt/

# Create extlinux.conf (or copy from SDK)
sudo mkdir -p /mnt/extlinux
sudo tee /mnt/extlinux/extlinux.conf << 'EOF'
DEFAULT linux
TIMEOUT 1
LABEL linux
    KERNEL /fitImage
    APPEND console=ttyS2,115200n8 root=/dev/mmcblk1p2 rw rootwait earlycon
    FDT /k3-am625-sk.dtb
EOF
sudo umount /mnt

# Populate rootfs partition
sudo mount /dev/sdX2 /mnt
sudo tar -xJf filesystem/am62xx-evm/tisdk-default-image-am62xx-evm.tar.xz -C /mnt
sync
sudo umount /mnt
```

## Building Boot Components from Source

All source builds use Yocto (see skill 09 for host setup):

```bash
source oe-layersetup/build/conf/setenv

# Build all boot artifacts in one command:
MACHINE=am62xx-evm bitbake u-boot-ti-staging

# Build individual components:
MACHINE=am62xx-evm bitbake trusted-firmware-a      # bl31.bin (A53 secure monitor)
MACHINE=am62xx-evm bitbake optee-os                 # bl32.bin (OP-TEE)
MACHINE=am62xx-evm bitbake linux-ti-staging         # fitImage + DTBs
```

Outputs in: `oe-layersetup/build/arago-tmp-default-glibc/deploy/images/am62xx-evm/`

### Building U-Boot Manually (without Yocto)

```bash
source linux-devkit/environment-setup-aarch64-oe-linux

cd board-support/ti-u-boot-*/

# Build A53 U-Boot (tispl.bin + u-boot.img)
make ARCH=arm CROSS_COMPILE="${CROSS_COMPILE}" am62x_evm_a53_defconfig
make ARCH=arm CROSS_COMPILE="${CROSS_COMPILE}" -j$(nproc)

# tiboot3.bin is built for R5 core — requires separate arm-none-eabi toolchain
# Use the Yocto build for tiboot3.bin, or use prebuilt
```

## Verifying Boot Artifacts

```bash
# Run this on host to verify all required files are present
source setup.sh
bash skills/05-boot-chain/scripts/verify-boot-artifacts.sh
```

Manual checks:

```bash
PREBUILT="board-support/prebuilt-images/am62xx-evm"

for f in tiboot3.bin tispl.bin u-boot.img fitImage; do
    if [[ -f "${PREBUILT}/${f}" ]]; then
        echo "OK: ${f} ($(du -h "${PREBUILT}/${f}" | cut -f1))"
    else
        echo "MISSING: ${f}"
    fi
done

# Verify fitImage is a valid FIT image
dumpimage -l "${PREBUILT}/fitImage" 2>/dev/null | head -20 || \
    echo "dumpimage not found — install u-boot-tools"
```

## U-Boot Environment

Common U-Boot env variables for boot configuration:

```bash
# Show all environment variables
printenv

# Show boot-specific variables
printenv boot_targets bootcmd fdtfile boot_fit

# Common variables:
# boot_targets  = "mmc1 mmc0 usb0 pxe dhcp"  (boot order)
# fdtfile       = "k3-am625-sk.dtb"  (used for standalone DTB boot)
# boot_fit      = "1"  (1=FIT boot, 0=standalone)

# To boot a different DTB:
setenv fdtfile k3-am625-myboard.dtb
saveenv
```

## Diagnosing Boot Failures

### No output on UART after power on
- Verify UART is connected to the **MAIN UART0** port (ttyUSB0/ttyUSB1)
- SK-AM62x: micro-USB UART port, 115200 8N1
- Check boot mode switch matches expected boot media (SD vs eMMC)
- LED D9 (green) = power OK. If off, check power supply.

### Stuck at "SYSFW ABI mismatch"
```
NOTICE: SYSFW ABI mismatch
```
- **Cause:** tiboot3.bin (contains SYSFW) and tispl.bin are from different SDK versions.
- **Fix:** Use all boot binaries from the **same SDK release**. Never mix binaries across releases.

### Stuck at "Trying to boot from MMC1" (SD boot) or "MMC2" (eMMC boot)
```
U-Boot SPL 2025.01-ti
Trying to boot from MMC1
[hangs]
```
- SD card FAT partition is corrupt or missing required files.
- Check partition 1 is FAT32 and contains `tiboot3.bin`, `tispl.bin`, `u-boot.img`.
- Re-flash SD card from scratch.

### Kernel panics at "VFS: Unable to mount root fs"
- Root filesystem missing or wrong rootfs device path in `APPEND` line.
- SD card: root device is typically `/dev/mmcblk1p2` (not `mmcblk0p2` which is eMMC).
- Check `printenv` and look at `bootargs` / `APPEND` for root= parameter.

### Wrong board boots after DT change
- U-Boot selected wrong DTB. Check `extlinux.conf` `FDT` field or `fdtfile` env.
- FIT image: add your DTB to `KERNEL_DEVICETREE` in Yocto (see skill 04).

## Scripts

- `scripts/verify-boot-artifacts.sh` — Verify all prebuilt boot artifacts are present

## Reference

- U-Boot doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_U-Boot.html
- AM62x Academy Boot: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
- snagboot (DFU flashing): https://github.com/bootlin/snagboot
