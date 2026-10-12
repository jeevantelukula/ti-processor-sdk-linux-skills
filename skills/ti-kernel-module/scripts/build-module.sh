#!/usr/bin/env bash
# Build an out-of-tree kernel module against the SDK kernel tree.
# Usage: build-module.sh <module-dir> [--board <user@host>] [--clean]
# Environment (exported by lib/ti-sdk-env.sh from the SDK Rules.make):
#   TI_SDK_ROOT, TI_ARCH, TI_CROSS_COMPILE        optional: KDIR (kernel tree, default below)
# The module directory needs a Kbuild or Makefile with "obj-m := <name>.o".
# --board only runs "uname -r" over ssh to compare with the tree's kernel release (read-only).
set -euo pipefail

usage() { echo "Usage: $0 <module-dir> [--board <user@host>] [--clean]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
mod=$1; shift
board=""; clean=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --board) [[ $# -ge 2 ]] || usage; board=$2; shift 2 ;;
        --clean) clean=1; shift ;;
        *) usage ;;
    esac
done

for v in TI_SDK_ROOT TI_ARCH TI_CROSS_COMPILE; do
    [[ -n ${!v:-} ]] || { echo "ERROR: $v not set; source lib/ti-sdk-env.sh first" >&2; exit 1; }
done
if [[ -n ${OECORE_TARGET_SYSROOT:-} ]]; then
    echo "ERROR: the SDK devkit environment-setup file is sourced (OECORE_TARGET_SYSROOT set)." >&2
    echo "       The TI kernel guide says not to source it when building kernel code. Use a clean shell." >&2
    exit 1
fi
[[ -d $mod ]] || { echo "ERROR: module dir $mod not found" >&2; exit 1; }
[[ -f $mod/Kbuild || -f $mod/Makefile ]] || { echo "ERROR: no Kbuild or Makefile in $mod" >&2; exit 1; }
mod=$(cd "$mod" && pwd)

kdir=${KDIR:-}
if [[ -z $kdir ]]; then
    # same lookup as LINUXKERNEL_INSTALL_DIR in the SDK Rules.make
    kdir=$(ls -d "$TI_SDK_ROOT"/board-support/ti-linux-kernel* 2>/dev/null | head -1 || true)
fi
[[ -n $kdir && -d $kdir ]] || { echo "ERROR: no kernel tree under $TI_SDK_ROOT/board-support (set KDIR)" >&2; exit 1; }
for f in .config include/generated/autoconf.h; do
    [[ -e $kdir/$f ]] || {
        echo "ERROR: $kdir/$f missing: the kernel tree is not built." >&2
        echo "       Build it first (make -C \"$TI_SDK_ROOT\" linux), or at least run:" >&2
        echo "       make -C \"$kdir\" ARCH=$TI_ARCH CROSS_COMPILE=$TI_CROSS_COMPILE modules_prepare" >&2
        exit 1
    }
done

[[ -e $kdir/Module.symvers ]] || echo "WARNING: $kdir/Module.symvers missing; modules using symbols from other modules, or CONFIG_MODVERSIONS, need a full kernel build (kernel docs, modules.rst)." >&2

rel=$(cat "$kdir/include/config/kernel.release" 2>/dev/null || echo unknown)
echo "kernel tree : $kdir"
echo "tree release: $rel"
if [[ -n $board ]]; then
    brel=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$board" uname -r)
    echo "board       : $brel"
    if [[ $brel != "$rel" ]]; then
        echo "WARNING: board kernel release differs from the tree; the built module's vermagic will not match the running kernel." >&2
    fi
fi

if [[ $clean -eq 1 ]]; then
    make -C "$kdir" M="$mod" ARCH="$TI_ARCH" CROSS_COMPILE="$TI_CROSS_COMPILE" clean
    exit 0
fi

make -C "$kdir" M="$mod" ARCH="$TI_ARCH" CROSS_COMPILE="$TI_CROSS_COMPILE" modules

shopt -s nullglob
kos=("$mod"/*.ko)
[[ ${#kos[@]} -gt 0 ]] || { echo "ERROR: build produced no .ko" >&2; exit 1; }
for ko in "${kos[@]}"; do
    echo "built: $ko"
    echo "  $(file -b "$ko" | cut -d, -f1-2)"
    if command -v modinfo >/dev/null; then echo "  vermagic: $(modinfo -F vermagic "$ko")"; fi
done
