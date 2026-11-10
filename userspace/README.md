# gts9wifi-userspace

aarch64 RPM with the Phase 1 userspace pieces from the Ubuntu port:

- Tab9 Extras GNOME Shell extension v6 (screen-lock/keyboard controls,
  floating on-screen keyboard button, FOD overlay is a separate phase)
- `gts9wifi-device-control` with charge_limit / charge_bypass entries and a
  "Bypass when full" policy (100 % -> bypass, 95 % -> release)
- live battery telemetry (power, voltage, current, temperature) in Tab9 Settings
- charger udev permissions for fast_charge, charge_limit, charge_bypass; the
  desktop user is added to the `video` group on install
- `gts9wifi-wifi-bdf` re-applies the tuned WCN6855 board payload to both
  selected slots (5 GHz RX fix) after firmware updates
- `gts9wifi-keyboard-fw.service` retries the V37 keyboard firmware update after
  the root filesystem is mounted
- the Chinese setup also sets the per-user GNOME language through AccountsService
- NetworkManager dispatcher that disables Wi-Fi background scanning
- `gts9wifi-update ffmpeg`, which installs the rebuilt ffmpeg-free RPMs
  (v4l2m2m H.264/HEVC), verifies their SHA256SUMS, sets Firefox's
  `media.hardware-video-decoding.force-enabled` policy and version-locks them
- `gts9wifi-power` with powersave/balanced/performance profiles (CPU
  governor/EPP, GPU devfreq, Wi-Fi powersave), applied at boot
- fast charging enabled once by default; USB debug network disabled by
  default (create `/etc/gts9wifi/usb-net-enabled` to restore it)
- all of the above in the extension's settings page (Extensions app ->
  gnome-gts9wifi -> Preferences, or
  `gnome-extensions prefs gnome-gts9wifi@tabs9linux`); power and USB debug
  changes authenticate through pkexec
- the GTS9 Plymouth splash theme for the rootfs (selected on install; the
  boot bundle carries the same theme for the initramfs)
- `Tab9 Settings`, a GTK4/libadwaita application in the app grid that
  aggregates the device controls, power profile, USB debug switch and
  system/firmware status (`gts9wifi-settings`); its Setup page adds
  EasyEffects, a LibreOffice -> ONLYOFFICE swap, IBus Rime with the Wanxiang
  dictionary (libpinyin removed, grammar model skipped, inline preedit off),
  RPM Fusion/Copr, Simplified Chinese,
  USTC/TUNA mirror switching, the dnf protection switch and the convertible
  power-key toggle, and Advanced installs
  components, flashes/rolls back the boot pair (typed confirmation) and
  installs the keyboard V37 firmware file
- the low-brightness warning is a transient normal-priority notification that
  expires on its own and is suppressed while GNOME's idle dimming is active;
  clicking it raises the brightness to 36%
- `gts9wifi-protect` blocks dnf updates of port-patched packages, the
  Fedora kernel/firmware and fedora-release/repos, and pins `releasever`;
  explicit `dnf system-upgrade` is still possible

Build (Fedora aarch64 container; needs gcc, glib2-devel and libgtop2-devel):

```sh
mkdir -p ~/rpmbuild/SOURCES
mkdir -p /tmp/src/gts9wifi-userspace-0.17.28
cp -a userspace/tree/. /tmp/src/gts9wifi-userspace-0.17.28/
tar -C /tmp/src -czf ~/rpmbuild/SOURCES/gts9wifi-userspace-0.17.28.tar.gz gts9wifi-userspace-0.17.28
cp userspace/cpuinfo/gts9-cpuinfo.c ~/rpmbuild/SOURCES/
rpmbuild -bb userspace/gts9wifi-userspace.spec
```

Install:

```sh
sudo dnf install ./gts9wifi-userspace-0.17.28-1.fc44.aarch64.rpm
```

The package also wraps `gnome-control-center` in `/usr/local/bin`: arm64
`/proc/cpuinfo` has no CPU model, so the wrapper preloads a small libgtop
shim that supplies it for the Settings > System > About processor row.

The keyboard firmware is not included. Copy the verified V37 blob to
`/lib/firmware/keyboard_stm/stm32_gts9family.bin` only after the matching
kernel is installed.

## Updates

```sh
gts9wifi-update check
sudo gts9wifi-update userspace
sudo gts9wifi-update ffmpeg
sudo gts9wifi-update fingerprint --calib /path/to/calibration
sudo gts9wifi-update kernel --flash --reboot
sudo gts9wifi-update rollback

gts9wifi-power status
sudo gts9wifi-power powersave|balanced|performance
```

`userspace` install enables the fast-charge default, the USB debug-net
off switch, and applies the saved power profile.  The debug link stays
off across boots; create `/etc/gts9wifi/usb-net-enabled` and reboot to
get it back.  The old initramfs gadget is unbound at boot either way.

`ffmpeg` defaults to the `ffmpeg-8.1.3-gts9wifi-1` release; override with
`--tag` if the rebuilt codecs are published elsewhere. It installs only
the runtime `*-free` packages and leaves devel/debuginfo assets alone.

`fingerprint` installs the EL721 libfprint build and the secure-start
runtime, locks both, enables the vendor/apnhlos mounts and fingerprint
units, and assembles the TA/firmware from the tablet's own partitions.
`--calib DIR` copies `calib.dat` and `egoptbds.dat` into the firmware
store (0600). After the first enrollment, enable the PAM path with
`sudo authselect enable-feature with-fingerprint`.

`kernel` without `--flash` only downloads and verifies the pair. With
`--flash` it backs up the four boot partitions and the running modules,
writes boot/init_boot/vendor_boot/dtbo, verifies the readback, then installs
the matching kernel RPM. It never writes vbmeta, persist, modemst or efs.
