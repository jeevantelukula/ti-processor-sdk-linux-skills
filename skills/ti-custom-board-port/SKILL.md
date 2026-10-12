---
name: ti-custom-board-port
description: >-
  Derive a custom board from a TI Processor SDK reference board: clone the kernel board DTS,
  the U-Boot R5 and A53 device trees and defconfigs, regenerate DDR/board configuration, and
  build and boot it with the SDK makefiles. Use when the user has their own carrier or SoM
  hardware based on a TI K3 SoC and needs boot (tiboot3/tispl/u-boot.img) plus Linux DTB for it.
---

# TI custom board port

Method: pick the SDK's own reference board for the same SoC and copy its files. Every path below is
derived from the SDK trees; paths and names differ per SoC, so list them first, do not assume them.

## Docs (MCP)
Follow [../../context/mcp-usage.md](../../context/mcp-usage.md). Always pass
`device=$TI_DOCS_DEVICE os="linux" version=$TI_SDK_VERSION_DOCS` explicitly (empty `$TI_DOCS_DEVICE`: key from `$TI_KB` or
`ti_processor_sdk_docs_list_variants`). If `ti_processor_sdk_docs_list_versions(device)` lacks your SDK version (the MCP lags new
releases), use `version="latest"` and say so. Cite the doc `path` you relied on; where docs and the SDK tree disagree, report both.
- `ti_processor_sdk_docs_search(query="U-Boot build R5 A53 binman tiboot3.bin tispl.bin", ...)` then read `.../U-Boot/BG-Build-K3.html`.
- `ti_processor_sdk_docs_search(query="DDR register configuration tool custom board", ...)` then read `.../U-Boot/UG-DDRSS.html`
  (the DDR configuration `.dtsi` is generated with the SysConfig tool, product "DDR Configuration for <device>").
- `ti_processor_sdk_docs_search(query="Kernel Users Guide build dtbs", ...)`.
- `ti_processor_sdk_docs_search(query="GP to HS-FS Migration Guide tiboot3", ...)` (which tiboot3 binary matches the silicon).

## Prerequisites
- SDK extracted, `source lib/ti-sdk-env.sh` (`TI_SOC`, `TI_PLATFORM`, `TI_UBOOT_MACHINE`, `TI_UBOOT_MACHINE_R5`, `TI_DTB_PREFIX`,
  `TI_KERNEL_SRC_DIR`, `TI_UBOOT_SRC_DIR`, `TI_CROSS_COMPILE`, `TI_CROSS_COMPILE_R5`, `TI_KB`, `TI_FACTS_JSON`).
  Reference board name, defconfigs, board directory and DDR/boot-binary names: read `$TI_KB` / `$TI_FACTS_JSON`; if unset or missing,
  run skill `ti-generate-kb`. Some SoCs have no R5 defconfig (empty `TI_UBOOT_MACHINE_R5`): then skip every R5 step.
- Board schematics: DDR part and layout, PMIC, boot media, pad usage. DDR settings cannot be copied from the EVM unless the memory is identical.
- A working reference build of the SDK first (`make u-boot`, `make linux-dtbs` from the SDK root).

## Steps

### 1. Identify the reference board (read, do not guess)
```bash
echo $TI_UBOOT_MACHINE $TI_UBOOT_MACHINE_R5 "$TI_DTB_PREFIX"
grep -n "DEFAULT_DEVICE_TREE\|OF_UPSTREAM" $TI_UBOOT_SRC_DIR/configs/$TI_UBOOT_MACHINE $TI_UBOOT_SRC_DIR/configs/$TI_UBOOT_MACHINE_R5
skills/ti-custom-board-port/scripts/create-board-dts.sh <reference-basename> <new-basename>     # dry run, prints every file to clone
ls $TI_UBOOT_SRC_DIR/board/ti/                                   # board directory of your SoC: env, evm.c, *-cfg.yaml
```
What to find (derive each from your SDK with the commands above):
- A53 defconfig: `CONFIG_DEFAULT_DEVICE_TREE` and whether `CONFIG_OF_UPSTREAM=y`. With OF_UPSTREAM the DTS comes from
  `dts/upstream/src/arm64/` in the U-Boot tree (`dts/Makefile`: `dt_dir := dts/upstream/src/arm64`); the same DTS is in the kernel tree.
- R5 defconfig (if any): its DTS is under `arch/arm/dts/` (no OF_UPSTREAM) and `#include`s the board DTS, a `-u-boot.dtsi`, a DDR `.dtsi` and a SoC R5 `.dtsi`.
- U-Boot auto-includes `<dts-basename>-u-boot.dtsi` from `arch/arm/dts/` if it exists (`scripts/Makefile.lib`, `u_boot_dtsi_options`),
  then falls back to SoC/CPU/vendor/`u-boot.dtsi`. So a new A53 board DTS named `X.dts` wants `arch/arm/dts/X-u-boot.dtsi`.
- The binman dtsi (`grep -ln "<reference-basename>" $TI_UBOOT_SRC_DIR/arch/arm/dts/*binman*`) hard-codes the reference DTB name and
  `description` entries. Clone/edit it for the new name.
- `board/ti/<soc-dir>/<soc-dir>.env` and `evm.c`: `board_late_init()` calls `ti_set_fdt_env(NULL, NULL)`, so `fdtfile` =
  `CONFIG_DEFAULT_FDT_FILE` if set, else `<CONFIG_DEFAULT_DEVICE_TREE>.dtb`; U-Boot then loads `${bootdir}/dtb/${fdtfile}`
  (`bootdir` from the env file). Renaming the device tree therefore renames the DTB the bootloader asks for.
- `board/ti/<soc-dir>/` also holds `board-cfg.yaml`, `pm-cfg.yaml`, `rm-cfg.yaml`, `sec-cfg.yaml` (TI-SCI board/resource configuration
  built into tiboot3). Changing resource ownership: see skill `ti-resource-partition`.

Names seen in the SDK used for verification (example from AM62P SDK 12.02.00.01.01; yours will differ):
```text
A53 defconfig   CONFIG_DEFAULT_DEVICE_TREE="ti/k3-am62p5-sk", CONFIG_OF_UPSTREAM=y
R5 defconfig    CONFIG_DEFAULT_DEVICE_TREE="k3-am62p5-r5-sk"  (includes k3-am62p5-sk-u-boot.dtsi)
binman dtsi     arch/arm/dts/k3-am62p-sk-binman.dtsi: #define SPL_AM62PX_SK_DTB "spl/dts/ti/k3-am62p5-sk.dtb"
board dir       board/ti/am62px/ (am62px.env, evm.c, *-cfg.yaml), bootdir=/boot
live board      /boot/dtb/ti/k3-am62p5-sk.dtb
```

### 2. Kernel device tree
1. `create-board-dts.sh <ref> <new> --apply` copies `arch/arm64/boot/dts/ti/<ref>.dts` to `<new>.dts` (never overwrites).
   Change `model` and `compatible`; keep the includes.
2. Add `dtb-$(CONFIG_ARCH_K3) += <new>.dtb` to `arch/arm64/boot/dts/ti/Makefile` beside the reference entry.
3. Keep `<new>` matching `$TI_DTB_PREFIX` (Rules.make `KERNEL_DEVICETREE_PREFIX`); `make linux-dtbs` selects files by that prefix
   and builds them with `DTC_FLAGS=-@` (`makerules/Makefile_linux-dtbs`). Install target: `$DESTDIR/boot/dtb/ti/`.
4. Edit pinmux, regulators, peripherals for your hardware (`ti-gpio-pinmux`; options as overlays: `ti-device-tree-overlay`).
Check the standalone compile quickly: `skills/ti-device-tree-overlay/scripts/build-dtbo.sh <new>.dts -o /tmp/x.dtb` (cpp+dtc with kernel includes;
tested, as an example, on the reference board DTS of six SoCs from the AM62P SDK kernel tree (AM62P, AM62x, AM62A, AM62L, AM64x, AM62D): all compile).

### 3. U-Boot
1. Copy the reference defconfigs under new names in `configs/`; set `CONFIG_DEFAULT_DEVICE_TREE` in each to the new DTS
   (A53: `ti/<new>`, R5: `<r5-new>`). Keep the other options until the board boots; remove/adjust only what the schematic requires.
2. R5: new `arch/arm/dts/<r5-new>.dts` (copy of the reference R5 dts, edit its includes), and add `<r5-new>.dtb` next to the reference in
   `arch/arm/dts/Makefile` (the reference line sits under a `dtb-$(CONFIG_SOC_K3_<soc>)` block; find yours with `grep -n "<r5-ref>" arch/arm/dts/Makefile`).
3. DDR: regenerate the DDR `.dtsi` for your memory with SysConfig and include it instead of the reference one (docs: DDR page above).
4. A53: board DTS into `dts/upstream/src/arm64/ti/`, plus `arch/arm/dts/<new>-u-boot.dtsi` and the binman dtsi changes above.
5. Build with the SDK rules (read `makerules/Makefile_u-boot`: the variables passed differ per SoC, for example `TI_DM`, `BL1`, `TEE`), overriding the machine names on the command line (command-line make variables override `Rules.make`):
```bash
make u-boot UBOOT_MACHINE=<new_a53_defconfig> UBOOT_MACHINE_R5=<new_r5_defconfig>     # SDK root; runs u-boot-r5 then u-boot-a53
```
`makerules/Makefile_u-boot` does `make ... $(UBOOT_MACHINE_R5) O=.../u-boot-build/r5` then the A53 build with `BINMAN_INDIRS`, `BL31`, `TEE`, `TI_DM`
from Rules.make; outputs `u-boot-build/r5/tiboot3*.bin` and `u-boot-build/a53/{tispl.bin,u-boot.img}`; `make u-boot_stage` copies them to `board-support/built-images/`.
Not build-tested for a renamed board in this skill (only the reference structure and the SDK build rules were verified).

### 4. Boot files per silicon type
List what your SDK built: `ls $TI_SDK_ROOT/board-support/built-images`. Example from AM62P SDK 12.02.00.01.01 (yours will differ): it had `tiboot3-<soc>-hs-evm.bin`,
`...-hs-fs-evm.bin` and `tiboot3.bin`; the docs migration page mentions a `gp` variant for GP devices and says HS-FS is the default, which that
build did not show - report any such mismatch with the docs path. Which variant matches your silicon: the migration guide above and the device marking.
Never mix boot binaries from different SDK releases.

## Verify
1. Kernel: `make linux-dtbs` produces `<new>.dtb`; `dtc -I dtb -O dts` shows your `model`.
2. U-Boot: R5 and A53 builds finish and the boot log shows U-Boot loading `dtb/<fdtfile>` for your DTB name.
3. Target: `cat /proc/device-tree/model`, `dmesg | grep -i error`, `gpiodetect`, `/sys/kernel/debug/pinctrl/*/pinmux-pins` (`ti-gpio-pinmux`).

## Troubleshooting (verified)
- U-Boot build fails with "Device Tree Source (...) is not correctly specified. Please define 'CONFIG_DEFAULT_DEVICE_TREE'" (`dts/Makefile`):
  the DTS named by `CONFIG_DEFAULT_DEVICE_TREE` is missing from `dt_dir` (`dts/upstream/src/arm64` for A53, `arch/arm/dts` for R5).
- Kernel boots the wrong DTB: `fdtfile` comes from `CONFIG_DEFAULT_FDT_FILE`/`CONFIG_DEFAULT_DEVICE_TREE` (`board/ti/common/fdt_ops.c`); check the name on the boot partition.
- No console or `Authentication failed` from SPL on HS parts: docs show these symptoms for unsigned or wrong-type boot images, see "GP to HS-FS Migration Guide" (authentication failure examples).
- Everything else (DDR bring-up, PMIC, boot-mode switches): not covered; docs query "DDR register configuration tool custom board", the TRM and the board schematic.
