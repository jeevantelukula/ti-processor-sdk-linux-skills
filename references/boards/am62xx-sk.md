# Board Profile: SK-AM62x (AM625 Starter Kit EVM)

## Overview

| Property | Value |
|---|---|
| SoC | AM625 (4× Cortex-A53 @ 1.4 GHz) |
| RAM | 2 GB LPDDR4 |
| Storage | 16 GB eMMC + microSD slot |
| Security | HS-FS (default) |
| MACHINE | `am62xx-evm` |
| DTB | `k3-am625-sk.dtb` |
| TI Part # | SK-AM62B-P1 (current), SK-AM62 (earlier) |

## Connectors and Interfaces

| Interface | SoC Peripheral | Notes |
|---|---|---|
| UART (USB) | MAIN_UART0 | micro-USB, 115200 8N1, shows as /dev/ttyUSB0 on host |
| Ethernet | CPSW3G (2-port switch) | RJ45 x1 on SK |
| USB3.0 Type-A | USB0 (host) | |
| USB Type-C | USB1 (DRD) | |
| microSD | SDHCI1 | SD card slot |
| eMMC | SDHCI0 | Internal 16 GB |
| 40-pin RPi header | MAIN domain GPIO/I2C/SPI/UART | Expansion |
| M.2 Key E | PCIe Gen2 | WiFi/BT card slot |
| HDMI | DSS7 + HDMI bridge | Display output |
| MIPI CSI-2 | CSI2RX | Camera connector |
| JTAG | via CC3301 XDS110 on-board | Debug via CCS |

## Boot Mode Switch (SW3)

| Mode | SW3 Setting | Notes |
|---|---|---|
| SD card | 1100000 (B3:B9) | Default for development |
| eMMC | 1001000 (B3:B9) | Production boot |
| UART (DFU) | 0100000 | USB DFU flash mode |
| OSPI | 1000010 | External SPI flash |

## GPIO Bank Assignment

| gpiochip | DT controller | Pins |
|---|---|---|
| gpiochip0 | main_gpio0 | GPIO0_0 to GPIO0_87 |
| gpiochip1 | main_gpio1 | GPIO1_0 to GPIO1_xx |
| gpiochip2 | mcu_gpio0 | MCU_GPIO0_0 to MCU_GPIO0_22 |

**Note:** gpiochip numbers are dynamically assigned and may change between SDK versions.
Use `gpiodetect` on target to confirm current assignment.

## RPi Header Pinout (40-pin)

Key signals on the 40-pin expansion header:
- Pin 3: I2C1_SDA (MAIN_I2C1)
- Pin 5: I2C1_SCL (MAIN_I2C1)
- Pin 8: UART5_TXD (MAIN_UART5)
- Pin 10: UART5_RXD
- Pin 11: GPIO1_14
- Pin 19: SPI1_D0 (MOSI)
- Pin 21: SPI1_D1 (MISO)
- Pin 23: SPI1_CLK
- Pin 24: SPI1_CS0

For the full RPi header pinout, see the SK-AM62x User Guide schematic.

## Console Access

Connect the micro-USB cable to the "DEBUG" USB port (not the USB Type-A ports).
This exposes 4 virtual COM ports on the host:

| Device | Purpose |
|---|---|
| /dev/ttyUSB0 | MAIN_UART0 (Linux console) |
| /dev/ttyUSB1 | WKUP_UART0 (TIFS/DM debug — read-only) |
| /dev/ttyUSB2 | MCU_UART0 (M4F console) |
| /dev/ttyUSB3 | Unused |

Terminal settings: **115200 baud, 8N1, no flow control**

## Prebuilt Images Location

```
board-support/prebuilt-images/am62xx-evm/
```

## Key DTS File

```
board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/k3-am625-sk.dts
board-support/ti-linux-kernel-*/arch/arm64/boot/dts/ti/k3-am62x-sk-common.dtsi
```

## Power Supply

- 5V/3A minimum via USB-C power port
- Do not power via the debug USB micro-USB port (insufficient current)

## References

- SK-AM62x Product Page: https://www.ti.com/tool/SK-AM62B-P1
- SK-AM62x User Guide: https://www.ti.com/lit/pdf/spruja3
- EVM Quick Start: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
