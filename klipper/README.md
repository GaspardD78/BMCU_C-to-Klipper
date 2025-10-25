# Compiler et Flasher Klipper sur la BMCU

Ce guide fournit les instructions détaillées pour compiler le firmware Klipper et le flasher sur la carte BMCU-C.

## 1. Prérequis

Avant de commencer, vous devez installer les outils suivants sur votre système.

### Installation sur les systèmes Debian/Ubuntu

```bash
sudo apt update
sudo apt install gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf
```

### Installation de `wchisp`

`wchisp` est un outil Python utilisé pour flasher les microcontrôleurs WCH. Installez-le en utilisant `pip` :

```bash
pip3 install wchisp
```

## 2. Compilation du Firmware

Le firmware est configuré pour la carte BMCU-C (microcontrôleur CH32V203). La configuration est déjà sauvegardée dans le fichier `.config`.

Pour compiler le firmware, exécutez la commande suivante à la racine de ce répertoire (`klipper/`) :

```bash
make
```

Cette commande va générer le fichier `out/klipper.bin`.

## 3. Flashage du Firmware

Pour flasher le firmware sur la BMCU-C, vous devez connecter la carte à votre ordinateur en mode bootloader (maintenez le bouton BOOT enfoncé en branchant le câble USB).

Ensuite, utilisez la commande suivante pour flasher le firmware, en remplaçant `FLASH_DEVICE` par le port série de votre carte (par exemple, `/dev/ttyACM0`) ou `wch-link-swd` si vous utilisez un WCH-Link :

```bash
make flash FLASH_DEVICE=/dev/ttyACM0
```

ou

```bash
make flash FLASH_DEVICE=wch-link-swd
```

Le script de flashage s'occupera du reste. Une fois le flashage terminé, vous pouvez débrancher et rebrancher la carte. Klipper devrait maintenant fonctionner sur votre BMCU-C.

## 4. Notes de Configuration

Le fichier `.config` a été pré-configuré avec les paramètres suivants :

*   **Microcontrôleur :** CH32V203
*   **Vitesse de communication (Baud Rate) :** 1,250,000
*   **ADC :** Désactivé pour éviter les bugs connus.

Si vous avez besoin de modifier la configuration, vous pouvez utiliser la commande `make menuconfig`.
