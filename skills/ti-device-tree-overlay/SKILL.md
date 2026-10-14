---
name: ti-device-tree-overlay
description: >-
  Write, build, install and enable a device tree overlay (.dtso to .dtbo) for a TI K3
  board running the Processor SDK Linux: build with the SDK kernel tree, test-apply it
  to the board's base DTB on the host, copy it to the SD card and enable it from U-Boot
  with name_overlays in uEnv.txt. Use when enabling a daughter card, panel, camera,
  CAN/PWM/eQEP option or extra pinmux without rebuilding the base board DTB.
---

# TI device tree overlay

## Docs (MCP)
Follow [references/mcp-usage.md](references/mcp-usage.md). Always pass
`device=$TI_DOCS_DEVICE os="linux" version=$TI_SDK_VERSION_DOCS` explicitly (empty `$TI_DOCS_DEVICE`: take the key from `$TI_KB` or
`ti_processor_sdk_docs_list_variants`). If `ti_processor_sdk_docs_list_versions(device)` lacks your version (the MCP lags new SDK releases),
use `version="latest"` and say so. Cite the doc `path` you relied on.
- `ti_processor_sdk_docs_search(query="How to enable DT overlays in linux", ...)` then read it (SD card procedure).
- `ti_processor_sdk_docs_search(query="Creating the kernel fitImage for high security device", ...)` (HS-SE devices need overlays packed in the fitImage).
- `ti_processor_sdk_docs_search(query="Kernel Users Guide build dtbs", ...)`.
- Per-feature overlay pages, for example `ti_processor_sdk_docs_search(query="enable MCAN overlay", ...)`.

## Prerequisites
- Paths here are relative to this skill's directory. Shell variables do not persist between commands: run
  `source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*` (the
  bundled scripts load it themselves).
- SDK on the host and `source scripts/ti-sdk-env.sh` (`TI_SDK_ROOT`, `TI_KERNEL_SRC_DIR`, `TI_UBOOT_SRC_DIR`, `TI_DTB_PREFIX`, `TI_KB`, `TI_FACTS_JSON`).
  Per-device facts (default board DTB, pinctrl/peripheral labels, pinmux macro, shipped overlays): read `$TI_KB` / `$TI_FACTS_JSON`;
  if unset or missing, run skill `ti-generate-kb`.
- The base board DTB must be built with symbols (`-@`) so `&label` fragments resolve. The SDK does this:
  `makerules/Makefile_linux-dtbs` passes `DTC_FLAGS=-@`, and the kernel `ti/Makefile` sets `DTC_FLAGS_<base> += -@`
  for the base board. Check on the board: `ls /proc/device-tree/__symbols__ | grep <label>` (example from AM62P SDK 12.02.00.01.01; yours will
  differ: `main_pmx0`, `main_gpio1`, `main_i2c1`, `epwm0` were present).
- Overlay and base DTB must come from the same kernel tree; labels and node names change between kernels.

## Steps

### 1. Find a reference overlay
Real overlays ship in the SDK kernel: `ls $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/*.dtso`
(pick the ones matching your board name prefix; `$TI_KB` lists them per board).
Patterns seen in `k3-am62p5-sk-mcan.dtso` and `k3-am62p5-sk-rpi-hdr-ehrpwm.dtso` (example from AM62P SDK 12.02.00.01.01; yours will differ):
```dts
/dts-v1/;
/plugin/;
#include <dt-bindings/gpio/gpio.h>
#include "k3-pinctrl.h"

&{/} { /* add root-level nodes, e.g. a phy/regulator */ };
&<pinctrl-label> { <name>: <name> { pinctrl-single,pins = < <SOC>_IOPAD(...) >; }; };
&<peripheral-label> { pinctrl-names = "default"; pinctrl-0 = <&<name>>; status = "okay"; };
&<conflicting-label> { /* Conflict: <pad> */ status = "disabled"; };
```
Use the pad macro the board DTS uses (see `ti-gpio-pinmux`). Disable every node that shares a pad, as the SDK overlays do.
Label names must exist in the base DTB: `grep -n "<label>:" $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/<board>.dts*`.

### 2. Build
In-tree (recommended; same flags as the SDK): drop `<name>.dtso` into `$TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/`,
add `dtb-$(CONFIG_ARCH_K3) += <name>.dtbo` to that directory's `Makefile` (existing entries show the form,
for example `k3-am62p5-sk-mcan.dtbo` in the AM62P SDK), then from the SDK root:
```bash
make linux-dtbs        # targets are derived from KERNEL_DEVICETREE_PREFIX in Rules.make
```
`makerules/Makefile_linux-dtbs` selects `.dts`/`.dtso` files under the kernel dts tree whose path matches
`$TI_DTB_PREFIX`, so keep that prefix in the file name. Outputs: `arch/arm64/boot/dts/ti/<name>.dtbo`;
`make linux-dtbs_stage` copies them to `board-support/built-images/dtb/ti/`.

Standalone check (host, no kernel build): 
```bash
scripts/build-dtbo.sh my.dtso -o my.dtbo -b <base>.dtb
```
This runs `cpp` with the kernel include paths, `dtc -@`, then `fdtoverlay` against the base DTB; it fails if a
label or path is missing (exit status non-zero). Tested (example, AM62P SDK; other SoCs behave the same): `k3-am62p5-sk-rpi-hdr-ehrpwm.dtso` applied cleanly to the
`k3-am62p5-sk.dtb` compiled from the kernel DTS; a fragment pointing at a non-existent label failed with `FDT_ERR_NOTFOUND`. The
`unit_address_vs_reg` warning for the `gpio@23` node also appears for the unmodified SDK overlay and is benign. The script also compiled the base
board DTS of five other SoCs' SDK kernel sources without error (`build-dtbo.sh <board>.dts -o /tmp/x.dtb`).

### 3. Install on an SD card (U-Boot applies it)
Per docs page "How to enable DT overlays in linux":
1. Copy `<name>.dtbo` to `boot/dtb/ti/` of the root partition.
2. Add to `uEnv.txt` in the boot partition, space separated, paths relative to `boot/dtb/`:
   `name_overlays=ti/<overlay-1>.dtbo ti/<overlay-2>.dtbo`
3. Boot.
Evidence in the SDK U-Boot (`$TI_UBOOT_SRC_DIR/include/env/ti/mmc.env` and the SoC's `board/ti/<soc>/<soc>.env`; read yours): `envboot` loads `uEnv.txt`
from the boot partition and imports it; `get_overlay_mmc` does `fdt address ${fdtaddr}; fdt resize 0x100000;` then
for each entry of `$name_overlays` runs `load mmc ${bootpart} ${dtboaddr} ${bootdir}/dtb/${overlay} && fdt apply ${dtboaddr}`;
the K3 board env files checked (e.g. AM62A, AM62D, AM64x) use `bootdir=/boot` and `bootpart=1:2`; confirm with
`grep -n "bootdir=\|bootpart=\|name_overlays" $TI_UBOOT_SRC_DIR/board/ti/*/*.env`. Some board env files preset a default
`name_overlays` (e.g. the AM62D one does); a `uEnv.txt` value replaces it. The shipped `uEnv.txt` in
`board-support/prebuilt-images/$TI_PLATFORM/` (if present) is the place to start. On the example board checked (AM62P), `/boot/dtb/ti/` already
held the SDK-built `.dtbo` files, so only step 2 was needed for them.
FIT boot (`boot_fit=1`; required on HS-SE): U-Boot instead builds `#overlay` suffixes from `name_overlays`
(`get_overlaystring` in `$TI_UBOOT_SRC_DIR/include/configs/ti_armv7_common.h`); the overlays must be packed into `fitImage`
(docs query "Creating the kernel fitImage for high security device").

## Verify
1. Host: `build-dtbo.sh ... -b base.dtb` prints `OK`. Inspect the merged result:
   `fdtoverlay -i base.dtb -o /tmp/m.dtb my.dtbo && dtc -I dtb -O dts /tmp/m.dtb | grep -n "<node or label>"`
   (`dtc` and `fdtoverlay` are in `$TI_KERNEL_SRC_DIR/scripts/dtc/` and in the SDK devkit's host `usr/bin`).
2. Target: node is live under `/proc/device-tree/...` and
   `status` reads `okay`; for pinmux changes use `ti-gpio-pinmux` (`pinmux-pins` owner).

## Troubleshooting (verified)
- `Failed to apply '<x>.dtbo': FDT_ERR_NOTFOUND` (host): the overlay references a label/path missing in that base DTB.
- Overlay silently not applied: `name_overlays` entries are looked up under `${bootdir}/dtb/` of `${bootpart}`
  (root partition), not the FAT boot partition; keep the `ti/` prefix.
- Labels not found by `dtc` at overlay build time is normal (resolved at apply time); `-@` on the base is what matters.
- Not covered: runtime (configfs) overlay loading. Example from the AM62P board checked: `CONFIG_OF_OVERLAY=y` but `/sys/kernel/config/device-tree` did not exist
  (no `CONFIG_OF_CONFIGFS`), so U-Boot-time overlays are the supported path there. Docs query: "device tree overlay configfs".
