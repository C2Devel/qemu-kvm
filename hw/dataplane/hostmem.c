/*
 * Thread-safe guest to host memory mapping
 *
 * Copyright 2012 Red Hat, Inc. and/or its affiliates
 *
 * Authors:
 *   Stefan Hajnoczi <stefanha@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 *
 */

#include <linux/vhost.h>
#include "hw/pci.h" /* for range_*() helper functions */
#include "hw/vhost.h"
#include "hostmem.h"

/**
 * Map guest physical address to host pointer
 */
void *hostmem_lookup(HostMem *hostmem, uint64_t phys, uint64_t len,
                     bool is_write)
{
    struct vhost_memory_region *found = NULL;
    void *host_addr = NULL;
    uint64_t offset_within_region;
    unsigned int i;

    is_write = is_write; /*r/w information is currently not tracked */

    qemu_mutex_lock(&hostmem->mem_lock);
    for (i = 0; i < hostmem->mem->nregions; i++) {
        struct vhost_memory_region *region = &hostmem->mem->regions[i];

        if (range_covers_byte(region->guest_phys_addr,
                              region->memory_size,
                              phys)) {
            found = region;
            break;
        }
    }
    if (!found) {
        goto out;
    }
    offset_within_region = phys - found->guest_phys_addr;
    if (len <= found->memory_size - offset_within_region) {
        host_addr = (void*)(uintptr_t)(found->userspace_addr +
                                       offset_within_region);
    }
out:
    qemu_mutex_unlock(&hostmem->mem_lock);

    return host_addr;
}

static void hostmem_client_set_memory(CPUPhysMemoryClient *client,
                                      target_phys_addr_t start_addr,
                                      ram_addr_t size,
                                      ram_addr_t phys_offset)
{
    HostMem *hostmem = container_of(client, HostMem, client);
    ram_addr_t flags = phys_offset & ~TARGET_PAGE_MASK;
    size_t s = offsetof(struct vhost_memory, regions) +
               (hostmem->mem->nregions + 1) * sizeof hostmem->mem->regions[0];

    /* TODO: this is a hack.
     * At least one vga card (cirrus) changes the gpa to hva
     * memory maps on data path, which slows us down.
     * Since we should never need to DMA into VGA memory
     * anyway, lets just skip these regions. */
    if (ranges_overlap(start_addr, size, 0xa0000, 0x10000)) {
        return;
    }

    qemu_mutex_lock(&hostmem->mem_lock);

    hostmem->mem = qemu_realloc(hostmem->mem, s);

    assert(size);

    vhost_mem_unassign_memory(hostmem->mem, start_addr, size);
    if (flags == IO_MEM_RAM) {
        /* Add given mapping, merging adjacent regions if any */
        vhost_mem_assign_memory(hostmem->mem, start_addr, size,
                                (uintptr_t)qemu_get_ram_ptr(phys_offset));
    }

    qemu_mutex_unlock(&hostmem->mem_lock);
}

static int hostmem_client_sync_dirty_bitmap(struct CPUPhysMemoryClient *client,
                                            target_phys_addr_t start_addr,
                                            target_phys_addr_t end_addr)
{
    return 0;
}

static int hostmem_client_migration_log(struct CPUPhysMemoryClient *client,
                                        int enable)
{
    return 0;
}

void hostmem_init(HostMem *hostmem)
{
    memset(hostmem, 0, sizeof(*hostmem));

    qemu_mutex_init(&hostmem->mem_lock);

    hostmem->mem = qemu_mallocz(sizeof(*hostmem->mem));

    hostmem->client.set_memory = hostmem_client_set_memory;
    hostmem->client.sync_dirty_bitmap = hostmem_client_sync_dirty_bitmap;
    hostmem->client.migration_log = hostmem_client_migration_log;
    cpu_register_phys_memory_client(&hostmem->client);
}

void hostmem_finalize(HostMem *hostmem)
{
    cpu_unregister_phys_memory_client(&hostmem->client);
    qemu_mutex_destroy(&hostmem->mem_lock);
    qemu_free(hostmem->mem);
}
