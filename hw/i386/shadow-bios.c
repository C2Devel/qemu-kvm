#include "qemu/osdep.h"
#include "sysemu/sysemu.h"
#include "target/i386/cpu.h"
#include "exec/ram_addr.h"
#include "qemu/cutils.h"

void shadow_bios(void)
{
    RAMBlock *block, *ram, *oprom, *bios;
    size_t one_meg, oprom_size, bios_size;
    uint8_t *cd_seg_host, *ef_seg_host;

    ram = NULL;
    oprom = NULL;
    bios = NULL;
    rcu_read_lock();
    QLIST_FOREACH_RCU(block, &ram_list.blocks, next) {
        if (strcmp("pc.ram", block->idstr) == 0) {
            assert(ram == NULL);
            ram = block;
        } else if (strcmp("pc.rom", block->idstr) == 0) {
            assert(oprom == NULL);
            oprom = block;
        } else if (strcmp("pc.bios", block->idstr) == 0) {
            assert(bios == NULL);
            bios = block;
        }
    }
    assert(ram != NULL);
    assert(oprom != NULL);
    assert(bios != NULL);
    assert(memory_region_is_ram(ram->mr));
    assert(memory_region_is_ram(oprom->mr));
    assert(memory_region_is_ram(bios->mr));
    assert(int128_eq(ram->mr->size, int128_make64(ram->used_length)));
    assert(int128_eq(oprom->mr->size, int128_make64(oprom->used_length)));
    assert(int128_eq(bios->mr->size, int128_make64(bios->used_length)));

    one_meg = 1024 * 1024;
    oprom_size = 128 * 1024;
    bios_size = 128 * 1024;
    assert(ram->used_length >= one_meg);
    assert(oprom->used_length == oprom_size);
    assert(bios->used_length == bios_size);

    ef_seg_host = memory_region_get_ram_ptr(ram->mr) + (one_meg - bios_size);
    cd_seg_host = ef_seg_host - oprom_size;

    /* This is a crude hack, but we must distinguish a rhel6.x.0 machtype guest
     * coming in from a RHEL-6 emulator (where shadowing has had no effect on
     * "pc.ram") from a similar guest coming in from a RHEL-7 emulator (where
     * shadowing has worked). In the latter case we must not trample the live
     * SeaBIOS variables in "pc.ram".
     */
    if (buffer_is_zero(ef_seg_host, bios_size)) {
        fprintf(stderr, "copying E and F segments from pc.bios to pc.ram\n");
        memcpy(ef_seg_host, memory_region_get_ram_ptr(bios->mr), bios_size);
    }
    if (buffer_is_zero(cd_seg_host, oprom_size)) {
        fprintf(stderr, "copying C and D segments from pc.rom to pc.ram\n");
        memcpy(cd_seg_host, memory_region_get_ram_ptr(oprom->mr), oprom_size);
    }
    rcu_read_unlock();
}
