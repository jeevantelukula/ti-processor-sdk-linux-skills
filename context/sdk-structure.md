# TI Processor SDK Linux — Directory Structure

## Top-Level Layout

```
ti-processor-sdk-linux-am62xx-evm-<version>/
├── board-support/           Kernel, U-Boot, TF-A, OP-TEE, firmware source
├── linux-devkit/            Cross-compile toolchain (aarch64-oe-linux)
├── filesystem/              Prebuilt root filesystems (tar.xz)
├── example-applications/    PRU-ICSS examples, benchmarks
├── bin/                     Flashing utilities (snagboot, Ethernet flash)
├── licenses/                Open-source license files
└── sdk_version              SDK version string
```

## board-support/

```
board-support/
├── ti-linux-kernel-6.18.38+git-ti/     Kernel source
│   └── arch/arm64/boot/dts/ti/         All K3 device tree files
├── ti-u-boot-2025.01+git/              U-Boot source
├── trusted-firmware-a/                 TF-A (BL31)
├── optee-os/                           OP-TEE (BL32)
├── ti-linux-firmware/                  Binary firmware blobs
│   └── ti-sysfw/                       SYSFW (loaded by tiboot3)
├── k3-respart-tool/                    Resource partitioning tool
├── prebuilt-images/
│   └── am62xx-evm/                     Ready-to-use boot binaries
│       ├── tiboot3.bin                 R5 SPL (primary boot)
│       ├── tispl.bin                   TF-A + OP-TEE + A53 SPL
│       ├── u-boot.img                  Full U-Boot
│       ├── fitImage                    Kernel + DTBs (FIT)
│       ├── k3-am625-sk.dtb             SK EVM standalone DTB
│       ├── k3-am625-beagleplay.dtb
│       ├── k3-am625-phyboard-lyra-rdk.dtb
│       ├── k3-am625-verdin-wifi-dev.dtb
│       └── *.dtbo                      Precompiled DT overlays
└── extra-drivers/                      Out-of-tree driver sources
```

## linux-devkit/

The cross-compile toolchain for building against the SDK sysroot.

```
linux-devkit/
├── environment-setup-aarch64-oe-linux   Source this to set CC, LD, SYSROOT, etc.
└── sysroots/
    ├── aarch64-oe-linux/                Target sysroot (headers, libs)
    │   ├── usr/include/                 Kernel headers, library headers
    │   └── usr/lib/                     Target libraries
    └── x86_64-arago-linux/              Host tools (gcc-cross, etc.)
```

**To activate the toolchain:**
```bash
source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux
echo $CC    # aarch64-oe-linux-gcc
echo $SYSROOT
```

## filesystem/

Prebuilt root filesystem tarballs for SD card or NFS:
```
filesystem/
├── am62xx-evm/
│   ├── tisdk-default-image-am62xx-evm.tar.xz    Full image (Weston, demos)
│   └── tisdk-base-image-am62xx-evm.tar.xz       Minimal image
├── am62xx-evm-jailhouse/                         Jailhouse-enabled image
├── am62xx-lp-evm/
└── am62xx-lp-evm-jailhouse/
```

## example-applications/

```
example-applications/
├── pru-icss-6.5.0/              PRU firmware examples
│   ├── PRU_Hardware_UART/       UART via PRU
│   ├── PRU_RPMsg_Echo_Interrupt0/  RPMsg echo example
│   └── ...
└── arm-benchmarks-1.3/         CPU benchmark apps
```

## Key File Locations Cheat Sheet

| What You Need | Where to Find It |
|---|---|
| GPIO/pinmux DT source | `board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/` |
| Reference board DTS | `board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/k3-am625-sk.dts` |
| PADCONFIG offsets | AM62x TRM Section 5 OR use SysConfig at https://dev.ti.com/sysconfig |
| Prebuilt boot binaries | `board-support/prebuilt-images/am62xx-evm/` |
| Cross-compiler | `linux-devkit/environment-setup-aarch64-oe-linux` |
| Kernel headers | `linux-devkit/sysroots/aarch64-oe-linux/usr/include/` |
| Full root FS | `filesystem/am62xx-evm/tisdk-default-image-am62xx-evm.tar.xz` |
| PRU examples | `example-applications/pru-icss-*/` |
| k3-respart-tool | `board-support/k3-respart-tool/` |
| Snagboot (USB flash) | `bin/snagboot_flash/` |

## Yocto Source Tree (oe-layersetup)

Located alongside the SDK install at `../oe-layersetup/` or cloned separately:

```
oe-layersetup/
├── oe-layertool-setup.sh        Layer setup script
├── configs/processor-sdk/       Layer config files per SDK release
├── build/
│   ├── conf/
│   │   ├── local.conf           Build config (MACHINE, threads, etc.)
│   │   └── bblayers.conf        Active layer list
│   └── arago-tmp-default-glibc/deploy/  Build outputs
└── sources/
    ├── meta-ti/meta-ti-bsp/     Kernel, U-Boot, TF-A recipes
    ├── meta-tisdk/              SDK-specific recipes
    ├── meta-arago/              Filesystem layer
    └── oe-core/                 Yocto core + bitbake
```
