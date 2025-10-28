# Protocole de tests manuels – automation_cli.py

Ce protocole décrit les vérifications manuelles à réaliser avant toute mise à
jour majeure du **gestionnaire interactif** (`flash_automation/automation_cli.py`).
Il se concentre sur trois scénarios remontés lors des sessions d'essai :

1. Gestion propre de `Ctrl+C` dans le menu principal.
2. Interruption volontaire au milieu d'une action et retour au menu.
3. Validation des invites disposant de valeurs par défaut.

Chaque scénario s'effectue depuis le dossier `flash_automation/` avec
`python3 automation_cli.py` (éventuellement en `--dry-run` si aucun matériel
n'est branché).

## Préparation

- Activer l'environnement Python utilisé en production (`source .venv/bin/activate`).
- Nettoyer les logs précédents : `rm -f ../logs/automation-*.log`.
- Démarrer le script : `python3 automation_cli.py --dry-run`.
- Laisser le tableau de synthèse final s'afficher pour confirmer la réussite.

## Cas de test détaillés

| ID | Objectif | Étapes | Résultat attendu |
|----|----------|--------|------------------|
| MT-01 | Interrompre le **menu principal** avec `Ctrl+C`. | 1. Lancer le menu.<br>2. Dès que l'invite `Votre choix :` apparaît, presser `Ctrl+C` une fois. | Le journal affiche un avertissement puis l'information « Menu principal réarmé ; choisissez une option. ». Le menu est redessiné sans quitter le programme, aucune suppression du dépôt n'est déclenchée, et `logs/automation-*.log` continue d'être alimenté. |
| MT-02 | Interrompre une **action en cours** (ex. compilation) avec `Ctrl+C`. | 1. Depuis le menu, choisir `3` (compilation).<br>2. Dès que la commande est annoncée, presser `Ctrl+C`. | Le script annonce l'interruption, nettoie les processus (`Arrêt manuel demandé...`), puis revient automatiquement au menu principal. La prochaine sélection est possible sans relancer le programme. |
| MT-03 | Vérifier les **valeurs par défaut** des invites critiques. | 1. Depuis le menu, choisir `6` (automatisation distante).<br>2. Laisser vide l'utilisateur SSH/IPMI pour accepter `root`.<br>3. Laisser vide le chemin distant pour accepter `/tmp/klipper_firmware.bin`.<br>4. Répondre directement `Entrée` à la confirmation « Attendre le redémarrage… ». | Les valeurs par défaut sont injectées dans le résumé de la commande (`--bmc-user root`, `--remote-firmware-path /tmp/klipper_firmware.bin`) et la confirmation considère la réponse vide comme `Oui`. |

> 💡 Les journaux `[progress]` affichés pendant `MT-02` doivent montrer la
> progression textuelle (ex. `receiving objects`, `compilation [#####.....] 45%`).

## Validation finale

Une fois les trois scénarios validés :

1. Quitter proprement le menu (`X`).
2. Archiver le journal généré dans `docs/test-logs/` si de nouveaux éléments
   sont observés (voir exemple le plus récent).
3. Noter tout écart ou message inattendu dans le même rapport pour alimenter les
   corrections futures.

En cas d'échec d'un scénario, consigner immédiatement :

- La commande exécutée et le contexte (machine, distribution, version de Python).
- La sortie console et le nom du fichier `logs/automation-*.log`.
- Les ajustements réalisés pour corriger le problème (pull request ou commit).

Ce protocole peut être reproduit sur une session SSH distante en
redirigeant les logs vers `screen` ou `tmux` ; seules les touches `Ctrl+C` et
`Entrée` sont nécessaires.
