// Placeholder ADC driver for CH32V20x

#include "command.h"
#include "gpio.h"

struct gpio_adc
gpio_adc_setup(uint32_t pin)
{
    (void)pin;
    struct gpio_adc adc = { .channel = 0 };
    shutdown("ADC not yet implemented on CH32V20x");
    return adc;
}

uint32_t
gpio_adc_sample(struct gpio_adc g)
{
    (void)g;
    return 0;
}

uint16_t
gpio_adc_read(struct gpio_adc g)
{
    (void)g;
    return 0;
}

void
gpio_adc_cancel_sample(struct gpio_adc g)
{
    (void)g;
}
