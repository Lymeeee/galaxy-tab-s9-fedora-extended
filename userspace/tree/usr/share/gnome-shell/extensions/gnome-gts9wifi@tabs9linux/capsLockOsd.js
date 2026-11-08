// SPDX-License-Identifier: MIT
//
// Caps Lock OSD for the pogo keyboard.  The key event itself says nothing
// reliable about the new state (the seat updates it after the event), so read
// the keyboard LED that the kernel toggles for us.  The LED device number can
// change between boots, so look it up by its "::capslock" suffix.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const CAPS_LOCK_KEYSYM = 0xffe5;
const LED_ROOT = '/sys/class/leds';
const SYNC_DELAY_MS = 40;

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
        this._capturedId = 0;
        this._ledPath = null;
        this._state = null;
    }

    enable() {
        this._capturedId = global.stage.connect('captured-event',
            (_actor, event) => this._onEvent(event));
        this._state = this._readLed();
    }

    disable() {
        if (this._capturedId) {
            global.stage.disconnect(this._capturedId);
            this._capturedId = 0;
        }
        this._ledPath = null;
    }

    _onEvent(event) {
        if (event.type() !== Clutter.EventType.KEY_PRESS ||
            event.get_key_symbol() !== CAPS_LOCK_KEYSYM)
            return Clutter.EVENT_PROPAGATE;

        GLib.timeout_add(GLib.PRIORITY_DEFAULT, SYNC_DELAY_MS, () => {
            this._sync();
            return GLib.SOURCE_REMOVE;
        });
        return Clutter.EVENT_PROPAGATE;
    }

    _sync() {
        const state = this._readLed();
        if (state === null || state === this._state)
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
