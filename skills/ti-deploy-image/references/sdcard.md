# SD card creation

Evidence (example from AM62P SDK 12.02; yours will differ): `bin/create-sdcard.sh` (read in full), docs page
`linux/Overview/Processor_SDK_Linux_create_SD_card.html` (example AM62P docs device, `latest` = 12.01), docs page
`linux/Overview/Top_Level_Makefile.html`.

## Option A: write a WIC image (docs)

The release page carries `tisdk-default-image-<machine>-<version>.rootfs.wic.xz`. Docs give two
tools: balenaEtcher, or `bmaptool`:

```bash
unxz tisdk-default-image-<machine>-<version>.rootfs.wic.xz
bmaptool create -o <image>.rootfs.bmap <image>.rootfs.wic        # optional, speeds up the copy
sudo bmaptool copy --bmap <image>.rootfs.bmap <image>.rootfs.wic /dev/sdX
```
`/dev/sdX` is the SD card; unmount its partitions first (`lsblk`, `umount`). This erases the card.
The SDK tree used for this skill ships `filesystem/<platform>/*.rootfs.tar.xz` and no `.wic`
file, so Option A needs a separate download.

## Option B: `bin/create-sdcard.sh` (installed with the SDK)

Facts read from the script:
- Run as root: `sudo <SDK>/bin/create-sdcard.sh [platform]`. The ONLY command-line argument is the
  optional platform name; if absent it is read from `PLATFORM?=` in the SDK `Rules.make`. There
  are no other flags. Everything else is interactive prompts.
- It lists block devices named `sdX` or `mmcblkX`, skipping the drive holding `/`. Docs warn the
  skip logic is wrong with LVM root volumes: check the list against `lsblk` yourself.
- Cards larger than about 16 GB trigger an extra "continue? [y/n]" confirmation.
- Existing partitions are unmounted. If the card already has a usable layout it asks whether to
  re-partition. Re-partitioning zeroes the first 1 MiB (`dd`) and runs `fdisk`.
- Layouts it creates: 2 partitions = `boot` (FAT32, 128 MiB, bootable) + `root` (ext4, rest of
  card); 3 partitions = `boot` + `root` (2.4 GiB) + `START_HERE` (ext4, rest).
- Then asks `1) Install pre-built images from SDK` or `2) custom boot and root paths`.
  - Option 1 reads boot files from `board-support/prebuilt-images/<platform>/` and the rootfs
    from `filesystem/<platform>/` (a `tisdk*image*.tar.xz`; if several exist you pick by number).
    Boot files it copies when present in that directory: `tispl.bin`, all `tiboot3*` files,
    `u-boot.img`/`u-boot.bin`, `uEnv.txt`, `ti_logo*`, `sysfw*`. The SDK directory name is matched against a name baked into the script
    (docs: option 1 only works with the default SDK directory name; otherwise use option 2).
  - Option 2 prompts for a boot tarball/directory and a rootfs tarball/directory, and whether to
    reuse the kernel and DTBs found in the rootfs `/boot` or take them from another directory.
    Boot content REQUIRED by the prompt text: `MLO` or (`tiboot3` and `tispl`), plus `u-boot`.
- Ends with `sync` and unmount. Mount points are temporary directories in the cwd.

Run it with the card inserted and identified (`lsblk`); never against a disk you have not
confirmed. Because every step prompts, an agent should hand the command to the user to run in
their terminal, not pipe answers into it.

## Option C: manual copy with the Makefile install targets (docs)

After `make linux` and `make u-boot` (see `ti-build-source`), with the card's partitions mounted:

```bash
sudo DESTDIR=/media/$USER/rootfs make linux_install     # kernel Image, fitImage, DTBs, modules into rootfs /boot, /lib/modules
sudo DESTDIR=/media/$USER/boot   make u-boot_install    # tispl.bin, u-boot.img, tiboot3*.bin into the boot partition
```
Mount points are the docs' example (`/media/$USER/...`); use yours. `linux_install` and
`u-boot_install` stop with an error if `$DESTDIR` does not exist (checked in the makerules).
`u-boot_install` copies every `tiboot3*.bin` variant. ROM loads the file named `tiboot3.bin`,
so make sure `tiboot3.bin` on the card matches the silicon security mode. The docs example for
HS-FS devices is:
```bash
sudo cp board-support/built-images/tiboot3-<soc>-hs-fs-evm.bin /media/$USER/boot/tiboot3.bin
sudo cp board-support/built-images/u-boot.img board-support/built-images/tispl.bin /media/$USER/boot
```
(`<soc>` and variant names: `ls board-support/built-images/tiboot3*` or `$TI_KB` boot files; example
from the AM62P docs: `tiboot3-am62p*-hs-fs-evm.bin`.)

Why the kernel goes to the rootfs partition: docs (Kernel Users Guide) say U-Boot reads the
kernel and DTBs from the rootfs `/boot` when booting from MMC, not from the FAT boot partition.

## Rules.make DESTDIR placeholder

Shipped `Rules.make` has `DESTDIR?=__DESTDIR__`. `bin/setup-targetfs-nfs.sh` tries to rewrite it
with `sed "s=DESTDIR ?\=.*$=..."` (note the space before `?`). Tested (example) on a copy of the AM62P
12.02 `Rules.make`: the pattern does not match, nothing changes. Always pass `DESTDIR=` on the
`make` command line as above.
