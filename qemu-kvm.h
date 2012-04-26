/*
 * qemu/kvm integration
 *
 * Copyright (C) 2006-2008 Qumranet Technologies
 *
 * Licensed under the terms of the GNU GPL version 2 or higher.
 */
#ifndef THE_ORIGINAL_AND_TRUE_QEMU_KVM_H
#define THE_ORIGINAL_AND_TRUE_QEMU_KVM_H

#include "cpu.h"

#include <signal.h>
#include <stdlib.h>

#ifdef CONFIG_KVM

#include <stdint.h>

#ifndef __user
#define __user       /* temporary, until installed via make headers_install */
#endif

#include <linux/kvm.h>

#include <signal.h>

/* FIXME: share this number with kvm */
/* FIXME: or dynamically alloc/realloc regions */
#define KVM_MAX_NUM_MEM_REGIONS 32u
#define MAX_VCPUS 16

#include "kvm.h"

/*!
 * \brief Notifies host kernel about a PCI device to be assigned to a guest
 *
 * Used for PCI device assignment, this function notifies the host
 * kernel about the assigning of the physical PCI device to a guest.
 *
 * \param kvm Pointer to the current kvm_context
 * \param assigned_dev Parameters, like bus, devfn number, etc
 */
int kvm_assign_pci_device(KVMState *s,
                          struct kvm_assigned_pci_dev *assigned_dev);

/*!
 * \brief Assign IRQ for an assigned device
 *
 * Used for PCI device assignment, this function assigns IRQ numbers for
 * an physical device and guest IRQ handling.
 *
 * \param kvm Pointer to the current kvm_context
 * \param assigned_irq Parameters, like dev id, host irq, guest irq, etc
 */
int kvm_assign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq);

/*!
 * \brief Deassign IRQ for an assigned device
 *
 * Used for PCI device assignment, this function deassigns IRQ numbers
 * for an assigned device.
 *
 * \param kvm Pointer to the current kvm_context
 * \param assigned_irq Parameters, like dev id, host irq, guest irq, etc
 */
int kvm_deassign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq);

int kvm_device_intx_set_mask(KVMState *s, uint32_t dev_id, bool masked);

/*!
 * \brief Notifies host kernel about a PCI device to be deassigned from a guest
 *
 * Used for hot remove PCI device, this function notifies the host
 * kernel about the deassigning of the physical PCI device from a guest.
 *
 * \param kvm Pointer to the current kvm_context
 * \param assigned_dev Parameters, like bus, devfn number, etc
 */
int kvm_deassign_pci_device(KVMState *s,
                            struct kvm_assigned_pci_dev *assigned_dev);

/*!
 * \brief Clears the temporary irq routing table
 *
 * Clears the temporary irq routing table.  Nothing is committed to the
 * running VM.
 *
 */
int kvm_clear_gsi_routes(void);

/*!
 * \brief Removes an irq route from the temporary irq routing table
 *
 * Adds an irq route to the temporary irq routing table.  Nothing is
 * committed to the running VM.
 */
int kvm_del_irq_route(int gsi, int irqchip, int pin);

struct kvm_irq_routing_entry;

void kvm_add_routing_entry(KVMState *s, struct kvm_irq_routing_entry *entry);

/*!
 * \brief Removes a routing from the temporary irq routing table
 *
 * Remove a routing to the temporary irq routing table.  Nothing is
 * committed to the running VM.
 */
int kvm_del_routing_entry(struct kvm_irq_routing_entry *entry);

/*!
 * \brief Updates a routing in the temporary irq routing table
 *
 * Update a routing in the temporary irq routing table
 * with a new value. entry type and GSI can not be changed.
 * Nothing is committed to the running VM.
 */
int kvm_update_routing_entry(struct kvm_irq_routing_entry *entry,
                             struct kvm_irq_routing_entry *newentry);


int kvm_assign_set_msix_nr(KVMState *s, struct kvm_assigned_msix_nr *msix_nr);
int kvm_assign_set_msix_entry(KVMState *s,
                              struct kvm_assigned_msix_entry *entry);

#endif /* CONFIG_KVM */

int kvm_add_ioport_region(unsigned long start, unsigned long size,
                          bool is_hot_plug);
int kvm_remove_ioport_region(unsigned long start, unsigned long size,
                             bool is_hot_unplug);

int kvm_update_ioport_access(CPUState *env);
int kvm_arch_set_ioport_access(unsigned long start, unsigned long size,
                               bool enable);

#endif
