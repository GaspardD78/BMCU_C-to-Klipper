# Flash automatique du BMCU-C

Ce répertoire constitue un dépôt autonome contenant tout le nécessaire pour
compiler Klipper, générer le binaire spécifique au BMCU-C et automatiser le
flash (manuel ou distant).

## 🧰 Prérequis

- Linux/macOS récent avec `bash`, `git`, `python3` (≥ 3.10) et `pip`.
- Accès réseau/USB au BMCU-C.
- Outils additionnels pour le flash local : `wchisp`, `sha256sum`, `stat`.
- Outils additionnels pour l'automatisation distante : `ipmitool`, `sshpass`,
  `scp`, `ping`.

> 💡 Sur hôte x86_64, la toolchain RISC-V et les sources Klipper sont téléchargées automatiquement
> dans `.cache/` si elles sont absentes.
> ⚠️ Sur Raspberry Pi OS / Armbian (ARM64), installez manuellement une toolchain compatible
> puis exportez `CROSS_PREFIX` (voir le README principal pour des commandes détaillées).
> 💡 Installez `wchisp` via `python3 -m pip install --user wchisp` si l'outil n'est pas encore disponible.

## 🚀 Démarrage rapide

```bash
cd flash_automation
chmod +x *.sh
./build.sh
python3 flash.py
```

- `build.sh` clone Klipper depuis `$KLIPPER_REPO_URL` (défaut : dépôt officiel)
  et applique les correctifs présents dans `klipper_overrides/` avant de lancer
  la compilation.
- Le binaire généré est disponible dans `.cache/klipper/out/klipper.bin`.
- `flash.py` propose une interface interactive haut-niveau ;
  `flash_automation.sh` fournit une version minimale (terminal) ;
  `flashBMCUtoKlipper_automation.py` permet l'orchestration distante (CI/batch).

## ⚙️ Paramètres utiles

| Variable d'environnement | Description | Défaut |
| --- | --- | --- |
| `KLIPPER_REPO_URL` | URL du dépôt Klipper à cloner | `https://github.com/Klipper3d/klipper.git` |
| `KLIPPER_REF` | Branche/tag/commit à utiliser | `master` |
| `KLIPPER_CLONE_DEPTH` | Profondeur du clone `git` | `1` |
| `CROSS_PREFIX` | Toolchain RISC-V installée manuellement | `riscv32-unknown-elf-` |

Les journaux et rapports d'échec sont écrits dans `logs/` avec horodatage.

## 📚 Documentation

- [Procédure complète de flash](./docs/flash_procedure.md)
- [Configuration Klipper de référence](./klipper.config)
- [Correctifs appliqués automatiquement](./klipper_overrides)

## 🧪 Tests recommandés

1. `./build.sh` – vérifie le téléchargement de Klipper et la compilation.
2. `python3 flash.py --dry-run` – valide le parcours interactif sans flasher.
3. `./flash_automation.sh` – teste le flash local avec un BMCU-C connecté.

## 📄 Licence

Le contenu est diffusé sous licence GPLv3, identique à la racine du projet.
