# Intégration BMCU-C ↔️ Klipper

<p align="center">
  <img src="assets/bmcu_logo.svg" alt="Logo BMCU-C to Klipper" width="200" />
</p>

Ce dépôt regroupe tout ce qu’il faut pour **flasher un BMCU-C avec Klipper** et **intégrer le module dans Happy Hare**. Il est scindé en deux sous-projets indépendants :

- [`flash_automation/`](./flash_automation) — scripts Bash & Python pour compiler Klipper, flasher le BMCU-C et automatiser la procédure (atelier, CI, production).
- [`addon/`](./addon) — module Klipper et configuration Happy Hare exploitant un BMCU-C déjà flashé.

Chaque dossier peut être versionné séparément ; la documentation et les scripts nécessaires sont fournis localement.

## Table des matières

1. [Pré-requis matériels & logiciels](#pré-requis-matériels--logiciels)
2. [Flash du BMCU-C (`flash_automation/`)](#flash-du-bmcu-c-flash_automation)
3. [Accès distant & automatisation](#accès-distant--automatisation)
4. [Addon Happy Hare (`addon/`)](#addon-happy-hare-addon)
5. [Exporter les sous-projets](#exporter-les-sous-projets)

---

## Pré-requis matériels & logiciels

### Matériel minimal

- BMCU-C avec câble USB-C ↔ USB-A (ou adaptateur équivalent).
- Poste Linux (Ubuntu 22.04+, Raspberry Pi OS 64 bits, Armbian BTT CB2) avec accès au groupe `dialout`.
- Optionnel : hub USB alimenté pour sécuriser l’alimentation pendant le flash.

> ⚠️ **Astuce fiabilité :** privilégiez un port USB natif et vérifiez visuellement le câble avant de lancer un flash.

### Paquets système à installer

| Plateforme | Commandes recommandées |
| --- | --- |
| x86_64 (Ubuntu/Debian 22.04+) | ```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip make \
    curl tar gcc-riscv32-unknown-elf picolibc-riscv32-unknown-elf
``` |
| Raspberry Pi OS 64 bits / Armbian | ```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip make \
    curl tar build-essential coreutils iputils-ping openssh-client \
    ipmitool sshpass
``` |

Complétez avec les dépendances Python communes :

```bash
python3 -m pip install --upgrade pip
python3 -m pip install --user wchisp
```

> ℹ️ Ajoutez `~/.local/bin` au `PATH` après une installation `pip --user` : `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc`.

### Outils utilisés par `flash_automation`

| Composant | Utilité | Installation (Debian/Ubuntu/Raspberry Pi OS) |
| --- | --- | --- |
| `git`, `curl`, `tar`, `make`, `python3`, `python3-venv`, `python3-pip` | Préparer l’environnement de build | `sudo apt install -y git curl tar build-essential python3 python3-venv python3-pip` |
| `gcc-riscv32-unknown-elf`, `picolibc-riscv32-unknown-elf` | Toolchain native x86_64 | `sudo apt install -y gcc-riscv32-unknown-elf picolibc-riscv32-unknown-elf` |
| `wchisp` | Flash du CH32V203 | `python3 -m pip install --user wchisp` |
| `ipmitool`, `sshpass`, `scp`, `ping` | Automatisation distante | `sudo apt install -y ipmitool sshpass openssh-client iputils-ping` |

> ✅ Vérifiez la présence de chaque binaire avec `command -v <outil>` avant d’exécuter les scripts.

### Toolchain RISC-V sur ARM

Sur architecture ARM64, `build.sh` ne télécharge pas de toolchain. Choisissez l’une des options suivantes et exportez `CROSS_PREFIX` :

1. **Paquets Debian (si disponibles)**

   ```bash
   sudo apt install -y gcc-riscv32-unknown-elf picolibc-riscv32-unknown-elf
   export CROSS_PREFIX="riscv32-unknown-elf-"
   ```

   > 💡 Selon la distribution, les paquets peuvent s’appeler `gcc-riscv-none-elf`.

2. **Archive xPack multi-architecture (recommandé)**

   ```bash
   cd /tmp
   curl -LO https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v15.2.0-1/xpack-riscv-none-elf-gcc-15.2.0-1-linux-arm64.tar.gz
   sudo mkdir -p /opt/riscv/xpack-15.2.0-1
   sudo tar -xzf xpack-riscv-none-elf-gcc-15.2.0-1-linux-arm64.tar.gz -C /opt/riscv/xpack-15.2.0-1 --strip-components=1
   echo 'export PATH=/opt/riscv/xpack-15.2.0-1/bin:$PATH' | sudo tee /etc/profile.d/xpack-riscv.sh
   echo 'export CROSS_PREFIX=/opt/riscv/xpack-15.2.0-1/bin/riscv-none-elf-' | sudo tee -a /etc/profile.d/xpack-riscv.sh
   source /etc/profile.d/xpack-riscv.sh
   ```

   > ✅ Vérifiez l’installation avec `/opt/riscv/xpack-15.2.0-1/bin/riscv-none-elf-gcc --version`.

### Cloner le dépôt

- **Dépôt complet**

  ```bash
  git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
  cd BMCU_C-to-Klipper
  ```

- **Clone minimal (`flash_automation/` uniquement)**

  ```bash
  git clone --depth 1 --filter=blob:none --sparse \
      https://github.com/GaspardD78/BMCU_C-to-Klipper.git bmcu-flash
  cd bmcu-flash
  git sparse-checkout set flash_automation
  ```

> 📦 Cette seconde option limite le téléchargement aux scripts de flash.

> ⚠️ **Conseil Git :** en session SSH, chargez votre clé (`ssh-add ~/.ssh/id_ed25519`) avant `git clone` pour éviter une erreur d’authentification.

---

## Flash du BMCU-C (`flash_automation/`)

```text
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

### 1. Préparer l’environnement

```bash
cd flash_automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # installe pyserial & dépendances
```

> ⚠️ Activez la virtualenv (`source .venv/bin/activate`) à chaque session pour éviter d’installer des dépendances au mauvais endroit.

### 2. Compiler Klipper pour le BMCU-C

```bash
./build.sh
```

Le firmware généré est disponible dans `.cache/klipper/out/klipper.bin`.

> ⚠️ Conservez la sortie de build (`./build.sh | tee build.log`) et notez `sha256sum .cache/klipper/out/klipper.bin` pour tracer la version flashée.

### 3. Flasher le microcontrôleur (mode guidé recommandé)

```bash
python3 flash.py
```

1. Sélectionnez le port série (ex. `/dev/ttyACM0`).
2. Vérifiez le résumé affiché.
3. Confirmez avec `y` pour lancer le flash.
4. Attendez le message « Flash complete ».

> ⚠️ Renseignez une commande de sauvegarde dans l’assistant (`flashBMCUtoKlipper_automation.py --backup-command "sudo /opt/bin/backup_bmcu.sh"`) afin de capturer l’état courant avant écriture.
> ⚠️ Surveillez l’alimentation : pas de mise en veille ni de hub passif pendant l’opération.

Alternative CLI : `./flash_automation.sh --help` décrit le mode non interactif.

### 4. Vérifier & dépanner

- Vérifiez l’émission de trames : `screen /dev/ttyACM0 115200`.
- Corrigez les permissions série si besoin :

  ```bash
  sudo usermod -aG dialout "$USER"
  newgrp dialout
  ```

- Consultez la procédure détaillée : [`flash_automation/docs/flash_procedure.md`](./flash_automation/docs/flash_procedure.md).

> 🆘 En cas d’échec, appliquez la [procédure de retour à l’état initial](flash_automation/docs/rollback_procedure.md) avant une nouvelle tentative.

---

## Accès distant & automatisation

1. **Installer SSH sur l’hôte distant**

   ```bash
   sudo apt install -y openssh-server
   sudo systemctl enable --now ssh
   ```

   > ⚠️ Désactivez l’authentification par mot de passe (`PasswordAuthentication no`) et appliquez `chmod 600 ~/.ssh/authorized_keys`.

2. **Provisionner les clés**

   ```bash
   ssh-keygen -t ed25519 -C "bmcu-maintenance"
   ssh-copy-id utilisateur@hote-distant
   ```

   > ⚠️ Stockez les clés temporaires sur un volume chiffré puis détruisez-les (`shred`).

3. **Ouvrir un tunnel série**

   ```bash
   ssh -NL 3333:/dev/ttyACM0 utilisateur@hote-distant
   ```

   - `-N` évite l’ouverture d’un shell, `-L` exporte le port série localement.
   - Si nécessaire, utilisez `socat TCP-LISTEN:3333,reuseaddr,fork FILE:/dev/ttyACM0,raw,echo=0` côté distant.

   > ⚠️ Arrêtez les services verrouillant `/dev/ttyACM0` (`sudo systemctl stop klipper`) avant d’ouvrir le tunnel.

4. **Lancer build & flash à distance**

   ```bash
   ssh utilisateur@hote-distant "cd /opt/BMCU_C-to-Klipper/flash_automation && ./build.sh | tee -a /var/log/bmcu_flash/build.log"
   ssh -t utilisateur@hote-distant "cd /opt/BMCU_C-to-Klipper/flash_automation && python3 flash.py"
   ```

   Pour un run totalement automatisé :

   ```bash
   ssh utilisateur@hote-distant "cd /opt/BMCU_C-to-Klipper/flash_automation && python3 flashBMCUtoKlipper_automation.py \
       --bmc-host 192.168.10.50 \
       --bmc-user root \
       --bmc-password '***' \
       --firmware-file .cache/klipper/out/klipper.bin \
       --remote-firmware-path /tmp/klipper.bin \
       --flash-command 'socflash -s {firmware}' \
       --backup-command '/opt/bin/backup_bmcu.sh' \
       --dry-run"
   ```

   > ⚠️ Archivez les journaux dans `/var/log/bmcu_flash/` avec un horodatage ISO8601.

5. **Nettoyer la session**

   - `exit` pour fermer la connexion SSH.
   - `lsof /dev/ttyACM0` pour vérifier que le port série est libéré.

   > ⚠️ Supprimez les clés temporaires et redémarrez les services (`sudo systemctl start klipper`) une fois l’opération validée.

---

## Addon Happy Hare (`addon/`)

```text
┌────────────────────────────────────────────────────────────┐
│ Checklist d’intégration Happy Hare                         │
├─────────────────────┬───────────────────────────────────────┤
│ Module chargé       │ `bmcu.py` détecté par Klipper         │
├─────────────────────┼───────────────────────────────────────┤
│ Menus interface     │ Sections BMCU visibles dans Happy Hare│
├─────────────────────┼───────────────────────────────────────┤
│ Journal Klipper     │ Pas d’erreur « MCU 'bmcu' shutdown »  │
├─────────────────────┼───────────────────────────────────────┤
│ Version firmware    │ Cohérente avec la build flashée       │
└─────────────────────┴───────────────────────────────────────┘
```

1. **Copier le module**

   ```bash
   cd addon
   cp bmcu.py <chemin_klipper>/klippy/extras/
   ```

2. **Installer les configurations Happy Hare**

   ```bash
   cp -r config/* <chemin_klipper>/config/
   ```

3. **Déclarer le module dans `printer.cfg`**

   ```ini
   [bmcu]
   serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
   baud: 1250000
   ```

4. **Redémarrer et valider**

   - `sudo systemctl restart klipper`
   - Consulter `/tmp/klippy.log`
   - Vérifier les menus BMCU dans Happy Hare

> Toute la procédure détaillée est documentée dans [`addon/docs/setup.md`](./addon/docs/setup.md).

> ⚠️ Surveillez les erreurs `MCU 'bmcu' shutdown` dans `/tmp/klippy.log` et confirmez que la version firmware affichée correspond au binaire fraîchement flashé.

---

## Exporter les sous-projets

Chaque sous-dossier peut devenir un dépôt autonome :

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
