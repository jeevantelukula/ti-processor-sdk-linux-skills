# SDK Customization Workflow

End-to-end view of how a TI Processor SDK customization flows from workspace initialization through to a deployed and validated board.

**Audience:** any engineer or skill that needs to understand where a given customization step sits in the larger pipeline, which files are touched, and which skill owns each phase.

---

## Phases at a glance

```
INIT ──► CUSTOMIZE ──► BUILD ──► DEPLOY ──► VALIDATE
```

- **INIT** prepares the workspace: SDK path, board profile, toolchain, document links.
- **CUSTOMIZE** stages customizations: device tree overlays, Yocto bbappend recipes, pinmux changes, peripheral config. No build occurs here.
- **BUILD** compiles artifacts from source: kernel, U-Boot, custom modules, Yocto image. Build outputs stay in-tree.
- **DEPLOY** writes artifacts to the target: flash SD/eMMC, load firmware via remoteproc, apply overlays.
- **VALIDATE** confirms the target behaves correctly: boot log analysis, GPIO test, remoteproc state, console check.

---

## Workflow invariants

Every SDK customization must satisfy these invariants. Violating them destroys the change trail that review, bisect, and SDK version migration depend on.

**Load the active target profile before acting.** Before any edit, build, flash, or validate step, read `target-platform/<active>.yaml`. If the profile is missing or incomplete, stop and run `/ti-sdk-init` first. Never infer board identity from directory names or tarball filenames.

**All customizations land in the workspace, not in SDK-installed paths.** The SDK root (`sdk.root_path`) is read-only after installation. All edits go to the Yocto workspace (`source.yocto_workspace`) or the custom layer (`source.custom_layer`). The SDK root is a pristine reference.

**SYSFW ABI lock.** Never mix `tiboot3.bin`, `tispl.bin`, or `u-boot.img` across SDK releases. The System Firmware ABI is release-specific. Breaking this causes silent boot failures that are hard to diagnose. See `references/sdk-versions.md`.

**Security mode governs signing.** `hs-se` boards require authenticated boot binaries signed with your production keys. `hs-fs` boards use TI-provided development certificates. `gp` boards have no authentication. The active profile's `board.security_mode` field determines which binary set to use.

**One commit per logical change.** When multiple files implement a single logical customization (e.g., adding a new peripheral requires DTS edit + bbappend + defconfig fragment), all files land in one commit with a message that names the feature and all affected files. Never one commit per file when they implement the same feature.

**Commit message preview gate.** Before committing any customization to the Yocto workspace or custom layer, the skill must display the proposed commit message and staged file list and wait for operator confirmation. The gate has no bypass. This ensures every change is intentional and traceable.

---

## Phase: INIT

Purpose: establish a reproducible workspace state so all subsequent skills share the same context.

```
/ti-sdk-init
  ▸ validates SDK installation at sdk.root_path
  ▸ detects kernel/U-Boot versions, writes to profile (DERIVED fields)
  ▸ validates toolchain at toolchain.path or sdk.root_path/linux-devkit/
  ▸ sets active: true on the chosen profile

/ti-sdk-link-docs   (optional but strongly recommended)
  ▸ accepts paths to TRM, datasheet, schematic, SysConfig CSV
  ▸ writes them to the documents: block of the active profile
  ▸ skills that parse datasheets and schematics read only from this block
```

Skills: `ti-sdk-init`, `ti-sdk-link-docs`

---

## Phase: CUSTOMIZE

Purpose: stage logical customizations to the Yocto workspace or custom layer. No compilation occurs. Each customization is an independent, reviewable change.

### Routing by customization type

| What you're changing | Target files | Skill |
|---|---|---|
| Kernel device tree (board-specific) | `meta-<company>/recipes-kernel/linux/linux-ti-staging.bbappend` + `files/*.dts` | `ti-yocto-custom-dt` |
| Device tree overlay (runtime, no rebuild) | `<rootfs>/boot/overlays/*.dtbo` + `extlinux.conf` | `ti-dt-overlay` |
| GPIO pad mux / pinmux PADCONFIG | Kernel DTS `&main_pmx0` block | `ti-gpio-pinmux` |
| Kernel config fragment | `meta-<company>/recipes-kernel/linux/files/*.cfg` | `ti-kernel-module` |
| Custom board port (new board) | new board DTS + bbappend | `ti-custom-board-port` |
| Clock rates | Kernel DTS clock nodes + TISCI constraints | `ti-customize-clocks` |
| R5F/M4F firmware | `<sdk>/board-support/prebuilt-images/` + remoteproc config | `ti-remoteproc-firmware` |
| PRU firmware | `<sdk>/board-support/prebuilt-images/` + PRU device tree | `ti-pru-programming` |
| eMMC flash | writes directly to target eMMC via SSH/console | `ti-emmc-deploy` |

### Commit protocol for Yocto workspace changes

A single logical customization that touches multiple files issues **at most two commits** in the custom layer:

1. **Pristine-state commit** — copies the original (unmodified) file into the custom layer if it isn't already there. Skip if the file is new (bbappend creating a new recipe has no pristine to import).
2. **Customization commit** — the actual change, covering every file the step touched.

Both commits pass through the **commit message preview gate**.

For SDK tree files that must not be modified in-place: copy to `source.custom_layer` first (pristine commit), then edit (customization commit). For new files that only live in the custom layer: one commit.

---

## Phase: BUILD

Purpose: compile artifacts from source. Auto-chains from CUSTOMIZE when source files changed. Re-runnable on demand via `/ti-yocto-build-setup`.

```
/ti-yocto-build-setup
  ▸ validates host prerequisites (Ubuntu 22.04, disk space, packages)
  ▸ sources oe-init-build-env
  ▸ configures bblayers.conf and local.conf for the active MACHINE
  ▸ runs bitbake <target-image> or bitbake virtual/kernel

Cross-module builds (kernel only, faster):
  ▸ uses sdk.root_path/linux-devkit/environment-setup-* for CROSS_COMPILE
  ▸ runs make -C <kernel-src> M=<module-src> modules
  ▸ handled by ti-kernel-module skill
```

Build outputs stay in-tree under the Yocto workspace `tmp/` directory. They are NOT promoted to the SDK root.

Skills: `ti-yocto-build-setup`, `ti-kernel-module`

---

## Phase: DEPLOY

Purpose: write artifacts to the target. Each leg is independently invokable.

```
SD card deploy:
  ▸ flash kernel + DTB + rootfs to SD via dd / bmaptool
  ▸ ti-boot-chain validates artifact set before writing

eMMC deploy:
  ▸ ti-emmc-deploy: writes boot binaries to boot0 sector offsets
  ▸ offset table: tiboot3@0, tispl@2048, u-boot@6144 (sectors, 512B each)
  ▸ WARNING: wrong offsets brick the boot sequence silently

Firmware deploy (R5F/M4F):
  ▸ ti-remoteproc-firmware copies .elf to /lib/firmware/ on target
  ▸ echo start > /sys/class/remoteproc/remoteprocN/state

PRU deploy:
  ▸ ti-pru-programming copies .out to /lib/firmware/ on target
  ▸ binds PRU via device tree remoteproc entry
```

Skills: `ti-boot-chain`, `ti-emmc-deploy`, `ti-remoteproc-firmware`, `ti-pru-programming`

---

## Phase: VALIDATE

Purpose: confirm the deployed board behaves correctly. Read-only. Does not change board state.

Run `/ti-diagnostic` on the target to capture a health snapshot:
- Boot log: check for kernel panics, DT load errors, driver probe failures
- GPIO state: verify pinmux matches intent (gpioinfo shows function, direction)
- Remoteproc state: `running` or error + trace buffer
- DRAM: available memory vs expected
- Console: confirm prompt is reachable

Autonomous validation is handled by agents (see `agents/`).

---

## Phase: PARTITION (K3-specific)

TI's K3 SoC family requires explicit resource partitioning when running Linux alongside R5F/M4F cores.

```
/ti-resource-partition
  ▸ invokes k3-respart-tool to assign DMA channels, ring accelerator rings,
    IRQ routers, and NAVSS resources to each core
  ▸ generates .rm-cfg.yaml config and corresponding DT fragments
  ▸ validates that Linux + R5F resource regions do not overlap
```

This phase has no NVIDIA equivalent. It is unique to K3 multi-core architecture.

Skills: `ti-resource-partition` (planned)

---

## Skill inventory

| Phase | Skill | Role |
|---|---|---|
| INIT | `ti-sdk-init` | validate SDK install, detect versions, write DERIVED profile fields |
| INIT | `ti-sdk-link-docs` | register TRM/datasheet/schematic paths in profile documents block |
| CUSTOMIZE | `ti-gpio-pinmux` | decode PADCONFIG, write AM625_IOPAD macros to DTS, test with libgpiod |
| CUSTOMIZE | `ti-dt-overlay` | apply/persist runtime DT overlay via configfs or extlinux.conf |
| CUSTOMIZE | `ti-yocto-custom-dt` | generate bbappend + DTS file, KERNEL_DEVICETREE append |
| CUSTOMIZE | `ti-custom-board-port` | scaffold new board DTS from reference, configure AM625_IOPAD macros |
| CUSTOMIZE | `ti-kernel-module` | cross-compile out-of-tree kernel module, generate bbappend |
| BUILD | `ti-yocto-build-setup` | host prerequisite check, oe-init-build-env, build image |
| BUILD | `ti-boot-chain` | verify all 4 boot artifacts present and version-consistent |
| DEPLOY | `ti-emmc-deploy` | flash eMMC boot0 sector with correct offsets, verify |
| DEPLOY | `ti-remoteproc-firmware` | load/stop/trace R5F or M4F firmware via remoteproc |
| DEPLOY | `ti-pru-programming` | load PRU firmware, test rpmsg channel, trace buffer |
| PARTITION | `ti-resource-partition` | k3-respart-tool: assign DMA/ring/IRQ resources per-core |
| VALIDATE | `ti-diagnostic` | read-only health snapshot: boot log, GPIO, remoteproc, DRAM |

---

## Workspace path convention

The workspace root is discovered at load time as the parent of `target-platform/`. Three optional override fields layer on top:

| Variable | Default | Override field |
|---|---|---|
| `<sdk.root_path>` | set in profile | `sdk.root_path` |
| `<source.yocto_workspace>` | `<workspace>/Source` | `source.yocto_workspace` |
| `<documents.root_path>` | `<workspace>/Documents` | `documents.root_path` |

`sdk.kernel_version` and `sdk.uboot_version` are auto-derived (`<DERIVED>`) by `ti-sdk-init` from the SDK directory structure. Re-run `ti-sdk-init` after installing a new SDK to refresh.

---

## Key differences from NVIDIA Jetson BSP workflow

| Aspect | TI K3 | NVIDIA Jetson |
|---|---|---|
| Build system | Yocto (Scarthgap/Kirkstone) | NVIDIA L4T `Linux_for_Tegra/` overlay |
| Boot binaries | tiboot3.bin + tispl.bin + u-boot.img (K3 5-stage) | CBoot + extlinux.conf |
| Multi-core | A53 + R5F/M4F + PRU-ICSS (heterogeneous) | Cortex-A + Cortex-R5 (homogeneous) |
| Resource partitioning | k3-respart-tool (required for multi-core) | Not applicable |
| Pinmux ground truth | AM625_IOPAD macros in kernel DTS | Pinmux XLSM spreadsheet |
| Industrial IO | PRU-ICSS (PROFINET/EtherCAT capable) | Not applicable |
| Security | HS-FS / HS-SE / GP (OTP-burned) | Jetson Secure Boot |
| Host OS | Ubuntu 22.04 (Yocto requirement) | Ubuntu 20.04 / 22.04 |

---

## References

- `../references/platform_template.yaml` — profile schema.
- `../references/sdk-versions.md` — component version matrix and SYSFW ABI constraints.
- `../context/k3-architecture.md` — K3 SoC domain and core map.
- `../context/boot-chain.md` — 5-stage boot sequence and binary locations.
- Per-skill `SKILL.md` files under `../skills/` for procedure detail.
