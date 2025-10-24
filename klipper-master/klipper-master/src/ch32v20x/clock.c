// Clock configuration for CH32V20x

#include "internal.h"

void
clock_init(void)
{
    // Enable HSE
    RCC->CTLR |= RCC_CTLR_HSEON;
    while (!(RCC->CTLR & RCC_CTLR_HSERDY))
        ;

    // Disable PLL before reconfiguration
    RCC->CTLR &= ~RCC_CTLR_PLLON;
    while (RCC->CTLR & RCC_CTLR_PLLRDY)
        ;

    // Configure PLL: source HSE, multiplier 12 (12MHz * 12 = 144MHz)
    uint32_t cfgr = RCC->CFGR0;
    cfgr &= ~(RCC_CFGR0_PLLSRC | RCC_CFGR0_PLLMULL_MASK);
    cfgr |= RCC_CFGR0_PLLSRC_HSE | RCC_CFGR0_PLLMULL(12);
    cfgr &= ~(0xFU << 4);
    cfgr |= RCC_CFGR0_PPRE1_DIV2;
    RCC->CFGR0 = cfgr;

    // Enable PLL
    RCC->CTLR |= RCC_CTLR_PLLON;
    while (!(RCC->CTLR & RCC_CTLR_PLLRDY))
        ;

    // Switch SYSCLK to PLL
    cfgr = RCC->CFGR0;
    cfgr &= ~0x3U;
    cfgr |= RCC_CFGR0_SW_PLL;
    RCC->CFGR0 = cfgr;
    while ((RCC->CFGR0 & (0x3U << 2)) != RCC_CFGR0_SWS_PLL)
        ;

    // Enable GPIO and timer clocks we rely on
    RCC->APB2PCENR |= RCC_APB2_AFIO | RCC_APB2_IOPA | RCC_APB2_IOPB
        | RCC_APB2_IOPC;
    RCC->APB1PCENR |= RCC_APB1_TIM2 | RCC_APB1_TIM3 | RCC_APB1_USART2;
    RCC->APB2PCENR |= RCC_APB2_USART1;
}
