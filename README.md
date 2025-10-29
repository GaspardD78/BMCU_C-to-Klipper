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

#### Alternative : installer Cargo via rustup

Si votre distribution ne fournit pas un paquet `cargo` récent ou si vous préférez gérer Rust depuis votre `$HOME`, vous pouvez utiliser [rustup](https://rustup.rs). Après l'installation, assurez-vous que les scripts du dépôt détectent bien les binaires attendus.

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --profile minimal
source "$HOME/.cargo/env"
rustup target add wasm32-unknown-unknown
cargo install cargo-web
command -v cargo
command -v cargo-web
command -v riscv-none-elf-gcc  # fournie par les paquets système, gardez-la installée
```

> 🧭 Si `command -v` ne trouve pas `cargo` ou `cargo-web`, ajoutez `~/.cargo/bin` à votre `PATH` **avant** de lancer `./build.sh` ou `python3 flash.py` : `echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`.
> 🛠️ Les optimisations comme `--no-install-recommends` ou l'installation rustup en profil minimal ne posent pas de problème tant que `cargo-web` est réinstallé et que la toolchain RISC-V ARM (`riscv-none-elf-*`) reste accessible.

### Dépendances Python communes

Le flash repose sur `pyserial` et `wchisp`. Installez-les dans l'environnement virtuel (recommandé) ou pour l'utilisateur courant :

```bash
python3 -m pip install --upgrade pip
pip install -r requirements.txt
python3 install_wchisp.py
```

> ⚠️ `wchisp` n'est pas distribué via PyPI : `install_wchisp.py` télécharge le binaire
> officiel correspondant à votre architecture et l'ajoute à votre environnement.
> ℹ️ Après une installation `--user`, ajoutez `~/.local/bin` au `PATH` :
> `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`

---

## 🤖 Procédure guidée (automation_cli.py)

Le script [`automation_cli.py`](flash_automation/automation_cli.py) propose un menu interactif inspiré de KIAUH qui **enchaîne pour vous les étapes fastidieuses** (permissions, installation, compilation, flash local ou distant). Chaque action est journalisée dans `~/BMCU_C_to_Klipper_logs/automation-<horodatage>.log` (chemin personnalisable via `BMCU_LOG_ROOT`), ce qui facilite le support en cas d'imprévu.

### Installation express

```bash
git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
cd BMCU_C-to-Klipper/flash_automation
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
python3 install_wchisp.py
python3 automation_cli.py
```

> ⚠️ L'outil `wchisp` n'étant pas packagé sur PyPI, ce script s'assure qu'il est
> installé depuis les releases officielles.

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

> ✋ **Nouvelle ergonomie :** Un appui sur `Ctrl+C` pendant que le menu attend
> une entrée n'interrompt plus l'application. Le gestionnaire affiche
> `Menu principal réarmé ; choisissez une option.` puis redessine les choix.
> Les actions déclenchées continuent d'accepter `Ctrl+C` pour revenir au menu
> principal après nettoyage.

> 📊 **Suivi de progression :** Les logs `~/BMCU_C_to_Klipper_logs/automation-*.log` contiennent
> désormais des lignes `[progress]` indiquant l'étape en cours (ex.
> `receiving objects`, `compilation [#####.....] 45%`). Consultez-les pour
> vérifier rapidement qu'une action longue ne s'est pas figée.

> 🧪 Un protocole de validation manuel et ses retours d'expérience sont
> disponibles dans [`docs/manual-test-protocol.md`](docs/manual-test-protocol.md)
> et `docs/test-logs/`. Inspirez-vous-en pour vos propres vérifications.

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
python3 install_wchisp.py
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
python3 install_wchisp.py
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

### `flash_automation.sh` : l'outil tout-en-un

Le script [`flash_automation.sh`](flash_automation/flash_automation.sh) est l'outil le plus puissant de ce dépôt. Il combine la compilation, la détection des périphériques et le flashage en une seule commande, avec des options avancées pour l'automatisation.

#### Fonctionnalités clés

- **`--bootstrap`** : Lance le script `./build.sh` pour compiler le firmware Klipper avant toute autre action. Idéal pour un démarrage de zéro.
- **`--auto-confirm`** : Active le mode non interactif. Le script sélectionne automatiquement le firmware le plus récent et le premier périphérique compatible trouvé. Parfait pour les scripts ou si vous êtes sûr de votre configuration.
- **`--dry-run`** : Simule toutes les étapes (compilation, sélection, flash) sans modifier le matériel. Utilisez-le pour vérifier votre configuration en toute sécurité.
- **Rapport final détaillé** : À la fin de chaque exécution, un résumé complet s'affiche, incluant le chemin du firmware, sa taille, son checksum SHA256, la méthode de flash utilisée et la durée totale.

#### Exemples d'utilisation

- **Flash interactif classique :**
  ```bash
  cd flash_automation/
  ./flash_automation.sh
  ```

- **Compiler et flasher en une seule commande (interactif) :**
  ```bash
  cd flash_automation/
  ./flash_automation.sh --bootstrap
  ```

- **Automatiser complètement le flashage (non interactif) :**
  ```bash
  cd flash_automation/
  # Le script compile, choisit le firmware récent et le premier port série
  ./flash_automation.sh --bootstrap --auto-confirm
  ```

- **Vérifier la configuration sans risque :**
  ```bash
  cd flash_automation/
  ./flash_automation.sh --bootstrap --dry-run
  ```
  *(Le rapport final indiquera `Mode: Simulation (dry-run)`)*.

#### Dépendances par méthode de flash

Le script choisit la meilleure méthode de flash en fonction des outils et périphériques détectés. Voici les dépendances pour chaque scénario :

| Scénario | Dépendances clés | Notes |
| --- | --- | --- |
| `wchisp` (auto-install) | `curl`, `tar`, `sha256sum` | Méthode par défaut si un bootloader WCH est détecté. Les outils ne sont requis que si `wchisp` n'est pas déjà installé. |
| `wchisp` (local) | `wchisp` dans le `PATH` | Aucun téléchargement si l'outil est déjà présent. |
| `serial` | `python3`, Klipper compilé | Requis pour `flash_usb.py`. Le script bascule sur cette méthode si un port série est trouvé mais pas de bootloader WCH/DFU. |
| `dfu` | `dfu-util` | Utilisé si un périphérique en mode DFU est détecté. |
| `sdcard` | `cp`, `sync` (outils de base) | Copie directe du firmware. Souvent une méthode de dernier recours. |

> Astuce : laissez `--method auto` (valeur par défaut) pour bénéficier de la détection guidée. Le script indiquera la raison du choix proposé (ex. "périphérique DFU détecté").

> ℹ️ **Python manquant ?** Si `python3` est indisponible, le script utilise des alternatives en Bash pour certaines tâches et désactive les méthodes qui en dépendent (comme le flash série).

Tous ces outils se trouvent dans le dossier [`flash_automation/`](flash_automation) et respectent les conventions décrites dans [AGENTS.md](AGENTS.md).

---

## 🧪 Tests automatisés

Les tests Python se lancent via `pytest` et les scripts Shell avec `tests/*.sh`. Le scénario
[tests/test_flash_automation_interactive.sh](tests/test_flash_automation_interactive.sh) couvre l'assistant
interactif de `flash_automation.sh`.

### Dépendances système

- [`expect`](https://core.tcl-lang.org/expect/index) (optionnelle mais recommandée) : permet de vérifier le texte des invites.

```bash
sudo apt-get update
sudo apt-get install -y expect
```

Sans `expect`, le test bascule automatiquement sur un pilote interactif Python basé sur `pty` et continue de
vérifier la copie du firmware. Installez `expect` pour bénéficier des assertions complètes sur les invites et
reproduire le comportement de la CI.

---

## 🤝 Contribuer & licence

- Suivez la convention [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/).
- Documentez tout changement qui touche à la sécurité ou à l'automatisation.
- Lisez [AGENTS.md](AGENTS.md) avant toute modification importante.

Le projet est distribué sous licence **GPLv3** – voir [LICENSE](LICENSE).

---

Bon flash ! Prenez votre temps, suivez les étapes, et le BMCU-C sera opérationnel en quelques minutes.
