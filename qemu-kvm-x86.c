/*
 * qemu/kvm integration, x86 specific code
 *
 * Copyright (C) 2006-2008 Qumranet Technologies
 *
 * Licensed under the terms of the GNU GPL version 2 or higher.
 */

#include "config.h"
#include "config-host.h"

#include <string.h>
#include "hw/hw.h"
#include "gdbstub.h"
#include <sys/io.h>

#include "qemu-kvm.h"
#include "libkvm.h"
#include <pthread.h>
#include <sys/utsname.h>
#include <linux/kvm_para.h>
#include <sys/ioctl.h>

#include "kvm.h"
#include "hw/pc.h"
#include "hyperv.h"

#define MSR_IA32_TSC		0x10

static struct kvm_msr_list *kvm_msr_list;
extern unsigned int kvm_shadow_memory;
static int kvm_has_msr_star;
static int kvm_has_vm_hsave_pa;
static bool has_msr_tsc_aux;
static int has_msr_tsc_deadline;

static int lm_capable_kernel;

static bool has_msr_pv_eoi_en;
static bool has_msr_kvm_steal_time;

static bool has_msr_architectural_pmu;
static uint32_t num_architectural_pmu_counters;

int kvm_set_tss_addr(kvm_context_t kvm, unsigned long addr)
{
#ifdef KVM_CAP_SET_TSS_ADDR
	int r;

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_SET_TSS_ADDR);
	if (r > 0) {
		r = kvm_vm_ioctl(kvm_state, KVM_SET_TSS_ADDR, addr);
		if (r < 0) {
			fprintf(stderr, "kvm_set_tss_addr: %m\n");
			return r;
		}
		return 0;
	}
#endif
	return -ENOSYS;
}

static int kvm_init_tss(kvm_context_t kvm)
{
#ifdef KVM_CAP_SET_TSS_ADDR
	int r;

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_SET_TSS_ADDR);
	if (r > 0) {
		/*
		 * this address is 3 pages before the bios, and the bios should present
		 * as unavaible memory
		 */
		r = kvm_set_tss_addr(kvm, 0xfeffd000);
		if (r < 0) {
			fprintf(stderr, "kvm_init_tss: unable to set tss addr\n");
			return r;
		}

	}
#endif
	return 0;
}

static int kvm_set_identity_map_addr(kvm_context_t kvm, uint64_t addr)
{
#ifdef KVM_CAP_SET_IDENTITY_MAP_ADDR
	int r;

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_SET_IDENTITY_MAP_ADDR);
	if (r > 0) {
		r = kvm_vm_ioctl(kvm_state, KVM_SET_IDENTITY_MAP_ADDR, &addr);
		if (r == -1) {
			fprintf(stderr, "kvm_set_identity_map_addr: %m\n");
			return -errno;
		}
		return 0;
	}
#endif
	return -ENOSYS;
}

static int kvm_init_identity_map_page(kvm_context_t kvm)
{
#ifdef KVM_CAP_SET_IDENTITY_MAP_ADDR
	int r;

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_SET_IDENTITY_MAP_ADDR);
	if (r > 0) {
		/*
		 * this address is 4 pages before the bios, and the bios should present
		 * as unavaible memory
		 */
		r = kvm_set_identity_map_addr(kvm, 0xfeffc000);
		if (r < 0) {
			fprintf(stderr, "kvm_init_identity_map_page: "
				"unable to set identity mapping addr\n");
			return r;
		}

	}
#endif
	return 0;
}

static int kvm_create_pit(kvm_context_t kvm)
{
#ifdef KVM_CAP_PIT
	int r;

	kvm->pit_in_kernel = 0;
	if (!kvm->no_pit_creation) {
		r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_PIT);
		if (r > 0) {
			r = kvm_vm_ioctl(kvm_state, KVM_CREATE_PIT);
			if (r >= 0)
				kvm->pit_in_kernel = 1;
			else {
				fprintf(stderr, "Create kernel PIC irqchip failed\n");
				return r;
			}
		}
	}
#endif
	return 0;
}

int kvm_arch_create(kvm_context_t kvm, unsigned long phys_mem_bytes,
			void **vm_mem)
{
	int r = 0;

	r = kvm_init_tss(kvm);
	if (r < 0)
		return r;

	r = kvm_init_identity_map_page(kvm);
	if (r < 0)
		return r;

	r = kvm_create_pit(kvm);
	if (r < 0)
		return r;

	r = kvm_init_coalesced_mmio(kvm);
	if (r < 0)
		return r;

#ifdef KVM_EXIT_TPR_ACCESS
    kvm_tpr_opt_setup();
#endif

	return 0;
}

#ifdef KVM_EXIT_TPR_ACCESS

static int kvm_handle_tpr_access(CPUState *env)
{
	struct kvm_run *run = env->kvm_run;
	kvm_tpr_access_report(env,
                         run->tpr_access.rip,
                         run->tpr_access.is_write);
    return 0;
}


int kvm_enable_vapic(CPUState *env, uint64_t vapic)
{
	struct kvm_vapic_addr va = {
		.vapic_addr = vapic,
	};

	return kvm_vcpu_ioctl(env, KVM_SET_VAPIC_ADDR, &va);
}

#endif

int kvm_arch_run(CPUState *env)
{
	int r = 0;
	struct kvm_run *run = env->kvm_run;


	switch (run->exit_reason) {
#ifdef KVM_EXIT_SET_TPR
		case KVM_EXIT_SET_TPR:
			break;
#endif
#ifdef KVM_EXIT_TPR_ACCESS
		case KVM_EXIT_TPR_ACCESS:
			r = kvm_handle_tpr_access(env);
			break;
#endif
		default:
			r = 1;
			break;
	}

	return r;
}

#define MAX_ALIAS_SLOTS 4
static struct {
	uint64_t start;
	uint64_t len;
} kvm_aliases[MAX_ALIAS_SLOTS];

static int get_alias_slot(uint64_t start)
{
	int i;

	for (i=0; i<MAX_ALIAS_SLOTS; i++)
		if (kvm_aliases[i].start == start)
			return i;
	return -1;
}
static int get_free_alias_slot(void)
{
        int i;

        for (i=0; i<MAX_ALIAS_SLOTS; i++)
                if (kvm_aliases[i].len == 0)
                        return i;
        return -1;
}

static void register_alias(int slot, uint64_t start, uint64_t len)
{
	kvm_aliases[slot].start = start;
	kvm_aliases[slot].len   = len;
}

int kvm_create_memory_alias(kvm_context_t kvm,
			    uint64_t phys_start,
			    uint64_t len,
			    uint64_t target_phys)
{
	struct kvm_memory_alias alias = {
		.flags = 0,
		.guest_phys_addr = phys_start,
		.memory_size = len,
		.target_phys_addr = target_phys,
	};
	int r;
	int slot;

	slot = get_alias_slot(phys_start);
	if (slot < 0)
		slot = get_free_alias_slot();
	if (slot < 0)
		return -EBUSY;
	alias.slot = slot;

	r = kvm_vm_ioctl(kvm_state, KVM_SET_MEMORY_ALIAS, &alias);
	if (r == -1)
	    return -errno;

	register_alias(slot, phys_start, len);
	return 0;
}

int kvm_destroy_memory_alias(kvm_context_t kvm, uint64_t phys_start)
{
	return kvm_create_memory_alias(kvm, phys_start, 0, 0);
}

#ifdef KVM_CAP_IRQCHIP

int kvm_get_lapic(CPUState *env, struct kvm_lapic_state *s)
{
	int r = 0;

	if (!kvm_irqchip_in_kernel())
		return r;

	r = kvm_vcpu_ioctl(env, KVM_GET_LAPIC, s);
	if (r < 0)
		fprintf(stderr, "KVM_GET_LAPIC failed\n");
	return r;
}

int kvm_set_lapic(CPUState *env, struct kvm_lapic_state *s)
{
	int r = 0;

	if (!kvm_irqchip_in_kernel())
		return 0;

	r = kvm_vcpu_ioctl(env, KVM_SET_LAPIC, s);

	if (r < 0)
		fprintf(stderr, "KVM_SET_LAPIC failed\n");
	return r;
}

#endif

#ifdef KVM_CAP_PIT

int kvm_get_pit(kvm_context_t kvm, struct kvm_pit_state *s)
{
	if (!kvm->pit_in_kernel)
		return 0;
	return kvm_vm_ioctl(kvm_state, KVM_GET_PIT, s);
}

int kvm_set_pit(kvm_context_t kvm, struct kvm_pit_state *s)
{
	if (!kvm->pit_in_kernel)
		return 0;
	return kvm_vm_ioctl(kvm_state, KVM_SET_PIT, s);
}

#ifdef KVM_CAP_PIT_STATE2
int kvm_get_pit2(kvm_context_t kvm, struct kvm_pit_state2 *ps2)
{
	if (!kvm->pit_in_kernel)
		return 0;
	return kvm_vm_ioctl(kvm_state, KVM_GET_PIT2, ps2);
}

int kvm_set_pit2(kvm_context_t kvm, struct kvm_pit_state2 *ps2)
{
	if (!kvm->pit_in_kernel)
		return 0;
	return kvm_vm_ioctl(kvm_state, KVM_SET_PIT2, ps2);
}

#endif
#endif

int kvm_has_pit_state2(kvm_context_t kvm)
{
	int r = 0;

#ifdef KVM_CAP_PIT_STATE2
	r = kvm_check_extension(kvm_state, KVM_CAP_PIT_STATE2);
#endif
	return r;
}

void kvm_show_code(CPUState *env)
{
#define SHOW_CODE_LEN 50
	struct kvm_regs regs;
	struct kvm_sregs sregs;
	int r, n;
	int back_offset;
	unsigned char code;
	char code_str[SHOW_CODE_LEN * 3 + 1];
	unsigned long rip;

	r = kvm_vcpu_ioctl(env, KVM_GET_SREGS, &sregs);
	if (r < 0 ) {
		perror("KVM_GET_SREGS");
		return;
	}
	r = kvm_vcpu_ioctl(env, KVM_GET_REGS, &regs);
	if (r < 0) {
		perror("KVM_GET_REGS");
		return;
	}
	rip = sregs.cs.base + regs.rip;
	back_offset = regs.rip;
	if (back_offset > 20)
	    back_offset = 20;
	*code_str = 0;
	for (n = -back_offset; n < SHOW_CODE_LEN-back_offset; ++n) {
		if (n == 0)
			strcat(code_str, " -->");
		cpu_physical_memory_rw(rip + n, &code, 1, 1);
		sprintf(code_str + strlen(code_str), " %02x", code);
	}
	fprintf(stderr, "code:%s\n", code_str);
}


/*
 * Returns available msr list.  User must free.
 */
struct kvm_msr_list *kvm_get_msr_list(kvm_context_t kvm)
{
	struct kvm_msr_list sizer, *msrs;
	int r;

	sizer.nmsrs = 0;
	r = kvm_ioctl(kvm_state, KVM_GET_MSR_INDEX_LIST, &sizer);
	if (r < 0 && r != -E2BIG)
		return NULL;
	/* Old kernel modules had a bug and could write beyond the provided
	   memory. Allocate at least a safe amount of 1K. */
	msrs = qemu_malloc(MAX(1024, sizeof(*msrs) +
				       sizer.nmsrs * sizeof(*msrs->indices)));

	msrs->nmsrs = sizer.nmsrs;
	r = kvm_ioctl(kvm_state, KVM_GET_MSR_INDEX_LIST, msrs);
	if (r < 0) {
		free(msrs);
		errno = r;
		return NULL;
	}
	return msrs;
}

int kvm_get_msrs(CPUState *env, struct kvm_msr_entry *msrs, int n)
{
    struct kvm_msrs *kmsrs = qemu_malloc(sizeof *kmsrs + n * sizeof *msrs);
    int r;

    kmsrs->nmsrs = n;
    memcpy(kmsrs->entries, msrs, n * sizeof *msrs);
    r = kvm_vcpu_ioctl(env, KVM_GET_MSRS, kmsrs);
    memcpy(msrs, kmsrs->entries, n * sizeof *msrs);
    free(kmsrs);
    return r;
}

int kvm_set_msrs(CPUState *env, struct kvm_msr_entry *msrs, int n)
{
    struct kvm_msrs *kmsrs = qemu_malloc(sizeof *kmsrs + n * sizeof *msrs);
    int r;

    kmsrs->nmsrs = n;
    memcpy(kmsrs->entries, msrs, n * sizeof *msrs);
    r = kvm_vcpu_ioctl(env, KVM_SET_MSRS, kmsrs);
    free(kmsrs);
    return r;
}

int kvm_get_mce_cap_supported(kvm_context_t kvm, uint64_t *mce_cap,
                              int *max_banks)
{
#ifdef KVM_CAP_MCE
    int r;

    r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_MCE);
    if (r > 0) {
        *max_banks = r;
        return kvm_ioctl(kvm_state, KVM_X86_GET_MCE_CAP_SUPPORTED, mce_cap);
    }
#endif
    return -ENOSYS;
}

int kvm_setup_mce(CPUState *env, uint64_t *mcg_cap)
{
#ifdef KVM_CAP_MCE
    return kvm_vcpu_ioctl(env, KVM_X86_SETUP_MCE, mcg_cap);
#else
    return -ENOSYS;
#endif
}

int kvm_set_mce(CPUState *env, struct kvm_x86_mce *m)
{
#ifdef KVM_CAP_MCE
    return kvm_vcpu_ioctl(env, KVM_X86_SET_MCE, m);
#else
    return -ENOSYS;
#endif
}

static void print_seg(FILE *file, const char *name, struct kvm_segment *seg)
{
	fprintf(stderr,
		"%s %04x (%08llx/%08x p %d dpl %d db %d s %d type %x l %d"
		" g %d avl %d)\n",
		name, seg->selector, seg->base, seg->limit, seg->present,
		seg->dpl, seg->db, seg->s, seg->type, seg->l, seg->g,
		seg->avl);
}

static void print_dt(FILE *file, const char *name, struct kvm_dtable *dt)
{
	fprintf(stderr, "%s %llx/%x\n", name, dt->base, dt->limit);
}

void kvm_show_regs(CPUState *env)
{
	struct kvm_regs regs;
	struct kvm_sregs sregs;
	int r;

	r = kvm_vcpu_ioctl(env, KVM_GET_REGS, &regs);
	if (r < 0) {
		perror("KVM_GET_REGS");
		return;
	}
	fprintf(stderr,
		"rax %016llx rbx %016llx rcx %016llx rdx %016llx\n"
		"rsi %016llx rdi %016llx rsp %016llx rbp %016llx\n"
		"r8  %016llx r9  %016llx r10 %016llx r11 %016llx\n"
		"r12 %016llx r13 %016llx r14 %016llx r15 %016llx\n"
		"rip %016llx rflags %08llx\n",
		regs.rax, regs.rbx, regs.rcx, regs.rdx,
		regs.rsi, regs.rdi, regs.rsp, regs.rbp,
		regs.r8,  regs.r9,  regs.r10, regs.r11,
		regs.r12, regs.r13, regs.r14, regs.r15,
		regs.rip, regs.rflags);
	r = kvm_vcpu_ioctl(env, KVM_GET_SREGS, &sregs);
	if (r < 0) {
		perror("KVM_GET_SREGS");
		return;
	}
	print_seg(stderr, "cs", &sregs.cs);
	print_seg(stderr, "ds", &sregs.ds);
	print_seg(stderr, "es", &sregs.es);
	print_seg(stderr, "ss", &sregs.ss);
	print_seg(stderr, "fs", &sregs.fs);
	print_seg(stderr, "gs", &sregs.gs);
	print_seg(stderr, "tr", &sregs.tr);
	print_seg(stderr, "ldt", &sregs.ldt);
	print_dt(stderr, "gdt", &sregs.gdt);
	print_dt(stderr, "idt", &sregs.idt);
	fprintf(stderr, "cr0 %llx cr2 %llx cr3 %llx cr4 %llx cr8 %llx"
		" efer %llx\n",
		sregs.cr0, sregs.cr2, sregs.cr3, sregs.cr4, sregs.cr8,
		sregs.efer);
}

static void kvm_set_cr8(CPUState *env, uint64_t cr8)
{
	env->kvm_run->cr8 = cr8;
}

int kvm_setup_cpuid(CPUState *env, int nent,
		    struct kvm_cpuid_entry *entries)
{
	struct kvm_cpuid *cpuid;
	int r;

	cpuid = qemu_malloc(sizeof(*cpuid) + nent * sizeof(*entries));

	cpuid->nent = nent;
	memcpy(cpuid->entries, entries, nent * sizeof(*entries));
	r = kvm_vcpu_ioctl(env, KVM_SET_CPUID, cpuid);

	free(cpuid);
	return r;
}

int kvm_setup_cpuid2(CPUState *env, int nent,
		     struct kvm_cpuid_entry2 *entries)
{
	struct kvm_cpuid2 *cpuid;
	int r;

	cpuid = qemu_malloc(sizeof(*cpuid) + nent * sizeof(*entries));

	cpuid->nent = nent;
	memcpy(cpuid->entries, entries, nent * sizeof(*entries));
	r = kvm_vcpu_ioctl(env, KVM_SET_CPUID2, cpuid);
	free(cpuid);
	return r;
}

int kvm_set_shadow_pages(kvm_context_t kvm, unsigned int nrshadow_pages)
{
#ifdef KVM_CAP_MMU_SHADOW_CACHE_CONTROL
	int r;

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION,
		  KVM_CAP_MMU_SHADOW_CACHE_CONTROL);
	if (r > 0) {
		r = kvm_vm_ioctl(kvm_state, KVM_SET_NR_MMU_PAGES, nrshadow_pages);
		if (r < 0) {
			fprintf(stderr, "kvm_set_shadow_pages: %m\n");
			return r;
		}
		return 0;
	}
#endif
	return -1;
}

int kvm_get_shadow_pages(kvm_context_t kvm, unsigned int *nrshadow_pages)
{
#ifdef KVM_CAP_MMU_SHADOW_CACHE_CONTROL
	int r;

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION,
		  KVM_CAP_MMU_SHADOW_CACHE_CONTROL);
	if (r > 0) {
		*nrshadow_pages = kvm_vm_ioctl(kvm_state, KVM_GET_NR_MMU_PAGES);
		return 0;
	}
#endif
	return -1;
}

#ifdef KVM_CAP_VAPIC

static int tpr_access_reporting(CPUState *env, int enabled)
{
	int r;
	struct kvm_tpr_access_ctl tac = {
		.enabled = enabled,
	};

	r = kvm_ioctl(kvm_state, KVM_CHECK_EXTENSION, KVM_CAP_VAPIC);
	if (r <= 0)
		return -ENOSYS;
	return kvm_vcpu_ioctl(env, KVM_TPR_ACCESS_REPORTING, &tac);
}

int kvm_enable_tpr_access_reporting(CPUState *env)
{
	return tpr_access_reporting(env, 1);
}

int kvm_disable_tpr_access_reporting(CPUState *env)
{
	return tpr_access_reporting(env, 0);
}

#endif

#ifdef KVM_CAP_EXT_CPUID

static struct kvm_cpuid2 *try_get_cpuid(kvm_context_t kvm, int max)
{
	struct kvm_cpuid2 *cpuid;
	int r, size;

	size = sizeof(*cpuid) + max * sizeof(*cpuid->entries);
	cpuid = qemu_malloc(size);
	cpuid->nent = max;
	r = kvm_ioctl(kvm_state, KVM_GET_SUPPORTED_CPUID, cpuid);
	if (r == 0 && cpuid->nent >= max)
		r = -E2BIG;
	if (r < 0) {
		if (r == -E2BIG) {
			free(cpuid);
			return NULL;
		} else {
			fprintf(stderr, "KVM_GET_SUPPORTED_CPUID failed: %s\n",
				strerror(-r));
			exit(1);
		}
	}
	return cpuid;
}

#define R_EAX 0
#define R_ECX 1
#define R_EDX 2
#define R_EBX 3
#define R_ESP 4
#define R_EBP 5
#define R_ESI 6
#define R_EDI 7
#endif

struct kvm_para_features {
	int cap;
	int feature;
} para_features[] = {
#ifdef KVM_CAP_CLOCKSOURCE
	{ KVM_CAP_CLOCKSOURCE, KVM_FEATURE_CLOCKSOURCE },
#endif
#ifdef KVM_CAP_NOP_IO_DELAY
	{ KVM_CAP_NOP_IO_DELAY, KVM_FEATURE_NOP_IO_DELAY },
#endif
#ifdef KVM_CAP_PV_MMU
	{ KVM_CAP_PV_MMU, KVM_FEATURE_MMU_OP },
#endif
#ifdef KVM_CAP_CR3_CACHE
	{ KVM_CAP_CR3_CACHE, KVM_FEATURE_CR3_CACHE },
#endif
	{ -1, -1 }
};

static int get_para_features(kvm_context_t kvm_context)
{
	int i, features = 0;

	for (i = 0; i < ARRAY_SIZE(para_features)-1; i++) {
		if (kvm_check_extension(kvm_state, para_features[i].cap))
			features |= (1 << para_features[i].feature);
	}

	return features;
}


uint32_t kvm_get_supported_cpuid(kvm_context_t kvm, uint32_t function,
                                 uint32_t index, int reg)
{
	uint32_t ret = -1;
	int has_kvm_features = 0;
#ifdef KVM_CAP_EXT_CPUID
	struct kvm_cpuid2 *cpuid;
	int i, max;
	uint32_t cpuid_1_edx;

	ret = 0;

	if (!kvm_check_extension(kvm_state, KVM_CAP_EXT_CPUID)) {
		return -1U;
	}

	max = 1;
	while ((cpuid = try_get_cpuid(kvm, max)) == NULL) {
		max *= 2;
	}

	for (i = 0; i < cpuid->nent; ++i) {
		if (cpuid->entries[i].function == function &&
		    cpuid->entries[i].index == index) {
			if (cpuid->entries[i].function == KVM_CPUID_FEATURES) {
				has_kvm_features = 1;
			}

			switch (reg) {
			case R_EAX:
				ret = cpuid->entries[i].eax;
				break;
			case R_EBX:
				ret = cpuid->entries[i].ebx;
				break;
			case R_ECX:
				ret = cpuid->entries[i].ecx;
				break;
			case R_EDX:
				ret = cpuid->entries[i].edx;
				break;
			}
		}
	}

	/* Fixups for the data returned by KVM, below */

	if (function == 1 && reg == R_EDX) {
		/* kvm misreports the following features
		 */
		ret |= 1 << 12; /* MTRR */
		ret |= 1 << 16; /* PAT */
		ret |= 1 << 7;  /* MCE */
		ret |= 1 << 14; /* MCA */
	} else if (function == 0x80000001 && reg == R_EDX) {
		/* On Intel, kvm returns cpuid according to
		 * the Intel spec, so add missing bits
		 * according to the AMD spec:
		 */
		cpuid_1_edx = kvm_get_supported_cpuid(kvm, 1, 0, R_EDX);
		ret |= cpuid_1_edx & 0x183f7ff;
	} else if (function == 1 && reg == R_ECX) {
		/* We can set the hypervisor flag, even if KVM does not return it on
		 * GET_SUPPORTED_CPUID
		 */
		ret |= CPUID_EXT_HYPERVISOR;
		/* tsc-deadline flag is not returned by GET_SUPPORTED_CPUID, but it
		 * can be enabled if the kernel has KVM_CAP_TSC_DEADLINE_TIMER,
		 * and the irqchip is in the kernel.
		 */
		if (kvm_irqchip_in_kernel() &&
				kvm_check_extension(kvm_state, KVM_CAP_TSC_DEADLINE_TIMER)) {
			ret |= CPUID_EXT_TSC_DEADLINE_TIMER;
		}

		/* x2apic is reported by GET_SUPPORTED_CPUID, but it can't be enabled
		 * without the in-kernel irqchip
		 */
		if (!kvm_irqchip_in_kernel()) {
			ret &= ~CPUID_EXT_X2APIC;
		}
	}


	free(cpuid);
#endif
	/* fallback for older kernels */
	if (!has_kvm_features && (function == KVM_CPUID_FEATURES)) {
		ret = get_para_features(kvm);
	}

	return ret;
}

int kvm_qemu_create_memory_alias(uint64_t phys_start,
                                 uint64_t len,
                                 uint64_t target_phys)
{
    return kvm_create_memory_alias(kvm_context, phys_start, len, target_phys);
}

int kvm_qemu_destroy_memory_alias(uint64_t phys_start)
{
	return kvm_destroy_memory_alias(kvm_context, phys_start);
}

int kvm_arch_qemu_create_context(void)
{
    int i;
    struct utsname utsname;

    uname(&utsname);
    lm_capable_kernel = strcmp(utsname.machine, "x86_64") == 0;

    if (kvm_shadow_memory)
        kvm_set_shadow_pages(kvm_context, kvm_shadow_memory);

    kvm_msr_list = kvm_get_msr_list(kvm_context);
    if (!kvm_msr_list)
		return -1;
    for (i = 0; i < kvm_msr_list->nmsrs; ++i) {
	if (kvm_msr_list->indices[i] == MSR_STAR)
	    kvm_has_msr_star = 1;
        if (kvm_msr_list->indices[i] == MSR_VM_HSAVE_PA)
            kvm_has_vm_hsave_pa = 1;
        if (kvm_msr_list->indices[i] == MSR_TSC_AUX)
            has_msr_tsc_aux = true;
        if (kvm_msr_list->indices[i] == MSR_IA32_TSCDEADLINE)
            has_msr_tsc_deadline = 1;
    }

    return 0;
}

static void set_msr_entry(struct kvm_msr_entry *entry, uint32_t index,
                          uint64_t data)
{
    entry->index = index;
    entry->data  = data;
}

/* returns 0 on success, non-0 on failure */
static int get_msr_entry(struct kvm_msr_entry *entry, CPUState *env)
{
        uint32_t index = entry->index;
        switch (index) {
        case MSR_IA32_SYSENTER_CS:
            env->sysenter_cs  = entry->data;
            break;
        case MSR_IA32_SYSENTER_ESP:
            env->sysenter_esp = entry->data;
            break;
        case MSR_IA32_SYSENTER_EIP:
            env->sysenter_eip = entry->data;
            break;
        case MSR_STAR:
            env->star         = entry->data;
            break;
#ifdef TARGET_X86_64
        case MSR_CSTAR:
            env->cstar        = entry->data;
            break;
        case MSR_KERNELGSBASE:
            env->kernelgsbase = entry->data;
            break;
        case MSR_FMASK:
            env->fmask        = entry->data;
            break;
        case MSR_LSTAR:
            env->lstar        = entry->data;
            break;
#endif
        case MSR_IA32_TSC:
            env->tsc          = entry->data;
            break;
        case MSR_VM_HSAVE_PA:
            env->vm_hsave     = entry->data;
            break;
        case MSR_TSC_AUX:
            env->tsc_aux      = entry->data;
            break;
        case MSR_IA32_TSCDEADLINE:
            env->tsc_deadline = entry->data;
            break;
        case MSR_KVM_SYSTEM_TIME:
            env->system_time_msr = entry->data;
            break;
        case MSR_KVM_WALL_CLOCK:
            env->wall_clock_msr = entry->data;
            break;
        case MSR_KVM_STEAL_TIME:
            env->steal_time_msr = entry->data;
            break;
        case MSR_CORE_PERF_FIXED_CTR_CTRL:
            env->msr_fixed_ctr_ctrl = entry->data;
            break;
        case MSR_CORE_PERF_GLOBAL_CTRL:
            env->msr_global_ctrl = entry->data;
            break;
        case MSR_CORE_PERF_GLOBAL_STATUS:
            env->msr_global_status = entry->data;
            break;
        case MSR_CORE_PERF_GLOBAL_OVF_CTRL:
            env->msr_global_ovf_ctrl = entry->data;
            break;
        case MSR_CORE_PERF_FIXED_CTR0 ... MSR_CORE_PERF_FIXED_CTR0 + MAX_FIXED_COUNTERS - 1:
            env->msr_fixed_counters[index - MSR_CORE_PERF_FIXED_CTR0] = entry->data;
            break;
        case MSR_P6_PERFCTR0 ... MSR_P6_PERFCTR0 + MAX_GP_COUNTERS - 1:
            env->msr_gp_counters[index - MSR_P6_PERFCTR0] = entry->data;
            break;
        case MSR_P6_EVNTSEL0 ... MSR_P6_EVNTSEL0 + MAX_GP_COUNTERS - 1:
            env->msr_gp_evtsel[index - MSR_P6_EVNTSEL0] = entry->data;
            break;
        case HV_X64_MSR_GUEST_OS_ID:
            env->hyperv_guest_os_id = entry->data;
            break;
        case HV_X64_MSR_HYPERCALL:
            env->hyperv_hypercall = entry->data;
            break;
        case MSR_KVM_PV_EOI_EN:
            env->pv_eoi_en_msr = entry->data;
            break;
#ifdef KVM_CAP_MCE
        case MSR_MCG_STATUS:
            env->mcg_status = entry->data;
            break;
        case MSR_MCG_CTL:
            env->mcg_ctl = entry->data;
            break;
#endif
        default:
#ifdef KVM_CAP_MCE
            if (entry->index >= MSR_MC0_CTL &&
                entry->index < MSR_MC0_CTL + (env->mcg_cap & 0xff) * 4) {
                env->mce_banks[entry->index - MSR_MC0_CTL] = entry->data;
                break;
            }
#endif
            printf("Warning unknown msr index 0x%x\n", entry->index);
            return 1;
        }
        return 0;
}

static void set_v8086_seg(struct kvm_segment *lhs, const SegmentCache *rhs)
{
    lhs->selector = rhs->selector;
    lhs->base = rhs->base;
    lhs->limit = rhs->limit;
    lhs->type = 3;
    lhs->present = 1;
    lhs->dpl = 3;
    lhs->db = 0;
    lhs->s = 1;
    lhs->l = 0;
    lhs->g = 0;
    lhs->avl = 0;
    lhs->unusable = 0;
}

static void set_seg(struct kvm_segment *lhs, const SegmentCache *rhs)
{
    unsigned flags = rhs->flags;
    lhs->selector = rhs->selector;
    lhs->base = rhs->base;
    lhs->limit = rhs->limit;
    lhs->type = (flags >> DESC_TYPE_SHIFT) & 15;
    lhs->present = (flags & DESC_P_MASK) != 0;
    lhs->dpl = (flags >> DESC_DPL_SHIFT) & 3;
    lhs->db = (flags >> DESC_B_SHIFT) & 1;
    lhs->s = (flags & DESC_S_MASK) != 0;
    lhs->l = (flags >> DESC_L_SHIFT) & 1;
    lhs->g = (flags & DESC_G_MASK) != 0;
    lhs->avl = (flags & DESC_AVL_MASK) != 0;
    lhs->unusable = 0;
}

static void get_seg(SegmentCache *lhs, const struct kvm_segment *rhs)
{
    lhs->selector = rhs->selector;
    lhs->base = rhs->base;
    lhs->limit = rhs->limit;
    lhs->flags =
	(rhs->type << DESC_TYPE_SHIFT)
	| (rhs->present * DESC_P_MASK)
	| (rhs->dpl << DESC_DPL_SHIFT)
	| (rhs->db << DESC_B_SHIFT)
	| (rhs->s * DESC_S_MASK)
	| (rhs->l << DESC_L_SHIFT)
	| (rhs->g * DESC_G_MASK)
	| (rhs->avl * DESC_AVL_MASK);
}

#define XSAVE_CWD_RIP     2
#define XSAVE_CWD_RDP     4
#define XSAVE_MXCSR       6
#define XSAVE_ST_SPACE    8
#define XSAVE_XMM_SPACE   40
#define XSAVE_XSTATE_BV   128
#define XSAVE_YMMH_SPACE  144

void kvm_arch_load_regs(CPUState *env)
{
    struct kvm_regs regs;
    struct kvm_fpu fpu;
    struct kvm_xsave* xsave = env->kvm_xsave_buf;
    struct kvm_xcrs xcrs;
    struct kvm_sregs sregs;
    struct kvm_msr_entry msrs[100];
    int rc, n, i;

    regs.rax = env->regs[R_EAX];
    regs.rbx = env->regs[R_EBX];
    regs.rcx = env->regs[R_ECX];
    regs.rdx = env->regs[R_EDX];
    regs.rsi = env->regs[R_ESI];
    regs.rdi = env->regs[R_EDI];
    regs.rsp = env->regs[R_ESP];
    regs.rbp = env->regs[R_EBP];
#ifdef TARGET_X86_64
    regs.r8 = env->regs[8];
    regs.r9 = env->regs[9];
    regs.r10 = env->regs[10];
    regs.r11 = env->regs[11];
    regs.r12 = env->regs[12];
    regs.r13 = env->regs[13];
    regs.r14 = env->regs[14];
    regs.r15 = env->regs[15];
#endif

    regs.rflags = env->eflags;
    regs.rip = env->eip;

    kvm_set_regs(env, &regs);

    if (xsave) {
        uint16_t cwd, swd, twd, fop;

        memset(xsave, 0, sizeof(struct kvm_xsave));
        cwd = swd = twd = fop = 0;
        swd = env->fpus & ~(7 << 11);
        swd |= (env->fpstt & 7) << 11;
        cwd = env->fpuc;
        for (i = 0; i < 8; ++i)
            twd |= (!env->fptags[i]) << i;
        xsave->region[0] = (uint32_t)(swd << 16) + cwd;
        xsave->region[1] = (uint32_t)(fop << 16) + twd;
        memcpy(&xsave->region[XSAVE_ST_SPACE], env->fpregs,
                sizeof env->fpregs);
        memcpy(&xsave->region[XSAVE_XMM_SPACE], env->xmm_regs,
                sizeof env->xmm_regs);
        xsave->region[XSAVE_MXCSR] = env->mxcsr;
        *(uint64_t *)&xsave->region[XSAVE_XSTATE_BV] = env->xstate_bv;
        memcpy(&xsave->region[XSAVE_YMMH_SPACE], env->ymmh_regs,
                sizeof env->ymmh_regs);
        kvm_set_xsave(env, xsave);
        if (kvm_check_extension(kvm_state, KVM_CAP_XCRS)) {
            xcrs.nr_xcrs = 1;
            xcrs.flags = 0;
            xcrs.xcrs[0].xcr = 0;
            xcrs.xcrs[0].value = env->xcr0;
            kvm_set_xcrs(env, &xcrs);
        }
    } else {
        memset(&fpu, 0, sizeof fpu);
        fpu.fsw = env->fpus & ~(7 << 11);
        fpu.fsw |= (env->fpstt & 7) << 11;
        fpu.fcw = env->fpuc;
        for (i = 0; i < 8; ++i)
            fpu.ftwx |= (!env->fptags[i]) << i;
        memcpy(fpu.fpr, env->fpregs, sizeof env->fpregs);
        memcpy(fpu.xmm, env->xmm_regs, sizeof env->xmm_regs);
        fpu.mxcsr = env->mxcsr;
        kvm_set_fpu(env, &fpu);
    }

    memset(sregs.interrupt_bitmap, 0, sizeof(sregs.interrupt_bitmap));
    if (env->interrupt_injected >= 0) {
        sregs.interrupt_bitmap[env->interrupt_injected / 64] |=
                (uint64_t)1 << (env->interrupt_injected % 64);
    }

    if ((env->eflags & VM_MASK)) {
	    set_v8086_seg(&sregs.cs, &env->segs[R_CS]);
	    set_v8086_seg(&sregs.ds, &env->segs[R_DS]);
	    set_v8086_seg(&sregs.es, &env->segs[R_ES]);
	    set_v8086_seg(&sregs.fs, &env->segs[R_FS]);
	    set_v8086_seg(&sregs.gs, &env->segs[R_GS]);
	    set_v8086_seg(&sregs.ss, &env->segs[R_SS]);
    } else {
	    set_seg(&sregs.cs, &env->segs[R_CS]);
	    set_seg(&sregs.ds, &env->segs[R_DS]);
	    set_seg(&sregs.es, &env->segs[R_ES]);
	    set_seg(&sregs.fs, &env->segs[R_FS]);
	    set_seg(&sregs.gs, &env->segs[R_GS]);
	    set_seg(&sregs.ss, &env->segs[R_SS]);
    }

    set_seg(&sregs.tr, &env->tr);
    set_seg(&sregs.ldt, &env->ldt);

    sregs.idt.limit = env->idt.limit;
    sregs.idt.base = env->idt.base;
    sregs.gdt.limit = env->gdt.limit;
    sregs.gdt.base = env->gdt.base;

    sregs.cr0 = env->cr[0];
    sregs.cr2 = env->cr[2];
    sregs.cr3 = env->cr[3];
    sregs.cr4 = env->cr[4];

    sregs.cr8 = cpu_get_apic_tpr(env);
    sregs.apic_base = cpu_get_apic_base(env);

    sregs.efer = env->efer;

    kvm_set_sregs(env, &sregs);

    /* msrs */
    n = 0;
    /* Remember to increase msrs size if you add new registers below */
    set_msr_entry(&msrs[n++], MSR_IA32_SYSENTER_CS,  env->sysenter_cs);
    set_msr_entry(&msrs[n++], MSR_IA32_SYSENTER_ESP, env->sysenter_esp);
    set_msr_entry(&msrs[n++], MSR_IA32_SYSENTER_EIP, env->sysenter_eip);
    if (kvm_has_msr_star)
	set_msr_entry(&msrs[n++], MSR_STAR,              env->star);
    if (kvm_has_vm_hsave_pa)
        set_msr_entry(&msrs[n++], MSR_VM_HSAVE_PA, env->vm_hsave);
    if (has_msr_tsc_aux)
        set_msr_entry(&msrs[n++], MSR_TSC_AUX, env->tsc_aux);
    if (has_msr_tsc_deadline)
        set_msr_entry(&msrs[n++], MSR_IA32_TSCDEADLINE, env->tsc_deadline);
#ifdef TARGET_X86_64
    if (lm_capable_kernel) {
        set_msr_entry(&msrs[n++], MSR_CSTAR,             env->cstar);
        set_msr_entry(&msrs[n++], MSR_KERNELGSBASE,      env->kernelgsbase);
        set_msr_entry(&msrs[n++], MSR_FMASK,             env->fmask);
        set_msr_entry(&msrs[n++], MSR_LSTAR  ,           env->lstar);
    }
#endif
    set_msr_entry(&msrs[n++], MSR_KVM_SYSTEM_TIME,  env->system_time_msr);
    set_msr_entry(&msrs[n++], MSR_KVM_WALL_CLOCK,  env->wall_clock_msr);
    if (has_msr_kvm_steal_time)
        set_msr_entry(&msrs[n++], MSR_KVM_STEAL_TIME,  env->steal_time_msr);
    if (has_msr_architectural_pmu) {
        /* Stop the counter.  */
        set_msr_entry(&msrs[n++], MSR_CORE_PERF_FIXED_CTR_CTRL, 0);
        set_msr_entry(&msrs[n++], MSR_CORE_PERF_GLOBAL_CTRL, 0);

        /* Set the counter values.  */
        for (i = 0; i < MAX_FIXED_COUNTERS; i++) {
            set_msr_entry(&msrs[n++], MSR_CORE_PERF_FIXED_CTR0 + i,
                          env->msr_fixed_counters[i]);
        }
        for (i = 0; i < num_architectural_pmu_counters; i++) {
            set_msr_entry(&msrs[n++], MSR_P6_PERFCTR0 + i,
                          env->msr_gp_counters[i]);
            set_msr_entry(&msrs[n++], MSR_P6_EVNTSEL0 + i,
                          env->msr_gp_evtsel[i]);
        }
        set_msr_entry(&msrs[n++], MSR_CORE_PERF_GLOBAL_STATUS,
                      env->msr_global_status);
        set_msr_entry(&msrs[n++], MSR_CORE_PERF_GLOBAL_OVF_CTRL,
                      env->msr_global_ovf_ctrl);

        /* Now start the PMU.  */
        set_msr_entry(&msrs[n++], MSR_CORE_PERF_FIXED_CTR_CTRL,
                      env->msr_fixed_ctr_ctrl);
        set_msr_entry(&msrs[n++], MSR_CORE_PERF_GLOBAL_CTRL,
                      env->msr_global_ctrl);
    }
    if (kvm_check_extension(kvm_state, KVM_CAP_HYPERV)) {
        set_msr_entry(&msrs[n++], HV_X64_MSR_GUEST_OS_ID, env->hyperv_guest_os_id);
        set_msr_entry(&msrs[n++], HV_X64_MSR_HYPERCALL, env->hyperv_hypercall);
    }
    if (has_msr_pv_eoi_en) {
        set_msr_entry(&msrs[n++], MSR_KVM_PV_EOI_EN, env->pv_eoi_en_msr);
    }

#ifdef KVM_CAP_MCE
    if (env->mcg_cap) {
        set_msr_entry(&msrs[n++], MSR_MCG_STATUS, env->mcg_status);
        set_msr_entry(&msrs[n++], MSR_MCG_CTL, env->mcg_ctl);
        for (i = 0; i < (env->mcg_cap & 0xff) * 4; i++)
            set_msr_entry(&msrs[n++], MSR_MC0_CTL + i, env->mce_banks[i]);
    }
#endif

    rc = kvm_set_msrs(env, msrs, n);
    if (rc == -1)
        perror("kvm_set_msrs FAILED");
}

void kvm_load_tsc(CPUState *env)
{
    int rc;
    struct kvm_msr_entry msr;

    set_msr_entry(&msr, MSR_IA32_TSC, env->tsc);

    rc = kvm_set_msrs(env, &msr, 1);
    if (rc == -1)
        perror("kvm_set_tsc FAILED.\n");
}

void kvm_arch_save_mpstate(CPUState *env)
{
#ifdef KVM_CAP_MP_STATE
    int r;
    struct kvm_mp_state mp_state;

    r = kvm_get_mpstate(env, &mp_state);
    if (r < 0)
        env->mp_state = -1;
    else
        env->mp_state = mp_state.mp_state;
    if (kvm_irqchip_in_kernel())
        env->halted = (env->mp_state == KVM_MP_STATE_HALTED);
#else
    env->mp_state = -1;
#endif
}

void kvm_arch_load_mpstate(CPUState *env)
{
#ifdef KVM_CAP_MP_STATE
    struct kvm_mp_state mp_state = { .mp_state = env->mp_state };

    /*
     * -1 indicates that the host did not support GET_MP_STATE ioctl,
     *  so don't touch it.
     */
    if (env->mp_state != -1)
        kvm_set_mpstate(env, &mp_state);
#endif
}

void kvm_arch_save_regs(CPUState *env)
{
    struct kvm_regs regs;
    struct kvm_fpu fpu;
    struct kvm_xsave* xsave = env->kvm_xsave_buf;
    struct kvm_xcrs xcrs;
    struct kvm_sregs sregs;
    struct kvm_msr_entry msrs[100];
    uint32_t hflags;
    uint32_t i, n, rc, bit;

    kvm_get_regs(env, &regs);

    env->regs[R_EAX] = regs.rax;
    env->regs[R_EBX] = regs.rbx;
    env->regs[R_ECX] = regs.rcx;
    env->regs[R_EDX] = regs.rdx;
    env->regs[R_ESI] = regs.rsi;
    env->regs[R_EDI] = regs.rdi;
    env->regs[R_ESP] = regs.rsp;
    env->regs[R_EBP] = regs.rbp;
#ifdef TARGET_X86_64
    env->regs[8] = regs.r8;
    env->regs[9] = regs.r9;
    env->regs[10] = regs.r10;
    env->regs[11] = regs.r11;
    env->regs[12] = regs.r12;
    env->regs[13] = regs.r13;
    env->regs[14] = regs.r14;
    env->regs[15] = regs.r15;
#endif

    env->eflags = regs.rflags;
    env->eip = regs.rip;

    if (xsave) {
        uint16_t cwd, swd, twd, fop;
        kvm_get_xsave(env, xsave);
        cwd = (uint16_t)xsave->region[0];
        swd = (uint16_t)(xsave->region[0] >> 16);
        twd = (uint16_t)xsave->region[1];
        fop = (uint16_t)(xsave->region[1] >> 16);
        env->fpstt = (swd >> 11) & 7;
        env->fpus = swd;
        env->fpuc = cwd;
        for (i = 0; i < 8; ++i)
            env->fptags[i] = !((twd >> i) & 1);
        env->mxcsr = xsave->region[XSAVE_MXCSR];
        memcpy(env->fpregs, &xsave->region[XSAVE_ST_SPACE],
                sizeof env->fpregs);
        memcpy(env->xmm_regs, &xsave->region[XSAVE_XMM_SPACE],
                sizeof env->xmm_regs);
        env->xstate_bv = *(uint64_t *)&xsave->region[XSAVE_XSTATE_BV];
        memcpy(env->ymmh_regs, &xsave->region[XSAVE_YMMH_SPACE],
                sizeof env->ymmh_regs);
        if (kvm_check_extension(kvm_state, KVM_CAP_XCRS)) {
            kvm_get_xcrs(env, &xcrs);
            if (xcrs.xcrs[0].xcr == 0)
                env->xcr0 = xcrs.xcrs[0].value;
        }
    } else {
        kvm_get_fpu(env, &fpu);
        env->fpstt = (fpu.fsw >> 11) & 7;
        env->fpus = fpu.fsw;
        env->fpuc = fpu.fcw;
        for (i = 0; i < 8; ++i)
            env->fptags[i] = !((fpu.ftwx >> i) & 1);
        memcpy(env->fpregs, fpu.fpr, sizeof env->fpregs);
        memcpy(env->xmm_regs, fpu.xmm, sizeof env->xmm_regs);
        env->mxcsr = fpu.mxcsr;
    }

    kvm_get_sregs(env, &sregs);

    /* There can only be one pending IRQ set in the bitmap at a time, so try
       to find it and save its number instead (-1 for none). */
    env->interrupt_injected = -1;
    for (i = 0; i < ARRAY_SIZE(sregs.interrupt_bitmap); i++) {
        if (sregs.interrupt_bitmap[i]) {
            bit = ctz64(sregs.interrupt_bitmap[i]);
            env->interrupt_injected = i * 64 + bit;
            break;
        }
    }

    get_seg(&env->segs[R_CS], &sregs.cs);
    get_seg(&env->segs[R_DS], &sregs.ds);
    get_seg(&env->segs[R_ES], &sregs.es);
    get_seg(&env->segs[R_FS], &sregs.fs);
    get_seg(&env->segs[R_GS], &sregs.gs);
    get_seg(&env->segs[R_SS], &sregs.ss);

    get_seg(&env->tr, &sregs.tr);
    get_seg(&env->ldt, &sregs.ldt);

    env->idt.limit = sregs.idt.limit;
    env->idt.base = sregs.idt.base;
    env->gdt.limit = sregs.gdt.limit;
    env->gdt.base = sregs.gdt.base;

    env->cr[0] = sregs.cr0;
    env->cr[2] = sregs.cr2;
    env->cr[3] = sregs.cr3;
    env->cr[4] = sregs.cr4;

    cpu_set_apic_base(env, sregs.apic_base);

    env->efer = sregs.efer;
    //cpu_set_apic_tpr(env, sregs.cr8);

#define HFLAG_COPY_MASK ~( \
			HF_CPL_MASK | HF_PE_MASK | HF_MP_MASK | HF_EM_MASK | \
			HF_TS_MASK | HF_TF_MASK | HF_VM_MASK | HF_IOPL_MASK | \
			HF_OSFXSR_MASK | HF_LMA_MASK | HF_CS32_MASK | \
			HF_SS32_MASK | HF_CS64_MASK | HF_ADDSEG_MASK)



    hflags = (env->segs[R_CS].flags >> DESC_DPL_SHIFT) & HF_CPL_MASK;
    hflags |= (env->cr[0] & CR0_PE_MASK) << (HF_PE_SHIFT - CR0_PE_SHIFT);
    hflags |= (env->cr[0] << (HF_MP_SHIFT - CR0_MP_SHIFT)) &
	    (HF_MP_MASK | HF_EM_MASK | HF_TS_MASK);
    hflags |= (env->eflags & (HF_TF_MASK | HF_VM_MASK | HF_IOPL_MASK));
    hflags |= (env->cr[4] & CR4_OSFXSR_MASK) <<
	    (HF_OSFXSR_SHIFT - CR4_OSFXSR_SHIFT);

    if (env->efer & MSR_EFER_LMA) {
        hflags |= HF_LMA_MASK;
    }

    if ((hflags & HF_LMA_MASK) && (env->segs[R_CS].flags & DESC_L_MASK)) {
        hflags |= HF_CS32_MASK | HF_SS32_MASK | HF_CS64_MASK;
    } else {
        hflags |= (env->segs[R_CS].flags & DESC_B_MASK) >>
		(DESC_B_SHIFT - HF_CS32_SHIFT);
        hflags |= (env->segs[R_SS].flags & DESC_B_MASK) >>
		(DESC_B_SHIFT - HF_SS32_SHIFT);
        if (!(env->cr[0] & CR0_PE_MASK) ||
                   (env->eflags & VM_MASK) ||
                   !(hflags & HF_CS32_MASK)) {
                hflags |= HF_ADDSEG_MASK;
            } else {
                hflags |= ((env->segs[R_DS].base |
                                env->segs[R_ES].base |
                                env->segs[R_SS].base) != 0) <<
                    HF_ADDSEG_SHIFT;
            }
    }
    env->hflags = (env->hflags & HFLAG_COPY_MASK) | hflags;

    /* msrs */
    n = 0;
    /* Remember to increase msrs size if you add new registers below */
    msrs[n++].index = MSR_IA32_SYSENTER_CS;
    msrs[n++].index = MSR_IA32_SYSENTER_ESP;
    msrs[n++].index = MSR_IA32_SYSENTER_EIP;
    if (kvm_has_msr_star)
	msrs[n++].index = MSR_STAR;

    if (!env->tsc_valid) {
        msrs[n++].index = MSR_IA32_TSC;
        env->tsc_valid = !runstate_is_running();
    }

    if (kvm_has_vm_hsave_pa)
        msrs[n++].index = MSR_VM_HSAVE_PA;
    if (has_msr_tsc_aux)
        msrs[n++].index = MSR_TSC_AUX;
    if (has_msr_tsc_deadline)
        msrs[n++].index = MSR_IA32_TSCDEADLINE;
#ifdef TARGET_X86_64
    if (lm_capable_kernel) {
        msrs[n++].index = MSR_CSTAR;
        msrs[n++].index = MSR_KERNELGSBASE;
        msrs[n++].index = MSR_FMASK;
        msrs[n++].index = MSR_LSTAR;
    }
#endif
    msrs[n++].index = MSR_KVM_SYSTEM_TIME;
    msrs[n++].index = MSR_KVM_WALL_CLOCK;
    if (has_msr_kvm_steal_time)
        msrs[n++].index = MSR_KVM_STEAL_TIME;
    if (has_msr_architectural_pmu) {
        msrs[n++].index = MSR_CORE_PERF_FIXED_CTR_CTRL;
        msrs[n++].index = MSR_CORE_PERF_GLOBAL_CTRL;
        msrs[n++].index = MSR_CORE_PERF_GLOBAL_STATUS;
        msrs[n++].index = MSR_CORE_PERF_GLOBAL_OVF_CTRL;
        for (i = 0; i < MAX_FIXED_COUNTERS; i++) {
            msrs[n++].index = MSR_CORE_PERF_FIXED_CTR0 + i;
        }
        for (i = 0; i < num_architectural_pmu_counters; i++) {
            msrs[n++].index = MSR_P6_PERFCTR0 + i;
            msrs[n++].index = MSR_P6_EVNTSEL0 + i;
        }
    }

    if (kvm_check_extension(kvm_state, KVM_CAP_HYPERV)) {
        msrs[n++].index = HV_X64_MSR_GUEST_OS_ID;
        msrs[n++].index = HV_X64_MSR_HYPERCALL;
    }
    if (has_msr_pv_eoi_en) {
        msrs[n++].index = MSR_KVM_PV_EOI_EN;
    }

#ifdef KVM_CAP_MCE
    if (env->mcg_cap) {
        msrs[n++].index = MSR_MCG_STATUS;
        msrs[n++].index = MSR_MCG_CTL;
        for (i = 0; i < (env->mcg_cap & 0xff) * 4; i++)
            msrs[n++].index = MSR_MC0_CTL + i;
    }
#endif

    rc = kvm_get_msrs(env, msrs, n);
    if (rc == -1) {
        perror("kvm_get_msrs FAILED");
    }
    else {
        n = rc; /* actual number of MSRs */
        for (i=0 ; i<n; i++) {
            if (get_msr_entry(&msrs[i], env))
                return;
        }
    }
    kvm_arch_save_mpstate(env);
}

static void do_cpuid_ent(struct kvm_cpuid_entry2 *e, uint32_t function,
                         uint32_t count, CPUState *env)
{
    env->regs[R_EAX] = function;
    env->regs[R_ECX] = count;
    qemu_kvm_cpuid_on_env(env);
    e->function = function;
    e->flags = 0;
    e->index = 0;
    e->eax = env->regs[R_EAX];
    e->ebx = env->regs[R_EBX];
    e->ecx = env->regs[R_ECX];
    e->edx = env->regs[R_EDX];
}

static void kvm_trim_features(uint32_t *features, uint32_t supported)
{
    int i;
    uint32_t mask;

    for (i = 0; i < 32; ++i) {
        mask = 1U << i;
        if ((*features & mask) && !(supported & mask)) {
            *features &= ~mask;
        }
    }
}

static void cpu_update_state(void *opaque, int running, RunState state)
{
    CPUState *env = opaque;

    if (running) {
        env->tsc_valid = false;
    }
}

unsigned long kvm_arch_vcpu_id(CPUArchState *env)
{
    return env->cpuid_apic_id;
}

/*
 * Find matching entry for function/index on kvm_cpuid2 struct
 */
static struct kvm_cpuid_entry2 *cpuid_find_entry(struct kvm_cpuid_entry2 *entries,
                                                 int nent,
                                                 uint32_t function,
                                                 uint32_t index)
{
    int i;
    for (i = 0; i < nent; ++i) {
        if (entries[i].function == function &&
            entries[i].index == index) {
            return &entries[i];
        }
    }
    /* not found: */
    return NULL;
}

static Error *invtsc_mig_blocker;

static const VMStateDescription vmstate_cpu_invtsc = {
    .name = "cpu_invtsc",
    .version_id = 1,
    .minimum_version_id = 1,
    .minimum_version_id_old = 1,
    .unmigratable = 1,
    .fields      = (VMStateField []) {
        VMSTATE_UINT32(halted, CPUState), /* dummy */
        VMSTATE_END_OF_LIST()
    }
};

int kvm_arch_init_vcpu(CPUState *cenv)
{
    struct kvm_cpuid_entry2 cpuid_ent[100];
    struct kvm_cpuid_entry2 *c;
#ifdef KVM_CPUID_SIGNATURE
    struct kvm_cpuid_entry2 *pv_ent;
    uint32_t signature[3];
#endif
    int cpuid_nent = 0;
    CPUState copy;
    uint32_t i, j, limit;

    qemu_kvm_load_lapic(cenv);

    cenv->interrupt_injected = -1;

#ifdef KVM_CPUID_SIGNATURE
    /* Paravirtualization CPUIDs */
    memcpy(signature, "KVMKVMKVM\0\0\0", 12);
    pv_ent = &cpuid_ent[cpuid_nent++];
    memset(pv_ent, 0, sizeof(*pv_ent));
    pv_ent->function = KVM_CPUID_SIGNATURE;
    pv_ent->eax = 0;
    if (hyperv_relaxed_timing_enabled()) {
        pv_ent->eax = HYPERV_CPUID_ENLIGHTMENT_INFO;
    }
    pv_ent->ebx = signature[0];
    pv_ent->ecx = signature[1];
    pv_ent->edx = signature[2];

    pv_ent = &cpuid_ent[cpuid_nent++];
    memset(pv_ent, 0, sizeof(*pv_ent));
    pv_ent->function = KVM_CPUID_FEATURES;
    pv_ent->eax = cenv->cpuid_kvm_features & kvm_arch_get_supported_cpuid(cenv->kvm_state,
						KVM_CPUID_FEATURES, 0, R_EAX);

    if (hyperv_relaxed_timing_enabled()) {
        memcpy(signature, "Hv#1\0\0\0\0\0\0\0\0", 12);
        pv_ent->eax = signature[0];

        pv_ent = &cpuid_ent[cpuid_nent++];
        memset(pv_ent, 0, sizeof(*pv_ent));
        pv_ent->function = HYPERV_CPUID_ENLIGHTMENT_INFO;
        pv_ent->eax |= HV_X64_RELAXED_TIMING_RECOMMENDED;
    }

#endif

    kvm_trim_features(&cenv->cpuid_features,
                      kvm_arch_get_supported_cpuid(cenv->kvm_state, 1, 0, R_EDX));

    /* prevent the hypervisor bit from being cleared by the kernel */
    kvm_trim_features(&cenv->cpuid_ext_features,
                      kvm_arch_get_supported_cpuid(cenv->kvm_state, 1, 0, R_ECX));
    kvm_trim_features(&cenv->cpuid_ext2_features,
                      kvm_arch_get_supported_cpuid(cenv->kvm_state, 0x80000001, 0, R_EDX));
    kvm_trim_features(&cenv->cpuid_ext3_features,
                      kvm_arch_get_supported_cpuid(cenv->kvm_state, 0x80000001, 0, R_ECX));

    copy = *cenv;

    has_msr_pv_eoi_en = pv_ent->eax & (1 << KVM_FEATURE_PV_EOI);
    has_msr_kvm_steal_time = pv_ent->eax & (1 << KVM_FEATURE_STEAL_TIME);

    copy.regs[R_EAX] = 0;
    qemu_kvm_cpuid_on_env(&copy);
    limit = copy.regs[R_EAX];

    for (i = 0; i <= limit; ++i) {
        if (i == 4 || i == 0xb || i == 0xd) {
            for (j = 0; ; ++j) {
                if (i == 0xd && j == 64)
                    break;

                do_cpuid_ent(&cpuid_ent[cpuid_nent], i, j, &copy);

                if (i == 0xd && copy.regs[R_EAX] == 0)
                    continue;

                cpuid_ent[cpuid_nent].flags = KVM_CPUID_FLAG_SIGNIFCANT_INDEX;
                cpuid_ent[cpuid_nent].index = j;

                cpuid_nent++;

                if (i == 4 && copy.regs[R_EAX] == 0)
                    break;
                if (i == 0xb && !(copy.regs[R_ECX] & 0xff00))
                    break;
            }
        } else
            do_cpuid_ent(&cpuid_ent[cpuid_nent++], i, 0, &copy);
    }

    if (limit >= 0x0a) {
        uint32_t ver;

        copy.regs[R_EAX] = 0x0a;
        qemu_kvm_cpuid_on_env(&copy);
        ver = copy.regs[R_EAX];
        if ((ver & 0xff) > 0) {
            has_msr_architectural_pmu = true;
            num_architectural_pmu_counters = (ver & 0xff00) >> 8;

            /* Shouldn't be more than 32, since that's the number of bits
             * available in EBX to tell us _which_ counters are available.
             * Play it safe.
             */
            if (num_architectural_pmu_counters > MAX_GP_COUNTERS) {
                num_architectural_pmu_counters = MAX_GP_COUNTERS;
            }
        }
    }

    copy.regs[R_EAX] = 0x80000000;
    qemu_kvm_cpuid_on_env(&copy);
    limit = copy.regs[R_EAX];

    for (i = 0x80000000; i <= limit; ++i)
	do_cpuid_ent(&cpuid_ent[cpuid_nent++], i, 0, &copy);

    c = cpuid_find_entry(cpuid_ent, cpuid_nent, 0x80000007, 0);
    if (c && (c->edx & 1<<8) && invtsc_mig_blocker == NULL) {
        /* migration */
        error_setg(&invtsc_mig_blocker,
                   "State blocked by non-migratable CPU device"
                   " (invtsc flag)");
        migrate_add_blocker(invtsc_mig_blocker);
        /* savevm */
        vmstate_register(NULL, 1, &vmstate_cpu_invtsc, cenv);
    }

    kvm_setup_cpuid2(cenv, cpuid_nent, cpuid_ent);

#ifdef KVM_CAP_MCE
    if (((cenv->cpuid_version >> 8)&0xF) >= 6
        && (cenv->cpuid_features&(CPUID_MCE|CPUID_MCA)) == (CPUID_MCE|CPUID_MCA)
        && kvm_check_extension(kvm_state, KVM_CAP_MCE) > 0) {
        uint64_t mcg_cap;
        int banks;

        if (kvm_get_mce_cap_supported(kvm_context, &mcg_cap, &banks))
            perror("kvm_get_mce_cap_supported FAILED");
        else {
            if (banks > MCE_BANKS_DEF)
                banks = MCE_BANKS_DEF;
            mcg_cap &= MCE_CAP_DEF;
            mcg_cap |= banks;
            if (kvm_setup_mce(cenv, &mcg_cap))
                perror("kvm_setup_mce FAILED");
            else
                cenv->mcg_cap = mcg_cap;
        }
    }
#endif

#ifdef KVM_EXIT_TPR_ACCESS
    kvm_tpr_vcpu_start(cenv);
#endif

    qemu_add_vm_change_state_handler(cpu_update_state, cenv);

    if (kvm_check_extension(kvm_state, KVM_CAP_XSAVE)) {
        cenv->kvm_xsave_buf = qemu_memalign(4096, sizeof(struct kvm_xsave));
    }

    return 0;
}

int kvm_arch_halt(CPUState *env)
{

    if (!((env->interrupt_request & CPU_INTERRUPT_HARD) &&
	  (env->eflags & IF_MASK)) &&
	!(env->interrupt_request & CPU_INTERRUPT_NMI)) {
            env->halted = 1;
    }
    return 1;
}

int kvm_arch_pre_run(CPUState *env, struct kvm_run *run)
{
    if (env->update_vapic) {
        kvm_tpr_enable_vapic(env);
    }
    if (!kvm_irqchip_in_kernel())
	kvm_set_cr8(env, cpu_get_apic_tpr(env));
    return 0;
}

int kvm_arch_has_work(CPUState *env)
{
    if (((env->interrupt_request & CPU_INTERRUPT_HARD) &&
	 (env->eflags & IF_MASK)) ||
	(env->interrupt_request & CPU_INTERRUPT_NMI))
	return 1;
    return 0;
}

int kvm_arch_try_push_interrupts(void *opaque)
{
    CPUState *env = cpu_single_env;
    int r, irq;

    if (kvm_is_ready_for_interrupt_injection(env) &&
        (env->interrupt_request & CPU_INTERRUPT_HARD) &&
        (env->eflags & IF_MASK)) {
            env->interrupt_request &= ~CPU_INTERRUPT_HARD;
	    irq = cpu_get_pic_interrupt(env);
	    if (irq >= 0) {
		r = kvm_inject_irq(env, irq);
		if (r < 0)
		    printf("cpu %d fail inject %x\n", env->cpu_index, irq);
	    }
    }

    return (env->interrupt_request & CPU_INTERRUPT_HARD) != 0;
}

#ifdef KVM_CAP_USER_NMI
void kvm_arch_push_nmi(void *opaque)
{
    CPUState *env = cpu_single_env;
    int r;

    if (likely(!(env->interrupt_request & CPU_INTERRUPT_NMI)))
        return;

    env->interrupt_request &= ~CPU_INTERRUPT_NMI;
    r = kvm_inject_nmi(env);
    if (r < 0)
        printf("cpu %d fail inject NMI\n", env->cpu_index);
}
#endif /* KVM_CAP_USER_NMI */

static int kvm_reset_msrs(CPUState *env)
{
    struct {
        struct kvm_msrs info;
        struct kvm_msr_entry entries[100];
    } msr_data;
    int n, n_msrs;
    struct kvm_msr_entry *msrs = msr_data.entries;

    if (!kvm_msr_list)
        return -1;

    n_msrs = 0;
    for (n = 0; n < kvm_msr_list->nmsrs; n++) {
        if (kvm_msr_list->indices[n] == MSR_IA32_TSC)
            continue;
        if (kvm_msr_list->indices[n] == MSR_PAT) {
            set_msr_entry(&msrs[n_msrs++], kvm_msr_list->indices[n], 0x0007040600070406ULL);
            continue;
        }
        set_msr_entry(&msrs[n_msrs++], kvm_msr_list->indices[n], 0);
    }

    msr_data.info.nmsrs = n_msrs;

    return kvm_vcpu_ioctl(env, KVM_SET_MSRS, &msr_data);
}


void kvm_arch_cpu_reset(CPUState *env)
{
    kvm_reset_msrs(env);
    kvm_arch_reset_vcpu(env);
    kvm_arch_load_regs(env);
    kvm_put_vcpu_events(env);
    if (!cpu_is_bsp(env)) {
	if (kvm_irqchip_in_kernel()) {
#ifdef KVM_CAP_MP_STATE
	    kvm_reset_mpstate(env);
#endif
	} else {
	    env->interrupt_request &= ~CPU_INTERRUPT_HARD;
	    env->halted = 1;
	}
    }
}

int kvm_arch_insert_sw_breakpoint(CPUState *env, struct kvm_sw_breakpoint *bp)
{
    uint8_t int3 = 0xcc;

    if (cpu_memory_rw_debug(env, bp->pc, (uint8_t *)&bp->saved_insn, 1, 0) ||
        cpu_memory_rw_debug(env, bp->pc, &int3, 1, 1))
        return -EINVAL;
    return 0;
}

int kvm_arch_remove_sw_breakpoint(CPUState *env, struct kvm_sw_breakpoint *bp)
{
    uint8_t int3;

    if (cpu_memory_rw_debug(env, bp->pc, &int3, 1, 0) || int3 != 0xcc ||
        cpu_memory_rw_debug(env, bp->pc, (uint8_t *)&bp->saved_insn, 1, 1))
        return -EINVAL;
    return 0;
}

#ifdef KVM_CAP_SET_GUEST_DEBUG
static struct {
    target_ulong addr;
    int len;
    int type;
} hw_breakpoint[4];

static int nb_hw_breakpoint;

static int find_hw_breakpoint(target_ulong addr, int len, int type)
{
    int n;

    for (n = 0; n < nb_hw_breakpoint; n++)
	if (hw_breakpoint[n].addr == addr && hw_breakpoint[n].type == type &&
	    (hw_breakpoint[n].len == len || len == -1))
	    return n;
    return -1;
}

int kvm_arch_insert_hw_breakpoint(target_ulong addr,
                                  target_ulong len, int type)
{
    switch (type) {
    case GDB_BREAKPOINT_HW:
	len = 1;
	break;
    case GDB_WATCHPOINT_WRITE:
    case GDB_WATCHPOINT_ACCESS:
	switch (len) {
	case 1:
	    break;
	case 2:
	case 4:
	case 8:
	    if (addr & (len - 1))
		return -EINVAL;
	    break;
	default:
	    return -EINVAL;
	}
	break;
    default:
	return -ENOSYS;
    }

    if (nb_hw_breakpoint == 4)
        return -ENOBUFS;

    if (find_hw_breakpoint(addr, len, type) >= 0)
        return -EEXIST;

    hw_breakpoint[nb_hw_breakpoint].addr = addr;
    hw_breakpoint[nb_hw_breakpoint].len = len;
    hw_breakpoint[nb_hw_breakpoint].type = type;
    nb_hw_breakpoint++;

    return 0;
}

int kvm_arch_remove_hw_breakpoint(target_ulong addr,
                                  target_ulong len, int type)
{
    int n;

    n = find_hw_breakpoint(addr, (type == GDB_BREAKPOINT_HW) ? 1 : len, type);
    if (n < 0)
        return -ENOENT;

    nb_hw_breakpoint--;
    hw_breakpoint[n] = hw_breakpoint[nb_hw_breakpoint];

    return 0;
}

void kvm_arch_remove_all_hw_breakpoints(void)
{
    nb_hw_breakpoint = 0;
}

static CPUWatchpoint hw_watchpoint;

int kvm_arch_debug(struct kvm_debug_exit_arch *arch_info)
{
    int handle = 0;
    int n;

    if (arch_info->exception == 1) {
	if (arch_info->dr6 & (1 << 14)) {
	    if (cpu_single_env->singlestep_enabled)
		handle = 1;
	} else {
	    for (n = 0; n < 4; n++)
		if (arch_info->dr6 & (1 << n))
		    switch ((arch_info->dr7 >> (16 + n*4)) & 0x3) {
		    case 0x0:
			handle = 1;
			break;
		    case 0x1:
			handle = 1;
			cpu_single_env->watchpoint_hit = &hw_watchpoint;
			hw_watchpoint.vaddr = hw_breakpoint[n].addr;
			hw_watchpoint.flags = BP_MEM_WRITE;
			break;
		    case 0x3:
			handle = 1;
			cpu_single_env->watchpoint_hit = &hw_watchpoint;
			hw_watchpoint.vaddr = hw_breakpoint[n].addr;
			hw_watchpoint.flags = BP_MEM_ACCESS;
			break;
		    }
	}
    } else if (kvm_find_sw_breakpoint(cpu_single_env, arch_info->pc))
	handle = 1;

    if (!handle)
	kvm_update_guest_debug(cpu_single_env,
			(arch_info->exception == 1) ?
			KVM_GUESTDBG_INJECT_DB : KVM_GUESTDBG_INJECT_BP);

    return handle;
}

void kvm_arch_update_guest_debug(CPUState *env, struct kvm_guest_debug *dbg)
{
    const uint8_t type_code[] = {
	[GDB_BREAKPOINT_HW] = 0x0,
	[GDB_WATCHPOINT_WRITE] = 0x1,
	[GDB_WATCHPOINT_ACCESS] = 0x3
    };
    const uint8_t len_code[] = {
	[1] = 0x0, [2] = 0x1, [4] = 0x3, [8] = 0x2
    };
    int n;

    if (kvm_sw_breakpoints_active(env))
	dbg->control |= KVM_GUESTDBG_ENABLE | KVM_GUESTDBG_USE_SW_BP;

    if (nb_hw_breakpoint > 0) {
	dbg->control |= KVM_GUESTDBG_ENABLE | KVM_GUESTDBG_USE_HW_BP;
	dbg->arch.debugreg[7] = 0x0600;
	for (n = 0; n < nb_hw_breakpoint; n++) {
	    dbg->arch.debugreg[n] = hw_breakpoint[n].addr;
	    dbg->arch.debugreg[7] |= (2 << (n * 2)) |
		(type_code[hw_breakpoint[n].type] << (16 + n*4)) |
		(len_code[hw_breakpoint[n].len] << (18 + n*4));
	}
    }
}
#endif

#ifdef CONFIG_KVM_DEVICE_ASSIGNMENT
void kvm_arch_do_ioperm(void *_data)
{
    struct ioperm_data *data = _data;
    ioperm(data->start_port, data->num, data->turn_on);
}
#endif

/*
 * Setup x86 specific IRQ routing
 */
int kvm_arch_init_irq_routing(void)
{
    int i, r;

    if (kvm_irqchip && kvm_has_gsi_routing(kvm_context)) {
        kvm_clear_gsi_routes(kvm_context);
        for (i = 0; i < 8; ++i) {
            if (i == 2)
                continue;
            r = kvm_add_irq_route(kvm_context, i, KVM_IRQCHIP_PIC_MASTER, i);
            if (r < 0)
                return r;
        }
        for (i = 8; i < 16; ++i) {
            r = kvm_add_irq_route(kvm_context, i, KVM_IRQCHIP_PIC_SLAVE, i - 8);
            if (r < 0)
                return r;
        }
        for (i = 0; i < 24; ++i) {
            if (i == 0) {
                r = kvm_add_irq_route(kvm_context, i, KVM_IRQCHIP_IOAPIC, 2);
            } else if (i != 2) {
                r = kvm_add_irq_route(kvm_context, i, KVM_IRQCHIP_IOAPIC, i);
            }
            if (r < 0)
                return r;
        }
        kvm_commit_irq_routes(kvm_context);
    }
    return 0;
}

uint32_t kvm_arch_get_supported_cpuid(KVMState *env, uint32_t function,
                                      uint32_t index, int reg)
{
    return kvm_get_supported_cpuid(kvm_context, function, index, reg);
}

void kvm_arch_process_irqchip_events(CPUState *env)
{
    if (env->interrupt_request & CPU_INTERRUPT_INIT) {
        kvm_cpu_synchronize_state(env);
        do_cpu_init(env);
    }
    if (env->interrupt_request & CPU_INTERRUPT_SIPI) {
        kvm_cpu_synchronize_state(env);
        do_cpu_sipi(env);
    }
}
