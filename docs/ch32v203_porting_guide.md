# Portage du CH32V203 dans Klipper

Ce guide détaille les principales étapes nécessaires pour ajouter la famille de microcontrôleurs **WCH CH32V20x** (cœur RISC-V) au firmware **Klipper**. Il s'appuie sur les conventions internes de Klipper et sur la documentation publique fournie par WCH pour les registres du CH32V203C8T6.

> ⚠️ Les exemples ci-dessous ciblent explicitement le CH32V203C8T6 utilisé sur la carte BMCU-C. Adaptez les valeurs d'horloge et de taille mémoire si vous ciblez un autre membre de la famille CH32V20x.

## 1. Préparer l'environnement

1. Installer une toolchain RISC-V bare-metal (GCC >= 12) :

   ```bash
   sudo apt-get install gcc-riscv-none-elf g++-riscv-none-elf binutils-riscv-none-elf
   ```

2. Récupérer les en-têtes publics de WCH (`ch32v20x.h`, `core_riscv.h`, `system_ch32v20x.c`). Ils sont disponibles dans le paquet « EVT » de WCH et peuvent être importés dans `lib/ch32v20x/`.

3. Compiler et flasher un exemple bare-metal WCH afin de valider la chaîne de compilation (blinky sur GPIOC PC13 par exemple). Cette étape permet de vérifier que l'interface SWD/JTAG fonctionne.

## 2. Ajouter une nouvelle architecture bas niveau

### 2.1 Kconfig

Déclarez une nouvelle entrée dans `src/Kconfig` afin que Klipper puisse sélectionner la famille CH32V20x :

```diff
 choice
     prompt "Micro-controller Architecture"
+    config MACH_CH32V20X
+        bool "WCH CH32V20x (RISC-V)"
     config MACH_AVR
         bool "Atmega AVR"
```

Puis créez `src/ch32v20x/Kconfig` :

```ini
if MACH_CH32V20X

config CH32V20X_SELECT
    bool
    default y
    select HAVE_GPIO
    select HAVE_GPIO_ADC
    select HAVE_GPIO_SPI
    select HAVE_GPIO_I2C
    select HAVE_GPIO_HARD_PWM
    select HAVE_STRICT_TIMING
    select HAVE_CHIPID

config BOARD_DIRECTORY
    string
    default "ch32v20x"

config MCU
    string "Modèle exact"
    default "ch32v203"

config CLOCK_FREQ
    int
    default 144000000

config FLASH_SIZE
    hex
    default 0x10000

config RAM_SIZE
    hex
    default 0x5000

choice
    prompt "Interface de communication"
    config CH32V20X_SERIAL1
        bool "USART1 (PA9/PA10)"
        select SERIAL
    config CH32V20X_USB
        bool "USB FS (PA11/PA12)" if LOW_LEVEL_OPTIONS
        select USBSERIAL
endchoice

endif
```

### 2.2 Règles de compilation

Créez `src/ch32v20x/Makefile` pour définir la toolchain et les sources :

```make
CROSS_PREFIX = riscv-none-elf-

# Ajouter les dossiers à la variable globale `dirs-y`
dirs-y += src/ch32v20x src/generic lib/ch32v20x

# Options de compilation spécifiques
CFLAGS += -march=rv32imac -mabi=ilp32 -mcmodel=medany -ffunction-sections -fdata-sections
CFLAGS += -Ilib/ch32v20x -DCH32V20X -Os

# Fichiers sources
src-y += generic/riscv_start.S generic/riscv_irq.c
src-y += ch32v20x/main.c ch32v20x/clock.c ch32v20x/gpio.c ch32v20x/timer.c
src-y += ch32v20x/serial.c ch32v20x/adc.c ch32v20x/hard_pwm.c ch32v20x/system.c

# Gestion du bootloader (linker script)
CFLAGS_klipper.elf += -nostdlib -T $(OUT)src/ch32v20x/ch32v20x_link.ld -Wl,--gc-sections -lgcc
```

Le fichier `generic/riscv_start.S` initialise la pile, configure la table d'interruptions ECLIC et appelle `riscv_main()` (à définir dans `ch32v20x/main.c`). Un exemple minimal :

```asm
.section .init
.globl _start
_start:
    la sp, _stack_top
    call riscv_main
1:  j 1b
```

## 3. Implémenter les couches matérielles

### 3.1 Initialisation principale (`main.c`)

```c
#include "autoconf.h"
#include "sched.h"
#include "board/misc.h"
#include "internal.h"

extern void SystemInit(void);

void __attribute__((noreturn)) riscv_main(void)
{
    SystemInit();              // Configure PLL à 144 MHz
    clock_init();              // Active les horloges des périphériques de base
    gpio_init();               // Met les GPIO dans un état sûr
    timer_init();              // Lance SysTick/TIM2 pour la planification
    serial_init();             // Prépare l'interface USART ou USB
    sched_main();              // Boucle principale Klipper
    for (;;)
        ;
}
```

### 3.2 Gestion des horloges (`clock.c`)

```c
#include "internal.h"
#include "ch32v20x_rcc.h"

void clock_init(void)
{
    // Active HSE 12 MHz, puis configure PLL à 144 MHz (12 MHz * 12)
    RCC->CTLR |= RCC_HSEON;
    while (!(RCC->CTLR & RCC_HSERDY))
        ;

    // Reset PLL
    RCC->CTLR &= ~RCC_PLLON;

    // Source PLL = HSE, multiplicateur = 12
    RCC->CFGR0 = (RCC->CFGR0 & ~(RCC_PLLSRC | RCC_PLLMULL))
               | RCC_PLLSRC_HSE | RCC_PLLMULL12;

    RCC->CTLR |= RCC_PLLON;
    while (!(RCC->CTLR & RCC_PLLRDY))
        ;

    // Sélectionne PLL comme SYSCLK
    RCC->CFGR0 = (RCC->CFGR0 & ~RCC_SW) | RCC_SW_PLL;
    while ((RCC->CFGR0 & RCC_SWS) != RCC_SWS_PLL)
        ;

    // Active les bus APB
    RCC->APB2PCENR |= RCC_APB2_IOPA | RCC_APB2_IOPB | RCC_APB2_IOPC | RCC_APB2_AFIO;
    RCC->APB1PCENR |= RCC_APB1_TIM2 | RCC_APB1_USART2;
}
```

> ℹ️ Les horloges optionnelles sont désormais gouvernées par les drapeaux
> `CONFIG_HAVE_PWM_TIM1`/`CONFIG_HAVE_PWM_TIM4` (exposés dans `make menuconfig`
> quand `LOW_LEVEL_OPTIONS` est activé). `clock_init()` n'active `TIM1` et
> `TIM4` que si ces options sont cochées, ce qui évite d'alimenter des blocs
> matériels inutilisés. De même, sélectionner l'interface USB (`CH32V20X_USB`
> ou toute option qui implique `CONFIG_USB`) provoque l'activation de
> `RCC_APB1_USB`.

### 3.3 GPIO (`gpio.c`)

Exposez `gpio_set_mode()` et `gpio_read()` en utilisant la structure des ports STM32F1 (registres `CRL/CRH`, `ODR`, `IDR`). L'initialisation par défaut peut forcer tous les ports en entrée flottante pour minimiser la consommation.

### 3.4 Timer système (`timer.c`)

Utilisez TIM2 comme source d'interruption toutes les 0,00025 s (4 kHz) pour la planification Klipper :

```c
void timer_init(void)
{
    RCC->APB1PCENR |= RCC_APB1_TIM2;
    TIM2->PSC = (CONFIG_CLOCK_FREQ / 1000000) - 1; // Tick à 1 MHz
    TIM2->ATRLR = 250;                              // 250 µs
    TIM2->DMAINTENR |= TIM_UIE;
    TIM2->CTLR1 |= TIM_CEN;
    eclic_enable_interrupt(TIM2_IRQn, 1, 1);
}

void TIM2_IRQHandler(void)
{
    TIM2->INTFR = ~TIM_UIF;
    sched_timer_dispatch();
}
```

### 3.5 Série (`serial.c`)

Pour l'USART1 (port RS-485 du BMCU-C) :

```c
void serial_init(void)
{
    RCC->APB2PCENR |= RCC_APB2_USART1;
    AFIO->PCFR1 |= AFIO_PCFR1_USART1_REMAP; // si nécessaire
    USART1->BRR = CONFIG_CLOCK_FREQ / CONFIG_SERIAL_BAUD;
    USART1->CTLR1 = USART_CTLR1_RE | USART_CTLR1_TE | USART_CTLR1_UE;
    eclic_enable_interrupt(USART1_IRQn, 1, 2);
}

void USART1_IRQHandler(void)
{
    uint16_t sr = USART1->STATR;
    if (sr & USART_STATR_RXNE)
        serial_rx_push(USART1->DATAR);
    if (sr & USART_STATR_TXE)
        serial_tx_pop();
}
```

### 3.6 ADC / PWM

* ADC : configurez ADC1 pour conversion simple sur les voies `ISENx` et `HALL_RC`. Utilisez le driver générique Klipper (`adc_sample()`).
* PWM matériel : TIM3/TIM4 peuvent générer les signaux de commande pour les AT8236. Implémentez `pwm_set_frequency()` et `pwm_set_duty_cycle()`.

## 4. Linker script

Créez `src/ch32v20x/ch32v20x_link.lds.S` pour placer le code au début de la flash et initialiser la RAM :

```ld
MEMORY
{
    FLASH (rx) : ORIGIN = 0x00000000, LENGTH = CONFIG_FLASH_SIZE
    RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = CONFIG_RAM_SIZE
}

ENTRY(_start)

SECTIONS
{
    .text : {
        *(.init)
        *(.text*)
        *(.rodata*)
    } > FLASH

    .data : AT (ADDR(.text) + SIZEOF(.text)) {
        _sdata = .;
        *(.data*)
        _edata = .;
    } > RAM

    .bss (NOLOAD) : {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        _ebss = .;
    } > RAM

    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
}
```

## 5. Ajouter une configuration de carte BMCU-C

Créez `config/boards/bmcu_c.cfg` pour documenter le mapping des broches :

```ini
[mcu bmcu]
serial: /dev/serial/by-id/usb-klipper_ch32v203-if00
restart_method: command

[board_pins bmcu]
aliases:
    motor1_h=PB5, motor1_l=PB4,
    motor2_h=PB3, motor2_l=PB2,
    motor3_h=PB1, motor3_l=PB0,
    motor4_h=PA7, motor4_l=PA6,
    hall_in=PA0,
    rs485_de=PA8, rs485_re=PA9,
    led_status=PA1
```

## 6. Tests

1. **Compilation** : lancer `make menuconfig` → sélectionner « WCH CH32V20x » puis `make`. Corriger les erreurs de compilation jusqu'à obtenir `out/klipper.elf`.
2. **Flash** : utiliser `wchisp` ou `openocd` avec l'adaptateur WCH-Link. Exemple `wchisp flash out/klipper.bin`.
3. **Bring-up** : activer les GPIO en toggling une LED, vérifier la trame UART via un convertisseur USB/TTL.
4. **Intégration Klipper** : déclarer le MCU secondaire dans `printer.cfg`, vérifier que `STATUS` remonte correctement et que les moteurs répondent à `MANUAL_STEPPER`.

## 7. Ressources complémentaires

* [WCH CH32V20x Reference Manual](https://www.wch-ic.com/downloads/CH32V20xRM_PDF.html)
* [Projet open-source `ch32v203c8t6-rs485`](https://github.com/openwch/ch32v20x) (exemples d'initialisation UART/RS485)
* [Port Klipper pour GD32VF103](https://github.com/btt-skr/Klipper) – architecture RISC-V proche, utile pour comparer la gestion des interruptions ECLIC et des timers.

En suivant ces étapes, vous disposez d'une base complète pour apporter le support du CH32V203 à Klipper. Il reste à implémenter précisément chaque pilote (ADC, PWM, UART) en fonction des besoins matériels de la carte BMCU-C.
