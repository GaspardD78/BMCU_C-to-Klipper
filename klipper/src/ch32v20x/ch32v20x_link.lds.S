MEMORY
{
    FLASH (rx) : ORIGIN = 0x00000000, LENGTH = CONFIG_FLASH_SIZE
    RAM   (rwx): ORIGIN = 0x20000000, LENGTH = CONFIG_RAM_SIZE
}

ENTRY(_start)

SECTIONS
{
    .text : {
        *(.init)
        *(.text*)
        *(.rodata*)
    } > FLASH

    .data : AT (ADDR(.text) + SIZEOF(.text)) {
        _sdata = .;
        *(.data*)
        _edata = .;
    } > RAM

    .bss (NOLOAD) : {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        _ebss = .;
    } > RAM

    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
}
