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

#include <glib.h>

#include "cpu.h"
#include "cpu-all.h"
#include "memory_mapping.h"

//#define DEBUG_GUEST_PHYS_REGION_ADD

static void memory_mapping_list_add_mapping_sorted(MemoryMappingList *list,
                                                   MemoryMapping *mapping)
{
    MemoryMapping *p;

    QTAILQ_FOREACH(p, &list->head, next) {
        if (p->phys_addr >= mapping->phys_addr) {
            QTAILQ_INSERT_BEFORE(p, mapping, next);
            return;
        }
    }
    QTAILQ_INSERT_TAIL(&list->head, mapping, next);
}

static void create_new_memory_mapping(MemoryMappingList *list,
                                      target_phys_addr_t phys_addr,
                                      target_phys_addr_t virt_addr,
                                      ram_addr_t length)
{
    MemoryMapping *memory_mapping;

    memory_mapping = g_malloc(sizeof(MemoryMapping));
    memory_mapping->phys_addr = phys_addr;
    memory_mapping->virt_addr = virt_addr;
    memory_mapping->length = length;
    list->last_mapping = memory_mapping;
    list->num++;
    memory_mapping_list_add_mapping_sorted(list, memory_mapping);
}

static inline bool mapping_contiguous(MemoryMapping *map,
                                      target_phys_addr_t phys_addr,
                                      target_phys_addr_t virt_addr)
{
    return phys_addr == map->phys_addr + map->length &&
           virt_addr == map->virt_addr + map->length;
}

/*
 * [map->phys_addr, map->phys_addr + map->length) and
 * [phys_addr, phys_addr + length) have intersection?
 */
static inline bool mapping_have_same_region(MemoryMapping *map,
                                            target_phys_addr_t phys_addr,
                                            ram_addr_t length)
{
    return !(phys_addr + length < map->phys_addr ||
             phys_addr >= map->phys_addr + map->length);
}

/*
 * [map->phys_addr, map->phys_addr + map->length) and
 * [phys_addr, phys_addr + length) have intersection. The virtual address in the
 * intersection are the same?
 */
static inline bool mapping_conflict(MemoryMapping *map,
                                    target_phys_addr_t phys_addr,
                                    target_phys_addr_t virt_addr)
{
    return virt_addr - map->virt_addr != phys_addr - map->phys_addr;
}

/*
 * [map->virt_addr, map->virt_addr + map->length) and
 * [virt_addr, virt_addr + length) have intersection. And the physical address
 * in the intersection are the same.
 */
static inline void mapping_merge(MemoryMapping *map,
                                 target_phys_addr_t virt_addr,
                                 ram_addr_t length)
{
    if (virt_addr < map->virt_addr) {
        map->length += map->virt_addr - virt_addr;
        map->virt_addr = virt_addr;
    }

    if ((virt_addr + length) >
        (map->virt_addr + map->length)) {
        map->length = virt_addr + length - map->virt_addr;
    }
}

void memory_mapping_list_add_merge_sorted(MemoryMappingList *list,
                                          target_phys_addr_t phys_addr,
                                          target_phys_addr_t virt_addr,
                                          ram_addr_t length)
{
    MemoryMapping *memory_mapping, *last_mapping;

    if (QTAILQ_EMPTY(&list->head)) {
        create_new_memory_mapping(list, phys_addr, virt_addr, length);
        return;
    }

    last_mapping = list->last_mapping;
    if (last_mapping) {
        if (mapping_contiguous(last_mapping, phys_addr, virt_addr)) {
            last_mapping->length += length;
            return;
        }
    }

    QTAILQ_FOREACH(memory_mapping, &list->head, next) {
        if (mapping_contiguous(memory_mapping, phys_addr, virt_addr)) {
            memory_mapping->length += length;
            list->last_mapping = memory_mapping;
            return;
        }

        if (phys_addr + length < memory_mapping->phys_addr) {
            /* create a new region before memory_mapping */
            break;
        }

        if (mapping_have_same_region(memory_mapping, phys_addr, length)) {
            if (mapping_conflict(memory_mapping, phys_addr, virt_addr)) {
                continue;
            }

            /* merge this region into memory_mapping */
            mapping_merge(memory_mapping, virt_addr, length);
            list->last_mapping = memory_mapping;
            return;
        }
    }

    /* this region can not be merged into any existed memory mapping. */
    create_new_memory_mapping(list, phys_addr, virt_addr, length);
}

void memory_mapping_list_free(MemoryMappingList *list)
{
    MemoryMapping *p, *q;

    QTAILQ_FOREACH_SAFE(p, &list->head, next, q) {
        QTAILQ_REMOVE(&list->head, p, next);
        g_free(p);
    }

    list->num = 0;
    list->last_mapping = NULL;
}

void memory_mapping_list_init(MemoryMappingList *list)
{
    list->num = 0;
    list->last_mapping = NULL;
    QTAILQ_INIT(&list->head);
}

void guest_phys_blocks_free(GuestPhysBlockList *list)
{
    GuestPhysBlock *p, *q;

    QTAILQ_FOREACH_SAFE(p, &list->head, next, q) {
        QTAILQ_REMOVE(&list->head, p, next);
        g_free(p);
    }
    list->num = 0;
}

void guest_phys_blocks_init(GuestPhysBlockList *list)
{
    list->num = 0;
    QTAILQ_INIT(&list->head);
}

typedef struct GuestPhysClient {
    GuestPhysBlockList *list;
    CPUPhysMemoryClient client;
} GuestPhysClient;

static void guest_phys_blocks_set_memory(struct CPUPhysMemoryClient *client,
                                         target_phys_addr_t target_start,
                                         ram_addr_t size,
                                         ram_addr_t ram_addr)
{
    GuestPhysClient *g;
    target_phys_addr_t target_end;
    uint8_t *host_addr;
    GuestPhysBlock *predecessor;

    /* we only care about RAM */
    if ((ram_addr & ~TARGET_PAGE_MASK) != 0) {
        return;
    }

    g           = container_of(client, GuestPhysClient, client);
    target_end  = target_start + size;
    host_addr   = qemu_get_ram_ptr(ram_addr);
    predecessor = NULL;

    /* find continuity in guest physical address space */
    if (!QTAILQ_EMPTY(&g->list->head)) {
        target_phys_addr_t predecessor_size;

        predecessor = QTAILQ_LAST(&g->list->head, GuestPhysBlockHead);
        predecessor_size = predecessor->target_end - predecessor->target_start;

        /* the memory API guarantees monotonically increasing traversal */
        g_assert(predecessor->target_end <= target_start);

        /* we want continuity in both guest-physical and host-virtual memory */
        if (predecessor->target_end < target_start ||
            predecessor->host_addr + predecessor_size != host_addr) {
            predecessor = NULL;
        }
    }

    if (predecessor == NULL) {
        /* isolated mapping, allocate it and add it to the list */
        GuestPhysBlock *block = g_malloc0(sizeof *block);

        block->target_start = target_start;
        block->target_end   = target_end;
        block->host_addr    = host_addr;

        QTAILQ_INSERT_TAIL(&g->list->head, block, next);
        ++g->list->num;
    } else {
        /* expand predecessor until @target_end; predecessor's start doesn't
         * change
         */
        predecessor->target_end = target_end;
    }

#ifdef DEBUG_GUEST_PHYS_REGION_ADD
    fprintf(stderr, "%s: target_start=" TARGET_FMT_plx " target_end="
            TARGET_FMT_plx ": %s (count: %u)\n", __FUNCTION__, target_start,
            target_end, predecessor ? "joined" : "added", g->list->num);
#endif
}

void guest_phys_blocks_append(GuestPhysBlockList *list)
{
    GuestPhysClient g = { 0 };

    g.list = list;
    g.client.set_memory = &guest_phys_blocks_set_memory;
    cpu_register_phys_memory_client(&g.client);
    cpu_unregister_phys_memory_client(&g.client);
}

#if defined(CONFIG_HAVE_GET_MEMORY_MAPPING)

static CPUArchState *find_paging_enabled_cpu(CPUArchState *start_cpu)
{
    CPUArchState *env;

    for (env = start_cpu; env != NULL; env = env->next_cpu) {
        if (cpu_paging_enabled(env)) {
            return env;
        }
    }

    return NULL;
}

int qemu_get_guest_memory_mapping(MemoryMappingList *list,
                                  const GuestPhysBlockList *guest_phys_blocks)
{
    CPUArchState *env, *first_paging_enabled_cpu;
    GuestPhysBlock *block;
    ram_addr_t offset, length;
    int ret;

    first_paging_enabled_cpu = find_paging_enabled_cpu(first_cpu);
    if (first_paging_enabled_cpu) {
        for (env = first_paging_enabled_cpu; env != NULL; env = env->next_cpu) {
            ret = cpu_get_memory_mapping(list, env);
            if (ret < 0) {
                return -1;
            }
        }
        return 0;
    }

    /*
     * If the guest doesn't use paging, the virtual address is equal to physical
     * address.
     */
    QTAILQ_FOREACH(block, &guest_phys_blocks->head, next) {
        offset = block->target_start;
        length = block->target_end - block->target_start;
        create_new_memory_mapping(list, offset, offset, length);
    }

    return 0;
}
#endif

void qemu_get_guest_simple_memory_mapping(MemoryMappingList *list,
                                   const GuestPhysBlockList *guest_phys_blocks)
{
    GuestPhysBlock *block;

    QTAILQ_FOREACH(block, &guest_phys_blocks->head, next) {
        create_new_memory_mapping(list, block->target_start, 0,
                                  block->target_end - block->target_start);
    }
}

void memory_mapping_filter(MemoryMappingList *list, int64_t begin,
                           int64_t length)
{
    MemoryMapping *cur, *next;

    QTAILQ_FOREACH_SAFE(cur, &list->head, next, next) {
        if (cur->phys_addr >= begin + length ||
            cur->phys_addr + cur->length <= begin) {
            QTAILQ_REMOVE(&list->head, cur, next);
            list->num--;
            continue;
        }

        if (cur->phys_addr < begin) {
            cur->length -= begin - cur->phys_addr;
            if (cur->virt_addr) {
                cur->virt_addr += begin - cur->phys_addr;
            }
            cur->phys_addr = begin;
        }

        if (cur->phys_addr + cur->length > begin + length) {
            cur->length -= cur->phys_addr + cur->length - begin - length;
        }
    }
}
