# build-time settings:
# Define rhev as the first variable
%define rhev 0

%if 0%{?rhev_test}
%define enable_fake_machine 1
%else
%define enable_fake_machine 0
%endif

# --with/--without variables:
# - guest_agent: build qemu-guest-agent subpackage
# - rhev_features: enable rhev features on configure, such as
#                  - live snapshots,
#                  - streaming,
#                  - mirror,
#                  - etc.

%if 0%{?rhev}
%bcond_without  rhev_features   # enabled
%bcond_with     guest_agent     # disabled
%else
%bcond_with     rhev_features   # disabled
%bcond_without  guest_agent     # enabled
%endif

%if %{with guest_agent}
%define build_arches i686 x86_64
%else
%define build_arches x86_64
%endif

%ifarch i686
%bcond_with     qemu_kvm              # disabled
%bcond_with     guest_agent_win32     # disabled - mingw is only available for
                                      #            x86_64
%else
%bcond_without  qemu_kvm              # enabled
%if %{with guest_agent}
%bcond_without  guest_agent_win32     # enabled
%endif # with guest_agent
%endif

# Package name and path configuration variables:
# - pkgname: the package name (qemu-kvm or qemu-kvm-rhev)
# - pkgsuffix: suffix for package names that are not "qemu-kvm-*" (e.g.
#   qemu-img and qemu-guest-agent). optional.
# - obsoletes_ver: version that packages will obsolete. Used to make the qemu-kvm-rhev
#   package obsolete old qemu-kvm packages that were present on RHEV
# - confname: "conf suffix", name for config file directories, data directories, etc.
# - progname: name of the qemu-kvm binary on /usr/libexec

# RHEV-specific changes:
%if 0%{?rhev}
# RHEV package:
# we will add qemu-kvm/qemu-img/etc as provides
%define extra_provides_suffix %{nil}
# Obsolete all qemu-kvm/qemu-img/etc versions[1], so users with both RHEL and
# RHEV channels will get the qemu-kvm-rhev package.
# [1] unless one day we want to revert it, then qemu-kvm Epoch should be
# increased to 10
%define obsoletes_ver   10:0-0
%define pkgsuffix       -rhev
# conflict with RHEL packages:
%define conflicts_suffix -rhel
# older RHEL packages didn't have the qemu-kvm-rhel/qemu-img-rhel provides:
%define old_conflict_ver 2:0.12.1.2-2.352.el6
%else
# RHEL package:
# conflict with RHEV packages:
%define conflicts_suffix -rhev
# We will provide "qemu-kvm-rhel" and "qemu-img-rhel" as well, to make
# it possible for the RHEV package to add a Conflicts line
%define extra_provides_suffix -rhel
%endif

%define confname qemu-kvm
%define progname qemu-kvm
%define pkgname      qemu-kvm%{?pkgsuffix}




# Versions of various parts:

# Polite request for people who spin their own qemu-kvm rpms:
# please modify the "buildid" define in a way that identifies
# that the kernel isn't the stock distribution qemu-kvm, for example,
# by setting the define to ".local" or ".bz123456"

%define zrelease 5
%define buildid .CROC1

%define sublevel 0.12.1.2
%define pkgrelease 2.355

%define rpmversion %{sublevel}
%define full_release %{pkgrelease}%{?dist}.%{?zrelease}%{?buildid}

# rhel_rhev_conflicts:
# reusable macro for the many conflicts/provides/obsoletes settings
# that are present on multiple subpackages
# Parameters:
#   %1 - package name (e.g qemu-kvm, qemu-img)
%define rhel_rhev_conflicts()                                                  \
%if 0%{?conflicts_suffix:1}                                                    \
# this is used to make *-rhev conflict with *-rhel and vice-versa              \
Conflicts: %1%{conflicts_suffix}                                               \
%endif                                                                         \
%if 0%{?old_conflict_ver:1}                                                    \
# Older qemu-kvm versions from RHEL didn't provide qemu-kvm-rhel, so           \
# we conflict with the qemu-kvm name directly                                  \
Conflicts: %1 <= %{old_conflict_ver}                                           \
%endif                                                                         \
%if 0%{?extra_provides_suffix:1}                                               \
# - qemu-kvm will provide qemu-kvm-rhel to make it easier for the RHEV         \
#   package to conflict with it                                                \
# - qemu-kvm-rhev will provide qemu-kvm, so all other packages that            \
#   reference qemu-kvm will accept it                                          \
Provides: %1%{extra_provides_suffix} = %{epoch}:%{version}-%{release}          \
%endif                                                                         \
%if 0%{?obsoletes_ver:1}                                                       \
# qemu-kvm-rhev will obsolete all older qemu-kvm packages, up to               \
# %{obsoletes_ver}                                                             \
Obsoletes: %1 < %{obsoletes_ver}                                               \
%endif


%if %{enable_fake_machine}
Summary: Userspace component of KVM (testing only)
%else
Summary: Userspace component of KVM
%endif
Name: %{pkgname}
Version: %{rpmversion}
Release: %{full_release}
# Before this release it was %(date +%s) for CROC packages - stop epoch
# incrementing.
Epoch: 1366118257
License: GPLv2+ and LGPLv2+ and BSD
Group: Development/Tools
URL: http://www.linux-kvm.org
Provides: %name = %version-%release
ExclusiveArch: %{build_arches}
%rhel_rhev_conflicts qemu-kvm

Source0: http://downloads.sourceforge.net/sourceforge/kvm/qemu-kvm-%{version}.tar.gz

# Loads kvm kernel modules at boot
Source2: kvm.modules

# Creates /dev/kvm
Source3: 80-kvm.rules

# KSM control scripts
Source4: ksm.init
Source5: ksm.sysconfig
Source6: ksmtuned.init
Source7: ksmtuned
Source8: ksmtuned.conf

# Blacklist vhost-net for RHEL6.0 GA
Source9: blacklist-kvm.conf

# Qemu-guest-agent control scripts
Source10: qemu-ga.init
Source11: qemu-ga.sysconfig

# Windows guest agent installation docs
Source12: README-qemu-ga-win32.txt

# Change datadir to /usr/share/qemu-kvm
Patch1000: qemu-change-share-suffix.patch
# Install manpage as qemu-kvm(1)
Patch1001: qemu-rename-manpage.patch
# Change SASL server name to qemu-kvm
Patch1002: qemu-rename-sasl-server-name.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1003: kvm-virtio-Remove-duplicate-macro-definition-for-max.-vi.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1004: kvm-virtio-console-qdev-conversion-new-virtio-serial-bus.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1005: kvm-virtio-serial-bus-Maintain-guest-and-host-port-open-.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1006: kvm-virtio-serial-bus-Add-a-port-name-property-for-port-.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1007: kvm-virtio-serial-bus-Add-support-for-buffering-guest-ou.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1008: kvm-virtio-serial-bus-Add-ability-to-hot-unplug-ports.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1009: kvm-virtio-serial-Add-a-virtserialport-device-for-generi.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1010: kvm-Move-virtio-serial-to-Makefile.hw.patch
# For bz#556459 - RFE - In-place backing file format change
Patch1011: kvm-block-Introduce-BDRV_O_NO_BACKING.patch
# For bz#556459 - RFE - In-place backing file format change
Patch1012: kvm-block-Add-bdrv_change_backing_file.patch
# For bz#556459 - RFE - In-place backing file format change
Patch1013: kvm-qemu-img-rebase.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1014: kvm-virtio-serial-bus-Remove-guest-buffer-caching-and-th.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1015: kvm-virtio-serial-Make-sure-we-don-t-crash-when-host-por.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1016: kvm-virtio-serial-Use-MSI-vectors-for-port-virtqueues.patch
# For bz#543825 - [RFE] Backport virtio-serial device to qemu
Patch1017: kvm-virtio-serial-bus-Match-upstream-whitespace.patch
# For bz#557435 - KVM: WIN7-32bit blue screen (IMAGE_NAME:  ntkrnlmp.exe).
Patch1018: kvm-reduce-number-of-reinjects-on-ACK.patch
# For bz#558412 - -help output not terminated by newline
Patch1019: kvm-Add-missing-newline-at-the-end-of-options-list.patch
# For bz#558414 - Artifacts in hextile decoding
Patch1020: kvm-vnc-Fix-artifacts-in-hextile-decoding.patch
# For bz#558415 - Assert triggers on qmp commands returning lists
Patch1021: kvm-QMP-Drop-wrong-assert.patch
# For bz#558435 - vmware-svga buffer overflow copying cursor data
Patch1022: kvm-vmware_vga-Check-cursor-dimensions-passed-from-guest.patch
# For bz#558438 - virtio status bits corrupted if guest deasserts bus mastering bit
Patch1023: kvm-virtio-pci-thinko-fix.patch
# For bz#558465 - Double-free of qmp async messages
Patch1024: kvm-QMP-Don-t-free-async-event-s-data.patch
# For bz#558466 - Possible segfault on vnc client disconnect
Patch1025: kvm-vnc_refresh-return-if-vd-timer-is-NULL.patch
# For bz#558477 - Incorrect handling of EINVAL from accept4()
Patch1026: kvm-osdep.c-Fix-accept4-fallback.patch
# For bz#558619 - QMP: Emit asynchronous events on all QMP monitors
Patch1027: kvm-QMP-Emit-asynchronous-events-on-all-QMP-monitors.patch
# For bz#558846 - fix use-after-free in vnc code
Patch1028: kvm-vnc_refresh-calling-vnc_update_client-might-free-vs.patch
# For bz#558416 - Machine check exception injected into qemu reinjected after every reset
Patch1029: kvm-MCE-Fix-bug-of-IA32_MCG_STATUS-after-system-reset.patch
# For bz#558432 - CPU topology not taking effect
Patch1030: kvm-Fix-CPU-topology-initialization.patch
# For bz#558467 - roms potentially loaded twice
Patch1031: kvm-loader-more-ignores-for-rom-intended-to-be-loaded-by.patch
# For bz#558470 - Incorrect machine types
Patch1032: kvm-pc-add-machine-type-for-0.12.patch
# For bz#559089 - Rename virtio-serial.c to virtio-console.c as is upstream.
Patch1033: kvm-virtio-console-Rename-virtio-serial.c-back-to-virtio.patch
# For bz#559503 - virtio-serial: fix multiple devices intialisation
Patch1034: kvm-virtio-serial-bus-Fix-bus-initialisation-and-allow-f.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1035: kvm-VNC-Use-enabled-key-instead-of-status.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1036: kvm-VNC-Make-auth-key-mandatory.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1037: kvm-VNC-Rename-client-s-username-key.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1038: kvm-VNC-Add-family-key.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1039: kvm-VNC-Cache-client-info-at-connection-time.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1040: kvm-QMP-Introduce-VNC_CONNECTED-event.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1041: kvm-QMP-Introduce-VNC_DISCONNECTED-event.patch
# For bz#549759 - A QMP event notification on VNC client connect/disconnect events
Patch1042: kvm-QMP-Introduce-VNC_INITIALIZED-event.patch
# For bz#558730 - qemu may create too large iovecs for the kernel
Patch1043: kvm-block-avoid-creating-too-large-iovecs-in-multiwrite_.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1044: kvm-Fix-QEMU_WARN_UNUSED_RESULT.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1045: kvm-qcow2-Fix-error-handling-in-qcow2_grow_l1_table.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1046: kvm-qcow2-Fix-error-handling-in-qcow_save_vmstate.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1047: kvm-qcow2-Return-0-errno-in-get_cluster_table.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1048: kvm-qcow2-Return-0-errno-in-qcow2_alloc_cluster_offset.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1049: kvm-block-Return-original-error-codes-in-bdrv_pread-writ.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1050: kvm-qcow2-Fix-error-handling-in-grow_refcount_table.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1051: kvm-qcow2-Improve-error-handling-in-update_refcount.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1052: kvm-qcow2-Allow-updating-no-refcounts.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1053: kvm-qcow2-Don-t-ignore-update_refcount-return-value.patch
# For bz#560623 - error codes aren't always propagated up through the block layer (e.g. -ENOSPC)
Patch1054: kvm-qcow2-Don-t-ignore-qcow2_alloc_clusters-return-value.patch
# For bz#562181 - Small VNC related cleanup
Patch1055: kvm-net-Make-inet_strfamily-public.patch
# For bz#562181 - Small VNC related cleanup
Patch1056: kvm-net-inet_strfamily-Better-unknown-family-report.patch
# For bz#562181 - Small VNC related cleanup
Patch1057: kvm-vnc-Use-inet_strfamily.patch
# For bz#558818 - rom loading
Patch1058: kvm-roms-minor-fixes-and-cleanups.patch
# For bz#558818 - rom loading
Patch1059: kvm-fw_cfg-rom-loader-tweaks.patch
# For bz#558818 - rom loading
Patch1060: kvm-roms-rework-rom-loading-via-fw.patch
# For bz#558818 - rom loading
Patch1061: kvm-pci-allow-loading-roms-via-fw_cfg.patch
# For bz#558818 - rom loading
Patch1062: kvm-pc-add-rombar-to-compat-properties-for-pc-0.10-and-p.patch
# For bz#560942 - virtio-blk error handling doesn't work reliably
Patch1063: kvm-virtio_blk-Factor-virtio_blk_handle_request-out.patch
# For bz#560942 - virtio-blk error handling doesn't work reliably
Patch1064: kvm-virtio-blk-Fix-restart-after-read-error.patch
# For bz#560942 - virtio-blk error handling doesn't work reliably
Patch1065: kvm-virtio-blk-Fix-error-cases-which-ignored-rerror-werr.patch
# For bz#557930 - QMP: Feature Negotiation support
Patch1066: kvm-QMP-Add-QEMU-s-version-to-the-greeting-message.patch
# For bz#557930 - QMP: Feature Negotiation support
Patch1067: kvm-QMP-Introduce-the-qmp_capabilities-command.patch
# For bz#557930 - QMP: Feature Negotiation support
Patch1068: kvm-QMP-Enforce-capability-negotiation-rules.patch
# For bz#557930 - QMP: Feature Negotiation support
Patch1069: kvm-QMP-spec-Capability-negotiation-updates.patch
# For bz#559667 - QMP: JSON parser doesn't escape some control chars
Patch1070: kvm-json-escape-u0000-.-u001F-when-outputting-json.patch
# For bz#563878 - QJSON: Fix PRId64 handling
Patch1071: kvm-json-fix-PRId64-on-Win32.patch
# For bz#563875 - QJSON: Improve debugging
Patch1072: kvm-qjson-Improve-debugging.patch
# For bz#563876 - Monitor: remove unneeded checks
Patch1073: kvm-Monitor-remove-unneeded-checks.patch
# For bz#559635 - QMP: assertion on multiple faults
Patch1074: kvm-QError-Don-t-abort-on-multiple-faults.patch
# For bz#559645 - QMP: leak when a QMP connection is closed
Patch1075: kvm-QMP-Don-t-leak-on-connection-close.patch
# For bz#558623 - QMP: Basic async events are not emitted
Patch1076: kvm-QMP-Emit-Basic-events.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1077: kvm-net-add-API-to-disable-enable-polling.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1078: kvm-virtio-rename-features-guest_features.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1079: kvm-qdev-add-bit-property-type.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1080: kvm-qdev-fix-thinko-leading-to-guest-crashes.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1081: kvm-virtio-add-features-as-qdev-properties-fixup.patch
# For bz#547501 - RFE: a QMP event notification for disk  I/O errors with werror/rerror flags
Patch1082: kvm-QMP-BLOCK_IO_ERROR-event-handling.patch
# For bz#547501 - RFE: a QMP event notification for disk  I/O errors with werror/rerror flags
Patch1083: kvm-block-BLOCK_IO_ERROR-QMP-event.patch
# For bz#547501 - RFE: a QMP event notification for disk  I/O errors with werror/rerror flags
Patch1084: kvm-ide-Generate-BLOCK_IO_ERROR-QMP-event.patch
# For bz#547501 - RFE: a QMP event notification for disk  I/O errors with werror/rerror flags
Patch1085: kvm-scsi-Generate-BLOCK_IO_ERROR-QMP-event.patch
# For bz#547501 - RFE: a QMP event notification for disk  I/O errors with werror/rerror flags
Patch1086: kvm-virtio-blk-Generate-BLOCK_IO_ERROR-QMP-event.patch
# For bz#558838 - add rhel machine types
Patch1087: kvm-add-rhel-machine-types.patch
# For bz#568739 - QMP: Fix 'query-balloon' key
Patch1088: kvm-QMP-Fix-query-balloon-key-change.patch
# For bz#558835 - ide/scsi drive versions
Patch1089: kvm-ide-device-version-property.patch
# For bz#558835 - ide/scsi drive versions
Patch1090: kvm-pc-add-driver-version-compat-properties.patch
# For bz#567602 - qemu-img rebase subcommand got Segmentation fault
Patch1091: kvm-qemu-img-Fix-segfault-during-rebase.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1092: kvm-path.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1093: kvm-hw-pc.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1094: kvm-slirp-misc.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1095: kvm-savevm.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1096: kvm-block-bochs.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1097: kvm-block.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1098: kvm-Introduce-qemu_write_full.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1099: kvm-force-to-test-result-for-qemu_write_full.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1100: kvm-block-cow.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1101: kvm-block-qcow.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1102: kvm-block-vmdk.o-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1103: kvm-block-vvfat.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1104: kvm-block-qcow2.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1105: kvm-net-slirp.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1106: kvm-usb-linux.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1107: kvm-vl.c-fix-warning-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1108: kvm-monitor.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1109: kvm-linux-user-mmap.c-fix-warnings-with-_FORTIFY_SOURCE.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1110: kvm-check-pipe-return-value.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1111: kvm-fix-qemu-kvm-_FORTIFY_SOURCE-compilation.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1112: kvm-Enable-_FORTIFY_SOURCE-2.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1113: kvm-qcow2-Fix-image-creation-regression.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1114: kvm-cow-return-errno-instead-of-1.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1115: kvm-slirp-check-system-success.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1116: kvm-qcow2-return-errno-instead-of-1.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1117: kvm-qcow-return-errno-instead-of-1.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1118: kvm-vmdk-return-errno-instead-of-1.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1119: kvm-vmdk-make-vmdk_snapshot_create-return-errno.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1120: kvm-vmdk-fix-double-free.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1121: kvm-vmdk-share-cleanup-code.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1122: kvm-block-print-errno-on-error.patch
# For bz#567099 - Allow _FORTIFY_SOURCE=2 & --enable-warning
Patch1123: kvm-documentation-qemu_write_full-don-t-work-with-non-bl.patch
# For bz#567035 - Backport changes for virtio-serial from upstream: disabling MSI, backward compat.
Patch1124: kvm-virtio-serial-pci-Allow-MSI-to-be-disabled.patch
# For bz#567035 - Backport changes for virtio-serial from upstream: disabling MSI, backward compat.
Patch1125: kvm-pc-Add-backward-compatibility-options-for-virtio-ser.patch
# For bz#567035 - Backport changes for virtio-serial from upstream: disabling MSI, backward compat.
Patch1126: kvm-virtio-serial-don-t-set-MULTIPORT-for-1-port-dev.patch
# For bz#567035 - Backport changes for virtio-serial from upstream: disabling MSI, backward compat.
Patch1127: kvm-qdev-Add-a-DEV_NVECTORS_UNSPECIFIED-enum-for-unspeci.patch
# For bz#567035 - Backport changes for virtio-serial from upstream: disabling MSI, backward compat.
Patch1128: kvm-virtio-pci-Use-DEV_NVECTORS_UNSPECIFIED-instead-of-1.patch
# For bz#569767 - Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc
Patch1129: kvm-kbd-leds-infrastructure.patch
# For bz#569767 - Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc
Patch1130: kvm-kbd-leds-ps-2-kbd.patch
# For bz#569767 - Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc
Patch1131: kvm-kbd-leds-usb-kbd.patch
# For bz#569767 - Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc
Patch1132: kvm-kbd-keds-vnc.patch
# For bz#570174 - Restoring a qemu guest from a saved state file using -incoming sometimes fails and hangs
Patch1133: kvm-migration-Clear-fd-also-in-error-cases.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1134: kvm-qemu-memory-notifiers.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1135: kvm-tap-add-interface-to-get-device-fd.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1136: kvm-add-API-to-set-ioeventfd.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1137: kvm-notifier-event-notifier-implementation.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1138: kvm-virtio-add-notifier-support.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1139: kvm-virtio-add-APIs-for-queue-fields.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1140: kvm-virtio-add-set_status-callback.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1141: kvm-virtio-move-typedef-to-qemu-common.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1142: kvm-virtio-pci-fill-in-notifier-support.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1143: kvm-vhost-vhost-net-support.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1144: kvm-tap-add-vhost-vhostfd-options.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1145: kvm-tap-add-API-to-retrieve-vhost-net-header.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1146: kvm-virtio-net-vhost-net-support.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1147: kvm-qemu-kvm-add-vhost.h-header.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1148: kvm-irqfd-support.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1149: kvm-msix-add-mask-unmask-notifiers.patch
# For bz#562958 - RFE: Support vhost net mode
Patch1150: kvm-virtio-pci-irqfd-support.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1151: kvm-add-spice-into-the-configure-file.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1152: kvm-spice-core-bits.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1153: kvm-spice-add-keyboard.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1154: kvm-spice-add-mouse.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1155: kvm-spice-simple-display.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1156: kvm-move-x509-file-name-defines-to-qemu-x509.h.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1157: kvm-spice-tls-support.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1158: kvm-spice-configure-listening-addr.patch
# For bz#549757 - Provide SPICE support  / -spice command line argument
Patch1159: kvm-spice-add-qxl-device.patch
# For bz#574211 - spice: add tablet support
Patch1160: kvm-spice-add-tablet.patch
# For bz#574212 - spice:wake spice server only when idle
Patch1161: kvm-spice-simple-display-wake-spice-server-only-when-idl.patch
# For bz#574214 - qxl: switch qxl from native into vga mode on vga register access
Patch1162: kvm-spice-qxl-switch-back-to-vga-mode-on-register-access.patch
# For bz#568820 - EMBARGOED CVE-2010-0431 qemu: Insufficient guest provided pointers validation [rhel-6.0]
Patch1163: kvm-spice-qxl-ring-access-security-fix.patch
# For bz#525935 - RFE: expire vnc password
Patch1164: kvm-vnc-support-password-expire.patch
# For bz#525935 - RFE: expire vnc password
Patch1165: kvm-spice-vnc-add-__com.redhat_set_password-monitor-comm.patch
# For bz#574222 - spice: add audio support
Patch1166: kvm-spice-add-audio-support.patch
# For bz#574225 - spice: add config options
Patch1167: kvm-spice-make-image-compression-configurable.patch
# For bz#574225 - spice: add config options
Patch1168: kvm-spice-configure-channel-security.patch
# For bz#574225 - spice: add config options
Patch1169: kvm-spice-configure-renderer.patch
# For bz#558957 - A QMP event notification on SPICE client connect/disconnect events
Patch1170: kvm-spice-send-connect-disconnect-monitor-events.patch
# For bz#574853 - spice/qxl: add qxl to -vga help text
Patch1171: kvm-spice-qxl-update-vga-help-text-indicating-qxl-is-the.patch
# For bz#574849 - spice: client migration support
Patch1172: kvm-spice-notifying-spice-when-migration-starts-and-ends.patch
# For bz#574849 - spice: client migration support
Patch1173: kvm-spice-add-__com.redhat_spice_migrate_info-monitor-co.patch
# For bz#567940 - qcow2 corruption with I/O error during refcount block allocation
Patch1174: kvm-qcow2-Factor-next_refcount_table_size-out.patch
# For bz#567940 - qcow2 corruption with I/O error during refcount block allocation
Patch1175: kvm-qcow2-Rewrite-alloc_refcount_block-grow_refcount_tab.patch
# For bz#567940 - qcow2 corruption with I/O error during refcount block allocation
Patch1176: kvm-qcow2-More-checks-for-qemu-img-check.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1177: kvm-spice-virtual-machine-channel-replacement-for-remove.patch
# For bz#558835 - ide/scsi drive versions
Patch1178: kvm-scsi-device-version-property.patch
# For bz#558835 - ide/scsi drive versions
Patch1179: kvm-scsi-disk-fix-buffer-overflow.patch
# For bz#574939 - Memory statistics support
Patch1180: kvm-New-API-for-asynchronous-monitor-commands.patch
# For bz#574939 - Memory statistics support
Patch1181: kvm-Revert-QMP-Fix-query-balloon-key-change.patch
# For bz#574939 - Memory statistics support
Patch1182: kvm-virtio-Add-memory-statistics-reporting-to-the-balloo.patch
# For bz#574525 - Align qemu-kvm guest memory for transparent hugepage support
Patch1183: kvm-Transparent-Hugepage-Support-3.patch
# For bz#574642 - QMP: Convert do_cpu_set() to QObject
Patch1184: kvm-monitor-Don-t-check-for-mon_get_cpu-failure.patch
# For bz#574642 - QMP: Convert do_cpu_set() to QObject
Patch1185: kvm-QError-New-QERR_OPEN_FILE_FAILED.patch
# For bz#574642 - QMP: Convert do_cpu_set() to QObject
Patch1186: kvm-monitor-convert-do_memory_save-to-QError.patch
# For bz#574642 - QMP: Convert do_cpu_set() to QObject
Patch1187: kvm-monitor-convert-do_physical_memory_save-to-QError.patch
# For bz#574642 - QMP: Convert do_cpu_set() to QObject
Patch1188: kvm-QError-New-QERR_INVALID_CPU_INDEX.patch
# For bz#574642 - QMP: Convert do_cpu_set() to QObject
Patch1189: kvm-monitor-convert-do_cpu_set-to-QObject-QError.patch
# For bz#575800 - Monitor: Backport a collection of fixes
Patch1190: kvm-monitor-Use-QERR_INVALID_PARAMETER-instead-of-QERR_I.patch
# For bz#575800 - Monitor: Backport a collection of fixes
Patch1191: kvm-Revert-QError-New-QERR_INVALID_CPU_INDEX.patch
# For bz#575800 - Monitor: Backport a collection of fixes
Patch1192: kvm-json-parser-Fix-segfault-on-malformed-input.patch
# For bz#575800 - Monitor: Backport a collection of fixes
Patch1193: kvm-fix-i-format-handling-in-memory-dump.patch
# For bz#575800 - Monitor: Backport a collection of fixes
Patch1194: kvm-Don-t-set-default-monitor-when-there-is-a-mux-ed-one.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1195: kvm-monitor-Document-argument-type-M.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1196: kvm-QDict-New-qdict_get_double.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1197: kvm-monitor-New-argument-type-b.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1198: kvm-monitor-Use-argument-type-b-for-migrate_set_speed.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1199: kvm-monitor-convert-do_migrate_set_speed-to-QObject.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1200: kvm-monitor-New-argument-type-T.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1201: kvm-monitor-Use-argument-type-T-for-migrate_set_downtime.patch
# For bz#575821 - QMP: Convert migrate_set_speed, migrate_set_downtime to QObject
Patch1202: kvm-monitor-convert-do_migrate_set_downtime-to-QObject.patch
# For bz#575912 - QMP: Backport event related fixes
Patch1203: kvm-block-Emit-BLOCK_IO_ERROR-before-vm_stop-call.patch
# For bz#575912 - QMP: Backport event related fixes
Patch1204: kvm-QMP-Move-STOP-event-into-do_vm_stop.patch
# For bz#575912 - QMP: Backport event related fixes
Patch1205: kvm-QMP-Move-RESET-event-into-qemu_system_reset.patch
# For bz#575912 - QMP: Backport event related fixes
Patch1206: kvm-QMP-Sync-with-upstream-event-changes.patch
# For bz#575912 - QMP: Backport event related fixes
Patch1207: kvm-QMP-Drop-DEBUG-event.patch
# For bz#575912 - QMP: Backport event related fixes
Patch1208: kvm-QMP-Revamp-the-qmp-events.txt-file.patch
# For bz#547534 - RFE: a QMP event notification for RTC clock changes
Patch1209: kvm-QMP-Introduce-RTC_CHANGE-event.patch
# For bz#557083 - QMP events for watchdog events
Patch1210: kvm-QMP-Introduce-WATCHDOG-event.patch
# For bz#576561 - spice: add more config options
Patch1211: kvm-spice-add-more-config-options.patch
# For bz#576561 - spice: add more config options
Patch1212: kvm-Revert-spice-add-more-config-options.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1213: kvm-Fix-kvm_load_mpstate-for-vcpu-hot-add.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1214: kvm-qemu-kvm-enable-get-set-vcpu-events-on-reset-and-mig.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1215: kvm-Synchronize-kvm-headers.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1216: kvm-Increase-VNC_MAX_WIDTH.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1217: kvm-device-assignment-default-requires-IOMMU.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1218: kvm-Do-not-allow-vcpu-stop-with-in-progress-PIO.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1219: kvm-fix-savevm-command-without-id-or-tag.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1220: kvm-Do-not-ignore-error-if-open-file-failed-serial-dev-t.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1221: kvm-segfault-due-to-buffer-overrun-in-usb-serial.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1222: kvm-fix-inet_parse-typo.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1223: kvm-virtio-net-fix-network-stall-under-load.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1224: kvm-don-t-dereference-NULL-after-failed-strdup.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1225: kvm-net-Remove-unused-net_client_uninit.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1226: kvm-net-net_check_clients-runs-too-early-to-see-device-f.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1227: kvm-net-Fix-bogus-Warning-vlan-0-with-no-nics-with-devic.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1228: kvm-net-net_check_clients-checks-only-VLAN-clients-fix.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1229: kvm-net-info-network-shows-only-VLAN-clients-fix.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1230: kvm-net-Monitor-command-set_link-finds-only-VLAN-clients.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1231: kvm-ide-save-restore-pio-atapi-cmd-transfer-fields-and-i.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1232: kvm-cirrus-Properly-re-register-cirrus_linear_io_addr-on.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1233: kvm-Monitor-Introduce-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1234: kvm-Monitor-Convert-simple-handlers-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1235: kvm-Monitor-Convert-do_cont-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1236: kvm-Monitor-Convert-do_eject-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1237: kvm-Monitor-Convert-do_cpu_set-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1238: kvm-Monitor-Convert-do_block_set_passwd-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1239: kvm-Monitor-Convert-do_getfd-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1240: kvm-Monitor-Convert-do_closefd-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1241: kvm-Monitor-Convert-pci_device_hot_add-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1242: kvm-Monitor-Convert-pci_device_hot_remove-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1243: kvm-Monitor-Convert-do_migrate-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1244: kvm-Monitor-Convert-do_memory_save-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1245: kvm-Monitor-Convert-do_physical_memory_save-to-cmd_new_r.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1246: kvm-Monitor-Convert-do_info-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1247: kvm-Monitor-Convert-do_change-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1248: kvm-Monitor-Convert-to-mon_set_password-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1249: kvm-Monitor-Convert-mon_spice_migrate-to-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1250: kvm-Monitor-Rename-cmd_new_ret.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1251: kvm-Monitor-Debugging-support.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1252: kvm-Monitor-Drop-the-print-disabling-mechanism.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1253: kvm-Monitor-Audit-handler-return.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1254: kvm-Monitor-Debug-stray-prints-the-right-way.patch
# For bz#563491 - QMP: New internal error handling mechanism
Patch1255: kvm-Monitor-Report-more-than-one-error-in-handlers.patch
# For bz#563641 - QMP: Wrong error message in block_passwd command
Patch1256: kvm-QError-New-QERR_DEVICE_NOT_ENCRYPTED.patch
# For bz#563641 - QMP: Wrong error message in block_passwd command
Patch1257: kvm-Wrong-error-message-in-block_passwd-command.patch
# For bz#578493 - QMP: Fix spice event names
Patch1258: kvm-Monitor-Introduce-RFQDN_REDHAT-and-use-it.patch
# For bz#578493 - QMP: Fix spice event names
Patch1259: kvm-QMP-Fix-Spice-event-names.patch
# For bz#558236 - qemu-kvm monitor corrupts tty on exit
Patch1260: kvm-char-Remove-redundant-qemu_chr_generic_open-call.patch
# For bz#558236 - qemu-kvm monitor corrupts tty on exit
Patch1261: kvm-add-close-callback-for-tty-based-char-device.patch
# For bz#558236 - qemu-kvm monitor corrupts tty on exit
Patch1262: kvm-Restore-terminal-attributes-for-tty-based-monitor.patch
# For bz#558236 - qemu-kvm monitor corrupts tty on exit
Patch1263: kvm-Restore-terminal-monitor-attributes-addition.patch
# For bz#578912 - Monitor: Overflow in 'info balloon'
Patch1264: kvm-balloon-Fix-overflow-when-reporting-actual-memory-si.patch
# For bz#576544 - Error message doesn't contain the content of invalid keyword
Patch1265: kvm-json-parser-Output-the-content-of-invalid-keyword.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1266: kvm-read-only-Make-CDROM-a-read-only-drive.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1267: kvm-read-only-BDRV_O_FLAGS-cleanup.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1268: kvm-read-only-Added-drives-readonly-option.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1269: kvm-read-only-Disable-fall-back-to-read-only.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1270: kvm-read-only-No-need-anymoe-for-bdrv_set_read_only.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1271: kvm-read_only-Ask-for-read-write-permissions-when-openin.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1272: kvm-read-only-Read-only-device-changed-to-opens-it-s-fil.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1273: kvm-read-only-qemu-img-Fix-qemu-img-can-t-create-qcow-im.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1274: kvm-block-clean-up-bdrv_open2-structure-a-bit.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1275: kvm-block-saner-flags-filtering-in-bdrv_open2.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1276: kvm-block-flush-backing_hd-in-the-right-place.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1277: kvm-block-fix-cache-flushing-in-bdrv_commit.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1278: kvm-block-more-read-only-changes-related-to-backing-file.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1279: kvm-read-only-minor-cleanup.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1280: kvm-read-only-Another-minor-cleanup.patch
# For bz#537164 - -drive arg has no way to request a read only disk
Patch1281: kvm-read-only-allow-read-only-CDROM-with-any-interface.patch
# For bz#580028 - 'qemu-img re-base' broken on block devices
Patch1282: kvm-qemu-img-rebase-Add-f-option.patch
# For bz#579974 - Get segmentation fault when creating qcow2 format image on block device with "preallocation=metadata"
Patch1283: kvm-qemu-io-Fix-return-value-handling-of-bdrv_open.patch
# For bz#579974 - Get segmentation fault when creating qcow2 format image on block device with "preallocation=metadata"
Patch1284: kvm-qemu-nbd-Fix-return-value-handling-of-bdrv_open.patch
# For bz#579974 - Get segmentation fault when creating qcow2 format image on block device with "preallocation=metadata"
Patch1285: kvm-qemu-img-Fix-error-message.patch
# For bz#579974 - Get segmentation fault when creating qcow2 format image on block device with "preallocation=metadata"
Patch1286: kvm-Replace-calls-of-old-bdrv_open.patch
# For bz#564101 - [RFE] topology support in the virt block layer
Patch1287: kvm-virtio-blk-revert-serial-number-support.patch
# For bz#564101 - [RFE] topology support in the virt block layer
Patch1288: kvm-block-add-topology-qdev-properties.patch
# For bz#564101 - [RFE] topology support in the virt block layer
Patch1289: kvm-virtio-blk-add-topology-support.patch
# For bz#564101 - [RFE] topology support in the virt block layer
Patch1290: kvm-scsi-add-topology-support.patch
# For bz#564101 - [RFE] topology support in the virt block layer
Patch1291: kvm-ide-add-topology-support.patch
# For bz#580140 - emulated pcnet nic in qemu-kvm has wrong PCI subsystem ID for Windows XP driver
Patch1292: kvm-pcnet-make-subsystem-vendor-id-match-hardware.patch
# For bz#569661 - RHEL6.0 requires backport of upstream cpu model support..
Patch1293: cpu-model-config-1.patch
# For bz#569661 - RHEL6.0 requires backport of upstream cpu model support..
Patch1294: cpu-model-config-2.patch
# For bz#569661 - RHEL6.0 requires backport of upstream cpu model support..
Patch1295: cpu-model-config-3.patch
# For bz#569661 - RHEL6.0 requires backport of upstream cpu model support..
Patch1296: cpu-model-config-4.patch
# For bz#561078 - "Cannot boot from non-existent NIC" when using virt-install --pxe
Patch1297: kvm-net-remove-NICInfo.bootable-field.patch
# For bz#561078 - "Cannot boot from non-existent NIC" when using virt-install --pxe
Patch1298: kvm-net-remove-broken-net_set_boot_mask-boot-device-vali.patch
# For bz#561078 - "Cannot boot from non-existent NIC" when using virt-install --pxe
Patch1299: kvm-boot-remove-unused-boot_devices_bitmap-variable.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1300: kvm-check-kvm-enabled.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1301: kvm-qemu-rename-notifier-event_notifier.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1302: kvm-virtio-API-name-cleanup.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1303: kvm-vhost-u_int64_t-uint64_t.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1304: kvm-virtio-pci-fix-coding-style.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1305: kvm-vhost-detect-lack-of-support-earlier-style.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1306: kvm-configure-vhost-related-fixes.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1307: kvm-vhost-fix-features-ack.patch
# For bz#580109 - vhost net lacks upstream fixes
Patch1308: kvm-vhost-net-disable-mergeable-buffers.patch
# For bz#579470 - QMP: device_add support
Patch1309: kvm-qemu-option-Make-qemu_opts_foreach-accumulate-return.patch
# For bz#579470 - QMP: device_add support
Patch1310: kvm-qdev-Fix-exit-code-for-device.patch
# For bz#579470 - QMP: device_add support
Patch1311: kvm-qdev-Add-help-for-device-properties.patch
# For bz#579470 - QMP: device_add support
Patch1312: kvm-qdev-update-help-on-device.patch
# For bz#579470 - QMP: device_add support
Patch1313: kvm-qdev-Add-rudimentary-help-for-property-value.patch
# For bz#579470 - QMP: device_add support
Patch1314: kvm-qdev-Free-opts-on-failed-do_device_add.patch
# For bz#579470 - QMP: device_add support
Patch1315: kvm-qdev-Improve-diagnostics-for-bad-property-values.patch
# For bz#579470 - QMP: device_add support
Patch1316: kvm-qdev-Catch-attempt-to-attach-more-than-one-device-to.patch
# For bz#579470 - QMP: device_add support
Patch1317: kvm-usb-Remove-disabled-monitor_printf-in-usb_read_file.patch
# For bz#579470 - QMP: device_add support
Patch1318: kvm-savevm-Fix-loadvm-to-report-errors-to-stderr-not-the.patch
# For bz#579470 - QMP: device_add support
Patch1319: kvm-pc-Fix-error-reporting-for-boot-once.patch
# For bz#579470 - QMP: device_add support
Patch1320: kvm-pc-Factor-common-code-out-of-pc_boot_set-and-cmos_in.patch
# For bz#579470 - QMP: device_add support
Patch1321: kvm-tools-Remove-unused-cur_mon-from-qemu-tool.c.patch
# For bz#579470 - QMP: device_add support
Patch1322: kvm-monitor-Separate-default-monitor-and-current-monitor.patch
# For bz#579470 - QMP: device_add support
Patch1323: kvm-block-Simplify-usb_msd_initfn-test-for-can-read-bdrv.patch
# For bz#579470 - QMP: device_add support
Patch1324: kvm-monitor-Factor-monitor_set_error-out-of-qemu_error_i.patch
# For bz#579470 - QMP: device_add support
Patch1325: kvm-error-Move-qemu_error-friends-from-monitor.c-to-own-.patch
# For bz#579470 - QMP: device_add support
Patch1326: kvm-error-Simplify-error-sink-setup.patch
# For bz#579470 - QMP: device_add support
Patch1327: kvm-error-Move-qemu_error-friends-into-their-own-header.patch
# For bz#579470 - QMP: device_add support
Patch1328: kvm-error-New-error_printf-and-error_vprintf.patch
# For bz#579470 - QMP: device_add support
Patch1329: kvm-error-Don-t-abuse-qemu_error-for-non-error-in-qdev_d.patch
# For bz#579470 - QMP: device_add support
Patch1330: kvm-error-Don-t-abuse-qemu_error-for-non-error-in-qbus_f.patch
# For bz#579470 - QMP: device_add support
Patch1331: kvm-error-Don-t-abuse-qemu_error-for-non-error-in-scsi_h.patch
# For bz#579470 - QMP: device_add support
Patch1332: kvm-error-Replace-qemu_error-by-error_report.patch
# For bz#579470 - QMP: device_add support
Patch1333: kvm-error-Rename-qemu_error_new-to-qerror_report.patch
# For bz#579470 - QMP: device_add support
Patch1334: kvm-error-Infrastructure-to-track-locations-for-error-re.patch
# For bz#579470 - QMP: device_add support
Patch1335: kvm-error-Include-the-program-name-in-error-messages-to-.patch
# For bz#579470 - QMP: device_add support
Patch1336: kvm-error-Track-locations-in-configuration-files.patch
# For bz#579470 - QMP: device_add support
Patch1337: kvm-QemuOpts-Fix-qemu_config_parse-to-catch-file-read-er.patch
# For bz#579470 - QMP: device_add support
Patch1338: kvm-error-Track-locations-on-command-line.patch
# For bz#579470 - QMP: device_add support
Patch1339: kvm-qdev-Fix-device-and-device_add-to-handle-unsuitable-.patch
# For bz#579470 - QMP: device_add support
Patch1340: kvm-qdev-Factor-qdev_create_from_info-out-of-qdev_create.patch
# For bz#579470 - QMP: device_add support
Patch1341: kvm-qdev-Hide-no_user-devices-from-users.patch
# For bz#579470 - QMP: device_add support
Patch1342: kvm-qdev-Hide-ptr-properties-from-users.patch
# For bz#579470 - QMP: device_add support
Patch1343: kvm-monitor-New-monitor_cur_is_qmp.patch
# For bz#579470 - QMP: device_add support
Patch1344: kvm-error-Let-converted-handlers-print-in-human-monitor.patch
# For bz#579470 - QMP: device_add support
Patch1345: kvm-error-Polish-human-readable-error-descriptions.patch
# For bz#579470 - QMP: device_add support
Patch1346: kvm-error-New-QERR_PROPERTY_NOT_FOUND.patch
# For bz#579470 - QMP: device_add support
Patch1347: kvm-error-New-QERR_PROPERTY_VALUE_BAD.patch
# For bz#579470 - QMP: device_add support
Patch1348: kvm-error-New-QERR_PROPERTY_VALUE_IN_USE.patch
# For bz#579470 - QMP: device_add support
Patch1349: kvm-error-New-QERR_PROPERTY_VALUE_NOT_FOUND.patch
# For bz#579470 - QMP: device_add support
Patch1350: kvm-qdev-convert-setting-device-properties-to-QError.patch
# For bz#579470 - QMP: device_add support
Patch1351: kvm-qdev-Relax-parsing-of-bus-option.patch
# For bz#579470 - QMP: device_add support
Patch1352: kvm-error-New-QERR_BUS_NOT_FOUND.patch
# For bz#579470 - QMP: device_add support
Patch1353: kvm-error-New-QERR_DEVICE_MULTIPLE_BUSSES.patch
# For bz#579470 - QMP: device_add support
Patch1354: kvm-error-New-QERR_DEVICE_NO_BUS.patch
# For bz#579470 - QMP: device_add support
Patch1355: kvm-qdev-Convert-qbus_find-to-QError.patch
# For bz#579470 - QMP: device_add support
Patch1356: kvm-error-New-error_printf_unless_qmp.patch
# For bz#579470 - QMP: device_add support
Patch1357: kvm-error-New-QERR_BAD_BUS_FOR_DEVICE.patch
# For bz#579470 - QMP: device_add support
Patch1358: kvm-error-New-QERR_BUS_NO_HOTPLUG.patch
# For bz#579470 - QMP: device_add support
Patch1359: kvm-error-New-QERR_DEVICE_INIT_FAILED.patch
# For bz#579470 - QMP: device_add support
Patch1360: kvm-error-New-QERR_NO_BUS_FOR_DEVICE.patch
# For bz#579470 - QMP: device_add support
Patch1361: kvm-Revert-qdev-Use-QError-for-device-not-found-error.patch
# For bz#579470 - QMP: device_add support
Patch1362: kvm-error-Convert-do_device_add-to-QError.patch
# For bz#579470 - QMP: device_add support
Patch1363: kvm-qemu-option-Functions-to-convert-to-from-QDict.patch
# For bz#579470 - QMP: device_add support
Patch1364: kvm-qemu-option-Move-the-implied-first-name-into-QemuOpt.patch
# For bz#579470 - QMP: device_add support
Patch1365: kvm-qemu-option-Rename-find_list-to-qemu_find_opts-exter.patch
# For bz#579470 - QMP: device_add support
Patch1366: kvm-monitor-New-argument-type-O.patch
# For bz#579470 - QMP: device_add support
Patch1367: kvm-monitor-Use-argument-type-O-for-device_add.patch
# For bz#579470 - QMP: device_add support
Patch1368: kvm-monitor-convert-do_device_add-to-QObject.patch
# For bz#579470 - QMP: device_add support
Patch1369: kvm-error-Trim-includes-after-Move-qemu_error-friends.patch
# For bz#579470 - QMP: device_add support
Patch1370: kvm-error-Trim-includes-in-qerror.c.patch
# For bz#579470 - QMP: device_add support
Patch1371: kvm-error-Trim-includes-after-Infrastructure-to-track-lo.patch
# For bz#579470 - QMP: device_add support
Patch1372: kvm-error-Make-use-of-error_set_progname-optional.patch
# For bz#579470 - QMP: device_add support
Patch1373: kvm-error-Link-qemu-img-qemu-nbd-qemu-io-with-qemu-error.patch
# For bz#579470 - QMP: device_add support
Patch1374: kvm-error-Move-qerror_report-from-qemu-error.-ch-to-qerr.patch
# For bz#576561 - spice: add more config options
Patch1375: kvm-spice-add-more-config-options-readd.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1376: kvm-Documentation-Add-monitor-commands-to-function-index.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1377: kvm-error-Put-error-definitions-back-in-alphabetical-ord.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1378: kvm-error-New-QERR_DUPLICATE_ID.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1379: kvm-error-Convert-qemu_opts_create-to-QError.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1380: kvm-error-New-QERR_INVALID_PARAMETER_VALUE.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1381: kvm-error-Convert-qemu_opts_set-to-QError.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1382: kvm-error-Drop-extra-messages-after-qemu_opts_set-and-qe.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1383: kvm-error-Use-QERR_INVALID_PARAMETER_VALUE-instead-of-QE.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1384: kvm-error-Convert-qemu_opts_validate-to-QError.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1385: kvm-error-Convert-net_client_init-to-QError.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1386: kvm-error-New-QERR_DEVICE_IN_USE.patch
# For bz#559670 - No 'netdev_add' command in monitor
Patch1387: kvm-monitor-New-commands-netdev_add-netdev_del.patch
# For bz#582325 - QMP: device_del support
Patch1388: kvm-qdev-Convert-qdev_unplug-to-QError.patch
# For bz#582325 - QMP: device_del support
Patch1389: kvm-monitor-convert-do_device_del-to-QObject-QError.patch
# For bz#582575 - Backport bdrv_aio_multiwrite fixes
Patch1390: kvm-block-Fix-error-code-in-multiwrite-for-immediate-fai.patch
# For bz#582575 - Backport bdrv_aio_multiwrite fixes
Patch1391: kvm-block-Fix-multiwrite-memory-leak-in-error-case.patch
# For bz#581540 - SPICE graphics event does not include auth details
Patch1392: kvm-spice-add-auth-info-to-monitor-events.patch
# For bz#569613 - backport qemu-kvm-0.12.3 fixes to RHEL6
Patch1393: kvm-Request-setting-of-nmi_pending-and-sipi_vector.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1394: kvm-virtio-serial-save-load-Ensure-target-has-enough-por.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1395: kvm-virtio-serial-save-load-Ensure-nr_ports-on-src-and-d.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1396: kvm-virtio-serial-save-load-Ensure-we-have-hot-plugged-p.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1397: kvm-virtio-serial-save-load-Send-target-host-connection-.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1398: kvm-virtio-serial-Use-control-messages-to-notify-guest-o.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1399: kvm-virtio-serial-whitespace-match-surrounding-code.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1400: kvm-virtio-serial-Remove-redundant-check-for-0-sized-wri.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1401: kvm-virtio-serial-Update-copyright-year-to-2010.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1402: kvm-virtio-serial-Propagate-errors-in-initialising-ports.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1403: kvm-virtio-serial-Send-out-guest-data-to-ports-only-if-p.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1404: kvm-iov-Introduce-a-new-file-for-helpers-around-iovs-add.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1405: kvm-iov-Add-iov_to_buf-and-iov_size-helpers.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1406: kvm-virtio-serial-Handle-scatter-gather-buffers-for-cont.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1407: kvm-virtio-serial-Handle-scatter-gather-input-from-the-g.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1408: kvm-virtio-serial-Apps-should-consume-all-data-that-gues.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1409: kvm-virtio-serial-Discard-data-that-guest-sends-us-when-.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1410: kvm-virtio-serial-Implement-flow-control-for-individual-.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1411: kvm-virtio-serial-Handle-output-from-guest-to-unintialis.patch
# For bz#574296 - Fix migration for virtio-serial after port hot-plug/hot-unplug operations
Patch1412: kvm-virtio-serial-bus-wake-up-iothread-upon-guest-read-n.patch
# For bz#587227 - Fix segfault when creating more vcpus than allowed.
Patch1413: kvm-Bail-out-when-VCPU_CREATE-fails.patch
# For bz#586572 - virtio-blk multiwrite merge memory leak
Patch1414: kvm-block-Free-iovec-arrays-allocated-by-multiwrite_merg.patch
# For bz#588828 - endless loop when parsing of command line with bare image argument
Patch1415: kvm-vl.c-fix-BZ-588828-endless-loop-caused-by-non-option.patch
# For bz#584902 - Cannot associate drive with a floppy device using -global
Patch1416: kvm-fdc-fix-drive-property-handling.patch
# For bz#585837 - After re-base snapshot, the file in the snapshot disappeared
Patch1417: kvm-qemu-img-use-the-heap-instead-of-the-huge-stack-arra.patch
# For bz#585837 - After re-base snapshot, the file in the snapshot disappeared
Patch1418: kvm-qemu-img-rebase-Fix-output-image-corruption.patch
# For bz#578448 - qemu-kvm segfault when nfs restart(without using werror&rerror)
Patch1419: kvm-virtio-blk-Fix-use-after-free-in-error-case.patch
# For bz#578448 - qemu-kvm segfault when nfs restart(without using werror&rerror)
Patch1420: kvm-block-Fix-multiwrite-error-handling.patch
# For bz#579692 - qemu-kvm "-boot once=drives" couldn't function properly
Patch1421: kvm-Fix-boot-once-option.patch
# For bz#573578 - Segfault when migrating via QMP command interface
Patch1422: kvm-QError-New-QERR_QMP_BAD_INPUT_OBJECT_MEMBER.patch
# For bz#573578 - Segfault when migrating via QMP command interface
Patch1423: kvm-QMP-Use-QERR_QMP_BAD_INPUT_OBJECT_MEMBER.patch
# For bz#573578 - Segfault when migrating via QMP command interface
Patch1424: kvm-QError-Improve-QERR_QMP_BAD_INPUT_OBJECT-desc.patch
# For bz#573578 - Segfault when migrating via QMP command interface
Patch1425: kvm-QMP-Check-arguments-member-s-type.patch
# For bz#590102 - QMP: Backport RESUME event
Patch1426: kvm-QMP-Introduce-RESUME-event.patch
# For bz#588133 - RHEL5.4 guest can lose virtio networking during migration
Patch1427: kvm-pci-irq_state-vmstate-breakage.patch
# For bz#588756 - blkdebug is missing
Patch1428: kvm-qemu-config-qemu_read_config_file-reads-the-normal-c.patch
# For bz#588756 - blkdebug is missing
Patch1429: kvm-qemu-config-Make-qemu_config_parse-more-generic.patch
# For bz#588756 - blkdebug is missing
Patch1430: kvm-blkdebug-Basic-request-passthrough.patch
# For bz#588756 - blkdebug is missing
Patch1431: kvm-blkdebug-Inject-errors.patch
# For bz#588756 - blkdebug is missing
Patch1432: kvm-Make-qemu-config-available-for-tools.patch
# For bz#588756 - blkdebug is missing
Patch1433: kvm-blkdebug-Add-events-and-rules.patch
# For bz#588756 - blkdebug is missing
Patch1434: kvm-qcow2-Trigger-blkdebug-events.patch
# For bz#588762 - Backport qcow2 fixes
Patch1435: kvm-qcow2-Fix-access-after-end-of-array.patch
# For bz#588762 - Backport qcow2 fixes
Patch1436: kvm-qcow2-rename-two-QCowAIOCB-members.patch
# For bz#588762 - Backport qcow2 fixes
Patch1437: kvm-qcow2-Don-t-ignore-immediate-read-write-failures.patch
# For bz#588762 - Backport qcow2 fixes
Patch1438: kvm-qcow2-Remove-request-from-in-flight-list-after-error.patch
# For bz#588762 - Backport qcow2 fixes
Patch1439: kvm-qcow2-Return-0-errno-in-write_l2_entries.patch
# For bz#588762 - Backport qcow2 fixes
Patch1440: kvm-qcow2-Fix-error-return-code-in-qcow2_alloc_cluster_l.patch
# For bz#588762 - Backport qcow2 fixes
Patch1441: kvm-qcow2-Return-0-errno-in-write_l1_entry.patch
# For bz#588762 - Backport qcow2 fixes
Patch1442: kvm-qcow2-Return-0-errno-in-l2_allocate.patch
# For bz#588762 - Backport qcow2 fixes
Patch1443: kvm-qcow2-Remove-abort-on-free_clusters-failure.patch
# For bz#591061 - make fails to build after make clean
Patch1444: kvm-Add-qemu-error.o-only-once-to-target-list.patch
# For bz#589439 - Qcow2 snapshot got corruption after commit using block device
Patch1445: kvm-block-Fix-bdrv_commit.patch
# For bz#578106 - call trace when boot guest with -cpu host
Patch1446: kvm-fix-80000001.EDX-supported-bit-filtering.patch
# For bz#591604 - cannot override cpu vendor from the command line
Patch1447: kvm-fix-CPUID-vendor-override.patch
# For bz#588884 - Rebooting a kernel with kvmclock enabled, into a kernel with kvmclock disabled, causes random crashes
Patch1448: kvm-turn-off-kvmclock-when-resetting-cpu.patch
# For bz#593369 - virtio-blk: Avoid zeroing every request structure
Patch1449: kvm-virtio-blk-Avoid-zeroing-every-request-structure.patch
# For bz#580363 - Error while creating raw image on block device
Patch1450: kvm-dmg-fix-open-failure.patch
# For bz#580363 - Error while creating raw image on block device
Patch1451: kvm-block-get-rid-of-the-BDRV_O_FILE-flag.patch
# For bz#580363 - Error while creating raw image on block device
Patch1452: kvm-block-Convert-first_drv-to-QLIST.patch
# For bz#580363 - Error while creating raw image on block device
Patch1453: kvm-block-separate-raw-images-from-the-file-protocol.patch
# For bz#580363 - Error while creating raw image on block device
Patch1454: kvm-block-Split-bdrv_open.patch
# For bz#580363 - Error while creating raw image on block device
Patch1455: kvm-block-Avoid-forward-declaration-of-bdrv_open_common.patch
# For bz#580363 - Error while creating raw image on block device
Patch1456: kvm-block-Open-the-underlying-image-file-in-generic-code.patch
# For bz#580363 - Error while creating raw image on block device
Patch1457: kvm-block-bdrv_has_zero_init.patch
# For bz#590998 - qcow2 high watermark
Patch1458: kvm-block-Do-not-export-bdrv_first.patch
# For bz#590998 - qcow2 high watermark
Patch1459: kvm-block-Convert-bdrv_first-to-QTAILQ.patch
# For bz#590998 - qcow2 high watermark
Patch1460: kvm-block-Add-wr_highest_sector-blockstat.patch
# For bz#582684 - Monitor: getfd command is broken
Patch1461: kvm-stash-away-SCM_RIGHTS-fd-until-a-getfd-command-arriv.patch
# For bz#582874 - Guest hangs during restart after hot unplug then hot plug physical NIC card
Patch1462: kvm-Fix-segfault-after-device-assignment-hot-remove.patch
# For bz#590884 - bogus 'info pci' state when hot-added assigned device fails to initialize
Patch1463: kvm-pci-cleanly-backout-of-pci_qdev_init.patch
# For bz#593287 - Failed asserting during ide_dma_cancel
Patch1464: kvm-ide-Fix-ide_dma_cancel.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1465: kvm-spice-vmc-add-copyright.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1466: kvm-spice-vmc-remove-debug-prints-and-defines.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1467: kvm-spice-vmc-add-braces-to-single-line-if-s.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1468: kvm-spice-vmc-s-SpiceVirtualChannel-SpiceVMChannel-g.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1469: kvm-spice-vmc-s-spice_virtual_channel-spice_vmc-g.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1470: kvm-spice-vmc-all-variables-of-type-SpiceVMChannel-renam.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1471: kvm-spice-vmc-remove-meaningless-cast-of-void.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1472: kvm-spice-vmc-add-spice_vmc_ring_t-fix-write-function.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1473: kvm-spice-vmc-don-t-touch-guest_out_ring-on-unplug.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1474: kvm-spice-vmc-VirtIOSerialPort-vars-renamed-to-vserport.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1475: kvm-spice-vmc-add-nr-property.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1476: kvm-spice-vmc-s-SPICE_VM_CHANNEL-SPICE_VMC-g.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1477: kvm-spice-vmc-add-vmstate.-saves-active_interface.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1478: kvm-spice-vmc-rename-guest-device-name-to-com.redhat.spi.patch
# For bz#576488 - Spice: virtio serial based device for guest-spice client communication
Patch1479: kvm-spice-vmc-remove-unused-property-name.patch
# For bz#566785 - virt block layer must not keep guest's logical_block_size fixed
Patch1480: kvm-block-add-logical_block_size-property.patch
# For bz#591176 - migration fails since virtio-serial-bus is using uninitialized memory
Patch1481: kvm-virtio-serial-bus-fix-ports_map-allocation.patch
# For bz#569661 - RHEL6.0 requires backport of upstream cpu model support..
Patch1482: kvm-Move-cpu-model-config-file-to-agree-with-rpm-build-B.patch
# For bz#590922 - backport qemu-kvm-0.12.4 fixes to RHEL6
Patch1483: kvm-fix-undefined-shifts-by-32.patch
# For bz#590922 - backport qemu-kvm-0.12.4 fixes to RHEL6
Patch1484: kvm-qemu-char.c-drop-debug-printfs-from-qemu_chr_parse_c.patch
# For bz#590922 - backport qemu-kvm-0.12.4 fixes to RHEL6
Patch1485: kvm-Fix-corner-case-in-chardev-udp-parameter.patch
# For bz#590922 - backport qemu-kvm-0.12.4 fixes to RHEL6
Patch1486: kvm-pci-passthrough-zap-option-rom-scanning.patch
# For bz#590922 - backport qemu-kvm-0.12.4 fixes to RHEL6
Patch1487: kvm-UHCI-spurious-interrupt-fix.patch
# For bz#590922 - backport qemu-kvm-0.12.4 fixes to RHEL6
Patch1488: kvm-Fix-SIGFPE-for-vnc-display-of-width-height-1.patch
# For bz#589670 - spice: Ensure ring data is save/restored on migration
Patch1489: kvm-spice-vmc-remove-ringbuffer.patch
# For bz#589670 - spice: Ensure ring data is save/restored on migration
Patch1490: kvm-spice-vmc-add-dprintfs.patch
# For bz#585940 - qemu-kvm crashes on reboot when vhost is enabled
Patch1491: kvm-qemu-kvm-fix-crash-on-reboot-with-vhost-net.patch
# For bz#577106 - Abort/Segfault when creating qcow2 format image with 512b cluster size
Patch1492: kvm-qcow2-Fix-creation-of-large-images.patch
# For bz#569767 - Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc
Patch1493: kvm-vnc-sync-lock-modifier-state-on-connect.patch
# For bz#589952 - QMP breaks when issuing any command with a backslash
Patch1494: kvm-json-lexer-Initialize-x-and-y.patch
# For bz#589952 - QMP breaks when issuing any command with a backslash
Patch1495: kvm-json-lexer-Handle-missing-escapes.patch
# For bz#589952 - QMP breaks when issuing any command with a backslash
Patch1496: kvm-qjson-Handle-f.patch
# For bz#589952 - QMP breaks when issuing any command with a backslash
Patch1497: kvm-json-lexer-Drop-buf.patch
# For bz#589952 - QMP breaks when issuing any command with a backslash
Patch1498: kvm-json-streamer-Don-t-use-qdict_put_obj.patch
# For bz#596119 - Possible corruption after block request merge
Patch1499: kvm-block-fix-sector-comparism-in-multiwrite_req_compare.patch
# For bz#596119 - Possible corruption after block request merge
Patch1500: kvm-block-Fix-multiwrite-with-overlapping-requests.patch
# For bz#595495 - Fail to hotplug pci device to guest
Patch1501: kvm-device-assignment-use-stdint-types.patch
# For bz#595495 - Fail to hotplug pci device to guest
Patch1502: kvm-device-assignment-Don-t-use-libpci.patch
# For bz#595495 - Fail to hotplug pci device to guest
Patch1503: kvm-device-assignment-add-config-fd-qdev-property.patch
# For bz#595301 - QEMU terminates without warning with virtio-net and SMP enabled
Patch1504: kvm-qemu-address-todo-comment-in-exec.c.patch
# For bz#595813 - virtio-blk doesn't handle barriers correctly
Patch1505: kvm-virtio-blk-fix-barrier-support.patch
# changes for make-release with no resulting changes on binary
Patch1506: kvm-make-release-misc-fixes.patch
# For bz#595287 - virtio net/vhost net speed enhancements from upstream kernel
Patch1507: kvm-virtio-utilize-PUBLISH_USED_IDX-feature.patch
# For bz#595263 - virtio net lacks upstream fixes as of may 24
Patch1508: kvm-virtio-invoke-set_features-on-load.patch
# For bz#595263 - virtio net lacks upstream fixes as of may 24
Patch1509: kvm-virtio-net-return-with-value-in-void-function.patch
# For bz#585940 - qemu-kvm crashes on reboot when vhost is enabled
Patch1510: kvm-vhost-net-fix-reversed-logic-in-mask-notifiers.patch
# For bz#595130 - Disable hpet by default
Patch1511: kvm-hpet-Disable-for-Red-Hat-Enterprise-Linux.patch
# For bz#598896 - migration breaks networking with vhost-net
Patch1513: kvm-virtio-net-stop-vhost-backend-on-vmstop.patch
# For bz#598896 - migration breaks networking with vhost-net
Patch1514: kvm-msix-fix-msix_set-unset_mask_notifier.patch
# For bz#585310 - qemu-kvm does not exit when device assignment fails due to IRQ sharing
Patch1515: kvm-device-assignment-fix-failure-to-exit-on-shared-IRQ.patch
# For bz#588719 - Fix monitor command documentation
Patch1516: kvm-doc-Fix-host-forwarding-monitor-command-documentatio.patch
# For bz#588719 - Fix monitor command documentation
Patch1517: kvm-doc-Fix-acl-monitor-command-documentation.patch
# For bz#588719 - Fix monitor command documentation
Patch1518: kvm-doc-Heading-for-monitor-command-cpu-got-lost-restore.patch
# For bz#588719 - Fix monitor command documentation
Patch1519: kvm-doc-Clean-up-monitor-command-function-index.patch
# For bz#593769 - "info cpus" doesn't show halted state
Patch1520: kvm-fix-info-cpus-halted-state-reporting.patch
# For bz#559618 - QMP: Fix 'quit' to return success before exiting
Patch1521: kvm-sysemu-Export-no_shutdown.patch
# For bz#559618 - QMP: Fix 'quit' to return success before exiting
Patch1522: kvm-Monitor-Return-before-exiting-with-quit.patch
# For bz#566291 - QMP: Support vendor extensions
Patch1523: kvm-QMP-Add-Downstream-extension-of-QMP-to-spec.patch
# For bz#580365 - QMP: pci_add/pci_del conversion should be reverted
Patch1524: kvm-Revert-PCI-Convert-pci_device_hot_add-to-QObject.patch
# For bz#580365 - QMP: pci_add/pci_del conversion should be reverted
Patch1525: kvm-Revert-monitor-Convert-do_pci_device_hot_remove-to-Q.patch
# For bz#565609 - Unable to use werror/rerror with  -drive syntax using if=none
# For bz#593256 - Unable to set readonly flag for floppy disks
Patch1526: kvm-drive-allow-rerror-werror-and-readonly-for-if-none.patch
# For bz#596093 - 16bit integer qdev properties are not parsed correctly.
Patch1527: kvm-qdev-properties-Fix-u-intXX-parsers.patch
# For bz#590070 - QEMU misses DESKTOP-RESIZE event if it is triggered during client connection initialization
Patch1528: kvm-vnc-factor-out-vnc_desktop_resize.patch
# For bz#590070 - QEMU misses DESKTOP-RESIZE event if it is triggered during client connection initialization
Patch1529: kvm-vnc-send-desktopresize-event-as-reply-to-set-encodin.patch
# For bz#590070 - QEMU misses DESKTOP-RESIZE event if it is triggered during client connection initialization
Patch1530: kvm-vnc-keep-track-of-client-desktop-size.patch
# For bz#590070 - QEMU misses DESKTOP-RESIZE event if it is triggered during client connection initialization
Patch1531: kvm-vnc-don-t-send-invalid-screen-updates.patch
# For bz#590070 - QEMU misses DESKTOP-RESIZE event if it is triggered during client connection initialization
Patch1532: kvm-vnc-move-size-changed-check-into-the-vnc_desktop_res.patch
# For bz#591759 - Segmentation fault when using vnc to view guest without vga card
Patch1533: kvm-check-for-active_console-before-using-it.patch
# For bz#586349 - BLOCK_IO_ERROR event does not provide the errno that caused it.
Patch1534: kvm-Monitor-Make-RFQDN_REDHAT-public.patch
# For bz#586349 - BLOCK_IO_ERROR event does not provide the errno that caused it.
Patch1535: kvm-QMP-Add-error-reason-to-BLOCK_IO_ERROR-event.patch
# For bz#591494 - Virtio: Transfer file caused guest in same vlan abnormally quit
Patch1536: kvm-virtio-net-truncating-packet.patch
# For bz#600203 - vhost net new userspace on old kernel: 95: falling back on userspace virtio
Patch1537: kvm-vhost-net-check-PUBLISH_USED-in-backend.patch
# For bz#596315 - device assignment truncates MSIX table size
Patch1538: kvm-device-assignment-don-t-truncate-MSIX-capabilities-t.patch
# For bz#561433 - Segfault when keyboard is removed
Patch1539: kvm-If-a-USB-keyboard-is-unplugged-the-keyboard-eventhan.patch
# For bz#599460 - virtio nic is hotpluged when hotplug rtl8139 nic to guest
Patch1540: kvm-net-Fix-hotplug-with-pci_add.patch
# For bz#593758 - qemu fails to start with -cdrom /dev/sr0 if no media inserted
Patch1541: kvm-raw-posix-Detect-CDROM-via-ioctl-on-linux.patch
# For bz#593758 - qemu fails to start with -cdrom /dev/sr0 if no media inserted
Patch1542: kvm-block-Remove-special-case-for-vvfat.patch
# For bz#593758 - qemu fails to start with -cdrom /dev/sr0 if no media inserted
Patch1543: kvm-block-Make-find_image_format-return-raw-BlockDriver-.patch
# For bz#593758 - qemu fails to start with -cdrom /dev/sr0 if no media inserted
Patch1544: kvm-block-Add-missing-bdrv_delete-for-SG_IO-BlockDriver-.patch
# For bz#593758 - qemu fails to start with -cdrom /dev/sr0 if no media inserted
Patch1545: kvm-block-Assume-raw-for-drives-without-media.patch
# For bz#598407 - qcow2 corruption bug in refcount table growth
Patch1546: kvm-qcow2-Fix-corruption-after-refblock-allocation.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1547: kvm-qcow2-Fix-corruption-after-error-in-update_refcount.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1548: kvm-qcow2-Allow-qcow2_get_cluster_offset-to-return-error.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1549: kvm-qcow2-Change-l2_load-to-return-0-errno.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1550: kvm-qcow2-Return-right-error-code-in-write_refcount_bloc.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1551: kvm-qcow2-Clear-L2-table-cache-after-write-error.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1552: kvm-qcow2-Fix-error-handling-in-l2_allocate.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1553: kvm-qcow2-Restore-L1-entry-on-l2_allocate-failure.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1554: kvm-qcow2-Allow-get_refcount-to-return-errors.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1555: kvm-qcow2-Avoid-shadowing-variable-in-alloc_clusters_nor.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1556: kvm-qcow2-Allow-alloc_clusters_noref-to-return-errors.patch
# For bz#598507 - Backport qcow2 error path fixes
Patch1557: kvm-qcow2-Return-real-error-code-in-load_refcount_block.patch
Patch1558: kvm-make-release-make-mtime-owner-group-consistent.patch
# For bz#602724 - VNC disconnect segfault on KVM video consoles
Patch1559: kvm-fix-vnc-memory-corruption-with-width-1400.patch
# For bz#599460 - virtio nic is hotpluged when hotplug rtl8139 nic to guest
Patch1560: kvm-net-Fix-VM-start-with-net-none.patch
# For bz#602590 - Disable pci_add, pci_del, drive_add
Patch1561: kvm-monitor-Remove-pci_add-command-for-Red-Hat-Enterpris.patch
# For bz#602590 - Disable pci_add, pci_del, drive_add
Patch1562: kvm-monitor-Remove-pci_del-command-for-Red-Hat-Enterpris.patch
# For bz#602590 - Disable pci_add, pci_del, drive_add
Patch1563: kvm-monitor-Remove-drive_add-command-for-Red-Hat-Enterpr.patch
# For bz#602026 - Cannot change cdrom by "change device filename [format] " in (qemu) command line
Patch1564: kvm-block-read-only-open-cdrom-as-read-only-when-using-m.patch
# For bz#598022 - Hot-added device is not visible in guest after live-migration.
Patch1565: kvm-acpi_piix4-save-gpe-and-pci-hotplug-slot-status.patch
# For bz#596014 - hot add virtio-blk-pci via device_add lead to virtio network lost
Patch1566: kvm-Don-t-check-for-bus-master-for-old-guests.patch
# For bz#597147 - libvirt: kvm disk error after first stage install of Win2K or WinXP
Patch1567: kvm-Make-IDE-drives-defined-with-device-visible-to-cmos_.patch
# For bz#597147 - libvirt: kvm disk error after first stage install of Win2K or WinXP
Patch1568: kvm-Make-geometry-of-IDE-drives-defined-with-device-visi.patch
# For bz#602417 - Enable VIRTIO_RING_F_PUBLISHED bit for all virtio devices
Patch1569: kvm-virtio-Enable-the-PUBLISH_USED-feature-by-default-fo.patch
# For bz#595647 - Windows guest with qxl driver can't get into S3 state
Patch1570: kvm-do-not-enter-vcpu-again-if-it-was-stopped-during-IO.patch
# For bz#581789 - Cannot eject cd-rom when configured to host cd-rom
Patch1571: kvm-monitor-allow-device-to-be-ejected-if-no-disk-is-ins.patch
# For bz#596609 - Live migration failed when migration during boot
Patch1572: kvm-New-slots-need-dirty-tracking-enabled-when-migrating.patch
# For bz#596274 - QMP: netdev_del sometimes fails claiming the device is in use
Patch1573: kvm-Make-netdev_del-delete-the-netdev-even-when-it-s-in-.patch
# For bz#605359 - Fix MSIX regression from bz595495
Patch1574: kvm-device-assignment-msi-PBA-is-long.patch
# For bz#604210 - Segmentation fault when check  preallocated qcow2 image on lvm.
Patch1575: kvm-qcow2-Fix-qemu-img-check-segfault-on-corrupted-image.patch
# For bz#604210 - Segmentation fault when check  preallocated qcow2 image on lvm.
Patch1576: kvm-qcow2-Don-t-try-to-check-tables-that-couldn-t-be-loa.patch
# For bz#604210 - Segmentation fault when check  preallocated qcow2 image on lvm.
Patch1577: kvm-qcow2-Fix-error-handling-during-metadata-preallocati.patch
# For bz#607200 - qcow2 image corruption when using cache=writeback
Patch1578: kvm-block-Add-bdrv_-p-write_sync.patch
# For bz#607200 - qcow2 image corruption when using cache=writeback
Patch1579: kvm-qcow2-Use-bdrv_-p-write_sync-for-metadata-writes.patch
# For bz#607263 - Unable to launch QEMU with -M pc-0.12 and  virtio serial
Patch1580: kvm-virtio-serial-Fix-compat-property-name.patch
# For bz#606733 - Unable to set the driftfix parameter
Patch1581: kvm-rtc-Remove-TARGET_I386-from-qemu-config.c-enables-dr.patch
# For bz#585009 - QMP: input needs trailing  char
Patch1582: kvm-add-some-tests-for-invalid-JSON.patch
# For bz#585009 - QMP: input needs trailing  char
Patch1583: kvm-implement-optional-lookahead-in-json-lexer.patch
# For bz#585009 - QMP: input needs trailing  char
Patch1584: kvm-remove-unnecessary-lookaheads.patch
# For bz#605704 - qemu-kvm: set per-machine-type smbios strings
Patch1585: kvm-per-machine-type-smbios-Type-1-smbios-values.patch
# For bz#607688 - Excessive lseek() causes severe performance issues with vm disk images over NFS
Patch1586: kvm-raw-posix-Use-pread-pwrite-instead-of-lseek-read-wri.patch
# For bz#607688 - Excessive lseek() causes severe performance issues with vm disk images over NFS
Patch1587: kvm-block-Cache-total_sectors-to-reduce-bdrv_getlength-c.patch
# For bz#599122 - Unable to launch QEMU with a guest disk filename containing a ':'
Patch1588: kvm-block-allow-filenames-with-colons-again-for-host-dev.patch
# For bz#606084 - Allow control of kvm cpuid option via -cpu flag
Patch1589: kvm-Add-KVM-paravirt-cpuid-leaf.patch
# For bz#605638 - Remove unsupported monitor commands from qemu-kvm
Patch1590: kvm-Remove-usage-of-CONFIG_RED_HAT_DISABLED.patch
# For bz#605638 - Remove unsupported monitor commands from qemu-kvm
Patch1591: kvm-monitor-Remove-host_net_add-remove-for-Red-Hat-Enter.patch
# For bz#605638 - Remove unsupported monitor commands from qemu-kvm
Patch1592: kvm-monitor-Remove-usb_add-del-commands-for-Red-Hat-Ente.patch
# For bz#607244 - virtio-blk doesn't load list of pending requests correctly
Patch1593: kvm-virtio-blk-fix-the-list-operation-in-virtio_blk_load.patch
# For bz#596279 - QMP: does not report the real cause of PCI device assignment failure
Patch1594: kvm-QError-Introduce-QERR_DEVICE_INIT_FAILED_2.patch
# For bz#596279 - QMP: does not report the real cause of PCI device assignment failure
Patch1595: kvm-dev-assignment-Report-IRQ-assign-errors-in-QMP.patch
# For bz#603851 - QMP: Can't reuse same 'id' when netdev_add fails
Patch1596: kvm-net-delete-QemuOpts-when-net_client_init-fails.patch
# For bz#587382 - QMP: balloon command may not report an error
Patch1597: kvm-QMP-Fix-error-reporting-in-the-async-API.patch
# For bz#580648 - QMP: Bad package version in greeting message
Patch1598: kvm-QMP-Remove-leading-whitespace-in-package.patch
# For bz#601540 - qemu requires ability to verify location of cpu model definition file..
Patch1599: kvm-Add-optional-dump-of-default-config-file-paths-v2-BZ.patch
# For bz#597198 - qxl: 16bpp vga mode is broken.
Patch1600: kvm-qxl-drop-check-for-depths-32.patch
# For bz#597198 - qxl: 16bpp vga mode is broken.
# For bz#600205 - Live migration cause qemu-kvm Segmentation fault (core dumped)by using "-vga std"
Patch1601: kvm-spice-handle-16-bit-color-depth.patch
# For bz#597968 - Should not allow one physical NIC card to be assigned to one guest for many times
Patch1602: kvm-device-assignment-Don-t-deassign-when-the-assignment.patch
# For bz#566785 - virt block layer must not keep guest's logical_block_size fixed
Patch1603: kvm-block-fix-physical_block_size-calculation.patch
# For bz#601517 - x2apic needs to be present in all new Intel cpu models..
Patch1604: kvm-Add-x2apic-to-cpuid-feature-set-for-new-Intel-models.patch
# For bz#570174 - Restoring a qemu guest from a saved state file using -incoming sometimes fails and hangs
Patch1605: kvm-Exit-if-incoming-migration-fails.patch
# For bz#570174 - Restoring a qemu guest from a saved state file using -incoming sometimes fails and hangs
Patch1606: kvm-Factorize-common-migration-incoming-code.patch
# For bz#605361 - 82576 physical function device assignment doesn't work with win7
Patch1607: kvm-device-assignment-be-more-selective-in-interrupt-dis.patch
# For bz#572043 - Guest gets segfault when do multiple device hot-plug and hot-unplug
Patch1608: kvm-device-assignment-Avoid-munmapping-the-real-MSIX-are.patch
# For bz#572043 - Guest gets segfault when do multiple device hot-plug and hot-unplug
Patch1609: kvm-device-assignment-Cleanup-on-exit.patch
# For bz#582262 - QMP: Missing commands doc
Patch1610: kvm-doc-Update-monitor-info-subcommands.patch
# For bz#582262 - QMP: Missing commands doc
Patch1611: kvm-Fix-typo-in-balloon-help.patch
# For bz#582262 - QMP: Missing commands doc
Patch1612: kvm-monitor-Reorder-info-documentation.patch
# For bz#582262 - QMP: Missing commands doc
Patch1613: kvm-QMP-Introduce-commands-documentation.patch
# For bz#582262 - QMP: Missing commands doc
Patch1614: kvm-QMP-Sync-documentation-with-RHEL6-only-changes.patch
# For bz#582262 - QMP: Missing commands doc
Patch1615: kvm-Monitor-Drop-QMP-documentation-from-code.patch
# For bz#582262 - QMP: Missing commands doc
Patch1616: kvm-hxtool-Fix-line-number-reporting-on-SQMP-EQMP-errors.patch
# For bz#581963 - QMP: missing drive_add command in JSON mode
Patch1617: kvm-monitor-New-command-__com.redhat_drive_add.patch
# For bz#611229 - -rtc cmdline changes
Patch1618: kvm-Fix-driftfix-option.patch
Patch1619: kvm-make-release-fix-mtime-on-rhel6-beta.patch
# For bz#598836 - RHEL 6.0 RTC Alarm unusable in vm
Patch1620: kvm-make-rtc-alatm-work.patch
# For bz#612164 - [kvm] qemu image check returns cluster errors when using virtIO block (thinly provisioned) during e_no_space events (along with EIO errors)
Patch1621: kvm-qemu-img-check-Distinguish-different-kinds-of-errors.patch
# For bz#612164 - [kvm] qemu image check returns cluster errors when using virtIO block (thinly provisioned) during e_no_space events (along with EIO errors)
Patch1622: kvm-qcow2-vdi-Change-check-to-distinguish-error-cases.patch
# For bz#612481 - Enable migration subsections
Patch1623: kvm-Revert-ide-save-restore-pio-atapi-cmd-transfer-field.patch
# For bz#612481 - Enable migration subsections
Patch1624: kvm-vmstate-add-subsections-code.patch
# For bz#612481 - Enable migration subsections
Patch1625: kvm-ide-fix-migration-in-the-middle-of-pio-operation.patch
# For bz#612481 - Enable migration subsections
Patch1626: kvm-ide-fix-migration-in-the-middle-of-a-bmdma-transfer.patch
# For bz#612481 - Enable migration subsections
Patch1627: kvm-Initial-documentation-for-migration-Signed-off-by-Ju.patch
# For bz#607263 - Remove -M pc-0.12 support
Patch1628: kvm-Disable-non-rhel-machine-types-pc-0.12-pc-0.11-pc-0..patch
# For bz#610805 - Move CPU definitions to /usr/share/...
Patch1629: kvm-Move-CPU-definitions-to-usr-share-.-BZ-610805.patch
# For bz#609261 - Exec outgoing migration is too slow
Patch1630: kvm-QEMUFileBuffered-indicate-that-we-re-ready-when-the-.patch
# For bz#611715 - qemu-kvm gets no responsive  when do  hot-unplug pass-through device
Patch1631: kvm-device-assignment-Better-fd-tracking.patch
# For bz#613884 - x2apic needs to be present in all new AMD cpu models..
Patch1634: kvm-Add-x2apic-to-cpuid-feature-set-for-new-AMD-models.-.patch
# For bz#602209 - Core dumped during Guest installation
Patch1635: kvm-block-Fix-early-failure-in-multiwrite.patch
# For bz#602209 - Core dumped during Guest installation
Patch1636: kvm-block-Handle-multiwrite-errors-only-when-all-request.patch
# For bz#584372 - Fails to detect errors when using exec: based migration
Patch1637: kvm-migration-respect-exit-status-with-exec.patch
# For bz#584372 - Fails to detect errors when using exec: based migration
Patch1638: kvm-set-proper-migration-status-on-write-error-v3.patch
# For bz#614377 - Windows 7 requires re-activation when migrated from RHEL5 to RHEL6
Patch1639: kvm-Set-SMBIOS-vendor-to-QEMU-for-RHEL5-machine-types.patch
# For bz#611797 - qemu does not call unlink() on temp files in snapshot mode
Patch1640: kvm-Don-t-reset-bs-is_temporary-in-bdrv_open_common.patch
# For bz#614537 - Skype crashes on VM.
Patch1641: kvm-Change-default-CPU-model-qemu64-to-model-6.patch
# For bz#614537 - Skype crashes on VM.
Patch1642: kvm-set-model-6-on-Intel-CPUs-on-cpu-x86_64.conf.patch
# For bz#615228 - oom in vhost_dev_start
Patch1643: kvm-vhost-fix-miration-during-device-start.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1644: kvm-ram_blocks-Convert-to-a-QLIST.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1645: kvm-Remove-uses-of-ram.last_offset-aka-last_ram_offset.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1646: kvm-pc-Allocate-all-ram-in-a-single-qemu_ram_alloc.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1647: kvm-qdev-Add-a-get_dev_path-function-to-BusInfo.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1648: kvm-pci-Implement-BusInfo.get_dev_path.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1649: kvm-savevm-Add-DeviceState-param.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1650: kvm-savevm-Make-use-of-DeviceState.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1651: kvm-eepro100-Add-a-dev-field-to-eeprom-new-free-function.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1652: kvm-virtio-net-Incorporate-a-DeviceState-pointer-and-let.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1653: kvm-qemu_ram_alloc-Add-DeviceState-and-name-parameters.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1654: kvm-ramblocks-Make-use-of-DeviceState-pointer-and-BusInf.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1655: kvm-savevm-Migrate-RAM-based-on-name-offset.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1656: kvm-savevm-Use-RAM-blocks-for-basis-of-migration.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1657: kvm-savevm-Create-a-new-continue-flag-to-avoid-resending.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1658: kvm-qemu_ram_free-Implement-it.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1659: kvm-pci-Free-the-space-allocated-for-the-option-rom-on-r.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1660: kvm-ramblocks-No-more-being-lazy-about-duplicate-names.patch
# For bz#616525 - savevm needs to reset block info on each new save
Patch1661: kvm-savevm-Reset-last-block-info-at-beginning-of-each-sa.patch
# For bz#615152 - rhel 6 performance worse than rhel5.6 when committing 1G  changes recorded in  snapshot in its base image.
Patch1662: kvm-block-Change-bdrv_commit-to-handle-multiple-sectors-.patch
# For bz#616501 - publish used ABI incompatible with future guests
Patch1663: kvm-Revert-virtio-Enable-the-PUBLISH_USED-feature-by-def.patch
# For bz#616501 - publish used ABI incompatible with future guests
Patch1664: kvm-Revert-vhost-net-check-PUBLISH_USED-in-backend.patch
# For bz#616501 - publish used ABI incompatible with future guests
Patch1665: kvm-Revert-virtio-utilize-PUBLISH_USED_IDX-feature.patch
# For bz#596328 - [RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.
Patch1666: kvm-savevm-Fix-memory-leak-of-compat-struct.patch
# For bz#580010 - migration failed after pci_add and pci_del a virtio storage device
Patch1667: kvm-virtio-blk-Create-exit-function-to-unregister-savevm.patch
# For bz#596232 - Update docs to exclude unsupported options
Patch1668: kvm-Documentation-Add-a-warning-message-to-qemu-kvm-help.patch
# For bz#617534 - Disable SCSI and usb-storage
Patch1669: kvm-Disable-SCSI.patch
# For bz#612074 - core dumped while live migration with spice
Patch1670: kvm-spice-don-t-force-fullscreen-redraw-on-display-resiz.patch
# For bz#616188 - KVM_GET_SUPPORTED_CPUID doesn't return all host cpuid flags..
Patch1671: kvm-KVM_GET_SUPPORTED_CPUID-doesn-t-return-all-host-cpui.patch
# For bz#612696 - virsh attach-device crash kvm guest.
Patch1672: kvm-Do-not-try-loading-option-ROM-for-hotplug-PCI-device.patch
# For bz#591494 - Virtio: Transfer file caused guest in same vlan abnormally quit
Patch1673: kvm-virtio-net-correct-packet-length-checks.patch
# For bz#617414 - avoid canceling in flight ide dma
Patch1674: kvm-avoid-canceling-ide-dma-rediff.patch
# For bz#617463 - Coredump occorred when enable qxl
Patch1675: kvm-spice-Rename-conflicting-ramblock.patch
# For bz#617271 - RHEL6 qemu-kvm guest gets partitioned at sector 63
Patch1676: kvm-block-default-to-0-minimal-optimal-I-O-size.patch
# For bz#581555 - race between qemu monitor "cont" and incoming migration can cause failed restore/migration
Patch1677: kvm-migration-Accept-cont-only-after-successful-incoming.patch
# For bz#617085 - core dumped when add netdev to VM with vhost on
Patch1678: kvm-vhost_dev_unassign_memory-don-t-assert-if-removing-f.patch
# For bz#615214 - [VT-d] Booting RHEL6 guest with Intel 82541PI NIC assigned by libvirt cause qemu crash
Patch1679: kvm-device-assignment-Use-PCI-I-O-port-sysfs-resource-fi.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch1680: kvm-block-Change-bdrv_eject-not-to-drop-the-image.patch
# For bz#618788 - device-assignment hangs with kvm_run: Bad address
Patch1681: kvm-device-assignment-Leave-option-ROM-space-RW-KVM-does.patch
# For bz#616890 - "qemu-img convert" fails on block device
Patch1682: kvm-block-Fix-bdrv_has_zero_init.patch
# For bz#619414 - CVE-2010-2784 qemu: insufficient constraints checking in exec.c:subpage_register() [rhel-6.0]
Patch1683: kvm-Fix-segfault-in-mmio-subpage-handling-code.patch
# For bz#618601 - We need to reopen images after migration
Patch1684: kvm-Migration-reopen-block-devices-files.patch
# For bz#613892 - [SR-IOV]VF device can not start on 32bit Windows2008 SP2
# For bz#618332 - CPUID_EXT_POPCNT enabled in qemu64 and qemu32 built-in models.
Patch1685: kvm-Correct-cpuid-flags-and-model-fields-V2.patch
# For bz#618168 - Qemu-kvm in the src host core dump when do migration by using spice
Patch1686: kvm-Fix-migration-with-spice-enabled.patch
# For bz#607244 - virtio-blk doesn't load list of pending requests correctly
Patch1687: kvm-virtio-Factor-virtqueue_map_sg-out.patch
# For bz#607244 - virtio-blk doesn't load list of pending requests correctly
Patch1688: kvm-virtio-blk-Fix-migration-of-queued-requests.patch
# For bz#607611 - pci hotplug of e1000, rtl8139 nic device fails for all guests.
Patch1689: kvm-qdev-Reset-hotplugged-devices.patch
# For bz#621161 - qemu-kvm crashes with I/O Possible message
Patch1690: kvm-Block-I-O-signals-in-audio-helper-threads.patch
# For bz#622356 - Live migration failed during reboot due to vhost
Patch1691: kvm-vhost-Fix-size-of-dirty-log-sync-on-resize.patch
# For bz#624666 - qemu-img re-base broken on RHEL6
Patch1692: kvm-qemu-img-rebase-Open-new-backing-file-read-only.patch
# For bz#623903 - query-balloon commmand didn't return on pasued guest cause virt-manger hang
Patch1693: kvm-disable-guest-provided-stats-on-info-ballon-monitor-.patch
# For bz#624767 - Replace virtio-net TX timer mitigation with bottom half handler
Patch1695: kvm-virtio-net-Make-tx_timer-timeout-configurable.patch
# For bz#624767 - Replace virtio-net TX timer mitigation with bottom half handler
Patch1696: kvm-virtio-net-Limit-number-of-packets-sent-per-TX-flush.patch
# For bz#624767 - Replace virtio-net TX timer mitigation with bottom half handler
Patch1697: kvm-virtio-net-Rename-tx_timer_active-to-tx_waiting.patch
# For bz#624767 - Replace virtio-net TX timer mitigation with bottom half handler
Patch1698: kvm-virtio-net-Introduce-a-new-bottom-half-packet-TX.patch
# For bz#482427 - support high resolutions
Patch1699: kvm-spice-qxl-enable-some-highres-modes.patch
# For bz#633699 - Cannot hot-plug nic in windows VM when the vmem is larger
Patch1700: kvm-add-MADV_DONTFORK-to-guest-physical-memory-v2.patch
# For bz#596610 - "Guest moved used index from 0 to 61440" if remove virtio serial device before virtserialport
Patch1701: kvm-virtio-serial-Check-if-virtio-queue-is-ready-before-.patch
# For bz#596610 - "Guest moved used index from 0 to 61440" if remove virtio serial device before virtserialport
Patch1702: kvm-virtio-serial-Assert-for-virtio-queue-ready-before-v.patch
# For bz#616703 - qemu-kvm core dump with virtio-serial-pci max-port greater than 31
Patch1703: kvm-virtio-serial-Check-if-more-max_ports-specified-than.patch
# For bz#624396 - migration failed after hot-unplug virtserialport - Unknown savevm section or instance '0000:00:07.0/virtio-console' 0
Patch1704: kvm-virtio-serial-Cleanup-on-device-hot-unplug.patch
# For bz#635354 - Can not commit copy-on-write image's data to raw backing-image
Patch1705: kvm-block-Fix-image-re-open-in-bdrv_commit.patch
# For bz#617119 - Qemu becomes unresponsive during unattended_installation
Patch1706: kvm-qxl-clear-dirty-rectangle-on-resize.patch
# For bz#625948 - qemu exits when hot adding rtl8139 nic to win2k8 guest
Patch1707: kvm-VGA-Don-t-register-deprecated-VBE-range.patch
# For bz#619168 - qemu should more clearly indicate internal detection of this host out-of-memory condition at startup..
Patch1708: kvm-BZ-619168-qemu-should-more-clearly-indicate-internal.patch
# For bz#639437 - Incorrect russian vnc keymap
Patch1709: kvm-fix-and-on-russian-keymap.patch
# For bz#631522 - spice: prepare qxl for 6.1 update.
Patch1710: kvm-spice-qxl-update-modes-ptr-in-post_load.patch
# For bz#631522 - spice: prepare qxl for 6.1 update.
Patch1711: kvm-spice-qxl-make-draw_area-and-vgafb-share-memory.patch
# For bz#632054 - [Intel 6.0 Virt] guest bootup fail with intel 82574L NIC assigned
Patch1713: kvm-Fix-underflow-error-in-device-assignment-size-check.patch
# For bz#641127 - qemu-img ignores close() errors
Patch1714: kvm-check-for-close-errors-on-qcow2_create.patch
# For bz#599307 - info snapshot return "bdrv_snapshot_list: error -95"
Patch1715: kvm-savevm-Really-verify-if-a-drive-supports-snapshots.patch
# For bz#643681 - Do not advertise boot=on capability to libvirt
Patch1716: kvm-drop-boot-on-from-help-string.patch
# For bz#585910 - [Intel 6.1 Bug] SRAO MCE in guest kills QEMU-KVM (qemu-kvm component)
Patch1717: kvm-Fix-parameters-of-prctl.patch
# For bz#585910 - [Intel 6.1 Bug] SRAO MCE in guest kills QEMU-KVM (qemu-kvm component)
Patch1718: kvm-Ignore-SRAO-MCE-if-another-MCE-is-being-processed.patch
# For bz#585910 - [Intel 6.1 Bug] SRAO MCE in guest kills QEMU-KVM (qemu-kvm component)
Patch1719: kvm-Add-RAM-physical-addr-mapping-in-MCE-simulation.patch
# For bz#585910 - [Intel 6.1 Bug] SRAO MCE in guest kills QEMU-KVM (qemu-kvm component)
Patch1720: kvm-Add-savevm-loadvm-support-for-MCE.patch
# For bz#585910 - [Intel 6.1 Bug] SRAO MCE in guest kills QEMU-KVM (qemu-kvm component)
Patch1721: kvm-Fix-SRAO-SRAR-MCE-injecting-on-guest-without-MCG_SER.patch
# For bz#634661 - [RHEL6 Snap13]: Hot-unplugging of virtio nic issue in Windows2008 KVM guest.
Patch1722: kvm-net-delay-freeing-peer-host-device.patch
# For bz#624607 - [qemu] [rhel6] guest installation stop (pause) on 'eother' event over COW disks (thin-provisioning)
Patch1723: kvm-QMP-Improve-debuggability-of-the-BLOCK_IO_ERROR-even.patch
# For bz#603413 - RHEL3.9 guest netdump hung with e1000
Patch1724: kvm-bz-603413-e1000-secrc-support.patch
# For bz#581750 - Vhost: Segfault when assigning a none vhostfd
Patch1725: kvm-net-properly-handle-illegal-fd-vhostfd-from-command-.patch
# For bz#647307 - Support slow mapping of PCI Bars
Patch1726: kvm-Enable-non-page-boundary-BAR-device-assignment.patch
# For bz#647307 - Support slow mapping of PCI Bars
Patch1727: kvm-Fix-build-failure-with-DEVICE_ASSIGNMENT_DEBUG.patch
# For bz#647307 - Support slow mapping of PCI Bars
Patch1728: kvm-slow_map-minor-improvements-to-ROM-BAR-handling.patch
# For bz#647307 - Support slow mapping of PCI Bars
Patch1729: kvm-device-assignment-Always-use-slow-mapping-for-PCI-op.patch
# For bz#648333 - TCP checksum overflows in qemu's e1000 emulation code when TSO is enabled in guest OS
Patch1730: kvm-e1000-Fix-TCP-checksum-overflow-with-TSO.patch
# For bz#647307 - Support slow mapping of PCI Bars
Patch1731: kvm-device-assignment-Fix-slow-option-ROM-mapping.patch
# For bz#653582 - Changing media with -snapshot deletes image file
Patch1732: kvm-Fix-snapshot-deleting-images-on-disk-change.patch
# For bz#625681 - RFE QMP: should have command to disconnect and connect network card for whql testing
Patch1733: kvm-monitor-Rename-argument-type-b-to-f.patch
# For bz#625681 - RFE QMP: should have command to disconnect and connect network card for whql testing
Patch1734: kvm-monitor-New-argument-type-b-bool.patch
# For bz#625681 - RFE QMP: should have command to disconnect and connect network card for whql testing
Patch1735: kvm-monitor-Use-argument-type-b-for-set_link.patch
# For bz#625681 - RFE QMP: should have command to disconnect and connect network card for whql testing
Patch1736: kvm-monitor-Convert-do_set_link-to-QObject-QError.patch
# For bz#653536 - qemu-img convert poor performance
Patch1737: kvm-cleanup-block-driver-option-handling-in-vl.c.patch
# For bz#653536 - qemu-img convert poor performance
Patch1738: kvm-Add-cache-unsafe-parameter-to-drive.patch
# For bz#653536 - qemu-img convert poor performance
Patch1739: kvm-move-unsafe-to-end-of-caching-modes-in-help.patch
# For bz#653536 - qemu-img convert poor performance
Patch1740: kvm-qemu-img-Eliminate-bdrv_new_open-code-duplication.patch
# For bz#653536 - qemu-img convert poor performance
Patch1741: kvm-qemu-img-Fix-BRDV_O_FLAGS-typo.patch
# For bz#653536 - qemu-img convert poor performance
Patch1742: kvm-qemu-img-convert-Use-cache-unsafe-for-output-image.patch
# For bz#625319 - Failed to update the media in floppy device
Patch1743: kvm-block-Fix-virtual-media-change-for-if-none.patch
# For bz#624721 - [qemu] [rhel6] bad error handling when qemu has no 'read' permissions over {kernel,initrd} files [pass boot options]
Patch1744: kvm-Check-for-invalid-initrd-file.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1745: kvm-qcow-qcow2-implement-bdrv_aio_flush.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1746: kvm-block-Remove-unused-s-hd-in-various-drivers.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1747: kvm-qcow2-Remove-unnecessary-flush-after-L2-write.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1748: kvm-qcow2-Move-sync-out-of-write_refcount_block_entries.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1749: kvm-qcow2-Move-sync-out-of-update_refcount.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1750: kvm-qcow2-Move-sync-out-of-qcow2_alloc_clusters.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1751: kvm-qcow2-Get-rid-of-additional-sync-on-COW.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1752: kvm-cutils-qemu_iovec_copy-and-qemu_iovec_memset.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1753: kvm-qcow2-Avoid-bounce-buffers-for-AIO-read-requests.patch
# For bz#653972 - qcow2: Backport performance related patches
Patch1754: kvm-qcow2-Avoid-bounce-buffers-for-AIO-write-requests.patch
# For bz#604992 - index is empty in qemu-doc.html
Patch1755: kvm-kill-empty-index-on-qemu-doc.texi.patch
# For bz#645342 - Implement QEMU driver for modern sound device like Intel HDA
Patch1756: kvm-add-VMSTATE_BOOL.patch
# For bz#645342 - Implement QEMU driver for modern sound device like Intel HDA
Patch1757: kvm-Add-Intel-HD-Audio-support-to-qemu.patch
# For bz#613893 - [RFE] qemu-io enable truncate function for qcow2.
Patch1758: kvm-qcow2-Implement-bdrv_truncate-for-growing-images.patch
# For bz#613893 - [RFE] qemu-io enable truncate function for qcow2.
Patch1759: kvm-qemu-img-Add-resize-command-to-grow-shrink-disk-imag.patch
# For bz#613893 - [RFE] qemu-io enable truncate function for qcow2.
Patch1760: kvm-qemu-img-Fix-copy-paste-bug-in-documentation.patch
# For bz#608548 - QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT
Patch1761: kvm-Fix-compilation-error-missing-include-statement.patch
# For bz#608548 - QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT
Patch1762: kvm-use-qemu_blockalign-consistently.patch
# For bz#608548 - QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT
Patch1763: kvm-raw-posix-handle-512-byte-alignment-correctly.patch
# For bz#608548 - QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT
Patch1764: kvm-virtio-blk-propagate-the-required-alignment.patch
# For bz#608548 - QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT
Patch1765: kvm-scsi-disk-propagate-the-required-alignment.patch
# For bz#608548 - QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT
Patch1766: kvm-ide-propagate-the-required-alignment.patch
# For bz#635954 - RFE: Assigned device should block migration
Patch1767: kvm-Support-marking-a-device-as-non-migratable.patch
# For bz#635954 - RFE: Assigned device should block migration
Patch1768: kvm-device-assignment-Register-as-un-migratable.patch
# For bz#658288 - Include (disabled by default) -fake-machine patch on qemu-kvm RPM spec
Patch1769: kvm-New-option-fake-machine.patch
# For bz#662633 - Fix build problem with recent compilers
Patch1770: kvm-Fix-build-problem-with-recent-compilers.patch
# For bz#628634 - vhost_net: untested error handling in vhost_net_start
Patch1771: kvm-vhost-fix-infinite-loop-on-error-path.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1772: kvm-pci-import-Linux-pci_regs.h.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1773: kvm-pci-s-PCI_SUBVENDOR_ID-PCI_SUBSYSTEM_VENDOR_ID-g.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1774: kvm-pci-use-pci_regs.h.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1775: kvm-pci-add-API-to-add-capability-at-a-known-offset.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1776: kvm-pci-consolidate-pci_add_capability_at_offset-into-pc.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1777: kvm-pci-pci_default_cap_write_config-ignores-wmask.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1778: kvm-pci-Remove-pci_enable_capability_support.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1779: kvm-device-assignment-Use-PCI-capabilities-support.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1780: kvm-pci-Replace-used-bitmap-with-config-byte-map.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1781: kvm-pci-Remove-cap.length-cap.start-cap.supported.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1782: kvm-device-assignment-Move-PCI-capabilities-to-match-phy.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1783: kvm-pci-Remove-capability-specific-handlers.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1784: kvm-device-assignment-Make-use-of-config_map.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1785: kvm-device-assignment-Fix-off-by-one-in-header-check.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1786: kvm-pci-Remove-PCI_CAPABILITY_CONFIG_.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1787: kvm-pci-Error-on-PCI-capability-collisions.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1788: kvm-device-assignment-Error-checking-when-adding-capabil.patch
# For bz#624790 - pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.
Patch1789: kvm-device-assignment-pass-through-and-stub-more-PCI-cap.patch
# For bz#623735 - hot unplug of vhost net virtio NIC causes qemu segfault
Patch1790: kvm-virtio-invoke-set_status-callback-on-reset.patch
# For bz#623735 - hot unplug of vhost net virtio NIC causes qemu segfault
Patch1791: kvm-virtio-net-unify-vhost-net-start-stop.patch
# For bz#623735 - hot unplug of vhost net virtio NIC causes qemu segfault
Patch1792: kvm-tap-clear-vhost_net-backend-on-cleanup.patch
# For bz#623735 - hot unplug of vhost net virtio NIC causes qemu segfault
Patch1793: kvm-tap-make-set_offload-a-nop-after-netdev-cleanup.patch
# For bz#628308 - [RFE] let management choose whether transparent huge pages are used
Patch1794: kvm-let-management-choose-whether-transparent-huge-pages.patch
# For bz#616659 - mrg buffers: migration breaks between systems with/without vhost
Patch1795: kvm-tap-generalize-code-for-different-vnet-header-len.patch
# For bz#616659 - mrg buffers: migration breaks between systems with/without vhost
Patch1796: kvm-tap-add-APIs-for-vnet-header-length.patch
# For bz#616659 - mrg buffers: migration breaks between systems with/without vhost
Patch1797: kvm-vhost_net-mergeable-buffers-support.patch
# For bz#623552 - SCP image fails from host to guest with vhost on when do migration
Patch1798: kvm-vhost-Fix-address-calculation-in-vhost_dev_sync_regi.patch
# For bz#632257 - Duplicate CPU fea.tures in cpu-x86_64.conf
Patch1799: kvm-Bug-632257-Duplicate-CPU-fea.tures-in-cpu-x86_64.con.patch
# For bz#647308 - Support Westmere as a CPU model or included within existing models..
Patch1800: kvm-BZ-647308-Support-Westmere-as-a-CPU-model-or-include.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1801: kvm-trace-Add-trace-events-file-for-declaring-trace-even.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1802: kvm-trace-Support-disabled-events-in-trace-events.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1803: kvm-trace-Add-user-documentation.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1804: kvm-trace-Trace-qemu_malloc-and-qemu_vmalloc.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1805: kvm-trace-Trace-virtio-blk-multiwrite-and-paio_submit.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1806: kvm-trace-Trace-virtqueue-operations.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1807: kvm-trace-Trace-port-IO.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1808: kvm-trace-Trace-entry-point-of-balloon-request-handler.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1809: kvm-trace-fix-a-typo.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1810: kvm-trace-fix-a-regex-portability-problem.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1811: kvm-trace-avoid-unnecessary-recompilation-if-nothing-cha.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1812: kvm-trace-Use-portable-format-strings.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1813: kvm-trace-Don-t-strip-lines-containing-arbitrarily.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1814: kvm-trace-Trace-bdrv_aio_-readv-writev.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1815: kvm-trace-remove-timestamp-files-when-cleaning-up.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1816: kvm-trace-Format-strings-must-begin-end-with-double-quot.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1817: kvm-apic-convert-debug-printf-statements-to-tracepoints.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1818: kvm-Add-a-DTrace-tracing-backend-targetted-for-SystemTAP.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1819: kvm-Add-support-for-generating-a-systemtap-tapset-static.patch
# For bz#632722 - [6.1 FEAT] QEMU static tracing framework
Patch1820: kvm-trace-Trace-vm_start-vm_stop.patch
# For bz#636494 - -cpu check  does not correctly enforce CPUID items
Patch1821: kvm-BZ-636494-cpu-check-does-not-correctly-enforce-CPUID.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1822: kvm-QDict-Introduce-qdict_get_qdict.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1823: kvm-monitor-QMP-Drop-info-hpet-query-hpet.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1824: kvm-QMP-Teach-basic-capability-negotiation-to-python-exa.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1825: kvm-QMP-Fix-python-helper-wrt-long-return-strings.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1826: kvm-QMP-update-query-version-documentation.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1827: kvm-Revert-QMP-Remove-leading-whitespace-in-package.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1828: kvm-QMP-monitor-update-do_info_version-to-output-broken-.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1829: kvm-QMP-Remove-leading-whitespace-in-package-again.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1830: kvm-QMP-doc-Add-Stability-Considerations-section.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1831: kvm-QMP-Update-README-file.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1832: kvm-QMP-Revamp-the-Python-class-example.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1833: kvm-QMP-Revamp-the-qmp-shell-script.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1834: kvm-QMP-Drop-vm-info-example-script.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1835: kvm-qemu-char-Introduce-Memory-driver.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1836: kvm-QMP-Introduce-Human-Monitor-passthrough-command.patch
# For bz#647447 - QMP:  provide a hmp_passthrough command to allow execution of non-converted commands
Patch1837: kvm-QMP-qmp-shell-Introduce-HMP-mode.patch
# For bz#667188 - device-assignment leaks option ROM memory
Patch1838: kvm-PCI-Export-pci_map_option_rom.patch
# For bz#667188 - device-assignment leaks option ROM memory
Patch1839: kvm-device-assignment-Allow-PCI-to-manage-the-option-ROM.patch
# For bz#656198 - Can only see 16 virtio ports while assigned 30 virtio serial ports on commandLine
Patch1840: kvm-virtio-serial-bus-bump-up-control-vq-size-to-32.patch
# For bz#635954 - RFE: Assigned device should block migration
Patch1841: kvm-Move-stdbool.h.patch
# For bz#635954 - RFE: Assigned device should block migration
Patch1842: kvm-savevm-Fix-no_migrate.patch
# For bz#635954 - RFE: Assigned device should block migration
Patch1843: kvm-device-assignment-Properly-terminate-vmsd.fields.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1844: kvm-spice-rip-out-all-the-old-non-upstream-spice-bits.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1845: kvm-Use-display-types-for-local-display-only.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1846: kvm-add-pflib-PixelFormat-conversion-library.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1847: kvm-Add-support-for-generic-notifier-lists.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1848: kvm-Rewrite-mouse-handlers-to-use-QTAILQ-and-to-have-an-.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1849: kvm-Add-kbd_mouse_has_absolute.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1850: kvm-Add-notifier-for-mouse-mode-changes.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1851: kvm-sdl-use-mouse-mode-notifier.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1852: kvm-input-make-vnc-use-mouse-mode-notifiers.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1853: kvm-vnc-make-sure-to-send-pointer-type-change-event-on-S.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1854: kvm-vmmouse-adapt-to-mouse-handler-changes.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1855: kvm-wacom-tablet-activate-event-handlers.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1856: kvm-cursor-add-cursor-functions.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1857: kvm-use-new-cursor-struct-functions-for-vmware-vga-and-s.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1858: kvm-add-spice-into-the-configure-file-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1859: kvm-spice-core-bits-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1860: kvm-spice-add-keyboard-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1861: kvm-spice-add-mouse-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1862: kvm-spice-simple-display-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1863: kvm-spice-add-tablet-support.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1864: kvm-spice-tls-support-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1865: kvm-spice-make-compression-configurable.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1866: kvm-spice-add-config-options-for-channel-security.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1867: kvm-spice-add-config-options-for-the-listening-address.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1868: kvm-spice-add-misc-config-options.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1869: kvm-spice-add-audio.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1870: kvm-add-copyright-to-spiceaudio.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1871: kvm-spice-core-fix-watching-for-write-events.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1872: kvm-spice-core-fix-warning-when-building-with-spice-0.6..patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1873: kvm-spice-display-replace-private-lock-with-qemu-mutex.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1874: kvm-spice-add-qxl-device-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1875: kvm-spice-connection-events.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1876: kvm-spice-add-qmp-query-spice-and-hmp-info-spice-command.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1877: kvm-Revert-vnc-support-password-expire.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1878: kvm-vnc-auth-reject-cleanup.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1879: kvm-vnc-support-password-expire-again.patch
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#634153 - coredumped when enable qxl without spice
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#631832 - manpage is missing spice options
# For bz#647865 - support 2560x1440 in qxl
Patch1880: kvm-vnc-spice-add-set_passwd-monitor-command.patch
# For bz#653591 - [RHEL6 Snap13]: Hot-unplugging issue noticed with rtl8139nic after migration of KVM guest.
Patch1881: kvm-qdev-Track-runtime-machine-modifications.patch
# For bz#653591 - [RHEL6 Snap13]: Hot-unplugging issue noticed with rtl8139nic after migration of KVM guest.
Patch1882: kvm-rtl8139-Use-subsection-to-restrict-migration-after-h.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1883: kvm-add-migration-state-change-notifiers.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1884: kvm-spice-vnc-client-migration.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1885: kvm-vnc-spice-fix-never-and-now-expire_time.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1886: kvm-spice-qxl-zap-spice-0.4-migration-compatibility-bits.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1887: kvm-spice-add-chardev-v4.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1888: kvm-qxl-locking-fix.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1889: kvm-spice-qxl-locking-fix-for-qemu-kvm.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1890: kvm-spice-qmp-events-restore-rhel6.0-compatibility.patch
# For bz#615947 - RFE QMP: support of query spice for guest
# For bz#631832 - manpage is missing spice options
# For bz#632458 - Guest may core dump when booting with spice and qxl.
# For bz#634153 - coredumped when enable qxl without spice
# For bz#642131 - qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits'
# For bz#647865 - support 2560x1440 in qxl
Patch1891: kvm-spice-monitor-commands-restore-rhel6.0-compatibility.patch
# For bz#638468 - [qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug
Patch1892: kvm-switch-stdvga-to-pci-vgabios.patch
# For bz#638468 - [qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug
Patch1893: kvm-switch-vmware_vga-to-pci-vgabios.patch
# For bz#638468 - [qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug
Patch1894: kvm-add-rhel6.1.0-machine-type.patch
# For bz#638468 - [qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug
Patch1895: kvm-vgabios-update-handle-compatibility-with-older-qemu-.patch
# For bz#672187 - Improper responsive message when shrinking qcow2 image
Patch1896: kvm-qemu-io-Fix-error-messages.patch
# For bz#637180 - watchdog timer isn't reset when qemu resets
Patch1897: kvm-wdt_i6300esb-register-a-reset-function.patch
# For bz#637180 - watchdog timer isn't reset when qemu resets
Patch1898: kvm-Watchdog-disable-watchdog-timer-when-hard-rebooting-.patch
# For bz#672720 - getting 'ctrl buffer too small' error on USB passthrough
Patch1899: kvm-usb-linux-increase-buffer-for-USB-control-requests.patch
# For bz#670787 - Hot plug the 14st VF to guest causes guest shut down
Patch1900: kvm-device-assignment-Cap-number-of-devices-we-can-have-.patch
# For bz#669268 - WinXP hang when reboot after setup copies files to the installation folders
Patch1901: kvm-clear-vapic-after-reset.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1902: kvm-add-support-for-protocol-driver-create_options.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1903: kvm-qemu-img-avoid-calling-exit-1-to-release-resources-p.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1904: kvm-Use-qemu_mallocz-instead-of-calloc-in-img_convert.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1905: kvm-img_convert-Only-try-to-free-bs-entries-if-bs-is-val.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1906: kvm-Consolidate-printing-of-block-driver-options.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1907: kvm-Fix-formatting-and-missing-braces-in-qemu-img.c.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1908: kvm-Fail-if-detecting-an-unknown-option.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1909: kvm-Make-error-handling-more-consistent-in-img_create-an.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1910: kvm-qemu-img-Deprecate-obsolete-6-and-e-options.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1911: kvm-qemu-img-Free-option-parameter-lists-in-img_create.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1912: kvm-qemu-img-Fail-creation-if-backing-format-is-invalid.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1913: kvm-Introduce-strtosz-library-function-to-convert-a-stri.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1914: kvm-Introduce-strtosz_suffix.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1915: kvm-qemu-img.c-Clean-up-handling-of-image-size-in-img_cr.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1916: kvm-qemu-img.c-Re-factor-img_create.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1917: kvm-Introduce-do_snapshot_blkdev-and-monitor-command-to-.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1918: kvm-Prevent-creating-an-image-with-the-same-filename-as-.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1919: kvm-qemu-option-Fix-uninitialized-value-in-append_option.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1920: kvm-bdrv_img_create-use-proper-errno-return-values.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1921: kvm-block-Use-backing-format-driver-during-image-creatio.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1922: kvm-Make-strtosz-return-int64_t-instead-of-ssize_t.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1923: kvm-strtosz-use-unsigned-char-and-switch-to-qemu_isspace.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1924: kvm-strtosz-use-qemu_toupper-to-simplify-switch-statemen.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1925: kvm-strtosz-Fix-name-confusion-in-use-of-modf.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1926: kvm-strtosz-Use-suffix-macros-in-switch-statement.patch
# For bz#637701 - RFE - support live snapshot of a subset of disks without RAM
Patch1927: kvm-do_snapshot_blkdev-error-on-missing-snapshot_file-ar.patch
# For bz#672229 - romfile memory leak
Patch1928: kvm-pci-memory-leak-of-PCIDevice-rom_file.patch
# For bz#625333 - qemu treatment of -nodefconfig and -readconfig problematic for debug
Patch1929: kvm-Bug-625333-qemu-treatment-of-nodefconfig-and-readcon.patch
# For bz#670539 - Block devices don't implement correct flush error handling
Patch1930: kvm-ide-Factor-ide_flush_cache-out.patch
# For bz#670539 - Block devices don't implement correct flush error handling
Patch1931: kvm-ide-Handle-flush-failure.patch
# For bz#670539 - Block devices don't implement correct flush error handling
Patch1932: kvm-virtio-blk-Respect-werror-option-for-flushes.patch
# For bz#670539 - Block devices don't implement correct flush error handling
Patch1933: kvm-block-Allow-bdrv_flush-to-return-errors.patch
# For bz#670539 - Block devices don't implement correct flush error handling
Patch1934: kvm-ide-Handle-immediate-bdrv_aio_flush-failure.patch
# For bz#670539 - Block devices don't implement correct flush error handling
Patch1935: kvm-virtio-blk-Handle-immediate-flush-failure-properly.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1936: kvm-vhost-error-code.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1937: kvm-vhost-fix-up-irqfd-support.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1938: kvm-virtio-pci-mask-notifier-error-handling-fixups.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1939: kvm-test-for-ioeventfd-support-on-old-kernels.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1940: kvm-virtio-pci-Rename-bugs-field-to-flags.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1941: kvm-virtio-move-vmstate-change-tracking-to-core.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1942: kvm-virtio-pci-Use-ioeventfd-for-virtqueue-notify.patch
# For bz#633394 - [6.1 FEAT] virtio-blk ioeventfd support
Patch1943: kvm-ioeventfd-error-handling-cleanup.patch
# For bz#635418 - Allow enable/disable ksm per VM
Patch1944: kvm-remove-redhat-disable-THP.patch
# For bz#498774 - QEMU: Too many devices are available for unplug in Windows XP (and we don't support that)
Patch1945: kvm-PATCH-RHEL6.1-qemu-kvm-acpi_piix4-qdevfy.patch
# For bz#498774 - QEMU: Too many devices are available for unplug in Windows XP (and we don't support that)
Patch1946: kvm-PATCH-RHEL6.1-qemu-kvm-pci-allow-devices-being-tagge.patch
# For bz#498774 - QEMU: Too many devices are available for unplug in Windows XP (and we don't support that)
Patch1947: kvm-PATCH-RHEL6.1-qemu-kvm-piix-tag-as-not-hotpluggable.patch
# For bz#498774 - QEMU: Too many devices are available for unplug in Windows XP (and we don't support that)
Patch1948: kvm-PATCH-RHEL6.1-qemu-kvm-vga-tag-as-not-hotplugable-v3.patch
# For bz#498774 - QEMU: Too many devices are available for unplug in Windows XP (and we don't support that)
Patch1949: kvm-PATCH-RHEL6.1-qemu-kvm-qxl-tag-as-not-hotpluggable.patch
# For bz#498774 - QEMU: Too many devices are available for unplug in Windows XP (and we don't support that)
Patch1950: kvm-PATCH-RHEL6.1-qemu-kvm-acpi_piix4-expose-no_hotplug-.patch
# For bz#621484 - Broken pipe when working with unix socket chardev
Patch1951: kvm-char-Split-out-tcp-socket-close-code-in-a-separate-f.patch
# For bz#621484 - Broken pipe when working with unix socket chardev
Patch1952: kvm-char-mark-socket-closed-if-write-fails-with-EPIPE.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1953: kvm-Introduce-fw_name-field-to-DeviceInfo-structure.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1954: kvm-Introduce-new-BusInfo-callback-get_fw_dev_path.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1955: kvm-Keep-track-of-ISA-ports-ISA-device-is-using-in-qdev.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1956: kvm-Add-get_fw_dev_path-callback-to-ISA-bus-in-qdev.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1957: kvm-Store-IDE-bus-id-in-IDEBus-structure-for-easy-access.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1958: kvm-Add-get_fw_dev_path-callback-to-IDE-bus.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1959: kvm-Add-get_fw_dev_path-callback-for-system-bus.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1960: kvm-Add-get_fw_dev_path-callback-for-pci-bus.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1961: kvm-Record-which-USBDevice-USBPort-belongs-too.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1962: kvm-Add-get_fw_dev_path-callback-for-usb-bus.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1963: kvm-Add-get_fw_dev_path-callback-to-scsi-bus.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1964: kvm-Add-bootindex-parameter-to-net-block-fd-device.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1965: kvm-Change-fw_cfg_add_file-to-get-full-file-path-as-a-pa.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1966: kvm-Add-bootindex-for-option-roms.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1967: kvm-Add-notifier-that-will-be-called-when-machine-is-ful.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1968: kvm-Pass-boot-device-list-to-firmware.patch
# For bz#635527 - KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk
Patch1969: kvm-close-all-the-block-drivers-before-the-qemu-process-.patch
# For bz#635527 - KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk
Patch1970: kvm-qemu-img-snapshot-Use-writeback-caching.patch
# For bz#635527 - KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk
Patch1971: kvm-qcow2-Add-QcowCache.patch
# For bz#635527 - KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk
Patch1972: kvm-qcow2-Use-QcowCache.patch
# For bz#635527 - KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk
Patch1973: kvm-qcow2-Batch-flushes-for-COW.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1975: kvm-add-bootindex-parameter-to-assigned-device.patch
# For bz#674539 - slow guests block other guests on the same lan
Patch1976: kvm-tap-safe-sndbuf-default.patch
# For bz#643687 - Allow to specify boot order on qemu command line.
Patch1977: kvm-do-not-pass-NULL-to-strdup.patch
# For bz#672441 - Tracetool autogenerate qemu-kvm.stp with wrong qemu-kvm path
Patch1978: kvm-Use-Makefile-to-install-qemu-kvm-in-correct-location.patch
# For bz#667976 - CVE-2011-0011 qemu-kvm: Setting VNC password to empty string silently disables all authentication [rhel-6.1]
Patch1979: kvm-Fix-CVE-2011-0011-qemu-kvm-Setting-VNC-password-to-e.patch
# For bz#674562 - disable vhost-net for rhel5 and older guests
Patch1980: kvm-vhost-force-vhost-off-for-non-MSI-guests.patch
# For bz#515775 - [RFE] Include support for online resizing of storage and network block devices
Patch1981: kvm-Add-support-for-o-octet-bytes-format-as-monitor-para.patch
# For bz#515775 - [RFE] Include support for online resizing of storage and network block devices
Patch1982: kvm-block-add-block_resize-monitor-command.patch
# For bz#515775 - [RFE] Include support for online resizing of storage and network block devices
Patch1983: kvm-block-tell-drivers-about-an-image-resize.patch
# For bz#515775 - [RFE] Include support for online resizing of storage and network block devices
Patch1984: kvm-virtio-blk-tell-the-guest-about-size-changes.patch
# For bz#641833 - Spice CAC support - qemu
Patch1985: kvm-qdev-add-print_options-callback.patch
# For bz#641833 - Spice CAC support - qemu
Patch1986: kvm-qdev-add-data-pointer-to-Property.patch
# For bz#641833 - Spice CAC support - qemu
Patch1987: kvm-qdev-properties-add-PROP_TYPE_ENUM.patch
# For bz#641833 - Spice CAC support - qemu
Patch1988: kvm-usb-ccid-add-CCID-bus.patch
# For bz#641833 - Spice CAC support - qemu
Patch1989: kvm-introduce-libcacard-vscard_common.h.patch
# For bz#641833 - Spice CAC support - qemu
Patch1990: kvm-ccid-add-passthru-card-device.patch
# For bz#641833 - Spice CAC support - qemu
Patch1991: kvm-libcacard-initial-commit.patch
# For bz#641833 - Spice CAC support - qemu
Patch1992: kvm-ccid-add-ccid-card-emulated-device-v2.patch
# For bz#641833 - Spice CAC support - qemu
Patch1993: kvm-ccid-add-docs.patch
# For bz#641833 - Spice CAC support - qemu
Patch1994: kvm-ccid-configure-fix-enable-disable-flags.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch1995: kvm-virtio-console-Factor-out-common-init-between-consol.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch1996: kvm-virtio-console-Remove-unnecessary-braces.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch1997: kvm-virtio-serial-Use-a-struct-to-pass-config-informatio.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch1998: kvm-Fold-send_all-wrapper-unix_write-into-one-function.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch1999: kvm-char-Add-a-QemuChrHandlers-struct-to-initialise-char.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2000: kvm-virtio-serial-move-out-discard-logic-in-a-separate-f.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2001: kvm-virtio-serial-Make-sure-virtqueue-is-ready-before-di.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2002: kvm-virtio-serial-Don-t-copy-over-guest-buffer-to-host.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2003: kvm-virtio-serial-Let-virtio-serial-bus-know-if-all-data.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2004: kvm-virtio-serial-Add-support-for-flow-control.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2005: kvm-virtio-serial-Add-rhel6.0.0-compat-property-for-flow.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2006: kvm-virtio-serial-save-restore-new-fields-in-port-struct.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2007: kvm-Convert-io-handlers-to-QLIST.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2008: kvm-iohandlers-Add-enable-disable_write_fd_handler-funct.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2009: kvm-char-Add-framework-for-a-write-unblocked-callback.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2010: kvm-char-Update-send_all-to-handle-nonblocking-chardev-w.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2011: kvm-char-Equip-the-unix-tcp-backend-to-handle-nonblockin.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
# For bz#621484 - Broken pipe when working with unix socket chardev
Patch2012: kvm-char-Throttle-when-host-connection-is-down.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2013: kvm-virtio-console-Enable-port-throttling-when-chardev-i.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2014: kvm-Add-spent-time-to-migration.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2015: kvm-No-need-to-iterate-if-we-already-are-over-the-limit.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2016: kvm-don-t-care-about-TLB-handling.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2017: kvm-Only-calculate-expected_time-for-stage-2.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2018: kvm-Count-nanoseconds-with-uint64_t-not-doubles.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2019: kvm-Exit-loop-if-we-have-been-there-too-long.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2020: kvm-Maintaing-number-of-dirty-pages.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2021: kvm-Drop-qemu_mutex_iothread-during-migration.patch
# For bz#643970 - guest migration turns failed by the end (16G + stress load)
Patch2022: kvm-Revert-Drop-qemu_mutex_iothread-during-migration.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2023: kvm-ide-Remove-redundant-IDEState-member-conf.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2024: kvm-ide-Split-ide_init1-off-ide_init2-v2.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2025: kvm-ide-Change-ide_init_drive-to-require-valid-dinfo-arg.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2026: kvm-ide-Split-non-qdev-code-off-ide_init2.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2027: kvm-qdev-Don-t-leak-string-property-value-on-hot-unplug.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2028: kvm-blockdev-New-drive_get_by_blockdev-v2.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2029: kvm-blockdev-Clean-up-automatic-drive-deletion-v2.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2030: kvm-qdev-Decouple-qdev_prop_drive-from-DriveInfo-v2.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2031: kvm-block-Catch-attempt-to-attach-multiple-devices-to-a-.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2032: kvm-Implement-drive_del-to-decouple-block-removal-from-d.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2033: kvm-blockdev-check-dinfo-ptr-before-using-v2.patch
# For bz#634652 - [RFE] qemu-img qcow2 'pre-allocation' should not only pre-allocate meta-data, but also data
Patch2034: kvm-qcow2-Add-full-image-preallocation-option.patch
# For bz#671100 - possible migration failure due to erroneous interpretation of subsection
Patch2035: kvm-savevm-fix-corruption-in-vmstate_subsection_load.patch
# For bz#588916 - qemu char fixes for nonblocking writes, virtio-console flow control
Patch2036: kvm-virtio-serial-Disable-flow-control-for-RHEL-5.0-mach.patch
Patch2037: kvm-fix-syntax-error-introduced-by-virtio-serial-Disable.patch
# For bz#619259 - qemu "-cpu [check | enforce ]" should work even when a model name is not specified on the command line
Patch2038: kvm-V3-Bug-619259-qemu-cpu-check-enforce-should-work-eve.patch
# For bz#675229 - Install of cpu-x86_64.conf bombs for an out of tree build..
Patch2039: kvm-Bug-675229-Install-of-cpu-x86_64.conf-bombs-for-an-o.patch
# For bz#602205 - Could not ping guest successfully after changing e1000 MTU
Patch2040: kvm-e1000-multi-buffer-packet-support.patch
# For bz#662386 - tsc clock breaks migration result stability
Patch2041: kvm-make-tsc-stable-over-migration-and-machine-start.patch
# For bz#635527 - KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk
Patch2042: kvm-qemu-kvm-Close-all-block-drivers-on-quit.patch
# For bz#676015 - set_link <tap> off not working with vhost-net
Patch2043: kvm-net-notify-peer-about-link-status-change.patch
# For bz#676015 - set_link <tap> off not working with vhost-net
Patch2044: kvm-vhost-disable-on-tap-link-down.patch
# For bz#616187 - vmware device emulation enabled but not supported
Patch2045: kvm-Add-config-devices.h-again.patch
# For bz#616187 - vmware device emulation enabled but not supported
Patch2046: kvm-Add-CONFIG_VMWARE_VGA-v2.patch
# For bz#616187 - vmware device emulation enabled but not supported
Patch2047: kvm-add-CONFIG_VMMOUSE-option-v2.patch
# For bz#616187 - vmware device emulation enabled but not supported
Patch2048: kvm-add-CONFIG_VMPORT-option-v2.patch
# For bz#677222 - segment fault happens after hot drive add then drive delete
Patch2050: kvm-blockdev-Fix-drive_del-not-to-crash-when-drive-is-no.patch
# For bz#665025 - lost double clicks on slow connections
Patch2051: kvm-USB-HID-does-not-support-Set_Idle.patch
# For bz#665025 - lost double clicks on slow connections
Patch2052: kvm-add-event-queueing-to-USB-HID.patch
# For bz#678338 - e1000 behaving out of spec after increasing MTU
Patch2053: kvm-e1000-clear-EOP-for-multi-buffer-descriptors.patch
# For bz#678338 - e1000 behaving out of spec after increasing MTU
Patch2054: kvm-e1000-verify-we-have-buffers-upfront.patch
# For bz#672441 - Tracetool autogenerate qemu-kvm.stp with wrong qemu-kvm path
Patch2055: kvm-tracetool-Add-optional-argument-to-specify-dtrace-pr.patch
# For bz#672441 - Tracetool autogenerate qemu-kvm.stp with wrong qemu-kvm path
Patch2056: kvm-Specify-probe-prefix-to-make-dtrace-probes-use-qemu-.patch
# For bz#655735 - qemu-kvm (or libvirt?) permission denied errors when exporting readonly IDE disk to guest
Patch2057: kvm-ide-Make-ide_init_drive-return-success.patch
# For bz#655735 - qemu-kvm (or libvirt?) permission denied errors when exporting readonly IDE disk to guest
Patch2058: kvm-ide-Reject-readonly-drives-unless-CD-ROM.patch
# For bz#655735 - qemu-kvm (or libvirt?) permission denied errors when exporting readonly IDE disk to guest
Patch2059: kvm-ide-Reject-invalid-CHS-geometry.patch
# For bz#662701 - Option -enable-kvm should exit when KVM is unavailable
Patch2061: kvm-Move-KVM-and-Xen-global-flags-to-vl.c.patch
# For bz#662701 - Option -enable-kvm should exit when KVM is unavailable
Patch2062: kvm-qemu-kvm-Switch-to-upstream-enable-kvm-semantics.patch
# For bz#607598 - Incorrect & misleading error reporting when failing to open a drive due to block driver whitelist denial
Patch2063: kvm-Fix-error-message-in-drive_init.patch
# For bz#607598 - Incorrect & misleading error reporting when failing to open a drive due to block driver whitelist denial
Patch2064: kvm-block-Use-error-codes-from-lower-levels-for-error-me.patch
# For bz#680058 - can't hotplug second vf successful with message "Too many open files"
Patch2065: kvm-device-assignment-Don-t-skip-closing-unmapped-resour.patch
# For bz#676529 - core dumped when save snapshot to non-exist disk
Patch2066: kvm-Improve-error-handling-in-do_snapshot_blkdev.patch
# For bz#683295 - qemu-kvm: Invalid parameter 'vhostforce'
Patch2067: kvm-net-Add-the-missing-option-declaration-of-vhostforce.patch
# For bz#684076 - Segfault occurred during migration
Patch2068: kvm-vhost-fix-dirty-page-handling.patch
# For bz#688119 - qcow2: qcow2_open doesn't return useful errors
Patch2069: kvm-block-qcow2.c-rename-qcow_-functions-to-qcow2_.patch
# For bz#688119 - qcow2: qcow2_open doesn't return useful errors
Patch2070: kvm-Add-proper-errno-error-return-values-to-qcow2_open.patch
# For bz#688147 - qcow2: Reads fail with backing file smaller than snapshot
Patch2071: kvm-QCOW2-bug-fix-read-base-image-beyond-its-size.patch
# For bz#688146 - qcow2: Some paths fail to handle I/O errors
Patch2072: kvm-qcow2-Fix-error-handling-for-immediate-backing-file-.patch
# For bz#688146 - qcow2: Some paths fail to handle I/O errors
Patch2073: kvm-qcow2-Fix-error-handling-for-reading-compressed-clus.patch
# For bz#688119 - qcow2: qcow2_open doesn't return useful errors
Patch2074: kvm-qerror-Add-QERR_UNKNOWN_BLOCK_FORMAT_FEATURE.patch
# For bz#688119 - qcow2: qcow2_open doesn't return useful errors
Patch2075: kvm-qcow2-Report-error-for-version-2.patch
# For bz#688146 - qcow2: Some paths fail to handle I/O errors
Patch2076: kvm-qcow2-Fix-order-in-L2-table-COW.patch
# For bz#688428 - qemu-kvm -no-kvm segfaults on pci_add
Patch2077: kvm-pci-assign-Catch-missing-KVM-support.patch
# For bz#685147 - guest with assigned nic got kernel panic when send system_reset signal in QEMU monitor
Patch2078: kvm-device-assignment-register-a-reset-function.patch
# For bz#685147 - guest with assigned nic got kernel panic when send system_reset signal in QEMU monitor
Patch2079: kvm-device-assignment-Reset-device-on-system-reset.patch
# For bz#678208 - qemu-kvm hangs when installing guest with -spice option
Patch2080: kvm-Revert-spice-qxl-locking-fix-for-qemu-kvm.patch
# For bz#678208 - qemu-kvm hangs when installing guest with -spice option
Patch2081: kvm-qxl-spice-display-move-pipe-to-ssd.patch
# For bz#678208 - qemu-kvm hangs when installing guest with -spice option
Patch2082: kvm-qxl-implement-get_command-in-vga-mode-without-locks.patch
# For bz#678208 - qemu-kvm hangs when installing guest with -spice option
Patch2083: kvm-qxl-spice-remove-qemu_mutex_-un-lock_iothread-around.patch
# For bz#678208 - qemu-kvm hangs when installing guest with -spice option
Patch2084: kvm-hw-qxl-render-drop-cursor-locks-replace-with-pipe.patch
# For bz#672191 - spicevmc: flow control on the spice agent channel is missing in both directions
Patch2085: kvm-spice-qemu-char.c-add-throttling.patch
# For bz#672191 - spicevmc: flow control on the spice agent channel is missing in both directions
Patch2086: kvm-spice-qemu-char.c-remove-intermediate-buffer.patch
# For bz#672191 - spicevmc: flow control on the spice agent channel is missing in both directions
Patch2087: kvm-spice-qemu-char-Fix-flow-control-in-client-guest-dir.patch
# For bz#688572 - spice-server does not switch back to server mouse mode if guest spice-agent dies.
Patch2088: kvm-chardev-Allow-frontends-to-notify-backends-of-guest-.patch
# For bz#688572 - spice-server does not switch back to server mouse mode if guest spice-agent dies.
Patch2089: kvm-virtio-console-notify-backend-of-guest-open-close.patch
# For bz#688572 - spice-server does not switch back to server mouse mode if guest spice-agent dies.
Patch2090: kvm-spice-chardev-listen-to-frontend-guest-open-close.patch
# For bz#690267 - Backport qemu_get_ram_ptr() performance improvement
Patch2091: kvm-Fix-performance-regression-in-qemu_get_ram_ptr.patch
# For bz#682243 - [KVM] pci hotplug after migration breaks virtio_net.
Patch2092: kvm-virtio-pci-fix-bus-master-work-around-on-load.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch2093: kvm-Use-getaddrinfo-for-migration.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch2094: kvm-net-socket-allow-ipv6-for-net_socket_listen_init-and.patch
# For bz#688058 - Drive serial number gets truncated
Patch2095: kvm-block-Fix-serial-number-assignment.patch
# For bz#678524 - Exec based migration randomly fails, particularly under high load
Patch2096: kvm-add-a-service-to-reap-zombies-use-it-in-SLIRP.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2097: kvm-Don-t-allow-multiwrites-against-a-block-device-witho.patch
# For bz#654682 - drive_del command to let libvirt safely remove block device from guest
Patch2098: kvm-Do-not-delete-BlockDriverState-when-deleting-the-dri.patch
# For bz#690174 - virtio-serial qemu-kvm crash on invalid input in migration
Patch2099: kvm-virtio-serial-don-t-crash-on-invalid-input.patch
# For bz#641833 - Spice CAC support - qemu
Patch2100: kvm-configure-fix-out-of-tree-build-with-enable-spice.patch
# For bz#641833 - Spice CAC support - qemu
Patch2101: kvm-ccid-card-emulated-replace-DEFINE_PROP_ENUM-with-DEF.patch
# For bz#641833 - Spice CAC support - qemu
Patch2102: kvm-Revert-qdev-properties-add-PROP_TYPE_ENUM.patch
# For bz#641833 - Spice CAC support - qemu
Patch2103: kvm-Revert-qdev-add-data-pointer-to-Property.patch
# For bz#641833 - Spice CAC support - qemu
Patch2104: kvm-Revert-qdev-add-print_options-callback.patch
# For bz#641833 - Spice CAC support - qemu
Patch2105: kvm-ccid-v18_upstream-v25-cleanup.patch
# For bz#641833 - Spice CAC support - qemu
Patch2106: kvm-libcacard-vscard_common.h-upstream-v18-v25-diff.patch
# For bz#641833 - Spice CAC support - qemu
Patch2107: kvm-ccid-card-passthru-upstream-v18-upstream-v25-diff.patch
# For bz#641833 - Spice CAC support - qemu
Patch2108: kvm-qemu-thread-add-qemu_mutex-cond_destroy-and-qemu_mut.patch
# For bz#641833 - Spice CAC support - qemu
Patch2109: kvm-adding-qemu-thread.o-to-obj-y.patch
# For bz#641833 - Spice CAC support - qemu
Patch2110: kvm-ccid-card-emulated-v18-v25.patch
# For bz#641833 - Spice CAC support - qemu
Patch2111: kvm-libcacard-v18-upstream-v25.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch2112: kvm-Revert-net-socket-allow-ipv6-for-net_socket_listen_i.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch2113: kvm-Revert-Use-getaddrinfo-for-migration.patch
# For bz#693741 - qemu-img re-base  fail with read-only new backing file
Patch2114: kvm-qemu-img-rebase-Fix-read-only-new-backing-file.patch
# For bz#681777 - floppy I/O error after live migration while floppy in use
Patch2115: kvm-floppy-save-and-restore-DIR-register.patch
# For bz#687900 - qemu host cdrom support not properly updating guests on media changes at physical CD/DVD drives
Patch2116: kvm-block-Do-not-cache-device-size-for-removable-media.patch
# For bz#683877 - RHEL6 guests fail to update cdrom block size on media change
Patch2117: kvm-cdrom-Allow-the-TEST_UNIT_READY-command-after-a-cdro.patch
# For bz#683877 - RHEL6 guests fail to update cdrom block size on media change
Patch2118: kvm-cdrom-Make-disc-change-event-visible-to-guests.patch
# For bz#691704 - Failed to boot up windows guest with huge memory and cpu and vhost=on within 30 mins
Patch2119: kvm-bz-691704-vhost-skip-VGA-memory-regions.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch2120: kvm-ide-atapi-add-support-for-GET-EVENT-STATUS-NOTIFICAT.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch2121: kvm-atapi-Allow-GET_EVENT_STATUS_NOTIFICATION-after-medi.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch2122: kvm-atapi-Move-GET_EVENT_STATUS_NOTIFICATION-command-han.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch2123: kvm-atapi-GESN-Use-structs-for-commonly-used-field-types.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch2124: kvm-atapi-GESN-Standardise-event-response-handling-for-f.patch
# For bz#558256 - rhel6 disk not detected first time in install
Patch2125: kvm-atapi-GESN-implement-media-subcommand.patch
# For bz#694095 - Migration fails when migrate guest from RHEL6.1 host to RHEL6 host with the same libvirt version
Patch2126: kvm-acpi_piix4-Maintain-RHEL6.0-migration.patch
# For bz#698910 - CVE-2011-1750 virtio-blk: heap buffer overflow caused by unaligned requests [rhel-6.1]
Patch2127: kvm-virtio-blk-fail-unaligned-requests.patch
# For bz#699789 - EMBARGOED CVE-2011-1751 acpi_piix4: missing hotplug check during device removal [rhel-6.1]
Patch2128: kvm-Ignore-pci-unplug-requests-for-unpluggable-devices.patch
# For bz#700859 - Fix phys memory client for vhost
Patch2129: kvm-Fix-phys-memory-client-pass-guest-physical-address-n.patch
# For bz#700511 - virtio-serial: Disallow generic ports at id 0
Patch2130: kvm-virtio-serial-Disallow-generic-ports-at-id-0.patch
# For bz#681736 - Guest->Host communication stops for other ports after one port is unplugged
Patch2131: kvm-virtio-serial-Don-t-clear-have_data-pointer-after-un.patch
# For bz#656779 - Core dumped when hot plug/un-plug virtio serial port to the same chardev
Patch2132: kvm-char-Prevent-multiple-devices-opening-same-chardev.patch
# For bz#656779 - Core dumped when hot plug/un-plug virtio serial port to the same chardev
Patch2133: kvm-char-Allow-devices-to-use-a-single-multiplexed-chard.patch
# For bz#656779 - Core dumped when hot plug/un-plug virtio serial port to the same chardev
Patch2134: kvm-char-Detect-chardev-release-by-NULL-handlers-as-well.patch
# For bz#700512 - Keep chardev open for later reuse
Patch2135: kvm-virtio-console-Keep-chardev-open-for-other-users-aft.patch
# For bz#700065 - Switch to upstream solution for cdrom patches
Patch2136: kvm-Revert-cdrom-Make-disc-change-event-visible-to-guest.patch
# For bz#700065 - Switch to upstream solution for cdrom patches
Patch2137: kvm-Revert-cdrom-Allow-the-TEST_UNIT_READY-command-after.patch
# For bz#700065 - Switch to upstream solution for cdrom patches
Patch2138: kvm-atapi-Add-medium-ready-to-medium-not-ready-transitio.patch
# For bz#621482 - [RFE] Be able to get progress from qemu-img
Patch2139: kvm-qemu-img-Initial-progress-printing-support.patch
# For bz#621482 - [RFE] Be able to get progress from qemu-img
Patch2140: kvm-Add-dd-style-SIGUSR1-progress-reporting.patch
# For bz#621482 - [RFE] Be able to get progress from qemu-img
Patch2141: kvm-Remove-obsolete-enabled-variable-from-progress-state.patch
# For bz#621482 - [RFE] Be able to get progress from qemu-img
Patch2142: kvm-qemu-progress.c-printf-isn-t-signal-safe.patch
# For bz#621482 - [RFE] Be able to get progress from qemu-img
Patch2143: kvm-qemu-img.c-Remove-superfluous-parenthesis.patch
# For bz#621482 - [RFE] Be able to get progress from qemu-img
Patch2144: kvm-Add-documentation-for-qemu_progress_-init-print.patch
# For bz#655719 - no error pops when change cd to non-exist file
Patch2145: kvm-Add-qerror-message-if-the-change-target-filename-can.patch
# For bz#684127 - e1000:Execute multiple netperf clients caused system call interrupted
Patch2146: kvm-e1000-check-buffer-availability.patch
# For bz#680378 - no error message when loading zero size internal snapshot
Patch2147: kvm-Add-error-message-for-loading-snapshot-without-VM-st.patch
# For bz#710046 - qemu-kvm prints warning "Using CPU model [...]" (with patch)
Patch2148: kvm-BZ710046-qemu-kvm-prints-warning-Using-CPU-model.patch
# For bz#701775 - KVM: stdio is flooded
Patch2149: kvm-ide-Factor-ide_dma_set_inactive-out.patch
# For bz#701775 - KVM: stdio is flooded
Patch2150: kvm-ide-Set-bus-master-inactive-on-error.patch
# For bz#701775 - KVM: stdio is flooded
Patch2151: kvm-ide-cleanup-warnings.patch
# For bz#701442 - vhost-net not enabled on hotplug
Patch2152: kvm-virtio-correctly-initialize-vm_running.patch
# For bz#710349 - Backport serial number support for virtio-blk devices
Patch2153: kvm-Add-virtio-disk-identification-support.patch
# For bz#693645 - RFE: add spice option to enable/disable copy paste
Patch2154: kvm-spice-add-option-for-disabling-copy-paste-support-rh.patch
# For bz#707094 - qemu-kvm: OOB memory access caused by negative vq notifies [rhel-6.2]
Patch2155: kvm-virtio-guard-against-negative-vq-notifies.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2156: kvm-blockdev-Belatedly-remove-MAX_DRIVES.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2157: kvm-blockdev-Hide-QEMUMachine-from-drive_init.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2158: kvm-qdev-Move-declaration-of-qdev_init_bdrv-into-qdev.h.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2159: kvm-blockdev-Collect-block-device-code-in-new-blockdev.c.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2160: kvm-Fix-regression-for-drive-file.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2161: kvm-block-Move-error-actions-from-DriveInfo-to-BlockDriv.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2162: kvm-blockdev-Fix-error-message-for-invalid-drive-CHS.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2163: kvm-blockdev-Make-drive_init-use-error_report.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2164: kvm-blockdev-Put-BlockInterfaceType-names-and-max_devs-i.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2165: kvm-blockdev-Fix-regression-in-drive-if-scsi-index-N.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2166: kvm-blockdev-Make-drive_add-take-explicit-type-index-par.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2167: kvm-blockdev-Factor-drive_index_to_-bus-unit-_id-out-of-.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2168: kvm-blockdev-New-drive_get_by_index.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2169: kvm-blockdev-Reject-multiple-definitions-for-the-same-dr.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2170: kvm-blockdev-Replace-drive_add-s-fmt-.-by-optstr-paramet.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2171: kvm-blockdev-Fix-drive_add-for-drives-without-media.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2172: kvm-blockdev-Plug-memory-leak-in-drive_uninit.patch
# For bz#627585 - Improve error messages for bad options in -drive and -device
Patch2173: kvm-blockdev-Plug-memory-leak-in-drive_init-error-paths.patch
# For bz#699635 - [REG][6.1] After executing virsh dump with --live option and the completion, the subsequent virsh dump command to the same domain behaves abnormally
Patch2174: kvm-vhost-fix-double-free-on-device-stop.patch
# For bz#644919 - RFE: QMP command to trigger an NMI in the guest
Patch2175: kvm-QMP-QError-New-QERR_UNSUPPORTED.patch
# For bz#644919 - RFE: QMP command to trigger an NMI in the guest
Patch2176: kvm-QMP-add-inject-nmi-qmp-command.patch
# For bz#644919 - RFE: QMP command to trigger an NMI in the guest
Patch2177: kvm-HMP-Use-QMP-inject-nmi-implementation.patch
# For bz#570830 - The 'cluster_size' shows wrong size to zero when creating a qcow2 without specify the option
Patch2178: kvm-qemu-img-create-Fix-displayed-default-cluster-size.patch
# For bz#715141 - Wrong Ethertype for RARP
Patch2179: kvm-Fix-the-RARP-protocol-ID.patch
# For bz#599306 - Some strange behaviors on key's appearance viewed by using vnc
Patch2180: kvm-vnc-fix-numlock-capslock-tracking.patch
# For bz#684949 - [RFE] Ability to display VM BIOS messages on boot
Patch2181: kvm-Add-an-isa-device-for-SGA.patch
# For bz#716906 - add 6.2 machine type
Patch2182: kvm-pc-add-rhel-6.2-pc-and-make-it-the-default.patch
# For bz#583922 - Guests in same vlan could not ping successfully using rtl8139 nic
Patch2183: kvm-rtl8139-cleanup-FCS-calculation.patch
# For bz#583922 - Guests in same vlan could not ping successfully using rtl8139 nic
Patch2184: kvm-rtl8139-add-vlan-tag-extraction.patch
# For bz#583922 - Guests in same vlan could not ping successfully using rtl8139 nic
Patch2185: kvm-rtl8139-add-vlan-tag-insertion.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2186: kvm-usb-serial-Fail-instead-of-crash-when-chardev-is-mis.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2187: kvm-Add-exit-notifiers.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2188: kvm-Return-usb-device-to-host-on-usb_del-command.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2189: kvm-Return-usb-device-to-host-on-exit.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2190: kvm-usb-linux-Store-devpath-into-USBHostDevice-when-usb_.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2191: kvm-usb-linux-introduce-a-usb_linux_get_configuration-fu.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2192: kvm-usb-linux-Get-the-active-configuration-from-sysfs-ra.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2193: kvm-usb-data-structs-and-helpers-for-usb-descriptors.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2194: kvm-usb-hid-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2195: kvm-usb-serial-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2196: kvm-usb-storage-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2197: kvm-scsi-disk-fix-build-disable-cdrom-emulation.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2198: kvm-enable-usb-storage-scsi-bus-scsi-disk.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2199: kvm-usb-wacom-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2200: kvm-usb-bluetooth-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2201: kvm-usb-hub-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2202: kvm-usb-descriptors-add-settable-strings.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2203: kvm-usb-storage-serial-number-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2204: kvm-usb-network-use-new-descriptor-infrastructure.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2205: kvm-usb-move-USB_REQ_SET_ADDRESS-handling-to-common-code.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2206: kvm-usb-move-USB_REQ_-GET-SET-_CONFIGURATION-handling-to.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2207: kvm-usb-move-remote-wakeup-handling-to-common-code.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2208: kvm-usb-create-USBPortOps-move-attach-there.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2209: kvm-usb-rework-attach-detach-workflow.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2210: kvm-usb-add-usb_wakeup-wakeup-callback-to-port-ops.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2211: kvm-usb-uhci-remote-wakeup-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2212: kvm-usb-hub-remote-wakeup-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2213: kvm-usb-hid-remote-wakeup-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2214: kvm-usb-hid-change-serial-number-to-42.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2215: kvm-usb-add-speed-mask-to-ports.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2216: kvm-usb-add-attach-callback.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2217: kvm-usb-add-usb_desc_attach.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2218: kvm-usb-add-device-qualifier-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2219: kvm-usb-storage-high-speed-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2220: kvm-usb-storage-fix-status-reporting.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2221: kvm-usb-storage-handle-long-responses.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2222: kvm-usb-mass-storage-fix.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2223: kvm-usb-keep-track-of-physical-port-address.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2224: kvm-usb-add-port-property.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2225: kvm-usb-rewrite-fw-path-fix-numbering.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2226: kvm-usb-zap-pdev-from-usbport.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2227: kvm-USB-keyboard-emulation-key-mapping-error.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2228: kvm-usb-hid-modifiers-should-generate-an-event.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2229: kvm-usb-keyboard-add-event-event-queue.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2230: kvm-usb-hid-move-head-n-to-common-struct.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2231: kvm-usb-core-add-migration-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2232: kvm-usb-hub-add-migration-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2233: kvm-usb-hid-add-migration-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2234: kvm-usb-bus-use-snprintf.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2235: kvm-Add-bootindex-handling-into-usb-storage-device.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2236: kvm-usb-trivial-spelling-fixes.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2237: kvm-usb-initialise-data-element-in-Linux-USB_DISCONNECT-.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2238: kvm-usb-linux-introduce-a-usb_linux_alt_setting-function.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2239: kvm-usb-linux-Get-the-alt.-setting-from-sysfs-rather-the.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2240: kvm-usb-linux-s-dprintf-DPRINTF-to-reduce-conflicts.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2241: kvm-usb-linux-Add-support-for-buffering-iso-usb-packets.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2242: kvm-usb-linux-Refuse-packets-for-endpoints-which-are-not.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2243: kvm-usb-linux-Refuse-iso-packets-when-max-packet-size-is.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2244: kvm-usb-linux-We-only-need-to-keep-track-of-15-endpoints.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2245: kvm-usb-linux-Add-support-for-buffering-iso-out-usb-pack.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2246: kvm-usb-control-buffer-fixes.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2247: kvm-uhci-switch-to-QTAILQ-cherry-picked-from-commit-ddf6.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2248: kvm-uhci-keep-uhci-state-pointer-in-async-packet-struct.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2249: kvm-ohci-get-ohci-state-via-container_of.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2250: kvm-musb-get-musb-state-via-container_of-cherry-picked-f.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2251: kvm-usb-move-complete-callback-to-port-ops-cherry-picked.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2252: kvm-usb-linux-Add-missing-break-statement.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2253: kvm-usb-Add-Interface-Association-Descriptor-descriptor-.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2254: kvm-usb-update-config-descriptors-to-identify-number-of-.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2255: kvm-usb-remove-fallback-to-bNumInterfaces-if-no-.nif.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2256: kvm-usb-add-support-for-grouped-interfaces-and-the-Inter.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2257: kvm-Bug-757654-UHCI-fails-to-signal-stall-response-patch.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2258: kvm-usb-Pass-the-packet-to-the-device-s-handle_control-c.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2259: kvm-usb-linux-use-usb_generic_handle_packet.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2260: kvm-usb-linux-fix-device-path-aka-physical-port-handling.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2261: kvm-usb-linux-add-hostport-property.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2262: kvm-usb-linux-track-aurbs-in-list.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2263: kvm-usb-linux-walk-async-urb-list-in-cancel.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2264: kvm-usb-linux-split-large-xfers.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2265: kvm-usb-linux-fix-max_packet_size-for-highspeed.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2266: kvm-usb-storage-don-t-call-usb_packet_complete-twice.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2267: kvm-usb-add-usb_handle_packet.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2268: kvm-usb-keep-track-of-packet-owner.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2269: kvm-usb-move-cancel-callback-to-USBDeviceInfo.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2270: kvm-usb-add-ehci-adapter.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2271: kvm-usb-linux-catch-ENODEV-in-more-places.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2272: kvm-usb-ehci-trace-mmio-and-usbsts-usb-ehci-trace-mmio-a.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2273: kvm-usb-ehci-trace-state-machine-changes.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2274: kvm-usb-ehci-trace-port-state.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2275: kvm-usb-ehci-improve-mmio-tracing.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2276: kvm-ehci-trace-workaround.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2277: kvm-usb-ehci-trace-buffer-copy.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2278: kvm-usb-ehci-add-queue-data-struct.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2279: kvm-usb-ehci-multiqueue-support.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2280: kvm-usb-ehci-fix-offset-writeback-in-ehci_buffer_rw.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2281: kvm-usb-ehci-fix-error-handling.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2282: kvm-ehci-fix-a-number-of-unused-but-set-variable-warning.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2283: kvm-usb-cancel-async-packets-on-unplug.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2284: kvm-usb-ehci-drop-EXECUTING-checks.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2285: kvm-Fix-USB-mouse-Set_Protocol-behavior.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2286: kvm-The-USB-tablet-should-not-claim-boot-protocol-suppor.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2287: kvm-usb-ehci-itd-handling-fixes.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2288: kvm-usb-ehci-split-trace-calls-to-handle-arg-count-limit.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2289: kvm-usb-linux-Get-speed-from-sysfs-rather-then-from-the-.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2290: kvm-usb-linux-Teach-about-super-speed.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2291: kvm-usb-linux-Don-t-do-perror-when-errno-is-not-set.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2292: kvm-usb-linux-Ensure-devep-0.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2293: kvm-usb-linux-Don-t-try-to-open-the-same-device-twice.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2294: kvm-usb-linux-only-cleanup-in-host_close-when-host_open-.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2295: kvm-usb-linux-Enlarge-buffer-for-descriptors-to-8192-byt.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2296: kvm-usb-bus-Add-knowledge-of-USB_SPEED_SUPER-to-usb_spee.patch
# For bz#561414 - Writes to virtual usb-storage produce I/O errors
# For bz#632299 - higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5
# For bz#645351 - Add support for USB 2.0 (EHCI) to QEMU
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2297: kvm-usb-bus-Don-t-detach-non-attached-devices-on-device-.patch
# For bz#711213 - QEMU should use pass preadv/pwritev a single vector when using cache=none and NFS
Patch2298: kvm-raw-posix-Linearize-direct-I-O-on-Linux-NFS.patch
# For bz#720535 - (virtio serial) Guest aborted when transferring data from guest to host
Patch2299: kvm-virtio-console-Prevent-abort-s-in-case-of-host-chard.patch
# For bz#696102 - [Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part
Patch2300: kvm-Add-qemu_ram_alloc_from_ptr-function.patch
# For bz#696102 - [Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part
Patch2301: kvm-exec-remove-code-duplication-in-qemu_ram_alloc-and-q.patch
# For bz#696102 - [Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part
Patch2302: kvm-Move-extern-of-mem_prealloc-to-cpu-all.h.patch
# For bz#696102 - [Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part
Patch2303: kvm-Add-qemu_ram_remap.patch
# For bz#696102 - [Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part
Patch2304: kvm-s390-Detect-invalid-invocations-of-qemu_ram_free-rem.patch
# For bz#696102 - [Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part
Patch2305: kvm-MCE-unpoison-memory-address-across-reboot.patch
# For bz#698537 - ide: core dump when stop/cont guest
Patch2306: kvm-ide-Split-error-status-from-status-register.patch
# For bz#698537 - ide: core dump when stop/cont guest
Patch2307: kvm-ide-Fix-ide_drive_pio_state_needed.patch
# For bz#698537 - ide: core dump when stop/cont guest
Patch2308: kvm-ide-Add-forgotten-VMSTATE_END_OF_LIST-in-subsection.patch
# For bz#698537 - ide: core dump when stop/cont guest
Patch2309: kvm-ide-Clear-error_status-after-restarting-flush.patch
# For bz#713743 - qemu-img: add cache command line option
Patch2310: kvm-qemu-img-Add-cache-command-line-option.patch
# For bz#709397 - virtio-serial unthrottling needs to use a bottomhalf to avoid recursion
Patch2311: kvm-virtio-serial-bus-use-bh-for-unthrottling.patch
# For bz#723864 - usb: compile out the crap
Patch2312: kvm-usb-bluetooth-compile-out.patch
# For bz#725054 - RHEL6.2: Clarify support statement in KVM help
Patch2313: kvm-clarify-support-statement-in-KVM-help.patch
# For bz#676982 - RFE: no qmp command for live snapshot
Patch2314: kvm-Change-snapshot_blkdev-hmp-to-use-correct-argument-t.patch
# For bz#676982 - RFE: no qmp command for live snapshot
Patch2315: kvm-QMP-add-snapshot-blkdev-sync-command.patch
# For bz#722728 - Update qemu-img convert/re-base man page
Patch2316: kvm-Add-missing-documentation-for-qemu-img-p.patch
# For bz#720237 - usb migration compatibility
Patch2317: kvm-usb-hid-RHEL-6.1-migration-compatibility.patch
# For bz#707130 - ACPI description of serial and parallel ports incorrect with -chardev/-device
Patch2318: kvm-report-serial-devices-created-with-device-in-the-PII.patch
# For bz#720972 - Unable to attach PCI device on a booted virt guest
Patch2319: kvm-device-assignment-handle-device-with-incorrect-PCIe-.patch
# For bz#712046 - Qemu allocates an existed macaddress to hotpluged nic
Patch2320: kvm-net-Consistently-use-qemu_macaddr_default_if_unset.patch
# For bz#725965 - spice client mouse doesn't work after migration
Patch2321: kvm-virtio-serial-bus-replay-guest_open-on-migration.patch
# For bz#727580 - bit property doesn't print correctly
Patch2322: kvm-qdev-Fix-printout-of-bit-device-properties-with-bit-.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2323: kvm-Revert-hw-qxl-render-drop-cursor-locks-replace-with-.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2324: kvm-Revert-qxl-spice-remove-qemu_mutex_-un-lock_iothread.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2325: kvm-Revert-qxl-implement-get_command-in-vga-mode-without.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2326: kvm-Revert-qxl-spice-display-move-pipe-to-ssd.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2327: kvm-spice-don-t-create-updates-in-spice-server-context.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2328: kvm-spice-don-t-call-displaystate-callbacks-from-spice-s.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2329: kvm-spice-drop-obsolete-iothread-locking.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2330: kvm-Make-spice-dummy-functions-inline-to-fix-calls-not-c.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2331: kvm-add-qdev_find_by_id.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2332: kvm-add-qxl_screendump-monitor-command.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2333: kvm-usb-linux-make-iso-urb-count-contigurable.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2334: kvm-usb-linux-track-inflight-iso-urb-count.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2335: kvm-ehci-add-freq-maxframes-properties.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2336: kvm-usb-bus-Don-t-allow-attaching-a-device-to-a-bus-with.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2337: kvm-usb-Proper-error-propagation-for-usb_device_attach-e.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2338: kvm-usb-Add-a-speedmask-to-devices.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2339: kvm-usb-linux-allow-compatible-high-speed-devices-to-con.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2340: kvm-usb-ignore-USB_DT_DEBUG.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2341: kvm-usb-Add-a-usb_fill_port-helper-function.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2342: kvm-usb-Move-initial-call-of-usb_port_location-to-usb_fi.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2343: kvm-usb-Add-a-register_companion-USB-bus-op.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2344: kvm-usb-Make-port-wakeup-and-complete-ops-take-a-USBPort.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2345: kvm-usb-Replace-device_destroy-bus-op-with-a-child_detac.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2346: kvm-usb-ehci-drop-unused-num-ports-state-member.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2347: kvm-usb-ehci-Connect-Status-bit-is-read-only-don-t-allow.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2348: kvm-usb-ehci-cleanup-port-reset-handling.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2349: kvm-usb-assert-on-calling-usb_attach-port-NULL-on-a-port.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2350: kvm-usb-ehci-Fix-handling-of-PED-and-PEDC-port-status-bi.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2351: kvm-usb-ehci-Add-support-for-registering-companion-contr.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2352: kvm-usb-uhci-Add-support-for-being-a-companion-controlle.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2353: kvm-pci-add-ich9-usb-controller-ids.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2354: kvm-uhci-add-ich9-controllers.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2355: kvm-ehci-fix-port-count.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2356: kvm-ehci-add-ich9-controller.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2357: kvm-usb-documentation-update.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2358: kvm-usb-fixup-bluetooth-descriptors.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2359: kvm-usb-hub-remove-unused-descriptor-arrays.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2360: kvm-usb-update-documentation.patch
# For bz#723858 - usb: add companion controller support
# For bz#723863 - usb: fixes various issues.
Patch2361: kvm-usb_register_port-do-not-set-port-opaque-and-port-in.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2362: kvm-qxl-fix-cmdlog-for-vga.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2363: kvm-qxl-interface_get_command-fix-reported-mode.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2364: kvm-spice-add-worker-wrapper-functions.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2365: kvm-spice-add-qemu_spice_display_init_common.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2366: kvm-spice-qxl-move-worker-wrappers.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2367: kvm-qxl-fix-surface-tracking-locking.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2368: kvm-qxl-add-io_port_to_string.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2369: kvm-qxl-error-handling-fixes-and-cleanups.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2370: kvm-qxl-make-qxl_guest_bug-take-variable-arguments.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2371: kvm-qxl-put-QXL_IO_UPDATE_IRQ-into-vgamode-whitelist.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2372: kvm-qxl-allow-QXL_IO_LOG-also-in-vga.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2373: kvm-qxl-only-disallow-specific-io-s-in-vga-mode.patch
# For bz#700134 - [qemu-kvm] - qxl runs i/o requests synchronously
Patch2374: kvm-qxl-async-io-support-using-new-spice-api.patch
# For bz#706711 - qemu-kvm process quits when windows guest doing S3 w/ qxl device
Patch2375: kvm-qxl-add-QXL_IO_FLUSH_-SURFACES-RELEASE-for-guest-S3-.patch
# For bz#706711 - qemu-kvm process quits when windows guest doing S3 w/ qxl device
Patch2376: kvm-qxl-Remove-support-for-the-unused-unstable-device-ID.patch
# For bz#706711 - qemu-kvm process quits when windows guest doing S3 w/ qxl device
Patch2377: kvm-qxl-bump-pci-rev.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2378: kvm-move-balloon-handling-to-balloon.c.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2379: kvm-balloon-Make-functions-local-vars-static.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2380: kvm-balloon-Add-braces-around-if-statements.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2381: kvm-balloon-Simplify-code-flow.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2382: kvm-virtio-balloon-Separate-status-handling-into-separat.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2383: kvm-balloon-Separate-out-stat-and-balloon-handling.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2384: kvm-balloon-Fix-header-comment-add-Copyright.patch
# For bz#694378 - Core dump occurs when ballooning memory to 0
Patch2385: kvm-virtio-balloon-Fix-header-comment-add-Copyright.patch
# For bz#725625 - Hot unplug one virtio balloon device cause another balloon device unavailable
Patch2386: kvm-balloon-Don-t-allow-multiple-balloon-handler-registr.patch
# For bz#725625 - Hot unplug one virtio balloon device cause another balloon device unavailable
Patch2387: kvm-virtio-balloon-Check-if-balloon-registration-failed.patch
# For bz#694373 - ballooning value reset to original value after setting a negative number
Patch2388: kvm-balloon-Reject-negative-balloon-values.patch
# For bz#726014 - Fix memleak on exit in virtio-balloon
Patch2389: kvm-virtio-balloon-Add-exit-handler-fix-memleaks.patch
# For bz#726023 - Migration after hot-unplug virtio-balloon will not succeed
Patch2390: kvm-virtio-balloon-Unregister-savevm-section-on-device-u.patch
# For bz#726015 - Fix memleak on exit in virtio-blk
Patch2391: kvm-virtio-blk-Fix-memleak-on-exit.patch
# For bz#726020 - Fix memleaks in all virtio devices
Patch2392: kvm-virtio-net-don-t-use-vdev-after-virtio_cleanup.patch
# For bz#726020 - Fix memleaks in all virtio devices
Patch2393: kvm-virtio-Plug-memleak-by-freeing-vdev.patch
# For bz#728905 - qemu-img: use larger output buffer for cache option "none"
Patch2394: kvm-qemu-img-Use-qemu_blockalign.patch
# For bz#623907 - device_add rejects valid netdev when NIC with same ID exists
Patch2395: kvm-Fix-automatically-assigned-network-names-for-netdev.patch
# For bz#623907 - device_add rejects valid netdev when NIC with same ID exists
Patch2396: kvm-Fix-netdev-name-lookup-in-device-device_add-netdev_d.patch
# For bz#728464 - QEMU does not honour '-no-shutdown' flag after the first shutdown attempt
Patch2397: kvm-do-not-reset-no_shutdown-after-we-shutdown-the-vm.patch
# For bz#710943 - event index support in virtio and vhost-net
Patch2398: kvm-virtio-event-index-support.patch
# For bz#710943 - event index support in virtio and vhost-net
Patch2399: kvm-pc-rhel-6.1-and-back-compat-event-idx-support.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2400: kvm-qdev-implement-qdev_prop_set_bit.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2401: kvm-pci-insert-assert-that-auto-assigned-address-functio.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2402: kvm-pci-introduce-multifunction-property.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2403: kvm-pci_bridge-make-pci-bridge-aware-of-pci-multi-functi.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2404: kvm-pci-set-multifunction-property-for-normal-device.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2405: kvm-pci-don-t-overwrite-multi-functio-bit-in-pci-header-.patch
# For bz#729104 - qemu-kvm: pci needs multifunction property
Patch2406: kvm-pci-set-PCI-multi-function-bit-appropriately.patch
# For bz#705070 - QMP: screendump command does not allow specification of monitor to capture
Patch2407: kvm-Add-user_print-handler-to-qxl_screendump-monitor-com.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2408: kvm-docs-Add-QED-image-format-specification.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2409: kvm-qed-Add-QEMU-Enhanced-Disk-image-format.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2410: kvm-qed-Table-L2-cache-and-cluster-functions.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2411: kvm-qed-Read-write-support.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2412: kvm-qed-Consistency-check-support.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2413: kvm-docs-Fix-missing-carets-in-QED-specification.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2414: kvm-qed-Refuse-to-create-images-on-block-devices.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2415: kvm-qed-Images-with-backing-file-do-not-require-QED_F_NE.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2416: kvm-docs-Describe-zero-data-clusters-in-QED-specificatio.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2417: kvm-qed-Add-support-for-zero-clusters.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2418: kvm-qed-Fix-consistency-check-on-32-bit-hosts.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2419: kvm-block-add-BDRV_O_INCOMING-migration-consistency-hint.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2420: kvm-qed-honor-BDRV_O_INCOMING-for-live-migration-support.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2422: kvm-qemu-tool-Stub-out-qemu-timer-functions.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2423: kvm-qed-Periodically-flush-and-clear-need-check-bit.patch
# For bz#633380 - [6.2 FEAT] Include QED image format for KVM guests
Patch2424: kvm-qed-support-for-growing-images.patch
# For bz#720979 - do not use next  as a variable name in qemu-kvm systemtap tapset
Patch2425: kvm-usb-ehci-trace-rename-next-to-nxt.patch
# For bz#729869 - qxl: primary surface not saved on migration
Patch2426: kvm-qxl-make-sure-primary-surface-is-saved-on-migration.patch
# For bz#682227 - qemu-kvm doesn't exit when binding to specified port fails
Patch2427: kvm-spice-catch-spice-server-initialization-failures.patch
# For bz#729572 - qcow2: Loading internal snapshot can corrupt image
Patch2428: kvm-qcow2-Fix-L1-table-size-after-bdrv_snapshot_goto.patch
# For bz#714773 - qemu missing marker for qemu.kvm.qemu_vmalloc
Patch2430: kvm-Add-missing-trace-call-to-oslib-posix.c-qemu_vmalloc.patch
# For bz#715582 - qemu-kvm doesn't report error when supplied negative spice port value
# For bz#717958 - qemu-kvm start vnc even though -spice ... is supplied
Patch2431: kvm-spice-add-sanity-check-for-spice-ports.patch
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2432: kvm-block-add-discard-support.patch
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2433: kvm-qemu-option-New-qemu_opts_reset.patch
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2434: kvm-error-New-qemu_opts_loc_restore.patch
# For bz#711354 - Fix and enable enough of SCSI to make usb-storage work
Patch2435: kvm-scsi-Rebase-to-upstream-v0.15.0-rc2.patch
# For bz#728984 - Target qemu process - assertion failed during migration
Patch2436: kvm-qxl-upon-reset-if-spice-worker-is-stopped-the-comman.patch
# For bz#728984 - Target qemu process - assertion failed during migration
Patch2437: kvm-qxl-allowing-the-command-rings-to-be-not-empty-when-.patch
# For bz#719818 - KVM qemu support for Supervisor Mode Execution Protection (SMEP)
Patch2438: kvm-bz719818-KVM-qemu-support-for-SMEP.patch
# For bz#723870 - tag devices without migration support
Patch2439: kvm-vmstate-add-no_migrate-flag-to-VMStateDescription.patch
# For bz#723870 - tag devices without migration support
Patch2440: kvm-ehci-doesn-t-support-migration.patch
# For bz#723870 - tag devices without migration support
Patch2441: kvm-usb-storage-first-migration-support-bits.patch
# For bz#713593 - EMBARGOED CVE-2011-2212 virtqueue: too-large indirect descriptor buffer overflow [rhel-6.2]
Patch2442: kvm-virtio-prevent-indirect-descriptor-buffer-overflow.patch
# For bz#658467 - kvm clock breaks migration result stability -  for unit test propose
Patch2443: kvm-x86-Introduce-kvmclock-device-to-save-restore-it.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2444: kvm-use-kernel-provided-para_features-instead-of-statica.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2445: kvm-add-kvmclock-to-its-second-bit-v2.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2446: kvm-create-kvmclock-when-one-of-the-flags-are-presen.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2447: kvm-x86-Allow-multiple-cpu-feature-matches-of-lookup_fea.patch
# For bz#695285 - guest quit with "Guest moved used index from 256 to 915" error when save_vm
Patch2448: kvm-vhost-net-cleanup-host-notifiers-at-last-step.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2449: kvm-block-include-flush-requests-in-info-blockstats.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2450: kvm-block-explicit-I-O-accounting.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2451: kvm-block-latency-accounting.patch
# For bz#718664 - Migration from host RHEL6.1+ to host RHEL6.0.z failed with floppy
Patch2452: kvm-revert-floppy-save-and-restore-DIR-register.patch
# For bz#734860 - qemu-kvm: segfault when missing host parameter for socket chardev
Patch2453: kvm-qemu-sockets-avoid-strlen-of-NULL-pointer.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2454: kvm-Revert-block-latency-accounting.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2455: kvm-Revert-block-explicit-I-O-accounting.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2456: kvm-Revert-block-include-flush-requests-in-info-blocksta.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2457: kvm-Revert-x86-Allow-multiple-cpu-feature-matches-of-loo.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2458: kvm-Revert-kvm-create-kvmclock-when-one-of-the-flags-are.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2459: kvm-Revert-add-kvmclock-to-its-second-bit-v2.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2460: kvm-Revert-use-kernel-provided-para_features-instead-of-.patch
# For bz#658467 - kvm clock breaks migration result stability -  for unit test propose
Patch2461: kvm-Revert-kvm-x86-Introduce-kvmclock-device-to-save-res.patch
# For bz#658467 - kvm clock breaks migration result stability -  for unit test propose
Patch2462: kvm-x86-Introduce-kvmclock-device-to-save-restore-it-fixed.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2463: kvm-use-kernel-provided-para_features-instead-of-statica-take2.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2464: kvm-add-kvmclock-to-its-second-bit-v2-take2.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2465: kvm-create-kvmclock-when-one-of-the-flags-are-present-take2.patch
# For bz#624983 - QEMU should support the newer set of MSRs for kvmclock
Patch2466: kvm-x86-Allow-multiple-cpu-feature-matches-of-lookup_fea-take2.patch
# For bz#730587 - qemu-img convert takes 25m for specific images when using cache=none
Patch2467: kvm-qemu-img-Require-larger-zero-areas-for-sparse-handli.patch
# For bz#732949 - Guest screen becomes abnormal after migration with spice
Patch2468: kvm-qxl-send-interrupt-after-migration-in-case-ram-int_p.patch
# For bz#732949 - Guest screen becomes abnormal after migration with spice
Patch2469: kvm-qxl-s-qxl_set_irq-qxl_update_irq.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2470: kvm-block-include-flush-requests-in-info-blockstats-v2.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2471: kvm-block-explicit-I-O-accounting-v2.patch
# For bz#715017 - Report disk latency (read and write) for each storage device
Patch2472: kvm-block-latency-accounting-v2.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2473: kvm-Add-flag-to-indicate-external-users-to-block-device.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2474: kvm-block-enable-in_use-flag.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2475: kvm-block-add-drive-copy-on-read-on-off.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2476: kvm-qed-replace-is_write-with-flags-field.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2477: kvm-qed-extract-qed_start_allocating_write.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2478: kvm-qed-make-qed_aio_write_alloc-reusable.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2479: kvm-qed-add-support-for-copy-on-read.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2480: kvm-qed-avoid-deadlock-on-emulated-synchronous-I-O.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2481: kvm-block-add-bdrv_aio_copy_backing.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2482: kvm-qmp-add-block_stream-command.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2483: kvm-qmp-add-block_job_cancel-command.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2484: kvm-qmp-add-query-block-jobs-command.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2485: kvm-qmp-add-block_job_set_speed-command.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2486: kvm-block-add-drive-stream-on-off.patch
# For bz#633370 - [6.1 FEAT] Enhance QED image format to support streaming from remote systems
Patch2487: kvm-qed-intelligent-streaming-implementation.patch
Patch2488: kvm-CVE-2011-2527-os-posix-set-groups-properly-for-runas.patch
# For bz#697441 - JSON corruption when closing SPICE window
Patch2489: kvm-spice-workaround-a-spice-server-bug.patch
# For bz#736975 - Qemu-kvm fails to unregister virtio-balloon-pci device when unplugging
Patch2490: kvm-balloon-Disassociate-handlers-from-balloon-device-on.patch
# For bz#736975 - Qemu-kvm fails to unregister virtio-balloon-pci device when unplugging
Patch2491: kvm-virtio-balloon-Disassociate-from-the-balloon-handler.patch
# For bz#738019 - Memleak in virtio-serial code: VirtIOSerialBus not freed
Patch2492: kvm-virtio-serial-Plug-memory-leak-on-qdev-exit.patch
# For bz#733993 - migration target can crash (assert(d->ssd.running))
Patch2493: kvm-spice-set-qxl-ssd.running-true-before-telling-spice-.patch
# For bz#729621 - ASSERT worker->running failed on source qemu during migration with Spice session
Patch2494: kvm-qemu-kvm-vm_stop-pause-threads-before-calling-other-.patch
# For bz#738487 - Fix termination by signal with -no-shutdown
Patch2495: kvm-Fix-termination-by-signal-with-no-shutdown.patch
# For bz#738555 - Stop exposing -enable-nested
Patch2496: kvm-qemu-option-Remove-enable-nesting-from-help-text.patch
# For bz#728120 - print error on usb speed mismatch between device and bus/port
Patch2497: kvm-usb-bus-Don-t-allow-speed-mismatch-while-attaching-d.patch
# For bz#734995 - Core dump when hotplug three usb-hub into the same port under both uhci and ehci
Patch2498: kvm-usb-vmstate-add-parent-dev-path.patch
# For bz#734995 - Core dump when hotplug three usb-hub into the same port under both uhci and ehci
Patch2499: kvm-usb-claim-port-at-device-initialization-time.patch
# For bz#723870 - tag devices without migration support
Patch2500: kvm-usb-host-tag-as-unmigratable.patch
# For bz#733010 - core dump when issue fdisk -l in guest which has two usb-storage attached
Patch2501: kvm-usb-storage-fix-NULL-pointer-dereference.patch
# For bz#735716 - QEMU should report the PID of the process that sent it signals for troubleshooting purposes
Patch2502: kvm-register-signal-handler-after-initializing-SDL.patch
# For bz#735716 - QEMU should report the PID of the process that sent it signals for troubleshooting purposes
Patch2503: kvm-report-that-QEMU-process-was-killed-by-a-signal.patch
# For bz#735716 - QEMU should report the PID of the process that sent it signals for troubleshooting purposes
Patch2504: kvm-Tidy-up-message-printed-when-we-exit-on-a-signal.patch
# For bz#729969 - Make screendump command available in QMP
Patch2505: kvm-Monitor-Convert-do_screen_dump-to-QObject.patch
# For bz#734995 - Core dump when hotplug three usb-hub into the same port under both uhci and ehci
Patch2506: kvm-usb-hub-need-to-check-dev-attached.patch
# For bz#734995 - Core dump when hotplug three usb-hub into the same port under both uhci and ehci
Patch2507: kvm-usb-fix-port-reset.patch
# For bz#678731 - Update qemu-kvm -device pci-assign,?  properties
Patch2508: kvm-qdev-print-bus-properties-too.patch
# For bz#739480 - qemu-kvm core dumps when migration with reboot
Patch2509: kvm-ide-link-BMDMA-and-IDEState-at-device-creation.patch
# For bz#737921 - No Spice password is set on target host after migration
Patch2510: kvm-spice-turn-client_migrate_info-to-async.patch
# For bz#737921 - No Spice password is set on target host after migration
Patch2511: kvm-spice-support-the-new-migration-interface-spice-0.8..patch
# For bz#678729 - Hotplug VF/PF with invalid addr value leading to qemu-kvm process quit with core dump
Patch2512: kvm-pci-devfn-check-device-slot-number-in-range.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2513: kvm-usb-linux-add-get_endp.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2514: kvm-usb-host-reapurb-error-report-fix.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2515: kvm-usb-host-fix-halted-endpoints.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2516: kvm-usb-host-limit-open-retries.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2517: kvm-usb-host-fix-configuration-tracking.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2518: kvm-usb-host-claim-port.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2519: kvm-usb-host-endpoint-table-fixup.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2520: kvm-usb-host-factor-out-code.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2521: kvm-usb-host-handle-USBDEVFS_SETCONFIGURATION-returning-.patch
# For bz#742080 - Device assignment of 82599 VFs no longer work after patch for v1 PCIe Capability structures
Patch2522: kvm-device-assignment-pci_cap_init-add-82599-VF-quirk.patch
# For bz#725565 - migration subsections are still broken
Patch2523: kvm-savevm-teach-qemu_fill_buffer-to-do-partial-refills.patch
# For bz#725565 - migration subsections are still broken
Patch2524: kvm-savevm-some-coding-style-cleanups.patch
# For bz#725565 - migration subsections are still broken
Patch2525: kvm-savevm-define-qemu_get_byte-using-qemu_peek_byte.patch
# For bz#725565 - migration subsections are still broken
Patch2526: kvm-savevm-improve-subsections-detection-on-load.patch
# For bz#725565 - migration subsections are still broken
Patch2527: kvm-Revert-savevm-fix-corruption-in-vmstate_subsection_l.patch
# For bz#742401 - qemu-kvm disable live snapshot support
Patch2528: kvm-QMP-HMP-Drop-the-live-snapshot-commands.patch
# For bz#733272 - Usb stick passthrough failed under uhci+ehci
Patch2529: kvm-usb-hub-wakeup-on-attach.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2530: kvm-bz716261-kvm-Extend-kvm_arch_get_supported_cpuid-to-.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2531: kvm-bz716261-Enable-XSAVE-related-CPUID.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2532: kvm-bz716261-Fix-XSAVE-feature-bit-enumeration.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2533: kvm-bz716261-Synchronize-kernel-headers.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2534: kvm-bz716261-kvm-Enable-XSAVE-live-migration-support.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2535: kvm-bz716261-Put-XSAVE-area-in-a-sub-section.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2536: kvm-bz716261-Enable-xsave-as-a-cpu-flag.patch
# For bz#743391 - KVM guest limited to 40bit of physical address space
Patch2537: kvm-allow-more-than-1T-in-KVM-x86-guest.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2538: kvm-blockdev-Belatedly-remove-driveopts.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2539: kvm-ide-Remove-useless-IDEDeviceInfo-members-unit-drive.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2540: kvm-block-New-bdrv_next.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2541: kvm-block-Decouple-savevm-from-DriveInfo.patch
# For bz#743269 - Hot unplug of snapshot device crashes
Patch2542: kvm-savevm-Survive-hot-unplug-of-snapshot-device.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2543: kvm-ide-Replace-IDEState-members-is_cdrom-is_cf-by-drive.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2544: kvm-ide-split-ide-command-interpretation-off.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2545: kvm-ide-fix-whitespace-gap-in-ide_exec_cmd.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2546: kvm-trace-Trace-bdrv_set_locked.patch
# For bz#742469 - Drives can not be locked without media present
Patch2547: kvm-atapi-Drives-can-be-locked-without-media-present.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2548: kvm-atapi-Report-correct-errors-on-guest-eject-request.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2549: kvm-ide-Split-atapi.c-out.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2550: kvm-ide-atapi-Factor-commands-out.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2551: kvm-ide-atapi-Use-table-instead-of-switch-for-commands.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2552: kvm-ide-atapi-Replace-bdrv_get_geometry-calls-by-s-nb_se.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2553: kvm-ide-atapi-Introduce-CHECK_READY-flag-for-commands.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2554: kvm-atapi-Move-comment-to-proper-place.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2555: kvm-atapi-Explain-why-we-need-a-media-not-present-state.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2556: kvm-block-QMP-Deprecate-query-block-s-type-drop-info-blo.patch
# For bz#742476 - Make eject fail for non-removable drives even with -f
Patch2557: kvm-blockdev-Make-eject-fail-for-non-removable-drives-ev.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2558: kvm-block-Reset-device-model-callbacks-on-detach.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2559: kvm-block-raw-win32-Drop-disabled-code-for-removable-hos.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2560: kvm-block-Make-BlockDriver-method-bdrv_set_locked-return.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2561: kvm-block-Make-BlockDriver-method-bdrv_eject-return-void.patch
# For bz#742480 - Don't let locked flag prevent medium load
Patch2562: kvm-block-Don-t-let-locked-flag-prevent-medium-load.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2563: kvm-scsi-disk-Codingstyle-fixes.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2564: kvm-scsi-Remove-references-to-SET_WINDOW.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2565: kvm-scsi-Remove-REZERO_UNIT-emulation.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2566: kvm-scsi-Sanitize-command-definitions.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2567: kvm-scsi-disk-Remove-drive_kind.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2568: kvm-scsi-disk-no-need-to-call-scsi_req_data-on-a-short-r.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2569: kvm-scsi-pass-status-when-completing.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2570: kvm-trace-Fix-harmless-mismerge-of-hw-scsi-bus.c-events.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2571: kvm-scsi-move-sense-handling-to-generic-code.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2572: kvm-block-Attach-non-qdev-devices-as-well.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2573: kvm-block-Generalize-change_cb-to-BlockDevOps.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2574: kvm-block-Split-change_cb-into-change_media_cb-resize_cb.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2575: kvm-ide-Update-command-code-definitions-as-per-ACS-2-Tab.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2576: kvm-ide-Clean-up-case-label-indentation-in-ide_exec_cmd.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2577: kvm-ide-Give-vmstate-structs-internal-linkage-where-poss.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2578: kvm-block-raw-Fix-to-forward-method-bdrv_media_changed.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2579: kvm-block-Leave-tracking-media-change-to-device-models.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2580: kvm-fdc-Make-media-change-detection-more-robust.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2581: kvm-block-Clean-up-bdrv_flush_all.patch
# For bz#742484 - should be also have  snapshot on floppy
Patch2582: kvm-savevm-Include-writable-devices-with-removable-media.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2583: kvm-scsi-fill-in-additional-sense-length-correctly.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2584: kvm-ide-Fix-ATA-command-READ-to-set-ATAPI-signature-for-.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2585: kvm-ide-Use-a-table-to-declare-which-drive-kinds-accept-.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2586: kvm-ide-Reject-ATA-commands-specific-to-drive-kinds.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2587: kvm-ide-atapi-Clean-up-misleading-name-in-cmd_start_stop.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2588: kvm-ide-atapi-Track-tray-open-close-state.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2589: kvm-scsi-disk-Factor-out-scsi_disk_emulate_start_stop.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2590: kvm-scsi-disk-Track-tray-open-close-state.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2591: kvm-block-Revert-entanglement-of-bdrv_is_inserted-with-t.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2592: kvm-block-Drop-tray-status-tracking-no-longer-used.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2593: kvm-ide-atapi-Track-tray-locked-state.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2594: kvm-scsi-disk-Track-tray-locked-state.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2595: kvm-block-Leave-enforcing-tray-lock-to-device-models.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2596: kvm-block-Drop-medium-lock-tracking-ask-device-models-in.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2597: kvm-block-Rename-bdrv_set_locked-to-bdrv_lock_medium.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2598: kvm-ide-atapi-Don-t-fail-eject-when-tray-is-already-open.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2599: kvm-scsi-disk-Fix-START_STOP-to-fail-when-it-can-t-eject.patch
# For bz#743342 - IDE CD-ROM tray state gets lost on migration
Patch2600: kvm-ide-atapi-Preserve-tray-state-on-migration.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2601: kvm-block-Clean-up-remaining-users-of-removable.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2602: kvm-block-Drop-BlockDriverState-member-removable.patch
# For bz#723270 - Report cdrom tray status in a monitor command such as info block
Patch2603: kvm-block-Show-whether-the-virtual-tray-is-open-in-info-.patch
# For bz#742458 - Tracker Bug:Big block layer backport
Patch2604: kvm-block-New-change_media_cb-parameter-load.patch
# For bz#676528 - Can't insert media after previous media was forcefully ejected
Patch2605: kvm-ide-atapi-scsi-disk-Make-monitor-eject-f-then-change.patch
# For bz#741878 - USB tablet mouse does not work well when migrating between 6.2<->6.2 hosts and 6.1<->6.2 hosts
Patch2606: kvm-usb-hid-activate-usb-tablet-mouse-after-migration.patch
# For bz#729294 - Keyboard leds/states are not synchronized after migration of guest
Patch2607: kvm-ps2-migrate-ledstate.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2608: kvm-Introduce-the-RunState-type.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2609: kvm-RunState-Add-additional-states.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2610: kvm-runstate_set-Check-for-valid-transitions.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2611: kvm-Drop-the-incoming_expected-global-variable.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2612: kvm-Drop-the-vm_running-global-variable.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2613: kvm-Monitor-QMP-Don-t-allow-cont-on-bad-VM-state.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2614: kvm-QMP-query-status-Introduce-status-key.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2615: kvm-HMP-info-status-Print-the-VM-state.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2616: kvm-RunState-Rename-enum-values.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2617: kvm-runstate-Allow-to-transition-from-paused-to-postmigr.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2618: kvm-savevm-qemu_savevm_state-Drop-stop-VM-logic.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2619: kvm-runstate-Allow-user-to-migrate-twice.patch
# For bz#617889 - QMP: provide VM stop reason
Patch2620: kvm-RunState-Don-t-abort-on-invalid-transitions.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2621: kvm-migration-s-dprintf-DPRINTF.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2622: kvm-migration-simplify-state-assignmente.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2623: kvm-migration-Check-that-migration-is-active-before-canc.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2624: kvm-Reorganize-and-fix-monitor-resume-after-migration.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2625: kvm-migration-add-error-handling-to-migrate_fd_put_notif.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2626: kvm-migration-If-there-is-one-error-it-makes-no-sense-to.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2627: kvm-buffered_file-Use-right-opaque.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2628: kvm-buffered_file-reuse-QEMUFile-has_error-field.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2629: kvm-migration-don-t-write-when-migration-is-not-active.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2630: kvm-migration-set-error-if-select-return-one-error.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2631: kvm-migration-change-has_error-to-contain-errno-values.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2632: kvm-migration-return-real-error-code.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2633: kvm-migration-rename-qemu_file_has_error-to-qemu_file_ge.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2634: kvm-savevm-Rename-has_error-to-last_error-field.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2635: kvm-migration-use-qemu_file_get_error-return-value-when-.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2636: kvm-migration-make-save_live-return-errors.patch
# For bz#738565 - [FJ6.2 Bug]: Failed to capture kdump due to redundant NMIs
Patch2637: kvm-qemu-kvm-fix-improper-nmi-emulation.patch
# For bz#744780 - use-after-free in QEMU SCSI target code
Patch2638: kvm-scsi-fix-accounting-of-writes.patch
# For bz#744780 - use-after-free in QEMU SCSI target code
Patch2639: kvm-scsi-disk-bump-SCSIRequest-reference-count-until-aio.patch
# For bz#738565 - [FJ6.2 Bug]: Failed to capture kdump due to redundant NMIs
Patch2640: kvm-Revert-qemu-kvm-fix-improper-nmi-emulation.patch
# For bz#738565 - [FJ6.2 Bug]: Failed to capture kdump due to redundant NMIs
Patch2641: kvm-qemu-kvm-fix-improper-nmi-emulation-2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2642: kvm-savevm-qemu_fille_buffer-used-to-return-one-error-fo.patch
# For bz#744518 - qemu-kvm core dumps when qxl-linux guest migrate with reboot
Patch2643: kvm-qxl-fix-guest-cursor-tracking.patch
# For bz#740547 - qxl: migrating when not in native mode causes a "panic: virtual address out of range"
Patch2644: kvm-qxl-create-slots-on-post_load-in-vga-state.patch
# For bz#690427 - qemu-kvm crashes when update/roll back of qxl driver in WindowsXP guest
Patch2645: kvm-qxl-reset-update_surface.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2646: kvm-Revert-savevm-qemu_fille_buffer-used-to-return-one-e.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2647: kvm-Revert-migration-make-save_live-return-errors.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2648: kvm-Revert-migration-use-qemu_file_get_error-return-valu.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2649: kvm-Revert-savevm-Rename-has_error-to-last_error-field.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2650: kvm-Revert-migration-rename-qemu_file_has_error-to-qemu_.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2651: kvm-Revert-migration-return-real-error-code.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2652: kvm-Revert-migration-change-has_error-to-contain-errno-v.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2653: kvm-Revert-migration-set-error-if-select-return-one-erro.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2654: kvm-Revert-migration-don-t-write-when-migration-is-not-a.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2655: kvm-Revert-buffered_file-reuse-QEMUFile-has_error-field.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2656: kvm-Revert-buffered_file-Use-right-opaque.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2657: kvm-Revert-migration-If-there-is-one-error-it-makes-no-s.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2658: kvm-Revert-migration-add-error-handling-to-migrate_fd_pu.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2659: kvm-Revert-Reorganize-and-fix-monitor-resume-after-migra.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2660: kvm-Revert-migration-Check-that-migration-is-active-befo.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2661: kvm-Revert-migration-simplify-state-assignmente.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2662: kvm-Revert-migration-s-dprintf-DPRINTF.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2663: kvm-migration-s-dprintf-DPRINTF-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2664: kvm-migration-simplify-state-assignmente-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2665: vm-migration-Check-that-migration-is-active-before-canc-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2666: kvm-Reorganize-and-fix-monitor-resume-after-migration-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2667: kvm-migration-add-error-handling-to-migrate_fd_put_notif-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2668: kvm-migration-If-there-is-one-error-it-makes-no-sense-to-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2669: kvm-buffered_file-Use-right-opaque-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2670: kvm-buffered_file-reuse-QEMUFile-has_error-field-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2671: kvm-migration-don-t-write-when-migration-is-not-active-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2672: kvm-migration-set-error-if-select-return-one-error-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2673: kvm-migration-change-has_error-to-contain-errno-values-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2674: kvm-migration-return-real-error-code-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2675: kvm-migration-rename-qemu_file_has_error-to-qemu_file_ge-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2676: kvm-savevm-Rename-has_error-to-last_error-field-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2677: kvm-migration-use-qemu_file_get_error-return-value-when--v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2678: kvm-migration-make-save_live-return-errors-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
Patch2679: kvm-savevm-qemu_fille_buffer-used-to-return-one-error-fo-v2.patch
# For bz#669581 - Migration Never end while Use firewall reject migration tcp port
# For bz#749806 - Migration segfault on migrate_fd_put_notify()/qemu_file_get_error()
Patch2680: kvm-Fix-segfault-on-migration-completion.patch
# For bz#721114 - qemu fails to restore guests that were previously suspended on host shutdown
Patch2681: kvm-migration-flush-migration-data-to-disk.patch
# For bz#740493 - audio playing doesn't work when sound recorder is opened
Patch2682: kvm-hda-do-not-mix-output-and-input-streams-RHBZ-740493-v2.patch
# For bz#740493 - audio playing doesn't work when sound recorder is opened
Patch2683: kvm-hda-do-not-mix-output-and-input-stream-states-RHBZ-740493-v2.patch
Patch2684: kvm-intel-hda-fix-stream-search.patch
# For bz#728843 - qemu-kvm: Some suspicious code (found by Coverity)
Patch2685: kvm-ehci-fix-cpage-check.patch
# For bz#728385 - attempting to take a screenshot of a VM with no graphics crashes qemu
Patch2686: kvm-Fix-segfault-on-screendump-with-nographic.patch
# For bz#740707 - pass-through usb stick under usb 1.1 controller causes QEMU to abort with an assertion failure
Patch2687: kvm-usb-hub-don-t-trigger-assert-on-packet-completion.patch
# For bz#750738 - Segmentation fault if -chardev without backend
Patch2688: kvm-qemu-char-Check-for-missing-backend-name.patch
# For bz#749830 - Use after free after wavcapture fails
Patch2689: kvm-monitor-use-after-free-in-do_wav_capture.patch
# For bz#594654 - Random read/write /dev/port [vga] caused 'invalid parameters' error
Patch2690: kvm-cirrus-fix-bank-unmap.patch
# For bz#749820 - Use after free in acl_reset
Patch2691: kvm-acl-Fix-use-after-free-in-qemu_acl_reset.patch
# For bz#757142 - Invalid command line option -device '?=x' crashes
Patch2692: kvm-qdev-Fix-crash-on-device-x.patch
# For bz#757132 - VGA underline causes read beyond static array, draws crap pixels
Patch2693: kvm-console-Fix-rendering-of-VGA-underline.patch
# For bz#757713 - File name completion in monitor can append '/' when it shouldn't
Patch2694: kvm-monitor-Fix-file_completion-to-check-for-stat-failur.patch
# For bz#745758 - Segmentation fault occurs after hot unplug virtio-serial-pci while virtio-serial-port in use
Patch2695: kvm-char-Disable-write-callback-if-throttled-chardev-is-.patch
# For bz#716261 - [Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes
Patch2696: kvm-bz716261-qemu-kvm-Fix-XSAVE-for-active-AVX-usage2.patch.patch
# For bz#767499 - windows (2k3 and 2k8) hit BSOD while booting guest with usb device
Patch2697: kvm-usb-hub-implement-reset.patch
# For bz#767499 - windows (2k3 and 2k8) hit BSOD while booting guest with usb device
Patch2698: kvm-usb-hub-wakeup-on-detach-too.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2699: kvm-ide-Make-it-explicit-that-ide_create_drive-can-t-fai.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2700: kvm-qdev-Don-t-hw_error-in-qdev_init_nofail.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2701: kvm-virtio-pci-Check-for-virtio_blk_init-failure.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2702: kvm-virtio-blk-Fix-virtio-blk-s390-to-require-drive.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2703: kvm-ide-scsi-virtio-blk-Reject-empty-drives-unless-media.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2704: kvm-exit-if-drive-specified-is-invalid-instead-of-ignori.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2705: kvm-qdev-Fix-comment-around-qdev_init_nofail.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2706: kvm-Strip-trailing-n-from-error_report-s-first-argument.patch
# For bz#737879 - Qemu-kvm fails to exit when given invalid "-drive" option name or option value
Patch2707: kvm-scsi-virtio-blk-usb-msd-Clean-up-device-init-error-m.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2708: kvm-virtio-serial-kill-VirtIOSerialDevice.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2709: kvm-virtio-serial-Clean-up-virtconsole-detection.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2710: kvm-virtio-serial-Drop-useless-property-is_console.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2711: kvm-virtio-serial-bus-Simplify-handle_output-function.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2712: kvm-virtio-serial-Drop-redundant-VirtIOSerialPort-member.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2713: kvm-virtio-console-Simplify-init-callbacks.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2714: kvm-virtio-serial-Turn-props-any-virtio-serial-bus-devic.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2715: kvm-virtio-console-Check-if-chardev-backends-available-b.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2716: kvm-virtio-console-Properly-initialise-class-methods.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch2717: kvm-virtio-serial-bus-Ports-are-expected-to-implement-ha.patch
# For bz#769760 - Formatting of usb-storage disk attached on usb-hub fails to end
Patch2718: kvm-usb-storage-cancel-I-O-on-reset.patch
# For bz#752375 - CVE-2011-4127 kernel: possible privilege escalation via SG_IO ioctl
Patch2719: kvm-virtio-blk-refuse-SG_IO-requests-with-scsi-off.patch
# For bz#772086 - EMBARGOED CVE-2012-0029 qemu-kvm: e1000: process_tx_desc legacy mode packets heap overflow [rhel-6.3]
Patch2720: kvm-e1000-prevent-buffer-overflow-when-processing-legacy.patch
# For bz#719269 - No -redhat-disable-KSM introduction in man page
Patch2721: kvm-KSM-add-manpage-entry-for-redhat-disable-KSM.patch
# For bz#739944 - CD-ROMs cannot be ejected in virtualized Fedora 16
Patch2722: kvm-block-add-eject-request-callback.patch
# For bz#739944 - CD-ROMs cannot be ejected in virtualized Fedora 16
Patch2723: kvm-atapi-implement-eject-requests.patch
# For bz#754565 - Fix device assignment Coverity issues
Patch2724: kvm-pci-assign-Fix-PCI_EXP_FLAGS_TYPE-shift.patch
# For bz#754565 - Fix device assignment Coverity issues
Patch2725: kvm-pci-assign-Fix-PCIe-lnkcap.patch
# For bz#754565 - Fix device assignment Coverity issues
Patch2726: kvm-pci-assign-Remove-bogus-PCIe-lnkcap-wmask-setting.patch
# For bz#754565 - Fix device assignment Coverity issues
Patch2727: kvm-pci-assign-Harden-I-O-port-test.patch
# For bz#736942 - qcow2:Segment fault when rebase snapshot on iscsi disk but do no create the qcow2 file on it
Patch2728: kvm-qemu-img-rebase-Fix-segfault-if-backing-file-can-t-b.patch
# For bz#746866 - Passthrough then delete host usb stick too fast causes host usb stick missing
Patch2729: kvm-usb-host-fix-host-close.patch
# For bz#769745 - Released usb stick after passthrough fails to be reused on host
Patch2730: kvm-usb-host-add-usb_host_do_reset-function.patch
# For bz#746866 - Passthrough then delete host usb stick too fast causes host usb stick missing
Patch2731: kvm-Fix-parse-of-usb-device-description-with-multiple-co.patch
# For bz#769745 - Released usb stick after passthrough fails to be reused on host
Patch2732: kvm-usb-host-properly-release-port-on-unplug-exit.patch
# For bz#752003 - EMBARGOED CVE-2011-4111 qemu: ccid: buffer overflow in handling of VSC_ATR message [rhel-6.3]
Patch2733: kvm-Revert-QMP-HMP-Drop-the-live-snapshot-commands.patch
# For bz#752003 - EMBARGOED CVE-2011-4111 qemu: ccid: buffer overflow in handling of VSC_ATR message [rhel-6.3]
Patch2734: kvm-ccid-Fix-buffer-overrun-in-handling-of-VSC_ATR-messa.patch
# For bz#758194 - Coverity omnibus
Patch2735: kvm-Simplify-qemu_realloc.patch
# For bz#758194 - Coverity omnibus
Patch2736: kvm-slirp-remove-dead-assignments-spotted-by-clang.patch
# For bz#758194 - Coverity omnibus
Patch2737: kvm-update-bochs-vbe-interface.patch
# For bz#758194 - Coverity omnibus
Patch2738: kvm-x86-remove-dead-assignments-spotted-by-clang-analyze.patch
# For bz#758194 - Coverity omnibus
Patch2739: kvm-Fix-tiny-leak-in-qemu_opts_parse.patch
# For bz#758194 - Coverity omnibus
Patch2740: kvm-Fix-uint8_t-comparisons-with-negative-values.patch
# For bz#758194 - Coverity omnibus
Patch2741: kvm-vl.c-Remove-dead-assignment.patch
# For bz#758194 - Coverity omnibus
Patch2742: kvm-remove-pointless-if-from-vl.c.patch
# For bz#758194 - Coverity omnibus
Patch2743: kvm-eepro100-initialize-a-variable-in-all-cases.patch
# For bz#758194 - Coverity omnibus
Patch2744: kvm-vnc-auth-sasl-fix-a-memory-leak.patch
# For bz#758194 - Coverity omnibus
Patch2745: kvm-loader-fix-a-file-descriptor-leak.patch
# For bz#758194 - Coverity omnibus
Patch2746: kvm-qemu-io-fix-a-memory-leak.patch
# For bz#758194 - Coverity omnibus
Patch2747: kvm-x86-Prevent-sign-extension-of-DR7-in-guest-debug.patch
# For bz#758194 - Coverity omnibus
Patch2748: kvm-pci-Fix-memory-leak.patch
# For bz#758194 - Coverity omnibus
Patch2749: kvm-Fix-warning-on-OpenBSD.patch
# For bz#758194 - Coverity omnibus
Patch2750: kvm-Fix-net_check_clients-warnings-make-it-per-vlan.patch
# For bz#758194 - Coverity omnibus
Patch2751: kvm-pcnet-Fix-sign-extension-make-ipxe-work-with-2G-RAM.patch
# For bz#758194 - Coverity omnibus
Patch2752: kvm-qcow2-Fix-memory-leaks-in-error-cases.patch
# For bz#758194 - Coverity omnibus
Patch2753: kvm-Do-not-use-dprintf.patch
# For bz#758194 - Coverity omnibus
Patch2754: kvm-qemu-io-fix-aio-help-texts.patch
# For bz#758194 - Coverity omnibus
Patch2755: kvm-Fix-lld-or-llx-printf-format-use.patch
# For bz#758194 - Coverity omnibus
Patch2756: kvm-vhost_net.c-v2-Fix-build-failure-introduced-by-0bfcd.patch
# For bz#758194 - Coverity omnibus
Patch2757: kvm-qemu-io-Fix-formatting.patch
# For bz#758194 - Coverity omnibus
Patch2758: kvm-qemu-io-Fix-if-scoping-bug.patch
# For bz#758194 - Coverity omnibus
Patch2759: kvm-fix-memory-leak-in-aio_write_f.patch
# For bz#758194 - Coverity omnibus
Patch2760: kvm-block-Fix-bdrv_open-use-after-free.patch
# For bz#758194 - Coverity omnibus
Patch2761: kvm-block-Remove-dead-code.patch
# For bz#758194 - Coverity omnibus
Patch2762: kvm-ide-Fix-off-by-one-error-in-array-index-check.patch
# For bz#758194 - Coverity omnibus
Patch2763: kvm-sysbus-Supply-missing-va_end.patch
# For bz#758194 - Coverity omnibus
Patch2764: kvm-Fix-warning-about-uninitialized-variable.patch
# For bz#758194 - Coverity omnibus
Patch2765: kvm-Error-check-find_ram_offset.patch
# For bz#758194 - Coverity omnibus
Patch2766: kvm-readline-Fix-buffer-overrun-on-re-add-to-history.patch
# For bz#758194 - Coverity omnibus
Patch2767: kvm-Clean-up-assertion-in-get_boot_devices_list.patch
# For bz#758194 - Coverity omnibus
Patch2768: kvm-malloc-shims-to-simplify-backporting.patch
# For bz#758194 - Coverity omnibus
Patch2769: kvm-ui-vnc-Convert-sasl.mechlist-to-g_malloc-friends.patch
# For bz#758194 - Coverity omnibus
Patch2770: kvm-x86-cpuid-move-CPUID-functions-into-separate-file.patch
# For bz#758194 - Coverity omnibus
Patch2771: kvm-x86-cpuid-Convert-remaining-strdup-to-g_strdup.patch
# For bz#758194 - Coverity omnibus
Patch2772: kvm-x86-cpuid-Plug-memory-leak-in-cpudef_setfield.patch
# For bz#758194 - Coverity omnibus
Patch2773: kvm-x86-cpuid-Fix-crash-on-cpu.patch
# For bz#758194 - Coverity omnibus
Patch2774: kvm-keymaps-Use-glib-memory-allocation-and-free-function.patch
# For bz#758194 - Coverity omnibus
Patch2775: kvm-ui-Plug-memory-leaks-on-parse_keyboard_layout-error-.patch
# For bz#758194 - Coverity omnibus
Patch2776: kvm-raw-posix-Always-check-paio_init-result.patch
# For bz#758194 - Coverity omnibus
Patch2777: kvm-posix-aio-compat-Plug-memory-leak-on-paio_init-error.patch
# For bz#758194 - Coverity omnibus
Patch2778: kvm-os-posix-Plug-fd-leak-in-qemu_create_pidfile.patch
# For bz#758194 - Coverity omnibus
Patch2779: kvm-qemu-sockets-Plug-fd-leak-on-unix_connect_opts-error.patch
# For bz#758194 - Coverity omnibus
Patch2780: kvm-usb-linux-Disable-legacy-proc-bus-usb-and-dev-bus-us.patch
# For bz#758194 - Coverity omnibus
Patch2781: kvm-ehci-add-assert.patch
# For bz#758194 - Coverity omnibus
Patch2782: kvm-slirp-Clean-up-net_slirp_hostfwd_remove-s-use-of-get.patch
# For bz#758194 - Coverity omnibus
Patch2783: kvm-cutils-Drop-broken-support-for-zero-strtosz-default_.patch
# For bz#758194 - Coverity omnibus
Patch2784: kvm-console-Fix-qemu_default_pixelformat-for-24-bpp.patch
# For bz#758194 - Coverity omnibus
Patch2785: kvm-console-Clean-up-confusing-indentation-in-console_pu.patch
# For bz#758194 - Coverity omnibus
Patch2786: kvm-console-Fix-console_putchar-for-CSI-J.patch
# For bz#740504 - SCSI INQUIRY (opcode 0x12) to virtio devices in the KVM guest returns success even when the underlying host devices have failed.
Patch2787: kvm-virtio-blk-pass-full-status-to-the-guest.patch
# For bz#769111 - RFE: Re-enable live snapshot feature, with configuration option to enable/disable.
Patch2788: kvm-QMP-configure-script-enable-disable-for-live-snapsho.patch
# For bz#770512 - Virtio serial chardev will be still in use even failed to hot plug a serial port on it
Patch2789: kvm-qdev-Add-a-free-method-to-disassociate-chardev-from-.patch
# For bz#770512 - Virtio serial chardev will be still in use even failed to hot plug a serial port on it
Patch2790: kvm-virtio-console-no-need-to-remove-char-handlers-expli.patch
# For bz#782161 - pci-assign: Fix multifunction support
Patch2791: kvm-pci-assign-Fix-multifunction-support.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2792: kvm-Drop-whole-archive-and-static-libraries.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2793: kvm-make-qemu-img-depends-on-config-host.h.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2794: kvm-Fix-generation-of-config-host.h.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2795: kvm-cloop-use-pread.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2796: kvm-cloop-use-qemu-block-API.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2797: kvm-block-bochs-improve-format-checking.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2798: kvm-bochs-use-pread.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2799: kvm-bochs-use-qemu-block-API.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2800: kvm-parallels-use-pread.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2801: kvm-parallels-use-qemu-block-API.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2802: kvm-dmg-fix-reading-of-uncompressed-chunks.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2803: kvm-dmg-use-pread.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2804: kvm-dmg-use-qemu-block-API.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2805: kvm-cow-use-pread-pwrite.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2806: kvm-cow-stop-using-mmap.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2807: kvm-cow-use-qemu-block-API.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2808: kvm-vpc-Implement-bdrv_flush.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2809: kvm-vmdk-Fix-COW.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2810: kvm-vmdk-Clean-up-backing-file-handling.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2811: kvm-vmdk-Convert-to-bdrv_open.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2812: kvm-block-set-sector-dirty-on-AIO-write-completion.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2813: kvm-trace-Trace-bdrv_aio_flush.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2814: kvm-block-Removed-unused-function-bdrv_write_sync.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2815: kvm-tools-Use-real-async.c-instead-of-stubs.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2816: kvm-Cleanup-Be-consistent-and-use-BDRV_SECTOR_SIZE-inste.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2817: kvm-Cleanup-raw-posix.c-Be-more-consistent-using-BDRV_SE.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2818: kvm-block-allow-resizing-of-images-residing-on-host-devi.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2819: kvm-raw-posix-Fix-test-for-host-CD-ROM.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2820: kvm-raw-posix-Fix-bdrv_flush-error-return-values.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2821: kvm-block-raw-posix-Abort-on-pread-beyond-end-of-non-gro.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2822: kvm-raw-posix-raw_pwrite-comment-fixup.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2823: kvm-raw-posix-add-discard-support.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2824: kvm-win32-pair-qemu_memalign-with-qemu_vfree.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2825: kvm-qcow2-refcount-remove-write-only-variables.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2826: kvm-qcow2-Use-Qcow2Cache-in-writeback-mode-during-loadvm.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2827: kvm-qcow2-Add-bdrv_discard-support.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2828: kvm-coroutine-introduce-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2829: kvm-block-Add-bdrv_co_readv-writev.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2830: kvm-block-Emulate-AIO-functions-with-bdrv_co_readv-write.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2831: kvm-block-Add-bdrv_co_readv-writev-emulation.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2832: kvm-coroutines-Locks.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2833: kvm-qcow2-Avoid-direct-AIO-callback.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2834: kvm-block-Avoid-unchecked-casts-for-AIOCBs.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2835: kvm-qcow2-Use-QLIST_FOREACH_SAFE-macro.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2836: kvm-qcow2-Fix-in-flight-list-after-qcow2_cache_put-failu.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2837: kvm-qcow2-Use-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2838: kvm-block-qcow-Don-t-ignore-immediate-read-write-and-oth.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2839: kvm-qcow-Avoid-direct-AIO-callback.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2840: kvm-qcow-Use-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2841: kvm-qcow-initialize-coroutine-mutex.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2842: kvm-dma-Avoid-reentrancy-in-DMA-transfer-handlers.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2843: kvm-Allow-nested-qemu_bh_poll-after-BH-deletion.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2844: kvm-Revert-qed-avoid-deadlock-on-emulated-synchronous-I-.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2845: kvm-async-Remove-AsyncContext.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2846: kvm-coroutines-Use-one-global-bottom-half-for-CoQueue.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2847: kvm-posix-aio-compat-Allow-read-after-EOF.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2848: kvm-linux-aio-Fix-laio_submit-error-handling.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2849: kvm-linux-aio-Allow-reads-beyond-the-end-of-growable-ima.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2850: kvm-block-Use-bdrv_co_-instead-of-synchronous-versions-i.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2851: kvm-qcow-qcow2-Allocate-QCowAIOCB-structure-using-stack.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2852: kvm-Introduce-emulation-for-g_malloc-and-friends.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2853: kvm-Convert-the-block-layer-to-g_malloc.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2854: kvm-qcow2-Removed-unused-AIOCB-fields.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2855: kvm-qcow2-removed-cur_nr_sectors-field-in-QCowAIOCB.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2856: kvm-qcow2-remove-l2meta-from-QCowAIOCB.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2857: kvm-qcow2-remove-cluster_offset-from-QCowAIOCB.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2858: kvm-qcow2-remove-common-from-QCowAIOCB.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2859: kvm-qcow2-reindent-and-use-while-before-the-big-jump.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2860: kvm-qcow2-Removed-QCowAIOCB-entirely.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2861: kvm-qcow2-remove-memory-leak.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2862: kvm-qcow2-Properly-initialise-QcowL2Meta.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2863: kvm-qcow2-Fix-error-cases-to-run-depedent-requests.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2864: kvm-async-Allow-nested-qemu_bh_poll-calls.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2865: kvm-block-directly-invoke-.bdrv_aio_-in-bdrv_co_io_em.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2866: kvm-block-directly-invoke-.bdrv_-from-emulation-function.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2867: kvm-block-split-out-bdrv_co_do_readv-and-bdrv_co_do_writ.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2868: kvm-block-switch-bdrv_read-bdrv_write-to-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2869: kvm-block-switch-bdrv_aio_readv-to-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2870: kvm-block-mark-blocks-dirty-on-coroutine-write-completio.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2871: kvm-block-switch-bdrv_aio_writev-to-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2872: kvm-block-drop-emulation-functions-that-use-coroutines.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2873: kvm-raw-posix-remove-bdrv_read-bdrv_write.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2874: kvm-block-use-coroutine-interface-for-raw-format.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2875: kvm-block-drop-.bdrv_read-.bdrv_write-emulation.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2876: kvm-block-drop-bdrv_has_async_rw.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2877: kvm-trace-add-arguments-to-bdrv_co_io_em-trace-event.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2878: kvm-block-rename-bdrv_co_rw_bh.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2879: kvm-block-unify-flush-implementations.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2880: kvm-block-drop-redundant-bdrv_flush-implementation.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2881: kvm-block-add-bdrv_co_discard-and-bdrv_aio_discard-suppo.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2882: kvm-block-add-a-CoMutex-to-synchronous-read-drivers.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2883: kvm-block-take-lock-around-bdrv_read-implementations.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2884: kvm-block-take-lock-around-bdrv_write-implementations.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2885: kvm-block-change-flush-to-co_flush.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2886: kvm-block-change-discard-to-co_discard.patch
# For bz#783950 - RFE: Backport corountine-based block layer
Patch2887: kvm-coroutine-switch-per-thread-free-pool-to-a-global-po.patch
# For bz#789417 - Fix memory leak in register save load due to xsave support
Patch2888: kvm-Fix-memory-leak-in-register-save-load-due-to-xsave-s.patch
# For bz#789417 - Fix memory leak in register save load due to xsave support
Patch2889: kvm-x86-Avoid-runtime-allocation-of-xsave-buffer.patch
# For bz#788682 - add rhel6.3.0 machine type
Patch2890: kvm-pc-add-6.3.0-machine-type.patch
# For bz#750739 - Work around valgrind choking on our use of memalign()
Patch2891: kvm-Support-running-QEMU-on-Valgrind.patch
# For bz#748810 - qemu crashes if screen dump is called when the vm is stopped
Patch2892: kvm-qxl-stride-fixup.patch
# For bz#748810 - qemu crashes if screen dump is called when the vm is stopped
Patch2893: kvm-qxl-make-sure-we-continue-to-run-with-a-shared-buffe.patch
# For bz#782825 - backport isa-debugcon
Patch2894: kvm-debugcon-support-for-debugging-consoles-e.g.-Bochs-p.patch
# For bz#782825 - backport isa-debugcon
Patch2895: kvm-Debugcon-Fix-debugging-printf.patch
# For bz#738519 - Core dump when hotplug/hotunplug usb controller more than 1000 times
Patch2896: kvm-pci-assign-Fix-cpu_register_io_memory-leak-for-slow-.patch
# For bz#785271 - add new CPU flag definitions that are already supported by the kernel
Patch2897: kvm-add-missing-CPU-flag-names.patch
# For bz#674583 - qemu-kvm build fails without --enable-spice
Patch2898: kvm-fix-build-without-spice.patch
# For bz#754349 - guest will core dump when hotplug multiple invalid usb-host
Patch2899: kvm-Fix-usbdevice-crash.patch
# For bz#754349 - guest will core dump when hotplug multiple invalid usb-host
Patch2900: kvm-usb-make-usb_create_simple-catch-and-pass-up-errors.patch
# For bz#754349 - guest will core dump when hotplug multiple invalid usb-host
Patch2901: kvm-usb-fix-usb_qdev_init-error-handling.patch
# For bz#754349 - guest will core dump when hotplug multiple invalid usb-host
Patch2902: kvm-usb-fix-usb_qdev_init-error-handling-again.patch
# For bz#791200 - Character device consumers can miss OPENED events
Patch2903: kvm-Always-notify-consumers-of-char-devices-if-they-re-o.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2904: kvm-qbus-add-functions-to-walk-both-devices-and-busses.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2905: kvm-qdev-trigger-reset-from-a-given-device.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2906: kvm-qdev-switch-children-device-list-to-QTAILQ.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2907: kvm-qiov-prevent-double-free-or-use-after-free.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2908: kvm-scsi-introduce-SCSIReqOps.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2909: kvm-scsi-move-request-related-callbacks-from-SCSIDeviceI.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2910: kvm-scsi-pass-cdb-already-to-scsi_req_new.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2911: kvm-scsi-introduce-SCSICommand.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2912: kvm-scsi-push-lun-field-to-SCSIDevice.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2913: kvm-scsi-move-request-parsing-to-common-code.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2914: kvm-hw-scsi-bus.c-Fix-use-of-uninitialised-variable.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2915: kvm-scsi-move-handling-of-REPORT-LUNS-and-invalid-LUNs-t.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2916: kvm-scsi-move-handling-of-REQUEST-SENSE-to-common-code.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2917: kvm-scsi-do-not-overwrite-memory-on-REQUEST-SENSE-comman.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2918: kvm-scsi-add-a-bunch-more-common-sense-codes.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2919: kvm-scsi-add-support-for-unit-attention-conditions.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2920: kvm-scsi-report-unit-attention-on-reset.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2921: kvm-scsi-add-special-traces-for-common-commands.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2922: kvm-scsi-move-tcq-ndev-to-SCSIBusOps-now-SCSIBusInfo.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2923: kvm-scsi-remove-devs-array-from-SCSIBus.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2924: kvm-scsi-implement-REPORT-LUNS-for-arbitrary-LUNs.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2925: kvm-scsi-allow-arbitrary-LUNs.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2926: kvm-scsi-add-channel-to-addressing.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2927: kvm-usb-storage-move-status-debug-message-to-usb_msd_sen.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2928: kvm-usb-storage-fill-status-in-complete-callback.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2929: kvm-usb-storage-drop-tag-from-device-state.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2930: kvm-usb-storage-drop-result-from-device-state.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2931: kvm-usb-storage-don-t-try-to-send-the-status-early.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2932: kvm-scsi-do-not-call-transfer_data-after-canceling-a-req.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2933: kvm-scsi-disk-reconcile-differences-around-cancellation.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2934: kvm-scsi-execute-SYNCHRONIZE_CACHE-asynchronously.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2935: kvm-scsi-refine-constants-for-READ-CAPACITY-16.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2936: kvm-scsi-improve-MODE-SENSE-emulation.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2937: kvm-scsi-disk-commonize-iovec-creation-between-reads-and.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2938: kvm-scsi-disk-lazily-allocate-bounce-buffer.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2939: kvm-scsi-disk-fix-retrying-a-flush.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2940: kvm-scsi-fix-sign-extension-problems.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2941: kvm-scsi-pass-correct-sense-code-for-ENOMEDIUM.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2942: kvm-scsi-disk-enable-CD-emulation.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2943: kvm-scsi-disk-add-missing-definitions-for-MMC.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2944: kvm-scsi-add-GESN-definitions-to-scsi-defs.h.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2945: kvm-scsi-notify-the-device-when-unit-attention-is-report.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2946: kvm-scsi-disk-report-media-changed-via-unit-attention-se.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2947: kvm-scsi-disk-fix-coding-style-issues-braces.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2948: kvm-scsi-disk-add-stubs-for-more-MMC-commands.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2949: kvm-scsi-disk-store-valid-mode-pages-in-a-table.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2950: kvm-scsi-disk-add-more-mode-page-values-from-atapi.c.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2951: kvm-scsi-disk-support-DVD-profile-in-GET-CONFIGURATION.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2952: kvm-scsi-disk-support-READ-DVD-STRUCTURE.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2953: kvm-scsi-disk-report-media-changed-via-GET-EVENT-STATUS-.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2954: kvm-scsi-Guard-against-buflen-exceeding-req-cmd.xfer-in-.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2955: kvm-scsi-disk-fail-READ-CAPACITY-if-LBA-0-but-PMI-0.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2956: kvm-scsi-disk-implement-eject-requests.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2957: kvm-scsi-disk-guess-geometry.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2958: kvm-scsi-generic-reenable.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2959: kvm-scsi-generic-do-not-disable-FUA.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2960: kvm-scsi-generic-remove-scsi_req_fixup.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2961: kvm-scsi-generic-drop-SCSIGenericState.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2962: kvm-scsi-generic-check-ioctl-statuses-when-SG_IO-succeed.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2963: kvm-scsi-generic-look-at-host-status.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2964: kvm-scsi-generic-snoop-READ-CAPACITY-commands-to-get-blo.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2965: kvm-scsi-disk-do-not-duplicate-BlockDriverState-member.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2966: kvm-scsi-disk-remove-cluster_size.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2967: kvm-scsi-disk-small-clean-up-to-INQUIRY.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2968: kvm-scsi-move-max_lba-to-SCSIDevice.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2969: kvm-scsi-make-reqops-const.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2970: kvm-scsi-export-scsi_generic_reqops.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2971: kvm-scsi-pass-cdb-to-alloc_req.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2972: kvm-scsi-generic-bump-SCSIRequest-reference-count-until-.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2973: kvm-scsi-push-request-restart-to-SCSIDevice.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2974: kvm-scsi-disk-add-scsi-block-for-device-passthrough.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2975: kvm-scsi-bus-remove-duplicate-table-entries.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2976: kvm-scsi-update-list-of-commands.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2977: kvm-scsi-fix-parsing-of-allocation-length-field.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2978: kvm-scsi-remove-block-descriptors-from-CDs.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2979: kvm-scsi-pass-down-REQUEST-SENSE-to-the-device-when-ther.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2980: kvm-scsi-block-always-use-SG_IO-for-MMC-devices.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2981: kvm-usb-msd-do-not-register-twice-in-the-boot-order.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2984: kvm-scsi-generic-add-as-boot-device.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2985: kvm-dma-helpers-rename-is_write-to-to_dev.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2986: kvm-dma-helpers-rewrite-completion-cancellation.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2987: kvm-dma-helpers-allow-including-from-target-independent-.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2988: kvm-dma-helpers-make-QEMUSGList-target-independent.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2989: kvm-dma-helpers-add-dma_buf_read-and-dma_buf_write.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2990: kvm-dma-helpers-add-accounting-wrappers.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2991: kvm-scsi-pass-residual-amount-to-command_complete.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2992: kvm-scsi-add-scatter-gather-functionality.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2993: kvm-scsi-disk-enable-scatter-gather-functionality.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2994: kvm-scsi-add-SCSIDevice-vmstate-definitions.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2995: kvm-scsi-generic-add-migration-support.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2996: kvm-scsi-disk-add-migration-support.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2997: kvm-virtio-scsi-Add-virtio-scsi-stub-device.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2998: kvm-virtio-scsi-Add-basic-request-processing-infrastruct.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch2999: kvm-virtio-scsi-add-basic-SCSI-bus-operation.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3000: kvm-virtio-scsi-process-control-queue-requests.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3001: kvm-virtio-scsi-add-migration-support.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3002: kvm-block-Add-SG_IO-device-check-in-refresh_total_sector.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3003: kvm-scsi-fix-wrong-return-for-target-INQUIRY.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3004: kvm-scsi-fix-searching-for-an-empty-id.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3005: kvm-scsi-block-always-use-scsi_generic_ops-for-cache-non.patch
# For bz#797186 - QMP: Backport the I/O status feature
Patch3006: kvm-block-Keep-track-of-devices-I-O-status.patch
# For bz#797186 - QMP: Backport the I/O status feature
Patch3007: kvm-virtio-Support-I-O-status.patch
# For bz#797186 - QMP: Backport the I/O status feature
Patch3008: kvm-ide-Support-I-O-status.patch
# For bz#797186 - QMP: Backport the I/O status feature
Patch3009: kvm-scsi-Support-I-O-status.patch
# For bz#797186 - QMP: Backport the I/O status feature
Patch3010: kvm-QMP-query-status-Add-io-status-key.patch
# For bz#797186 - QMP: Backport the I/O status feature
Patch3011: kvm-HMP-Print-io-status-information.patch
# For bz#758194 - Coverity omnibus
Patch3012: kvm-keep-the-PID-file-locked-for-the-lifetime-of-the-pro.patch
# For bz#796063 - KVM virtual machine hangs after live migration or save/restore migration.
Patch3013: kvm-We-should-check-the-return-code-of-virtio_load.patch
# For bz#788027 - Spice and vnc connection buffer keyboard and mouse event after guest stopped
Patch3014: kvm-input-send-kbd-mouse-events-only-to-running-guests.patch
# For bz#752049 - windows guest hangs when booting with usb stick passthrough
Patch3015: kvm-usb-ehci-fix-reset.patch
# For bz#769142 - Qemu-kvm core dumped when connecting to listening vnc with "reverse"
Patch3016: kvm-vnc-Fix-fatal-crash-with-vnc-reverse-mode.patch
# For bz#638055 - Allow qemu-img re-base with undersized backing files
Patch3017: kvm-qemu-img-rebase-Fix-for-undersized-backing-files.patch
# For bz#790083 - qxl: primary surface not saved on migration when the qxl is in COMPAT mode
Patch3018: kvm-qxl-set-only-off-screen-surfaces-dirty-instead-of-th.patch
# For bz#790083 - qxl: primary surface not saved on migration when the qxl is in COMPAT mode
Patch3019: kvm-qxl-make-sure-primary-surface-is-saved-on-migration-.patch
# For bz#748810 - qemu crashes if screen dump is called when the vm is stopped
Patch3020: kvm-qxl-don-t-render-stuff-when-the-vm-is-stopped.patch
# For bz#688586 - Errors in man page: [un]supported tls-channels for Spice
Patch3021: kvm-qemu-options.hx-fix-tls-channel-help-text.patch
# For bz#769512 - The spice IPv6 option is invalid
Patch3022: kvm-spice-support-ipv6-channel-address-in-monitor-events.patch
# For bz#767606 - Need to remove the "Linearized QEMU Hack" for underlying NFS storage
Patch3024: kvm-raw-posix-do-not-linearize-anymore-direct-I-O-on-Lin.patch
# For bz#751937 - qemu-kvm core dumps during iofuzz test
Patch3025: kvm-ide-fail-I-O-to-empty-disk.patch
# For bz#743251 - segfault on monitor command "info spice" when no "-spice" option given
Patch3026: kvm-ui-spice-core-fix-segfault-in-monitor.patch
# For bz#790350 - qemu-img hits core dumped with error "qcow2_cache_destroy: Assertion" when does "qemu-img convert ........"
Patch3027: kvm-qcow2-Fix-bdrv_write_compressed-error-handling.patch
# For bz#725748 - Update qemu-img convert/re-base/commit -t man page
Patch3028: kvm-Documentation-Add-qemu-img-check-rebase.patch
# For bz#725748 - Update qemu-img convert/re-base/commit -t man page
Patch3029: kvm-Add-missing-documentation-for-qemu-img.patch
# For bz#725748 - Update qemu-img convert/re-base/commit -t man page
Patch3030: kvm-Documentation-Add-qemu-img-t-parameter-in-man-page.patch
# For bz#676484 - There is no indication of full preallocation mode in qemu-img man page
Patch3031: kvm-Documentation-Mention-qcow2-full-preallocation.patch
# For bz#653779 - [RFE] VNC server ignore shared-flag during client init
Patch3032: kvm-vnc-Migrate-to-using-QTAILQ-instead-of-custom-implem.patch
# For bz#653779 - [RFE] VNC server ignore shared-flag during client init
Patch3033: kvm-vnc-implement-shared-flag-handling.patch
# For bz#752138 - qemu: "unlimited" migration speed to regular file can't be cancelled
Patch3034: kvm-ram-use-correct-milliseconds-amount.patch
# For bz#752138 - qemu: "unlimited" migration speed to regular file can't be cancelled
Patch3035: kvm-migration-Fix-calculation-of-bytes_transferred.patch
# For bz#752138 - qemu: "unlimited" migration speed to regular file can't be cancelled
Patch3036: kvm-ram-calculate-bwidth-correctly.patch
# For bz#575159 - RFE: a QMP event notification for disk media eject
Patch3037: kvm-block-Rename-bdrv_mon_event-BlockMonEventAction.patch
# For bz#575159 - RFE: a QMP event notification for disk media eject
Patch3038: kvm-block-bdrv_eject-Make-eject_flag-a-real-bool.patch
# For bz#575159 - RFE: a QMP event notification for disk media eject
Patch3039: kvm-block-Don-t-call-bdrv_eject-if-the-tray-state-didn-t.patch
# For bz#575159 - RFE: a QMP event notification for disk media eject
Patch3040: kvm-ide-drop-ide_tray_state_post_load.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch3041: kvm-virtio-serial-Fix-segfault-on-guest-boot.patch
# For bz#575159 - RFE: a QMP event notification for disk media eject
Patch3042: kvm-qmp-add-DEVICE_TRAY_MOVED-event.patch
# For bz#796575 - qemu-kvm wakes up 66 times a second
Patch3043: kvm-Flush-coalesced-MMIO-buffer-periodly.patch
# For bz#796575 - qemu-kvm wakes up 66 times a second
Patch3044: kvm-Flush-coalesced-mmio-buffer-on-IO-window-exits.patch
# For bz#796575 - qemu-kvm wakes up 66 times a second
Patch3045: kvm-Move-graphic-related-coalesced-MMIO-flushes-to-affec.patch
# For bz#796575 - qemu-kvm wakes up 66 times a second
Patch3046: kvm-Drop-obsolete-nographic-timer.patch
# For bz#796575 - qemu-kvm wakes up 66 times a second
Patch3047: kvm-avoid-reentring-kvm_flush_coalesced_mmio_buffer.patch
# For bz#742841 - [RHEL6.2] Assertion failure in qed l2 cache commit
Patch3049: kvm-qed-fix-use-after-free-during-l2-cache-commit.patch
Patch3050: kvm-qxl-Add-support-for-2000x2000-resolution.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3051: kvm-notifier-Pass-data-argument-to-callback.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3052: kvm-qemu-timer-Introduce-clock-reset-notifier.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3053: kvm-mc146818rtc-Handle-host-clock-resets.patch
# For bz#798936 - enable architectural PMU cpuid leaf for kvm
Patch3054: kvm-enable-architectural-PMU-cpuid-leaf-for-kvm.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3055: kvm-Revert-notifier-Pass-data-argument-to-callback.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3056: kvm-Revert-qemu-timer-Introduce-clock-reset-notifier.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3057: kvm-Revert-mc146818rtc-Handle-host-clock-resets.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3058: kvm-USB-add-usb-network-redirection-support.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3059: kvm-usb-redir-rhel6-build-fixups.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3060: kvm-usb-redir-Device-disconnect-re-connect-robustness-fi.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3061: kvm-usb-redir-Don-t-try-to-write-to-the-chardev-after-a-.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3062: kvm-usb-redir-Clear-iso-irq-error-when-stopping-the-stre.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3063: kvm-usb-redir-Dynamically-adjust-iso-buffering-size-base.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3064: kvm-usb-redir-Pre-fill-our-isoc-input-buffer-before-send.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3065: kvm-usb-redir-Try-to-keep-our-buffer-size-near-the-targe.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3066: kvm-usb-redir-Improve-some-debugging-messages.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3067: kvm-qemu-char-make-qemu_chr_event-public.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3068: kvm-spice-qemu-char-Generate-chardev-open-close-events.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3069: kvm-usb-redir-Call-qemu_chr_fe_open-close.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3070: kvm-usb-redir-Add-flow-control-support.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3071: kvm-usb-ehci-Clear-the-portstatus-powner-bit-on-device-d.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3072: kvm-usb-redir-Add-the-posibility-to-filter-out-certain-d.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3073: kvm-usb-ehci-Handle-ISO-packets-failing-with-an-error-ot.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3074: kvm-ehci-drop-old-stuff.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3075: kvm-usb-redir-Fix-printing-of-device-version.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3076: kvm-usb-redir-Always-clear-device-state-on-filter-reject.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3077: kvm-usb-redir-Let-the-usb-host-know-about-our-device-fil.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3078: kvm-usb-redir-Limit-return-values-returned-by-iso-packet.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3079: kvm-usb-redir-Return-USB_RET_NAK-when-we-ve-no-data-for-.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3080: kvm-usb-ehci-Never-follow-table-entries-with-the-T-bit-s.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3081: kvm-usb-ehci-split-our-qh-queue-into-async-and-periodic-.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3082: kvm-usb-ehci-always-call-ehci_queues_rip_unused-for-peri.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3083: kvm-usb-ehci-Drop-cached-qhs-when-the-doorbell-gets-rung.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3084: kvm-usb-ehci-Rip-the-queues-when-the-async-or-period-sch.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3085: kvm-usb-ehci-Any-packet-completion-except-for-NAK-should.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3086: kvm-usb-ehci-Fix-cerr-tracking.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3087: kvm-usb-ehci-Remove-dead-nakcnt-code.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3088: kvm-usb-ehci-Fix-and-simplify-nakcnt-handling.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3089: kvm-usb-ehci-Cleanup-itd-error-handling.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3090: kvm-usb-return-BABBLE-rather-then-NAK-when-we-receive-to.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3091: kvm-usb-add-USB_RET_IOERROR.patch
# For bz#758104 - [SPICE]Add usbredirection support to qemu
Patch3092: kvm-usb-ehci-sanity-check-iso-xfers.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3093: kvm-notifier-Pass-data-argument-to-callback-v2.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3094: kvm-suspend-add-infrastructure.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3095: kvm-suspend-switch-acpi-s3-to-new-infrastructure.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3096: kvm-suspend-add-system_wakeup-monitor-command.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3097: kvm-suspend-make-ps-2-devices-wakeup-the-guest.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3098: kvm-suspend-make-serial-ports-wakeup-the-guest.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3099: kvm-suspend-make-rtc-alarm-wakeup-the-guest.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3100: kvm-suspend-make-acpi-timer-wakeup-the-guest.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3101: kvm-suspend-add-qmp-events.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3102: kvm-add-qemu_unregister_suspend_notifier.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3103: kvm-make-assigned-pci-devices-wakeup-the-guest-instantly.patch
# For bz#766303 - [RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action
Patch3104: kvm-wakeup-on-migration.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3105: kvm-qemu-timer-Introduce-clock-reset-notifier2.patch
# For bz#734426 - KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation
Patch3106: kvm-mc146818rtc-Handle-host-clock-resets2.patch
# For bz#767302 - new CPU model for AMD Bulldozer
Patch3107: kvm-cpu-flags-aliases-pclmuldq-pclmulqdq-and-ffxsr-fxsr_.patch
# For bz#767302 - new CPU model for AMD Bulldozer
Patch3108: kvm-add-Opteron_G4-CPU-model-v2.patch
# For bz#760953 - qemu-kvm: new Sandy Bridge CPU definition
Patch3109: kvm-add-SandyBridge-CPU-model-v2.patch
# For bz#800536 - virtio-blk nonfunctional after live migration or save/restore migration.
Patch3110: kvm-force-enable-VIRTIO_BLK_F_SCSI-if-present-on-migrati.patch
# For bz#562886 - Implement vCPU hotplug/unplug
Patch3111: kvm-Use-defines-instead-of-numbers-for-cpu-hotplug.patch
# For bz#562886 - Implement vCPU hotplug/unplug
Patch3112: kvm-Fix-cpu-pci-hotplug-to-generate-level-triggered-inte.patch
# For bz#562886 - Implement vCPU hotplug/unplug
Patch3113: kvm-Make-pause-resume_all_vcpus-available-to-usage-from-.patch
# For bz#562886 - Implement vCPU hotplug/unplug
Patch3114: kvm-Prevent-partially-initialized-vcpu-being-visible.patch
# For bz#795652 - Inappropriate __com.redhat_spice_migrate_info error handler causes qemu monitor hanging
Patch3115: kvm-monitor-fix-client_migrate_info-error-handling.patch
# For bz#781920 - rtl8139: prevent unlimited send buffer allocated for guest descriptors.
Patch3116: kvm-rtl8139-limit-transmission-buffer-size-in-c-mode.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3117: kvm-configure-fix-rhel-6-only-configure-break-on-audio_d.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3118: kvm-qxl-fix-spice-sdl-no-cursor-regression.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3119: kvm-qxl-drop-qxl_spice_update_area_async-definition.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3120: kvm-qxl-require-spice-0.8.2.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3121: kvm-qxl-remove-flipped.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3122: kvm-qxl-introduce-QXLCookie.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3123: kvm-qxl-make-qxl_render_update-async.patch
# For bz#747011 - Taking screenshot  hangs Spice display when a client is connected
Patch3124: kvm-qxl-properly-handle-upright-and-non-shared-surfaces.patch
# For bz#803344 - qemu-img convert doesn't print errno strings on I/O errors
Patch3125: kvm-qemu-img-print-error-codes-when-convert-fails.patch
# For bz#796118 - qemu hits core dump when boot guest with 2 pass-though usb devices under 1.1 controller
Patch3126: kvm-usb-fix-use-after-free.patch
# For bz#800183 - qed: do not evict in-use L2 table cache entries
Patch3127: kvm-qed-do-not-evict-in-use-L2-table-cache-entries.patch
# For bz#802033 - kvm guest hangs on reboot after cpu-hotplug
Patch3128: kvm-Update-cpu-count-on-cpu-hotplug-in-cmos.patch
Patch3129: kvm-QList-Introduce-QLIST_FOREACH_ENTRY.patch
Patch3130: kvm-QDict-Small-terminology-change.patch
Patch3131: kvm-QDict-Introduce-functions-to-retrieve-QDictEntry-val.patch
Patch3132: kvm-QDict-Introduce-new-iteration-API.patch
Patch3133: kvm-check-qdict-Introduce-test-for-the-new-iteration-API.patch
Patch3134: kvm-QDict-Rename-err_value.patch
Patch3135: kvm-QDict-Introduce-qdict_get_try_bool.patch
Patch3136: kvm-QError-Introduce-QERR_QMP_EXTRA_MEMBER.patch
Patch3137: kvm-Move-macros-GCC_ATTR-and-GCC_FMT_ATTR-to-common-head.patch
Patch3138: kvm-Introduce-compiler.h-header-file.patch
Patch3139: kvm-QError-Introduce-qerror_format_desc.patch
Patch3140: kvm-QError-Introduce-qerror_format.patch
Patch3141: kvm-Introduce-the-new-error-framework.patch
Patch3142: kvm-json-parser-propagate-error-from-parser.patch
Patch3143: kvm-Add-simple-pkg_config-variable-to-configure-script.patch
Patch3144: kvm-Add-hard-build-dependency-on-glib.patch
Patch3145: kvm-qlist-add-qlist_first-qlist_next.patch
Patch3146: kvm-qapi-add-module-init-types-for-qapi.patch
Patch3147: kvm-qapi-add-QAPI-visitor-core.patch
Patch3148: kvm-qapi-add-QMP-input-visitor.patch
Patch3149: kvm-qapi-add-QMP-output-visitor.patch
Patch3150: kvm-qapi-add-QAPI-dealloc-visitor.patch
Patch3151: kvm-qapi-add-QMP-command-registration-lookup-functions.patch
Patch3152: kvm-qapi-add-QMP-dispatch-functions.patch
Patch3153: kvm-qapi-add-ordereddict.py-helper-library.patch
Patch3154: kvm-qapi-add-qapi.py-helper-libraries.patch
Patch3155: kvm-qapi-add-qapi-types.py-code-generator.patch
Patch3156: kvm-qapi-add-qapi-visit.py-code-generator.patch
Patch3157: kvm-qapi-add-qapi-commands.py-code-generator.patch
Patch3158: kvm-qapi-test-schema-used-for-unit-tests.patch
Patch3159: kvm-qapi-add-test-visitor-tests-for-gen.-visitor-code.patch
Patch3160: kvm-qapi-add-test-qmp-commands-tests-for-gen.-marshallin.patch
Patch3161: kvm-qapi-add-QAPI-code-generation-documentation.patch
Patch3162: kvm-qerror-add-QERR_JSON_PARSE_ERROR-to-qerror.c.patch
Patch3163: kvm-guest-agent-command-state-class.patch
Patch3164: kvm-Make-glib-mandatory-and-fixup-utils-appropriately.patch
Patch3165: kvm-guest-agent-qemu-ga-daemon.patch
Patch3166: kvm-guest-agent-add-guest-agent-RPCs-commands.patch
Patch3167: kvm-guest-agent-fix-build-with-OpenBSD.patch
Patch3168: kvm-guest-agent-use-QERR_UNSUPPORTED-for-disabled-RPCs.patch
Patch3169: kvm-guest-agent-only-enable-FSFREEZE-when-it-s-supported.patch
Patch3170: kvm-qemu-ga-remove-dependency-on-gio-and-gthread.patch
Patch3171: kvm-guest-agent-remove-g_strcmp0-usage.patch
Patch3172: kvm-guest-agent-remove-uneeded-dependencies.patch
Patch3173: kvm-guest-agent-add-RPC-blacklist-command-line-option.patch
Patch3174: kvm-guest-agent-add-supported-command-list-to-guest-info.patch
Patch3175: kvm-qapi-add-code-generation-support-for-middle-mode.patch
Patch3176: kvm-qapi-fixup-command-generation-for-functions-that-ret.patch
Patch3177: kvm-qapi-dealloc-visitor-fix-premature-free-and-iteratio.patch
Patch3178: kvm-qapi-generate-qapi_free_-functions-for-List-types.patch
Patch3179: kvm-qapi-add-test-cases-for-generated-free-functions.patch
Patch3180: kvm-qapi-dealloc-visitor-support-freeing-of-nested-lists.patch
Patch3181: kvm-qapi-modify-visitor-code-generation-for-list-iterati.patch
Patch3182: kvm-qapi-Don-t-use-c_var-on-enum-strings.patch
Patch3183: kvm-qapi-Automatically-generate-a-_MAX-value-for-enums.patch
Patch3184: kvm-qapi-commands.py-Don-t-call-the-output-marshal-on-er.patch
Patch3185: kvm-qapi-Check-for-negative-enum-values.patch
Patch3186: kvm-qapi-fix-guardname-generation.patch
Patch3187: kvm-qapi-allow-a-gen-key-to-suppress-code-generation.patch
Patch3188: kvm-Makefile-add-missing-deps-on-GENERATED_HEADERS.patch
Patch3189: kvm-qapi-protect-against-NULL-QObject-in-qmp_input_get_o.patch
Patch3190: kvm-Fix-spelling-in-comments-and-debug-messages-recieve-.patch
Patch3191: kvm-json-lexer-fix-conflict-with-mingw32-ERROR-definitio.patch
Patch3192: kvm-json-streamer-allow-recovery-after-bad-input.patch
Patch3193: kvm-json-lexer-limit-the-maximum-size-of-a-given-token.patch
Patch3194: kvm-json-streamer-limit-the-maximum-recursion-depth-and-.patch
Patch3195: kvm-json-streamer-make-sure-to-reset-token_size-after-em.patch
Patch3196: kvm-json-parser-detect-premature-EOI.patch
Patch3197: kvm-json-lexer-reset-the-lexer-state-on-an-invalid-token.patch
Patch3198: kvm-json-lexer-fix-flushing-logic-to-not-always-go-to-er.patch
Patch3199: kvm-json-lexer-make-lexer-error-recovery-more-determinis.patch
Patch3200: kvm-json-streamer-add-handling-for-JSON_ERROR-token-stat.patch
Patch3201: kvm-json-parser-add-handling-for-NULL-token-list.patch
Patch3202: kvm-.gitignore-ignore-qemu-ga-and-qapi-generated.patch
Patch3204: kvm-Makefile-fix-dependencies-for-generated-.h-.c.patch
Patch3205: kvm-Create-qemu-os-win32.h-and-move-WIN32-specific-decla.patch
Patch3206: kvm-Introduce-os-win32.c-and-move-polling-functions-from.patch
Patch3207: kvm-vl.c-Move-host_main_loop_wait-to-OS-specific-files.patch
Patch3208: kvm-Introduce-os-posix.c-and-create-os_setup_signal_hand.patch
Patch3209: kvm-Move-win32-early-signal-handling-setup-to-os_setup_s.patch
Patch3210: kvm-Rename-os_setup_signal_handling-to-os_setup_early_si.patch
Patch3211: kvm-Rename-qemu-options.h-to-qemu-options.def.patch
Patch3212: kvm-qemu-ga-Add-schema-documentation-for-types.patch
Patch3213: kvm-qemu-ga-move-channel-transport-functionality-into-wr.patch
Patch3214: kvm-qemu-ga-separate-out-common-commands-from-posix-spec.patch
Patch3215: kvm-qemu-ga-rename-guest-agent-commands.c-commands-posix.patch
Patch3216: kvm-qemu-ga-fixes-for-win32-build-of-qemu-ga.patch
Patch3217: kvm-qemu-ga-add-initial-win32-support.patch
Patch3218: kvm-qemu-ga-add-Windows-service-integration.patch
Patch3219: kvm-qemu-ga-add-win32-guest-shutdown-command.patch
Patch3220: kvm-qemu-ga-add-guest-suspend-disk.patch
Patch3221: kvm-qemu-ga-add-guest-suspend-ram.patch
Patch3222: kvm-qemu-ga-add-guest-suspend-hybrid.patch
Patch3223: kvm-Fix-qapi-code-generation-wrt-parallel-build.patch
Patch3224: kvm-qemu-ga-make-guest-suspend-posix-only.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3225: kvm-monitor-Establish-cmd-flags-and-convert-the-async-ta.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3226: kvm-Monitor-handle-optional-arg-as-a-bool.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3227: kvm-QMP-New-argument-checker-first-part.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3228: kvm-QMP-New-argument-checker-second-part.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3229: kvm-QMP-Drop-old-client-argument-checker.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3230: kvm-monitor-Allow-and-b-boolean-types-to-be-either-bool-.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3231: kvm-QMP-Introduce-qmp_check_input_obj.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3232: kvm-QMP-Drop-old-input-object-checking.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3233: kvm-QMP-handle_qmp_command-Small-cleanup.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3234: kvm-monitor-Allow-to-exclude-commands-from-QMP.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3235: kvm-Monitor-Introduce-search_dispatch_table.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3236: kvm-QMP-handle_qmp_command-Move-cmd-sanity-check.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3237: kvm-QMP-Don-t-use-do_info.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3238: kvm-QMP-Introduce-qmp_find_cmd.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3239: kvm-QMP-Fix-default-response-regression.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3240: kvm-qerror-add-qerror_report_err.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3241: kvm-qapi-use-middle-mode-in-QMP-server.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3242: kvm-QError-Introduce-QERR_IO_ERROR.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3243: kvm-qapi-Introduce-blockdev-group-snapshot-sync-command.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3244: kvm-QMP-Add-qmp-command-for-blockdev-group-snapshot-sync.patch
# For bz#784153 - RFE - Support Group Live Snapshots
Patch3245: kvm-Only-build-group-snapshots-if-CONFIG_LIVE_SNAPSHOTS-.patch
# For bz#632771 - [6.3 FEAT] add virt-agent (qemu-ga backend) to qemu
Patch3246: kvm-guest-agent-remove-unsupported-guest-agent-commands-.patch
Patch3247: kvm-Revert-virtio-serial-Fix-segfault-on-guest-boot.patch
# For bz#769528 - virtio-serial: Backport code cleanups from upstream
Patch3248: kvm-virtio-serial-Fix-segfault-on-guest-boot-v2.patch
# For bz#785963 - keys left pressed on the vncserver when closing the connection
Patch3249: kvm-Fix-curses-interaction-with-keymaps.patch
# For bz#785963 - keys left pressed on the vncserver when closing the connection
Patch3250: kvm-vnc-lift-modifier-keys-on-client-disconnect.patch
# For bz#761439 - Add command to put guest into hibernation to qemu-ga
Patch3251: kvm-Fix-qapi-code-generation-fix.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3252: kvm-Revert-qed-intelligent-streaming-implementation.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3253: kvm-Revert-block-add-drive-stream-on-off.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3254: kvm-Revert-qmp-add-block_job_set_speed-command.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3255: kvm-Revert-qmp-add-query-block-jobs-command.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3256: kvm-Revert-qmp-add-block_job_cancel-command.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3257: kvm-Revert-qmp-add-block_stream-command.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3258: kvm-Revert-block-add-bdrv_aio_copy_backing.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3259: kvm-Revert-qed-add-support-for-copy-on-read.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3260: kvm-Revert-qed-make-qed_aio_write_alloc-reusable.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3261: kvm-Revert-qed-extract-qed_start_allocating_write.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3262: kvm-Revert-qed-replace-is_write-with-flags-field.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3263: kvm-Revert-block-add-drive-copy-on-read-on-off.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3264: kvm-block-use-public-bdrv_is_allocated-interface.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3265: kvm-block-add-.bdrv_co_is_allocated.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3266: kvm-qed-convert-to-.bdrv_co_is_allocated.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3267: kvm-block-convert-qcow2-qcow2-and-vmdk-to-.bdrv_co_is_al.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3268: kvm-vvfat-convert-to-.bdrv_co_is_allocated.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3269: kvm-vdi-convert-to-.bdrv_co_is_allocated.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3270: kvm-cow-convert-to-.bdrv_co_is_allocated.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3271: kvm-vvfat-Fix-read-write-mode.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3272: kvm-block-drop-.bdrv_is_allocated-interface.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3273: kvm-block-add-bdrv_co_is_allocated-interface.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3274: kvm-qemu-common-add-QEMU_ALIGN_DOWN-and-QEMU_ALIGN_UP-ma.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3275: kvm-coroutine-add-qemu_co_queue_restart_all.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3276: kvm-block-add-request-tracking.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3277: kvm-block-add-interface-to-toggle-copy-on-read.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3278: kvm-block-wait-for-overlapping-requests.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3279: kvm-block-request-overlap-detection.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3280: kvm-cow-use-bdrv_co_is_allocated.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3281: kvm-block-core-copy-on-read-logic.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3282: kvm-block-add-drive-copy-on-read-on-offv2.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3283: kvm-block-implement-bdrv_co_is_allocated-boundary-cases.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3284: kvm-block-wait_for_overlapping_requests-deadlock-detecti.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3285: kvm-block-convert-qemu_aio_flush-calls-to-bdrv_drain_all.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3286: kvm-coroutine-add-co_sleep_ns-coroutine-sleep-function.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3287: kvm-block-check-bdrv_in_use-before-blockdev-operations.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3288: kvm-block-make-copy-on-read-a-per-request-flag.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3289: kvm-block-add-BlockJob-interface-for-long-running-operat.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3290: kvm-block-add-image-streaming-block-job.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3291: kvm-block-rate-limit-streaming-operations.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3292: kvm-qmp-add-block_stream-commandv2.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3293: kvm-qmp-add-block_job_set_speed-commandv2.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3294: kvm-qmp-add-block_job_set_speed-command2.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3295: kvm-qmp-add-query-block-jobs.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3296: kvm-block-add-bdrv_find_backing_image.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3297: kvm-add-QERR_BASE_NOT_FOUND.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3298: kvm-block-add-support-for-partial-streaming.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3299: kvm-docs-describe-live-block-operations.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3300: kvm-cutils-extract-buffer_is_zero-from-qemu-img.c.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3301: kvm-block-add-.bdrv_co_write_zeroes-interface.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3302: kvm-block-perform-zero-detection-during-copy-on-read.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3303: kvm-qed-replace-is_write-with-flags-field2.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3304: kvm-qed-add-.bdrv_co_write_zeroes-support.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3305: kvm-qemu-io-add-write-z-option-for-bdrv_co_write_zeroes.patch
# For bz#790421 - exit with error when tls-port is not specified but tls is enabled by tls-channel or x509* options
Patch3306: kvm-Error-out-when-tls-channel-option-is-used-without-TL.patch
# For bz#582475 - RFE: Support live migration of storage (live streaming)
Patch3307: kvm-fix-virtio-scsi-build-after-streaming-patches.patch
# For bz#788942 - virtio-scsi TMF handling fixes
Patch3308: kvm-virtio-scsi-fix-cmd-lun-cut-and-paste-errors.patch
# For bz#800710 - migration crashes on the source after hot remove of virtio-scsi controller
Patch3309: kvm-virtio-scsi-call-unregister_savevm.patch
# For bz#800710 - migration crashes on the source after hot remove of virtio-scsi controller
Patch3310: kvm-scsi-add-get_dev_path.patch
# For bz#803219 - virtio-scsi:after eject  virtio-scsi CD-ROM  tray-open's value still be 0
Patch3311: kvm-scsi-cd-check-ready-condition-before-processing-seve.patch
# For bz#801416 - virtio-scsi: use local image as guest disk can not configure the multipath
Patch3312: kvm-scsi-copy-serial-number-into-VPD-page-0x83.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3313: kvm-block-use-proper-qerrors-in-qmp_block_resize.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3314: kvm-qapi-Convert-blockdev_snapshot_sync.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3315: kvm-use-QSIMPLEQ_FOREACH_SAFE-when-freeing-list-elements.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3316: kvm-Group-snapshot-Fix-format-name-for-backing-file.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3317: kvm-qapi-complete-implementation-of-unions.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3318: kvm-rename-blockdev-group-snapshot-sync.patch
# For bz#785683 - A live snapshot shouldn't reconfigure the backing file path in the new image
Patch3319: kvm-add-mode-field-to-blockdev-snapshot-sync-transaction.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3320: kvm-qmp-convert-blockdev-snapshot-sync-to-a-wrapper-arou.patch
# For bz#723754 - Update qemu-kvm -global option man page
Patch3321: kvm-Add-global-option-to-man-page.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3322: kvm-Add-blkmirror-block-driver.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3323: kvm-qapi-add-c_fun-to-escape-function-names.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3324: kvm-add-mirroring-to-transaction.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3325: kvm-add-drive-mirror-command-and-HMP-equivalent.patch
# For bz#647384 - RFE - Support live modification of the backing file chain (aka "snapshot deletion" aka "drive-reopen")
Patch3326: kvm-Add-the-drive-reopen-command.patch
# For bz#802284 - RFE: Support live migration of storage (mirroring)
Patch3327: kvm-Live-block-copy-Fix-mirroring.patch
# For bz#805362 - guest kernel call trace when hotplug vcpu
Patch3328: kvm-Use-defines-instead-of-numbers-for-pci-hotplug-sts-b.patch
# For bz#805362 - guest kernel call trace when hotplug vcpu
Patch3329: kvm-Fix-pci-hotplug-to-generate-level-triggered-interrup.patch
# For bz#801449 - qemu-kvm is not closing the merged images files (block_stream)
Patch3330: kvm-block-stream-close-unused-files-and-update-backing_h.patch
# For bz#769760 - Formatting of usb-storage disk attached on usb-hub fails to end
Patch3331: kvm-ehci-fix-ehci_child_detach.patch
# For bz#807916 - boot from the USB storage core dumped after press "ctrl-alt-delete"
Patch3332: kvm-usb-ehci-drop-assert.patch
# For bz#807984 - [SPICE]Hi speed USB ISO streaming does not work with windows XP
Patch3333: kvm-usb-ehci-frindex-always-is-a-14-bits-counter-rhbz-80.patch
# For bz#808760 - [SPICE] usb-redir device does not accept unconfigured devices
Patch3334: kvm-usb-redir-An-interface-count-of-0-is-a-valid-value-r.patch
# For bz#806975 - Live migration of bridge network to direct network fails with libvirt and virtio
Patch3335: kvm-macvtap-rhel6.2-compatibility.patch
# For bz#807512 - qemu exit and Segmentation fault when hotplug vcpus with bigger value
Patch3336: kvm-Allow-to-hot-plug-cpus-only-in-range-0.max_cpus.patch
# For bz#810983 - QAPI may double free on errors
Patch3337: kvm-qapi-fix-double-free-in-qmp_output_visitor_cleanup.patch
# For bz#807898 - guest quit or device hot-unplug during streaming fails
Patch3338: kvm-blockdev-add-refcount-to-DriveInfo.patch
# For bz#807898 - guest quit or device hot-unplug during streaming fails
Patch3339: kvm-blockdev-make-image-streaming-safe-across-hotplug.patch
# For bz#807898 - guest quit or device hot-unplug during streaming fails
Patch3340: kvm-block-cancel-jobs-when-a-device-is-ready-to-go-away.patch
# For bz#807898 - guest quit or device hot-unplug during streaming fails
Patch3341: kvm-block-fix-streaming-closing-race.patch
# For bz#798857 - pkill qemu-kvm appear block I/O error after live snapshot for multiple vms in parallelly
Patch3342: kvm-block-Drain-requests-in-bdrv_close.patch
# For bz#807878 - Cannot hear sound when passthrough a USB speaker into RHEL guest
Patch3343: kvm-usb-add-USBDescriptor-use-for-device-descriptors.patch
# For bz#807878 - Cannot hear sound when passthrough a USB speaker into RHEL guest
Patch3344: kvm-usb-use-USBDescriptor-for-device-qualifier-descripto.patch
# For bz#807878 - Cannot hear sound when passthrough a USB speaker into RHEL guest
Patch3345: kvm-usb-use-USBDescriptor-for-config-descriptors.patch
# For bz#807878 - Cannot hear sound when passthrough a USB speaker into RHEL guest
Patch3346: kvm-usb-use-USBDescriptor-for-interface-descriptors.patch
# For bz#807878 - Cannot hear sound when passthrough a USB speaker into RHEL guest
Patch3347: kvm-usb-use-USBDescriptor-for-endpoint-descriptors.patch
# For bz#807878 - Cannot hear sound when passthrough a USB speaker into RHEL guest
Patch3348: kvm-usb-host-rewrite-usb_linux_update_endp_table.patch
# For bz#801449 - qemu-kvm is not closing the merged images files (block_stream)
# For bz#811228 - block streaming reverts image to auto-probe backing file format
Patch3349: kvm-block-pass-new-base-image-format-to-bdrv_change_back.patch
# For bz#812085 - use the name block-job-cancel to indicate async cancel support
Patch3350: kvm-use-hyphens-in-streaming-commands-to-indicate-async-.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3351: kvm-block-set-job-speed-in-block_set_speed.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3352: kvm-block-bdrv_append-fixes.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3353: kvm-block-fail-live-snapshot-if-disk-has-no-medium.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3354: kvm-block-open-backing-file-as-read-only-when-probing-fo.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3355: kvm-Count-dirty-blocks-and-expose-an-API-to-get-dirty-co.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3356: kvm-block-fix-shift-in-dirty-bitmap-calculation.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3357: kvm-block-fix-allocation-size-for-dirty-bitmap.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3358: kvm-block-introduce-new-dirty-bitmap-functionality.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3359: kvm-block-allow-interrupting-a-co_sleep_ns.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3360: kvm-block-allow-doing-I-O-in-a-job-after-cancellation.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3361: kvm-block-cancel-job-on-drive-reopen.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3362: kvm-block-add-witness-argument-to-drive-reopen.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3363: kvm-block-add-mirror-job.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3364: kvm-block-copy-over-job-and-dirty-bitmap-fields-in-bdrv_.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3365: kvm-block-rewrite-drive-mirror-for-mirror-job.patch
# For bz#812948 - drive-reopen broken with snapshots
Patch3366: kvm-block-Set-backing_hd-to-NULL-after-deleting-it.patch
# For bz#812948 - drive-reopen broken with snapshots
Patch3367: kvm-block-another-bdrv_append-fix.patch
# For bz#812328 - qemu-kvm aborted when using multiple usb storage on Win2003 guest
Patch3368: kvm-ehci-remove-hack.patch
# For bz#798967 - host kernel panic when sending system_reset to windows guest with 82576 PF assigned
Patch3369: kvm-device-assignment-Disable-MSI-MSI-X-in-assigned-devi.patch
# For bz#812833 - qcow2 converting error when -o cluster_size <= 2048
Patch3370: kvm-qcow2-Fix-return-value-of-alloc_refcount_block.patch
# For bz#808805 - qemu-kvm-el version should disable block_stream
Patch3371: kvm-Block-streaming-disable-for-RHEL.patch
# For bz#807313 - qemu-kvm core dumped while booting guest with usb-storage running on uhci
Patch3372: kvm-usb-storage-fix-request-canceling.patch
# For bz#810507 - prepare virtio-scsi migration format for multiqueue
Patch3373: kvm-virtio-scsi-prepare-migration-format-for-multiqueue.patch
# For bz#804578 - KVM Guest with virtio network driver loses network connectivity
Patch3374: kvm-virtio-add-missing-mb-on-notification.patch
# For bz#698936 - Migrate failed in different version of RHEL 6.1 host
Patch3375: kvm-qxl-PC_RHEL6_1_COMPAT-make-qxl-default-revision-valu.patch
# For bz#804578 - KVM Guest with virtio network driver loses network connectivity
Patch3376: kvm-virtio-add-missing-mb-on-enable-notification.patch
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3377: kvm-block-make-bdrv_append-assert-that-dirty_bitmap-is-N.patch
# For bz#813810 - plug small race window at the end of block_stream command
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3378: kvm-mirror-remove-need-for-bdrv_drain_all-in-block_job_c.patch
# For bz#813810 - plug small race window at the end of block_stream command
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3379: kvm-block-add-block_job_sleep.patch
# For bz#813810 - plug small race window at the end of block_stream command
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3380: kvm-block-wait-for-job-callback-in-block_job_cancel_sync.patch
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3381: kvm-block-drive-reopen-fixes.patch
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3382: kvm-block-drive-mirror-fixes.patch
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3383: kvm-block-remove-duplicate-check-in-qmp_transaction.patch
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3384: kvm-mirror-do-not-reset-sector_num.patch
# For bz#798676 - do not use next  as a variable name in qemu-kvm systemtap tapset
Patch3385: kvm-trace-events-Rename-next-argument.patch
# For bz#814617 - NFS performance regression in large file sequential writes.
Patch3386: kvm-Revert-raw-posix-do-not-linearize-anymore-direct-I-O.patch
Patch3387: kvm-qcow2-Don-t-hold-cache-references-across-yield.patch
# For bz#787974 - Spice Client mouse loss after live migrate windows guest with spice vmc channel and inactive guest service
Patch3388: kvm-virtio-serial-bus-fix-guest_connected-init-before-dr.patch
# For bz#787974 - Spice Client mouse loss after live migrate windows guest with spice vmc channel and inactive guest service
Patch3389: kvm-virtio-serial-bus-Unset-guest_connected-at-reset-and.patch
# For bz#813953 - block-job-set-speed is racy with block-stream/drive-mirror
Patch3390: kvm-block-change-block-job-set-speed-argument-from-value.patch
# For bz#813953 - block-job-set-speed is racy with block-stream/drive-mirror
Patch3391: kvm-block-add-speed-optional-parameter-to-block-stream.patch
# For bz#818226 - Weird check for null pointer in mirror_abort()
Patch3392: kvm-fix-mirror_abort-NULL-pointer-dereference.patch
# For bz#813862 - post-snap1 fixups to live block copy aka mirroring
Patch3393: kvm-fail-drive-reopen-before-reaching-mirroring-steady-s.patch
# For bz#816471 - qemu-kvm is not closing the merged images files (mirroring with "full"=true)
Patch3394: kvm-block-do-not-reuse-the-backing-file-across-bdrv_clos.patch
# For bz#818876 - streaming to stable iscsi path names (with colons) fails to close backing file
Patch3395: kvm-block-Introduce-path_has_protocol-function.patch
# For bz#818876 - streaming to stable iscsi path names (with colons) fails to close backing file
Patch3396: kvm-block-Fix-the-use-of-protocols-in-backing-files.patch
# For bz#818876 - streaming to stable iscsi path names (with colons) fails to close backing file
Patch3397: kvm-block-simplify-path_is_absolute.patch
# For bz#818876 - streaming to stable iscsi path names (with colons) fails to close backing file
Patch3398: kvm-block-protect-path_has_protocol-from-filenames-with-.patch
# For bz#818876 - streaming to stable iscsi path names (with colons) fails to close backing file
Patch3399: kvm-qemu-img-make-info-backing-file-output-correct-and-e.patch
# For bz#698936 - Migrate failed from RHEL6.1 host to RHEL6.3 host with -M rhel6.1.0 (qxl and usb device related)
Patch3400: kvm-qxl-set-size-of-PCI-IO-BAR-correctly-16-for-revision.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3401: kvm-scsi-fix-fw-p1-take2.patch
# For bz#782029 - [RFE] virtio-scsi: qemu-kvm implementation
Patch3402: kvm-scsi-fix-fw-p2-take2.patch
# For bz#806432 - Review the design/code of the blkmirror block driver
Patch3403: kvm-remove-blkmirror-take2.patch
# For bz#819562 - SMEP is enabled unconditionally
Patch3404: kvm-x86-Pass-KVMState-to-kvm_arch_get_supported_cpui.patch
# For bz#819562 - SMEP is enabled unconditionally
Patch3405: kvm-Expose-CPUID-leaf-7-only-for-cpu-host-v2.patch
# For bz#836498 - oad KVM modules in postinstall scriptlet
Patch3406: kvm-isa-bus-Remove-bogus-IRQ-sharing-check.patch
# For bz#806768 - -qmp stdio is unusable
Patch3407: kvm-remove-broken-code-for-tty.patch
# For bz#806768 - -qmp stdio is unusable
Patch3408: kvm-add-qemu_chr_set_echo.patch
# For bz#806768 - -qmp stdio is unusable
Patch3409: kvm-move-atexit-term_exit-and-O_NONBLOCK-to-qemu_chr_ope.patch
# For bz#806768 - -qmp stdio is unusable
Patch3410: kvm-add-set_echo-implementation-for-qemu_chr_stdio.patch
# For bz#814102 - mirroring starts anyway with "existing" mode and a non-existing target
Patch3411: kvm-block-don-t-create-mirror-block-job-if-the-target-bd.patch
# For bz#821692 - Migration always failed from rhel6.3 to rhel6.1 host with sound device
Patch3412: kvm-hda-audio-send-v1-migration-format-for-rhel6.1.0.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3413: kvm-Revert-qemu-ga-make-guest-suspend-posix-only.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3414: kvm-qemu-ga-win32-add-guest-suspend-stubs.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3415: kvm-qemu-ga-Fix-spelling-in-documentation.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3416: kvm-qemu-ga-add-win32-guest-suspend-disk-command.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3417: kvm-configure-fix-mingw32-libs_qga-typo.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3418: kvm-qemu-ga-add-win32-guest-suspend-ram-command.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3419: kvm-qemu-ga-add-guest-network-get-interfaces-command.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3420: kvm-qemu-ga-qmp_guest_network_get_interfaces-Use-qemu_ma.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3421: kvm-qemu-ga-add-guest-sync-delimited.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3422: kvm-qemu-ga-for-w32-fix-leaked-handle-ov.hEvent-in-ga_ch.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3423: kvm-qemu-ga-fix-bsd-build-and-re-org-linux-specific-impl.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3424: kvm-qemu-ga-generate-missing-stubs-for-fsfreeze.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3425: kvm-qemu-ga-fix-help-output.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3426: kvm-qemu-ga-guest_fsfreeze_build_mount_list-use-g_malloc.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3427: kvm-qemu-ga-improve-recovery-options-for-fsfreeze.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3428: kvm-qemu-ga-add-a-whitelist-for-fsfreeze-safe-commands.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3429: kvm-qemu-ga-persist-tracking-of-fsfreeze-state-via-files.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3430: kvm-qemu-ga-Implement-alternative-to-O_ASYNC.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3431: kvm-qemu-ga-fix-some-common-typos.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3432: kvm-qapi-add-support-for-command-options.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3433: kvm-qemu-ga-don-t-warn-on-no-command-return.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3434: kvm-qemu-ga-guest-shutdown-don-t-emit-a-success-response.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3435: kvm-qemu-ga-guest-suspend-disk-don-t-emit-a-success-resp.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3436: kvm-qemu-ga-guest-suspend-ram-don-t-emit-a-success-respo.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3437: kvm-qemu-ga-guest-suspend-hybrid-don-t-emit-a-success-re.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3438: kvm-qemu-ga-make-reopen_fd_to_null-public.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3439: kvm-qemu-ga-become_daemon-reopen-standard-fds-to-dev-nul.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3440: kvm-qemu-ga-guest-suspend-make-the-API-synchronous.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3441: kvm-qemu-ga-guest-shutdown-become-synchronous.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3442: kvm-qemu-ga-guest-shutdown-use-only-async-signal-safe-fu.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3443: kvm-qemu-ga-fix-segv-after-failure-to-open-log-file.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3444: kvm-configure-check-if-environ-is-declared.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3445: kvm-qemu-ga-Fix-missing-environ-declaration.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3446: kvm-qemu-ga-Fix-use-of-environ-on-Darwin.patch
# For bz#827612 - Update qemu-ga to its latest upstream version
Patch3447: kvm-qemu-ga-avoid-blocking-on-atime-update-when-reading-.patch
# For bz#819900 - [6.3 FEAT] add guest-file-* operations into posix qemu-ga
Patch3448: kvm-Revert-guest-agent-remove-unsupported-guest-agent-co.patch
# For bz#839156 - Fedora 16 and 17 guests hang during boot
Patch3449: kvm-virtio-console-Fix-failure-on-unconnected-pty.patch
# For bz#825188 - make scsi-testsuite pass
Patch3450: kvm-scsi-do-not-require-a-minimum-allocation-length-for-.patch
# For bz#825188 - make scsi-testsuite pass
Patch3451: kvm-scsi-set-VALID-bit-to-0-in-fixed-format-sense-data.patch
# For bz#825188 - make scsi-testsuite pass
Patch3452: kvm-scsi-do-not-report-bogus-overruns-for-commands-in-th.patch
# For bz#825188 - make scsi-testsuite pass
Patch3453: kvm-scsi-do-not-require-a-minimum-allocation-length-2.patch
# For bz#825188 - make scsi-testsuite pass
Patch3454: kvm-scsi-remove-useless-debug-messages.patch
# For bz#796043 - 'getaddrinfo(127.0.0.1,5902): Name or service not known' when starting guest on host with IPv6 only
Patch3455: kvm-vnc-add-a-more-descriptive-error-message.patch
# For bz#797728 - qemu-kvm allows a value of -1 for uint32 qdev property types
Patch3456: kvm-qdev-properties-restrict-uint32-input-values-between.patch
# For bz#643577 - Lost packet during bonding test with e1000 nic
Patch3457: kvm-e1000-use-MII-status-register-for-link-up-down.patch
# For bz#784496 - Device assignment doesn't get updated for guest irq pinning
Patch3458: kvm-pci-assign-Use-struct-for-MSI-X-table.patch
# For bz#784496 - Device assignment doesn't get updated for guest irq pinning
Patch3459: kvm-pci-assign-Only-calculate-maximum-MSI-X-vector-entri.patch
# For bz#784496 - Device assignment doesn't get updated for guest irq pinning
Patch3460: kvm-pci-assign-Proper-initialization-for-MSI-X-table.patch
# For bz#784496 - Device assignment doesn't get updated for guest irq pinning
Patch3461: kvm-pci-assign-Allocate-entries-for-all-MSI-X-vectors.patch
# For bz#784496 - Device assignment doesn't get updated for guest irq pinning
Patch3462: kvm-pci-assign-Update-MSI-X-config-based-on-table-writes.patch
# For bz#808653 - Audio quality is very bad when playing audio via passthroughed USB speaker in guest
# For bz#831549 - unmount of usb storage in RHEL guest takes around 50mins
Patch3463: kvm-audio-streaming-from-usb-devices.patch
# For bz#808653 - Audio quality is very bad when playing audio via passthroughed USB speaker in guest
# For bz#831549 - unmount of usb storage in RHEL guest takes around 50mins
Patch3464: kvm-usb-uhci-fix-commit-8e65b7c04965c8355e4ce43211582b6b.patch
# For bz#808653 - Audio quality is very bad when playing audio via passthroughed USB speaker in guest
# For bz#831549 - unmount of usb storage in RHEL guest takes around 50mins
Patch3465: kvm-usb-uhci-fix-expire-time-initialization.patch
# For bz#808653 - Audio quality is very bad when playing audio via passthroughed USB speaker in guest
# For bz#831549 - unmount of usb storage in RHEL guest takes around 50mins
Patch3466: kvm-usb-uhci-implement-bandwidth-management.patch
# For bz#808653 - Audio quality is very bad when playing audio via passthroughed USB speaker in guest
# For bz#831549 - unmount of usb storage in RHEL guest takes around 50mins
Patch3467: kvm-uhci-fix-bandwidth-management.patch
# For bz#729244 - floppy does not show in guest after change floppy from no inserted to new file
Patch3468: kvm-fdc-DIR-Digital-Input-Register-should-return-status-.patch
# For bz#729244 - floppy does not show in guest after change floppy from no inserted to new file
Patch3469: kvm-fdc-simplify-media-change-handling.patch
# For bz#729244 - floppy does not show in guest after change floppy from no inserted to new file
Patch3470: kvm-fdc-fix-media-detection.patch
# For bz#729244 - floppy does not show in guest after change floppy from no inserted to new file
Patch3471: kvm-fdc-fix-implied-seek-while-there-is-no-media-in-driv.patch
# For bz#729244 - floppy does not show in guest after change floppy from no inserted to new file
Patch3472: kvm-fdc-rewrite-seek-and-DSKCHG-bit-handling.patch
# For bz#729244 - floppy does not show in guest after change floppy from no inserted to new file
Patch3473: kvm-fdc-fix-interrupt-handling.patch
# For bz#794653 - Finnish keymap has errors
Patch3474: kvm-qemu-keymaps-Finnish-keyboard-mapping-broken.patch
# For bz#807391 - lost hotplug events
Patch3475: kvm-acpi_piix4-Disallow-write-to-up-down-PCI-hotplug-reg.patch
# For bz#807391 - lost hotplug events
Patch3476: kvm-acpi_piix4-Fix-PCI-hotplug-race.patch
# For bz#807391 - lost hotplug events
Patch3477: kvm-acpi_piix4-Remove-PCI_RMV_BASE-write-code.patch
# For bz#807391 - lost hotplug events
Patch3478: kvm-acpi_piix4-Re-define-PCI-hotplug-eject-register-read.patch
# For bz#807391 - lost hotplug events
Patch3479: kvm-acpi-explicitly-account-for-1-device-per-slot.patch
# For bz#813633 - need to update qemu-kvm about "-vnc" option for "password" in man page
Patch3480: kvm-qemu-options.hx-Fix-set_password-and-expire_password.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3481: kvm-e1000-Pad-short-frames-to-minimum-size-60-bytes.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3482: kvm-e1000-Fix-multi-descriptor-packet-checksum-offload.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3483: kvm-e1000-introduce-bits-of-PHY-control-register.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3484: kvm-e1000-conditionally-raise-irq-at-the-end-of-MDI-cycl.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3485: kvm-e1000-Preserve-link-state-across-device-reset.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3486: kvm-e1000-move-reset-function-earlier-in-file.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3487: kvm-e1000-introduce-helpers-to-manipulate-link-status.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3488: kvm-e1000-introduce-bit-for-debugging-PHY-emulation.patch
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#607510 - Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000
# For bz#819915 - e1000: Fix multi-descriptor packet checksum offload
Patch3489: kvm-e1000-link-auto-negotiation-emulation.patch
# For bz#831614 - [6.4 FEAT] KVM suppress cpu softlockup message after suspend/resume of a VM
Patch3490: kvm-kvmclock-guest-stop-notification.patch
# For bz#839957 - usb-storage: SYNCHRONIZE_CACHE is broken
Patch3491: kvm-usb-storage-fix-SYNCHRONIZE_CACHE.patch
# For bz#813713 - Windows guest can't drive more than 21 usb-storage devices
Patch3492: kvm-usb-change-VID-PID-for-usb-hub-and-usb-msd-to-preven.patch
# For bz#813713 - Windows guest can't drive more than 21 usb-storage devices
Patch3493: kvm-usb-add-serial-number-generator.patch
# For bz#813713 - Windows guest can't drive more than 21 usb-storage devices
Patch3494: kvm-add-rhel6.4.0-machine-type.patch
# For bz#813713 - Windows guest can't drive more than 21 usb-storage devices
Patch3495: kvm-usb-add-compat-property-to-skip-unique-serial-number.patch
# For bz#846954 - qemu-img convert segfaults on zeroed image
Patch3496: kvm-qemu-img-Fix-segmentation-fault.patch
# For bz#816575 - backing clusters of the image convert with -B  are allocated when they shouldn't
Patch3497: kvm-qemu-img-Fix-qemu-img-convert-obacking_file.patch
# For bz#801063 - [RFE] Ability to configure sound pass-through to appear as MIC as opposed to line-in
Patch3498: kvm-hda-move-input-widgets-from-duplex-to-common.patch
# For bz#801063 - [RFE] Ability to configure sound pass-through to appear as MIC as opposed to line-in
Patch3499: kvm-hda-add-hda-micro-codec.patch
# For bz#801063 - [RFE] Ability to configure sound pass-through to appear as MIC as opposed to line-in
Patch3500: kvm-hda-fix-codec-ids.patch
# For bz#851258 - EMBARGOED CVE-2012-3515 qemu: VT100 emulation vulnerability [rhel-6.4]
Patch3501: kvm-console-bounds-check-whenever-changing-the-cursor-du.patch
# For bz#851143 - qemu-kvm segfaulting when running a VM
Patch3502: kvm-qxl-render-fix-broken-vnc-spice-since-commit-f934493.patch
# For bz#805501 - qemu-kvm core dumped while sending system_reset to a virtio-scsi guest
# For bz#805501, - qemu-kvm core dumped while sending system_reset to a virtio-scsi guest
# For bz#808664 - With virtio-scsi disk guest can't resume form "No space left on device"
Patch3503: kvm-scsi-add-missing-test-for-cancelled-request.patch
# For bz#814084 - scsi disk emulation doesn't enforce FUA (Force Unit Access) on writes
Patch3504: kvm-scsi-make-code-more-homogeneous-in-AIO-callback-func.patch
# For bz#814084 - scsi disk emulation doesn't enforce FUA (Force Unit Access) on writes
Patch3505: kvm-scsi-move-scsi_flush_complete-around.patch
# For bz#814084 - scsi disk emulation doesn't enforce FUA (Force Unit Access) on writes
Patch3506: kvm-scsi-add-support-for-FUA-on-writes.patch
# For bz#808664 - With virtio-scsi disk guest can't resume form "No space left on device"
# For bz#808664, - With virtio-scsi disk guest can't resume form "No space left on device"
# For bz#805501 - qemu-kvm core dumped while sending system_reset to a virtio-scsi guest
Patch3507: kvm-scsi-force-unit-access-on-VERIFY.patch
# For bz#808664 - With virtio-scsi disk guest can't resume form "No space left on device"
# For bz#808664, - With virtio-scsi disk guest can't resume form "No space left on device"
# For bz#805501 - qemu-kvm core dumped while sending system_reset to a virtio-scsi guest
Patch3508: kvm-scsi-disk-more-assertions-and-resets-for-aiocb.patch
# For bz#808664 - With virtio-scsi disk guest can't resume form "No space left on device"
Patch3509: kvm-virtio-scsi-do-not-compare-32-bit-QEMU-tags-against-.patch
Patch3510: kvm-vvfat-Use-cache-unsafe.patch
Patch3511: kvm-block-prevent-snapshot-mode-TMPDIR-symlink-attack.patch
# For bz#835101 - RFE: backport pv eoi support - qemu-kvm
Patch3512: kvm-pc-refactor-RHEL-compat-code.patch
# For bz#835101 - RFE: backport pv eoi support - qemu-kvm
Patch3513: kvm-cpuid-disable-pv-eoi-for-6.3-and-older-compat-types.patch
# For bz#835101 - RFE: backport pv eoi support - qemu-kvm
Patch3514: kvm-kvm_pv_eoi-add-flag-support.patch
# For bz#836133 - spice migration: prevent race with libvirt
Patch3515: kvm-spice-notify-spice-server-on-vm-start-stop.patch
# For bz#836133 - spice migration: prevent race with libvirt
Patch3516: kvm-spice-notify-on-vm-state-change-only-via-spice_serve.patch
# For bz#836133 - spice migration: prevent race with libvirt
Patch3517: kvm-spice-migration-add-QEVENT_SPICE_MIGRATE_COMPLETED.patch
# For bz#836133 - spice migration: prevent race with libvirt
Patch3518: kvm-spice-add-migrated-flag-to-spice-info.patch
# For bz#836133 - spice migration: prevent race with libvirt
Patch3519: kvm-spice-adding-seamless-migration-option-to-the-comman.patch
# For bz#836133 - spice migration: prevent race with libvirt
Patch3520: kvm-spice-increase-the-verbosity-of-spice-section-in-qem.patch
# For bz#814426 - "rdtscp" flag defined on SandyBridge and Opteron models, but not supported by the kernel
Patch3521: kvm-disable-rdtscp-on-all-CPU-model-definitions.patch
# For bz#817224 - there is no "-nodefaults" option help doc in qemu-kvm man page
Patch3522: kvm-qemu-options.hx-Improve-nodefaults-description.patch
# For bz#850927 - QMP: two events related issues on S3 wakeup
Patch3523: kvm-Allow-silent-system-resets.patch
# For bz#850927 - QMP: two events related issues on S3 wakeup
Patch3524: kvm-qmp-don-t-emit-the-RESET-event-on-wakeup-from-S3.patch
# For bz#850927 - QMP: two events related issues on S3 wakeup
Patch3525: kvm-qmp-emit-the-WAKEUP-event-when-the-guest-is-put-to-r.patch
# For bz#854304 - reset PMBA and PMREGMISC PIIX4 registers
Patch3526: kvm-reset-PMBA-and-PMREGMISC-PIIX4-registers.patch
# For bz#805172 - Add live migration support for USB
Patch3527: kvm-uhci-zap-uhci_pre_save.patch
# For bz#805172 - Add live migration support for USB
Patch3528: kvm-ehci-move-async-schedule-to-bottom-half.patch
# For bz#805172 - Add live migration support for USB
Patch3529: kvm-ehci-schedule-async-bh-on-async-packet-completion.patch
# For bz#805172 - Add live migration support for USB
Patch3530: kvm-ehci-kick-async-schedule-on-wakeup.patch
# For bz#805172 - Add live migration support for USB
Patch3531: kvm-ehci-Kick-async-schedule-on-wakeup-in-the-non-compan.patch
# For bz#805172 - Add live migration support for USB
Patch3532: kvm-ehci-raise-irq-in-the-frame-timer.patch
# For bz#805172 - Add live migration support for USB
Patch3533: kvm-ehci-add-live-migration-support.patch
# For bz#805172 - Add live migration support for USB
Patch3534: kvm-ehci-fix-Interrupt-Threshold-Control-implementation.patch
# For bz#805172 - Add live migration support for USB
Patch3535: kvm-scsi-prepare-migration-code-for-usb-storage-support.patch
# For bz#805172 - Add live migration support for USB
Patch3536: kvm-Endian-fix-an-assertion-in-usb-msd.patch
# For bz#805172 - Add live migration support for USB
Patch3537: kvm-usb-storage-remove-MSDState-residue.patch
# For bz#805172 - Add live migration support for USB
Patch3538: kvm-usb-storage-add-usb_msd_packet_complete.patch
# For bz#805172 - Add live migration support for USB
Patch3539: kvm-usb-storage-add-scsi_off-remove-scsi_buf.patch
# For bz#805172 - Add live migration support for USB
Patch3540: kvm-usb-storage-migration-support.patch
# For bz#805172 - Add live migration support for USB
Patch3541: kvm-usb-storage-DPRINTF-fixup.patch
# For bz#805172 - Add live migration support for USB
Patch3542: kvm-usb-restore-USBDevice-attached-on-vmload.patch
# For bz#805172 - Add live migration support for USB
Patch3543: kvm-usb-host-attach-only-to-running-guest.patch
# For bz#805172 - Add live migration support for USB
Patch3544: kvm-usb-host-live-migration-support.patch
# For bz#818134 - '-writeconfig/-readconfig' option need to update in qemu-kvm manpage
Patch3545: kvm-qemu-options.hx-Improve-read-write-config-options-de.patch
# For bz#846268 - [virtio-win][scsi] Windows guest Core dumped when trying to initialize readonly scsi data disk
Patch3546: kvm-scsi-disk-Fail-medium-writes-with-proper-sense-for-r.patch
# For bz#827503 - Config s3/s4 per VM - in qemu-kvm
Patch3547: kvm-Add-PIIX4-properties-to-control-PM-system-states.patch
# For bz#755594 - -m 1 crashes
Patch3548: kvm-vl-Tighten-parsing-of-m-argument.patch
# For bz#755594 - -m 1 crashes
Patch3549: kvm-vl-Round-argument-of-m-up-to-multiple-of-8KiB.patch
# For bz#755594 - -m 1 crashes
Patch3550: kvm-vl-Round-argument-of-m-up-to-multiple-of-2MiB-instea.patch
# Related to bz#827503
Patch3551: kvm-fix-build-20120912.patch
# For bz#852665 - Backport e1000 receive queue fixes from upstream
Patch3552: kvm-net-notify-iothread-after-flushing-queue.patch
# For bz#852665 - Backport e1000 receive queue fixes from upstream
Patch3553: kvm-e1000-flush-queue-whenever-can_receive-can-go-from-f.patch
# For bz#831708 - Spice-Server, VM Creation works when a bad value is entered for streaming-video
Patch3554: kvm-spice-abort-on-invalid-streaming-cmdline-params.patch
# For bz#849657 - scsi devices see an unit attention condition on migration
Patch3555: kvm-skip-media-change-notify-on-reopen.patch
# For bz#827499 - RFE: QMP notification for S3/S4 events
Patch3556: kvm-qmp-qmp-events.txt-add-missing-doc-for-the-SUSPEND-e.patch
# For bz#827499 - RFE: QMP notification for S3/S4 events
Patch3557: kvm-qmp-add-SUSPEND_DISK-event.patch
# For bz#805172 - Add live migration support for USB
Patch3558: kvm-usb-unique-packet-ids.patch
# For bz#805172 - Add live migration support for USB
Patch3559: kvm-usb-redir-Notify-our-peer-when-we-reject-a-device-du.patch
# For bz#805172 - Add live migration support for USB
Patch3560: kvm-usb-redir-Reset-device-address-and-speed-on-disconne.patch
# For bz#805172 - Add live migration support for USB
Patch3561: kvm-usb-redir-Correctly-handle-the-usb_redir_babble-usbr.patch
# For bz#805172 - Add live migration support for USB
Patch3562: kvm-usb-redir-Never-return-USB_RET_NAK-for-async-handled.patch
# For bz#805172 - Add live migration support for USB
Patch3563: kvm-usb-redir-Don-t-delay-handling-of-open-events-to-a-b.patch
# For bz#805172 - Add live migration support for USB
Patch3564: kvm-usb-redir-Get-rid-of-async-struct-get-member.patch
# For bz#805172 - Add live migration support for USB
Patch3565: kvm-usb-redir-Get-rid-of-local-shadow-copy-of-packet-hea.patch
# For bz#805172 - Add live migration support for USB
Patch3566: kvm-usb-redir-Get-rid-of-unused-async-struct-dev-member.patch
# For bz#805172 - Add live migration support for USB
Patch3567: kvm-usb-redir-Move-to-core-packet-id-handling.patch
# For bz#805172 - Add live migration support for USB
Patch3568: kvm-usb-redir-Return-babble-when-getting-more-bulk-data-.patch
# For bz#805172 - Add live migration support for USB
Patch3569: kvm-usb-redir-Convert-to-new-libusbredirparser-0.5-API.patch
# For bz#848369 - S3/S4 should be disabled by default
Patch3570: kvm-disable-s3-s4-by-default.patch
# For bz#805172 - Add live migration support for USB
Patch3571: kvm-ehci-RHEL-6-only-call-ehci_advance_async_state-ehci-.patch
# For bz#805172 - Add live migration support for USB
Patch3572: kvm-usb-ehci-drop-unused-isoch_pause-variable.patch
# For bz#805172 - Add live migration support for USB
Patch3573: kvm-usb-ehci-Drop-unused-sofv-value.patch
# For bz#805172 - Add live migration support for USB
Patch3574: kvm-usb-ehci-Ensure-frindex-writes-leave-a-valid-frindex.patch
# For bz#805172 - Add live migration support for USB
Patch3575: kvm-ehci-fix-reset.patch
# For bz#805172 - Add live migration support for USB
Patch3576: kvm-ehci-remove-unused-attach_poll_counter.patch
# For bz#805172 - Add live migration support for USB
Patch3577: kvm-ehci-create-ehci_update_frindex.patch
# For bz#805172 - Add live migration support for USB
Patch3578: kvm-ehci-rework-frame-skipping.patch
# For bz#805172 - Add live migration support for USB
Patch3579: kvm-ehci-fix-ehci_qh_do_overlay.patch
# For bz#805172 - Add live migration support for USB
Patch3580: kvm-ehci-fix-td-writeback.patch
# For bz#805172 - Add live migration support for USB
Patch3581: kvm-ehci-Schedule-async-bh-when-IAAD-bit-gets-set.patch
# For bz#805172 - Add live migration support for USB
Patch3582: kvm-ehci-simplify-ehci_state_executing.patch
# For bz#805172 - Add live migration support for USB
Patch3583: kvm-ehci-Properly-report-completed-but-not-yet-processed.patch
# For bz#805172 - Add live migration support for USB
Patch3584: kvm-ehci-Don-t-process-too-much-frames-in-1-timer-tick-v.patch
# For bz#805172 - Add live migration support for USB
Patch3585: kvm-ehci-Don-t-set-seen-to-0-when-removing-unseen-queue-.patch
# For bz#805172 - Add live migration support for USB
Patch3586: kvm-ehci-Walk-async-schedule-before-and-after-migration.patch
# For bz#805172 - Add live migration support for USB
Patch3587: kvm-usb-redir-Set-ep-max_packet_size-if-available.patch
# For bz#805172 - Add live migration support for USB
Patch3588: kvm-usb-redir-Add-a-usbredir_reject_device-helper-functi.patch
# For bz#805172 - Add live migration support for USB
Patch3589: kvm-usb-redir-Change-cancelled-packet-code-into-a-generi.patch
# For bz#805172 - Add live migration support for USB
Patch3590: kvm-usb-redir-Add-an-already_in_flight-packet-id-queue.patch
# For bz#805172 - Add live migration support for USB
Patch3591: kvm-usb-redir-Store-max_packet_size-in-endp_data.patch
# For bz#805172 - Add live migration support for USB
Patch3592: kvm-usb-redir-Add-support-for-migration.patch
# For bz#805172 - Add live migration support for USB
Patch3593: kvm-usb-redir-Add-chardev-open-close-debug-logging.patch
# For bz#807146 - snapshot_blkdev tab completion for device id missing
Patch3594: kvm-monitor-Fix-leakage-during-completion-processing.patch
# For bz#807146 - snapshot_blkdev tab completion for device id missing
Patch3595: kvm-monitor-Fix-command-completion-vs.-boolean-switches.patch
# For bz#835101 - RFE: backport pv eoi support - qemu-kvm
Patch3596: kvm-linux-headers-update-asm-kvm_para.h-to-3.6.patch
# For bz#835101 - RFE: backport pv eoi support - qemu-kvm
Patch3597: kvm-get-set-PV-EOI-MSR.patch
# For bz#835101 - RFE: backport pv eoi support - qemu-kvm
Patch3598: kvm-kill-dead-KVM_UPSTREAM-code.patch
# For bz#841171 - fix parsing of UNMAP command
Patch3599: kvm-scsi-fix-WRITE-SAME-transfer-length-and-direction.patch
# For bz#841171 - fix parsing of UNMAP command
Patch3600: kvm-scsi-Specify-the-xfer-direction-for-UNMAP-commands.patch
# For bz#831102 - add the ability to set a wwn for SCSI disks
Patch3601: kvm-scsi-add-a-qdev-property-for-the-disk-s-WWN.patch
# For bz#831102 - add the ability to set a wwn for SCSI disks
Patch3602: kvm-ide-Adds-wwn-hex-qdev-option.patch
# For bz#832336 - block streaming "explodes" a qcow2 file to the full virtual size of the disk
Patch3603: kvm-stream-do-not-copy-unallocated-sectors-from-the-base.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3604: kvm-x86-cpuid-add-host-to-the-list-of-supported-CPU-mode.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3605: kvm-target-i386-Fold-cpu-cpuid-model-output-into-cpu-hel.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3606: kvm-target-i386-Add-missing-CPUID_-constants.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3607: kvm-target-i386-Move-CPU-models-from-cpus-x86_64.conf-to.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3608: kvm-Eliminate-cpus-x86_64.conf-file-v2.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3609: kvm-target-i386-x86_cpudef_setup-coding-style-change.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3610: kvm-target-i386-Kill-cpudef-config-section-support.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3611: kvm-target-i386-Drop-unused-setscalar-macro.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3612: kvm-target-i386-move-compatibility-static-variables-to-t.patch
# For bz#833152 - per-machine-type CPU models for safe migration
Patch3613: kvm-target-i386-group-declarations-of-compatibility-func.patch
# For bz#745717 - SEP flag is not exposed to guest, but is defined on CPU model config
Patch3614: kvm-disable-SEP-on-all-CPU-models.patch
# For bz#833152 - per-machine-type CPU models for safe migration
# For bz#852083 - qemu-kvm "vPMU passthrough" mode breaks migration, shouldn't be enabled by default
Patch3615: kvm-replace-disable_cpuid_leaf10-with-set_pmu_passthroug.patch
# For bz#852083 - qemu-kvm "vPMU passthrough" mode breaks migration, shouldn't be enabled by default
Patch3616: kvm-enable-PMU-emulation-only-on-cpu-host-v3.patch
# For bz#767944 - [Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm
Patch3617: kvm-expose-tsc-deadline-timer-feature-to-guest.patch
# For bz#767944 - [Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm
Patch3618: kvm-enable-TSC-deadline-on-SandyBridge-CPU-model-on-rhel.patch
# For bz#689665 - Specify the number of cpu cores failed with cpu model Nehalem Penryn and Conroe
Patch3619: kvm-introduce-CPU-model-compat-function-to-set-level-fie.patch
# For bz#689665 - Specify the number of cpu cores failed with cpu model Nehalem Penryn and Conroe
Patch3620: kvm-set-level-4-on-CPU-models-Conroe-Penryn-Nehalem-v2.patch
# For bz#854191 - Add a new boot parameter to set the delay time before rebooting
Patch3621: kvm-convert-boot-to-QemuOpts.patch
# For bz#854191 - Add a new boot parameter to set the delay time before rebooting
Patch3622: kvm-add-a-boot-parameter-to-set-reboot-timeout.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3623: kvm-sockets-Drop-sockets_debug-debug-code.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3624: kvm-sockets-Clean-up-inet_listen_opts-s-convoluted-bind-.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3625: kvm-qerror-add-five-qerror-strings.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3626: kvm-sockets-change-inet_connect-to-support-nonblock-sock.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3627: kvm-sockets-use-error-class-to-pass-listen-error.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3628: kvm-use-inet_listen-inet_connect-to-support-ipv6-migrati.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3629: kvm-socket-clean-up-redundant-assignment.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3630: kvm-net-inet_connect-inet_connect_opts-add-in_progress-a.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3631: kvm-migration-don-t-rely-on-any-QERR_SOCKET_.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3632: kvm-qerror-drop-QERR_SOCKET_CONNECT_IN_PROGRESS.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3633: kvm-Refactor-inet_connect_opts-function.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3634: kvm-Separate-inet_connect-into-inet_connect-blocking-and.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3635: kvm-Fix-address-handling-in-inet_nonblocking_connect.patch
# For bz#680356 - Live migration failed in ipv6 environment
Patch3636: kvm-Clear-handler-only-for-valid-fd.patch
# For bz#767944 - [Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm
Patch3637: kvm-support-TSC-deadline-MSR-with-subsection.patch
# For bz#833687 - manpage says e1000 is the default nic (default is rtl8139)
Patch3638: kvm-doc-correct-default-NIC-to-rtl8139.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3639: kvm-Add-API-to-create-memory-mapping-list.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3640: kvm-exec-add-cpu_physical_memory_is_io.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3641: kvm-target-i386-cpu.h-add-CPUArchState.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3642: kvm-implement-cpu_get_memory_mapping.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3643: kvm-Add-API-to-check-whether-paging-mode-is-enabled.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3644: kvm-Add-API-to-get-memory-mapping.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3645: kvm-Add-API-to-get-memory-mapping-without-do-paging.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3646: kvm-target-i386-Add-API-to-write-elf-notes-to-core-file.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3647: kvm-target-i386-Add-API-to-write-cpu-status-to-core-file.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3648: kvm-target-i386-add-API-to-get-dump-info.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3649: kvm-target-i386-Add-API-to-get-note-s-size.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3650: kvm-make-gdb_id-generally-avialable-and-rename-it-to-cpu.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3651: kvm-hmp.h-include-qdict.h.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3652: kvm-monitor-allow-qapi-and-old-hmp-to-share-the-same-dis.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3653: kvm-introduce-a-new-monitor-command-dump-guest-memory-to.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3654: kvm-qmp-dump-guest-memory-improve-schema-doc.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3655: kvm-qmp-dump-guest-memory-improve-schema-doc-again.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3656: kvm-qmp-dump-guest-memory-don-t-spin-if-non-blocking-fd-.patch
# For bz#832458 - [FEAT RHEL6.4]: Support dump-guest-memory monitor command
Patch3657: kvm-hmp-dump-guest-memory-hardcode-protocol-argument-to-.patch
# For bz#854528 - spice: fix vga mode performance
Patch3658: kvm-spice-switch-to-queue-for-vga-mode-updates.patch
# For bz#854528 - spice: fix vga mode performance
Patch3659: kvm-spice-split-qemu_spice_create_update.patch
# For bz#854528 - spice: fix vga mode performance
Patch3660: kvm-spice-add-screen-mirror.patch
# For bz#854528 - spice: fix vga mode performance
Patch3661: kvm-spice-send-updates-only-for-changed-screen-content.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3662: kvm-tracetool-support-format-strings-containing-parenthe.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3663: kvm-qxl-add-dev-id-to-guest-prints.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3664: kvm-qxl-logger-add-timestamp-to-command-log.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3665: kvm-hw-qxl-Fix-format-string-errors.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3666: kvm-qxl-switch-qxl.c-to-trace-events.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3667: kvm-qxl-better-cleanup-for-surface-destroy.patch
# For bz#820136 - RFE: Improve qxl logging by adding trace-events from upstream
Patch3668: kvm-qxl-qxl_render.c-add-trace-events.patch
# For bz#856422 - qemu-ga: after reboot of frozen fs, guest-fsfreeze-status is wrong
Patch3669: kvm-create_config-separate-section-for-qemu_-dir-variabl.patch
# For bz#856422 - qemu-ga: after reboot of frozen fs, guest-fsfreeze-status is wrong
Patch3670: kvm-configure-add-localstatedir.patch
# For bz#856422 - qemu-ga: after reboot of frozen fs, guest-fsfreeze-status is wrong
Patch3671: kvm-qemu-ga-use-state-dir-from-CONFIG_QEMU_LOCALSTATEDIR.patch
# For bz#856422 - qemu-ga: after reboot of frozen fs, guest-fsfreeze-status is wrong
Patch3672: kvm-qemu-ga-ga_open_pidfile-add-new-line-to-pidfile.patch
# For bz#767944 - [Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm
Patch3673: kvm-add-tsc-deadline-flag-name-to-feature_ecx-table.patch
# For bz#806775 - QMP: add errno information to OpenFileFailed error
Patch3674: kvm-qerror-OpenFileFailed-add-__com.redhat_error_message.patch
# For bz#806775 - QMP: add errno information to OpenFileFailed error
Patch3675: kvm-monitor-memory_save-pass-error-message-to-OpenFileFa.patch
# For bz#806775 - QMP: add errno information to OpenFileFailed error
Patch3676: kvm-dump-qmp_dump_guest_memory-pass-error-message-to-Ope.patch
# For bz#806775 - QMP: add errno information to OpenFileFailed error
Patch3677: kvm-blockdev-do_change_block-pass-error-message-to-OpenF.patch
# For bz#806775 - QMP: add errno information to OpenFileFailed error
Patch3678: kvm-blockdev-qmp_transaction-pass-error-message-to-OpenF.patch
# For bz#806775 - QMP: add errno information to OpenFileFailed error
Patch3679: kvm-blockdev-drive_reopen-pass-error-message-to-OpenFile.patch
# For bz#860017 - [RFE] -spice- Add rendering support in order to improve spice performance
Patch3680: kvm-qxl-Add-set_client_capabilities-interface-to-QXLInte.patch
# For bz#860017 - [RFE] -spice- Add rendering support in order to improve spice performance
Patch3681: kvm-qxl-Ignore-set_client_capabilities-pre-post-migrate.patch
# For bz#860017 - [RFE] -spice- Add rendering support in order to improve spice performance
Patch3682: kvm-qxl-Set-default-revision-to-4.patch
# For bz#843084 - [Intel 6.4 FEAT] Haswell new instructions support for qemu-kvm
Patch3683: kvm-x86-cpuid-add-missing-CPUID-feature-flag-names.patch
# For bz#843084 - [Intel 6.4 FEAT] Haswell new instructions support for qemu-kvm
Patch3684: kvm-x86-Implement-SMEP-and-SMAP.patch
# For bz#843084 - [Intel 6.4 FEAT] Haswell new instructions support for qemu-kvm
Patch3685: kvm-i386-cpu-add-missing-CPUID-EAX-7-ECX-0-flag-names.patch
# For bz#843084 - [Intel 6.4 FEAT] Haswell new instructions support for qemu-kvm
Patch3686: kvm-add-missing-CPUID-bit-constants.patch
# For bz#843084 - [Intel 6.4 FEAT] Haswell new instructions support for qemu-kvm
Patch3687: kvm-add-Haswell-CPU-model.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3688: kvm-scsi-introduce-hotplug-and-hot_unplug-interfaces-for.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3689: kvm-scsi-establish-precedence-levels-for-unit-attention.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3690: kvm-scsi-disk-report-resized-disk-via-sense-codes.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3691: kvm-scsi-report-parameter-changes-to-HBA-drivers.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3692: kvm-virtio-scsi-do-not-crash-on-adding-buffers-to-the-ev.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3693: kvm-virtio-scsi-Implement-hotplug-support-for-virtio-scs.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3694: kvm-virtio-scsi-Report-missed-events.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3695: kvm-virtio-scsi-do-not-report-dropped-events-after-reset.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3696: kvm-virtio-scsi-report-parameter-change-events.patch
# For bz#808660 - RFE - Virtio-scsi should support block_resize
Patch3697: kvm-virtio-scsi-add-backwards-compatibility-properties-f.patch
# For bz#852612 - guest hang if query cpu frequently during pxe boot
Patch3698: kvm-x86-Fix-DPL-write-back-of-segment-registers.patch
# For bz#852612 - guest hang if query cpu frequently during pxe boot
Patch3699: kvm-x86-Remove-obsolete-SS.RPL-DPL-aligment.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3700: kvm-bitmap-add-a-generic-bitmap-and-bitops-library.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3701: kvm-bitops-fix-test_and_change_bit.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3702: kvm-add-hierarchical-bitmap-data-type-and-test-cases.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3703: kvm-block-implement-dirty-bitmap-using-HBitmap.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3704: kvm-block-return-count-of-dirty-sectors-not-chunks.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3705: kvm-block-allow-customizing-the-granularity-of-the-dirty.patch
# For bz#844627 - copy cluster-sized blocks to the target of live storage migration
Patch3706: kvm-mirror-use-target-cluster-size-as-granularity.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3707: kvm-qxl-don-t-abort-on-guest-trigerrable-ring-indices-mi.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3708: kvm-qxl-Slot-sanity-check-in-qxl_phys2virt-is-off-by-one.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3709: kvm-hw-qxl.c-qxl_phys2virt-replace-panics-with-guest_bug.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3710: kvm-qxl-check-for-NULL-return-from-qxl_phys2virt.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3711: kvm-qxl-replace-panic-with-guest-bug-in-qxl_track_comman.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3712: kvm-qxl-qxl_add_memslot-remove-guest-trigerrable-panics.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3713: kvm-qxl-don-t-assert-on-guest-create_guest_primary.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3714: kvm-qxl-Add-missing-GCC_FMT_ATTR-and-fix-format-specifie.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3715: kvm-qxl-ioport_write-remove-guest-trigerrable-abort.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3716: kvm-hw-qxl-s-qxl_guest_bug-qxl_set_guest_bug.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3717: kvm-hw-qxl-ignore-guest-from-guestbug-until-reset.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3718: kvm-qxl-reset-current_async-on-qxl_soft_reset.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3719: kvm-qxl-update_area_io-guest_bug-on-invalid-parameters.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3720: kvm-qxl-disallow-unknown-revisions.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3721: kvm-qxl-add-QXL_IO_MONITORS_CONFIG_ASYNC.patch
# For bz#770842 - RFE: qemu-kvm: qxl device should support multiple monitors
Patch3722: kvm-configure-print-spice-protocol-and-spice-server-vers.patch
# For bz#797227 - qemu guest agent should report error description
Patch3723: kvm-qemu-ga-switch-to-the-new-error-format-on-the-wire.patch
# For bz#852965 - set_link can not change rtl8139 network card's status
Patch3724: kvm-rtl8139-implement-8139cp-link-status.patch
# For bz#852965 - set_link can not change rtl8139 network card's status
Patch3725: kvm-e1000-update-nc.link_down-in-e1000_post_load.patch
# For bz#852965 - set_link can not change rtl8139 network card's status
Patch3726: kvm-virtio-net-update-nc.link_down-in-virtio_net_load.patch
# For bz#854474 - floppy I/O error after do live migration with floppy in used
Patch3727: kvm-fdc-fix-DIR-register-migration.patch
# For bz#854474 - floppy I/O error after do live migration with floppy in used
Patch3728: kvm-fdc-introduce-new-property-migrate_dir.patch
Patch3729: kvm-usb-redir-Change-usbredir_open_chardev-into-usbredir.patch
Patch3730: kvm-usb-redir-Don-t-make-migration-fail-in-none-seamless.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3731: kvm-raw-posix-don-t-assign-bs-read_only.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3732: kvm-block-clarify-the-meaning-of-BDRV_O_NOCACHE.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3733: kvm-qcow2-Update-whole-header-at-once.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3734: kvm-qcow2-Keep-unknown-header-extension-when-rewriting-h.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3735: kvm-block-push-bdrv_change_backing_file-error-checking-u.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3736: kvm-block-update-in-memory-backing-file-and-format.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3737: kvm-stream-fix-ratelimiting-corner-case.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3738: kvm-stream-tweak-usage-of-bdrv_co_is_allocated.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3739: kvm-stream-move-is_allocated_above-to-block.c.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3740: kvm-block-New-bdrv_get_flags.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3741: kvm-block-correctly-set-the-keep_read_only-flag.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3742: kvm-block-Framework-for-reopening-files-safely.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3743: kvm-block-move-aio-initialization-into-a-helper-function.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3744: kvm-block-move-open-flag-parsing-in-raw-block-drivers-to.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3745: kvm-block-use-BDRV_O_NOCACHE-instead-of-s-aligned_buf-in.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3746: kvm-block-purge-s-aligned_buf-and-s-aligned_buf_size-fro.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3747: kvm-cutils-break-fcntl_setfl-out-into-accesible-helper-f.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3748: kvm-block-raw-posix-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3749: kvm-block-raw-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3750: kvm-block-qed-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3751: kvm-block-qcow2-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3752: kvm-block-qcow-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3753: kvm-block-vdi-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3754: kvm-block-vpc-image-file-reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3755: kvm-block-convert-bdrv_commit-to-use-bdrv_reopen.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3756: kvm-block-remove-keep_read_only-flag-from-BlockDriverSta.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3757: kvm-block-after-creating-a-live-snapshot-make-old-image-.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3758: kvm-block-add-support-functions-for-live-commit-to-find-.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3759: kvm-qerror-add-QERR_INVALID_PARAMETER_COMBINATION.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3760: kvm-qerror-Error-types-for-block-commit.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3761: kvm-block-add-live-block-commit-functionality.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3762: kvm-block-helper-function-to-find-the-base-image-of-a-ch.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3763: kvm-QAPI-add-command-for-live-block-commit-block-commit.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3764: kvm-block-make-bdrv_find_backing_image-compare-canonical.patch
# For bz#767233 - RFE - Support advanced (bi-directional) live deletion / merge of snapshots
Patch3765: kvm-block-in-commit-determine-base-image-from-the-top-im.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3766: kvm-Introduce-machine-command-option.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3767: kvm-Generalize-machine-command-line-option.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3768: kvm-Allow-to-leave-type-on-default-in-machine.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3769: kvm-qemu-option-Introduce-default-mechanism.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3770: kvm-qemu-option-Add-support-for-merged-QemuOptsLists.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3771: kvm-Make-machine-enable-kvm-options-merge-into-a-single-.patch
# For bz#859447 - [Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process
Patch3772: kvm-memory-add-machine-dump-guest-core-on-off.patch
# For bz#866736 - [hck][svvp] PCI Hardware Compliance Test for Systems job failed when e1000 is in use
Patch3773: kvm-e1000-switch-to-symbolic-names-for-pci-registers.patch
# For bz#866736 - [hck][svvp] PCI Hardware Compliance Test for Systems job failed when e1000 is in use
Patch3774: kvm-pci-interrupt-pin-documentation-update.patch
# For bz#866736 - [hck][svvp] PCI Hardware Compliance Test for Systems job failed when e1000 is in use
Patch3775: kvm-e1000-Don-t-set-the-Capabilities-List-bit.patch
# For bz#867983 - qemu-ga: empty reason string for OpenFileFailed error
Patch3776: kvm-qemu-ga-pass-error-message-to-OpenFileFailed-error.patch
# For bz#831102 - add the ability to set a wwn for SCSI disks
Patch3777: kvm-scsi-simplify-handling-of-the-VPD-page-length-field.patch
# For bz#831102 - add the ability to set a wwn for SCSI disks
Patch3778: kvm-scsi-block-remove-properties-that-are-not-relevant-f.patch
# For bz#831102 - add the ability to set a wwn for SCSI disks
Patch3779: kvm-scsi-more-fixes-to-properties-for-passthrough-device.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3780: kvm-Fixes-related-to-processing-of-qemu-s-numa-option.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3781: kvm-create-kvm_arch_vcpu_id-function.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3782: kvm-target-i386-kvm-set-vcpu_id-to-APIC-ID-instead-of-CP.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3783: kvm-fw_cfg-remove-FW_CFG_MAX_CPUS-from-fw_cfg_init.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3784: kvm-pc-set-CPU-APIC-ID-explicitly.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3785: kvm-pc-set-fw_cfg-data-based-on-APIC-ID-calculation.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3786: kvm-CPU-hotplug-use-apic_id_for_cpu.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3787: kvm-target-i386-topology-and-APIC-ID-utility-functions.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3788: kvm-sysemu.h-add-extern-declarations-for-smp_cores-smp_t.patch
# For bz#733720 - '-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests
Patch3789: kvm-pc-generate-APIC-IDs-according-to-CPU-topology.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3790: kvm-i386-kvm-kvm_arch_get_supported_cpuid-move-R_EDX-hac.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3791: kvm-i386-kvm-kvm_arch_get_supported_cpuid-replace-nested.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3792: kvm-i386-kvm-set-CPUID_EXT_HYPERVISOR-on-kvm_arch_get_su.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3793: kvm-i386-kvm-set-CPUID_EXT_TSC_DEADLINE_TIMER-on-kvm_arc.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3794: kvm-i386-kvm-x2apic-is-not-supported-without-in-kernel-i.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3795: kvm-target-i385-make-cpu_x86_fill_host-void.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3796: kvm-target-i386-cpu-make-cpu-host-check-enforce-code-KVM.patch
# For bz#691638 - x2apic is not exported to guest when boot guest with -cpu host
Patch3797: kvm-target-i386-kvm_cpu_fill_host-use-GET_SUPPORTED_CPUI.patch
Patch3798: kvm-i386-cpu-name-new-CPUID-bits.patch
Patch3799: kvm-x86-cpu-add-new-Opteron-CPU-model.patch
# For bz#860573 - Live migration from rhel6.3 release version to rhel6.4 newest version with 501MB memory in guest will fail
Patch3800: kvm-vl-Fix-cross-version-migration-for-odd-RAM-sizes.patch
# For bz#876534 - [regression] unable to boot from usb-host devices
Patch3801: kvm-usb-host-scan-for-usb-devices-when-the-vm-starts.patch
# For bz#865767 - qemu crashed when rhel6.3 64 bit guest reboots
Patch3802: kvm-qxl-call-dpy_gfx_resize-when-entering-vga-mode.patch
# For bz#877933 - vga: fix bochs alignment issue
Patch3803: kvm-vga-fix-bochs-alignment-issue.patch
# For bz#801196 - Win28k KVM guest on RHEL6.1 BSOD with CLOCK_WATCHDOG_TIMEOUT
Patch3804: kvm-hyper-v-Minimal-hyper-v-support.patch
# For bz#874400 - "rdtscp" flag defined on Opteron_G5 model and cann't be exposed to guest
Patch3805: kvm-remove-rdtscp-flag-from-Opteron_G5-model-definition.patch
# For bz#877339 - fail to commit live snapshot image(lv) to a backing image(lv)
Patch3806: kvm-block-add-bdrv_reopen-support-for-raw-hdev-floppy-an.patch
# For bz#870917 - qcow2: Crash when growing large refcount table
Patch3807: kvm-qcow2-Fix-refcount-table-size-calculation.patch
# For bz#878991 - block-commit functionality should be RHEV-only, and disabled for RHEL
Patch3808: kvm-qapi-disable-block-commit-command-for-rhel.patch
# For bz#869214 - Cpu flag "invpcid" is not exposed to guest on Hashwell host
Patch3809: kvm-Recognize-PCID-feature.patch
# For bz#869214 - Cpu flag "invpcid" is not exposed to guest on Hashwell host
Patch3810: kvm-target-i386-cpu-add-CPUID_EXT_PCID-constant.patch
# For bz#869214 - Cpu flag "invpcid" is not exposed to guest on Hashwell host
Patch3811: kvm-add-PCID-feature-to-Haswell-CPU-model-definition.patch
# For bz#874574 - VM terminates when changing display configuration during migration
Patch3812: kvm-qxl-reload-memslots-after-migration-when-qxl-is-in-U.patch
Patch3813: kvm-add-cscope.-to-.gitignore.patch
Patch3814: kvm-.gitignore-ignore-vi-swap-files-and-ctags-files.patch
Patch3815: kvm-Add-TAGS-and-to-.gitignore.patch
Patch3816: kvm-Revert-hyper-v-Minimal-hyper-v-support.patch
# For bz#733302 - Migration failed with error "warning: error while loading state for instance 0x0 of device '0000:00:02.0/qxl"
Patch3817: kvm-hw-pc-Correctly-order-compatibility-props.patch
# For bz#881732 - vdsm: vdsm is stuck in recovery for almost an hour on NFS storage with running vm's when blocking storage from host
Patch3818: kvm-trace-trace-monitor-qmp-dispatch-completion.patch
# For bz#881732 - vdsm: vdsm is stuck in recovery for almost an hour on NFS storage with running vm's when blocking storage from host
Patch3819: kvm-Add-query-events-command-to-QMP-to-query-async-event.patch
# For bz#881732 - vdsm: vdsm is stuck in recovery for almost an hour on NFS storage with running vm's when blocking storage from host
Patch3820: kvm-Add-event-notification-for-guest-balloon-changes.patch
# For bz#881732 - vdsm: vdsm is stuck in recovery for almost an hour on NFS storage with running vm's when blocking storage from host
Patch3821: kvm-Add-rate-limiting-of-RTC_CHANGE-BALLOON_CHANGE-WATCH.patch
Patch3822: kvm-qxl-vnc-register-a-vm-state-change-handler-for-dummy.patch
Patch3823: kvm-hyper-v-Minimal-hyper-v-support-v5.patch
Patch3824: kvm-audio-split-sample-conversion-and-volume-mixing.patch
Patch3825: kvm-audio-add-VOICE_VOLUME-ctl.patch
Patch3826: kvm-audio-don-t-apply-volume-effect-if-backend-has-VOICE.patch
Patch3827: kvm-hw-ac97-remove-USE_MIXER-code.patch
Patch3828: kvm-hw-ac97-the-volume-mask-is-not-only-0x1f.patch
Patch3829: kvm-hw-ac97-add-support-for-volume-control.patch
Patch3830: kvm-audio-spice-add-support-for-volume-control.patch
Patch3831: kvm-spice-add-new-spice-server-callbacks-to-ui-spice-dis.patch
Patch3832: kvm-vmmouse-add-reset-handler.patch
Patch3833: kvm-vmmouse-fix-queue_size-field-initialization.patch
Patch3834: kvm-hw-vmmouse.c-Disable-vmmouse-after-reboot.patch
Patch3835: kvm-block-Fix-vpc-initialization-of-the-Dynamic-Disk-Hea.patch
Patch3836: kvm-block-vpc-write-checksum-back-to-footer-after-check.patch
# For bz#886798 - Guest should get S3/S4 state according to machine type to avoid cross migration issue
Patch3837: kvm-pc-rhel6-compat-enable-S3-S4-for-6.1-and-lower-machi.patch
# For bz#890288 - use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest
Patch3838: kvm-e1000-no-need-auto-negotiation-if-link-was-down.patch
# For bz#890288 - use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest
Patch3839: kvm-rtl8139-preserve-link-state-across-device-reset.patch
# For bz#886410 - interrupts aren't passed from the Hypervisor to VMs running Mellanox ConnectX3 VFs
# For bz#bz886410 - 
Patch3840: kvm-pci-assign-Enable-MSIX-on-device-to-match-guest.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3841: kvm-raw-posix-add-raw_get_aio_fd-for-virtio-blk-data-pla.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3842: kvm-configure-add-CONFIG_VIRTIO_BLK_DATA_PLANE.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3843: kvm-vhost-make-memory-region-assign-unassign-functions-p.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3844: kvm-dataplane-add-host-memory-mapping-code.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3845: kvm-dataplane-add-virtqueue-vring-code.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3846: kvm-event_notifier-add-event_notifier_set.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3847: kvm-dataplane-add-event-loop.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3848: kvm-dataplane-add-Linux-AIO-request-queue.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3849: kvm-iov-add-iov_discard_front-back-to-remove-data.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3850: kvm-iov-add-qemu_iovec_concat_iov.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3851: kvm-virtio-blk-Turn-drive-serial-into-a-qdev-property.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3852: kvm-virtio-blk-define-VirtIOBlkConf.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3853: kvm-virtio-blk-add-scsi-on-off-to-VirtIOBlkConf.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3854: kvm-dataplane-add-virtio-blk-data-plane-code.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3855: kvm-virtio-blk-add-x-data-plane-on-off-performance-featu.patch
# For bz#877836 - backport virtio-blk data-plane patches
Patch3856: kvm-virtio-pci-fix-virtio_pci_set_guest_notifiers-error-.patch
# For bz#885644 - Memory leak and use after free in qxl_render_update_area_unlocked()
Patch3857: kvm-qxl-save-qemu_create_displaysurface_from-result.patch
# For bz#895392 - fail to initialize the the data disk specified x-data-plane=on via 'Device Manager' in win7 64bit guest
Patch3858: kvm-block-make-qiov_is_aligned-public.patch
# For bz#895392 - fail to initialize the the data disk specified x-data-plane=on via 'Device Manager' in win7 64bit guest
Patch3859: kvm-dataplane-extract-virtio-blk-read-write-processing-i.patch
# For bz#895392 - fail to initialize the the data disk specified x-data-plane=on via 'Device Manager' in win7 64bit guest
Patch3860: kvm-dataplane-handle-misaligned-virtio-blk-requests.patch
# For bz#876982 - Start Windows 7 guest, connect using virt-viewer within seconds guest locks up
Patch3861: kvm-qxl-fix-range-check-for-rev3-io-commands.patch
# For bz#894995 - core dump when install windows guest with x-data-plane=on
Patch3862: kvm-dataplane-avoid-reentrancy-during-virtio_blk_data_pl.patch
# For bz#894995 - core dump when install windows guest with x-data-plane=on
Patch3863: kvm-dataplane-support-viostor-virtio-pci-status-bit-sett.patch
# For bz#869981 - Cross version migration between different host with spice is broken
Patch3864: kvm-qxl-stop-using-non-revision-4-rom-fields-for-revisio.patch
# For bz#869981 - Cross version migration between different host with spice is broken
Patch3865: kvm-qxl-change-rom-size-to-8192.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3866: kvm-Revert-audio-spice-add-support-for-volume-control.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3867: kvm-Revert-hw-ac97-add-support-for-volume-control.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3868: kvm-Revert-hw-ac97-the-volume-mask-is-not-only-0x1f.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3869: kvm-Revert-hw-ac97-remove-USE_MIXER-code.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3870: kvm-Revert-audio-don-t-apply-volume-effect-if-backend-ha.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3871: kvm-Revert-audio-add-VOICE_VOLUME-ctl.patch
# For bz#884253 - Allow control of volume from within Windows Guests (Volume Mixture)
Patch3872: kvm-Revert-audio-split-sample-conversion-and-volume-mixi.patch
# For bz#taskinfo?taskID=5353762 - 
Patch3873: kvm-Revert-e1000-no-need-auto-negotiation-if-link-was-do.patch
# For bz#910842 - CVE-2012-6075  qemu (e1000 device driver): Buffer overflow when processing large packets when SBP and LPE flags are disabled [rhel-6.5]
Patch3874: kvm-e1000-Discard-packets-that-are-too-long-if-SBP-and-L.patch
# For bz#910842 - CVE-2012-6075  qemu (e1000 device driver): Buffer overflow when processing large packets when SBP and LPE flags are disabled [rhel-6.5]
Patch3875: kvm-e1000-Discard-oversized-packets-based-on-SBP-LPE.patch
# For bz#929105 - [RHEL6.4] [regression] qemu-kvm does not enable ioeventfd
Patch3876: kvm-Fix-regression-introduced-by-machine-accel.patch
# For bz#958750 - QMP event shows incorrect balloon value when balloon size is grater than or equal to 4G
Patch3877: kvm-virtio-balloon-fix-integer-overflow-in-BALLOON_CHANG.patch
# For bz#907716 - use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest
# For bz#927591 - use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest
Patch3878: kvm-e1000-fix-link-down-handling-with-auto-negotiation.patch
# For bz#907716 - use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest
# For bz#927591 - use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest
Patch3879: kvm-e1000-unbreak-the-guest-network-when-migration-to-RH.patch
# For bz#957056 - CVE-2013-2007 qemu: guest agent creates files with insecure permissions in deamon mode [rhel-6.4.z]
Patch3880: kvm-reimplement-error_setg-and-error_setg_errno-for-RHEL.patch
# For bz#957056 - CVE-2013-2007 qemu: guest agent creates files with insecure permissions in deamon mode [rhel-6.4.z]
Patch3881: kvm-qga-set-umask-0077-when-daemonizing-CVE-2013-2007.patch
# For bz#957056 - CVE-2013-2007 qemu: guest agent creates files with insecure permissions in deamon mode [rhel-6.4.z]
Patch3882: kvm-qga-distinguish-binary-modes-in-guest_file_open_mode.patch
# For bz#957056 - CVE-2013-2007 qemu: guest agent creates files with insecure permissions in deamon mode [rhel-6.4.z]
Patch3883: kvm-qga-unlink-just-created-guest-file-if-fchmod-or-fdop.patch

Patch9999: CROC.patch

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires: SDL-devel zlib-devel which texi2html gnutls-devel cyrus-sasl-devel
BuildRequires: rsync dev86 iasl
BuildRequires: pciutils-devel
BuildRequires: pulseaudio-libs-devel
BuildRequires: ncurses-devel
BuildRequires: libaio-devel
%if %{with qemu_kvm}
BuildRequires: usbredir-devel >= 0.5

# seamless spice migration needs a recent spice server version
BuildRequires: spice-server-devel >= 0.12.0
%endif

BuildRequires: systemtap-sdt-devel

# 'stap' binary is required by configure detection of systemtap:
BuildRequires: systemtap
BuildRequires: gcc

# If we are building the guest agent, we also are building it for
# windows
%if %{with guest_agent_win32}
BuildRequires: mingw32-gcc mingw32-zlib mingw32-glib2
%endif

Requires(post): /usr/bin/getent
Requires(post): /usr/sbin/groupadd
Requires(post): /usr/sbin/useradd
Requires(post): /sbin/chkconfig
Requires(preun): /sbin/service /sbin/chkconfig
Requires(postun): /sbin/service

Provides: kvm = 85
Obsoletes: kvm < 85
%if %{with qemu_kvm}
Requires: vgabios
Requires: vgabios-qxl
Requires: vgabios-stdvga
Requires: vgabios-vmware
# The fix for qemu-kvm bz#733720 requires a seabios version with the patches
# for seabios bz#851245
Requires: seabios >= 0.6.1.2-20.el6
Requires: /usr/share/gpxe/e1000-0x100e.rom
Requires: /usr/share/gpxe/rtl8029.rom
Requires: /usr/share/gpxe/pcnet32.rom
Requires: /usr/share/gpxe/rtl8139.rom
Requires: /usr/share/gpxe/virtio-net.rom
Requires: /usr/share/sgabios/sgabios.bin
%endif

# fix for CVE-2011-2527 requires newer glibc
Requires: glibc >= 2.12-1.40.el6

# We don't provide vvfat anymore, that is used by older VDSM versions.
Conflicts: vdsm < 4.5

Requires: qemu-img%{?pkgsuffix} = %{epoch}:%{version}-%{release}

%define qemudocdir %{_docdir}/%{name}-%{version}

%description
KVM (for Kernel-based Virtual Machine) is a full virtualization solution
for Linux on x86 hardware.

Using KVM, one can run multiple virtual machines running unmodified Linux
or Windows images. Each virtual machine has private virtualized hardware:
a network card, disk, graphics adapter, etc.

%if %{enable_fake_machine}
NOTE: This package includes a version of qemu-kvm compiled with
--enable-fake-machine, meaning it is usable only for scalability testing of
management code, not to run actual virtual machines.
%endif


%if %{with qemu_kvm}
%package -n qemu-img%{?pkgsuffix}
Summary: QEMU command line tool for manipulating disk images
Group: Development/Tools
Provides: qemu-img%{?pkgsuffix} = %version-%release
%rhel_rhev_conflicts qemu-img

%description -n qemu-img%{?pkgsuffix}
This package provides a command line tool for manipulating disk images

%package -n %{pkgname}-tools
Summary: KVM debugging and diagnostics tools
Group: Development/Tools
Provides: %{pkgname}-tools = %version-%release
%rhel_rhev_conflicts qemu-kvm-tools

%description -n %{pkgname}-tools
This package contains some diagnostics and debugging tools for KVM,
such as kvm_stat.

%endif # with qemu_kvm

%if %{with guest_agent}
%package -n qemu-guest-agent%{?pkgsuffix}
Summary: QEMU Guest Agent
Group: Development/Tools
%rhel_rhev_conflicts qemu-guest-agent

%description -n qemu-guest-agent%{?pkgsuffix}
This package provides a qemu guest agent daemon to be running inside of
linux guests to provide the guest information.

%if %{with guest_agent_win32}
%package -n qemu-guest-agent-win32%{?pkgsuffix}
Summary: QEMU Guest Agent for Windows
Group: Development/Tools
%rhel_rhev_conflicts qemu-guest-agent-win32

%description -n qemu-guest-agent-win32%{?pkgsuffix}
This package provides a qemu guest agent daemon to be running inside of
Windows guests to provide the guest information.
%endif # with guest_agent_win32

%endif # guest_agent

%prep
%setup -q -n qemu-kvm-%{version}

# if patch fuzzy patch applying will be forbidden
%define with_fuzzy_patches 0
%if %{with_fuzzy_patches}
  patch_command='patch -p1 -s'
%else
  patch_command='patch -p1 -F1 -s'
%endif

ApplyPatch()
{
  local patch=$1
  shift
  if [ ! -f $RPM_SOURCE_DIR/$patch ]; then
    exit 1
  fi
  case "$patch" in
  *.bz2) bunzip2 < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *.gz) gunzip < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *) $patch_command ${1+"$@"} < "$RPM_SOURCE_DIR/$patch" ;;
  esac
}

# don't apply patch if it's empty or does not exist
ApplyOptionalPatch()
{
  local patch=$1
  shift
  if [ ! -f $RPM_SOURCE_DIR/$patch ]; then
    return 0
  fi
  local C=$(wc -l $RPM_SOURCE_DIR/$patch | awk '{print $1}')
  if [ "$C" -gt 9 ]; then
    ApplyPatch $patch ${1+"$@"}
  fi
}


%patch1000 -p1
%patch1001 -p1
%patch1002 -p1
%patch1003 -p1
%patch1004 -p1
%patch1005 -p1
%patch1006 -p1
%patch1007 -p1
%patch1008 -p1
%patch1009 -p1
%patch1010 -p1
%patch1011 -p1
%patch1012 -p1
%patch1013 -p1
%patch1014 -p1
%patch1015 -p1
%patch1016 -p1
%patch1017 -p1
%patch1018 -p1
%patch1019 -p1
%patch1020 -p1
%patch1021 -p1
%patch1022 -p1
%patch1023 -p1
%patch1024 -p1
%patch1025 -p1
%patch1026 -p1
%patch1027 -p1
%patch1028 -p1
%patch1029 -p1
%patch1030 -p1
%patch1031 -p1
%patch1032 -p1
%patch1033 -p1
%patch1034 -p1
%patch1035 -p1
%patch1036 -p1
%patch1037 -p1
%patch1038 -p1
%patch1039 -p1
%patch1040 -p1
%patch1041 -p1
%patch1042 -p1
%patch1043 -p1
%patch1044 -p1
%patch1045 -p1
%patch1046 -p1
%patch1047 -p1
%patch1048 -p1
%patch1049 -p1
%patch1050 -p1
%patch1051 -p1
%patch1052 -p1
%patch1053 -p1
%patch1054 -p1
%patch1055 -p1
%patch1056 -p1
%patch1057 -p1
%patch1058 -p1
%patch1059 -p1
%patch1060 -p1
%patch1061 -p1
%patch1062 -p1
%patch1063 -p1
%patch1064 -p1
%patch1065 -p1
%patch1066 -p1
%patch1067 -p1
%patch1068 -p1
%patch1069 -p1
%patch1070 -p1
%patch1071 -p1
%patch1072 -p1
%patch1073 -p1
%patch1074 -p1
%patch1075 -p1
%patch1076 -p1
%patch1077 -p1
%patch1078 -p1
%patch1079 -p1
%patch1080 -p1
%patch1081 -p1
%patch1082 -p1
%patch1083 -p1
%patch1084 -p1
%patch1085 -p1
%patch1086 -p1
%patch1087 -p1
%patch1088 -p1
%patch1089 -p1
%patch1090 -p1
%patch1091 -p1
%patch1092 -p1
%patch1093 -p1
%patch1094 -p1
%patch1095 -p1
%patch1096 -p1
%patch1097 -p1
%patch1098 -p1
%patch1099 -p1
%patch1100 -p1
%patch1101 -p1
%patch1102 -p1
%patch1103 -p1
%patch1104 -p1
%patch1105 -p1
%patch1106 -p1
%patch1107 -p1
%patch1108 -p1
%patch1109 -p1
%patch1110 -p1
%patch1111 -p1
%patch1112 -p1
%patch1113 -p1
%patch1114 -p1
%patch1115 -p1
%patch1116 -p1
%patch1117 -p1
%patch1118 -p1
%patch1119 -p1
%patch1120 -p1
%patch1121 -p1
%patch1122 -p1
%patch1123 -p1
%patch1124 -p1
%patch1125 -p1
%patch1126 -p1
%patch1127 -p1
%patch1128 -p1
%patch1129 -p1
%patch1130 -p1
%patch1131 -p1
%patch1132 -p1
%patch1133 -p1
%patch1134 -p1
%patch1135 -p1
%patch1136 -p1
%patch1137 -p1
%patch1138 -p1
%patch1139 -p1
%patch1140 -p1
%patch1141 -p1
%patch1142 -p1
%patch1143 -p1
%patch1144 -p1
%patch1145 -p1
%patch1146 -p1
%patch1147 -p1
%patch1148 -p1
%patch1149 -p1
%patch1150 -p1
%patch1151 -p1
%patch1152 -p1
%patch1153 -p1
%patch1154 -p1
%patch1155 -p1
%patch1156 -p1
%patch1157 -p1
%patch1158 -p1
%patch1159 -p1
%patch1160 -p1
%patch1161 -p1
%patch1162 -p1
%patch1163 -p1
%patch1164 -p1
%patch1165 -p1
%patch1166 -p1
%patch1167 -p1
%patch1168 -p1
%patch1169 -p1
%patch1170 -p1
%patch1171 -p1
%patch1172 -p1
%patch1173 -p1
%patch1174 -p1
%patch1175 -p1
%patch1176 -p1
%patch1177 -p1
%patch1178 -p1
%patch1179 -p1
%patch1180 -p1
%patch1181 -p1
%patch1182 -p1
%patch1183 -p1
%patch1184 -p1
%patch1185 -p1
%patch1186 -p1
%patch1187 -p1
%patch1188 -p1
%patch1189 -p1
%patch1190 -p1
%patch1191 -p1
%patch1192 -p1
%patch1193 -p1
%patch1194 -p1
%patch1195 -p1
%patch1196 -p1
%patch1197 -p1
%patch1198 -p1
%patch1199 -p1
%patch1200 -p1
%patch1201 -p1
%patch1202 -p1
%patch1203 -p1
%patch1204 -p1
%patch1205 -p1
%patch1206 -p1
%patch1207 -p1
%patch1208 -p1
%patch1209 -p1
%patch1210 -p1
%patch1211 -p1
%patch1212 -p1
%patch1213 -p1
%patch1214 -p1
%patch1215 -p1
%patch1216 -p1
%patch1217 -p1
%patch1218 -p1
%patch1219 -p1
%patch1220 -p1
%patch1221 -p1
%patch1222 -p1
%patch1223 -p1
%patch1224 -p1
%patch1225 -p1
%patch1226 -p1
%patch1227 -p1
%patch1228 -p1
%patch1229 -p1
%patch1230 -p1
%patch1231 -p1
%patch1232 -p1
%patch1233 -p1
%patch1234 -p1
%patch1235 -p1
%patch1236 -p1
%patch1237 -p1
%patch1238 -p1
%patch1239 -p1
%patch1240 -p1
%patch1241 -p1
%patch1242 -p1
%patch1243 -p1
%patch1244 -p1
%patch1245 -p1
%patch1246 -p1
%patch1247 -p1
%patch1248 -p1
%patch1249 -p1
%patch1250 -p1
%patch1251 -p1
%patch1252 -p1
%patch1253 -p1
%patch1254 -p1
%patch1255 -p1
%patch1256 -p1
%patch1257 -p1
%patch1258 -p1
%patch1259 -p1
%patch1260 -p1
%patch1261 -p1
%patch1262 -p1
%patch1263 -p1
%patch1264 -p1
%patch1265 -p1
%patch1266 -p1
%patch1267 -p1
%patch1268 -p1
%patch1269 -p1
%patch1270 -p1
%patch1271 -p1
%patch1272 -p1
%patch1273 -p1
%patch1274 -p1
%patch1275 -p1
%patch1276 -p1
%patch1277 -p1
%patch1278 -p1
%patch1279 -p1
%patch1280 -p1
%patch1281 -p1
%patch1282 -p1
%patch1283 -p1
%patch1284 -p1
%patch1285 -p1
%patch1286 -p1
%patch1287 -p1
%patch1288 -p1
%patch1289 -p1
%patch1290 -p1
%patch1291 -p1
%patch1292 -p1
%patch1293 -p1
%patch1294 -p1
%patch1295 -p1
%patch1296 -p1
%patch1297 -p1
%patch1298 -p1
%patch1299 -p1
%patch1300 -p1
%patch1301 -p1
%patch1302 -p1
%patch1303 -p1
%patch1304 -p1
%patch1305 -p1
%patch1306 -p1
%patch1307 -p1
%patch1308 -p1
%patch1309 -p1
%patch1310 -p1
%patch1311 -p1
%patch1312 -p1
%patch1313 -p1
%patch1314 -p1
%patch1315 -p1
%patch1316 -p1
%patch1317 -p1
%patch1318 -p1
%patch1319 -p1
%patch1320 -p1
%patch1321 -p1
%patch1322 -p1
%patch1323 -p1
%patch1324 -p1
%patch1325 -p1
%patch1326 -p1
%patch1327 -p1
%patch1328 -p1
%patch1329 -p1
%patch1330 -p1
%patch1331 -p1
%patch1332 -p1
%patch1333 -p1
%patch1334 -p1
%patch1335 -p1
%patch1336 -p1
%patch1337 -p1
%patch1338 -p1
%patch1339 -p1
%patch1340 -p1
%patch1341 -p1
%patch1342 -p1
%patch1343 -p1
%patch1344 -p1
%patch1345 -p1
%patch1346 -p1
%patch1347 -p1
%patch1348 -p1
%patch1349 -p1
%patch1350 -p1
%patch1351 -p1
%patch1352 -p1
%patch1353 -p1
%patch1354 -p1
%patch1355 -p1
%patch1356 -p1
%patch1357 -p1
%patch1358 -p1
%patch1359 -p1
%patch1360 -p1
%patch1361 -p1
%patch1362 -p1
%patch1363 -p1
%patch1364 -p1
%patch1365 -p1
%patch1366 -p1
%patch1367 -p1
%patch1368 -p1
%patch1369 -p1
%patch1370 -p1
%patch1371 -p1
%patch1372 -p1
%patch1373 -p1
%patch1374 -p1
%patch1375 -p1
%patch1376 -p1
%patch1377 -p1
%patch1378 -p1
%patch1379 -p1
%patch1380 -p1
%patch1381 -p1
%patch1382 -p1
%patch1383 -p1
%patch1384 -p1
%patch1385 -p1
%patch1386 -p1
%patch1387 -p1
%patch1388 -p1
%patch1389 -p1
%patch1390 -p1
%patch1391 -p1
%patch1392 -p1
%patch1393 -p1
%patch1394 -p1
%patch1395 -p1
%patch1396 -p1
%patch1397 -p1
%patch1398 -p1
%patch1399 -p1
%patch1400 -p1
%patch1401 -p1
%patch1402 -p1
%patch1403 -p1
%patch1404 -p1
%patch1405 -p1
%patch1406 -p1
%patch1407 -p1
%patch1408 -p1
%patch1409 -p1
%patch1410 -p1
%patch1411 -p1
%patch1412 -p1
%patch1413 -p1
%patch1414 -p1
%patch1415 -p1
%patch1416 -p1
%patch1417 -p1
%patch1418 -p1
%patch1419 -p1
%patch1420 -p1
%patch1421 -p1
%patch1422 -p1
%patch1423 -p1
%patch1424 -p1
%patch1425 -p1
%patch1426 -p1
%patch1427 -p1
%patch1428 -p1
%patch1429 -p1
%patch1430 -p1
%patch1431 -p1
%patch1432 -p1
%patch1433 -p1
%patch1434 -p1
%patch1435 -p1
%patch1436 -p1
%patch1437 -p1
%patch1438 -p1
%patch1439 -p1
%patch1440 -p1
%patch1441 -p1
%patch1442 -p1
%patch1443 -p1
%patch1444 -p1
%patch1445 -p1
%patch1446 -p1
%patch1447 -p1
%patch1448 -p1
%patch1449 -p1
%patch1450 -p1
%patch1451 -p1
%patch1452 -p1
%patch1453 -p1
%patch1454 -p1
%patch1455 -p1
%patch1456 -p1
%patch1457 -p1
%patch1458 -p1
%patch1459 -p1
%patch1460 -p1
%patch1461 -p1
%patch1462 -p1
%patch1463 -p1
%patch1464 -p1
%patch1465 -p1
%patch1466 -p1
%patch1467 -p1
%patch1468 -p1
%patch1469 -p1
%patch1470 -p1
%patch1471 -p1
%patch1472 -p1
%patch1473 -p1
%patch1474 -p1
%patch1475 -p1
%patch1476 -p1
%patch1477 -p1
%patch1478 -p1
%patch1479 -p1
%patch1480 -p1
%patch1481 -p1
%patch1482 -p1
%patch1483 -p1
%patch1484 -p1
%patch1485 -p1
%patch1486 -p1
%patch1487 -p1
%patch1488 -p1
%patch1489 -p1
%patch1490 -p1
%patch1491 -p1
%patch1492 -p1
%patch1493 -p1
%patch1494 -p1
%patch1495 -p1
%patch1496 -p1
%patch1497 -p1
%patch1498 -p1
%patch1499 -p1
%patch1500 -p1
%patch1501 -p1
%patch1502 -p1
%patch1503 -p1
%patch1504 -p1
%patch1505 -p1
%patch1506 -p1
%patch1507 -p1
%patch1508 -p1
%patch1509 -p1
%patch1510 -p1
%patch1511 -p1
%patch1513 -p1
%patch1514 -p1
%patch1515 -p1
%patch1516 -p1
%patch1517 -p1
%patch1518 -p1
%patch1519 -p1
%patch1520 -p1
%patch1521 -p1
%patch1522 -p1
%patch1523 -p1
%patch1524 -p1
%patch1525 -p1
%patch1526 -p1
%patch1527 -p1
%patch1528 -p1
%patch1529 -p1
%patch1530 -p1
%patch1531 -p1
%patch1532 -p1
%patch1533 -p1
%patch1534 -p1
%patch1535 -p1
%patch1536 -p1
%patch1537 -p1
%patch1538 -p1
%patch1539 -p1
%patch1540 -p1
%patch1541 -p1
%patch1542 -p1
%patch1543 -p1
%patch1544 -p1
%patch1545 -p1
%patch1546 -p1
%patch1547 -p1
%patch1548 -p1
%patch1549 -p1
%patch1550 -p1
%patch1551 -p1
%patch1552 -p1
%patch1553 -p1
%patch1554 -p1
%patch1555 -p1
%patch1556 -p1
%patch1557 -p1
%patch1558 -p1
%patch1559 -p1
%patch1560 -p1
%patch1561 -p1
%patch1562 -p1
%patch1563 -p1
%patch1564 -p1
%patch1565 -p1
%patch1566 -p1
%patch1567 -p1
%patch1568 -p1
%patch1569 -p1
%patch1570 -p1
%patch1571 -p1
%patch1572 -p1
%patch1573 -p1
%patch1574 -p1
%patch1575 -p1
%patch1576 -p1
%patch1577 -p1
%patch1578 -p1
%patch1579 -p1
%patch1580 -p1
%patch1581 -p1
%patch1582 -p1
%patch1583 -p1
%patch1584 -p1
%patch1585 -p1
%patch1586 -p1
%patch1587 -p1
%patch1588 -p1
%patch1589 -p1
%patch1590 -p1
%patch1591 -p1
%patch1592 -p1
%patch1593 -p1
%patch1594 -p1
%patch1595 -p1
%patch1596 -p1
%patch1597 -p1
%patch1598 -p1
%patch1599 -p1
%patch1600 -p1
%patch1601 -p1
%patch1602 -p1
%patch1603 -p1
%patch1604 -p1
%patch1605 -p1
%patch1606 -p1
%patch1607 -p1
%patch1608 -p1
%patch1609 -p1
%patch1610 -p1
%patch1611 -p1
%patch1612 -p1
%patch1613 -p1
%patch1614 -p1
%patch1615 -p1
%patch1616 -p1
%patch1617 -p1
%patch1618 -p1
%patch1619 -p1
%patch1620 -p1
%patch1621 -p1
%patch1622 -p1
%patch1623 -p1
%patch1624 -p1
%patch1625 -p1
%patch1626 -p1
%patch1627 -p1
%patch1628 -p1
%patch1629 -p1
%patch1630 -p1
%patch1631 -p1
%patch1634 -p1
%patch1635 -p1
%patch1636 -p1
%patch1637 -p1
%patch1638 -p1
%patch1639 -p1
%patch1640 -p1
%patch1641 -p1
%patch1642 -p1
%patch1643 -p1
%patch1644 -p1
%patch1645 -p1
%patch1646 -p1
%patch1647 -p1
%patch1648 -p1
%patch1649 -p1
%patch1650 -p1
%patch1651 -p1
%patch1652 -p1
%patch1653 -p1
%patch1654 -p1
%patch1655 -p1
%patch1656 -p1
%patch1657 -p1
%patch1658 -p1
%patch1659 -p1
%patch1660 -p1
%patch1661 -p1
%patch1662 -p1
%patch1663 -p1
%patch1664 -p1
%patch1665 -p1
%patch1666 -p1
%patch1667 -p1
%patch1668 -p1
%patch1669 -p1
%patch1670 -p1
%patch1671 -p1
%patch1672 -p1
%patch1673 -p1
%patch1674 -p1
%patch1675 -p1
%patch1676 -p1
%patch1677 -p1
%patch1678 -p1
%patch1679 -p1
%patch1680 -p1
%patch1681 -p1
%patch1682 -p1
%patch1683 -p1
%patch1684 -p1
%patch1685 -p1
%patch1686 -p1
%patch1687 -p1
%patch1688 -p1
%patch1689 -p1
%patch1690 -p1
%patch1691 -p1
%patch1692 -p1
%patch1693 -p1
%patch1695 -p1
%patch1696 -p1
%patch1697 -p1
%patch1698 -p1
%patch1699 -p1
%patch1700 -p1
%patch1701 -p1
%patch1702 -p1
%patch1703 -p1
%patch1704 -p1
%patch1705 -p1
%patch1706 -p1
%patch1707 -p1
%patch1708 -p1
%patch1709 -p1
%patch1710 -p1
%patch1711 -p1
%patch1713 -p1
%patch1714 -p1
%patch1715 -p1
%patch1716 -p1
%patch1717 -p1
%patch1718 -p1
%patch1719 -p1
%patch1720 -p1
%patch1721 -p1
%patch1722 -p1
%patch1723 -p1
%patch1724 -p1
%patch1725 -p1
%patch1726 -p1
%patch1727 -p1
%patch1728 -p1
%patch1729 -p1
%patch1730 -p1
%patch1731 -p1
%patch1732 -p1
%patch1733 -p1
%patch1734 -p1
%patch1735 -p1
%patch1736 -p1
%patch1737 -p1
%patch1738 -p1
%patch1739 -p1
%patch1740 -p1
%patch1741 -p1
%patch1742 -p1
%patch1743 -p1
%patch1744 -p1
%patch1745 -p1
%patch1746 -p1
%patch1747 -p1
%patch1748 -p1
%patch1749 -p1
%patch1750 -p1
%patch1751 -p1
%patch1752 -p1
%patch1753 -p1
%patch1754 -p1
%patch1755 -p1
%patch1756 -p1
%patch1757 -p1
%patch1758 -p1
%patch1759 -p1
%patch1760 -p1
%patch1761 -p1
%patch1762 -p1
%patch1763 -p1
%patch1764 -p1
%patch1765 -p1
%patch1766 -p1
%patch1767 -p1
%patch1768 -p1
%patch1769 -p1
%patch1770 -p1
%patch1771 -p1
%patch1772 -p1
%patch1773 -p1
%patch1774 -p1
%patch1775 -p1
%patch1776 -p1
%patch1777 -p1
%patch1778 -p1
%patch1779 -p1
%patch1780 -p1
%patch1781 -p1
%patch1782 -p1
%patch1783 -p1
%patch1784 -p1
%patch1785 -p1
%patch1786 -p1
%patch1787 -p1
%patch1788 -p1
%patch1789 -p1
%patch1790 -p1
%patch1791 -p1
%patch1792 -p1
%patch1793 -p1
%patch1794 -p1
%patch1795 -p1
%patch1796 -p1
%patch1797 -p1
%patch1798 -p1
%patch1799 -p1
%patch1800 -p1
%patch1801 -p1
%patch1802 -p1
%patch1803 -p1
%patch1804 -p1
%patch1805 -p1
%patch1806 -p1
%patch1807 -p1
%patch1808 -p1
%patch1809 -p1
%patch1810 -p1
%patch1811 -p1
%patch1812 -p1
%patch1813 -p1
%patch1814 -p1
%patch1815 -p1
%patch1816 -p1
%patch1817 -p1
%patch1818 -p1
%patch1819 -p1
%patch1820 -p1
%patch1821 -p1
%patch1822 -p1
%patch1823 -p1
%patch1824 -p1
%patch1825 -p1
%patch1826 -p1
%patch1827 -p1
%patch1828 -p1
%patch1829 -p1
%patch1830 -p1
%patch1831 -p1
%patch1832 -p1
%patch1833 -p1
%patch1834 -p1
%patch1835 -p1
%patch1836 -p1
%patch1837 -p1
%patch1838 -p1
%patch1839 -p1
%patch1840 -p1
%patch1841 -p1
%patch1842 -p1
%patch1843 -p1
%patch1844 -p1
%patch1845 -p1
%patch1846 -p1
%patch1847 -p1
%patch1848 -p1
%patch1849 -p1
%patch1850 -p1
%patch1851 -p1
%patch1852 -p1
%patch1853 -p1
%patch1854 -p1
%patch1855 -p1
%patch1856 -p1
%patch1857 -p1
%patch1858 -p1
%patch1859 -p1
%patch1860 -p1
%patch1861 -p1
%patch1862 -p1
%patch1863 -p1
%patch1864 -p1
%patch1865 -p1
%patch1866 -p1
%patch1867 -p1
%patch1868 -p1
%patch1869 -p1
%patch1870 -p1
%patch1871 -p1
%patch1872 -p1
%patch1873 -p1
%patch1874 -p1
%patch1875 -p1
%patch1876 -p1
%patch1877 -p1
%patch1878 -p1
%patch1879 -p1
%patch1880 -p1
%patch1881 -p1
%patch1882 -p1
%patch1883 -p1
%patch1884 -p1
%patch1885 -p1
%patch1886 -p1
%patch1887 -p1
%patch1888 -p1
%patch1889 -p1
%patch1890 -p1
%patch1891 -p1
%patch1892 -p1
%patch1893 -p1
%patch1894 -p1
%patch1895 -p1
%patch1896 -p1
%patch1897 -p1
%patch1898 -p1
%patch1899 -p1
%patch1900 -p1
%patch1901 -p1
%patch1902 -p1
%patch1903 -p1
%patch1904 -p1
%patch1905 -p1
%patch1906 -p1
%patch1907 -p1
%patch1908 -p1
%patch1909 -p1
%patch1910 -p1
%patch1911 -p1
%patch1912 -p1
%patch1913 -p1
%patch1914 -p1
%patch1915 -p1
%patch1916 -p1
%patch1917 -p1
%patch1918 -p1
%patch1919 -p1
%patch1920 -p1
%patch1921 -p1
%patch1922 -p1
%patch1923 -p1
%patch1924 -p1
%patch1925 -p1
%patch1926 -p1
%patch1927 -p1
%patch1928 -p1
%patch1929 -p1
%patch1930 -p1
%patch1931 -p1
%patch1932 -p1
%patch1933 -p1
%patch1934 -p1
%patch1935 -p1
%patch1936 -p1
%patch1937 -p1
%patch1938 -p1
%patch1939 -p1
%patch1940 -p1
%patch1941 -p1
%patch1942 -p1
%patch1943 -p1
%patch1944 -p1
%patch1945 -p1
%patch1946 -p1
%patch1947 -p1
%patch1948 -p1
%patch1949 -p1
%patch1950 -p1
%patch1951 -p1
%patch1952 -p1
%patch1953 -p1
%patch1954 -p1
%patch1955 -p1
%patch1956 -p1
%patch1957 -p1
%patch1958 -p1
%patch1959 -p1
%patch1960 -p1
%patch1961 -p1
%patch1962 -p1
%patch1963 -p1
%patch1964 -p1
%patch1965 -p1
%patch1966 -p1
%patch1967 -p1
%patch1968 -p1
%patch1969 -p1
%patch1970 -p1
%patch1971 -p1
%patch1972 -p1
%patch1973 -p1
%patch1975 -p1
%patch1976 -p1
%patch1977 -p1
%patch1978 -p1
%patch1979 -p1
%patch1980 -p1
%patch1981 -p1
%patch1982 -p1
%patch1983 -p1
%patch1984 -p1
%patch1985 -p1
%patch1986 -p1
%patch1987 -p1
%patch1988 -p1
%patch1989 -p1
%patch1990 -p1
%patch1991 -p1
%patch1992 -p1
%patch1993 -p1
%patch1994 -p1
%patch1995 -p1
%patch1996 -p1
%patch1997 -p1
%patch1998 -p1
%patch1999 -p1
%patch2000 -p1
%patch2001 -p1
%patch2002 -p1
%patch2003 -p1
%patch2004 -p1
%patch2005 -p1
%patch2006 -p1
%patch2007 -p1
%patch2008 -p1
%patch2009 -p1
%patch2010 -p1
%patch2011 -p1
%patch2012 -p1
%patch2013 -p1
%patch2014 -p1
%patch2015 -p1
%patch2016 -p1
%patch2017 -p1
%patch2018 -p1
%patch2019 -p1
%patch2020 -p1
%patch2021 -p1
%patch2022 -p1
%patch2023 -p1
%patch2024 -p1
%patch2025 -p1
%patch2026 -p1
%patch2027 -p1
%patch2028 -p1
%patch2029 -p1
%patch2030 -p1
%patch2031 -p1
%patch2032 -p1
%patch2033 -p1
%patch2034 -p1
%patch2035 -p1
%patch2036 -p1
%patch2037 -p1
%patch2038 -p1
%patch2039 -p1
%patch2040 -p1
%patch2041 -p1
%patch2042 -p1
%patch2043 -p1
%patch2044 -p1
%patch2045 -p1
%patch2046 -p1
%patch2047 -p1
%patch2048 -p1
%patch2050 -p1
%patch2051 -p1
%patch2052 -p1
%patch2053 -p1
%patch2054 -p1
%patch2055 -p1
%patch2056 -p1
%patch2057 -p1
%patch2058 -p1
%patch2059 -p1
%patch2061 -p1
%patch2062 -p1
%patch2063 -p1
%patch2064 -p1
%patch2065 -p1
%patch2066 -p1
%patch2067 -p1
%patch2068 -p1
%patch2069 -p1
%patch2070 -p1
%patch2071 -p1
%patch2072 -p1
%patch2073 -p1
%patch2074 -p1
%patch2075 -p1
%patch2076 -p1
%patch2077 -p1
%patch2078 -p1
%patch2079 -p1
%patch2080 -p1
%patch2081 -p1
%patch2082 -p1
%patch2083 -p1
%patch2084 -p1
%patch2085 -p1
%patch2086 -p1
%patch2087 -p1
%patch2088 -p1
%patch2089 -p1
%patch2090 -p1
%patch2091 -p1
%patch2092 -p1
%patch2093 -p1
%patch2094 -p1
%patch2095 -p1
%patch2096 -p1
%patch2097 -p1
%patch2098 -p1
%patch2099 -p1
%patch2100 -p1
%patch2101 -p1
%patch2102 -p1
%patch2103 -p1
%patch2104 -p1
%patch2105 -p1
%patch2106 -p1
%patch2107 -p1
%patch2108 -p1
%patch2109 -p1
%patch2110 -p1
%patch2111 -p1
%patch2112 -p1
%patch2113 -p1
%patch2114 -p1
%patch2115 -p1
%patch2116 -p1
%patch2117 -p1
%patch2118 -p1
%patch2119 -p1
%patch2120 -p1
%patch2121 -p1
%patch2122 -p1
%patch2123 -p1
%patch2124 -p1
%patch2125 -p1
%patch2126 -p1
%patch2127 -p1
%patch2128 -p1
%patch2129 -p1
%patch2130 -p1
%patch2131 -p1
%patch2132 -p1
%patch2133 -p1
%patch2134 -p1
%patch2135 -p1
%patch2136 -p1
%patch2137 -p1
%patch2138 -p1
%patch2139 -p1
%patch2140 -p1
%patch2141 -p1
%patch2142 -p1
%patch2143 -p1
%patch2144 -p1
%patch2145 -p1
%patch2146 -p1
%patch2147 -p1
%patch2148 -p1
%patch2149 -p1
%patch2150 -p1
%patch2151 -p1
%patch2152 -p1
%patch2153 -p1
%patch2154 -p1
%patch2155 -p1
%patch2156 -p1
%patch2157 -p1
%patch2158 -p1
%patch2159 -p1
%patch2160 -p1
%patch2161 -p1
%patch2162 -p1
%patch2163 -p1
%patch2164 -p1
%patch2165 -p1
%patch2166 -p1
%patch2167 -p1
%patch2168 -p1
%patch2169 -p1
%patch2170 -p1
%patch2171 -p1
%patch2172 -p1
%patch2173 -p1
%patch2174 -p1
%patch2175 -p1
%patch2176 -p1
%patch2177 -p1
%patch2178 -p1
%patch2179 -p1
%patch2180 -p1
%patch2181 -p1
%patch2182 -p1
%patch2183 -p1
%patch2184 -p1
%patch2185 -p1
%patch2186 -p1
%patch2187 -p1
%patch2188 -p1
%patch2189 -p1
%patch2190 -p1
%patch2191 -p1
%patch2192 -p1
%patch2193 -p1
%patch2194 -p1
%patch2195 -p1
%patch2196 -p1
%patch2197 -p1
%patch2198 -p1
%patch2199 -p1
%patch2200 -p1
%patch2201 -p1
%patch2202 -p1
%patch2203 -p1
%patch2204 -p1
%patch2205 -p1
%patch2206 -p1
%patch2207 -p1
%patch2208 -p1
%patch2209 -p1
%patch2210 -p1
%patch2211 -p1
%patch2212 -p1
%patch2213 -p1
%patch2214 -p1
%patch2215 -p1
%patch2216 -p1
%patch2217 -p1
%patch2218 -p1
%patch2219 -p1
%patch2220 -p1
%patch2221 -p1
%patch2222 -p1
%patch2223 -p1
%patch2224 -p1
%patch2225 -p1
%patch2226 -p1
%patch2227 -p1
%patch2228 -p1
%patch2229 -p1
%patch2230 -p1
%patch2231 -p1
%patch2232 -p1
%patch2233 -p1
%patch2234 -p1
%patch2235 -p1
%patch2236 -p1
%patch2237 -p1
%patch2238 -p1
%patch2239 -p1
%patch2240 -p1
%patch2241 -p1
%patch2242 -p1
%patch2243 -p1
%patch2244 -p1
%patch2245 -p1
%patch2246 -p1
%patch2247 -p1
%patch2248 -p1
%patch2249 -p1
%patch2250 -p1
%patch2251 -p1
%patch2252 -p1
%patch2253 -p1
%patch2254 -p1
%patch2255 -p1
%patch2256 -p1
%patch2257 -p1
%patch2258 -p1
%patch2259 -p1
%patch2260 -p1
%patch2261 -p1
%patch2262 -p1
%patch2263 -p1
%patch2264 -p1
%patch2265 -p1
%patch2266 -p1
%patch2267 -p1
%patch2268 -p1
%patch2269 -p1
%patch2270 -p1
%patch2271 -p1
%patch2272 -p1
%patch2273 -p1
%patch2274 -p1
%patch2275 -p1
%patch2276 -p1
%patch2277 -p1
%patch2278 -p1
%patch2279 -p1
%patch2280 -p1
%patch2281 -p1
%patch2282 -p1
%patch2283 -p1
%patch2284 -p1
%patch2285 -p1
%patch2286 -p1
%patch2287 -p1
%patch2288 -p1
%patch2289 -p1
%patch2290 -p1
%patch2291 -p1
%patch2292 -p1
%patch2293 -p1
%patch2294 -p1
%patch2295 -p1
%patch2296 -p1
%patch2297 -p1
%patch2298 -p1
%patch2299 -p1
%patch2300 -p1
%patch2301 -p1
%patch2302 -p1
%patch2303 -p1
%patch2304 -p1
%patch2305 -p1
%patch2306 -p1
%patch2307 -p1
%patch2308 -p1
%patch2309 -p1
%patch2310 -p1
%patch2311 -p1
%patch2312 -p1
%patch2313 -p1
%patch2314 -p1
%patch2315 -p1
%patch2316 -p1
%patch2317 -p1
%patch2318 -p1
%patch2319 -p1
%patch2320 -p1
%patch2321 -p1
%patch2322 -p1
%patch2323 -p1
%patch2324 -p1
%patch2325 -p1
%patch2326 -p1
%patch2327 -p1
%patch2328 -p1
%patch2329 -p1
%patch2330 -p1
%patch2331 -p1
%patch2332 -p1
%patch2333 -p1
%patch2334 -p1
%patch2335 -p1
%patch2336 -p1
%patch2337 -p1
%patch2338 -p1
%patch2339 -p1
%patch2340 -p1
%patch2341 -p1
%patch2342 -p1
%patch2343 -p1
%patch2344 -p1
%patch2345 -p1
%patch2346 -p1
%patch2347 -p1
%patch2348 -p1
%patch2349 -p1
%patch2350 -p1
%patch2351 -p1
%patch2352 -p1
%patch2353 -p1
%patch2354 -p1
%patch2355 -p1
%patch2356 -p1
%patch2357 -p1
%patch2358 -p1
%patch2359 -p1
%patch2360 -p1
%patch2361 -p1
%patch2362 -p1
%patch2363 -p1
%patch2364 -p1
%patch2365 -p1
%patch2366 -p1
%patch2367 -p1
%patch2368 -p1
%patch2369 -p1
%patch2370 -p1
%patch2371 -p1
%patch2372 -p1
%patch2373 -p1
%patch2374 -p1
%patch2375 -p1
%patch2376 -p1
%patch2377 -p1
%patch2378 -p1
%patch2379 -p1
%patch2380 -p1
%patch2381 -p1
%patch2382 -p1
%patch2383 -p1
%patch2384 -p1
%patch2385 -p1
%patch2386 -p1
%patch2387 -p1
%patch2388 -p1
%patch2389 -p1
%patch2390 -p1
%patch2391 -p1
%patch2392 -p1
%patch2393 -p1
%patch2394 -p1
%patch2395 -p1
%patch2396 -p1
%patch2397 -p1
%patch2398 -p1
%patch2399 -p1
%patch2400 -p1
%patch2401 -p1
%patch2402 -p1
%patch2403 -p1
%patch2404 -p1
%patch2405 -p1
%patch2406 -p1
%patch2407 -p1
%patch2408 -p1
%patch2409 -p1
%patch2410 -p1
%patch2411 -p1
%patch2412 -p1
%patch2413 -p1
%patch2414 -p1
%patch2415 -p1
%patch2416 -p1
%patch2417 -p1
%patch2418 -p1
%patch2419 -p1
%patch2420 -p1
%patch2422 -p1
%patch2423 -p1
%patch2424 -p1
%patch2425 -p1
%patch2426 -p1
%patch2427 -p1
%patch2428 -p1
%patch2430 -p1
%patch2431 -p1
%patch2432 -p1
%patch2433 -p1
%patch2434 -p1
%patch2435 -p1
%patch2436 -p1
%patch2437 -p1
%patch2438 -p1
%patch2439 -p1
%patch2440 -p1
%patch2441 -p1
%patch2442 -p1
%patch2443 -p1
%patch2444 -p1
%patch2445 -p1
%patch2446 -p1
%patch2447 -p1
%patch2448 -p1
%patch2449 -p1
%patch2450 -p1
%patch2451 -p1
%patch2452 -p1
%patch2453 -p1
%patch2454 -p1
%patch2455 -p1
%patch2456 -p1
%patch2457 -p1
%patch2458 -p1
%patch2459 -p1
%patch2460 -p1
%patch2461 -p1
%patch2462 -p1
%patch2463 -p1
%patch2464 -p1
%patch2465 -p1
%patch2466 -p1
%patch2467 -p1
%patch2468 -p1
%patch2469 -p1
%patch2470 -p1
%patch2471 -p1
%patch2472 -p1
%patch2473 -p1
%patch2474 -p1
%patch2475 -p1
%patch2476 -p1
%patch2477 -p1
%patch2478 -p1
%patch2479 -p1
%patch2480 -p1
%patch2481 -p1
%patch2482 -p1
%patch2483 -p1
%patch2484 -p1
%patch2485 -p1
%patch2486 -p1
%patch2487 -p1
%patch2488 -p1
%patch2489 -p1
%patch2490 -p1
%patch2491 -p1
%patch2492 -p1
%patch2493 -p1
%patch2494 -p1
%patch2495 -p1
%patch2496 -p1
%patch2497 -p1
%patch2498 -p1
%patch2499 -p1
%patch2500 -p1
%patch2501 -p1
%patch2502 -p1
%patch2503 -p1
%patch2504 -p1
%patch2505 -p1
%patch2506 -p1
%patch2507 -p1
%patch2508 -p1
%patch2509 -p1
%patch2510 -p1
%patch2511 -p1
%patch2512 -p1
%patch2513 -p1
%patch2514 -p1
%patch2515 -p1
%patch2516 -p1
%patch2517 -p1
%patch2518 -p1
%patch2519 -p1
%patch2520 -p1
%patch2521 -p1
%patch2522 -p1
%patch2523 -p1
%patch2524 -p1
%patch2525 -p1
%patch2526 -p1
%patch2527 -p1
%patch2528 -p1
%patch2529 -p1
%patch2530 -p1
%patch2531 -p1
%patch2532 -p1
%patch2533 -p1
%patch2534 -p1
%patch2535 -p1
%patch2536 -p1
%patch2537 -p1
%patch2538 -p1
%patch2539 -p1
%patch2540 -p1
%patch2541 -p1
%patch2542 -p1
%patch2543 -p1
%patch2544 -p1
%patch2545 -p1
%patch2546 -p1
%patch2547 -p1
%patch2548 -p1
%patch2549 -p1
%patch2550 -p1
%patch2551 -p1
%patch2552 -p1
%patch2553 -p1
%patch2554 -p1
%patch2555 -p1
%patch2556 -p1
%patch2557 -p1
%patch2558 -p1
%patch2559 -p1
%patch2560 -p1
%patch2561 -p1
%patch2562 -p1
%patch2563 -p1
%patch2564 -p1
%patch2565 -p1
%patch2566 -p1
%patch2567 -p1
%patch2568 -p1
%patch2569 -p1
%patch2570 -p1
%patch2571 -p1
%patch2572 -p1
%patch2573 -p1
%patch2574 -p1
%patch2575 -p1
%patch2576 -p1
%patch2577 -p1
%patch2578 -p1
%patch2579 -p1
%patch2580 -p1
%patch2581 -p1
%patch2582 -p1
%patch2583 -p1
%patch2584 -p1
%patch2585 -p1
%patch2586 -p1
%patch2587 -p1
%patch2588 -p1
%patch2589 -p1
%patch2590 -p1
%patch2591 -p1
%patch2592 -p1
%patch2593 -p1
%patch2594 -p1
%patch2595 -p1
%patch2596 -p1
%patch2597 -p1
%patch2598 -p1
%patch2599 -p1
%patch2600 -p1
%patch2601 -p1
%patch2602 -p1
%patch2603 -p1
%patch2604 -p1
%patch2605 -p1
%patch2606 -p1
%patch2607 -p1
%patch2608 -p1
%patch2609 -p1
%patch2610 -p1
%patch2611 -p1
%patch2612 -p1
%patch2613 -p1
%patch2614 -p1
%patch2615 -p1
%patch2616 -p1
%patch2617 -p1
%patch2618 -p1
%patch2619 -p1
%patch2620 -p1
%patch2621 -p1
%patch2622 -p1
%patch2623 -p1
%patch2624 -p1
%patch2625 -p1
%patch2626 -p1
%patch2627 -p1
%patch2628 -p1
%patch2629 -p1
%patch2630 -p1
%patch2631 -p1
%patch2632 -p1
%patch2633 -p1
%patch2634 -p1
%patch2635 -p1
%patch2636 -p1
%patch2637 -p1
%patch2638 -p1
%patch2639 -p1
%patch2640 -p1
%patch2641 -p1
%patch2642 -p1
%patch2643 -p1
%patch2644 -p1
%patch2645 -p1
%patch2646 -p1
%patch2647 -p1
%patch2648 -p1
%patch2649 -p1
%patch2650 -p1
%patch2651 -p1
%patch2652 -p1
%patch2653 -p1
%patch2654 -p1
%patch2655 -p1
%patch2656 -p1
%patch2657 -p1
%patch2658 -p1
%patch2659 -p1
%patch2660 -p1
%patch2661 -p1
%patch2662 -p1
%patch2663 -p1
%patch2664 -p1
%patch2665 -p1
%patch2666 -p1
%patch2667 -p1
%patch2668 -p1
%patch2669 -p1
%patch2670 -p1
%patch2671 -p1
%patch2672 -p1
%patch2673 -p1
%patch2674 -p1
%patch2675 -p1
%patch2676 -p1
%patch2677 -p1
%patch2678 -p1
%patch2679 -p1
%patch2680 -p1
%patch2681 -p1
%patch2682 -p1
%patch2683 -p1
%patch2684 -p1
%patch2685 -p1
%patch2686 -p1
%patch2687 -p1
%patch2688 -p1
%patch2689 -p1
%patch2690 -p1
%patch2691 -p1
%patch2692 -p1
%patch2693 -p1
%patch2694 -p1
%patch2695 -p1
%patch2696 -p1
%patch2697 -p1
%patch2698 -p1
%patch2699 -p1
%patch2700 -p1
%patch2701 -p1
%patch2702 -p1
%patch2703 -p1
%patch2704 -p1
%patch2705 -p1
%patch2706 -p1
%patch2707 -p1
%patch2708 -p1
%patch2709 -p1
%patch2710 -p1
%patch2711 -p1
%patch2712 -p1
%patch2713 -p1
%patch2714 -p1
%patch2715 -p1
%patch2716 -p1
%patch2717 -p1
%patch2718 -p1
%patch2719 -p1
%patch2720 -p1
%patch2721 -p1
%patch2722 -p1
%patch2723 -p1
%patch2724 -p1
%patch2725 -p1
%patch2726 -p1
%patch2727 -p1
%patch2728 -p1
%patch2729 -p1
%patch2730 -p1
%patch2731 -p1
%patch2732 -p1
%patch2733 -p1
%patch2734 -p1
%patch2735 -p1
%patch2736 -p1
%patch2737 -p1
%patch2738 -p1
%patch2739 -p1
%patch2740 -p1
%patch2741 -p1
%patch2742 -p1
%patch2743 -p1
%patch2744 -p1
%patch2745 -p1
%patch2746 -p1
%patch2747 -p1
%patch2748 -p1
%patch2749 -p1
%patch2750 -p1
%patch2751 -p1
%patch2752 -p1
%patch2753 -p1
%patch2754 -p1
%patch2755 -p1
%patch2756 -p1
%patch2757 -p1
%patch2758 -p1
%patch2759 -p1
%patch2760 -p1
%patch2761 -p1
%patch2762 -p1
%patch2763 -p1
%patch2764 -p1
%patch2765 -p1
%patch2766 -p1
%patch2767 -p1
%patch2768 -p1
%patch2769 -p1
%patch2770 -p1
%patch2771 -p1
%patch2772 -p1
%patch2773 -p1
%patch2774 -p1
%patch2775 -p1
%patch2776 -p1
%patch2777 -p1
%patch2778 -p1
%patch2779 -p1
%patch2780 -p1
%patch2781 -p1
%patch2782 -p1
%patch2783 -p1
%patch2784 -p1
%patch2785 -p1
%patch2786 -p1
%patch2787 -p1
%patch2788 -p1
%patch2789 -p1
%patch2790 -p1
%patch2791 -p1
%patch2792 -p1
%patch2793 -p1
%patch2794 -p1
%patch2795 -p1
%patch2796 -p1
%patch2797 -p1
%patch2798 -p1
%patch2799 -p1
%patch2800 -p1
%patch2801 -p1
%patch2802 -p1
%patch2803 -p1
%patch2804 -p1
%patch2805 -p1
%patch2806 -p1
%patch2807 -p1
%patch2808 -p1
%patch2809 -p1
%patch2810 -p1
%patch2811 -p1
%patch2812 -p1
%patch2813 -p1
%patch2814 -p1
%patch2815 -p1
%patch2816 -p1
%patch2817 -p1
%patch2818 -p1
%patch2819 -p1
%patch2820 -p1
%patch2821 -p1
%patch2822 -p1
%patch2823 -p1
%patch2824 -p1
%patch2825 -p1
%patch2826 -p1
%patch2827 -p1
%patch2828 -p1
%patch2829 -p1
%patch2830 -p1
%patch2831 -p1
%patch2832 -p1
%patch2833 -p1
%patch2834 -p1
%patch2835 -p1
%patch2836 -p1
%patch2837 -p1
%patch2838 -p1
%patch2839 -p1
%patch2840 -p1
%patch2841 -p1
%patch2842 -p1
%patch2843 -p1
%patch2844 -p1
%patch2845 -p1
%patch2846 -p1
%patch2847 -p1
%patch2848 -p1
%patch2849 -p1
%patch2850 -p1
%patch2851 -p1
%patch2852 -p1
%patch2853 -p1
%patch2854 -p1
%patch2855 -p1
%patch2856 -p1
%patch2857 -p1
%patch2858 -p1
%patch2859 -p1
%patch2860 -p1
%patch2861 -p1
%patch2862 -p1
%patch2863 -p1
%patch2864 -p1
%patch2865 -p1
%patch2866 -p1
%patch2867 -p1
%patch2868 -p1
%patch2869 -p1
%patch2870 -p1
%patch2871 -p1
%patch2872 -p1
%patch2873 -p1
%patch2874 -p1
%patch2875 -p1
%patch2876 -p1
%patch2877 -p1
%patch2878 -p1
%patch2879 -p1
%patch2880 -p1
%patch2881 -p1
%patch2882 -p1
%patch2883 -p1
%patch2884 -p1
%patch2885 -p1
%patch2886 -p1
%patch2887 -p1
%patch2888 -p1
%patch2889 -p1
%patch2890 -p1
%patch2891 -p1
%patch2892 -p1
%patch2893 -p1
%patch2894 -p1
%patch2895 -p1
%patch2896 -p1
%patch2897 -p1
%patch2898 -p1
%patch2899 -p1
%patch2900 -p1
%patch2901 -p1
%patch2902 -p1
%patch2903 -p1
%patch2904 -p1
%patch2905 -p1
%patch2906 -p1
%patch2907 -p1
%patch2908 -p1
%patch2909 -p1
%patch2910 -p1
%patch2911 -p1
%patch2912 -p1
%patch2913 -p1
%patch2914 -p1
%patch2915 -p1
%patch2916 -p1
%patch2917 -p1
%patch2918 -p1
%patch2919 -p1
%patch2920 -p1
%patch2921 -p1
%patch2922 -p1
%patch2923 -p1
%patch2924 -p1
%patch2925 -p1
%patch2926 -p1
%patch2927 -p1
%patch2928 -p1
%patch2929 -p1
%patch2930 -p1
%patch2931 -p1
%patch2932 -p1
%patch2933 -p1
%patch2934 -p1
%patch2935 -p1
%patch2936 -p1
%patch2937 -p1
%patch2938 -p1
%patch2939 -p1
%patch2940 -p1
%patch2941 -p1
%patch2942 -p1
%patch2943 -p1
%patch2944 -p1
%patch2945 -p1
%patch2946 -p1
%patch2947 -p1
%patch2948 -p1
%patch2949 -p1
%patch2950 -p1
%patch2951 -p1
%patch2952 -p1
%patch2953 -p1
%patch2954 -p1
%patch2955 -p1
%patch2956 -p1
%patch2957 -p1
%patch2958 -p1
%patch2959 -p1
%patch2960 -p1
%patch2961 -p1
%patch2962 -p1
%patch2963 -p1
%patch2964 -p1
%patch2965 -p1
%patch2966 -p1
%patch2967 -p1
%patch2968 -p1
%patch2969 -p1
%patch2970 -p1
%patch2971 -p1
%patch2972 -p1
%patch2973 -p1
%patch2974 -p1
%patch2975 -p1
%patch2976 -p1
%patch2977 -p1
%patch2978 -p1
%patch2979 -p1
%patch2980 -p1
%patch2981 -p1
%patch2984 -p1
%patch2985 -p1
%patch2986 -p1
%patch2987 -p1
%patch2988 -p1
%patch2989 -p1
%patch2990 -p1
%patch2991 -p1
%patch2992 -p1
%patch2993 -p1
%patch2994 -p1
%patch2995 -p1
%patch2996 -p1
%patch2997 -p1
%patch2998 -p1
%patch2999 -p1
%patch3000 -p1
%patch3001 -p1
%patch3002 -p1
%patch3003 -p1
%patch3004 -p1
%patch3005 -p1
%patch3006 -p1
%patch3007 -p1
%patch3008 -p1
%patch3009 -p1
%patch3010 -p1
%patch3011 -p1
%patch3012 -p1
%patch3013 -p1
%patch3014 -p1
%patch3015 -p1
%patch3016 -p1
%patch3017 -p1
%patch3018 -p1
%patch3019 -p1
%patch3020 -p1
%patch3021 -p1
%patch3022 -p1
%patch3024 -p1
%patch3025 -p1
%patch3026 -p1
%patch3027 -p1
%patch3028 -p1
%patch3029 -p1
%patch3030 -p1
%patch3031 -p1
%patch3032 -p1
%patch3033 -p1
%patch3034 -p1
%patch3035 -p1
%patch3036 -p1
%patch3037 -p1
%patch3038 -p1
%patch3039 -p1
%patch3040 -p1
%patch3041 -p1
%patch3042 -p1
%patch3043 -p1
%patch3044 -p1
%patch3045 -p1
%patch3046 -p1
%patch3047 -p1
%patch3049 -p1
%patch3050 -p1
%patch3051 -p1
%patch3052 -p1
%patch3053 -p1
%patch3054 -p1
%patch3055 -p1
%patch3056 -p1
%patch3057 -p1
%patch3058 -p1
%patch3059 -p1
%patch3060 -p1
%patch3061 -p1
%patch3062 -p1
%patch3063 -p1
%patch3064 -p1
%patch3065 -p1
%patch3066 -p1
%patch3067 -p1
%patch3068 -p1
%patch3069 -p1
%patch3070 -p1
%patch3071 -p1
%patch3072 -p1
%patch3073 -p1
%patch3074 -p1
%patch3075 -p1
%patch3076 -p1
%patch3077 -p1
%patch3078 -p1
%patch3079 -p1
%patch3080 -p1
%patch3081 -p1
%patch3082 -p1
%patch3083 -p1
%patch3084 -p1
%patch3085 -p1
%patch3086 -p1
%patch3087 -p1
%patch3088 -p1
%patch3089 -p1
%patch3090 -p1
%patch3091 -p1
%patch3092 -p1
%patch3093 -p1
%patch3094 -p1
%patch3095 -p1
%patch3096 -p1
%patch3097 -p1
%patch3098 -p1
%patch3099 -p1
%patch3100 -p1
%patch3101 -p1
%patch3102 -p1
%patch3103 -p1
%patch3104 -p1
%patch3105 -p1
%patch3106 -p1
%patch3107 -p1
%patch3108 -p1
%patch3109 -p1
%patch3110 -p1
%patch3111 -p1
%patch3112 -p1
%patch3113 -p1
%patch3114 -p1
%patch3115 -p1
%patch3116 -p1
%patch3117 -p1
%patch3118 -p1
%patch3119 -p1
%patch3120 -p1
%patch3121 -p1
%patch3122 -p1
%patch3123 -p1
%patch3124 -p1
%patch3125 -p1
%patch3126 -p1
%patch3127 -p1
%patch3128 -p1
%patch3129 -p1
%patch3130 -p1
%patch3131 -p1
%patch3132 -p1
%patch3133 -p1
%patch3134 -p1
%patch3135 -p1
%patch3136 -p1
%patch3137 -p1
%patch3138 -p1
%patch3139 -p1
%patch3140 -p1
%patch3141 -p1
%patch3142 -p1
%patch3143 -p1
%patch3144 -p1
%patch3145 -p1
%patch3146 -p1
%patch3147 -p1
%patch3148 -p1
%patch3149 -p1
%patch3150 -p1
%patch3151 -p1
%patch3152 -p1
%patch3153 -p1
%patch3154 -p1
%patch3155 -p1
%patch3156 -p1
%patch3157 -p1
%patch3158 -p1
%patch3159 -p1
%patch3160 -p1
%patch3161 -p1
%patch3162 -p1
%patch3163 -p1
%patch3164 -p1
%patch3165 -p1
%patch3166 -p1
%patch3167 -p1
%patch3168 -p1
%patch3169 -p1
%patch3170 -p1
%patch3171 -p1
%patch3172 -p1
%patch3173 -p1
%patch3174 -p1
%patch3175 -p1
%patch3176 -p1
%patch3177 -p1
%patch3178 -p1
%patch3179 -p1
%patch3180 -p1
%patch3181 -p1
%patch3182 -p1
%patch3183 -p1
%patch3184 -p1
%patch3185 -p1
%patch3186 -p1
%patch3187 -p1
%patch3188 -p1
%patch3189 -p1
%patch3190 -p1
%patch3191 -p1
%patch3192 -p1
%patch3193 -p1
%patch3194 -p1
%patch3195 -p1
%patch3196 -p1
%patch3197 -p1
%patch3198 -p1
%patch3199 -p1
%patch3200 -p1
%patch3201 -p1
%patch3202 -p1
%patch3204 -p1
%patch3205 -p1
%patch3206 -p1
%patch3207 -p1
%patch3208 -p1
%patch3209 -p1
%patch3210 -p1
%patch3211 -p1
%patch3212 -p1
%patch3213 -p1
%patch3214 -p1
%patch3215 -p1
%patch3216 -p1
%patch3217 -p1
%patch3218 -p1
%patch3219 -p1
%patch3220 -p1
%patch3221 -p1
%patch3222 -p1
%patch3223 -p1
%patch3224 -p1
%patch3225 -p1
%patch3226 -p1
%patch3227 -p1
%patch3228 -p1
%patch3229 -p1
%patch3230 -p1
%patch3231 -p1
%patch3232 -p1
%patch3233 -p1
%patch3234 -p1
%patch3235 -p1
%patch3236 -p1
%patch3237 -p1
%patch3238 -p1
%patch3239 -p1
%patch3240 -p1
%patch3241 -p1
%patch3242 -p1
%patch3243 -p1
%patch3244 -p1
%patch3245 -p1
%patch3246 -p1
%patch3247 -p1
%patch3248 -p1
%patch3249 -p1
%patch3250 -p1
%patch3251 -p1
%patch3252 -p1
%patch3253 -p1
%patch3254 -p1
%patch3255 -p1
%patch3256 -p1
%patch3257 -p1
%patch3258 -p1
%patch3259 -p1
%patch3260 -p1
%patch3261 -p1
%patch3262 -p1
%patch3263 -p1
%patch3264 -p1
%patch3265 -p1
%patch3266 -p1
%patch3267 -p1
%patch3268 -p1
%patch3269 -p1
%patch3270 -p1
%patch3271 -p1
%patch3272 -p1
%patch3273 -p1
%patch3274 -p1
%patch3275 -p1
%patch3276 -p1
%patch3277 -p1
%patch3278 -p1
%patch3279 -p1
%patch3280 -p1
%patch3281 -p1
%patch3282 -p1
%patch3283 -p1
%patch3284 -p1
%patch3285 -p1
%patch3286 -p1
%patch3287 -p1
%patch3288 -p1
%patch3289 -p1
%patch3290 -p1
%patch3291 -p1
%patch3292 -p1
%patch3293 -p1
%patch3294 -p1
%patch3295 -p1
%patch3296 -p1
%patch3297 -p1
%patch3298 -p1
%patch3299 -p1
%patch3300 -p1
%patch3301 -p1
%patch3302 -p1
%patch3303 -p1
%patch3304 -p1
%patch3305 -p1
%patch3306 -p1
%patch3307 -p1
%patch3308 -p1
%patch3309 -p1
%patch3310 -p1
%patch3311 -p1
%patch3312 -p1
%patch3313 -p1
%patch3314 -p1
%patch3315 -p1
%patch3316 -p1
%patch3317 -p1
%patch3318 -p1
%patch3319 -p1
%patch3320 -p1
%patch3321 -p1
%patch3322 -p1
%patch3323 -p1
%patch3324 -p1
%patch3325 -p1
%patch3326 -p1
%patch3327 -p1
%patch3328 -p1
%patch3329 -p1
%patch3330 -p1
%patch3331 -p1
%patch3332 -p1
%patch3333 -p1
%patch3334 -p1
%patch3335 -p1
%patch3336 -p1
%patch3337 -p1
%patch3338 -p1
%patch3339 -p1
%patch3340 -p1
%patch3341 -p1
%patch3342 -p1
%patch3343 -p1
%patch3344 -p1
%patch3345 -p1
%patch3346 -p1
%patch3347 -p1
%patch3348 -p1
%patch3349 -p1
%patch3350 -p1
%patch3351 -p1
%patch3352 -p1
%patch3353 -p1
%patch3354 -p1
%patch3355 -p1
%patch3356 -p1
%patch3357 -p1
%patch3358 -p1
%patch3359 -p1
%patch3360 -p1
%patch3361 -p1
%patch3362 -p1
%patch3363 -p1
%patch3364 -p1
%patch3365 -p1
%patch3366 -p1
%patch3367 -p1
%patch3368 -p1
%patch3369 -p1
%patch3370 -p1
%patch3371 -p1
%patch3372 -p1
%patch3373 -p1
%patch3374 -p1
%patch3375 -p1
%patch3376 -p1
%patch3377 -p1
%patch3378 -p1
%patch3379 -p1
%patch3380 -p1
%patch3381 -p1
%patch3382 -p1
%patch3383 -p1
%patch3384 -p1
%patch3385 -p1
%patch3386 -p1
%patch3387 -p1
%patch3388 -p1
%patch3389 -p1
%patch3390 -p1
%patch3391 -p1
%patch3392 -p1
%patch3393 -p1
%patch3394 -p1
%patch3395 -p1
%patch3396 -p1
%patch3397 -p1
%patch3398 -p1
%patch3399 -p1
%patch3400 -p1
%patch3401 -p1
%patch3402 -p1
%patch3403 -p1
%patch3404 -p1
%patch3405 -p1
%patch3406 -p1
%patch3407 -p1
%patch3408 -p1
%patch3409 -p1
%patch3410 -p1
%patch3411 -p1
%patch3412 -p1
%patch3413 -p1
%patch3414 -p1
%patch3415 -p1
%patch3416 -p1
%patch3417 -p1
%patch3418 -p1
%patch3419 -p1
%patch3420 -p1
%patch3421 -p1
%patch3422 -p1
%patch3423 -p1
%patch3424 -p1
%patch3425 -p1
%patch3426 -p1
%patch3427 -p1
%patch3428 -p1
%patch3429 -p1
%patch3430 -p1
%patch3431 -p1
%patch3432 -p1
%patch3433 -p1
%patch3434 -p1
%patch3435 -p1
%patch3436 -p1
%patch3437 -p1
%patch3438 -p1
%patch3439 -p1
%patch3440 -p1
%patch3441 -p1
%patch3442 -p1
%patch3443 -p1
%patch3444 -p1
%patch3445 -p1
%patch3446 -p1
%patch3447 -p1
%patch3448 -p1
%patch3449 -p1
%patch3450 -p1
%patch3451 -p1
%patch3452 -p1
%patch3453 -p1
%patch3454 -p1
%patch3455 -p1
%patch3456 -p1
%patch3457 -p1
%patch3458 -p1
%patch3459 -p1
%patch3460 -p1
%patch3461 -p1
%patch3462 -p1
%patch3463 -p1
%patch3464 -p1
%patch3465 -p1
%patch3466 -p1
%patch3467 -p1
%patch3468 -p1
%patch3469 -p1
%patch3470 -p1
%patch3471 -p1
%patch3472 -p1
%patch3473 -p1
%patch3474 -p1
%patch3475 -p1
%patch3476 -p1
%patch3477 -p1
%patch3478 -p1
%patch3479 -p1
%patch3480 -p1
%patch3481 -p1
%patch3482 -p1
%patch3483 -p1
%patch3484 -p1
%patch3485 -p1
%patch3486 -p1
%patch3487 -p1
%patch3488 -p1
%patch3489 -p1
%patch3490 -p1
%patch3491 -p1
%patch3492 -p1
%patch3493 -p1
%patch3494 -p1
%patch3495 -p1
%patch3496 -p1
%patch3497 -p1
%patch3498 -p1
%patch3499 -p1
%patch3500 -p1
%patch3501 -p1
%patch3502 -p1
%patch3503 -p1
%patch3504 -p1
%patch3505 -p1
%patch3506 -p1
%patch3507 -p1
%patch3508 -p1
%patch3509 -p1
%patch3510 -p1
%patch3511 -p1
%patch3512 -p1
%patch3513 -p1
%patch3514 -p1
%patch3515 -p1
%patch3516 -p1
%patch3517 -p1
%patch3518 -p1
%patch3519 -p1
%patch3520 -p1
%patch3521 -p1
%patch3522 -p1
%patch3523 -p1
%patch3524 -p1
%patch3525 -p1
%patch3526 -p1
%patch3527 -p1
%patch3528 -p1
%patch3529 -p1
%patch3530 -p1
%patch3531 -p1
%patch3532 -p1
%patch3533 -p1
%patch3534 -p1
%patch3535 -p1
%patch3536 -p1
%patch3537 -p1
%patch3538 -p1
%patch3539 -p1
%patch3540 -p1
%patch3541 -p1
%patch3542 -p1
%patch3543 -p1
%patch3544 -p1
%patch3545 -p1
%patch3546 -p1
%patch3547 -p1
%patch3548 -p1
%patch3549 -p1
%patch3550 -p1
%patch3551 -p1
%patch3552 -p1
%patch3553 -p1
%patch3554 -p1
%patch3555 -p1
%patch3556 -p1
%patch3557 -p1
%patch3558 -p1
%patch3559 -p1
%patch3560 -p1
%patch3561 -p1
%patch3562 -p1
%patch3563 -p1
%patch3564 -p1
%patch3565 -p1
%patch3566 -p1
%patch3567 -p1
%patch3568 -p1
%patch3569 -p1
%patch3570 -p1
%patch3571 -p1
%patch3572 -p1
%patch3573 -p1
%patch3574 -p1
%patch3575 -p1
%patch3576 -p1
%patch3577 -p1
%patch3578 -p1
%patch3579 -p1
%patch3580 -p1
%patch3581 -p1
%patch3582 -p1
%patch3583 -p1
%patch3584 -p1
%patch3585 -p1
%patch3586 -p1
%patch3587 -p1
%patch3588 -p1
%patch3589 -p1
%patch3590 -p1
%patch3591 -p1
%patch3592 -p1
%patch3593 -p1
%patch3594 -p1
%patch3595 -p1
%patch3596 -p1
%patch3597 -p1
%patch3598 -p1
%patch3599 -p1
%patch3600 -p1
%patch3601 -p1
%patch3602 -p1
%patch3603 -p1
%patch3604 -p1
%patch3605 -p1
%patch3606 -p1
%patch3607 -p1
%patch3608 -p1
%patch3609 -p1
%patch3610 -p1
%patch3611 -p1
%patch3612 -p1
%patch3613 -p1
%patch3614 -p1
%patch3615 -p1
%patch3616 -p1
%patch3617 -p1
%patch3618 -p1
%patch3619 -p1
%patch3620 -p1
%patch3621 -p1
%patch3622 -p1
%patch3623 -p1
%patch3624 -p1
%patch3625 -p1
%patch3626 -p1
%patch3627 -p1
%patch3628 -p1
%patch3629 -p1
%patch3630 -p1
%patch3631 -p1
%patch3632 -p1
%patch3633 -p1
%patch3634 -p1
%patch3635 -p1
%patch3636 -p1
%patch3637 -p1
%patch3638 -p1
%patch3639 -p1
%patch3640 -p1
%patch3641 -p1
%patch3642 -p1
%patch3643 -p1
%patch3644 -p1
%patch3645 -p1
%patch3646 -p1
%patch3647 -p1
%patch3648 -p1
%patch3649 -p1
%patch3650 -p1
%patch3651 -p1
%patch3652 -p1
%patch3653 -p1
%patch3654 -p1
%patch3655 -p1
%patch3656 -p1
%patch3657 -p1
%patch3658 -p1
%patch3659 -p1
%patch3660 -p1
%patch3661 -p1
%patch3662 -p1
%patch3663 -p1
%patch3664 -p1
%patch3665 -p1
%patch3666 -p1
%patch3667 -p1
%patch3668 -p1
%patch3669 -p1
%patch3670 -p1
%patch3671 -p1
%patch3672 -p1
%patch3673 -p1
%patch3674 -p1
%patch3675 -p1
%patch3676 -p1
%patch3677 -p1
%patch3678 -p1
%patch3679 -p1
%patch3680 -p1
%patch3681 -p1
%patch3682 -p1
%patch3683 -p1
%patch3684 -p1
%patch3685 -p1
%patch3686 -p1
%patch3687 -p1
%patch3688 -p1
%patch3689 -p1
%patch3690 -p1
%patch3691 -p1
%patch3692 -p1
%patch3693 -p1
%patch3694 -p1
%patch3695 -p1
%patch3696 -p1
%patch3697 -p1
%patch3698 -p1
%patch3699 -p1
%patch3700 -p1
%patch3701 -p1
%patch3702 -p1
%patch3703 -p1
%patch3704 -p1
%patch3705 -p1
%patch3706 -p1
%patch3707 -p1
%patch3708 -p1
%patch3709 -p1
%patch3710 -p1
%patch3711 -p1
%patch3712 -p1
%patch3713 -p1
%patch3714 -p1
%patch3715 -p1
%patch3716 -p1
%patch3717 -p1
%patch3718 -p1
%patch3719 -p1
%patch3720 -p1
%patch3721 -p1
%patch3722 -p1
%patch3723 -p1
%patch3724 -p1
%patch3725 -p1
%patch3726 -p1
%patch3727 -p1
%patch3728 -p1
%patch3729 -p1
%patch3730 -p1
%patch3731 -p1
%patch3732 -p1
%patch3733 -p1
%patch3734 -p1
%patch3735 -p1
%patch3736 -p1
%patch3737 -p1
%patch3738 -p1
%patch3739 -p1
%patch3740 -p1
%patch3741 -p1
%patch3742 -p1
%patch3743 -p1
%patch3744 -p1
%patch3745 -p1
%patch3746 -p1
%patch3747 -p1
%patch3748 -p1
%patch3749 -p1
%patch3750 -p1
%patch3751 -p1
%patch3752 -p1
%patch3753 -p1
%patch3754 -p1
%patch3755 -p1
%patch3756 -p1
%patch3757 -p1
%patch3758 -p1
%patch3759 -p1
%patch3760 -p1
%patch3761 -p1
%patch3762 -p1
%patch3763 -p1
%patch3764 -p1
%patch3765 -p1
%patch3766 -p1
%patch3767 -p1
%patch3768 -p1
%patch3769 -p1
%patch3770 -p1
%patch3771 -p1
%patch3772 -p1
%patch3773 -p1
%patch3774 -p1
%patch3775 -p1
%patch3776 -p1
%patch3777 -p1
%patch3778 -p1
%patch3779 -p1
%patch3780 -p1
%patch3781 -p1
%patch3782 -p1
%patch3783 -p1
%patch3784 -p1
%patch3785 -p1
%patch3786 -p1
%patch3787 -p1
%patch3788 -p1
%patch3789 -p1
%patch3790 -p1
%patch3791 -p1
%patch3792 -p1
%patch3793 -p1
%patch3794 -p1
%patch3795 -p1
%patch3796 -p1
%patch3797 -p1
%patch3798 -p1
%patch3799 -p1
%patch3800 -p1
%patch3801 -p1
%patch3802 -p1
%patch3803 -p1
%patch3804 -p1
%patch3805 -p1
%patch3806 -p1
%patch3807 -p1
%patch3808 -p1
%patch3809 -p1
%patch3810 -p1
%patch3811 -p1
%patch3812 -p1
%patch3813 -p1
%patch3814 -p1
%patch3815 -p1
%patch3816 -p1
%patch3817 -p1
%patch3818 -p1
%patch3819 -p1
%patch3820 -p1
%patch3821 -p1
%patch3822 -p1
%patch3823 -p1
%patch3824 -p1
%patch3825 -p1
%patch3826 -p1
%patch3827 -p1
%patch3828 -p1
%patch3829 -p1
%patch3830 -p1
%patch3831 -p1
%patch3832 -p1
%patch3833 -p1
%patch3834 -p1
%patch3835 -p1
%patch3836 -p1
%patch3837 -p1
%patch3838 -p1
%patch3839 -p1
%patch3840 -p1
%patch3841 -p1
%patch3842 -p1
%patch3843 -p1
%patch3844 -p1
%patch3845 -p1
%patch3846 -p1
%patch3847 -p1
%patch3848 -p1
%patch3849 -p1
%patch3850 -p1
%patch3851 -p1
%patch3852 -p1
%patch3853 -p1
%patch3854 -p1
%patch3855 -p1
%patch3856 -p1
%patch3857 -p1
%patch3858 -p1
%patch3859 -p1
%patch3860 -p1
%patch3861 -p1
%patch3862 -p1
%patch3863 -p1
%patch3864 -p1
%patch3865 -p1
%patch3866 -p1
%patch3867 -p1
%patch3868 -p1
%patch3869 -p1
%patch3870 -p1
%patch3871 -p1
%patch3872 -p1
%patch3873 -p1
%patch3874 -p1
%patch3875 -p1
%patch3876 -p1
%patch3877 -p1
%patch3878 -p1
%patch3879 -p1
%patch3880 -p1
%patch3881 -p1
%patch3882 -p1
%patch3883 -p1

%patch9999 -p1

ApplyOptionalPatch qemu-kvm-test.patch

%build
# --build-id option is used fedora 8 onwards for giving info to the debug packages.
extraldflags="-Wl,--build-id";
buildldflags="VL_LDFLAGS=-Wl,--build-id"

%if %{enable_fake_machine}
%define fake_machine_arg --enable-fake-machine
%else
%define fake_machine_arg %{nil}
%endif

%if %{with rhev_features}
%define disable_rhev_features_arg %{nil}
%else
%define disable_rhev_features_arg --disable-rhev-features
%endif

%define qemu_ga_build_flags --prefix=%{_prefix} \\\
             --localstatedir=%{_localstatedir} \\\
             --sysconfdir=%{_sysconfdir} \\\
             --disable-strip \\\
             --disable-xen \\\
             --block-drv-whitelist=qcow2,raw,file,host_device,host_cdrom,qed \\\
             --disable-debug-tcg \\\
             --disable-sparse \\\
             --disable-sdl \\\
             --disable-curses \\\
             --disable-curl \\\
             --disable-check-utests \\\
             --disable-brlapi \\\
             --disable-bluez \\\
             --enable-docs \\\
             --disable-vde \\\
             --disable-spice \\\
             --trace-backend=nop \\\
             --enable-smartcard \\\
             --disable-smartcard-nss

mkdir qemu-kvm-x86_64-build
cd qemu-kvm-x86_64-build

%if %{with qemu_kvm}
# we are building in a separate build directory, so that we can build for both linux x86_64
# and windows (for the guest agent).
# sdl outputs to alsa or pulseaudio depending on system config, but it's broken (#495964)
# alsa works, but causes huge CPU load due to bugs
# oss works, but is very problematic because it grabs exclusive control of the device causing other apps to go haywire
../configure --target-list=x86_64-softmmu \
            --prefix=%{_prefix} \
            --localstatedir=%{_localstatedir} \
            --sysconfdir=%{_sysconfdir} \
            --audio-drv-list=pa,alsa \
            --audio-card-list=ac97,es1370 \
            --disable-strip \
            --extra-ldflags="$extraldflags -pie -Wl,-z,relro -Wl,-z,now" \
            --extra-cflags="$RPM_OPT_FLAGS -fPIE -DPIE" \
            --disable-xen \
            --block-drv-whitelist=qcow2,raw,file,host_device,host_cdrom,qed \
            --disable-debug-tcg \
            --disable-sparse \
            --enable-werror \
            --disable-sdl \
            --disable-curses \
            --disable-curl \
            --disable-check-utests \
            --enable-vnc-tls \
            --enable-vnc-sasl \
            --disable-brlapi \
            --disable-bluez \
            --enable-docs \
            --disable-vde \
            --enable-linux-aio \
            --enable-kvm \
            --enable-spice \
            --enable-kvm-cap-pit \
            --enable-kvm-cap-device-assignment \
            --trace-backend=dtrace \
            --enable-smartcard \
            --disable-smartcard-nss \
            --enable-usb-redir \
            %{fake_machine_arg} \
            %{disable_rhev_features_arg}

echo "config-host.mak contents:"
echo "==="
cat config-host.mak
echo "==="
%endif # with qemu_kvm

%if %{with guest_agent}
# Now configure for the windows guest agent build, using mingw32-
cd ..
mkdir qemu-kvm-win32-build
%if %{with guest_agent_win32}
cd qemu-kvm-win32-build

../configure --target-list=x86_64-softmmu \
             --cross-prefix=i686-pc-mingw32- \
             %{qemu_ga_build_flags}

cd ..
%endif # with guest_agent_win32
# Now configure for the Linux guest agent build
mkdir qemu-kvm-qemu-ga-build
cd qemu-kvm-qemu-ga-build

../configure --target-list=x86_64-softmmu \
             --extra-ldflags="$extraldflags -pie -Wl,-z,relro -Wl,-z,now" \
             --extra-cflags="$RPM_OPT_FLAGS -fPIE -DPIE" \
             %{qemu_ga_build_flags}

cd ../qemu-kvm-x86_64-build
%endif

%if %{with qemu_kvm}
# generate the default config:
make x86_64-softmmu/config-devices.mak

# disable vmware_vga on the config:
sed -i -e '/CONFIG_VMWARE_VGA=y/d' x86_64-softmmu/config-devices.mak

make V=1 QEMU_PROG=%{progname} QEMU_BINDIR="%{_prefix}/libexec" \
     %{?_smp_mflags} $buildldflags
%endif # with qemu_kvm

%if %{with guest_agent}
%if %{with guest_agent_win32}
# build the windows guest agent
cd ../qemu-kvm-win32-build
make V=1 %{?_smp_mflags} $buildldflags qemu-ga.exe
%endif # with guest_agent_win32
# build the linux guest agent
cd ../qemu-kvm-qemu-ga-build
make V=1 %{?_smp_mflags} $buildldflags qemu-ga
%endif
cd ..   # we are now in the parent dir of all the build dirs

%install
cd qemu-kvm-x86_64-build
rm -rf $RPM_BUILD_ROOT

%if %{with qemu_kvm}
install -D -p -m 0755 %{SOURCE4} $RPM_BUILD_ROOT%{_initddir}/ksm
install -D -p -m 0644 %{SOURCE5} $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/ksm

install -D -p -m 0755 %{SOURCE6} $RPM_BUILD_ROOT%{_initddir}/ksmtuned
install -D -p -m 0755 %{SOURCE7} $RPM_BUILD_ROOT%{_sbindir}/ksmtuned
install -D -p -m 0644 %{SOURCE8} $RPM_BUILD_ROOT%{_sysconfdir}/ksmtuned.conf

mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/modules
mkdir -p $RPM_BUILD_ROOT%{_bindir}/
mkdir -p $RPM_BUILD_ROOT%{_libexecdir}/
mkdir -p $RPM_BUILD_ROOT%{_datadir}/%{confname}
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/udev/rules.d
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/modprobe.d

install -m 0755 %{SOURCE2} $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/modules/kvm.modules
install -m 0755 ../kvm/kvm_stat $RPM_BUILD_ROOT%{_bindir}/
install -m 0644 %{SOURCE3} $RPM_BUILD_ROOT%{_sysconfdir}/udev/rules.d
install -m 0644 %{SOURCE9} $RPM_BUILD_ROOT%{_sysconfdir}/modprobe.d/blacklist-kvm.conf

make DESTDIR="${RPM_BUILD_ROOT}" \
     docdir="%{_docdir}/%{name}-%{version}" \
     sharedir="%{_datadir}/%{confname}" \
     datadir="%{_datadir}/%{confname}" \
     sysconfdir="%{_sysconfdir}" \
     QEMU_PROG=%{progname} \
     QEMU_BINDIR="%{_prefix}/libexec" \
     install
%endif # with qemu_kvm

%if %{with guest_agent}
install -D -p -m 0755 ../qemu-kvm-qemu-ga-build/qemu-ga $RPM_BUILD_ROOT%{_bindir}/qemu-ga
install -D -p -m 0755 %{SOURCE10} $RPM_BUILD_ROOT%{_initddir}/qemu-ga
install -D -p -m 0644 %{SOURCE11} $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/qemu-ga
%endif # guest_agent

rm -rf ${RPM_BUILD_ROOT}%{_bindir}/qemu-nbd
rm -rf ${RPM_BUILD_ROOT}%{_mandir}/man8/qemu-nbd.8*
%if %{without guest_agent}
rm -f $RPM_BUILD_ROOT%{_bindir}/qemu-ga
%endif

%if %{with qemu_kvm}
chmod -x ${RPM_BUILD_ROOT}%{_mandir}/man1/*
install -D -p -m 0644 -t ${RPM_BUILD_ROOT}%{qemudocdir} ../Changelog ../README ../TODO ../COPYING ../COPYING.LIB ../LICENSE

install -D -p -m 0644 ../qemu.sasl $RPM_BUILD_ROOT%{_sysconfdir}/sasl2/qemu-kvm.conf

rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/pxe*bin
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/vgabios*bin
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/bios.bin
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/openbios-ppc
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/openbios-sparc32
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/openbios-sparc64
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/petalogix-s3adsp1800.dtb
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/video.x
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/bamboo.dtb
rm -rf ${RPM_BUILD_ROOT}%{_datadir}/%{confname}/ppc_rom.bin

# the pxe gpxe images will be symlinks to the images on
# /usr/share/gpxe, as QEMU doesn't know how to look
# for other paths, yet.
pxe_link() {
  ln -s ../gpxe/$2.rom %{buildroot}%{_datadir}/%{confname}/pxe-$1.bin
}

pxe_link e1000 e1000-0x100e
pxe_link ne2k_pci rtl8029
pxe_link pcnet pcnet32
pxe_link rtl8139 rtl8139
pxe_link virtio virtio-net
ln -s ../vgabios/VGABIOS-lgpl-latest.bin  %{buildroot}/%{_datadir}/%{confname}/vgabios.bin
ln -s ../vgabios/VGABIOS-lgpl-latest.cirrus.bin %{buildroot}/%{_datadir}/%{confname}/vgabios-cirrus.bin
ln -s ../vgabios/VGABIOS-lgpl-latest.qxl.bin %{buildroot}/%{_datadir}/%{confname}/vgabios-qxl.bin
ln -s ../vgabios/VGABIOS-lgpl-latest.stdvga.bin %{buildroot}/%{_datadir}/%{confname}/vgabios-stdvga.bin
ln -s ../vgabios/VGABIOS-lgpl-latest.vmware.bin %{buildroot}/%{_datadir}/%{confname}/vgabios-vmware.bin
ln -s ../seabios/bios.bin %{buildroot}/%{_datadir}/%{confname}/bios.bin
ln -s ../sgabios/sgabios.bin %{buildroot}/%{_datadir}/%{confname}/sgabios.bin
%endif # with qemu_kvm

%if %{with guest_agent_win32}
mkdir -p $RPM_BUILD_ROOT%{_datadir}/%{confname}/qemu-ga-win32/
install -m 0755 ../qemu-kvm-win32-build/qemu-ga.exe $RPM_BUILD_ROOT%{_datadir}/%{confname}/qemu-ga-win32/
install -D -p -m 0444 %{SOURCE12} $RPM_BUILD_ROOT%{_datadir}/%{confname}/qemu-ga-win32/README.txt
%endif # with guest_agent_win32


%if %{with qemu_kvm}
cd %{buildroot}/usr/share/systemtap/tapset
%endif # with qemu_kvm

%clean
rm -rf $RPM_BUILD_ROOT

%post
getent group kvm >/dev/null || groupadd -g 36 -r kvm
getent group qemu >/dev/null || groupadd -g 107 -r qemu
getent passwd qemu >/dev/null || \
  useradd -r -u 107 -g qemu -G kvm -d / -s /sbin/nologin \
    -c "qemu user" qemu

/sbin/chkconfig --add ksm
/sbin/chkconfig --add ksmtuned

%if %{with qemu_kvm}
# load kvm modules now, so we can make sure no reboot is needed.
# If there's already a kvm module installed, we don't mess with it
sh %{_sysconfdir}/sysconfig/modules/kvm.modules
%endif # with qemu_kvm

%if %{with guest_agent}
%post -n qemu-guest-agent%{?pkgsuffix}
/sbin/chkconfig --add qemu-ga
/sbin/chkconfig qemu-ga off
%endif # guest_agent

%if %{with qemu_kvm}
%preun
if [ $1 -eq 0 ]; then
    /sbin/service ksmtuned stop &>/dev/null || :
    /sbin/chkconfig --del ksmtuned
    /sbin/service ksm stop &>/dev/null || :
    /sbin/chkconfig --del ksm
fi
%endif # with qemu_kvm

%if %{with guest_agent}
%preun -n qemu-guest-agent%{?pkgsuffix}
if [ $1 -eq 0 ]; then
    /sbin/service qemu-ga stop &>/dev/null || :
    /sbin/chkconfig --del qemu-ga
fi
%endif # guest_agent

%if %{with qemu_kvm}
%postun
if [ $1 -ge 1 ]; then
    /sbin/service ksm condrestart &>/dev/null || :
    /sbin/service ksmtuned condrestart &>/dev/null || :
fi
%endif # with qemu_kvm

%if %{with qemu_kvm}
%files
%defattr(-,root,root)
%doc %{qemudocdir}/Changelog
%doc %{qemudocdir}/README
%doc %{qemudocdir}/TODO
%doc %{qemudocdir}/qemu-doc.html
%doc %{qemudocdir}/qemu-tech.html
%doc %{qemudocdir}/COPYING
%doc %{qemudocdir}/COPYING.LIB
%doc %{qemudocdir}/LICENSE
%dir %{_datadir}/%{confname}/
%{_datadir}/%{confname}/keymaps/
%{_mandir}/man1/%{progname}.1*
%config(noreplace) %{_sysconfdir}/sasl2/qemu-kvm.conf
%{_initddir}/ksm
%config(noreplace) %{_sysconfdir}/sysconfig/ksm
%{_initddir}/ksmtuned
%{_sbindir}/ksmtuned
%config(noreplace) %{_sysconfdir}/ksmtuned.conf
%{_datadir}/%{confname}/bios.bin
%{_datadir}/%{confname}/sgabios.bin
%{_datadir}/%{confname}/linuxboot.bin
%{_datadir}/%{confname}/multiboot.bin
%{_datadir}/%{confname}/vapic.bin
%{_datadir}/%{confname}/vgabios.bin
%{_datadir}/%{confname}/vgabios-cirrus.bin
%{_datadir}/%{confname}/vgabios-qxl.bin
%{_datadir}/%{confname}/vgabios-stdvga.bin
%{_datadir}/%{confname}/vgabios-vmware.bin
%{_datadir}/%{confname}/pxe-e1000.bin
%{_datadir}/%{confname}/pxe-virtio.bin
%{_datadir}/%{confname}/pxe-pcnet.bin
%{_datadir}/%{confname}/pxe-rtl8139.bin
%{_datadir}/%{confname}/pxe-ne2k_pci.bin
%{_datadir}/%{confname}/extboot.bin
%{_datadir}/systemtap/tapset/%{progname}.stp
%{_libexecdir}/%{progname}
%{_sysconfdir}/sysconfig/modules/kvm.modules
%{_sysconfdir}/udev/rules.d/80-kvm.rules
%config(noreplace) %{_sysconfdir}/modprobe.d/blacklist-kvm.conf
%endif # with qemu_kvm

%if %{with guest_agent}
%files -n qemu-guest-agent%{?pkgsuffix}
%defattr(-,root,root,-)
%{_bindir}/qemu-ga
%{_initddir}/qemu-ga
%config(noreplace) %{_sysconfdir}/sysconfig/qemu-ga

%if %{with guest_agent_win32}
%files -n qemu-guest-agent-win32%{?pkgsuffix}
%defattr(-,root,root,-)
%{_datadir}/%{confname}/qemu-ga-win32/
%{_datadir}/%{confname}/qemu-ga-win32/qemu-ga.exe
%{_datadir}/%{confname}/qemu-ga-win32/README.txt
%endif # with guest_agent_win32
%endif # guest_agent

%if %{with qemu_kvm}
%files -n %{pkgname}-tools
%defattr(-,root,root,-)
%{_bindir}/kvm_stat

%files -n qemu-img%{?pkgsuffix}
%defattr(-,root,root)
%{_bindir}/qemu-img
%{_bindir}/qemu-io
%{_mandir}/man1/qemu-img.1*
%endif # with qemu_kvm

%changelog
* Tue Jun 18 2013 Dmitry Konishchev <konishchev@gmail.com> - qemu-kvm-0.12.1.2-2.355.el6.5.CROC1
- Added CROC.patch

* Thu May 23 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.355.el6_4.5
- kvm-e1000-fix-link-down-handling-with-auto-negotiation.patch [bz#907716]
- kvm-e1000-unbreak-the-guest-network-when-migration-to-RH.patch [bz#907716]
- kvm-reimplement-error_setg-and-error_setg_errno-for-RHEL.patch [bz#957056]
- kvm-qga-set-umask-0077-when-daemonizing-CVE-2013-2007.patch [bz#957056]
- kvm-qga-distinguish-binary-modes-in-guest_file_open_mode.patch [bz#957056]
- kvm-qga-unlink-just-created-guest-file-if-fchmod-or-fdop.patch [bz#957056]
- Resolves: bz#907716
  (use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest)
- Resolves: bz#957056
  (CVE-2013-2007 qemu: guest agent creates files with insecure permissions in deamon mode [rhel-6.4.z])

* Fri May 03 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.355.el6_4.4
- kvm-virtio-balloon-fix-integer-overflow-in-BALLOON_CHANG.patch [bz#958750]
- Resolves: bz#958750
  (QMP event shows incorrect balloon value when balloon size is grater than or equal to 4G)

* Wed Apr 10 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.355.el6_4.3
- kvm-Fix-regression-introduced-by-machine-accel.patch [bz#929105]
- Resolves: bz#929105
  ([RHEL6.4] [regression] qemu-kvm does not enable ioeventfd)

* Thu Feb 28 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.355.el6_4.2
- kvm-e1000-Discard-packets-that-are-too-long-if-SBP-and-L.patch [bz#910841]
- kvm-e1000-Discard-oversized-packets-based-on-SBP-LPE.patch [bz#910841]
- Resolves: bz#910841
  (CVE-2012-6075  qemu (e1000 device driver): Buffer overflow when processing large packets when SBP and LPE flags are disabled [rhel-6.4.z])

* Wed Feb 06 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.355.el6_4.1
- kvm-Revert-e1000-no-need-auto-negotiation-if-link-was-do.patch [bz#907397]
- Resolves: bz#907397
  (Patch "e1000: no need auto-negotiation if link was down" may break e1000 guest)

* Wed Jan 23 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.355.el6
- kvm-Revert-audio-spice-add-support-for-volume-control.patch [bz#884253]
- kvm-Revert-hw-ac97-add-support-for-volume-control.patch [bz#884253]
- kvm-Revert-hw-ac97-the-volume-mask-is-not-only-0x1f.patch [bz#884253]
- kvm-Revert-hw-ac97-remove-USE_MIXER-code.patch [bz#884253]
- kvm-Revert-audio-don-t-apply-volume-effect-if-backend-ha.patch [bz#884253]
- kvm-Revert-audio-add-VOICE_VOLUME-ctl.patch [bz#884253]
- kvm-Revert-audio-split-sample-conversion-and-volume-mixi.patch [bz#884253]
- Resolves: bz#884253
  (Allow control of volume from within Windows Guests (Volume Mixture))

* Wed Jan 23 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.354.el6
- spec: add Epoch to old_conflict_ver
- Resolves: bz#895954
  (qemu-kvm-rhev conflicts and provides qemu-kvm)

* Wed Jan 23 2013 Miroslav Rezanina <mrezanin@redhat.com> - qemu-kvm-0.12.1.2-2.353.el6
- kvm-qxl-fix-range-check-for-rev3-io-commands.patch [bz#876982]
- kvm-dataplane-avoid-reentrancy-during-virtio_blk_data_pl.patch [bz#894995]
- kvm-dataplane-support-viostor-virtio-pci-status-bit-sett.patch [bz#894995]
- kvm-qxl-stop-using-non-revision-4-rom-fields-for-revisio.patch [bz#869981]
- kvm-qxl-change-rom-size-to-8192.patch [bz#869981]
- Resolves: bz#869981
  (Cross version migration between different host with spice is broken)
- Resolves: bz#876982
  (Start Windows 7 guest, connect using virt-viewer within seconds guest locks up)
- Resolves: bz#894995
  (core dump when install windows guest with x-data-plane=on)
- Resolves: bz#895954
  (qemu-kvm-rhev conflicts and provides qemu-kvm)

* Wed Jan 16 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.352.el6
- kvm-block-make-qiov_is_aligned-public.patch [bz#895392]
- kvm-dataplane-extract-virtio-blk-read-write-processing-i.patch [bz#895392]
- kvm-dataplane-handle-misaligned-virtio-blk-requests.patch [bz#895392]
- Resolves: bz#895392
  (fail to initialize the the data disk specified x-data-plane=on via 'Device Manager' in win7 64bit guest)

* Wed Jan 09 2013 Miroslav Rezanina <mrezanin@redhat.com> - qemu-kvm-0.12.1.2-2.351.el6
- kvm-qxl-save-qemu_create_displaysurface_from-result.patch [bz#885644]
- Resolves: bz#839832
  (qemu-ga: document selinux policy for read/write of guest files)
- Resolves: bz#885644
  (Memory leak and use after free in qxl_render_update_area_unlocked())

* Wed Jan 09 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.350.el6
- kvm-raw-posix-add-raw_get_aio_fd-for-virtio-blk-data-pla.patch [bz#877836]
- kvm-configure-add-CONFIG_VIRTIO_BLK_DATA_PLANE.patch [bz#877836]
- kvm-vhost-make-memory-region-assign-unassign-functions-p.patch [bz#877836]
- kvm-dataplane-add-host-memory-mapping-code.patch [bz#877836]
- kvm-dataplane-add-virtqueue-vring-code.patch [bz#877836]
- kvm-event_notifier-add-event_notifier_set.patch [bz#877836]
- kvm-dataplane-add-event-loop.patch [bz#877836]
- kvm-dataplane-add-Linux-AIO-request-queue.patch [bz#877836]
- kvm-iov-add-iov_discard_front-back-to-remove-data.patch [bz#877836]
- kvm-iov-add-qemu_iovec_concat_iov.patch [bz#877836]
- kvm-virtio-blk-Turn-drive-serial-into-a-qdev-property.patch [bz#877836]
- kvm-virtio-blk-define-VirtIOBlkConf.patch [bz#877836]
- kvm-virtio-blk-add-scsi-on-off-to-VirtIOBlkConf.patch [bz#877836]
- kvm-dataplane-add-virtio-blk-data-plane-code.patch [bz#877836]
- kvm-virtio-blk-add-x-data-plane-on-off-performance-featu.patch [bz#877836]
- kvm-virtio-pci-fix-virtio_pci_set_guest_notifiers-error-.patch [bz#877836]
- Resolves: bz#877836
  (backport virtio-blk data-plane patches)

* Tue Jan 08 2013 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.349.el6
- kvm-pc-rhel6-compat-enable-S3-S4-for-6.1-and-lower-machi.patch [bz#886798]
- kvm-e1000-no-need-auto-negotiation-if-link-was-down.patch [bz#890288]
- kvm-rtl8139-preserve-link-state-across-device-reset.patch [bz#890288]
- kvm-pci-assign-Enable-MSIX-on-device-to-match-guest.patch [bz#886410]
- Resolves: bz#886410
  (interrupts aren't passed from the Hypervisor to VMs running Mellanox ConnectX3 VFs)
- Resolves: bz#886798
  (Guest should get S3/S4 state according to machine type to avoid cross migration issue)
- Resolves: bz#890288
  (use set_link  to change rtl8139 and e1000 network card's status but fail to make effectively after reboot guest)
- Resolves: bz#886410
  (interrupts aren't passed from the Hypervisor to VMs running Mellanox ConnectX3 VFs)

* Wed Dec 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.348.el6
- kvm-spice-add-new-spice-server-callbacks-to-ui-spice-dis.patch [bz#879559]
- kvm-vmmouse-add-reset-handler.patch [bz#884450]
- kvm-vmmouse-fix-queue_size-field-initialization.patch [bz#884450]
- kvm-hw-vmmouse.c-Disable-vmmouse-after-reboot.patch [bz#884450]
- kvm-block-Fix-vpc-initialization-of-the-Dynamic-Disk-Hea.patch [bz#887897]
- kvm-block-vpc-write-checksum-back-to-footer-after-check.patch [bz#887897]
- Resolves: bz#879559
  (spice with non-qxl vga dumps core)
- Resolves: bz#884450
  (after change mac address of guest, mouse inside guest can not be used after system_reset in qemu)
- Resolves: bz#887897
  (Backport vpc initialization of the Dynamic Disk Header fix)

* Wed Dec 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.347.el6
- kvm-qxl-vnc-register-a-vm-state-change-handler-for-dummy.patch [#873563]
- kvm-hyper-v-Minimal-hyper-v-support-v5.patch [#801196]
- kvm-audio-split-sample-conversion-and-volume-mixing.patch [bz#884253]
- kvm-audio-add-VOICE_VOLUME-ctl.patch [bz#884253]
- kvm-audio-don-t-apply-volume-effect-if-backend-has-VOICE.patch [bz#884253]
- kvm-hw-ac97-remove-USE_MIXER-code.patch [bz#884253]
- kvm-hw-ac97-the-volume-mask-is-not-only-0x1f.patch [bz#884253]
- kvm-hw-ac97-add-support-for-volume-control.patch [bz#884253]
- kvm-audio-spice-add-support-for-volume-control.patch [bz#884253]
- Resolves: bz#873563
  (Guest aborted when boot with vnc and qxl)
- Resolves: bz#801196
  (Win28k KVM guest on RHEL6.1 BSOD with CLOCK_WATCHDOG_TIMEOUT)
- Resolves bz#884253
  (Allow control of volume from within Windows Guests (Volume Mixture))

* Fri Dec 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.346.el6
- qemu-ga: add appropriate flags to the guest agent builds
- Resolves: bz#787723

* Fri Dec 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.345.el6
- Update spec file to generate i686 and win32 packages [bz#787723 bz#815180]
- Resolves: bz#787723 bz#815180

* Tue Dec 11 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.344.el6
- kvm-hw-pc-Correctly-order-compatibility-props.patch [bz#733302]
- kvm-trace-trace-monitor-qmp-dispatch-completion.patch [bz#881732]
- kvm-Add-query-events-command-to-QMP-to-query-async-event.patch [bz#881732]
- kvm-Add-event-notification-for-guest-balloon-changes.patch [bz#881732]
- kvm-Add-rate-limiting-of-RTC_CHANGE-BALLOON_CHANGE-WATCH.patch [bz#881732]
- Resolves: bz#733302
  (Migration failed with error "warning: error while loading state for instance 0x0 of device '0000:00:02.0/qxl")
- Resolves: bz#881732
  (vdsm: vdsm is stuck in recovery for almost an hour on NFS storage with running vm's when blocking storage from host)

* Tue Dec 11 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.343.el6
- kvm-Revert-hyper-v-Minimal-hyper-v-support.patch [bz#801196]
- Related: bz#801196
  (Win28k KVM guest on RHEL6.1 BSOD with CLOCK_WATCHDOG_TIMEOUT)

* Mon Dec 10 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.342.el6
- kvm-add-cscope.-to-.gitignore.patch
- kvm-.gitignore-ignore-vi-swap-files-and-ctags-files.patch
- kvm-Add-TAGS-and-to-.gitignore.patch

* Wed Dec 05 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.341.el6
- Add Conflicts to spec file [bz#877901]
- Resolves: bz#877901
  (qemu-img and qemu-kvm conflict with qemu-img-rhev and qemu-kvm-rhev)

* Mon Dec 03 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.340.el6
- kvm-qxl-reload-memslots-after-migration-when-qxl-is-in-U.patch [bz#874574]
- Resolves: bz#874574
  (VM terminates when changing display configuration during migration)

* Mon Dec 03 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.339.el6
- kvm-Recognize-PCID-feature.patch [bz#869214]
- kvm-target-i386-cpu-add-CPUID_EXT_PCID-constant.patch [bz#869214]
- kvm-add-PCID-feature-to-Haswell-CPU-model-definition.patch [bz#869214]
- Resolves: bz#869214
  (Cpu flag "invpcid" is not exposed to guest on Hashwell host)

* Mon Dec 03 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.338.el6
- kvm-remove-rdtscp-flag-from-Opteron_G5-model-definition.patch [bz#874400]
- kvm-block-add-bdrv_reopen-support-for-raw-hdev-floppy-an.patch [bz#877339]
- kvm-qcow2-Fix-refcount-table-size-calculation.patch [bz#870917]
- kvm-qapi-disable-block-commit-command-for-rhel.patch [bz#878991]
- Resolves: bz#870917
  (qcow2: Crash when growing large refcount table)
- Resolves: bz#874400
  ("rdtscp" flag defined on Opteron_G5 model and cann't be exposed to guest)
- Resolves: bz#877339
  (fail to commit live snapshot image(lv) to a backing image(lv))
- Resolves: bz#878991
  (block-commit functionality should be RHEV-only, and disabled for RHEL)

* Thu Nov 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.337.el6
- kvm-hyper-v-Minimal-hyper-v-support.patch [bz#801196]
- Resolves: bz#801196
  (Win28k KVM guest on RHEL6.1 BSOD with CLOCK_WATCHDOG_TIMEOUT)

* Thu Nov 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.336.el6
- kvm-usb-host-scan-for-usb-devices-when-the-vm-starts.patch [bz#876534]
- kvm-qxl-call-dpy_gfx_resize-when-entering-vga-mode.patch [bz#865767]
- kvm-vga-fix-bochs-alignment-issue.patch [bz#877933]
- Resolves: bz#865767
  (qemu crashed when rhel6.3 64 bit guest reboots)
- Resolves: bz#876534
  ([regression] unable to boot from usb-host devices)
- Resolves: bz#877933
  (vga: fix bochs alignment issue)

* Mon Nov 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.335.el6
- kvm-vl-Fix-cross-version-migration-for-odd-RAM-sizes.patch [bz#860573]
- Resolves: bz#860573
  (Live migration from rhel6.3 release version to rhel6.4 newest version with 501MB memory in guest will fail)

* Fri Nov 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.334.el6
- kvm-i386-cpu-name-new-CPUID-bits.patch [bz#838126]
- kvm-x86-cpu-add-new-Opteron-CPU-model.patch [bz#838126]
- Resolves: bz#838126
  ([FEAT RHEL 6.4] Include support for AMD Seoul (AMD Opteron™ 4xxx series) processor)

* Thu Nov 01 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.333.el6
- kvm-i386-kvm-kvm_arch_get_supported_cpuid-move-R_EDX-hac.patch [bz#691638]
- kvm-i386-kvm-kvm_arch_get_supported_cpuid-replace-nested.patch [bz#691638]
- kvm-i386-kvm-set-CPUID_EXT_HYPERVISOR-on-kvm_arch_get_su.patch [bz#691638]
- kvm-i386-kvm-set-CPUID_EXT_TSC_DEADLINE_TIMER-on-kvm_arc.patch [bz#691638]
- kvm-i386-kvm-x2apic-is-not-supported-without-in-kernel-i.patch [bz#691638]
- kvm-target-i385-make-cpu_x86_fill_host-void.patch [bz#691638]
- kvm-target-i386-cpu-make-cpu-host-check-enforce-code-KVM.patch [bz#691638]
- kvm-target-i386-kvm_cpu_fill_host-use-GET_SUPPORTED_CPUI.patch [bz#691638]
- Resolves: bz#691638
  (x2apic is not exported to guest when boot guest with -cpu host)

* Thu Nov 01 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.332.el6
- kvm-Fixes-related-to-processing-of-qemu-s-numa-option.patch [bz#733720]
- kvm-create-kvm_arch_vcpu_id-function.patch [bz#733720]
- kvm-target-i386-kvm-set-vcpu_id-to-APIC-ID-instead-of-CP.patch [bz#733720]
- kvm-fw_cfg-remove-FW_CFG_MAX_CPUS-from-fw_cfg_init.patch [bz#733720]
- kvm-pc-set-CPU-APIC-ID-explicitly.patch [bz#733720]
- kvm-pc-set-fw_cfg-data-based-on-APIC-ID-calculation.patch [bz#733720]
- kvm-CPU-hotplug-use-apic_id_for_cpu.patch [bz#733720]
- kvm-target-i386-topology-and-APIC-ID-utility-functions.patch [bz#733720]
- kvm-sysemu.h-add-extern-declarations-for-smp_cores-smp_t.patch [bz#733720]
- kvm-pc-generate-APIC-IDs-according-to-CPU-topology.patch [bz#733720]
- Resolves: bz#733720
  ('-smp 24,sockets=2,cores=6,threads=2' exposes 8 & 4 cores to CPUs on RHEL6 Linux guests)

* Tue Oct 23 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.331.el6
- kvm-scsi-simplify-handling-of-the-VPD-page-length-field.patch [bz#831102]
- kvm-scsi-block-remove-properties-that-are-not-relevant-f.patch [bz#831102]
- kvm-scsi-more-fixes-to-properties-for-passthrough-device.patch [bz#831102]
- Resolves: bz#831102
  (add the ability to set a wwn for SCSI disks)

* Mon Oct 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.330.el6
- kvm-e1000-switch-to-symbolic-names-for-pci-registers.patch [bz#866736]
- kvm-pci-interrupt-pin-documentation-update.patch [bz#866736]
- kvm-e1000-Don-t-set-the-Capabilities-List-bit.patch [bz#866736]
- kvm-qemu-ga-pass-error-message-to-OpenFileFailed-error.patch [bz#867983]
- Resolves: bz#866736
  ([hck][svvp] PCI Hardware Compliance Test for Systems job failed when e1000 is in use)
- Resolves: bz#867983
  (qemu-ga: empty reason string for OpenFileFailed error)

* Thu Oct 18 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.329.el6
- kvm-Introduce-machine-command-option.patch [bz#859447]
- kvm-Generalize-machine-command-line-option.patch [bz#859447]
- kvm-Allow-to-leave-type-on-default-in-machine.patch [bz#859447]
- kvm-qemu-option-Introduce-default-mechanism.patch [bz#859447]
- kvm-qemu-option-Add-support-for-merged-QemuOptsLists.patch [bz#859447]
- kvm-Make-machine-enable-kvm-options-merge-into-a-single-.patch [bz#859447]
- kvm-memory-add-machine-dump-guest-core-on-off.patch [bz#859447]
- Resolves: bz#859447
  ([Hitachi 6.4 FEAT] Coredump filter to exclude KVM guest OS memory out of QEMU process)

* Wed Oct 17 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.328.el6
- kvm-raw-posix-don-t-assign-bs-read_only.patch [bz#767233]
- kvm-block-clarify-the-meaning-of-BDRV_O_NOCACHE.patch [bz#767233]
- kvm-qcow2-Update-whole-header-at-once.patch [bz#767233]
- kvm-qcow2-Keep-unknown-header-extension-when-rewriting-h.patch [bz#767233]
- kvm-block-push-bdrv_change_backing_file-error-checking-u.patch [bz#767233]
- kvm-block-update-in-memory-backing-file-and-format.patch [bz#767233]
- kvm-stream-fix-ratelimiting-corner-case.patch [bz#767233]
- kvm-stream-tweak-usage-of-bdrv_co_is_allocated.patch [bz#767233]
- kvm-stream-move-is_allocated_above-to-block.c.patch [bz#767233]
- kvm-block-New-bdrv_get_flags.patch [bz#767233]
- kvm-block-correctly-set-the-keep_read_only-flag.patch [bz#767233]
- kvm-block-Framework-for-reopening-files-safely.patch [bz#767233]
- kvm-block-move-aio-initialization-into-a-helper-function.patch [bz#767233]
- kvm-block-move-open-flag-parsing-in-raw-block-drivers-to.patch [bz#767233]
- kvm-block-use-BDRV_O_NOCACHE-instead-of-s-aligned_buf-in.patch [bz#767233]
- kvm-block-purge-s-aligned_buf-and-s-aligned_buf_size-fro.patch [bz#767233]
- kvm-cutils-break-fcntl_setfl-out-into-accesible-helper-f.patch [bz#767233]
- kvm-block-raw-posix-image-file-reopen.patch [bz#767233]
- kvm-block-raw-image-file-reopen.patch [bz#767233]
- kvm-block-qed-image-file-reopen.patch [bz#767233]
- kvm-block-qcow2-image-file-reopen.patch [bz#767233]
- kvm-block-qcow-image-file-reopen.patch [bz#767233]
- kvm-block-vdi-image-file-reopen.patch [bz#767233]
- kvm-block-vpc-image-file-reopen.patch [bz#767233]
- kvm-block-convert-bdrv_commit-to-use-bdrv_reopen.patch [bz#767233]
- kvm-block-remove-keep_read_only-flag-from-BlockDriverSta.patch [bz#767233]
- kvm-block-after-creating-a-live-snapshot-make-old-image-.patch [bz#767233]
- kvm-block-add-support-functions-for-live-commit-to-find-.patch [bz#767233]
- kvm-qerror-add-QERR_INVALID_PARAMETER_COMBINATION.patch [bz#767233]
- kvm-qerror-Error-types-for-block-commit.patch [bz#767233]
- kvm-block-add-live-block-commit-functionality.patch [bz#767233]
- kvm-block-helper-function-to-find-the-base-image-of-a-ch.patch [bz#767233]
- kvm-QAPI-add-command-for-live-block-commit-block-commit.patch [bz#767233]
- kvm-block-make-bdrv_find_backing_image-compare-canonical.patch [bz#767233]
- kvm-block-in-commit-determine-base-image-from-the-top-im.patch [bz#767233]
- Resolves: bz#767233
  (RFE - Support advanced (bi-directional) live deletion / merge of snapshots)

* Mon Oct 15 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.327.el6
- kvm-fdc-fix-DIR-register-migration.patch [bz#854474]
- kvm-fdc-introduce-new-property-migrate_dir.patch [bz#854474]
- kvm-usb-redir-Change-usbredir_open_chardev-into-usbredir.patch [bz#861331]
- kvm-usb-redir-Don-t-make-migration-fail-in-none-seamless.patch [bz#861331]
- Resolves: bz#854474
  (floppy I/O error after do live migration with floppy in used)
- Resolves: bz#861331
  (Allow non-seamless migration of vms with usb-redir devices)

* Mon Oct 15 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.326.el6
- kvm-bitmap-add-a-generic-bitmap-and-bitops-library.patch [bz#844627]
- kvm-bitops-fix-test_and_change_bit.patch [bz#844627]
- kvm-add-hierarchical-bitmap-data-type-and-test-cases.patch [bz#844627]
- kvm-block-implement-dirty-bitmap-using-HBitmap.patch [bz#844627]
- kvm-block-return-count-of-dirty-sectors-not-chunks.patch [bz#844627]
- kvm-block-allow-customizing-the-granularity-of-the-dirty.patch [bz#844627]
- kvm-mirror-use-target-cluster-size-as-granularity.patch [bz#844627]
- kvm-qxl-don-t-abort-on-guest-trigerrable-ring-indices-mi.patch [bz#770842]
- kvm-qxl-Slot-sanity-check-in-qxl_phys2virt-is-off-by-one.patch [bz#770842]
- kvm-hw-qxl.c-qxl_phys2virt-replace-panics-with-guest_bug.patch [bz#770842]
- kvm-qxl-check-for-NULL-return-from-qxl_phys2virt.patch [bz#770842]
- kvm-qxl-replace-panic-with-guest-bug-in-qxl_track_comman.patch [bz#770842]
- kvm-qxl-qxl_add_memslot-remove-guest-trigerrable-panics.patch [bz#770842]
- kvm-qxl-don-t-assert-on-guest-create_guest_primary.patch [bz#770842]
- kvm-qxl-Add-missing-GCC_FMT_ATTR-and-fix-format-specifie.patch [bz#770842]
- kvm-qxl-ioport_write-remove-guest-trigerrable-abort.patch [bz#770842]
- kvm-hw-qxl-s-qxl_guest_bug-qxl_set_guest_bug.patch [bz#770842]
- kvm-hw-qxl-ignore-guest-from-guestbug-until-reset.patch [bz#770842]
- kvm-qxl-reset-current_async-on-qxl_soft_reset.patch [bz#770842]
- kvm-qxl-update_area_io-guest_bug-on-invalid-parameters.patch [bz#770842]
- kvm-qxl-disallow-unknown-revisions.patch [bz#770842]
- kvm-qxl-add-QXL_IO_MONITORS_CONFIG_ASYNC.patch [bz#770842]
- kvm-configure-print-spice-protocol-and-spice-server-vers.patch [bz#770842]
- kvm-qemu-ga-switch-to-the-new-error-format-on-the-wire.patch [bz#797227]
- kvm-rtl8139-implement-8139cp-link-status.patch [bz#852965]
- kvm-e1000-update-nc.link_down-in-e1000_post_load.patch [bz#852965]
- kvm-virtio-net-update-nc.link_down-in-virtio_net_load.patch [bz#852965]
- Resolves: bz#770842
  (RFE: qemu-kvm: qxl device should support multiple monitors)
- Resolves: bz#797227
  (qemu guest agent should report error description)
- Resolves: bz#844627
  (copy cluster-sized blocks to the target of live storage migration)
- Resolves: bz#852965
  (set_link can not change rtl8139 network card's status)

* Mon Oct 15 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.325.el6
- kvm-x86-cpuid-add-missing-CPUID-feature-flag-names.patch [bz#843084]
- kvm-x86-Implement-SMEP-and-SMAP.patch [bz#843084]
- kvm-i386-cpu-add-missing-CPUID-EAX-7-ECX-0-flag-names.patch [bz#843084]
- kvm-add-missing-CPUID-bit-constants.patch [bz#843084]
- kvm-add-Haswell-CPU-model.patch [bz#843084]
- kvm-scsi-introduce-hotplug-and-hot_unplug-interfaces-for.patch [bz#808660]
- kvm-scsi-establish-precedence-levels-for-unit-attention.patch [bz#808660]
- kvm-scsi-disk-report-resized-disk-via-sense-codes.patch [bz#808660]
- kvm-scsi-report-parameter-changes-to-HBA-drivers.patch [bz#808660]
- kvm-virtio-scsi-do-not-crash-on-adding-buffers-to-the-ev.patch [bz#808660]
- kvm-virtio-scsi-Implement-hotplug-support-for-virtio-scs.patch [bz#808660]
- kvm-virtio-scsi-Report-missed-events.patch [bz#808660]
- kvm-virtio-scsi-do-not-report-dropped-events-after-reset.patch [bz#808660]
- kvm-virtio-scsi-report-parameter-change-events.patch [bz#808660]
- kvm-virtio-scsi-add-backwards-compatibility-properties-f.patch [bz#808660]
- kvm-x86-Fix-DPL-write-back-of-segment-registers.patch [bz#852612]
- kvm-x86-Remove-obsolete-SS.RPL-DPL-aligment.patch [bz#852612]
- Resolves: bz#808660
  (RFE - Virtio-scsi should support block_resize)
- Resolves: bz#843084
  ([Intel 6.4 FEAT] Haswell new instructions support for qemu-kvm)
- Resolves: bz#852612
  (guest hang if query cpu frequently during pxe boot)

* Mon Oct 15 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.324.el6
- kvm-qxl-Add-set_client_capabilities-interface-to-QXLInte.patch [bz#860017]
- kvm-qxl-Ignore-set_client_capabilities-pre-post-migrate.patch [bz#860017]
- kvm-qxl-Set-default-revision-to-4.patch [bz#860017]
- Resolves: bz#860017
  ([RFE] -spice- Add rendering support in order to improve spice performance)

* Fri Oct 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.323.el6
- kvm-create_config-separate-section-for-qemu_-dir-variabl.patch [bz#856422]
- kvm-configure-add-localstatedir.patch [bz#856422]
- kvm-qemu-ga-use-state-dir-from-CONFIG_QEMU_LOCALSTATEDIR.patch [bz#856422]
- kvm-qemu-ga-ga_open_pidfile-add-new-line-to-pidfile.patch [bz#856422]
- kvm-spec-pass-localstatedir-in-configure.patch [bz#856422]
- kvm-add-tsc-deadline-flag-name-to-feature_ecx-table.patch [bz#767944]
- kvm-qerror-OpenFileFailed-add-__com.redhat_error_message.patch [bz#806775]
- kvm-monitor-memory_save-pass-error-message-to-OpenFileFa.patch [bz#806775]
- kvm-dump-qmp_dump_guest_memory-pass-error-message-to-Ope.patch [bz#806775]
- kvm-blockdev-do_change_block-pass-error-message-to-OpenF.patch [bz#806775]
- kvm-blockdev-qmp_transaction-pass-error-message-to-OpenF.patch [bz#806775]
- kvm-blockdev-drive_reopen-pass-error-message-to-OpenFile.patch [bz#806775]
- Resolves: bz#767944
  ([Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm)
- Resolves: bz#806775
  (QMP: add errno information to OpenFileFailed error)
- Resolves: bz#856422
  (qemu-ga: after reboot of frozen fs, guest-fsfreeze-status is wrong)

* Wed Oct 10 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.322.el6
- kvm-spice-switch-to-queue-for-vga-mode-updates.patch [bz#854528]
- kvm-spice-split-qemu_spice_create_update.patch [bz#854528]
- kvm-spice-add-screen-mirror.patch [bz#854528]
- kvm-spice-send-updates-only-for-changed-screen-content.patch [bz#854528]
- kvm-tracetool-support-format-strings-containing-parenthe.patch [bz#820136]
- kvm-qxl-add-dev-id-to-guest-prints.patch [bz#820136]
- kvm-qxl-logger-add-timestamp-to-command-log.patch [bz#820136]
- kvm-hw-qxl-Fix-format-string-errors.patch [bz#820136]
- kvm-qxl-switch-qxl.c-to-trace-events.patch [bz#820136]
- kvm-qxl-better-cleanup-for-surface-destroy.patch [bz#820136]
- kvm-qxl-qxl_render.c-add-trace-events.patch [bz#820136]
- Resolves: bz#820136
  (RFE: Improve qxl logging by adding trace-events from upstream)
- Resolves: bz#854528
  (spice: fix vga mode performance)

* Tue Oct 09 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.321.el6
- kvm-support-TSC-deadline-MSR-with-subsection.patch [bz#767944]
- kvm-doc-correct-default-NIC-to-rtl8139.patch [bz#833687]
- kvm-Add-API-to-create-memory-mapping-list.patch [bz#832458]
- kvm-exec-add-cpu_physical_memory_is_io.patch [bz#832458]
- kvm-target-i386-cpu.h-add-CPUArchState.patch [bz#832458]
- kvm-implement-cpu_get_memory_mapping.patch [bz#832458]
- kvm-Add-API-to-check-whether-paging-mode-is-enabled.patch [bz#832458]
- kvm-Add-API-to-get-memory-mapping.patch [bz#832458]
- kvm-Add-API-to-get-memory-mapping-without-do-paging.patch [bz#832458]
- kvm-target-i386-Add-API-to-write-elf-notes-to-core-file.patch [bz#832458]
- kvm-target-i386-Add-API-to-write-cpu-status-to-core-file.patch [bz#832458]
- kvm-target-i386-add-API-to-get-dump-info.patch [bz#832458]
- kvm-target-i386-Add-API-to-get-note-s-size.patch [bz#832458]
- kvm-make-gdb_id-generally-avialable-and-rename-it-to-cpu.patch [bz#832458]
- kvm-hmp.h-include-qdict.h.patch [bz#832458]
- kvm-monitor-allow-qapi-and-old-hmp-to-share-the-same-dis.patch [bz#832458]
- kvm-introduce-a-new-monitor-command-dump-guest-memory-to.patch [bz#832458]
- kvm-qmp-dump-guest-memory-improve-schema-doc.patch [bz#832458]
- kvm-qmp-dump-guest-memory-improve-schema-doc-again.patch [bz#832458]
- kvm-qmp-dump-guest-memory-don-t-spin-if-non-blocking-fd-.patch [bz#832458]
- kvm-hmp-dump-guest-memory-hardcode-protocol-argument-to-.patch [bz#832458]
- Resolves: bz#767944
  ([Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm)
- Resolves: bz#832458
  ([FEAT RHEL6.4]: Support dump-guest-memory monitor command)
- Resolves: bz#833687
  (manpage says e1000 is the default nic (default is rtl8139))

* Tue Oct 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.320.el6
- kvm-stream-do-not-copy-unallocated-sectors-from-the-base.patch [bz#832336]
- kvm-x86-cpuid-add-host-to-the-list-of-supported-CPU-mode.patch [bz#833152]
- kvm-target-i386-Fold-cpu-cpuid-model-output-into-cpu-hel.patch [bz#833152]
- kvm-target-i386-Add-missing-CPUID_-constants.patch [bz#833152]
- kvm-target-i386-Move-CPU-models-from-cpus-x86_64.conf-to.patch [bz#833152]
- kvm-Eliminate-cpus-x86_64.conf-file-v2.patch [bz#833152]
- kvm-target-i386-x86_cpudef_setup-coding-style-change.patch [bz#833152]
- kvm-target-i386-Kill-cpudef-config-section-support.patch [bz#833152]
- kvm-target-i386-Drop-unused-setscalar-macro.patch [bz#833152]
- kvm-target-i386-move-compatibility-static-variables-to-t.patch [bz#833152]
- kvm-target-i386-group-declarations-of-compatibility-func.patch [bz#833152]
- kvm-disable-SEP-on-all-CPU-models.patch [bz#745717]
- kvm-replace-disable_cpuid_leaf10-with-set_pmu_passthroug.patch [bz#833152 bz#852083]
- kvm-enable-PMU-emulation-only-on-cpu-host-v3.patch [bz#852083]
- kvm-expose-tsc-deadline-timer-feature-to-guest.patch [bz#767944]
- kvm-enable-TSC-deadline-on-SandyBridge-CPU-model-on-rhel.patch [bz#767944]
- kvm-introduce-CPU-model-compat-function-to-set-level-fie.patch [bz#689665]
- kvm-set-level-4-on-CPU-models-Conroe-Penryn-Nehalem-v2.patch [bz#689665]
- kvm-convert-boot-to-QemuOpts.patch [bz#854191]
- kvm-add-a-boot-parameter-to-set-reboot-timeout.patch [bz#854191]
- kvm-sockets-Drop-sockets_debug-debug-code.patch [bz#680356]
- kvm-sockets-Clean-up-inet_listen_opts-s-convoluted-bind-.patch [bz#680356]
- kvm-qerror-add-five-qerror-strings.patch [bz#680356]
- kvm-sockets-change-inet_connect-to-support-nonblock-sock.patch [bz#680356]
- kvm-sockets-use-error-class-to-pass-listen-error.patch [bz#680356]
- kvm-use-inet_listen-inet_connect-to-support-ipv6-migrati.patch [bz#680356]
- kvm-socket-clean-up-redundant-assignment.patch [bz#680356]
- kvm-net-inet_connect-inet_connect_opts-add-in_progress-a.patch [bz#680356]
- kvm-migration-don-t-rely-on-any-QERR_SOCKET_.patch [bz#680356]
- kvm-qerror-drop-QERR_SOCKET_CONNECT_IN_PROGRESS.patch [bz#680356]
- kvm-Refactor-inet_connect_opts-function.patch [bz#680356]
- kvm-Separate-inet_connect-into-inet_connect-blocking-and.patch [bz#680356]
- kvm-Fix-address-handling-in-inet_nonblocking_connect.patch [bz#680356]
- kvm-Clear-handler-only-for-valid-fd.patch [bz#680356]
- Resolves: bz#680356
  (Live migration failed in ipv6 environment)
- Resolves: bz#689665
  (Specify the number of cpu cores failed with cpu model Nehalem Penryn and Conroe)
- Resolves: bz#745717
  (SEP flag is not exposed to guest, but is defined on CPU model config)
- Resolves: bz#767944
  ([Intel 6.4 FEAT] VIRT: TSC deadline support for qemu-kvm)
- Resolves: bz#832336
  (block streaming "explodes" a qcow2 file to the full virtual size of the disk)
- Resolves: bz#833152
  (per-machine-type CPU models for safe migration)
- Resolves: bz#852083
  (qemu-kvm "vPMU passthrough" mode breaks migration, shouldn't be enabled by default)
- Resolves: bz#854191
  (Add a new boot parameter to set the delay time before rebooting)

* Fri Sep 28 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.319.el6
- kvm-scsi-fix-WRITE-SAME-transfer-length-and-direction.patch [bz#841171]
- kvm-scsi-Specify-the-xfer-direction-for-UNMAP-commands.patch [bz#841171]
- kvm-scsi-add-a-qdev-property-for-the-disk-s-WWN.patch [bz#831102]
- kvm-ide-Adds-wwn-hex-qdev-option.patch [bz#831102]
- spice: update build dependencies [bz#857937]
- Resolves: bz#831102
  (add the ability to set a wwn for SCSI disks)
- Resolves: bz#841171
  (fix parsing of UNMAP command)
- Resolves: bz#857937
  (exit with error if old spice-server is used and '-spice seamless-migration=on' option)

* Thu Sep 27 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.318.el6
- kvm-monitor-Fix-leakage-during-completion-processing.patch [bz#807146]
- kvm-monitor-Fix-command-completion-vs.-boolean-switches.patch [bz#807146]
- kvm-linux-headers-update-asm-kvm_para.h-to-3.6.patch [bz#835101]
- kvm-get-set-PV-EOI-MSR.patch [bz#835101]
- kvm-kill-dead-KVM_UPSTREAM-code.patch [bz#835101]
- Resolves: bz#807146
  (snapshot_blkdev tab completion for device id missing)
- Resolves: bz#835101
  (RFE: backport pv eoi support - qemu-kvm)

* Wed Sep 26 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.317.el6
- kvm-ehci-RHEL-6-only-call-ehci_advance_async_state-ehci-.patch [bz#805172]
- kvm-usb-ehci-drop-unused-isoch_pause-variable.patch [bz#805172]
- kvm-usb-ehci-Drop-unused-sofv-value.patch [bz#805172]
- kvm-usb-ehci-Ensure-frindex-writes-leave-a-valid-frindex.patch [bz#805172]
- kvm-ehci-fix-reset.patch [bz#805172]
- kvm-ehci-remove-unused-attach_poll_counter.patch [bz#805172]
- kvm-ehci-create-ehci_update_frindex.patch [bz#805172]
- kvm-ehci-rework-frame-skipping.patch [bz#805172]
- kvm-ehci-fix-ehci_qh_do_overlay.patch [bz#805172]
- kvm-ehci-fix-td-writeback.patch [bz#805172]
- kvm-ehci-Schedule-async-bh-when-IAAD-bit-gets-set.patch [bz#805172]
- kvm-ehci-simplify-ehci_state_executing.patch [bz#805172]
- kvm-ehci-Properly-report-completed-but-not-yet-processed.patch [bz#805172]
- kvm-ehci-Don-t-process-too-much-frames-in-1-timer-tick-v.patch [bz#805172]
- kvm-ehci-Don-t-set-seen-to-0-when-removing-unseen-queue-.patch [bz#805172]
- kvm-ehci-Walk-async-schedule-before-and-after-migration.patch [bz#805172]
- kvm-usb-redir-Set-ep-max_packet_size-if-available.patch [bz#805172]
- kvm-usb-redir-Add-a-usbredir_reject_device-helper-functi.patch [bz#805172]
- kvm-usb-redir-Change-cancelled-packet-code-into-a-generi.patch [bz#805172]
- kvm-usb-redir-Add-an-already_in_flight-packet-id-queue.patch [bz#805172]
- kvm-usb-redir-Store-max_packet_size-in-endp_data.patch [bz#805172]
- kvm-usb-redir-Add-support-for-migration.patch [bz#805172]
- kvm-usb-redir-Add-chardev-open-close-debug-logging.patch [bz#805172]
- Resolves: bz#805172
  (Add live migration support for USB)

* Thu Sep 20 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.316.el6
- Add missing patch, that was already supposed to be in the paackage
  kvm-scsi-do-not-require-a-minimum-allocation-length-2.patch
- Regenerated kvm-scsi-remove-useless-debug-messages.patch to match
  what was submitted/reviewed
- Resolves: bz#825188
  (make scsi-testsuite pass)

* Wed Sep 19 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.315.el6
- kvm-usb-unique-packet-ids.patch [bz#805172]
- kvm-usb-redir-Notify-our-peer-when-we-reject-a-device-du.patch [bz#805172]
- kvm-usb-redir-Reset-device-address-and-speed-on-disconne.patch [bz#805172]
- kvm-usb-redir-Correctly-handle-the-usb_redir_babble-usbr.patch [bz#805172]
- kvm-usb-redir-Never-return-USB_RET_NAK-for-async-handled.patch [bz#805172]
- kvm-usb-redir-Don-t-delay-handling-of-open-events-to-a-b.patch [bz#805172]
- kvm-usb-redir-Get-rid-of-async-struct-get-member.patch [bz#805172]
- kvm-usb-redir-Get-rid-of-local-shadow-copy-of-packet-hea.patch [bz#805172]
- kvm-usb-redir-Get-rid-of-unused-async-struct-dev-member.patch [bz#805172]
- kvm-usb-redir-Move-to-core-packet-id-handling.patch [bz#805172]
- kvm-usb-redir-Return-babble-when-getting-more-bulk-data-.patch [bz#805172]
- kvm-usb-redir-Convert-to-new-libusbredirparser-0.5-API.patch [bz#805172]
- kvm-disable-s3-s4-by-default.patch [bz#848369]
- Require usbredir-devel >= 0.5 [bz#848369]
- Resolves: bz#848369
  (S3/S4 should be disabled by default)
- Related: bz#805172
  (Add live migration support for USB)

* Tue Sep 18 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.314.el6
- kvm-net-notify-iothread-after-flushing-queue.patch [bz#852665]
- kvm-e1000-flush-queue-whenever-can_receive-can-go-from-f.patch [bz#852665]
- kvm-spice-abort-on-invalid-streaming-cmdline-params.patch [bz#831708]
- kvm-skip-media-change-notify-on-reopen.patch [bz#849657]
- kvm-qmp-qmp-events.txt-add-missing-doc-for-the-SUSPEND-e.patch [bz#827499]
- kvm-qmp-add-SUSPEND_DISK-event.patch [bz#827499]
- Resolves: bz#827499
  (RFE: QMP notification for S3/S4 events)
- Resolves: bz#831708
  (Spice-Server, VM Creation works when a bad value is entered for streaming-video)
- Resolves: bz#849657
  (scsi devices see an unit attention condition on migration)
- Resolves: bz#852665
  (Backport e1000 receive queue fixes from upstream)

* Wed Sep 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.313.el6
- kvm-qemu-options.hx-Improve-read-write-config-options-de.patch [bz#818134]
- kvm-scsi-disk-Fail-medium-writes-with-proper-sense-for-r.patch [bz#846268]
- kvm-Add-PIIX4-properties-to-control-PM-system-states.patch [bz#827503]
- kvm-vl-Tighten-parsing-of-m-argument.patch [bz#755594]
- kvm-vl-Round-argument-of-m-up-to-multiple-of-8KiB.patch [bz#755594]
- kvm-vl-Round-argument-of-m-up-to-multiple-of-2MiB-instea.patch [bz#755594]
- Resolves: bz#755594
  (-m 1 crashes)
- Resolves: bz#818134
  ('-writeconfig/-readconfig' option need to update in qemu-kvm manpage)
- Resolves: bz#827503
  (Config s3/s4 per VM - in qemu-kvm)
- Resolves: bz#846268
  ([virtio-win][scsi] Windows guest Core dumped when trying to initialize readonly scsi data disk)

* Thu Sep 06 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.312.el6
- kvm-uhci-zap-uhci_pre_save.patch [bz#805172]
- kvm-ehci-move-async-schedule-to-bottom-half.patch [bz#805172]
- kvm-ehci-schedule-async-bh-on-async-packet-completion.patch [bz#805172]
- kvm-ehci-kick-async-schedule-on-wakeup.patch [bz#805172]
- kvm-ehci-Kick-async-schedule-on-wakeup-in-the-non-compan.patch [bz#805172]
- kvm-ehci-raise-irq-in-the-frame-timer.patch [bz#805172]
- kvm-ehci-add-live-migration-support.patch [bz#805172]
- kvm-ehci-fix-Interrupt-Threshold-Control-implementation.patch [bz#805172]
- kvm-scsi-prepare-migration-code-for-usb-storage-support.patch [bz#805172]
- kvm-Endian-fix-an-assertion-in-usb-msd.patch [bz#805172]
- kvm-usb-storage-remove-MSDState-residue.patch [bz#805172]
- kvm-usb-storage-add-usb_msd_packet_complete.patch [bz#805172]
- kvm-usb-storage-add-scsi_off-remove-scsi_buf.patch [bz#805172]
- kvm-usb-storage-migration-support.patch [bz#805172]
- kvm-usb-storage-DPRINTF-fixup.patch [bz#805172]
- kvm-usb-restore-USBDevice-attached-on-vmload.patch [bz#805172]
- kvm-usb-host-attach-only-to-running-guest.patch [bz#805172]
- kvm-usb-host-live-migration-support.patch [bz#805172]
- Resolves: bz#805172
  (Add live migration support for USB)

* Wed Sep 05 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.311.el6
- kvm-qemu-options.hx-Improve-nodefaults-description.patch [bz#817224]
- kvm-Allow-silent-system-resets.patch [bz#850927]
- kvm-qmp-don-t-emit-the-RESET-event-on-wakeup-from-S3.patch [bz#850927]
- kvm-qmp-emit-the-WAKEUP-event-when-the-guest-is-put-to-r.patch [bz#850927]
- kvm-reset-PMBA-and-PMREGMISC-PIIX4-registers.patch [bz#854304]
- Resolves: bz#817224
  (there is no "-nodefaults" option help doc in qemu-kvm man page)
- Resolves: bz#850927
  (QMP: two events related issues on S3 wakeup)
- Resolves: bz#854304
  (reset PMBA and PMREGMISC PIIX4 registers)

* Tue Sep 04 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.310.el6
- kvm-pc-refactor-RHEL-compat-code.patch [bz#835101]
- kvm-cpuid-disable-pv-eoi-for-6.3-and-older-compat-types.patch [bz#835101]
- kvm-kvm_pv_eoi-add-flag-support.patch [bz#835101]
- kvm-spice-notify-spice-server-on-vm-start-stop.patch [bz#836133]
- kvm-spice-notify-on-vm-state-change-only-via-spice_serve.patch [bz#836133]
- kvm-spice-migration-add-QEVENT_SPICE_MIGRATE_COMPLETED.patch [bz#836133]
- kvm-spice-add-migrated-flag-to-spice-info.patch [bz#836133]
- kvm-spice-adding-seamless-migration-option-to-the-comman.patch [bz#836133]
- kvm-spice-increase-the-verbosity-of-spice-section-in-qem.patch [bz#836133]
- kvm-disable-rdtscp-on-all-CPU-model-definitions.patch [bz#814426]
- Resolves: bz#814426
  ("rdtscp" flag defined on SandyBridge and Opteron models, but not supported by the kernel)
- Resolves: bz#835101
  (RFE: backport pv eoi support - qemu-kvm)
- Resolves: bz#836133
  (spice migration: prevent race with libvirt)

* Mon Sep 03 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.309.el6
- kvm-qxl-render-fix-broken-vnc-spice-since-commit-f934493.patch [bz#851143]
- kvm-scsi-add-missing-test-for-cancelled-request.patch [bz#805501 bz#805501, bz#808664]
- kvm-scsi-make-code-more-homogeneous-in-AIO-callback-func.patch [bz#814084]
- kvm-scsi-move-scsi_flush_complete-around.patch [bz#814084]
- kvm-scsi-add-support-for-FUA-on-writes.patch [bz#814084]
- kvm-scsi-force-unit-access-on-VERIFY.patch [bz#808664 bz#808664, bz#805501]
- kvm-scsi-disk-more-assertions-and-resets-for-aiocb.patch [bz#808664 bz#808664, bz#805501]
- kvm-virtio-scsi-do-not-compare-32-bit-QEMU-tags-against-.patch [bz#808664]
- kvm-vvfat-Use-cache-unsafe.patch [bz#825691]
- kvm-block-prevent-snapshot-mode-TMPDIR-symlink-attack.patch [bz#825691]
- CVE: CVE-2012-2652
- Resolves: bz#825691
  ( CVE-2012-2652 qemu: vulnerable to temporary file symlink attacks [rhel-6.4])
- Resolves: bz#805501
  (qemu-kvm core dumped while sending system_reset to a virtio-scsi guest)
- Resolves: bz#805501,
  (qemu-kvm core dumped while sending system_reset to a virtio-scsi guest)
- Resolves: bz#808664
  (With virtio-scsi disk guest can't resume form "No space left on device")
- Resolves: bz#808664,
  (With virtio-scsi disk guest can't resume form "No space left on device")
- Resolves: bz#814084
  (scsi disk emulation doesn't enforce FUA (Force Unit Access) on writes)
- Resolves: bz#851143
  (qemu-kvm segfaulting when running a VM)

* Thu Aug 30 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.308.el6
- kvm-console-bounds-check-whenever-changing-the-cursor-du.patch [bz#851258]
- Resolves: bz#851258
  (EMBARGOED CVE-2012-3515 qemu: VT100 emulation vulnerability [rhel-6.4])

* Tue Aug 21 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.307.el6
- Update information: Add bug 805533 information to changelog (fix for 827612 fixed also 805533)
- kvm-hda-move-input-widgets-from-duplex-to-common.patch [bz#801063]
- kvm-hda-add-hda-micro-codec.patch [bz#801063]
- kvm-hda-fix-codec-ids.patch [bz#801063]
- Resolves: bz#801063
  ([RFE] Ability to configure sound pass-through to appear as MIC as opposed to line-in)
- Resolves: bz#805533
  (qemu-ga: possible race while suspending the guest)

* Tue Aug 21 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.306.el6
- kvm-kvmclock-guest-stop-notification.patch [bz#831614]
- kvm-usb-storage-fix-SYNCHRONIZE_CACHE.patch [bz#839957]
- kvm-usb-change-VID-PID-for-usb-hub-and-usb-msd-to-preven.patch [bz#813713]
- kvm-usb-add-serial-number-generator.patch [bz#813713]
- kvm-add-rhel6.4.0-machine-type.patch [bz#813713]
- kvm-usb-add-compat-property-to-skip-unique-serial-number.patch [bz#813713]
- kvm-qemu-img-Fix-segmentation-fault.patch [bz#846954]
- kvm-qemu-img-Fix-qemu-img-convert-obacking_file.patch [bz#816575]
- Resolves: bz#813713
  (Windows guest can't drive more than 21 usb-storage devices)
- Resolves: bz#816575
  (backing clusters of the image convert with -B  are allocated when they shouldn't)
- Resolves: bz#831614
  ([6.4 FEAT] KVM suppress cpu softlockup message after suspend/resume of a VM)
- Resolves: bz#839957
  (usb-storage: SYNCHRONIZE_CACHE is broken)
- Resolves: bz#846954
  (qemu-img convert segfaults on zeroed image)

* Thu Aug 16 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.305.el6
- kvm-e1000-Pad-short-frames-to-minimum-size-60-bytes.patch [bz#607510 bz#819915 bz#819915]
- kvm-e1000-Fix-multi-descriptor-packet-checksum-offload.patch [bz#607510 bz#819915 bz#819915]
- kvm-e1000-introduce-bits-of-PHY-control-register.patch [bz#607510 bz#607510 bz#819915]
- kvm-e1000-conditionally-raise-irq-at-the-end-of-MDI-cycl.patch [bz#607510 bz#607510 bz#819915]
- kvm-e1000-Preserve-link-state-across-device-reset.patch [bz#607510 bz#607510 bz#819915]
- kvm-e1000-move-reset-function-earlier-in-file.patch [bz#607510 bz#607510 bz#819915]
- kvm-e1000-introduce-helpers-to-manipulate-link-status.patch [bz#607510 bz#607510 bz#819915]
- kvm-e1000-introduce-bit-for-debugging-PHY-emulation.patch [bz#607510 bz#607510 bz#819915]
- kvm-e1000-link-auto-negotiation-emulation.patch [bz#607510 bz#607510 bz#819915]
- Resolves: bz#607510
  (Windows7 guest cannot resume after suspended to disk after plenty of pause:resume iterations - e1000)
- Resolves: bz#819915
  (e1000: Fix multi-descriptor packet checksum offload)

* Tue Aug 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.304.el6
- kvm-qemu-options.hx-Fix-set_password-and-expire_password.patch [bz#813633]
- Resolves: bz#813633
  (need to update qemu-kvm about "-vnc" option for "password" in man page)

* Mon Aug 13 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.303.el6
- kvm-acpi_piix4-Disallow-write-to-up-down-PCI-hotplug-reg.patch [bz#807391]
- kvm-acpi_piix4-Fix-PCI-hotplug-race.patch [bz#807391]
- kvm-acpi_piix4-Remove-PCI_RMV_BASE-write-code.patch [bz#807391]
- kvm-acpi_piix4-Re-define-PCI-hotplug-eject-register-read.patch [bz#807391]
- kvm-acpi-explicitly-account-for-1-device-per-slot.patch [bz#807391]
- Resolves: bz#807391
  (lost hotplug events)

* Thu Aug 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.302.el6
- kvm-fdc-DIR-Digital-Input-Register-should-return-status-.patch [bz#729244]
- kvm-fdc-simplify-media-change-handling.patch [bz#729244]
- kvm-fdc-fix-media-detection.patch [bz#729244]
- kvm-fdc-fix-implied-seek-while-there-is-no-media-in-driv.patch [bz#729244]
- kvm-fdc-rewrite-seek-and-DSKCHG-bit-handling.patch [bz#729244]
- kvm-fdc-fix-interrupt-handling.patch [bz#729244]
- kvm-qemu-keymaps-Finnish-keyboard-mapping-broken.patch [bz#794653]
- Resolves: bz#729244
  (floppy does not show in guest after change floppy from no inserted to new file)
- Resolves: bz#794653
  (Finnish keymap has errors)

* Tue Jul 31 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.301.el6
- kvm-audio-streaming-from-usb-devices.patch [bz#808653 bz#831549]
- kvm-usb-uhci-fix-commit-8e65b7c04965c8355e4ce43211582b6b.patch [bz#808653 bz#831549]
- kvm-usb-uhci-fix-expire-time-initialization.patch [bz#808653 bz#831549]
- kvm-usb-uhci-implement-bandwidth-management.patch [bz#808653 bz#831549]
- kvm-uhci-fix-bandwidth-management.patch [bz#808653 bz#831549]
- Resolves: bz#808653
  (Audio quality is very bad when playing audio via passthroughed USB speaker in guest)
- Resolves: bz#831549
  (unmount of usb storage in RHEL guest takes around 50mins)

* Tue Jul 31 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.300.el6
- kvm-e1000-use-MII-status-register-for-link-up-down.patch [bz#643577]
- kvm-pci-assign-Use-struct-for-MSI-X-table.patch [bz#784496]
- kvm-pci-assign-Only-calculate-maximum-MSI-X-vector-entri.patch [bz#784496]
- kvm-pci-assign-Proper-initialization-for-MSI-X-table.patch [bz#784496]
- kvm-pci-assign-Allocate-entries-for-all-MSI-X-vectors.patch [bz#784496]
- kvm-pci-assign-Update-MSI-X-config-based-on-table-writes.patch [bz#784496]
- Resolves: bz#643577
  (Lost packet during bonding test with e1000 nic)
- Resolves: bz#784496
  (Device assignment doesn't get updated for guest irq pinning)

* Wed Jul 25 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.299.el6
- kvm-qdev-properties-restrict-uint32-input-values-between.patch [bz#797728]
- Resolves: bz#797728
  (qemu-kvm allows a value of -1 for uint32 qdev property types)

* Mon Jul 23 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.298.el6
- kvm-Revert-guest-agent-remove-unsupported-guest-agent-co.patch [bz#819900]
- kvm-qemu-ga-add-guest-file-operations-in-qemu-ga-BLACKLI.patch [bz#819900]
- kvm-virtio-console-Fix-failure-on-unconnected-pty.patch [bz#839156]
- kvm-scsi-do-not-require-a-minimum-allocation-length-for-.patch [bz#825188]
- kvm-scsi-set-VALID-bit-to-0-in-fixed-format-sense-data.patch [bz#825188]
- kvm-scsi-do-not-report-bogus-overruns-for-commands-in-th.patch [bz#825188]
- kvm-scsi-do-not-require-a-minimum-allocation-length-for-.patch [bz#825188]
- kvm-scsi-remove-useless-debug-messages.patch [bz#825188]
- kvm-vnc-add-a-more-descriptive-error-message.patch [bz#796043]
- Resolves: bz#796043
  ('getaddrinfo(127.0.0.1,5902): Name or service not known' when starting guest on host with IPv6 only)
- Resolves: bz#819900
  ([6.3 FEAT] add guest-file-* operations into posix qemu-ga)
- Resolves: bz#825188
  (make scsi-testsuite pass)
- Resolves: bz#839156
  (Fedora 16 and 17 guests hang during boot)

* Tue Jul 17 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.297.el6
- kvm-remove-broken-code-for-tty.patch [bz#806768]
- kvm-add-qemu_chr_set_echo.patch [bz#806768]
- kvm-move-atexit-term_exit-and-O_NONBLOCK-to-qemu_chr_ope.patch [bz#806768]
- kvm-add-set_echo-implementation-for-qemu_chr_stdio.patch [bz#806768]
- kvm-block-don-t-create-mirror-block-job-if-the-target-bd.patch [bz#814102]
- kvm-hda-audio-send-v1-migration-format-for-rhel6.1.0.patch [bz#821692]
- kvm-Revert-qemu-ga-make-guest-suspend-posix-only.patch [bz#827612]
- kvm-qemu-ga-win32-add-guest-suspend-stubs.patch [bz#827612]
- kvm-qemu-ga-Fix-spelling-in-documentation.patch [bz#827612]
- kvm-qemu-ga-add-win32-guest-suspend-disk-command.patch [bz#827612]
- kvm-configure-fix-mingw32-libs_qga-typo.patch [bz#827612]
- kvm-qemu-ga-add-win32-guest-suspend-ram-command.patch [bz#827612]
- kvm-qemu-ga-add-guest-network-get-interfaces-command.patch [bz#827612]
- kvm-qemu-ga-qmp_guest_network_get_interfaces-Use-qemu_ma.patch [bz#827612]
- kvm-qemu-ga-add-guest-sync-delimited.patch [bz#827612]
- kvm-qemu-ga-for-w32-fix-leaked-handle-ov.hEvent-in-ga_ch.patch [bz#827612]
- kvm-qemu-ga-fix-bsd-build-and-re-org-linux-specific-impl.patch [bz#827612]
- kvm-qemu-ga-generate-missing-stubs-for-fsfreeze.patch [bz#827612]
- kvm-qemu-ga-fix-help-output.patch [bz#827612]
- kvm-qemu-ga-guest_fsfreeze_build_mount_list-use-g_malloc.patch [bz#827612]
- kvm-qemu-ga-improve-recovery-options-for-fsfreeze.patch [bz#827612]
- kvm-qemu-ga-add-a-whitelist-for-fsfreeze-safe-commands.patch [bz#827612]
- kvm-qemu-ga-persist-tracking-of-fsfreeze-state-via-files.patch [bz#827612]
- kvm-qemu-ga-Implement-alternative-to-O_ASYNC.patch [bz#827612]
- kvm-qemu-ga-fix-some-common-typos.patch [bz#827612]
- kvm-qapi-add-support-for-command-options.patch [bz#827612]
- kvm-qemu-ga-don-t-warn-on-no-command-return.patch [bz#827612]
- kvm-qemu-ga-guest-shutdown-don-t-emit-a-success-response.patch [bz#827612]
- kvm-qemu-ga-guest-suspend-disk-don-t-emit-a-success-resp.patch [bz#827612]
- kvm-qemu-ga-guest-suspend-ram-don-t-emit-a-success-respo.patch [bz#827612]
- kvm-qemu-ga-guest-suspend-hybrid-don-t-emit-a-success-re.patch [bz#827612]
- kvm-qemu-ga-make-reopen_fd_to_null-public.patch [bz#827612]
- kvm-qemu-ga-become_daemon-reopen-standard-fds-to-dev-nul.patch [bz#827612]
- kvm-qemu-ga-guest-suspend-make-the-API-synchronous.patch [bz#827612]
- kvm-qemu-ga-guest-shutdown-become-synchronous.patch [bz#827612]
- kvm-qemu-ga-guest-shutdown-use-only-async-signal-safe-fu.patch [bz#827612]
- kvm-qemu-ga-fix-segv-after-failure-to-open-log-file.patch [bz#827612]
- kvm-configure-check-if-environ-is-declared.patch [bz#827612]
- kvm-qemu-ga-Fix-missing-environ-declaration.patch [bz#827612]
- kvm-qemu-ga-Fix-use-of-environ-on-Darwin.patch [bz#827612]
- kvm-qemu-ga-avoid-blocking-on-atime-update-when-reading-.patch [bz#827612]
- Resolves: bz#806768
  (-qmp stdio is unusable)
- Resolves: bz#814102
  (mirroring starts anyway with "existing" mode and a non-existing target)
- Resolves: bz#827612
  (Update qemu-ga to its latest upstream version)

* Thu Jul 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.296.el6
- Load KVM modules in postinstall scriptlet [bz#836498]
- kvm-isa-bus-Remove-bogus-IRQ-sharing-check.patch [bz#771624]
- Resolves: bz#836498
  (postinstall scriptlet no longer loads KVM modules)
- Resolves: bz#771624
  (guest fails with error: isa irq 4 already assigned when starting guest with more than two serial devices)

* Tue May 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.295.el6
- kvm-x86-Pass-KVMState-to-kvm_arch_get_supported_cpui.patch [bz#819562]
- kvm-Expose-CPUID-leaf-7-only-for-cpu-host-v2.patch [bz#819562]
- Resolves: bz#819562
  (SMEP is enabled unconditionally)

* Wed May 16 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.294.el6
- Re-adding patches that were missing
- kvm-scsi-fix-fw-p1-take2.patch [bz#782029]
- kvm-scsi-fix-fw-p2-take2.patch [bz#782029]
- kvm-remove-blkmirror-take2.patch [bz#802284]
- Resolves: bz#782029
  ([RFE] virtio-scsi: qemu-kvm implementation)
- Resolves: bz#802284
  (RFE: Support live migration of storage (mirroring))

* Mon May 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.293.el6
- kvm-qxl-set-size-of-PCI-IO-BAR-correctly-16-for-revision.patch [bz#698936]
- Resolves: bz#698936
  (Migrate failed from RHEL6.1 host to RHEL6.3 host with -M rhel6.1.0 (qxl and usb device related))

* Tue May 08 2012 Eduardo Habkost <ehabkost@redhat.com> - 2:0.12.1.2-2.292.el6
- kvm-block-do-not-reuse-the-backing-file-across-bdrv_clos.patch [bz#816471]
- kvm-block-Introduce-path_has_protocol-function.patch [bz#818876]
- kvm-block-Fix-the-use-of-protocols-in-backing-files.patch [bz#818876]
- kvm-block-simplify-path_is_absolute.patch [bz#818876]
- kvm-block-protect-path_has_protocol-from-filenames-with-.patch [bz#818876]
- kvm-qemu-img-make-info-backing-file-output-correct-and-e.patch [bz#818876]
- Resolves: bz#816471
  (qemu-kvm is not closing the merged images files (mirroring with "full"=true))
- Resolves: bz#818876
  (streaming to stable iscsi path names (with colons) fails to close backing file)

* Tue May 08 2012 Eduardo Habkost <ehabkost@redhat.com> - 2:0.12.1.2-2.291.el6
- kvm-fix-mirror_abort-NULL-pointer-dereference.patch [bz#818226]
- kvm-fail-drive-reopen-before-reaching-mirroring-steady-s.patch [bz#813862]
- kvm-qemu-kvm-rhev-obsoletes-all-released-qemu-kvm-versio.patch [bz#818620]
- Resolves: bz#813862
  (post-snap1 fixups to live block copy aka mirroring)
- Resolves: bz#818226
  (Weird check for null pointer in mirror_abort())
- Resolves: bz#818620
  (qemu-kvm-rhev should obsolete qemu-kvm)

* Wed May 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.290.el6
- kvm-block-change-block-job-set-speed-argument-from-value.patch [bz#813953]
- kvm-block-add-speed-optional-parameter-to-block-stream.patch [bz#813953]
- Resolves: bz#813953
  (block-job-set-speed is racy with block-stream/drive-mirror)

* Wed May 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.289.el6
- kvm-virtio-serial-bus-fix-guest_connected-init-before-dr.patch [bz#787974]
- kvm-virtio-serial-bus-Unset-guest_connected-at-reset-and.patch [bz#787974]
- Resolves: bz#787974
  (Spice Client mouse loss after live migrate windows guest with spice vmc channel and inactive guest service)

* Thu Apr 26 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.288.el6
- kvm-qcow2-Don-t-hold-cache-references-across-yield.patch [bz#812705]
- Resolves: bz#812705
  (Installing guest with cluster_size=4096, failed)

* Thu Apr 26 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.287.el6
- kvm-trace-events-Rename-next-argument.patch [bz#798676]
- kvm-Revert-raw-posix-do-not-linearize-anymore-direct-I-O.patch [bz#814617]
- Resolves: bz#798676
  (do not use next  as a variable name in qemu-kvm systemtap tapset)
- Resolves: bz#814617
  (NFS performance regression in large file sequential writes.)

* Wed Apr 25 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.286.el6
- kvm-block-make-bdrv_append-assert-that-dirty_bitmap-is-N.patch [bz#813862]
- kvm-mirror-remove-need-for-bdrv_drain_all-in-block_job_c.patch [bz#813810 bz#813862]
- kvm-block-add-block_job_sleep.patch [bz#813810 bz#813862]
- kvm-block-wait-for-job-callback-in-block_job_cancel_sync.patch [bz#813810 bz#813862]
- kvm-block-drive-reopen-fixes.patch [bz#813862]
- kvm-block-drive-mirror-fixes.patch [bz#813862]
- kvm-block-remove-duplicate-check-in-qmp_transaction.patch [bz#813862]
- kvm-mirror-do-not-reset-sector_num.patch [bz#813862]
- Resolves: bz#813810
  (plug small race window at the end of block_stream command)
- Resolves: bz#813862
  (post-snap1 fixups to live block copy aka mirroring)

* Tue Apr 24 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.285.el6
- kvm-virtio-add-missing-mb-on-enable-notification.patch [bz#804578]
- Resolves: bz#804578
  (KVM Guest with virtio network driver loses network connectivity)

* Tue Apr 24 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.284.el6
- kvm-qemu-kvm.spec.template-fix-Provides-versioning.patch [bz#800496]
- kvm-qemu-kvm.spec.template-qemu-kvm-rhev-obsolete-old-qe.patch [bz#800496]
- kvm-qxl-PC_RHEL6_1_COMPAT-make-qxl-default-revision-valu.patch [bz#698936]
- Resolves: bz#698936
  (Migrate failed in different version of RHEL 6.1 host)
- Resolves: bz#800496
  (RHEV specific qemu-kvm)

* Mon Apr 23 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.283.el6
- kvm-virtio-scsi-prepare-migration-format-for-multiqueue.patch [bz#810507]
- kvm-virtio-add-missing-mb-on-notification.patch [bz#804578]
- Resolves: bz#804578
  (KVM Guest with virtio network driver loses network connectivity)
- Resolves: bz#810507
  (prepare virtio-scsi migration format for multiqueue)

* Thu Apr 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.282.el6
- kvm-usb-storage-fix-request-canceling.patch [bz#807313]
- Resolves: bz#807313
  (qemu-kvm core dumped while booting guest with usb-storage running on uhci)

* Thu Apr 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.281.el6
- kvm-Block-streaming-disable-for-RHEL.patch [bz#808805]
- Resolves: bz#808805
  (qemu-kvm-el version should disable block_stream)

* Thu Apr 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.280.el6
- kvm-device-assignment-Disable-MSI-MSI-X-in-assigned-devi.patch [bz#798967]
- kvm-qcow2-Fix-return-value-of-alloc_refcount_block.patch [bz#812833]
- Resolves: bz#798967
  (host kernel panic when sending system_reset to windows guest with 82576 PF assigned)
- Resolves: bz#812833
  (qcow2 converting error when -o cluster_size <= 2048)

* Thu Apr 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.279.el6
- kvm-block-Set-backing_hd-to-NULL-after-deleting-it.patch [bz#812948]
- kvm-block-another-bdrv_append-fix.patch [bz#812948]
- kvm-ehci-remove-hack.patch [bz#812328]
- Resolves: bz#812328
  (qemu-kvm aborted when using multiple usb storage on Win2003 guest)
- Resolves: bz#812948
  (drive-reopen broken with snapshots)

* Wed Apr 18 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.278.el6
- kvm-block-pass-new-base-image-format-to-bdrv_change_back.patch [bz#801449 bz#811228]
- kvm-use-hyphens-in-streaming-commands-to-indicate-async-.patch [bz#812085]
- kvm-block-set-job-speed-in-block_set_speed.patch [bz#806432]
- kvm-block-bdrv_append-fixes.patch [bz#806432]
- kvm-block-fail-live-snapshot-if-disk-has-no-medium.patch [bz#806432]
- kvm-block-open-backing-file-as-read-only-when-probing-fo.patch [bz#806432]
- kvm-Count-dirty-blocks-and-expose-an-API-to-get-dirty-co.patch [bz#806432]
- kvm-block-fix-shift-in-dirty-bitmap-calculation.patch [bz#806432]
- kvm-block-fix-allocation-size-for-dirty-bitmap.patch [bz#806432]
- kvm-block-introduce-new-dirty-bitmap-functionality.patch [bz#806432]
- kvm-block-allow-interrupting-a-co_sleep_ns.patch [bz#806432]
- kvm-block-allow-doing-I-O-in-a-job-after-cancellation.patch [bz#806432]
- kvm-block-cancel-job-on-drive-reopen.patch [bz#806432]
- kvm-block-add-witness-argument-to-drive-reopen.patch [bz#806432]
- kvm-block-add-mirror-job.patch [bz#806432]
- kvm-block-copy-over-job-and-dirty-bitmap-fields-in-bdrv_.patch [bz#806432]
- kvm-block-rewrite-drive-mirror-for-mirror-job.patch [bz#806432]
- kvm-remove-blkmirror.patch [bz#806432]
- Resolves: bz#801449
  (qemu-kvm is not closing the merged images files (block_stream))
- Resolves: bz#806432
  (Review the design/code of the blkmirror block driver)
- Resolves: bz#811228
  (block streaming reverts image to auto-probe backing file format)
- Resolves: bz#812085
  (use the name block-job-cancel to indicate async cancel support)

* Tue Apr 17 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.277.el6
- kvm-qemu-kvm.spec.template-fix-datadir-directory-path.patch [bz#800496]
- Resolves: bz#800496
  (RHEV specific qemu-kvm)

* Mon Apr 16 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.276.el6
- kvm-usb-add-USBDescriptor-use-for-device-descriptors.patch [bz#807878]
- kvm-usb-use-USBDescriptor-for-device-qualifier-descripto.patch [bz#807878]
- kvm-usb-use-USBDescriptor-for-config-descriptors.patch [bz#807878]
- kvm-usb-use-USBDescriptor-for-interface-descriptors.patch [bz#807878]
- kvm-usb-use-USBDescriptor-for-endpoint-descriptors.patch [bz#807878]
- kvm-usb-host-rewrite-usb_linux_update_endp_table.patch [bz#807878]
- Resolves: bz#807878
  (Cannot hear sound when passthrough a USB speaker into RHEL guest)

* Thu Apr 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.275.el6
- kvm-block-Drain-requests-in-bdrv_close.patch [bz#798857]
- Resolves: bz#798857
  (pkill qemu-kvm appear block I/O error after live snapshot for multiple vms in parallelly)

* Thu Apr 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.274.el6
- kvm-blockdev-add-refcount-to-DriveInfo.patch [bz#807898]
- kvm-blockdev-make-image-streaming-safe-across-hotplug.patch [bz#807898]
- kvm-block-cancel-jobs-when-a-device-is-ready-to-go-away.patch [bz#807898]
- kvm-block-fix-streaming-closing-race.patch [bz#807898]
- Resolves: bz#807898
  (guest quit or device hot-unplug during streaming fails)

* Thu Apr 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.273.el6
- kvm-qapi-fix-double-free-in-qmp_output_visitor_cleanup.patch [bz#810983]
- Resolves: bz#810983
  (QAPI may double free on errors)

* Tue Apr 10 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.271.el6
- kvm-macvtap-rhel6.2-compatibility.patch [bz#806975]
- kvm-Allow-to-hot-plug-cpus-only-in-range-0.max_cpus.patch [bz#807512]
- Resolves: bz#806975
  (Live migration of bridge network to direct network fails with libvirt and virtio)
- Resolves: bz#807512
  (qemu exit and Segmentation fault when hotplug vcpus with bigger value)

* Thu Apr 05 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.270.el6
- kvm-usb-redir-An-interface-count-of-0-is-a-valid-value-r.patch [bz#808760]
- kvm-qemu-kvm.spec.template-move-some-lines-around.patch [bz#800496]
- kvm-qemu-kvm.spec.template-delete-define-rhev-0-line.patch [bz#800496]
- kvm-qemu-kvm.spec.template-define-with-live_snapshots.patch [bz#800496]
- kvm-qemu-kvm.spec.template-add-with-guest_agent-build-ti.patch [bz#800496]
- kvm-qemu-kvm.spec.template-make-some-file-paths-and-pack.patch [bz#800496]
- kvm-qemu-kvm.spec.template-add-RHEV-specific-package-nam.patch [bz#800496]
- kvm-redhat-disable-qemu-guest-agent-on-RHEV-builds.patch [bz#800496]
- Resolves: bz#800496
  (RHEV specific qemu-kvm)
- Resolves: bz#808760
  ([SPICE] usb-redir device does not accept unconfigured devices)

* Tue Apr 03 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.269.el6
- kvm-usb-ehci-frindex-always-is-a-14-bits-counter-rhbz-80.patch [bz#807984]
- Resolves: bz#807984
  ([SPICE]Hi speed USB ISO streaming does not work with windows XP)

* Mon Apr 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.268.el6
- kvm-block-stream-close-unused-files-and-update-backing_h.patch [bz#801449]
- kvm-ehci-fix-ehci_child_detach.patch [bz#769760]
- kvm-usb-ehci-drop-assert.patch [bz#807916]
- Resolves: bz#769760
  (Formatting of usb-storage disk attached on usb-hub fails to end)
- Resolves: bz#801449
  (qemu-kvm is not closing the merged images files (block_stream))
- Resolves: bz#807916
  (boot from the USB storage core dumped after press "ctrl-alt-delete")

* Wed Mar 28 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.267.el6
- kvm-Use-defines-instead-of-numbers-for-pci-hotplug-sts-b.patch [bz#805362]
- kvm-Fix-pci-hotplug-to-generate-level-triggered-interrup.patch [bz#805362]
- Resolves: bz#805362
  (guest kernel call trace when hotplug vcpu)

* Tue Mar 27 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.266.el6
- kvm-Live-block-copy-Fix-mirroring.patch [bz#802284]
- Resolves: bz#802284
  (RFE: Support live migration of storage (mirroring))

* Fri Mar 23 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.265.el6
- kvm-Add-blkmirror-block-driver.patch [bz#802284]
- kvm-qapi-add-c_fun-to-escape-function-names.patch [bz#802284]
- kvm-add-mirroring-to-transaction.patch [bz#802284]
- kvm-add-drive-mirror-command-and-HMP-equivalent.patch [bz#802284]
- kvm-Add-the-drive-reopen-command.patch [bz#647384]
- Resolves: bz#647384
  (RFE - Support live modification of the backing file chain (aka "snapshot deletion" aka "drive-reopen"))
- Resolves: bz#802284
  (RFE: Support live migration of storage (mirroring))

* Fri Mar 23 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.264.el6
- kvm-block-use-proper-qerrors-in-qmp_block_resize.patch [bz#802284]
- kvm-qapi-Convert-blockdev_snapshot_sync.patch [bz#802284]
- kvm-use-QSIMPLEQ_FOREACH_SAFE-when-freeing-list-elements.patch [bz#802284]
- kvm-Group-snapshot-Fix-format-name-for-backing-file.patch [bz#802284]
- kvm-qapi-complete-implementation-of-unions.patch [bz#802284]
- kvm-rename-blockdev-group-snapshot-sync.patch [bz#802284]
- kvm-add-mode-field-to-blockdev-snapshot-sync-transaction.patch [bz#785683]
- kvm-qmp-convert-blockdev-snapshot-sync-to-a-wrapper-arou.patch [bz#802284]
- kvm-Add-global-option-to-man-page.patch [bz#723754]
- Resolves: bz#723754
  (Update qemu-kvm -global option man page)
- Resolves: bz#785683
  (A live snapshot shouldn't reconfigure the backing file path in the new image)
- Resolves: bz#802284
  (RFE: Support live migration of storage (mirroring))

* Fri Mar 23 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.263.el6
- kvm-virtio-scsi-fix-cmd-lun-cut-and-paste-errors.patch [bz#788942]
- kvm-virtio-scsi-call-unregister_savevm.patch [bz#800710]
- kvm-scsi-add-get_dev_path.patch [bz#800710]
- kvm-scsi-cd-check-ready-condition-before-processing-seve.patch [bz#803219]
- kvm-scsi-copy-serial-number-into-VPD-page-0x83.patch [bz#801416]
- qemu-ga.init: fix bash syntax error, and exit codes [bz#632771]
- Resolves: bz#632771
  ([6.3 FEAT] add virt-agent (qemu-ga backend) to qemu)
- Resolves: bz#788942
  (virtio-scsi TMF handling fixes)
- Resolves: bz#800710
  (migration crashes on the source after hot remove of virtio-scsi controller)
- Resolves: bz#801416
  (virtio-scsi: use local image as guest disk can not configure the multipath)
- Resolves: bz#803219
  (virtio-scsi:after eject  virtio-scsi CD-ROM  tray-open's value still be 0)

* Thu Mar 22 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.262.el6
- Remove kvm-ksmtuned-should-use-rsz-instead-of-vsz.patch from the spec file
  (it was just a patch for ksmtuned)
- Related: bz#747010

* Thu Mar 22 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.261.el6
- kvm-fix-virtio-scsi-build-after-streaming-patches.patch [bz#582475]
- Resolves: bz#582475
  (RFE: Support live migration of storage (live streaming))

* Thu Mar 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.260.el6
- kvm-Revert-qed-intelligent-streaming-implementation.patch [bz#582475]
- kvm-Revert-block-add-drive-stream-on-off.patch [bz#582475]
- kvm-Revert-qmp-add-block_job_set_speed-command.patch [bz#582475]
- kvm-Revert-qmp-add-query-block-jobs-command.patch [bz#582475]
- kvm-Revert-qmp-add-block_job_cancel-command.patch [bz#582475]
- kvm-Revert-qmp-add-block_stream-command.patch [bz#582475]
- kvm-Revert-block-add-bdrv_aio_copy_backing.patch [bz#582475]
- kvm-Revert-qed-add-support-for-copy-on-read.patch [bz#582475]
- kvm-Revert-qed-make-qed_aio_write_alloc-reusable.patch [bz#582475]
- kvm-Revert-qed-extract-qed_start_allocating_write.patch [bz#582475]
- kvm-Revert-qed-replace-is_write-with-flags-field.patch [bz#582475]
- kvm-Revert-block-add-drive-copy-on-read-on-off.patch [bz#582475]
- kvm-block-use-public-bdrv_is_allocated-interface.patch [bz#582475]
- kvm-block-add-.bdrv_co_is_allocated.patch [bz#582475]
- kvm-qed-convert-to-.bdrv_co_is_allocated.patch [bz#582475]
- kvm-block-convert-qcow2-qcow2-and-vmdk-to-.bdrv_co_is_al.patch [bz#582475]
- kvm-vvfat-convert-to-.bdrv_co_is_allocated.patch [bz#582475]
- kvm-vdi-convert-to-.bdrv_co_is_allocated.patch [bz#582475]
- kvm-cow-convert-to-.bdrv_co_is_allocated.patch [bz#582475]
- kvm-vvfat-Fix-read-write-mode.patch [bz#582475]
- kvm-block-drop-.bdrv_is_allocated-interface.patch [bz#582475]
- kvm-block-add-bdrv_co_is_allocated-interface.patch [bz#582475]
- kvm-qemu-common-add-QEMU_ALIGN_DOWN-and-QEMU_ALIGN_UP-ma.patch [bz#582475]
- kvm-coroutine-add-qemu_co_queue_restart_all.patch [bz#582475]
- kvm-block-add-request-tracking.patch [bz#582475]
- kvm-block-add-interface-to-toggle-copy-on-read.patch [bz#582475]
- kvm-block-wait-for-overlapping-requests.patch [bz#582475]
- kvm-block-request-overlap-detection.patch [bz#582475]
- kvm-cow-use-bdrv_co_is_allocated.patch [bz#582475]
- kvm-block-core-copy-on-read-logic.patch [bz#582475]
- kvm-block-add-drive-copy-on-read-on-offv2.patch [bz#582475]
- kvm-block-implement-bdrv_co_is_allocated-boundary-cases.patch [bz#582475]
- kvm-block-wait_for_overlapping_requests-deadlock-detecti.patch [bz#582475]
- kvm-block-convert-qemu_aio_flush-calls-to-bdrv_drain_all.patch [bz#582475]
- kvm-coroutine-add-co_sleep_ns-coroutine-sleep-function.patch [bz#582475]
- kvm-block-check-bdrv_in_use-before-blockdev-operations.patch [bz#582475]
- kvm-block-make-copy-on-read-a-per-request-flag.patch [bz#582475]
- kvm-block-add-BlockJob-interface-for-long-running-operat.patch [bz#582475]
- kvm-block-add-image-streaming-block-job.patch [bz#582475]
- kvm-block-rate-limit-streaming-operations.patch [bz#582475]
- kvm-qmp-add-block_stream-commandv2.patch [bz#582475]
- kvm-qmp-add-block_job_set_speed-commandv2.patch [bz#582475]
- kvm-qmp-add-block_job_set_speed-command2.patch [bz#582475]
- kvm-qmp-add-query-block-jobs.patch [bz#582475]
- kvm-block-add-bdrv_find_backing_image.patch [bz#582475]
- kvm-add-QERR_BASE_NOT_FOUND.patch [bz#582475]
- kvm-block-add-support-for-partial-streaming.patch [bz#582475]
- kvm-docs-describe-live-block-operations.patch [bz#582475]
- kvm-cutils-extract-buffer_is_zero-from-qemu-img.c.patch [bz#582475]
- kvm-block-add-.bdrv_co_write_zeroes-interface.patch [bz#582475]
- kvm-block-perform-zero-detection-during-copy-on-read.patch [bz#582475]
- kvm-qed-replace-is_write-with-flags-field2.patch [bz#582475]
- kvm-qed-add-.bdrv_co_write_zeroes-support.patch [bz#582475]
- kvm-qemu-io-add-write-z-option-for-bdrv_co_write_zeroes.patch [bz#582475]
- kvm-Error-out-when-tls-channel-option-is-used-without-TL.patch [bz#790421]
- Resolves: bz#582475
  (RFE: Support live migration of storage (live streaming))
- Resolves: bz#790421
  (exit with error when tls-port is not specified but tls is enabled by tls-channel or x509* options)

* Thu Mar 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.259.el6
- kvm-Fix-qapi-code-generation-fix.patch [bz#761439]
- Resolves: bz#761439
  (Add command to put guest into hibernation to qemu-ga)

* Thu Mar 22 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.258.el6
- kvm-Revert-virtio-serial-Fix-segfault-on-guest-boot.patch [bz#769528]
- kvm-virtio-serial-Fix-segfault-on-guest-boot-v2.patch [bz#769528]
- kvm-Fix-curses-interaction-with-keymaps.patch [bz#785963]
- kvm-vnc-lift-modifier-keys-on-client-disconnect.patch [bz#785963]
- Resolves: bz#769528
  (virtio-serial: Backport code cleanups from upstream)
- Resolves: bz#785963
  (keys left pressed on the vncserver when closing the connection)

* Wed Mar 21 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.257.el6
- kvm-guest-agent-remove-unsupported-guest-agent-commands-.patch [bz#632771]
- Resolves: bz#632771
  ([6.3 FEAT] add virt-agent (qemu-ga backend) to qemu)

* Wed Mar 21 2012 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.256.el6
- kvm-monitor-Establish-cmd-flags-and-convert-the-async-ta.patch [bz#784153]
- kvm-Monitor-handle-optional-arg-as-a-bool.patch [bz#784153]
- kvm-QMP-New-argument-checker-first-part.patch [bz#784153]
- kvm-QMP-New-argument-checker-second-part.patch [bz#784153]
- kvm-QMP-Drop-old-client-argument-checker.patch [bz#784153]
- kvm-monitor-Allow-and-b-boolean-types-to-be-either-bool-.patch [bz#784153]
- kvm-QMP-Introduce-qmp_check_input_obj.patch [bz#784153]
- kvm-QMP-Drop-old-input-object-checking.patch [bz#784153]
- kvm-QMP-handle_qmp_command-Small-cleanup.patch [bz#784153]
- kvm-monitor-Allow-to-exclude-commands-from-QMP.patch [bz#784153]
- kvm-Monitor-Introduce-search_dispatch_table.patch [bz#784153]
- kvm-QMP-handle_qmp_command-Move-cmd-sanity-check.patch [bz#784153]
- kvm-QMP-Don-t-use-do_info.patch [bz#784153]
- kvm-QMP-Introduce-qmp_find_cmd.patch [bz#784153]
- kvm-QMP-Fix-default-response-regression.patch [bz#784153]
- kvm-qerror-add-qerror_report_err.patch [bz#784153]
- kvm-qapi-use-middle-mode-in-QMP-server.patch [bz#784153]
- kvm-QError-Introduce-QERR_IO_ERROR.patch [bz#784153]
- kvm-qapi-Introduce-blockdev-group-snapshot-sync-command.patch [bz#784153]
- kvm-QMP-Add-qmp-command-for-blockdev-group-snapshot-sync.patch [bz#784153]
- kvm-Only-build-group-snapshots-if-CONFIG_LIVE_SNAPSHOTS-.patch [bz#784153]
- Resolves: bz#784153
  (RFE - Support Group Live Snapshots)

* Wed Mar 21 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.255.el6
- kvm-QList-Introduce-QLIST_FOREACH_ENTRY.patch [bz#632771]
- kvm-QDict-Small-terminology-change.patch [bz#632771]
- kvm-QDict-Introduce-functions-to-retrieve-QDictEntry-val.patch [bz#632771]
- kvm-QDict-Introduce-new-iteration-API.patch [bz#632771]
- kvm-check-qdict-Introduce-test-for-the-new-iteration-API.patch [bz#632771]
- kvm-QDict-Rename-err_value.patch [bz#632771]
- kvm-QDict-Introduce-qdict_get_try_bool.patch [bz#632771]
- kvm-QError-Introduce-QERR_QMP_EXTRA_MEMBER.patch [bz#632771]
- kvm-Move-macros-GCC_ATTR-and-GCC_FMT_ATTR-to-common-head.patch [bz#632771]
- kvm-Introduce-compiler.h-header-file.patch [bz#632771]
- kvm-QError-Introduce-qerror_format_desc.patch [bz#632771]
- kvm-QError-Introduce-qerror_format.patch [bz#632771]
- kvm-Introduce-the-new-error-framework.patch [bz#632771]
- kvm-json-parser-propagate-error-from-parser.patch [bz#632771]
- kvm-Add-simple-pkg_config-variable-to-configure-script.patch [bz#632771]
- kvm-Add-hard-build-dependency-on-glib.patch [bz#632771]
- kvm-qlist-add-qlist_first-qlist_next.patch [bz#632771]
- kvm-qapi-add-module-init-types-for-qapi.patch [bz#632771]
- kvm-qapi-add-QAPI-visitor-core.patch [bz#632771]
- kvm-qapi-add-QMP-input-visitor.patch [bz#632771]
- kvm-qapi-add-QMP-output-visitor.patch [bz#632771]
- kvm-qapi-add-QAPI-dealloc-visitor.patch [bz#632771]
- kvm-qapi-add-QMP-command-registration-lookup-functions.patch [bz#632771]
- kvm-qapi-add-QMP-dispatch-functions.patch [bz#632771]
- kvm-qapi-add-ordereddict.py-helper-library.patch [bz#632771]
- kvm-qapi-add-qapi.py-helper-libraries.patch [bz#632771]
- kvm-qapi-add-qapi-types.py-code-generator.patch [bz#632771]
- kvm-qapi-add-qapi-visit.py-code-generator.patch [bz#632771]
- kvm-qapi-add-qapi-commands.py-code-generator.patch [bz#632771]
- kvm-qapi-test-schema-used-for-unit-tests.patch [bz#632771]
- kvm-qapi-add-test-visitor-tests-for-gen.-visitor-code.patch [bz#632771]
- kvm-qapi-add-test-qmp-commands-tests-for-gen.-marshallin.patch [bz#632771]
- kvm-qapi-add-QAPI-code-generation-documentation.patch [bz#632771]
- kvm-qerror-add-QERR_JSON_PARSE_ERROR-to-qerror.c.patch [bz#632771]
- kvm-guest-agent-command-state-class.patch [bz#632771]
- kvm-Make-glib-mandatory-and-fixup-utils-appropriately.patch [bz#632771]
- kvm-guest-agent-qemu-ga-daemon.patch [bz#632771]
- kvm-guest-agent-add-guest-agent-RPCs-commands.patch [bz#632771]
- kvm-guest-agent-fix-build-with-OpenBSD.patch [bz#632771]
- kvm-guest-agent-use-QERR_UNSUPPORTED-for-disabled-RPCs.patch [bz#632771]
- kvm-guest-agent-only-enable-FSFREEZE-when-it-s-supported.patch [bz#632771]
- kvm-qemu-ga-remove-dependency-on-gio-and-gthread.patch [bz#632771]
- kvm-guest-agent-remove-g_strcmp0-usage.patch [bz#632771]
- kvm-guest-agent-remove-uneeded-dependencies.patch [bz#632771]
- kvm-guest-agent-add-RPC-blacklist-command-line-option.patch [bz#632771]
- kvm-guest-agent-add-supported-command-list-to-guest-info.patch [bz#632771]
- kvm-qapi-add-code-generation-support-for-middle-mode.patch [bz#632771]
- kvm-qapi-fixup-command-generation-for-functions-that-ret.patch [bz#632771]
- kvm-qapi-dealloc-visitor-fix-premature-free-and-iteratio.patch [bz#632771]
- kvm-qapi-generate-qapi_free_-functions-for-List-types.patch [bz#632771]
- kvm-qapi-add-test-cases-for-generated-free-functions.patch [bz#632771]
- kvm-qapi-dealloc-visitor-support-freeing-of-nested-lists.patch [bz#632771]
- kvm-qapi-modify-visitor-code-generation-for-list-iterati.patch [bz#632771]
- kvm-qapi-Don-t-use-c_var-on-enum-strings.patch [bz#632771]
- kvm-qapi-Automatically-generate-a-_MAX-value-for-enums.patch [bz#632771]
- kvm-qapi-commands.py-Don-t-call-the-output-marshal-on-er.patch [bz#632771]
- kvm-qapi-Check-for-negative-enum-values.patch [bz#632771]
- kvm-qapi-fix-guardname-generation.patch [bz#632771]
- kvm-qapi-allow-a-gen-key-to-suppress-code-generation.patch [bz#632771]
- kvm-Makefile-add-missing-deps-on-GENERATED_HEADERS.patch [bz#632771]
- kvm-qapi-protect-against-NULL-QObject-in-qmp_input_get_o.patch [bz#632771]
- kvm-Fix-spelling-in-comments-and-debug-messages-recieve-.patch [bz#632771]
- kvm-json-lexer-fix-conflict-with-mingw32-ERROR-definitio.patch [bz#632771]
- kvm-json-streamer-allow-recovery-after-bad-input.patch [bz#632771]
- kvm-json-lexer-limit-the-maximum-size-of-a-given-token.patch [bz#632771]
- kvm-json-streamer-limit-the-maximum-recursion-depth-and-.patch [bz#632771]
- kvm-json-streamer-make-sure-to-reset-token_size-after-em.patch [bz#632771]
- kvm-json-parser-detect-premature-EOI.patch [bz#632771]
- kvm-json-lexer-reset-the-lexer-state-on-an-invalid-token.patch [bz#632771]
- kvm-json-lexer-fix-flushing-logic-to-not-always-go-to-er.patch [bz#632771]
- kvm-json-lexer-make-lexer-error-recovery-more-determinis.patch [bz#632771]
- kvm-json-streamer-add-handling-for-JSON_ERROR-token-stat.patch [bz#632771]
- kvm-json-parser-add-handling-for-NULL-token-list.patch [bz#632771]
- kvm-.gitignore-ignore-qemu-ga-and-qapi-generated.patch [bz#632771]
- kvm-spec-Change-spec-file-and-include-initscripts-for-qe.patch [bz#632771]
- kvm-Makefile-fix-dependencies-for-generated-.h-.c.patch [bz#632771]
- kvm-Create-qemu-os-win32.h-and-move-WIN32-specific-decla.patch [bz#787723]
- kvm-Introduce-os-win32.c-and-move-polling-functions-from.patch [bz#787723]
- kvm-vl.c-Move-host_main_loop_wait-to-OS-specific-files.patch [bz#787723]
- kvm-Introduce-os-posix.c-and-create-os_setup_signal_hand.patch [bz#787723]
- kvm-Move-win32-early-signal-handling-setup-to-os_setup_s.patch [bz#787723]
- kvm-Rename-os_setup_signal_handling-to-os_setup_early_si.patch [bz#787723]
- kvm-Move-main-signal-handler-setup-to-os-specificfiles.patch [bz#787723]
- kvm-Move-find_datadir-to-OS-specific-files.patch [bz#787723]
- kvm-Rename-qemu-options.h-to-qemu-options.def.patch [bz#787723]
- kvm-qemu-ga-Add-schema-documentation-for-types.patch [bz#787723]
- kvm-qemu-ga-move-channel-transport-functionality-into-wr.patch [bz#787723]
- kvm-qemu-ga-separate-out-common-commands-from-posix-spec.patch [bz#787723]
- kvm-qemu-ga-rename-guest-agent-commands.c-commands-posix.patch [bz#787723]
- kvm-qemu-ga-fixes-for-win32-build-of-qemu-ga.patch [bz#787723]
- kvm-qemu-ga-add-initial-win32-support.patch [bz#787723]
- kvm-qemu-ga-add-Windows-service-integration.patch [bz#787723]
- kvm-qemu-ga-add-win32-guest-shutdown-command.patch [bz#787723]
- kvm-qemu-ga-add-guest-suspend-disk.patch [bz#761439]
- kvm-qemu-ga-add-guest-suspend-ram.patch [bz#761439]
- kvm-qemu-ga-add-guest-suspend-hybrid.patch [bz#761439]
- kvm-Fix-qapi-code-generation-wrt-parallel-build.patch [bz#761439]
- kvm-qemu-ga-make-guest-suspend-posix-only.patch [bz#761439]
- Resolves: bz#632771
  ([6.3 FEAT] add virt-agent (qemu-ga backend) to qemu)
- Resolves: bz#787723
  (Backport qemu-ga for Windows)
- Resolves: bz#761439
  (Add command to put guest into hibernation to qemu-ga)

* Wed Mar 21 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.254.el6
- kvm-qed-do-not-evict-in-use-L2-table-cache-entries.patch [bz#800183]
- kvm-Update-cpu-count-on-cpu-hotplug-in-cmos.patch [bz#802033]
- Resolves: bz#800183
  (qed: do not evict in-use L2 table cache entries)
- Resolves: bz#802033
  (kvm guest hangs on reboot after cpu-hotplug)

* Tue Mar 20 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.253.el6
- kvm-qemu-img-print-error-codes-when-convert-fails.patch [bz#803344]
- kvm-usb-fix-use-after-free.patch [bz#796118]
- Resolves: bz#796118
  (qemu hits core dump when boot guest with 2 pass-though usb devices under 1.1 controller)
- Resolves: bz#803344
  (qemu-img convert doesn't print errno strings on I/O errors)

* Tue Mar 20 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.252.el6
- kvm-qemu-img-print-error-codes-when-convert-fails.patch [bz#803344]
- kvm-usb-fix-use-after-free.patch [bz#796118]
- Resolves: bz#796118
  (qemu hits core dump when boot guest with 2 pass-though usb devices under 1.1 controller)
- Resolves: bz#803344
  (qemu-img convert doesn't print errno strings on I/O errors)

* Tue Mar 20 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.251.el6
- kvm-rtl8139-limit-transmission-buffer-size-in-c-mode.patch [bz#781920]
- kvm-configure-fix-rhel-6-only-configure-break-on-audio_d.patch [bz#747011]
- kvm-qxl-fix-spice-sdl-no-cursor-regression.patch [bz#747011]
- kvm-qxl-drop-qxl_spice_update_area_async-definition.patch [bz#747011]
- kvm-qxl-require-spice-0.8.2.patch [bz#747011]
- kvm-qxl-remove-flipped.patch [bz#747011]
- kvm-qxl-introduce-QXLCookie.patch [bz#747011]
- kvm-qxl-make-qxl_render_update-async.patch [bz#747011]
- kvm-qxl-properly-handle-upright-and-non-shared-surfaces.patch [bz#747011]
- Resolves: bz#747011
  (Taking screenshot  hangs Spice display when a client is connected)
- Resolves: bz#781920
  (rtl8139: prevent unlimited send buffer allocated for guest descriptors.)

* Mon Mar 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.250.el6
- kvm-Use-defines-instead-of-numbers-for-cpu-hotplug.patch [bz#562886]
- kvm-Fix-cpu-pci-hotplug-to-generate-level-triggered-inte.patch [bz#562886]
- kvm-Make-pause-resume_all_vcpus-available-to-usage-from-.patch [bz#562886]
- kvm-Prevent-partially-initialized-vcpu-being-visible.patch [bz#562886]
- kvm-monitor-fix-client_migrate_info-error-handling.patch [bz#795652]
- Resolves: bz#562886
  (Implement vCPU hotplug/unplug)
- Resolves: bz#795652
  (Inappropriate __com.redhat_spice_migrate_info error handler causes qemu monitor hanging)

* Fri Mar 16 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.249.el6
- kvm-force-enable-VIRTIO_BLK_F_SCSI-if-present-on-migrati.patch [bz#800536]
- Resolves: bz#800536
  (virtio-blk nonfunctional after live migration or save/restore migration.)

* Wed Mar 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.248.el6
- kvm-cpu-flags-aliases-pclmuldq-pclmulqdq-and-ffxsr-fxsr_.patch [bz#767302]
- kvm-add-Opteron_G4-CPU-model-v2.patch [bz#767302]
- kvm-add-SandyBridge-CPU-model-v2.patch [bz#760953]
- Resolves: bz#760953
  (qemu-kvm: new Sandy Bridge CPU definition)
- Resolves: bz#767302
  (new CPU model for AMD Bulldozer)

* Tue Mar 13 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.247.el6
- kvm-qemu-timer-Introduce-clock-reset-notifier2.patch [bz#734426]
- kvm-mc146818rtc-Handle-host-clock-resets2.patch [bz#734426]
- Resolves: bz#734426
  (KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation)

* Mon Mar 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.246.el6
- kvm-notifier-Pass-data-argument-to-callback-v2.patch [bz#766303]
- kvm-suspend-add-infrastructure.patch [bz#766303]
- kvm-suspend-switch-acpi-s3-to-new-infrastructure.patch [bz#766303]
- kvm-suspend-add-system_wakeup-monitor-command.patch [bz#766303]
- kvm-suspend-make-ps-2-devices-wakeup-the-guest.patch [bz#766303]
- kvm-suspend-make-serial-ports-wakeup-the-guest.patch [bz#766303]
- kvm-suspend-make-rtc-alarm-wakeup-the-guest.patch [bz#766303]
- kvm-suspend-make-acpi-timer-wakeup-the-guest.patch [bz#766303]
- kvm-suspend-add-qmp-events.patch [bz#766303]
- kvm-add-qemu_unregister_suspend_notifier.patch [bz#766303]
- kvm-make-assigned-pci-devices-wakeup-the-guest-instantly.patch [bz#766303]
- kvm-wakeup-on-migration.patch [bz#766303]
- Resolves: bz#766303
  ([RFE] Resume VM from s3 as a response for monitor/keyboard/mouse action)

* Mon Mar 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.245.el6
- kvm-USB-add-usb-network-redirection-support.patch [bz#758104]
- kvm-usb-redir-rhel6-build-fixups.patch [bz#758104]
- kvm-usb-redir-Device-disconnect-re-connect-robustness-fi.patch [bz#758104]
- kvm-usb-redir-Don-t-try-to-write-to-the-chardev-after-a-.patch [bz#758104]
- kvm-usb-redir-Clear-iso-irq-error-when-stopping-the-stre.patch [bz#758104]
- kvm-usb-redir-Dynamically-adjust-iso-buffering-size-base.patch [bz#758104]
- kvm-usb-redir-Pre-fill-our-isoc-input-buffer-before-send.patch [bz#758104]
- kvm-usb-redir-Try-to-keep-our-buffer-size-near-the-targe.patch [bz#758104]
- kvm-usb-redir-Improve-some-debugging-messages.patch [bz#758104]
- kvm-qemu-char-make-qemu_chr_event-public.patch [bz#758104]
- kvm-spice-qemu-char-Generate-chardev-open-close-events.patch [bz#758104]
- kvm-usb-redir-Call-qemu_chr_fe_open-close.patch [bz#758104]
- kvm-usb-redir-Add-flow-control-support.patch [bz#758104]
- kvm-usb-ehci-Clear-the-portstatus-powner-bit-on-device-d.patch [bz#758104]
- kvm-usb-redir-Add-the-posibility-to-filter-out-certain-d.patch [bz#758104]
- kvm-usb-ehci-Handle-ISO-packets-failing-with-an-error-ot.patch [bz#758104]
- kvm-ehci-drop-old-stuff.patch [bz#758104]
- kvm-usb-redir-Fix-printing-of-device-version.patch [bz#758104]
- kvm-usb-redir-Always-clear-device-state-on-filter-reject.patch [bz#758104]
- kvm-usb-redir-Let-the-usb-host-know-about-our-device-fil.patch [bz#758104]
- kvm-usb-redir-Limit-return-values-returned-by-iso-packet.patch [bz#758104]
- kvm-usb-redir-Return-USB_RET_NAK-when-we-ve-no-data-for-.patch [bz#758104]
- kvm-usb-ehci-Never-follow-table-entries-with-the-T-bit-s.patch [bz#758104]
- kvm-usb-ehci-split-our-qh-queue-into-async-and-periodic-.patch [bz#758104]
- kvm-usb-ehci-always-call-ehci_queues_rip_unused-for-peri.patch [bz#758104]
- kvm-usb-ehci-Drop-cached-qhs-when-the-doorbell-gets-rung.patch [bz#758104]
- kvm-usb-ehci-Rip-the-queues-when-the-async-or-period-sch.patch [bz#758104]
- kvm-usb-ehci-Any-packet-completion-except-for-NAK-should.patch [bz#758104]
- kvm-usb-ehci-Fix-cerr-tracking.patch [bz#758104]
- kvm-usb-ehci-Remove-dead-nakcnt-code.patch [bz#758104]
- kvm-usb-ehci-Fix-and-simplify-nakcnt-handling.patch [bz#758104]
- kvm-usb-ehci-Cleanup-itd-error-handling.patch [bz#758104]
- kvm-usb-return-BABBLE-rather-then-NAK-when-we-receive-to.patch [bz#758104]
- kvm-usb-add-USB_RET_IOERROR.patch [bz#758104]
- kvm-usb-ehci-sanity-check-iso-xfers.patch [bz#758104]
- Resolves: bz#758104
  ([SPICE]Add usbredirection support to qemu)

* Mon Mar 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.244.el6
- kvm-Revert-notifier-Pass-data-argument-to-callback.patch [bz#734426]
- kvm-Revert-qemu-timer-Introduce-clock-reset-notifier.patch [bz#734426]
- kvm-Revert-mc146818rtc-Handle-host-clock-resets.patch [bz#734426]
- Related: bz#734426
  (KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation)

* Mon Mar 12 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.243.el6
- kvm-enable-architectural-PMU-cpuid-leaf-for-kvm.patch [bz#798936]
- Resolves: bz#798936
  (enable architectural PMU cpuid leaf for kvm)

* Thu Mar 08 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.242.el6
- kvm-notifier-Pass-data-argument-to-callback.patch [bz#734426]
- kvm-qemu-timer-Introduce-clock-reset-notifier.patch [bz#734426]
- kvm-mc146818rtc-Handle-host-clock-resets.patch [bz#734426]
- Resolves: bz#734426
  (KVM guests hang/stall if host clock is set back - problem in qemu-kvm RTC timer emulation)

* Wed Mar 07 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.241.el6
- kvm-qxl-Add-support-for-2000x2000-resolution.patch [bz#736867]
- Resolves: bz#736867
  (qxl: Add support for 2000x2000 resolution)

* Tue Mar 06 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.240.el6
- kvm-Flush-coalesced-MMIO-buffer-periodly.patch [bz#796575]
- kvm-Flush-coalesced-mmio-buffer-on-IO-window-exits.patch [bz#796575]
- kvm-Move-graphic-related-coalesced-MMIO-flushes-to-affec.patch [bz#796575]
- kvm-Drop-obsolete-nographic-timer.patch [bz#796575]
- kvm-avoid-reentring-kvm_flush_coalesced_mmio_buffer.patch [bz#796575]
- kvm-ksmtuned-should-use-rsz-instead-of-vsz.patch [bz#747010]
- kvm-qed-fix-use-after-free-during-l2-cache-commit.patch [bz#742841]
- Resolves: bz#742841
  ([RHEL6.2] Assertion failure in qed l2 cache commit)
- Resolves: bz#747010
  (ksmtuned uses "vsz" instead of "rsz" when calculating qemu-kvm mem usage ( KSM turn on too early ))
- Resolves: bz#796575
  (qemu-kvm wakes up 66 times a second)

* Tue Mar 06 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.239.el6
- kvm-vnc-Migrate-to-using-QTAILQ-instead-of-custom-implem.patch [bz#653779]
- kvm-vnc-implement-shared-flag-handling.patch [bz#653779]
- kvm-ram-use-correct-milliseconds-amount.patch [bz#752138]
- kvm-migration-Fix-calculation-of-bytes_transferred.patch [bz#752138]
- kvm-ram-calculate-bwidth-correctly.patch [bz#752138]
- kvm-block-Rename-bdrv_mon_event-BlockMonEventAction.patch [bz#575159]
- kvm-block-bdrv_eject-Make-eject_flag-a-real-bool.patch [bz#575159]
- kvm-block-Don-t-call-bdrv_eject-if-the-tray-state-didn-t.patch [bz#575159]
- kvm-ide-drop-ide_tray_state_post_load.patch [bz#575159]
- kvm-virtio-serial-Fix-segfault-on-guest-boot.patch [bz#769528]
- kvm-qmp-add-DEVICE_TRAY_MOVED-event.patch [bz#575159]
- Resolves: bz#575159
  (RFE: a QMP event notification for disk media eject)
- Resolves: bz#653779
  ([RFE] VNC server ignore shared-flag during client init)
- Resolves: bz#752138
  (qemu: "unlimited" migration speed to regular file can't be cancelled)
- Resolves: bz#769528
  (virtio-serial: Backport code cleanups from upstream)

* Mon Mar 05 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.238.el6
- kvm-qxl-don-t-render-stuff-when-the-vm-is-stopped.patch [bz#748810]
- kvm-qemu-options.hx-fix-tls-channel-help-text.patch [bz#688586]
- kvm-spice-support-ipv6-channel-address-in-monitor-events.patch [bz#769512]
- kvm-raw-posix-do-not-linearize-anymore-direct-I-O-on-Lin.patch [bz#767606]
- kvm-ide-fail-I-O-to-empty-disk.patch [bz#751937]
- kvm-ui-spice-core-fix-segfault-in-monitor.patch [bz#743251]
- kvm-qcow2-Fix-bdrv_write_compressed-error-handling.patch [bz#790350]
- kvm-Documentation-Add-qemu-img-check-rebase.patch [bz#725748]
- kvm-Add-missing-documentation-for-qemu-img.patch [bz#725748]
- kvm-Documentation-Add-qemu-img-t-parameter-in-man-page.patch [bz#725748]
- kvm-Documentation-Mention-qcow2-full-preallocation.patch [bz#676484]
- Resolves: bz#676484
  (There is no indication of full preallocation mode in qemu-img man page)
- Resolves: bz#688586
  (Errors in man page: [un]supported tls-channels for Spice)
- Resolves: bz#725748
  (Update qemu-img convert/re-base/commit -t man page)
- Resolves: bz#743251
  (segfault on monitor command "info spice" when no "-spice" option given)
- Resolves: bz#748810
  (qemu crashes if screen dump is called when the vm is stopped)
- Resolves: bz#751937
  (qemu-kvm core dumps during iofuzz test)
- Resolves: bz#767606
  (Need to remove the "Linearized QEMU Hack" for underlying NFS storage)
- Resolves: bz#769512
  (The spice IPv6 option is invalid)
- Resolves: bz#790350
  (qemu-img hits core dumped with error "qcow2_cache_destroy: Assertion" when does "qemu-img convert ........")

* Mon Mar 05 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.237.el6
- kvm-vnc-Fix-fatal-crash-with-vnc-reverse-mode.patch [bz#769142]
- kvm-qemu-img-rebase-Fix-for-undersized-backing-files.patch [bz#638055]
- kvm-qxl-set-only-off-screen-surfaces-dirty-instead-of-th.patch [bz#790083]
- kvm-qxl-make-sure-primary-surface-is-saved-on-migration-.patch [bz#790083]
- Resolves: bz#638055
  (Allow qemu-img re-base with undersized backing files)
- Resolves: bz#769142
  (Qemu-kvm core dumped when connecting to listening vnc with "reverse")
- Resolves: bz#790083
  (qxl: primary surface not saved on migration when the qxl is in COMPAT mode)

* Fri Mar 02 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.236.el6
- kvm-We-should-check-the-return-code-of-virtio_load.patch [bz#796063]
- kvm-input-send-kbd-mouse-events-only-to-running-guests.patch [bz#788027 bz#788027 - Spice and vnc connection buffer keyboard and mouse]
- kvm-usb-ehci-fix-reset.patch [bz#752049]
- Resolves: bz#752049
  (windows guest hangs when booting with usb stick passthrough)
- Resolves: bz#788027
  (Spice and vnc connection buffer keyboard and mouse event after guest stopped)
- Resolves: bz#796063
  (KVM virtual machine hangs after live migration or save/restore migration.)

* Thu Mar 01 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.235.el6
- kvm-keep-the-PID-file-locked-for-the-lifetime-of-the-pro.patch [bz#758194]
- Resolves: bz#758194
  (Coverity omnibus)

* Tue Feb 28 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.234.el6
- kvm-Always-notify-consumers-of-char-devices-if-they-re-o.patch [bz#791200]
- kvm-qbus-add-functions-to-walk-both-devices-and-busses.patch [bz#782029]
- kvm-qdev-trigger-reset-from-a-given-device.patch [bz#782029]
- kvm-qdev-switch-children-device-list-to-QTAILQ.patch [bz#782029]
- kvm-qiov-prevent-double-free-or-use-after-free.patch [bz#782029]
- kvm-scsi-introduce-SCSIReqOps.patch [bz#782029]
- kvm-scsi-move-request-related-callbacks-from-SCSIDeviceI.patch [bz#782029]
- kvm-scsi-pass-cdb-already-to-scsi_req_new.patch [bz#782029]
- kvm-scsi-introduce-SCSICommand.patch [bz#782029]
- kvm-scsi-push-lun-field-to-SCSIDevice.patch [bz#782029]
- kvm-scsi-move-request-parsing-to-common-code.patch [bz#782029]
- kvm-hw-scsi-bus.c-Fix-use-of-uninitialised-variable.patch [bz#782029]
- kvm-scsi-move-handling-of-REPORT-LUNS-and-invalid-LUNs-t.patch [bz#782029]
- kvm-scsi-move-handling-of-REQUEST-SENSE-to-common-code.patch [bz#782029]
- kvm-scsi-do-not-overwrite-memory-on-REQUEST-SENSE-comman.patch [bz#782029]
- kvm-scsi-add-a-bunch-more-common-sense-codes.patch [bz#782029]
- kvm-scsi-add-support-for-unit-attention-conditions.patch [bz#782029]
- kvm-scsi-report-unit-attention-on-reset.patch [bz#782029]
- kvm-scsi-add-special-traces-for-common-commands.patch [bz#782029]
- kvm-scsi-move-tcq-ndev-to-SCSIBusOps-now-SCSIBusInfo.patch [bz#782029]
- kvm-scsi-remove-devs-array-from-SCSIBus.patch [bz#782029]
- kvm-scsi-implement-REPORT-LUNS-for-arbitrary-LUNs.patch [bz#782029]
- kvm-scsi-allow-arbitrary-LUNs.patch [bz#782029]
- kvm-scsi-add-channel-to-addressing.patch [bz#782029]
- kvm-usb-storage-move-status-debug-message-to-usb_msd_sen.patch [bz#782029]
- kvm-usb-storage-fill-status-in-complete-callback.patch [bz#782029]
- kvm-usb-storage-drop-tag-from-device-state.patch [bz#782029]
- kvm-usb-storage-drop-result-from-device-state.patch [bz#782029]
- kvm-usb-storage-don-t-try-to-send-the-status-early.patch [bz#782029]
- kvm-scsi-do-not-call-transfer_data-after-canceling-a-req.patch [bz#782029]
- kvm-scsi-disk-reconcile-differences-around-cancellation.patch [bz#782029]
- kvm-scsi-execute-SYNCHRONIZE_CACHE-asynchronously.patch [bz#782029]
- kvm-scsi-refine-constants-for-READ-CAPACITY-16.patch [bz#782029]
- kvm-scsi-improve-MODE-SENSE-emulation.patch [bz#782029]
- kvm-scsi-disk-commonize-iovec-creation-between-reads-and.patch [bz#782029]
- kvm-scsi-disk-lazily-allocate-bounce-buffer.patch [bz#782029]
- kvm-scsi-disk-fix-retrying-a-flush.patch [bz#782029]
- kvm-scsi-fix-sign-extension-problems.patch [bz#782029]
- kvm-scsi-pass-correct-sense-code-for-ENOMEDIUM.patch [bz#782029]
- kvm-scsi-disk-enable-CD-emulation.patch [bz#782029]
- kvm-scsi-disk-add-missing-definitions-for-MMC.patch [bz#782029]
- kvm-scsi-add-GESN-definitions-to-scsi-defs.h.patch [bz#782029]
- kvm-scsi-notify-the-device-when-unit-attention-is-report.patch [bz#782029]
- kvm-scsi-disk-report-media-changed-via-unit-attention-se.patch [bz#782029]
- kvm-scsi-disk-fix-coding-style-issues-braces.patch [bz#782029]
- kvm-scsi-disk-add-stubs-for-more-MMC-commands.patch [bz#782029]
- kvm-scsi-disk-store-valid-mode-pages-in-a-table.patch [bz#782029]
- kvm-scsi-disk-add-more-mode-page-values-from-atapi.c.patch [bz#782029]
- kvm-scsi-disk-support-DVD-profile-in-GET-CONFIGURATION.patch [bz#782029]
- kvm-scsi-disk-support-READ-DVD-STRUCTURE.patch [bz#782029]
- kvm-scsi-disk-report-media-changed-via-GET-EVENT-STATUS-.patch [bz#782029]
- kvm-scsi-Guard-against-buflen-exceeding-req-cmd.xfer-in-.patch [bz#782029]
- kvm-scsi-disk-fail-READ-CAPACITY-if-LBA-0-but-PMI-0.patch [bz#782029]
- kvm-scsi-disk-implement-eject-requests.patch [bz#782029]
- kvm-scsi-disk-guess-geometry.patch [bz#782029]
- kvm-scsi-generic-reenable.patch [bz#782029]
- kvm-scsi-generic-do-not-disable-FUA.patch [bz#782029]
- kvm-scsi-generic-remove-scsi_req_fixup.patch [bz#782029]
- kvm-scsi-generic-drop-SCSIGenericState.patch [bz#782029]
- kvm-scsi-generic-check-ioctl-statuses-when-SG_IO-succeed.patch [bz#782029]
- kvm-scsi-generic-look-at-host-status.patch [bz#782029]
- kvm-scsi-generic-snoop-READ-CAPACITY-commands-to-get-blo.patch [bz#782029]
- kvm-scsi-disk-do-not-duplicate-BlockDriverState-member.patch [bz#782029]
- kvm-scsi-disk-remove-cluster_size.patch [bz#782029]
- kvm-scsi-disk-small-clean-up-to-INQUIRY.patch [bz#782029]
- kvm-scsi-move-max_lba-to-SCSIDevice.patch [bz#782029]
- kvm-scsi-make-reqops-const.patch [bz#782029]
- kvm-scsi-export-scsi_generic_reqops.patch [bz#782029]
- kvm-scsi-pass-cdb-to-alloc_req.patch [bz#782029]
- kvm-scsi-generic-bump-SCSIRequest-reference-count-until-.patch [bz#782029]
- kvm-scsi-push-request-restart-to-SCSIDevice.patch [bz#782029]
- kvm-scsi-disk-add-scsi-block-for-device-passthrough.patch [bz#782029]
- kvm-scsi-bus-remove-duplicate-table-entries.patch [bz#782029]
- kvm-scsi-update-list-of-commands.patch [bz#782029]
- kvm-scsi-fix-parsing-of-allocation-length-field.patch [bz#782029]
- kvm-scsi-remove-block-descriptors-from-CDs.patch [bz#782029]
- kvm-scsi-pass-down-REQUEST-SENSE-to-the-device-when-ther.patch [bz#782029]
- kvm-scsi-block-always-use-SG_IO-for-MMC-devices.patch [bz#782029]
- kvm-usb-msd-do-not-register-twice-in-the-boot-order.patch [bz#782029]
- kvm-scsi-fix-fw-path.patch [bz#782029]
- kvm-scsi-generic-add-as-boot-device.patch [bz#782029]
- kvm-dma-helpers-rename-is_write-to-to_dev.patch [bz#782029]
- kvm-dma-helpers-rewrite-completion-cancellation.patch [bz#782029]
- kvm-dma-helpers-allow-including-from-target-independent-.patch [bz#782029]
- kvm-dma-helpers-make-QEMUSGList-target-independent.patch [bz#782029]
- kvm-dma-helpers-add-dma_buf_read-and-dma_buf_write.patch [bz#782029]
- kvm-dma-helpers-add-accounting-wrappers.patch [bz#782029]
- kvm-scsi-pass-residual-amount-to-command_complete.patch [bz#782029]
- kvm-scsi-add-scatter-gather-functionality.patch [bz#782029]
- kvm-scsi-disk-enable-scatter-gather-functionality.patch [bz#782029]
- kvm-scsi-add-SCSIDevice-vmstate-definitions.patch [bz#782029]
- kvm-scsi-generic-add-migration-support.patch [bz#782029]
- kvm-scsi-disk-add-migration-support.patch [bz#782029]
- kvm-virtio-scsi-Add-virtio-scsi-stub-device.patch [bz#782029]
- kvm-virtio-scsi-Add-basic-request-processing-infrastruct.patch [bz#782029]
- kvm-virtio-scsi-add-basic-SCSI-bus-operation.patch [bz#782029]
- kvm-virtio-scsi-process-control-queue-requests.patch [bz#782029]
- kvm-virtio-scsi-add-migration-support.patch [bz#782029]
- kvm-block-Add-SG_IO-device-check-in-refresh_total_sector.patch [bz#782029]
- kvm-scsi-fix-wrong-return-for-target-INQUIRY.patch [bz#782029]
- kvm-scsi-fix-searching-for-an-empty-id.patch [bz#782029]
- kvm-scsi-block-always-use-scsi_generic_ops-for-cache-non.patch [bz#782029]
- kvm-block-Keep-track-of-devices-I-O-status.patch [bz#797186]
- kvm-virtio-Support-I-O-status.patch [bz#797186]
- kvm-ide-Support-I-O-status.patch [bz#797186]
- kvm-scsi-Support-I-O-status.patch [bz#797186]
- kvm-QMP-query-status-Add-io-status-key.patch [bz#797186]
- kvm-HMP-Print-io-status-information.patch [bz#797186]
- Resolves: bz#782029
  ([RFE] virtio-scsi: qemu-kvm implementation)
- Resolves: bz#791200
  (Character device consumers can miss OPENED events)
- Resolves: bz#797186
  (QMP: Backport the I/O status feature)

* Thu Feb 23 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.233.el6
- kvm-fix-build-without-spice.patch [bz#674583]
- kvm-Fix-usbdevice-crash.patch [bz#754349]
- kvm-usb-make-usb_create_simple-catch-and-pass-up-errors.patch [bz#754349]
- kvm-usb-fix-usb_qdev_init-error-handling.patch [bz#754349]
- kvm-usb-fix-usb_qdev_init-error-handling-again.patch [bz#754349]
- Resolves: bz#674583
  (qemu-kvm build fails without --enable-spice)
- Resolves: bz#754349
  (guest will core dump when hotplug multiple invalid usb-host)

* Mon Feb 20 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.232.el6
- kvm-add-missing-CPU-flag-names.patch [bz#785271]
- Resolves: bz#785271
  (add new CPU flag definitions that are already supported by the kernel)

* Thu Feb 16 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.231.el6
- kvm-pci-assign-Fix-cpu_register_io_memory-leak-for-slow-.patch [bz#738519]
- Resolves: bz#738519
  (Core dump when hotplug/hotunplug usb controller more than 1000 times)

* Wed Feb 15 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.230.el6
- kvm-qxl-stride-fixup.patch [bz#748810]
- kvm-qxl-make-sure-we-continue-to-run-with-a-shared-buffe.patch [bz#748810]
- kvm-debugcon-support-for-debugging-consoles-e.g.-Bochs-p.patch [bz#782825]
- kvm-Debugcon-Fix-debugging-printf.patch [bz#782825]
- Resolves: bz#748810
  (qemu crashes if screen dump is called when the vm is stopped)
- Resolves: bz#782825
  (backport isa-debugcon)

* Tue Feb 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.229.el6
- kvm-Support-running-QEMU-on-Valgrind.patch [bz#750739]
- Resolves: bz#750739
  (Work around valgrind choking on our use of memalign())

* Tue Feb 14 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.228.el6
- kvm-Drop-whole-archive-and-static-libraries.patch [bz#783950]
- kvm-make-qemu-img-depends-on-config-host.h.patch [bz#783950]
- kvm-Fix-generation-of-config-host.h.patch [bz#783950]
- kvm-cloop-use-pread.patch [bz#783950]
- kvm-cloop-use-qemu-block-API.patch [bz#783950]
- kvm-block-bochs-improve-format-checking.patch [bz#783950]
- kvm-bochs-use-pread.patch [bz#783950]
- kvm-bochs-use-qemu-block-API.patch [bz#783950]
- kvm-parallels-use-pread.patch [bz#783950]
- kvm-parallels-use-qemu-block-API.patch [bz#783950]
- kvm-dmg-fix-reading-of-uncompressed-chunks.patch [bz#783950]
- kvm-dmg-use-pread.patch [bz#783950]
- kvm-dmg-use-qemu-block-API.patch [bz#783950]
- kvm-cow-use-pread-pwrite.patch [bz#783950]
- kvm-cow-stop-using-mmap.patch [bz#783950]
- kvm-cow-use-qemu-block-API.patch [bz#783950]
- kvm-vpc-Implement-bdrv_flush.patch [bz#783950]
- kvm-vmdk-Fix-COW.patch [bz#783950]
- kvm-vmdk-Clean-up-backing-file-handling.patch [bz#783950]
- kvm-vmdk-Convert-to-bdrv_open.patch [bz#783950]
- kvm-block-set-sector-dirty-on-AIO-write-completion.patch [bz#783950]
- kvm-trace-Trace-bdrv_aio_flush.patch [bz#783950]
- kvm-block-Removed-unused-function-bdrv_write_sync.patch [bz#783950]
- kvm-tools-Use-real-async.c-instead-of-stubs.patch [bz#783950]
- kvm-Cleanup-Be-consistent-and-use-BDRV_SECTOR_SIZE-inste.patch [bz#783950]
- kvm-Cleanup-raw-posix.c-Be-more-consistent-using-BDRV_SE.patch [bz#783950]
- kvm-block-allow-resizing-of-images-residing-on-host-devi.patch [bz#783950]
- kvm-raw-posix-Fix-test-for-host-CD-ROM.patch [bz#783950]
- kvm-raw-posix-Fix-bdrv_flush-error-return-values.patch [bz#783950]
- kvm-block-raw-posix-Abort-on-pread-beyond-end-of-non-gro.patch [bz#783950]
- kvm-raw-posix-raw_pwrite-comment-fixup.patch [bz#783950]
- kvm-raw-posix-add-discard-support.patch [bz#783950]
- kvm-win32-pair-qemu_memalign-with-qemu_vfree.patch [bz#783950]
- kvm-qcow2-refcount-remove-write-only-variables.patch [bz#783950]
- kvm-qcow2-Use-Qcow2Cache-in-writeback-mode-during-loadvm.patch [bz#783950]
- kvm-qcow2-Add-bdrv_discard-support.patch [bz#783950]
- kvm-coroutine-introduce-coroutines.patch [bz#783950]
- kvm-block-Add-bdrv_co_readv-writev.patch [bz#783950]
- kvm-block-Emulate-AIO-functions-with-bdrv_co_readv-write.patch [bz#783950]
- kvm-block-Add-bdrv_co_readv-writev-emulation.patch [bz#783950]
- kvm-coroutines-Locks.patch [bz#783950]
- kvm-qcow2-Avoid-direct-AIO-callback.patch [bz#783950]
- kvm-block-Avoid-unchecked-casts-for-AIOCBs.patch [bz#783950]
- kvm-qcow2-Use-QLIST_FOREACH_SAFE-macro.patch [bz#783950]
- kvm-qcow2-Fix-in-flight-list-after-qcow2_cache_put-failu.patch [bz#783950]
- kvm-qcow2-Use-coroutines.patch [bz#783950]
- kvm-block-qcow-Don-t-ignore-immediate-read-write-and-oth.patch [bz#783950]
- kvm-qcow-Avoid-direct-AIO-callback.patch [bz#783950]
- kvm-qcow-Use-coroutines.patch [bz#783950]
- kvm-qcow-initialize-coroutine-mutex.patch [bz#783950]
- kvm-dma-Avoid-reentrancy-in-DMA-transfer-handlers.patch [bz#783950]
- kvm-Allow-nested-qemu_bh_poll-after-BH-deletion.patch [bz#783950]
- kvm-Revert-qed-avoid-deadlock-on-emulated-synchronous-I-.patch [bz#783950]
- kvm-async-Remove-AsyncContext.patch [bz#783950]
- kvm-coroutines-Use-one-global-bottom-half-for-CoQueue.patch [bz#783950]
- kvm-posix-aio-compat-Allow-read-after-EOF.patch [bz#783950]
- kvm-linux-aio-Fix-laio_submit-error-handling.patch [bz#783950]
- kvm-linux-aio-Allow-reads-beyond-the-end-of-growable-ima.patch [bz#783950]
- kvm-block-Use-bdrv_co_-instead-of-synchronous-versions-i.patch [bz#783950]
- kvm-qcow-qcow2-Allocate-QCowAIOCB-structure-using-stack.patch [bz#783950]
- kvm-Introduce-emulation-for-g_malloc-and-friends.patch [bz#783950]
- kvm-Convert-the-block-layer-to-g_malloc.patch [bz#783950]
- kvm-qcow2-Removed-unused-AIOCB-fields.patch [bz#783950]
- kvm-qcow2-removed-cur_nr_sectors-field-in-QCowAIOCB.patch [bz#783950]
- kvm-qcow2-remove-l2meta-from-QCowAIOCB.patch [bz#783950]
- kvm-qcow2-remove-cluster_offset-from-QCowAIOCB.patch [bz#783950]
- kvm-qcow2-remove-common-from-QCowAIOCB.patch [bz#783950]
- kvm-qcow2-reindent-and-use-while-before-the-big-jump.patch [bz#783950]
- kvm-qcow2-Removed-QCowAIOCB-entirely.patch [bz#783950]
- kvm-qcow2-remove-memory-leak.patch [bz#783950]
- kvm-qcow2-Properly-initialise-QcowL2Meta.patch [bz#783950]
- kvm-qcow2-Fix-error-cases-to-run-depedent-requests.patch [bz#783950]
- kvm-async-Allow-nested-qemu_bh_poll-calls.patch [bz#783950]
- kvm-block-directly-invoke-.bdrv_aio_-in-bdrv_co_io_em.patch [bz#783950]
- kvm-block-directly-invoke-.bdrv_-from-emulation-function.patch [bz#783950]
- kvm-block-split-out-bdrv_co_do_readv-and-bdrv_co_do_writ.patch [bz#783950]
- kvm-block-switch-bdrv_read-bdrv_write-to-coroutines.patch [bz#783950]
- kvm-block-switch-bdrv_aio_readv-to-coroutines.patch [bz#783950]
- kvm-block-mark-blocks-dirty-on-coroutine-write-completio.patch [bz#783950]
- kvm-block-switch-bdrv_aio_writev-to-coroutines.patch [bz#783950]
- kvm-block-drop-emulation-functions-that-use-coroutines.patch [bz#783950]
- kvm-raw-posix-remove-bdrv_read-bdrv_write.patch [bz#783950]
- kvm-block-use-coroutine-interface-for-raw-format.patch [bz#783950]
- kvm-block-drop-.bdrv_read-.bdrv_write-emulation.patch [bz#783950]
- kvm-block-drop-bdrv_has_async_rw.patch [bz#783950]
- kvm-trace-add-arguments-to-bdrv_co_io_em-trace-event.patch [bz#783950]
- kvm-block-rename-bdrv_co_rw_bh.patch [bz#783950]
- kvm-block-unify-flush-implementations.patch [bz#783950]
- kvm-block-drop-redundant-bdrv_flush-implementation.patch [bz#783950]
- kvm-block-add-bdrv_co_discard-and-bdrv_aio_discard-suppo.patch [bz#783950]
- kvm-block-add-a-CoMutex-to-synchronous-read-drivers.patch [bz#783950]
- kvm-block-take-lock-around-bdrv_read-implementations.patch [bz#783950]
- kvm-block-take-lock-around-bdrv_write-implementations.patch [bz#783950]
- kvm-block-change-flush-to-co_flush.patch [bz#783950]
- kvm-block-change-discard-to-co_discard.patch [bz#783950]
- kvm-coroutine-switch-per-thread-free-pool-to-a-global-po.patch [bz#783950]
- kvm-Fix-memory-leak-in-register-save-load-due-to-xsave-s.patch [bz#789417]
- kvm-x86-Avoid-runtime-allocation-of-xsave-buffer.patch [bz#789417]
- kvm-pc-add-6.3.0-machine-type.patch [bz#788682]
- Resolves: bz#783950
  (RFE: Backport corountine-based block layer)
- Resolves: bz#788682
  (add rhel6.3.0 machine type)
- Resolves: bz#789417
  (Fix memory leak in register save load due to xsave support)

* Mon Feb 13 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.227.el6
- kvm-pci-assign-Fix-multifunction-support.patch [bz#782161]
- Resolves: bz#782161
  (pci-assign: Fix multifunction support)

* Mon Feb 13 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.226.el6
- kvm-QMP-configure-script-enable-disable-for-live-snapsho.patch [bz#769111]
- kvm-qdev-Add-a-free-method-to-disassociate-chardev-from-.patch [bz#770512]
- kvm-virtio-console-no-need-to-remove-char-handlers-expli.patch [bz#770512]
- Resolves: bz#769111
  (RFE: Re-enable live snapshot feature, with configuration option to enable/disable.)
- Resolves: bz#770512
  (Virtio serial chardev will be still in use even failed to hot plug a serial port on it)

* Wed Feb 08 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.225.el6
- kvm-pci-assign-Fix-PCI_EXP_FLAGS_TYPE-shift.patch [bz#754565]
- kvm-pci-assign-Fix-PCIe-lnkcap.patch [bz#754565]
- kvm-pci-assign-Remove-bogus-PCIe-lnkcap-wmask-setting.patch [bz#754565]
- kvm-pci-assign-Harden-I-O-port-test.patch [bz#754565]
- kvm-redhat-updating-version-info-for-qemu-kvm-0.12.1.2-2.patch []
- Resolves: bz#754565
  (Fix device assignment Coverity issues)

* Tue Feb 07 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.224.el6
- kvm-virtio-blk-pass-full-status-to-the-guest.patch [bz#740504]
- Resolves: bz#740504
  (SCSI INQUIRY (opcode 0x12) to virtio devices in the KVM guest returns success even when the underlying host devices have failed.)

* Mon Feb 06 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.223.el6
- kvm-Simplify-qemu_realloc.patch [bz#758194]
- kvm-slirp-remove-dead-assignments-spotted-by-clang.patch [bz#758194]
- kvm-update-bochs-vbe-interface.patch [bz#758194]
- kvm-x86-remove-dead-assignments-spotted-by-clang-analyze.patch [bz#758194]
- kvm-Fix-tiny-leak-in-qemu_opts_parse.patch [bz#758194]
- kvm-Fix-uint8_t-comparisons-with-negative-values.patch [bz#758194]
- kvm-vl.c-Remove-dead-assignment.patch [bz#758194]
- kvm-remove-pointless-if-from-vl.c.patch [bz#758194]
- kvm-eepro100-initialize-a-variable-in-all-cases.patch [bz#758194]
- kvm-vnc-auth-sasl-fix-a-memory-leak.patch [bz#758194]
- kvm-loader-fix-a-file-descriptor-leak.patch [bz#758194]
- kvm-qemu-io-fix-a-memory-leak.patch [bz#758194]
- kvm-x86-Prevent-sign-extension-of-DR7-in-guest-debug.patch [bz#758194]
- kvm-pci-Fix-memory-leak.patch [bz#758194]
- kvm-Fix-warning-on-OpenBSD.patch [bz#758194]
- kvm-Fix-net_check_clients-warnings-make-it-per-vlan.patch [bz#758194]
- kvm-pcnet-Fix-sign-extension-make-ipxe-work-with-2G-RAM.patch [bz#758194]
- kvm-qcow2-Fix-memory-leaks-in-error-cases.patch [bz#758194]
- kvm-Do-not-use-dprintf.patch [bz#758194]
- kvm-qemu-io-fix-aio-help-texts.patch [bz#758194]
- kvm-Fix-lld-or-llx-printf-format-use.patch [bz#758194]
- kvm-vhost_net.c-v2-Fix-build-failure-introduced-by-0bfcd.patch [bz#758194]
- kvm-qemu-io-Fix-formatting.patch [bz#758194]
- kvm-qemu-io-Fix-if-scoping-bug.patch [bz#758194]
- kvm-fix-memory-leak-in-aio_write_f.patch [bz#758194]
- kvm-block-Fix-bdrv_open-use-after-free.patch [bz#758194]
- kvm-block-Remove-dead-code.patch [bz#758194]
- kvm-ide-Fix-off-by-one-error-in-array-index-check.patch [bz#758194]
- kvm-sysbus-Supply-missing-va_end.patch [bz#758194]
- kvm-Fix-warning-about-uninitialized-variable.patch [bz#758194]
- kvm-Error-check-find_ram_offset.patch [bz#758194]
- kvm-readline-Fix-buffer-overrun-on-re-add-to-history.patch [bz#758194]
- kvm-Clean-up-assertion-in-get_boot_devices_list.patch [bz#758194]
- kvm-malloc-shims-to-simplify-backporting.patch [bz#758194]
- kvm-ui-vnc-Convert-sasl.mechlist-to-g_malloc-friends.patch [bz#758194]
- kvm-x86-cpuid-move-CPUID-functions-into-separate-file.patch [bz#758194]
- kvm-x86-cpuid-Convert-remaining-strdup-to-g_strdup.patch [bz#758194]
- kvm-x86-cpuid-Plug-memory-leak-in-cpudef_setfield.patch [bz#758194]
- kvm-x86-cpuid-Fix-crash-on-cpu.patch [bz#758194]
- kvm-keymaps-Use-glib-memory-allocation-and-free-function.patch [bz#758194]
- kvm-ui-Plug-memory-leaks-on-parse_keyboard_layout-error-.patch [bz#758194]
- kvm-raw-posix-Always-check-paio_init-result.patch [bz#758194]
- kvm-posix-aio-compat-Plug-memory-leak-on-paio_init-error.patch [bz#758194]
- kvm-os-posix-Plug-fd-leak-in-qemu_create_pidfile.patch [bz#758194]
- kvm-qemu-sockets-Plug-fd-leak-on-unix_connect_opts-error.patch [bz#758194]
- kvm-usb-linux-Disable-legacy-proc-bus-usb-and-dev-bus-us.patch [bz#758194]
- kvm-ehci-add-assert.patch [bz#758194]
- kvm-slirp-Clean-up-net_slirp_hostfwd_remove-s-use-of-get.patch [bz#758194]
- kvm-cutils-Drop-broken-support-for-zero-strtosz-default_.patch [bz#758194]
- kvm-console-Fix-qemu_default_pixelformat-for-24-bpp.patch [bz#758194]
- kvm-console-Clean-up-confusing-indentation-in-console_pu.patch [bz#758194]
- kvm-console-Fix-console_putchar-for-CSI-J.patch [bz#758194]
- Resolves: bz#758194
  (Coverity omnibus)

* Tue Jan 31 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.222.el6
- kvm-qemu-img-rebase-Fix-segfault-if-backing-file-can-t-b.patch [bz#736942]
- kvm-usb-host-fix-host-close.patch [bz#746866]
- kvm-usb-host-add-usb_host_do_reset-function.patch [bz#769745]
- kvm-Fix-parse-of-usb-device-description-with-multiple-co.patch [bz#746866]
- kvm-usb-host-properly-release-port-on-unplug-exit.patch [bz#769745]
- kvm-Revert-QMP-HMP-Drop-the-live-snapshot-commands.patch [bz#752003]
- kvm-ccid-Fix-buffer-overrun-in-handling-of-VSC_ATR-messa.patch [bz#752003]
- Resolves: bz#736942
  (qcow2:Segment fault when rebase snapshot on iscsi disk but do no create the qcow2 file on it)
- Resolves: bz#746866
  (Passthrough then delete host usb stick too fast causes host usb stick missing)
- Resolves: bz#752003
  (EMBARGOED CVE-2011-4111 qemu: ccid: buffer overflow in handling of VSC_ATR message [rhel-6.3])
- Resolves: bz#769745
  (Released usb stick after passthrough fails to be reused on host)

* Thu Jan 26 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.221.el6
- kvm-pci-assign-Fix-PCI_EXP_FLAGS_TYPE-shift.patch [bz#754565]
- kvm-pci-assign-Fix-PCIe-lnkcap.patch [bz#754565]
- kvm-pci-assign-Remove-bogus-PCIe-lnkcap-wmask-setting.patch [bz#754565]
- kvm-pci-assign-Harden-I-O-port-test.patch [bz#754565]
- Resolves: bz#754565
  (Fix device assignment Coverity issues)

* Tue Jan 24 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.220.el6
- kvm-block-add-eject-request-callback.patch [bz#739944]
- kvm-atapi-implement-eject-requests.patch [bz#739944]
- Resolves: bz#739944
  (CD-ROMs cannot be ejected in virtualized Fedora 16)

* Thu Jan 19 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.219.el6
- kvm-KSM-add-manpage-entry-for-redhat-disable-KSM.patch [bz#719269]
- Resolves: bz#719269
  (No -redhat-disable-KSM introduction in man page)

* Mon Jan 16 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.218.el6
- kvm-e1000-prevent-buffer-overflow-when-processing-legacy.patch [bz#772086]
- CVE: CVE-2012-0029
- Resolves: bz#772086
  (EMBARGOED CVE-2012-0029 qemu-kvm: e1000: process_tx_desc legacy mode packets heap overflow [rhel-6.3])

* Fri Jan 13 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.217.el6
- kvm-virtio-blk-refuse-SG_IO-requests-with-scsi-off.patch [bz#756677]
- CVE: CVE-2011-4127
- Resolves: bz#756677
  (qemu-kvm: virtio-blk: refuse SG_IO requests with scsi=off (CVE-2011-4127 mitigation) [rhel-6.3)

* Wed Jan 11 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.216.el6
- kvm-usb-storage-cancel-I-O-on-reset.patch [bz#769760]
- Resolves: bz#769760
  (Formatting of usb-storage disk attached on usb-hub fails to end)

* Tue Jan 10 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.215.el6
- kvm-virtio-serial-kill-VirtIOSerialDevice.patch [bz#769528]
- kvm-virtio-serial-Clean-up-virtconsole-detection.patch [bz#769528]
- kvm-virtio-serial-Drop-useless-property-is_console.patch [bz#769528]
- kvm-virtio-serial-bus-Simplify-handle_output-function.patch [bz#769528]
- kvm-virtio-serial-Drop-redundant-VirtIOSerialPort-member.patch [bz#769528]
- kvm-virtio-console-Simplify-init-callbacks.patch [bz#769528]
- kvm-virtio-serial-Turn-props-any-virtio-serial-bus-devic.patch [bz#769528]
- kvm-virtio-console-Check-if-chardev-backends-available-b.patch [bz#769528]
- kvm-virtio-console-Properly-initialise-class-methods.patch [bz#769528]
- kvm-virtio-serial-bus-Ports-are-expected-to-implement-ha.patch [bz#769528]
- Resolves: bz#769528
  (virtio-serial: Backport code cleanups from upstream)

* Tue Jan 10 2012 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.214.el6
- kvm-ide-Make-it-explicit-that-ide_create_drive-can-t-fai.patch [bz#737879]
- kvm-qdev-Don-t-hw_error-in-qdev_init_nofail.patch [bz#737879]
- kvm-virtio-pci-Check-for-virtio_blk_init-failure.patch [bz#737879]
- kvm-virtio-blk-Fix-virtio-blk-s390-to-require-drive.patch [bz#737879]
- kvm-ide-scsi-virtio-blk-Reject-empty-drives-unless-media.patch [bz#737879]
- kvm-exit-if-drive-specified-is-invalid-instead-of-ignori.patch [bz#737879]
- kvm-qdev-Fix-comment-around-qdev_init_nofail.patch [bz#737879]
- kvm-Strip-trailing-n-from-error_report-s-first-argument.patch [bz#737879]
- kvm-scsi-virtio-blk-usb-msd-Clean-up-device-init-error-m.patch [bz#737879]
- Resolves: bz#737879
  (Qemu-kvm fails to exit when given invalid "-drive" option name or option value)

* Mon Dec 19 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.213.el6
- kvm-usb-hub-implement-reset.patch [bz#767499]
- kvm-usb-hub-wakeup-on-detach-too.patch [bz#767499]
- Resolves: bz#767499
  (windows (2k3 and 2k8) hit BSOD while booting guest with usb device)

* Thu Dec 15 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.212.el6
- kvm-bz716261-qemu-kvm-Fix-XSAVE-for-active-AVX-usage.patch [bz#716261]
- Resolves: bz#716261
  ([Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes)

* Tue Dec 13 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.211.el6
- kvm-enable-PIE-and-full-relro-for-qemu-kvm.patch [bz#738812]
- kvm-Fix-segfault-on-screendump-with-nographic.patch [bz#728385]
- kvm-usb-hub-don-t-trigger-assert-on-packet-completion.patch [bz#740707]
- kvm-qemu-char-Check-for-missing-backend-name.patch [bz#750738]
- kvm-monitor-use-after-free-in-do_wav_capture.patch [bz#749830]
- kvm-cirrus-fix-bank-unmap.patch [bz#594654]
- kvm-acl-Fix-use-after-free-in-qemu_acl_reset.patch [bz#749820]
- kvm-qdev-Fix-crash-on-device-x.patch [bz#757142]
- kvm-console-Fix-rendering-of-VGA-underline.patch [bz#757132]
- kvm-monitor-Fix-file_completion-to-check-for-stat-failur.patch [bz#757713]
- kvm-char-Disable-write-callback-if-throttled-chardev-is-.patch [bz#745758]
- Resolves: bz#594654
  (Random read/write /dev/port [vga] caused 'invalid parameters' error)
- Resolves: bz#728385
  (attempting to take a screenshot of a VM with no graphics crashes qemu)
- Resolves: bz#738812
  (qemu-kvm should be built with full relro and PIE support)
- Resolves: bz#740707
  (pass-through usb stick under usb 1.1 controller causes QEMU to abort with an assertion failure)
- Resolves: bz#745758
  (Segmentation fault occurs after hot unplug virtio-serial-pci while virtio-serial-port in use)
- Resolves: bz#749820
  (Use after free in acl_reset)
- Resolves: bz#749830
  (Use after free after wavcapture fails)
- Resolves: bz#750738
  (Segmentation fault if -chardev without backend)
- Resolves: bz#757132
  (VGA underline causes read beyond static array, draws crap pixels)
- Resolves: bz#757142
  (Invalid command line option -device '?=x' crashes)
- Resolves: bz#757713
  (File name completion in monitor can append '/' when it shouldn't)

* Wed Nov 23 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.210.el6
- kvm-ehci-fix-cpage-check.patch [bz#728843]
- Resolves: bz#728843
  (qemu-kvm: Some suspicious code (found by Coverity))

* Wed Nov 02 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.209.el6
- kvm-hda-do-not-mix-output-and-input-streams-RHBZ-740493-v2.patch [bz#740493]
- kvm-hda-do-not-mix-output-and-input-stream-states-RHBZ-740493-v2.patch [bz#740493]
- kvm-intel-hda-fix-stream-search.patch [bz#740493]
- Resolves: bz#740493
  (audio playing doesn't work when sound recorder is opened)

* Tue Nov 01 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.208.el6
- kvm-migration-flush-migration-data-to-disk.patch [bz#721114]
- Resolves: bz#721114
  (qemu fails to restore guests that were previously suspended on host shutdown)

* Mon Oct 31 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.207.el6
- kvm-migration-s-dprintf-DPRINTF-v2.patch [bz#669581]
- kvm-migration-simplify-state-assignmente-v2.patch [bz#669581]
- vm-migration-Check-that-migration-is-active-before-canc-v2.patch [bz#669581]
- kvm-Reorganize-and-fix-monitor-resume-after-migration-v2.patch [bz#669581]
- kvm-migration-add-error-handling-to-migrate_fd_put_notif-v2.patch [bz#669581]
- kvm-migration-If-there-is-one-error-it-makes-no-sense-to-v2.patch [bz#669581]
- kvm-buffered_file-Use-right-opaque-v2.patch [bz#669581]
- kvm-buffered_file-reuse-QEMUFile-has_error-field-v2.patch [bz#669581]
- kvm-migration-don-t-write-when-migration-is-not-active-v2.patch [bz#669581]
- kvm-migration-set-error-if-select-return-one-error-v2.patch [bz#669581]
- kvm-migration-change-has_error-to-contain-errno-values-v2.patch [bz#669581]
- kvm-migration-return-real-error-code-v2.patch [bz#669581]
- kvm-migration-rename-qemu_file_has_error-to-qemu_file_ge-v2.patch [bz#669581]
- kvm-savevm-Rename-has_error-to-last_error-field-v2.patch [bz#669581]
- kvm-migration-use-qemu_file_get_error-return-value-when--v2.patch [bz#669581]
- kvm-migration-make-save_live-return-errors-v2.patch [bz#669581]
- kvm-savevm-qemu_fille_buffer-used-to-return-one-error-fo-v2.patch [bz#669581]
- kvm-Fix-segfault-on-migration-completion.patch [bz#669581 bz#749806]
- Resolves: bz#669581
  (Migration Never end while Use firewall reject migration tcp port)
- Resolves: bz#749806
  (Migration segfault on migrate_fd_put_notify()/qemu_file_get_error())

* Fri Oct 28 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.206.el6
- kvm-Revert-savevm-qemu_fille_buffer-used-to-return-one-e.patch [bz#669581]
- kvm-Revert-migration-make-save_live-return-errors.patch [bz#669581]
- kvm-Revert-migration-use-qemu_file_get_error-return-valu.patch [bz#669581]
- kvm-Revert-savevm-Rename-has_error-to-last_error-field.patch [bz#669581]
- kvm-Revert-migration-rename-qemu_file_has_error-to-qemu_.patch [bz#669581]
- kvm-Revert-migration-return-real-error-code.patch [bz#669581]
- kvm-Revert-migration-change-has_error-to-contain-errno-v.patch [bz#669581]
- kvm-Revert-migration-set-error-if-select-return-one-erro.patch [bz#669581]
- kvm-Revert-migration-don-t-write-when-migration-is-not-a.patch [bz#669581]
- kvm-Revert-buffered_file-reuse-QEMUFile-has_error-field.patch [bz#669581]
- kvm-Revert-buffered_file-Use-right-opaque.patch [bz#669581]
- kvm-Revert-migration-If-there-is-one-error-it-makes-no-s.patch [bz#669581]
- kvm-Revert-migration-add-error-handling-to-migrate_fd_pu.patch [bz#669581]
- kvm-Revert-Reorganize-and-fix-monitor-resume-after-migra.patch [bz#669581]
- kvm-Revert-migration-Check-that-migration-is-active-befo.patch [bz#669581]
- kvm-Revert-migration-simplify-state-assignmente.patch [bz#669581]
- kvm-Revert-migration-s-dprintf-DPRINTF.patch [bz#669581]
- Related: bz#669581
  (Migration Never end while Use firewall reject migration tcp port)
- Fixes bz#749806
  (Migration segfault on migrate_fd_put_notify()/qemu_file_get_error())

* Thu Oct 27 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.205.el6
- kvm-qxl-fix-guest-cursor-tracking.patch [bz#744518]
- kvm-qxl-create-slots-on-post_load-in-vga-state.patch [bz#740547]
- kvm-qxl-reset-update_surface.patch [bz#690427]
- Resolves: bz#690427
  (qemu-kvm crashes when update/roll back of qxl driver in WindowsXP guest)
- Resolves: bz#740547
  (qxl: migrating when not in native mode causes a "panic: virtual address out of range")
- Resolves: bz#744518
  (qemu-kvm core dumps when qxl-linux guest migrate with reboot)

* Wed Oct 26 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.204.el6
- kvm-savevm-qemu_fille_buffer-used-to-return-one-error-fo.patch [bz#669581]
- Resolves: bz#669581
  (Migration Never end while Use firewall reject migration tcp port)

* Wed Oct 26 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.203.el6
- kvm-qemu-kvm-fix-improper-nmi-emulation-2.patch [bz#738565]
- Resolves: bz#738565
  ([FJ6.2 Bug]: Failed to capture kdump due to redundant NMIs)

* Wed Oct 26 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.202.el6
- kvm-Revert-qemu-kvm-fix-improper-nmi-emulation.patch [bz#738565]
- Related: bz#738565
  ([FJ6.2 Bug]: Failed to capture kdump due to redundant NMIs)

* Wed Oct 26 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.201.el6
- kvm-migration-s-dprintf-DPRINTF.patch [bz#669581]
- kvm-migration-simplify-state-assignmente.patch [bz#669581]
- kvm-migration-Check-that-migration-is-active-before-canc.patch [bz#669581]
- kvm-Reorganize-and-fix-monitor-resume-after-migration.patch [bz#669581]
- kvm-migration-add-error-handling-to-migrate_fd_put_notif.patch [bz#669581]
- kvm-migration-If-there-is-one-error-it-makes-no-sense-to.patch [bz#669581]
- kvm-buffered_file-Use-right-opaque.patch [bz#669581]
- kvm-buffered_file-reuse-QEMUFile-has_error-field.patch [bz#669581]
- kvm-migration-don-t-write-when-migration-is-not-active.patch [bz#669581]
- kvm-migration-set-error-if-select-return-one-error.patch [bz#669581]
- kvm-migration-change-has_error-to-contain-errno-values.patch [bz#669581]
- kvm-migration-return-real-error-code.patch [bz#669581]
- kvm-migration-rename-qemu_file_has_error-to-qemu_file_ge.patch [bz#669581]
- kvm-savevm-Rename-has_error-to-last_error-field.patch [bz#669581]
- kvm-migration-use-qemu_file_get_error-return-value-when-.patch [bz#669581]
- kvm-migration-make-save_live-return-errors.patch [bz#669581]
- kvm-qemu-kvm-fix-improper-nmi-emulation.patch [bz#738565]
- kvm-scsi-fix-accounting-of-writes.patch [bz#744780]
- kvm-scsi-disk-bump-SCSIRequest-reference-count-until-aio.patch [bz#744780]
- Resolves: bz#669581
  (Migration Never end while Use firewall reject migration tcp port)
- Resolves: bz#738565
  ([FJ6.2 Bug]: Failed to capture kdump due to redundant NMIs)
- Resolves: bz#744780
  (use-after-free in QEMU SCSI target code)

* Thu Oct 20 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.200.el6
- kvm-Introduce-the-RunState-type.patch [bz#617889]
- kvm-RunState-Add-additional-states.patch [bz#617889]
- kvm-runstate_set-Check-for-valid-transitions.patch [bz#617889]
- kvm-Drop-the-incoming_expected-global-variable.patch [bz#617889]
- kvm-Drop-the-vm_running-global-variable.patch [bz#617889]
- kvm-Monitor-QMP-Don-t-allow-cont-on-bad-VM-state.patch [bz#617889]
- kvm-QMP-query-status-Introduce-status-key.patch [bz#617889]
- kvm-HMP-info-status-Print-the-VM-state.patch [bz#617889]
- kvm-RunState-Rename-enum-values.patch [bz#617889]
- kvm-runstate-Allow-to-transition-from-paused-to-postmigr.patch [bz#617889]
- kvm-savevm-qemu_savevm_state-Drop-stop-VM-logic.patch [bz#617889]
- kvm-runstate-Allow-user-to-migrate-twice.patch [bz#617889]
- kvm-RunState-Don-t-abort-on-invalid-transitions.patch [bz#617889]
- Resolves: bz#617889
  (QMP: provide VM stop reason)

* Tue Oct 18 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.199.el6
- kvm-usb-hid-activate-usb-tablet-mouse-after-migration.patch [bz#741878]
- kvm-ps2-migrate-ledstate.patch [bz#729294]
- Resolves: bz#729294
  (Keyboard leds/states are not synchronized after migration of guest)
- Resolves: bz#741878
  (USB tablet mouse does not work well when migrating between 6.2<->6.2 hosts and 6.1<->6.2 hosts)

* Tue Oct 18 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.198.el6
- kvm-bz716261-kvm-Extend-kvm_arch_get_supported_cpuid-to-.patch [bz#716261]
- kvm-bz716261-Enable-XSAVE-related-CPUID.patch [bz#716261]
- kvm-bz716261-Fix-XSAVE-feature-bit-enumeration.patch [bz#716261]
- kvm-bz716261-Synchronize-kernel-headers.patch [bz#716261]
- kvm-bz716261-kvm-Enable-XSAVE-live-migration-support.patch [bz#716261]
- kvm-bz716261-Put-XSAVE-area-in-a-sub-section.patch [bz#716261]
- kvm-bz716261-Enable-xsave-as-a-cpu-flag.patch [bz#716261]
- kvm-allow-more-than-1T-in-KVM-x86-guest.patch [bz#743391]
- kvm-blockdev-Belatedly-remove-driveopts.patch [bz#742458]
- kvm-ide-Remove-useless-IDEDeviceInfo-members-unit-drive.patch [bz#742458]
- kvm-block-New-bdrv_next.patch [bz#742458]
- kvm-block-Decouple-savevm-from-DriveInfo.patch [bz#742458]
- kvm-savevm-Survive-hot-unplug-of-snapshot-device.patch [bz#743269]
- kvm-ide-Replace-IDEState-members-is_cdrom-is_cf-by-drive.patch [bz#742458]
- kvm-ide-split-ide-command-interpretation-off.patch [bz#742458]
- kvm-ide-fix-whitespace-gap-in-ide_exec_cmd.patch [bz#742458]
- kvm-trace-Trace-bdrv_set_locked.patch [bz#742458]
- kvm-atapi-Drives-can-be-locked-without-media-present.patch [bz#742469]
- kvm-atapi-Report-correct-errors-on-guest-eject-request.patch [bz#742458]
- kvm-ide-Split-atapi.c-out.patch [bz#742458]
- kvm-ide-atapi-Factor-commands-out.patch [bz#742458]
- kvm-ide-atapi-Use-table-instead-of-switch-for-commands.patch [bz#742458]
- kvm-ide-atapi-Replace-bdrv_get_geometry-calls-by-s-nb_se.patch [bz#742458]
- kvm-ide-atapi-Introduce-CHECK_READY-flag-for-commands.patch [bz#742458]
- kvm-atapi-Move-comment-to-proper-place.patch [bz#742458]
- kvm-atapi-Explain-why-we-need-a-media-not-present-state.patch [bz#742458]
- kvm-block-QMP-Deprecate-query-block-s-type-drop-info-blo.patch [bz#742458]
- kvm-blockdev-Make-eject-fail-for-non-removable-drives-ev.patch [bz#742476]
- kvm-block-Reset-device-model-callbacks-on-detach.patch [bz#742458]
- kvm-block-raw-win32-Drop-disabled-code-for-removable-hos.patch [bz#742458]
- kvm-block-Make-BlockDriver-method-bdrv_set_locked-return.patch [bz#742458]
- kvm-block-Make-BlockDriver-method-bdrv_eject-return-void.patch [bz#742458]
- kvm-block-Don-t-let-locked-flag-prevent-medium-load.patch [bz#742480]
- kvm-scsi-disk-Codingstyle-fixes.patch [bz#742458]
- kvm-scsi-Remove-references-to-SET_WINDOW.patch [bz#742458]
- kvm-scsi-Remove-REZERO_UNIT-emulation.patch [bz#742458]
- kvm-scsi-Sanitize-command-definitions.patch [bz#742458]
- kvm-scsi-disk-Remove-drive_kind.patch [bz#742458]
- kvm-scsi-disk-no-need-to-call-scsi_req_data-on-a-short-r.patch [bz#742458]
- kvm-scsi-pass-status-when-completing.patch [bz#742458]
- kvm-trace-Fix-harmless-mismerge-of-hw-scsi-bus.c-events.patch [bz#742458]
- kvm-scsi-move-sense-handling-to-generic-code.patch [bz#742458]
- kvm-block-Attach-non-qdev-devices-as-well.patch [bz#742458]
- kvm-block-Generalize-change_cb-to-BlockDevOps.patch [bz#742458]
- kvm-block-Split-change_cb-into-change_media_cb-resize_cb.patch [bz#742458]
- kvm-ide-Update-command-code-definitions-as-per-ACS-2-Tab.patch [bz#742458]
- kvm-ide-Clean-up-case-label-indentation-in-ide_exec_cmd.patch [bz#742458]
- kvm-ide-Give-vmstate-structs-internal-linkage-where-poss.patch [bz#742458]
- kvm-block-raw-Fix-to-forward-method-bdrv_media_changed.patch [bz#742458]
- kvm-block-Leave-tracking-media-change-to-device-models.patch [bz#742458]
- kvm-fdc-Make-media-change-detection-more-robust.patch [bz#742458]
- kvm-block-Clean-up-bdrv_flush_all.patch [bz#742458]
- kvm-savevm-Include-writable-devices-with-removable-media.patch [bz#742484]
- kvm-scsi-fill-in-additional-sense-length-correctly.patch [bz#742458]
- kvm-ide-Fix-ATA-command-READ-to-set-ATAPI-signature-for-.patch [bz#742458]
- kvm-ide-Use-a-table-to-declare-which-drive-kinds-accept-.patch [bz#742458]
- kvm-ide-Reject-ATA-commands-specific-to-drive-kinds.patch [bz#742458]
- kvm-ide-atapi-Clean-up-misleading-name-in-cmd_start_stop.patch [bz#742458]
- kvm-ide-atapi-Track-tray-open-close-state.patch [bz#742458]
- kvm-scsi-disk-Factor-out-scsi_disk_emulate_start_stop.patch [bz#742458]
- kvm-scsi-disk-Track-tray-open-close-state.patch [bz#742458]
- kvm-block-Revert-entanglement-of-bdrv_is_inserted-with-t.patch [bz#742458]
- kvm-block-Drop-tray-status-tracking-no-longer-used.patch [bz#742458]
- kvm-ide-atapi-Track-tray-locked-state.patch [bz#742458]
- kvm-scsi-disk-Track-tray-locked-state.patch [bz#742458]
- kvm-block-Leave-enforcing-tray-lock-to-device-models.patch [bz#742458]
- kvm-block-Drop-medium-lock-tracking-ask-device-models-in.patch [bz#742458]
- kvm-block-Rename-bdrv_set_locked-to-bdrv_lock_medium.patch [bz#742458]
- kvm-ide-atapi-Don-t-fail-eject-when-tray-is-already-open.patch [bz#742458]
- kvm-scsi-disk-Fix-START_STOP-to-fail-when-it-can-t-eject.patch [bz#742458]
- kvm-ide-atapi-Preserve-tray-state-on-migration.patch [bz#743342]
- kvm-block-Clean-up-remaining-users-of-removable.patch [bz#742458]
- kvm-block-Drop-BlockDriverState-member-removable.patch [bz#742458]
- kvm-block-Show-whether-the-virtual-tray-is-open-in-info-.patch [bz#723270]
- kvm-block-New-change_media_cb-parameter-load.patch [bz#742458]
- kvm-ide-atapi-scsi-disk-Make-monitor-eject-f-then-change.patch [bz#676528]
- Resolves: bz#676528
  (Can't insert media after previous media was forcefully ejected)
- Resolves: bz#716261
  ([Intel 6.2 FEAT] Add support for XSAVE/XRSTOR qemu-kvm changes)
- Resolves: bz#723270
  (Report cdrom tray status in a monitor command such as info block)
- Resolves: bz#742458
  (Tracker Bug:Big block layer backport)
- Resolves: bz#742469
  (Drives can not be locked without media present)
- Resolves: bz#742476
  (Make eject fail for non-removable drives even with -f)
- Resolves: bz#742480
  (Don't let locked flag prevent medium load)
- Resolves: bz#742484
  (should be also have  snapshot on floppy)
- Resolves: bz#743269
  (Hot unplug of snapshot device crashes)
- Resolves: bz#743342
  (IDE CD-ROM tray state gets lost on migration)
- Resolves: bz#743391
  (KVM guest limited to 40bit of physical address space)

* Mon Oct 17 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.197.el6
- kvm-device-assignment-pci_cap_init-add-82599-VF-quirk.patch [bz#742080]
- kvm-savevm-teach-qemu_fill_buffer-to-do-partial-refills.patch [bz#725565]
- kvm-savevm-some-coding-style-cleanups.patch [bz#725565]
- kvm-savevm-define-qemu_get_byte-using-qemu_peek_byte.patch [bz#725565]
- kvm-savevm-improve-subsections-detection-on-load.patch [bz#725565]
- kvm-Revert-savevm-fix-corruption-in-vmstate_subsection_l.patch [bz#725565]
- kvm-QMP-HMP-Drop-the-live-snapshot-commands.patch [bz#742401]
- kvm-usb-hub-wakeup-on-attach.patch [bz#733272]
- Resolves: bz#725565
  (migration subsections are still broken)
- Resolves: bz#733272
  (Usb stick passthrough failed under uhci+ehci)
- Resolves: bz#742080
  (Device assignment of 82599 VFs no longer work after patch for v1 PCIe Capability structures)
- Resolves: bz#742401
  (qemu-kvm disable live snapshot support)

* Tue Oct 11 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.196.el6
- kvm-usb-linux-add-get_endp.patch [bz#733272]
- kvm-usb-host-reapurb-error-report-fix.patch [bz#733272]
- kvm-usb-host-fix-halted-endpoints.patch [bz#733272]
- kvm-usb-host-limit-open-retries.patch [bz#733272]
- kvm-usb-host-fix-configuration-tracking.patch [bz#733272]
- kvm-usb-host-claim-port.patch [bz#733272]
- kvm-usb-host-endpoint-table-fixup.patch [bz#733272]
- kvm-usb-host-factor-out-code.patch [bz#733272]
- kvm-usb-host-handle-USBDEVFS_SETCONFIGURATION-returning-.patch [bz#733272]
- Resolves: bz#733272
  (Usb stick passthrough failed under uhci+ehci)

* Mon Oct 03 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.195.el6
- Require spice-server-devel >= 0.8.2-4 [bz#737921]
- Resolves: bz#737921
  (No Spice password is set on target host after migration)

* Mon Oct 03 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.194.el6
- kvm-spice-turn-client_migrate_info-to-async.patch [bz#737921]
- kvm-spice-support-the-new-migration-interface-spice-0.8..patch [bz#737921]
- kvm-pci-devfn-check-device-slot-number-in-range.patch [bz#678729]
- Resolves: bz#678729
  (Hotplug VF/PF with invalid addr value leading to qemu-kvm process quit with core dump)
- Resolves: bz#737921
  (No Spice password is set on target host after migration)

* Mon Sep 26 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.193.el6
- kvm-usb-bus-Don-t-allow-speed-mismatch-while-attaching-d.patch [bz#728120]
- kvm-usb-vmstate-add-parent-dev-path.patch [bz#734995]
- kvm-usb-claim-port-at-device-initialization-time.patch [bz#734995]
- kvm-usb-host-tag-as-unmigratable.patch [bz#723870]
- kvm-usb-storage-fix-NULL-pointer-dereference.patch [bz#733010]
- kvm-register-signal-handler-after-initializing-SDL.patch [bz#735716]
- kvm-report-that-QEMU-process-was-killed-by-a-signal.patch [bz#735716]
- kvm-Tidy-up-message-printed-when-we-exit-on-a-signal.patch [bz#735716]
- kvm-Monitor-Convert-do_screen_dump-to-QObject.patch [bz#729969]
- kvm-usb-hub-need-to-check-dev-attached.patch [bz#734995]
- kvm-usb-fix-port-reset.patch [bz#734995]
- kvm-qdev-print-bus-properties-too.patch [bz#678731]
- kvm-ide-link-BMDMA-and-IDEState-at-device-creation.patch [bz#739480]
- Resolves: bz#678731
  (Update qemu-kvm -device pci-assign,?  properties)
- Resolves: bz#723870
  (tag devices without migration support)
- Resolves: bz#728120
  (print error on usb speed mismatch between device and bus/port)
- Resolves: bz#729969
  (Make screendump command available in QMP)
- Resolves: bz#733010
  (core dump when issue fdisk -l in guest which has two usb-storage attached)
- Resolves: bz#734995
  (Core dump when hotplug three usb-hub into the same port under both uhci and ehci)
- Resolves: bz#735716
  (QEMU should report the PID of the process that sent it signals for troubleshooting purposes)
- Resolves: bz#739480
  (qemu-kvm core dumps when migration with reboot)

* Tue Sep 20 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.192.el6
- kvm-spice-workaround-a-spice-server-bug.patch [bz#697441]
- kvm-balloon-Disassociate-handlers-from-balloon-device-on.patch [bz#736975]
- kvm-virtio-balloon-Disassociate-from-the-balloon-handler.patch [bz#736975]
- kvm-virtio-serial-Plug-memory-leak-on-qdev-exit.patch [bz#738019]
- kvm-spice-set-qxl-ssd.running-true-before-telling-spice-.patch [bz#733993]
- kvm-qemu-kvm-vm_stop-pause-threads-before-calling-other-.patch [bz#729621]
- kvm-Fix-termination-by-signal-with-no-shutdown.patch [bz#738487]
- kvm-qemu-option-Remove-enable-nesting-from-help-text.patch [bz#738555]
- Resolves: bz#697441
  (JSON corruption when closing SPICE window)
- Resolves: bz#729621
  (ASSERT worker->running failed on source qemu during migration with Spice session)
- Resolves: bz#733993
  (migration target can crash (assert(d->ssd.running)))
- Resolves: bz#736975
  (Qemu-kvm fails to unregister virtio-balloon-pci device when unplugging)
- Resolves: bz#738019
  (Memleak in virtio-serial code: VirtIOSerialBus not freed)
- Resolves: bz#738487
  (Fix termination by signal with -no-shutdown)
- Resolves: bz#738555
  (Stop exposing -enable-nested)

* Mon Sep 19 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.191.el6
- kvm-CVE-2011-2527-os-posix-set-groups-properly-for-runas.patch [bz#722583]
- CVE: CVE-2011-2527
- Resolves: bz#722583
  (when started as root, extra groups are not dropped correctly)

* Thu Sep 15 2011 Michal Novotny <minovotn@redhat.com> - qemu-kvm-0.12.1.2-2.190.el6
- kvm-Add-flag-to-indicate-external-users-to-block-device.patch [bz#633370]
- kvm-block-enable-in_use-flag.patch [bz#633370]
- kvm-block-add-drive-copy-on-read-on-off.patch [bz#633370]
- kvm-qed-replace-is_write-with-flags-field.patch [bz#633370]
- kvm-qed-extract-qed_start_allocating_write.patch [bz#633370]
- kvm-qed-make-qed_aio_write_alloc-reusable.patch [bz#633370]
- kvm-qed-add-support-for-copy-on-read.patch [bz#633370]
- kvm-qed-avoid-deadlock-on-emulated-synchronous-I-O.patch [bz#633370]
- kvm-block-add-bdrv_aio_copy_backing.patch [bz#633370]
- kvm-qmp-add-block_stream-command.patch [bz#633370]
- kvm-qmp-add-block_job_cancel-command.patch [bz#633370]
- kvm-qmp-add-query-block-jobs-command.patch [bz#633370]
- kvm-qmp-add-block_job_set_speed-command.patch [bz#633370]
- kvm-block-add-drive-stream-on-off.patch [bz#633370]
- kvm-qed-intelligent-streaming-implementation.patch [bz#633370]
- Resolves: bz#633370
  ([6.1 FEAT] Enhance QED image format to support streaming from remote systems)

* Fri Sep 09 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.189.el6
- kvm-qemu-img-Require-larger-zero-areas-for-sparse-handli.patch [bz#730587]
- kvm-qxl-send-interrupt-after-migration-in-case-ram-int_p.patch [bz#732949]
- kvm-qxl-s-qxl_set_irq-qxl_update_irq.patch [bz#732949]
- kvm-block-include-flush-requests-in-info-blockstats-v2.patch [bz#715017]
- kvm-block-explicit-I-O-accounting-v2.patch [bz#715017]
- kvm-block-latency-accounting-v2.patch [bz#715017]
- Resolves: bz#715017
  (Report disk latency (read and write) for each storage device)
- Resolves: bz#730587
  (qemu-img convert takes 25m for specific images when using cache=none)
- Resolves: bz#732949
  (Guest screen becomes abnormal after migration with spice)

* Tue Sep 06 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.188.el6
- kvm-x86-Introduce-kvmclock-device-to-save-restore-it-fixed.patch [bz#658467]
- kvm-use-kernel-provided-para_features-instead-of-statica-take2.patch [bz#624983]
- kvm-add-kvmclock-to-its-second-bit-v2-take2.patch [bz#624983]
- kvm-create-kvmclock-when-one-of-the-flags-are-present-take2.patch [bz#624983]
- kvm-x86-Allow-multiple-cpu-feature-matches-of-lookup_fea-take2.patch [bz#624983]
- Resolves: bz#624983
  (QEMU should support the newer set of MSRs for kvmclock)
- Resolves: bz#658467
  (kvm clock breaks migration result stability -  for unit test propose)

* Tue Sep 06 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.187.el6
- Revert patches that broke the build
- kvm-Revert-block-latency-accounting.patch [bz#715017]
- kvm-Revert-block-explicit-I-O-accounting.patch [bz#715017]
- kvm-Revert-block-include-flush-requests-in-info-blocksta.patch [bz#715017]
- kvm-Revert-x86-Allow-multiple-cpu-feature-matches-of-loo.patch [bz#624983]
- kvm-Revert-kvm-create-kvmclock-when-one-of-the-flags-are.patch [bz#624983]
- kvm-Revert-add-kvmclock-to-its-second-bit-v2.patch [bz#624983]
- kvm-Revert-use-kernel-provided-para_features-instead-of-.patch [bz#624983]
- kvm-Revert-kvm-x86-Introduce-kvmclock-device-to-save-res.patch [bz#658467]
- Related: bz#624983
  (QEMU should support the newer set of MSRs for kvmclock)
- Related: bz#658467
  (kvm clock breaks migration result stability -  for unit test propose)
- Related: bz#715017
  (Report disk latency (read and write) for each storage device)

* Mon Sep 05 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.186.el6
- kvm-x86-Introduce-kvmclock-device-to-save-restore-it.patch [bz#658467]
- kvm-use-kernel-provided-para_features-instead-of-statica.patch [bz#624983]
- kvm-add-kvmclock-to-its-second-bit-v2.patch [bz#624983]
- kvm-create-kvmclock-when-one-of-the-flags-are-presen.patch [bz#624983]
- kvm-x86-Allow-multiple-cpu-feature-matches-of-lookup_fea.patch [bz#624983]
- kvm-vhost-net-cleanup-host-notifiers-at-last-step.patch [bz#695285]
- kvm-block-include-flush-requests-in-info-blockstats.patch [bz#715017]
- kvm-block-explicit-I-O-accounting.patch [bz#715017]
- kvm-block-latency-accounting.patch [bz#715017]
- kvm-revert-floppy-save-and-restore-DIR-register.patch [bz#718664]
- kvm-qemu-sockets-avoid-strlen-of-NULL-pointer.patch [bz#734860]
- Resolves: bz#624983
  (QEMU should support the newer set of MSRs for kvmclock)
- Resolves: bz#658467
  (kvm clock breaks migration result stability -  for unit test propose)
- Resolves: bz#695285
  (guest quit with "Guest moved used index from 256 to 915" error when save_vm)
- Resolves: bz#715017
  (Report disk latency (read and write) for each storage device)
- Resolves: bz#718664
  (Migration from host RHEL6.1+ to host RHEL6.0.z failed with floppy)
- Resolves: bz#734860
  (qemu-kvm: segfault when missing host parameter for socket chardev)

* Fri Aug 26 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.185.el6
- kvm-virtio-prevent-indirect-descriptor-buffer-overflow.patch [bz#713593]
- Resolves: bz#713593
  (CVE-2011-2212 virtqueue: too-large indirect descriptor buffer overflow [rhel-6.2])
- CVE: CVE-2011-2212

* Wed Aug 17 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.184.el6
- kvm-bz719818-KVM-qemu-support-for-SMEP.patch [bz#719818]
- kvm-vmstate-add-no_migrate-flag-to-VMStateDescription.patch [bz#723870]
- kvm-ehci-doesn-t-support-migration.patch [bz#723870]
- kvm-usb-storage-first-migration-support-bits.patch [bz#723870]
- Resolves: bz#719818
  (KVM qemu support for Supervisor Mode Execution Protection (SMEP))
- Resolves: bz#723870
  (tag devices without migration support)

* Mon Aug 15 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.183.el6
- kvm-spice-add-sanity-check-for-spice-ports.patch [bz#715582 bz#717958]
- kvm-block-add-discard-support.patch [bz#711354]
- kvm-qemu-option-New-qemu_opts_reset.patch [bz#711354]
- kvm-error-New-qemu_opts_loc_restore.patch [bz#711354]
- kvm-scsi-Rebase-to-upstream-v0.15.0-rc2.patch [bz#711354]
- kvm-qxl-upon-reset-if-spice-worker-is-stopped-the-comman.patch [bz#728984]
- kvm-qxl-allowing-the-command-rings-to-be-not-empty-when-.patch [bz#728984]
- Resolves: bz#711354
  (Fix and enable enough of SCSI to make usb-storage work)
- Resolves: bz#715582
  (qemu-kvm doesn't report error when supplied negative spice port value)
- Resolves: bz#717958
  (qemu-kvm start vnc even though -spice ... is supplied)
- Resolves: bz#728984
  (Target qemu process - assertion failed during migration)

* Sun Aug 14 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.182.el6
- kvm-spice-catch-spice-server-initialization-failures.patch [bz#682227]
- kvm-qcow2-Fix-L1-table-size-after-bdrv_snapshot_goto.patch [bz#729572]
- spec: require spice-server-devel >= 0.8.2-2 [bz#723676]
- kvm-Add-missing-trace-call-to-oslib-posix.c-qemu_vmalloc.patch [bz#714773]
- Resolves: bz#682227
  (qemu-kvm doesn't exit when binding to specified port fails)
- Resolves: bz#714773
  (qemu missing marker for qemu.kvm.qemu_vmalloc)
- Related: bz#723676
  (spice-server: update to upstream spice 0.8.2)
- Resolves: bz#729572
  (qcow2: Loading internal snapshot can corrupt image)

* Sun Aug 14 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.181.el6
- kvm-docs-Add-QED-image-format-specification.patch [bz#633380]
- kvm-qed-Add-QEMU-Enhanced-Disk-image-format.patch [bz#633380]
- kvm-qed-Table-L2-cache-and-cluster-functions.patch [bz#633380]
- kvm-qed-Read-write-support.patch [bz#633380]
- kvm-qed-Consistency-check-support.patch [bz#633380]
- kvm-docs-Fix-missing-carets-in-QED-specification.patch [bz#633380]
- kvm-qed-Refuse-to-create-images-on-block-devices.patch [bz#633380]
- kvm-qed-Images-with-backing-file-do-not-require-QED_F_NE.patch [bz#633380]
- kvm-docs-Describe-zero-data-clusters-in-QED-specificatio.patch [bz#633380]
- kvm-qed-Add-support-for-zero-clusters.patch [bz#633380]
- kvm-qed-Fix-consistency-check-on-32-bit-hosts.patch [bz#633380]
- kvm-block-add-BDRV_O_INCOMING-migration-consistency-hint.patch [bz#633380]
- kvm-qed-honor-BDRV_O_INCOMING-for-live-migration-support.patch [bz#633380]
- spec file: spec-file-whitelist-QED-image-format [bz#633380]
- kvm-qemu-tool-Stub-out-qemu-timer-functions.patch [bz#633380]
- kvm-qed-Periodically-flush-and-clear-need-check-bit.patch [bz#633380]
- kvm-qed-support-for-growing-images.patch [bz#633380]
- kvm-usb-ehci-trace-rename-next-to-nxt.patch [bz#720979]
- kvm-qxl-make-sure-primary-surface-is-saved-on-migration.patch [bz#729869]
- Resolves: bz#633380
  ([6.2 FEAT] Include QED image format for KVM guests)
- Resolves: bz#720979
  (do not use next  as a variable name in qemu-kvm systemtap tapset)
- Resolves: bz#729869
  (qxl: primary surface not saved on migration)

* Thu Aug 11 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.180.el6
- kvm-virtio-event-index-support.patch [bz#710943]
- kvm-pc-rhel-6.1-and-back-compat-event-idx-support.patch [bz#710943]
- kvm-qdev-implement-qdev_prop_set_bit.patch [bz#729104]
- kvm-pci-insert-assert-that-auto-assigned-address-functio.patch [bz#729104]
- kvm-pci-introduce-multifunction-property.patch [bz#729104]
- kvm-pci_bridge-make-pci-bridge-aware-of-pci-multi-functi.patch [bz#729104]
- kvm-pci-set-multifunction-property-for-normal-device.patch [bz#729104]
- kvm-pci-don-t-overwrite-multi-functio-bit-in-pci-header-.patch [bz#729104]
- kvm-pci-set-PCI-multi-function-bit-appropriately.patch [bz#729104]
- kvm-Add-user_print-handler-to-qxl_screendump-monitor-com.patch [bz#705070]
- Resolves: bz#705070
  (QMP: screendump command does not allow specification of monitor to capture)
- Resolves: bz#710943
  (event index support in virtio and vhost-net)
- Resolves: bz#729104
  (qemu-kvm: pci needs multifunction property)

* Wed Aug 10 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.179.el6
- kvm-usb-linux-make-iso-urb-count-contigurable.patch [bz#723858 bz#723863]
- kvm-usb-linux-track-inflight-iso-urb-count.patch [bz#723858 bz#723863]
- kvm-ehci-add-freq-maxframes-properties.patch [bz#723858 bz#723863]
- kvm-usb-bus-Don-t-allow-attaching-a-device-to-a-bus-with.patch [bz#723858 bz#723863]
- kvm-usb-Proper-error-propagation-for-usb_device_attach-e.patch [bz#723858 bz#723863]
- kvm-usb-Add-a-speedmask-to-devices.patch [bz#723858 bz#723863]
- kvm-usb-linux-allow-compatible-high-speed-devices-to-con.patch [bz#723858 bz#723863]
- kvm-usb-ignore-USB_DT_DEBUG.patch [bz#723858 bz#723863]
- kvm-usb-Add-a-usb_fill_port-helper-function.patch [bz#723858 bz#723863]
- kvm-usb-Move-initial-call-of-usb_port_location-to-usb_fi.patch [bz#723858 bz#723863]
- kvm-usb-Add-a-register_companion-USB-bus-op.patch [bz#723858 bz#723863]
- kvm-usb-Make-port-wakeup-and-complete-ops-take-a-USBPort.patch [bz#723858 bz#723863]
- kvm-usb-Replace-device_destroy-bus-op-with-a-child_detac.patch [bz#723858 bz#723863]
- kvm-usb-ehci-drop-unused-num-ports-state-member.patch [bz#723858 bz#723863]
- kvm-usb-ehci-Connect-Status-bit-is-read-only-don-t-allow.patch [bz#723858 bz#723863]
- kvm-usb-ehci-cleanup-port-reset-handling.patch [bz#723858 bz#723863]
- kvm-usb-assert-on-calling-usb_attach-port-NULL-on-a-port.patch [bz#723858 bz#723863]
- kvm-usb-ehci-Fix-handling-of-PED-and-PEDC-port-status-bi.patch [bz#723858 bz#723863]
- kvm-usb-ehci-Add-support-for-registering-companion-contr.patch [bz#723858 bz#723863]
- kvm-usb-uhci-Add-support-for-being-a-companion-controlle.patch [bz#723858 bz#723863]
- kvm-pci-add-ich9-usb-controller-ids.patch [bz#723858 bz#723863]
- kvm-uhci-add-ich9-controllers.patch [bz#723858 bz#723863]
- kvm-ehci-fix-port-count.patch [bz#723858 bz#723863]
- kvm-ehci-add-ich9-controller.patch [bz#723858 bz#723863]
- kvm-usb-documentation-update.patch [bz#723858 bz#723863]
- kvm-usb-fixup-bluetooth-descriptors.patch [bz#723858 bz#723863]
- kvm-usb-hub-remove-unused-descriptor-arrays.patch [bz#723858 bz#723863]
- kvm-usb-update-documentation.patch [bz#723858 bz#723863]
- kvm-usb_register_port-do-not-set-port-opaque-and-port-in.patch [bz#723858 bz#723863]
- kvm-qxl-fix-cmdlog-for-vga.patch [bz#700134]
- kvm-qxl-interface_get_command-fix-reported-mode.patch [bz#700134]
- kvm-spice-add-worker-wrapper-functions.patch [bz#700134]
- kvm-spice-add-qemu_spice_display_init_common.patch [bz#700134]
- kvm-spice-qxl-move-worker-wrappers.patch [bz#700134]
- kvm-qxl-fix-surface-tracking-locking.patch [bz#700134]
- kvm-qxl-add-io_port_to_string.patch [bz#700134]
- kvm-qxl-error-handling-fixes-and-cleanups.patch [bz#700134]
- kvm-qxl-make-qxl_guest_bug-take-variable-arguments.patch [bz#700134]
- kvm-qxl-put-QXL_IO_UPDATE_IRQ-into-vgamode-whitelist.patch [bz#700134]
- kvm-qxl-allow-QXL_IO_LOG-also-in-vga.patch [bz#700134]
- kvm-qxl-only-disallow-specific-io-s-in-vga-mode.patch [bz#700134]
- kvm-qxl-async-io-support-using-new-spice-api.patch [bz#700134]
- kvm-qxl-add-QXL_IO_FLUSH_-SURFACES-RELEASE-for-guest-S3-.patch [bz#706711]
- kvm-qxl-Remove-support-for-the-unused-unstable-device-ID.patch [bz#706711]
- kvm-qxl-bump-pci-rev.patch [bz#706711]
- kvm-move-balloon-handling-to-balloon.c.patch [bz#694378]
- kvm-balloon-Make-functions-local-vars-static.patch [bz#694378]
- kvm-balloon-Add-braces-around-if-statements.patch [bz#694378]
- kvm-balloon-Simplify-code-flow.patch [bz#694378]
- kvm-virtio-balloon-Separate-status-handling-into-separat.patch [bz#694378]
- kvm-balloon-Separate-out-stat-and-balloon-handling.patch [bz#694378]
- kvm-balloon-Fix-header-comment-add-Copyright.patch [bz#694378]
- kvm-virtio-balloon-Fix-header-comment-add-Copyright.patch [bz#694378]
- kvm-balloon-Don-t-allow-multiple-balloon-handler-registr.patch [bz#725625]
- kvm-virtio-balloon-Check-if-balloon-registration-failed.patch [bz#725625]
- kvm-balloon-Reject-negative-balloon-values.patch [bz#694373]
- kvm-virtio-balloon-Add-exit-handler-fix-memleaks.patch [bz#726014]
- kvm-virtio-balloon-Unregister-savevm-section-on-device-u.patch [bz#726023]
- kvm-virtio-blk-Fix-memleak-on-exit.patch [bz#726015]
- kvm-virtio-net-don-t-use-vdev-after-virtio_cleanup.patch [bz#726020]
- kvm-virtio-Plug-memleak-by-freeing-vdev.patch [bz#726020]
- kvm-qemu-img-Use-qemu_blockalign.patch [bz#728905]
- kvm-Fix-automatically-assigned-network-names-for-netdev.patch [bz#623907]
- kvm-Fix-netdev-name-lookup-in-device-device_add-netdev_d.patch [bz#623907]
- kvm-do-not-reset-no_shutdown-after-we-shutdown-the-vm.patch [bz#728464]
- Resolves: bz#623907
  (device_add rejects valid netdev when NIC with same ID exists)
- Resolves: bz#694373
  (ballooning value reset to original value after setting a negative number)
- Resolves: bz#694378
  (Core dump occurs when ballooning memory to 0)
- Resolves: bz#700134
  ([qemu-kvm] - qxl runs i/o requests synchronously)
- Resolves: bz#706711
  (qemu-kvm process quits when windows guest doing S3 w/ qxl device)
- Resolves: bz#723858
  (usb: add companion controller support)
- Resolves: bz#723863
  (usb: fixes various issues.)
- Resolves: bz#725625
  (Hot unplug one virtio balloon device cause another balloon device unavailable)
- Resolves: bz#726014
  (Fix memleak on exit in virtio-balloon)
- Resolves: bz#726015
  (Fix memleak on exit in virtio-blk)
- Resolves: bz#726020
  (Fix memleaks in all virtio devices)
- Resolves: bz#726023
  (Migration after hot-unplug virtio-balloon will not succeed)
- Resolves: bz#728464
  (QEMU does not honour '-no-shutdown' flag after the first shutdown attempt)
- Resolves: bz#728905
  (qemu-img: use larger output buffer for cache option "none")

* Fri Aug 05 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.178.el6
- Require new sgabios package [bz#684949]
- Resolves: bz#684949
  ([RFE] Ability to display VM BIOS messages on boot)

* Thu Aug 04 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.177.el6
- kvm-Revert-hw-qxl-render-drop-cursor-locks-replace-with-.patch [bz#674583 bz#705070]
- kvm-Revert-qxl-spice-remove-qemu_mutex_-un-lock_iothread.patch [bz#674583 bz#705070]
- kvm-Revert-qxl-implement-get_command-in-vga-mode-without.patch [bz#674583 bz#705070]
- kvm-Revert-qxl-spice-display-move-pipe-to-ssd.patch [bz#674583 bz#705070]
- kvm-spice-don-t-create-updates-in-spice-server-context.patch [bz#674583 bz#705070]
- kvm-spice-don-t-call-displaystate-callbacks-from-spice-s.patch [bz#674583 bz#705070]
- kvm-spice-drop-obsolete-iothread-locking.patch [bz#674583 bz#705070]
- kvm-Make-spice-dummy-functions-inline-to-fix-calls-not-c.patch [bz#674583 bz#705070]
- kvm-add-qdev_find_by_id.patch [bz#674583 bz#705070]
- kvm-add-qxl_screendump-monitor-command.patch [bz#674583 bz#705070]
- Resolves: bz#674583
  (qemu-kvm build fails without --enable-spice)
- Resolves: bz#705070
  (QMP: screendump command does not allow specification of monitor to capture)

* Wed Aug 03 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.176.el6
- kvm-net-Consistently-use-qemu_macaddr_default_if_unset.patch [bz#712046]
- kvm-virtio-serial-bus-replay-guest_open-on-migration.patch [bz#725965]
- kvm-qdev-Fix-printout-of-bit-device-properties-with-bit-.patch [bz#727580]
- Resolves: bz#712046
  (Qemu allocates an existed macaddress to hotpluged nic)
- Resolves: bz#725965
  (spice client mouse doesn't work after migration)
- Resolves: bz#727580
  (bit property doesn't print correctly)

* Fri Jul 29 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.175.el6
- kvm-report-serial-devices-created-with-device-in-the-PII.patch [bz#707130]
- kvm-device-assignment-handle-device-with-incorrect-PCIe-.patch [bz#720972]
- Resolves: bz#707130
  (ACPI description of serial and parallel ports incorrect with -chardev/-device)
- Resolves: bz#720972
  (Unable to attach PCI device on a booted virt guest)

* Thu Jul 28 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.174.el6
- kvm-usb-hid-RHEL-6.1-migration-compatibility.patch [bz#720237]
- Resolves: bz#720237
  (usb migration compatibility)

* Thu Jul 28 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.173.el6
- kvm-Change-snapshot_blkdev-hmp-to-use-correct-argument-t.patch [bz#676982]
- kvm-QMP-add-snapshot-blkdev-sync-command.patch [bz#676982]
- kvm-Add-missing-documentation-for-qemu-img-p.patch [bz#722728]
- Resolves: bz#676982
  (RFE: no qmp command for live snapshot)
- Resolves: bz#722728
  (Update qemu-img convert/re-base man page)

* Mon Jul 25 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.172.el6
- kvm-ide-Split-error-status-from-status-register.patch [bz#698537]
- kvm-ide-Fix-ide_drive_pio_state_needed.patch [bz#698537]
- kvm-ide-Add-forgotten-VMSTATE_END_OF_LIST-in-subsection.patch [bz#698537]
- kvm-ide-Clear-error_status-after-restarting-flush.patch [bz#698537]
- kvm-qemu-img-Add-cache-command-line-option.patch [bz#713743]
- kvm-virtio-serial-bus-use-bh-for-unthrottling.patch [bz#709397]
- kvm-usb-bluetooth-compile-out.patch [bz#723864]
- kvm-clarify-support-statement-in-KVM-help.patch [bz#725054]
- Resolves: bz#698537
- Resolves: bz#709397
- Resolves: bz#713743
- Resolves: bz#723864
- Resolves: bz#725054

* Wed Jul 13 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.171.el6
- kvm-Add-qemu_ram_alloc_from_ptr-function.patch [bz#696102]
- kvm-exec-remove-code-duplication-in-qemu_ram_alloc-and-q.patch [bz#696102]
- kvm-Move-extern-of-mem_prealloc-to-cpu-all.h.patch [bz#696102]
- kvm-Add-qemu_ram_remap.patch [bz#696102]
- kvm-s390-Detect-invalid-invocations-of-qemu_ram_free-rem.patch [bz#696102]
- kvm-MCE-unpoison-memory-address-across-reboot.patch [bz#696102]
- Resolves: bz#696102
  ([Intel 6.2 FEAT] KVM: un-poison page when guest reboot: QEMU part)

* Wed Jul 13 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.170.el6
- kvm-raw-posix-Linearize-direct-I-O-on-Linux-NFS.patch [bz#711213]
- kvm-virtio-console-Prevent-abort-s-in-case-of-host-chard.patch [bz#720535]
- Resolves: bz#711213
  (QEMU should use pass preadv/pwritev a single vector when using cache=none and NFS)
- Resolves: bz#720535
  ((virtio serial) Guest aborted when transferring data from guest to host)

* Fri Jul 08 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.169.el6
- kvm-rtl8139-cleanup-FCS-calculation.patch [bz#583922]
- kvm-rtl8139-add-vlan-tag-extraction.patch [bz#583922]
- kvm-rtl8139-add-vlan-tag-insertion.patch [bz#583922]
- kvm-usb-serial-Fail-instead-of-crash-when-chardev-is-mis.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-Add-exit-notifiers.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-Return-usb-device-to-host-on-usb_del-command.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-Return-usb-device-to-host-on-exit.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Store-devpath-into-USBHostDevice-when-usb_.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-introduce-a-usb_linux_get_configuration-fu.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Get-the-active-configuration-from-sysfs-ra.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-data-structs-and-helpers-for-usb-descriptors.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hid-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-serial-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-storage-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-scsi-disk-fix-build-disable-cdrom-emulation.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-enable-usb-storage-scsi-bus-scsi-disk.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-wacom-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-bluetooth-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hub-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-descriptors-add-settable-strings.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-storage-serial-number-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-network-use-new-descriptor-infrastructure.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-move-USB_REQ_SET_ADDRESS-handling-to-common-code.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-move-USB_REQ_-GET-SET-_CONFIGURATION-handling-to.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-move-remote-wakeup-handling-to-common-code.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-create-USBPortOps-move-attach-there.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-rework-attach-detach-workflow.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-usb_wakeup-wakeup-callback-to-port-ops.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-uhci-remote-wakeup-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hub-remote-wakeup-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hid-remote-wakeup-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hid-change-serial-number-to-42.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-speed-mask-to-ports.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-attach-callback.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-usb_desc_attach.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-device-qualifier-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-storage-high-speed-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-storage-fix-status-reporting.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-storage-handle-long-responses.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-mass-storage-fix.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-keep-track-of-physical-port-address.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-port-property.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-rewrite-fw-path-fix-numbering.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-zap-pdev-from-usbport.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-USB-keyboard-emulation-key-mapping-error.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hid-modifiers-should-generate-an-event.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-keyboard-add-event-event-queue.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hid-move-head-n-to-common-struct.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-core-add-migration-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hub-add-migration-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-hid-add-migration-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-bus-use-snprintf.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-Add-bootindex-handling-into-usb-storage-device.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-trivial-spelling-fixes.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-initialise-data-element-in-Linux-USB_DISCONNECT-.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-introduce-a-usb_linux_alt_setting-function.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Get-the-alt.-setting-from-sysfs-rather-the.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-s-dprintf-DPRINTF-to-reduce-conflicts.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Add-support-for-buffering-iso-usb-packets.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Refuse-packets-for-endpoints-which-are-not.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Refuse-iso-packets-when-max-packet-size-is.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-We-only-need-to-keep-track-of-15-endpoints.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Add-support-for-buffering-iso-out-usb-pack.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-control-buffer-fixes.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-uhci-switch-to-QTAILQ-cherry-picked-from-commit-ddf6.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-uhci-keep-uhci-state-pointer-in-async-packet-struct.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-ohci-get-ohci-state-via-container_of.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-musb-get-musb-state-via-container_of-cherry-picked-f.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-move-complete-callback-to-port-ops-cherry-picked.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Add-missing-break-statement.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-Add-Interface-Association-Descriptor-descriptor-.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-update-config-descriptors-to-identify-number-of-.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-remove-fallback-to-bNumInterfaces-if-no-.nif.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-support-for-grouped-interfaces-and-the-Inter.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-Bug-757654-UHCI-fails-to-signal-stall-response-patch.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-Pass-the-packet-to-the-device-s-handle_control-c.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-use-usb_generic_handle_packet.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-fix-device-path-aka-physical-port-handling.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-add-hostport-property.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-track-aurbs-in-list.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-walk-async-urb-list-in-cancel.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-split-large-xfers.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-fix-max_packet_size-for-highspeed.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-storage-don-t-call-usb_packet_complete-twice.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-usb_handle_packet.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-keep-track-of-packet-owner.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-move-cancel-callback-to-USBDeviceInfo.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-add-ehci-adapter.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-catch-ENODEV-in-more-places.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-trace-mmio-and-usbsts-usb-ehci-trace-mmio-a.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-trace-state-machine-changes.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-trace-port-state.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-improve-mmio-tracing.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-ehci-trace-workaround.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-trace-buffer-copy.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-add-queue-data-struct.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-multiqueue-support.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-fix-offset-writeback-in-ehci_buffer_rw.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-fix-error-handling.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-ehci-fix-a-number-of-unused-but-set-variable-warning.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-cancel-async-packets-on-unplug.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-drop-EXECUTING-checks.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-Fix-USB-mouse-Set_Protocol-behavior.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-The-USB-tablet-should-not-claim-boot-protocol-suppor.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-itd-handling-fixes.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-ehci-split-trace-calls-to-handle-arg-count-limit.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Get-speed-from-sysfs-rather-then-from-the-.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Teach-about-super-speed.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Don-t-do-perror-when-errno-is-not-set.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Ensure-devep-0.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Don-t-try-to-open-the-same-device-twice.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-only-cleanup-in-host_close-when-host_open-.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-linux-Enlarge-buffer-for-descriptors-to-8192-byt.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-bus-Add-knowledge-of-USB_SPEED_SUPER-to-usb_spee.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- kvm-usb-bus-Don-t-detach-non-attached-devices-on-device-.patch [bz#561414 bz#632299 bz#645351 bz#711354]
- Resolves: bz#561414
  (Writes to virtual usb-storage produce I/O errors)
- Resolves: bz#583922
  (Guests in same vlan could not ping successfully using rtl8139 nic)
- Resolves: bz#632299
  (higher CPU load observed for virtualization workload on RHEL 6 than on RHEL 5.5)
- Resolves: bz#645351
  (Add support for USB 2.0 (EHCI) to QEMU)
- Resolves: bz#711354
  (Fix and enable enough of SCSI to make usb-storage work)

* Wed Jul 06 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.168.el6
- kvm-vnc-fix-numlock-capslock-tracking.patch [bz#599306]
- kvm-Add-an-isa-device-for-SGA.patch [bz#684949]
- kvm-pc-add-rhel-6.2-pc-and-make-it-the-default.patch [bz#716906]
- Resolves: bz#599306
  (Some strange behaviors on key's appearance viewed by using vnc)
- Resolves: bz#684949
  ([RFE] Ability to display VM BIOS messages on boot)
- Resolves: bz#716906
  (add 6.2 machine type)

* Thu Jun 30 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.167.el6
- kvm-qemu-img-create-Fix-displayed-default-cluster-size.patch [bz#570830]
- kvm-Fix-the-RARP-protocol-ID.patch [bz#715141]
- Resolves: bz#570830
  (The 'cluster_size' shows wrong size to zero when creating a qcow2 without specify the option)
- Resolves: bz#715141
  (Wrong Ethertype for RARP)

* Wed Jun 29 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.166.el6
- kvm-virtio-guard-against-negative-vq-notifies.patch [bz#707094]
- kvm-blockdev-Belatedly-remove-MAX_DRIVES.patch [bz#627585]
- kvm-blockdev-Hide-QEMUMachine-from-drive_init.patch [bz#627585]
- kvm-qdev-Move-declaration-of-qdev_init_bdrv-into-qdev.h.patch [bz#627585]
- kvm-blockdev-Collect-block-device-code-in-new-blockdev.c.patch [bz#627585]
- kvm-Fix-regression-for-drive-file.patch [bz#627585]
- kvm-block-Move-error-actions-from-DriveInfo-to-BlockDriv.patch [bz#627585]
- kvm-blockdev-Fix-error-message-for-invalid-drive-CHS.patch [bz#627585]
- kvm-blockdev-Make-drive_init-use-error_report.patch [bz#627585]
- kvm-blockdev-Put-BlockInterfaceType-names-and-max_devs-i.patch [bz#627585]
- kvm-blockdev-Fix-regression-in-drive-if-scsi-index-N.patch [bz#627585]
- kvm-blockdev-Make-drive_add-take-explicit-type-index-par.patch [bz#627585]
- kvm-blockdev-Factor-drive_index_to_-bus-unit-_id-out-of-.patch [bz#627585]
- kvm-blockdev-New-drive_get_by_index.patch [bz#627585]
- kvm-blockdev-Reject-multiple-definitions-for-the-same-dr.patch [bz#627585]
- kvm-blockdev-Replace-drive_add-s-fmt-.-by-optstr-paramet.patch [bz#627585]
- kvm-blockdev-Fix-drive_add-for-drives-without-media.patch [bz#627585]
- kvm-blockdev-Plug-memory-leak-in-drive_uninit.patch [bz#627585]
- kvm-blockdev-Plug-memory-leak-in-drive_init-error-paths.patch [bz#627585]
- kvm-vhost-fix-double-free-on-device-stop.patch [bz#699635]
- kvm-QMP-QError-New-QERR_UNSUPPORTED.patch [bz#644919]
- kvm-QMP-add-inject-nmi-qmp-command.patch [bz#644919]
- kvm-HMP-Use-QMP-inject-nmi-implementation.patch [bz#644919]
- Resolves: bz#627585
  (Improve error messages for bad options in -drive and -device)
- Resolves: bz#644919
  (RFE: QMP command to trigger an NMI in the guest)
- Resolves: bz#699635
  ([REG][6.1] After executing virsh dump with --live option and the completion, the subsequent virsh dump command to the same domain behaves abnormally)
- Resolves: bz#707094
  (qemu-kvm: OOB memory access caused by negative vq notifies [rhel-6.2])

* Tue Jun 14 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.165.el6
- kvm-ide-Factor-ide_dma_set_inactive-out.patch [bz#701775]
- kvm-ide-Set-bus-master-inactive-on-error.patch [bz#701775]
- kvm-ide-cleanup-warnings.patch [bz#701775]
- kvm-virtio-correctly-initialize-vm_running.patch [bz#701442]
- kvm-Add-virtio-disk-identification-support.patch [bz#710349]
- kvm-spice-add-option-for-disabling-copy-paste-support-rh.patch [bz#693645]
- Resolves: bz#693645
  (RFE: add spice option to enable/disable copy paste)
- Resolves: bz#701442
  (vhost-net not enabled on hotplug)
- Resolves: bz#701775
  (KVM: stdio is flooded)
- Resolves: bz#710349
  (Backport serial number support for virtio-blk devices)

* Tue Jun 07 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.164.el6
- kvm-e1000-check-buffer-availability.patch [bz#684127]
- kvm-Add-error-message-for-loading-snapshot-without-VM-st.patch [bz#680378]
- kvm-BZ710046-qemu-kvm-prints-warning-Using-CPU-model.patch [bz#710046]
- Resolves: bz#680378
  (no error message when loading zero size internal snapshot)
- Resolves: bz#684127
  (e1000:Execute multiple netperf clients caused system call interrupted)
- Resolves: bz#710046
  (qemu-kvm prints warning "Using CPU model [...]" (with patch))

* Mon Jun 06 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.163.el6
- kvm-qemu-img-Initial-progress-printing-support.patch [bz#621482]
- kvm-Add-dd-style-SIGUSR1-progress-reporting.patch [bz#621482]
- kvm-Remove-obsolete-enabled-variable-from-progress-state.patch [bz#621482]
- kvm-qemu-progress.c-printf-isn-t-signal-safe.patch [bz#621482]
- kvm-qemu-img.c-Remove-superfluous-parenthesis.patch [bz#621482]
- kvm-Add-documentation-for-qemu_progress_-init-print.patch [bz#621482]
- kvm-Add-qerror-message-if-the-change-target-filename-can.patch [bz#655719]
- Resolves: bz#621482
  ([RFE] Be able to get progress from qemu-img)
- Resolves: bz#655719
  (no error pops when change cd to non-exist file)

* Mon May 16 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.162.el6
- kvm-virtio-serial-Disallow-generic-ports-at-id-0.patch [bz#700511]
- kvm-virtio-serial-Don-t-clear-have_data-pointer-after-un.patch [bz#681736]
- kvm-char-Prevent-multiple-devices-opening-same-chardev.patch [bz#656779]
- kvm-char-Allow-devices-to-use-a-single-multiplexed-chard.patch [bz#656779]
- kvm-char-Detect-chardev-release-by-NULL-handlers-as-well.patch [bz#656779]
- kvm-virtio-console-Keep-chardev-open-for-other-users-aft.patch [bz#700512]
- kvm-Revert-cdrom-Make-disc-change-event-visible-to-guest.patch [bz#700065]
- kvm-Revert-cdrom-Allow-the-TEST_UNIT_READY-command-after.patch [bz#700065]
- kvm-atapi-Add-medium-ready-to-medium-not-ready-transitio.patch [bz#700065]
- Resolves: bz#656779
  (Core dumped when hot plug/un-plug virtio serial port to the same chardev)
- Resolves: bz#681736
  (Guest->Host communication stops for other ports after one port is unplugged)
- Resolves: bz#700065
  (Switch to upstream solution for cdrom patches)
- Resolves: bz#700511
  (virtio-serial: Disallow generic ports at id 0)
- Resolves: bz#700512
  (Keep chardev open for later reuse)

* Tue May 03 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.161.el6
- kvm-Fix-phys-memory-client-pass-guest-physical-address-n.patch [bz#700859]
- Resolves: bz#700859
  (Fix phys memory client for vhost)

* Wed Apr 27 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.160.el6
- kvm-virtio-blk-fail-unaligned-requests.patch [bz#698910]
- kvm-Ignore-pci-unplug-requests-for-unpluggable-devices.patch [bz#699789]
- Resolves: bz#698910
  (CVE-2011-1750 virtio-blk: heap buffer overflow caused by unaligned requests [rhel-6.1])
- Resolves: bz#699789
  (CVE-2011-1751 acpi_piix4: missing hotplug check during device removal [rhel-6.1])

* Tue Apr 19 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.159.el6
- kvm-acpi_piix4-Maintain-RHEL6.0-migration.patch [bz#694095]
- Resolves: bz#694095
  (Migration fails when migrate guest from RHEL6.1 host to RHEL6 host with the same libvirt version)

* Tue Apr 12 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.158.el6
- kvm-bz-691704-vhost-skip-VGA-memory-regions.patch [bz#691704]
- kvm-ide-atapi-add-support-for-GET-EVENT-STATUS-NOTIFICAT.patch [bz#558256]
- kvm-atapi-Allow-GET_EVENT_STATUS_NOTIFICATION-after-medi.patch [bz#558256]
- kvm-atapi-Move-GET_EVENT_STATUS_NOTIFICATION-command-han.patch [bz#558256]
- kvm-atapi-GESN-Use-structs-for-commonly-used-field-types.patch [bz#558256]
- kvm-atapi-GESN-Standardise-event-response-handling-for-f.patch [bz#558256]
- kvm-atapi-GESN-implement-media-subcommand.patch [bz#558256]
- Resolves: bz#558256
  (rhel6 disk not detected first time in install)
- Resolves: bz#691704
  (Failed to boot up windows guest with huge memory and cpu and vhost=on within 30 mins)

* Tue Apr 12 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.157.el6
- kvm-qemu-img-rebase-Fix-read-only-new-backing-file.patch [bz#693741]
- kvm-floppy-save-and-restore-DIR-register.patch [bz#681777]
- kvm-block-Do-not-cache-device-size-for-removable-media.patch [bz#687900]
- kvm-cdrom-Allow-the-TEST_UNIT_READY-command-after-a-cdro.patch [bz#683877]
- kvm-cdrom-Make-disc-change-event-visible-to-guests.patch [bz#683877]
- Resolves: bz#681777
  (floppy I/O error after live migration while floppy in use)
- Resolves: bz#683877
  (RHEL6 guests fail to update cdrom block size on media change)
- Resolves: bz#687900
  (qemu host cdrom support not properly updating guests on media changes at physical CD/DVD drives)
- Resolves: bz#693741
  (qemu-img re-base  fail with read-only new backing file)

* Wed Apr 06 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.156.el6
- kvm-Revert-net-socket-allow-ipv6-for-net_socket_listen_i.patch [bz#680356]
- kvm-Revert-Use-getaddrinfo-for-migration.patch [bz#680356]
- Related: bz#680356
  (Live migration failed in ipv6 environment)
- Fixes bz#694196
  (RHEL 6.1 qemu-kvm: Specifying ipv6 addresses breaks migration)

* Wed Apr 06 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.155.el6
- kvm-configure-fix-out-of-tree-build-with-enable-spice.patch [bz#641833]
- kvm-ccid-card-emulated-replace-DEFINE_PROP_ENUM-with-DEF.patch [bz#641833]
- kvm-Revert-qdev-properties-add-PROP_TYPE_ENUM.patch [bz#641833]
- kvm-Revert-qdev-add-data-pointer-to-Property.patch [bz#641833]
- kvm-Revert-qdev-add-print_options-callback.patch [bz#641833]
- kvm-ccid-v18_upstream-v25-cleanup.patch [bz#641833]
- kvm-libcacard-vscard_common.h-upstream-v18-v25-diff.patch [bz#641833]
- kvm-ccid-card-passthru-upstream-v18-upstream-v25-diff.patch [bz#641833]
- kvm-qemu-thread-add-qemu_mutex-cond_destroy-and-qemu_mut.patch [bz#641833]
- kvm-adding-qemu-thread.o-to-obj-y.patch [bz#641833]
- kvm-ccid-card-emulated-v18-v25.patch [bz#641833]
- kvm-libcacard-v18-upstream-v25.patch [bz#641833]
- Resolves: bz#641833
  (Spice CAC support - qemu)

* Tue Apr 05 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.154.el6
- kvm-add-a-service-to-reap-zombies-use-it-in-SLIRP.patch [bz#678524]
- kvm-Don-t-allow-multiwrites-against-a-block-device-witho.patch [bz#654682]
- kvm-Do-not-delete-BlockDriverState-when-deleting-the-dri.patch [bz#654682]
- kvm-virtio-serial-don-t-crash-on-invalid-input.patch [bz#690174]
- Resolves: bz#678524
  (Exec based migration randomly fails, particularly under high load)
- Resolves: bz#690174
  (virtio-serial qemu-kvm crash on invalid input in migration)
- Resolves: bz#654682
  (drive_del command to let libvirt safely remove block device from guest)

* Tue Mar 29 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.153.el6
- kvm-Revert-spice-qxl-locking-fix-for-qemu-kvm.patch [bz#678208]
- kvm-qxl-spice-display-move-pipe-to-ssd.patch [bz#678208]
- kvm-qxl-implement-get_command-in-vga-mode-without-locks.patch [bz#678208]
- kvm-qxl-spice-remove-qemu_mutex_-un-lock_iothread-around.patch [bz#678208]
- kvm-hw-qxl-render-drop-cursor-locks-replace-with-pipe.patch [bz#678208]
- kvm-spice-qemu-char.c-add-throttling.patch [bz#672191]
- kvm-spice-qemu-char.c-remove-intermediate-buffer.patch [bz#672191]
- kvm-spice-qemu-char-Fix-flow-control-in-client-guest-dir.patch [bz#672191]
- kvm-chardev-Allow-frontends-to-notify-backends-of-guest-.patch [bz#688572]
- kvm-virtio-console-notify-backend-of-guest-open-close.patch [bz#688572]
- kvm-spice-chardev-listen-to-frontend-guest-open-close.patch [bz#688572]
- kvm-Fix-performance-regression-in-qemu_get_ram_ptr.patch [bz#690267]
- kvm-virtio-pci-fix-bus-master-work-around-on-load.patch [bz#682243]
- kvm-Use-getaddrinfo-for-migration.patch [bz#680356]
- kvm-net-socket-allow-ipv6-for-net_socket_listen_init-and.patch [bz#680356]
- kvm-block-Fix-serial-number-assignment.patch [bz#688058]
- Resolves: bz#672191
  (spicevmc: flow control on the spice agent channel is missing in both directions)
- Resolves: bz#678208
  (qemu-kvm hangs when installing guest with -spice option)
- Resolves: bz#680356
  (Live migration failed in ipv6 environment)
- Resolves: bz#682243
  ([KVM] pci hotplug after migration breaks virtio_net.)
- Resolves: bz#688058
  (Drive serial number gets truncated)
- Resolves: bz#688572
  (spice-server does not switch back to server mouse mode if guest spice-agent dies.)
- Resolves: bz#690267
  (Backport qemu_get_ram_ptr() performance improvement)
- Related: bz#672191
  (spicevmc: flow control on the spice agent channel is missing in both directions)

* Tue Mar 22 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.152.el6
- kvm-device-assignment-register-a-reset-function.patch [bz#685147]
- kvm-device-assignment-Reset-device-on-system-reset.patch [bz#685147]
- Resolves: bz#685147
  (guest with assigned nic got kernel panic when send system_reset signal in QEMU monitor)

* Fri Mar 18 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.151.el6
- kvm-net-Add-the-missing-option-declaration-of-vhostforce.patch [bz#683295]
- kvm-vhost-fix-dirty-page-handling.patch [bz#684076]
- kvm-block-qcow2.c-rename-qcow_-functions-to-qcow2_.patch [bz#688119]
- kvm-Add-proper-errno-error-return-values-to-qcow2_open.patch [bz#688119]
- kvm-QCOW2-bug-fix-read-base-image-beyond-its-size.patch [bz#688147]
- kvm-qcow2-Fix-error-handling-for-immediate-backing-file-.patch [bz#688146]
- kvm-qcow2-Fix-error-handling-for-reading-compressed-clus.patch [bz#688146]
- kvm-qerror-Add-QERR_UNKNOWN_BLOCK_FORMAT_FEATURE.patch [bz#688119]
- kvm-qcow2-Report-error-for-version-2.patch [bz#688119]
- kvm-qcow2-Fix-order-in-L2-table-COW.patch [bz#688146]
- kvm-pci-assign-Catch-missing-KVM-support.patch [bz#688428]
- Resolves: bz#683295
  (qemu-kvm: Invalid parameter 'vhostforce')
- Resolves: bz#684076
  (Segfault occurred during migration)
- Resolves: bz#688119
  (qcow2: qcow2_open doesn't return useful errors)
- Resolves: bz#688146
  (qcow2: Some paths fail to handle I/O errors)
- Resolves: bz#688147
  (qcow2: Reads fail with backing file smaller than snapshot)
- Resolves: bz#688428
  (qemu-kvm -no-kvm segfaults on pci_add)

* Wed Mar 09 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.150.el6
- kvm-Improve-error-handling-in-do_snapshot_blkdev.patch [bz#676529]
- Resolves: bz#676529
  (core dumped when save snapshot to non-exist disk)

* Thu Mar 03 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.149.el6
- kvm-Fix-error-message-in-drive_init.patch [bz#607598]
- kvm-block-Use-error-codes-from-lower-levels-for-error-me.patch [bz#607598]
- kvm-device-assignment-Don-t-skip-closing-unmapped-resour.patch [bz#680058]
- Resolves: bz#607598
  (Incorrect & misleading error reporting when failing to open a drive due to block driver whitelist denial)
- Resolves: bz#680058
  (can't hotplug second vf successful with message "Too many open files")

* Thu Feb 24 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.148.el6
- kvm-ide-Make-ide_init_drive-return-success.patch [bz#655735]
- kvm-ide-Reject-readonly-drives-unless-CD-ROM.patch [bz#655735]
- kvm-ide-Reject-invalid-CHS-geometry.patch [bz#655735]
- kvm-Move-KVM-and-Xen-global-flags-to-vl.c.patch [bz#662701]
- kvm-qemu-kvm-Switch-to-upstream-enable-kvm-semantics.patch [bz#662701]
- Update BuildRequire for newer spice-server [bz#672035]
- Resolves: bz#655735
  (qemu-kvm (or libvirt?) permission denied errors when exporting readonly IDE disk to guest)
- Resolves: bz#662701
  (Option -enable-kvm should exit when KVM is unavailable)
- Related: bz#672035
  (spice-server: rebase to upstream 0.8 for RHEL-6.1)

* Fri Feb 18 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.147.el6
- kvm-e1000-clear-EOP-for-multi-buffer-descriptors.patch [bz#678338]
- kvm-e1000-verify-we-have-buffers-upfront.patch [bz#678338]
- kvm-tracetool-Add-optional-argument-to-specify-dtrace-pr.patch [bz#672441]
- kvm-Specify-probe-prefix-to-make-dtrace-probes-use-qemu-.patch [bz#672441]
- Resolves: bz#672441
  (Tracetool autogenerate qemu-kvm.stp with wrong qemu-kvm path)
- Resolves: bz#678338
  (e1000 behaving out of spec after increasing MTU)

* Wed Feb 16 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.146.el6
- kvm-USB-HID-does-not-support-Set_Idle.patch [bz#665025]
- kvm-add-event-queueing-to-USB-HID.patch [bz#665025]
- Spec patch to reenable CONFIG_VMMOUSE and CONFIG_VMPORT [bz#616187 (the original feature-disable bug) bz#677712 bz#677712 (the new broken migration bug)]
- Resolves: bz#665025
  (lost double clicks on slow connections)
- Resolves: bz#677712
  (disabling vmware device emulation breaks old->new migration)

* Tue Feb 15 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.145.el6
- kvm-make-tsc-stable-over-migration-and-machine-start.patch [bz#662386]
- kvm-qemu-kvm-Close-all-block-drivers-on-quit.patch [bz#635527]
- kvm-net-notify-peer-about-link-status-change.patch [bz#676015]
- kvm-vhost-disable-on-tap-link-down.patch [bz#676015]
- kvm-Add-config-devices.h-again.patch [bz#616187]
- kvm-Add-CONFIG_VMWARE_VGA-v2.patch [bz#616187]
- kvm-add-CONFIG_VMMOUSE-option-v2.patch [bz#616187]
- kvm-add-CONFIG_VMPORT-option-v2.patch [bz#616187]
- kvm-blockdev-Fix-drive_del-not-to-crash-when-drive-is-no.patch [bz#677222]
- Resolves: bz#616187
  (vmware device emulation enabled but not supported)
- Resolves: bz#635527
  (KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk)
- Resolves: bz#662386
  (tsc clock breaks migration result stability)
- Resolves: bz#676015
  (set_link <tap> off not working with vhost-net)
- Resolves: bz#677222
  (segment fault happens after hot drive add then drive delete)
- Related: bz#635527
  (KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk)

* Tue Feb 08 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.144.el6
- kvm-V3-Bug-619259-qemu-cpu-check-enforce-should-work-eve.patch [bz#619259]
- kvm-Bug-675229-Install-of-cpu-x86_64.conf-bombs-for-an-o.patch [bz#675229]
- kvm-e1000-multi-buffer-packet-support.patch [bz#602205]
- Resolves: bz#602205
  (Could not ping guest successfully after changing e1000 MTU)
- Resolves: bz#619259
  (qemu "-cpu [check | enforce ]" should work even when a model name is not specified on the command line)
- Resolves: bz#675229
  (Install of cpu-x86_64.conf bombs for an out of tree build..)

* Mon Feb 07 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.143.el6
- kvm-fix-syntax-error-introduced-by-virtio-serial-Disable.patch [bz#588916]
- Resolves: bz#588916
  (qemu char fixes for nonblocking writes, virtio-console flow control)

* Mon Feb 07 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.142.el6
- kvm-ide-Remove-redundant-IDEState-member-conf.patch [bz#654682]
- kvm-ide-Split-ide_init1-off-ide_init2-v2.patch [bz#654682]
- kvm-ide-Change-ide_init_drive-to-require-valid-dinfo-arg.patch [bz#654682]
- kvm-ide-Split-non-qdev-code-off-ide_init2.patch [bz#654682]
- kvm-qdev-Don-t-leak-string-property-value-on-hot-unplug.patch [bz#654682]
- kvm-blockdev-New-drive_get_by_blockdev-v2.patch [bz#654682]
- kvm-blockdev-Clean-up-automatic-drive-deletion-v2.patch [bz#654682]
- kvm-qdev-Decouple-qdev_prop_drive-from-DriveInfo-v2.patch [bz#654682]
- kvm-block-Catch-attempt-to-attach-multiple-devices-to-a-.patch [bz#654682]
- kvm-Implement-drive_del-to-decouple-block-removal-from-d.patch [bz#654682]
- kvm-blockdev-check-dinfo-ptr-before-using-v2.patch [bz#654682]
- kvm-qcow2-Add-full-image-preallocation-option.patch [bz#634652]
- kvm-savevm-fix-corruption-in-vmstate_subsection_load.patch [bz#671100]
- kvm-virtio-serial-Disable-flow-control-for-RHEL-5.0-mach.patch [bz#588916]
- Resolves: bz#588916
  (qemu char fixes for nonblocking writes, virtio-console flow control)
- Resolves: bz#634652
  ([RFE] qemu-img qcow2 'pre-allocation' should not only pre-allocate meta-data, but also data)
- Resolves: bz#654682
  (drive_del command to let libvirt safely remove block device from guest)
- Resolves: bz#671100
  (possible migration failure due to erroneous interpretation of subsection)

* Mon Feb 07 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.141.el6
- spec file: symlink to stdvga and vmware vgabios images [bz#638468]
- Related: bz#638468
  ([qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug)

* Mon Feb 07 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.140.el6
- spec file: require new vgabios images (stdvga and vmware) [bz#638468]
- Related: bz#638468
  ([qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug)

* Mon Feb 07 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.139.el6
- kvm-Revert-Drop-qemu_mutex_iothread-during-migration.patch [bz#643970]
- Related: bz#643970
  (guest migration turns failed by the end (16G + stress load))

* Fri Feb 04 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.138.el6
- kvm-virtio-console-Factor-out-common-init-between-consol.patch [bz#588916]
- kvm-virtio-console-Remove-unnecessary-braces.patch [bz#588916]
- kvm-virtio-serial-Use-a-struct-to-pass-config-informatio.patch [bz#588916]
- kvm-Fold-send_all-wrapper-unix_write-into-one-function.patch [bz#588916]
- kvm-char-Add-a-QemuChrHandlers-struct-to-initialise-char.patch [bz#588916]
- kvm-virtio-serial-move-out-discard-logic-in-a-separate-f.patch [bz#588916]
- kvm-virtio-serial-Make-sure-virtqueue-is-ready-before-di.patch [bz#588916]
- kvm-virtio-serial-Don-t-copy-over-guest-buffer-to-host.patch [bz#588916]
- kvm-virtio-serial-Let-virtio-serial-bus-know-if-all-data.patch [bz#588916]
- kvm-virtio-serial-Add-support-for-flow-control.patch [bz#588916]
- kvm-virtio-serial-Add-rhel6.0.0-compat-property-for-flow.patch [bz#588916]
- kvm-virtio-serial-save-restore-new-fields-in-port-struct.patch [bz#588916]
- kvm-Convert-io-handlers-to-QLIST.patch [bz#588916]
- kvm-iohandlers-Add-enable-disable_write_fd_handler-funct.patch [bz#588916]
- kvm-char-Add-framework-for-a-write-unblocked-callback.patch [bz#588916]
- kvm-char-Update-send_all-to-handle-nonblocking-chardev-w.patch [bz#588916]
- kvm-char-Equip-the-unix-tcp-backend-to-handle-nonblockin.patch [bz#588916]
- kvm-char-Throttle-when-host-connection-is-down.patch [bz#588916 bz#621484]
- kvm-virtio-console-Enable-port-throttling-when-chardev-i.patch [bz#588916]
- kvm-Add-spent-time-to-migration.patch [bz#643970]
- kvm-No-need-to-iterate-if-we-already-are-over-the-limit.patch [bz#643970]
- kvm-don-t-care-about-TLB-handling.patch [bz#643970]
- kvm-Only-calculate-expected_time-for-stage-2.patch [bz#643970]
- kvm-Count-nanoseconds-with-uint64_t-not-doubles.patch [bz#643970]
- kvm-Exit-loop-if-we-have-been-there-too-long.patch [bz#643970]
- kvm-Maintaing-number-of-dirty-pages.patch [bz#643970]
- kvm-Drop-qemu_mutex_iothread-during-migration.patch [bz#643970]
- Resolves: bz#588916
  (qemu char fixes for nonblocking writes, virtio-console flow control)
- Resolves: bz#621484
  (Broken pipe when working with unix socket chardev)
- Resolves: bz#643970
  (guest migration turns failed by the end (16G + stress load))

* Fri Feb 04 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.137.el6
- kvm-Add-support-for-o-octet-bytes-format-as-monitor-para.patch [bz#515775]
- kvm-block-add-block_resize-monitor-command.patch [bz#515775]
- kvm-block-tell-drivers-about-an-image-resize.patch [bz#515775]
- kvm-virtio-blk-tell-the-guest-about-size-changes.patch [bz#515775]
- kvm-qdev-add-print_options-callback.patch [bz#641833]
- kvm-qdev-add-data-pointer-to-Property.patch [bz#641833]
- kvm-qdev-properties-add-PROP_TYPE_ENUM.patch [bz#641833]
- kvm-usb-ccid-add-CCID-bus.patch [bz#641833]
- kvm-introduce-libcacard-vscard_common.h.patch [bz#641833]
- kvm-ccid-add-passthru-card-device.patch [bz#641833]
- kvm-libcacard-initial-commit.patch [bz#641833]
- kvm-ccid-add-ccid-card-emulated-device-v2.patch [bz#641833]
- kvm-ccid-add-docs.patch [bz#641833]
- kvm-ccid-configure-fix-enable-disable-flags.patch [bz#641833]
- Note: smartcard spec patch applied by hand [bz#641833]
- Resolves: bz#515775
  ([RFE] Include support for online resizing of storage and network block devices)
- Resolves: bz#641833
  (Spice CAC support - qemu)

* Fri Feb 04 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.136.el6
- kvm-Introduce-fw_name-field-to-DeviceInfo-structure.patch [bz#643687]
- kvm-Introduce-new-BusInfo-callback-get_fw_dev_path.patch [bz#643687]
- kvm-Keep-track-of-ISA-ports-ISA-device-is-using-in-qdev.patch [bz#643687]
- kvm-Add-get_fw_dev_path-callback-to-ISA-bus-in-qdev.patch [bz#643687]
- kvm-Store-IDE-bus-id-in-IDEBus-structure-for-easy-access.patch [bz#643687]
- kvm-Add-get_fw_dev_path-callback-to-IDE-bus.patch [bz#643687]
- kvm-Add-get_fw_dev_path-callback-for-system-bus.patch [bz#643687]
- kvm-Add-get_fw_dev_path-callback-for-pci-bus.patch [bz#643687]
- kvm-Record-which-USBDevice-USBPort-belongs-too.patch [bz#643687]
- kvm-Add-get_fw_dev_path-callback-for-usb-bus.patch [bz#643687]
- kvm-Add-get_fw_dev_path-callback-to-scsi-bus.patch [bz#643687]
- kvm-Add-bootindex-parameter-to-net-block-fd-device.patch [bz#643687]
- kvm-Change-fw_cfg_add_file-to-get-full-file-path-as-a-pa.patch [bz#643687]
- kvm-Add-bootindex-for-option-roms.patch [bz#643687]
- kvm-Add-notifier-that-will-be-called-when-machine-is-ful.patch [bz#643687]
- kvm-Pass-boot-device-list-to-firmware.patch [bz#643687]
- kvm-close-all-the-block-drivers-before-the-qemu-process-.patch [bz#635527]
- kvm-qemu-img-snapshot-Use-writeback-caching.patch [bz#635527]
- kvm-qcow2-Add-QcowCache.patch [bz#635527]
- kvm-qcow2-Use-QcowCache.patch [bz#635527]
- kvm-qcow2-Batch-flushes-for-COW.patch [bz#635527]
- Commited 'Remove vhost blacklisting' by hand [bz#665299]
- kvm-add-bootindex-parameter-to-assigned-device.patch [bz#643687]
- kvm-tap-safe-sndbuf-default.patch [bz#674539]
- kvm-do-not-pass-NULL-to-strdup.patch [bz#643687]
- kvm-Use-Makefile-to-install-qemu-kvm-in-correct-location.patch [bz#672441]
- kvm-Fix-CVE-2011-0011-qemu-kvm-Setting-VNC-password-to-e.patch [bz#667976]
- kvm-vhost-force-vhost-off-for-non-MSI-guests.patch [bz#674562]
- Resolves: bz#635527
  (KVM:qemu-img re-base poor performance(on local storage) when snapshot to a new disk)
- Resolves: bz#643687
  (Allow to specify boot order on qemu command line.)
- Resolves: bz#665299
  (load vhost-net by default)
- Resolves: bz#667976
  (CVE-2011-0011 qemu-kvm: Setting VNC password to empty string silently disables all authentication [rhel-6.1])
- Resolves: bz#672441
  (Tracetool autogenerate qemu-kvm.stp with wrong qemu-kvm path)
- Resolves: bz#674539
  (slow guests block other guests on the same lan)
- Resolves: bz#674562
  (disable vhost-net for rhel5 and older guests)

* Wed Feb 02 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.135.el6
- kvm-Bug-625333-qemu-treatment-of-nodefconfig-and-readcon.patch [bz#625333]
- kvm-ide-Factor-ide_flush_cache-out.patch [bz#670539]
- kvm-ide-Handle-flush-failure.patch [bz#670539]
- kvm-virtio-blk-Respect-werror-option-for-flushes.patch [bz#670539]
- kvm-block-Allow-bdrv_flush-to-return-errors.patch [bz#670539]
- kvm-ide-Handle-immediate-bdrv_aio_flush-failure.patch [bz#670539]
- kvm-virtio-blk-Handle-immediate-flush-failure-properly.patch [bz#670539]
- kvm-vhost-error-code.patch [bz#633394]
- kvm-vhost-fix-up-irqfd-support.patch [bz#633394]
- kvm-virtio-pci-mask-notifier-error-handling-fixups.patch [bz#633394]
- kvm-test-for-ioeventfd-support-on-old-kernels.patch [bz#633394]
- kvm-virtio-pci-Rename-bugs-field-to-flags.patch [bz#633394]
- kvm-virtio-move-vmstate-change-tracking-to-core.patch [bz#633394]
- kvm-virtio-pci-Use-ioeventfd-for-virtqueue-notify.patch [bz#633394]
- kvm-ioeventfd-error-handling-cleanup.patch [bz#633394]
- kvm-remove-redhat-disable-THP.patch [bz#635418]
- kvm-PATCH-RHEL6.1-qemu-kvm-acpi_piix4-qdevfy.patch [bz#498774]
- kvm-PATCH-RHEL6.1-qemu-kvm-pci-allow-devices-being-tagge.patch [bz#498774]
- kvm-PATCH-RHEL6.1-qemu-kvm-piix-tag-as-not-hotpluggable.patch [bz#498774]
- kvm-PATCH-RHEL6.1-qemu-kvm-vga-tag-as-not-hotplugable-v3.patch [bz#498774]
- kvm-PATCH-RHEL6.1-qemu-kvm-qxl-tag-as-not-hotpluggable.patch [bz#498774]
- kvm-PATCH-RHEL6.1-qemu-kvm-acpi_piix4-expose-no_hotplug-.patch [bz#498774]
- kvm-char-Split-out-tcp-socket-close-code-in-a-separate-f.patch [bz#621484]
- kvm-char-mark-socket-closed-if-write-fails-with-EPIPE.patch [bz#621484]
- Resolves: bz#498774
  (QEMU: Too many devices are available for unplug in Windows XP (and we don't support that))
- Resolves: bz#621484
  (Broken pipe when working with unix socket chardev)
- Resolves: bz#625333
  (qemu treatment of -nodefconfig and -readconfig problematic for debug)
- Resolves: bz#633394
  ([6.1 FEAT] virtio-blk ioeventfd support)
- Resolves: bz#635418
  (Allow enable/disable ksm per VM)
- Resolves: bz#670539
  (Block devices don't implement correct flush error handling)
- Related: bz#635418
  (Allow enable/disable ksm per VM)

* Tue Feb 01 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.134.el6
- kvm-switch-stdvga-to-pci-vgabios.patch [bz#638468]
- kvm-switch-vmware_vga-to-pci-vgabios.patch [bz#638468]
- kvm-add-rhel6.1.0-machine-type.patch [bz#638468]
- kvm-vgabios-update-handle-compatibility-with-older-qemu-.patch [bz#638468]
- kvm-qemu-io-Fix-error-messages.patch [bz#672187]
- kvm-wdt_i6300esb-register-a-reset-function.patch [bz#637180]
- kvm-Watchdog-disable-watchdog-timer-when-hard-rebooting-.patch [bz#637180]
- kvm-usb-linux-increase-buffer-for-USB-control-requests.patch [bz#672720]
- kvm-device-assignment-Cap-number-of-devices-we-can-have-.patch [bz#670787]
- kvm-clear-vapic-after-reset.patch [bz#669268]
- kvm-add-support-for-protocol-driver-create_options.patch [bz#637701]
- kvm-qemu-img-avoid-calling-exit-1-to-release-resources-p.patch [bz#637701]
- kvm-Use-qemu_mallocz-instead-of-calloc-in-img_convert.patch [bz#637701]
- kvm-img_convert-Only-try-to-free-bs-entries-if-bs-is-val.patch [bz#637701]
- kvm-Consolidate-printing-of-block-driver-options.patch [bz#637701]
- kvm-Fix-formatting-and-missing-braces-in-qemu-img.c.patch [bz#637701]
- kvm-Fail-if-detecting-an-unknown-option.patch [bz#637701]
- kvm-Make-error-handling-more-consistent-in-img_create-an.patch [bz#637701]
- kvm-qemu-img-Deprecate-obsolete-6-and-e-options.patch [bz#637701]
- kvm-qemu-img-Free-option-parameter-lists-in-img_create.patch [bz#637701]
- kvm-qemu-img-Fail-creation-if-backing-format-is-invalid.patch [bz#637701]
- kvm-Introduce-strtosz-library-function-to-convert-a-stri.patch [bz#637701]
- kvm-Introduce-strtosz_suffix.patch [bz#637701]
- kvm-qemu-img.c-Clean-up-handling-of-image-size-in-img_cr.patch [bz#637701]
- kvm-qemu-img.c-Re-factor-img_create.patch [bz#637701]
- kvm-Introduce-do_snapshot_blkdev-and-monitor-command-to-.patch [bz#637701]
- kvm-Prevent-creating-an-image-with-the-same-filename-as-.patch [bz#637701]
- kvm-qemu-option-Fix-uninitialized-value-in-append_option.patch [bz#637701]
- kvm-bdrv_img_create-use-proper-errno-return-values.patch [bz#637701]
- kvm-block-Use-backing-format-driver-during-image-creatio.patch [bz#637701]
- kvm-Make-strtosz-return-int64_t-instead-of-ssize_t.patch [bz#637701]
- kvm-strtosz-use-unsigned-char-and-switch-to-qemu_isspace.patch [bz#637701]
- kvm-strtosz-use-qemu_toupper-to-simplify-switch-statemen.patch [bz#637701]
- kvm-strtosz-Fix-name-confusion-in-use-of-modf.patch [bz#637701]
- kvm-strtosz-Use-suffix-macros-in-switch-statement.patch [bz#637701]
- kvm-do_snapshot_blkdev-error-on-missing-snapshot_file-ar.patch [bz#637701]
- kvm-pci-memory-leak-of-PCIDevice-rom_file.patch [bz#672229]
- Resolves: bz#637180
  (watchdog timer isn't reset when qemu resets)
- Resolves: bz#637701
  (RFE - support live snapshot of a subset of disks without RAM)
- Resolves: bz#638468
  ([qemu-kvm] bochs vga lfb @ 0xe0000000 causes trouble for hot-plug)
- Resolves: bz#669268
  (WinXP hang when reboot after setup copies files to the installation folders)
- Resolves: bz#670787
  (Hot plug the 14st VF to guest causes guest shut down)
- Resolves: bz#672187
  (Improper responsive message when shrinking qcow2 image)
- Resolves: bz#672229
  (romfile memory leak)
- Resolves: bz#672720
  (getting 'ctrl buffer too small' error on USB passthrough)

* Fri Jan 28 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.133.el6
- kvm-spice-rip-out-all-the-old-non-upstream-spice-bits.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-Use-display-types-for-local-display-only.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-add-pflib-PixelFormat-conversion-library.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-Add-support-for-generic-notifier-lists.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-Rewrite-mouse-handlers-to-use-QTAILQ-and-to-have-an-.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-Add-kbd_mouse_has_absolute.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-Add-notifier-for-mouse-mode-changes.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-sdl-use-mouse-mode-notifier.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-input-make-vnc-use-mouse-mode-notifiers.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-vnc-make-sure-to-send-pointer-type-change-event-on-S.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-vmmouse-adapt-to-mouse-handler-changes.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-wacom-tablet-activate-event-handlers.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-cursor-add-cursor-functions.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-use-new-cursor-struct-functions-for-vmware-vga-and-s.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-add-spice-into-the-configure-file-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-core-bits-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-keyboard-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-mouse-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-simple-display-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-tablet-support.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-tls-support-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-make-compression-configurable.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-config-options-for-channel-security.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-config-options-for-the-listening-address.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-misc-config-options.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-audio.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-add-copyright-to-spiceaudio.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-core-fix-watching-for-write-events.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-core-fix-warning-when-building-with-spice-0.6..patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-display-replace-private-lock-with-qemu-mutex.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-qxl-device-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-connection-events.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-spice-add-qmp-query-spice-and-hmp-info-spice-command.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-Revert-vnc-support-password-expire.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-vnc-auth-reject-cleanup.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-vnc-support-password-expire-again.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-vnc-spice-add-set_passwd-monitor-command.patch [bz#642131 bz#634153 bz#615947 bz#632458 bz#631832 bz#647865]
- kvm-qdev-Track-runtime-machine-modifications.patch [bz#653591]
- kvm-rtl8139-Use-subsection-to-restrict-migration-after-h.patch [bz#653591]
- kvm-add-migration-state-change-notifiers.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-spice-vnc-client-migration.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-vnc-spice-fix-never-and-now-expire_time.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-spice-qxl-zap-spice-0.4-migration-compatibility-bits.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-spice-add-chardev-v4.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-qxl-locking-fix.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-spice-qxl-locking-fix-for-qemu-kvm.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-spice-qmp-events-restore-rhel6.0-compatibility.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- kvm-spice-monitor-commands-restore-rhel6.0-compatibility.patch [bz#615947 bz#631832 bz#632458 bz#634153 bz#642131 bz#647865]
- Resolves: bz#615947
  (RFE QMP: support of query spice for guest)
- Resolves: bz#631832
  (manpage is missing spice options)
- Resolves: bz#632458
  (Guest may core dump when booting with spice and qxl.)
- Resolves: bz#634153
  (coredumped when enable qxl without spice)
- Resolves: bz#642131
  (qemu-kvm aborts of 'qemu_spice_display_create_update: unhandled depth: 0 bits')
- Resolves: bz#647865
  (support 2560x1440 in qxl)
- Resolves: bz#653591
  ([RHEL6 Snap13]: Hot-unplugging issue noticed with rtl8139nic after migration of KVM guest.)

* Tue Jan 25 2011 Luiz Capitulino <lcapitulino@redhat.com> - qemu-kvm-0.12.1.2-2.132.el6
- kvm-BZ-636494-cpu-check-does-not-correctly-enforce-CPUID.patch [bz#636494]
- kvm-QDict-Introduce-qdict_get_qdict.patch [bz#647447]
- kvm-monitor-QMP-Drop-info-hpet-query-hpet.patch [bz#647447]
- kvm-QMP-Teach-basic-capability-negotiation-to-python-exa.patch [bz#647447]
- kvm-QMP-Fix-python-helper-wrt-long-return-strings.patch [bz#647447]
- kvm-QMP-update-query-version-documentation.patch [bz#647447]
- kvm-Revert-QMP-Remove-leading-whitespace-in-package.patch [bz#647447]
- kvm-QMP-monitor-update-do_info_version-to-output-broken-.patch [bz#647447]
- kvm-QMP-Remove-leading-whitespace-in-package-again.patch [bz#647447]
- kvm-QMP-doc-Add-Stability-Considerations-section.patch [bz#647447]
- kvm-QMP-Update-README-file.patch [bz#647447]
- kvm-QMP-Revamp-the-Python-class-example.patch [bz#647447]
- kvm-QMP-Revamp-the-qmp-shell-script.patch [bz#647447]
- kvm-QMP-Drop-vm-info-example-script.patch [bz#647447]
- kvm-qemu-char-Introduce-Memory-driver.patch [bz#647447]
- kvm-QMP-Introduce-Human-Monitor-passthrough-command.patch [bz#647447]
- kvm-QMP-qmp-shell-Introduce-HMP-mode.patch [bz#647447]
- kvm-PCI-Export-pci_map_option_rom.patch [bz#667188]
- kvm-device-assignment-Allow-PCI-to-manage-the-option-ROM.patch [bz#667188]
- kvm-virtio-serial-bus-bump-up-control-vq-size-to-32.patch [bz#656198]
- kvm-Move-stdbool.h.patch [bz#635954]
- kvm-savevm-Fix-no_migrate.patch [bz#635954]
- kvm-device-assignment-Properly-terminate-vmsd.fields.patch [bz#635954]
- Resolves: bz#635954
  (RFE: Assigned device should block migration)
- Resolves: bz#636494
  (-cpu check  does not correctly enforce CPUID items)
- Resolves: bz#647447
  (QMP:  provide a hmp_passthrough command to allow execution of non-converted commands)
- Resolves: bz#656198
  (Can only see 16 virtio ports while assigned 30 virtio serial ports on commandLine)
- Resolves: bz#667188
  (device-assignment leaks option ROM memory)

* Mon Jan 24 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.131.el6
- fix spec file to require systemtap, or configure won't enable the systemtap
  tapset
- Resolves: bz#632722
  ([6.1 FEAT] QEMU static tracing framework)

* Fri Jan 14 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.130.el6
- kvm-Bug-632257-Duplicate-CPU-fea.tures-in-cpu-x86_64.con.patch [bz#632257]
- kvm-BZ-647308-Support-Westmere-as-a-CPU-model-or-include.patch [bz#647308]
- kvm-trace-Add-trace-events-file-for-declaring-trace-even.patch [bz#632722]
- kvm-trace-Support-disabled-events-in-trace-events.patch [bz#632722]
- kvm-trace-Add-user-documentation.patch [bz#632722]
- kvm-trace-Trace-qemu_malloc-and-qemu_vmalloc.patch [bz#632722]
- kvm-trace-Trace-virtio-blk-multiwrite-and-paio_submit.patch [bz#632722]
- kvm-trace-Trace-virtqueue-operations.patch [bz#632722]
- kvm-trace-Trace-port-IO.patch [bz#632722]
- kvm-trace-Trace-entry-point-of-balloon-request-handler.patch [bz#632722]
- kvm-trace-fix-a-typo.patch [bz#632722]
- kvm-trace-fix-a-regex-portability-problem.patch [bz#632722]
- kvm-trace-avoid-unnecessary-recompilation-if-nothing-cha.patch [bz#632722]
- kvm-trace-Use-portable-format-strings.patch [bz#632722]
- kvm-trace-Don-t-strip-lines-containing-arbitrarily.patch [bz#632722]
- kvm-trace-Trace-bdrv_aio_-readv-writev.patch [bz#632722]
- kvm-trace-remove-timestamp-files-when-cleaning-up.patch [bz#632722]
- kvm-trace-Format-strings-must-begin-end-with-double-quot.patch [bz#632722]
- kvm-apic-convert-debug-printf-statements-to-tracepoints.patch [bz#632722]
- kvm-Add-a-DTrace-tracing-backend-targetted-for-SystemTAP.patch [bz#632722]
- kvm-Add-support-for-generating-a-systemtap-tapset-static.patch [bz#632722]
- kvm-trace-Trace-vm_start-vm_stop.patch [bz#632722]
- spec file changes to enable trace support [bz#632722]
- Resolves: bz#632257
  (Duplicate CPU fea.tures in cpu-x86_64.conf)
- Resolves: bz#632722
  ([6.1 FEAT] QEMU static tracing framework)
- Resolves: bz#647308
  (Support Westmere as a CPU model or included within existing models..)

* Mon Jan 10 2011 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.129.el6
- kvm-let-management-choose-whether-transparent-huge-pages.patch [bz#628308]
- kvm-tap-generalize-code-for-different-vnet-header-len.patch [bz#616659]
- kvm-tap-add-APIs-for-vnet-header-length.patch [bz#616659]
- kvm-vhost_net-mergeable-buffers-support.patch [bz#616659]
- kvm-vhost-Fix-address-calculation-in-vhost_dev_sync_regi.patch [bz#623552]
- Resolves: bz#616659
  (mrg buffers: migration breaks between systems with/without vhost)
- Resolves: bz#623552
  (SCP image fails from host to guest with vhost on when do migration)
- Resolves: bz#628308
  ([RFE] let management choose whether transparent huge pages are used)

* Mon Dec 20 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.128.el6
- kvm-virtio-invoke-set_status-callback-on-reset.patch [bz#623735]
- kvm-virtio-net-unify-vhost-net-start-stop.patch [bz#623735]
- kvm-tap-clear-vhost_net-backend-on-cleanup.patch [bz#623735]
- kvm-tap-make-set_offload-a-nop-after-netdev-cleanup.patch [bz#623735]
- Resolves: bz#623735
  (hot unplug of vhost net virtio NIC causes qemu segfault)

* Mon Dec 20 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.127.el6
- kvm-pci-import-Linux-pci_regs.h.patch [bz#624790]
- kvm-pci-s-PCI_SUBVENDOR_ID-PCI_SUBSYSTEM_VENDOR_ID-g.patch [bz#624790]
- kvm-pci-use-pci_regs.h.patch [bz#624790]
- kvm-pci-add-API-to-add-capability-at-a-known-offset.patch [bz#624790]
- kvm-pci-consolidate-pci_add_capability_at_offset-into-pc.patch [bz#624790]
- kvm-pci-pci_default_cap_write_config-ignores-wmask.patch [bz#624790]
- kvm-pci-Remove-pci_enable_capability_support.patch [bz#624790]
- kvm-device-assignment-Use-PCI-capabilities-support.patch [bz#624790]
- kvm-pci-Replace-used-bitmap-with-config-byte-map.patch [bz#624790]
- kvm-pci-Remove-cap.length-cap.start-cap.supported.patch [bz#624790]
- kvm-device-assignment-Move-PCI-capabilities-to-match-phy.patch [bz#624790]
- kvm-pci-Remove-capability-specific-handlers.patch [bz#624790]
- kvm-device-assignment-Make-use-of-config_map.patch [bz#624790]
- kvm-device-assignment-Fix-off-by-one-in-header-check.patch [bz#624790]
- kvm-pci-Remove-PCI_CAPABILITY_CONFIG_.patch [bz#624790]
- kvm-pci-Error-on-PCI-capability-collisions.patch [bz#624790]
- kvm-device-assignment-Error-checking-when-adding-capabil.patch [bz#624790]
- kvm-device-assignment-pass-through-and-stub-more-PCI-cap.patch [bz#624790]
- Resolves: bz#624790
  (pass through fails with KVM using Neterion Inc's X3100 Series 10GbE PCIe I/O Virtualized Server Adapter in Multifunction mode.)

* Fri Dec 17 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.126.el6
- kvm-Fix-build-problem-with-recent-compilers.patch [bz#662633]
- kvm-vhost-fix-infinite-loop-on-error-path.patch [bz#628634]
- Resolves: bz#628634
  (vhost_net: untested error handling in vhost_net_start)
- Resolves: bz#662633
  (Fix build problem with recent compilers)

* Fri Dec 10 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.125.el6
- kvm-New-option-fake-machine.patch [bz#658288]
- spec file code for --enable-fake-machine [bz#658288]
- Resolves: bz#658288
  (Include (disabled by default) -fake-machine patch on qemu-kvm RPM spec)

* Fri Dec 10 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.124.el6
- kvm-Fix-compilation-error-missing-include-statement.patch [bz#608548]
- kvm-use-qemu_blockalign-consistently.patch [bz#608548]
- kvm-raw-posix-handle-512-byte-alignment-correctly.patch [bz#608548]
- kvm-virtio-blk-propagate-the-required-alignment.patch [bz#608548]
- kvm-scsi-disk-propagate-the-required-alignment.patch [bz#608548]
- kvm-ide-propagate-the-required-alignment.patch [bz#608548]
- kvm-Support-marking-a-device-as-non-migratable.patch [bz#635954]
- kvm-device-assignment-Register-as-un-migratable.patch [bz#635954]
- Resolves: bz#608548
  (QEMU doesn't respect hardware sector size of underlying block device when doing O_DIRECT)
- Resolves: bz#635954
  (RFE: Assigned device should block migration)

* Thu Dec 09 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.123.el6
- kvm-qcow2-Implement-bdrv_truncate-for-growing-images.patch [bz#613893]
- kvm-qemu-img-Add-resize-command-to-grow-shrink-disk-imag.patch [bz#613893]
- kvm-qemu-img-Fix-copy-paste-bug-in-documentation.patch [bz#613893]
- Resolves: bz#613893
  ([RFE] qemu-io enable truncate function for qcow2.)

* Wed Dec 08 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.122.el6
- kvm-cleanup-block-driver-option-handling-in-vl.c.patch [bz#653536]
- kvm-Add-cache-unsafe-parameter-to-drive.patch [bz#653536]
- kvm-move-unsafe-to-end-of-caching-modes-in-help.patch [bz#653536]
- kvm-qemu-img-Eliminate-bdrv_new_open-code-duplication.patch [bz#653536]
- kvm-qemu-img-Fix-BRDV_O_FLAGS-typo.patch [bz#653536]
- kvm-qemu-img-convert-Use-cache-unsafe-for-output-image.patch [bz#653536]
- kvm-block-Fix-virtual-media-change-for-if-none.patch [bz#625319]
- kvm-Check-for-invalid-initrd-file.patch [bz#624721]
- kvm-qcow-qcow2-implement-bdrv_aio_flush.patch [bz#653972]
- kvm-block-Remove-unused-s-hd-in-various-drivers.patch [bz#653972]
- kvm-qcow2-Remove-unnecessary-flush-after-L2-write.patch [bz#653972]
- kvm-qcow2-Move-sync-out-of-write_refcount_block_entries.patch [bz#653972]
- kvm-qcow2-Move-sync-out-of-update_refcount.patch [bz#653972]
- kvm-qcow2-Move-sync-out-of-qcow2_alloc_clusters.patch [bz#653972]
- kvm-qcow2-Get-rid-of-additional-sync-on-COW.patch [bz#653972]
- kvm-cutils-qemu_iovec_copy-and-qemu_iovec_memset.patch [bz#653972]
- kvm-qcow2-Avoid-bounce-buffers-for-AIO-read-requests.patch [bz#653972]
- kvm-qcow2-Avoid-bounce-buffers-for-AIO-write-requests.patch [bz#653972]
- kvm-kill-empty-index-on-qemu-doc.texi.patch [bz#604992]
- kvm-add-VMSTATE_BOOL.patch [bz#645342]
- kvm-Add-Intel-HD-Audio-support-to-qemu.patch [bz#645342]
- Resolves: bz#604992
  (index is empty in qemu-doc.html)
- Resolves: bz#624721
  ([qemu] [rhel6] bad error handling when qemu has no 'read' permissions over {kernel,initrd} files [pass boot options])
- Resolves: bz#625319
  (Failed to update the media in floppy device)
- Resolves: bz#645342
  (Implement QEMU driver for modern sound device like Intel HDA)
- Resolves: bz#653536
  (qemu-img convert poor performance)
- Resolves: bz#653972
  (qcow2: Backport performance related patches)

* Thu Dec 02 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.121.el6
- kvm-monitor-Rename-argument-type-b-to-f.patch [bz#625681]
- kvm-monitor-New-argument-type-b-bool.patch [bz#625681]
- kvm-monitor-Use-argument-type-b-for-set_link.patch [bz#625681]
- kvm-monitor-Convert-do_set_link-to-QObject-QError.patch [bz#625681]
- Resolves: bz#625681
  (RFE QMP: should have command to disconnect and connect network card for whql testing)

* Thu Nov 18 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.120.el6
- kvm-Fix-snapshot-deleting-images-on-disk-change.patch [bz#653582]
- Resolves: bz#653582
  (Changing media with -snapshot deletes image file)

* Tue Nov 16 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.119.el6
- kvm-bz-603413-e1000-secrc-support.patch [bz#603413]
- kvm-net-properly-handle-illegal-fd-vhostfd-from-command-.patch [bz#581750]
- kvm-Enable-non-page-boundary-BAR-device-assignment.patch [bz#647307]
- kvm-Fix-build-failure-with-DEVICE_ASSIGNMENT_DEBUG.patch [bz#647307]
- kvm-slow_map-minor-improvements-to-ROM-BAR-handling.patch [bz#647307]
- kvm-device-assignment-Always-use-slow-mapping-for-PCI-op.patch [bz#647307]
- kvm-e1000-Fix-TCP-checksum-overflow-with-TSO.patch [bz#648333]
- kvm-device-assignment-Fix-slow-option-ROM-mapping.patch [bz#647307]
- Resolves: bz#581750
  (Vhost: Segfault when assigning a none vhostfd)
- Resolves: bz#603413
  (RHEL3.9 guest netdump hung with e1000)
- Resolves: bz#647307
  (Support slow mapping of PCI Bars)
- Resolves: bz#648333
  (TCP checksum overflows in qemu's e1000 emulation code when TSO is enabled in guest OS)

* Tue Nov 09 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.118.el6
- kvm-net-delay-freeing-peer-host-device.patch [bz#634661]
- kvm-QMP-Improve-debuggability-of-the-BLOCK_IO_ERROR-even.patch [bz#624607]
- Resolves: bz#624607
  ([qemu] [rhel6] guest installation stop (pause) on 'eother' event over COW disks (thin-provisioning))
- Resolves: bz#634661
  ([RHEL6 Snap13]: Hot-unplugging of virtio nic issue in Windows2008 KVM guest.)

* Mon Oct 25 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.117.el6
- kvm-savevm-Really-verify-if-a-drive-supports-snapshots.patch [bz#599307]
- kvm-drop-boot-on-from-help-string.patch [bz#643681]
- kvm-Fix-parameters-of-prctl.patch [bz#585910]
- kvm-Ignore-SRAO-MCE-if-another-MCE-is-being-processed.patch [bz#585910]
- kvm-Add-RAM-physical-addr-mapping-in-MCE-simulation.patch [bz#585910]
- kvm-Add-savevm-loadvm-support-for-MCE.patch [bz#585910]
- kvm-Fix-SRAO-SRAR-MCE-injecting-on-guest-without-MCG_SER.patch [bz#585910]
- Resolves: bz#585910
  ([Intel 6.1 Bug] SRAO MCE in guest kills QEMU-KVM (qemu-kvm component))
- Resolves: bz#599307
  (info snapshot return "bdrv_snapshot_list: error -95")
- Resolves: bz#643681
  (Do not advertise boot=on capability to libvirt)

* Thu Oct 14 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.116.el6
- ksmtuned: committed_memory of 0 qemus [bz#609016]
- kvm-Fix-underflow-error-in-device-assignment-size-check.patch [bz#632054]
- kvm-check-for-close-errors-on-qcow2_create.patch [bz#641127]
- Resolves: bz#609016
  (incorrect committed memory on idle host)
- Resolves: bz#632054
  ([Intel 6.0 Virt] guest bootup fail with intel 82574L NIC assigned)
- Resolves: bz#641127
  (qemu-img ignores close() errors)

* Fri Oct 08 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.115.el6
- kvm-spice-qxl-update-modes-ptr-in-post_load.patch [bz#631522]
- kvm-spice-qxl-make-draw_area-and-vgafb-share-memory.patch [bz#631522]
- Give a nicer message if retune is called while ksmtuned is off [bz#637976]
- Resolves: bz#631522
  (spice: prepare qxl for 6.1 update.)
- Resolves: bz#637976
  (ksmtuned: give a nicer message if retune is called while ksmtuned is off)

* Thu Oct 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.114.el6
- fix ksmd.init "status" [bz#570467]
- kvm-virtio-net-Make-tx_timer-timeout-configurable.patch [bz#624767]
- kvm-virtio-net-Limit-number-of-packets-sent-per-TX-flush.patch [bz#624767]
- kvm-virtio-net-Rename-tx_timer_active-to-tx_waiting.patch [bz#624767]
- kvm-virtio-net-Introduce-a-new-bottom-half-packet-TX.patch [bz#624767]
- kvm-spice-qxl-enable-some-highres-modes.patch [bz#482427]
- kvm-add-MADV_DONTFORK-to-guest-physical-memory-v2.patch [bz#633699]
- kvm-virtio-serial-Check-if-virtio-queue-is-ready-before-.patch [bz#596610]
- kvm-virtio-serial-Assert-for-virtio-queue-ready-before-v.patch [bz#596610]
- kvm-virtio-serial-Check-if-more-max_ports-specified-than.patch [bz#616703]
- kvm-virtio-serial-Cleanup-on-device-hot-unplug.patch [bz#624396]
- kvm-block-Fix-image-re-open-in-bdrv_commit.patch [bz#635354]
- kvm-qxl-clear-dirty-rectangle-on-resize.patch [bz#617119]
- kvm-VGA-Don-t-register-deprecated-VBE-range.patch [bz#625948]
- kvm-BZ-619168-qemu-should-more-clearly-indicate-internal.patch [bz#619168]
- kvm-fix-and-on-russian-keymap.patch [bz#639437]
- Resolves: bz#482427
  (support high resolutions)
- Resolves: bz#570467
  ([RHEL 6] Initscripts improvement for ksm and ksmtuned)
- Resolves: bz#596610
  ("Guest moved used index from 0 to 61440" if remove virtio serial device before virtserialport)
- Resolves: bz#616703
  (qemu-kvm core dump with virtio-serial-pci max-port greater than 31)
- Resolves: bz#617119
  (Qemu becomes unresponsive during unattended_installation)
- Resolves: bz#619168
  (qemu should more clearly indicate internal detection of this host out-of-memory condition at startup..)
- Resolves: bz#624396
  (migration failed after hot-unplug virtserialport - Unknown savevm section or instance '0000:00:07.0/virtio-console' 0)
- Resolves: bz#624767
  (Replace virtio-net TX timer mitigation with bottom half handler)
- Resolves: bz#625948
  (qemu exits when hot adding rtl8139 nic to win2k8 guest)
- Resolves: bz#633699
  (Cannot hot-plug nic in windows VM when the vmem is larger)
- Resolves: bz#635354
  (Can not commit copy-on-write image's data to raw backing-image)
- Resolves: bz#639437
  (Incorrect russian vnc keymap)

* Tue Aug 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.113.el6
- kvm-disable-guest-provided-stats-on-info-ballon-monitor-.patch [bz#623903]
- Resolves: bz#623903
  (query-balloon commmand didn't return on pasued guest cause virt-manger hang)

* Wed Aug 18 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.112.el6
- kvm-qemu-img-rebase-Open-new-backing-file-read-only.patch [bz#624666]
- Resolves: bz#624666
  (qemu-img re-base broken on RHEL6)

* Tue Aug 17 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.111.el6
- blacklist vhost_net [bz#624769]
- Resolves: bz#624769
  (Blacklist vhost_net)

* Mon Aug 16 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.110.el6
- kvm-vhost-Fix-size-of-dirty-log-sync-on-resize.patch [bz#622356]
- Resolves: bz#622356
  (Live migration failed during reboot due to vhost)

* Mon Aug 09 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.109.el6
- kvm-qdev-Reset-hotplugged-devices.patch [bz#607611]
- kvm-Block-I-O-signals-in-audio-helper-threads.patch [bz#621161]
- Resolves: bz#607611
  (pci hotplug of e1000, rtl8139 nic device fails for all guests.)
- Resolves: bz#621161
  (qemu-kvm crashes with I/O Possible message)

* Wed Aug 04 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.108.el6
- kvm-Fix-migration-with-spice-enabled.patch [bz#618168]
- kvm-virtio-Factor-virtqueue_map_sg-out.patch [bz#607244]
- kvm-virtio-blk-Fix-migration-of-queued-requests.patch [bz#607244]
- Resolves: bz#607244
  (virtio-blk doesn't load list of pending requests correctly)
- Resolves: bz#618168
  (Qemu-kvm in the src host core dump when do migration by using spice)

* Tue Aug 03 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.107.el6
- kvm-Correct-cpuid-flags-and-model-fields-V2.patch [bz#613892 bz#618332]
- Resolves: bz#613892
  ([SR-IOV]VF device can not start on 32bit Windows2008 SP2)
- Resolves: bz#618332
  (CPUID_EXT_POPCNT enabled in qemu64 and qemu32 built-in models.)

* Fri Jul 30 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.106.el6
- kvm-device-assignment-Leave-option-ROM-space-RW-KVM-does.patch [bz#618788]
- kvm-block-Fix-bdrv_has_zero_init.patch [bz#616890]
- kvm-Fix-segfault-in-mmio-subpage-handling-code.patch [bz#619414]
- kvm-Migration-reopen-block-devices-files.patch [bz#618601]
- Resolves: bz#616890
  ("qemu-img convert" fails on block device)
- Resolves: bz#618601
  (We need to reopen images after migration)
- Resolves: bz#618788
  (device-assignment hangs with kvm_run: Bad address)
- Resolves: bz#619414
  (CVE-2010-2784 qemu: insufficient constraints checking in exec.c:subpage_register() [rhel-6.0])

* Wed Jul 28 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.105.el6
- kvm-device-assignment-Use-PCI-I-O-port-sysfs-resource-fi.patch [bz#615214]
- kvm-block-Change-bdrv_eject-not-to-drop-the-image.patch [bz#558256]
- Resolves: bz#558256
  (rhel6 disk not detected first time in install)
- Resolves: bz#615214
  ([VT-d] Booting RHEL6 guest with Intel 82541PI NIC assigned by libvirt cause qemu crash)

* Tue Jul 27 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.104.el6
- kvm-vhost_dev_unassign_memory-don-t-assert-if-removing-f.patch [bz#617085]
- Resolves: bz#617085
  (core dumped when add netdev to VM with vhost on)

* Tue Jul 27 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.103.el6
- kvm-migration-Accept-cont-only-after-successful-incoming.patch [bz#581555]
- Resolves: bz#581555
  (race between qemu monitor "cont" and incoming migration can cause failed restore/migration)

* Tue Jul 27 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.102.el6
- kvm-spice-Rename-conflicting-ramblock.patch [bz#617463]
- kvm-block-default-to-0-minimal-optimal-I-O-size.patch [bz#617271]
- Resolves: bz#617271
  (RHEL6 qemu-kvm guest gets partitioned at sector 63)
- Resolves: bz#617463
  (Coredump occorred when enable qxl)

* Tue Jul 27 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.101.el6
- kvm-virtio-net-correct-packet-length-checks.patch [bz#591494]
- kvm-avoid-canceling-ide-dma-rediff.patch [bz#617414]
- Resolves: bz#591494
  (Virtio: Transfer file caused guest in same vlan abnormally quit)
- Resolves: bz#617414
  (avoid canceling in flight ide dma)

* Mon Jul 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.100.el6
- kvm-Disable-SCSI.patch [bz#617534]
- kvm-spice-don-t-force-fullscreen-redraw-on-display-resiz.patch [bz#612074]
- kvm-KVM_GET_SUPPORTED_CPUID-doesn-t-return-all-host-cpui.patch [bz#616188]
- kvm-Do-not-try-loading-option-ROM-for-hotplug-PCI-device.patch [bz#612696]
- Resolves: bz#612074
  (core dumped while live migration with spice)
- Resolves: bz#612696
  (virsh attach-device crash kvm guest.)
- Resolves: bz#616188
  (KVM_GET_SUPPORTED_CPUID doesn't return all host cpuid flags..)
- Resolves: bz#617534
  (Disable SCSI and usb-storage)

* Thu Jul 22 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.99.el6
- kvm-Documentation-Add-a-warning-message-to-qemu-kvm-help.patch [bz#596232]
- Resolves: bz#596232
  (Update docs to exclude unsupported options)

* Thu Jul 22 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.98.el6
- kvm-ram_blocks-Convert-to-a-QLIST.patch [bz#596328]
- kvm-Remove-uses-of-ram.last_offset-aka-last_ram_offset.patch [bz#596328]
- kvm-pc-Allocate-all-ram-in-a-single-qemu_ram_alloc.patch [bz#596328]
- kvm-qdev-Add-a-get_dev_path-function-to-BusInfo.patch [bz#596328]
- kvm-pci-Implement-BusInfo.get_dev_path.patch [bz#596328]
- kvm-savevm-Add-DeviceState-param.patch [bz#596328]
- kvm-savevm-Make-use-of-DeviceState.patch [bz#596328]
- kvm-eepro100-Add-a-dev-field-to-eeprom-new-free-function.patch [bz#596328]
- kvm-virtio-net-Incorporate-a-DeviceState-pointer-and-let.patch [bz#596328]
- kvm-qemu_ram_alloc-Add-DeviceState-and-name-parameters.patch [bz#596328]
- kvm-ramblocks-Make-use-of-DeviceState-pointer-and-BusInf.patch [bz#596328]
- kvm-savevm-Migrate-RAM-based-on-name-offset.patch [bz#596328]
- kvm-savevm-Use-RAM-blocks-for-basis-of-migration.patch [bz#596328]
- kvm-savevm-Create-a-new-continue-flag-to-avoid-resending.patch [bz#596328]
- kvm-qemu_ram_free-Implement-it.patch [bz#596328]
- kvm-pci-Free-the-space-allocated-for-the-option-rom-on-r.patch [bz#596328]
- kvm-ramblocks-No-more-being-lazy-about-duplicate-names.patch [bz#596328]
- kvm-savevm-Reset-last-block-info-at-beginning-of-each-sa.patch [bz#616525]
- kvm-block-Change-bdrv_commit-to-handle-multiple-sectors-.patch [bz#615152]
- kvm-Revert-virtio-Enable-the-PUBLISH_USED-feature-by-def.patch [bz#616501]
- kvm-Revert-vhost-net-check-PUBLISH_USED-in-backend.patch [bz#616501]
- kvm-Revert-virtio-utilize-PUBLISH_USED_IDX-feature.patch [bz#616501]
- kvm-savevm-Fix-memory-leak-of-compat-struct.patch [bz#596328]
- kvm-virtio-blk-Create-exit-function-to-unregister-savevm.patch [bz#580010]
- Resolves: bz#580010
  (migration failed after pci_add and pci_del a virtio storage device)
- Resolves: bz#596328
  ([RHEL6 Beta1] : KVM guest remote migration fails with pci device hotplug.)
- Resolves: bz#615152
  (rhel 6 performance worse than rhel5.6 when committing 1G  changes recorded in  snapshot in its base image.)
- Resolves: bz#616501
  (publish used ABI incompatible with future guests)
- Resolves: bz#616525
  (savevm needs to reset block info on each new save)

* Tue Jul 20 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.97.el6
- kvm-block-Fix-early-failure-in-multiwrite.patch [bz#602209]
- kvm-block-Handle-multiwrite-errors-only-when-all-request.patch [bz#602209]
- kvm-migration-respect-exit-status-with-exec.patch [bz#584372]
- kvm-set-proper-migration-status-on-write-error-v3.patch [bz#584372]
- kvm-Set-SMBIOS-vendor-to-QEMU-for-RHEL5-machine-types.patch [bz#614377]
- kvm-Don-t-reset-bs-is_temporary-in-bdrv_open_common.patch [bz#611797]
- kvm-Change-default-CPU-model-qemu64-to-model-6.patch [bz#614537]
- kvm-set-model-6-on-Intel-CPUs-on-cpu-x86_64.conf.patch [bz#614537]
- kvm-vhost-fix-miration-during-device-start.patch [bz#615228]
- Resolves: bz#584372
  (Fails to detect errors when using exec: based migration)
- Resolves: bz#602209
  (Core dumped during Guest installation)
- Resolves: bz#611797
  (qemu does not call unlink() on temp files in snapshot mode)
- Resolves: bz#614377
  (Windows 7 requires re-activation when migrated from RHEL5 to RHEL6)
- Resolves: bz#614537
  (Skype crashes on VM.)
- Resolves: bz#615228
  (oom in vhost_dev_start)

* Thu Jul 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.96.el6
- fix some errors in ksmd.init [bz#570467]
- fix some errors in ksmtuned.init [bz#579883]
- kvm-Add-x2apic-to-cpuid-feature-set-for-new-AMD-models.-.patch [bz#613884]
- Resolves: bz#570467
  ([RHEL 6] Initscripts improvement for ksm and ksmtuned)
- Resolves: bz#579883
  (init script doesn't stop ksmd)
- Resolves: bz#613884
  (x2apic needs to be present in all new AMD cpu models..)

* Wed Jul 14 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.95.el6
- kvm-Move-CPU-definitions-to-usr-share-.-BZ-610805.patch [bz#610805]
- kvm-QEMUFileBuffered-indicate-that-we-re-ready-when-the-.patch [bz#609261]
- kvm-device-assignment-Better-fd-tracking.patch [bz#611715]
- Resolves: bz#609261
  (Exec outgoing migration is too slow)
- Resolves: bz#610805
  (Move CPU definitions to /usr/share/...)
- Resolves: bz#611715
  (qemu-kvm gets no responsive  when do  hot-unplug pass-through device)

* Tue Jul 13 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.94.el6
- kvm-Revert-ide-save-restore-pio-atapi-cmd-transfer-field.patch [bz#612481]
- kvm-vmstate-add-subsections-code.patch [bz#612481]
- kvm-ide-fix-migration-in-the-middle-of-pio-operation.patch [bz#612481]
- kvm-ide-fix-migration-in-the-middle-of-a-bmdma-transfer.patch [bz#612481]
- kvm-Initial-documentation-for-migration-Signed-off-by-Ju.patch [bz#612481]
- kvm-Disable-non-rhel-machine-types-pc-0.12-pc-0.11-pc-0..patch [bz#607263]
- Resolves: bz#607263
  (Remove -M pc-0.12 support)
- Resolves: bz#612481
  (Enable migration subsections)

* Fri Jul 09 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.93.el6
- kvm-make-rtc-alatm-work.patch [bz#598836]
- kvm-qemu-img-check-Distinguish-different-kinds-of-errors.patch [bz#612164]
- kvm-qcow2-vdi-Change-check-to-distinguish-error-cases.patch [bz#612164]
- Resolves: bz#598836
  (RHEL 6.0 RTC Alarm unusable in vm)
- Resolves: bz#612164
  ([kvm] qemu image check returns cluster errors when using virtIO block (thinly provisioned) during e_no_space events (along with EIO errors))

* Wed Jul 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.92.el6
- build-time-only fix: fix the tarball-generation make-release script for newer git versions
  (kvm-make-release-fix-mtime-on-rhel6-beta.patch)
- Related: bz#581963 bz#582262 bz#611229

* Wed Jul 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.91.el6
- kvm-doc-Update-monitor-info-subcommands.patch [bz#582262]
- kvm-Fix-typo-in-balloon-help.patch [bz#582262]
- kvm-monitor-Reorder-info-documentation.patch [bz#582262]
- kvm-QMP-Introduce-commands-documentation.patch [bz#582262]
- kvm-QMP-Sync-documentation-with-RHEL6-only-changes.patch [bz#582262]
- kvm-Monitor-Drop-QMP-documentation-from-code.patch [bz#582262]
- kvm-hxtool-Fix-line-number-reporting-on-SQMP-EQMP-errors.patch [bz#582262]
- kvm-monitor-New-command-__com.redhat_drive_add.patch [bz#581963]
- kvm-Fix-driftfix-option.patch [bz#611229]
- Resolves: bz#581963
  (QMP: missing drive_add command in JSON mode)
- Resolves: bz#582262
  (QMP: Missing commands doc)
- Resolves: bz#611229
  (-rtc cmdline changes)

* Tue Jun 29 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.90.el6
- kvm-device-assignment-Avoid-munmapping-the-real-MSIX-are.patch [bz#572043]
- kvm-device-assignment-Cleanup-on-exit.patch [bz#572043]
- Resolves: bz#572043
  (Guest gets segfault when do multiple device hot-plug and hot-unplug)

* Tue Jun 29 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.89.el6
- kvm-device-assignment-be-more-selective-in-interrupt-dis.patch [bz#605361]
- Resolves: bz#605361
  (82576 physical function device assignment doesn't work with win7)

* Tue Jun 29 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.88.el6
- kvm-Exit-if-incoming-migration-fails.patch [bz#570174]
- kvm-Factorize-common-migration-incoming-code.patch [bz#570174]
- Resolves: bz#570174
  (Restoring a qemu guest from a saved state file using -incoming sometimes fails and hangs)

* Tue Jun 29 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.87.el6
- kvm-qxl-drop-check-for-depths-32.patch [bz#597198]
- kvm-spice-handle-16-bit-color-depth.patch [bz#597198 bz#600205]
- kvm-device-assignment-Don-t-deassign-when-the-assignment.patch [bz#597968]
- kvm-block-fix-physical_block_size-calculation.patch [bz#566785]
- kvm-Add-x2apic-to-cpuid-feature-set-for-new-Intel-models.patch [bz#601517]
- Resolves: bz#566785
  (virt block layer must not keep guest's logical_block_size fixed)
- Resolves: bz#597198
  (qxl: 16bpp vga mode is broken.)
- Resolves: bz#597968
  (Should not allow one physical NIC card to be assigned to one guest for many times)
- Resolves: bz#600205
  (Live migration cause qemu-kvm Segmentation fault (core dumped)by using "-vga std")
- Resolves: bz#601517
  (x2apic needs to be present in all new Intel cpu models..)

* Mon Jun 28 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.86.el6
- kvm-net-delete-QemuOpts-when-net_client_init-fails.patch [bz#603851]
- kvm-QMP-Fix-error-reporting-in-the-async-API.patch [bz#587382]
- kvm-QMP-Remove-leading-whitespace-in-package.patch [bz#580648]
- kvm-Add-optional-dump-of-default-config-file-paths-v2-BZ.patch [bz#601540]
- Resolves: bz#580648
  (QMP: Bad package version in greeting message)
- Resolves: bz#587382
  (QMP: balloon command may not report an error)
- Resolves: bz#601540
  (qemu requires ability to verify location of cpu model definition file..)
- Resolves: bz#603851
  (QMP: Can't reuse same 'id' when netdev_add fails)

* Mon Jun 28 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.85.el6
- kvm-Remove-usage-of-CONFIG_RED_HAT_DISABLED.patch [bz#605638]
- kvm-monitor-Remove-host_net_add-remove-for-Red-Hat-Enter.patch [bz#605638]
- kvm-monitor-Remove-usb_add-del-commands-for-Red-Hat-Ente.patch [bz#605638]
- kvm-virtio-blk-fix-the-list-operation-in-virtio_blk_load.patch [bz#607244]
- kvm-QError-Introduce-QERR_DEVICE_INIT_FAILED_2.patch [bz#596279]
- kvm-dev-assignment-Report-IRQ-assign-errors-in-QMP.patch [bz#596279]
- Resolves: bz#596279
  (QMP: does not report the real cause of PCI device assignment failure)
- Resolves: bz#605638
  (Remove unsupported monitor commands from qemu-kvm)
- Resolves: bz#607244
  (virtio-blk doesn't load list of pending requests correctly)

* Mon Jun 28 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.84.el6
- kvm-Add-KVM-paravirt-cpuid-leaf.patch [bz#606084]
- Resolves: bz#606084
  (Allow control of kvm cpuid option via -cpu flag)

* Mon Jun 28 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.83.el6
- kvm-add-some-tests-for-invalid-JSON.patch [bz#585009]
- kvm-implement-optional-lookahead-in-json-lexer.patch [bz#585009]
- kvm-remove-unnecessary-lookaheads.patch [bz#585009]
- kvm-per-machine-type-smbios-Type-1-smbios-values.patch [bz#605704]
- kvm-raw-posix-Use-pread-pwrite-instead-of-lseek-read-wri.patch [bz#607688]
- kvm-block-Cache-total_sectors-to-reduce-bdrv_getlength-c.patch [bz#607688]
- kvm-block-allow-filenames-with-colons-again-for-host-dev.patch [bz#599122]
- Resolves: bz#585009
  (QMP: input needs trailing  char)
- Resolves: bz#599122
  (Unable to launch QEMU with a guest disk filename containing a ':')
- Resolves: bz#605704
  (qemu-kvm: set per-machine-type smbios strings)
- Resolves: bz#607688
  (Excessive lseek() causes severe performance issues with vm disk images over NFS)

* Fri Jun 25 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.82.el6
- kvm-monitor-allow-device-to-be-ejected-if-no-disk-is-ins.patch [bz#581789]
- kvm-New-slots-need-dirty-tracking-enabled-when-migrating.patch [bz#596609]
- kvm-Make-netdev_del-delete-the-netdev-even-when-it-s-in-.patch [bz#596274]
- kvm-device-assignment-msi-PBA-is-long.patch [bz#605359]
- kvm-qcow2-Fix-qemu-img-check-segfault-on-corrupted-image.patch [bz#604210]
- kvm-qcow2-Don-t-try-to-check-tables-that-couldn-t-be-loa.patch [bz#604210]
- kvm-qcow2-Fix-error-handling-during-metadata-preallocati.patch [bz#604210]
- kvm-block-Add-bdrv_-p-write_sync.patch [bz#607200]
- kvm-qcow2-Use-bdrv_-p-write_sync-for-metadata-writes.patch [bz#607200]
- kvm-virtio-serial-Fix-compat-property-name.patch [bz#607263]
- kvm-rtc-Remove-TARGET_I386-from-qemu-config.c-enables-dr.patch [bz#606733]
- Resolves: bz#581789
  (Cannot eject cd-rom when configured to host cd-rom)
- Resolves: bz#596274
  (QMP: netdev_del sometimes fails claiming the device is in use)
- Resolves: bz#596609
  (Live migration failed when migration during boot)
- Resolves: bz#604210
  (Segmentation fault when check  preallocated qcow2 image on lvm.)
- Resolves: bz#605359
  (Fix MSIX regression from bz595495)
- Resolves: bz#606733
  (Unable to set the driftfix parameter)
- Resolves: bz#607200
  (qcow2 image corruption when using cache=writeback)
- Resolves: bz#607263
  (Unable to launch QEMU with -M pc-0.12 and  virtio serial)

* Thu Jun 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.81.el6
- kvm-virtio-Enable-the-PUBLISH_USED-feature-by-default-fo.patch [bz#602417]
- kvm-do-not-enter-vcpu-again-if-it-was-stopped-during-IO.patch [bz#595647]
- Resolves: bz#595647
  (Windows guest with qxl driver can't get into S3 state)
- Resolves: bz#602417
  (Enable VIRTIO_RING_F_PUBLISHED bit for all virtio devices)

* Wed Jun 23 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.80.el6
- don't package kvmtrace anymore
- Resolves: bz#605426
  (obsolete kvmtrace binary is still being packaged)

* Tue Jun 22 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.79.el6
- kvm-Make-geometry-of-IDE-drives-defined-with-device-visi.patch [bz#597147]
- Resolves: bz#597147
  (libvirt: kvm disk error after first stage install of Win2K or WinXP)

* Mon Jun 21 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.78.el6
- kvm-block-read-only-open-cdrom-as-read-only-when-using-m.patch [bz#602026]
- kvm-acpi_piix4-save-gpe-and-pci-hotplug-slot-status.patch [bz#598022]
- kvm-Don-t-check-for-bus-master-for-old-guests.patch [bz#596014]
- kvm-Make-IDE-drives-defined-with-device-visible-to-cmos_.patch [bz#597147]
- Resolves: bz#596014
  (hot add virtio-blk-pci via device_add lead to virtio network lost)
- Resolves: bz#597147
  (libvirt: kvm disk error after first stage install of Win2K or WinXP)
- Resolves: bz#598022
  (Hot-added device is not visible in guest after live-migration.)
- Resolves: bz#602026
  (Cannot change cdrom by "change device filename [format] " in (qemu) command line)

* Wed Jun 16 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.77.el6
- kvm.modules: autoload vhost-net module too [bz#596891]
- Resolves: bz#596891
  (vhost-net module should be loaded automatically)

* Wed Jun 16 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.76.el6
- kvm-fix-vnc-memory-corruption-with-width-1400.patch [bz#602724]
- kvm-net-Fix-VM-start-with-net-none.patch [bz#599460]
- kvm-monitor-Remove-pci_add-command-for-Red-Hat-Enterpris.patch [bz#602590]
- kvm-monitor-Remove-pci_del-command-for-Red-Hat-Enterpris.patch [bz#602590]
- kvm-monitor-Remove-drive_add-command-for-Red-Hat-Enterpr.patch [bz#602590]
- Resolves: bz#599460
  (virtio nic is hotpluged when hotplug rtl8139 nic to guest)
- Resolves: bz#602590
  (Disable pci_add, pci_del, drive_add)
- Resolves: bz#602724
  (VNC disconnect segfault on KVM video consoles)

* Tue Jun 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.75.el6
- kvm-qcow2-Fix-corruption-after-refblock-allocation.patch [bz#598407]
- kvm-qcow2-Fix-corruption-after-error-in-update_refcount.patch [bz#598507]
- kvm-qcow2-Allow-qcow2_get_cluster_offset-to-return-error.patch [bz#598507]
- kvm-qcow2-Change-l2_load-to-return-0-errno.patch [bz#598507]
- kvm-qcow2-Return-right-error-code-in-write_refcount_bloc.patch [bz#598507]
- kvm-qcow2-Clear-L2-table-cache-after-write-error.patch [bz#598507]
- kvm-qcow2-Fix-error-handling-in-l2_allocate.patch [bz#598507]
- kvm-qcow2-Restore-L1-entry-on-l2_allocate-failure.patch [bz#598507]
- kvm-qcow2-Allow-get_refcount-to-return-errors.patch [bz#598507]
- kvm-qcow2-Avoid-shadowing-variable-in-alloc_clusters_nor.patch [bz#598507]
- kvm-qcow2-Allow-alloc_clusters_noref-to-return-errors.patch [bz#598507]
- kvm-qcow2-Return-real-error-code-in-load_refcount_block.patch [bz#598507]
- kvm-make-release-make-mtime-owner-group-consistent.patch
- Resolves: bz#598407
  (qcow2 corruption bug in refcount table growth)
- Resolves: bz#598507
  (Backport qcow2 error path fixes)

* Mon Jun 14 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.74.el6
- kvm-raw-posix-Detect-CDROM-via-ioctl-on-linux.patch [bz#593758]
- kvm-block-Remove-special-case-for-vvfat.patch [bz#593758]
- kvm-block-Make-find_image_format-return-raw-BlockDriver-.patch [bz#593758]
- kvm-block-Add-missing-bdrv_delete-for-SG_IO-BlockDriver-.patch [bz#593758]
- kvm-block-Assume-raw-for-drives-without-media.patch [bz#593758]
- Resolves: bz#593758
  (qemu fails to start with -cdrom /dev/sr0 if no media inserted)

* Fri Jun 11 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.73.el6
- kvm-net-Fix-hotplug-with-pci_add.patch [bz#599460]
- Resolves: bz#599460
  (virtio nic is hotpluged when hotplug rtl8139 nic to guest)

* Wed Jun 09 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.72.el6
- kvm-Monitor-Make-RFQDN_REDHAT-public.patch [bz#586349]
- kvm-QMP-Add-error-reason-to-BLOCK_IO_ERROR-event.patch [bz#586349]
- kvm-virtio-net-truncating-packet.patch [bz#591494]
- kvm-vhost-net-check-PUBLISH_USED-in-backend.patch [bz#600203]
- kvm-device-assignment-don-t-truncate-MSIX-capabilities-t.patch [bz#596315]
- kvm-If-a-USB-keyboard-is-unplugged-the-keyboard-eventhan.patch [bz#561433]
- Resolves: bz#561433
  (Segfault when keyboard is removed)
- Resolves: bz#586349
  (BLOCK_IO_ERROR event does not provide the errno that caused it.)
- Resolves: bz#591494
  (Virtio: Transfer file caused guest in same vlan abnormally quit)
- Resolves: bz#596315
  (device assignment truncates MSIX table size)
- Resolves: bz#600203
  (vhost net new userspace on old kernel: 95: falling back on userspace virtio)

* Mon Jun 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.71.el6
- kvm-device-assignment-fix-failure-to-exit-on-shared-IRQ.patch [bz#585310]
- kvm-doc-Fix-host-forwarding-monitor-command-documentatio.patch [bz#588719]
- kvm-doc-Fix-acl-monitor-command-documentation.patch [bz#588719]
- kvm-doc-Heading-for-monitor-command-cpu-got-lost-restore.patch [bz#588719]
- kvm-doc-Clean-up-monitor-command-function-index.patch [bz#588719]
- kvm-fix-info-cpus-halted-state-reporting.patch [bz#593769]
- kvm-sysemu-Export-no_shutdown.patch [bz#559618]
- kvm-Monitor-Return-before-exiting-with-quit.patch [bz#559618]
- kvm-QMP-Add-Downstream-extension-of-QMP-to-spec.patch [bz#566291]
- kvm-Revert-PCI-Convert-pci_device_hot_add-to-QObject.patch [bz#580365]
- kvm-Revert-monitor-Convert-do_pci_device_hot_remove-to-Q.patch [bz#580365]
- kvm-drive-allow-rerror-werror-and-readonly-for-if-none.patch [bz#565609 bz#593256]
- kvm-qdev-properties-Fix-u-intXX-parsers.patch [bz#596093]
- kvm-vnc-factor-out-vnc_desktop_resize.patch [bz#590070]
- kvm-vnc-send-desktopresize-event-as-reply-to-set-encodin.patch [bz#590070]
- kvm-vnc-keep-track-of-client-desktop-size.patch [bz#590070]
- kvm-vnc-don-t-send-invalid-screen-updates.patch [bz#590070]
- kvm-vnc-move-size-changed-check-into-the-vnc_desktop_res.patch [bz#590070]
- kvm-check-for-active_console-before-using-it.patch [bz#591759]
- Resolves: bz#559618
  (QMP: Fix 'quit' to return success before exiting)
- Resolves: bz#565609
  (Unable to use werror/rerror with  -drive syntax using if=none)
- Resolves: bz#566291
  (QMP: Support vendor extensions)
- Resolves: bz#580365
  (QMP: pci_add/pci_del conversion should be reverted)
- Resolves: bz#585310
  (qemu-kvm does not exit when device assignment fails due to IRQ sharing)
- Resolves: bz#588719
  (Fix monitor command documentation)
- Resolves: bz#590070
  (QEMU misses DESKTOP-RESIZE event if it is triggered during client connection initialization)
- Resolves: bz#591759
  (Segmentation fault when using vnc to view guest without vga card)
- Resolves: bz#593256
  (Unable to set readonly flag for floppy disks)
- Resolves: bz#593769
  ("info cpus" doesn't show halted state)
- Resolves: bz#596093
  (16bit integer qdev properties are not parsed correctly.)

* Mon Jun 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.70.el6
- kvm-virtio-invoke-set_features-on-load.patch [bz#595263]
- kvm-virtio-net-return-with-value-in-void-function.patch [bz#595263]
- kvm-vhost-net-fix-reversed-logic-in-mask-notifiers.patch [bz#585940]
- kvm-hpet-Disable-for-Red-Hat-Enterprise-Linux.patch [bz#595130]
- ksmtuned: typo MemCached -> Cached [bz#597005]
- kvm-virtio-net-stop-vhost-backend-on-vmstop.patch [bz#598896]
- kvm-msix-fix-msix_set-unset_mask_notifier.patch [bz#598896]
- Resolves: bz#585940
  (qemu-kvm crashes on reboot when vhost is enabled)
- Resolves: bz#595130
  (Disable hpet by default)
- Resolves: bz#595263
  (virtio net lacks upstream fixes as of may 24)
- Resolves: bz#597005
  (ksmtune: typo: MemCached -> Cached)
- Resolves: bz#598896
  (migration breaks networking with vhost-net)

* Tue Jun 01 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.69.el6
- Changes to make-release script with no resulting changes on binary package
- kvm-virtio-utilize-PUBLISH_USED_IDX-feature.patch [bz#595287]
- Resolves: bz#595287
  (virtio net/vhost net speed enhancements from upstream kernel)

* Wed May 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.68.el6
- kvm-virtio-blk-fix-barrier-support.patch [bz#595813]
- Resolves: bz#595813
  (virtio-blk doesn't handle barriers correctly)

* Wed May 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.67.el6
- kvm-qemu-address-todo-comment-in-exec.c.patch [bz#595301]
- Resolves: bz#595301
  (QEMU terminates without warning with virtio-net and SMP enabled)

* Wed May 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.66.el6
- kvm-device-assignment-use-stdint-types.patch [bz#595495]
- kvm-device-assignment-Don-t-use-libpci.patch [bz#595495]
- kvm-device-assignment-add-config-fd-qdev-property.patch [bz#595495]
- Resolves: bz#595495
  (Fail to hotplug pci device to guest)

* Wed May 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.65.el6
- kvm-qcow2-Fix-creation-of-large-images.patch [bz#577106]
- kvm-vnc-sync-lock-modifier-state-on-connect.patch [bz#569767]
- kvm-json-lexer-Initialize-x-and-y.patch [bz#589952]
- kvm-json-lexer-Handle-missing-escapes.patch [bz#589952]
- kvm-qjson-Handle-f.patch [bz#589952]
- kvm-json-lexer-Drop-buf.patch [bz#589952]
- kvm-json-streamer-Don-t-use-qdict_put_obj.patch [bz#589952]
- kvm-block-fix-sector-comparism-in-multiwrite_req_compare.patch [bz#596119]
- kvm-block-Fix-multiwrite-with-overlapping-requests.patch [bz#596119]
- Resolves: bz#569767
  (Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc)
- Resolves: bz#577106
  (Abort/Segfault when creating qcow2 format image with 512b cluster size)
- Resolves: bz#589952
  (QMP breaks when issuing any command with a backslash)
- Resolves: bz#596119
  (Possible corruption after block request merge)

* Tue May 25 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.64.el6
- kvm-qemu-kvm-fix-crash-on-reboot-with-vhost-net.patch [bz#585940]
- Related: bz#585940
  (qemu-kvm crashes on reboot when vhost is enabled)

* Tue May 25 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.63.el6
- kvm-fix-undefined-shifts-by-32.patch [bz#590922]
- kvm-qemu-char.c-drop-debug-printfs-from-qemu_chr_parse_c.patch [bz#590922]
- kvm-Fix-corner-case-in-chardev-udp-parameter.patch [bz#590922]
- kvm-pci-passthrough-zap-option-rom-scanning.patch [bz#590922]
- kvm-UHCI-spurious-interrupt-fix.patch [bz#590922]
- kvm-Fix-SIGFPE-for-vnc-display-of-width-height-1.patch [bz#590922]
- kvm-spice-vmc-remove-ringbuffer.patch [bz#589670]
- kvm-spice-vmc-add-dprintfs.patch [bz#589670]
- Resolves: bz#589670
  (spice: Ensure ring data is save/restored on migration)
- Related: bz#590922
  (backport qemu-kvm-0.12.4 fixes to RHEL6)

* Mon May 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.62.el6
- kvm-block-add-logical_block_size-property.patch [bz#566785]
- kvm-virtio-serial-bus-fix-ports_map-allocation.patch [bz#591176]
- kvm-Move-cpu-model-config-file-to-agree-with-rpm-build-B.patch [bz#569661]
- Resolves: bz#566785
  (virt block layer must not keep guest's logical_block_size fixed)
- Resolves: bz#569661
  (RHEL6.0 requires backport of upstream cpu model support..)
- Resolves: bz#591176
  (migration fails since virtio-serial-bus is using uninitialized memory)

* Mon May 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.61.el6
- Add "file" format to bdrv whitelist
- Resolves: bz#593909
  (VM can not start by using qemu-kvm-0.12.1.2-2.56.el6)

* Thu May 20 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.60.el6
- kvm-spice-vmc-add-copyright.patch [bz#576488]
- kvm-spice-vmc-remove-debug-prints-and-defines.patch [bz#576488]
- kvm-spice-vmc-add-braces-to-single-line-if-s.patch [bz#576488]
- kvm-spice-vmc-s-SpiceVirtualChannel-SpiceVMChannel-g.patch [bz#576488]
- kvm-spice-vmc-s-spice_virtual_channel-spice_vmc-g.patch [bz#576488]
- kvm-spice-vmc-all-variables-of-type-SpiceVMChannel-renam.patch [bz#576488]
- kvm-spice-vmc-remove-meaningless-cast-of-void.patch [bz#576488]
- kvm-spice-vmc-add-spice_vmc_ring_t-fix-write-function.patch [bz#576488]
- kvm-spice-vmc-don-t-touch-guest_out_ring-on-unplug.patch [bz#576488]
- kvm-spice-vmc-VirtIOSerialPort-vars-renamed-to-vserport.patch [bz#576488]
- kvm-spice-vmc-add-nr-property.patch [bz#576488]
- kvm-spice-vmc-s-SPICE_VM_CHANNEL-SPICE_VMC-g.patch [bz#576488]
- kvm-spice-vmc-add-vmstate.-saves-active_interface.patch [bz#576488]
- kvm-spice-vmc-rename-guest-device-name-to-com.redhat.spi.patch [bz#576488]
- kvm-spice-vmc-remove-unused-property-name.patch [bz#576488]
- Resolves: bz#576488
  (Spice: virtio serial based device for guest-spice client communication)

* Wed May 19 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.59.el6
- kvm-pci-cleanly-backout-of-pci_qdev_init.patch [bz#590884]
- kvm-ide-Fix-ide_dma_cancel.patch [bz#593287]
- Resolves: bz#590884
  (bogus 'info pci' state when hot-added assigned device fails to initialize)
- Resolves: bz#593287
  (Failed asserting during ide_dma_cancel)

* Wed May 19 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.58.el6
- kvm-Fix-segfault-after-device-assignment-hot-remove.patch [bz#582874]
- Resolves: bz#582874
  (Guest hangs during restart after hot unplug then hot plug physical NIC card)

* Wed May 19 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.57.el6
- kvm-stash-away-SCM_RIGHTS-fd-until-a-getfd-command-arriv.patch [bz#582684]
- Resolves: bz#582684
  (Monitor: getfd command is broken)

* Wed May 19 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.56.el6
- kvm-dmg-fix-open-failure.patch [bz#580363]
- kvm-block-get-rid-of-the-BDRV_O_FILE-flag.patch [bz#580363]
- kvm-block-Convert-first_drv-to-QLIST.patch [bz#580363]
- kvm-block-separate-raw-images-from-the-file-protocol.patch [bz#580363]
- kvm-block-Split-bdrv_open.patch [bz#580363]
- kvm-block-Avoid-forward-declaration-of-bdrv_open_common.patch [bz#580363]
- kvm-block-Open-the-underlying-image-file-in-generic-code.patch [bz#580363]
- kvm-block-bdrv_has_zero_init.patch [bz#580363]
- kvm-block-Do-not-export-bdrv_first.patch [bz#590998]
- kvm-block-Convert-bdrv_first-to-QTAILQ.patch [bz#590998]
- kvm-block-Add-wr_highest_sector-blockstat.patch [bz#590998]
- Resolves: bz#580363
  (Error while creating raw image on block device)
- Resolves: bz#590998
  (qcow2 high watermark)

* Wed May 19 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.55.el6
- kvm-turn-off-kvmclock-when-resetting-cpu.patch [bz#588884]
- kvm-virtio-blk-Avoid-zeroing-every-request-structure.patch [bz#593369]
- Resolves: bz#588884
  (Rebooting a kernel with kvmclock enabled, into a kernel with kvmclock disabled, causes random crashes)
- Resolves: bz#593369
  (virtio-blk: Avoid zeroing every request structure)

* Mon May 17 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.54.el6
- kvm-qemu-config-qemu_read_config_file-reads-the-normal-c.patch [bz#588756]
- kvm-qemu-config-Make-qemu_config_parse-more-generic.patch [bz#588756]
- kvm-blkdebug-Basic-request-passthrough.patch [bz#588756]
- kvm-blkdebug-Inject-errors.patch [bz#588756]
- kvm-Make-qemu-config-available-for-tools.patch [bz#588756]
- kvm-blkdebug-Add-events-and-rules.patch [bz#588756]
- kvm-qcow2-Trigger-blkdebug-events.patch [bz#588756]
- kvm-qcow2-Fix-access-after-end-of-array.patch [bz#588762]
- kvm-qcow2-rename-two-QCowAIOCB-members.patch [bz#588762]
- kvm-qcow2-Don-t-ignore-immediate-read-write-failures.patch [bz#588762]
- kvm-qcow2-Remove-request-from-in-flight-list-after-error.patch [bz#588762]
- kvm-qcow2-Return-0-errno-in-write_l2_entries.patch [bz#588762]
- kvm-qcow2-Fix-error-return-code-in-qcow2_alloc_cluster_l.patch [bz#588762]
- kvm-qcow2-Return-0-errno-in-write_l1_entry.patch [bz#588762]
- kvm-qcow2-Return-0-errno-in-l2_allocate.patch [bz#588762]
- kvm-qcow2-Remove-abort-on-free_clusters-failure.patch [bz#588762]
- kvm-Add-qemu-error.o-only-once-to-target-list.patch [bz#591061]
- kvm-block-Fix-bdrv_commit.patch [bz#589439]
- kvm-fix-80000001.EDX-supported-bit-filtering.patch [bz#578106]
- kvm-fix-CPUID-vendor-override.patch [bz#591604]
- Resolves: bz#578106
  (call trace when boot guest with -cpu host)
- Resolves: bz#588756
  (blkdebug is missing)
- Resolves: bz#588762
  (Backport qcow2 fixes)
- Resolves: bz#589439
  (Qcow2 snapshot got corruption after commit using block device)
- Resolves: bz#591061
  (make fails to build after make clean)
- Resolves: bz#591604
  (cannot override cpu vendor from the command line)

* Wed May 12 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.53.el6
- kvm-virtio-blk-Fix-use-after-free-in-error-case.patch [bz#578448]
- kvm-block-Fix-multiwrite-error-handling.patch [bz#578448]
- kvm-Fix-boot-once-option.patch [bz#579692]
- kvm-QError-New-QERR_QMP_BAD_INPUT_OBJECT_MEMBER.patch [bz#573578]
- kvm-QMP-Use-QERR_QMP_BAD_INPUT_OBJECT_MEMBER.patch [bz#573578]
- kvm-QError-Improve-QERR_QMP_BAD_INPUT_OBJECT-desc.patch [bz#573578]
- kvm-QMP-Check-arguments-member-s-type.patch [bz#573578]
- kvm-QMP-Introduce-RESUME-event.patch [bz#590102]
- kvm-pci-irq_state-vmstate-breakage.patch [bz#588133]
- Resolves: bz#573578
  (Segfault when migrating via QMP command interface)
- Resolves: bz#578448
  (qemu-kvm segfault when nfs restart(without using werror&rerror))
- Resolves: bz#579692
  (qemu-kvm "-boot once=drives" couldn't function properly)
- Resolves: bz#588133
  (RHEL5.4 guest can lose virtio networking during migration)
- Resolves: bz#590102
  (QMP: Backport RESUME event)

* Mon May 10 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.52.el6
- kvm-qemu-img-use-the-heap-instead-of-the-huge-stack-arra.patch [bz#585837]
- kvm-qemu-img-rebase-Fix-output-image-corruption.patch [bz#585837]
- Resolves: bz#585837
  (After re-base snapshot, the file in the snapshot disappeared)

* Fri May 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.51.el6
- kvm-fdc-fix-drive-property-handling.patch [bz#584902]
- Resolves: bz#584902
  (Cannot associate drive with a floppy device using -global)

* Wed May 05 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.50.el6
- kvm-vl.c-fix-BZ-588828-endless-loop-caused-by-non-option.patch [bz#588828]
- Resolves: bz#588828
  (endless loop when parsing of command line with bare image argument)

* Tue May 04 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.49.el6
- kvm-block-Free-iovec-arrays-allocated-by-multiwrite_merg.patch [bz#586572]
- Resolves: bz#586572
  (virtio-blk multiwrite merge memory leak)
- Force spice to be enabled and fix BuildRequires to use spice-server-devel
- Resolves: bz#588904
  (qemu-kvm builds without spice support)

* Thu Apr 29 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.48.el6
- kvm-virtio-serial-save-load-Ensure-target-has-enough-por.patch [bz#574296]
- kvm-virtio-serial-save-load-Ensure-nr_ports-on-src-and-d.patch [bz#574296]
- kvm-virtio-serial-save-load-Ensure-we-have-hot-plugged-p.patch [bz#574296]
- kvm-virtio-serial-save-load-Send-target-host-connection-.patch [bz#574296]
- kvm-virtio-serial-Use-control-messages-to-notify-guest-o.patch [bz#574296]
- kvm-virtio-serial-whitespace-match-surrounding-code.patch [bz#574296]
- kvm-virtio-serial-Remove-redundant-check-for-0-sized-wri.patch [bz#574296]
- kvm-virtio-serial-Update-copyright-year-to-2010.patch [bz#574296]
- kvm-virtio-serial-Propagate-errors-in-initialising-ports.patch [bz#574296]
- kvm-virtio-serial-Send-out-guest-data-to-ports-only-if-p.patch [bz#574296]
- kvm-iov-Introduce-a-new-file-for-helpers-around-iovs-add.patch [bz#574296]
- kvm-iov-Add-iov_to_buf-and-iov_size-helpers.patch [bz#574296]
- kvm-virtio-serial-Handle-scatter-gather-buffers-for-cont.patch [bz#574296]
- kvm-virtio-serial-Handle-scatter-gather-input-from-the-g.patch [bz#574296]
- kvm-virtio-serial-Apps-should-consume-all-data-that-gues.patch [bz#574296]
- kvm-virtio-serial-Discard-data-that-guest-sends-us-when-.patch [bz#574296]
- kvm-virtio-serial-Implement-flow-control-for-individual-.patch [bz#574296]
- kvm-virtio-serial-Handle-output-from-guest-to-unintialis.patch [bz#574296]
- kvm-virtio-serial-bus-wake-up-iothread-upon-guest-read-n.patch [bz#574296]
- kvm-Bail-out-when-VCPU_CREATE-fails.patch [bz#587227]
- Resolves: bz#574296
  (Fix migration for virtio-serial after port hot-plug/hot-unplug operations)
- Resolves: bz#587227
  (Fix segfault when creating more vcpus than allowed.)

* Wed Apr 28 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.47.el6
- kvm-Request-setting-of-nmi_pending-and-sipi_vector.patch [bz#569613]
- Resolves: bz#569613
  (backport qemu-kvm-0.12.3 fixes to RHEL6)

* Tue Apr 27 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.46.el6
- kvm-spice-add-auth-info-to-monitor-events.patch [bz#581540]
- Resolves: bz#581540
  (SPICE graphics event does not include auth details)

* Mon Apr 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.45.el6
- kvm-Documentation-Add-monitor-commands-to-function-index.patch [bz#559670]
- kvm-error-Put-error-definitions-back-in-alphabetical-ord.patch [bz#559670]
- kvm-error-New-QERR_DUPLICATE_ID.patch [bz#559670]
- kvm-error-Convert-qemu_opts_create-to-QError.patch [bz#559670]
- kvm-error-New-QERR_INVALID_PARAMETER_VALUE.patch [bz#559670]
- kvm-error-Convert-qemu_opts_set-to-QError.patch [bz#559670]
- kvm-error-Drop-extra-messages-after-qemu_opts_set-and-qe.patch [bz#559670]
- kvm-error-Use-QERR_INVALID_PARAMETER_VALUE-instead-of-QE.patch [bz#559670]
- kvm-error-Convert-qemu_opts_validate-to-QError.patch [bz#559670]
- kvm-error-Convert-net_client_init-to-QError.patch [bz#559670]
- kvm-error-New-QERR_DEVICE_IN_USE.patch [bz#559670]
- kvm-monitor-New-commands-netdev_add-netdev_del.patch [bz#559670]
- kvm-qdev-Convert-qdev_unplug-to-QError.patch [bz#582325]
- kvm-monitor-convert-do_device_del-to-QObject-QError.patch [bz#582325]
- kvm-block-Fix-error-code-in-multiwrite-for-immediate-fai.patch [bz#582575]
- kvm-block-Fix-multiwrite-memory-leak-in-error-case.patch [bz#582575]
- Resolves: bz#559670
  (No 'netdev_add' command in monitor)
- Resolves: bz#582325
  (QMP: device_del support)
- Resolves: bz#582575
  (Backport bdrv_aio_multiwrite fixes)

* Mon Apr 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.44.el6
- kvm-spice-add-more-config-options-readd.patch [bz#576561]
- BuildRequires spice-server-devel >= 0.4.2-10.el6 because of API changes
- Resolves: bz#576561
  (spice: add more config options)

* Mon Apr 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.43.el6
- kvm-qemu-option-Make-qemu_opts_foreach-accumulate-return.patch [bz#579470]
- kvm-qdev-Fix-exit-code-for-device.patch [bz#579470]
- kvm-qdev-Add-help-for-device-properties.patch [bz#579470]
- kvm-qdev-update-help-on-device.patch [bz#579470]
- kvm-qdev-Add-rudimentary-help-for-property-value.patch [bz#579470]
- kvm-qdev-Free-opts-on-failed-do_device_add.patch [bz#579470]
- kvm-qdev-Improve-diagnostics-for-bad-property-values.patch [bz#579470]
- kvm-qdev-Catch-attempt-to-attach-more-than-one-device-to.patch [bz#579470]
- kvm-usb-Remove-disabled-monitor_printf-in-usb_read_file.patch [bz#579470]
- kvm-savevm-Fix-loadvm-to-report-errors-to-stderr-not-the.patch [bz#579470]
- kvm-pc-Fix-error-reporting-for-boot-once.patch [bz#579470]
- kvm-pc-Factor-common-code-out-of-pc_boot_set-and-cmos_in.patch [bz#579470]
- kvm-tools-Remove-unused-cur_mon-from-qemu-tool.c.patch [bz#579470]
- kvm-monitor-Separate-default-monitor-and-current-monitor.patch [bz#579470]
- kvm-block-Simplify-usb_msd_initfn-test-for-can-read-bdrv.patch [bz#579470]
- kvm-monitor-Factor-monitor_set_error-out-of-qemu_error_i.patch [bz#579470]
- kvm-error-Move-qemu_error-friends-from-monitor.c-to-own-.patch [bz#579470]
- kvm-error-Simplify-error-sink-setup.patch [bz#579470]
- kvm-error-Move-qemu_error-friends-into-their-own-header.patch [bz#579470]
- kvm-error-New-error_printf-and-error_vprintf.patch [bz#579470]
- kvm-error-Don-t-abuse-qemu_error-for-non-error-in-qdev_d.patch [bz#579470]
- kvm-error-Don-t-abuse-qemu_error-for-non-error-in-qbus_f.patch [bz#579470]
- kvm-error-Don-t-abuse-qemu_error-for-non-error-in-scsi_h.patch [bz#579470]
- kvm-error-Replace-qemu_error-by-error_report.patch [bz#579470]
- kvm-error-Rename-qemu_error_new-to-qerror_report.patch [bz#579470]
- kvm-error-Infrastructure-to-track-locations-for-error-re.patch [bz#579470]
- kvm-error-Include-the-program-name-in-error-messages-to-.patch [bz#579470]
- kvm-error-Track-locations-in-configuration-files.patch [bz#579470]
- kvm-QemuOpts-Fix-qemu_config_parse-to-catch-file-read-er.patch [bz#579470]
- kvm-error-Track-locations-on-command-line.patch [bz#579470]
- kvm-qdev-Fix-device-and-device_add-to-handle-unsuitable-.patch [bz#579470]
- kvm-qdev-Factor-qdev_create_from_info-out-of-qdev_create.patch [bz#579470]
- kvm-qdev-Hide-no_user-devices-from-users.patch [bz#579470]
- kvm-qdev-Hide-ptr-properties-from-users.patch [bz#579470]
- kvm-monitor-New-monitor_cur_is_qmp.patch [bz#579470]
- kvm-error-Let-converted-handlers-print-in-human-monitor.patch [bz#579470]
- kvm-error-Polish-human-readable-error-descriptions.patch [bz#579470]
- kvm-error-New-QERR_PROPERTY_NOT_FOUND.patch [bz#579470]
- kvm-error-New-QERR_PROPERTY_VALUE_BAD.patch [bz#579470]
- kvm-error-New-QERR_PROPERTY_VALUE_IN_USE.patch [bz#579470]
- kvm-error-New-QERR_PROPERTY_VALUE_NOT_FOUND.patch [bz#579470]
- kvm-qdev-convert-setting-device-properties-to-QError.patch [bz#579470]
- kvm-qdev-Relax-parsing-of-bus-option.patch [bz#579470]
- kvm-error-New-QERR_BUS_NOT_FOUND.patch [bz#579470]
- kvm-error-New-QERR_DEVICE_MULTIPLE_BUSSES.patch [bz#579470]
- kvm-error-New-QERR_DEVICE_NO_BUS.patch [bz#579470]
- kvm-qdev-Convert-qbus_find-to-QError.patch [bz#579470]
- kvm-error-New-error_printf_unless_qmp.patch [bz#579470]
- kvm-error-New-QERR_BAD_BUS_FOR_DEVICE.patch [bz#579470]
- kvm-error-New-QERR_BUS_NO_HOTPLUG.patch [bz#579470]
- kvm-error-New-QERR_DEVICE_INIT_FAILED.patch [bz#579470]
- kvm-error-New-QERR_NO_BUS_FOR_DEVICE.patch [bz#579470]
- kvm-Revert-qdev-Use-QError-for-device-not-found-error.patch [bz#579470]
- kvm-error-Convert-do_device_add-to-QError.patch [bz#579470]
- kvm-qemu-option-Functions-to-convert-to-from-QDict.patch [bz#579470]
- kvm-qemu-option-Move-the-implied-first-name-into-QemuOpt.patch [bz#579470]
- kvm-qemu-option-Rename-find_list-to-qemu_find_opts-exter.patch [bz#579470]
- kvm-monitor-New-argument-type-O.patch [bz#579470]
- kvm-monitor-Use-argument-type-O-for-device_add.patch [bz#579470]
- kvm-monitor-convert-do_device_add-to-QObject.patch [bz#579470]
- kvm-error-Trim-includes-after-Move-qemu_error-friends.patch [bz#579470]
- kvm-error-Trim-includes-in-qerror.c.patch [bz#579470]
- kvm-error-Trim-includes-after-Infrastructure-to-track-lo.patch [bz#579470]
- kvm-error-Make-use-of-error_set_progname-optional.patch [bz#579470]
- kvm-error-Link-qemu-img-qemu-nbd-qemu-io-with-qemu-error.patch [bz#579470]
- kvm-error-Move-qerror_report-from-qemu-error.-ch-to-qerr.patch [bz#579470]
- Resolves: bz#579470
  (QMP: device_add support)

* Fri Apr 23 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.42.el6
- kvm-net-remove-NICInfo.bootable-field.patch [bz#561078]
- kvm-net-remove-broken-net_set_boot_mask-boot-device-vali.patch [bz#561078]
- kvm-boot-remove-unused-boot_devices_bitmap-variable.patch [bz#561078]
- kvm-check-kvm-enabled.patch [bz#580109]
- kvm-qemu-rename-notifier-event_notifier.patch [bz#580109]
- kvm-virtio-API-name-cleanup.patch [bz#580109]
- kvm-vhost-u_int64_t-uint64_t.patch [bz#580109]
- kvm-virtio-pci-fix-coding-style.patch [bz#580109]
- kvm-vhost-detect-lack-of-support-earlier-style.patch [bz#580109]
- kvm-configure-vhost-related-fixes.patch [bz#580109]
- kvm-vhost-fix-features-ack.patch [bz#580109]
- kvm-vhost-net-disable-mergeable-buffers.patch [bz#580109]
- Resolves: bz#561078
  ("Cannot boot from non-existent NIC" when using virt-install --pxe)
- Resolves: bz#580109
  (vhost net lacks upstream fixes)

* Thu Apr 22 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.41.el6
- Build fix: pass sysconfdir to 'make install'
- Related: bz#569661

* Tue Apr 20 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.40.el6
- cpu-model-config-1.patch [bz#569661]
- cpu-model-config-2.patch [bz#569661]
- cpu-model-config-3.patch [bz#569661]
- cpu-model-config-4.patch [bz#569661]
- Resolves: bz#569661
  (RHEL6.0 requires backport of upstream cpu model support..)

* Mon Apr 19 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.39.el6
- kvm-virtio-blk-revert-serial-number-support.patch [bz#564101]
- kvm-block-add-topology-qdev-properties.patch [bz#564101]
- kvm-virtio-blk-add-topology-support.patch [bz#564101]
- kvm-scsi-add-topology-support.patch [bz#564101]
- kvm-ide-add-topology-support.patch [bz#564101]
- kvm-pcnet-make-subsystem-vendor-id-match-hardware.patch [bz#580140]
- Resolves: bz#564101
  ([RFE] topology support in the virt block layer)
- Resolves: bz#580140
  (emulated pcnet nic in qemu-kvm has wrong PCI subsystem ID for Windows XP driver)

* Tue Apr 13 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.38.el6
- kvm-read-only-Make-CDROM-a-read-only-drive.patch [bz#537164]
- kvm-read-only-BDRV_O_FLAGS-cleanup.patch [bz#537164]
- kvm-read-only-Added-drives-readonly-option.patch [bz#537164]
- kvm-read-only-Disable-fall-back-to-read-only.patch [bz#537164]
- kvm-read-only-No-need-anymoe-for-bdrv_set_read_only.patch [bz#537164]
- kvm-read_only-Ask-for-read-write-permissions-when-openin.patch [bz#537164]
- kvm-read-only-Read-only-device-changed-to-opens-it-s-fil.patch [bz#537164]
- kvm-read-only-qemu-img-Fix-qemu-img-can-t-create-qcow-im.patch [bz#537164]
- kvm-block-clean-up-bdrv_open2-structure-a-bit.patch [bz#537164]
- kvm-block-saner-flags-filtering-in-bdrv_open2.patch [bz#537164]
- kvm-block-flush-backing_hd-in-the-right-place.patch [bz#537164]
- kvm-block-fix-cache-flushing-in-bdrv_commit.patch [bz#537164]
- kvm-block-more-read-only-changes-related-to-backing-file.patch [bz#537164]
- kvm-read-only-minor-cleanup.patch [bz#537164]
- kvm-read-only-Another-minor-cleanup.patch [bz#537164]
- kvm-read-only-allow-read-only-CDROM-with-any-interface.patch [bz#537164]
- kvm-qemu-img-rebase-Add-f-option.patch [bz#580028]
- kvm-qemu-io-Fix-return-value-handling-of-bdrv_open.patch [bz#579974]
- kvm-qemu-nbd-Fix-return-value-handling-of-bdrv_open.patch [bz#579974]
- kvm-qemu-img-Fix-error-message.patch [bz#579974]
- kvm-Replace-calls-of-old-bdrv_open.patch [bz#579974]
- Resolves: bz#537164
  (-drive arg has no way to request a read only disk)
- Resolves: bz#579974
  (Get segmentation fault when creating qcow2 format image on block device with "preallocation=metadata")
- Resolves: bz#580028
  ('qemu-img re-base' broken on block devices)

* Mon Apr 12 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.37.el6
- kvm-balloon-Fix-overflow-when-reporting-actual-memory-si.patch [bz#578912]
- kvm-json-parser-Output-the-content-of-invalid-keyword.patch [bz#576544]
- Resolves: bz#576544
  (Error message doesn't contain the content of invalid keyword)
- Resolves: bz#578912
  (Monitor: Overflow in 'info balloon')

* Wed Apr 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.36.el6
- kvm-char-Remove-redundant-qemu_chr_generic_open-call.patch [bz#558236]
- kvm-add-close-callback-for-tty-based-char-device.patch [bz#558236]
- kvm-Restore-terminal-attributes-for-tty-based-monitor.patch [bz#558236]
- kvm-Restore-terminal-monitor-attributes-addition.patch [bz#558236]
- Resolves: bz#558236
  (qemu-kvm monitor corrupts tty on exit)

* Tue Apr 06 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.35.el6
- kvm-QError-New-QERR_DEVICE_NOT_ENCRYPTED.patch [bz#563641]
- kvm-Wrong-error-message-in-block_passwd-command.patch [bz#563641]
- kvm-Monitor-Introduce-RFQDN_REDHAT-and-use-it.patch [bz#578493]
- kvm-QMP-Fix-Spice-event-names.patch [bz#578493]
- Resolves: bz#563641
  (QMP: Wrong error message in block_passwd command)
- Resolves: bz#578493
  (QMP: Fix spice event names)
- ksm.init: touch max_kernel_pages only if it exists [bz#561907]
- Resolves: bz#561907
- ksmtuned: add debug information [bz#576789]
- Resolves: bz#576789

* Tue Mar 30 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.34.el6
- kvm-Monitor-Introduce-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-simple-handlers-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_cont-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_eject-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_cpu_set-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_block_set_passwd-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_getfd-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_closefd-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-pci_device_hot_add-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-pci_device_hot_remove-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_migrate-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_memory_save-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_physical_memory_save-to-cmd_new_r.patch [bz#563491]
- kvm-Monitor-Convert-do_info-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-do_change-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-to-mon_set_password-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Convert-mon_spice_migrate-to-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Rename-cmd_new_ret.patch [bz#563491]
- kvm-Monitor-Debugging-support.patch [bz#563491]
- kvm-Monitor-Drop-the-print-disabling-mechanism.patch [bz#563491]
- kvm-Monitor-Audit-handler-return.patch [bz#563491]
- kvm-Monitor-Debug-stray-prints-the-right-way.patch [bz#563491]
- kvm-Monitor-Report-more-than-one-error-in-handlers.patch [bz#563491]
- Resolves: bz#563491
  (QMP: New internal error handling mechanism)

* Mon Mar 29 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.33.el6
- kvm-Fix-kvm_load_mpstate-for-vcpu-hot-add.patch [bz#569613]
- kvm-qemu-kvm-enable-get-set-vcpu-events-on-reset-and-mig.patch [bz#569613]
- kvm-Synchronize-kvm-headers.patch [bz#569613]
- kvm-Increase-VNC_MAX_WIDTH.patch [bz#569613]
- kvm-device-assignment-default-requires-IOMMU.patch [bz#569613]
- kvm-Do-not-allow-vcpu-stop-with-in-progress-PIO.patch [bz#569613]
- kvm-fix-savevm-command-without-id-or-tag.patch [bz#569613]
- kvm-Do-not-ignore-error-if-open-file-failed-serial-dev-t.patch [bz#569613]
- kvm-segfault-due-to-buffer-overrun-in-usb-serial.patch [bz#569613]
- kvm-fix-inet_parse-typo.patch [bz#569613]
- kvm-virtio-net-fix-network-stall-under-load.patch [bz#569613]
- kvm-don-t-dereference-NULL-after-failed-strdup.patch [bz#569613]
- kvm-net-Remove-unused-net_client_uninit.patch [bz#569613]
- kvm-net-net_check_clients-runs-too-early-to-see-device-f.patch [bz#569613]
- kvm-net-Fix-bogus-Warning-vlan-0-with-no-nics-with-devic.patch [bz#569613]
- kvm-net-net_check_clients-checks-only-VLAN-clients-fix.patch [bz#569613]
- kvm-net-info-network-shows-only-VLAN-clients-fix.patch [bz#569613]
- kvm-net-Monitor-command-set_link-finds-only-VLAN-clients.patch [bz#569613]
- kvm-ide-save-restore-pio-atapi-cmd-transfer-fields-and-i.patch [bz#569613]
- kvm-cirrus-Properly-re-register-cirrus_linear_io_addr-on.patch [bz#569613]
- Related: bz#569613
  (backport qemu-kvm-0.12.3 fixes to RHEL6)

* Fri Mar 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.32.el6
- kvm-Revert-spice-add-more-config-options.patch [bz#576561]
  (need to wait for spice patches to be included on spice-server)
- Related: bz#576561
  (spice: add more config options)

* Fri Mar 26 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.31.el6
- kvm-Transparent-Hugepage-Support-3.patch [bz#574525]
- kvm-monitor-Don-t-check-for-mon_get_cpu-failure.patch [bz#574642]
- kvm-QError-New-QERR_OPEN_FILE_FAILED.patch [bz#574642]
- kvm-monitor-convert-do_memory_save-to-QError.patch [bz#574642]
- kvm-monitor-convert-do_physical_memory_save-to-QError.patch [bz#574642]
- kvm-QError-New-QERR_INVALID_CPU_INDEX.patch [bz#574642]
- kvm-monitor-convert-do_cpu_set-to-QObject-QError.patch [bz#574642]
- kvm-monitor-Use-QERR_INVALID_PARAMETER-instead-of-QERR_I.patch [bz#575800]
- kvm-Revert-QError-New-QERR_INVALID_CPU_INDEX.patch [bz#575800]
- kvm-json-parser-Fix-segfault-on-malformed-input.patch [bz#575800]
- kvm-fix-i-format-handling-in-memory-dump.patch [bz#575800]
- kvm-Don-t-set-default-monitor-when-there-is-a-mux-ed-one.patch [bz#575800]
- kvm-monitor-Document-argument-type-M.patch [bz#575821]
- kvm-QDict-New-qdict_get_double.patch [bz#575821]
- kvm-monitor-New-argument-type-b.patch [bz#575821]
- kvm-monitor-Use-argument-type-b-for-migrate_set_speed.patch [bz#575821]
- kvm-monitor-convert-do_migrate_set_speed-to-QObject.patch [bz#575821]
- kvm-monitor-New-argument-type-T.patch [bz#575821]
- kvm-monitor-Use-argument-type-T-for-migrate_set_downtime.patch [bz#575821]
- kvm-monitor-convert-do_migrate_set_downtime-to-QObject.patch [bz#575821]
- kvm-block-Emit-BLOCK_IO_ERROR-before-vm_stop-call.patch [bz#575912]
- kvm-QMP-Move-STOP-event-into-do_vm_stop.patch [bz#575912]
- kvm-QMP-Move-RESET-event-into-qemu_system_reset.patch [bz#575912]
- kvm-QMP-Sync-with-upstream-event-changes.patch [bz#575912]
- kvm-QMP-Drop-DEBUG-event.patch [bz#575912]
- kvm-QMP-Revamp-the-qmp-events.txt-file.patch [bz#575912]
- kvm-QMP-Introduce-RTC_CHANGE-event.patch [bz#547534]
- kvm-QMP-Introduce-WATCHDOG-event.patch [bz#557083]
- kvm-spice-add-more-config-options.patch [bz#576561]
- Resolves: bz#547534
  (RFE: a QMP event notification for RTC clock changes)
- Resolves: bz#557083
  (QMP events for watchdog events)
- Resolves: bz#574525
  (Align qemu-kvm guest memory for transparent hugepage support)
- Resolves: bz#574642
  (QMP: Convert do_cpu_set() to QObject)
- Resolves: bz#575800
  (Monitor: Backport a collection of fixes)
- Resolves: bz#575821
  (QMP: Convert migrate_set_speed, migrate_set_downtime to QObject)
- Resolves: bz#575912
  (QMP: Backport event related fixes)
- Resolves: bz#576561
  (spice: add more config options)

* Thu Mar 25 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.30.el6
- kvm-New-API-for-asynchronous-monitor-commands.patch [bz#574939]
- kvm-Revert-QMP-Fix-query-balloon-key-change.patch [bz#574939]
- kvm-virtio-Add-memory-statistics-reporting-to-the-balloo.patch [bz#574939]
- Resolves: bz#574939
  (Memory statistics support)

* Wed Mar 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.29.el6
- kvm-scsi-device-version-property.patch [bz#558835]
- kvm-scsi-disk-fix-buffer-overflow.patch [bz#558835]
- Resolves: bz#558835
  (ide/scsi drive versions)

* Wed Mar 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.28.el6
- kvm-qcow2-Factor-next_refcount_table_size-out.patch [bz#567940]
- kvm-qcow2-Rewrite-alloc_refcount_block-grow_refcount_tab.patch [bz#567940]
- kvm-qcow2-More-checks-for-qemu-img-check.patch [bz#567940]
- kvm-spice-virtual-machine-channel-replacement-for-remove.patch [bz#576488]
- Resolves: bz#567940
  (qcow2 corruption with I/O error during refcount block allocation)
- Resolves: bz#576488
  (Spice: virtio serial based device for guest-spice client communication)

* Wed Mar 24 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.27.el6
- kvm-spice-add-tablet.patch [bz#574211]
- kvm-spice-simple-display-wake-spice-server-only-when-idl.patch [bz#574212]
- kvm-spice-qxl-switch-back-to-vga-mode-on-register-access.patch [bz#574214]
- kvm-spice-qxl-ring-access-security-fix.patch [bz#568820]
- kvm-vnc-support-password-expire.patch [bz#525935]
- kvm-spice-vnc-add-__com.redhat_set_password-monitor-comm.patch [bz#525935]
- kvm-spice-add-audio-support.patch [bz#574222]
- kvm-spice-make-image-compression-configurable.patch [bz#574225]
- kvm-spice-configure-channel-security.patch [bz#574225]
- kvm-spice-configure-renderer.patch [bz#574225]
- kvm-spice-send-connect-disconnect-monitor-events.patch [bz#558957]
- kvm-spice-qxl-update-vga-help-text-indicating-qxl-is-the.patch [bz#574853]
- kvm-spice-notifying-spice-when-migration-starts-and-ends.patch [bz#574849]
- kvm-spice-add-__com.redhat_spice_migrate_info-monitor-co.patch [bz#574849]
- Resolves: bz#525935
  (RFE: expire vnc password)
- Resolves: bz#558957
  (A QMP event notification on SPICE client connect/disconnect events)
- Resolves: bz#568820
  (EMBARGOED CVE-2010-0431 qemu: Insufficient guest provided pointers validation [rhel-6.0])
- Resolves: bz#574211
  (spice: add tablet support)
- Resolves: bz#574212
  (spice:wake spice server only when idle)
- Resolves: bz#574214
  (qxl: switch qxl from native into vga mode on vga register access)
- Resolves: bz#574222
  (spice: add audio support)
- Resolves: bz#574225
  (spice: add config options)
- Resolves: bz#574849
  (spice: client migration support)
- Resolves: bz#574853
  (spice/qxl: add qxl to -vga help text)

* Thu Mar 18 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.26.el6
- kvm-add-spice-into-the-configure-file.patch [bz#549757]
- kvm-spice-core-bits.patch [bz#549757]
- kvm-spice-add-keyboard.patch [bz#549757]
- kvm-spice-add-mouse.patch [bz#549757]
- kvm-spice-simple-display.patch [bz#549757]
- kvm-move-x509-file-name-defines-to-qemu-x509.h.patch [bz#549757]
- kvm-spice-tls-support.patch [bz#549757]
- kvm-spice-configure-listening-addr.patch [bz#549757]
- kvm-spice-add-qxl-device.patch [bz#549757]
- Resolves: bz#549757
  (Provide SPICE support  / -spice command line argument)

* Wed Mar 17 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.25.el6
- kvm-qemu-memory-notifiers.patch [bz#562958]
- kvm-tap-add-interface-to-get-device-fd.patch [bz#562958]
- kvm-add-API-to-set-ioeventfd.patch [bz#562958]
- kvm-notifier-event-notifier-implementation.patch [bz#562958]
- kvm-virtio-add-notifier-support.patch [bz#562958]
- kvm-virtio-add-APIs-for-queue-fields.patch [bz#562958]
- kvm-virtio-add-set_status-callback.patch [bz#562958]
- kvm-virtio-move-typedef-to-qemu-common.patch [bz#562958]
- kvm-virtio-pci-fill-in-notifier-support.patch [bz#562958]
- kvm-vhost-vhost-net-support.patch [bz#562958]
- kvm-tap-add-vhost-vhostfd-options.patch [bz#562958]
- kvm-tap-add-API-to-retrieve-vhost-net-header.patch [bz#562958]
- kvm-virtio-net-vhost-net-support.patch [bz#562958]
- kvm-qemu-kvm-add-vhost.h-header.patch [bz#562958]
- kvm-irqfd-support.patch [bz#562958]
- kvm-msix-add-mask-unmask-notifiers.patch [bz#562958]
- kvm-virtio-pci-irqfd-support.patch [bz#562958]
- Resolves: bz#562958
  (RFE: Support vhost net mode)

* Fri Mar 12 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.24.el6
- kvm-path.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-hw-pc.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-slirp-misc.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-savevm.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-block-bochs.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-block.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-Introduce-qemu_write_full.patch [bz#567099]
- kvm-force-to-test-result-for-qemu_write_full.patch [bz#567099]
- kvm-block-cow.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-block-qcow.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-block-vmdk.o-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-block-vvfat.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-block-qcow2.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-net-slirp.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-usb-linux.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-vl.c-fix-warning-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-monitor.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-linux-user-mmap.c-fix-warnings-with-_FORTIFY_SOURCE.patch [bz#567099]
- kvm-check-pipe-return-value.patch [bz#567099]
- kvm-fix-qemu-kvm-_FORTIFY_SOURCE-compilation.patch [bz#567099]
- kvm-Enable-_FORTIFY_SOURCE-2.patch [bz#567099]
- kvm-qcow2-Fix-image-creation-regression.patch [bz#567099]
- kvm-cow-return-errno-instead-of-1.patch [bz#567099]
- kvm-slirp-check-system-success.patch [bz#567099]
- kvm-qcow2-return-errno-instead-of-1.patch [bz#567099]
- kvm-qcow-return-errno-instead-of-1.patch [bz#567099]
- kvm-vmdk-return-errno-instead-of-1.patch [bz#567099]
- kvm-vmdk-make-vmdk_snapshot_create-return-errno.patch [bz#567099]
- kvm-vmdk-fix-double-free.patch [bz#567099]
- kvm-vmdk-share-cleanup-code.patch [bz#567099]
- kvm-block-print-errno-on-error.patch [bz#567099]
- kvm-documentation-qemu_write_full-don-t-work-with-non-bl.patch [bz#567099]
- kvm-virtio-serial-pci-Allow-MSI-to-be-disabled.patch [bz#567035]
- kvm-pc-Add-backward-compatibility-options-for-virtio-ser.patch [bz#567035]
- kvm-virtio-serial-don-t-set-MULTIPORT-for-1-port-dev.patch [bz#567035]
- kvm-qdev-Add-a-DEV_NVECTORS_UNSPECIFIED-enum-for-unspeci.patch [bz#567035]
- kvm-virtio-pci-Use-DEV_NVECTORS_UNSPECIFIED-instead-of-1.patch [bz#567035]
- kvm-kbd-leds-infrastructure.patch [bz#569767]
- kvm-kbd-leds-ps-2-kbd.patch [bz#569767]
- kvm-kbd-leds-usb-kbd.patch [bz#569767]
- kvm-kbd-keds-vnc.patch [bz#569767]
- kvm-migration-Clear-fd-also-in-error-cases.patch [bz#570174]
- Resolves: bz#567035
  (Backport changes for virtio-serial from upstream: disabling MSI, backward compat.)
- Resolves: bz#567099
  (Allow _FORTIFY_SOURCE=2 & --enable-warning)
- Resolves: bz#569767
  (Caps Lock the key's appearance  of guest is not synchronous as host's --view kvm with vnc)
- Resolves: bz#570174
  (Restoring a qemu guest from a saved state file using -incoming sometimes fails and hangs)

* Tue Mar 02 2010 Glauber Costa <glommer@redhat.com> - qemu-kvm-0.12.1.2-2.23.el6
- kvm-ide-device-version-property.patch [bz#558835]
- kvm-pc-add-driver-version-compat-properties.patch [bz#558835]
- kvm-qemu-img-Fix-segfault-during-rebase.patch [bz#567602]
- Resolves: bz#558835
  (ide/scsi drive versions)
- Resolves: bz#567602
  (qemu-img rebase subcommand got Segmentation fault)

* Mon Mar 01 2010 Glauber Costa <glommer@redhat.com> - qemu-kvm-0.12.1.2-2.22.el6
- kvm-QMP-BLOCK_IO_ERROR-event-handling.patch [bz#547501]
- kvm-block-BLOCK_IO_ERROR-QMP-event.patch [bz#547501]
- kvm-ide-Generate-BLOCK_IO_ERROR-QMP-event.patch [bz#547501]
- kvm-scsi-Generate-BLOCK_IO_ERROR-QMP-event.patch [bz#547501]
- kvm-virtio-blk-Generate-BLOCK_IO_ERROR-QMP-event.patch [bz#547501]
- kvm-add-rhel-machine-types.patch [bz#558838]
- kvm-QMP-Fix-query-balloon-key-change.patch [bz#568739]
- Resolves: bz#547501
  (RFE: a QMP event notification for disk  I/O errors with werror/rerror flags)
- Resolves: bz#558838
  (add rhel machine types)
- Resolves: bz#568739
  (QMP: Fix 'query-balloon' key)

* Fri Feb 26 2010 Glauber Costa <glommer@redhat.com> - qemu-kvm-0.12.1.2-2.21.el6
- kvm-net-add-API-to-disable-enable-polling.patch [bz#562958]
- kvm-virtio-rename-features-guest_features.patch [bz#562958]
- kvm-qdev-add-bit-property-type.patch [bz#562958]
- kvm-qdev-fix-thinko-leading-to-guest-crashes.patch [bz#562958]
- kvm-virtio-add-features-as-qdev-properties-fixup.patch [bz#562958]
- Resolves: bz#562958
  (RFE: Support vhost net mode)

* Fri Feb 26 2010 Glauber Costa <glommer@redhat.com> - qemu-kvm-0.12.1.2-2.20.el6
- kvm-QMP-Add-QEMU-s-version-to-the-greeting-message.patch [bz#557930]
- kvm-QMP-Introduce-the-qmp_capabilities-command.patch [bz#557930]
- kvm-QMP-Enforce-capability-negotiation-rules.patch [bz#557930]
- kvm-QMP-spec-Capability-negotiation-updates.patch [bz#557930]
- kvm-json-escape-u0000-.-u001F-when-outputting-json.patch [bz#559667]
- kvm-json-fix-PRId64-on-Win32.patch [bz#563878]
- kvm-qjson-Improve-debugging.patch [bz#563875]
- kvm-Monitor-remove-unneeded-checks.patch [bz#563876]
- kvm-QError-Don-t-abort-on-multiple-faults.patch [bz#559635]
- kvm-QMP-Don-t-leak-on-connection-close.patch [bz#559645]
- kvm-QMP-Emit-Basic-events.patch [bz#558623]
- Resolves: bz#557930
  (QMP: Feature Negotiation support)
- Resolves: bz#558623
  (QMP: Basic async events are not emitted)
- Resolves: bz#559635
  (QMP: assertion on multiple faults)
- Resolves: bz#559645
  (QMP: leak when a QMP connection is closed)
- Resolves: bz#559667
  (QMP: JSON parser doesn't escape some control chars)
- Resolves: bz#563875
  (QJSON: Improve debugging)
- Resolves: bz#563876
  (Monitor: remove unneeded checks)
- Resolves: bz#563878
  (QJSON: Fix PRId64 handling)

* Fri Feb 19 2010 Glauber Costa <glommer@redhat.com> - qemu-kvm-0.12.1.2-2.19.el6
- kvm-virtio_blk-Factor-virtio_blk_handle_request-out.patch [bz#560942]
- kvm-virtio-blk-Fix-restart-after-read-error.patch [bz#560942]
- kvm-virtio-blk-Fix-error-cases-which-ignored-rerror-werr.patch [bz#560942]
- Resolves: bz#560942
  (virtio-blk error handling doesn't work reliably)

* Thu Feb 11 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.18.el6
- kvm-roms-minor-fixes-and-cleanups.patch [bz#558818]
- kvm-fw_cfg-rom-loader-tweaks.patch [bz#558818]
- kvm-roms-rework-rom-loading-via-fw.patch [bz#558818]
- kvm-pci-allow-loading-roms-via-fw_cfg.patch [bz#558818]
- kvm-pc-add-rombar-to-compat-properties-for-pc-0.10-and-p.patch [bz#558818]
- Resolves: bz#558818
  (rom loading)

* Wed Feb 10 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.17.el6
- kvm-Fix-QEMU_WARN_UNUSED_RESULT.patch [bz#560623]
- kvm-qcow2-Fix-error-handling-in-qcow2_grow_l1_table.patch [bz#560623]
- kvm-qcow2-Fix-error-handling-in-qcow_save_vmstate.patch [bz#560623]
- kvm-qcow2-Return-0-errno-in-get_cluster_table.patch [bz#560623]
- kvm-qcow2-Return-0-errno-in-qcow2_alloc_cluster_offset.patch [bz#560623]
- kvm-block-Return-original-error-codes-in-bdrv_pread-writ.patch [bz#560623]
- kvm-qcow2-Fix-error-handling-in-grow_refcount_table.patch [bz#560623]
- kvm-qcow2-Improve-error-handling-in-update_refcount.patch [bz#560623]
- kvm-qcow2-Allow-updating-no-refcounts.patch [bz#560623]
- kvm-qcow2-Don-t-ignore-update_refcount-return-value.patch [bz#560623]
- kvm-qcow2-Don-t-ignore-qcow2_alloc_clusters-return-value.patch [bz#560623]
- kvm-net-Make-inet_strfamily-public.patch [bz#562181]
- kvm-net-inet_strfamily-Better-unknown-family-report.patch [bz#562181]
- kvm-vnc-Use-inet_strfamily.patch [bz#562181]
- Resolves: bz#560623
  (error codes aren't always propagated up through the block layer (e.g. -ENOSPC))
- Resolves: bz#562181
  (Small VNC related cleanup)

* Mon Feb 08 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.16.el6
- Move /usr/bin/qemu-kvm to /usr/libexec/qemu-kvm
- Resolves: bz#560651

* Wed Feb 03 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.15.el6
- kvm-VNC-Use-enabled-key-instead-of-status.patch [bz#549759]
- kvm-VNC-Make-auth-key-mandatory.patch [bz#549759]
- kvm-VNC-Rename-client-s-username-key.patch [bz#549759]
- kvm-VNC-Add-family-key.patch [bz#549759]
- kvm-VNC-Cache-client-info-at-connection-time.patch [bz#549759]
- kvm-QMP-Introduce-VNC_CONNECTED-event.patch [bz#549759]
- kvm-QMP-Introduce-VNC_DISCONNECTED-event.patch [bz#549759]
- kvm-QMP-Introduce-VNC_INITIALIZED-event.patch [bz#549759]
- kvm-block-avoid-creating-too-large-iovecs-in-multiwrite_.patch [bz#558730]
- Resolves: bz#549759
  (A QMP event notification on VNC client connect/disconnect events)
- Resolves: bz#558730
  (qemu may create too large iovecs for the kernel)

* Thu Jan 28 2010 Glauber Costa <glommer@redhat.com> - qemu-kvm-0.12.1.2-2.14.el6
- kvm-MCE-Fix-bug-of-IA32_MCG_STATUS-after-system-reset.patch [bz#558416]
- kvm-Fix-CPU-topology-initialization.patch [bz#558432]
- kvm-loader-more-ignores-for-rom-intended-to-be-loaded-by.patch [bz#558467]
- kvm-pc-add-machine-type-for-0.12.patch [bz#558470]
- kvm-virtio-console-Rename-virtio-serial.c-back-to-virtio.patch [bz#559089]
- kvm-virtio-serial-bus-Fix-bus-initialisation-and-allow-f.patch [bz#559503]
- Resolves: bz#558416
  (Machine check exception injected into qemu reinjected after every reset)
- Resolves: bz#558432
  (CPU topology not taking effect)
- Resolves: bz#558467
  (roms potentially loaded twice)
- Resolves: bz#558470
  (Incorrect machine types)
- Resolves: bz#559089
  (Rename virtio-serial.c to virtio-console.c as is upstream.)
- Resolves: bz#559503
  (virtio-serial: fix multiple devices intialisation)

* Wed Jan 27 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.13.el6
- kvm-reduce-number-of-reinjects-on-ACK.patch [bz#557435]
- kvm-Add-missing-newline-at-the-end-of-options-list.patch [bz#558412]
- kvm-vnc-Fix-artifacts-in-hextile-decoding.patch [bz#558414]
- kvm-QMP-Drop-wrong-assert.patch [bz#558415]
- kvm-vmware_vga-Check-cursor-dimensions-passed-from-guest.patch [bz#558435]
- kvm-virtio-pci-thinko-fix.patch [bz#558438]
- kvm-QMP-Don-t-free-async-event-s-data.patch [bz#558465]
- kvm-vnc_refresh-return-if-vd-timer-is-NULL.patch [bz#558466]
- kvm-osdep.c-Fix-accept4-fallback.patch [bz#558477]
- kvm-QMP-Emit-asynchronous-events-on-all-QMP-monitors.patch [bz#558619]
- kvm-vnc_refresh-calling-vnc_update_client-might-free-vs.patch [bz#558846]
- Resolves: bz#557435
  (KVM: WIN7-32bit blue screen (IMAGE_NAME:  ntkrnlmp.exe).)
- Resolves: bz#558412
  (-help output not terminated by newline)
- Resolves: bz#558414
  (Artifacts in hextile decoding)
- Resolves: bz#558415
  (Assert triggers on qmp commands returning lists)
- Resolves: bz#558435
  (vmware-svga buffer overflow copying cursor data)
- Resolves: bz#558438
  (virtio status bits corrupted if guest deasserts bus mastering bit)
- Resolves: bz#558465
  (Double-free of qmp async messages)
- Resolves: bz#558466
  (Possible segfault on vnc client disconnect)
- Resolves: bz#558477
  (Incorrect handling of EINVAL from accept4())
- Resolves: bz#558619
  (QMP: Emit asynchronous events on all QMP monitors)
- Resolves: bz#558846
  (fix use-after-free in vnc code)

* Fri Jan 22 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.12.el6
- kvm-virtio-serial-bus-Remove-guest-buffer-caching-and-th.patch [bz#543825]
- kvm-virtio-serial-Make-sure-we-don-t-crash-when-host-por.patch [bz#543825]
- kvm-virtio-serial-Use-MSI-vectors-for-port-virtqueues.patch [bz#543825]
- kvm-virtio-serial-bus-Match-upstream-whitespace.patch [bz#543825]
- Resolves: bz#543825
  ([RFE] Backport virtio-serial device to qemu)

* Mon Jan 18 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.11.el6
- kvm-block-Introduce-BDRV_O_NO_BACKING.patch [bz#556459]
- kvm-block-Add-bdrv_change_backing_file.patch [bz#556459]
- kvm-qemu-img-rebase.patch [bz#556459]
- Resolves: bz#556459
  (RFE - In-place backing file format change)

* Mon Jan 18 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.10.el6
- Conflicts with older vdsm version, that needs vvfat support
- Related: bz#555336

* Fri Jan 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.9.el6
- Disable -Werror again, as there are still warnings on the build
- Related: bz#555336
  (Remove unneeded features)

* Fri Jan 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.8.el6
- Require libaio-devel for build
- Related: bz#555336
  (Remove unneeded features)

* Fri Jan 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.7.el6
- Disable vvfat support
- Resolves: bz#555336
  (Remove unneeded features)

* Fri Jan 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.6.el6
- Fix misapply of virtio patches
- Related: bz#543825

* Fri Jan 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.5.el6
- Remove unneeded/unsupported features: [bz#555336]
  - make default options explicit
  - remove sdl support
  - remove sb16 emulation
  - remove oss support
  - remove curses support
  - disable curl support
  - disable bluez support
  - enable -Werror
  - limit block drivers support
  - add host_cdrom block device
- Resolves: bz#555336
  (Remove unneeded features)

* Fri Jan 15 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.4.el6
- kvm-virtio-Remove-duplicate-macro-definition-for-max.-vi.patch [bz#543825]
- kvm-virtio-console-qdev-conversion-new-virtio-serial-bus.patch [bz#543825]
- kvm-virtio-serial-bus-Maintain-guest-and-host-port-open-.patch [bz#543825]
- kvm-virtio-serial-bus-Add-a-port-name-property-for-port-.patch [bz#543825]
- kvm-virtio-serial-bus-Add-support-for-buffering-guest-ou.patch [bz#543825]
- kvm-virtio-serial-bus-Add-ability-to-hot-unplug-ports.patch [bz#543825]
- kvm-virtio-serial-Add-a-virtserialport-device-for-generi.patch [bz#543825]
- kvm-Move-virtio-serial-to-Makefile.hw.patch [bz#543825]
- Resolves: bz#543825
  ([RFE] Backport virtio-serial device to qemu)

* Tue Jan 12 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.3.el6
- Use seabios instead of bochs-bios
- Resolves: bz#553732

* Tue Jan 12 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.2.el6
- Build only on x86_64
- Resolves: bz#538039

* Thu Jan 07 2010 Eduardo Habkost <ehabkost@redhat.com> - qemu-kvm-0.12.1.2-2.1.el6
- Rebasing to 0.12.1.2-2.fc13
- Resolves: bz#553271

* Tue Dec 08 2009 Dennis Gregorovic <dgregor@redhat.com> - 2:0.11.0-7.1
- Rebuilt for RHEL 6

* Mon Oct 19 2009 Mark McLoughlin <markmc@redhat.com> - 2:0.11.0-7.el6
- Initial RHEL6 qemu-kvm package
