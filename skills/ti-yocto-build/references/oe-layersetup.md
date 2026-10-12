# oe-layersetup facts

Evidence: a local clone of `oe-layersetup` (`oe-layertool-setup.sh` usage text, `configs/processor-sdk/`,
README) and docs page `linux/Overview_Building_the_SDK.html` (example: AM62P docs device, version `latest`;
use `$TI_DOCS_DEVICE`).

## Script usage (from the script itself)
`oe-layertool-setup.sh [-i] [-f inputfile] [-o outputfile] [-d dldir] [-b basedir] [-h] [-r]`
- `-f` input file of repositories; `-i` interactive; `-o` save the interactive choices to a file;
  `-d` download directory (`DL_DIR`); `-b` base directory for the build (default: current directory);
  `-r` reset previous checkouts or local changes to pull remote branches.
- Input line format: `name,repo uri,branch,commit[,layers=layer1:layer2:...]`.
- A config file also sets `OECORELAYERCONF` and `OECORELOCALCONF` sample files, and can carry a message
  of the day and custom `local.conf` settings (README).

## Config files
`configs/processor-sdk/processor-sdk-<codename-or-branch>-<release>-config.txt` plus variants
(for example names containing `chromium`, `selinux`, `luks`, `nongpu`, `nonui`). The clone checked had files up to
a `12.01.00.05.03` release; a newer SDK may need a newer clone. The docs Yocto Layer Configuration page for the
device lists which file builds which machine.

## Docker alternative (docs)
TI publishes an Ubuntu 22.04 based image at `ghcr.io/texasinstruments` with the required packages; the
prerequisites listed on the docs "Steps to Run Yocto builds inside a Container" page apply first.
