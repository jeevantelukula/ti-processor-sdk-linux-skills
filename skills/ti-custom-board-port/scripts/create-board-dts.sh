#!/usr/bin/env bash
# create-board-dts.sh - start a custom board from an existing reference board.
#
# Usage: create-board-dts.sh <reference-basename> <new-basename> [--apply] [--out-dir DIR]
#   <reference-basename>  a board .dts in the SDK kernel tree, without extension
#                         (list them: ls $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/*.dts)
#   <new-basename>        name for the new board; keep the SoC prefix so the SDK
#                         'make linux-dtbs' picks it up (see KERNEL_DEVICETREE_PREFIX)
# Default is a dry run: prints what would be copied and every U-Boot file that mentions
# the reference board. --apply copies the kernel .dts (never overwrites) into --out-dir
# (default: the kernel dts/ti directory). Makefiles and defconfigs are NOT edited.
# Needs TI_KERNEL_SRC_DIR and TI_UBOOT_SRC_DIR (source lib/ti-sdk-env.sh).
set -euo pipefail

usage() { sed -n '2,12p' "$0" >&2; exit 2; }

[ $# -ge 2 ] || usage
ref=$1; new=$2; shift 2
apply=0; outdir=
while [ $# -gt 0 ]; do
    case $1 in
        --apply) apply=1 ;;
        --out-dir) shift; outdir=${1:?--out-dir needs a directory} ;;
        *) usage ;;
    esac
    shift
done

: "${TI_KERNEL_SRC_DIR:?source lib/ti-sdk-env.sh first}"
: "${TI_UBOOT_SRC_DIR:?source lib/ti-sdk-env.sh first}"
kdts=$TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti
src=$kdts/$ref.dts
[ -f "$src" ] || { echo "error: $src not found" >&2; exit 1; }
dest=${outdir:-$kdts}/$new.dts

echo "Kernel : $src"
echo "      -> $dest"
echo "Makefile line to add by hand in $kdts/Makefile (follow the existing entries for $ref):"
{ grep -n -- "$ref\.dtb" "$kdts/Makefile" || true; } | head -n 5 | sed 's/^/        existing: /'
echo "Rules.make KERNEL_DEVICETREE_PREFIX = ${TI_DTB_PREFIX:-<unset>} (the new name must match it to be built by 'make linux-dtbs')"
echo
echo "U-Boot files mentioning '$ref' (clone/adjust the ones your board needs):"
{ grep -rl -- "$ref" "$TI_UBOOT_SRC_DIR/arch/arm/dts" "$TI_UBOOT_SRC_DIR/configs" "$TI_UBOOT_SRC_DIR/board" 2>/dev/null || true; } |
    sed "s|^$TI_UBOOT_SRC_DIR/|        |" | sort
echo
echo "U-Boot-side files named after the reference (the A53 board dts is synced from the kernel into dts/upstream/src/arm64/ti):"
find "$TI_UBOOT_SRC_DIR/arch/arm/dts" "$TI_UBOOT_SRC_DIR/dts/upstream/src/arm64/ti" -maxdepth 1 \( -name "$ref.dts" -o -name "$ref-u-boot.dtsi" \) 2>/dev/null |
    sed "s|^$TI_UBOOT_SRC_DIR/|        |" | sort

if [ "$apply" -eq 1 ]; then
    [ ! -e "$dest" ] || { echo "error: $dest exists; not overwriting" >&2; exit 1; }
    mkdir -p "$(dirname "$dest")"
    cp -- "$src" "$dest"
    echo; echo "copied -> $dest"
    echo "Edit the 'model' and 'compatible' properties in $dest before building."
else
    echo; echo "(dry run; pass --apply to copy the kernel dts)"
fi
