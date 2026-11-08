// SPDX-License-Identifier: MIT
//
// A top-centre OSD for the S Pen and Caps Lock notices.  It reuses the shape
// of the Shell's own volume/brightness OSD -- dark translucent rounded pill,
// symbolic icon, label and, when a percentage is known, a level bar -- but
// anchors itself under the top panel instead of at the bottom edge.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import cairo from 'cairo';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const BAR_WIDTH = 180;
const BAR_HEIGHT = 6;
const SHOW_MS = 1800;
const FADE_IN_MS = 120;
const FADE_OUT_MS = 220;

export class TopOsd {
    constructor() {
        this._actor = null;
        this._icon = null;
        this._label = null;
        this._bar = null;
        this._level = 0;
        this._iconName = '';
        this._hideId = 0;
    }

    enable() {
        this._icon = new St.Icon({
            icon_size: 28,
            style: 'color: #ffffff;',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._label = new St.Label({
            style: 'color: #ffffff; font-weight: bold; font-size: 15px;',
        });
        this._bar = new St.DrawingArea({
            width: BAR_WIDTH,
            height: BAR_HEIGHT,
            visible: false,
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._bar.connect('repaint', area => this._drawBar(area));

        const text = new St.BoxLayout({
            vertical: true,
            y_align: Clutter.ActorAlign.CENTER,
            style: 'spacing: 4px;',
        });
        text.add_child(this._label);
        text.add_child(this._bar);

        this._actor = new St.BoxLayout({
            vertical: false,
            visible: false,
            opacity: 0,
            style: 'background-color: rgba(20, 20, 22, 0.92); ' +
                'border-radius: 20px; padding: 10px 18px; ' +
                'border: 1px solid rgba(255, 255, 255, 0.08); ' +
                'spacing: 14px;',
        });
        this._actor.add_child(this._icon);
        this._actor.add_child(text);

        Main.uiGroup.add_child(this._actor);
        Main.uiGroup.set_child_above_sibling(this._actor, null);
    }

    disable() {
        if (this._hideId) {
            GLib.source_remove(this._hideId);
            this._hideId = 0;
        }
        this._actor?.destroy();
        this._actor = null;
        this._icon = null;
        this._label = null;
        this._bar = null;
    }

    show(iconName, text, level = null, duration = SHOW_MS) {
        if (!this._actor)
            return;

        if (this._iconName !== iconName) {
            this._iconName = iconName;
            this._icon.gicon = Gio.ThemedIcon.new(iconName);
        }
        this._label.text = text;

        if (level === null || level < 0 || level > 100) {
            this._bar.hide();
        } else {
            this._level = level;
            this._bar.show();
            this._bar.queue_repaint();
        }

        if (this._hideId) {
            GLib.source_remove(this._hideId);
            this._hideId = 0;
        }

        this._actor.remove_all_transitions();
        this._actor.show();
        this._actor.opacity = 0;
        this._position();
        this._actor.ease({
            opacity: 255,
            duration: FADE_IN_MS,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });

        this._hideId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, duration, () => {
            this._hideId = 0;
            this._actor?.ease({
                opacity: 0,
                duration: FADE_OUT_MS,
                mode: Clutter.AnimationMode.EASE_IN_QUAD,
                onComplete: () => this._actor?.hide(),
            });
            return GLib.SOURCE_REMOVE;
        });
    }

    _position() {
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;

        const [minWidth, natWidth] = this._actor.get_preferred_width(-1);
        const width = Math.max(minWidth, natWidth);
        const [minHeight, natHeight] = this._actor.get_preferred_height(width);
        const height = Math.max(minHeight, natHeight);
        const panelHeight = Main.layoutManager.panelBox?.height ?? 0;

        this._actor.set_position(
            monitor.x + Math.round((monitor.width - width) / 2),
            monitor.y + Math.max(12, panelHeight + 10));
    }

    _drawBar(area) {
        const cr = area.get_context();
        const [width, height] = area.get_surface_size();
        const radius = height / 2;

        cr.setOperator(cairo.Operator.CLEAR);
        cr.paint();
        cr.setOperator(cairo.Operator.SOURCE);

        cr.setSourceRGBA(1, 1, 1, 0.25);
        this._roundedRect(cr, 0, 0, width, height, radius);
        cr.fill();

        const fill = Math.max(0, Math.min(1, this._level / 100));
        if (fill > 0) {
            cr.setSourceRGBA(1, 1, 1, 0.95);
            this._roundedRect(cr, 0, 0,
                Math.max(radius * 2, width * fill), height, radius);
            cr.fill();
        }
        cr.$dispose();
    }

    _roundedRect(cr, x, y, width, height, radius) {
        const r = Math.min(radius, width / 2, height / 2);
        cr.newSubPath();
        cr.arc(x + r, y + r, r, Math.PI, 1.5 * Math.PI);
        cr.arc(x + width - r, y + r, r, 1.5 * Math.PI, 2 * Math.PI);
        cr.arc(x + width - r, y + height - r, r, 0, 0.5 * Math.PI);
        cr.arc(x + r, y + height - r, r, 0.5 * Math.PI, Math.PI);
        cr.closePath();
    }
}
