// SPDX-License-Identifier: MIT
//
// Device integration for the Galaxy Tab S9 Fedora port.  The corner mask and
// the under-display fingerprint target run in every supported session mode
// (user, lock screen, GDM greeter).  The remaining helpers only make sense in
// the user session: oskFocus.js opens the on-screen keyboard for touch-focused
// text fields of Chromium-based apps, keyboardButton.js adds a floating button
// for apps that never ask for it, sleepWarning.js keeps gsd-power's "Automatic
// suspend" warning from lighting the dark screen, topOsd.js backs the transient
// S Pen dock and Caps Lock notices, brightnessWarning.js warns when the panel
// leaves its DC dimming range, autoBrightnessFloor.js optionally keeps automatic
// brightness from taking the panel below that range, and brightnessOsdGuard.js
// hides the Shell OSD while the brightness slider is being dragged.

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {KeyboardButton} from './keyboardButton.js';
import {OskFocus} from './oskFocus.js';
import {SleepWarning} from './sleepWarning.js';
import {CornerMask} from './cornerMask.js';
import {FingerprintOverlay} from './fingerprintOverlay.js';
import {TopOsd} from './topOsd.js';
import {SpenOsd} from './spenOsd.js';
import {CapsLockOsd} from './capsLockOsd.js';
import {BrightnessWarning} from './brightnessWarning.js';
import {AutoBrightnessFloor} from './autoBrightnessFloor.js';
import {BrightnessOsdGuard} from './brightnessOsdGuard.js';

export default class GalaxyTabExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._userModules = null;

        this._cornerMask = new CornerMask(this._settings);
        this._cornerMask.enable();
        this._fingerprintOverlay = new FingerprintOverlay();
        this._fingerprintOverlay.enable();

        this._sessionModeId = Main.sessionMode.connect('updated',
            () => this._syncUserModules());
        this._syncUserModules();
    }

    _syncUserModules() {
        const userMode = Main.sessionMode.currentMode === 'user';
        if (userMode && !this._userModules)
            this._enableUserModules();
        else if (!userMode && this._userModules)
            this._disableUserModules();
    }

    _enableUserModules() {
        const modules = [];
        const oskFocus = new OskFocus();
        oskFocus.enable();
        modules.push(oskFocus);
        const keyboardButton = new KeyboardButton(this._settings);
        keyboardButton.enable();
        modules.push(keyboardButton);
        const sleepWarning = new SleepWarning();
        sleepWarning.enable();
        modules.push(sleepWarning);
        const topOsd = new TopOsd();
        topOsd.enable();
        modules.push(topOsd);
        const spenOsd = new SpenOsd(topOsd);
        spenOsd.enable();
        modules.push(spenOsd);
        const capsLockOsd = new CapsLockOsd(topOsd);
        capsLockOsd.enable();
        modules.push(capsLockOsd);
        const brightnessWarning = new BrightnessWarning(this._settings);
        brightnessWarning.enable();
        modules.push(brightnessWarning);
        const autoBrightnessFloor = new AutoBrightnessFloor(this._settings);
        autoBrightnessFloor.enable();
        modules.push(autoBrightnessFloor);
        const brightnessOsdGuard = new BrightnessOsdGuard();
        brightnessOsdGuard.enable();
        modules.push(brightnessOsdGuard);
        this._userModules = modules;
    }

    _disableUserModules() {
        if (!this._userModules)
            return;
        for (const module of this._userModules.slice().reverse())
            module.disable();
        this._userModules = null;
    }

    disable() {
        if (this._sessionModeId) {
            Main.sessionMode.disconnect(this._sessionModeId);
            this._sessionModeId = 0;
        }
        this._disableUserModules();
        this._fingerprintOverlay?.disable();
        this._fingerprintOverlay = null;
        this._cornerMask?.disable();
        this._cornerMask = null;
        this._settings = null;
    }
}
