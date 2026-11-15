#!/usr/bin/env bash
# build-dtbo.sh - compile a .dtso to .dtbo outside the kernel build, and optionally
# test-apply it to a base .dtb with fdtoverlay (same tool the kernel build uses).
#
# Usage: build-dtbo.sh <overlay.dtso> [-o out.dtbo] [-b base.dtb]
# Needs: TI_KERNEL_SRC_DIR (source lib/ti-sdk-env.sh) or KDIR=<kernel tree>; cpp; and the SDK's
# dtc (+ fdtoverlay for -b). The host's dtc is never used; DTC= / FDTOVERLAY= override the lookup.
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

# dtc and fdtoverlay come from the SDK, never from the host: a host build can be another
# version and reject or mis-build what the SDK kernel accepts. Look in the SDK kernel tree
# (present once the kernel DTBs are built), then in the SDK devkit host sysroot.
sdk=${TI_SDK_ROOT:-}
case $kdir in */board-support/*) [ -n "$sdk" ] || sdk=${kdir%%/board-support/*} ;; esac

find_sdk_tool() {
    local name=$1 c
    if [ -f "$kdir/scripts/dtc/$name" ] && [ -x "$kdir/scripts/dtc/$name" ]; then
        printf '%s\n' "$kdir/scripts/dtc/$name"; return 0
    fi
    [ -n "$sdk" ] || return 1
    for c in "$sdk"/*devkit/sysroots/x86_64-*/usr/bin/"$name" \
             "$sdk"/*devkit/sysroots/x86_64-*/usr/bin/*/"$name"; do
        if [ -f "$c" ] && [ -x "$c" ]; then printf '%s\n' "$c"; return 0; fi
    done
    return 1
}

dtc=${DTC:-}
[ -n "$dtc" ] || dtc=$(find_sdk_tool dtc) || {
    echo "error: SDK dtc not found in $kdir/scripts/dtc or ${sdk:-<TI_SDK_ROOT unset>}/*devkit/sysroots/x86_64-*/usr/bin" >&2
    echo "       build the SDK kernel DTBs (make linux-dtbs) or set DTC=<path to the SDK's dtc>" >&2
    exit 1; }
fdtoverlay=${FDTOVERLAY:-}
[ -n "$fdtoverlay" ] || fdtoverlay=$(find_sdk_tool fdtoverlay || true)

dts_dir=$kdir/arch/arm64/boot/dts
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
    -I "$(dirname "$src")" -I "$dts_dir/ti" -I "$dts_dir" -I "$kdir/include" \
    "$src" |
    "$dtc" -@ -I dts -O dtb -o "$out" -
echo "built $out ($("$dtc" --version), $dtc)"

if [ -n "$base" ]; then
    [ -f "$base" ] || { echo "error: base dtb $base not found" >&2; exit 1; }
    [ -n "$fdtoverlay" ] || {
        echo "error: SDK fdtoverlay not found (same places as dtc); set FDTOVERLAY=<path>" >&2; exit 1; }
    tmp=$(mktemp)
    trap 'rm -f "$tmp"' EXIT
    # The base DTB needs symbols (-@) so overlay labels resolve. Decompile to a file, not a
    # pipe: grep -q exiting early would SIGPIPE dtc and trip pipefail. A dtc failure is
    # reported as such, not as missing symbols.
    "$dtc" -q -I dtb -O dts -o "$tmp" "$base" || {
        echo "error: $dtc cannot read base DTB $base" >&2; exit 1; }
    grep -q '__symbols__' "$tmp" || {
        echo "error: base DTB lacks symbols (-@ flag). Rebuild with: make linux-dtbs" >&2; exit 1; }
    "$fdtoverlay" -i "$base" -o "$tmp" "$out"
    echo "OK: $out applies cleanly to $base"
fi
