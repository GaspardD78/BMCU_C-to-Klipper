# Procédure de flash du BMCU-C

Ce document détaille la procédure complète pour compiler et flasher le firmware Klipper sur le BMCU-C, y compris les indications disponibles pour les variantes dépourvues de bouton BOOT physique ou équipées uniquement d'un port USB-C.

## 1. Préparation

1. Vérifiez que vous disposez des prérequis logiciels suivants :
   - Une instance Klipper fonctionnelle avec accès SSH.
   - Une interface d'administration (Mainsail ou Fluidd).
   - Le module Happy Hare installé.
  - Les toolchains `gcc-riscv32-unknown-elf`, `picolibc-riscv32-unknown-elf` et l'outil de flash `wchisp` installés sur la machine qui exécutera le flash. Le script `firmware/build.sh` peut télécharger automatiquement la toolchain RV32 officielle si nécessaire.
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

Certaines cartes BMCU-C récentes sont dépourvues de bouton **BOOT0** et **RESET** et ne proposent qu'un connecteur USB-C pour le flash. La procédure ci-dessous reprend les étapes recommandées pour utiliser l'outil graphique **WCHISPTool** depuis Windows :

1. **Lancez WCHISPTool.**
2. **Configurez les paramètres** comme suit :
   - *Chip Model* : `CH32V203`
   - *Download Type* : `Serial Port`
   - *DI – Baud Rate* : `1M`
   - *User File* : sélectionnez le firmware `klipper/out/klipper.bin` généré à l'étape précédente.
   - Cochez l'option **Serial Auto DI**.
3. **Enchaînez les actions dans l'ordre suivant** jusqu'à obtenir un flash réussi : `Remove Protect` → `Download` → `Remove Protect` → `Download`.
   - Il est normal que la première itération échoue ; le second passage aboutit généralement.
4. **Terminez le flash** en redémarrant la carte avec le bouton `R`. Une LED rouge sur la carte mère confirme que le firmware est chargé.

### Astuces de dépannage

- Maintenez le bouton **B** enfoncé pendant que vous cliquez sur **Download** si le flash refuse de démarrer.
- Essayez de réduire le débit à `115200` bauds en cas d'échec répété.
- Inversez les connexions **TX/RX** (TX↔TX, RX↔RX) selon la configuration de votre interface USB-C ↔ UART si nécessaire.

⚠️ Évitez de brancher ou débrancher la BMCU pendant que l'imprimante est sous tension. Pour les tests, suivez la séquence : éteindre l'imprimante, connecter la BMCU, allumer l'imprimante, vérifier la détection de l'AMS, éteindre l'imprimante, puis déconnecter la BMCU.

Ces indications complètent la méthode de flash automatique (`flash.sh`) et doivent être utilisées lorsque la mise en mode bootloader physique n'est pas possible.
