// SPDX-License-Identifier: MIT
//
// Add a "Turn Off Screen" ("关闭屏幕") item to the Quick Settings power menu.
//
// Locks the session via Main.screenShield and then blanks the OLED panel
// through Mutter's DisplayConfig PowerSaveMode without entering system
// suspend, so background tasks keep running and waking is instant while
// avoiding screen burn-in.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const LOCK_FALLBACK_MS = 1500;
const BLANK_AFTER_LOCK_MS = 250;
const BLANK_ALREADY_LOCKED_MS = 300;

export class ScreenOffMenu {
    constructor() {
        this._item = null;
        this._activateId = 0;
        this._sessionModeId = 0;
        this._shieldId = 0;
        this._fallbackTimerId = 0;
        this._blankTimerId = 0;
    }

    enable() {
        const menu = Main.panel.statusArea.quickSettings?._system?._systemItem?.menu;
        if (!menu)
            return;

        const isZh = GLib.get_language_names().some(l => l.startsWith('zh'));
        const label = isZh ? '关闭屏幕' : 'Turn Off Screen';

        this._item = new PopupMenu.PopupMenuItem(label);
        this._activateId = this._item.connect('activate', () => this._activate());
        menu.addMenuItem(this._item, 0);

        this._sessionModeId = Main.sessionMode.connect('updated',
            () => this._syncVisibility());
        this._syncVisibility();
    }

    _syncVisibility() {
        if (this._item)
            this._item.visible = !Main.sessionMode.isGreeter;
    }

    _activate() {
        this._cancelPending();
        Main.panel.closeQuickSettings();

        const shield = Main.screenShield;
        if (shield && !shield.active) {
            this._shieldId = shield.connect('active-changed', () => {
                if (!shield.active)
                    return;
                this._cancelPending();
                this._scheduleBlank(BLANK_AFTER_LOCK_MS);
            });
            this._fallbackTimerId = GLib.timeout_add(
                GLib.PRIORITY_DEFAULT, LOCK_FALLBACK_MS, () => {
                    this._fallbackTimerId = 0;
                    this._cancelPending();
                    this._blankDisplay();
                    return GLib.SOURCE_REMOVE;
                });
            shield.lock(true);
        } else {
            this._scheduleBlank(BLANK_ALREADY_LOCKED_MS);
        }
    }

    _scheduleBlank(delayMs) {
        this._blankTimerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delayMs, () => {
            this._blankTimerId = 0;
            this._blankDisplay();
            return GLib.SOURCE_REMOVE;
        });
    }

    _blankDisplay() {
        Gio.DBus.session.call(
            'org.gnome.Mutter.DisplayConfig',
            '/org/gnome/Mutter/DisplayConfig',
            'org.freedesktop.DBus.Properties',
            'Set',
            new GLib.Variant('(ssv)', [
                'org.gnome.Mutter.DisplayConfig',
                'PowerSaveMode',
                GLib.Variant.new_int32(1),
            ]),
            null,
            Gio.DBusCallFlags.NONE,
            1000,
            null,
            (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (e) {
                    console.error(`ScreenOffMenu: PowerSaveMode blank failed: ${e.message}`);
                }
            });
    }

    _cancelPending() {
        if (this._shieldId && Main.screenShield) {
            Main.screenShield.disconnect(this._shieldId);
            this._shieldId = 0;
        }
        if (this._fallbackTimerId) {
            GLib.source_remove(this._fallbackTimerId);
            this._fallbackTimerId = 0;
        }
        if (this._blankTimerId) {
            GLib.source_remove(this._blankTimerId);
            this._blankTimerId = 0;
        }
    }

    disable() {
        this._cancelPending();
        if (this._sessionModeId) {
            Main.sessionMode.disconnect(this._sessionModeId);
            this._sessionModeId = 0;
        }
        if (this._item) {
            if (this._activateId) {
                this._item.disconnect(this._activateId);
                this._activateId = 0;
            }
            this._item.destroy();
            this._item = null;
        }
    }
}
