#!/usr/bin/env bash
# TI Processor SDK Linux Skills — Environment Setup and Validation
# Source this file: source setup.sh

set -euo pipefail

TI_SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TI_SKILLS_DIR

_ti_info()  { echo "[TI-SKILLS] $*"; }
_ti_warn()  { echo "[TI-SKILLS] WARNING: $*" >&2; }
_ti_error() { echo "[TI-SKILLS] ERROR: $*" >&2; }

# ── Detect context: host or target ──────────────────────────────────────────
_detect_context() {
    if grep -q "PROCESSOR-SDK\|am62\|am64\|sitara" /proc/device-tree/model 2>/dev/null; then
        echo "target"
    else
        echo "host"
    fi
}
export TI_CONTEXT
TI_CONTEXT=$(_detect_context)
_ti_info "Context: ${TI_CONTEXT}"

# ── Locate Processor SDK install ─────────────────────────────────────────────
_find_sdk() {
    # 1. Explicit env var
    if [[ -n "${PROCESSOR_SDK_LINUX:-}" ]] && [[ -d "${PROCESSOR_SDK_LINUX}" ]]; then
        echo "${PROCESSOR_SDK_LINUX}"
        return
    fi
    # 2. Common install locations
    for candidate in \
        "${TI_SKILLS_DIR}/../ti-processor-sdk-linux-am62xx-evm-"*/ \
        "${HOME}/ti-processor-sdk-linux-"*/ \
        "/opt/ti-processor-sdk-linux-"*/; do
        if [[ -d "${candidate}/linux-devkit" ]]; then
            echo "$(realpath "${candidate}")"
            return
        fi
    done
    echo ""
}

export PROCESSOR_SDK_LINUX
PROCESSOR_SDK_LINUX=$(_find_sdk)

if [[ -z "${PROCESSOR_SDK_LINUX}" ]]; then
    _ti_warn "Processor SDK not found. Set PROCESSOR_SDK_LINUX=/path/to/sdk"
else
    _ti_info "SDK: ${PROCESSOR_SDK_LINUX}"

    # ── Source devkit toolchain ───────────────────────────────────────────────
    DEVKIT_ENV="${PROCESSOR_SDK_LINUX}/linux-devkit/environment-setup-aarch64-oe-linux"
    if [[ -f "${DEVKIT_ENV}" ]]; then
        # shellcheck disable=SC1090
        source "${DEVKIT_ENV}"
        _ti_info "Toolchain: ${CC:-not set}"
    else
        _ti_warn "Devkit env not found: ${DEVKIT_ENV}"
    fi

    # ── SDK version ───────────────────────────────────────────────────────────
    SDK_VERSION_FILE="${PROCESSOR_SDK_LINUX}/sdk_version"
    if [[ -f "${SDK_VERSION_FILE}" ]]; then
        export TI_SDK_VERSION
        TI_SDK_VERSION=$(cat "${SDK_VERSION_FILE}")
        _ti_info "SDK Version: ${TI_SDK_VERSION}"
    fi

    # ── Prebuilt images directory ─────────────────────────────────────────────
    PREBUILT_DIRS=("${PROCESSOR_SDK_LINUX}"/board-support/prebuilt-images/*)
    if [[ ${#PREBUILT_DIRS[@]} -gt 0 ]] && [[ -d "${PREBUILT_DIRS[0]}" ]]; then
        export TI_PREBUILT_DIR="${PREBUILT_DIRS[0]}"
        _ti_info "Prebuilt images: ${TI_PREBUILT_DIR}"
    fi
fi

# ── Locate Yocto workspace ───────────────────────────────────────────────────
_find_yocto() {
    for candidate in \
        "${PROCESSOR_SDK_LINUX:-.}/../oe-layersetup" \
        "${TI_SKILLS_DIR}/../oe-layersetup" \
        "${HOME}/tisdk" \
        "${HOME}/yocto/tisdk"; do
        if [[ -f "${candidate}/oe-layertool-setup.sh" ]]; then
            echo "$(realpath "${candidate}")"
            return
        fi
    done
    echo ""
}

export TI_YOCTO_DIR
TI_YOCTO_DIR=$(_find_yocto)
if [[ -n "${TI_YOCTO_DIR}" ]]; then
    _ti_info "Yocto workspace: ${TI_YOCTO_DIR}"
    export TI_META_TI_DIR="${TI_YOCTO_DIR}/sources/meta-ti"
    export TI_META_TISDK_DIR="${TI_YOCTO_DIR}/sources/meta-tisdk"
fi

# ── Target board detection (when running on device) ──────────────────────────
if [[ "${TI_CONTEXT}" == "target" ]]; then
    if [[ -f /proc/device-tree/model ]]; then
        export TI_BOARD_MODEL
        TI_BOARD_MODEL=$(tr -d '\0' < /proc/device-tree/model)
        _ti_info "Board: ${TI_BOARD_MODEL}"
    fi
    if [[ -f /proc/device-tree/compatible ]]; then
        export TI_BOARD_COMPATIBLE
        TI_BOARD_COMPATIBLE=$(tr -d '\0' < /proc/device-tree/compatible)
    fi
fi

# ── Validate key tools ────────────────────────────────────────────────────────
_check_tool() {
    if command -v "$1" &>/dev/null; then
        _ti_info "Found: $1 ($(command -v "$1"))"
    else
        _ti_warn "Missing: $1"
    fi
}

if [[ "${TI_CONTEXT}" == "host" ]]; then
    _check_tool aarch64-oe-linux-gcc
    _check_tool dtc
    _check_tool bitbake
    _check_tool git
fi

if [[ "${TI_CONTEXT}" == "target" ]]; then
    _check_tool gpiodetect
    _check_tool gpioinfo
    _check_tool devmem2
fi

_ti_info "Environment ready. TI_SKILLS_DIR=${TI_SKILLS_DIR}"
