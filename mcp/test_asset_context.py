#!/usr/bin/env python3
"""
Test script for the enriched list_page_assets tool.

Runs the MCP server as a subprocess (stdio mode) and exercises:
  1. Linux SDK GPIO page  -> raster images with semantic context
  2. Buildroot Overview page -> graphviz SVG with dot_source
  3. content_only=False vs True showing _static/ filter
  4. get_asset on a resolved path
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

SERVER = Path(__file__).parent / "server.py"


def rpc(proc, req_id, method, params=None):
    req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    raw = proc.stdout.readline()
    resp = json.loads(raw)
    if "error" in resp:
        raise RuntimeError(f"RPC error: {resp['error']}")
    content = resp["result"]["content"][0]["text"]
    return json.loads(content)


def start():
    p = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    # initialize
    p.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": 0,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
    }) + "\n")
    p.stdin.flush()
    p.stdout.readline()  # discard init response
    return p


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def show_asset(a, idx):
    print(f"\n  [{idx}] {a['path']}")
    print(f"       mimeType : {a['mimeType']}")
    print(f"       category : {a['category']}")
    print(f"       heading  : {a.get('section_heading', '')!r}")
    print(f"       caption  : {a.get('caption', '')!r}")
    ctx = a.get('context_text') or ''
    if ctx:
        print(f"       context  : {textwrap.shorten(ctx, 80)!r}")
    if 'dot_source' in a:
        ds_preview = a['dot_source'][:120].replace('\n', ' ')
        print(f"       dot_src  : {ds_preview!r}...")


proc = start()
_id = [1]


def call(method, **kwargs):
    i = _id[0]; _id[0] += 1
    return rpc(proc, i, "tools/call", {"name": method, "arguments": kwargs})


# ── TEST 1: Linux GPIO page ──────────────────────────────────────────────────
section("1. Linux GPIO page (raster images + semantic context)")

result = call(
    "ti_processor_sdk_docs_list_assets",
    path="linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html",
    device="AM62X", os="linux", version="latest", source="software-dl",
    content_only=True,
)
meta = result["metadata"]
print(f"\n  page_title    : {meta.get('page_title')!r}")
print(f"  asset_count   : {meta['asset_count']}")
print(f"  static_filtered: {meta.get('static_filtered', 0)}")

for i, a in enumerate(result["assets"]):
    show_asset(a, i)


# ── TEST 2: content_only=False shows _static/ assets ────────────────────────
section("2. GPIO page with content_only=False (shows _static/ noise)")

result2 = call(
    "ti_processor_sdk_docs_list_assets",
    path="linux/Foundational_Components/Kernel/Kernel_Drivers/GPIO.html",
    device="AM62X", os="linux", version="latest", source="software-dl",
    content_only=False,
)
static_paths = [a["path"] for a in result2["assets"] if "_static/" in a["path"]]
content_paths = [a["path"] for a in result2["assets"] if "_images/" in a["path"]]
print(f"\n  Total with content_only=False : {result2['metadata']['asset_count']}")
print(f"  _static/ paths : {static_paths}")
print(f"  _images/ paths : {content_paths}")


# ── TEST 3: Buildroot page → graphviz dot_source ─────────────────────────────
section("3. Buildroot Overview page (graphviz SVG + dot_source)")

result3 = call(
    "ti_processor_sdk_docs_list_assets",
    path="buildroot/Overview.html",
    device="AM62X", os="buildroot", version="latest", source="software-dl",
    content_only=True,
)
meta3 = result3["metadata"]
print(f"\n  page_title  : {meta3.get('page_title')!r}")
print(f"  asset_count : {meta3['asset_count']}")

for i, a in enumerate(result3["assets"]):
    show_asset(a, i)

# Check dot_source present
gv_assets = [a for a in result3["assets"] if "dot_source" in a]
print(f"\n  Graphviz assets with dot_source: {len(gv_assets)}")
if gv_assets:
    print(f"\n  DOT source (first 500 chars):")
    print(textwrap.indent(gv_assets[0]["dot_source"][:500], "    "))


# ── TEST 4: get_asset on a resolved path ────────────────────────────────────
section("4. get_asset on first image from GPIO page")

if result["assets"]:
    first_path = result["assets"][0]["path"]
    print(f"\n  Fetching: {first_path}")
    asset = call(
        "ti_processor_sdk_docs_get_asset",
        asset_path=first_path,
        device="AM62X", os="linux", version="latest", source="software-dl",
    )
    print(f"  mimeType : {asset.get('mimeType')}")
    print(f"  size     : {asset.get('size')} bytes")
    print(f"  data len : {len(asset.get('data',''))} base64 chars")
else:
    print("  No assets found on GPIO page, skipping.")


# ── TEST 5: Buildroot get_asset on graphviz SVG ──────────────────────────────
section("5. get_asset on the Buildroot graphviz SVG")

if gv_assets:
    gv_path = gv_assets[0]["path"]
    print(f"\n  Fetching: {gv_path}")
    svg_asset = call(
        "ti_processor_sdk_docs_get_asset",
        asset_path=gv_path,
        device="AM62X", os="buildroot", version="latest", source="software-dl",
    )
    print(f"  mimeType : {svg_asset.get('mimeType')}")
    print(f"  size     : {svg_asset.get('size')} bytes")
    print(f"  data len : {len(svg_asset.get('data',''))} base64 chars")
    # Decode first 200 chars of SVG to confirm it's valid SVG
    import base64
    svg_bytes = base64.b64decode(svg_asset["data"])
    print(f"  SVG start: {svg_bytes[:80]!r}")
else:
    print("  No graphviz assets found, skipping.")


proc.terminate()
proc.wait()
print("\n\nAll tests complete.")
