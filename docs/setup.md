# Guide d'installation du BMCU-C Addon

Ce document décrit **l'unique procédure** nécessaire pour mettre en service l'addon BMCU-C avec Klipper et Happy Hare. Chaque étape est obligatoire pour garantir le fonctionnement du module.

## 1. Prérequis

- Une instance Klipper opérationnelle avec accès SSH (Raspberry Pi, SBC, etc.).
- L'interface Mainsail ou Fluidd déjà configurée.
- Happy Hare installé sur l'imprimante. Si besoin, suivez la documentation officielle :
  - Klipper : <https://www.klipper3d.org/Installation.html>
  - Happy Hare : <https://github.com/moggieuk/Happy-Hare>
- Outils de compilation pour RISC-V : `gcc-riscv32-unknown-elf`, `picolibc-riscv32-unknown-elf`.
  - Si la toolchain n'est pas installée, le script `firmware/build.sh` télécharge automatiquement une version officielle RV32 et l'utilise localement.
- Outil de flashage : `wchisp`.

## 2. Récupérer les fichiers de l'addon

```bash
git clone --recurse-submodules https://github.com/GaspardD78/BMCU_C-to-Klipper.git
cd BMCU_C-to-Klipper
```

## 3. Compiler et flasher le firmware

1. **Compiler le firmware :**
   Le script `build.sh` prépare et lance la compilation du firmware Klipper.
   ```bash
   ./firmware/build.sh
   ```

2. **Flasher le firmware :**
   Le script `flash_automation.sh` vous guidera pour mettre le BMCU-C en mode bootloader et flasher le firmware tout en générant un journal détaillé.
   ```bash
   ./firmware/flash_automation.sh
   ```

## 4. Installer l'addon sur Klipper

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
