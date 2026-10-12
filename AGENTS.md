# TI Processor SDK Linux - agent instructions

You help developers work with an installed TI Processor SDK Linux: set up, customize, build,
deploy, and validate on a TI K3 board. Skills live in `skills/` (one directory each, `SKILL.md` inside).

## Ground rules

1. Device values come from the SDK, not memory. Read `Rules.make` (via `lib/ti-sdk-env.sh`),
   the SDK `manifest/`, the kernel DTS, or the live board. Never assume SoC, DTB, firmware or pin names.
2. Per-device facts come from the generated knowledge base (`$TI_KB`, with `$TI_FACTS_JSON` and
   `$TI_FACTS_DIR`; set by `lib/ti-sdk-env.sh`). Regenerate it with the `ti-generate-kb` skill. If it is
   absent, derive the facts from the SDK directly. Never reuse facts from another device or SDK.
3. Procedures come from TI docs through the `ti-processor-sdk-docs` MCP. Follow
   `context/mcp-usage.md`: pass `device`, `os`, `version` explicitly; search, then read.
4. If a fact cannot be verified from the SDK, the board, or the docs, say so. Do not fill the gap.
5. Ask before destructive actions: flashing, partitioning, overwriting boot files, `rm` in the SDK.

## Layout

| Path | Purpose |
|---|---|
| `skills/` | Task skills; start at `ti-sdk-quick-start` |
| `context/` | Shared reference: `workflow.md`, `sdk-structure.md`, `mcp-usage.md` |
| `lib/ti-sdk-env.sh` | Exports `TI_SOC`, `TI_PLATFORM`, `TI_ARCH`, `TI_SDK_ROOT`, `TI_KB`, ... from the SDK |
| `templates/` | `target-profile.yaml` (user-chosen values only) |
| `mcp/` | Docs MCP server source (deployed separately) |
| `install.sh` | Copies `skills/`, `context/`, `lib/`, `templates/` into `<workspace>/.claude` |

## Contributing

See `CONTRIBUTING.md`.
