<!-- SPDX-License-Identifier: Apache-2.0 -->
# dongtian management tool

`tools/dongtian.c` is a small RV64 freestanding management tool for the
Dongtian prototype.  It has no libc, no Linux user headers, no stdio, and no
dynamic dependencies.  It talks only to `/dev/dongtian` through the three
fixed ioctls in `include/dongtian_abi.h`; it never opens `/dev/mem` and has no
shell.

`tools/start.S` contains `_start`.  It reads the initial stack pointer from
the kernel, passes it to `tool_main(unsigned long *initial_stack)`, and the C
entry parses `argc`/`argv` from that stack.  Normal exit uses the RISC-V Linux
`exit` syscall number 93.  The syscall wrappers are direct `ecall`
instructions:

* `write` = 64
* `openat` = 56
* `close` = 57
* `ioctl` = 29
* `exit` = 93
* `finit_module` = 273 (only for the optional `load` command)

## Commands

```text
dongtian info
dongtian demote
dongtian run
dongtian demo
dongtian load /path/to/dongtian.ko
```

* `info` prints the ABI version, numeric state, state name, and guest run
  count:
  `DONGTIAN_INFO abi=1 state=0 state_name=NATIVE guest_runs=0`
* `demote` issues `DEMOTE`, then re-reads `INFO` and verifies `state=DEMOTED`.
* `run` issues `RUN`, then re-reads `INFO` and verifies `state=GUEST_DONE`.
* `demo` is the machine-readable acceptance sequence:
  `info` -> `demote` -> `info` -> `run` -> `info`.
  On success it prints `DONGTIAN_CONTROL_DEMO_PASS`.  On failure it prints
  `DONGTIAN_CONTROL_DEMO_FAIL reason=...` and returns nonzero.
* `load` opens the given module path and calls `finit_module(fd, "", 0)`.
  It is a convenience only; `insmod` is equally valid.  It does not install
  or search for modules.

All control commands use only `/dev/dongtian`.  The driver requires
`CAP_SYS_ADMIN`; `load` additionally needs the normal module-loading
privileges.

## Build

The binary must be RV64 and statically linked with no interpreter.  The
following is the exact command sequence used in this task environment
(macOS, Zig 0.17.0, Homebrew LLD 22.1.8).  It uses a `sifive_u74` (RV64GC)
CPU model as the local proxy for the target; substitute the board's
`-march`/`-mcpu` as appropriate.

```sh
export ZIG_GLOBAL_CACHE_DIR=/tmp/dongtian-zig-global
export ZIG_LOCAL_CACHE_DIR=/tmp/dongtian-zig-local
mkdir -p "$ZIG_GLOBAL_CACHE_DIR" "$ZIG_LOCAL_CACHE_DIR"

zig cc -target riscv64-linux-gnu -mcpu=sifive_u74 -mabi=lp64d \
  -O2 -g0 -ffreestanding -fno-builtin -fno-stack-protector \
  -fno-sanitize=all -fno-asynchronous-unwind-tables -fno-unwind-tables \
  -nostdlib -I include -c tools/dongtian.c -o /tmp/dongtian-tool.o

zig cc -target riscv64-linux-gnu -mcpu=sifive_u74 -mabi=lp64d \
  -O2 -g0 -fno-stack-protector -fno-sanitize=all \
  -fno-asynchronous-unwind-tables -fno-unwind-tables -nostdlib \
  -c tools/start.S -o /tmp/dongtian-start.o

ld.lld -m elf64lriscv -static -e _start -Ttext=0x10000 \
  -o /tmp/dongtian /tmp/dongtian-start.o /tmp/dongtian-tool.o
```

If `ld.lld` is not in `PATH`, use the full path to the LLVM linker, for
example `/opt/homebrew/Cellar/lld@22/22.1.8/bin/ld.lld`.

An equivalent GNU toolchain link, not executed in this environment, is:

```sh
riscv64-unknown-elf-gcc -march=rv64gc -mabi=lp64d -nostdlib -static \
  -ffreestanding -fno-builtin -Wl,-e,_start -Wl,-Ttext=0x10000 \
  -Iinclude tools/start.S tools/dongtian.c -o dongtian
```

Do not add `-lc`, a dynamic linker, or Linux UAPI headers.  Do not link the
tool against the kernel module.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | command succeeded |
| 2 | usage error |
| 3 | open/ioctl/read/write or module-load syscall failed |
| 4 | state verification or `demo` sequence failed |

Errors are printed as machine-readable lines, for example:

```text
DONGTIAN_ERROR op=open detail=/dev/dongtian errno=2 name=ENOENT
DONGTIAN_ERROR op=ioctl:INFO errno=25 name=ENOTTY
```

## Verification performed

The local build produced:

```text
ELF 64-bit LSB executable, UCB RISC-V, RVC, double-float ABI, version 1 (SYSV),
statically linked, not stripped
```

ELF inspection confirmed `ET_EXEC`, `e_machine=243` (RISC-V), entry
`0x10000`, no `PT_INTERP`, no `PT_DYNAMIC`, and no undefined symbols.  The
header ABI check printed `sizeof=16`, with offsets 0/4/8.  QEMU smoke tests
with a Linux 6.12 RISC-V kernel verified `_start`, `argc`/`argv`, `openat`,
`ioctl`, `write`, and `exit`, including the missing-device and `ENOTTY`
error paths.  The success path against a real `/dev/dongtian` was not tested
because no driver/device was available in this environment.  See
`../DRIVER-TASK-REPORT.md` for commands and full outputs.
