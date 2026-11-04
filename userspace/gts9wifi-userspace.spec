%define debug_package %{nil}

Name:           gts9wifi-userspace
Version:        0.8.0
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
Requires:       plymouth
Requires:       plymouth-plugin-script
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita

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
systemctl daemon-reload >/dev/null 2>&1 || :
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme gts9wifi >/dev/null 2>&1 || :
fi

%postun
glib-compile-schemas %{_datadir}/glib-2.0/schemas >/dev/null 2>&1 || :
systemctl daemon-reload >/dev/null 2>&1 || :
if [ "$1" = 0 ] && command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme spinner >/dev/null 2>&1 || :
fi

%files
%{_bindir}/gts9wifi-update
%{_bindir}/gts9wifi-settings
%{_datadir}/applications/gts9wifi-settings.desktop
%{_datadir}/icons/hicolor/scalable/apps/gts9wifi-settings.svg
%dir %{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux
%{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux/*
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.gts9wifi.gschema.xml
%dir %{_datadir}/gts9wifi
%dir %{_datadir}/gts9wifi/versionlock.d
%{_datadir}/gts9wifi/versionlock.d/README
%dir %{_datadir}/plymouth/themes/gts9wifi
%{_datadir}/plymouth/themes/gts9wifi/*
%{_libexecdir}/gts9wifi-device-control
%{_libexecdir}/gts9wifi-privileged
%{_libexecdir}/gts9wifi-usb-net-off
%{_bindir}/gts9wifi-power
%{_unitdir}/gts9wifi-fast-charge-default.service
%{_unitdir}/gts9wifi-usb-net-off.service
%dir %{_unitdir}/gts9wifi-usb-net.service.d
%{_unitdir}/gts9wifi-usb-net.service.d/10-gts9wifi-default-off.conf
%{_unitdir}/gts9wifi-power.service
%{_udevrulesdir}/72-gts9wifi-charger-perms.rules
%config(noreplace) %{_sysconfdir}/NetworkManager/dispatcher.d/90-gts9wifi-no-bgscan
%config(noreplace) %{_sysconfdir}/NetworkManager/conf.d/90-gts9wifi-usb0-unmanaged.conf
%config(noreplace) %{_sysconfdir}/NetworkManager/conf.d/90-gts9wifi-powersave.conf

%changelog
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
