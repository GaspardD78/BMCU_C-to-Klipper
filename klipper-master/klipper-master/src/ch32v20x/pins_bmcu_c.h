#ifndef __CH32V20X_PINS_BMCU_C_H
#define __CH32V20X_PINS_BMCU_C_H

#include "internal.h"

// Convenience aliases for the BMCU-C mainboard pinout.
// The names follow the signal labels used in the original schematic.

// RS-485 transceiver and debug header
#define BMCU_C_RS485_TX          GPIO('A', 9)
#define BMCU_C_RS485_RX          GPIO('A', 10)
#define BMCU_C_RS485_DE          GPIO('A', 12)
#define BMCU_C_DEBUG_SWCLK       GPIO('A', 14)
#define BMCU_C_DEBUG_SWDIO       GPIO('A', 13)
#define BMCU_C_DEBUG_EXIT_TX     GPIO('B', 10)
#define BMCU_C_DEBUG_EXIT_RX     GPIO('B', 11)

// WS2812B status LED and light pipe outputs
#define BMCU_C_STATUS_LED        GPIO('D', 1)
#define BMCU_C_RGB_OUT1          GPIO('B', 0)
#define BMCU_C_RGB_OUT2          GPIO('B', 1)
#define BMCU_C_RGB_OUT3          GPIO('A', 8)
#define BMCU_C_RGB_OUT4          GPIO('A', 11)

// Motor phase controls (inputs of the four AT8236 drivers)
#define BMCU_C_MOTOR1_HIGH       GPIO('A', 15)
#define BMCU_C_MOTOR1_LOW        GPIO('B', 3)
#define BMCU_C_MOTOR2_HIGH       GPIO('B', 4)
#define BMCU_C_MOTOR2_LOW        GPIO('B', 5)
#define BMCU_C_MOTOR3_HIGH       GPIO('B', 6)
#define BMCU_C_MOTOR3_LOW        GPIO('B', 7)
#define BMCU_C_MOTOR4_HIGH       GPIO('B', 8)
#define BMCU_C_MOTOR4_LOW        GPIO('B', 9)

// Spool sensor buses (one I2C pair plus two sense lines per channel)
#define BMCU_C_SPOOL1_SDA        GPIO('C', 13)
#define BMCU_C_SPOOL1_SCL        GPIO('B', 12)
#define BMCU_C_SPOOL1_PULL       GPIO('A', 0)
#define BMCU_C_SPOOL1_ONLINE     GPIO('A', 1)

#define BMCU_C_SPOOL2_SDA        GPIO('C', 14)
#define BMCU_C_SPOOL2_SCL        GPIO('B', 13)
#define BMCU_C_SPOOL2_PULL       GPIO('A', 2)
#define BMCU_C_SPOOL2_ONLINE     GPIO('A', 3)

#define BMCU_C_SPOOL3_SDA        GPIO('C', 15)
#define BMCU_C_SPOOL3_SCL        GPIO('B', 14)
#define BMCU_C_SPOOL3_PULL       GPIO('A', 4)
#define BMCU_C_SPOOL3_ONLINE     GPIO('A', 5)

#define BMCU_C_SPOOL4_SDA        GPIO('D', 0)
#define BMCU_C_SPOOL4_SCL        GPIO('B', 15)
#define BMCU_C_SPOOL4_PULL       GPIO('A', 6)
#define BMCU_C_SPOOL4_ONLINE     GPIO('A', 7)

#endif // __CH32V20X_PINS_BMCU_C_H
