---
name: ti-serial-console
description: Capture the TI board's serial console (SPL, U-Boot and kernel boot log) to a file, stop U-Boot autoboot, and run single U-Boot or shell commands over the UART, non-interactively; or open an interactive terminal for the user. Use when the board has no network, does not boot, a boot log is needed, or a U-Boot command must be run.
---

# ti-serial-console

The UART console shows the boot stages that ssh never sees (SPL, U-Boot, early kernel). The
agent's shell is not interactive, so the agent uses the two non-interactive scripts below;
`serial-connect.sh` is the interactive terminal for the user.

## Docs (MCP)

Follow [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`,
`version=$TI_SDK_VERSION_DOCS` (else `latest`; say the MCP may lag the SDK). Cite the page path.
- `ti_processor_sdk_docs_search(query="Setup UART serial console minicom", device=$TI_DOCS_DEVICE, os="linux", version=...)`
- `ti_processor_sdk_docs_search(query="U-Boot environment uEnv.txt", ...)` before changing U-Boot variables.
- Which USB port or header carries the console, and the boot-mode switches: the board user guide and TRM
  (not in the MCP). Do not guess them.

## Prerequisites

- Profile `board.serial` (`port`, `baud`, `program`) in `.claude/target-profile.yaml`
  (see `ti-sdk-quick-start`), or pass `--port` / `--baud`, or set `TI_SERIAL_PORT` / `TI_SERIAL_BAUD`.
  Precedence: option > environment > profile > default (115200; `screen` for the interactive terminal).
- USB-to-UART adapter (or the board's on-board USB-UART) connected; read/write access to the device.
- No other program holding the port: the scripts refuse a port that is already open (`fuser`).
- Host Linux with `stty` (coreutils). Windows `COM` ports are not supported by the scripts.

## Steps

1. Find the port (read-only):
   ```bash
   ls -l /dev/serial/by-id/ 2>/dev/null; ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
   ```
   Prefer the `/dev/serial/by-id/...` path: `ttyUSBn` numbers change with plug order. Multi-channel
   adapters expose several ports for one board; the board user guide says which is the main console.
   If unsure, try each with step 2 (exit status 4 = no output on that port). Baud: 115200 8N1 is what the
   SDK `bin/setup-minicom.sh` writes; on a running board `cat /proc/cmdline` shows `console=<tty>,<baud>`.

2. Capture a boot log (starts listening, then the user power-cycles or resets the board):
   ```bash
   scripts/capture-boot.sh --port <dev> --seconds 120 --out boot.log    # stops at the login prompt
   ```
   Exit 0 = pattern seen, 3 = timeout with output, 4 = no output at all, 1 = port error. Each log line has a
   host timestamp. Other end points: `--until 'Starting kernel'`, or any bash regex.

3. Stop in U-Boot and run commands (changes board state: the board stays at the U-Boot prompt; confirm first):
   ```bash
   scripts/capture-boot.sh --port <dev> --stop-autoboot --out uboot.log     # sends Enter at "Hit any key"
   scripts/serial-cmd.sh --port <dev> -- printenv bootcmd                    # prints the reply
   scripts/serial-cmd.sh --port <dev> -- boot                                # continue booting
   ```
   `serial-cmd.sh` waits for the prompt (default: U-Boot `=> ` or a root shell `# `; `--prompt` for others) and
   exits 3 on timeout. Read-only commands such as `printenv`, `version`, `mmc list`, `bdinfo` are safe; anything
   that writes (`mmc write`, `fatwrite`, `env default -a`, `setenv` followed by `boot`) needs the user's go-ahead.
   `setenv` lasts until reset. To persist variables use `uEnv.txt` on the boot partition, not `saveenv` (TI
   SDKs boot with the built-in default environment; see `ti-deploy-image` `references/network-boot.md`).

4. Interactive terminal for the user (the agent cannot drive it): suggest the user run, in this session,
   ```bash
   ! .claude/skills/ti-serial-console/scripts/serial-connect.sh --port <dev>
   ```
   | Program | Exit keys |
   |---|---|
   | `screen` | `Ctrl-A` `k`, then `y` |
   | `minicom` | `Ctrl-A` `x` |
   | `picocom` | `Ctrl-A` `Ctrl-X` |
   | `cu` | `~.` |

5. Read the log. What to look for on K3 boards (see `ti-boot-chain` for the flow and the files involved):
   the R5 SPL banner (`U-Boot SPL ...`), the boot device (`Trying to boot from ...`), the U-Boot proper banner
   and `Model:` line, the autoboot countdown, `Starting kernel ...`, then kernel messages and the login prompt.
   The last line before output stops tells which stage failed. Banner text differs per release; match on it
   loosely.

## Verify

- `capture-boot.sh` exits 0 and the log contains the SPL banner and the stage you stopped at.
- `serial-cmd.sh -- version` prints the U-Boot (or `uname`-style) version and exits 0.
- `serial-connect.sh` opens the terminal (user side) and keys typed reach the board.

## Troubleshooting

| Symptom | Check |
|---|---|
| exit 4, no output | Other ports of the same adapter; board power and reset; cable on the console header (board guide) |
| Garbled characters | Baud: board guide, or `console=` in `/proc/cmdline` on a running board |
| `no read/write access` | Device group shown in the message (often `dialout`): `sudo usermod -aG <group> $USER`, then log in again (user runs it) |
| `already open by PID(s)` | Close the program holding the port (`fuser -v <dev>` names it), then retry |
| `--stop-autoboot` misses the prompt | Autoboot delay too short or prompt text differs: run `--until 'Hit any key'` to see it, then stop it interactively |
| `serial-cmd.sh` exit 3 | Board not at the expected prompt: capture first to see where it is, or pass `--prompt` |
| No SPL banner at all | Boot binaries or boot mode: `ti-boot-chain` (tiboot3 variant vs security type), boot-mode pins (TRM) |

Not covered: board power control (the user power-cycles), Windows hosts, console on a USB gadget or network.

## Scripts

- `scripts/capture-boot.sh` - non-interactive capture with timestamps, end pattern and optional autoboot stop.
- `scripts/serial-cmd.sh` - send one command, print the reply up to the next prompt.
- `scripts/serial-connect.sh` - interactive terminal for the user (`screen`, `minicom`, `picocom`, `cu`).
- `scripts/serial-common.sh` - shared: port/baud/profile resolution, busy check, `stty` raw 8N1 setup.

Tested against a simulated console on a pty (boot log, autoboot stop, U-Boot commands, timeouts, busy port);
not yet run against a physical board.
