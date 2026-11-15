%global debug_package %{nil}

Name:           gts9wifi-sensors
Version:        0.1.0
Release:        1%{?dist}
Summary:        Qualcomm SSC sensor stack for the Galaxy Tab S9 Wi-Fi
License:        GPL-3.0-or-later and GPL-2.0-or-later
URL:            https://github.com/Lymeeee/galaxy-tab-s9-fedora-extended
BuildArch:      aarch64
Source0:        %{name}-%{version}.tar.gz
Source1:        fix-ssc-sync-wait-busy-loop.patch
Source2:        fix-early-ssc-claim-race.patch
Source3:        79-gts9wifi-ssc-types.rules
Source4:        30-gts9wifi-sensors.conf

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  glib2-devel
BuildRequires:  libgudev-devel
BuildRequires:  polkit-devel
BuildRequires:  libqmi-devel
BuildRequires:  libmbim-devel
BuildRequires:  libqrtr-glib-devel
BuildRequires:  protobuf-c-devel
BuildRequires:  protobuf-devel
BuildRequires:  python3-devel
BuildRequires:  python3-protobuf
BuildRequires:  systemd-rpm-macros
BuildRequires:  libxml2

Requires:       iio-sensor-proxy >= 3.8

%description
Qualcomm Sensor Core (SSC) sensor stack for the Galaxy Tab S9 Wi-Fi
(SM-X710).  The ADSP exposes ambient light, accelerometer, compass and
proximity over FastRPC/QRTR; Fedora's iio-sensor-proxy does not consume
SSC.  This package builds libssc and iio-sensor-proxy 3.9 with SSC
support, adds the FastRPC sensor-type udev tags and the AF_QIPCRTR
systemd override.

%prep
%setup -q
pushd libssc-0.4.4
patch -p1 < %{SOURCE1}
popd
pushd iio-sensor-proxy-3.9
patch -p1 < %{SOURCE2}
popd

%build
pushd libssc-0.4.4
meson setup output --prefix=%{_prefix} --libdir=%{_libdir}
meson compile -C output
DESTDIR=%{_builddir}/libssc-stage meson install --no-rebuild -C output
popd

pc=%{_builddir}/libssc-stage%{_libdir}/pkgconfig/libssc.pc
sed -i "s|^prefix=.*|prefix=%{_builddir}/libssc-stage%{_prefix}|" "$pc"
export PKG_CONFIG_PATH=%{_builddir}/libssc-stage%{_libdir}/pkgconfig
unset PKG_CONFIG_SYSROOT_DIR

pushd iio-sensor-proxy-3.9
meson setup output --prefix=%{_prefix} \
    -Dssc-support=enabled \
    -Dudevrulesdir=%{_prefix}/lib/udev/rules.d \
    -Dsystemdsystemunitdir=%{_unitdir}
meson compile -C output
popd

%install
DESTDIR=%{buildroot} meson install --no-rebuild -C libssc-0.4.4/output
DESTDIR=%{buildroot} meson install --no-rebuild -C iio-sensor-proxy-3.9/output

mkdir -p %{buildroot}%{_libexecdir}/gts9wifi
mv %{buildroot}%{_libexecdir}/iio-sensor-proxy %{buildroot}%{_libexecdir}/gts9wifi/iio-sensor-proxy

# The Fedora iio-sensor-proxy package owns these; only provide the binary.
rm -rf %{buildroot}%{_unitdir}/iio-sensor-proxy.service \
       %{buildroot}%{_prefix}/lib/udev/rules.d/80-iio-sensor-proxy.rules \
       %{buildroot}%{_datadir}/dbus-1/system.d/net.hadess.SensorProxy.conf \
       %{buildroot}%{_datadir}/polkit-1/actions/net.hadess.SensorProxy.policy \
       %{buildroot}%{_bindir}/monitor-sensor \
       %{buildroot}/usr/lib/python*/site-packages/ssc_server \
       %{buildroot}%{_libexecdir}/installed-tests

install -Dm0644 %{SOURCE3} %{buildroot}%{_sysconfdir}/udev/rules.d/79-gts9wifi-ssc-types.rules
install -Dm0644 %{SOURCE4} %{buildroot}%{_sysconfdir}/systemd/system/iio-sensor-proxy.service.d/30-gts9wifi-sensors.conf

%post
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=misc >/dev/null 2>&1 || :
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart iio-sensor-proxy.service >/dev/null 2>&1 || :

%postun
udevadm control --reload-rules >/dev/null 2>&1 || :
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl try-restart iio-sensor-proxy.service >/dev/null 2>&1 || :

%files
%{_libexecdir}/gts9wifi/iio-sensor-proxy
%config(noreplace) %{_sysconfdir}/udev/rules.d/79-gts9wifi-ssc-types.rules
%config(noreplace) %{_sysconfdir}/systemd/system/iio-sensor-proxy.service.d/30-gts9wifi-sensors.conf
%{_bindir}/ssccli
%{_libdir}/libssc.so*
%{_includedir}/libssc
%{_libdir}/pkgconfig/libssc.pc

%changelog
* Sun Nov 15 2026 Lymeeee <mr_xunyu@163.com> - 0.1.0-1
- Initial SSC sensor stack package for the Galaxy Tab S9 Wi-Fi.
