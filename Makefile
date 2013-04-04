# Makefile for QEMU.

# useful for passing ' ' and ',' into Makefile functional calls,
# as these characters cannot be passed otherwise
_empty :=  
_space := $(_empty) $(_empty)
_comma := ,

qapi-dir := qapi-generated
GENERATED_HEADERS = config-host.h trace.h config-all-devices.h
ifeq ($(TRACE_BACKEND),dtrace)
GENERATED_HEADERS += trace-dtrace.h
endif
GENERATED_HEADERS += qmp-commands.h

ifneq ($(wildcard config-host.mak),)
# Put the all: rule here so that config-host.mak can contain dependencies.
all: build-all
include config-host.mak
include $(SRC_PATH)/rules.mak
config-host.mak: configure
	@echo $@ is out-of-date, running configure
	@sed -n "/.*Configured with/s/[^:]*: //p" $@ | sh
else
config-host.mak:
	@echo "Please call configure before running make!"
	@exit 1
endif

ifeq ($(CONFIG_LIVE_SNAPSHOTS),y)
rhel_rhev_qmp_commands.h = rhev-qmp-commands.h
GENERATED_HEADERS += rhev-qmp-commands.h rhev-qapi-types.h rhev-qapi-visit.h
GENERATED_SOURCES += rhev-qmp-marshal.c rhev-qapi-types.c rhev-qapi-visit.c
else
rhel_rhev_qmp_commands.h = rhel-qmp-commands.h
GENERATED_HEADERS += rhel-qmp-commands.h rhel-qapi-types.h rhel-qapi-visit.h
GENERATED_SOURCES += rhel-qmp-marshal.c rhel-qapi-types.c rhel-qapi-visit.c
endif

# Don't try to regenerate Makefile or configure
# We don't generate any of them
Makefile: ;
configure: ;

.PHONY: all clean cscope distclean dvi html info install install-doc \
	recurse-all speed tar tarbin test build-all

VPATH=$(SRC_PATH):$(SRC_PATH)/hw

LIBS+=-lz $(LIBS_TOOLS)

ifdef BUILD_DOCS
DOCS=qemu-doc.html qemu-tech.html qemu.1 qemu-img.1 qemu-nbd.8 QMP/qmp-commands.txt
else
DOCS=
endif

SUBDIR_MAKEFLAGS=$(if $(V),,--no-print-directory)
SUBDIR_DEVICES_MAK=$(patsubst %, %/config-devices.mak, $(TARGET_DIRS))

config-all-devices.mak: $(SUBDIR_DEVICES_MAK)
	$(call quiet-command,cat $(SUBDIR_DEVICES_MAK) | grep =y | sort -u > $@,"  GEN   $@")

%/config-devices.mak: default-configs/%.mak
	$(call quiet-command,cat $< > $@.tmp, "  GEN   $@")
	@if test -f $@ ; then \
	  echo "WARNING: $@ out of date." ;\
	  echo "Run \"make defconfig\" to regenerate." ; \
	  rm $@.tmp ; \
	 else \
	  mv $@.tmp $@ ; \
	 fi

defconfig:
	rm -f config-all-devices.mak $(SUBDIR_DEVICES_MAK)

-include config-all-devices.mak

build-all: $(DOCS) $(TOOLS) recurse-all

config-host.h: config-host.h-timestamp
config-host.h-timestamp: config-host.mak

config-all-devices.h: config-all-devices.h-timestamp
config-all-devices.h-timestamp: config-all-devices.mak

SUBDIR_RULES=$(patsubst %,subdir-%, $(TARGET_DIRS))

ifeq ($(KVM_KMOD),yes)

.PHONEY: kvm-kmod

all: kvm-kmod

kvm-kmod:
	$(call quiet-command,$(MAKE) $(SUBDIR_MAKEFLAGS) -C kvm/kernel V="$(V)" )


endif

subdir-%: $(GENERATED_HEADERS)
	$(call quiet-command,$(MAKE) $(SUBDIR_MAKEFLAGS) -C $* V="$(V)" TARGET_DIR="$*/" all,)

include $(SRC_PATH)/Makefile.objs

$(common-obj-y): $(GENERATED_HEADERS)
$(filter %-softmmu,$(SUBDIR_RULES)): $(common-obj-y)

$(filter %-user,$(SUBDIR_RULES)): libuser.a

libuser.a: $(GENERATED_HEADERS)
	$(call quiet-command,$(MAKE) $(SUBDIR_MAKEFLAGS) -C libuser V="$(V)" TARGET_DIR="libuser/" all,)

ROMSUBDIR_RULES=$(patsubst %,romsubdir-%, $(ROMS))
romsubdir-%:
	$(call quiet-command,$(MAKE) $(SUBDIR_MAKEFLAGS) -C pc-bios/$* V="$(V)" TARGET_DIR="$*/",)

ALL_SUBDIRS=$(TARGET_DIRS) $(patsubst %,pc-bios/%, $(ROMS))

recurse-all: $(SUBDIR_RULES) $(ROMSUBDIR_RULES)

audio/audio.o audio/fmodaudio.o: QEMU_CFLAGS += $(FMOD_CFLAGS)
QEMU_CFLAGS+=$(CURL_CFLAGS)

QEMU_CFLAGS+=$(GLIB_CFLAGS)

cocoa.o: cocoa.m

keymaps.o: keymaps.c keymaps.h

sdl_zoom.o: sdl_zoom.c sdl_zoom.h sdl_zoom_template.h

sdl.o: sdl.c keymaps.h sdl_keysym.h sdl_zoom.h

sdl.o audio/sdlaudio.o sdl_zoom.o baum.o: QEMU_CFLAGS += $(SDL_CFLAGS)

acl.o: acl.h acl.c

vnc.h: vnc-tls.h vnc-auth-vencrypt.h vnc-auth-sasl.h keymaps.h

vnc.o: vnc.c vnc.h vnc_keysym.h vnchextile.h d3des.c d3des.h acl.h

vnc.o: QEMU_CFLAGS += $(VNC_TLS_CFLAGS)

vnc-tls.o: vnc-tls.c vnc.h

vnc-auth-vencrypt.o: vnc-auth-vencrypt.c vnc.h

vnc-auth-sasl.o: vnc-auth-sasl.c vnc.h

curses.o: curses.c keymaps.h curses_keys.h

bt-host.o: QEMU_CFLAGS += $(BLUEZ_CFLAGS)

ifeq ($(TRACE_BACKEND),dtrace)
trace.h: trace.h-timestamp trace-dtrace.h
else
trace.h: trace.h-timestamp
endif
trace.h-timestamp: $(SRC_PATH)/trace-events config-host.mak
	$(call quiet-command,sh $(SRC_PATH)/tracetool --$(TRACE_BACKEND) -h < $< > $@,"  GEN   trace.h")
	@cmp -s $@ trace.h || cp $@ trace.h

trace.c: trace.c-timestamp
trace.c-timestamp: $(SRC_PATH)/trace-events config-host.mak
	$(call quiet-command,sh $(SRC_PATH)/tracetool --$(TRACE_BACKEND) -c < $< > $@,"  GEN   trace.c")
	@cmp -s $@ trace.c || cp $@ trace.c

trace.o: trace.c $(GENERATED_HEADERS)

trace-dtrace.h: trace-dtrace.dtrace
	$(call quiet-command,dtrace -o $@ -h -s $<, "  GEN   trace-dtrace.h")

# Normal practice is to name DTrace probe file with a '.d' extension
# but that gets picked up by QEMU's Makefile as an external dependancy
# rule file. So we use '.dtrace' instead
trace-dtrace.dtrace: trace-dtrace.dtrace-timestamp
trace-dtrace.dtrace-timestamp: $(SRC_PATH)/trace-events config-host.mak
	$(call quiet-command,sh $(SRC_PATH)/tracetool --$(TRACE_BACKEND) -d < $< > $@,"  GEN   trace-dtrace.dtrace")
	@cmp -s $@ trace-dtrace.dtrace || cp $@ trace-dtrace.dtrace

trace-dtrace.o: trace-dtrace.dtrace $(GENERATED_HEADERS)
	$(call quiet-command,dtrace -o $@ -G -s $<, "  GEN trace-dtrace.o")

######################################################################

qemu-img.o: qemu-img-cmds.h
qemu-img.o qemu-tool.o qemu-nbd.o qemu-io.o: $(GENERATED_HEADERS)

TOOLS_OBJ=qemu-tool.o qerror.o $(shared-obj-y) $(trace-obj-y)

qemu-img$(EXESUF): qemu-img.o $(TOOLS_OBJ)

qemu-nbd$(EXESUF): qemu-nbd.o $(TOOLS_OBJ)

qemu-io$(EXESUF): qemu-io.o cmd.o $(TOOLS_OBJ)

qemu-img-cmds.h: $(SRC_PATH)/qemu-img-cmds.hx
	$(call quiet-command,sh $(SRC_PATH)/hxtool -h < $< > $@,"  GEN   $@")

check-qint: check-qint.o qint.o qemu-malloc.o qemu-tool.o
check-qstring: check-qstring.o qstring.o qemu-malloc.o qemu-tool.o
check-qdict: check-qdict.o qdict.o qfloat.o qint.o qstring.o qbool.o qemu-malloc.o qlist.o qemu-tool.o
check-qlist: check-qlist.o qlist.o qint.o qemu-malloc.o qemu-tool.o
check-qfloat: check-qfloat.o qfloat.o qemu-malloc.o qemu-tool.o
check-qjson: check-qjson.o qfloat.o qint.o qdict.o qstring.o qlist.o qbool.o qjson.o json-streamer.o json-lexer.o json-parser.o qemu-malloc.o error.o qerror.o qemu-error.o qemu-tool.o

$(qapi-obj-y): $(GENERATED_HEADERS) 
qapi-dir := qapi-generated
$(qga-obj-y): $(qapi-dir)/qga-qapi-types.h $(qapi-dir)/qga-qapi-visit.h $(qapi-dir)/qga-qmp-commands.h
test-visitor.o test-qmp-commands.o qemu-ga$(EXESUF): QEMU_CFLAGS += -I $(qapi-dir)
qemu-ga$(EXESUF): LIBS = $(LIBS_QGA)

gen-out-type = $(subst .,-,$(suffix $@))

$(qapi-dir)/test-qapi-types.c $(qapi-dir)/test-qapi-types.h :\
$(SRC_PATH)/qapi-schema-test.json $(SRC_PATH)/scripts/qapi-types.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-types.py $(gen-out-type) -o "$(qapi-dir)" -p "test-" < $<, "  GEN   $@")
$(qapi-dir)/test-qapi-visit.c $(qapi-dir)/test-qapi-visit.h :\
$(SRC_PATH)/qapi-schema-test.json $(SRC_PATH)/scripts/qapi-visit.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-visit.py $(gen-out-type) -o "$(qapi-dir)" -p "test-" < $<, "  GEN   $@")
$(qapi-dir)/test-qmp-commands.h $(qapi-dir)/test-qmp-marshal.c :\
$(SRC_PATH)/qapi-schema-test.json $(SRC_PATH)/scripts/qapi-commands.py
	    $(call quiet-command,python $(SRC_PATH)/scripts/qapi-commands.py $(gen-out-type) -o "$(qapi-dir)" -p "test-" < $<, "  GEN   $@")

$(qapi-dir)/qga-qapi-types.c $(qapi-dir)/qga-qapi-types.h :\
$(SRC_PATH)/qapi-schema-guest.json $(SRC_PATH)/scripts/qapi-types.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-types.py $(gen-out-type) -o "$(qapi-dir)" -p "qga-" < $<, "  GEN   $@")
$(qapi-dir)/qga-qapi-visit.c $(qapi-dir)/qga-qapi-visit.h :\
$(SRC_PATH)/qapi-schema-guest.json $(SRC_PATH)/scripts/qapi-visit.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-visit.py $(gen-out-type) -o "$(qapi-dir)" -p "qga-" < $<, "  GEN   $@")
$(qapi-dir)/qga-qmp-commands.h $(qapi-dir)/qga-qmp-marshal.c :\
$(SRC_PATH)/qapi-schema-guest.json $(SRC_PATH)/scripts/qapi-commands.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-commands.py $(gen-out-type) -o "$(qapi-dir)" -p "qga-" < $<, "  GEN   $@")

rhev-qapi-types.c rhev-qapi-types.h :\
qapi-schema-rhev.json $(SRC_PATH)/scripts/qapi-types.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-types.py $(gen-out-type) -o "." -p "rhev-" < $<, "  GEN   $@")
rhev-qapi-visit.c rhev-qapi-visit.h :\
qapi-schema-rhev.json $(SRC_PATH)/scripts/qapi-visit.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-visit.py $(gen-out-type) -o "." -p "rhev-" < $<, "  GEN   $@")
rhev-qmp-commands.h rhev-qmp-marshal.c :\
qapi-schema-rhev.json $(SRC_PATH)/scripts/qapi-commands.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-commands.py $(gen-out-type) -m -o "." -p "rhev-" < $<, "  GEN   $@")

# if there are multiple config items to be RHEV-only, simply add it to
# RHEV_CONFIGS, like so: RHEV_CONFIGS = CONFIG_LIVE_SNAPSHOTS CONFIG_SOME_FEATURE
RHEV_CONFIGS = CONFIG_LIVE_SNAPSHOTS
# Turn $(RHEV_CONFIGS) into a regex with logical OR, and whole word matching
RHEV_ONLY_CONFIG_ITEMS = (\b$(subst $(_space),\b|\b,$(strip $(RHEV_CONFIGS)))\b)

GENERATED_JSON_FILES = $(addprefix $(SRC_PATH)/, qapi-schema-rhel.json qapi-schema-rhev.json)

qapi-schema-rhev.json: $(SRC_PATH)/qapi-schema.json
	-@echo "# THIS FILE IS AUTOMATICALLY GENERATED, DO NOT MODIFY" > $@
	-@echo "#" >> $@
	$(call quiet-command,sed -r "/^#ifdef +$(RHEV_ONLY_CONFIG_ITEMS)/d;/^#endif/d" $< >> $@, "  GEN   $@")

qapi-schema-rhel.json: $(SRC_PATH)/qapi-schema.json
	-@echo "# THIS FILE IS AUTOMATICALLY GENERATED, DO NOT MODIFY" > $@
	-@echo "#" >> $@
	$(call quiet-command,sed -r "/^#ifdef +$(RHEV_ONLY_CONFIG_ITEMS)/$(_comma)/^#endif/d" $< >> $@, "  GEN   $@")

rhel-qapi-types.c rhel-qapi-types.h :\
qapi-schema-rhel.json $(SRC_PATH)/scripts/qapi-types.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-types.py $(gen-out-type) -o "." -p "rhel-" < $<, "  GEN   $@")
rhel-qapi-visit.c rhel-qapi-visit.h :\
qapi-schema-rhel.json $(SRC_PATH)/scripts/qapi-visit.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-visit.py $(gen-out-type) -o "." -p "rhel-" < $<, "  GEN   $@")
rhel-qmp-commands.h rhel-qmp-marshal.c :\
qapi-schema-rhel.json $(SRC_PATH)/scripts/qapi-commands.py
	$(call quiet-command,python $(SRC_PATH)/scripts/qapi-commands.py $(gen-out-type) -m -o "." -p "rhel-" < $<, "  GEN   $@")

define QMP_COMMANDS_H
/* THIS FILE IS AUTOMATICALLY GENERATED, DO NOT MODIFY */

#ifndef QMP_COMMANDS_H
#define QMP_COMMANDS_H

#include "$(rhel_rhev_qmp_commands.h)"


#endif
endef

export QMP_COMMANDS_H
qmp-commands.h: $(rhel_rhev_qmp_commands.h)
	$(call quiet-command, echo "$$QMP_COMMANDS_H" > $@, "  GEN   $@")


test-visitor.o: $(addprefix $(qapi-dir)/, test-qapi-types.c test-qapi-types.h test-qapi-visit.c test-qapi-visit.h) $(qapi-obj-y)
test-visitor: test-visitor.o qfloat.o qint.o qdict.o qstring.o qlist.o qbool.o $(qapi-obj-y) error.o osdep.o qemu-malloc.o $(oslib-obj-y) qjson.o json-streamer.o json-lexer.o json-parser.o qerror.o qemu-error.o qemu-tool.o $(qapi-dir)/test-qapi-visit.o $(qapi-dir)/test-qapi-types.o

test-qmp-commands.o: $(addprefix $(qapi-dir)/, test-qapi-types.c test-qapi-types.h test-qapi-visit.c test-qapi-visit.h test-qmp-marshal.c test-qmp-commands.h) $(qapi-obj-y)
test-qmp-commands: test-qmp-commands.o qfloat.o qint.o qdict.o qstring.o qlist.o qbool.o $(qapi-obj-y) error.o osdep.o qemu-malloc.o $(oslib-obj-y) qjson.o json-streamer.o json-lexer.o json-parser.o qerror.o qemu-error.o qemu-tool.o $(qapi-dir)/test-qapi-visit.o $(qapi-dir)/test-qapi-types.o $(qapi-dir)/test-qmp-marshal.o module.o

QGALIB_GEN=$(addprefix $(qapi-dir)/, qga-qapi-types.c qga-qapi-types.h qga-qapi-visit.c qga-qmp-marshal.c)
$(QGALIB_GEN): $(GENERATED_HEADERS)
$(QGALIB) qemu-ga.o: $(QGALIB_GEN) $(qapi-obj-y)


qemu-ga$(EXESUF): qemu-ga.o $(qga-obj-y) $(qapi-obj-y) $(trace-obj-y) $(qobject-obj-y) $(version-obj-y) $(addprefix $(qapi-dir)/, qga-qapi-visit.o qga-qapi-types.o qga-qmp-marshal.o)

QEMULIBS=libhw32 libhw64 libuser

clean:
# avoid old build problems by removing potentially incorrect old files
	rm -f config.mak op-i386.h opc-i386.h gen-op-i386.h op-arm.h opc-arm.h gen-op-arm.h
	rm -f *.o *.d *.a $(TOOLS) qemu-ga TAGS cscope.* *.pod *~ */*~
	rm -f slirp/*.o slirp/*.d audio/*.o audio/*.d block/*.o block/*.d net/*.o net/*.d ui/*.o ui/*.d qapi/*.o qapi/*.d qga/*.o qga/*.d
	rm -f qemu-img-cmds.h
	rm -f trace.c trace.h trace.c-timestamp trace.h-timestamp
	rm -f trace-dtrace.dtrace trace-dtrace.dtrace-timestamp
	rm -f trace-dtrace.h trace-dtrace.h-timestamp
	rm -rf $(qapi-dir)
	rm -rf $(GENERATED_HEADERS)
	rm -rf $(GENERATED_SOURCES)
	rm -rf $(GENERATED_JSON_FILES)
	$(MAKE) -C tests clean
	for d in $(ALL_SUBDIRS) $(QEMULIBS) libcacard; do \
	if test -d $$d; then $(MAKE) -C $$d $@ || exit 1; fi; \
        done

distclean: clean
	rm -f config-host.mak config-host.h* config-host.ld $(DOCS) qemu-options.texi qemu-img-cmds.texi qemu-monitor.texi
	rm -f config-all-devices.mak config-all-devices.h*
	rm -f roms/seabios/config.mak roms/vgabios/config.mak
	rm -f qemu-{doc,tech}.{info,aux,cp,dvi,fn,info,ky,log,pg,toc,tp,vr}
	for d in $(TARGET_DIRS) $(QEMULIBS); do \
	rm -rf $$d || exit 1 ; \
        done

KEYMAPS=da     en-gb  et  fr     fr-ch  is  lt  modifiers  no  pt-br  sv \
ar      de     en-us  fi  fr-be  hr     it  lv  nl         pl  ru     th \
common  de-ch  es     fo  fr-ca  hu     ja  mk  nl-be      pt  sl     tr

ifdef INSTALL_BLOBS
BLOBS=bios.bin vgabios.bin vgabios-cirrus.bin ppc_rom.bin \
video.x openbios-sparc32 openbios-sparc64 openbios-ppc \
pxe-e1000.bin pxe-i82559er.bin \
pxe-ne2k_pci.bin pxe-pcnet.bin \
pxe-rtl8139.bin pxe-virtio.bin \
bamboo.dtb petalogix-s3adsp1800.dtb \
multiboot.bin linuxboot.bin
BLOBS += extboot.bin
BLOBS += vapic.bin
else
BLOBS=
endif

install-doc: $(DOCS)
	$(INSTALL_DIR) "$(DESTDIR)$(docdir)"
	$(INSTALL_DATA) qemu-doc.html  qemu-tech.html "$(DESTDIR)$(docdir)"
ifdef CONFIG_POSIX
	$(INSTALL_DIR) "$(DESTDIR)$(mandir)/man1"
	$(INSTALL_DATA) qemu-img.1 "$(DESTDIR)$(mandir)/man1"
	$(INSTALL_DATA) qemu.1 "$(DESTDIR)$(mandir)/man1/qemu-kvm.1"
	$(INSTALL_DIR) "$(DESTDIR)$(mandir)/man8"
	$(INSTALL_DATA) qemu-nbd.8 "$(DESTDIR)$(mandir)/man8"
endif

install: all $(if $(BUILD_DOCS),install-doc)
	$(INSTALL_DIR) "$(DESTDIR)$(bindir)"
ifneq ($(TOOLS),)
	$(INSTALL_PROG) $(STRIP_OPT) $(TOOLS) "$(DESTDIR)$(bindir)"
endif
ifneq ($(BLOBS),)
	$(INSTALL_DIR) "$(DESTDIR)$(datadir)"
	set -e; for x in $(BLOBS); do \
	    if [ -f $(SRC_PATH)/pc-bios/$$x ];then \
		$(INSTALL_DATA) $(SRC_PATH)/pc-bios/$$x "$(DESTDIR)$(datadir)"; \
	    fi \
	    ; if [ -f pc-bios/optionrom/$$x ];then \
		$(INSTALL_DATA) pc-bios/optionrom/$$x "$(DESTDIR)$(datadir)"; \
	    fi \
	done
endif
	$(INSTALL_DIR) "$(DESTDIR)$(datadir)/keymaps"
	set -e; for x in $(KEYMAPS); do \
		$(INSTALL_DATA) $(SRC_PATH)/pc-bios/keymaps/$$x "$(DESTDIR)$(datadir)/keymaps"; \
	done
	for d in $(TARGET_DIRS); do \
	$(MAKE) -C $$d $@ || exit 1 ; \
        done
ifeq ($(KVM_KMOD),yes)
	$(MAKE) -C kvm/kernel $@
endif

# various test targets
test speed: all
	$(MAKE) -C tests $@

.PHONY: TAGS
TAGS:
	find "$(SRC_PATH)" -name '*.[hc]' -print0 | xargs -0 etags

cscope:
	rm -f ./cscope.*
	find . -name "*.[ch]" -print | sed 's,^\./,,' > ./cscope.files
	cscope -b

# documentation
%.html: %.texi
	$(call quiet-command,texi2html -I=. -monolithic -number $<,"  GEN   $@")

%.info: %.texi
	$(call quiet-command,makeinfo -I . $< -o $@,"  GEN   $@")

%.dvi: %.texi
	$(call quiet-command,texi2dvi -I . $<,"  GEN   $@")

qemu-options.texi: $(SRC_PATH)/qemu-options.hx
	$(call quiet-command,sh $(SRC_PATH)/hxtool -t < $< > $@,"  GEN   $@")

qemu-monitor.texi: $(SRC_PATH)/qemu-monitor.hx
	$(call quiet-command,sh $(SRC_PATH)/hxtool -t < $< > $@,"  GEN   $@")

QMP/qmp-commands.txt: $(SRC_PATH)/qemu-monitor.hx
	$(call quiet-command,sh $(SRC_PATH)/hxtool -q < $< > $@,"  GEN   $@")

qemu-img-cmds.texi: $(SRC_PATH)/qemu-img-cmds.hx
	$(call quiet-command,sh $(SRC_PATH)/hxtool -t < $< > $@,"  GEN   $@")

qemu.1: qemu-doc.texi qemu-options.texi qemu-monitor.texi
	$(call quiet-command, \
	  perl -Ww -- $(SRC_PATH)/texi2pod.pl $< qemu.pod && \
	  pod2man --section=1 --center=" " --release=" " qemu.pod > $@, \
	  "  GEN   $@")

qemu-img.1: qemu-img.texi qemu-img-cmds.texi
	$(call quiet-command, \
	  perl -Ww -- $(SRC_PATH)/texi2pod.pl $< qemu-img.pod && \
	  pod2man --section=1 --center=" " --release=" " qemu-img.pod > $@, \
	  "  GEN   $@")

qemu-nbd.8: qemu-nbd.texi
	$(call quiet-command, \
	  perl -Ww -- $(SRC_PATH)/texi2pod.pl $< qemu-nbd.pod && \
	  pod2man --section=8 --center=" " --release=" " qemu-nbd.pod > $@, \
	  "  GEN   $@")

info: qemu-doc.info qemu-tech.info

dvi: qemu-doc.dvi qemu-tech.dvi

html: qemu-doc.html qemu-tech.html

qemu-doc.dvi qemu-doc.html qemu-doc.info: qemu-img.texi qemu-nbd.texi qemu-options.texi qemu-monitor.texi qemu-img-cmds.texi

VERSION ?= $(shell cat VERSION)
FILE = qemu-$(VERSION)

# tar release (use 'make -k tar' on a checkouted tree)
tar:
	rm -rf /tmp/$(FILE)
	cp -r . /tmp/$(FILE)
	cd /tmp && tar zcvf ~/$(FILE).tar.gz $(FILE) --exclude CVS --exclude .git --exclude .svn
	rm -rf /tmp/$(FILE)

# generate a binary distribution
tarbin:
	cd / && tar zcvf ~/qemu-$(VERSION)-$(ARCH).tar.gz \
	$(bindir)/qemu \
	$(bindir)/qemu-system-x86_64 \
	$(bindir)/qemu-system-arm \
	$(bindir)/qemu-system-cris \
	$(bindir)/qemu-system-m68k \
	$(bindir)/qemu-system-microblaze \
	$(bindir)/qemu-system-mips \
	$(bindir)/qemu-system-mipsel \
	$(bindir)/qemu-system-mips64 \
	$(bindir)/qemu-system-mips64el \
	$(bindir)/qemu-system-ppc \
	$(bindir)/qemu-system-ppcemb \
	$(bindir)/qemu-system-ppc64 \
	$(bindir)/qemu-system-sh4 \
	$(bindir)/qemu-system-sh4eb \
	$(bindir)/qemu-system-sparc \
	$(bindir)/qemu-i386 \
	$(bindir)/qemu-x86_64 \
	$(bindir)/qemu-alpha \
	$(bindir)/qemu-arm \
	$(bindir)/qemu-armeb \
	$(bindir)/qemu-cris \
	$(bindir)/qemu-m68k \
	$(bindir)/qemu-microblaze \
	$(bindir)/qemu-mips \
	$(bindir)/qemu-mipsel \
	$(bindir)/qemu-ppc \
	$(bindir)/qemu-ppc64 \
	$(bindir)/qemu-ppc64abi32 \
	$(bindir)/qemu-sh4 \
	$(bindir)/qemu-sh4eb \
	$(bindir)/qemu-sparc \
	$(bindir)/qemu-sparc64 \
	$(bindir)/qemu-sparc32plus \
	$(bindir)/qemu-img \
	$(bindir)/qemu-nbd \
	$(datadir)/bios.bin \
	$(datadir)/vgabios.bin \
	$(datadir)/vgabios-cirrus.bin \
	$(datadir)/ppc_rom.bin \
	$(datadir)/video.x \
	$(datadir)/openbios-sparc32 \
	$(datadir)/openbios-sparc64 \
	$(datadir)/openbios-ppc \
	$(datadir)/pxe-ne2k_pci.bin \
	$(datadir)/pxe-rtl8139.bin \
	$(datadir)/pxe-pcnet.bin \
	$(datadir)/pxe-e1000.bin \
	$(datadir)/extboot.bin \
	$(docdir)/qemu-doc.html \
	$(docdir)/qemu-tech.html \
	$(mandir)/man1/qemu.1 \
	$(mandir)/man1/qemu-img.1 \
	$(mandir)/man8/qemu-nbd.8

# Include automatically generated dependency files
-include $(wildcard *.d audio/*.d slirp/*.d block/*.d net/*.d ui/*.d qapi/*.d qga/*.d)
