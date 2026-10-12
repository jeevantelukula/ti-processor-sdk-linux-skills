---
name: ti-pru
description: >
  Build and run PRU (Programmable Real-time Unit, PRU-ICSS / ICSSG PRU, RTU, TX_PRU) firmware on a TI
  board from Linux: gate on PRU presence in the device tree, build an SDK example with the PRU compiler,
  load it through remoteproc, and talk to it over RPMsg. Use when the user mentions PRU, PRU-ICSS, ICSSG,
  RTU, TX_PRU or real-time I/O firmware. Some SoCs (for example AM62P) have no PRU: the skill stops there.
---

# ti-pru

Linux loads PRU firmware through the same `remoteproc` sysfs interface as other cores (`ti-remoteproc`),
using the `pruss` and `pru_rproc` drivers. Whether a SoC has PRU cores at all is decided by its device tree.

## Docs (MCP)
Follow [../../context/mcp-usage.md](../../context/mcp-usage.md): pass `device=$TI_DOCS_DEVICE`, `os="linux"`,
`version=$TI_SDK_VERSION_DOCS` explicitly (empty `$TI_DOCS_DEVICE`: key from `$TI_KB` or `ti_processor_sdk_docs_list_variants`). If
`ti_processor_sdk_docs_list_versions(device)` lacks your version (the MCP lags new SDKs), use `version="latest"` and say so. Cite the doc
`path` you used. PRU docs matter only for devices whose DT has PRU cores (gate in Step 1 first): searches (e.g. AM62X, AM64X)
returned the PRU pages below; on a device without PRU they return unrelated pages.
- `ti_processor_sdk_docs_search(query="PRU Subsystem overview", ...)` -> `linux/Foundational_Components_PRU_Subsystem.html` (index)
- `query="Lab 4: How to Initialize the PRU"` -> `common/PRU-ICSS/PRU-Getting-Started-Labs_Lab4.html`, section "Initializing the PRU from Linux Core"
- `query="PRU remoteproc driver load procedure"` -> `.../PRU-ICSS/Linux_Drivers/RemoteProc.html`
- `query="PRU RPMsg rpmsg_pru character device"` -> `.../Linux_Drivers/RPMsg.html` (lists the supported SoCs)
Warning: the "RPMsg Quick Start Guide" and "PRU Hands-on Labs" pages are written around AM335x
(`am335x-pru0-fw`, BeagleBone Black); the Quick Start's supported-device list does not include AM62x (example of a mismatch). Use them
for concepts, take names and ids from your own board.

## Prerequisites
- `lib/ti-sdk-env.sh` exported `TI_SDK_ROOT`, `TI_SOC`, `TI_DOCS_DEVICE`, `TI_KB`, `TI_FACTS_JSON` (board DTB name, PRU instance list: read
  `$TI_KB`; if unset or missing, run skill `ti-generate-kb`).
- `dtc` on the host. PRU code generation tools (`clpru`): not in the SDK devkit (see Step 3).
- Board access as root over ssh for loading.

## Steps

1. Gate: does this device tree have PRU cores? (host, read-only)
   ```
   scripts/pru-gate.sh "$TI_SDK_ROOT"/board-support/built-images/dtb/ti/<board>.dtb     # or prebuilt-images/<platform>/<board>.dtb; or --live on the board
   ```
   No built DTB: compile the board DTS to /tmp as shown in `ti-remoteproc` Step 1.
   Exit 3 and "no PRU support" -> stop and tell the user this SoC has none. Example, checked on SDK 12.02 kernel DTS: AM62x SK (2 PRU) and AM64x EVM
   (2 ICSSG, each PRU/RTU/TX_PRU x2) pass; AM62P, AM62A, AM62D and AM62L exit 3. The script reuses `../ti-remoteproc/scripts/dt-cores.sh`
   and prints a NOTE when PRU nodes exist but none is `okay` (enable them in the board DTS first).
   A `status` other than `okay`, or an Ethernet node whose own `firmware-name` lists `ti-pruss/...-prueth-fw.elf`
   (e.g. seen on the AM64x EVM DTB, node `icssg1-eth`), means the board or another driver may own those cores.

2. Map PRU cores to remoteproc ids on the board (docs, Lab 4):
   ```
   ssh root@<board-ip> 'bash -s -- list' < ../ti-remoteproc/scripts/rproc.sh
   ```
   PRU instances have names like `<addr>.pru`, addr = parent base + unit address from Step 1 (e.g. AM62x DTS `pruss@30040000/pru@34000`
   is `30074000.pru`; the AM62X docs list `30074000.pru` / `30078000.pru`). Docs
   alternative: `grep -Isr pru /sys/kernel/debug/remoteproc/` and replace `pru` with `rtu` or `txpru` for
   RTU/TX_PRU cores on ICSSG devices. Ids depend on probe order, never assume them.

3. Get sources and compiler.
   - Sources: the PRU Software Support Package ships in some SDKs as `example-applications/pru-icss-<ver>/`
     (`ls "$TI_SDK_ROOT"/example-applications`). Seen: `pru-icss-6.5.0` in the AM335x SDK 12.02 (it holds `examples/am62x` and
     `examples/am64x`); the AM62P SDK 12.02 has none. If yours has none, get the package through the docs page "Getting Started with PRU
     Software Support Package" (`common/PRU-ICSS/Getting_Started_with_PSSP.html`). Examples in 6.5.0 (match `<soc-dir>` to your SoC with
     `ls .../examples`): `am62x`: `PRU_Halt`, `PRU_Direct_Connect0/1`, `PRU_MAC_Multiply_Accum`, `PRU_RPMsg_Echo_Interrupt0/1`,
     `PRU_Hardware_UART`; `am64x`: the same minus `PRU_Hardware_UART`, plus `RTU_*` and `TX_PRU_Halt`.
   - Compiler: the example Makefiles require `PRU_CGT` pointing to the TI PRU code generation tools (their comment: download from
     https://www.ti.com/tool/PRU-CGT or the CCS App Center; they also describe `PRU_CGT=/usr/share/ti/cgt-pru` for building on an Arm
     Linux target, with a `bin` symlink). The Makefiles call `$PRU_CGT/bin/clpru`. No SDK checked ships it (the AM335x SDK has only a
     license folder `licenses/x86_64/ti-cgt-pru-native`). If `clpru` is missing, ask the user to install it.

4. Build:
   ```
   export PRU_CGT=<path to ti-cgt-pru>
   cd "$TI_SDK_ROOT"/example-applications/pru-icss-<ver>/examples/<soc-dir>/<example> && make
   ```
   Output: `gen/<example>.out` (name = project directory name). `make clean` removes `gen/`.
   Not build-tested in this repo (no `clpru` installed on the verification host).

5. Deploy and start (changes board state; confirm first). Docs (Lab 4): copy the `.out` to `/lib/firmware/pru/`
   on the target, then
   ```
   scp gen/<example>.out root@<board-ip>:/lib/firmware/pru/
   ssh root@<board-ip> 'bash -s -- load remoteprocN pru/<example>.out' < ../ti-remoteproc/scripts/rproc.sh
   ```
   `load` stops a running core first; docs say PRUs must be stopped before new firmware is loaded. The firmware
   path is relative to `/lib/firmware`.

6. RPMsg (only if the firmware has an RPMsg resource table, as the `PRU_RPMsg_Echo_*` examples do): the
   `rpmsg_pru` interface module creates a character device you can write to and read from (docs, RPMsg page).
   Device node names for AM62x/AM64x: check docs query `PRU RPMsg rpmsg_pru character device` and
   `ls /dev/rpmsg*` after the load; do not assume `/dev/rpmsg_pru30` (that name is from the AM335x guide).

## Verify
- `rproc.sh list`: the PRU instance shows `running` and the firmware path you set.
- `dmesg | tail`: remoteproc messages for that instance (same format as in `ti-remoteproc` Verify).
- Echo example: write a string to the rpmsg device and read it back (docs: the demo firmware echoes messages).

## Troubleshooting (docs and observed)
- Gate exits 3: no PRU in the DT. Do not look for PRU firmware on that board.
- Docs RPMsg Quick Start (AM335x): building `TI PRUSS remoteproc support` and `PRU RPMsg Communication driver`
  into the kernel (`y`) made boot hang and PRU loading fail; keep them modules (`m`). On K3 SDK kernels the
  docs state remoteproc and rpmsg modules are enabled by default.
- `make` stops with "PRU_CGT environment variable is not set": export it as in Step 4.
- e.g. CCS cannot see the PRU on AM62x (Lab 4): docs say to use the `AM62` target configuration instead of `AM62_SK_EVM`.
- Firmware not found at start: the path written to `firmware` is relative to `/lib/firmware`.
See `references/pru-build-and-examples.md` for the Makefile details.
