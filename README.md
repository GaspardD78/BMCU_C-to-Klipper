# Intégration BMCU-C ↔️ Klipper

<p align="center">
  <img src="assets/bmcu_logo.svg" alt="Logo BMCU-C to Klipper" width="200" />
</p>

Ce dépôt a été allégé et réorganisé en **deux projets autonomes** :

- [`flash_automation/`](./flash_automation) – scripts bash & Python pour compiler Klipper, flasher le BMCU-C et automatiser la procédure (CI, atelier, production en série).
- [`addon/`](./addon) – module Klipper + fichiers de configuration Happy Hare pour exploiter un BMCU-C déjà flashé.

Chaque dossier peut vivre comme un dépôt Git indépendant : il contient sa documentation, ses scripts et n'a pas de dépendance croisée.

---

## ⚡️ Flash du BMCU-C (dépôt `flash_automation/`)

```bash
cd flash_automation
./build.sh                # compile Klipper dans .cache/klipper/
python3 flash.py          # assistant interactif (mode guidé)
# ou
./flash_automation.sh     # flash minimaliste au clavier
```

Points clés :

- Le script `build.sh` télécharge automatiquement la toolchain RISC-V **et** clone Klipper dans `flash_automation/.cache/klipper`. Aucun sous-module n'est requis.
- Les correctifs locaux sont appliqués depuis `klipper_overrides/` avant la compilation.
- `flash.py` et `flashBMCUtoKlipper_automation.py` partagent la même logique (mode interactif vs orchestration distante).
- Une procédure détaillée est disponible dans [`flash_automation/docs/flash_procedure.md`](./flash_automation/docs/flash_procedure.md).

---

## 🐍 Addon Happy Hare (dépôt `addon/`)

```bash
cd addon
cp bmcu.py <chemin_klipper>/klippy/extras/
cp -r config/* <chemin_klipper>/config/
```

- Le module expose les commandes nécessaires pour piloter le BMCU-C depuis Happy Hare.
- Les profils de configuration sont regroupés dans `addon/config/`.
- Le guide d'intégration est disponible dans [`addon/docs/setup.md`](./addon/docs/setup.md).

---

## 📦 Publier deux dépôts distincts

Chaque sous-répertoire peut être exporté vers son dépôt cible :

```bash
# Exemple : extraire flash_automation dans un nouveau dépôt
cd flash_automation
git init
git add .
git commit -m "feat: initial import"
```

Les historiques pourront ensuite être fusionnés via `git subtree split` ou `git filter-repo` si nécessaire.

---

## 🤝 Contribuer

- Respecter la convention [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/) (`feat`, `fix`, `docs`, ...).
- Documenter tout changement impactant la sécurité ou l'automatisation.
- Les instructions générales sont regroupées dans [AGENTS.md](./AGENTS.md).

---

## 📄 Licence

Ce projet est distribué sous licence **GPLv3** – voir [LICENSE](./LICENSE).
