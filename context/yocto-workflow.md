# Yocto / OpenEmbedded Workflow for TI Processor SDK

## Layer Structure

```
oe-layersetup/sources/
├── meta-ti/
│   └── meta-ti-bsp/          Official TI BSP layer (kernel, U-Boot, TF-A, OP-TEE)
├── meta-tisdk/
│   ├── meta-ti-foundational/  SDK recipes (ti-linux-fw, prueth-fw, k3-respart-tool)
│   ├── meta-ti-extras/        Jailhouse, extra components
│   └── meta-ti-ml/            Edge AI / ML stack
├── meta-arago/                TI's filesystem layer (based on Yocto Poky)
├── oe-core/                   Yocto core (bitbake included)
└── meta-openembedded/         Community OE layers (meta-oe, meta-networking, etc.)
```

**Never edit files in upstream layers** (`meta-ti`, `meta-tisdk`, `meta-arago`).
All customization goes in a custom layer (e.g., `meta-custom`) via `.bbappend` files.

## Key Concepts

### Recipes (`.bb`)
A recipe defines how to build one package. Located at:
```
meta-ti-bsp/recipes-kernel/linux/linux-ti-staging_6.18.bb
meta-ti-bsp/recipes-bsp/u-boot/u-boot-ti-staging_2025.01.bb
```

### Append Files (`.bbappend`)
Extend an existing recipe without modifying it:
```
meta-custom/recipes-kernel/linux/linux-ti-staging_%.bbappend
```
The `%` wildcard matches any version, making appends version-agnostic.

### Machine Configuration
`MACHINE` selects the target hardware. Available MACHINEs:
- `am62xx-evm` — AM62x Starter Kit (GP, HS-FS, HS-SE)
- `am62xx-lp-evm` — AM62x LP Starter Kit
- `beagleplay-ti` — BeaglePlay SBC
- Custom machines go in `meta-custom/conf/machine/<machine>.conf`

### Build Configuration (`conf/local.conf`)
Located at `oe-layersetup/build/conf/local.conf`. Key variables:
```
MACHINE = "am62xx-evm"
BB_NUMBER_THREADS = "8"      # parallel tasks (cap if system unstable)
PARALLEL_MAKE = "-j8"        # parallel make jobs
DL_DIR = "/path/to/downloads"  # shared download cache
SSTATE_DIR = "/path/to/sstate"  # shared state cache
```

## Common Build Targets

```bash
# Full SDK image (~750 GB with Chromium)
MACHINE=am62xx-evm bitbake tisdk-default-image

# Base image (minimal, faster build)
MACHINE=am62xx-evm bitbake tisdk-base-image

# Linux kernel only (fast, <1 hour)
MACHINE=am62xx-evm bitbake linux-ti-staging

# U-Boot (all three boot stages)
MACHINE=am62xx-evm bitbake u-boot-ti-staging

# Cross-compile devkit / SDK installer
MACHINE=am62xx-evm bitbake meta-toolchain-arago-tisdk

# Jailhouse image
MACHINE=am62xx-evm bitbake tisdk-jailhouse-image
```

## Adding a Custom DTS File (Standard Pattern)

### Step 1: Create custom layer

```bash
# From yocto workspace root
bitbake-layers create-layer sources/meta-custom
bitbake-layers add-layer sources/meta-custom
```

### Step 2: Create directory structure

```
meta-custom/
├── conf/
│   └── layer.conf
└── recipes-kernel/
    └── linux/
        ├── linux-ti-staging_%.bbappend
        └── files/
            └── k3-am625-custom-board.dts
```

### Step 3: Write the bbappend

```bitbake
# meta-custom/recipes-kernel/linux/linux-ti-staging_%.bbappend

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://k3-am625-custom-board.dts"

do_configure:append() {
    cp ${WORKDIR}/k3-am625-custom-board.dts \
       ${S}/arch/arm64/boot/dts/ti/
}

KERNEL_DEVICETREE:append:am62xx-evm = " \
    ti/k3-am625-custom-board.dtb \
"
```

### Step 4: U-Boot bbappend (to set default DTB for standalone boot)

```bitbake
# meta-custom/recipes-bsp/u-boot/u-boot-ti-staging_%.bbappend

# Only needed if NOT using FIT image boot
# For FIT boot, edit extlinux.conf instead
do_configure:append() {
    echo "CONFIG_DEFAULT_DEVICE_TREE=\"k3-am625-custom-board\"" \
        >> ${B}/am62x_evm_a53_defconfig
}
```

### Step 5: Build

```bash
MACHINE=am62xx-evm bitbake linux-ti-staging
```

Output: `build/arago-tmp-default-glibc/deploy/images/am62xx-evm/k3-am625-custom-board.dtb`

## Forced Recompile

```bash
# Clean and rebuild one recipe
MACHINE=am62xx-evm bitbake linux-ti-staging -c cleansstate && \
MACHINE=am62xx-evm bitbake linux-ti-staging

# Rebuild only compile step (after editing source)
MACHINE=am62xx-evm bitbake linux-ti-staging --force -c compile
MACHINE=am62xx-evm bitbake linux-ti-staging -c deploy
```

## Useful Commands

```bash
# Find recipe workdir
MACHINE=am62xx-evm bitbake-getvar -r linux-ti-staging WORKDIR --value

# Find recipe source dir
MACHINE=am62xx-evm bitbake-getvar -r linux-ti-staging S --value

# List all layers
bitbake-layers show-layers

# Find which recipe provides a package
bitbake-layers show-recipes | grep linux-ti

# Show recipe variable
MACHINE=am62xx-evm bitbake-getvar -r linux-ti-staging KERNEL_DEVICETREE --value
```

## FIT Image vs Standalone DTB Boot

| | FIT Image (`fitImage`) | Standalone |
|---|---|---|
| Contains | kernel + multiple DTBs in one file | separate Image + DTB |
| U-Boot config | `CONFIG_SPL_FIT=y`, `CONFIG_FIT=y` | `CONFIG_LEGACY_IMAGE_FORMAT=y` |
| DTB selection | `extlinux.conf` `fdt /` field | `fdtfile` env var |
| Add custom DTB | Add to `KERNEL_DEVICETREE`, listed in fitImage config | Same + set `fdtfile` |

Default SDK uses FIT image. Most customers stay with FIT.

## Reference

- Yocto Build Guide: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html
- Layer Configuration: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Release_Specific_Yocto_layer_Configuration.html
- Yocto Project docs: https://docs.yoctoproject.org/
