---
name: ti-build-source
description: Build the Linux kernel, device tree blobs, and U-Boot boot binaries (R5/A-core or single-stage, depending on the SoC) from the SDK sources using the SDK top-level Makefile and Rules.make, locate the outputs, rebuild incrementally, and change kernel config. Use when the user wants to compile the kernel, DTBs or bootloaders from the SDK tree. For the Yocto/bitbake path use ti-yocto-build instead.
---

# Build kernel, DTBs and U-Boot from the SDK

Device values come from `Rules.make` through `lib/ti-sdk-env.sh` (see `ti-sdk-setup`); the list of
targets and boot files for your device is in `$TI_KB` / `$TI_FACTS_JSON` (run `ti-generate-kb` if
unset). The makerules differ per SoC, so read them before choosing targets (step 1).

## Docs (MCP)

Follow [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`,
`os="linux"`, `version=$TI_SDK_VERSION_DOCS` (or `latest` if `list_versions` lacks it; say that
the page may lag the SDK) on every call. The SDK makerules win over a page; report both.

- `ti_processor_sdk_docs_search(query="SDK build using Makefile top level targets", ...)`
  then read `linux/Overview/Top_Level_Makefile.html`
- `query="kernel users guide configuring compiling kernel"`, then read
  `linux/Foundational_Components_Kernel_Users_Guide.html`
- `query="build U-Boot R5 A53 defconfig binman"`, then read
  `linux/Foundational_Components/U-Boot/BG-Build-K3.html` (K3 devices only)

## Prerequisites

- `ti-sdk-setup` done: `source lib/ti-sdk-env.sh` works and `check-sdk.sh` (in `ti-sdk-setup`) passes.
- Run `make` from the SDK root in a clean shell: do NOT source `linux-devkit/environment-setup`
  (docs: the kernel target breaks when it is sourced).
- `MAKE_JOBS` is set in `Rules.make`; override with `make MAKE_JOBS=<n> <target>`.

## Steps

1. Discover what this SDK builds (read-only), then preview a target (no side effects):
   ```bash
   source <skills-root>/lib/ti-sdk-env.sh && cd "$TI_SDK_ROOT"
   grep -hoE '^[a-z0-9_-]+:' makerules/Makefile_linux makerules/Makefile_linux-dtbs makerules/Makefile_u-boot | tr -d : | sort -u
   grep -n 'defconfig\|zImage\|Image' makerules/Makefile_linux      # kernel config and image targets
   make -n u-boot | head -20
   ```
   `make: *** No rule to make target` means this SDK has no such target. Observed differences:
   one SDK had `u-boot-r5` and `u-boot-a53`; its makerule also branches to `atf u-boot-a53` with no
   R5 stage for one SoC; an AM335x SDK has a single `u-boot` target and builds `zImage`;
   an ADAS SDK builds U-Boot into different directories. Targets in later steps are the K3 pattern
   (example from AM62P SDK 12.02.00.01.01; yours will differ).
2. Build. Targets are `<name>`, `<name>_stage`, `<name>_install`, `<name>_clean` (docs):
   ```bash
   make u-boot-r5      # R5 SPL tiboot3*, UBOOT_MACHINE_R5 + CROSS_COMPILE_ARMV7 (if the target exists)
   make u-boot-a53     # tispl.bin + u-boot.img, UBOOT_MACHINE, BL31/TEE/TI_DM from Rules.make
   make u-boot         # the stage(s) your makerule lists
   make linux-dtbs     # DTBs selected by KERNEL_DEVICETREE_PREFIX
   make linux          # kernel, modules, fitImage where the makerule builds one
   ```
   `make linux` depends on `linux-dtbs` and, where the makerule says `linux: linux-dtbs u-boot`,
   on U-Boot as well.
3. Stage outputs into `board-support/built-images/`:
   ```bash
   make u-boot_stage ; make linux_stage    # linux_stage also runs u-boot_stage/linux-dtbs_stage where defined
   ```
   Target-by-target detail: [references/targets-and-outputs.md](references/targets-and-outputs.md).
4. Incremental rebuild: re-run the same target. U-Boot uses out-of-tree dirs under
   `board-support/u-boot-build/` (where the makerule sets `O=`), so only changed objects rebuild.
   `make linux` re-applies the config line from `makerules/Makefile_linux` (step 1 `grep`) on
   every run, which regenerates `.config` and discards manual changes.
5. Change the kernel configuration. Choose one:
   - Build the kernel by hand, keeping your `.config` (docs, Kernel Users Guide). Take `<cfg>` from the
     `grep defconfig` line of step 1 (config target plus fragments) and the image target from the
     makerule (`Image`, `zImage`, ...):
     ```bash
     cd "$TI_KERNEL_SRC_DIR"
     make ARCH=$TI_ARCH CROSS_COMPILE=$TI_CROSS_COMPILE <cfg>
     make ARCH=$TI_ARCH CROSS_COMPILE=$TI_CROSS_COMPILE menuconfig
     make ARCH=$TI_ARCH CROSS_COMPILE=$TI_CROSS_COMPILE -j"$(nproc)" <image-target> modules
     make DTC_FLAGS=-@ ARCH=$TI_ARCH CROSS_COMPILE=$TI_CROSS_COMPILE dtbs   # or one ti/<name>.dtb
     ```
     Fragments live in `<kernel>/kernel/configs/` (docs); `ls` it. Rebuild modules whenever the
     kernel is rebuilt (docs).
   - Keep using `make linux`: edit the fragment list in your SDK copy of `makerules/Makefile_linux`
     (back it up first).
   `.scmversion` in the kernel tree pins the version string; delete it if you add commits or
   upgrade the sources (docs).
6. Which device tree: take names from the SDK (`$TI_KB`, section on the board device tree), or:
   ```bash
   ls "$TI_KERNEL_SRC_DIR"/arch/$TI_ARCH/boot/dts/ti | grep -E "^($(echo "$TI_DTB_PREFIX" | sed 's|ti/||g'))" | grep -E '\.dtbo?$'
   ```
   `TI_DTB_PREFIX` is a `|`-separated list from `KERNEL_DEVICETREE_PREFIX`; some SDKs use a path
   without `ti/` (observed: AM335x) so adjust the directory. Writing overlays: `ti-device-tree-overlay`.
7. Custom boot-binary or board work (custom defconfig, signing): `ti-custom-board-port`, `ti-boot-chain`.

## Verify

```bash
ls -l "$TI_SDK_ROOT"/board-support/u-boot-build/*/{tiboot3*.bin,tispl.bin,u-boot.img} 2>/dev/null
ls -l "$TI_KERNEL_SRC_DIR"/arch/$TI_ARCH/boot/{Image,zImage} 2>/dev/null
file "$TI_KERNEL_SRC_DIR"/arch/$TI_ARCH/boot/Image     # on 64-bit SDKs: an ARM aarch64 boot executable
```
`built-images/` after `linux_stage` should hold what `$TI_KB` lists under boot files for your
platform, plus `dtb/ti/*.dtb*`. Newer mtimes than your edit confirm the rebuild ran. Then go to
`ti-deploy-image`.

## Troubleshooting (verified from docs/SDK)

- Docs say `linux` builds with `tisdk_<PLATFORM>_defconfig`; the makerule in the example AM62P 12.02 SDK uses
  `defconfig ti_arm64_prune.config` (and an AM335x SDK `multi_v7_defconfig ti_multi_v7_prune.config`).
  The SDK file is what runs; report both when asked.
- `make linux` also builds U-Boot where `linux: linux-dtbs u-boot`. For the kernel only, build by hand (step 5).
- Out-of-tree modules (GPU driver, cryptodev) must be rebuilt and reinstalled after the kernel
  is rebuilt; `modules_install` removes the old ones (docs).
- Kernel not rebuilding after `source environment-setup`: open a fresh shell (docs warning).
- Docs: U-Boot needs `bl31.bin`, `bl32.bin` (TEE) and TI firmware under `TI_LINUX_FIRMWARE`
  (`board-support/prebuilt-images/<platform>/` in the example AM62P SDK); read `Rules.make` for `UBOOT_ATF`,
  `UBOOT_TEE`, `TI_LINUX_FIRMWARE`, `TI_DM`.
- Yocto instead of SDK sources: use `ti-yocto-build`.
