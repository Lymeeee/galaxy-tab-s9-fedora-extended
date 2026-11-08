#!/bin/sh
# ABL appends lpcharge=1 to the cmdline when the tablet was started by a
# charger while powered off.  Show the charging UI and only continue booting
# when the user holds the power key for five seconds.
if grep -q 'lpcharge=1' /proc/cmdline; then
    /usr/libexec/gts9wifi-lpcharge
fi
