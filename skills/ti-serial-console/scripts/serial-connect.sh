#!/usr/bin/env bash
# Connect to board serial console using profile settings.
# Reads board.serial from target-profile.yaml (or env vars).

set -euo pipefail

# Load profile if exists
PROFILE="${TI_PROFILE:-$HOME/.claude/target-profile.yaml}"
if [[ -f "$PROFILE" ]]; then
  # Extract serial settings from YAML (simple grep, assumes profile format)
  PORT=$(awk '/^  serial:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="port:"{sub(/^[^:]*:[ ]*/,"");print;exit}' "$PROFILE")
  BAUD=$(awk '/^  serial:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="baud:"{sub(/^[^:]*:[ ]*/,"");print;exit}' "$PROFILE")
  PROG=$(awk '/^  serial:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="program:"{sub(/^[^:]*:[ ]*/,"");print;exit}' "$PROFILE")
fi

# Fallback to env vars
PORT="${PORT:-${TI_SERIAL_PORT:-}}"
BAUD="${BAUD:-${TI_SERIAL_BAUD:-115200}}"
PROG="${PROG:-${TI_SERIAL_PROGRAM:-screen}}"

if [[ -z "$PORT" ]]; then
  echo "Error: serial port not set. Set board.serial.port in profile or TI_SERIAL_PORT env." >&2
  exit 1
fi

if [[ ! -e "$PORT" ]]; then
  echo "Error: serial device $PORT not found" >&2
  echo "Available: $(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo 'none')" >&2
  exit 1
fi

case "$PROG" in
  screen)
    echo "Connecting with screen: $PORT $BAUD (exit: Ctrl-A K Y)"
    exec screen "$PORT" "$BAUD"
    ;;
  minicom)
    echo "Connecting with minicom: $PORT $BAUD (exit: Ctrl-A X)"
    exec minicom -D "$PORT" -b "$BAUD"
    ;;
  picocom)
    echo "Connecting with picocom: $PORT $BAUD (exit: Ctrl-A Ctrl-X)"
    exec picocom -b "$BAUD" "$PORT"
    ;;
  cu)
    echo "Connecting with cu: $PORT $BAUD (exit: ~.)"
    exec cu -l "$PORT" -s "$BAUD"
    ;;
  *)
    echo "Error: unknown program '$PROG'. Use: screen, minicom, picocom, cu" >&2
    exit 1
    ;;
esac