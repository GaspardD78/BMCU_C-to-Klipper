# Documentation : step_03_flash.py

## Objectif du script

Ce script est la troisième étape du workflow MatrixFlow. Son objectif est de téléverser (flasher) le firmware `klipper.bin`, compilé à l'étape précédente, dans la mémoire du microcontrôleur de la carte BMCU-C via une connexion série (USB).

## Logique métier

Le flashage est une opération délicate qui interagit directement avec le matériel. La logique de ce script vise à la rendre aussi fiable et automatique que possible :
1.  **Utilisation de l'outil `wchisp`** : Le microcontrôleur CH32V203 nécessite un outil de flashage spécifique. Ce script utilise `wchisp`, un outil open-source en Rust conçu pour les MCU WCH. Une version pré-compilée de cet outil est fournie dans le dossier `bin/` pour éviter à l'utilisateur de devoir l'installer manuellement.
2.  **Gestion des conflits de port série** : Si le service Klipper est en cours d'exécution sur la machine hôte, il peut monopoliser le port série et empêcher l'outil de flashage de communiquer avec la carte. Pour éviter ce conflit, le script tente d'arrêter le service Klipper (`klipper.service`) avant le flashage et de le redémarrer après, que l'opération ait réussi ou échoué.
3.  **Détection automatique du port série** : Le nom du port série (`/dev/ttyUSB0`, `/dev/serial/by-id/...`) peut varier d'une machine à l'autre. Le script peut détecter automatiquement les ports disponibles pour simplifier la tâche de l'utilisateur. L'utilisateur peut également spécifier un port manuellement s'il le souhaite.
4.  **Sécurité** : Le script vérifie la présence du firmware et de l'outil `wchisp` avant de commencer toute opération.

## Logique de construction

Le script est construit autour de la classe `FlashManager`.

-   **Initialisation (`__init__`)** :
    -   Définit les chemins vers le répertoire de Klipper et le fichier `klipper.bin`.

-   **`_run_command()`** :
    -   Similaire aux autres étapes, mais ajoute le répertoire `bin/` (contenant `wchisp`) au `PATH` de l'environnement d'exécution.
    -   Possède un paramètre `ignore_errors` pour les commandes qui ne doivent pas bloquer le processus en cas d'échec (comme l'arrêt/démarrage du service Klipper, qui peut ne pas exister).

-   **`_manage_klipper_service()`** :
    -   Fonction dédiée à l'arrêt (`stop`) et au démarrage (`start`) du service `klipper.service`.
    -   Elle utilise `sudo systemctl` et ignore les erreurs, car l'utilisateur n'a pas forcément `sudo` ou Klipper n'est pas forcément installé en tant que service.

-   **`detect_serial_devices()`** :
    -   Recherche les fichiers de périphériques correspondant à des motifs courants pour les connexions série sur Linux (`/dev/serial/by-id/*`, `/dev/ttyUSB*`, etc.).
    -   Retourne une liste des périphériques trouvés.

-   **`run()`** :
    -   Orchestre le processus de flashage :
        1.  Vérifie que le firmware `klipper.bin` existe.
        2.  Vérifie que l'exécutable `wchisp` est trouvable dans le `PATH` modifié.
        3.  Si aucun port série n'est fourni par l'utilisateur, il appelle `detect_serial_devices()` et utilise le premier trouvé.
        4.  Appelle `_manage_klipper_service("stop")`.
        5.  Exécute la commande `wchisp flash` avec les bons arguments (port et chemin du firmware) dans un bloc `try...finally`.
        6.  Le bloc `finally` garantit que `_manage_klipper_service("start")` est appelé à la fin, même si le flashage échoue.

-   **`main()`** :
    -   Utilise `argparse` pour permettre à l'utilisateur de passer le chemin du port série en argument de ligne de commande (`--device`).
    -   Instancie `FlashManager`, exécute le processus de flashage et gère les exceptions.

## Historique des modifications

*Cette section est laissée vide et sera complétée au fil des futures modifications du code.*

## Problèmes connus

- Le script requiert les droits `sudo` pour arrêter/démarrer le service Klipper. Si l'utilisateur ne peut pas utiliser `sudo`, cette étape sera sautée, ce qui pourrait causer des échecs de flashage si Klipper est en cours d'exécution.
- La détection automatique du port série peut ne pas être fiable si plusieurs périphériques série sont connectés. Dans ce cas, l'utilisateur doit spécifier le port manuellement.

*Cette section est laissée vide et sera complétée si d'autres bugs ou points de vigilance sont identifiés.*
