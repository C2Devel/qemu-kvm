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

#ifndef HOSTMEM_H
#define HOSTMEM_H

#include "hw/hw.h"
#include "qemu-thread.h"

struct vhost_memory;
typedef struct {
    CPUPhysMemoryClient client;
    QemuMutex mem_lock;
    struct vhost_memory *mem;
} HostMem;

void hostmem_init(HostMem *hostmem);
void hostmem_finalize(HostMem *hostmem);

/**
 * Map a guest physical address to a pointer
 *
 * Note that there is no map/unmap mechanism here.  The caller must ensure that
 * mapped memory is no longer used across events like hot memory unplug.  This
 * can be done with other mechanisms like bdrv_drain_all() that quiesce
 * in-flight I/O.
 */
void *hostmem_lookup(HostMem *hostmem, uint64_t phys, uint64_t len,
                     bool is_write);

#endif /* HOSTMEM_H */
