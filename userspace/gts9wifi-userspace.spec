%define debug_package %{nil}

Name:           gts9wifi-userspace
Version:        0.1.0
Release:        1%{?dist}
Summary:        Galaxy Tab S9 Wi-Fi device controls and GNOME integration
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

%description
Tab9 Extras GNOME Shell extension (v6), the gts9wifi device-control helper
with charge limit/bypass, charger udev permissions and the Wi-Fi background
scan dispatcher.  Imported from the ygecesefa/gts9wifi-ubuntu-port userspace
and adapted for the Fedora port.

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
%dir %{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux
%{_datadir}/gnome-shell/extensions/gnome-gts9wifi@tabs9linux/*
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.gts9wifi.gschema.xml
%{_libexecdir}/gts9wifi-device-control
%{_udevrulesdir}/72-gts9wifi-charger-perms.rules
%config(noreplace) %{_sysconfdir}/NetworkManager/dispatcher.d/90-gts9wifi-no-bgscan

%changelog
* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.1.0-1
- Initial port of the Tab9 Extras v6 extension and device helpers
