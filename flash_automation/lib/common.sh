#!/bin/bash
# Copyright (C) 2024 Gaspard Douté
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# Bibliothèque partagée pour les scripts flash_automation

set -euo pipefail

# Fonction pour vérifier si une commande existe
function command_exists() {
    local cmd="$1"
    if [[ "${cmd}" == */* ]]; then
        [[ -x "${cmd}" ]]
    else
        command -v "${cmd}" >/dev/null 2>&1
    fi
}
