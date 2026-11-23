/* SPDX-License-Identifier: Apache-2.0 */
.option norvc
.section .text.entry,"ax"
.globl monitor_entry
monitor_entry:
    la sp, monitor_stack_top
    la t0, __bss_start
    la t1, __bss_end
1:  bgeu t0, t1, 2f
    sd zero, 0(t0)
    addi t0, t0, 8
    j 1b
2:  tail monitor_main
