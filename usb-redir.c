/*
 * USB redirector usb-guest
 *
 * Copyright (c) 2011-2012 Red Hat, Inc.
 *
 * Red Hat Authors:
 * Hans de Goede <hdegoede@redhat.com>
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

#include "qemu-common.h"
#include "qemu-timer.h"
#include "monitor.h"
#include "sysemu.h"

#include <dirent.h>
#include <sys/ioctl.h>
#include <signal.h>
#include <usbredirparser.h>
#include <usbredirfilter.h>

#include "hw/usb.h"

#define MAX_ENDPOINTS 32
#define NO_INTERFACE_INFO 255 /* Valid interface_count always <= 32 */
#define EP2I(ep_address) (((ep_address & 0x80) >> 3) | (ep_address & 0x0f))
#define I2EP(i) (((i & 0x10) << 3) | (i & 0x0f))

typedef struct AsyncURB AsyncURB;
typedef struct USBRedirDevice USBRedirDevice;

/* Struct to hold buffered packets (iso or int input packets) */
struct buf_packet {
    uint8_t *data;
    int len;
    int status;
    QTAILQ_ENTRY(buf_packet)next;
};

struct endp_data {
    uint8_t type;
    uint8_t interval;
    uint8_t interface; /* bInterfaceNumber this ep belongs to */
    uint16_t max_packet_size; /* In bytes, not wMaxPacketSize format !! */
    uint8_t iso_started;
    uint8_t iso_error; /* For reporting iso errors to the HC */
    uint8_t interrupt_started;
    uint8_t interrupt_error;
    uint8_t bufpq_prefilled;
    uint8_t bufpq_dropping_packets;
    QTAILQ_HEAD(, buf_packet) bufpq;
    int32_t bufpq_size;
    int32_t bufpq_target_size;
};

struct PacketIdQueueEntry {
    uint64_t id;
    QTAILQ_ENTRY(PacketIdQueueEntry)next;
};

struct PacketIdQueue {
    USBRedirDevice *dev;
    const char *name;
    QTAILQ_HEAD(, PacketIdQueueEntry) head;
    int size;
};

struct USBRedirDevice {
    USBDevice dev;
    /* Properties */
    CharDriverState *cs;
    uint8_t debug;
    char *filter_str;
    /* Data passed from chardev the fd_read cb to the usbredirparser read cb */
    const uint8_t *read_buf;
    int read_buf_size;
    /* For async handling of close */
    QEMUBH *chardev_close_bh;
    /* To delay the usb attach in case of quick chardev close + open */
    QEMUTimer *attach_timer;
    int64_t next_attach_time;
    struct usbredirparser *parser;
    struct endp_data endpoint[MAX_ENDPOINTS];
    QTAILQ_HEAD(, AsyncURB) asyncq;
    struct PacketIdQueue cancelled;
    struct PacketIdQueue already_in_flight;
    /* Data for device filtering */
    struct usb_redir_device_connect_header device_info;
    struct usb_redir_interface_info_header interface_info;
    struct usbredirfilter_rule *filter_rules;
    int filter_rules_count;
};

struct AsyncURB {
    USBPacket *packet;
    QTAILQ_ENTRY(AsyncURB)next;
};

static void usbredir_hello(void *priv, struct usb_redir_hello_header *h);
static void usbredir_device_connect(void *priv,
    struct usb_redir_device_connect_header *device_connect);
static void usbredir_device_disconnect(void *priv);
static void usbredir_interface_info(void *priv,
    struct usb_redir_interface_info_header *interface_info);
static void usbredir_ep_info(void *priv,
    struct usb_redir_ep_info_header *ep_info);
static void usbredir_configuration_status(void *priv, uint64_t id,
    struct usb_redir_configuration_status_header *configuration_status);
static void usbredir_alt_setting_status(void *priv, uint64_t id,
    struct usb_redir_alt_setting_status_header *alt_setting_status);
static void usbredir_iso_stream_status(void *priv, uint64_t id,
    struct usb_redir_iso_stream_status_header *iso_stream_status);
static void usbredir_interrupt_receiving_status(void *priv, uint64_t id,
    struct usb_redir_interrupt_receiving_status_header
    *interrupt_receiving_status);
static void usbredir_bulk_streams_status(void *priv, uint64_t id,
    struct usb_redir_bulk_streams_status_header *bulk_streams_status);
static void usbredir_control_packet(void *priv, uint64_t id,
    struct usb_redir_control_packet_header *control_packet,
    uint8_t *data, int data_len);
static void usbredir_bulk_packet(void *priv, uint64_t id,
    struct usb_redir_bulk_packet_header *bulk_packet,
    uint8_t *data, int data_len);
static void usbredir_iso_packet(void *priv, uint64_t id,
    struct usb_redir_iso_packet_header *iso_packet,
    uint8_t *data, int data_len);
static void usbredir_interrupt_packet(void *priv, uint64_t id,
    struct usb_redir_interrupt_packet_header *interrupt_header,
    uint8_t *data, int data_len);

static int usbredir_handle_status(USBRedirDevice *dev,
                                       int status, int actual_len);

#define VERSION "qemu usb-redir guest " QEMU_VERSION

/*
 * Logging stuff
 */

#define ERROR(...) \
    do { \
        if (dev->debug >= usbredirparser_error) { \
            error_report("usb-redir error: " __VA_ARGS__); \
        } \
    } while (0)
#define WARNING(...) \
    do { \
        if (dev->debug >= usbredirparser_warning) { \
            error_report("usb-redir warning: " __VA_ARGS__); \
        } \
    } while (0)
#define INFO(...) \
    do { \
        if (dev->debug >= usbredirparser_info) { \
            error_report("usb-redir: " __VA_ARGS__); \
        } \
    } while (0)
#define DPRINTF(...) \
    do { \
        if (dev->debug >= usbredirparser_debug) { \
            error_report("usb-redir: " __VA_ARGS__); \
        } \
    } while (0)
#define DPRINTF2(...) \
    do { \
        if (dev->debug >= usbredirparser_debug_data) { \
            error_report("usb-redir: " __VA_ARGS__); \
        } \
    } while (0)

static void usbredir_log(void *priv, int level, const char *msg)
{
    USBRedirDevice *dev = priv;

    if (dev->debug < level) {
        return;
    }

    error_report("%s\n", msg);
}

static void usbredir_log_data(USBRedirDevice *dev, const char *desc,
    const uint8_t *data, int len)
{
    int i, j, n;

    if (dev->debug < usbredirparser_debug_data) {
        return;
    }

    for (i = 0; i < len; i += j) {
        char buf[128];

        n = sprintf(buf, "%s", desc);
        for (j = 0; j < 8 && i + j < len; j++) {
            n += sprintf(buf + n, " %02X", data[i + j]);
        }
        error_report("%s\n", buf);
    }
}

/*
 * usbredirparser io functions
 */

static int usbredir_read(void *priv, uint8_t *data, int count)
{
    USBRedirDevice *dev = priv;

    if (dev->read_buf_size < count) {
        count = dev->read_buf_size;
    }

    memcpy(data, dev->read_buf, count);

    dev->read_buf_size -= count;
    if (dev->read_buf_size) {
        dev->read_buf += count;
    } else {
        dev->read_buf = NULL;
    }

    return count;
}

static int usbredir_write(void *priv, uint8_t *data, int count)
{
    USBRedirDevice *dev = priv;
    int r;

    if (!dev->cs->opened || dev->cs->write_blocked) {
        return 0;
    }

    /* Don't send new data to the chardev until our state is fully synced */
    if (!runstate_check(RUN_STATE_RUNNING)) {
        return 0;
    }

    r = qemu_chr_write(dev->cs, data, count);

    if (r < 0) {
        if (dev->cs->write_blocked) {
            return 0;
        }
        return -1;
    }

    return r;
}

/*
 * Async, cancelled and buffered packets helpers
 */

static void async_alloc(USBRedirDevice *dev, USBPacket *p)
{
    AsyncURB *aurb = (AsyncURB *) qemu_mallocz(sizeof(AsyncURB));
    aurb->packet = p;
    QTAILQ_INSERT_TAIL(&dev->asyncq, aurb, next);
}

static void async_free(USBRedirDevice *dev, AsyncURB *aurb)
{
    QTAILQ_REMOVE(&dev->asyncq, aurb, next);
    qemu_free(aurb);
}

static AsyncURB *async_find_by_packet(USBRedirDevice *dev, USBPacket *p)
{
    AsyncURB *aurb;

    QTAILQ_FOREACH(aurb, &dev->asyncq, next) {
        if (aurb->packet == p) {
            return aurb;
        }
    }
    ERROR("could not find async urb for packet %p id %"PRIu64"\n", p, p->id);
    return NULL;
}

static void packet_id_queue_init(struct PacketIdQueue *q,
    USBRedirDevice *dev, const char *name)
{
    q->dev = dev;
    q->name = name;
    QTAILQ_INIT(&q->head);
    q->size = 0;
}

static void packet_id_queue_add(struct PacketIdQueue *q, uint64_t id)
{
    USBRedirDevice *dev = q->dev;
    struct PacketIdQueueEntry *e;

    DPRINTF("adding packet id %"PRIu64" to %s queue\n", id, q->name);

    e = qemu_mallocz(sizeof(struct PacketIdQueueEntry));
    e->id = id;
    QTAILQ_INSERT_TAIL(&q->head, e, next);
    q->size++;
}

static int packet_id_queue_remove(struct PacketIdQueue *q, uint64_t id)
{
    USBRedirDevice *dev = q->dev;
    struct PacketIdQueueEntry *e;

    QTAILQ_FOREACH(e, &q->head, next) {
        if (e->id == id) {
            DPRINTF("removing packet id %"PRIu64" from %s queue\n",
                    id, q->name);
            QTAILQ_REMOVE(&q->head, e, next);
            q->size--;
            qemu_free(e);
            return 1;
        }
    }
    return 0;
}

static void packet_id_queue_empty(struct PacketIdQueue *q)
{
    USBRedirDevice *dev = q->dev;
    struct PacketIdQueueEntry *e, *next_e;

    DPRINTF("removing %d packet-ids from %s queue\n", q->size, q->name);

    QTAILQ_FOREACH_SAFE(e, &q->head, next, next_e) {
        QTAILQ_REMOVE(&q->head, e, next);
        qemu_free(e);
    }
    q->size = 0;
}

static void usbredir_cancel_packet(USBDevice *udev, USBPacket *p)
{
    USBRedirDevice *dev = DO_UPCAST(USBRedirDevice, dev, udev);
    AsyncURB *aurb;

    aurb = async_find_by_packet(dev, p);
    if (aurb == NULL) {
        ERROR("could not cancel packet with id %"PRIu64"\n", p->id);
        return;
    }

    packet_id_queue_add(&dev->cancelled, aurb->packet->id);
    usbredirparser_send_cancel_data_packet(dev->parser, aurb->packet->id);
    usbredirparser_do_write(dev->parser);

    async_free(dev, aurb);
}

static int usbredir_is_cancelled(USBRedirDevice *dev, uint64_t id)
{
    if (!dev->dev.attached) {
        return 1; /* Treat everything as cancelled after a disconnect */
    }

    return packet_id_queue_remove(&dev->cancelled, id);
}

static void usbredir_fill_already_in_flight(USBRedirDevice *dev)
{
    AsyncURB *aurb;

    QTAILQ_FOREACH(aurb, &dev->asyncq, next) {
        packet_id_queue_add(&dev->already_in_flight, aurb->packet->id);
    }
}

static int usbredir_already_in_flight(USBRedirDevice *dev, USBPacket *p)
{
    if (packet_id_queue_remove(&dev->already_in_flight, p->id)) {
        /* RHEL-6: so that we can find the packet when we get the completion */
        async_alloc(dev, p);
        return 1;
    }
    return 0;
}

static AsyncURB *async_find(USBRedirDevice *dev, uint64_t id)
{
    AsyncURB *aurb;

    if (usbredir_is_cancelled(dev, id)) {
        return NULL;
    }

    QTAILQ_FOREACH(aurb, &dev->asyncq, next) {
        if (aurb->packet->id == id) {
            return aurb;
        }
    }
    ERROR("could not find async urb for id %"PRIu64"\n", id);
    return NULL;
}

static void bufp_alloc(USBRedirDevice *dev,
    uint8_t *data, int len, int status, uint8_t ep)
{
    struct buf_packet *bufp;

    if (!dev->endpoint[EP2I(ep)].bufpq_dropping_packets &&
        dev->endpoint[EP2I(ep)].bufpq_size >
            2 * dev->endpoint[EP2I(ep)].bufpq_target_size) {
        DPRINTF("bufpq overflow, dropping packets ep %02X\n", ep);
        dev->endpoint[EP2I(ep)].bufpq_dropping_packets = 1;
    }
    /* Since we're interupting the stream anyways, drop enough packets to get
       back to our target buffer size */
    if (dev->endpoint[EP2I(ep)].bufpq_dropping_packets) {
        if (dev->endpoint[EP2I(ep)].bufpq_size >
                dev->endpoint[EP2I(ep)].bufpq_target_size) {
            free(data);
            return;
        }
        dev->endpoint[EP2I(ep)].bufpq_dropping_packets = 0;
    }

    bufp = qemu_malloc(sizeof(struct buf_packet));
    bufp->data   = data;
    bufp->len    = len;
    bufp->status = status;
    QTAILQ_INSERT_TAIL(&dev->endpoint[EP2I(ep)].bufpq, bufp, next);
    dev->endpoint[EP2I(ep)].bufpq_size++;
}

static void bufp_free(USBRedirDevice *dev, struct buf_packet *bufp,
    uint8_t ep)
{
    QTAILQ_REMOVE(&dev->endpoint[EP2I(ep)].bufpq, bufp, next);
    dev->endpoint[EP2I(ep)].bufpq_size--;
    free(bufp->data);
    qemu_free(bufp);
}

static void usbredir_free_bufpq(USBRedirDevice *dev, uint8_t ep)
{
    struct buf_packet *buf, *buf_next;

    QTAILQ_FOREACH_SAFE(buf, &dev->endpoint[EP2I(ep)].bufpq, next, buf_next) {
        bufp_free(dev, buf, ep);
    }
}

/*
 * USBDevice callbacks
 */

static void usbredir_handle_reset(USBDevice *udev)
{
    USBRedirDevice *dev = DO_UPCAST(USBRedirDevice, dev, udev);

    DPRINTF("reset device\n");
    usbredirparser_send_reset(dev->parser);
    usbredirparser_do_write(dev->parser);
}

static int usbredir_handle_iso_data(USBRedirDevice *dev, USBPacket *p,
                                     uint8_t ep)
{
    int status, len;
    if (!dev->endpoint[EP2I(ep)].iso_started &&
            !dev->endpoint[EP2I(ep)].iso_error) {
        struct usb_redir_start_iso_stream_header start_iso = {
            .endpoint = ep,
        };
        int pkts_per_sec;

        if (dev->dev.speed == USB_SPEED_HIGH) {
            pkts_per_sec = 8000 / dev->endpoint[EP2I(ep)].interval;
        } else {
            pkts_per_sec = 1000 / dev->endpoint[EP2I(ep)].interval;
        }
        /* Testing has shown that we need circa 60 ms buffer */
        dev->endpoint[EP2I(ep)].bufpq_target_size = (pkts_per_sec * 60) / 1000;

        /* Aim for approx 100 interrupts / second on the client to
           balance latency and interrupt load */
        start_iso.pkts_per_urb = pkts_per_sec / 100;
        if (start_iso.pkts_per_urb < 1) {
            start_iso.pkts_per_urb = 1;
        } else if (start_iso.pkts_per_urb > 32) {
            start_iso.pkts_per_urb = 32;
        }

        start_iso.no_urbs = (dev->endpoint[EP2I(ep)].bufpq_target_size +
                             start_iso.pkts_per_urb - 1) /
                            start_iso.pkts_per_urb;
        /* Output endpoints pre-fill only 1/2 of the packets, keeping the rest
           as overflow buffer. Also see the usbredir protocol documentation */
        if (!(ep & USB_DIR_IN)) {
            start_iso.no_urbs *= 2;
        }
        if (start_iso.no_urbs > 16) {
            start_iso.no_urbs = 16;
        }

        /* No id, we look at the ep when receiving a status back */
        usbredirparser_send_start_iso_stream(dev->parser, 0, &start_iso);
        usbredirparser_do_write(dev->parser);
        DPRINTF("iso stream started pkts/sec %d pkts/urb %d urbs %d ep %02X\n",
                pkts_per_sec, start_iso.pkts_per_urb, start_iso.no_urbs, ep);
        dev->endpoint[EP2I(ep)].iso_started = 1;
        dev->endpoint[EP2I(ep)].bufpq_prefilled = 0;
        dev->endpoint[EP2I(ep)].bufpq_dropping_packets = 0;
    }

    if (ep & USB_DIR_IN) {
        struct buf_packet *isop;

        if (dev->endpoint[EP2I(ep)].iso_started &&
                !dev->endpoint[EP2I(ep)].bufpq_prefilled) {
            if (dev->endpoint[EP2I(ep)].bufpq_size <
                    dev->endpoint[EP2I(ep)].bufpq_target_size) {
                return usbredir_handle_status(dev, 0, 0);
            }
            dev->endpoint[EP2I(ep)].bufpq_prefilled = 1;
        }

        isop = QTAILQ_FIRST(&dev->endpoint[EP2I(ep)].bufpq);
        if (isop == NULL) {
            DPRINTF("iso-token-in ep %02X, no isop, iso_error: %d\n",
                    ep, dev->endpoint[EP2I(ep)].iso_error);
            /* Re-fill the buffer */
            dev->endpoint[EP2I(ep)].bufpq_prefilled = 0;
            /* Check iso_error for stream errors, otherwise its an underrun */
            status = dev->endpoint[EP2I(ep)].iso_error;
            dev->endpoint[EP2I(ep)].iso_error = 0;
            return status ? USB_RET_IOERROR : 0;
        }
        DPRINTF2("iso-token-in ep %02X status %d len %d queue-size: %d\n", ep,
                 isop->status, isop->len, dev->endpoint[EP2I(ep)].bufpq_size);

        status = isop->status;
        if (status != usb_redir_success) {
            bufp_free(dev, isop, ep);
            return USB_RET_IOERROR;
        }

        len = isop->len;
        if (len > p->len) {
            ERROR("received iso data is larger then packet ep %02X (%d > %d)\n",
                  ep, len, (int)p->len);
            bufp_free(dev, isop, ep);
            return USB_RET_BABBLE;
        }
        memcpy(p->data, isop->data, len);
        bufp_free(dev, isop, ep);
        return len;
    } else {
        /* If the stream was not started because of a pending error don't
           send the packet to the usb-host */
        if (dev->endpoint[EP2I(ep)].iso_started) {
            struct usb_redir_iso_packet_header iso_packet = {
                .endpoint = ep,
                .length = p->len
            };
            /* No id, we look at the ep when receiving a status back */
            usbredirparser_send_iso_packet(dev->parser, 0, &iso_packet,
                                           p->data, p->len);
            usbredirparser_do_write(dev->parser);
        }
        status = dev->endpoint[EP2I(ep)].iso_error;
        dev->endpoint[EP2I(ep)].iso_error = 0;
        DPRINTF2("iso-token-out ep %02X status %d len %d\n", ep, status,
                 p->len);
        return usbredir_handle_status(dev, status, p->len);
    }
}

static void usbredir_stop_iso_stream(USBRedirDevice *dev, uint8_t ep)
{
    struct usb_redir_stop_iso_stream_header stop_iso_stream = {
        .endpoint = ep
    };
    if (dev->endpoint[EP2I(ep)].iso_started) {
        usbredirparser_send_stop_iso_stream(dev->parser, 0, &stop_iso_stream);
        DPRINTF("iso stream stopped ep %02X\n", ep);
        dev->endpoint[EP2I(ep)].iso_started = 0;
    }
    dev->endpoint[EP2I(ep)].iso_error = 0;
    usbredir_free_bufpq(dev, ep);
}

static int usbredir_handle_bulk_data(USBRedirDevice *dev, USBPacket *p,
                                      uint8_t ep)
{
    struct usb_redir_bulk_packet_header bulk_packet;

    DPRINTF("bulk-out ep %02X len %d id %"PRIu64"\n", ep, p->len, p->id);

    if (usbredir_already_in_flight(dev, p)) {
        return USB_RET_ASYNC;
    }

    async_alloc(dev, p);

    bulk_packet.endpoint  = ep;
    bulk_packet.length    = p->len;
    bulk_packet.stream_id = 0;

    if (ep & USB_DIR_IN) {
        usbredirparser_send_bulk_packet(dev->parser, p->id,
                                        &bulk_packet, NULL, 0);
    } else {
        usbredir_log_data(dev, "bulk data out:", p->data, p->len);
        usbredirparser_send_bulk_packet(dev->parser, p->id,
                                        &bulk_packet, p->data, p->len);
    }
    usbredirparser_do_write(dev->parser);
    return USB_RET_ASYNC;
}

static int usbredir_handle_interrupt_data(USBRedirDevice *dev,
                                           USBPacket *p, uint8_t ep)
{
    if (ep & USB_DIR_IN) {
        /* Input interrupt endpoint, buffered packet input */
        struct buf_packet *intp;
        int status, len;

        if (!dev->endpoint[EP2I(ep)].interrupt_started &&
                !dev->endpoint[EP2I(ep)].interrupt_error) {
            struct usb_redir_start_interrupt_receiving_header start_int = {
                .endpoint = ep,
            };
            /* No id, we look at the ep when receiving a status back */
            usbredirparser_send_start_interrupt_receiving(dev->parser, 0,
                                                          &start_int);
            usbredirparser_do_write(dev->parser);
            DPRINTF("interrupt recv started ep %02X\n", ep);
            dev->endpoint[EP2I(ep)].interrupt_started = 1;
            /* We don't really want to drop interrupt packets ever, but
               having some upper limit to how much we buffer is good. */
            dev->endpoint[EP2I(ep)].bufpq_target_size = 1000;
            dev->endpoint[EP2I(ep)].bufpq_dropping_packets = 0;
        }

        intp = QTAILQ_FIRST(&dev->endpoint[EP2I(ep)].bufpq);
        if (intp == NULL) {
            DPRINTF2("interrupt-token-in ep %02X, no intp\n", ep);
            /* Check interrupt_error for stream errors */
            status = dev->endpoint[EP2I(ep)].interrupt_error;
            dev->endpoint[EP2I(ep)].interrupt_error = 0;
            if (status) {
                return usbredir_handle_status(dev, status, 0);
            }
            return USB_RET_NAK;
        }
        DPRINTF("interrupt-token-in ep %02X status %d len %d\n", ep,
                intp->status, intp->len);

        status = intp->status;
        if (status != usb_redir_success) {
            bufp_free(dev, intp, ep);
            return usbredir_handle_status(dev, status, 0);
        }

        len = intp->len;
        if (len > p->len) {
            ERROR("received int data is larger then packet ep %02X\n", ep);
            bufp_free(dev, intp, ep);
            return USB_RET_BABBLE;
        }
        memcpy(p->data, intp->data, len);
        bufp_free(dev, intp, ep);
        return len;
    } else {
        /* Output interrupt endpoint, normal async operation */
        struct usb_redir_interrupt_packet_header interrupt_packet;

        DPRINTF("interrupt-out ep %02X len %d id %"PRIu64"\n", ep, p->len,
                p->id);

        if (usbredir_already_in_flight(dev, p)) {
            return USB_RET_ASYNC;
        }

        async_alloc(dev, p);

        interrupt_packet.endpoint  = ep;
        interrupt_packet.length    = p->len;

        usbredir_log_data(dev, "interrupt data out:", p->data, p->len);
        usbredirparser_send_interrupt_packet(dev->parser, p->id,
                                        &interrupt_packet, p->data, p->len);
        usbredirparser_do_write(dev->parser);
        return USB_RET_ASYNC;
    }
}

static void usbredir_stop_interrupt_receiving(USBRedirDevice *dev,
    uint8_t ep)
{
    struct usb_redir_stop_interrupt_receiving_header stop_interrupt_recv = {
        .endpoint = ep
    };
    if (dev->endpoint[EP2I(ep)].interrupt_started) {
        usbredirparser_send_stop_interrupt_receiving(dev->parser, 0,
                                                     &stop_interrupt_recv);
        DPRINTF("interrupt recv stopped ep %02X\n", ep);
        dev->endpoint[EP2I(ep)].interrupt_started = 0;
    }
    dev->endpoint[EP2I(ep)].interrupt_error = 0;
    usbredir_free_bufpq(dev, ep);
}

static int usbredir_handle_data(USBDevice *udev, USBPacket *p)
{
    USBRedirDevice *dev = DO_UPCAST(USBRedirDevice, dev, udev);
    uint8_t ep;

    ep = p->devep;
    if (p->pid == USB_TOKEN_IN) {
        ep |= USB_DIR_IN;
    }

    switch (dev->endpoint[EP2I(ep)].type) {
    case USB_ENDPOINT_XFER_CONTROL:
        ERROR("handle_data called for control transfer on ep %02X\n", ep);
        return USB_RET_NAK;
    case USB_ENDPOINT_XFER_ISOC:
        return usbredir_handle_iso_data(dev, p, ep);
    case USB_ENDPOINT_XFER_BULK:
        return usbredir_handle_bulk_data(dev, p, ep);;
    case USB_ENDPOINT_XFER_INT:
        return usbredir_handle_interrupt_data(dev, p, ep);;
    default:
        ERROR("handle_data ep %02X has unknown type %d\n", ep,
              dev->endpoint[EP2I(ep)].type);
        return USB_RET_NAK;
    }
}

static int usbredir_set_config(USBRedirDevice *dev, USBPacket *p,
                                int config)
{
    struct usb_redir_set_configuration_header set_config;
    int i;

    DPRINTF("set config %d id %"PRIu64"\n", config, p->id);

    async_alloc(dev, p);

    for (i = 0; i < MAX_ENDPOINTS; i++) {
        switch (dev->endpoint[i].type) {
        case USB_ENDPOINT_XFER_ISOC:
            usbredir_stop_iso_stream(dev, I2EP(i));
            break;
        case USB_ENDPOINT_XFER_INT:
            if (i & 0x10) {
                usbredir_stop_interrupt_receiving(dev, I2EP(i));
            }
            break;
        }
        usbredir_free_bufpq(dev, I2EP(i));
    }

    set_config.configuration = config;
    usbredirparser_send_set_configuration(dev->parser, p->id, &set_config);
    usbredirparser_do_write(dev->parser);
    return USB_RET_ASYNC;
}

static int usbredir_get_config(USBRedirDevice *dev, USBPacket *p)
{
    DPRINTF("get config id %"PRIu64"\n", p->id);

    async_alloc(dev, p);
    usbredirparser_send_get_configuration(dev->parser, p->id);
    usbredirparser_do_write(dev->parser);
    return USB_RET_ASYNC;
}

static int usbredir_set_interface(USBRedirDevice *dev, USBPacket *p,
                                   int interface, int alt)
{
    struct usb_redir_set_alt_setting_header set_alt;
    int i;

    DPRINTF("set interface %d alt %d id %"PRIu64"\n", interface, alt,
            p->id);

    async_alloc(dev, p);

    for (i = 0; i < MAX_ENDPOINTS; i++) {
        if (dev->endpoint[i].interface == interface) {
            switch (dev->endpoint[i].type) {
            case USB_ENDPOINT_XFER_ISOC:
                usbredir_stop_iso_stream(dev, I2EP(i));
                break;
            case USB_ENDPOINT_XFER_INT:
                if (i & 0x10) {
                    usbredir_stop_interrupt_receiving(dev, I2EP(i));
                }
                break;
            }
            usbredir_free_bufpq(dev, I2EP(i));
        }
    }

    set_alt.interface = interface;
    set_alt.alt = alt;
    usbredirparser_send_set_alt_setting(dev->parser, p->id, &set_alt);
    usbredirparser_do_write(dev->parser);
    return USB_RET_ASYNC;
}

static int usbredir_get_interface(USBRedirDevice *dev, USBPacket *p,
                                   int interface)
{
    struct usb_redir_get_alt_setting_header get_alt;

    DPRINTF("get interface %d id %"PRIu64"\n", interface, p->id);

    async_alloc(dev, p);
    get_alt.interface = interface;
    usbredirparser_send_get_alt_setting(dev->parser, p->id, &get_alt);
    usbredirparser_do_write(dev->parser);
    return USB_RET_ASYNC;
}

static int usbredir_handle_control(USBDevice *udev, USBPacket *p,
        int request, int value, int index, int length, uint8_t *data)
{
    USBRedirDevice *dev = DO_UPCAST(USBRedirDevice, dev, udev);
    struct usb_redir_control_packet_header control_packet;

    if (usbredir_already_in_flight(dev, p)) {
        return USB_RET_ASYNC;
    }

    /* Special cases for certain standard device requests */
    switch (request) {
    case DeviceOutRequest | USB_REQ_SET_ADDRESS:
        DPRINTF("set address %d\n", value);
        dev->dev.addr = value;
        return 0;
    case DeviceOutRequest | USB_REQ_SET_CONFIGURATION:
        return usbredir_set_config(dev, p, value & 0xff);
    case DeviceRequest | USB_REQ_GET_CONFIGURATION:
        return usbredir_get_config(dev, p);
    case InterfaceOutRequest | USB_REQ_SET_INTERFACE:
        return usbredir_set_interface(dev, p, index, value);
    case InterfaceRequest | USB_REQ_GET_INTERFACE:
        return usbredir_get_interface(dev, p, index);
    }

    /* "Normal" ctrl requests */
    async_alloc(dev, p);

    /* Note request is (bRequestType << 8) | bRequest */
    DPRINTF(
        "ctrl-out type 0x%x req 0x%x val 0x%x index %d len %d id %"PRIu64"\n",
        request >> 8, request & 0xff, value, index, length, p->id);

    control_packet.request     = request & 0xFF;
    control_packet.requesttype = request >> 8;
    control_packet.endpoint    = control_packet.requesttype & USB_DIR_IN;
    control_packet.value       = value;
    control_packet.index       = index;
    control_packet.length      = length;

    if (control_packet.requesttype & USB_DIR_IN) {
        usbredirparser_send_control_packet(dev->parser, p->id,
                                           &control_packet, NULL, 0);
    } else {
        usbredir_log_data(dev, "ctrl data out:", data, length);
        usbredirparser_send_control_packet(dev->parser, p->id,
                                           &control_packet, data, length);
    }
    usbredirparser_do_write(dev->parser);
    return USB_RET_ASYNC;
}

/*
 * Close events can be triggered by usbredirparser_do_write which gets called
 * from within the USBDevice data / control packet callbacks and doing a
 * usb_detach from within these callbacks is not a good idea.
 *
 * So we use a bh handler to take care of close events.
 */
static void usbredir_chardev_close_bh(void *opaque)
{
    USBRedirDevice *dev = opaque;

    usbredir_device_disconnect(dev);

    if (dev->parser) {
        DPRINTF("destroying usbredirparser\n");
        usbredirparser_destroy(dev->parser);
        dev->parser = NULL;
    }
}

static void usbredir_create_parser(USBRedirDevice *dev)
{
    uint32_t caps[USB_REDIR_CAPS_SIZE] = { 0, };
    int flags = 0;

    DPRINTF("creating usbredirparser\n");

    dev->parser = usbredirparser_create();
    if (dev->parser == NULL) {
        abort();
    }
    dev->parser->priv = dev;
    dev->parser->log_func = usbredir_log;
    dev->parser->read_func = usbredir_read;
    dev->parser->write_func = usbredir_write;
    dev->parser->hello_func = usbredir_hello;
    dev->parser->device_connect_func = usbredir_device_connect;
    dev->parser->device_disconnect_func = usbredir_device_disconnect;
    dev->parser->interface_info_func = usbredir_interface_info;
    dev->parser->ep_info_func = usbredir_ep_info;
    dev->parser->configuration_status_func = usbredir_configuration_status;
    dev->parser->alt_setting_status_func = usbredir_alt_setting_status;
    dev->parser->iso_stream_status_func = usbredir_iso_stream_status;
    dev->parser->interrupt_receiving_status_func =
        usbredir_interrupt_receiving_status;
    dev->parser->bulk_streams_status_func = usbredir_bulk_streams_status;
    dev->parser->control_packet_func = usbredir_control_packet;
    dev->parser->bulk_packet_func = usbredir_bulk_packet;
    dev->parser->iso_packet_func = usbredir_iso_packet;
    dev->parser->interrupt_packet_func = usbredir_interrupt_packet;
    dev->read_buf = NULL;
    dev->read_buf_size = 0;

    usbredirparser_caps_set_cap(caps, usb_redir_cap_connect_device_version);
    usbredirparser_caps_set_cap(caps, usb_redir_cap_filter);
    usbredirparser_caps_set_cap(caps, usb_redir_cap_ep_info_max_packet_size);
    usbredirparser_caps_set_cap(caps, usb_redir_cap_64bits_ids);

    if (runstate_check(RUN_STATE_INMIGRATE)) {
        flags |= usbredirparser_fl_no_hello;
    }
    usbredirparser_init(dev->parser, VERSION, caps, USB_REDIR_CAPS_SIZE,
                        flags);
    usbredirparser_do_write(dev->parser);
}

static void usbredir_reject_device(USBRedirDevice *dev)
{
    usbredir_device_disconnect(dev);
    if (usbredirparser_peer_has_cap(dev->parser, usb_redir_cap_filter)) {
        usbredirparser_send_filter_reject(dev->parser);
        usbredirparser_do_write(dev->parser);
    }
}

static void usbredir_do_attach(void *opaque)
{
    USBRedirDevice *dev = opaque;

    if (usb_device_attach(&dev->dev) != 0) {
        usbredir_reject_device(dev);
    }
}

/*
 * chardev callbacks
 */

static int usbredir_chardev_can_read(void *opaque)
{
    USBRedirDevice *dev = opaque;

    if (!dev->parser) {
        WARNING("chardev_can_read called on non open chardev!\n");
        return 0;
    }

    /* Don't read new data from the chardev until our state is fully synced */
    if (!runstate_check(RUN_STATE_RUNNING)) {
        return 0;
    }

    /* usbredir_parser_do_read will consume *all* data we give it */
    return 1024 * 1024;
}

static void usbredir_chardev_read(void *opaque, const uint8_t *buf, int size)
{
    USBRedirDevice *dev = opaque;

    /* No recursion allowed! */
    assert(dev->read_buf == NULL);

    dev->read_buf = buf;
    dev->read_buf_size = size;

    usbredirparser_do_read(dev->parser);
    /* Send any acks, etc. which may be queued now */
    usbredirparser_do_write(dev->parser);
}

static void usbredir_chardev_event(void *opaque, int event)
{
    USBRedirDevice *dev = opaque;

    switch (event) {
    case CHR_EVENT_OPENED:
        DPRINTF("chardev open\n");
        /* Make sure any pending closes are handled (no-op if none pending) */
        usbredir_chardev_close_bh(dev);
        qemu_bh_cancel(dev->chardev_close_bh);
        usbredir_create_parser(dev);
        break;
    case CHR_EVENT_CLOSED:
        DPRINTF("chardev close\n");
        qemu_bh_schedule(dev->chardev_close_bh);
        break;
    }
}

static void usbredir_chardev_write_unblocked(void *opaque)
{
    USBRedirDevice *dev = opaque;

    if (dev->parser == NULL) {
        /* usbredir_open_close_bh hasn't handled the open event yet */
        return;
    }
    usbredirparser_do_write(dev->parser);
}

/*
 * init + destroy
 */

static QemuChrHandlers usbredir_handlers = {
    .fd_can_read = usbredir_chardev_can_read,
    .fd_read = usbredir_chardev_read,
    .fd_event = usbredir_chardev_event,
    .fd_write_unblocked = usbredir_chardev_write_unblocked,
};

static void usbredir_vm_state_change(void *priv, int running, RunState state)
{
    USBRedirDevice *dev = priv;

    if (state == RUN_STATE_RUNNING && dev->parser != NULL) {
        usbredirparser_do_write(dev->parser); /* Flush any pending writes */
    }
}

static int usbredir_initfn(USBDevice *udev)
{
    USBRedirDevice *dev = DO_UPCAST(USBRedirDevice, dev, udev);
    int i;

    if (dev->cs == NULL) {
        qerror_report(QERR_MISSING_PARAMETER, "chardev");
        return -1;
    }

    if (dev->filter_str) {
        i = usbredirfilter_string_to_rules(dev->filter_str, ":", "|",
                                           &dev->filter_rules,
                                           &dev->filter_rules_count);
        if (i) {
            qerror_report(QERR_INVALID_PARAMETER_VALUE, "filter", "a usb device filter string");
            return -1;
        }
    }

    dev->chardev_close_bh = qemu_bh_new(usbredir_chardev_close_bh, dev);
    dev->attach_timer = qemu_new_timer(vm_clock, usbredir_do_attach, dev);

    QTAILQ_INIT(&dev->asyncq);
    packet_id_queue_init(&dev->cancelled, dev, "cancelled");
    packet_id_queue_init(&dev->already_in_flight, dev, "already-in-flight");
    for (i = 0; i < MAX_ENDPOINTS; i++) {
        QTAILQ_INIT(&dev->endpoint[i].bufpq);
    }

    /* We'll do the attach once we receive the speed from the usb-host */
    udev->auto_attach = 0;

    /* Let the backend know we are ready */
    qemu_chr_guest_open(dev->cs);
    qemu_chr_add_handlers(dev->cs, &usbredir_handlers, dev);

    qemu_add_vm_change_state_handler(usbredir_vm_state_change, dev);
    return 0;
}

static void usbredir_cleanup_device_queues(USBRedirDevice *dev)
{
    AsyncURB *aurb, *next_aurb;
    int i;

    QTAILQ_FOREACH_SAFE(aurb, &dev->asyncq, next, next_aurb) {
        async_free(dev, aurb);
    }
    packet_id_queue_empty(&dev->cancelled);
    packet_id_queue_empty(&dev->already_in_flight);
    for (i = 0; i < MAX_ENDPOINTS; i++) {
        usbredir_free_bufpq(dev, I2EP(i));
    }
}

static void usbredir_handle_destroy(USBDevice *udev)
{
    USBRedirDevice *dev = DO_UPCAST(USBRedirDevice, dev, udev);

    qemu_chr_guest_close(dev->cs);
    qemu_chr_close(dev->cs);
    /* Note must be done after qemu_chr_close, as that causes a close event */
    qemu_bh_delete(dev->chardev_close_bh);

    qemu_del_timer(dev->attach_timer);
    qemu_free_timer(dev->attach_timer);

    usbredir_cleanup_device_queues(dev);

    if (dev->parser) {
        usbredirparser_destroy(dev->parser);
    }

    free(dev->filter_rules);
}

static int usbredir_check_filter(USBRedirDevice *dev)
{
    if (dev->interface_info.interface_count == NO_INTERFACE_INFO) {
        ERROR("No interface info for device\n");
        goto error;
    }

    if (dev->filter_rules) {
        if (!usbredirparser_peer_has_cap(dev->parser,
                                    usb_redir_cap_connect_device_version)) {
            ERROR("Device filter specified and peer does not have the "
                  "connect_device_version capability\n");
            goto error;
        }

        if (usbredirfilter_check(
                dev->filter_rules,
                dev->filter_rules_count,
                dev->device_info.device_class,
                dev->device_info.device_subclass,
                dev->device_info.device_protocol,
                dev->interface_info.interface_class,
                dev->interface_info.interface_subclass,
                dev->interface_info.interface_protocol,
                dev->interface_info.interface_count,
                dev->device_info.vendor_id,
                dev->device_info.product_id,
                dev->device_info.device_version_bcd,
                0) != 0) {
            goto error;
        }
    }

    return 0;

error:
    usbredir_reject_device(dev);
    return -1;
}

/*
 * usbredirparser packet complete callbacks
 */

static int usbredir_handle_status(USBRedirDevice *dev,
                                       int status, int actual_len)
{
    switch (status) {
    case usb_redir_success:
        return actual_len;
    case usb_redir_stall:
        return USB_RET_STALL;
    case usb_redir_cancelled:
        /*
         * When the usbredir-host unredirects a device, it will report a status
         * of cancelled for all pending packets, followed by a disconnect msg.
         */
        return USB_RET_IOERROR;
    case usb_redir_inval:
        WARNING("got invalid param error from usb-host?\n");
        return USB_RET_IOERROR;
    case usb_redir_babble:
        return USB_RET_BABBLE;
    case usb_redir_ioerror:
    case usb_redir_timeout:
    default:
        return USB_RET_IOERROR;
    }
}

static void usbredir_hello(void *priv, struct usb_redir_hello_header *h)
{
    USBRedirDevice *dev = priv;

    /* Try to send the filter info now that we've the usb-host's caps */
    if (usbredirparser_peer_has_cap(dev->parser, usb_redir_cap_filter) &&
            dev->filter_rules) {
        usbredirparser_send_filter_filter(dev->parser, dev->filter_rules,
                                          dev->filter_rules_count);
        usbredirparser_do_write(dev->parser);
    }
}

static void usbredir_device_connect(void *priv,
    struct usb_redir_device_connect_header *device_connect)
{
    USBRedirDevice *dev = priv;
    const char *speed;

    if (qemu_timer_pending(dev->attach_timer) || dev->dev.attached) {
        ERROR("Received device connect while already connected\n");
        return;
    }

    switch (device_connect->speed) {
    case usb_redir_speed_low:
        speed = "low speed";
        dev->dev.speed = USB_SPEED_LOW;
        break;
    case usb_redir_speed_full:
        speed = "full speed";
        dev->dev.speed = USB_SPEED_FULL;
        break;
    case usb_redir_speed_high:
        speed = "high speed";
        dev->dev.speed = USB_SPEED_HIGH;
        break;
    case usb_redir_speed_super:
        speed = "super speed";
        dev->dev.speed = USB_SPEED_SUPER;
        break;
    default:
        speed = "unknown speed";
        dev->dev.speed = USB_SPEED_FULL;
    }

    if (usbredirparser_peer_has_cap(dev->parser,
                                    usb_redir_cap_connect_device_version)) {
        INFO("attaching %s device %04x:%04x version %d.%d class %02x\n",
             speed, device_connect->vendor_id, device_connect->product_id,
             ((device_connect->device_version_bcd & 0xf000) >> 12) * 10 +
             ((device_connect->device_version_bcd & 0x0f00) >>  8),
             ((device_connect->device_version_bcd & 0x00f0) >>  4) * 10 +
             ((device_connect->device_version_bcd & 0x000f) >>  0),
             device_connect->device_class);
    } else {
        INFO("attaching %s device %04x:%04x class %02x\n", speed,
             device_connect->vendor_id, device_connect->product_id,
             device_connect->device_class);
    }

    dev->dev.speedmask = (1 << dev->dev.speed);
    dev->device_info = *device_connect;

    if (usbredir_check_filter(dev)) {
        WARNING("Device %04x:%04x rejected by device filter, not attaching\n",
                device_connect->vendor_id, device_connect->product_id);
        return;
    }

    qemu_mod_timer(dev->attach_timer, dev->next_attach_time);
}

static void usbredir_device_disconnect(void *priv)
{
    USBRedirDevice *dev = priv;
    int i;

    /* Stop any pending attaches */
    qemu_del_timer(dev->attach_timer);

    if (dev->dev.attached) {
        DPRINTF("detaching device\n");
        usb_device_detach(&dev->dev);
        /*
         * Delay next usb device attach to give the guest a chance to see
         * see the detach / attach in case of quick close / open succession
         */
        dev->next_attach_time = qemu_get_clock(vm_clock)
            + get_ticks_per_sec() * 200 / 1000; /* 200 ms */
    }

    /* Reset state so that the next dev connected starts with a clean slate */
    usbredir_cleanup_device_queues(dev);
    memset(dev->endpoint, 0, sizeof(dev->endpoint));
    for (i = 0; i < MAX_ENDPOINTS; i++) {
        QTAILQ_INIT(&dev->endpoint[i].bufpq);
    }
    dev->interface_info.interface_count = NO_INTERFACE_INFO;
    dev->dev.addr = 0;
    dev->dev.speed = 0;
}

static void usbredir_interface_info(void *priv,
    struct usb_redir_interface_info_header *interface_info)
{
    USBRedirDevice *dev = priv;

    dev->interface_info = *interface_info;

    /*
     * If we receive interface info after the device has already been
     * connected (ie on a set_config), re-check the filter.
     */
    if (qemu_timer_pending(dev->attach_timer) || dev->dev.attached) {
        if (usbredir_check_filter(dev)) {
            ERROR("Device no longer matches filter after interface info "
                  "change, disconnecting!\n");
        }
    }
}

static void usbredir_ep_info(void *priv,
    struct usb_redir_ep_info_header *ep_info)
{
    USBRedirDevice *dev = priv;
    int i;

    for (i = 0; i < MAX_ENDPOINTS; i++) {
        dev->endpoint[i].type = ep_info->type[i];
        dev->endpoint[i].interval = ep_info->interval[i];
        dev->endpoint[i].interface = ep_info->interface[i];
        switch (dev->endpoint[i].type) {
        case usb_redir_type_invalid:
            break;
        case usb_redir_type_iso:
        case usb_redir_type_interrupt:
            if (dev->endpoint[i].interval == 0) {
                ERROR("Received 0 interval for isoc or irq endpoint\n");
                usbredir_device_disconnect(dev);
            }
            /* Fall through */
        case usb_redir_type_control:
        case usb_redir_type_bulk:
            DPRINTF("ep: %02X type: %d interface: %d\n", I2EP(i),
                    dev->endpoint[i].type, dev->endpoint[i].interface);
            break;
        default:
            ERROR("Received invalid endpoint type\n");
            usbredir_device_disconnect(dev);
        }
        if (usbredirparser_peer_has_cap(dev->parser,
                                     usb_redir_cap_ep_info_max_packet_size)) {
            dev->endpoint[i].max_packet_size = ep_info->max_packet_size[i];
        }
    }
}

static void usbredir_configuration_status(void *priv, uint64_t id,
    struct usb_redir_configuration_status_header *config_status)
{
    USBRedirDevice *dev = priv;
    AsyncURB *aurb;
    int len = 0;

    DPRINTF("set config status %d config %d id %"PRIu64"\n",
            config_status->status, config_status->configuration, id);

    aurb = async_find(dev, id);
    if (aurb) {
        if (dev->dev.setup_buf[0] & USB_DIR_IN) {
            dev->dev.data_buf[0] = config_status->configuration;
            len = 1;
        }
        aurb->packet->len =
            usbredir_handle_status(dev, config_status->status, len);
        usb_generic_async_ctrl_complete(&dev->dev, aurb->packet);
        async_free(dev, aurb);
    }
}

static void usbredir_alt_setting_status(void *priv, uint64_t id,
    struct usb_redir_alt_setting_status_header *alt_setting_status)
{
    USBRedirDevice *dev = priv;
    AsyncURB *aurb;
    int len = 0;

    DPRINTF("alt status %d intf %d alt %d id: %"PRIu64"\n",
            alt_setting_status->status, alt_setting_status->interface,
            alt_setting_status->alt, id);

    aurb = async_find(dev, id);
    if (aurb) {
        if (dev->dev.setup_buf[0] & USB_DIR_IN) {
            dev->dev.data_buf[0] = alt_setting_status->alt;
            len = 1;
        }
        aurb->packet->len =
            usbredir_handle_status(dev, alt_setting_status->status, len);
        usb_generic_async_ctrl_complete(&dev->dev, aurb->packet);
        async_free(dev, aurb);
    }
}

static void usbredir_iso_stream_status(void *priv, uint64_t id,
    struct usb_redir_iso_stream_status_header *iso_stream_status)
{
    USBRedirDevice *dev = priv;
    uint8_t ep = iso_stream_status->endpoint;

    DPRINTF("iso status %d ep %02X id %"PRIu64"\n", iso_stream_status->status,
            ep, id);

    if (!dev->dev.attached || !dev->endpoint[EP2I(ep)].iso_started) {
        return;
    }

    dev->endpoint[EP2I(ep)].iso_error = iso_stream_status->status;
    if (iso_stream_status->status == usb_redir_stall) {
        DPRINTF("iso stream stopped by peer ep %02X\n", ep);
        dev->endpoint[EP2I(ep)].iso_started = 0;
    }
}

static void usbredir_interrupt_receiving_status(void *priv, uint64_t id,
    struct usb_redir_interrupt_receiving_status_header
    *interrupt_receiving_status)
{
    USBRedirDevice *dev = priv;
    uint8_t ep = interrupt_receiving_status->endpoint;

    DPRINTF("interrupt recv status %d ep %02X id %"PRIu64"\n",
            interrupt_receiving_status->status, ep, id);

    if (!dev->dev.attached || !dev->endpoint[EP2I(ep)].interrupt_started) {
        return;
    }

    dev->endpoint[EP2I(ep)].interrupt_error =
        interrupt_receiving_status->status;
    if (interrupt_receiving_status->status == usb_redir_stall) {
        DPRINTF("interrupt receiving stopped by peer ep %02X\n", ep);
        dev->endpoint[EP2I(ep)].interrupt_started = 0;
    }
}

static void usbredir_bulk_streams_status(void *priv, uint64_t id,
    struct usb_redir_bulk_streams_status_header *bulk_streams_status)
{
}

static void usbredir_control_packet(void *priv, uint64_t id,
    struct usb_redir_control_packet_header *control_packet,
    uint8_t *data, int data_len)
{
    USBRedirDevice *dev = priv;
    int len = control_packet->length;
    AsyncURB *aurb;

    DPRINTF("ctrl-in status %d len %d id %"PRIu64"\n", control_packet->status,
            len, id);

    aurb = async_find(dev, id);
    if (aurb) {
        len = usbredir_handle_status(dev, control_packet->status, len);
        if (len > 0) {
            usbredir_log_data(dev, "ctrl data in:", data, data_len);
            if (data_len <= sizeof(dev->dev.data_buf)) {
                memcpy(dev->dev.data_buf, data, data_len);
            } else {
                ERROR("ctrl buffer too small (%d > %zu)\n",
                      data_len, sizeof(dev->dev.data_buf));
                len = USB_RET_STALL;
            }
        }
        aurb->packet->len = len;
        usb_generic_async_ctrl_complete(&dev->dev, aurb->packet);
        async_free(dev, aurb);
    }
    free(data);
}

static void usbredir_bulk_packet(void *priv, uint64_t id,
    struct usb_redir_bulk_packet_header *bulk_packet,
    uint8_t *data, int data_len)
{
    USBRedirDevice *dev = priv;
    uint8_t ep = bulk_packet->endpoint;
    int len = bulk_packet->length;
    AsyncURB *aurb;

    DPRINTF("bulk-in status %d ep %02X len %d id %"PRIu64"\n",
            bulk_packet->status, ep, len, id);

    aurb = async_find(dev, id);
    if (aurb) {
        len = usbredir_handle_status(dev, bulk_packet->status, len);
        if (len > 0) {
            usbredir_log_data(dev, "bulk data in:", data, data_len);
            if (data_len <= aurb->packet->len) {
                memcpy(aurb->packet->data, data, data_len);
            } else {
                ERROR("bulk got more data then requested (%d > %d)\n",
                      data_len, aurb->packet->len);
                len = USB_RET_BABBLE;
            }
        }
        aurb->packet->len = len;
        usb_packet_complete(&dev->dev, aurb->packet);
        async_free(dev, aurb);
    }
    free(data);
}

static void usbredir_iso_packet(void *priv, uint64_t id,
    struct usb_redir_iso_packet_header *iso_packet,
    uint8_t *data, int data_len)
{
    USBRedirDevice *dev = priv;
    uint8_t ep = iso_packet->endpoint;

    DPRINTF2("iso-in status %d ep %02X len %d id %"PRIu64"\n",
             iso_packet->status, ep, data_len, id);

    if (dev->endpoint[EP2I(ep)].type != USB_ENDPOINT_XFER_ISOC) {
        ERROR("received iso packet for non iso endpoint %02X\n", ep);
        free(data);
        return;
    }

    if (dev->endpoint[EP2I(ep)].iso_started == 0) {
        DPRINTF("received iso packet for non started stream ep %02X\n", ep);
        free(data);
        return;
    }

    /* bufp_alloc also adds the packet to the ep queue */
    bufp_alloc(dev, data, data_len, iso_packet->status, ep);
}

static void usbredir_interrupt_packet(void *priv, uint64_t id,
    struct usb_redir_interrupt_packet_header *interrupt_packet,
    uint8_t *data, int data_len)
{
    USBRedirDevice *dev = priv;
    uint8_t ep = interrupt_packet->endpoint;

    DPRINTF("interrupt-in status %d ep %02X len %d id %"PRIu64"\n",
            interrupt_packet->status, ep, data_len, id);

    if (dev->endpoint[EP2I(ep)].type != USB_ENDPOINT_XFER_INT) {
        ERROR("received int packet for non interrupt endpoint %02X\n", ep);
        free(data);
        return;
    }

    if (ep & USB_DIR_IN) {
        if (dev->endpoint[EP2I(ep)].interrupt_started == 0) {
            DPRINTF("received int packet while not started ep %02X\n", ep);
            free(data);
            return;
        }

        /* bufp_alloc also adds the packet to the ep queue */
        bufp_alloc(dev, data, data_len, interrupt_packet->status, ep);
    } else {
        int len = interrupt_packet->length;

        AsyncURB *aurb = async_find(dev, id);
        if (aurb) {
            aurb->packet->len = usbredir_handle_status(dev,
                                               interrupt_packet->status, len);
            usb_packet_complete(&dev->dev, aurb->packet);
            async_free(dev, aurb);
        }
    }
}

/*
 * Migration code
 */

static void usbredir_pre_save(void *priv)
{
    USBRedirDevice *dev = priv;

    usbredir_fill_already_in_flight(dev);
}

static int usbredir_post_load(void *priv, int version_id)
{
    USBRedirDevice *dev = priv;

    switch (dev->device_info.speed) {
    case usb_redir_speed_low:
        dev->dev.speed = USB_SPEED_LOW;
        break;
    case usb_redir_speed_full:
        dev->dev.speed = USB_SPEED_FULL;
        break;
    case usb_redir_speed_high:
        dev->dev.speed = USB_SPEED_HIGH;
        break;
    case usb_redir_speed_super:
        dev->dev.speed = USB_SPEED_SUPER;
        break;
    default:
        dev->dev.speed = USB_SPEED_FULL;
    }
    dev->dev.speedmask = (1 << dev->dev.speed);

    return 0;
}

/* For usbredirparser migration */
static void usbredir_put_parser(QEMUFile *f, void *priv, size_t unused)
{
    USBRedirDevice *dev = priv;
    uint8_t *data;
    int len;

    if (dev->parser == NULL) {
        qemu_put_be32(f, 0);
        return;
    }

    usbredirparser_serialize(dev->parser, &data, &len);
    if (data == NULL) {
        abort();
    }

    qemu_put_be32(f, len);
    qemu_put_buffer(f, data, len);

    free(data);
}

static int usbredir_get_parser(QEMUFile *f, void *priv, size_t unused)
{
    USBRedirDevice *dev = priv;
    uint8_t *data;
    int len, ret;

    len = qemu_get_be32(f);
    if (len == 0) {
        return 0;
    }

    /*
     * If our chardev is not open already at this point the usbredir connection
     * has been broken (non seamless migration, or restore from disk).
     *
     * In this case create a temporary parser to receive the migration data,
     * and schedule the close_bh to report the device as disconnected to the
     * guest and to destroy the parser again.
     */
    if (dev->parser == NULL) {
        WARNING("usb-redir connection broken during migration\n");
        usbredir_create_parser(dev);
        qemu_bh_schedule(dev->chardev_close_bh);
    }

    data = qemu_malloc(len);
    qemu_get_buffer(f, data, len);

    ret = usbredirparser_unserialize(dev->parser, data, len);

    qemu_free(data);

    return ret;
}

static const VMStateInfo usbredir_parser_vmstate_info = {
    .name = "usb-redir-parser",
    .put  = usbredir_put_parser,
    .get  = usbredir_get_parser,
};


/* For buffered packets (iso/irq) queue migration */
static void usbredir_put_bufpq(QEMUFile *f, void *priv, size_t unused)
{
    struct endp_data *endp = priv;
    struct buf_packet *bufp;
    int remain = endp->bufpq_size;

    qemu_put_be32(f, endp->bufpq_size);
    QTAILQ_FOREACH(bufp, &endp->bufpq, next) {
        qemu_put_be32(f, bufp->len);
        qemu_put_be32(f, bufp->status);
        qemu_put_buffer(f, bufp->data, bufp->len);
        remain--;
    }
    assert(remain == 0);
}

static int usbredir_get_bufpq(QEMUFile *f, void *priv, size_t unused)
{
    struct endp_data *endp = priv;
    struct buf_packet *bufp;
    int i;

    endp->bufpq_size = qemu_get_be32(f);
    for (i = 0; i < endp->bufpq_size; i++) {
        bufp = qemu_malloc(sizeof(struct buf_packet));
        bufp->len = qemu_get_be32(f);
        bufp->status = qemu_get_be32(f);
        bufp->data = malloc(bufp->len); /* regular malloc! */
        if (bufp->data == NULL) {
            abort();
        }
        qemu_get_buffer(f, bufp->data, bufp->len);
        QTAILQ_INSERT_TAIL(&endp->bufpq, bufp, next);
    }
    return 0;
}

static const VMStateInfo usbredir_ep_bufpq_vmstate_info = {
    .name = "usb-redir-bufpq",
    .put  = usbredir_put_bufpq,
    .get  = usbredir_get_bufpq,
};


/* For endp_data migration */
static const VMStateDescription usbredir_ep_vmstate = {
    .name = "usb-redir-ep",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField []) {
        VMSTATE_UINT8(type, struct endp_data),
        VMSTATE_UINT8(interval, struct endp_data),
        VMSTATE_UINT8(interface, struct endp_data),
        VMSTATE_UINT16(max_packet_size, struct endp_data),
        VMSTATE_UINT8(iso_started, struct endp_data),
        VMSTATE_UINT8(iso_error, struct endp_data),
        VMSTATE_UINT8(interrupt_started, struct endp_data),
        VMSTATE_UINT8(interrupt_error, struct endp_data),
        VMSTATE_UINT8(bufpq_prefilled, struct endp_data),
        VMSTATE_UINT8(bufpq_dropping_packets, struct endp_data),
        {
            .name         = "bufpq",
            .version_id   = 0,
            .field_exists = NULL,
            .size         = 0,
            .info         = &usbredir_ep_bufpq_vmstate_info,
            .flags        = VMS_SINGLE,
            .offset       = 0,
        },
        VMSTATE_INT32(bufpq_target_size, struct endp_data),
        VMSTATE_END_OF_LIST()
    }
};


/* For PacketIdQueue migration */
static void usbredir_put_packet_id_q(QEMUFile *f, void *priv, size_t unused)
{
    struct PacketIdQueue *q = priv;
    USBRedirDevice *dev = q->dev;
    struct PacketIdQueueEntry *e;
    int remain = q->size;

    DPRINTF("put_packet_id_q %s size %d\n", q->name, q->size);
    qemu_put_be32(f, q->size);
    QTAILQ_FOREACH(e, &q->head, next) {
        qemu_put_be64(f, e->id);
        remain--;
    }
    assert(remain == 0);
}

static int usbredir_get_packet_id_q(QEMUFile *f, void *priv, size_t unused)
{
    struct PacketIdQueue *q = priv;
    USBRedirDevice *dev = q->dev;
    int i, size;
    uint64_t id;

    size = qemu_get_be32(f);
    DPRINTF("get_packet_id_q %s size %d\n", q->name, size);
    for (i = 0; i < size; i++) {
        id = qemu_get_be64(f);
        packet_id_queue_add(q, id);
    }
    assert(q->size == size);
    return 0;
}

static const VMStateInfo usbredir_ep_packet_id_q_vmstate_info = {
    .name = "usb-redir-packet-id-q",
    .put  = usbredir_put_packet_id_q,
    .get  = usbredir_get_packet_id_q,
};

static const VMStateDescription usbredir_ep_packet_id_queue_vmstate = {
    .name = "usb-redir-packet-id-queue",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField []) {
        {
            .name         = "queue",
            .version_id   = 0,
            .field_exists = NULL,
            .size         = 0,
            .info         = &usbredir_ep_packet_id_q_vmstate_info,
            .flags        = VMS_SINGLE,
            .offset       = 0,
        },
        VMSTATE_END_OF_LIST()
    }
};


/* For usb_redir_device_connect_header migration */
static const VMStateDescription usbredir_device_info_vmstate = {
    .name = "usb-redir-device-info",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField []) {
        VMSTATE_UINT8(speed, struct usb_redir_device_connect_header),
        VMSTATE_UINT8(device_class, struct usb_redir_device_connect_header),
        VMSTATE_UINT8(device_subclass, struct usb_redir_device_connect_header),
        VMSTATE_UINT8(device_protocol, struct usb_redir_device_connect_header),
        VMSTATE_UINT16(vendor_id, struct usb_redir_device_connect_header),
        VMSTATE_UINT16(product_id, struct usb_redir_device_connect_header),
        VMSTATE_UINT16(device_version_bcd,
                       struct usb_redir_device_connect_header),
        VMSTATE_END_OF_LIST()
    }
};


/* For usb_redir_interface_info_header migration */
static const VMStateDescription usbredir_interface_info_vmstate = {
    .name = "usb-redir-interface-info",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (VMStateField []) {
        VMSTATE_UINT32(interface_count,
                       struct usb_redir_interface_info_header),
        VMSTATE_UINT8_ARRAY(interface,
                            struct usb_redir_interface_info_header, 32),
        VMSTATE_UINT8_ARRAY(interface_class,
                            struct usb_redir_interface_info_header, 32),
        VMSTATE_UINT8_ARRAY(interface_subclass,
                            struct usb_redir_interface_info_header, 32),
        VMSTATE_UINT8_ARRAY(interface_protocol,
                            struct usb_redir_interface_info_header, 32),
        VMSTATE_END_OF_LIST()
    }
};


/* And finally the USBRedirDevice vmstate itself */
static const VMStateDescription usbredir_vmstate = {
    .name = "usb-redir",
    .version_id = 1,
    .minimum_version_id = 1,
    .pre_save = usbredir_pre_save,
    .post_load = usbredir_post_load,
    .fields = (VMStateField []) {
        VMSTATE_USB_DEVICE(dev, USBRedirDevice),
        VMSTATE_TIMER(attach_timer, USBRedirDevice),
        {
            .name         = "parser",
            .version_id   = 0,
            .field_exists = NULL,
            .size         = 0,
            .info         = &usbredir_parser_vmstate_info,
            .flags        = VMS_SINGLE,
            .offset       = 0,
        },
        VMSTATE_STRUCT_ARRAY(endpoint, USBRedirDevice, MAX_ENDPOINTS, 1,
                             usbredir_ep_vmstate, struct endp_data),
        VMSTATE_STRUCT(cancelled, USBRedirDevice, 1,
                       usbredir_ep_packet_id_queue_vmstate,
                       struct PacketIdQueue),
        VMSTATE_STRUCT(already_in_flight, USBRedirDevice, 1,
                       usbredir_ep_packet_id_queue_vmstate,
                       struct PacketIdQueue),
        VMSTATE_STRUCT(device_info, USBRedirDevice, 1,
                       usbredir_device_info_vmstate,
                       struct usb_redir_device_connect_header),
        VMSTATE_STRUCT(interface_info, USBRedirDevice, 1,
                       usbredir_interface_info_vmstate,
                       struct usb_redir_interface_info_header),
        VMSTATE_END_OF_LIST()
    }
};

static struct USBDeviceInfo usbredir_dev_info = {
    .product_desc   = "USB Redirection Device",
    .qdev.name      = "usb-redir",
    .qdev.size      = sizeof(USBRedirDevice),
    .init           = usbredir_initfn,
    .handle_destroy = usbredir_handle_destroy,
    .handle_packet  = usb_generic_handle_packet,
    .cancel_packet  = usbredir_cancel_packet,
    .handle_reset   = usbredir_handle_reset,
    .handle_data    = usbredir_handle_data,
    .handle_control = usbredir_handle_control,
    .qdev.vmsd      = &usbredir_vmstate,
    .qdev.props     = (Property[]) {
        DEFINE_PROP_CHR("chardev", USBRedirDevice, cs),
        DEFINE_PROP_UINT8("debug", USBRedirDevice, debug, 0),
        DEFINE_PROP_STRING("filter", USBRedirDevice, filter_str),
        DEFINE_PROP_END_OF_LIST(),
    },
};

static void usbredir_register_devices(void)
{
    usb_qdev_register(&usbredir_dev_info);
}
device_init(usbredir_register_devices);
