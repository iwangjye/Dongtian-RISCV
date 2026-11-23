# Linux boot and SBI boundary

This note describes the controlled single-hart QEMU execution implemented by Dongtian. The initial HS host and preloaded images are trusted.

## Boot and transition actually implemented

1. The M firmware starts hart 0, parks other harts, permits HS physical accesses through PMP, initializes delegation and machine timer handling, and enters the ordinary Linux Image at PA `0x80200000` with `satp=0`, `a0=0`, and `a1=0x9f000000` (host FDT). The host kernel initially runs in HS; this is not a host first booted in VS.
2. The host `/init` mounts devtmpfs, maps PA `0x11000000` through `/dev/mem`, and issues a deliberately noncompressed four-byte `sw`. Its first store faults while `/init` is in U mode. M retains store-access-fault handling and translates `mtval` through the current host page tables to confirm the trigger PA. The helper supports Bare and Sv39/Sv48/Sv57 layouts; it is a local trusted-page-table address resolver, not a complete architectural page-walk validator.
3. M saves all integer registers (including original U stack), original `mepc`, and `mstatus`. It captures the S execution/translation/trap state used here: `sstatus`, `satp`, `stvec`, `sscratch`, `sie`, `sepc`, `scause`, and `stval`. It advances the saved PC by exactly four bytes, derives the return privilege from saved MPP, clears `satp`, fences, resets the separate M stack pointer, and enters `monitor_main` on the HS monitor stack. The saved U origin produces SPP=0 and SPVP=0; it must not be forced to supervisor origin.
4. HS copies the captured frame, creates separate G-stage RAM maps, installs VS CSRs on restore, and resumes the existing host `/init` in VU immediately after the first store. The host kernel, page tables, userspace, and memory remain live; host boot is not restarted. The previous SBI timer deadline and pending timer indication are carried into the host virtual timer. The demonstrated post-transition `nanosleep` returns successfully.
5. The second four-byte store to the same PA hits the host's intentionally absent G-stage MMIO leaf. HS advances that host PC and enters the independently preloaded guest Linux at GPA `0x80200000`. Guest shutdown returns to the suspended VS host; host then resumes userspace and shuts down.

## Loader and memory layout

| Item | Host physical address | Guest GPA → physical address |
|---|---:|---:|
| Linux Image | `0x80200000` | `0x80200000` → `0xa0200000` |
| initramfs | `0x85000000` | `0x85000000` → `0xa5000000` |
| FDT | `0x9f000000` | `0x87000000` → `0xa7000000` |
| Allocatable RAM | `[0x80200000,0xa0000000)` | `[0x80000000,0x88000000)` → `[0xa0000000,0xa8000000)` |

QEMU raw-loader devices preload all six artifacts. Neither VS domain maps the firmware/monitor region `[0x80000000,0x80200000)` as RAM; the host does not map guest private RAM. UART and PLIC are shared physical devices. The host is suspended during synchronous guest execution; this is not device isolation or concurrent device virtualization.

## SBI retained and excluded

The M layer provides the local boot necessities: BASE (reported spec 2.0), TIME/legacy timer, legacy UART console calls, and shutdown/SRST through the QEMU finisher. Unsupported extensions return not-supported. TIME programs hart 0's CLINT `mtimecmp`; MTIP is converted to delegated STIP. This is a deliberately small implementation, not a complete SBI 2.0 conformance claim: modern M TIME/SRST paths do not validate every function/argument, machine identity results are synthetic zeroes, and SMP/IPI/RFENCE/HSM facilities are not provided by M.

After demotion, VS SBI calls terminate at the HS monitor. It implements the local BASE/TIME, legacy console, single-hart IPI/local RFENCE, limited HSM status, bounded DBCN console, and SRST paths used by these Linux boots. HS uses M TIME for periodic ticks, compares virtual deadlines, and injects VSTIP. Physical PLIC output is sampled on those ticks and delivered as VSEIP. These are bounded single-hart services, not general multi-hart firmware. Guest SRST means return to the host in this demonstration; host SRST reaches the finisher after the expected chain completes.

## Kernel provenance and claim boundary

Both Linux instances use the same unmodified Debian kernel, `linux-image-6.12.117+deb13-riscv64`, version `6.12.117-1`. The user explicitly acquires it through the pinned fetch workflow; no Image binary is included in the source repository. See the retained metadata in `images/`. OpenSBI is not linked into this execution path.

Both host and guest post-demotion MMIO mappings are limited to UART and the six-MiB PLIC aperture. Neither exposes CLINT or a broad MMIO window through G-stage. Timers use SBI through M/HS. The verified behavior is a controlled transition, second Linux boot, synchronous return, and one private-page CPU read denial. See [LIMITATIONS.md](LIMITATIONS.md) for remaining architectural and security boundaries.
