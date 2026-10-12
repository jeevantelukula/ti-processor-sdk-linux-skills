# Targets and outputs

Source: docs page `linux/Overview_Building_the_SDK.html` (example read for the AM62P docs device, version
`latest`; the page is generic but its Platforms table is per device, so re-read it for `$TI_DOCS_DEVICE`). Output paths are
relative to the `deploy-ti` directory of the build.

| Target | Output | Description |
|---|---|---|
| tisdk-default-image | images/<machine>/tisdk-default-image-<machine>.rootfs.tar.xz | target filesystem |
| tisdk-display-cluster-image | images/<machine>/tisdk-display-cluster-image-<machine>.rootfs.tar.xz | display cluster filesystem |
| tisdk-jailhouse-image | images/<machine>/tisdk-jailhouse-image-<machine>.rootfs.tar.xz | Jailhouse filesystem |
| tisdk-base-image | images/<machine>/tisdk-base-image-<machine>.rootfs.tar.xz | minimal filesystem |
| tisdk-thinlinux-image | images/<machine>/tisdk-thinlinux-image-<machine>.rootfs.tar.xz | minimal, docker enabled |
| meta-toolchain-arago-tisdk | sdk/arago-<arago-version>-<architecture>.sh | devkit |
| mc:k3r5:meta-toolchain-arago | sdk/arago-<arago-version>-<architecture>.sh | K3 R5 bare-metal toolchain |

The docs also state: the wic image is generated in `deploy-ti`; recipe work directories are under
`arago-tmp-<toolchain>/work/<arch>/<recipe>/` (example given: `arago-tmp-default-glibc/work/aarch64-oe-linux/zlib`),
with IPKs in `deploy-ipks`; `opkg install <file>.ipk` installs a rebuilt package on the target.
The rest of the machine/target availability depends on the device; the docs "Platforms" table is per device.
