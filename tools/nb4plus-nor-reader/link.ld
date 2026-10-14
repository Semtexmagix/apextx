/* SPDX-License-Identifier: GPL-2.0-only */
/* RAM-only image for the NB4+ NOR reader, loaded at 0x20008000 by ROM DFU. */
MEMORY
{
  RAM (rwx) : ORIGIN = 0x20008000, LENGTH = 0x7F00
}

_stack_top = 0x2000FF00 - 0x100;

SECTIONS
{
  .text : {
    KEEP(*(.vectors))
    *(.text*)
    *(.rodata*)
    . = ALIGN(4);
  } > RAM

  /DISCARD/ : { *(.data*) *(.bss*) *(.ARM.*) *(.comment) }
}
