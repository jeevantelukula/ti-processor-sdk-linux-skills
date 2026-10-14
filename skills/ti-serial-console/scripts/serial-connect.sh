#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# serial-connect.sh - open an INTERACTIVE serial terminal for the user.
# An agent cannot drive it; agents use capture-boot.sh and serial-cmd.sh instead.
#
# Usage: serial-connect.sh [--port DEV] [--baud N] [--program screen|minicom|picocom|cu]
# Defaults: TI_SERIAL_* env, then profile board.serial (see serial-common.sh), then 115200 / screen.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=serial-common.sh
. "$here/serial-common.sh"

port="" baud="" prog=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --port) port=${2:?}; shift 2 ;;
        --baud) baud=${2:?}; shift 2 ;;
        --program) prog=${2:?}; shift 2 ;;
        -h|--help) sed -n '3,7p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 1 ;;
    esac
done

serial_resolve "$port" "$baud" || exit 1
prog=${prog:-$SERIAL_PROGRAM}
serial_open_check "$SERIAL_PORT" || exit 1
command -v "$prog" >/dev/null 2>&1 || { echo "error: '$prog' is not installed" >&2; exit 1; }

case $prog in
    screen)  echo "screen $SERIAL_PORT $SERIAL_BAUD   (exit: Ctrl-A k, then y)"
             exec screen "$SERIAL_PORT" "$SERIAL_BAUD" ;;
    minicom) echo "minicom $SERIAL_PORT $SERIAL_BAUD   (exit: Ctrl-A x)"
             exec minicom -D "$SERIAL_PORT" -b "$SERIAL_BAUD" ;;
    picocom) echo "picocom $SERIAL_PORT $SERIAL_BAUD   (exit: Ctrl-A Ctrl-X)"
             exec picocom -b "$SERIAL_BAUD" "$SERIAL_PORT" ;;
    cu)      echo "cu $SERIAL_PORT $SERIAL_BAUD   (exit: ~.)"
             exec cu -l "$SERIAL_PORT" -s "$SERIAL_BAUD" ;;
    *)       echo "error: unknown program '$prog' (screen, minicom, picocom, cu)" >&2; exit 1 ;;
esac
