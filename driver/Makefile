# SPDX-License-Identifier: GPL-2.0-only
#
# Build the Dongtian control module against an externally supplied RISC-V
# Linux kernel tree.  Nothing here downloads or installs a kernel/toolchain.

obj-m := dongtian.o

ccflags-y += -I$(src)/../include

KDIR ?= /lib/modules/$(shell uname -r)/build
ARCH ?= riscv
CROSS_COMPILE ?=

.PHONY: all modules modules_install clean help

all: modules

modules:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) \
		CROSS_COMPILE=$(CROSS_COMPILE) modules

modules_install:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) \
		CROSS_COMPILE=$(CROSS_COMPILE) modules_install

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=$(ARCH) \
		CROSS_COMPILE=$(CROSS_COMPILE) clean

help:
	@echo "Usage: make -C driver KDIR=/path/to/linux ARCH=riscv CROSS_COMPILE=riscv64-linux-gnu-"
	@echo "Targets: all (default), modules, modules_install, clean"
	@echo "KDIR must point at a configured RISC-V Linux 6.12 build tree."
