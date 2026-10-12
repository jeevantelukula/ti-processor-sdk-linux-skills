#!/usr/bin/env bash
# build-dtbo.sh - compile a .dtso to .dtbo outside the kernel build, and optionally
# test-apply it to a base .dtb with fdtoverlay (same tool the kernel build uses).
#
# Usage: build-dtbo.sh <overlay.dtso> [-o out.dtbo] [-b base.dtb]
# Needs: TI_KERNEL_SRC_DIR (source lib/ti-sdk-env.sh) or KDIR=<kernel tree>; cpp; dtc.
# Include paths mirror the kernel's DTS preprocessing: <kernel>/include and
# <kernel>/arch/arm64/boot/dts[/ti] (the .dtso may #include "k3-pinctrl.h").
set -euo pipefail

usage() { echo "Usage: $0 <overlay.dtso> [-o out.dtbo] [-b base.dtb]" >&2; exit 2; }
case "${1:-}" in -h|--help) usage ;; esac

[ $# -ge 1 ] || usage
src=$1; shift
out=${src%.dtso}.dtbo
base=
while getopts "o:b:" opt; do
    case $opt in
        o) out=$OPTARG ;;
        b) base=$OPTARG ;;
        *) usage ;;
    esac
done

kdir=${KDIR:-${TI_KERNEL_SRC_DIR:-}}
[ -n "$kdir" ] && [ -d "$kdir/include/dt-bindings" ] || {
    echo "error: kernel tree not found; source lib/ti-sdk-env.sh or set KDIR" >&2; exit 1; }
[ -f "$src" ] || { echo "error: $src not found" >&2; exit 1; }

# Prefer the dtc built with the SDK kernel; fall back to the host one.
dtc=$kdir/scripts/dtc/dtc
[ -x "$dtc" ] || dtc=$(command -v dtc) || { echo "error: dtc not found" >&2; exit 1; }
fdtoverlay=$kdir/scripts/dtc/fdtoverlay
[ -x "$fdtoverlay" ] || fdtoverlay=$(command -v fdtoverlay || true)

dts_dir=$kdir/arch/arm64/boot/dts
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
    -I "$(dirname "$src")" -I "$dts_dir/ti" -I "$dts_dir" -I "$kdir/include" \
    "$src" |
    "$dtc" -@ -I dts -O dtb -o "$out" -
echo "built $out ($("$dtc" --version))"

if [ -n "$base" ]; then
    [ -f "$base" ] || { echo "error: base dtb $base not found" >&2; exit 1; }
    [ -n "$fdtoverlay" ] || { echo "error: fdtoverlay not found" >&2; exit 1; }
    # Verify base DTB has symbols (-@ flag) for label resolution
    if ! dtc -I dtb -O dts "$base" 2>/dev/null | grep -q '__symbols__'; then
        echo "error: base DTB lacks symbols (-@ flag). Rebuild with: make linux-dtbs" >&2
        exit 1
    fi
    tmp=$(mktemp)
    trap 'rm -f "$tmp"' EXIT
    "$fdtoverlay" -i "$base" -o "$tmp" "$out"
    echo "OK: $out applies cleanly to $base"
fi
