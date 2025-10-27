// Minimal RISC-V RV32I implementation of setjmp/longjmp
//
// This code saves and restores the callee-saved registers along with the
// stack pointer and return address so that Klipper's scheduler can unwind
// to the main loop during a shutdown.

#include "setjmp.h"

int
setjmp(jmp_buf env)
{
    uint32_t *buf = (uint32_t *)env;
    __asm__ volatile(
        "sw ra, 0(%0)\n"
        "sw sp, 4(%0)\n"
        "sw s0, 8(%0)\n"
        "sw s1, 12(%0)\n"
        "sw s2, 16(%0)\n"
        "sw s3, 20(%0)\n"
        "sw s4, 24(%0)\n"
        "sw s5, 28(%0)\n"
        "sw s6, 32(%0)\n"
        "sw s7, 36(%0)\n"
        "sw s8, 40(%0)\n"
        "sw s9, 44(%0)\n"
        "sw s10, 48(%0)\n"
        "sw s11, 52(%0)\n"
        :
        : "r"(buf)
        : "memory");
    return 0;
}

void
longjmp(jmp_buf env, int val)
{
    if (val == 0)
        val = 1;
    uint32_t *buf = (uint32_t *)env;
    __asm__ volatile(
        "lw ra, 0(%0)\n"
        "lw sp, 4(%0)\n"
        "lw s0, 8(%0)\n"
        "lw s1, 12(%0)\n"
        "lw s2, 16(%0)\n"
        "lw s3, 20(%0)\n"
        "lw s4, 24(%0)\n"
        "lw s5, 28(%0)\n"
        "lw s6, 32(%0)\n"
        "lw s7, 36(%0)\n"
        "lw s8, 40(%0)\n"
        "lw s9, 44(%0)\n"
        "lw s10, 48(%0)\n"
        "lw s11, 52(%0)\n"
        "mv a0, %1\n"
        "jr ra\n"
        :
        : "r"(buf), "r"(val)
        : "memory", "a0");
    __builtin_unreachable();
}
