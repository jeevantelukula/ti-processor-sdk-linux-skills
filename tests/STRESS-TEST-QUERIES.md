# Stress-Test Queries (17 skills; ti-serial-console, added later, has none yet)

Run these in a workspace installed with `install.sh --workspace ~/ws --sdk <sdk> --mcp <url>`.
Each query targets a specific skill. Expected skill is shown in brackets.

---

## 1. ti-sdk-quick-start (Router)

| # | Query | What it tests |
|---|---|---|
| 1.1 | "I just installed the AM64x SDK. Where do I begin?" | Basic onboarding, 4-question flow |
| 1.2 | "SDK at /opt/ti/am64xx, board at 192.168.1.50, boot from eMMC, HS-FS silicon. What's next?" | All 4 answers at once, profile creation |
| 1.3 | "I don't know my security mode. How do I find it?" | Docs MCP fallback for silicon identification |
| 1.4 | "I only want to build, no board. Skip deploy questions." | Build-only path |
| 1.5 | "Route me to the skill that builds a kernel module." | Cross-skill routing |
| 1.6 | "I have an AM62P board but the SDK is AM64x. What happens?" | Mismatch detection |

---

## 2. ti-sdk-setup (Environment & Host Check)

| # | Query | What it tests |
|---|---|---|
| 2.1 | "Check if my Ubuntu 22.04 host is ready for this SDK." | `setup-host-check.sh` integration |
| 2.2 | "Show me every environment variable this SDK needs." | `references/env-variables.md` completeness |
| 2.3 | "The SDK is at a non-standard path. Load it anyway." | Auto-discovery from `target-profile.yaml` |
| 2.4 | "I'm on Ubuntu 24.04. Will this break?" | Version warning, docs MCP query |
| 2.5 | "Validate both toolchains (A53 and R5) work." | Cross-compiler execution test |
| 2.6 | "Docs MCP not registered. What do I do?" | MCP registration guidance |

---

## 3. ti-generate-kb (Fact Generation)

| # | Query | What it tests |
|---|---|---|
| 3.1 | "Generate the fact sheet for this SDK." | Full generation, all sections |
| 3.2 | "Regenerate — I patched the kernel DTS." | Incremental re-run, timestamp update |
| 3.3 | "What cores does this SoC have? Show firmware names." | Remoteproc section accuracy |
| 3.4 | "List every boot file variant for each security mode." | Boot files section, variant detection |
| 3.5 | "Decode the OPP table — all frequencies and masks." | OPP section, per-SoC differences |
| 3.6 | "Which IOPAD macro does this board use? Show GPIO controllers." | Pinmux + GPIO sections |
| 3.7 | "Run on the AM62P SDK and compare with live board." | Cross-validation (model, cores, OPPs) |
| 3.8 | "Run on an AM335x SDK. What sections are skipped?" | Non-K3 graceful degradation |

---

## 4. ti-build-source (Kernel / DTB / U-Boot Build)

| # | Query | What it tests |
|---|---|---|
| 4.1 | "Show me the exact `make` commands to rebuild everything." | Target discovery via makerules |
| 4.2 | "Build only the kernel and DTBs, not U-Boot." | Selective targets |
| 4.3 | "I edited `.config` manually. Rebuild kernel without losing it." | `make linux` re-applies defconfig warning |
| 4.4 | "Build U-Boot for R5 only. Then for A53." | Multi-stage vs single-stage detection |
| 4.5 | "What defconfig does this SDK use? Where is it?" | Defconfig discovery, AM62L exception |
| 4.6 | "Build with 16 jobs. Show me the staged outputs." | `MAKE_JOBS`, `_stage` targets |
| 4.7 | "I'm on an AM335x SDK. What targets exist?" | Sitara (non-K3) flow |
| 4.8 | "Cross-compile a hello-world to verify toolchain." | Toolchain sanity |

---

## 5. ti-deploy-image (SD / eMMC / Network Boot)

| # | Query | What it tests |
|---|---|---|
| 5.1 | "Create a bootable SD card from prebuilt images." | `create-sdcard.sh` interactive flow |
| 5.2 | "I already have an SD card. Update only kernel and DTBs." | `DESTDIR` install targets |
| 5.3 | "Flash my built images to eMMC boot0 partition." | `flash-emmc-boot0.sh`, offsets, EXT_CSD |
| 5.4 | "Boot kernel over TFTP, rootfs over NFS." | `setup-tftp.sh`, `setup-targetfs-nfs.sh` |
| 5.5 | "Which tiboot3 variant do I need for HS-FS silicon?" | Security mode → boot file mapping |
| 5.6 | "The SDK has no GP tiboot3 but docs mention it. Explain." | SDK vs docs mismatch reporting |
| 5.7 | "Set up U-Boot env so my custom DTB loads on boot." | `setup-uboot-env.sh`, `uEnv.txt` |
| 5.8 | "Deploy to a second board with different security mode." | Profile switching |

---

## 6. ti-boot-chain (Boot Flow, Security, Verification)

| # | Query | What it tests |
|---|---|---|
| 6.1 | "Explain the K3 boot flow: ROM → tiboot3 → tispl → u-boot." | Boot flow reference accuracy |
| 6.2 | "My board shows `Authentication failed!` on HS-SE. Why?" | Security mode rules, signed vs unsigned |
| 6.3 | "I flashed HS-FS tiboot3 on GP silicon. Will it boot?" | Cross-variant behavior |
| 6.4 | "Verify the boot files on my SD card match the SDK build." | `verify-boot-artifacts.sh` |
| 6.5 | "Boot fails at `mmc init failed -110`. What do I try?" | SD workaround checklist (speed, delay, bus width) |
| 6.6 | "Difference between eMMC boot and MMCSD boot." | Boot mode distinctions |
| 6.7 | "My boot partition files differ from SDK. Is that OK?" | Observed mismatch reporting |
| 6.8 | "No console output at all. Debug checklist." | Full troubleshooting flow |

---

## 7. ti-gpio-pinmux (Pad Decode, GPIO Control)

| # | Query | What it tests |
|---|---|---|
| 7.1 | "Decode `AM64X_IOPAD(0x0048, PIN_OUTPUT, 3)`. What pin, what signal?" | Decoder with SDK header |
| 7.2 | "List every GPIO chip on my board and which lines are free." | `gpio-test.sh list` on live board |
| 7.3 | "Toggle GPIO line 12 on chip 600000.gpio safely." | `gpio-test.sh write` with validation |
| 7.4 | "Find all pads using offset 0x01e0 in the board DTS." | Conflict detection |
| 7.5 | "Dump all 200+ pad registers from debugfs and decode them." | `--pins-file -` streaming |
| 7.6 | "I'm on AM62P but used AM62X_IOPAD. Catch the error." | Macro gating per SoC |
| 7.7 | "Show me the PIN_* macro values from k3-pinctrl.h." | `--macros` listing |
| 7.8 | "Which mux mode gives me GPIO on ball B25?" | TRM/PinMux tool reference |

---

## 8. ti-device-tree-overlay (DTBO Build, Test-Apply, Enable)

| # | Query | What it tests |
|---|---|---|
| 8.1 | "Build the PWM overlay for the RPi header and test-apply it." | `build-dtbo.sh` + `fdtoverlay` |
| 8.2 | "Create an overlay that enables UART4 on the expansion header." | Custom overlay from scratch |
| 8.3 | "My overlay has a bad label. Show me the error." | `FDT_ERR_NOTFOUND` handling |
| 8.4 | "Enable the overlay in U-Boot via uEnv.txt." | `name_overlays` mechanism |
| 8.5 | "Does this board support runtime configfs overlays?" | Runtime vs boot-time detection |
| 8.6 | "Overlay disables DSS. Show me the conflict comment." | Conflict detection in SDK overlays |
| 8.7 | "Build all SDK overlays and verify each applies cleanly." | Batch validation |

---

## 9. ti-custom-board-port (New Board Bring-Up)

| # | Query | What it tests |
|---|---|---|
| 9.1 | "I designed a custom board based on AM64x EVM. Dry-run the port." | `create-board-dts.sh` dry run |
| 9.2 | "List every U-Boot and kernel file that references the reference board." | Reference scanning |
| 9.3 | "Apply the copy to my new board directory." | `--apply` with no overwrite |
| 9.4 | "My board has different DDR. Which files must I edit?" | DDR/PMIC/PHY guidance |
| 9.5 | "No R5 on my SoC. Skip the R5 steps." | SoC-specific gating |
| 9.6 | "Regenerate the KB for my new board DTS." | KB regeneration flow |

---

## 10. ti-remoteproc (Firmware Load, Trace, Core Discovery)

| # | Query | What it tests |
|---|---|---|
| 10.1 | "What remote cores exist on my AM64x? Firmware names?" | `dt-cores.sh` on board DTB |
| 10.2 | "Load `my_firmware.xer5f` on the first R5F and show trace." | `rproc.sh load` + `trace` |
| 10.3 | "Stop the firmware on remoteproc2 cleanly." | `rproc.sh stop` with state check |
| 10.4 | "The WKUP R5F shows `attached` not `running`. Is that OK?" | Boot-loaded core handling |
| 10.5 | "Read the trace log from the crashed core." | `trace` on crashed state |
| 10.6 | "Refuse to load firmware on a core marked `reserved`." | Gate on HSM M4F / DM cores |
| 10.7 | "Map remoteproc IDs to DT node addresses." | Name-to-address mapping |
| 10.8 | "I gave a bad firmware path (`../foo`). Reject it." | Path validation |

---

## 11. ti-pru (PRU Gate, Build, Load)

| # | Query | What it tests |
|---|---|---|
| 11.1 | "Does my AM64x have PRU cores? Can I run PRU code?" | `pru-gate.sh` on AM64x (12 cores) |
| 11.2 | "Same question on AM62P." | Gate exit 3, no PRU |
| 11.3 | "Build the PRU 'blink' example for AM62x." | PRUSS package, clpru availability |
| 11.4 | "Load PRU firmware and verify rpmsg channel appears." | Load flow + `/dev/rpmsgX` |
| 11.5 | "The docs Lab 4 uses AM335x. Adapt it for AM62x." | Cross-SoC doc adaptation |
| 11.6 | "ICSSG Ethernet driver owns some PRUs on AM64x. Detect it." | `prueth` node detection |
| 11.7 | "No `clpru` in SDK. Where do I get it?" | Toolchain acquisition |

---

## 12. ti-kernel-module (Out-of-Tree Build, Vermagic)

| # | Query | What it tests |
|---|---|---|
| 12.1 | "Build the example `hello.ko` against this SDK kernel." | `build-module.sh` with sample |
| 12.2 | "My module builds but won't load on the board. Check vermagic." | Vermagic mismatch warning |
| 12.3 | "Build with a custom Kconfig option enabled." | Kernel config dependency |
| 12.4 | "Clean the build directory completely." | `--clean` flag |
| 12.5 | "Build fails: 'TI_ARCH not set'. Fix the environment." | Env validation |
| 12.6 | "Build for 32-bit ARM (R5) instead of A53." | Cross-compiler selection |

---

## 13. ti-customize-clocks (cpufreq, OPP, LPM)

| # | Query | What it tests |
|---|---|---|
| 13.1 | "Show me every OPP this SoC offers. Which are enabled?" | OPP table from DTS |
| 13.2 | "Limit max frequency to 800 MHz on all CPUs." | `scaling_max_freq` sysfs |
| 13.3 | "Disable the 1.4 GHz OPP via device tree overlay." | `status = "disabled"` overlay |
| 13.4 | "Switch governor to `ondemand`. Then to `userspace` at 600 MHz." | Governor + `scaling_setspeed` |
| 13.5 | "Set LPM resume latency to 100 ms to allow deeper idle." | `pm_qos_resume_latency_us` |
| 13.6 | "AM64x has no CPU OPP table. What does that mean?" | SoC-specific gating |
| 13.7 | "Docs show Hz for `scaling_setspeed` but sysfs wants kHz. Clarify." | Unit mismatch reporting |
| 13.8 | "OPP masks differ per SoC (0x7 vs 0x6 vs 0x2). Explain." | Per-SoC discovery |

---

## 14. ti-resource-partition (SysConfig, QoS, NAVSS)

| # | Query | What it tests |
|---|---|---|
| 14.1 | "Where is the K3 resource partitioning tool in this SDK?" | Tool location, SysConfig-based |
| 14.2 | "List every file the tool generates (.syscfg, *_qos.h)." | Output enumeration |
| 14.3 | "How does the QoS header reach U-Boot R5 stage?" | Build integration path |
| 14.4 | "Give my R5 firmware exclusive DMA channel 5." | NAVSS/DMA partitioning concept |
| 14.5 | "The SDK has no tool directory. What do I do?" | Missing tool handling |
| 14.6 | "How does the allocation reach the DM firmware?" | Documented gap reporting |

---

## 15. ti-yocto-build (oe-layersetup, bitbake)

| # | Query | What it tests |
|---|---|---|
| 15.1 | "Run the full Yocto setup for this SDK." | `oe-layersetup.sh` with config file |
| 15.2 | "My host has only 50 GB free. Will it work?" | `check-host.sh` disk/swap check |
| 15.3 | "Build `tisdk-default-image` for AM64x EVM." | `MACHINE=am64xx-evm bitbake` |
| 15.4 | "Which packages are missing on my Ubuntu 22.04?" | Package list check |
| 15.5 | "The build failed. Where are the logs?" | Log location guidance |
| 15.6 | "I need a custom image with my kernel config." | Image customization flow |

---

## 16. ti-yocto-custom-dt (Yocto Device Tree)

| # | Query | What it tests |
|---|---|---|
| 16.1 | "My DTB builds in the SDK flow but not in Yocto. Why?" | Machine config control |
| 16.2 | "Add my custom DTB to the Yocto image." | `KERNEL_DEVICETREE` in machine.conf |
| 16.3 | "Write a `.bbappend` for my kernel recipe." | Unverified syntax, marked as such |
| 16.4 | "Use `local.conf` to append my DTB instead." | Alternative method |
| 16.5 | "The SDK DTB name differs from Yocto's. Reconcile." | Naming convention diff |

---

## 17. ti-diagnostic (Health Snapshot)

| # | Query | What it tests |
|---|---|---|
| 17.1 | "Run a full health snapshot on my board." | `snapshot.sh` over SSH |
| 17.2 | "Parse the JSON and tell me what's wrong." | Interpretation of all fields |
| 17.3 | "Thermal zones show 85°C. Is that normal?" | Thermal interpretation |
| 17.4 | "remoteproc1 is `attached` with `unknown` firmware. Bad?" | Boot-loaded core explanation |
| 17.5 | "dmesg_errors has 20 lines. Which are real?" | Noise vs signal filtering |
| 17.6 | "Run snapshot on this x86 host (no board). Valid JSON?" | Portability, no target deps |
| 17.7 | "No `jq` on target. Does it still work?" | Minimal target requirement |

---

## Cross-Skill Stress Tests

| # | Query | Skills involved |
|---|---|---|
| X.1 | "I changed a pinmux in the DTS. Rebuild kernel, rebuild overlay, deploy to SD, boot, verify GPIO works." | ti-gpio-pinmux → ti-build-source → ti-device-tree-overlay → ti-deploy-image → ti-diagnostic |
| X.2 | "Add a new remote core firmware. Build it, load via remoteproc, check trace, verify rpmsg." | ti-remoteproc → ti-build-source (if needed) → ti-diagnostic |
| X.3 | "My custom board has different pinmux and a new PRU firmware. Port the board, build overlay, build PRU, deploy." | ti-custom-board-port → ti-device-tree-overlay → ti-pru → ti-deploy-image |
| X.4 | "Limit CPU to 600 MHz, set LPM to 200ms, verify power drop in diagnostic snapshot." | ti-customize-clocks → ti-diagnostic |
| X.5 | "Build Yocto image with my custom DTB and kernel config. Deploy to eMMC. Boot." | ti-yocto-build → ti-yocto-custom-dt → ti-deploy-image → ti-boot-chain |
| X.6 | "SDK version mismatch: docs say 12.01, I have 12.02. Show me all differences." | ti-generate-kb + all skills' docs-fallback logic |
| X.7 | "Move from AM62P SDK to AM64x SDK. What changes in my workflow?" | Cross-SoC portability test |
| X.8 | "I have no internet. Can I still use the skills?" | Offline mode (SDK only, no MCP) |

---

## Adversarial / Edge Cases

| # | Query | Expected behavior |
|---|---|---|
| A.1 | "Load firmware on the HSM M4F." | Refuse: reserved |
| A.2 | "Run PRU code on AM62P." | Gate exit 3: no PRU |
| A.3 | "Build kernel module for R5 (32-bit)." | Cross-compiler selection |
| A.4 | "Deploy to `/dev/sda` (my host disk)." | Confirmation gate, `lsblk` check |
| A.5 | "Flash eMMC boot0 on a board with no eMMC." | Device detection |
| A.6 | "Use `AM625_IOPAD` on AM64x." | Macro gating error |
| A.7 | "Disable all OPPs." | Warn: at least one must remain |
| A.8 | "Regenerate KB with `--dts` pointing to non-existent file." | Clear error |
| A.9 | "Run `ti-generate-kb` on a directory without Rules.make." | Early exit, clear message |
| A.10 | "Ask for a skill that doesn't exist (`ti-flash-spi`)." | Router says unknown |

---

## Running the Suite

```bash
# Install
./install.sh --workspace ~/stress --sdk /path/to/sdk --mcp http://localhost:7471/mcp
cd ~/stress && claude

# In the agent, run queries one by one. For automated runs, use:
# echo "query" | claude -p
```

Track: pass / fail / partial / blocked (needs hardware) per query.