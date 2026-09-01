---
name: sdk-setup
version: "1.0.0"
description: >
  Install and configure the TI Processor SDK for Linux. Verify the cross-compile
  toolchain (aarch64-oe-linux), set environment variables, and confirm the devkit
  is functional with a test cross-compile.
tags: [setup, toolchain, environment, cross-compile, devkit, am62x]
related_context:
  - context/sdk-structure.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview.html
  - https://www.ti.com/tool/download/PROCESSOR-SDK-LINUX-AM62X
---

# Skill: SDK Setup and Environment Check

## Overview

The Processor SDK ships as a self-extracting installer. After installation,
you source the devkit environment file to activate the cross-compile toolchain.
This skill verifies that the SDK is correctly installed and the toolchain works.

## Download

Get the latest SDK from:
https://www.ti.com/tool/download/PROCESSOR-SDK-LINUX-AM62X

Select: **Processor SDK Linux for AM62x** → click the installer link.
Current version: **12.01.00.05.03** (2026-07-31)

Multiple distributions available — each is a separate download:
- **Yocto** (default) — `ti-processor-sdk-linux-am62xx-evm-<ver>-Linux-x86-Install.bin`
- **Debian** (Armbian-based) — separate installer
- **Buildroot** — separate installer

## Installation

```bash
# Make installer executable
chmod +x ti-processor-sdk-linux-am62xx-evm-<ver>-Linux-x86-Install.bin

# Run installer (GUI mode if display available, else text mode)
./ti-processor-sdk-linux-am62xx-evm-<ver>-Linux-x86-Install.bin

# Text mode (no display):
./ti-processor-sdk-linux-am62xx-evm-<ver>-Linux-x86-Install.bin --mode text

# Silent install to specific directory:
./ti-processor-sdk-linux-am62xx-evm-<ver>-Linux-x86-Install.bin \
    --mode unattended \
    --prefix /opt/ti-processor-sdk-linux-am62xx-evm-<ver>
```

The SDK installs to the chosen prefix directory. Default is current directory.

## Environment Setup

```bash
# Source the devkit environment (run once per terminal session)
source <sdk-path>/linux-devkit/environment-setup-aarch64-oe-linux

# Verify key variables are set:
echo "CC:       ${CC}"
echo "CXX:      ${CXX}"
echo "AR:       ${AR}"
echo "SYSROOT:  ${SYSROOT}"
echo "OECORE_TARGET_ARCH: ${OECORE_TARGET_ARCH}"
```

Expected output:
```
CC:       aarch64-oe-linux-gcc -mcpu=cortex-a53 --sysroot=<sysroot-path>
CXX:      aarch64-oe-linux-g++ ...
SYSROOT:  <sdk-path>/linux-devkit/sysroots/aarch64-oe-linux
OECORE_TARGET_ARCH: aarch64
```

## Verify Toolchain

```bash
# Print compiler version
${CC} --version
# Expected: aarch64-oe-linux-gcc X.X.X ...

# Compile a hello world test program
cat > /tmp/hello.c << 'EOF'
#include <stdio.h>
int main() { printf("Hello from aarch64!\n"); return 0; }
EOF

${CC} -o /tmp/hello-aarch64 /tmp/hello.c

# Verify it is an aarch64 binary
file /tmp/hello-aarch64
# Expected: ELF 64-bit LSB executable, ARM aarch64

# Check linked libraries
${CC} -print-sysroot
readelf -d /tmp/hello-aarch64 | grep NEEDED
```

## Verify Kernel Headers

The devkit sysroot contains kernel headers needed for kernel module development:

```bash
ls ${SYSROOT}/usr/include/linux/
# Should list kernel UAPI headers (gpio.h, i2c.h, spi.h, etc.)

# Test kernel headers work
cat > /tmp/test-kheader.c << 'EOF'
#include <linux/gpio.h>
#include <linux/i2c.h>
int main() { return 0; }
EOF
${CC} -c /tmp/test-kheader.c -o /tmp/test-kheader.o
echo "Kernel headers OK"
```

## Environment Script (add to ~/.bashrc for convenience)

```bash
# Add to ~/.bashrc:
SDK_PATH="/path/to/ti-processor-sdk-linux-am62xx-evm-12.01.00.05.03"
alias ti-sdk-env="source ${SDK_PATH}/linux-devkit/environment-setup-aarch64-oe-linux"

# Or use the skills setup.sh:
alias ti-sdk="source /path/to/ti-processor-sdk-linux-skills/setup.sh"
```

## SDK Directory Quick Reference

```
<sdk-path>/
├── linux-devkit/environment-setup-aarch64-oe-linux   ← source this
├── linux-devkit/sysroots/aarch64-oe-linux/            ← target headers/libs
├── board-support/prebuilt-images/am62xx-evm/          ← boot binaries, DTBs
├── board-support/ti-linux-kernel-*/                   ← kernel source
├── filesystem/am62xx-evm/                             ← root filesystem tarballs
└── example-applications/                              ← PRU, benchmarks
```

## Validation

```bash
# Run automated check:
source setup.sh   # from ti-processor-sdk-linux-skills/

# Manual checks:
echo "SDK: ${PROCESSOR_SDK_LINUX}"
echo "CC: ${CC}"
${CC} --version | head -1
ls ${PROCESSOR_SDK_LINUX}/board-support/prebuilt-images/am62xx-evm/tiboot3.bin
# → file exists
```

## Troubleshooting

### "environment-setup-aarch64-oe-linux: No such file"
- SDK not installed or wrong path.
- Check: `find /opt ~/Downloads -name "environment-setup-aarch64-oe-linux" 2>/dev/null`

### CC is undefined after sourcing environment-setup
- Sourced with `sh` instead of `bash` or `source`. Must use `source` (bash built-in).
- Fix: `source .../environment-setup-aarch64-oe-linux` (not `sh .../environment-setup...`)

### Binary runs on host but "Exec format error" on target
- You compiled for host (x86) instead of target (aarch64).
- Verify `${CC}` starts with `aarch64-oe-linux-gcc`, not just `gcc`.

## Scripts

- `scripts/check-env.sh` — Automated environment validation with pass/fail output

## Reference

- Getting Started: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Overview.html
- SDK download: https://www.ti.com/tool/download/PROCESSOR-SDK-LINUX-AM62X
