#!/usr/bin/env bash
# Inspect and control remoteproc instances through sysfs. Run ON THE BOARD, e.g.
#   ssh root@<board-ip> 'bash -s -- list' < rproc.sh
# Commands:
#   list              id, name, state, firmware for every instance (read-only)
#   trace <id>        print debugfs trace* of an instance (read-only)
#   load <id> <fw>    stop if running, set firmware, start. <fw> is a path relative
#                     to the firmware directory (/lib/firmware), as the driver requests it
#   stop <id>         echo stop > state
# <id> is the directory name, e.g. remoteproc0. Instances in state "attached" (firmware
# started by the bootloader) are never modified.
# Test hooks: RPROC_SYSFS, RPROC_DEBUGFS, RPROC_FWDIR override the default paths.
set -euo pipefail

RP=${RPROC_SYSFS:-/sys/class/remoteproc}
FW=${RPROC_FWDIR:-/lib/firmware}
DBG=${RPROC_DEBUGFS:-/sys/kernel/debug/remoteproc}

usage() {
    echo "Usage: $0 list | trace <id> | load <id> <fw> | stop <id>" >&2
    exit 2
}
rd() { cat "$1" 2>/dev/null || echo "?"; }
need() {
    [[ $1 =~ ^remoteproc[0-9]+$ ]] || { echo "ERROR: id must look like remoteproc0, got: $1" >&2; exit 2; }
    [[ -d "$RP/$1" ]] || { echo "ERROR: $RP/$1 not found (run 'list')" >&2; exit 1; }; }
guard() {
    local st
    st=$(rd "$RP/$1/state")
    if [[ "$st" == "attached" ]]; then
        echo "ERROR: $1 is 'attached' (firmware started by the bootloader); refusing to change it" >&2
        exit 1
    fi
}

[[ $# -ge 1 ]] || usage
case "$1" in
list)
    [[ -d $RP ]] || { echo "ERROR: $RP missing: no remoteproc driver bound" >&2; exit 1; }
    printf '%-14s %-22s %-10s %s\n' ID NAME STATE FIRMWARE
    found=0
    for d in "$RP"/remoteproc*; do
        [[ -d $d ]] || continue
        found=1
        printf '%-14s %-22s %-10s %s\n' "$(basename "$d")" "$(rd "$d/name")" "$(rd "$d/state")" "$(rd "$d/firmware")"
    done
    [[ $found -eq 1 ]] || echo "(no remoteproc instances)"
    ;;
trace)
    [[ $# -eq 2 ]] || usage
    need "$2"
    shopt -s nullglob
    files=("$DBG/$2"/trace*)
    [[ ${#files[@]} -gt 0 ]] || { echo "ERROR: no $DBG/$2/trace* (debugfs mounted? running as root?)" >&2; exit 1; }
    for t in "${files[@]}"; do echo "== $t"; cat "$t"; done
    ;;
load)
    [[ $# -eq 3 ]] || usage
    need "$2"
    guard "$2"
    case $3 in /*|*..*) echo "ERROR: <fw> must be a path relative to $FW without '..': $3" >&2; exit 2 ;; esac
    [[ -e "$FW/$3" ]] || { echo "ERROR: $FW/$3 not found (broken symlink?)" >&2; exit 1; }
    case $(rd "$RP/$2/state") in running|crashed|suspended)
        echo "stopping $2"
        echo stop > "$RP/$2/state" ;;
    esac
    echo "$3" > "$RP/$2/firmware"
    echo start > "$RP/$2/state"
    echo "$2: state=$(rd "$RP/$2/state") firmware=$(rd "$RP/$2/firmware")"
    ;;
stop)
    [[ $# -eq 2 ]] || usage
    need "$2"
    guard "$2"
    echo stop > "$RP/$2/state"
    echo "$2: state=$(rd "$RP/$2/state")"
    ;;
*) usage ;;
esac
