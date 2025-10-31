# Build rules for WCH CH32V20x (RISC-V)

CROSS_PREFIX=riscv-none-elf-

dirs-y += src/ch32v20x src/generic

CFLAGS += -march=rv32imac_zicsr -mabi=ilp32 -mcmodel=medany
CFLAGS += -ffunction-sections -fdata-sections -fno-common
CFLAGS += -Isrc/ch32v20x -Isrc/generic -DCH32V20X

src-y += generic/riscv_start.S generic/riscv_irq.c generic/timer_irq.c
src-y += generic/crc16_ccitt.c generic/alloc.c generic/stdlib.c generic/setjmp.c
src-y += generic/byteswap_compat.c generic/ctz_compat.c
src-y += ch32v20x/system.c ch32v20x/main.c ch32v20x/clock.c
src-y += ch32v20x/gpio.c ch32v20x/timer.c
src-$(CONFIG_SERIAL) += ch32v20x/usart.c generic/serial_irq.c
src-$(CONFIG_WANT_ADC) += ch32v20x/adc.c
src-$(CONFIG_WANT_HARD_PWM) += ch32v20x/hard_pwm.c

# Linker script preprocessing
src-y += ch32v20x/ch32v20x_link.lds.S

CFLAGS_klipper.elf += -nostdlib -Wl,--gc-sections
CFLAGS_klipper.elf += -T $(OUT)src/ch32v20x/ch32v20x_link.ld
CFLAGS_klipper.elf += -Wl,-melf32lriscv

$(OUT)klipper.elf: $(OUT)src/ch32v20x/ch32v20x_link.ld

# Binary output
target-y += $(OUT)klipper.bin

$(OUT)klipper.bin: $(OUT)klipper.elf
	@echo "  Creating bin file $@"
	$(Q)$(OBJCOPY) -O binary $< $@

flash: $(OUT)klipper.bin
	@if ! command -v $(CROSS_PREFIX)gcc >/dev/null 2>&1; then \
		echo "Le compilateur '$(CROSS_PREFIX)gcc' est introuvable."; \
		echo "Veuillez l'installer via votre gestionnaire de paquets (ex: sudo apt install gcc-riscv32-unknown-elf)"; \
		exit 1; \
	fi
	@if [ -z "$(FLASH_DEVICE)" ]; then \
		echo "Please specify FLASH_DEVICE=wch-link-swd ou FLASH_DEVICE=/dev/ttyUSBx"; \
		exit 1; \
	fi
	@if ! command -v wchisp >/dev/null 2>&1; then \
		echo "L'outil 'wchisp' est introuvable. Installez-le via 'pip3 install wchisp'."; \
		exit 1; \
	fi
	@echo "  Flashing $< to $(FLASH_DEVICE) via wchisp"
	$(Q)cmd="wchisp flash $< --chip ch32v203 --device \"$(FLASH_DEVICE)\""; \
	if [ -n "$(FLASH_BAUD)" ]; then \
		cmd="$$cmd --baud $(FLASH_BAUD)"; \
	fi; \
	if [ -n "$(FLASH_EXTRA_OPTS)" ]; then \
		cmd="$$cmd $(FLASH_EXTRA_OPTS)"; \
	fi; \
	eval "$$cmd"
