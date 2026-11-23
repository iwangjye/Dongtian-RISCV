OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
 . = 0x80000000;
 .text : { KEEP(*(.text.boot)) *(.text .text.*) }
 .rodata : { *(.rodata .rodata.*) }
 .data : { *(.data .data.*) *(.sdata .sdata.*) }
 . = ALIGN(16); __bss_start = .;
 .bss (NOLOAD) : { *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) }
 . = ALIGN(16); __bss_end = .;
 .m_stack (NOLOAD) : { . += 0x10000; __m_stack_top = .; }
 ASSERT(. < 0x80200000,"firmware/monitor exceeds reserved region")
 /DISCARD/ : { *(.comment) *(.eh_frame*) *(.riscv.attributes) }
}
