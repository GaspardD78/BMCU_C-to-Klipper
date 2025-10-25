# Audit du portage CH32V203 vers Klipper et procédure de flash

Ce document récapitule l'état du portage **CH32V203** inclus dans ce dépôt, met en lumière les points qui restent à
compléter et fournit une procédure pas-à-pas pour construire et flasher le firmware, avec une alternative suivant que
l'hôte soit un **CB2** (carte d'appoint Bambu) ou un **Raspberry Pi**.

## 1. Audit du portage

### 1.1 Intégration build et configuration

* L'architecture `MACH_CH32V20X` expose ses options propres dans `src/ch32v20x/Kconfig` (fréquence, taille flash/RAM,
  sélection USART 1 ou USB) et active les sous-systèmes GPIO/ADC/PWM attendus par Klipper.【F:klipper/src/ch32v20x/Kconfig†L1-L43】
* Le `Makefile` dédié force l'utilisation de la toolchain `riscv-none-elf`, ajoute les sources RISC-V génériques et les
  fichiers spécifiques au CH32V20x, puis référence le script de link `ch32v20x_link.lds.S`. Les pilotes ADC et PWM sont
  compilés uniquement si les options correspondantes sont demandées, ce qui facilite l'activation incrémentale des
  fonctionnalités.【F:klipper/src/ch32v20x/Makefile†L1-L28】

### 1.2 Chaîne de démarrage et horloges

* Le point d'entrée `riscv_main()` appelle successivement `SystemInit()`, l'initialisation horloge/GPIO/timer, puis
  démarre l'ordonnanceur Klipper. L'initialisation de l'USART reste conditionnée par la configuration pour éviter de
  tirer de dépendances inutiles.【F:klipper/src/ch32v20x/main.c†L9-L22】
* `clock_init()` bascule le MCU sur l'oscillateur externe 12 MHz, configure la PLL à 144 MHz, divise l'APB1 par 2 et
  active les horloges des blocs GPIO, timers et UART nécessaires à Klipper.【F:klipper/src/ch32v20x/clock.c†L5-L43】
* `SystemInit()` positionne le contrôleur d'interruptions ECLIC en mode niveau et garantit la disponibilité du HSI avant
  que `clock_init()` ne prenne la main.【F:klipper/src/ch32v20x/system.c†L5-L20】

### 1.3 Planification temps réel et communication

* Le timer système utilise TIM2 pour générer les interruptions de planification. La fonction `timer_dispatch_many()` de
  Klipper est déclenchée à chaque overflow, avec reprogrammation automatique de la prochaine échéance. Une fonction
  `udelay()` par polling est également fournie pour les attentes courtes.【F:klipper/src/ch32v20x/timer.c†L11-L82】
* Le driver `usart.c` implémente l'USART1 en mode RS-485 demi-duplex (pins PA9/PA10 avec DE sur PA12), gère
  l'inversion du sens de transmission via une GPIO dédiée et s'appuie sur les utilitaires IRQ de Klipper pour la file
  RX/TX.【F:klipper/src/ch32v20x/usart.c†L1-L83】

### 1.4 GPIO et description de carte

* `gpio.c` propose une abstraction pour les ports A–E, assure la mise en sécurité des broches au démarrage et expose des
  alias spécifiques aux drivers AT8236 utilisés par le BMCU-C. La fonction `gpio_out_setup()` assure l'activation du
  bus APB2 correspondant avant de reconfigurer la broche.【F:klipper/src/ch32v20x/gpio.c†L1-L126】
* Le fichier `config/boards/bmcu_c.cfg` cartographie l'ensemble des broches du PCB (RS‑485, drivers moteurs, capteurs,
  LEDs) et fournit des objets `manual_stepper`/`gcode_macro` prêts à l'emploi pour piloter les quatre tiroirs de
  filament.【F:klipper/config/boards/bmcu_c.cfg†L1-L108】

### 1.5 Fonctions manquantes ou à compléter

* Le module ADC (`adc.c`) est fonctionnel mais nécessite une calibration fine pour des lectures précises.
* L'option USB FS est déclarée dans le Kconfig mais aucun driver n'est encore fourni – toute sélection de l'USB conduit à
  une erreur de build ; privilégiez pour l'instant l'USART1.

## 2. Préparation commune avant flash

1. **Cloner le dépôt et se placer sur la branche** contenant le portage :
   ```bash
   cd ~/BMCU_C-to-Klipper
   git pull
   cd klipper
   ```
2. **Installer la toolchain RISC-V bare-metal** (ou utiliser celle fournie par WCH) :
   ```bash
   sudo apt-get update
   sudo apt-get install gcc-riscv64-unknown-elf g++-riscv64-unknown-elf binutils-riscv64-unknown-elf
   ```
   > Sur CB2, ajoutez `sudo apt-get install build-essential python3` si les paquets ne sont pas déjà présents.
3. **Configurer Klipper** :
   ```bash
   make menuconfig
   ```
   * Micro-controller Architecture : `WCH CH32V20x`.
   * Processor model : `CH32V203C8`.
   * Communication interface : `USART1 (PA9/PA10)`.
   * Baud rate : `1250000` (recommandé pour le bambubus) ou `250000`.
   * Conservez `Enable extra low-level configuration options` désactivé tant que l'USB n'est pas implémenté.
4. **Compiler** :
   ```bash
   make
   ```
   Le binaire `out/klipper.bin` est généré en sortie.

## 3. Méthode A : flash depuis un CB2

Le CB2 embarque un Linux minimaliste connecté au BMCU-C via un header interne. Il est possible d'utiliser le WCH-LinkE en
USB ou l'interface série exposée par le CB2.

1. **Connexion au CB2** : via SSH (`ssh root@<ip_du_cb2>`) ou en branchant un câble USB-C en mode gadget.
2. **Installer les utilitaires WCH** (si absent) :
   ```bash
   sudo apt-get install git python3-pip
   pip3 install --user wchisp
   ```
3. **Monter le répertoire de build** : synchronisez `klipper/` sur le CB2 (rsync/scp) ou utilisez un partage NFS.
4. **Mettre le BMCU-C en mode bootloader** : reliez le WCH-LinkE au port SWD du BMCU-C (SWCLK/SWDIO/GND/3V3) et maintenez
   la carte alimentée (24 V ou 5 V).
5. **Flasher** :
   ```bash
   cd /chemin/vers/klipper
   make flash FLASH_DEVICE=wch-link-swd
   ```
   Si vous utilisez le port série interne du CB2, spécifiez `FLASH_DEVICE=/dev/ttyS2` (ou le port détecté) et lancez
   `wchisp flash out/klipper.bin`.
6. **Vérifier** : après reset, la commande suivante doit afficher l'identifiant USB du MCU :
   ```bash
   ls /dev/serial/by-id/
   ```

## 4. Méthode B : flash depuis un Raspberry Pi

1. **Préparer le Raspberry Pi** : assurez-vous qu'il exécute l'hôte Klipper (Mainsail/Fluidd) et qu'il dispose des paquets
   installés à l'étape 2.
2. **Brancher le WCH-LinkE ou un adaptateur USB-SWD** sur le Pi et connecter les broches SWD au BMCU-C.
3. **Transférer le firmware** :
   ```bash
   scp out/klipper.bin pi@<ip_du_pi>:/home/pi/klipper/out/
   ```
4. **Flasher via `make`** (dans `/home/pi/klipper`) :
   ```bash
   make flash FLASH_DEVICE=wch-link-swd
   ```
   En l'absence de WCH-LinkE, vous pouvez utiliser un convertisseur série USB ↔︎ UART et la commande :
   ```bash
   wchisp flash out/klipper.bin --device /dev/ttyUSB0 --baud 115200
   ```
5. **Réassocier Klipper** : mettez à jour `printer.cfg` pour ajouter le MCU BMCU-C :
   ```ini
   [mcu bmcu_c]
   serial: /dev/serial/by-id/usb-klipper_ch32v203-if00
   restart_method: command
   ```
   Les alias et macros complémentaires se trouvent dans `config/boards/bmcu_c.cfg`.【F:klipper/config/boards/bmcu_c.cfg†L1-L108】
6. **Redémarrer Klipper** et vérifier que le MCU apparaît `ready`.

## 5. Validation post-flash

1. Dans la console Klipper, lancer `STATUS` et vérifier que le MCU `bmcu_c` répond.
2. Tester l'allumage de la LED de statut ou un mouvement court sur un spool via `BMCU_SPOOL_MOVE GATE=1 MOVE=10`.
3. Documenter toute anomalie (absence de télémétrie, impossibilité d'actionner les drivers) – ces points sont souvent liés
   aux pilotes ADC/PWM encore manquants.

---

**Prochaines actions recommandées :**

* Implémenter le support ADC (TIM2 trigger + DMA) pour exploiter les capteurs IR et les mesures de courant.
* Finaliser la génération PWM pour piloter l'éclairage et les entrées AT8236 en mode linéaire.
* Ajouter une chaîne de test automatique (blinky, boucle UART) pour sécuriser les évolutions futures.
