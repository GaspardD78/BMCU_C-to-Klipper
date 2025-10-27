#include <stdint.h>

// Provide a local implementation of __bswapsi2 for toolchains that
// do not ship this libgcc helper (observed with certain riscv-none-elf
// builds). Mark the symbol weak so a toolchain-provided version still
// takes precedence when available and "used" so LTO keeps the fallback.
__attribute__((weak, used))
uint32_t __bswapsi2(uint32_t value)
{
    return __builtin_bswap32(value);
}
