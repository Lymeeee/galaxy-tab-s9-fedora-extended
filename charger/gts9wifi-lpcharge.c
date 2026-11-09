// SPDX-License-Identifier: MIT
//
// Off-mode charging screen for the Galaxy Tab S9 Fedora port.  This runs
// from the dracut initramfs when ABL passes lpcharge=1: it draws directly on
// /dev/fb0, blanks the backlight after 10 s, wakes on a short power press and
// continues the normal boot after a 5 s hold.
//
// Text is rendered with FreeType directly from the bundled font subsets.
// Pango/fontconfig are deliberately not used: inside the initramfs the
// Pango layout produced no glyphs (only the ring and background were drawn),
// even though the config and both subset files were present in the image.
// Loading the subsets by path keeps text independent of fontconfig.
//
// The same binary has a --preview mode so the Cairo layout and the embedded
// font subsets can be checked in userspace without flashing a bundle.

#define _GNU_SOURCE
#include <cairo/cairo.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_SYNTHESIS_H
#include <linux/fb.h>
#include <linux/input.h>
#include <linux/input-event-codes.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/poll.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <time.h>
#include <math.h>
#include <errno.h>

#define CANVAS_W 2560
#define CANVAS_H 1600
#define FONT_UI "Adwaita Sans"
#define FONT_CJK "Noto Sans CJK SC"
#define FONT_UI_PATH "/usr/share/fonts/gts9wifi/AdwaitaSans-GTS9.ttf"
#define FONT_CJK_PATH "/usr/share/fonts/gts9wifi/NotoSansCJKSC-GTS9.ttf"
#define HOLD_SECONDS 5.0
#define BLANK_SECONDS 10.0

static const double FG[3] = {0.94, 0.95, 0.97};
static const double ACCENT[3] = {0.318, 0.635, 0.855};

static FT_Library ft_lib;
static FT_Face ft_ui;
static FT_Face ft_cjk;

static void kmsg(const char *fmt, ...)
{
    char buf[256];
    va_list ap;
    int fd;
    int len;

    va_start(ap, fmt);
    len = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (len <= 0)
        return;
    fd = open("/dev/kmsg", O_WRONLY);
    if (fd < 0)
        return;
    if (write(fd, buf, (size_t)len) < 0)
        ;
    close(fd);
}

static int fonts_init(void)
{
    FT_Error ui;
    FT_Error cjk;

    if (FT_Init_FreeType(&ft_lib) != 0) {
        kmsg("gts9wifi-lpcharge: FreeType init failed");
        return -1;
    }
    ui = FT_New_Face(ft_lib, FONT_UI_PATH, 0, &ft_ui);
    cjk = FT_New_Face(ft_lib, FONT_CJK_PATH, 0, &ft_cjk);
    if (ui)
        ft_ui = NULL;
    if (cjk)
        ft_cjk = NULL;
    kmsg("gts9wifi-lpcharge: fonts ui=%d cjk=%d", ui == 0, cjk == 0);
    return (ft_ui || ft_cjk) ? 0 : -1;
}

struct reading {
    int percent;
    double volts;
    double amps;
    double watts;
    double temp;
};

struct backlight {
    char brightness[256];
    char max[256];
    int saved;
    int maximum;
};

struct fbdev {
    int fd;
    unsigned char *map;
    size_t length;
    int width;
    int height;
    int stride;
    cairo_surface_t *surface;
    cairo_t *cr;
};

static double mono_seconds(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static int read_text(const char *path, char *buf, size_t size)
{
    int fd = open(path, O_RDONLY);
    ssize_t n;

    if (fd < 0)
        return -1;
    n = read(fd, buf, size - 1);
    close(fd);
    if (n <= 0)
        return -1;
    buf[n] = '\0';
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r'))
        buf[--n] = '\0';
    return 0;
}

static int read_long(const char *path, long *value)
{
    char buf[128];
    char *end;

    if (read_text(path, buf, sizeof(buf)) < 0)
        return -1;
    *value = strtol(buf, &end, 10);
    return end == buf ? -1 : 0;
}

static int write_int(const char *path, int value)
{
    char buf[32];
    int fd;
    int len = snprintf(buf, sizeof(buf), "%d\n", value);

    fd = open(path, O_WRONLY);
    if (fd < 0)
        return -1;
    if (write(fd, buf, len) != len) {
        close(fd);
        return -1;
    }
    close(fd);
    return 0;
}

static int write_text(const char *path, const char *value)
{
    size_t len = strlen(value);
    int fd = open(path, O_WRONLY);

    if (fd < 0)
        return -1;
    if (write(fd, value, len) != (ssize_t)len) {
        close(fd);
        return -1;
    }
    close(fd);
    return 0;
}

static int find_power_supply(const char *prefix, char *out, size_t size)
{
    DIR *dir = opendir("/sys/class/power_supply");
    struct dirent *entry;

    if (!dir)
        return -1;
    while ((entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, prefix, strlen(prefix)) != 0)
            continue;
        snprintf(out, size, "/sys/class/power_supply/%s", entry->d_name);
        closedir(dir);
        return 0;
    }
    closedir(dir);
    return -1;
}

static void read_reading(struct reading *r)
{
    char path[320];
    char battery[256];
    char source[256];
    long value;

    memset(r, 0, sizeof(*r));
    battery[0] = '\0';
    source[0] = '\0';
    r->percent = -1;
    if (find_power_supply("sm5714-battery", battery, sizeof(battery)) == 0) {
        snprintf(path, sizeof(path), "%s/capacity", battery);
        if (read_long(path, &value) == 0)
            r->percent = (int)value;
        snprintf(path, sizeof(path), "%s/temp", battery);
        if (read_long(path, &value) == 0)
            r->temp = value / 10.0;
        else
            r->temp = NAN;
    }

    if (find_power_supply("tcpm-source-psy", source, sizeof(source)) == 0) {
        double volts = 0, amps = 0;

        snprintf(path, sizeof(path), "%s/voltage_now", source);
        if (read_long(path, &value) == 0)
            volts = value / 1e6;
        snprintf(path, sizeof(path), "%s/current_now", source);
        if (read_long(path, &value) == 0)
            amps = fabs(value) / 1e6;
        if (volts > 1.0 && amps > 0.01) {
            r->volts = volts;
            r->amps = amps;
            r->watts = volts * amps;
            return;
        }
    }

    if (battery[0]) {
        double volts = 0, amps = 0;

        snprintf(path, sizeof(path), "%s/voltage_now", battery);
        if (read_long(path, &value) == 0)
            volts = value / 1e6;
        snprintf(path, sizeof(path), "%s/current_now", battery);
        if (read_long(path, &value) == 0)
            amps = fabs(value) / 1e6;
        r->volts = volts;
        r->amps = amps;
        r->watts = volts * amps;
    }
    if (r->percent < 0)
        r->percent = 0;
}

static int utf8_decode(const char **text, unsigned *codepoint)
{
    const unsigned char *s = (const unsigned char *)*text;
    unsigned c = s[0];

    if (c < 0x80) {
        *codepoint = c;
        *text += 1;
        return 0;
    }
    if ((c & 0xe0) == 0xc0) {
        *codepoint = ((c & 0x1f) << 6) | (s[1] & 0x3f);
        *text += 2;
        return 0;
    }
    if ((c & 0xf0) == 0xe0) {
        *codepoint = ((c & 0x0f) << 12) | ((s[1] & 0x3f) << 6) |
            (s[2] & 0x3f);
        *text += 3;
        return 0;
    }
    if ((c & 0xf8) == 0xf0) {
        *codepoint = ((c & 0x07) << 18) | ((s[1] & 0x3f) << 12) |
            ((s[2] & 0x3f) << 6) | (s[3] & 0x3f);
        *text += 4;
        return 0;
    }
    return -1;
}

static void draw_text(cairo_t *cr, const char *text, double size,
                      double cx, double cy, const double color[3],
                      int bold, const char *family)
{
    struct {
        FT_Face face;
        FT_UInt index;
    } runs[128];
    FT_Face primary = strcmp(family, FONT_CJK) == 0 ? ft_cjk : ft_ui;
    FT_Face fallback = primary == ft_ui ? ft_cjk : ft_ui;
    const char *p = text;
    double width = 0;
    double pen;
    double baseline;
    int count = 0;
    int i;

    if (!primary)
        primary = fallback;
    if (!primary)
        return;
    if (!fallback)
        fallback = primary;

    FT_Set_Pixel_Sizes(primary, 0, (FT_UInt)(size + 0.5));
    if (fallback != primary)
        FT_Set_Pixel_Sizes(fallback, 0, (FT_UInt)(size + 0.5));

    while (*p && count < (int)(sizeof(runs) / sizeof(runs[0]))) {
        unsigned codepoint;
        FT_UInt index;
        FT_Face face = primary;

        if (utf8_decode(&p, &codepoint) < 0)
            break;
        index = FT_Get_Char_Index(primary, codepoint);
        if (!index && fallback != primary) {
            face = fallback;
            index = FT_Get_Char_Index(fallback, codepoint);
        }
        if (FT_Load_Glyph(face, index, FT_LOAD_DEFAULT) != 0)
            continue;
        if (bold)
            FT_GlyphSlot_Embolden(face->glyph);
        runs[count].face = face;
        runs[count].index = index;
        count++;
        width += face->glyph->advance.x / 64.0;
    }

    baseline = cy +
        (primary->size->metrics.ascender + primary->size->metrics.descender) /
        128.0;
    pen = cx - width / 2.0;

    for (i = 0; i < count; i++) {
        FT_GlyphSlot slot;
        cairo_surface_t *glyph;
        unsigned char *dst;
        int stride;
        int y;

        if (FT_Load_Glyph(runs[i].face, runs[i].index, FT_LOAD_DEFAULT) != 0)
            continue;
        slot = runs[i].face->glyph;
        if (bold)
            FT_GlyphSlot_Embolden(slot);
        if (FT_Render_Glyph(slot, FT_RENDER_MODE_NORMAL) != 0)
            continue;
        if (slot->bitmap.pixel_mode == FT_PIXEL_MODE_GRAY &&
            slot->bitmap.width && slot->bitmap.rows) {
            glyph = cairo_image_surface_create(CAIRO_FORMAT_A8,
                slot->bitmap.width, slot->bitmap.rows);
            dst = cairo_image_surface_get_data(glyph);
            stride = cairo_image_surface_get_stride(glyph);
            for (y = 0; y < (int)slot->bitmap.rows; y++)
                memcpy(dst + y * stride,
                    slot->bitmap.buffer + y * slot->bitmap.pitch,
                    slot->bitmap.width);
            cairo_surface_mark_dirty(glyph);
            cairo_save(cr);
            cairo_translate(cr, pen + slot->bitmap_left,
                baseline - slot->bitmap_top);
            cairo_set_source_rgb(cr, color[0], color[1], color[2]);
            cairo_mask_surface(cr, glyph, 0, 0);
            cairo_restore(cr);
            cairo_surface_destroy(glyph);
        }
        pen += slot->advance.x / 64.0;
    }
}

static void draw_ui(cairo_t *cr, const struct reading *r)
{
    char percent[32], power[32], values[96];
    double cx = CANVAS_W / 2.0, cy = CANVAS_H * 0.45;
    double radius = CANVAS_H * 0.2;
    double thickness = 26;
    double start = -M_PI / 2;
    double end = start + 2 * M_PI * r->percent / 100.0;

    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_set_source_rgb(cr, 0, 0, 0);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);
    cairo_new_path(cr);

    cairo_set_line_width(cr, thickness);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
    cairo_set_source_rgba(cr, 1, 1, 1, 0.08);
    cairo_arc(cr, cx, cy, radius, 0, 2 * M_PI);
    cairo_stroke(cr);

    cairo_set_source_rgb(cr, ACCENT[0], ACCENT[1], ACCENT[2]);
    cairo_arc(cr, cx, cy, radius, start, end);
    cairo_stroke(cr);

    snprintf(percent, sizeof(percent), "%d%%", r->percent);
    snprintf(power, sizeof(power), "%d W", (int)lround(r->watts));
    if (isnan(r->temp))
        snprintf(values, sizeof(values), "%.1f V %.1f A", r->volts, r->amps);
    else
        snprintf(values, sizeof(values), "%.1f V %.1f A %.1f °C",
            r->volts, r->amps, r->temp);

    draw_text(cr, "充电中", 68, cx, cy - 200, ACCENT, 1, FONT_CJK);
    draw_text(cr, percent, 200, cx, cy + 10, FG, 1, FONT_UI);
    draw_text(cr, power, 72, cx, cy + 190, ACCENT, 1, FONT_UI);
    draw_text(cr, "长按电源键5秒以开机", 30, CANVAS_W / 2.0, 1420, FG, 1,
        FONT_CJK);
    draw_text(cr, values, 28, CANVAS_W / 2.0, 1480, FG, 1, FONT_UI);
    cairo_new_path(cr);
}

static int find_backlight(struct backlight *bl)
{
    DIR *dir = opendir("/sys/class/backlight");
    struct dirent *entry;
    long value;

    bl->brightness[0] = bl->max[0] = '\0';
    if (!dir)
        return -1;
    while ((entry = readdir(dir)) != NULL) {
        char path[320];

        if (entry->d_name[0] == '.')
            continue;
        snprintf(bl->brightness, sizeof(bl->brightness),
            "/sys/class/backlight/%s/brightness", entry->d_name);
        snprintf(bl->max, sizeof(bl->max),
            "/sys/class/backlight/%s/max_brightness", entry->d_name);
        if (read_long(bl->brightness, &value) == 0 &&
            read_long(bl->max, &value) == 0) {
            closedir(dir);
            return 0;
        }
    }
    closedir(dir);
    return -1;
}

static void setup_backlight(struct backlight *bl)
{
    long value = 0;

    if (find_backlight(bl) < 0)
        return;
    read_long(bl->max, &value);
    bl->maximum = value > 0 ? (int)value : 2047;
    if (read_long(bl->brightness, &value) < 0 || value <= 0)
        value = bl->maximum / 2;
    bl->saved = (int)value;
    write_int(bl->brightness, bl->saved);
}

#define MAX_KEY_DEVS 8

struct key_devs {
    int fd[MAX_KEY_DEVS];
    int count;
};

static void find_power_keys(struct key_devs *keys)
{
    DIR *dir = opendir("/sys/class/input");
    struct dirent *entry;

    memset(keys, 0, sizeof(*keys));
    if (!dir)
        return;
    while ((entry = readdir(dir)) != NULL) {
        unsigned char bits[(KEY_MAX + 7) / 8];
        char namepath[320], devpath[320], name[128];
        int fd;

        if (keys->count >= MAX_KEY_DEVS)
            break;
        if (strncmp(entry->d_name, "event", 5) != 0)
            continue;
        snprintf(devpath, sizeof(devpath), "/dev/input/%s",
            entry->d_name);
        fd = open(devpath, O_RDONLY | O_NONBLOCK);
        if (fd < 0)
            continue;
        memset(bits, 0, sizeof(bits));
        if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(bits)), bits) < 0 ||
            !(bits[KEY_POWER / 8] & (1 << (KEY_POWER % 8)))) {
            close(fd);
            continue;
        }
        snprintf(namepath, sizeof(namepath),
            "/sys/class/input/%s/device/name", entry->d_name);
        if (read_text(namepath, name, sizeof(name)) < 0)
            snprintf(name, sizeof(name), "%s", entry->d_name);
        keys->fd[keys->count++] = fd;
        kmsg("gts9wifi-lpcharge: power key %s (%s)", entry->d_name, name);
    }
    closedir(dir);
}

static void panel_blank(struct fbdev *fb, int blank)
{
    int fb_rc;
    int drm_rc;

    fb_rc = ioctl(fb->fd, FBIOBLANK, blank);
    drm_rc = write_text("/sys/class/drm/card0-DSI-1/dpms",
        blank == FB_BLANK_POWERDOWN ? "off" : "on");
    if (fb_rc < 0 && drm_rc < 0)
        kmsg("gts9wifi-lpcharge: panel blank=%d failed", blank);
}

static void quit_plymouth(void)
{
    static const char *paths[] = {
        "/usr/bin/plymouth", "/bin/plymouth", "/usr/sbin/plymouth", NULL
    };
    int i;

    for (i = 0; paths[i]; i++) {
        pid_t pid;

        if (access(paths[i], X_OK) < 0)
            continue;
        pid = fork();
        if (pid == 0) {
            execl(paths[i], "plymouth", "--quit", (char *)NULL);
            _exit(1);
        }
        if (pid > 0) {
            waitpid(pid, NULL, 0);
            break;
        }
    }
}

static int open_fb(struct fbdev *fb)
{
    struct fb_var_screeninfo var;
    struct fb_fix_screeninfo fix;

    memset(fb, 0, sizeof(*fb));
    fb->fd = open("/dev/fb0", O_RDWR);
    if (fb->fd < 0)
        return -1;
    if (ioctl(fb->fd, FBIOGET_VSCREENINFO, &var) < 0 ||
        ioctl(fb->fd, FBIOGET_FSCREENINFO, &fix) < 0 ||
        var.bits_per_pixel != 32 ||
        var.xres != CANVAS_W || var.yres != CANVAS_H) {
        close(fb->fd);
        return -1;
    }
    fb->length = fix.smem_len;
    fb->map = mmap(NULL, fb->length, PROT_READ | PROT_WRITE, MAP_SHARED,
        fb->fd, 0);
    if (fb->map == MAP_FAILED) {
        close(fb->fd);
        return -1;
    }
    fb->width = var.xres;
    fb->height = var.yres;
    fb->stride = fix.line_length;
    fb->surface = cairo_image_surface_create_for_data(fb->map,
        CAIRO_FORMAT_RGB24, fb->width, fb->height, fb->stride);
    fb->cr = cairo_create(fb->surface);
    return 0;
}

static void close_fb(struct fbdev *fb)
{
    if (fb->cr)
        cairo_destroy(fb->cr);
    if (fb->surface)
        cairo_surface_destroy(fb->surface);
    if (fb->map && fb->map != MAP_FAILED)
        munmap(fb->map, fb->length);
    if (fb->fd >= 0)
        close(fb->fd);
    memset(fb, 0, sizeof(*fb));
    fb->fd = -1;
}

static void render_fb(struct fbdev *fb, const struct reading *r)
{
    draw_ui(fb->cr, r);
    cairo_surface_flush(fb->surface);
}

static int preview(const char *path)
{
    cairo_surface_t *surface;
    cairo_t *cr;
    struct reading r = {
        .percent = 58,
        .volts = 9.5,
        .amps = 3.0,
        .watts = 28.0,
        .temp = 25.8,
    };
    cairo_status_t status;

    surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32,
        CANVAS_W, CANVAS_H);
    cr = cairo_create(surface);
    draw_ui(cr, &r);
    status = cairo_surface_write_to_png(surface, path);
    cairo_destroy(cr);
    cairo_surface_destroy(surface);
    return status == CAIRO_STATUS_SUCCESS ? 0 : 1;
}

int main(int argc, char **argv)
{
    struct fbdev fb = {.fd = -1};
    struct backlight bl = {0};
    struct key_devs keys;
    struct reading r;
    int screen_on = 1;
    int pressed = 0;
    int i;
    double press_at = 0;
    double last_activity;
    double last_draw = 0;
    double last_log = 0;

    if (fonts_init() < 0)
        kmsg("gts9wifi-lpcharge: no usable fonts; text will be missing");
    if (argc == 3 && strcmp(argv[1], "--preview") == 0)
        return preview(argv[2]);

    quit_plymouth();
    if (open_fb(&fb) < 0) {
        kmsg("gts9wifi-lpcharge: /dev/fb0 unavailable");
        return 1;
    }
    setup_backlight(&bl);
    find_power_keys(&keys);
    if (keys.count == 0) {
        kmsg("gts9wifi-lpcharge: no power key device; continuing boot");
        close_fb(&fb);
        return 1;
    }

    read_reading(&r);
    kmsg("gts9wifi-lpcharge: fb %dx%d battery=%d%%",
        fb.width, fb.height, r.percent);
    render_fb(&fb, &r);
    last_activity = mono_seconds();
    last_log = last_activity;

    for (;;) {
        struct pollfd fds[MAX_KEY_DEVS];
        double now = mono_seconds();
        int ret;

        for (i = 0; i < keys.count; i++) {
            fds[i].fd = keys.fd[i];
            fds[i].events = POLLIN;
            fds[i].revents = 0;
        }
        ret = poll(fds, keys.count, 50);
        if (ret > 0) {
            for (i = 0; i < keys.count; i++) {
                struct input_event ev;

                if (!(fds[i].revents & POLLIN))
                    continue;
                while (read(keys.fd[i], &ev, sizeof(ev)) == sizeof(ev)) {
                    if (ev.type != EV_KEY || ev.code != KEY_POWER)
                        continue;
                    kmsg("gts9wifi-lpcharge: power key value=%d",
                        ev.value);
                    if (ev.value == 1) {
                        pressed = 1;
                        press_at = now;
                        last_activity = now;
                        if (!screen_on) {
                            screen_on = 1;
                            panel_blank(&fb, FB_BLANK_UNBLANK);
                            write_int(bl.brightness, bl.saved);
                            read_reading(&r);
                            render_fb(&fb, &r);
                            last_draw = now;
                            kmsg("gts9wifi-lpcharge: wake pct=%d v=%.1f a=%.1f w=%.1f",
                                r.percent, r.volts, r.amps, r.watts);
                        }
                    } else if (ev.value == 0) {
                        pressed = 0;
                        last_activity = now;
                    }
                }
            }
        }

        now = mono_seconds();
        if (pressed && now - press_at >= HOLD_SECONDS)
            break;
        if (screen_on && now - last_activity >= BLANK_SECONDS) {
            screen_on = 0;
            write_int(bl.brightness, 0);
            panel_blank(&fb, FB_BLANK_POWERDOWN);
            kmsg("gts9wifi-lpcharge: blank");
        }
        if (screen_on && now - last_draw >= 0.25) {
            read_reading(&r);
            render_fb(&fb, &r);
            last_draw = now;
        }
        if (now - last_log >= 30.0) {
            read_reading(&r);
            kmsg("gts9wifi-lpcharge: data pct=%d v=%.1f a=%.1f w=%.1f t=%.1f",
                r.percent, r.volts, r.amps, r.watts, r.temp);
            last_log = now;
        }
    }

    panel_blank(&fb, FB_BLANK_UNBLANK);
    write_int(bl.brightness, bl.saved);
    kmsg("gts9wifi-lpcharge: boot requested");
    for (i = 0; i < keys.count; i++)
        close(keys.fd[i]);
    close_fb(&fb);
    return 0;
}
