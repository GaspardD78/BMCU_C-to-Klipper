// RISC-V interrupt helpers
//
// Copyright (C) 2024  Contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "irq.h" // irqstatus_t
#include "sched.h" // DECL_SHUTDOWN

void
irq_disable(void)
{
    asm volatile("csrci mstatus, 0x8" ::: "memory");
}

void
irq_enable(void)
{
    asm volatile("csrsi mstatus, 0x8" ::: "memory");
}

irqstatus_t
irq_save(void)
{
    irqstatus_t flag;
    asm volatile("csrrc %0, mstatus, 0x8" : "=r"(flag) :: "memory");
    return flag;
}

void
irq_restore(irqstatus_t flag)
{
    asm volatile("csrw mstatus, %0" :: "r"(flag) : "memory");
}

void
irq_wait(void)
{
    asm volatile("csrsi mstatus, 0x8\n    wfi\n    csrci mstatus, 0x8" ::: "memory");
}

void
irq_poll(void)
{
}

static void
clear_active_irq(void)
{
    // The ECLIC automatically clears the current vector when the
    // handler returns, so nothing to do here.
}
DECL_SHUTDOWN(clear_active_irq);
