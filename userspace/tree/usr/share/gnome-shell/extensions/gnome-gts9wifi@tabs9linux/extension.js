// SPDX-License-Identifier: MIT
//
// All of this extension's UI is its settings page (prefs.js), which is where
// the device-specific controls live.  There is deliberately no panel or Quick
// Settings presence: these are set-once controls rather than something worth
// toggling from the top bar, and on a tablet a stray panel toggle is easy to
// hit by accident.
//
// The extension also has to be enabled for its settings page to be reachable
// from the Extensions app.  At runtime it helps the on-screen keyboard:
// oskFocus.js opens it for touch-focused text fields of Chromium-based apps,
// keyboardButton.js adds a floating button for apps that never ask for it.
// sleepWarning.js keeps gsd-power's "Automatic suspend" warning from
// lighting the dark screen (which kept the tablet from ever suspending).
// topOsd.js backs the transient S Pen dock and Caps Lock notices.

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {KeyboardButton} from './keyboardButton.js';
import {OskFocus} from './oskFocus.js';
import {SleepWarning} from './sleepWarning.js';
import {CornerMask} from './cornerMask.js';
import {TopOsd} from './topOsd.js';
import {SpenOsd} from './spenOsd.js';
import {CapsLockOsd} from './capsLockOsd.js';

export default class Gts9wifiExtension extends Extension {
    enable() {
        this._oskFocus = new OskFocus();
        this._oskFocus.enable();
        this._keyboardButton = new KeyboardButton(this.getSettings());
        this._keyboardButton.enable();
        this._sleepWarning = new SleepWarning();
        this._sleepWarning.enable();
        this._cornerMask = new CornerMask(this.getSettings());
        this._cornerMask.enable();
        this._topOsd = new TopOsd();
        this._topOsd.enable();
        this._spenOsd = new SpenOsd(this._topOsd);
        this._spenOsd.enable();
        this._capsLockOsd = new CapsLockOsd(this._topOsd);
        this._capsLockOsd.enable();
    }

    disable() {
        this._capsLockOsd?.disable();
        this._capsLockOsd = null;
        this._spenOsd?.disable();
        this._spenOsd = null;
        this._topOsd?.disable();
        this._topOsd = null;
        this._cornerMask?.disable();
        this._cornerMask = null;
        this._sleepWarning?.disable();
        this._sleepWarning = null;
        this._keyboardButton?.disable();
        this._keyboardButton = null;
        this._oskFocus?.disable();
        this._oskFocus = null;
    }
}
