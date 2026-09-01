---
name: yocto-build-setup
version: "1.0.0"
description: >
  Set up a host machine to build TI Processor SDK Linux using Yocto/OpenEmbedded.
  Covers Ubuntu 22.04 requirements, required packages, 750 GB disk space, swap
  file, dash-to-bash reconfiguration, Docker container option, and proxy setup.
tags: [yocto, build, host-setup, ubuntu, bitbake, docker, am62x]
related_context:
  - context/yocto-workflow.md
  - context/sdk-structure.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html
---

# Skill: Yocto Build Host Setup

## Overview

Building the full TI Processor SDK with Yocto requires careful host configuration.
The most common failure modes are: wrong Ubuntu version, insufficient disk space,
wrong default shell, and locale errors. This skill covers all prerequisites.

## Host Requirements

| Requirement | Value | Notes |
|---|---|---|
| OS | Ubuntu 22.04 LTS (x86_64) | **Ubuntu 24.04 has permission errors — not supported** |
| RAM | 16 GB minimum | 32 GB recommended for parallel builds |
| Disk | 750 GB minimum | Full SDK with Chromium. 250 GB for tisdk-base-image |
| Swap | 16 GB if RAM < 32 GB | Prevents OOM kills on large package builds |
| Shell | bash (not dash) | Yocto build scripts use bash-specific syntax |

## Option A: Docker Container (Recommended — avoids Ubuntu version issues)

TI provides a pre-configured Ubuntu 22.04 Docker image:

```bash
# Pull TI's official Yocto build container
docker pull ghcr.io/texasinstruments/ubuntu-distro:22.04

# Start container with access to your workspace
docker run -it \
    -v /path/to/tisdk:/home/user/tisdk \
    -v /path/to/downloads:/home/user/downloads \
    ghcr.io/texasinstruments/ubuntu-distro:22.04 /bin/bash

# Inside container — proceed with normal build steps
```

For full Docker guide:
https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html#steps-to-run-yocto-builds-inside-container

## Option B: Native Ubuntu 22.04 Setup

### Step 1: Install Required Packages

```bash
sudo apt-get update
sudo apt-get -f -y install \
    git build-essential diffstat texinfo gawk chrpath socat doxygen \
    dos2unix python3 bison flex libssl-dev u-boot-tools mono-devel \
    mono-complete curl python3-distutils repo pseudo python3-sphinx \
    g++-multilib libc6-dev-i386 jq git-lfs pigz zstd liblz4-tool \
    cpio file lz4 debianutils iputils-ping python3-git python3-jinja2 \
    python3-subunit locales libacl1 unzip gcc python3-pip python3-pexpect \
    xz-utils wget
```

### Step 2: Configure Default Shell to bash

Ubuntu 22.04 uses `dash` as `/bin/sh` by default. Yocto scripts require `bash`.

```bash
sudo dpkg-reconfigure dash
# When prompted: select "No" to NOT use dash as system shell
```

Verify:
```bash
ls -la /bin/sh
# Should point to: /bin/bash  (not /bin/dash)
```

### Step 3: Set Locale

Missing or incorrect locale causes `bitbake` to fail with `locale.Error`:

```bash
sudo locale-gen en_US.UTF-8
sudo update-locale LANG=en_US.UTF-8

# Also export for current session:
export LC_ALL="en_US.UTF-8"
export LC_CTYPE="en_US.UTF-8"
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8
```

### Step 4: Create Swap File (if RAM < 32 GB)

Large packages (especially Chromium) require significant virtual memory:

```bash
# Create 16 GB swap file
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Step 5: Configure File Descriptor Limit

Yocto opens many files simultaneously:

```bash
ulimit -n 4096

# Make persistent:
echo "* soft nofile 4096" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 4096" | sudo tee -a /etc/security/limits.conf
```

## Cloning the Layer Setup

```bash
# Clone the oe-layersetup repository
git clone https://git.ti.com/git/arago-project/oe-layersetup.git tisdk
cd tisdk

# Find the correct config file for your SDK release
# For SDK 12.01.00.05.03 (AM62x), check:
ls configs/processor-sdk/ | grep am62

# Set up layers (replace <config-file> with the correct filename)
./oe-layertool-setup.sh -f configs/processor-sdk/<config-file>
```

## First Build

```bash
cd tisdk
source build/conf/setenv

# Build minimal image first to verify environment (faster, ~50 GB)
MACHINE=am62xx-evm bitbake tisdk-base-image

# Full image with Chromium (~750 GB disk, 4-8 hours first build)
MACHINE=am62xx-evm bitbake tisdk-default-image

# Linux kernel only (quick verification, ~30 min)
MACHINE=am62xx-evm bitbake linux-ti-staging
```

**Tip:** Remove Chromium to save ~200 GB disk and significant build time:
Edit the oeconfig file before running `oe-layertool-setup.sh` and remove the
`meta-browser` layer line. Do NOT do this if you want the TI Apps Launcher (OOB demo).

## Optimizing Build Performance

In `build/conf/local.conf`:

```bitbake
# Cap parallel tasks to avoid OOM (default = all CPU cores)
BB_NUMBER_THREADS = "8"
PARALLEL_MAKE = "-j8"

# Shared download cache (saves re-downloading on new workspaces)
DL_DIR = "/opt/yocto-downloads"

# Shared sstate cache (dramatically speeds up subsequent builds)
SSTATE_DIR = "/opt/yocto-sstate"
```

## Proxy Setup (Corporate Network)

If building behind a corporate proxy:

```bash
# In ~/.bashrc or before running bitbake:
export http_proxy="http://proxy.company.com:8080"
export https_proxy="http://proxy.company.com:8080"
export no_proxy="localhost,127.0.0.1,.company.com"

# Also add to bitbake config:
cat >> build/conf/local.conf << 'EOF'
BB_ENV_PASSTHROUGH_ADDITIONS += "http_proxy https_proxy no_proxy"
EOF
```

## Validation

```bash
# Verify shell is bash:
ls -la /bin/sh   # → bash

# Verify locale:
locale | grep LANG
# → LANG=en_US.UTF-8

# Verify disk space:
df -h .
# → Available: > 750G (for full build) or > 100G (for kernel-only)

# Verify bitbake available:
cd tisdk && source build/conf/setenv && bitbake --version
# → BitBake Build Tool Core version X.X.X

# Quick test build (kernel config only, ~2 min):
MACHINE=am62xx-evm bitbake linux-ti-staging -c configure
```

## Troubleshooting

### "Permission denied" errors during bitbake (Ubuntu 24 issue)
- **Cause:** Ubuntu 24.04 uses `pseudo` in a way incompatible with this SDK.
- **Fix:** Use Ubuntu 22.04 or the Docker container. Ubuntu 24 is not supported
  for SDK 12.x builds. See E2E thread 1387497 for details.

### "locale.Error: unsupported locale setting"
- **Fix:**
  ```bash
  export LC_ALL="en_US.UTF-8"
  export LC_CTYPE="en_US.UTF-8"
  export LANG=en_US.UTF-8
  ulimit -n 4096
  ```
  Then retry the build.

### Build crashes / OOM kill
- **Cause:** Insufficient RAM or swap for parallel compilation (Chromium, LLVM).
- **Fix:** Reduce `BB_NUMBER_THREADS` and `PARALLEL_MAKE` in `local.conf`.
  Add/increase swap file (Step 4).

### "SSTATE signature mismatch" or stale cache errors
- **Fix:** `bitbake <recipe> -c cleansstate` clears the shared state for that recipe.
  If persistent: `bitbake-layers clear-cache` or delete `sstate-cache/` directory.

### "dtb not found" in deploy directory after kernel build
- **Cause:** Custom DTB added to `KERNEL_DEVICETREE` but path is wrong.
- **Fix:** Check the path in `KERNEL_DEVICETREE` starts with `ti/` for AM62x DTS files.
  Run `MACHINE=am62xx-evm bitbake-getvar -r linux-ti-staging KERNEL_DEVICETREE --value`

## Scripts

- `scripts/check-host.sh` — Automated host prerequisite check and fix suggestions

## Reference

- Official build guide: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html
- E2E Yocto build error (Ubuntu 24): https://e2e.ti.com/support/processors-group/processors/f/processors-forum/1387497/
- Docker build guide: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview_Building_the_SDK.html#steps-to-run-yocto-builds-inside-container
