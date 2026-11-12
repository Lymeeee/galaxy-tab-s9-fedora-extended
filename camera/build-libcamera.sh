#!/bin/bash
# SPDX-License-Identifier: MIT
#
# Rebuild Fedora's libcamera 0.7.2 with the software-ISP fixes from the
# Galaxy Tab S9 Ultra port (agcarbajo/ubuntu-galaxy-tab-s9-ultra):
#   - HI1337 black-level and analogue-gain helpers (libipa camera sensor helper)
#   - grey-world AWB + conservative CCM tuning file for "hi1337-gts9u"
#   - contrast-detect autofocus for the DW9808 VCM in the simple IPA
#   - CAMSS link reset before configuring a different camera
# One combined, rebased patch is applied through the Fedora spec so the IPA
# keeps being signed by the package build.
set -euxo pipefail

srpm_url=https://kojipkgs.fedoraproject.org/packages/libcamera/0.7.2/2.fc44/src/libcamera-0.7.2-2.fc44.src.rpm
patch=/work/camera/gts9wifi-libcamera-0.7.2.patch
out=/work/out-camera

dnf -y install rpm-build dnf5-plugins curl bzip2 tar findutils

curl -fsSL -o /tmp/libcamera.src.rpm "$srpm_url"
rpm -i /tmp/libcamera.src.rpm
dnf -y builddep /root/rpmbuild/SPECS/libcamera.spec

cp "$patch" /root/rpmbuild/SOURCES/
spec=/root/rpmbuild/SPECS/libcamera.spec
sed -i '/^Patch02:/a Patch03: gts9wifi-libcamera-0.7.2.patch' "$spec"
sed -i 's/^Release:.*/Release: 3%{?dist}.gts9wifi1/' "$spec"

rpmbuild -bb "$spec"

mkdir -p "$out"
for pattern in 'libcamera-[0-9]*.aarch64.rpm' 'libcamera-ipa-[0-9]*.aarch64.rpm' \
               'libcamera-tools-[0-9]*.aarch64.rpm' 'libcamera-gstreamer-[0-9]*.aarch64.rpm' \
               'libcamera-v4l2-[0-9]*.aarch64.rpm' 'libcamera-qcam-[0-9]*.aarch64.rpm' \
               'python3-libcamera-[0-9]*.aarch64.rpm'; do
	cp /root/rpmbuild/RPMS/aarch64/$pattern "$out"/ 2>/dev/null || true
done
(cd "$out" && sha256sum *.rpm > LIBCAMERA-SHA256SUMS)
ls -l "$out"
