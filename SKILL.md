---
name: ti-processor-sdk-linux-skills
version: "1.1.0"
description: >
  Agentic skills for TI Processor SDK Linux — covers SDK setup, GPIO/pinmux,
  device tree, Yocto build, boot chain, eMMC flashing, remote core firmware
  loading, custom board porting, kernel modules, and PRU programming.
tags: [ti, sitara, am62x, k3, linux, yocto, device-tree, gpio, remoteproc, pru]
license: Apache-2.0
sdk_version: "12.01.00.05.03"
kernel_version: "6.18.38-ti"
yocto_codename: scarthgap
---

# TI Processor SDK Linux Skills

AI-assisted skills for understanding, building, and customizing the
Texas Instruments Processor SDK for Linux on Sitara K3 SoCs.

## Quick Selection Guide

| User Question Contains | Use Skill |
|---|---|
| "set up SDK", "install SDK", "environment variables" | [01-sdk-setup](skills/01-sdk-setup/SKILL.md) |
| "GPIO", "pinmux", "IOPAD", "libgpiod", "PIN_INPUT", "gpiochip" | [02-gpio-pinmux](skills/02-gpio-pinmux/SKILL.md) |
| "device tree overlay", ".dtbo", ".dtso", "cape", "runtime DT" | [03-device-tree-overlay](skills/03-device-tree-overlay/SKILL.md) |
| "custom DTS", "Yocto device tree", "bbappend kernel", "KERNEL_DEVICETREE" | [04-yocto-custom-dt](skills/04-yocto-custom-dt/SKILL.md) |
| "boot", "tiboot3", "tispl", "u-boot", "fitImage", "boot chain" | [05-boot-chain](skills/05-boot-chain/SKILL.md) |
| "eMMC", "emmc boot", "flash eMMC", "boot0 partition" | [06-emmc-boot](skills/06-emmc-boot/SKILL.md) |
| "M4F", "R5F", "remoteproc", "firmware loading", "resource table", "RPMsg", "IPC" | [07-remoteproc-firmware](skills/07-remoteproc-firmware/SKILL.md) |
| "custom board", "board porting", "new hardware", "UART", "I2C", "SPI" setup | [08-custom-board-port](skills/08-custom-board-port/SKILL.md) |
| "Yocto build", "bitbake", "build error", "host setup", "Ubuntu" | [09-yocto-build-setup](skills/09-yocto-build-setup/SKILL.md) |
| "kernel module", "out-of-tree", "DKMS", "cross-compile driver" | [10-kernel-module](skills/10-kernel-module/SKILL.md) |
| "PRU", "PRU-ICSS", "industrial IO", "PRUSS", "RPMsg PRU" | [11-pru-programming](skills/11-pru-programming/SKILL.md) |

## Skill Catalog

### Tier 1 — Most Common Pain Points (start here)

#### [Skill 02: GPIO and Pinmux Configuration](skills/02-gpio-pinmux/SKILL.md)
Configure GPIO pins in device tree using the K3 pinctrl framework. Covers IOPAD
macros, PIN_INPUT/PIN_OUTPUT semantics, gpiochip numbering, and the libgpiod
userspace API. Addresses the most-viewed AM62x E2E topic.

#### [Skill 04: Custom Device Tree in Yocto Build](skills/04-yocto-custom-dt/SKILL.md)
Add a custom `.dts` file to the Yocto build and select it at boot. Covers the
`linux-ti-staging_%.bbappend` pattern, `KERNEL_DEVICETREE`, U-Boot
`default_device_tree`, and FIT image vs standalone DTB boot mode.

#### [Skill 07: Remote Core Firmware Loading (M4F / R5F)](skills/07-remoteproc-firmware/SKILL.md)
Load MCU+ SDK firmware onto the M4F or R5F from Linux using remoteproc.
Covers the resource table requirement, SysConfig IPC setup, linker.cmd DDR
placement, `/lib/firmware` symlink, and reading remote core trace logs.

#### [Skill 09: Yocto Build Host Setup](skills/09-yocto-build-setup/SKILL.md)
Set up an Ubuntu 22.04 host (or Docker container) to build the Processor SDK
with Yocto. Covers required packages, disk space (750 GB), swap file, dash→bash
reconfiguration, locale settings, and proxy setup.

### Tier 2 — Hardware Bringup

#### [Skill 06: eMMC Boot Mode](skills/06-emmc-boot/SKILL.md)
Flash bootloader and rootfs to eMMC and boot in eMMC hardware boot0 mode.
Covers boot mode switch settings, U-Boot SPL eMMC patch, MMC speed reduction
DTB patch, flashing sequence, and environment save verification.

#### [Skill 08: Custom Board Porting](skills/08-custom-board-port/SKILL.md)
Port the SDK to a custom AM62x-based board. Covers creating a new board DTS
from the SK reference, U-Boot board configuration, SysConfig pinmux export,
UART/I2C/SPI peripheral nodes, and Yocto MACHINE configuration.

#### [Skill 05: Boot Chain — Build and Debug](skills/05-boot-chain/SKILL.md)
Understand and rebuild the 5-stage K3 boot chain. Covers tiboot3.bin (R5 SPL),
tispl.bin (TF-A + OP-TEE + A53 SPL), u-boot.img, and fitImage. Includes
artifact verification and boot failure diagnosis.

### Tier 3 — Device Tree and Kernel

#### [Skill 03: Device Tree Overlays](skills/03-device-tree-overlay/SKILL.md)
Create and apply device tree overlays (`.dtso` → `.dtbo`) for runtime peripheral
configuration. Covers fragment syntax, dtc compilation, U-Boot overlay loading,
and the prebuilt DTBO files in the SDK.

#### [Skill 10: Out-of-Tree Kernel Module](skills/10-kernel-module/SKILL.md)
Cross-compile and load an out-of-tree kernel module using the SDK devkit
toolchain. Covers environment setup, Makefile template, module signing for HS
devices, and Yocto recipe for permanent inclusion.

### Tier 4 — TI-Unique Capabilities

#### [Skill 01: SDK Setup and Environment Check](skills/01-sdk-setup/SKILL.md)
Install the Processor SDK, verify the cross-compile toolchain, set environment
variables, and confirm the devkit is functional with a test compile.

#### [Skill 11: PRU-ICSS Programming](skills/11-pru-programming/SKILL.md)
Write and load PRU firmware for industrial IO use cases. Covers PRU-ICSS
architecture, pru-icss device tree node, RPMsg from PRU to Linux, and the
`pru-icss` example applications in the SDK.

## Autonomous Diagnostic Agents

For "why isn't this working?" investigations — load these before skills:

| Symptom | Agent |
|---|---|
| Board won't boot / stuck / kernel panic | [ti-boot-investigator](agents/ti-boot-investigator.md) |
| R5F/M4F firmware not loading / RPMsg broken | [ti-m4f-investigator](agents/ti-m4f-investigator.md) |
| Yocto bitbake build failure | [ti-build-investigator](agents/ti-build-investigator.md) |

## Context Documents

Load these for background knowledge before applying skills:

- [SDK Customization Workflow](context/sdk-customization-workflow.md) — **start here**: INIT → CUSTOMIZE → BUILD → DEPLOY phases
- [K3 Architecture](context/k3-architecture.md) — multi-core SoC, domain isolation, clocks
- [Boot Chain](context/boot-chain.md) — 5-stage K3 boot sequence with binary map
- [Device Tree System](context/device-tree-system.md) — DT structure, overlays, pinctrl
- [Yocto Workflow](context/yocto-workflow.md) — layers, recipes, bbappend, images
- [SDK Structure](context/sdk-structure.md) — directory layout and key file locations

## Hardware Reference

- [TRM Chapter Index](references/hardware/trm-chapter-index.md) — AM625 TRM navigation
- [AM625 Pinmux Registers](references/hardware/am625-pinmux-registers.yaml) — PADCONFIG offsets (machine-readable)
- [SK-AM62x Connectors](references/hardware/sk-am62x-connectors.yaml) — RPi header, USB, JTAG, boot switches
- [Known Issues — SDK 12.x](references/errata/sdk-12-known-issues.md) — bugs, workarounds, silicon errata

## Workspace Setup

Before your first skill invocation, initialize the target platform profile:

```bash
# Copy the template and fill in your board/SDK details
cp target-platform/platform_template.yaml target-platform/sk-am62x.yaml
# Edit: board.name, board.machine, board.soc, sdk.version, sdk.root_path
# Optionally: documents.trm, documents.board_schematic for hardware-accurate skills
```

Skills read `target-platform/*.yaml` (where `active: true`) for board context.

## Environment Setup

```bash
# Source the devkit toolchain (cross-compile for aarch64)
source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux

# Verify cross-compiler
${CC} --version   # should show aarch64-oe-linux-gcc

# Detect SDK version
cat <sdk-path>/board-support/ti-linux-kernel-*.version 2>/dev/null || \
  ls <sdk-path>/board-support/prebuilt-images/
```

Run `setup.sh` in this repository for automated environment detection:
```bash
source setup.sh
```
