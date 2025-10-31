# shellcheck shell=bash

if [[ -n "${FLASH_AUTOMATION_LIB_FIRMWARE_SH:-}" ]]; then
    return 0
fi
FLASH_AUTOMATION_LIB_FIRMWARE_SH=1

# Ce module regroupe les fonctions liées à la découverte et à la sélection
# du firmware. Il repose sur l'initialisation des variables globales
# effectuée par flash_automation.sh (chemins, couleurs, helpers UI).

run_find_firmware_files() {
    local search_dir="$1"
    local max_depth="${2:-}"
    local respect_excludes="${3:-true}"

    local -a find_cmd=(find "${search_dir}")
    if [[ -n "${max_depth}" ]]; then
        find_cmd+=(-maxdepth "${max_depth}")
    fi

    if [[ "${respect_excludes}" == "true" && ${#FIRMWARE_SCAN_EXCLUDES[@]} -gt 0 ]]; then
        find_cmd+=("(")
        local first_pattern=true
        for exclude in "${FIRMWARE_SCAN_EXCLUDES[@]}"; do
            local sanitized="${exclude%/}"
            [[ -n "${sanitized}" ]] || continue
            for pattern in "${sanitized}" "${sanitized}/*"; do
                if [[ "${first_pattern}" == "true" ]]; then
                    first_pattern=false
                else
                    find_cmd+=(-o)
                fi
                find_cmd+=(-path "${pattern}")
            done
        done
        find_cmd+=(")")
        find_cmd+=(-prune)
        find_cmd+=(-o)
    fi

    find_cmd+=(-type)
    find_cmd+=(f)

    local -a effective_include_exts=()
    if [[ ${#FIRMWARE_SCAN_EXTENSIONS[@]} -gt 0 ]]; then
        effective_include_exts=("${FIRMWARE_SCAN_EXTENSIONS[@]}")
    else
        effective_include_exts=("${DEFAULT_FIRMWARE_SCAN_EXTENSIONS[@]}")
    fi

    local -a effective_exclude_exts=()
    if [[ ${#FIRMWARE_SCAN_EXCLUDE_EXTENSIONS[@]} -gt 0 ]]; then
        effective_exclude_exts=("${FIRMWARE_SCAN_EXCLUDE_EXTENSIONS[@]}")
    else
        effective_exclude_exts=("${DEFAULT_FIRMWARE_EXCLUDE_EXTENSIONS[@]}")
    fi

    declare -A exclude_lookup=()
    local ext
    for ext in "${effective_exclude_exts[@]}"; do
        [[ -n "${ext}" ]] || continue
        exclude_lookup["${ext}"]=1
    done

    local -a filtered_include_exts=()
    for ext in "${effective_include_exts[@]}"; do
        [[ -n "${ext}" ]] || continue
        if [[ -n "${exclude_lookup["${ext}"]:-}" ]]; then
            continue
        fi
        filtered_include_exts+=("${ext}")
    done
    effective_include_exts=("${filtered_include_exts[@]}")

    if [[ ${#effective_include_exts[@]} -eq 0 ]]; then
        return 0
    fi

    declare -A include_lookup=()
    for ext in "${effective_include_exts[@]}"; do
        include_lookup["${ext}"]=1
    done

    for ext in "${effective_exclude_exts[@]}"; do
        [[ -n "${include_lookup["${ext}"]:-}" ]] && continue
        if [[ -n "${ext}" ]]; then
            find_cmd+=(!)
            find_cmd+=(-name "*.${ext}")
        fi
    done

    find_cmd+=("(")
    local first_include=true
    for ext in "${effective_include_exts[@]}"; do
        [[ -n "${ext}" ]] || continue
        if [[ "${first_include}" == "true" ]]; then
            first_include=false
        else
            find_cmd+=(-o)
        fi
        find_cmd+=(-name "*.${ext}")
    done
    find_cmd+=(")")
    find_cmd+=(-print0)

    "${find_cmd[@]}"
}

collect_firmware_candidates() {
    local -n firmware_candidates_ref=$1
    firmware_candidates_ref=()
    FIRMWARE_CANDIDATE_MTIMES=()
    FIRMWARE_CANDIDATE_TIMESTAMPS=()

    declare -A seen_paths=()
    local -a decorated=()

    add_candidate() {
        local path="$1"
        [[ -f "${path}" ]] || return
        if [[ -n "${seen_paths["${path}"]:-}" ]]; then
            return
        fi
        seen_paths["${path}"]=1
        local raw_mtime
        raw_mtime=$(get_file_mtime_epoch "${path}" 2>/dev/null) || raw_mtime=""
        local mtime="${raw_mtime:-0}"
        FIRMWARE_CANDIDATE_MTIMES["${path}"]="${mtime}"
        if [[ -n "${raw_mtime}" ]]; then
            FIRMWARE_CANDIDATE_TIMESTAMPS["${path}"]="$(format_epoch_for_display "${mtime}")"
        else
            FIRMWARE_CANDIDATE_TIMESTAMPS["${path}"]=""
        fi
        decorated+=("${mtime}"$'\t'"${path}")
    }

    if [[ -n "${FIRMWARE_DISPLAY_PATH}" ]]; then
        local resolved_hint
        resolved_hint="$(resolve_path_relative_to_flash_root "${FIRMWARE_DISPLAY_PATH}")"
        if [[ -d "${resolved_hint}" ]]; then
            while IFS= read -r -d '' file; do
                add_candidate "${file}"
            done < <(run_find_firmware_files "${resolved_hint}" 3 false 2>/dev/null)
        else
            add_candidate "${resolved_hint}"
        fi
    fi

    if [[ -n "${PRESELECTED_FIRMWARE_FILE}" ]]; then
        add_candidate "${PRESELECTED_FIRMWARE_FILE}"
    fi

    for rel_path in "${DEFAULT_FIRMWARE_RELATIVE_PATHS[@]}"; do
        local default_dir="${FLASH_ROOT}/${rel_path}"
        [[ -d "${default_dir}" ]] || continue
        while IFS= read -r -d '' file; do
            add_candidate "${file}"
        done < <(run_find_firmware_files "${default_dir}" 2 true 2>/dev/null)
    done

    if [[ "${DEEP_SCAN_ENABLED}" == "true" ]]; then
        local -a extra_search=("${FLASH_ROOT}")
        for dir in "${extra_search[@]}"; do
            [[ -d "${dir}" ]] || continue
            while IFS= read -r -d '' file; do
                add_candidate "${file}"
            done < <(run_find_firmware_files "${dir}" 4 true 2>/dev/null)
        done
    fi

    if [[ ${#decorated[@]} -gt 0 ]]; then
        mapfile -t decorated < <(printf '%s\n' "${decorated[@]}" | sort -t $'\t' -k1,1nr -k2,2)
        for entry in "${decorated[@]}"; do
            firmware_candidates_ref+=("${entry#*$'\t'}")
        done
    fi

    unset -f add_candidate 2>/dev/null || true
}

create_dry_run_stream_writer() {
    local fifo_path="$1"
    (
        while true; do
            printf 'flash_automation dry-run firmware stream\n'
            sleep 1
        done
    ) > "${fifo_path}" &
    DRY_RUN_STREAM_WRITER_PID=$!
}

use_dry_run_placeholder_firmware() {
    local placeholder_dir="${FLASH_ROOT}/.cache/firmware"
    mkdir -p "${placeholder_dir}"

    local mode="${DRY_RUN_ARTIFACT_MODE:-file}"
    case "${mode}" in
        fifo)
            if ! command -v mkfifo >/dev/null 2>&1; then
                warn "Mode flux simulé indisponible : mkfifo est absent. Utilisation d'un fichier factice."
                mode="file"
            fi
            ;;
        stream|pipe)
            mode="fifo"
            ;;
    esac

    if [[ "${mode}" == "fifo" ]]; then
        local fifo_path
        fifo_path="$(mktemp -u "${placeholder_dir}/klipper-stream-XXXXXX")"
        if ! mkfifo "${fifo_path}"; then
            warn "Impossible de créer un flux simulé (${fifo_path}). Utilisation d'un fichier factice."
            mode="file"
        else
            DRY_RUN_PLACEHOLDER_CREATED="true"
            DRY_RUN_PLACEHOLDER_PATH="${fifo_path}"
            FIRMWARE_FILE="${fifo_path}"
            FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
            FIRMWARE_FORMAT="stream"
            FIRMWARE_SELECTION_SOURCE="mode --dry-run (flux simulé)"
            FIRMWARE_METADATA_AVAILABLE="false"
            info "Mode --dry-run : aucun firmware détecté, flux simulé injecté (${FIRMWARE_DISPLAY_PATH})."
            create_dry_run_stream_writer "${fifo_path}"
            return
        fi
    fi

    local placeholder_file="${placeholder_dir}/klipper.bin"
    if [[ ! -f "${placeholder_file}" ]]; then
        : > "${placeholder_file}"
        DRY_RUN_PLACEHOLDER_CREATED="true"
    else
        DRY_RUN_PLACEHOLDER_CREATED="false"
    fi

    DRY_RUN_PLACEHOLDER_PATH="${placeholder_file}"
    FIRMWARE_FILE="${placeholder_file}"
    FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
    FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
    FIRMWARE_SELECTION_SOURCE="mode --dry-run (artefact simulé)"
    FIRMWARE_METADATA_AVAILABLE="true"
    info "Mode --dry-run : aucun firmware détecté, utilisation d'un artefact simulé (${FIRMWARE_DISPLAY_PATH})."
}

prompt_firmware_selection() {
    local -n candidates_ref=$1
    local choice=""
    local default_choice=""
    local default_display=""

    if (( ${#candidates_ref[@]} > 0 )); then
        default_choice="${candidates_ref[0]}"
        default_display="$(format_path_for_display "${default_choice}")"
    fi

    local -a hints=("Options : saisir un numéro, un chemin absolu/relatif, ou 'q' (quitter).")
    if [[ -n "${default_display}" ]]; then
        hints+=("Appuyer sur Entrée sélectionnera le firmware le plus récent.")
        note "Le firmware le plus récent est présélectionné : ${default_display}"
    fi
    info "$(IFS=" "; echo "${hints[*]}")"

    while true; do
        echo
        echo "Sélectionnez le firmware à utiliser :"
        local index=1
        for file in "${candidates_ref[@]}"; do
            local timestamp
            timestamp="$(get_candidate_timestamp_display "${file}")"
            local display
            display="$(format_path_for_display "${file}")"
            local is_default=""
            if [[ "${file}" == "${default_choice}" ]]; then
                is_default=" (défaut)"
            fi
            if [[ -n "${timestamp}" ]]; then
                printf "  [%d] %s (%s)%s\n" "${index}" "${display}" "${timestamp}" "${is_default}"
            else
                printf "  [%d] %s%s\n" "${index}" "${display}" "${is_default}"
            fi
            ((index++))
        done
        printf "  [q] Quitter et annuler la procédure\n"

        local prompt_hint="Entrée pour le choix par défaut"
        read -rp "Votre choix [q pour quitter] : " choice

        case "${choice}" in
            q|Q)
                info "Arrêt demandé par l'utilisateur lors de la sélection du firmware."
                exit 0
                ;;
            "")
                if [[ -n "${default_choice}" ]]; then
                    FIRMWARE_FILE="${default_choice}"
                    FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
                    FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
                    FIRMWARE_SELECTION_SOURCE="sélection par défaut"
                    break
                fi
                warn "Aucune sélection détectée. Veuillez choisir un firmware ou saisir 'q'."
                ;;
            *)
                if [[ "${choice}" =~ ^[0-9]+$ ]]; then
                    local idx=$((choice))
                    if (( idx >= 1 && idx <= ${#candidates_ref[@]} )); then
                        FIRMWARE_FILE="${candidates_ref[$((idx-1))]}"
                        FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
                        FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
                        FIRMWARE_SELECTION_SOURCE="sélection interactive"
                        break
                    fi
                fi

                local resolved="${choice}"
                if [[ "${resolved}" != /* ]]; then
                    resolved="$(resolve_path_relative_to_flash_root "${resolved}")"
                fi

                if [[ -f "${resolved}" ]]; then
                    FIRMWARE_FILE="${resolved}"
                    FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
                    FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
                    FIRMWARE_SELECTION_SOURCE="chemin personnalisé"
                    break
                fi

                error_msg "Firmware introuvable : ${choice}."
                ;;
        esac
    done
}

prepare_firmware() {
    let "CURRENT_STEP_NUMBER+=1"
    CURRENT_STEP="Étape ${CURRENT_STEP_NUMBER}/${TOTAL_STEPS}: Sélection du firmware"
    render_box "${CURRENT_STEP}"
    FIRMWARE_METADATA_AVAILABLE="true"
    local -a include_ext_display=()
    if [[ ${#FIRMWARE_SCAN_EXTENSIONS[@]} -gt 0 ]]; then
        include_ext_display=("${FIRMWARE_SCAN_EXTENSIONS[@]}")
    else
        include_ext_display=("${DEFAULT_FIRMWARE_SCAN_EXTENSIONS[@]}")
    fi
    local extension_display
    extension_display="$(format_extensions_for_display "${include_ext_display[@]}")"
    if [[ -z "${extension_display}" ]]; then
        extension_display="$(format_extensions_for_display "${DEFAULT_FIRMWARE_SCAN_EXTENSIONS[@]}")"
    fi
    info "Recherche des artefacts firmware (${extension_display})."

    local search_roots_display=""
    for rel_path in "${DEFAULT_FIRMWARE_RELATIVE_PATHS[@]}"; do
        if [[ -n "${search_roots_display}" ]]; then
            search_roots_display+=", "
        fi
        search_roots_display+="${rel_path}"
    done
    info "Répertoires analysés par défaut : ${search_roots_display}"

    if [[ "${DEEP_SCAN_ENABLED}" == "true" ]]; then
        local exclude_display=""
        if [[ ${#FIRMWARE_SCAN_EXCLUDES[@]} -gt 0 ]]; then
            for exclude in "${FIRMWARE_SCAN_EXCLUDES[@]}"; do
                local formatted
                formatted="$(format_path_for_display "${exclude}")"
                if [[ -n "${exclude_display}" ]]; then
                    exclude_display+=", "
                fi
                exclude_display+="${formatted}"
            done
        fi
        info "Mode --deep-scan actif : recherche étendue dans ${FLASH_ROOT}."
        if [[ -n "${exclude_display}" ]]; then
            info "Chemins ignorés : ${exclude_display}"
        fi
        local -a exclude_ext_display=()
        if [[ ${#FIRMWARE_SCAN_EXCLUDE_EXTENSIONS[@]} -gt 0 ]]; then
            exclude_ext_display=("${FIRMWARE_SCAN_EXCLUDE_EXTENSIONS[@]}")
        else
            exclude_ext_display=("${DEFAULT_FIRMWARE_EXCLUDE_EXTENSIONS[@]}")
        fi
        local exclude_ext_string
        exclude_ext_string="$(format_extensions_for_display "${exclude_ext_display[@]}")"
        if [[ -n "${exclude_ext_string}" ]]; then
            info "Extensions ignorées : ${exclude_ext_string}"
        fi
    else
        info "Utilisez --deep-scan pour élargir la recherche à l'ensemble du dépôt."
    fi

    local -a candidates=()
    if [[ -n "${PRESELECTED_FIRMWARE_FILE}" ]]; then
        if [[ -n "${FIRMWARE_SELECTION_SOURCE}" ]]; then
            info "Firmware imposé par ${FIRMWARE_SELECTION_SOURCE}."
        fi

        if [[ "${FIRMWARE_SELECTION_SOURCE}" == "option CLI (--firmware)" || "${AUTO_CONFIRM_MODE}" == "true" ]]; then
            FIRMWARE_FILE="${PRESELECTED_FIRMWARE_FILE}"
            FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
            FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
        else
            candidates+=("${PRESELECTED_FIRMWARE_FILE}")
        fi
    fi

    if [[ -z "${FIRMWARE_FILE}" ]]; then
        local -a discovered
        collect_firmware_candidates discovered

        if [[ -n "${FIRMWARE_PATTERN}" && ${#discovered[@]} -gt 0 ]]; then
            local -a filtered=()
            for file in "${discovered[@]}"; do
                local basename
                basename="$(basename "${file}")"
                if [[ "${basename}" == ${FIRMWARE_PATTERN} ]]; then
                    filtered+=("${file}")
                fi
            done
            if [[ ${#filtered[@]} -gt 0 ]]; then
                info "Motif --firmware-pattern appliqué (${FIRMWARE_PATTERN})."
                discovered=("${filtered[@]}")
            else
                warn "Aucun firmware ne correspond au motif '${FIRMWARE_PATTERN}'. Sélection sur la base du plus récent."
            fi
        fi

        if [[ ${#candidates[@]} -gt 0 ]]; then
            candidates+=("${discovered[@]}")
            dedupe_array_in_place candidates
        else
            candidates=("${discovered[@]}")
        fi

        if [[ ${#candidates[@]} -eq 0 ]]; then
            if [[ "${DRY_RUN_MODE}" == "true" ]]; then
                use_dry_run_placeholder_firmware
            else
                local message="Aucun firmware compatible détecté (recherché dans ${search_roots_display})."
                if [[ "${DEEP_SCAN_ENABLED}" != "true" ]]; then
                    message+=" Utilisez --deep-scan pour élargir la recherche."
                fi
                error_msg "${message} Lancer './build.sh' ou fournir KLIPPER_FIRMWARE_PATH."
                exit 1
            fi
        fi

        if [[ -z "${FIRMWARE_FILE}" ]]; then
            if [[ "${AUTO_CONFIRM_MODE}" == "true" ]]; then
                FIRMWARE_FILE="${candidates[0]}"
                FIRMWARE_DISPLAY_PATH="$(format_path_for_display "${FIRMWARE_FILE}")"
                FIRMWARE_FORMAT="${FIRMWARE_FILE##*.}"
                if [[ ${#candidates[@]} -le 1 ]]; then
                    info "Mode auto-confirm : sélection automatique du firmware ${FIRMWARE_DISPLAY_PATH}."
                else
                    if [[ -n "${FIRMWARE_PATTERN}" ]]; then
                        info "Mode auto-confirm : plusieurs correspondances au motif '${FIRMWARE_PATTERN}', utilisation du firmware le plus récent (${FIRMWARE_DISPLAY_PATH})."
                    else
                        info "Mode auto-confirm : plusieurs firmwares détectés, utilisation du plus récent (${FIRMWARE_DISPLAY_PATH})."
                    fi
                fi
            else
                prompt_firmware_selection candidates
            fi
        fi
    fi

    if [[ "${FIRMWARE_METADATA_AVAILABLE}" != "false" ]]; then
        spinner_start "Calcul du checksum SHA256..."
        FIRMWARE_SIZE=$(portable_stat "--printf=%s" "${FIRMWARE_FILE}")
        FIRMWARE_SHA=$(portable_sha256 "${FIRMWARE_FILE}")
        spinner_stop
        success "Firmware sélectionné : ${FIRMWARE_DISPLAY_PATH} (${FIRMWARE_FORMAT})"
        info "Taille : ${FIRMWARE_SIZE} octets"
        info "SHA256 : ${FIRMWARE_SHA}"
    else
        FIRMWARE_SIZE="N/A"
        FIRMWARE_SHA="N/A"
        success "Firmware sélectionné : ${FIRMWARE_DISPLAY_PATH} (${FIRMWARE_FORMAT})"
        info "Taille : non applicable (flux simulé)"
        info "SHA256 : non applicable (flux simulé)"
    fi
}
