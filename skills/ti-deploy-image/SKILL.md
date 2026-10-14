---
name: ti-deploy-image
description: Put built or prebuilt SDK images on a TI board - create an SD card with the SDK bin/create-sdcard.sh or the Makefile install targets (DESTDIR), copy boot files, flash boot binaries and rootfs to eMMC, set up TFTP/NFS network boot with the SDK helper scripts, and persist U-Boot variables with uEnv.txt. Use after ti-build-source, or when the user asks to flash, write an SD card, boot from eMMC, or boot over the network.
---

# Deploy images to the board

Everything here was read from the SDK `bin/` scripts, `Makefile`/`makerules`, the docs MCP, and
a live board (read-only). Device values come from `scripts/ti-sdk-env.sh` (see `ti-sdk-setup`); boot
file names and security variants for your platform are in `$TI_KB` / `$TI_FACTS_JSON` (section
"Boot files"; run `ti-generate-kb` if unset).

## Docs (MCP)

Follow [references/mcp-usage.md](references/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`,
`os="linux"`, `version=$TI_SDK_VERSION_DOCS` (else `latest`) explicitly every call; the MCP may lag
the SDK, tell the user if so. SDK scripts win over a page; report both. Cite the page path you used.

- `ti_processor_sdk_docs_search(query="create SD card create-sdcard.sh", ...)`
  then read `linux/Overview/Processor_SDK_Linux_create_SD_card.html`
- `ti_processor_sdk_docs_search(query="how to flash eMMC and boot with eMMC boot", ...)`
  then read `linux/How_to_Guides/Target/How_to_emmc_boot.html`
- `ti_processor_sdk_docs_search(query="uEnv.txt U-Boot environment", ...)`
  then read `linux/Foundational_Components/U-Boot/BG-Environment-K3.html`
- `query="SDK build using Makefile install DESTDIR"`, then read `linux/Overview/Top_Level_Makefile.html`
- `query="eMMC boot offsets tiboot3 tispl u-boot.img boot0"` for your device's sector offsets (they differ per SoC)

## Prerequisites

- Paths here are relative to this skill's directory. Shell variables do not persist between commands: run
  `source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*` (the
  bundled scripts load it themselves).
- `ti-sdk-setup` done (`TI_SDK_ROOT`, `TI_PLATFORM`, ... exported).
- Images exist: either SDK prebuilt (`board-support/prebuilt-images/$TI_PLATFORM/`,
  `filesystem/$TI_PLATFORM/*.tar.xz`) or built and staged via `ti-build-source`
  (`board-support/built-images/`).
- Ask the user: boot medium (SD, eMMC, network), silicon security mode (decides which
  `tiboot3` file is used; variant names are listed in `$TI_KB`), board IP, **serial console** (port, baud, program; see profile `board.serial`), and the exact SD card device. Profile keys: `board.*` in `.claude/target-profile.yaml` (see `ti-sdk-quick-start`).
- Host `sudo`. Destructive steps (partitioning, `dd`) must be confirmed by the user against
  `lsblk` output. Do not pipe answers into interactive SDK scripts: give the user the command.

## Steps

1. Choose the path.

   | Goal | Section |
   |---|---|
   | Fresh bootable SD card | 2 |
   | Update kernel/DTBs/modules or boot files on an existing card | 3 |
   | Boot from eMMC | 4 |
   | Kernel over TFTP, rootfs over NFS | 5 |
   | Keep U-Boot variables across reboots | 6 |

2. New SD card, from the SDK. Full behavior of the script and the alternatives (WIC image with
   bmaptool/balenaEtcher): [references/sdcard.md](references/sdcard.md).
   ```bash
   sudo "$TI_SDK_ROOT"/bin/create-sdcard.sh        # interactive; optional single arg: platform
   ```
   It lists removable disks, offers 2 or 3 partitions, then option 1 (SDK prebuilt images) or
   2 (custom boot and rootfs paths). The script takes no other options.

3. Existing card, Makefile install targets (docs), from the SDK root, with partitions mounted:
   ```bash
   sudo make DESTDIR=<rootfs mount> linux_install     # Image, fitImage, DTBs, modules -> rootfs
   sudo make DESTDIR=<boot mount>   u-boot_install    # tispl.bin, u-boot.img, tiboot3*.bin -> boot
   ```
   Pass `DESTDIR` on the command line: the shipped `Rules.make` placeholder `__DESTDIR__` is
   not rewritten by `setup-targetfs-nfs.sh` in the SDK checked (details in `sdcard.md`).
   Then make sure `tiboot3.bin` on the boot partition is the variant for your security mode.

4. eMMC. Two documented modes (eMMC boot from boot0/boot1, or MMCSD boot from the user data
   area). Commands, offsets, EXT_CSD settings and the write-once warning:
   [references/emmc.md](references/emmc.md). Target-side helper with dry-run and read-back:
   ```bash
   scp scripts/flash-emmc-boot0.sh root@<board-ip>:/tmp/
   ssh root@<board-ip> /tmp/flash-emmc-boot0.sh --emmc <dev> --part boot0 \
       --image <file>:<sector> [--image <file>:<sector> ...] --dry-run
   ```
   Offsets are per SoC, from the docs page for `$TI_DOCS_DEVICE`; the script has none built in. Drop
   `--dry-run` only after the user confirms. `<dev>` is the eMMC from `ls /dev/mmcblk*` on the target
   (the one with `boot0`/`boot1`).

5. Network boot. TFTP root, NFS rootfs export and the U-Boot variables are set up by
   `bin/setup-tftp.sh`, `bin/setup-targetfs-nfs.sh`, `bin/setup-uboot-env.sh` (and
   `setup-minicom.sh`); `<SDK>/setup.sh` runs them in sequence. They edit `/etc/exports`,
   `/etc/xinetd.d/tftp` and restart services: show the user
   [references/network-boot.md](references/network-boot.md) first.

6. Persist U-Boot variables with `uEnv.txt` on the boot media (docs; `saveenv` is not used in
   current SDKs). Procedure and caveats in `network-boot.md`.

7. Boot the board: set the boot-mode pins for the medium (TRM "Boot Mode Pins" and the board
   guide; not reproduced here), power cycle, watch the serial console (115200 8N1 is what
   `setup-minicom.sh` writes).

## Verify

```bash
ssh root@<board-ip> 'uname -r; cat /proc/device-tree/model; cat /proc/cmdline; findmnt -n -o SOURCE /'
```
Expected: kernel release matches what you built or shipped, `root=` points at the intended
medium (SD, eMMC, or `/dev/nfs`). Example from the live AM62P board (yours will differ): the same
command returned the SD-card rootfs `/dev/mmcblk1p2` and `root=PARTUUID=...`. Checksums for copied files:
`sha256sum` the staged file and the file on the card.

## Troubleshooting (from SDK/docs only)

- `create-sdcard.sh` option 1 fails to find the SDK: the script matches the default SDK
  directory name (docs). Use option 2 with explicit paths.
- Card not listed or the wrong list: the root-drive masking is heuristic and docs warn it is
  off by one on LVM hosts; compare with `lsblk` before answering.
- `u-boot_install` / `linux_install` print "directory doesn't exist": `DESTDIR` unset or not a
  directory (checked in the makerules).
- Warm reset ignored on eMMC: EXT_CSD[162] unset; `mmc rst-function 0 1` in U-Boot, write-once
  (docs).
- SD card init errors in SPL (`mmc init failed with error: -110`): docs list device-tree
  workarounds (speed cap with `sdhci-caps-mask`, longer power-cycle delay, bus-width 1); read
  `UG-Memory-K3.html` section "workaround SD card issues" before changing anything.
- SYSFW / boot-binary mixing: no warning about mixing boot binaries across releases was found in
  the docs pages above, so none is stated here. Search `ti_processor_sdk_docs_search(query="boot
  binaries must match SDK release", ...)` before advising on it.
