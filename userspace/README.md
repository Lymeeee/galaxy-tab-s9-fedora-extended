# gts9wifi-userspace

Noarch RPM with the Phase 1 userspace pieces from the Ubuntu port:

- Tab9 Extras GNOME Shell extension v6 (screen-lock/keyboard controls,
  floating on-screen keyboard button, FOD overlay is a separate phase)
- `gts9wifi-device-control` with charge_limit / charge_bypass entries
- charger udev permissions for fast_charge, charge_limit, charge_bypass
- NetworkManager dispatcher that disables Wi-Fi background scanning

Build (Fedora container):

```sh
mkdir -p ~/rpmbuild/SOURCES
mkdir -p /tmp/src/gts9wifi-userspace-0.1.0
cp -a userspace/tree/. /tmp/src/gts9wifi-userspace-0.1.0/
tar -C /tmp/src -czf ~/rpmbuild/SOURCES/gts9wifi-userspace-0.1.0.tar.gz gts9wifi-userspace-0.1.0
rpmbuild -bb userspace/gts9wifi-userspace.spec
```

Install:

```sh
sudo dnf install ./gts9wifi-userspace-0.1.0-1.fc44.noarch.rpm
```

The keyboard firmware is not included. Copy the verified V37 blob to
`/lib/firmware/keyboard_stm/stm32_gts9family.bin` only after the matching
kernel is installed.
