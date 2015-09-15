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

#include "hmp.h"
#include "qmp-commands.h"

static void hmp_handle_error(Monitor *mon, Error **errp)
{
    if (error_is_set(errp)) {
        monitor_printf(mon, "%s\n", error_get_pretty(*errp));
        error_free(*errp);
    }
}

#ifdef CONFIG_LIVE_SNAPSHOTS
void hmp_drive_mirror(Monitor *mon, const QDict *qdict)
{
    const char *device = qdict_get_str(qdict, "device");
    const char *filename = qdict_get_try_str(qdict, "target");
    const char *format = qdict_get_try_str(qdict, "format");
    int reuse = qdict_get_try_bool(qdict, "reuse", 0);
    int full = qdict_get_try_bool(qdict, "full", 0);
    int speed = qdict_get_try_int(qdict, "speed", 0);
    enum NewImageMode mode;
    Error *errp = NULL;

    if (!filename) {
        error_set(&errp, QERR_MISSING_PARAMETER, "target");
        hmp_handle_error(mon, &errp);
        return;
    }

    if (reuse) {
        mode = NEW_IMAGE_MODE_EXISTING;
    } else {
        mode = NEW_IMAGE_MODE_ABSOLUTE_PATHS;
    }

    qmp___com_redhat_drive_mirror(device, filename, !!format, format,
				  qdict_haskey(qdict, "speed"), speed, true, full, true, mode, &errp);
    hmp_handle_error(mon, &errp);
}

void hmp_snapshot_blkdev(Monitor *mon, const QDict *qdict)
{
    const char *device = qdict_get_str(qdict, "device");
    const char *filename = qdict_get_try_str(qdict, "snapshot-file");
    const char *format = qdict_get_try_str(qdict, "format");
    int reuse = qdict_get_try_bool(qdict, "reuse", 0);
    enum NewImageMode mode;
    Error *errp = NULL;

    if (!filename) {
        /* In the future, if 'snapshot-file' is not specified, the snapshot
           will be taken internally. Today it's actually required. */
        error_set(&errp, QERR_MISSING_PARAMETER, "snapshot-file");
        hmp_handle_error(mon, &errp);
        return;
    }

    mode = reuse ? NEW_IMAGE_MODE_EXISTING : NEW_IMAGE_MODE_ABSOLUTE_PATHS;
    qmp_blockdev_snapshot_sync(device, filename, !!format, format,
                               true, mode, &errp);
    hmp_handle_error(mon, &errp);
}

void hmp_drive_reopen(Monitor *mon, const QDict *qdict)
{
    const char *device = qdict_get_str(qdict, "device");
    const char *filename = qdict_get_str(qdict, "new-image-file");
    const char *format = qdict_get_try_str(qdict, "format");
    Error *errp = NULL;

    qmp___com_redhat_drive_reopen(device, filename, !!format, format, false, NULL, &errp);
    hmp_handle_error(mon, &errp);
}
#endif

void hmp_dump_guest_memory(Monitor *mon, const QDict *qdict)
{
    Error *errp = NULL;
    int paging = qdict_get_try_bool(qdict, "paging", 0);
    const char *file = qdict_get_str(qdict, "filename");
    bool has_begin = qdict_haskey(qdict, "begin");
    bool has_length = qdict_haskey(qdict, "length");
    /* kdump-compressed format is not supported for HMP */
    bool has_format = false;
    int64_t begin = 0;
    int64_t length = 0;
    enum DumpGuestMemoryFormat dump_format = DUMP_GUEST_MEMORY_FORMAT_ELF;
    char *prot;

    if (has_begin) {
        begin = qdict_get_int(qdict, "begin");
    }
    if (has_length) {
        length = qdict_get_int(qdict, "length");
    }

    prot = g_strconcat("file:", file, NULL);
    qmp_dump_guest_memory(paging, prot, has_begin, begin, has_length, length,
                          has_format, dump_format, &errp);
    hmp_handle_error(mon, &errp);
    g_free(prot);
}

static void hmp_info_pci_device(Monitor *mon, const PciDeviceInfo *dev)
{
    PciMemoryRegionList *region;

    monitor_printf(mon, "  Bus %2" PRId64 ", ", dev->bus);
    monitor_printf(mon, "device %3" PRId64 ", function %" PRId64 ":\n",
                   dev->slot, dev->function);
    monitor_printf(mon, "    ");

    if (dev->class_info.has_desc) {
        monitor_printf(mon, "%s", dev->class_info.desc);
    } else {
        monitor_printf(mon, "Class %04" PRId64, dev->class_info.class);
    }

    monitor_printf(mon, ": PCI device %04" PRIx64 ":%04" PRIx64 "\n",
                   dev->id.vendor, dev->id.device);

    if (dev->has_irq) {
        monitor_printf(mon, "      IRQ %" PRId64 ".\n", dev->irq);
    }

    if (dev->has_pci_bridge) {
        monitor_printf(mon, "      BUS %" PRId64 ".\n",
                       dev->pci_bridge->bus.number);
        monitor_printf(mon, "      secondary bus %" PRId64 ".\n",
                       dev->pci_bridge->bus.secondary);
        monitor_printf(mon, "      subordinate bus %" PRId64 ".\n",
                       dev->pci_bridge->bus.subordinate);

        monitor_printf(mon, "      IO range [0x%04"PRIx64", 0x%04"PRIx64"]\n",
                       dev->pci_bridge->bus.io_range->base,
                       dev->pci_bridge->bus.io_range->limit);

        monitor_printf(mon,
                       "      memory range [0x%08"PRIx64", 0x%08"PRIx64"]\n",
                       dev->pci_bridge->bus.memory_range->base,
                       dev->pci_bridge->bus.memory_range->limit);

        monitor_printf(mon, "      prefetchable memory range "
                       "[0x%08"PRIx64", 0x%08"PRIx64"]\n",
                       dev->pci_bridge->bus.prefetchable_range->base,
                       dev->pci_bridge->bus.prefetchable_range->limit);
    }

    for (region = dev->regions; region; region = region->next) {
        uint64_t addr, size;

        addr = region->value->address;
        size = region->value->size;

        monitor_printf(mon, "      BAR%" PRId64 ": ", region->value->bar);

        if (!strcmp(region->value->type, "io")) {
            monitor_printf(mon, "I/O at 0x%04" PRIx64
                                " [0x%04" PRIx64 "].\n",
                           addr, addr + size - 1);
        } else {
            monitor_printf(mon, "%d bit%s memory at 0x%08" PRIx64
                               " [0x%08" PRIx64 "].\n",
                           region->value->mem_type_64 ? 64 : 32,
                           region->value->prefetch ? " prefetchable" : "",
                           addr, addr + size - 1);
        }
    }

    monitor_printf(mon, "      id \"%s\"\n", dev->qdev_id);

    if (dev->has_pci_bridge) {
        if (dev->pci_bridge->has_devices) {
            PciDeviceInfoList *cdev;
            for (cdev = dev->pci_bridge->devices; cdev; cdev = cdev->next) {
                hmp_info_pci_device(mon, cdev->value);
            }
        }
    }
}

void hmp_info_pci(Monitor *mon)
{
    PciInfoList *info_list, *info;
    Error *err = NULL;

    info_list = qmp_query_pci(&err);
    if (err) {
        monitor_printf(mon, "PCI devices not supported\n");
        error_free(err);
        return;
    }

    for (info = info_list; info; info = info->next) {
        PciDeviceInfoList *dev;

        for (dev = info->value->devices; dev; dev = dev->next) {
            hmp_info_pci_device(mon, dev->value);
        }
    }

    qapi_free_PciInfoList(info_list);
}
