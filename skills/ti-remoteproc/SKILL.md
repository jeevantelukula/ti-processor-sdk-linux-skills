---
name: ti-remoteproc
description: >
  Discover, load, reload and verify firmware on the remote processors (R5F, M4F, ...) of a TI K3 or
  Sitara board through the Linux remoteproc and RPMsg interfaces. Core list comes from the device tree
  and /sys/class/remoteproc, never from memory. Use when asked to run firmware on a secondary core,
  swap an IPC example, read a core's trace log, check rpmsg devices, or find out which cores exist
  and which one Linux may load. PRU cores are covered by ti-pru.
---

# ti-remoteproc

Linux loads firmware into a remote core when the kernel `remoteproc` driver is told to start it. Which cores
exist, what firmware name each requests, and which ones Linux may touch differ per SoC, so read them from
the SDK device tree and from the board.

## Docs (MCP)
Follow [../../context/mcp-usage.md](../../context/mcp-usage.md). Always pass `device=$TI_DOCS_DEVICE`,
`os="linux"`, and `version=$TI_SDK_VERSION_DOCS`. Never rely on the default device (the MCP default is not yours). If `$TI_DOCS_DEVICE` is empty take
the key from `$TI_KB` or `ti_processor_sdk_docs_list_variants`. If `ti_processor_sdk_docs_list_versions(device)` lacks your version (example, checked
12.02: the AM62PX docs list up to 12.01), use `version="latest"` and say the page may differ from the SDK. Cite the doc `path` you used.
Queries that worked (e.g. AM62PX, AM62X, AM64X each have a page; AM62LX returned none, matching its DT with no remote cores):
- `ti_processor_sdk_docs_search(query="IPC for <device> remoteproc firmware", ...)` returns the per-device
  page (for example `linux/Foundational_Components_IPC64x.html` for AM64X, `..._IPC62px.html` for AM62PX); read it for the
  firmware-name table, loading steps, DMA carveouts and rpmsg examples. No page: the SoC has no remote cores or the MCP lacks it.
- `query="Booting Remote Cores from Linux console/User space"`
- `query="RPMsg char driver ti-rpmsg-char rpmsg_char_simple"`
- `query="PRU remoteproc"` only to confirm a PRU question belongs to `ti-pru`.
If a doc page and the SDK or board disagree, report both (the docs examples are taken from other SDK releases).

## Prerequisites
- SDK installed; `lib/ti-sdk-env.sh` exported `TI_SDK_ROOT`, `TI_SOC`, `TI_DOCS_DEVICE`, `TI_KB`, `TI_FACTS_JSON`.
- For board steps: root ssh to the board (`ssh root@<board-ip>`), debugfs mounted for traces.
- `dtc` on the host for `scripts/dt-cores.sh` (the board image used for verification also had it).
- Per-device facts (default board DTB, core list, firmware names): read `$TI_KB` / `$TI_FACTS_JSON`; if unset or the file is
  missing, run skill `ti-generate-kb`. The DTB is the final authority for which cores exist (step 1).

## Steps

1. Which cores does this SoC's device tree define? (host, read-only)
   ```
   scripts/dt-cores.sh "$TI_SDK_ROOT"/board-support/built-images/dtb/ti/<board>.dtb
   ```
   Output: node, `compatible`, `firmware-name`, `status`. Pick `<board>.dtb` from `$TI_KB`, or list
   `"$TI_SDK_ROOT"/board-support/built-images/dtb/ti` or `"$TI_SDK_ROOT"/board-support/prebuilt-images/$TI_PLATFORM`. No built DTB: compile the
   board DTS (host, never inside the SDK): `K=$TI_KERNEL_SRC_DIR; D=$K/arch/arm64/boot/dts; cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp
   -I $D/ti -I $D -I $K/include $D/ti/<board>.dts | dtc -q -@ -I dts -O dtb -o /tmp/<board>.dtb -`. On the running board use
   `ssh root@<board-ip> 'bash -s -- --live' < scripts/dt-cores.sh`.
   Rows with `status` `reserved` or `disabled` are not usable. Rows that are not processors (for example an
   Ethernet node with its own `firmware-name` list) show up too: judge by `compatible`.
   Gate on the output: a core class exists only if a row of that class is present (`*-r5f`, `*-m4fss`, `*-dsp`, `*-pru|rtu|tx-pru`).
   The script prints `(no node with firmware-name ...)` when the SoC has none: stop and say so. Checked against SDK 12.02 kernel DTS:
   AM62P (R5F x2, HSM M4F reserved), AM62x (R5F, M4F, PRU), AM62A and AM62D (R5F x2, C7x DSP), AM64x (R5F x4, M4F, PRU/RTU/TX_PRU), AM62L (none).

2. Which instances did the kernel register? (board, read-only)
   ```
   ssh root@<board-ip> 'bash -s -- list' < scripts/rproc.sh
   ```
   Columns: id, `name` (DT unit address plus node name, for example `79000000.r5f`), `state`, `firmware`.
   Match `name` to the node address from step 1. When the node sits under a subsystem node with a different base, `name` uses the full
   bus address (parent base + unit address): DTS `pruss@30040000/pru@34000` appears as `30074000.pru`, the same value the AM62X docs list.

3. Read the state before touching anything.
   | state | meaning | action |
   |---|---|---|
   | `offline` | not started | can load |
   | `running` | Linux started it | can stop, change firmware, start |
   | `attached` | bootloader started it; Linux only attached | do not stop. `rproc.sh` refuses. Change it by rebuilding the boot image (see `references/boot-loaded-cores.md`) |
   Example from an AM62P board (SDK 12.02.00.01.01; yours will differ): MCU R5F `running`, WKUP R5F `attached` with firmware `unknown`.

4. Find the firmware the driver will request. It is the node's `firmware-name`, looked up under
   `/lib/firmware` (docs: "RemoteProc starts looking for firmware at /lib/firmware").
   ```
   ssh root@<board-ip> 'ls -l /lib/firmware | grep -- "-fw"'
   ```
   On SDK images these names are symlinks to example binaries (AM62P board: into `/usr/lib/firmware/ti-ipc/<dir>/`; the AM64x docs
   show `/lib/firmware/pdk-ipc/`). List the candidates: `ls /usr/lib/firmware/ti-ipc/*/` and trust what is on the image.

5. Load or reload (changes board state; confirm with the user first). Docs: the RemoteProc driver does not
   support graceful shutdown of R5 and DSP cores (e.g. AM64x page: R5 and M4 cores) and recommends rebooting the
   board when loading new binaries into them.
   ```
   ssh root@<board-ip> 'bash -s -- load remoteproc0 <firmware-name>' < scripts/rproc.sh
   ```
   `load` stops a running core, writes `firmware`, then writes `start` to `state`. To point a name at a
   different binary first: `ln -sf <new-binary> /lib/firmware/<firmware-name>` on the board.
   Manual equivalent (from the docs): `echo stop > .../state`, `ln -sf`, `echo start > .../state`.

## Verify
- `rproc.sh list`: state `running`.
- `dmesg | grep -E "remoteproc|virtio_rpmsg"` shows `Booting fw image <name>` and
  `remote processor <addr>.<node> is now up`, then `rpmsg host is online` and
  `creating channel ...` lines.
- `rproc.sh trace remoteproc0` prints the core's trace buffer (the TI IPC echo example prints its banner and
  the end points it waits on).
- `ls /sys/bus/rpmsg/devices /dev/rpmsg*`: `rpmsg_ctrl` and `rpmsg_chrdev` devices appear per virtio.
  For message round trips use the `rpmsg_char_simple` example (docs: the ti-rpmsg-char git repo) or the
  `rpmsg_client_sample` kernel module; see `references/ipc-memory-and-rpmsg.md`.

## Troubleshooting (all observed or stated in the docs)
- Expected core missing from `list`: in the SDK kernel the SoC dtsi can declare these nodes `status = "disabled"`
  and the board DTS enables them through `k3-<family>-ti-ipc-firmware.dtsi` (which also adds mailboxes and
  `memory-region`; `ls $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/*ipc-firmware*`). Run `dt-cores.sh --live` and compare the `status` column with the SDK DTB.
- Core missing from `list` but present in the DT with `status` `reserved`: reserved on purpose (example: the AM62P HSM M4F).
- `state` `attached`, firmware `unknown`: normal for a core the bootloader started; dmesg on the example AM62P board
  said `configured R5F for IPC-only mode` (example).
- dmesg `R5F core may have been powered on by a different host, programmed state (0) != actual state (1)`
  appeared (example) on the attached core of the AM62P board; the core still attached.
- `trace` fails: debugfs not mounted (`/sys/kernel/debug/remoteproc/<id>/` absent) or not root.
- Firmware loads but IPC does not come up: the DT carveouts must match the firmware linker map, and the
  resource table must sit at the start of the core's external-memory region (docs). Details in
  `references/ipc-memory-and-rpmsg.md`.
- Doc page names a firmware directory that does not exist on your image (e.g. the AM62Px page shows
  `ti-ipc/am62xx/`, the AM62P board had `ti-ipc/am62pxx/`): trust `ls /usr/lib/firmware/ti-ipc`.

## References
- `references/rproc-sysfs.md`: sysfs and debugfs layout, with the live-board output it was taken from.
- `references/ipc-memory-and-rpmsg.md`: carveouts, mailboxes, rpmsg devices.
- `references/boot-loaded-cores.md`: cores started by the bootloader (DM firmware) and how to replace them.
- `$TI_KB`: generated per-platform core table (skill `ti-generate-kb`).
