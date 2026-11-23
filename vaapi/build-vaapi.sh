#!/bin/bash
# SPDX-License-Identifier: MIT
#
# Build qcom-va-driver (Qualcomm Iris stateful V4L2 M2M VA-API backend) as a
# Fedora 44 aarch64 RPM.  Run as root inside a quay.io/fedora/fedora:44
# container.  If FLATPAK_DRIVER_SO is set to a prebuilt Ubuntu 24.04
# qcom_drv_video.so, it is bundled under /usr/lib64/qcom-va-driver-flatpak/.
set -euxo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
out=${VAAPI_OUTDIR:-$repo/out-vaapi}
commit=${QCOM_VA_COMMIT:-0980a1decf26d34c9aa71cd0a4a0d25703a7a17f}
tarball_url="https://github.com/radxa-pkg/qcom-va-driver/archive/${commit}.tar.gz"
top=$HOME/rpmbuild

dnf -y install rpm-build gcc-c++ meson ninja-build pkgconf-pkg-config \
    libva-devel libdrm-devel mesa-libEGL-devel mesa-libGLES-devel \
    mesa-libgbm-devel vulkan-loader-devel glslang curl tar findutils >/dev/null

rm -rf "$top" "$out"
mkdir -p "$top/SOURCES" "$top/SPECS" "$out"

cp "$here/qcom-va-driver.spec" "$top/SPECS/"
curl -fsSL --retry 3 -o "$top/SOURCES/qcom-va-driver-${commit}.tar.gz" "$tarball_url"

rpmbuild_args=(
    --define "upstream_commit $commit"
)
if [ -n "${FLATPAK_DRIVER_SO:-}" ] && [ -f "$FLATPAK_DRIVER_SO" ]; then
    cp "$FLATPAK_DRIVER_SO" "$top/SOURCES/qcom_drv_video-flatpak.so"
    rpmbuild_args+=(--define "with_flatpak 1")
fi

rpmbuild -bb "${rpmbuild_args[@]}" "$top/SPECS/qcom-va-driver.spec"

find "$top/RPMS" -name '*.rpm' -exec cp -t "$out" {} +

(
    cd "$out"
    sha256sum *.rpm > VAAPI-SHA256SUMS
    {
        echo "upstream_repo: https://github.com/radxa-pkg/qcom-va-driver"
        echo "upstream_commit: $commit"
        echo "source_tarball_sha256: $(sha256sum "$top/SOURCES/qcom-va-driver-${commit}.tar.gz" | cut -d' ' -f1)"
        if [ -n "${FLATPAK_DRIVER_SO:-}" ] && [ -f "$FLATPAK_DRIVER_SO" ]; then
            echo "flatpak_driver_bundled: yes"
            echo "flatpak_driver_sha256: $(sha256sum "$FLATPAK_DRIVER_SO" | cut -d' ' -f1)"
        else
            echo "flatpak_driver_bundled: no"
        fi
    } > VAAPI-BUILD-METADATA.txt
)

ls -l "$out"
