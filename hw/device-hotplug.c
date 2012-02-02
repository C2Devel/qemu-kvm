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

#include "hw.h"
#include "boards.h"
#include "qerror.h"
#include "net.h"
#include "block_int.h"
#include "sysemu.h"

DriveInfo *add_init_drive(const char *optstr)
{
    int fatal_error;
    DriveInfo *dinfo;
    QemuOpts *opts;

    opts = drive_add(NULL, "%s", optstr);
    if (!opts)
        return NULL;

    dinfo = drive_init(opts, current_machine, &fatal_error);
    if (!dinfo) {
        qemu_opts_del(opts);
        return NULL;
    }

    return dinfo;
}

static void check_parm(const char *key, QObject *obj, void *opaque)
{
    static const char *valid_keys[] = {
        "id", "cyls", "heads", "secs", "trans", "media", "snapshot",
        "file", "cache", "aio", "format", "serial", "rerror", "werror",
        "readonly", NULL
    };
    int *stopped = opaque;
    const char **p;

    if (*stopped) {
        return;
    }

    for (p = valid_keys; *p; p++) {
        if (!strcmp(key, *p)) {
            return;
        }
    }
    
    qerror_report(QERR_INVALID_PARAMETER, key);
    *stopped = 1;
}

int simple_drive_add(Monitor *mon, const QDict *qdict, QObject **ret_data)
{
    int stopped, fatal_error;
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

    opts = qemu_opts_from_qdict(&qemu_drive_opts, qdict);
    if (!opts) {
        return -1;
    }
    qemu_opt_set(opts, "if", "none");
    dinfo = drive_init(opts, current_machine, &fatal_error);
    if (!dinfo && fatal_error) {
        qerror_report(QERR_DEVICE_INIT_FAILED, /* close enough */
                      qemu_opts_id(opts));
        /* drive_init() can leave an empty drive behind, reap it */
        dinfo = drive_get_by_id(qemu_opts_id(opts));
        if (dinfo) {
            drive_uninit(dinfo);
        } else {
            qemu_opts_del(opts);
        }
        return -1;
    }

    return 0;
}

int do_drive_del(Monitor *mon, const QDict *qdict, QObject **ret_data)
{
    const char *id = qdict_get_str(qdict, "id");
    BlockDriverState *bs;

    bs = bdrv_find(id);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, id);
        return -1;
    }

    /* quiesce block driver; prevent further io */
    qemu_aio_flush();
    bdrv_flush(bs);
    bdrv_close(bs);

    /* if we have a device associated with this BlockDriverState (bs->peer)
     * then we need to make the drive anonymous until the device
     * can be removed.  If this is a drive with no device backing
     * then we can just get rid of the block driver state right here.
     */
    if (bs->peer) {
        bdrv_make_anon(bs);
    } else {
        drive_uninit(drive_get_by_blockdev(bs));
    }

    return 0;
}
