// Minimal USART1 driver for CH32V20x

#include "autoconf.h"
#include "command.h"
#include "generic/serial_irq.h"
#include "gpio.h"
#include "internal.h"
#include "sched.h"

#if CONFIG_CH32V20X_SERIAL1
  DECL_CONSTANT_STR("RESERVE_PINS_serial", "PA10,PA9");
  #define GPIO_Rx GPIO('A', 10)
  #define GPIO_Tx GPIO('A', 9)
  #define USARTx USART1
  #define USARTx_IRQn USART1_IRQn
#else
  #error "Only USART1 is supported on CH32V20x"
#endif

#define CTLR1_FLAGS (USART_CTLR1_UE | USART_CTLR1_RE | USART_CTLR1_TE \
                     | USART_CTLR1_RXNEIE)

void
USART1_IRQHandler(void)
{
    uint32_t sr = USARTx->STATR;
    if (sr & (USART_STATR_RXNE | USART_STATR_ORE))
        serial_rx_byte(USARTx->DATAR);
    if ((sr & USART_STATR_TXE) && (USARTx->CTLR1 & USART_CTLR1_TXEIE)) {
        uint8_t data;
        if (serial_get_tx_byte(&data))
            USARTx->CTLR1 = CTLR1_FLAGS;
        else
            USARTx->DATAR = data;
    }
}

void
serial_enable_tx_irq(void)
{
    USARTx->CTLR1 = CTLR1_FLAGS | USART_CTLR1_TXEIE;
}

void
serial_init(void)
{
    RCC->APB2PCENR |= RCC_APB2_USART1;

    uint32_t div = CONFIG_CLOCK_FREQ / CONFIG_SERIAL_BAUD;
    USARTx->BRR = div;
    USARTx->CTLR1 = CTLR1_FLAGS;

    gpio_peripheral(GPIO_Rx,
                    GPIO_CONFIG(GPIO_MODE_INPUT, GPIO_CNF_INPUT_PU_PD), 1);
    gpio_peripheral(GPIO_Tx,
                    GPIO_CONFIG(GPIO_MODE_OUTPUT_50MHZ, GPIO_CNF_AF_PUSHPULL), 0);

    eclic_enable_interrupt(USARTx_IRQn, 1, 2);
}
DECL_INIT(serial_init);
