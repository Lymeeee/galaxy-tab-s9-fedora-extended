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
        Main.osdWindowManager.showOne(monitor, Gio.ThemedIcon.new(iconName),
            text, level ?? -1, 100);
    }
}
