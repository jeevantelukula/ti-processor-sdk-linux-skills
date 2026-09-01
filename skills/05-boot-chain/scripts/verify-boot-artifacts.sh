#!/usr/bin/env bash
# Verify all required boot artifacts are present for AM62x SD card boot
# Run from the SDK root directory

set -euo pipefail

PASS=0
FAIL=0

_pass() { echo "  [OK]     $*"; ((PASS++)) || true; }
_fail() { echo "  [MISSING] $*"; ((FAIL++)) || true; }

# Find prebuilt images directory
SDK_ROOT="${PROCESSOR_SDK_LINUX:-$(pwd)}"
PREBUILT=""
for d in "${SDK_ROOT}/board-support/prebuilt-images/"*/; do
    [[ -d "${d}" ]] && PREBUILT="${d}" && break
done

if [[ -z "${PREBUILT}" ]]; then
    echo "ERROR: Cannot find prebuilt-images directory."
    echo "       Set PROCESSOR_SDK_LINUX or run from SDK root."
    exit 1
fi

echo "=== Boot Artifact Check ==="
echo "Prebuilt dir: ${PREBUILT}"
echo ""

echo "--- Required Boot Binaries ---"
for f in tiboot3.bin tispl.bin u-boot.img; do
    if [[ -f "${PREBUILT}/${f}" ]]; then
        SIZE=$(du -h "${PREBUILT}/${f}" | cut -f1)
        _pass "${f} (${SIZE})"
    else
        _fail "${f}"
    fi
done

echo ""
echo "--- FIT Image / Kernel ---"
if [[ -f "${PREBUILT}/fitImage" ]]; then
    SIZE=$(du -h "${PREBUILT}/fitImage" | cut -f1)
    _pass "fitImage (${SIZE})"
    # Verify FIT image validity
    if command -v dumpimage &>/dev/null; then
        CONFIGS=$(dumpimage -l "${PREBUILT}/fitImage" 2>/dev/null | grep "Image.*:" | wc -l)
        echo "         Contains ${CONFIGS} image(s)"
    fi
else
    _fail "fitImage"
fi

echo ""
echo "--- Device Tree Blobs ---"
DTB_COUNT=0
for f in "${PREBUILT}"/*.dtb; do
    [[ -f "${f}" ]] && { _pass "$(basename "${f}")"; ((DTB_COUNT++)) || true; }
done
[[ "${DTB_COUNT}" -eq 0 ]] && _fail "No .dtb files found"

echo ""
echo "--- DT Overlays ---"
DTBO_COUNT=0
for f in "${PREBUILT}"/*.dtbo; do
    [[ -f "${f}" ]] && ((DTBO_COUNT++)) || true
done
if [[ "${DTBO_COUNT}" -gt 0 ]]; then
    _pass "${DTBO_COUNT} .dtbo overlay(s) available"
else
    echo "  [INFO]   No .dtbo overlays (optional)"
fi

echo ""
echo "--- HS Variants ---"
for f in tiboot3-hs-fs.bin tiboot3-gp.bin; do
    if [[ -f "${PREBUILT}/${f}" ]]; then
        _pass "${f}"
    else
        echo "  [INFO]   ${f} not present (use tiboot3.bin for default SK variant)"
    fi
done

echo ""
echo "=== Summary ==="
echo "  Found: ${PASS}  Missing: ${FAIL}"
if [[ "${FAIL}" -eq 0 ]]; then
    echo ""
    echo "  All required boot artifacts present."
    echo "  Flash to SD card:"
    echo "    cp ${PREBUILT}/tiboot3.bin ${PREBUILT}/tispl.bin ${PREBUILT}/u-boot.img"
    echo "       ${PREBUILT}/fitImage ${PREBUILT}/*.dtb /media/\$USER/boot/"
else
    echo ""
    echo "  Missing artifacts — rebuild with Yocto:"
    echo "    MACHINE=am62xx-evm bitbake u-boot-ti-staging linux-ti-staging"
fi
