#!/bin/bash

# Script pour construire l'environnement de test Docker et lancer la suite de tests pytest.
#
# Ce script automatise les étapes suivantes :
# 1. Vérifie si Docker est installé et en cours d'exécution.
# 2. Construit l'image Docker 'bmcu-c-test-env' si elle n'existe pas déjà.
# 3. Lance un conteneur temporaire à partir de cette image.
# 4. Monte le répertoire du projet actuel dans le conteneur.
# 5. Installe les dépendances Python requises.
# 6. Exécute la suite de tests pytest.
# 7. Le conteneur est automatiquement supprimé après l'exécution des tests.

set -euo pipefail

# --- Variables de configuration ---
IMAGE_NAME="bmcu-c-test-env:latest"
PROJECT_ROOT=$(pwd)

# --- Fonctions utilitaires pour des logs clairs ---
info() {
    echo -e "\033[34m[INFO]\033[0m $1"
}

error() {
    echo -e "\033[31m[ERREUR]\033[0m $1" >&2
    exit 1
}

# --- Vérification des prérequis ---
if ! command -v docker &> /dev/null; then
    error "Docker n'est pas installé. Veuillez l'installer pour continuer."
fi

if ! docker info &> /dev/null; then
    error "Le démon Docker ne semble pas être en cours d'exécution. Veuillez le démarrer."
fi

# --- Exécution principale ---
info "Construction de l'image Docker '$IMAGE_NAME'..."
docker build -t "$IMAGE_NAME" .

info "Lancement de la suite de tests dans un conteneur Docker..."

# Exécute les tests dans un conteneur éphémère (--rm) qui sera supprimé automatiquement.
# Monte le répertoire courant (-v) pour que le code soit accessible à l'intérieur du conteneur.
docker run --rm \
    -v "${PROJECT_ROOT}:/app" \
    --workdir /app \
    "$IMAGE_NAME" \
    bash -c "
        set -e # Arrêter le script du conteneur en cas d'erreur
        echo '--- Installation des dépendances Python ---'
        python3 -m pip install --upgrade pip
        python3 -m pip install pytest
        python3 -m pip install -r flash_automation/requirements.txt
        echo '--- Lancement de Pytest ---'
        python3 -m pytest flash_automation/tests/ addon/tests/
    "

info "Tests terminés avec succès."
