# audit/audit_poc.py

import os
import sys
import pty
import subprocess
import datetime
import shutil
import platform
import select
import tty
import termios
import io

# --- Configuration ---
# Commande pour arrêter la session d'audit
EXIT_COMMAND = b"exit-audit"
# Nom du répertoire du projet à nettoyer
PROJECT_DIR_NAME = "BMCU_C-to-Klipper"

def run_command(command):
    """Exécute une commande shell et retourne sa sortie ou un message d'erreur."""
    try:
        result = subprocess.check_output(
            command,
            shell=True,
            text=True,
            stderr=subprocess.PIPE
        )
        return result.strip()
    except subprocess.CalledProcessError as e:
        return f"Erreur lors de l'exécution de '{command}':\\n{e.stderr.strip()}"
    except FileNotFoundError:
        return f"Erreur: La commande '{command.split()[0]}' n'a pas été trouvée."

def get_system_info():
    """
    Collecte les informations système et d'environnement.
    """
    info = []
    info.append("=" * 20 + " RAPPORT D'AUDIT DE SESSION " + "=" * 20)
    info.append(f"Début de la session: {datetime.datetime.now().isoformat()}")
    info.append(f"Système d'exploitation: {platform.platform()}")
    info.append(f"Architecture CPU: {platform.machine()}")
    info.append(f"Version de Python: {sys.version.replace(os.linesep, ' ')}")

    # --- Informations système étendues ---
    info.append("\n--- Informations CPU ---")
    info.append(run_command("lscpu"))

    info.append("\n--- Utilisation de la Mémoire ---")
    info.append(run_command("free -h"))

    info.append("\n--- Utilisation du Disque ---")
    info.append(run_command("df -h"))

    info.append("\n--- État du Dépôt Git ---")
    info.append(run_command("git status --short"))
    info.append(run_command("git log -n 1 --pretty=format:'%H (%an, %ar): %s'"))

    info.append("\n--- Arborescence du Projet ---")
    if shutil.which("tree"):
        info.append(run_command("tree -L 3 -a"))
    else:
        info.append("Commande 'tree' non trouvée. Utilisation de 'ls -laR' en alternative.")
        info.append(run_command("ls -laR"))

    # Collecte des paquets pip installés
    info.append("\n--- Paquets Pip Installés ---")
    info.append(run_command(f"{sys.executable} -m pip list --format=freeze"))

    # Collecte des variables d'environnement
    info.append("\n--- Variables d'Environnement ---")
    for key, value in sorted(os.environ.items()):
        info.append(f"{key}={value}")

    info.append("=" * 64)
    info.append("Début du journal de la session du terminal :\n")
    return "\n".join(info)

def start_audit():
    """
    Démarre une session de pseudo-terminal pour enregistrer les commandes et les sorties.
    """
    # Détermination des chemins
    try:
        project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        parent_path = os.path.abspath(os.path.join(project_path, '..'))

        # Vérification de sécurité pour le nettoyage
        if os.path.basename(project_path) != PROJECT_DIR_NAME:
            print(f"Erreur: Le script ne semble pas être dans le répertoire attendu '{PROJECT_DIR_NAME}'.", file=sys.stderr)
            print(f"Détecté : '{os.path.basename(project_path)}'. Annulation par sécurité.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Erreur lors de la détermination des chemins : {e}", file=sys.stderr)
        sys.exit(1)

    # Création du nom de fichier pour le rapport final
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"audit_report_{timestamp}.txt"
    final_log_path = os.path.join(parent_path, log_filename)

    # Sauvegarde des attributs du terminal pour les restaurer à la fin
    original_stdin_fd = sys.stdin.fileno()
    try:
        original_tty_attrs = termios.tcgetattr(original_stdin_fd)
    except termios.error:
        print("Avertissement: Impossible d'obtenir les attributs TTY. L'environnement n'est peut-être pas un terminal interactif.", file=sys.stderr)
        original_tty_attrs = None

    # Fork du processus pour créer un pseudo-terminal
    pid, master_fd = pty.fork()

    if pid == pty.CHILD:
        # Processus enfant : exécute un nouveau shell
        shell = os.environ.get("SHELL", "/bin/bash")
        print(f"Lancement du shell : {shell}")
        try:
            os.execvp(shell, [shell])
        except OSError as e:
            print(f"Erreur critique: Impossible de lancer le shell '{shell}': {e}", file=sys.stderr)
            os._exit(1) # Quitte le processus enfant en cas d'échec

    # Processus parent : lit et écrit les données du/vers le terminal et le log
    else:
        print("=" * 60)
        print("Session d'audit démarrée. Toute l'activité est enregistrée.")
        print(f"Tapez '{EXIT_COMMAND.decode()}' et appuyez sur Entrée pour arrêter.")
        print("=" * 60)

        # Passage du terminal en mode "raw" pour une transmission directe des entrées
        if original_tty_attrs:
            tty.setraw(original_stdin_fd)

        user_input_buffer = b''

        try:
            with open(final_log_path, "wb") as log_file:
                # Écriture des informations système initiales
                log_file.write(get_system_info().encode('utf-8', 'replace'))
                log_file.flush()

                while True:
                    # Attend une activité sur le master_fd (sortie du shell) ou stdin (entrée utilisateur)
                    try:
                        rlist, _, _ = select.select([master_fd, original_stdin_fd], [], [])
                    except (ValueError, InterruptedError):
                        break # Sortie propre si les descripteurs de fichiers sont fermés

                    # 1. Gérer la sortie du shell enfant
                    if master_fd in rlist:
                        try:
                            data = os.read(master_fd, 1024)
                            if not data:  # Le processus enfant s'est terminé
                                break

                            # Afficher sur le terminal de l'utilisateur et enregistrer
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                            log_file.write(data)
                            log_file.flush()
                        except OSError:
                            break # Le shell enfant est probablement mort

                    # 2. Gérer l'entrée de l'utilisateur
                    if original_stdin_fd in rlist:
                        user_input = os.read(original_stdin_fd, 1024)

                        # Transférer l'entrée au shell enfant
                        os.write(master_fd, user_input)

                        # Vérifier la commande de sortie
                        user_input_buffer += user_input
                        if EXIT_COMMAND in user_input_buffer:
                             # Cherche un retour à la ligne après la commande
                            if b'\\r' in user_input_buffer or b'\\n' in user_input_buffer:
                                print(f"\\r\\nCommande '{EXIT_COMMAND.decode()}' détectée. Arrêt de la session...\\r\\n")
                                break

                        # Garder le buffer propre
                        if len(user_input_buffer) > 256:
                            user_input_buffer = user_input_buffer[-256:]


        finally:
            # Nettoyage
            if original_tty_attrs:
                termios.tcsetattr(original_stdin_fd, termios.TCSADRAIN, original_tty_attrs)

            # S'assurer que le processus enfant est terminé
            if pid > 0:
                try:
                    os.kill(pid, 9)
                    os.waitpid(pid, 0)
                except OSError:
                    pass # Le processus a peut-être déjà terminé

            print(f"\nSession d'audit terminée.")
            print(f"Rapport sauvegardé dans : {final_log_path}")

            # Rendre le nettoyage optionnel
            while True:
                try:
                    answer = input(f"\\nSouhaitez-vous supprimer le répertoire du projet '{project_path}'? [oui/non]: ").lower()
                    if answer in ["oui", "o"]:
                        print("Suppression du répertoire du projet...")
                        shutil.rmtree(project_path)
                        print("Répertoire du projet supprimé avec succès.")
                        break
                    elif answer in ["non", "n"]:
                        print("Le nettoyage a été annulé. Le répertoire du projet est conservé.")
                        break
                    else:
                        print("Réponse non valide. Veuillez entrer 'oui' ou 'non'.")
                except EOFError:
                    # Gère le cas où le script est exécuté dans un contexte non interactif
                    print("\\nImpossible de lire l'entrée. Le nettoyage est annulé par défaut.")
                    break
                except Exception as e:
                    print(f"Une erreur est survenue lors de la tentative de nettoyage : {e}", file=sys.stderr)
                    break

if __name__ == "__main__":
    start_audit()
