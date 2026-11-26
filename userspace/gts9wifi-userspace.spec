%define debug_package %{nil}

Name:           gts9wifi-userspace
Version:        0.17.104
Release:        1%{?dist}
Summary:        Galaxy Tab S9 Wi-Fi device controls, updates and GNOME integration
License:        MIT
URL:            https://github.com/Lymeeee/galaxy-tab-s9-fedora-extended
BuildArch:      aarch64
Source0:        %{name}-%{version}.tar.gz
Source1:        gts9-cpuinfo.c
BuildRequires:  systemd-rpm-macros
BuildRequires:  gcc
BuildRequires:  glib2-devel
BuildRequires:  libgtop2-devel
BuildRequires:  checkpolicy
BuildRequires:  policycoreutils
Requires:       glib2
Requires:       gnome-shell
Requires:       gnome-control-center
Requires:       NetworkManager
Requires:       wpa_supplicant
Requires:       bash
Requires:       curl
Requires:       python3
Requires:       python3-rpm
Requires:       unzip
Requires:       util-linux
Requires:       dtc
Requires:       libcap
Requires:       iw
Requires:       systemd
Requires:       polkit
Requires:       alsa-utils
Requires:       plymouth
Requires:       irqbalance
Requires:       plymouth-plugin-script
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       libwacom-data
Requires:       bluez
Requires:       python3-dbus
Requires:       chrony
Requires:       zram-generator
Requires:       pipewire-module-filter-chain-lv2
Requires:       lv2-calf-plugins
Requires:       tuned-ppd

%description
Tab9 Extras GNOME Shell extension (v6), the gts9wifi device-control helper
with charge limit/bypass, charger udev permissions, the Wi-Fi background
scan dispatcher and the gts9wifi-update tool (userspace RPM install,
versionlock, kernel boot-bundle self-flash and rollback, and the rebuilt
ffmpeg-free codec packages).  Imported from the
ygecesefa/gts9wifi-ubuntu-port userspace and adapted for Fedora.

The proprietary V37 keyboard firmware is not part of this package; install
stm32_gts9family.bin into /lib/firmware/keyboard_stm/ separately.

%prep
%setup -q

%build
gcc %{optflags} -fPIC -shared -Wall -Wextra -o libgts9-cpuinfo.so %{SOURCE1} \
    $(pkg-config --cflags glib-2.0 libgtop-2.0) \
    $(pkg-config --libs glib-2.0) -ldl
checkmodule -M -m -o gts9wifi.mod selinux/gts9wifi.te
semodule_package -o gts9wifi.pp -m gts9wifi.mod -f selinux/gts9wifi.fc

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a . %{buildroot}/
rm -f %{buildroot}/libgts9-cpuinfo.so \
      %{buildroot}/gts9wifi.mod %{buildroot}/gts9wifi.pp
rm -rf %{buildroot}/selinux
install -d %{buildroot}%{_libdir}/gts9wifi
install -m 0755 libgts9-cpuinfo.so %{buildroot}%{_libdir}/gts9wifi/libgts9-cpuinfo.so
install -d %{buildroot}%{_datadir}/gts9wifi/selinux
install -m 0644 gts9wifi.pp %{buildroot}%{_datadir}/gts9wifi/selinux/gts9wifi.pp

%post
if command -v semodule >/dev/null 2>&1; then
    if semodule -i %{_datadir}/gts9wifi/selinux/gts9wifi.pp >/dev/null 2>&1; then
        for path in /run/gts9wifi-fingerprint /run/gts9wifi-fingerprint-ui \
                    /var/lib/gts9wifi/fingerprint; do
            [ -e "$path" ] && restorecon -RF "$path" >/dev/null 2>&1 || :
        done
        [ -e /dev/esfp0 ] && restorecon -F /dev/esfp0 >/dev/null 2>&1 || :
        [ -e /dev/tee0 ] && restorecon -F /dev/tee0 >/dev/null 2>&1 || :
        # A fresh image boots permissive, relabels the tree, then reboots.
        # Only switch to enforcing once that relabel is done and the module
        # is loaded; the stamp keeps a later manual revert intact.
        if selinuxenabled 2>/dev/null && [ ! -e /.autorelabel ] \
               && [ ! -e /var/lib/gts9wifi/selinux-enforcing ] \
               && grep -q '^SELINUX=permissive' /etc/selinux/config; then
            install -d /var/lib/gts9wifi
            sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
            touch /var/lib/gts9wifi/selinux-enforcing
            echo "SELinux will run enforcing from the next boot" >&2
        fi
    else
        echo "warning: could not load the gts9wifi SELinux policy" >&2
    fi
fi
glib-compile-schemas %{_datadir}/glib-2.0/schemas >/dev/null 2>&1 || :
if command -v dconf >/dev/null 2>&1; then
    dconf update >/dev/null 2>&1 || :
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database %{_datadir}/applications >/dev/null 2>&1 || :
fi
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block >/dev/null 2>&1 || :
# 0.17.2: double-tap-to-wake was removed from the kernel driver.
rm -f /usr/lib/udev/rules.d/71-gts9wifi-touchscreen-perms.rules
systemctl daemon-reload >/dev/null 2>&1 || :
# The dynpart mount units depend on a mapper device unit this kernel never
# creates; mount the mapper directly from the userspace helper instead.
systemctl disable vendor.mount vendor-dsp.mount vendor-firmware_mnt.mount \
    >/dev/null 2>&1 || :
systemctl stop vendor.mount vendor-dsp.mount vendor-firmware_mnt.mount \
    >/dev/null 2>&1 || :
systemctl reset-failed vendor.mount vendor-dsp.mount \
    vendor-firmware_mnt.mount >/dev/null 2>&1 || :
if [ -x %{_libexecdir}/gts9wifi-android-mounts ]; then
    %{_libexecdir}/gts9wifi-android-mounts >/dev/null 2>&1 || :
fi
systemctl enable --now gts9wifi-charge-guard.timer >/dev/null 2>&1 || :
systemctl --global enable gts9wifi-charge-mode.service >/dev/null 2>&1 || :
systemctl enable gts9wifi-speaker-protection.service >/dev/null 2>&1 || :
systemctl enable gts9wifi-keyboard-fw.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-spen-remote.service >/dev/null 2>&1 || :
systemctl try-restart gts9wifi-spen-remote.service >/dev/null 2>&1 || :
systemctl enable gts9wifi-nologs.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-mem-sleep-deep.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-device-name.service >/dev/null 2>&1 || :
systemctl enable gts9wifi-rtc-time.service >/dev/null 2>&1 || :
systemctl enable --now gts9wifi-rtc-anchor.timer >/dev/null 2>&1 || :
systemctl enable gts9wifi-cover-boot-guard.service >/dev/null 2>&1 || :
systemctl enable --now irqbalance.service >/dev/null 2>&1 || :
# Wire GNOME's native power-profile switcher (tuned-ppd) to the GTS9
# SM8550-AC profiles and retire the standalone boot-time power service.
if [ -d /etc/tuned ]; then
    cat > /etc/tuned/ppd.conf <<'EOF'
[main]
default=balanced
battery_detection=false
sysfs_acpi_monitor=false

[profiles]
power-saver=gts9wifi-powersave
balanced=gts9wifi-balanced
performance=gts9wifi-performance
EOF
fi
systemctl disable gts9wifi-power.service >/dev/null 2>&1 || :
systemctl enable --now tuned.service tuned-ppd.service >/dev/null 2>&1 || :
systemctl try-restart tuned-ppd.service >/dev/null 2>&1 || :
# Keep the PMIC counter continuous; the anchor stores its own UTC relation.
if [ -f /etc/chrony.conf ] && \
   grep -qE '^[[:space:]]*rtcsync[[:space:]]*$' /etc/chrony.conf; then
    sed -i 's/^[[:space:]]*rtcsync[[:space:]]*$/# rtcsync disabled by gts9wifi (PMIC RTC anchor)/' /etc/chrony.conf
    systemctl try-restart chronyd.service >/dev/null 2>&1 || :
fi
if getent group video >/dev/null 2>&1 && command -v usermod >/dev/null 2>&1; then
    while IFS=: read -r account _ uid _; do
        [ "$uid" -ge 1000 ] && [ "$uid" -lt 60000 ] || continue
        usermod -aG video "$account" >/dev/null 2>&1 || :
    done < /etc/passwd
fi
if [ -x %{_libexecdir}/gts9wifi-wifi-bdf ]; then
    %{_libexecdir}/gts9wifi-wifi-bdf >/dev/null 2>&1 || :
fi
if [ -x %{_libexecdir}/gts9wifi-speaker-routing ]; then
    %{_libexecdir}/gts9wifi-speaker-routing >/dev/null 2>&1 || :
fi
if command -v alsactl >/dev/null 2>&1; then
    alsactl store >/dev/null 2>&1 || :
fi
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme gts9wifi >/dev/null 2>&1 || :
fi
# Older rootfs tarballs (and TWRP's tar) dropped security.capability; re-apply
# what RPM recorded so newuidmap/newgidmap and rootless containers work
# without reinstalling or reflashing the affected packages.
if command -v rpm >/dev/null 2>&1 && command -v setcap >/dev/null 2>&1; then
    rpm -qa --qf '[%%{FILENAMES} %%{FILECAPS}\n]' 2>/dev/null |
    while read -r cap_path cap_value; do
        case "$cap_value" in
            cap_*) ;;
            *) continue ;;
        esac
        [ -f "$cap_path" ] || continue
        setcap "$cap_value" "$cap_path" >/dev/null 2>&1 || :
    done
fi

%postun
if [ "$1" = 0 ] && command -v semodule >/dev/null 2>&1; then
    semodule -r gts9wifi >/dev/null 2>&1 || :
fi
glib-compile-schemas %{_datadir}/glib-2.0/schemas >/dev/null 2>&1 || :
if command -v dconf >/dev/null 2>&1; then
    dconf update >/dev/null 2>&1 || :
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database %{_datadir}/applications >/dev/null 2>&1 || :
fi
systemctl daemon-reload >/dev/null 2>&1 || :
if [ "$1" = 0 ]; then
    systemctl disable --now gts9wifi-charge-guard.timer >/dev/null 2>&1 || :
    systemctl --global disable gts9wifi-charge-mode.service >/dev/null 2>&1 || :
    systemctl disable gts9wifi-keyboard-fw.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-spen-remote.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-nologs.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-mem-sleep-deep.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-device-name.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-rtc-time.service >/dev/null 2>&1 || :
    systemctl disable --now gts9wifi-rtc-anchor.timer >/dev/null 2>&1 || :
    systemctl disable gts9wifi-cover-boot-guard.service >/dev/null 2>&1 || :
fi
if [ "$1" = 0 ] && command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme spinner >/dev/null 2>&1 || :
fi

%files
%{_bindir}/gts9wifi-update
%{_bindir}/gts9wifi-settings
%{_prefix}/local/bin/gnome-control-center
%{_libdir}/gts9wifi/libgts9-cpuinfo.so
%{_datadir}/applications/gts9wifi-settings.desktop
%{_datadir}/icons/hicolor/scalable/apps/gts9wifi-settings.svg
%{_datadir}/libwacom/samsung-gts9wifi-spen.tablet
%{_datadir}/libwacom/samsung-gts9wifi-spen.stylus
%dir %{_datadir}/gnome-shell/extensions/galaxy-tab-extension@tabs9linux
%{_datadir}/gnome-shell/extensions/galaxy-tab-extension@tabs9linux/*
%config %{_sysconfdir}/dconf/db/gdm.d/99-galaxy-tab-extension
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.gts9wifi.gschema.xml
%{_datadir}/glib-2.0/schemas/99-gts9wifi.gschema.override
%dir %{_datadir}/gts9wifi
%dir %{_datadir}/gts9wifi/selinux
%{_datadir}/gts9wifi/selinux/gts9wifi.pp
%dir %{_datadir}/gts9wifi/versionlock.d
%{_datadir}/gts9wifi/versionlock.d/README
%dir %{_datadir}/plymouth/themes/gts9wifi
%{_datadir}/plymouth/themes/gts9wifi/*
%{_libexecdir}/gts9wifi-device-control
%{_libexecdir}/gts9wifi-panel-coldboot-check
%{_libexecdir}/gts9wifi-bt-provision
%{_libexecdir}/gts9wifi-spen-remote
%{_libexecdir}/gts9wifi-spen-button
%{_libexecdir}/gts9wifi-logging
%{_libexecdir}/gts9wifi-camera-resume
%{_libexecdir}/gts9wifi-camera-calib
%{_libexecdir}/gts9wifi-mem-sleep
%{_libexecdir}/gts9wifi-office
%{_libexecdir}/gts9wifi-librepods
%{_libexecdir}/gts9wifi-device-name
%{_libexecdir}/gts9wifi-android-mounts
%{_libexecdir}/gts9wifi-rtc-time
%{_libexecdir}/gts9wifi-charge-guard
%{_libexecdir}/gts9wifi-charge-mode
%{_libexecdir}/gts9wifi-cover-boot-guard
%{_libexecdir}/gts9wifi-keyboard-fw
%{_libexecdir}/gts9wifi-wifi-bdf
%{_libexecdir}/gts9wifi-privileged
%{_libexecdir}/gts9wifi-mirrors
%{_libexecdir}/gts9wifi-protect
%{_libexecdir}/gts9wifi-zh-translations
%{_libexecdir}/gts9wifi-ime
%{_libexecdir}/gts9wifi-power-key
%{_libexecdir}/gts9wifi-powerkey-mode
%{_libexecdir}/gts9wifi-speaker-routing
%{_libexecdir}/gts9wifi-speaker-protection
%{_libexecdir}/gts9wifi-sd-uuid-fix
%dir %{_datadir}/alsa/ucm2/Qualcomm/sm8550/GTS9
%{_datadir}/alsa/ucm2/Qualcomm/sm8550/GTS9/HiFi.conf
%{_datadir}/alsa/ucm2/Qualcomm/sm8550/GTS9/Samsung-Galaxy-Tab-S9.conf
%{_datadir}/alsa/ucm2/conf.d/sm8550/Samsung-Galaxy-Tab-S9.conf
%dir %{_unitdir}/alsa-restore.service.d
%{_unitdir}/alsa-restore.service.d/90-gts9wifi-speaker-routing.conf
%{_userunitdir}/gts9wifi-power-key.service
%{_userunitdir}/gts9wifi-charge-mode.service
%{_udevrulesdir}/72-gts9wifi-power-key.rules
%{_bindir}/gts9wifi-power
%{_unitdir}/gts9wifi-fast-charge-default.service
%{_unitdir}/gts9wifi-power.service
%{_unitdir}/gts9wifi-speaker-protection.service
%{_unitdir}/gts9wifi-sd-uuid-fix@.service
%{_unitdir}/gts9wifi-charge-guard.service
%{_unitdir}/gts9wifi-charge-guard.timer
%{_unitdir}/gts9wifi-cover-boot-guard.service
%{_unitdir}/gts9wifi-keyboard-fw.service
%{_unitdir}/gts9wifi-spen-remote.service
%{_unitdir}/gts9wifi-nologs.service
%{_unitdir}/gts9wifi-mem-sleep-deep.service
%{_unitdir}/gts9wifi-device-name.service
%{_unitdir}/gts9wifi-rtc-time.service
%{_unitdir}/gts9wifi-rtc-anchor.service
%{_unitdir}/gts9wifi-rtc-anchor.timer
%{_udevrulesdir}/90-gts9wifi-spen-no-wakeup.rules
%{_prefix}/lib/modules-load.d/90-gts9wifi-rtc.conf
%dir %{_unitdir}/gts9wifi-panel-coldboot-recover.service.d
%{_unitdir}/gts9wifi-panel-coldboot-recover.service.d/10-gts9wifi-fast-path.conf
%{_udevrulesdir}/72-gts9wifi-charger-perms.rules
%{_udevrulesdir}/60-gts9wifi-sd-uuid.rules
%{_udevrulesdir}/90-gts9wifi-hide-internal.rules
%{_udevrulesdir}/90-gts9wifi-hide-camss-video.rules
%{_udevrulesdir}/90-gts9wifi-usb-pm.rules
%{_prefix}/lib/modprobe.d/90-gts9wifi-blacklist-qcrypto.conf
%config(noreplace) %{_sysconfdir}/NetworkManager/dispatcher.d/90-gts9wifi-no-bgscan
%config(noreplace) %{_sysconfdir}/NetworkManager/conf.d/90-gts9wifi-powersave.conf
%config(noreplace) %{_sysconfdir}/systemd/zram-generator.conf.d/10-gts9wifi-zstd.conf
%config(noreplace) %{_sysconfdir}/sysctl.d/99-gts9wifi-zram.conf
%config(noreplace) %{_sysconfdir}/systemd/logind.conf.d/11-gts9wifi-lid-holdoff.conf
%dir %{_sysconfdir}/systemd/system/gts9wifi-android-parts.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/gts9wifi-wait-sensor-proxy.service
%config(noreplace) %{_sysconfdir}/systemd/system/gts9wifi-android-parts.service.d/10-gts9wifi-mounts.conf
%dir %{_sysconfdir}/systemd/system/pd-mapper.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/pd-mapper.service.d/10-gts9wifi-selinux.conf
%dir %{_sysconfdir}/systemd/system/hexagonrpcd-adsp-sensorspd.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/hexagonrpcd-adsp-sensorspd.service.d/20-gts9wifi-selinux.conf
%dir %{_sysconfdir}/systemd/system/hexagonrpcd-adsp-rootpd.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/hexagonrpcd-adsp-rootpd.service.d/10-gts9wifi-selinux.conf
%attr(0755, root, root) %{_libexecdir}/gts9wifi-camera-suspend-pre
%dir %{_unitdir}/systemd-suspend.service.d
%{_unitdir}/systemd-suspend.service.d/10-gts9wifi-camera-suspend.conf
%{_prefix}/lib/systemd/system-sleep/gts9wifi-camera-suspend
%attr(0755, root, root) %{_prefix}/lib/systemd/system-sleep/gts9wifi-speaker-protection
%dir %{_datadir}/pipewire
%dir %{_datadir}/pipewire/client.conf.d
%{_datadir}/pipewire/client.conf.d/90-gts9wifi-upmix.conf
%dir %{_datadir}/pipewire/pipewire-pulse.conf.d
%{_datadir}/pipewire/pipewire-pulse.conf.d/90-gts9wifi-upmix.conf
%dir %{_datadir}/pipewire/pipewire.conf.d
%{_datadir}/pipewire/pipewire.conf.d/90-gts9wifi-speaker-eq.conf
%dir %{_datadir}/wireplumber
%dir %{_datadir}/wireplumber/wireplumber.conf.d
%{_datadir}/wireplumber/wireplumber.conf.d/90-gts9wifi-alsa-headroom.conf
%{_prefix}/lib/firmware/qcom/sm8550/Samsung-Galaxy-Tab-S9-tplg.bin
%dir %{_prefix}/lib/tuned/profiles/gts9wifi-powersave
%{_prefix}/lib/tuned/profiles/gts9wifi-powersave/tuned.conf
%attr(0755, root, root) %{_prefix}/lib/tuned/profiles/gts9wifi-powersave/script.sh
%dir %{_prefix}/lib/tuned/profiles/gts9wifi-balanced
%{_prefix}/lib/tuned/profiles/gts9wifi-balanced/tuned.conf
%attr(0755, root, root) %{_prefix}/lib/tuned/profiles/gts9wifi-balanced/script.sh
%dir %{_prefix}/lib/tuned/profiles/gts9wifi-performance
%{_prefix}/lib/tuned/profiles/gts9wifi-performance/tuned.conf
%attr(0755, root, root) %{_prefix}/lib/tuned/profiles/gts9wifi-performance/script.sh

%changelog
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.104-1
- Set device.form-factor = "speaker" and device.icon-name = "audio-speakers"
  on the gts9wifi_speaker_eq virtual sink so GNOME displays the speaker icon
  instead of the generic sound-card icon.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.103-1
- Refine gts9wifi-power balanced cluster caps to SM8550 TSMC N4P per-cluster
  efficiency sweet spots: A510 1.34 GHz (1344 MHz), A715+A710 1.92 GHz
  (1920 MHz, under the ~2.05 GHz knee), and X3 1.98 GHz (1977.6 MHz, under
  the ~2.0 GHz voltage cliff), keeping uclamp_max=460 and 8 ms schedutil.
- Lower powersave A510 cap to 1.11 GHz (1113.6 MHz).
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.102-1
- Make gts9wifi-power balanced profile genuinely conservative (~3 W target) and
  distinct from performance: disable boost, cap clusters at high-efficiency
  sweet spots (1.56 / 1.65 / 1.59 GHz), raise schedutil rate_limit_us to 8 ms,
  lower sched_util_clamp_max to 460 so EAS avoids waking CPU7 (X3) and keeps
  tasks in low OPPs, and cap GPU at 550 MHz @ 15 ms.
- Tighten powersave profile (uclamp_max=320, ~1.25 GHz caps, GPU <= 401 MHz)
  and ensure performance resets scaling_max_freq and uclamp_max back to full.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.101-1
- Hide raw CS35L45 Direct sink (media.class = Audio/Sink/Internal) by default
  in WirePlumber to prevent accidentally switching to the 100% hardware sink,
  and flip the gts9wifi-settings toggle to an opt-in debug "show direct" switch.
- Set state.default-volume = 0.027 (30% cubic) on gts9wifi_speaker_eq so fresh
  installs or state resets never initialize the speaker sink at 100% volume.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.100-1
- Gate the system 90-gts9wifi-speaker-eq.conf filter-chain on
  `gts9wifi.speaker-eq.custom = !true` and make gts9wifi-settings automatically
  inject `gts9wifi.speaker-eq.custom = true` into user copies so PipeWire never
  loads duplicate speaker EQ sinks when editing or reloading tuning.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.99-1
- Move fingerprint and camera calibration actions into a dedicated "硬件校准"
  group on the 配置 tab in gts9wifi-settings, keeping 高级 focused on updates,
  kernel flashing/rollback, and logging.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.98-1
- Replace typed-word confirmation (FLASH/ROLLBACK) in gts9wifi-settings with
  direct red destructive confirmation buttons for kernel flash and rollback.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.97-1
- Rename default PipeWire tuned speaker sink from "平板内置扬声器" to "内置扬声器".
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.96-1
- Disable unused ALSA Compress-Offload virtual card (alsa_card.comprC*) in
  WirePlumber, shorten default tuned speaker sink name to "平板内置扬声器"
  and raw hardware sink name to "CS35L45 Direct", and add a toggle in
  gts9wifi-settings to hide/show "CS35L45 Direct" via Audio/Sink/Internal.
- Auto-import the Pogo keyboard V37 firmware (stm32_gts9family.bin) from
  /vendor/firmware/keyboard_stm/ on boot in gts9wifi-keyboard-fw so fresh
  installs require zero manual firmware copying.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.95-1
- Switch ALSA UCM2 (HiFi.conf / Samsung-Galaxy-Tab-S9.conf) to 4-channel
  PRIMARY_TDM_RX_0 (PlaybackChannels 4, ASP_RX1 per-slot routing) and upgrade
  PipeWire 90-gts9wifi-speaker-eq.conf filter-chain from 2.0 to 4.0
  ([FL FR RL RR]) so GNOME speaker test and 4-channel playback drive all four
  speakers independently.
- Add one-click LibrePods (AirPods companion) installer in gts9wifi-settings
  (/usr/libexec/gts9wifi-librepods) downloading the aarch64 RPM from GitHub
  Releases and configuring BlueZ Apple DeviceID.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.94-1
- Switch CPU scaling across all profiles to EAS-preserving schedutil (with
  fast 2 ms rate_limit_us and 3.36 GHz boost on demand in balanced, 2.95 GHz
  cap in powersave, and elevated floor clocks in performance) and real GPU
  devfreq min/max/polling tuning (10 ms for 120 Hz in balanced/performance,
  475 MHz cap in powersave).
- Keep Wi-Fi power_save off in both balanced and performance (and on only in
  powersave), setting NetworkManager wifi.powersave=1 (ignore) so it does not
  override profile selection on reconnect.
- Integrate with GNOME's native power-profile switcher via tuned-ppd
  (gts9wifi-{powersave,balanced,performance} profiles) and remove the
  redundant performance-mode dropdown from gts9wifi-settings.
* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.93-1
- Ship built-in PipeWire speaker tuning (Calf Bass Enhancer LV2 + 9-band
  biquad EQ in 90-gts9wifi-speaker-eq.conf) and q6apm ALSA headroom drop-in
  (90-gts9wifi-alsa-headroom.conf), auto-loaded for all installs without
  EasyEffects buffer-underrun crackling.
- Replace EasyEffects installer in gts9wifi-settings with built-in speaker
  tuning editor and PipeWire reload actions; require
  pipewire-module-filter-chain-lv2 and lv2-calf-plugins.

* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.92-1
- Revert DACPCM Source back to ASP_RX1/ASP_RX2 bypass: routing through DSP_TX1
  without full CSPL_ENABLE/DSP_RX initialization caused crackling on
  volume/seek/play-pause transients and eventually tripped DSP mute.

* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.91-1
- Enable CS35L45 hardware speaker protection (DACPCM Source = DSP_TX1) across
  UCM2 and gts9wifi-speaker-routing after live playback verification confirmed
  per-unit factory Rdc selection (AL_SET_STATUS=2), zero CSPL_ERRORNO, and live
  voice-coil temperature tracking.

* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.90-1
- Build and ship Samsung-Galaxy-Tab-S9-tplg.bin with both 4-channel discrete
  PRIMARY_TDM_RX_0 (MODULE_ID_TDM_SINK 0x0700100E) and backwards-compatible
  2-channel PRIMARY_MI2S_RX, plus 2..4ch MultiMedia1/2/5 stream subgraphs.

* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.89-1
- Make gts9wifi-speaker-protection.service Type=simple so it does not block
  boot, and wait up to 90s on boot (15s on resume) for CS35L45 DSP1 controls
  to appear instead of timing out after 10s before the sound card finishes
  probing.

* Thu Nov 26 2026 Lymeeee <mr_xunyu@163.com> - 0.17.88-1
- Rebuild userspace RPM cleanly after GitHub Actions outage (includes all
  0.17.87 CS35L45 calibration/resume hook, PipeWire 4.0 upmix, and irqbalance
  preset changes).

* Wed Nov 25 2026 Lymeeee <mr_xunyu@163.com> - 0.17.87-1
- Fix CS35L45 speaker-protection CAL_CHECKSUM formula (CAL_R + 1, matching
  Linux cs-amp-lib.c) and write order (CAL_AMBIENT -> CAL_R -> CAL_STATUS ->
  CAL_CHECKSUM), and add a non-blocking systemd-sleep post hook to reload
  DSP1 and re-apply volatile calibration after resume.
- Ship PipeWire 2.0->4.0 PSD upmix drop-in configs (no-op on 2-ch sinks,
  ready for 4-channel TDM).

* Wed Nov 25 2026 Lymeeee <mr_xunyu@163.com> - 0.17.86-1
- Streamline gts9wifi-settings from 8 tabs to 6: merge charging controls into
  the Power tab, move the logging switch into Advanced, remove COPR, redundant
  check-all/reinstall-userspace actions and manual keyboard firmware picker,
  and show qcom-va-driver instead of legacy ffmpeg in Status.
- Fix broken RPM Fusion installed check ('未安装' vs 'not installed'), move
  blocking pkexec calls off the GTK main thread, and clean up the battery
  polling timer on window destroy.
- Lower gts9wifi-update kernel flash battery threshold from 60% to 25% and drop
  legacy ffmpeg from `gts9wifi-update all`.
- Relax gts9wifi-charge-guard.timer polling from 20s to 60s and require
  irqbalance so SoC SPI IRQs are not pinned exclusively to CPU0.

* Wed Nov 25 2026 Lymeeee <mr_xunyu@163.com> - 0.17.85-1
- Force fresh release metadata in gts9wifi-update kernel before selecting
  assets so a stale cached release JSON never causes an older kernel to be
  re-flashed; fail cleanly when explicit refresh fails and use mv -f to avoid
  interactive overwrite prompts on root-owned cache files.

* Tue Nov 24 2026 Lymeeee <mr_xunyu@163.com> - 0.17.84-1
- Keep PPS direct charging alive across power key, lid close, and power menu
  suspend by arming charge_hold proactively below 90% and blanking via Mutter
  DisplayConfig PowerSaveMode instead of read-only DRM dpms sysfs.
- Fix gts9wifi-cover-boot-guard panel blanking on charger boot (lpcharge=1)
  by using backlight bl_power (FB_BLANK_POWERDOWN) instead of read-only dpms.

* Tue Nov 24 2026 Lymeeee <mr_xunyu@163.com> - 0.17.83-1
- Enable runtime PM on 88e8000.phy (USB3 QMP combo PHY) in
  90-gts9wifi-usb-pm.rules and trigger GCC/GPUCC sync_state() in
  gts9wifi-mem-sleep once the GPU driver is bound, allowing usb3_phy_gdsc
  and usb30_prim_gdsc to collapse to off-0 when idle.

* Mon Nov 23 2026 Lymeeee <mr_xunyu@163.com> - 0.17.82-1
- Blacklist qcrypto (1dfa000.crypto holds a permanent sleep-set DDR
  bandwidth vote) and enable runtime PM on a600000.usb (drops its 1 GB/s
  sleep-set DDR vote when idle) to unblock deep suspend CXSD/AOSD.

* Mon Nov 23 2026 Lymeeee <mr_xunyu@163.com> - 0.17.81-1
- gts9wifi-speaker-protection: cache per-unit CS35L45 factory calibration
  (rdc/vsc/isc/temp) from sec_efs/cirrus into /var/lib/gts9wifi/speaker-cal,
  align DSP_RX1..8 sensor routing with Samsung mixer_paths.xml, and apply
  per-amp CAL_R/CAL_AMBIENT/CAL_STATUS/CAL_CHECKSUM/VSC/ISC controls (keeping
  DACPCM Source on ASP_RX1/2 until live DSP validation).

* Mon Nov 23 2026 Lymeeee <mr_xunyu@163.com> - 0.17.80-1
- Tune 99-gts9wifi-zram.conf for zstd zram: vm.swappiness=180,
  vm.page-cluster=0, vm.watermark_boost_factor=0, and
  vm.watermark_scale_factor=125.

* Mon Nov 23 2026 Lymeeee <mr_xunyu@163.com> - 0.17.79-1
- gts9wifi-update: fix Flatpak VA-API override to use --filesystem=host-os:ro
  and LIBVA_DRIVERS_PATH=/run/host/usr/lib64/qcom-va-driver-flatpak (Flatpak
  reserves /usr), drop the unnecessary Firefox policy from vaapi (and clean
  up the legacy entry), fix install_firefox_policy 0644 permissions, and
  match the actual display_delay V4L2 control name.

* Mon Nov 23 2026 Lymeeee <mr_xunyu@163.com> - 0.17.78-1
- gts9wifi-protect: drop the patched ffmpeg-free packages from EXCLUDES
  and protect qcom-va-driver instead; gts9wifi-update vaapi removes the
  legacy 50-ffmpeg.list versionlock.

* Mon Nov 23 2026 Lymeeee <mr_xunyu@163.com> - 0.17.77-1
- gts9wifi-update: add the vaapi component (qcom-va-driver RPM from
  latest, Firefox hardware-decoding policy, and system Flatpak VA-API
  override) and track it in check/check-all/all.

* Sat Nov 21 2026 Lymeeee <mr_xunyu@163.com> - 0.17.76-1
- Camera calibration: stop rewriting hi1337-gts9u-front-uw.yaml.  The
  front-uw sensor only exists on the Tab S9 Ultra; gts9wifi has a single
  front HI1337 and the YAML was never used.

* Sat Nov 21 2026 Lymeeee <mr_xunyu@163.com> - 0.17.75-1
- SELinux: restorecon runs as setfiles_t, which also needs stat and relabel
  access to the fingerprint runtime directories and device nodes, so the
  %post relabel completes with the policy enforced.

* Sat Nov 21 2026 Lymeeee <mr_xunyu@163.com> - 0.17.74-1
- SELinux: let rpm_script_t stat and relabel the fingerprint runtime
  directories and device nodes, so the %post restorecon works with the
  policy enforced instead of logging getattr denials.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.73-1
- SELinux: after the first-boot relabel has completed and the policy module
  is loaded, switch a permissive config to enforcing one time.  Fresh images
  still boot permissive for the relabel, and the stamp file keeps a later
  manual switch back to permissive.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.72-1
- SELinux policy: close the remaining permissive-only holes found by an
  enforcing soak: udev labeling of /dev/esfp0 and /dev/tee0, tmpfs
  association for /run, fprintd RuntimeDirectory removal, TEE access for
  the secure-start owner, the vndbinder context manager, and stat access
  for user tools.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.71-1
- SELinux policy follow-up: let the GNOME session, the UI broker and
  systemd manage the fingerprint runtime directory, so the lease handshake
  keeps working with the policy enforced.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.70-1
- Ship a small SELinux policy that labels the fingerprint lease
  directories and the EL721/qcomtee devices, allows fprintd the sysfs and
  device access it needs, and lets the camera sleep hook run systemctl.
  Rootfs installs relabel themselves on first boot, and pd-mapper plus
  hexagonrpcd run in unconfined_service_t instead of init_t.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.69-1
- Fingerprint target: show just the 3px white ring, fill it while the finger
  is down, and drop the black card backing.  A near-miss inside the padded
  ring no longer cancels; a press outside it still does.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.68-1
- Fingerprint target: drop the prompt text and let the card wrap the ring
  only, with a white outline so it stays visible on dark lock-screen
  wallpapers.  Raise the target above the screen-shield lightbox and the GDM
  dialog, which otherwise dim it into the shade, and observe presses with a
  stage capture handler so a tap outside the card cancels verification even
  while the lock screen holds its modal grab.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.67-1
- Draw the fingerprint target as a local black rounded card holding the ring
  and prompt instead of a full-screen shade, remove the close button, thicken
  the ring, and cancel on a press outside the card.  Global panel HBM stays.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.66-1
- Stop passing the removed affectsInputRegion chrome option to
  addTopChrome() on GNOME 50, which rejected it and aborted the whole
  Galaxy Tab Extension enable() (corner mask, keyboard helpers and OSDs
  included).  Non-reactive actors stay input-transparent there.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.65-1
- Enable authselect's with-fingerprint feature when installing the
  fingerprint stack.  GNOME 50 hides the Settings fingerprint row and never
  probes the lock-screen reader while authselect pins
  org.gnome.login-screen enable-fingerprint-authentication to false, and
  gdm-fingerprint needs pam_fprintd in fingerprint-auth.
- Correct the previous guidance: Fedora touches fingerprint-auth and
  system-auth only, so GDM's password prompt (password-auth) is not
  duplicated.  Sudo and console logins now try the fingerprint first.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.64-1
- Rename the shell extension to Galaxy Tab Extension (uuid
  galaxy-tab-extension@tabs9linux).  Device controls and the performance
  profile are removed from its settings page; Tab9 Settings is now the only
  place for them.  All other settings and runtime helpers are unchanged.
- Move the EL721 fingerprint target into the extension and run it in the
  user session, on the lock screen and in the GDM greeter, with the rounded
  corner mask following the same session modes.  Add a GDM dconf drop-in so
  GDM loads the system extension.  The standalone GTK4 overlay and its xdg
  autostart entry are removed.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.63-1
- fingerprint-overlay: parse logind's ActiveSession (session-id,
  object-path) instead of treating the struct as a path.  Without
  XDG_SESSION_ID in the GNOME autostart environment the fallback raised
  TypeError, so the overlay never sent Pulse, the driver kept touch
  suppression enabled, and presses never lit the target.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.62-1
- Add the EL721 full-screen fingerprint target overlay: a black
  compensation frame with a thin sensor ring, solid white feedback while
  the driver waits for a presented frame, the enrollment/verification
  prompt, and a GTK4 close button.  The close button asks the root broker
  to cancel the current fprintd operation.  Autostart in the GNOME user
  session; the GDM greeter is explicitly excluded.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.61-1
- Provision the native Bluetooth address into freshly flashed boot images:
  gts9wifi-update kernel --flash now patches the new boot/vendor_boot DTBs
  after writing and verifying them, before the reboot, so the first boot
  after a kernel update has a usable controller.
- bt-provision: write partitions through unbuffered pread/pwrite and verify
  the readback.  Buffered writes mixed with a raw SEEK_END lseek reported
  success but never reached the boot partition, so every boot rewrote it.
- Cache the Samsung EFS address in /var/lib/gts9wifi/bt-address and fall
  back to it when the EFS mount fails.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.60-1
- Remove the USB ECM/RNDIS debug network: the initramfs RNDIS hook, the
  ECM gadget service, the usb0 NetworkManager profile, the enable/disable
  switches in the settings app and the GNOME extension, and the gadget
  function/configfs options in the kernel config.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.59-1
- Keep the panel dark when a charger-triggered cold boot (lpcharge=1)
  starts with the folio cover already shut.  The firmware does not report
  SW_LID at boot, but the pogo controller's connected GPIO is 0 while the
  cover is closed; hold DPMS off until the cover connects or the user
  touches the tablet.

* Fri Nov 20 2026 Lymeeee <mr_xunyu@163.com> - 0.17.58-1
- Apply the charger sysfs permissions on driver bind as well: the i2c
  device exists before the driver probes, so the add event ran before
  charge_hold/fast_charge existed and the session could not engage the
  off-screen charge hold.

* Tue Nov 17 2026 Lymeeee <mr_xunyu@163.com> - 0.17.57-1
- Add the 息屏直充 charge mode: keep PPS direct charging alive with the
  panel off and enter deep sleep at 90%, backed by the new SM5440
  charge_hold sysfs attribute.

* Mon Nov 16 2026 Lymeeee <mr_xunyu@163.com> - 0.17.56-1
- Drop the SM5714 USB-PD unbind sleep hook.  The kernel keeps the PD
  stack alive across deep suspend and defers the charger-detach
  interrupt after resume; the userspace workaround is no longer wanted.

* Mon Nov 16 2026 Lymeeee <mr_xunyu@163.com> - 0.17.55-1
- Unbind the SM5714 USB-PD controller for the deep-suspend window when a
  charger is attached, and bind it again after resume.  The TCPM stack
  cannot handle a charger detach while suspended: the next resume (RTC or
  power key) stalls in the detach path and the PMIC hard-resets the SoC.
  The PD contract is renegotiated after resume; during sleep the source
  falls back to its default contract and charging continues.

* Mon Nov 16 2026 Lymeeee <mr_xunyu@163.com> - 0.17.54-1
- Require dtc at runtime: gts9wifi-bt-provision needs fdtget/fdtput to
  write local-bd-address into the boot DTBs.  Removing dtc during a
  build-tool cleanup left hci0 unconfigured on every boot and made
  Bluetooth unusable.

* Mon Nov 16 2026 Lymeeee <mr_xunyu@163.com> - 0.17.53-1
- Hide the internal CAMSS VFE video nodes from GStreamer's v4l2 device
  provider.  The camera app listed them as extra "rear" cameras next to
  the two libcamera cameras.  libcamera opens the media graph directly
  and is unaffected.

* Mon Nov 16 2026 Lymeeee <mr_xunyu@163.com> - 0.17.52-1
- Camera calibration: target the kernel's per-variant sensor model names
  (hi1337-gts9u-rear/front/front-uw) instead of the CCI instance names.
  The kernel now reports a distinct model per module.

* Sun Nov 15 2026 Lymeeee <mr_xunyu@163.com> - 0.17.51-1
- Settings: add "导入相机校准" under 高级 -> 相机.  It decodes the OEM
  Samsung Chromatix colour matrices from this unit's vendor partition and
  rewrites the libcamera HI1337 tuning file.  No kernel or libcamera
  rebuild is needed on the device.

* Sun Nov 15 2026 Lymeeee <mr_xunyu@163.com> - 0.17.50-1
- Fix the executable bit on gts9wifi-camera-suspend-pre.  It was installed
  0644, so systemd-suspend.service failed at ExecStartPre with 203/EXEC
  and every suspend attempt aborted before reaching sleep.
- CI now rejects non-executable helpers under /usr/bin, /usr/libexec and
  /usr/lib/systemd/system-sleep.

* Sun Nov 15 2026 Lymeeee <mr_xunyu@163.com> - 0.17.49-1
- Settings: add a Display page with switches for the automatic-brightness
  floor and the low-brightness warning.  The floor raises gsd-power's
  ambient target by the current manual offset, so the 36% floor holds at
  any slider position; manual brightness changes can still go below it.
  The warning's "set to 36%" action now also accounts for the auto target.
- libwacom: name the tablet "Samsung Galaxy Tab S9" and ship a Samsung S Pen
  stylus description with its single side button, replacing the generic
  two-button entry shown by the Wacom settings page.

* Sun Nov 15 2026 Lymeeee <mr_xunyu@163.com> - 0.17.48-1
- Run the camera-stop half of the suspend safety net from a
  systemd-suspend.service ExecStartPre drop-in.  systemd-sleep freezes
  user.slice before the system-sleep pre hooks, so the old pre hook blocked
  in `systemctl --user stop` for ~45 s and delayed every suspend.

* Fri Nov 13 2026 Lymeeee <mr_xunyu@163.com> - 0.17.47-1
- Raise the zram cap to 6 GiB and set vm.swappiness=100.  With the browser,
  WeChat, QQ and OnlyOFFICE open, the 4 GiB device already used 2.3 GiB of
  swap with only 1.5 GiB available, and the default 60 frees anonymous pages
  reluctantly.

* Fri Nov 13 2026 Lymeeee <mr_xunyu@163.com> - 0.17.46-1
- Verify downloaded release assets against the asset size/digest and resume
  interrupted transfers.  A truncated kernel RPM used to be accepted by
  curl and only failed at rpm install time, after the boot partitions had
  already been written.
- Unify the S Pen dock OSD wording as "S Pen 已离开/已吸附/充电中/已充满
  <battery>%".

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.45-1
- Fix the keyboard firmware helper's executable mode and stop ordering it
  before the display manager.
- Override the rootfs sensor-proxy unit so GDM does not wait for ADSP
  bring-up; the sensor proxy still runs after login.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.44-1
- Drop the ath11k deep-suspend unbind hook.  The kernel now keeps WoW for
  s2idle and uses the normal power-down path for deep suspend, which lets
  the PCIe/pwrseq stack cut the WCN6855 rails.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.43-1
- gts9wifi-settings: rename the desktop entry to 平板杂项设置.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.42-1
- gts9wifi-settings: the Simplified Chinese action now reinstalls packages
  whose zh_CN .mo files were never written by the rootfs build.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.41-1
- gts9wifi-update: add "calib" to import the fingerprint calibration on
  its own, without touching the installed packages.
- Settings: add the separate fingerprint-calibration button; "update all"
  still carries the installed fingerprint and ffmpeg packages.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.40-1
- gts9wifi-update: add check-all and all.  The update now covers
  userspace, dynpart, the patched libcamera (with LIBCAMERA-SHA256SUMS
  verification and a versionlock), fingerprint and ffmpeg; the kernel
  still requires an explicit --flash.  check-all can run unprivileged.
- Settings: replace the separate ffmpeg/fingerprint update rows with one
  "check all" dialog and one "update all" action.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.39-1
- Stop the user's PipeWire stack for the sleep window if a camera stream
  is still holding a video node, and restart it through a transient system
  unit after resume.  The VCM driver already has the runtime-only PM ops;
  this only releases the userspace owner so CAMSS and the lens cannot
  block deep suspend.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.38-1
- Remove the S Pen air-mouse pointer and gyro subscription.  The pen's
  BLE button now taps a configurable KEY_* shortcut (Settings > S Pen)
  and is ignored while the tip is in digitizer range, so the native
  stylus button keeps working without a double trigger.
- Add a "disable all logging" switch: stops journald storage,
  rsyslog/auditd/ABRT, clears /var/log, the journal, crash dumps and the
  kernel ring buffer, and a boot unit keeps it in effect.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.37-1
- Unbind ath11k_pci around deep suspend and probe it again on resume.
  The WoW policy keeps the WCN6855 powered, which drained roughly a
  quarter of the battery over one night and left the morning resume
  without Wi-Fi; the following suspend panicked.

* Thu Nov 12 2026 Lymeeee <mr_xunyu@163.com> - 0.17.36-1
- Switch /sys/power/mem_sleep to deep at boot now that RTC alarm wake
  from deep has been verified on the tablet.

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.17.35-1
- Add the S Pen air-mouse pointer: when the pen leaves the dock the
  spen-remote daemon switches the BLE sensor to pointer mode and feeds a
  uinput relative pointer; the Settings app gains an S Pen page with a
  toggle, plus revised Simplified Chinese strings.

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.17.34-1
- Install the fingerprint runtime 0.1.2 from the Settings button and pass
  --calib-from-device so this unit's sec_efs calibration is imported
  automatically

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.17.33-1
- Suppress the Shell brightness OSD only while the Quick Settings
  brightness slider is being dragged; the brightness keys, auto-brightness
  and other sources keep the normal OSD

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.17.32-1
- Require libcap explicitly so the file-capability repair has setcap
- Syntax-check gts9wifi-update in CI

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.17.31-1
- Import the fingerprint calibration from this unit's sec_efs with
  `--calib-from-device`; keep the supplied-directory path as `--calib`
- Stop recommending authselect's with-fingerprint feature: Fedora's GDM
  already uses the dedicated gdm-fingerprint PAM service, and the feature
  adds a second fingerprint prompt to the password stack

* Wed Nov 11 2026 Lymeeee <mr_xunyu@163.com> - 0.17.30-1
- Re-apply file capabilities from RPM's own metadata after install, repairing
  newuidmap/newgidmap, arping and the sssd helpers that older xattr-less
  rootfs tarballs stripped

* Tue Nov 10 2026 Lymeeee <mr_xunyu@163.com> - 0.17.29-1
- Shorten logind's post-resume lid holdoff to 5 s so closing the cover right
  after waking suspends the tablet instead of being ignored
- Enable the firmware CPU boost OPPs (CPU7 3.36 GHz) in balanced, sticky and
  performance, and keep them off in powersave

* Tue Nov 10 2026 Lymeeee <mr_xunyu@163.com> - 0.17.28-1
- Skip the low-brightness warning while gsd-power's idle dimming is active
  (Main.brightnessManager.dimming), so the automatic dim no longer pops it

* Tue Nov 10 2026 Lymeeee <mr_xunyu@163.com> - 0.17.27-1
- Add an ONLYOFFICE action that removes LibreOffice (RPM or Flatpak) when
  present and installs the official aarch64 RPM
- Rework the Rime action into the Wanxiang setup: remove ibus-libpinyin and
  libpinyin-data, install ibus-rime with the Wanxiang base dictionary, drop
  the grammar model, turn off inline preedit and make Rime the default source
- Send the low-brightness warning as a normal transient notification so it
  expires instead of staying until dismissed, and make clicking it set the
  brightness to 36%

* Tue Nov 10 2026 Lymeeee <mr_xunyu@163.com> - 0.17.26-1
- Show all Shell OSDs at the top edge by mirroring the theme's bottom margin
  instead of anchoring them at the bottom
- Feed the OSD level bar a 0-1 fraction so a full S Pen battery is white, not
  the red overdrive colour Shell 50 uses past its 1.0 threshold
- Never report a missing /run/gts9wifi/spen-battery file as 0% battery
- Fill the missing Settings > System > About processor row on arm64 with a
  libgtop shim that reports the device CPU model

* Mon Nov 09 2026 Lymeeee <mr_xunyu@163.com> - 0.17.25-1
- Translate the Tab9 Settings UI, device control labels, desktop entry and
  the GNOME extension preferences to Simplified Chinese

* Mon Nov 09 2026 Lymeeee <mr_xunyu@163.com> - 0.17.24-1
- Fix the Shell 50 OSD level bar: pass null instead of -1 so only the
  S Pen battery popup shows a bar, and clamp it to 0-100
- Drop the meaningless Caps Lock level bar

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.17.1-1
- Temporarily lift gts9wifi-protect excludes and versionlocks while the
  updater installs userspace, FFmpeg, fingerprint or kernel packages, and
  restore both afterwards (including on failure or interrupt)

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.17.0-1
- Install the gts9wifi-dynpart aarch64 RPM alongside userspace updates,
  providing the Android super dynamic-partition mappings and vendor mounts

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.16.2-1
- Pre-render the Plymouth theme images at panel size so the boot splash
  is no longer aliased by Plymouth's fixed 2x2 Image.Scale

* Sat Nov 07 2026 Lymeeee <mr_xunyu@163.com> - 0.16.1-1
- Fix the kernel update's EXIT trap so a successful flash no longer ends
  with an unbound-variable error and a non-zero status

* Fri Nov 06 2026 Lymeeee <mr_xunyu@163.com> - 0.16.0-1
- Restore the system clock from the continuing PMIC RTC counter before
  the network is up, without writing Android's RTC

* Fri Nov 06 2026 Lymeeee <mr_xunyu@163.com> - 0.15.0-1
- Skip the panel recovery platform-suspend cycle when the driver already
  reported a valid ANA38407 panel ID, and retry the cycle if a wake event
  aborts it
- Remove the fixed two-second delay before the panel check
- Accept NUL padding after the appended DTB and provision vendor_boot before
  boot, so one copy cannot hide the other
- Shrink the Samsung wordmark on the boot splash
- Pair the docked S Pen over BLE and publish its battery through BlueZ

* Fri Nov 06 2026 Lymeeee <mr_xunyu@163.com> - 0.14.0-1
- Add a libwacom definition so GNOME treats the S Pen as a
  display-integrated digitizer and maps it to the panel in every rotation
- Pick the newest release asset by version instead of filename order and
  refresh release metadata older than five minutes

* Thu Nov 05 2026 Lymeeee <mr_xunyu@163.com> - 0.13.0-1
- Anti-alias the Plymouth spinner and add live battery telemetry
- Add automatic charging bypass at 100 % with a 95 % release
- Grant the desktop user video-group access for the device controls
- Retry the keyboard V37 update after the root filesystem is mounted
- Set the GNOME per-user language when switching to Chinese

* Thu Nov 05 2026 Lymeeee <mr_xunyu@163.com> - 0.12.0-1
- Fix the CS35L45 right-channel routing (Front/Rear Right to ASP_RX2)
- Reapply speaker gains and routing after alsa-restore

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.11.0-1
- Port the convertible power-key user service with a settings toggle

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.10.0-1
- Add the IBus Rime / 雾凇拼音 one-click installer

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.9.0-1
- Add setup helpers: mirrors, RPM Fusion/Copr, Chinese locale, protection

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.8.0-1
- Add the Tab9 Settings GTK4/libadwaita application

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.7.0-1
- Ship the GTS9 Plymouth theme in the rootfs and select it on install

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.6.0-1
- Add gts9wifi-update fingerprint: libfprint EL721 + runtime, mounts,
  services, versionlock and optional calibration import

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.5.0-1
- Add power profile and USB debug network controls to the settings page
- Add the pkexec helper for privileged settings actions

* Wed Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.4.0-1
- Default fast charging on and add the one-time default service
- Disable the USB debug net by default, with a rescue flag file
- Add gts9wifi-power profiles and Wi-Fi powersave default

* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.3.0-1
- Add gts9wifi-update ffmpeg to install and lock the rebuilt ffmpeg-free RPMs
- Set Firefox media.hardware-video-decoding.force-enabled policy

* Tue Nov 04 2026 Lymeeee <mr_xunyu@163.com> - 0.2.0-1
- Add gts9wifi-update with kernel self-flash, rollback and versionlock
- Initial port of the Tab9 Extras v6 extension and device helpers
