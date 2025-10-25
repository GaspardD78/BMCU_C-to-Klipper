# Intégration du BMCU-C avec Klipper et Happy Hare

**⚠️ Attention : Ce projet est une preuve de concept et n'est pas entièrement fonctionnel en l'état. Il est destiné aux développeurs et aux utilisateurs avancés qui souhaitent contribuer à son développement.**

Ce dépôt fournit une base de code pour intégrer un BMCU-C (un clone open-source de l'AMS de Bambu Lab) avec Klipper, en utilisant le framework Happy Hare pour la gestion des filaments.

L'objectif de ce projet est de fournir une alternative open-source complète pour la gestion multi-filaments sur les imprimantes 3D Klipper.

## 📝 État du Projet

Ce projet est actuellement au stade de **preuve de concept**. Bien que la structure de base soit en place, l'implémentation du protocole de communication "bambubus" n'a pas pu être finalisée sans accès direct au matériel pour les tests.

### Ce qui fonctionne :

*   **Structure du projet :** Tous les fichiers nécessaires sont présents (`bmcu.py`, `config/bmcu_config.cfg`, `config/bmcu_macros.cfg`).
*   **Intégration Happy Hare :** La configuration pour utiliser le `MacroSelector` de Happy Hare est correcte.
*   **Checksums :** Les algorithmes de checksum `CRC8 DVB-S2` et `CRC16` spécifiques au "bambubus" ont été implémentés en Python.

### Prochaines étapes :

Un développeur ayant accès à un BMCU-C physique devra réaliser les étapes suivantes :

1.  **Valider le débit de 1,25 Mbaud** et la communication série.
2.  **Valider et compléter la structure des paquets** en comparant avec le trafic réel.
3.  **Implémenter la lecture des réponses** du BMCU-C.
4.  **Finaliser les commandes G-code** et leur payload.

## ✨ Fonctionnalités

*   **Intégration Klipper :** Un module Klipper (`bmcu.py`) pour la communication avec le BMCU-C.
*   **Configuration Happy Hare :** Des fichiers de configuration prêts à l'emploi pour le `MacroSelector`.
*   **Firmware Klipper pour CH32V203 :** Un portage du firmware Klipper pour le microcontrôleur du BMCU-C.
*   **Scripts d'automatisation :** Des scripts pour simplifier l'installation et le flashage.

## ⚙️ Prérequis

### Matériel

*   Un BMCU-C (ou clone compatible)
*   Une imprimante 3D fonctionnant avec Klipper
*   Un ordinateur pour flasher le firmware (Raspberry Pi, CB2, ou autre)
*   Un adaptateur de flashage (WCH-Link, ST-Link, ou adaptateur série)

### Logiciel

*   Une installation fonctionnelle de Klipper et Mainsail/Fluidd
*   Python 3
*   Les dépendances pour la compilation du firmware (voir la section "Pour les développeurs")

## 🚀 Installation

L'installation est simplifiée grâce à un script automatisé.

1.  **Clonez ce dépôt sur votre machine hôte Klipper :**
    ```bash
    git clone https://github.com/votre-utilisateur/votre-repo.git
    cd votre-repo
    ```

2.  **Exécutez le script d'installation :**
    ```bash
    python3 scripts/setup_bmcu.py --klipper-path ~/klipper --config-path ~/klipper_config --printer-config ~/klipper_config/printer.cfg
    ```
    Le script copiera les fichiers nécessaires et vous guidera pour la configuration.

3.  **Redémarrez Klipper.**

Pour une installation manuelle, veuillez vous référer au [guide d'installation manuelle](docs/usage.md).

## ⚡ Démarrage Rapide

Après l'installation, vous pouvez tester la communication avec le BMCU-C en utilisant les macros G-code fournies.

*   `BMCU_ENABLE_SPOOLS` : Active les moteurs du BMCU-C.
*   `BMCU_SPOOL_MOVE GATE=1 MOVE=120 VELOCITY=25` : Déplace le filament du tiroir 1.
*   `BMCU_HOME` : Lance une séquence de "homing".

## 👨‍💻 Pour les Développeurs : Compilation et Flashage

Cette section est destinée aux développeurs qui souhaitent compiler et flasher le firmware Klipper sur le BMCU-C.

### Dépendances

*   `gcc-riscv64-unknown-elf`
*   `picolibc-riscv64-unknown-elf`
*   `wchisp`

Pour des instructions d'installation détaillées, consultez le [guide de compilation et flashage](docs/ch32v203_audit_et_flash.md).

### Procédure

Un script `flash_bmcu.sh` est fourni pour automatiser le processus.

1.  **Rendre le script exécutable :**
    ```bash
    chmod +x flash_bmcu.sh
    ```

2.  **Lancer le script :**
    ```bash
    ./flash_bmcu.sh
    ```

3.  **Suivez les instructions.** Le script vous guidera à travers la configuration de Klipper (`menuconfig`) et le processus de flashage.

Pour des informations plus détaillées, y compris des procédures de flashage manuelles pour différentes plateformes, veuillez consulter notre [documentation technique](docs/ch32v203_audit_et_flash.md).

## 📁 Organisation du Dépôt

| Répertoire      | Contenu                                                               |
| --------------- | --------------------------------------------------------------------- |
| `config/`       | Fichiers de configuration Klipper (`bmcu_config.cfg`, `bmcu_macros.cfg`). |
| `docs/`         | Documentation détaillée du projet.                                    |
| `firmware/`     | Binaires officiels du firmware du BMCU-C.                             |
| `hardware/`     | Schémas et fichiers PCB pour le matériel.                             |
| `klipper/`      | Copie du dépôt Klipper avec le module `bmcu.py`.                      |
| `scripts/`      | Scripts d'automatisation pour l'installation et le flashage.          |
| `BMCU`, `Happy-Hare` | Sous-modules Git vers les projets originaux.                     |

## 📚 Documentation

*   [Guide d'utilisation et d'installation manuelle](docs/usage.md)
*   [Guide de flashage et d'intégration Mainsail](docs/bmcu_c_flashing_mainsail.md)
*   [Audit technique et procédure de flashage avancée](docs/ch32v203_audit_et_flash.md)
*   [Détails sur le protocole "bambubus"](docs/bambubus_protocol.md)

## ❤️ Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une "issue" pour signaler un bug ou proposer une amélioration, ou à soumettre une "pull request".

## 📄 Licence

Ce projet n'a pas de licence définie. Veuillez en ajouter une si vous souhaitez le distribuer.
