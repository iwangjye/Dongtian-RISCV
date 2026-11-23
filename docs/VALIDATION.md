# Validation and evidence

The expanded OpenSBI/driver runtime was rebuilt and executed on x86_64 Ubuntu 26.04 with QEMU 10.2.1, GCC 14.2, GNU Linux-target binutils 2.46, and dtc 1.7.2. Both Linux instances use the pinned unmodified Debian 6.12.117 kernel. The real external module was compiled against its matching generated headers and symbol versions.

| Check | Observed result |
| --- | --- |
| M-mode firmware | Real OpenSBI 1.7 banner; Linux reports OpenSBI implementation ID 1 |
| Driver load | `finit_module` loads `dongtian.ko`, creates `/dev/dongtian` |
| Native management process | INFO reports `NATIVE`, ABI 1, zero guest runs |
| Kernel-context handoff | DEMOTE ioctl resumes the same kernel continuation in VS; INFO reports `DEMOTED` |
| Post-handoff userspace/timer | Original host userspace continues; 10 ms sleep completes |
| Guest execution | RUN ioctl boots independent Linux to guest PID 1 |
| Return and status | Host resumes; INFO reports `GUEST_DONE` and one completed run |
| Normal completion | Driver workflow and final completion markers; QEMU exits 0 |
| CPU private-read denial | Actual host load faults at private HPA `0xa0200000`; expected QEMU exit 1 |
| Interactive control | Real terminal exchange of `info`, `demote`, `info`, `run`, `info`, `quit`; clean exit |

The [normal serial log](../evidence/linux-positive.log), [private-read log](../evidence/linux-private-read-denied.log), and [interactive transcript](../evidence/control-console.log) record these runs. The negative case requires an actual load fault with cause 21 and `htval=0x28080000`, not a rejected `/dev/mem` mapping. Init drains console output before the deliberately faulting read.

The command-line runner verifies build artifacts, the kernel pin, ordered execution markers, and exit status. Interactive mode itself records a session end rather than an automatic PASS; the terminal exchange above was additionally checked by the integration run. Source hashes and logs establish the exercised configuration, without constituting hardware attestation or a comprehensive security evaluation.

Earlier standalone-firmware code has separate QEMU execution evidence on Linux and macOS. That earlier result is not used as a substitute for the expanded OpenSBI/module/control-console runs. See [execution scope](LIMITATIONS.md) and [reproduction instructions](REPRODUCIBILITY.md).

## One-command workflow checks

The environment checker and `demo.py` wrapper were exercised on the tested Linux host. The checker produced a real ELF64 RISC-V PIE probe. The demo then prepared dependencies from a pinned local archive cache, rebuilt the complete runtime, and passed the automatic Linux handoff/guest/return check. The existing verified Image cache was used; the kernel HTTP-download path was not exercised in this check.

The same new build was reused through `demo.py` for the expected private-read denial and for a real terminal exchange of `info`, `demote`, `info`, `run`, `info`, `quit`. The interactive wrapper records `INTERACTIVE_COMPLETED`, not an automatic PASS. Each wrapper receipt records child commands and exit codes and points to the existing runner receipt. See the [portable check summary](../evidence/usability-summary.json) for outcomes and helper source hashes.
