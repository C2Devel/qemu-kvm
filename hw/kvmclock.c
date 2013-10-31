/*
 * QEMU KVM support, paravirtual clock device
 *
 * Copyright (C) 2011 Siemens AG
 *
 * Authors:
 *  Jan Kiszka        <jan.kiszka@siemens.com>
 *
 * This work is licensed under the terms of the GNU GPL version 2.
 * See the COPYING file in the top-level directory.
 *
 */

#include "qemu-common.h"
#include "sysemu.h"
#include "sysbus.h"
#include "kvm.h"
#include "kvmclock.h"

#if defined(KVM_CAP_ADJUST_CLOCK)

#include <linux/kvm.h>
#include <linux/kvm_para.h>

typedef struct KVMClockState {
    uint64_t clock;
    bool clock_valid;
} KVMClockState;

static KVMClockState kvmclock_state;

static void kvmclock_vm_state_change(void *opaque, int running, RunState state)
{
    KVMClockState *s = opaque;
    CPUState *penv = first_cpu;
    int cap_clock_ctrl = kvm_check_extension(kvm_state, KVM_CAP_KVMCLOCK_CTRL);
    int ret;

    if (running) {
        struct kvm_clock_data data;

        s->clock_valid = false;

        data.clock = s->clock;
        data.flags = 0;
        ret = kvm_vm_ioctl(kvm_state, KVM_SET_CLOCK, &data);
        if (ret < 0) {
            fprintf(stderr, "KVM_SET_CLOCK failed: %s\n", strerror(ret));
            abort();
        }

        if (!cap_clock_ctrl) {
            return;
        }
        for (penv = first_cpu; penv != NULL; penv = penv->next_cpu) {
            ret = kvm_vcpu_ioctl(penv, KVM_KVMCLOCK_CTRL, 0);
            if (ret) {
                if (ret != -EINVAL) {
                    fprintf(stderr, "%s: %s\n", __func__, strerror(-ret));
                }
                return;
            }
        }
    } else {
        struct kvm_clock_data data;
        int ret;

        if (s->clock_valid) {
            return;
        }
        ret = kvm_vm_ioctl(kvm_state, KVM_GET_CLOCK, &data);
        if (ret < 0) {
            fprintf(stderr, "KVM_GET_CLOCK failed: %s\n", strerror(ret));
            abort();
        }
        s->clock = data.clock;

        /*
         * If the VM is stopped, declare the clock state valid to
         * avoid re-reading it on next vmsave (which would return
         * a different value). Will be reset when the VM is continued.
         */
        s->clock_valid = true;
    }
}

static const VMStateDescription kvmclock_vmsd = {
    .name = "kvmclock",
    .version_id = 1,
    .minimum_version_id = 1,
    .minimum_version_id_old = 1,
    .fields = (VMStateField[]) {
        VMSTATE_UINT64(clock, KVMClockState),
        VMSTATE_END_OF_LIST()
    }
};

/* Note: Must be called after VCPU initialization. */
void kvmclock_create(void)
{
    if (kvm_enabled() && kvm_check_extension(kvm_state, KVM_CAP_ADJUST_CLOCK)  &&
        first_cpu->cpuid_kvm_features & ((1ULL << KVM_FEATURE_CLOCKSOURCE)
#ifdef KVM_FEATURE_CLOCKSOURCE2
        || (1ULL << KVM_FEATURE_CLOCKSOURCE2)
#endif
    )) {
        vmstate_register(NULL, 0, &kvmclock_vmsd, &kvmclock_state);
    	qemu_add_vm_change_state_handler(kvmclock_vm_state_change, &kvmclock_state);
    }
}

#else /* !(KVM_CAP_ADJUST_CLOCK) */
void kvmclock_create(void)
{
}
#endif /* !(KVM_CAP_ADJUST_CLOCK) */
