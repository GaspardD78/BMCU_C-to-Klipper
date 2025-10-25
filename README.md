# Intégration du BMCU-C avec Klipper et Happy Hare

> ⚠️ **Statut : preuve de concept.** L'intégration n'a pas encore été validée sur un BMCU-C réel. Ce dépôt s'adresse aux développeurs et "makers" souhaitant contribuer aux tests matériels et logiciels.

Ce dépôt open-source fournit les briques nécessaires pour piloter un BMCU-C (clone communautaire de l'AMS Bambu Lab) depuis Klipper à l'aide du framework Happy Hare.

## Sommaire
- [Vue d'ensemble](#vue-densemble)
- [Prérequis](#prérequis)
- [Mise en route rapide](#mise-en-route-rapide)
- [Utilisation des macros](#utilisation-des-macros)
- [Procédures développeur](#procédures-développeur)
- [Architecture du dépôt](#architecture-du-dépôt)
- [Aller plus loin](#aller-plus-loin)
- [Contribuer](#contribuer)
- [Licence](#licence)

## Vue d'ensemble
- ✔️ **Infrastructure logicielle prête** : module Klipper `bmcu.py`, macros Happy Hare et scripts d'installation.
- ✔️ **Implémentation des checksums Bambubus** (`CRC8 DVB-S2`, `CRC16`).
- ❌ **Communication matérielle à valider** : nécessite un BMCU-C opérationnel pour finaliser le protocole.

### Objectifs court terme
1. Confirmer le débit série à **1,25 Mbaud** et l'échange de paquets.
2. Ajuster la **structure des trames** selon des captures réelles.
3. Implémenter la **lecture/parsing** des réponses du BMCU-C.
4. Stabiliser les **macros G-code** pour l'usage quotidien.

## Prérequis
### Matériel
- Un **BMCU-C** (ou équivalent communautaire).
- Une **imprimante 3D** pilotée par Klipper.
- Une **machine hôte Linux** (Raspberry Pi, CB2, mini PC...).
- Un **programmateur** compatible CH32V203 (WCH-Link, ST-Link, adaptateur série...).

### Logiciel
- Klipper + interface (Mainsail/Fluidd) déjà installés.
- **Python 3** sur l'hôte pour exécuter les scripts.
- Toolchain RISC-V si vous prévoyez de recompiler le firmware (voir [Procédures développeur](#procédures-développeur)).

## Mise en route rapide
> Ces étapes installent le module et les configurations nécessaires dans votre environnement Klipper.

1. **Cloner le dépôt public et se placer dans le dossier :**
   ```bash
   git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
   cd BMCU_C-to-Klipper
   ```
2. **Lancer l'assistant d'installation :**
   ```bash
   python3 scripts/setup_bmcu.py \
       --klipper-path ~/klipper \
       --config-path ~/klipper_config \
       --printer-config ~/klipper_config/printer.cfg
   ```
   Le script vérifie les chemins, copie les fichiers nécessaires et ajoute les inclusions aux configurations Klipper.
3. **Redémarrer Klipper** (via Mainsail/Fluidd ou `sudo service klipper restart`).

### Installation manuelle (alternative)
1. Copier `klipper/klippy/extras/bmcu.py` dans votre dépôt Klipper (`~/klipper/klippy/extras/`).
2. Copier `config/bmcu_config.cfg` et `config/bmcu_macros.cfg` dans votre répertoire de configuration Klipper.
3. Ajouter les lignes suivantes à votre `printer.cfg` :
   ```ini
   [include bmcu_config.cfg]
   [include bmcu_macros.cfg]
   ```
4. Redémarrer Klipper.

## Utilisation des macros
Une fois l'installation terminée, les macros Happy Hare deviennent accessibles :
- `BMCU_ENABLE_SPOOLS` : alimente les moteurs du BMCU-C.
- `BMCU_SPOOL_MOVE GATE=<id> MOVE=<mm> VELOCITY=<mm_s>` : actionne un tiroir spécifique.
- `BMCU_HOME` : lance la séquence complète de homing.

Adaptez les paramètres à votre matériel. Les macros sont définies dans `config/bmcu_macros.cfg` et peuvent servir de base à vos automatisations.

## Procédures développeur
Destinées aux contributeurs qui souhaitent compiler ou flasher le firmware.

### Dépendances
Installez les toolchains suivants (paquets disponibles dans la plupart des distributions Linux) :
- `gcc-riscv64-unknown-elf`
- `picolibc-riscv64-unknown-elf`
- `wchisp`

Des instructions détaillées pour Linux, macOS et Windows sont disponibles dans [docs/ch32v203_audit_et_flash.md](docs/ch32v203_audit_et_flash.md).

### Flashage automatisé
Le script `flash_bmcu.sh` gère la configuration Klipper et le flashage :
```bash
chmod +x flash_bmcu.sh
./flash_bmcu.sh
```
L'assistant propose `menuconfig`, compile le firmware puis programme la carte via l'outil sélectionné.

### Flashage manuel
Vous pouvez également utiliser directement `make menuconfig`, `make flash` ou `wchisp`. Consultez la documentation ci-dessus pour les commandes détaillées et les paramètres spécifiques au CH32V203.

## Architecture du dépôt
| Répertoire | Contenu |
| --- | --- |
| `config/` | Macros et fichiers d'inclusion Klipper. |
| `docs/` | Guides pas-à-pas, fiches techniques, protocole. |
| `firmware/` | Binaires BMCU-C précompilés. |
| `hardware/` | Schémas électroniques, PCB et documentation matérielle. |
| `klipper/` | Copie de Klipper avec le module `bmcu.py`. |
| `scripts/` | Scripts d'installation, de configuration et de flashage. |
| `BMCU/`, `Happy-Hare/` | Sous-modules vers les projets amont. |

## Aller plus loin
- [Installation et utilisation détaillées](docs/usage.md)
- [Flashage + intégration Mainsail](docs/bmcu_c_flashing_mainsail.md)
- [Audit technique & procédures avancées](docs/ch32v203_audit_et_flash.md)
- [Protocole "bambubus"](docs/bambubus_protocol.md)

## Contribuer
1. Ouvrez une issue pour remonter un bug, partager des captures de bus ou proposer une amélioration.
2. Créez une branche dédiée pour vos développements.
3. Soumettez une pull request décrivant les changements et les tests effectués.

## Licence
Aucune licence n'est définie pour le moment. Ajoutez-en une avant toute redistribution ou dérivation du projet.
