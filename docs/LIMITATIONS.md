# Limitations

The demonstrated configuration is one hart under QEMU TCG with integer context. Other harts are parked. Floating-point/vector state, unrestricted privileged/device state capture, live SMP migration, and physical hardware behavior are outside the tested scope. The runner disables F/D/V, SSTC, and additional CPU features recorded in its command.

The initial HS Linux kernel, its page tables, and statically preloaded images are trusted. Handoff occurs at an intentional userspace trigger containing a known noncompressed four-byte store. This is a controlled transition of a running Linux continuation; it does not establish arbitrary migration of a malicious initial HS kernel. Before handoff, the trusted HS host has physical access to the preloaded guest data. Later G-stage mappings cannot retroactively protect that data.

Post-demotion G-stage mappings separate host and guest RAM and exclude firmware/monitor RAM. The negative test validates one actual host CPU read from one guest private address. It does not establish protection from every hostile-host access pattern, DMA, side channels, or all architectural attacks. There is no attestation, encryption, secure-boot chain, or IOMMU policy in this prototype.

The host is suspended during guest execution. UART and the six-MiB PLIC aperture are shared physical MMIO. Timers use SBI and CLINT-backed M-mode ticks; PLIC output is sampled. Narrow mappings and disabled FDT devices reduce the exercised surface without establishing device isolation or concurrent ownership.

SBI support is the small single-hart subset needed for this execution. BASE reports version 2.0, but no complete SBI 2.0 conformance evaluation has been performed. Guest SRST deliberately returns to the host. The boot/SBI note documents these semantics.

The kernel is an unchanged Debian binary acquired explicitly by the user. Firmware, monitor, init programs, initramfs, and device trees are rebuilt; Linux itself is not rebuilt or independently audited. Pinned hashes establish identity rather than independent signed-archive authentication. QEMU and the compiler/linker/tool environment remain external dependencies.
