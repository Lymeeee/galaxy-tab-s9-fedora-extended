# gts9wifi Ubuntu-port patch set

These 17 patches are imported from `ygecesefa/gts9wifi-ubuntu-port`
(`kernel/patches-gts9wifi/`, v0.4.2 era). The Ubuntu port builds its gts9wifi
kernel by running nacht20-de's `kernel/prepare.sh` first and then applying
this series, so they are applied here at the same point: after the base
recipe has copied the out-of-tree drivers and board DTS, before the kernel
configuration is merged.

Two patches needed a local rebase because this branch's base differs slightly
from the tree the Ubuntu port generated them on:

- `0008`: appended the same reserved-memory reclaim block after the C-neon
  pogo `i2c15` node (the Ubuntu patch expected the file to end at the root
  node).
- `0016`: the upstream file contained a duplicated copy of the original Ultra
  patch after the re-diffed section, which BSD/GNU patch and `git apply`
  reject as malformed. Rebuilt as a clean, correctly counted patch from the
  re-diffed content with `git apply --recount`; the resulting change is
  identical.

Covered features: HI1337/DW9808 camera stream fixes (0001-0003), CCI
recovery (0004), ath11k WoW suspend (0005), touch wake gesture (0006),
SM5714 charge limit/bypass (0007), unused DTS carveouts (0008), generic
q6v5/fastrpc/GPU/GENI/qcomtee fixes (0009-0016), FTS1BA90A fingerprint
area (0017).  Upstream patch provenance and per-patch rationale are in each
file header; the originals remain GPL-2.0-only.
