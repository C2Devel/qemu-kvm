/*
 * qemu/kvm integration
 *
 * Copyright (C) 2006-2008 Qumranet Technologies
 *
 * Licensed under the terms of the GNU GPL version 2 or higher.
 */
#include "config.h"
#include "config-host.h"

#include <assert.h>
#include <string.h>
#include "hw/hw.h"
#include "sysemu.h"
#include "qemu-common.h"
#include "console.h"
#include "block.h"
#include "compatfd.h"
#include "gdbstub.h"
#include "monitor.h"
#include "cpus.h"

#include "qemu-kvm.h"

#define EXPECTED_KVM_API_VERSION 12

#if EXPECTED_KVM_API_VERSION != KVM_API_VERSION
#error libkvm: userspace and kernel version mismatch
#endif

#define ALIGN(x, y) (((x)+(y)-1) & ~((y)-1))

#ifdef KVM_CAP_IRQ_ROUTING
static inline void clear_gsi(KVMState *s, unsigned int gsi)
{
    uint32_t *bitmap = s->used_gsi_bitmap;

    if (gsi < s->gsi_count) {
        bitmap[gsi / 32] &= ~(1U << (gsi % 32));
    } else {
        DPRINTF("Invalid GSI %u\n", gsi);
    }
}
#endif

#ifdef KVM_CAP_DEVICE_ASSIGNMENT
int kvm_assign_pci_device(KVMState *s,
                          struct kvm_assigned_pci_dev *assigned_dev)
{
    return kvm_vm_ioctl(s, KVM_ASSIGN_PCI_DEVICE, assigned_dev);
}

static int kvm_old_assign_irq(KVMState *s,
                              struct kvm_assigned_irq *assigned_irq)
{
    return kvm_vm_ioctl(s, KVM_ASSIGN_IRQ, assigned_irq);
}

int kvm_device_intx_set_mask(KVMState *s, uint32_t dev_id, bool masked)
{
    struct kvm_assigned_pci_dev assigned_dev;

    assigned_dev.assigned_dev_id = dev_id;
    assigned_dev.flags = masked ? KVM_DEV_ASSIGN_MASK_INTX : 0;
    return kvm_vm_ioctl(s, KVM_ASSIGN_SET_INTX_MASK, &assigned_dev);
}

#ifdef KVM_CAP_ASSIGN_DEV_IRQ
int kvm_assign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq)
{
    int ret;

    ret = kvm_ioctl(s, KVM_CHECK_EXTENSION, KVM_CAP_ASSIGN_DEV_IRQ);
    if (ret > 0) {
        return kvm_vm_ioctl(s, KVM_ASSIGN_DEV_IRQ, assigned_irq);
    }

    return kvm_old_assign_irq(s, assigned_irq);
}

int kvm_deassign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq)
{
    return kvm_vm_ioctl(s, KVM_DEASSIGN_DEV_IRQ, assigned_irq);
}
#else
int kvm_assign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq)
{
    return kvm_old_assign_irq(s, assigned_irq);
}
#endif
#endif

#ifdef KVM_CAP_DEVICE_DEASSIGNMENT
int kvm_deassign_pci_device(KVMState *s,
                            struct kvm_assigned_pci_dev *assigned_dev)
{
    return kvm_vm_ioctl(s, KVM_DEASSIGN_PCI_DEVICE, assigned_dev);
}
#endif

int kvm_del_routing_entry(struct kvm_irq_routing_entry *entry)
{
#ifdef KVM_CAP_IRQ_ROUTING
    KVMState *s = kvm_state;
    struct kvm_irq_routing_entry *e, *p;
    int i, gsi, found = 0;

    gsi = entry->gsi;

    for (i = 0; i < s->irq_routes->nr; ++i) {
        e = &s->irq_routes->entries[i];
        if (e->type == entry->type && e->gsi == gsi) {
            switch (e->type) {
            case KVM_IRQ_ROUTING_IRQCHIP:{
                    if (e->u.irqchip.irqchip ==
                        entry->u.irqchip.irqchip
                        && e->u.irqchip.pin == entry->u.irqchip.pin) {
                        p = &s->irq_routes->entries[--s->irq_routes->nr];
                        *e = *p;
                        found = 1;
                    }
                    break;
                }
            case KVM_IRQ_ROUTING_MSI:{
                    if (e->u.msi.address_lo ==
                        entry->u.msi.address_lo
                        && e->u.msi.address_hi ==
                        entry->u.msi.address_hi
                        && e->u.msi.data == entry->u.msi.data) {
                        p = &s->irq_routes->entries[--s->irq_routes->nr];
                        *e = *p;
                        found = 1;
                    }
                    break;
                }
            default:
                break;
            }
            if (found) {
                /* If there are no other users of this GSI
                 * mark it available in the bitmap */
                for (i = 0; i < s->irq_routes->nr; i++) {
                    e = &s->irq_routes->entries[i];
                    if (e->gsi == gsi)
                        break;
                }
                if (i == s->irq_routes->nr) {
                    clear_gsi(s, gsi);
                }

                return 0;
            }
        }
    }
    return -ESRCH;
#else
    return -ENOSYS;
#endif
}

int kvm_update_routing_entry(struct kvm_irq_routing_entry *entry,
                             struct kvm_irq_routing_entry *newentry)
{
#ifdef KVM_CAP_IRQ_ROUTING
    KVMState *s = kvm_state;
    struct kvm_irq_routing_entry *e;
    int i;

    if (entry->gsi != newentry->gsi || entry->type != newentry->type) {
        return -EINVAL;
    }

    for (i = 0; i < s->irq_routes->nr; ++i) {
        e = &s->irq_routes->entries[i];
        if (e->type != entry->type || e->gsi != entry->gsi) {
            continue;
        }
        switch (e->type) {
        case KVM_IRQ_ROUTING_IRQCHIP:
            if (e->u.irqchip.irqchip == entry->u.irqchip.irqchip &&
                e->u.irqchip.pin == entry->u.irqchip.pin) {
                memcpy(&e->u.irqchip, &newentry->u.irqchip,
                       sizeof e->u.irqchip);
                return 0;
            }
            break;
        case KVM_IRQ_ROUTING_MSI:
            if (e->u.msi.address_lo == entry->u.msi.address_lo &&
                e->u.msi.address_hi == entry->u.msi.address_hi &&
                e->u.msi.data == entry->u.msi.data) {
                memcpy(&e->u.msi, &newentry->u.msi, sizeof e->u.msi);
                return 0;
            }
            break;
        default:
            break;
        }
    }
    return -ESRCH;
#else
    return -ENOSYS;
#endif
}

int kvm_get_irq_route_gsi(void)
{
#ifdef KVM_CAP_IRQ_ROUTING
    KVMState *s = kvm_state;
    int max_words = ALIGN(s->gsi_count, 32) / 32;
    int i, bit;
    uint32_t *buf = s->used_gsi_bitmap;

    /* Return the lowest unused GSI in the bitmap */
    for (i = 0; i < max_words; i++) {
        bit = ffs(~buf[i]);
        if (!bit) {
            continue;
        }

        return bit - 1 + i * 32;
    }

    return -ENOSPC;
#else
    return -ENOSYS;
#endif
}

#ifdef KVM_CAP_IRQ_ROUTING
static void kvm_msi_routing_entry(struct kvm_irq_routing_entry *e,
                                  KVMMsiMessage *msg)

{
    e->gsi = msg->gsi;
    e->type = KVM_IRQ_ROUTING_MSI;
    e->flags = 0;
    e->u.msi.address_lo = msg->addr_lo;
    e->u.msi.address_hi = msg->addr_hi;
    e->u.msi.data = msg->data;
}
#endif

int kvm_msi_message_add(KVMMsiMessage *msg)
{
#ifdef KVM_CAP_IRQ_ROUTING
    struct kvm_irq_routing_entry e;
    int ret;

    ret = kvm_get_irq_route_gsi();
    if (ret < 0) {
        return ret;
    }
    msg->gsi = ret;

    kvm_msi_routing_entry(&e, msg);
    kvm_add_routing_entry(kvm_state, &e);
    return 0;
#else
    return -ENOSYS;
#endif
}

int kvm_msi_message_del(KVMMsiMessage *msg)
{
#ifdef KVM_CAP_IRQ_ROUTING
    struct kvm_irq_routing_entry e;

    kvm_msi_routing_entry(&e, msg);
    return kvm_del_routing_entry(&e);
#else
    return -ENOSYS;
#endif
}

int kvm_msi_message_update(KVMMsiMessage *old, KVMMsiMessage *new)
{
#ifdef KVM_CAP_IRQ_ROUTING
    struct kvm_irq_routing_entry e1, e2;
    int ret;

    new->gsi = old->gsi;
    if (memcmp(old, new, sizeof(KVMMsiMessage)) == 0) {
        return 0;
    }

    kvm_msi_routing_entry(&e1, old);
    kvm_msi_routing_entry(&e2, new);

    ret = kvm_update_routing_entry(&e1, &e2);
    if (ret < 0) {
        return ret;
    }

    return 1;
#else
    return -ENOSYS;
#endif
}


#ifdef KVM_CAP_DEVICE_MSIX
int kvm_assign_set_msix_nr(KVMState *s, struct kvm_assigned_msix_nr *msix_nr)
{
    return kvm_vm_ioctl(s, KVM_ASSIGN_SET_MSIX_NR, msix_nr);
}

int kvm_assign_set_msix_entry(KVMState *s,
                              struct kvm_assigned_msix_entry *entry)
{
    return kvm_vm_ioctl(s, KVM_ASSIGN_SET_MSIX_ENTRY, entry);
}
#endif

#if !defined(TARGET_I386)
void kvm_arch_init_irq_routing(KVMState *s)
{
}
#endif
