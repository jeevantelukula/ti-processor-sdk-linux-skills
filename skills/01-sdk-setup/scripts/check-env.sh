#!/usr/bin/env bash
# Validate TI Processor SDK devkit environment
# Source the devkit first, then run this script

set -euo pipefail

PASS=0
FAIL=0
WARN=0

_pass() { echo "  [PASS] $*"; ((PASS++)) || true; }
_fail() { echo "  [FAIL] $*"; ((FAIL++)) || true; }
_warn() { echo "  [WARN] $*"; ((WARN++)) || true; }

echo "=== TI Processor SDK Environment Check ==="
echo ""

echo "--- Cross-Compiler ---"
if [[ -n "${CC:-}" ]]; then
    if echo "${CC}" | grep -q "aarch64-oe-linux-gcc"; then
        _pass "CC = ${CC}"
        # Test compile
        echo "int main(){return 0;}" | ${CC} -x c -o /tmp/ti_cc_test - 2>/dev/null && {
            _pass "Cross-compile test: OK"
            file /tmp/ti_cc_test | grep -q "aarch64" && _pass "Output is aarch64 ELF"
            rm -f /tmp/ti_cc_test
        } || _fail "Cross-compile test failed"
    else
        _fail "CC does not look like aarch64-oe-linux-gcc: ${CC}"
    fi
else
    _fail "CC not set — source the devkit first:"
    echo "         source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux"
fi

echo ""
echo "--- Sysroot ---"
if [[ -n "${SYSROOT:-}" && -d "${SYSROOT}" ]]; then
    _pass "SYSROOT = ${SYSROOT}"
    [[ -d "${SYSROOT}/usr/include" ]] && _pass "Headers present" || _warn "usr/include missing"
    [[ -d "${SYSROOT}/usr/lib" ]]    && _pass "Libraries present" || _warn "usr/lib missing"
    [[ -f "${SYSROOT}/usr/include/linux/gpio.h" ]] && _pass "linux/gpio.h found" \
        || _warn "linux/gpio.h missing"
else
    _fail "SYSROOT not set or not a directory"
fi

echo ""
echo "--- SDK Path ---"
if [[ -n "${PROCESSOR_SDK_LINUX:-}" && -d "${PROCESSOR_SDK_LINUX}" ]]; then
    _pass "PROCESSOR_SDK_LINUX = ${PROCESSOR_SDK_LINUX}"
    for subdir in linux-devkit board-support filesystem; do
        [[ -d "${PROCESSOR_SDK_LINUX}/${subdir}" ]] && _pass "${subdir}/ present" \
            || _warn "${subdir}/ missing"
    done
else
    _warn "PROCESSOR_SDK_LINUX not set — prebuilt images location unknown"
fi

echo ""
echo "--- Key Tools ---"
for tool in dtc git python3; do
    command -v "${tool}" &>/dev/null && _pass "${tool}: $(command -v "${tool}")" \
        || _warn "${tool}: not found"
done

echo ""
echo "=== Summary ==="
echo "  PASS: ${PASS}  WARN: ${WARN}  FAIL: ${FAIL}"
[[ "${FAIL}" -eq 0 ]] && echo "  Environment OK." || echo "  Fix FAIL items above."
