// Hardware PWM implementation for CH32V20x timers

#include "compiler.h"
#include "command.h"
#include "gpio.h"

#define PWM_MAX 0x10000U
DECL_CONSTANT("PWM_MAX", PWM_MAX);

#define AFIO_PCFR1_TIM1_REMAP_MASK      (0x3U << 6)
#define AFIO_PCFR1_TIM1_REMAP_NONE      (0x0U << 6)
#define AFIO_PCFR1_TIM2_REMAP_MASK      (0x3U << 8)
#define AFIO_PCFR1_TIM2_REMAP_NONE      (0x0U << 8)
#define AFIO_PCFR1_TIM2_REMAP_PARTIAL1  (0x1U << 8)
#define AFIO_PCFR1_TIM2_REMAP_PARTIAL2  (0x2U << 8)
#define AFIO_PCFR1_TIM2_REMAP_FULL      (0x3U << 8)
#define AFIO_PCFR1_TIM3_REMAP_MASK      (0x3U << 10)
#define AFIO_PCFR1_TIM3_REMAP_NONE      (0x0U << 10)
#define AFIO_PCFR1_TIM3_REMAP_PARTIAL   (0x1U << 10)
#define AFIO_PCFR1_TIM3_REMAP_FULL      (0x2U << 10)
#define AFIO_PCFR1_TIM4_REMAP_MASK      (1U << 12)
#define AFIO_PCFR1_TIM4_REMAP_NONE      (0x0U << 12)
#define AFIO_PCFR1_TIM4_REMAP_FULL      (1U << 12)

struct gpio_pwm_info {
    TIM_TypeDef *timer;
    uint32_t pin;
    uint8_t channel;
    uint32_t remap_mask;
    uint32_t remap_value;
};

static const struct gpio_pwm_info pwm_map[] = {
#if CONFIG_HAVE_PWM_TIM1
    // TIM1 default mapping (PA8-PA11)
    { TIM1, GPIO('A', 8),  1, AFIO_PCFR1_TIM1_REMAP_MASK, AFIO_PCFR1_TIM1_REMAP_NONE },
    { TIM1, GPIO('A', 9),  2, AFIO_PCFR1_TIM1_REMAP_MASK, AFIO_PCFR1_TIM1_REMAP_NONE },
    { TIM1, GPIO('A', 10), 3, AFIO_PCFR1_TIM1_REMAP_MASK, AFIO_PCFR1_TIM1_REMAP_NONE },
    { TIM1, GPIO('A', 11), 4, AFIO_PCFR1_TIM1_REMAP_MASK, AFIO_PCFR1_TIM1_REMAP_NONE },
#endif

    // TIM2 mappings
    { TIM2, GPIO('A', 0),  1, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_NONE },
    { TIM2, GPIO('A', 1),  2, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_NONE },
    { TIM2, GPIO('A', 2),  3, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_NONE },
    { TIM2, GPIO('A', 3),  4, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_NONE },
    { TIM2, GPIO('A', 15), 1, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_PARTIAL1 },
    { TIM2, GPIO('B', 3),  2, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_PARTIAL1 },
    { TIM2, GPIO('A', 2),  3, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_PARTIAL1 },
    { TIM2, GPIO('A', 3),  4, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_PARTIAL1 },
    { TIM2, GPIO('B', 10), 3, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_FULL },
    { TIM2, GPIO('B', 11), 4, AFIO_PCFR1_TIM2_REMAP_MASK, AFIO_PCFR1_TIM2_REMAP_FULL },

    // TIM3 mappings
    { TIM3, GPIO('A', 6),  1, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_NONE },
    { TIM3, GPIO('A', 7),  2, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_NONE },
    { TIM3, GPIO('B', 0),  3, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_NONE },
    { TIM3, GPIO('B', 1),  4, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_NONE },
    { TIM3, GPIO('B', 4),  1, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_PARTIAL },
    { TIM3, GPIO('B', 5),  2, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_PARTIAL },
    { TIM3, GPIO('B', 0),  3, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_PARTIAL },
    { TIM3, GPIO('B', 1),  4, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_PARTIAL },
    { TIM3, GPIO('C', 6),  1, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_FULL },
    { TIM3, GPIO('C', 7),  2, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_FULL },
    { TIM3, GPIO('C', 8),  3, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_FULL },
    { TIM3, GPIO('C', 9),  4, AFIO_PCFR1_TIM3_REMAP_MASK, AFIO_PCFR1_TIM3_REMAP_FULL },

#if CONFIG_HAVE_PWM_TIM4
    // TIM4 mappings
    { TIM4, GPIO('B', 6),  1, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_NONE },
    { TIM4, GPIO('B', 7),  2, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_NONE },
    { TIM4, GPIO('B', 8),  3, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_NONE },
    { TIM4, GPIO('B', 9),  4, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_NONE },
    { TIM4, GPIO('D', 12), 1, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_FULL },
    { TIM4, GPIO('D', 13), 2, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_FULL },
    { TIM4, GPIO('D', 14), 3, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_FULL },
    { TIM4, GPIO('D', 15), 4, AFIO_PCFR1_TIM4_REMAP_MASK, AFIO_PCFR1_TIM4_REMAP_FULL },
#endif
};

static const struct gpio_pwm_info *
lookup_pwm_info(uint32_t pin)
{
    const struct gpio_pwm_info *p = pwm_map;
    for (; p < &pwm_map[ARRAY_SIZE(pwm_map)]; p++) {
        if (p->pin != pin)
            continue;
        if (p->remap_mask) {
            uint32_t current = AFIO->PCFR1 & p->remap_mask;
            if (current && current != p->remap_value)
                continue;
        }
        return p;
    }
    shutdown("Not a valid PWM pin");
    return NULL;
}

static void
apply_remap(const struct gpio_pwm_info *info)
{
    if (!info->remap_mask)
        return;
    uint32_t current = AFIO->PCFR1 & info->remap_mask;
    if (current && current != info->remap_value)
        shutdown("PWM remap conflict");
    AFIO->PCFR1 = (AFIO->PCFR1 & ~info->remap_mask) | info->remap_value;
}

static uint32_t
compute_timer_period(uint32_t cycle_time, uint32_t *prescaler_out)
{
    if (!cycle_time)
        shutdown("Invalid PWM cycle time");

    uint32_t prescaler = 1;
    uint32_t period = cycle_time;

    if (cycle_time > PWM_MAX) {
        uint32_t limit = DIV_ROUND_UP(cycle_time, PWM_MAX);
        for (uint32_t p = 1; p <= limit; p++) {
            if (cycle_time % p)
                continue;
            uint32_t candidate = cycle_time / p;
            if (candidate <= PWM_MAX) {
                prescaler = p;
                period = candidate;
                break;
            }
        }
        if (period > PWM_MAX) {
            prescaler = limit;
            period = DIV_ROUND_UP(cycle_time, prescaler);
        }
    }

    if (!period)
        period = 1;

    *prescaler_out = prescaler;
    return period;
}

static void
configure_channel(const struct gpio_pwm_info *info)
{
    uint32_t shift = ((info->channel - 1U) % 2U) * 8U;
    volatile uint32_t *ccmr = info->channel <= 2 ? &info->timer->CHCTLR1
                                                : &info->timer->CHCTLR2;
    uint32_t mask = (TIM_CCMR_CC1S_MASK | TIM_CCMR_OC1PE
                     | TIM_CCMR_OC1M_MASK) << shift;
    uint32_t val = *ccmr;
    val &= ~mask;
    val |= (TIM_CCMR_OC1M_PWM1 | TIM_CCMR_OC1PE) << shift;
    *ccmr = val;

    uint32_t ccer_shift = (info->channel - 1U) * 4U;
    info->timer->CCER &= ~(0xFU << ccer_shift);
}

static volatile uint32_t *
channel_ccr(const struct gpio_pwm_info *info)
{
    switch (info->channel) {
    case 1:
        return &info->timer->CH1CVR;
    case 2:
        return &info->timer->CH2CVR;
    case 3:
        return &info->timer->CH3CVR;
    case 4:
        return &info->timer->CH4CVR;
    default:
        shutdown("Invalid PWM channel");
    }
    return NULL;
}

struct gpio_pwm
gpio_pwm_setup(uint8_t pin, uint32_t cycle_time, uint32_t val)
{
    const struct gpio_pwm_info *info = lookup_pwm_info(pin);
    apply_remap(info);
    clock_enable_timer(info->timer);

    uint32_t prescaler;
    uint32_t period = compute_timer_period(cycle_time, &prescaler);
    uint32_t psc_reg = prescaler - 1U;
    uint32_t arr_reg = period - 1U;

    if (info->timer->CTLR1 & TIM_CEN) {
        if (info->timer->PSC != psc_reg || info->timer->ATRLR != arr_reg)
            shutdown("PWM already programmed at different speed");
    } else {
        info->timer->PSC = psc_reg;
        info->timer->ATRLR = arr_reg;
        info->timer->RPTCR = 0;
        info->timer->CTLR1 |= TIM_ARPE;
        info->timer->SWEVGR = TIM_SWEVGR_UG;
    }

    configure_channel(info);
    volatile uint32_t *ccr = channel_ccr(info);

    gpio_peripheral(info->pin,
                    GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_AF_PUSHPULL),
                    0);

    struct gpio_pwm g = {
        .timer = info->timer,
        .ccr = ccr,
        .top = arr_reg,
        .channel = info->channel,
    };

    gpio_pwm_write(g, val);

    info->timer->SWEVGR = TIM_SWEVGR_UG;
    info->timer->CCER |= (TIM_CCER_CC1E << ((info->channel - 1U) * 4U));
    info->timer->CTLR1 |= TIM_CEN;
    if (info->timer == TIM1)
        info->timer->BDTR |= TIM_BDTR_MOE;

    return g;
}

void
gpio_pwm_write(struct gpio_pwm g, uint32_t val)
{
    if (!g.ccr)
        return;
    if (val > g.top)
        val = g.top;
    *g.ccr = val;
}
