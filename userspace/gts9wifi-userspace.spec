%define debug_package %{nil}

Name:           gts9wifi-userspace
Version:        0.17.22
Release:        1%{?dist}
Summary:        Galaxy Tab S9 Wi-Fi device controls, updates and GNOME integration
License:        MIT
URL:            https://github.com/Lymeeee/gts9wifi-fedora-linux
BuildArch:      noarch
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  systemd-rpm-macros
Requires:       glib2
Requires:       gnome-shell
Requires:       NetworkManager
Requires:       wpa_supplicant
Requires:       bash
Requires:       curl
Requires:       python3
Requires:       unzip
Requires:       util-linux
Requires:       iw
Requires:       systemd
Requires:       polkit
Requires:       alsa-utils
Requires:       plymouth
Requires:       plymouth-plugin-script
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       libwacom-data
Requires:       bluez
Requires:       python3-dbus
Requires:       chrony
Requires:       zram-generator

%description
Tab9 Extras GNOME Shell extension (v6), the gts9wifi device-control helper
with charge limit/bypass, charger udev permissions, the Wi-Fi background
scan dispatcher and the gts9wifi-update tool (userspace RPM install,
versionlock, kernel boot-bundle self-flash and rollback, and the rebuilt
ffmpeg-free codec packages).  Imported from the
ygecesefa/gts9wifi-ubuntu-port userspace and adapted for Fedora.

The proprietary V37 keyboard firmware is not part of this package; install
stm32_gts9family.bin into /lib/firmware/keyboard_stm/ separately.

%prep
%setup -q

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a . %{buildroot}/

%post
glib-compile-schemas %{_datadir}/glib-2.0/schemas >/dev/null 2>&1 || :
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block >/dev/null 2>&1 || :
# 0.17.2: double-tap-to-wake was removed from the kernel driver.
rm -f /usr/lib/udev/rules.d/71-gts9wifi-touchscreen-perms.rules
systemctl daemon-reload >/dev/null 2>&1 || :
# The dynpart mount units depend on a mapper device unit this kernel never
# creates; mount the mapper directly from the userspace helper instead.
systemctl disable vendor.mount vendor-dsp.mount vendor-firmware_mnt.mount \
    >/dev/null 2>&1 || :
systemctl stop vendor.mount vendor-dsp.mount vendor-firmware_mnt.mount \
    >/dev/null 2>&1 || :
systemctl reset-failed vendor.mount vendor-dsp.mount \
    vendor-firmware_mnt.mount >/dev/null 2>&1 || :
if [ -x %{_libexecdir}/gts9wifi-android-mounts ]; then
    %{_libexecdir}/gts9wifi-android-mounts >/dev/null 2>&1 || :
fi
systemctl enable --now gts9wifi-charge-guard.timer >/dev/null 2>&1 || :
systemctl enable gts9wifi-speaker-protection.service >/dev/null 2>&1 || :
systemctl enable gts9wifi-keyboard-fw.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-spen-remote.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-device-name.service >/dev/null 2>&1 || :
systemctl enable gts9wifi-rtc-time.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-rtc-anchor.timer >/dev/null 2>&1 || :
# Keep the PMIC counter continuous; the anchor stores its own UTC relation.
if [ -f /etc/chrony.conf ] && \
   grep -qE '^[[:space:]]*rtcsync[[:space:]]*$' /etc/chrony.conf; then
    sed -i 's/^[[:space:]]*rtcsync[[:space:]]*$/# rtcsync disabled by gts9wifi (PMIC RTC anchor)/' /etc/chrony.conf
    systemctl try-restart chronyd.service >/dev/null 2>&1 || :
fi
if getent group video >/dev/null 2>&1 && command -v usermod >/dev/null 2>&1; then
    while IFS=: read -r account _ uid _; do
        [ "$uid" -ge 1000 ] && [ "$uid" -lt 60000 ] || continue
        usermod -aG video "$account" >/dev/null 2>&1 || :
    done < /etc/passwd
fi
if [ -x %{_libexecdir}/gts9wifi-wifi-bdf ]; then
    %{_libexecdir}/gts9wifi-wifi-bdf >/dev/null 2>&1 || :
fi
if [ -x %{_libexecdir}/gts9wifi-speaker-routing ]; then
    %{_libexecdir}/gts9wifi-speaker-routing >/dev/null 2>&1 || :
fi
if command -v alsactl >/dev/null 2>&1; then
    alsactl store >/dev/null 2>&1 || :
fi
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme gts9wifi >/dev/null 2>&1 || :
fi

%postun
glib-compile-schemas %{_datadir}/glib-2.0/schemas >/dev/null 2>&1 || :
systemctl daemon-reload >/dev/null 2>&1 || :
if [ "$1" = 0 ]; then
    systemctl disable --now gts9wifi-charge-guard.timer >/dev/null 2>&1 || :
    systemctl disable gts9wifi-keyboard-fw.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-spen-remote.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-device-name.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-rtc-time.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-rtc-anchor.timer >/dev/null 2>&1 || :
fi
if [ "$1" = 0 ] && command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme spinner >/dev/null 2>&1 || :
fi

%files
%{_bindir}/gts9wifi-update
%{_bindir}/gts9wifi-settings
%{_datadir}/applications/gts9wifi-settings.desktop
%{_datadir}/icons/hicolor/scalable/apps/gts9wifi-settings.svg
%{_datadir}/libwacom/samsung-gts9wifi-spen.tablet
%dir %{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux
%{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux/*
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.gts9wifi.gschema.xml
%dir %{_datadir}/gts9wifi
%dir %{_datadir}/gts9wifi/versionlock.d
%{_datadir}/gts9wifi/versionlock.d/README
%dir %{_datadir}/plymouth/themes/gts9wifi
%{_datadir}/plymouth/themes/gts9wifi/*
%{_libexecdir}/gts9wifi-device-control
%{_libexecdir}/gts9wifi-panel-coldboot-check
%{_libexecdir}/gts9wifi-bt-provision
%{_libexecdir}/gts9wifi-spen-remote
%{_libexecdir}/gts9wifi-device-name
%{_libexecdir}/gts9wifi-android-mounts
%{_libexecdir}/gts9wifi-rtc-time
%{_libexecdir}/gts9wifi-charge-guard
%{_libexecdir}/gts9wifi-keyboard-fw
%{_libexecdir}/gts9wifi-wifi-bdf
%{_libexecdir}/gts9wifi-privileged
%{_libexecdir}/gts9wifi-usb-net-off
%{_libexecdir}/gts9wifi-mirrors
%{_libexecdir}/gts9wifi-protect
%{_libexecdir}/gts9wifi-ime
%{_libexecdir}/gts9wifi-power-key
%{_libexecdir}/gts9wifi-powerkey-mode
%{_libexecdir}/gts9wifi-speaker-routing
%{_libexecdir}/gts9wifi-speaker-protection
%{_libexecdir}/gts9wifi-sd-uuid-fix
%dir %{_datadir}/alsa/ucm2/Qualcomm/sm8550/GTS9
%{_datadir}/alsa/ucm2/Qualcomm/sm8550/GTS9/HiFi.conf
%{_datadir}/alsa/ucm2/Qualcomm/sm8550/GTS9/Samsung-Galaxy-Tab-S9.conf
%{_datadir}/alsa/ucm2/conf.d/sm8550/Samsung-Galaxy-Tab-S9.conf
%dir %{_unitdir}/alsa-restore.service.d
%{_unitdir}/alsa-restore.service.d/90-gts9wifi-speaker-routing.conf
%{_userunitdir}/gts9wifi-power-key.service
%{_udevrulesdir}/72-gts9wifi-power-key.rules
%{_bindir}/gts9wifi-power
%{_unitdir}/gts9wifi-fast-charge-default.service
%{_unitdir}/gts9wifi-usb-net-off.service
%dir %{_unitdir}/gts9wifi-usb-net.service.d
%{_unitdir}/gts9wifi-usb-net.service.d/10-gts9wifi-default-off.conf
%{_unitdir}/gts9wifi-power.service
%{_unitdir}/gts9wifi-speaker-protection.service
%{_unitdir}/gts9wifi-sd-uuid-fix@.service
%{_unitdir}/gts9wifi-charge-guard.service
%{_unitdir}/gts9wifi-charge-guard.timer
%{_unitdir}/gts9wifi-keyboard-fw.service
%{_unitdir}/gts9wifi-spen-remote.service
%{_unitdir}/gts9wifi-device-name.service
%{_unitdir}/gts9wifi-rtc-time.service
%{_unitdir}/gts9wifi-rtc-anchor.service
%{_unitdir}/gts9wifi-rtc-anchor.timer
%{_udevrulesdir}/90-gts9wifi-spen-no-wakeup.rules
%{_prefix}/lib/modules-load.d/90-gts9wifi-rtc.conf
%dir %{_unitdir}/gts9wifi-panel-coldboot-recover.service.d
%{_unitdir}/gts9wifi-panel-coldboot-recover.service.d/10-gts9wifi-fast-path.conf
%{_udevrulesdir}/72-gts9wifi-charger-perms.rules
%{_udevrulesdir}/60-gts9wifi-sd-uuid.rules
%{_udevrulesdir}/90-gts9wifi-hide-internal.rules
%config(noreplace) %{_sysconfdir}/NetworkManager/dispatcher.d/90-gts9wifi-no-bgscan
%config(noreplace) %{_sysconfdir}/NetworkManager/conf.d/90-gts9wifi-usb0-unmanaged.conf
%config(noreplace) %{_sysconfdir}/NetworkManager/conf.d/90-gts9wifi-powersave.conf
%config(noreplace) %{_sysconfdir}/systemd/zram-generator.conf.d/10-gts9wifi-zstd.conf
%dir %{_sysconfdir}/systemd/system/gts9wifi-android-parts.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/gts9wifi-android-parts.service.d/10-gts9wifi-mounts.conf

%changelog
* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.17.1-1
- Temporarily lift gts9wifi-protect excludes and versionlocks while the
  updater installs userspace, FFmpeg, fingerprint or kernel packages, and
  restore both afterwards (including on failure or interrupt)

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.17.0-1
- Install the gts9wifi-dynpart aarch64 RPM alongside userspace updates,
  providing the Android super dynamic-partition mappings and vendor mounts

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.16.2-1
- Pre-render the Plymouth theme images at panel size so the boot splash
  is no longer aliased by Plymouth's fixed 2x2 Image.Scale

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.16.1-1
- Fix the kernel update's EXIT trap so a successful flash no longer ends
  with an unbound-variable error and a non-zero status

* Fri Nov 06 2026 Lymeeee <mr_xunyu@163.com> - 0.16.0-1
- Restore the system clock from the continuing PMIC RTC counter before
  the network is up, without writing Android's RTC

* Fri Nov 06 2026 Lymeeee <mr_xunyu@163.com> - 0.15.0-1
- Skip the panel recovery platform-suspend cycle when the driver already
  reported a valid ANA38407 panel ID, and retry the cycle if a wake event
  aborts it
- Remove the fixed two-second delay before the panel check
- Accept NUL padding after the appended DTB and provision vendor_boot before
  boot, so one copy cannot hide the other
- Shrink the Samsung wordmark on the boot splash
- Pair the docked S Pen over BLE and publish its battery through BlueZ

* Fri Nov 06 2026 Lymeeee <mr_xunyu@163.com> - 0.14.0-1
- Add a libwacom definition so GNOME treats the S Pen as a
  display-integrated digitizer and maps it to the panel in every rotation
- Pick the newest release asset by version instead of filename order and
  refresh release metadata older than five minutes

* Thu Nov 05 2026 Lymeeee <mr_xunyu@163.com> - 0.13.0-1
- Anti-alias the Plymouth spinner and add live battery telemetry
- Add automatic charging bypass at 100 % with a 95 % release
- Grant the desktop user video-group access for the device controls
- Retry the keyboard V37 update after the root filesystem is mounted
- Set the GNOME per-user language when switching to Chinese

* Thu Nov 05 2026 Lymeeee <mr_xunyu@163.com> - 0.12.0-1
- Fix the CS35L45 right-channel routing (Front/Rear Right to ASP_RX2)
- Reapply speaker gains and routing after alsa-restore

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.11.0-1
- Port the convertible power-key user service with a settings toggle

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.10.0-1
- Add the IBus Rime / 雾凇拼音 one-click installer

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.9.0-1
- Add setup helpers: mirrors, RPM Fusion/Copr, Chinese locale, protection

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.8.0-1
- Add the Tab9 Settings GTK4/libadwaita application

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.7.0-1
- Ship the GTS9 Plymouth theme in the rootfs and select it on install

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.6.0-1
- Add gts9wifi-update fingerprint: libfprint EL721 + runtime, mounts,
  services, versionlock and optional calibration import

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.5.0-1
- Add power profile and USB debug network controls to the settings page
- Add the pkexec helper for privileged settings actions

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.4.0-1
- Default fast charging on and add the one-time default service
- Disable the USB debug net by default, with a rescue flag file
- Add gts9wifi-power profiles and Wi-Fi powersave default

* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.3.0-1
- Add gts9wifi-update ffmpeg to install and lock the rebuilt ffmpeg-free RPMs
- Set Firefox media.hardware-video-decoding.force-enabled policy

* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.2.0-1
- Add gts9wifi-update with kernel self-flash, rollback and versionlock
- Initial port of the Tab9 Extras v6 extension and device helpers
