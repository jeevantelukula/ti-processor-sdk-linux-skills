#!/usr/bin/env bash
# GPIO test script using libgpiod (run on target board)
# Usage: gpio-test.sh [chip] [line] [output|input] [value]

set -euo pipefail

usage() {
    echo "Usage:"
    echo "  $0 list                      — list all GPIO chips and lines"
    echo "  $0 read  <chip> <line>       — read input GPIO value"
    echo "  $0 write <chip> <line> <0|1> — set output GPIO value"
    echo "  $0 watch <chip> <line>       — monitor GPIO edge events"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 read  gpiochip1 14"
    echo "  $0 write gpiochip0 22 1"
    echo "  $0 watch gpiochip1 14"
    exit 1
}

_check_tool() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: '$1' not found. Install: apt install gpiod" >&2
        exit 1
    fi
}

case "${1:-}" in
    list)
        _check_tool gpiodetect
        _check_tool gpioinfo
        echo "=== GPIO Chips ==="
        gpiodetect
        echo ""
        echo "=== GPIO Lines ==="
        gpioinfo
        ;;
    read)
        [[ $# -ge 3 ]] || usage
        _check_tool gpioget
        CHIP="$2"; LINE="$3"
        VAL=$(gpioget "${CHIP}" "${LINE}")
        echo "GPIO ${CHIP} line ${LINE} = ${VAL}"
        ;;
    write)
        [[ $# -ge 4 ]] || usage
        _check_tool gpioset
        CHIP="$2"; LINE="$3"; VALUE="$4"
        [[ "$VALUE" == "0" || "$VALUE" == "1" ]] || { echo "Value must be 0 or 1"; exit 1; }
        echo "Setting GPIO ${CHIP} line ${LINE} = ${VALUE}"
        gpioset "${CHIP}" "${LINE}=${VALUE}"
        echo "Done."
        ;;
    watch)
        [[ $# -ge 3 ]] || usage
        _check_tool gpiomon
        CHIP="$2"; LINE="$3"
        echo "Monitoring GPIO ${CHIP} line ${LINE} — press Ctrl+C to stop"
        gpiomon --num-events=0 --format="%e %o %s %n" "${CHIP}" "${LINE}"
        ;;
    *)
        usage
        ;;
esac
