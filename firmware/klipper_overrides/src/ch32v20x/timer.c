// Timer implementation for CH32V20x using TIM2

#include <stdint.h>
#include "autoconf.h"
#include "board/irq.h"
#include "command.h"
#include "generic/timer_irq.h"
#include "sched.h"
#include "internal.h"

static uint32_t timer_base;

static inline uint32_t
current_ticks(void)
{
    return timer_base + TIM2->CNT;
}

static void
schedule_next(uint32_t next)
{
    uint32_t now = current_ticks();
    int32_t diff = (int32_t)(next - now);
    if (diff < 2)
        diff = 2;
    timer_base = now;
    TIM2->ATRLR = (uint32_t)diff;
    TIM2->CNT = 0;
    TIM2->SWEVGR = 1;
}

uint32_t
timer_read_time(void)
{
    return current_ticks();
}

void
timer_kick(void)
{
    schedule_next(timer_read_time() + 50);
}

void
TIM2_IRQHandler(void)
{
    // Clear update flag
    TIM2->INTFR = (uint32_t)~TIM_UIF;
    timer_base += TIM2->ATRLR;

    irq_disable();
    uint32_t next = timer_dispatch_many();
    schedule_next(next);
    irq_enable();
}

void
udelay(uint32_t usecs)
{
    uint32_t end = timer_read_time() + usecs;
    while ((int32_t)(timer_read_time() - end) < 0)
        ;
}

void
timer_init(void)
{
    irqstatus_t flag = irq_save();
    RCC->APB1PCENR |= RCC_APB1_TIM2;

    TIM2->PSC = (CONFIG_CLOCK_FREQ / 1000000U) - 1U;
    TIM2->ATRLR = 1000U;
    TIM2->CNT = 0;
    TIM2->DMAINTENR = TIM_UIE;
    TIM2->CTLR1 = TIM_CEN;

    eclic_enable_interrupt(TIM2_IRQn, 1, 1);
    timer_base = 0;
    timer_kick();
    irq_restore(flag);
}
DECL_INIT(timer_init);
