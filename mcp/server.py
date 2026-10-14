#!/usr/bin/env python3
"""TI Processor SDK Documentation MCP Server.

Six tools:
  ti_processor_sdk_docs_list_variants  — list all supported (device, OS) combos
  ti_processor_sdk_docs_list_versions  — list available SDK versions for a device (from ti.com)
  ti_processor_sdk_docs_search         — keyword search scoped to a specific variant
  ti_processor_sdk_docs_read           — read a doc page as clean text
  ti_processor_sdk_docs_list_assets — list all images/diagrams on a page with semantic context
  ti_processor_sdk_docs_get_asset      — fetch an asset as base64-encoded bytes

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
TI_PROCESSOR_SDK_DEFAULT_DEVICE         default device (default: AM62X)
TI_PROCESSOR_SDK_DEFAULT_OS             default OS (default: linux)
TI_PROCESSOR_SDK_DEFAULT_RT             default rt flag (default: false)
TI_PROCESSOR_SDK_MCP_PORT               HTTP server port (default: 7471)
TI_PROCESSOR_SDK_DOC_CONFIGS            path to processor-sdk-doc configs/ dir
                                        (auto-detected from adjacent repo; falls back to GitHub API)
TI_PROCESSOR_SDK_CATALOG_TTL            catalog re-fetch interval in seconds (default: 86400)
TI_PROCESSOR_SDK_MAX_INDEXES            max variants in memory before LRU eviction (default: 50)
TI_PROCESSOR_SDK_MAX_CONCURRENT_FETCHES max simultaneous HTTP fetches (default: 10)
TI_PROCESSOR_SDK_MAX_PAGES_PER_VARIANT  max cached pages per variant before LRU eviction (default: 200)
TI_PROCESSOR_SDK_TOOL_ID_OVERRIDES      override ti.com download tool ID per device
                                        format: DEVICE=TOOL_ID,DEVICE2=TOOL_ID2
                                        example: AM62DX=PROCESSOR-SDK-LINUX-AM62DX
TI_PROCESSOR_SDK_DOCS_LOCAL_ROOT        local nightly build root for staging/internal mode
                                        structure: {root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/
                                        "latest" resolves to highest build ID
TI_PROCESSOR_SDK_DOCS_HTTP_ROOT         HTTP-served nightly build root (autoindex must be enabled)
                                        same structure as LOCAL_ROOT, served via HTTP
GITHUB_TOKEN                            GitHub PAT (60/hr -> 5000/hr rate limit)

Legacy single-variant (backward compat):
TI_PROCESSOR_SDK_DOCS_URL               base URL -- locks tools to this URL
TI_PROCESSOR_SDK_DOCS_ROOT              local path -- locks tools to this path
"""

import logging
import sys

# Logs go to stderr: in stdio mode stdout is the JSON-RPC channel, and any
# other byte on it (ours, httpx's or the mcp library's) corrupts the protocol.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("ti-sdk-mcp")

import argparse
import asyncio
import atexit
import base64
import html as _html
import json
import math
import os as _os
import re
import sqlite3
import sys
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin as _urljoin

import httpx
import snowballstemmer as _snowball
from bs4 import BeautifulSoup, NavigableString, Tag
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

_STEMMER = _snowball.stemmer("english")


class VariantNotFoundError(Exception):
    """Raised when a device/OS/version combo does not exist on the docs server."""


# ---------------------------------------------------------------------------
# Input validation and SSRF prevention
# ---------------------------------------------------------------------------

_VALID_SOURCES      = frozenset({"software-dl", "github"})
_DEVICE_RE          = re.compile(r'^[A-Z][A-Z0-9]{1,19}$')
_OS_RE              = re.compile(r'^[a-z][a-z0-9]{0,19}$')
_VERSION_RE         = re.compile(r'^(latest|\d{1,4}(_\d{1,4}){2,5})$')
_SHORT_VER_RE       = re.compile(r'^\d{1,2}\.\d{1,2}(\.\d{1,4})*$')
_PATH_SAFE_RE       = re.compile(r'^[a-zA-Z0-9_.][a-zA-Z0-9_/.\-]*$')
_MAX_QUERY_LEN      = 500
_MAX_PATH_LEN       = 300
_MAX_SEARCH_RESULTS = 20
_MAX_SEARCH_TERMS   = 50

_ALLOWED_URL_HOSTS = frozenset({"software-dl.ti.com", "texasinstruments.github.io"})


def _check_url_host(url: str, var_name: str = "URL") -> None:
    """Raise ValueError if url host is not on the TI allowlist (SSRF prevention)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{var_name} must use http or https, got {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not (host in _ALLOWED_URL_HOSTS or host.endswith(".ti.com") or host == "ti.com"):
        raise ValueError(
            f"{var_name} host {host!r} not allowed. "
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
    """Return an error string on invalid input, None on success."""
    if device is not None and not _DEVICE_RE.match(device):
        return (
            f"Invalid device {device!r}: must be 1-20 uppercase alphanumeric chars "
            "(e.g. 'AM62X'). Call ti_processor_sdk_docs_list_variants to see valid devices."
        )
    if os_type is not None and not _OS_RE.match(os_type):
        return (
            f"Invalid os {os_type!r}: must be lowercase alphanumeric, max 20 chars "
            "(e.g. 'linux', 'debian', 'buildroot'). "
            "Call ti_processor_sdk_docs_list_variants to see valid OS types."
        )
    if version is not None and not (_VERSION_RE.match(version) or _SHORT_VER_RE.match(version)):
        return (
            f"Invalid version {version!r}: must be 'latest', a full version string "
            "like '12_01_00_05_03', or a short alias like '12.01'."
        )
    if source is not None and source not in _VALID_SOURCES:
        return f"Invalid source {source!r}: must be 'software-dl' or 'github'."
    if path is not None:
        if len(path) > _MAX_PATH_LEN:
            return f"Path too long: max {_MAX_PATH_LEN} characters."
        # Disallow absolute paths
        if path.startswith('/'):
            return "Invalid path: absolute paths are not allowed."
        norm = path.replace("\\", "/")
        if not _PATH_SAFE_RE.match(norm):
            return f"Invalid path {path!r}: only alphanumeric, '/', '_', '-', '.' allowed."
    if query is not None and len(query) > _MAX_QUERY_LEN:
        return f"Query too long: max {_MAX_QUERY_LEN} characters."
    return None


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

_OS_PREFIX: dict[str, str] = {
    "linux":     "processor-sdk-linux",
    "debian":    "processor-sdk-linux",
    "buildroot": "processor-sdk-linux",
    "android":   "processor-sdk-android",
    "edgeai":    "processor-sdk-linux",
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


def _parse_os_patterns() -> None:
    """Populate OS URL maps from TI_PROCESSOR_SDK_OS_PATTERNS env var.

    Format: os:prefix:version_suffix:latest_dir  (comma-separated entries)
    Example: rtos:processor-sdk-rtos::latest,newos:processor-sdk-linux:_NewOS:latest_NewOS
    """
    raw = _os.environ.get("TI_PROCESSOR_SDK_OS_PATTERNS", "")
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 4:
            logger.info(
                f"Warning: TI_PROCESSOR_SDK_OS_PATTERNS entry {entry!r} invalid -- "
                "expected os:prefix:version_suffix:latest_dir, skipping.\n"
            )
            continue
        os_name, prefix, suffix, latest = parts
        _OS_PREFIX[os_name] = prefix
        _OS_SUFFIX[os_name] = suffix
        _OS_LATEST[os_name] = latest
        logger.info(
            f"OS pattern override: {os_name} -> "
            f"prefix={prefix!r} suffix={suffix!r} latest={latest!r}\n"
        )


_parse_os_patterns()


# ---------------------------------------------------------------------------
# Asset MIME types
# ---------------------------------------------------------------------------

import mimetypes


def _mime_from_asset_path(path: str) -> str:
    """Return a MIME type based on file extension using standard library."""
    if not path:
        return "application/octet-stream"
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "application/octet-stream"


def _asset_category(path_str: str, mime: str) -> str:
    """Return a content-type category hint for an asset."""
    if mime == "image/svg+xml":
        return "diagram"
    if mime in ("image/jpeg",):
        return "photo"
    if mime == "application/pdf":
        return "document"
    name = path_str.lower()
    diagram_kw = ("diagram", "arch", "flow", "block", "schematic", "chart",
                  "layout", "overview", "topology", "bsp")
    if any(kw in name for kw in diagram_kw):
        return "diagram"
    return "image"


def _software_dl_url(device: str, os_type: str, version: str, rt: bool) -> str:
    if os_type not in _OS_PREFIX:
        logger.info(
            f"Warning: unknown OS type '{os_type}' -- falling back to processor-sdk-linux. "
            f"Set TI_PROCESSOR_SDK_OS_PATTERNS to add '{os_type}' without editing server.py.\n"
        )
    base_prefix = _OS_PREFIX.get(os_type, "processor-sdk-linux")
    if rt and os_type == "linux":
        base_prefix = "processor-sdk-linux-rt"
    ver_dir = (
        _OS_LATEST.get(os_type, "latest") if version == "latest"
        else version + _OS_SUFFIX.get(os_type, "")
    )
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
# Local docs root -- nightly build disk access (staging mode)
#
# Set TI_PROCESSOR_SDK_DOCS_LOCAL_ROOT to the nightly build root, e.g.:
#   /datalocal/nightly_builds/nightly/smpusdk-docs-build/
#
# Structure: {root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/
# ---------------------------------------------------------------------------

_LOCAL_DOCS_ROOT: Path | None = (
    Path(_os.environ["TI_PROCESSOR_SDK_DOCS_LOCAL_ROOT"])
    if "TI_PROCESSOR_SDK_DOCS_LOCAL_ROOT" in _os.environ else None
)

_KNOWN_OS_TYPES = ["linux", "debian", "buildroot", "android", "edgeai"]


def _local_device_dir(device: str) -> str:
    return device.lower() + "-evm"


def _local_os_docs_dir(os_type: str) -> str:
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
    try:
        dirs = sorted(root.iterdir())
    except PermissionError:
        return result
    for device_path in dirs:
        if not device_path.is_dir() or not device_path.name.endswith("-evm"):
            continue
        device = device_path.name[:-4].upper()
        for os_type in _KNOWN_OS_TYPES:
            if _local_latest_docs(device_path, os_type) is not None:
                result.append({"device": device, "os": os_type})
    return result


# ---------------------------------------------------------------------------
# HTTP docs root -- nightly build HTTP access (autoindex mode)
#
# Set TI_PROCESSOR_SDK_DOCS_HTTP_ROOT to the HTTP-served nightly build root, e.g.:
#   http://swubn04.india.englab.ti.com/smpusdk-docs-build
#
# Structure (same as local root, served via HTTP with autoindex enabled):
#   {root}/{device}-evm/{build_id}_{date}/processor-sdk-{os}-docs/
# ---------------------------------------------------------------------------

_HTTP_DOCS_ROOT: str | None = (
    _os.environ.get("TI_PROCESSOR_SDK_DOCS_HTTP_ROOT", "").rstrip("/") or None
)

if _HTTP_DOCS_ROOT is not None:
    try:
        _check_url_host(_HTTP_DOCS_ROOT, "TI_PROCESSOR_SDK_DOCS_HTTP_ROOT")
    except ValueError as _exc:
        logger.info(f"ERROR: {_exc}\n")
        sys.exit(1)

_AUTOINDEX_HREF_RE = re.compile(r'href="([^"?/][^"]*?/)"')

# Resolved HTTP docs URLs -- avoids repeated HEAD scans per tool call.
# Keyed by (device, os_type, version). Invalidated on server restart.
_HTTP_DOCS_CACHE:      dict[tuple, str | None] = {}
_HTTP_DOCS_CACHE_LOCK  = asyncio.Lock()


async def _http_list_dir(url: str) -> list[str]:
    """Fetch autoindex page and return list of directory entry names."""
    try:
        async with _FETCH_SEMAPHORE:
            r = await _HTTP_CLIENT.get(url.rstrip("/") + "/", timeout=15)
        if r.status_code != 200:
            return []
        return _AUTOINDEX_HREF_RE.findall(r.text)
    except httpx.RequestError:
        return []


async def _http_latest_build(root: str, device_evm: str, os_type: str) -> str | None:
    """Return URL of latest (highest build ID) docs dir for device+os, or None."""
    entries = await _http_list_dir(f"{root}/{device_evm}")
    os_docs_name = _local_os_docs_dir(os_type)
    candidates: list[tuple[int, str]] = []
    for entry in entries:
        name = entry.rstrip("/")
        try:
            build_id = int(name.split("_")[0])
        except (ValueError, IndexError):
            continue
        candidates.append((build_id, name))
    if not candidates:
        return None
    for _, build_name in sorted(candidates, reverse=True):
        url = f"{root}/{device_evm}/{build_name}/{os_docs_name}"
        try:
            async with _FETCH_SEMAPHORE:
                r = await _HTTP_CLIENT.head(f"{url}/searchindex.js", timeout=10)
            if r.status_code == 200:
                return url
        except httpx.RequestError:
            continue
    return None


async def _resolve_http_docs(device: str, os_type: str, version: str) -> str | None:
    """Resolve HTTP docs base URL for (device, os_type, version). Cached for server lifetime."""
    if _HTTP_DOCS_ROOT is None:
        return None
    cache_key = (device, os_type, version)
    if cache_key in _HTTP_DOCS_CACHE:
        return _HTTP_DOCS_CACHE[cache_key]
    async with _HTTP_DOCS_CACHE_LOCK:
        if cache_key in _HTTP_DOCS_CACHE:
            return _HTTP_DOCS_CACHE[cache_key]
        device_evm = _local_device_dir(device)
        if version == "latest":
            url = await _http_latest_build(_HTTP_DOCS_ROOT, device_evm, os_type)
        else:
            url = None
            os_docs_name = _local_os_docs_dir(os_type)
            entries = await _http_list_dir(f"{_HTTP_DOCS_ROOT}/{device_evm}")
            for entry in sorted(entries):
                name = entry.rstrip("/")
                if version not in name:
                    continue
                candidate = f"{_HTTP_DOCS_ROOT}/{device_evm}/{name}/{os_docs_name}"
                try:
                    async with _FETCH_SEMAPHORE:
                        r = await _HTTP_CLIENT.head(f"{candidate}/searchindex.js", timeout=10)
                    if r.status_code == 200:
                        url = candidate
                        break
                except httpx.RequestError:
                    pass
        _HTTP_DOCS_CACHE[cache_key] = url
        return url


async def _catalog_from_http_root(root: str) -> list[dict[str, str]]:
    """Discover (device, os) combos by parsing autoindex at root URL."""
    device_entries = await _http_list_dir(root)
    device_entries = [e.rstrip("/") for e in device_entries if e.rstrip("/").endswith("-evm")]

    async def _probe(device_evm: str, os_type: str) -> dict | None:
        device = device_evm[:-4].upper()
        url = await _http_latest_build(root, device_evm, os_type)
        return {"device": device, "os": os_type} if url else None

    found = await asyncio.gather(*[
        _probe(d, o) for d in device_entries for o in _KNOWN_OS_TYPES
    ])
    return [f for f in found if f is not None]


# ---------------------------------------------------------------------------
# Legacy single-variant mode
# ---------------------------------------------------------------------------

_LEGACY_URL: str | None = (
    _os.environ.get("TI_PROCESSOR_SDK_DOCS_URL", "").rstrip("/") or None
)
_LEGACY_ROOT: Path | None = (
    Path(_os.environ["TI_PROCESSOR_SDK_DOCS_ROOT"])
    if "TI_PROCESSOR_SDK_DOCS_ROOT" in _os.environ else None
)

if _LEGACY_URL is not None:
    try:
        _check_url_host(_LEGACY_URL, "TI_PROCESSOR_SDK_DOCS_URL")
    except ValueError as _exc:
        logger.info(f"ERROR: {_exc}\n")
        sys.exit(1)

_LEGACY_KEY = ("__legacy__", "__legacy__", "__legacy__", False, "__legacy__")


def _is_legacy_mode() -> bool:
    return _LEGACY_URL is not None or _LEGACY_ROOT is not None


# ---------------------------------------------------------------------------
# Catalog -- dynamically loaded from processor-sdk-doc configs/
#
# Source priority: TI_PROCESSOR_SDK_DOC_CONFIGS env var -> adjacent repo -> GitHub tree API
# ---------------------------------------------------------------------------

_CATALOG: list[dict[str, str]] | None = None
_CATALOG_LOCK      = asyncio.Lock()
_CATALOG_LOADED_AT: float = 0.0
_CATALOG_TTL: int  = int(_os.environ.get("TI_PROCESSOR_SDK_CATALOG_TTL", "86400"))
_GITHUB_TOKEN: str = _os.environ.get("GITHUB_TOKEN", "")


def _find_local_configs() -> Path | None:
    if cfg := _os.environ.get("TI_PROCESSOR_SDK_DOC_CONFIGS"):
        return Path(cfg)
    adj = Path(__file__).parent.parent.parent / "processor-sdk-doc" / "configs"
    return adj if adj.is_dir() else None


_LOCAL_CONFIGS: Path | None = _find_local_configs()

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
    async with _FETCH_SEMAPHORE:
        r = await _HTTP_CLIENT.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    if data.get("truncated"):
        logger.info(
            "Warning: GitHub tree response truncated -- catalog may be incomplete.\n"
            "  Set TI_PROCESSOR_SDK_DOC_CONFIGS=/path/to/processor-sdk-doc/configs for complete catalog.\n"
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
        rest = filename[len(device) + 1:]
        for frag in _REQUIRED_FRAGMENTS:
            if rest.endswith(f"_{frag}"):
                os_name = rest[: -(len(frag) + 1)]
                found.setdefault((device, os_name), set()).add(frag)
                break

    return [
        {"device": device, "os": os_name}
        for (device, os_name), frags in sorted(found.items())
        if frags == _REQUIRED_FRAGMENTS
    ]


async def _ensure_catalog() -> list[dict[str, str]]:
    global _CATALOG, _CATALOG_LOADED_AT
    now = time.monotonic()
    if _CATALOG is not None and (now - _CATALOG_LOADED_AT) < _CATALOG_TTL:
        return _CATALOG
    async with _CATALOG_LOCK:
        now = time.monotonic()
        if _CATALOG is not None and (now - _CATALOG_LOADED_AT) < _CATALOG_TTL:
            return _CATALOG
        if _LOCAL_DOCS_ROOT is not None:
            _CATALOG = _catalog_from_local_root(_LOCAL_DOCS_ROOT)
            logger.info(f"Catalog: {len(_CATALOG)} variants (local root {_LOCAL_DOCS_ROOT})\n")
        elif _HTTP_DOCS_ROOT is not None:
            _CATALOG = await _catalog_from_http_root(_HTTP_DOCS_ROOT)
            logger.info(f"Catalog: {len(_CATALOG)} variants (HTTP root {_HTTP_DOCS_ROOT})\n")
        elif _LOCAL_CONFIGS is not None:
            _CATALOG = _catalog_from_local(_LOCAL_CONFIGS)
            logger.info(f"Catalog: {len(_CATALOG)} variants (local configs {_LOCAL_CONFIGS})\n")
        else:
            _CATALOG = await _catalog_from_github()
            logger.info(f"Catalog: {len(_CATALOG)} variants (GitHub)\n")
        _CATALOG_LOADED_AT = time.monotonic()
        return _CATALOG


# ---------------------------------------------------------------------------
# Search: TI-specific synonym expansion
#
# Maps a query word to additional terms to score alongside it.
# Covers common driver/subsystem name mismatches between what customers say
# and what the Sphinx index contains (e.g. "remoteproc" vs "rproc").
# ---------------------------------------------------------------------------

_TI_SYNONYMS: dict[str, list[str]] = {
    "gpio":       ["pinctrl", "pinmux", "iopad", "gpiod"],
    "remoteproc": ["rproc", "m4f", "r5f", "rpmsg", "firmware"],
    "rproc":      ["remoteproc", "m4f", "r5f", "rpmsg"],
    "emmc":       ["mmc", "sdmmc"],
    "ethernet":   ["cpsw", "icssg", "netdev", "phy"],
    "display":    ["dss", "drm", "tidss", "hdmi", "dpi"],
    "usb":        ["dwc3", "musb", "cdns3", "otg"],
    "pcie":       ["pci", "cadence"],
    "can":        ["mcan", "hecc"],
    "spi":        ["mcspi", "qspi", "ospi", "spinor"],
    "i2c":        ["omap", "davinci"],
    "uart":       ["serial", "tty", "console"],
    "dma":        ["udma", "pktdma", "bcdma", "edma"],
    "crypto":     ["sa2ul", "trng", "aes", "sha"],
    "ipc":        ["rpmsg", "virtio", "mailbox"],
    "power":      ["cpufreq", "cpuidle", "suspend"],
    "watchdog":   ["wdt", "rti"],
    "timer":      ["dmtimer"],
    "audio":      ["mcasp", "alsa", "asoc"],
    "camera":     ["csi", "csi2rx", "v4l2"],
    "boot":       ["uboot", "spl", "tiboot3", "tispl"],
    "yocto":      ["bitbake", "meta", "recipe", "layer"],
    "kernel":     ["linux", "kconfig", "defconfig"],
    "devicetree": ["dts", "dtsi", "dtb", "overlay"],
    "dt":         ["dts", "dtsi", "dtb", "devicetree", "overlay"],
}


def _expand_terms(words: list[str]) -> list[str]:
    """Expand query words with TI-specific synonyms. Preserves order, deduplicates."""
    expanded = list(words)
    seen = set(words)
    for w in words:
        for syn in _TI_SYNONYMS.get(w, []):
            if syn not in seen:
                expanded.append(syn)
                seen.add(syn)
    return expanded[:_MAX_SEARCH_TERMS]


# ---------------------------------------------------------------------------
# Version discovery — auto-probe ti.com for available SDK versions per device
#
# No hardcoded version lists. Each device is probed via 4 URL patterns in
# parallel (HEAD requests). The matching ti.com download page is scraped for
# the items="[...]" attribute (server-side rendered, no JS needed).
#
# Cache: per-device dict with _CATALOG_TTL invalidation. Graceful failure
# (returns []) for devices without a ti.com download page (e.g. DRA821A).
# ---------------------------------------------------------------------------

_TI_TOOL_ID_CACHE:      dict[str, str | None]         = {}
_TI_VERSIONS_CACHE:     dict[str, tuple[float, list]] = {}
_TI_VERSION_LOCKS:      dict[str, asyncio.Lock]       = {}
_TI_VERSION_GLOBAL_LOCK = asyncio.Lock()
_TI_ITEMS_RE = re.compile(r'items="(\[.*?\])"', re.DOTALL)


def _parse_tool_id_overrides() -> dict[str, str]:
    """Parse TI_PROCESSOR_SDK_TOOL_ID_OVERRIDES into a device -> tool_id dict."""
    overrides: dict[str, str] = {}
    raw = _os.environ.get("TI_PROCESSOR_SDK_TOOL_ID_OVERRIDES", "")
    for entry in raw.split(","):
        entry = entry.strip()
        if "=" in entry:
            dev, tid = entry.split("=", 1)
            overrides[dev.strip().upper()] = tid.strip()
    return overrides


_TI_TOOL_ID_OVERRIDES: dict[str, str] = _parse_tool_id_overrides()


async def _probe_ti_tool_id(device: str) -> str | None:
    """Probe ti.com to find the download tool ID for device (cached after first hit)."""
    if device in _TI_TOOL_ID_OVERRIDES:
        return _TI_TOOL_ID_OVERRIDES[device]
    if device in _TI_TOOL_ID_CACHE:
        return _TI_TOOL_ID_CACHE[device]

    patterns = [
        f"PROCESSOR-SDK-LINUX-{device}",
        f"PROCESSOR-SDK-LINUX-{device[:-1]}",
        f"{device[:-1]}-LINUX-SDK",
        f"{device}-PROCESSOR-LINUX-SDK",
    ]
    probe_results = await asyncio.gather(
        *[_HTTP_CLIENT.head(f"https://www.ti.com/tool/download/{p}", timeout=4, follow_redirects=False) for p in patterns],
        return_exceptions=True,
    )

    tool_id = next(
        (p for p, r in zip(patterns, probe_results)
         if not isinstance(r, Exception) and r.status_code == 200),
        None,
    )
    _TI_TOOL_ID_CACHE[device] = tool_id
    return tool_id


async def _fetch_ti_versions(device: str) -> list[dict]:
    """Return list of {version, short, label} dicts from ti.com download page (cached)."""
    now = time.monotonic()
    if device in _TI_VERSIONS_CACHE:
        loaded_at, versions = _TI_VERSIONS_CACHE[device]
        if (now - loaded_at) < _CATALOG_TTL:
            return versions

    async with _TI_VERSION_GLOBAL_LOCK:
        if device not in _TI_VERSION_LOCKS:
            _TI_VERSION_LOCKS[device] = asyncio.Lock()

    async with _TI_VERSION_LOCKS[device]:
        if device in _TI_VERSIONS_CACHE:
            loaded_at, versions = _TI_VERSIONS_CACHE[device]
            if (now - loaded_at) < _CATALOG_TTL:
                return versions

        tool_id = await _probe_ti_tool_id(device)
        if not tool_id:
            _TI_VERSIONS_CACHE[device] = (time.monotonic(), [])
            return []

        try:
            async with _FETCH_SEMAPHORE:
                r = await _HTTP_CLIENT.get(
                    f"https://www.ti.com/tool/download/{tool_id}",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
            m = _TI_ITEMS_RE.search(r.text)
            if not m:
                versions = []
            else:
                raw = json.loads(_html.unescape(m.group(1)))
                versions = []
                for group in raw:
                    for v in group.get("children", []):
                        ver_dot = v["value"].split("/")[-1]
                        ver_us  = ver_dot.replace(".", "_")
                        short   = ".".join(ver_dot.split(".")[:2])
                        versions.append({
                            "version": ver_us,
                            "short":   short,
                            "label":   v.get("label", ver_dot),
                        })
        except Exception as exc:
            logger.info(f"Warning: version fetch failed for {device}: {exc}\n")
            versions = []

        _TI_VERSIONS_CACHE[device] = (time.monotonic(), versions)
        return versions


async def _resolve_version(device: str, version: str) -> tuple[str, str | None]:
    """Resolve a short version alias ('12.01') to full form ('12_01_00_05_03').

    Returns (resolved_version, error_message). error_message is None on success.
    Pass-through for 'latest' and already-full version strings.
    """
    if version == "latest" or _VERSION_RE.match(version):
        return version, None
    versions = await _fetch_ti_versions(device)
    if not versions:
        return version, (
            f"Cannot resolve version {version!r} for {device}: no version list from ti.com. "
            "Use an explicit version string like '12_01_00_05_03' or 'latest'."
        )
    ver_dot = version.replace("_", ".")
    for v in versions:
        if v["short"] == ver_dot or v["version"] == version.replace(".", "_"):
            return v["version"], None
    available = sorted({v["short"] for v in versions})
    return version, (
        f"Version {version!r} not found for {device}. "
        f"Available short aliases: {', '.join(available)}. "
        "Or use full version string like '12_01_00_05_03'."
    )


# ---------------------------------------------------------------------------
# Per-variant lazy state
# ---------------------------------------------------------------------------

_MAX_INDEXES:           int = int(_os.environ.get("TI_PROCESSOR_SDK_MAX_INDEXES", "50"))
_MAX_CONCURRENT_FETCHES: int = int(_os.environ.get("TI_PROCESSOR_SDK_MAX_CONCURRENT_FETCHES", "10"))
_MAX_PAGES_PER_VARIANT: int = int(_os.environ.get("TI_PROCESSOR_SDK_MAX_PAGES_PER_VARIANT", "200"))

_FETCH_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)

_INDEXES:      dict[tuple, dict[str, Any]] = {}
_INDEX_LOCKS:  dict[tuple, asyncio.Lock]   = {}
_PAGE_CACHES:  dict[tuple, dict[str, str]] = {}
_INDEX_ERRORS: dict[tuple, str]            = {}
_GLOBAL_LOCK   = asyncio.Lock()

# Asset cache (LRU) for get_asset tool
_ASSET_CACHE: OrderedDict[tuple, str] = OrderedDict()
_ASSET_CACHE_MAX: int = int(_os.environ.get("TI_PROCESSOR_SDK_MAX_ASSETS_PER_VARIANT", "200"))
_MAX_ASSET_BYTES: int = int(_os.environ.get("TI_PROCESSOR_SDK_MAX_ASSET_BYTES", str(20 * 1024 * 1024)))  # 20 MB download limit

_HTTP_CLIENT = httpx.AsyncClient(
    follow_redirects=True,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)

_FTS_DBS:           dict[tuple, sqlite3.Connection | None] = {}
_FTS_DB_FILES:      dict[tuple, str]                       = {}
_FTS_DB_LOCKS:      dict[tuple, asyncio.Lock]              = {}
_FTS_DB_GLOBAL_LOCK = asyncio.Lock()
_FTS_SCHEMA_CACHE:  dict[int, bool]                        = {}  # id(conn) -> has page_type col


def _cleanup_fts_files() -> None:
    for path in list(_FTS_DB_FILES.values()):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


atexit.register(_cleanup_fts_files)


def _cache_key(device: str, os_type: str, version: str, rt: bool, source: str) -> tuple:
    if source == "github":
        return (device, os_type, "master", False, "github")
    return (device, os_type, version, rt, "software-dl")


async def _docs_location(
    device: str, os_type: str, version: str, rt: bool, source: str
) -> tuple[Path | None, str]:
    """Return (local_root, base_url) for the given variant.

    local_root is non-None when docs are on local disk; base_url is the HTTP base otherwise.
    Handles legacy mode, local nightly root, HTTP nightly root, and standard URLs.
    """
    if _is_legacy_mode():
        return (_LEGACY_ROOT, _LEGACY_URL or "")
    if source == "software-dl":
        local = _resolve_local_docs(device, os_type, version)
        if local is not None:
            return (local, "")
        url = await _resolve_http_docs(device, os_type, version)
        return (None, url or _make_url(device, os_type, version, rt, source))
    return (None, _make_url(device, os_type, version, rt, source))


# ---------------------------------------------------------------------------
# Index parsing and lazy loading
# ---------------------------------------------------------------------------

async def _fetch_index_raw(base_url: str) -> str:
    async with _FETCH_SEMAPHORE:
        r = await _HTTP_CLIENT.get(f"{base_url}/searchindex.js", timeout=30)
    r.raise_for_status()
    return r.text


def _parse_index(raw: str) -> dict[str, Any]:
    raw = re.sub(r"^Search\.setIndex\(", "", raw)
    raw = raw.rstrip().rstrip(")")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Older Sphinx versions emit unquoted JS keys — quote them before parsing.
        raw = re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', raw)
        return json.loads(raw)


async def _ensure_index(
    device: str, os_type: str, version: str, rt: bool, source: str
) -> dict[str, Any]:
    legacy = _is_legacy_mode()
    key = _LEGACY_KEY if legacy else _cache_key(device, os_type, version, rt, source)

    if key in _INDEX_ERRORS:
        raise VariantNotFoundError(_INDEX_ERRORS[key])
    if key in _INDEXES:
        return _INDEXES[key]

    async with _GLOBAL_LOCK:
        if key not in _INDEX_LOCKS:
            _INDEX_LOCKS[key] = asyncio.Lock()

    async with _INDEX_LOCKS[key]:
        if key in _INDEX_ERRORS:
            raise VariantNotFoundError(_INDEX_ERRORS[key])
        if key in _INDEXES:
            return _INDEXES[key]

        try:
            local, url = await _docs_location(device, os_type, version, rt, source)
            if local is not None:
                raw = (local / "searchindex.js").read_text(encoding="utf-8")
            else:
                raw = await _fetch_index_raw(url)
            idx = _parse_index(raw)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                msg = (
                    f"Docs not found for device={device!r} os={os_type!r} version={version!r} "
                    f"source={source!r} (HTTP 404). "
                    "Version may not exist or device was added after this release. "
                    "Call ti_processor_sdk_docs_list_variants to see available combos, "
                    "or try version='latest'."
                )
                _INDEX_ERRORS[key] = msg
                raise VariantNotFoundError(msg) from exc
            raise

        except (json.JSONDecodeError, ValueError) as exc:
            msg = (
                f"searchindex.js for device={device!r} os={os_type!r} version={version!r} "
                f"is malformed: {exc}. "
                "This version may predate Sphinx search or have a corrupted build."
            )
            _INDEX_ERRORS[key] = msg
            raise VariantNotFoundError(msg) from exc

        if len(_INDEXES) >= _MAX_INDEXES:
            oldest_key = next(iter(_INDEXES))
            del _INDEXES[oldest_key]
            _PAGE_CACHES.pop(oldest_key, None)
            _INDEX_LOCKS.pop(oldest_key, None)

        _INDEXES[key] = idx
        _PAGE_CACHES.setdefault(key, {})
        return idx


# Pre-load in legacy local mode to fail fast on bad path
if _LEGACY_ROOT is not None:
    _si_path = _LEGACY_ROOT / "searchindex.js"
    if not _si_path.exists():
        logger.info(f"ERROR: searchindex.js not found at {_si_path}\n")
        sys.exit(1)
    _INDEXES[_LEGACY_KEY] = _parse_index(_si_path.read_text(encoding="utf-8"))
    _PAGE_CACHES[_LEGACY_KEY] = {}


# ---------------------------------------------------------------------------
# FTS5 SQLite index -- BM25 search, falls back to Sphinx IDF when absent
#
# searchindex.db is built by scripts/build_searchindex.py and published
# alongside searchindex.js. When absent (old SDK versions), search falls
# back to the Sphinx IDF scorer below.
# ---------------------------------------------------------------------------

async def _download_fts_db(base_url: str) -> bytes | None:
    """Fetch searchindex.db from base_url. Returns None on 404 or network error."""
    try:
        async with _FETCH_SEMAPHORE:
            r = await _HTTP_CLIENT.get(f"{base_url}/searchindex.db", timeout=60)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
    except (httpx.HTTPStatusError, httpx.RequestError):
        return None


async def _ensure_fts_db(
    key: tuple, device: str, os_type: str, version: str, rt: bool, source: str
) -> sqlite3.Connection | None:
    """Return cached sqlite3 connection for the FTS index, or None if unavailable.

    None is cached after a 404/missing file to avoid re-probing on every search call.
    """
    if key in _FTS_DBS:
        return _FTS_DBS[key]

    async with _FTS_DB_GLOBAL_LOCK:
        if key not in _FTS_DB_LOCKS:
            _FTS_DB_LOCKS[key] = asyncio.Lock()

    async with _FTS_DB_LOCKS[key]:
        if key in _FTS_DBS:
            return _FTS_DBS[key]

        local, url = await _docs_location(device, os_type, version, rt, source)
        if local is not None:
            db_file = local / "searchindex.db"
            data = db_file.read_bytes() if db_file.exists() else None
        elif url:
            data = await _download_fts_db(url)
        else:
            data = None

        if data is None:
            _FTS_DBS[key] = None
            return None

        fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="ti-sdk-fts-")
        _os.close(fd)
        Path(tmp_path).write_bytes(data)
        conn = sqlite3.connect(tmp_path, check_same_thread=False)
        _FTS_DB_FILES[key] = tmp_path
        _FTS_SCHEMA_CACHE[id(conn)] = conn.execute(
            "SELECT 1 FROM pragma_table_info('docs') WHERE name='page_type'"
        ).fetchone() is not None

        # LRU: evict oldest real connection when at capacity
        real_count = sum(1 for v in _FTS_DBS.values() if v is not None)
        if real_count >= _MAX_INDEXES:
            oldest = next(k for k, v in _FTS_DBS.items() if v is not None)
            old_conn = _FTS_DBS.pop(oldest)
            old_file = _FTS_DB_FILES.pop(oldest, None)
            _FTS_SCHEMA_CACHE.pop(id(old_conn), None)
            old_conn.close()
            if old_file:
                try:
                    Path(old_file).unlink(missing_ok=True)
                except OSError:
                    pass
            _FTS_DB_LOCKS.pop(oldest, None)

        _FTS_DBS[key] = conn
        return conn


def _fts_search(
    conn: sqlite3.Connection,
    base_words: list[str],
    expanded_words: list[str],
    n: int,
) -> list[dict]:
    """BM25 FTS5 search: OR semantics, explicit column weights, matched_terms metadata."""
    fts_query = ' OR '.join(f'"{w}"' for w in expanded_words)
    page_type_col = "d.page_type" if _FTS_SCHEMA_CACHE.get(id(conn)) else "NULL"

    try:
        rows = conn.execute(f"""
            SELECT d.docname, d.title, {page_type_col}, fts.rowid,
                   bm25(fts, 10.0, 5.0, 1.0) AS score
            FROM fts
            JOIN docs d ON fts.rowid = d.id
            WHERE fts MATCH ?
            ORDER BY score
            LIMIT ?
        """, (fts_query, n)).fetchall()
    except sqlite3.OperationalError:
        return []

    if not rows:
        return []

    term_rowids: dict[str, set[int]] = {}
    for word in base_words:
        try:
            hits = conn.execute(
                "SELECT rowid FROM fts WHERE fts MATCH ?", (f'"{word}"',)
            ).fetchall()
            term_rowids[word] = {r[0] for r in hits}
        except sqlite3.OperationalError:
            term_rowids[word] = set()

    results = []
    for docname, title, page_type, rowid, bm25_score in rows:
        matched = sorted(w for w, rids in term_rowids.items() if rowid in rids)
        coverage = round(len(matched) / len(base_words), 2) if base_words else 0.0
        clean_title = re.sub(r'<[^>]+>', '', title or '').strip() or docname.split('/')[-1]
        results.append({
            "title": clean_title,
            "path": docname + ".html",
            "page_type": page_type or "other",
            "score": round(-bm25_score, 3),
            "matched_terms": matched,
            "coverage": coverage,
        })
    return results


# ---------------------------------------------------------------------------
# Page fetching (clean text)
# ---------------------------------------------------------------------------

async def _fetch_http(base_url: str, path: str) -> str:
    """Fetch a doc page from base_url/path and return clean text."""
    try:
        async with _FETCH_SEMAPHORE:
            r = await _HTTP_CLIENT.get(f"{base_url}/{path}", timeout=30)
        if r.status_code == 404:
            return (
                f"Page not found: {path}\n"
                "Use ti_processor_sdk_docs_search to find valid paths."
            )
        r.raise_for_status()
        return _html_to_text(r.text)
    except httpx.HTTPStatusError as exc:
        return f"HTTP {exc.response.status_code} error fetching {path}: {exc.response.reason_phrase}"
    except httpx.RequestError as exc:
        return f"Network error fetching {path}: {exc}"


def _read_local_file(path: str, root: Path) -> str:
    full = (root / path).resolve()
    if not str(full).startswith(str(root.resolve())):
        return "Error: path outside docs root"
    if not full.exists():
        return (
            f"Page not found: {path}\n"
            "Use ti_processor_sdk_docs_search to find valid paths."
        )
    return _html_to_text(full.read_text(encoding="utf-8", errors="replace"))


# ---------------------------------------------------------------------------
# Raw fetching (for asset listing)
# ---------------------------------------------------------------------------

async def _fetch_http_raw(base_url: str, path: str) -> str:
    """Fetch a doc page from base_url/path and return raw HTML (not cleaned)."""
    try:
        async with _FETCH_SEMAPHORE:
            r = await _HTTP_CLIENT.get(f"{base_url}/{path}", timeout=30)
        if r.status_code == 404:
            return (
                f"Page not found: {path}\n"
                "Use ti_processor_sdk_docs_search to find valid paths."
            )
        r.raise_for_status()
        return r.text   # raw, not cleaned
    except httpx.HTTPStatusError as exc:
        return f"HTTP {exc.response.status_code} error fetching {path}: {exc.response.reason_phrase}"
    except httpx.RequestError as exc:
        return f"Network error fetching {path}: {exc}"


def _read_local_file_raw(path: str, root: Path) -> str:
    """Read a local file and return raw string (not cleaned)."""
    full = (root / path).resolve()
    if not str(full).startswith(str(root.resolve())):
        return "Error: path outside docs root"
    if not full.exists():
        return (
            f"Page not found: {path}\n"
            "Use ti_processor_sdk_docs_search to find valid paths."
        )
    return full.read_text(encoding="utf-8", errors="replace")


async def _fetch_page(
    path: str, device: str, os_type: str, version: str, rt: bool, source: str
) -> str:
    key = _LEGACY_KEY if _is_legacy_mode() else _cache_key(device, os_type, version, rt, source)
    cache = _PAGE_CACHES.setdefault(key, {})
    if path in cache:
        return cache[path]

    local, url = await _docs_location(device, os_type, version, rt, source)
    text = _read_local_file(path, local) if local is not None else await _fetch_http(url, path)

    if len(cache) >= _MAX_PAGES_PER_VARIANT:
        del cache[next(iter(cache))]
    cache[path] = text
    return text


# ---------------------------------------------------------------------------
# HTML -> clean text
# ---------------------------------------------------------------------------

def _html_to_text(html: str) -> str:
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
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _node_to_lines(node: Any, lines: list[str]) -> None:
    if isinstance(node, NavigableString):
        if str(node).strip():
            lines.append(str(node).rstrip())
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

_DEFAULT_DEVICE = _os.environ.get("TI_PROCESSOR_SDK_DEFAULT_DEVICE", "AM62X")
_DEFAULT_OS     = _os.environ.get("TI_PROCESSOR_SDK_DEFAULT_OS",     "linux")
_DEFAULT_RT     = _os.environ.get("TI_PROCESSOR_SDK_DEFAULT_RT",     "").lower() in ("1", "true", "yes")
_HTTP_PORT      = int(_os.environ.get("TI_PROCESSOR_SDK_MCP_PORT",   "7471"))

mcp = FastMCP(
    "ti-processor-sdk-docs",
    instructions=(
        "Search and read TI Processor SDK documentation across all devices and OS types. "
        "Supports AM62X, AM64X, AM62PX, J721E and more; "
        "linux, debian, and buildroot OS types; "
        "all historical versions from software-dl.ti.com plus latest master from GitHub Pages. "
        "Call ti_processor_sdk_docs_list_variants first to discover available combos. "
        "Use ti_processor_sdk_docs_search to find pages by topic, "
        "ti_processor_sdk_docs_read for full content."
    ),
    host="0.0.0.0",
    port=_HTTP_PORT,
)


_UPSTREAM_PROBE_URL = "https://software-dl.ti.com/"


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Plain HTTP health endpoint (HTTP mode only; not an MCP tool).

    GET /health             liveness: answered by the same Starlette app that serves
                            /mcp, makes no outbound calls. Use it for the Docker
                            HEALTHCHECK. (GET /mcp is not usable for this: the
                            streamable-HTTP transport answers a plain GET with 406,
                            and a POST initialize creates a session that is kept in
                            memory until the client deletes it.)
    GET /health?upstream=1  also checks that the docs host answers; 503 if it does not
                            (proxy or network problem). Not for HEALTHCHECK: an
                            upstream outage must not mark the container unhealthy.
    """
    body: dict[str, Any] = {"status": "ok", "service": "ti-processor-sdk-docs"}
    if request.query_params.get("upstream", "0") not in ("", "0", "false"):
        if _LEGACY_ROOT is not None or _LOCAL_DOCS_ROOT is not None:
            body["upstream"] = {"reachable": True, "source": "local filesystem"}
        else:
            target = _LEGACY_URL or _HTTP_DOCS_ROOT or _UPSTREAM_PROBE_URL
            try:
                r = await _HTTP_CLIENT.head(target, timeout=5)
                body["upstream"] = {"reachable": r.status_code < 500, "url": target,
                                    "http_status": r.status_code}
            except httpx.HTTPError as exc:
                body["upstream"] = {"reachable": False, "url": target,
                                    "error": f"{type(exc).__name__}: {exc}"}
            if not body["upstream"]["reachable"]:
                body["status"] = "degraded"
                return JSONResponse(body, status_code=503)
    return JSONResponse(body)


@mcp.tool()
async def ti_processor_sdk_docs_list_variants() -> str:
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


@mcp.tool()
async def ti_processor_sdk_docs_list_versions(
    device: str = _DEFAULT_DEVICE,
) -> str:
    """List all available SDK versions for a device from ti.com.

    Discovers versions by scraping the ti.com download page for the device.
    Cached for 24 hours (configurable via TI_PROCESSOR_SDK_CATALOG_TTL).
    Returns empty list for devices without a public ti.com download page
    (e.g. DRA821A, TDA4VM — these share another device's SDK).

    Args:
        device: Device family (e.g. "AM62X", "AM64X", "J721E").

    Returns:
        JSON object with tool_id (ti.com download page ID) and versions array.
        Each version: {version (full underscore form), short (e.g. "12.01"), label}.
        Versions listed newest-first. Use short alias in search/read version parameter.
    """
    err = _validate(device=device)
    if err:
        return err
    tool_id = await _probe_ti_tool_id(device)
    versions = await _fetch_ti_versions(device)
    return json.dumps({"tool_id": tool_id, "versions": versions}, indent=2)


def _doc_indices(v: Any) -> list[int]:
    return [v] if isinstance(v, int) else list(v)


@mcp.tool()
async def ti_processor_sdk_docs_search(
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
                Run ti_processor_sdk_docs_list_variants to see all supported combos.
        os: OS type: "linux" (default), "debian", or "buildroot".
        version: SDK version ("latest", full string like "12_01_00_05_03", or short
                 alias like "12.01"). Ignored when source="github".
        rt: True to query the processor-sdk-linux-rt prefix. Ignored when source="github".
        source: "software-dl" (default, versioned) or "github" (latest master only).
        max_results: Pages to return, default 8, max 20.

    Returns:
        JSON array sorted by relevance. Each entry: title, path, score.
        When FTS5 index available: also includes page_type, matched_terms, coverage.
        Pass path to ti_processor_sdk_docs_read to get full content.
    """
    err = _validate(device=device, os_type=os, version=version, source=source, query=query)
    if err:
        return err
    if source == "software-dl":
        version, ver_err = await _resolve_version(device, version)
        if ver_err:
            return ver_err
    max_results = min(max(1, max_results), _MAX_SEARCH_RESULTS)
    try:
        idx = await _ensure_index(device, os, version, rt, source)
    except VariantNotFoundError as exc:
        return str(exc)

    base_words = list(dict.fromkeys(re.findall(r"[a-z][a-z0-9]*", query.lower())))[:_MAX_SEARCH_TERMS]
    if not base_words:
        return json.dumps([])
    expanded_words = _expand_terms(base_words)

    # FTS5 BM25 (primary) -- falls back to Sphinx IDF if searchindex.db absent
    key = _LEGACY_KEY if _is_legacy_mode() else _cache_key(device, os, version, rt, source)
    fts_conn = await _ensure_fts_db(key, device, os, version, rt, source)
    if fts_conn is not None:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, _fts_search, fts_conn, base_words, expanded_words, max_results
        )
        return json.dumps(results, indent=2)

    # Sphinx IDF fallback -- used when searchindex.db is absent (old SDK versions)
    docnames:   list[str]      = idx["docnames"]
    titles:     list[str]      = idx["titles"]
    terms:      dict[str, Any] = idx["terms"]
    titleterms: dict[str, Any] = idx.get("titleterms", {})
    N = len(docnames)

    scores: dict[int, float] = {}
    for word in expanded_words:
        stemmed = _STEMMER.stemWord(word)

        hits = terms.get(word) if word in terms else terms.get(stemmed)
        if hits is not None:
            doc_list = _doc_indices(hits)
            idf = math.log((N + 1) / (len(doc_list) + 1)) + 1.0
            for doc_idx in doc_list:
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf

        title_hits = titleterms.get(word) if word in titleterms else titleterms.get(stemmed)
        if title_hits is not None:
            doc_list = _doc_indices(title_hits)
            idf = math.log((N + 1) / (len(doc_list) + 1)) + 1.0
            for doc_idx in doc_list:
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * 3.0

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max_results]
    return json.dumps([
        {"title": re.sub(r'<[^>]+>', '', titles[i]).strip(),
         "path": docnames[i] + ".html",
         "score": round(s, 3)}
        for i, s in ranked
    ], indent=2)


@mcp.tool()
async def ti_processor_sdk_docs_read(
    path: str,
    device: str = _DEFAULT_DEVICE,
    os: str = _DEFAULT_OS,
    version: str = "latest",
    rt: bool = _DEFAULT_RT,
    source: str = "software-dl",
) -> str:
    """Read a TI Processor SDK documentation page as clean text.

    Args:
        path: Relative HTML path from ti_processor_sdk_docs_search
              (e.g. "linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html").
              .html extension optional.
        device: Target device -- must match the device used in ti_processor_sdk_docs_search.
        os: OS type: "linux", "debian", or "buildroot".
        version: SDK version ("latest", full string like "12_01_00_05_03", or short
                 alias like "12.01"). Ignored when source="github".
        rt: True to use processor-sdk-linux-rt prefix. Ignored when source="github".
        source: "software-dl" (default, versioned) or "github" (latest master only).

    Returns:
        Clean text with headings as # markdown, code blocks as ```.
        Sidebar and navigation are stripped.
    """
    err = _validate(device=device, os_type=os, version=version, source=source, path=path)
    if err:
        return err
    if source == "software-dl":
        version, ver_err = await _resolve_version(device, version)
        if ver_err:
            return ver_err
    if not path.endswith(".html"):
        path = path + ".html"
    try:
        await _ensure_index(device, os, version, rt, source)
    except VariantNotFoundError as exc:
        return str(exc)
    return await _fetch_page(path, device, os, version, rt, source)


# ---------------------------------------------------------------------------
# Asset tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def ti_processor_sdk_docs_get_asset(
    asset_path: str,
    device: str = _DEFAULT_DEVICE,
    os: str = _DEFAULT_OS,
    version: str = "latest",
    source: str = "software-dl",
) -> str:
    """Fetch a raw asset (image, diagram, SVG, PDF, etc.) from the documentation source.

    Args:
        asset_path: Path to the asset relative to the documentation root.
                    Must not contain '..' or absolute paths – validated like `path` in read/search.
        device: Target device family (e.g. "AM62X").
        os: OS type: "linux", "debian", or "buildroot".
        version: SDK version ("latest", full string like "12_01_00_05_03", or short alias like "12.01").
        source: "software-dl" (default, versioned) or "github" (latest master only).

    Returns:
        JSON string with:
          - data: base64-encoded asset bytes
          - mimeType: MIME type (e.g. "image/png", "image/svg+xml", "application/pdf")
          - size: size in bytes of the original asset

    On error returns an error string (same convention as other tools).
    """
    # Validate inputs (reuse _validate for device, os, version, source, and asset_path as path)
    err = _validate(device=device, os_type=os, version=version, source=source, path=asset_path)
    if err:
        return err

    # Resolve version (only for software-dl)
    if source == "software-dl":
        version, ver_err = await _resolve_version(device, version)
        if ver_err:
            return ver_err

    # Get location (local root or base URL)
    local, url = await _docs_location(device, os, version, rt=False, source=source)

    # Check asset cache
    cache_key = (device, os, version, source, asset_path)
    if cache_key in _ASSET_CACHE:
        # Return cached result to avoid re-encoding
        return _ASSET_CACHE[cache_key]

    # Fetch raw bytes
    try:
        if local is not None:
            asset_file = local / asset_path
            if not asset_file.is_file():
                return f"Asset not found: {asset_path}"
            file_size = asset_file.stat().st_size
            if file_size > _MAX_ASSET_BYTES:
                return f"Asset too large: {file_size} bytes (limit {_MAX_ASSET_BYTES})"
            data = asset_file.read_bytes()
        elif url is not None:
            asset_url = url.rstrip('/') + '/' + asset_path.lstrip('/')
            async with _FETCH_SEMAPHORE:
                async with _HTTP_CLIENT.stream("GET", asset_url, timeout=30) as r:
                    if r.status_code == 404:
                        return f"Asset not found: {asset_path}"
                    r.raise_for_status()
                    cl = r.headers.get("content-length")
                    if cl and int(cl) > _MAX_ASSET_BYTES:
                        return f"Asset too large: {cl} bytes (limit {_MAX_ASSET_BYTES})"
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in r.aiter_bytes(65536):
                        size += len(chunk)
                        if size > _MAX_ASSET_BYTES:
                            return f"Asset too large: exceeds {_MAX_ASSET_BYTES} bytes"
                        chunks.append(chunk)
                    data = b"".join(chunks)
        else:
            return "Variant not found"
    except Exception as e:
        return f"Failed to fetch asset: {str(e)}"

    # Encode, build result, cache with LRU eviction
    mime = _mime_from_asset_path(asset_path)
    size = len(data)

    b64 = base64.b64encode(data).decode("ascii")
    result_json = json.dumps({"data": b64, "mimeType": mime, "size": size})

    if len(_ASSET_CACHE) >= _ASSET_CACHE_MAX:
        _ASSET_CACHE.popitem(last=False)
    _ASSET_CACHE[cache_key] = result_json

    return result_json


@mcp.tool()
async def ti_processor_sdk_docs_list_assets(
    path: str,
    device: str = _DEFAULT_DEVICE,
    os: str = _DEFAULT_OS,
    version: str = "latest",
    source: str = "software-dl",
    content_only: bool = True,
) -> str:
    """List all assets (images, diagrams, etc.) referenced in a documentation page.

    Args:
        path: Relative HTML path from ti_processor_sdk_docs_search
              (e.g. "linux/Foundational_Components/Tools/Flash_via_Fastboot.html").
              .html extension optional.
        device: Target device family (e.g. "AM62X").
        os: OS type: "linux", "debian", or "buildroot".
        version: SDK version ("latest", full string like "12_01_00_05_03", or short alias like "12.01").
        source: "software-dl" (default, versioned) or "github" (latest master only).
        content_only: When True (default), skip _static/ assets (fonts, CSS, JS, UI icons)
                      and return only documentation content assets from _images/.

    Returns:
        JSON array of objects, each with:
          - path: asset path relative to documentation root
          - mimeType: MIME type (e.g. "image/png", "image/svg+xml")
          - category: "diagram", "photo", "image", or "document"
          - section_heading: nearest preceding heading (h1-h4) above the asset
          - caption: figcaption text if the asset is inside a <figure>
          - context_text: up to 150 chars of the nearest preceding paragraph
          - dot_source: for Graphviz SVGs, the raw DOT language source (useful for
                        text-only agents that cannot process binary image data)
        Also returns a metadata object with page_title, asset_count, and status.
    On error returns an error string (same convention as other tools).
    """
    # Validate inputs
    err = _validate(device=device, os_type=os, version=version, source=source, path=path)
    if err:
        return err

    # Resolve version (only for software-dl)
    if source == "software-dl":
        version, ver_err = await _resolve_version(device, version)
        if ver_err:
            return ver_err

    # Get location (local root or base URL)
    local, url = await _docs_location(device, os, version, rt=False, source=source)

    # Fetch raw HTML.
    # _fetch_http_raw manages _FETCH_SEMAPHORE internally; local reads are sync.
    # Do NOT wrap either call in an outer semaphore – that would double-acquire.
    try:
        if local is not None:
            html = _read_local_file_raw(path, local)
        elif url is not None:
            html = await _fetch_http_raw(url, path)
        else:
            return "Variant not found"
    except Exception as e:
        return f"Failed to fetch page: {str(e)}"

    # Parse HTML to find assets
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        return f"Failed to parse HTML: {str(e)}"

    # Page title from <title> or first <h1>
    page_title = None
    title_tag = soup.find("title")
    if title_tag:
        page_title = title_tag.get_text(strip=True)
    if not page_title:
        h1 = soup.find("h1")
        if h1:
            page_title = h1.get_text(strip=True)

    # Find tags that can reference external assets
    asset_tags = soup.find_all(['img', 'object', 'embed', 'source', 'audio', 'video'])
    total_tags_found = len(asset_tags)
    image_tags_found = len(soup.find_all('img'))
    assets = []
    warnings = []
    skipped_assets = 0
    static_filtered = 0

    for tag in asset_tags:
        src = None
        if tag.name == 'img':
            src = tag.get('src')
        elif tag.name in ('object', 'embed'):
            src = tag.get('data') or tag.get('src')
        elif tag.name == 'source':
            src = tag.get('src')
        elif tag.name in ('audio', 'video'):
            src = tag.get('src')
            if tag.name == 'video' and not src:
                src = tag.get('poster')

        if src and isinstance(src, str) and src.strip():
            src = src.strip()
            # Resolve src relative to the documentation root
            try:
                if local is not None:
                    html_file = local / path
                    asset_absolute = (html_file.parent / src).resolve()
                    asset_relative = asset_absolute.relative_to(local)
                    asset_path_str = str(asset_relative)
                else:
                    html_absolute = url.rstrip('/') + '/' + path.lstrip('/')
                    asset_absolute = _urljoin(html_absolute, src)
                    if asset_absolute.startswith(url):
                        asset_path_str = asset_absolute[len(url):]
                        if asset_path_str.startswith('/'):
                            asset_path_str = asset_path_str[1:]
                    else:
                        skipped_assets += 1
                        continue
            except Exception:
                skipped_assets += 1
                continue

            # Filter _static/ when content_only=True
            if content_only and (
                asset_path_str.startswith('_static/')
                or '/_static/' in asset_path_str
            ):
                static_filtered += 1
                continue

            mime = _mime_from_asset_path(asset_path_str)
            category = _asset_category(asset_path_str, mime)

            # --- Semantic context extraction ---
            # Nearest preceding heading
            h = tag.find_previous(['h1', 'h2', 'h3', 'h4'])
            section_heading = h.get_text(strip=True) if h else None

            # Figcaption from parent <figure>
            caption = None
            fig = tag.find_parent('figure')
            if fig:
                cap = fig.find('figcaption')
                if cap:
                    caption = cap.get_text(strip=True)

            # Nearest preceding paragraph (up to 150 chars)
            context_text = None
            prev_p = tag.find_previous('p')
            if prev_p:
                txt = prev_p.get_text(strip=True)
                if txt:
                    context_text = txt[:150]

            # DOT source for Graphviz SVGs
            # Sphinx renders: <div class="graphviz"><object class="graphviz" data="...svg">
            #                   <p class="warning">digraph ... { ... }</p></object></div>
            dot_source = None
            if tag.name == 'object' and 'graphviz' in (tag.get('class') or []):
                warning_p = tag.find('p', class_='warning')
                if warning_p:
                    dot_src = warning_p.get_text(strip=True)
                    if dot_src.startswith(('digraph', 'graph', 'strict')):
                        dot_source = dot_src
            # Also catch when iterating the outer div instead of the object
            if dot_source is None:
                parent_gv = tag.find_parent('div', class_='graphviz')
                if parent_gv:
                    inner_obj = parent_gv.find('object', class_='graphviz')
                    if inner_obj:
                        warning_p = inner_obj.find('p', class_='warning')
                        if warning_p:
                            dot_src = warning_p.get_text(strip=True)
                            if dot_src.startswith(('digraph', 'graph', 'strict')):
                                dot_source = dot_src

            entry = {
                "path": asset_path_str,
                "mimeType": mime,
                "category": category,
                "section_heading": section_heading,
                "caption": caption,
                "context_text": context_text,
            }
            if dot_source is not None:
                entry["dot_source"] = dot_source

            assets.append(entry)

    # Deduplicate by path (preserve first occurrence / richest context)
    seen = set()
    unique_assets = []
    for asset in assets:
        if asset["path"] not in seen:
            seen.add(asset["path"])
            unique_assets.append(asset)

    # Build metadata
    metadata = {
        "page_title": page_title,
        "total_tags_found": total_tags_found,
        "image_tags_found": image_tags_found,
        "status": "success",
        "asset_count": len(unique_assets),
        "skipped_assets": skipped_assets,
        "static_filtered": static_filtered,
        "warnings": warnings,
    }
    if skipped_assets > 0:
        warnings.append(f"Skipped {skipped_assets} asset(s) outside documentation root")

    return json.dumps({"assets": unique_assets, "metadata": metadata})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="TI Processor SDK Docs MCP Server")
    p.add_argument(
        "--http", metavar="PORT", type=int, nargs="?", const=_HTTP_PORT,
        help="Run as HTTP server on PORT (defaults to TI_PROCESSOR_SDK_MCP_PORT or 7471). "
             "Register: claude mcp add --transport http ti-processor-sdk-docs http://host:PORT/mcp",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.http:
        port = args.http
        mcp.settings.port = port
        logger.info(f"TI Processor SDK Docs MCP -- HTTP mode, port {port}\n")
        logger.info(
            f"Register: claude mcp add --transport http ti-processor-sdk-docs "
            f"http://localhost:{port}/mcp\n"
        )
        asyncio.run(mcp.run_streamable_http_async())
    else:
        asyncio.run(mcp.run_stdio_async())
