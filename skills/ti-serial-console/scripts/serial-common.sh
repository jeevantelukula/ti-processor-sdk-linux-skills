# shellcheck shell=bash
# SPDX-License-Identifier: Apache-2.0
# serial-common.sh - sourced by the ti-serial-console scripts; not run directly.
#
# serial_resolve [port] [baud]  sets SERIAL_PORT, SERIAL_BAUD, SERIAL_PROGRAM.
#   Precedence: argument > TI_SERIAL_PORT/TI_SERIAL_BAUD/TI_SERIAL_PROGRAM > profile
#   board.serial.{port,baud,program} > defaults (no port, 115200, screen).
#   Profile: $TI_PROFILE, else ./.claude/target-profile.yaml, else the installed
#   .claude/target-profile.yaml next to this skill (written by install.sh).
# serial_open_check  fails if the port is missing, not readable/writable, or held by
#   another process (a second reader would split the data stream between programs).
# serial_configure   sets the line to raw 8N1, no flow control, no echo (stty).

_serial_here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

serial_profile_path() {
    local p
    for p in "${TI_PROFILE:-}" "$PWD/.claude/target-profile.yaml" "$_serial_here/../../../target-profile.yaml"; do
        [[ -n $p && -f $p ]] && { printf '%s\n' "$p"; return 0; }
    done
    return 1
}

# Value of board.serial.<key>, without quotes or trailing comment ("" when unset).
serial_profile_value() {
    awk -v k="$1:" '
        /^board:/ { b = 1; next }
        b && /^[^ #]/ { b = 0 }
        b && /^  serial:/ { s = 1; next }
        s && /^  [^ ]/ { s = 0 }
        s && $1 == k {
            sub(/^[^:]*:[ \t]*/, ""); sub(/[ \t]+#.*$/, ""); sub(/^#.*$/, "")
            gsub(/^["\047]|["\047]$/, ""); print; exit
        }' "$2"
}

serial_resolve() {
    local prof="" pp="" pb="" pg=""
    if prof=$(serial_profile_path); then
        pp=$(serial_profile_value port "$prof"); pb=$(serial_profile_value baud "$prof")
        pg=$(serial_profile_value program "$prof")
    fi
    SERIAL_PORT=${1:-${TI_SERIAL_PORT:-$pp}}
    SERIAL_BAUD=${2:-${TI_SERIAL_BAUD:-${pb:-115200}}}
    SERIAL_PROGRAM=${TI_SERIAL_PROGRAM:-${pg:-screen}}
    SERIAL_PROFILE=${prof:-<none>}
    if [[ -z $SERIAL_PORT ]]; then
        echo "error: no serial port: pass --port, set TI_SERIAL_PORT, or board.serial.port in ${prof:-.claude/target-profile.yaml}" >&2
        serial_list_ports >&2
        return 1
    fi
    [[ $SERIAL_BAUD =~ ^[0-9]+$ ]] || { echo "error: baud must be a number, got '$SERIAL_BAUD'" >&2; return 1; }
}

serial_list_ports() {
    local f found=0
    echo "serial ports on this host:"
    for f in /dev/serial/by-id/*; do
        [[ -e $f ]] || continue; found=1; echo "  $f -> $(readlink -f "$f")"
    done
    for f in /dev/ttyUSB* /dev/ttyACM*; do
        [[ -e $f ]] || continue; found=1; echo "  $f"
    done
    [[ $found -eq 1 ]] || echo "  none (adapter not plugged in, or no driver bound: dmesg | grep -i tty)"
}

serial_open_check() {
    local port=$1 holders
    [[ -e $port ]] || { echo "error: $port does not exist" >&2; serial_list_ports >&2; return 1; }
    if [[ ! -r $port || ! -w $port ]]; then
        echo "error: no read/write access to $port ($(stat -c '%U:%G %a' "$port" 2>/dev/null))." >&2
        echo "  Add yourself to its group (often dialout), then log in again: sudo usermod -aG <group> \$USER" >&2
        return 1
    fi
    if command -v fuser >/dev/null 2>&1 && holders=$(fuser "$port" 2>/dev/null) && [[ -n ${holders// /} ]]; then
        echo "error: $port is already open by PID(s)${holders}; close that terminal program first" >&2
        return 1
    fi
}

serial_configure() {
    stty -F "$1" "$2" cs8 -cstopb -parenb -crtscts -ixon -ixoff raw -echo
}
