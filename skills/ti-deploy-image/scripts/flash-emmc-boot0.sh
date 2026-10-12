#!/usr/bin/env bash
# Write boot images into an eMMC hardware boot partition from Linux, then read them back.
# Implements the "Flash from Linux" dd procedure of the TI docs page
# linux/How_to_Guides/Target/How_to_emmc_boot.html. Runs ON THE TARGET (as root), normally
# booted from SD. The sector offsets are SoC specific: take them from that page for your device;
# this script has no defaults on purpose.
#
# Usage:
#   flash-emmc-boot0.sh --emmc /dev/mmcblkN --part boot0|boot1 \
#       --image FILE:SECTOR_OFFSET [--image FILE:SECTOR_OFFSET ...] [--dry-run]
#
# SECTOR_OFFSET is in 512-byte sectors (the dd "seek" value with bs=512).
set -euo pipefail

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-1}"; }

emmc= part= dry=0
images=()
while [ $# -gt 0 ]; do
    case $1 in
        --emmc) emmc=${2:?}; shift 2 ;;
        --part) part=${2:?}; shift 2 ;;
        --image) images+=("${2:?}"); shift 2 ;;
        --dry-run) dry=1; shift ;;
        -h|--help) usage 0 ;;
        *) echo "unknown option: $1" >&2; usage ;;
    esac
done
[ -n "$emmc" ] && [ -n "$part" ] && [ "${#images[@]}" -gt 0 ] || usage
case $part in boot0|boot1) ;; *) echo "--part must be boot0 or boot1" >&2; exit 1 ;; esac

name=$(basename "$emmc")
bootdev=/dev/${name}${part}
ro=/sys/block/${name}${part}/force_ro

[ -b "$emmc" ] || { echo "not a block device: $emmc" >&2; exit 1; }
[ -b "$bootdev" ] || { echo "no $bootdev: $emmc has no eMMC hardware boot partitions" >&2; exit 1; }
[ -w "$ro" ] || { echo "cannot write $ro (run as root)" >&2; exit 1; }

# Refuse to touch the device that holds the running root filesystem.
rootsrc=$(findmnt -n -o SOURCE / || true)
case $rootsrc in "$emmc"*) echo "root filesystem is on $emmc; boot from SD to flash it" >&2; exit 1 ;; esac

for spec in "${images[@]}"; do
    f=${spec%:*} off=${spec##*:}
    [ -f "$f" ] || { echo "missing file: $f" >&2; exit 1; }
    case $off in ''|*[!0-9]*) echo "offset must be decimal sectors: $spec" >&2; exit 1 ;; esac
done

run() { if [ "$dry" -eq 1 ]; then echo "DRY: $*"; else "$@"; fi; }

echo "target: $bootdev (force_ro currently $(cat "$ro"))"
prev_ro=$(cat "$ro")
run sh -c "echo 0 > $ro"
for spec in "${images[@]}"; do
    f=${spec%:*} off=${spec##*:}
    echo "write $f -> $bootdev at sector $off"
    run dd if="$f" of="$bootdev" seek="$off" bs=512 conv=fsync status=none
done
run sync

# Read back and compare exactly the bytes written.
for spec in "${images[@]}"; do
    f=${spec%:*} off=${spec##*:}
    size=$(stat -c %s "$f")
    sectors=$(( (size + 511) / 512 ))
    if [ "$dry" -eq 1 ]; then
        echo "DRY: verify $f against $bootdev sector $off (+$sectors sectors)"
    elif dd if="$bootdev" bs=512 skip="$off" count="$sectors" status=none | cmp -n "$size" - "$f"; then
        echo "verify OK: $f"
    else
        echo "verify FAILED: $f" >&2
        run sh -c "echo $prev_ro > $ro"
        exit 1
    fi
done
run sh -c "echo $prev_ro > $ro"
echo "done. Next: set EXT_CSD boot config from U-Boot (docs: mmc partconf / mmc bootbus)."
