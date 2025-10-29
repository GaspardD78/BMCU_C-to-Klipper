# shellcheck shell=bash

if [[ -n "${FLASH_AUTOMATION_LIB_WCHISP_SH:-}" ]]; then
    return 0
fi
FLASH_AUTOMATION_LIB_WCHISP_SH=1

readonly WCHISP_CACHE_DIR="${TOOLS_ROOT}/wchisp"
readonly WCHISP_RELEASE="${WCHISP_RELEASE:-v0.3.0}"
readonly WCHISP_AUTO_INSTALL="${WCHISP_AUTO_INSTALL:-true}"
readonly WCHISP_BASE_URL="${WCHISP_BASE_URL:-https://github.com/ch32-rs/wchisp/releases/download}"
readonly WCHISP_CHECKSUM_FILE="${FLASH_ROOT}/wchisp_sha256sums.txt"
readonly WCHISP_ARCH_OVERRIDE="${WCHISP_ARCH_OVERRIDE:-}"
readonly WCHISP_FALLBACK_ARCHIVE_URL="${WCHISP_FALLBACK_ARCHIVE_URL:-}"
readonly WCHISP_FALLBACK_CHECKSUM="${WCHISP_FALLBACK_CHECKSUM:-}"
readonly WCHISP_FALLBACK_ARCHIVE_NAME="${WCHISP_FALLBACK_ARCHIVE_NAME:-}"
readonly WCHISP_MANUAL_DOC="${FLASH_ROOT}/docs/wchisp_manual_install.md"

WCHISP_ARCHIVE_CHECKSUM_OVERRIDE_DEFAULT="${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE:-}"
ALLOW_UNVERIFIED_WCHISP_DEFAULT="${ALLOW_UNVERIFIED_WCHISP:-false}"
WCHISP_ARCHIVE_CHECKSUM_OVERRIDE=""
WCHISP_COMMAND="${WCHISP_BIN:-wchisp}"
readonly WCHISP_TRANSPORT="${WCHISP_TRANSPORT:-usb}"
readonly WCHISP_USB_INDEX="${WCHISP_USB_INDEX:-}"
readonly WCHISP_SERIAL_PORT="${WCHISP_SERIAL_PORT:-}"
readonly WCHISP_SERIAL_BAUDRATE="${WCHISP_SERIAL_BAUDRATE:-}"

detect_wchisp_machine() {
    if [[ -n "${WCHISP_ARCH_OVERRIDE}" ]]; then
        printf '%s\n' "${WCHISP_ARCH_OVERRIDE}"
        return
    fi

    uname -m
}

normalize_wchisp_machine() {
    local raw="$1"

    case "${raw}" in
        amd64)
            printf '%s\n' "x86_64"
            ;;
        arm64)
            printf '%s\n' "aarch64"
            ;;
        armv8l|armv7|armv7l|armhf)
            printf '%s\n' "armv7l"
            ;;
        armv6|armv6l|armel)
            printf '%s\n' "armv6l"
            ;;
        i386|i486|i586|i686)
            printf '%s\n' "i686"
            ;;
        *)
            printf '%s\n' "${raw}"
            ;;
    esac
}

wchisp_architecture_not_supported() {
    local arch="$1"

    log_message "ERROR" "Aucun binaire wchisp pré-compilé disponible pour ${arch}."
    cat <<EOF2 >&2
Aucun binaire wchisp pré-compilé n'est disponible pour l'architecture '${arch}'.
Vous pouvez :
  1. Compiler wchisp depuis les sources (voir ${WCHISP_MANUAL_DOC}).
  2. Fournir une archive compatible via WCHISP_FALLBACK_ARCHIVE_URL et, si possible, WCHISP_FALLBACK_CHECKSUM
     (ajoutez WCHISP_FALLBACK_ARCHIVE_NAME si l'URL comporte des paramètres).
  3. Exporter WCHISP_BIN vers un binaire wchisp déjà installé sur votre système.

Pour simuler une architecture différente (tests ou CI), exportez WCHISP_ARCH_OVERRIDE.
EOF2
    return 1
}

resolve_wchisp_download() {
    local raw_arch normalized_arch asset url mode checksum

    raw_arch="$(detect_wchisp_machine)"
    normalized_arch="$(normalize_wchisp_machine "${raw_arch}")"
    mode="official"
    checksum=""

    case "${normalized_arch}" in
        x86_64)
            asset="wchisp-${WCHISP_RELEASE}-linux-x64.tar.gz"
            url="${WCHISP_BASE_URL}/${WCHISP_RELEASE}/${asset}"
            ;;
        aarch64)
            asset="wchisp-${WCHISP_RELEASE}-linux-aarch64.tar.gz"
            url="${WCHISP_BASE_URL}/${WCHISP_RELEASE}/${asset}"
            ;;
        armv7l|armv6l|i686)
            if [[ -n "${WCHISP_FALLBACK_ARCHIVE_URL}" ]]; then
                asset="${WCHISP_FALLBACK_ARCHIVE_NAME:-${WCHISP_FALLBACK_ARCHIVE_URL##*/}}"
                asset="${asset%%\?*}"
                url="${WCHISP_FALLBACK_ARCHIVE_URL}"
                mode="fallback"
                checksum="${WCHISP_FALLBACK_CHECKSUM}"
                log_message "WARN" "Utilisation de l'archive de secours pour ${raw_arch} (${asset})."
            else
                wchisp_architecture_not_supported "${raw_arch}" || true
                return 1
            fi
            ;;
        *)
            if [[ -n "${WCHISP_FALLBACK_ARCHIVE_URL}" ]]; then
                asset="${WCHISP_FALLBACK_ARCHIVE_NAME:-${WCHISP_FALLBACK_ARCHIVE_URL##*/}}"
                asset="${asset%%\?*}"
                url="${WCHISP_FALLBACK_ARCHIVE_URL}"
                mode="fallback"
                checksum="${WCHISP_FALLBACK_CHECKSUM}"
                log_message "WARN" "Architecture ${raw_arch} non prise en charge officiellement; utilisation de l'archive de secours (${asset})."
            else
                wchisp_architecture_not_supported "${raw_arch}" || true
                return 1
            fi
            ;;
    esac

    if [[ -z "${asset}" ]]; then
        error_msg "Impossible de déterminer le nom de l'archive wchisp pour ${raw_arch}."
        printf "Définissez WCHISP_FALLBACK_ARCHIVE_URL avec une URL complète vers une archive wchisp valide.\n" >&2
        return 1
    fi

    printf '%s|%s|%s|%s|%s|%s\n' "${raw_arch}" "${normalized_arch}" "${asset}" "${url}" "${mode}" "${checksum}"
}

lookup_wchisp_checksum() {
    local asset="$1"

    if [[ ! -f "${WCHISP_CHECKSUM_FILE}" ]]; then
        error_msg "Fichier de sommes de contrôle wchisp introuvable (${WCHISP_CHECKSUM_FILE})."
        printf "Assurez-vous que le dépôt contient les sommes SHA-256 de wchisp avant de poursuivre.\n" >&2
        return 1
    fi

    local checksum
    checksum=$(awk -v target="${asset}" '
        /^[[:space:]]*#/ {next}
        NF >= 2 && $NF == target {print $1; exit}
    ' "${WCHISP_CHECKSUM_FILE}")

    if [[ -z "${checksum}" ]]; then
        error_msg "Somme de contrôle attendue introuvable pour ${asset}."
        printf "Mettez à jour %s avec l'empreinte SHA-256 officielle correspondant à cette archive.\n" "${WCHISP_CHECKSUM_FILE}" >&2
        return 1
    fi

    printf '%s\n' "${checksum}"
}

verify_wchisp_archive() {
    local asset="$1"
    local archive_path="$2"
    local expected="${3:-__auto__}"
    local degraded="${ALLOW_UNVERIFIED_WCHISP}"

    if [[ "${degraded}" == "true" ]]; then
        warn "Mode dégradé actif : la vérification SHA-256 de ${asset} sera tolérée en cas d'échec."
        log_message "WARN" "Mode dégradé actif pour ${asset} : les écarts de checksum seront ignorés."
    fi

    if [[ "${expected}" == "__auto__" ]]; then
        if ! expected=$(lookup_wchisp_checksum "${asset}"); then
            if [[ "${degraded}" == "true" ]]; then
                warn "Impossible de récupérer la somme de contrôle officielle pour ${asset}. Le mode dégradé permet de continuer."
                log_message "WARN" "Checksum officiel introuvable pour ${asset}, poursuite en mode dégradé."
                return 0
            fi
            return 1
        fi
    fi

    if [[ -n "${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}" ]]; then
        if [[ "${expected}" != "${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}" ]]; then
            warn "Somme de contrôle wchisp remplacée par la valeur fournie par l'utilisateur."
            log_message "WARN" "Checksum de ${asset} remplacé par l'override utilisateur."
        fi
        expected="${WCHISP_ARCHIVE_CHECKSUM_OVERRIDE}"
    fi

    if [[ -z "${expected}" ]]; then
        log_message "WARN" "Somme de contrôle inconnue pour ${asset}; vérification ignorée."
        echo "AVERTISSEMENT : aucune somme de contrôle n'est disponible pour ${asset}. Vérifiez manuellement l'origine de l'archive ou fournissez WCHISP_FALLBACK_CHECKSUM." >&2
        return 0
    fi

    local actual
    if ! actual=$(portable_sha256 "${archive_path}" 2>/dev/null); then
        error_msg "Impossible de calculer l'empreinte SHA-256 de ${archive_path}."
        printf "Vérifiez les permissions de lecture sur l'archive avant de relancer.\n" >&2
        return 1
    fi

    if [[ "${actual}" != "${expected}" ]]; then
        if [[ "${degraded}" == "true" ]]; then
            warn "Empreinte SHA-256 inattendue pour ${asset} (${actual}). L'archive est conservée car le mode dégradé est actif."
            log_message "WARN" "Checksum inattendu pour ${asset} (attendu=${expected}; obtenu=${actual}) mais conservation de l'archive (mode dégradé)."
            return 0
        fi
        rm -f "${archive_path}" || true
        error_msg "La vérification d'intégrité de l'archive ${asset} a échoué."
        printf "Empreinte attendue : %s\nEmpreinte calculée : %s\n" "${expected}" "${actual}" >&2
        printf "L'archive téléchargée a été supprimée. Relancez le script après avoir vérifié votre connexion ou la source du fichier.\n" >&2
        return 1
    fi

    log_message "INFO" "Somme de contrôle SHA-256 validée pour ${asset}."
}

ensure_wchisp() {
    if command_exists "${WCHISP_COMMAND}"; then
        return
    fi

    if [[ "${WCHISP_AUTO_INSTALL}" != "true" ]]; then
        log_message "ERROR" "wchisp est introuvable et l'installation automatique est désactivée."
        error_msg "La dépendance 'wchisp' est introuvable."
        error_msg "Exportez WCHISP_BIN ou activez WCHISP_AUTO_INSTALL=true pour autoriser le téléchargement automatique."
        exit 1
    fi

    if ! command_exists curl; then
        log_message "ERROR" "Impossible d'installer wchisp automatiquement: curl est absent."
        error_msg "curl est requis pour installer automatiquement wchisp. Installez curl ou wchisp manuellement."
        exit 1
    fi

    if ! command_exists tar; then
        log_message "ERROR" "Impossible d'installer wchisp automatiquement: tar est absent."
        error_msg "tar est requis pour installer automatiquement wchisp. Installez tar ou wchisp manuellement."
        exit 1
    fi

    local resolution
    if ! resolution=$(resolve_wchisp_download); then
        exit 1
    fi

    local arch_raw arch asset url checksum_mode checksum_value expected_checksum
    IFS='|' read -r arch_raw arch asset url checksum_mode checksum_value <<< "${resolution}"

    if [[ "${checksum_mode}" == "official" ]]; then
        if ! expected_checksum=$(lookup_wchisp_checksum "${asset}"); then
            exit 1
        fi
    else
        expected_checksum="${checksum_value}"
        if [[ -z "${expected_checksum}" ]]; then
            log_message "WARN" "Aucune somme de contrôle fournie pour l'archive de secours ${asset}."
        fi
    fi

    mkdir -p "${WCHISP_CACHE_DIR}"
    local archive_path="${WCHISP_CACHE_DIR}/${asset}"

    if [[ ! -f "${archive_path}" ]]; then
        log_message "INFO" "Téléchargement de wchisp (${url})."
        if ! curl --fail --location --progress-bar "${url}" -o "${archive_path}"; then
            rm -f "${archive_path}"
            log_message "ERROR" "Échec du téléchargement de wchisp depuis ${url}."
            error_msg "Échec du téléchargement de wchisp (${url}). Installez wchisp manuellement."
            exit 1
        fi
    else
        log_message "INFO" "Archive wchisp déjà présente (${archive_path})."
    fi

    ensure_portable_sha256_available

    if ! verify_wchisp_archive "${asset}" "${archive_path}" "${expected_checksum}"; then
        exit 1
    fi

    local install_dir="${WCHISP_CACHE_DIR}/${WCHISP_RELEASE}-${arch}"
    rm -rf "${install_dir}"
    mkdir -p "${install_dir}"

    log_message "INFO" "Extraction de wchisp dans ${install_dir}."
    if ! tar -xf "${archive_path}" --strip-components=1 -C "${install_dir}"; then
        rm -rf "${install_dir}"
        log_message "ERROR" "Échec de l'extraction de wchisp depuis ${archive_path}."
        error_msg "Impossible d'extraire wchisp. Vérifiez l'archive ou installez l'outil manuellement."
        exit 1
    fi

    local candidate="${install_dir}/wchisp"
    if [[ ! -x "${candidate}" ]]; then
        log_message "ERROR" "Le binaire wchisp est introuvable après extraction (${candidate})."
        error_msg "Le binaire wchisp est manquant après extraction. Installez l'outil manuellement."
        exit 1
    fi

    WCHISP_COMMAND="${candidate}"
    log_message "INFO" "wchisp disponible localement via ${WCHISP_COMMAND} (architecture détectée : ${arch_raw} -> ${arch})."
    success "wchisp installé automatiquement dans ${install_dir}."
}

flash_with_wchisp() {
    if [[ "${DRY_RUN_MODE}" == "true" ]]; then
        info "[DRY-RUN] wchisp flasherait ${FIRMWARE_DISPLAY_PATH}."
        return
    fi

    ensure_wchisp

    local transport="${WCHISP_TRANSPORT,,}"
    if [[ -z "${transport}" ]]; then
        transport="usb"
    fi

    info "Début du flash via ${WCHISP_COMMAND} (transport ${transport})."

    local cmd=("${WCHISP_COMMAND}")

    case "${transport}" in
        usb)
            cmd+=("--usb")
            if [[ -n "${WCHISP_USB_INDEX}" ]]; then
                if [[ "${WCHISP_USB_INDEX}" =~ ^[0-9]+$ ]]; then
                    cmd+=("--device" "${WCHISP_USB_INDEX}")
                else
                    warn "Valeur WCHISP_USB_INDEX invalide (${WCHISP_USB_INDEX}). Utilisation de la détection automatique."
                fi
            fi
            ;;
        serial)
            cmd+=("--serial")
            if [[ -n "${WCHISP_SERIAL_PORT}" ]]; then
                cmd+=("--port" "${WCHISP_SERIAL_PORT}")
            else
                error_msg "WCHISP_SERIAL_PORT doit être défini pour utiliser le transport série de wchisp."
                exit 1
            fi
            if [[ -n "${WCHISP_SERIAL_BAUDRATE}" ]]; then
                cmd+=("--baudrate" "${WCHISP_SERIAL_BAUDRATE}")
            fi
            ;;
        *)
            warn "Transport WCHISP_TRANSPORT=${WCHISP_TRANSPORT} non reconnu. Retour au mode USB."
            cmd+=("--usb")
            ;;
    esac

    cmd+=(flash "${FIRMWARE_FILE}")

    log_message "DEBUG" "Commande exécutée: ${cmd[*]}"
    "${cmd[@]}" 2>&1 | tee -a "${LOG_FILE}"
    success "wchisp a terminé le flash sans erreur."
}
