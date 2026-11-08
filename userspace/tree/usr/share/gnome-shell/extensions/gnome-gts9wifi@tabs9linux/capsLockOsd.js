// SPDX-License-Identifier: MIT
//
// Caps Lock OSD for the pogo keyboard.  The Shell's stage does not see the
// keyboard events a Wayland client receives, so do not try to intercept the
// key: poll the LED the kernel toggles instead.  The LED device number can
// change between boots, so look it up by its "::capslock" suffix.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const LED_ROOT = '/sys/class/leds';
const POLL_MS = 250;

function readFile(path) {
    try {
        const [ok, data] = Gio.File.new_for_path(path).load_contents(null);
        return ok ? new TextDecoder('utf-8').decode(data).trim() : null;
    } catch {
        return null;
    }
}

export class CapsLockOsd {
    constructor(osd) {
        this._osd = osd;
        this._pollId = 0;
        this._ledPath = null;
        this._state = null;
    }

    enable() {
        this._ledPath = this._findLed();
        this._state = this._readLed();
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
        this._ledPath = null;
        this._state = null;
    }

    _poll() {
        const state = this._readLed();
        if (state === null)
            return;
        if (this._state === null) {
            this._state = state;
            return;
        }
        if (state === this._state)
            return;

        this._state = state;
        this._osd.show('input-keyboard-symbolic',
            state ? 'Caps Lock 开' : 'Caps Lock 关', null, 1400);
    }

    _readLed() {
        let state = this._ledPath ? this._readBrightness(this._ledPath) : null;
        if (state !== null)
            return state;

        this._ledPath = this._findLed();
        return this._ledPath ? this._readBrightness(this._ledPath) : null;
    }

    _readBrightness(path) {
        const value = readFile(path);
        return value === null ? null : value !== '0';
    }

    _findLed() {
        let enumerator;
        try {
            enumerator = Gio.File.new_for_path(LED_ROOT).enumerate_children(
                'standard::name', Gio.FileQueryInfoFlags.NONE, null);
        } catch {
            return null;
        }

        try {
            let info;
            while ((info = enumerator.next_file(null)) !== null) {
                const name = info.get_name();
                if (name.endsWith('::capslock'))
                    return `${LED_ROOT}/${name}/brightness`;
            }
        } finally {
            enumerator.close(null);
        }
        return null;
    }
}
