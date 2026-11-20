// SPDX-License-Identifier: MIT
//
// The extension's own settings page, reachable from the Extensions app or with
//   gnome-extensions prefs galaxy-tab-extension@tabs9linux
//
// Device controls and the power profile deliberately live in Tab9 Settings
// only; this page keeps the settings the extension itself implements.

import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class GalaxyTabPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const page = new Adw.PreferencesPage({
            title: _('常规'),
            icon_name: 'preferences-system-symbolic',
        });

        const boot = this._bootGroup();
        if (boot)
            page.add(boot);
        page.add(this._lockGroup());
        page.add(this._displayGroup());
        page.add(this._keyboardGroup());
        window.add(page);
    }

    // The boot animation gts9wifi-boot-animation plays: one of the videos in
    // animations.list (id|label per line, written by the image build), saved
    // as its id in /var/lib/gts9wifi/boot-animation, which the boot service
    // reads.  The directory belongs to group video.
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
