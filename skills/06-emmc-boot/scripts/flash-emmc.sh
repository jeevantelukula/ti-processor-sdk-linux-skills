#!/usr/bin/env bash
# Flash AM62x boot binaries and rootfs to eMMC
# Run on TARGET BOARD from an SD card boot
# Usage: flash-emmc.sh [--binaries-dir <dir>] [--rootfs <tarball>] [--device <emmc-dev>]

set -euo pipefail

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --binaries-dir <dir>    Directory containing tiboot3.bin, tispl.bin, u-boot.img"
    echo "                          Default: /tmp (copy files there first)"
    echo "  --rootfs <tarball>      Root filesystem tarball (.tar.xz)"
    echo "  --device <dev>          eMMC device (default: /dev/mmcblk0)"
    echo "  --verify-only           Only verify eMMC state, don't flash"
    exit 1
}

BINARIES_DIR="/tmp"
ROOTFS_TARBALL=""
EMMC_DEV="/dev/mmcblk0"
VERIFY_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --binaries-dir) BINARIES_DIR="$2"; shift 2 ;;
        --rootfs)       ROOTFS_TARBALL="$2"; shift 2 ;;
        --device)       EMMC_DEV="$2"; shift 2 ;;
        --verify-only)  VERIFY_ONLY=true; shift ;;
        *) usage ;;
    esac
done

echo "=== AM62x eMMC Flash Tool ==="
echo "eMMC device: ${EMMC_DEV}"
echo ""

# ── Safety checks ─────────────────────────────────────────────────────────────
if [[ ! -b "${EMMC_DEV}" ]]; then
    echo "ERROR: ${EMMC_DEV} is not a block device"
    echo "Available block devices:"
    lsblk -d | grep -v "loop\|sr"
    exit 1
fi

# Warn if this is also the boot device
ROOT_DEV=$(findmnt -n -o SOURCE / | sed 's/p[0-9]*$//')
if [[ "${ROOT_DEV}" == "${EMMC_DEV}" ]]; then
    echo "ERROR: ${EMMC_DEV} is the current root device. Cannot flash the booted device."
    echo "       Boot from SD card and flash eMMC."
    exit 1
fi

echo "Target eMMC: ${EMMC_DEV}"
echo "Size: $(blockdev --getsize64 "${EMMC_DEV}" | numfmt --to=iec)"
echo ""

if ${VERIFY_ONLY}; then
    echo "--- Verify Mode ---"
    echo "eMMC partitions:"
    lsblk "${EMMC_DEV}"
    echo ""
    echo "boot0 partition:"
    ls -la "${EMMC_DEV}boot0" 2>/dev/null || echo "  (not accessible)"
    echo ""
    echo "EXTCSD boot config:"
    mmc extcsd read "${EMMC_DEV}" 2>/dev/null | grep -A2 "BOOT_PARTITION_ENABLE" || true
    exit 0
fi

# ── Check boot binaries ───────────────────────────────────────────────────────
echo "--- Checking boot binaries in ${BINARIES_DIR} ---"
for f in tiboot3.bin tispl.bin u-boot.img; do
    if [[ -f "${BINARIES_DIR}/${f}" ]]; then
        echo "  OK: ${f} ($(du -h "${BINARIES_DIR}/${f}" | cut -f1))"
    else
        echo "  MISSING: ${BINARIES_DIR}/${f}"
        echo ""
        echo "Copy boot binaries to ${BINARIES_DIR} first:"
        echo "  scp host:/path/to/prebuilt-images/am62xx-evm/{tiboot3,tispl,u-boot}.bin ${BINARIES_DIR}/"
        exit 1
    fi
done

echo ""
read -r -p "Flash ${EMMC_DEV}? This will ERASE eMMC data. Type 'yes' to confirm: " CONFIRM
[[ "${CONFIRM}" == "yes" ]] || { echo "Aborted."; exit 0; }

# ── Flash boot0 partition ─────────────────────────────────────────────────────
echo ""
echo "--- Flashing boot0 partition ---"
BOOT0="${EMMC_DEV}boot0"

echo 0 > "/sys/block/$(basename "${EMMC_DEV}")boot0/force_ro"

# Offsets: tiboot3 @ 0, tispl @ 2048 sectors (1 MB), u-boot @ 6144 sectors (3 MB)
dd if="${BINARIES_DIR}/tiboot3.bin" of="${BOOT0}" bs=512 seek=0    status=progress conv=notrunc
dd if="${BINARIES_DIR}/tispl.bin"   of="${BOOT0}" bs=512 seek=2048 status=progress conv=notrunc
dd if="${BINARIES_DIR}/u-boot.img"  of="${BOOT0}" bs=512 seek=6144 status=progress conv=notrunc
sync

echo 1 > "/sys/block/$(basename "${EMMC_DEV}")boot0/force_ro"
echo "boot0 flashed."

# ── Configure eMMC to boot from boot0 ────────────────────────────────────────
echo ""
echo "--- Configuring eMMC boot partition ---"
if command -v mmc &>/dev/null; then
    mmc bootpart enable 1 1 "${EMMC_DEV}"
    echo "eMMC configured to boot from boot0."
else
    echo "WARNING: mmc-utils not found. Install: apt install mmc-utils"
    echo "         Manually set BOOT_PARTITION_ENABLE=1 in EXTCSD."
fi

# ── Partition eMMC UDA ────────────────────────────────────────────────────────
echo ""
echo "--- Partitioning eMMC UDA ---"
parted -s "${EMMC_DEV}" mklabel msdos
parted -s "${EMMC_DEV}" mkpart primary fat32 8MiB 264MiB
parted -s "${EMMC_DEV}" mkpart primary ext4 264MiB 100%
parted -s "${EMMC_DEV}" set 1 boot on
partprobe "${EMMC_DEV}" && sleep 2

mkfs.vfat -F 32 -n "boot" "${EMMC_DEV}p1"
mkfs.ext4 -L "rootfs" "${EMMC_DEV}p2"
echo "Partitioned."

# ── Flash boot files to FAT partition ────────────────────────────────────────
echo ""
echo "--- Copying boot files to FAT partition ---"
mkdir -p /mnt/emmc-boot
mount "${EMMC_DEV}p1" /mnt/emmc-boot

# Copy from SD card boot partition if available
SD_BOOT=$(findmnt -n -o SOURCE /boot 2>/dev/null || echo "")
if [[ -n "${SD_BOOT}" ]]; then
    cp /boot/fitImage /boot/*.dtb /boot/*.dtbo /mnt/emmc-boot/ 2>/dev/null || true
    cp /boot/extlinux.conf /mnt/emmc-boot/ 2>/dev/null || true
    echo "Copied boot files from /boot"
else
    echo "WARNING: No /boot mount found. Copy fitImage, DTBs, and extlinux.conf manually."
fi

umount /mnt/emmc-boot

# ── Flash rootfs ──────────────────────────────────────────────────────────────
if [[ -n "${ROOTFS_TARBALL}" ]]; then
    echo ""
    echo "--- Extracting rootfs to eMMC p2 ---"
    mkdir -p /mnt/emmc-rootfs
    mount "${EMMC_DEV}p2" /mnt/emmc-rootfs
    tar -xJf "${ROOTFS_TARBALL}" -C /mnt/emmc-rootfs
    sync
    umount /mnt/emmc-rootfs
    echo "rootfs extracted."
fi

echo ""
echo "=== Flash complete ==="
echo "Switch boot mode to eMMC and reboot."
echo "Expected boot message: 'Trying to boot from MMC2'"
