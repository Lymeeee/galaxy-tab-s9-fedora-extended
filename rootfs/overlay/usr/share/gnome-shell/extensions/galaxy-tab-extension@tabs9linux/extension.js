// SPDX-License-Identifier: MIT
//
// Bootstrap copy shipped in the image so the extension UUID exists and is
// enabled before the userspace package is installed; the package replaces
// this directory with the full extension.

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class Gts9wifiExtension extends Extension {
    enable() {
    }

    disable() {
    }
}
