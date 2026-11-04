#!/bin/sh
# Bring up the RNDIS gadget early only when the caller asked for it with
# gts9wifi.usbnet=1 on the kernel cmdline.  The debug link keeps the UDC
# powered, so it is off by default.
case "$(cat /proc/cmdline 2>/dev/null)" in
    *gts9wifi.usbnet=1*) ;;
    *) return 0 ;;
esac
modprobe configfs 2>/dev/null
modprobe libcomposite 2>/dev/null
modprobe usb_f_rndis 2>/dev/null
[ -d /sys/kernel/config/usb_gadget ] || mount -t configfs configfs /sys/kernel/config 2>/dev/null
G=/sys/kernel/config/usb_gadget/g1
mkdir -p "$G/functions/rndis.usb0" "$G/configs/b.1/strings/0x409" "$G/strings/0x409" 2>/dev/null || return 0
echo "fedora-gts9wifi" > "$G/strings/0x409/serialnumber" 2>/dev/null
ln -sf "$G/functions/rndis.usb0" "$G/configs/b.1" 2>/dev/null
UDC=$(ls /sys/class/udc 2>/dev/null | head -1)
[ -n "$UDC" ] && echo "$UDC" > "$G/UDC" 2>/dev/null
sleep 1
ip link set usb0 up 2>/dev/null
ip addr add 172.16.42.1/24 dev usb0 2>/dev/null
