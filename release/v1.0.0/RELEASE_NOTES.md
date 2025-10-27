# Notes de Version - v1.0.0

Ceci est la première version officielle du projet d'intégration du BMCU-C avec Klipper.

Cette version fournit les briques logicielles nécessaires pour flasher le firmware Klipper sur un BMCU-C et l'intégrer avec Happy Hare.

## Contenu de la Release

Cette version est distribuée en trois archives distinctes pour répondre à différents besoins :

### 1. `bmcu_addon_v1.0.0.zip`

Cette archive contient les fichiers nécessaires pour intégrer un BMCU-C déjà flashé avec Klipper dans votre configuration Happy Hare.

**Contenu :**
- `bmcu.py` : Le module Klipper `[extra]` à placer dans `klipper/klippy/extras/`.
- `bmcu_config.cfg` : Fichier de configuration d'exemple.
- `bmcu_macros.cfg` : Macros Klipper pour piloter le BMCU-C.

**Installation :**
Suivez les instructions de la section "Addon Python pour Klipper (Happy Hare)" du fichier `README.md`.

### 2. `manual_flash_v1.0.0.zip`

Cette archive contient les scripts et la configuration nécessaires pour compiler et flasher manuellement le firmware Klipper sur votre BMCU-C.

**Contenu :**
- `build.sh` : Script pour compiler le firmware Klipper.
- `flash.py` : Assistant interactif pour flasher le firmware.
- `flash_automation.sh` : Script de flashage bas niveau avec journalisation (pour utilisateurs avancés).
- `klipper.config` : Fichier de configuration Klipper pour le BMCU-C.

**Installation :**
Suivez la procédure décrite dans la section "Flashage du BMCU-C (firmware)" du `README.md`.

### 3. `auto_flash_v1.0.0.zip`

Cette archive est destinée aux utilisateurs avancés souhaitant automatiser le processus de flashage du firmware.

**Contenu :**
- `flashBMCUtoKlipper_automation.py` : Script Python pour l'automatisation du flash.
- `flash_automation.sh` : Script shell d'exemple utilisant le script Python ou exécutable en mode autonome.

**Utilisation :**
Consultez la section "Automatiser le flash" dans le `README.md` pour les détails sur les paramètres et l'utilisation.

## Prochaines Étapes

Le projet est encore au stade de preuve de concept. Les prochaines étapes se concentreront sur :
- La validation sur du matériel réel.
- L'amélioration de la documentation.
- L'ajout de tests automatisés.

Merci de votre intérêt pour ce projet ! N'hésitez pas à ouvrir une issue pour tout commentaire ou question.
