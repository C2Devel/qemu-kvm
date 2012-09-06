/*
 * QEMU host block devices
 *
 * Copyright (c) 2003-2008 Fabrice Bellard
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or
 * later.  See the COPYING file in the top-level directory.
 */

#ifndef BLOCKDEV_H
#define BLOCKDEV_H

#include "block.h"
#include "qemu-queue.h"

void blockdev_mark_auto_del(BlockDriverState *bs);
void blockdev_auto_del(BlockDriverState *bs);

#define BLOCK_SERIAL_STRLEN 20

typedef enum {
    IF_DEFAULT = -1,            /* for use with drive_add() only */
    IF_NONE,
    IF_IDE, IF_SCSI, IF_FLOPPY, IF_PFLASH, IF_MTD, IF_SD, IF_VIRTIO, IF_XEN,
    IF_COUNT
} BlockInterfaceType;

typedef struct DriveInfo {
    BlockDriverState *bdrv;
    char *id;
    const char *devaddr;
    BlockInterfaceType type;
    int bus;
    int unit;
    int auto_del;               /* see blockdev_mark_auto_del() */
    QemuOpts *opts;
    char serial[BLOCK_SERIAL_STRLEN + 1];
    QTAILQ_ENTRY(DriveInfo) next;
    int opened;
    int bdrv_flags;
    char *file;
    BlockDriver *drv;
    int refcount;
} DriveInfo;

extern QTAILQ_HEAD(drivelist, DriveInfo) drives;
extern DriveInfo *extboot_drive;

extern DriveInfo *drive_get(BlockInterfaceType type, int bus, int unit);
extern DriveInfo *drive_get_by_id(const char *id);
DriveInfo *drive_get_by_index(BlockInterfaceType type, int index);
extern int drive_get_max_bus(BlockInterfaceType type);
extern DriveInfo *drive_get_by_blockdev(BlockDriverState *bs);
extern const char *drive_get_serial(BlockDriverState *bdrv);
void drive_get_ref(DriveInfo *dinfo);
void drive_put_ref(DriveInfo *dinfo);

QemuOpts *drive_def(const char *optstr);
QemuOpts *drive_add(BlockInterfaceType type, int index, const char *file,
                    const char *optstr);
DriveInfo *drive_init(QemuOpts *arg, int default_to_scsi);

extern int drives_reopen(void);

/* device-hotplug */

DriveInfo *add_init_drive(const char *opts);

void do_commit(Monitor *mon, const QDict *qdict);
int do_eject(Monitor *mon, const QDict *qdict, QObject **ret_data);
int do_block_set_passwd(Monitor *mon, const QDict *qdict, QObject **ret_data);
int do_change_block(Monitor *mon, const char *device,
                    const char *filename, const char *fmt);
int simple_drive_add(Monitor *mon, const QDict *qdict, QObject **ret_data);
int do_drive_del(Monitor *mon, const QDict *qdict, QObject **ret_data);
int do_block_stream(Monitor *mon, const QDict *qdict, QObject **ret_data);
int do_block_job_set_speed(Monitor *mon, const QDict *params,
                           QObject **ret_data);
int do_block_job_cancel(Monitor *mon, const QDict *params, QObject **ret_data);
void monitor_print_block_jobs(Monitor *mon, const QObject *data);
void do_info_block_jobs(Monitor *mon, QObject **ret_data);

#endif
