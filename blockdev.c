/*
 * QEMU host block devices
 *
 * Copyright (c) 2003-2008 Fabrice Bellard
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or
 * later.  See the COPYING file in the top-level directory.
 */

#include "block.h"
#include "blockdev.h"
#include "monitor.h"
#include "qerror.h"
#include "qemu-option.h"
#include "qemu-config.h"
#include "sysemu.h"
#include "block_int.h"
#include "qjson.h"

struct drivelist drives = QTAILQ_HEAD_INITIALIZER(drives);
DriveInfo *extboot_drive = NULL;

static const char *const if_name[IF_COUNT] = {
    [IF_NONE] = "none",
    [IF_IDE] = "ide",
    [IF_SCSI] = "scsi",
    [IF_FLOPPY] = "floppy",
    [IF_PFLASH] = "pflash",
    [IF_MTD] = "mtd",
    [IF_SD] = "sd",
    [IF_VIRTIO] = "virtio",
    [IF_XEN] = "xen",
};

static const int if_max_devs[IF_COUNT] = {
    /*
     * Do not change these numbers!  They govern how drive option
     * index maps to unit and bus.  That mapping is ABI.
     *
     * All controllers used to imlement if=T drives need to support
     * if_max_devs[T] units, for any T with if_max_devs[T] != 0.
     * Otherwise, some index values map to "impossible" bus, unit
     * values.
     *
     * For instance, if you change [IF_SCSI] to 255, -drive
     * if=scsi,index=12 no longer means bus=1,unit=5, but
     * bus=0,unit=12.  With an lsi53c895a controller (7 units max),
     * the drive can't be set up.  Regression.
     */
    [IF_IDE] = 2,
    [IF_SCSI] = 7,
};

enum {
    SLICE_TIME_MS = 100,  /* 100 ms rate-limiting slice time */
};

typedef struct StreamState {
    MonitorCompletion *cancel_cb;
    void *cancel_opaque;
    int64_t offset;             /* current position in block device */
    BlockDriverState *bs;
    QEMUTimer *timer;
    int64_t bytes_per_sec;      /* rate limit */
    int64_t bytes_per_slice;    /* rate limit scaled to slice */
    int64_t slice_end_time;     /* when this slice finishes */
    int64_t slice_start_offset; /* offset when slice started */
    QLIST_ENTRY(StreamState) list;
} StreamState;

static QLIST_HEAD(, StreamState) block_streams =
    QLIST_HEAD_INITIALIZER(block_streams);

static QObject *stream_get_qobject(StreamState *s)
{
    const char *name = bdrv_get_device_name(s->bs);
    int64_t len = bdrv_getlength(s->bs);

    return qobject_from_jsonf("{ 'device': %s, 'type': 'stream', "
                              "'offset': %" PRId64 ", 'len': %" PRId64 ", "
                              "'speed': %" PRId64 " }",
                              name, s->offset, len, s->bytes_per_sec);
}

static void stream_mon_event(StreamState *s, int ret)
{
    QObject *data = stream_get_qobject(s);

    if (ret < 0) {
        QDict *qdict = qobject_to_qdict(data);

        qdict_put(qdict, "error", qstring_from_str(strerror(-ret)));
    }

    monitor_protocol_event(QEVENT_BLOCK_JOB_COMPLETED, data);
    qobject_decref(data);
}

static void stream_free(StreamState *s)
{
    QLIST_REMOVE(s, list);

    if (s->cancel_cb) {
        s->cancel_cb(s->cancel_opaque, NULL);
    }

    bdrv_set_in_use(s->bs, 0);
    qemu_del_timer(s->timer);
    qemu_free_timer(s->timer);
    qemu_free(s);
}

static void stream_complete(StreamState *s, int ret)
{
    stream_mon_event(s, ret);
    stream_free(s);
}

static void stream_schedule_next_iteration(StreamState *s)
{
    int64_t next = qemu_get_clock(rt_clock);

    /* New slice */
    if (next >= s->slice_end_time) {
        s->slice_end_time = next + SLICE_TIME_MS;
        s->slice_start_offset = s->offset;
    }

    /* Throttle */
    if (s->bytes_per_slice &&
        s->offset - s->slice_start_offset >= s->bytes_per_slice) {
        next = s->slice_end_time;
        s->slice_end_time = next + SLICE_TIME_MS;
        s->slice_start_offset += s->bytes_per_slice;
    }

    qemu_mod_timer(s->timer, next);
}

static void stream_cb(void *opaque, int nb_sectors)
{
    StreamState *s = opaque;

    if (nb_sectors < 0) {
        stream_complete(s, nb_sectors);
        return;
    }

    s->offset += nb_sectors * BDRV_SECTOR_SIZE;

    if (s->offset == bdrv_getlength(s->bs)) {
        bdrv_change_backing_file(s->bs, NULL, NULL);
        stream_complete(s, 0);
    } else if (s->cancel_cb) {
        stream_free(s);
    } else {
        stream_schedule_next_iteration(s);
    }
}

/* We can't call bdrv_aio_stream() directly from the callback because that
 * makes qemu_aio_flush() not complete until the streaming is completed.
 * By delaying with a timer, we give qemu_aio_flush() a chance to complete.
 */
static void stream_next_iteration(void *opaque)
{
    StreamState *s = opaque;

    bdrv_aio_copy_backing(s->bs, s->offset / BDRV_SECTOR_SIZE, stream_cb, s);
}

static StreamState *stream_find(const char *device)
{
    StreamState *s;

    QLIST_FOREACH(s, &block_streams, list) {
        if (strcmp(bdrv_get_device_name(s->bs), device) == 0) {
            return s;
        }
    }
    return NULL;
}

static StreamState *stream_start(const char *device)
{
    StreamState *s;
    BlockDriverAIOCB *acb;
    BlockDriverState *bs;

    s = stream_find(device);
    if (s) {
        qerror_report(QERR_DEVICE_IN_USE, device);
        return NULL;
    }

    bs = bdrv_find(device);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, device);
        return NULL;
    }
    if (bdrv_in_use(bs)) {
        qerror_report(QERR_DEVICE_IN_USE, device);
        return NULL;
    }
    bdrv_set_in_use(bs, 1);

    s = qemu_mallocz(sizeof(*s));
    s->bs = bs;
    s->timer = qemu_new_timer(rt_clock, stream_next_iteration, s);
    QLIST_INSERT_HEAD(&block_streams, s, list);

    acb = bdrv_aio_copy_backing(s->bs, s->offset / BDRV_SECTOR_SIZE,
                                stream_cb, s);
    if (acb == NULL) {
        stream_free(s);
        qerror_report(QERR_NOT_SUPPORTED);
        return NULL;
    }
    return s;
}

static int stream_stop(const char *device, MonitorCompletion *cb, void *opaque)
{
    StreamState *s = stream_find(device);

    if (!s) {
        qerror_report(QERR_DEVICE_NOT_ACTIVE, device);
        return -1;
    }
    if (s->cancel_cb) {
        qerror_report(QERR_DEVICE_IN_USE, device);
        return -1;
    }

    s->cancel_cb = cb;
    s->cancel_opaque = opaque;
    return 0;
}

static int stream_set_speed(const char *device, int64_t bytes_per_sec)
{
    StreamState *s = stream_find(device);

    if (!s) {
        qerror_report(QERR_DEVICE_NOT_ACTIVE, device);
        return -1;
    }

    s->bytes_per_sec = bytes_per_sec;
    s->bytes_per_slice = bytes_per_sec * SLICE_TIME_MS / 1000LL;
    return 0;
}

/*
 * We automatically delete the drive when a device using it gets
 * unplugged.  Questionable feature, but we can't just drop it.
 * Device models call blockdev_mark_auto_del() to schedule the
 * automatic deletion, and generic qdev code calls blockdev_auto_del()
 * when deletion is actually safe.
 */
void blockdev_mark_auto_del(BlockDriverState *bs)
{
    DriveInfo *dinfo = drive_get_by_blockdev(bs);

    if (dinfo) {
        dinfo->auto_del = 1;
    }
}

void blockdev_auto_del(BlockDriverState *bs)
{
    DriveInfo *dinfo = drive_get_by_blockdev(bs);

    if (dinfo && dinfo->auto_del) {
        drive_uninit(dinfo);
    }
}

static int drive_index_to_bus_id(BlockInterfaceType type, int index)
{
    int max_devs = if_max_devs[type];
    return max_devs ? index / max_devs : 0;
}

static int drive_index_to_unit_id(BlockInterfaceType type, int index)
{
    int max_devs = if_max_devs[type];
    return max_devs ? index % max_devs : index;
}

QemuOpts *drive_def(const char *optstr)
{
    return qemu_opts_parse(&qemu_drive_opts, optstr, 0);
}

QemuOpts *drive_add(BlockInterfaceType type, int index, const char *file,
                    const char *optstr)
{
    QemuOpts *opts;
    char buf[32];

    opts = drive_def(optstr);
    if (!opts) {
        return NULL;
    }
    if (type != IF_DEFAULT) {
        qemu_opt_set(opts, "if", if_name[type]);
    }
    if (index >= 0) {
        snprintf(buf, sizeof(buf), "%d", index);
        qemu_opt_set(opts, "index", buf);
    }
    if (file)
        qemu_opt_set(opts, "file", file);
    return opts;
}

DriveInfo *drive_get(BlockInterfaceType type, int bus, int unit)
{
    DriveInfo *dinfo;

    /* seek interface, bus and unit */

    QTAILQ_FOREACH(dinfo, &drives, next) {
        if (dinfo->type == type &&
	    dinfo->bus == bus &&
	    dinfo->unit == unit)
            return dinfo;
    }

    return NULL;
}

DriveInfo *drive_get_by_id(const char *id)
{
    DriveInfo *dinfo;

    QTAILQ_FOREACH(dinfo, &drives, next) {
        if (strcmp(id, dinfo->id))
            continue;
        return dinfo;
    }
    return NULL;
}

DriveInfo *drive_get_by_index(BlockInterfaceType type, int index)
{
    return drive_get(type,
                     drive_index_to_bus_id(type, index),
                     drive_index_to_unit_id(type, index));
}

int drive_get_max_bus(BlockInterfaceType type)
{
    int max_bus;
    DriveInfo *dinfo;

    max_bus = -1;
    QTAILQ_FOREACH(dinfo, &drives, next) {
        if(dinfo->type == type &&
           dinfo->bus > max_bus)
            max_bus = dinfo->bus;
    }
    return max_bus;
}

DriveInfo *drive_get_by_blockdev(BlockDriverState *bs)
{
    DriveInfo *dinfo;

    QTAILQ_FOREACH(dinfo, &drives, next) {
        if (dinfo->bdrv == bs) {
            return dinfo;
        }
    }
    return NULL;
}

const char *drive_get_serial(BlockDriverState *bdrv)
{
    DriveInfo *dinfo;

    QTAILQ_FOREACH(dinfo, &drives, next) {
        if (dinfo->bdrv == bdrv)
            return dinfo->serial;
    }

    return "\0";
}

static void bdrv_format_print(void *opaque, const char *name)
{
    error_printf(" %s", name);
}

void drive_uninit(DriveInfo *dinfo)
{
    qemu_opts_del(dinfo->opts);
    bdrv_delete(dinfo->bdrv);
    qemu_free(dinfo->id);
    QTAILQ_REMOVE(&drives, dinfo, next);
    qemu_free(dinfo->file);
    qemu_free(dinfo);
}

static int parse_block_error_action(const char *buf, int is_read)
{
    if (!strcmp(buf, "ignore")) {
        return BLOCK_ERR_IGNORE;
    } else if (!is_read && !strcmp(buf, "enospc")) {
        return BLOCK_ERR_STOP_ENOSPC;
    } else if (!strcmp(buf, "stop")) {
        return BLOCK_ERR_STOP_ANY;
    } else if (!strcmp(buf, "report")) {
        return BLOCK_ERR_REPORT;
    } else {
        error_report("'%s' invalid %s error action",
                     buf, is_read ? "read" : "write");
        return -1;
    }
}

static int drive_open(DriveInfo *dinfo)
{
    int res;
    int bdrv_flags = dinfo->bdrv_flags;

    if (runstate_check(RUN_STATE_INMIGRATE)) {
        bdrv_flags |= BDRV_O_INCOMING;
    }

    res = bdrv_open(dinfo->bdrv, dinfo->file, bdrv_flags, dinfo->drv);

    if (res < 0) {
        error_report("could not open disk image %s: %s",
                     dinfo->file, strerror(-res));
    }
    return res;
}

int drives_reopen(void)
{
    DriveInfo *dinfo;

    QTAILQ_FOREACH(dinfo, &drives, next) {
        if (dinfo->opened && !bdrv_is_read_only(dinfo->bdrv)) {
            int res;
            bdrv_close(dinfo->bdrv);
            res = drive_open(dinfo);
            if (res) {
		    fprintf(stderr, "qemu: re-open of %s failed wth error %d\n",
			    dinfo->file, res);
		    return res;
	    }
        }
    }
    return 0;
}

DriveInfo *drive_init(QemuOpts *opts, int default_to_scsi)
{
    const char *buf;
    const char *file = NULL;
    char devname[128];
    const char *serial;
    const char *mediastr = "";
    BlockInterfaceType type;
    enum { MEDIA_DISK, MEDIA_CDROM } media;
    int bus_id, unit_id;
    int cyls, heads, secs, translation;
    BlockDriver *drv = NULL;
    int max_devs;
    int index;
    int ro = 0;
    int bdrv_flags = 0;
    int on_read_error, on_write_error;
    const char *devaddr;
    DriveInfo *dinfo;
    int is_extboot = 0;
    int snapshot = 0;
    int copy_on_read, stream;

    translation = BIOS_ATA_TRANSLATION_AUTO;

    if (default_to_scsi) {
        type = IF_SCSI;
        pstrcpy(devname, sizeof(devname), "scsi");
    } else {
        type = IF_IDE;
        pstrcpy(devname, sizeof(devname), "ide");
    }
    media = MEDIA_DISK;

    /* extract parameters */
    bus_id  = qemu_opt_get_number(opts, "bus", 0);
    unit_id = qemu_opt_get_number(opts, "unit", -1);
    index   = qemu_opt_get_number(opts, "index", -1);

    cyls  = qemu_opt_get_number(opts, "cyls", 0);
    heads = qemu_opt_get_number(opts, "heads", 0);
    secs  = qemu_opt_get_number(opts, "secs", 0);

    snapshot = qemu_opt_get_bool(opts, "snapshot", 0);
    ro = qemu_opt_get_bool(opts, "readonly", 0);
    copy_on_read = qemu_opt_get_bool(opts, "copy-on-read", 0);
    stream = qemu_opt_get_bool(opts, "stream", 0);

    file = qemu_opt_get(opts, "file");
    serial = qemu_opt_get(opts, "serial");

    if ((buf = qemu_opt_get(opts, "if")) != NULL) {
        pstrcpy(devname, sizeof(devname), buf);
        for (type = 0; type < IF_COUNT && strcmp(buf, if_name[type]); type++)
            ;
        if (type == IF_COUNT) {
            error_report("unsupported bus type '%s'", buf);
            return NULL;
	}
    }
    max_devs = if_max_devs[type];

    if (cyls || heads || secs) {
        if (cyls < 1 || (type == IF_IDE && cyls > 16383)) {
            error_report("invalid physical cyls number");
	    return NULL;
	}
        if (heads < 1 || (type == IF_IDE && heads > 16)) {
            error_report("invalid physical heads number");
	    return NULL;
	}
        if (secs < 1 || (type == IF_IDE && secs > 63)) {
            error_report("invalid physical secs number");
	    return NULL;
	}
    }

    if ((buf = qemu_opt_get(opts, "trans")) != NULL) {
        if (!cyls) {
            error_report("'%s' trans must be used with cyls,heads and secs",
                         buf);
            return NULL;
        }
        if (!strcmp(buf, "none"))
            translation = BIOS_ATA_TRANSLATION_NONE;
        else if (!strcmp(buf, "lba"))
            translation = BIOS_ATA_TRANSLATION_LBA;
        else if (!strcmp(buf, "auto"))
            translation = BIOS_ATA_TRANSLATION_AUTO;
	else {
            error_report("'%s' invalid translation type", buf);
	    return NULL;
	}
    }

    if ((buf = qemu_opt_get(opts, "media")) != NULL) {
        if (!strcmp(buf, "disk")) {
	    media = MEDIA_DISK;
	} else if (!strcmp(buf, "cdrom")) {
            if (cyls || secs || heads) {
                error_report("'%s' invalid physical CHS format", buf);
	        return NULL;
            }
	    media = MEDIA_CDROM;
	} else {
	    error_report("'%s' invalid media", buf);
	    return NULL;
	}
    }

    if ((buf = qemu_opt_get(opts, "cache")) != NULL) {
        if (!strcmp(buf, "off") || !strcmp(buf, "none")) {
            bdrv_flags |= BDRV_O_NOCACHE;
        } else if (!strcmp(buf, "writeback")) {
            bdrv_flags |= BDRV_O_CACHE_WB;
        } else if (!strcmp(buf, "unsafe")) {
            bdrv_flags |= BDRV_O_CACHE_WB;
            bdrv_flags |= BDRV_O_NO_FLUSH;
        } else if (!strcmp(buf, "writethrough")) {
            /* this is the default */
        } else {
           error_report("invalid cache option");
           return NULL;
        }
    }

#ifdef CONFIG_LINUX_AIO
    if ((buf = qemu_opt_get(opts, "aio")) != NULL) {
        if (!strcmp(buf, "native")) {
            bdrv_flags |= BDRV_O_NATIVE_AIO;
        } else if (!strcmp(buf, "threads")) {
            /* this is the default */
        } else {
           error_report("invalid aio option");
           return NULL;
        }
    }
#endif

    if ((buf = qemu_opt_get(opts, "format")) != NULL) {
       if (strcmp(buf, "?") == 0) {
           error_printf("Supported formats:");
           bdrv_iterate_format(bdrv_format_print, NULL);
           error_printf("\n");
           return NULL;
        }
        drv = bdrv_find_whitelisted_format(buf);
        if (!drv) {
            error_report("'%s' invalid format", buf);
            return NULL;
        }
    }

    is_extboot = qemu_opt_get_bool(opts, "boot", 0);
    if (is_extboot && extboot_drive) {
        error_report("two bootable drives specified");
        return NULL;
    }

    on_write_error = BLOCK_ERR_STOP_ENOSPC;
    if ((buf = qemu_opt_get(opts, "werror")) != NULL) {
        if (type != IF_IDE && type != IF_SCSI && type != IF_VIRTIO && type != IF_NONE) {
            error_report("werror is not supported by this bus type");
            return NULL;
        }

        on_write_error = parse_block_error_action(buf, 0);
        if (on_write_error < 0) {
            return NULL;
        }
    }

    on_read_error = BLOCK_ERR_REPORT;
    if ((buf = qemu_opt_get(opts, "rerror")) != NULL) {
        if (type != IF_IDE && type != IF_VIRTIO && type != IF_NONE) {
            error_report("rerror is not supported by this bus type");
            return NULL;
        }

        on_read_error = parse_block_error_action(buf, 1);
        if (on_read_error < 0) {
            return NULL;
        }
    }

    if ((devaddr = qemu_opt_get(opts, "addr")) != NULL) {
        if (type != IF_VIRTIO) {
            error_report("addr is not supported by this bus type");
            return NULL;
        }
    }

    /* compute bus and unit according index */

    if (index != -1) {
        if (bus_id != 0 || unit_id != -1) {
            error_report("index cannot be used with bus and unit");
            return NULL;
        }
        bus_id = drive_index_to_bus_id(type, index);
        unit_id = drive_index_to_unit_id(type, index);
    }

    /* if user doesn't specify a unit_id,
     * try to find the first free
     */

    if (unit_id == -1) {
       unit_id = 0;
       while (drive_get(type, bus_id, unit_id) != NULL) {
           unit_id++;
           if (max_devs && unit_id >= max_devs) {
               unit_id -= max_devs;
               bus_id++;
           }
       }
    }

    /* check unit id */

    if (max_devs && unit_id >= max_devs) {
        error_report("unit %d too big (max is %d)",
                     unit_id, max_devs - 1);
        return NULL;
    }

    /*
     * catch multiple definitions
     */

    if (drive_get(type, bus_id, unit_id) != NULL) {
        error_report("drive with bus=%d, unit=%d (index=%d) exists",
                     bus_id, unit_id, index);
        return NULL;
    }

    /* init */

    dinfo = qemu_mallocz(sizeof(*dinfo));
    if ((buf = qemu_opts_id(opts)) != NULL) {
        dinfo->id = qemu_strdup(buf);
    } else {
        /* no id supplied -> create one */
        dinfo->id = qemu_mallocz(32);
        if (type == IF_IDE || type == IF_SCSI)
            mediastr = (media == MEDIA_CDROM) ? "-cd" : "-hd";
        if (max_devs)
            snprintf(dinfo->id, 32, "%s%i%s%i",
                     devname, bus_id, mediastr, unit_id);
        else
            snprintf(dinfo->id, 32, "%s%s%i",
                     devname, mediastr, unit_id);
    }
    dinfo->bdrv = bdrv_new(dinfo->id);
    dinfo->devaddr = devaddr;
    dinfo->type = type;
    dinfo->bus = bus_id;
    dinfo->unit = unit_id;
    dinfo->opts = opts;
    if (serial)
        strncpy(dinfo->serial, serial, sizeof(dinfo->serial) - 1);
    QTAILQ_INSERT_TAIL(&drives, dinfo, next);
    if (is_extboot) {
        extboot_drive = dinfo;
    }

    bdrv_set_on_error(dinfo->bdrv, on_read_error, on_write_error);

    switch(type) {
    case IF_IDE:
    case IF_SCSI:
    case IF_XEN:
    case IF_NONE:
        switch(media) {
	case MEDIA_DISK:
            if (cyls != 0) {
                bdrv_set_geometry_hint(dinfo->bdrv, cyls, heads, secs);
                bdrv_set_translation_hint(dinfo->bdrv, translation);
            }
	    break;
	case MEDIA_CDROM:
            bdrv_set_type_hint(dinfo->bdrv, BDRV_TYPE_CDROM);
	    break;
	}
        break;
    case IF_SD:
        /* FIXME: This isn't really a floppy, but it's a reasonable
           approximation.  */
    case IF_FLOPPY:
        bdrv_set_type_hint(dinfo->bdrv, BDRV_TYPE_FLOPPY);
        break;
    case IF_PFLASH:
    case IF_MTD:
        break;
    case IF_VIRTIO:
        /* add virtio block device */
        opts = qemu_opts_create(&qemu_device_opts, NULL, 0);
        qemu_opt_set(opts, "driver", "virtio-blk-pci");
        qemu_opt_set(opts, "drive", dinfo->id);
        if (devaddr)
            qemu_opt_set(opts, "addr", devaddr);
        break;
    default:
        abort();
    }
    if (!file || !*file) {
        return dinfo;
    }
    if (snapshot) {
        /* always use write-back with snapshot */
        bdrv_flags &= ~BDRV_O_CACHE_MASK;
        bdrv_flags |= (BDRV_O_SNAPSHOT|BDRV_O_CACHE_WB);
    }

    if (copy_on_read) {
        bdrv_flags |= BDRV_O_COPY_ON_READ;
    }

    if (media == MEDIA_CDROM) {
        /* mark CDROM as read-only. CDROM is fine for any interface, don't check */
        ro = 1;
    } else if (ro == 1) {
        if (type != IF_SCSI && type != IF_VIRTIO && type != IF_FLOPPY && type != IF_NONE) {
            error_report("readonly not supported by this bus type");
            goto err;
        }
    }
    bdrv_flags |= ro ? 0 : BDRV_O_RDWR;

    dinfo->file = qemu_strdup(file);
    dinfo->bdrv_flags = bdrv_flags;
    dinfo->drv = drv;
    dinfo->opened = 1;

    if (drive_open(dinfo) < 0) {
        goto err;
    }

    if (stream) {
        const char *device_name = bdrv_get_device_name(dinfo->bdrv);

        if (!stream_start(device_name)) {
            fprintf(stderr, "qemu: warning: stream_start failed for '%s'\n",
                    device_name);
        }
    }

    if (bdrv_key_required(dinfo->bdrv))
        autostart = 0;
    return dinfo;

err:
    bdrv_delete(dinfo->bdrv);
    qemu_free(dinfo->id);
    QTAILQ_REMOVE(&drives, dinfo, next);
    qemu_free(dinfo->file);
    qemu_free(dinfo);
    return NULL;
}

void do_commit(Monitor *mon, const QDict *qdict)
{
    int all_devices;
    DriveInfo *dinfo;
    const char *device = qdict_get_str(qdict, "device");

    all_devices = !strcmp(device, "all");
    QTAILQ_FOREACH(dinfo, &drives, next) {
        if (!all_devices)
            if (strcmp(bdrv_get_device_name(dinfo->bdrv), device))
                continue;
        bdrv_commit(dinfo->bdrv);
    }
}

static void monitor_print_block_stream(Monitor *mon, const QObject *data)
{
    QDict *stream;

    assert(data);
    stream = qobject_to_qdict(data);

    monitor_printf(mon, "Streaming device %s: Completed %" PRId64 " of %"
                   PRId64 " bytes, speed limit %" PRId64 " bytes/s\n",
                   qdict_get_str(stream, "device"),
                   qdict_get_int(stream, "offset"),
                   qdict_get_int(stream, "len"),
                   qdict_get_int(stream, "speed"));
}

static void monitor_print_block_job(QObject *obj, void *opaque)
{
    monitor_print_block_stream((Monitor *)opaque, obj);
}

void monitor_print_block_jobs(Monitor *mon, const QObject *data)
{
    QList *streams;

    assert(data);
    streams = qobject_to_qlist(data);
    assert(streams); /* we pass a list of stream objects to ourselves */

    if (qlist_empty(streams)) {
        monitor_printf(mon, "No active jobs\n");
        return;
    }

    qlist_iter(streams, monitor_print_block_job, mon);
}

void do_info_block_jobs(Monitor *mon, QObject **ret_data)
{
    QList *streams;
    StreamState *s;

    streams = qlist_new();
    QLIST_FOREACH(s, &block_streams, list) {
        qlist_append_obj(streams, stream_get_qobject(s));
    }
    *ret_data = QOBJECT(streams);
}

int do_block_stream(Monitor *mon, const QDict *params, QObject **ret_data)
{
    const char *device = qdict_get_str(params, "device");

    return stream_start(device) ? 0 : -1;
}

int do_block_job_cancel(Monitor *mon, const QDict *params,
                        MonitorCompletion cb, void *opaque)
{
    const char *device = qdict_get_str(params, "device");

    return stream_stop(device, cb, opaque);
}

int do_block_job_set_speed(Monitor *mon, const QDict *params,
                           QObject **ret_data)
{
    const char *device = qdict_get_str(params, "device");
    int64_t value;

    value = qdict_get_int(params, "value");
    if (value < 0) {
        value = 0;
    }

    return stream_set_speed(device, value);
}

static int eject_device(Monitor *mon, BlockDriverState *bs, int force)
{
    if (!bdrv_dev_has_removable_media(bs)) {
        qerror_report(QERR_DEVICE_NOT_REMOVABLE, bdrv_get_device_name(bs));
        return -1;
    }
    if (!force && !bdrv_dev_is_tray_open(bs)
        && bdrv_dev_is_medium_locked(bs)) {
        qerror_report(QERR_DEVICE_LOCKED, bdrv_get_device_name(bs));
        return -1;
    }
    bdrv_close(bs);
    return 0;
}

int do_eject(Monitor *mon, const QDict *qdict, QObject **ret_data)
{
    BlockDriverState *bs;
    int force = qdict_get_int(qdict, "force");
    const char *filename = qdict_get_str(qdict, "device");

    bs = bdrv_find(filename);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, filename);
        return -1;
    }
    return eject_device(mon, bs, force);
}

int do_block_set_passwd(Monitor *mon, const QDict *qdict,
                        QObject **ret_data)
{
    BlockDriverState *bs;
    int err;

    bs = bdrv_find(qdict_get_str(qdict, "device"));
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, qdict_get_str(qdict, "device"));
        return -1;
    }

    err = bdrv_set_key(bs, qdict_get_str(qdict, "password"));
    if (err == -EINVAL) {
        qerror_report(QERR_DEVICE_NOT_ENCRYPTED, bdrv_get_device_name(bs));
        return -1;
    } else if (err < 0) {
        qerror_report(QERR_INVALID_PASSWORD);
        return -1;
    }

    return 0;
}

int do_change_block(Monitor *mon, const char *device,
                    const char *filename, const char *fmt)
{
    BlockDriverState *bs;
    BlockDriver *drv = NULL;
    int bdrv_flags;

    bs = bdrv_find(device);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, device);
        return -1;
    }
    if (fmt) {
        drv = bdrv_find_whitelisted_format(fmt);
        if (!drv) {
            qerror_report(QERR_INVALID_BLOCK_FORMAT, fmt);
            return -1;
        }
    }
    if (eject_device(mon, bs, 0) < 0) {
        return -1;
    }
    bdrv_flags = bdrv_get_type_hint(bs) == BDRV_TYPE_CDROM ? 0 : BDRV_O_RDWR;
    bdrv_flags |= bdrv_is_snapshot(bs) ? BDRV_O_SNAPSHOT : 0;
    if (bdrv_open(bs, filename, bdrv_flags, drv)) {
        qerror_report(QERR_OPEN_FILE_FAILED, filename);
        return -1;
    }
    return monitor_read_bdrv_key_start(mon, bs, NULL, NULL);
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
    if (bdrv_in_use(bs)) {
        qerror_report(QERR_DEVICE_IN_USE, id);
        return -1;
    }

    /* quiesce block driver; prevent further io */
    qemu_aio_flush();
    bdrv_flush(bs);
    bdrv_close(bs);

    /* if we have a device attached to this BlockDriverState
     * then we need to make the drive anonymous until the device
     * can be removed.  If this is a drive with no device backing
     * then we can just get rid of the block driver state right here.
     */
    if (bdrv_get_attached_dev(bs)) {
        bdrv_make_anon(bs);
    } else {
        drive_uninit(drive_get_by_blockdev(bs));
    }

    return 0;
}

/*
 * XXX: replace the QERR_UNDEFINED_ERROR errors with real values once the
 * existing QERR_ macro mess is cleaned up.  A good example for better
 * error reports can be found in the qemu-img resize code.
 */
int do_block_resize(Monitor *mon, const QDict *qdict, QObject **ret_data)
{
    const char *device = qdict_get_str(qdict, "device");
    int64_t size = qdict_get_int(qdict, "size");
    BlockDriverState *bs;

    bs = bdrv_find(device);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, device);
        return -1;
    }

    if (size < 0) {
        qerror_report(QERR_UNDEFINED_ERROR);
        return -1;
    }

    if (bdrv_truncate(bs, size)) {
        qerror_report(QERR_UNDEFINED_ERROR);
        return -1;
    }

    return 0;
}
