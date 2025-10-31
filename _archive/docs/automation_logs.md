# Journaux et rapports d'automatisation

Ce document explique comment récupérer les journaux générés par `automation_cli.py`,
comprendre le tableau de synthèse affiché en console et exporter ces informations
au format JSON.

## Emplacement et format des journaux

Chaque exécution de `automation_cli.py` crée un fichier de log dédié dans le
répertoire externe `~/BMCU_C_to_Klipper_logs/` (par défaut) afin que les
journaux survivent aux opérations de nettoyage du dépôt :

```
~/BMCU_C_to_Klipper_logs/automation-<horodatage>.log
```

* `<horodatage>` suit le format `YYYYMMDDTHHMMSSZ` (par exemple
  `20240514T172233Z`) et correspond à l'instant de lancement de l'automatisation
  en temps universel (UTC).
* Les entrées de log utilisent un horodatage ISO 8601 complet avec fuseau
  (`2024-05-14T17:22:33+0000 | INFO | automation | ...`) afin de faciliter la
  corrélation avec d'autres systèmes de supervision. Les lignes préfixées par
  `[progress]` détaillent l'étape courante (clone Git, compilation, transfert…)
  et affichent un pourcentage lorsqu'il est disponible.
* Définissez la variable d'environnement `BMCU_LOG_ROOT` pour changer le
  dossier parent des journaux. Si la valeur pointe vers un chemin situé dans le
  dépôt Git, elle sera automatiquement redirigée vers `~/BMCU_C_to_Klipper_logs`
  avec un avertissement dans la console.

> 💡 En cas d'interruption manuelle (`Ctrl+C`), le script rappelle le chemin du
> fichier de log actif juste avant de quitter. Un `Ctrl+C` isolé dans le menu
> principal affiche également `Menu principal réarmé ; choisissez une option.`
> et continue d'alimenter le même journal.

## Tableau de synthèse en console

À la fin de chaque exécution, un tableau récapitulatif est affiché dans la
console. Il couvre trois vérifications clés :

1. **Permissions des scripts** (`build.sh`, `flash_automation.sh`)
2. **Dépendances Python** (`requirements.txt` et `requirements.lock`)
3. **Compilation du firmware** (`build.sh`)

Chaque ligne indique l'état de la vérification ainsi qu'un message détaillé.
Les couleurs sont activées automatiquement si la sortie standard est reliée à un
terminal :

| Couleur / Icône | Statut           | Signification                                                |
|-----------------|------------------|--------------------------------------------------------------|
| `✔` vert        | `OK`             | Vérification réussie sans intervention supplémentaire.       |
| `⚠` jaune       | `AVERTISSEMENT`  | Vérification partielle (ex. exécution en `--dry-run`).       |
| `✖` rouge       | `ÉCHEC`          | Action interrompue ou prérequis manquant.                    |
| `⏭` bleu        | `IGNORÉ`         | Vérification explicitement ignorée (non utilisée actuellement). |
| `…` gris/cyan   | `EN ATTENTE` / `EN COURS` | Vérification non déclenchée pendant la session.    |

Le tableau reste visible même en mode non interactif (`--action`) afin de
permettre une lecture rapide de l'état général.

## Export JSON des rapports

Ajoutez l'option `--report-json` pour enregistrer la synthèse dans un fichier
structuré :

```
python3 automation_cli.py --action 1 --report-json reports/dernier-rapport.json
```

Le fichier généré contient :

- le chemin du fichier de log correspondant ;
- la date/heure de génération (`generated_at`) ;
- la liste des vérifications avec leur statut, description et horodatages de
  début/fin.

Les répertoires parents du fichier sont créés automatiquement si nécessaire.
