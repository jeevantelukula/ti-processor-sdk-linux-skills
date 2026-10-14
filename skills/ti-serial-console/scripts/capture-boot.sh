#!/usr/bin/env bash
# Capture full boot log from power-on to login prompt.
# Requires: serial-connect.sh, board power control (optional), profile with serial settings.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${1:-boot-$(date +%Y%m%d-%H%M%S).log}"

# Load profile
PROFILE="${TI_PROFILE:-$HOME/.claude/target-profile.yaml}"
if [[ -f "$PROFILE" ]]; then
  PORT=$(awk '/^  serial:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="port:"{sub(/^[^:]*:[ ]*/,"");print;exit}' "$PROFILE")
  BAUD=$(awk '/^  serial:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="baud:"{sub(/^[^:]*:[ ]*/,"");print;exit}' "$PROFILE")
  PROG=$(awk '/^  serial:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="program:"{sub(/^[^:]*:[ ]*/,"");print;exit}' "$PROFILE")
fi

PORT="${PORT:-${TI_SERIAL_PORT:-}}"
BAUD="${BAUD:-${TI_SERIAL_BAUD:-115200}}"
PROG="${PROG:-${TI_SERIAL_PROGRAM:-screen}}"

if [[ -z "$PORT" ]]; then
  echo "Error: serial port not set in profile or TI_SERIAL_PORT" >&2
  exit 1
fi

echo "Capturing boot log to $LOG_FILE"
echo "Port: $PORT, Baud: $BAUD, Program: $PROG"
echo "Power-cycle the board now (or it will capture current output)"
echo "Press Ctrl-C to stop capture"

case "$PROG" in
  screen)
    screen -L -Logfile "$LOG_FILE" "$PORT" "$BAUD"
    ;;
  minicom)
    minicom -D "$PORT" -b "$BAUD" -C "$LOG_FILE"
    ;;
  picocom)
    picocom -b "$BAUD" "$PORT" --logfile "$LOG_FILE"
    ;;
  cu)
    # cu doesn't have built-in logging; use tee
    cu -l "$PORT" -s "$BAUD" | tee "$LOG_FILE"
    ;;
  *)
    echo "Error: program '$PROG' doesn't support logging directly" >&2
    exit 1
    ;;
esac

echo "Capture saved to $LOG_FILE"
echo "View with: less $LOG_FILE"