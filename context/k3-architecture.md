# K3 Multi-Core SoC Architecture

## Overview

TI K3 SoCs (AM62x, AM64x, AM62Ax, AM62Px) contain multiple heterogeneous processor
cores within distinct power/clock domains. Understanding the domain structure is
essential for device tree, resource partitioning, and multi-core firmware work.

## AM62x Core Map

| Core | Count | Runs | Managed By |
|---|---|---|---|
| Cortex-A53 | 4 (AM625) / 2 (AM623) / 1 (AM620) | Linux | — |
| Cortex-M4F | 1 | MCU+ SDK RTOS | Linux remoteproc |
| PRU-ICSS | 2 (PRU0, PRU1) | Custom firmware | Linux remoteproc |
| DMSC (WKUP-R5F) | 1 | DM firmware (ti-dm-fw) | System firmware |

## Domain Structure

K3 uses a "domain" model for isolation:

- **MAIN domain** — A53 cores, MAIN_UART, MAIN_I2C, MAIN_SPI, MAIN_GPIO
- **MCU domain** — M4F core, MCU_UART, MCU_I2C, MCU_SPI, MCU_GPIO0
- **WKUP domain** — Always-on section, WKUP-R5F (runs DM firmware), WKUP_UART0

### Practical Impact on Device Tree

Peripherals in the MAIN domain use `/main_conf/...` base addresses.
MCU domain peripherals use `/mcu_conf/...` base addresses.
The domain a peripheral lives in determines its pinmux node prefix:
- MAIN_GPIO → `main_pmx0` pinmux node
- MCU_GPIO0 → `mcu_pmx0` pinmux node

### GPIO Domain Confusion

A common pain point: `GPIO0` in the device tree refers to a MAIN domain GPIO controller,
while `MCU_GPIO0` is a separate controller in the MCU domain. They have different
`gpiochip` numbers visible to Linux and different pinmux nodes.

## System Controller: TISCI / DMSC

All clock, power, and resource management goes through **TISCI** (TI System Controller
Interface). The WKUP-R5F core runs Device Management (DM) firmware (`ti-dm-fw`) and
acts as the system controller proxy. Never directly access clocks or power domains
from Linux — always use the TISCI clk/pm drivers.

## Resource Partitioning (k3-respart-tool)

K3 SoCs have shared resources (DMA channels, IRQ lines, MSMC SRAM banks, ring
accelerator rings) that must be allocated between the Linux A53 and the remote cores
(M4F, R5F). The `k3-respart-tool` generates resource partition configuration.

Key file: `board-support/k3-respart-tool/`

When adding a new remote core use case (e.g., Ethernet on R5F via ICSSG), resource
partitioning for DMA and IRQ must be updated before the firmware will work.

## MSMC SRAM

AM62x has 512 KB of Multi-Subsystem Cache (MSMC) SRAM shared between all cores.
Default allocation reserves a portion for the M4F stack and heap. Visible in
device tree as the `sram@...` node under `/reserved-memory`.

## Inter-Processor Communication

Linux ↔ M4F/R5F communication uses:
- **RPMsg** (kernel `rpmsg` framework) — virtual serial channels
- **OpenAMP** (userspace via rpmsg-char) — zero-copy option
- **Shared memory** — direct DDR buffers (requires cache coherency care)

The M4F or R5F firmware must have RPMsg enabled via SysConfig IPC to use RPMsg.

## Key Differences: AM62x vs AM64x

| Feature | AM62x | AM64x |
|---|---|---|
| A53 cores | 4 (AM625), 2, or 1 | 2 |
| R5F clusters | 0 | 2 clusters × 2 cores |
| M4F | 1 | 0 |
| PRU-ICSS | 1 instance (2 PRUs) | 2 instances |
| ICSSG | No | Yes (industrial Ethernet) |

## Reference

- AM62x Technical Reference Manual (TRM): https://www.ti.com/lit/pdf/spruiv7
- K3 Resource Partitioning: `board-support/k3-respart-tool/README.md`
- AM62x Academy — Architecture Module: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
