%global upstream_commit 0980a1decf26d34c9aa71cd0a4a0d25703a7a17f
%global debug_package %{nil}

# Exclude the Ubuntu-built Flatpak compatibility copy from RPM auto-prov/req so
# it neither duplicates host driver provides nor interferes with host deps.
%global __provides_exclude_from ^%{_libdir}/qcom-va-driver-flatpak/.*$
%global __requires_exclude_from ^%{_libdir}/qcom-va-driver-flatpak/.*$

Name:           qcom-va-driver
Version:        1.1.1
Release:        1%{?dist}.gts9wifi1
Summary:        VA-API backend for Qualcomm Iris stateful V4L2 M2M (gts9wifi)
License:        MIT
URL:            https://github.com/radxa-pkg/qcom-va-driver
Source0:        qcom-va-driver-%{upstream_commit}.tar.gz
%if 0%{?with_flatpak}
Source1:        qcom_drv_video-flatpak.so
%endif

BuildRequires:  gcc-c++
BuildRequires:  meson >= 0.61
BuildRequires:  ninja-build
BuildRequires:  pkgconf-pkg-config
BuildRequires:  libva-devel >= 1.10
BuildRequires:  libdrm-devel
BuildRequires:  mesa-libEGL-devel
BuildRequires:  mesa-libGLES-devel
BuildRequires:  mesa-libgbm-devel
BuildRequires:  vulkan-loader-devel
BuildRequires:  glslang

Requires:       libva%{?_isa} >= 1.10
Recommends:     mesa-vulkan-drivers%{?_isa}

%description
VA-API backend for Qualcomm Iris video accelerators backed by the Linux V4L2
stateful memory-to-memory interface. Provides hardware-accelerated H.264,
HEVC, VP9 and AV1 decoding plus H.264/HEVC encoding with DMA-BUF zero-copy
and Vulkan VPP, and installs the msm_drv_video.so alias so libva selects it
automatically on Qualcomm MSM devices.

Also ships an older-glibc (Ubuntu 24.04 / GLIBC 2.39) compatibility copy under
%{_libdir}/qcom-va-driver-flatpak so Flatpak runtimes (Freedesktop 25.08+) can
use the same hardware decoder via LIBVA_DRIVERS_PATH.

%prep
%autosetup -n qcom-va-driver-%{upstream_commit}

%build
%meson \
    -Dgpu_copy=enabled \
    -Dcdsp_vpp=disabled \
    -Dvulkan_vpp=enabled \
    -Dv4l2_symlink=true \
    -Dtests=false
%meson_build

%install
%meson_install

# GStreamer VA environment defaults (matches upstream Debian/Arch packaging,
# plus vaav1dec for SM8550 Iris AV1 support).
install -d %{buildroot}%{_prefix}/lib/environment.d
cat > %{buildroot}%{_prefix}/lib/environment.d/60-libva-v4l2.conf <<'EOF'
GST_VA_ALL_DRIVERS=1
GST_PLUGIN_FEATURE_RANK=vah264dec:1000,vah264enc:1000,vah265dec:1000,vah265enc:1000,vavp9dec:1000,vaav1dec:1000
EOF

install -d %{buildroot}%{_sysconfdir}/profile.d
cat > %{buildroot}%{_sysconfdir}/profile.d/libva-v4l2.sh <<'EOF'
export GST_VA_ALL_DRIVERS=1
export GST_PLUGIN_FEATURE_RANK=vah264dec:1000,vah264enc:1000,vah265dec:1000,vah265enc:1000,vavp9dec:1000,vaav1dec:1000
EOF

%if 0%{?with_flatpak}
install -d %{buildroot}%{_libdir}/qcom-va-driver-flatpak
install -m 0755 %{SOURCE1} %{buildroot}%{_libdir}/qcom-va-driver-flatpak/qcom_drv_video.so
ln -s qcom_drv_video.so %{buildroot}%{_libdir}/qcom-va-driver-flatpak/msm_drv_video.so
ln -s qcom_drv_video.so %{buildroot}%{_libdir}/qcom-va-driver-flatpak/v4l2_drv_video.so
%endif

%files
%license LICENSE
%doc README.md
%{_libdir}/dri/qcom_drv_video.so
%{_libdir}/dri/msm_drv_video.so
%{_libdir}/dri/v4l2_drv_video.so
%{_prefix}/lib/environment.d/60-libva-v4l2.conf
%config(noreplace) %{_sysconfdir}/profile.d/libva-v4l2.sh
%if 0%{?with_flatpak}
%dir %{_libdir}/qcom-va-driver-flatpak
%{_libdir}/qcom-va-driver-flatpak/qcom_drv_video.so
%{_libdir}/qcom-va-driver-flatpak/msm_drv_video.so
%{_libdir}/qcom-va-driver-flatpak/v4l2_drv_video.so
%endif

%changelog
* Mon Nov 23 2026 gts9wifi port <gts9wifi@localhost> - 1.1.1-1.gts9wifi1
- Initial Fedora 44 package of radxa-pkg/qcom-va-driver (0980a1d) with
  GPU copy, Vulkan VPP, and Flatpak compatibility binary.
