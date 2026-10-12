---
name: ti-generate-kb
description: Generate or refresh the per-platform knowledge base (cores and firmware names, reserved memory, OPPs, IOPAD macros, GPIO, overlays, boot files, component versions) from the installed TI Processor SDK sources. Use after installing the skills, when the SDK or kernel changed, when $TI_KB is missing or stale, or when a skill needs device facts.
---

# Generate the platform knowledge base

Device facts are never hand-written. `lib/gen-sdk-facts.py` reads the installed SDK and writes
`<platform>.md` and `<platform>.json`. Re-run it whenever the sources change.

## Docs (MCP)

Follow [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device`, `os`, `version` explicitly.
The KB holds what the SDK contains. Use the docs to check meaning or procedure, not to fill KB gaps.

- `ti_processor_sdk_docs_search(query="IPC remoteproc firmware file names", device=$TI_DOCS_DEVICE, os="linux", version="latest")`
- `ti_processor_sdk_docs_search(query="device tree overlays", device=$TI_DOCS_DEVICE, os="linux", version="latest")`

If the docs and the KB disagree (for example a reserved-memory size), report both. The KB reflects the
installed kernel DTS; the docs page may describe another release.

## Prerequisites

- An installed SDK (`Rules.make` plus `board-support/`), found by `lib/ti-sdk-env.sh`.
- `python3` (stdlib only), `make`, host `cpp` and `dtc`. If `dtc` is not on the host the generator
  tries the SDK `linux-devkit` host sysroot and the kernel `scripts/dtc/dtc`. If none exists it skips the
  device-tree sections and lists them under "Skipped sections" in the header. Install `device-tree-compiler`
  and re-run to fill them.

## Steps

1. Load the environment: `source lib/ti-sdk-env.sh` (from the installed `.claude/lib/`).
2. Generate:
   ```bash
   python3 .claude/lib/gen-sdk-facts.py      # installed workspace; in a repo checkout: python3 lib/gen-sdk-facts.py
   ```
   Defaults: `--sdk-root $TI_SDK_ROOT`, `--out-dir $TI_FACTS_DIR`, `--format md,json`.
   Options: `--kernel-dir DIR`, `--dts FILE` (override the board DTS, for example to inspect another
   board or a patched DTS), `--name STEM` (output file name).
3. Reload: `source lib/ti-sdk-env.sh` again so `$TI_KB` and `$TI_FACTS_JSON` point at the new files.
4. Read `$TI_KB`. Sections: build configuration (`Rules.make`), component versions, boot files
   (security-mode variants, which variant `tiboot3.bin` is byte-identical to), board DTS and how it was
   selected, remote processors (status, `firmware-name`, memory regions, `bootph-*`), reserved memory,
   OPP tables, pinmux (IOPAD macros the board DTS uses, pinctrl nodes), GPIO controllers, overlay
   sources, `k3-respart-tool` outputs, `bin/` helpers, top-level make targets. Each lists evidence
   (`file:line` or path). "not found" means the SDK does not contain it; do not guess.

## How other skills consume it

- Human-readable: read `$TI_KB` (Markdown). Cite its evidence lines.
- Scripts and agents: parse `$TI_FACTS_JSON`. Layout: `meta{generated, generator, sdk_root, sdk_version, platform, skipped_sections[]}`
  and `sections.<key>{title, found, data, evidence[], note}`. Keys: `rules`, `components`, `boot_files`,
  `dt_identity`, `remoteprocs`, `reserved_memory`, `opp`, `pinmux`, `gpio`, `overlays`, `respart`, `bin`, `make_targets`.
  Example: `jq '.sections.remoteprocs.data[] | {node, firmware_name, status}' "$TI_FACTS_JSON"`.
- If `$TI_KB` is unset or the file is missing, run this skill first. Do not copy facts between platforms.

## Board DTS selection rule

First existing kernel `.dts` among: basename of `MKIMAGE_DTB_FILE` in `Rules.make`; the stem equal to
`PLATFORM`; each `KERNEL_DEVICETREE_PREFIX` alternative as an exact stem; else the shortest shipped DTB name
under the first prefix. `--dts` overrides. The chosen rule is written in the KB. If it picked the wrong
board, re-run with `--dts <kernel>/arch/.../<board>.dts --name <platform>`.

## When to re-run

- New SDK installed, or `Rules.make` changed.
- The kernel tree under `board-support/ti-linux-kernel-*` was patched or rebased.
- Device-tree or overlay edits you want reflected (the KB reads source `.dts`, not the running board).
- `meta.generated` is older than the kernel or manifest.

## Verify

- `ls "$TI_FACTS_DIR"` shows `<platform>.md` and `<platform>.json`; the header has the date, SDK path and
  version, and "do not edit".
- `python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["meta"]["skipped_sections"])' "$TI_FACTS_JSON"` prints `[]`.
- On a live board, spot-check: `/proc/device-tree/model` equals the KB model; `head /sys/class/remoteproc/*/name`
  matches the core nodes whose status is `okay`; `cpufreq` frequencies match the CPU OPP table (a silicon
  speed grade may hide higher OPPs through `opp-supported-hw`).
- Manual test: `tests/test_gen_facts.sh` (needs an SDK).

## Troubleshooting

- "skipped: host cpp not found" / "dtc not found": install `gcc` (cpp) and `device-tree-compiler`, re-run.
- "cpp failed": the DTS includes a header missing from the kernel tree. Pass `--kernel-dir` explicitly.
- Wrong board chosen: use `--dts` (see selection rule).
- A core shows `reserved`: Linux does not manage it (for example the HSM M4F). A core with status `okay`
  that is loaded by the boot chain (the device-manager core) attaches instead of booting: the DTS does not
  say which; check the boot files section and the docs IPC page.
- Non-K3 or legacy SDK (for example AM335x): sections that do not apply read "not found". That is expected.
- `$TI_DOCS_DEVICE` is derived from `PLATFORM` (see `lib/ti-sdk-env.sh`). If the MCP has no such key, ask the
  user and use `ti_processor_sdk_docs_list_variants`.
