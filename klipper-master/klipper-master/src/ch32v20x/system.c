// System initialization helpers for CH32V20x

#include "internal.h"

uint32_t SystemCoreClock = CONFIG_CLOCK_FREQ;

void
SystemInit(void)
{
    // Configure vector controller for direct mode
    ECLIC_CFG = 0; // level mode, nlbits = 0
    ECLIC_MTH = 0;

    // Ensure clocks are in a known state
    RCC->CTLR |= RCC_CTLR_HSION;
    while (!(RCC->CTLR & RCC_CTLR_HSIRDY))
        ;

    // Configure PLL via clock_init(); SystemCoreClock is constant here.
    SystemCoreClock = CONFIG_CLOCK_FREQ;
}
