# AGENTS.md

Ce document sert de guide pour toute contribution à ce projet. Il définit les conventions, les workflows et les points d'attention essentiels pour assurer la cohérence et la qualité du code.

## 1. Principes Généraux

- **Clarté avant tout :** Le code doit être lisible, commenté lorsque c'est nécessaire, et facile à comprendre.
- **Robustesse :** Les scripts et automatisations doivent inclure une gestion des erreurs solide pour éviter les comportements inattendus.
- **Sécurité :** Les opérations sensibles (comme le flashage de firmware) doivent être sécurisées, avec des confirmations utilisateur et des validations.

## 2. Structure du Projet

Le projet est organisé comme suit :

- `bmcu_addon/` : Contient la logique de l'addon Klipper pour l'intégration du BMCU-C.
- `firmware/` : Regroupe les scripts et configurations pour la compilation et le flashage du firmware Klipper sur le BMCU-C.
  - `build.sh` : Script pour compiler le firmware.
  - `flash.py` : Script interactif pour flasher le firmware.
  - `klipper.config` : Fichier de configuration Klipper pour le BMCU-C.
- `klipper/` : Submodule Git contenant le code source de Klipper. **Ne pas modifier directement ce répertoire sans synchroniser avec le dépôt officiel.**
- `docs/` : Documentation détaillée du projet.

## 3. Conventions de Codage

### Scripts Shell (`.sh`)

- **En-tête de robustesse :** Tout script doit commencer par `set -euo pipefail` pour garantir une sortie immédiate en cas d'erreur.
- **Configuration claire :** Les variables modifiables par l'utilisateur (chemins, adresses IP, etc.) doivent être regroupées et commentées en début de fichier.
- **Modularité :** Le code doit être organisé en fonctions claires et distinctes pour une meilleure lisibilité et maintenance.
- **Sorties utilisateur :** Utiliser des `echo` avec des couleurs pour améliorer la lisibilité des logs et des instructions. Rediriger les sorties verbeuses vers des fichiers de log.

### Scripts d'Automatisation (Python)

- **Gestion des erreurs :** Utiliser des blocs `try...except` pour capturer les erreurs et fournir des messages clairs. Arrêter l'exécution proprement en cas d'échec.
- **Logging structuré :** Mettre en place un logging détaillé avec des timestamps, et séparer les logs destinés à la console (succincts) de ceux écrits dans un fichier (détaillés).
- **Fonctionnalités de sécurité :** Pour les scripts critiques comme `flashBMCUtoKlipper_automation.py` :
  - Implémenter un mode `--dry-run` pour simuler les opérations.
  - Valider le firmware avec un checksum SHA256 (`--firmware-checksum`).
  - Vérifier la version de la cible (`--target-version`).
  - Permettre l'exécution de commandes de sauvegarde avant flashage (`--backup-command`).

## 4. Gestion des Versions

### Messages de Commit

Les messages de commit doivent suivre la spécification **Conventional Commits**. Cela permet de générer automatiquement des changelogs et de rendre l'historique plus lisible.

Format : `<type>[scope]: <description>`

- **Types courants :**
  - `feat` : Ajout d'une nouvelle fonctionnalité.
  - `fix` : Correction d'un bug.
  - `docs` : Modification de la documentation.
  - `style` : Changements de formatage n'affectant pas le code.
  - `refactor` : Réécriture de code sans changer son comportement.
  - `test` : Ajout ou modification de tests.
  - `chore` : Tâches de maintenance (mise à jour de dépendances, etc.).

Exemple : `feat(firmware): add checksum validation to flash.py`

### Versionnement du Firmware

La version du firmware est gérée à l'aide de **tags Git**.

- Le format de version est `vX.Y.Z` (par exemple, `v1.2.0`).
- Pour créer une nouvelle version :
  1. Assurez-vous que la branche principale est à jour et stable.
  2. Créez un tag annoté : `git tag -a v1.2.0 -m "Release version 1.2.0"`
  3. Poussez le tag vers le dépôt distant : `git push origin v1.2.0`

## 5. Workflows Essentiels

### Compilation du Firmware

1.  **Naviguer vers le bon répertoire :** `cd firmware/`
2.  **Lancer le script de build :** `./build.sh`
3.  **Vérifier la sortie :** Le firmware compilé (`klipper.bin`) sera disponible dans `klipper/out/`.

### Flashage du Firmware

Le flashage doit être effectué avec le script interactif pour minimiser les risques.

1.  **Naviguer vers le bon répertoire :** `cd firmware/`
2.  **Lancer le script de flashage :** `python3 flash.py`
3.  **Suivre les instructions :** Le script guidera l'utilisateur à travers les étapes de vérification et de confirmation.

### Nettoyage des Artefacts

Pour nettoyer les fichiers générés par la compilation :

1.  **Naviguer vers le répertoire Klipper :** `cd klipper/`
2.  **Exécuter la commande de nettoyage :** `make clean` ou `rm -rf out/`

## 6. Points d'Attention Particuliers

- **Submodule Klipper :** Le répertoire `klipper/` est un submodule. Pour le mettre à jour, utilisez les commandes `git submodule sync` et `git submodule update --init --recursive`.
- **Protocole "bambubus" :** Il s'agit d'un protocole de communication série complexe et non standard. Toute modification liée à ce protocole nécessite une compréhension approfondie de son fonctionnement (baud rate de 1,250,000, checksums CRC8 DVB-S2 et CRC16 custom).
- **Environnement de Compilation :** La compilation pour le microcontrôleur CH32V203 requiert `gcc-riscv64-unknown-elf` et `picolibc-riscv64-unknown-elf`. La variable `CROSS_PREFIX` dans `klipper/src/ch32v20x/Makefile` doit être correctement définie (`riscv64-unknown-elf-`).
