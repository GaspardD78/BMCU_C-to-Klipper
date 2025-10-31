# Banc de test Manta EZE3 + CB2 + BMCU-C

Ce guide décrit la mise en place d'un environnement de test complet pour le
firmware Klipper intégrant une carte **Manta EZE3**, un **BTT CB2** (Compute
Board) et un **BMCU-C** alimenté en 24 V et relié en USB. Il vise à offrir un
cadre reproductible pour valider les évolutions du projet BMCU_C-to-Klipper.

## 1. Objectifs du banc

- Vérifier l'intégration matérielle CB2 ↔ Manta EZE3 ↔ BMCU-C.
- Tester les scripts de flash/diagnostic avec un BMCU-C réel, alimenté et
  visible sur le bus USB.
- Offrir une plateforme de tests manuels ou automatisés pour la
  configuration Klipper fournie dans `flash_automation/klipper.config`.

## 2. Matériel requis

| Élément | Référence / recommandation | Notes |
| --- | --- | --- |
| Carte mère | BigTreeTech Manta EZE3 | Carte principale pilotée par le CB2 via le connecteur d'extension. |
| Compute board | BigTreeTech CB2 (avec eMMC ou carte SD) | Doit pouvoir exécuter Debian/Armbian pour Klipper + Moonraker. |
| Microcontrôleur | BMCU-C rev. A ou ultérieure | Port USB-C fonctionnel + bornier 24 V. |
| Alimentation 24 V | 24 V / 5 A minimum | Permet d'alimenter simultanément la Manta et le BMCU-C. |
| Câbles USB | USB-C ↔ USB-A (données) + câble court de secours | Préférer un câble blindé. |
| Câbles d'alim 24 V | 2×0,75 mm² min | Un pour la Manta, un pour le BMCU-C si alimentation séparée. |
| PC de contrôle | Linux x86_64 avec accès SSH et USB | Pour piloter les scripts `flash_automation`. |
| Multimètre | — | Vérification des polarités et de la tension. |
| Accessoires sécurité | Coupe-circuit ou disjoncteur 5 A, EPI | Recommandé pour tests prolongés. |

## 3. Schéma de câblage

1. **Alimentation**
   - Relier l'alimentation 24 V aux borniers `VIN/GND` de la Manta EZE3.
   - Alimenter le BMCU-C via son bornier 24 V (respecter la polarité) ou via
     une dérivation dédiée avec fusible 5 A.
   - Vérifier au multimètre que 24 V est présent avant de brancher les cartes.

2. **Liaison CB2 ↔ Manta**
   - Insérer le CB2 sur le connecteur d'extension dédié de la Manta.
   - Brancher le câble FFC / connecteur dédié (si fourni) pour les lignes USB
     et alimentation.

3. **Connexion BMCU-C**
   - Brancher le BMCU-C en USB sur la Manta (port USB interne) ou directement
     au PC de contrôle selon l'usage.
   - Conserver un accès direct au BMCU-C via un câble USB-C ↔ PC pour les
     opérations de flash/diagnostic.

> ⚠️ Ne jamais connecter/déconnecter le BMCU-C sous tension 24 V. Couper
> l'alimentation principale avant toute manipulation du bornier.

## 4. Préparation logicielle du CB2

1. **Système d'exploitation**
   - Installer l'image Armbian / Debian recommandée par BigTreeTech.
   - Ajouter un utilisateur `klipper` avec droits `sudo`.
   - Mettre à jour le système :
     ```bash
     sudo apt update && sudo apt full-upgrade -y
     sudo reboot
     ```

2. **Pile logicielle Klipper**
   - Cloner Klipper, Moonraker et Mainsail/Fluidd selon les besoins.
   - Installer les dépendances :
     ```bash
     sudo apt install -y python3-virtualenv python3-dev libopenblas-dev \
       libncurses-dev libffi-dev build-essential git
     ```
   - Configurer l'environnement virtuel Klipper :
     ```bash
     cd ~/klipper
     python3 -m venv .venv
     source .venv/bin/activate
     ./scripts/install-debian.sh
     ```

3. **Configuration de la Manta**
   - Copier `flash_automation/klipper.config` vers `/home/klipper/printer.cfg`.
   - Adapter les sections spécifiques (endstops, drivers) selon le matériel.
   - Redémarrer le service Klipper :
     ```bash
     sudo systemctl restart klipper
     ```

## 5. Préparation du BMCU-C

1. **Connexion initiale** : brancher le BMCU-C via USB au PC de contrôle.
2. **Compilation du firmware** :
   ```bash
   cd ~/BMCU_C-to-Klipper/flash_automation
   ./build.sh --target bmcuc
   ```
3. **Flash** :
   ```bash
   python3 flash.py --port /dev/ttyACM0 --power-source 24v
   ```
   - Le script demande confirmation de la tension ; vérifier au multimètre.
   - Vérifier que le firmware est correctement détecté (`lsusb`, `dmesg`).

4. **Journalisation** :
   - Les logs se trouvent dans `~/BMCU_C_to_Klipper_logs/`.
   - Archiver les journaux pertinents dans `docs/test-logs/` après chaque
     session.

## 6. Validation du banc

### 6.1 Tests électriques
- Couper l'alimentation, vérifier l'absence de court-circuit.
- Mesurer 24 V sur les borniers Manta et BMCU-C.
- S'assurer que la masse USB et la masse 24 V sont communes.

### 6.2 Tests de communication
- Lancer `lsusb` sur le CB2 : le BMCU-C doit apparaître.
- Démarrer Klipper et vérifier que le MCU secondaire est en ligne (`STATUS`
  dans l'interface Mainsail/Fluidd).
- Utiliser `python3 automation_cli.py --dry-run` pour valider le pipeline
  logiciel côté PC.

### 6.3 Tests fonctionnels
- Envoyer une commande Mainsail `STATUS` pour vérifier la remontée des
  capteurs.
- Exécuter une séquence de chauffe/ventilation simulée via Klipper (commande
  `SET_FAN_SPEED` sur un ventilateur factice).
- Contrôler la stabilité USB en lançant un transfert prolongé :
  ```bash
  python3 flash_automation/flashBMCUtoKlipper_automation.py \
    --dry-run --stress-usb 600
  ```
  (Le paramètre `--stress-usb` est optionnel ; adapter si absent.)

## 7. Automatisation & CI

- Prévoir un Raspberry Pi ou un PC Linux dédié connecté à la Manta pour
  déclencher des tests programmés (cron ou GitHub Actions self-hosted runner).
- Intégrer un script d'automatisation qui :
  1. Met à jour le dépôt `BMCU_C-to-Klipper`.
  2. Recompile et flashe le BMCU-C (mode supervision).
  3. Exécute des tests Klipper (`QUERY_ADC`, `M112`, redémarrage MCU).
  4. Publie les journaux dans `docs/test-logs/`.

## 8. Sécurité & bonnes pratiques

- Utiliser un disjoncteur différentiel 30 mA en amont de l'alimentation 24 V.
- Étiqueter clairement les câbles 24 V et USB.
- Maintenir une ventilation suffisante autour des cartes durant les tests.
- Documenter toute modification matérielle (longueur câbles, connecteurs) dans
  un journal de bord.

## 9. Checklist de mise en service

| Étape | OK | Commentaires |
| --- | --- | --- |
| Tension 24 V vérifiée au multimètre | ☐ | |
| CB2 flashé avec la dernière image Armbian/Debian | ☐ | |
| Klipper + Moonraker opérationnels | ☐ | |
| BMCU-C flashé avec le firmware BMCU_C-to-Klipper | ☐ | |
| Communication USB stable (60 min) | ☐ | |
| Logs archivés dans `docs/test-logs/` | ☐ | |

> 💡 Conserver cette checklist imprimée à proximité du banc de test et la
> signer à chaque session de validation.
