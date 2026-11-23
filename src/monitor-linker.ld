OUTPUT_ARCH(riscv)
ENTRY(monitor_entry)
SECTIONS {
 . = 0x80100000;
 .text : { KEEP(*(.text.entry)) *(.text .text.*) }
 .rodata : { *(.rodata .rodata.*) }
 .data : { *(.data .data.*) *(.sdata .sdata.*) }
 . = ALIGN(16); __bss_start = .;
 .bss (NOLOAD) : { *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) }
 . = ALIGN(16); __bss_end = .;
 ASSERT(. < 0x801f0000,"monitor overlaps fixed handoff page")
 /DISCARD/ : { *(.comment) *(.eh_frame*) *(.riscv.attributes) }
}
