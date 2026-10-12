# Kbuild notes for SDK kernels

Example evidence: `Documentation/kbuild/modules.rst` in `ti-linux-kernel-6.18.51+git-ti`; SDK `Rules.make` and
`makerules/Makefile_linux` (AM62P SDK 12.02.00.01.01); tested 2026-10-12.

- Command (modules.rst): `make -C <path_to_kernel_dir> M=$PWD`; targets include `modules`, `modules_install`,
  `clean`, and single objects such as `foo.ko`. `INSTALL_MOD_PATH` prefixes the install location.
- Kbuild file: `obj-m := <module_name>.o`, in `Kbuild` or `Makefile` (Kbuild is preferred if both exist).
- "To build external modules, you must have a prebuilt kernel available that contains the configuration and
  header files used in the build." `modules_prepare` prepares a tree without building `Module.symvers`.
- Rules.make: `LINUXKERNEL_INSTALL_DIR:=$(shell ls -d $(TI_SDK_PATH)/board-support/ti-linux-kernel*)`;
  `ARCH`, `CROSS_COMPILE` are defined there. `makerules/Makefile_linux` `linux` target runs
  `defconfig ti_arm64_prune.config $(RT_FRAGMENT)` then `Image Image.gz` and `modules` in that tree.
- Test result: `scripts/build-module.sh` on the example module with the AM62P SDK toolchain produced
  `hello.ko` (ELF aarch64) and left the SDK kernel tree unchanged.
- Not tested: building against an SDK whose kernel tree is unbuilt (the script stops with instructions),
  `insmod` on a board.
