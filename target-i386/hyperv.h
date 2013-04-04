#ifndef QEMU_HYPERV_H
#define QEMU_HYPERV_H

#include "qemu-common.h"

#ifndef HYPERV_CPUID_ENLIGHTMENT_INFO
#define HYPERV_CPUID_ENLIGHTMENT_INFO		0x40000004
#endif

#ifndef HV_X64_RELAXED_TIMING_RECOMMENDED
#define HV_X64_RELAXED_TIMING_RECOMMENDED	(1 << 5)
#endif

#ifndef HV_X64_MSR_GUEST_OS_ID
#define HV_X64_MSR_GUEST_OS_ID			0x40000000
#endif

#ifndef HV_X64_MSR_HYPERCALL
#define HV_X64_MSR_HYPERCALL			0x40000001
#endif

#if defined(CONFIG_KVM)
void hyperv_enable_relaxed_timing(bool val);
#else
static inline void hyperv_enable_relaxed_timing(bool val) { }
#endif

bool hyperv_relaxed_timing_enabled(void);

#endif /* QEMU_HYPERV_H */
