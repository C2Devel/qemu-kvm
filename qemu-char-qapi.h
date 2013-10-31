#ifndef QEMU_CHAR_QAPI_H
#define QEMU_CHAR_QAPI_H

void register_char_driver_qapi(const char *name, ChardevBackendKind kind,
        void (*parse)(QemuOpts *opts, ChardevBackend *backend, Error **errp));
CharDriverState *text_console_init(ChardevVC *vc);

#endif
