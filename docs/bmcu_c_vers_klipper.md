# Adapter le BMCU-C pour Klipper

Ce document propose une démarche pour porter le circuit imprimé **BMCU-C** (contrôleur multi-couleurs d'origine Bambu) sur le firmware **Klipper**, afin de piloter le buffer et les capteurs de filament avec une imprimante non Bambu.

## 1. Comprendre le matériel disponible

### 1.1 Cartographie générale

* **Microcontrôleur** : la carte principale s'appuie sur un `CH32V203C8T6` (cœur RISC-V à 144 MHz, 64 Ko de flash, 20 Ko de RAM). 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L396-L500】
* **Pilotes moteurs** : quatre ponts en H `AT8236` gèrent directement les bobines des moteurs 370 du buffer (senses de courant de 680 mΩ par canal). 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L1342-L1500】
* **Communication** : un transceiver `TP75176E-SR` assure le lien différentiel RS‑485 qui relie habituellement le BMCU à l'imprimante/hub. 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L114-L146】【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L1740-L1827】
* **Alimentation** : une chaîne `TPS54202` + inductance 10 µH crée l'alimentation 5 V/3,3 V à partir du 24 V du bus. 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L820-L900】
* **Signalisation** : une LED RVB adressable WS2812B (`LED1`) ainsi que quatre sorties `RGB_OUTx` sont disponibles pour reproduire les états lumineux d'origine. 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L680-L714】
* **Capteurs** : la carte « composants » expose des sorties hall `HALL_OUT`/`HALL_RC`, un bus I²C (`MCU_SCL`/`MCU_SDA`) et les lignes `MOTOR_HOUT`/`MOTOR_LOUT` vers la carte principale. 【F:pbmcu_c_hall/BMCU-C Hall/组件板/Schematic1_1/1_P1.schdoc†L200-L360】

### 1.2 Signaux utiles à interfacer

| Groupe de signaux | Rôle | Références |
| --- | --- | --- |
| `MOTORx_H`, `MOTORx_L` (x = 1..4) | Commande des enroulements moteur via les AT8236. | 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L669-L676】【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L1342-L1500】 |
| `MOTORx_HOUT`, `MOTORx_LOUT` | Sorties de puissance des drivers vers le faisceau moteurs/hall. | 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L1308-L1516】 |
| `RS485_A/B`, résistances R9/R10, TVS D2 | Lien différentiel avec terminaison 120 Ω et protection TVS. | 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L1740-L1827】 |
| `MCU_TX`, `MCU_RX`, `MCU_RTS` | UART interne CH32⇄transceiver RS‑485. | 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L498-L506】【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L151-L153】 |
| `MCU_SCL`, `MCU_SDA`, `HALL_OUT`, `HALL_RC` | Bus I²C et retours capteurs depuis la carte hall. | 【F:pbmcu_c_hall/BMCU-C Hall/组件板/Schematic1_1/1_P1.schdoc†L215-L224】【F:pbmcu_c_hall/BMCU-C Hall/组件板/Schematic1_1/1_P1.schdoc†L659-L798】 |
| `SYS_RGB`, `RGB_OUTx`, LED WS2812B | Indicateurs lumineux état buffer. | 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L680-L714】 |

## 2. Portage du microcontrôleur CH32V203 vers Klipper

1. **Créer une nouvelle architecture bas niveau** :
   * Ajouter `config MACH_CH32V20X` dans `src/Kconfig` et pointer vers un nouveau dossier `src/ch32v20x`. 【F:klipper-master/klipper-master/src/Kconfig†L1-L36】
   * Décliner les règles de compilation dans `src/Makefile` pour activer GPIO, PWM, UART… comme pour les autres architectures. 【F:klipper-master/klipper-master/src/Makefile†L1-L27】
   * Fournir l'initialisation horloge/PLL, la gestion NVIC et les couches GPIO/ADC/PWM. On peut s'inspirer des ports existants (STM32, HC32) pour la structure des fichiers (`board.c`, `gpio.c`, `clock.c`).
   * Utiliser une toolchain `riscv-none-elf-gcc` (WCH fournit un SDK libre) et l'intégrer dans `scripts/toolchain-riscv.cmake` (copie du script RP2040 en adaptant les options).

2. **Mapper les broches** :
   * Exporter la netlist depuis les schémas (`*.schdoc`) ou utiliser EasyEDA/Altium pour associer chaque net `MOTORx_H/L`, `MCU_TX`… à un port physique (`PA9`, `PB5`, etc.). Les coordonnées listées ci-dessus facilitent le repérage des pins sur le composant CH32. 【F:pbmcu_c_hall/BMCU-C Hall/主机板子/Schematic1/1_P1.schdoc†L447-L500】
   * Créer un fichier `src/ch32v20x/pins_bmcu_c.h` qui expose ces correspondances, puis une carte Klipper `config/boards/bmcu_c.cfg` contenant les sections `stepper_bmcu1` à `stepper_bmcu4`, entrées capteurs, LED et bus RS‑485.

3. **Piloter les AT8236** :
   * Chaque driver exige deux entrées logiques (`IN1/IN2`) et une référence de courant `VREF/ISEN`. On peut réutiliser le module `stepper.c` de Klipper en mode « pas direction logique » si l'on génère un microcode qui convertit STEP/DIR en séquences de phases, ou écrire un module dédié basé sur des timers PWM.
   * Les senseurs `ISEN` sont analogiques : activer `CONFIG_WANT_ADC` pour mesurer le courant et implémenter un limiteur logiciel (rapprocher du fonctionnement du firmware Bambu qui ajuste la vitesse du moteur).

4. **Communication RS‑485** :
   * Déterminer si l'on conserve le protocole Bambu (nécessite rétro‑ingénierie) ou si l'on expose un protocole Klipper spécifique. Dans le second cas, on peut créer un service Python côté host qui publie des commandes `gcode_macro` et discute via l'UART du CH32.
   * Configurer `usart` en demi‑duplex avec contrôle DE/RE (ligne `MCU_RTS`).

5. **Gestion des capteurs et LED** :
   * Déclarer des entrées digitales pour `HALL_OUT` et analogiques pour les photodiodes IR (voir nets `IR1_RECV` dans la carte capteur). 【F:pbmcu_c_hall/BMCU-C Hall/组件板/Schematic1_1/1_P1.schdoc†L659-L798】
   * Utiliser le module `neopixel` de Klipper pour piloter `SYS_RGB` et reproduire les animations lumineuses de l'AMS.

## 3. Exemple de configuration Klipper

Une fois la couche bas niveau opérationnelle, le host peut déclarer le BMCU comme MCU secondaire :

```ini
[mcu bmcu]
serial: /dev/serial/by-id/usb-klipper_ch32v203-if00
restart_method: command

[board_pins bmcu]
aliases:
    motor1_h=PB5, motor1_l=PB4,
    motor2_h=PB3, motor2_l=PB2,
    rs485_de=PA8, rs485_re=PA9,
    hall_out=PA0, hall_rc=PA1,
    led_data=PA7
# (Adapter avec la correspondance réelle extraite du schéma.)

[manual_stepper bmcu_spool_1]
step_pin: bmcu:motor1_h
dir_pin: bmcu:!motor1_l
rotation_distance: 22.0
velocity: 40
accel: 600

[neopixel bmcu_status]
pin: bmcu:led_data
chain_count: 1
color_order: GRB

[gcode_macro LOAD_SPOOL_1]
variable_target: 1
gcode:
    MANUAL_STEPPER STEPPER=bmcu_spool_1 VELOCITY=30 MOVE=400
```

> ⚠️ Les broches listées ci-dessus sont indicatives : remplissez-les avec les noms exacts obtenus lors du point 2.2.

## 4. Validation et tests

1. **Bring-up matériel** : vérifier les alimentations 3,3 V/5 V, la communication SWD/serial et le clignotement d'une LED témoin.
2. **Tests unitaires Klipper** : compiler `make menuconfig` avec l'architecture `CH32V203`, flasher via SWD, puis lancer `make flash`.
3. **Pilotage des moteurs** : utiliser `MANUAL_STEPPER` pour faire tourner chaque canal, surveiller le courant via `ISEN` et la réponse des capteurs hall.
4. **Intégration RS‑485** : valider l'échange de messages avec l'imprimante Klipper (par exemple un script Python qui publie des événements de changement de filament).

## 5. Aller plus loin

* Implémenter une couche de compatibilité avec les G-code AMS (`M620`, `M621`, etc.) afin de rester compatible avec les slicers Bambu.
* Ajouter des macros Klipper (par exemple `LOAD_SPOOL`, `EJECT_SPOOL`) pour orchestrer les séquences multi-couleurs.
* Publier la configuration finale (`config/boards/bmcu_c.cfg`, `docs/usage.md`) dans ce dépôt pour faciliter la reproduction par la communauté.

