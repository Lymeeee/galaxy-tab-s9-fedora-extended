%define debug_package %{nil}

Name:           gts9wifi-fingerprint
Version:        0.1.0
Release:        1%{?dist}
Summary:        EL721 secure-start runtime for the Galaxy Tab S9 Wi-Fi
License:        MIT AND LGPL-2.1-or-later AND BSD-3-Clause
URL:            https://github.com/Lymeeee/gts9wifi-fedora-linux
BuildArch:      aarch64
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  glib2-devel
Requires:       bash
Requires:       python3
Requires:       systemd
Requires:       util-linux
Requires:       device-mapper
Requires:       kmod
Requires:       fprintd
Requires:       libfprint >= 1.94.100-100.gts9wifi1

%description
Boot-time secure owner and runtime assembly for the EgisTec EL721
under-display fingerprint reader.  Copies Samsung's signed TA, firmware
and the SPSS userspace from the tablet's own read-only Android
partitions, starts the SPU/Keymaster/HwVault sequence once per boot and
provides the QTEE socket the patched libfprint driver talks to.

All proprietary files come from the tablet; none are packaged here.

%prep
%setup -q

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a . %{buildroot}/

%post
systemctl daemon-reload >/dev/null 2>&1 || :

%postun
systemctl daemon-reload >/dev/null 2>&1 || :

%files
%{_libexecdir}/gts9wifi-android-parts
%{_libexecdir}/gts9wifi-fingerprint-runtime
%{_libexecdir}/gts9wifi-fingerprint-secure
%{_libexecdir}/gts9wifi-fingerprint-secure-owner
%{_libexecdir}/gts9wifi-binder-ctxmgr
%dir %{_prefix}/lib/gts9wifi
%dir %{_prefix}/lib/gts9wifi/fingerprint
%{_prefix}/lib/gts9wifi/fingerprint/liblog_capture.so
%{_prefix}/lib/gts9wifi/fingerprint/libvmmem_shim.so
%{_prefix}/lib/modules-load.d/gts9wifi-fingerprint.conf
%{_unitdir}/gts9wifi-android-parts.service
%{_unitdir}/gts9wifi-fingerprint-runtime.service
%{_unitdir}/gts9wifi-fingerprint-secure.service
%dir %{_unitdir}/fprintd.service.d
%{_unitdir}/fprintd.service.d/10-gts9wifi-el721.conf
%{_unitdir}/vendor.mount
%{_unitdir}/vendor-firmware_mnt.mount

%changelog
* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.1.0-1
- Initial EL721 secure-start runtime, mounts and fprintd drop-in
