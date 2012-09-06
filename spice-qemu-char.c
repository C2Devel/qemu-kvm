#include "config-host.h"
#include "qemu-common.h"
#include "qemu-timer.h"
#include "ui/qemu-spice.h"
#include <spice.h>
#include <spice-experimental.h>

#include "osdep.h"

#define dprintf(_scd, _level, _fmt, ...)                                \
    do {                                                                \
        static unsigned __dprintf_counter = 0;                          \
        if (_scd->debug >= _level) {                                    \
            fprintf(stderr, "scd: %3d: " _fmt, ++__dprintf_counter, ## __VA_ARGS__);\
        }                                                               \
    } while (0)

#define VMC_MAX_HOST_WRITE    2048

typedef struct SpiceCharDriver {
    CharDriverState*      chr;
    SpiceCharDeviceInstance     sin;
    char                  *subtype;
    bool                  active;
    const uint8_t         *datapos;
    int                   datalen;
    uint32_t              debug;
    QEMUTimer             *unblock_timer;
} SpiceCharDriver;

static int vmc_write(SpiceCharDeviceInstance *sin, const uint8_t *buf, int len)
{
    SpiceCharDriver *scd = container_of(sin, SpiceCharDriver, sin);
    ssize_t out = 0;
    ssize_t last_out;
    uint8_t* p = (uint8_t*)buf;

    while (len > 0) {
        last_out = MIN(len, VMC_MAX_HOST_WRITE);
        if (qemu_chr_can_read(scd->chr) < last_out) {
            break;
        }
        qemu_chr_read(scd->chr, p, last_out);
        out += last_out;
        len -= last_out;
        p += last_out;
    }

    dprintf(scd, 3, "%s: %lu/%zd\n", __func__, out, len + out);
    return out;
}

static void spice_chr_unblock(void *opaque)
{
    SpiceCharDriver *scd = opaque;

    if (scd->chr->chr_write_unblocked == NULL) {
        dprintf(scd, 1, "%s: backend doesn't support unthrottling.\n", __func__);
        return;
    }
    scd->chr->chr_write_unblocked(scd->chr->handler_opaque);
}

static int vmc_read(SpiceCharDeviceInstance *sin, uint8_t *buf, int len)
{
    SpiceCharDriver *scd = container_of(sin, SpiceCharDriver, sin);
    int bytes = MIN(len, scd->datalen);

    dprintf(scd, 2, "%s: %p %d/%d/%d\n", __func__, scd->datapos, len, bytes, scd->datalen);
    if (bytes > 0) {
        memcpy(buf, scd->datapos, bytes);
        scd->datapos += bytes;
        scd->datalen -= bytes;
        assert(scd->datalen >= 0);
    }
    if (scd->datalen == 0 && scd->chr->write_blocked) {
        dprintf(scd, 1, "%s: unthrottling (%d)\n", __func__, bytes);
        scd->chr->write_blocked = false;
        /*
         * set a timer instead of calling scd->chr->chr_write_unblocked directly,
         * because that will call back into spice_chr_write (see
         * virtio-console.c:chr_write_unblocked), which is unwanted.
         */
        qemu_mod_timer(scd->unblock_timer, 0);
    }
    return bytes;
}

static void vmc_state(SpiceCharDeviceInstance *sin, int connected)
{
    SpiceCharDriver *scd = container_of(sin, SpiceCharDriver, sin);

#if SPICE_SERVER_VERSION < 0x000901
    /*
     * spice-server calls the state callback for the agent channel when the
     * spice client connects / disconnects. Given that not the client but
     * the server is doing the parsing of the messages this is wrong as the
     * server is still listening. Worse, this causes the parser in the server
     * to go out of sync, so we ignore state calls for subtype vdagent
     * spicevmc chardevs. For the full story see:
     * http://lists.freedesktop.org/archives/spice-devel/2011-July/004837.html
     */
    if (strcmp(sin->subtype, "vdagent") == 0) {
        return;
    }
#endif

    if ((scd->chr->opened && connected) ||
        (!scd->chr->opened && !connected)) {
        return;
    }

    qemu_chr_event(scd->chr,
                   connected ? CHR_EVENT_OPENED : CHR_EVENT_CLOSED);
}

static SpiceCharDeviceInterface vmc_interface = {
    .base.type          = SPICE_INTERFACE_CHAR_DEVICE,
    .base.description   = "spice virtual channel char device",
    .base.major_version = SPICE_INTERFACE_CHAR_DEVICE_MAJOR,
    .base.minor_version = SPICE_INTERFACE_CHAR_DEVICE_MINOR,
    .state              = vmc_state,
    .write              = vmc_write,
    .read               = vmc_read,
};


static void vmc_register_interface(SpiceCharDriver *scd)
{
    if (scd->active) {
        return;
    }
    dprintf(scd, 1, "%s\n", __func__);
    scd->sin.base.sif = &vmc_interface.base;
    qemu_spice_add_interface(&scd->sin.base);
    scd->active = true;
}

static void vmc_unregister_interface(SpiceCharDriver *scd)
{
    if (!scd->active) {
        return;
    }
    dprintf(scd, 1, "%s\n", __func__);
    spice_server_remove_interface(&scd->sin.base);
    scd->active = false;
}


static int spice_chr_write(CharDriverState *chr, const uint8_t *buf, int len)
{
    SpiceCharDriver *s = chr->opaque;
    int read_bytes;

    dprintf(s, 2, "%s: %d\n", __func__, len);
    vmc_register_interface(s);
    assert(s->datalen == 0);
    s->datapos = buf;
    s->datalen = len;
    spice_server_char_device_wakeup(&s->sin);
    read_bytes = len - s->datalen;
    if (read_bytes != len) {
        dprintf(s, 1, "%s: throttling: %d < %d\n", __func__,
                read_bytes, len);
        s->chr->write_blocked = true;
        /* We'll get passed in the unconsumed data with the next call */
        s->datalen = 0;
    }
    return read_bytes;
}

static void spice_chr_close(struct CharDriverState *chr)
{
    SpiceCharDriver *s = chr->opaque;

    printf("%s\n", __func__);
    vmc_unregister_interface(s);
    qemu_free(s);
}

static void spice_chr_guest_open(struct CharDriverState *chr)
{
    SpiceCharDriver *s = chr->opaque;
    vmc_register_interface(s);
}

static void spice_chr_guest_close(struct CharDriverState *chr)
{
    SpiceCharDriver *s = chr->opaque;
    vmc_unregister_interface(s);
}

static void print_allowed_subtypes(void)
{
    const char** psubtype;
    int i;

    fprintf(stderr, "allowed names: ");
    for(i=0, psubtype = spice_server_char_device_recognized_subtypes();
        *psubtype != NULL; ++psubtype, ++i) {
        if (i == 0) {
            fprintf(stderr, "%s", *psubtype);
        } else {
            fprintf(stderr, ", %s", *psubtype);
        }
    }
    fprintf(stderr, "\n");
}

CharDriverState *qemu_chr_open_spice(QemuOpts *opts)
{
    CharDriverState *chr;
    SpiceCharDriver *s;
    const char* name = qemu_opt_get(opts, "name");
    uint32_t debug = qemu_opt_get_number(opts, "debug", 0);
    const char** psubtype = spice_server_char_device_recognized_subtypes();
    const char *subtype = NULL;

    if (name == NULL) {
        fprintf(stderr, "spice-qemu-char: missing name parameter\n");
        print_allowed_subtypes();
        return NULL;
    }
    for(;*psubtype != NULL; ++psubtype) {
        if (strcmp(name, *psubtype) == 0) {
            subtype = *psubtype;
            break;
        }
    }
    if (subtype == NULL) {
        fprintf(stderr, "spice-qemu-char: unsupported name\n");
        print_allowed_subtypes();
        return NULL;
    }

    chr = qemu_mallocz(sizeof(CharDriverState));
    s = qemu_mallocz(sizeof(SpiceCharDriver));
    s->chr = chr;
    s->debug = debug;
    s->active = false;
    s->sin.subtype = subtype;
    chr->opaque = s;
    chr->chr_write = spice_chr_write;
    chr->chr_close = spice_chr_close;
    chr->chr_guest_open = spice_chr_guest_open;
    chr->chr_guest_close = spice_chr_guest_close;
    s->unblock_timer = qemu_new_timer(vm_clock, spice_chr_unblock, s);

#if SPICE_SERVER_VERSION < 0x000901
    /* See comment in vmc_state() */
    if (strcmp(subtype, "vdagent") == 0) {
        qemu_chr_generic_open(chr);
    }
#endif

    return chr;
}
