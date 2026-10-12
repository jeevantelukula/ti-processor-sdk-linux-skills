#!/usr/bin/env bash
# gpio-test.sh - thin wrapper over the libgpiod v2 command-line tools. Run ON THE TARGET.
# Verified syntax: gpiodetect, gpioinfo [-c chip] [line...], gpioget --numeric -c chip line,
# gpioset -c chip line=value (holds the line until killed), gpiomon -c chip -n N line.
# Chip names/line numbers/line names come from the board; nothing is hard-coded here.
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage:
  gpio-test.sh list                              chips, then lines that have a name or a consumer
  gpio-test.sh info  [chip]                      full gpioinfo for one chip (or all chips)
  gpio-test.sh find  <name>                      lines whose name or consumer contains <name>
  gpio-test.sh read  <chip> <line>               read a line as input (prints 0 or 1)
  gpio-test.sh write <chip> <line> <0|1> [secs]  drive a line (default hold 5 s; GPIO is released on exit)
  gpio-test.sh watch <chip> <line> [events]      print edge events (default 10 events)
chip = gpiochipN or the chip name shown by gpiodetect; line = offset shown by gpioinfo.
EOF
    exit 2
}

need() { command -v "$1" >/dev/null 2>&1 || { echo "error: '$1' not found (package libgpiod tools)" >&2; exit 1; }; }

check_v2() {
    need gpioget
    local v
    v=$(gpioget --version 2>&1 | head -n1)
    case "$v" in
        *" v2."*|*" v3."*) ;;
        *) echo "error: libgpiod v2 CLI required (found: $v). v1 uses different syntax; not covered here." >&2; exit 1 ;;
    esac
}

[ $# -ge 1 ] || usage
cmd=$1; shift

case "$cmd" in
    list)
        need gpiodetect; need gpioinfo
        gpiodetect
        echo "--- named or in-use lines ---"
        gpioinfo | grep -E '^gpiochip|"' || true
        ;;
    info)
        need gpioinfo
        if [ $# -ge 1 ]; then gpioinfo -c "$1"; else gpioinfo; fi
        ;;
    find)
        [ $# -eq 1 ] || usage
        need gpioinfo
        gpioinfo | grep -i -- "$1" || echo "no line matching '$1'"
        ;;
    read)
        [ $# -eq 2 ] || usage
        check_v2
        gpioget --numeric -c "$1" "$2"
        ;;
    write)
        [ $# -ge 3 ] && [ $# -le 4 ] || usage
        case "$3" in 0|1) ;; *) echo "error: value must be 0 or 1" >&2; exit 2 ;; esac
        check_v2; need gpioset; need timeout
        hold=${4:-5}
        echo "driving chip=$1 line=$2 value=$3 for ${hold}s" >&2
        gpioset -z -c "$1" "$2=$3" &
        pid=$!
        sleep "$hold"
        kill "$pid" 2>/dev/null || true
        ;;
    watch)
        [ $# -ge 2 ] && [ $# -le 3 ] || usage
        check_v2; need gpiomon
        gpiomon -c "$1" -n "${3:-10}" "$2"
        ;;
    *) usage ;;
esac
