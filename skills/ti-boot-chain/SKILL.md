---
name: ti-boot-chain
description: >
  Explain, locate, rebuild and sanity-check the TI K3 boot binaries (tiboot3.bin, tispl.bin, u-boot.img,
  fitImage) and the device-manager (DM) firmware inside tispl.bin, and choose the right tiboot3 variant for
  a GP, HS-FS or HS-SE device. Use when a board does not reach U-Boot, when boot files must be rebuilt or
  copied to an SD/eMMC boot partition, or when asked how the K3 boot flow works. Older Sitara parts
  (MLO + u-boot.img) are detected and reported as a different flow.
---

# ti-boot-chain

Only what the SDK docs and the installed SDK state is recorded here. Flashing media is `ti-deploy-image`.

## Docs (MCP)
Follow [references/mcp-usage.md](references/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`,
`version=$TI_SDK_VERSION_DOCS` (else `latest`; the MCP lags the SDK, say so) explicitly. The SDK files win over a
page; several pages are written for one SoC (the Migration Guide names one), so state which parts you applied
to your device. Cite the page path.
- `ti_processor_sdk_docs_search(query="Boot Flow K3 tiboot3 tispl u-boot.img", device=$TI_DOCS_DEVICE, os="linux", version=...)` -> `linux/Foundational_Components/U-Boot/BG-Bootflow-K3.html`
- `query="Build U-Boot K3 R5 A53 defconfig BINMAN_INDIRS"` -> `.../U-Boot/BG-Build-K3.html`
- `query="Secure Boot HS-FS HS-SE chain of trust"` -> `linux/Foundational_Components_Secure_Boot.html`
- `query="GP to HS-FS Migration Guide tiboot3 device type"` -> `linux/Foundational_Components_Migration_Guide.html`
- `query="SD, eMMC and USB MMC boot modes"` -> `.../U-Boot/UG-Memory-K3.html`

## Prerequisites
- Paths here are relative to this skill's directory. Shell variables do not persist between commands: run
  `source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*` (the
  bundled scripts load it themselves).
- `scripts/ti-sdk-env.sh` exported `TI_SDK_ROOT`, `TI_PLATFORM`, `TI_DOCS_DEVICE`; `$TI_KB` / `$TI_FACTS_JSON` hold the boot
  files and tiboot3 variants found in this SDK (run `ti-generate-kb` if unset).
- The device's security type (GP, HS-FS, HS-SE). It is a silicon property, see `references/security-modes.md`.
- Serial console to the board for boot logs (port, baud, program from profile `board.serial`; default 115200 8N1).

## tiboot3 Security Variants (per SoC - check SDK directory)

Each SoC provides up to three `tiboot3` variants in `board-support/prebuilt-images/<platform>/`:
- `tiboot3-<soc>-gp-evm.bin` - General Purpose (no security)
- `tiboot3-<soc>-hs-fs-evm.bin` - High Security Field Securable (default in SDK)
- `tiboot3-<soc>-hs-evm.bin` - High Security Enforced (signed required)

Use `ls $TI_SDK_ROOT/board-support/prebuilt-images/$TI_PLATFORM/tiboot3*.bin` to list what's available for your platform.

Cross-variant behavior (docs Migration Guide):
- HS-FS + unsigned: boots with "Skipping authentication" warning
- HS-SE + unsigned: "Authentication failed!" - boots only signed
- GP + signed: warning "certificate skipped"
- Signed images boot on all variants

## The K3 flow (docs "Boot Flow")
Docs: ROM supports boot only via the MCU R5 core, so (K3 devices with an R5 stage; see step 3 for an exception): ROM loads and authenticates `tiboot3.bin` (R5 SPL plus TIFS
firmware) -> R5 SPL configures DDR, loads `tispl.bin`, loads the device-manager firmware, starts the A53
and jumps to DM -> on the A53, TF-A/OP-TEE and A53 SPL (all from `tispl.bin`) run -> A53 SPL loads
`u-boot.img` -> U-Boot proper -> kernel (`fitImage`, or `Image` + DTB). Details: `references/boot-flow.md`.

## Steps

1. Identify the flow and the files shipped with the SDK (read-only):
   ```
   scripts/verify-boot-artifacts.sh
   ```
   K3 SDKs list `tiboot3*.bin`, `tispl.bin`, `u-boot.img` in `board-support/built-images`
   (or `prebuilt-images`). An SDK with `MLO` + `u-boot.img` (observed: an AM335x SDK) uses the older SPL flow,
   which this skill does not cover beyond detection. The script sources `scripts/ti-sdk-env.sh` itself if
   `TI_SDK_ROOT` is unset (pass the SDK path via `TI_SDK_ROOT=...`).
2. Choose the `tiboot3` variant for the silicon. The script prints which named variant `tiboot3.bin` equals;
   that default differs per SDK (example observed: an AM62P SDK default = HS-FS variant, an ADAS SDK default = GP).
   Docs: one variant's TI firmware may not work on another device type. See `references/security-modes.md`.
3. Rebuild (only if sources changed). With the SDK top-level Makefile, from `$TI_SDK_ROOT`:
   ```
   make u-boot          # stages named in makerules/Makefile_u-boot: R5 (tiboot3*) then A53 (tispl.bin, u-boot.img)
   make u-boot_stage    # copies results into board-support/built-images
   ```
   Build dirs: `board-support/u-boot-build/{r5,a53}`. Exception seen in the makerule: one SoC branch builds
   without an R5 stage and takes `tiboot3*` from the A53 build dir; read `makerules/Makefile_u-boot` first. Machine names, DM firmware path (`TI_DM`), TF-A and
   OP-TEE inputs come from `Rules.make`; do not retype them. Manual builds and the `BINMAN_INDIRS` input are in
   the docs "Build" page (`references/build-and-files.md`).
4. Put the files on the boot medium (changes the board; confirm first). Docs (SD): copy `tiboot3.bin`,
   `tispl.bin`, `u-boot.img` to the SD boot partition. Name the chosen variant `tiboot3.bin`.
   Compare against a mounted or copied boot partition:
   ```
   scripts/verify-boot-artifacts.sh --boot-dir /media/$USER/boot
   ```
5. Kernel selection: docs say U-Boot boots `fitImage` by default and falls back to `Image` + DTB under
   `root/boot`; HS-SE devices boot only `fitImage`. Env var `boot_fit` set to 1 selects the FIT image.

## Verify
- Serial console: SPL banners, `Trying to boot from MMC...`, U-Boot prompt or autoboot, then kernel. Docs sample logs
  show `Authentication passed` lines on secure devices.
- On the running board, `dmesg | grep ti-sci` shows the TIFS firmware version the boot chain loaded
  (example from one AM62P board; yours will differ: `ti-sci 44043000.system-controller: ABI: 4.0 (firmware rev 0x000c '12.1.2--v12.01.02 (Clever Cat)')`).
- `scripts/verify-boot-artifacts.sh --boot-dir <boot partition>` reports SAME for all three files when the board
  runs exactly the SDK's images.
- Keep `tiboot3`, `tispl` and `u-boot.img` from one build. No docs page read for this skill states a mixing rule, so this is
  a precaution, not a documented requirement; the script flags differences.

## Troubleshooting (docs; observed where stated)
- No console output or `Authentication failed!` on HS-SE with unsigned images (docs Migration Guide).
- HS-FS with unsigned images: boots with `Skipping authentication` warning; signed image on GP: warning that the
  certificate is skipped (docs).
- Wrong device type binary: docs say one device type's firmware may not work on another; use the matching variant.
- Example: the AM62P Migration Guide names a `gp` variant of tiboot3; the AM62P SDK 12.02.00.01.01 `built-images`
  had only `hs` and `hs-fs` variants plus `tiboot3.bin` (and a capsule file). Trust the SDK directory listing over the docs
  and report the mismatch.
- SD init failure in SPL (`spl: mmc init failed with error: -110`): docs list workarounds in order (cap the SD
  speed mode with `sdhci-caps-mask`, longer power-cycle delay, bus width 1) on the "SD, eMMC and USB" page.
- Boot from eMMC: docs distinguish eMMC boot (ROM boots only from Boot0/Boot1) and MMCSD boot (SD, or eMMC UDA);
  pins select it per the TRM.
- Boot partition files differ from the SDK's: the script shows it (observed: all three files differed between an
  SDK `built-images` and a running board's boot partition; cause not determined). Make the card and the SDK images
  come from the same build before debugging further.
References: `boot-flow.md`, `security-modes.md`, `build-and-files.md`.
