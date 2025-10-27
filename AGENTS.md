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

### Matrice des Zones Sensibles

| Répertoire | Impact potentiel | Recommandations de revue |
| --- | --- | --- |
| `firmware/` | Modifie le binaire flashé sur le BMCU-C et peut rendre une machine inutilisable en cas d'erreur. | Exiger au moins un test matériel ou une simulation et une double validation par un reviewer connaissant le matériel. |
| `bmcu_addon/` | Affecte l'intégration Klipper et peut casser la compatibilité avec certains modules Klipper. | Vérifier la compatibilité avec les versions cibles de Klipper et inclure des tests sur banc ou en environnement réel. |
| `klipper/` | Submodule synchronisé avec le dépôt officiel, toute divergence peut compliquer les mises à jour futures. | Synchroniser avec le dépôt amont et justifier la nécessité de chaque patch local. |
| `docs/` | Influence la compréhension utilisateur et la conformité des procédures. | Vérifier la cohérence avec les scripts et scénarios les plus récents. |
| Scripts `flash_automation.sh` et Python associés | Interagissent directement avec le matériel et les permissions système. | Tester en mode `--dry-run` et vérifier les garde-fous (checksums, confirmations). |

## 3. Pré-requis et Compatibilité des Outils

Avant de lancer les workflows, assurez-vous que les outils suivants sont disponibles et à jour :

| Outil / Dépendance | Version minimale recommandée | Notes de compatibilité |
| --- | --- | --- |
| `gcc-riscv32-unknown-elf` | 13.2.0 | Nécessaire pour compiler le firmware CH32V203. Vérifier que `CROSS_PREFIX` pointe vers `riscv32-unknown-elf-`. |
| `picolibc-riscv32-unknown-elf` | 1.8 | Bibliothèque standard utilisée lors de la compilation ; installer les headers correspondants. |
| Python | 3.10 | Requis pour les scripts `flash.py` et les automatisations. Vérifier la présence de `python3` dans le PATH. |
| `pip` | 23.0 | Utilisé pour installer les dépendances Python (ex. `pyserial`). |
| `git` | 2.35 | Indispensable pour gérer le submodule `klipper/`. |
| Accès USB / permissions `dialout` | N/A | Assurez-vous que l'utilisateur appartient au groupe permettant l'accès au port série. |

✅ **Check-list rapide**

- [ ] Les versions minimales ci-dessus sont installées.
- [ ] Le sous-module `klipper/` est initialisé (`git submodule update --init --recursive`).
- [ ] Les scripts sont exécutables (`chmod +x`).
- [ ] L'utilisateur courant possède les permissions sur le port série ciblé.

## 4. Conventions de Codage

### Scripts Shell (`.sh`)

- **En-tête de robustesse :** Tout script doit commencer par `set -euo pipefail` pour garantir une sortie immédiate en cas d'erreur.
- **Configuration claire :** Les variables modifiables par l'utilisateur (chemins, adresses IP, etc.) doivent être regroupées et commentées en début de fichier.
- **Modularité :** Le code doit être organisé en fonctions claires et distinctes pour une meilleure lisibilité et maintenance.
- **Sorties utilisateur :** Utiliser des `echo` avec des couleurs pour améliorer la lisibilité des logs et des instructions. Rediriger les sorties verbeuses vers des fichiers de log.

### Scripts d'Automatisation (Python)

- **Gestion des erreurs :** Utiliser des blocs `try...except` pour capturer les erreurs et fournir des messages clairs. Arrêter l'exécution proprement en cas d'échec.
- **Logging structuré :**
  - Format recommandé : `%(asctime)s | %(levelname)s | %(name)s | %(message)s` avec un timestamp ISO8601 (`%Y-%m-%dT%H:%M:%S%z`).
  - Niveau par défaut : `INFO` pour la console, `DEBUG` pour les fichiers.
  - Emplacement des logs : répertoire `logs/` à la racine du projet (créé si absent) avec rotation hebdomadaire (`RotatingFileHandler`, taille max 5 Mo, 4 backups).
  - Intégration avec les outils système : les déploiements Linux peuvent rediriger vers `journalctl` ; documenter la commande d'installation dans les scripts si nécessaire.
- **Fonctionnalités de sécurité :** Pour les scripts critiques comme `flashBMCUtoKlipper_automation.py` :
  - Implémenter un mode `--dry-run` pour simuler les opérations.
  - Valider le firmware avec un checksum SHA256 (`--firmware-checksum`).
  - Vérifier la version de la cible (`--target-version`).
  - Permettre l'exécution de commandes de sauvegarde avant flashage (`--backup-command`).

## 5. Processus de Revue de Code

- **Nombre de reviewers :** Minimum deux reviewers pour tout changement affectant `firmware/` ou `bmcu_addon/`. Un reviewer est suffisant pour les modifications de documentation ou de scripts auxiliaires.
- **Critères d'acceptation :**
  - Respect des conventions de codage et des prérequis listés ci-dessus.
  - Tests pertinents exécutés (voir section Workflows) et résultats partagés dans la revue.
  - Absence de régressions détectées par les tests automatisés ou l'analyse statique.
- **Check-list de revue :**
  - [ ] Documentation mise à jour si comportement ou interface changent.
  - [ ] Logs et messages utilisateur clairs et localisés.
  - [ ] Permissions et interactions matériel validées (flash, accès série, etc.).
  - [ ] Sécurité et garde-fous (checksums, confirmations) actifs.

## 6. Gestion des Versions

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

## 7. Workflows Essentiels

### Compilation du Firmware

1.  **Naviguer vers le bon répertoire :** `cd firmware/`
2.  **Lancer le script de build :** `./build.sh`
3.  **Vérifier la sortie :** Le firmware compilé (`klipper.bin`) sera disponible dans `klipper/out/`.

#### Dépannage

- **Erreur : `riscv32-unknown-elf-gcc: command not found`** → Vérifier que le compilateur est installé et que le PATH contient le dossier des binaires.
- **Erreur de permission sur `build.sh`** → Donner les droits d'exécution : `chmod +x firmware/build.sh`.
- **Sous-module Klipper non initialisé** → Exécuter `git submodule update --init --recursive` avant la compilation.

### Flashage du Firmware

Le flashage doit être effectué avec le script interactif pour minimiser les risques.

1.  **Naviguer vers le bon répertoire :** `cd firmware/`
2.  **Lancer le script de flashage :** `python3 flash.py`
3.  **Suivre les instructions :** Le script guidera l'utilisateur à travers les étapes de vérification et de confirmation.

#### Dépannage

- **Accès refusé au périphérique USB (`Permission denied`)** → Ajouter l'utilisateur au groupe `dialout` ou ajuster les règles `udev`.
- **`python3` introuvable** → Vérifier l'installation de Python 3 et le lien symbolique `python3` dans `/usr/bin`.
- **Firmware non détecté** → Vérifier le câble USB et relancer le microcontrôleur en mode bootloader.

### Nettoyage des Artefacts

Pour nettoyer les fichiers générés par la compilation :

1.  **Naviguer vers le répertoire Klipper :** `cd klipper/`
2.  **Exécuter la commande de nettoyage :** `make clean` ou `rm -rf out/`

#### Dépannage

- **`make` introuvable** → Installer les outils de développement (`build-essential` sous Debian/Ubuntu).
- **Sous-module verrouillé en lecture seule** → Vérifier que le submodule n'a pas de modifications locales ou exécuter `git submodule foreach git clean -xfd`.
- **Dossier `out/` inaccessible** → S'assurer que le répertoire n'est pas utilisé par un processus (`lsof`) avant la suppression.

## 8. Points d'Attention Particuliers

- **Submodule Klipper :** Le répertoire `klipper/` est un submodule. Pour le mettre à jour, utilisez les commandes `git submodule sync` et `git submodule update --init --recursive`.
- **Protocole "bambubus" :** Il s'agit d'un protocole de communication série complexe et non standard. Toute modification liée à ce protocole nécessite une compréhension approfondie de son fonctionnement (baud rate de 1,250,000, checksums CRC8 DVB-S2 et CRC16 custom).
- **Environnement de Compilation :** La compilation pour le microcontrôleur CH32V203 requiert `gcc-riscv32-unknown-elf` et `picolibc-riscv32-unknown-elf`. La variable `CROSS_PREFIX` dans `klipper/src/ch32v20x/Makefile` doit être correctement définie (`riscv32-unknown-elf-`).
- **Documentation externe recommandée :**
  - Protocole bambubus : [https://github.com/bambulab/BambuBus-protocol](https://github.com/bambulab/BambuBus-protocol)
  - Microcontrôleur CH32V203 : [https://www.wch-ic.com/products/CH32V203.html](https://www.wch-ic.com/products/CH32V203.html)
  - Documentation Klipper : [https://www.klipper3d.org/](https://www.klipper3d.org/)
