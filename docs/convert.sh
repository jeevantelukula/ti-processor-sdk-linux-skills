#!/usr/bin/env bash
# Convert TI SDK RST documentation or live HTML pages to clean Markdown snippets.
# Output goes to docs/snippets/<sanitized-name>.md
#
# Usage:
#   ./docs/convert.sh <path-to-rst-file>
#   ./docs/convert.sh <url-to-html-page>
#   ./docs/convert.sh --all <sdk-root-path>   # batch convert key pages

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/snippets"
mkdir -p "$OUTPUT_DIR"

usage() {
    echo "Usage: $0 <rst-file|html-url>"
    echo "       $0 --all <sdk-root-path>"
    exit 1
}

[[ $# -eq 0 ]] && usage

sanitize_name() {
    local name
    name=$(basename "$1")
    name="${name%.*}"             # strip extension
    name="${name//[^a-zA-Z0-9_-]/-}"  # replace special chars
    name="${name,,}"              # lowercase
    echo "$name"
}

check_pandoc() {
    if ! command -v pandoc &>/dev/null; then
        echo "ERROR: pandoc not installed. Install with: sudo apt-get install pandoc"
        exit 1
    fi
}

convert_rst() {
    local input="$1"
    local name
    name=$(sanitize_name "$input")
    local output="$OUTPUT_DIR/${name}.md"

    check_pandoc
    echo "Converting RST: $input"
    pandoc --from=rst --to=gfm --wrap=none "$input" -o "$output"
    echo "Written: $output"
}

convert_html_url() {
    local url="$1"
    local name
    name=$(sanitize_name "$(echo "$url" | sed 's|.*/||')")
    local output="$OUTPUT_DIR/${name}.md"

    if command -v curl &>/dev/null; then
        echo "Fetching: $url"
        local html
        html=$(curl -s --max-time 30 "$url")
    else
        echo "ERROR: curl not installed"
        exit 1
    fi

    check_pandoc
    echo "$html" | pandoc --from=html --to=gfm --wrap=none -o "$output"

    # Strip navigation cruft (header/footer/sidebar text)
    # Keep only lines after the first H1 heading
    python3 - "$output" <<'PYEOF'
import sys, re
with open(sys.argv[1]) as f:
    lines = f.readlines()

# Find first heading
start = 0
for i, line in enumerate(lines):
    if line.startswith('# ') or line.startswith('## '):
        start = i
        break

# Write back trimmed content
with open(sys.argv[1], 'w') as f:
    f.writelines(lines[start:])
PYEOF

    echo "Written: $output"
}

convert_all_key_pages() {
    local sdk_root="$1"
    local docs_dir="$sdk_root/docs"

    if [[ ! -d "$docs_dir" ]]; then
        echo "ERROR: docs directory not found at $docs_dir"
        exit 1
    fi

    declare -A KEY_FILES=(
        ["boot-flow"]="linux/Foundational_Components/Kernel/Kernel_Drivers/index.rst"
        ["yocto-layer-guide"]="linux/Foundational_Components/Yocto/index.rst"
        ["remoteproc-guide"]="linux/Foundational_Components/Kernel/Kernel_Drivers/Remoteproc.rst"
        ["gpio-driver"]="linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.rst"
        ["emmc-layout"]="linux/How_to_Guides/Host/How_to_Flash_eMMC.rst"
    )

    local converted=0
    local missing=0

    for name in "${!KEY_FILES[@]}"; do
        local rel="${KEY_FILES[$name]}"
        local full="$docs_dir/$rel"
        if [[ -f "$full" ]]; then
            check_pandoc
            local output="$OUTPUT_DIR/${name}.md"
            pandoc --from=rst --to=gfm --wrap=none "$full" -o "$output"
            echo "OK: $output"
            ((converted++))
        else
            echo "SKIP (not found): $rel"
            ((missing++))
        fi
    done

    echo ""
    echo "Converted: $converted  Skipped: $missing"
    echo "Output: $OUTPUT_DIR/"
}

# Main dispatch
if [[ "$1" == "--all" ]]; then
    [[ $# -lt 2 ]] && usage
    convert_all_key_pages "$2"
elif [[ "$1" == http* ]]; then
    convert_html_url "$1"
elif [[ -f "$1" && "${1##*.}" == "rst" ]]; then
    convert_rst "$1"
else
    echo "ERROR: argument must be an RST file path or HTTP URL"
    usage
fi
