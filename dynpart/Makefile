CC = $(CROSS_COMPILE)gcc
PKG_CONFIG = pkg-config

CFLAGS = 
LDFLAGS = 

devmapper-CFLAGS = $(shell $(PKG_CONFIG) --cflags devmapper)
devmapper-LDFLAGS = $(shell $(PKG_CONFIG) --libs devmapper)

libmd-CFLAGS = $(shell $(PKG_CONFIG) --cflags libmd)
libmd-LDFLAGS = $(shell $(PKG_CONFIG) --libs libmd)

blkid-CFLAGS = $(shell $(PKG_CONFIG) --cflags blkid)
blkid-LDFLAGS = $(shell $(PKG_CONFIG) --libs blkid)

CONFIG_DEFS := 

ifeq ($(USERSPACE), 1)
CONFIG_DEFS += -DUSERSPACE
endif

.PHONY += all
all: make-dynpart-mappings


clean:
	rm -f make-dynpart-mappings

make-dynpart-mappings: main.c 3rdparty/metadata_format.h
	$(CC) -o make-dynpart-mappings main.c $(CFLAGS) $(LDFLAGS) $(CONFIG_DEFS) $(devmapper-CFLAGS) $(devmapper-LDFLAGS) $(libmd-CFLAGS) $(libmd-LDFLAGS) $(blkid-CFLAGS) $(blkid-LDFLAGS) -I3rdparty
