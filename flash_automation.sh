#!/bin/bash
#
# Script d'automatisation pour le flashage et la validation d'un firmware sur un BMCU.
#
# Auteur: Jules, Ingénieur DevOps & Embarqué
# Date: $(date "+%Y-%m-%d")

# ==============================================================================
# SECTION DE CONFIGURATION
# Modifiez ces variables pour correspondre à votre environnement.
# ==============================================================================
readonly BMCU_IP="192.168.1.100"
readonly BMCU_USER="root"
readonly BMCU_PASS="votre_mot_de_passe"
readonly FIRMWARE_PATH="./firmware/firmware_nouveau.bin" # Chemin vers le binaire à flasher

# Configuration des logs
readonly LOG_BASE_DIR="logs"
readonly LOG_DIR="${LOG_BASE_DIR}/flash_test_$(date +%Y-%m-%d_%H-%M-%S)"
readonly LOG_FILE="${LOG_DIR}/debug.log"

# Variable globale pour suivre l'étape en cours
CURRENT_STEP="Initialisation"

# ==============================================================================
# ROBUSTESSE DU SCRIPT (FAIL-FAST)
# -e: Quitte immédiatement si une commande retourne un code d'erreur non nul.
# -u: Traite les variables non définies comme une erreur.
# -o pipefail: Le code de retour d'un pipeline est celui de la dernière
#              commande qui a échoué.
# ==============================================================================
set -euo pipefail

# ==============================================================================
# GESTION DES ERREURS ET JOURNALISATION
# ==============================================================================

# Crée le répertoire de logs
mkdir -p "${LOG_DIR}"

# Fonction de journalisation
# Usage: log_message "NIVEAU" "Votre message"
function log_message() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    # Écrit dans le fichier de log
    echo "[$timestamp] [$level] - $message" >> "${LOG_FILE}"
}

# Fonction de gestion des erreurs, appelée par 'trap'
function handle_error() {
    local exit_code=$?
    local line_number=$1
    local command="$2"

    log_message "ERROR" "Échec critique à l'étape : '${CURRENT_STEP}'"
    log_message "ERROR" "Commande échouée : '$command' (ligne $line_number) avec le code de sortie $exit_code"

    echo "### ÉCHEC CRITIQUE ###"
    echo "Une erreur est survenue. Le script va s'arrêter."
    echo "Un rapport d'échec a été généré dans : ${LOG_DIR}/FAILURE_REPORT.txt"

    # Création du rapport d'échec
    {
        echo "Rapport d'échec - Test de flashage automatisé"
        echo "==============================================="
        echo "Date: $(date)"
        echo "Étape qui a échoué: ${CURRENT_STEP}"
        echo "Commande: ${command}"
        echo "Ligne: ${line_number}"
        echo "Code de sortie: ${exit_code}"
        echo ""
        echo "Contexte (50 dernières lignes du log):"
        echo "-----------------------------------------------"
        tail -n 50 "${LOG_FILE}"
    } > "${LOG_DIR}/FAILURE_REPORT.txt"

    exit $exit_code
}

# 'trap' intercepte le signal ERR (erreur) et appelle la fonction handle_error
# en lui passant le numéro de ligne et la commande qui a échoué.
trap 'handle_error $LINENO "$BASH_COMMAND"' ERR


# ==============================================================================
# ÉTAPE 0 : INITIALISATION ET NETTOYAGE
# ==============================================================================

function initialisation() {
    CURRENT_STEP="Étape 0: Initialisation"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Début du script d'automatisation."

    # Vérification des dépendances
    log_message "INFO" "Vérification des dépendances requises..."
    local dependencies=("sshpass" "scp" "ping")
    for cmd in "${dependencies[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_message "ERROR" "Dépendance manquante : '$cmd'. Veuillez l'installer."
            # L'erreur est fatale, 'trap' va s'activer mais on ajoute un exit pour la clarté.
            exit 1
        fi
    done
    log_message "INFO" "Toutes les dépendances sont présentes."

    # Vérification de l'existence du fichier firmware
    if [ ! -f "${FIRMWARE_PATH}" ]; then
        log_message "ERROR" "Le fichier firmware '${FIRMWARE_PATH}' n'a pas été trouvé."
        exit 1
    fi
    log_message "INFO" "Fichier firmware trouvé : ${FIRMWARE_PATH}"

    echo "Initialisation... OK"
}

# Lancement de l'initialisation
initialisation

log_message "INFO" "Le script continuera avec les autres étapes..."

# ==============================================================================
# ÉTAPE 1 : PRÉ-VÉRIFICATION
# Récupère la version actuelle du firmware avant le flashage.
# ==============================================================================

# Variable globale pour stocker la version du firmware avant flashage
FIRMWARE_VERSION_AVANT=""

function pre_verification() {
    CURRENT_STEP="Étape 1: Pré-vérification"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Récupération de la version actuelle du firmware..."

    # --- ACTION REQUISE ---
    # Adaptez la commande ci-dessous pour récupérer la version du firmware sur votre BMCU.
    # Exemple : "ipmitool raw 0x06 0x01" ou "cat /etc/os-release | grep VERSION_ID"
    local get_version_cmd="echo 'Version-Firmware-1.0.0'" # COMMANDE DE SUBSTITUTION

    FIRMWARE_VERSION_AVANT=$(sshpass -p "${BMCU_PASS}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${BMCU_USER}@${BMCU_IP}" "${get_version_cmd}")

    if [ -z "${FIRMWARE_VERSION_AVANT}" ]; then
        log_message "ERROR" "Impossible de récupérer la version du firmware. La réponse était vide."
        exit 1
    fi

    log_message "INFO" "Version du firmware détectée : ${FIRMWARE_VERSION_AVANT}"
    echo "Pré-vérification... OK"
}


# ==============================================================================
# ÉTAPE 2 : PRÉPARATION DU FLASHAGE
# Met le BMCU en mode maintenance et transfère le binaire.
# ==============================================================================

function prepare_flash() {
    CURRENT_STEP="Étape 2: Préparation du Flashage"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Mise du BMCU en mode maintenance..."

    # --- ACTION REQUISE ---
    # Adaptez la commande ci-dessous si votre BMCU nécessite une mise en mode maintenance.
    local maintenance_cmd="echo 'Mise en mode maintenance... OK'" # COMMANDE DE SUBSTITUTION
    sshpass -p "${BMCU_PASS}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${BMCU_USER}@${BMCU_IP}" "${maintenance_cmd}"

    log_message "INFO" "Transfert du fichier firmware vers le BMCU..."

    # On extrait juste le nom du fichier pour la destination
    local firmware_filename
    firmware_filename=$(basename "${FIRMWARE_PATH}")

    sshpass -p "${BMCU_PASS}" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${FIRMWARE_PATH}" "${BMCU_USER}@${BMCU_IP}:/tmp/${firmware_filename}"

    log_message "INFO" "Firmware transféré avec succès vers /tmp/${firmware_filename}"
    echo "Préparation du flashage... OK"
}


# ==============================================================================
# ÉTAPE 3 : EXÉCUTION DU FLASHAGE
# Lance la commande de flashage et capture toute la sortie.
# ==============================================================================

function execute_flash() {
    CURRENT_STEP="Étape 3: Exécution du Flashage"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Lancement de la commande de flashage principale."
    echo "Flashage... EN COURS (cette opération peut prendre plusieurs minutes)"

    # --- ACTION REQUISE ---
    # Adaptez la commande de flashage ci-dessous.
    # Assurez-vous qu'elle retourne un code de sortie non nul en cas d'échec.
    local firmware_filename
    firmware_filename=$(basename "${FIRMWARE_PATH}")
    local flash_cmd="socflash -s /tmp/${firmware_filename}" # COMMANDE DE SUBSTITUTION

    # Exécute la commande via SSH.
    # La syntaxe '&>>' redirige à la fois stdout et stderr vers le fichier de log.
    # Si la commande échoue, 'set -e' arrêtera le script et le 'trap' s'activera.
    sshpass -p "${BMCU_PASS}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${BMCU_USER}@${BMCU_IP}" "${flash_cmd}" &>> "${LOG_FILE}"

    log_message "INFO" "Commande de flashage terminée."
    echo "Flashage... OK"
}


# ==============================================================================
# ÉTAPE 4 : POST-VÉRIFICATION
# Attend le redémarrage du BMCU et valide la nouvelle version du firmware.
# ==============================================================================

function post_verification() {
    CURRENT_STEP="Étape 4: Post-vérification"
    echo "=== ${CURRENT_STEP} ==="
    log_message "INFO" "Le processus de flashage est terminé. Attente du redémarrage du BMCU."

    # Attente du redémarrage (ping)
    local max_wait_time=300 # 5 minutes
    local wait_interval=10  # secondes
    local elapsed_time=0

    echo "Attente du redémarrage du BMCU (max 5 minutes)..."
    while ! ping -c 1 -W 1 "${BMCU_IP}" &> /dev/null; do
        if [ $elapsed_time -ge $max_wait_time ]; then
            log_message "ERROR" "Le BMCU n'est pas revenu en ligne après ${max_wait_time} secondes."
            exit 1
        fi
        sleep $wait_interval
        elapsed_time=$((elapsed_time + wait_interval))
        echo -n "." # Indicateur de progression
    done
    echo "" # Saut de ligne après les points
    log_message "INFO" "Le BMCU est de nouveau en ligne."

    # Re-vérification de la version
    log_message "INFO" "Récupération de la nouvelle version du firmware..."

    # --- ACTION REQUISE ---
    # Assurez-vous que cette commande est identique à celle de l'étape 1.
    local get_version_cmd="echo 'Version-Firmware-2.0.0'" # COMMANDE DE SUBSTITUTION
    local firmware_version_apres
    firmware_version_apres=$(sshpass -p "${BMCU_PASS}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${BMCU_USER}@${BMCU_IP}" "${get_version_cmd}")

    if [ -z "${firmware_version_apres}" ]; then
        log_message "ERROR" "Impossible de récupérer la nouvelle version du firmware. La réponse était vide."
        exit 1
    fi
    log_message "INFO" "Nouvelle version du firmware détectée : ${firmware_version_apres}"

    # Comparaison des versions
    if [ "${FIRMWARE_VERSION_AVANT}" == "${firmware_version_apres}" ]; then
        log_message "ERROR" "La version du firmware n'a pas changé. Ancien: ${FIRMWARE_VERSION_AVANT}, Nouveau: ${firmware_version_apres}"
        exit 1
    fi

    log_message "INFO" "SUCCÈS : La version a été mise à jour de '${FIRMWARE_VERSION_AVANT}' à '${firmware_version_apres}'."
    echo "Post-vérification... OK"
}


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# FONCTION PRINCIPALE (MAIN)
# Orchestre l'exécution de toutes les étapes.
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

function main() {
    # L'initialisation est déjà appelée en dehors de main pour que le trap
    # soit actif le plus tôt possible.

    pre_verification
    prepare_flash
    execute_flash
    post_verification

    # Si nous arrivons ici, tout s'est bien passé.
    local end_message=">>> Le processus de flashage et de vérification s'est terminé avec SUCCÈS. <<<"
    log_message "INFO" "${end_message}"
    echo ""
    echo "${end_message}"
    echo "Le log complet est disponible ici : ${LOG_FILE}"
}

# Lance l'exécution principale du script
main
