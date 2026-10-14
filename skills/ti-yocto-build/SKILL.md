---
name: ti-yocto-build
description: >
  Set up and run the TI Processor SDK Yocto (Arago / OpenEmbedded) build on a Linux host with oe-layersetup
  and bitbake: check host prerequisites, pick the layer configuration file for the SDK release, build
  tisdk-default-image and related targets, rebuild one recipe, and find the output images. Use when the
  user wants a full SDK image from source, an RT or Jailhouse image, a single recipe rebuild, or hits a
  Yocto build setup problem. Customising the device tree inside Yocto is ti-yocto-custom-dt.
---

# ti-yocto-build

TI documents one flow: clone `oe-layersetup`, generate the layers from a release configuration file, source
the build environment, run `bitbake` for a machine and image target.

## Docs (MCP)
Follow [references/mcp-usage.md](references/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`,
`version=$TI_SDK_VERSION_DOCS` if `ti_processor_sdk_docs_list_versions` has it, else `latest`. The MCP lags
the SDK and the layer configuration page is release specific, so say which release you read; the SDK
(`Rules.make`, `yocto-build/` if shipped) wins over the page. Cite the page path you used.
- `ti_processor_sdk_docs_search(query="Building the SDK with Yocto oe-layersetup", device=$TI_DOCS_DEVICE, os="linux", version=...)` -> `linux/Overview_Building_the_SDK.html`
  (host packages, build steps, targets, recipes)
- `query="Yocto Layer Configuration oe-layersetup config files"` -> a device-specific page named
  `Release_Specific_Yocto_layer_Configuration.html` (use the path the search returns; it says which
  `configs/processor-sdk/...` file builds which machine)
- `query="Steps to Run Yocto Builds inside Container"` (container alternative linked from the first page)
- `query="Release Notes"` -> release-specific notes for the SDK you target

## Prerequisites
- Paths here are relative to this skill's directory. Shell variables do not persist between commands: run
  `source scripts/ti-sdk-env.sh >/dev/null &&` in the same command as anything that uses `$TI_*` (the
  bundled scripts load it themselves).
- `scripts/ti-sdk-env.sh` exported `TI_DOCS_DEVICE`; the machine name is `YOCTO_MACHINE` in the SDK `Rules.make`
  (`PLATFORM` if it is absent: an ADAS SDK checked defines only `PLATFORM`). `$TI_KB` (run `ti-generate-kb`
  if unset) records both. Docs list the supported `MACHINE` values per device.
- Host that passes `scripts/check-host.sh <build-dir>` (OS, `/bin/sh`, packages, locale, RAM/swap, disk).
  The docs recommend Ubuntu 22.04, `bash` as `/bin/sh`, a ~16 GB swap file on hosts with less than 32 GB RAM,
  and about 750 GB of disk for `tisdk-default-image` including Chromium.
- Network access to git.ti.com and every host named in the chosen config file (example from the 12.01 config
  in a local oe-layersetup clone: git.openembedded.org, git.yoctoproject.org, github.com, code.qt.io). Proxy: docs page "Working Behind a Network Proxy".

## Steps
1. Check the host: `scripts/check-host.sh /path/to/build/parent`. Fix every FAIL first.
2. Get oe-layersetup (docs):
   ```
   git clone https://git.ti.com/git/arago-project/oe-layersetup.git tisdk
   cd tisdk
   ls configs/processor-sdk
   ```
3. Choose `<oeconfig-file>`: take the file name from the docs "Yocto Layer Configuration" page for your device
   and release, and confirm it exists in `configs/processor-sdk` (the docs table pairs each file with its
   supported machines and purpose, for example a Chromium, SELinux or LUKS variant). Do not infer the
   file from the SDK version number alone: file names embed a release codename that is not derivable here.
4. Generate layers (this clones many repositories):
   ```
   ./oe-layertool-setup.sh -f configs/processor-sdk/<oeconfig-file>
   cd build
   . conf/setenv
   ```
5. Build (docs; hours, large disk use):
   ```
   MACHINE=<machine> bitbake -k tisdk-default-image
   ```
   Variants from the docs: RT image `MACHINE=<machine> ARAGO_RT_ENABLE=1 bitbake -k tisdk-default-image`;
   Jailhouse: `echo 'TI_EXTRAS="tie-jailhouse"' >> conf/local.conf`, then `bitbake -k tisdk-jailhouse-image`;
   other targets in the docs table: `tisdk-base-image`, `tisdk-thinlinux-image`, `tisdk-display-cluster-image`
   (needs `DISPLAY_CLUSTER_ENABLE="1"` in `conf/local.conf`), `meta-toolchain-arago-tisdk`
   (devkit), `mc:k3r5:meta-toolchain-arago` (R5 toolchain). Availability depends on the machine: read the table.
6. Single recipe (docs): `MACHINE=<machine> bitbake <recipe>`; work dir:
   `MACHINE=<machine> bitbake-getvar -r <recipe> WORKDIR --value`; force rebuild:
   `bitbake <recipe> --force -c compile` then `bitbake <recipe>`; clean: `bitbake <target> -c cleanall`
   (removes outputs, sstate and downloaded sources for it).

## Verify
- `bitbake` ends with no failed tasks (`-k` keeps going after errors: scroll back for `ERROR:`).
- Outputs under the `deploy-ti` directory: `images/<machine>/tisdk-default-image-<machine>.rootfs.tar.xz`
  and the generated `.wic` image (docs). Flash it with `ti-deploy-image`.
- `ls conf/` shows `local.conf` and `bblayers.conf` created by `oe-layertool-setup.sh`.

## Troubleshooting (docs; items marked * also checked on this repo's build host)
- *`/bin/sh` is dash: `sudo dpkg-reconfigure dash`, answer "No".
- `locale.Error: unsupported locale setting`: docs fix: `sudo locale-gen en_US.UTF-8`, then export
  `LC_ALL`, `LC_CTYPE`, `LC_NUMERIC`, `LANG`, `LANGUAGE` as `en_US.UTF-8` and `ulimit -n 4096`.
- Host crashes or runs out of memory during bitbake: docs say to set `BB_NUMBER_THREADS` and `PARALLEL_MAKE`
  in `conf/local.conf`, and to use a large swap file.
- Chromium makes the build long: docs say it can be removed by deleting the `meta-browser` layer from the
  oeconfig file before `oe-layertool-setup.sh`, but not if you want the TI Apps Launcher.
- Re-running the setup against changed checkouts: `oe-layertool-setup.sh -r` resets previous checkouts or
  local changes (from the script's own usage text). Other flags there: `-d <dldir>` download dir, `-b <basedir>`.
See `references/oe-layersetup.md` and `references/targets-and-outputs.md`.
