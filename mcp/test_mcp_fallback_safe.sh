#!/usr/bin/env bash
#=====================================================================
# test_mcp_fallback_safe.sh
#
# Demonstrates that the TI Processor SDK Docs MCP server uses the
# FTS5 searchindex.db when it exists and falls back to Sphinx‑IDF
# when the file is missing.
#
# IMPORTANT: This script never touches the original
#            processor-sdk-doc-fork repository. It works on a
#            temporary copy of the build directory.
#
# Prerequisites:
#   * Python 3.11+ with the MCP server dependencies installed
#   * The server script (server.py) is located in the same directory
#     as this script (or you can set SERVER_PATH below).
#   * A local SDK build that contains searchindex.js and (optionally)
#     searchindex.db – e.g. the output of
#         scripts/build_searchindex.py <build_dir>
#   * curl and (optional) jq for pretty‑printing JSON.
#
# Usage:
#   chmod +x test_mcp_fallback_safe.sh
#   ./test_mcp_fallback_safe.sh \
#        --build-root "/path/to/processor-sdk-linux-AM62X/esd/docs/12_01_00_05_03"
#
# The script will:
#   1. Create a temporary directory and copy the SDK build there.
#   2. Start the MCP server in stdio mode pointing to the copy.
#   3. Run a sample search (u-boot bootloader flash eMMC) and save the output.
#   4. Remove searchindex.db **only inside the temporary copy**.
#   5. Restart the server (same temp copy) pointing to the same copy.
#   6. Run the same search again.
#   7. Print a short comparison of the two results.
#   8. Store the raw and extracted responses in the test_output directory.
#   9. Clean up the temporary directory.
#=====================================================================

set -euo pipefail

# ---------- Default values (can be overridden on the command line) ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PATH="${SCRIPT_DIR}/server.py"          # adjust if server.py lives elsewhere
BUILD_ROOT=""                                  # must be supplied via --build-root
TMP_ROOT=""                                    # will hold the temporary copy
QUERY="u-boot bootloader flash eMMC"
DEVICE="AM62X"
OS="linux"
VERSION="latest"
SOURCE="software-dl"
MAX_RESULTS=8
OUTPUT_DIR="${SCRIPT_DIR}/test_output"         # directory to store test results
# ---------------------------------------------------------------------------

# ---------- Helper functions ----------
usage() {
    cat <<EOF
Usage: $0 --build-root <path-to-sdk-build> [--server <path-to-server.py>]

Options:
  --build-root <path>   Absolute path to the SDK build directory that
                        contains searchindex.js (and optionally searchindex.db).
  --server <path>       Path to the MCP server script (default: ./server.py)
  -h, --help            Show this help and exit.
EOF
    exit 1
}

error() { echo "ERROR: $*" >&2; exit 1; }
info()  { echo "[INFO] $*"; }

# Run a search using stdio mode via tools/call and return the raw JSON‑RPC result string
run_search_stdio() {
    local query_json="$1"
    local tmpdir="$2"
    local server_path="$3"
    # Use a Python subprocess to communicate with the server over stdio
    local response
    response=$(PYTHONPATH="" TI_PROCESSOR_SDK_DOCS_ROOT="${tmpdir}" python3 -c "
import sys, json, os, subprocess
env = os.environ.copy()
proc = subprocess.Popen(
    [sys.executable, '$SERVER_PATH'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env
)
# Initialize request (required by MCP)
init_req = {
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'initialize',
    'params': {
        'protocolVersion': '2024-11-05',
        'capabilities': {},
        'clientInfo': {'name': 'test', 'version': '0.1.0'}
    }
}
proc.stdin.write(json.dumps(init_req) + '\\n')
proc.stdin.flush()
# Read initialize response (we don't need it, but we must read it to avoid blocking)
_init_resp = proc.stdout.readline()
# Now send the tools/call request
params = json.loads('''$query_json''')
tools_call_req = {
    'jsonrpc': '2.0',
    'id': 2,
    'method': 'tools/call',
    'params': {
        'name': 'ti_processor_sdk_docs_search',
        'arguments': params
    }
}
proc.stdin.write(json.dumps(tools_call_req) + '\\n')
proc.stdin.flush()
# Read the tools/call response
tools_call_resp = proc.stdout.readline()
print(tools_call_resp, end='')
proc.terminate()
proc.wait()
")
    echo "$response"
}

# Extract the actual results array from the RPC response.
# The MCP tool returns a JSON string (the result) which is a JSON-encoded array.
extract_results() {
    local rpc_response="$1"
    # Use Python to parse the outer JSON, then extract the result string from the MCP response.
    python3 -c "
import sys, json
try:
    outer = json.loads(sys.argv[1])
except Exception as e:
    sys.stdout.write(sys.argv[1])
    sys.exit(0)

# Try to get the result string from the MCP response
result_str = None
if isinstance(outer.get('result'), dict):
    res_dict = outer['result']
    # Try structuredContent.result first
    if 'structuredContent' in res_dict and isinstance(res_dict['structuredContent'], dict) and 'result' in res_dict['structuredContent']:
        result_str = res_dict['structuredContent']['result']
    # Fallback to content[0].text
    elif 'content' in res_dict and isinstance(res_dict['content'], list) and len(res_dict['content']) > 0:
        first = res_dict['content'][0]
        if isinstance(first, dict) and first.get('type') == 'text' and 'text' in first:
            result_str = first['text']
elif isinstance(outer.get('result'), str):
    result_str = outer['result']

if result_str is None:
    # If we didn't find a result string, output the raw response
    sys.stdout.write(json.dumps(outer))
    sys.exit(0)

# Now try to parse the result_str as JSON (it should be a JSON array)
try:
    result_array = json.loads(result_str)
    # Output the array as compact JSON
    json.dump(result_array, sys.stdout, separators=(',', ':'))
except Exception as e:
    # If not JSON, output the string
    sys.stdout.write(result_str)
" "$rpc_response" 2>/dev/null || cat
}

# ---------- Parse command line ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-root)
            BUILD_ROOT="$2"
            shift 2
            ;;
        --server)
            SERVER_PATH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

if [[ -z "${BUILD_ROOT}" ]]; then
    error "--build-root is required"
fi

if [[ ! -d "${BUILD_ROOT}" ]]; then
    error "Build root not found: ${BUILD_ROOT}"
fi

if [[ ! -f "${SERVER_PATH}" ]]; then
    error "Server script not found: ${SERVER_PATH}"
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"
info "Output directory: ${OUTPUT_DIR}"

# ---------- Main test ----------
info "Original build root: ${BUILD_ROOT}"
info "Server script: ${SERVER_PATH}"

# Create a temporary directory and copy the build there
TMP_ROOT=$(mktemp -d -t mcp-test-XXXXXX)
info "Temporary directory: ${TMP_ROOT}"
cp -a "${BUILD_ROOT}"/* "${TMP_ROOT}/"
info "Copied SDK build to temporary location."

# Build the query JSON for the search
QUERY_JSON=$(printf '{"query":"%s","device":"%s","os":"%s","version":"%s","source":"%s","max_results":%d}' \
    "${QUERY}" "${DEVICE}" "${OS}" "${VERSION}" "${SOURCE}" "${MAX_RESULTS}")

# ---- Test with searchindex.db present (in the temp copy) ----
info "=== Test WITH searchindex.db (in temp copy) ==="
RAW_WITH=$(run_search_stdio "${QUERY_JSON}" "${TMP_ROOT}" "${SERVER_PATH}")

# Save raw RPC response for debugging (optional)
echo "${RAW_WITH}" > "${OUTPUT_DIR}/raw_with_db.json"

RESULTS_WITH=$(extract_results "${RAW_WITH}")
echo "${RESULTS_WITH}" > "${OUTPUT_DIR}/extracted_with_db.json"

# ---- Remove the DB from the temporary copy ----
info "Removing searchindex.db from the temporary copy ..."
rm -f "${TMP_ROOT}/searchindex.db"
if [[ -f "${TMP_ROOT}/searchindex.db" ]]; then
    error "Failed to delete searchindex.db in temporary copy"
fi
info "searchindex.db removed from temporary copy."

# ---- Test without searchindex.db (still using the temp copy) ----
info "=== Test WITHOUT searchindex.db (in temp copy) ==="
RAW_WITHOUT=$(run_search_stdio "${QUERY_JSON}" "${TMP_ROOT}" "${SERVER_PATH}")

echo "${RAW_WITHOUT}" > "${OUTPUT_DIR}/raw_without_db.json"
RESULTS_WITHOUT=$(extract_results "${RAW_WITHOUT}")
echo "${RESULTS_WITHOUT}" > "${OUTPUT_DIR}/extracted_without_db.json"

# ---------- Comparison ----------
echo
echo "===================== COMPARISON ====================="
echo
echo "Results WITH searchindex.db (FTS5):"
echo "------------------------------------"
if command -v jq >/dev/null 2>&1; then
    # Format as a table with headers
    echo "${RESULTS_WITH}" | jq -r '
      ["Title", "Path", "Score", "Page Type", "Matched Terms", "Coverage"],
      (.[] | [.title, .path, .score, .page_type, (.matched_terms | join(",")), .coverage])
      | @tsv' | column -t -s $'\t'
else
    echo "${RESULTS_WITH}"
fi
echo
echo "Results WITHOUT searchindex.db (Sphinx‑IDF fallback):"
echo "------------------------------------------------------"
if command -v jq >/dev/null 2>&1; then
    echo "${RESULTS_WITHOUT}" | jq -r '
      ["Title", "Path", "Score"],
      (.[] | [.title, .path, .score])
      | @tsv' | column -t -s $'\t'
else
    echo "${RESULTS_WITHOUT}"
fi
echo
echo "Key differences to look for:"
echo "  * With DB present: each entry contains page_type, matched_terms, coverage and NEGATIVE scores."
echo "  * Without DB: those three fields are absent and scores are POSITIVE."
echo "  * The ordering of the results will usually change."
echo
echo "Logs are available in:"
echo "  ${OUTPUT_DIR}/raw_with_db.json          – raw RPC response with DB"
echo "  ${OUTPUT_DIR}/raw_without_db.json       – raw RPC response without DB"
echo "  ${OUTPUT_DIR}/extracted_with_db.json    – extracted results array (JSON) with DB"
echo "  ${OUTPUT_DIR}/extracted_without_db.json – extracted results array (JSON) without DB"
echo

info "Test completed."

# Clean up: stop any stray server processes and remove the temporary directory
# (Note: our stdio test starts and stops the server for each search, so no stray server)
rm -rf "${TMP_ROOT}"
info "Temporary directory removed."

exit 0