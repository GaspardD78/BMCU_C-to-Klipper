# Plan d'Amélioration du Processus de Flash pour le BMCU-C

## 1. Diagnostic du Problème Actuel

L'analyse approfondie du système de build de Klipper et du portage spécifique au BMCU-C a révélé une **divergence fondamentale** entre la méthode de flash prévue et celle implémentée, ce qui est la cause principale de la faible fiabilité du processus.

-   **La Méthode Prévue** : Le portage Klipper pour le microcontrôleur CH32V20x a été conçu pour être flashé via un outil externe spécialisé, **`wchisp`**. La logique est correctement définie dans la cible `make flash` du `Makefile` de l'architecture (`flash_automation/klipper_overrides/src/ch32v20x/Makefile`).
-   **La Méthode Implémentée** : L'outil de haut niveau du projet (`bmcu_tool.py`, via son `flash_manager.py`) ignore complètement cette méthode. À la place, il tente d'utiliser le script générique de Klipper, `flash_usb.py`.
-   **Le Point de Défaillance** : Le script `flash_usb.py` est un orchestrateur qui appelle des flasheurs standards (comme `dfu-util` ou `bossac`) en fonction du type de MCU. **Il n'a aucune connaissance du microcontrôleur CH32V20x**. Par conséquent, l'appel à ce script échoue systématiquement, rendant le processus de flash inutilisable en l'état.

De plus, le processus est entravé par une **contrainte matérielle** : le bootloader de la puce CH32V20x nécessite une intervention manuelle (appui sur le bouton "BOOT") pour être activé, ce qui rend une automatisation à 100% très difficile à atteindre.

## 2. Pistes d'Amélioration Proposées

### Piste n°1 : Correction et Intégration de `wchisp` (Priorité Haute)

C'est la correction la plus critique et la plus simple à mettre en œuvre.

-   **Action** : Modifier le module `flash_automation/flash_manager.py`. Remplacer l'appel au script `flash_usb.py` par un appel direct en ligne de commande à l'outil `wchisp`.
-   **Implémentation Exemple** :
    ```python
    # Dans flash_manager.py, méthode flash_serial
    command = [
        "wchisp", "flash", str(firmware_path),
        "--chip", "ch32v203",
        "--device", device
    ]
    self._run_command(command)
    ```
-   **Avantages** :
    -   Utilise la méthode de flash correcte et prévue.
    -   Augmentation massive de la fiabilité de base du processus.
    -   Relativement simple à implémenter.
-   **Inconvénients** :
    -   Ne résout pas le problème de l'entrée manuelle en mode bootloader.
    -   Requiert que l'utilisateur ait installé `wchisp` (`pip install wchisp`).

---

### Piste n°2 : Amélioration Radicale du Guidage Utilisateur (Priorité Moyenne)

Cette piste s'appuie sur la Piste n°1 et vise à résoudre le problème de l'expérience utilisateur lié à l'intervention manuelle.

-   **Action** : Transformer un échec de flash prévisible en une étape guidée.
-   **Implémentation** :
    1.  Dans `flash_manager.py`, entourer l'appel à `wchisp` d'un bloc `try...except`.
    2.  Si `wchisp` échoue avec une erreur indiquant que la carte n'est pas en mode bootloader, intercepter cette erreur.
    3.  Au lieu d'afficher une erreur technique, afficher un guide clair dans la console pour l'utilisateur, expliquant la procédure manuelle (débrancher, appuyer sur BOOT, rebrancher).
    4.  Demander à l'utilisateur d'appuyer sur "Entrée" pour lancer une nouvelle tentative de flash.
-   **Avantages** :
    -   Rend le processus de flash robuste et résilient aux erreurs.
    -   Améliore considérablement l'expérience pour les utilisateurs non techniques.
    -   Accepte la contrainte matérielle au lieu de la combattre.
-   **Inconvénients** :
    -   N'est pas une automatisation complète.

---

### Piste n°3 : Automatisation via Saut Logiciel (Priorité Basse / Expérimental)

Cette piste est une amélioration à plus long terme qui vise une automatisation quasi complète.

-   **Action** : Modifier le firmware Klipper pour permettre un redémarrage logiciel en mode bootloader.
-   **Implémentation** :
    1.  Ajouter une fonction en C au code source du portage (`flash_automation/klipper_overrides/src/ch32v20x/`) qui force un saut à l'adresse du bootloader (`0x1FFF8000`), en s'inspirant de la méthode trouvée sur Stack Overflow.
    2.  Exposer cette fonction comme une commande Klipper personnalisée (ex: `ENTER_BOOTLOADER`).
    3.  Modifier `flash_manager.py` pour qu'il envoie cette commande série à la carte *avant* d'appeler `wchisp`.
-   **Avantages** :
    -   Potentiel de supprimer complètement l'intervention manuelle.
-   **Inconvénients** :
    -   **Haute Complexité** : Nécessite une modification de bas niveau du firmware.
    -   **Risque d'Instabilité** : Peut causer des "bricks" si mal implémenté.
    -   Ne fonctionne que si un firmware Klipper fonctionnel est déjà sur la carte. Ne résout pas le cas du premier flash.

## 3. Recommandation

Il est fortement recommandé de suivre les pistes dans l'ordre de leur priorité :

1.  **Implémenter la Piste n°1 immédiatement.** C'est un bug qui doit être corrigé et qui apportera le plus grand gain de fiabilité avec le moins d'effort.
2.  **Implémenter la Piste n°2 ensuite.** Cette amélioration de l'expérience utilisateur rendra l'outil utilisable et agréable pour la majorité des utilisateurs.
3.  **Considérer la Piste n°3 comme une R&D à long terme.** Elle est prometteuse mais risquée et devrait être abordée une fois que le processus de base est stable et robuste.
