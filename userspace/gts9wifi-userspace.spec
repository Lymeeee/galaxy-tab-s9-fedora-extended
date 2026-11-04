%define debug_package %{nil}

Name:           gts9wifi-userspace
Version:        0.3.0
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

%postun
glib-compile-schemas %{_datadir}/glib-2.0/schemas >/dev/null 2>&1 || :

%files
%{_bindir}/gts9wifi-update
%dir %{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux
%{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux/*
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.gts9wifi.gschema.xml
%dir %{_datadir}/gts9wifi
%dir %{_datadir}/gts9wifi/versionlock.d
%{_datadir}/gts9wifi/versionlock.d/README
%{_libexecdir}/gts9wifi-device-control
%{_udevrulesdir}/72-gts9wifi-charger-perms.rules
%config(noreplace) %{_sysconfdir}/NetworkManager/dispatcher.d/90-gts9wifi-no-bgscan

%changelog
* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.3.0-1
- Add gts9wifi-update ffmpeg to install and lock the rebuilt ffmpeg-free RPMs
- Set Firefox media.hardware-video-decoding.force-enabled policy

* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.2.0-1
- Add gts9wifi-update with kernel self-flash, rollback and versionlock
- Initial port of the Tab9 Extras v6 extension and device helpers
