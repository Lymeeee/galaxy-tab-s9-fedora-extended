// SPDX-License-Identifier: MIT
//
// Off-mode charging screen for the Galaxy Tab S9 Fedora port.  This runs
// from the dracut initramfs when ABL passes lpcharge=1: it draws directly on
// /dev/fb0, blanks the backlight after 15 s, wakes on a short power press and
// continues the normal boot after a 5 s hold.
//
// The same binary has a --preview mode so the Cairo/Pango layout and the
// embedded font subsets can be checked in userspace without flashing a bundle.

#define _GNU_SOURCE
#include <cairo/cairo.h>
#include <pango/pangocairo.h>
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
#include <time.h>
#include <math.h>
#include <errno.h>

#define CANVAS_W 2560
#define CANVAS_H 1600
#define FONT_UI "Adwaita Sans"
#define FONT_CJK "Noto Sans CJK SC"
#define HOLD_SECONDS 5.0
#define BLANK_SECONDS 15.0

static const double BG_TOP[3] = {0.055, 0.060, 0.075};
static const double BG_BOTTOM[3] = {0.025, 0.030, 0.040};
static const double FG[3] = {0.94, 0.95, 0.97};
static const double ACCENT[3] = {0.318, 0.635, 0.855};

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

static void draw_text(cairo_t *cr, const char *text, double size,
                      double cx, double cy, const double color[3],
                      int bold, const char *family)
{
    PangoLayout *layout = pango_cairo_create_layout(cr);
    PangoFontDescription *desc = pango_font_description_new();
    int width, height;

    pango_font_description_set_family(desc, family);
    pango_font_description_set_absolute_size(desc, size * PANGO_SCALE);
    pango_font_description_set_weight(desc,
        bold ? PANGO_WEIGHT_BOLD : PANGO_WEIGHT_NORMAL);
    pango_layout_set_font_description(layout, desc);
    pango_layout_set_text(layout, text, -1);
    pango_layout_get_pixel_size(layout, &width, &height);
    cairo_set_source_rgb(cr, color[0], color[1], color[2]);
    cairo_move_to(cr, cx - width / 2.0, cy - height / 2.0);
    pango_cairo_show_layout(cr, layout);
    g_object_unref(layout);
    pango_font_description_free(desc);
}

static void draw_ui(cairo_t *cr, const struct reading *r)
{
    cairo_pattern_t *bg;
    char percent[32], power[32], values[96];
    double cx = CANVAS_W / 2.0, cy = CANVAS_H * 0.45;
    double radius = CANVAS_H * 0.2;
    double thickness = 26;
    double start = -M_PI / 2;
    double end = start + 2 * M_PI * r->percent / 100.0;

    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_set_source_rgb(cr, BG_TOP[0], BG_TOP[1], BG_TOP[2]);
    cairo_paint(cr);
    bg = cairo_pattern_create_linear(0, 0, 0, CANVAS_H);
    cairo_pattern_add_color_stop_rgb(bg, 0, BG_TOP[0], BG_TOP[1], BG_TOP[2]);
    cairo_pattern_add_color_stop_rgb(bg, 1, BG_BOTTOM[0], BG_BOTTOM[1],
        BG_BOTTOM[2]);
    cairo_set_source(cr, bg);
    cairo_paint(cr);
    cairo_pattern_destroy(bg);
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

static int find_power_key(void)
{
    DIR *dir = opendir("/sys/class/input");
    struct dirent *entry;
    int fd = -1;

    if (dir) {
        while ((entry = readdir(dir)) != NULL) {
            char namepath[320], devpath[320], name[128];

            if (strncmp(entry->d_name, "event", 5) != 0)
                continue;
            snprintf(namepath, sizeof(namepath),
                "/sys/class/input/%s/device/name", entry->d_name);
            if (read_text(namepath, name, sizeof(name)) < 0)
                continue;
            if (!strstr(name, "pmic_pwrkey") && !strstr(name, "pwrkey"))
                continue;
            snprintf(devpath, sizeof(devpath), "/dev/input/%s",
                entry->d_name);
            fd = open(devpath, O_RDONLY | O_NONBLOCK);
            if (fd >= 0)
                break;
        }
        closedir(dir);
    }
    if (fd < 0)
        fd = open("/dev/input/event0", O_RDONLY | O_NONBLOCK);
    return fd;
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

static void set_fonts(void)
{
    const char *conf = getenv("LPCHARGE_FONTS_CONF");
    const char *default_conf = "/usr/share/gts9wifi/fonts.conf";

    if (!conf)
        conf = default_conf;
    if (access(conf, R_OK) == 0)
        setenv("FONTCONFIG_FILE", conf, 1);
}

int main(int argc, char **argv)
{
    struct fbdev fb = {.fd = -1};
    struct backlight bl = {0};
    struct reading r;
    int key_fd;
    int screen_on = 1;
    int pressed = 0;
    double press_at = 0;
    double last_activity;
    double last_draw = 0;

    set_fonts();
    if (argc == 3 && strcmp(argv[1], "--preview") == 0)
        return preview(argv[2]);

    quit_plymouth();
    if (open_fb(&fb) < 0)
        return 1;
    setup_backlight(&bl);
    key_fd = find_power_key();
    if (key_fd < 0) {
        close_fb(&fb);
        return 1;
    }

    read_reading(&r);
    render_fb(&fb, &r);
    last_activity = mono_seconds();

    for (;;) {
        struct pollfd pfd = {.fd = key_fd, .events = POLLIN};
        double now = mono_seconds();
        int ret = poll(&pfd, 1, 100);

        if (ret > 0 && (pfd.revents & POLLIN)) {
            struct input_event ev;

            while (read(key_fd, &ev, sizeof(ev)) == sizeof(ev)) {
                if (ev.type != EV_KEY || ev.code != KEY_POWER)
                    continue;
                if (ev.value == 1) {
                    pressed = 1;
                    press_at = now;
                    last_activity = now;
                    if (!screen_on) {
                        screen_on = 1;
                        write_int(bl.brightness, bl.saved);
                        read_reading(&r);
                        render_fb(&fb, &r);
                        last_draw = now;
                    }
                } else if (ev.value == 0) {
                    pressed = 0;
                    last_activity = now;
                }
            }
        }

        now = mono_seconds();
        if (pressed && now - press_at >= HOLD_SECONDS)
            break;
        if (screen_on && now - last_activity >= BLANK_SECONDS) {
            screen_on = 0;
            write_int(bl.brightness, 0);
        }
        if (screen_on && now - last_draw >= 1.0) {
            read_reading(&r);
            render_fb(&fb, &r);
            last_draw = now;
        }
    }

    write_int(bl.brightness, bl.saved);
    close(key_fd);
    close_fb(&fb);
    return 0;
}
