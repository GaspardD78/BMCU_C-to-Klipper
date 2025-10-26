# Intégration du BMCU-C avec Klipper et Happy Hare

<p align="center">
  <img src="logo/bmcu_logo.png" alt="Logo BMCU-CtoKlipper" width="110" />
</p>

> ⚠️ **Statut : preuve de concept.** L'intégration n'a pas encore été validée sur un BMCU-C réel. Ce dépôt s'adresse aux développeurs et « makers » souhaitant contribuer aux tests matériels et logiciels.

Ce projet open-source fournit deux briques complémentaires pour piloter un BMCU-C (clone communautaire de l'AMS Bambu Lab) depuis Klipper via Happy Hare :

1. **Flashage du BMCU-C** — scripts et configurations pour compiler puis charger Klipper sur le microcontrôleur.
2. **Addon Python pour Klipper** — module, macros et documentation permettant à Happy Hare de dialoguer avec le BMCU-C.

Les deux volets peuvent être utilisés ensemble ou séparément selon votre besoin (par exemple : vous pouvez ne déployer que l'addon Python si vous disposez déjà d'un BMCU-C flashé avec Klipper).

---

## Sommaire

1. [Pré-requis](#pré-requis)
2. [Flashage du BMCU-C (firmware)](#flashage-du-bmcu-c-firmware)
   1. [Préparer l'environnement](#préparer-lenvironnement)
   2. [Compiler Klipper](#compiler-klipper)
   3. [Flasher le microcontrôleur](#flasher-le-microcontrôleur)
   4. [Vérifier le flash](#vérifier-le-flash)
3. [Addon Python pour Klipper (Happy Hare)](#addon-python-pour-klipper-happy-hare)
   1. [Copier les fichiers nécessaires](#copier-les-fichiers-nécessaires)
   2. [Configurer Happy Hare](#configurer-happy-hare)
   3. [Valider la communication](#valider-la-communication)
4. [Structure du dépôt](#structure-du-dépôt)
5. [Contribuer](#contribuer)
6. [Licence](#licence)

---

## Pré-requis

Avant de démarrer, assurez-vous de disposer des éléments suivants :

- Une machine hôte équipée de Python 3.10 ou plus récent.
- Les outils de compilation RISC-V (`gcc-riscv64-unknown-elf` et `picolibc-riscv64-unknown-elf`).
- L'accès en lecture/écriture au port série utilisé par le BMCU-C (généralement via l'appartenance au groupe `dialout`).
- Le sous-module `klipper/` initialisé :
  ```bash
  git submodule update --init --recursive
  ```
- Les scripts du dépôt marqués comme exécutables (`chmod +x firmware/*.sh`).

> ℹ️ Pour une liste complète des versions minimales supportées, consultez [AGENTS.md](./AGENTS.md).

---

## 1. Flashage du BMCU-C (firmware)

Tout le nécessaire pour compiler et flasher le firmware Klipper se trouve dans le répertoire `firmware/`.

### 1.1 Préparer l'environnement

1. Installez les dépendances système requises pour le cross-compilateur RISC-V.
2. Ouvrez un terminal et placez-vous à la racine du dépôt :
   ```bash
   cd /chemin/vers/BMCU_C-to-Klipper
   ```
3. Vérifiez que le sous-module Klipper est initialisé :
   ```bash
   git submodule status
   ```
   Le commit référencé ne doit pas être préfixé par un signe `-`.

### 1.2 Compiler Klipper

1. Lancez la compilation depuis le script dédié :
   ```bash
   ./firmware/build.sh
   ```
2. Patientez jusqu'à la fin de la compilation. Le firmware généré (`klipper.bin`) se trouvera dans `klipper/out/`.
3. Si la compilation échoue, vérifiez les messages d'erreur pour confirmer la présence des dépendances et la configuration de `CROSS_PREFIX`.

### 1.3 Flasher le microcontrôleur

1. Connectez le BMCU-C à votre machine via USB et placez-le en mode bootloader si nécessaire.
2. Exécutez l'assistant interactif de flash :
   ```bash
   ./firmware/flash.py
   ```
3. Suivez les questions affichées par le script (sélection du port série, confirmation du firmware, etc.).
4. Pour des scénarios avancés :
   - Automatisation : `./firmware/flashBMCUtoKlipper_automation.py`
   - Flash bas niveau : `./firmware/flash.sh`

### 1.4 Vérifier le flash

1. Redémarrez le BMCU-C en mode normal.
2. Ouvrez un terminal série (ex. `screen /dev/ttyUSB0 115200`) pour vérifier que Klipper initialise correctement le périphérique.
3. Consultez les journaux de Klipper pour confirmer que le microcontrôleur est détecté sans erreur.

> 📄 Une procédure détaillée avec captures et conseils de dépannage est disponible dans [docs/flash_procedure.md](./docs/flash_procedure.md).

### 1.5 Automatiser le flash

Pour un flash totalement piloté par script (usage en CI, en atelier ou pour répéter la procédure sur plusieurs BMCU-C), vous pouvez utiliser `firmware/flashBMCUtoKlipper_automation.py`.

1. **Vérifiez les dépendances système** : par défaut, le script exige `ipmitool`, `sshpass`, `scp` et `ping`. Ajustez la liste avec `--required-commands` si nécessaire.
2. **Préparez le firmware** : assurez-vous que le fichier binaire généré (`klipper/out/klipper.bin`) est accessible depuis la machine d'orchestration.
3. **Lancez l'automatisation** avec les paramètres adaptés à votre installation :
   ```bash
   python3 firmware/flashBMCUtoKlipper_automation.py \
       --bmc-host 192.168.1.100 \
       --bmc-user root \
       --bmc-password "mot_de_passe" \
       --firmware-file klipper/out/klipper.bin \
       --wait-for-reboot \
       --firmware-sha256 "<hash_attendu>" \
       --expected-final-version "vX.Y.Z"
   ```
   Les options `--firmware-sha256` et `--expected-final-version` sont facultatives mais recommandées pour valider l'intégrité du binaire et la version cible.
4. **Mode test** : ajoutez `--dry-run` pour vérifier la configuration sans exécuter d'opérations distantes.
5. **Consultez les journaux** : chaque exécution crée un dossier horodaté dans `logs/flash_test_*` contenant `debug.log` et un éventuel rapport d'échec.

---

## 2. Addon Python pour Klipper (Happy Hare)

Le dossier `bmcu_addon/` regroupe le code et la configuration nécessaires à l'intégration du BMCU-C.

### 2.1 Copier les fichiers nécessaires

1. Transférez le module principal dans l'instance Klipper cible :
   ```bash
   cp bmcu_addon/bmcu.py <chemin_klipper>/klippy/extras/
   ```
2. Copiez les macros et configurations associées :
   ```bash
   cp -r bmcu_addon/config/* <chemin_klipper>/config/
   ```

### 2.2 Configurer Happy Hare

1. Éditez votre `printer.cfg` (ou le fichier d'inclusion Happy Hare) pour inclure les macros fournies.
2. Ajustez les paramètres de communication (port RS-485, vitesse, identifiants de gate) selon votre installation.
3. Redémarrez Klipper pour charger le module `bmcu` et valider la configuration.

### 2.3 Valider la communication

1. Depuis l'interface de contrôle (Fluidd, Mainsail, etc.), envoyez la commande :
   ```
   BMCU_SELECT_GATE GATE=1
   ```
2. Vérifiez que la sélection est reconnue et qu'aucune erreur ne remonte dans les logs.
3. Testez les autres macros (`BMCU_HOME`, `BMCU_STATUS`) pour confirmer le dialogue complet.

> 📘 Le guide d'installation détaillé est disponible dans [docs/setup.md](./docs/setup.md).

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

Ce projet est distribué sous la licence GNU General Public License v3 (GPLv3).

Le texte complet de la licence est disponible dans le fichier [LICENSE](./LICENSE) à la racine de ce dépôt. En résumé, cette licence vous autorise à utiliser, modifier et distribuer ce logiciel, à condition que tout projet dérivé soit également distribué sous la même licence.
