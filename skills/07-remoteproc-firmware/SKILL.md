---
name: remoteproc-firmware
version: "1.0.0"
description: >
  Load MCU+ SDK firmware onto the M4F or R5F remote core from Linux using
  the remoteproc framework. Covers resource table requirement, SysConfig
  IPC setup, linker.cmd DDR placement, /lib/firmware symlink, and reading
  remote core debug logs.
tags: [remoteproc, m4f, r5f, firmware, ipc, rpmsg, multicore, am62x, am64x]
related_context:
  - context/k3-architecture.md
references:
  - https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1193620/faq-am62x-am64x-how-to-allow-linux-to-load-m4f-r5f-firmware-by-adding-a-resource-table
  - https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
---

# Skill: Remote Core Firmware Loading (M4F / R5F)

## Overview

Linux uses the `remoteproc` framework to load and manage firmware on the M4F
(AM62x) or R5F (AM64x) cores. The key requirement that trips up most users:
**the firmware binary must contain a resource table** — a data structure the
remoteproc driver parses before loading. Without it, Linux silently refuses to
load the firmware.

This skill covers both the minimal path (empty resource table, no IPC) and
the full path (RPMsg IPC between Linux A53 and M4F/R5F).

## Prerequisites

- MCU+ SDK installed for the target SoC (https://www.ti.com/tool/MCU-PLUS-SDK-AM62X)
- CCS (Code Composer Studio) or MCU+ SDK build environment for building firmware
- Linux kernel with `remoteproc` and `rpmsg` enabled (default in TI kernel config)
- Root access on the target Linux board

## How remoteproc Works on AM62x

```
Linux (A53)                   MCU Subsystem
    │                              │
    │  1. Write firmware path      │
    │  > /sys/class/remoteproc/    │
    │    remoteproc0/firmware      │
    │                              │
    │  2. Trigger start            │
    │  > .../state = "start"       │
    │                              │
    │  3. Kernel reads /lib/firmware/<name>
    │     Parses resource table    │
    │     Copies binary to DDR ───►│  M4F boots from DDR
    │                              │  Firmware runs
    │  4. RPMsg channels open      │
    │  /dev/rpmsg0, /dev/rpmsg1    │◄── firmware sends messages
```

## Step 1: Add a Resource Table to Your MCU+ Firmware

The resource table is a C struct that tells remoteproc where the firmware's
memory sections live and what IPC channels it wants.

### Option A: Enable Linux IPC in SysConfig (recommended — includes RPMsg)

Open your MCU+ project's `.syscfg` file in CCS SysConfig editor:
1. Under **IPC** → Enable `Linux A53 IPC RP Message`
2. This auto-generates a resource table and RPMsg transport layer

Then update `linker.cmd` to place the resource table in DDR at the start of the
remote core's DDR allocation. Reference the IPC RPMsg echo example:
```
<mcu-plus-sdk>/examples/drivers/ipc/ipc_rpmsg_echo_linux/am62x-sk/m4fss0-0_freertos/ti-arm-clang/linker.cmd
```

The critical linker change — map resource table at DDR start:
```
SECTIONS {
    .resource_table : {
        __RESOURCE_TABLE_START = .;
        *(.resource_table)
        __RESOURCE_TABLE_END = .;
    } > DDR_0    /* Must be first section in DDR */
}
```

### Option B: Minimal empty resource table (no RPMsg, saves ~4 KB code space)

If you only want Linux to load the firmware (no IPC needed):

Add to your project (create `resource_table_empty.h`):
```c
/* resource_table_empty.h — minimal resource table for remoteproc loading */
#include <stdint.h>

#define RPMSG_VDEV_FEATURES  (1 << 0)

struct resource_table_0 {
    uint32_t ver;
    uint32_t num;
    uint32_t reserved[2];
};

__attribute__((section(".resource_table")))
struct resource_table_0 ti_resource_table = {
    .ver = 1,
    .num = 0,         /* zero entries = no IPC channels */
    .reserved = {0, 0},
};
```

In `linker.cmd`, add `.resource_table` to DDR section (must be at DDR start):
```
.resource_table > DDR_0
```

Also enable memory log in SysConfig to allow Linux to read debug prints:
Debug Log → Enable Memory Log = checked.

### Option C: Apply TI's reference patch (quickest for hello_world project)

TI provides ready-made patches for the MCU+ hello_world project:
- Approach 2A (no IPC, with debug logs): patches available in E2E FAQ thread 1193620
- Approach 2B (no IPC, no logs, minimal footprint): also in the same FAQ

## Step 2: Build the Firmware

```bash
# In MCU+ SDK project directory (from Linux terminal):
make -s -C examples/drivers/ipc/ipc_rpmsg_echo_linux/am62x-sk/m4fss0-0_freertos/ti-arm-clang/ clean
make -s -C examples/drivers/ipc/ipc_rpmsg_echo_linux/am62x-sk/m4fss0-0_freertos/ti-arm-clang/

# Output binary:
# examples/.../m4fss0-0_freertos/ti-arm-clang/ipc_rpmsg_echo_linux.release.out
```

## Step 3: Copy Firmware to Target

```bash
# Copy the .out file to the target /lib/firmware/
scp your_firmware.release.out root@<board-ip>:/lib/firmware/am62-mcu-m4f0_0-fw

# The firmware file name must match what the device tree expects.
# Check the DT node:
#   board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/k3-am62.dtsi
# Look for: mcu_m4fss0_0 { firmware-name = "am62-mcu-m4f0_0-fw"; }
```

## Step 4: Load the Firmware via remoteproc

```bash
# On target — find the remoteproc entry for M4F:
ls /sys/class/remoteproc/

# Typically: remoteproc0 = M4F core
cat /sys/class/remoteproc/remoteproc0/name
# Expected: mcu-m4fss0-0

# Verify firmware file is present:
ls /lib/firmware/am62-mcu-m4f0_0-fw

# Start the remote core:
echo "am62-mcu-m4f0_0-fw" > /sys/class/remoteproc/remoteproc0/firmware
echo start > /sys/class/remoteproc/remoteproc0/state

# Check status:
cat /sys/class/remoteproc/remoteproc0/state
# Expected: "running"
```

## Step 5: Communicate via RPMsg (if IPC was enabled)

```bash
# RPMsg channels appear as /dev/rpmsg* after firmware starts
ls /dev/rpmsg*

# Echo test using the rpmsg_char example (if compiled into image):
# Or use the TI rpmsg-char userspace library

# Simple echo test via character device:
cat /dev/rpmsg0 &           # read in background
echo "hello m4f" > /dev/rpmsg0
```

## Step 6: Read Remote Core Debug Logs

If "Enable Memory Log" was selected in SysConfig:
```bash
# After firmware is running, trace log appears at:
cat /sys/kernel/debug/remoteproc/remoteproc0/trace0
```

## Validation

```bash
# 1. Firmware loaded successfully:
cat /sys/class/remoteproc/remoteproc0/state
# → "running"

# 2. No error in dmesg:
dmesg | grep -i "remoteproc\|m4f\|mcu"
# Should NOT show "bad elf magic" or "resource table not found"

# 3. If IPC enabled — RPMsg device appears:
ls /dev/rpmsg*
# → /dev/rpmsg0 (or similar)

# 4. Trace log readable:
cat /sys/kernel/debug/remoteproc/remoteproc0/trace0
# → "Hello from M4F!" (or whatever your firmware prints)
```

## Stopping and Reloading Firmware

```bash
# Stop the remote core:
echo stop > /sys/class/remoteproc/remoteproc0/state

# Load different firmware:
echo "new-firmware-name" > /sys/class/remoteproc/remoteproc0/firmware
echo start > /sys/class/remoteproc/remoteproc0/state
```

## Automatic Load at Boot (persistent)

The DM firmware device tree node specifies the default firmware name. For
custom firmware loaded every boot, create a udev rule or systemd service:

```bash
# /etc/systemd/system/m4f-firmware.service
[Unit]
Description=Load M4F firmware
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo my-firmware > /sys/class/remoteproc/remoteproc0/firmware && echo start > /sys/class/remoteproc/remoteproc0/state'

[Install]
WantedBy=multi-user.target
```

Or simply place the firmware at the name specified in the DT node's
`firmware-name` property — it loads automatically at boot via the TI
remoteproc device tree node.

## Troubleshooting

### "Failed to load firmware: -22" or firmware not found
- **Cause:** `/lib/firmware/<name>` does not exist, or name doesn't match DT.
- **Fix:** Verify file name matches `firmware-name` in DT exactly (case-sensitive).
  Use `find /lib/firmware -name "*m4f*"` to check.

### "bad elf magic" in dmesg
- **Cause:** The `.out` file is a TI COFF/ELF but corrupt, or wrong architecture.
  M4F firmware must be compiled for Cortex-M4 (Thumb2), not A53.
- **Fix:** Verify you used `tiarmclang` (TI ARM Clang) targeting M4F, not GCC for A53.

### remoteproc0/state shows "offline" after start attempt
- **Cause:** Resource table missing or invalid. This is the most common failure.
- **Fix:** Re-check Step 1. Confirm `.resource_table` section exists in the ELF:
  ```bash
  aarch64-linux-gnu-readelf -S your_firmware.out | grep resource
  ```
  Must show `.resource_table` section.

### Core starts but trace0 is empty
- **Cause:** Debug Memory Log not enabled in SysConfig, or firmware crashed before
  printing.
- **Fix:** Enable "Debug Log → Memory Log" in SysConfig for the project.

### "power-domain request rejected" when reloading firmware pre-booted by SBL
- **Cause:** SBL (Secondary Boot Loader) pre-booted the M4F and Linux cannot
  re-acquire the power domain.
- **Fix:** Do not pre-boot M4F in SBL if Linux needs to manage it via remoteproc.
  Choose one owner. Or use the correct remoteproc driver for SBL-booted cores.

## Scripts

- `scripts/load-firmware.sh` — Automate firmware copy + remoteproc start + status check

## Reference

- E2E Resource Table FAQ: https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1193620/faq-am62x-am64x-how-to-allow-linux-to-load-m4f-r5f-firmware-by-adding-a-resource-table
- AM62x Academy Multicore: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST (section: Application Development on Remote Cores)
- MCU+ SDK IPC Guide: https://software-dl.ti.com/mcu-plus-sdk/esd/AM62X/latest/exports/docs/api_guide_am62x/IPC_GUIDE.html
- SDK remoteproc doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Drivers_Remote_Proc.html
