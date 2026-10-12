# SDK directory structure

Example listing from `ti-processor-sdk-linux-am62pxx-evm-12.02.00.01.01` (taken 2026-10-12); yours will differ.
Layout varies by SDK; always read `Rules.make` and list the tree (`ls $TI_SDK_ROOT $TI_SDK_ROOT/board-support`) instead of assuming.
Per-device facts derived from these files are collected in the generated KB (`$TI_KB`, `ti-generate-kb`).

| Path | Content |
|---|---|
| `Rules.make` | Per-SDK device config: `SOC`, `PLATFORM`, `ARCH`, U-Boot machine names, DTB prefix, cross compiler, `TI_SDK_PATH`, source dir variables |
| `Makefile`, `makerules/` | Top-level build: targets such as `linux`, `linux-dtbs`, `u-boot` and their `_stage`, `_install`, `_clean` forms (see docs page `linux/Overview/Top_Level_Makefile.html`) |
| `setup.sh` | Interactive SDK setup (patches `Rules.make` placeholders `DESTDIR`, `BOOTFS`, `EXEC_DIR`) |
| `bin/` | Helper scripts, for example `create-sdcard.sh`, `setup-host-check.sh`, `setup-package-install.sh`, `setup-uboot-env.sh`, `setup-tftp.sh`, `setup-targetfs-nfs.sh`, `setup-minicom.sh`, `setup-snagboot.sh`, `add-to-group.sh`, `sysfw_trace_parser.py`; list `bin/` for the full set |
| `board-support/ti-linux-kernel-*` | Kernel source |
| `board-support/ti-u-boot-*`, `trusted-firmware-a-*`, `optee-os-*` | Boot component sources |
| `board-support/built-images/` | Prebuilt boot and kernel images (`tiboot3*.bin`, `tispl.bin`, `u-boot.img`, `Image`, `fitImage`, `dtb/`) |
| `board-support/prebuilt-images/` | Prebuilt images shipped with the SDK |
| `board-support/k3-respart-tool/` | K3 resource partitioning tool inputs and `out/` (present only if the SDK ships it) |
| `board-support/extra-drivers/`, `linux-extras-*` | Out-of-tree drivers and extras |
| `linux-devkit/`, `k3r5-devkit/` | Cross toolchains and sysroots (A-core and R5) |
| `filesystem/` | Target root filesystem tarballs |
| `example-applications/` | Example application sources |
| `manifest/software_manifest.txt` | Component versions |

Docs: `ti_processor_sdk_docs_search(query="SDK directory structure", device=<TI_DOCS_DEVICE>, os="linux", version=<ver>)`.
