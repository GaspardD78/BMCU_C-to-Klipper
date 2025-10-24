#ifndef __CH32V20X_INTERNAL_H
#define __CH32V20X_INTERNAL_H

#include <stdint.h>
#include "autoconf.h"

#define GPIO(PORT, NUM) (((PORT) - 'A') * 16 + (NUM))
#define GPIO2PORT(GPIO) ((GPIO) / 16)
#define GPIO2BIT(GPIO)  (1U << ((GPIO) % 16))

struct gpio_regs {
    volatile uint32_t CFGLR;
    volatile uint32_t CFGHR;
    volatile uint32_t INDR;
    volatile uint32_t OUTDR;
    volatile uint32_t BSHR;
    volatile uint32_t BCR;
    volatile uint32_t LCKR;
};

typedef struct gpio_regs GPIO_TypeDef;

struct rcc_regs {
    volatile uint32_t CTLR;
    volatile uint32_t CFGR0;
    volatile uint32_t INTR;
    volatile uint32_t APB2PRSTR;
    volatile uint32_t APB1PRSTR;
    volatile uint32_t AHBPCENR;
    volatile uint32_t APB2PCENR;
    volatile uint32_t APB1PCENR;
};

typedef struct rcc_regs RCC_TypeDef;

struct afio_regs {
    volatile uint32_t ECFR;
    volatile uint32_t PCFR1;
    volatile uint32_t EXTICR1;
    volatile uint32_t EXTICR2;
    volatile uint32_t EXTICR3;
    volatile uint32_t EXTICR4;
};

typedef struct afio_regs AFIO_TypeDef;

struct tim_regs {
    volatile uint32_t CTLR1;
    volatile uint32_t CTLR2;
    volatile uint32_t SMCFGR;
    volatile uint32_t DMAINTENR;
    volatile uint32_t INTFR;
    volatile uint32_t SWEVGR;
    volatile uint32_t CHCTLR1;
    volatile uint32_t CHCTLR2;
    volatile uint32_t CHIER;
    volatile uint32_t CNT;
    volatile uint32_t PSC;
    volatile uint32_t ATRLR;
    volatile uint32_t RPTCR;
    volatile uint32_t CH1CVR;
    volatile uint32_t CH2CVR;
    volatile uint32_t CH3CVR;
    volatile uint32_t CH4CVR;
};

typedef struct tim_regs TIM_TypeDef;

struct usart_regs {
    volatile uint32_t STATR;
    volatile uint32_t DATAR;
    volatile uint32_t BRR;
    volatile uint32_t CTLR1;
    volatile uint32_t CTLR2;
    volatile uint32_t CTLR3;
    volatile uint32_t GPR;
};

typedef struct usart_regs USART_TypeDef;

struct adc_regs {
    volatile uint32_t STATR;
    volatile uint32_t CTLR1;
    volatile uint32_t CTLR2;
    volatile uint32_t SAMPTR1;
    volatile uint32_t SAMPTR2;
    volatile uint32_t IOFR1;
    volatile uint32_t IOFR2;
    volatile uint32_t IOFR3;
    volatile uint32_t IOFR4;
    volatile uint32_t WDHTR;
    volatile uint32_t WDLTR;
    volatile uint32_t RSQR1;
    volatile uint32_t RSQR2;
    volatile uint32_t RSQR3;
    volatile uint32_t ISQR;
    volatile uint32_t IDATAR1;
    volatile uint32_t IDATAR2;
    volatile uint32_t IDATAR3;
    volatile uint32_t IDATAR4;
    volatile uint32_t RDATAR;
};

typedef struct adc_regs ADC_TypeDef;

#define PERIPH_BASE      0x40000000UL
#define APB1PERIPH_BASE  (PERIPH_BASE + 0x00000)
#define APB2PERIPH_BASE  (PERIPH_BASE + 0x10000)

#define RCC_BASE         (PERIPH_BASE + 0x21000)
#define AFIO_BASE        (APB2PERIPH_BASE + 0x0000)
#define GPIOA_BASE       (APB2PERIPH_BASE + 0x0800)
#define GPIOB_BASE       (APB2PERIPH_BASE + 0x0C00)
#define GPIOC_BASE       (APB2PERIPH_BASE + 0x1000)
#define GPIOD_BASE       (APB2PERIPH_BASE + 0x1400)
#define GPIOE_BASE       (APB2PERIPH_BASE + 0x1800)
#define ADC1_BASE        (APB2PERIPH_BASE + 0x2400)
#define TIM1_BASE        (APB2PERIPH_BASE + 0x2C00)
#define USART1_BASE      (APB2PERIPH_BASE + 0x3800)

#define TIM2_BASE        (APB1PERIPH_BASE + 0x0000)
#define TIM3_BASE        (APB1PERIPH_BASE + 0x0400)
#define TIM4_BASE        (APB1PERIPH_BASE + 0x0800)
#define USART2_BASE      (APB1PERIPH_BASE + 0x4400)
#define USART3_BASE      (APB1PERIPH_BASE + 0x4800)

#define RCC   ((RCC_TypeDef *)RCC_BASE)
#define AFIO  ((AFIO_TypeDef *)AFIO_BASE)
#define GPIOA ((GPIO_TypeDef *)GPIOA_BASE)
#define GPIOB ((GPIO_TypeDef *)GPIOB_BASE)
#define GPIOC ((GPIO_TypeDef *)GPIOC_BASE)
#define GPIOD ((GPIO_TypeDef *)GPIOD_BASE)
#define GPIOE ((GPIO_TypeDef *)GPIOE_BASE)
#define ADC1  ((ADC_TypeDef *)ADC1_BASE)
#define TIM1  ((TIM_TypeDef *)TIM1_BASE)
#define TIM2  ((TIM_TypeDef *)TIM2_BASE)
#define TIM3  ((TIM_TypeDef *)TIM3_BASE)
#define TIM4  ((TIM_TypeDef *)TIM4_BASE)
#define USART1 ((USART_TypeDef *)USART1_BASE)
#define USART2 ((USART_TypeDef *)USART2_BASE)
#define USART3 ((USART_TypeDef *)USART3_BASE)

/* RCC bits */
#define RCC_CTLR_HSION    (1U << 0)
#define RCC_CTLR_HSIRDY   (1U << 1)
#define RCC_CTLR_HSEON    (1U << 16)
#define RCC_CTLR_HSERDY   (1U << 17)
#define RCC_CTLR_PLLON    (1U << 24)
#define RCC_CTLR_PLLRDY   (1U << 25)

#define RCC_CFGR0_SW_HSI  0x00000000U
#define RCC_CFGR0_SW_PLL  0x00000002U
#define RCC_CFGR0_SWS_PLL (0x2U << 2)
#define RCC_CFGR0_HPRE_DIV1 0x00000000U
#define RCC_CFGR0_PPRE1_DIV2 (0x4U << 8)
#define RCC_CFGR0_PPRE2_DIV1 0x00000000U
#define RCC_CFGR0_PLLSRC       (1U << 16)
#define RCC_CFGR0_PLLSRC_HSE   (1U << 16)
#define RCC_CFGR0_PLLMULL_SHIFT 18
#define RCC_CFGR0_PLLMULL_MASK  (0xFU << RCC_CFGR0_PLLMULL_SHIFT)
#define RCC_CFGR0_PLLMULL(val)  (((val) - 2U) << RCC_CFGR0_PLLMULL_SHIFT)

#define RCC_APB2_IOPA   (1U << 2)
#define RCC_APB2_IOPB   (1U << 3)
#define RCC_APB2_IOPC   (1U << 4)
#define RCC_APB2_IOPD   (1U << 5)
#define RCC_APB2_IOPE   (1U << 6)
#define RCC_APB2_AFIO   (1U << 0)
#define RCC_APB2_USART1 (1U << 14)
#define RCC_APB2_ADC1   (1U << 9)

#define RCC_APB1_TIM2   (1U << 0)
#define RCC_APB1_TIM3   (1U << 1)
#define RCC_APB1_TIM4   (1U << 2)
#define RCC_APB1_USART2 (1U << 17)
#define RCC_APB1_USART3 (1U << 18)

/* GPIO configuration helper */
#define GPIO_MODE_INPUT         0x0
#define GPIO_MODE_OUTPUT_10MHZ  0x1
#define GPIO_MODE_OUTPUT_2MHZ   0x2
#define GPIO_MODE_OUTPUT_50MHZ  0x3

#define GPIO_CNF_ANALOG         0x0
#define GPIO_CNF_FLOATING       0x1
#define GPIO_CNF_INPUT_PU_PD    0x2
#define GPIO_CNF_GP_PUSHPULL    0x0
#define GPIO_CNF_GP_OPENDRAIN   0x1
#define GPIO_CNF_AF_PUSHPULL    0x2
#define GPIO_CNF_AF_OPENDRAIN   0x3

#define GPIO_CONFIG(mode, cnf) (((mode) & 0x3) | (((cnf) & 0x3) << 2))

/* Timer helpers */
#define TIM_CEN   (1U << 0)
#define TIM_UIE   (1U << 0)
#define TIM_UIF   (1U << 0)

/* USART bits */
#define USART_CTLR1_RE   (1U << 2)
#define USART_CTLR1_TE   (1U << 3)
#define USART_CTLR1_IDLEIE (1U << 4)
#define USART_CTLR1_RXNEIE (1U << 5)
#define USART_CTLR1_TCIE (1U << 6)
#define USART_CTLR1_TXEIE (1U << 7)
#define USART_CTLR1_UE   (1U << 13)

#define USART_STATR_RXNE (1U << 5)
#define USART_STATR_TXE  (1U << 7)
#define USART_STATR_ORE  (1U << 3)
#define USART_STATR_TC   (1U << 6)

/* Simple ECLIC helpers */
#define ECLIC_BASE        0xE0000000UL
#define ECLIC_CFG         (*(volatile uint8_t *)(ECLIC_BASE + 0x0000))
#define ECLIC_MTH         (*(volatile uint8_t *)(ECLIC_BASE + 0x0004))
#define ECLIC_INT_IP_BASE (ECLIC_BASE + 0x1000)
#define ECLIC_INT_IE_BASE (ECLIC_BASE + 0x1001)
#define ECLIC_INT_ATTR_BASE (ECLIC_BASE + 0x1002)
#define ECLIC_INT_CTRL_BASE (ECLIC_BASE + 0x1003)

static inline void
eclic_enable_interrupt(uint32_t irq, uint8_t level, uint8_t priority)
{
    volatile uint8_t *ie = (volatile uint8_t *)(ECLIC_INT_IE_BASE + irq * 4);
    volatile uint8_t *attr = (volatile uint8_t *)(ECLIC_INT_ATTR_BASE + irq * 4);
    volatile uint8_t *ctrl = (volatile uint8_t *)(ECLIC_INT_CTRL_BASE + irq * 4);
    *attr = 0; // level triggered, positive edge
    *ctrl = (level << 4) | (priority & 0x0f);
    *ie = 1;
}

/* IRQ numbers */
#define TIM2_IRQn   30
#define USART1_IRQn 37

void clock_init(void);
void gpio_init(void);
void timer_init(void);
void serial_init(void);

#define ADC_STATR_EOC       (1U << 1)

#define ADC_CTLR2_ADON      (1U << 0)
#define ADC_CTLR2_CONT      (1U << 1)
#define ADC_CTLR2_CAL       (1U << 2)
#define ADC_CTLR2_RSTCAL    (1U << 3)
#define ADC_CTLR2_EXTTRIG   (1U << 20)
#define ADC_CTLR2_SWSTART   (1U << 22)

#define ADC_RDATAR_DATA_Msk 0x00000FFFU

#endif
