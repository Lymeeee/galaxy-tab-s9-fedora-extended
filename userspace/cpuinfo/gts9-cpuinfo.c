// SPDX-License-Identifier: MIT
//
// GNOME Settings fills its "Processor" row from libgtop, which only reads
// /proc/cpuinfo.  arm64 cpuinfo has no model-name line, so the row is empty.
// Interpose glibtop_get_sysinfo() to add the model the device profile knows.

#define _GNU_SOURCE

#include <dlfcn.h>
#include <glib.h>
#include <glibtop/sysinfo.h>

typedef const glibtop_sysinfo *(*SysinfoFunc)(void);

const glibtop_sysinfo *
glibtop_get_sysinfo(void)
{
    static SysinfoFunc real_sysinfo;
    const char *model = g_getenv("GTS9_CPU_MODEL");
    const glibtop_sysinfo *info;

    if (real_sysinfo == NULL)
        real_sysinfo = (SysinfoFunc)dlsym(RTLD_NEXT, "glibtop_get_sysinfo");
    if (real_sysinfo == NULL)
        return NULL;

    info = real_sysinfo();
    if (info == NULL || model == NULL || *model == '\0')
        return info;

    for (guint64 i = 0; i < info->ncpu; i++) {
        glibtop_entry *entry = (glibtop_entry *)&info->cpuinfo[i];

        if (g_hash_table_contains(entry->values, "model name") ||
            g_hash_table_contains(entry->values, "cpu") ||
            g_hash_table_contains(entry->values, "Processor") ||
            g_hash_table_contains(entry->values, "Model Name"))
            continue;

        g_hash_table_insert(entry->values, g_strdup("model name"),
                            g_strdup(model));
        g_ptr_array_add(entry->labels, g_strdup("model name"));
    }

    return info;
}
