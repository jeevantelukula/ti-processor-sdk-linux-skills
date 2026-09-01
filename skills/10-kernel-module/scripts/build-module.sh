#!/usr/bin/env bash
# Cross-compile an out-of-tree kernel module for AM62x
# Usage: build-module.sh [--kernel-dir <path>] [--module-dir <path>]
#        Run after sourcing the TI SDK devkit environment

set -euo pipefail

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --kernel-dir <path>   Path to kernel source with modules_prepare done"
    echo "                        Default: auto-detect from PROCESSOR_SDK_LINUX"
    echo "  --module-dir <path>   Directory containing module source (default: .)"
    echo "  --install <target>    scp target for deploy, e.g. root@192.168.1.100"
    echo "  --clean               Clean module build artifacts"
    echo ""
    echo "Environment required (source devkit first):"
    echo "  CROSS_COMPILE=aarch64-oe-linux-"
    echo "  CC=aarch64-oe-linux-gcc ..."
    echo ""
    echo "Example:"
    echo "  source /opt/ti-sdk/linux-devkit/environment-setup-aarch64-oe-linux"
    echo "  $0 --kernel-dir /opt/ti-sdk/board-support/ti-linux-kernel-6.18.38/"
    exit 1
}

KERNEL_DIR=""
MODULE_DIR="$(pwd)"
INSTALL_TARGET=""
CLEAN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --kernel-dir)  KERNEL_DIR="$2"; shift 2 ;;
        --module-dir)  MODULE_DIR="$2"; shift 2 ;;
        --install)     INSTALL_TARGET="$2"; shift 2 ;;
        --clean)       CLEAN=true; shift ;;
        -h|--help)     usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ── Validate cross-compile environment ───────────────────────────────────────
echo "=== AM62x Kernel Module Build ==="
echo ""
echo "--- Environment Check ---"
if [[ -z "${CROSS_COMPILE:-}" ]]; then
    echo "ERROR: CROSS_COMPILE not set."
    echo "       Source the devkit:"
    echo "       source <sdk>/linux-devkit/environment-setup-aarch64-oe-linux"
    exit 1
fi

if ! echo "${CROSS_COMPILE}" | grep -q "aarch64"; then
    echo "WARNING: CROSS_COMPILE does not look like aarch64: ${CROSS_COMPILE}"
fi
echo "  CROSS_COMPILE = ${CROSS_COMPILE}"
echo "  CC            = ${CC:-not set}"
echo ""

# ── Find kernel directory ─────────────────────────────────────────────────────
if [[ -z "${KERNEL_DIR}" ]]; then
    SDK_ROOT="${PROCESSOR_SDK_LINUX:-}"
    if [[ -n "${SDK_ROOT}" && -d "${SDK_ROOT}" ]]; then
        KERNEL_DIR=$(find "${SDK_ROOT}/board-support" -maxdepth 1 -name "ti-linux-kernel-*" -type d 2>/dev/null | head -1)
    fi
fi

if [[ -z "${KERNEL_DIR}" || ! -d "${KERNEL_DIR}" ]]; then
    echo "ERROR: Kernel source directory not found."
    echo "       Specify with --kernel-dir or set PROCESSOR_SDK_LINUX."
    exit 1
fi

echo "Kernel:     ${KERNEL_DIR}"
echo "Module src: ${MODULE_DIR}"
echo ""

# ── Check modules_prepare ─────────────────────────────────────────────────────
if [[ ! -f "${KERNEL_DIR}/scripts/recordmcount" ]]; then
    echo "--- Running modules_prepare ---"
    make -C "${KERNEL_DIR}" \
        ARCH=arm64 \
        CROSS_COMPILE="${CROSS_COMPILE}" \
        modules_prepare
    echo "  modules_prepare done."
    echo ""
fi

# ── Validate module directory has Kbuild/Makefile ────────────────────────────
if [[ ! -f "${MODULE_DIR}/Kbuild" && ! -f "${MODULE_DIR}/Makefile" ]]; then
    echo "ERROR: No Kbuild or Makefile found in ${MODULE_DIR}"
    echo ""
    echo "Minimal Kbuild example:"
    echo "  obj-m := my_module.o"
    echo ""
    echo "Minimal Makefile example:"
    cat << 'MAKEFILE_EXAMPLE'
  KERNEL_DIR ?= /path/to/kernel
  ARCH       ?= arm64

  all:
      $(MAKE) -C $(KERNEL_DIR) M=$(PWD) ARCH=$(ARCH) CROSS_COMPILE=$(CROSS_COMPILE) modules

  clean:
      $(MAKE) -C $(KERNEL_DIR) M=$(PWD) clean
MAKEFILE_EXAMPLE
    exit 1
fi

# ── Clean if requested ────────────────────────────────────────────────────────
if ${CLEAN}; then
    echo "--- Clean ---"
    make -C "${KERNEL_DIR}" \
        M="${MODULE_DIR}" \
        ARCH=arm64 \
        CROSS_COMPILE="${CROSS_COMPILE}" \
        clean
    echo "  Clean done."
    exit 0
fi

# ── Build ─────────────────────────────────────────────────────────────────────
echo "--- Building module ---"
make -C "${KERNEL_DIR}" \
    M="${MODULE_DIR}" \
    ARCH=arm64 \
    CROSS_COMPILE="${CROSS_COMPILE}" \
    modules

echo ""
echo "--- Build artifacts ---"
MODULES=$(find "${MODULE_DIR}" -name "*.ko" 2>/dev/null)
if [[ -z "${MODULES}" ]]; then
    echo "  ERROR: No .ko files generated. Check build output above."
    exit 1
fi

for ko in ${MODULES}; do
    echo "  Built: ${ko}"
    file "${ko}"
done

echo ""

# ── Deploy to target ──────────────────────────────────────────────────────────
if [[ -n "${INSTALL_TARGET}" ]]; then
    echo "--- Deploying to ${INSTALL_TARGET} ---"
    for ko in ${MODULES}; do
        KO_NAME=$(basename "${ko}")
        scp "${ko}" "${INSTALL_TARGET}:/tmp/${KO_NAME}"
        echo "  Copied: ${KO_NAME}"
    done
    echo ""
    echo "On target, run:"
    for ko in ${MODULES}; do
        KO_NAME=$(basename "${ko}")
        echo "  insmod /tmp/${KO_NAME}"
    done
    echo "  # Or: modprobe after: depmod -a && modprobe <module-name>"
else
    echo "To deploy to target:"
    for ko in ${MODULES}; do
        KO_NAME=$(basename "${ko}")
        echo "  scp ${ko} root@<target-ip>:/tmp/${KO_NAME}"
        echo "  # On target: insmod /tmp/${KO_NAME}"
    done
fi
