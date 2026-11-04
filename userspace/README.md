# gts9wifi-userspace

Noarch RPM with the Phase 1 userspace pieces from the Ubuntu port:

- Tab9 Extras GNOME Shell extension v6 (screen-lock/keyboard controls,
  floating on-screen keyboard button, FOD overlay is a separate phase)
- `gts9wifi-device-control` with charge_limit / charge_bypass entries
- charger udev permissions for fast_charge, charge_limit, charge_bypass
- NetworkManager dispatcher that disables Wi-Fi background scanning
- `gts9wifi-update ffmpeg`, which installs the rebuilt ffmpeg-free RPMs
  (v4l2m2m H.264/HEVC), verifies their SHA256SUMS, sets Firefox's
  `media.hardware-video-decoding.force-enabled` policy and version-locks them

Build (Fedora container):

```sh
mkdir -p ~/rpmbuild/SOURCES
mkdir -p /tmp/src/gts9wifi-userspace-0.3.0
cp -a userspace/tree/. /tmp/src/gts9wifi-userspace-0.3.0/
tar -C /tmp/src -czf ~/rpmbuild/SOURCES/gts9wifi-userspace-0.3.0.tar.gz gts9wifi-userspace-0.3.0
rpmbuild -bb userspace/gts9wifi-userspace.spec
```

Install:

```sh
sudo dnf install ./gts9wifi-userspace-0.3.0-1.fc44.noarch.rpm
```

The keyboard firmware is not included. Copy the verified V37 blob to
`/lib/firmware/keyboard_stm/stm32_gts9family.bin` only after the matching
kernel is installed.

## Updates

```sh
gts9wifi-update check
sudo gts9wifi-update userspace
sudo gts9wifi-update ffmpeg
sudo gts9wifi-update kernel --flash --reboot
sudo gts9wifi-update rollback
```

`ffmpeg` defaults to the `ffmpeg-8.1.3-gts9wifi-1` release; override with
`--tag` if the rebuilt codecs are published elsewhere. It installs only
the runtime `*-free` packages and leaves devel/debuginfo assets alone.

`kernel` without `--flash` only downloads and verifies the pair. With
`--flash` it backs up the four boot partitions and the running modules,
writes boot/init_boot/vendor_boot/dtbo, verifies the readback, then installs
the matching kernel RPM. It never writes vbmeta, persist, modemst or efs.
