# Mise à jour de Klipper et intégration Mainsail pour le BMCU-C

Ce guide décrit la marche à suivre pour rendre un BMCU-C opérationnel sous Klipper/Mainsail à partir des sources de ce dépôt. Les étapes couvrent la mise à jour du firmware Klipper pour inclure l'architecture `MACH_CH32V20X`, la compilation et le flash du microcontrôleur CH32V203 de la carte, puis l'intégration dans l'interface Mainsail.

## 1. Préparer l'environnement Klipper

1. **Cloner ou mettre à jour les sources** : depuis la machine hôte Klipper, synchronisez le répertoire de travail avec ce dépôt afin de récupérer la branche portant le support CH32V203 et la configuration BMCU-C.
   ```bash
   cd ~/klipper
   git remote add bmcu https://github.com/<votre-fork>/BMCU_C-to-Klipper.git   # une seule fois
   git fetch bmcu
   git checkout -B bmcu-ch32v203 bmcu/main
   ```
2. **Installer la toolchain RISC-V** : le port CH32V20x s'appuie sur `riscv-none-elf-gcc`. Vérifiez que les paquets `gcc-riscv64-unknown-elf` (ou l'archive WCH officielle) sont présents et ajoutez le binaire au `PATH` avant de lancer la compilation.
3. **Configurer Klipper** : exécutez `make menuconfig` et sélectionnez :
   * **Micro-controller Architecture** : `CH32V203` (entrée `MACH_CH32V20X`).
   * **Processor model** : `CH32V203C8`.
   * **Clock Reference** : `Internal 8 MHz crystal`.
   * **Communication interface** : `USART1 (PA9/PA10)`.
   * **Baud rate for serial port** : `1250000` (pour le protocole bambubus) ou `250000` (pour un usage Klipper standard).
   * Activez `Enable extra low-level configuration options` puis assurez-vous que `CONFIG_WANT_ADC` reste activé pour la télémétrie courant/capteurs.【F:klipper/src/ch32v20x/Kconfig†L6-L19】
4. **Sauvegarder la configuration** : le menu `Save Configuration` génère `out/klipper.dict` ainsi que le binaire `out/klipper.bin` ciblant le CH32V203.

## 2. Flasher le CH32V203 du BMCU-C

1. **Mettre la carte en mode bootloader** : connectez un adaptateur SWD (WCH-Link ou ST-Link compatible) sur les broches `SWCLK/SWDIO` présentes sur le PCB. Alimentez la carte via son connecteur 24 V ou par le 5 V auxiliaire.
2. **Lancer le flash** : installez au préalable l'outil [`wchisp`](https://github.com/ch32-rs/wchisp) (`pip3 install --user wchisp`), puis utilisez `make flash FLASH_DEVICE=<interface>` pour écrire `out/klipper.bin` sur la flash interne. Avec un WCH-LinkE configuré en SWD, la commande ressemble à :
   ```bash
   make flash FLASH_DEVICE=wch-link-swd
   ```
   Le paramètre `FLASH_BAUD=115200` permet de fixer une vitesse série lorsque vous utilisez un adaptateur UART, et `FLASH_EXTRA_OPTS="--chip ch32v20x"` relaie des options supplémentaires à `wchisp` si besoin.【F:klipper/src/ch32v20x/Makefile†L29-L46】
   En alternative, `openocd` ou un script personnel peuvent être employés si vous disposez déjà des scripts correspondants.
3. **Redémarrer et vérifier** : après flash, exécutez `make serial` pour confirmer que le microcontrôleur répond et expose l'identifiant USB/serial attendu (préfixe `usb-klipper_ch32v203`).

## 3. Déployer la configuration Klipper côté host

1. **Déclarer le MCU secondaire** : dans votre `printer.cfg`, ajoutez l'inclusion du fichier de carte et la définition du MCU BMCU-C.
   ```ini
   [include config/boards/bmcu_c.cfg]

   [mcu bmcu_c]
   serial: /dev/serial/by-id/usb-klipper_ch32v203-if00
   restart_method: command
   ```
   Le fichier `config/boards/bmcu_c.cfg` fournit les alias de broches, les sections `[manual_stepper]` et `[neopixel]` nécessaires au buffer.【F:klipper/config/boards/bmcu_c.cfg†L1-L134】
2. **Charger les macros dédiées** : ajoutez au besoin `bmcu_macros.cfg` pour bénéficier des commandes de changement de spool.
   ```ini
   [include bmcu_macros.cfg]
   ```
   Les macros `BMCU_ENABLE_SPOOLS`, `BMCU_SPOOL_MOVE` et `BMCU_HOME` encapsulent les séquences de pilotage décrites dans le guide d'utilisation.【F:docs/usage.md†L9-L53】
3. **Redémarrer Klipper** : exécutez `sudo service klipper restart` (ou utilisez l'interface Mainsail) pour prendre en compte les nouveaux fichiers.

## 4. Intégration et validation sous Mainsail

1. **Vérifier la connexion MCU** : dans Mainsail, l'onglet « Console » doit afficher le MCU `bmcu_c` comme `ready`. En cas d'erreur, contrôlez le port série (`ls /dev/serial/by-id/`) et réappliquez `make flash`.
2. **Tester les macros** : exécutez depuis la console Mainsail :
   ```gcode
   BMCU_ENABLE_SPOOLS
   BMCU_SPOOL_MOVE GATE=1 MOVE=120 VELOCITY=25 ACCEL=300
   BMCU_HOME
   ```
   Les commandes actionnent successivement l'alimentation des drivers, le déplacement d'un spool et le retour à la position de référence.【F:docs/usage.md†L19-L52】
3. **Surveiller les capteurs** : utilisez `QUERY_ENDSTOPS` pour suivre les capteurs Hall et `QUERY_ADC PIN=bmcu_c:spool1_ir` pour les photodiodes IR exposées par le portage.【F:docs/usage.md†L54-L70】
4. **Configurer l'éclairage** : personnalisez l'objet `[neopixel bmcu_c_status]` dans `bmcu_c.cfg` afin de synchroniser la LED WS2812B avec vos scripts de changement de filament.【F:klipper/config/boards/bmcu_c.cfg†L101-L134】

## 5. Maintenance

* Conservez la branche `bmcu-ch32v203` alignée avec les sources officielles Klipper via `git rebase origin/master` pour récupérer les correctifs amont.
* Après chaque mise à jour du firmware, répétez les étapes de compilation (`make menuconfig`, `make`) et de flash pour assurer la cohérence entre l'hôte et le MCU.
* Documentez vos ajustements (vitesse RS-485, paramètres moteurs) dans `docs/usage.md` ou un fichier dédié afin de faciliter les retours d'expérience.
