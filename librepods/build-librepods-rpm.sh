#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LIBREPODS_REPO:-https://github.com/librepods-org/librepods.git}"
BRANCH="${LIBREPODS_BRANCH:-linux/rust}"
OUT_DIR="/work/out-librepods"

dnf -y install \
    git \
    gcc \
    rust \
    cargo \
    pkgconf-pkg-config \
    rpm-build \
    dbus-devel \
    pulseaudio-libs-devel \
    wayland-devel \
    libxkbcommon-devel \
    fontconfig-devel

BUILD_ROOT="$(mktemp -d)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$BUILD_ROOT/src"
COMMIT_SHA="$(git -C "$BUILD_ROOT/src" rev-parse --short HEAD)"
COMMIT_DATE="$(git -C "$BUILD_ROOT/src" show -s --format=%cd --date=format:%Y%m%d HEAD)"
CRATE_VER="$(sed -n 's/^version = "\([^"]*\)".*/\1/p' "$BUILD_ROOT/src/linux-rust/Cargo.toml" | head -n1)"
PKG_VER="${CRATE_VER:-0.1.0}.git${COMMIT_DATE}.${COMMIT_SHA}"

cd "$BUILD_ROOT/src/linux-rust"
cargo build --release --locked

RPM_TOP="$BUILD_ROOT/rpmbuild"
mkdir -p "$RPM_TOP"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

cp target/release/librepods "$RPM_TOP/SOURCES/librepods"
cp assets/me.kavishdevar.librepods.desktop "$RPM_TOP/SOURCES/me.kavishdevar.librepods.desktop"
cp assets/icon.png "$RPM_TOP/SOURCES/me.kavishdevar.librepods.png"

cat > "$RPM_TOP/SPECS/librepods.spec" <<EOF
%define debug_package %{nil}
%define _build_id_links none

Name:           librepods
Version:        ${PKG_VER}
Release:        1%{?dist}
Summary:        AirPods features on Linux (noise control, battery, ear detection)
License:        GPL-3.0-or-later
URL:            https://github.com/librepods-org/librepods
BuildArch:      aarch64

Requires:       dbus-libs
Requires:       pulseaudio-libs
Requires:       bluez

%description
LibrePods (Linux Rust rewrite) brings Apple-exclusive AirPods features
such as noise control modes, battery status, and ear detection to Linux.

%install
install -Dm0755 %{SOURCE0} %{buildroot}%{_bindir}/librepods
install -Dm0644 %{SOURCE1} %{buildroot}%{_datadir}/applications/me.kavishdevar.librepods.desktop
install -Dm0644 %{SOURCE2} %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/me.kavishdevar.librepods.png

%files
%{_bindir}/librepods
%{_datadir}/applications/me.kavishdevar.librepods.desktop
%{_datadir}/icons/hicolor/256x256/apps/me.kavishdevar.librepods.png
EOF

rpmbuild -bb \
    --define "_topdir $RPM_TOP" \
    --define "SOURCE0 $RPM_TOP/SOURCES/librepods" \
    --define "SOURCE1 $RPM_TOP/SOURCES/me.kavishdevar.librepods.desktop" \
    --define "SOURCE2 $RPM_TOP/SOURCES/me.kavishdevar.librepods.png" \
    "$RPM_TOP/SPECS/librepods.spec"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
cp "$RPM_TOP"/RPMS/aarch64/librepods-*.rpm "$OUT_DIR/"
(cd "$OUT_DIR" && sha256sum *.rpm > SHA256SUMS)
cat > "$OUT_DIR/BUILD-METADATA.txt" <<EOF
repo=${REPO_URL}
branch=${BRANCH}
commit=${COMMIT_SHA}
version=${PKG_VER}
EOF
ls -la "$OUT_DIR"
