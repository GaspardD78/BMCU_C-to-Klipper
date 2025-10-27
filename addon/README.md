# Addon Klipper pour BMCU-C

Ce dossier correspond au dépôt dédié à l'intégration logicielle du BMCU-C dans
Klipper/Happy Hare. Il fournit le module Python et les fichiers de
configuration nécessaires pour piloter un chargeur multi-bobines basé sur un
BMCU-C déjà flashé.

## 🚀 Installation rapide

```bash
cd addon
cp bmcu.py <chemin_klipper>/klippy/extras/
cp -r config/* <chemin_klipper>/config/
```

> ℹ️ Adaptez `<chemin_klipper>` au chemin d'installation de Klipper sur votre
> machine (ex. `/home/pi/klipper`).

## 🔧 Configuration

- Les profils prêts à l'emploi sont regroupés dans `config/`.
- Le fichier principal `bmcu.py` expose les commandes nécessaires
  (`BMCU_SELECT_GATE`, `BMCU_STATUS`, …).
- Des instructions détaillées et des exemples de macros sont disponibles dans
  [`docs/setup.md`](./docs/setup.md).

## ✅ Tests de base

1. Redémarrez Klipper après avoir copié le module.
2. Exécutez `BMCU_STATUS` dans la console Klipper pour vérifier la communication.
3. Lancer une sélection de plateau : `BMCU_SELECT_GATE GATE=1`.

## 📄 Licence

GPLv3 – identique au fichier `LICENSE` à la racine du projet.
