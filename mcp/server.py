#!/usr/bin/env python3
"""TI Processor SDK Documentation MCP Server — generic multi-variant edition.

Three tools:
  ti_sdk_docs_list_variants  — list all 32 supported (device, OS) combos
  ti_sdk_docs_search         — keyword search, scoped to a specific variant
  ti_sdk_docs_read           — read a doc page as clean text

--- SOURCES ---

software-dl (default):  https://software-dl.ti.com/...  versioned + latest symlinks
github:                  https://texasinstruments.github.io/...  latest master only

--- MODES ---

1. stdio (local dev / customer CLI):
   python3 server.py

2. HTTP server (Docker / TI-hosted endpoint):
   python3 server.py --http 7471
   TI endpoint: https://software-dl.ti.com/processor-sdk-linux/mcp

--- ENV VARS ---

TI_SDK_DEFAULT_DEVICE   default device for tools         (default: AM62X)
TI_SDK_DEFAULT_OS       default OS for tools             (default: linux)
TI_SDK_DEFAULT_RT       default rt flag                  (default: false)
TI_SDK_MCP_PORT         HTTP server port                 (default: 7471)
TI_SDK_DOC_CONFIGS      path to processor-sdk-doc configs/ dir
                        (auto-detected from adjacent repo if not set;
                         falls back to GitHub API)
TI_SDK_CATALOG_TTL      catalog re-fetch interval in seconds (default: 86400 = 24h)
TI_SDK_MAX_INDEXES              max variants in memory before LRU eviction (default: 50)
TI_SDK_MAX_CONCURRENT_FETCHES  max simultaneous HTTP fetches (default: 10)
TI_SDK_MAX_PAGES_PER_VARIANT   max cached pages per variant before LRU eviction (default: 200)
GITHUB_TOKEN                   GitHub PAT for API auth (60/hr → 5000/hr; avoids rate limits)
TI_SDK_DOCS_LOCAL_ROOT         local nightly build root for staging/internal server mode
                               structure: {root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/
                               "latest" resolves to highest build ID for each device+OS

Legacy single-variant (backward compat):
TI_SDK_DOCS_URL         base URL  — locks tools to this URL only
TI_SDK_DOCS_ROOT        local path — locks tools to this path only
"""

import argparse
import asyncio
import json
import os as _os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP


class VariantNotFoundError(Exception):
    """Raised when a device/OS/version combo does not exist on the docs server."""


# ---------------------------------------------------------------------------
# Guard rails — input validation, SSRF prevention, abuse limits
# ---------------------------------------------------------------------------

_VALID_SOURCES       = frozenset({"software-dl", "github"})
_DEVICE_RE           = re.compile(r'^[A-Z][A-Z0-9]{1,19}$')
_OS_RE               = re.compile(r'^[a-z][a-z0-9]{0,19}$')
_VERSION_RE          = re.compile(r'^(latest|\d{1,4}(_\d{1,4}){2,5})$')
_PATH_SAFE_RE        = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_/.\-]*$')
_MAX_QUERY_LEN       = 500   # chars — prevents CPU exhaustion via regex on huge strings
_MAX_PATH_LEN        = 300   # chars — prevents oversized URL construction
_MAX_SEARCH_RESULTS  = 20    # hard cap regardless of caller-supplied max_results
_MAX_SEARCH_TERMS    = 50    # unique terms scored per query — caps scoring loop

# SSRF allowlist — only these hosts may appear in TI_SDK_DOCS_URL
_ALLOWED_URL_HOSTS = frozenset({"software-dl.ti.com", "texasinstruments.github.io"})


def _check_url_host(url: str, var_name: str = "URL") -> None:
    """Raise ValueError if url is not on an allowed host (SSRF prevention)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"{var_name} must use http or https scheme, got {parsed.scheme!r}"
        )
    host = (parsed.hostname or "").lower()
    if not (host in _ALLOWED_URL_HOSTS or host.endswith(".ti.com") or host == "ti.com"):
        raise ValueError(
            f"{var_name} host {host!r} is not in the allowed list. "
            "Permitted: *.ti.com and texasinstruments.github.io."
        )


def _validate(
    device: str | None = None,
    os_type: str | None = None,
    version: str | None = None,
    path: str | None = None,
    source: str | None = None,
    query: str | None = None,
) -> str | None:
    """Validate tool inputs. Returns an error string on failure, None on success."""
    if device is not None and not _DEVICE_RE.match(device):
        return (
            f"Invalid device {device!r}: must be 1-20 uppercase alphanumeric chars "
            "(e.g. 'AM62X'). Call ti_sdk_docs_list_variants to see valid devices."
        )
    if os_type is not None and not _OS_RE.match(os_type):
        return (
            f"Invalid os {os_type!r}: must be lowercase alphanumeric, max 20 chars "
            "(e.g. 'linux', 'debian', 'buildroot'). "
            "Call ti_sdk_docs_list_variants to see valid OS types."
        )
    if version is not None and not _VERSION_RE.match(version):
        return (
            f"Invalid version {version!r}: must be 'latest' or a version string "
            "like '12_01_00_05_03'."
        )
    if source is not None and source not in _VALID_SOURCES:
        return f"Invalid source {source!r}: must be 'software-dl' or 'github'."
    if path is not None:
        if len(path) > _MAX_PATH_LEN:
            return f"Path too long: max {_MAX_PATH_LEN} characters."
        norm = path.replace("\\", "/")
        if ".." in norm.split("/"):
            return "Invalid path: '..' (path traversal) is not allowed."
        # Strip optional .html suffix before character-class check
        check = norm[:-5] if norm.endswith(".html") else norm
        if check and not _PATH_SAFE_RE.match(check):
            return (
                f"Invalid path {path!r}: only alphanumeric, '/', '_', '-', '.' allowed."
            )
    if query is not None and len(query) > _MAX_QUERY_LEN:
        return f"Query too long: max {_MAX_QUERY_LEN} characters."
    return None


# ---------------------------------------------------------------------------
# Catalog — dynamically loaded from processor-sdk-doc configs/
#
# Mirrors build_matrix.py logic: scan {DEVICE}_{OS}_{config.txt|tags.py|toc.txt}
# Source priority: TI_SDK_DOC_CONFIGS env var → adjacent repo → GitHub tree API
# ---------------------------------------------------------------------------

_EXCLUDED_OS: set[str] = set()  # all OS types included

_CATALOG: list[dict[str, str]] | None = None
_CATALOG_LOCK: asyncio.Lock | None = None
_CATALOG_LOADED_AT: float = 0.0
# Catalog TTL: re-fetch after this many seconds (default 24h).
# New devices added to processor-sdk-doc will be picked up on next expiry.
_CATALOG_TTL: int = int(_os.environ.get("TI_SDK_CATALOG_TTL", "86400"))

# GitHub token for authenticated API requests (60/hr → 5000/hr).
# Set GITHUB_TOKEN env var to avoid rate limits on busy servers.
_GITHUB_TOKEN: str = _os.environ.get("GITHUB_TOKEN", "")

# Resolve local configs/ path at import time
_env_configs = _os.environ.get("TI_SDK_DOC_CONFIGS", "")
if _env_configs:
    _LOCAL_CONFIGS: Path | None = Path(_env_configs)
else:
    _adj = Path(__file__).parent.parent.parent / "processor-sdk-doc" / "configs"
    _LOCAL_CONFIGS = _adj if _adj.is_dir() else None

_REQUIRED_FRAGMENTS = {"config.txt", "tags.py", "toc.txt"}


def _catalog_from_local(configs: Path) -> list[dict[str, str]]:
    result = []
    for platform in sorted(configs.glob("*/")):
        if not platform.is_dir():
            continue
        device = platform.stem
        fragments: set[str] = set()
        for frag in _REQUIRED_FRAGMENTS:
            for f in platform.glob(f"{device}_*_{frag}"):
                fragments.add(f.name)
        os_names = {name.split("_")[1] for name in fragments}
        for os_name in sorted(os_names):
            if os_name in _EXCLUDED_OS:
                continue
            if all(f"{device}_{os_name}_{frag}" in fragments for frag in _REQUIRED_FRAGMENTS):
                result.append({"device": device, "os": os_name})
    return result


async def _catalog_from_github() -> list[dict[str, str]]:
    url = (
        "https://api.github.com/repos/TexasInstruments/processor-sdk-doc"
        "/git/trees/master?recursive=1"
    )
    headers = {"Accept": "application/vnd.github+json"}
    if _GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {_GITHUB_TOKEN}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        async with _http_semaphore():
            r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    if data.get("truncated"):
        # Repo too large for single tree fetch. Fall back to TI_SDK_DOC_CONFIGS env var
        # or a local clone to get the complete catalog.
        sys.stderr.write(
            "Warning: GitHub tree response truncated — catalog may be incomplete.\n"
            "  Set TI_SDK_DOC_CONFIGS=/path/to/processor-sdk-doc/configs for complete catalog.\n"
        )

    found: dict[tuple[str, str], set[str]] = {}
    for item in data.get("tree", []):
        path = item.get("path", "")
        if not path.startswith("configs/"):
            continue
        parts = path.split("/")
        if len(parts) != 3:
            continue
        device, filename = parts[1], parts[2]
        if not filename.startswith(f"{device}_"):
            continue
        rest = filename[len(device) + 1:]  # strip "DEVICE_" prefix
        for frag in _REQUIRED_FRAGMENTS:
            if rest.endswith(f"_{frag}"):
                os_name = rest[: -(len(frag) + 1)]
                if os_name not in _EXCLUDED_OS:
                    found.setdefault((device, os_name), set()).add(frag)
                break

    return [
        {"device": device, "os": os_name}
        for (device, os_name), frags in sorted(found.items())
        if frags == _REQUIRED_FRAGMENTS
    ]


async def _ensure_catalog() -> list[dict[str, str]]:
    global _CATALOG, _CATALOG_LOCK, _CATALOG_LOADED_AT
    now = time.monotonic()
    if _CATALOG is not None and (now - _CATALOG_LOADED_AT) < _CATALOG_TTL:
        return _CATALOG
    if _CATALOG_LOCK is None:
        _CATALOG_LOCK = asyncio.Lock()
    async with _CATALOG_LOCK:
        now = time.monotonic()
        if _CATALOG is not None and (now - _CATALOG_LOADED_AT) < _CATALOG_TTL:
            return _CATALOG
        if _LOCAL_DOCS_ROOT is not None:
            # Nightly build root (swubn04-style): scan {device}-evm/{build}/processor-sdk-{os}-docs/
            _CATALOG = _catalog_from_local_root(_LOCAL_DOCS_ROOT)
            sys.stderr.write(f"Catalog: {len(_CATALOG)} variants (local root {_LOCAL_DOCS_ROOT})\n")
        elif _LOCAL_CONFIGS is not None:
            # processor-sdk-doc configs/ dir (processor-sdk-doc repo clone)
            _CATALOG = _catalog_from_local(_LOCAL_CONFIGS)
            sys.stderr.write(f"Catalog: {len(_CATALOG)} variants (local configs {_LOCAL_CONFIGS})\n")
        else:
            _CATALOG = await _catalog_from_github()
            sys.stderr.write(f"Catalog: {len(_CATALOG)} variants (GitHub)\n")
        _CATALOG_LOADED_AT = time.monotonic()
        return _CATALOG

# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

# software-dl URL components per OS type
_OS_PREFIX: dict[str, str] = {
    "linux":     "processor-sdk-linux",
    "debian":    "processor-sdk-linux",
    "buildroot": "processor-sdk-linux",
    "android":   "processor-sdk-android",
    "edgeai":    "processor-sdk-linux",   # edgeai lives inside the linux SDK docs tree
}
_OS_SUFFIX: dict[str, str] = {
    "linux":     "",
    "debian":    "_Debian",
    "buildroot": "_Buildroot",
    "android":   "",
    "edgeai":    "",
}
_OS_LATEST: dict[str, str] = {
    "linux":     "latest",
    "debian":    "latest_Debian",
    "buildroot": "latest_Buildroot",
    "android":   "latest",
    "edgeai":    "latest",
}


def _software_dl_url(device: str, os_type: str, version: str, rt: bool) -> str:
    if os_type not in _OS_PREFIX:
        # New OS type added to processor-sdk-doc configs but not yet mapped here.
        # Using linux prefix as fallback; add to _OS_PREFIX/_OS_SUFFIX/_OS_LATEST to fix.
        sys.stderr.write(
            f"Warning: unknown OS type '{os_type}' — falling back to processor-sdk-linux prefix. "
            f"Add '{os_type}' to _OS_PREFIX/_OS_SUFFIX/_OS_LATEST in server.py.\n"
        )
    # rt only applies to linux; ignored for android/edgeai/debian/buildroot
    base_prefix = _OS_PREFIX.get(os_type, "processor-sdk-linux")
    if rt and os_type == "linux":
        base_prefix = "processor-sdk-linux-rt"
    ver_dir = _OS_LATEST.get(os_type, "latest") if version == "latest" else version + _OS_SUFFIX.get(os_type, "")
    return f"https://software-dl.ti.com/{base_prefix}/esd/{device}/{ver_dir}/exports/docs"


def _github_pages_url(device: str, os_type: str) -> str:
    return (
        f"https://texasinstruments.github.io/processor-sdk-doc"
        f"/processor-sdk-{os_type}-{device}/esd/docs/master"
    )


def _make_url(device: str, os_type: str, version: str, rt: bool, source: str) -> str:
    if source == "github":
        return _github_pages_url(device, os_type)
    return _software_dl_url(device, os_type, version, rt)


# ---------------------------------------------------------------------------
# Local docs root — multi-variant disk read (staging / internal server mode)
#
# Set TI_SDK_DOCS_LOCAL_ROOT to the nightly build root, e.g.:
#   /datalocal/nightly_builds/nightly/smpusdk-docs-build/
#
# Expected directory structure:
#   {root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/searchindex.js
#
# "latest" resolves to the build with the highest numeric build ID.
# Specific version strings are matched as substrings of the build dir name.
# ---------------------------------------------------------------------------

_LOCAL_DOCS_ROOT: Path | None = (
    Path(_os.environ["TI_SDK_DOCS_LOCAL_ROOT"])
    if "TI_SDK_DOCS_LOCAL_ROOT" in _os.environ else None
)


def _local_device_dir(device: str) -> str:
    """AM62XX -> am62xx-evm"""
    return device.lower() + "-evm"


def _local_os_docs_dir(os_type: str) -> str:
    """linux -> processor-sdk-linux-docs"""
    return f"processor-sdk-{os_type}-docs"


def _local_latest_docs(device_path: Path, os_type: str) -> Path | None:
    """Return path to latest build's docs dir for given OS (highest build ID), or None."""
    os_docs_name = _local_os_docs_dir(os_type)
    candidates: list[tuple[int, Path]] = []
    try:
        for build_dir in device_path.iterdir():
            if not build_dir.is_dir():
                continue
            docs_path = build_dir / os_docs_name
            if not (docs_path / "searchindex.js").exists():
                continue
            try:
                build_id = int(build_dir.name.split("_")[0])
                candidates.append((build_id, docs_path))
            except (ValueError, IndexError):
                continue
    except PermissionError:
        return None
    return max(candidates, key=lambda x: x[0])[1] if candidates else None


def _local_versioned_docs(device_path: Path, os_type: str, version: str) -> Path | None:
    """Return docs path for build dir whose name contains version as substring."""
    os_docs_name = _local_os_docs_dir(os_type)
    try:
        for build_dir in sorted(device_path.iterdir()):
            if version not in build_dir.name:
                continue
            docs_path = build_dir / os_docs_name
            if (docs_path / "searchindex.js").exists():
                return docs_path
    except PermissionError:
        return None
    return None


def _resolve_local_docs(device: str, os_type: str, version: str) -> Path | None:
    """Resolve local docs Path for (device, os_type, version). Returns None if unavailable."""
    if _LOCAL_DOCS_ROOT is None:
        return None
    device_path = _LOCAL_DOCS_ROOT / _local_device_dir(device)
    if not device_path.is_dir():
        return None
    if version == "latest":
        return _local_latest_docs(device_path, os_type)
    return _local_versioned_docs(device_path, os_type, version)


def _catalog_from_local_root(root: Path) -> list[dict[str, str]]:
    """Discover (device, os) combos from nightly build root structure."""
    result = []
    known_os = ["linux", "debian", "buildroot", "android", "edgeai"]
    try:
        dirs = sorted(root.iterdir())
    except PermissionError:
        return result
    for device_path in dirs:
        if not device_path.is_dir() or not device_path.name.endswith("-evm"):
            continue
        device = device_path.name[:-4].upper()  # am62xx-evm -> AM62XX
        for os_type in known_os:
            if _local_latest_docs(device_path, os_type) is not None:
                result.append({"device": device, "os": os_type})
    return result


# ---------------------------------------------------------------------------
# Legacy env var backward compat (TI_SDK_DOCS_URL / TI_SDK_DOCS_ROOT)
# ---------------------------------------------------------------------------

_LEGACY_URL:  str | None  = _os.environ.get("TI_SDK_DOCS_URL", "").rstrip("/") or None
_LEGACY_ROOT: Path | None = (
    Path(_os.environ["TI_SDK_DOCS_ROOT"]) if "TI_SDK_DOCS_ROOT" in _os.environ
    else None
)

# SSRF guard — fail fast if the operator pointed TI_SDK_DOCS_URL at an unexpected host
if _LEGACY_URL is not None:
    try:
        _check_url_host(_LEGACY_URL, "TI_SDK_DOCS_URL")
    except ValueError as _ssrf_exc:
        sys.stderr.write(f"ERROR: {_ssrf_exc}\n")
        sys.exit(1)

_LEGACY_KEY = ("__legacy__", "__legacy__", "__legacy__", False, "__legacy__")

# ---------------------------------------------------------------------------
# Per-variant lazy state
# ---------------------------------------------------------------------------

_INDEXES:      dict[tuple, dict[str, Any]] = {}
_INDEX_LOCKS:  dict[tuple, asyncio.Lock]   = {}
_PAGE_CACHES:  dict[tuple, dict[str, str]] = {}
_INDEX_ERRORS: dict[tuple, str]            = {}  # permanent errors (404, parse fail) — not retried
_GLOBAL_LOCK:  asyncio.Lock | None = None

# Max variants held in memory. Oldest evicted when limit reached.
# Each variant holds ~300KB index + up to _MAX_PAGES_PER_VARIANT cached pages.
_MAX_INDEXES: int = int(_os.environ.get("TI_SDK_MAX_INDEXES", "50"))

# Max simultaneous HTTP fetches — prevents FD exhaustion under concurrent tool calls.
# 50 variants × 10 concurrent = bounded connection pool even under heavy load.
_MAX_CONCURRENT_FETCHES: int = int(_os.environ.get("TI_SDK_MAX_CONCURRENT_FETCHES", "10"))
_FETCH_SEMAPHORE: asyncio.Semaphore | None = None

# Max pages cached per variant — prevents memory growth via repeated ti_sdk_docs_read calls.
# 50 variants × 200 pages × ~60KB avg ≈ 600MB worst case (vs unbounded without cap).
_MAX_PAGES_PER_VARIANT: int = int(_os.environ.get("TI_SDK_MAX_PAGES_PER_VARIANT", "200"))


def _http_semaphore() -> asyncio.Semaphore:
    global _FETCH_SEMAPHORE
    if _FETCH_SEMAPHORE is None:
        _FETCH_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
    return _FETCH_SEMAPHORE


def _global_lock() -> asyncio.Lock:
    global _GLOBAL_LOCK
    if _GLOBAL_LOCK is None:
        _GLOBAL_LOCK = asyncio.Lock()
    return _GLOBAL_LOCK


def _cache_key(device: str, os_type: str, version: str, rt: bool, source: str) -> tuple:
    if source == "github":
        return (device, os_type, "master", False, "github")
    return (device, os_type, version, rt, "software-dl")


def _is_legacy_mode() -> bool:
    return _LEGACY_URL is not None or _LEGACY_ROOT is not None


# ---------------------------------------------------------------------------
# Index parsing + lazy loading
# ---------------------------------------------------------------------------

def _parse_index(raw: str) -> dict[str, Any]:
    raw = re.sub(r"^Search\.setIndex\(", "", raw)
    raw = raw.rstrip().rstrip(")")
    return json.loads(raw)


async def _ensure_index(device: str, os_type: str, version: str, rt: bool, source: str) -> dict[str, Any]:
    legacy = _is_legacy_mode()
    key = _LEGACY_KEY if legacy else _cache_key(device, os_type, version, rt, source)

    # Permanent error — don't retry (version genuinely doesn't exist, parse failure, etc.)
    if key in _INDEX_ERRORS:
        raise VariantNotFoundError(_INDEX_ERRORS[key])

    if key in _INDEXES:
        return _INDEXES[key]

    async with _global_lock():
        if key not in _INDEX_LOCKS:
            _INDEX_LOCKS[key] = asyncio.Lock()

    async with _INDEX_LOCKS[key]:
        if key in _INDEX_ERRORS:
            raise VariantNotFoundError(_INDEX_ERRORS[key])
        if key in _INDEXES:
            return _INDEXES[key]

        try:
            if legacy:
                if _LEGACY_ROOT is not None:
                    raw = (_LEGACY_ROOT / "searchindex.js").read_text(encoding="utf-8")
                else:
                    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                        async with _http_semaphore():
                            r = await client.get(f"{_LEGACY_URL}/searchindex.js")
                        r.raise_for_status()
                        raw = r.text
            else:
                # Check local docs root first (staging/internal server mode)
                local_path = _resolve_local_docs(device, os_type, version) if source == "software-dl" else None
                if local_path is not None:
                    raw = (local_path / "searchindex.js").read_text(encoding="utf-8")
                else:
                    base_url = _make_url(device, os_type, version, rt, source)
                    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                        async with _http_semaphore():
                            r = await client.get(f"{base_url}/searchindex.js")
                        r.raise_for_status()
                        raw = r.text

            idx = _parse_index(raw)

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                # Permanent: version/device doesn't exist on server — cache, don't retry
                msg = (
                    f"Docs not found for device={device!r} os={os_type!r} version={version!r} "
                    f"source={source!r} (HTTP 404). "
                    "The version may not exist yet, or the device was added after this release. "
                    "Call ti_sdk_docs_list_variants to see available combos, "
                    "or try version='latest'."
                )
                _INDEX_ERRORS[key] = msg
                raise VariantNotFoundError(msg) from exc
            # Transient (5xx, rate limit, etc.) — don't cache, allow retry on next call
            raise

        except (json.JSONDecodeError, ValueError) as exc:
            # Permanent: malformed searchindex.js in old/broken release — cache, don't retry
            msg = (
                f"searchindex.js for device={device!r} os={os_type!r} version={version!r} "
                f"is malformed and cannot be parsed: {exc}. "
                "This version may predate Sphinx search or have a corrupted build."
            )
            _INDEX_ERRORS[key] = msg
            raise VariantNotFoundError(msg) from exc

        # LRU eviction — keep memory bounded
        if len(_INDEXES) >= _MAX_INDEXES:
            oldest_key = next(iter(_INDEXES))
            del _INDEXES[oldest_key]
            _PAGE_CACHES.pop(oldest_key, None)
            _INDEX_LOCKS.pop(oldest_key, None)

        _INDEXES[key] = idx
        _PAGE_CACHES.setdefault(key, {})
        return idx


# Pre-load synchronously in legacy local mode to fail fast on bad path
if _LEGACY_ROOT is not None:
    _si_path = _LEGACY_ROOT / "searchindex.js"
    if not _si_path.exists():
        sys.stderr.write(f"ERROR: searchindex.js not found at {_si_path}\n")
        sys.exit(1)
    _INDEXES[_LEGACY_KEY] = _parse_index(_si_path.read_text(encoding="utf-8"))
    _PAGE_CACHES[_LEGACY_KEY] = {}

# ---------------------------------------------------------------------------
# Page fetching / reading
# ---------------------------------------------------------------------------

async def _fetch_page(path: str, device: str, os_type: str, version: str, rt: bool, source: str) -> str:
    legacy = _is_legacy_mode()
    key = _LEGACY_KEY if legacy else _cache_key(device, os_type, version, rt, source)
    cache = _PAGE_CACHES.setdefault(key, {})

    if path in cache:
        return cache[path]

    if legacy and _LEGACY_ROOT is not None:
        text = _read_local_file(path, _LEGACY_ROOT)
    elif not legacy and source == "software-dl":
        local_path = _resolve_local_docs(device, os_type, version)
        if local_path is not None:
            text = _read_local_file(path, local_path)
        else:
            base_url = _make_url(device, os_type, version, rt, source)
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    async with _http_semaphore():
                        r = await client.get(f"{base_url}/{path}")
                    if r.status_code == 404:
                        return f"Page not found: {path}\nUse ti_sdk_docs_search to find valid paths."
                    r.raise_for_status()
                    text = _html_to_text(r.text, path)
            except httpx.HTTPStatusError as exc:
                return f"HTTP {exc.response.status_code} error fetching {path}: {exc.response.reason_phrase}"
            except httpx.RequestError as exc:
                return f"Network error fetching {path}: {exc}"
    else:
        base_url = _LEGACY_URL if (legacy and _LEGACY_URL) else _make_url(device, os_type, version, rt, source)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                async with _http_semaphore():
                    r = await client.get(f"{base_url}/{path}")
                if r.status_code == 404:
                    return f"Page not found: {path}\nUse ti_sdk_docs_search to find valid paths."
                r.raise_for_status()
                text = _html_to_text(r.text, path)
        except httpx.HTTPStatusError as exc:
            return f"HTTP {exc.response.status_code} error fetching {path}: {exc.response.reason_phrase}"
        except httpx.RequestError as exc:
            return f"Network error fetching {path}: {exc}"

    # LRU page cache eviction — keeps per-variant memory bounded
    if len(cache) >= _MAX_PAGES_PER_VARIANT:
        oldest = next(iter(cache))
        del cache[oldest]
    cache[path] = text
    return text


def _read_local_file(path: str, root: Path) -> str:
    full = (root / path).resolve()
    if not str(full).startswith(str(root.resolve())):
        return "Error: path outside docs root"
    if not full.exists():
        return f"Page not found: {path}\nUse ti_sdk_docs_search to find valid paths."
    return _html_to_text(full.read_text(encoding="utf-8", errors="replace"), path)


# ---------------------------------------------------------------------------
# HTML → clean text
# ---------------------------------------------------------------------------

def _html_to_text(html: str, path: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for sel in (
        "nav", ".wy-nav-side", ".wy-nav-top", ".wy-breadcrumbs",
        "footer", "script", "style", ".sphinxsidebar", ".related",
        ".headerlink", "#searchbox",
    ):
        for tag in soup.select(sel):
            tag.decompose()

    main = (
        soup.select_one('div[role="main"]')
        or soup.select_one(".document")
        or soup.select_one("article")
        or soup.select_one(".body")
        or soup.body
    )
    lines: list[str] = []
    _node_to_lines(main or soup, lines)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _node_to_lines(node: Any, lines: list[str]) -> None:
    from bs4 import NavigableString, Tag
    if isinstance(node, NavigableString):
        if t := str(node).rstrip():
            if t.strip():
                lines.append(t)
        return
    if not isinstance(node, Tag):
        return
    tag = node.name.lower()
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        lines.extend(["", "#" * int(tag[1]) + " " + node.get_text(" ", strip=True), ""])
        return
    if tag == "pre":
        lines.extend(["", "```", node.get_text().rstrip(), "```", ""])
        return
    if tag == "code" and node.parent and node.parent.name != "pre":
        lines.append(f"`{node.get_text().strip()}`")
        return
    if tag == "li":
        lines.append("- " + node.get_text(" ", strip=True))
        return
    if tag == "p":
        if t := node.get_text(" ", strip=True):
            lines.extend(["", t, ""])
        return
    if tag == "table":
        _table_to_lines(node, lines)
        return
    if tag == "br":
        lines.append("")
        return
    for child in node.children:
        _node_to_lines(child, lines)


def _table_to_lines(table: Any, lines: list[str]) -> None:
    lines.append("")
    for i, row in enumerate(table.find_all("tr")):
        cells = [td.get_text(" ", strip=True) for td in row.find_all(["th", "td"])]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    lines.append("")


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

_DEFAULT_DEVICE = _os.environ.get("TI_SDK_DEFAULT_DEVICE", "AM62X")
_DEFAULT_OS     = _os.environ.get("TI_SDK_DEFAULT_OS",     "linux")
_DEFAULT_RT     = _os.environ.get("TI_SDK_DEFAULT_RT",     "").lower() in ("1", "true", "yes")
_HTTP_PORT      = int(_os.environ.get("TI_SDK_MCP_PORT",   "7471"))

mcp = FastMCP(
    "ti-sdk-docs",
    instructions=(
        "Search and read TI Processor SDK documentation across all devices and OS types. "
        "Supports AM62X, AM64X, AM62PX, J721E and 28 more devices; "
        "linux, debian, and buildroot; "
        "all historical versions from software-dl.ti.com plus latest master from GitHub Pages. "
        "Call ti_sdk_docs_list_variants first to discover available combos. "
        "Use ti_sdk_docs_search to find pages by topic, ti_sdk_docs_read for full content."
    ),
    host="0.0.0.0",
    port=_HTTP_PORT,
)


@mcp.tool()
async def ti_sdk_docs_list_variants() -> str:
    """List all supported (device, OS) combinations with their documentation URLs.

    Catalog is auto-discovered from the processor-sdk-doc configs/ directory
    (local repo if available, otherwise fetched from GitHub).

    Returns:
        JSON array of {device, os, software_dl_url, github_pages_url} entries.
        software_dl_url supports versioned access (version parameter in search/read).
        github_pages_url always points to latest master.
    """
    catalog = await _ensure_catalog()
    result = [
        {
            "device": e["device"],
            "os": e["os"],
            "software_dl_url": _software_dl_url(e["device"], e["os"], "latest", False),
            "github_pages_url": _github_pages_url(e["device"], e["os"]),
        }
        for e in catalog
    ]
    return json.dumps(result, indent=2)


def _doc_indices(v: Any) -> list[int]:
    return [v] if isinstance(v, int) else list(v)


@mcp.tool()
async def ti_sdk_docs_search(
    query: str,
    device: str = _DEFAULT_DEVICE,
    os: str = _DEFAULT_OS,
    version: str = "latest",
    rt: bool = _DEFAULT_RT,
    source: str = "software-dl",
    max_results: int = 8,
) -> str:
    """Search TI Processor SDK Linux documentation.

    Args:
        query: Keywords or natural language (e.g. "GPIO pinmux IOPAD",
               "eMMC boot flashing", "remoteproc M4F firmware RPMsg").
        device: Target device family (e.g. "AM62X", "AM64X", "AM62PX", "J721E").
                Run ti_sdk_docs_list_variants to see all 32 supported combos.
        os: OS type: "linux" (default), "debian", or "buildroot".
        version: SDK version string ("latest" or e.g. "12_01_00_05_03").
                 Ignored when source="github" (always latest master).
        rt: True to query the processor-sdk-linux-rt prefix. Ignored when source="github".
        source: "software-dl" (default, supports versioned history) or
                "github" (GitHub Pages, latest master only).
        max_results: Pages to return, default 8, max 20.

    Returns:
        JSON array sorted by relevance. Each entry: title, path, score.
        Pass path to ti_sdk_docs_read to get full content.
    """
    err = _validate(device=device, os_type=os, version=version, source=source, query=query)
    if err:
        return err
    max_results = min(max(1, max_results), _MAX_SEARCH_RESULTS)
    try:
        idx = await _ensure_index(device, os, version, rt, source)
    except VariantNotFoundError as exc:
        return str(exc)
    docnames: list[str] = idx["docnames"]
    titles:   list[str] = idx["titles"]
    terms:    dict[str, Any] = idx["terms"]

    # Deduplicate + cap unique terms — prevents quadratic CPU blowup on repeated/long inputs
    words = list(dict.fromkeys(re.findall(r"[a-z][a-z0-9]*", query.lower())))[:_MAX_SEARCH_TERMS]
    if not words:
        return json.dumps([])

    scores: dict[int, int] = {}
    for word in words:
        hits = terms.get(word)
        if hits is None:
            for stem in (word.rstrip("s"), word.rstrip("ing")):
                if stem != word:
                    hits = terms.get(stem)
                    if hits is not None:
                        break
        if hits is not None:
            for doc_idx in _doc_indices(hits):
                scores[doc_idx] = scores.get(doc_idx, 0) + 1

    for doc_idx, title in enumerate(titles):
        if any(w in title.lower() for w in words):
            scores[doc_idx] = scores.get(doc_idx, 0) + 3

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max_results]
    results = [
        {"title": titles[i], "path": docnames[i] + ".html", "score": s}
        for i, s in ranked
    ]
    return json.dumps(results, indent=2)


@mcp.tool()
async def ti_sdk_docs_read(
    path: str,
    device: str = _DEFAULT_DEVICE,
    os: str = _DEFAULT_OS,
    version: str = "latest",
    rt: bool = _DEFAULT_RT,
    source: str = "software-dl",
) -> str:
    """Read a TI Processor SDK documentation page as clean text.

    Args:
        path: Relative HTML path from ti_sdk_docs_search
              (e.g. "linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html").
              .html extension optional.
        device: Target device — must match the device used in ti_sdk_docs_search.
        os: OS type: "linux", "debian", or "buildroot".
        version: SDK version ("latest" or e.g. "12_01_00_05_03"). Ignored when source="github".
        rt: True to use processor-sdk-linux-rt prefix. Ignored when source="github".
        source: "software-dl" (default, versioned) or "github" (latest master only).

    Returns:
        Clean text with headings as # markdown, code blocks as ```.
        Sidebar and navigation are stripped.
    """
    err = _validate(device=device, os_type=os, version=version, source=source, path=path)
    if err:
        return err
    if not path.endswith(".html"):
        path = path + ".html"
    try:
        await _ensure_index(device, os, version, rt, source)
    except VariantNotFoundError as exc:
        return str(exc)
    return await _fetch_page(path, device, os, version, rt, source)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="TI SDK Docs MCP Server")
    p.add_argument(
        "--http", metavar="PORT", type=int, nargs="?", const=8000,
        help="Run as HTTP server on PORT (default 8000). "
             "Clients: claude mcp add --transport http ti-sdk-docs http://host:PORT/mcp",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.http:
        port = args.http
        mcp.settings.port = port
        sys.stderr.write(f"TI SDK Docs MCP — HTTP mode, port {port}\n")
        sys.stderr.write(
            f"Register: claude mcp add --transport http ti-sdk-docs http://localhost:{port}/mcp\n"
        )
        asyncio.run(mcp.run_streamable_http_async())
    else:
        asyncio.run(mcp.run_stdio_async())
