#!/bin/bash
# Rebuild Fedora 44's ffmpeg-free with the gts9wifi V4L2 M2M patches.
# Run as root inside a fedora:44 aarch64 container; writes out-ffmpeg/.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/.." && pwd)
out=${FFMPEG_OUTDIR:-$repo/out-ffmpeg}
srpm_url=${SRPM_URL:-https://dl.fedoraproject.org/pub/fedora/linux/updates/44/Everything/source/tree/Packages/f/ffmpeg-8.1.3-2.fc44.src.rpm}
top=$HOME/rpmbuild
work=$top/gts9wifi-build

dnf -y install rpm-build rpmdevtools dnf5-plugins tar xz zstd cpio patch git curl findutils gnupg2 >/dev/null
git config --system user.name rpmbuild
git config --system user.email rpmbuild@localhost

rm -rf "$work" && mkdir -p "$work" "$out"
curl -fL --retry 3 -o "$work/ffmpeg.src.rpm" "$srpm_url"
rm -rf "$top/SPECS" "$top/SOURCES"
rpm -ivh --nosignature --nodeps "$work/ffmpeg.src.rpm" >/dev/null

spec=$top/SPECS/ffmpeg.spec
cp "$here"/patches/0001-*.patch "$top/SOURCES/gts9wifi-0001-v4l2-buffers-timestamps.patch"
cp "$here"/patches/0002-*.patch "$top/SOURCES/gts9wifi-0002-v4l2m2m-drm-prime-output.patch"

# Apply our patches after Fedora's stack with patch(1): 0002 is a plain git
# diff, which %autosetup -S git_am does not reliably parse.
python3 - "$spec" <<'PY'
import re
import sys

path = sys.argv[1]
lines = open(path).read().splitlines(keepends=True)
out = []
bumped = False
for line in lines:
    if line.startswith("Release:") and not bumped:
        line = re.sub(r"^Release:(\s*)(\d[^%\s]*)%\{\?dist\}",
                      r"Release:\1\2.gts9wifi1%{?dist}", line)
        bumped = True
    out.append(line)
    if line.startswith("Patch1002:"):
        out.append("Source1003:     gts9wifi-0001-v4l2-buffers-timestamps.patch\n")
        out.append("Source1004:     gts9wifi-0002-v4l2m2m-drm-prime-output.patch\n")
    if line.startswith("%autosetup"):
        out.append("patch -p1 < %{SOURCE1003} || exit 1\n")
        out.append("patch -p1 < %{SOURCE1004} || exit 1\n")
open(path, "w").writelines(out)
PY

# Fedora's free build whitelists decoders and omits the v4l2m2m H.264/HEVC
# ones, which would leave the patches unused.
grep -q '^h264_v4l2m2m' "$top/SOURCES/enable_decoders" || \
    printf 'h264_v4l2m2m # hardware\nhevc_v4l2m2m # hardware\n' >> "$top/SOURCES/enable_decoders"

dnf builddep -y --spec "$spec" >/dev/null
rpmbuild -bb "$spec"

rm -f "$out"/*.rpm "$out"/SHA256SUMS "$out"/BUILD-METADATA.txt
find "$top/RPMS" -name '*.rpm' -exec cp -t "$out" {} +

(
    cd "$out"
    sha256sum *.rpm > SHA256SUMS
    {
        echo "source_srpm: $srpm_url"
        echo "source_srpm_sha256: $(sha256sum "$work/ffmpeg.src.rpm" | cut -d' ' -f1)"
        echo "source_version: $(rpm -qp --qf '%{VERSION}-%{RELEASE}' "$work/ffmpeg.src.rpm")"
        echo "patch_0001_sha256: $(sha256sum "$here"/patches/0001-*.patch | cut -d' ' -f1)"
        echo "patch_0002_sha256: $(sha256sum "$here"/patches/0002-*.patch | cut -d' ' -f1)"
        echo "extra_decoders: h264_v4l2m2m hevc_v4l2m2m"
    } > BUILD-METADATA.txt
)

ls -l "$out"
