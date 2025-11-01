#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MatrixFlow - Module d'interface utilisateur (UI).

Ce module centralise les fonctions et les styles pour l'affichage
dans la console, garantissant une expérience utilisateur cohérente.
"""

import shutil
from pathlib import Path

# --- Définitions des couleurs ANSI ---
class AnsiColors:
    """Collection de codes de couleur ANSI pour le terminal."""
    PINK = "\033[95m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[1;97m"
    GREY = "\033[90m"
    RESET = "\033[0m"

# Cache pour le contenu du fichier bannière
_banner_content = None

def get_banner() -> str:
    """
    Charge la bannière depuis le fichier assets/banner.txt.
    Met en cache le contenu après la première lecture.
    """
    global _banner_content
    if _banner_content is None:
        try:
            banner_path = Path(__file__).parent.parent / "assets/banner.txt"
            _banner_content = banner_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            _banner_content = "MatrixFlow"
    return _banner_content

def print_banner():
    """Affiche la bannière MatrixFlow."""
    # Création d'un dictionnaire de couleurs à partir de la classe AnsiColors.
    # On utilise str.format() pour une substitution sécurisée, évitant eval().
    colors = {
        key: value
        for key, value in AnsiColors.__dict__.items()
        if not key.startswith("__")
    }
    banner = get_banner().format(**colors)
    print(banner)

def print_header(text: str):
    """Affiche un en-tête de section."""
    width = shutil.get_terminal_size((80, 20)).columns
    padding = (width - len(text) - 2) // 2
    print(f"\n{AnsiColors.CYAN}{'=' * padding} {AnsiColors.WHITE}{text.upper()} {AnsiColors.CYAN}{'=' * padding}{AnsiColors.RESET}")

def print_success(text: str):
    """Affiche un message de succès."""
    print(f"{AnsiColors.GREEN}✔ {text}{AnsiColors.RESET}")

def print_error(text: str):
    """Affiche un message d'erreur."""
    print(f"{AnsiColors.RED}✖ {text}{AnsiColors.RESET}", file=__import__("sys").stderr)

def print_warning(text: str):
    """Affiche un message d'avertissement."""
    print(f"{AnsiColors.YELLOW}⚠ {text}{AnsiColors.RESET}")

def print_info(text: str):
    """Affiche un message d'information."""
    print(f"{AnsiColors.BLUE}ℹ {text}{AnsiColors.RESET}")

def print_table(headers: list[str], data: list[list[str]]):
    """Affiche des données dans un tableau formaté."""
    # Calcul de la largeur de chaque colonne
    col_widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            if len(cell) > col_widths[i]:
                col_widths[i] = len(cell)

    # Ligne d'en-tête
    header_line = " | ".join(f"{AnsiColors.WHITE}{headers[i]:<{col_widths[i]}}{AnsiColors.RESET}" for i in range(len(headers)))
    separator = "-+-".join("-" * w for w in col_widths)
    print(header_line)
    print(separator)

    # Données
    for row in data:
        row_line = " | ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(row))
        print(row_line)

def ask_confirmation(prompt: str) -> bool:
    """Demande une confirmation (oui/non) à l'utilisateur."""
    while True:
        response = input(f"{AnsiColors.YELLOW}? {prompt} [O/n] {AnsiColors.RESET}").lower().strip()
        if response in ["o", "oui", ""]:
            return True
        if response in ["n", "non"]:
            return False
        print_error("Réponse invalide. Veuillez répondre par 'o' (oui) ou 'n' (non).")
