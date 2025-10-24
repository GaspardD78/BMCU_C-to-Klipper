// Placeholder PWM implementation for CH32V20x

#include "command.h"
#include "gpio.h"

struct gpio_pwm
gpio_pwm_setup(uint8_t pin, uint32_t cycle_time, uint32_t val)
{
    (void)pin;
    (void)cycle_time;
    (void)val;
    shutdown("Hardware PWM not yet implemented on CH32V20x");
    return (struct gpio_pwm){ .timer = NULL, .channel = 0 };
}

void
gpio_pwm_write(struct gpio_pwm g, uint32_t val)
{
    (void)g;
    (void)val;
}
