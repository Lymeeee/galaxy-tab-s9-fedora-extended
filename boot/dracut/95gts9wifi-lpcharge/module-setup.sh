#!/bin/bash
# Off-mode charging screen, run before the root filesystem is mounted when
# ABL passes lpcharge=1.  The binary, its Cairo/FreeType libraries and the
# font subsets all live inside the initramfs.

check() { return 0; }
# dracut-ng (107+) has no "udev" module; its udev userspace is "systemd-udevd".
depends() { echo base systemd-udevd; }

install() {
    inst_multiple /usr/libexec/gts9wifi-lpcharge
    for font in /usr/share/fonts/gts9wifi/*; do
        inst_simple "$font"
    done
    for lib in $(ldd /usr/libexec/gts9wifi-lpcharge | awk '/=>/ {print $3}'); do
        [ -n "$lib" ] && inst_simple "$lib"
    done
    inst_hook pre-mount 99 "$moddir/lpcharge.sh"
}
