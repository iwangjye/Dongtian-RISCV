# Execution scope

The current expanded runtime has been designed for one RISC-V hart under QEMU TCG, integer execution state, a trusted initial HS Linux, and trusted preloaded host/guest images. The initial host can access guest data before handoff. The driver controls a fixed monitor and one preloaded guest; it is not a general image loader or multi-VM manager.

After handoff, the host and guest have separate CPU RAM mappings. UART and PLIC remain shared, and the host pauses during guest execution. The private-read check exercises one actual CPU denial; device/DMA isolation, physical-board behavior, multicore coordination, floating-point/vector migration, and remote attestation are outside the current validation.

The handoff captures the state used by this controlled single-hart workflow. It does not establish arbitrary hostile-host takeover or full architectural-state migration. A guest has one execution/return cycle per session. The interactive interface is a management console, not a general Linux shell.

Expanded dependency preparation and module construction are tested on x86_64 Linux. The earlier standalone-firmware path also has macOS build/run evidence; that evidence does not imply macOS can run the Linux kernel-module build workflow.
