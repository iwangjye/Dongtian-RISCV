# Reproducing the Linux transition

## Dependencies and tested environments

Use Python 3.9+, RISC-V-capable GCC/binutils or Clang/LLD, the device-tree compiler, and QEMU system emulation with the RISC-V H extension. The prototype was built and both execution cases passed with GCC 14.2, dtc 1.7.2, and QEMU 10.2.1 on x86_64 Ubuntu 26.04, and with Clang/LLD 22.1.8 and QEMU 11.1.2 on macOS arm64. These were RISC-V QEMU TCG executions; they do not establish physical-board behavior. Apple system Clang was not the tested RISC-V compiler.

On Ubuntu 26.04, the tested package names are `gcc-riscv64-unknown-elf`, `device-tree-compiler`, and `qemu-system-riscv`. Verify availability for your distribution release. Python and the tools are external dependencies.

## Acquire the pinned kernel

Run from the repository root:

```sh
python3 -B scripts/verify.py
python3 -B scripts/fetch-kernel.py
```

Only the explicit fetch command downloads the kernel. It obtains Debian `linux-image-6.12.117+deb13-riscv64`, version `6.12.117-1`, checks the package SHA256, and extracts the fixed Image member with an additional SHA256 check. The repository includes kernel configuration, copyright, source descriptor, and metadata, but excludes the Image binary. For an existing matching package:

```sh
python3 -B scripts/fetch-kernel.py --deb /path/to/package.deb
```

The pins are in `images/kernel-info.json`. Hash matching checks identity against these pins; this workflow does not independently validate Debian's signed archive trust chain or rebuild Linux from source.

## Build and run

Use new output directories outside the repository:

```sh
python3 -B scripts/build.py --output ../dongtian-build
python3 -B scripts/run.py --build ../dongtian-build --output ../dongtian-run
python3 -B scripts/run.py --build ../dongtian-build --output ../dongtian-private-read --private-read
```

Select tools through build options `--cc`, `--ld`, and `--dtc`, and run option `--qemu`. For example, a Clang build requires a RISC-V-capable Clang and matching LLD. Consult each script's `--help` for accepted arguments.

The build reconstructs firmware, monitor, three no-libc init binaries, initramfs archives, and FDTs. Both Linux instances use the same unmodified downloaded kernel with different initramfs. The runner checks artifact hashes, preloads host/guest into separate RAM, and writes `serial.log` and `receipt.json`.

Positive acceptance requires the complete ordered boot/transition/return sequence and QEMU exit 0, yielding `PASS_LINUX_HOST_AND_CVM`. The negative run deliberately causes QEMU exit 1; the runner accepts only the expected actual CPU G-stage read fault and reports `PASS_EXPECTED_CPU_READ_DENIAL`. A rejected `/dev/mem` mapping alone is insufficient.

`verify.py` checks the public source inventory in `PUBLIC_MANIFEST.json`. Source integrity, build receipts, and runtime acceptance are separate checks: a successful compile or matching hash alone does not prove either Linux boot.
