#!/usr/bin/env bash
# Check host machine prerequisites for TI Processor SDK Yocto build
# Run on the build host (not the target board)

set -euo pipefail

PASS=0
WARN=0
FAIL=0

_pass() { echo "  [PASS] $*"; ((PASS++)) || true; }
_warn() { echo "  [WARN] $*"; ((WARN++)) || true; }
_fail() { echo "  [FAIL] $*"; ((FAIL++)) || true; }

echo "=== TI Processor SDK Yocto Build Host Check ==="
echo ""

# ── OS Version ──────────────────────────────────────────────────────────────
echo "--- OS ---"
if [[ -f /etc/os-release ]]; then
    OS_ID=$(grep "^ID=" /etc/os-release | cut -d= -f2 | tr -d '"')
    OS_VER=$(grep "^VERSION_ID=" /etc/os-release | cut -d= -f2 | tr -d '"')
    if [[ "${OS_ID}" == "ubuntu" && "${OS_VER}" == "22.04" ]]; then
        _pass "Ubuntu 22.04 LTS detected"
    elif [[ "${OS_ID}" == "ubuntu" && "${OS_VER}" == "24.04" ]]; then
        _fail "Ubuntu 24.04 NOT supported (permission errors with pseudo). Use 22.04 or Docker."
    else
        _warn "OS: ${OS_ID} ${OS_VER} — only Ubuntu 22.04 officially tested. May work."
    fi
else
    _warn "Cannot determine OS version"
fi

# ── Default shell ────────────────────────────────────────────────────────────
echo ""
echo "--- Shell ---"
SH_TARGET=$(readlink -f /bin/sh)
if [[ "${SH_TARGET}" == *bash* ]]; then
    _pass "/bin/sh → bash"
elif [[ "${SH_TARGET}" == *dash* ]]; then
    _fail "/bin/sh → dash. Fix: sudo dpkg-reconfigure dash (select 'No' for dash as default)"
else
    _warn "/bin/sh → ${SH_TARGET} (expected bash)"
fi

# ── Locale ───────────────────────────────────────────────────────────────────
echo ""
echo "--- Locale ---"
if locale 2>/dev/null | grep -q "LANG=en_US.UTF-8"; then
    _pass "LANG=en_US.UTF-8 set"
else
    LANG_VAL=$(locale 2>/dev/null | grep "^LANG=" | head -1)
    _warn "${LANG_VAL:-LANG not set} — recommended: export LANG=en_US.UTF-8"
fi

if locale-gen --no-archive en_US.UTF-8 &>/dev/null || locale -a 2>/dev/null | grep -q "en_US.utf8"; then
    _pass "en_US.UTF-8 locale generated"
else
    _fail "en_US.UTF-8 locale missing. Fix: sudo locale-gen en_US.UTF-8"
fi

# ── Disk space ───────────────────────────────────────────────────────────────
echo ""
echo "--- Disk Space ---"
AVAIL_GB=$(df -BG . | tail -1 | awk '{print $4}' | tr -d 'G')
if [[ "${AVAIL_GB}" -ge 750 ]]; then
    _pass "${AVAIL_GB} GB available (≥750 GB needed for full tisdk-default-image)"
elif [[ "${AVAIL_GB}" -ge 250 ]]; then
    _warn "${AVAIL_GB} GB available. Enough for tisdk-base-image but NOT tisdk-default-image (Chromium needs ~500 GB extra)"
elif [[ "${AVAIL_GB}" -ge 100 ]]; then
    _warn "${AVAIL_GB} GB available. Enough for kernel/U-Boot only builds."
else
    _fail "${AVAIL_GB} GB available — insufficient. Need ≥750 GB for full build."
fi

# ── RAM / Swap ───────────────────────────────────────────────────────────────
echo ""
echo "--- RAM / Swap ---"
RAM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
SWAP_GB=$(awk '/SwapTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
TOTAL_MEM=$((RAM_GB + SWAP_GB))

if [[ "${RAM_GB}" -ge 32 ]]; then
    _pass "RAM: ${RAM_GB} GB (no swap required)"
elif [[ "${RAM_GB}" -ge 16 && "${TOTAL_MEM}" -ge 32 ]]; then
    _pass "RAM: ${RAM_GB} GB + Swap: ${SWAP_GB} GB = ${TOTAL_MEM} GB virtual memory"
elif [[ "${RAM_GB}" -ge 16 ]]; then
    _warn "RAM: ${RAM_GB} GB, Swap: ${SWAP_GB} GB. Add 16 GB swap for large package builds."
else
    _fail "RAM: ${RAM_GB} GB — too low. Minimum 16 GB RAM + 16 GB swap."
fi

# ── File descriptor limit ────────────────────────────────────────────────────
echo ""
echo "--- File Descriptors ---"
FD_LIMIT=$(ulimit -n)
if [[ "${FD_LIMIT}" -ge 4096 ]]; then
    _pass "ulimit -n = ${FD_LIMIT}"
else
    _warn "ulimit -n = ${FD_LIMIT} (recommended ≥4096). Fix: ulimit -n 4096"
fi

# ── Required tools ───────────────────────────────────────────────────────────
echo ""
echo "--- Required Packages ---"
REQUIRED_TOOLS=(git python3 gcc make gawk chrpath socat dtc bison flex curl wget)
for tool in "${REQUIRED_TOOLS[@]}"; do
    if command -v "${tool}" &>/dev/null; then
        _pass "${tool}: $(command -v "${tool}")"
    else
        _fail "${tool}: NOT FOUND"
    fi
done

# ── Bitbake ──────────────────────────────────────────────────────────────────
echo ""
echo "--- Bitbake ---"
if command -v bitbake &>/dev/null; then
    _pass "bitbake: $(bitbake --version | head -1)"
else
    _warn "bitbake not in PATH. Source oe-layersetup/build/conf/setenv first."
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Summary ==="
echo "  PASS: ${PASS}  WARN: ${WARN}  FAIL: ${FAIL}"
echo ""
if [[ "${FAIL}" -eq 0 && "${WARN}" -eq 0 ]]; then
    echo "  Host is READY for Yocto build."
elif [[ "${FAIL}" -eq 0 ]]; then
    echo "  Host is READY with warnings. Review WARN items above."
else
    echo "  Host has ISSUES. Fix FAIL items before building."
fi
