# AGENTS.md
# TI Processor SDK Linux Skills — AI Agent Guide

This repository contains agentic skills for working with the Texas Instruments Processor SDK for Linux.
It follows the [Linux Foundation AAIF](https://aaif.linuxfoundation.org/) AGENTS.md standard.

## Purpose

Help customers and engineers:
- Set up, build, and flash the TI Processor SDK for Linux
- Customize device trees for custom hardware
- Configure GPIO, pinmux, and peripherals (UART, I2C, SPI, etc.)
- Load firmware onto remote cores (M4F, R5F) via Linux remoteproc
- Port the SDK to a custom board
- Build and extend with Yocto/OpenEmbedded

Skills target the **AM62x family** (AM625, AM623, AM620, AM62xx-SIP) as the primary reference
but use K3-architecture patterns applicable across AM64x, AM62Ax, AM62Px, and other Sitara K3 SoCs.

## Repository Layout

```
ti-processor-sdk-linux-skills/
├── AGENTS.md               ← This file
├── SKILL.md                ← Master skill index
├── setup.sh                ← Environment detection and validation
├── context/                ← Background knowledge for AI agents
│   ├── k3-architecture.md      K3 multi-core SoC overview
│   ├── boot-chain.md           5-stage K3 boot sequence
│   ├── device-tree-system.md   DT + DTBO overlay system
│   ├── yocto-workflow.md       Yocto layer/recipe/bbappend model
│   └── sdk-structure.md        SDK directory layout reference
├── skills/                 ← Individual skill directories
│   ├── 01-sdk-setup/           SDK installation and environment check
│   ├── 02-gpio-pinmux/         GPIO configuration and pinmux setup
│   ├── 03-device-tree-overlay/ DT overlays (.dtso/.dtbo)
│   ├── 04-yocto-custom-dt/     Adding custom DTS to Yocto build
│   ├── 05-boot-chain/          Understanding and building boot artifacts
│   ├── 06-emmc-boot/           Flashing and booting from eMMC
│   ├── 07-remoteproc-firmware/ Loading M4F/R5F firmware from Linux
│   ├── 08-custom-board-port/   Porting SDK to custom hardware
│   ├── 09-yocto-build-setup/   Host machine setup for Yocto builds
│   ├── 10-kernel-module/       Out-of-tree kernel module build
│   └── 11-pru-programming/     PRU-ICSS firmware and device tree
└── references/
    ├── docs-index.md           Official TI documentation links
    ├── sdk-versions.md         SDK version compatibility matrix
    └── boards/                 Board-specific reference profiles
```

## How AI Agents Should Use This Repository

### Session Start
1. Read `SKILL.md` to understand the available skills and their triggers.
2. Load relevant `context/` documents based on the user's question domain.
3. Run `setup.sh` (or read its output) to understand the current environment.

### Applying a Skill
1. Read the skill's `SKILL.md` — it contains the complete procedure.
2. Check **Prerequisites** before starting.
3. Follow **Steps** in order. Each step includes the exact commands.
4. Run **Validation** to confirm success.
5. If errors occur, consult **Troubleshooting** in the skill file.

### Context Loading Strategy
- GPIO / peripheral questions → load `context/device-tree-system.md` first
- Build errors → load `context/yocto-workflow.md` first
- Boot failures → load `context/boot-chain.md` first
- Custom board → load `context/k3-architecture.md` + `context/device-tree-system.md`
- Remote core questions → skill 07 + `context/k3-architecture.md`

## Important TI SDK Concepts

### K3 Multi-Core Architecture
K3 SoCs have multiple heterogeneous cores: Cortex-A53 (runs Linux), R5F and/or M4F
(run MCU+ SDK RTOS firmware), and PRU-ICSS (programmable real-time units for industrial IO).
The Linux `remoteproc` framework manages the non-Linux cores.

### Boot Chain
Every K3 boot goes through 5 binaries: `tiboot3.bin` (R5 ROM bootstrap) →
`tispl.bin` (TF-A + OP-TEE + A53 SPL) → `u-boot.img` (full U-Boot) →
`fitImage` (kernel + DTB) or standalone kernel + DTB. All are in `board-support/prebuilt-images/`.

### Device Tree
All hardware configuration is in device tree source (`.dts`/`.dtsi`).
Overlays (`.dtso` compiled to `.dtbo`) allow runtime configuration of optional peripherals.
GPIO, pinmux, and peripheral configuration all require device tree changes.

### Yocto Build System
The SDK uses Yocto/OpenEmbedded with layers: `meta-ti-bsp` (BSP), `meta-ti-foundational`
(SDK recipes), `meta-arago` (filesystem), `oe-core` (core). Customization happens
via `.bbappend` files in a custom layer — never edit upstream layer files directly.

## SDK Version Reference

Current: **Processor SDK Linux for AM62x v12.01.00.05.03** (released 2026-07-31)
Kernel: **6.18.38-ti** | U-Boot: **2025.01-ti** | TF-A: **v2.12-ti** | OP-TEE: **4.5.0-ti**

## Official Documentation

- AM62x Academy: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
- SDK Documentation: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/devices/AM62X/linux/index.html
- E2E Support Forum: https://e2e.ti.com/support/processors-group/processors/f/processors-forum
