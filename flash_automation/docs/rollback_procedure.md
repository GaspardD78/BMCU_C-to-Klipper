# Procédure de retour à l'état initial après un échec

Cette procédure vous ramène pas à pas vers un environnement sain après un échec ou une interruption de script dans `flash_automation/`. Elle couvre :

| Étape | Objectif |
| --- | --- |
| 1. Sécuriser le matériel | Couper toute opération en cours et stabiliser le BMCU-C |
| 2. Collecter les traces | Conserver les journaux avant nettoyage |
| 3. Nettoyer l’environnement | Repartir d’un dépôt et d’une virtualenv propres |
| 4. Restaurer un firmware | Réinjecter un binaire validé (origine ou Klipper fiable) |
| 5. Vérifier avant reprise | Contrôler build/flash et documenter l’incident |

> 💡 Avant **chaque** flash, déclenchez une sauvegarde via `--backup-command` ou un script maison : les étapes suivantes supposent qu’un binaire de référence est disponible.

---

## 1. Sécuriser le matériel

1. Interrompez le script fautif (`Ctrl+C`) puis vérifiez qu’aucun autre processus `flash.py`, `flash_automation.sh` ou `flashBMCUtoKlipper_automation.py` n’est actif :

   ```bash
   pgrep -af flash_automation || true
   ```

2. Coupez l’alimentation de l’imprimante/BMCU-C si l’écriture a été interrompue, attendez 10 s puis reconnectez uniquement l’USB ou le lien réseau utilisé pour le diagnostic.
3. Notez l’état des voyants (LED, relais, écran) pour faciliter l’analyse ultérieure.

## 2. Collecter les traces d'échec

1. Sauvegardez le dernier journal généré :

   ```bash
   dernier_log="$(ls -1t logs/flash_* 2>/dev/null | head -n 1)"
   [ -n "$dernier_log" ] && tail -n 200 "$dernier_log"
   ```

2. Copiez également `build.log` ou les sorties console si le script s’est arrêté avant la création d’un fichier dans `logs/`.
3. Identifiez le message d’erreur principal (compilation, flash, réseau…) afin de choisir la bonne stratégie de restauration.

## 3. Nettoyer l'environnement local

1. **Revenir à un dépôt propre**

   ```bash
   git status
   git restore --staged --worktree .
   ```

   Cette remise à zéro évite que des patchs temporaires dans `.cache/klipper` ou `klipper_overrides/` ne perturbent la prochaine tentative.

2. **Réinitialiser la virtualenv (si utilisée)**

   ```bash
   deactivate 2>/dev/null || true
   rm -rf .venv
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Supprimer les artefacts incomplets**

   ```bash
   rm -rf .cache/klipper/out
   rm -rf .cache/toolchains/tmp_*
   ```

   Le prochain `./build.sh` reconstruira un environnement propre et une toolchain valide.

## 4. Restaurer un firmware fonctionnel

### 4.1 Réinstaller le firmware d'origine

1. Localisez l’archive de sauvegarde (`factory.bin`, `backup_<date>.bin`, etc.).
2. Passez le BMCU-C en mode bootloader (bouton **BOOT0** maintenu pendant un reset) ou suivez la séquence décrite pour la variante USB-C dans la [procédure de flash](./flash_procedure.md#4-variantes-sans-bouton-boot--connecteur-usb-c).
3. Relancez le flash avec `wchisp` :

   ```bash
   wchisp -d 30 -c ch32v20x flash /chemin/vers/factory.bin
   ```

4. Redémarrez le module et vérifiez que l’AMS, les capteurs et les relais répondent comme avant l’incident.

### 4.2 Revenir à un firmware Klipper validé

Si seul un binaire Klipper fiable est disponible :

1. Copiez le fichier connu vers un emplacement sécurisé :

   ```bash
   mkdir -p backups
   cp "${KLIPPER_FIRMWARE_PATH:-.cache/klipper/out/klipper.bin}" "backups/klipper_$(date +%F).bin"
   ```

2. Flashez ce binaire avec `flash_automation.sh` (en ajustant `KLIPPER_FIRMWARE_PATH` si nécessaire) :

   ```bash
   KLIPPER_FIRMWARE_PATH="backups/klipper_YYYY-MM-DD.bin" ./flash_automation.sh
   ```

3. Vérifiez la version reportée via `flashBMCUtoKlipper_automation.py --dry-run` (champ `expected_final_version`) ou la commande `STATUS` dans Klipper avant de reprendre la production.

## 5. Vérifications finales

1. Relancez `./build.sh` puis `python3 flash.py --dry-run` pour confirmer que l’environnement est stable.
2. Validez les connexions réseau/USB (`ping`, `screen`, `ssh`).
3. Consignez l’incident (symptômes, actions, correctifs) dans votre outil de suivi afin de capitaliser sur l’expérience.

En suivant ces étapes, vous revenez à un état de référence documenté tout en conservant les preuves nécessaires à l’analyse de l’échec initial.
