/*
 *  i386 CPUID helper functions
 *
 *  Copyright (c) 2003 Fabrice Bellard
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>

#include "cpu.h"
#include "kvm.h"
#include "asm/kvm_para.h"

#include "qemu-option.h"
#include "qemu-config.h"
#include "hyperv.h"

/* feature flags taken from "Intel Processor Identification and the CPUID
 * Instruction" and AMD's "CPUID Specification".  In cases of disagreement
 * between feature naming conventions, aliases may be added.
 */
static const char *feature_name[] = {
    "fpu", "vme", "de", "pse",
    "tsc", "msr", "pae", "mce",
    "cx8", "apic", NULL, "sep",
    "mtrr", "pge", "mca", "cmov",
    "pat", "pse36", "pn" /* Intel psn */, "clflush" /* Intel clfsh */,
    NULL, "ds" /* Intel dts */, "acpi", "mmx",
    "fxsr", "sse", "sse2", "ss",
    "ht" /* Intel htt */, "tm", "ia64", "pbe",
};
static const char *ext_feature_name[] = {
    "pni|sse3" /* Intel,AMD sse3 */, "pclmulqdq|pclmuldq", "dtes64", "monitor",
    "ds_cpl", "vmx", "smx", "est",
    "tm2", "ssse3", "cid", NULL,
    "fma", "cx16", "xtpr", "pdcm",
    NULL, "pcid", "dca", "sse4.1|sse4_1",
    "sse4.2|sse4_2", "x2apic", "movbe", "popcnt",
    "tsc-deadline", "aes", "xsave", "osxsave",
    "avx", "f16c", "rdrand", "hypervisor",
};
static const char *ext2_feature_name[] = {
    "fpu", "vme", "de", "pse",
    "tsc", "msr", "pae", "mce",
    "cx8" /* AMD CMPXCHG8B */, "apic", NULL, "syscall",
    "mtrr", "pge", "mca", "cmov",
    "pat", "pse36", NULL, NULL /* Linux mp */,
    "nx|xd", NULL, "mmxext", "mmx",
    "fxsr", "fxsr_opt|ffxsr" /* AMD ffxsr */, "pdpe1gb" /* AMD Page1GB */, "rdtscp",
    NULL, "lm|i64", "3dnowext", "3dnow",
};
static const char *ext3_feature_name[] = {
    "lahf_lm" /* AMD LahfSahf */, "cmp_legacy", "svm", "extapic" /* AMD ExtApicSpace */,
    "cr8legacy" /* AMD AltMovCr8 */, "abm", "sse4a", "misalignsse",
    "3dnowprefetch", "osvw", "ibs", "xop",
    "skinit", "wdt", NULL, "lwp",
    "fma4", "tce", NULL, "nodeid_msr",
    NULL, "tbm", "topoext", "perfctr_core",
    "perfctr_nb", NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
};

static const char *cpuid_7_0_ebx_feature_name[] = {
    "fsgsbase", NULL, NULL, "bmi1", "hle", "avx2", NULL, "smep",
    "bmi2", "erms", "invpcid", "rtm", NULL, NULL, NULL, NULL,
    NULL, NULL, "rdseed", "adx", "smap", NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
};

static const char *cpuid_apm_edx_feature_name[] = {
    NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    "invtsc", NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
};

typedef struct ExtSaveArea {
    bool (*enabled)(const CPUX86State *);
    uint32_t offset, size;
} ExtSaveArea;

static bool cpu_has_avx(const CPUX86State *env)
{
    return env->cpuid_ext_features & CPUID_EXT_AVX;
}

static const ExtSaveArea ext_save_areas[] = {
    [2] = { .enabled = cpu_has_avx, .offset = 0x240, .size = 0x100 },
};

/* collects per-function cpuid data
 */
typedef struct model_features_t {
    uint32_t *guest_feat;
    uint32_t *host_feat;
    uint32_t check_feat;
    uint32_t restrict_feat;
    const char **flag_names;
    const char *cpuid_fn;
    } model_features_t;

int check_cpuid = 0;
int enforce_cpuid = 0;

/* machine-type compatibility settings: */
static bool kvm_pv_eoi_disabled;
static bool pmu_passthrough_enabled;
static bool tsc_deadline_disabled;
static bool kvm_sep_disabled;

static void host_cpuid(uint32_t function, uint32_t count, uint32_t *eax,
                       uint32_t *ebx, uint32_t *ecx, uint32_t *edx);

#define iswhite(c) ((c) && ((c) <= ' ' || '~' < (c)))

/* general substring compare of *[s1..e1) and *[s2..e2).  sx is start of
 * a substring.  ex if !NULL points to the first char after a substring,
 * otherwise the string is assumed to sized by a terminating nul.
 * Return lexical ordering of *s1:*s2.
 */
static int sstrcmp(const char *s1, const char *e1, const char *s2,
    const char *e2)
{
    for (;;) {
        if (!*s1 || !*s2 || *s1 != *s2)
            return (*s1 - *s2);
        ++s1, ++s2;
        if (s1 == e1 && s2 == e2)
            return (0);
        else if (s1 == e1)
            return (*s2);
        else if (s2 == e2)
            return (*s1);
    }
}

/* compare *[s..e) to *altstr.  *altstr may be a simple string or multiple
 * '|' delimited (possibly empty) strings in which case search for a match
 * within the alternatives proceeds left to right.  Return 0 for success,
 * non-zero otherwise.
 */
static int altcmp(const char *s, const char *e, const char *altstr)
{
    const char *p, *q;

    for (q = p = altstr; ; ) {
        while (*p && *p != '|')
            ++p;
        if ((q == p && !*s) || (q != p && !sstrcmp(s, e, q, p)))
            return (0);
        if (!*p)
            return (1);
        else
            q = ++p;
    }
}

/* search featureset for flag *[s..e), if found set corresponding bit in
 * *pval and return success, otherwise return false 
 */
static bool lookup_feature(uint32_t *pval, const char *s, const char *e,
    const char **featureset)
{
    uint32_t mask;
    const char **ppc;
    bool found = false;

    for (mask = 1, ppc = featureset; mask; mask <<= 1, ++ppc) {
        if (*ppc && !altcmp(s, e, *ppc)) {
            *pval |= mask;
            found = true;
        }
    }
    return found;
}

static const char *kvm_feature_name[] = {
    "kvmclock", "kvm_nopiodelay", "kvm_mmu", "kvmclock", NULL, NULL, "kvm_pv_eoi", NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
};

static void add_flagname_to_bitmaps(const char *flagname, uint32_t *features,
                                    uint32_t *ext_features,
                                    uint32_t *ext2_features,
                                    uint32_t *ext3_features,
                                    uint32_t *kvm_features,
                                    uint32_t *cpuid_7_0_ebx_features,
                                    uint32_t *apm_edx_features)
{
    if (!lookup_feature(features, flagname, NULL, feature_name) &&
        !lookup_feature(ext_features, flagname, NULL, ext_feature_name) &&
        !lookup_feature(ext2_features, flagname, NULL, ext2_feature_name) &&
        !lookup_feature(ext3_features, flagname, NULL, ext3_feature_name) &&
        !lookup_feature(kvm_features, flagname, NULL, kvm_feature_name) &&
        !lookup_feature(cpuid_7_0_ebx_features, flagname, NULL,
                        cpuid_7_0_ebx_feature_name) &&
        !lookup_feature(apm_edx_features, flagname, NULL,
                        cpuid_apm_edx_feature_name))
            fprintf(stderr, "CPU feature %s not found\n", flagname);
}

typedef struct x86_def_t {
    struct x86_def_t *next;
    const char *name;
    uint32_t level;
    uint32_t vendor1, vendor2, vendor3;
    int family;
    int model;
    int stepping;
    uint32_t features, ext_features, ext2_features, ext3_features, kvm_features;
    uint32_t apm_edx_features;
    uint32_t xlevel;
    char model_id[48];
    int vendor_override;
    /* The feature bits on CPUID[EAX=7,ECX=0].EBX */
    uint32_t cpuid_7_0_ebx_features;
    bool pmu_passthrough;
} x86_def_t;

#define I486_FEATURES (CPUID_FP87 | CPUID_VME | CPUID_PSE)
#define PENTIUM_FEATURES (I486_FEATURES | CPUID_DE | CPUID_TSC | \
          CPUID_MSR | CPUID_MCE | CPUID_CX8 | CPUID_MMX)
#define PENTIUM2_FEATURES (PENTIUM_FEATURES | CPUID_PAE | CPUID_SEP | \
          CPUID_MTRR | CPUID_PGE | CPUID_MCA | CPUID_CMOV | CPUID_PAT | \
          CPUID_PSE36 | CPUID_FXSR)
#define PENTIUM3_FEATURES (PENTIUM2_FEATURES | CPUID_SSE)
#define PPRO_FEATURES (CPUID_FP87 | CPUID_DE | CPUID_PSE | CPUID_TSC | \
          CPUID_MSR | CPUID_MCE | CPUID_CX8 | CPUID_PGE | CPUID_CMOV | \
          CPUID_PAT | CPUID_FXSR | CPUID_MMX | CPUID_SSE | CPUID_SSE2 | \
          CPUID_PAE | CPUID_SEP | CPUID_APIC)

/* maintains list of cpu model definitions
 */
static x86_def_t *x86_defs = {NULL};

/* built-in cpu model definitions (deprecated)
 */
static x86_def_t builtin_x86_defs[] = {
#ifdef TARGET_X86_64
    {
        .name = "qemu64",
        .level = 4,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 6,
        /* Athlon (PM core) || P2 with on-die L2 cache - P6 has no sep */
        .model = 6,
        .stepping = 3,
        .features = PPRO_FEATURES |
        /* these features are needed for Win64 and aren't fully implemented */
            CPUID_MTRR | CPUID_CLFLUSH | CPUID_MCA |
        /* this feature is needed for Solaris and isn't fully implemented */
            CPUID_PSE36,
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_CX16 | CPUID_EXT_POPCNT,
        .ext2_features = (PPRO_FEATURES & 0x0183F3FF) |
            CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        .ext3_features = CPUID_EXT3_LAHF_LM | CPUID_EXT3_SVM |
            CPUID_EXT3_ABM | CPUID_EXT3_SSE4A,
        .xlevel = 0x8000000A,
        .model_id = "QEMU Virtual CPU version " QEMU_VERSION,
    },
    {
        .name = "phenom",
        .level = 5,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 16,
        .model = 2,
        .stepping = 3,
        /* Missing: CPUID_VME, CPUID_HT */
        .features = PPRO_FEATURES |
            CPUID_MTRR | CPUID_CLFLUSH | CPUID_MCA |
            CPUID_PSE36,
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_MONITOR | CPUID_EXT_CX16 |
            CPUID_EXT_POPCNT,
        /* Missing: CPUID_EXT2_PDPE1GB, CPUID_EXT2_RDTSCP */
        .ext2_features = (PPRO_FEATURES & 0x0183F3FF) |
            CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX |
            CPUID_EXT2_3DNOW | CPUID_EXT2_3DNOWEXT | CPUID_EXT2_MMXEXT |
            CPUID_EXT2_FFXSR,
        /* Missing: CPUID_EXT3_CMP_LEG, CPUID_EXT3_EXTAPIC,
                    CPUID_EXT3_CR8LEG,
                    CPUID_EXT3_MISALIGNSSE, CPUID_EXT3_3DNOWPREFETCH,
                    CPUID_EXT3_OSVW, CPUID_EXT3_IBS */
        .ext3_features = CPUID_EXT3_LAHF_LM | CPUID_EXT3_SVM |
            CPUID_EXT3_ABM | CPUID_EXT3_SSE4A,
        .xlevel = 0x8000001A,
        .model_id = "AMD Phenom(tm) 9550 Quad-Core Processor"
    },
    {
        .name = "core2duo",
        .level = 10,
        .family = 6,
        .model = 15,
        .stepping = 11,
	/* The original CPU also implements these features:
               CPUID_VME, CPUID_DTS, CPUID_ACPI, CPUID_SS, CPUID_HT,
               CPUID_TM, CPUID_PBE */
        .features = PPRO_FEATURES |
            CPUID_MTRR | CPUID_CLFLUSH | CPUID_MCA |
            CPUID_PSE36,
	/* The original CPU also implements these ext features:
               CPUID_EXT_DTES64, CPUID_EXT_DSCPL, CPUID_EXT_VMX, CPUID_EXT_EST,
               CPUID_EXT_TM2, CPUID_EXT_CX16, CPUID_EXT_XTPR, CPUID_EXT_PDCM */
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_MONITOR | CPUID_EXT_SSSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .xlevel = 0x80000008,
        .model_id = "Intel(R) Core(TM)2 Duo CPU     T7700  @ 2.40GHz",
    },
    {
        .name = "kvm64",
        .level = 5,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 15,
        .model = 6,
        .stepping = 1,
        /* Missing: CPUID_VME, CPUID_HT */
        .features = PPRO_FEATURES |
            CPUID_MTRR | CPUID_CLFLUSH | CPUID_MCA |
            CPUID_PSE36,
        /* Missing: CPUID_EXT_POPCNT, CPUID_EXT_MONITOR */
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_CX16,
        /* Missing: CPUID_EXT2_PDPE1GB, CPUID_EXT2_RDTSCP */
        .ext2_features = (PPRO_FEATURES & 0x0183F3FF) |
            CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        /* Missing: CPUID_EXT3_LAHF_LM, CPUID_EXT3_CMP_LEG, CPUID_EXT3_EXTAPIC,
                    CPUID_EXT3_CR8LEG, CPUID_EXT3_ABM, CPUID_EXT3_SSE4A,
                    CPUID_EXT3_MISALIGNSSE, CPUID_EXT3_3DNOWPREFETCH,
                    CPUID_EXT3_OSVW, CPUID_EXT3_IBS, CPUID_EXT3_SVM */
        .ext3_features = 0,
        .xlevel = 0x80000008,
        .model_id = "Common KVM processor"
    },
#endif
    {
        .name = "qemu32",
        .level = 4,
        .family = 6,
        .model = 3,
        .stepping = 3,
        .features = PPRO_FEATURES,
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_POPCNT,
        .xlevel = 0,
        .model_id = "QEMU Virtual CPU version " QEMU_VERSION,
    },
    {
        .name = "coreduo",
        .level = 10,
        .family = 6,
        .model = 14,
        .stepping = 8,
        /* The original CPU also implements these features:
               CPUID_DTS, CPUID_ACPI, CPUID_SS, CPUID_HT,
               CPUID_TM, CPUID_PBE */
        .features = PPRO_FEATURES | CPUID_VME |
            CPUID_MTRR | CPUID_CLFLUSH | CPUID_MCA,
        /* The original CPU also implements these ext features:
               CPUID_EXT_VMX, CPUID_EXT_EST, CPUID_EXT_TM2, CPUID_EXT_XTPR,
               CPUID_EXT_PDCM */
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_MONITOR,
        .ext2_features = CPUID_EXT2_NX,
        .xlevel = 0x80000008,
        .model_id = "Genuine Intel(R) CPU           T2600  @ 2.16GHz",
    },
    {
        .name = "486",
        .level = 0,
        .family = 4,
        .model = 0,
        .stepping = 0,
        .features = I486_FEATURES,
        .xlevel = 0,
    },
    {
        .name = "pentium",
        .level = 1,
        .family = 5,
        .model = 4,
        .stepping = 3,
        .features = PENTIUM_FEATURES,
        .xlevel = 0,
    },
    {
        .name = "pentium2",
        .level = 2,
        .family = 6,
        .model = 5,
        .stepping = 2,
        .features = PENTIUM2_FEATURES,
        .xlevel = 0,
    },
    {
        .name = "pentium3",
        .level = 2,
        .family = 6,
        .model = 7,
        .stepping = 3,
        .features = PENTIUM3_FEATURES,
        .xlevel = 0,
    },
    {
        .name = "athlon",
        .level = 2,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 6,
        .model = 2,
        .stepping = 3,
        .features = PPRO_FEATURES | CPUID_PSE36 | CPUID_VME | CPUID_MTRR | CPUID_MCA,
        .ext2_features = (PPRO_FEATURES & 0x0183F3FF) | CPUID_EXT2_MMXEXT | CPUID_EXT2_3DNOW | CPUID_EXT2_3DNOWEXT,
        .xlevel = 0x80000008,
        /* XXX: put another string ? */
        .model_id = "QEMU Virtual CPU version " QEMU_VERSION,
    },
    {
        .name = "n270",
        /* original is on level 10 */
        .level = 5,
        .family = 6,
        .model = 28,
        .stepping = 2,
        .features = PPRO_FEATURES |
            CPUID_MTRR | CPUID_CLFLUSH | CPUID_MCA | CPUID_VME,
            /* Missing: CPUID_DTS | CPUID_ACPI | CPUID_SS |
             * CPUID_HT | CPUID_TM | CPUID_PBE */
            /* Some CPUs got no CPUID_SEP */
        .ext_features = CPUID_EXT_MONITOR |
            CPUID_EXT_SSE3 /* PNI */ | CPUID_EXT_SSSE3,
            /* Missing: CPUID_EXT_DSCPL | CPUID_EXT_EST |
             * CPUID_EXT_TM2 | CPUID_EXT_XTPR */
        .ext2_features = (PPRO_FEATURES & 0x0183F3FF) | CPUID_EXT2_NX,
        /* Missing: .ext3_features = CPUID_EXT3_LAHF_LM */
        .xlevel = 0x8000000A,
        .model_id = "Intel(R) Atom(TM) CPU N270   @ 1.60GHz",
    },
    {
        .name = "cpu64-rhel6",
        .level = 4,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 6,
        .model = 13,
        .stepping = 3,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_CX16 | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_FXSR | CPUID_EXT2_MMX |
             CPUID_EXT2_NX | CPUID_EXT2_PAT | CPUID_EXT2_CMOV | CPUID_EXT2_PGE |
             CPUID_EXT2_SYSCALL | CPUID_EXT2_APIC | CPUID_EXT2_CX8 |
             CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR | CPUID_EXT2_TSC |
             CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .ext3_features = CPUID_EXT3_SSE4A | CPUID_EXT3_ABM | CPUID_EXT3_SVM |
             CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000000A,
        .model_id = "QEMU Virtual CPU version (cpu64-rhel6)",
    },
    {
        .name = "cpu64-rhel5",
        .level = 4,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 6,
        .model = 6,
        .stepping = 3,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_3DNOW | CPUID_EXT2_3DNOWEXT |
             CPUID_EXT2_LM | CPUID_EXT2_FXSR | CPUID_EXT2_MMX | CPUID_EXT2_NX |
             CPUID_EXT2_PAT | CPUID_EXT2_CMOV | CPUID_EXT2_PGE |
             CPUID_EXT2_SYSCALL | CPUID_EXT2_APIC | CPUID_EXT2_CX8 |
             CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR | CPUID_EXT2_TSC |
             CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .ext3_features = CPUID_EXT3_SVM,
        .xlevel = 0x8000000A,
        .model_id = "QEMU Virtual CPU version (cpu64-rhel5)",
    },
    {
        .name = "Conroe",
        .level = 4,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 15,
        .stepping = 3,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_X2APIC | CPUID_EXT_SSSE3 | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000000A,
        .model_id = "Intel Celeron_4x0 (Conroe/Merom Class Core 2)",
    },
    {
        .name = "Penryn",
        .level = 4,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 23,
        .stepping = 3,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_X2APIC | CPUID_EXT_SSE41 | CPUID_EXT_CX16 |
             CPUID_EXT_SSSE3 | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000000A,
        .model_id = "Intel Core 2 Duo P9xxx (Penryn Class Core 2)",
    },
    {
        .name = "Nehalem",
        .level = 4,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 26,
        .stepping = 3,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_POPCNT | CPUID_EXT_X2APIC | CPUID_EXT_SSE42 |
             CPUID_EXT_SSE41 | CPUID_EXT_CX16 | CPUID_EXT_SSSE3 |
             CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000000A,
        .model_id = "Intel Core i7 9xx (Nehalem Class Core i7)",
    },
    {
        .name = "Westmere",
        .level = 11,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 44,
        .stepping = 1,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_PAT | CPUID_CMOV | CPUID_PGE | CPUID_SEP | CPUID_APIC |
             CPUID_CX8 | CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC |
             CPUID_PSE | CPUID_DE | CPUID_FP87 | CPUID_MTRR | CPUID_CLFLUSH |
             CPUID_MCA | CPUID_PSE36,
        .ext_features = CPUID_EXT_SSE3 | CPUID_EXT_CX16 | CPUID_EXT_SSSE3 |
             CPUID_EXT_SSE41 | CPUID_EXT_SSE42 | CPUID_EXT_X2APIC |
             CPUID_EXT_POPCNT | CPUID_EXT_AES,
        .ext2_features = CPUID_EXT2_FXSR | CPUID_EXT2_MMX | CPUID_EXT2_PAT |
             CPUID_EXT2_CMOV | CPUID_EXT2_PGE | CPUID_EXT2_APIC |
             CPUID_EXT2_CX8 | CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR |
             CPUID_EXT2_TSC | CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU |
             CPUID_EXT2_LM | CPUID_EXT2_SYSCALL | CPUID_EXT2_NX,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000000A,
        .model_id = "Westmere E56xx/L56xx/X56xx (Nehalem-C)",
    },
    {
        .name = "SandyBridge",
        .level = 0xd,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 42,
        .stepping = 1,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_AVX | CPUID_EXT_XSAVE | CPUID_EXT_AES |
             CPUID_EXT_POPCNT | CPUID_EXT_X2APIC | CPUID_EXT_SSE42 |
             CPUID_EXT_SSE41 | CPUID_EXT_CX16 | CPUID_EXT_SSSE3 |
             CPUID_EXT_PCLMULQDQ | CPUID_EXT_SSE3 |
             CPUID_EXT_TSC_DEADLINE_TIMER,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_NX | CPUID_EXT2_SYSCALL,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000000A,
        .model_id = "Intel Xeon E312xx (Sandy Bridge)",
    },
    {
        .name = "Haswell",
        .level = 0xd,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 60,
        .stepping = 1,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_AVX | CPUID_EXT_XSAVE | CPUID_EXT_AES |
             CPUID_EXT_POPCNT | CPUID_EXT_X2APIC | CPUID_EXT_SSE42 |
             CPUID_EXT_SSE41 | CPUID_EXT_CX16 | CPUID_EXT_SSSE3 |
             CPUID_EXT_PCLMULQDQ | CPUID_EXT_SSE3 |
             CPUID_EXT_TSC_DEADLINE_TIMER | CPUID_EXT_FMA | CPUID_EXT_MOVBE |
             CPUID_EXT_PCID,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_NX | CPUID_EXT2_SYSCALL,
        .ext3_features = CPUID_EXT3_LAHF_LM,
        .cpuid_7_0_ebx_features = CPUID_7_0_EBX_FSGSBASE | CPUID_7_0_EBX_BMI1 |
            CPUID_7_0_EBX_HLE | CPUID_7_0_EBX_AVX2 | CPUID_7_0_EBX_SMEP |
            CPUID_7_0_EBX_BMI2 | CPUID_7_0_EBX_ERMS | CPUID_7_0_EBX_INVPCID |
            CPUID_7_0_EBX_RTM,
        .xlevel = 0x8000000A,
        .model_id = "Intel Core Processor (Haswell)",
    },
    {
        .name = "Broadwell",
        .level = 0xd,
        .vendor1 = CPUID_VENDOR_INTEL_1,
        .vendor2 = CPUID_VENDOR_INTEL_2,
        .vendor3 = CPUID_VENDOR_INTEL_3,
        .family = 6,
        .model = 61,
        .stepping = 2,
        .features =
            CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
            CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
            CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
            CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
            CPUID_DE | CPUID_FP87,
        .ext_features =
            CPUID_EXT_AVX | CPUID_EXT_XSAVE | CPUID_EXT_AES |
            CPUID_EXT_POPCNT | CPUID_EXT_X2APIC | CPUID_EXT_SSE42 |
            CPUID_EXT_SSE41 | CPUID_EXT_CX16 | CPUID_EXT_SSSE3 |
            CPUID_EXT_PCLMULQDQ | CPUID_EXT_SSE3 |
            CPUID_EXT_TSC_DEADLINE_TIMER | CPUID_EXT_FMA | CPUID_EXT_MOVBE |
            CPUID_EXT_PCID,
        .ext2_features =
            CPUID_EXT2_LM | CPUID_EXT2_NX | CPUID_EXT2_SYSCALL,
        .ext3_features =
            CPUID_EXT3_LAHF_LM | CPUID_EXT3_3DNOWPREFETCH,
        .cpuid_7_0_ebx_features =
            CPUID_7_0_EBX_FSGSBASE | CPUID_7_0_EBX_BMI1 |
            CPUID_7_0_EBX_HLE | CPUID_7_0_EBX_AVX2 | CPUID_7_0_EBX_SMEP |
            CPUID_7_0_EBX_BMI2 | CPUID_7_0_EBX_ERMS | CPUID_7_0_EBX_INVPCID |
            CPUID_7_0_EBX_RTM | CPUID_7_0_EBX_RDSEED | CPUID_7_0_EBX_ADX,
        .xlevel = 0x8000000A,
        .model_id = "Intel Core Processor (Broadwell)",
    },
    {
        .name = "Opteron_G1",
        .level = 5,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 15,
        .model = 6,
        .stepping = 1,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_X2APIC | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_FXSR | CPUID_EXT2_MMX |
             CPUID_EXT2_NX | CPUID_EXT2_PSE36 | CPUID_EXT2_PAT |
             CPUID_EXT2_CMOV | CPUID_EXT2_MCA | CPUID_EXT2_PGE |
             CPUID_EXT2_MTRR | CPUID_EXT2_SYSCALL | CPUID_EXT2_APIC |
             CPUID_EXT2_CX8 | CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR |
             CPUID_EXT2_TSC | CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .xlevel = 0x80000008,
        .model_id = "AMD Opteron 240 (Gen 1 Class Opteron)",
    },
    {
        .name = "Opteron_G2",
        .level = 5,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 15,
        .model = 6,
        .stepping = 1,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_X2APIC | CPUID_EXT_CX16 | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_FXSR | CPUID_EXT2_MMX |
             CPUID_EXT2_NX | CPUID_EXT2_PSE36 | CPUID_EXT2_PAT |
             CPUID_EXT2_CMOV | CPUID_EXT2_MCA | CPUID_EXT2_PGE |
             CPUID_EXT2_MTRR | CPUID_EXT2_SYSCALL | CPUID_EXT2_APIC |
             CPUID_EXT2_CX8 | CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR |
             CPUID_EXT2_TSC | CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .ext3_features = CPUID_EXT3_SVM | CPUID_EXT3_LAHF_LM,
        .xlevel = 0x80000008,
        .model_id = "AMD Opteron 22xx (Gen 2 Class Opteron)",
    },
    {
        .name = "Opteron_G3",
        .level = 5,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 15,
        .model = 6,
        .stepping = 1,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_POPCNT | CPUID_EXT_X2APIC | CPUID_EXT_CX16 |
             CPUID_EXT_MONITOR | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_FXSR | CPUID_EXT2_MMX |
             CPUID_EXT2_NX | CPUID_EXT2_PSE36 | CPUID_EXT2_PAT |
             CPUID_EXT2_CMOV | CPUID_EXT2_MCA | CPUID_EXT2_PGE |
             CPUID_EXT2_MTRR | CPUID_EXT2_SYSCALL | CPUID_EXT2_APIC |
             CPUID_EXT2_CX8 | CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR |
             CPUID_EXT2_TSC | CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .ext3_features = CPUID_EXT3_MISALIGNSSE | CPUID_EXT3_SSE4A |
             CPUID_EXT3_ABM | CPUID_EXT3_SVM | CPUID_EXT3_LAHF_LM,
        .xlevel = 0x80000008,
        .model_id = "AMD Opteron 23xx (Gen 3 Class Opteron)",
    },
    {
        .name = "Opteron_G4",
        .level = 0xd,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 21,
        .model = 1,
        .stepping = 2,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_AVX | CPUID_EXT_XSAVE | CPUID_EXT_AES |
             CPUID_EXT_POPCNT | CPUID_EXT_SSE42 | CPUID_EXT_SSE41 |
             CPUID_EXT_CX16 | CPUID_EXT_SSSE3 | CPUID_EXT_PCLMULQDQ |
             CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM | CPUID_EXT2_PDPE1GB | CPUID_EXT2_FXSR |
             CPUID_EXT2_MMX | CPUID_EXT2_NX | CPUID_EXT2_PSE36 |
             CPUID_EXT2_PAT | CPUID_EXT2_CMOV | CPUID_EXT2_MCA |
             CPUID_EXT2_PGE | CPUID_EXT2_MTRR | CPUID_EXT2_SYSCALL |
             CPUID_EXT2_APIC | CPUID_EXT2_CX8 | CPUID_EXT2_MCE |
             CPUID_EXT2_PAE | CPUID_EXT2_MSR | CPUID_EXT2_TSC | CPUID_EXT2_PSE |
             CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .ext3_features = CPUID_EXT3_FMA4 | CPUID_EXT3_XOP |
             CPUID_EXT3_3DNOWPREFETCH | CPUID_EXT3_MISALIGNSSE |
             CPUID_EXT3_SSE4A | CPUID_EXT3_ABM | CPUID_EXT3_SVM |
             CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000001A,
        .model_id = "AMD Opteron 62xx class CPU",
    },
    {
        .name = "Opteron_G5",
        .level = 0xd,
        .vendor1 = CPUID_VENDOR_AMD_1,
        .vendor2 = CPUID_VENDOR_AMD_2,
        .vendor3 = CPUID_VENDOR_AMD_3,
        .family = 21,
        .model = 2,
        .stepping = 0,
        .features = CPUID_SSE2 | CPUID_SSE | CPUID_FXSR | CPUID_MMX |
             CPUID_CLFLUSH | CPUID_PSE36 | CPUID_PAT | CPUID_CMOV | CPUID_MCA |
             CPUID_PGE | CPUID_MTRR | CPUID_SEP | CPUID_APIC | CPUID_CX8 |
             CPUID_MCE | CPUID_PAE | CPUID_MSR | CPUID_TSC | CPUID_PSE |
             CPUID_DE | CPUID_FP87,
        .ext_features = CPUID_EXT_F16C | CPUID_EXT_AVX | CPUID_EXT_XSAVE |
             CPUID_EXT_AES | CPUID_EXT_POPCNT | CPUID_EXT_SSE42 |
             CPUID_EXT_SSE41 | CPUID_EXT_CX16 | CPUID_EXT_FMA |
             CPUID_EXT_SSSE3 | CPUID_EXT_PCLMULQDQ | CPUID_EXT_SSE3,
        .ext2_features = CPUID_EXT2_LM |
             CPUID_EXT2_PDPE1GB | CPUID_EXT2_FXSR | CPUID_EXT2_MMX |
             CPUID_EXT2_NX | CPUID_EXT2_PSE36 | CPUID_EXT2_PAT |
             CPUID_EXT2_CMOV | CPUID_EXT2_MCA | CPUID_EXT2_PGE |
             CPUID_EXT2_MTRR | CPUID_EXT2_SYSCALL | CPUID_EXT2_APIC |
             CPUID_EXT2_CX8 | CPUID_EXT2_MCE | CPUID_EXT2_PAE | CPUID_EXT2_MSR |
             CPUID_EXT2_TSC | CPUID_EXT2_PSE | CPUID_EXT2_DE | CPUID_EXT2_FPU,
        .ext3_features = CPUID_EXT3_TBM | CPUID_EXT3_FMA4 | CPUID_EXT3_XOP |
             CPUID_EXT3_3DNOWPREFETCH | CPUID_EXT3_MISALIGNSSE |
             CPUID_EXT3_SSE4A | CPUID_EXT3_ABM | CPUID_EXT3_SVM |
             CPUID_EXT3_LAHF_LM,
        .xlevel = 0x8000001A,
        .model_id = "AMD Opteron 63xx class CPU",
    },
};

static int cpu_x86_fill_model_id(char *str)
{
    uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0;
    int i;

    for (i = 0; i < 3; i++) {
        host_cpuid(0x80000002 + i, 0, &eax, &ebx, &ecx, &edx);
        memcpy(str + i * 16 +  0, &eax, 4);
        memcpy(str + i * 16 +  4, &ebx, 4);
        memcpy(str + i * 16 +  8, &ecx, 4);
        memcpy(str + i * 16 + 12, &edx, 4);
    }
    return 0;
}

/* Fill a x86_def_t struct with information about the host CPU, and
 * the CPU features supported by the host hardware + host kernel
 *
 * This function may be called only if KVM is enabled.
 */
static void kvm_cpu_fill_host(x86_def_t *x86_cpu_def)
{
    KVMState *s = kvm_state;
    uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0;

    assert(kvm_enabled());

    x86_cpu_def->name = "host";
    host_cpuid(0x0, 0, &eax, &ebx, &ecx, &edx);
    x86_cpu_def->vendor1 = ebx;
    x86_cpu_def->vendor2 = edx;
    x86_cpu_def->vendor3 = ecx;

    host_cpuid(0x1, 0, &eax, &ebx, &ecx, &edx);
    x86_cpu_def->family = ((eax >> 8) & 0x0F) + ((eax >> 20) & 0xFF);
    x86_cpu_def->model = ((eax >> 4) & 0x0F) | ((eax & 0xF0000) >> 12);
    x86_cpu_def->stepping = eax & 0x0F;

    x86_cpu_def->level = kvm_arch_get_supported_cpuid(s, 0x0, 0, R_EAX);
    x86_cpu_def->features = kvm_arch_get_supported_cpuid(s, 0x1, 0, R_EDX);
    x86_cpu_def->ext_features = kvm_arch_get_supported_cpuid(s, 0x1, 0, R_ECX);

    if (x86_cpu_def->level >= 7) {
        x86_cpu_def->cpuid_7_0_ebx_features =
                    kvm_arch_get_supported_cpuid(s, 0x7, 0, R_EBX);
    } else {
        x86_cpu_def->cpuid_7_0_ebx_features = 0;
    }

    x86_cpu_def->xlevel = kvm_arch_get_supported_cpuid(s, 0x80000000, 0, R_EAX);
    x86_cpu_def->ext2_features =
                kvm_arch_get_supported_cpuid(s, 0x80000001, 0, R_EDX);
    x86_cpu_def->ext3_features =
                kvm_arch_get_supported_cpuid(s, 0x80000001, 0, R_ECX);
    x86_cpu_def->apm_edx_features =
                kvm_arch_get_supported_cpuid(s, 0x80000007, 0, R_EDX);

    cpu_x86_fill_model_id(x86_cpu_def->model_id);
    x86_cpu_def->vendor_override = 0;
    x86_cpu_def->pmu_passthrough = true;
}

static int unavailable_host_feature(struct model_features_t *f, uint32_t mask)
{
    int i;
    uint32_t m;

    for (i = 0; i < 32; ++i)
        if ((m = 1 << i & mask)) {
            fprintf(stderr, "warning: host cpuid %s %s '%s' [0x%08x]\n",
                f->cpuid_fn, m & f->restrict_feat & *f->host_feat ?
                    "flag restricted to guest" : "lacks requested flag",
                f->flag_names[i] ? f->flag_names[i] : "[reserved]", mask);
            break;
        }
    return 0;
}

/* determine the effective set of cpuid features visible to a guest.
 * in the case kvm is enabled, we also selectively include features
 * emulated by the hypervisor
 */ 
static void summary_cpuid_features(CPUX86State *env, x86_def_t *hd)
{
    struct {
        uint32_t *pfeat, cmd, reg, mask;
	} fmap[] = {
            {&hd->features, 0x00000001, R_EDX, 0},
            {&hd->ext_features, 0x00000001, R_ECX, CPUID_EXT_X2APIC},
            {&hd->ext2_features, 0x80000001, R_EDX, 0},
            {&hd->ext3_features, 0x80000001, R_ECX, 0},
            {&hd->cpuid_7_0_ebx_features, 0x7, R_EBX, 0},
            {&hd->apm_edx_features, 0x80000007, R_EDX, 0},
            {NULL}}, *p;

    kvm_cpu_fill_host(hd);
    if (kvm_enabled()) {
        for (p = fmap; p->pfeat; ++p) {
            if (p->mask) {
                *p->pfeat |= p->mask &
                    kvm_arch_get_supported_cpuid(env->kvm_state, p->cmd, 0, p->reg);
            }
        }
    }
}

/* inform the user of any requested cpu features (both explicitly requested
 * flags and implicit cpu model flags) not making their way to the guest
 */
static int kvm_check_features_against_host(CPUX86State *env, x86_def_t *guest_def)
{
    x86_def_t host_def;
    uint32_t mask;
    int rv;
    struct model_features_t ft[] = {
        {&guest_def->features, &host_def.features,
            ~0, 0,
            feature_name, "0000_0001:edx"},
        {&guest_def->ext_features, &host_def.ext_features,
            ~CPUID_EXT_HYPERVISOR, CPUID_EXT_VMX,
            ext_feature_name, "0000_0001:ecx"},
        {&guest_def->ext2_features, &host_def.ext2_features,
            ~PPRO_FEATURES, 0,
            ext2_feature_name, "8000_0001:edx"},
        {&guest_def->ext3_features, &host_def.ext3_features,
            ~0, kvm_nested ? 0 : CPUID_EXT3_SVM,
            ext3_feature_name, "8000_0001:ecx"},
        {&guest_def->cpuid_7_0_ebx_features, &host_def.cpuid_7_0_ebx_features,
            ~0, 0,
            cpuid_7_0_ebx_feature_name, "EAX=7,ECX=0:ebx"},
        {&guest_def->apm_edx_features, &host_def.apm_edx_features,
            ~0, 0,
            cpuid_apm_edx_feature_name, "8000_0007:edx"},
        {NULL}}, *p;

    assert(kvm_enabled());

    summary_cpuid_features(env, &host_def);
    for (rv = 0, p = ft; p->guest_feat; ++p)
        for (mask = 1; mask; mask <<= 1)
            if (mask & p->check_feat & *p->guest_feat &
                (~*p->host_feat | p->restrict_feat)) {
                    unavailable_host_feature(p, mask);
                    rv = 1;
            }
    return rv;
}

static int cpu_x86_find_by_name(x86_def_t *x86_cpu_def, const char *cpu_model)
{
    unsigned int i;
    x86_def_t *def;

    char *s = g_strdup(cpu_model);
    char *featurestr, *name = strtok(s, ",");
    uint32_t plus_features = 0, plus_ext_features = 0, plus_ext2_features = 0, plus_ext3_features = 0, plus_kvm_features = 0;
    uint32_t plus_7_0_ebx_features = 0;
    uint32_t plus_apm_edx_features = 0;
    uint32_t minus_features = 0, minus_ext_features = 0, minus_ext2_features = 0, minus_ext3_features = 0, minus_kvm_features = 0;
    uint32_t minus_7_0_ebx_features = 0;
    uint32_t minus_apm_edx_features = 0;
    uint32_t numvalue;

    for (def = x86_defs; def; def = def->next)
        if (name && !strcmp(name, def->name))
            break;
    if (kvm_enabled() && name && strcmp(name, "host") == 0) {
        kvm_cpu_fill_host(x86_cpu_def);
        /* invtsc enabled only with -cpu host,+invtsc, this emulates
         * the default migratable=no upstream.
         */
        x86_cpu_def->apm_edx_features = 0;
    } else if (!def) {
        fprintf(stderr, "Unknown cpu model: %s\n", name);
        goto error;
    } else {
        memcpy(x86_cpu_def, def, sizeof(*def));
    }

    plus_kvm_features = ~0; /* not supported bits will be filtered out later */

    /* machine-type compatibility bits: */

    /* Disable PV EOI for old machine types.
     * Feature flags can still override. */
    if (kvm_pv_eoi_disabled) {
        plus_kvm_features &= ~(0x1 << KVM_FEATURE_PV_EOI);
    }
    if (pmu_passthrough_enabled) {
        x86_cpu_def->pmu_passthrough = true;
    }
    if (tsc_deadline_disabled) {
        x86_cpu_def->ext_features &= ~CPUID_EXT_TSC_DEADLINE_TIMER;
    }

    /* RHEL 6.4 and below machine types have SEP disabled */
    if (kvm_sep_disabled) {
	    x86_cpu_def->features &= ~CPUID_SEP;
    }

    /* end of machine-type compatibility bits */

    add_flagname_to_bitmaps("hypervisor", &plus_features,
        &plus_ext_features, &plus_ext2_features, &plus_ext3_features,
        &plus_kvm_features, &plus_7_0_ebx_features,
        &plus_apm_edx_features);

    featurestr = strtok(NULL, ",");

    while (featurestr) {
        char *val;
        if (featurestr[0] == '+') {
            add_flagname_to_bitmaps(featurestr + 1, &plus_features,
                            &plus_ext_features, &plus_ext2_features,
                            &plus_ext3_features, &plus_kvm_features,
                            &plus_7_0_ebx_features,
                            &plus_apm_edx_features);
        } else if (featurestr[0] == '-') {
            add_flagname_to_bitmaps(featurestr + 1, &minus_features,
                            &minus_ext_features, &minus_ext2_features,
                            &minus_ext3_features, &minus_kvm_features,
                            &minus_7_0_ebx_features,
                            &minus_apm_edx_features);
        } else if ((val = strchr(featurestr, '='))) {
            *val = 0; val++;
            if (!strcmp(featurestr, "family")) {
                char *err;
                numvalue = strtoul(val, &err, 0);
                if (!*val || *err) {
                    fprintf(stderr, "bad numerical value %s\n", val);
                    goto error;
                }
                x86_cpu_def->family = numvalue;
            } else if (!strcmp(featurestr, "model")) {
                char *err;
                numvalue = strtoul(val, &err, 0);
                if (!*val || *err || numvalue > 0xff) {
                    fprintf(stderr, "bad numerical value %s\n", val);
                    goto error;
                }
                x86_cpu_def->model = numvalue;
            } else if (!strcmp(featurestr, "stepping")) {
                char *err;
                numvalue = strtoul(val, &err, 0);
                if (!*val || *err || numvalue > 0xf) {
                    fprintf(stderr, "bad numerical value %s\n", val);
                    goto error;
                }
                x86_cpu_def->stepping = numvalue ;
            } else if (!strcmp(featurestr, "level")) {
                char *err;
                numvalue = strtoul(val, &err, 0);
                if (!*val || *err) {
                    fprintf(stderr, "bad numerical value %s\n", val);
                    goto error;
                }
                x86_cpu_def->level = numvalue;
            } else if (!strcmp(featurestr, "xlevel")) {
                char *err;
                numvalue = strtoul(val, &err, 0);
                if (!*val || *err) {
                    fprintf(stderr, "bad numerical value %s\n", val);
                    goto error;
                }
                if (numvalue < 0x80000000) {
			numvalue += 0x80000000;
                }
                x86_cpu_def->xlevel = numvalue;
            } else if (!strcmp(featurestr, "vendor")) {
                if (strlen(val) != 12) {
                    fprintf(stderr, "vendor string must be 12 chars long\n");
                    goto error;
                }
                x86_cpu_def->vendor1 = 0;
                x86_cpu_def->vendor2 = 0;
                x86_cpu_def->vendor3 = 0;
                for(i = 0; i < 4; i++) {
                    x86_cpu_def->vendor1 |= ((uint8_t)val[i    ]) << (8 * i);
                    x86_cpu_def->vendor2 |= ((uint8_t)val[i + 4]) << (8 * i);
                    x86_cpu_def->vendor3 |= ((uint8_t)val[i + 8]) << (8 * i);
                }
                x86_cpu_def->vendor_override = 1;
            } else if (!strcmp(featurestr, "model_id")) {
                pstrcpy(x86_cpu_def->model_id, sizeof(x86_cpu_def->model_id),
                        val);
            } else {
                fprintf(stderr, "unrecognized feature %s\n", featurestr);
                goto error;
            }
        } else if (!strcmp(featurestr, "check")) {
            check_cpuid = 1;
        } else if (!strcmp(featurestr, "enforce")) {
            check_cpuid = enforce_cpuid = 1;
        } else if (!strcmp(featurestr, "hv_relaxed")) {
                hyperv_enable_relaxed_timing(true);
        } else {
            fprintf(stderr, "feature string `%s' not in format (+feature|-feature|feature=xyz)\n", featurestr);
            goto error;
        }
        featurestr = strtok(NULL, ",");
    }
    x86_cpu_def->features |= plus_features;
    x86_cpu_def->ext_features |= plus_ext_features;
    x86_cpu_def->ext2_features |= plus_ext2_features;
    x86_cpu_def->ext3_features |= plus_ext3_features;
    x86_cpu_def->kvm_features |= plus_kvm_features;
    x86_cpu_def->cpuid_7_0_ebx_features |= plus_7_0_ebx_features;
    x86_cpu_def->apm_edx_features |= plus_apm_edx_features;
    x86_cpu_def->features &= ~minus_features;
    x86_cpu_def->ext_features &= ~minus_ext_features;
    x86_cpu_def->ext2_features &= ~minus_ext2_features;
    x86_cpu_def->ext3_features &= ~minus_ext3_features;
    x86_cpu_def->kvm_features &= ~minus_kvm_features;
    x86_cpu_def->cpuid_7_0_ebx_features &= ~minus_7_0_ebx_features;
    x86_cpu_def->apm_edx_features &= ~minus_apm_edx_features;
    if (x86_cpu_def->cpuid_7_0_ebx_features && x86_cpu_def->level < 7) {
        x86_cpu_def->level = 7;
    }
    g_free(s);
    return 0;

error:
    g_free(s);
    return -1;
}

/* generate a composite string into buf of all cpuid names in featureset
 * selected by fbits.  indicate truncation at bufsize in the event of overflow.
 * if flags, suppress names undefined in featureset.
 */
static void listflags(char *buf, int bufsize, uint32_t fbits,
    const char **featureset, uint32_t flags)
{
    const char **p = &featureset[31];
    char *q, *b, bit;
    int nc;

    b = 4 <= bufsize ? buf + (bufsize -= 3) - 1 : NULL;
    *buf = '\0';
    for (q = buf, bit = 31; fbits && bufsize; --p, fbits &= ~(1 << bit), --bit)
        if (fbits & 1 << bit && (*p || !flags)) {
            if (*p)
                nc = snprintf(q, bufsize, "%s%s", q == buf ? "" : " ", *p);
            else
                nc = snprintf(q, bufsize, "%s[%d]", q == buf ? "" : " ", bit);
            if (bufsize <= nc) {
                if (b)
                    sprintf(b, "...");
                return;
            }
            q += nc;
            bufsize -= nc;
        }
}

/* generate CPU information */
void x86_cpu_list (FILE *f, int (*cpu_fprintf)(FILE *f, const char *fmt, ...),
                  const char *optarg)
{
    x86_def_t *def;
    char buf[256];

    for (def = x86_defs; def; def = def->next) {
        snprintf(buf, sizeof(buf), "%s", def->name);
        (*cpu_fprintf)(f, "x86 %16s  %-48s\n", buf, def->model_id);
    }
    if (kvm_enabled()) {
        (*cpu_fprintf)(f, "x86 %16s\n", "[host]");
    }
    (*cpu_fprintf)(f, "\nRecognized CPUID flags:\n");
    listflags(buf, sizeof(buf), (uint32_t)~0, feature_name, 1);
    (*cpu_fprintf)(f, "  f_edx: %s\n", buf);
    listflags(buf, sizeof(buf), (uint32_t)~0, ext_feature_name, 1);
    (*cpu_fprintf)(f, "  f_ecx: %s\n", buf);
    listflags(buf, sizeof(buf), (uint32_t)~0, ext2_feature_name, 1);
    (*cpu_fprintf)(f, "  extf_edx: %s\n", buf);
    listflags(buf, sizeof(buf), (uint32_t)~0, ext3_feature_name, 1);
    (*cpu_fprintf)(f, "  extf_ecx: %s\n", buf);
}

int cpu_x86_register (CPUX86State *env, const char *cpu_model)
{
    x86_def_t def1, *def = &def1;

    if (cpu_x86_find_by_name(def, cpu_model) < 0)
        return -1;
    if (def->vendor1) {
        env->cpuid_vendor1 = def->vendor1;
        env->cpuid_vendor2 = def->vendor2;
        env->cpuid_vendor3 = def->vendor3;
    } else {
        env->cpuid_vendor1 = CPUID_VENDOR_INTEL_1;
        env->cpuid_vendor2 = CPUID_VENDOR_INTEL_2;
        env->cpuid_vendor3 = CPUID_VENDOR_INTEL_3;
    }
    env->cpuid_vendor_override = def->vendor_override;
    env->cpuid_level = def->level;
    if (def->family > 0x0f)
        env->cpuid_version = 0xf00 | ((def->family - 0x0f) << 20);
    else
        env->cpuid_version = def->family << 8;
    env->cpuid_version |= ((def->model & 0xf) << 4) | ((def->model >> 4) << 16);
    env->cpuid_version |= def->stepping;
    env->cpuid_features = def->features;
    env->xstate_bv = XSTATE_FP | XSTATE_SSE;
    env->pat = 0x0007040600070406ULL;
    env->cpuid_ext_features = def->ext_features;
    env->cpuid_ext2_features = def->ext2_features;
    env->cpuid_xlevel = def->xlevel;
    env->cpuid_ext3_features = def->ext3_features;
    env->cpuid_7_0_ebx_features = def->cpuid_7_0_ebx_features;
    env->cpuid_kvm_features = def->kvm_features;
    env->cpuid_apm_edx_features = def->apm_edx_features;
    env->cpuid_pmu_passthrough = def->pmu_passthrough;
    {
        const char *model_id = def->model_id;
        int c, len, i;
        if (!model_id)
            model_id = "";
        len = strlen(model_id);
        for(i = 0; i < 48; i++) {
            if (i >= len)
                c = '\0';
            else
                c = (uint8_t)model_id[i];
            env->cpuid_model[i >> 2] |= c << (8 * (i & 3));
        }
    }
    if (kvm_enabled() && check_cpuid) {
        if (kvm_check_features_against_host(env, def) && enforce_cpuid)
            return -1;
    }
    return 0;
}

/* Initialize list of CPU models, filling some non-static fields if necessary
 */
void x86_cpudef_setup(void)
{
    int i;

    for (i = 0; i < ARRAY_SIZE(builtin_x86_defs); ++i) {
        x86_def_t *def = &builtin_x86_defs[i];
        def->next = x86_defs;
        x86_defs = def;
    }
}

static void host_cpuid(uint32_t function, uint32_t count,
                       uint32_t *eax, uint32_t *ebx,
                       uint32_t *ecx, uint32_t *edx)
{
#if defined(CONFIG_KVM) || defined(USE_KVM)
    uint32_t vec[4];

#ifdef __x86_64__
    asm volatile("cpuid"
                 : "=a"(vec[0]), "=b"(vec[1]),
                   "=c"(vec[2]), "=d"(vec[3])
                 : "0"(function), "c"(count) : "cc");
#else
    asm volatile("pusha \n\t"
                 "cpuid \n\t"
                 "mov %%eax, 0(%2) \n\t"
                 "mov %%ebx, 4(%2) \n\t"
                 "mov %%ecx, 8(%2) \n\t"
                 "mov %%edx, 12(%2) \n\t"
                 "popa"
                 : : "a"(function), "c"(count), "S"(vec)
                 : "memory", "cc");
#endif

    if (eax)
	*eax = vec[0];
    if (ebx)
	*ebx = vec[1];
    if (ecx)
	*ecx = vec[2];
    if (edx)
	*edx = vec[3];
#endif
}

static void get_cpuid_vendor(CPUX86State *env, uint32_t *ebx,
                             uint32_t *ecx, uint32_t *edx)
{
    *ebx = env->cpuid_vendor1;
    *edx = env->cpuid_vendor2;
    *ecx = env->cpuid_vendor3;

    /* sysenter isn't supported on compatibility mode on AMD, syscall
     * isn't supported in compatibility mode on Intel.
     * Normally we advertise the actual cpu vendor, but you can override
     * this if you want to use KVM's sysenter/syscall emulation
     * in compatibility mode and when doing cross vendor migration
     */
    if (kvm_enabled() && !env->cpuid_vendor_override) {
        host_cpuid(0, 0, NULL, ebx, ecx, edx);
    }
}

void cpu_x86_cpuid(CPUX86State *env, uint32_t index, uint32_t count,
                   uint32_t *eax, uint32_t *ebx,
                   uint32_t *ecx, uint32_t *edx)
{
    /* test if maximum index reached */
    if (index & 0x80000000) {
        if (index > env->cpuid_xlevel)
            index = env->cpuid_level;
    } else {
        if (index > env->cpuid_level)
            index = env->cpuid_level;
    }

    switch(index) {
    case 0:
        *eax = env->cpuid_level;
        get_cpuid_vendor(env, ebx, ecx, edx);
        break;
    case 1:
        *eax = env->cpuid_version;
        *ebx = (env->cpuid_apic_id << 24) | 8 << 8; /* CLFLUSH size in quad words, Linux wants it. */
        *ecx = env->cpuid_ext_features;
        *edx = env->cpuid_features;
        if (env->nr_cores * env->nr_threads > 1) {
            *ebx |= (env->nr_cores * env->nr_threads) << 16;
            *edx |= 1 << 28;    /* HTT bit */
        }
        break;
    case 2:
        /* cache info: needed for Pentium Pro compatibility */
        *eax = 1;
        *ebx = 0;
        *ecx = 0;
        *edx = 0x2c307d;
        break;
    case 4:
        /* cache info: needed for Core compatibility */
        if (env->nr_cores > 1) {
		*eax = (env->nr_cores - 1) << 26;
        } else {
		*eax = 0;
        }
        switch (count) {
            case 0: /* L1 dcache info */
                *eax |= 0x0000121;
                *ebx = 0x1c0003f;
                *ecx = 0x000003f;
                *edx = 0x0000001;
                break;
            case 1: /* L1 icache info */
                *eax |= 0x0000122;
                *ebx = 0x1c0003f;
                *ecx = 0x000003f;
                *edx = 0x0000001;
                break;
            case 2: /* L2 cache info */
                *eax |= 0x0000143;
                if (env->nr_threads > 1) {
                    *eax |= (env->nr_threads - 1) << 14;
                }
                *ebx = 0x3c0003f;
                *ecx = 0x0000fff;
                *edx = 0x0000001;
                break;
            default: /* end of info */
                *eax = 0;
                *ebx = 0;
                *ecx = 0;
                *edx = 0;
                break;
        }
        break;
    case 5:
        /* mwait info: needed for Core compatibility */
        *eax = 0; /* Smallest monitor-line size in bytes */
        *ebx = 0; /* Largest monitor-line size in bytes */
        *ecx = CPUID_MWAIT_EMX | CPUID_MWAIT_IBE;
        *edx = 0;
        break;
    case 6:
        /* Thermal and Power Leaf */
        *eax = 0;
        *ebx = 0;
        *ecx = 0;
        *edx = 0;
        break;
   case 7:
        /* Structured Extended Feature Flags Enumeration Leaf */
        if (count == 0) {
            *eax = 0; /* Maximum ECX value for sub-leaves */
            *ebx = env->cpuid_7_0_ebx_features; /* Feature flags */
            *ecx = 0; /* Reserved */
            *edx = 0; /* Reserved */
       } else {
           *eax = 0;
           *ebx = 0;
           *ecx = 0;
           *edx = 0;
       }
       break;
    case 9:
        /* Direct Cache Access Information Leaf */
        *eax = 0; /* Bits 0-31 in DCA_CAP MSR */
        *ebx = 0;
        *ecx = 0;
        *edx = 0;
        break;
    case 0xA:
        /* Architectural Performance Monitoring Leaf */
        if (kvm_enabled() && env->cpuid_pmu_passthrough) {
            KVMState *s = env->kvm_state;
            *eax = kvm_arch_get_supported_cpuid(s, 0xA, count, R_EAX);
            *ebx = kvm_arch_get_supported_cpuid(s, 0xA, count, R_EBX);
            *ecx = kvm_arch_get_supported_cpuid(s, 0xA, count, R_ECX);
            *edx = kvm_arch_get_supported_cpuid(s, 0xA, count, R_EDX);
        } else {
            *eax = 0;
            *ebx = 0;
            *ecx = 0;
            *edx = 0;
        }
        break;
    case 0xD: {
        KVMState *s = env->kvm_state;
        uint64_t kvm_mask;
        int i;

        /* Processor Extended State */
        *eax = 0;
        *ebx = 0;
        *ecx = 0;
        *edx = 0;
        if (!(env->cpuid_ext_features & CPUID_EXT_XSAVE) || !kvm_enabled()) {
            break;
        }
        kvm_mask =
            kvm_arch_get_supported_cpuid(s, 0xd, 0, R_EAX) |
            ((uint64_t)kvm_arch_get_supported_cpuid(s, 0xd, 0, R_EDX) << 32);

        if (count == 0) {
            *ecx = 0x240;
            for (i = 2; i < ARRAY_SIZE(ext_save_areas); i++) {
                const ExtSaveArea *esa = &ext_save_areas[i];
                if (esa->enabled(env) && kvm_mask & (1 << i)) {
                    if (i < 32) {
                        *eax |= 1 << i;
                    } else {
                        *edx |= 1 << (i - 32);
                    }
                    *ecx = MAX(*ecx, esa->offset + esa->size);
                }
            }
            *eax |= kvm_mask & (XSTATE_FP | XSTATE_SSE);
            *ebx = *ecx;
        } else if (count == 1) {
            *eax = kvm_arch_get_supported_cpuid(s, 0xd, 1, R_EAX);
        } else if (count < ARRAY_SIZE(ext_save_areas)) {
            const ExtSaveArea *esa = &ext_save_areas[count];
            if (esa->enabled(env) && kvm_mask & (1 << count)) {
                *eax = esa->size;
                *ebx = esa->offset;
            }
        }
        break;
    }
    case 0x80000000:
        *eax = env->cpuid_xlevel;
        *ebx = env->cpuid_vendor1;
        *edx = env->cpuid_vendor2;
        *ecx = env->cpuid_vendor3;
        break;
    case 0x80000001:
        *eax = env->cpuid_version;
        *ebx = 0;
        *ecx = env->cpuid_ext3_features;
        *edx = env->cpuid_ext2_features;

        /* The Linux kernel checks for the CMPLegacy bit and
         * discards multiple thread information if it is set.
         * So dont set it here for Intel to make Linux guests happy.
         */
        if (env->nr_cores * env->nr_threads > 1) {
            uint32_t tebx, tecx, tedx;
            get_cpuid_vendor(env, &tebx, &tecx, &tedx);
            if (tebx != CPUID_VENDOR_INTEL_1 ||
                tedx != CPUID_VENDOR_INTEL_2 ||
                tecx != CPUID_VENDOR_INTEL_3) {
                *ecx |= 1 << 1;    /* CmpLegacy bit */
            }
        }

        if (kvm_enabled()) {
            uint32_t h_eax, h_edx;

            host_cpuid(index, 0, &h_eax, NULL, NULL, &h_edx);

            /* disable CPU features that the host does not support */

            /* long mode */
            if ((h_edx & 0x20000000) == 0 /* || !lm_capable_kernel */)
                *edx &= ~0x20000000;
            /* syscall */
            if ((h_edx & 0x00000800) == 0)
                *edx &= ~0x00000800;
            /* nx */
            if ((h_edx & 0x00100000) == 0)
                *edx &= ~0x00100000;

            /* disable CPU features that KVM cannot support */

            /* svm */
            if (!kvm_nested)
                *ecx &= ~CPUID_EXT3_SVM;
            /* 3dnow */
            *edx &= ~0xc0000000;
        } else {
            /* AMD 3DNow! is not supported in QEMU */
            *edx &= ~(CPUID_EXT2_3DNOW | CPUID_EXT2_3DNOWEXT);
        }
        break;
    case 0x80000002:
    case 0x80000003:
    case 0x80000004:
        *eax = env->cpuid_model[(index - 0x80000002) * 4 + 0];
        *ebx = env->cpuid_model[(index - 0x80000002) * 4 + 1];
        *ecx = env->cpuid_model[(index - 0x80000002) * 4 + 2];
        *edx = env->cpuid_model[(index - 0x80000002) * 4 + 3];
        break;
    case 0x80000005:
        /* cache info (L1 cache) */
        *eax = 0x01ff01ff;
        *ebx = 0x01ff01ff;
        *ecx = 0x40020140;
        *edx = 0x40020140;
        break;
    case 0x80000006:
        /* cache info (L2 cache) */
        *eax = 0;
        *ebx = 0x42004200;
        *ecx = 0x02008140;
        *edx = 0;
        break;
    case 0x80000007:
        *eax = 0;
        *ebx = 0;
        *ecx = 0;
        *edx = env->cpuid_apm_edx_features;
        break;
    case 0x80000008:
        /* virtual & phys address size in low 2 bytes. */
/* XXX: This value must match the one used in the MMU code. */
        if (env->cpuid_ext2_features & CPUID_EXT2_LM) {
            /* 64 bit processor */
/* XXX: The physical address space is limited to 42 bits in exec.c. */
            *eax = 0x00003028;	/* 48 bits virtual, 40 bits physical */
            if (kvm_enabled()) {
                uint32_t _eax;
                host_cpuid(0x80000000, 0, &_eax, NULL, NULL, NULL);
                if (_eax >= 0x80000008)
                    host_cpuid(0x80000008, 0, eax, NULL, NULL, NULL);
            }
        } else {
            if (env->cpuid_features & CPUID_PSE36)
                *eax = 0x00000024; /* 36 bits physical */
            else
                *eax = 0x00000020; /* 32 bits physical */
        }
        *ebx = 0;
        *ecx = 0;
        *edx = 0;
        if (env->nr_cores * env->nr_threads > 1) {
            *ecx |= (env->nr_cores * env->nr_threads) - 1;
        }
        break;
    case 0x8000000A:
        *eax = 0x00000001; /* SVM Revision */
        *ebx = 0x00000010; /* nr of ASIDs */
        *ecx = 0;
        *edx = 0; /* optional features */
        break;
    default:
        /* reserved values: zero */
        *eax = 0;
        *ebx = 0;
        *ecx = 0;
        *edx = 0;
        break;
    }
}

/* machine-type compatibility hacks below: */

/* Called from hw/pc.c but there is no header
 * both files include to put this into.
 * Put it here to silence compiler warning.
 */
void set_pmu_passthrough(bool enable);
void disable_kvm_pv_eoi(void);
void disable_tsc_deadline(void);
void disable_kvm_sep(void);

void set_cpu_model_level(const char *name, int level);

void set_pmu_passthrough(bool enable)
{
	pmu_passthrough_enabled = enable;
}

void disable_kvm_pv_eoi(void)
{
	kvm_pv_eoi_disabled = true;
}

void disable_tsc_deadline(void)
{
    tsc_deadline_disabled = true;
}

void disable_kvm_sep(void)
{
	kvm_sep_disabled = true;
}

void set_cpu_model_level(const char *name, int level)
{
    x86_def_t *def;
    for (def = x86_defs; def; def = def->next) {
        if (!strcmp(name, def->name)) {
            def->level = level;
        }
    }
}
