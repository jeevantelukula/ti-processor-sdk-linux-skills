#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Install TI Processor SDK Linux skills into a workspace's .claude/ directory.
# Works standalone (cloned repo) and packaged inside an SDK installer.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install.sh --workspace <dir> [--sdk <sdk-root>] [--mcp <url>] [--mcp-mode <mode>] [--force]

  --workspace <dir>  workspace to populate (<dir>/.claude is created)
  --sdk <sdk-root>   SDK root (contains Rules.make); written to <dir>/.claude/target-profile.yaml.
                     Default: $TI_SDK_ROOT, then $PROCESSOR_SDK_LINUX, then the parent of this
                     repo if it contains Rules.make.
  --mcp <url>        write <dir>/.mcp.json registering the ti-processor-sdk-docs MCP at <url>
                     (HTTP transport, e.g. http://localhost:7471/mcp).
  --mcp-mode <mode>  how to handle MCP: auto (default), docker, stdio, none.
                     auto   = try HTTP, if unreachable build Docker image, else fallback to stdio
                     docker = ensure Docker image exists and register HTTP endpoint
                     stdio  = register stdio transport (no Docker, uses local Sphinx HTML)
                     none   = skip MCP registration entirely
  --force            replace an existing <dir>/.claude
USAGE
}

workspace="" sdk="" mcp="" mcp_mode="auto" force=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; workspace=$2; shift 2 ;;
    --sdk)       [[ $# -ge 2 ]] || { usage >&2; exit 2; }; sdk=$2; shift 2 ;;
    --mcp)       [[ $# -ge 2 ]] || { usage >&2; exit 2; }; mcp=$2; shift 2 ;;
    --mcp-mode)  [[ $# -ge 2 ]] || { usage >&2; exit 2; }; mcp_mode=$2; shift 2 ;;
    --force)     force=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *)           echo "install.sh: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -n "$workspace" ]] || { echo "install.sh: --workspace is required" >&2; usage >&2; exit 2; }

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -d "$repo/skills" ]] || { echo "install.sh: $repo/skills not found" >&2; exit 1; }

if [[ -z "$sdk" ]]; then
  for c in "${TI_SDK_ROOT:-}" "${PROCESSOR_SDK_LINUX:-}" "$repo/.." "$repo/../.."; do
    [[ -n "$c" && -f "$c/Rules.make" ]] && { sdk="$(cd "$c" && pwd)"; break; }
  done
fi
if [[ -n "$sdk" && ! -f "$sdk/Rules.make" ]]; then
  echo "install.sh: $sdk has no Rules.make; not an SDK root" >&2; exit 1
fi
[[ -z "$sdk" ]] || sdk="$(cd "$sdk" && pwd)"

dest="$workspace/.claude"
if [[ -e "$dest" ]]; then
  [[ $force -eq 1 ]] || { echo "install.sh: $dest exists; use --force" >&2; exit 1; }
  rm -rf "$dest"
fi
mkdir -p "$dest"

for d in skills context lib templates; do
  [[ -d "$repo/$d" ]] && cp -r "$repo/$d" "$dest/"
done
for f in AGENTS.md CLAUDE.md; do
  if [[ -e "$workspace/$f" && $force -ne 1 ]]; then
    echo "install.sh: $workspace/$f exists; left unchanged (use --force to replace)"
  elif [[ $f == AGENTS.md ]]; then
    cp "$repo/AGENTS.md" "$workspace/AGENTS.md"
  else
    printf '@AGENTS.md\n' > "$workspace/CLAUDE.md"
  fi
done

if [[ -n "$sdk" ]]; then
  # Replace the sdk.root line without sed, so any character in the path is safe.
  while IFS= read -r line; do
    if [[ $line == "  root: "* ]]; then printf '  root: %s\n' "$sdk"; else printf '%s\n' "$line"; fi
  done < "$repo/templates/target-profile.yaml" > "$dest/target-profile.yaml"
  echo "install.sh: SDK root $sdk"
else
  cp "$repo/templates/target-profile.yaml" "$dest/target-profile.yaml"
  echo "install.sh: no SDK found; edit $dest/target-profile.yaml (sdk.root)"
fi
# Generate the platform knowledge base from the SDK sources (non-fatal).
if [[ -n "$sdk" ]]; then
  if command -v python3 >/dev/null 2>&1 && [[ -f "$dest/lib/gen-sdk-facts.py" ]]; then
    if python3 "$dest/lib/gen-sdk-facts.py" --sdk-root "$sdk" --out-dir "$dest/target-platform"; then
      echo "install.sh: knowledge base in $dest/target-platform (re-run: python3 $dest/lib/gen-sdk-facts.py)"
    else
      echo "install.sh: WARNING: knowledge base generation failed; run python3 $dest/lib/gen-sdk-facts.py --sdk-root $sdk later" >&2
    fi
  else
    echo "install.sh: WARNING: python3 or gen-sdk-facts.py missing; knowledge base not generated" >&2
  fi
else
  echo "install.sh: no SDK root; generate the knowledge base later with the ti-generate-kb skill"
fi
# MCP registration with mode handling
register_mcp() {
  local url="$1" mode="$2" repo="$3"
  case "$mode" in
    none)
      echo "install.sh: MCP registration skipped (--mcp-mode none)"
      ;;
    stdio)
      if [[ -e "$workspace/.mcp.json" && $force -ne 1 ]]; then
        echo "install.sh: $workspace/.mcp.json exists; left unchanged (use --force to replace)"
      else
        local docs_root="${TI_PROCESSOR_SDK_DOCS_ROOT:-$repo/mcp}"
        printf '{\n  "mcpServers": {\n    "ti-processor-sdk-docs": {\n      "command": "python3",\n      "args": ["%s/server.py"],\n      "env": { "TI_PROCESSOR_SDK_DOCS_ROOT": "%s" }\n    }\n  }\n}\n' "$docs_root" "$docs_root" > "$workspace/.mcp.json"
        echo "install.sh: wrote $workspace/.mcp.json (stdio mode, docs root: $docs_root)"
        echo "install.sh: requires: pip3 install \"mcp>=1.0,<2\" beautifulsoup4 httpx uvicorn snowballstemmer"
      fi
      ;;
    docker)
      local http_url="${mcp:-http://localhost:7471/mcp}"
      if ! docker image inspect ti-processor-sdk-docs-mcp >/dev/null 2>&1; then
        echo "install.sh: Docker image not found; building..."
        if docker build -t ti-processor-sdk-docs-mcp "$repo/mcp/"; then
          echo "install.sh: built ti-processor-sdk-docs-mcp"
        else
          echo "install.sh: ERROR: Docker build failed; falling back to stdio mode" >&2
          register_mcp "$url" "stdio" "$repo"
          return
        fi
      fi
      if ! docker ps --format '{{.Names}}' | grep -q '^ti-processor-sdk-docs-mcp$'; then
        echo "install.sh: starting container..."
        docker run -d --name ti-processor-sdk-docs-mcp -p 7471:7471 ti-processor-sdk-docs-mcp
      fi
      if [[ -e "$workspace/.mcp.json" && $force -ne 1 ]]; then
        echo "install.sh: $workspace/.mcp.json exists; left unchanged (use --force to replace)"
      else
        printf '{\n  "mcpServers": {\n    "ti-processor-sdk-docs": {"type": "http", "url": "%s"}\n  }\n}\n' "$http_url" > "$workspace/.mcp.json"
        echo "install.sh: wrote $workspace/.mcp.json (Docker HTTP mode)"
      fi
      ;;
    auto|*)
      local http_url="${mcp:-http://localhost:7471/mcp}"
      # Try HTTP first
      if command -v curl >/dev/null 2>&1 && curl -sf -m 2 "$http_url" >/dev/null 2>&1; then
        if [[ -e "$workspace/.mcp.json" && $force -ne 1 ]]; then
          echo "install.sh: $workspace/.mcp.json exists; left unchanged (use --force to replace)"
        else
          printf '{\n  "mcpServers": {\n    "ti-processor-sdk-docs": {"type": "http", "url": "%s"}\n  }\n}\n' "$http_url" > "$workspace/.mcp.json"
          echo "install.sh: wrote $workspace/.mcp.json (HTTP reachable)"
        fi
      elif command -v docker >/dev/null 2>&1 && docker image inspect ti-processor-sdk-docs-mcp >/dev/null 2>&1; then
        echo "install.sh: HTTP not reachable, Docker image exists; starting container..."
        docker run -d --name ti-processor-sdk-docs-mcp -p 7471:7471 ti-processor-sdk-docs-mcp 2>/dev/null || true
        if [[ -e "$workspace/.mcp.json" && $force -ne 1 ]]; then
          echo "install.sh: $workspace/.mcp.json exists; left unchanged (use --force to replace)"
        else
          printf '{\n  "mcpServers": {\n    "ti-processor-sdk-docs": {"type": "http", "url": "%s"}\n  }\n}\n' "$http_url" > "$workspace/.mcp.json"
          echo "install.sh: wrote $workspace/.mcp.json (Docker HTTP mode)"
        fi
      elif command -v docker >/dev/null 2>&1; then
        echo "install.sh: HTTP not reachable, Docker image missing; building..."
        if docker build -t ti-processor-sdk-docs-mcp "$repo/mcp/"; then
          docker run -d --name ti-processor-sdk-docs-mcp -p 7471:7471 ti-processor-sdk-docs-mcp
          if [[ -e "$workspace/.mcp.json" && $force -ne 1 ]]; then
            echo "install.sh: $workspace/.mcp.json exists; left unchanged (use --force to replace)"
          else
            printf '{\n  "mcpServers": {\n    "ti-processor-sdk-docs": {"type": "http", "url": "%s"}\n  }\n}\n' "$http_url" > "$workspace/.mcp.json"
            echo "install.sh: wrote $workspace/.mcp.json (Docker HTTP mode, built image)"
          fi
        else
          echo "install.sh: WARNING: Docker build failed; falling back to stdio mode" >&2
          register_mcp "$url" "stdio" "$repo"
        fi
      else
        echo "install.sh: HTTP not reachable, Docker not available; falling back to stdio mode"
        register_mcp "$url" "stdio" "$repo"
      fi
      ;;
  esac
}

if [[ -n "$mcp" ]]; then
  register_mcp "$mcp" "$mcp_mode" "$repo"
else
  echo "install.sh: docs MCP not registered; run: claude mcp add --transport http ti-processor-sdk-docs <url>  (see mcp/README.md)"
fi
echo "install.sh: ready. Next: cd $workspace && claude, then ask to set up the TI SDK workspace"
echo "install.sh: (the agent runs ti-generate-kb to build the per-device knowledge base from the SDK)."
