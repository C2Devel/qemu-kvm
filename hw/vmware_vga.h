#ifndef QEMU_VMWARE_VGA_H
#define QEMU_VMWARE_VGA_H

#include "qemu-common.h"

/* vmware_vga.c */
#ifdef CONFIG_VMWARE_VGA
void pci_vmsvga_init(PCIBus *bus);
#else
#define pci_vmsvga_init(bus) do { \
		fprintf(stderr, "%s: vmware_vga support is not compiled in\n", __FUNCTION__); \
	} while (0)
#endif

#endif
