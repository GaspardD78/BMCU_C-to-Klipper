# Build rules for WCH CH32V20x (RISC-V)

CROSS_PREFIX=riscv-none-elf-

dirs-y += src/ch32v20x src/generic

CFLAGS += -march=rv32imac -mabi=ilp32 -mcmodel=medany
CFLAGS += -ffunction-sections -fdata-sections -fno-common
CFLAGS += -Isrc/ch32v20x -DCH32V20X

src-y += generic/riscv_start.S generic/riscv_irq.c generic/timer_irq.c
src-y += ch32v20x/system.c ch32v20x/main.c ch32v20x/clock.c
src-y += ch32v20x/gpio.c ch32v20x/timer.c
src-$(CONFIG_SERIAL) += ch32v20x/usart.c generic/serial_irq.c
src-$(CONFIG_WANT_ADC) += ch32v20x/adc.c
src-$(CONFIG_WANT_HARD_PWM) += ch32v20x/hard_pwm.c

# Linker script preprocessing
src-y += ch32v20x/ch32v20x_link.lds.S

CFLAGS_klipper.elf += -nostdlib -Wl,--gc-sections
CFLAGS_klipper.elf += -T $(OUT)src/ch32v20x/ch32v20x_link.ld -lgcc

# Binary output
target-y += $(OUT)klipper.bin

$(OUT)klipper.bin: $(OUT)klipper.elf
@echo "  Creating bin file $@"
$(Q)$(OBJCOPY) -O binary $< $@
