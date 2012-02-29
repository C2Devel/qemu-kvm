/*
 * QEMU 8253/8254 interval timer emulation
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

#ifndef HW_I8254_H
#define HW_I8254_H

#include "kvm.h"

#define PIT_SAVEVM_NAME "i8254"
#define PIT_SAVEVM_VERSION 2

#define RW_STATE_LSB 1
#define RW_STATE_MSB 2
#define RW_STATE_WORD0 3
#define RW_STATE_WORD1 4

#define PIT_FLAGS_HPET_LEGACY  1

typedef struct PITChannelState {
    int count; /* can be 65536 */
    uint16_t latched_count;
    uint8_t count_latched;
    uint8_t status_latched;
    uint8_t status;
    uint8_t read_state;
    uint8_t write_state;
    uint8_t write_latch;
    uint8_t rw_mode;
    uint8_t mode;
    uint8_t bcd; /* not supported */
    uint8_t gate; /* timer start */
    int64_t count_load_time;
    /* irq handling */
    int64_t next_transition_time;
    QEMUTimer *irq_timer;
    qemu_irq irq;
    uint32_t irq_disabled;
} PITChannelState;

struct PITState {
    ISADevice dev;
    MemoryRegion ioports;
    uint32_t iobase;
    PITChannelState channels[3];
};

void pit_save(QEMUFile *f, void *opaque);

int pit_load(QEMUFile *f, void *opaque, int version_id);

typedef struct PITState PITState;

/* i8254-kvm.c */
void kvm_pit_init(PITState *pit);

#define PIT_FREQ 1193182

static inline ISADevice *pit_init(ISABus *bus, int base, int isa_irq,
                                  qemu_irq alt_irq)
{
    ISADevice *dev;

    dev = isa_create(bus, "isa-pit");
    qdev_prop_set_uint32(&dev->qdev, "iobase", base);
    qdev_init_nofail(&dev->qdev);

    if (kvm_enabled() && kvm_irqchip_in_kernel()) {
        return dev;
    }

    qdev_connect_gpio_out(&dev->qdev, 0,
                          isa_irq >= 0 ? isa_get_irq(dev, isa_irq) : alt_irq);

    return dev;
}

void pit_set_gate(ISADevice *dev, int channel, int val);
int pit_get_gate(ISADevice *dev, int channel);
int pit_get_initial_count(ISADevice *dev, int channel);
int pit_get_mode(ISADevice *dev, int channel);
int pit_get_out(ISADevice *dev, int channel, int64_t current_time);

#endif /* !HW_I8254_H */
