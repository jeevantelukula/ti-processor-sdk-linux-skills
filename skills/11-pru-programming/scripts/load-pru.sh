#!/usr/bin/env bash
# Manage PRU-ICSS firmware loading via remoteproc
# Run on TARGET BOARD
# PRU0 maps to remoteproc1, PRU1 maps to remoteproc2 (after M4F at remoteproc0)

set -euo pipefail

RPROC_BASE="/sys/class/remoteproc"
FW_DIR="/lib/firmware"

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  list                     List available remoteproc instances"
    echo "  load <rproc-id> <fw>     Load firmware (fw relative to /lib/firmware)"
    echo "  stop <rproc-id>          Stop (unload) a remote core"
    echo "  status                   Show all remoteproc status"
    echo "  trace <rproc-id>         Show trace log (PRU printf output)"
    echo "  rpmsg-test               List RPMsg char devices"
    echo ""
    echo "PRU mapping (typical AM62x):"
    echo "  remoteproc0 = M4F0     (MCU domain)"
    echo "  remoteproc1 = PRU0_0   (PRUSS0 PRU0)"
    echo "  remoteproc2 = PRU0_1   (PRUSS0 PRU1)"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 load 1 ti-pruss/am65x-pru0-prueth-fw.elf"
    echo "  $0 load 1 my-pru0-firmware.out"
    echo "  $0 stop 1"
    echo "  $0 trace 1"
    exit 1
}

[[ $# -lt 1 ]] && usage

CMD="$1"

_rproc_path() {
    local id="$1"
    echo "${RPROC_BASE}/remoteproc${id}"
}

_check_rproc() {
    local id="$1"
    local path
    path=$(_rproc_path "${id}")
    if [[ ! -d "${path}" ]]; then
        echo "ERROR: remoteproc${id} not found in ${RPROC_BASE}"
        echo "       Available:"
        ls "${RPROC_BASE}" 2>/dev/null || echo "  (none)"
        exit 1
    fi
}

case "${CMD}" in

  list)
    echo "=== Remote Processors ==="
    found=0
    for rproc_dir in "${RPROC_BASE}"/remoteproc*/; do
        [[ -d "${rproc_dir}" ]] || continue
        name=$(cat "${rproc_dir}/name" 2>/dev/null || echo "unknown")
        state=$(cat "${rproc_dir}/state" 2>/dev/null || echo "unknown")
        fw=$(cat "${rproc_dir}/firmware" 2>/dev/null || echo "none")
        id=$(basename "${rproc_dir}" | sed 's/remoteproc//')
        echo "  remoteproc${id}: ${name}"
        echo "    state:    ${state}"
        echo "    firmware: ${fw}"
        ((found++)) || true
    done
    [[ "${found}" -eq 0 ]] && echo "  (no remoteproc instances found)"
    ;;

  status)
    echo "=== RemoteProc Status ==="
    for rproc_dir in "${RPROC_BASE}"/remoteproc*/; do
        [[ -d "${rproc_dir}" ]] || continue
        id=$(basename "${rproc_dir}" | sed 's/remoteproc//')
        name=$(cat "${rproc_dir}/name" 2>/dev/null || echo "?")
        state=$(cat "${rproc_dir}/state" 2>/dev/null || echo "?")
        fw=$(cat "${rproc_dir}/firmware" 2>/dev/null || echo "none")
        printf "  [remoteproc%s] %-30s  state=%-10s  fw=%s\n" \
            "${id}" "${name}" "${state}" "${fw}"
    done
    echo ""
    echo "PRU character devices:"
    ls /dev/rpmsg* 2>/dev/null | sed 's/^/  /' || echo "  (none — PRU not running or no RPMsg channels)"
    ;;

  load)
    [[ $# -lt 3 ]] && { echo "Usage: $0 load <rproc-id> <firmware>"; exit 1; }
    RPROC_ID="$2"
    FW_NAME="$3"
    _check_rproc "${RPROC_ID}"
    RPROC_PATH=$(_rproc_path "${RPROC_ID}")

    STATE=$(cat "${RPROC_PATH}/state")
    if [[ "${STATE}" != "offline" ]]; then
        echo "ERROR: remoteproc${RPROC_ID} is in state '${STATE}', not offline."
        echo "       Stop it first: $0 stop ${RPROC_ID}"
        exit 1
    fi

    # Validate firmware file exists
    if [[ ! -f "${FW_DIR}/${FW_NAME}" ]]; then
        echo "ERROR: Firmware not found: ${FW_DIR}/${FW_NAME}"
        echo ""
        echo "Copy firmware first:"
        echo "  cp my-pru0-firmware.out /lib/firmware/"
        echo ""
        echo "Available PRU firmware in ${FW_DIR}:"
        find "${FW_DIR}" -name "*.out" -o -name "*.elf" 2>/dev/null | grep -i "pru\|pruss" | head -10 \
            || echo "  (none found)"
        exit 1
    fi

    echo "Loading: remoteproc${RPROC_ID} firmware=${FW_NAME}"
    echo "${FW_NAME}" > "${RPROC_PATH}/firmware"
    echo "start" > "${RPROC_PATH}/state"

    sleep 0.5
    NEW_STATE=$(cat "${RPROC_PATH}/state")
    if [[ "${NEW_STATE}" == "running" ]]; then
        echo "  [OK] remoteproc${RPROC_ID} running"
    else
        echo "  [FAIL] State: ${NEW_STATE}"
        echo "  Check dmesg:"
        dmesg | grep -i "remoteproc\|pru\|pruss" | tail -20
        exit 1
    fi
    ;;

  stop)
    [[ $# -lt 2 ]] && { echo "Usage: $0 stop <rproc-id>"; exit 1; }
    RPROC_ID="$2"
    _check_rproc "${RPROC_ID}"
    RPROC_PATH=$(_rproc_path "${RPROC_ID}")

    STATE=$(cat "${RPROC_PATH}/state")
    if [[ "${STATE}" == "offline" ]]; then
        echo "remoteproc${RPROC_ID} already offline."
        exit 0
    fi

    echo "Stopping remoteproc${RPROC_ID}..."
    echo "stop" > "${RPROC_PATH}/state"
    sleep 0.3
    NEW_STATE=$(cat "${RPROC_PATH}/state")
    echo "  State: ${NEW_STATE}"
    [[ "${NEW_STATE}" == "offline" ]] && echo "  [OK] Stopped" || echo "  [WARN] Unexpected state"
    ;;

  trace)
    [[ $# -lt 2 ]] && { echo "Usage: $0 trace <rproc-id>"; exit 1; }
    RPROC_ID="$2"
    _check_rproc "${RPROC_ID}"

    TRACE="/sys/kernel/debug/remoteproc/remoteproc${RPROC_ID}/trace0"
    if [[ -f "${TRACE}" ]]; then
        CONTENT=$(cat "${TRACE}")
        if [[ -z "${CONTENT}" ]]; then
            echo "(trace0 is empty — PRU may not be running or firmware has no trace buffer)"
        else
            echo "=== remoteproc${RPROC_ID} trace0 ==="
            echo "${CONTENT}"
        fi
    else
        echo "No trace0 for remoteproc${RPROC_ID}."
        echo "  debugfs may not be mounted: mount -t debugfs none /sys/kernel/debug"
        echo "  Or PRU firmware has no carveout/trace resource."
    fi
    ;;

  rpmsg-test)
    echo "=== RPMsg devices ==="
    ls -la /dev/rpmsg* 2>/dev/null || echo "  (no /dev/rpmsg* — start PRU with RPMsg resource table first)"
    echo ""
    echo "Check kernel RPMsg channels:"
    cat /sys/bus/rpmsg/devices/*/name 2>/dev/null | sort -u | sed 's/^/  /' \
        || echo "  (none registered)"
    ;;

  *)
    usage
    ;;
esac
