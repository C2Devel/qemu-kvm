/*
 * Human Monitor Interface
 *
 * Copyright IBM, Corp. 2011
 *
 * Authors:
 *  Anthony Liguori   <aliguori@us.ibm.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2.  See
 * the COPYING file in the top-level directory.
 *
 */

#ifndef HMP_H
#define HMP_H

#include "qemu-common.h"
#include "qdict.h"

#ifdef CONFIG_LIVE_SNAPSHOTS
#include "rhev-qapi-types.h"

void hmp_snapshot_blkdev(Monitor *mon, const QDict *qdict);
void hmp_drive_mirror(Monitor *mon, const QDict *qdict);
void hmp_drive_reopen(Monitor *mon, const QDict *qdict);
#endif

void hmp_dump_guest_memory(Monitor *mon, const QDict *qdict);

#endif
