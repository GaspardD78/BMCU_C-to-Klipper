# Guide simplifié : Flasher un BMCU-C avec Klipper

<p align="center">
  <img src="assets/bmcu_logo.svg" alt="Logo BMCU-C to Klipper" width="220" />
</p>

Ce dépôt rassemble **tout le nécessaire pour transformer un BMCU-C en module Klipper**. Ce guide a été conçu pour un public **débutant, pressé et prudent** : chaque commande est prête à copier-coller, des vérifications automatiques sont prévues, et des solutions sont listées si quelque chose coince.

> 🛟 **En cas de doute** : exécutez exactement ce qui est indiqué et ne sautez pas les étapes de vérification.

---

## 🗺️ Vue d'ensemble

1. [Ce qu'il vous faut](#-ce-quil-vous-faut)
2. [Procédure guidée (bmcu_tool.py)](#-procédure-guidée-bmcu_toolpy)
3. [Et après le flash ?](#-et-après-le-flash-)
4. [Dépanner sans paniquer](#-dépanner-sans-paniquer)
5. [Contribuer & licence](#-contribuer--licence)

---

## 📦 Ce qu'il vous faut

### Matériel

- Un BMCU-C (avec son câble USB-C).
- Un PC ou un SBC sous Linux (Ubuntu 22.04+, Debian 12+, Raspberry Pi OS 64 bits...) avec accès administrateur.

### Logiciels

L'outil principal `bmcu_tool.py` peut installer la plupart des dépendances pour vous. Si vous préférez une installation manuelle, voici les paquets nécessaires pour un système Debian/Ubuntu :

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip make curl tar build-essential sshpass ipmitool
```

---

## 🤖 Procédure guidée (bmcu_tool.py)

L'outil `bmcu_tool.py` est le **point d'entrée unique** pour toutes les opérations. Il vous guide à travers un menu interactif.

### Lancement rapide

1.  **Clonez le dépôt et placez-vous à la racine :**
    ```bash
    git clone https://github.com/GaspardD78/BMCU_C-to-Klipper.git
    cd BMCU_C-to-Klipper
    ```

2.  **Préparez l'environnement Python (une seule fois) :**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r flash_automation/requirements.txt
    ```

3.  **Lancez l'outil principal (en tant que module) :**
    ```bash
    python3 -m flash_automation.bmcu_tool
    ```

### Utilisation du menu

Suivez simplement les options dans l'ordre :

1.  **Vérifier et installer les dépendances** : L'outil détecte votre système et vous propose d'installer les paquets manquants.
2.  **Compiler le firmware** : Prépare le firmware Klipper pour votre BMCU-C.
3.  **Flasher le firmware (assistant)** : Vous guide pour sélectionner le firmware et le port série, puis lance le flashage.

---

## ✅ Et après le flash ?

Intégrez le module avec Klipper :

1. Copiez `addon/bmcu.py` dans `klippy/extras/`.
2. Ajoutez la section suivante à votre `printer.cfg`, en adaptant le port série si nécessaire :

   ```ini
   [bmcu]
   serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
   baud: 1250000
   ```

3. Redémarrez Klipper.

La documentation complète d'intégration est disponible dans [`addon/docs/setup.md`](addon/docs/setup.md).

---

## 🆘 Dépanner sans paniquer

| Problème | Solution rapide |
| --- | --- |
| `python3` ou `git` introuvable | Reprenez la section [Logiciels](#-logiciels). |
| `Permission denied` sur le port série | `sudo usmod -aG dialout "$USER"` puis reconnectez-vous. |
| `bmcu_tool.py` ne se lance pas | Activez l'environnement virtuel (`source .venv/bin/activate`). |
| Le flash échoue | Vérifiez le câble USB et assurez-vous que le BMCU-C est bien alimenté. |

---

## 🧪 Tests automatisés

Le projet inclut une suite de tests pour garantir la qualité du code. Pour les lancer :

```bash
# Installez pytest
pip install pytest

# Lancez les tests
python3 -m pytest
```

---

## 🤝 Contribuer & licence

- Suivez la convention [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/).
- Lisez [AGENTS.md](AGENTS.md) avant toute modification importante.

Le projet est distribué sous licence **GPLv3** – voir [LICENSE](LICENSE).
