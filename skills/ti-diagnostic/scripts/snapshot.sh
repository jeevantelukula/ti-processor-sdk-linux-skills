#!/bin/bash
# Read-only health snapshot of a TI K3 target. Prints JSON to stdout.
# Run on the target, or: ssh root@<ip> 'bash -s' < snapshot.sh
# No `set -e`: every probe is best-effort and a missing sysfs file must not abort the snapshot.
# Output is ASCII-only JSON (control and non-ASCII bytes are dropped) so it always parses.
set -uo pipefail

esc() { printf '%s' "$1" | tr -cd '\11\12\40-\176' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' | awk 'BEGIN{ORS="\\n"}{print}' | sed 's/\\n$//'; }
rd()  { [ -r "$1" ] && head -n 1 "$1" 2>/dev/null | tr -d '\000' || true; }
str() { printf '"%s"' "$(esc "$1")"; }
list() { # args: json strings
  local out="" s; for s in "$@"; do out="${out:+$out,}$s"; done; printf '[%s]' "$out"
}

compat=""
[ -r /proc/device-tree/compatible ] && compat=$(tr '\000' ' ' < /proc/device-tree/compatible 2>/dev/null)
nv() { printf '%s' "${1:-null}"; }
mem() { awk -v k="$1" '$1==k":"{print $2}' /proc/meminfo; }

thermal=()
for z in /sys/class/thermal/thermal_zone*; do
  [ -d "$z" ] || continue
  thermal+=("{\"type\":$(str "$(rd "$z/type")"),\"millicelsius\":$(rd "$z/temp" | grep -E '^-?[0-9]+$' || echo null)}")
done

cpus=()
for c in /sys/devices/system/cpu/cpu[0-9]*; do
  f="$c/cpufreq"; [ -d "$f" ] || continue
  cpus+=("{\"cpu\":$(str "$(basename "$c")"),\"cur_khz\":$(rd "$f/scaling_cur_freq" | grep -E '^[0-9]+$' || echo null),\"governor\":$(str "$(rd "$f/scaling_governor")"),\"available_khz\":$(str "$(rd "$f/scaling_available_frequencies")")}")
done

rprocs=()
for r in /sys/class/remoteproc/remoteproc*; do
  [ -d "$r" ] || continue
  rprocs+=("{\"id\":$(str "$(basename "$r")"),\"name\":$(str "$(rd "$r/name")"),\"state\":$(str "$(rd "$r/state")"),\"firmware\":$(str "$(rd "$r/firmware")")}")
done

disks=()
while read -r fs size used avail pct mnt; do
  disks+=("{\"mount\":$(str "$mnt"),\"fs\":$(str "$fs"),\"size_kb\":$size,\"avail_kb\":$avail,\"use\":$(str "$pct")}")
done < <(df -kP 2>/dev/null | awk 'NR>1 && $1 ~ /^\/dev\//')

failed=()
if command -v systemctl >/dev/null 2>&1; then
  while read -r u _; do [ -n "$u" ] && failed+=("$(str "$u")"); done < <(systemctl --failed --no-legend --plain 2>/dev/null)
fi

derr=()
while IFS= read -r l; do derr+=("$(str "$l")"); done < <(dmesg 2>/dev/null | grep -iE 'error|fail|timeout|oops|panic' | tail -n 20)

cat <<JSON
{
  "board": {"model": $(str "$(rd /proc/device-tree/model)"), "compatible": $(str "$compat")},
  "kernel": $(str "$(uname -r)"),
  "machine": $(str "$(uname -m)"),
  "uptime_s": $(awk '{print int($1)}' /proc/uptime),
  "cmdline": $(str "$(rd /proc/cmdline)"),
  "memory_kb": {"total": $(nv "$(mem MemTotal)"), "available": $(nv "$(mem MemAvailable)"), "cma_free": $(nv "$(mem CmaFree)")},
  "thermal": $(list "${thermal[@]+"${thermal[@]}"}"),
  "cpufreq": $(list "${cpus[@]+"${cpus[@]}"}"),
  "remoteproc": $(list "${rprocs[@]+"${rprocs[@]}"}"),
  "disks": $(list "${disks[@]+"${disks[@]}"}"),
  "failed_units": $(list "${failed[@]+"${failed[@]}"}"),
  "dmesg_errors": $(list "${derr[@]+"${derr[@]}"}")
}
JSON
