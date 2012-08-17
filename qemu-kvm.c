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

#ifdef KVM_CAP_DEVICE_ASSIGNMENT
static int kvm_old_assign_irq(KVMState *s,
                              struct kvm_assigned_irq *assigned_irq)
{
    return kvm_vm_ioctl(s, KVM_ASSIGN_IRQ, assigned_irq);
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
#else
int kvm_assign_irq(KVMState *s, struct kvm_assigned_irq *assigned_irq)
{
    return kvm_old_assign_irq(s, assigned_irq);
}
#endif
#endif

#if !defined(TARGET_I386)
void kvm_arch_init_irq_routing(KVMState *s)
{
}
#endif
