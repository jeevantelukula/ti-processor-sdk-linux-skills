---
name: ti-sdk-setup
description: Install or locate a TI Processor SDK Linux tree, check the build host, load device values (SOC, PLATFORM, toolchain, U-Boot machines) from the SDK Rules.make into the shell, and confirm the docs MCP works. Use first in any session, when the user mentions installing the SDK, SDK path, toolchain, Rules.make, host requirements, or before ti-build-source / ti-deploy-image.
---

# SDK setup and environment

Generic for every SDK built on the TI top-level Makefile + `Rules.make` layout. Device values
come from the SDK, never from this file.

## Docs (MCP)

Follow [references/mcp-usage.md](references/mcp-usage.md): always pass `device`, `os` and
`version` explicitly (never the defaults). `device` is `$TI_DOCS_DEVICE`, `os` is `linux`,
`version` is `$TI_SDK_VERSION_DOCS` if `ti_processor_sdk_docs_list_versions(device=$TI_DOCS_DEVICE)`
lists it, else `latest` (MCP lags the SDK: say so). Where a page and the SDK disagree, the SDK wins; report both.

- `ti_processor_sdk_docs_search(query="download and install the SDK installer", device=$TI_DOCS_DEVICE, os="linux", version=...)`
  then read the path the search returns; this page is device-specific (example from the AM62P search:
  `.../AM62PX/linux/Overview/Download_and_Install_the_SDK.html`; yours will differ).
- `query="SDK build using Makefile Rules.make variables"`, then read `linux/Overview/Top_Level_Makefile.html`.
- `query="kernel users guide cross compile environment"`.
Cite the page path you used when you pass on a command.

## Prerequisites

- Paths here are relative to this skill's directory. Shell variables do not persist between commands: run
  `source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*` (the
  bundled scripts load it themselves).
- x86_64 Linux host. The SDK's `bin/setup-host-check.sh` only accepts Ubuntu 22.04 and exits 1
  otherwise (read from the script; it tests the `lsb_release` codename against `jammy`). Docs: the SDK is built and tested on 22.04, other
  distributions are not blocked by the docs but are untested.
- Either the SDK is already installed, or you have the installer
  `ti-processor-sdk-linux-<machine>-<version>-Linux-x86-Install.bin` (name pattern from the docs).
- `make` (the env library evaluates `Rules.make` with it; it falls back to text parsing without it).

## Steps

1. Install, if needed. Docs: install `file fdisk dosfstools`, then
   ```bash
   chmod +x ./ti-processor-sdk-linux-<machine>-<version>-Linux-x86-Install.bin
   ./ti-processor-sdk-linux-<machine>-<version>-Linux-x86-Install.bin
   ```
   The installer keeps working about a minute after it shows 100% (docs). A TI Ubuntu 22.04
   container image on ghcr.io/texasinstruments is the documented alternative
   (check docs: `run SDK installer inside a container`).
   The installer's own options are not documented in the pages used here; do not invent flags.

2. Optional host helpers, run from the SDK root. `setup.sh` is interactive and, from reading
   it, prompts in turn for: host packages (`bin/setup-package-install.sh`), NFS rootfs
   (`bin/setup-targetfs-nfs.sh`), TFTP (`bin/setup-tftp.sh`), minicom (`bin/setup-minicom.sh`),
   U-Boot env (`bin/setup-uboot-env.sh`). Each prompt can be skipped. They call `sudo`.
   ```bash
   cd "$TI_SDK_ROOT" && ./setup.sh
   ```
   The network ones (TFTP, NFS, U-Boot env) are covered by the `ti-deploy-image` skill.

3. Load device values from the SDK (source it; do not execute it):
   ```bash
   export TI_SDK_ROOT=/path/to/ti-processor-sdk-linux-<machine>-<version>   # or cd into the SDK
   source scripts/ti-sdk-env.sh
   ```
   Discovery order: `$TI_SDK_ROOT`, `$PROCESSOR_SDK_LINUX`, then the cwd and its parents.
   Exports: `TI_SOC TI_PLATFORM TI_ARCH TI_UBOOT_MACHINE TI_UBOOT_MACHINE_R5 TI_DTB_PREFIX
   TI_CROSS_COMPILE TI_CROSS_COMPILE_R5 TI_KERNEL_SRC_DIR TI_UBOOT_SRC_DIR TI_SDK_VERSION
   TI_SDK_VERSION_DOCS TI_KERNEL_VERSION TI_DOCS_DEVICE TI_FACTS_DIR TI_KB TI_FACTS_JSON`. Field
   meanings and sources: [references/env-variables.md](references/env-variables.md).
   Per-device facts (boot files, DT identity, remote cores, make targets) are in `$TI_KB` (markdown)
   and `$TI_FACTS_JSON`. If the library warns `no generated facts`, `TI_KB` is empty: run the skill
   `ti-generate-kb`, then re-source. If it warns it cannot derive the docs device key, ask the user
   and confirm with `ti_processor_sdk_docs_list_variants`.

4. Run the host and toolchain check:
   ```bash
   scripts/check-sdk.sh [SDK_ROOT]
   ```
   It runs `bin/setup-host-check.sh`, executes `${CROSS_COMPILE}gcc --version` for the A-core and
   (when `CROSS_COMPILE_ARMV7` exists) R5 toolchains, and checks `make gcc bison flex bc mkimage
   swig python3` plus the python modules the docs list for binman (`jsonschema pyelftools PyYAML
   Mako`). Install what is missing with the docs package list:
   ```bash
   sudo apt-get install build-essential autoconf automake bison flex libgnutls28-dev libmpc-dev \
        libmpcdec6 libmpc3 libmpcdec-dev libssl-dev bc u-boot-tools swig python3 python3-pip
   pip3 install jsonschema pyelftools PyYAML Mako yamllint
   ```

5. Confirm the docs MCP works and matches the SDK:
   - `ti_processor_sdk_docs_list_variants()` must contain `device=$TI_DOCS_DEVICE`, `os=linux`
     (otherwise ask the user for the key; do not guess).
   - `ti_processor_sdk_docs_list_versions(device=$TI_DOCS_DEVICE)`: if `$TI_SDK_VERSION_DOCS` is
     missing, the MCP lags the SDK. Use `version="latest"` and tell the user pages may differ.
   - If the MCP is unreachable, say so and rely on the SDK on disk (Rules.make, Makefile).

6. Record the answers for the other skills (SDK path, board IP, boot medium, security mode) in
   the workspace profile `.claude/target-profile.yaml` (user-chosen values only; create it from
   [assets/target-profile.yaml](assets/target-profile.yaml) if it does not exist).

## Verify

- `check-sdk.sh` prints `RESULT: OK` and exit status 0.
- `echo "$TI_SOC $TI_PLATFORM $TI_SDK_VERSION"` is non-empty and matches the SDK directory name.
- `[ -f "$TI_KB" ] && echo KB ok`; otherwise run `ti-generate-kb`.
- Build tools do not need `linux-devkit/environment-setup` sourced. Docs: do NOT source an
  `environment-setup` script when calling the top-level Makefile or building the kernel; it
  breaks host-side tools.

## Troubleshooting (from SDK/docs only)

- `Unsupported host Linux. Only Ubuntu 22.04 LTS is supported`: message of
  `bin/setup-host-check.sh` on any other distribution (codename other than `jammy`). The docs say
  other distributions are not blocked, only untested: for those, skip the SDK check and rely on the
  package list in step 4.
- `ti-sdk-env: could not evaluate Rules.make with make`: install `make`; values are then read
  as plain text and `$(...)` references stay unexpanded.
- `Rules.make` contains the install path in `TI_SDK_PATH?=`. If the SDK directory was moved,
  the env library overrides it with the discovered root; the top-level Makefile does not, so run
  `make TI_SDK_PATH=$TI_SDK_ROOT <target>` (command-line values override `?=`).
