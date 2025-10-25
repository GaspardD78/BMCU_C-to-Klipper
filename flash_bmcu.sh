#!/bin/bash

# Script pour aider à la compilation et au flashage du firmware Klipper pour le BMCU-C
# Arrêt du script en cas d'erreur
set -e

# --- Couleurs pour les messages ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # Pas de couleur

echo -e "${GREEN}--- Script de flashage pour BMCU-C ---${NC}"

# --- Étape 1: Installation des dépendances ---
echo -e "\n${YELLOW}[ÉTAPE 1/5] Vérification des dépendances...${NC}"
PACKAGES="gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf wchisp"
NEEDS_INSTALL=false
for pkg in $PACKAGES; do
    if ! dpkg -s "$pkg" &> /dev/null; then
        echo "Le paquet '$pkg' est manquant."
        NEEDS_INSTALL=true
    fi
done

if [ "$NEEDS_INSTALL" = true ]; then
    echo "Installation des paquets manquants..."
    sudo apt-get update
    sudo apt-get install -y $PACKAGES
else
    echo "Toutes les dépendances sont déjà installées."
fi

# --- Étape 2: Configuration de Klipper ---
cd ~/klipper
echo -e "\n${YELLOW}[ÉTAPE 2/5] Configuration du firmware Klipper...${NC}"
echo "Nettoyage de l'ancienne configuration..."
make clean

echo -e "\n${YELLOW}L'interface de configuration va s'ouvrir. Configurez les options comme suit :${NC}"
echo "  - \`[*] Enable extra low-level configuration options\`"
echo "  - Micro-controller Architecture: RISC-V"
echo "  - Processor model: CH32V20x"
echo "  - Clock Reference: 8 MHz crystal"
echo "  - Communication interface: Serial (on USART1 PA10/PA9)"
echo "  - Baud rate: 250000"
echo -e "\n${YELLOW}Appuyez sur 'Q' puis 'Y' pour sauvegarder une fois terminé.${NC}"
read -p "Appuyez sur [Entrée] pour lancer 'make menuconfig'..."

make menuconfig

echo -e "${GREEN}Configuration sauvegardée !${NC}"

# --- Étape 3: Compilation ---
echo -e "\n${YELLOW}[ÉTAPE 3/5] Compilation du firmware...${NC}"
make
echo -e "${GREEN}Compilation terminée ! Le firmware se trouve dans ~/klipper/out/klipper.bin${NC}"

# --- Étape 4: Flashage ---
echo -e "\n${YELLOW}[ÉTAPE 4/5] Préparation au flashage... (ACTION MANUELLE REQUISE)${NC}"
echo "  1. Déconnectez le BMCU-C de votre ordinateur."
echo "  2. Maintenez le bouton 'BOOT' du BMCU-C enfoncé."
echo "  3. Tout en le maintenant, rebranchez le câble USB."
echo "  4. Relâchez le bouton 'BOOT'."
echo "Le BMCU-C est maintenant en mode bootloader."
read -p "Appuyez sur [Entrée] lorsque vous êtes prêt à flasher..."

make flash

echo -e "${GREEN}Flashage terminé avec succès !${NC}"

# --- Étape 5: Vérification finale ---
echo -e "\n${YELLOW}[ÉTAPE 5/5] Identification du MCU... (ACTION MANUELLE REQUISE)${NC}"
echo "  1. Débranchez et rebranchez le BMCU-C (cette fois, SANS appuyer sur BOOT)."
read -p "Appuyez sur [Entrée] une fois que c'est fait pour trouver l'ID du port série..."

echo "Recherche de l'ID du port série..."
sleep 2 # Laisse le temps au système de détecter le périphérique
ls -l /dev/serial/by-id/

echo -e "\n${GREEN}--- Procédure terminée ! ---${NC}"
echo "Vous devriez voir un nouvel appareil (ex: usb-Klipper_ch32...). Copiez son chemin complet."
echo "Ajoutez la section suivante à votre 'printer.cfg' :"
echo -e "${YELLOW}"
echo "[mcu bmcu]"
echo "serial: /dev/serial/by-id/VOTRE_ID_COPIE_ICI"
echo "restart_method: command"
echo -e "${NC}"
echo "N'oubliez pas de redémarrer Klipper après avoir modifié votre configuration."
