---
name: pru-programming
version: "1.0.0"
description: >
  Write, build, and load PRU-ICSS firmware on TI AM62x for real-time industrial IO.
  Covers PRU-ICSS architecture, device tree node, RPMsg from PRU to Linux, and
  the pru-icss example applications in the SDK.
tags: [pru, pru-icss, pruss, industrial-io, rpmsg, real-time, am62x]
related_context:
  - context/k3-architecture.md
references:
  - https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_PRU-ICSS.html
  - https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
---

# Skill: PRU-ICSS Programming

## Overview

The PRU-ICSS (Programmable Real-time Unit Industrial Communication Subsystem)
is TI's biggest differentiator for industrial applications. Each PRU is a 200 MHz
32-bit RISC core with direct I/O pin access (no kernel overhead), sub-microsecond
determinism, and its own GPIO ports.

AM62x contains one PRU-ICSS instance with two PRU cores (PRU0, PRU1).

**Primary use cases:**
- Industrial Ethernet (PROFINET, EtherNet/IP, EtherCAT) — via ICSSG (AM64x) or PRUETH
- Bit-bang serial protocols (RS-485, custom timing)
- Encoder/resolver interfaces
- Real-time GPIO toggling with <100 ns jitter

## PRU-ICSS Architecture on AM62x

```
PRU-ICSS
├── PRU0 (Programmable Real-time Core 0)
│   ├── 8 KB Instruction RAM
│   ├── 8 KB Data RAM
│   ├── 16 dedicated R30/R31 output/input pins
│   └── OCP master port (DDR access, RPMsg buffers)
├── PRU1 (Programmable Real-time Core 1)
│   └── (same as PRU0)
├── Shared Data RAM (12 KB, visible to both PRUs and A53)
├── INTC (Interrupt Controller — 64 system events)
└── IEP (Industrial Ethernet Peripheral — timer, sync)
```

The PRU R30 register directly drives output pins.
The PRU R31 register directly reads input pins.
A write to R30 bit N takes one clock cycle (~5 ns at 200 MHz).

## Device Tree Configuration

The PRU-ICSS node must be enabled in your board DTS:

```dts
/* From k3-am62-main.dtsi — PRU-ICSS base node */
&pruss0 {
    status = "okay";   /* Enable the PRUSS */
};

/* Enable individual PRU remoteproc instances */
&pru0_0 {
    status = "okay";
    firmware-name = "am62x-pru0_0-fw";   /* firmware file in /lib/firmware/ */
};

&pru0_1 {
    status = "okay";
    firmware-name = "am62x-pru0_1-fw";
};
```

For PRU GPIO (R30/R31 pins), add pinmux for the PRUSS_PRUn_GPO/GPI signals:

```dts
&main_pmx0 {
    pru0_gpio_pins: pru0-gpio-pins {
        pinctrl-single,pins = <
            /* PRU0 output pins — R30 register */
            AM625_IOPAD(0x00f4, PIN_OUTPUT, 5)   /* PRU0_GPO0 */
            AM625_IOPAD(0x00f8, PIN_OUTPUT, 5)   /* PRU0_GPO1 */
            /* PRU0 input pins — R31 register */
            AM625_IOPAD(0x010c, PIN_INPUT,  5)   /* PRU0_GPI4 */
        >;
    };
};
```

## Building PRU Firmware

TI provides PRU firmware examples in the SDK:

```bash
ls example-applications/pru-icss-*/
# PRU_Hardware_UART/
# PRU_RPMsg_Echo_Interrupt0/    ← most common starting point
# PRU_RPMsg_Echo_Interrupt1/
# PRU_Halt/
```

### Build PRU RPMsg Echo Example

```bash
# PRU firmware is cross-compiled for the PRU core (not aarch64)
# Requires pru-cgt (PRU Code Generation Tools) from TI

# Install pru-cgt (if not already):
# Download from: https://www.ti.com/tool/PRU-CGT

# Set PRU compiler path
export PRU_CGT=/path/to/pru-cgt

cd example-applications/pru-icss-*/PRU_RPMsg_Echo_Interrupt0

# Build PRU0 firmware
make PRU_CGT=${PRU_CGT} PRUN=0

# Output: gen/PRU_RPMsg_Echo_Interrupt0.out
```

### Build with GCC PRU (alternative, open-source)

The Linux kernel pru-gcc is available in some distributions:
```bash
# Ubuntu
sudo apt install gcc-pru binutils-pru

# Compile PRU firmware
pru-gcc -mmcu=am335x.pru0 -o pru0_echo.elf pru0_echo.c
```

## Loading PRU Firmware

```bash
# Copy firmware to /lib/firmware (name must match firmware-name in DTS)
cp PRU_RPMsg_Echo_Interrupt0.out /lib/firmware/am62x-pru0_0-fw

# The remoteproc driver starts PRU automatically at boot if DT node is okay.
# Or trigger manually:
echo "am62x-pru0_0-fw" > /sys/class/remoteproc/remoteproc1/firmware
echo start > /sys/class/remoteproc/remoteproc1/state

# Verify:
cat /sys/class/remoteproc/remoteproc1/state
# → "running"
```

**Note:** The remoteproc numbering: remoteproc0 = M4F, remoteproc1 = PRU0,
remoteproc2 = PRU1 (ordering may vary — check the `name` file to confirm).

## Communicating with PRU via RPMsg

PRU firmware using the RPMsg transport appears as `/dev/rpmsg*`:

```bash
# After PRU starts with RPMsg firmware:
ls /dev/rpmsg*
# → /dev/rpmsg0

# Send message to PRU and read echoed response:
echo "hello pru" > /dev/rpmsg0
cat /dev/rpmsg0   # PRU echoes back
```

## Writing PRU Firmware (C language example)

Minimal PRU firmware using RPMsg to communicate with Linux:

```c
/* pru0_rpmsg_echo.c */
#include <stdint.h>
#include <pru_cfg.h>
#include <pru_ctrl.h>
#include <rsc_types.h>
#include <pru_rpmsg.h>
#include <pru_virtio_ids.h>

/* Resource table — required for remoteproc loading */
#pragma DATA_SECTION(resourceTable, ".resource_table")
#pragma RETAIN(resourceTable)
struct my_resource_table {
    struct resource_table base;
    uint32_t offset[2];
    struct fw_rsc_vdev rpmsg_vdev;
    struct fw_rsc_vdev_vring rpmsg_vring0;
    struct fw_rsc_vdev_vring rpmsg_vring1;
} resourceTable = {
    { 1, 1, {0, 0} },        /* version, num, reserved */
    { offsetof(struct my_resource_table, rpmsg_vdev) },
    {   /* VDEV entry for RPMsg */
        TYPE_VDEV, VIRTIO_ID_RPMSG, 0,
        RPMSG_PRU_C0_FEATURES, 0, 0, 0, 2, {0, 0}
    },
    /* vring0: Linux→PRU */
    {PRU_RPMSG_VQ0_DA, 16, RPMSG_VQ0_SIZE, 0, 0},
    /* vring1: PRU→Linux */
    {PRU_RPMSG_VQ1_DA, 16, RPMSG_VQ1_SIZE, 0, 0},
};

void main(void) {
    struct pru_rpmsg_transport transport;
    uint16_t src, dst, len;
    uint8_t payload[RPMSG_MESSAGE_SIZE];

    /* Initialize RPMsg transport */
    pru_rpmsg_init(&transport, &resourceTable.rpmsg_vring0,
                   &resourceTable.rpmsg_vring1, SYSEVT_PRU0_TO_ARM,
                   SYSEVT_ARM_TO_PRU0);

    while (1) {
        /* Wait for and echo messages from Linux */
        if (pru_rpmsg_receive(&transport, &src, &dst, payload, &len) == PRU_RPMSG_SUCCESS)
            pru_rpmsg_send(&transport, dst, src, payload, len);
    }
}
```

## Shared Memory Between PRU and Linux

For high-throughput data (e.g., ADC samples, encoder counts) use shared DRAM
instead of RPMsg:

```c
/* In PRU firmware — write to DDR via OCP master */
volatile uint32_t *shared_buf = (volatile uint32_t *)0x9ca00000; /* DDR address */

void main(void) {
    uint32_t count = 0;
    while (1) {
        shared_buf[0] = count++;
        __delay_cycles(200);   /* 1 µs at 200 MHz */
    }
}
```

```c
/* In Linux userspace — map same physical address */
int fd = open("/dev/mem", O_RDWR | O_SYNC);
uint32_t *shared_buf = mmap(NULL, 4096, PROT_READ|PROT_WRITE,
                             MAP_SHARED, fd, 0x9ca00000);
printf("PRU counter: %u\n", shared_buf[0]);
```

The DDR address must be in the reserved memory region allocated for the PRU
in the device tree `reserved-memory` node.

## Validation

```bash
# PRU loaded and running:
cat /sys/class/remoteproc/remoteproc1/state
# → "running"

# RPMsg echo test:
echo "test" > /dev/rpmsg0
# No error = PRU received and echoed successfully

# PRU trace log (if debug prints enabled):
cat /sys/kernel/debug/remoteproc/remoteproc1/trace0
```

## Reference

- SDK PRU-ICSS doc: https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/latest/exports/docs/linux/Foundational_Components_PRU-ICSS.html
- PRU examples: `example-applications/pru-icss-*/`
- AM62x Academy PRU: https://dev.ti.com/tirex/explore/node?node=A__AM62-ACADEMY__uiYMDcq__LATEST
- PRU Reference Guide: https://www.ti.com/lit/ug/spruhj1i/spruhj1i.pdf
