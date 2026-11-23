/* New compact entry: frozen sm_env_trap.S sscratch/context mechanism. */
.section .text
.align 2
.globl hs_trap
hs_trap:
 csrrw sp, sscratch, sp
 sd x5, 40(sp)
 csrr x5, sscratch
 sd x5, 16(sp)
 sd zero, 0(sp)
 sd x1, 8(sp)
 sd x3, 24(sp)
 sd x4, 32(sp)
 sd x6, 48(sp)
 sd x7, 56(sp)
 sd x8, 64(sp)
 sd x9, 72(sp)
 sd x10, 80(sp)
 sd x11, 88(sp)
 sd x12, 96(sp)
 sd x13, 104(sp)
 sd x14, 112(sp)
 sd x15, 120(sp)
 sd x16, 128(sp)
 sd x17, 136(sp)
 sd x18, 144(sp)
 sd x19, 152(sp)
 sd x20, 160(sp)
 sd x21, 168(sp)
 sd x22, 176(sp)
 sd x23, 184(sp)
 sd x24, 192(sp)
 sd x25, 200(sp)
 sd x26, 208(sp)
 sd x27, 216(sp)
 sd x28, 224(sp)
 sd x29, 232(sp)
 sd x30, 240(sp)
 sd x31, 248(sp)
 csrr t0, sepc
 sd t0, 256(sp)
 csrr t0, vsstatus
 sd t0, 264(sp)
 csrr t0, vsatp
 sd t0, 272(sp)
 csrr t0, vstvec
 sd t0, 280(sp)
 csrr t0, vsscratch
 sd t0, 288(sp)
 csrr t0, vsie
 sd t0, 296(sp)
 csrr t0, vsepc
 sd t0, 304(sp)
 csrr t0, vscause
 sd t0, 312(sp)
 csrr t0, vstval
 sd t0, 320(sp)
 csrr t0, sstatus
 sd t0, 328(sp)
 csrr t0, hstatus
 sd t0, 336(sp)
 csrr t0, hvip
 sd t0, 344(sp)
 mv a0, sp
 csrw sscratch, zero
 la sp, monitor_stack_top
 call monitor_trap
.globl vs_restore
vs_restore:
 mv sp, a0
 ld t0, 256(sp)
 csrw sepc, t0
 ld t0, 264(sp)
 csrw vsstatus, t0
 ld t0, 272(sp)
 csrw vsatp, t0
 ld t0, 280(sp)
 csrw vstvec, t0
 ld t0, 288(sp)
 csrw vsscratch, t0
 ld t0, 296(sp)
 csrw vsie, t0
 ld t0, 304(sp)
 csrw vsepc, t0
 ld t0, 312(sp)
 csrw vscause, t0
 ld t0, 320(sp)
 csrw vstval, t0
 ld t0, 328(sp)
 csrw sstatus, t0
 ld t0, 336(sp)
 csrw hstatus, t0
 ld t0, 344(sp)
 csrw hvip, t0
 csrw sscratch, sp
 ld x1, 8(sp)
 ld x3, 24(sp)
 ld x4, 32(sp)
 ld x5, 40(sp)
 ld x6, 48(sp)
 ld x7, 56(sp)
 ld x8, 64(sp)
 ld x9, 72(sp)
 ld x10, 80(sp)
 ld x11, 88(sp)
 ld x12, 96(sp)
 ld x13, 104(sp)
 ld x14, 112(sp)
 ld x15, 120(sp)
 ld x16, 128(sp)
 ld x17, 136(sp)
 ld x18, 144(sp)
 ld x19, 152(sp)
 ld x20, 160(sp)
 ld x21, 168(sp)
 ld x22, 176(sp)
 ld x23, 184(sp)
 ld x24, 192(sp)
 ld x25, 200(sp)
 ld x26, 208(sp)
 ld x27, 216(sp)
 ld x28, 224(sp)
 ld x29, 232(sp)
 ld x30, 240(sp)
 ld x31, 248(sp)
 ld sp, 16(sp)
 sret
.section .bss
.balign 16
monitor_stack:
 .space 16384
.globl monitor_stack_top
monitor_stack_top:
