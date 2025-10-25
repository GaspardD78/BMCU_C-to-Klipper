# Guide d'installation du BMCU-C Addon

Ce document décrit **l'unique procédure** nécessaire pour mettre en service l'addon BMCU-C avec Klipper et Happy Hare. Chaque étape est obligatoire pour garantir le fonctionnement du module.

## 1. Prérequis

- Une instance Klipper opérationnelle avec accès SSH (Raspberry Pi, SBC, etc.).
- L'interface Mainsail ou Fluidd déjà configurée.
- Happy Hare installé sur l'imprimante. Si besoin, suivez la documentation officielle :
  - Klipper : <https://www.klipper3d.org/Installation.html>
  - Happy Hare : <https://github.com/moggieuk/Happy-Hare>
- Accès aux sources du firmware BMCU-C (dépôt séparé, voir section 4).

## 2. Récupérer les fichiers de l'addon

```bash
git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
cd BMCU_C-to-Klipper
```

Le dépôt contient uniquement le module Klipper et les fichiers de configuration nécessaires.

## 3. Installer l'addon sur Klipper

1. Copier l'addon dans le dossier de configuration Klipper :

   ```bash
   cp -r bmcu_addon ~/klipper_config/
   ```

2. Installer le module Python dans `klippy/extras` :

   ```bash
   cp ~/klipper_config/bmcu_addon/bmcu.py ~/klipper/klippy/extras/
   ```

3. Inclure la configuration dans `printer.cfg` :

   ```ini
   [include bmcu_addon/config/bmcu_config.cfg]
   [include bmcu_addon/config/bmcu_macros.cfg]
   ```

4. Redémarrer Klipper pour charger le module :

   ```bash
   sudo service klipper restart
   ```

## 4. Préparer le firmware BMCU-C

Le firmware et les instructions de flashage sont fournis dans un dépôt séparé afin de garder ce projet focalisé sur l'addon Klipper :

- <https://github.com/GaspardD78/BMCU-C-Firmware>

Suivez la documentation de ce dépôt pour compiler et flasher le BMCU-C avant d'utiliser l'addon.
