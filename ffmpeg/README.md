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

Next step: rebuild Fedora's `libavcodec-free`/`libavutil-free` RPMs with
these patches in an arm64 CI job, then install and enable
`media.hardware-video-decoding.force-enabled` for Firefox. The kernel iris
driver is already present; no kernel patch is involved.
