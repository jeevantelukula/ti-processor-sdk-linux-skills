# TI Processor SDK Documentation MCP Server

Lets Claude Code (and any MCP-compatible AI agent) search and read
TI Processor SDK Linux documentation — without loading full HTML pages into context.

Three tools:
- **`ti_sdk_docs_list_variants`** — list all 32 supported (device, OS) combos
- **`ti_sdk_docs_search`** — keyword search → ranked list of relevant pages
- **`ti_sdk_docs_read`** — read a specific page as clean text (navigation stripped)

Supports all devices (AM62X, AM64X, AM62PX, J721E, ...), all OS types (linux, debian, buildroot),
and historical versions from software-dl.ti.com.

---

## Two documentation sources

| source= | URL | Version support |
|---|---|---|
| `software-dl` (default) | software-dl.ti.com | `latest` + any historical version (e.g. `12_01_00_05_03`) |
| `github` | texasinstruments.github.io | Latest master only — no version history |

---

## Deployment options

### Option A — Customer self-hosts (Docker)

Each customer runs their own container. No TI infra required.

**Build:**
```bash
docker build -t ti-sdk-docs-mcp ./mcp/
```

**Run:**
```bash
docker run -d --name ti-sdk-docs-mcp -p 7471:7471 ti-sdk-docs-mcp
```

**Register with Claude Code:**
```bash
claude mcp add --transport http ti-sdk-docs http://localhost:7471/mcp
```

Override defaults (optional):
```bash
docker run -d -p 7471:7471 \
  -e TI_SDK_DEFAULT_DEVICE=AM64X \
  -e TI_SDK_DEFAULT_OS=linux \
  ti-sdk-docs-mcp
```

---

### Option B — TI-hosted endpoint

TI hosts one instance. Customers register with a single URL — no Docker, no Python.

**TI endpoint:**
```
https://software-dl.ti.com/processor-sdk-linux/mcp
```

**Customer registration (one command):**
```bash
claude mcp add --transport http ti-sdk-docs https://software-dl.ti.com/processor-sdk-linux/mcp
```

**Claude Desktop:**
```json
{
  "mcpServers": {
    "ti-sdk-docs": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://software-dl.ti.com/processor-sdk-linux/mcp"]
    }
  }
}
```

**TI hosting setup (on the software-dl server):**
```bash
docker run -d --restart always -p 7471:7471 ti-sdk-docs-mcp
```
Then add nginx proxy:
```nginx
location /processor-sdk-linux/mcp {
    proxy_pass http://127.0.0.1:7471/mcp;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

---

### Option C — stdio + local filesystem (SDK developers)

Uses the Sphinx HTML build on disk. Fast, no network dependency.

**Install dependencies:**
```bash
pip3 install mcp beautifulsoup4 httpx uvicorn
```

**Register with Claude Code:**
```bash
claude mcp add ti-sdk-docs -- \
  env TI_SDK_DOCS_ROOT=/path/to/sphinx-build/docs/12_01_00_05_03 \
  python3 /path/to/mcp/server.py
```

---

## Tool reference

### `ti_sdk_docs_list_variants`

No parameters. Returns all supported (device, OS) combos with their software-dl and GitHub Pages URLs.
Catalog is auto-discovered from processor-sdk-doc `configs/` (local repo if present, otherwise GitHub API).

```json
[
  {
    "device": "AM62X",
    "os": "linux",
    "software_dl_url": "https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs",
    "github_pages_url": "https://texasinstruments.github.io/processor-sdk-doc/processor-sdk-linux-AM62X/esd/docs/master"
  },
  ...
]
```

---

### `ti_sdk_docs_search`

| Parameter | Default | Description |
|---|---|---|
| `query` | required | Keywords or natural language |
| `device` | `AM62X` | Device family — see list_variants for valid values |
| `os` | `linux` | `linux`, `debian`, or `buildroot` |
| `version` | `latest` | `latest` or exact version e.g. `12_01_00_05_03`. Ignored when source=github |
| `rt` | `false` | `true` = use `processor-sdk-linux-rt` URL prefix. Ignored when source=github |
| `source` | `software-dl` | `software-dl` (versioned) or `github` (latest master) |
| `max_results` | `8` | Max pages returned (max 20) |

**Example — AM62X GPIO:**
```
ti_sdk_docs_search("GPIO pinmux IOPAD RXACTIVE", device="AM62X", os="linux")
```

**Example — AM64X Debian latest:**
```
ti_sdk_docs_search("remoteproc", device="AM64X", os="debian")
```

**Example — historical version:**
```
ti_sdk_docs_search("eMMC boot", device="AM62X", version="12_00_00_07_04")
```

**Example — GitHub Pages (pre-release preview):**
```
ti_sdk_docs_search("GPIO", device="AM62X", source="github")
```

---

### `ti_sdk_docs_read`

| Parameter | Default | Description |
|---|---|---|
| `path` | required | Relative HTML path from search results |
| `device` | `AM62X` | Must match device used in search |
| `os` | `linux` | Must match OS used in search |
| `version` | `latest` | Must match version used in search |
| `rt` | `false` | Must match rt flag used in search |
| `source` | `software-dl` | Must match source used in search |

**Example:**
```
ti_sdk_docs_read(
    "linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html",
    device="AM62X",
    os="linux",
    version="latest"
)
```

---

## How it works

1. **First call for a variant:** Fetches `searchindex.js` from software-dl.ti.com (~300 KB).
   Contains all page titles and a full term index. No external DB, no embeddings. Cached in memory.

2. **`ti_sdk_docs_search`:** Tokenizes query, scores pages by term-hit count,
   boosts pages whose title matches, returns top N results.

3. **`ti_sdk_docs_read`:** Fetches HTML page (~50–150 KB), strips navigation/sidebar,
   converts headings to `#` markdown and code blocks to ` ``` `. Cached per variant.

4. **Per-variant isolation:** Each (device, os, version, source) combination gets its own
   index and page cache. AM62X v12.01 and AM64X v11.01 never share state.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TI_SDK_DEFAULT_DEVICE` | `AM62X` | Default device for tool parameters |
| `TI_SDK_DEFAULT_OS` | `linux` | Default OS for tool parameters |
| `TI_SDK_DEFAULT_RT` | `false` | Default rt flag (`1`/`true`/`yes` to enable) |
| `TI_SDK_MCP_PORT` | `7471` | HTTP server port |
| `TI_SDK_DOC_CONFIGS` | (auto) | Path to processor-sdk-doc `configs/` dir. Auto-detected from adjacent repo; falls back to GitHub API |
| `TI_SDK_CATALOG_TTL` | `86400` | Seconds before catalog is re-fetched (24h default). New devices added to processor-sdk-doc are picked up on expiry |
| `TI_SDK_MAX_INDEXES` | `50` | Max variants held in memory. Oldest evicted when exceeded |
| `TI_SDK_MAX_CONCURRENT_FETCHES` | `10` | Max simultaneous HTTP fetches. Prevents FD exhaustion under load |
| `TI_SDK_MAX_PAGES_PER_VARIANT` | `200` | Max pages cached per variant. Older pages evicted when exceeded |
| `TI_SDK_DOCS_LOCAL_ROOT` | — | Staging/internal mode: path to nightly build root on disk. Structure: `{root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/`. Reads docs from disk, no HTTP. "latest" = highest build ID |
| `TI_SDK_DOCS_HTTP_ROOT` | — | Staging/internal mode: base URL of nginx-served build root. Same directory structure as LOCAL_ROOT but served over HTTP. nginx autoindex must be enabled. "latest" = highest build ID probed via HEAD. SSRF-checked at startup |
| `GITHUB_TOKEN` | — | GitHub PAT. Raises catalog API rate limit from 60 to 5000 req/hr |
| `TI_SDK_DOCS_URL` | — | Legacy: lock to single base URL (must be *.ti.com or texasinstruments.github.io) |
| `TI_SDK_DOCS_ROOT` | — | Legacy: lock to local filesystem path |

If `TI_SDK_DOCS_URL` or `TI_SDK_DOCS_ROOT` is set, the server runs in single-variant
legacy mode — device/os/version parameters are accepted but ignored.

---

## Security

- **Input validation**: device, os, version, path, source, and query are validated before use. Path traversal (`../`) and unsafe characters are rejected with a clear error message.
- **SSRF protection**: `TI_SDK_DOCS_URL` is checked against an allowlist (`*.ti.com`, `texasinstruments.github.io`) at startup. Server exits with an error if the host is not permitted.
- **Concurrency cap**: `TI_SDK_MAX_CONCURRENT_FETCHES` (default 10) limits simultaneous HTTP connections. Requests queue rather than exhaust file descriptors.
- **Memory bounds**: indexes are evicted LRU at `TI_SDK_MAX_INDEXES` (default 50). Pages per variant are evicted LRU at `TI_SDK_MAX_PAGES_PER_VARIANT` (default 200).
- **Query cap**: queries over 500 characters are rejected. Search terms are deduplicated and capped at 50 unique words before scoring.
