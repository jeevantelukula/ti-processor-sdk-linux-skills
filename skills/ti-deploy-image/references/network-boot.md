# TFTP, NFS and U-Boot environment helpers

Evidence: `setup.sh` and `bin/setup-tftp.sh`, `setup-targetfs-nfs.sh`, `setup-uboot-env.sh`,
`setup-minicom.sh` in the example AM62P 12.02 SDK (read in full; yours will differ); docs pages
`linux/Foundational_Components/U-Boot/BG-Environment-K3.html` and
`linux/Foundational_Components/U-Boot/UG-Network-K3.html` (read for the example AM62P docs device, `latest` = 12.01).
All scripts are interactive, call `sudo`, and take at most one optional argument (platform;
default read from `PLATFORM?=` in Rules.make). They have no other flags.

| Script (under `<SDK>/bin/`) | What it does (from the code) |
|---|---|
| `setup-tftp.sh [platform]` | Asks for a TFTP root (default `/tftpboot`), creates it if missing, writes `/etc/xinetd.d/tftp` (service uses `/usr/sbin/in.tftpd`), copies from `board-support/prebuilt-images/<platform>/` the kernel `*Image-<prefix>*.bin`, all `*.dtb` and `*.dtbo` (into `<root>/ti` except on two 32-bit platforms the script special-cases), plus any `u-boot*.gph`, `skern*.bin`, `*firmware*.bin`. Records the root in `<SDK>/.tftproot`. Asks before overwriting. |
| `setup-targetfs-nfs.sh [platform]` | Extracts `filesystem/<platform>/tisdk*rootfs*` or `*default*` `.tar.xz` to a directory you choose (default `<SDK>/targetNFS`) with `sudo tar xJf`; writes `<SDK>/.targetfs`; appends the directory to `/etc/exports` with `rw,nohide,insecure,no_subtree_check,async,no_root_squash`; restarts `nfs-kernel-server`. Also attempts to edit `EXEC_DIR` and `DESTDIR` in Rules.make, which does not match the shipped file (see `sdcard.md`). |
| `setup-uboot-env.sh [platform]` | Asks host IP, kernel from TFTP or SD, rootfs from NFS or SD, then writes `setupBoard.minicom` and (optionally) runs `minicom` to type U-Boot commands: it starts with `env default -f -a` and `reset`, then sets `serverip`, `nfs_root`, `name_kern`, `bootcmd`, `args_net`, `get_kern_net`, `get_fdt_net`, `nfs_options`, `kern_boot`, `rootfs_boot`. It does not run `saveenv`. Needs the board on a serial port and `minicom`. |
| `setup-minicom.sh` | Writes `~/.minirc.dfl` (115200 8N1, no flow control; backs up the old file to `.minirc.dfl.old`). Default port `/dev/ttyS0` unless you enter another. |
| `setup-package-install.sh` | `apt-get install`s `xinetd tftpd nfs-kernel-server minicom build-essential libncurses5-dev autoconf automake dos2unix screen lrzsz lzop flex libssl-dev u-boot-tools` when missing, after asking. |

Run them via `<SDK>/setup.sh` (prompts for each in turn, host check first) or individually.
They change host state (`/etc/exports`, `/etc/xinetd.d/tftp`, services), so show the user what
they will do and let them run them in their own terminal.

## Persistent U-Boot variables: uEnv.txt (docs)

Since SDK 9.0 the board uses the default environment built into U-Boot; `saveenv` is not used.
Customise through a `uEnv.txt` file on the boot media (name from `${bootenvfile}`):

```
=> env export -t $loadaddr <list of variables>
=> fatwrite mmc ${mmcdev} ${loadaddr} ${bootenvfile} ${filesize}
```
`run envboot` reads it again at boot, from the MMC selected by `mmcdev`. Manual read:
`fatload mmc ${mmcdev} ${loadaddr} ${bootenvfile}` then `env import -t ${loadaddr} ${filesize}`.
Comment from the shipped SD image (example read on the live AM62P board): the file is evaluated
after `bootcmd` starts, so some variables such as `bootdelay` cannot be changed there.

If DHCP supplies a wrong TFTP server (docs): `setenv autoload no; dhcp; setenv serverip <ip>; tftp`.

## Boot U-Boot itself over Ethernet (docs)

The docs page for Ethernet boot says: build `tiboot3.bin` from the `*_r5_ethboot_defconfig`
and `tispl.bin`/`u-boot.img` from the `*_a53_ethboot_defconfig` of your board, and have the DHCP
server return the right filename per DHCP vendor-class identifier. Names and the ISC dhcpd
example are on that page: read it with `ti_processor_sdk_docs_read`, do not copy from memory.
