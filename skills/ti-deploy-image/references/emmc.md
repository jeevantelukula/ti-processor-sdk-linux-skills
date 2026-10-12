# Flash and boot from eMMC

Evidence (example from AM62P SDK 12.02.00.01.01 and its docs device; yours will differ): docs pages `linux/How_to_Guides/Target/How_to_emmc_boot.html` (eMMC boot from
boot0/boot1), `linux/How_to_Guides/Target/How_to_mmcsd_boot_emmc_uda.html` (MMCSD boot from
the user data area), and `linux/Foundational_Components/U-Boot/UG-Memory-K3.html`, all read for
device `$TI_DOCS_DEVICE`, version `latest` (12.01 at the time; the installed SDK was 12.02, so the MCP
lagged). Every sector offset below is an example value printed on that docs page. For your SoC
re-read the page (`ti_processor_sdk_docs_search(query="eMMC boot offsets tiboot3 tispl u-boot.img boot0",
device=$TI_DOCS_DEVICE, ...)`): offsets and sizes are per SoC. Live-board facts are from one AM62P board
on 2026-10-12, read only.

An SD card that boots Linux is the staging medium for both flows (docs).

## Pick a mode (docs, UG-Memory-K3)

| Mode | ROM boots from | Rootfs |
|---|---|---|
| eMMC boot | eMMC hardware partition boot0 or boot1 only (cannot boot SD in this mode) | eMMC user data area (UDA) |
| MMCSD boot, FS mode | SD card or eMMC UDA (raw or filesystem mode set by boot-mode pins) | eMMC UDA |

Boot-mode pin settings are board specific: TRM section "Initialization / Boot Mode Pins" and the
board user guide. The SDK pages say so; no switch table is reproduced here.

## Identify devices

U-Boot: `mmc list` prints the eMMC and SD indices. Linux: `ls /dev/mmcblk*`. A device with
`mmcblkNboot0`, `mmcblkNboot1`, `mmcblkNrpmb` is the eMMC. Example, live AM62P board: `mmcblk0` is the
eMMC (also `mmcblk0boot0/1`, `mmcblk0rpmb`, `mmcblk0p1`), `mmcblk1` is the SD card booted from.
This is an example from that one board; do not assume it on another.

## A. eMMC boot (boot0/boot1)

1. Put the boot binaries to flash in the SD card boot partition under `emmc/` (docs). The SD
   boot partition on the live board (SDK image) has no `emmc/` directory; create it and copy `tiboot3.bin`,
   `tispl.bin`, `u-boot.img` there (they must match the silicon security mode; see
   `sdcard.md`).
2. Boot the board from SD. Flash boot0 either way (docs):
   - U-Boot (eMMC is `mmc dev 0` in the docs example):
     ```
     => mmc dev 0 1
     => fatload mmc 1 ${loadaddr} emmc/tiboot3.bin
     => mmc write ${loadaddr} 0x0 0x400
     => fatload mmc 1 ${loadaddr} emmc/tispl.bin
     => mmc write ${loadaddr} 0x400 0x1000
     => fatload mmc 1 ${loadaddr} emmc/u-boot.img
     => mmc write ${loadaddr} 0x1400 0x2000
     ```
     For boot1 use `mmc dev 0 2`.
   - Linux (docs; bs=512, seek in sectors):
     ```
     echo 0 > /sys/block/mmcblk0boot0/force_ro
     mkdir /mnt/sdboot && mount /dev/mmcblk1p1 /mnt/sdboot && cd /mnt/sdboot
     dd if=emmc/tiboot3.bin of=/dev/mmcblk0boot0 seek=0    bs=512
     dd if=emmc/tispl.bin   of=/dev/mmcblk0boot0 seek=1024 bs=512
     dd if=emmc/u-boot.img  of=/dev/mmcblk0boot0 seek=5120 bs=512
     ```
     The same with read-back verification and a dry-run mode:
     `scripts/flash-emmc-boot0.sh --emmc /dev/mmcblk0 --part boot0 --image emmc/tiboot3.bin:0 --image emmc/tispl.bin:1024 --image emmc/u-boot.img:5120 --dry-run`
     (the numbers are the docs' offsets for the example AM62P device; use your device's).
   Layout from the docs: tiboot3.bin at 0x0, tispl.bin at 0x400, u-boot.img at 0x1400 sectors,
   U-Boot environment at 0x3400 and a backup at 0x3500 (8 MB boot0).
3. Root filesystem to the UDA (docs): from Linux on the SD-booted system create a partition on
   the eMMC, format ext4, mount it, extract the rootfs tarball into it
   (`filesystem/<platform>/tisdk-*-image-*.rootfs.tar.xz` in the SDK). Kernel `Image` and DTBs
   must be in that rootfs `/boot` for U-Boot to find them.
4. In U-Boot configure the eMMC EXT_CSD so ROM boots from the hardware partition (docs):
   ```
   => mmc partconf 0 1 1 1      # boot0   (boot1: mmc partconf 0 1 2 1)
   => mmc bootbus 0 2 0 0
   => mmc rst-function 0 1      # WRITE-ONCE field (docs warning): only once per part, deliberately
   ```
5. `saveenv` is not used in the TI SDK (docs). To boot Linux from the eMMC UDA, either each boot:
   ```
   => setenv mmcdev 0
   => setenv bootpart 0
   => boot
   ```
   or persist it in a `uEnv.txt` on the boot media (see `network-boot.md`) or by changing
   `mmcdev`/`bootpart` in the board's U-Boot `.env` file and rebuilding (docs show the diff:
   `mmcdev=0`, `bootpart=0:1`).
6. Power off, set the boot-mode pins to eMMC boot per the TRM, power on.

Live check (example from an AM62P board; yours will differ, `mmc extcsd read /dev/mmcblk0`, `mmc` from mmc-utils at `/usr/bin/mmc`):
`PARTITION_CONFIG: 0x48` printed "Boot Partition 1 enabled", `RST_N_FUNCTION: 0x01`,
`BOOT_BUS_CONDITIONS: 0x02`, and `/sys/block/mmcblk0boot0/force_ro` was `1`.

## B. MMCSD boot from eMMC UDA (docs)

- Whole-image route: copy the `.wic` image to the target, boot from SD, then
  `xz -d -k <image>.wic.xz`, `umount /dev/mmcblk0*`, `dd if=<image>.wic of=/dev/mmcblk0`.
- Manual route: create a `boot` (vfat) and a `root` (ext4) partition on the eMMC, copy the boot
  binaries to boot and the rootfs to root. U-Boot: `mmc partconf 0 1 7 1`, `mmc bootbus 0 2 0 0`,
  `mmc rst-function 0 1` (write-once), then `setenv mmcdev 0; setenv bootpart 0:2; boot`.
- Set boot-mode pins to MMCSD boot from the eMMC port in FS mode (TRM).

## Verify

- U-Boot banner shows the boot device after power cycle (serial console).
- Linux: `cat /proc/cmdline` shows `root=` on the eMMC (`/dev/mmcblk0...` or its PARTUUID);
  `findmnt -n -o SOURCE /`; `mmc extcsd read /dev/mmcblk0 | grep -i partition_config`.

## Not carried over from the previous version of this skill (unverified in docs/SDK)

Boot0 offsets 2048/6144, `mmc bootpart enable`, `saveenv` to eMMC, MMC1/MMC2 banner strings, and
an MMC speed DTB patch were removed. The docs offsets for the example AM62P device are 1024 and 5120 sectors.
