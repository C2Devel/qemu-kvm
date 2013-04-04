/*
 * QEMU live migration
 *
 * Copyright IBM, Corp. 2008
 *
 * Authors:
 *  Anthony Liguori   <aliguori@us.ibm.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2.  See
 * the COPYING file in the top-level directory.
 *
 */

#include "qemu-common.h"
#include "qemu_socket.h"
#include "migration.h"
#include "qemu-char.h"
#include "sysemu.h"
#include "buffered_file.h"
#include "block.h"

//#define DEBUG_MIGRATION_TCP

#ifdef DEBUG_MIGRATION_TCP
#define DPRINTF(fmt, ...) \
    do { printf("migration-tcp: " fmt, ## __VA_ARGS__); } while (0)
#else
#define DPRINTF(fmt, ...) \
    do { } while (0)
#endif

static int socket_errno(FdMigrationState *s)
{
    return socket_error();
}

static int socket_write(FdMigrationState *s, const void * buf, size_t size)
{
    return send(s->fd, buf, size, 0);
}

static int tcp_close(FdMigrationState *s)
{
    DPRINTF("tcp_close\n");
    if (s->fd != -1) {
        close(s->fd);
        s->fd = -1;
    }
    return 0;
}

static void tcp_wait_for_connect(int fd, void *opaque)
{
    FdMigrationState *s = opaque;

    if (fd < 0) {
        DPRINTF("migrate connect error\n");
        s->fd = -1;
        migrate_fd_error(s);
    } else {
        DPRINTF("migrate connect success\n");
        s->fd = fd;
        migrate_fd_connect(s);
    }
}

MigrationState *tcp_start_outgoing_migration(Monitor *mon,
                                             const char *host_port,
                                             int64_t bandwidth_limit,
                                             int detach,
                                             int blk,
                                             int inc,
                                             Error **errp)
{
    FdMigrationState *s;

    s = qemu_mallocz(sizeof(*s));

    s->get_error = socket_errno;
    s->write = socket_write;
    s->close = tcp_close;
    s->mig_state.cancel = migrate_fd_cancel;
    s->mig_state.get_status = migrate_fd_get_status;
    s->mig_state.release = migrate_fd_release;

    s->mig_state.blk = blk;
    s->mig_state.shared = inc;

    s->state = MIG_STATE_ACTIVE;
    s->mon = NULL;
    s->bandwidth_limit = bandwidth_limit;

    if (!detach) {
        migrate_fd_monitor_suspend(s, mon);
    }

    s->fd = inet_nonblocking_connect(host_port, tcp_wait_for_connect, s,
                                     errp);
    if (error_is_set(errp)) {
        migrate_fd_error(s);
        qemu_free(s);
        return NULL;
    }

    return &s->mig_state;
}

static void tcp_accept_incoming_migration(void *opaque)
{
    struct sockaddr_in addr;
    socklen_t addrlen = sizeof(addr);
    int s = (unsigned long)opaque;
    QEMUFile *f;
    int c;

    do {
        c = qemu_accept(s, (struct sockaddr *)&addr, &addrlen);
    } while (c == -1 && socket_error() == EINTR);

    DPRINTF("accepted migration\n");

    if (c == -1) {
        fprintf(stderr, "could not accept migration connection\n");
        return;
    }

    f = qemu_fopen_socket(c);
    if (f == NULL) {
        fprintf(stderr, "could not qemu_fopen socket\n");
        goto out;
    }

    process_incoming_migration(f);
    qemu_fclose(f);
out:
    qemu_set_fd_handler2(s, NULL, NULL, NULL, NULL);
    close(s);
    close(c);
}

int tcp_start_incoming_migration(const char *host_port, Error **errp)
{
    int s;

    s = inet_listen(host_port, NULL, 256, SOCK_STREAM, 0, errp);

    if (s < 0) {
        return -1;
    }

    qemu_set_fd_handler2(s, NULL, tcp_accept_incoming_migration, NULL,
                         (void *)(unsigned long)s);

    return 0;
}
