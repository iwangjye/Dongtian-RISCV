# Component licenses and provenance

## Dongtian code

Original monitor, handoff extension, management command, scripts, and documentation use Apache-2.0. The small Linux control module and its Makefile use GPL-2.0-only, as marked in their SPDX headers; the GPL text is in `LICENSES/GPL-2.0.txt`. The shared ABI contains fixed protocol declarations. The driver is a reduced ioctl/SBI control implementation rather than a copy of an entire historical runtime.

## OpenSBI

OpenSBI 1.7 is acquired separately from the official repository at the exact commit and SHA-256 pin in `dependencies/manifest.json`. Upstream keeps its BSD-2-Clause license and notices; `LICENSES/OpenSBI-BSD-2-Clause.txt` retains the upstream license text. Preparation copies the local extension into the downloaded tree and explicitly adds its registration to the OpenSBI objects list. The extension is marked Apache-2.0; upstream files retain their terms.

## Linux and Debian

The repository does not distribute the Linux Image, module headers, or kernel build-helper binaries. Explicit preparation commands acquire pinned Debian packages. Their upstream terms remain in effect. Kernel version/source URLs, copyright, configuration, and source descriptor are retained in `images/`; matching header/helper pins are in `dependencies/manifest.json`. The local module build does not modify or rebuild the Linux kernel.

## QEMU and external tools

Device-tree templates derive from QEMU-generated virt hardware descriptions and are adapted for this experiment. QEMU implementation code, GNU/LLVM toolchains, Python, make, and dtc are external dependencies and retain their own terms.
