#include "config-host.h"
#include "ui/qemu-spice.h"
#include <spice.h>
#include <spice-experimental.h>

#include "osdep.h"

#include "qapi-visit.h"
#include "qemu-char-qapi.h"

#define VMC_MAX_HOST_WRITE    2048

typedef struct SpiceCharDriver {
    CharDriverState*      chr;
    SpiceCharDeviceInstance     sin;
    char                  *subtype;
    bool                  active;
    bool                  blocked;
    const uint8_t         *datapos;
    int                   datalen;
} SpiceCharDriver;

typedef struct SpiceCharSource {
    GSource               source;
    SpiceCharDriver       *scd;
} SpiceCharSource;

static int vmc_write(SpiceCharDeviceInstance *sin, const uint8_t *buf, int len)
{
    SpiceCharDriver *scd = container_of(sin, SpiceCharDriver, sin);
    ssize_t out = 0;
    ssize_t last_out;
    uint8_t* p = (uint8_t*)buf;

    while (len > 0) {
        last_out = MIN(len, VMC_MAX_HOST_WRITE);
        if (qemu_chr_be_can_write(scd->chr) < last_out) {
            break;
        }
        qemu_chr_be_write(scd->chr, p, last_out);
        out += last_out;
        len -= last_out;
        p += last_out;
    }

    return out;
}

static int vmc_read(SpiceCharDeviceInstance *sin, uint8_t *buf, int len)
{
    SpiceCharDriver *scd = container_of(sin, SpiceCharDriver, sin);
    int bytes = MIN(len, scd->datalen);

    if (bytes > 0) {
        memcpy(buf, scd->datapos, bytes);
        scd->datapos += bytes;
        scd->datalen -= bytes;
        assert(scd->datalen >= 0);
        if (scd->datalen == 0) {
            scd->datapos = 0;
        }
    }
    if (scd->datalen == 0) {
        scd->datapos = 0;
        scd->blocked = false;
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

    qemu_chr_be_event(scd->chr,
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
    scd->sin.base.sif = &vmc_interface.base;
    qemu_spice_add_interface(&scd->sin.base);
    scd->active = true;
}

static void vmc_unregister_interface(SpiceCharDriver *scd)
{
    if (!scd->active) {
        return;
    }
    spice_server_remove_interface(&scd->sin.base);
    scd->active = false;
}

static gboolean spice_char_source_prepare(GSource *source, gint *timeout)
{
    SpiceCharSource *src = (SpiceCharSource *)source;

    *timeout = -1;

    return !src->scd->blocked;
}

static gboolean spice_char_source_check(GSource *source)
{
    SpiceCharSource *src = (SpiceCharSource *)source;

    return !src->scd->blocked;
}

static gboolean spice_char_source_dispatch(GSource *source,
    GSourceFunc callback, gpointer user_data)
{
    GIOFunc func = (GIOFunc)callback;

    return func(NULL, G_IO_OUT, user_data);
}

GSourceFuncs SpiceCharSourceFuncs = {
    .prepare  = spice_char_source_prepare,
    .check    = spice_char_source_check,
    .dispatch = spice_char_source_dispatch,
};

static GSource *spice_chr_add_watch(CharDriverState *chr, GIOCondition cond)
{
    SpiceCharDriver *scd = chr->opaque;
    SpiceCharSource *src;

    assert(cond == G_IO_OUT);

    src = (SpiceCharSource *)g_source_new(&SpiceCharSourceFuncs,
                                          sizeof(SpiceCharSource));
    src->scd = scd;

    return (GSource *)src;
}

static int spice_chr_write(CharDriverState *chr, const uint8_t *buf, int len)
{
    SpiceCharDriver *s = chr->opaque;
    int read_bytes;

    vmc_register_interface(s);
    assert(s->datalen == 0);
    s->datapos = buf;
    s->datalen = len;
    spice_server_char_device_wakeup(&s->sin);
    read_bytes = len - s->datalen;
    if (read_bytes != len) {
        /* We'll get passed in the unconsumed data with the next call */
        s->datalen = 0;
        s->datapos = NULL;
        s->blocked = true;
    }
    return read_bytes;
}

static void spice_chr_close(struct CharDriverState *chr)
{
    SpiceCharDriver *s = chr->opaque;

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

CharDriverState *qemu_chr_open_spice_vmc(const char *type)
{
    CharDriverState *chr;
    SpiceCharDriver *s;
    const char **psubtype = spice_server_char_device_recognized_subtypes();

    if (type == NULL) {
        fprintf(stderr, "spice-qemu-char: missing name parameter\n");
        print_allowed_subtypes();
        return NULL;
    }
    for (; *psubtype != NULL; ++psubtype) {
        if (strcmp(type, *psubtype) == 0) {
            break;
        }
    }
    if (*psubtype == NULL) {
        fprintf(stderr, "spice-qemu-char: unsupported type: %s\n", type);
        print_allowed_subtypes();
        return NULL;
    }

    chr = qemu_mallocz(sizeof(CharDriverState));
    s = qemu_mallocz(sizeof(SpiceCharDriver));
    s->chr = chr;
    s->active = false;
    s->sin.subtype = *psubtype;
    chr->opaque = s;
    chr->chr_write = spice_chr_write;
    chr->chr_add_watch = spice_chr_add_watch;
    chr->chr_close = spice_chr_close;
    chr->chr_guest_open = spice_chr_guest_open;
    chr->chr_guest_close = spice_chr_guest_close;

#if SPICE_SERVER_VERSION < 0x000901
    /* See comment in vmc_state() */
    if (strcmp(type, "vdagent") == 0) {
        qemu_chr_generic_open(chr);
    }
#endif

    return chr;
}

static void qemu_chr_parse_spice_vmc(QemuOpts *opts, ChardevBackend *backend,
                                     Error **errp)
{
    const char *name = qemu_opt_get(opts, "name");

    if (name == NULL) {
        error_setg(errp, "chardev: spice channel: no name given");
        return;
    }
    backend->spicevmc = g_new0(ChardevSpiceChannel, 1);
    backend->spicevmc->type = g_strdup(name);
}

static void register_types(void)
{
    register_char_driver_qapi("spicevmc", CHARDEV_BACKEND_KIND_SPICEVMC,
                              qemu_chr_parse_spice_vmc);
}

machine_init(register_types);
