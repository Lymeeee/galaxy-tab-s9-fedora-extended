%define debug_package %{nil}
# liblog_capture.so targets bionic and records libc.so/LIBC as NEEDED; inside
# the Android runtime that resolves to the tablet's own libc.so, but on Fedora
# no package provides it, so the automatic dependency makes dnf reject the
# whole transaction.  Keep libc.so.6 and drop only the bionic soname.
%global __requires_exclude ^libc[.]so[(]

Name:           gts9wifi-fingerprint
Version:        0.1.5
Release:        1%{?dist}
Summary:        EL721 secure-start runtime for the Galaxy Tab S9 Wi-Fi
License:        MIT AND LGPL-2.1-or-later AND BSD-3-Clause
URL:            https://github.com/Lymeeee/galaxy-tab-s9-fedora-extended
BuildArch:      aarch64
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  glib2-devel
BuildRequires:  systemd-rpm-macros
Requires:       bash
Requires:       python3
Requires:       systemd
Requires:       util-linux
Requires:       device-mapper
Requires:       kmod
Requires:       fprintd
Requires:       fprintd-pam
Requires:       libfprint >= 1.94.100-100.gts9wifi1
Requires:       gts9wifi-dynpart >= 0.1.3

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
%{_prefix}/lib/gts9wifi/fingerprint/libhardware_legacy.so
%{_prefix}/lib/modules-load.d/gts9wifi-fingerprint.conf
%{_unitdir}/gts9wifi-fingerprint-runtime.service
%{_unitdir}/gts9wifi-fingerprint-secure.service
%dir %{_unitdir}/fprintd.service.d
%{_unitdir}/fprintd.service.d/10-gts9wifi-el721.conf

%changelog
* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.1.5-1
- Align the secure owner and libfprint with this port's runtime paths:
  use /run/gts9wifi-fingerprint-secure/attempt, the gts9wifi firmware
  directory and the gts9wifi gatekeeper state instead of the Ultra
  gts9u paths. Drain the owner pipe and log the exited secure child
  PID/status before failing.

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.1.4-1
- Replace the vendor libhardware_legacy.so with a no-op wake-lock stub:
  the vendor build pulls binder/hidl/suspend HAL and left spdaemon spinning
  before it opened /dev/vndbinder.
- Start the SPSS remoteproc after the daemons register for the SPCom link-up
  event; starting it earlier made them miss the event.

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.1.3-1
- Stop shipping gts9wifi-android-parts.service, vendor.mount and
  vendor-firmware_mnt.mount: gts9wifi-dynpart owns those units, and the
  duplicate copies made dnf reject the 0.1.2 transaction with file conflicts.
  Require gts9wifi-dynpart >= 0.1.3 instead.

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.1.2-1
- Stop leaking the bionic shim's libc.so requirement into the Fedora
  dependency set; dnf refused the 0.1.1 transaction with "nothing provides
  libc.so()(64bit)"

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.1.1-1
- Import this unit's calibration from sec_efs (read-only) instead of asking
  for Android /data paths, and keep calibration hashes in the runtime manifest
- Require fprintd-pam: Fedora's GDM uses the dedicated gdm-fingerprint PAM
  service, so no authselect feature or fprintd rebuild is needed

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.1.0-1
- Initial EL721 secure-start runtime, mounts and fprintd drop-in
