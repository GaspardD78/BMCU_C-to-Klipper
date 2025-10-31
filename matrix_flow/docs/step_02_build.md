# Documentation : step_02_build.py

## Objectif du script

Ce script est la deuxième étape du workflow MatrixFlow. Son rôle est de compiler le code source de Klipper pour générer un binaire de firmware (`klipper.bin`) spécifiquement adapté au microcontrôleur CH32V20X de la carte BMCU-C. Il s'appuie sur l'environnement et les sources préparés par `step_01_environment.py`.

## Logique métier

La compilation d'un firmware Klipper pour une cible non standard comme le CH32V20X nécessite plusieurs étapes critiques :
1.  **Personnalisation de Klipper** : Le support du CH32V20X n'est pas inclus dans la version officielle de Klipper. Il est donc nécessaire d'appliquer des modifications (fichiers sources additionnels et patchs) pour ajouter le support de cette architecture. Ces modifications sont stockées dans le dossier `klipper_overrides/`.
2.  **Configuration de la compilation** : Le processus de compilation de Klipper est contrôlé par un fichier `.config`. Ce script copie une configuration prédéfinie (`klipper.config`) qui contient les bons paramètres pour la carte BMCU-C (type de microcontrôleur, interface de communication USB, etc.).
3.  **Compilation avec la bonne Toolchain** : La compilation doit impérativement utiliser la toolchain RISC-V téléchargée à l'étape 1. Le script s'assure que le `PATH` de l'environnement d'exécution inclut le répertoire `bin` de cette toolchain.
4.  **Vérification du résultat** : Après l'exécution de `make`, le script vérifie que le fichier binaire `klipper.bin` a bien été créé. C'est une sécurité importante, car `make` peut parfois se terminer sans erreur (code de sortie 0) même si la compilation a échoué à produire l'artefact final.

## Logique de construction

Le script est construit autour de la classe `BuildManager`.

-   **Initialisation (`__init__`)** :
    -   Définit les chemins essentiels : `base_dir`, `.cache`, `klipper`, `klipper_overrides`, et le chemin du fichier de configuration Klipper par défaut (`klipper.config`).
    -   Charge la configuration JSON.
    -   Définit le chemin de sortie attendu pour le firmware (`klipper.bin`).

-   **`_run_command()`** :
    -   Similaire à celui de l'étape 1, mais avec une modification cruciale : il modifie la variable d'environnement `PATH` pour y ajouter le chemin vers le `bin` de la toolchain RISC-V.
    -   Ceci garantit que les commandes `make` appelleront les bons compilateurs (`riscv-none-elf-gcc`, etc.) au lieu de ceux du système.

-   **`_apply_overrides()`** :
    -   Copie récursivement le contenu de `klipper_overrides/` dans le répertoire de Klipper, écrasant les fichiers si nécessaire. C'est ainsi que de nouveaux fichiers de support pour le CH32V20X sont ajoutés.
    -   Recherche ensuite des fichiers `.patch` dans `klipper_overrides/` et les applique en utilisant la commande `git apply`.
    -   La gestion d'erreur vérifie si un patch a déjà été appliqué pour éviter les échecs lors de re-exécutions.

-   **`run()`** :
    -   Orchestre le processus de compilation :
        1.  Vérifie que le répertoire Klipper existe.
        2.  Appelle `_apply_overrides()` pour patcher les sources.
        3.  Copie le fichier `klipper.config` vers `klipper/.config`.
        4.  Exécute `make olddefconfig` pour préparer et valider la configuration Klipper.
        5.  Exécute `make clean` pour assurer une compilation propre.
        6.  Lance la compilation avec `make`.
        7.  Vérifie l'existence du fichier `klipper.bin`. S'il est manquant, une `BuildError` détaillée est levée, incluant le `stdout` et `stderr` de `make` pour faciliter le diagnostic.

-   **`main()`** :
    -   Point d'entrée qui instancie `BuildManager`, exécute le processus et gère les exceptions pour fournir un retour clair à l'utilisateur.

## Historique des modifications

*Cette section est laissée vide et sera complétée au fil des futures modifications du code.*

## Problèmes connus

*Cette section est laissée vide et sera complétée si des bugs ou des points de vigilance sont identifiés.*
