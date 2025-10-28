# Plan de Test Approfondi pour `flash_automation.sh`

## 1. Objectif

Ce document définit une série de tests pour valider le comportement, la robustesse et la fiabilité du script `flash_automation.sh` sur les systèmes d'exploitation **Armbian** et **Raspberry Pi OS**. L'objectif est d'identifier, de documenter et de corriger les erreurs potentielles et les points de blocage avant le déploiement.

## 2. Environnement de Test Cible

Les tests doivent être réalisés sur les configurations suivantes :

- **Matériel :**
  - Raspberry Pi 3B+ / 4B / 5
  - Alternative Armbian (ex: Orange Pi, Banana Pi)
- **Système d'exploitation :**
  - Raspberry Pi OS Lite (Bullseye/Bookworm) - 64-bit de préférence.
  - Armbian (Debian-based, version stable la plus récente).
- **Prérequis :**
  - Une installation fraîche du système d'exploitation.
  - L'utilisateur de test doit avoir des droits `sudo`.
  - Accès Internet pour le téléchargement des dépendances.
  - Un BMCU-C (ou une carte de développement CH32V20x) pour les tests de flash physiques.

## 3. Matrice des Scénarios de Test

---

### Phase 1: Diagnostic et Dépendances (`verify_environment`)

| ID | Scénario | Prérequis | Action | Résultat Attendu |
|:---|:---|:---|:---|:---|
| **T1.1** | **Nominal - Dépendances présentes** | Toutes les dépendances (`sha256sum`, `stat`, `python3`, `make`, `curl`, `tar`) sont installées. | Lancer le script. | Le script passe l'étape 0 sans avertissement. |
| **T1.2** | **Dépendance obligatoire manquante** | Désinstaller `sha256sum` (`sudo apt remove coreutils`). | Lancer le script. | Le script affiche une erreur claire et s'arrête immédiatement. |
| **T1.3** | **Dépendance optionnelle manquante** | Désinstaller `python3`. | Lancer le script. | Affiche un avertissement mais continue. Le flash série doit échouer plus tard. |
| **T1.4** | **Permissions - Groupe `dialout` manquant** | L'utilisateur n'est pas dans le groupe `dialout`. | Lancer le script. | Affiche un avertissement sur les permissions série mais continue. |
| **T1.5** | **Permissions - Cache** | L'utilisateur est dans `dialout`. | Lancer le script une 1ère fois, puis une 2ème fois dans la foulée. | La 2ème exécution doit indiquer que la vérification est sautée grâce au cache. |
| **T1.6** | **wchisp - Installation automatique** | `wchisp` n'est pas installé dans le PATH. `curl` et `tar` sont présents. | Lancer le script et choisir la méthode `wchisp`. | Le script doit télécharger, extraire et utiliser `wchisp` depuis le cache local. |
| **T1.7** | **wchisp - Échec du téléchargement** | Bloquer l'accès à `github.com` (`/etc/hosts`). | Lancer le script et choisir `wchisp`. | Le script doit afficher une erreur de téléchargement claire et s'arrêter. |

---

### Phase 2: Sélection du Firmware (`prepare_firmware`)

| ID | Scénario | Prérequis | Action | Résultat Attendu |
|:---|:---|:---|:---|:---|
| **T2.1** | **Aucun firmware trouvé** | Supprimer le répertoire `.cache/klipper/out`. | Lancer le script. | Le script doit s'arrêter avec une erreur indiquant qu'aucun firmware n'a été trouvé et suggérer de lancer `build.sh`. |
| **T2.2** | **Firmware unique** | Un seul fichier `.bin` existe dans `.cache/klipper/out`. | Lancer le script. | Le script doit proposer ce firmware comme choix par défaut ou le présélectionner. |
| **T2.3** | **Firmwares multiples** | Créer plusieurs fichiers `.bin` et `.elf` dans le dossier de recherche. | Lancer le script. | Le menu de sélection doit lister tous les firmwares trouvés. La sélection par numéro doit fonctionner. |
| **T2.4**| **Sélection par chemin personnalisé** | - | Choisir "Saisir un chemin personnalisé" et entrer un chemin valide vers un firmware. | Le script accepte le chemin et affiche les bonnes informations (taille, SHA256). |
| **T2.5** | **Chemin personnalisé invalide** | - | Choisir "Saisir un chemin personnalisé" et entrer un chemin invalide. | Le script doit refuser le chemin, afficher une erreur, et redemander la sélection. |

---

### Phase 3: Méthodes de Flash et Gestion des Erreurs

| ID | Scénario | Prérequis | Action | Résultat Attendu |
|:---|:---|:---|:---|:---|
| **T3.1** | **`wchisp` - Nominal** | BMCU en mode bootloader. | Sélectionner la méthode `wchisp`. | La commande `wchisp flash` est exécutée. Le script doit afficher la sortie de la commande. |
| **T3.2** | **Série - Périphérique manquant** | Aucun périphérique USB/série n'est connecté. | Sélectionner la méthode série. | Le menu de sélection de port doit afficher "Aucun port série détecté". |
| **T3.3** | **Série - `flash_usb.py` manquant** | Renommer/supprimer `.cache/klipper/scripts/flash_usb.py`. | Sélectionner la méthode série et un port. | Le script doit s'arrêter avec une erreur claire indiquant que le script de flash Klipper est introuvable. |
| **T3.4** | **SD Card - Chemin de montage invalide** | - | Sélectionner la méthode SD Card et fournir un chemin inexistant ou sans droits d'écriture. | Le script doit refuser le chemin, afficher une erreur et redemander. |
| **T3.5** | **SD Card - Copie nominale** | Monter un périphérique de stockage (ex: clé USB). | Sélectionner la méthode SD Card et fournir le point de montage. | Le firmware est copié avec succès. Le script exécute `sync`. |
| **T3.6** | **Erreur - Rapport d'échec** | Provoquer une erreur (ex: `chmod -x .cache/klipper/out/klipper.bin`). | Essayer de flasher ce firmware. | Le script doit s'arrêter, et un `FAILURE_REPORT.txt` doit être créé dans les logs, contenant le contexte de l'erreur. |

---

### Phase 4: Gestion des Services Klipper

| ID | Scénario | Prérequis | Action | Résultat Attendu |
|:---|:---|:---|:---|:---|
| **T4.1** | **Services Actifs** | Simuler le service `klipper.service` (`sudo systemctl start ...`). | Lancer le script jusqu'à l'étape 4. | Le script doit détecter le service, demander son arrêt, puis l'arrêter. |
| **T4.2** | **Services Inactifs** | S'assurer que `klipper.service` est arrêté. | Lancer le script. | Le script doit indiquer qu'aucun service actif n'a été détecté. |
| **T4.3** | **Restauration des services après succès** | `klipper.service` actif au départ. | Mener une procédure de flash (simulée) à son terme. | Le script doit tenter de redémarrer `klipper.service` à la fin. |
| **T4.4** | **Restauration des services après échec** | `klipper.service` actif au départ. | Provoquer un échec après l'arrêt des services (étape 4). | Le script doit intercepter l'erreur et tenter de redémarrer le service avant de quitter. |

## 4. Procédure de Test et de Documentation

Pour chaque scénario de test listé ci-dessous :

1.  **Préparation :** Assurez-vous que l'environnement correspond aux prérequis du test.
2.  **Exécution :** Lancez le script `flash_automation.sh` et suivez les étapes définies dans le scénario.
3.  **Observation :** Notez attentivement le comportement du script.
4.  **Documentation :**
    - Si le test réussit, marquez-le comme **`[PASS]`**.
    - Si le test échoue, marquez-le comme **`[FAIL]`** et créez un rapport détaillé incluant :
      - Le nom du scénario.
      - Une description précise de l'erreur (comportement inattendu, message d'erreur).
      - Une copie complète du rapport d'échec généré (`FAILURE_REPORT.txt`).
      - Les 50 dernières lignes du fichier de log (`logs/flash_.../flash.log`).
      - Des informations sur l'environnement (version de l'OS, `uname -a`).

---

## 5. Conclusion

L'exécution rigoureuse de ce plan de test est essentielle pour garantir que le script `flash_automation.sh` soit non seulement fonctionnel, mais aussi résilient et simple d'utilisation pour la communauté. Chaque erreur identifiée et corrigée contribuera à une meilleure expérience utilisateur et à la stabilité du projet.
