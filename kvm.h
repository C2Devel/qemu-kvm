/*
 * QEMU KVM support
 *
 * Copyright IBM, Corp. 2008
 *
 * Authors:
 *  Anthony Liguori   <aliguori@us.ibm.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 *
 */

#ifndef QEMU_KVM_H
#define QEMU_KVM_H

#include <errno.h>
#include "config.h"
#include "qemu-queue.h"
#include "qemu-kvm.h"

int kvm_has_vcpu_events(void);
int kvm_put_vcpu_events(CPUState *env);
int kvm_get_vcpu_events(CPUState *env);

void kvm_flush_coalesced_mmio_buffer(void);

void kvm_arch_reset_vcpu(CPUState *env);

/* Returns VCPU ID to be used on KVM_CREATE_VCPU ioctl() */
unsigned long kvm_arch_vcpu_id(CPUArchState *env);


int kvm_has_many_ioeventfds(void);

#if defined(KVM_IOEVENTFD) && defined(CONFIG_KVM)
int kvm_set_ioeventfd_pio_word(int fd, uint16_t adr, uint16_t val, bool assign);
int kvm_check_many_ioeventfds(void);
#else
static inline
int kvm_set_ioeventfd_pio_word(int fd, uint16_t adr, uint16_t val, bool assign)
{
    return -ENOSYS;
}
static inline
int kvm_check_many_ioeventfds(void)
{
    return 0;
}
#endif

#if defined(KVM_IRQFD) && defined(CONFIG_KVM)
int kvm_set_irqfd(int gsi, int fd, bool assigned);
#else
static inline
int kvm_set_irqfd(int gsi, int fd, bool assigned)
{
    return -ENOSYS;
}
#endif

#endif
