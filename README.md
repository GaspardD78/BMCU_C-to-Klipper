# Intégration du BMCU-C avec Klipper et Happy Hare

> ⚠️ **Statut : preuve de concept.** L'intégration n'a pas encore été validée sur un BMCU-C réel. Ce dépôt s'adresse aux développeurs et "makers" souhaitant contribuer aux tests matériels et logiciels.

Ce projet open-source fournit deux briques complémentaires pour piloter un BMCU-C (clone communautaire de l'AMS Bambu Lab) depuis Klipper via Happy Hare :

1. **(1) Flashage du BMCU-C** — scripts et configurations pour compiler puis charger Klipper sur le microcontrôleur.
2. **(2) Addon Python pour Klipper** — module, macros et documentation permettant à Happy Hare de dialoguer avec le BMCU-C.

Les deux volets peuvent être utilisés ensemble ou séparément selon votre besoin (par exemple : vous pouvez ne déployer que l'addon Python si vous disposez déjà d'un BMCU-C flashé avec Klipper).

---

## 1. Flashage du BMCU-C (firmware)

Tout le nécessaire pour compiler et flasher le firmware Klipper se trouve dans le répertoire `firmware/`.

### Étapes rapides

1. **Compiler le firmware**
   ```bash
   ./firmware/build.sh
   ```
2. **Flasher le microcontrôleur** (assistant interactif recommandé)
   ```bash
   ./firmware/flash.py
   ```
   - Pour l'automatisation : `./firmware/flashBMCUtoKlipper_automation.py`
   - Pour un flash manuel bas niveau : `./firmware/flash.sh`

### Documentation dédiée

- 📄 [Procédure de flash du BMCU-C](./docs/flash_procedure.md)
- ✅ Vérifiez les prérequis matériels et logiciels listés dans [AGENTS.md](./AGENTS.md) avant toute manipulation.

---

## 2. Addon Python pour Klipper (Happy Hare)

Le dossier `bmcu_addon/` regroupe le code et la configuration pour intégrer le BMCU-C à Happy Hare.

### Contenu principal

- `bmcu_addon/bmcu.py` : module Klipper gérant la communication RS-485 et les commandes G-code (`BMCU_SELECT_GATE`, `BMCU_HOME`, etc.).
- `bmcu_addon/config/` : macros et paramètres à inclure dans votre `printer.cfg`.
- `docs/setup.md` : guide pas-à-pas pour installer et activer l'addon.

### Mise en place

1. Copier `bmcu_addon/bmcu.py` vers `klippy/extras/` dans votre instance Klipper.
2. Importer les fichiers de `bmcu_addon/config/` dans votre configuration Happy Hare.
3. Suivre les indications détaillées du [guide d'installation](./docs/setup.md) pour finaliser l'intégration.

---

## Structure du dépôt

- `bmcu_addon/` : addon Klipper pour Happy Hare.
- `docs/` : documentation additionnelle (installation, flash, dépannage, etc.).
- `firmware/` : scripts de compilation et de flash du firmware Klipper.
- `klipper/` : sous-module Git contenant les sources du firmware Klipper (ne pas modifier directement sans synchronisation amont).

---

## Contribuer

Les contributions sont les bienvenues ! Ouvrez une issue ou soumettez une pull request pour proposer des améliorations. Consultez [AGENTS.md](./AGENTS.md) pour connaître les conventions de contribution.

## Licence

Ce projet n'a pas encore de licence définie. Veuillez en ajouter une avant toute redistribution ou dérivation.
