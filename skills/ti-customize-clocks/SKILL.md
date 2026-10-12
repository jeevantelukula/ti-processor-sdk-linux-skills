---
name: ti-customize-clocks
description: Inspect and change CPU frequency scaling (cpufreq sysfs, governors, the A53 OPP table in the kernel DTS) and set LPM resume-latency constraints (pm_qos_resume_latency_us) on a K3 Processor SDK Linux target. Use when the user asks about CPU frequency, governors, OPPs, disabling or limiting an OPP, DVFS, or which low power mode the SoC enters.
---

# CPU frequency, OPPs and LPM constraints

Scope: cpufreq sysfs, the OPP table in the SDK kernel DTS, and the LPM resume-latency constraint.
Not covered: GPU/VPU devfreq tuning, clock tree changes, spread spectrum, custom voltages. There is
no procedure for those here; point the user to the docs and the TRM instead of inventing one.

All frequencies, masks, node names and file names below come from run-time commands. Values shown
as "example" were read on an AM62P SK with SDK 12.02.00.01.01; yours will differ.

## Docs (MCP)

Follow [../../context/mcp-usage.md](../../context/mcp-usage.md). Always pass `device`, `os`, `version`
explicitly: `device=$TI_DOCS_DEVICE`, `os="linux"`, `version=$TI_SDK_VERSION_DOCS` if
`ti_processor_sdk_docs_list_versions` lists it, else `"latest"` (the MCP lags the SDK: say so and
compare the page with the DTS on disk; the SDK wins for values).

- DFS: `ti_processor_sdk_docs_search(query="DFS cpufreq governors operating points", device=$TI_DOCS_DEVICE, os="linux", version=<ver>)`,
  then read the hit. Example path (AM62PX, latest): `linux/Foundational_Components/Power_Management/pm_dfs.html`.
  If search returns no DFS page for the device, cpufreq is probably not supported on it (see Prerequisites).
- LPM: `ti_processor_sdk_docs_search(query="LPM constraints pm_qos_resume_latency_us low power modes", ...)`,
  then read the S/W architecture and Low Power Modes pages (example paths: `.../Power_Management/pm_sw_arch.html`,
  `.../pm_low_power_modes.html`). The mode list in those pages is device specific; read the one for your device.

## Prerequisites

- Target running the SDK Linux image. Check `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver`
  (example: `cpufreq-dt`). No `cpufreq` directory means no DVFS on this SoC or the driver is not bound.
- Whether the SoC has an A53 OPP table is a DTS fact, check it before promising cpufreq control:
  ```
  source <skills-root>/lib/ti-sdk-env.sh      # TI_SDK_ROOT, TI_KERNEL_SRC_DIR, TI_DTB_PREFIX, TI_DOCS_DEVICE
  DTS=$TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti
  grep -ln 'operating-points-v2-ti-cpu' "$DTS"/*.dtsi    # SoC dtsi that defines the CPU OPP table
  ```
  Example (SDK 12.02.00.01.01; re-run on yours): the grep finds the table in the dtsi of the AM62P,
  AM62x, AM62A (AM62D inherits it) and AM62L families, all with label `a53_opp_table`, and finds
  nothing for the AM64x family, which has no CPU OPP table. If yours finds nothing, cpufreq scaling
  does not apply; say so.
- Per-device facts: read the generated KB (`$TI_KB`, regenerate with `ti-generate-kb`) first; if it is
  absent, derive from the SDK DTS with the commands below.
- For OPP edits: SDK kernel source, built via `ti-build-source`.

## Steps

### 1. Read current cpufreq state (target)

```
cd /sys/devices/system/cpu/cpu0/cpufreq
cat scaling_driver scaling_governor scaling_available_governors \
    scaling_available_frequencies scaling_cur_freq scaling_min_freq scaling_max_freq \
    cpuinfo_transition_latency
cat related_cpus          # CPUs sharing this policy (opp-shared)
```

Example (AM62P5 SK): driver `cpufreq-dt`, governor `performance`, governors `ondemand userspace performance`,
frequencies `200000 ... 1400000` kHz, 4 cores in one policy. `ti-diagnostic` collects the same fields.

### 2. Governors (docs: DFS page)

Docs list ondemand, conservative, performance, powersave, userspace, schedutil; the kernel builds
`performance`, `ondemand`, `userspace` in and `conservative`, `powersave` as modules, default
`performance`. Use only what `scaling_available_governors` shows.

```
echo ondemand > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo userspace > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo <kHz from scaling_available_frequencies> > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed   # userspace only
```

The docs write the `scaling_setspeed` example in Hz (`1000000000`); the sysfs unit is kHz, so use a
value from `scaling_available_frequencies`.

### 3. Find the real OPP table (host, SDK kernel tree)

```
cd "$DTS"
F=$(grep -ln 'operating-points-v2-ti-cpu' *.dtsi)        # SoC dtsi, e.g. k3-am62p5.dtsi
grep -n 'opp-[0-9]* {\|opp-supported-hw\|opp-suspend\|syscon\|ti,soc-info' $F
grep -n 'opp-table\|a53_opp_table' <board>.dts           # board-level additions
```

`<board>.dts` is the board your deployed DTB is built from (`cat /proc/device-tree/model`, or the
DTB names under `$TI_SDK_ROOT/board-support/built-images/`, filtered by `$TI_DTB_PREFIX`).
Authoritative merged result: decompile the DTB you deploy,
`dtc -I dtb -O dts <dtb> | sed -n '/opp-table {/,/^\t};/p'`, or on the target
`ls /proc/device-tree/opp-table*`.

Facts to apply, all verified in the SDK 12.02.00.01.01 kernel DTS (re-verify on your SDK):
- Each OPP node has `opp-hz`, `opp-supported-hw = <0x01 mask>` and `clock-latency-ns`. The mask is matched
  against the efuse (`syscon = <&opp_efuse_table>`, `ti,soc-info`), so the speed grade decides which OPPs
  appear. The masks differ per SoC (e.g. in this SDK the 1000 MHz OPP is `0x0007` on AM62P, `0x0006` on
  AM62x and AM62A, `0x0002` on AM62L). Do not edit masks.
- The top OPP is often added by the board DTS as a root `opp-table { opp-<hz> { ... }; };` node that
  merges into the SoC table; the board file comments the required rail (example: "Requires VDD_CORE
  at 0v85" for 1400 MHz on the AM62P SK, e.g.). A board without that node, or with a lower mask, stops below it.
- Example (AM62P, `k3-am62p5.dtsi` + `k3-am62p5-sk.dts`): OPPs 200, 400, 600, 800, 1000, 1250 MHz
  (1250 has `opp-suspend`) plus 1400 MHz from the board file. The docs page shows older masks and
  `syscon = <&wkup_conf>`; the SDK DTS is authoritative, report both if asked.
- Other tables exist, such as the VPU table (label `vpu_opp_table`) on SoCs with a VPU; they are not
  CPU OPPs.

### 4. Limit or disable an OPP (docs: DFS page)

Docs: add `status = "disabled";` to the OPP node. Using the `a53_opp_table` label (present on the
SoCs listed in Prerequisites; confirm with the grep above), for an OPP that exists in your table:

```
&a53_opp_table {
	opp-<hz> {                /* a node name listed by step 3 */
		status = "disabled";
	};
};
```

Put it in the board DTS or a dedicated DTS/overlay (`ti-device-tree-overlay`), rebuild DTBs and deploy
(`ti-build-source`, `ti-deploy-image`). Runtime alternative without DT changes: write
`scaling_max_freq` / `scaling_min_freq` (kHz) under `cpufreq/`. Changing voltages, adding frequencies
or other clock edits are not documented here; ask the user and point to the docs plus the TRM.

## Generic Example: Disable Top OPP via DTBO Overlay

```dts
/dts-v1/;
/plugin/;

&a53_opp_table {
	/* Disable highest OPP - check board DTS for voltage requirements */
	opp-<highest-hz> {
		status = "disabled";
	};
};
```

Build (host):
```bash
source lib/ti-sdk-env.sh
bash skills/ti-device-tree-overlay/scripts/build-dtbo.sh disable-top-opp.dtso \
    -o disable-top-opp.dtbo \
    -b "$TI_SDK_ROOT/board-support/built-images/dtb/ti/<board>.dtb"
```

Deploy (target):
```bash
scp disable-top-opp.dtbo root@<board>:/boot/dtb/ti/
ssh root@<board> 'echo "name_overlays=ti/disable-top-opp.dtbo" >> /run/media/boot-mmcblk1p1/uEnv.txt'
ssh root@<board> reboot
```

Verify (target):
```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
# Expected: highest frequency removed from list
```

### 5. LPM resume-latency constraint (docs: S/W architecture of system suspend, Low Power Modes)

```
echo 100000 > /sys/devices/system/cpu/cpu0/power/pm_qos_resume_latency_us   # 100 ms, any CPU
echo 0      > /sys/devices/system/cpu/cpu0/power/pm_qos_resume_latency_us   # clear
```

Docs: default is no constraint (deepest mode); the DM firmware clears constraints at resume, so set
it again before each suspend. 100 ms is the docs example for entering MCU Only mode
(`rtcwake -s 5 -m mem`; example page: AM62P). Device constraints are placed automatically for
wakeup-enabled devices. Documented limits: RT Linux supports no low power modes; kernel 6.6 with DM
firmware < 10.0 always enters DeepSleep. The latency-to-mode table is in the TISCI docs linked from
the S/W architecture page. Which modes exist depends on the SoC and firmware; do not assume.

## Verify

- `cat scaling_available_frequencies` no longer lists a disabled OPP after reboot with the new DTB.
- `ls /proc/device-tree/opp-table*` lists the OPP nodes (a disabled node carries a `status` property).
- Governor: `cat scaling_governor`; with `userspace`, `scaling_cur_freq` equals the value written.
- Constraint: `cat /sys/devices/system/cpu/cpu0/power/pm_qos_resume_latency_us`, then
  `dmesg | grep -i "latency"`; docs show `ti_sci_suspend: sending max CPU latency=100` on suspend.

## Troubleshooting

- Fewer frequencies than the DTS lists: `opp-supported-hw` filters by the efuse speed grade.
- Top frequency missing: it is added only by the board DTS (step 3) and may need a higher core voltage.
- `conservative`/`powersave` missing: modules per docs; load them or change the kernel config.
- `scaling_setspeed` has no effect: governor must be `userspace`.
- Constraint seems ignored after resume: DM clears it at resume; set it before each suspend.
- No `cpufreq` directory: no OPP table for this SoC (step "Prerequisites") or `cpufreq-dt` not bound;
  check `dmesg | grep -i cpufreq` and the kernel config (docs: Generic DT based cpufreq driver, Texas
  Instruments CPUFreq support).
