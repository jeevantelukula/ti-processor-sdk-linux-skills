# Known Issues — SDK 12.x (Scarthgap)

Known bugs, workarounds, and SDK-specific behaviors for TI Processor SDK Linux 12.x.

**SDK version:** 12.01.00.05.03 and earlier in the 12.x series
**Kernel:** 6.18.38-ti
**U-Boot:** 2025.01-ti
**Yocto:** Scarthgap (5.0)

---

## Boot Issues

### SYSFW-001: ABI mismatch silent failure on eMMC reflash
**Symptom:** Board boots from SD, fails silently from eMMC after partial reflash.
**Root cause:** `tiboot3.bin` and `tispl.bin` from different SDK releases have incompatible SYSFW ABI.
**Workaround:** Always reflash all three binaries (`tiboot3.bin`, `tispl.bin`, `u-boot.img`) as a set from the same SDK release. Never mix binaries across releases.
**Verification:** `strings tiboot3.bin | grep SDK` and `strings tispl.bin | grep SDK` must show the same version.

### BOOT-002: AM625 HS-FS tiboot3.bin required for SK-AM62x Rev E3
**Symptom:** Board hangs at ROM stage with no SPL output on Rev E3 boards.
**Root cause:** SK-AM62x Rev E3 has HS-FS OTP burn. Using GP tiboot3.bin causes silent ROM authentication failure.
**Workaround:** Use `tiboot3-am62xx-gp.bin` for GP boards, `tiboot3-am62xx-hs-fs.bin` for HS-FS boards. SDK ships both — check `board.security_mode` in your profile.

---

## GPIO / Pinmux Issues

### GPIO-001: gpiochip numbers not stable across boots
**Symptom:** `gpioget gpiochip0 51=0` works on some boots but not others.
**Root cause:** Kernel assigns gpiochip numbers in probe order, which varies by driver init.
**Workaround:** Use chip-by-label: `gpioget $(gpiodetect | grep "GPIO0" | cut -d' ' -f1) 51=0`. Never hardcode gpiochipN in scripts.

### GPIO-002: MCU domain GPIO not accessible from Linux by default
**Symptom:** MCU_GPIO0 pins not visible in gpioinfo output.
**Root cause:** MCU domain GPIO controller driver not probed on some SDK configurations.
**Workaround:** Verify `mcu_gpio0` node is enabled in the board DTS. Check `dmesg | grep mcu_gpio`.

### GPIO-003: Missing PIN_INPUT on I2C SDA/SCL reconfigured as GPIO
**Symptom:** I2C lines configured as GPIO input always read 0.
**Root cause:** I2C pads are open-drain bidirectional. When reconfigured as GPIO input, RXACTIVE (PIN_INPUT) must be set.
**Workaround:** Use `AM625_IOPAD(offset, PIN_INPUT | MUX_MODE7)` not `PIN_OUTPUT` for any input-capable pad.

---

## Remoteproc / M4F Issues

### RPROC-001: MCU R5F firmware file name case sensitivity
**Symptom:** `echo start > .../state` returns "No such file" for firmware.
**Root cause:** Firmware file name in `/lib/firmware/` must match exactly what the DTS `firmware-name` property specifies. Case-sensitive.
**Workaround:** Check DTS: `grep firmware-name /proc/device-tree/.../mcu_r5fss*/`. Copy file with exact matching name.

### RPROC-002: RPMsg device not appearing after R5F start
**Symptom:** `echo start` succeeds (state = running) but no `/dev/rpmsgN` device appears.
**Root cause:** Resource table in firmware ELF does not include RPMsg vring entries.
**Workaround:** Firmware must include a `resource_table` with VDEV entries for RPMsg. Use TI IPC SDK example firmwares as reference.

---

## Yocto Build Issues

### YOCTO-001: BB_DANGLINGAPPENDS on Scarthgap for linux-ti-staging
**Symptom:** `bitbake` fails: `ERROR: No recipes in default applicable to variable in BB_DANGLINGAPPENDS_ABORTS`.
**Root cause:** Custom `linux-ti-staging_6.1.bbappend` does not match Scarthgap recipe name `linux-ti-staging_6.12.bbappend`.
**Workaround:** Rename bbappend to `linux-ti-staging_%.bbappend` (use `%` wildcard to match any version).

### YOCTO-002: Ubuntu 24.04 host not supported
**Symptom:** Various bitbake, Python, or toolchain errors on Ubuntu 24.04 hosts.
**Root cause:** SDK 12.x Yocto builds are only validated on Ubuntu 22.04 LTS.
**Workaround:** Use Ubuntu 22.04. Running in a Docker container with Ubuntu 22.04 base image is an acceptable alternative.

### YOCTO-003: KERNEL_DEVICETREE append syntax changed in Scarthgap
**Symptom:** Custom DTB not included in Yocto image.
**Root cause:** In Kirkstone the syntax was `KERNEL_DEVICETREE += "..."`. In Scarthgap it uses `:append`.
**Workaround:** Use `KERNEL_DEVICETREE:append = " ti/k3-am625-sk-my-overlay.dtb"` (note leading space). See `context/yocto-workflow.md`.

---

## eMMC Issues

### EMMC-001: eMMC boot partition sector offsets
**Symptom:** Board fails to boot from eMMC after flash.
**Root cause:** Wrong byte offsets when writing to `mmcblk0boot0`.
**Verified offsets (SDK 12.x):**
```
tiboot3.bin:  dd ... seek=0      (sector 0,    byte 0)
tispl.bin:    dd ... seek=2048   (sector 2048, byte 1048576)
u-boot.img:   dd ... seek=6144  (sector 6144, byte 3145728)
```
Always use `conv=fsync` to ensure writes complete before power-cycle.

---

## Silicon Errata

See AM625 Errata (SPRZ463) for silicon-level bugs. Most relevant to SDK users:
- **ERRATA_i2311:** PCIe EP mode: link training may fail on first attempt. Retry in firmware.
- **ERRATA_i2161:** USB3: SuperSpeed may not enumerate after warm reset. Cold power cycle required.

Full errata document: https://www.ti.com/lit/er/sprz463/sprz463.pdf
