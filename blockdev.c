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
#include "qemu-objects.h"
#include "sysemu.h"
#include "block_int.h"
#include "qmp-commands.h"
#include "trace.h"

struct drivelist drives = QTAILQ_HEAD_INITIALIZER(drives);
DriveInfo *extboot_drive = NULL;
static void block_job_cb(void *opaque, int ret);

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

    if (bs->job) {
        block_job_cancel(bs->job);
    }
    if (dinfo) {
        dinfo->auto_del = 1;
    }
}

void blockdev_auto_del(BlockDriverState *bs)
{
    DriveInfo *dinfo = drive_get_by_blockdev(bs);

    if (dinfo && dinfo->auto_del) {
        drive_put_ref(dinfo);
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

static void drive_uninit(DriveInfo *dinfo)
{
    qemu_opts_del(dinfo->opts);
    bdrv_delete(dinfo->bdrv);
    qemu_free(dinfo->id);
    QTAILQ_REMOVE(&drives, dinfo, next);
    qemu_free(dinfo->file);
    qemu_free(dinfo);
}

void drive_put_ref(DriveInfo *dinfo)
{
    assert(dinfo->refcount);
    if (--dinfo->refcount == 0) {
        drive_uninit(dinfo);
    }
}

void drive_get_ref(DriveInfo *dinfo)
{
    dinfo->refcount++;
}

typedef struct {
    QEMUBH *bh;
    DriveInfo *dinfo;
} DrivePutRefBH;

static void drive_put_ref_bh(void *opaque)
{
    DrivePutRefBH *s = opaque;

    drive_put_ref(s->dinfo);
    qemu_bh_delete(s->bh);
    g_free(s);
}

/*
 * Release a drive reference in a BH
 *
 * It is not possible to use drive_put_ref() from a callback function when the
 * callers still need the drive.  In such cases we schedule a BH to release the
 * reference.
 */
static void drive_put_ref_bh_schedule(DriveInfo *dinfo)
{
    DrivePutRefBH *s;

    s = g_new(DrivePutRefBH, 1);
    s->bh = qemu_bh_new(drive_put_ref_bh, s);
    s->dinfo = dinfo;
    qemu_bh_schedule(s->bh);
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
            ThrottleConfig cfg;
            bool io_limits_enabled = dinfo->bdrv->io_limits_enabled;

            if (io_limits_enabled) {
                throttle_get_config(&dinfo->bdrv->throttle_state, &cfg);
            }

            bdrv_close(dinfo->bdrv);
            res = drive_open(dinfo);
            if (res) {
		    fprintf(stderr, "qemu: re-open of %s failed wth error %d\n",
			    dinfo->file, res);
		    return res;
	    }

            if (io_limits_enabled) {
                bdrv_io_limits_enable(dinfo->bdrv);
                bdrv_set_io_limits(dinfo->bdrv, &cfg);
            }
        }
    }
    return 0;
}

static bool check_throttle_config(ThrottleConfig *cfg, Error **errp)
{
    if (throttle_conflicting(cfg)) {
        error_setg(errp, "bps/iops/max total values and read/write values"
                         " cannot be used at the same time");
        return false;
    }

    if (!throttle_is_valid(cfg)) {
        error_setg(errp, "bps/iops/max values must be within [0, %lld]",
                   THROTTLE_VALUE_MAX);
        return false;
    }

    return true;
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
    ThrottleConfig cfg;
    int snapshot = 0;
    bool copy_on_read;
#ifdef CONFIG_BLOCK_IO_THROTTLING
    Error *error = NULL;
#endif

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
    copy_on_read = qemu_opt_get_bool(opts, "copy-on-read", false);

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
        if (bdrv_parse_cache_flags(buf, &bdrv_flags) != 0) {
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
        drv = bdrv_find_whitelisted_format(buf, ro);
        if (!drv) {
            if (!ro && bdrv_find_whitelisted_format(buf, !ro)) {
                error_report("'%s' can be only used as read-only device.", buf);
            } else {
                error_report("'%s' invalid format", buf);
            }
            return NULL;
        }
    }

    is_extboot = qemu_opt_get_bool(opts, "boot", 0);
    if (is_extboot && extboot_drive) {
        error_report("two bootable drives specified");
        return NULL;
    }

#ifdef CONFIG_BLOCK_IO_THROTTLING
    /* disk I/O throttling */
    memset(&cfg, 0, sizeof(cfg));
    cfg.buckets[THROTTLE_BPS_TOTAL].avg =
        qemu_opt_get_number(opts, "bps", 0);
    cfg.buckets[THROTTLE_BPS_READ].avg  =
        qemu_opt_get_number(opts, "bps_rd", 0);
    cfg.buckets[THROTTLE_BPS_WRITE].avg =
        qemu_opt_get_number(opts, "bps_wr", 0);
    cfg.buckets[THROTTLE_OPS_TOTAL].avg =
        qemu_opt_get_number(opts, "iops", 0);
    cfg.buckets[THROTTLE_OPS_READ].avg =
        qemu_opt_get_number(opts, "iops_rd", 0);
    cfg.buckets[THROTTLE_OPS_WRITE].avg =
        qemu_opt_get_number(opts, "iops_wr", 0);

    cfg.buckets[THROTTLE_BPS_TOTAL].max = 0;
    cfg.buckets[THROTTLE_BPS_READ].max  = 0;
    cfg.buckets[THROTTLE_BPS_WRITE].max = 0;

    cfg.buckets[THROTTLE_OPS_TOTAL].max = 0;
    cfg.buckets[THROTTLE_OPS_READ].max  = 0;
    cfg.buckets[THROTTLE_OPS_WRITE].max = 0;

    cfg.op_size = 0;

    if (!check_throttle_config(&cfg, &error)) {
        error_report("%s", error_get_pretty(error));
        error_free(error);
        return NULL;
    }
#else
    memset(&cfg, 0, sizeof(cfg));
#endif

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
    dinfo->bdrv->open_flags = snapshot ? BDRV_O_SNAPSHOT : 0;
    dinfo->bdrv->read_only = ro;
    dinfo->devaddr = devaddr;
    dinfo->type = type;
    dinfo->bus = bus_id;
    dinfo->unit = unit_id;
    dinfo->opts = opts;
    dinfo->refcount = 1;
    if (serial)
        strncpy(dinfo->serial, serial, sizeof(dinfo->serial) - 1);
    QTAILQ_INSERT_TAIL(&drives, dinfo, next);
    if (is_extboot) {
        extboot_drive = dinfo;
    }

    bdrv_set_on_error(dinfo->bdrv, on_read_error, on_write_error);

    /* disk I/O throttling */
    if (throttle_enabled(&cfg)) {
        bdrv_io_limits_enable(dinfo->bdrv);
        bdrv_set_io_limits(dinfo->bdrv, &cfg);
    }

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
    const char *device = qdict_get_str(qdict, "device");
    BlockDriverState *bs;
    int ret;

    if (!strcmp(device, "all")) {
        ret = bdrv_commit_all();
    } else {
        bs = bdrv_find(device);
        if (!bs) {
            monitor_printf(mon, "Device '%s' not found\n", device);
            return;
        }
        ret = bdrv_commit(bs);
    }
    if (ret < 0) {
        monitor_printf(mon, "'commit' error for '%s': %s\n", device,
                       strerror(-ret));
    }
}

#ifdef CONFIG_LIVE_SNAPSHOTS
void qmp___com_redhat_drive_reopen(const char *device, const char *new_image_file,
                      bool has_format, const char *format,
                      bool has_witness, const char *witness,
                      Error **errp)
{
    BlockDriverState *bs;
    BlockDriver *drv, *old_drv, *proto_drv;
    int fd = -1;
    int ret = 0;
    int flags;
    char old_filename[1024];

    if (has_witness) {
        fd = monitor_get_fd(cur_mon, witness);
        if (fd == -1) {
            error_set(errp, QERR_FD_NOT_FOUND, witness);
            return;
        }
    }

    bs = bdrv_find(device);
    if (!bs) {
        error_set(errp, QERR_DEVICE_NOT_FOUND, device);
        return;
    }
    if (bs->job) {
        int ret = block_job_cancel_sync(bs->job);

        /* Do not complete the switch if the job had an I/O error or
         * was canceled (for mirroring, the target was not synchronized
         * completely).
         */
        if (ret != 0) {
            error_set(errp, QERR_DEVICE_IN_USE, device);
            return;
        }
    }
    if (bdrv_in_use(bs)) {
        error_set(errp, QERR_DEVICE_IN_USE, device);
        return;
    }

    pstrcpy(old_filename, sizeof(old_filename), bs->filename);

    old_drv = bs->drv;
    flags = bs->open_flags;

    if (has_format) {
        drv = bdrv_find_format(format);
        if (!drv) {
            error_set(errp, QERR_INVALID_BLOCK_FORMAT, format);
            return;
        }
    } else {
        drv = NULL;
    }

    proto_drv = bdrv_find_protocol(new_image_file, NULL);
    if (!proto_drv) {
        error_set(errp, QERR_INVALID_BLOCK_FORMAT, format);
        return;
    }

    qemu_aio_flush();
    if (!bdrv_is_read_only(bs) && bdrv_is_inserted(bs)) {
        if (bdrv_flush(bs)) {
            error_set(errp, QERR_IO_ERROR);
            return;
        }
    }

    bdrv_close(bs);
    ret = bdrv_open(bs, new_image_file, flags, drv);

    if (ret == 0 && fd != -1) {
        ret = write(fd, "", 1) == 1 ? 0 : -1;
        qemu_fdatasync(fd);
        close(fd);
        if (ret < 0) {
            bdrv_close(bs);
        }
    }

    /*
     * If reopening the image file we just created fails, fall back
     * and try to re-open the original image. If that fails too, we
     * are in serious trouble.
     */
    if (ret != 0) {
        int ret2;
        ret2 = bdrv_open(bs, old_filename, flags, old_drv);
        if (ret2 != 0) {
            error_set(errp, QERR_OPEN_FILE_FAILED, old_filename,
                      strerror(-ret2));
        } else {
            error_set(errp, QERR_OPEN_FILE_FAILED, new_image_file,
                      strerror(-ret));
        }
    }
}

static void blockdev_do_action(int kind, void *data, Error **errp)
{
    BlockdevAction action;
    BlockdevActionList list;

    action.kind = kind;
    action.data = data;
    list.value = &action;
    list.next = NULL;
    qmp_transaction(&list, errp);
}

void qmp_blockdev_snapshot_sync(const char *device, const char *snapshot_file,
                                bool has_format, const char *format,
                                bool has_mode, enum NewImageMode mode,
                                Error **errp)
{
    BlockdevSnapshot snapshot = {
        .device = (char *) device,
        .snapshot_file = (char *) snapshot_file,
        .has_format = has_format,
        .format = (char *) format,
        .has_mode = has_mode,
        .mode = mode,
    };
    blockdev_do_action(BLOCKDEV_ACTION_KIND_BLOCKDEV_SNAPSHOT_SYNC, &snapshot,
                       errp);
}
#endif 

#ifdef CONFIG_LIVE_SNAPSHOTS
void qmp___com_redhat_drive_mirror(const char *device, const char *target,
                      bool has_format, const char *format,
                      bool has_speed, int64_t speed,
                      bool has_full, bool full,
                      bool has_mode, enum NewImageMode mode, Error **errp)
{
    BlockdevMirror mirror = {
        .device = (char *) device,
        .target = (char *) target,
        .has_format = has_format,
        .format = (char *) format,
        .has_mode = has_mode,
        .mode = mode,
        .has_full = has_full,
        .full = full,
        .has_speed = has_speed,
        .speed = speed,
    };
    blockdev_do_action(BLOCKDEV_ACTION_KIND_COM_REDHAT_DRIVE_MIRROR, &mirror, errp);
}

/* New and old BlockDriverState structs for group snapshots */
typedef struct BlkTransactionStates {
    enum BlockdevActionKind kind;
    BlockDriverState *old_bs;
    BlockDriverState *new_bs;
    QSIMPLEQ_ENTRY(BlkTransactionStates) entry;
} BlkTransactionStates;

/*
 * 'Atomic' group snapshots.  The snapshots are taken as a set, and if any fail
 *  then we do not pivot any of the devices in the group, and abandon the
 *  snapshots
 */
void qmp_transaction(BlockdevActionList *dev_list, Error **errp)
{
    int ret = 0;
    BlockdevActionList *dev_entry = dev_list;
    BlkTransactionStates *states, *next;
    Error *local_err = NULL;

    QSIMPLEQ_HEAD(snap_bdrv_states, BlkTransactionStates) snap_bdrv_states;
    QSIMPLEQ_INIT(&snap_bdrv_states);

    /* drain all i/o before any snapshots */
    qemu_aio_flush();

    /* We don't do anything in this loop that commits us to the snapshot */
    while (NULL != dev_entry) {
        BlockdevAction *dev_info = NULL;
        BlockDriverState *source;
        BlockDriver *proto_drv;
        BlockDriver *drv = NULL;
        int flags;
        enum NewImageMode mode;
        const char *new_image_file;
        const char *device;
        const char *format = NULL;
        uint64_t size;
        bool full;
        int64_t speed=0;

        dev_info = dev_entry->value;
        dev_entry = dev_entry->next;

        states = g_malloc0(sizeof(BlkTransactionStates));
        QSIMPLEQ_INSERT_TAIL(&snap_bdrv_states, states, entry);
        states->kind = dev_info->kind;

        switch (dev_info->kind) {
        case BLOCKDEV_ACTION_KIND_BLOCKDEV_SNAPSHOT_SYNC:
            device = dev_info->blockdev_snapshot_sync->device;
            if (!dev_info->blockdev_snapshot_sync->has_mode) {
                dev_info->blockdev_snapshot_sync->mode = NEW_IMAGE_MODE_ABSOLUTE_PATHS;
            }
            new_image_file = dev_info->blockdev_snapshot_sync->snapshot_file;
            if (dev_info->blockdev_snapshot_sync->has_format) {
                format = dev_info->blockdev_snapshot_sync->format;
            }
            mode = dev_info->blockdev_snapshot_sync->mode;
            if (!format && mode != NEW_IMAGE_MODE_EXISTING) {
                format = "qcow2";
            }
            source = states->old_bs;
            full = false;
            break;

        case BLOCKDEV_ACTION_KIND_COM_REDHAT_DRIVE_MIRROR:
            device = dev_info->__com_redhat_drive_mirror->device;
            if (!dev_info->__com_redhat_drive_mirror->has_mode) {
                dev_info->__com_redhat_drive_mirror->mode = NEW_IMAGE_MODE_ABSOLUTE_PATHS;
            }
            new_image_file = dev_info->__com_redhat_drive_mirror->target;
            if (dev_info->__com_redhat_drive_mirror->has_format) {
                format = dev_info->__com_redhat_drive_mirror->format;
            }
            mode = dev_info->__com_redhat_drive_mirror->mode;
            full = dev_info->__com_redhat_drive_mirror->has_full
                && dev_info->__com_redhat_drive_mirror->full;
            if (dev_info->__com_redhat_drive_mirror->has_speed) {
                speed = dev_info->__com_redhat_drive_mirror->speed;
            }
            break;

        default:
            abort();
        }

        if (format) {
            drv = bdrv_find_format(format);
            if (!drv) {
                error_set(errp, QERR_INVALID_BLOCK_FORMAT, format);
                goto delete_and_fail;
            }
        }

        states->old_bs = bdrv_find(device);
        if (!states->old_bs) {
            error_set(errp, QERR_DEVICE_NOT_FOUND, device);
            goto delete_and_fail;
        }

        if (!bdrv_is_inserted(states->old_bs)) {
            error_set(errp, QERR_DEVICE_HAS_NO_MEDIUM, device);
            goto delete_and_fail;
        }

        if (bdrv_in_use(states->old_bs)) {
            error_set(errp, QERR_DEVICE_IN_USE, device);
            goto delete_and_fail;
        }

        if (!format && mode != NEW_IMAGE_MODE_EXISTING) {
            format = states->old_bs->drv->format_name;
            drv = states->old_bs->drv;
        }
        if (dev_info->kind == BLOCKDEV_ACTION_KIND_BLOCKDEV_SNAPSHOT_SYNC) {
            if (!bdrv_is_read_only(states->old_bs)) {
                if (bdrv_flush(states->old_bs)) {
                    error_set(errp, QERR_IO_ERROR);
                    goto delete_and_fail;
                }
            }

            source = states->old_bs;
        } else {
            source = states->old_bs->backing_hd;
            if (!source) {
                full = true;
            }
        }
        flags = states->old_bs->open_flags;

        proto_drv = bdrv_find_protocol(new_image_file, NULL);
        if (!proto_drv) {
            error_set(errp, QERR_INVALID_BLOCK_FORMAT, format);
            goto delete_and_fail;
        }

        bdrv_get_geometry(states->old_bs, &size);
        size *= 512;
        if (full && mode != NEW_IMAGE_MODE_EXISTING) {
            assert(format && drv);
            bdrv_img_create(new_image_file, format,
                            NULL, NULL, NULL, size, flags, &local_err);
        } else {
            /* create new image w/backing file */
            switch (mode) {
            case NEW_IMAGE_MODE_EXISTING:
                break;
            case NEW_IMAGE_MODE_ABSOLUTE_PATHS:
                bdrv_img_create(new_image_file, format,
                                source->filename,
                                source->drv->format_name,
                                NULL, size, flags, &local_err);
                break;
            default:
                error_setg(&local_err, "%s: invalid NewImageMode %u",
                           __FUNCTION__, (unsigned)mode);
                break;
            }
        }

        if (error_is_set(&local_err)) {
            error_propagate(errp, local_err);
            goto delete_and_fail;
        }

        /* We will manually add the backing_hd field to the bs later */
        switch (dev_info->kind) {
        case BLOCKDEV_ACTION_KIND_BLOCKDEV_SNAPSHOT_SYNC:
            states->new_bs = bdrv_new("");
            ret = bdrv_open(states->new_bs, new_image_file,
                            flags | BDRV_O_NO_BACKING, drv);
            break;

        case BLOCKDEV_ACTION_KIND_COM_REDHAT_DRIVE_MIRROR:
            /* Grab a reference so hotplug does not delete the BlockDriverState
             * from underneath us.
             */
            drive_get_ref(drive_get_by_blockdev(states->old_bs));
            ret = mirror_start(states->old_bs, new_image_file, drv, flags,
                               speed, block_job_cb, states->old_bs, full);
            if (ret == 0) {
                /* A marker for the abort action  */
                states->new_bs = states->old_bs;
            }
            break;

        default:
            abort();
        }

        if (ret != 0) {
            error_set(errp, QERR_OPEN_FILE_FAILED, new_image_file,
                      strerror(-ret));
            goto delete_and_fail;
        }
    }


    /* Now we are going to do the actual pivot.  Everything up to this point
     * is reversible, but we are committed at this point */
    QSIMPLEQ_FOREACH(states, &snap_bdrv_states, entry) {
        switch (states->kind) {
        case BLOCKDEV_ACTION_KIND_BLOCKDEV_SNAPSHOT_SYNC:
            /* This removes our old bs from the bdrv_states, and adds the new bs */
            bdrv_append(states->new_bs, states->old_bs);
            /* We don't need (or want) to use the transactional
             * bdrv_reopen_multiple() across all the entries at once, because we
             * don't want to abort all of them if one of them fails the reopen */
            bdrv_reopen(states->new_bs, states->new_bs->open_flags & ~BDRV_O_RDWR,
                        NULL);
            break;

        case BLOCKDEV_ACTION_KIND_COM_REDHAT_DRIVE_MIRROR:
            mirror_commit(states->old_bs);
            break;

        default:
            abort();
        }
    }

    /* success */
    goto exit;

delete_and_fail:
    /*
    * failure, and it is all-or-none; abandon each new bs, and keep using
    * the original bs for all images
    */
    QSIMPLEQ_FOREACH(states, &snap_bdrv_states, entry) {
        switch (states->kind) {
        case BLOCKDEV_ACTION_KIND_BLOCKDEV_SNAPSHOT_SYNC:
            if (states->new_bs) {
                bdrv_delete(states->new_bs);
            }
            break;

        case BLOCKDEV_ACTION_KIND_COM_REDHAT_DRIVE_MIRROR:
            /* This will still invoke the callback and release the
             * reference.  */
            if (states->new_bs) {
                mirror_abort(states->old_bs);
            }
            break;

        default:
            abort();
        }
    }
exit:
    QSIMPLEQ_FOREACH_SAFE(states, &snap_bdrv_states, entry, next) {
        g_free(states);
    }
    return;
}
#endif

static int eject_device(Monitor *mon, BlockDriverState *bs, int force)
{
    if (bdrv_in_use(bs)) {
        qerror_report(QERR_DEVICE_IN_USE, bdrv_get_device_name(bs));
        return -1;
    }
    if (!bdrv_dev_has_removable_media(bs)) {
        qerror_report(QERR_DEVICE_NOT_REMOVABLE, bdrv_get_device_name(bs));
        return -1;
    }
    if (bdrv_dev_is_medium_locked(bs) && !bdrv_dev_is_tray_open(bs)) {
        bdrv_dev_eject_request(bs, force);
        if (!force) {
            qerror_report(QERR_DEVICE_LOCKED, bdrv_get_device_name(bs));
            return -1;
        }
    }
    bdrv_close(bs);
    return 0;
}

int do_eject(Monitor *mon, const QDict *qdict, QObject **ret_data)
{
    BlockDriverState *bs;
    int force = qdict_get_try_bool_or_int(qdict, "force", 0);
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
    int ret;

    bs = bdrv_find(device);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, device);
        return -1;
    }
    if (fmt) {
        drv = bdrv_find_whitelisted_format(fmt, bs->read_only);
        if (!drv) {
            qerror_report(QERR_INVALID_BLOCK_FORMAT, fmt);
            return -1;
        }
    }
    if (eject_device(mon, bs, 0) < 0) {
        return -1;
    }
    bdrv_flags = bdrv_is_read_only(bs) ? 0 : BDRV_O_RDWR;
    bdrv_flags |= bdrv_is_snapshot(bs) ? BDRV_O_SNAPSHOT : 0;
    ret = bdrv_open(bs, filename, bdrv_flags, drv);
    if (ret < 0) {
        qerror_report(QERR_OPEN_FILE_FAILED, filename, strerror(-ret));
        return -1;
    }
    return monitor_read_bdrv_key_start(mon, bs, NULL, NULL);
}

/* throttling disk I/O limits */
int do_block_set_io_throttle(Monitor *mon,
                       const QDict *qdict, QObject **ret_data)
{
    ThrottleConfig cfg;
    const char *devname = qdict_get_str(qdict, "device");
    BlockDriverState *bs;
    Error *error = NULL;
    int64_t bps, bps_rd, bps_wr;
    int64_t iops, iops_rd, iops_wr;

    bps = qdict_get_try_int(qdict, "bps", -1);
    bps_rd = qdict_get_try_int(qdict, "bps_rd", -1);
    bps_wr = qdict_get_try_int(qdict, "bps_wr", -1);
    iops = qdict_get_try_int(qdict, "iops", -1);
    iops_rd = qdict_get_try_int(qdict, "iops_rd", -1);
    iops_wr = qdict_get_try_int(qdict, "iops_wr", -1);

    bs = bdrv_find(devname);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, devname);
        return -1;
    }

    memset(&cfg, 0, sizeof(cfg));
    cfg.buckets[THROTTLE_BPS_TOTAL].avg = bps;
    cfg.buckets[THROTTLE_BPS_READ].avg  = bps_rd;
    cfg.buckets[THROTTLE_BPS_WRITE].avg = bps_wr;

    cfg.buckets[THROTTLE_OPS_TOTAL].avg = iops;
    cfg.buckets[THROTTLE_OPS_READ].avg  = iops_rd;
    cfg.buckets[THROTTLE_OPS_WRITE].avg = iops_wr;

    cfg.buckets[THROTTLE_BPS_TOTAL].max = 0;
    cfg.buckets[THROTTLE_BPS_READ].max  = 0;
    cfg.buckets[THROTTLE_BPS_WRITE].max = 0;

    cfg.buckets[THROTTLE_OPS_TOTAL].max = 0;
    cfg.buckets[THROTTLE_OPS_READ].max  = 0;
    cfg.buckets[THROTTLE_OPS_WRITE].max = 0;

    cfg.op_size = 0;

    if (!check_throttle_config(&cfg, &error)) {
        if (error_is_set(&error)) {
            qerror_report(QERR_GENERIC_ERROR, error_get_pretty(error));
        }
        error_free(error);
        return -1;
    }

    if (!bs->io_limits_enabled && throttle_enabled(&cfg)) {
        bdrv_io_limits_enable(bs);
    } else if (bs->io_limits_enabled && !throttle_enabled(&cfg)) {
        bdrv_io_limits_disable(bs);
    }

    if (bs->io_limits_enabled) {
        bdrv_set_io_limits(bs, &cfg);
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
    if (bdrv_in_use(bs)) {
        qerror_report(QERR_DEVICE_IN_USE, id);
        return -1;
    }

    /* quiesce block driver; prevent further io */
    bdrv_drain_all();
    bdrv_flush(bs);
    bdrv_close(bs);

    /* if we have a device attached to this BlockDriverState
     * then we need to make the drive anonymous until the device
     * can be removed.  If this is a drive with no device backing
     * then we can just get rid of the block driver state right here.
     */
    if (bdrv_get_attached_dev(bs)) {
        bdrv_make_anon(bs);

        /* Further I/O must not pause the guest */
        bdrv_set_on_error(bs, BLOCK_ERR_REPORT, BLOCK_ERR_REPORT);
    } else {
        drive_uninit(drive_get_by_blockdev(bs));
    }

    return 0;
}

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
        qerror_report(QERR_INVALID_PARAMETER_VALUE, "size", "a >0 size");
        return -1;
    }

    switch (bdrv_truncate(bs, size)) {
    case 0:
        break;
    case -ENOMEDIUM:
        qerror_report(QERR_DEVICE_HAS_NO_MEDIUM, device);
        return -1;
    case -ENOTSUP:
        qerror_report(QERR_UNSUPPORTED);
        return -1;
    case -EACCES:
        qerror_report(QERR_DEVICE_IS_READ_ONLY, device);
        return -1;
    case -EBUSY:
        qerror_report(QERR_DEVICE_IN_USE, device);
        return -1;
    default:
        qerror_report(QERR_UNDEFINED_ERROR);
        return -1;
    }

    return 0;
}

static QObject *qobject_from_block_job(BlockJob *job)
{
    return qobject_from_jsonf("{ 'type': %s,"
                              "'device': %s,"
                              "'len': %" PRId64 ","
                              "'offset': %" PRId64 ","
                              "'speed': %" PRId64 " }",
                              job->job_type->job_type,
                              bdrv_get_device_name(job->bs),
                              job->len,
                              job->offset,
                              job->speed);
}

static void block_job_cb(void *opaque, int ret)
{
    BlockDriverState *bs = opaque;
    QObject *obj;

    trace_block_job_cb(bs, bs->job, ret);

    assert(bs->job);
    obj = qobject_from_block_job(bs->job);
    if (ret < 0) {
        QDict *dict = qobject_to_qdict(obj);
        qdict_put(dict, "error", qstring_from_str(strerror(-ret)));
    }

    if (block_job_is_cancelled(bs->job)) {
        monitor_protocol_event(QEVENT_BLOCK_JOB_CANCELLED, obj);
    } else {
        monitor_protocol_event(QEVENT_BLOCK_JOB_COMPLETED, obj);
    }
    qobject_decref(obj);

    drive_put_ref_bh_schedule(drive_get_by_blockdev(bs));
}

int do_block_stream(Monitor *mon, const QDict *params, QObject **ret_data)
{
    const char *device = qdict_get_str(params, "device");
    const char *base = qdict_get_try_str(params, "base");
    const int64_t speed = qdict_get_try_int(params, "speed", 0);
    BlockDriverState *bs;
    BlockDriverState *base_bs = NULL;
    int ret;

    bs = bdrv_find(device);
    if (!bs) {
        qerror_report(QERR_DEVICE_NOT_FOUND, device);
        return -1;
    }

    if (base) {
        base_bs = bdrv_find_backing_image(bs, base);
        if (base_bs == NULL) {
            qerror_report(QERR_BASE_NOT_FOUND, base);
            return -1;
        }
    }

    ret = stream_start(bs, base_bs, base, speed, block_job_cb, bs);
    if (ret < 0) {
        switch (ret) {
        case -EBUSY:
            qerror_report(QERR_DEVICE_IN_USE, device);
            return -1;
        default:
            qerror_report(QERR_NOT_SUPPORTED);
            return -1;
        }
    }

    /* Grab a reference so hotplug does not delete the BlockDriverState from
     * underneath us.
     */
    drive_get_ref(drive_get_by_blockdev(bs));

    trace_do_block_stream(bs, bs->job);
    return 0;
}

#ifdef CONFIG_LIVE_SNAPSHOTS
void qmp___com_redhat_block_commit(const char *device,
                      bool has_base, const char *base, const char *top,
                      bool has_speed, int64_t speed,
                      Error **errp)
{
    BlockDriverState *bs;
    BlockDriverState *base_bs, *top_bs;
    Error *local_err = NULL;
    /* This will be part of the QMP command, if/when the
     * BlockdevOnError change for blkmirror makes it in
     */
    BlockErrorAction on_error = BLOCK_ERR_REPORT;

    /* drain all i/o before commits */
    bdrv_drain_all();

    bs = bdrv_find(device);
    if (!bs) {
        error_set(errp, QERR_DEVICE_NOT_FOUND, device);
        return;
    }

    /* default top_bs is the active layer */
    top_bs = bs;

    if (top) {
        if (strcmp(bs->filename, top) != 0) {
            top_bs = bdrv_find_backing_image(bs, top);
        }
    }

    if (top_bs == NULL) {
        error_set(errp, QERR_TOP_NOT_FOUND, top ? top : "NULL");
        return;
    }

    if (has_base && base) {
        base_bs = bdrv_find_backing_image(top_bs, base);
    } else {
        base_bs = bdrv_find_base(top_bs);
    }

    if (base_bs == NULL) {
        error_set(errp, QERR_BASE_NOT_FOUND, base ? base : "NULL");
        return;
    }

    commit_start(bs, base_bs, top_bs, speed, on_error, block_job_cb, bs,
                &local_err);
    if (local_err != NULL) {
        error_propagate(errp, local_err);
        return;
    }
    /* Grab a reference so hotplug does not delete the BlockDriverState from
     * underneath us.
     */
    drive_get_ref(drive_get_by_blockdev(bs));
}
#endif

static BlockJob *find_block_job(const char *device)
{
    BlockDriverState *bs;

    bs = bdrv_find(device);
    if (!bs || !bs->job) {
        return NULL;
    }
    return bs->job;
}

int do_block_job_set_speed(Monitor *mon, const QDict *params,
                           QObject **ret_data)
{
    const char *device = qdict_get_str(params, "device");
    int64_t speed = qdict_get_int(params, "speed");
    BlockJob *job = find_block_job(device);

    if (!job) {
        qerror_report(QERR_DEVICE_NOT_ACTIVE, device);
        return -1;
    }

    if (block_job_set_speed(job, speed) < 0) {
        qerror_report(QERR_NOT_SUPPORTED);
        return -1;
    }
    return 0;
}

int do_block_job_cancel(Monitor *mon, const QDict *params, QObject **ret_data)
{
    const char *device = qdict_get_str(params, "device");
    BlockJob *job = find_block_job(device);

    if (!job) {
        qerror_report(QERR_DEVICE_NOT_ACTIVE, device);
        return -1;
    }

    trace_do_block_job_cancel(job);
    block_job_cancel(job);
    return 0;
}

static void monitor_print_block_jobs_one(QObject *info, void *opaque)
{
    QDict *stream = qobject_to_qdict(info);
    Monitor *mon = opaque;

    if (strcmp(qdict_get_str(stream, "type"), "stream") == 0) {
        monitor_printf(mon, "Streaming device %s: Completed %" PRId64
                " of %" PRId64 " bytes, speed limit %" PRId64
                " bytes/s\n",
                qdict_get_str(stream, "device"),
                qdict_get_int(stream, "offset"),
                qdict_get_int(stream, "len"),
                qdict_get_int(stream, "speed"));
    } else {
        monitor_printf(mon, "Type %s, device %s: Completed %" PRId64
                " of %" PRId64 " bytes, speed limit %" PRId64
                " bytes/s\n",
                qdict_get_str(stream, "type"),
                qdict_get_str(stream, "device"),
                qdict_get_int(stream, "offset"),
                qdict_get_int(stream, "len"),
                qdict_get_int(stream, "speed"));
    }
}

void monitor_print_block_jobs(Monitor *mon, const QObject *data)
{
    QList *list = qobject_to_qlist(data);

    assert(list);

    if (qlist_empty(list)) {
        monitor_printf(mon, "No active jobs\n");
        return;
    }

    qlist_iter(list, monitor_print_block_jobs_one, mon);
}

static void do_info_block_jobs_one(void *opaque, BlockDriverState *bs)
{
    QList *list = opaque;
    BlockJob *job = bs->job;

    if (job) {
        qlist_append_obj(list, qobject_from_block_job(job));
    }
}

void do_info_block_jobs(Monitor *mon, QObject **ret_data)
{
    QList *list = qlist_new();
    bdrv_iterate(do_info_block_jobs_one, list);
    *ret_data = QOBJECT(list);
}
