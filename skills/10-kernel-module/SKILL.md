---
name: kernel-module
version: "1.0.0"
description: >
  Cross-compile an out-of-tree Linux kernel module for AM62x using the TI SDK
  devkit toolchain. Covers Makefile template, kernel headers, loading with
  insmod/modprobe, and adding to Yocto for permanent inclusion.
tags: [kernel-module, out-of-tree, cross-compile, driver, insmod, yocto, am62x]
related_context:
  - context/sdk-structure.md
  - context/yocto-workflow.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Users_Guide.html
---

# Skill: Out-of-Tree Kernel Module

## Overview

Out-of-tree kernel modules are compiled against the running kernel's headers
and inserted with `insmod` or `modprobe`. The TI SDK devkit provides the
necessary toolchain and kernel headers. The kernel source tree is needed
for the full build infrastructure (Kbuild).

## Prerequisites

- SDK devkit toolchain sourced
- Kernel source at `board-support/ti-linux-kernel-*/`
- Target board running the matching SDK kernel (same version as the source)

## Step 1: Prepare Kernel Source for Module Build

The kernel source must be "prepared" (`.config` + `Module.symvers`) before
building external modules:

```bash
# Source the SDK devkit
source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux

KERNEL_DIR="<sdk-path>/board-support/ti-linux-kernel-*"

cd ${KERNEL_DIR}

# Configure kernel (use the default TI config for AM62x)
make ARCH=arm64 CROSS_COMPILE="${CROSS_COMPILE}" ti_arm64_prune.config

# Prepare kernel for external module builds
make ARCH=arm64 CROSS_COMPILE="${CROSS_COMPILE}" modules_prepare

# Verify: Module.symvers should now exist
ls Module.symvers
```

Alternatively, use the Yocto-built kernel source directory
(`arago-tmp-default-glibc/work/am62xx_evm-oe-linux/linux-ti-staging/.../`) which
is already prepared.

## Step 2: Create the Module Source

```bash
mkdir -p ~/my-module && cd ~/my-module
```

Create `my_module.c`:
```c
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Your Name");
MODULE_DESCRIPTION("Example out-of-tree module for AM62x");
MODULE_VERSION("1.0");

static int __init my_module_init(void)
{
    pr_info("my_module: loaded on AM62x\n");
    return 0;
}

static void __exit my_module_exit(void)
{
    pr_info("my_module: unloaded\n");
}

module_init(my_module_init);
module_exit(my_module_exit);
```

Create `Makefile`:
```makefile
# Kernel build system Makefile for external modules
# Usage: make KERNEL_DIR=/path/to/kernel/source

obj-m += my_module.o

# For a module with multiple source files:
# my_module-y := my_module_main.o my_module_helper.o
# obj-m += my_module.o

KERNEL_DIR ?= $(HOME)/ti-processor-sdk-linux-am62xx-evm-*/board-support/ti-linux-kernel-*

all:
	$(MAKE) -C $(KERNEL_DIR) \
		ARCH=arm64 \
		CROSS_COMPILE=$(CROSS_COMPILE) \
		M=$(PWD) \
		modules

clean:
	$(MAKE) -C $(KERNEL_DIR) \
		ARCH=arm64 \
		CROSS_COMPILE=$(CROSS_COMPILE) \
		M=$(PWD) \
		clean

install:
	$(MAKE) -C $(KERNEL_DIR) \
		ARCH=arm64 \
		CROSS_COMPILE=$(CROSS_COMPILE) \
		M=$(PWD) \
		INSTALL_MOD_PATH=$(DESTDIR) \
		modules_install
```

## Step 3: Build the Module

```bash
source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux

KERNEL_DIR="<sdk-path>/board-support/ti-linux-kernel-*"

cd ~/my-module
make KERNEL_DIR="${KERNEL_DIR}"

# Output:
ls *.ko
# → my_module.ko

# Verify it is an aarch64 kernel module
file my_module.ko
# → ELF 64-bit LSB relocatable, ARM aarch64
modinfo my_module.ko
```

## Step 4: Transfer and Load on Target

```bash
# Copy module to target
scp my_module.ko root@<board-ip>:/tmp/

# On target:
# Load module
insmod /tmp/my_module.ko

# Verify loaded
lsmod | grep my_module
# → my_module   XXXX  0

# Check kernel log
dmesg | tail -5
# → my_module: loaded on AM62x

# Unload
rmmod my_module
```

## Step 5: Make Module Persistent (install to correct path)

```bash
# Install to the kernel modules directory on target
scp my_module.ko \
    root@<board-ip>:/lib/modules/$(uname -r)/extra/

# On target: update module database
depmod -a

# Now load by name (no path needed):
modprobe my_module

# Load at boot: add to /etc/modules
echo "my_module" >> /etc/modules
```

## Adding Module to Yocto Build

Create a Yocto recipe for the module:

```bash
mkdir -p sources/meta-myboard/recipes-kernel/my-module/files/
cp my_module.c Makefile sources/meta-myboard/recipes-kernel/my-module/files/

cat > sources/meta-myboard/recipes-kernel/my-module/my-module_1.0.bb << 'EOF'
SUMMARY = "My out-of-tree kernel module"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://my_module.c;beginline=1;endline=1;md5=..."

inherit module

SRC_URI = " \
    file://my_module.c \
    file://Makefile \
"

S = "${WORKDIR}"

# MACHINE_ESSENTIAL_EXTRA_RRECOMMENDS += "my-module"  # auto-load at boot
EOF
```

The `inherit module` class handles cross-compilation automatically.

## Module Signing for HS Devices

On HS-SE secured boards, kernel modules must be signed. The Yocto `module` class
handles this automatically when `CONFIG_MODULE_SIG=y` is set.

For manual signing:
```bash
# Generate a signing key (or use the kernel's built-in key):
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
    -subj "/CN=Module Sign/" \
    -keyout signing_key.pem -out signing_cert.pem

# Sign the module
${KERNEL_DIR}/scripts/sign-file sha256 \
    signing_key.pem signing_cert.pem \
    my_module.ko
```

For GP and HS-FS boards (default SK-AM62x), signing is not required.

## Troubleshooting

### "version magic mismatch" when loading module
- **Cause:** Module built against different kernel version than running kernel.
- **Fix:** Build module against the exact kernel source that matches `uname -r` on target.
  On target: `uname -r` should match the version in the kernel source directory name.

### Module loads but device doesn't appear
- **Cause:** Module loaded but device tree node is missing or `status = "disabled"`.
- **Fix:** Add/enable the DT node for the device (see skill 02 or 08).

### `Module.symvers` missing / "modules_prepare failed"
- **Cause:** Kernel source not configured before building external module.
- **Fix:** Run `make modules_prepare` in the kernel source (Step 1).

## Reference

- SDK Kernel guide: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_Kernel_Users_Guide.html
- Kernel external modules: `Documentation/kbuild/modules.rst` in kernel source
