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
 * \brief Assign IRQ for an assigned device
 *
 * Used for PCI device assignment, this function assigns IRQ numbers for
 * an physical device and guest IRQ handling.
 *
 * \param kvm Pointer to the current kvm_context
 * \param assigned_irq Parameters, like dev id, host irq, guest irq, etc
 */
int kvm_assign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq);

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

#endif
