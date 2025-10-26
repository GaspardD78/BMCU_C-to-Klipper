# Intégration du BMCU-C avec Klipper et Happy Hare

> ⚠️ **Statut : preuve de concept.** L'intégration n'a pas encore été validée sur un BMCU-C réel. Ce dépôt s'adresse aux développeurs et "makers" souhaitant contribuer aux tests matériels et logiciels.

Ce dépôt open-source fournit uniquement les éléments nécessaires pour piloter un BMCU-C (clone communautaire de l'AMS Bambu Lab) depuis Klipper en s'appuyant sur Happy Hare :

- un module Python à copier dans `klippy/extras` ;
- les fichiers de configuration et macros à inclure dans votre `printer.cfg` ;
- la documentation d'installation minimale pour préparer l'environnement.

## Structure du dépôt

- `bmcu_addon/bmcu.py` : module Klipper responsable de la communication RS-485 avec le BMCU-C (implémentation du protocole « bambubus »).
- `bmcu_addon/config/` : fichiers de configuration et macros Happy Hare à inclure dans votre configuration Klipper.
- `docs/setup.md` : guide pas-à-pas pour installer et activer l'addon.
- `firmware/` : scripts et configuration pour compiler et flasher le firmware Klipper sur le BMCU-C.
- `klipper/` : sous-module Git contenant les sources du firmware Klipper.

## Fonctionnalités

- **Module Klipper `bmcu.py` :** Gère l'encodage/décodage des trames, expose les commandes G-code (`BMCU_SELECT_GATE`, `BMCU_HOME`, etc.) et publie l'état du BMCU-C.
- **Intégration Happy Hare :** Paramètres et macros prêts à l'emploi pour relier Happy Hare au BMCU-C.
- **Documentation minimale :** Toutes les étapes d'installation sont regroupées dans `docs/setup.md`.

## Installation

Suivez le guide d'installation détaillé disponible dans `docs/setup.md` :

**➡️ [Guide d'installation](./docs/setup.md)**

## Firmware

Ce dépôt inclut désormais tout le nécessaire pour compiler et flasher le firmware Klipper sur le BMCU-C.

1. **Compiler le firmware :**
   ```bash
   ./firmware/build.sh
   ```
2. **Flasher le firmware :**
   Deux options sont disponibles :
   - interface interactive avec checklist et génération automatique d'un prompt d'assistance en cas d'erreur :
     ```bash
     ./firmware/flashBMCUtoKlipper_interface.py
     ```
   - lancement direct du script d'automatisation (mode non interactif) :
     ```bash
     ./firmware/flash.sh
     ```

📄 **Documentation annexe :** [Procédure de flash du BMCU-C](./docs/flash_procedure.md)

## Contribuer

Les contributions sont les bienvenues ! Si vous souhaitez participer au développement, n'hésitez pas à ouvrir une issue ou à soumettre une pull request.

## Licence

Ce projet n'a pas encore de licence définie. Veuillez en ajouter une avant toute redistribution ou dérivation.
