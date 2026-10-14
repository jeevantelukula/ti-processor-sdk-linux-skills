# Cores started by the bootloader (device-manager firmware)

Example evidence (AM62P SDK 12.02.00.01.01; yours will differ): docs "IPC for AM62Px" / "IPC for AM62x", SDK `Rules.make`, `makerules/Makefile_u-boot`,
live AM62P board dmesg. Only SoCs whose `rproc.sh list` shows an
`attached` core or whose `Rules.make` defines `TI_DM` apply; on others (e.g. AM64x, AM62L) skip this page.

- Docs (e.g. AM62Px, AM62x): the WKUP R5F runs device-manager firmware plus a demo IPC app. It is packed into
  `tispl.bin` and started early by the R5 SPL right after DDR init. The Linux driver only attaches
  (live board: state `attached`, dmesg `remote processor 78000000.r5f is now attached`).
- Docs (e.g. AM64x): early boot of R5F is not supported there; Linux loads them.
- `Rules.make` names the file used for the build: variable `TI_DM` (a path under
  `board-support/prebuilt-images/<PLATFORM>/ti-dm/...` in the example AM62P SDK; there `Rules.make` has two `TI_DM` lines selected by
  `DISPLAY_CLUSTER`, default 0).

## Replace the firmware in the boot image
The docs describe: replace the DM firmware binary, rebuild U-Boot with the top-level Makefile, copy the new
`tispl.bin` to the boot partition, reboot. The docs' source path differs from the SDK layout; the authority is
`TI_DM` in your `Rules.make`:
```
grep -n '^TI_DM' "$TI_SDK_ROOT/Rules.make"
cp <new-firmware> <TI_DM path of the variant you build>      # back up the original first
make -C "$TI_SDK_ROOT" u-boot                    # builds R5 and A53 U-Boot
```
`makerules/Makefile_u-boot` writes the A53 build to `board-support/u-boot-build/a53/` (`tispl.bin`
included) and `make u-boot_stage` copies it to `board-support/built-images/`. Deploy the new `tispl.bin`
together with the `tiboot3.bin` of the same build (a precaution, not a documented rule; see `ti-boot-chain`).
The docs say this firmware runs the device manager (SciServer). Replace it only with firmware that still
provides it, confirm with the user, and keep a known-good `tispl.bin`.
