# Analyse Comparative : Firmware BMCU d'Origine vs Implémentation Klipper

Ce document synthétise les différences fondamentales entre le firmware d'origine du BMCU et l'implémentation actuelle du projet basée sur Klipper.

En résumé, les deux approches sont radicalement différentes, tant sur le plan philosophique que technique. Le projet d'origine fournit un firmware spécialisé pour une tâche unique (émuler un AMS), tandis que le projet local transforme la carte BMCU en un contrôleur Klipper standard et polyvalent, avec un processus de développement et de déploiement beaucoup plus robuste et automatisé.

### 1. Logique et Objectif du Firmware

*   **Firmware d'origine :** L'objectif est de créer un firmware "stand-alone" (autonome) qui **émule le comportement du système AMS Lite de Bambu Lab**. La carte BMCU se fait passer pour un AMS officiel, communiquant avec l'imprimante via le "Bambu Bus". Le code est spécifiquement écrit pour cette tâche.
*   **Implémentation du projet (Klipper) :** L'objectif est de **porter le firmware Klipper** sur la carte BMCU. Klipper est un firmware d'imprimante 3D complet. La carte ne se comporte plus comme un AMS, mais comme un microcontrôleur standard (MCU) que Klipper peut piloter. Cela la rend beaucoup plus polyvalente : elle pourrait, en théorie, contrôler des moteurs, des capteurs, ou d'autres périphériques d'une imprimante 3D, et pas seulement gérer des filaments.

### 2. Chaîne de Compilation (Toolchain & Build)

*   **Firmware d'origine :**
    *   **Outil :** Utilise **PlatformIO**, généralement intégré dans des éditeurs comme Visual Studio Code.
    *   **Principe :** PlatformIO gère automatiquement le téléchargement de la toolchain de compilation (le compilateur RISC-V), les bibliothèques et les dépendances. C'est une approche très accessible pour les développeurs, mais moins contrôlée.
*   **Implémentation du projet (Klipper) :**
    *   **Outil :** Utilise le système de build standard de Klipper, basé sur **`make`**.
    *   **Principe :** Le projet a une approche beaucoup plus rigoureuse et reproductible. Un script (`step_01_environment.py`) télécharge une version spécifique et bien définie de la **toolchain RISC-V**, ainsi qu'une version précise du code source de Klipper. Tout est contenu localement, garantissant que la compilation fonctionnera de la même manière partout.

### 3. Processus de Flashage (Déploiement du firmware)

*   **Firmware d'origine :**
    *   **Méthode :** Entièrement **manuelle**.
    *   **Matériel :** Nécessite un **adaptateur USB-série (CH340) externe** à connecter sur la carte.
    *   **Logiciel :** Utilise un **outil graphique spécifique (WCHISPTool, probablement pour Windows)**.
    *   **Procédure :** L'utilisateur doit mettre la carte en "mode bootloader" en **appuyant sur une séquence de boutons** avant de pouvoir lancer le flashage depuis le logiciel.
*   **Implémentation du projet (Klipper) :**
    *   **Méthode :** Entièrement **automatisée** via un script (`step_03_flash.py`).
    *   **Matériel :** Utilise la **connexion USB native** de la carte BMCU (pas besoin d'adaptateur externe).
    *   **Logiciel :** Utilise un outil en ligne de commande, **`wchisp`**, qui est intégré au projet.
    *   **Procédure :** Le script gère tout : il arrête le service Klipper pour libérer le port série, détecte le port, lance la commande de flashage, et redémarre le service. **Aucune intervention physique n'est requise**.

---

### 4. Analyse Approfondie de l'Architecture Logicielle

#### Firmware d'Origine : Approche Monolithique et "Stateful"

Le firmware d'origine est une application embarquée **monolithique**, où toute l'intelligence réside sur le microcontrôleur.

*   **Architecture applicative :**
    *   Le code est structuré en modules (contrôle moteur, communication, etc.) mais reste compilé en un seul exécutable.
    *   La logique est **réactive** : la boucle principale (`main.cpp`) attend passivement les commandes provenant du "Bambu Bus".
    *   L'ensemble de l'état du système (quel filament est chargé, sa couleur, son type) est stocké et maintenu par le firmware. Il sauvegarde même ces informations en mémoire flash pour les conserver après un redémarrage, ce qui le rend **"stateful"** (il a une mémoire).

*   **Contrôle Matériel :**
    *   Le code pilote le matériel à un niveau très bas ("bare-metal"), en configurant directement les registres du microcontrôleur pour les GPIO, les timers (PWM), et le port série (USART avec DMA et interruptions).
    *   Il implémente une **boucle de contrôle PID (Proportionnel-Intégral-Dérivé)** pour asservir la vitesse des moteurs, en se basant sur les données des encodeurs magnétiques AS5600. C'est une méthode de contrôle précise et robuste.

*   **Protocole de Communication :**
    *   Le firmware implémente le protocole propriétaire "Bambu Bus". Il analyse les paquets entrants, vérifie leur intégrité (CRC), et construit des réponses complexes pour se faire passer pour un AMS officiel.

#### Implémentation Klipper : Approche Client-Serveur et "Stateless"

L'implémentation Klipper adopte une architecture radicalement différente, qui sépare les responsabilités entre un hôte intelligent et un microcontrôleur simple.

*   **Architecture Client-Serveur :**
    *   **L'Hôte (Serveur) :** Un ordinateur (ex: Raspberry Pi) exécute le service Klipper (`klippy`), écrit en Python. C'est le **cerveau** : il contient toute la logique de haut niveau, lit le G-code, effectue les calculs complexes et connaît l'état de l'imprimante.
    *   **Le MCU (Client) :** La carte BMCU exécute un firmware minimaliste. C'est le **muscle** : il est "stupide" et ne fait qu'exécuter les ordres simples et précis que l'hôte lui envoie. Le firmware du MCU est **"stateless"** (sans état) : il ne stocke aucune information sur l'état global de la machine.

*   **Contrôle Matériel :**
    *   La logique complexe (comme le PID) n'est pas gérée par le MCU. C'est l'hôte Klipper qui, après avoir lu la configuration dans le fichier `printer.cfg`, calcule la séquence exacte d'événements (par exemple, "active le pas du moteur A à l'instant T").
    *   Le firmware sur la BMCU se contente de recevoir ces ordres ("faire un pas", "lire un capteur") et de les exécuter avec une synchronisation parfaite.

*   **Communication et Configuration :**
    *   La communication entre l'hôte et le MCU est un simple protocole de commandes/réponses de bas niveau.
    *   Toute la configuration et la logique applicative (par exemple, une macro pour charger un filament) sont définies sur l'hôte dans le fichier `printer.cfg`. Modifier le comportement de la machine se fait en éditant ce fichier texte, **sans jamais avoir à recompiler le firmware du MCU**.
