# gts9wifi-userspace

aarch64 RPM with the Phase 1 userspace pieces from the Ubuntu port:

- Galaxy Tab Extension GNOME Shell extension (screen-lock/keyboard controls,
  floating on-screen keyboard button, rounded screen corners, and the
  under-display fingerprint target; loaded in the user session, on the lock
  screen and on the GDM login screen)
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
  and reinstalls packages whose zh_CN translations the image build skipped
- NetworkManager dispatcher that disables Wi-Fi background scanning
- `gts9wifi-update ffmpeg`, which installs the rebuilt ffmpeg-free RPMs
  (v4l2m2m H.264/HEVC), verifies their SHA256SUMS, sets Firefox's
  `media.hardware-video-decoding.force-enabled` policy and version-locks them
- `gts9wifi-power` with powersave/balanced/sticky/performance profiles (CPU
  governor/EPP and boost OPPs, GPU devfreq, Wi-Fi powersave), applied at boot;
  balanced, sticky and performance expose CPU7's 3.36 GHz boost OPP
- fast charging enabled once by default
- device controls and the power profile live in `平板杂项设置` (Tab9 Settings);
  the extension's own settings page (Extensions app -> Galaxy Tab Extension ->
  Preferences, or `gnome-extensions prefs galaxy-tab-extension@tabs9linux`)
  keeps the boot animation, lock behaviour, rounded corners and the floating
  keyboard button; power changes authenticate through pkexec
- the GTS9 Plymouth splash theme for the rootfs (selected on install; the
  boot bundle carries the same theme for the initramfs)
- `平板杂项设置` (Tab9 Settings), a GTK4/libadwaita application in the app grid that
  aggregates the device controls, power profile, USB debug switch and
  system/firmware status (`gts9wifi-settings`); its Setup page adds
  EasyEffects, a LibreOffice -> ONLYOFFICE swap, IBus Rime with the Wanxiang
  dictionary (libpinyin removed, grammar model skipped, inline preedit off),
  RPM Fusion/Copr, Simplified Chinese,
  USTC/TUNA mirror switching, the dnf protection switch and the convertible
  power-key toggle, and Advanced installs
  components, flashes/rolls back the boot pair (typed confirmation) and
  installs the keyboard V37 firmware file
- a logind drop-in shortens the post-resume lid holdoff to 5 s; together with
  the kernel's Wacom cover-detect (SW_LID) closing the keyboard folio suspends
  and opening it wakes the tablet
- the low-brightness warning is a transient normal-priority notification that
  expires on its own and is suppressed while GNOME's idle dimming is active;
  clicking it raises the brightness to 36%; it can be switched off
- the settings app's Display page has an optional auto-brightness floor: when
  on, ambient-light dimming stops at 36% (the target is raised by the current
  manual offset so the floor holds at any slider position); manual brightness
  changes can still go below 36%, and the low-brightness warning still covers
  them
- the S Pen libwacom entry names the tablet "Samsung Galaxy Tab S9" and the
  pen "Samsung S Pen" with its single side button (the generic fallback
  advertised a second, unusable button)
- the Shell brightness OSD is suppressed only while the Quick Settings
  brightness slider is being dragged; brightness keys and auto-brightness
  still show it
- `gts9wifi-protect` blocks dnf updates of port-patched packages, the
  Fedora kernel/firmware and fedora-release/repos, and pins `releasever`;
  explicit `dnf system-upgrade` is still possible
- install-time repair of file capabilities that older xattr-less rootfs
  tarballs dropped (newuidmap/newgidmap, arping, the sssd helpers)

Build (Fedora aarch64 container; needs gcc, glib2-devel and libgtop2-devel):

```sh
mkdir -p ~/rpmbuild/SOURCES
mkdir -p /tmp/src/gts9wifi-userspace-0.17.33
cp -a userspace/tree/. /tmp/src/gts9wifi-userspace-0.17.33/
tar -C /tmp/src -czf ~/rpmbuild/SOURCES/gts9wifi-userspace-0.17.33.tar.gz gts9wifi-userspace-0.17.33
cp userspace/cpuinfo/gts9-cpuinfo.c ~/rpmbuild/SOURCES/
rpmbuild -bb userspace/gts9wifi-userspace.spec
```

Install:

```sh
sudo dnf install ./gts9wifi-userspace-0.17.33-1.fc44.aarch64.rpm
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

`userspace` install enables the fast-charge default and applies the saved
power profile.

`ffmpeg` defaults to the `ffmpeg-8.1.3-gts9wifi-1` release; override with
`--tag` if the rebuilt codecs are published elsewhere. It installs only
the runtime `*-free` packages and leaves devel/debuginfo assets alone.

`fingerprint` installs the EL721 libfprint build and the secure-start
runtime, locks both, enables the vendor/apnhlos mounts and fingerprint
units, and assembles the TA/firmware from the tablet's own partitions.
`--calib-from-device` mounts `sec_efs` read-only and imports this unit's
`biometrics/meta/egis_calibration_data.bin` as `calib.dat` plus
`egoptbds.dat` when present; `--calib DIR` imports both from a directory
instead. Reboot, then enroll with GNOME Settings or `fprintd-enroll`.
Fingerprint login in GNOME Settings, the lock screen and GDM requires
authselect's `with-fingerprint` feature, which the updater enables. Without
it authselect pins `org.gnome.login-screen enable-fingerprint-authentication`
to false, so GNOME 50 hides the Settings row and never probes the reader, and
`gdm-fingerprint` has no `pam_fprintd`. Fedora only adds it to
`fingerprint-auth` and `system-auth`, not `password-auth`, so GDM's password
prompt is not duplicated.

`kernel` without `--flash` only downloads and verifies the pair. With
`--flash` it backs up the four boot partitions and the running modules,
writes boot/init_boot/vendor_boot/dtbo, verifies the readback, then installs
the matching kernel RPM. It never writes vbmeta, persist, modemst or efs.
