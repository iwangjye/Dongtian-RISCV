# Validation and evidence

The existing prototype passed both execution cases on x86_64 Ubuntu 26.04 (QEMU 10.2.1, GCC 14.2, dtc 1.7.2) and macOS arm64 (QEMU 11.1.2, Clang/LLD 22.1.8). Both environments emulate RISC-V using QEMU TCG. The public source-only package was then rebuilt and both execution cases rerun successfully on macOS arm64. Its kernel acquisition script was tested offline against the pinned Debian package and produced the exact expected Image; the HTTP download path was not exercised in that check.

| Check | Observed result |
| --- | --- |
| Initial HS Linux boot | Real `uname` and `getpid=1` from host init |
| Controlled HS → VS/VU transition | Existing userspace continuation prints `HOST_AFTER_DEMOTION` |
| Post-transition timer syscall | 10 ms `nanosleep` succeeds |
| Independent guest Linux | Second kernel reaches guest PID 1 |
| Guest SRST and host return | `HOST_AFTER_CVM_RETURN`, final completion, QEMU exit 0 |
| Host private-page CPU load | Actual `ld` causes G-stage load fault, QEMU exit 1 |

[Positive sample serial log](../evidence/linux-positive.log) and [private-read sample serial log](../evidence/linux-private-read-denied.log) were recorded by rebuilding and running this public source package. They contain serial output rather than private host paths or environment metadata. They demonstrate the exercised functionality; they are not full security evidence.

The negative case maps guest private address `0xa0200000` after host return and performs a CPU load. The observed cause is 21 with `htval=0x28080000`. Acceptance excludes an unexpectedly returned read value and a mere failure to map `/dev/mem`. The runner reports `PASS_EXPECTED_CPU_READ_DENIAL` only for the expected fault.

To validate a new checkout, follow [REPRODUCIBILITY.md](REPRODUCIBILITY.md), retain build/run receipts, and check both runner statuses. The positive run requires ordered markers and exit 0; the negative QEMU exit 1 is intentional. Hash checks confirm artifact identity; execution logs establish the exercised boot path. See [LIMITATIONS.md](LIMITATIONS.md) for the boundaries of these results.
