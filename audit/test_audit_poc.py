# audit/test_audit_poc.py

import unittest
from unittest.mock import patch, Mock
import subprocess
import platform
import sys
import os

# Ajoute le répertoire parent au path pour permettre l'import du module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from audit.audit_poc import get_system_info, run_command

class TestAuditPoc(unittest.TestCase):
    """
    Suite de tests pour le script d'audit.
    """

    @patch('audit.audit_poc.run_command')
    def test_get_system_info_structure(self, mock_run_command):
        """
        Vérifie que la fonction get_system_info retourne une chaîne de caractères
        contenant les sections attendues.
        """
        # Configuration du mock pour simuler la sortie des commandes externes
        mock_run_command.side_effect = [
            "Fake lscpu output",
            "Fake free -h output",
            "Fake df -h output",
            "M audit/audit_poc.py",
            "abcdef (John Doe, 1 day ago): feat: new feature",
            "package1==1.0.0\\npackage2==2.1.3"
        ]

        # Appel de la fonction à tester
        info_string = get_system_info()

        # Vérifications
        self.assertIsInstance(info_string, str)

        # Vérifie la présence des en-têtes et des sections clés
        self.assertIn("RAPPORT D'AUDIT DE SESSION", info_string)
        self.assertIn("Début de la session:", info_string)
        self.assertIn(f"Système d'exploitation: {platform.platform()}", info_string)
        self.assertIn(f"Version de Python:", info_string)
        self.assertIn("--- Informations CPU ---", info_string)
        self.assertIn("Fake lscpu output", info_string)
        self.assertIn("--- Utilisation de la Mémoire ---", info_string)
        self.assertIn("Fake free -h output", info_string)
        self.assertIn("--- Utilisation du Disque ---", info_string)
        self.assertIn("Fake df -h output", info_string)
        self.assertIn("--- État du Dépôt Git ---", info_string)
        self.assertIn("M audit/audit_poc.py", info_string)
        self.assertIn("abcdef (John Doe, 1 day ago): feat: new feature", info_string)
        self.assertIn("--- Paquets Pip Installés ---", info_string)
        self.assertIn("package1==1.0.0", info_string) # Vérifie le contenu mocké
        self.assertIn("--- Variables d'Environnement ---", info_string)

        # Vérifie la présence d'au moins une variable d'environnement (PATH est généralement défini)
        self.assertIn("PATH=", info_string)

    @patch('subprocess.check_output')
    def test_run_command_success(self, mock_check_output):
        """Vérifie que run_command retourne la sortie en cas de succès."""
        mock_check_output.return_value = "commande réussie"
        result = run_command("ls -l")
        self.assertEqual(result, "commande réussie")

    @patch('subprocess.check_output')
    def test_run_command_called_process_error(self, mock_check_output):
        """Vérifie que run_command gère une CalledProcessError."""
        error_stderr = "erreur de commande"
        mock_check_output.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="commande_invalide",
            stderr=error_stderr
        )
        result = run_command("commande_invalide")
        self.assertIn("Erreur lors de l'exécution", result)
        self.assertIn(error_stderr, result)

    @patch('subprocess.check_output')
    def test_run_command_file_not_found_error(self, mock_check_output):
        """Vérifie que run_command gère une FileNotFoundError."""
        mock_check_output.side_effect = FileNotFoundError
        result = run_command("commande_inexistante")
        self.assertIn("Erreur: La commande 'commande_inexistante' n'a pas été trouvée.", result)


if __name__ == '__main__':
    unittest.main()
