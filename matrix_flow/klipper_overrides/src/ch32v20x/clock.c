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

    // Enable GPIO and mandatory peripheral clocks
    RCC->APB2PCENR |= RCC_APB2_AFIO | RCC_APB2_IOPA | RCC_APB2_IOPB
        | RCC_APB2_IOPC | RCC_APB2_IOPD | RCC_APB2_IOPE;
    RCC->APB1PCENR |= RCC_APB1_TIM2 | RCC_APB1_TIM3 | RCC_APB1_USART2;

    // Optional clocks depend on the board layout / menuconfig toggles.
#if CONFIG_HAVE_PWM_TIM1
    RCC->APB2PCENR |= RCC_APB2_TIM1;
#endif
#if CONFIG_HAVE_PWM_TIM4
    RCC->APB1PCENR |= RCC_APB1_TIM4;
#endif
#if CONFIG_USB
    RCC->APB1PCENR |= RCC_APB1_USB;
#endif

    RCC->APB2PCENR |= RCC_APB2_USART1;
}

void
clock_enable_timer(TIM_TypeDef *timer)
{
    if (timer == TIM2) {
        RCC->APB1PCENR |= RCC_APB1_TIM2;
        return;
    }

    if (timer == TIM3) {
        RCC->APB1PCENR |= RCC_APB1_TIM3;
        return;
    }

#if CONFIG_HAVE_PWM_TIM1
    if (timer == TIM1) {
        RCC->APB2PCENR |= RCC_APB2_TIM1;
        return;
    }
#endif

#if CONFIG_HAVE_PWM_TIM4
    if (timer == TIM4) {
        RCC->APB1PCENR |= RCC_APB1_TIM4;
        return;
    }
#endif
}
