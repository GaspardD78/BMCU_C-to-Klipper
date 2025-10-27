# Politique interne de stockage des artefacts

Cette note décrit les règles à respecter pour éviter que des fichiers volumineux ou générés ne soient versionnés accidentellement. Elle complète les contrôles automatisés introduits dans `ci/check_repo_artifacts.py`.

## Principes généraux
- Versionner uniquement le code source, la documentation et les scripts nécessaires à la reproduction du firmware.
- Conserver les artefacts produits (firmwares, journaux, archives temporaires) hors du dépôt Git. Utilisez des publications GitHub, un stockage objet ou des dossiers locaux ignorés par Git.

## Répertoires volatils
Les chemins suivants sont réservés aux fichiers générés et sont exclus du versionnage (voir `.gitignore` et `ci/forbidden-paths.txt`) :

- `flash_automation/.cache/` – clones Klipper, toolchains et artefacts de build.
- `flash_automation/out/` et sous-répertoires `out/` – binaires intermédiaires.
- `flash_automation/logs/` et `logs/` à la racine – journaux d'exécution.

Ne déplacez pas ces dossiers hors de la liste d'exclusion sans revue préalable.

## Formats interdits
Le garde-fou CI rejette automatiquement :

- Les binaires et images firmware (`*.bin`, `*.elf`, `*.hex`).
- Les journaux et caches ajoutés au dépôt.
- Tout fichier dépassant la taille configurée via `ci/check_repo_artifacts.py --threshold-mb` (valeur par défaut : 50 Mo).

Avant d'ouvrir une Pull Request, exécutez :

```bash
python3 ci/check_repo_artifacts.py --forbidden-config ci/forbidden-paths.txt
```

## Publication de livrables
- Archivez les versions historiques dans `archive/` ou via les Releases GitHub.
- Les paquets "tout-en-un" ne sont plus générés automatiquement ; documentez les étapes pour reconstruire le firmware depuis `flash_automation/`.
- Pour partager un firmware spécifique, publiez-le dans un stockage externe et mentionnez le SHA-256 calculé avec `sha256sum`.

## Bonnes pratiques pour les journaux
- Conservez les logs détaillés dans `logs/` ou `flash_automation/logs/` (répertoires ignorés par Git).
- Ajoutez les extraits pertinents aux revues en copiant/collant le texte ou en déposant un fichier compressé dans une issue, pas dans le dépôt principal.
