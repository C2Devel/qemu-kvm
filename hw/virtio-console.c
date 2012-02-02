/*
 * Virtio Console and Generic Serial Port Devices
 *
 * Copyright Red Hat, Inc. 2009, 2010
 *
 * Authors:
 *  Amit Shah <amit.shah@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2.  See
 * the COPYING file in the top-level directory.
 */

#include "qemu-char.h"
#include "qemu-error.h"
#include "virtio-serial.h"

typedef struct VirtConsole {
    VirtIOSerialPort port;
    CharDriverState *chr;
} VirtConsole;

/*
 * Callback function that's called from chardevs when backend becomes
 * writable.
 */
static void chr_write_unblocked(void *opaque)
{
    VirtConsole *vcon = opaque;

    virtio_serial_throttle_port(&vcon->port, false);
}

/* Callback function that's called when the guest sends us data */
static ssize_t flush_buf(VirtIOSerialPort *port, const uint8_t *buf, size_t len)
{
    VirtConsole *vcon = DO_UPCAST(VirtConsole, port, port);
    ssize_t ret;

    ret = qemu_chr_write(vcon->chr, buf, len);
    if (ret < 0 && ret != -EAGAIN) {
        /*
         * Ideally we'd get a better error code than just -1, but
         * that's what the chardev interface gives us right now.  If
         * we had a finer-grained message, like -EPIPE, we could close
         * this connection.  Absent such error messages, the most we
         * can do is to return 0 here.
         *
         * This will prevent stray -1 values to go to
         * virtio-serial-bus.c and cause abort()s in
         * do_flush_queued_data().
         */
        ret = 0;
    }
    return ret;
}

/* Callback function that's called when the guest opens the port */
static void guest_open(VirtIOSerialPort *port)
{
    VirtConsole *vcon = DO_UPCAST(VirtConsole, port, port);

    return qemu_chr_guest_open(vcon->chr);
}

/* Callback function that's called when the guest closes the port */
static void guest_close(VirtIOSerialPort *port)
{
    VirtConsole *vcon = DO_UPCAST(VirtConsole, port, port);

    return qemu_chr_guest_close(vcon->chr);
}

/* Readiness of the guest to accept data on a port */
static int chr_can_read(void *opaque)
{
    VirtConsole *vcon = opaque;

    return virtio_serial_guest_ready(&vcon->port);
}

/* Send data from a char device over to the guest */
static void chr_read(void *opaque, const uint8_t *buf, int size)
{
    VirtConsole *vcon = opaque;

    virtio_serial_write(&vcon->port, buf, size);
}

static void chr_event(void *opaque, int event)
{
    VirtConsole *vcon = opaque;

    switch (event) {
    case CHR_EVENT_OPENED:
        virtio_serial_open(&vcon->port);
        break;
    case CHR_EVENT_CLOSED:
        virtio_serial_close(&vcon->port);
        break;
    }
}

static const QemuChrHandlers chr_handlers = {
    .fd_can_read = chr_can_read,
    .fd_read = chr_read,
    .fd_event = chr_event,
    .fd_write_unblocked = chr_write_unblocked,
};

static const QemuChrHandlers chr_handlers_no_flow_control = {
    .fd_can_read = chr_can_read,
    .fd_read = chr_read,
    .fd_event = chr_event,
};

static int generic_port_init(VirtConsole *vcon, VirtIOSerialDevice *dev)
{
    static const QemuChrHandlers *handlers;

    vcon->port.info = dev->info;

    if (vcon->chr) {
        handlers = &chr_handlers;
        if (!virtio_serial_flow_control_enabled(&vcon->port)) {
            handlers = &chr_handlers_no_flow_control;
        }
        qemu_chr_add_handlers(vcon->chr, handlers, vcon);
        vcon->port.info->have_data = flush_buf;
        vcon->port.info->guest_open = guest_open;
        vcon->port.info->guest_close = guest_close;
    }
    return 0;
}

/* Virtio Console Ports */
static int virtconsole_initfn(VirtIOSerialDevice *dev)
{
    VirtIOSerialPort *port = DO_UPCAST(VirtIOSerialPort, dev, &dev->qdev);
    VirtConsole *vcon = DO_UPCAST(VirtConsole, port, port);

    port->is_console = true;
    return generic_port_init(vcon, dev);
}

static int virtconsole_exitfn(VirtIOSerialDevice *dev)
{
    VirtIOSerialPort *port = DO_UPCAST(VirtIOSerialPort, dev, &dev->qdev);
    VirtConsole *vcon = DO_UPCAST(VirtConsole, port, port);

    if (vcon->chr) {
	/*
	 * Instead of closing the chardev, free it so it can be used
	 * for other purposes.
	 */
        qemu_chr_add_handlers(vcon->chr, NULL, NULL);
    }

    return 0;
}

static VirtIOSerialPortInfo virtconsole_info = {
    .qdev.name     = "virtconsole",
    .qdev.size     = sizeof(VirtConsole),
    .init          = virtconsole_initfn,
    .exit          = virtconsole_exitfn,
    .qdev.props = (Property[]) {
        DEFINE_PROP_UINT8("is_console", VirtConsole, port.is_console, 1),
        DEFINE_PROP_UINT32("nr", VirtConsole, port.id, VIRTIO_CONSOLE_BAD_ID),
        DEFINE_PROP_CHR("chardev", VirtConsole, chr),
        DEFINE_PROP_STRING("name", VirtConsole, port.name),
        DEFINE_PROP_END_OF_LIST(),
    },
};

static void virtconsole_register(void)
{
    virtio_serial_port_qdev_register(&virtconsole_info);
}
device_init(virtconsole_register)

/* Generic Virtio Serial Ports */
static int virtserialport_initfn(VirtIOSerialDevice *dev)
{
    VirtIOSerialPort *port = DO_UPCAST(VirtIOSerialPort, dev, &dev->qdev);
    VirtConsole *vcon = DO_UPCAST(VirtConsole, port, port);

    if (port->id == 0) {
        /*
         * Disallow a generic port at id 0, that's reserved for
         * console ports.
         */
        error_report("Port number 0 on virtio-serial devices reserved for virtconsole devices for backward compatibility.");
        return -1;
    }
    return generic_port_init(vcon, dev);
}

static VirtIOSerialPortInfo virtserialport_info = {
    .qdev.name     = "virtserialport",
    .qdev.size     = sizeof(VirtConsole),
    .init          = virtserialport_initfn,
    .exit          = virtconsole_exitfn,
    .qdev.props = (Property[]) {
        DEFINE_PROP_UINT32("nr", VirtConsole, port.id, VIRTIO_CONSOLE_BAD_ID),
        DEFINE_PROP_CHR("chardev", VirtConsole, chr),
        DEFINE_PROP_STRING("name", VirtConsole, port.name),
        DEFINE_PROP_END_OF_LIST(),
    },
};

static void virtserialport_register(void)
{
    virtio_serial_port_qdev_register(&virtserialport_info);
}
device_init(virtserialport_register)
