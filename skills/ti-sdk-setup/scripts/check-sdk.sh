#!/usr/bin/env bash
# Host-side SDK sanity check. Read-only: installs nothing, writes nothing.
# Usage: check-sdk.sh [SDK_ROOT]
#   SDK_ROOT defaults to $TI_SDK_ROOT, $PROCESSOR_SDK_LINUX, or the SDK containing the cwd.
# Exit status: 0 if all checks pass, 1 otherwise.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
skills_dir=${TI_SKILLS_DIR:-$(cd "$here/../../.." && pwd)}
env_lib=$skills_dir/lib/ti-sdk-env.sh
[ -f "$env_lib" ] || { echo "FAIL: $env_lib not found (set TI_SKILLS_DIR)" >&2; exit 1; }

[ $# -ge 1 ] && export TI_SDK_ROOT=$1
# shellcheck disable=SC1090
source "$env_lib" || exit 1

fail=0
ok()   { printf 'PASS  %s\n' "$*"; }
bad()  { printf 'FAIL  %s\n' "$*"; fail=1; }
warn() { printf 'WARN  %s\n' "$*"; }

echo "== SDK values (from Rules.make / directory name / manifest)"
for v in TI_SDK_ROOT TI_SDK_VERSION TI_SOC TI_PLATFORM TI_ARCH TI_UBOOT_MACHINE \
         TI_UBOOT_MACHINE_R5 TI_DTB_PREFIX TI_CROSS_COMPILE TI_CROSS_COMPILE_R5 \
         TI_KERNEL_VERSION TI_DOCS_DEVICE TI_KB TI_FACTS_JSON; do
    printf '%-22s %s\n' "$v" "${!v:-<unset>}"
done

echo "== Generated device facts (skill ti-generate-kb)"
if [ -n "${TI_KB:-}" ] && [ -f "$TI_KB" ]; then
    ok "TI_KB=$TI_KB"
else
    warn "no generated KB for '${TI_PLATFORM:-?}': run the skill ti-generate-kb, then re-source lib/ti-sdk-env.sh"
fi
[ -n "${TI_DOCS_DEVICE:-}" ] || warn "TI_DOCS_DEVICE empty: ask the user for the docs MCP device key (ti_processor_sdk_docs_list_variants)"

echo "== Host distribution (SDK bin/setup-host-check.sh)"
if [ -x "$TI_SDK_ROOT/bin/setup-host-check.sh" ]; then
    if "$TI_SDK_ROOT/bin/setup-host-check.sh" >/dev/null 2>&1; then
        ok "setup-host-check.sh passed"
    else
        bad "setup-host-check.sh failed (run it directly to see the message)"
    fi
else
    warn "$TI_SDK_ROOT/bin/setup-host-check.sh not present in this SDK"
fi

echo "== Toolchains from Rules.make"
if [ -n "$TI_CROSS_COMPILE" ] && [ -x "${TI_CROSS_COMPILE}gcc" ]; then
    ok "A-core: $("${TI_CROSS_COMPILE}gcc" --version | head -n1)"
else
    bad "CROSS_COMPILE gcc not executable: '${TI_CROSS_COMPILE}gcc'"
fi
if [ -n "$TI_CROSS_COMPILE_R5" ]; then
    if [ -x "${TI_CROSS_COMPILE_R5}gcc" ]; then
        ok "R5 (CROSS_COMPILE_ARMV7): $("${TI_CROSS_COMPILE_R5}gcc" --version | head -n1)"
    else
        bad "CROSS_COMPILE_ARMV7 gcc not executable: '${TI_CROSS_COMPILE_R5}gcc'"
    fi
else
    warn "Rules.make defines no CROSS_COMPILE_ARMV7 (SDK has no separate R5 toolchain)"
fi

echo "== Host build tools (package list: docs page linux/Overview/Top_Level_Makefile.html)"
for t in make gcc bison flex bc mkimage swig python3; do
    if command -v "$t" >/dev/null 2>&1; then ok "$t"; else bad "$t not found"; fi
done
if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import jsonschema, elftools, yaml, mako' 2>/dev/null; then
        ok "python modules for binman (jsonschema, pyelftools, PyYAML, Mako)"
    else
        bad "python modules missing: need jsonschema pyelftools PyYAML Mako (pip3 install, per docs)"
    fi
fi

echo "== Source and prebuilt trees"
for d in "$TI_KERNEL_SRC_DIR" "$TI_UBOOT_SRC_DIR"; do
    if [ -n "$d" ] && [ -d "$d" ]; then ok "$d"; else bad "missing source dir: '${d}'"; fi
done
if [ -n "$TI_PLATFORM" ] && [ -d "$TI_SDK_ROOT/board-support/prebuilt-images/$TI_PLATFORM" ]; then
    ok "board-support/prebuilt-images/$TI_PLATFORM"
else
    warn "board-support/prebuilt-images/$TI_PLATFORM not found (this SDK may use a different layout; ls board-support/prebuilt-images)"
fi

[ "$fail" -eq 0 ] && echo "RESULT: OK" || echo "RESULT: problems found"
exit "$fail"
