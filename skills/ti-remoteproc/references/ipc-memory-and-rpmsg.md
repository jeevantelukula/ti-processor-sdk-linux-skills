# IPC memory, mailboxes and RPMsg

Example evidence (AM62P SDK 12.02.00.01.01): SDK kernel DTS (`ls $TI_KERNEL_SRC_DIR/arch/arm64/boot/dts/ti/*ipc-firmware*`), live AM62P board, docs pages "IPC for
AM62Px / AM62x / AM64x". All addresses and device names below are an example from AM62P SDK 12.02.00.01.01; yours will differ
(read your DTS and `$TI_KB`).

## Where the wiring lives
The SoC dtsi declares each remote core `status = "disabled"`. A board DTS includes
`k3-<family>-ti-ipc-firmware.dtsi` (for example `k3-am62p5-sk.dts` includes
`k3-am62p-ti-ipc-firmware.dtsi`), which adds reserved-memory pools, enables `mailbox0_clusterN`,
defines `mbox-*` sub-nodes and sets on each core `mboxes`, `memory-region` and `status = "okay"`.
Read that file in your SDK kernel instead of copying addresses; the docs say reservations change between
releases.

## Layout rules from the docs
- Each core gets a DMA pool (default first 1 MB: virtio/vring buffers) and a code/data pool.
- The DT pool addresses and sizes must match the firmware's linker map. Do not overlap carveouts.
- The resource table must be at the beginning of the core's external-memory region.
- e.g. the AM64x doc states default pools assume R5F subsystems in split mode.
Example observed on AM62P: vring0 at the DMA pool base (`0x9b800000`) and vring1 at `+0x4000`, each `0x3000` long.

## RPMsg devices observed on the example AM62P board (two cores, two virtio buses)
`/sys/bus/rpmsg/devices`: `virtio0.rpmsg_ctrl.0.0`, `virtio0.rpmsg_ns.53.53`,
`virtio0.rpmsg-client-sample.-1.13`, `virtio0.rpmsg_chrdev.-1.14` and the same for `virtio1`.
`/dev/rpmsg_ctrl0`, `/dev/rpmsg_ctrl1`, `/dev/rpmsg0`, `/dev/rpmsg1`. dmesg:
`virtio_rpmsg_bus virtio0: creating channel rpmsg_chrdev addr 0xe`.
The channel name announced by the firmware depends on the firmware (the SDK IPC echo example announced
`rpmsg-client-sample` and `rpmsg_chrdev`; the docs' examples show `ti.ipc4.ping-pong`).

## User-space and kernel examples (docs)
- ti-rpmsg-char library (git.ti.com `rpmsg/ti-rpmsg-char`), example `rpmsg_char_simple`; usage printed in
  the docs: `rpmsg_char_simple [-r <rproc_id>] [-n <num_msgs>] [-d <rpmsg_dev_name>] [-p <remote_endpt>]`.
  `rproc_id` values are the enumerations in the library's `include/rproc_id.h`.
- Kernel sample: `samples/rpmsg/rpmsg_client_sample.c`, built as a module by enabling
  `SAMPLE_RPMSG_CLIENT` (menuconfig: Kernel hacking > Sample kernel code), loaded with
  `modprobe rpmsg_client_sample count=10`.
- Firmware sources come from the separate MCU+ SDK (docs: use the same version number as the Linux SDK).
