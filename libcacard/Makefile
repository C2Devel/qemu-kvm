-include ../config-host.mak
-include $(SRC_PATH)/Makefile.objs
-include $(SRC_PATH)/rules.mak

# TODO: duplicate from Makefile, to be removed once Makefile.objs lands.
libcacard-y = cac.o event.o vcard.o vreader.o vcard_emul_nss.o \
              vcard_emul_type.o card_7816.o

VPATH=$(SRC_PATH):$(SRC_PATH)/hw:$(SRC_PATH)/libcacard

QEMU_OBJS=$(addprefix ../, $(oslib-obj-y) $(trace-obj-y) qemu-malloc.o qemu-thread.o osdep.o)

QEMU_CFLAGS+=-I../

QEMU_CFLAGS+=$(GLIB_CFLAGS)

vscclient: $(libcacard-y) $(QEMU_OBJS) vscclient.o
	$(call quiet-command,$(CC) $(libcacard_libs) $(LIBS) -lrt -o $@ $^,"  LINK  $(TARGET_DIR)$@")

all: vscclient

clean:
	rm -f *.o */*.o *.d */*.d *.a */*.a *~ */*~ vscclient
