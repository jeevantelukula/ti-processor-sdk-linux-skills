---
name: ti-diagnostic
description: Read-only health snapshot of a running TI K3 board (identity, kernel, memory, thermal, cpufreq, remoteproc, disks, failed units, dmesg errors) as JSON. Use to validate a deployment or to start debugging a board.
---

# ti-diagnostic

Collect a read-only JSON snapshot from the target, then interpret it. Nothing is modified.

## Docs (MCP)

Follow [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`,
`version=$TI_SDK_VERSION_DOCS` (or `"latest"` when `ti_processor_sdk_docs_list_versions` lacks it; the MCP
lags the SDK, so treat pages as guidance and the snapshot as the fact). Search by symptom, then read the hit:
- `ti_processor_sdk_docs_search(query="remoteproc firmware load failure", device=$TI_DOCS_DEVICE, os="linux", version=<ver>)`
- `ti_processor_sdk_docs_search(query="voltage thermal management VTM", ...)` (example path:
  `linux/Foundational_Components/Kernel/Kernel_Drivers/VTM.html`)
- `ti_processor_sdk_docs_search(query="DFS cpufreq governors", ...)`; see also `ti-customize-clocks`
- Expected remoteproc cores and firmware names for this SDK: `ti-remoteproc`, or the generated KB (`$TI_KB`).

## Prerequisites

- Target booted to Linux, reachable by ssh (`board.ip` in the target profile) or a local shell on it.
- `bash` on the target. No `jq` or `python3` needed on the target.

## Steps

1. Run from the host: `ssh root@<ip> 'bash -s' < scripts/snapshot.sh > snapshot.json`
   (or run `scripts/snapshot.sh` on the target).
2. Validate: `python3 -m json.tool snapshot.json`.
3. Read the fields (`references/sample-output.json` is an example from an AM62P5 SK, SDK 12.02.00.01.01; yours will differ):

| Field | Source | Look for |
|---|---|---|
| `board.model`, `board.compatible` | `/proc/device-tree/{model,compatible}` | Matches the board and DTB you deployed |
| `kernel`, `cmdline` | `uname -r`, `/proc/cmdline` | Expected kernel and root device |
| `memory_kb` | `/proc/meminfo` | Low `available`, low `cma_free` |
| `thermal[]` | `/sys/class/thermal/thermal_zone*` | Zone names, count and sensors are SoC/board specific; temperatures in millicelsius (`null` = unreadable) |
| `cpufreq[]` | `/sys/devices/system/cpu/cpu*/cpufreq` | One entry per CPU that has `cpufreq/`; governor and the OPPs offered |
| `remoteproc[]` | `/sys/class/remoteproc/remoteproc*` | `state` of each core, firmware name |
| `disks[]` | `df -kP` | Near-full root or boot partitions (only `/dev/*` filesystems are listed; NFS root does not appear) |
| `failed_units[]` | `systemctl --failed` | Any entry |
| `dmesg_errors[]` | `dmesg` filtered for error/fail/timeout/oops/panic | Driver probe failures |

## Verify

The command exits 0 and `json.tool` parses the output. Empty arrays mean the subsystem is absent or not
exposed, not healthy. Output is ASCII only (control and non-ASCII bytes are dropped) so it always parses.
The script reads only `/proc`, `/sys`, `df`, `uname`, `systemctl --failed` and `dmesg`; it writes nothing.

## Troubleshooting

- `remoteproc` shows `state: attached` with firmware `unknown` (example: the AM62P WKUP R5F): the core was
  started by the bootloader and Linux attached to it. Check with `ti-remoteproc` whether that core is expected
  on your SoC before calling it healthy.
- Empty `thermal` or `cpufreq`: driver not built or not probed; check `dmesg_errors` and the kernel config.
- `dmesg_errors` lists lines matching a loose pattern; benign hits happen (e.g. a systemd condition message
  containing "Fail"). Judge each line against the docs, do not treat the count as a score.
- `dmesg` empty: `kernel.dmesg_restrict` may be set; run as root.
