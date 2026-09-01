# SDK Version Compatibility Matrix

## Current Release

| Component | Version | Notes |
|---|---|---|
| SDK | 12.01.00.05.03 | Released 2026-07-31 |
| Linux Kernel | 6.18.38-ti | LTS + TI patches |
| U-Boot | 2025.01-ti | |
| TF-A | v2.12-ti | BL31 |
| OP-TEE | 4.5.0-ti | BL32 |
| SYSFW | ti-fs-stub-enc-hs.bin (inside tiboot3) | |
| TI DM FW | from ti-linux-firmware | |
| Yocto Version | Scarthgap (5.0) | |
| GCC Toolchain | aarch64-oe-linux-gcc 14.x | in linux-devkit |

## Supported Boards (SDK 12.01.00.05.03)

| MACHINE | Board | Notes |
|---|---|---|
| am62xx-evm | SK-AM62x (GP, HS-FS, HS-SE) | Primary reference |
| am62xx-lp-evm | SK-AM62x LP | Low-power variant |
| beagleplay-ti | BeaglePlay | Community board |

## Prebuilt DTBs (am62xx-evm)

| DTB | Board |
|---|---|
| k3-am625-sk.dtb | AM625 SK EVM |
| k3-am625-beagleplay.dtb | BeaglePlay |
| k3-am625-phyboard-lyra-rdk.dtb | Phytec phyBOARD-Lyra |
| k3-am625-verdin-wifi-dev.dtb | Toradex Verdin AM62 |
| k3-am625-sk-lp-evm.dtb | AM625 LP EVM |
| k3-am623-beagleplay.dtb | BeaglePlay (AM623) |

## Breaking Changes Between Releases

### SDK 12.x → Key Changes
- Kernel 6.18 (from 6.6 in SDK 11.x)
- Yocto Scarthgap (was Nanbield in SDK 11.x)
- eMMC boot mode detection fix included (no longer needs manual patch)
- Chromium added to `tisdk-default-image` by default (~200 GB extra disk)

### SDK 10.x → 11.x
- Kernel 6.6 (from 6.1 in SDK 10.x)
- U-Boot 2025.01 (was 2024.01)
- `KERNEL_DEVICETREE` append syntax changed: requires `:am62xx-evm` machine override

### SDK 9.x → 10.x
- Layer name changes: `meta-ti-bsp` separated from `meta-tisdk`
- Yocto Kirkstone → Nanbield

## Version Mismatch Warnings

**Never mix boot binaries across SDK releases.** The SYSFW version inside
`tiboot3.bin` must match the DM firmware version in `tispl.bin`.

Symptom of mismatch: `NOTICE: SYSFW ABI mismatch` at boot.
Fix: Use all boot binaries from the same SDK release.

## SDK Download URLs

| Release | URL |
|---|---|
| Latest AM62x | https://www.ti.com/tool/download/PROCESSOR-SDK-LINUX-AM62X |
| 12.01.00.05.03 | https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/12_01_00_05_03/ |
| Release history | https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/ |
