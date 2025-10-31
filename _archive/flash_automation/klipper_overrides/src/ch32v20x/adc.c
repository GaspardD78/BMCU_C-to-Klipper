// Basic ADC driver for CH32V20x

#include "command.h"
#include "compiler.h"
#include "gpio.h"
#include "sched.h" // sched_shutdown

DECL_CONSTANT("ADC_MAX", 4095);

static const uint8_t adc_pin_map[] = {
    GPIO('A', 0), GPIO('A', 1), GPIO('A', 2), GPIO('A', 3),
    GPIO('A', 4), GPIO('A', 5), GPIO('A', 6), GPIO('A', 7),
    GPIO('B', 0), GPIO('B', 1),
    GPIO('C', 0), GPIO('C', 1), GPIO('C', 2), GPIO('C', 3),
    GPIO('C', 4), GPIO('C', 5),
};

static uint8_t adc_initialized;

static void
adc_init_once(void)
{
    if (adc_initialized)
        return;
    adc_initialized = 1;

    RCC->APB2PCENR |= RCC_APB2_ADC1;

    // Reset and calibrate the ADC
    ADC1->CTLR2 |= ADC_CTLR2_RSTCAL;
    while (ADC1->CTLR2 & ADC_CTLR2_RSTCAL)
        ;
    ADC1->CTLR2 |= ADC_CTLR2_CAL;
    while (ADC1->CTLR2 & ADC_CTLR2_CAL)
        ;

    // Configure a long sample time on all channels to improve accuracy
    const uint32_t sample_bits = 7U; // 239.5 cycles on STM32F1-compatible ADC
    uint32_t smpr2 = 0;
    for (int i = 0; i < 10; i++)
        smpr2 |= sample_bits << (i * 3);
    uint32_t smpr1 = 0;
    for (int i = 0; i < 8; i++)
        smpr1 |= sample_bits << (i * 3);
    ADC1->SAMPTR2 = smpr2;
    ADC1->SAMPTR1 = smpr1;

    ADC1->RSQR1 = 0;
    ADC1->RSQR2 = 0;

    // Power on the ADC block
    ADC1->CTLR2 |= ADC_CTLR2_ADON;
}

struct gpio_adc
gpio_adc_setup(uint32_t pin)
{
    adc_init_once();

    int chan;
    for (chan = 0; chan < ARRAY_SIZE(adc_pin_map); chan++) {
        if (adc_pin_map[chan] == pin)
            break;
    }
    if (chan >= ARRAY_SIZE(adc_pin_map))
        shutdown("Not a valid ADC pin");

    gpio_peripheral(pin,
                    GPIO_CONFIG(GPIO_MODE_INPUT, GPIO_CNF_ANALOG),
                    0);

    return (struct gpio_adc){ .channel = chan };
}

uint32_t
gpio_adc_sample(struct gpio_adc g)
{
    if (ADC1->STATR & ADC_STATR_EOC)
        (void)ADC1->RDATAR;
    ADC1->RSQR3 = g.channel;

    // Start conversion and poll until completion
    ADC1->CTLR2 |= ADC_CTLR2_ADON;
    while (!(ADC1->STATR & ADC_STATR_EOC))
        ;

    return ADC1->RDATAR & ADC_RDATAR_DATA_Msk;
}

uint16_t
gpio_adc_read(struct gpio_adc g)
{
    (void)g;
    uint16_t value = ADC1->RDATAR & ADC_RDATAR_DATA_Msk;
    return value;
}

void
gpio_adc_cancel_sample(struct gpio_adc g)
{
    (void)g;
    if (ADC1->STATR & ADC_STATR_EOC)
        (void)ADC1->RDATAR;
    ADC1->CTLR2 &= ~ADC_CTLR2_ADON;
}
