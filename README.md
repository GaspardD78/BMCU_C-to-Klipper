# Intégration du BMCU-C avec Klipper et Happy Hare

> ⚠️ **Statut : preuve de concept.** Ce projet n'est pas utilisable tel quel sans validation matérielle. Il s'adresse aux développeurs et utilisateurs avancés prêts à contribuer.

Ce dépôt propose une base open-source pour piloter un BMCU-C (clone communautaire de l'AMS Bambu Lab) depuis Klipper en s'appuyant sur le framework Happy Hare pour la gestion multi-filaments.

## Sommaire
- [État du projet](#état-du-projet)
- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation rapide](#installation-rapide)
- [Utilisation express](#utilisation-express)
- [Compilation & flashage développeur](#compilation--flashage-développeur)
- [Organisation du dépôt](#organisation-du-dépôt)
- [Documentation](#documentation)
- [Contribuer](#contribuer)
- [Licence](#licence)

## État du projet
- ✔️ **Structure logicielle prête** : module `bmcu.py`, macros Happy Hare et scripts fournis.
- ✔️ **Checksums bambubus** : implémentations `CRC8 DVB-S2` et `CRC16` en Python.
- ❌ **Communication matérielle non validée** : nécessite un BMCU-C réel pour finaliser le protocole `bambubus`.

### Prochaines étapes
Pour rendre l'intégration fonctionnelle, un contributeur équipé doit :
1. Vérifier le débit série à **1,25 Mbaud** et confirmer l'échange de messages.
2. Ajuster la **structure des paquets** à partir de captures réelles.
3. Implémenter la **lecture et le parsing** des réponses BMCU-C.
4. Finaliser les **macros G-code** et leurs payloads.

## Fonctionnalités
- **Module Klipper dédié** (`klipper/klippy/extras/bmcu.py`).
- **Configuration Happy Hare** prête (`config/bmcu_config.cfg`, `config/bmcu_macros.cfg`).
- **Firmware Klipper adapté** au microcontrôleur CH32V203.
- **Scripts d'automatisation** pour l'installation et le flashage.

## Prérequis
### Matériel
- Un **BMCU-C** (ou clone compatible).
- Une **imprimante Klipper** (ex. Voron, P1P sous Klipper, etc.).
- Une **machine hôte** (Raspberry Pi, CB2, PC Linux...).
- Un **outil de flashage** (WCH-Link, ST-Link ou adaptateur série).

### Logiciel
- Klipper + interface (Mainsail/Fluidd).
- **Python 3** sur l'hôte.
- Outils de compilation pour le CH32V203 (voir section développeur).

## Installation rapide
> Ces instructions copient les fichiers nécessaires dans votre environnement Klipper.

1. **Cloner le dépôt :**
   ```bash
   git clone https://github.com/Happy-Hare/BMCU_C-to-Klipper.git
   cd BMCU_C-to-Klipper
   ```
   Si vous travaillez depuis un fork, remplacez `Happy-Hare` par votre organisation ou votre compte personnel.
2. **Lancer l'assistant d'installation :**
   ```bash
   python3 scripts/setup_bmcu.py \
       --klipper-path ~/klipper \
       --config-path ~/klipper_config \
       --printer-config ~/klipper_config/printer.cfg
   ```
   Le script vérifie les chemins, copie les fichiers et ajoute les inclusions nécessaires.
3. **Redémarrer Klipper** via Mainsail/Fluidd ou `sudo service klipper restart`.

> 📘 Pour un déploiement manuel pas-à-pas (copie de fichiers, modifications de config), consultez [docs/usage.md](docs/usage.md).

## Utilisation express
Une fois l'installation effectuée :
- `BMCU_ENABLE_SPOOLS` : alimente les moteurs du BMCU-C.
- `BMCU_SPOOL_MOVE GATE=1 MOVE=120 VELOCITY=25` : déplace le filament du tiroir 1.
- `BMCU_HOME` : séquence de homing complet.

Ces macros sont déclarées dans `config/bmcu_macros.cfg`. Adaptez-les selon votre setup.

## Compilation & flashage développeur
Destiné à ceux qui doivent compiler ou mettre à jour le firmware.

### Dépendances
Installer les toolchains suivantes (ex. via votre gestionnaire de paquets) :
- `gcc-riscv64-unknown-elf`
- `picolibc-riscv64-unknown-elf`
- `wchisp`

Des instructions détaillées par plateforme sont disponibles dans [docs/ch32v203_audit_et_flash.md](docs/ch32v203_audit_et_flash.md).

### Procédure automatisée
Le script `flash_bmcu.sh` orchestre `menuconfig` et le flashage :
```bash
chmod +x flash_bmcu.sh
./flash_bmcu.sh
```
Suivez les invites pour sélectionner la cible, compiler puis flasher via votre programmateur.

### Procédure manuelle
La documentation décrit également des commandes `make menuconfig`, `make flash` et l'utilisation de `wchisp` manuelle pour Linux, macOS et Windows.

## Organisation du dépôt
| Répertoire | Contenu |
| --- | --- |
| `config/` | Fichiers de configuration Klipper (macros, includes...). |
| `docs/` | Guides d'installation, d'usage et références protocole. |
| `firmware/` | Binaires fournis du firmware BMCU-C. |
| `hardware/` | Schémas électroniques, PCB et docs matérielles. |
| `klipper/` | Copie du dépôt Klipper incluant le module `bmcu.py`. |
| `scripts/` | Scripts pour installer, configurer ou flasher. |
| `BMCU`, `Happy-Hare/` | Sous-modules vers les projets amont. |

## Documentation
- [Guide d'utilisation & installation manuelle](docs/usage.md)
- [Flashage + intégration Mainsail](docs/bmcu_c_flashing_mainsail.md)
- [Audit technique et procédures avancées](docs/ch32v203_audit_et_flash.md)
- [Détails du protocole "bambubus"](docs/bambubus_protocol.md)

## Contribuer
Les contributions sont encouragées :
1. Ouvrir une issue pour discuter d'un bug ou d'une idée.
2. Travailler sur une branche dédiée.
3. Soumettre une pull request détaillant les changements et tests.

## Licence
Aucune licence n'est définie. Ajoutez-en une si vous souhaitez redistribuer ou dériver ce projet.
