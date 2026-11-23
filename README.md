# Dongtian

Dongtian is a RISC-V runtime for handing a running Linux host to an HS monitor through OpenSBI, then executing an independent Linux guest. It includes a Linux control driver, a freestanding management command, and an interactive control console.

## Components

| Component | Implementation |
| --- | --- |
| M-mode firmware | Pinned OpenSBI 1.7 with `opensbi/sbi_ecall_dongtian.c` |
| HS monitor | `src/monitor.c`, `src/trap.S`, `src/monitor-entry.S` |
| Linux control driver | `driver/dongtian.c`, exposing `/dev/dongtian` |
| Management command | `tools/dongtian.c`: `info`, `demote`, `run`, `demo` |
| Host and guest userspace | `src/host-init.c`, `src/init.c` |
| Build and QEMU tools | `scripts/prepare-runtime.py`, `build-runtime.py`, `run-runtime.py` |

Both Linux instances use the same unmodified Debian kernel. The host loads a real `dongtian.ko`; control operations use driver ioctls and a local experimental SBI extension.

## Quick start

The expanded build runs on x86_64 Linux with Python 3.12+, GNU make, a native C compiler, `dtc`, QEMU RISC-V system emulation, and a GNU RISC-V cross toolchain with a PIE-capable linker. On the tested Ubuntu 26.04 host the relevant distribution packages include `gcc-riscv64-linux-gnu`, `device-tree-compiler`, and `qemu-system-riscv`.

From the repository root, use new output directories outside the checkout:

```sh
python3 -B scripts/verify.py
python3 -B scripts/fetch-kernel.py
python3 -B scripts/prepare-runtime.py --output ../dongtian-deps
python3 -B scripts/build-runtime.py --deps ../dongtian-deps --output ../dongtian-build
python3 -B scripts/run-runtime.py --build ../dongtian-build --output ../dongtian-run
```

The two explicit preparation commands acquire pinned third-party inputs. The build compiles OpenSBI, the HS monitor, the kernel module, the management command, and host/guest initramfs. Successful automatic execution ends with `PASS_LINUX_HOST_AND_CVM`.

Tool paths can be selected with `--cross-compile <prefix>`, `--dtc`, and `--qemu`. Offline archive caches are supported; see [reproduction instructions](docs/REPRODUCIBILITY.md).

## Try the control console

```sh
python3 -B scripts/run-runtime.py --build ../dongtian-build --output ../dongtian-console --interactive
```

At the `dongtian>` prompt:

```text
info
demote
info
run
info
quit
```

The states progress from `NATIVE` to `DEMOTED` to `GUEST_DONE`. One guest execution is supported per QEMU session. This console invokes the same management binary and kernel driver as the automatic workflow.

## Tested configuration

The current runtime uses single-hart RISC-V QEMU TCG with a trusted initial host and preloaded guest images. See [validation](docs/VALIDATION.md), [implementation details](docs/BOOT_AND_SBI_BOUNDARY.md), and [execution scope](docs/LIMITATIONS.md).

The [earlier standalone-firmware example](docs/LEGACY_MINIMAL.md) remains available separately.

## License

Dongtian's original firmware extension, monitor, management command, scripts, and documentation use [Apache-2.0](LICENSE). The Linux control module uses GPL-2.0-only; downloaded OpenSBI retains BSD-2-Clause and Linux retains its upstream terms. See [component notices](THIRD_PARTY_NOTICES.md) and [file inventory](LICENSE_INVENTORY.json).
