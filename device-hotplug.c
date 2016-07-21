/*
 * QEMU device hotplug helpers
 *
 * Copyright (c) 2004 Fabrice Bellard
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include "hw/hw.h"
#include "hw/boards.h"
#include "sysemu/blockdev.h"
#include "qemu/config-file.h"
#include "sysemu/sysemu.h"
#include "monitor/monitor.h"

DriveInfo *add_init_drive(const char *optstr)
{
    DriveInfo *dinfo;
    QemuOpts *opts;

    opts = drive_def(optstr);
    if (!opts)
        return NULL;

    dinfo = drive_init(opts, current_machine->block_default_type);
    if (!dinfo) {
        qemu_opts_del(opts);
        return NULL;
    }

    return dinfo;
}

void drive_hot_add(Monitor *mon, const QDict *qdict)
{
    DriveInfo *dinfo = NULL;
    const char *opts = qdict_get_str(qdict, "opts");

    dinfo = add_init_drive(opts);
    if (!dinfo) {
        goto err;
    }
    if (dinfo->devaddr) {
        monitor_printf(mon, "Parameter addr not supported\n");
        goto err;
    }

    switch (dinfo->type) {
    case IF_NONE:
        monitor_printf(mon, "OK\n");
        break;
    default:
        if (pci_drive_hot_add(mon, qdict, dinfo)) {
            goto err;
        }
    }
    return;

err:
    if (dinfo) {
        drive_put_ref(dinfo);
    }
}

static void check_parm(const char *key, QObject *obj, void *opaque)
{
    static const char *unwanted_keys[] = {
        "bus", "unit", "index", "if", "boot", "addr",
        NULL

    };
    int *stopped = opaque;
    const char **p;

    if (*stopped) {
        return;
    }

    for (p = unwanted_keys; *p; p++) {
        if (!strcmp(key, *p)) {
            qerror_report(QERR_INVALID_PARAMETER, key);
            *stopped = 1;
            return;
        }
    }

}

int simple_drive_add(Monitor *mon, const QDict *qdict, QObject **ret_data)
{
    int stopped;
    Error *local_err = NULL;
    QemuOpts *opts;
    DriveInfo *dinfo;

    if (!qdict_haskey(qdict, "id")) {
        qerror_report(QERR_MISSING_PARAMETER, "id");
        return -1;
    }

    stopped = 0;
    qdict_iter(qdict, check_parm, &stopped);
    if (stopped) {
        return -1;
    }

    opts = qemu_opts_from_qdict(&qemu_drive_opts, qdict, &local_err);
    if (!opts) {
        qerror_report_err(local_err);
        error_free(local_err);
        return -1;
    }
    qemu_opt_set(opts, "if", "none");
    dinfo = drive_init(opts, current_machine->block_default_type);
    if (!dinfo) {
        /*
         * drive_init() reports some errors with qerror_report_err(),
         * and some with error_report().  The latter vanish without
         * trace in monitor_vprintf().  See also the rather optimistic
         * upstream commit 74ee59a.  Emit a generic error here.  If a
         * prior error from qerror_report_err() is pending, it'll get
         * ignored.
         */
        qerror_report(QERR_DEVICE_INIT_FAILED,
                      qemu_opts_id(opts));
        qemu_opts_del(opts);
        return -1;
    }

    return 0;
}
