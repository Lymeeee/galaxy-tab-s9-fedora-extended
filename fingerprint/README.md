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
- `build-runtime-rpm.sh` / `gts9wifi-fingerprint.spec` — the secure-start
  runtime: `gts9wifi-fingerprint-secure-owner`, the binder context manager,
  the two bionic LD_PRELOAD shims, the runtime/secure supervisors, the
  `/vendor` and apnhlos read-only mounts, the SPSS module list and the
  fprintd drop-in.

CI: `.github/workflows/fingerprint.yml` publishes the libfprint RPM to
`libfprint-1.94.100-gts9wifi-1`; `.github/workflows/fingerprint-runtime.yml`
publishes the runtime RPM to `gts9wifi-fingerprint-0.1.0-1`. Both are
arm64 and include `SHA256SUMS`/`BUILD-METADATA.txt`.

```sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work \
  quay.io/fedora/fedora:44 bash /work/fingerprint/build-libfprint-rpm.sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work \
  quay.io/fedora/fedora:44 bash /work/fingerprint/build-runtime-rpm.sh
# -> out-fingerprint/libfprint-1.94.100-100.gts9wifi1.fc44.aarch64.rpm
# -> out-fingerprint/gts9wifi-fingerprint-0.1.0-1.fc44.aarch64.rpm
```

Install both and lock them.  fprintd and GNOME then see a normal reader;
no fprintd patch is needed for basic login.

```sh
sudo dnf install ./libfprint-1.94.100-100.gts9wifi1.fc44.aarch64.rpm \
  ./gts9wifi-fingerprint-0.1.0-1.fc44.aarch64.rpm
sudo dnf versionlock add libfprint gts9wifi-fingerprint
```

The runtime units assemble the sensitive files on first boot and start
the SPU once per boot.  Enable them explicitly; the package never starts
the secure world on its own:

```sh
sudo systemctl enable --now gts9wifi-android-parts.service
sudo systemctl enable --now vendor.mount vendor-firmware_mnt.mount
sudo systemctl enable --now gts9wifi-fingerprint-runtime.service
sudo systemctl enable --now gts9wifi-fingerprint-secure.service
```

Not included yet:

- device calibration (`calib.dat`, `egoptbds.dat`): copy them into
  `/var/lib/gts9wifi/fingerprint/firmware/` (0600) once, from this
  tablet's own Android data/backup;
- PAM/authselect enablement and the GNOME overlay/presented bridge;
- hardware validation: the stack was built and inspected but has not run
  on the tablet yet.

The kernel half (egis_el721, qcomtee, spcom and the SPSS modules) is
already in the ported 7.2.0 kernel; nacht's issue 15 shows it stopping at
the TEE's `KEYMASTER_NOT_CONFIGURED` until the secure owner runs. No
proprietary blob is in this repository — everything comes from the
tablet's own partitions at install time.
