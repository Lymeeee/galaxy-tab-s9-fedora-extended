# FFmpeg VPU patches for Fedora 44

Fedora 44 ships FFmpeg (free variant) 8.1.3; Firefox 159 Recommends
`ffmpeg-free` and is expected to use the system `libavcodec` at runtime
(verify on the tablet). The Ubuntu port's two v4l2m2m fixes were rebased
against the upstream FFmpeg n8.1.3 source:

- `0001-v4l2-buffers-pass-timestamps-without-time-base.patch` — applies
  cleanly, unchanged from the Ubuntu port.
- `0002-v4l2m2m-drm-prime-output-ffmpeg-8.1.3.patch` — applies 9 of 10
  original hunks; the only failure is the missing include of
  `libavutil/hwcontext.h`, added in the rebased patch. Verified clean with
  `patch -p1` on a fresh FFmpeg n8.1.3 tree.

The patches are also verified on Fedora's actual source tree: after applying
Fedora's own patch stack (`ffmpeg-codec-choice`, fdk-aac, decklink,
openh264, streamcopy-pts, vulkan, chromium), `patch -p1` applies both
cleanly. The Fedora RPM build applies them the same way, after
`%autosetup -S git_am`.

Fedora's free build whitelists decoders in `enable_decoders` and omits
`h264_v4l2m2m`/`hevc_v4l2m2m`, so the patches would otherwise be dead code.
`build-rpms.sh` appends both decoders before the build. 0002 also needs
`h264_mp4toannexb_bsf`/`hevc_mp4toannexb_bsf`, which the v4l2m2m decoders
select automatically.

## Build

`build-rpms.sh` runs as root inside a Fedora 44 aarch64 container: it
downloads the pinned `ffmpeg-8.1.3-2.fc44.src.rpm`, adds a `.gts9wifi1`
release suffix, applies the patches, and runs `rpmbuild`. The CI workflow
`.github/workflows/ffmpeg.yml` does this on `ubuntu-24.04-arm` and publishes
the RPMs plus `SHA256SUMS`/`BUILD-METADATA.txt` to
`ffmpeg-8.1.3-gts9wifi-1`.

```sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work \
  quay.io/fedora/fedora:44 bash /work/ffmpeg/build-rpms.sh
# -> out-ffmpeg/libavcodec-free-8.1.3-2.gts9wifi1.fc44.aarch64.rpm ...
```

Override `SRPM_URL` to rebuild against a newer Fedora update. The rebuilt
RPMs are ABI-compatible with Fedora's 8.1.3 packages (same sonames); the
`.gts9wifi1` release makes them upgrade over the distro packages.

Installation goes through `gts9wifi-update`: the nonfree FFmpeg RPMs become
another userspace component, installed and version-locked after boot, along
with Firefox's `media.hardware-video-decoding.force-enabled` policy. The
kernel iris driver is already present; no kernel patch is involved.
