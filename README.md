# MatrixFlow : Flashez votre BMCU-C avec Klipper

<p align="center">
  <img src="assets/logo.png" alt="Logo Matrix_Flow" width="220" />
</p>

**MatrixFlow** est un workflow automatisé et scripté pour compiler et flasher le firmware [Klipper](https://www.klipper3d.org/) sur une carte **BMCU-C**. Conçu pour être robuste, simple et transparent, il vous guide à travers chaque étape, de la préparation de l'environnement au flashage final.

Ce projet se concentre exclusivement sur la méthode MatrixFlow, qui utilise une série de scripts Python non interactifs pour une automatisation complète et fiable.

---

## 🗺️ Vue d'ensemble

1.  [Principe de fonctionnement](#-principe-de-fonctionnement)
2.  [Prérequis](#-prérequis)
3.  [Installation et Utilisation](#-installation-et-utilisation)
4.  [Détail du Workflow](#-détail-du-workflow)
5.  [Dépannage](#-dépannage)
6.  [Licence](#-licence)

---

## ⚙️ Principe de fonctionnement

MatrixFlow est un ensemble de scripts Python qui s'exécutent séquentiellement. Chaque script a une seule responsabilité :

1.  **Préparer l'environnement** : Télécharge Klipper et la toolchain de compilation.
2.  **Compiler le firmware** : Applique les patchs nécessaires et compile Klipper pour la BMCU-C.
3.  **Flasher le firmware** : Téléverse le firmware compilé sur la carte.
4.  **Aider à la configuration** : Génère le bloc de configuration Klipper à ajouter à votre `printer.cfg`.

Cette approche modulaire rend le processus facile à comprendre, à déboguer et à maintenir.

---

## 📦 Prérequis

### Matériel

-   Une carte BMCU-C (avec son câble USB-C).
-   Un ordinateur ou un SBC (Single-Board Computer) sous Linux (par ex. Raspberry Pi, BTT CB1/Pi, etc.) avec un accès `sudo`. Les distributions basées sur Debian (Debian, Ubuntu, Armbian) sont recommandées.

### Logiciels

-   **git**
-   **python3**
-   **make**

Vous pouvez les installer sur un système Debian/Ubuntu avec la commande suivante :
```bash
sudo apt update && sudo apt install -y git python3 make
```

---

## 🚀 Installation et Utilisation

### Étape 1 : Cloner le dépôt

Clonez ce dépôt sur votre machine hôte Klipper (votre Raspberry Pi ou équivalent) :
```bash
git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
cd BMCU_C-to-Klipper
```

### Étape 2 : Lancer le workflow

Le workflow complet est géré par un seul script. Exécutez-le depuis la racine du projet :
```bash
python3 -m matrix_flow.run_workflow
```

Le script va maintenant exécuter les quatre étapes les unes après les autres. Suivez les instructions affichées à l'écran.

-   Le script va s'arrêter pour vous demander de mettre la carte en **mode bootloader** avant le flashage. Pour cela :
    1.  Débranchez la carte.
    2.  Maintenez le bouton `BOOT` appuyé.
    3.  Branchez la carte via USB-C.
    4.  Relâchez le bouton `BOOT`.

Une fois le flashage terminé, le script affichera le bloc de configuration à ajouter à votre `printer.cfg`.

---

## 🔬 Détail du Workflow

Le workflow est composé de quatre scripts principaux, situés dans le dossier `matrix_flow/`. Pour les utilisateurs avancés, il est possible de les exécuter individuellement.

| Script | Description |
| :--- | :--- |
| `step_01_environment.py` | **Prépare l'environnement.** Clone Klipper et télécharge la toolchain RISC-V dans un dossier `.cache/`. |
| `step_02_build.py` | **Compile le firmware.** Applique les patchs spécifiques au CH32V20X, configure Klipper et lance la compilation pour générer `klipper.bin`. |
| `step_03_flash.py` | **Flashe la carte.** Utilise l'outil `wchisp` pour téléverser `klipper.bin` sur la BMCU-C via USB. |
| `step_04_configure.py` | **Aide à la configuration.** Détecte le port série de la carte et génère le bloc `[mcu bmcu]` à ajouter à `printer.cfg`. |

Pour une documentation technique détaillée de chaque script, consultez le dossier [`matrix_flow/docs/`](./matrix_flow/docs/).

---

## 🆘 Dépannage

| Problème | Solution |
| :--- | :--- |
| **Commande `git`, `python3` ou `make` introuvable** | Assurez-vous d'avoir installé les [prérequis logiciels](#-prérequis). |
| **Échec du flashage (`wchisp` échoue)** | - Vérifiez que la carte est bien en **mode bootloader**.<br>- Assurez-vous que le câble USB est bien connecté et fonctionnel.<br>- Si le service Klipper est en cours, le script tente de l'arrêter. Si cela échoue, arrêtez Klipper manuellement (`sudo systemctl stop klipper`) avant de relancer. |
| **"Permission denied" sur le port série** | Votre utilisateur n'a pas les droits pour accéder aux ports série. Ajoutez-le au groupe `dialout` : `sudo usermod -aG dialout $USER`, puis déconnectez-vous et reconnectez-vous. |
| **Aucun port série détecté** | Après le flashage, la carte peut prendre quelques secondes à s'initialiser. Débranchez et rebranchez-la. Vous pouvez aussi trouver le port manuellement avec `ls /dev/serial/by-id/*` et l'ajouter dans la configuration. |

---

## 🤝 Licence

Ce projet est distribué sous licence **GPLv3**. Voir le fichier [LICENSE](./LICENSE) pour plus de détails.
