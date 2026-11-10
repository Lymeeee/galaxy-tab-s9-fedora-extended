// SPDX-License-Identifier: MIT
//
// Show the Shell-style OSD when the S Pen is inserted into or removed from
// its garage.  The kernel power supply carries the dock state and charging
// state; the userspace daemon drops the last GATT battery reading into
// /run/gts9wifi/spen-battery so the notice can show a percentage too.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const SUPPLY = '/sys/class/power_supply/gts9wifi-spen';
const BATTERY_STATE = '/run/gts9wifi/spen-battery';
const POLL_SECONDS = 1;

function readFile(path) {
    try {
        const [ok, data] = Gio.File.new_for_path(path).load_contents(null);
        return ok ? new TextDecoder('utf-8').decode(data).trim() : null;
    } catch {
        return null;
    }
}

export class SpenOsd {
    constructor(osd) {
        this._osd = osd;
        this._pollId = 0;
        this._docked = null;
    }

    enable() {
        this._docked = readFile(`${SUPPLY}/present`) === '1';
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,
            POLL_SECONDS, () => {
                this._poll();
                return GLib.SOURCE_CONTINUE;
            });
    }

    disable() {
        if (this._pollId) {
            GLib.source_remove(this._pollId);
            this._pollId = 0;
        }
    }

    _poll() {
        const docked = readFile(`${SUPPLY}/present`) === '1';
        if (docked === this._docked)
            return;
        this._docked = docked;
        this._notify(docked);
    }

    _notify(docked) {
        const battery = this._battery();

        if (!docked) {
            const text = battery === null
                ? 'S Pen 已拔出' : `S Pen 已拔出 · 上次 ${battery}%`;
            this._osd.show('document-edit-symbolic', text, battery);
            return;
        }

        const suffix = battery === null ? '' : ` · ${battery}%`;
        const status = readFile(`${SUPPLY}/status`);
        if (status === 'full') {
            this._osd.show('battery-level-100-symbolic',
                `S Pen 已入坞 · 已充满${suffix}`, battery ?? 100);
        } else if (status === 'charging') {
            this._osd.show('battery-level-100-charging-symbolic',
                `S Pen 已入坞 · 充电中${suffix}`, battery);
        } else {
            this._osd.show('document-edit-symbolic',
                `S Pen 已入坞${suffix}`, battery);
        }
    }

    _battery() {
        const text = readFile(BATTERY_STATE);
        if (text === null || text === '')
            return null;
        const value = Number(text);
        return Number.isInteger(value) && value >= 0 && value <= 100
            ? value : null;
    }
}
