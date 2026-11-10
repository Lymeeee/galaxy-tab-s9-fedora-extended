// SPDX-License-Identifier: MIT
//
// The S Pen and Caps Lock notices reuse the Shell's own OSD manager.  The
// extension moves those windows to the top edge: Shell anchors every OSD at
// the bottom with y_align END and a bottom margin, so switching the alignment
// and mirroring the margin in stylesheet.css puts all OSDs above instead.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class TopOsd {
    constructor() {
        this._monitorsChangedId = 0;
    }

    enable() {
        this._applyPosition();
        this._monitorsChangedId = Main.layoutManager.connect('monitors-changed',
            () => this._applyPosition());
    }

    disable() {
        if (this._monitorsChangedId) {
            Main.layoutManager.disconnect(this._monitorsChangedId);
            this._monitorsChangedId = 0;
        }
        for (const osd of Main.osdWindowManager?._osdWindows ?? []) {
            if (osd)
                osd.y_align = Clutter.ActorAlign.END;
        }
    }

    show(iconName, text, level = null) {
        const monitor = Main.layoutManager.primaryIndex ?? 0;
        // Shell 50 shows the level bar whenever the value is not null, and its
        // BarLevel paints everything above value 1 as red overdrive, so feed
        // it a 0-1 fraction rather than a 0-100 percentage.
        const value = Number.isFinite(level)
            ? Math.max(0, Math.min(100, level)) / 100 : null;
        Main.osdWindowManager.showOne(monitor, Gio.ThemedIcon.new(iconName),
            text, value, 1);
    }

    _applyPosition() {
        for (const osd of Main.osdWindowManager?._osdWindows ?? []) {
            if (osd)
                osd.y_align = Clutter.ActorAlign.START;
        }
    }
}
