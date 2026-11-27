// SPDX-License-Identifier: MIT
//
// GNOME Shell shows a brightness OSD for every BrightnessManager change,
// including each value change while the Quick Settings brightness slider is
// being dragged. Suppress the OSD only during that drag; keyboard brightness
// keys, auto-brightness and other sources keep the normal OSD.

import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const ATTACH_RETRY_MS = 250;
const ATTACH_MAX_ATTEMPTS = 40;

export class BrightnessOsdGuard {
    constructor() {
        this._manager = null;
        this._original = null;
        this._patched = null;
        this._slider = null;
        this._beginId = 0;
        this._endId = 0;
        this._destroyId = 0;
        this._indicators = null;
        this._childAddedId = 0;
        this._retryTimerId = 0;
        this._dragging = false;
    }

    enable() {
        this._manager = Main.brightnessManager;
        if (!this._manager || typeof this._manager._showOSD !== 'function')
            return;

        this._original = this._manager._showOSD;
        this._patched = (...args) => {
            if (this._dragging)
                return;
            return this._original.apply(this._manager, args);
        };
        this._manager._showOSD = this._patched;

        if (this._connectSlider())
            return;

        // QuickSettings._setupIndicators() is async; wait for _brightness.
        const indicators = Main.panel.statusArea.quickSettings?._indicators;
        if (indicators) {
            this._indicators = indicators;
            this._childAddedId = indicators.connect('child-added', () => {
                if (this._connectSlider())
                    this._stopWatching();
            });
        }

        let attempts = 0;
        this._retryTimerId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT, ATTACH_RETRY_MS, () => {
                if (this._connectSlider() || ++attempts >= ATTACH_MAX_ATTEMPTS) {
                    this._retryTimerId = 0;
                    this._stopWatching();
                    return GLib.SOURCE_REMOVE;
                }
                return GLib.SOURCE_CONTINUE;
            });
    }

    _connectSlider() {
        if (this._slider)
            return true;

        const indicator = Main.panel.statusArea.quickSettings?._brightness;
        const slider = indicator?.quickSettingsItems?.[0]?.slider;
        if (!slider)
            return false;

        this._slider = slider;
        this._beginId = slider.connect('drag-begin', () => {
            this._dragging = true;
        });
        this._endId = slider.connect('drag-end', () => {
            this._dragging = false;
        });
        this._destroyId = slider.connect('destroy', () => {
            this._dragging = false;
            this._slider = null;
            this._beginId = 0;
            this._endId = 0;
            this._destroyId = 0;
        });
        return true;
    }

    _stopWatching() {
        if (this._indicators && this._childAddedId)
            this._indicators.disconnect(this._childAddedId);
        this._indicators = null;
        this._childAddedId = 0;
        if (this._retryTimerId) {
            GLib.source_remove(this._retryTimerId);
            this._retryTimerId = 0;
        }
    }

    disable() {
        this._stopWatching();
        this._dragging = false;
        if (this._slider) {
            if (this._beginId)
                this._slider.disconnect(this._beginId);
            if (this._endId)
                this._slider.disconnect(this._endId);
            if (this._destroyId)
                this._slider.disconnect(this._destroyId);
        }
        this._slider = null;
        this._beginId = 0;
        this._endId = 0;
        this._destroyId = 0;

        if (this._manager && this._manager._showOSD === this._patched)
            this._manager._showOSD = this._original;
        this._manager = null;
        this._original = null;
        this._patched = null;
    }
}
