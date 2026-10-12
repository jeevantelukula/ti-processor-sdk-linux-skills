# remoteproc sysfs and debugfs layout

Example evidence: live AM62P5 SK board, kernel `6.18.51-ti-00952-gfff856a50d43-dirty`, read-only, 2026-10-12. Names, addresses and ids
below are an example from AM62P SDK 12.02.00.01.01; yours will differ.

## /sys/class/remoteproc/remoteprocN/
Files present: `coredump dev device firmware name power recovery state subsystem uevent` plus a
`rproc-virtio.N.auto` child when the firmware has a vdev. Observed values (example):
```
remoteproc0  name 79000000.r5f  state running   firmware am62p-mcu-r5f0_0-fw
remoteproc1  name 78000000.r5f  state attached  firmware unknown
recovery: disabled   coredump: disabled   (both instances)
```
- `name` = full bus address + node name of the DT node (e.g. `r5f@79000000` -> `79000000.r5f`). Docs show
  `5000000.m4fss` for an M4F and `30074000.pru` for a PRU (DTS `pruss@30040000/pru@34000`) on AM62x.
- Writing `stop` / `start` to `state`, and a file name to `firmware`, is the documented control path
  (docs: IPC62x / IPC62px / IPC64x "Booting Remote Cores from Linux console/User space").
- `/dev/remoteproc0`, `/dev/remoteproc1` also exist (char devices, root only).

## /sys/kernel/debug/remoteproc/remoteprocN/ (needs debugfs and root)
`carveout_memories coredump crash name recovery resource_table trace0`.
- `trace0`: the firmware's trace buffer; with the SDK echo example it printed
  `[mcu-r5f0-0] ... [IPC RPMSG ECHO] Version: REL.MCUSDK.K3.12.01.00.05+ ...` and
  `Remote Core waiting for messages at end point 13 / 14`.
- `resource_table`: parsed table; entry 0 `vdev` (ID 7, 2 vrings, 256 buffers each), entry 1 `trace`.
- `carveout_memories`: `vdev0vring0` at `0x9b800000` and `vdev0vring1` at `0x9b804000`, length `0x3000` each.

## Kernel pieces seen loaded on that board
`/proc/modules`: `ti_k3_r5_remoteproc`, `ti_k3_common`, `rpmsg_ctrl`, `rpmsg_char`.
For PRU cores the docs name different drivers (`pruss`, `pru_rproc`): see `ti-pru`.

## Core states
The kernel ABI doc (`Documentation/ABI/testing/sysfs-class-remoteproc` in the SDK kernel) lists `offline`,
`running`, `crashed` (and says unknown states are possible); `start` / `stop` are the writable values, and the
firmware name may only be changed while the core is stopped. `attached` is not in that list but was observed
on the WKUP R5F whose firmware was started before Linux booted. `recovery` `disabled` means a crashed core
stays crashed (useful for debugging).
