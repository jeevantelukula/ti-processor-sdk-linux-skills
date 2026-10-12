# Top-level Makefile targets and outputs

Evidence (example from AM62P SDK 12.02.00.01.01; yours will differ): `Makefile`,
`makerules/Makefile_linux`, `Makefile_linux-dtbs`, `Makefile_u-boot`, and docs page
`linux/Overview/Top_Level_Makefile.html` (read for the AM62P docs device, `latest`, which lags the SDK).
Other SoCs share the layout but branch on `SOC` or differ entirely (an AM335x SDK has `linux: linux-dtbs`,
`zImage`, a single `u-boot` target and no `u-boot-r5`; an ADAS SDK stages into other directories):
re-read your SDK's makerules and `$TI_KB` (make targets section).
Paths are relative to the SDK root (`$TI_SDK_ROOT`). `$X` means the `Rules.make` variable.

| Target | What it runs (from the makerule) | Writes |
|---|---|---|
| `u-boot-r5` | `make $UBOOT_MACHINE_R5` then build with `CROSS_COMPILE_ARMV7`, `BINMAN_INDIRS=$TI_LINUX_FIRMWARE`, `O=...` | `board-support/u-boot-build/r5/` (`tiboot3*.bin`) |
| `u-boot-a53` | `make $UBOOT_MACHINE` then build with `CROSS_COMPILE`, `BINMAN_INDIRS`, `BL31=$UBOOT_ATF`, `TEE=$UBOOT_TEE`, `TI_DM=$TI_DM` | `board-support/u-boot-build/a53/` (`tispl.bin`, `u-boot.img` expected) |
| `u-boot` | `u-boot-r5 u-boot-a53` (SoC-dependent prerequisites) | both of the above |
| `u-boot_stage` | copies `a53/tispl.bin`, `a53/u-boot.img`, `r5/tiboot3*.bin` | `board-support/built-images/` |
| `u-boot_install` | `u-boot_stage`, then copies the same three to `$(DESTDIR)` | `$DESTDIR/` (must exist). The error text says `BOOTFS=` but the recipe tests and uses `DESTDIR` |
| `linux-dtbs` | `defconfig ti_arm64_prune.config $(RT_FRAGMENT)`, then `make DTC_FLAGS=-@ <dtb>` for each match of `KERNEL_DEVICETREE_PREFIX` | `<kernel>/arch/<arch>/boot/dts/ti/` |
| `linux-dtbs_stage` | copies the DTBs | `board-support/built-images/dtb/ti/` |
| `linux-dtbs_install` | stage, then `install -m 0644` | `$DESTDIR/boot/dtb/ti/` |
| `linux` | prerequisites `linux-dtbs u-boot`; `defconfig ti_arm64_prune.config $(RT_FRAGMENT)`; `Image Image.gz`; `modules`; `mkimage` of `prebuilt-images/<platform>/fitImage-its-<machine>` with the U-Boot key dir; rebuilds U-Boot A53 so its dtb carries the key | kernel tree plus `board-support/built-images/fitImage` |
| `linux_stage` | `linux-dtbs_stage u-boot_stage`, then copies `Image` | `board-support/built-images/` |
| `linux_install` | `linux_stage linux-dtbs_install`; installs `fitImage`, `Image`, `vmlinux`, `System.map` to `$DESTDIR/boot`; `modules_install` with `INSTALL_MOD_PATH=$DESTDIR` and `INSTALL_MOD_STRIP` | `$DESTDIR/boot`, `$DESTDIR/lib/modules` |
| `*_clean` | `linux_clean` = kernel `mrproper`; `u-boot_clean` = `distclean` of both build dirs | |
| `all`, `install`, `clean` | iterate `MAKE_ALL_TARGETS` from Rules.make | list differs per SDK |

`RT_FRAGMENT` is referenced by the makerules. In the RT SDK checked (AM335x) it is defined in
`Rules.make` as `ti_rt.config`; the other SDK checked (example: AM62P) does not define it (empty).

## Preview without building

`make -n <target>` prints the expanded commands (recursive makes included). Used for the checks
in this repo; no build was started.

## Where DTBs and the kernel image come from at runtime

Docs (Kernel Users Guide): U-Boot reads `Image` and the DTB/DTBO files from `/boot` of the root
filesystem on MMC; HS-SE devices boot `fitImage` by default; `boot_fit` U-Boot variable toggles
FIT booting. See `ti-deploy-image` for placing them.
