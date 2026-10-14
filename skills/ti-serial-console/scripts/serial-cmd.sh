#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# serial-cmd.sh - send one command to the serial console and print its output.
#
# Usage: serial-cmd.sh [--port DEV] [--baud N] [--prompt REGEX] [--seconds N] -- <command...>
#   --prompt REGEX  output ends when the console shows this prompt (bash ERE; default matches the
#                   U-Boot "=> " prompt and a root shell "# "). Use it for other prompts.
#   --seconds N     give up after N seconds (default 10)
# The board must already sit at that prompt (U-Boot: capture-boot.sh --stop-autoboot; Linux:
# logged in). Output excludes the echoed command and the final prompt.
# Exit: 0 prompt seen, 3 timeout (output so far is printed), 1 usage/port error.
# The command runs on the board: commands that write (mmc write, setenv + boot, rm, ...)
# change it - confirm those with the user first.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=serial-common.sh
. "$here/serial-common.sh"

usage() { sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 1; }

port="" baud="" prompt='(=>|#) $' seconds=10
while [[ $# -gt 0 ]]; do
    case $1 in
        --port) port=${2:?}; shift 2 ;;
        --baud) baud=${2:?}; shift 2 ;;
        --prompt) prompt=${2:?}; shift 2 ;;
        --seconds) seconds=${2:?}; shift 2 ;;
        --) shift; break ;;
        -h|--help) usage ;;
        -*) echo "unknown option: $1" >&2; usage ;;
        *) break ;;
    esac
done
[[ $# -gt 0 ]] || usage
[[ $seconds =~ ^[0-9]+$ ]] || { echo "error: --seconds must be a whole number" >&2; exit 1; }
cmd="$*"

serial_resolve "$port" "$baud" || exit 1
serial_open_check "$SERIAL_PORT" || exit 1
serial_configure "$SERIAL_PORT" "$SERIAL_BAUD" || { echo "error: stty failed on $SERIAL_PORT" >&2; exit 1; }
exec 3<>"$SERIAL_PORT"

# Drop whatever is pending (old boot output) so it is not mistaken for the reply.
while IFS= read -r -t 0.2 -u 3 _; do :; done || true

printf '%s\r' "$cmd" >&3
deadline=$((SECONDS + seconds)) buf="" first=1
while (( SECONDS < deadline )); do
    chunk=""
    if IFS= read -r -t 1 -u 3 chunk; then
        line=${buf}${chunk}; buf=""; line=${line//$'\r'/}
        if [[ $first -eq 1 && $line == *"$cmd"* ]]; then first=0; continue; fi  # echo of the command
        first=0
        printf '%s\n' "$line"
    else
        rc=$?
        (( rc > 128 )) || { echo "error: $SERIAL_PORT closed (rc $rc)" >&2; exit 1; }
        [[ -n $chunk ]] || continue
        buf+=${chunk//$'\r'/}
        if [[ $buf =~ $prompt ]]; then exit 0; fi
    fi
done
[[ -z $buf ]] || printf '%s\n' "$buf"
echo "timeout after ${seconds}s without prompt /$prompt/ (is the board at that prompt?)" >&2
exit 3
