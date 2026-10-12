#!/usr/bin/env bash
# List the boot binaries in an SDK's board-support/built-images (or prebuilt-images) and optionally compare them with the
# files on a boot partition (mounted on the host, or copied from the board).
# Usage: verify-boot-artifacts.sh [--boot-dir <dir>]
# Environment: TI_SDK_ROOT (else discovered via lib/ti-sdk-env.sh). Read-only; changes nothing.
# Exit: 0 all required files present (and equal if --boot-dir given), 1 otherwise.
set -euo pipefail

bootdir=""
if [[ ${1:-} == "--boot-dir" ]]; then
    [[ -n ${2:-} && -d ${2:-} ]] || { echo "ERROR: --boot-dir needs an existing directory" >&2; exit 2; }
    bootdir=$2; shift 2
fi
[[ $# -eq 0 ]] || { echo "Usage: $0 [--boot-dir <dir>]" >&2; exit 2; }
if [[ -z ${TI_SDK_ROOT:-} ]]; then
    # Not exported by the caller: load the SDK values ourselves (discovery: TI_SDK_ROOT, PROCESSOR_SDK_LINUX, cwd).
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    env_lib=${TI_SKILLS_DIR:-$(cd "$here/../../.." && pwd)}/lib/ti-sdk-env.sh
    # shellcheck disable=SC1090
    [[ -f $env_lib ]] && source "$env_lib" 2>/dev/null || true
fi
[[ -n ${TI_SDK_ROOT:-} ]] || { echo "ERROR: no SDK found; set TI_SDK_ROOT to the SDK directory" >&2; exit 1; }
bs=$TI_SDK_ROOT/board-support
img=$bs/built-images
if ! compgen -G "$img/tiboot3*.bin" >/dev/null; then
    # SDKs without built-images: use the first prebuilt-images directory that has tiboot3*.bin
    for d in "$bs"/prebuilt-images "$bs"/prebuilt-images/*/; do
        if compgen -G "$d/tiboot3*.bin" >/dev/null; then img=${d%/}; break; fi
    done
fi
if ! compgen -G "$img/tiboot3*.bin" >/dev/null && compgen -G "$TI_SDK_ROOT/board-support/prebuilt-images/*/MLO*" >/dev/null; then
    echo "This SDK uses the legacy SPL flow (MLO + u-boot.img in board-support/prebuilt-images/<platform>/), not the K3 tiboot3/tispl flow."
    ls "$TI_SDK_ROOT"/board-support/prebuilt-images/*/{MLO*,u-boot*.img} 2>/dev/null
    exit 0
fi
[[ -d $img ]] || { echo "ERROR: $img not found" >&2; exit 1; }

rc=0
sum() { sha256sum "$1" | cut -c1-12; }

shopt -s nullglob
tiboot3_all=("$img"/tiboot3*.bin)
if [[ ${#tiboot3_all[@]} -gt 0 ]]; then
    flow="K3 (tiboot3.bin, tispl.bin, u-boot.img)"
    required=(tiboot3.bin tispl.bin u-boot.img)
else
    flow="unknown: no tiboot3*.bin in built-images"
    required=()
fi
echo "SDK         : $TI_SDK_ROOT"
echo "images dir  : $img"
echo "boot flow   : $flow"

echo "== files in built-images"
for f in "$img"/tiboot3*.bin "$img"/tispl*.bin "$img"/u-boot*.img "$img"/fitImage "$img"/Image; do
    [[ -e $f ]] && printf '  %-34s %10s bytes  sha256:%s\n' "$(basename "$f")" "$(stat -c %s "$f")" "$(sum "$f")"
done

echo "== required"
for f in "${required[@]}"; do
    if [[ -e $img/$f ]]; then echo "  [OK]      $f"; else echo "  [MISSING] $f"; rc=1; fi
done

if [[ -e $img/tiboot3.bin ]]; then
    echo "== tiboot3.bin equals which variant?"
    me=$(sum "$img/tiboot3.bin"); found=0
    for v in "${tiboot3_all[@]}"; do
        [[ $(basename "$v") == tiboot3.bin ]] && continue
        if [[ $(sum "$v") == "$me" ]]; then echo "  identical to $(basename "$v")"; found=1; fi
    done
    [[ $found -eq 1 ]] || echo "  no named variant is identical"
    echo "  (pick the variant for your device's security type: GP, HS-FS or HS-SE; see SKILL.md)"
fi

if [[ -n $bootdir ]]; then
    echo "== compare with $bootdir"
    for f in "${required[@]}"; do
        if [[ ! -e $bootdir/$f ]]; then echo "  [MISSING on boot dir] $f"; rc=1
        elif cmp -s "$img/$f" "$bootdir/$f"; then echo "  [SAME]      $f"
        else echo "  [DIFFERENT] $f  (sdk $(sum "$img/$f") vs boot $(sum "$bootdir/$f")): do not mix boot binaries from different builds"; rc=1; fi
    done
fi
exit $rc
