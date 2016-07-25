/*
 * Null block driver
 *
 * Authors:
 *  Fam Zheng <famz@redhat.com>
 *
 * Copyright (C) 2014 Red Hat, Inc.
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 */

#include "qemu-common.h"
#include "block_int.h"
#include "module.h"

static int null_file_open(BlockDriverState *bs, const char *filename, int flags)
{
    return 0;
}

/* We have nothing to do for null reopen, stubs just return
 * success */
static int null_reopen_prepare(BDRVReopenState *state,
                              BlockReopenQueue *queue,  Error **errp)
{
    return 0;
}

static int coroutine_fn null_co_readv(BlockDriverState *bs, int64_t sector_num,
                                     int nb_sectors, QEMUIOVector *qiov)
{
    return 0;
}

static int coroutine_fn null_co_writev(BlockDriverState *bs, int64_t sector_num,
                                      int nb_sectors, QEMUIOVector *qiov)
{
    return 0;
}

static void null_close(BlockDriverState *bs)
{
}

static int64_t null_getlength(BlockDriverState *bs)
{
    return 8ULL * 1024 * 1024 * 1024;
}

static BlockDriver bdrv_null = {
    .format_name          = "null",
    .protocol_name        = "null",

    /* It's really 0, but we need to make g_malloc() happy */
    .instance_size        = 1,

    .bdrv_file_open       = null_file_open,
    .bdrv_close           = null_close,
    .bdrv_reopen_prepare  = null_reopen_prepare,

    .bdrv_co_readv        = null_co_readv,
    .bdrv_co_writev       = null_co_writev,

    .bdrv_getlength       = null_getlength,
};

static void bdrv_null_init(void)
{
    bdrv_register(&bdrv_null);
}

block_init(bdrv_null_init);
