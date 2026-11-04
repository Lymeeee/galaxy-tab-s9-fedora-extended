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
            title: _('Device controls'),
            icon_name: 'preferences-system-symbolic',
        });

        const controls = helperAvailable() ? listControls() : [];
        if (controls.length === 0) {
            const group = new Adw.PreferencesGroup();
            group.add(new Adw.ActionRow({
                title: _('No device controls found'),
                subtitle: _('This extension only does anything on the Galaxy Tab S9 Wi-Fi (SM-X710) Linux ports.'),
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
        page.add(this._keyboardGroup());
        window.add(page);
    }

    _powerGroup() {
        if (!privilegedAvailable())
            return null;

        const ids = ['powersave', 'balanced', 'performance'];
        const names = [_('Power saver'), _('Balanced'), _('Performance')];
        const model = new Gtk.StringList();
        names.forEach(name => model.append(name));

        let current = 'balanced';
        try {
            current = new TextDecoder().decode(
                GLib.file_get_contents('/var/lib/gts9wifi/power-profile')[1]).trim();
        } catch {}

        const group = new Adw.PreferencesGroup({title: _('Power')});
        const row = new Adw.ComboRow({
            title: _('Power profile'),
            subtitle: _('CPU governor/EPP, GPU devfreq and Wi-Fi powersave. Each change asks for authentication.'),
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
        const group = new Adw.PreferencesGroup({title: _('Debug')});
        const row = new Adw.SwitchRow({
            title: _('USB debug network'),
            subtitle: _('The USB gadget at 172.16.42.1 for SSH when the system does not boot. It keeps the USB device controller powered, so leave it off for daily use.'),
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

        const group = new Adw.PreferencesGroup({title: _('Boot')});
        const row = new Adw.ComboRow({
            title: _('Boot animation'),
            subtitle: _('Shown from the moment the screen comes on until the login screen.'),
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
        const group = new Adw.PreferencesGroup({title: _('Screen lock')});
        this._screensaver = new Gio.Settings({schema_id: 'org.gnome.desktop.screensaver'});
        // Off by default (GNOME's default: lock-enabled true).
        const row = new Adw.SwitchRow({
            title: _('Wake without the password'),
            subtitle: _('The password is asked once, at login: after that the power key and the screen timeout only turn the screen off, and waking goes straight back to the desktop.'),
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

    _keyboardGroup() {
        const group = new Adw.PreferencesGroup({title: _('Keyboard')});
        const row = new Adw.SwitchRow({
            title: _('Floating keyboard button'),
            subtitle: _('A draggable button that opens the on-screen keyboard, for apps that do not open it on their own (X11 apps, Wine).'),
        });
        this.getSettings().bind('keyboard-button', row, 'active',
            Gio.SettingsBindFlags.DEFAULT);
        group.add(row);
        return group;
    }
}
