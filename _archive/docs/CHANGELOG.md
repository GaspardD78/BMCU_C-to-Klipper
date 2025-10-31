# Changelog

## 2025-10-27

### Suppressions
- Les archives "tout-en-un" de la version 1.0.0 ont été retirées de la racine du dépôt et déplacées dans `archive/release/`. Elles restent accessibles uniquement pour référence historique.

### Impacts
- Les scripts internes ou pipelines qui consommaient les artefacts depuis `./release/` doivent désormais cibler `./archive/release/` ou récupérer les fichiers depuis l'onglet "Releases" de GitHub.
- Les livrables actuels doivent être régénérés via les scripts `flash_automation/` ; aucune nouvelle mise à jour ne sera publiée dans l'ancien format zip.
