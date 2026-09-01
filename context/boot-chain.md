# K3 Boot Chain

## Overview

K3 SoC boot is a 5-stage pipeline. Each stage authenticates and loads the next.
Understanding this chain is essential for boot failures, custom board bringup,
and eMMC/OSPI flash programming.

## Stage Map

```
ROM Bootloader (in chip)
        │
        ▼
tiboot3.bin  ── R5F SPL (executes in OCMC RAM)
   Contains: R5F U-Boot SPL + SYSFW (System Firmware) + Device Management FW
   Built from: board-support/ti-linux-firmware/ + board-support/u-boot/
   Loads from: SD boot0 | eMMC boot0 | OSPI | UART (DFU)
        │
        ▼
tispl.bin  ── A53 SPL (executes after DRAM init)
   Contains: TF-A (bl31.bin) + OP-TEE (bl32.bin) + A53 U-Boot SPL
   Built from: board-support/trusted-firmware-a/ + board-support/optee-os/ + u-boot/
        │
        ▼
u-boot.img  ── Full U-Boot (proper U-Boot with env, commands)
   Runs on A53, reads uEnv.txt or extlinux.conf or FIT image
        │
        ▼ (two options)
       /\
      /  \
fitImage   kernel + DTB (standalone)
  │               │
  └── kernel+DTB  └── zImage/Image + k3-am625-xxx.dtb
      bundled FIT
```

## Binary Locations in SDK

Prebuilt binaries for SK-AM62x EVM:
```
board-support/prebuilt-images/am62xx-evm/
├── tiboot3.bin               R5 SPL (HS-FS) — default for SK-AM62x
├── tiboot3-hs-fs.bin         Same, explicit HS-FS label
├── tiboot3-gp.bin            GP (non-secure) variant
├── tispl.bin                 TF-A + OP-TEE + A53 SPL
├── u-boot.img                Full U-Boot
├── fitImage                  Kernel + default DTB (FIT format)
├── fitImage-k3-am625-sk.dtb  Standalone DTB (for non-FIT boot)
├── k3-am625-sk.dtb           Standalone DTB
├── k3-am625-beagleplay.dtb   BeaglePlay DTB
├── k3-am625-phyboard-lyra-rdk.dtb
└── *.dtbo                    Device tree overlay blobs
```

## SD Card Layout

Partition 1 (FAT, `/boot`):
```
tiboot3.bin   tispl.bin   u-boot.img   uEnv.txt (or extlinux.conf)
fitImage      *.dtb       *.dtbo
```

Partition 2 (ext4, `/`):
```
Linux root filesystem
```

## U-Boot Boot Modes

### FIT Image Boot (default, recommended)
`fitImage` bundles kernel + multiple DTBs. U-Boot selects DTB based on board
detection or `name_fdt` in extlinux.conf.

### Standalone DTB Boot
Separate `zImage`/`Image` + `k3-am625-xxx.dtb`. U-Boot uses `default_device_tree`
env variable or `fdtfile` to select the DTB.

To switch to standalone DTB in U-Boot:
```
setenv boot_fit 0
setenv fdtfile k3-am625-sk.dtb
saveenv
```

## HS-FS vs HS-SE vs GP

| Mode | Description | tiboot3 |
|---|---|---|
| GP | General Purpose — no secure boot | tiboot3-gp.bin |
| HS-FS | High Security - Field Securable (dev keys) | tiboot3-hs-fs.bin (default SK) |
| HS-SE | High Security - Security Enforced (OTP key) | Customer-signed tiboot3 |

SK-AM62x EVMs ship as HS-FS. Production boards may be HS-SE.

## Common Boot Failures

### Stuck at "SYSFW ABI mismatch" / no output after tiboot3
- `tiboot3.bin` and `tispl.bin` versions must match. Mismatched SDK versions
  cause silent hang. Use prebuilt set from same SDK release.

### "Trying to boot from MMC1 ... " then hang
- Filesystem on SD is corrupt or partition table is wrong.
- U-Boot found `tiboot3.bin` but cannot load `tispl.bin` from FAT partition.
- Verify: FAT partition must be partition 1, type W95 FAT32 (LBA).

### Board shows correct board but boots wrong DTB
- In FIT mode: check `extlinux.conf` `fdt` field.
- In standalone mode: check U-Boot `fdtfile` env variable.

### DFU Boot (USB Peripheral Boot)
Used to flash a board without SD card. Boot mode switch: DFU (UART boot pins).
```bash
# From host PC
sudo dfu-util -l               # verify device detected
sudo dfu-util -R -a bootloader -D tiboot3.bin
sudo dfu-util -R -a tispl.bin  -D tispl.bin
sudo dfu-util -R -a u-boot.img -D u-boot.img
```

## Building Boot Artifacts

```bash
# All-in-one Yocto build (generates all boot artifacts):
MACHINE=am62xx-evm bitbake tisdk-default-image

# Individual components
MACHINE=am62xx-evm bitbake u-boot-ti-staging     # tiboot3.bin, tispl.bin, u-boot.img
MACHINE=am62xx-evm bitbake trusted-firmware-a    # bl31.bin (inside tispl.bin)
MACHINE=am62xx-evm bitbake optee-os              # bl32.bin (inside tispl.bin)
MACHINE=am62xx-evm bitbake linux-ti-staging      # fitImage, DTBs
```

## Reference

- SDK U-Boot doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_U-Boot.html
- AM62x Academy Boot modules: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
- TRM Boot chapter: https://www.ti.com/lit/pdf/spruiv7 (Section 5)
