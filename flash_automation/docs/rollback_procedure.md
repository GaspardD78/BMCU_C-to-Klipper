# Procédure de retour à l'état initial après un échec de script

Cette procédure décrit les étapes à suivre pour revenir à un état stable après
l'échec ou l'interruption d'un des scripts de `flash_automation/`. Elle couvre
à la fois la remise en sécurité du matériel, le nettoyage de l'environnement de
travail et la restauration d'un firmware connu sur le BMCU-C.

> 💡 Réalisez systématiquement une sauvegarde de l'état courant du BMCU-C (via
> `--backup-command` ou un script équivalent) **avant** chaque flash. Les
> étapes ci-dessous supposent qu'un fichier de référence est disponible pour
> restaurer le microcontrôleur.

## 1. Sécuriser le matériel

1. **Coupez les opérations en cours :** interrompez le script fautif avec
   `Ctrl+C` et assurez-vous qu'aucun autre processus `flash.py`,
   `flash_automation.sh` ou `flashBMCUtoKlipper_automation.py` ne tourne encore
   (`pgrep -af flash_automation`).
2. **Stabilisez le BMCU-C :**
   - Débranchez l'alimentation de l'imprimante et du BMCU-C si le flash a été
     interrompu au milieu d'une écriture.
   - Patientez 10 secondes, puis rebranchez uniquement l'alimentation USB ou la
     connexion réseau nécessaire au diagnostic.
3. **Notez l'état des voyants** (LED, écran, relais) pour faciliter l'analyse
   ultérieure.

## 2. Collecter les traces d'échec

1. Récupérez le dernier journal généré :
   ```bash
   ls -1t logs/flash_* | head -n 1
   tail -n 200 "$(ls -1t logs/flash_* | head -n 1)"
   ```
2. Conservez également les sorties de `build.log` ou de la console si le script
   s'est arrêté avant de créer un fichier dans `logs/`.
3. Identifiez le message d'erreur principal afin de choisir la stratégie de
   restauration appropriée (erreur de compilation, échec de flash, absence de
   connexion réseau, etc.).

## 3. Nettoyer l'environnement local

1. **Revenir à un dépôt propre :**
   ```bash
   git status
   git restore --staged --worktree .
   ```
   Cette étape garantit que les correctifs appliqués par `build.sh` dans
   `.cache/klipper` ou `klipper_overrides/` ne polluent pas la prochaine
   tentative.
2. **Réinitialiser la virtualenv (si utilisée) :**
   ```bash
   deactivate 2>/dev/null || true
   rm -rf .venv
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Purger les artefacts incomplets :**
   ```bash
   rm -rf .cache/klipper/out
   rm -rf .cache/toolchains/tmp_*
   ```
   Cela force `build.sh` à reconstruire le firmware et la toolchain au prochain
   lancement.

## 4. Revenir à un firmware connu sur le BMCU-C

### 4.1 Réinstaller le firmware d'origine

1. Localisez l'archive de sauvegarde générée par votre script (`factory.bin`,
   `backup_<date>.bin`, etc.).
2. Rebranchez le BMCU-C en mode bootloader (bouton **BOOT0** maintenu pendant un
   reset) ou, pour les variantes USB-C uniquement, suivez la séquence décrite
   dans la [procédure de flash](./flash_procedure.md#4-variantes-sans-bouton-boot--connecteur-usb-c).
3. Lancez la restauration via `wchisp` :
   ```bash
   wchisp -d 30 -c ch32v20x flash /chemin/vers/factory.bin
   ```
4. Redémarrez le module et vérifiez que les services attendus (AMS, capteurs,
   relais) répondent comme avant l'incident.

### 4.2 Retour au dernier firmware Klipper fonctionnel

Si la sauvegarde d'origine n'est pas disponible mais qu'une version Klipper
fiable l'est :

1. Créez un répertoire de sauvegarde local si nécessaire puis copiez le binaire
   validé vers un emplacement distinct :
   ```bash
   mkdir -p backups
   cp .cache/klipper/out/klipper.bin backups/klipper_$(date +%F).bin
   ```
2. Flashez ce binaire connu à l'aide de `flash_automation.sh` en mode
   interactif :
   ```bash
   ./flash_automation.sh --firmware backups/klipper_YYYY-MM-DD.bin
   ```
3. Vérifiez la version reportée par `flashBMCUtoKlipper_automation.py --dry-run`
   (champ « expected_final_version ») ou via l'interface Klipper (`STATUS`)
   avant de reprendre une production.

## 5. Vérifications finales

1. Relancez `./build.sh` puis `python3 flash.py --dry-run` pour valider que
   l'environnement local est de nouveau sain avant tout nouveau flash.
2. Confirmez que les accès réseau/USB sont stables (`ping`, `screen`, `ssh`).
3. Documentez l'incident (erreur observée, actions menées) dans votre outil de
   suivi pour prévenir toute régression future.

En suivant cette séquence, vous revenez à un état de référence documenté tout
en conservant les journaux nécessaires pour analyser et corriger l'échec
initial.
