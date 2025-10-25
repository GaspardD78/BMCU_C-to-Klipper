# Procédure de flash du BMCU-C

Ce document détaille la procédure complète pour compiler et flasher le firmware Klipper sur le BMCU-C, y compris les indications disponibles pour les variantes dépourvues de bouton BOOT physique ou équipées uniquement d'un port USB-C.

## 1. Préparation

1. Vérifiez que vous disposez des prérequis logiciels suivants :
   - Une instance Klipper fonctionnelle avec accès SSH.
   - Une interface d'administration (Mainsail ou Fluidd).
   - Le module Happy Hare installé.
   - Les toolchains `gcc-riscv64-unknown-elf`, `picolibc-riscv64-unknown-elf` et l'outil de flash `wchisp` installés sur la machine qui exécutera le flash.
2. Récupérez ce dépôt ainsi que ses sous-modules :
   ```bash
   git clone --recurse-submodules https://github.com/GaspardD78/BMCU_C-to-Klipper.git
   cd BMCU_C-to-Klipper
   ```

## 2. Compilation du firmware

1. Lancez la construction du firmware Klipper pour le BMCU-C :
   ```bash
   ./firmware/build.sh
   ```
2. Le script prépare l'environnement de compilation et produit un binaire `klipper/out/klipper.bin` qui sera ensuite flashé sur le BMCU-C.

## 3. Mise en mode bootloader et flash

1. Démarrez le script de flash :
   ```bash
   ./firmware/flash.sh
   ```
2. Le script vérifie la présence du fichier `klipper.bin`, puis vous invite à placer manuellement le module en mode bootloader :
   1. Maintenez le bouton **BOOT0** enfoncé.
   2. Appuyez puis relâchez le bouton **RESET**.
   3. Relâchez le bouton **BOOT0**.
   4. Revenez dans le terminal et appuyez sur Entrée pour lancer `wchisp`.
3. L'utilitaire `wchisp` programme ensuite la puce avec la commande `wchisp -d 30 -c ch32v20x flash klipper/out/klipper.bin` et affiche un message de confirmation en fin d'opération.

## 4. Variantes sans bouton BOOT / connecteur USB-C

La documentation fournie à ce jour ne couvre que la séquence décrite ci-dessus, qui suppose la présence des boutons **BOOT0** et **RESET**. Pour les révisions dépourvues de bouton BOOT ou équipées uniquement d'un connecteur USB-C, il n'existe pas encore de procédure officielle.

- Il peut être nécessaire d'appliquer une méthode matérielle alternative (pontage du signal BOOT0 vers 3V3, utilisation de points de test sur le PCB ou d'un adaptateur USB-C vers UART/RS-485, etc.).
- Référez-vous aux instructions délivrées par votre vendeur ou la communauté BMCU-C pour ces variantes avant d'entamer le flash, afin de limiter tout risque matériel.

Ce document sera complété dès que des informations plus précises seront disponibles pour ces modèles.
