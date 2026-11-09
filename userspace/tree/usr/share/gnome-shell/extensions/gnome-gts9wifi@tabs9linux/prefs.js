// SPDX-License-Identifier: MIT
//
// The extension's own settings page, reachable from the Extensions app or with
//   gnome-extensions prefs gnome-gts9wifi@tabs9linux
//
// The page is built from whatever the helper reports, grouped by the group
// field it carries, so a new control shows up here without touching this file.

import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

import {helperAvailable, listControls, setControl} from './deviceControls.js';

const PRIVILEGED_HELPER = '/usr/libexec/gts9wifi-privileged';

function privilegedAvailable() {
    return GLib.file_test(PRIVILEGED_HELPER, GLib.FileTest.IS_EXECUTABLE);
}

function runPrivileged(args) {
    try {
        const proc = Gio.Subprocess.new(
            ['pkexec', PRIVILEGED_HELPER, ...args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
        proc.communicate_utf8(null, null);
        return proc.get_successful();
    } catch (error) {
        console.error(`gnome-gts9wifi: ${error.message}`);
        return false;
    }
}

export default class Gts9wifiPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const page = new Adw.PreferencesPage({
            title: _('设备控制'),
            icon_name: 'preferences-system-symbolic',
        });

        const controls = helperAvailable() ? listControls() : [];
        if (controls.length === 0) {
            const group = new Adw.PreferencesGroup();
            group.add(new Adw.ActionRow({
                title: _('未找到设备控制项'),
                subtitle: _('此扩展仅在 Galaxy Tab S9 Wi-Fi（SM-X710）的 Linux 移植上生效。'),
            }));
            page.add(group);
            window.add(page);
            return;
        }

        const groups = new Map();
        for (const control of controls) {
            if (!groups.has(control.group)) {
                const group = new Adw.PreferencesGroup({title: control.group});
                groups.set(control.group, group);
                page.add(group);
            }

            const row = new Adw.SwitchRow({
                title: control.label,
                subtitle: control.description,
                active: control.enabled,
            });

            // Reverting `active` after a refusal re-emits this signal, so guard
            // against recursing into it.
            let reverting = false;
            row.connect('notify::active', () => {
                if (reverting)
                    return;
                if (setControl(control.name, row.active))
                    return;

                reverting = true;
                row.active = !row.active;
                reverting = false;
            });

            groups.get(control.group).add(row);
        }

        const power = this._powerGroup();
        if (power)
            page.add(power);
        const usbNet = this._usbNetGroup();
        if (usbNet)
            page.add(usbNet);

        const boot = this._bootGroup();
        if (boot)
            page.add(boot);
        page.add(this._lockGroup());
        page.add(this._displayGroup());
        page.add(this._keyboardGroup());
        window.add(page);
    }

    _powerGroup() {
        if (!privilegedAvailable())
            return null;

        const ids = ['powersave', 'sticky', 'balanced', 'performance'];
        const names = [_('省电'), _('粘性'), _('均衡'),
            _('性能')];
        const model = new Gtk.StringList();
        names.forEach(name => model.append(name));

        let current = 'balanced';
        try {
            current = new TextDecoder().decode(
                GLib.file_get_contents('/var/lib/gts9wifi/power-profile')[1]).trim();
        } catch {}

        const group = new Adw.PreferencesGroup({title: _('电源')});
        const row = new Adw.ComboRow({
            title: _('性能模式'),
            subtitle: _('CPU 调频/EPP、GPU 调频和 Wi-Fi 省电策略。每次修改都会请求认证。'),
            model,
            selected: Math.max(0, ids.indexOf(current)),
        });
        row.connect('notify::selected', () => {
            if (!runPrivileged(['power', ids[row.selected]]))
                logError(new Error('cannot apply the power profile'),
                    'gnome-gts9wifi');
        });
        group.add(row);
        return group;
    }

    _usbNetGroup() {
        if (!privilegedAvailable())
            return null;

        const enabled = GLib.file_test('/etc/gts9wifi/usb-net-enabled',
            GLib.FileTest.EXISTS);
        const group = new Adw.PreferencesGroup({title: _('调试')});
        const row = new Adw.SwitchRow({
            title: _('USB 调试网络'),
            subtitle: _('系统无法启动时，通过 172.16.42.1 的 USB 网卡提供 SSH。它会持续给 USB 设备控制器供电，日常使用建议关闭。'),
            active: enabled,
        });

        let reverting = false;
        row.connect('notify::active', () => {
            if (reverting)
                return;
            if (runPrivileged(['usbnet', row.active ? 'on' : 'off']))
                return;

            reverting = true;
            row.active = !row.active;
            reverting = false;
        });
        group.add(row);
        return group;
    }

    // The boot animation gts9wifi-boot-animation plays: one of the videos in
    // animations.list (id|label per line, written by the image build), saved
    // as its id in /var/lib/gts9wifi/boot-animation, which the boot service
    // reads.  The directory belongs to group video, as for the controls above.
    _bootGroup() {
        let lines;
        try {
            const [, bytes] = GLib.file_get_contents('/usr/share/gts9wifi/boot-animation/animations.list');
            lines = new TextDecoder().decode(bytes).split('\n');
        } catch {
            return null;
        }
        const ids = [];
        const labels = new Gtk.StringList();
        for (const line of lines) {
            const [id, label] = line.split('|');
            if (!id)
                continue;
            ids.push(id);
            labels.append(label || id);
        }
        if (ids.length === 0)
            return null;

        const choice = '/var/lib/gts9wifi/boot-animation';
        let current = 'blackhole';
        try {
            current = new TextDecoder().decode(GLib.file_get_contents(choice)[1]).trim();
        } catch {}

        const group = new Adw.PreferencesGroup({title: _('启动')});
        const row = new Adw.ComboRow({
            title: _('开机动画'),
            subtitle: _('从亮屏开始显示，直到登录界面。'),
            model: labels,
            selected: Math.max(0, ids.indexOf(current)),
        });
        row.connect('notify::selected', () => {
            try {
                GLib.file_set_contents(choice, `${ids[row.selected]}\n`);
            } catch (e) {
                logError(e, 'gts9wifi: cannot save the boot animation');
            }
        });
        group.add(row);
        return group;
    }

    // GNOME's own lock settings: lock-enabled covers the screen blanking after
    // idle, Ubuntu's ubuntu-lock-on-suspend the suspend; gts9wifi-power-key
    // reads lock-enabled and does not lock before suspending when it is off.
    _lockGroup() {
        const group = new Adw.PreferencesGroup({title: _('屏幕锁定')});
        this._screensaver = new Gio.Settings({schema_id: 'org.gnome.desktop.screensaver'});
        // Off by default (GNOME's default: lock-enabled true).
        const row = new Adw.SwitchRow({
            title: _('唤醒无需密码'),
            subtitle: _('只在登录时询问一次密码：之后电源键和熄屏超时只会关闭屏幕，唤醒后直接回到桌面。'),
        });
        this._screensaver.bind('lock-enabled', row, 'active',
            Gio.SettingsBindFlags.DEFAULT | Gio.SettingsBindFlags.INVERT_BOOLEAN);
        row.connect('notify::active', () => {
            if (this._screensaver.settings_schema.has_key('ubuntu-lock-on-suspend'))
                this._screensaver.set_boolean('ubuntu-lock-on-suspend', !row.active);
        });
        group.add(row);
        return group;
    }

    _displayGroup() {
        const group = new Adw.PreferencesGroup({title: _('显示')});

        const corners = new Adw.SwitchRow({
            title: _('屏幕圆角遮罩'),
            subtitle: _('用黑色圆角楔形遮住面板四角，类似 One UI。'),
        });
        this.getSettings().bind('rounded-corners', corners, 'active',
            Gio.SettingsBindFlags.DEFAULT);
        group.add(corners);

        const radius = new Adw.SpinRow({
            title: _('圆角半径'),
            subtitle: _('以 2560 像素面板宽度为基准的物理像素。'),
            adjustment: new Gtk.Adjustment({
                lower: 8,
                upper: 64,
                step_increment: 2,
                page_increment: 8,
                value: this.getSettings().get_int('rounded-corner-radius'),
            }),
        });
        // GSettings int <-> SpinRow double needs an explicit conversion.
        radius.connect('notify::value', () => {
            const value = Math.round(radius.value);
            if (this.getSettings().get_int('rounded-corner-radius') !== value)
                this.getSettings().set_int('rounded-corner-radius', value);
        });
        group.add(radius);

        return group;
    }

    _keyboardGroup() {
        const group = new Adw.PreferencesGroup({title: _('键盘')});
        const row = new Adw.SwitchRow({
            title: _('浮动键盘按钮'),
            subtitle: _('可拖动的按钮，用于打开屏幕键盘，适合不会自行唤出键盘的应用（X11 应用、Wine）。'),
        });
        this.getSettings().bind('keyboard-button', row, 'active',
            Gio.SettingsBindFlags.DEFAULT);
        group.add(row);
        return group;
    }
}
