# K3 boot flow details

Source: docs `BG-Bootflow-K3.html`, `Foundational_Components_Secure_Boot.html`, `BG-Build-K3.html`
(example read for the AM62P docs device, version `latest`; use `$TI_DOCS_DEVICE`); the device's IPC page; SDK files
listed under `built-images`.

| Stage | Runs on | Loaded by | Contents (docs) |
|---|---|---|---|
| ROM | TIFS / DMSC secure ROM, then public ROM on the R5 | reset | selects boot device per BOOTMODE pins |
| `tiboot3.bin` | MCU-side R5, on-chip SRAM | ROM (authenticates/decrypts on HS) | TIFS firmware + R5 SPL |
| `tispl.bin` (FIT) | R5 SPL loads it from boot media | R5 SPL | TF-A (`bl31`), OP-TEE, A53 SPL, SPL DTB, and the DM firmware |
| `u-boot.img` (FIT) | A53 SPL | A53 SPL | U-Boot proper + DTB |
| `fitImage` | U-Boot | U-Boot | kernel, DTB, DTBOs (verified by U-Boot itself) |

- Docs: the DM firmware runs the device-manager software (SciServer); example from the IPC pages for the
  AM62x/AM62P families: the WKUP R5F runs it, it is packaged in `tispl.bin` and started by R5 SPL right after
  DDR init (check the page for your device). See `ti-remoteproc`.
- Docs (U-Boot Build page): since the HSM re-architecture, loading remote cores with firmware at boot is only
  supported at the A72 SPL stage, not at R5 SPL (core reset moved into the DM service; R5 SPL lacks device and
  clock control for it). The note names A72, so it targets families with A72 cores; check the page for yours.
- Docs (Secure Boot): binman in the U-Boot source (`board-support/ti-u-boot*`) builds `tiboot3.bin` (R5 SPL), `tispl.bin` (bl31, bl32,
  A53 SPL and DTBs) and `u-boot.img`; per-component signing is described in `k3-<soc>-binman.dtsi`.
- Docs (Migration Guide): `k3-image-gen` is no longer used since SDK 9.0; binman replaced it.
