// GPIO support for CH32V20x
//
// This file provides a minimal GPIO implementation suitable for
// bringing up Klipper on the WCH CH32V203.

#include <stddef.h>
#include <string.h>
#include "board/irq.h" // irq_save
#include "command.h" // DECL_ENUMERATION_RANGE, shutdown
#include "compiler.h"
#include "gpio.h"
#include "pins_bmcu_c.h"

DECL_ENUMERATION_RANGE("pin", "PA0", GPIO('A', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PB0", GPIO('B', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PC0", GPIO('C', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PD0", GPIO('D', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PE0", GPIO('E', 0), 16);
DECL_ENUMERATION("pin", "AT8236_M1_STEP", BMCU_C_MOTOR1_STEP);
DECL_ENUMERATION("pin", "AT8236_M1_DIR", BMCU_C_MOTOR1_DIR);
DECL_ENUMERATION("pin", "AT8236_M2_STEP", BMCU_C_MOTOR2_STEP);
DECL_ENUMERATION("pin", "AT8236_M2_DIR", BMCU_C_MOTOR2_DIR);
DECL_ENUMERATION("pin", "AT8236_M3_STEP", BMCU_C_MOTOR3_STEP);
DECL_ENUMERATION("pin", "AT8236_M3_DIR", BMCU_C_MOTOR3_DIR);
DECL_ENUMERATION("pin", "AT8236_M4_STEP", BMCU_C_MOTOR4_STEP);
DECL_ENUMERATION("pin", "AT8236_M4_DIR", BMCU_C_MOTOR4_DIR);

static GPIO_TypeDef * const digital_regs[] = {
    ['A' - 'A'] = GPIOA,
    ['B' - 'A'] = GPIOB,
    ['C' - 'A'] = GPIOC,
    ['D' - 'A'] = GPIOD,
    ['E' - 'A'] = GPIOE,
};

#define AT8236_VIRTUAL_BASE     BMCU_C_AT8236_PIN_BASE
#define AT8236_VIRTUAL_MAX      (AT8236_VIRTUAL_BASE \
                                 + BMCU_C_AT8236_PIN_STRIDE * 4)

struct at8236_channel {
    struct gpio_out high_pin;
    struct gpio_out low_pin;
    uint8_t configured;
    uint8_t step_state;
    uint8_t dir_state;
};

static struct at8236_channel at8236_channels[4];

static inline int
is_at8236_virtual(uint32_t pin)
{
    return pin >= AT8236_VIRTUAL_BASE && pin < AT8236_VIRTUAL_MAX;
}

static inline uint8_t
at8236_index(uint32_t pin)
{
    return (pin - AT8236_VIRTUAL_BASE) / BMCU_C_AT8236_PIN_STRIDE;
}

static inline uint8_t
at8236_role(uint32_t pin)
{
    return (pin - AT8236_VIRTUAL_BASE) & 0x1;
}

static void
gpio_clock_enable(GPIO_TypeDef *regs)
{
    if (regs == GPIOA)
        RCC->APB2PCENR |= RCC_APB2_IOPA;
    else if (regs == GPIOB)
        RCC->APB2PCENR |= RCC_APB2_IOPB;
    else if (regs == GPIOC)
        RCC->APB2PCENR |= RCC_APB2_IOPC;
    else if (regs == GPIOD)
        RCC->APB2PCENR |= RCC_APB2_IOPD;
    else if (regs == GPIOE)
        RCC->APB2PCENR |= RCC_APB2_IOPE;
}

static GPIO_TypeDef *
gpio_pin_to_regs(uint32_t pin)
{
    uint32_t port = GPIO2PORT(pin);
    if (port >= ARRAY_SIZE(digital_regs) || !digital_regs[port])
        shutdown("Invalid GPIO");
    return digital_regs[port];
}

static void
configure_pin(GPIO_TypeDef *regs, uint32_t pin, uint32_t config)
{
    uint32_t shift = (pin & 7) * 4;
    volatile uint32_t *cfg = pin < 8 ? &regs->CFGLR : &regs->CFGHR;
    uint32_t mask = 0xFU << shift;
    *cfg = (*cfg & ~mask) | (config << shift);
}

void
gpio_peripheral(uint32_t pin, uint32_t mode, int pull_up)
{
    GPIO_TypeDef *regs = gpio_pin_to_regs(pin);
    uint32_t pnum = pin % 16;
    uint32_t config = mode;
    if (mode == GPIO_CONFIG(GPIO_MODE_INPUT, GPIO_CNF_INPUT_PU_PD)) {
        if (pull_up)
            regs->BSHR = GPIO2BIT(pin);
        else
            regs->BCR = GPIO2BIT(pin);
    }
    configure_pin(regs, pnum, config);
}

void
gpio_init(void)
{
    RCC->APB2PCENR |= RCC_APB2_AFIO | RCC_APB2_IOPA | RCC_APB2_IOPB
        | RCC_APB2_IOPC | RCC_APB2_IOPD | RCC_APB2_IOPE;
    for (size_t i = 0; i < ARRAY_SIZE(digital_regs); i++) {
        if (!digital_regs[i])
            continue;
        digital_regs[i]->CFGLR = 0x44444444U;
        digital_regs[i]->CFGHR = 0x44444444U;
        digital_regs[i]->OUTDR = 0x00000000U;
    }
}

static void
gpio_out_write_hw(struct gpio_out g, uint32_t val)
{
    if (val)
        g.regs->BSHR = g.bit;
    else
        g.regs->BCR = g.bit;
}

static void
gpio_out_toggle_noirq_hw(struct gpio_out g)
{
    g.regs->OUTDR ^= g.bit;
}

static void
gpio_out_reset_hw(struct gpio_out g, uint32_t val)
{
    irqstatus_t flag = irq_save();
    gpio_out_write_hw(g, val);
    uint32_t pin = 0;
    for (size_t i = 0; i < ARRAY_SIZE(digital_regs); i++)
        if (digital_regs[i] == g.regs) {
            pin = GPIO('A' + i, __builtin_ctz(g.bit));
            break;
        }
    gpio_peripheral(pin,
                    GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_GP_PUSHPULL),
                    0);
    irq_restore(flag);
}

static struct gpio_out
gpio_out_setup_hw(uint32_t pin, uint32_t val)
{
    GPIO_TypeDef *regs = gpio_pin_to_regs(pin);
    gpio_clock_enable(regs);
    struct gpio_out g = { .regs = regs, .bit = GPIO2BIT(pin) };
    gpio_out_reset_hw(g, val);
    return g;
}

static void
at8236_apply(struct at8236_channel *ch)
{
    if (!ch->configured)
        return;
    if (ch->step_state) {
        if (ch->dir_state) {
            gpio_out_write_hw(ch->high_pin, 0);
            gpio_out_write_hw(ch->low_pin, 1);
        } else {
            gpio_out_write_hw(ch->high_pin, 1);
            gpio_out_write_hw(ch->low_pin, 0);
        }
    } else {
        gpio_out_write_hw(ch->high_pin, 0);
        gpio_out_write_hw(ch->low_pin, 0);
    }
}

static void
at8236_configure(uint8_t idx)
{
    struct at8236_channel *ch = &at8236_channels[idx];
    if (ch->configured)
        return;
    static const uint32_t high_map[] = {
        BMCU_C_MOTOR1_HIGH,
        BMCU_C_MOTOR2_HIGH,
        BMCU_C_MOTOR3_HIGH,
        BMCU_C_MOTOR4_HIGH,
    };
    static const uint32_t low_map[] = {
        BMCU_C_MOTOR1_LOW,
        BMCU_C_MOTOR2_LOW,
        BMCU_C_MOTOR3_LOW,
        BMCU_C_MOTOR4_LOW,
    };
    ch->high_pin = gpio_out_setup_hw(high_map[idx], 0);
    ch->low_pin = gpio_out_setup_hw(low_map[idx], 0);
    ch->step_state = 0;
    ch->dir_state = 0;
    ch->configured = 1;
}

static struct gpio_out
at8236_setup_pin(uint32_t pin, uint32_t val)
{
    uint8_t idx = at8236_index(pin);
    struct at8236_channel *ch = &at8236_channels[idx];
    at8236_configure(idx);
    if (at8236_role(pin))
        ch->dir_state = !!val;
    else
        ch->step_state = !!val;
    at8236_apply(ch);
    struct gpio_out g = { .regs = NULL, .bit = pin };
    return g;
}

static void
at8236_write(uint32_t pin, uint32_t val)
{
    struct at8236_channel *ch = &at8236_channels[at8236_index(pin)];
    if (at8236_role(pin))
        ch->dir_state = !!val;
    else
        ch->step_state = !!val;
    at8236_apply(ch);
}

static void
at8236_toggle(uint32_t pin)
{
    struct at8236_channel *ch = &at8236_channels[at8236_index(pin)];
    if (at8236_role(pin))
        ch->dir_state ^= 1;
    else
        ch->step_state ^= 1;
    at8236_apply(ch);
}

struct gpio_out
gpio_out_setup(uint32_t pin, uint32_t val)
{
    if (is_at8236_virtual(pin))
        return at8236_setup_pin(pin, val);
    return gpio_out_setup_hw(pin, val);
}

void
gpio_out_reset(struct gpio_out g, uint32_t val)
{
    if (!g.regs && is_at8236_virtual(g.bit)) {
        at8236_write(g.bit, val);
        return;
    }
    gpio_out_reset_hw(g, val);
}

void
gpio_out_toggle_noirq(struct gpio_out g)
{
    if (!g.regs && is_at8236_virtual(g.bit)) {
        at8236_toggle(g.bit);
        return;
    }
    gpio_out_toggle_noirq_hw(g);
}

void
gpio_out_toggle(struct gpio_out g)
{
    irqstatus_t flag = irq_save();
    gpio_out_toggle_noirq(g);
    irq_restore(flag);
}

void
gpio_out_write(struct gpio_out g, uint32_t val)
{
    if (!g.regs && is_at8236_virtual(g.bit)) {
        at8236_write(g.bit, val);
        return;
    }
    gpio_out_write_hw(g, val);
}

struct gpio_in
gpio_in_setup(uint32_t pin, int32_t pull_up)
{
    GPIO_TypeDef *regs = gpio_pin_to_regs(pin);
    struct gpio_in g = { .regs = regs, .bit = GPIO2BIT(pin) };
    gpio_in_reset(g, pull_up);
    return g;
}

void
gpio_in_reset(struct gpio_in g, int32_t pull_up)
{
    uint32_t mode = GPIO_CONFIG(GPIO_MODE_INPUT, GPIO_CNF_FLOATING);
    if (pull_up >= 0)
        mode = GPIO_CONFIG(GPIO_MODE_INPUT, GPIO_CNF_INPUT_PU_PD);
    uint32_t pin = 0;
    for (size_t i = 0; i < ARRAY_SIZE(digital_regs); i++)
        if (digital_regs[i] == g.regs) {
            pin = GPIO('A' + i, __builtin_ctz(g.bit));
            break;
        }
    gpio_peripheral(pin, mode, pull_up);
}

uint8_t
gpio_in_read(struct gpio_in g)
{
    return !!(g.regs->INDR & g.bit);
}

struct spi_config
spi_setup(uint32_t bus, uint8_t mode, uint32_t rate)
{
    (void)bus;
    (void)mode;
    (void)rate;
    struct spi_config cfg = { .bus = 0 };
    shutdown("SPI not yet implemented on CH32V20x");
    return cfg;
}

void
spi_prepare(struct spi_config config)
{
    (void)config;
}

void
spi_transfer(struct spi_config config, uint8_t receive_data,
             uint8_t len, uint8_t *data)
{
    (void)config;
    (void)receive_data;
    (void)len;
    (void)data;
}

struct i2c_config
i2c_setup(uint32_t bus, uint32_t rate, uint8_t addr)
{
    (void)bus;
    (void)rate;
    struct i2c_config cfg = { .bus = 0, .addr = addr };
    shutdown("I2C not yet implemented on CH32V20x");
    return cfg;
}

int
i2c_write(struct i2c_config config, uint8_t write_len, uint8_t *write)
{
    (void)config;
    (void)write_len;
    (void)write;
    return -1;
}

int
i2c_read(struct i2c_config config, uint8_t reg_len, uint8_t *reg,
          uint8_t read_len, uint8_t *read)
{
    (void)config;
    (void)reg_len;
    (void)reg;
    (void)read_len;
    (void)read;
    return -1;
}
