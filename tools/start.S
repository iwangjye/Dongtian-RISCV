/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Freestanding RV64 entry point for the Dongtian control tool.
 *
 * The Linux process entry stack layout is:
 *   sp[0] = argc, sp[1..argc] = argv[], then a NULL, envp[], auxv.
 * _start preserves the original stack pointer in a0, aligns the stack for
 * the C ABI, and calls tool_main(initial_stack).  tool_main parses argc/argv
 * and exits with SYS_exit (93); the fallback below is only for safety.
 */

	.section .text.start, "ax", @progbits
	.globl _start
	.type _start, @function
_start:
	mv	a0, sp
	andi	sp, sp, -16
	call	tool_main

	/* Unreachable if tool_main behaves; avoid falling into data. */
	li	a0, 127
	li	a7, 93		/* SYS_exit */
	ecall
1:
	j	1b
	.size _start, .-_start

	.section .note.GNU-stack, "", @progbits
