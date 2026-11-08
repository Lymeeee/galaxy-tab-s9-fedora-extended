// SPDX-License-Identifier: MIT
//
// The Tab S9's OLED is a rectangle, so the desktop reaches the corners with
// square edges.  One UI masks those corners in SurfaceFlinger; draw the same
// black rounded wedges above the shell so full-screen content gets the
// familiar rounded look.

import St from 'gi://St';
import cairo from 'cairo';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const REFERENCE_WIDTH = 2560;
const DEFAULT_RADIUS = 32;

export class CornerMask {
    constructor(settings) {
        this._settings = settings;
        this._actors = [];
        this._settingsIds = [];
        this._monitorsId = 0;
        this._sessionId = 0;
    }

    enable() {
        this._settingsIds = [
            this._settings.connect('changed::rounded-corners', () => this._build()),
            this._settings.connect('changed::rounded-corner-radius', () => this._repaint()),
        ];
        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => this._build());
        this._sessionId = Main.sessionMode.connect('updated', () => this._raise());
        this._build();
    }

    disable() {
        for (const id of this._settingsIds)
            this._settings.disconnect(id);
        this._settingsIds = [];

        if (this._monitorsId) {
            Main.layoutManager.disconnect(this._monitorsId);
            this._monitorsId = 0;
        }
        if (this._sessionId) {
            Main.sessionMode.disconnect(this._sessionId);
            this._sessionId = 0;
        }

        this._destroy();
    }

    _build() {
        this._destroy();
        if (!this._settings.get_boolean('rounded-corners'))
            return;

        for (const monitor of Main.layoutManager.monitors) {
            const area = new St.DrawingArea({
                reactive: false,
                x: monitor.x,
                y: monitor.y,
                width: monitor.width,
                height: monitor.height,
            });
            area.connect('repaint', (actor, cr) => this._draw(actor, cr));
            this._actors.push(area);
            Main.uiGroup.add_child(area);
            Main.uiGroup.set_child_above_sibling(area, null);
            area.queue_repaint();
        }
    }

    _destroy() {
        for (const actor of this._actors)
            actor.destroy();
        this._actors = [];
    }

    _raise() {
        for (const actor of this._actors)
            Main.uiGroup.set_child_above_sibling(actor, null);
    }

    _repaint() {
        for (const actor of this._actors)
            actor.queue_repaint();
    }

    _draw(area, cr) {
        const [width, height] = area.get_surface_size();
        const radius = Math.max(4, Math.round(width * this._settings.get_int('rounded-corner-radius') / REFERENCE_WIDTH));

        cr.setOperator(cairo.Operator.CLEAR);
        cr.paint();
        cr.setOperator(cairo.Operator.SOURCE);
        cr.setSourceRGBA(0, 0, 0, 1);

        // top-left
        cr.moveTo(0, 0);
        cr.lineTo(radius, 0);
        cr.arcNegative(radius, radius, radius, 1.5 * Math.PI, Math.PI);
        cr.closePath();

        // top-right
        cr.moveTo(width, 0);
        cr.lineTo(width - radius, 0);
        cr.arc(width - radius, radius, radius, 1.5 * Math.PI, 2 * Math.PI);
        cr.closePath();

        // bottom-left
        cr.moveTo(0, height);
        cr.lineTo(0, height - radius);
        cr.arcNegative(radius, height - radius, radius, Math.PI, 0.5 * Math.PI);
        cr.closePath();

        // bottom-right
        cr.moveTo(width, height);
        cr.lineTo(width, height - radius);
        cr.arc(width - radius, height - radius, radius, 0, 0.5 * Math.PI);
        cr.closePath();

        cr.fill();
    }
}
