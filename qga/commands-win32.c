/*
 * QEMU Guest Agent win32-specific command implementations
 *
 * Copyright IBM Corp. 2012
 *
 * Authors:
 *  Michael Roth      <mdroth@linux.vnet.ibm.com>
 *  Gal Hammer        <ghammer@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2 or later.
 * See the COPYING file in the top-level directory.
 */

#include <glib.h>
#include <wtypes.h>
#include <powrprof.h>
#include <lm.h>

#include "qga/guest-agent-core.h"
#include "qga-qmp-commands.h"
#include "qerror.h"
#include "qemu/base64.h"

#ifndef SHTDN_REASON_FLAG_PLANNED
#define SHTDN_REASON_FLAG_PLANNED 0x80000000
#endif

/* multiple of 100 nanoseconds elapsed between windows baseline
 *    (1/1/1601) and Unix Epoch (1/1/1970), accounting for leap years */
#define W32_FT_OFFSET (10000000ULL * 60 * 60 * 24 * \
                       (365 * (1970 - 1601) +       \
                        (1970 - 1601) / 4 - 3))

static void acquire_privilege(const char *name, Error **err)
{
    HANDLE token;
    TOKEN_PRIVILEGES priv;
    Error *local_err = NULL;

    if (error_is_set(err)) {
        return;
    }

    if (OpenProcessToken(GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES|TOKEN_QUERY, &token))
    {
        if (!LookupPrivilegeValue(NULL, name, &priv.Privileges[0].Luid)) {
            error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                      "no luid for requested privilege");
            goto out;
        }

        priv.PrivilegeCount = 1;
        priv.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;

        if (!AdjustTokenPrivileges(token, FALSE, &priv, 0, NULL, 0)) {
            error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                      "unable to acquire requested privilege");
            goto out;
        }

        CloseHandle(token);
    } else {
        error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                  "failed to open privilege token");
    }

out:
    if (local_err) {
        error_propagate(err, local_err);
    }
}

static void execute_async(DWORD WINAPI (*func)(LPVOID), LPVOID opaque, Error **err)
{
    Error *local_err = NULL;

    if (error_is_set(err)) {
        return;
    }
    HANDLE thread = CreateThread(NULL, 0, func, opaque, 0, NULL);
    if (!thread) {
        error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                  "failed to dispatch asynchronous command");
        error_propagate(err, local_err);
    }
}

void qmp_guest_shutdown(bool has_mode, const char *mode, Error **err)
{
    UINT shutdown_flag = EWX_FORCE;

    slog("guest-shutdown called, mode: %s", mode);

    if (!has_mode || strcmp(mode, "powerdown") == 0) {
        shutdown_flag |= EWX_POWEROFF;
    } else if (strcmp(mode, "halt") == 0) {
        shutdown_flag |= EWX_SHUTDOWN;
    } else if (strcmp(mode, "reboot") == 0) {
        shutdown_flag |= EWX_REBOOT;
    } else {
        error_set(err, QERR_INVALID_PARAMETER_VALUE, "mode",
                  "halt|powerdown|reboot");
        return;
    }

    /* Request a shutdown privilege, but try to shut down the system
       anyway. */
    acquire_privilege(SE_SHUTDOWN_NAME, err);
    if (error_is_set(err)) {
        return;
    }

    if (!ExitWindowsEx(shutdown_flag, SHTDN_REASON_FLAG_PLANNED)) {
        slog("guest-shutdown failed: %d", GetLastError());
        error_set(err, QERR_UNDEFINED_ERROR);
    }
}

int64_t qmp_guest_file_open(const char *path, bool has_mode, const char *mode, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

void qmp_guest_file_close(int64_t handle, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
}

GuestFileRead *qmp_guest_file_read(int64_t handle, bool has_count,
                                   int64_t count, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

GuestFileWrite *qmp_guest_file_write(int64_t handle, const char *buf_b64,
                                     bool has_count, int64_t count, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

GuestFileSeek *qmp_guest_file_seek(int64_t handle, int64_t offset,
                                   int64_t whence, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

void qmp_guest_file_flush(int64_t handle, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
}

/*
 * Return status of freeze/thaw
 */
GuestFsfreezeStatus qmp_guest_fsfreeze_status(Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

/*
 * Walk list of mounted file systems in the guest, and freeze the ones which
 * are real local file systems.
 */
int64_t qmp_guest_fsfreeze_freeze(Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

/*
 * Walk list of frozen file systems in the guest, and thaw them.
 */
int64_t qmp_guest_fsfreeze_thaw(Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return 0;
}

/*
 * Walk list of mounted file systems in the guest, and discard unused
 * areas.
 */
void qmp_guest_fstrim(bool has_minimum, int64_t minimum, Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
}

typedef enum {
    GUEST_SUSPEND_MODE_DISK,
    GUEST_SUSPEND_MODE_RAM
} GuestSuspendMode;

static void check_suspend_mode(GuestSuspendMode mode, Error **err)
{
    SYSTEM_POWER_CAPABILITIES sys_pwr_caps;
    Error *local_err = NULL;

    if (error_is_set(err)) {
        return;
    }
    ZeroMemory(&sys_pwr_caps, sizeof(sys_pwr_caps));
    if (!GetPwrCapabilities(&sys_pwr_caps)) {
        error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                  "failed to determine guest suspend capabilities");
        goto out;
    }

    switch (mode) {
    case GUEST_SUSPEND_MODE_DISK:
        if (!sys_pwr_caps.SystemS4) {
            error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                      "suspend-to-disk not supported by OS");
        }
        break;
    case GUEST_SUSPEND_MODE_RAM:
        if (!sys_pwr_caps.SystemS3) {
            error_set(&local_err, QERR_QGA_COMMAND_FAILED,
                      "suspend-to-ram not supported by OS");
        }
        break;
    default:
        error_set(&local_err, QERR_INVALID_PARAMETER_VALUE, "mode",
                  "GuestSuspendMode");
    }

out:
    if (local_err) {
        error_propagate(err, local_err);
    }
}

static DWORD WINAPI do_suspend(LPVOID opaque)
{
    GuestSuspendMode *mode = opaque;
    DWORD ret = 0;

    if (!SetSuspendState(*mode == GUEST_SUSPEND_MODE_DISK, TRUE, TRUE)) {
        slog("failed to suspend guest, %s", GetLastError());
        ret = -1;
    }
    g_free(mode);
    return ret;
}

void qmp_guest_suspend_disk(Error **err)
{
    GuestSuspendMode *mode = g_malloc(sizeof(GuestSuspendMode));

    *mode = GUEST_SUSPEND_MODE_DISK;
    check_suspend_mode(*mode, err);
    acquire_privilege(SE_SHUTDOWN_NAME, err);
    execute_async(do_suspend, mode, err);

    if (error_is_set(err)) {
        g_free(mode);
    }
}

void qmp_guest_suspend_ram(Error **err)
{
    GuestSuspendMode *mode = g_malloc(sizeof(GuestSuspendMode));

    *mode = GUEST_SUSPEND_MODE_RAM;
    check_suspend_mode(*mode, err);
    acquire_privilege(SE_SHUTDOWN_NAME, err);
    execute_async(do_suspend, mode, err);

    if (error_is_set(err)) {
        g_free(mode);
    }
}

void qmp_guest_suspend_hybrid(Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
}

GuestNetworkInterfaceList *qmp_guest_network_get_interfaces(Error **err)
{
    error_set(err, QERR_UNSUPPORTED);
    return NULL;
}

int64_t qmp_guest_get_time(Error **errp)
{
    SYSTEMTIME ts = {0};
    int64_t time_ns;
    FILETIME tf;

    GetSystemTime(&ts);
    if (ts.wYear < 1601 || ts.wYear > 30827) {
        error_setg(errp, "Failed to get time");
        return -1;
    }

    if (!SystemTimeToFileTime(&ts, &tf)) {
        error_setg(errp, "Failed to convert system time: %d", (int)GetLastError());
        return -1;
    }

    time_ns = ((((int64_t)tf.dwHighDateTime << 32) | tf.dwLowDateTime)
                - W32_FT_OFFSET) * 100;

    return time_ns;
}

void qmp_guest_set_time(bool has_time, int64_t time_ns, Error **errp)
{
    SYSTEMTIME ts;
    FILETIME tf;
    LONGLONG time;

    if (has_time) {
        /* Okay, user passed a time to set. Validate it. */
        if (time_ns < 0 || time_ns / 100 > INT64_MAX - W32_FT_OFFSET) {
            error_setg(errp, "Time %" PRId64 "is invalid", time_ns);
            return;
        }

        time = time_ns / 100 + W32_FT_OFFSET;

        tf.dwLowDateTime = (DWORD) time;
        tf.dwHighDateTime = (DWORD) (time >> 32);

        if (!FileTimeToSystemTime(&tf, &ts)) {
            error_setg(errp, "Failed to convert system time %d",
                       (int)GetLastError());
            return;
        }
    } else {
        /* Otherwise read the time from RTC which contains the correct value.
         * Hopefully. */
        GetSystemTime(&ts);
        if (ts.wYear < 1601 || ts.wYear > 30827) {
            error_setg(errp, "Failed to get time");
            return;
        }
    }

    acquire_privilege(SE_SYSTEMTIME_NAME, errp);
    if (error_is_set(errp)) {
        return;
    }

    if (!SetSystemTime(&ts)) {
        error_setg(errp, "Failed to set time to guest: %d", (int)GetLastError());
        return;
    }
}

GuestLogicalProcessorList *qmp_guest_get_vcpus(Error **errp)
{
    error_set(errp, QERR_UNSUPPORTED);
    return NULL;
}

int64_t qmp_guest_set_vcpus(GuestLogicalProcessorList *vcpus, Error **errp)
{
    error_set(errp, QERR_UNSUPPORTED);
    return -1;
}

static gchar *
get_net_error_message(gint error)
{
    HMODULE module = NULL;
    gchar *retval = NULL;
    wchar_t *msg = NULL;
    int flags;
    size_t nchars;

    flags = FORMAT_MESSAGE_ALLOCATE_BUFFER |
        FORMAT_MESSAGE_IGNORE_INSERTS |
        FORMAT_MESSAGE_FROM_SYSTEM;

    if (error >= NERR_BASE && error <= MAX_NERR) {
        module = LoadLibraryExW(L"netmsg.dll", NULL, LOAD_LIBRARY_AS_DATAFILE);

        if (module != NULL) {
            flags |= FORMAT_MESSAGE_FROM_HMODULE;
        }
    }

    FormatMessageW(flags, module, error, 0, (LPWSTR)&msg, 0, NULL);

    if (msg != NULL) {
        nchars = wcslen(msg);

        if (nchars >= 2 &&
            msg[nchars - 1] == L'\n' &&
            msg[nchars - 2] == L'\r') {
            msg[nchars - 2] = L'\0';
        }

        retval = g_utf16_to_utf8(msg, -1, NULL, NULL, NULL);

        LocalFree(msg);
    }

    if (module != NULL) {
        FreeLibrary(module);
    }

    return retval;
}

void qmp_guest_set_user_password(const char *username,
                                 const char *password,
                                 bool crypted,
                                 Error **errp)
{
    NET_API_STATUS nas;
    char *rawpasswddata = NULL;
    size_t rawpasswdlen;
    wchar_t *user = NULL, *wpass = NULL;
    USER_INFO_1003 pi1003 = { 0, };
    GError *gerr = NULL;

    if (crypted) {
        error_setg(errp, QERR_UNSUPPORTED);
        return;
    }

    rawpasswddata = (char *)qbase64_decode(password, -1, &rawpasswdlen, errp);
    if (!rawpasswddata) {
        return;
    }
    rawpasswddata = g_renew(char, rawpasswddata, rawpasswdlen + 1);
    rawpasswddata[rawpasswdlen] = '\0';

    user = g_utf8_to_utf16(username, -1, NULL, NULL, &gerr);
    if (!user) {
        goto done;
    }

    wpass = g_utf8_to_utf16(rawpasswddata, -1, NULL, NULL, &gerr);
    if (!wpass) {
        goto done;
    }

    pi1003.usri1003_password = wpass;
    nas = NetUserSetInfo(NULL, user,
                         1003, (LPBYTE)&pi1003,
                         NULL);

    if (nas != NERR_Success) {
        gchar *msg = get_net_error_message(nas);
        error_setg(errp, "failed to set password: %s", msg);
        g_free(msg);
    }

done:
    if (gerr) {
        error_setg(errp, QERR_QGA_COMMAND_FAILED, gerr->message);
        g_error_free(gerr);
    }
    g_free(user);
    g_free(wpass);
    g_free(rawpasswddata);
}

/* register init/cleanup routines for stateful command groups */
void ga_command_state_init(GAState *s, GACommandState *cs)
{
}
