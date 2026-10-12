# Device security types and tiboot3 variants

Source: docs "GP to HS-FS Migration Guide" (example read for the AM62P docs device, version `latest`; the page is
written for one SoC family, re-read it for `$TI_DOCS_DEVICE`) and the SDK file listings.

- GP: no device protection, authentication not enabled for boot.
- HS-FS: factory state of a high-security device before customer keys are blown; authentication is not forced
  for boot, but the DMSC is locked. The default device targeted by the example (AM62P) docs is HS-FS.
- HS-SE: customer keys blown and enabled; all security features enforced; only signed images boot, and only
  `fitImage` boots the kernel.
- `tiboot3.bin` packages TI firmware that differs per device type, so the SDK ships up to three variants. The
  docs' fix for a GP board with the HS-FS default: rename the GP variant to `tiboot3.bin` on the boot partition.
- How to identify a device (docs): UART boot mode, capture the string the ROM prints, decode it with TI's
  `parse_uart_boot_socid.py`; it prints `DeviceType` GP, HSFS or HS-SE. Boot mode switch settings: TRM.
- Image rules (docs): unsigned images boot on GP and HS-FS, not on HS-SE; signed images boot on all.
- Observed files (examples; yours will differ): AM62P SDK `built-images`: `tiboot3-am62px-hs-evm.bin`,
  `tiboot3-am62px-hs-fs-evm.bin`, `tiboot3.bin` (identical to the hs-fs file by sha256). AM62x SDK 12.01
  prebuilt-images: `tiboot3-am62x-{gp,hs,hs-fs}-evm.bin`, default identical to the hs-fs file. ADAS SDK:
  `tiboot3-gp.bin`, `tiboot3-hs-fs.bin`, default `tiboot3.bin` identical to the GP file. Variant names differ per
  SDK: list (`scripts/verify-boot-artifacts.sh` or `$TI_KB`), do not guess.
- Secure-boot hardening items from the docs (production only): remove `uEnv.txt` loading, disable environment
  loading and fallback, set firewalls in board-config, enable dm-verity/dm-crypt, disable debug options.
