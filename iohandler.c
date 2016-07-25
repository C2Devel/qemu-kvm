/*
 * QEMU System Emulator - managing I/O handler
 *
 * Copyright (c) 2003-2008 Fabrice Bellard
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

#include "config-host.h"
#include "qemu-common.h"
#include "qemu-char.h"
#include "qemu-queue.h"
#include "qemu-aio.h"

#ifndef _WIN32
#include <sys/wait.h>
#endif

/* reaping of zombies.  right now we're not passing the status to
   anyone, but it would be possible to add a callback.  */
#ifndef _WIN32
typedef struct ChildProcessRecord {
    int pid;
    QLIST_ENTRY(ChildProcessRecord) next;
} ChildProcessRecord;

static QLIST_HEAD(, ChildProcessRecord) child_watches =
    QLIST_HEAD_INITIALIZER(child_watches);

static QEMUBH *sigchld_bh;

static void sigchld_handler(int signal)
{
    qemu_bh_schedule(sigchld_bh);
}

static void sigchld_bh_handler(void *opaque)
{
    ChildProcessRecord *rec, *next;

    QLIST_FOREACH_SAFE(rec, &child_watches, next, next) {
        if (waitpid(rec->pid, NULL, WNOHANG) == rec->pid) {
            QLIST_REMOVE(rec, next);
            qemu_free(rec);
        }
    }
}

static void qemu_init_child_watch(void)
{
    struct sigaction act;
    sigchld_bh = qemu_bh_new(sigchld_bh_handler, NULL);

    act.sa_handler = sigchld_handler;
    act.sa_flags = SA_NOCLDSTOP;
    sigaction(SIGCHLD, &act, NULL);
}

int qemu_add_child_watch(pid_t pid)
{
    ChildProcessRecord *rec;

    if (!sigchld_bh) {
        qemu_init_child_watch();
    }

    QLIST_FOREACH(rec, &child_watches, next) {
        if (rec->pid == pid) {
            return 1;
        }
    }
    rec = qemu_mallocz(sizeof(ChildProcessRecord));
    rec->pid = pid;
    QLIST_INSERT_HEAD(&child_watches, rec, next);
    return 0;
}
#endif
