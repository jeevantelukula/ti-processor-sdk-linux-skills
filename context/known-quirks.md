# Known quirks (not derivable from the SDK sources)

Only facts that `lib/gen-sdk-facts.py` cannot read from the SDK. Each has evidence. Everything else
belongs in the generated knowledge base (`$TI_KB`, skill `ti-generate-kb`), never here.

## Device-manager R5F is not booted by Linux

Evidence: live AM62P5 SK, SDK 12.02.00.01.01, 2026-10-12: `/sys/class/remoteproc/remoteproc1` name
`78000000.r5f`, state `attached`, firmware `unknown`, while `remoteproc0` (`79000000.r5f`) is `running` with
`am62p-mcu-r5f0_0-fw`. Docs (`linux/Foundational_Components_IPC62px.html`, AM62PX, latest): the wakeup R5F runs
the device manager, is packed into `tispl.bin` and started by U-Boot R5 SPL; Linux only attaches. The DTS
node has `status = "okay"` and no `bootph-*` property, so the DTS alone does not show this. Rule: the
`firmware-name` of a wakeup-domain R5F node is not a file you load from `/lib/firmware`; to change it,
rebuild `tispl.bin` (docs page above).

## HSM M4F is reserved

Evidence: `k3-am62p-j722s-common-main.dtsi` node `hsm: remoteproc@43c00000`, `status = "reserved"`;
live board has no remoteproc instance for it. The generated KB flags this through the `reserved` column.
