# Documentation : step_01_environment.py

## Objectif du script

Ce script est la première étape du workflow MatrixFlow. Son rôle est de préparer l'environnement de travail pour s'assurer que toutes les dépendances, les outils et les codes sources nécessaires sont disponibles et correctement configurés pour les étapes suivantes de compilation et de flashage du firmware Klipper sur le BMCU-C.

## Logique métier

Pour garantir une compilation fiable et reproductible, il est essentiel de contrôler précisément l'environnement. Plutôt que de dépendre des outils installés sur le système de l'utilisateur (qui peuvent varier en version ou en configuration), ce script met en place un environnement de travail autonome et isolé dans un dossier `.cache/`.

La logique est la suivante :
1.  **Vérifier les dépendances de base** : S'assurer que des outils système indispensables comme `git` et `make` sont présents.
2.  **Télécharger la Toolchain RISC-V** : La compilation pour le microcontrôleur CH32V203 nécessite une chaîne de compilation croisée (toolchain) spécifique. Le script la télécharge automatiquement depuis une URL définie dans `config.json` pour garantir que la bonne version est toujours utilisée.
3.  **Cloner le dépôt Klipper** : Le firmware est basé sur Klipper. Le script clone le dépôt officiel de Klipper et se positionne sur une version (tag Git) spécifique, également définie dans `config.json`, pour éviter les problèmes liés à des versions de développement instables.

Toutes ces opérations sont effectuées dans un dossier cache pour ne pas polluer le répertoire du projet et pour pouvoir réutiliser les téléchargements lors d'exécutions futures.

## Logique de construction

Le script est construit autour de la classe `EnvironmentManager`, qui encapsule toute la logique de préparation.

-   **Initialisation (`__init__`)** :
    -   Définit les chemins clés : le répertoire de base, le dossier `.cache/`, le chemin vers le fichier `config.json` et le futur emplacement de Klipper.
    -   Appelle `_load_config()` pour charger les configurations (URL, versions, etc.).

-   **`_load_config()`** :
    -   Lit et parse le fichier `config.json`. En cas d'erreur, une exception `EnvironmentError` est levée.

-   **`_run_command()`** :
    -   Une fonction utilitaire robuste pour exécuter des commandes externes (comme `git`).
    -   Elle capture `stdout` et `stderr`, et lève une exception `EnvironmentError` détaillée en cas d'échec, ce qui simplifie grandement le débogage.

-   **`check_system_dependencies()`** :
    -   Utilise `shutil.which()` pour vérifier la présence des dépendances système de base dans le `PATH` de l'utilisateur.

-   **`ensure_klipper_repo()`** :
    -   Vérifie si le dépôt Klipper existe déjà dans le cache.
    -   Si non, il le clone (`git clone`).
    -   Si oui, il s'assure qu'il est à jour et sur la bonne branche/tag (`git fetch` et `git checkout`).

-   **`ensure_toolchain()`** :
    -   Vérifie si la toolchain est déjà présente.
    -   Sinon, elle télécharge l'archive `.tar.gz` depuis l'URL configurée en utilisant `urllib`.
    -   Elle extrait ensuite l'archive dans le dossier `.cache/`. La gestion des chemins est faite pour s'adapter à la structure de l'archive.
    -   L'archive téléchargée est supprimée après l'extraction.

-   **`run()`** :
    -   La méthode principale qui orchestre l'appel des autres méthodes dans le bon ordre.

-   **`main()`** :
    -   Le point d'entrée du script. Il instancie `EnvironmentManager` et appelle `run()`.
    -   Il inclut un bloc `try...except` pour attraper les `EnvironmentError` et afficher un message clair à l'utilisateur avant de quitter.

## Historique des modifications

*Cette section est laissée vide et sera complétée au fil des futures modifications du code.*

## Problèmes connus

*Cette section est laissée vide et sera complétée si des bugs ou des points de vigilance sont identifiés.*
