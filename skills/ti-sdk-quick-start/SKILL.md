---
name: ti-sdk-quick-start
description: Entry point and router for TI Processor SDK Linux work. Gathers the few inputs every other skill needs (SDK path, board IP, boot medium, security mode) and sends the user through Setup, Customize, Build, Deploy, Validate by naming the skill for each phase. Use at the start of a session, or when the user says "get started", "set up my board", or is unsure which skill applies.
---

# TI SDK quick start (router)

This skill does no work itself. It collects inputs, records them in a profile, and hands off to
the skill that owns each phase. Device values are never asked: they come from the SDK
`Rules.make` through `lib/ti-sdk-env.sh` (loaded by `ti-sdk-setup`), and per-device facts come
from the generated knowledge base (`$TI_KB`, `$TI_FACTS_JSON`, made by `ti-generate-kb`).

## Docs (MCP)

Rules in [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device`, `os` and
`version` explicitly on every `ti_processor_sdk_docs_*` call; `device` comes from
`$TI_DOCS_DEVICE` (set by `lib/ti-sdk-env.sh`) or the profile `docs.device`, never the default;
`version` is `$TI_SDK_VERSION_DOCS` if `ti_processor_sdk_docs_list_versions` has it, else `latest`
(tell the user the pages may lag the SDK). Before `ti-sdk-setup` has run, use the first two calls
below to find the key; ask the user if it is ambiguous.

- `ti_processor_sdk_docs_list_variants()` - confirm the device key exists for `os=linux`.
- `ti_processor_sdk_docs_search(query="SDK overview getting started", device=$TI_DOCS_DEVICE, os="linux", version=...)`
- `ti_processor_sdk_docs_search(query="download and install the SDK", device=$TI_DOCS_DEVICE, os="linux", version=...)`
  then read the returned path and cite it.

## Prerequisites

- A Linux x86_64 host and a Processor SDK Linux installer or an installed SDK directory.
- Optional but needed to deploy and validate: a board reachable by ssh and a serial console.

## Questions to ask (keep it to these five)

Ask them together, once. Do not infer answers from directory names or earlier sessions.

1. SDK path: the installed `ti-processor-sdk-linux-*` directory (or "not installed yet").
2. Board IP for ssh/scp, or "none" (build-only session).
3. Serial console: device path (e.g. `/dev/ttyUSB0`, `COM3`), baud (default 115200), program (`screen`, `minicom`, `picocom`, `cu`), or "none".
4. Boot medium: `sd`, `emmc`, `tftp`, or `nfs`.
5. Silicon security mode: `gp`, `hs-fs`, or `hs`. The user reads it from the silicon marking or
   the board guide; if unsure, leave it open and research it with the docs MCP before choosing
   boot binaries (it decides which `tiboot3` file is used).

Record the answers in a copy of [../../templates/target-profile.yaml](../../templates/target-profile.yaml).
Profile contract (user-chosen values only; SOC, PLATFORM, ARCH, U-Boot machine, DTB prefix and
toolchain are NOT stored, they are read from the SDK):

| Key | Required | Values |
|---|---|---|
| `sdk.root` | yes | absolute SDK path |
| `board.ip`, `board.user` | no | target address, ssh user (`root` in the template) |
| `board.serial.port` | no | serial device (e.g. `/dev/ttyUSB0`, `COM3`) |
| `board.serial.baud` | no | baud rate (default `115200`) |
| `board.serial.program` | no | terminal program (`screen`, `minicom`, `picocom`, `cu`) |
| `board.boot_medium` | for deploy | `sd`, `emmc`, `tftp`, `nfs` |
| `board.security_mode` | for boot binaries | `gp`, `hs-fs`, `hs` |
| `docs.device`, `docs.version` | no | override of the MCP device key; MCP version (`latest` unless `list_versions` has the SDK version) |

## Phases and the skill that owns each

| Phase | Skill | Use it for |
|---|---|---|
| 1 Setup | `ti-sdk-setup` | install/locate SDK, host check, toolchain, env vars, MCP check |
| | `ti-generate-kb` | generate `$TI_KB` / `$TI_FACTS_JSON` (per-device facts) from the SDK; run when they are unset |
| 2 Customize | `ti-gpio-pinmux` | pin muxing and GPIO |
| | `ti-device-tree-overlay` | device tree overlays |
| | `ti-customize-clocks` | CPU frequency scaling and resume-latency constraints |
| | `ti-resource-partition` | K3 resource partitioning tool |
| | `ti-custom-board-port` | porting to a custom board |
| | `ti-yocto-custom-dt` | custom device tree in a Yocto build |
| 3 Build | `ti-build-source` | kernel, DTBs, U-Boot from SDK sources (no bitbake) |
| | `ti-yocto-build` | Yocto (bitbake) image build |
| | `ti-kernel-module` | out-of-tree kernel modules |
| | `ti-boot-chain` | rebuild or choose boot binaries (tiboot3, tispl, u-boot.img) |
| 4 Deploy | `ti-deploy-image` | SD card, eMMC, TFTP/NFS, uEnv.txt |
| | `ti-remoteproc`, `ti-pru` | run firmware on remote cores or PRUs (only if the device has them: check `$TI_KB`) |
| 5 Validate | `ti-diagnostic` | read-only health snapshot of the running board |

Run phases in order the first time: Setup, Customize, Build, Deploy, Validate. Customize is
optional; Build and Deploy repeat after each change. Pick the Build skill by path: SDK sources
(`ti-build-source`) or Yocto (`ti-yocto-build`). If a skill listed here is missing from `skills/`,
say so instead of improvising.

## Steps

1. Print nothing but the four questions; wait for the answers.
2. Write the profile. Hand `sdk.root` to `ti-sdk-setup` (it sets `TI_SDK_ROOT`).
3. After setup succeeds, say which `TI_SOC`, `TI_PLATFORM` and `TI_SDK_VERSION` were detected and
   whether `$TI_KB` exists. If not, run `ti-generate-kb` before any skill that needs device facts
   (pins, remote cores, boot files).
4. Ask which phase to start with, then invoke that skill. After Build go to Deploy, after Deploy
   go to Validate.

## Verify

- `echo "$TI_SOC $TI_SDK_VERSION $TI_DOCS_DEVICE"` is non-empty after `ti-sdk-setup`, and `[ -f "$TI_KB" ]`.
- Each phase hand-off names a skill from the table; if a skill listed there is not installed in
  `skills/`, tell the user rather than improvising its steps.

## Troubleshooting

- No SDK yet: start with step 1 of `ti-sdk-setup` (installer).
- MCP not reachable: say so; continue from the SDK on disk (Rules.make, Makefile, kernel DTS).
- Unsure which skill fits: read the `description` line of each `skills/*/SKILL.md`.
- Board misbehaves after Deploy: `ti-diagnostic`; no boot output at all: `ti-boot-chain`.
