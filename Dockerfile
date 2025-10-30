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
    # Outils pour télécharger et extraire le toolchain
    wget \
    tar \
    # Dépendance système trouvée dans le workflow GitHub Actions existant
    expect \
    # Nettoyer le cache pour réduire la taille de l'image
    && rm -rf /var/lib/apt/lists/*

# Télécharger et installer le toolchain RISC-V pré-compilé
RUN wget https://github.com/stnolting/riscv-gcc-prebuilt/releases/download/rv32e-231223/riscv32-unknown-elf.gcc-13.2.0.picolibc-1.8.6.tar.gz -O /tmp/riscv-toolchain.tar.gz && \
    mkdir -p /opt/riscv-toolchain && \
    tar -xvf /tmp/riscv-toolchain.tar.gz -C /opt/riscv-toolchain --strip-components=1 && \
    rm /tmp/riscv-toolchain.tar.gz

# Ajouter le toolchain au PATH
ENV PATH="/opt/riscv-toolchain/bin:${PATH}"

# Créer un répertoire de travail pour l'application
WORKDIR /app

# Commande par défaut (peut être surchargée par le script de lancement)
# Ici, nous affichons simplement les versions pour vérifier que tout est bien installé
CMD ["/bin/bash", "-c", "python3 --version && riscv32-unknown-elf-gcc --version"]
