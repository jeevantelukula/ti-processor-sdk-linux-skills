# TI Processor SDK Linux - agent instructions

You help developers work with an installed TI Processor SDK Linux: set up, customize, build,
deploy, and validate on a TI K3 board. Skills live in `skills/` (`.claude/skills/` in an installed
workspace), one directory each with a `SKILL.md`. Start at `ti-sdk-quick-start`.

Each skill is self-contained: everything it uses is inside its directory, and paths in a `SKILL.md`
are relative to that directory. Every skill bundles `scripts/ti-sdk-env.sh` (SDK values) and
`references/mcp-usage.md` (docs MCP rules). Shell variables do not persist between commands, so run
`source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*`; the
bundled scripts load it themselves.

## Ground rules

1. Device values come from the SDK, not memory. Read `Rules.make` (via the skill's
   `scripts/ti-sdk-env.sh`), the SDK `manifest/`, the kernel DTS, or the live board. Never assume SoC,
   DTB, firmware or pin names.
2. Per-device facts come from the generated knowledge base (`$TI_KB`, with `$TI_FACTS_JSON` and
   `$TI_FACTS_DIR`; set by `scripts/ti-sdk-env.sh`). Regenerate it with the `ti-generate-kb` skill. If it
   is absent, derive the facts from the SDK directly. Never reuse facts from another device or SDK.
3. Procedures come from TI docs through the `ti-processor-sdk-docs` MCP. Follow the skill's
   `references/mcp-usage.md`: pass `device`, `os`, `version` explicitly; search, then read.
4. If a fact cannot be verified from the SDK, the board, or the docs, say so. Do not fill the gap.
5. Ask before destructive actions: flashing, partitioning, overwriting boot files, `rm` in the SDK.

## Layout

| Path | Purpose |
|---|---|
| `skills/` | Task skills, each self-contained (`SKILL.md`, `scripts/`, `references/`, `assets/`) |
| `context/` | Overview: `workflow.md` (phases and skills), `sdk-structure.md`, `known-quirks.md`, `mcp-usage.md` |
| `mcp/` | Docs MCP server (`server.py`, `requirements.txt`); run in Docker or as a local stdio server |
| `.claude/target-profile.yaml` | Workspace profile: user-chosen values only (SDK path, board, serial, boot medium) |
| `.claude/target-platform/` | Generated knowledge base (`ti-generate-kb`) |

In the skills repository (not copied into workspaces), the files several skills share have one
source each in `lib/`, `context/` and `templates/`; `tools/sync-shared.py` copies them into the
skills, and CI fails if a copy is out of date. `install.sh` copies `skills/`, `context/` and the MCP
server into `<workspace>/.claude` (other `.claude` content is left alone); `--mcp-mode` registers the
docs MCP. Contributing: `CONTRIBUTING.md`.
