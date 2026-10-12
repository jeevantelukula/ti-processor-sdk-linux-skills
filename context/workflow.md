# End-to-end workflow

| Phase | Skill |
|---|---|
| Setup | `ti-sdk-setup`, `ti-generate-kb` (builds the per-device knowledge base `$TI_KB` from the SDK) |
| Customize | `ti-gpio-pinmux`, `ti-device-tree-overlay`, `ti-custom-board-port`, `ti-customize-clocks`, `ti-resource-partition`, `ti-yocto-custom-dt` |
| Build | `ti-build-source` (SDK Makefile), `ti-yocto-build` (Yocto), `ti-kernel-module` |
| Deploy | `ti-deploy-image`, `ti-boot-chain` |
| Run on target | `ti-remoteproc`, `ti-pru` (only SoCs with PRU) |
| Validate / debug | `ti-diagnostic` |

Entry point: `ti-sdk-quick-start`. Skill list must match `skills/`; CI enforces this.
Documentation for every phase comes from the docs MCP: see `mcp-usage.md`.
