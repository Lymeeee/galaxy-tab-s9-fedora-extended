#!/bin/bash
# Build the gts9wifi-fingerprint runtime RPM (secure owner, binder context
# manager, bionic shims, systemd units).  Run as root inside fedora:44 aarch64.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
out=${FINGERPRINT_OUTDIR:-$repo/out-fingerprint}
qcbor_commit=4ace4620d549f22c1163c5b00d3ae0c0dae1d207
quic_teec_commit=736419e25a2036aac3292a10a93e394a90750ca3
top=$HOME/rpmbuild
work=$top/gts9wifi-fingerprint-runtime

dnf -y install rpm-build rpmdevtools dnf5-plugins tar xz zstd cpio patch git curl findutils gnupg2 cmake gcc gcc-c++ clang lld llvm glib2-devel kernel-headers >/dev/null
git config --system user.name rpmbuild
git config --system user.email rpmbuild@localhost

rm -rf "$work" && mkdir -p "$work" "$out" "$top/SOURCES" "$top/SPECS" "$top/RPMS"

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
qcbor_lib=$(find "$deps" -name libqcbor.a -print -quit)
qtee_lib=$(find "$deps" -name libqcomtee.a -print -quit)
[ -n "$qcbor_lib" ] && [ -n "$qtee_lib" ] || {
    echo "static QTEE libraries were not installed" >&2
    exit 1
}

cc -std=c11 -Wall -Wextra -Werror -Wno-unused-function -O2 \
    "$here/libfprint/el721-secure-owner.c" \
    -I"$here/include" -I"$deps/include" \
    $(pkg-config --cflags glib-2.0) \
    "$qtee_lib" "$qcbor_lib" $(pkg-config --libs glib-2.0) -lpthread \
    -o "$work/gts9wifi-fingerprint-secure-owner"
strip --strip-unneeded "$work/gts9wifi-fingerprint-secure-owner"

cc -std=gnu11 -O2 -Wall -Wextra -Werror \
    "$here/binder-ctxmgr/gts9wifi-binder-ctxmgr.c" \
    -o "$work/gts9wifi-binder-ctxmgr"
strip --strip-unneeded "$work/gts9wifi-binder-ctxmgr"

shims=$work/shims
mkdir -p "$shims"
printf 'LIBC { global: write; snprintf; vsnprintf; abort; local: *; };\n' > "$shims/libc.map"
printf 'void write(void){}\nvoid snprintf(void){}\nvoid vsnprintf(void){}\nvoid abort(void){}\n' > "$shims/stub.c"
clang --target=aarch64-linux-android29 -w -fPIC -shared -nostdlib -fuse-ld=lld \
    -Wl,-soname,libc.so -Wl,--version-script="$shims/libc.map" \
    "$shims/stub.c" -o "$shims/libc.so"
clang --target=aarch64-linux-android29 -O2 -fPIC -fvisibility=hidden \
    -ffreestanding -Wall -Wextra -Werror -c "$here/liblog_capture.c" \
    -o "$shims/liblog_capture.o"
clang --target=aarch64-linux-android29 -fuse-ld=lld -shared -nostdlib \
    -Wl,-soname,liblog_capture.so -Wl,--hash-style=gnu -Wl,-z,now \
    "$shims/liblog_capture.o" -L"$shims" -lc -o "$shims/liblog_capture.so"
clang --target=aarch64-linux-android29 -O2 -fPIC -fvisibility=hidden \
    -ffreestanding -Wall -Wextra -Werror -shared -nostdlib -fuse-ld=lld \
    -Wl,-soname,libvmmem_shim.so "$here/libvmmem_shim.c" \
    -o "$shims/libvmmem_shim.so"

version=$(sed -n 's/^Version:[[:space:]]*//p' "$here/gts9wifi-fingerprint.spec" | head -1)
src=$work/gts9wifi-fingerprint-$version
rm -rf "$src"
mkdir -p "$src"
cp -a "$here/device/." "$src/"
install -m0755 "$work/gts9wifi-fingerprint-secure-owner" \
    "$work/gts9wifi-binder-ctxmgr" "$src/usr/libexec/"
mkdir -p "$src/usr/lib/gts9wifi/fingerprint"
install -m0755 "$shims/liblog_capture.so" "$shims/libvmmem_shim.so" \
    "$src/usr/lib/gts9wifi/fingerprint/"
(cd "$work" && tar -czf "$top/SOURCES/gts9wifi-fingerprint-$version.tar.gz" \
    "gts9wifi-fingerprint-$version")

dnf builddep -y --spec "$here/gts9wifi-fingerprint.spec" >/dev/null
rpmbuild -bb "$here/gts9wifi-fingerprint.spec"

rm -f "$out"/*.rpm "$out"/SHA256SUMS "$out"/BUILD-METADATA.txt
find "$top/RPMS" -name '*.rpm' -exec cp -t "$out" {} +
(
    cd "$out"
    sha256sum *.rpm > SHA256SUMS
    {
        echo "qcbor_commit: $qcbor_commit"
        echo "quic_teec_commit: $quic_teec_commit"
        echo "version: $version"
    } > BUILD-METADATA.txt
)

# The shims are preloaded into the tablet's Android runtime, where libc.so is
# the bionic libc; on Fedora that soname has no provider and dnf refuses the
# transaction, so fail the build if the spec filter ever stops matching.
if rpm -qpR "$out"/gts9wifi-fingerprint-[0-9]*.rpm | grep -qE '^libc[.]so[(]'; then
    echo "error: bionic libc.so dependency leaked into the runtime RPM" >&2
    exit 1
fi

ls -l "$out"
