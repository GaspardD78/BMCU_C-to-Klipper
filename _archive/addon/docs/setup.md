# Guide d'installation du BMCU-C Addon

Ce document décrit **l'unique procédure** nécessaire pour mettre en service l'addon BMCU-C avec Klipper et Happy Hare. Chaque étape est obligatoire pour garantir le fonctionnement du module.

## 1. Prérequis

- Une instance Klipper opérationnelle avec accès SSH (Raspberry Pi, SBC, etc.).
- L'interface Mainsail ou Fluidd déjà configurée.
- Happy Hare installé sur l'imprimante. Si besoin, suivez la documentation officielle :
  - Klipper : <https://www.klipper3d.org/Installation.html>
  - Happy Hare : <https://github.com/moggieuk/Happy-Hare>
- Un BMCU-C déjà flashé avec Klipper. Si nécessaire, suivez la procédure décrite dans le **[guide de flashage principal](../../flash_automation/docs/flash_procedure.md)**.

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

## 5. Cas Particulier : Configuration avec CAN Bus

Si votre imprimante utilise déjà des périphériques sur un bus CAN (comme une tête d'outil), votre configuration Klipper est "mixte" : elle doit gérer à la fois le BMCU-C en USB et vos autres outils en CAN.

Voici comment vous assurer que tout fonctionne ensemble.

### Identifier les périphériques

1.  **Trouver le port série du BMCU-C (USB)** :
    Même après un redémarrage, le chemin stable de votre BMCU-C se trouve avec la commande :
    ```bash
    ls /dev/serial/by-id/*
    ```
    Le résultat devrait ressembler à ceci :
    ```
    /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
    ```
    C'est ce chemin qu'il faut utiliser dans la section `[bmcu]` de votre configuration.

2.  **Trouver l'UUID de vos outils CAN** :
    Utilisez le script `canbus_query.py` fourni par Klipper pour lister les périphériques sur votre bus CAN :
    ```bash
    ~/klippy-env/bin/python ~/klipper/scripts/canbus_query.py can0
    ```
    Vous obtiendrez une liste des `canbus_uuid` de vos périphériques, par exemple :
    ```
    Found canbus_uuid=0e8b37766f2a at an RTT of 0.000139
    ```

### Exemple de `printer.cfg` mixte

Voici un exemple simplifié de `printer.cfg` qui montre comment déclarer à la fois le `[mcu]` principal, un `[mcu]` pour l'outil sur CAN Bus, et le `[bmcu]` :

```ini
[mcu]
# MCU principal (ex: Manta E3EZ)
serial: /dev/serial/by-id/usb-Klipper_stm32g0b1xx_...

[mcu tool_head]
# MCU de la tête d'outil sur le bus CAN (ex: Fly SB2040)
canbus_uuid: 0e8b37766f2a

[bmcu]
# Configuration du BMCU-C en USB
serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
baud: 1250000

# ... le reste de votre configuration (steppers, extrudeuse, etc.)
```

L'important est que chaque section (`[mcu]`, `[mcu tool_head]`, `[bmcu]`) pointe vers le bon périphérique via son identifiant unique (série ou `canbus_uuid`).
