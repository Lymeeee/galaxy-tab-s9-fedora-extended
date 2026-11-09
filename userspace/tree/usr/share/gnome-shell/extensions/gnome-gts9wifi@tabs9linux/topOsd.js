// SPDX-License-Identifier: MIT
//
// The S Pen and Caps Lock notices reuse the Shell's own OSD manager.  That
// gives them the exact same position, theme, level bar and fade as the
// volume/brightness popup without maintaining a second OSD implementation.

import Gio from 'gi://Gio';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class TopOsd {
    enable() {
    }

    disable() {
    }

    show(iconName, text, level = null) {
        const monitor = Main.layoutManager.primaryIndex ?? 0;
        // Shell 50 shows the level bar whenever the value is not null; a
        // negative sentinel (such as the old -1) drew a broken empty bar.
        const value = Number.isFinite(level)
            ? Math.max(0, Math.min(100, level)) : null;
        Main.osdWindowManager.showOne(monitor, Gio.ThemedIcon.new(iconName),
            text, value, 100);
    }
}
