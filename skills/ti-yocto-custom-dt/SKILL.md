---
name: ti-yocto-custom-dt
description: >-
  Carry a custom device tree or overlay from the Processor SDK kernel tree into a Yocto
  (Arago/oe-layersetup) image build of the same SDK. Use after the DTS works with the SDK
  `make linux-dtbs` flow and the user wants it in a bitbake-built image; also to find which
  kernel recipe, machine config and DTB list the Yocto build uses. Unverified Yocto details are
  marked "check docs" instead of guessed.
---

# TI custom device tree in a Yocto build

Scope is small on purpose: facts below were read from the SDK, the docs MCP, and local clones of
`oe-layersetup`, `meta-ti` and `meta-tisdk` (read-only). Recipe edits that were not checked say so.

## Docs (MCP)
Follow [../../context/mcp-usage.md](../../context/mcp-usage.md). Always pass
`device=$TI_DOCS_DEVICE`, `os="linux"`, `version=$TI_SDK_VERSION_DOCS` (or `latest` if
`ti_processor_sdk_docs_list_versions` lacks it; say so) explicitly. The SDK and your layer checkout win over a page.
- `ti_processor_sdk_docs_search(query="Building the SDK with Yocto", ...)` then read `linux/Overview_Building_the_SDK.html`
  (oe-layersetup flow, MACHINE, build targets, recipe iteration commands).
- `query="Kernel Users Guide device tree dtbs"`, then read the hit and cite the path.
- `query="Yocto kernel recipe add patch device tree bbappend"` - if nothing usable comes back, tell the user the
  docs do not cover it and fall back to the Yocto Project manual.
- Layer set for your release: the `Release_Specific_Yocto_layer_Configuration.html` page the search returns
  names the `oeconfig` file (`ti-yocto-build` step 3).

## Prerequisites
- A DTS or DTSO that already builds and boots through the SDK flow (`make linux-dtbs`; see `ti-device-tree-overlay`
  and `ti-custom-board-port`). Do not debug DTS errors inside bitbake first.
- `source lib/ti-sdk-env.sh`. Machine name: `YOCTO_MACHINE` in the SDK `Rules.make` (else `PLATFORM`); `$TI_KB`
  (from `ti-generate-kb`) lists the board DTS and overlays the SDK builds.
- A Yocto host and layers per `ti-yocto-build`; this skill does not repeat them.

## Verified facts
- SDK side: `makerules/Makefile_linux-dtbs` builds `KERNEL_DEVICETREE`, derived from `KERNEL_DEVICETREE_PREFIX` in
  `Rules.make` plus the `dtb-$(CONFIG_ARCH_K3)` lines of the kernel `ti/Makefile`. That is the SDK makefile, not the recipe.
- Yocto side (example from a local `meta-ti` clone, branch `wrynose-next`, machine for AM62P; yours will differ):
  `meta-ti-bsp/conf/machine/<machine>.conf` sets both `KERNEL_DEVICETREE_PREFIX` and an explicit
  `KERNEL_DEVICETREE` list of `ti/*.dtb` and `ti/*.dtbo`. That prefix list was similar to, but not identical with,
  the SDK `Rules.make` prefix, so a DTB that builds in the SDK flow is not automatically in the Yocto image. Confirm in your checkout: `grep -rn KERNEL_DEVICETREE sources/*/conf/machine/<machine>.conf`.
- Kernel recipe names seen in that clone: `linux-ti-staging_<series>.bb` and `linux-ti-staging-rt_<series>.bb`
  under `meta-ti-bsp/recipes-kernel/linux/`; `meta-tisdk` adds `.bbappend` files for the same names that set
  `SRCREV` and `PR`. The series suffix follows your kernel (`$TI_KERNEL_VERSION`). Confirm:
  `find sources -name 'linux-ti-staging*'`.
- Inspect the real build (commands from the docs page): `MACHINE=<machine> bitbake-getvar -r <kernel-recipe> WORKDIR --value`;
  `MACHINE=<machine> bitbake <kernel-recipe> --force -c compile`; `-c cleanall` drops work, sstate and downloads.
- U-Boot only loads the base DTB and overlays present in the image `/boot/dtb/ti` (SD) or inside `fitImage`
  (see `ti-device-tree-overlay`).

## Steps
1. Finish and test the DTS in the SDK kernel tree (`$TI_KERNEL_SRC_DIR`). Record the exact files you added or changed
   (`.dts`, `.dtso`, includes, and the `ti/Makefile` lines).
2. Turn the change into a patch against the kernel git tree the recipe fetches (same version as `TI_KERNEL_VERSION`):
   `git -C $TI_KERNEL_SRC_DIR diff` if the SDK tree is a git checkout, else `diff -ruN` against a pristine copy.
   Keep the `ti/Makefile` `dtb-$(CONFIG_ARCH_K3) += <name>.dtb[o]` lines in the patch; they make the kernel build the file.
3. Add the patch to the kernel recipe from a layer of your own as a `.bbappend` of the recipe found above
   (`check docs: Yocto kernel recipe add patch device tree`; the exact append syntax is not verified here).
4. Make the machine install your DTB: the list is `KERNEL_DEVICETREE` in the machine conf found above. Extend it from
   your layer or `conf/local.conf` (standard Yocto override syntax, not verified here for this layer set) and check
   the result with `MACHINE=<machine> bitbake-getvar -r <kernel-recipe> KERNEL_DEVICETREE --value`.
5. Build: `MACHINE=<machine> bitbake <kernel-recipe>` then the image target.

## Verify
- Built DTB exists under `deploy-ti` for the machine, and `dtc -I dtb -O dts <dtb> | grep -n "<your node>"` shows it.
- Overlays: `fdtoverlay -i <base>.dtb -o /tmp/m.dtb <overlay>.dtbo` succeeds (the docs use `fdtoverlay -v -i ... -o ...`).
- On target after flashing: `cat /proc/device-tree/model`, `ls /boot/dtb/ti` and the node under `/proc/device-tree`.

## Troubleshooting (verified)
- `locale.Error: unsupported locale setting` during bitbake: docs say export `LC_ALL`, `LC_CTYPE`, `LC_NUMERIC`, `LANG`, `LANGUAGE`
  as `en_US.UTF-8` and `ulimit -n 4096`, then rebuild.
- DTB built but not on the image: it is not in `KERNEL_DEVICETREE` for the machine (step 4); the kernel Makefile alone is not enough.
- Everything else (append syntax, devtool usage): not verified; use the docs queries above.
