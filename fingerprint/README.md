# EgisTec EL721 fingerprint stack for Fedora 44

Fedora 44 ships libfprint 1.94.100, which has no EL721 platform driver.
This directory rebuilds that exact source with the driver from the
agcarbajo/ygecesefa Galaxy Tab S9 port, rebased to 1.94.100.

What is here:

- `libfprint/` — EL721 driver sources (`el721.c`, the QTEE bridge, wire
  helpers). From the Ubuntu port, LGPL-2.1+ / BSD-3-Clause; see `copyright`.
- `patches/0001-el721-platform-driver-1.94.100.patch` — the Ubuntu port's
  libfprint integration patch, with its meson hunks rebased from 1.94.7 to
  1.94.100. The C hunks applied unchanged.
- `quic-teec/` — the two Qualcomm TEE patches from the Ubuntu port.
- `build-libfprint-rpm.sh` — builds the RPM inside `fedora:44` aarch64:
  Fedora's libfprint-v1.94.100 tarball, the EL721 patch and sources,
  statically linked pinned QCBOR and quic-teec, then `rpmbuild` with
  release `100.gts9wifi1` so a plain install upgrades over Fedora's.

CI: `.github/workflows/fingerprint.yml` (arm64) publishes the RPMs plus
`SHA256SUMS`/`BUILD-METADATA.txt` to `libfprint-1.94.100-gts9wifi-1`.

```sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work \
  quay.io/fedora/fedora:44 bash /work/fingerprint/build-libfprint-rpm.sh
# -> out-fingerprint/libfprint-1.94.100-100.gts9wifi1.fc44.aarch64.rpm
```

Install the runtime package and lock it. fprintd and GNOME's fingerprint
UI then see a normal reader; no fprintd patch is needed for basic login.

```sh
sudo dnf install ./libfprint-1.94.100-100.gts9wifi1.fc44.aarch64.rpm
sudo dnf versionlock add libfprint
```

Not included yet:

- the secure-owner binary and boot supervisor that configure
  `sp_keymaster`/HwVault (the Ubuntu port's `gts9wifi-fingerprint-secure`
  and `el721-secure-owner.c`);
- the Android-runtime assembler that copies Samsung's signed TA, firmware
  and the SPU userspace from the tablet's own `vendor`/`system`/`apnhlos`
  partitions;
- calibration assets (`calib.dat`, `egoptbds.dat`) and PAM/authselect
  configuration.

The kernel half (egis_el721, qcomtee, spcom and the SPSS modules) is
already in the ported 7.2.0 kernel; nacht's issue 15 shows it stopping at
the TEE's `KEYMASTER_NOT_CONFIGURED` until the secure owner runs. No
proprietary blob is in this repository — everything comes from the
tablet's own partitions at install time.
