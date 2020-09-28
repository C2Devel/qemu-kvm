/*
 * QEMU PC System Emulator
 *
 * Copyright (c) 2003-2004 Fabrice Bellard
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include "qemu/osdep.h"

#include "hw/hw.h"
#include "hw/loader.h"
#include "hw/i386/pc.h"
#include "hw/i386/apic.h"
#include "hw/smbios/smbios.h"
#include "hw/pci/pci.h"
#include "hw/pci/pci_ids.h"
#include "hw/usb.h"
#include "net/net.h"
#include "hw/boards.h"
#include "hw/ide.h"
#include "sysemu/kvm.h"
#include "hw/kvm/clock.h"
#include "sysemu/sysemu.h"
#include "hw/sysbus.h"
#include "sysemu/arch_init.h"
#include "hw/i2c/smbus.h"
#include "hw/xen/xen.h"
#include "exec/memory.h"
#include "exec/address-spaces.h"
#include "hw/acpi/acpi.h"
#include "cpu.h"
#include "qapi/error.h"
#include "qemu/error-report.h"
#include "migration/migration.h"
#ifdef CONFIG_XEN
#include <xen/hvm/hvm_info_table.h>
#include "hw/xen/xen_pt.h"
#endif
#include "migration/global_state.h"
#include "migration/misc.h"
#include "kvm_i386.h"
#include "sysemu/numa.h"

#define MAX_IDE_BUS 2

static const int ide_iobase[MAX_IDE_BUS] = { 0x1f0, 0x170 };
static const int ide_iobase2[MAX_IDE_BUS] = { 0x3f6, 0x376 };
static const int ide_irq[MAX_IDE_BUS] = { 14, 15 };

/* PC hardware initialisation */
static void pc_init1(MachineState *machine,
                     const char *host_type, const char *pci_type)
{
    PCMachineState *pcms = PC_MACHINE(machine);
    PCMachineClass *pcmc = PC_MACHINE_GET_CLASS(pcms);
    MemoryRegion *system_memory = get_system_memory();
    MemoryRegion *system_io = get_system_io();
    int i;
    PCIBus *pci_bus;
    ISABus *isa_bus;
    PCII440FXState *i440fx_state;
    int piix3_devfn = -1;
    qemu_irq *i8259;
    qemu_irq smi_irq;
    GSIState *gsi_state;
    DriveInfo *hd[MAX_IDE_BUS * MAX_IDE_DEVS];
    BusState *idebus[MAX_IDE_BUS];
    ISADevice *rtc_state;
    MemoryRegion *ram_memory;
    MemoryRegion *pci_memory;
    MemoryRegion *rom_memory;
    ram_addr_t lowmem;

    /*
     * Calculate ram split, for memory below and above 4G.  It's a bit
     * complicated for backward compatibility reasons ...
     *
     *  - Traditional split is 3.5G (lowmem = 0xe0000000).  This is the
     *    default value for max_ram_below_4g now.
     *
     *  - Then, to gigabyte align the memory, we move the split to 3G
     *    (lowmem = 0xc0000000).  But only in case we have to split in
     *    the first place, i.e. ram_size is larger than (traditional)
     *    lowmem.  And for new machine types (gigabyte_align = true)
     *    only, for live migration compatibility reasons.
     *
     *  - Next the max-ram-below-4g option was added, which allowed to
     *    reduce lowmem to a smaller value, to allow a larger PCI I/O
     *    window below 4G.  qemu doesn't enforce gigabyte alignment here,
     *    but prints a warning.
     *
     *  - Finally max-ram-below-4g got updated to also allow raising lowmem,
     *    so legacy non-PAE guests can get as much memory as possible in
     *    the 32bit address space below 4G.
     *
     *  - Note that Xen has its own ram setp code in xen_ram_init(),
     *    called via xen_hvm_init().
     *
     * Examples:
     *    qemu -M pc-1.7 -m 4G    (old default)    -> 3584M low,  512M high
     *    qemu -M pc -m 4G        (new default)    -> 3072M low, 1024M high
     *    qemu -M pc,max-ram-below-4g=2G -m 4G     -> 2048M low, 2048M high
     *    qemu -M pc,max-ram-below-4g=4G -m 3968M  -> 3968M low (=4G-128M)
     */
    if (xen_enabled()) {
        xen_hvm_init(pcms, &ram_memory);
    } else {
        if (!pcms->max_ram_below_4g) {
            pcms->max_ram_below_4g = 0xe0000000; /* default: 3.5G */
        }
        lowmem = pcms->max_ram_below_4g;
        if (machine->ram_size >= pcms->max_ram_below_4g) {
            if (pcmc->gigabyte_align) {
                if (lowmem > 0xc0000000) {
                    lowmem = 0xc0000000;
                }
                if (lowmem & ((1ULL << 30) - 1)) {
                    warn_report("Large machine and max_ram_below_4g "
                                "(%" PRIu64 ") not a multiple of 1G; "
                                "possible bad performance.",
                                pcms->max_ram_below_4g);
                }
            }
        }

        if (machine->ram_size >= lowmem) {
            pcms->above_4g_mem_size = machine->ram_size - lowmem;
            pcms->below_4g_mem_size = lowmem;
        } else {
            pcms->above_4g_mem_size = 0;
            pcms->below_4g_mem_size = machine->ram_size;
        }
    }

    pc_cpus_init(pcms);

    if (kvm_enabled() && pcmc->kvmclock_enabled) {
        kvmclock_create();
    }

    if (pcmc->pci_enabled) {
        pci_memory = g_new(MemoryRegion, 1);
        memory_region_init(pci_memory, NULL, "pci", UINT64_MAX);
        rom_memory = pci_memory;
    } else {
        pci_memory = NULL;
        rom_memory = system_memory;
    }

    pc_guest_info_init(pcms);

    if (pcmc->smbios_defaults) {
        MachineClass *mc = MACHINE_GET_CLASS(machine);
        /* These values are guest ABI, do not change */
        smbios_set_defaults("Red Hat", "KVM",
                            mc->desc, pcmc->smbios_legacy_mode,
                            pcmc->smbios_uuid_encoded,
                            SMBIOS_ENTRY_POINT_21);
    }

    /* allocate ram and load rom/bios */
    if (!xen_enabled()) {
        pc_memory_init(pcms, system_memory,
                       rom_memory, &ram_memory);
    } else if (machine->kernel_filename != NULL) {
        /* For xen HVM direct kernel boot, load linux here */
        xen_load_linux(pcms);
    }

    gsi_state = g_malloc0(sizeof(*gsi_state));
    if (kvm_ioapic_in_kernel()) {
        kvm_pc_setup_irq_routing(pcmc->pci_enabled);
        pcms->gsi = qemu_allocate_irqs(kvm_pc_gsi_handler, gsi_state,
                                       GSI_NUM_PINS);
    } else {
        pcms->gsi = qemu_allocate_irqs(gsi_handler, gsi_state, GSI_NUM_PINS);
    }

    if (pcmc->pci_enabled) {
        pci_bus = i440fx_init(host_type,
                              pci_type,
                              &i440fx_state, &piix3_devfn, &isa_bus, pcms->gsi,
                              system_memory, system_io, machine->ram_size,
                              pcms->below_4g_mem_size,
                              pcms->above_4g_mem_size,
                              pci_memory, ram_memory);
        pcms->bus = pci_bus;
    } else {
        pci_bus = NULL;
        i440fx_state = NULL;
        isa_bus = isa_bus_new(NULL, get_system_memory(), system_io,
                              &error_abort);
        no_hpet = 1;
    }
    isa_bus_irqs(isa_bus, pcms->gsi);

    if (kvm_pic_in_kernel()) {
        i8259 = kvm_i8259_init(isa_bus);
    } else if (xen_enabled()) {
        i8259 = xen_interrupt_controller_init();
    } else {
        i8259 = i8259_init(isa_bus, pc_allocate_cpu_irq());
    }

    for (i = 0; i < ISA_NUM_IRQS; i++) {
        gsi_state->i8259_irq[i] = i8259[i];
    }
    g_free(i8259);
    if (pcmc->pci_enabled) {
        ioapic_init_gsi(gsi_state, "i440fx");
    }

    pc_register_ferr_irq(pcms->gsi[13]);

    pc_vga_init(isa_bus, pcmc->pci_enabled ? pci_bus : NULL);

    assert(pcms->vmport != ON_OFF_AUTO__MAX);
    if (pcms->vmport == ON_OFF_AUTO_AUTO) {
        pcms->vmport = xen_enabled() ? ON_OFF_AUTO_OFF : ON_OFF_AUTO_ON;
    }

    /* init basic PC hardware */
    pc_basic_device_init(isa_bus, pcms->gsi, &rtc_state, true,
                         (pcms->vmport != ON_OFF_AUTO_ON), pcms->pit, 0x4);

    pc_nic_init(pcmc, isa_bus, pci_bus);

    ide_drive_get(hd, ARRAY_SIZE(hd));
    if (pcmc->pci_enabled) {
        PCIDevice *dev;
        if (xen_enabled()) {
            dev = pci_piix3_xen_ide_init(pci_bus, hd, piix3_devfn + 1);
        } else {
            dev = pci_piix3_ide_init(pci_bus, hd, piix3_devfn + 1);
        }
        idebus[0] = qdev_get_child_bus(&dev->qdev, "ide.0");
        idebus[1] = qdev_get_child_bus(&dev->qdev, "ide.1");
    } else {
        for(i = 0; i < MAX_IDE_BUS; i++) {
            ISADevice *dev;
            char busname[] = "ide.0";
            dev = isa_ide_init(isa_bus, ide_iobase[i], ide_iobase2[i],
                               ide_irq[i],
                               hd[MAX_IDE_DEVS * i], hd[MAX_IDE_DEVS * i + 1]);
            /*
             * The ide bus name is ide.0 for the first bus and ide.1 for the
             * second one.
             */
            busname[4] = '0' + i;
            idebus[i] = qdev_get_child_bus(DEVICE(dev), busname);
        }
    }

    pc_cmos_init(pcms, idebus[0], idebus[1], rtc_state);

    if (pcmc->pci_enabled && machine_usb(machine)) {
        pci_create_simple(pci_bus, piix3_devfn + 2, "piix3-usb-uhci");
    }

    if (pcmc->pci_enabled && acpi_enabled) {
        DeviceState *piix4_pm;
        I2CBus *smbus;

        smi_irq = qemu_allocate_irq(pc_acpi_smi_interrupt, first_cpu, 0);
        /* TODO: Populate SPD eeprom data.  */
        smbus = piix4_pm_init(pci_bus, piix3_devfn + 3, 0xb100,
                              pcms->gsi[9], smi_irq,
                              pc_machine_is_smm_enabled(pcms),
                              &piix4_pm);
        smbus_eeprom_init(smbus, 8, NULL, 0);

        object_property_add_link(OBJECT(machine), PC_MACHINE_ACPI_DEVICE_PROP,
                                 TYPE_HOTPLUG_HANDLER,
                                 (Object **)&pcms->acpi_dev,
                                 object_property_allow_set_link,
                                 OBJ_PROP_LINK_STRONG, &error_abort);
        object_property_set_link(OBJECT(machine), OBJECT(piix4_pm),
                                 PC_MACHINE_ACPI_DEVICE_PROP, &error_abort);
    }

    if (pcms->acpi_nvdimm_state.is_enabled) {
        nvdimm_init_acpi_state(&pcms->acpi_nvdimm_state, system_io,
                               pcms->fw_cfg, OBJECT(pcms));
    }
}

/* Looking for a pc_compat_2_4() function? It doesn't exist.
 * pc_compat_*() functions that run on machine-init time and
 * change global QEMU state are deprecated. Please don't create
 * one, and implement any pc-*-2.4 (and newer) compat code in
 * HW_COMPAT_*, PC_COMPAT_*, or * pc_*_machine_options().
 */

#if 0 /* Disabled for Red Hat Enterprise Linux */
static void pc_compat_2_3(MachineState *machine)
{
    PCMachineState *pcms = PC_MACHINE(machine);
    if (kvm_enabled()) {
        pcms->smm = ON_OFF_AUTO_OFF;
    }
}

static void pc_compat_2_2(MachineState *machine)
{
    pc_compat_2_3(machine);
    machine->suppress_vmdesc = true;
}

static void pc_compat_2_1(MachineState *machine)
{
    pc_compat_2_2(machine);
    x86_cpu_change_kvm_default("svm", NULL);
}

static void pc_compat_2_0(MachineState *machine)
{
    pc_compat_2_1(machine);
}

static void pc_compat_1_7(MachineState *machine)
{
    pc_compat_2_0(machine);
    x86_cpu_change_kvm_default("x2apic", NULL);
}

static void pc_compat_1_6(MachineState *machine)
{
    pc_compat_1_7(machine);
}

static void pc_compat_1_5(MachineState *machine)
{
    pc_compat_1_6(machine);
}

static void pc_compat_1_4(MachineState *machine)
{
    pc_compat_1_5(machine);
}

static void pc_compat_1_3(MachineState *machine)
{
    pc_compat_1_4(machine);
    enable_compat_apic_id_mode();
}

/* PC compat function for pc-0.14 to pc-1.2 */
static void pc_compat_1_2(MachineState *machine)
{
    pc_compat_1_3(machine);
    x86_cpu_change_kvm_default("kvm-pv-eoi", NULL);
}

/* PC compat function for pc-0.10 to pc-0.13 */
static void pc_compat_0_13(MachineState *machine)
{
    pc_compat_1_2(machine);
}

static void pc_init_isa(MachineState *machine)
{
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, TYPE_I440FX_PCI_DEVICE);
}

#ifdef CONFIG_XEN
static void pc_xen_hvm_init_pci(MachineState *machine)
{
    const char *pci_type = has_igd_gfx_passthru ?
                TYPE_IGD_PASSTHROUGH_I440FX_PCI_DEVICE : TYPE_I440FX_PCI_DEVICE;

    pc_init1(machine,
             TYPE_I440FX_PCI_HOST_BRIDGE,
             pci_type);
}

static void pc_xen_hvm_init(MachineState *machine)
{
    PCMachineState *pcms = PC_MACHINE(machine);

    if (!xen_enabled()) {
        error_report("xenfv machine requires the xen accelerator");
        exit(1);
    }

    pc_xen_hvm_init_pci(machine);
    pci_create_simple(pcms->bus, -1, "xen-platform");
}
#endif

#define DEFINE_I440FX_MACHINE(suffix, name, compatfn, optionfn) \
    static void pc_init_##suffix(MachineState *machine) \
    { \
        void (*compat)(MachineState *m) = (compatfn); \
        if (compat) { \
            compat(machine); \
        } \
        pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
                 TYPE_I440FX_PCI_DEVICE); \
    } \
    DEFINE_PC_MACHINE(suffix, name, pc_init_##suffix, optionfn)

static void pc_i440fx_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pcmc->default_nic_model = "e1000";

    m->family = "pc_piix";
    m->desc = "Standard PC (i440FX + PIIX, 1996)";
    m->default_machine_opts = "firmware=bios-256k.bin";
    m->default_display = "std";
}

static void pc_i440fx_2_12_machine_options(MachineClass *m)
{
    pc_i440fx_machine_options(m);
    m->alias = "pc";
    m->is_default = 1;
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_12);
}

DEFINE_I440FX_MACHINE(v2_12, "pc-i440fx-2.12", NULL,
                      pc_i440fx_2_12_machine_options);

static void pc_i440fx_2_11_machine_options(MachineClass *m)
{
    pc_i440fx_2_12_machine_options(m);
    m->is_default = 0;
    m->alias = NULL;
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_11);
}

DEFINE_I440FX_MACHINE(v2_11, "pc-i440fx-2.11", NULL,
                      pc_i440fx_2_11_machine_options);

static void pc_i440fx_2_10_machine_options(MachineClass *m)
{
    pc_i440fx_2_11_machine_options(m);
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_10);
    m->auto_enable_numa_with_memhp = false;
}

DEFINE_I440FX_MACHINE(v2_10, "pc-i440fx-2.10", NULL,
                      pc_i440fx_2_10_machine_options);

static void pc_i440fx_2_9_machine_options(MachineClass *m)
{
    pc_i440fx_2_10_machine_options(m);
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_9);
    m->numa_auto_assign_ram = numa_legacy_auto_assign_ram;
}

DEFINE_I440FX_MACHINE(v2_9, "pc-i440fx-2.9", NULL,
                      pc_i440fx_2_9_machine_options);

static void pc_i440fx_2_8_machine_options(MachineClass *m)
{
    pc_i440fx_2_9_machine_options(m);
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_8);
}

DEFINE_I440FX_MACHINE(v2_8, "pc-i440fx-2.8", NULL,
                      pc_i440fx_2_8_machine_options);


static void pc_i440fx_2_7_machine_options(MachineClass *m)
{
    pc_i440fx_2_8_machine_options(m);
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_7);
}

DEFINE_I440FX_MACHINE(v2_7, "pc-i440fx-2.7", NULL,
                      pc_i440fx_2_7_machine_options);


static void pc_i440fx_2_6_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_7_machine_options(m);
    pcmc->legacy_cpu_hotplug = true;
    pcmc->linuxboot_dma_enabled = false;
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_6);
}

DEFINE_I440FX_MACHINE(v2_6, "pc-i440fx-2.6", NULL,
                      pc_i440fx_2_6_machine_options);


static void pc_i440fx_2_5_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_6_machine_options(m);
    pcmc->save_tsc_khz = false;
    m->legacy_fw_cfg_order = 1;
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_5);
}

DEFINE_I440FX_MACHINE(v2_5, "pc-i440fx-2.5", NULL,
                      pc_i440fx_2_5_machine_options);


static void pc_i440fx_2_4_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_5_machine_options(m);
    m->hw_version = "2.4.0";
    pcmc->broken_reserved_end = true;
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_4);
}

DEFINE_I440FX_MACHINE(v2_4, "pc-i440fx-2.4", NULL,
                      pc_i440fx_2_4_machine_options)


static void pc_i440fx_2_3_machine_options(MachineClass *m)
{
    pc_i440fx_2_4_machine_options(m);
    m->hw_version = "2.3.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_3);
}

DEFINE_I440FX_MACHINE(v2_3, "pc-i440fx-2.3", pc_compat_2_3,
                      pc_i440fx_2_3_machine_options);


static void pc_i440fx_2_2_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_3_machine_options(m);
    m->hw_version = "2.2.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_2);
    pcmc->rsdp_in_ram = false;
}

DEFINE_I440FX_MACHINE(v2_2, "pc-i440fx-2.2", pc_compat_2_2,
                      pc_i440fx_2_2_machine_options);


static void pc_i440fx_2_1_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_2_machine_options(m);
    m->hw_version = "2.1.0";
    m->default_display = NULL;
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_1);
    pcmc->smbios_uuid_encoded = false;
    pcmc->enforce_aligned_dimm = false;
}

DEFINE_I440FX_MACHINE(v2_1, "pc-i440fx-2.1", pc_compat_2_1,
                      pc_i440fx_2_1_machine_options);



static void pc_i440fx_2_0_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_1_machine_options(m);
    m->hw_version = "2.0.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_2_0);
    pcmc->smbios_legacy_mode = true;
    pcmc->has_reserved_memory = false;
    /* This value depends on the actual DSDT and SSDT compiled into
     * the source QEMU; unfortunately it depends on the binary and
     * not on the machine type, so we cannot make pc-i440fx-1.7 work on
     * both QEMU 1.7 and QEMU 2.0.
     *
     * Large variations cause migration to fail for more than one
     * consecutive value of the "-smp" maxcpus option.
     *
     * For small variations of the kind caused by different iasl versions,
     * the 4k rounding usually leaves slack.  However, there could be still
     * one or two values that break.  For QEMU 1.7 and QEMU 2.0 the
     * slack is only ~10 bytes before one "-smp maxcpus" value breaks!
     *
     * 6652 is valid for QEMU 2.0, the right value for pc-i440fx-1.7 on
     * QEMU 1.7 it is 6414.  For RHEL/CentOS 7.0 it is 6418.
     */
    pcmc->legacy_acpi_table_size = 6652;
    pcmc->acpi_data_size = 0x10000;
}

DEFINE_I440FX_MACHINE(v2_0, "pc-i440fx-2.0", pc_compat_2_0,
                      pc_i440fx_2_0_machine_options);


static void pc_i440fx_1_7_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_2_0_machine_options(m);
    m->hw_version = "1.7.0";
    m->default_machine_opts = NULL;
    m->option_rom_has_mr = true;
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_7);
    pcmc->smbios_defaults = false;
    pcmc->gigabyte_align = false;
    pcmc->legacy_acpi_table_size = 6414;
}

DEFINE_I440FX_MACHINE(v1_7, "pc-i440fx-1.7", pc_compat_1_7,
                      pc_i440fx_1_7_machine_options);


static void pc_i440fx_1_6_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_1_7_machine_options(m);
    m->hw_version = "1.6.0";
    m->rom_file_has_mr = false;
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_6);
    pcmc->has_acpi_build = false;
}

DEFINE_I440FX_MACHINE(v1_6, "pc-i440fx-1.6", pc_compat_1_6,
                      pc_i440fx_1_6_machine_options);


static void pc_i440fx_1_5_machine_options(MachineClass *m)
{
    pc_i440fx_1_6_machine_options(m);
    m->hw_version = "1.5.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_5);
}

DEFINE_I440FX_MACHINE(v1_5, "pc-i440fx-1.5", pc_compat_1_5,
                      pc_i440fx_1_5_machine_options);


static void pc_i440fx_1_4_machine_options(MachineClass *m)
{
    pc_i440fx_1_5_machine_options(m);
    m->hw_version = "1.4.0";
    m->hot_add_cpu = NULL;
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_4);
}

DEFINE_I440FX_MACHINE(v1_4, "pc-i440fx-1.4", pc_compat_1_4,
                      pc_i440fx_1_4_machine_options);


#define PC_COMPAT_1_3 \
        PC_CPU_MODEL_IDS("1.3.0") \
        {\
            .driver   = "usb-tablet",\
            .property = "usb_version",\
            .value    = stringify(1),\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "ctrl_mac_addr",\
            .value    = "off",      \
        },{ \
            .driver   = "virtio-net-pci", \
            .property = "mq", \
            .value    = "off", \
        }, {\
            .driver   = "e1000",\
            .property = "autonegotiation",\
            .value    = "off",\
        },


static void pc_i440fx_1_3_machine_options(MachineClass *m)
{
    pc_i440fx_1_4_machine_options(m);
    m->hw_version = "1.3.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_3);
}

DEFINE_I440FX_MACHINE(v1_3, "pc-1.3", pc_compat_1_3,
                      pc_i440fx_1_3_machine_options);


#define PC_COMPAT_1_2 \
        PC_CPU_MODEL_IDS("1.2.0") \
        {\
            .driver   = "nec-usb-xhci",\
            .property = "msi",\
            .value    = "off",\
        },{\
            .driver   = "nec-usb-xhci",\
            .property = "msix",\
            .value    = "off",\
        },{\
            .driver   = "ivshmem",\
            .property = "use64",\
            .value    = "0",\
        },{\
            .driver   = "qxl",\
            .property = "revision",\
            .value    = stringify(3),\
        },{\
            .driver   = "qxl-vga",\
            .property = "revision",\
            .value    = stringify(3),\
        },{\
            .driver   = "VGA",\
            .property = "mmio",\
            .value    = "off",\
        },

static void pc_i440fx_1_2_machine_options(MachineClass *m)
{
    pc_i440fx_1_3_machine_options(m);
    m->hw_version = "1.2.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_2);
}

DEFINE_I440FX_MACHINE(v1_2, "pc-1.2", pc_compat_1_2,
                      pc_i440fx_1_2_machine_options);


#define PC_COMPAT_1_1 \
        PC_CPU_MODEL_IDS("1.1.0") \
        {\
            .driver   = "virtio-scsi-pci",\
            .property = "hotplug",\
            .value    = "off",\
        },{\
            .driver   = "virtio-scsi-pci",\
            .property = "param_change",\
            .value    = "off",\
        },{\
            .driver   = "VGA",\
            .property = "vgamem_mb",\
            .value    = stringify(8),\
        },{\
            .driver   = "vmware-svga",\
            .property = "vgamem_mb",\
            .value    = stringify(8),\
        },{\
            .driver   = "qxl-vga",\
            .property = "vgamem_mb",\
            .value    = stringify(8),\
        },{\
            .driver   = "qxl",\
            .property = "vgamem_mb",\
            .value    = stringify(8),\
        },{\
            .driver   = "virtio-blk-pci",\
            .property = "config-wce",\
            .value    = "off",\
        },

static void pc_i440fx_1_1_machine_options(MachineClass *m)
{
    pc_i440fx_1_2_machine_options(m);
    m->hw_version = "1.1.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_1);
}

DEFINE_I440FX_MACHINE(v1_1, "pc-1.1", pc_compat_1_2,
                      pc_i440fx_1_1_machine_options);


#define PC_COMPAT_1_0 \
        PC_CPU_MODEL_IDS("1.0") \
        {\
            .driver   = TYPE_ISA_FDC,\
            .property = "check_media_rate",\
            .value    = "off",\
        }, {\
            .driver   = "virtio-balloon-pci",\
            .property = "class",\
            .value    = stringify(PCI_CLASS_MEMORY_RAM),\
        },{\
            .driver   = "apic-common",\
            .property = "vapic",\
            .value    = "off",\
        },{\
            .driver   = TYPE_USB_DEVICE,\
            .property = "full-path",\
            .value    = "no",\
        },

static void pc_i440fx_1_0_machine_options(MachineClass *m)
{
    pc_i440fx_1_1_machine_options(m);
    m->hw_version = "1.0";
    SET_MACHINE_COMPAT(m, PC_COMPAT_1_0);
}

DEFINE_I440FX_MACHINE(v1_0, "pc-1.0", pc_compat_1_2,
                      pc_i440fx_1_0_machine_options);


#define PC_COMPAT_0_15 \
        PC_CPU_MODEL_IDS("0.15")

static void pc_i440fx_0_15_machine_options(MachineClass *m)
{
    pc_i440fx_1_0_machine_options(m);
    m->hw_version = "0.15";
    SET_MACHINE_COMPAT(m, PC_COMPAT_0_15);
}

DEFINE_I440FX_MACHINE(v0_15, "pc-0.15", pc_compat_1_2,
                      pc_i440fx_0_15_machine_options);


#define PC_COMPAT_0_14 \
        PC_CPU_MODEL_IDS("0.14") \
        {\
            .driver   = "virtio-blk-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "virtio-serial-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "virtio-balloon-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "qxl",\
            .property = "revision",\
            .value    = stringify(2),\
        },{\
            .driver   = "qxl-vga",\
            .property = "revision",\
            .value    = stringify(2),\
        },

static void pc_i440fx_0_14_machine_options(MachineClass *m)
{
    pc_i440fx_0_15_machine_options(m);
    m->hw_version = "0.14";
    SET_MACHINE_COMPAT(m, PC_COMPAT_0_14);
}

DEFINE_I440FX_MACHINE(v0_14, "pc-0.14", pc_compat_1_2,
                      pc_i440fx_0_14_machine_options);


#define PC_COMPAT_0_13 \
        PC_CPU_MODEL_IDS("0.13") \
        {\
            .driver   = TYPE_PCI_DEVICE,\
            .property = "command_serr_enable",\
            .value    = "off",\
        },{\
            .driver   = "AC97",\
            .property = "use_broken_id",\
            .value    = stringify(1),\
        },{\
            .driver   = "virtio-9p-pci",\
            .property = "vectors",\
            .value    = stringify(0),\
        },{\
            .driver   = "VGA",\
            .property = "rombar",\
            .value    = stringify(0),\
        },{\
            .driver   = "vmware-svga",\
            .property = "rombar",\
            .value    = stringify(0),\
        },

static void pc_i440fx_0_13_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_i440fx_0_14_machine_options(m);
    m->hw_version = "0.13";
    SET_MACHINE_COMPAT(m, PC_COMPAT_0_13);
    pcmc->kvmclock_enabled = false;
}

DEFINE_I440FX_MACHINE(v0_13, "pc-0.13", pc_compat_0_13,
                      pc_i440fx_0_13_machine_options);


#define PC_COMPAT_0_12 \
        PC_CPU_MODEL_IDS("0.12") \
        {\
            .driver   = "virtio-serial-pci",\
            .property = "max_ports",\
            .value    = stringify(1),\
        },{\
            .driver   = "virtio-serial-pci",\
            .property = "vectors",\
            .value    = stringify(0),\
        },{\
            .driver   = "usb-mouse",\
            .property = "serial",\
            .value    = "1",\
        },{\
            .driver   = "usb-tablet",\
            .property = "serial",\
            .value    = "1",\
        },{\
            .driver   = "usb-kbd",\
            .property = "serial",\
            .value    = "1",\
        },

static void pc_i440fx_0_12_machine_options(MachineClass *m)
{
    pc_i440fx_0_13_machine_options(m);
    m->hw_version = "0.12";
    SET_MACHINE_COMPAT(m, PC_COMPAT_0_12);
}

DEFINE_I440FX_MACHINE(v0_12, "pc-0.12", pc_compat_0_13,
                      pc_i440fx_0_12_machine_options);


#define PC_COMPAT_0_11 \
        PC_CPU_MODEL_IDS("0.11") \
        {\
            .driver   = "virtio-blk-pci",\
            .property = "vectors",\
            .value    = stringify(0),\
        },{\
            .driver   = TYPE_PCI_DEVICE,\
            .property = "rombar",\
            .value    = stringify(0),\
        },{\
            .driver   = "ide-drive",\
            .property = "ver",\
            .value    = "0.11",\
        },{\
            .driver   = "scsi-disk",\
            .property = "ver",\
            .value    = "0.11",\
        },

static void pc_i440fx_0_11_machine_options(MachineClass *m)
{
    pc_i440fx_0_12_machine_options(m);
    m->hw_version = "0.11";
    SET_MACHINE_COMPAT(m, PC_COMPAT_0_11);
}

DEFINE_I440FX_MACHINE(v0_11, "pc-0.11", pc_compat_0_13,
                      pc_i440fx_0_11_machine_options);


#define PC_COMPAT_0_10 \
    PC_CPU_MODEL_IDS("0.10") \
    {\
        .driver   = "virtio-blk-pci",\
        .property = "class",\
        .value    = stringify(PCI_CLASS_STORAGE_OTHER),\
    },{\
        .driver   = "virtio-serial-pci",\
        .property = "class",\
        .value    = stringify(PCI_CLASS_DISPLAY_OTHER),\
    },{\
        .driver   = "virtio-net-pci",\
        .property = "vectors",\
        .value    = stringify(0),\
    },{\
        .driver   = "ide-drive",\
        .property = "ver",\
        .value    = "0.10",\
    },{\
        .driver   = "scsi-disk",\
        .property = "ver",\
        .value    = "0.10",\
    },

static void pc_i440fx_0_10_machine_options(MachineClass *m)
{
    pc_i440fx_0_11_machine_options(m);
    m->hw_version = "0.10";
    SET_MACHINE_COMPAT(m, PC_COMPAT_0_10);
}

DEFINE_I440FX_MACHINE(v0_10, "pc-0.10", pc_compat_0_13,
                      pc_i440fx_0_10_machine_options);

typedef struct {
    uint16_t gpu_device_id;
    uint16_t pch_device_id;
    uint8_t pch_revision_id;
} IGDDeviceIDInfo;

/* In real world different GPU should have different PCH. But actually
 * the different PCH DIDs likely map to different PCH SKUs. We do the
 * same thing for the GPU. For PCH, the different SKUs are going to be
 * all the same silicon design and implementation, just different
 * features turn on and off with fuses. The SW interfaces should be
 * consistent across all SKUs in a given family (eg LPT). But just same
 * features may not be supported.
 *
 * Most of these different PCH features probably don't matter to the
 * Gfx driver, but obviously any difference in display port connections
 * will so it should be fine with any PCH in case of passthrough.
 *
 * So currently use one PCH version, 0x8c4e, to cover all HSW(Haswell)
 * scenarios, 0x9cc3 for BDW(Broadwell).
 */
static const IGDDeviceIDInfo igd_combo_id_infos[] = {
    /* HSW Classic */
    {0x0402, 0x8c4e, 0x04}, /* HSWGT1D, HSWD_w7 */
    {0x0406, 0x8c4e, 0x04}, /* HSWGT1M, HSWM_w7 */
    {0x0412, 0x8c4e, 0x04}, /* HSWGT2D, HSWD_w7 */
    {0x0416, 0x8c4e, 0x04}, /* HSWGT2M, HSWM_w7 */
    {0x041E, 0x8c4e, 0x04}, /* HSWGT15D, HSWD_w7 */
    /* HSW ULT */
    {0x0A06, 0x8c4e, 0x04}, /* HSWGT1UT, HSWM_w7 */
    {0x0A16, 0x8c4e, 0x04}, /* HSWGT2UT, HSWM_w7 */
    {0x0A26, 0x8c4e, 0x06}, /* HSWGT3UT, HSWM_w7 */
    {0x0A2E, 0x8c4e, 0x04}, /* HSWGT3UT28W, HSWM_w7 */
    {0x0A1E, 0x8c4e, 0x04}, /* HSWGT2UX, HSWM_w7 */
    {0x0A0E, 0x8c4e, 0x04}, /* HSWGT1ULX, HSWM_w7 */
    /* HSW CRW */
    {0x0D26, 0x8c4e, 0x04}, /* HSWGT3CW, HSWM_w7 */
    {0x0D22, 0x8c4e, 0x04}, /* HSWGT3CWDT, HSWD_w7 */
    /* HSW Server */
    {0x041A, 0x8c4e, 0x04}, /* HSWSVGT2, HSWD_w7 */
    /* HSW SRVR */
    {0x040A, 0x8c4e, 0x04}, /* HSWSVGT1, HSWD_w7 */
    /* BSW */
    {0x1606, 0x9cc3, 0x03}, /* BDWULTGT1, BDWM_w7 */
    {0x1616, 0x9cc3, 0x03}, /* BDWULTGT2, BDWM_w7 */
    {0x1626, 0x9cc3, 0x03}, /* BDWULTGT3, BDWM_w7 */
    {0x160E, 0x9cc3, 0x03}, /* BDWULXGT1, BDWM_w7 */
    {0x161E, 0x9cc3, 0x03}, /* BDWULXGT2, BDWM_w7 */
    {0x1602, 0x9cc3, 0x03}, /* BDWHALOGT1, BDWM_w7 */
    {0x1612, 0x9cc3, 0x03}, /* BDWHALOGT2, BDWM_w7 */
    {0x1622, 0x9cc3, 0x03}, /* BDWHALOGT3, BDWM_w7 */
    {0x162B, 0x9cc3, 0x03}, /* BDWHALO28W, BDWM_w7 */
    {0x162A, 0x9cc3, 0x03}, /* BDWGT3WRKS, BDWM_w7 */
    {0x162D, 0x9cc3, 0x03}, /* BDWGT3SRVR, BDWM_w7 */
};

static void isa_bridge_class_init(ObjectClass *klass, void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    PCIDeviceClass *k = PCI_DEVICE_CLASS(klass);

    dc->desc        = "ISA bridge faked to support IGD PT";
    k->vendor_id    = PCI_VENDOR_ID_INTEL;
    k->class_id     = PCI_CLASS_BRIDGE_ISA;
};

static TypeInfo isa_bridge_info = {
    .name          = "igd-passthrough-isa-bridge",
    .parent        = TYPE_PCI_DEVICE,
    .instance_size = sizeof(PCIDevice),
    .class_init = isa_bridge_class_init,
    .interfaces = (InterfaceInfo[]) {
        { INTERFACE_CONVENTIONAL_PCI_DEVICE },
        { },
    },
};

static void pt_graphics_register_types(void)
{
    type_register_static(&isa_bridge_info);
}
type_init(pt_graphics_register_types)

void igd_passthrough_isa_bridge_create(PCIBus *bus, uint16_t gpu_dev_id)
{
    struct PCIDevice *bridge_dev;
    int i, num;
    uint16_t pch_dev_id = 0xffff;
    uint8_t pch_rev_id;

    num = ARRAY_SIZE(igd_combo_id_infos);
    for (i = 0; i < num; i++) {
        if (gpu_dev_id == igd_combo_id_infos[i].gpu_device_id) {
            pch_dev_id = igd_combo_id_infos[i].pch_device_id;
            pch_rev_id = igd_combo_id_infos[i].pch_revision_id;
        }
    }

    if (pch_dev_id == 0xffff) {
        return;
    }

    /* Currently IGD drivers always need to access PCH by 1f.0. */
    bridge_dev = pci_create_simple(bus, PCI_DEVFN(0x1f, 0),
                                   "igd-passthrough-isa-bridge");

    /*
     * Note that vendor id is always PCI_VENDOR_ID_INTEL.
     */
    if (!bridge_dev) {
        fprintf(stderr, "set igd-passthrough-isa-bridge failed!\n");
        return;
    }
    pci_config_set_device_id(bridge_dev->config, pch_dev_id);
    pci_config_set_revision(bridge_dev->config, pch_rev_id);
}

static void isapc_machine_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    m->desc = "ISA-only PC";
    m->max_cpus = 1;
    m->option_rom_has_mr = true;
    m->rom_file_has_mr = false;
    pcmc->pci_enabled = false;
    pcmc->has_acpi_build = false;
    pcmc->smbios_defaults = false;
    pcmc->gigabyte_align = false;
    pcmc->smbios_legacy_mode = true;
    pcmc->has_reserved_memory = false;
    pcmc->default_nic_model = "ne2k_isa";
    m->default_cpu_type = X86_CPU_TYPE_NAME("486");
}

DEFINE_PC_MACHINE(isapc, "isapc", pc_init_isa,
                  isapc_machine_options);


#ifdef CONFIG_XEN
static void xenfv_machine_options(MachineClass *m)
{
    m->desc = "Xen Fully-virtualized PC";
    m->max_cpus = HVM_MAX_VCPUS;
    m->default_machine_opts = "accel=xen";
}

DEFINE_PC_MACHINE(xenfv, "xenfv", pc_xen_hvm_init,
                  xenfv_machine_options);
#endif
machine_init(pc_machine_init);

#endif  /* Disabled for Red Hat Enterprise Linux */

/* Red Hat Enterprise Linux machine types */

/* Options for the latest rhel7 machine type */
static void pc_machine_rhel7_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    m->family = "pc_piix_Y";
    m->default_machine_opts = "firmware=bios-256k.bin";
    pcmc->default_nic_model = "e1000";
    m->default_display = "std";
    SET_MACHINE_COMPAT(m, PC_RHEL_COMPAT);
    m->alias = "pc";
    m->is_default = 1;
}

static void pc_init_rhel760(MachineState *machine)
{
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel760_options(MachineClass *m)
{
    pc_machine_rhel7_options(m);
    m->desc = "RHEL 7.6.0 PC (i440FX + PIIX, 1996)";
}

DEFINE_PC_MACHINE(rhel760, "pc-i440fx-rhel7.6.0", pc_init_rhel760,
                  pc_machine_rhel760_options);

static void pc_init_rhel750(MachineState *machine)
{
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel750_options(MachineClass *m)
{
    pc_machine_rhel760_options(m);
    m->alias = NULL;
    m->is_default = 0;
    m->desc = "RHEL 7.5.0 PC (i440FX + PIIX, 1996)";
    m->auto_enable_numa_with_memhp = false;
    SET_MACHINE_COMPAT(m, PC_RHEL7_5_COMPAT);
}

DEFINE_PC_MACHINE(rhel750, "pc-i440fx-rhel7.5.0", pc_init_rhel750,
                  pc_machine_rhel750_options);

static void pc_init_rhel740(MachineState *machine)
{
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel740_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_machine_rhel750_options(m);
    m->desc = "RHEL 7.4.0 PC (i440FX + PIIX, 1996)";
    m->numa_auto_assign_ram = numa_legacy_auto_assign_ram;
    pcmc->pc_rom_ro = false;
    SET_MACHINE_COMPAT(m, PC_RHEL7_4_COMPAT);
}

DEFINE_PC_MACHINE(rhel740, "pc-i440fx-rhel7.4.0", pc_init_rhel740,
                  pc_machine_rhel740_options);

static void pc_init_rhel730(MachineState *machine)
{
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel730_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_machine_rhel740_options(m);
    m->alias = NULL;
    m->is_default = 0;
    m->desc = "RHEL 7.3.0 PC (i440FX + PIIX, 1996)";
    pcmc->linuxboot_dma_enabled = false;
    SET_MACHINE_COMPAT(m, PC_RHEL7_3_COMPAT);
}

DEFINE_PC_MACHINE(rhel730, "pc-i440fx-rhel7.3.0", pc_init_rhel730,
                  pc_machine_rhel730_options);


static void pc_init_rhel720(MachineState *machine)
{
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel720_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_machine_rhel730_options(m);
    m->desc = "RHEL 7.2.0 PC (i440FX + PIIX, 1996)";
    /* From pc_i440fx_2_5_machine_options */
    pcmc->save_tsc_khz = false;
    m->legacy_fw_cfg_order = 1;
    /* Note: broken_reserved_end was already in 7.2 */
    /* From pc_i440fx_2_6_machine_options */
    pcmc->legacy_cpu_hotplug = true;
    SET_MACHINE_COMPAT(m, PC_RHEL7_2_COMPAT);
}

DEFINE_PC_MACHINE(rhel720, "pc-i440fx-rhel7.2.0", pc_init_rhel720,
                  pc_machine_rhel720_options);

static void pc_compat_rhel710(MachineState *machine)
{
    PCMachineState *pcms = PC_MACHINE(machine);
    PCMachineClass *pcmc = PC_MACHINE_GET_CLASS(pcms);

    /* From pc_compat_2_2 */
    pcmc->rsdp_in_ram = false;
    machine->suppress_vmdesc = true;

    /* From pc_compat_2_1 */
    pcmc->smbios_uuid_encoded = false;
    x86_cpu_change_kvm_default("svm", NULL);
    pcmc->enforce_aligned_dimm = false;

    /* Disable all the extra subsections that were added in 2.2 */
    migrate_pre_2_2 = true;

    /* From pc_i440fx_2_4_machine_options */
    pcmc->broken_reserved_end = true;
}

static void pc_init_rhel710(MachineState *machine)
{
    pc_compat_rhel710(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel710_options(MachineClass *m)
{
    pc_machine_rhel720_options(m);
    m->family = "pc_piix_Y";
    m->desc = "RHEL 7.1.0 PC (i440FX + PIIX, 1996)";
    m->default_display = "cirrus";
    SET_MACHINE_COMPAT(m, PC_RHEL7_1_COMPAT);
}

DEFINE_PC_MACHINE(rhel710, "pc-i440fx-rhel7.1.0", pc_init_rhel710,
                  pc_machine_rhel710_options);

static void pc_compat_rhel700(MachineState *machine)
{
    PCMachineState *pcms = PC_MACHINE(machine);
    PCMachineClass *pcmc = PC_MACHINE_GET_CLASS(pcms);

    pc_compat_rhel710(machine);

    /* Upstream enables it for everyone, we're a little more selective */
    x86_cpu_change_kvm_default("x2apic", NULL);
    x86_cpu_change_kvm_default("svm", NULL);
    pcmc->legacy_acpi_table_size = 6418; /* see pc_compat_2_0() */
    pcmc->smbios_legacy_mode = true;
    pcmc->has_reserved_memory = false;
    migrate_cve_2014_5263_xhci_fields = true;
}

static void pc_init_rhel700(MachineState *machine)
{
    pc_compat_rhel700(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);
}

static void pc_machine_rhel700_options(MachineClass *m)
{
    pc_machine_rhel710_options(m);
    m->family = "pc_piix_Y";
    m->desc = "RHEL 7.0.0 PC (i440FX + PIIX, 1996)";
    SET_MACHINE_COMPAT(m, PC_RHEL7_0_COMPAT);
}

DEFINE_PC_MACHINE(rhel700, "pc-i440fx-rhel7.0.0", pc_init_rhel700,
                  pc_machine_rhel700_options);

#define PC_RHEL6_6_COMPAT \
        {\
            .driver   = "scsi-hd",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "scsi-cd",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "scsi-disk",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "ide-hd",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "ide-cd",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "ide-drive",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "virtio-blk-pci",\
            .property = "discard_granularity",\
            .value    = stringify(0),\
        },{\
            .driver   = "virtio-serial-pci",\
            .property = "vectors",\
            /* DEV_NVECTORS_UNSPECIFIED as a uint32_t string */\
            .value    = stringify(0xFFFFFFFF),\
        },{\
            .driver   = "486-" TYPE_X86_CPU,\
            .property = "model",\
            .value    = stringify(0),\
        },{\
            .driver   = "usb-tablet",\
            .property = "usb_version",\
            .value    = stringify(1),\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "mq",\
            .value    = "off",\
        },{\
            .driver   = "VGA",\
            .property = "mmio",\
            .value    = "off",\
        },{\
            .driver   = "virtio-blk-pci",\
            .property = "config-wce",\
            .value    = "off",\
        },{\
            .driver   = TYPE_ISA_FDC,\
            .property = "check_media_rate",\
            .value    = "off",\
        },{\
            .driver   = "virtio-balloon-pci",\
            .property = "class",\
            .value    = stringify(PCI_CLASS_MEMORY_RAM),\
        },{\
            .driver   = TYPE_PCI_DEVICE,\
            .property = "command_serr_enable",\
            .value    = "off",\
        },{\
            .driver   = "AC97",\
            .property = "use_broken_id",\
            .value    = stringify(1),\
        },{\
            .driver   = "intel-hda",\
            .property = "msi",\
            .value    = "off",\
        },{\
            .driver = "qemu32-" TYPE_X86_CPU,\
            .property = "min-xlevel",\
            .value = stringify(0),\
        },{\
            .driver = "486-" TYPE_X86_CPU,\
            .property = "min-level",\
            .value = stringify(0),\
        },{\
            .driver   = "qemu32-" TYPE_X86_CPU,\
            .property = "model",\
            .value    = stringify(3),\
        },{\
            .driver   = "usb-ccid",\
            .property = "serial",\
            .value    = "1",\
        },{\
            .driver   = "ne2k_pci",\
            .property = "romfile",\
            .value    = "rhel6-ne2k_pci.rom",\
        },{\
            .driver   = "pcnet",\
            .property = "romfile",\
            .value    = "rhel6-pcnet.rom",\
        },{\
            .driver   = "rtl8139",\
            .property = "romfile",\
            .value    = "rhel6-rtl8139.rom",\
        },{\
            .driver   = "e1000",\
            .property = "romfile",\
            .value    = "rhel6-e1000.rom",\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "romfile",\
            .value    = "rhel6-virtio.rom",\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "any_layout",\
            .value    = "off",\
        },\
        {\
            .driver = "pentium" "-" TYPE_X86_CPU,\
            .property = "apic",\
            .value = "off",\
        },\
        {\
            .driver = "pentium2" "-" TYPE_X86_CPU,\
            .property = "apic",\
            .value = "off",\
        },\
        {\
            .driver = "pentium3" "-" TYPE_X86_CPU,\
            .property = "apic",\
            .value = "off",\
        },\
        {\
            .driver = "Conroe" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Penryn" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Nehalem" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Nehalem-IBRS" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "pclmulqdq",\
            .value = "off",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "pclmulqdq",\
            .value = "off",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "fxsr",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "fxsr",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "mmx",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "mmx",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "pat",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "pat",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "cmov",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "cmov",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "pge",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "pge",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "apic",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "apic",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "cx8",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "cx8",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "mce",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "mce",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "pae",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "pae",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "msr",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "msr",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "tsc",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "tsc",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "pse",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "pse",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "de",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "de",\
            .value = "on",\
        },\
        {\
            .driver = "Westmere" "-" TYPE_X86_CPU,\
            .property = "fpu",\
            .value = "on",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Westmere-IBRS" "-" TYPE_X86_CPU,\
            .property = "fpu",\
            .value = "on",\
        },\
        {\
            .driver = "Broadwell" "-" TYPE_X86_CPU,\
            .property = "rdtscp",\
            .value = "off",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Broadwell-IBRS" "-" TYPE_X86_CPU,\
            .property = "rdtscp",\
            .value = "off",\
        },\
        {\
            .driver = "Broadwell" "-" TYPE_X86_CPU,\
            .property = "smap",\
            .value = "off",\
        },\
        { /* PC_RHEL6_6_COMPAT (copied from the entry above) */ \
            .driver = "Broadwell-IBRS" "-" TYPE_X86_CPU,\
            .property = "smap",\
            .value = "off",\
        },\
        {\
            .driver = TYPE_X86_CPU,\
            .property = "rdtscp",\
            .value = "off",\
        },\
        {\
            .driver = "Opteron_G1" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Opteron_G2" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Opteron_G3" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "on",\
        },\
        {\
            .driver = "Opteron_G4" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "off",\
        },\
        {\
            .driver = "Opteron_G5" "-" TYPE_X86_CPU,\
            .property = "x2apic",\
            .value = "off",\
        },\
        {\
            .driver = TYPE_X86_CPU,\
            .property = "3dnow",\
            .value = "off",\
        },\
        {\
            .driver = TYPE_X86_CPU,\
            .property = "3dnowext",\
            .value = "off",\
        },\
        {\
            .driver = "virtio-net-pci",\
            .property = "__com.redhat_rhel6_ctrl_guest_workaround", \
            .value = "on",\
        },

static void pc_compat_rhel660(MachineState *machine)
{
    PCMachineState *pcms = PC_MACHINE(machine);
    PCMachineClass *pcmc = PC_MACHINE_GET_CLASS(pcms);

    pc_compat_rhel700(machine);
    if (!machine->cpu_type) {
        machine->cpu_type = "cpu64-rhel6";
    }

    x86_cpu_change_kvm_default("kvm-pv-unhalt", NULL);

    pcmc->gigabyte_align = false;
    shadow_bios_after_incoming = true;
    ich9_uhci123_irqpin_override = true;
}

static void pc_init_rhel660(MachineState *machine)
{
    pc_compat_rhel660(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel660_options(MachineClass *m)
{
    PCMachineClass *pcmc = PC_MACHINE_CLASS(m);
    pc_machine_rhel700_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.6.0 PC";
    m->rom_file_has_mr = false;
    m->default_machine_opts = "firmware=bios.bin";
    pcmc->has_acpi_build = false;
    SET_MACHINE_COMPAT(m, PC_RHEL6_6_COMPAT);
}

DEFINE_PC_MACHINE(rhel660, "rhel6.6.0", pc_init_rhel660,
                  pc_machine_rhel660_options);

#define PC_RHEL6_5_COMPAT \
        {\
            .driver   = TYPE_USB_DEVICE,\
            .property = "msos-desc",\
            .value    = "no",\
        },

static void pc_compat_rhel650(MachineState *machine)
{
    pc_compat_rhel660(machine);
}

static void pc_init_rhel650(MachineState *machine)
{
    pc_compat_rhel650(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel650_options(MachineClass *m)
{
    pc_machine_rhel660_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.5.0 PC";
    SET_MACHINE_COMPAT(m, PC_RHEL6_5_COMPAT);
}

DEFINE_PC_MACHINE(rhel650, "rhel6.5.0", pc_init_rhel650,
                  pc_machine_rhel650_options);

#define PC_RHEL6_4_COMPAT \
        {\
            .driver   = "virtio-scsi-pci",\
            .property = "vectors",\
            .value    = stringify(2),\
        },{\
            .driver   = "hda-micro",\
            .property = "mixer",\
            .value    = "off",\
        },{\
            .driver   = "hda-duplex",\
            .property = "mixer",\
            .value    = "off",\
        },{\
            .driver   = "hda-output",\
            .property = "mixer",\
            .value    = "off",\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "ctrl_mac_addr",\
            .value    = "off",\
        },\
        {\
            .driver = TYPE_X86_CPU,\
            .property = "sep",\
            .value = "off",\
        },\
        {\
            .driver = "virtio-net-pci",\
            .property = "__com.redhat_rhel6_ctrl_guest_workaround", \
            .value = "off",\
        },

static void pc_compat_rhel640(MachineState *machine)
{
    pc_compat_rhel650(machine);
}

static void pc_init_rhel640(MachineState *machine)
{
    pc_compat_rhel640(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel640_options(MachineClass *m)
{
    pc_machine_rhel650_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.4.0 PC";
    SET_MACHINE_COMPAT(m, PC_RHEL6_4_COMPAT);
}

DEFINE_PC_MACHINE(rhel640, "rhel6.4.0", pc_init_rhel640,
                  pc_machine_rhel640_options);

#define PC_RHEL6_3_COMPAT \
        {\
            .driver   = "Conroe-" TYPE_X86_CPU,\
            .property = "min-level",\
            .value    = stringify(2),\
        },{\
            .driver   = "Penryn-" TYPE_X86_CPU,\
            .property = "min-level",\
            .value    = stringify(2),\
        },{\
            .driver   = "Nehalem-" TYPE_X86_CPU,\
            .property = "min-level",\
            .value    = stringify(2),\
        },{\
            .driver   = "e1000",\
            .property = "autonegotiation",\
            .value    = "off",\
        },{\
            .driver   = "qxl",\
            .property = "revision",\
            .value    = stringify(3),\
        },{\
            .driver   = "qxl-vga",\
            .property = "revision",\
            .value    = stringify(3),\
        },{\
            .driver   = "virtio-scsi-pci",\
            .property = "hotplug",\
            .value    = "off",\
        },{\
            .driver   = "virtio-scsi-pci",\
            .property = "param_change",\
            .value    = "off",\
        },{\
            .driver = TYPE_X86_CPU,\
            .property = "pmu",\
            .value = "on",\
        },{\
            .driver   = "usb-hub",\
            .property = "serial",\
            .value    = "314159",\
        },{\
            .driver   = "usb-storage",\
            .property = "serial",\
            .value    = "1",\
        },\
        {\
            .driver = "SandyBridge" "-" TYPE_X86_CPU,\
            .property = "tsc-deadline",\
            .value = "off",\
        },\
        { /* PC_RHEL6_3_COMPAT (copied from the entry above) */ \
            .driver = "SandyBridge-IBRS" "-" TYPE_X86_CPU,\
            .property = "tsc-deadline",\
            .value = "off",\
        },

static void pc_compat_rhel630(MachineState *machine)
{
    pc_compat_rhel640(machine);
    x86_cpu_change_kvm_default("kvm-pv-eoi",NULL);
    enable_compat_apic_id_mode();
}

static void pc_init_rhel630(MachineState *machine)
{
    pc_compat_rhel630(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel630_options(MachineClass *m)
{
    pc_machine_rhel640_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.3.0 PC";
    SET_MACHINE_COMPAT(m, PC_RHEL6_3_COMPAT);
}

DEFINE_PC_MACHINE(rhel630, "rhel6.3.0", pc_init_rhel630,
                  pc_machine_rhel630_options);


#define PC_RHEL6_2_COMPAT \
        {\
            .driver = TYPE_X86_CPU,\
            .property = "pmu",\
            .value = "off",\
        },

static void pc_compat_rhel620(MachineState *machine)
{
    pc_compat_rhel630(machine);
}

static void pc_init_rhel620(MachineState *machine)
{
    pc_compat_rhel620(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel620_options(MachineClass *m)
{
    pc_machine_rhel630_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.2.0 PC";
    SET_MACHINE_COMPAT(m, PC_RHEL6_2_COMPAT);
}

DEFINE_PC_MACHINE(rhel620, "rhel6.2.0", pc_init_rhel620,
                  pc_machine_rhel620_options);

/*
 * NOTE: We don't have the event_idx compat entry for the
 * virtio-balloon-pci driver because RHEL6 doesn't disable
 * it either due to a bug (see RHBZ 1029539 fo more info)
 */
#define PC_RHEL6_1_COMPAT \
        {\
            .driver   = "PIIX4_PM",\
            .property = "disable_s3",\
            .value    = "0",\
        },{\
            .driver   = "PIIX4_PM",\
            .property = "disable_s4",\
            .value    = "0",\
        },{\
            .driver   = "qxl",\
            .property = "revision",\
            .value    = stringify(2),\
        },{\
            .driver   = "qxl-vga",\
            .property = "revision",\
            .value    = stringify(2),\
        },{\
            .driver   = "virtio-blk-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "virtio-serial-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "virtio-net-pci",\
            .property = "event_idx",\
            .value    = "off",\
        },{\
            .driver   = "usb-kbd",\
            .property = "serial",\
            .value    = "1",\
        },{\
            .driver   = "usb-mouse",\
            .property = "serial",\
            .value    = "1",\
        },{\
            .driver   = "usb-tablet",\
            .property = "serial",\
            .value    = "1",\
        },

static void pc_compat_rhel610(MachineState *machine)
{
    pc_compat_rhel620(machine);
}

static void pc_init_rhel610(MachineState *machine)
{
    pc_compat_rhel610(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel610_options(MachineClass *m)
{
    pc_machine_rhel620_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.1.0 PC";
    SET_MACHINE_COMPAT(m, PC_RHEL6_1_COMPAT);
}

DEFINE_PC_MACHINE(rhel610, "rhel6.1.0", pc_init_rhel610,
                  pc_machine_rhel610_options);

#define PC_RHEL6_0_COMPAT \
        {\
            .driver   = "qxl",\
            .property = "revision",\
            .value    = stringify(1),\
        },{\
            .driver   = "qxl-vga",\
            .property = "revision",\
            .value    = stringify(1),\
        },{\
            .driver   = "VGA",\
            .property = "rombar",\
            .value    = stringify(0),\
        },

static void pc_compat_rhel600(MachineState *machine)
{
    pc_compat_rhel610(machine);
}

static void pc_init_rhel600(MachineState *machine)
{
    pc_compat_rhel600(machine);
    pc_init1(machine, TYPE_I440FX_PCI_HOST_BRIDGE, \
             TYPE_I440FX_PCI_DEVICE);}

static void pc_machine_rhel600_options(MachineClass *m)
{
    pc_machine_rhel610_options(m);
    m->family = "pc_piix_Z";
    m->desc = "RHEL 6.0.0 PC";
    SET_MACHINE_COMPAT(m, PC_RHEL6_0_COMPAT);
}

DEFINE_PC_MACHINE(rhel600, "rhel6.0.0", pc_init_rhel600,
                  pc_machine_rhel600_options);
