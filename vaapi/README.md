# Qualcomm Iris VA-API driver (`qcom-va-driver`)

Packages [`radxa-pkg/qcom-va-driver`](https://github.com/radxa-pkg/qcom-va-driver)
for Fedora 44 (`aarch64`), exposing Qualcomm's stateful V4L2 M2M `iris_driver`
(`/dev/video17` / `/dev/video18`) as a standard VA-API backend
(`/usr/lib64/dri/qcom_drv_video.so` with automatic `msm_drv_video.so` alias).

## Kernel requirement

`qcom-va-driver` requires the five `qcom-iris` HFI gen2 patches staged in
`kernel/patches-gts9wifi/0019..0023` (decode-order output via
`V4L2_CID_MPEG_VIDEO_DEC_DISPLAY_DELAY`, 64-buffer CAPTURE pool, encoder
deblocking controls, error timestamps, and AV1 NOSHOW buffer recycling).

## Flatpak compatibility

Fedora 44 ships glibc 2.43 / `GLIBCXX_3.4.36`, which is newer than the
Freedesktop 25.08 Flatpak runtime (glibc 2.42 / `GLIBCXX_3.4.34`).
`.github/workflows/vaapi.yml` therefore also builds a compatibility copy on
Ubuntu 24.04 (`GLIBC_2.39` / `GLIBCXX_3.4.32`) and bundles it into the same
RPM under `/usr/lib64/qcom-va-driver-flatpak/`.

Enable it for all Flatpak apps with:

```sh
sudo flatpak override --system \
  --device=all \
  --filesystem=host-os:ro \
  --env=LIBVA_DRIVERS_PATH=/run/host/usr/lib64/qcom-va-driver-flatpak \
  --env=GST_VA_ALL_DRIVERS=1 \
  --env=GST_PLUGIN_FEATURE_RANK=vah264dec:1000,vah264enc:1000,vah265dec:1000,vah265enc:1000,vavp9dec:1000,vaav1dec:1000
```

## Verification

```sh
vainfo --display drm --device /dev/dri/renderD128
mpv --hwdec=auto input.mp4
```
