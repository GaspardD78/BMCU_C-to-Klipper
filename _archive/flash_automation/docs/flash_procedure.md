# Procédure de Flashage Manuel du BMCU-C

Ce document détaille la procédure de flashage manuel du firmware Klipper sur la carte BMCU-C.

## Quand utiliser cette méthode ?

L'outil automatisé `bmcu_tool.py` est la méthode recommandée pour flasher votre carte. Cependant, cette procédure manuelle est nécessaire dans les cas suivants :

-   **Échec du flashage automatique :** Si l'outil `bmcu_tool.py` ne parvient pas à flasher la carte.
-   **Dé-blocage ("Unbricking") :** Si la carte ne répond plus et n'est plus détectée correctement.
-   **Anciennes versions matérielles :** Certaines versions plus anciennes du BMCU-C, notamment celles sans port USB-C dédié à la communication, peuvent nécessiter cette approche.

---

## ⚠️ Prérequis Essentiels

-   **Système d'exploitation :** Un ordinateur sous **Windows**. L'outil de flashage officiel (`WCHISPTool`) n'est disponible que pour cet OS.
-   **Logiciel :** [WCHISPTool](https://www.wch-ic.com/downloads/WCHISPTool_Setup_exe.html).
-   **Firmware :** Le fichier `klipper.bin` compilé. Vous pouvez l'obtenir en utilisant l'option "Compiler le firmware" de `bmcu_tool.py`. Le fichier se trouvera dans `flash_automation/.cache/klipper/out/klipper.bin`.

---

## Méthode 1 : Flashage via UART (pour les cartes sans USB-C ou en cas de blocage)

Cette méthode est la plus fiable, notamment pour récupérer une carte qui ne répond plus.

### Matériel requis

-   Un adaptateur USB vers Série/TTL (type CH340, FT232, etc.).
-   Des câbles Dupont pour la connexion.

### 1. Connexion matérielle

**🔥 ATTENTION : Ne connectez PAS le BMCU-C à l'imprimante pendant toute la durée de l'opération.**

1.  **Reliez l'adaptateur USB-Série à la carte BMCU-C** en suivant ce schéma :

| Port sur BMCU-C | Port sur l'adaptateur USB-Série |
| :-------------: | :-----------------------------: |
|       `R`       |               `TXD`             |
|       `T`       |               `RXD`             |
|       `+`       |               `3V3`             |
|       `-`       |               `GND`             |

2.  **Connectez l'adaptateur USB-Série à votre PC Windows.** Le port COM devrait être détecté automatiquement. Si ce n'est pas le cas, installez les pilotes de votre adaptateur (ex: CH340).

### 2. Configuration de WCHISPTool

1.  Lancez `WCHISPTool`.
2.  Configurez les paramètres comme suit :
    -   **Chip Model :** `CH32V203`
    -   **Download Type :** `SerialPort`
    -   **DI – Baud Rate :** `1M` (ou 1000000)
    -   **SerialPort :** Sélectionnez le port COM de votre adaptateur.
    -   **User File :** Cliquez sur "..." et sélectionnez votre fichier `klipper.bin`.

### 3. Déverrouillage de la Puce (Étape cruciale)

1.  **Maintenez le bouton `B` (Boot) enfoncé** sur la carte BMCU-C. Ne le relâchez pas.
2.  Tout en maintenant `B`, **appuyez brièvement une fois sur le bouton `R` (Reset)**.
3.  Toujours en maintenant `B`, cliquez sur le bouton **"Remove Protect"** dans WCHISPTool.
4.  Si l'opération réussit, un message "Unlocked" en rouge apparaîtra dans l'outil. Vous pouvez alors relâcher le bouton `B`.

> **Si ça échoue :** Vérifiez vos connexions. Parfois, inverser les fils TX et RX (`TX-TX`, `RX-RX`) peut fonctionner.

### 4. Flashage du Firmware

1.  Cliquez sur le bouton **"Download"** dans WCHISPTool.
2.  La barre de progression devrait avancer. Une fois terminé, un message de succès s'affichera.

### 5. Redémarrage

1.  Appuyez une fois sur le bouton `R` (Reset) de la carte.
2.  La LED rouge devrait s'allumer. Le flashage est terminé !

---

## Méthode 2 : Flashage via le port USB-C

Cette méthode s'applique aux versions plus récentes de la carte équipées d'un port USB-C pour la communication.

### 1. Connexion

1.  Connectez la carte BMCU-C à votre PC Windows via son port USB-C.

### 2. Configuration de WCHISPTool

1.  Lancez `WCHISPTool`.
2.  Configurez les paramètres comme suit :
    -   **Chip Model :** `CH32V203`
    -   **Download Type :** `SerialPort` (Oui, même en USB-C)
    -   **DI – Baud Rate :** `1M`
    -   **User File :** Sélectionnez votre fichier `klipper.bin`.
    -   **Cochez l'option "Serial Auto DI"**.

### 3. Séquence de flashage

Cette méthode est moins manuelle mais peut nécessiter plusieurs tentatives.

1.  Cliquez sur **"Remove Protect"**.
2.  Cliquez immédiatement après sur **"Download"**.
3.  Il est probable que des erreurs apparaissent lors du premier cycle. **Répétez la séquence "Remove Protect" -> "Download"** jusqu'à ce que le flashage réussisse (généralement au deuxième essai).

Une fois le firmware transféré avec succès, débranchez et rebranchez la carte pour la redémarrer.
