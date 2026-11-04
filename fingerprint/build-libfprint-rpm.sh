#!/bin/bash
# Build Fedora 44's libfprint 1.94.100 with the EgisTec EL721 driver.
# Run as root inside a fedora:44 aarch64 container; writes out-fingerprint/.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
out=${FINGERPRINT_OUTDIR:-$repo/out-fingerprint}
srpm_url=${SRPM_URL:-https://dl.fedoraproject.org/pub/fedora/linux/updates/44/Everything/source/tree/Packages/l/libfprint-1.94.100-1.fc44.src.rpm}
qcbor_commit=4ace4620d549f22c1163c5b00d3ae0c0dae1d207
quic_teec_commit=736419e25a2036aac3292a10a93e394a90750ca3
top=$HOME/rpmbuild
work=$top/gts9wifi-fingerprint

dnf -y install rpm-build rpmdevtools dnf5-plugins tar xz zstd cpio patch git curl findutils gnupg2 cmake gcc gcc-c++ >/dev/null
git config --system user.name rpmbuild
git config --system user.email rpmbuild@localhost

rm -rf "$work" && mkdir -p "$work" "$out"
curl -fL --retry 3 -o "$work/libfprint.src.rpm" "$srpm_url"
rm -rf "$top/SPECS" "$top/SOURCES"
rpm -ivh --nosignature --nodeps "$work/libfprint.src.rpm" >/dev/null

spec=$top/SPECS/libfprint.spec
version=$(rpm -qp --qf '%{VERSION}' "$work/libfprint.src.rpm")
srcdir=$work/libfprint-v$version
tar -C "$work" -xf "$top/SOURCES/libfprint-v$version.tar.gz"

(cd "$srcdir" && patch -p1 < "$here/patches/0001-el721-platform-driver-1.94.100.patch")
install -m0644 "$here"/libfprint/el721.c "$here"/libfprint/el721.h \
    "$here"/libfprint/el721-qtee.c "$here"/libfprint/el721-qtee.h \
    "$here"/libfprint/el721-*.h "$srcdir/libfprint/drivers/"

# quic-teec and QCBOR are linked statically into the driver, as in the
# Ubuntu port, so the tablet needs no private runtime ABI.
git clone --quiet https://github.com/laurencelundblade/QCBOR.git "$work/qcbor"
git -C "$work/qcbor" checkout --quiet "$qcbor_commit"
git clone --quiet https://github.com/qualcomm/quic-teec.git "$work/quic-teec"
git -C "$work/quic-teec" checkout --quiet "$quic_teec_commit"
git -C "$work/quic-teec" apply --recount \
    "$here/quic-teec/0002-qcomtee-expose-memory-fd.patch" \
    "$here/quic-teec/0003-qcomtee-register-dmabuf.patch"

deps=$work/qtee-prefix
cmake -S "$work/qcbor" -B "$work/build-qcbor" -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCMAKE_INSTALL_PREFIX="$deps" >/dev/null
cmake --build "$work/build-qcbor" -j"$(nproc)" >/dev/null
cmake --install "$work/build-qcbor" >/dev/null
cmake -S "$work/quic-teec" -B "$work/build-quic-teec" -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DCMAKE_INSTALL_PREFIX="$deps" -DQCBOR_DIR_HINT="$deps" >/dev/null
cmake --build "$work/build-quic-teec" -j"$(nproc)" >/dev/null
cmake --install "$work/build-quic-teec" >/dev/null

mkdir -p "$srcdir/el721-qtee-deps/include" "$srcdir/el721-qtee-deps/lib"
cp -a "$deps/include/." "$srcdir/el721-qtee-deps/include/"
qcbor_lib=$(find "$deps" -name libqcbor.a -print -quit)
qtee_lib=$(find "$deps" -name libqcomtee.a -print -quit)
[ -n "$qcbor_lib" ] && [ -n "$qtee_lib" ] || {
    echo "static QTEE libraries were not installed" >&2
    exit 1
}
cp "$qcbor_lib" "$qtee_lib" "$srcdir/el721-qtee-deps/lib/"

(cd "$work" && tar -czf "$top/SOURCES/libfprint-v$version.tar.gz" "libfprint-v$version")

# Higher than Fedora's current release so a plain install upgrades it;
# versionlock keeps Fedora updates from replacing the EL721 build.
sed -i 's/^Release:.*/Release:        100.gts9wifi1%{?dist}/' "$spec"

dnf builddep -y --spec "$spec" >/dev/null
rpmbuild -bb "$spec"

rm -f "$out"/*.rpm "$out"/SHA256SUMS "$out"/BUILD-METADATA.txt
find "$top/RPMS" -name '*.rpm' -exec cp -t "$out" {} +
(
    cd "$out"
    sha256sum *.rpm > SHA256SUMS
    {
        echo "source_srpm: $srpm_url"
        echo "source_srpm_sha256: $(sha256sum "$work/libfprint.src.rpm" | cut -d' ' -f1)"
        echo "source_version: $(rpm -qp --qf '%{VERSION}-%{RELEASE}' "$work/libfprint.src.rpm")"
        echo "patch_0001_sha256: $(sha256sum "$here"/patches/0001-*.patch | cut -d' ' -f1)"
        echo "qcbor_commit: $qcbor_commit"
        echo "quic_teec_commit: $quic_teec_commit"
    } > BUILD-METADATA.txt
)

ls -l "$out"
