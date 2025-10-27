# Guide d'installation du BMCU-C Addon

Ce document décrit **l'unique procédure** nécessaire pour mettre en service l'addon BMCU-C avec Klipper et Happy Hare. Chaque étape est obligatoire pour garantir le fonctionnement du module.

## 1. Prérequis

- Une instance Klipper opérationnelle avec accès SSH (Raspberry Pi, SBC, etc.).
- L'interface Mainsail ou Fluidd déjà configurée.
- Happy Hare installé sur l'imprimante. Si besoin, suivez la documentation officielle :
  - Klipper : <https://www.klipper3d.org/Installation.html>
  - Happy Hare : <https://github.com/moggieuk/Happy-Hare>
- Un BMCU-C déjà flashé avec Klipper. Si nécessaire, suivez la procédure décrite dans [`flash_automation/docs/flash_procedure.md`](../../flash_automation/docs/flash_procedure.md).

## 2. Récupérer les fichiers de l'addon

```bash
git clone https://github.com/GaspardD78/BMCU_C-to-Klipper-addon.git
cd BMCU_C-to-Klipper-addon
```

> 💡 Si vous travaillez depuis le dépôt monorepo, copiez simplement le dossier `addon/` sur votre machine Klipper.

## 3. Compiler et flasher le firmware

> ✅ Cette étape est déjà couverte par le dépôt `flash_automation/`. Passez à la suite si votre BMCU-C dispose déjà d'un firmware Klipper fonctionnel.

## 4. Installer l'addon sur Klipper

1. Copier l'addon dans le dossier de configuration Klipper :

   ```bash
   cp -r config ~/klipper_config/bmcu_addon_config
   ```

2. Installer le module Python dans `klippy/extras` :

   ```bash
   cp bmcu.py ~/klipper/klippy/extras/
   ```

3. Inclure la configuration dans `printer.cfg` :

   ```ini
   [include bmcu_addon_config/bmcu_config.cfg]
   [include bmcu_addon_config/bmcu_macros.cfg]
   ```

4. Redémarrer Klipper pour charger le module :

   ```bash
   sudo service klipper restart
   ```
