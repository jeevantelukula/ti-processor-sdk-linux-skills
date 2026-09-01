# Board Profile: BeaglePlay (AM625)

## Overview

| Property | Value |
|---|---|
| SoC | AM625 (4× Cortex-A53 @ 1.4 GHz) or AM623 (1× A53) |
| RAM | 2 GB LPDDR4 |
| Storage | 16 GB eMMC + microSD |
| MACHINE (TI SDK) | `beagleplay-ti` |
| DTB | `k3-am625-beagleplay.dtb` |
| Maker | BeagleBoard.org Foundation |

## Purpose

BeaglePlay is a community single-board computer based on AM625. It is
**not** a TI EVM — it is a third-party board that uses the AM625 SoC and
runs TI SDK firmware. Common among:
- Hobbyists and makers
- University courses
- Prototyping embedded Linux

## Board Differences vs SK-AM62x

| Feature | SK-AM62x | BeaglePlay |
|---|---|---|
| Primary orientation | SDK eval / bring-up | Community / maker |
| Click connector | No | MikroBUS Click |
| Ethernet | RJ45 only | RJ45 + Sub-GHz radio (CC1352) |
| Boot media | SD / eMMC | SD / eMMC |
| Console | micro-USB (XDS110) | USB-C (on-board UART) |
| 40-pin RPi header | Yes | Yes |
| Camera | MIPI CSI-2 | No |

## Console Access

Connect via USB-C to the port labeled "CONSOLE/DEBUG".
- Device: `/dev/ttyUSB1` or `/dev/ttyACM0` depending on host
- 115200 baud, 8N1

## Boot Mode

BeaglePlay always tries SD card first, then eMMC. No DIP switch needed.

Default boot order defined in `sysboot.txt` on the FAT partition.

## Using with TI Processor SDK

TI SDK supports BeaglePlay via the `beagleplay-ti` MACHINE.

```bash
MACHINE=beagleplay-ti bitbake tisdk-default-image
```

The prebuilt image for BeaglePlay is:
```
board-support/prebuilt-images/am62xx-evm/k3-am625-beagleplay.dtb
```

Note: the prebuilt WIC image (`tisdk-default-image-am62xx-evm.wic.xz`) is
built for `am62xx-evm` MACHINE; for BeaglePlay use the beagleplay-ti MACHINE
to get the correct DTB set as default.

## DTS File

```
arch/arm64/boot/dts/ti/k3-am625-beagleplay.dts
```

Key differences from k3-am625-sk.dts:
- No DSS/HDMI (uses external bridge differently)
- CC1352 sub-GHz radio connected via UART + GPIO
- Different power management IC (TPS6522x vs TPS6594x on SK)
- mikroBUS Click header connected to MAIN_SPI1 + MAIN_I2C1 + GPIO

## References

- BeaglePlay Product Page: https://www.beagleboard.org/boards/beagleplay
- BeaglePlay Quick Start: https://docs.beagleboard.org/latest/boards/beagleplay/index.html
- AM625 SoC Datasheet: https://www.ti.com/lit/gpn/am6254
