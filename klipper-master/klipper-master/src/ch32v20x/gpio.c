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

DECL_ENUMERATION_RANGE("pin", "PA0", GPIO('A', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PB0", GPIO('B', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PC0", GPIO('C', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PD0", GPIO('D', 0), 16);
DECL_ENUMERATION_RANGE("pin", "PE0", GPIO('E', 0), 16);

static GPIO_TypeDef * const digital_regs[] = {
    ['A' - 'A'] = GPIOA,
    ['B' - 'A'] = GPIOB,
    ['C' - 'A'] = GPIOC,
    ['D' - 'A'] = GPIOD,
    ['E' - 'A'] = GPIOE,
};

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

struct gpio_out
gpio_out_setup(uint32_t pin, uint32_t val)
{
    GPIO_TypeDef *regs = gpio_pin_to_regs(pin);
    gpio_clock_enable(regs);
    struct gpio_out g = { .regs = regs, .bit = GPIO2BIT(pin) };
    gpio_out_reset(g, val);
    return g;
}

void
gpio_out_reset(struct gpio_out g, uint32_t val)
{
    irqstatus_t flag = irq_save();
    if (val)
        g.regs->BSHR = g.bit;
    else
        g.regs->BCR = g.bit;
    uint32_t pin = 0;
    for (size_t i = 0; i < ARRAY_SIZE(digital_regs); i++)
        if (digital_regs[i] == g.regs) {
            pin = GPIO('A' + i, __builtin_ctz(g.bit));
            break;
        }
    gpio_peripheral(pin, GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_GP_PUSHPULL), 0);
    irq_restore(flag);
}

void
gpio_out_toggle_noirq(struct gpio_out g)
{
    g.regs->OUTDR ^= g.bit;
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
    if (val)
        g.regs->BSHR = g.bit;
    else
        g.regs->BCR = g.bit;
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
