/*
 * QEMU Error Objects
 *
 * Copyright IBM, Corp. 2011
 *
 * Authors:
 *  Anthony Liguori   <aliguori@us.ibm.com>
 *
 * This work is licensed under the terms of the GNU LGPL, version 2.  See
 * the COPYING.LIB file in the top-level directory.
 */
#include "error.h"
#include "error_int.h"
#include "qemu-objects.h"
#include "qerror.h"
#include <assert.h>
#include <string.h>

struct Error
{
    QDict *obj;
    const char *fmt;
    char *msg;
};

void error_set(Error **errp, const char *fmt, ...)
{
    Error *err;
    va_list ap;

    if (errp == NULL) {
        return;
    }
    assert(*errp == NULL);

    err = qemu_mallocz(sizeof(*err));

    va_start(ap, fmt);
    err->obj = qobject_to_qdict(qobject_from_jsonv(fmt, &ap));
    va_end(ap);
    err->fmt = fmt;

    *errp = err;
}

/* RHEL-6 note:
 *
 * The following function, error_vsetg_errno(), and the implementation of
 * error_setg_errno() and error_setg() below, are RHEL-6 only compatibility
 * code. The RHEL-6 Error object is incompatible with that of upstream, but the
 * structure is not externally visible.
 */
static void error_vsetg_errno(Error **errp, int os_errno, const char *fmt,
                              va_list ap)
{
    char *msg;

    msg = g_strdup_vprintf(fmt, ap);
    if (os_errno != 0) {
        char *msg2;

        msg2 = g_strdup_printf("%s: %s", msg, strerror(os_errno));
        free(msg);
        msg = msg2;
    }
    error_set(errp, QERR_GENERIC_ERROR, msg);
    free(msg);
}

void error_setg_errno(Error **errp, int os_errno, const char *fmt, ...)
{
    va_list ap;

    va_start(ap, fmt);
    error_vsetg_errno(errp, os_errno, fmt, ap);
    va_end(ap);
}

void error_setg(Error **errp, const char *fmt, ...)
{
    va_list ap;

    va_start(ap, fmt);
    error_vsetg_errno(errp, 0, fmt, ap);
    va_end(ap);
}

bool error_is_set(Error **errp)
{
    return (errp && *errp);
}

const char *error_get_pretty(Error *err)
{
    if (err->msg == NULL) {
        QString *str;
        str = qerror_format(err->fmt, err->obj);
        err->msg = qemu_strdup(qstring_get_str(str));
        QDECREF(str);
    }

    return err->msg;
}

const char *error_get_field(Error *err, const char *field)
{
    if (strcmp(field, "class") == 0) {
        return qdict_get_str(err->obj, field);
    } else {
        QDict *dict = qdict_get_qdict(err->obj, "data");
        return qdict_get_str(dict, field);
    }
}

QDict *error_get_data(Error *err)
{
    QDict *data = qdict_get_qdict(err->obj, "data");
    QINCREF(data);
    return data;
}

void error_set_field(Error *err, const char *field, const char *value)
{
    QDict *dict = qdict_get_qdict(err->obj, "data");
    return qdict_put(dict, field, qstring_from_str(value));
}

void error_free(Error *err)
{
    if (err) {
        QDECREF(err->obj);
        qemu_free(err->msg);
        qemu_free(err);
    }
}

bool error_is_type(Error *err, const char *fmt)
{
    const char *error_class;
    char *ptr;
    char *end;

    ptr = strstr(fmt, "'class': '");
    assert(ptr != NULL);
    ptr += strlen("'class': '");

    end = strchr(ptr, '\'');
    assert(end != NULL);

    error_class = error_get_field(err, "class");
    if (strlen(error_class) != end - ptr) {
        return false;
    }

    return strncmp(ptr, error_class, end - ptr) == 0;
}

void error_propagate(Error **dst_err, Error *local_err)
{
    if (dst_err && !*dst_err) {
        *dst_err = local_err;
    } else if (local_err) {
        error_free(local_err);
    }
}
