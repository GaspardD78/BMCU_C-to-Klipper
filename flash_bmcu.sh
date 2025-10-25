#!/bin/bash

# Script pour aider à la compilation et au flashage du firmware Klipper pour le BMCU-C
# Conception sécurisée : arrêt immédiat en cas d'erreur, de variable non définie ou d'échec dans un pipeline.
set -euo pipefail

# --- Constantes et couleurs ---
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # Pas de couleur

readonly LOG_FILE="/tmp/bmcu_flash.log"
readonly KLIPPER_DIR_DEFAULT="../klipper" # Emplacement attendu par rapport au script

# --- Fonctions de journalisation ---
log_info() { echo -e "${NC}$1${NC}"; }
log_success() { echo -e "${GREEN}$1${NC}"; }
log_warning() { echo -e "${YELLOW}$1${NC}"; }
log_error() { echo -e "${RED}$1${NC}" >&2; }
log_step() { echo -e "${CYAN}$1${NC}"; }

# --- Fonctions utilitaires ---
press_enter_to_continue() {
    read -p "Appuyez sur [Entrée] pour continuer..."
}

# --- Fonctions principales du script ---

check_os() {
    if ! grep -q -E "ID=debian|ID_LIKE=debian" /etc/os-release; then
        log_warning "Ce script est optimisé pour les systèmes Debian (Debian, Ubuntu, Raspberry Pi OS)."
        log_warning "La vérification des dépendances sera sautée. Assurez-vous d'avoir les paquets requis installés."
        press_enter_to_continue
        return 1 # Indique que les dépendances ne seront pas gérées
    fi
    return 0
}

check_dependencies() {
    log_info ""
    log_step "[ÉTAPE 1/5] Vérification des dépendances..."
    local packages="gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf wchisp"
    local missing_packages=""
    for pkg in $packages; do
        if ! dpkg -s "$pkg" &> /dev/null; then
            missing_packages+="$pkg "
        fi
    done

    if [ -n "$missing_packages" ]; then
        log_warning "Les paquets suivants sont manquants : $missing_packages"
        read -p "Voulez-vous les installer avec 'sudo apt-get install' ? (o/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Oo]$ ]]; then
            log_info "Mise à jour des listes de paquets... (les logs sont dans $LOG_FILE)"
            sudo apt-get update &>> "$LOG_FILE"
            log_info "Installation des paquets manquants..."
            sudo apt-get install -y $missing_packages &>> "$LOG_FILE"
            log_success "Dépendances installées."
        else
            log_error "Les dépendances sont nécessaires pour continuer. Abandon."
            exit 1
        fi
    else
        log_success "Toutes les dépendances sont déjà installées."
    fi
}

configure_klipper() {
    log_info ""
    log_step "[ÉTAPE 2/5] Configuration du firmware Klipper..."
    log_info "Nettoyage de l'ancienne configuration..."
    make clean &> "$LOG_FILE"

    log_warning "L'interface de configuration va s'ouvrir. Configurez les options comme suit :"
    log_info "  - [*] Enable extra low-level configuration options"
    log_info "  - Micro-controller Architecture: RISC-V"
    log_info "  - Processor model: CH32V20x"
    log_info "  - Clock Reference: 8 MHz crystal"
    log_info "  - Communication interface: Serial (on USART1 PA10/PA9)"
    log_info "  - Baud rate: 250000"
    log_warning "Appuyez sur 'Q' puis 'Y' pour sauvegarder une fois terminé."
    press_enter_to_continue

    make menuconfig
    log_success "Configuration sauvegardée !"
}

compile_firmware() {
    log_info ""
    log_step "[ÉTAPE 3/5] Compilation du firmware..."
    log_info "La compilation peut prendre un certain temps. Les détails sont dans $LOG_FILE"
    if make &> "$LOG_FILE"; then
        log_success "Compilation terminée ! Le firmware se trouve dans $(pwd)/out/klipper.bin"
    else
        log_error "La compilation a échoué. Voici les dernières lignes du log :"
        tail -n 20 "$LOG_FILE"
        exit 1
    fi
}

flash_firmware() {
    log_info ""
    log_step "[ÉTAPE 4/5] Préparation au flashage... (ACTION MANUELLE REQUISE)"
    log_warning "  1. Déconnectez le BMCU-C de votre ordinateur."
    log_warning "  2. Maintenez le bouton 'BOOT' du BMCU-C enfoncé."
    log_warning "  3. Tout en le maintenant, rebranchez le câble USB."
    log_warning "  4. Relâchez le bouton 'BOOT'."
    log_info "Le BMCU-C est maintenant en mode bootloader."
    press_enter_to_continue

    log_info "Recherche du port série du BMCU en mode bootloader..."
    local device_path
    # wch-isp est le nom usuel pour le bootloader du CH32
    device_path=$(find /dev/serial/by-id/ -name "*wch-isp*" 2>/dev/null || true)

    if [ -z "$device_path" ]; then
        log_warning "Détection automatique échouée."
        log_info "Veuillez trouver manuellement le chemin de votre appareil dans la liste ci-dessous (il contient souvent 'wch-isp') :"
        ls -l /dev/serial/by-id/
        read -p "Entrez le chemin complet du périphérique (ex: /dev/ttyACM0) : " device_path
        if [ ! -e "$device_path" ]; then
            log_error "Le chemin '$device_path' n'existe pas. Abandon."
            exit 1
        fi
    else
        log_success "Appareil trouvé automatiquement : $device_path"
    fi

    log_info "Lancement du flashage sur $device_path..."
    if make flash FLASH_DEVICE="$device_path" &>> "$LOG_FILE"; then
        log_success "Flashage terminé avec succès !"
    else
        log_error "Le flashage a échoué. Voici les dernières lignes du log :"
        tail -n 20 "$LOG_FILE"
        exit 1
    fi
}

final_check() {
    log_info ""
    log_step "[ÉTAPE 5/5] Identification du MCU... (ACTION MANUELLE REQUISE)"
    log_warning "  1. Débranchez et rebranchez le BMCU-C (cette fois, SANS appuyer sur BOOT)."
    press_enter_to_continue

    log_info "Recherche de l'ID du port série..."
    sleep 2 # Laisse le temps au système de détecter le périphérique

    local serial_ids
    serial_ids=$(ls -l /dev/serial/by-id/ | grep "Klipper_ch32" || true)

    if [ -z "$serial_ids" ]; then
        log_warning "Impossible de trouver automatiquement l'ID Klipper. Voici la liste des ports disponibles :"
        ls -l /dev/serial/by-id/
    else
        log_success "ID du port série trouvé :"
        echo "$serial_ids"
    fi

    log_info ""
    log_success "--- Procédure terminée ! ---"
    log_info "Vous devriez voir un nouvel appareil (ex: usb-Klipper_ch32...). Copiez son chemin complet."
    log_warning "Ajoutez la section suivante à votre 'printer.cfg' :"
    log_info "$(
        echo
        echo "[mcu bmcu]"
        echo "serial: /dev/serial/by-id/VOTRE_ID_COPIE_ICI"
        echo "restart_method: command"
    )"
    log_warning "N'oubliez pas de redémarrer Klipper après avoir modifié votre configuration."
}

# --- Fonction principale ---
main() {
    log_success "--- Script de flashage optimisé pour BMCU-C ---"
    rm -f "$LOG_FILE"

    if check_os; then
        check_dependencies
    fi

    local klipper_dir="$KLIPPER_DIR_DEFAULT"
    if [ ! -d "$klipper_dir" ]; then
        log_error "Le répertoire Klipper n'a pas été trouvé à l'emplacement attendu : ${klipper_dir}"
        log_error "Veuillez vous assurer que Klipper est cloné au même niveau que le répertoire de ce script."
        exit 1
    fi
    cd "$klipper_dir"
    log_info "Utilisation du répertoire Klipper : $(pwd)"

    configure_klipper
    compile_firmware
    flash_firmware
    final_check
}

# --- Exécution ---
trap 'log_error "Une erreur inattendue est survenue à la ligne $LINENO. Consultez les logs dans ${LOG_FILE} pour plus de détails."' ERR
main "$@"
