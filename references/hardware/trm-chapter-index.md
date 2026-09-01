# AM625 TRM Chapter Index

Quick navigation guide for the AM625 Technical Reference Manual (SPRUIV7A).
Use this when a skill needs to direct an agent to the right TRM section.

Document ID: SPRUIV7A | Download: https://www.ti.com/lit/pdf/SPRUIV7

---

## Chapter Map

| Chapter | Title | Key Content |
|---|---|---|
| 1 | Introduction | SoC overview, block diagram, feature summary |
| 2 | Device Configurations | Ball map, package pinout, IO voltage domains |
| 3 | Memory Map | All peripheral base addresses, MSMC address, DDR layout |
| 4 | Boot | Boot modes, ROM boot flow, SBL, secure boot sequence |
| 5 | TISCI | System Firmware interface, resource management API |
| 6 | Power Management | Power domains, voltage rails, LPSC modules, deep sleep |
| 7 | Clock Architecture | PLL configuration, HFOSC, clock trees, gate/mux nodes |
| 8 | Interrupts | Interrupt Router, Interrupt Aggregator, IRQ routing |
| 9 | DMA (UDMA-P) | Channels, rings, ring accelerator, packet DMA |
| 10 | GPIO | **PADCONFIG registers**, AM625_IOPAD macro, mux modes |
| 11 | I2C | Register map, timing, multi-master, HS mode |
| 12 | SPI (MCSPI/OSPI) | MCSPI controller, OSPI NOR/NAND flash interface |
| 13 | UART | Register map, flow control, DMA modes |
| 14 | USB | USB3SS DRD controller, PHY configuration |
| 15 | Ethernet (CPSW3G) | MAC config, RGMII/RMII, VLAN, rate limiting |
| 16 | ICSSG | PRU-ICSS subsystem, firmware interfaces, dual emac |
| 17 | MMC (MMCSD) | SD/eMMC host controller, HS400 mode, DDR50 |
| 18 | PCIe | EP/RC mode, PHY config, power management |
| 19 | Display (DSS7) | OLDI, DPI, HDMI output path |
| 20 | Camera (CSI2RX) | MIPI CSI-2 receiver, virtual channels |
| 21 | ADC (ADC12) | Channel config, trigger, FIFO, calibration |
| 22 | Timers | MCU/MAIN domain timers, PWM, capture/compare |
| 23 | Watchdog | Register map, NMI mode, service sequence |
| 24 | Security | SA2UL, PKA, RNG, DKEK, secure storage |
| 25 | DDR Controller | DRAM timing, ECC, power management |
| 26 | MCU Domain | MCU_UART, MCU_I2C, MCU_GPIO, MCU_MCAN |
| 27 | MCAN | CAN-FD controller, message RAM layout |
| 28 | OSPI | Octal-SPI flash, DTR mode, XIP |

---

## Critical sections for common customization tasks

### GPIO / Pinmux
- **Chapter 10, Section 10.2**: PADCONFIG register bit fields
  - Bits [3:0] = MUX_MODE (0=default function, 7=GPIO)
  - Bit 18 = RXACTIVE (must set for inputs — most common GPIO bug)
  - Bits [21:19] = PULL (none=0, up=1, down=2, keeper=3)
- **Chapter 10, Section 10.3**: `main_pmx0` and `mcu_pmx0` pin banks
- **Chapter 2, Section 2.3**: Ball map (SoC pin to ball name lookup)

### Clock configuration
- **Chapter 7, Section 7.3**: PLL lock sequence, input clock requirements
- **Chapter 7, Section 7.4**: Peripheral clock sources and dividers (TISCI handles this — do not write clock registers directly)

### Boot / eMMC
- **Chapter 4, Section 4.2**: Primary/backup bootloader flow
- **Chapter 4, Section 4.5**: ROM bootloader memory layout (eMMC offsets)
- **Chapter 17, Section 17.4**: eMMC boot partitions (boot0, boot1, RPMB)

### DMA (NAVSS)
- **Chapter 9, Section 9.3**: UDMA channel allocation (k3-respart-tool manages this)
- **Chapter 9, Section 9.5**: Ring Accelerator — ring descriptors, modes

### Security (HS-SE)
- **Chapter 24, Section 24.2**: Secure boot key provisioning
- **Chapter 24, Section 24.4**: DKEK derivation
- **Chapter 24, Section 24.6**: SA2UL (Security Accelerator)

---

## Register lookup guide

For PADCONFIG registers, the formula is:
```
Register address = <main_pmx0 base> + <pin_offset>
main_pmx0 base = 0x000F4000 (MAIN domain, from memory map Chapter 3)
mcu_pmx0 base  = 0x04084000 (MCU domain)
```

The `AM625_IOPAD(offset, muxmode, pullup)` macro in kernel DTS encodes:
- `offset`: byte offset from pmx0 base (e.g. `0x01e4`)
- `muxmode`: bits[3:0] of PADCONFIG — which function to select
- `pullup`: GPIO_ACTIVE_HIGH / PIN_PULLUP_EN / PIN_PULLDOWN_EN / PIN_NOPULL

See `context/device-tree-system.md` for the full macro explanation.

---

## TRM revision history

| Revision | Key changes |
|---|---|
| SPRUIV7A | Added AM625 SiP variants, corrected PADCONFIG table for MCU domain pads |
| SPRUIV7 | Initial release for AM625 |

Always use the latest revision. Errata (SPRZ463) takes precedence over TRM content.
