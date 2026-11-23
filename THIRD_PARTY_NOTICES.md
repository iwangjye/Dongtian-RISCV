# Third-party notices

## Linux and Debian kernel materials

The Linux kernel is a separate upstream/Debian work. The repository does not distribute its Image binary. Users explicitly acquire the pinned Debian kernel package with `scripts/fetch-kernel.py` or provide a matching local `.deb`. Linux is not relicensed under the license selected for Dongtian's own code.

Retain and consult `images/debian-kernel-copyright.txt`, `images/kernel.config`, `images/kernel-info.json`, `images/linux_6.12.117-1.dsc`, and the kernel license material in `LICENSES/`. The metadata and Debian source descriptor identify corresponding source archives and their hashes. These files preserve third-party attribution and source information; they do not replace the upstream licensing terms.

## QEMU device-tree data

The device-tree sources describe the emulated `virt` hardware. They derive from QEMU-generated hardware-description data and are narrowed for this experiment's memory and device layout. This is generated descriptive data, not a copy of QEMU's implementation. QEMU is an external dependency and is not distributed here.

## External tools

Python, QEMU, GCC/binutils or LLVM/Clang/LLD, and the device-tree compiler are installed separately and retain their respective licenses. No ownership of those projects is claimed by this repository.
