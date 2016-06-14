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

#ifndef BLOCK_QCOW2_H
#define BLOCK_QCOW2_H

#include <stdbool.h>
#include "aes.h"
#include "qemu-coroutine.h"

//#define DEBUG_ALLOC
//#define DEBUG_ALLOC2
//#define DEBUG_EXT

#define QCOW_MAGIC (('Q' << 24) | ('F' << 16) | ('I' << 8) | 0xfb)
#define QCOW_VERSION 2

#define QCOW_CRYPT_NONE 0
#define QCOW_CRYPT_AES  1

#define QCOW_MAX_CRYPT_CLUSTERS 32
#define QCOW_MAX_SNAPSHOTS 65536

/* 8 MB refcount table is enough for 2 PB images at 64k cluster size
 * (128 GB for 512 byte clusters, 2 EB for 2 MB clusters) */
#define QCOW_MAX_REFTABLE_SIZE 0x800000

/* Allow for an average of 1k per snapshot table entry, should be plenty of
 * space for snapshot names and IDs */
#define QCOW_MAX_SNAPSHOTS_SIZE (1024 * QCOW_MAX_SNAPSHOTS)

/* indicate that the refcount of the referenced cluster is exactly one. */
#define QCOW_OFLAG_COPIED     (1LL << 63)
/* indicate that the cluster is compressed (they never have the copied flag) */
#define QCOW_OFLAG_COMPRESSED (1LL << 62)

#define MIN_CLUSTER_BITS 9
#define MAX_CLUSTER_BITS 21

#define L2_CACHE_SIZE 16

/* Must be at least 4 to cover all cases of refcount table growth */
#define REFCOUNT_CACHE_SIZE 4

#define DEFAULT_CLUSTER_SIZE 65536

typedef struct QCowHeader {
    uint32_t magic;
    uint32_t version;
    uint64_t backing_file_offset;
    uint32_t backing_file_size;
    uint32_t cluster_bits;
    uint64_t size; /* in bytes */
    uint32_t crypt_method;
    uint32_t l1_size; /* XXX: save number of clusters instead ? */
    uint64_t l1_table_offset;
    uint64_t refcount_table_offset;
    uint32_t refcount_table_clusters;
    uint32_t nb_snapshots;
    uint64_t snapshots_offset;
} QCowHeader;

typedef struct __attribute__((packed)) QCowSnapshotHeader {
    /* header is 8 byte aligned */
    uint64_t l1_table_offset;

    uint32_t l1_size;
    uint16_t id_str_size;
    uint16_t name_size;

    uint32_t date_sec;
    uint32_t date_nsec;

    uint64_t vm_clock_nsec;

    uint32_t vm_state_size;
    uint32_t extra_data_size; /* for extension */
    /* extra data follows */
    /* id_str follows */
    /* name follows  */
} QCowSnapshotHeader;


typedef struct QCowSnapshot {
    uint64_t l1_table_offset;
    uint32_t l1_size;
    char *id_str;
    char *name;
    uint32_t vm_state_size;
    uint32_t date_sec;
    uint32_t date_nsec;
    uint64_t vm_clock_nsec;
} QCowSnapshot;

struct Qcow2Cache;
typedef struct Qcow2Cache Qcow2Cache;

typedef struct Qcow2UnknownHeaderExtension {
    uint32_t magic;
    uint32_t len;
    QLIST_ENTRY(Qcow2UnknownHeaderExtension) next;
    uint8_t data[];
} Qcow2UnknownHeaderExtension;

typedef struct BDRVQcowState {
    int cluster_bits;
    int cluster_size;
    int cluster_sectors;
    int l2_bits;
    int l2_size;
    int l1_size;
    int l1_vm_state_index;
    int refcount_block_bits;
    int refcount_block_size;
    int csize_shift;
    int csize_mask;
    uint64_t cluster_offset_mask;
    uint64_t l1_table_offset;
    uint64_t *l1_table;

    Qcow2Cache* l2_table_cache;
    Qcow2Cache* refcount_block_cache;

    uint8_t *cluster_cache;
    uint8_t *cluster_data;
    uint64_t cluster_cache_offset;
    QLIST_HEAD(QCowClusterAlloc, QCowL2Meta) cluster_allocs;

    uint64_t *refcount_table;
    uint64_t refcount_table_offset;
    uint32_t refcount_table_size;
    uint64_t free_cluster_index;
    uint64_t free_byte_offset;

    CoMutex lock;

    uint32_t crypt_method; /* current crypt method, 0 if no key yet */
    uint32_t crypt_method_header;
    AES_KEY aes_encrypt_key;
    AES_KEY aes_decrypt_key;
    uint64_t snapshots_offset;
    int snapshots_size;
    unsigned int nb_snapshots;
    QCowSnapshot *snapshots;

    int overlap_check; /* bitmask of Qcow2MetadataOverlap values */
    bool signaled_corruption, signaled_fatal_corruption;

    QLIST_HEAD(, Qcow2UnknownHeaderExtension) unknown_header_ext;
} BDRVQcowState;

/* XXX: use std qcow open function ? */
typedef struct QCowCreateState {
    int cluster_size;
    int cluster_bits;
    uint16_t *refcount_block;
    uint64_t *refcount_table;
    int64_t l1_table_offset;
    int64_t refcount_table_offset;
    int64_t refcount_block_offset;
} QCowCreateState;

struct QCowAIOCB;

/* XXX This could be private for qcow2-cluster.c */
typedef struct QCowL2Meta
{
    uint64_t offset;
    uint64_t cluster_offset;
    int n_start;
    int nb_available;
    int nb_clusters;
    struct QCowL2Meta *depends_on;
    CoQueue dependent_requests;

    QLIST_ENTRY(QCowL2Meta) next_in_flight;
} QCowL2Meta;

enum {
    QCOW2_CLUSTER_UNALLOCATED,
    QCOW2_CLUSTER_NORMAL,
    QCOW2_CLUSTER_COMPRESSED,
};

typedef enum QCow2MetadataOverlap {
    QCOW2_OL_MAIN_HEADER_BITNR    = 0,
    QCOW2_OL_ACTIVE_L1_BITNR      = 1,
    QCOW2_OL_ACTIVE_L2_BITNR      = 2,
    QCOW2_OL_REFCOUNT_TABLE_BITNR = 3,
    QCOW2_OL_REFCOUNT_BLOCK_BITNR = 4,
    QCOW2_OL_SNAPSHOT_TABLE_BITNR = 5,
    QCOW2_OL_INACTIVE_L1_BITNR    = 6,
    QCOW2_OL_INACTIVE_L2_BITNR    = 7,

    QCOW2_OL_MAX_BITNR            = 8,

    QCOW2_OL_NONE           = 0,
    QCOW2_OL_MAIN_HEADER    = (1 << QCOW2_OL_MAIN_HEADER_BITNR),
    QCOW2_OL_ACTIVE_L1      = (1 << QCOW2_OL_ACTIVE_L1_BITNR),
    QCOW2_OL_ACTIVE_L2      = (1 << QCOW2_OL_ACTIVE_L2_BITNR),
    QCOW2_OL_REFCOUNT_TABLE = (1 << QCOW2_OL_REFCOUNT_TABLE_BITNR),
    QCOW2_OL_REFCOUNT_BLOCK = (1 << QCOW2_OL_REFCOUNT_BLOCK_BITNR),
    QCOW2_OL_SNAPSHOT_TABLE = (1 << QCOW2_OL_SNAPSHOT_TABLE_BITNR),
    QCOW2_OL_INACTIVE_L1    = (1 << QCOW2_OL_INACTIVE_L1_BITNR),
    /* NOTE: Checking overlaps with inactive L2 tables will result in bdrv
     * reads. */
    QCOW2_OL_INACTIVE_L2    = (1 << QCOW2_OL_INACTIVE_L2_BITNR),
} QCow2MetadataOverlap;

/* Perform all overlap checks which can be done in constant time */
#define QCOW2_OL_CONSTANT \
    (QCOW2_OL_MAIN_HEADER | QCOW2_OL_ACTIVE_L1 | QCOW2_OL_REFCOUNT_TABLE | \
     QCOW2_OL_SNAPSHOT_TABLE)

/* Perform all overlap checks which don't require disk access */
#define QCOW2_OL_CACHED \
    (QCOW2_OL_CONSTANT | QCOW2_OL_ACTIVE_L2 | QCOW2_OL_REFCOUNT_BLOCK | \
     QCOW2_OL_INACTIVE_L1)

/* Perform all overlap checks */
#define QCOW2_OL_ALL \
    (QCOW2_OL_CACHED | QCOW2_OL_INACTIVE_L2)

#define L1E_OFFSET_MASK 0x00fffffffffffe00ULL
#define L2E_OFFSET_MASK 0x00fffffffffffe00ULL
#define L2E_COMPRESSED_OFFSET_SIZE_MASK 0x3fffffffffffffffULL

#define REFT_OFFSET_MASK 0xfffffffffffffe00ULL

static inline int64_t start_of_cluster(BDRVQcowState *s, int64_t offset)
{
    return offset & ~(s->cluster_size - 1);
}

static inline int64_t offset_into_cluster(BDRVQcowState *s, int64_t offset)
{
    return offset & (s->cluster_size - 1);
}

static inline int size_to_clusters(BDRVQcowState *s, int64_t size)
{
    return (size + (s->cluster_size - 1)) >> s->cluster_bits;
}

static inline int64_t size_to_l1(BDRVQcowState *s, int64_t size)
{
    int shift = s->cluster_bits + s->l2_bits;
    return (size + (1ULL << shift) - 1) >> shift;
}

static inline int64_t align_offset(int64_t offset, int n)
{
    offset = (offset + n - 1) & ~(n - 1);
    return offset;
}

static inline uint64_t qcow2_max_refcount_clusters(BDRVQcowState *s)
{
    return QCOW_MAX_REFTABLE_SIZE >> s->cluster_bits;
}

static inline int64_t qcow2_vm_state_offset(BDRVQcowState *s)
{
    return (int64_t)s->l1_vm_state_index << (s->cluster_bits + s->l2_bits);
}

static inline int qcow2_get_cluster_type(uint64_t l2_entry)
{
    if (l2_entry & QCOW_OFLAG_COMPRESSED) {
        return QCOW2_CLUSTER_COMPRESSED;
    } else if (!(l2_entry & L2E_OFFSET_MASK)) {
        return QCOW2_CLUSTER_UNALLOCATED;
    } else {
        return QCOW2_CLUSTER_NORMAL;
    }
}

// FIXME Need qcow2_ prefix to global functions

/* qcow2.c functions */
int qcow2_backing_read1(BlockDriverState *bs, QEMUIOVector *qiov,
                  int64_t sector_num, int nb_sectors);
int qcow2_update_header(BlockDriverState *bs);

void qcow2_signal_corruption(BlockDriverState *bs, bool fatal, int64_t offset,
                             int64_t size, const char *message_format, ...)
                             GCC_FMT_ATTR(5, 6);

/* qcow2-refcount.c functions */
int qcow2_refcount_init(BlockDriverState *bs);
void qcow2_refcount_close(BlockDriverState *bs);

int64_t qcow2_alloc_clusters(BlockDriverState *bs, uint64_t size);
int64_t qcow2_alloc_bytes(BlockDriverState *bs, int size);
void qcow2_free_clusters(BlockDriverState *bs,
    int64_t offset, int64_t size);
void qcow2_free_any_clusters(BlockDriverState *bs,
    uint64_t cluster_offset, int nb_clusters);

void qcow2_create_refcount_update(QCowCreateState *s, int64_t offset,
    int64_t size);
int qcow2_update_snapshot_refcount(BlockDriverState *bs,
    int64_t l1_table_offset, int l1_size, int addend);

int qcow2_check_refcounts(BlockDriverState *bs, BdrvCheckResult *res,
                          BdrvCheckMode fix);

int qcow2_check_metadata_overlap(BlockDriverState *bs, int ign, int64_t offset,
                                 int64_t size);
int qcow2_pre_write_overlap_check(BlockDriverState *bs, int ign, int64_t offset,
                                  int64_t size);

/* qcow2-cluster.c functions */
int qcow2_grow_l1_table(BlockDriverState *bs, uint64_t min_size);
int qcow2_write_l1_entry(BlockDriverState *bs, int l1_index);
void qcow2_l2_cache_reset(BlockDriverState *bs);
int qcow2_decompress_cluster(BlockDriverState *bs, uint64_t cluster_offset);
void qcow2_encrypt_sectors(BDRVQcowState *s, int64_t sector_num,
                     uint8_t *out_buf, const uint8_t *in_buf,
                     int nb_sectors, int enc,
                     const AES_KEY *key);

int qcow2_get_cluster_offset(BlockDriverState *bs, uint64_t offset,
    int *num, uint64_t *cluster_offset);
int qcow2_alloc_cluster_offset(BlockDriverState *bs, uint64_t offset,
    int n_start, int n_end, int *num, QCowL2Meta *m);
uint64_t qcow2_alloc_compressed_cluster_offset(BlockDriverState *bs,
                                         uint64_t offset,
                                         int compressed_size);

int qcow2_alloc_cluster_link_l2(BlockDriverState *bs, QCowL2Meta *m);
int qcow2_discard_clusters(BlockDriverState *bs, uint64_t offset,
    int nb_sectors);

/* qcow2-snapshot.c functions */
int qcow2_snapshot_create(BlockDriverState *bs, QEMUSnapshotInfo *sn_info);
int qcow2_snapshot_goto(BlockDriverState *bs, const char *snapshot_id);
int qcow2_snapshot_delete(BlockDriverState *bs, const char *snapshot_id);
int qcow2_snapshot_list(BlockDriverState *bs, QEMUSnapshotInfo **psn_tab);

void qcow2_free_snapshots(BlockDriverState *bs);
int qcow2_read_snapshots(BlockDriverState *bs);

/* qcow2-cache.c functions */
Qcow2Cache *qcow2_cache_create(BlockDriverState *bs, int num_tables,
    bool writethrough);
int qcow2_cache_destroy(BlockDriverState* bs, Qcow2Cache *c);
bool qcow2_cache_set_writethrough(BlockDriverState *bs, Qcow2Cache *c,
    bool enable);

void qcow2_cache_entry_mark_dirty(Qcow2Cache *c, void *table);
int qcow2_cache_flush(BlockDriverState *bs, Qcow2Cache *c);
int qcow2_cache_set_dependency(BlockDriverState *bs, Qcow2Cache *c,
    Qcow2Cache *dependency);
void qcow2_cache_depends_on_flush(Qcow2Cache *c);

int qcow2_cache_empty(BlockDriverState *bs, Qcow2Cache *c);

int qcow2_cache_get(BlockDriverState *bs, Qcow2Cache *c, uint64_t offset,
    void **table);
int qcow2_cache_get_empty(BlockDriverState *bs, Qcow2Cache *c, uint64_t offset,
    void **table);
int qcow2_cache_put(BlockDriverState *bs, Qcow2Cache *c, void **table);

#endif
