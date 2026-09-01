#!/usr/bin/env bash
# Load M4F/R5F firmware via Linux remoteproc (run on target board)
# Usage: load-firmware.sh [--core <name>] [--fw <filename>] [--stop]

set -euo pipefail

RPROC_DIR="/sys/class/remoteproc"
FW_DIR="/lib/firmware"

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --list              List all remoteproc cores and their state"
    echo "  --load <rproc> <fw> Load firmware <fw> onto core <rproc>"
    echo "                      e.g.: --load remoteproc0 am62-mcu-m4f0_0-fw"
    echo "  --stop <rproc>      Stop a running remote core"
    echo "  --trace <rproc>     Print trace log from remote core"
    echo "  --status <rproc>    Show current state of a remote core"
    exit 1
}

list_cores() {
    echo "=== Remote Processor Cores ==="
    for rp in "${RPROC_DIR}"/remoteproc*; do
        NAME=$(cat "${rp}/name" 2>/dev/null || echo "unknown")
        STATE=$(cat "${rp}/state" 2>/dev/null || echo "unknown")
        FW=$(cat "${rp}/firmware" 2>/dev/null || echo "none")
        printf "  %-20s  name=%-30s  state=%-10s  fw=%s\n" \
            "$(basename "${rp}")" "${NAME}" "${STATE}" "${FW}"
    done
}

load_fw() {
    local RPROC="$1"
    local FW="$2"
    local RPROC_PATH="${RPROC_DIR}/${RPROC}"

    [[ -d "${RPROC_PATH}" ]] || { echo "ERROR: ${RPROC} not found"; exit 1; }
    [[ -f "${FW_DIR}/${FW}" ]] || { echo "ERROR: /lib/firmware/${FW} not found"; exit 1; }

    STATE=$(cat "${RPROC_PATH}/state")
    if [[ "${STATE}" == "running" ]]; then
        echo "Core ${RPROC} is running — stopping first..."
        echo stop > "${RPROC_PATH}/state"
        sleep 1
    fi

    echo "Loading firmware: ${FW} onto ${RPROC}"
    echo "${FW}" > "${RPROC_PATH}/firmware"
    echo start > "${RPROC_PATH}/state"

    sleep 1
    STATE=$(cat "${RPROC_PATH}/state")
    if [[ "${STATE}" == "running" ]]; then
        echo "SUCCESS: ${RPROC} is running (firmware: ${FW})"
    else
        echo "FAILED: ${RPROC} state = ${STATE}"
        echo "Check dmesg for errors:"
        dmesg | grep -i "remoteproc\|$(cat "${RPROC_PATH}/name")" | tail -20
        exit 1
    fi
}

stop_core() {
    local RPROC="$1"
    local RPROC_PATH="${RPROC_DIR}/${RPROC}"
    [[ -d "${RPROC_PATH}" ]] || { echo "ERROR: ${RPROC} not found"; exit 1; }

    STATE=$(cat "${RPROC_PATH}/state")
    if [[ "${STATE}" != "running" ]]; then
        echo "Core ${RPROC} is not running (state: ${STATE})"
    else
        echo stop > "${RPROC_PATH}/state"
        echo "Stopped ${RPROC}"
    fi
}

print_trace() {
    local RPROC="$1"
    local TRACE="/sys/kernel/debug/remoteproc/${RPROC}/trace0"
    if [[ -f "${TRACE}" ]]; then
        echo "=== Trace log for ${RPROC} ==="
        cat "${TRACE}"
    else
        echo "No trace log for ${RPROC} (firmware may not have debug logging enabled)"
    fi
}

show_status() {
    local RPROC="$1"
    local RPROC_PATH="${RPROC_DIR}/${RPROC}"
    echo "Name:     $(cat "${RPROC_PATH}/name" 2>/dev/null)"
    echo "State:    $(cat "${RPROC_PATH}/state" 2>/dev/null)"
    echo "Firmware: $(cat "${RPROC_PATH}/firmware" 2>/dev/null)"
}

[[ $# -eq 0 ]] && { list_cores; exit 0; }

case "$1" in
    --list)   list_cores ;;
    --load)   [[ $# -ge 3 ]] || usage; load_fw "$2" "$3" ;;
    --stop)   [[ $# -ge 2 ]] || usage; stop_core "$2" ;;
    --trace)  [[ $# -ge 2 ]] || usage; print_trace "$2" ;;
    --status) [[ $# -ge 2 ]] || usage; show_status "$2" ;;
    *)        usage ;;
esac
