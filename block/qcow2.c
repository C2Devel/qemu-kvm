/*
 * Block driver for the QCOW version 2 format
 *
 * Copyright (c) 2004-2006 Fabrice Bellard
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
#include "qemu-common.h"
#include "block_int.h"
#include "module.h"
#include <zlib.h>
#include "aes.h"
#include "block/qcow2.h"
#include "qemu-error.h"
#include "qerror.h"
#include "qapi/util.h"
#include "qapi-visit.h"
#include "qemu-objects.h"
#include "monitor.h"

/*
  Differences with QCOW:

  - Support for multiple incremental snapshots.
  - Memory management by reference counts.
  - Clusters which have a reference count of one have the bit
    QCOW_OFLAG_COPIED to optimize write performance.
  - Size of compressed clusters is stored in sectors to reduce bit usage
    in the cluster offsets.
  - Support for storing additional data (such as the VM state) in the
    snapshots.
  - If a backing store is used, the cluster size is not constrained
    (could be backported to QCOW).
  - L2 tables have always a size of one cluster.
*/


typedef struct {
    uint32_t magic;
    uint32_t len;
} QCowExtension;

#define  QCOW2_EXT_MAGIC_END 0
#define  QCOW2_EXT_MAGIC_BACKING_FORMAT 0xE2792ACA

static BlockDriver bdrv_qcow2;

static int qcow2_probe(const uint8_t *buf, int buf_size, const char *filename)
{
    const QCowHeader *cow_header = (const void *)buf;

    if (buf_size >= sizeof(QCowHeader) &&
        be32_to_cpu(cow_header->magic) == QCOW_MAGIC &&
        be32_to_cpu(cow_header->version) >= QCOW_VERSION)
        return 100;
    else
        return 0;
}


/* 
 * read qcow2 extension and fill bs
 * start reading from start_offset
 * finish reading upon magic of value 0 or when end_offset reached
 * unknown magic is skipped (future extension this version knows nothing about)
 * return 0 upon success, non-0 otherwise
 */
static int qcow2_read_extensions(BlockDriverState *bs, uint64_t start_offset,
                                 uint64_t end_offset)
{
    BDRVQcowState *s = bs->opaque;
    QCowExtension ext;
    uint64_t offset;
    int ret;

#ifdef DEBUG_EXT
    printf("qcow2_read_extensions: start=%ld end=%ld\n", start_offset, end_offset);
#endif
    offset = start_offset;
    while (offset < end_offset) {

#ifdef DEBUG_EXT
        /* Sanity check */
        if (offset > s->cluster_size)
            printf("qcow2_read_extension: suspicious offset %lu\n", offset);

        printf("attemting to read extended header in offset %lu\n", offset);
#endif

        if (bdrv_pread(bs->file, offset, &ext, sizeof(ext)) != sizeof(ext)) {
            fprintf(stderr, "qcow2_handle_extension: ERROR: "
                    "pread fail from offset %" PRIu64 "\n",
                    offset);
            return 1;
        }
        be32_to_cpus(&ext.magic);
        be32_to_cpus(&ext.len);
        offset += sizeof(ext);
#ifdef DEBUG_EXT
        printf("ext.magic = 0x%x\n", ext.magic);
#endif
        if (offset > end_offset || ext.len > end_offset - offset) {
            error_report("Header extension too large");
            return -EINVAL;
        }

        switch (ext.magic) {
        case QCOW2_EXT_MAGIC_END:
            return 0;

        case QCOW2_EXT_MAGIC_BACKING_FORMAT:
            if (ext.len >= sizeof(bs->backing_format)) {
                fprintf(stderr, "ERROR: ext_backing_format: len=%u too large"
                        " (>=%zu)\n",
                        ext.len, sizeof(bs->backing_format));
                return 2;
            }
            if (bdrv_pread(bs->file, offset , bs->backing_format,
                           ext.len) != ext.len)
                return 3;
            bs->backing_format[ext.len] = '\0';
#ifdef DEBUG_EXT
            printf("Qcow2: Got format extension %s\n", bs->backing_format);
#endif
            offset = ((offset + ext.len + 7) & ~7);
            break;

        default:
            /* unknown magic - save it in case we need to rewrite the header */
            {
                Qcow2UnknownHeaderExtension *uext;

                uext = g_malloc0(sizeof(*uext)  + ext.len);
                uext->magic = ext.magic;
                uext->len = ext.len;
                QLIST_INSERT_HEAD(&s->unknown_header_ext, uext, next);

                ret = bdrv_pread(bs->file, offset , uext->data, uext->len);
                if (ret < 0) {
                    return ret;
                }

                offset = ((offset + ext.len + 7) & ~7);
            }
            break;
        }
    }

    return 0;
}

static void cleanup_unknown_header_ext(BlockDriverState *bs)
{
    BDRVQcowState *s = bs->opaque;
    Qcow2UnknownHeaderExtension *uext, *next;

    QLIST_FOREACH_SAFE(uext, &s->unknown_header_ext, next, next) {
        QLIST_REMOVE(uext, next);
        g_free(uext);
    }
}

static int validate_table_offset(BlockDriverState *bs, uint64_t offset,
                                 uint64_t entries, size_t entry_len)
{
    BDRVQcowState *s = bs->opaque;
    uint64_t size;

    /* Use signed INT64_MAX as the maximum even for uint64_t header fields,
     * because values will be passed to qemu functions taking int64_t. */
    if (entries > INT64_MAX / entry_len) {
        return -EINVAL;
    }

    size = entries * entry_len;

    if (INT64_MAX - size < offset) {
        return -EINVAL;
    }

    /* Tables must be cluster aligned */
    if (offset & (s->cluster_size - 1)) {
        return -EINVAL;
    }

    return 0;
}

static int qcow2_open(BlockDriverState *bs, int flags)
{
    BDRVQcowState *s = bs->opaque;
    unsigned int len, i;
    int ret = 0;
    QCowHeader header;
    uint64_t ext_end;
    bool writethrough;
    uint64_t l1_vm_state_index;

    ret = bdrv_pread(bs->file, 0, &header, sizeof(header));
    if (ret < 0) {
        goto fail;
    }
    be32_to_cpus(&header.magic);
    be32_to_cpus(&header.version);
    be64_to_cpus(&header.backing_file_offset);
    be32_to_cpus(&header.backing_file_size);
    be64_to_cpus(&header.size);
    be32_to_cpus(&header.cluster_bits);
    be32_to_cpus(&header.crypt_method);
    be64_to_cpus(&header.l1_table_offset);
    be32_to_cpus(&header.l1_size);
    be64_to_cpus(&header.refcount_table_offset);
    be32_to_cpus(&header.refcount_table_clusters);
    be64_to_cpus(&header.snapshots_offset);
    be32_to_cpus(&header.nb_snapshots);

    if (header.magic != QCOW_MAGIC) {
        ret = -EINVAL;
        goto fail;
    }
    if (header.version != QCOW_VERSION) {
        char version[64];
        snprintf(version, sizeof(version), "QCOW version %d", header.version);
        qerror_report(QERR_UNKNOWN_BLOCK_FORMAT_FEATURE,
            bs->device_name, "qcow2", version);
        ret = -ENOTSUP;
        goto fail;
    }
    if (header.cluster_bits < MIN_CLUSTER_BITS ||
        header.cluster_bits > MAX_CLUSTER_BITS) {
        ret = -EINVAL;
        goto fail;
    }
    if (header.crypt_method > QCOW_CRYPT_AES) {
        ret = -EINVAL;
        goto fail;
    }
    s->crypt_method_header = header.crypt_method;
    if (s->crypt_method_header) {
        bs->encrypted = 1;
    }
    s->cluster_bits = header.cluster_bits;
    s->cluster_size = 1 << s->cluster_bits;
    s->cluster_sectors = 1 << (s->cluster_bits - 9);
    s->l2_bits = s->cluster_bits - 3; /* L2 is always one cluster */
    s->l2_size = 1 << s->l2_bits;
    /* 2^(refcount_order - 3) is the refcount width in bytes
     * (and refcount_order == 4) */
    s->refcount_block_bits = s->cluster_bits - (4 - 3);
    s->refcount_block_size = 1 << s->refcount_block_bits;
    bs->total_sectors = header.size / 512;
    s->csize_shift = (62 - (s->cluster_bits - 8));
    s->csize_mask = (1 << (s->cluster_bits - 8)) - 1;
    s->cluster_offset_mask = (1LL << s->csize_shift) - 1;

    s->refcount_table_offset = header.refcount_table_offset;
    s->refcount_table_size =
        header.refcount_table_clusters << (s->cluster_bits - 3);

    if (header.refcount_table_clusters > qcow2_max_refcount_clusters(s)) {
        qerror_report(QERR_GENERIC_ERROR, "Reference count table too large");
        ret = -EINVAL;
        goto fail;
    }

    ret = validate_table_offset(bs, s->refcount_table_offset,
                                s->refcount_table_size, sizeof(uint64_t));
    if (ret < 0) {
         qerror_report(QERR_GENERIC_ERROR,
                      "Invalid reference count table offset");
        goto fail;
    }

    /* Snapshot table offset/length */
    if (header.nb_snapshots > QCOW_MAX_SNAPSHOTS) {
        qerror_report(QERR_GENERIC_ERROR, "Too many snapshots");
        ret = -EINVAL;
        goto fail;
    }

    ret = validate_table_offset(bs, header.snapshots_offset,
                                header.nb_snapshots,
                                sizeof(QCowSnapshotHeader));
    if (ret < 0) {
        qerror_report(QERR_GENERIC_ERROR, "Invalid snapshot table offset");
        goto fail;
    }

    /* read the level 1 table */
    if (header.l1_size > 0x2000000) {
        /* 32 MB L1 table is enough for 2 PB images at 64k cluster size
         * (128 GB for 512 byte clusters, 2 EB for 2 MB clusters) */
        qerror_report(QERR_GENERIC_ERROR, "Active L1 table too large");
        ret = -EFBIG;
        goto fail;
    }
    s->l1_size = header.l1_size;

    l1_vm_state_index = size_to_l1(s, header.size);
    if (l1_vm_state_index > INT_MAX) {
        ret = -EFBIG;
        goto fail;
    }
    s->l1_vm_state_index = l1_vm_state_index;

    /* the L1 table must contain at least enough entries to put
       header.size bytes */
    if (s->l1_size < s->l1_vm_state_index) {
        ret = -EINVAL;
        goto fail;
    }

    ret = validate_table_offset(bs, header.l1_table_offset,
                                header.l1_size, sizeof(uint64_t));
    if (ret < 0) {
        qerror_report(QERR_GENERIC_ERROR, "Invalid L1 table offset");
        goto fail;
    }
    s->l1_table_offset = header.l1_table_offset;


    if (s->l1_size > 0) {
        s->l1_table = g_malloc0(
            align_offset(s->l1_size * sizeof(uint64_t), 512));
        ret = bdrv_pread(bs->file, s->l1_table_offset, s->l1_table,
                         s->l1_size * sizeof(uint64_t));
        if (ret < 0) {
            goto fail;
        }
        for(i = 0;i < s->l1_size; i++) {
            be64_to_cpus(&s->l1_table[i]);
        }
    }

    /* alloc L2 table/refcount block cache */
    writethrough = ((flags & BDRV_O_CACHE_WB) == 0);
    s->l2_table_cache = qcow2_cache_create(bs, L2_CACHE_SIZE, writethrough);
    s->refcount_block_cache = qcow2_cache_create(bs, REFCOUNT_CACHE_SIZE,
        writethrough);

    s->cluster_cache = g_malloc(s->cluster_size);
    /* one more sector for decompressed data alignment */
    s->cluster_data = g_malloc(QCOW_MAX_CRYPT_CLUSTERS * s->cluster_size
                                  + 512);
    s->cluster_cache_offset = -1;

    ret = qcow2_refcount_init(bs);
    if (ret != 0) {
        goto fail;
    }

    QLIST_INIT(&s->cluster_allocs);

    /* read qcow2 extensions */
    if (header.backing_file_offset > s->cluster_size) {
        qerror_report(QERR_GENERIC_ERROR, "Invalid backing file offset");
        ret = -EINVAL;
        goto fail;
    }

    if (header.backing_file_offset) {
        ext_end = header.backing_file_offset;
    } else {
        ext_end = s->cluster_size;
    }
    if (qcow2_read_extensions(bs, sizeof(header), ext_end)) {
        ret = -EINVAL;
        goto fail;
    }

    /* read the backing file name */
    if (header.backing_file_offset != 0) {
        len = header.backing_file_size;
        if (len > MIN(1023, s->cluster_size - header.backing_file_offset)) {
            qerror_report(QERR_GENERIC_ERROR, "Backing file name too long");
            ret = -EINVAL;
            goto fail;
        }
        ret = bdrv_pread(bs->file, header.backing_file_offset,
                         bs->backing_file, len);
        if (ret < 0) {
            goto fail;
        }
        bs->backing_file[len] = '\0';
    }

    /* Internal snapshots */
    s->snapshots_offset = header.snapshots_offset;
    s->nb_snapshots = header.nb_snapshots;

    ret = qcow2_read_snapshots(bs);
    if (ret < 0) {
        goto fail;
    }

    /* Initialise locks */
    qemu_co_mutex_init(&s->lock);

    s->overlap_check = QCOW2_OL_CACHED;

#ifdef DEBUG_ALLOC
    qcow2_check_refcounts(bs);
#endif
    return ret;

 fail:
    cleanup_unknown_header_ext(bs);
    qcow2_free_snapshots(bs);
    qcow2_refcount_close(bs);
    g_free(s->l1_table);
    /* else pre-write overlap checks in cache_destroy may crash */
    s->l1_table = NULL;
    if (s->l2_table_cache) {
        qcow2_cache_destroy(bs, s->l2_table_cache);
    }
    g_free(s->cluster_cache);
    g_free(s->cluster_data);
    return ret;
}

static int qcow2_set_key(BlockDriverState *bs, const char *key)
{
    BDRVQcowState *s = bs->opaque;
    uint8_t keybuf[16];
    int len, i;

    memset(keybuf, 0, 16);
    len = strlen(key);
    if (len > 16)
        len = 16;
    /* XXX: we could compress the chars to 7 bits to increase
       entropy */
    for(i = 0;i < len;i++) {
        keybuf[i] = key[i];
    }
    s->crypt_method = s->crypt_method_header;

    if (AES_set_encrypt_key(keybuf, 128, &s->aes_encrypt_key) != 0)
        return -1;
    if (AES_set_decrypt_key(keybuf, 128, &s->aes_decrypt_key) != 0)
        return -1;
#if 0
    /* test */
    {
        uint8_t in[16];
        uint8_t out[16];
        uint8_t tmp[16];
        for(i=0;i<16;i++)
            in[i] = i;
        AES_encrypt(in, tmp, &s->aes_encrypt_key);
        AES_decrypt(tmp, out, &s->aes_decrypt_key);
        for(i = 0; i < 16; i++)
            printf(" %02x", tmp[i]);
        printf("\n");
        for(i = 0; i < 16; i++)
            printf(" %02x", out[i]);
        printf("\n");
    }
#endif
    return 0;
}

/* We have nothing to do for QCOW2 reopen, stubs just return
 * success */
static int qcow2_reopen_prepare(BDRVReopenState *state,
                                BlockReopenQueue *queue, Error **errp)
{
    return 0;
}

static int64_t coroutine_fn qcow2_co_get_block_status(BlockDriverState *bs,
        int64_t sector_num, int nb_sectors, int *pnum)
{
    BDRVQcowState *s = bs->opaque;
    uint64_t cluster_offset;
    int index_in_cluster, ret;
    int64_t status = 0;

    *pnum = nb_sectors;
    qemu_co_mutex_lock(&s->lock);
    ret = qcow2_get_cluster_offset(bs, sector_num << 9, pnum, &cluster_offset);
    qemu_co_mutex_unlock(&s->lock);
    if (ret < 0) {
        return ret;
    }

    if (cluster_offset != 0 && ret != QCOW2_CLUSTER_COMPRESSED &&
        !s->crypt_method) {
        index_in_cluster = sector_num & (s->cluster_sectors - 1);
        cluster_offset |= (index_in_cluster << BDRV_SECTOR_BITS);
        status |= BDRV_BLOCK_OFFSET_VALID | cluster_offset;
    }
    if (ret != QCOW2_CLUSTER_UNALLOCATED) {
        status |= BDRV_BLOCK_DATA;
    }
    return status;
}

/* handle reading after the end of the backing file */
int qcow2_backing_read1(BlockDriverState *bs, QEMUIOVector *qiov,
                  int64_t sector_num, int nb_sectors)
{
    int n1;
    if ((sector_num + nb_sectors) <= bs->total_sectors)
        return nb_sectors;
    if (sector_num >= bs->total_sectors)
        n1 = 0;
    else
        n1 = bs->total_sectors - sector_num;

    qemu_iovec_memset_skip(qiov, 0, 512 * (nb_sectors - n1), 512 * n1);

    return n1;
}

static int qcow2_co_readv(BlockDriverState *bs, int64_t sector_num,
                          int remaining_sectors, QEMUIOVector *qiov)
{
    BDRVQcowState *s = bs->opaque;
    int index_in_cluster, n1;
    int ret;
    int cur_nr_sectors; /* number of sectors in current iteration */
    uint64_t cluster_offset = 0;
    uint64_t bytes_done = 0;
    QEMUIOVector hd_qiov;
    uint8_t *cluster_data = NULL;

    qemu_iovec_init(&hd_qiov, qiov->niov);

    qemu_co_mutex_lock(&s->lock);

    while (remaining_sectors != 0) {

        /* prepare next request */
        cur_nr_sectors = remaining_sectors;
        if (s->crypt_method) {
            cur_nr_sectors = MIN(cur_nr_sectors,
                QCOW_MAX_CRYPT_CLUSTERS * s->cluster_sectors);
        }

        ret = qcow2_get_cluster_offset(bs, sector_num << 9,
            &cur_nr_sectors, &cluster_offset);
        if (ret < 0) {
            goto fail;
        }

        index_in_cluster = sector_num & (s->cluster_sectors - 1);

        qemu_iovec_reset(&hd_qiov);
        qemu_iovec_copy(&hd_qiov, qiov, bytes_done,
            cur_nr_sectors * 512);

        switch (ret) {
        case QCOW2_CLUSTER_UNALLOCATED:

            if (bs->backing_hd) {
                /* read from the base image */
                n1 = qcow2_backing_read1(bs->backing_hd, &hd_qiov,
                    sector_num, cur_nr_sectors);
                if (n1 > 0) {
                    BLKDBG_EVENT(bs->file, BLKDBG_READ_BACKING_AIO);
                    qemu_co_mutex_unlock(&s->lock);
                    ret = bdrv_co_readv(bs->backing_hd, sector_num,
                                        n1, &hd_qiov);
                    qemu_co_mutex_lock(&s->lock);
                    if (ret < 0) {
                        goto fail;
                    }
                }
            } else {
                /* Note: in this case, no need to wait */
                qemu_iovec_memset(&hd_qiov, 0, 512 * cur_nr_sectors);
            }
            break;

        case QCOW2_CLUSTER_COMPRESSED:
            /* add AIO support for compressed blocks ? */
            ret = qcow2_decompress_cluster(bs, cluster_offset);
            if (ret < 0) {
                goto fail;
            }

            qemu_iovec_from_buffer(&hd_qiov,
                s->cluster_cache + index_in_cluster * 512,
                512 * cur_nr_sectors);
            break;

        case QCOW2_CLUSTER_NORMAL:
            if ((cluster_offset & 511) != 0) {
                ret = -EIO;
                goto fail;
            }

            if (s->crypt_method) {
                /*
                 * For encrypted images, read everything into a temporary
                 * contiguous buffer on which the AES functions can work.
                 */
                if (!cluster_data) {
                    cluster_data =
                        g_malloc0(QCOW_MAX_CRYPT_CLUSTERS * s->cluster_size);
                }

                assert(cur_nr_sectors <=
                    QCOW_MAX_CRYPT_CLUSTERS * s->cluster_sectors);
                qemu_iovec_reset(&hd_qiov);
                qemu_iovec_add(&hd_qiov, cluster_data,
                    512 * cur_nr_sectors);
            }

            BLKDBG_EVENT(bs->file, BLKDBG_READ_AIO);
            qemu_co_mutex_unlock(&s->lock);
            ret = bdrv_co_readv(bs->file,
                                (cluster_offset >> 9) + index_in_cluster,
                                cur_nr_sectors, &hd_qiov);
            qemu_co_mutex_lock(&s->lock);
            if (ret < 0) {
                goto fail;
            }
            if (s->crypt_method) {
                qcow2_encrypt_sectors(s, sector_num,  cluster_data,
                    cluster_data, cur_nr_sectors, 0, &s->aes_decrypt_key);
                qemu_iovec_reset(&hd_qiov);
                qemu_iovec_copy(&hd_qiov, qiov, bytes_done,
                    cur_nr_sectors * 512);
                qemu_iovec_from_buffer(&hd_qiov, cluster_data,
                    512 * cur_nr_sectors);
            }
            break;

        default:
            g_assert_not_reached();
            ret = -EIO;
            goto fail;
        }

        remaining_sectors -= cur_nr_sectors;
        sector_num += cur_nr_sectors;
        bytes_done += cur_nr_sectors * 512;
    }
    ret = 0;

fail:
    qemu_co_mutex_unlock(&s->lock);

    qemu_iovec_destroy(&hd_qiov);
    g_free(cluster_data);

    return ret;
}

static void run_dependent_requests(BDRVQcowState *s, QCowL2Meta *m)
{
    /* Take the request off the list of running requests */
    if (m->nb_clusters != 0) {
        QLIST_REMOVE(m, next_in_flight);
    }

    /* Restart all dependent requests */
    if (!qemu_co_queue_empty(&m->dependent_requests)) {
        qemu_co_mutex_unlock(&s->lock);
        qemu_co_queue_restart_all(&m->dependent_requests);
        qemu_co_mutex_lock(&s->lock);
    }
}

static int qcow2_co_writev(BlockDriverState *bs,
                           int64_t sector_num,
                           int remaining_sectors,
                           QEMUIOVector *qiov)
{
    BDRVQcowState *s = bs->opaque;
    int index_in_cluster;
    int n_end;
    int ret;
    int cur_nr_sectors; /* number of sectors in current iteration */
    uint64_t cluster_offset;
    QEMUIOVector hd_qiov;
    uint64_t bytes_done = 0;
    uint8_t *cluster_data = NULL;
    QCowL2Meta l2meta = {
        .nb_clusters = 0,
    };

    qemu_co_queue_init(&l2meta.dependent_requests);

    qemu_iovec_init(&hd_qiov, qiov->niov);

    s->cluster_cache_offset = -1; /* disable compressed cache */

    qemu_co_mutex_lock(&s->lock);

    while (remaining_sectors != 0) {

        index_in_cluster = sector_num & (s->cluster_sectors - 1);
        n_end = index_in_cluster + remaining_sectors;
        if (s->crypt_method &&
            n_end > QCOW_MAX_CRYPT_CLUSTERS * s->cluster_sectors) {
            n_end = QCOW_MAX_CRYPT_CLUSTERS * s->cluster_sectors;
        }

        ret = qcow2_alloc_cluster_offset(bs, sector_num << 9,
            index_in_cluster, n_end, &cur_nr_sectors, &l2meta);
        if (ret < 0) {
            goto fail;
        }

        cluster_offset = l2meta.cluster_offset;
        assert((cluster_offset & 511) == 0);

        qemu_iovec_reset(&hd_qiov);
        qemu_iovec_copy(&hd_qiov, qiov, bytes_done,
            cur_nr_sectors * 512);

        if (s->crypt_method) {
            if (!cluster_data) {
                cluster_data = g_malloc0(QCOW_MAX_CRYPT_CLUSTERS *
                                                 s->cluster_size);
            }

            assert(hd_qiov.size <=
                   QCOW_MAX_CRYPT_CLUSTERS * s->cluster_size);
            qemu_iovec_to_buffer(&hd_qiov, cluster_data);

            qcow2_encrypt_sectors(s, sector_num, cluster_data,
                cluster_data, cur_nr_sectors, 1, &s->aes_encrypt_key);

            qemu_iovec_reset(&hd_qiov);
            qemu_iovec_add(&hd_qiov, cluster_data,
                cur_nr_sectors * 512);
        }

        ret = qcow2_pre_write_overlap_check(bs, 0,
                cluster_offset + index_in_cluster * BDRV_SECTOR_SIZE,
                cur_nr_sectors * BDRV_SECTOR_SIZE);
        if (ret < 0) {
            goto fail;
        }

        BLKDBG_EVENT(bs->file, BLKDBG_WRITE_AIO);
        qemu_co_mutex_unlock(&s->lock);
        ret = bdrv_co_writev(bs->file,
                             (cluster_offset >> 9) + index_in_cluster,
                             cur_nr_sectors, &hd_qiov);
        qemu_co_mutex_lock(&s->lock);
        if (ret < 0) {
            goto fail;
        }

        ret = qcow2_alloc_cluster_link_l2(bs, &l2meta);
        if (ret < 0) {
            goto fail;
        }

        run_dependent_requests(s, &l2meta);

        remaining_sectors -= cur_nr_sectors;
        sector_num += cur_nr_sectors;
        bytes_done += cur_nr_sectors * 512;
    }
    ret = 0;

fail:
    run_dependent_requests(s, &l2meta);

    qemu_co_mutex_unlock(&s->lock);

    qemu_iovec_destroy(&hd_qiov);
    g_free(cluster_data);

    return ret;
}

static void qcow2_close(BlockDriverState *bs)
{
    BDRVQcowState *s = bs->opaque;
    g_free(s->l1_table);
    /* else pre-write overlap checks in cache_destroy may crash */
    s->l1_table = NULL;

    qcow2_cache_flush(bs, s->l2_table_cache);
    qcow2_cache_flush(bs, s->refcount_block_cache);

    qcow2_cache_destroy(bs, s->l2_table_cache);
    qcow2_cache_destroy(bs, s->refcount_block_cache);

    cleanup_unknown_header_ext(bs);
    g_free(s->cluster_cache);
    g_free(s->cluster_data);
    qcow2_refcount_close(bs);
}

static size_t header_ext_add(char *buf, uint32_t magic, const void *s,
    size_t len, size_t buflen)
{
    QCowExtension *ext_backing_fmt = (QCowExtension*) buf;
    size_t ext_len = sizeof(QCowExtension) + ((len + 7) & ~7);

    if (buflen < ext_len) {
        return -ENOSPC;
    }

    *ext_backing_fmt = (QCowExtension) {
        .magic  = cpu_to_be32(magic),
        .len    = cpu_to_be32(len),
    };
    memcpy(buf + sizeof(QCowExtension), s, len);

    return ext_len;
}

/*
 * Updates the qcow2 header, including the variable length parts of it, i.e.
 * the backing file name and all extensions. qcow2 was not designed to allow
 * such changes, so if we run out of space (we can only use the first cluster)
 * this function may fail.
 *
 * Returns 0 on success, -errno in error cases.
 */
int qcow2_update_header(BlockDriverState *bs)
{
    BDRVQcowState *s = bs->opaque;
    QCowHeader *header;
    char *buf;
    size_t buflen = s->cluster_size;
    int ret;
    uint64_t total_size;
    uint32_t refcount_table_clusters;
    Qcow2UnknownHeaderExtension *uext;

    buf = qemu_blockalign(bs, buflen);
    memset(buf, 0, s->cluster_size);

    /* Header structure */
    header = (QCowHeader*) buf;

    if (buflen < sizeof(*header)) {
        ret = -ENOSPC;
        goto fail;
    }

    total_size = bs->total_sectors * BDRV_SECTOR_SIZE;
    refcount_table_clusters = s->refcount_table_size >> (s->cluster_bits - 3);

    *header = (QCowHeader) {
        .magic                  = cpu_to_be32(QCOW_MAGIC),
        .version                = cpu_to_be32(QCOW_VERSION),
        .backing_file_offset    = 0,
        .backing_file_size      = 0,
        .cluster_bits           = cpu_to_be32(s->cluster_bits),
        .size                   = cpu_to_be64(total_size),
        .crypt_method           = cpu_to_be32(s->crypt_method_header),
        .l1_size                = cpu_to_be32(s->l1_size),
        .l1_table_offset        = cpu_to_be64(s->l1_table_offset),
        .refcount_table_offset  = cpu_to_be64(s->refcount_table_offset),
        .refcount_table_clusters = cpu_to_be32(refcount_table_clusters),
        .nb_snapshots           = cpu_to_be32(s->nb_snapshots),
        .snapshots_offset       = cpu_to_be64(s->snapshots_offset),
    };

    buf += sizeof(*header);
    buflen -= sizeof(*header);

    /* Backing file format header extension */
    if (*bs->backing_format) {
        ret = header_ext_add(buf, QCOW2_EXT_MAGIC_BACKING_FORMAT,
                             bs->backing_format, strlen(bs->backing_format),
                             buflen);
        if (ret < 0) {
            goto fail;
        }

        buf += ret;
        buflen -= ret;
    }

    /* Keep unknown header extensions */
    QLIST_FOREACH(uext, &s->unknown_header_ext, next) {
        ret = header_ext_add(buf, uext->magic, uext->data, uext->len, buflen);
        if (ret < 0) {
            goto fail;
        }

        buf += ret;
        buflen -= ret;
    }

    /* End of header extensions */
    ret = header_ext_add(buf, QCOW2_EXT_MAGIC_END, NULL, 0, buflen);
    if (ret < 0) {
        goto fail;
    }

    buf += ret;
    buflen -= ret;

    /* Backing file name */
    if (*bs->backing_file) {
        size_t backing_file_len = strlen(bs->backing_file);

        if (buflen < backing_file_len) {
            ret = -ENOSPC;
            goto fail;
        }

        strncpy(buf, bs->backing_file, buflen);

        header->backing_file_offset = cpu_to_be64(buf - ((char*) header));
        header->backing_file_size   = cpu_to_be32(backing_file_len);
    }

    /* Write the new header */
    ret = bdrv_pwrite(bs->file, 0, header, s->cluster_size);
    if (ret < 0) {
        goto fail;
    }

    ret = 0;
fail:
    qemu_vfree(header);
    return ret;
}

static int qcow2_change_backing_file(BlockDriverState *bs,
    const char *backing_file, const char *backing_fmt)
{
    pstrcpy(bs->backing_file, sizeof(bs->backing_file), backing_file ?: "");
    pstrcpy(bs->backing_format, sizeof(bs->backing_format), backing_fmt ?: "");

    return qcow2_update_header(bs);
}

static int preallocate(BlockDriverState *bs)
{
    uint64_t nb_sectors;
    uint64_t offset;
    int num;
    int ret;
    QCowL2Meta meta;

    nb_sectors = bdrv_getlength(bs) >> 9;
    offset = 0;
    qemu_co_queue_init(&meta.dependent_requests);
    meta.cluster_offset = 0;

    while (nb_sectors) {
        num = MIN(nb_sectors, INT_MAX >> 9);
        ret = qcow2_alloc_cluster_offset(bs, offset, 0, num, &num, &meta);
        if (ret < 0) {
            return ret;
        }

        ret = qcow2_alloc_cluster_link_l2(bs, &meta);
        if (ret < 0) {
            qcow2_free_any_clusters(bs, meta.cluster_offset, meta.nb_clusters);
            return ret;
        }

        /* There are no dependent requests, but we need to remove our request
         * from the list of in-flight requests */
        run_dependent_requests(bs->opaque, &meta);

        /* TODO Preallocate data if requested */

        nb_sectors -= num;
        offset += num << 9;
    }

    /*
     * It is expected that the image file is large enough to actually contain
     * all of the allocated clusters (otherwise we get failing reads after
     * EOF). Extend the image to the last allocated sector.
     */
    if (meta.cluster_offset != 0) {
        uint8_t buf[512];
        memset(buf, 0, 512);
        ret = bdrv_write(bs->file, (meta.cluster_offset >> 9) + num - 1, buf, 1);
        if (ret < 0) {
            return ret;
        }
    }

    return 0;
}

static int qcow2_truncate(BlockDriverState *bs, int64_t offset)
{
    BDRVQcowState *s = bs->opaque;
    int64_t new_l1_size;
    int ret;

    if (offset & 511) {
        return -EINVAL;
    }

    /* cannot proceed if image has snapshots */
    if (s->nb_snapshots) {
        return -ENOTSUP;
    }

    /* shrinking is currently not supported */
    if (offset < bs->total_sectors * 512) {
        return -ENOTSUP;
    }

    new_l1_size = size_to_l1(s, offset);
    ret = qcow2_grow_l1_table(bs, new_l1_size);
    if (ret < 0) {
        return ret;
    }

    /* write updated header.size */
    offset = cpu_to_be64(offset);
    ret = bdrv_pwrite(bs->file, offsetof(QCowHeader, size),
                      &offset, sizeof(uint64_t));
    if (ret < 0) {
        return ret;
    }

    s->l1_vm_state_index = new_l1_size;
    return 0;
}

static int qcow2_create2(const char *filename, int64_t total_size,
                        const char *backing_file, const char *backing_format,
                        int flags, size_t cluster_size, PreallocMode prealloc)
{
    /* Calulate cluster_bits */
    int cluster_bits;
    cluster_bits = ffs(cluster_size) - 1;
    if (cluster_bits < MIN_CLUSTER_BITS || cluster_bits > MAX_CLUSTER_BITS ||
        (1 << cluster_bits) != cluster_size)
    {
        error_report(
            "Cluster size must be a power of two between %d and %dk\n",
            1 << MIN_CLUSTER_BITS, 1 << (MAX_CLUSTER_BITS - 10));
        return -EINVAL;
    }

    /*
     * Open the image file and write a minimal qcow2 header.
     *
     * We keep things simple and start with a zero-sized image. We also
     * do without refcount blocks or a L1 table for now. We'll fix the
     * inconsistency later.
     *
     * We do need a refcount table because growing the refcount table means
     * allocating two new refcount blocks - the seconds of which would be at
     * 2 GB for 64k clusters, and we don't want to have a 2 GB initial file
     * size for any qcow2 image.
     */
    BlockDriverState* bs;
    QCowHeader *header;
    uint64_t* refcount_table;
    int ret;
    QEMUOptionParameter *options = NULL;
    BlockDriver *file_drv;

    if (prealloc == PREALLOC_MODE_FULL || prealloc == PREALLOC_MODE_FALLOC) {
        int64_t meta_size = 0;
        uint64_t nreftablee, nrefblocke, nl1e, nl2e;
        int64_t aligned_total_size = align_offset(total_size * BDRV_SECTOR_SIZE,
                                                  cluster_size);

        /* header: 1 cluster */
        meta_size += cluster_size;

        /* total size of L2 tables */
        nl2e = aligned_total_size / cluster_size;
        nl2e = align_offset(nl2e, cluster_size / sizeof(uint64_t));
        meta_size += nl2e * sizeof(uint64_t);

        /* total size of L1 tables */
        nl1e = nl2e * sizeof(uint64_t) / cluster_size;
        nl1e = align_offset(nl1e, cluster_size / sizeof(uint64_t));
        meta_size += nl1e * sizeof(uint64_t);

        /* total size of refcount blocks
         *
         * note: every host cluster is reference-counted, including metadata
         * (even refcount blocks are recursively included).
         * Let:
         *   a = total_size (this is the guest disk size)
         *   m = meta size not including refcount blocks and refcount tables
         *   c = cluster size
         *   y1 = number of refcount blocks entries
         *   y2 = meta size including everything
         * then,
         *   y1 = (y2 + a)/c
         *   y2 = y1 * sizeof(u16) + y1 * sizeof(u16) * sizeof(u64) / c + m
         * we can get y1:
         *   y1 = (a + m) / (c - sizeof(u16) - sizeof(u16) * sizeof(u64) / c)
         */
        nrefblocke = (aligned_total_size + meta_size + cluster_size) /
            (cluster_size - sizeof(uint16_t) -
             1.0 * sizeof(uint16_t) * sizeof(uint64_t) / cluster_size);
        nrefblocke = align_offset(nrefblocke, cluster_size / sizeof(uint16_t));
        meta_size += nrefblocke * sizeof(uint16_t);

        /* total size of refcount tables */
        nreftablee = nrefblocke * sizeof(uint16_t) / cluster_size;
        nreftablee = align_offset(nreftablee, cluster_size / sizeof(uint64_t));
        meta_size += nreftablee * sizeof(uint64_t);

        file_drv = bdrv_find_protocol(filename, NULL);
        if (file_drv == NULL) {
            error_report("Could not find protocol for file '%s'", filename);
            return -ENOENT;
        }

        options = append_option_parameters(options, file_drv->create_options);

        set_option_parameter_int(options, BLOCK_OPT_SIZE,
                                 aligned_total_size + meta_size);
        set_option_parameter(options, BLOCK_OPT_PREALLOC, PreallocMode_lookup[prealloc]);
    }

    ret = bdrv_create_file(filename, options);
    free_option_parameters(options);
    if (ret < 0) {
        return ret;
    }

    ret = bdrv_file_open(&bs, filename, BDRV_O_RDWR);
    if (ret < 0) {
        return ret;
    }

    /* Write the header */
    QEMU_BUILD_BUG_ON((1 << MIN_CLUSTER_BITS) < sizeof(*header));
    header = g_malloc0(cluster_size);
    *header = (QCowHeader) {
        .magic                      = cpu_to_be32(QCOW_MAGIC),
        .version                    = cpu_to_be32(QCOW_VERSION),
        .cluster_bits               = cpu_to_be32(cluster_bits),
        .size                       = cpu_to_be64(0),
        .l1_table_offset            = cpu_to_be64(0),
        .l1_size                    = cpu_to_be32(0),
        .refcount_table_offset      = cpu_to_be64(cluster_size),
        .refcount_table_clusters    = cpu_to_be32(1),
    };

    if (flags & BLOCK_FLAG_ENCRYPT) {
        header->crypt_method = cpu_to_be32(QCOW_CRYPT_AES);
    } else {
        header->crypt_method = cpu_to_be32(QCOW_CRYPT_NONE);
    }

    ret = bdrv_pwrite(bs, 0, header, cluster_size);
    g_free(header);
    if (ret < 0) {
        goto out;
    }

    /* Write a refcount table with one refcount block */
    refcount_table = qemu_mallocz(2 * cluster_size);
    refcount_table[0] = cpu_to_be64(2 * cluster_size);
    ret = bdrv_pwrite(bs, cluster_size, refcount_table, 2 * cluster_size);
    qemu_free(refcount_table);

    if (ret < 0) {
        goto out;
    }

    bdrv_close(bs);

    /*
     * And now open the image and make it consistent first (i.e. increase the
     * refcount of the cluster that is occupied by the header and the refcount
     * table)
     */
    BlockDriver* drv = bdrv_find_format("qcow2");
    assert(drv != NULL);
    ret = bdrv_open(bs, filename,
        BDRV_O_RDWR | BDRV_O_CACHE_WB | BDRV_O_NO_FLUSH, drv);
    if (ret < 0) {
        goto out;
    }

    ret = qcow2_alloc_clusters(bs, 3 * cluster_size);
    if (ret < 0) {
        goto out;

    } else if (ret != 0) {
        error_report("Huh, first cluster in empty image is already in use?");
        abort();
    }

    /* Okay, now that we have a valid image, let's give it the right size */
    ret = bdrv_truncate(bs, total_size * BDRV_SECTOR_SIZE);
    if (ret < 0) {
        goto out;
    }

    /* Want a backing file? There you go.*/
    if (backing_file) {
        ret = bdrv_change_backing_file(bs, backing_file, backing_format);
        if (ret < 0) {
            goto out;
        }
    }

    /* And if we're supposed to preallocate metadata, do that now */
    if (prealloc != PREALLOC_MODE_OFF) {
        ret = preallocate(bs);
        if (ret < 0) {
            goto out;
        }
    }

    bdrv_close(bs);

    /* Reopen the image without BDRV_O_NO_FLUSH to flush it before returning */
    ret = bdrv_open(bs, filename, BDRV_O_RDWR | BDRV_O_CACHE_WB, drv);
    if (ret < 0) {
        goto out;
    }

    ret = 0;
out:
    bdrv_delete(bs);
    return ret;
}

static int qcow2_create(const char *filename, QEMUOptionParameter *options)
{
    const char *backing_file = NULL;
    const char *backing_fmt = NULL;
    uint64_t sectors = 0;
    int flags = 0;
    size_t cluster_size = DEFAULT_CLUSTER_SIZE;
    PreallocMode prealloc = PREALLOC_MODE_OFF;
    Error *local_err = NULL;

    /* Read out options */
    while (options && options->name) {
        if (!strcmp(options->name, BLOCK_OPT_SIZE)) {
            sectors = options->value.n / 512;
        } else if (!strcmp(options->name, BLOCK_OPT_BACKING_FILE)) {
            backing_file = options->value.s;
        } else if (!strcmp(options->name, BLOCK_OPT_BACKING_FMT)) {
            backing_fmt = options->value.s;
        } else if (!strcmp(options->name, BLOCK_OPT_ENCRYPT)) {
            flags |= options->value.n ? BLOCK_FLAG_ENCRYPT : 0;
        } else if (!strcmp(options->name, BLOCK_OPT_CLUSTER_SIZE)) {
            if (options->value.n) {
                cluster_size = options->value.n;
            }
        } else if (!strcmp(options->name, BLOCK_OPT_PREALLOC)) {
            prealloc = qapi_enum_parse(PreallocMode_lookup,
                                       options->value.s, PREALLOC_MODE_MAX,
                                       PREALLOC_MODE_OFF, &local_err);
            if (local_err) {
                qerror_report_err(local_err);
                error_free(local_err);
                return -EINVAL;
            }
        }
        options++;
    }

    if (backing_file && prealloc != PREALLOC_MODE_OFF) {
        fprintf(stderr, "Backing file and preallocation cannot be used at "
            "the same time\n");
        return -EINVAL;
    }

    assert(!options || !options->name);
    return qcow2_create2(filename, sectors, backing_file, backing_fmt, flags,
                         cluster_size, prealloc);
}

static int qcow2_make_empty(BlockDriverState *bs)
{
#if 0
    /* XXX: not correct */
    BDRVQcowState *s = bs->opaque;
    uint32_t l1_length = s->l1_size * sizeof(uint64_t);
    int ret;

    memset(s->l1_table, 0, l1_length);
    if (bdrv_pwrite(bs->file, s->l1_table_offset, s->l1_table, l1_length) < 0)
        return -1;
    ret = bdrv_truncate(bs->file, s->l1_table_offset + l1_length);
    if (ret < 0)
        return ret;

    l2_cache_reset(bs);
#endif
    return 0;
}

static coroutine_fn int qcow2_co_discard(BlockDriverState *bs,
    int64_t sector_num, int nb_sectors)
{
    int ret;
    BDRVQcowState *s = bs->opaque;

    qemu_co_mutex_lock(&s->lock);
    ret = qcow2_discard_clusters(bs, sector_num << BDRV_SECTOR_BITS,
        nb_sectors);
    qemu_co_mutex_unlock(&s->lock);
    return ret;
}

/* XXX: put compressed sectors first, then all the cluster aligned
   tables to avoid losing bytes in alignment */
static int qcow2_write_compressed(BlockDriverState *bs, int64_t sector_num,
                                  const uint8_t *buf, int nb_sectors)
{
    BDRVQcowState *s = bs->opaque;
    z_stream strm;
    int ret, out_len;
    uint8_t *out_buf;
    uint64_t cluster_offset;

    if (nb_sectors == 0) {
        /* align end of file to a sector boundary to ease reading with
           sector based I/Os */
        cluster_offset = bdrv_getlength(bs->file);
        cluster_offset = (cluster_offset + 511) & ~511;
        bdrv_truncate(bs->file, cluster_offset);
        return 0;
    }

    if (nb_sectors != s->cluster_sectors)
        return -EINVAL;

    out_buf = g_malloc(s->cluster_size + (s->cluster_size / 1000) + 128);

    /* best compression, small window, no zlib header */
    memset(&strm, 0, sizeof(strm));
    ret = deflateInit2(&strm, Z_DEFAULT_COMPRESSION,
                       Z_DEFLATED, -12,
                       9, Z_DEFAULT_STRATEGY);
    if (ret != 0) {
        ret = -EINVAL;
        goto fail;
    }

    strm.avail_in = s->cluster_size;
    strm.next_in = (uint8_t *)buf;
    strm.avail_out = s->cluster_size;
    strm.next_out = out_buf;

    ret = deflate(&strm, Z_FINISH);
    if (ret != Z_STREAM_END && ret != Z_OK) {
        deflateEnd(&strm);
        ret = -EINVAL;
        goto fail;
    }
    out_len = strm.next_out - out_buf;

    deflateEnd(&strm);

    if (ret != Z_STREAM_END || out_len >= s->cluster_size) {
        /* could not compress: write normal cluster */
        ret = bdrv_write(bs, sector_num, buf, s->cluster_sectors);
        if (ret < 0) {
            goto fail;
        }
    } else {
        cluster_offset = qcow2_alloc_compressed_cluster_offset(bs,
            sector_num << 9, out_len);
        if (!cluster_offset) {
            ret = -EIO;
            goto fail;
        }
        cluster_offset &= s->cluster_offset_mask;

        ret = qcow2_pre_write_overlap_check(bs, 0, cluster_offset, out_len);
        if (ret < 0) {
            goto fail;
        }

        BLKDBG_EVENT(bs->file, BLKDBG_WRITE_COMPRESSED);
        ret = bdrv_pwrite(bs->file, cluster_offset, out_buf, out_len);
        if (ret < 0) {
            goto fail;
        }
    }

    ret = 0;
fail:
    g_free(out_buf);
    return ret;
}

static int qcow2_co_flush(BlockDriverState *bs)
{
    BDRVQcowState *s = bs->opaque;
    int ret;

    qemu_co_mutex_lock(&s->lock);
    ret = qcow2_cache_flush(bs, s->l2_table_cache);
    if (ret < 0) {
        qemu_co_mutex_unlock(&s->lock);
        return ret;
    }

    ret = qcow2_cache_flush(bs, s->refcount_block_cache);
    if (ret < 0) {
        qemu_co_mutex_unlock(&s->lock);
        return ret;
    }
    qemu_co_mutex_unlock(&s->lock);

    return bdrv_co_flush(bs->file);
}

static int qcow2_get_info(BlockDriverState *bs, BlockDriverInfo *bdi)
{
    BDRVQcowState *s = bs->opaque;
    bdi->cluster_size = s->cluster_size;
    bdi->vm_state_offset = qcow2_vm_state_offset(s);
    return 0;
}


static int qcow2_check(BlockDriverState *bs, BdrvCheckResult *result,
                       BdrvCheckMode fix)
{
    return qcow2_check_refcounts(bs, result, fix);
}

#if 0
static void dump_refcounts(BlockDriverState *bs)
{
    BDRVQcowState *s = bs->opaque;
    int64_t nb_clusters, k, k1, size;
    int refcount;

    size = bdrv_getlength(bs->file);
    nb_clusters = size_to_clusters(s, size);
    for(k = 0; k < nb_clusters;) {
        k1 = k;
        refcount = get_refcount(bs, k);
        k++;
        while (k < nb_clusters && get_refcount(bs, k) == refcount)
            k++;
        printf("%" PRId64 ": refcount=%d nb=%" PRId64 "\n", k, refcount,
               k - k1);
    }
}
#endif

static int qcow2_save_vmstate(BlockDriverState *bs, const uint8_t *buf,
                              int64_t pos, int size)
{
    BDRVQcowState *s = bs->opaque;
    int growable = bs->growable;
    int ret;

    BLKDBG_EVENT(bs->file, BLKDBG_VMSTATE_SAVE);
    bs->growable = 1;
    ret = bdrv_pwrite(bs, qcow2_vm_state_offset(s) + pos, buf, size);
    bs->growable = growable;

    return ret;
}

static int qcow2_load_vmstate(BlockDriverState *bs, uint8_t *buf,
                              int64_t pos, int size)
{
    BDRVQcowState *s = bs->opaque;
    int growable = bs->growable;
    bool zero_beyond_eof = bs->zero_beyond_eof;
    int ret;

    BLKDBG_EVENT(bs->file, BLKDBG_VMSTATE_LOAD);
    bs->growable = 1;
    bs->zero_beyond_eof = false;
    ret = bdrv_pread(bs, qcow2_vm_state_offset(s) + pos, buf, size);
    bs->growable = growable;
    bs->zero_beyond_eof = zero_beyond_eof;

    return ret;
}

/*
 * If offset or size are negative, respectively, they will not be included in
 * the BLOCK_IMAGE_CORRUPTED event emitted.
 * fatal will be ignored for read-only BDS; corruptions found there will always
 * be considered non-fatal.
 */
void qcow2_signal_corruption(BlockDriverState *bs, bool fatal, int64_t offset,
                             int64_t size, const char *message_format, ...)
{
    BDRVQcowState *s = bs->opaque;
    char *message;
    QObject *data;
    va_list ap;

    fatal = fatal && !bs->read_only;

    if (fatal ? s->signaled_fatal_corruption : s->signaled_corruption) {
        return;
    }

    va_start(ap, message_format);
    message = g_strdup_vprintf(message_format, ap);
    va_end(ap);

    if (fatal) {
        fprintf(stderr, "qcow2: Image is corrupt (further access will be "
                "prevented): %s; please use qemu-img check -r. Further "
                "corruption events will be suppressed\n", message);
    } else {
        fprintf(stderr, "qcow2: Image is corrupt: %s; please use qemu-img "
                "check -r. Further non-fatal corruption events will be "
                "suppressed\n", message);
    }

    assert((offset >= 0) == (size >= 0));

    if (offset >= 0) {
        data = qobject_from_jsonf("{ 'device': %s, 'msg': %s, 'offset': %"
                                  PRId64 ", 'size': %" PRId64 ", 'fatal': %s }",
                                  bdrv_get_device_name(bs), message,
                                  offset, size, fatal ? "true" : "false");
    } else {
        data = qobject_from_jsonf("{ 'device': %s, 'msg': %s, 'fatal': %s }",
                                  bdrv_get_device_name(bs), message,
                                  fatal ? "true" : "false");
    }

    monitor_protocol_event(QEVENT_BLOCK_IMAGE_CORRUPTED, data);
    qobject_decref(data);

    g_free(message);

    if (fatal) {
        bs->drv = NULL; /* make BDS unusable */
        s->signaled_fatal_corruption = true;
    }

    s->signaled_corruption = true;
}

static QEMUOptionParameter qcow2_create_options[] = {
    {
        .name = BLOCK_OPT_SIZE,
        .type = OPT_SIZE,
        .help = "Virtual disk size"
    },
    {
        .name = BLOCK_OPT_BACKING_FILE,
        .type = OPT_STRING,
        .help = "File name of a base image"
    },
    {
        .name = BLOCK_OPT_BACKING_FMT,
        .type = OPT_STRING,
        .help = "Image format of the base image"
    },
    {
        .name = BLOCK_OPT_ENCRYPT,
        .type = OPT_FLAG,
        .help = "Encrypt the image"
    },
    {
        .name = BLOCK_OPT_CLUSTER_SIZE,
        .type = OPT_SIZE,
        .help = "qcow2 cluster size",
        .value = { .n = DEFAULT_CLUSTER_SIZE },
    },
    {
        .name = BLOCK_OPT_PREALLOC,
        .type = OPT_STRING,
        .help = "Preallocation mode (allowed values: off, metadata, "
                "falloc, full)"
    },
    { NULL }
};

static BlockDriver bdrv_qcow2 = {
    .format_name        = "qcow2",
    .instance_size      = sizeof(BDRVQcowState),
    .bdrv_probe         = qcow2_probe,
    .bdrv_open          = qcow2_open,
    .bdrv_close         = qcow2_close,
    .bdrv_reopen_prepare  = qcow2_reopen_prepare,
    .bdrv_create        = qcow2_create,
    .bdrv_co_get_block_status = qcow2_co_get_block_status,
    .bdrv_set_key       = qcow2_set_key,
    .bdrv_make_empty    = qcow2_make_empty,

    .bdrv_co_readv      = qcow2_co_readv,
    .bdrv_co_writev     = qcow2_co_writev,
    .bdrv_co_flush      = qcow2_co_flush,

    .bdrv_co_discard        = qcow2_co_discard,
    .bdrv_truncate          = qcow2_truncate,
    .bdrv_write_compressed  = qcow2_write_compressed,

    .bdrv_snapshot_create   = qcow2_snapshot_create,
    .bdrv_snapshot_goto     = qcow2_snapshot_goto,
    .bdrv_snapshot_delete   = qcow2_snapshot_delete,
    .bdrv_snapshot_list     = qcow2_snapshot_list,
    .bdrv_get_info      = qcow2_get_info,

    .bdrv_save_vmstate    = qcow2_save_vmstate,
    .bdrv_load_vmstate    = qcow2_load_vmstate,

    .bdrv_change_backing_file   = qcow2_change_backing_file,

    .create_options = qcow2_create_options,
    .bdrv_check = qcow2_check,
};

static void bdrv_qcow2_init(void)
{
    bdrv_register(&bdrv_qcow2);
}

block_init(bdrv_qcow2_init);
