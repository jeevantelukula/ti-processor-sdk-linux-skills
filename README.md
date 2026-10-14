# TI Processor SDK Linux skills

Agent skills (Claude Code / AGENTS.md compatible) for TI Processor SDK Linux:
setup, customize, build, deploy, validate. Device-agnostic: device facts are read from the installed
SDK and collected in a generated knowledge base (`ti-generate-kb`); procedures come from TI
documentation via the `ti-processor-sdk-docs` MCP.

```bash
./install.sh --workspace ~/ws --sdk /path/to/ti-processor-sdk-linux-<platform>-<version>
cd ~/ws && claude
```

Add `--mcp-mode auto` to register the `ti-processor-sdk-docs` MCP too (HTTP server if one answers, else
Docker, else a local stdio server). Re-run with `--force` to update; only the installer's own files are replaced.

Packaged in an SDK installer, `install.sh` finds the SDK automatically. Standalone, pass `--sdk` or
set `TI_SDK_ROOT`. See `AGENTS.md`, `context/mcp-usage.md`, and `mcp/README.md`.

Demo and management guide: `docs/AGENTIC-SDK-GUIDE.md`.
