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

```text
┌──────────────────────────────────────────────┐
│ Checklist de préparation                     │
├───────────────────────┬──────────────────────┤
│ Matériel              │ BMCU-C + USB-C ↔ USB-A │
│                       │ Hub USB alimenté (opt.) │
├───────────────────────┼──────────────────────┤
│ Poste de travail      │ Linux 22.04+ avec accès │
│                       │ au groupe dialout       │
├───────────────────────┼──────────────────────┤
│ Toolchain             │ gcc/picolibc RISC-V OK  │
├───────────────────────┼──────────────────────┤
│ Réseau & sauvegarde   │ SSH prêt, script backup │
└───────────────────────┴──────────────────────┘
```

1. **Matériel**
   - Un BMCU-C avec câble USB-C vers USB-A.
   - Un ordinateur sous Linux (Ubuntu 22.04+ testé) avec accès au port série (`dialout`).
   - Optionnel : un hub USB alimenté pour éviter les coupures pendant le flash.
   > ⚠️ **Point de vigilance matériel :** privilégiez un port USB natif (pas de hub passif) et inspectez visuellement le câble pour éviter les micro-coupures durant le flashage.
2. **Logiciels / paquets système** (copier-coller les commandes ci-dessous) :

   ```bash
   sudo apt update
   sudo apt install -y git python3 python3-venv python3-pip make \
       gcc-riscv32-unknown-elf picolibc-riscv32-unknown-elf
   ```

   > ⚠️ **Point de vigilance toolchain :** confirmez la présence de la bonne version avec `riscv32-unknown-elf-gcc --version` et sauvegardez la sortie pour votre rapport d'intervention.

   > 💡 Si la toolchain RISC-V n'est pas disponible dans votre distribution, installez le paquet `gcc-riscv32-unknown-elf` depuis [xpack-dev-tools](https://xpack.github.io/dev-tools/riscv-none-elf-gcc/) puis ajoutez-le au `PATH`.

3. **Cloner ce dépôt** :

   ```bash
   git clone https://github.com/bambulabs-community/BMCU_C-to-Klipper.git
   cd BMCU_C-to-Klipper
   ```

   > ⚠️ **Point de vigilance Git :** si vous exécutez ces commandes via une session SSH (voir section dédiée), chargez votre clé dans l'agent (`ssh-add ~/.ssh/id_ed25519`) avant `git clone` pour éviter un échec d'authentification.

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

> ⚠️ **Point de vigilance environnement :** Activez la virtualenv pour chaque session (`source .venv/bin/activate`). Un oubli peut installer des dépendances au mauvais endroit ou déclencher des conflits de version.

> ℹ️ Le script `build.sh` télécharge la toolchain si elle est absente et clone Klipper dans `flash_automation/.cache/klipper`. Aucune configuration manuelle n'est nécessaire.

### Étape 2 – Compiler Klipper pour le BMCU-C

```bash
./build.sh
```

Attendez la fin de la compilation : le firmware généré (`.cache/klipper/out/klipper.bin`) sera utilisé automatiquement par les scripts de flash.

> ⚠️ **Point de vigilance compilation :** Conservez la sortie du script (`./build.sh | tee build.log`) et calculez `sha256sum .cache/klipper/out/klipper.bin` pour attester de l'intégrité du binaire.

### Étape 3 – Flasher le microcontrôleur (mode guidé recommandé)

```bash
python3 flash.py
```

1. Choisissez le port série proposé (ex. `/dev/ttyACM0`).
2. Vérifiez le résumé affiché par le script.
3. Confirmez avec `y` pour lancer le flash.
4. Attendez le redémarrage du BMCU-C (log « Flash complete »).

> ⚠️ **Point de vigilance sauvegarde :** Dans l'assistant, renseignez la « Commande distante de mise en maintenance » pour lancer un script de sauvegarde (ex. `sudo /opt/bin/backup_bmcu.sh`). Pour une exécution sans interaction, utilisez `flashBMCUtoKlipper_automation.py --backup-command "sudo /opt/bin/backup_bmcu.sh"` afin de capturer l'état avant écriture.
> ⚠️ **Point de vigilance alimentation :** Évitez la mise en veille de la machine et surveillez la tension USB si vous êtes sur batterie ; une coupure peut corrompre le microcontrôleur.

> Alternative : `./flash_automation.sh` offre un mode non interactif (utilisez `--help` pour la liste des options).

### Étape 4 – Vérifications & dépannage

- Confirmez que le BMCU-C émet des trames via `screen /dev/ttyACM0 115200`.
- En cas d'erreur `Permission denied`, ajoutez l'utilisateur courant au groupe `dialout` :

  ```bash
  sudo usermod -aG dialout "$USER"
  newgrp dialout
  ```

- Consultez le guide détaillé : [`flash_automation/docs/flash_procedure.md`](./flash_automation/docs/flash_procedure.md).

> ⚠️ **Point de vigilance post-flash :** Gardez une session locale prête à interrompre l'opération (`Ctrl+C`) si la connexion SSH se coupe pendant le flashage et journalisez les logs dans `logs/flash_$(date +%F).log`.

---

## 🔐 Accès distant et automatisation via SSH

1. **Préparer l'hôte distant**
   ```bash
   sudo apt install -y openssh-server
   sudo systemctl enable --now ssh
   ```
   > ⚠️ **Point de vigilance sécurité :** Utilisez exclusivement l'authentification par clé (`PasswordAuthentication no`) et appliquez `chmod 600 ~/.ssh/authorized_keys`.

2. **Valider votre identité**
   ```bash
   ssh-keygen -t ed25519 -C "bmcu-maintenance"
   ssh-copy-id utilisateur@hote-distant
   ```
   > ⚠️ **Point de vigilance clé privée :** Stockez les clés temporaires sur un volume chiffré et détruisez-les (`shred`) après l'intervention.

3. **Ouvrir un tunnel sécurisé pour le port série**
   ```bash
   ssh -NL 3333:/dev/ttyACM0 utilisateur@hote-distant
   ```
   - `-N` évite l'ouverture d'un shell, `-L` expose `/dev/ttyACM0` via le port local `3333`.
   - Si l'hôte distant ne supporte pas le direct, lancez `socat TCP-LISTEN:3333,reuseaddr,fork FILE:/dev/ttyACM0,raw,echo=0`.
   > ⚠️ **Point de vigilance device lock :** Coupez les services utilisant déjà `/dev/ttyACM0` (`sudo systemctl stop klipper`) avant l'ouverture du tunnel.

4. **Automatiser build & flash à distance**
   ```bash
   ssh utilisateur@hote-distant "cd /opt/BMCU_C-to-Klipper/flash_automation && ./build.sh | tee -a /var/log/bmcu_flash/build.log"
   ssh -t utilisateur@hote-distant "cd /opt/BMCU_C-to-Klipper/flash_automation && python3 flash.py"
   ```

   > 💡 **Mode test à blanc :** Activez l'option lorsque l'assistant vous la propose. Pour un run 100 % non interactif, préparez un fichier de paramètres ou appelez directement `python3 flashBMCUtoKlipper_automation.py` avec `--dry-run`, `--backup-command` et les options réseau adaptées.

   Exemple d'automatisation complète :

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
   > ⚠️ **Point de vigilance audit :** Archivez les journaux dans `/var/log/bmcu_flash/` avec un horodatage ISO8601 pour chaque passage.

5. **Fermer proprement la session**
   - `exit` pour fermer la session interactive.
   - `lsof /dev/ttyACM0` pour vérifier que le port série est libéré.
   > ⚠️ **Point de vigilance nettoyage :** Supprimez les clés temporaires et réactivez les services (`sudo systemctl start klipper`) seulement après validation du flash.

---

## 🐍 Addon Happy Hare (dépôt `addon/`)

```text
┌────────────────────────────────────────────────────────────┐
│ Validation Happy Hare                                       │
├─────────────────────┬───────────────────────────────────────┤
│ Module chargé       │ bmcu.py détecté par Klipper            │
├─────────────────────┼───────────────────────────────────────┤
│ Menus interface     │ Sections BMCU visibles dans Happy Hare │
├─────────────────────┼───────────────────────────────────────┤
│ Journal Klipper     │ Pas d'erreur « MCU 'bmcu' shutdown »   │
├─────────────────────┼───────────────────────────────────────┤
│ Version firmware    │ Correspond à la build fraîchement flashée │
└─────────────────────┴───────────────────────────────────────┘
```

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

> ⚠️ **Point de vigilance Klipper :** Surveillez les occurrences de `MCU 'bmcu' shutdown` dans `/tmp/klippy.log` et assurez-vous que la version de firmware signalée correspond à celle fraîchement flashée.

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
