# Flash automatique du BMCU-C

Ce répertoire constitue un dépôt autonome contenant tout le nécessaire pour
compiler Klipper, générer le binaire spécifique au BMCU-C et automatiser le
flash (manuel ou distant).

## 🧰 Prérequis

- Linux/macOS récent avec `bash`, `git`, `python3` (≥ 3.10) et `pip`.
- Accès réseau/USB au BMCU-C.
- Outils additionnels pour le flash local : `wchisp`, `sha256sum`, `stat`.
  - `flash_automation.sh` télécharge automatiquement `wchisp` depuis les
    releases GitHub officielles (`.cache/tools/wchisp/`) lorsque l'outil est
    absent du système et que `WCHISP_AUTO_INSTALL` vaut `true` (comportement
    par défaut).
- Les architectures non prises en charge officiellement (ex. `armv7l`, `i686`)
  doivent suivre [la procédure de compilation manuelle](./docs/wchisp_manual_install.md)
  ou fournir une archive personnalisée via les variables `WCHISP_FALLBACK_*`.
- Outils additionnels pour l'automatisation distante : `ipmitool`, `sshpass`,
  `scp`, `ping`.

> 💡 Sur hôte x86_64, la toolchain RISC-V et les sources Klipper sont téléchargées automatiquement
> dans `.cache/` si elles sont absentes.
> ⚠️ Sur Raspberry Pi OS / Armbian (ARM64), installez manuellement une toolchain compatible
> puis exportez `CROSS_PREFIX` (voir le README principal pour des commandes détaillées).
> 💡 Désactivez l'installation automatique en exportant `WCHISP_AUTO_INSTALL=false`
> si vous préférez gérer manuellement l'outil (paquet distribution, build
> local, etc.).

## 🚀 Démarrage rapide

```bash
cd flash_automation
chmod +x *.sh
./build.sh
python3 install_wchisp.py
python3 flash.py
```

- `build.sh` synchronise Klipper depuis `$KLIPPER_REPO_URL` (défaut : dépôt
  officiel) et applique les correctifs présents dans `klipper_overrides/` avant
  de lancer la compilation. Le dépôt local (`.cache/klipper`) est conservé :
  un `git fetch --depth=1 --tags` actualise la branche suivie et limite les
  références téléchargées aux seules entrées nécessaires. Si un binaire
  `out/klipper.bin` est détecté avec la même empreinte de configuration,
  l'utilisateur peut choisir de le réutiliser afin d'éviter une recompilation.
- Par défaut, le binaire généré est disponible dans `.cache/klipper/out/klipper.bin`.
  Si Klipper est déjà installé ailleurs, exportez `KLIPPER_SRC_DIR=/chemin/vers/klipper`
  avant `./build.sh` pour réutiliser cet environnement et `KLIPPER_FIRMWARE_PATH`
  pour pointer `flash_automation.sh` vers le firmware compilé.
- `flash.py` propose une interface interactive haut-niveau ;
  `flash_automation.sh` fournit une version minimale (terminal) ;
  `flashBMCUtoKlipper_automation.py` permet l'orchestration distante (CI/batch).
  `automation_cli.py` centralise ces procédures dans un menu inspiré de KIAUH
  et consigne toutes les étapes dans `~/BMCU_C_to_Klipper_logs/automation-<horodatage>.log`.

### 🔐 Vérification du firmware

- `flash.py` calcule désormais automatiquement l'empreinte **SHA-256** du firmware
  avant de lancer le flash.
- Placez la valeur de référence dans `klipper.sha256` (format `sha256sum`)
  pour qu'elle soit chargée automatiquement :

  ```bash
  sha256sum .cache/klipper/out/klipper.bin > klipper.sha256
  ```

- Vous pouvez également fournir la valeur attendue en CLI via
  `--firmware-sha256=<empreinte>` ou en pointant un fichier spécifique avec
  `--firmware-sha256-file=/chemin/vers/mon_checksum.txt`.
- En cas de divergence, l'assistant interrompt le processus et affiche les
  deux empreintes afin d'éviter un flash risqué.

## ⚙️ Paramètres utiles

| Variable d'environnement | Description | Défaut |
| --- | --- | --- |
| `KLIPPER_REPO_URL` | URL du dépôt Klipper à cloner | `https://github.com/Klipper3d/klipper.git` |
| `KLIPPER_REF` | Branche/tag/commit à utiliser | `master` |
| `KLIPPER_CLONE_DEPTH` | Profondeur du clone `git` | `1` |
| `KLIPPER_FETCH_REFSPEC` | Référence distante suivie (`refs/heads/...` ou `refs/tags/...`) | `refs/heads/${KLIPPER_REF}` (déduit automatiquement) |
| `KLIPPER_SRC_DIR` | Répertoire Klipper à réutiliser (aucun clone/checkout automatique) | `flash_automation/.cache/klipper` |
| `KLIPPER_FIRMWARE_PATH` | Firmware attendu par `flash_automation.sh` | `.cache/klipper/out/klipper.bin` |
| `CROSS_PREFIX` | Toolchain RISC-V installée manuellement | `riscv32-unknown-elf-` |
| `TOOLCHAIN_RELEASE` | Tag de la toolchain RISC-V officielle à télécharger | `2025.10.18` |
| `TOOLCHAIN_ARCHIVE_X86_64` | Nom d'archive utilisé pour `TOOLCHAIN_RELEASE` | `riscv32-elf-ubuntu-22.04-gcc.tar.xz` |
| `TOOLCHAIN_BASE_URL` | Base des téléchargements toolchain (concaténée avec l'archive) | `https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/${TOOLCHAIN_RELEASE}` |
| `WCHISP_AUTO_INSTALL` | Autoriser le téléchargement automatique de `wchisp` | `true` |
| `WCHISP_RELEASE` | Tag GitHub utilisé pour récupérer `wchisp` | `v0.3.0` |
| `WCHISP_BASE_URL` | Base des URL de téléchargement `wchisp` | `https://github.com/ch32-rs/wchisp/releases/download` |
| `WCHISP_ARCH_OVERRIDE` | Forcer l'architecture détectée (tests/simulations) | `uname -m` |
| `WCHISP_FALLBACK_ARCHIVE_URL` | Archive alternative à utiliser pour les architectures non supportées | *(vide)* |
| `WCHISP_FALLBACK_ARCHIVE_NAME` | Nom de fichier à utiliser si l'URL de secours contient des paramètres | dérivé de l'URL |
| `WCHISP_FALLBACK_CHECKSUM` | Somme SHA-256 de l'archive de secours (fortement recommandé) | *(vide)* |
| `WCHISP_ARCHIVE_CHECKSUM_OVERRIDE` | Somme SHA-256 personnalisée appliquée à l'archive wchisp téléchargée | *(vide)* |
| `ALLOW_UNVERIFIED_WCHISP` | `true`/`1` pour autoriser le mode dégradé (archive conservée même si la vérification échoue) | `false` |

Les journaux et rapports d'échec sont écrits dans `~/BMCU_C_to_Klipper_logs/`
avec horodatage (chemin personnalisable via `BMCU_LOG_ROOT`).

Le script shell accepte également quelques options CLI avancées :

- `--wchisp-checksum <sha256>` (ou `--wchisp-checksum=<sha256>`) pour imposer
  une empreinte spécifique lors de l'installation automatique.
- `--allow-unsigned-wchisp` pour activer le mode dégradé qui laisse le binaire
  en place malgré une vérification SHA-256 échouée ; un avertissement est
  affiché et journalisé pour rappeler le risque encouru.

### 🔄 Flux de synchronisation

- Lors des exécutions successives, `./build.sh` réutilise le dépôt
  `.cache/klipper` et l'actualise via `git fetch --depth=1 --tags --prune`
  en se limitant au refspec configuré (`remote.origin.fetch`).
- Les signatures de la configuration (`klipper.config`, `klipper_overrides/`)
  et du binaire `out/klipper.bin` sont enregistrées dans
  `.cache/klipper.bin.meta`. Si rien n'a changé et que le binaire est plus
  récent que les fichiers de configuration, le script propose de le réutiliser
  au lieu de recompiler.
- Répondez `o` pour conserver le firmware existant ou toute autre touche pour
  forcer une recompilation propre.

## 📚 Documentation

- [Procédure complète de flash](./docs/flash_procedure.md)
- [Retour à l'état initial après échec](./docs/rollback_procedure.md)
- [Configuration Klipper de référence](./klipper.config)
- [Correctifs appliqués automatiquement](./klipper_overrides)
- [Compilation manuelle de `wchisp`](./docs/wchisp_manual_install.md)

## 🧪 Tests recommandés

1. `./build.sh` – vérifie le téléchargement de Klipper et la compilation.
2. `python3 flash.py --dry-run` – valide le parcours interactif sans flasher.
3. `./flash_automation.sh` – teste le flash local avec un BMCU-C connecté.

## 📄 Licence

Le contenu est diffusé sous licence GPLv3, identique à la racine du projet.
