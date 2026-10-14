#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# capture-boot.sh - record the board's serial console to a file, non-interactively.
#
# Usage: capture-boot.sh [--port DEV] [--baud N] [--seconds N] [--until REGEX]
#                        [--stop-autoboot] [--out FILE]
#   --seconds N       stop after N seconds (default 120)
#   --until REGEX     stop when the console output matches REGEX (bash ERE; default: login prompt).
#                     Prompts without a newline (e.g. "login: ", "=> ") are matched too.
#   --stop-autoboot   send Enter when U-Boot prints "Hit any key to stop autoboot" (this stops
#                     the boot at the U-Boot prompt: changes board state) and then stop at the
#                     U-Boot prompt, unless --until is given
#   --out FILE        log file (default boot-<date>.log); each line gets a host timestamp
# Port/baud default to TI_SERIAL_PORT/TI_SERIAL_BAUD, then the profile board.serial (see
# serial-common.sh). Start it, then power-cycle or reset the board.
# Exit: 0 pattern seen, 3 timeout with output, 4 no output at all (wrong port, baud or
# cable, or board off), 1 usage/port error.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=serial-common.sh
. "$here/serial-common.sh"

usage() { sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 1; }

port="" baud="" seconds=120 until="" until_set=0 stop_ab=0 out=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --port) port=${2:?}; shift 2 ;;
        --baud) baud=${2:?}; shift 2 ;;
        --seconds) seconds=${2:?}; shift 2 ;;
        --until) until=${2:?}; until_set=1; shift 2 ;;
        --stop-autoboot) stop_ab=1; shift ;;
        --out) out=${2:?}; shift 2 ;;
        -h|--help) usage ;;
        *) echo "unknown option: $1" >&2; usage ;;
    esac
done
[[ $seconds =~ ^[0-9]+$ ]] || { echo "error: --seconds must be a whole number" >&2; exit 1; }
if [[ $until_set -eq 0 ]]; then
    if [[ $stop_ab -eq 1 ]]; then until='=> $'; else until='login: ?$'; fi
fi
out=${out:-boot-$(date +%Y%m%d-%H%M%S).log}

serial_resolve "$port" "$baud" || exit 1
serial_open_check "$SERIAL_PORT" || exit 1
serial_configure "$SERIAL_PORT" "$SERIAL_BAUD" || { echo "error: stty failed on $SERIAL_PORT" >&2; exit 1; }
exec 3<>"$SERIAL_PORT"
: > "$out"

echo "capturing $SERIAL_PORT at $SERIAL_BAUD for up to ${seconds}s into $out (stop on /$until/)" >&2
echo "now power-cycle or reset the board" >&2

log() { printf '%s %s\n' "$(date +%T.%3N)" "$1" >> "$out"; }
got=0 buf="" sent=0
deadline=$((SECONDS + seconds))
while (( SECONDS < deadline )); do
    chunk=""
    if IFS= read -r -t 1 -u 3 chunk; then
        line=${buf}${chunk}; buf=""
        line=${line%$'\r'}; line=${line//$'\r'/}
        got=1; log "$line"
        current=$line
    else
        rc=$?
        (( rc > 128 )) || { echo "error: $SERIAL_PORT closed (rc $rc)" >&2; break; }
        # timeout: keep partial text; prompts are not newline terminated
        [[ -n $chunk ]] || continue
        buf+=${chunk//$'\r'/}; got=1; current=$buf
    fi
    if [[ $stop_ab -eq 1 && $sent -eq 0 && $current == *"Hit any key to stop autoboot"* ]]; then
        printf '\r' >&3; sent=1
        echo "sent Enter to stop autoboot" >&2
    fi
    if [[ $current =~ $until ]]; then
        [[ -z $buf ]] || log "$buf"
        echo "matched /$until/; log: $out ($(wc -l < "$out") lines)" >&2
        exit 0
    fi
done
[[ -z $buf ]] || log "$buf"
if [[ $got -eq 0 ]]; then
    echo "no output from $SERIAL_PORT in ${seconds}s: check the port (another ttyUSB/ttyACM of the same adapter?), baud, cable, and that the board was reset" >&2
    exit 4
fi
echo "timeout after ${seconds}s without /$until/; log: $out ($(wc -l < "$out") lines)" >&2
exit 3
