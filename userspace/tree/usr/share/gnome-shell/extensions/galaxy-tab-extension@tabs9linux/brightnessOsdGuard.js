// SPDX-License-Identifier: MIT
//
// GNOME Shell shows a brightness OSD for every BrightnessManager change,
// including each value change while the Quick Settings brightness slider is
// being dragged. Suppress the OSD only during that drag; keyboard brightness
// keys, auto-brightness and other sources keep the normal OSD.

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class BrightnessOsdGuard {
    constructor() {
        this._manager = null;
        this._original = null;
        this._patched = null;
        this._slider = null;
        this._beginId = 0;
        this._endId = 0;
        this._destroyId = 0;
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
        this._connectSlider();
    }

    _connectSlider() {
        const indicator = Main.panel.statusArea.quickSettings?._brightness;
        const slider = indicator?.quickSettingsItems?.[0]?.slider;
        if (!slider)
            return;

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
    }

    disable() {
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
