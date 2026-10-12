#!/usr/bin/env bash
# Check a build host against the prerequisites in the TI docs page "Building the SDK with Yocto"
# (linux/Overview_Building_the_SDK.html, section "Steps to Run Yocto Builds on Host").
# Usage: check-host.sh [build-dir]    (default: current directory; used for the free-space check)
# Exit status: 0 if no FAIL, 1 otherwise. WARN lines are advisory.
set -euo pipefail

dir=${1:-.}
fail=0
ok()   { echo "  [OK]   $*"; }
warn() { echo "  [WARN] $*"; }
bad()  { echo "  [FAIL] $*"; fail=1; }

# Package list copied from the docs page (Ubuntu 22.04). Re-read the page if it changes.
pkgs=(git build-essential diffstat texinfo gawk chrpath socat doxygen dos2unix python3 bison flex
      libssl-dev u-boot-tools mono-devel mono-complete curl python3-distutils repo pseudo python3-sphinx
      g++-multilib libc6-dev-i386 jq git-lfs pigz zstd liblz4-tool cpio file lz4 debianutils iputils-ping
      python3-git python3-jinja2 python3-subunit locales libacl1 unzip gcc python3-pip python3-pexpect
      xz-utils wget)

echo "== OS"
. /etc/os-release 2>/dev/null || true
echo "  ${PRETTY_NAME:-unknown OS}"
if [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 22.04 ]]; then ok "Ubuntu 22.04 (the docs' recommended host)"
else warn "docs recommend Ubuntu 22.04; other hosts are untested here (docs also offer a container image)"; fi

echo "== /bin/sh (docs: must be bash, not dash)"
sh_target=$(readlink -f /bin/sh)
if [[ $sh_target == *dash* ]]; then bad "/bin/sh -> $sh_target ; run: sudo dpkg-reconfigure dash (answer No)"
else ok "/bin/sh -> $sh_target"; fi

echo "== Packages"
if command -v dpkg-query >/dev/null; then
    missing=()
    for p in "${pkgs[@]}"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
    done
    if [[ ${#missing[@]} -eq 0 ]]; then ok "all ${#pkgs[@]} packages from the docs list installed"
    else bad "not installed: ${missing[*]}  (some names may not exist on non-22.04 releases)"; fi
else
    warn "dpkg-query not found: cannot check packages (non-Debian host)"
fi

echo "== Locale (docs: en_US.UTF-8 must exist)"
if locale -a 2>/dev/null | grep -qiE '^en_US\.utf-?8$'; then ok "en_US.UTF-8 available"
else bad "en_US.UTF-8 missing: sudo locale-gen en_US.UTF-8"; fi

echo "== Memory (docs: <32 GB RAM may need ~16 GB swap)"
ram_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
swap_kb=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
echo "  RAM $((ram_kb / 1024 / 1024)) GiB, swap $((swap_kb / 1024 / 1024)) GiB"
if (( ram_kb < 31 * 1024 * 1024 && swap_kb < 15 * 1024 * 1024 )); then warn "less than ~32 GB RAM and little swap"; else ok "RAM/swap"; fi

echo "== Disk (docs: ~750 GB for tisdk-default-image including Chromium)"
[[ -d $dir ]] || { bad "$dir is not a directory"; exit 1; }
avail_gb=$(df -BG --output=avail "$dir" | tail -1 | tr -dc '0-9')
echo "  free in $(cd "$dir" && pwd): ${avail_gb} GiB"
if (( avail_gb < 750 )); then warn "below the ~750 GB figure in the docs"; else ok "disk space"; fi

echo "== Network"
if [[ -n ${http_proxy:-}${https_proxy:-}${HTTP_PROXY:-}${HTTPS_PROXY:-} ]]; then echo "  proxy variables set; see docs 'Working Behind a Network Proxy'"
else echo "  no proxy variables set"; fi

exit $fail
