# Using the `ti-processor-sdk-docs` MCP

Skills do not embed TI documentation. They point to it and fetch it on demand
through the `ti-processor-sdk-docs` MCP server (source: `mcp/`).

## Tools

| Tool | Use |
|---|---|
| `ti_processor_sdk_docs_list_variants` | Discover valid `(device, os)` pairs. Call first if unsure of the device key. |
| `ti_processor_sdk_docs_list_versions(device)` | List SDK versions published on ti.com for a device. |
| `ti_processor_sdk_docs_search(query, device, os, version, max_results)` | Find pages. Returns `title`, `path`, `score`. |
| `ti_processor_sdk_docs_read(path, device, os, version)` | Read one page as text. `path` comes from search. |
| `ti_processor_sdk_docs_list_assets(path, ...)` / `..._get_asset(asset_path, ...)` | Diagrams and images referenced by a page. |

`device` uses the MCP key (list with `ti_processor_sdk_docs_list_variants`; e.g. `AM62PX`, `AM64X`), not the SDK
`PLATFORM` value. `os` is `linux` unless the user says otherwise.

## Rules every skill follows

1. Pass `device` and `version` explicitly. Never rely on defaults (default device is `AM62X`).
2. Get `device` from `$TI_DOCS_DEVICE` (set by `lib/ti-sdk-env.sh`), else `docs.device` in
   `.claude/target-profile.yaml`, else find it with `ti_processor_sdk_docs_list_variants` and ask the user.
3. Get `version` from `$TI_SDK_VERSION_DOCS` (derived from the SDK directory name, for example
   `12.02.00.01.01` becomes `12_02_00_01_01`; cross-check `manifest/software_manifest.txt`). If `list_versions` does not include it,
   the MCP lags the SDK: use `latest`, and tell the user the page may differ from the installed SDK.
4. Search, then read. Do not guess page paths.
5. Treat docs as the authority for procedures. Treat the installed SDK (`Rules.make`, `Makefile`,
   kernel DTS) as the authority for device values. If they disagree, report both.
6. If the MCP is unavailable, say so and fall back to the SDK on disk. Do not answer from memory.
7. Cite the doc path you used. When the page names a different SoC, board or version than the installed
   SDK, say which parts you took from the page and which from the SDK.

## Example

Example from AM62P SDK 12.02.00.01.01 (`TI_DOCS_DEVICE=AM62PX`; yours will differ):

```
ti_processor_sdk_docs_search(query="top level makefile build linux u-boot", device=$TI_DOCS_DEVICE, os="linux", version="latest")
ti_processor_sdk_docs_read(path="linux/Overview/Top_Level_Makefile.html", device=$TI_DOCS_DEVICE, os="linux", version="latest")
```
