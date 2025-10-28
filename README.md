# Guide simplifié : Flasher un BMCU-C avec Klipper

<p align="center">
  <img src="assets/bmcu_logo.svg" alt="Logo BMCU-C to Klipper" width="220" />
</p>

Ce dépôt rassemble **tout le nécessaire pour transformer un BMCU-C en module Klipper** et, si vous le souhaitez, installer ensuite l'addon Happy Hare. Ce guide a été réécrit pour un public **débutant, pressé et prudent** : chaque commande est prête à copier-coller, des vérifications automatiques sont prévues, et des solutions de secours sont listées si quelque chose coince.

> 🛟 **En cas de doute** : exécutez exactement ce qui est indiqué et ne sautez pas les étapes de vérification. Elles ont été ajoutées pour éviter les mauvaises surprises.

---

## 🗺️ Vue d'ensemble

1. [Ce qu'il vous faut](#-ce-quil-vous-faut)
2. [Procédure guidée (automation_cli.py)](#-procédure-guidée-automation_clipy)
3. [Mode turbo (tout-en-un)](#-mode-turbo-tout-en-un)
4. [Étapes détaillées et sécurisées](#-étapes-détaillées-et-sécurisées)
5. [Et après le flash ?](#-et-après-le-flash-)
6. [Dépanner sans paniquer](#-dépanner-sans-paniquer)
7. [Aller plus loin (optionnel)](#-aller-plus-loin-optionnel)
8. [Contribuer & licence](#-contribuer--licence)

---

## 📦 Ce qu'il vous faut

### Matériel minimum

- Un BMCU-C (avec son câble USB-C ↔ USB-A ou adaptateur équivalent).
- Un PC ou un SBC sous Linux (Ubuntu 22.04+, Debian 12+, Raspberry Pi OS 64 bits, Armbian…) avec accès administrateur.
- Idéalement un port USB natif et un câble en bon état. Évitez les hubs passifs pendant le flash.

### Logiciels et paquets système

Copiez-collez le bloc qui correspond à votre machine. Il installe Python 3, `git`, la toolchain RISC-V et les utilitaires nécessaires.

#### Ubuntu / Debian x86_64

```bash
sudo apt update
sudo apt install -y \
  git python3 python3-venv python3-pip make curl tar \
  gcc-riscv32-unknown-elf picolibc-riscv32-unknown-elf \
  cargo cargo-web screen
```

#### Raspberry Pi OS 64 bits / Armbian (ARM64)

```bash
sudo apt update
sudo apt install -y \
  git python3 python3-venv python3-pip make curl tar build-essential \
  gcc-riscv-none-elf picolibc-riscv-none-elf cargo cargo-web screen

# La toolchain ARM se nomme parfois "riscv-none-elf". Exportez CROSS_PREFIX :
cat <<'ENV' | sudo tee /etc/profile.d/riscv-toolchain.sh
export PATH="/usr/bin:$PATH"
export CROSS_PREFIX="riscv-none-elf-"
ENV
source /etc/profile.d/riscv-toolchain.sh
```

> ✅ Vérifiez que `python3`, `git`, `riscv32-unknown-elf-gcc` (ou `riscv-none-elf-gcc`) et `screen` répondent avec `command -v <outil>`.

### Dépendances Python communes

Le flash repose sur `pyserial` et `wchisp`. Installez-les dans l'environnement virtuel (recommandé) ou pour l'utilisateur courant :

```bash
python3 -m pip install --upgrade pip
python3 -m pip install --user wchisp
```

> ℹ️ Après une installation `--user`, ajoutez `~/.local/bin` au `PATH` :
> `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`

---

## 🤖 Procédure guidée (automation_cli.py)

Le script [`automation_cli.py`](flash_automation/automation_cli.py) propose un menu interactif inspiré de KIAUH qui **enchaîne pour vous les étapes fastidieuses** (permissions, installation, compilation, flash local ou distant). Chaque action est journalisée dans `logs/automation_cli.log`, ce qui facilite le support en cas d'imprévu.

### Installation express

```bash
git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
cd BMCU_C-to-Klipper/flash_automation
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install wchisp
python3 automation_cli.py
```

Dans le menu, suivez la séquence recommandée :

1. `1` – **Vérifier les permissions** : rend `build.sh` et `flash_automation.sh` exécutables.
2. `2` – **Installer les dépendances Python** : s'assure que `pyserial` est prêt (vous avez déjà installé `wchisp` dans l'étape précédente).
3. `3` – **Compiler le firmware** : lance `./build.sh` et enregistre la sortie.
4. **Avant l'étape 4**, quittez temporairement le menu (option `X`) ou ouvrez un second terminal **dans le même dossier** pour exécuter :

   ```bash
   python3 -m compileall flash.py
   ```

   Cette vérification compile `flash.py` sans toucher au matériel et sécurise la suite.
5. Relancez `python3 automation_cli.py` si besoin, puis `4` – **Flash interactif (flash.py)** : suivez l'assistant étape par étape.

> 🧾 Besoin d'automatiser encore plus ? Utilisez le mode direct sans menu :
>
> ```bash
> python3 automation_cli.py --action 1
> python3 automation_cli.py --action 2
> python3 automation_cli.py --action 3
> python3 -m compileall flash.py
> python3 automation_cli.py --action 4
> ```
>
> Ajoutez `--dry-run` à n'importe quelle commande pour vérifier ce qui serait exécuté.

---

## ⚡ Mode turbo (tout-en-un)

Ce bloc prépare un environnement propre, compile Klipper, vérifie `flash.py` et lance l'assistant de flash. À utiliser sur une machine fraîchement configurée.

```bash
git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
cd BMCU_C-to-Klipper/flash_automation
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install wchisp
./build.sh
python3 -m compileall flash.py
python3 flash.py
```

> 🧹 `python3 -m compileall flash.py` crée `__pycache__/flash.cpython-*.pyc`. Ce fichier est normal : il confirme que Python comprend le script avant de toucher au matériel.
> 🔁 À chaque nouvelle session terminal, pensez à relancer `source .venv/bin/activate` avant d'utiliser `flash.py`.

---

## 🧭 Étapes détaillées et sécurisées

### 1. Cloner le dépôt (version complète ou minimale)

- **Tout le projet** :

  ```bash
  git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
  cd BMCU_C-to-Klipper
  ```

- **Seulement les scripts de flash** (téléchargement réduit) :

  ```bash
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/GaspardD78/BMCU_C-to-Klipper.git bmcu-flash
  cd bmcu-flash
  git sparse-checkout set flash_automation
  cd flash_automation
  ```

### 2. Préparer un environnement isolé

```bash
cd flash_automation
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install wchisp
```

- La virtualenv évite d'installer des paquets système par erreur.
- `wchisp` est l'outil officiel de flash pour le microcontrôleur CH32V203.

### 3. Compiler Klipper pour le BMCU-C

```bash
./build.sh | tee logs/build_$(date +%Y%m%d-%H%M%S).log
```

- Le firmware apparaît dans `.cache/klipper/out/klipper.bin`.
- Conservez le résumé `sha256sum .cache/klipper/out/klipper.bin` pour noter la version flashée.

### 4. Valider le script de flash en avance

```bash
python3 -m compileall flash.py
```

- Si la commande réussit, un dossier `__pycache__` est créé et aucun message d'erreur n'apparaît.
- Si une erreur de syntaxe est détectée, **rien n'est flashé** : corrigez (ou reclonez le dépôt) avant de continuer.

### 5. Lancer le flash en mode guidé

```bash
python3 flash.py
```

L'assistant vous demandera :

1. Le port série (généralement `/dev/ttyACM0`).
2. Une confirmation avant de modifier quoi que ce soit.
3. Le suivi en direct des étapes (effacement, écriture, vérification).

> 💡 Connectez le BMCU-C directement au PC, sans rallonge douteuse. Pas de mise en veille pendant le flash.

### 6. Contrôles de fin de procédure

- Vérifiez le message `Flash complete` dans le terminal.
- Débranchez/rebranchez le BMCU-C si le port série n'apparaît plus.
- Ouvrez une session série pour vérifier l'activité : `screen /dev/ttyACM0 115200` (Ctrl+A puis `k` pour quitter proprement).

---

## ✅ Et après le flash ?

Vous pouvez directement intégrer le module côté Happy Hare :

1. Copiez `addon/bmcu.py` dans `klippy/extras/`.
2. Copiez les fichiers de `addon/config/` dans votre dossier de configuration Klipper.
3. Ajoutez la section suivante à `printer.cfg` :

   ```ini
   [bmcu]
   serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
   baud: 1250000
   ```

4. Redémarrez Klipper (`sudo systemctl restart klipper`) et vérifiez `/tmp/klippy.log`.

La documentation complète d'intégration est disponible dans [`addon/docs/setup.md`](addon/docs/setup.md).

---

## 🆘 Dépanner sans paniquer

| Problème | Solution rapide |
| --- | --- |
| `python3` ou `git` introuvable | Reprenez la section [Logiciels et paquets système](#-ce-quil-vous-faut). |
| `Permission denied` sur le port série | `sudo usermod -aG dialout "$USER"` puis reconnectez-vous ou utilisez `newgrp dialout`. |
| `riscv32-unknown-elf-gcc: command not found` | Installez la toolchain (voir ci-dessus) ou exportez `CROSS_PREFIX` vers votre installation. |
| `python3 -m compileall flash.py` renvoie une erreur | Le fichier est corrompu : supprimez et reclonez `flash.py`, ou comparez avec la version du dépôt. Aucun flash n'a eu lieu tant que cette étape échoue. |
| Le flash échoue au milieu | Consultez `logs/` et appliquez la [procédure de retour arrière](flash_automation/docs/rollback_procedure.md) avant de recommencer. |
| Le port série disparaît après flash | Débranchez/branchez le câble, testez un autre port, vérifiez l'alimentation et relancez `screen`. |

> 📚 Détails supplémentaires :
> - [Procédure complète de flash](flash_automation/docs/flash_procedure.md)
> - [Retour à l'état initial](flash_automation/docs/rollback_procedure.md)

---

## 🧰 Aller plus loin (optionnel)

- `flash_automation.sh` : version scriptée (non interactive) pour exécuter le flash en une commande.
- `flashBMCUtoKlipper_automation.py` : exécutions distantes ou en atelier (avec options `--dry-run`, `--backup-command`, etc.).
- `automation_cli.py` : menu interactif façon KIAUH qui regroupe build, flash et journalisation.
- Toolchains personnalisées : exportez `KLIPPER_SRC_DIR` ou `KLIPPER_FIRMWARE_PATH` pour réutiliser des artefacts existants.

Tous ces outils se trouvent dans le dossier [`flash_automation/`](flash_automation) et respectent les conventions décrites dans [AGENTS.md](AGENTS.md).

---

## 🤝 Contribuer & licence

- Suivez la convention [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/).
- Documentez tout changement qui touche à la sécurité ou à l'automatisation.
- Lisez [AGENTS.md](AGENTS.md) avant toute modification importante.

Le projet est distribué sous licence **GPLv3** – voir [LICENSE](LICENSE).

---

Bon flash ! Prenez votre temps, suivez les étapes, et le BMCU-C sera opérationnel en quelques minutes.
