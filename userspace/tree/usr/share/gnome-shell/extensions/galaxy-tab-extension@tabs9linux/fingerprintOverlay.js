// SPDX-License-Identifier: MIT
//
// Under-display fingerprint target, merged into the shell extension so it is
// also present on the lock screen and in the GDM greeter.  It holds no
// authentication state: it reads the driver's short-lived leases, tells the
// root broker that a visible target is available, and acknowledges a light
// request only after the drawn frame has been presented.  The target is a
// black card holding the ring, with no text; a press outside the card
// cancels the pending verification without blocking the session UI.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import cairo from 'cairo';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Config from 'resource:///org/gnome/shell/misc/config.js';

const ACTIVE_LEASE = '/run/gts9wifi-fingerprint/active';
const LIGHT_REQUEST = '/run/gts9wifi-fingerprint/light';
const BUS_NAME = 'io.github.lymeeee.Gts9wifiFingerprintUI';
const OBJECT_PATH = '/io/github/lymeeee/Gts9wifiFingerprintUI';
const INTERFACE = BUS_NAME;

const RAW_WIDTH = 1600;
const RAW_HEIGHT = 2560;
// The FOD rect is reported in the portrait touch coordinate space.  This is
// the X710 centre the kernel accepts; the driver writes the same rect.
const DEFAULT_FOD_RECT = [700, 2250, 960, 2480];
// 14.8 mm optical target on the 147.7 mm short side of the X710 panel.
const SENSOR_DIAMETER_RATIO = 14.8 / 147.7;
const CARD_PADDING = 24;
const CARD_RADIUS = 28;
const CARD_BORDER_WIDTH = 2;
const CARD_BORDER_RGBA = [1, 1, 1, 1];
const RING_WIDTH = 3.5;
// GNOME 50 removed the X11-only input-region chrome option; non-reactive
// actors stay input-transparent without it.
function topChromeOptions(trackFullscreen) {
    const options = {trackFullscreen};
    if (Number.parseInt(Config.PACKAGE_VERSION, 10) < 50)
        options.affectsInputRegion = false;
    return options;
}

const TRANSFORM_POINTS = [
    (u, v) => [u, v],
    (u, v) => [1 - v, u],
    (u, v) => [1 - u, 1 - v],
    (u, v) => [v, 1 - u],
    (u, v) => [1 - u, v],
    (u, v) => [v, u],
    (u, v) => [u, 1 - v],
    (u, v) => [1 - v, 1 - u],
];

function readText(path) {
    try {
        const [, bytes] = GLib.file_get_contents(path);
        return new TextDecoder().decode(bytes);
    } catch {
        return '';
    }
}

function parseActiveLease(contents, now) {
    const match = /^active ([0-9]+)(?: [a-z]+)?\n?$/.exec(contents ?? '');
    if (!match)
        return false;
    const expires = Number(match[1]);
    return Number.isSafeInteger(expires) && expires > now &&
        expires - now <= 3_100_000;
}

function parseLightRequest(contents, now) {
    const match = /^prepare ([0-9]+)\n?$/.exec(contents ?? '');
    const token = match ? Number(match[1]) : 0;
    return Number.isSafeInteger(token) && token > 0 && token <= now &&
        now - token < 1_000_000 ? token : 0;
}

function parseFodRect(contents) {
    const values = (contents ?? '').split(/\s+/).filter(field => field !== '');
    if (values.length !== 4)
        return null;
    const rect = values.map(value => Number(value));
    if (!rect.every(Number.isInteger) || rect[2] <= rect[0] || rect[3] <= rect[1])
        return null;
    return rect;
}

function findFodRect() {
    const directory = Gio.File.new_for_path('/sys/bus/i2c/devices');
    let enumerator = null;
    try {
        enumerator = directory.enumerate_children('standard::name',
            Gio.FileQueryInfoFlags.NONE, null);
        for (let info = enumerator.next_file(null); info; info = enumerator.next_file(null)) {
            const name = info.get_name();
            const entry = `/sys/bus/i2c/devices/${name}`;
            if (readText(`${entry}/name`).trim().toLowerCase() !== 'fts1ba90a')
                continue;
            const rect = parseFodRect(readText(`${entry}/fod_rect`));
            if (rect)
                return rect;
        }
    } catch {
        // The sensor is not ready yet; fall back to the X710 rect.
    } finally {
        enumerator?.close(null);
    }
    return DEFAULT_FOD_RECT;
}

function sensorFractions(rect, transform) {
    const [left, top, right, bottom] = rect;
    // The DTS applies touchscreen-swapped-x-y and touchscreen-inverted-x:
    // landscape x = raw y, landscape y = RAW_WIDTH - 1 - raw x.  Transform 0
    // is that native landscape panel; Mutter's rotation is applied after it.
    const u = ((top + bottom) / 2) / RAW_HEIGHT;
    const v = 1 - ((left + right) / 2) / RAW_WIDTH;
    return TRANSFORM_POINTS[transform & 7](u, v);
}

function sensorGeometry(rect, transform, width, height) {
    const [u, v] = sensorFractions(rect, transform);
    const diameter = Math.round(Math.min(width, height) * SENSOR_DIAMETER_RATIO);
    return {cx: u * width, cy: v * height, radius: diameter / 2};
}

export class FingerprintOverlay {
    constructor() {
        this._container = null;
        this._area = null;
        this._card = null;
        this._monitor = null;
        this._rect = DEFAULT_FOD_RECT;
        this._transform = 0;
        this._active = false;
        this._pressed = false;
        this._dismissed = false;
        this._lightToken = 0;
        this._presentedToken = 0;
        this._presentingToken = 0;
        this._presentPaints = 0;
        this._paintId = 0;
        this._presentTimeoutId = 0;
        this._tickId = 0;
        this._nextPulse = 0;
        this._sessionId = null;
        this._sessionLookup = false;
        this._pulsePending = null;
        this._brokerErrorLogged = false;
        this._monitorsId = 0;
        this._sessionModeId = 0;
        this._capturedId = 0;
    }

    enable() {
        this._area = new St.DrawingArea({reactive: false});
        this._area.connect('repaint', actor => this._draw(actor));

        // The actor spans the monitor but stays input-transparent: the lock
        // screen and GDM already hold a modal grab, so presses are observed
        // through a stage capture handler instead of an actor grab.
        this._container = new St.Widget({reactive: false, visible: false});
        this._container.add_child(this._area);
        Main.layoutManager.addTopChrome(this._container, topChromeOptions(false));

        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => {
            this._refreshGeometry();
            this._layout();
            this._area.queue_repaint();
        });
        this._sessionModeId = Main.sessionMode.connect('updated', () => {
            this._sessionId = null;
            this._layout();
            this._raise();
        });

        this._refreshGeometry();
        this._layout();
        this._tickId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            this._tick();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._tickId) {
            GLib.source_remove(this._tickId);
            this._tickId = 0;
        }
        this._cancelPresentation();
        this._setCapture(false);
        if (this._monitorsId) {
            Main.layoutManager.disconnect(this._monitorsId);
            this._monitorsId = 0;
        }
        if (this._sessionModeId) {
            Main.sessionMode.disconnect(this._sessionModeId);
            this._sessionModeId = 0;
        }
        if (this._container) {
            Main.layoutManager.removeChrome(this._container);
            this._container.destroy();
            this._container = null;
        }
        this._area = null;
    }

    _refreshGeometry() {
        this._rect = findFodRect();
        this._queryTransform();
    }

    _queryTransform() {
        Gio.DBus.session.call(
            'org.gnome.Mutter.DisplayConfig',
            '/org/gnome/Mutter/DisplayConfig',
            'org.gnome.Mutter.DisplayConfig',
            'GetCurrentState',
            null, null, Gio.DBusCallFlags.NONE, 1000, null,
            (connection, result) => {
                try {
                    const reply = connection.call_finish(result);
                    const [, , logicalMonitors] = reply.deep_unpack();
                    for (const monitor of logicalMonitors) {
                        const specs = monitor[5];
                        if (!specs.some(spec => spec[0] === 'DSI-1'))
                            continue;
                        this._transform = Number(monitor[3]) & 7;
                        this._layout();
                        this._area?.queue_repaint();
                        return;
                    }
                } catch {
                    // Keep the previous transform; geometry falls back to 0.
                }
            });
    }

    _layout() {
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor || !this._container)
            return;
        this._monitor = monitor;
        this._container.set_position(monitor.x, monitor.y);
        this._container.set_size(monitor.width, monitor.height);
        this._area.set_position(0, 0);
        this._area.set_size(monitor.width, monitor.height);
        const {cx, cy, radius} = sensorGeometry(
            this._rect, this._transform, monitor.width, monitor.height);
        const half = radius + RING_WIDTH / 2;
        const left = Math.max(0, Math.round(cx - half) - CARD_PADDING);
        const top = Math.max(0, Math.round(cy - half) - CARD_PADDING);
        const right = Math.min(monitor.width,
            Math.round(cx + half) + CARD_PADDING);
        const bottom = Math.min(monitor.height,
            Math.round(cy + half) + CARD_PADDING);
        this._card = {x: left, y: top, w: right - left, h: bottom - top};
        this._area.queue_repaint();
    }

    _tick() {
        const now = GLib.get_monotonic_time();
        if (!parseActiveLease(readText(ACTIVE_LEASE), now)) {
            this._dismissed = false;
            if (this._active)
                this._finishHide();
            return;
        }

        this._active = true;
        if (this._dismissed)
            return;
        if (!this._container.visible)
            this._show(now);
        else
            this._raise();
        if (now >= this._nextPulse) {
            this._pulse(true);
            this._nextPulse = now + 250_000;
        }

        const token = parseLightRequest(readText(LIGHT_REQUEST), now);
        if (token !== this._lightToken) {
            this._lightToken = token;
            this._pressed = token > 0;
            this._presentedToken = 0;
            this._area.queue_repaint();
            if (token)
                this._schedulePresentation(token);
            else
                this._cancelPresentation();
        }
    }

    _show(now) {
        this._layout();
        this._container.show();
        this._raise();
        this._setCapture(true);
        this._pressed = false;
        this._area.queue_repaint();
        this._pulse(true);
        this._nextPulse = now + 250_000;
    }

    _finishHide() {
        this._cancelPresentation();
        this._setCapture(false);
        this._active = false;
        this._pressed = false;
        this._lightToken = 0;
        this._presentedToken = 0;
        this._container.hide();
        this._pulse(false);
    }

    _dismiss() {
        if (!this._active)
            return;
        if (this._sessionId)
            this._callBroker('Cancel', new GLib.Variant('(s)', [this._sessionId]));
        this._dismissed = true;
        this._setCapture(false);
        this._container.hide();
        this._cancelPresentation();
    }

    // The lock screen's lightbox and the GDM dialog are raised to the top of
    // uiGroup, above our top chrome; keep the target above them so the card
    // is not dimmed into the dark shade.  The shield raises its lightbox
    // during the fade, so re-check while the target is up.
    _raise() {
        if (!this._container?.visible || Main.sessionMode.currentMode === 'user')
            return;
        if (Main.uiGroup.get_last_child() !== this._container)
            Main.uiGroup.set_child_above_sibling(this._container, null);
    }

    _setCapture(active) {
        if (active && !this._capturedId) {
            this._capturedId = global.stage.connect('captured-event',
                (actor, event) => this._onCapturedEvent(event));
        } else if (!active && this._capturedId) {
            global.stage.disconnect(this._capturedId);
            this._capturedId = 0;
        }
    }

    _onCapturedEvent(event) {
        if (!this._active || this._dismissed || !this._container?.visible)
            return Clutter.EVENT_PROPAGATE;
        const type = event.type();
        if (type !== Clutter.EventType.BUTTON_PRESS &&
            type !== Clutter.EventType.TOUCH_BEGIN)
            return Clutter.EVENT_PROPAGATE;
        const card = this._card;
        if (!card)
            return Clutter.EVENT_PROPAGATE;
        const [x, y] = event.get_coords();
        if (!Number.isFinite(x) || !Number.isFinite(y))
            return Clutter.EVENT_PROPAGATE;
        const monitor = this._monitor;
        const localX = x - (monitor?.x ?? 0);
        const localY = y - (monitor?.y ?? 0);
        const inside = localX >= card.x && localX < card.x + card.w &&
            localY >= card.y && localY < card.y + card.h;
        if (!inside)
            this._dismiss();
        return Clutter.EVENT_PROPAGATE;
    }

    _draw(area) {
        const cr = area.get_context();
        const [width, height] = area.get_surface_size();
        cr.setOperator(cairo.Operator.SOURCE);
        cr.setSourceRGBA(0, 0, 0, 0);
        cr.paint();
        if (this._active) {
            const {cx, cy, radius} = sensorGeometry(
                this._rect, this._transform, width, height);
            const card = this._card;
            if (card) {
                const r = Math.min(CARD_RADIUS, card.w / 2, card.h / 2);
                cr.newPath();
                cr.arc(card.x + r, card.y + r, r, Math.PI, 1.5 * Math.PI);
                cr.arc(card.x + card.w - r, card.y + r, r,
                    1.5 * Math.PI, 2 * Math.PI);
                cr.arc(card.x + card.w - r, card.y + card.h - r, r,
                    0, 0.5 * Math.PI);
                cr.arc(card.x + r, card.y + card.h - r, r,
                    0.5 * Math.PI, Math.PI);
                cr.closePath();
                cr.setSourceRGBA(0, 0, 0, 1);
                cr.fillPreserve();
                cr.setSourceRGBA(...CARD_BORDER_RGBA);
                cr.setLineWidth(CARD_BORDER_WIDTH);
                cr.stroke();
            }
            cr.setSourceRGBA(1, 1, 1, 1);
            cr.setLineWidth(RING_WIDTH);
            cr.arc(cx, cy, radius, 0, 2 * Math.PI);
            if (this._pressed)
                cr.fill();
            else
                cr.stroke();
        }
        cr.$dispose();
    }

    _schedulePresentation(token) {
        this._cancelPresentation();
        this._presentingToken = token;
        this._presentPaints = 0;
        this._paintId = global.stage.connect('after-paint', () => {
            this._presentPaints++;
            if (this._presentPaints < 2) {
                // Force a second frame so the first paint that counted is not
                // an older commit than the one carrying the shade.
                this._area.queue_repaint();
                return;
            }
            this._disconnectPaint();
            this._presentTimeoutId = GLib.timeout_add(
                GLib.PRIORITY_DEFAULT, 35, () => {
                    this._presentTimeoutId = 0;
                    this._present(token);
                    return GLib.SOURCE_REMOVE;
                });
        });
    }

    _cancelPresentation() {
        this._disconnectPaint();
        if (this._presentTimeoutId) {
            GLib.source_remove(this._presentTimeoutId);
            this._presentTimeoutId = 0;
        }
        this._presentingToken = 0;
    }

    _disconnectPaint() {
        if (this._paintId) {
            global.stage.disconnect(this._paintId);
            this._paintId = 0;
        }
    }

    _present(token) {
        const now = GLib.get_monotonic_time();
        if (token !== this._lightToken || this._presentingToken !== token ||
            !this._active || this._dismissed || !this._container.visible ||
            token === this._presentedToken ||
            parseLightRequest(readText(LIGHT_REQUEST), now) !== token) {
            this._presentingToken = 0;
            return;
        }
        if (this._sessionId)
            this._callBroker('Presented',
                new GLib.Variant('(st)', [this._sessionId, token]));
        this._presentedToken = token;
        this._presentingToken = 0;
    }

    _ensureSession() {
        if (this._sessionId || this._sessionLookup)
            return;
        this._sessionLookup = true;
        Gio.DBus.system.call(
            'org.freedesktop.login1',
            '/org/freedesktop/login1/seat/seat0',
            'org.freedesktop.DBus.Properties',
            'Get',
            new GLib.Variant('(ss)',
                ['org.freedesktop.login1.Seat', 'ActiveSession']),
            new GLib.VariantType('(v)'), Gio.DBusCallFlags.NONE, 1000, null,
            (connection, result) => {
                this._sessionLookup = false;
                try {
                    const reply = connection.call_finish(result);
                    let [active] = reply.deep_unpack();
                    if (active instanceof GLib.Variant)
                        active = active.deep_unpack();
                    const [sessionId, sessionPath] = active;
                    if (sessionId && sessionPath && sessionPath !== '/')
                        this._sessionId = String(sessionId);
                } catch {
                    this._sessionId = null;
                }
                if (this._sessionId && this._pulsePending !== null) {
                    const pending = this._pulsePending;
                    this._pulsePending = null;
                    this._callBroker('Pulse',
                        new GLib.Variant('(sb)', [this._sessionId, pending]));
                }
            });
    }

    _pulse(available) {
        if (!this._sessionId) {
            this._pulsePending = available;
            this._ensureSession();
            return;
        }
        this._pulsePending = null;
        this._callBroker('Pulse',
            new GLib.Variant('(sb)', [this._sessionId, available]));
    }

    _callBroker(method, parameters) {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters, null,
            Gio.DBusCallFlags.NONE, 2000, null,
            (connection, result) => {
                try {
                    connection.call_finish(result);
                    this._brokerErrorLogged = false;
                } catch (error) {
                    const message = String(error?.message ?? error);
                    if (message.includes('NotActiveSession')) {
                        this._sessionId = null;
                        if (this._active)
                            this._pulsePending = true;
                    }
                    if (!this._brokerErrorLogged) {
                        console.log(`Galaxy Tab fingerprint ${method}: ${message}`);
                        this._brokerErrorLogged = true;
                    }
                }
            });
    }
}
