#!/usr/bin/env bash
# Gate for PRU work: does the device tree define PRU/RTU/TX_PRU cores?
# Usage: pru-gate.sh <file.dtb> | --live
# Exit 0 and print the cores if present; exit 3 if the DT has none (do not continue with PRU steps).
set -euo pipefail

[[ $# -eq 1 ]] || { echo "Usage: $0 <file.dtb> | --live" >&2; exit 2; }
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
lister="$here/../../ti-remoteproc/scripts/dt-cores.sh"
[[ -x $lister ]] || { echo "ERROR: $lister not found (ti-remoteproc skill must be installed)" >&2; exit 1; }

out=$("$lister" "$1")
rows=$(printf '%s\n' "$out" | grep -E '[[:space:]]ti,[^[:space:]]*-(pru|rtu|tx-pru)[[:space:]]' || true)
if [[ -z $rows ]]; then
    echo "No PRU/RTU/TX_PRU nodes in this device tree: this SoC/board has no PRU support. Stop."
    exit 3
fi
printf '%s\n' "$out" | head -1
printf '%s\n' "$rows"
if ! printf '%s\n' "$rows" | grep -qE '[[:space:]]okay$'; then
    echo "NOTE: PRU nodes exist but none has status \"okay\": enable them in the board DTS/overlay first." >&2
fi
