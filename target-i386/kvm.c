/*
 * QEMU KVM support
 *
 * Copyright (C) 2006-2008 Qumranet Technologies
 * Copyright IBM, Corp. 2008
 *
 * Authors:
 *  Anthony Liguori   <aliguori@us.ibm.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 *
 */

#include <sys/types.h>
#include <sys/ioctl.h>
#include <sys/mman.h>

#include <linux/kvm.h>

#include "qemu-common.h"
#include "sysemu.h"
#include "kvm.h"
#include "cpu.h"
#include "gdbstub.h"
#include "host-utils.h"

static void kvm_clear_vapic(CPUState *env)
{
#ifdef KVM_SET_VAPIC_ADDR
    struct kvm_vapic_addr va = {
        .vapic_addr = 0,
    };

    kvm_vcpu_ioctl(env, KVM_SET_VAPIC_ADDR, &va);
#endif
}

void kvm_arch_reset_vcpu(CPUState *env)
{
    kvm_clear_vapic(env);
    env->interrupt_injected = -1;
    env->nmi_injected = 0;
    env->nmi_pending = 0;
    /* Legal xcr0 for loading */
    env->xcr0 = 1;
}

int kvm_put_vcpu_events(CPUState *env)
{
#ifdef KVM_CAP_VCPU_EVENTS
    struct kvm_vcpu_events events;

    if (!kvm_has_vcpu_events()) {
        return 0;
    }

    events.exception.injected = (env->exception_injected >= 0);
    events.exception.nr = env->exception_injected;
    events.exception.has_error_code = env->has_error_code;
    events.exception.error_code = env->error_code;

    events.interrupt.injected = (env->interrupt_injected >= 0);
    events.interrupt.nr = env->interrupt_injected;
    events.interrupt.soft = env->soft_interrupt;

    events.nmi.injected = env->nmi_injected;
    events.nmi.pending = env->nmi_pending;
    events.nmi.masked = !!(env->hflags2 & HF2_NMI_MASK);

    events.sipi_vector = env->sipi_vector;

    events.flags =
        KVM_VCPUEVENT_VALID_NMI_PENDING | KVM_VCPUEVENT_VALID_SIPI_VECTOR;

    return kvm_vcpu_ioctl(env, KVM_SET_VCPU_EVENTS, &events);
#else
    return 0;
#endif
}

int kvm_get_vcpu_events(CPUState *env)
{
#ifdef KVM_CAP_VCPU_EVENTS
    struct kvm_vcpu_events events;
    int ret;

    if (!kvm_has_vcpu_events()) {
        return 0;
    }

    ret = kvm_vcpu_ioctl(env, KVM_GET_VCPU_EVENTS, &events);
    if (ret < 0) {
       return ret;
    }
    env->exception_injected =
       events.exception.injected ? events.exception.nr : -1;
    env->has_error_code = events.exception.has_error_code;
    env->error_code = events.exception.error_code;

    env->interrupt_injected =
        events.interrupt.injected ? events.interrupt.nr : -1;
    env->soft_interrupt = events.interrupt.soft;

    env->nmi_injected = events.nmi.injected;
    env->nmi_pending = events.nmi.pending;
    if (events.nmi.masked) {
        env->hflags2 |= HF2_NMI_MASK;
    } else {
        env->hflags2 &= ~HF2_NMI_MASK;
    }

    env->sipi_vector = events.sipi_vector;
#endif

    return 0;
}

int kvm_arch_post_run(CPUState *env, struct kvm_run *run)
{
    if (run->if_flag)
        env->eflags |= IF_MASK;
    else
        env->eflags &= ~IF_MASK;
    
    cpu_set_apic_tpr(env, run->cr8);
    cpu_set_apic_base(env, run->apic_base);

    return 0;
}

#include "qemu-kvm-x86.c"
