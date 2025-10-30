# Utiliser une image Debian stable, similaire à Armbian
FROM debian:bookworm-slim

# Empêcher les installations de paquets de poser des questions interactives
ENV DEBIAN_FRONTEND=noninteractive

# Mettre à jour les paquets et installer les dépendances système requises
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Essentiels pour la compilation et Python
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    git \
    # Le compilateur cross-platform pour le firmware Klipper sur le CH32V203
    gcc-riscv32-unknown-elf \
    # Dépendance système trouvée dans le workflow GitHub Actions existant
    expect \
    # Nettoyer le cache pour réduire la taille de l'image
    && rm -rf /var/lib/apt/lists/*

# Créer un répertoire de travail pour l'application
WORKDIR /app

# Commande par défaut (peut être surchargée par le script de lancement)
# Ici, nous affichons simplement les versions pour vérifier que tout est bien installé
CMD ["/bin/bash", "-c", "python3 --version && gcc-riscv32-unknown-elf --version"]
