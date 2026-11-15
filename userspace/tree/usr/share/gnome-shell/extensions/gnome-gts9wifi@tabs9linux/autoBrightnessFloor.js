// SPDX-License-Identifier: MIT
//
// Keep auto-brightness from dimming the panel below the point where it
// leaves DC dimming.  GNOME 50 combines the ambient target from gsd-power
// with the manual slider bias (target + scale - 0.5), so raise the target
// by the current bias instead of clamping only at 36%, which would still
// let a lowered slider take the screen below the floor.  Only the D-Bus
// SetAutoBrightnessTarget path goes through this accessor; manual slider
// changes bypass it and may still go below 36%.

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const FLOOR = 0.36;

export class AutoBrightnessFloor {
    constructor(settings) {
        this._settings = settings;
        this._manager = null;
        this._originalGetter = null;
        this._originalSetter = null;
        this._patchedSetter = null;
        this._settingsId = 0;
    }

    enable() {
        this._manager = Main.brightnessManager;
        if (!this._manager)
            return;

        const descriptor = Object.getOwnPropertyDescriptor(
            Object.getPrototypeOf(this._manager), 'autoBrightnessTarget');
        if (!descriptor || typeof descriptor.get !== 'function' ||
            typeof descriptor.set !== 'function')
            return;

        this._originalGetter = descriptor.get;
        this._originalSetter = descriptor.set;
        this._patchedSetter = target => {
            this._originalSetter.call(this._manager, this._clamp(target));
        };
        Object.defineProperty(this._manager, 'autoBrightnessTarget', {
            configurable: true,
            get: () => this._originalGetter.call(this._manager),
            set: this._patchedSetter,
        });

        this._settingsId = this._settings.connect(
            'changed::auto-brightness-floor', () => this._onSettingChanged());
        this._onSettingChanged();
    }

    _clamp(target) {
        if (!Number.isFinite(target) || target < 0 ||
            !this._settings.get_boolean('auto-brightness-floor'))
            return target;

        const scale = this._manager.globalScale;
        const bias = (scale ? scale.value : 0.5) - 0.5;
        return Math.max(target, FLOOR - bias);
    }

    // Apply the floor as soon as the option is turned on; the sensor may
    // not send a new target for a while if the light is stable.
    _onSettingChanged() {
        if (!this._settings.get_boolean('auto-brightness-floor') ||
            this._originalGetter.call(this._manager) < 0)
            return;
        this._manager.autoBrightnessTarget =
            this._originalGetter.call(this._manager);
    }

    disable() {
        if (this._settingsId) {
            this._settings.disconnect(this._settingsId);
            this._settingsId = 0;
        }
        if (this._manager) {
            const descriptor = Object.getOwnPropertyDescriptor(
                this._manager, 'autoBrightnessTarget');
            if (descriptor && descriptor.set === this._patchedSetter)
                delete this._manager.autoBrightnessTarget;
        }
        this._manager = null;
        this._originalGetter = null;
        this._originalSetter = null;
        this._patchedSetter = null;
    }
}
