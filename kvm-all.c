/*
 * QEMU KVM support
 *
 * Copyright IBM, Corp. 2008
 *           Red Hat, Inc. 2008
 *
 * Authors:
 *  Anthony Liguori   <aliguori@us.ibm.com>
 *  Glauber Costa     <gcosta@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 *
 */

#include <sys/types.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <stdarg.h>

#include <linux/kvm.h>

#include "qemu-common.h"
#include "sysemu.h"
#include "hw/hw.h"
#include "gdbstub.h"
#include "kvm.h"

/* This check must be after config-host.h is included */
#ifdef CONFIG_EVENTFD
#include <sys/eventfd.h>
#endif

int kvm_irqchip_in_kernel(void)
{
    return kvm_state->irqchip_in_kernel;
}

int kvm_coalesce_mmio_region(target_phys_addr_t start, ram_addr_t size)
{
    int ret = -ENOSYS;
#ifdef KVM_CAP_COALESCED_MMIO
    KVMState *s = kvm_state;

    if (s->coalesced_mmio) {
        struct kvm_coalesced_mmio_zone zone;

        zone.addr = start;
        zone.size = size;

        ret = kvm_vm_ioctl(s, KVM_REGISTER_COALESCED_MMIO, &zone);
    }
#endif

    return ret;
}

int kvm_uncoalesce_mmio_region(target_phys_addr_t start, ram_addr_t size)
{
    int ret = -ENOSYS;
#ifdef KVM_CAP_COALESCED_MMIO
    KVMState *s = kvm_state;

    if (s->coalesced_mmio) {
        struct kvm_coalesced_mmio_zone zone;

        zone.addr = start;
        zone.size = size;

        ret = kvm_vm_ioctl(s, KVM_UNREGISTER_COALESCED_MMIO, &zone);
    }
#endif

    return ret;
}

int kvm_check_extension(KVMState *s, unsigned int extension)
{
    int ret;

    ret = kvm_ioctl(s, KVM_CHECK_EXTENSION, extension);
    if (ret < 0) {
        ret = 0;
    }

    return ret;
}

int kvm_check_many_ioeventfds(void)
{
    /* Older kernels have a 6 device limit on the KVM io bus.  Find out so we
     * can avoid creating too many ioeventfds.
     */
#ifdef CONFIG_EVENTFD
    int ioeventfds[7];
    int i, ret = 0;
    for (i = 0; i < ARRAY_SIZE(ioeventfds); i++) {
        ioeventfds[i] = eventfd(0, EFD_CLOEXEC);
        if (ioeventfds[i] < 0) {
            break;
        }
        ret = kvm_set_ioeventfd_pio_word(ioeventfds[i], 0, i, true);
        if (ret < 0) {
            close(ioeventfds[i]);
            break;
        }
    }

    /* Decide whether many devices are supported or not */
    ret = i == ARRAY_SIZE(ioeventfds);

    while (i-- > 0) {
        kvm_set_ioeventfd_pio_word(ioeventfds[i], 0, i, false);
        close(ioeventfds[i]);
    }
    return ret;
#else
    return 0;
#endif
}

static int kvm_handle_io(uint16_t port, void *data, int direction, int size,
                         uint32_t count)
{
    int i;
    uint8_t *ptr = data;

    for (i = 0; i < count; i++) {
        if (direction == KVM_EXIT_IO_IN) {
            switch (size) {
            case 1:
                stb_p(ptr, cpu_inb(port));
                break;
            case 2:
                stw_p(ptr, cpu_inw(port));
                break;
            case 4:
                stl_p(ptr, cpu_inl(port));
                break;
            }
        } else {
            switch (size) {
            case 1:
                cpu_outb(port, ldub_p(ptr));
                break;
            case 2:
                cpu_outw(port, lduw_p(ptr));
                break;
            case 4:
                cpu_outl(port, ldl_p(ptr));
                break;
            }
        }

        ptr += size;
    }

    return 1;
}

int kvm_ioctl(KVMState *s, int type, ...)
{
    int ret;
    void *arg;
    va_list ap;

    va_start(ap, type);
    arg = va_arg(ap, void *);
    va_end(ap);

    ret = ioctl(s->fd, type, arg);
    if (ret == -1)
        ret = -errno;

    return ret;
}

int kvm_vm_ioctl(KVMState *s, int type, ...)
{
    int ret;
    void *arg;
    va_list ap;

    va_start(ap, type);
    arg = va_arg(ap, void *);
    va_end(ap);

    ret = ioctl(s->vmfd, type, arg);
    if (ret == -1)
        ret = -errno;

    return ret;
}

int kvm_vcpu_ioctl(CPUState *env, int type, ...)
{
    int ret;
    void *arg;
    va_list ap;

    va_start(ap, type);
    arg = va_arg(ap, void *);
    va_end(ap);

    ret = ioctl(env->kvm_fd, type, arg);
    if (ret == -1)
        ret = -errno;

    return ret;
}

int kvm_has_sync_mmu(void)
{
#ifdef KVM_CAP_SYNC_MMU
    KVMState *s = kvm_state;

    return kvm_check_extension(s, KVM_CAP_SYNC_MMU);
#else
    return 0;
#endif
}

int kvm_has_vcpu_events(void)
{
    return kvm_state->vcpu_events;
}

int kvm_has_many_ioeventfds(void)
{
    if (!kvm_enabled()) {
        return 0;
    }
    return kvm_state->many_ioeventfds;
}

#ifdef KVM_CAP_SET_GUEST_DEBUG

struct kvm_sw_breakpoint *kvm_find_sw_breakpoint(CPUState *env,
                                                 target_ulong pc)
{
    struct kvm_sw_breakpoint *bp;

    QTAILQ_FOREACH(bp, &env->kvm_state->kvm_sw_breakpoints, entry) {
        if (bp->pc == pc)
            return bp;
    }
    return NULL;
}

int kvm_sw_breakpoints_active(CPUState *env)
{
    return !QTAILQ_EMPTY(&env->kvm_state->kvm_sw_breakpoints);
}

int kvm_insert_breakpoint(CPUState *current_env, target_ulong addr,
                          target_ulong len, int type)
{
    struct kvm_sw_breakpoint *bp;
    CPUState *env;
    int err;

    if (type == GDB_BREAKPOINT_SW) {
        bp = kvm_find_sw_breakpoint(current_env, addr);
        if (bp) {
            bp->use_count++;
            return 0;
        }

        bp = qemu_malloc(sizeof(struct kvm_sw_breakpoint));
        if (!bp)
            return -ENOMEM;

        bp->pc = addr;
        bp->use_count = 1;
        err = kvm_arch_insert_sw_breakpoint(current_env, bp);
        if (err) {
            free(bp);
            return err;
        }

        QTAILQ_INSERT_HEAD(&current_env->kvm_state->kvm_sw_breakpoints,
                          bp, entry);
    } else {
        err = kvm_arch_insert_hw_breakpoint(addr, len, type);
        if (err)
            return err;
    }

    for (env = first_cpu; env != NULL; env = env->next_cpu) {
        err = kvm_update_guest_debug(env, 0);
        if (err)
            return err;
    }
    return 0;
}

int kvm_remove_breakpoint(CPUState *current_env, target_ulong addr,
                          target_ulong len, int type)
{
    struct kvm_sw_breakpoint *bp;
    CPUState *env;
    int err;

    if (type == GDB_BREAKPOINT_SW) {
        bp = kvm_find_sw_breakpoint(current_env, addr);
        if (!bp)
            return -ENOENT;

        if (bp->use_count > 1) {
            bp->use_count--;
            return 0;
        }

        err = kvm_arch_remove_sw_breakpoint(current_env, bp);
        if (err)
            return err;

        QTAILQ_REMOVE(&current_env->kvm_state->kvm_sw_breakpoints, bp, entry);
        qemu_free(bp);
    } else {
        err = kvm_arch_remove_hw_breakpoint(addr, len, type);
        if (err)
            return err;
    }

    for (env = first_cpu; env != NULL; env = env->next_cpu) {
        err = kvm_update_guest_debug(env, 0);
        if (err)
            return err;
    }
    return 0;
}

void kvm_remove_all_breakpoints(CPUState *current_env)
{
    struct kvm_sw_breakpoint *bp, *next;
    KVMState *s = current_env->kvm_state;
    CPUState *env;

    QTAILQ_FOREACH_SAFE(bp, &s->kvm_sw_breakpoints, entry, next) {
        if (kvm_arch_remove_sw_breakpoint(current_env, bp) != 0) {
            /* Try harder to find a CPU that currently sees the breakpoint. */
            for (env = first_cpu; env != NULL; env = env->next_cpu) {
                if (kvm_arch_remove_sw_breakpoint(env, bp) == 0)
                    break;
            }
        }
    }
    kvm_arch_remove_all_hw_breakpoints();

    for (env = first_cpu; env != NULL; env = env->next_cpu)
        kvm_update_guest_debug(env, 0);
}

#else /* !KVM_CAP_SET_GUEST_DEBUG */

int kvm_update_guest_debug(CPUState *env, unsigned long reinject_trap)
{
    return -EINVAL;
}

int kvm_insert_breakpoint(CPUState *current_env, target_ulong addr,
                          target_ulong len, int type)
{
    return -EINVAL;
}

int kvm_remove_breakpoint(CPUState *current_env, target_ulong addr,
                          target_ulong len, int type)
{
    return -EINVAL;
}

void kvm_remove_all_breakpoints(CPUState *current_env)
{
}
#endif /* !KVM_CAP_SET_GUEST_DEBUG */

#ifdef KVM_IOEVENTFD
int kvm_set_ioeventfd_pio_word(int fd, uint16_t addr, uint16_t val, bool assign)
{
    struct kvm_ioeventfd kick = {
        .datamatch = val,
        .addr = addr,
        .len = 2,
        .flags = KVM_IOEVENTFD_FLAG_DATAMATCH | KVM_IOEVENTFD_FLAG_PIO,
        .fd = fd,
    };
    int r;
    if (!kvm_enabled())
        return -ENOSYS;
    if (!assign)
        kick.flags |= KVM_IOEVENTFD_FLAG_DEASSIGN;
    r = kvm_vm_ioctl(kvm_state, KVM_IOEVENTFD, &kick);
    if (r < 0)
        return r;
    return 0;
}
#endif

#if defined(KVM_IRQFD)
int kvm_set_irqfd(int gsi, int fd, bool assigned)
{
    struct kvm_irqfd irqfd = {
        .fd = fd,
        .gsi = gsi,
        .flags = assigned ? 0 : KVM_IRQFD_FLAG_DEASSIGN,
    };
    int r;
    if (!kvm_enabled() || !kvm_irqchip_in_kernel())
        return -ENOSYS;

    r = kvm_vm_ioctl(kvm_state, KVM_IRQFD, &irqfd);
    if (r < 0)
        return r;
    return 0;
}
#endif

#include "qemu-kvm.c"
