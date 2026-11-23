# Dongtian

Dongtian is a small RISC-V virtualization prototype for studying a controlled transition of a running Linux host from HS into VS/VU, followed by synchronous execution of one independent Linux CVM. It provides compact M-mode firmware, an HS monitor, direct-syscall Linux init programs, and reproducible QEMU checks.

The host first boots an unmodified Debian Linux kernel to PID 1 in HS. A deliberate userspace store transfers control to the monitor, which resumes the same host continuation in VU. The resumed host completes a 10 ms timer syscall, starts a second Linux instance that reaches PID 1, and resumes after guest SRST. A separate negative test executes an actual host CPU load from guest private RAM and requires a G-stage load fault.

## Quick start

Requirements: Python 3.9+, a RISC-V capable GCC/binutils or Clang/LLD toolchain, `dtc`, and `qemu-system-riscv64` with the H extension. On the tested Ubuntu 26.04 environment, the relevant package names are `qemu-system-riscv`, `gcc-riscv64-unknown-elf`, and `device-tree-compiler`. Other releases may package these tools differently.

Run from the repository root. Build and run output directories must be new and outside the repository.

```sh
python3 -B scripts/verify.py
python3 -B scripts/fetch-kernel.py
python3 -B scripts/build.py --output ../dongtian-build
python3 -B scripts/run.py --build ../dongtian-build --output ../dongtian-run
python3 -B scripts/run.py --build ../dongtian-build --output ../dongtian-private-read --private-read
```

The kernel fetch is an explicit download from Debian; the repository contains no Linux `Image` binary. To use a previously downloaded matching package, run `python3 -B scripts/fetch-kernel.py --deb /path/to/package.deb`. The fetcher checks the pinned package and extracted Image hashes. Build tool paths can be selected with `--cc`, `--ld`, and `--dtc`; the runner accepts `--qemu`. See [reproduction instructions](docs/REPRODUCIBILITY.md).

## Demonstrated scope

This is a single-hart, integer-context QEMU TCG prototype with trusted initial HS Linux and trusted, statically preloaded guest images. The host pauses while the guest runs. UART and PLIC remain shared. The demonstrated CPU memory boundary does not provide DMA isolation, multi-hart migration, floating-point/vector state migration, attestation, or a complete malicious-OS security guarantee. Physical RISC-V hardware has not been tested. Preloaded guest data is accessible to the trusted initial HS host before demotion.

See [limitations](docs/LIMITATIONS.md), [validation](docs/VALIDATION.md), and [boot/SBI details](docs/BOOT_AND_SBI_BOUNDARY.md). Sample serial logs record functional evidence under these conditions; they are not a comprehensive security evaluation.

## Repository layout

- `src/`, `include/`: M firmware, HS monitor, and context/trap support.
- `src/init.c`: minimal host and guest init programs.
- `tests/`: the private-read negative-test init source.
- `scripts/`: integrity verification, explicit kernel acquisition, build, and QEMU execution.
- `images/`: pinned kernel metadata, configuration, and provenance materials.
- `evidence/`: two recorded serial logs.

Dongtian's original firmware, monitor, init programs, scripts, and documentation are licensed under [Apache-2.0](LICENSE). Third-party materials retain their original terms, as described in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

