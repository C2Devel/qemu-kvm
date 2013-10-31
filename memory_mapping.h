/*
 * QEMU memory mapping
 *
 * Copyright Fujitsu, Corp. 2011, 2012
 *
 * Authors:
 *     Wen Congyang <wency@cn.fujitsu.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2. See
 * the COPYING file in the top-level directory.
 *
 */

#ifndef MEMORY_MAPPING_H
#define MEMORY_MAPPING_H

#include "qemu-queue.h"

#ifndef CONFIG_USER_ONLY
typedef struct GuestPhysBlock {
    /* visible to guest, reflects PCI hole, etc */
    target_phys_addr_t target_start;

    /* implies size */
    target_phys_addr_t target_end;

    /* points into host memory */
    uint8_t *host_addr;

    QTAILQ_ENTRY(GuestPhysBlock) next;
} GuestPhysBlock;

/* point-in-time snapshot of guest-visible physical mappings */
typedef struct GuestPhysBlockList {
    unsigned num;
    QTAILQ_HEAD(GuestPhysBlockHead, GuestPhysBlock) head;
} GuestPhysBlockList;

/* The physical and virtual address in the memory mapping are contiguous. */
typedef struct MemoryMapping {
    target_phys_addr_t phys_addr;
    target_ulong virt_addr;
    ram_addr_t length;
    QTAILQ_ENTRY(MemoryMapping) next;
} MemoryMapping;

typedef struct MemoryMappingList {
    unsigned int num;
    MemoryMapping *last_mapping;
    QTAILQ_HEAD(, MemoryMapping) head;
} MemoryMappingList;

/*
 * add or merge the memory region [phys_addr, phys_addr + length) into the
 * memory mapping's list. The region's virtual address starts with virt_addr,
 * and is contiguous. The list is sorted by phys_addr.
 */
void memory_mapping_list_add_merge_sorted(MemoryMappingList *list,
                                          target_phys_addr_t phys_addr,
                                          target_phys_addr_t virt_addr,
                                          ram_addr_t length);

void memory_mapping_list_free(MemoryMappingList *list);

void memory_mapping_list_init(MemoryMappingList *list);

void guest_phys_blocks_free(GuestPhysBlockList *list);
void guest_phys_blocks_init(GuestPhysBlockList *list);
void guest_phys_blocks_append(GuestPhysBlockList *list);

/*
 * Return value:
 *    0: success
 *   -1: failed
 *   -2: unsupported
 */
#if defined(CONFIG_HAVE_GET_MEMORY_MAPPING)
int qemu_get_guest_memory_mapping(MemoryMappingList *list,
                                  const GuestPhysBlockList *guest_phys_blocks);
#else
static inline
int qemu_get_guest_memory_mapping(MemoryMappingList *list,
                                  const GuestPhysBlockList *guest_phys_blocks)
{
    return -2;
}
#endif

/* get guest's memory mapping without do paging(virtual address is 0). */
void qemu_get_guest_simple_memory_mapping(MemoryMappingList *list,
                                  const GuestPhysBlockList *guest_phys_blocks);

void memory_mapping_filter(MemoryMappingList *list, int64_t begin,
                           int64_t length);

#else

/* We use MemoryMappingList* in cpu-all.h */
typedef struct MemoryMappingList MemoryMappingList;
#endif
#endif
