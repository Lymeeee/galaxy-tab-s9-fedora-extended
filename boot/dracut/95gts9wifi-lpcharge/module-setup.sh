#!/bin/bash
# Off-mode charging screen, run before the root filesystem is mounted when
# ABL passes lpcharge=1.  The binary, its Cairo/Pango libraries and the font
# subsets all live inside the initramfs.

check() { return 0; }
depends() { echo base udev; }

install() {
    inst_multiple /usr/libexec/gts9wifi-lpcharge
    inst_simple /usr/share/gts9wifi/fonts.conf
    for font in /usr/share/fonts/gts9wifi/*; do
        inst_simple "$font"
    done
    for lib in $(ldd /usr/libexec/gts9wifi-lpcharge | awk '/=>/ {print $3}'); do
        [ -n "$lib" ] && inst_simple "$lib"
    done
    inst_hook pre-mount 99 "$moddir/lpcharge.sh"
}
