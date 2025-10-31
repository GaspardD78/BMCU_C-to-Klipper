// GPIO support for CH32V20x
//
// This file provides a minimal GPIO implementation suitable for
// bringing up Klipper on the WCH CH32V203.

#include <stddef.h>
#include <string.h>
#include "board/irq.h" // irq_save
#include "board/misc.h" // timer_read_time
#include "command.h" // DECL_ENUMERATION_RANGE, shutdown
#include "compiler.h"
#include "gpio.h"
#include "i2ccmds.h" // I2C_BUS_SUCCESS
#include "pins_bmcu_c.h"
#include "sched.h" // sched_shutdown

// Missing I2C status codes
#define I2C_BUS_SUCCESS 0
#define I2C_BUS_NACK -1
#define I2C_BUS_TIMEOUT -2
#define I2C_BUS_START_NACK -3
#define I2C_BUS_START_READ_NACK -4

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

struct i2c_bus_info {
    I2C_TypeDef *regs;
    uint32_t scl_pin;
    uint32_t sda_pin;
    volatile uint32_t *clk_reg;
    uint32_t clk_mask;
};

DECL_ENUMERATION("i2c_bus", "i2c1", 0);
DECL_CONSTANT_STR("BUS_PINS_i2c1", "PB6,PB7");
DECL_ENUMERATION("i2c_bus", "i2c2", 1);
DECL_CONSTANT_STR("BUS_PINS_i2c2", "PB10,PB11");

static const struct i2c_bus_info i2c_buses[] = {
    {
        .regs = I2C1,
        .scl_pin = GPIO('B', 6),
        .sda_pin = GPIO('B', 7),
        .clk_reg = &RCC->APB1PCENR,
        .clk_mask = RCC_APB1_I2C1,
    },
    {
        .regs = I2C2,
        .scl_pin = GPIO('B', 10),
        .sda_pin = GPIO('B', 11),
        .clk_reg = &RCC->APB1PCENR,
        .clk_mask = RCC_APB1_I2C2,
    },
};

static uint32_t
ch32_i2c_get_pclk(void)
{
    static const uint8_t presc_table[8] = { 1, 1, 1, 1, 2, 4, 8, 16 };
    uint32_t presc = (RCC->CFGR0 >> 8) & 0x7U;
    uint32_t divisor = presc_table[presc];
    return CONFIG_CLOCK_FREQ / divisor;
}

struct spi_bus {
    SPI_TypeDef *regs;
    uint32_t sck_pin;
    uint32_t miso_pin;
    uint32_t mosi_pin;
    volatile uint32_t *clk_reg;
    uint32_t clk_mask;
    uint32_t pclk_hz;
};

DECL_ENUMERATION("spi_bus", "spi1", 0);
DECL_CONSTANT_STR("BUS_PINS_spi1", "PA6,PA7,PA5");

static const struct spi_bus spi_bus[] = {
    {
        .regs = SPI1,
        .sck_pin = GPIO('A', 5),
        .miso_pin = GPIO('A', 6),
        .mosi_pin = GPIO('A', 7),
        .clk_reg = &RCC->APB2PCENR,
        .clk_mask = RCC_APB2_SPI1,
        .pclk_hz = CONFIG_CLOCK_FREQ,
    },
};

static void
spi_bus_enable(uint32_t bus)
{
    const struct spi_bus *info = &spi_bus[bus];
    *info->clk_reg |= info->clk_mask;

    static uint8_t initialized[ARRAY_SIZE(spi_bus)];
    if (initialized[bus])
        return;
    initialized[bus] = 1;

    gpio_peripheral(info->miso_pin,
                    GPIO_CONFIG(GPIO_MODE_INPUT, GPIO_CNF_FLOATING), -1);
    gpio_peripheral(info->mosi_pin,
                    GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_AF_PUSHPULL),
                    0);
    gpio_peripheral(info->sck_pin,
                    GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_AF_PUSHPULL),
                    0);

    SPI_TypeDef *spi = info->regs;
    spi->CTLR1 = 0;
    spi->CTLR2 = 0;
}

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
    if (bus >= ARRAY_SIZE(spi_bus))
        shutdown("Invalid spi bus");

    spi_bus_enable(bus);

    const struct spi_bus *info = &spi_bus[bus];
    uint32_t pclk = info->pclk_hz;
    if (!rate || rate > pclk)
        rate = pclk;

    uint32_t br = 0;
    while ((pclk / (1U << (br + 1))) > rate && br < 7)
        br++;

    uint32_t mode_bits = 0;
    if (mode & 0x1)
        mode_bits |= SPI_CTLR1_CPHA;
    if (mode & 0x2)
        mode_bits |= SPI_CTLR1_CPOL;

    uint32_t ctlr1 = mode_bits | (br << SPI_CTLR1_BR_SHIFT)
        | SPI_CTLR1_MSTR | SPI_CTLR1_SSM | SPI_CTLR1_SSI | SPI_CTLR1_SPE;

    return (struct spi_config){ .spi = info->regs, .ctlr1 = ctlr1 };
}

void
spi_prepare(struct spi_config config)
{
    SPI_TypeDef *spi = config.spi;
    uint32_t cur = spi->CTLR1;
    if (cur == config.ctlr1)
        return;

    spi->CTLR1 = cur & ~SPI_CTLR1_SPE;
    spi->CTLR1;
    spi->CTLR1 = config.ctlr1;
}

void
spi_transfer(struct spi_config config, uint8_t receive_data,
             uint8_t len, uint8_t *data)
{
    SPI_TypeDef *spi = config.spi;

    while (spi->STATR & SPI_STATR_RXNE)
        (void)spi->DATAR;

    while (len--) {
        while (!(spi->STATR & SPI_STATR_TXE))
            ;
        uint8_t out = *data;
        *(volatile uint8_t *)&spi->DATAR = out;
        while (!(spi->STATR & SPI_STATR_RXNE))
            ;
        uint8_t in = *(volatile uint8_t *)&spi->DATAR;
        if (receive_data)
            *data = in;
        data++;
    }

    while (spi->STATR & SPI_STATR_BSY)
        ;
}

static int
i2c_wait(I2C_TypeDef *i2c, uint32_t set, uint32_t clear, uint32_t timeout)
{
    while (1) {
        uint32_t star1 = i2c->STAR1;
        if ((star1 & set) == set && (star1 & clear) == 0)
            return I2C_BUS_SUCCESS;
        if (star1 & I2C_STAR1_AF)
            return I2C_BUS_NACK;
        if (!timer_is_before(timer_read_time(), timeout))
            return I2C_BUS_TIMEOUT;
    }
}

static int
i2c_start(I2C_TypeDef *i2c, uint8_t addr, uint8_t xfer_len, uint32_t timeout)
{
    uint32_t wait_end = timeout;
    while (i2c->STAR2 & I2C_STAR2_BUSY) {
        if (!timer_is_before(timer_read_time(), wait_end))
            return I2C_BUS_TIMEOUT;
    }

    i2c->CTLR1 |= I2C_CTLR1_PE;
    i2c->CTLR1 |= I2C_CTLR1_START;

    int ret = i2c_wait(i2c, I2C_STAR1_SB, 0, timeout);
    if (ret != I2C_BUS_SUCCESS)
        return ret;

    if (addr & 0x01 && xfer_len > 1)
        i2c->CTLR1 |= I2C_CTLR1_ACK;

    i2c->DATAR = addr;

    ret = i2c_wait(i2c, I2C_STAR1_ADDR, 0, timeout);
    if (ret != I2C_BUS_SUCCESS)
        return ret;

    irqstatus_t flag = irq_save();
    uint32_t star2 = i2c->STAR2;
    if ((addr & 0x01) && xfer_len == 1)
        i2c->CTLR1 = I2C_CTLR1_STOP | I2C_CTLR1_PE;
    irq_restore(flag);

    if (!(star2 & I2C_STAR2_MSL))
        shutdown("Failed to send i2c addr");

    return ret;
}

static int
i2c_send_byte(I2C_TypeDef *i2c, uint8_t b, uint32_t timeout)
{
    i2c->DATAR = b;
    return i2c_wait(i2c, I2C_STAR1_TXE, 0, timeout);
}

static uint8_t
i2c_read_byte(I2C_TypeDef *i2c, uint32_t timeout, uint8_t remaining)
{
    i2c_wait(i2c, I2C_STAR1_RXNE, 0, timeout);
    irqstatus_t flag = irq_save();
    uint8_t b = i2c->DATAR;
    if (remaining == 1)
        i2c->CTLR1 = I2C_CTLR1_STOP | I2C_CTLR1_PE;
    irq_restore(flag);
    return b;
}

static int
i2c_stop(I2C_TypeDef *i2c, uint32_t timeout)
{
    i2c->CTLR1 = I2C_CTLR1_STOP | I2C_CTLR1_PE;
    return i2c_wait(i2c, 0, I2C_STAR1_TXE, timeout);
}

struct i2c_config
i2c_setup(uint32_t bus, uint32_t rate, uint8_t addr)
{
    if (bus >= ARRAY_SIZE(i2c_buses))
        shutdown("Unsupported i2c bus");

    const struct i2c_bus_info *info = &i2c_buses[bus];
    I2C_TypeDef *i2c = info->regs;

    *info->clk_reg |= info->clk_mask;

    static uint8_t initialized[ARRAY_SIZE(i2c_buses)];
    if (!initialized[bus]) {
        initialized[bus] = 1;
        gpio_peripheral(info->scl_pin,
                        GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_AF_OPENDRAIN),
                        1);
        gpio_peripheral(info->sda_pin,
                        GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_AF_OPENDRAIN),
                        1);

        i2c->CTLR1 = I2C_CTLR1_SWRST;
        i2c->CTLR1 = 0;

        uint32_t pclk = ch32_i2c_get_pclk();
        uint32_t target = rate ? rate : 100000U;
        if (target > 400000U)
            target = 400000U;

        uint32_t freq = pclk / 1000000U;
        if (freq < 2U)
            freq = 2U;
        if (freq > I2C_CTLR2_FREQ_MASK)
            freq = I2C_CTLR2_FREQ_MASK;

        i2c->CTLR2 = freq;

        uint32_t divider = pclk / (target * 2U);
        if (divider < 4U)
            divider = 4U;
        if (divider > 0x0FFFU)
            divider = 0x0FFFU;
        i2c->CKCFGR = divider;
        i2c->RTR = freq + 1U;
    }

    i2c->CTLR1 |= I2C_CTLR1_PE;

    return (struct i2c_config){ .bus = bus, .addr = (addr & 0x7fU) << 1 };
}

int
i2c_write(struct i2c_config config, uint8_t write_len, uint8_t *write)
{
    if (config.bus >= ARRAY_SIZE(i2c_buses))
        return I2C_BUS_TIMEOUT;

    const struct i2c_bus_info *info = &i2c_buses[config.bus];
    I2C_TypeDef *i2c = info->regs;
    uint32_t timeout = timer_read_time() + timer_from_us(5000);

    int ret = i2c_start(i2c, config.addr, write_len, timeout);
    if (ret == I2C_BUS_NACK)
        ret = I2C_BUS_START_NACK;

    while (write_len-- && ret == I2C_BUS_SUCCESS)
        ret = i2c_send_byte(i2c, *write++, timeout);

    int stop_ret = i2c_stop(i2c, timeout);
    if (ret == I2C_BUS_SUCCESS && stop_ret != I2C_BUS_SUCCESS)
        ret = stop_ret;

    return ret;
}

int
i2c_read(struct i2c_config config, uint8_t reg_len, uint8_t *reg,
          uint8_t read_len, uint8_t *read)
{
    if (config.bus >= ARRAY_SIZE(i2c_buses))
        return I2C_BUS_TIMEOUT;

    const struct i2c_bus_info *info = &i2c_buses[config.bus];
    I2C_TypeDef *i2c = info->regs;
    uint32_t timeout = timer_read_time() + timer_from_us(5000);
    uint8_t addr_read = config.addr | 0x01;
    int ret = I2C_BUS_SUCCESS;

    if (reg_len) {
        ret = i2c_start(i2c, config.addr, reg_len, timeout);
        if (ret == I2C_BUS_NACK)
            ret = I2C_BUS_START_NACK;
        while (reg_len-- && ret == I2C_BUS_SUCCESS)
            ret = i2c_send_byte(i2c, *reg++, timeout);
        if (ret != I2C_BUS_SUCCESS)
            goto out;
    }

    ret = i2c_start(i2c, addr_read, read_len, timeout);
    if (ret == I2C_BUS_NACK)
        ret = I2C_BUS_START_READ_NACK;
    if (ret != I2C_BUS_SUCCESS)
        goto out;

    while (read_len--) {
        *read = i2c_read_byte(i2c, timeout, read_len);
        read++;
    }

    return i2c_wait(i2c, 0, I2C_STAR1_RXNE, timeout);

out:
    i2c_stop(i2c, timeout);
    return ret;
}

// ADC functions (stubs for linking)
struct gpio_adc
gpio_adc_setup(uint32_t pin)
{
    shutdown("ADC not supported on this MCU");
    return (struct gpio_adc){0};
}

uint32_t
gpio_adc_sample(struct gpio_adc g)
{
    return 0;
}

uint16_t
gpio_adc_read(struct gpio_adc g)
{
    return 0;
}

void
gpio_adc_cancel_sample(struct gpio_adc g)
{
}

// PWM functions (stubs for linking)
struct gpio_pwm
gpio_pwm_setup(uint8_t pin, uint32_t cycle_time, uint32_t val)
{
    shutdown("PWM not supported on this MCU");
    return (struct gpio_pwm){0};
}

void
gpio_pwm_write(struct gpio_pwm g, uint32_t val)
{
}
