# Plan de test avancé pour `flash_automation.sh`

## Objectifs
- Valider l'exécution du script `flash_automation.sh` sur Armbian et Raspberry Pi OS.
- Détecter les erreurs bloquantes liées aux dépendances, permissions, périphériques et chemins firmware.
- Documenter systématiquement les anomalies rencontrées (messages utilisateur, logs, rapports d'échec).

## Périmètre
Le plan couvre l'intégralité du flux `main` du script :
1. `verify_environment`
2. `prepare_firmware`
3. `select_flash_method`
4. `detect_klipper_services`
5. `prepare_target`
6. `stop_klipper_services`
7. `execute_flash`
8. `post_flash`

## Préparation de l'environnement
1. **Plateformes cibles**
   - Armbian Bookworm (kernel >= 6.1) sur SoC Allwinner/Rockchip.
   - Raspberry Pi OS Bookworm (kernel >= 6.6) sur Raspberry Pi 4/5.
2. **Utilisateur de test**
   - Créer un utilisateur `bmcu` appartenant ou non au groupe `dialout` selon le scénario.
   - Accorder un accès sudo pour la manipulation des services.
3. **Données nécessaires**
   - Firmware valide (`klipper.bin`) produit via `flash_automation/build.sh`.
   - Firmware factice (`dummy.bin`, `dummy.uf2`, `dummy.elf`) généré avec `dd if=/dev/zero of=dummy.bin bs=1 count=256` puis conversion en ELF/UF2 avec `objcopy`.
   - Carte SD formatée FAT32 montée sur `/media/bmcu/SDCARD`.
4. **Instrumentation**
   - Activer `set -x` en tête du script lors des essais de debugging.
   - Exporter `BASH_ENV` pour ajouter `trap 'echo "[DEBUG] $? $BASH_COMMAND" >&2' DEBUG` si besoin.
   - Configurer `journalctl -f -u klipper*` sur un terminal séparé pour suivre les services.

## Méthodologie générale
- Avant chaque essai : `rm -rf flash_automation/logs` et `rm -f ~/.cache/bmcu_permissions.json`.
- Lancer le script avec `./flash_automation/flash_automation.sh 2>&1 | tee ~/flash_automation_$(date +%s).log`.
- Après l'exécution, archiver :
  - `flash_automation/logs/flash_*/flash.log`
  - `flash_automation/logs/flash_*/FAILURE_REPORT.txt`
  - sortie standard capturée.
- Documenter :
  - Commande exécutée, variables d'environnement, état matériel.
  - Résultat attendu vs obtenu, message d'erreur, code de sortie.

## Matrice de scénarios
### 1. Dépendances et commandes externes
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| D1 | `sha256sum` absent | `sudo mv /usr/bin/sha256sum /usr/bin/sha256sum.bak` puis lancer le script | Arrêt immédiat dans `verify_environment` avec message d'erreur et `FAILURE_REPORT` généré. |
| D2 | `python3` absent | `sudo update-alternatives --remove python3 /usr/bin/python3` (ou masquer via PATH) | Avertissement (dépendance optionnelle) puis poursuite ; blocage plus tard si méthode `serial`. |
| D3 | `wchisp` absent + auto-install désactivé | `WCHISP_AUTO_INSTALL=false ./flash_automation.sh` | Message bloquant lors de la sélection `wchisp`, invitant à installer manuellement. |
| D4 | `curl` manquant | `sudo mv /usr/bin/curl /usr/bin/curl.bak` | Échec de `ensure_wchisp` avec sortie documentée. |
| D5 | `dfu-util` manquant | Masquer l'exécutable | `detect_dfu_devices` ignore DFU, aucun crash. |

### 2. Cache des permissions
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| P1 | Cache inexistant | Supprimer `~/.cache/bmcu_permissions.json` | Script vérifie l'appartenance groupe `dialout`. |
| P2 | Cache expiré | `echo '{"status":"ok","checked_at":"2000-01-01T00:00:00+00:00"}' > ~/.cache/bmcu_permissions.json` | Vérification relancée, cache invalidé. |
| P3 | Cache valide | Générer entrée actuelle | Message `Vérification des permissions sautée`. |
| P4 | Utilisateur hors groupe `dialout` | Retirer l'utilisateur du groupe | Avertissement + absence de mise à jour du cache. |

### 3. Découverte du firmware
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| F1 | Aucun fichier disponible | Vider `.cache/klipper/out` | Boucle de sélection jusqu'à saisie d'un chemin manuel ; vérifier message d'erreur. |
| F2 | Fichier inaccessible | `chmod 000 klipper.bin` | Échec lors de `stat`/lecture avec rapport d'échec. |
| F3 | Fichier `.elf` | Placer un ELF valide | `determine_firmware_format` doit reconnaître l'extension et poursuivre. |
| F4 | Chemin relatif personnalisé | Saisir `../other/firmware.bin` | Résolution via `resolve_path_relative_to_flash_root`. |
| F5 | Firmware > 16 Mo | Créer fichier volumineux | Vérifier message informatif sur la taille (pas de hard limit). |

### 4. Calcul hash et métadonnées
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| H1 | `sha256sum` invalide | Altérer le fichier pendant l'exécution (ouvrir second terminal et `truncate`) | Script doit échouer au recalcul ou lors de la copie. |
| H2 | `stat` renvoie erreur | Monter firmware sur FS read-only et retirer durant `stat` | Gestion de l'erreur via `handle_error`. |

### 5. Sélection de la méthode de flash
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| M1 | Option `wchisp` | Choisir `wchisp` sans appareil connecté | Message guidant vers bootloader, logs wchisp avec erreur de connexion. |
| M2 | Option `serial` | Brancher microcontrôleur via CDC | `flash_usb.py` doit se lancer ; en cas d'absence de script, erreur bloquante. |
| M3 | Option `sdcard` | Montage en lecture seule | Échec de la copie avec rapport. |
| M4 | Entrée invalide | Taper `foo` au prompt | Message `[ERROR] Sélection invalide`. |

### 6. Gestion des périphériques
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| G1 | Aucun périphérique | Débrancher l'appareil | `detect_serial_devices` renvoie vide, avertissement. |
| G2 | Multiples ports | Simuler via `socat` pour créer `pty` | Vérifier liste numérotée, sélection correcte. |
| G3 | Accès refusé | `sudo chown root:root /dev/ttyUSB0 && chmod 600` | Message `Permission refusée` lors de `check_device_write_access`. |
| G4 | DFU disponible | Connecter carte en mode DFU | Vérifier affichage `dfu-util -l`. |

### 7. Services Klipper
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| S1 | Services actifs | Démarrer `klipper.service` et `klipper-mcu.service` | Script doit les arrêter puis relancer en fin de procédure. |
| S2 | `systemctl` absent | Tester dans un conteneur sans systemd | Message informatif, pas de crash. |
| S3 | Échec d'arrêt | Simuler via `systemctl mask` | Journaliser un `warn` et poursuivre. |
| S4 | Interruption avant `post_flash` | Forcer un `CTRL+C` après arrêt des services | Vérifier `trap EXIT` redémarre les services. |

### 8. Méthode `wchisp`
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| W1 | Installation automatique | Supprimer `wchisp` du PATH et laisser `WCHISP_AUTO_INSTALL=true` | Téléchargement et extraction dans `.cache/tools/wchisp`. |
| W2 | Architecture non gérée | Forcer `uname -m` à valeur exotique via `setarch` | Message demandant installation manuelle. |
| W3 | Archive corrompue | Modifier l'archive téléchargée | Échec d'extraction avec message dédié. |
| W4 | Timeout bootloader | Débrancher avant flash | `wchisp` retourne code d'erreur capturé dans `FAILURE_REPORT`. |

### 9. Méthode `serial`
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| R1 | Script manquant | Supprimer `.cache/klipper/scripts/flash_usb.py` | Message d'erreur et arrêt. |
| R2 | Firmware incompatible | Utiliser firmware non flashable via USB | `flash_usb.py` renvoie erreur analysée. |
| R3 | Port invalide | Sélectionner `/dev/null` | Échec du script Python, vérifier logs. |

### 10. Méthode `sdcard`
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| SD1 | Chemin invalide | Entrer `/mnt/doesnotexist` | Message d'erreur et nouvelle saisie. |
| SD2 | Espace insuffisant | Monter tmpfs 1 Mo et copier firmware >1 Mo | Échec de `cp`, handle_error déclenché. |
| SD3 | Sync obligatoire | Vérifier que `sync` est appelé (observer `strace`). |

### 11. Robustesse générale
| ID | Contexte | Action | Résultat attendu |
|----|----------|--------|------------------|
| X1 | Interruption utilisateur | `CTRL+C` durant `ensure_wchisp` | `trap ERR` génère rapport et quitte proprement. |
| X2 | Variables d'environnement personnalisées | Définir `KLIPPER_FIRMWARE_PATH` sur chemin absolu/relatif | Priorisation respectée. |
| X3 | Exécution non interactive | `yes '' | ./flash_automation.sh` | Observer comportement des prompts (devrait échouer proprement). |
| X4 | Logs en lecture seule | `chmod 400 flash_automation/logs` | Détection d'erreur d'écriture log. |
| X5 | Banner manquant | Supprimer `banner.txt` | Aucun impact fonctionnel. |

## Critères de réussite
- Toutes les erreurs critiques produisent un `FAILURE_REPORT.txt` détaillé.
- Les messages utilisateurs sont localisés et compréhensibles.
- Les services arrêtés sont systématiquement relancés même en cas d'échec.
- Les dépendances manquantes sont signalées avant d'engager une action irréversible.

## Rapport
Pour chaque scénario :
1. **Identifiant** (ex. `D1`).
2. **Plateforme** (Armbian/Raspberry Pi OS + version).
3. **Contexte** (packages installés, état des services, connexion périphériques).
4. **Étapes exécutées** (commandes précises, valeurs saisies).
5. **Résultat** (succès/échec, extraits de log, code retour).
6. **Analyse** (comportement attendu vs observé, recommandations).

Centraliser les rapports dans `BMCU_C_to_Klipper_logs/flash_automation/<date>.md` et joindre les artefacts (`flash.log`, `FAILURE_REPORT.txt`, `journalctl`, captures `dmesg`).
