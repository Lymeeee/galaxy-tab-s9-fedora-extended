// SPDX-License-Identifier: MIT
//
// Warn when the panel is dimmed below the point where the backlight leaves
// DC dimming.  The kernel backlight percentage is what the user sees on the
// brightness slider, so watch the sysfs value directly; notify once per low
// excursion, re-arming after the level returns above 36%.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BACKLIGHT_ROOT = '/sys/class/backlight';
const THRESHOLD = 36;
const POLL_MS = 1000;
const COOLDOWN_US = 60 * 1000 * 1000;
const TEXT = '警告：亮度低于36%时屏幕将由DC调光进入低频PWM调光，为了保护您的视力健康，请谨慎操作。';

function readFile(path) {
    try {
        const [ok, data] = Gio.File.new_for_path(path).load_contents(null);
        return ok ? new TextDecoder('utf-8').decode(data).trim() : null;
    } catch {
        return null;
    }
}

export class BrightnessWarning {
    constructor() {
        this._dir = null;
        this._armed = true;
        this._lastNotify = -Infinity;
        this._pollId = 0;
    }

    enable() {
        this._dir = this._findBacklight();
        this._pollId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, POLL_MS, () => {
            this._poll();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._pollId) {
            GLib.source_remove(this._pollId);
            this._pollId = 0;
        }
        this._dir = null;
    }

    _poll() {
        const percent = this._readPercent();
        if (percent === null)
            return;
        if (percent >= THRESHOLD) {
            this._armed = true;
            return;
        }
        if (!this._armed)
            return;
        this._armed = false;
        this._notify();
    }

    _notify() {
        const now = GLib.get_monotonic_time();
        if (now - this._lastNotify < COOLDOWN_US)
            return;
        this._lastNotify = now;

        Gio.DBus.session.call(
            'org.freedesktop.Notifications',
            '/org/freedesktop/Notifications',
            'org.freedesktop.Notifications', 'Notify',
            new GLib.Variant('(susssasa{sv}i)', [
                'gts9wifi', 0, 'dialog-warning-symbolic',
                '亮度警告', TEXT, [],
                {urgency: new GLib.Variant('y', 2)},
                10000,
            ]),
            null, Gio.DBusCallFlags.NONE, -1, null, null);
    }

    _findBacklight() {
        let enumerator;
        try {
            enumerator = Gio.File.new_for_path(BACKLIGHT_ROOT)
                .enumerate_children('standard::name',
                    Gio.FileQueryInfoFlags.NONE, null);
        } catch {
            return null;
        }

        try {
            let info;
            while ((info = enumerator.next_file(null)) !== null) {
                const dir = `${BACKLIGHT_ROOT}/${info.get_name()}`;
                if (readFile(`${dir}/brightness`) !== null &&
                    readFile(`${dir}/max_brightness`) !== null)
                    return dir;
            }
        } finally {
            enumerator.close(null);
        }
        return null;
    }

    _readPercent() {
        if (!this._dir)
            this._dir = this._findBacklight();
        if (!this._dir)
            return null;

        const brightness = Number(readFile(`${this._dir}/brightness`));
        const max = Number(readFile(`${this._dir}/max_brightness`));
        if (!Number.isFinite(brightness) || !Number.isFinite(max) || max <= 0) {
            this._dir = null;
            return null;
        }
        return brightness * 100 / max;
    }
}
