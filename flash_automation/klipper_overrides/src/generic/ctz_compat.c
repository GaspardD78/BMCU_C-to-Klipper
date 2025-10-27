#include <stdint.h>

// Provide a local implementation of __ctzsi2 for toolchains missing
// this helper. GCC expects the return value to be the number of
// trailing zero bits; use a defined result when the input is zero to
// avoid undefined behaviour from __builtin_ctz().
__attribute__((weak, used))
int __ctzsi2(unsigned int value)
{
    if (value == 0)
        return sizeof(value) * 8;
    return __builtin_ctz(value);
}
