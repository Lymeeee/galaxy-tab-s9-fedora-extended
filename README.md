> [!IMPORTANT]
> ### 开宗明义：完全可以日用。
> ### 严重警告：安装Linux需要解锁BL，需要一个可以用的Recovery，而且安装时会清空你平板上的的所有数据。运行安装脚本需要一台Linux系统的电脑，或者mac也行，实在不行安卓手机装个termux也不是不能跑

---


## 状态

我自己在用，所以说稳定性没必要担心，哪里不能用的话我比你还急

| 硬件/功能 | 状态 |
|---|---|
| CPU | 正常 |
| GPU | 正常 |
| WLAN | 正常 |
| 蓝牙 | 不完全正常，更新完开机以后需要再重启一次要不然用不了 |
| 休眠 | 是深睡，具体睡眠掉电多不多还没认真测 |
| 扬声器 | 正常，就是声音有点空 |
| 震动 | 应该正常，但好像也没啥用 |
| 相机和闪光灯 | 应该正常，还没测 |
| 充电 | 最高可以握手45W PPS，真正进去电池的应该不到三十瓦，而且可以开启满电自动直供电 |
| 屏幕 | 正常，三星不给HDR我真的很生气，亮度低于36%离开DC调光的时候会提醒你保护视力 |
| 官方皮套键盘 | 要安装一下V37固件，我忘记去哪里找了，你可以让AI在Vendor分区翻一翻，反正按键正常，合盖休眠开盖唤醒也正常 |
| USBC接口 | 满速3.2，干啥都行，包括扩展坞，外接屏幕什么的 |
| 传感器 | 没认真测试过，不确定是不是都好用 |

  注意：关机充电我没做，插入充电器直接开机属于正常，确定你设置了插入电源时自动熄灭屏幕或者休眠超时，要不然到时候烧屏了别去贴吧挂我。

---

## Getting the images

[Releases](https://github.com/Lymeeee/galaxy-tab-s9-fedora-extended/releases)
carries everything needed. Releases follow a fixed naming scheme:

- **`latest`** — the rolling channel used by `gts9wifi-update`: newest
  `gts9wifi-userspace` and `gts9wifi-dynpart` RPMs, the charger preview, and
  the current kernel pair. Old package versions are pruned automatically.
- **`kernel-7.2.0-<YYYYMMDD>.<run>`** — one immutable kernel build: boot
  images, `linux-gts9wifi-7.2.0-<build>.fc44.aarch64.rpm`,
  `gts9wifi-fedora-7.2.0-<build>.zip`, `BUILD-METADATA.txt` and
  `BUNDLE-SHA256SUMS`. Use this tag with `gts9wifi-update kernel --tag ...`
  to pin or roll back a specific build.
- **`ffmpeg-…`, `libfprint-…`, `gts9wifi-fingerprint-…`** — third-party RPM
  builds referenced by the updater.

`<build>` is `<YYYYMMDD>.<GitHub run number>`; the same identifier appears in
the kernel RPM release, the TWRP zip filename and `BUILD-METADATA.txt`.
Historical `kernel-7.2.0-merge-*` and `rootfs-*` tags are kept for reference
only.

The full walk-through is in [INSTALL.md](INSTALL.md).

---

## Building from source

Everything builds on native arm64 in GitHub Actions (`workflow_dispatch`):
**Fedora rootfs**, **Kernel build** (RPM + initramfs + bundle + TWRP zip), and
**Boot bundle** (fast path against a pinned released RPM). Locally, the rootfs
build needs an arm64 Fedora container:

```sh
./rootfs/fetch-local-assets.sh
podman run --rm -it -v "$PWD:/work:Z" -w /work quay.io/fedora/fedora:44 \
    ./rootfs/build-rootfs.sh
sudo ./rootfs/mk-sd-card.sh out/gts9wifi-fedora-44-rootfs.tar.gz /dev/sdX
```

`GTS9_USER` (default `fedora`) names the first-boot user, and
`GTS9_DESKTOP=core` builds a small headless debug image.

Device blobs are never committed: everything the rootfs needs is either
extracted from the tablet's own stock partitions (`apnhlos`, `dsp`, `persist`)
or fetched from a pinned source with a verified checksum.

---

## 前人栽树后人乘凉

- 感谢[Azkali](https://github.com/Azkali)对这个平板的的主线化工作，以及对系统固件的慷慨提供
- 感谢[agcarbajo](https://github.com/agcarbajo)在他的Tab S9 Ultra仓库的辛勤耕耘。这个仓库的功能修复很大一部分来源于此。

---

## License

MIT — see [LICENSE](LICENSE). Files under `kernel/` are kernel sources and
carry their own SPDX identifiers (GPL-2.0 for drivers, BSD-3-Clause for device
trees); those identifiers govern those files.