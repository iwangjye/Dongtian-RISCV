# Reproducing the OpenSBI and driver runtime

## Inputs

The expanded path targets x86_64 Linux and Python 3.12+. It needs GNU make, a native C compiler for OpenSBI build helpers, `dtc`, a RISC-V GNU compiler/binutils prefix, and QEMU system emulation with H-extension support. The OpenSBI link requires PIE support. `--cross-compile riscv64-linux-gnu-` selects a standard Linux-target toolchain; a custom complete GNU prefix can also be supplied.

The dependency manifest pins OpenSBI 1.7, commit `a32a91069119e7a5aa31e6bc51d5e00860be3d80`, plus Debian Linux 6.12.117-1 common headers, RISC-V generated headers/symbol versions, and x86_64 kernel build helpers. The kernel Image pin remains in `images/kernel-info.json`. The repository distributes source and metadata rather than a Linux binary, kernel headers, or third-party tool binaries.

## Environment check and complete demo

Check the full build environment before starting:

```sh
python3 -B scripts/check-env.py
python3 -B scripts/demo.py --output ../dongtian-demo
```

The full check covers x86_64 Linux, Python 3.12+, native GCC, make, dtc, QEMU, and the complete GNU RISC-V tool prefix, including an actual PIE link probe. Select non-default tools with `--cross-compile PREFIX`, `--dtc PATH`, and `--qemu PATH`.

The demo verifies source inputs, fetches a missing pinned kernel Image, prepares missing dependencies, builds, and runs automatic acceptance. Its output directory must be new and outside the checkout. It may download fixed third-party packages but never installs software. `demo-receipt.json` connects the step results and runtime receipt; inspect it alongside the per-step logs.

```sh
# Reuse a prepared dependency tree; build and run in a fresh output directory.
python3 -B scripts/demo.py --deps ../dongtian-deps --output ../dongtian-demo
# Reuse the build from a completed demo; artifact hashes are still checked.
python3 -B scripts/demo.py --build ../dongtian-demo/build --output ../dongtian-again
# Connect the terminal to the control console, or exercise the denial case.
python3 -B scripts/demo.py --build ../dongtian-demo/build --output ../dongtian-console --interactive
python3 -B scripts/demo.py --build ../dongtian-demo/build --output ../dongtian-denial --private-read
```

`--build` and `--deps` are alternatives. A reused build needs only the runtime environment check. `check-env.py --runtime-only` checks Python and QEMU; it does not run or accept the guest workflow. For cached inputs, add `--downloads /path/to/archive-cache` and `--kernel-deb /path/to/kernel.deb` to the demo. `--jobs N` selects build parallelism.

The [validation page](VALIDATION.md) distinguishes recorded runtime evidence from helper checks performed for the current release. An environment check alone is not an execution result. The individual commands below remain available for inspecting each stage.

## Prepare

```sh
python3 -B scripts/fetch-kernel.py
python3 -B scripts/prepare-runtime.py --output ../dongtian-deps
```

For offline preparation, supply `fetch-kernel.py --deb /path/to/kernel.deb` and `prepare-runtime.py --downloads /path/to/archive-cache --output ../dongtian-deps`. The cache filenames and hashes are in `dependencies/manifest.json`; missing cache entries are downloaded by the explicit prepare command. Files are SHA-256 checked before extraction. Debian's signing trust chain is not independently checked by these scripts.

Preparation extracts third-party packages without installing them or executing package maintainer scripts. It adds the local SBI extension to the pinned OpenSBI source and relocates the generated header Makefile to the prepared common-header path. Keep prepared output outside the source checkout and use a new directory after changing the extension or dependency pins. The builder rejects a stale extension source.

## Build

```sh
python3 -B scripts/build-runtime.py --deps ../dongtian-deps --output ../dongtian-build
```

The kernel is not rebuilt or patched. The real external module uses the matching Debian `Module.symvers` and generated headers. Optional module BTF debug metadata is omitted; the kernel configuration and module ABI remain the pinned versions. Every build step has a log and a receipt; failures preserve their output.

Artifacts include OpenSBI `fw_jump.bin`, the HS monitor, `dongtian.ko`, the static `dongtian` command, four initramfs archives, and host/guest device trees. The automatic, manual-console, and private-read host variants share the same driver/monitor implementation.

## Execute

```sh
python3 -B scripts/run-runtime.py --build ../dongtian-build --output ../dongtian-run
python3 -B scripts/run-runtime.py --build ../dongtian-build --output ../dongtian-private-read --private-read
python3 -B scripts/run-runtime.py --build ../dongtian-build --output ../dongtian-console --interactive
```

All output paths must be new and outside the checkout. Automatic acceptance requires the real OpenSBI banner, driver load, ordered Linux handoff/guest/return markers, and QEMU exit 0. The negative case accepts only the specific actual CPU private-page fault and intentional QEMU exit 1; its runner returns success when the denial is observed. Interactive mode connects the terminal to QEMU and records a session outcome rather than claiming automatic acceptance.

The host's `/init` loads `/lib/modules/dongtian.ko` with `finit_module`. It invokes `/sbin/dongtian` as separate Linux processes, exercising the ioctl interface across native and virtualized host execution. The interactive prompt supports `info`, `demote`, `run`, and `quit`; it is a control console rather than a general shell.

The driver is built for the emulated RISC-V Linux. Do not load it into the x86_64 machine running QEMU.
