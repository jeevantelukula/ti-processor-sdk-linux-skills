---
name: ti-kernel-module
description: >
  Cross-compile an out-of-tree Linux kernel module against the kernel tree shipped in a TI Processor SDK,
  check that it matches the kernel running on the board, and load it. Use when the user wants to build,
  rebuild or deploy a custom driver (.ko), asks why insmod says "Invalid module format", or asks how to
  build modules for the SDK kernel. Uses the toolchain and architecture from the SDK Rules.make.
---

# ti-kernel-module

An out-of-tree module is built with the kernel's Kbuild against a configured kernel tree. In a TI SDK that
tree is `board-support/ti-linux-kernel-*` and the cross compiler is the one named in `Rules.make`.
A module only loads on a kernel whose release string matches the one it was built against (see Step 2).

## Docs (MCP)
Follow [references/mcp-usage.md](references/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`,
`version=$TI_SDK_VERSION_DOCS` explicitly (empty `$TI_DOCS_DEVICE`: key from `$TI_KB` or `ti_processor_sdk_docs_list_variants`).
If `ti_processor_sdk_docs_list_versions(device)` lacks your version, use `latest` and say the MCP lags the SDK. Cite the doc `path` you used.
- `ti_processor_sdk_docs_search(query="Kernel Users Guide compiling the kernel modules", ...)` -> `linux/Foundational_Components_Kernel_Users_Guide.html` (cross compile setup, `modules`, `modules_install`, `INSTALL_MOD_PATH`)
- `query="SDK build using Makefile linux_install"` -> `linux/Overview/Top_Level_Makefile.html`
- `query="rpmsg client sample kernel module"` -> per-device IPC page (a worked kernel-module build and `modprobe` example;
  only devices with remote cores have one: a search on AM62LX finds none)
Kbuild rules themselves are in the SDK kernel tree: `Documentation/kbuild/modules.rst`.

## Prerequisites
- Paths here are relative to this skill's directory. Shell variables do not persist between commands: run
  `source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*` (the
  bundled scripts load it themselves).
- `scripts/ti-sdk-env.sh` sourced: `TI_SDK_ROOT`, `TI_ARCH`, `TI_CROSS_COMPILE` (from `Rules.make`: `ARCH`, `CROSS_COMPILE`).
- A clean shell: do not source the devkit `environment-setup*` file. The TI kernel guide says doing so
  makes host-side kernel components fail to compile; `scripts/build-module.sh` refuses if it is sourced.
- The SDK kernel tree must be configured and built (`.config`, `include/generated/autoconf.h`; a full build
  also produces `Module.symvers`). `make -C "$TI_SDK_ROOT" linux` builds it (target defined in `makerules/Makefile_linux`);
  `modules_prepare` is the minimal alternative (kernel docs: it does not build `Module.symvers`).
- Host tools: `make`, `file`, `modinfo` (kmod); `ssh` only for `--board`.

## Steps
1. Module sources in one directory with a `Kbuild` (or `Makefile`) containing `obj-m := <name>.o`.
   A minimal working pair is in `references/example-module/` (`hello.c`, `Kbuild`).
2. Compare releases before building (read-only):
   ```
   cat "$TI_SDK_ROOT"/board-support/ti-linux-kernel-*/include/config/kernel.release
   ssh root@<board-ip> uname -r
   ```
   They must be identical. If they differ, the board runs a different kernel build than the SDK tree.
   Fix it by running the tree's kernel on the board (build `linux`, then deploy the `Image`/`fitImage`, DTB and
   modules from the tree, see `ti-deploy-image`, or `make linux_install`, defined in `makerules/Makefile_linux`),
   or build against a tree that matches the board's kernel.
3. Build:
   ```
   scripts/build-module.sh <module-dir> --board root@<board-ip>
   ```
   It runs `make -C <kernel tree> M=<module-dir> ARCH=$TI_ARCH CROSS_COMPILE=$TI_CROSS_COMPILE modules`,
   prints the tree release, warns if the board differs, and prints `file` and `vermagic` of each `.ko`.
   `--clean` runs the `clean` target. Set `KDIR` to override the tree.
4. Deploy and load (changes board state; confirm first):
   ```
   scp <module-dir>/<name>.ko root@<board-ip>:/tmp/
   ssh root@<board-ip> 'insmod /tmp/<name>.ko && dmesg | tail'
   ```
   To install into a root filesystem instead, kernel docs: `make -C <tree> M=<module-dir> INSTALL_MOD_PATH=<rootfs>
   modules_install`, then `depmod` on the target and `modprobe <name>`.

## Verify
- `modinfo -F vermagic <name>.ko` on the host: first token equals `uname -r` of the board. Observed vermagic
  format (example from AM62P SDK 12.02.00.01.01; yours will differ): `6.18.51-... SMP preempt mod_unload aarch64`; the whole string must match the board's kernel.
- `file <name>.ko`: `ELF 64-bit LSB relocatable, ARM aarch64` when `$TI_ARCH` is `arm64`.
- On the board: `lsmod | grep <name>` and the `dmesg` lines from your `module_init`.

## Troubleshooting (observed)
- `kernel tree is not built` from the script: `.config` or `autoconf.h` missing in the tree. Build `linux`
  or run the printed `modules_prepare` command.
- Release mismatch warning. Seen on an AM62P setup (example from AM62P SDK 12.02.00.01.01; yours will differ): tree `6.18.51-gaf8a51f2097d-dirty` vs board
  `6.18.51-ti-00952-gfff856a50d43-dirty`; the module built fine with vermagic
  `6.18.51-gaf8a51f2097d-dirty SMP preempt mod_unload aarch64`, which differs from the board's, so it must not be
  expected to load there. The board's `modinfo -F vermagic rpmsg_char` was
  `6.18.51-ti-00952-gfff856a50d43-dirty SMP preempt mod_unload aarch64`. (Not loaded on the board: read-only check.)
- `/lib/modules/$(uname -r)/build` does not exist on that board image: build on the host, not on the target.
- Both that board kernel and the tree had `CONFIG_MODVERSIONS` unset, so symbol CRCs are not checked; the
  vermagic string is still compared by the kernel's module loader (standard behaviour, not exercised here).
- Build errors about host tools when the devkit environment is sourced: open a clean shell.
- `cc1: error: plugin arm_ssp_per_task_plugin should be specified before ...` (observed): the module was built
  with `ARCH=arm CROSS_COMPILE=$TI_CROSS_COMPILE_R5` against the 64-bit kernel tree. Modules run only on the
  cores that run Linux, so build with `$TI_ARCH` / `$TI_CROSS_COMPILE` (what `build-module.sh` uses).
  `TI_CROSS_COMPILE_R5` (`CROSS_COMPILE_ARMV7`) is the toolchain the SDK uses for the R5 U-Boot SPL
  (`makerules/Makefile_u-boot`); R5/M4F cores run firmware (MCU+ SDK), loaded with `ti-remoteproc`.
- 32-bit SDKs (an AM335x SDK `Rules.make` has `ARCH=arm` and an `arm-none-linux-gnueabihf-` compiler) are meant
  to work the same way (the script takes arch, compiler and SDK root only from the environment); not tested,
  that SDK's kernel tree was unbuilt.
See `references/kbuild-notes.md`.
