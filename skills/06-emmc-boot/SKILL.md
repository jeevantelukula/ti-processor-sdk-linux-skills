---
name: emmc-boot
version: "1.0.0"
description: >
  Flash the TI Processor SDK Linux bootloader and rootfs to eMMC and configure
  the board to boot from eMMC hardware boot0 partition. Covers boot mode switch
  settings, required patches, flashing commands, and environment save.
tags: [emmc, boot, flash, u-boot, mmc, am62x]
related_context:
  - context/boot-chain.md
  - context/sdk-structure.md
references:
  - https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1233869/faq-am625-how-to-boot-with-emmc-boot-mode-on-am62x
  - https://dev.ti.com/tirex/explore/node?node=A__AHRrRyaBVyh3lIzvQ8a6tQ__linux_academy_am62x__XaWts8R__LATEST
---

# Skill: eMMC Boot Mode

## Overview

Booting AM62x from eMMC requires:
1. Correct boot mode switch settings
2. Bootloader binaries flashed to eMMC `boot0` hardware partition
3. Root filesystem flashed to eMMC UDA (user data area) partition
4. (SDK < 12.x) A U-Boot patch to detect eMMC boot mode correctly

SD card boot is used as the staging medium to run Linux and then flash eMMC.

## Prerequisites

- Working SD card boot (see skill 05 for SD card setup)
- SDK prebuilt images at `board-support/prebuilt-images/am62xx-evm/`
- Root filesystem at `filesystem/am62xx-evm/tisdk-default-image-am62xx-evm.tar.xz`
- USB-UART access to the board for U-Boot console
- SDK v12.x (includes the eMMC boot fixes already; older SDKs may need the patches below)

## eMMC Boot Mode Switch Settings

Set the boot mode switch to **eMMC** before attempting eMMC boot:

| Bit | B9 | B8 | B7 | B6 | B5 | B4 | B3 |
|---|---|---|---|---|---|---|---|
| Value | 1 | 0 | 0 | 1 | 0 | 0 | 0 |

Reference: AM62x TRM Section 5.3 Boot Mode Pins.

For SD card boot (staging): configure SD boot mode per TRM, boot, flash, then switch.

## Step 1: Boot from SD Card (staging)

Use SD card boot to get a running Linux environment on the board:

```bash
# On host: flash SD card with prebuilt SD image
sudo dd if=filesystem/am62xx-evm/tisdk-default-image-am62xx-evm.rootfs.wic \
        of=/dev/sdX bs=4M status=progress
sync
```

Boot the board from SD card. Log in as root.

## Step 2: Copy Boot Binaries and Rootfs to Board

```bash
# From host — copy over SCP or USB storage
scp board-support/prebuilt-images/am62xx-evm/tiboot3.bin  root@<board-ip>:/tmp/
scp board-support/prebuilt-images/am62xx-evm/tispl.bin    root@<board-ip>:/tmp/
scp board-support/prebuilt-images/am62xx-evm/u-boot.img   root@<board-ip>:/tmp/
scp filesystem/am62xx-evm/tisdk-default-image-am62xx-evm.tar.xz root@<board-ip>:/tmp/
```

Or use a USB drive mounted on the target.

## Step 3: Flash Bootloader to eMMC boot0 Partition

On the target (running from SD card):

```bash
# Check eMMC device (usually mmcblk0 = eMMC, mmcblk1 = SD on AM62x SK)
ls /dev/mmcblk*
# mmcblk0 = eMMC, mmcblk0boot0 = eMMC hardware boot0 partition

# Enable write access to boot0 partition
echo 0 > /sys/block/mmcblk0boot0/force_ro

# Flash tiboot3.bin to boot0 at offset 0
dd if=/tmp/tiboot3.bin of=/dev/mmcblk0boot0 bs=512 seek=0
# Flash tispl.bin at 1 MB offset (0x800 sectors × 512 = 1 MB)
dd if=/tmp/tispl.bin of=/dev/mmcblk0boot0 bs=512 seek=2048
# Flash u-boot.img at 3 MB offset (0x1800 sectors × 512 = 3 MB)
dd if=/tmp/u-boot.img of=/dev/mmcblk0boot0 bs=512 seek=6144
sync

# Re-enable write protection on boot0
echo 1 > /sys/block/mmcblk0boot0/force_ro
```

**Boot0 Partition Layout:**

| Binary | Offset | Sector (512B) |
|---|---|---|
| tiboot3.bin | 0 KB | 0 |
| tispl.bin | 1 MB | 2048 |
| u-boot.img | 3 MB | 6144 |

## Step 4: Configure eMMC to Boot from boot0

```bash
# Set the EXTCSD register to boot from boot0 partition
# Using mmc-utils (install with: apt install mmc-utils)
mmc bootpart enable 1 1 /dev/mmcblk0

# Verify:
mmc extcsd read /dev/mmcblk0 | grep -A2 "BOOT_PARTITION_ENABLE"
# Expected: BOOT_PARTITION_ENABLE: 0x1 (boot0 selected)
```

## Step 5: Create eMMC Partition Table and Flash Rootfs

```bash
# Create partition table on eMMC UDA (user data area)
# Partition 1: FAT32 boot (256 MB), Partition 2: ext4 rootfs (remaining)
parted -s /dev/mmcblk0 mklabel msdos
parted -s /dev/mmcblk0 mkpart primary fat32 8MiB 264MiB
parted -s /dev/mmcblk0 mkpart primary ext4 264MiB 100%
parted -s /dev/mmcblk0 set 1 boot on

# Format partitions
mkfs.vfat -F 32 -n "boot" /dev/mmcblk0p1
mkfs.ext4 -L "rootfs" /dev/mmcblk0p2

# Mount and populate boot partition
mount /dev/mmcblk0p1 /mnt/boot
cp /tmp/tiboot3.bin   /mnt/boot/    # not needed here (in boot0) but harmless
cp /tmp/tispl.bin     /mnt/boot/
cp /tmp/u-boot.img    /mnt/boot/

# Copy DTBs and fitImage from SD card boot partition
cp /run/media/mmcblk1p1/fitImage  /mnt/boot/
cp /run/media/mmcblk1p1/*.dtb     /mnt/boot/
cp /run/media/mmcblk1p1/extlinux.conf /mnt/boot/
umount /mnt/boot

# Extract rootfs to eMMC rootfs partition
mount /dev/mmcblk0p2 /mnt/rootfs
tar -xJf /tmp/tisdk-default-image-am62xx-evm.tar.xz -C /mnt/rootfs
sync
umount /mnt/rootfs
```

## Step 6: Switch to eMMC Boot Mode and Reboot

1. Power off the board
2. Set boot mode switch to eMMC (see Step 0 above)
3. Power on

Expected U-Boot output:
```
U-Boot SPL 2025.01-ti (Jul 2026)
Trying to boot from MMC2
...
U-Boot 2025.01-ti (Jul 2026)
```
`MMC2` = eMMC. If it shows `MMC1`, it is booting from SD.

## Step 7: Verify and Save U-Boot Environment

```bash
# At U-Boot prompt (via UART), verify boot device:
printenv boot_targets
# Should include "mmc0" (eMMC) before "mmc1" (SD)

# Save environment to eMMC (creates env partition):
saveenv
# Should respond: "Saving Environment to MMC... Writing to MMC(0)... OK"
```

If `saveenv` fails or returns "No MMC device at slot 0", the eMMC boot mode
detection patch (below) is needed.

## Known Issue: eMMC Boot Mode Detection (SDK < 12.x)

On older SDK releases (< ~10.x), U-Boot SPL does not correctly detect eMMC
boot mode and falls back to SD card mode. Symptom: `saveenv` writes to SD instead
of eMMC, or board boots SD even with eMMC switch set.

The fix is a U-Boot patch to `arch/arm/mach-k3/am625_init.c`:

```c
/* In spl_mmc_boot_mode(), add eMMC detection: */
#define EMMC_BOOT 9

u32 spl_mmc_boot_mode(const u32 boot_device) {
    switch (boot_device) {
    case BOOT_DEVICE_MMC1:
        if (((devstat & MAIN_DEVSTAT_PRIMARY_BOOTMODE_MASK) >>
             MAIN_DEVSTAT_PRIMARY_BOOTMODE_SHIFT) == EMMC_BOOT)
            return MMCSD_MODE_EMMCBOOT;    /* ← add this */
        return MMCSD_MODE_FS;
    ...
    }
}
```

**SDK 12.x includes this fix** — no patch needed for the current SDK.

## Known Issue: rootfs Flashing Failures (MMC Speed)

On some AM62x board revisions, flashing large rootfs to eMMC UDA fails with
I/O errors due to MMC HS200/DDR52 instability. Fix: reduce MMC speed in DTB.

If you see `mmc0: error -110 whilst initialising MMC card` during flashing:

Apply this DTB patch to `arch/arm64/boot/dts/ti/k3-am62-main.dtsi`:
```dts
/* In sdhci0 node, remove high-speed properties: */
&sdhci0 {
    /* Remove or comment out these lines: */
    /* ti,otap-del-sel-mmc-hs  = <0x0>; */
    /* ti,otap-del-sel-ddr52   = <0x5>; */
    /* ti,otap-del-sel-hs200   = <0x5>; */
    /delete-property/ mmc-ddr-1_8v;
    /delete-property/ mmc-hs200-1_8v;
};
```

**SDK 12.x** has resolved most eMMC stability issues — apply only if still seeing errors.

## Validation

```bash
# On target (booted from eMMC):
cat /proc/cmdline | grep mmcblk0
# Root device should be /dev/mmcblk0p2

dmesg | grep mmc0
# Should show: "new high speed MMC card"

# Verify boot partition contents:
mount /dev/mmcblk0p1 /mnt && ls /mnt && umount /mnt
```

## Scripts

- `scripts/flash-emmc.sh` — Automated eMMC flash script (runs on target from SD)

## Reference

- E2E eMMC FAQ: https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1233869/faq-am625-how-to-boot-with-emmc-boot-mode-on-am62x
- AM62x Academy eMMC: https://dev.ti.com/tirex/explore/node?node=A__AHRrRyaBVyh3lIzvQ8a6tQ__linux_academy_am62x__XaWts8R__LATEST
- SDK U-Boot doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_U-Boot.html
