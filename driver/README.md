<!-- SPDX-License-Identifier: GPL-2.0-only -->
# Dongtian control driver

`driver/dongtian.c` is a small, single-hart Linux misc driver for the
Dongtian prototype.  It exposes exactly three ioctls on `/dev/dongtian` and
forwards them to the fixed local SBI experimental extension.  It does not map
arbitrary physical memory, accept an SBI extension/function ID from userspace,
load guest images, or perform DMA.

The module is licensed GPL-2.0-only and declares `MODULE_LICENSE("GPL")`.
The shared ABI header `include/dongtian_abi.h` and the management tool are
Apache-2.0.

## UAPI

The ABI version is `DONGTIAN_ABI_VERSION == 1`.

```c
struct dongtian_info {
	unsigned int abi_version; /* 1 */
	unsigned int state;       /* 0=NATIVE, 1=DEMOTED, 2=GUEST_DONE */
	unsigned long long guest_runs;
};
```

The structure is exactly 16 bytes.  The ioctl numbers are fixed generic Linux
`_IOC` values written as literals in `include/dongtian_abi.h`:

| Operation | Request | Encoding | Argument |
|---|---|---:|---|
| `INFO` | `0x80104400` | `_IOR('D', 0, struct dongtian_info)` | pointer to a 16-byte `struct dongtian_info` |
| `DEMOTE` | `0x00004401` | `_IO('D', 1)` | ignored; pass 0 |
| `RUN` | `0x00004402` | `_IO('D', 2)` | ignored; pass 0 |

`INFO` queries the firmware for the current state (FID 0) and completed guest
run count (FID 3), then copies them and the ABI version to userspace.
`DEMOTE` and `RUN` validate the driver's state before issuing the corresponding
SBI call.

## SBI contract

* EID: `0x0800D07A` (the local experimental range)
* FID 0 `QUERY`: `a0 == 0`, state in `a1` (`struct sbiret.value`)
* FID 1 `DEMOTE`: native HS to monitor; returns to the same kernel
  continuation; success requires `a0 == 0, a1 == 0`
* FID 2 `RUN`: enter the independently preloaded guest and return after guest
  shutdown; success requires `a0 == 0, a1 == 0`
* FID 3 `RUN_COUNT`: `a0 == 0`, number of completed guest runs in `a1`
  (`struct sbiret.value`)

The driver treats a negative SBI error as an error and never as success.  It
maps `SBI_ERR_DENIED` to `EPERM`, `SBI_ERR_INVALID_PARAM` to `EINVAL`,
`SBI_ERR_INVALID_ADDRESS` to `EFAULT`, `SBI_ERR_NOT_SUPPORTED` to
`EOPNOTSUPP`, `SBI_ERR_ALREADY_*` to `EALREADY`, and other failures to `EIO`.

## Device and permissions

* Name: `/dev/dongtian` (dynamic misc minor)
* Mode: `0600`
* Access: `CAP_SYS_ADMIN` is checked on open and again on every ioctl
* Only the three fixed requests above are accepted; all other requests return
  `ENOTTY`

## Build

The module must be built against a configured RISC-V Linux 6.12 kernel tree.
`CONFIG_MODULES=y` and `CONFIG_RISCV_SBI=y` are required: the Linux
`asm/sbi.h` `sbi_ecall()` macro is only available with `CONFIG_RISCV_SBI`, and
the driver calls the exported `__sbi_ecall()` implementation.

From the repository root:

```sh
make -C driver \
	KDIR=/path/to/linux-6.12 \
	ARCH=riscv \
	CROSS_COMPILE=riscv64-linux-gnu-
```

The Makefile accepts `KDIR`, `ARCH`, and `CROSS_COMPILE`.  It does not download
or install a kernel, compiler, or module.  `make -C driver ... modules_install`
is an explicit target only; nothing is installed automatically.

## Load and unload

```sh
insmod driver/dongtian.ko
dmesg | tail
```

or, with the management tool:

```sh
dongtian load /path/to/dongtian.ko
```

The module probes the fixed EID during init.  If OpenSBI does not implement it,
init fails with `-ENODEV` and `/dev/dongtian` is not registered.  Unload with
`rmmod dongtian`.

## State machine and restrictions

* `NATIVE` -> `DEMOTE` -> `DEMOTED` -> `RUN` -> `GUEST_DONE`
* A repeated `DEMOTE` returns `EALREADY`.
* `RUN` is accepted only in `DEMOTED`; any other state returns `EINVAL`.
* At most one guest run is supported per boot.
* The prototype is single-hart.  The SBI call is made only when the current
  CPU is CPU 0, with preemption disabled by `get_cpu()`/`put_cpu()` and
  interrupts disabled by `local_irq_save()`/`local_irq_restore()`.  If the
  caller is not on CPU 0, the driver returns `-ENODEV` rather than migrating
  the task or performing an SMP rendezvous.
* There is no reset ioctl; a new boot or a firmware-side reset is outside this
  driver's scope.

## Verification status

This tree was not built or loaded as a module in the task environment because
no matching RISC-V Linux 6.12 build tree/headers were available.  The source
was statically reviewed against upstream Linux v6.12 `asm/sbi.h`,
`kernel/sbi_ecall.c`, `linux/smp.h`, `linux/cpumask.h`, and
`linux/miscdevice.h`.  See `../DRIVER-TASK-REPORT.md` for the exact review and
the unverified items.  The main integration agent is responsible for the real
module build and load test.
