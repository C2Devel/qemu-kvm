/*
 * Image mirroring
 *
 * Copyright Red Hat, Inc. 2012
 *
 * Authors:
 *  Paolo Bonzini  <pbonzini@redhat.com>
 *
 * This work is licensed under the terms of the GNU LGPL, version 2 or later.
 * See the COPYING.LIB file in the top-level directory.
 *
 */

#include "trace.h"
#include "block_int.h"

enum {
    /*
     * Size of data buffer for populating the image file.  This should be large
     * enough to process multiple clusters in a single call, so that populating
     * contiguous regions of the image is efficient.
     */
    BLOCK_SIZE = 512 * BDRV_SECTORS_PER_DIRTY_CHUNK, /* in bytes */
};

#define SLICE_TIME 100ULL /* ms */

typedef struct {
    int64_t next_slice_time;
    uint64_t slice_quota;
    uint64_t dispatched;
} RateLimit;

static int64_t ratelimit_calculate_delay(RateLimit *limit, uint64_t n)
{
    int64_t delay_ms = 0;
    int64_t now = qemu_get_clock(rt_clock);

    if (limit->next_slice_time < now) {
        limit->next_slice_time = now + SLICE_TIME;
        limit->dispatched = 0;
    }
    if (limit->dispatched + n > limit->slice_quota) {
        delay_ms = limit->next_slice_time - now;
    } else {
        limit->dispatched += n;
    }
    return MAX(0, delay_ms);
}

static void ratelimit_set_speed(RateLimit *limit, uint64_t speed)
{
    limit->slice_quota = speed / (1000ULL / SLICE_TIME);
}

typedef struct MirrorBlockJob {
    BlockJob common;
    RateLimit limit;
    BlockDriverState *target;
    bool full;
} MirrorBlockJob;

static int coroutine_fn mirror_populate(BlockDriverState *source,
                                        BlockDriverState *target,
                                        int64_t sector_num, int nb_sectors,
                                        void *buf)
{
    struct iovec iov = {
        .iov_base = buf,
        .iov_len  = nb_sectors * 512,
    };
    QEMUIOVector qiov;
    int ret;

    qemu_iovec_init_external(&qiov, &iov, 1);

    /* Copy-on-read the unallocated clusters */
    ret = bdrv_co_readv(source, sector_num, nb_sectors, &qiov);
    if (ret < 0) {
        return ret;
    }
    return bdrv_co_writev(target, sector_num, nb_sectors, &qiov);
}

static int is_any_allocated(BlockDriverState *bs, int64_t sector_num,
                            int nb_sectors, int *pnum)
{
    BlockDriverState *intermediate;
    int ret, n, unalloc = nb_sectors;

    intermediate = bs;
    while (intermediate) {
        ret = bdrv_co_is_allocated(intermediate, sector_num, nb_sectors,
                                   &n);
        if (ret < 0) {
            return ret;
        } else if (ret) {
            break;
        } else {
            unalloc = MIN(unalloc, n);
        }

        intermediate = intermediate->backing_hd;
    }

    *pnum = ret ? n : unalloc;
    return ret;
}

static void coroutine_fn mirror_run(void *opaque)
{
    MirrorBlockJob *s = opaque;
    BlockDriverState *bs = s->common.bs;
    int64_t sector_num, end;
    int ret = 0;
    int n;
    bool synced = false;
    void *buf;

    if (block_job_is_cancelled(&s->common)) {
        goto immediate_exit;
    }

    s->common.len = bdrv_getlength(bs);
    if (s->common.len < 0) {
        block_job_complete(&s->common, s->common.len);
        return;
    }

    end = s->common.len >> BDRV_SECTOR_BITS;
    buf = qemu_blockalign(bs, BLOCK_SIZE);

    /* First part, loop on the sectors and initialize the dirty bitmap.  */
    for (sector_num = 0; sector_num < end; ) {
        int64_t next = (sector_num | (BDRV_SECTORS_PER_DIRTY_CHUNK - 1)) + 1;
        if (s->full) {
            ret = is_any_allocated(bs, sector_num, next - sector_num, &n);
        } else {
            ret = bdrv_co_is_allocated(bs, sector_num, next - sector_num, &n);
        }
        if (ret < 0) {
            break;
        }

        if (ret == 1) {
            bdrv_set_dirty(bs, sector_num, n);
            sector_num = next;
        } else {
            sector_num += n;
        }
    }

    if (ret < 0) {
        block_job_complete(&s->common, ret);
    }

    sector_num = -1;
    for (;;) {
        uint64_t delay_ms;
        int64_t cnt;

        if (bdrv_get_dirty_count(bs) == 0) {
            /* Switch out of the streaming phase.  From now on, if the
             * job is cancelled we will actually complete all pending
             * I/O and report completion, so that drive-reopen can be
             * used to pivot to the mirroring target.
             */
            synced = true;
            s->common.offset = end * BDRV_SECTOR_SIZE;
        }

        if (bdrv_get_dirty_count(bs) != 0) {
            int nb_sectors;
            sector_num = bdrv_get_next_dirty(bs, sector_num);
            nb_sectors = MIN(BDRV_SECTORS_PER_DIRTY_CHUNK, end - sector_num);
            trace_mirror_one_iteration(s, sector_num);
            bdrv_reset_dirty(bs, sector_num, BDRV_SECTORS_PER_DIRTY_CHUNK);
            ret = mirror_populate(bs, s->target, sector_num, nb_sectors, buf);
            if (ret < 0) {
                break;
            }
        }

        if (synced && block_job_is_cancelled(&s->common)) {
            /* The dirty bitmap is not updated while operations are pending.
             * If we're about to exit, wait for pending operations before
             * calling bdrv_get_dirty_count(bs), or we may exit while the
             * source has dirty data to copy!
             *
             * Note that I/O can be submitted by the guest while
             * mirror_populate runs.
             */
            bdrv_drain_all();
        }

        ret = 0;
        cnt = bdrv_get_dirty_count(bs);
        if (synced) {
            if (!block_job_is_cancelled(&s->common)) {
                delay_ms = (cnt == 0 ? SLICE_TIME : 0);
                block_job_sleep(&s->common, rt_clock, delay_ms);
            } else if (cnt == 0) {
                /* The two disks are in sync.  Exit and report successful
                 * completion.
                 */
                assert(QLIST_EMPTY(&bs->tracked_requests));
                s->common.cancelled = false;
                break;
            }

            /* We get here either to poll the target, or because the job
             * was cancelled.  In the latter case, we still have an
             * opportunity to do I/O (without going to sleep) before
             * exiting.
             */
        } else {
            /* Publish progress */
            s->common.offset = end * BDRV_SECTOR_SIZE - cnt * BLOCK_SIZE;

            if (s->common.speed) {
                delay_ms = ratelimit_calculate_delay(&s->limit, BDRV_SECTORS_PER_DIRTY_CHUNK);
            } else {
                delay_ms = 0;
            }

            /* Note that even when no rate limit is applied we need to yield
             * with no pending I/O here so that qemu_aio_flush() returns.
             */
            block_job_sleep(&s->common, rt_clock, delay_ms);
            if (block_job_is_cancelled(&s->common)) {
                break;
            }
        }
    }

immediate_exit:
    bdrv_set_dirty_tracking(bs, false);
    bdrv_close(s->target);
    bdrv_delete(s->target);
    block_job_complete(&s->common, ret);
}

static int mirror_set_speed(BlockJob *job, int64_t value)
{
    MirrorBlockJob *s = container_of(job, MirrorBlockJob, common);

    if (value < 0) {
        return -EINVAL;
    }
    ratelimit_set_speed(&s->limit, value / BDRV_SECTOR_SIZE);
    return 0;
}

static BlockJobType mirror_job_type = {
    .instance_size = sizeof(MirrorBlockJob),
    .job_type      = "mirror",
    .set_speed     = mirror_set_speed,
};

int mirror_start(BlockDriverState *bs,
                 const char *target, BlockDriver *drv, int flags,
                 int64_t speed, BlockDriverCompletionFunc *cb,
                 void *opaque, bool full)
{
    MirrorBlockJob *s;
    int ret;

    s = block_job_create(&mirror_job_type, bs, speed, cb, opaque);
    if (!s) {
        return -EBUSY; /* bs must already be in use */
    }

    s->target = bdrv_new("");
    ret = bdrv_open(s->target, target,
                    flags | BDRV_O_NO_BACKING | BDRV_O_NO_FLUSH | BDRV_O_CACHE_WB,
                    drv);

    if (ret < 0) {
        bdrv_delete(s->target);
        return ret;
    }

    s->full = full;
    bdrv_set_dirty_tracking(bs, true);
    s->common.co = qemu_coroutine_create(mirror_run);
    trace_mirror_start(bs, s, s->common.co, opaque);
    return 0;
}

void mirror_abort(BlockDriverState *bs)
{
    if (bs->job) {
        MirrorBlockJob *s = container_of(bs->job, MirrorBlockJob, common);
        block_job_cancel(&s->common);
        qemu_coroutine_enter(s->common.co, s);
    }
}

void mirror_commit(BlockDriverState *bs)
{
    MirrorBlockJob *s = container_of(bs->job, MirrorBlockJob, common);

    assert(s->common.bs == bs);
    qemu_coroutine_enter(s->common.co, s);
}
