#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Install TI Processor SDK Linux skills into a workspace's .claude/ directory.
# Works standalone (cloned repo) and packaged inside an SDK installer.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install.sh --workspace <dir> [--sdk <sdk-root>] [--mcp <url>] [--mcp-mode <mode>] [--force]

  --workspace <dir>  workspace to populate (<dir>/.claude is created if missing; other content
                     already in <dir>/.claude, such as settings.json, is never touched)
  --sdk <sdk-root>   SDK root (contains Rules.make); written to <dir>/.claude/target-profile.yaml.
                     Default: $TI_SDK_ROOT, then $PROCESSOR_SDK_LINUX, then the parent of this
                     repo if it contains Rules.make.
  --mcp <url>        URL of the ti-processor-sdk-docs MCP (HTTP transport, default for the
                     http/docker modes: http://localhost:7471/mcp). Implies --mcp-mode auto.
  --mcp-mode <mode>  register the docs MCP in <dir>/.mcp.json: auto, docker, stdio, none.
                     auto   = use the HTTP server at <url> if it answers, else run it in Docker,
                              else fall back to stdio
                     docker = build/start the Docker image, wait until healthy, register HTTP
                     stdio  = register a local stdio server (.claude/mcp/server.py). It reads the
                              docs from software-dl.ti.com, or from a local Sphinx build if
                              TI_PROCESSOR_SDK_DOCS_ROOT is exported (must contain searchindex.js)
                     none   = do not register (default when neither --mcp nor --mcp-mode is given)
  --force            replace the files this installer owns (its skills, context/, mcp/,
                     AGENTS.md, its .mcp.json entry; lib/ and templates/ left by older
                     versions are removed). Nothing else is removed.
USAGE
}

workspace="" sdk="" mcp="" mcp_mode="" force=0
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
case "$mcp_mode" in
  "") [[ -n "$mcp" ]] && mcp_mode=auto || mcp_mode=none ;;
  auto|docker|stdio|none) ;;
  *) echo "install.sh: --mcp-mode must be auto, docker, stdio or none (got '$mcp_mode')" >&2; exit 2 ;;
esac

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

# --- files owned by this installer -------------------------------------------------------
# Only these paths are created or (with --force) replaced. Anything else in .claude/
# (settings.json, settings.local.json, the user's own skills, commands, agents) is left alone.
# Skills are self-contained (each bundles its scripts/ti-sdk-env.sh etc.), so lib/ and
# templates/ are no longer installed; they stay in the list so --force removes them from
# installs made by older versions of this script.
mkdir -p "$workspace"
workspace="$(cd "$workspace" && pwd)"
dest="$workspace/.claude"
owned=(context mcp lib templates)
for s in "$repo"/skills/*/; do owned+=("skills/$(basename "$s")"); done

existing=()
for p in "${owned[@]}"; do [[ -e "$dest/$p" ]] && existing+=("$p"); done
if [[ ${#existing[@]} -gt 0 && $force -ne 1 ]]; then
  echo "install.sh: already installed in $dest (${#existing[@]} owned paths, e.g. ${existing[0]}); use --force to update" >&2
  exit 1
fi
mkdir -p "$dest/skills"
for p in "${owned[@]}"; do rm -rf "${dest:?}/$p"; done
cp -r "$repo/context" "$dest/"
for s in "$repo"/skills/*/; do cp -r "$s" "$dest/skills/"; done
# Docs MCP server source, so a stdio registration does not depend on where this repo lives.
mkdir -p "$dest/mcp"
cp "$repo/mcp/server.py" "$repo/mcp/requirements.txt" "$dest/mcp/"

# AGENTS.md is ours; keep a copy of a different pre-existing file before replacing it.
if [[ -e "$workspace/AGENTS.md" ]] && ! cmp -s "$repo/AGENTS.md" "$workspace/AGENTS.md"; then
  if [[ $force -eq 1 ]]; then
    cp "$workspace/AGENTS.md" "$workspace/AGENTS.md.orig"
    cp "$repo/AGENTS.md" "$workspace/AGENTS.md"
    echo "install.sh: replaced $workspace/AGENTS.md (previous version saved as AGENTS.md.orig)"
  else
    echo "install.sh: $workspace/AGENTS.md exists; left unchanged (use --force to replace)"
  fi
else
  cp "$repo/AGENTS.md" "$workspace/AGENTS.md"
fi
# CLAUDE.md belongs to the user: only make sure it imports AGENTS.md, never overwrite it.
if [[ ! -e "$workspace/CLAUDE.md" ]]; then
  printf '@AGENTS.md\n' > "$workspace/CLAUDE.md"
elif ! grep -qx '@AGENTS.md' "$workspace/CLAUDE.md"; then
  printf '\n@AGENTS.md\n' >> "$workspace/CLAUDE.md"
  echo "install.sh: appended '@AGENTS.md' to $workspace/CLAUDE.md"
fi

# --- target profile: user answers, so an existing one is kept ---------------------------
profile="$dest/target-profile.yaml"
set_sdk_root() {  # $1 = input profile; replaces the sdk.root line without sed (any char is safe)
  local line
  while IFS= read -r line; do
    if [[ $line == "  root: "* ]]; then printf '  root: %s\n' "$sdk"; else printf '%s\n' "$line"; fi
  done < "$1"
}
if [[ -f "$profile" ]]; then
  if [[ -n "$sdk" ]]; then
    set_sdk_root "$profile" > "$profile.new" && mv "$profile.new" "$profile"
    echo "install.sh: kept $profile, sdk.root set to $sdk"
  else
    echo "install.sh: kept existing $profile"
  fi
elif [[ -n "$sdk" ]]; then
  set_sdk_root "$repo/templates/target-profile.yaml" > "$profile"
  echo "install.sh: SDK root $sdk"
else
  cp "$repo/templates/target-profile.yaml" "$profile"
  echo "install.sh: no SDK found; edit $profile (sdk.root)"
fi

# Generate the platform knowledge base from the SDK sources (non-fatal).
if [[ -n "$sdk" ]]; then
  gen="$dest/skills/ti-generate-kb/scripts/gen-sdk-facts.py"
  if command -v python3 >/dev/null 2>&1 && [[ -f "$gen" ]]; then
    if python3 "$gen" --sdk-root "$sdk" --out-dir "$dest/target-platform"; then
      echo "install.sh: knowledge base in $dest/target-platform (re-run: skill ti-generate-kb)"
    else
      echo "install.sh: WARNING: knowledge base generation failed; run the ti-generate-kb skill later" >&2
    fi
  else
    echo "install.sh: WARNING: python3 or gen-sdk-facts.py missing; knowledge base not generated" >&2
  fi
else
  echo "install.sh: no SDK root; generate the knowledge base later with the ti-generate-kb skill"
fi

# --- docs MCP registration -------------------------------------------------------------
mcp_name=ti-processor-sdk-docs
image=ti-processor-sdk-docs-mcp
http_url="${mcp:-http://localhost:7471/mcp}"
health_url="${http_url%/}"; health_url="${health_url%/mcp}/health"

# True if an MCP server answers at $http_url. GET /health (200) is the server's own
# liveness route. Otherwise GET on the MCP URL: a streamable-HTTP endpoint answers a plain
# GET with 406, which also identifies a remote proxy that only forwards /mcp. Neither
# probe creates an MCP session (a POST initialize would, and the server keeps it).
mcp_reachable() {
  command -v curl >/dev/null 2>&1 || return 1
  [[ $(curl -s -o /dev/null -m 3 -w '%{http_code}' "$health_url" || true) == 200 ]] && return 0
  [[ $(curl -s -o /dev/null -m 3 -w '%{http_code}' "$http_url" || true) == 406 ]]
}

# Poll until the server answers (startup is ~1 s; 30 s covers a cold container).
wait_reachable() {
  for _ in $(seq 1 30); do mcp_reachable && return 0; sleep 1; done
  return 1
}

# Merge our server entry into .mcp.json; other servers in the file are preserved.
# Our existing entry is replaced only with --force. $1 = JSON object for the entry.
write_mcp_entry() {
  local entry=$1 file="$workspace/.mcp.json"
  command -v python3 >/dev/null 2>&1 || { echo "install.sh: python3 needed to write $file" >&2; return 1; }
  python3 - "$file" "$mcp_name" "$entry" "$force" <<'PY'
import json, os, sys
path, name, entry, force = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4] == "1"
data = {}
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
servers = data.setdefault("mcpServers", {})
if name in servers and servers[name] != entry and not force:
    print("install.sh: %s already registers %s; left unchanged (use --force to replace)" % (path, name))
    sys.exit(0)
servers[name] = entry
with open(path + ".tmp", "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
os.replace(path + ".tmp", path)
print("install.sh: registered %s in %s" % (name, path))
PY
}

register_http() {
  write_mcp_entry "$(printf '{"type": "http", "url": "%s"}' "$http_url")"
}

register_stdio() {
  local server="$dest/mcp/server.py" env_json="{}" docs_root="${TI_PROCESSOR_SDK_DOCS_ROOT:-}"
  if [[ -n "$docs_root" ]]; then
    # The server exits at startup if this has no searchindex.js; catch it here instead.
    [[ -f "$docs_root/searchindex.js" ]] || {
      echo "install.sh: TI_PROCESSOR_SDK_DOCS_ROOT=$docs_root has no searchindex.js (need a Sphinx HTML build); not registering stdio" >&2
      return 1; }
    env_json=$(python3 -c 'import json,sys; print(json.dumps({"TI_PROCESSOR_SDK_DOCS_ROOT": sys.argv[1]}))' "$docs_root")
  fi
  write_mcp_entry "$(python3 -c 'import json,sys; print(json.dumps({"command": "python3", "args": [sys.argv[1]], "env": json.loads(sys.argv[2])}))' "$server" "$env_json")"
  if [[ -n "$docs_root" ]]; then
    echo "install.sh: stdio server reads local docs from $docs_root"
  else
    echo "install.sh: stdio server fetches docs from software-dl.ti.com (needs network access)"
  fi
  if ! python3 -c 'import sys; assert sys.version_info >= (3, 10); import mcp, bs4, httpx, snowballstemmer' 2>/dev/null; then
    echo "install.sh: WARNING: the stdio server needs Python >= 3.10 and its packages:" >&2
    echo "install.sh:   python3 -m pip install -r $dest/mcp/requirements.txt" >&2
  fi
}

# Start the container (create it, or restart a stopped one) and wait until it answers.
start_docker() {
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "install.sh: building Docker image $image ..."
    docker build -t "$image" "$repo/mcp/" || { echo "install.sh: WARNING: docker build failed" >&2; return 1; }
  fi
  local state
  state=$(docker container inspect -f '{{.State.Status}}' "$image" 2>/dev/null || true)
  case "$state" in
    running) ;;
    "") echo "install.sh: starting container $image"
        docker run -d --name "$image" -p 7471:7471 "$image" >/dev/null || return 1 ;;
    *)  echo "install.sh: restarting existing container $image (was $state)"
        docker start "$image" >/dev/null || return 1 ;;
  esac
  if ! wait_reachable; then
    echo "install.sh: WARNING: container $image did not answer at $health_url within 30 s; see: docker logs $image" >&2
    return 1
  fi
}

case "$mcp_mode" in
  none)
    echo "install.sh: docs MCP not registered; use --mcp-mode auto|docker|stdio, or: claude mcp add --transport http $mcp_name <url>  (see mcp/README.md)"
    ;;
  stdio)
    [[ -z "$mcp" ]] || echo "install.sh: --mcp $mcp ignored with --mcp-mode stdio"
    register_stdio || echo "install.sh: WARNING: docs MCP not registered" >&2
    ;;
  docker)
    # The container publishes port 7471 on this host; register (and health-check) that.
    if [[ $http_url != http://localhost:7471/* && $http_url != http://127.0.0.1:7471/* ]]; then
      echo "install.sh: --mcp $http_url ignored with --mcp-mode docker; using the local container"
      http_url=http://localhost:7471/mcp health_url=http://localhost:7471/health
    fi
    if command -v docker >/dev/null 2>&1 && start_docker; then
      register_http
    else
      echo "install.sh: WARNING: Docker MCP not available; falling back to stdio" >&2
      register_stdio || echo "install.sh: WARNING: docs MCP not registered" >&2
    fi
    ;;
  auto)
    if mcp_reachable; then
      echo "install.sh: MCP server answers at $http_url"
      register_http
    elif [[ -z "$mcp" || $http_url == http://localhost:7471/* || $http_url == http://127.0.0.1:7471/* ]] \
         && command -v docker >/dev/null 2>&1 && start_docker; then
      register_http
    else
      echo "install.sh: no MCP server at $http_url and no usable Docker; falling back to stdio"
      register_stdio || echo "install.sh: WARNING: docs MCP not registered" >&2
    fi
    ;;
esac
echo "install.sh: ready. Next: cd $workspace && claude, then ask to set up the TI SDK workspace"
echo "install.sh: (the agent runs ti-generate-kb to build the per-device knowledge base from the SDK)."
