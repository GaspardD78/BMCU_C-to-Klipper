# Intégration BMCU-C ↔️ Klipper

<p align="center">
  <img src="assets/bmcu_logo.svg" alt="Logo BMCU-C to Klipper" width="200" />
</p>

Ce dépôt a été allégé et réorganisé en **deux projets autonomes** :

- [`flash_automation/`](./flash_automation) – scripts bash & Python pour compiler Klipper, flasher le BMCU-C et automatiser la procédure (CI, atelier, production en série).
- [`addon/`](./addon) – module Klipper + fichiers de configuration Happy Hare pour exploiter un BMCU-C déjà flashé.

Chaque dossier peut vivre comme un dépôt Git indépendant : il contient sa documentation, ses scripts et n'a pas de dépendance croisée.

---

## ⚙️ Pré-requis matériels & logiciels

1. **Matériel**
   - Un BMCU-C avec câble USB-C vers USB-A.
   - Un ordinateur sous Linux (Ubuntu 22.04+ testé) avec accès au port série (`dialout`).
   - Optionnel : un hub USB alimenté pour éviter les coupures pendant le flash.
2. **Logiciels / paquets système** (copier-coller les commandes ci-dessous) :

   ```bash
   sudo apt update
   sudo apt install -y git python3 python3-venv python3-pip make \
       gcc-riscv32-unknown-elf picolibc-riscv32-unknown-elf
   ```

   > 💡 Si la toolchain RISC-V n'est pas disponible dans votre distribution, installez le paquet `gcc-riscv32-unknown-elf` depuis [xpack-dev-tools](https://xpack.github.io/dev-tools/riscv-none-elf-gcc/) puis ajoutez-le au `PATH`.

3. **Cloner ce dépôt** :

   ```bash
   git clone https://github.com/bambulabs-community/BMCU_C-to-Klipper.git
   cd BMCU_C-to-Klipper
   ```

---

## ⚡️ Flash du BMCU-C (dépôt `flash_automation/`)


```
+------------------------------+--------------------------+
|  Flash Automation Assistant  |  Klipper BMCU-C Utility  |
+------------------------------+--------------------------+
| [1] Build firmware           |   Target: /dev/ttyACM0   |
| [2] Flash firmware           |   Firmware: klipper.bin  |
| [3] Dry-run validation       |                          |
|                              |  [L] View live logs      |
| (Q) Quit                     |  [H] Show help           |
+------------------------------+--------------------------+
```

### Étape 1 – Préparer l'environnement

```bash
cd flash_automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # installe pyserial & dépendances
```

> ℹ️ Le script `build.sh` télécharge la toolchain si elle est absente et clone Klipper dans `flash_automation/.cache/klipper`. Aucune configuration manuelle n'est nécessaire.

### Étape 2 – Compiler Klipper pour le BMCU-C

```bash
./build.sh
```

Attendez la fin de la compilation : le firmware généré (`.cache/klipper/out/klipper.bin`) sera utilisé automatiquement par les scripts de flash.

### Étape 3 – Flasher le microcontrôleur (mode guidé recommandé)

```bash
python3 flash.py
```

1. Choisissez le port série proposé (ex. `/dev/ttyACM0`).
2. Vérifiez le résumé affiché par le script.
3. Confirmez avec `y` pour lancer le flash.
4. Attendez le redémarrage du BMCU-C (log « Flash complete »).

> Alternative : `./flash_automation.sh` offre un mode non interactif (utilisez `--help` pour la liste des options).

### Étape 4 – Vérifications & dépannage

- Confirmez que le BMCU-C émet des trames via `screen /dev/ttyACM0 115200`.
- En cas d'erreur `Permission denied`, ajoutez l'utilisateur courant au groupe `dialout` :

  ```bash
  sudo usermod -aG dialout "$USER"
  newgrp dialout
  ```

- Consultez le guide détaillé : [`flash_automation/docs/flash_procedure.md`](./flash_automation/docs/flash_procedure.md).

---

## 🐍 Addon Happy Hare (dépôt `addon/`)

### Étape 1 – Copier le module dans Klipper

```bash
cd addon
cp bmcu.py <chemin_klipper>/klippy/extras/
```

### Étape 2 – Installer les configurations Happy Hare

```bash
cp -r config/* <chemin_klipper>/config/
```

### Étape 3 – Déclarer le module dans votre `printer.cfg`

```ini
[bmcu]
serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
baud: 1250000
```

### Étape 4 – Redémarrer Klipper et valider

1. Redémarrez le service Klipper (`sudo systemctl restart klipper`).
2. Vérifiez les logs (`/tmp/klippy.log`) pour confirmer la détection du BMCU-C.
3. Depuis l'interface Happy Hare, assurez-vous que les menus BMCU sont présents.

> Tout le guide d'intégration (dépannage, personnalisation des profils) est disponible dans [`addon/docs/setup.md`](./addon/docs/setup.md).

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
