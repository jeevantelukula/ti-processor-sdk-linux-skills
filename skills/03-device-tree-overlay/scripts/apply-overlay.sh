#!/usr/bin/env bash
# Apply DT overlay at runtime via configfs, or prepare extlinux.conf for boot-time loading
# Run on TARGET BOARD

set -euo pipefail

CONFIGFS="/sys/kernel/config/device-tree/overlays"
EXTLINUX="/boot/extlinux/extlinux.conf"

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  load <dtbo>         Load overlay at runtime via configfs"
    echo "  unload <name>       Remove overlay by name (directory name in configfs)"
    echo "  list                List currently active overlays"
    echo "  check-support       Check if configfs DT overlay is available"
    echo "  add-extlinux <dtbo> Add overlay to /boot/extlinux/extlinux.conf (persistent)"
    echo ""
    echo "Examples:"
    echo "  $0 load /boot/k3-am625-sk-rpi-header-exp-brd.dtbo"
    echo "  $0 load ./my-custom-overlay.dtbo"
    echo "  $0 list"
    echo "  $0 unload k3-am625-sk-rpi-header-exp-brd"
    echo "  $0 add-extlinux /boot/my-overlay.dtbo"
    exit 1
}

[[ $# -lt 1 ]] && usage

CMD="$1"

case "${CMD}" in

  check-support)
    echo "=== Configfs DT overlay support ==="
    if [[ -d "${CONFIGFS}" ]]; then
        echo "  [OK] ${CONFIGFS} exists"
    else
        if mountpoint -q /sys/kernel/config 2>/dev/null; then
            echo "  [FAIL] configfs mounted but no device-tree/overlays directory"
            echo "         Kernel needs CONFIG_OF_OVERLAY=y and CONFIG_CONFIGFS_FS=y"
        else
            echo "  [INFO] configfs not mounted. Try:"
            echo "         mount -t configfs none /sys/kernel/config"
            echo "         Then check ${CONFIGFS}"
        fi
        exit 1
    fi
    echo ""
    echo "Available prebuilt overlays:"
    ls /boot/*.dtbo 2>/dev/null | while read -r f; do
        echo "  $(basename "${f}")"
    done
    ;;

  list)
    echo "=== Active DT overlays ==="
    if [[ -d "${CONFIGFS}" ]]; then
        count=0
        for dir in "${CONFIGFS}"/*/; do
            [[ -d "${dir}" ]] || continue
            name=$(basename "${dir}")
            status=$(cat "${dir}/status" 2>/dev/null || echo "unknown")
            echo "  ${name}: ${status}"
            ((count++)) || true
        done
        [[ "${count}" -eq 0 ]] && echo "  (none loaded via configfs)"
    else
        echo "  configfs not available — see 'check-support'"
    fi
    ;;

  load)
    [[ $# -lt 2 ]] && { echo "Usage: $0 load <dtbo-file>"; exit 1; }
    DTBO="$2"
    [[ -f "${DTBO}" ]] || { echo "ERROR: File not found: ${DTBO}"; exit 1; }

    if [[ ! -d "${CONFIGFS}" ]]; then
        echo "ERROR: ${CONFIGFS} not available"
        echo "       Kernel may need CONFIG_OF_OVERLAY=y"
        exit 1
    fi

    NAME=$(basename "${DTBO}" .dtbo)
    OVERLAY_DIR="${CONFIGFS}/${NAME}"

    if [[ -d "${OVERLAY_DIR}" ]]; then
        echo "WARNING: Overlay '${NAME}' already loaded. Unload first if replacing."
        exit 1
    fi

    echo "Loading overlay: ${NAME}"
    mkdir "${OVERLAY_DIR}"
    cp "${DTBO}" "${OVERLAY_DIR}/dtbo"

    STATUS=$(cat "${OVERLAY_DIR}/status" 2>/dev/null || echo "unknown")
    if [[ "${STATUS}" == "applied" ]]; then
        echo "  [OK] Overlay applied: ${NAME}"
    else
        echo "  [FAIL] Status: ${STATUS}"
        echo "         Check 'dmesg | tail -30' for errors"
        rmdir "${OVERLAY_DIR}" 2>/dev/null || true
        exit 1
    fi
    ;;

  unload)
    [[ $# -lt 2 ]] && { echo "Usage: $0 unload <overlay-name>"; exit 1; }
    NAME="$2"
    # Strip .dtbo extension if provided
    NAME="${NAME%.dtbo}"
    OVERLAY_DIR="${CONFIGFS}/${NAME}"

    if [[ ! -d "${OVERLAY_DIR}" ]]; then
        echo "ERROR: No overlay '${NAME}' in configfs."
        echo "       Active overlays:"
        ls "${CONFIGFS}" 2>/dev/null || echo "  (configfs not available)"
        exit 1
    fi

    echo "Removing overlay: ${NAME}"
    rmdir "${OVERLAY_DIR}"
    echo "  [OK] Overlay removed"
    ;;

  add-extlinux)
    [[ $# -lt 2 ]] && { echo "Usage: $0 add-extlinux <dtbo-file>"; exit 1; }
    DTBO="$2"
    DTBO_NAME=$(basename "${DTBO}")

    if [[ ! -f "${EXTLINUX}" ]]; then
        echo "ERROR: ${EXTLINUX} not found."
        echo "       Make sure the boot partition is mounted at /boot."
        exit 1
    fi

    # Check if FDTOVERLAYS line already exists
    if grep -q "FDTOVERLAYS" "${EXTLINUX}"; then
        # Append to existing FDTOVERLAYS line
        CURRENT=$(grep "FDTOVERLAYS" "${EXTLINUX}" | sed 's/.*FDTOVERLAYS //')
        if echo "${CURRENT}" | grep -qF "${DTBO_NAME}"; then
            echo "Overlay ${DTBO_NAME} already in FDTOVERLAYS."
            grep "FDTOVERLAYS" "${EXTLINUX}"
        else
            sed -i "s|FDTOVERLAYS .*|& /${DTBO_NAME}|" "${EXTLINUX}"
            echo "  [OK] Added ${DTBO_NAME} to FDTOVERLAYS"
            grep "FDTOVERLAYS" "${EXTLINUX}"
        fi
    else
        # Add FDTOVERLAYS line after FDTFILE line or after KERNEL line
        if grep -q "^    FDTFILE" "${EXTLINUX}"; then
            sed -i "/^    FDTFILE/a\\    FDTOVERLAYS /${DTBO_NAME}" "${EXTLINUX}"
        else
            echo "    FDTOVERLAYS /${DTBO_NAME}" >> "${EXTLINUX}"
        fi
        echo "  [OK] Added FDTOVERLAYS /${DTBO_NAME} to ${EXTLINUX}"
    fi

    echo ""
    echo "Current extlinux.conf:"
    cat "${EXTLINUX}"
    echo ""
    echo "Reboot to apply. Make sure ${DTBO_NAME} is in /boot."
    ;;

  *)
    usage
    ;;
esac
