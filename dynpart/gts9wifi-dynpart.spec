%define debug_package %{nil}

Name:           gts9wifi-dynpart
Version:        0.1.0
Release:        1%{?dist}
Summary:        Android dynamic-partition mapper for the Galaxy Tab S9 Fedora port
License:        GPL-3.0-only AND Apache-2.0
URL:            https://gitlab.com/flamingradian/make-dynpart-mappings
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  pkgconf-pkg-config
BuildRequires:  device-mapper-devel
BuildRequires:  libmd-devel
BuildRequires:  libblkid-devel
BuildRequires:  systemd-rpm-macros
Requires:       libdevmapper
Requires:       libmd
Requires:       libblkid
Requires:       systemd

%description
make-dynpart-mappings reads the Android super partition's liblp metadata
and creates device-mapper linear mappings for its logical partitions.  The
port uses it to mount the stock vendor image (erofs), dsp, apnhlos and
persist partitions from a Fedora rootfs.

%prep
%setup -q

%build
make %{?_smp_mflags}

%install
install -Dpm0755 make-dynpart-mappings %{buildroot}%{_bindir}/make-dynpart-mappings
install -Dpm0644 systemd/gts9wifi-android-parts.service \
    %{buildroot}%{_unitdir}/gts9wifi-android-parts.service
install -Dpm0644 systemd/vendor.mount %{buildroot}%{_unitdir}/vendor.mount
install -Dpm0644 systemd/vendor-dsp.mount %{buildroot}%{_unitdir}/vendor-dsp.mount
install -Dpm0644 systemd/vendor-firmware_mnt.mount \
    %{buildroot}%{_unitdir}/vendor-firmware_mnt.mount
install -Dpm0644 systemd/mnt-vendor-persist.mount \
    %{buildroot}%{_unitdir}/mnt-vendor-persist.mount

%post
# The full-set rootfs ships vendor.mount masked until the mapper exists.
if [ -L /etc/systemd/system/vendor.mount ] && \
   [ "$(readlink /etc/systemd/system/vendor.mount)" = /dev/null ]; then
    rm -f /etc/systemd/system/vendor.mount
fi
systemctl daemon-reload >/dev/null 2>&1 || :
systemctl enable gts9wifi-android-parts.service vendor.mount \
    vendor-dsp.mount vendor-firmware_mnt.mount mnt-vendor-persist.mount \
    >/dev/null 2>&1 || :
if [ -e /dev/disk/by-partlabel/super ]; then
    systemctl start gts9wifi-android-parts.service >/dev/null 2>&1 || :
    systemctl start vendor.mount vendor-dsp.mount \
        vendor-firmware_mnt.mount mnt-vendor-persist.mount \
        >/dev/null 2>&1 || :
fi

%preun
if [ "$1" -eq 0 ]; then
    systemctl disable gts9wifi-android-parts.service vendor.mount \
        vendor-dsp.mount vendor-firmware_mnt.mount mnt-vendor-persist.mount \
        >/dev/null 2>&1 || :
fi

%postun
systemctl daemon-reload >/dev/null 2>&1 || :

%files
%{_bindir}/make-dynpart-mappings
%license LICENSE
%{_unitdir}/gts9wifi-android-parts.service
%{_unitdir}/vendor.mount
%{_unitdir}/vendor-dsp.mount
%{_unitdir}/vendor-firmware_mnt.mount
%{_unitdir}/mnt-vendor-persist.mount

%changelog
* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.1.0-1
- Package make-dynpart-mappings (upstream f883b0b) and the Android parts
  mount units for the Galaxy Tab S9 Fedora port
