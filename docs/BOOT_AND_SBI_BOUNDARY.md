# OpenSBI, driver, and HS handoff

## Runtime layout

OpenSBI 1.7 occupies M mode at physical `0x80000000`. A separately linked HS monitor is preloaded at `0x80100000`, and a fixed handoff page is at `0x801f0000`. The host kernel begins at `0x80200000`; its device tree excludes the firmware/monitor reservation from allocatable RAM.

The initial firmware device tree enables the QEMU timer and system-reset descriptions so OpenSBI can initialize M-mode services. The local extension then disables those platform-device nodes in the next-stage Linux device-tree copy. Linux uses SBI for timer/reset services, and the post-handoff G-stage does not expose CLINT or the finisher. Firmware and Linux receive the same bounded host RAM layout, avoiding allocator access to preloaded guest RAM.

| Item | Host physical address | Guest GPA to host physical address |
| --- | --- | --- |
| Kernel Image | `0x80200000` | `0x80200000` to `0xa0200000` |
| initramfs | `0x85000000` | `0x85000000` to `0xa5000000` |
| Device tree | `0x9f000000` | `0x87000000` to `0xa7000000` |
| RAM | `[0x80200000,0xa0000000)` | `[0x80000000,0x88000000)` to `[0xa0000000,0xa8000000)` |

## Management path

The host boots in native HS and reaches PID 1. Init loads the kernel module and starts management commands as separate processes. `/dev/dongtian` exposes exactly INFO, DEMOTE, and RUN ioctls to privileged callers. The driver serializes operations and issues the fixed experimental SBI extension `0x0800d07a` on hart 0 with preemption and interrupts disabled.

- FID 0 queries state; FID 3 queries the completed guest-run count.
- FID 1 hands native HS execution to the monitor.
- FID 2, handled by the HS monitor after demotion, enters the independent guest.

The SBI result follows the ordinary error/value convention in `a0`/`a1`. The ioctl structure is a fixed 16-byte ABI. State transitions are NATIVE (0), DEMOTED (1), and GUEST_DONE (2).

## Handoff and return

The OpenSBI extension captures the integer registers and the S translation/trap state. It stores the original SBI continuation at `mepc+4`, with successful SBI return values, in the fixed handoff page. `skip_regs_update` prevents the ordinary ecall dispatcher from overwriting the redirected entry state. M-mode trap return enters the HS monitor with bare `satp`.

The monitor builds separate G-stage mappings, places the saved native S state into VS CSRs, and uses `sret` to resume the same kernel driver invocation in VS. The driver restores its saved IRQ/preemption state and returns to the management process in VU. The original Linux is not rebooted. The pre-handoff timer deadline and pending indication are preserved in the handoff record.

RUN suspends the host and starts guest Linux. Guest SRST or supported legacy shutdown marks completion and resumes the host's ioctl continuation. The management tool checks GUEST_DONE and one completed run. A host shutdown then reaches OpenSBI's system-reset service through the HS SBI handler.

## Implementation lineage

This path extends the compact public monitor with actual OpenSBI integration, a reduced kernel control driver, and user management tools. It is not a verbatim pruning of a larger historical runtime. The standalone `build.py`/`run.py` workflow is retained as an earlier comparison example.
