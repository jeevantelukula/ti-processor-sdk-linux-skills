# shellcheck shell=bash
# ti-sdk-env.sh - source this file; do not execute it.
#
#   source lib/ti-sdk-env.sh            # auto-discover the SDK
#   TI_SDK_ROOT=/path/to/sdk source lib/ti-sdk-env.sh
#
# SDK discovery order: $TI_SDK_ROOT, $PROCESSOR_SDK_LINUX, then the current
# directory and its parents. A directory is an SDK root if it contains both
# Rules.make and board-support/.
#
# Exports (empty when the SDK does not define the value):
#   TI_SDK_ROOT, TI_SDK_VERSION (from the directory name, dotted form),
#   TI_SDK_VERSION_DOCS (underscored form for the docs MCP version parameter),
#   TI_SOC, TI_PLATFORM, TI_ARCH, TI_UBOOT_MACHINE, TI_UBOOT_MACHINE_R5,
#   TI_DTB_PREFIX, TI_CROSS_COMPILE, TI_CROSS_COMPILE_R5,
#   TI_KERNEL_SRC_DIR, TI_UBOOT_SRC_DIR, TI_KERNEL_VERSION (software_manifest.txt),
#   TI_DOCS_DEVICE (docs MCP device key derived from PLATFORM, see _ti_env_docs_device;
#     verify with ti_processor_sdk_docs_list_variants; empty if PLATFORM is unknown),
#   TI_FACTS_DIR (generated facts directory), TI_KB (<platform>.md there, only if it exists),
#   TI_FACTS_JSON (<platform>.json there, only if it exists). Generate with lib/gen-sdk-facts.py.
# Returns 1 (and prints to stderr) if no SDK is found. Never calls exit.

_ti_env_warn() { printf 'ti-sdk-env: %s\n' "$*" >&2; }

_ti_env_is_sdk() { [ -f "$1/Rules.make" ] && [ -d "$1/board-support" ]; }

_ti_env_discover() {
    local d
    for d in "${TI_SDK_ROOT:-}" "${PROCESSOR_SDK_LINUX:-}"; do
        if [ -n "$d" ]; then
            if _ti_env_is_sdk "$d"; then (cd "$d" && pwd); return 0; fi
            _ti_env_warn "ignoring '$d': no Rules.make and board-support/ found"
        fi
    done
    d=$PWD
    while [ -n "$d" ] && [ "$d" != "/" ]; do
        if _ti_env_is_sdk "$d"; then printf '%s\n' "$d"; return 0; fi
        d=$(dirname "$d")
    done
    # Installed workspace: sdk.root from target-profile.yaml (written by install.sh).
    local here p r
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)
    for p in "$PWD/.claude/target-profile.yaml" "$here/../target-profile.yaml"; do
        [ -f "$p" ] || continue
        r=$(awk '/^sdk:/{s=1;next} s&&/^[^ ]/{s=0} s&&$1=="root:"{sub(/^[^:]*:[ ]*/,"");sub(/[ ]*#.*/,"");print;exit}' "$p")
        if [ -n "$r" ] && _ti_env_is_sdk "$r"; then (cd "$r" && pwd); return 0; fi
    done
    return 1
}

# Evaluate Rules.make with GNU make so $(VAR) references are expanded.
# TI_SDK_PATH is forced to the discovered root (Rules.make uses ?=), so a
# relocated SDK still resolves correctly.
_ti_env_eval_rules() {
    local root=$1
    command -v make >/dev/null 2>&1 || return 1
    make -s --no-print-directory -f - TI_SDK_PATH="$root" __ti_print 2>/dev/null <<EOF
include $root/Rules.make
.PHONY: __ti_print
__ti_print:
	@printf 'SOC=%s\n' '\$(SOC)'
	@printf 'PLATFORM=%s\n' '\$(PLATFORM)'
	@printf 'ARCH=%s\n' '\$(ARCH)'
	@printf 'UBOOT_MACHINE=%s\n' '\$(UBOOT_MACHINE)'
	@printf 'UBOOT_MACHINE_R5=%s\n' '\$(UBOOT_MACHINE_R5)'
	@printf 'KERNEL_DEVICETREE_PREFIX=%s\n' '\$(KERNEL_DEVICETREE_PREFIX)'
	@printf 'CROSS_COMPILE=%s\n' '\$(CROSS_COMPILE)'
	@printf 'CROSS_COMPILE_ARMV7=%s\n' '\$(CROSS_COMPILE_ARMV7)'
	@printf 'LINUXKERNEL_INSTALL_DIR=%s\n' '\$(LINUXKERNEL_INSTALL_DIR)'
	@printf 'UBOOT_SRC_DIR=%s\n' '\$(UBOOT_SRC_DIR)'
EOF
}

# Fallback when make is missing or fails: plain-text lookup (no expansion).
_ti_env_grep_rules() {
    local root=$1 k v
    for k in SOC PLATFORM ARCH UBOOT_MACHINE UBOOT_MACHINE_R5 \
             KERNEL_DEVICETREE_PREFIX CROSS_COMPILE; do
        v=$(sed -n -E "s/^(export[[:space:]]+)?${k}[[:space:]]*\??=[[:space:]]*//p" \
            "$root/Rules.make" | head -n1)
        printf '%s=%s\n' "$k" "$v"
    done
}

# Docs MCP device key from PLATFORM: take the part before the first '-' (board suffix such as
# -evm/-sk), uppercase, drop trailing 'XX' suffix when present. Checked against
# ti_processor_sdk_docs_list_variants: am62pxx->AM62PX, am62xx->AM62X, am62lxx->AM62LX,
# am62axx->AM62AX, am62dxx->AM62DX, am64xx->AM64X, am335x->AM335X. The result is a candidate:
# if list_variants does not list it, ask the user.
_ti_env_docs_device() {
    local k=${1%%-*}
    [ -n "$k" ] || return 0
    k=$(printf '%s' "$k" | tr '[:lower:]' '[:upper:]')
    case $k in *XX) k=${k%XX} ;; esac
    printf '%s\n' "$k"
}

_ti_env_main() {
    local root line key val ver dir lib_dir ws
    root=$(_ti_env_discover) || {
        _ti_env_warn "no SDK found. Set TI_SDK_ROOT (or PROCESSOR_SDK_LINUX) to the SDK directory, or cd into it."
        return 1
    }
    export TI_SDK_ROOT=$root

    TI_SOC= TI_PLATFORM= TI_ARCH= TI_UBOOT_MACHINE= TI_UBOOT_MACHINE_R5=
    TI_DTB_PREFIX= TI_CROSS_COMPILE= TI_CROSS_COMPILE_R5=
    TI_KERNEL_SRC_DIR= TI_UBOOT_SRC_DIR= TI_KERNEL_VERSION= TI_DOCS_DEVICE=

    local parsed
    parsed=$(_ti_env_eval_rules "$root") || parsed=
    if [ -z "$parsed" ]; then
        _ti_env_warn "could not evaluate Rules.make with make; falling back to text parsing (variables are not expanded)"
        parsed=$(_ti_env_grep_rules "$root")
    fi
    while IFS= read -r line; do
        key=${line%%=*}; val=${line#*=}
        case $key in
            SOC) TI_SOC=$val ;;
            PLATFORM) TI_PLATFORM=$val ;;
            ARCH) TI_ARCH=$val ;;
            UBOOT_MACHINE) TI_UBOOT_MACHINE=$val ;;
            UBOOT_MACHINE_R5) TI_UBOOT_MACHINE_R5=$val ;;
            KERNEL_DEVICETREE_PREFIX) TI_DTB_PREFIX=$val ;;
            CROSS_COMPILE) TI_CROSS_COMPILE=$val ;;
            CROSS_COMPILE_ARMV7) TI_CROSS_COMPILE_R5=$val ;;
            LINUXKERNEL_INSTALL_DIR) TI_KERNEL_SRC_DIR=$val ;;
            UBOOT_SRC_DIR) TI_UBOOT_SRC_DIR=$val ;;
        esac
    done <<<"$parsed"
    [ -n "$TI_SOC" ] || _ti_env_warn "SOC not found in $root/Rules.make"

    # SDK version: trailing version token of the directory name (e.g. -12.02.00.01.01 or -12_01_00_09).
    dir=$(basename "$root")
    ver=$(printf '%s\n' "$dir" | sed -n -E 's/.*-([0-9]+([._][0-9]+){2,4})$/\1/p')
    if [ -n "$ver" ]; then
        TI_SDK_VERSION=${ver//_/.}
        TI_SDK_VERSION_DOCS=${ver//./_}
    else
        TI_SDK_VERSION= TI_SDK_VERSION_DOCS=
        _ti_env_warn "cannot derive SDK version from directory name '$dir'"
    fi

    # Kernel version: package row "| kernel | <version> | ..." in the manifest.
    if [ -f "$root/manifest/software_manifest.txt" ]; then
        TI_KERNEL_VERSION=$(awk -F'|' '$2 ~ /^ *kernel *$/ {gsub(/^ +| +$/, "", $3); print $3; exit}' \
            "$root/manifest/software_manifest.txt")
    else
        _ti_env_warn "manifest/software_manifest.txt not found"
    fi

    TI_DOCS_DEVICE=$(_ti_env_docs_device "$TI_PLATFORM")
    [ -n "$TI_DOCS_DEVICE" ] || _ti_env_warn "cannot derive docs MCP device key from PLATFORM '$TI_PLATFORM'; ask the user or call ti_processor_sdk_docs_list_variants"

    # Generated facts (lib/gen-sdk-facts.py): TI_FACTS_DIR > <workspace>/.claude/target-platform > ./target-platform
    lib_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    if [ -z "${TI_FACTS_DIR:-}" ]; then
        ws=$(dirname "$(dirname "$lib_dir")")
        if [ "$(basename "$(dirname "$lib_dir")")" = ".claude" ]; then
            TI_FACTS_DIR=$ws/.claude/target-platform
        elif [ -d "$PWD/.claude/target-platform" ]; then
            TI_FACTS_DIR=$PWD/.claude/target-platform
        else
            TI_FACTS_DIR=$PWD/target-platform
        fi
    fi
    TI_KB= TI_FACTS_JSON=
    if [ -n "$TI_PLATFORM" ]; then
        [ -f "$TI_FACTS_DIR/$TI_PLATFORM.md" ] && TI_KB=$TI_FACTS_DIR/$TI_PLATFORM.md
        [ -f "$TI_FACTS_DIR/$TI_PLATFORM.json" ] && TI_FACTS_JSON=$TI_FACTS_DIR/$TI_PLATFORM.json
    fi
    [ -n "$TI_KB" ] || _ti_env_warn "no generated facts for '$TI_PLATFORM' in $TI_FACTS_DIR; run: python3 $lib_dir/gen-sdk-facts.py (skill ti-generate-kb)"

    export TI_SDK_VERSION TI_SDK_VERSION_DOCS TI_SOC TI_PLATFORM TI_ARCH \
           TI_UBOOT_MACHINE TI_UBOOT_MACHINE_R5 TI_DTB_PREFIX TI_CROSS_COMPILE \
           TI_CROSS_COMPILE_R5 TI_KERNEL_SRC_DIR TI_UBOOT_SRC_DIR \
           TI_KERNEL_VERSION TI_DOCS_DEVICE TI_FACTS_DIR TI_KB TI_FACTS_JSON
}

_ti_env_main
_ti_env_rc=$?
unset -f _ti_env_main _ti_env_docs_device _ti_env_discover _ti_env_eval_rules _ti_env_grep_rules _ti_env_is_sdk
# shellcheck disable=SC2317
return "$_ti_env_rc" 2>/dev/null || exit "$_ti_env_rc"
