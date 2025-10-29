# Compilation manuelle de `wchisp`

Les releases officielles de `wchisp` ne fournissent actuellement que des binaires Linux pour
les architectures `x86_64` et `aarch64`. Les machines 32 bits (ex. `armv7l`, `i686`) ou les
architectures plus exotiques doivent compiler l'outil manuellement ou fournir une archive
personnalisée au système d'automatisation.

## 1. Dépendances nécessaires

- Rust et `cargo` (version 1.70 ou ultérieure recommandée).
- `git`
- `build-essential` / outils de compilation standards.

Sous Debian/Ubuntu, installez les prérequis avec :

```bash
sudo apt update
sudo apt install build-essential git curl pkg-config libudev-dev
curl https://sh.rustup.rs -sSf | sh
source "$HOME/.cargo/env"
```

## 2. Récupérer et compiler `wchisp`

```bash
git clone https://github.com/ch32-rs/wchisp.git
cd wchisp
cargo build --release
```

Le binaire compilé est disponible dans `target/release/wchisp`.

## 3. Intégration avec les scripts d'automatisation

Deux options sont possibles :

1. **Utiliser un binaire local** : copiez `target/release/wchisp` vers un dossier présent
   dans votre `PATH` (ex. `~/.local/bin`) puis exportez `WCHISP_BIN` pour pointer vers ce
   binaire avant d'exécuter `flash_automation.sh` ou `install_wchisp.py`.
2. **Fournir une archive personnalisée** : créez une archive tar.gz contenant le binaire :

   ```bash
   tar -czf wchisp-linux-armv7.tar.gz -C target/release wchisp
   ```

   Ensuite, exportez les variables suivantes :

   ```bash
   export WCHISP_FALLBACK_ARCHIVE_URL="https://mon-serveur.exemple/wchisp-linux-armv7.tar.gz"
   export WCHISP_FALLBACK_CHECKSUM="<sha256 de l'archive>"
   export WCHISP_FALLBACK_ARCHIVE_NAME="wchisp-linux-armv7.tar.gz"  # Optionnel si l'URL est propre
   ```

   Les scripts téléchargeront et installeront cette archive lors de la détection d'une
   architecture non officiellement prise en charge.

## 4. Validation

Après installation, vérifiez la version et l'accès USB :

```bash
wchisp --version
wchisp scan
```

Si ces commandes fonctionnent, vous pouvez lancer le flash via `flash_automation.sh` ou
`flash.py` comme documenté.
