#include "autoconf.h"

#ifndef CONFIG_FLASH_APPLICATION_ADDRESS
#define CONFIG_FLASH_APPLICATION_ADDRESS 0x00000000
#endif

#ifndef CONFIG_RAM_START
#define CONFIG_RAM_START 0x20000000
#endif

OUTPUT_FORMAT("elf32-littleriscv", "elf32-littleriscv", "elf32-littleriscv")
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    flash (rx) : ORIGIN = CONFIG_FLASH_APPLICATION_ADDRESS, LENGTH = CONFIG_FLASH_SIZE
    ram   (rwx) : ORIGIN = CONFIG_RAM_START, LENGTH = CONFIG_RAM_SIZE
}

SECTIONS
{
    .text : {
        . = ALIGN(4);
        *(.init)
        *(.text .text.*)
        *(.rodata .rodata*)
    } > flash

    . = ALIGN(4);
    _data_flash = .;

    .data : AT(_data_flash) {
        . = ALIGN(4);
        _sdata = .;
        *(.data .data.*)
        . = ALIGN(4);
        _edata = .;
    } > ram

    . = ALIGN(4);
    _sbss = .;
    .bss (NOLOAD) : {
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > ram

    . = ALIGN(4);
    _end = .;
}

_stack_top = ORIGIN(ram) + LENGTH(ram);
PROVIDE(__stack = _stack_top);
