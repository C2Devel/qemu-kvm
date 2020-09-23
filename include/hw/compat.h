#ifndef HW_COMPAT_H
#define HW_COMPAT_H

#define HW_COMPAT_2_11 \
    {\
        .driver   = "hpet",\
        .property = "hpet-offset-saved",\
        .value    = "false",\
    },{\
        .driver   = "virtio-blk-pci",\
        .property = "vectors",\
        .value    = "2",\
    },{\
        .driver   = "vhost-user-blk-pci",\
        .property = "vectors",\
        .value    = "2",\
    },{\
        .driver   = "e1000",\
        .property = "migrate_tso_props",\
        .value    = "off",\
    },

#define HW_COMPAT_2_10 \
    {\
        .driver   = "virtio-mouse-device",\
        .property = "wheel-axis",\
        .value    = "false",\
    },{\
        .driver   = "virtio-tablet-device",\
        .property = "wheel-axis",\
        .value    = "false",\
    },

#define HW_COMPAT_2_9 \
    {\
        .driver   = "pci-bridge",\
        .property = "shpc",\
        .value    = "off",\
    },{\
        .driver   = "intel-iommu",\
        .property = "pt",\
        .value    = "off",\
    },{\
        .driver   = "virtio-net-device",\
        .property = "x-mtu-bypass-backend",\
        .value    = "off",\
    },{\
        .driver   = "pcie-root-port",\
        .property = "x-migrate-msix",\
        .value    = "false",\
    },

#define HW_COMPAT_2_8 \
    {\
        .driver   = "fw_cfg_mem",\
        .property = "x-file-slots",\
        .value    = stringify(0x10),\
    },{\
        .driver   = "fw_cfg_io",\
        .property = "x-file-slots",\
        .value    = stringify(0x10),\
    },{\
        .driver   = "pflash_cfi01",\
        .property = "old-multiple-chip-handling",\
        .value    = "on",\
    },{\
        .driver   = "pci-bridge",\
        .property = "shpc",\
        .value    = "on",\
    },{\
        .driver   = TYPE_PCI_DEVICE,\
        .property = "x-pcie-extcap-init",\
        .value    = "off",\
    },{\
        .driver   = "virtio-pci",\
        .property = "x-pcie-deverr-init",\
        .value    = "off",\
    },{\
        .driver   = "virtio-pci",\
        .property = "x-pcie-lnkctl-init",\
        .value    = "off",\
    },{\
        .driver   = "virtio-pci",\
        .property = "x-pcie-pm-init",\
        .value    = "off",\
    },{\
        .driver   = "cirrus-vga",\
        .property = "vgamem_mb",\
        .value    = "8",\
    },{\
        .driver   = "isa-cirrus-vga",\
        .property = "vgamem_mb",\
        .value    = "8",\
    },

#define HW_COMPAT_2_7 \
    {\
        .driver   = "virtio-pci",\
        .property = "page-per-vq",\
        .value    = "on",\
    },{\
        .driver   = "virtio-serial-device",\
        .property = "emergency-write",\
        .value    = "off",\
    },{\
        .driver   = "ioapic",\
        .property = "version",\
        .value    = "0x11",\
    },{\
        .driver   = "intel-iommu",\
        .property = "x-buggy-eim",\
        .value    = "true",\
    },{\
        .driver   = "virtio-pci",\
        .property = "x-ignore-backend-features",\
        .value    = "on",\
    },

#define HW_COMPAT_2_6 \
    {\
        .driver   = "virtio-mmio",\
        .property = "format_transport_address",\
        .value    = "off",\
    },{\
        .driver   = "virtio-pci",\
        .property = "disable-modern",\
        .value    = "on",\
    },{\
        .driver   = "virtio-pci",\
        .property = "disable-legacy",\
        .value    = "off",\
    },

#define HW_COMPAT_2_5 \
    {\
        .driver   = "isa-fdc",\
        .property = "fallback",\
        .value    = "144",\
    },{\
        .driver   = "pvscsi",\
        .property = "x-old-pci-configuration",\
        .value    = "on",\
    },{\
        .driver   = "pvscsi",\
        .property = "x-disable-pcie",\
        .value    = "on",\
    },\
    {\
        .driver   = "vmxnet3",\
        .property = "x-old-msi-offsets",\
        .value    = "on",\
    },{\
        .driver   = "vmxnet3",\
        .property = "x-disable-pcie",\
        .value    = "on",\
    },

#define HW_COMPAT_2_4 \
    {\
        .driver   = "virtio-blk-device",\
        .property = "scsi",\
        .value    = "true",\
    },{\
        .driver   = "e1000",\
        .property = "extra_mac_registers",\
        .value    = "off",\
    },{\
        .driver   = "virtio-pci",\
        .property = "x-disable-pcie",\
        .value    = "on",\
    },{\
        .driver   = "virtio-pci",\
        .property = "migrate-extra",\
        .value    = "off",\
    },{\
        .driver   = "fw_cfg_mem",\
        .property = "dma_enabled",\
        .value    = "off",\
    },{\
        .driver   = "fw_cfg_io",\
        .property = "dma_enabled",\
        .value    = "off",\
    },

#define HW_COMPAT_2_3 \
    {\
        .driver   = "virtio-blk-pci",\
        .property = "any_layout",\
        .value    = "off",\
    },{\
        .driver   = "virtio-balloon-pci",\
        .property = "any_layout",\
        .value    = "off",\
    },{\
        .driver   = "virtio-serial-pci",\
        .property = "any_layout",\
        .value    = "off",\
    },{\
        .driver   = "virtio-9p-pci",\
        .property = "any_layout",\
        .value    = "off",\
    },{\
        .driver   = "virtio-rng-pci",\
        .property = "any_layout",\
        .value    = "off",\
    },{\
        .driver   = TYPE_PCI_DEVICE,\
        .property = "x-pcie-lnksta-dllla",\
        .value    = "off",\
    },{\
        .driver   = "migration",\
        .property = "send-configuration",\
        .value    = "off",\
    },{\
        .driver   = "migration",\
        .property = "send-section-footer",\
        .value    = "off",\
    },{\
        .driver   = "migration",\
        .property = "store-global-state",\
        .value    = "off",\
    },

#define HW_COMPAT_2_2 \
    /* empty */

#define HW_COMPAT_2_1 \
    {\
        .driver   = "intel-hda",\
        .property = "old_msi_addr",\
        .value    = "on",\
    },{\
        .driver   = "VGA",\
        .property = "qemu-extended-regs",\
        .value    = "off",\
    },{\
        .driver   = "secondary-vga",\
        .property = "qemu-extended-regs",\
        .value    = "off",\
    },{\
        .driver   = "virtio-scsi-pci",\
        .property = "any_layout",\
        .value    = "off",\
    },{\
        .driver   = "usb-mouse",\
        .property = "usb_version",\
        .value    = stringify(1),\
    },{\
        .driver   = "usb-kbd",\
        .property = "usb_version",\
        .value    = stringify(1),\
    },{\
        .driver   = "virtio-pci",\
        .property = "virtio-pci-bus-master-bug-migration",\
        .value    = "on",\
    },

/* Mostly like HW_COMPAT_2_1 but:
 *    we don't need virtio-scsi-pci since 7.0 already had that on
 *
 * RH: Note, qemu-extended-regs should have been enabled in the 7.1
 * machine type, but was accidentally turned off in 7.2 onwards.
 *
 */
#define HW_COMPAT_RHEL7_1 \
        { /* COMPAT_RHEL7.1 */ \
            .driver   = "intel-hda-generic",\
            .property = "old_msi_addr",\
            .value    = "on",\
        },{\
            .driver   = "VGA",\
            .property = "qemu-extended-regs",\
            .value    = "off",\
        },{\
            .driver   = "secondary-vga",\
            .property = "qemu-extended-regs",\
            .value    = "off",\
        },{\
            .driver   = "usb-mouse",\
            .property = "usb_version",\
            .value    = stringify(1),\
        },{\
            .driver   = "usb-kbd",\
            .property = "usb_version",\
            .value    = stringify(1),\
        },{\
            .driver   = "virtio-pci",\
            .property = "virtio-pci-bus-master-bug-migration",\
            .value    = "on",\
        },{\
            .driver   = "virtio-blk-pci",\
            .property = "any_layout",\
            .value    = "off",\
        },{\
            .driver   = "virtio-balloon-pci",\
            .property = "any_layout",\
            .value    = "off",\
        },{\
            .driver   = "virtio-serial-pci",\
            .property = "any_layout",\
            .value    = "off",\
        },{\
            .driver   = "virtio-9p-pci",\
            .property = "any_layout",\
            .value    = "off",\
        },{\
            .driver   = "virtio-rng-pci",\
            .property = "any_layout",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_1 - introduced with 2.10.0 */ \
            .driver   = "migration",\
            .property = "send-configuration",\
            .value    = "off",\
        },

/* Mostly like HW_COMPAT_2_4 + 2_3 but:
 *  we don't need "any_layout" as it has been backported to 7.2
 */

#define HW_COMPAT_RHEL7_2 \
        {\
            .driver   = "virtio-blk-device",\
            .property = "scsi",\
            .value    = "true",\
        },{\
            .driver   = "e1000-82540em",\
            .property = "extra_mac_registers",\
            .value    = "off",\
        },{\
            .driver   = "virtio-pci",\
            .property = "x-disable-pcie",\
            .value    = "on",\
        },{\
            .driver   = "virtio-pci",\
            .property = "migrate-extra",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = "fw_cfg_mem",\
            .property = "dma_enabled",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = "fw_cfg_io",\
            .property = "dma_enabled",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = "isa-fdc",\
            .property = "fallback",\
            .value    = "144",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = "virtio-pci",\
            .property = "disable-modern",\
            .value    = "on",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = "virtio-pci",\
            .property = "disable-legacy",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = TYPE_PCI_DEVICE,\
            .property = "x-pcie-lnksta-dllla",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 */ \
            .driver   = "virtio-pci",\
            .property = "page-per-vq",\
            .value    = "on",\
        },{ /* HW_COMPAT_RHEL7_2 from HW_COMPAT_2_4 added in 2.9 */ \
            .driver   = "vmgenid",\
            .property = "x-write-pointer-available",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 - introduced with 2.10.0 */ \
            .driver   = "migration",\
            .property = "send-section-footer",\
            .value    = "off",\
        },{ /* HW_COMPAT_RHEL7_2 - introduced with 2.10.0 */ \
            .driver   = "migration",\
            .property = "store-global-state",\
            .value    = "off",\
        },

/* Mostly like HW_COMPAT_2_6 + HW_COMPAT_2_7 + HW_COMPAT_2_8 except
 * disable-modern, disable-legacy, page-per-vq have already been
 * backported to RHEL7.3
 */
#define HW_COMPAT_RHEL7_3 \
    { /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-mmio",\
        .property = "format_transport_address",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-serial-device",\
        .property = "emergency-write",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "ioapic",\
        .property = "version",\
        .value    = "0x11",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "intel-iommu",\
        .property = "x-buggy-eim",\
        .value    = "true",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-pci",\
        .property = "x-ignore-backend-features",\
        .value    = "on",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "fw_cfg_mem",\
        .property = "x-file-slots",\
        .value    = stringify(0x10),\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "fw_cfg_io",\
        .property = "x-file-slots",\
        .value    = stringify(0x10),\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "pflash_cfi01",\
        .property = "old-multiple-chip-handling",\
        .value    = "on",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = TYPE_PCI_DEVICE,\
        .property = "x-pcie-extcap-init",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-pci",\
        .property = "x-pcie-deverr-init",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-pci",\
        .property = "x-pcie-lnkctl-init",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-pci",\
        .property = "x-pcie-pm-init",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "virtio-net-device",\
        .property = "x-mtu-bypass-backend",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_3 */ \
        .driver   = "e1000e",\
        .property = "__redhat_e1000e_7_3_intr_state",\
        .value    = "on",\
    },

/* Mostly like HW_COMPAT_2_9 except
 * x-mtu-bypass-backend, x-migrate-msix has already been
 * backported to RHEL7.4. shpc was already on in 7.4.
 */
#define HW_COMPAT_RHEL7_4 \
    { /* HW_COMPAT_RHEL7_4 */ \
        .driver   = "intel-iommu",\
        .property = "pt",\
        .value    = "off",\
    },

/* The same as HW_COMPAT_2_11 + HW_COMPAT_2_10 */
#define HW_COMPAT_RHEL7_5 \
    { /* HW_COMPAT_RHEL7_5 from HW_COMPAT_2_11 */ \
        .driver   = "hpet",\
        .property = "hpet-offset-saved",\
        .value    = "false",\
    },{ /* HW_COMPAT_RHEL7_5 from HW_COMPAT_2_11 */ \
        .driver   = "virtio-blk-pci",\
        .property = "vectors",\
        .value    = "2",\
    },{ /* HW_COMPAT_RHEL7_5 from HW_COMPAT_2_11 */ \
        .driver   = "vhost-user-blk-pci",\
        .property = "vectors",\
        .value    = "2",\
    },{ /* HW_COMPAT_RHEL7_5 from HW_COMPAT_2_11 but \
           bz 1608778 modified for our naming */ \
        .driver   = "e1000-82540em",\
        .property = "migrate_tso_props",\
        .value    = "off",\
    },{ /* HW_COMPAT_RHEL7_5 from HW_COMPAT_2_10 */ \
        .driver   = "virtio-mouse-device",\
        .property = "wheel-axis",\
        .value    = "false",\
    },{ /* HW_COMPAT_RHEL7_5 from HW_COMPAT_2_10 */ \
        .driver   = "virtio-tablet-device",\
        .property = "wheel-axis",\
        .value    = "false",\
    },{ /* HW_COMPAT_RHEL7_5 */ \
        .driver   = "cirrus-vga",\
        .property = "vgamem_mb",\
        .value    = "16",\
    },{ /* HW_COMPAT_RHEL7_5 */ \
        .driver   = "migration",\
        .property = "decompress-error-check",\
        .value    = "off",\
    },


#endif /* HW_COMPAT_H */
