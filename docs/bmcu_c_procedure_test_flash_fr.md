# Procédure de test et de mise en fonction du BMCU-C sous Klipper/Mainsail

Cette procédure détaille pas à pas la préparation, le flash et la validation d'un BMCU-C destiné à piloter un buffer de filament sur une Ender 3 custom équipée de Klipper/Mainsail, d'une carte Manta EZE3 et d'un Fly SB2040 Pro V3. Chaque étape intègre des recommandations de sécurité ainsi que les informations à consigner pour documenter les problèmes rencontrés.

## 1. Préparations matérielles et sécurité

1. **Couper l'alimentation principale** : débranchez l'imprimante du secteur et attendez 1 à 2 minutes que les condensateurs se déchargent complètement.
2. **Installer la carte en sécurité** : placez le BMCU-C sur un plan de travail isolé, ventilé et protégé des décharges électrostatiques.
3. **Préparer la programmation** : raccordez l'adaptateur SWD (WCH-LinkE, ST-Link, etc.) sur les broches `SWCLK`/`SWDIO` du BMCU-C et prévoyez une alimentation 24 V (ou 5 V auxiliaire) pour la durée du flash.
4. **Mettre en place un journal de suivi** : ouvrez un carnet (papier ou fichier) où noter la date, la version de firmware, les câblages utilisés et les symptômes observés tout au long des essais.

## 2. Sauvegarder l'état actuel de l'installation

1. **Exporter la configuration Klipper existante** : dans Mainsail, rendez-vous dans `Settings → Machine` puis téléchargez `printer.cfg` et toute inclusion pertinente.
2. **Recenser les paramètres clés** : notez les vitesses, macros et assignations spécifiques à votre buffer (notamment le bus RS-485).
3. **Documenter le câblage** : prenez des photos nettes des branchements (RS-485, alimentation, connexions MCU principaux/secondaires) pour faciliter un retour arrière si nécessaire.

## 3. Préparer l'environnement Klipper

1. **Cloner ou synchroniser la branche CH32V203** :
   ```bash
   cd ~/klipper
   git remote add bmcu https://github.com/<votre-fork>/BMCU_C-to-Klipper.git   # première fois
   git fetch bmcu
   git checkout -B bmcu-ch32v203 bmcu/main
   ```
2. **Vérifier la toolchain** : confirmez la présence de `riscv-none-elf-gcc` et ajoutez-la au `PATH`. Inscrivez la version utilisée dans votre journal.
3. **Configurer Klipper** : lancez `make menuconfig` et choisissez :
   - Architecture `CH32V203` (`MACH_CH32V20X`)
   - Modèle `CH32V203C8`
   - Horloge `Internal 8 MHz crystal`
   - Interface `USART1 (PA9/PA10)`
   - Baud rate `1250000` (ou `250000` pour un test bas débit)
   - Activez `Enable extra low-level configuration options` et assurez-vous que `CONFIG_WANT_ADC` est actif
4. **Compiler** : sauvegardez la configuration puis exécutez `make` pour générer `out/klipper.bin`. Notez le hash Git et la date de compilation.

## 4. Flasher le BMCU-C

1. **Placer la carte en mode bootloader** : alimentez le BMCU-C et maintenez le bouton de reset selon les besoins de votre programmateur.
2. **Installer l'outil de flash** : si nécessaire, installez `wchisp` via `pip3 install --user wchisp`.
3. **Lancer le flash** :
   - Via SWD :
     ```bash
     make flash FLASH_DEVICE=wch-link-swd
     ```
   - Via UART :
     ```bash
     make flash FLASH_DEVICE=/dev/ttyUSB0 FLASH_BAUD=115200 FLASH_EXTRA_OPTS="--chip ch32v20x"
     ```
   Consignez l'interface utilisée, les messages de la console et la durée de l'opération.
4. **Redémarrer et valider** : exécutez `make serial` pour vérifier la détection (`usb-klipper_ch32v203`) ou relever tout message d'erreur.

## 5. Câblage et intégration sur l'imprimante

1. **Relier la communication** : raccordez la liaison RS-485 au Fly SB2040 Pro V3 (ou à la Manta EZE3) en respectant `A/B` et une masse commune.
2. **Alimenter la carte** : connectez l'alimentation 24 V du BMCU-C via un fusible 1–2 A adapté et assurez-vous d'un 5 V logique propre.
3. **Connecter au SBC** : branchez le câble USB (ou UART) vers le SBC qui exécute Klipper et notez les ports `/dev/serial/by-id/...`.

## 6. Configurer Klipper/Mainsail

1. **Déclarer le MCU** : ajoutez au `printer.cfg` :
   ```ini
   [include config/boards/bmcu_c.cfg]

   [mcu bmcu_c]
   serial: /dev/serial/by-id/usb-klipper_ch32v203-if00
   restart_method: command
   ```
   Inscrivez la date et le port série utilisé dans votre journal.
2. **Charger les macros** : incluez `bmcu_macros.cfg` si vous souhaitez disposer des commandes prêtes à l'emploi.
3. **Configurer le bus RS-485** : complétez la section `[bmcu]` :
   ```ini
   [bmcu]
   serial: /dev/serial/by-id/usb-your_bmcu_serial_id_here
   baud: 1250000
   ```
   Documentez la valeur de `baud` et les options retenues.
4. **Redémarrer Klipper** : redémarrez le service (via Mainsail ou `sudo service klipper restart`) et consignez le statut (`ready` ou `error`).

## 7. Tests fonctionnels initiaux

1. **Connexion MCU** : observez l'onglet Console dans Mainsail et notez tout message d'erreur.
2. **Test RS-485 (optionnel)** :
   ```bash
   python3 scripts/bmcu_rs485_test.py /dev/ttyUSB0 --baud 250000 --payload 766572
   ```
   Copiez les octets renvoyés dans votre journal.
3. **Macros de mouvement** : depuis la console Mainsail, envoyez :
   ```
   BMCU_ENABLE_SPOOLS
   BMCU_SPOOL_MOVE GATE=1 MOVE=120 VELOCITY=25 ACCEL=300
   BMCU_HOME
   ```
   Décrivez les bruits, mouvements et éventuelles erreurs. Terminez par `BMCU_DISABLE_SPOOLS` pour couper les drivers.
4. **Capteurs** :
   - `QUERY_ENDSTOPS` pour vérifier les capteurs Hall.
   - `QUERY_ADC PIN=bmcu_c:spool1_ir` pour la photodiode IR.
   Relevez les valeurs attendues ou anormales.
5. **Éclairage** : ajustez la section `[neopixel bmcu_c_status]` si nécessaire et notez l'effet obtenu.

## 8. Documentation des problèmes

Pour chaque anomalie rencontrée, consignez :

- La commande envoyée, l'état du buffer et la position des moteurs.
- Les logs Mainsail (`klippy.log`) ou la sortie console pertinente.
- Les mesures électriques (tension RS-485, intensité 24 V) si elles sont pertinentes.
- Des photos/vidéos pour les problèmes mécaniques.

Classez vos observations par thème (flash, communication, moteurs, capteurs) pour faciliter les échanges d'assistance.

## 9. Maintenance et itérations

- Après chaque modification (firmware, configuration), répétez le cycle `make` → `make flash` → tests et mettez à jour votre journal.
- Maintenez la branche `bmcu-ch32v203` à jour via `git rebase origin/master` et notez la date du dernier rebase.
- Archivez vos observations et correctifs dans ce dépôt ou votre documentation personnelle pour capitaliser sur les retours d'expérience.

