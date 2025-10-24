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

1.  **Corriger le Baud Rate :** Le firmware du BMCU-C communique à **1,250,000 baud**. Cette vitesse n'est souvent pas supportée par défaut par PySerial. Il sera probablement nécessaire de recompiler Klipper ou de trouver une autre solution pour permettre cette vitesse de communication. Le code est actuellement configuré pour un baud rate standard (115200) qui ne fonctionnera pas.

2.  **Valider et Compléter la Structure des Paquets :** La fonction `_send_command` dans `bmcu.py` est une première tentative. Il faut la comparer avec le trafic réel d'un BMCU-C pour s'assurer que tous les champs (adresses, numéros de paquets, etc.) sont corrects.

3.  **Implémenter la Lecture des Réponses :** Le code actuel n'écoute pas les réponses du BMCU-C. Il est indispensable d'ajouter une boucle de lecture sur le port série pour recevoir, parser et réagir aux messages de statut (présence de filament, erreurs, etc.).

4.  **Finaliser les Commandes :** Les commandes G-code `BMCU_...` doivent être testées et leur payload ajusté pour correspondre à ce que le firmware attend réellement.

## Installation (pour le développement)

1.  **Copier le module Klipper :**
    *   `cp klipper/klippy/extras/bmcu.py /home/pi/klipper/klippy/extras/`

2.  **Copier les fichiers de configuration :**
    *   `cp config/bmcu_config.cfg config/bmcu_macros.cfg /home/pi/klipper_config/`

3.  **Modifier `printer.cfg` :**
    *   Ajoutez `[include bmcu_config.cfg]` et `[include bmcu_macros.cfg]`.
    *   Ajoutez la section `[bmcu]` en spécifiant le bon port série :
        ```cfg
        [bmcu]
        serial: /dev/serial/by-id/usb-your_bmcu_serial_id_here
        # baud: 1250000 # À activer quand le support sera prêt
        ```

4.  **Redémarrer Klipper.**

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
