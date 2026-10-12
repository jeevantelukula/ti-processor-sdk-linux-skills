#!/usr/bin/env bash
# List device-tree nodes that carry a "firmware-name" property (remote processors:
# R5F, M4F, PRU, ...) in a compiled DTB, with compatible, firmware name and status.
# Host or target. Needs dtc. Usage: dt-cores.sh <file.dtb>
#        dt-cores.sh --live        (reads /proc/device-tree on a running board)
set -euo pipefail

usage() { echo "Usage: $0 <file.dtb> | --live" >&2; exit 2; }
[[ $# -eq 1 ]] || usage
command -v dtc >/dev/null || { echo "ERROR: dtc not found (install device-tree-compiler)" >&2; exit 1; }

if [[ "$1" == "--live" ]]; then
    [[ -d /proc/device-tree ]] || { echo "ERROR: /proc/device-tree not found; run on the board" >&2; exit 1; }
    src=(dtc -q -I fs -O dts /proc/device-tree)
else
    [[ -f "$1" ]] || { echo "ERROR: $1 not found" >&2; exit 1; }
    src=(dtc -q -I dtb -O dts "$1")
fi

printf '%-44s %-26s %-24s %s\n' NODE COMPATIBLE FIRMWARE-NAME STATUS
dts=$("${src[@]}" 2>/dev/null) || { echo "ERROR: dtc could not read the device tree" >&2; exit 1; }
printf '%s\n' "$dts" | awk '
BEGIN { n = 0 }
/\{[[:space:]]*$/ {
    name=$0; sub(/^[[:space:]]*/, "", name); sub(/[[:space:]]*\{[[:space:]]*$/, "", name)
    depth++; nm[depth]=name; fw[depth]=""; st[depth]="okay"; cp[depth]=""; next
}
/^[[:space:]]*firmware-name = / { v=$0; sub(/^[^"]*"/, "", v); sub(/"[^"]*;[[:space:]]*$/, "", v); gsub(/\\0/, ",", v); gsub(/", "/, ",", v); fw[depth]=v; next }
/^[[:space:]]*status = /        { v=$0; sub(/^[^"]*"/, "", v); sub(/".*$/, "", v); st[depth]=v; next }
/^[[:space:]]*compatible = /    { v=$0; sub(/^[^"]*"/, "", v); sub(/".*$/, "", v); cp[depth]=v; next }
/^[[:space:]]*\};/ {
    if (depth > 0 && fw[depth] != "") {
        path = nm[depth]; if (depth > 2) path = nm[depth-1] "/" path
        printf "%-44s %-26s %-24s %s\n", path, cp[depth], fw[depth], st[depth]; n++
    }
    depth--
}
END { if (n == 0) print "(no node with firmware-name: this device tree defines no remote cores)" > "/dev/stderr" }'
