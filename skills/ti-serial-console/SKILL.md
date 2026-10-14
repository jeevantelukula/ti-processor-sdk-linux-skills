---
name: ti-serial-console
description: Connect to the target board's serial console, capture boot logs (ROM, SPL, U-Boot, kernel), and interact with the bootloader. Use when the board has no network, when debugging early boot failures, or when you need to interrupt U-Boot.
---

# ti-serial-console

Access the board's serial console (UART) to see the full boot sequence: ROM → SPL (tiboot3) → U-Boot → kernel. SSH only shows you the Linux login; serial shows everything before that.

## Docs (MCP)

Follow [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`, `version=$TI_SDK_VERSION_DOCS` (else `latest`). Cite page path.
- `ti_processor_sdk_docs_search(query="UART serial console setup", device=$TI_DOCS_DEVICE, os="linux", version=...)`
- `ti_processor_sdk_docs_search(query="minicom setup screen picocom", device=$TI_DOCS_DEVICE, os="linux", version=...)`
- `ti_processor_sdk_docs_search(query="boot mode pins TRM", device=$TI_DOCS_DEVICE, os="linux", version=...)` for boot medium selection

## Prerequisites

- `ti-sdk-setup` done (`TI_SDK_ROOT`, `TI_PLATFORM`, `TI_DOCS_DEVICE` exported).
- Profile `board.serial` populated: `port` (e.g. `/dev/ttyUSB0`, `COM3`), `baud` (default 115200), `program` (`screen`, `minicom`, `picocom`, `cu`).
- USB-to-serial adapter connected to the board's debug UART header (check board guide for pinout).
- Host user in `dialout` group (Linux) or appropriate permissions.

## Steps

### 1. Identify the serial port

```bash
# Linux: list USB serial devices
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
dmesg -T | grep -i usb | tail -20

# Windows: Device Manager → Ports (COM & LPT)
```

Typical TI EVMs: FTDI or CP210x USB-to-UART → `/dev/ttyUSB0` (Linux) or `COM3` (Windows).

### 2. Connect with your preferred program

| Program | Command (Linux) | Exit |
|---|---|---|
| `screen` | `screen /dev/ttyUSB0 115200` | `Ctrl-A` `K` `Y` |
| `minicom` | `minicom -D /dev/ttyUSB0 -b 115200` | `Ctrl-A` `X` |
| `picocom` | `picocom -b 115200 /dev/ttyUSB0` | `Ctrl-A` `Ctrl-X` |
| `cu` | `cu -l /dev/ttyUSB0 -s 115200` | `~.` |

The SDK includes `bin/setup-minicom.sh` which writes a minicom config for the board.

### 3. Watch the boot sequence

Power cycle the board. You should see:

```
ROM: ... (silicon revision, boot mode)
tiboot3 (R5 SPL): DDR init, loading tispl.bin
tispl.bin: DM firmware, TF-A, OP-TEE, A53 SPL
u-boot.img: U-Boot proper, environment, bootcmd
Kernel: Linux version ..., cmdline=...
Login prompt
```

### 4. Interrupt U-Boot (if needed)

At the `Hit any key to stop autoboot:` prompt, press any key. Common commands:

```bash
=> printenv          # show environment
=> setenv bootdelay 5
=> saveenv           # persist to boot medium
=> mmc dev 0         # select eMMC/SD
=> fatload mmc 0:1 ${loadaddr} tiboot3.bin
=> bootm ${loadaddr}
```

### 5. Capture logs to file

```bash
# screen
screen -L -Logfile boot.log /dev/ttyUSB0 115200

# picocom
picocom -b 115200 /dev/ttyUSB0 --logfile boot.log

# minicom
minicom -D /dev/ttyUSB0 -b 115200 -C boot.log
```

## Verify

- You see ROM version string (confirms correct UART pins and baud)
- You see `tiboot3` and `tispl` messages (confirms boot files are correct)
- You see U-Boot prompt if interrupted, or Linux login if not
- Log file captures everything for later analysis

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Garbled output | Wrong baud rate | Try 115200, 9600, 57600; check board guide |
| No output | USB adapter not bound / wrong port | `dmesg -T \| grep tty`; check `ls /dev/ttyUSB*` |
| Permission denied | User not in `dialout` | `sudo usermod -a -G dialout $USER`; relogin |
| Double characters | Local echo on | `screen -L` disables; `minicom -c on` |
| Can't interrupt U-Boot | Boot delay too short / no key sent | Increase `bootdelay` in U-Boot env; ensure terminal sends keys |

## Scripts

- `scripts/serial-connect.sh` — wrapper that reads profile and launches the chosen program
- `scripts/capture-boot.sh` — connects, power-cycles board (if power control available), captures to timestamped file

## Related Skills

- `ti-boot-chain` — understand what you're seeing in the boot log
- `ti-deploy-image` — flash the images that produce these logs
- `ti-diagnostic` — health check after boot completes