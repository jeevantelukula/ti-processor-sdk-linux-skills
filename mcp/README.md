# TI Processor SDK Documentation MCP Server

Lets Claude Code (and any MCP-compatible AI agent) search and read
TI Processor SDK Linux documentation — without loading full HTML pages into context.

Six tools:
- **`ti_processor_sdk_docs_list_variants`** — list all supported (device, OS) combos
- **`ti_processor_sdk_docs_list_versions`** — list available SDK versions for a device (auto-discovered from ti.com)
- **`ti_processor_sdk_docs_search`** — keyword search → ranked list of relevant pages
- **`ti_processor_sdk_docs_read`** — read a specific page as clean text (navigation stripped)
- **`ti_processor_sdk_docs_list_assets`** — list all images/diagrams on a page with semantic context (heading, caption, surrounding text, DOT source for Graphviz diagrams)
- **`ti_processor_sdk_docs_get_asset`** — fetch an asset (image, SVG, PDF) as base64-encoded bytes

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
docker build -t ti-processor-sdk-docs-mcp ./mcp/
```

**Run:**
```bash
docker run -d --name ti-processor-sdk-docs-mcp -p 7471:7471 ti-processor-sdk-docs-mcp
```

**Register with Claude Code:**
```bash
claude mcp add --transport http ti-processor-sdk-docs http://localhost:7471/mcp
```

Override defaults (optional):
```bash
docker run -d -p 7471:7471 \
  -e TI_PROCESSOR_SDK_DEFAULT_DEVICE=AM64X \
  -e TI_PROCESSOR_SDK_DEFAULT_OS=linux \
  ti-processor-sdk-docs-mcp
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
claude mcp add --transport http ti-processor-sdk-docs https://software-dl.ti.com/processor-sdk-linux/mcp
```

**Claude Desktop:**
```json
{
  "mcpServers": {
    "ti-processor-sdk-docs": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://software-dl.ti.com/processor-sdk-linux/mcp"]
    }
  }
}
```

**TI hosting setup (on the software-dl server):**
```bash
docker run -d --restart always -p 7471:7471 ti-processor-sdk-docs-mcp
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
pip3 install "mcp>=1.0,<2" beautifulsoup4 httpx uvicorn snowballstemmer
```

**Register with Claude Code:**
```bash
claude mcp add ti-processor-sdk-docs -- \
  env TI_PROCESSOR_SDK_DOCS_ROOT=/path/to/sphinx-build/docs/12_01_00_05_03 \
  python3 /path/to/mcp/server.py
```

---

## Tool reference

### `ti_processor_sdk_docs_list_variants`

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

### `ti_processor_sdk_docs_list_versions`

| Parameter | Default | Description |
|---|---|---|
| `device` | `AM62X` | Device family — see list_variants for valid values |

Returns JSON with `tool_id` (ti.com download page ID) and `versions` array. Each version has `version` (full underscore form like `12_01_00_05_03`), `short` (dot alias like `12.01`), and `label` (human label with date).

Returns empty `versions` list for devices without a public ti.com download page (e.g. DRA821A, TDA4VM).

**Example:**
```
ti_processor_sdk_docs_list_versions(device="AM62X")
```

---

### `ti_processor_sdk_docs_search`

| Parameter | Default | Description |
|---|---|---|
| `query` | required | Keywords or natural language |
| `device` | `AM62X` | Device family — see list_variants for valid values |
| `os` | `linux` | `linux`, `debian`, or `buildroot` |
| `version` | `latest` | `latest`, full version `12_01_00_05_03`, or short alias `12.01`. Ignored when source=github |
| `rt` | `false` | `true` = use `processor-sdk-linux-rt` URL prefix. Ignored when source=github |
| `source` | `software-dl` | `software-dl` (versioned) or `github` (latest master) |
| `max_results` | `8` | Max pages returned (max 20) |

**Result fields:**

| Field | Always present | Description |
|---|---|---|
| `title` | yes | Page title (HTML stripped) |
| `path` | yes | Relative HTML path — pass directly to `ti_processor_sdk_docs_read` |
| `score` | yes | Relevance score (higher = better) |
| `page_type` | FTS5 only | `release_notes`, `migration_guide`, `getting_started`, `how_to`, `driver_reference`, `overview`, or `other` |
| `matched_terms` | FTS5 only | Which base query words matched this page |
| `coverage` | FTS5 only | Fraction of query words matched (0.0–1.0) |

FTS5 fields are present when `searchindex.db` exists for the SDK version (built by `scripts/build_searchindex.py` in the docs repo). Older SDK versions fall back to Sphinx IDF scoring and return only `title`, `path`, `score`.

**Example — AM62X GPIO:**
```
ti_processor_sdk_docs_search("GPIO pinmux IOPAD RXACTIVE", device="AM62X", os="linux")
```

**Example — AM64X Debian latest:**
```
ti_processor_sdk_docs_search("remoteproc", device="AM64X", os="debian")
```

**Example — historical version:**
```
ti_processor_sdk_docs_search("eMMC boot", device="AM62X", version="12_00_00_07_04")
```

**Example — GitHub Pages (pre-release preview):**
```
ti_processor_sdk_docs_search("GPIO", device="AM62X", source="github")
```

---

### `ti_processor_sdk_docs_read`

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
ti_processor_sdk_docs_read(
    "linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html",
    device="AM62X",
    os="linux",
    version="latest"
)
```

---

### `ti_processor_sdk_docs_list_assets`

List all images and diagrams on a documentation page with semantic context extracted from the surrounding HTML. Works for multimodal agents (vision) and text-only agents alike.

| Parameter | Default | Description |
|---|---|---|
| `path` | required | Relative HTML path from search results |
| `device` | `AM62X` | Device family |
| `os` | `linux` | `linux`, `debian`, or `buildroot` |
| `version` | `latest` | SDK version |
| `source` | `software-dl` | `software-dl` or `github` |
| `content_only` | `true` | `true` = filter out `_static/` UI chrome (logos, icons). `false` = include everything |

**Result structure:**
```json
{
  "assets": [
    {
      "path": "_images/GPIO_driver_diagram.png",
      "mimeType": "image/png",
      "category": "diagram",
      "section_heading": "GPIO",
      "caption": null,
      "context_text": "The GPIO controllers allow interaction with GPIO pins..."
    },
    {
      "path": "_images/graphviz-724b61dc.svg",
      "mimeType": "image/svg+xml",
      "category": "diagram",
      "section_heading": "Buildroot Architecture for TI Devices",
      "caption": "Fig. 1.1 Buildroot-based Linux Architecture for TI Devices",
      "context_text": "Each component in the diagram below is a clickable hyperlink...",
      "dot_source": "digraph buildroot_architecture { rankdir=TB; ... }"
    }
  ],
  "metadata": {
    "page_title": "GPIO — Processor SDK AM62x Documentation",
    "asset_count": 3,
    "static_filtered": 1,
    "total_tags_found": 45,
    "image_tags_found": 4,
    "skipped_assets": 0,
    "status": "success",
    "warnings": []
  }
}
```

**Asset fields:**

| Field | Always present | Description |
|---|---|---|
| `path` | yes | Relative path from doc root — pass directly to `get_asset` |
| `mimeType` | yes | MIME type (`image/png`, `image/svg+xml`, etc.) |
| `category` | yes | `diagram`, `image`, `photo`, or `document` |
| `section_heading` | when found | Nearest `h1`–`h4` heading before the asset |
| `caption` | when found | `<figcaption>` text if asset is inside a `<figure>` |
| `context_text` | when found | First 150 chars of preceding paragraph — for text-only agents |
| `dot_source` | Graphviz only | Full DOT graph source from `<object class="graphviz">` — lets text-only agents read the full architecture topology |

**Example:**
```
ti_processor_sdk_docs_list_assets(
    "buildroot/Overview.html",
    device="AM62X", os="buildroot", version="latest"
)
```

---

### `ti_processor_sdk_docs_get_asset`

Fetch a binary asset (image, SVG, PDF) as base64-encoded bytes. Use `list_assets` first to discover asset paths.

| Parameter | Default | Description |
|---|---|---|
| `asset_path` | required | Relative path from doc root (e.g. `_images/GPIO_driver_diagram.png`) |
| `device` | `AM62X` | Must match device used in `list_assets` |
| `os` | `linux` | Must match OS used in `list_assets` |
| `version` | `latest` | Must match version used in `list_assets` |
| `source` | `software-dl` | Must match source used in `list_assets` |

**Result — always returns inline base64:**
```json
{
  "data": "<base64-encoded bytes>",
  "mimeType": "image/png",
  "size": 22751
}
```

The agent must decode the base64 to view the image. No URL fallback is provided — large assets are also returned as base64. Assets larger than `TI_PROCESSOR_SDK_MAX_ASSET_BYTES` (default 20 MB) are rejected before download.

**Example:**
```
ti_processor_sdk_docs_get_asset(
    "_images/GPIO_driver_diagram.png",
    device="AM62X", os="linux", version="latest"
)
```

---

## How it works

1. **First call for a variant:** Fetches `searchindex.js` (~300 KB) from software-dl.ti.com.
   Contains all page titles and a full term index. No embeddings. Cached in memory.
   Also attempts to fetch `searchindex.db` (~5–15 MB SQLite FTS5 index, if available).

2. **`ti_processor_sdk_docs_search`:** Two search paths:
   - **FTS5 (primary):** If `searchindex.db` exists, runs BM25-ranked FTS5 query with OR
     semantics, explicit column weights (title 10×, code blocks 5×, body text 1×), and TI
     synonym expansion. Returns `page_type`, `matched_terms`, and `coverage` alongside results.
   - **Sphinx IDF (fallback):** If `searchindex.db` absent (old SDK versions), scores pages
     using term-hit IDF with title 3× boost. Returns `title`, `path`, `score` only.

3. **`ti_processor_sdk_docs_read`:** Fetches HTML page (~50–150 KB), strips navigation/sidebar,
   converts headings to `#` markdown and code blocks to ` ``` `. Cached per variant.

4. **Per-variant isolation:** Each (device, os, version, source) combination gets its own
   index and page cache. AM62X v12.01 and AM64X v11.01 never share state.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `TI_PROCESSOR_SDK_DEFAULT_DEVICE` | `AM62X` | Default device for tool parameters |
| `TI_PROCESSOR_SDK_DEFAULT_OS` | `linux` | Default OS for tool parameters |
| `TI_PROCESSOR_SDK_DEFAULT_RT` | `false` | Default rt flag (`1`/`true`/`yes` to enable) |
| `TI_PROCESSOR_SDK_MCP_PORT` | `7471` | HTTP server port |
| `TI_PROCESSOR_SDK_DOC_CONFIGS` | (auto) | Path to processor-sdk-doc `configs/` dir. Auto-detected from adjacent repo; falls back to GitHub API |
| `TI_PROCESSOR_SDK_CATALOG_TTL` | `86400` | Seconds before catalog is re-fetched (24h default) |
| `TI_PROCESSOR_SDK_OS_PATTERNS` | — | Add or override OS URL patterns without editing server.py. Format: `os:prefix:version_suffix:latest_dir` comma-separated. Example: `rtos:processor-sdk-rtos::latest` |
| `TI_PROCESSOR_SDK_TOOL_ID_OVERRIDES` | — | Override ti.com download tool ID per device (for restricted/renamed pages). Format: `DEVICE=TOOL_ID` comma-separated. Example: `AM62DX=PROCESSOR-SDK-LINUX-AM62DX` |
| `TI_PROCESSOR_SDK_MAX_INDEXES` | `50` | Max variants held in memory. Oldest evicted when exceeded |
| `TI_PROCESSOR_SDK_MAX_CONCURRENT_FETCHES` | `10` | Max simultaneous HTTP fetches |
| `TI_PROCESSOR_SDK_MAX_PAGES_PER_VARIANT` | `200` | Max pages cached per variant |
| `TI_PROCESSOR_SDK_MAX_ASSETS_PER_VARIANT` | `200` | Max assets cached in the get_asset LRU cache |
| `TI_PROCESSOR_SDK_MAX_ASSET_BYTES` | `20971520` | Max asset size (bytes) for get_asset — requests over this limit are rejected before download |
| `TI_PROCESSOR_SDK_DOCS_LOCAL_ROOT` | — | Staging/internal mode: path to nightly build root on disk. Structure: `{root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/`. "latest" = highest build ID |
| `TI_PROCESSOR_SDK_DOCS_HTTP_ROOT` | — | Staging/internal mode: base URL of HTTP-served build root. Same directory structure as LOCAL_ROOT. Autoindex must be enabled. SSRF-checked at startup |
| `GITHUB_TOKEN` | — | GitHub PAT. Raises catalog API rate limit from 60 to 5000 req/hr |
| `TI_PROCESSOR_SDK_DOCS_URL` | — | Legacy: lock to single base URL (must be *.ti.com or texasinstruments.github.io) |
| `TI_PROCESSOR_SDK_DOCS_ROOT` | — | Legacy: lock to local filesystem path |

If `TI_PROCESSOR_SDK_DOCS_URL` or `TI_PROCESSOR_SDK_DOCS_ROOT` is set, the server runs in single-variant
legacy mode — device/os/version parameters are accepted but ignored.

---

## Security

- **Input validation**: device, os, version, path, source, and query are validated before use. Path traversal (`../`) and unsafe characters are rejected with a clear error message.
- **SSRF protection**: `TI_PROCESSOR_SDK_DOCS_URL` and `TI_PROCESSOR_SDK_DOCS_HTTP_ROOT` are checked against an allowlist (`*.ti.com`, `texasinstruments.github.io`) at startup. Server exits with an error if the host is not permitted.
- **Concurrency cap**: `TI_PROCESSOR_SDK_MAX_CONCURRENT_FETCHES` (default 10) limits simultaneous HTTP connections.
- **Memory bounds**: indexes are evicted LRU at `TI_PROCESSOR_SDK_MAX_INDEXES` (default 50). Pages per variant are evicted LRU at `TI_PROCESSOR_SDK_MAX_PAGES_PER_VARIANT` (default 200).
- **Query cap**: queries over 500 characters are rejected. Search terms are deduplicated and capped at 50 unique words before scoring.
