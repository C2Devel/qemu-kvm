HXCOMM Use DEFHEADING() to define headings in both help text and texi
HXCOMM Text between STEXI and ETEXI are copied to texi version and
HXCOMM discarded from C version
HXCOMM Text between SQMP and EQMP is copied to the QMP documention file and
HXCOMM does not show up in the other formats.
HXCOMM DEF(command, args, callback, arg_string, help) is used to construct
HXCOMM monitor commands
HXCOMM HXCOMM can be used for comments, discarded from both texi and C

SQMP
                        QMP Supported Commands
                        ----------------------

This document describes all commands currently supported by QMP in
Red Hat Enterprise Linux 6.0.

Most of the time their usage is exactly the same as in the user Monitor, this
means that any other document which also describe commands (the manpage,
QEMU's manual, etc) can and should be consulted.

QMP has two types of commands: regular and query commands. Regular commands
usually change the Virtual Machine's state someway, while query commands just
return information. The sections below are divided accordingly.

It's important to observe that all communication examples are formatted in
a reader-friendly way, so that they're easier to understand. However, in real
protocol usage, they're emitted as a single line.

Also, the following notation is used to denote data flow:

-> data issued by the Client
<- Server data response

Please, refer to the QMP specification (QMP/qmp-spec.txt) for detailed
information on the Server command and response formats.

NOTE: This document is temporary and will be replaced soon.

1. Stability Considerations
===========================

The current QMP command set (described in this file) may be useful for a
number of use cases, however it's limited and several commands have bad
defined semantics, specially with regard to command completion.

These problems are going to be solved incrementally in the next QEMU releases
and we're going to establish a deprecation policy for badly defined commands.

If you're planning to adopt QMP, please observe the following:

    1. The deprecation policy will take efect and be documented soon, please
       check the documentation of each used command as soon as a new release of
       QEMU is available

    2. DO NOT rely on anything which is not explicit documented

    3. Errors, in special, are not documented. Applications should NOT check
       for specific errors classes or data (it's strongly recommended to only
       check for the "error" key)

2. Regular Commands
===================

Server's responses in the examples below are always a success response, please
refer to the QMP specification for more details on error responses.

EQMP

STEXI
@table @option
ETEXI

    {
        .name       = "help|?",
        .args_type  = "name:s?",
        .params     = "[cmd]",
        .help       = "show the help",
        .mhandler.cmd = do_help_cmd,
    },

STEXI
@item help or ? [@var{cmd}]
@findex help
Show the help for all commands or just for command @var{cmd}.
ETEXI

    {
        .name       = "commit",
        .args_type  = "device:B",
        .params     = "device|all",
        .help       = "commit changes to the disk images (if -snapshot is used) or backing files",
        .mhandler.cmd = do_commit,
    },

STEXI
@item commit
@findex commit
Commit changes to the disk images (if -snapshot is used) or backing files.
ETEXI

    {
        .name       = "q|quit",
        .args_type  = "",
        .params     = "",
        .help       = "quit the emulator",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_quit,
    },

STEXI
@item q or quit
@findex quit
Quit the emulator.
ETEXI
SQMP
quit
----

Quit the emulator.

Arguments: None.

Example:

-> { "execute": "quit" }
<- { "return": {} }

EQMP

    {
        .name       = "eject",
        .args_type  = "force:-f,device:B",
        .params     = "[-f] device",
        .help       = "eject a removable medium (use -f to force it)",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_eject,
    },

STEXI
@item eject [-f] @var{device}
@findex eject
Eject a removable medium (use -f to force it).
ETEXI
SQMP
eject
-----

Eject a removable medium.

Arguments: 

- force: force ejection (json-bool, optional)
- device: device name (json-string)

Example:

-> { "execute": "eject", "arguments": { "device": "ide1-cd0" } }
<- { "return": {} }

Note: The "force" argument defaults to false.

EQMP

    {
        .name       = RFQDN_REDHAT "drive_del",
        .args_type  = "id:s",
        .params     = "device",
        .help       = "remove host block device",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_drive_del,
    },

STEXI
@item __com.redhat_drive_del @var{device}
@findex __com.redhat_drive_del
Remove host block device.  The result is that guest generated IO is no longer
submitted against the host device underlying the disk.  Once a drive has
been deleted, the QEMU Block layer returns -EIO which results in IO
errors in the guest for applications that are reading/writing to the device.
ETEXI
SQMP
__com.redhat_drive_del
----------

    {
Remove host block device.  The result is that guest generated IO is no longer
submitted against the host device underlying the disk.  Once a drive has
been deleted, the QEMU Block layer returns -EIO which results in IO
errors in the guest for applications that are reading/writing to the device.

Arguments:

- "id": the device's ID (json-string)

Example:

-> { "execute": "drive_del", "arguments": { "id": "block1" } }
<- { "return": {} }

EQMP

    {

        .name       = "change",
        .args_type  = "device:B,target:F,arg:s?",
        .params     = "device filename [format]",
        .help       = "change a removable medium, optional format",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_change,
    },

STEXI
@item change @var{device} @var{setting}
@findex change

Change the configuration of a device.

@table @option
@item change @var{diskdevice} @var{filename} [@var{format}]
Change the medium for a removable disk device to point to @var{filename}. eg

@example
(qemu) change ide1-cd0 /path/to/some.iso
@end example

@var{format} is optional.

@item change vnc @var{display},@var{options}
Change the configuration of the VNC server. The valid syntax for @var{display}
and @var{options} are described at @ref{sec_invocation}. eg

@example
(qemu) change vnc localhost:1
@end example

@item change vnc password [@var{password}]

Change the password associated with the VNC server. If the new password is not
supplied, the monitor will prompt for it to be entered. VNC passwords are only
significant up to 8 letters. eg

@example
(qemu) change vnc password
Password: ********
@end example

@end table
ETEXI
SQMP
change
------

Change a removable medium or VNC configuration.

Arguments:

- "device": device name (json-string)
- "target": filename or item (json-string)
- "arg": additional argument (json-string, optional)

Examples:

1. Change a removable medium

-> { "execute": "change",
             "arguments": { "device": "ide1-cd0",
                            "target": "/srv/images/Fedora-12-x86_64-DVD.iso" } }
<- { "return": {} }

2. Change VNC password

-> { "execute": "change",
             "arguments": { "device": "vnc", "target": "password",
                            "arg": "foobar1" } }
<- { "return": {} }

EQMP

    {
        .name       = "screendump",
        .args_type  = "filename:F",
        .params     = "filename",
        .help       = "save screen into PPM image 'filename'",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_screen_dump,
    },

STEXI
@item screendump @var{filename}
@findex screendump
Save screen into PPM image @var{filename}.
ETEXI

    {
        .name       = RFQDN_REDHAT "qxl_screendump",
        .args_type  = "id:s,filename:F",
        .params     = "id filename",
        .help       = "save screen from qxl device 'id' into PPM image 'filename'",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = rhel6_qxl_do_screen_dump,
    },

STEXI
@item __com.redhat_screendump @var{id} @var{filename}
@findex __com.redhat_screendump
Save screen from qxl device @var{id} into PPM image @var{filename}.
ETEXI

    {
        .name       = "logfile",
        .args_type  = "filename:F",
        .params     = "filename",
        .help       = "output logs to 'filename'",
        .mhandler.cmd = do_logfile,
    },

STEXI
@item logfile @var{filename}
@findex logfile
Output logs to @var{filename}.
ETEXI

    {
        .name       = "log",
        .args_type  = "items:s",
        .params     = "item1[,...]",
        .help       = "activate logging of the specified items to '/tmp/qemu.log'",
        .mhandler.cmd = do_log,
    },

STEXI
@item log @var{item1}[,...]
@findex log
Activate logging of the specified items to @file{/tmp/qemu.log}.
ETEXI

    {
        .name       = "savevm",
        .args_type  = "name:s?",
        .params     = "[tag|id]",
        .help       = "save a VM snapshot. If no tag or id are provided, a new snapshot is created",
        .mhandler.cmd = do_savevm,
    },

STEXI
@item savevm [@var{tag}|@var{id}]
@findex savevm
Create a snapshot of the whole virtual machine. If @var{tag} is
provided, it is used as human readable identifier. If there is already
a snapshot with the same tag or ID, it is replaced. More info at
@ref{vm_snapshots}.
ETEXI

    {
        .name       = "loadvm",
        .args_type  = "name:s",
        .params     = "tag|id",
        .help       = "restore a VM snapshot from its tag or id",
        .mhandler.cmd = do_loadvm,
    },

STEXI
@item loadvm @var{tag}|@var{id}
@findex loadvm
Set the whole virtual machine to the snapshot identified by the tag
@var{tag} or the unique snapshot ID @var{id}.
ETEXI

    {
        .name       = "delvm",
        .args_type  = "name:s",
        .params     = "tag|id",
        .help       = "delete a VM snapshot from its tag or id",
        .mhandler.cmd = do_delvm,
    },

STEXI
@item delvm @var{tag}|@var{id}
@findex delvm
Delete the snapshot identified by @var{tag} or @var{id}.
ETEXI

    {
        .name       = "singlestep",
        .args_type  = "option:s?",
        .params     = "[on|off]",
        .help       = "run emulation in singlestep mode or switch to normal mode",
        .mhandler.cmd = do_singlestep,
    },

STEXI
@item singlestep [off]
@findex singlestep
Run the emulation in single step mode.
If called with option off, the emulation returns to normal mode.
ETEXI

    {
        .name       = "stop",
        .args_type  = "",
        .params     = "",
        .help       = "stop emulation",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_stop,
    },

STEXI
@item stop
@findex stop
Stop emulation.
ETEXI
SQMP
stop
----

Stop the emulator.

Arguments: None.

Example:

-> { "execute": "stop" }
<- { "return": {} }

EQMP

    {
        .name       = "c|cont",
        .args_type  = "",
        .params     = "",
        .help       = "resume emulation",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_cont,
    },

STEXI
@item c or cont
@findex cont
Resume emulation.
ETEXI
SQMP
cont
----

Resume emulation.

Arguments: None.

Example:

-> { "execute": "cont" }
<- { "return": {} }

EQMP

    {
        .name       = "system_wakeup",
        .args_type  = "",
        .params     = "",
        .help       = "wakeup guest from suspend",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_system_wakeup,
    },

STEXI
@item system_wakeup
@findex system_wakeup
Wakeup guest from suspend.
ETEXI

    {
        .name       = "gdbserver",
        .args_type  = "device:s?",
        .params     = "[device]",
        .help       = "start gdbserver on given device (default 'tcp::1234'), stop with 'none'",
        .mhandler.cmd = do_gdbserver,
    },

STEXI
@item gdbserver [@var{port}]
@findex gdbserver
Start gdbserver session (default @var{port}=1234)
ETEXI

    {
        .name       = "x",
        .args_type  = "fmt:/,addr:l",
        .params     = "/fmt addr",
        .help       = "virtual memory dump starting at 'addr'",
        .mhandler.cmd = do_memory_dump,
    },

STEXI
@item x/fmt @var{addr}
@findex x
Virtual memory dump starting at @var{addr}.
ETEXI

    {
        .name       = "xp",
        .args_type  = "fmt:/,addr:l",
        .params     = "/fmt addr",
        .help       = "physical memory dump starting at 'addr'",
        .mhandler.cmd = do_physical_memory_dump,
    },

STEXI
@item xp /@var{fmt} @var{addr}
@findex xp
Physical memory dump starting at @var{addr}.

@var{fmt} is a format which tells the command how to format the
data. Its syntax is: @option{/@{count@}@{format@}@{size@}}

@table @var
@item count
is the number of items to be dumped.

@item format
can be x (hex), d (signed decimal), u (unsigned decimal), o (octal),
c (char) or i (asm instruction).

@item size
can be b (8 bits), h (16 bits), w (32 bits) or g (64 bits). On x86,
@code{h} or @code{w} can be specified with the @code{i} format to
respectively select 16 or 32 bit code instruction size.

@end table

Examples:
@itemize
@item
Dump 10 instructions at the current instruction pointer:
@example
(qemu) x/10i $eip
0x90107063:  ret
0x90107064:  sti
0x90107065:  lea    0x0(%esi,1),%esi
0x90107069:  lea    0x0(%edi,1),%edi
0x90107070:  ret
0x90107071:  jmp    0x90107080
0x90107073:  nop
0x90107074:  nop
0x90107075:  nop
0x90107076:  nop
@end example

@item
Dump 80 16 bit values at the start of the video memory.
@smallexample
(qemu) xp/80hx 0xb8000
0x000b8000: 0x0b50 0x0b6c 0x0b65 0x0b78 0x0b38 0x0b36 0x0b2f 0x0b42
0x000b8010: 0x0b6f 0x0b63 0x0b68 0x0b73 0x0b20 0x0b56 0x0b47 0x0b41
0x000b8020: 0x0b42 0x0b69 0x0b6f 0x0b73 0x0b20 0x0b63 0x0b75 0x0b72
0x000b8030: 0x0b72 0x0b65 0x0b6e 0x0b74 0x0b2d 0x0b63 0x0b76 0x0b73
0x000b8040: 0x0b20 0x0b30 0x0b35 0x0b20 0x0b4e 0x0b6f 0x0b76 0x0b20
0x000b8050: 0x0b32 0x0b30 0x0b30 0x0b33 0x0720 0x0720 0x0720 0x0720
0x000b8060: 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720
0x000b8070: 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720
0x000b8080: 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720
0x000b8090: 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720 0x0720
@end smallexample
@end itemize
ETEXI

    {
        .name       = "p|print",
        .args_type  = "fmt:/,val:l",
        .params     = "/fmt expr",
        .help       = "print expression value (use $reg for CPU register access)",
        .mhandler.cmd = do_print,
    },

STEXI
@item p or print/@var{fmt} @var{expr}
@findex print

Print expression value. Only the @var{format} part of @var{fmt} is
used.
ETEXI

    {
        .name       = "i",
        .args_type  = "fmt:/,addr:i,index:i.",
        .params     = "/fmt addr",
        .help       = "I/O port read",
        .mhandler.cmd = do_ioport_read,
    },

STEXI
Read I/O port.
ETEXI

    {
        .name       = "o",
        .args_type  = "fmt:/,addr:i,val:i",
        .params     = "/fmt addr value",
        .help       = "I/O port write",
        .mhandler.cmd = do_ioport_write,
    },

STEXI
Write to I/O port.
ETEXI

    {
        .name       = "sendkey",
        .args_type  = "string:s,hold_time:i?",
        .params     = "keys [hold_ms]",
        .help       = "send keys to the VM (e.g. 'sendkey ctrl-alt-f1', default hold time=100 ms)",
        .mhandler.cmd = do_sendkey,
    },

STEXI
@item sendkey @var{keys}
@findex sendkey

Send @var{keys} to the emulator. @var{keys} could be the name of the
key or @code{#} followed by the raw value in either decimal or hexadecimal
format. Use @code{-} to press several keys simultaneously. Example:
@example
sendkey ctrl-alt-f1
@end example

This command is useful to send keys that your graphical user interface
intercepts at low level, such as @code{ctrl-alt-f1} in X Window.
ETEXI

    {
        .name       = "system_reset",
        .args_type  = "",
        .params     = "",
        .help       = "reset the system",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_system_reset,
    },

STEXI
@item system_reset
@findex system_reset

Reset the system.
ETEXI
SQMP
system_reset
------------

Reset the system.

Arguments: None.

Example:

-> { "execute": "system_reset" }
<- { "return": {} }

EQMP

    {
        .name       = "system_powerdown",
        .args_type  = "",
        .params     = "",
        .help       = "send system power down event",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_system_powerdown,
    },

STEXI
@item system_powerdown
@findex system_powerdown

Power down the system (if supported).
ETEXI
SQMP
system_powerdown
----------------

Send system power down event.

Arguments: None.

Example:

-> { "execute": "system_powerdown" }
<- { "return": {} }

EQMP

    {
        .name       = "sum",
        .args_type  = "start:i,size:i",
        .params     = "addr size",
        .help       = "compute the checksum of a memory region",
        .mhandler.cmd = do_sum,
    },

STEXI
@item sum @var{addr} @var{size}
@findex sum

Compute the checksum of a memory region.
ETEXI

#if 0 /* Disabled for Red Hat Enterprise Linux */
    {
        .name       = "usb_add",
        .args_type  = "devname:s",
        .params     = "device",
        .help       = "add USB device (e.g. 'host:bus.addr' or 'host:vendor_id:product_id')",
        .mhandler.cmd = do_usb_add,
    },

STEXI
@item usb_add @var{devname}
@findex usb_add

Add the USB device @var{devname}.  For details of available devices see
@ref{usb_devices}
ETEXI

    {
        .name       = "usb_del",
        .args_type  = "devname:s",
        .params     = "device",
        .help       = "remove USB device 'bus.addr'",
        .mhandler.cmd = do_usb_del,
    },

STEXI
@item usb_del @var{devname}
@findex usb_del

Remove the USB device @var{devname} from the QEMU virtual USB
hub. @var{devname} has the syntax @code{bus.addr}. Use the monitor
command @code{info usb} to see the devices you can remove.
ETEXI
#endif

    {
        .name       = "device_add",
        .args_type  = "device:O",
        .params     = "driver[,prop=value][,...]",
        .help       = "add device, like -device on the command line",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_device_add,
    },

STEXI
@item device_add @var{config}
@findex device_add

Add device.
ETEXI
SQMP
device_add
----------

Add a device.

Arguments:

- "driver": the name of the new device's driver (json-string)
- "bus": the device's parent bus (device tree path, json-string, optional)
- "id": the device's ID, must be unique (json-string)
- device properties

Example:

-> { "execute": "device_add", "arguments": { "driver": "e1000", "id": "net1" } }
<- { "return": {} }

Notes:

(1) For detailed information about this command, please refer to the
    'docs/qdev-device-use.txt' file.

(2) It's possible to list device properties by running QEMU with the
    "-device DEVICE,\?" command-line argument, where DEVICE is the device's name

EQMP

    {
        .name       = "device_del",
        .args_type  = "id:s",
        .params     = "device",
        .help       = "remove device",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_device_del,
    },

STEXI
@item device_del @var{id}
@findex device_del

Remove device @var{id}.
ETEXI
SQMP
device_del
----------

Remove a device.

Arguments:

- "id": the device's ID (json-string)

Example:

-> { "execute": "device_del", "arguments": { "id": "net1" } }
<- { "return": {} }

EQMP

    {
        .name       = "cpu",
        .args_type  = "index:i",
        .params     = "index",
        .help       = "set the default CPU",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_cpu_set,
    },

STEXI
@item cpu @var{index}
@findex cpu
Set the default CPU.
ETEXI
SQMP
cpu
---

Set the default CPU.

Arguments:

- "index": the CPU's index (json-int)

Example:

-> { "execute": "cpu", "arguments": { "index": 0 } }
<- { "return": {} }

Note: CPUs' indexes are obtained with the 'query-cpus' command.

EQMP

    {
        .name       = "mouse_move",
        .args_type  = "dx_str:s,dy_str:s,dz_str:s?",
        .params     = "dx dy [dz]",
        .help       = "send mouse move events",
        .mhandler.cmd = do_mouse_move,
    },

STEXI
@item mouse_move @var{dx} @var{dy} [@var{dz}]
@findex mouse_move
Move the active mouse to the specified coordinates @var{dx} @var{dy}
with optional scroll axis @var{dz}.
ETEXI

    {
        .name       = "mouse_button",
        .args_type  = "button_state:i",
        .params     = "state",
        .help       = "change mouse button state (1=L, 2=M, 4=R)",
        .mhandler.cmd = do_mouse_button,
    },

STEXI
@item mouse_button @var{val}
@findex mouse_button
Change the active mouse button state @var{val} (1=L, 2=M, 4=R).
ETEXI

    {
        .name       = "mouse_set",
        .args_type  = "index:i",
        .params     = "index",
        .help       = "set which mouse device receives events",
        .mhandler.cmd = do_mouse_set,
    },

STEXI
@item mouse_set @var{index}
@findex mouse_set
Set which mouse device receives events at given @var{index}, index
can be obtained with
@example
info mice
@end example
ETEXI

#ifdef HAS_AUDIO
    {
        .name       = "wavcapture",
        .args_type  = "path:F,freq:i?,bits:i?,nchannels:i?",
        .params     = "path [frequency [bits [channels]]]",
        .help       = "capture audio to a wave file (default frequency=44100 bits=16 channels=2)",
        .mhandler.cmd = do_wav_capture,
    },
#endif
STEXI
@item wavcapture @var{filename} [@var{frequency} [@var{bits} [@var{channels}]]]
@findex wavcapture
Capture audio into @var{filename}. Using sample rate @var{frequency}
bits per sample @var{bits} and number of channels @var{channels}.

Defaults:
@itemize @minus
@item Sample rate = 44100 Hz - CD quality
@item Bits = 16
@item Number of channels = 2 - Stereo
@end itemize
ETEXI

#ifdef HAS_AUDIO
    {
        .name       = "stopcapture",
        .args_type  = "n:i",
        .params     = "capture index",
        .help       = "stop capture",
        .mhandler.cmd = do_stop_capture,
    },
#endif
STEXI
@item stopcapture @var{index}
@findex stopcapture
Stop capture with a given @var{index}, index can be obtained with
@example
info capture
@end example
ETEXI

    {
        .name       = "memsave",
        .args_type  = "val:l,size:i,filename:s",
        .params     = "addr size file",
        .help       = "save to disk virtual memory dump starting at 'addr' of size 'size'",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_memory_save,
    },

STEXI
@item memsave @var{addr} @var{size} @var{file}
@findex memsave
save to disk virtual memory dump starting at @var{addr} of size @var{size}.
ETEXI
SQMP
memsave
-------

Save to disk virtual memory dump starting at 'val' of size 'size'.

Arguments:

- "val": the starting address (json-int)
- "size": the memory size, in bytes (json-int)
- "filename": file path (json-string)

Example:

-> { "execute": "memsave",
             "arguments": { "val": 10,
                            "size": 100,
                            "filename": "/tmp/virtual-mem-dump" } }
<- { "return": {} }

Note: Depends on the current CPU.

EQMP

    {
        .name       = "pmemsave",
        .args_type  = "val:l,size:i,filename:s",
        .params     = "addr size file",
        .help       = "save to disk physical memory dump starting at 'addr' of size 'size'",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_physical_memory_save,
    },

STEXI
@item pmemsave @var{addr} @var{size} @var{file}
@findex pmemsave
save to disk physical memory dump starting at @var{addr} of size @var{size}.
ETEXI
SQMP
pmemsave
--------

Save to disk physical memory dump starting at 'val' of size 'size'.

Arguments:

- "val": the starting address (json-int)
- "size": the memory size, in bytes (json-int)
- "filename": file path (json-string)

Example:

-> { "execute": "pmemsave",
             "arguments": { "val": 10,
                            "size": 100,
                            "filename": "/tmp/physical-mem-dump" } }
<- { "return": {} }

EQMP

    {
        .name       = "boot_set",
        .args_type  = "bootdevice:s",
        .params     = "bootdevice",
        .help       = "define new values for the boot device list",
        .mhandler.cmd = do_boot_set,
    },

STEXI
@item boot_set @var{bootdevicelist}
@findex boot_set

Define new values for the boot device list. Those values will override
the values specified on the command line through the @code{-boot} option.

The values that can be specified here depend on the machine type, but are
the same that can be specified in the @code{-boot} command line option.
ETEXI

#if defined(TARGET_I386)
    {
        .name       = "nmi",
        .args_type  = "",
        .params     = "",
        .help       = "inject an NMI on all guest's CPUs",
        .mhandler.cmd = do_inject_nmi_hmp,
    },
#endif
STEXI
@item nmi @var{cpu}
@findex nmi
Inject an NMI on the given CPU (x86 only).
ETEXI

    {
        .name       = "inject-nmi",
        .args_type  = "",
        .params     = "",
        .help       = "",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_inject_nmi,
    },

SQMP
inject-nmi
----------

Inject an NMI on guest's CPUs.

Arguments: None.

Example:

-> { "execute": "inject-nmi" }
<- { "return": {} }

Note: inject-nmi is only supported for x86 guest currently, it will
      returns "Unsupported" error for non-x86 guest.

EQMP

    {
        .name       = "migrate",
        .args_type  = "detach:-d,blk:-b,inc:-i,uri:s",
        .params     = "[-d] [-b] [-i] uri",
        .help       = "migrate to URI (using -d to not wait for completion)"
		      "\n\t\t\t -b for migration without shared storage with"
		      " full copy of disk\n\t\t\t -i for migration without "
		      "shared storage with incremental copy of disk "
		      "(base image shared between src and destination)",
        .user_print = monitor_user_noop,	
	.mhandler.cmd_new = do_migrate,
    },


STEXI
@item migrate [-d] [-b] [-i] @var{uri}
@findex migrate
Migrate to @var{uri} (using -d to not wait for completion).
	-b for migration with full copy of disk
	-i for migration with incremental copy of disk (base image is shared)
ETEXI
SQMP
migrate
-------

Migrate to URI.

Arguments:

- "blk": block migration, full disk copy (json-bool, optional)
- "inc": incremental disk copy (json-bool, optional)
- "uri": Destination URI (json-string)

Example:

-> { "execute": "migrate", "arguments": { "uri": "tcp:0:4446" } }
<- { "return": {} }

Notes:

(1) The 'query-migrate' command should be used to check migration's progress
    and final result (this information is provided by the 'status' member)
(2) All boolean arguments default to false
(3) The user Monitor's "detach" argument is invalid in QMP and should not
    be used

EQMP

    {
        .name       = "migrate_cancel",
        .args_type  = "",
        .params     = "",
        .help       = "cancel the current VM migration",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_migrate_cancel,
    },

STEXI
@item migrate_cancel
@findex migrate_cancel
Cancel the current VM migration.
ETEXI
SQMP
migrate_cancel
--------------

Cancel the current migration.

Arguments: None.

Example:

-> { "execute": "migrate_cancel" }
<- { "return": {} }

EQMP

    {
        .name       = "migrate_set_speed",
        .args_type  = "value:f",
        .params     = "value",
        .help       = "set maximum speed (in bytes) for migrations",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_migrate_set_speed,
    },

STEXI
@item migrate_set_speed @var{value}
@findex migrate_set_speed
Set maximum speed to @var{value} (in bytes) for migrations.
ETEXI
SQMP
client_migrate_info
------------------

Set the spice/vnc connection info for the migration target.  The spice/vnc
server will ask the spice/vnc client to automatically reconnect using the
new parameters (if specified) once the vm migration finished successfully.

Arguments:

- "protocol":     protocol: "spice" or "vnc" (json-string)
- "hostname":     migration target hostname (json-string)
- "port":         spice/vnc tcp port for plaintext channels (json-int, optional)
- "tls-port":     spice tcp port for tls-secured channels (json-int, optional)
- "cert-subject": server certificate subject (json-string, optional)

Example:

-> { "execute": "client_migrate_info",
     "arguments": { "protocol": "spice",
                    "hostname": "virt42.lab.kraxel.org",
                    "port": 1234 } }
<- { "return": {} }

EQMP

    {
        .name       = "client_migrate_info",
        .args_type  = "protocol:s,hostname:s,port:i?,tls-port:i?,cert-subject:s?",
        .params     = "protocol hostname port tls-port cert-subject",
        .help       = "send migration info to spice/vnc client",
        .user_print = monitor_user_noop,
        .mhandler.cmd_async = client_migrate_info,
        .flags      = MONITOR_CMD_ASYNC,
    },

SQMP
migrate_set_speed
-----------------

Set maximum speed for migrations.

Arguments:

- "value": maximum speed, in bytes per second (json-number)

Example:

-> { "execute": "migrate_set_speed", "arguments": { "value": 1024 } }
<- { "return": {} }

EQMP

    {
        .name       = "migrate_set_downtime",
        .args_type  = "value:T",
        .params     = "value",
        .help       = "set maximum tolerated downtime (in seconds) for migrations",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_migrate_set_downtime,
    },

STEXI
@item migrate_set_downtime @var{second}
@findex migrate_set_downtime
Set maximum tolerated downtime (in seconds) for migration.
ETEXI
SQMP
migrate_set_downtime
--------------------

Set maximum tolerated downtime (in seconds) for migrations.

Arguments:

- "value": maximum downtime (json-number)

Example:

-> { "execute": "migrate_set_downtime", "arguments": { "value": 0.1 } }
<- { "return": {} }

EQMP

#ifdef CONFIG_LIVE_SNAPSHOTS
    {
        .name       = "snapshot_blkdev",
        .args_type  = "reuse:-n,device:B,snapshot-file:s?,format:s?",
        .params     = "[-n] device [new-image-file] [format]",
        .help       = "initiates a live snapshot\n\t\t\t"
                      "of device. If a new image file is specified, the\n\t\t\t"
                      "new image file will become the new root image.\n\t\t\t"
                      "If format is specified, the snapshot file will\n\t\t\t"
                      "be created in that format. Otherwise the\n\t\t\t"
                      "snapshot will be internal! (currently unsupported).\n\t\t\t"
                      "The default format is qcow2.  The -n flag requests QEMU\n\t\t\t"
                      "to reuse the image found in new-image-file, instead of\n\t\t\t"
                      "recreating it from scratch.",
        .mhandler.cmd = hmp_snapshot_blkdev,
    },
#endif

STEXI
@item snapshot_blkdev
@findex snapshot_blkdev
Snapshot device, using snapshot file as target if provided
ETEXI

    {
        .name       = "block_resize",
        .args_type  = "device:B,size:o",
        .params     = "device size",
        .help       = "resize a block image",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_block_resize,
    },

STEXI
@item block_resize
@findex block_resize
Resize a block image while a guest is running.  Usually requires guest
action to see the updated size.  Resize to a lower size is supported,
but should be used with extreme caution.  Note that this command only
resizes image files, it can not resize block devices like LVM volumes.
ETEXI
SQMP
block_resize
------------

Resize a block image while a guest is running.

Arguments:

- "device": the device's ID, must be unique (json-string)
- "size": new size

Example:

-> { "execute": "block_resize", "arguments": { "device": "scratch", "size": 1073741824 }
}
<- { "return": {} }

EQMP

#if defined(TARGET_I386) && 0 /* Disabled for Red Hat Enterprise Linux */
    {
        .name       = "drive_add",
        .args_type  = "pci_addr:s,opts:s",
        .params     = "[[<domain>:]<bus>:]<slot>\n"
                      "[file=file][,if=type][,bus=n]\n"
                      "[,unit=m][,media=d][,index=i]\n"
                      "[,cyls=c,heads=h,secs=s[,trans=t]]\n"
                      "[,snapshot=on|off][,cache=on|off]",
                      "[,readonly=on|off][,copy-on-read=on|off]",
        .help       = "add drive to PCI storage controller",
        .mhandler.cmd = drive_hot_add,
    },
#endif

STEXI
@item drive_add
@findex drive_add
Add drive to PCI storage controller.
ETEXI

#if defined(TARGET_I386) && 0 /* Disabled for Red Hat Enterprise Linux */
    {
        .name       = "pci_add",
        .args_type  = "pci_addr:s,type:s,opts:s?",
        .params     = "auto|[[<domain>:]<bus>:]<slot> nic|storage|host [[vlan=n][,macaddr=addr][,model=type]] [file=file][,if=type][,bus=nr]... [host=02:00.0[,name=string][,dma=none]",
        .help       = "hot-add PCI device",
        .mhandler.cmd = pci_device_hot_add,
    },
#endif

STEXI
@item pci_add
@findex pci_add
Hot-add PCI device.
ETEXI

#if defined(TARGET_I386) && 0 /* Disabled for Red Hat Enterprise Linux */
    {
        .name       = "pci_del",
        .args_type  = "pci_addr:s",
        .params     = "[[<domain>:]<bus>:]<slot>",
        .help       = "hot remove PCI device",
        .mhandler.cmd = do_pci_device_hot_remove,
    },
#endif

STEXI
@item pci_del
@findex pci_del
Hot remove PCI device.
ETEXI

#if 0 /* Disabled for Red Hat Enterprise Linux */
    {
        .name       = "host_net_add",
        .args_type  = "device:s,opts:s?",
        .params     = "tap|user|socket|vde|dump [options]",
        .help       = "add host VLAN client",
        .mhandler.cmd = net_host_device_add,
    },

STEXI
@item host_net_add
@findex host_net_add
Add host VLAN client.
ETEXI

    {
        .name       = "host_net_remove",
        .args_type  = "vlan_id:i,device:s",
        .params     = "vlan_id name",
        .help       = "remove host VLAN client",
        .mhandler.cmd = net_host_device_remove,
    },

STEXI
@item host_net_remove
@findex host_net_remove
Remove host VLAN client.
ETEXI
#endif

    {
        .name       = "netdev_add",
        .args_type  = "netdev:O",
        .params     = "[user|tap|socket],id=str[,prop=value][,...]",
        .help       = "add host network device",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_netdev_add,
    },

STEXI
@item netdev_add
@findex netdev_add
Add host network device.
ETEXI
SQMP
netdev_add
----------

Add host network device.

Arguments:

- "type": the device type, "tap", "user", ... (json-string)
- "id": the device's ID, must be unique (json-string)
- device options

Example:

-> { "execute": "netdev_add", "arguments": { "type": "user", "id": "netdev1" } }
<- { "return": {} }

Note: The supported device options are the same ones supported by the '-net'
      command-line argument, which are listed in the '-help' output or QEMU's
      manual

EQMP

    {
        .name       = "netdev_del",
        .args_type  = "id:s",
        .params     = "id",
        .help       = "remove host network device",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_netdev_del,
    },

STEXI
@item netdev_del
@findex netdev_del
Remove host network device.
ETEXI
SQMP
netdev_del
----------

Remove host network device.

Arguments:

- "id": the device's ID, must be unique (json-string)

Example:

-> { "execute": "netdev_del", "arguments": { "id": "netdev1" } }
<- { "return": {} }

EQMP

#ifdef CONFIG_SLIRP
    {
        .name       = "hostfwd_add",
        .args_type  = "arg1:s,arg2:s?,arg3:s?",
        .params     = "[vlan_id name] [tcp|udp]:[hostaddr]:hostport-[guestaddr]:guestport",
        .help       = "redirect TCP or UDP connections from host to guest (requires -net user)",
        .mhandler.cmd = net_slirp_hostfwd_add,
    },
#endif
STEXI
@item hostfwd_add
@findex hostfwd_add
Redirect TCP or UDP connections from host to guest (requires -net user).
ETEXI

#ifdef CONFIG_SLIRP
    {
        .name       = "hostfwd_remove",
        .args_type  = "arg1:s,arg2:s?,arg3:s?",
        .params     = "[vlan_id name] [tcp|udp]:[hostaddr]:hostport",
        .help       = "remove host-to-guest TCP or UDP redirection",
        .mhandler.cmd = net_slirp_hostfwd_remove,
    },

#endif
STEXI
@item hostfwd_remove
@findex hostfwd_remove
Remove host-to-guest TCP or UDP redirection.
ETEXI

#ifdef CONFIG_LIVE_SNAPSHOTS
    {
        .name       = "transaction",
        .args_type  = "actions:O",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = qmp_marshal_input_transaction,
    },
#endif

SQMP
transaction
-----------

Atomically operate on one or more block devices, snapshotting them
or enabling mirrored writes.  If there is any failure performing
any of the operations, all snapshots for the group are abandoned, and
the original disks pre-snapshot attempt are used.

Mirrored writes keep the previous image file open, and start writing
data also to the new file specified in the command.

A list of dictionaries is accepted, that contains the actions to be performed.

For snapshots this is the device, the file to use for the new snapshot,
and the format.  The default format, if not specified, is qcow2.

Each new snapshot defaults to being created by QEMU (wiping any
contents if the file already exists), but it is also possible to reuse
an externally-created file.  In the latter case, you should ensure that
the new image file has the same contents as the current one; QEMU cannot
perform any meaningful check.  Typically this is achieved by using the
current image file as the backing file for the new image.

Arguments:

actions array:
    - "type": the operation to perform.  The only supported
      values are "blockdev-snapshot-sync" and "mirror". (json-string)
    - "data": a dictionary.  The contents depend on the value
      of "type".  When "type" is "blockdev-snapshot-sync":
      - "device": device name to snapshot (json-string)
      - "snapshot-file": name of new image file (json-string)
      - "format": format of new image (json-string, optional)
      - "mode": whether and how QEMU should create the snapshot file
        (NewImageMode, optional, default "absolute-paths")
      When "type" is "__com.redhat_drive-mirror":
      - "device": device name to snapshot (json-string)
      - "target": name of destination image file (json-string)
      - "format": format of new image (json-string, optional)
      - "full": whether the mirror should include all images or
        just the topmost (json-bool)
      - "mode": how QEMU should look for an existing image file
        (NewImageMode, optional, default "absolute-paths")

Example:

-> { "execute": "transaction",
     "arguments": { "actions": [
         { 'type': 'blockdev-snapshot-sync', 'data' : { "device": "ide-hd0",
                                         "snapshot-file": "/some/place/my-image",
                                         "format": "qcow2" } },
         { 'type': 'blockdev-snapshot-sync', 'data' : { "device": "ide-hd1",
                                         "snapshot-file": "/some/place/my-image2",
                                         "mode": "existing",
                                         "format": "qcow2" } } ] } }
<- { "return": {} }

EQMP

#ifdef CONFIG_LIVE_SNAPSHOTS
    {
        .name       = "blockdev-snapshot-sync",
        .args_type  = "device:B,snapshot-file:s,mode:s?,format:s?",
        .params     = "device [new-image-file] [mode] [format]",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = qmp_marshal_input_blockdev_snapshot_sync,
    },
#endif

SQMP
blockdev-snapshot-sync
----------------------

Synchronous snapshot of a block device. snapshot-file specifies the
target of the new image. If the file exists, or if it is a device, the
snapshot will be created in the existing file/device. If does not
exist, a new file will be created. format specifies the format of the
snapshot image, default is qcow2.

Arguments:

- "device": device name to snapshot (json-string)
- "snapshot-file": name of new image file (json-string)
- "mode": whether and how QEMU should create the snapshot file
  (NewImageMode, optional, default "absolute-paths")
- "full": whether the whole disk should be copied to the destination,
  or only the topmost image (json-bool)
- "format": format of new image (json-string, optional)

Example:

-> { "execute": "blockdev-snapshot", "arguments": { "device": "ide-hd0",
                                                    "snapshot-file":
                                                    "/some/place/my-image",
                                                    "full": false,
                                                    "format": "qcow2" } }
<- { "return": {} }

EQMP

#ifdef CONFIG_LIVE_SNAPSHOTS
    {
        .name       = "__com.redhat_drive-mirror",
        .args_type  = "full:-f,device:B,target:s,mode:s?,format:s?,speed:o?",
        .params     = "device destination-image-file [mode] [format] [speed]",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = qmp_marshal_input___com_redhat_drive_mirror,
    },
#endif

SQMP
__com.redhat_drive-mirror
-------------------------

Start mirroring a block device's writes to a new destination. target
specifies the target of the new image. If the file exists, or if it is
a device, it will be used as the new destination for writes. If does not
exist, a new file will be created. format specifies the format of the
mirror image, default is to probe if mode='existing', else qcow2.

Arguments:

- "device": device name to operate on (json-string)
- "target": name of new image file (json-string)
- "format": format of new image (json-string, optional)
- "speed": the maximum speed, in bytes per second (json-int, optional)
- "mode": how an image file should be created into the target
  file/device (NewImageMode, optional, default 'absolute-paths')
- "full": whether the whole disk should be copied to the destination,
  or only the topmost image (json-bool)

Example:

-> { "execute": "__com.redhat_drive-mirror", "arguments": { "device": "ide-hd0",
                                               "target": "/some/place/my-image",
                                               "format": "qcow2" } }
<- { "return": {} }

EQMP

#ifdef CONFIG_LIVE_SNAPSHOTS
    {
        .name       = "__com.redhat_drive-reopen",
        .args_type  = "device:B,new-image-file:s,format:s?,witness:s?",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = qmp_marshal_input___com_redhat_drive_reopen,
    },
#endif

SQMP
__com.redhat_drive-reopen
-------------------------

Assigns a new image file to a device. Except extremely rare cases where the
guest is expecting the drive to change its content, the new image should
contain the same data of the current one.  One use case is to terminate
a __com.redhat-drive-mirror command.

The command can optionally write a single byte to a file descriptor name
that was passed via SCM rights (getfd).  QEMU will write a single byte
to this file descriptor before completing the command successfully.
If the byte is not written to the file, it is guaranteed that the
guest has not issued any I/O to the new image.  Failure to write the
byte is fatal just like failure to open the new image, and will cause
the guest to revert to the currently open file.


Arguments:

- "device": device name to operate on (json-string)
- "new-image-file": name of new image file (json-string)
- "format": format of new image (json-string, optional)
- "witness": file descriptor previously passed via SCM rights (json-string, optional)

Example:

-> { "execute": "__com.redhat_drive-reopen", "arguments": {"device": "ide-hd0",
                                    "new-image-file": "/some/place/my-image",
                                    "format": "qcow2" } }
<- { "return": {} }

EQMP

    {
        .name       = "balloon",
        .args_type  = "value:M",
        .params     = "target",
        .help       = "request VM to change its memory allocation (in MB)",
        .user_print = monitor_user_noop,
        .mhandler.cmd_async = do_balloon,
        .flags      = MONITOR_CMD_ASYNC,
    },

STEXI
@item balloon @var{value}
@findex balloon
Request VM to change its memory allocation to @var{value} (in MB).
ETEXI
SQMP
balloon
-------

Request VM to change its memory allocation (in bytes).

Arguments:

- "value": New memory allocation (json-int)

Example:

-> { "execute": "balloon", "arguments": { "value": 536870912 } }
<- { "return": {} }

EQMP

    {
        .name       = "set_link",
        .args_type  = "name:s,up:b",
        .params     = "name on|off",
        .help       = "change the link status of a network adapter",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_set_link,
    },

STEXI
@item set_link @var{name} [on|off]
@findex set_link
Switch link @var{name} on (i.e. up) or off (i.e. down).
ETEXI

    {
        .name       = "watchdog_action",
        .args_type  = "action:s",
        .params     = "[reset|shutdown|poweroff|pause|debug|none]",
        .help       = "change watchdog action",
        .mhandler.cmd = do_watchdog_action,
    },

STEXI
@item watchdog_action
@findex watchdog_action
Change watchdog action.
ETEXI

    {
        .name       = "acl_show",
        .args_type  = "aclname:s",
        .params     = "aclname",
        .help       = "list rules in the access control list",
        .mhandler.cmd = do_acl_show,
    },

STEXI
@item acl_show @var{aclname}
@findex acl_show
List all the matching rules in the access control list, and the default
policy. There are currently two named access control lists,
@var{vnc.x509dname} and @var{vnc.username} matching on the x509 client
certificate distinguished name, and SASL username respectively.
ETEXI

    {
        .name       = "acl_policy",
        .args_type  = "aclname:s,policy:s",
        .params     = "aclname allow|deny",
        .help       = "set default access control list policy",
        .mhandler.cmd = do_acl_policy,
    },

STEXI
@item acl_policy @var{aclname} @code{allow|deny}
@findex acl_policy
Set the default access control list policy, used in the event that
none of the explicit rules match. The default policy at startup is
always @code{deny}.
ETEXI

    {
        .name       = "acl_add",
        .args_type  = "aclname:s,match:s,policy:s,index:i?",
        .params     = "aclname match allow|deny [index]",
        .help       = "add a match rule to the access control list",
        .mhandler.cmd = do_acl_add,
    },

STEXI
@item acl_add @var{aclname} @var{match} @code{allow|deny} [@var{index}]
@findex acl_add
Add a match rule to the access control list, allowing or denying access.
The match will normally be an exact username or x509 distinguished name,
but can optionally include wildcard globs. eg @code{*@@EXAMPLE.COM} to
allow all users in the @code{EXAMPLE.COM} kerberos realm. The match will
normally be appended to the end of the ACL, but can be inserted
earlier in the list if the optional @var{index} parameter is supplied.
ETEXI

    {
        .name       = "acl_remove",
        .args_type  = "aclname:s,match:s",
        .params     = "aclname match",
        .help       = "remove a match rule from the access control list",
        .mhandler.cmd = do_acl_remove,
    },

STEXI
@item acl_remove @var{aclname} @var{match}
@findex acl_remove
Remove the specified match rule from the access control list.
ETEXI

    {
        .name       = "acl_reset",
        .args_type  = "aclname:s",
        .params     = "aclname",
        .help       = "reset the access control list",
        .mhandler.cmd = do_acl_reset,
    },

STEXI
@item acl_reset @var{aclname}
@findex acl_reset
Remove all matches from the access control list, and set the default
policy back to @code{deny}.
ETEXI

#if defined(TARGET_I386)

    {
        .name       = "mce",
        .args_type  = "cpu_index:i,bank:i,status:l,mcg_status:l,addr:l,misc:l",
        .params     = "cpu bank status mcgstatus addr misc",
        .help       = "inject a MCE on the given CPU",
        .mhandler.cmd = do_inject_mce,
    },

#endif
STEXI
@item mce @var{cpu} @var{bank} @var{status} @var{mcgstatus} @var{addr} @var{misc}
@findex mce (x86)
Inject an MCE on the given CPU (x86 only).
ETEXI

    {
        .name       = "getfd",
        .args_type  = "fdname:s",
        .params     = "getfd name",
        .help       = "receive a file descriptor via SCM rights and assign it a name",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_getfd,
    },

STEXI
@item getfd @var{fdname}
@findex getfd
If a file descriptor is passed alongside this command using the SCM_RIGHTS
mechanism on unix sockets, it is stored using the name @var{fdname} for
later use by other monitor commands.
ETEXI
SQMP
getfd
-----

Receive a file descriptor via SCM rights and assign it a name.

Arguments:

- "fdname": file descriptor name (json-string)

Example:

-> { "execute": "getfd", "arguments": { "fdname": "fd1" } }
<- { "return": {} }

EQMP

    {
        .name       = "closefd",
        .args_type  = "fdname:s",
        .params     = "closefd name",
        .help       = "close a file descriptor previously passed via SCM rights",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_closefd,
    },

STEXI
@item closefd @var{fdname}
@findex closefd
Close the file descriptor previously assigned to @var{fdname} using the
@code{getfd} command. This is only needed if the file descriptor was never
used by another monitor command.
ETEXI
SQMP
closefd
-------

Close a file descriptor previously passed via SCM rights.

Arguments:

- "fdname": file descriptor name (json-string)

Example:

-> { "execute": "closefd", "arguments": { "fdname": "fd1" } }
<- { "return": {} }

EQMP

    {
        .name       = "block_passwd",
        .args_type  = "device:B,password:s",
        .params     = "block_passwd device password",
        .help       = "set the password of encrypted block devices",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_block_set_passwd,
    },

STEXI
@item block_passwd @var{device} @var{password}
@findex block_passwd
Set the encrypted device @var{device} password to @var{password}
ETEXI
SQMP
block_passwd
------------

Set the password of encrypted block devices.

Arguments:

- "device": device name (json-string)
- "password": password (json-string)

Example:

-> { "execute": "block_passwd", "arguments": { "device": "ide0-hd0",
                                               "password": "12345" } }
<- { "return": {} }

EQMP

    {
        .name       = "cpu_set",
        .args_type  = "cpu:i,state:s",
        .params     = "cpu [online|offline]",
        .help       = "change cpu state",
        .mhandler.cmd  = do_cpu_set_nr,
    },

STEXI
@item cpu_set @var{cpu} [online|offline]
@findex cpu_set
Set CPU @var{cpu} online or offline.
ETEXI

    {
        .name       = "set_password",
        .args_type  = "protocol:s,password:s,connected:s?",
        .params     = "protocol password action-if-connected",
        .help       = "set spice/vnc password",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = set_password,
    },

SQMP
set_password
------------

Set the password for vnc/spice protocols.

Arguments:

- "protocol": protocol name (json-string)
- "password": password (json-string)
- "connected": [ keep | disconnect | fail ] (josn-string, optional)

Example:

-> { "execute": "set_password", "arguments": { "protocol": "vnc",
                                               "password": "secret" } }
<- { "return": {} }

EQMP

    {
        .name       = "expire_password",
        .args_type  = "protocol:s,time:s",
        .params     = "protocol time",
        .help       = "set spice/vnc password expire-time",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = expire_password,
    },

SQMP
expire_password
---------------

Set the password expire time for vnc/spice protocols.

Arguments:

- "protocol": protocol name (json-string)
- "time": [ now | never | +secs | secs ] (json-string)

Example:

-> { "execute": "expire_password", "arguments": { "protocol": "vnc",
                                                  "time": "+60" } }
<- { "return": {} }

EQMP

    {
        .name       = RFQDN_REDHAT "set_password",
        .args_type  = "protocol:s,password:s,expiration:i,connected:s?",
        .params     = "protocol password expiration action-if-connected",
        .help       = "set spice/vnc password",
	.user_print = monitor_user_noop,
        .mhandler.cmd_new = redhat_set_password,
    },
    {
        .name       = RFQDN_REDHAT "spice_migrate_info",
        .args_type  = "hostname:s,port:i?,tls-port:i?,cert-subject:s?",
        .params     = "hostname port tls-port cert-subject",
        .help       = "send migration info to spice client",
	.user_print = monitor_user_noop,
        .mhandler.cmd_async = redhat_spice_migrate_info,
        .flags      = MONITOR_CMD_ASYNC,
    },


    {
        .name       = "qmp_capabilities",
        .args_type  = "",
        .params     = "",
        .help       = "enable QMP capabilities",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_qmp_capabilities,
    },

STEXI
@item qmp_capabilities
@findex qmp_capabilities
Enable the specified QMP capabilities
ETEXI
SQMP
qmp_capabilities
----------------

Enable QMP capabilities.

Arguments: None.

Example:

-> { "execute": "qmp_capabilities" }
<- { "return": {} }

Note: This command must be issued before issuing any other command.

EQMP

    {
        .name       = "human-monitor-command",
        .args_type  = "command-line:s,cpu-index:i?",
        .params     = "",
        .help       = "",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_hmp_passthrough,
    },

SQMP
human-monitor-command
---------------------

Execute a Human Monitor command.

Arguments: 

- command-line: the command name and its arguments, just like the
                Human Monitor's shell (json-string)
- cpu-index: select the CPU number to be used by commands which access CPU
             data, like 'info registers'. The Monitor selects CPU 0 if this
             argument is not provided (json-int, optional)

Example:

-> { "execute": "human-monitor-command", "arguments": { "command-line": "info kvm" } }
<- { "return": "kvm support: enabled\r\n" }

Notes:

(1) The Human Monitor is NOT an stable interface, this means that command
    names, arguments and responses can change or be removed at ANY time.
    Applications that rely on long term stability guarantees should NOT
    use this command

(2) Limitations:

    o This command is stateless, this means that commands that depend
      on state information (such as getfd) might not work

    o Commands that prompt the user for data (eg. 'cont' when the block
      device is encrypted) don't currently work

EQMP

    {
        .name       = RFQDN_REDHAT "drive_add",
        .args_type  = "simple-drive:O",
        .params     = "id=name,[file=file][,format=f][,media=d]...",
        .help       = "Create a drive similar to -device if=none.",
	.user_print = monitor_user_noop,
        .mhandler.cmd_new = simple_drive_add,
    },

STEXI
@item __com.redhat_drive_add
@findex __com.redhat_drive_add
Create a drive similar to -device if=none.
ETEXI
SQMP
__com.redhat_drive_add
----------------------

Create a drive similar to -device if=none.

Arguments:

- "id": Drive ID, must be unique (json-string)
- "file": Disk image (json-string, optional)
- "format": Disk format (json-string, optional)
- "aio": How to perform asynchronous disk I/O (json-string, optional)
- "cache": Host cache use policy (json-string, optional)
- "cyls", "heads", "secs": Disk geometry (json-int, optional)
- "trans": BIOS translation mode (json-string, optional)
- "media": Media type (json-string, optional)
- "readonly": Open image read-only (json-bool, optional)
- "rerror": What to do on read error (json-string, optional)
- "werror": What to do on write error (json-string, optional)
- "serial": Drive serial number (json-string, optional)
- "snapshot": Enable snapshot mode (json-bool, optional)
- "copy-on-read": Enable copy-on-read mode (json-bool, optional)

Example:

1. Add a drive without medium:

-> { "execute": "__com.redhat_drive_add", "arguments": { "id": "foo" } }
<- {"return": {}}

2. Add a drive with 

-> { "execute": "__com.redhat_drive_add",
     "arguments": { "id": "bar", "file": "tmp.qcow2", "format": "qcow2" } }
<- {"return": {}}

EQMP

#ifdef CONFIG_BLOCK_STREAM
    {
        .name       = "block-stream",
        .args_type  = "device:B,speed:o?,base:s?",
        .params     = "device [speed [base]]",
        .help       = "background copy backing file into a block device",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_block_stream,
    },
#endif

SQMP
block-stream
------------

Copy data from a backing file into a block device.

The block streaming operation is performed in the background until the entire
backing file has been copied.  This command returns immediately once streaming
has started.  The status of ongoing block streaming operations can be checked
with query-block-jobs.  The operation can be stopped before it has completed
using the block-job-cancel command.

If a base file is specified then sectors are not copied from that base file and
its backing chain.  When streaming completes the image file will have the base
file as its backing file.  This can be used to stream a subset of the backing
file chain instead of flattening the entire image.

On successful completion the image file is updated to drop the backing file
and the BLOCK_JOB_COMPLETED event is emitted.

Arguments:

- device: the device name (json-string)
- speed:  the rate limit, bytes per second (json-int, optional)
- base:   the common backing file name (json-string, optional)

Returns:

Nothing on success.
If streaming is already active on this device, DeviceInUse.
If device does not exist, DeviceNotFound.
If image streaming is not supported by this device, NotSupported.
If base does not exist, BaseNotFound

EQMP

    {
        .name       = "block-job-set-speed",
        .args_type  = "device:B,speed:o",
        .params     = "device speed",
        .help       = "set maximum speed for a background block operation",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_block_job_set_speed,
    },

STEXI
@item block-job-set-speed
@findex block-job-set-speed
Set maximum speed for a background block operation.
ETEXI

SQMP
block-job-set-speed
-------------------

Set maximum speed for a background block operation.

This command can only be issued when there is an active block job.

Throttling can be disabled by setting the speed to 0.

Arguments:

- device: the device name
- value:  the maximum speed, in bytes per second

Returns:

Nothing on success
If the job type does not support throttling, NotSupported
If streaming is not active on this device, DeviceNotActive

Example:

-> { "execute": "block-job-set-speed",
    "arguments": { "device": "virtio0", "value": 1024 } }
EQMP

    {
        .name       = "block-job-cancel",
        .args_type  = "device:B",
        .params     = "device",
        .help       = "stop an active block streaming operation",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_block_job_cancel,
    },

STEXI
@item block-job-cancel
@findex block-job-cancel
Stop an active block streaming operation.
ETEXI

SQMP
block-job-cancel
----------------

Stop an active block streaming operation.

This command returns immediately after marking the active block streaming
operation for cancellation.  It is an error to call this command if no
operation is in progress.

The operation will cancel as soon as possible and then emit the
BLOCK_JOB_CANCELLED event.  Before that happens the job is still visible when
enumerated using query-block-jobs.

The image file retains its backing file unless the streaming operation happens
to complete just as it is being cancelled.

A new block streaming operation can be started at a later time to finish
copying all data from the backing file.

Arguments:

- device: the device name

Returns:

Nothing on success
If streaming is not active on this device, DeviceNotActive
If cancellation already in progress, DeviceInUse
EQMP

HXCOMM Keep the 'info' command at the end!
HXCOMM This is required for the QMP documentation layout.

SQMP

3. Query Commands
=================

EQMP

    {
        .name       = "info",
        .args_type  = "item:s?",
        .params     = "[subcommand]",
        .help       = "show various information about the system state",
        .user_print = monitor_user_noop,
        .mhandler.cmd_new = do_info,
    },

STEXI
@item info @var{subcommand}
@findex info
Show various information about the system state.

@table @option
@item info version
show the version of QEMU
ETEXI
SQMP
query-version
-------------

Show QEMU version.

Return a json-object with the following information:

- "qemu": A json-object containing three integer values:
    - "major": QEMU's major version (json-int)
    - "minor": QEMU's minor version (json-int)
    - "micro": QEMU's micro version (json-int)
- "package": package's version (json-string)

Example:

-> { "execute": "query-version" }
<- {
      "return":{
         "qemu":{
            "major":0,
            "minor":11,
            "micro":5
         },
         "package":""
      }
   }

EQMP

STEXI
@item info commands
list QMP available commands
ETEXI
SQMP
query-commands
--------------

List QMP available commands.

Each command is represented by a json-object, the returned value is a json-array
of all commands.

Each json-object contain:

- "name": command's name (json-string)

Example:

-> { "execute": "query-commands" }
<- {
      "return":[
         {
            "name":"query-balloon"
         },
         {
            "name":"system_powerdown"
         }
      ]
   }

Note: This example has been shortened as the real response is too long.

EQMP

STEXI
@item info network
show the various VLANs and the associated devices
ETEXI

STEXI
@item info chardev
show the character devices
ETEXI
SQMP
query-chardev
-------------

Each device is represented by a json-object. The returned value is a json-array
of all devices.

Each json-object contain the following:

- "label": device's label (json-string)
- "filename": device's file (json-string)

Example:

-> { "execute": "query-chardev" }
<- {
      "return":[
         {
            "label":"monitor",
            "filename":"stdio"
         },
         {
            "label":"serial0",
            "filename":"vc"
         }
      ]
   }

EQMP

STEXI
@item info block
show the block devices
ETEXI
SQMP
query-block
-----------

Show the block devices.

Each block device information is stored in a json-object and the returned value
is a json-array of all devices.

Each json-object contain the following:

- "device": device name (json-string)
- "type": device type (json-string)
         - deprecated, retained for backward compatibility
         - Possible values: "unknown"
- "removable": true if the device is removable, false otherwise (json-bool)
- "locked": true if the device is locked, false otherwise (json-bool)
- "tray-open": only present if removable, true if the device has a tray,
               and it is open (json-bool)
- "inserted": only present if the device is inserted, it is a json-object
   containing the following:
         - "file": device file name (json-string)
         - "ro": true if read-only, false otherwise (json-bool)
         - "drv": driver format name (json-string)
             - Possible values: "blkdebug", "bochs", "cloop", "cow", "dmg",
                                "file", "file", "ftp", "ftps", "host_cdrom",
                                "host_device", "host_floppy", "http", "https",
                                "nbd", "parallels", "qcow", "qcow2", "raw",
                                "tftp", "vdi", "vmdk", "vpc", "vvfat"
         - "backing_file": backing file name (json-string, optional)
         - "encrypted": true if encrypted, false otherwise (json-bool)
- "io-status": I/O operation status, only present if the device supports it
               and the VM is configured to stop on errors. It's always reset
               to "ok" when the "cont" command is issued (json_string, optional)
             - Possible values: "ok", "failed", "nospace"

Example:

-> { "execute": "query-block" }
<- {
      "return":[
         {
            "io-status": "ok",
            "device":"ide0-hd0",
            "locked":false,
            "removable":false,
            "inserted":{
               "ro":false,
               "drv":"qcow2",
               "encrypted":false,
               "file":"disks/test.img"
            },
            "type":"unknown"
         },
         {
            "io-status": "ok",
            "device":"ide1-cd0",
            "locked":false,
            "removable":true,
            "type":"unknown"
         },
         {
            "device":"floppy0",
            "locked":false,
            "removable":true,
            "type":"unknown"
         },
         {
            "device":"sd0",
            "locked":false,
            "removable":true,
            "type":"unknown"
         }
      ]
   }

EQMP

STEXI
@item info blockstats
show block device statistics
ETEXI
SQMP
query-blockstats
----------------

Show block device statistics.

Each device statistic information is stored in a json-object and the returned
value is a json-array of all devices.

Each json-object contain the following:

- "device": device name (json-string)
- "stats": A json-object with the statistics information, it contains:
    - "rd_bytes": bytes read (json-int)
    - "wr_bytes": bytes written (json-int)
    - "rd_operations": read operations (json-int)
    - "wr_operations": write operations (json-int)
    - "flush_operations": cache flush operations (json-int)
    - "wr_total_time_ns": total time spend on writes in nano-seconds (json-int)
    - "rd_total_time_ns": total time spend on reads in nano-seconds (json-int)
    - "flush_total_time_ns": total time spend on cache flushes in nano-seconds (json-int)
    - "wr_highest_offset": Highest offset of a sector written since the
                           BlockDriverState has been opened (json-int)
- "parent": Contains recursively the statistics of the underlying
            protocol (e.g. the host file for a qcow2 image). If there is
            no underlying protocol, this field is omitted
            (json-object, optional)

Example:

-> { "execute": "query-blockstats" }
<- {
      "return":[
         {
            "device":"ide0-hd0",
            "parent":{
               "stats":{
                  "wr_highest_offset":3686448128,
                  "wr_bytes":9786368,
                  "wr_operations":751,
                  "rd_bytes":122567168,
                  "rd_operations":36772
                  "wr_total_times_ns":313253456
                  "rd_total_times_ns":3465673657
                  "flush_total_times_ns":49653
                  "flush_operations":61,
               }
            },
            "stats":{
               "wr_highest_offset":2821110784,
               "wr_bytes":9786368,
               "wr_operations":692,
               "rd_bytes":122739200,
               "rd_operations":36604
               "flush_operations":51,
               "wr_total_times_ns":313253456
               "rd_total_times_ns":3465673657
               "flush_total_times_ns":49653
            }
         },
         {
            "device":"ide1-cd0",
            "stats":{
               "wr_highest_offset":0,
               "wr_bytes":0,
               "wr_operations":0,
               "rd_bytes":0,
               "rd_operations":0
               "flush_operations":0,
               "wr_total_times_ns":0
               "rd_total_times_ns":0
               "flush_total_times_ns":0
            }
         },
         {
            "device":"floppy0",
            "stats":{
               "wr_highest_offset":0,
               "wr_bytes":0,
               "wr_operations":0,
               "rd_bytes":0,
               "rd_operations":0
               "flush_operations":0,
               "wr_total_times_ns":0
               "rd_total_times_ns":0
               "flush_total_times_ns":0
            }
         },
         {
            "device":"sd0",
            "stats":{
               "wr_highest_offset":0,
               "wr_bytes":0,
               "wr_operations":0,
               "rd_bytes":0,
               "rd_operations":0
               "flush_operations":0,
               "wr_total_times_ns":0
               "rd_total_times_ns":0
               "flush_total_times_ns":0
            }
         }
      ]
   }

EQMP

STEXI
@item info registers
show the cpu registers
@item info cpus
show infos for each CPU
ETEXI
SQMP
query-cpus
----------

Show CPU information.

Return a json-array. Each CPU is represented by a json-object, which contains:

- "CPU": CPU index (json-int)
- "current": true if this is the current CPU, false otherwise (json-bool)
- "halted": true if the cpu is halted, false otherwise (json-bool)
- Current program counter. The key's name depends on the architecture:
     "pc": i386/x86_64 (json-int)
     "nip": PPC (json-int)
     "pc" and "npc": sparc (json-int)
     "PC": mips (json-int)

Example:

-> { "execute": "query-cpus" }
<- {
      "return":[
         {
            "CPU":0,
            "current":true,
            "halted":false,
            "pc":3227107138
         },
         {
            "CPU":1,
            "current":false,
            "halted":true,
            "pc":7108165
         }
      ]
   }

EQMP

STEXI
@item info history
show the command line history
@item info irq
show the interrupts statistics (if available)
@item info pic
show i8259 (PIC) state
ETEXI

STEXI
@item info pci
show emulated PCI device info
@item info tlb
show virtual to physical memory mappings (i386 only)
@item info mem
show the active virtual memory mappings (i386 only)
ETEXI

STEXI
@item info jit
show dynamic compiler info
@item info kvm
show KVM information
@item info numa
show NUMA information
ETEXI

STEXI
@item info kvm
show KVM information
ETEXI
SQMP
query-kvm
---------

Show KVM information.

Return a json-object with the following information:

- "enabled": true if KVM support is enabled, false otherwise (json-bool)
- "present": true if QEMU has KVM support, false otherwise (json-bool)

Example:

-> { "execute": "query-kvm" }
<- { "return": { "enabled": true, "present": true } }

EQMP

STEXI
@item info usb
show USB devices plugged on the virtual USB hub
@item info usbhost
show all USB host devices
@item info profile
show profiling information
@item info capture
show information about active capturing
@item info snapshots
show list of VM snapshots
ETEXI

STEXI
@item info status
show the current VM status (running|paused)
ETEXI
SQMP
query-status
------------

Return a json-object with the following information:

- "running": true if the VM is running, or false if it is paused (json-bool)
- "singlestep": true if the VM is in single step mode,
                false otherwise (json-bool)
- "status": one of the following values (json-string)
    "debug" - QEMU is running on a debugger
    "inmigrate" - guest is paused waiting for an incoming migration
    "internal-error" - An internal error that prevents further guest
    execution has occurred
    "io-error" - the last IOP has failed and the device is configured
    to pause on I/O errors
    "paused" - guest has been paused via the 'stop' command
    "postmigrate" - guest is paused following a successful 'migrate'
    "prelaunch" - QEMU was started with -S and guest has not started
    "finish-migrate" - guest is paused to finish the migration process
    "restore-vm" - guest is paused to restore VM state
    "running" - guest is actively running
    "save-vm" - guest is paused to save the VM state
    "shutdown" - guest is shut down (and -no-shutdown is in use)
    "watchdog" - the watchdog action is configured to pause and
     has been triggered

Example:

-> { "execute": "query-status" }
<- { "return": { "running": true, "singlestep": false, "status": "running" } }

EQMP

STEXI
@item info pcmcia
show guest PCMCIA status
ETEXI

STEXI
@item info mice
show which guest mouse is receiving events
ETEXI
SQMP
query-mice
----------

Show VM mice information.

Each mouse is represented by a json-object, the returned value is a json-array
of all mice.

The mouse json-object contains the following:

- "name": mouse's name (json-string)
- "index": mouse's index (json-int)
- "current": true if this mouse is receiving events, false otherwise (json-bool)
- "absolute": true if the mouse generates absolute input events (json-bool)

Example:

-> { "execute": "query-mice" }
<- {
      "return":[
         {
            "name":"QEMU Microsoft Mouse",
            "index":0,
            "current":false,
            "absolute":false
         },
         {
            "name":"QEMU PS/2 Mouse",
            "index":1,
            "current":true,
            "absolute":true
         }
      ]
   }

EQMP

STEXI
@item info vnc
show the vnc server status
ETEXI
SQMP
query-vnc
---------

Show VNC server information.

Return a json-object with server information. Connected clients are returned
as a json-array of json-objects.

The main json-object contains the following:

- "enabled": true or false (json-bool)
- "host": server's IP address (json-string)
- "family": address family (json-string)
         - Possible values: "ipv4", "ipv6", "unix", "unknown"
- "service": server's port number (json-string)
- "auth": authentication method (json-string)
         - Possible values: "invalid", "none", "ra2", "ra2ne", "sasl", "tight",
                            "tls", "ultra", "unknown", "vencrypt", "vencrypt",
                            "vencrypt+plain", "vencrypt+tls+none",
                            "vencrypt+tls+plain", "vencrypt+tls+sasl",
                            "vencrypt+tls+vnc", "vencrypt+x509+none",
                            "vencrypt+x509+plain", "vencrypt+x509+sasl",
                            "vencrypt+x509+vnc", "vnc"
- "clients": a json-array of all connected clients

Clients are described by a json-object, each one contain the following:

- "host": client's IP address (json-string)
- "family": address family (json-string)
         - Possible values: "ipv4", "ipv6", "unix", "unknown"
- "service": client's port number (json-string)
- "x509_dname": TLS dname (json-string, optional)
- "sasl_username": SASL username (json-string, optional)

Example:

-> { "execute": "query-vnc" }
<- {
      "return":{
         "enabled":true,
         "host":"0.0.0.0",
         "service":"50402",
         "auth":"vnc",
         "family":"ipv4",
         "clients":[
            {
               "host":"127.0.0.1",
               "service":"50401",
               "family":"ipv4"
            }
         ]
      }
   }

EQMP

STEXI
@item info name
show the current VM name
ETEXI
SQMP
query-spice
-----------

Show SPICE server information.

Return a json-object with server information. Connected clients are returned
as a json-array of json-objects.

The main json-object contains the following:

- "enabled": true or false (json-bool)
- "host": server's IP address (json-string)
- "port": server's port number (json-int, optional)
- "tls-port": server's port number (json-int, optional)
- "auth": authentication method (json-string)
         - Possible values: "none", "spice"
- "channels": a json-array of all active channels clients

Channels are described by a json-object, each one contain the following:

- "host": client's IP address (json-string)
- "family": address family (json-string)
         - Possible values: "ipv4", "ipv6", "unix", "unknown"
- "port": client's port number (json-string)
- "connection-id": spice connection id.  All channels with the same id
                   belong to the same spice session (json-int)
- "channel-type": channel type.  "1" is the main control channel, filter for
                  this one if you want track spice sessions only (json-int)
- "channel-id": channel id.  Usually "0", might be different needed when
                multiple channels of the same type exist, such as multiple
                display channels in a multihead setup (json-int)
- "tls": whevener the channel is encrypted (json-bool)

Example:

-> { "execute": "query-spice" }
<- {
      "return": {
         "enabled": true,
         "auth": "spice",
         "port": 5920,
         "tls-port": 5921,
         "host": "0.0.0.0",
         "channels": [
            {
               "port": "54924",
               "family": "ipv4",
               "channel-type": 1,
               "connection-id": 1804289383,
               "host": "127.0.0.1",
               "channel-id": 0,
               "tls": true
            },
            {
               "port": "36710",
               "family": "ipv4",
               "channel-type": 4,
               "connection-id": 1804289383,
               "host": "127.0.0.1",
               "channel-id": 0,
               "tls": false
            },
            [ ... more channels follow ... ]
         ]
      }
   }

EQMP

SQMP
query-name
----------

Show VM name.

Return a json-object with the following information:

- "name": VM's name (json-string, optional)

Example:

-> { "execute": "query-name" }
<- { "return": { "name": "qemu-name" } }

EQMP

STEXI
@item info uuid
show the current VM UUID
ETEXI
SQMP
query-uuid
----------

Show VM UUID.

Return a json-object with the following information:

- "UUID": Universally Unique Identifier (json-string)

Example:

-> { "execute": "query-uuid" }
<- { "return": { "UUID": "550e8400-e29b-41d4-a716-446655440000" } }

EQMP

STEXI
@item info cpustats
show CPU statistics
@item info usernet
show user network stack connection states
ETEXI

STEXI
@item info migrate
show migration status
ETEXI
SQMP
query-migrate
-------------

Migration status.

Return a json-object. If migration is active there will be another json-object
with RAM migration status and if block migration is active another one with
block migration status.

The main json-object contains the following:

- "status": migration status (json-string)
     - Possible values: "active", "completed", "failed", "cancelled"
- "ram": only present if "status" is "active", it is a json-object with the
  following RAM information (in bytes):
         - "transferred": amount transferred (json-int)
         - "remaining": amount remaining (json-int)
         - "total": total (json-int)
- "disk": only present if "status" is "active" and it is a block migration,
  it is a json-object with the following disk information (in bytes):
         - "transferred": amount transferred (json-int)
         - "remaining": amount remaining (json-int)
         - "total": total (json-int)

Examples:

1. Before the first migration

-> { "execute": "query-migrate" }
<- { "return": {} }

2. Migration is done and has succeeded

-> { "execute": "query-migrate" }
<- { "return": { "status": "completed" } }

3. Migration is done and has failed

-> { "execute": "query-migrate" }
<- { "return": { "status": "failed" } }

4. Migration is being performed and is not a block migration:

-> { "execute": "query-migrate" }
<- {
      "return":{
         "status":"active",
         "ram":{
            "transferred":123,
            "remaining":123,
            "total":246
         }
      }
   }

5. Migration is being performed and is a block migration:

-> { "execute": "query-migrate" }
<- {
      "return":{
         "status":"active",
         "ram":{
            "total":1057024,
            "remaining":1053304,
            "transferred":3720
         },
         "disk":{
            "total":20971520,
            "remaining":20880384,
            "transferred":91136
         }
      }
   }

EQMP

STEXI
@item info balloon
show balloon information
ETEXI
SQMP
query-balloon
-------------

Show balloon information.

Make an asynchronous request for balloon info. When the request completes a
json-object will be returned containing the following data:

- "actual": current balloon value in bytes (json-int)
- "mem_swapped_in": Amount of memory swapped in bytes (json-int, optional)
- "mem_swapped_out": Amount of memory swapped out in bytes (json-int, optional)
- "major_page_faults": Number of major faults (json-int, optional)
- "minor_page_faults": Number of minor faults (json-int, optional)
- "free_mem": Total amount of free and unused memory in
              bytes (json-int, optional)
- "total_mem": Total amount of available memory in bytes (json-int, optional)

Example:

-> { "execute": "query-balloon" }
<- {
      "return":{
         "actual":1073741824,
         "mem_swapped_in":0,
         "mem_swapped_out":0,
         "major_page_faults":142,
         "minor_page_faults":239245,
         "free_mem":1014185984,
         "total_mem":1044668416
      }
   }

EQMP

STEXI
@item info qtree
show device tree
@item info qdm
show qdev device model list
@item info roms
show roms
@item info block-jobs
show long-running block device operations
ETEXI

SQMP
query-block-jobs
----------------

Return a list of block job objects for each active block job containing the
following fields:

- type: the job type (json-string, 'stream' for image streaming)
- device: the block device name (json-string)
- len: the maximum progress value (json-int)
- offset: the current progress value (json-int)
- speed: the rate limit, bytes per second (json-int)
EQMP

STEXI
@end table
ETEXI

HXCOMM DO NOT add new commands after 'info', move your addition before it!

STEXI
@end table
ETEXI
