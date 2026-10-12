# PRU example build details

Evidence: `example-applications/pru-icss-6.5.0` in SDK `ti-processor-sdk-linux-rt-am335x-evm-12.02.00.01.01` (re-read
2026-10-12; example from that package, yours may be another version); docs (device=AM62X / AM64X). SoC-specific names below
(`am62x`, `AM62x_PRU0_intc_rscTbl.cmd`) belong to the AM62x example; other SoC directories use their own.

## Layout of the support package
`examples/<soc>` (am243x, am335x, am437x, am572x, am62x, am64x, am65x, j721e, k2g), `include/<soc>`,
`lib/` (RPMsg library `rpmsg_lib.lib`), `labs/`, `pru_cape/`, `Makefile`. `examples/am62x/ReadMe.txt`
describes each example; `Release_Notes.txt` is at the package root.

## What an example Makefile does (e.g. `examples/am62x/PRU_RPMsg_Echo_Interrupt0/Makefile`)
- Fails with an error block unless `PRU_CGT` is set.
- `PROJ_NAME` = the directory name; output `gen/<PROJ_NAME>.out` and `gen/<PROJ_NAME>.map`.
- Compile (e.g. the am62x one): `$PRU_CGT/bin/clpru ... -v3 -O2 --endian=little --hardware_mac=on` with include paths
  `../../../include` and `../../../include/am62x`.
- Link (e.g. am62x): `clpru ... -z`, linker command file `AM62x_PRU0_intc_rscTbl.cmd` (INTC map and resource table
  placement), library `../../../lib/rpmsg_lib.lib` and `libc.a`; stack and heap `0x100`.
- The example directory holds `main.c`, `resource_table.h` (vring and RPMsg feature definitions) and `intc_map_0.h`
  (interrupt mapping; docs: INTC configuration is passed to the Linux driver via the resource table).
Docs: resource table and INTC configuration pages are under the PRU Subsystem index, "Firmware Development".

## Loading on the target (docs, Lab 4 and RemoteProc page)
The driver checks that the file named in `firmware` exists under `/lib/firmware`, parses the
`.resource_table` section, sets up vrings and the PRUSS INTC mapping, copies code to the PRU instruction RAM
and the resource table to data RAM, then starts the core.
