# Intégration BMCU-C avec Klipper et Happy Hare (PREUVE DE CONCEPT)

**ATTENTION : Ce projet est une preuve de concept et n'est PAS fonctionnel en l'état.**

Ce dépôt contient une base de code solide pour intégrer un BMCU-C avec Klipper et Happy Hare, mais l'implémentation du protocole de communication "bambubus" n'a pas pu être finalisée sans accès direct au matériel pour les tests.

## État Actuel

*   **Structure du projet :** Tous les fichiers nécessaires sont présents (`bmcu.py`, `config/bmcu_config.cfg`, `config/bmcu_macros.cfg`).
*   **Intégration Happy Hare :** La configuration pour utiliser le `MacroSelector` de Happy Hare est correcte.
*   **Checksums :** Les algorithmes de checksum `CRC8 DVB-S2` et `CRC16` spécifiques au "bambubus" ont été implémentés en Python.
*   **Communication :** Le module Klipper contient une logique de base pour envoyer des paquets, mais elle est simplifiée et doit être complétée.

## Prochaines Étapes pour Finaliser l'Intégration

Un développeur ayant accès à un BMCU-C physique devra réaliser les étapes suivantes :

1.  **Valider le débit 1,25 Mbaud :** Le firmware du BMCU-C communique à **1 250 000 baud** et le module Klipper ouvre désormais le port à cette vitesse par défaut. Lors de l'initialisation, PySerial est interrogé : si le débit effectif diffère, Klipper affiche un message d'erreur invitant à activer `set_custom_baudrate()` (option `use_custom_baudrate: True` si votre build PySerial le propose), à recompiler Klipper/PySerial pour supporter le 1,25 Mbaud ou à fournir un débit alternatif via `fallback_baud` après reconfiguration du BMCU.

2.  **Valider et Compléter la Structure des Paquets :** La fonction `_send_command` dans `bmcu.py` est une première tentative. Il faut la comparer avec le trafic réel d'un BMCU-C pour s'assurer que tous les champs (adresses, numéros de paquets, etc.) sont corrects.

3.  **Implémenter la Lecture des Réponses :** Le code actuel n'écoute pas les réponses du BMCU-C. Il est indispensable d'ajouter une boucle de lecture sur le port série pour recevoir, parser et réagir aux messages de statut (présence de filament, erreurs, etc.).

4.  **Finaliser les Commandes :** Les commandes G-code `BMCU_...` doivent être testées et leur payload ajusté pour correspondre à ce que le firmware attend réellement.

## Installation (pour le développement)

1.  **Installation automatisée (recommandée)** :
    *   Le script `scripts/setup_bmcu.py` copie le module, les fichiers de configuration et peut mettre à jour `printer.cfg`.
        ```bash
        python3 scripts/setup_bmcu.py \
          --klipper-path ~/klipper \
          --config-path ~/klipper_config \
          --printer-config ~/klipper_config/printer.cfg
        ```
        Ajoutez `--list-firmware` pour afficher les binaires fournis, `--firmware-variant <nom>`/`--firmware-dest <chemin>` pour en déployer un vers la machine cible, et `--flash --flash-device <interface>` pour chaîner un `make flash`.

2.  **Installation manuelle** :
    *   Copier le module Klipper : `cp klipper/klippy/extras/bmcu.py /home/pi/klipper/klippy/extras/`
    *   Copier les fichiers de configuration : `cp config/bmcu_config.cfg config/bmcu_macros.cfg /home/pi/klipper_config/`
    *   Ajouter dans `printer.cfg` :
        ```cfg
        [include bmcu_config.cfg]
        [include bmcu_macros.cfg]

        [bmcu]
        serial: /dev/serial/by-id/usb-your_bmcu_serial_id_here
        baud: 1250000
        # use_custom_baudrate: True  # Active set_custom_baudrate() sur une build PySerial patchée
        # fallback_baud: 250000      # Si vous avez recompilé le BMCU pour un autre débit
        ```

3.  **Redémarrer Klipper.**

## Compilation et Flashage du Firmware Klipper

Pour compiler le firmware Klipper pour la BMCU-C, vous devez d'abord installer les dépendances nécessaires sur votre système.

### Dépendances Requises

Assurez-vous d'avoir les paquets suivants installés :

*   `gcc-riscv64-unknown-elf`
*   `picolibc-riscv64-unknown-elf`
*   `wchisp` (installable via `pip3 install wchisp`)

Sur les systèmes basés sur Debian (comme Raspberry Pi OS), vous pouvez les installer avec la commande suivante :

```bash
sudo apt-get update
sudo apt-get install gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf
pip3 install wchisp
```

**Note :** Une chaîne de compilation `riscv64-unknown-elf` correctement installée devrait automatiquement trouver ses bibliothèques et en-têtes (comme `picolibc`). Si vous rencontrez des erreurs de compilation concernant des fichiers d'en-tête manquants, assurez-vous que votre environnement de compilation est correctement configuré.

### Compilation et Flashage

Une fois les dépendances installées, vous pouvez compiler et flasher le firmware en utilisant la commande `make flash` depuis le répertoire `klipper`.

```bash
cd klipper
make flash FLASH_DEVICE=/dev/ttyUSB0
```

Remplacez `/dev/ttyUSB0` par le port série de votre BMCU-C.

## Documentation complémentaire

*   [Mise à jour de Klipper et intégration Mainsail pour le BMCU-C](docs/bmcu_c_flashing_mainsail.md) : procédure pas-à-pas pour compiler, flasher le CH32V203 et déclarer la carte dans Mainsail.
*   [Audit du portage CH32V203 et procédures de flash](docs/ch32v203_audit_et_flash.md) : état du support bas niveau et méthode de flash depuis un CB2 ou un Raspberry Pi.

## Organisation du dépôt

| Répertoire | Contenu |
| --- | --- |
| `config/` | Fichiers Klipper prêts à l'emploi (`bmcu_config.cfg`, `bmcu_macros.cfg`). |
| `firmware/` | Images binaires officielles du BMCU-C triées par variantes. |
| `hardware/` | Ressources matérielles (schémas, PCB) pour la carte principale et la carte capteurs. |
| `klipper/` | Copie figée du dépôt Klipper incluant le module expérimental `bmcu.py`. |
| `BMCU`, `Happy-Hare` | Sous-modules optionnels pointant vers les projets amont pour référence. |

## Ressources firmware

Les dumps fournis par Bambu pour les différentes variantes du buffer sont désormais regroupés dans le répertoire `firmware/` afin de faciliter leur consultation et d'éviter la duplication d'arborescences intermédiaires.【F:firmware/README.md†L3-L5】
