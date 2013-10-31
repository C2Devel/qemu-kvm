/*
 * QEMU simulated pvpanic device.
 *
 * Copyright Red Hat, Inc. 2013
 * Copyright Fujitsu, Corp. 2013
 *
 * Authors:
 *     Laszlo Ersek <lersek@redhat.com> (RHEL-6 port)
 *     Wen Congyang <wency@cn.fujitsu.com>
 *     Hu Tao <hutao@cn.fujitsu.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 *
 */

#include "qobject.h"
#include "qjson.h"
#include "monitor.h"
#include "sysemu.h"
#include "qemu-log.h"

#include "hw/fw_cfg.h"

/* The bit of supported pv event */
#define PVPANIC_F_PANICKED      0

/* The pv event value */
#define PVPANIC_PANICKED        (1 << PVPANIC_F_PANICKED)


static void panicked_mon_event(const char *action)
{
    QObject *data;

    data = qobject_from_jsonf("{ 'action': %s }", action);
    monitor_protocol_event(QEVENT_GUEST_PANICKED, data);
    qobject_decref(data);
}

static void handle_event(int event)
{
    static bool logged;

    if (event & ~PVPANIC_PANICKED && !logged) {
        qemu_log("pvpanic: unknown event %#x.\n", event);
        logged = true;
    }

    if (event & PVPANIC_PANICKED) {
        panicked_mon_event("pause");
        vm_stop(RUN_STATE_GUEST_PANICKED);
        return;
    }
}

#include "hw/isa.h"

typedef struct PVPanicState {
    ISADevice isa_dev;
    uint16_t ioport;
} PVPanicState;

/* return supported events on read */
static uint32_t pvpanic_ioport_read(void *opaque, uint32_t address)
{
    return PVPANIC_PANICKED;
}

static void pvpanic_ioport_write(void *opaque, uint32_t address, uint32_t data)
{
    handle_event(data);
}

static int pvpanic_isa_init(ISADevice *dev)
{
    PVPanicState *s = DO_UPCAST(PVPanicState, isa_dev, dev);
    static bool port_configured;

    register_ioport_read(s->ioport, 1, 1, &pvpanic_ioport_read, s);
    register_ioport_write(s->ioport, 1, 1, &pvpanic_ioport_write, s);

    if (!port_configured && fw_get_global()) {
        fw_cfg_add_file(fw_get_global(), "etc/pvpanic-port",
                        g_memdup(&s->ioport, sizeof(s->ioport)),
                        sizeof(s->ioport));
        port_configured = true;
    }

    return 0;
}

static ISADeviceInfo pvpanic_isa_info = {
    .qdev.name     = "pvpanic",
    .qdev.size     = sizeof(PVPanicState),
    .qdev.props = (Property[]) {
        DEFINE_PROP_UINT16("ioport", PVPanicState, ioport, 0x505),
        DEFINE_PROP_END_OF_LIST()
    },
    .init          = &pvpanic_isa_init
};

static void pvpanic_devices(void)
{
    isa_qdev_register(&pvpanic_isa_info);
}

device_init(pvpanic_devices)
