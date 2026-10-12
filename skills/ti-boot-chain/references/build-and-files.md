# Building and file locations

Evidence (example from AM62P SDK 12.02.00.01.01; yours will differ): `Rules.make`, `makerules/Makefile_u-boot`,
docs `BG-Build-K3.html`. An AM335x SDK has none of this (single `u-boot` target, MLO flow); an ADAS SDK stages
into other directories; one SoC branch in the makerule has no R5 stage.

## SDK Makefile (authoritative for this SDK)
- `u-boot` = `u-boot-r5 u-boot-a53` (for SoCs where the target applies; the makefile special-cases some SoCs).
- `u-boot-r5`: `make -C $(UBOOT_SRC_DIR) ARCH=arm $(UBOOT_MACHINE_R5) O=.../u-boot-build/r5`, then builds with
  `CROSS_COMPILE_ARMV7` and `BINMAN_INDIRS=$(TI_LINUX_FIRMWARE)`.
- `u-boot-a53`: `$(UBOOT_MACHINE)` then build with `BINMAN_INDIRS`, `BL31=$(UBOOT_ATF)`, `TEE=$(UBOOT_TEE)`,
  `TI_DM=$(TI_DM)`, `O=.../u-boot-build/a53`.
- `u-boot_stage` copies `tispl.bin`, `u-boot.img` from `u-boot-build/a53` and `tiboot3*.bin` from
  `u-boot-build/r5` into `board-support/built-images/`.
- The variables are in `Rules.make`: `UBOOT_MACHINE`, `UBOOT_MACHINE_R5`, `UBOOT_ATF` (`bl31.bin`),
  `UBOOT_TEE` (`bl32.bin`), `TI_LINUX_FIRMWARE` (prebuilt-images/<platform>), `TI_DM`.

## Manual build (docs "Build" page)
Exports `UBOOT_DIR`, `TI_LINUX_FW_DIR`, `TFA_DIR`, `OPTEE_DIR`; R5: `make ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_32"
<r5 defconfig> O=$UBOOT_DIR/out/r5` then the same with `BINMAN_INDIRS=$TI_LINUX_FW_DIR`; A53: `<a53 defconfig>`,
then `make ... CC="$CC_64" BL31=<bl31.bin> TEE=<tee-pager_v2.bin> O=$UBOOT_DIR/out/a53 BINMAN_INDIRS=...`.
Docs: since SDK 9.0 GP, HS-SE and HS-FS use the same defconfig. `BINMAN_INDIRS` must be an absolute path with
`ti-dm/` and `ti-sysfw/` subdirectories (the SDK `prebuilt-images/<platform>` layout). Optional `TI_DM=<file>`
picks a custom DM binary (devices using split firmware).
The docs table lists USB DFU and USB MSC boot variants as extra config fragments for the R5 build; read the page
for your board before using them.

## DFU (docs, "SD, eMMC and USB")
With the board at U-Boot and USB in peripheral mode: `dfu 0 mmc 0` after `setenv dfu_alt_info ${dfu_alt_info_emmc}`,
then `dfu-util -R -a tiboot3.bin.raw -D tiboot3.bin` (same pattern for `tispl.bin.raw`, `u-boot.img.raw`).
Target names come from `dfu-util -l`.
