#ifndef SYSEMU_H
#define SYSEMU_H
/* Misc. things related to the system emulator.  */

#include "qemu-common.h"
#include "qemu-option.h"
#include "qemu-queue.h"
#include "qemu-timer.h"
#include "notify.h"

#ifdef _WIN32
#include <windows.h>
#include "qemu-os-win32.h"
#endif

#ifdef CONFIG_POSIX
#include "qemu-os-posix.h"
#endif

/* vl.c */

typedef enum {
    RUN_STATE_NO_STATE,
    RUN_STATE_DEBUG,          /* qemu is running under gdb */
    RUN_STATE_INMIGRATE,     /* paused waiting for an incoming migration */
    RUN_STATE_INTERNAL_ERROR,       /* paused due to an internal error */
    RUN_STATE_IO_ERROR,       /* paused due to an I/O error */
    RUN_STATE_PAUSED,         /* paused by the user (ie. the 'stop' command) */
    RUN_STATE_POSTMIGRATE,   /* paused following a successful migration */
    RUN_STATE_PRELAUNCH,     /* qemu was started with -S and haven't started */
    RUN_STATE_FINISH_MIGRATE,    /* paused preparing to finish migrate */
    RUN_STATE_RESTORE_VM,        /* paused restoring the VM state */
    RUN_STATE_RUNNING,        /* qemu is running */
    RUN_STATE_SAVE_VM,         /* paused saving VM state */
    RUN_STATE_SHUTDOWN,       /* guest shut down and -no-shutdown is in use */
    RUN_STATE_WATCHDOG,       /* watchdog fired and qemu is configured to pause */
    RUN_STATE_MAX
} RunState;

extern const char *bios_name;

#define QEMU_FILE_TYPE_BIOS   0
#define QEMU_FILE_TYPE_KEYMAP 1
char *qemu_find_file(int type, const char *name);

extern const char *qemu_name;
extern uint8_t qemu_uuid[];
int qemu_uuid_parse(const char *str, uint8_t *uuid);
#define UUID_FMT "%02hhx%02hhx%02hhx%02hhx-%02hhx%02hhx-%02hhx%02hhx-%02hhx%02hhx-%02hhx%02hhx%02hhx%02hhx%02hhx%02hhx"

void runstate_init(void);
bool runstate_check(RunState state);
void runstate_set(RunState new_state);
int runstate_is_running(void);
const char *runstate_as_string(void);
typedef struct vm_change_state_entry VMChangeStateEntry;
typedef void VMChangeStateHandler(void *opaque, int running, RunState state);

VMChangeStateEntry *qemu_add_vm_change_state_handler(VMChangeStateHandler *cb,
                                                     void *opaque);
void qemu_del_vm_change_state_handler(VMChangeStateEntry *e);

void vm_start(void);
void vm_stop(RunState state);
void vm_stop_force_state(RunState state);

uint64_t ram_bytes_remaining(void);
uint64_t ram_bytes_transferred(void);
uint64_t ram_bytes_total(void);

int64_t cpu_get_ticks(void);
void cpu_enable_ticks(void);
void cpu_disable_ticks(void);

typedef enum WakeupReason {
    QEMU_WAKEUP_REASON_OTHER = 0,
    QEMU_WAKEUP_REASON_RTC,
    QEMU_WAKEUP_REASON_PMTIMER,
} WakeupReason;

void qemu_system_reset_request(void);
void qemu_system_suspend_request(void);
void qemu_register_suspend_notifier(Notifier *notifier);
void qemu_unregister_suspend_notifier(Notifier *notifier);
void qemu_system_wakeup_request(WakeupReason reason);
void qemu_system_wakeup_enable(WakeupReason reason, bool enabled);
void qemu_register_wakeup_notifier(Notifier *notifier);
void qemu_system_shutdown_request(void);
void qemu_system_powerdown_request(void);
int qemu_no_shutdown(void);
int qemu_shutdown_requested(void);
int qemu_reset_requested(void);
int qemu_suspend_requested(void);
int qemu_powerdown_requested(void);
void qemu_system_killed(int signal, pid_t pid);
void qemu_kill_report(void);
extern qemu_irq qemu_system_powerdown;
void qemu_system_reset(void);
void qemu_system_suspend(void);

void qemu_add_machine_init_done_notifier(Notifier *notify);
void qemu_add_exit_notifier(Notifier *notify);
void qemu_remove_exit_notifier(Notifier *notify);

void do_savevm(Monitor *mon, const QDict *qdict);
int load_vmstate(const char *name);
void do_delvm(Monitor *mon, const QDict *qdict);
void do_info_snapshots(Monitor *mon);

void qemu_announce_self(void);

void main_loop_wait(int timeout);

bool qemu_savevm_state_blocked(Monitor *mon);
int qemu_savevm_state_begin(Monitor *mon, QEMUFile *f, int blk_enable,
                            int shared);
int qemu_savevm_state_iterate(Monitor *mon, QEMUFile *f);
int qemu_savevm_state_complete(Monitor *mon, QEMUFile *f);
void qemu_savevm_state_cancel(Monitor *mon, QEMUFile *f);
int qemu_loadvm_state(QEMUFile *f);

/* SLIRP */
void do_info_slirp(Monitor *mon);

void os_setup_early_signal_handling(void);

typedef enum DisplayType
{
    DT_DEFAULT,
    DT_CURSES,
    DT_SDL,
    DT_NOGRAPHIC,
} DisplayType;

extern int autostart;
extern int incoming_expected;
extern int bios_size;

typedef enum {
    VGA_NONE, VGA_STD, VGA_CIRRUS, VGA_VMWARE, VGA_XENFB, VGA_QXL,
} VGAInterfaceType;

extern int vga_interface_type;
#define cirrus_vga_enabled (vga_interface_type == VGA_CIRRUS)
#define std_vga_enabled (vga_interface_type == VGA_STD)
#define xenfb_enabled (vga_interface_type == VGA_XENFB)
#define vmsvga_enabled (vga_interface_type == VGA_VMWARE)
#define qxl_enabled (vga_interface_type == VGA_QXL)

extern int graphic_width;
extern int graphic_height;
extern int graphic_depth;
extern uint8_t irq0override;
extern DisplayType display_type;
extern const char *keyboard_layout;
extern int win2k_install_hack;
extern int rtc_td_hack;
extern int alt_grab;
extern int ctrl_grab;
extern int usb_enabled;
extern int smp_cpus;
extern int max_cpus;
extern int cursor_hide;
extern int graphic_rotate;
extern int no_quit;
extern int no_shutdown;
extern int semihosting_enabled;
extern int old_param;
extern int boot_menu;
extern QEMUClock *rtc_clock;
extern long hpagesize;

#define MAX_NODES 64
extern int nb_numa_nodes;
extern uint64_t node_mem[MAX_NODES];
extern uint64_t node_cpumask[MAX_NODES];

#define MAX_OPTION_ROMS 16
typedef struct QEMUOptionRom {
    const char *name;
    int32_t bootindex;
} QEMUOptionRom;
extern QEMUOptionRom option_rom[MAX_OPTION_ROMS];
extern int nb_option_roms;

#ifdef NEED_CPU_H
#if defined(TARGET_SPARC) || defined(TARGET_PPC)
#define MAX_PROM_ENVS 128
extern const char *prom_envs[MAX_PROM_ENVS];
extern unsigned int nb_prom_envs;
#endif
#endif

/* acpi */
void qemu_system_cpu_hot_add(int cpu, int state, Monitor *mon);

/* pci-hotplug */
void pci_device_hot_add(Monitor *mon, const QDict *qdict);
void drive_hot_add(Monitor *mon, const QDict *qdict);
int pci_device_hot_remove(Monitor *mon, const char *pci_addr);
void do_pci_device_hot_remove(Monitor *mon, const QDict *qdict);

/* serial ports */

#define MAX_SERIAL_PORTS 4

extern CharDriverState *serial_hds[MAX_SERIAL_PORTS];

/* parallel ports */

#define MAX_PARALLEL_PORTS 3

extern CharDriverState *parallel_hds[MAX_PARALLEL_PORTS];

#define TFR(expr) do { if ((expr) != -1) break; } while (errno == EINTR)

#ifdef HAS_AUDIO
struct soundhw {
    const char *name;
    const char *descr;
    int enabled;
    int isa;
    union {
        int (*init_isa) (qemu_irq *pic);
        int (*init_pci) (PCIBus *bus);
    } init;
};

extern struct soundhw soundhw[];
#endif

void do_usb_add(Monitor *mon, const QDict *qdict);
void do_usb_del(Monitor *mon, const QDict *qdict);
void usb_info(Monitor *mon);

void rtc_change_mon_event(struct tm *tm);

void register_devices(void);

int do_snapshot_blkdev(Monitor *mon, const QDict *qdict, QObject **ret_data);
int do_block_resize(Monitor *mon, const QDict *qdict, QObject **ret_data);

void add_boot_device_path(int32_t bootindex, DeviceState *dev,
                          const char *suffix);
char *get_boot_devices_list(uint32_t *size);
#endif
