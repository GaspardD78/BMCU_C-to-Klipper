# audit/test_audit_poc.py

import unittest
from unittest.mock import patch, Mock
import subprocess
import platform
import sys
import os
import shutil

# Ajoute le répertoire parent au path pour permettre l'import du module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from audit.audit_poc import get_system_info, run_command

class TestAuditPoc(unittest.TestCase):
    """
    Suite de tests pour le script d'audit.
    """

    @patch('audit.audit_poc.run_command')
    @patch('shutil.which')
    def test_get_system_info_structure_with_tree(self, mock_which, mock_run_command):
        """
        Vérifie que la fonction get_system_info inclut l'arborescence des fichiers
        lorsque 'tree' est disponible.
        """
        # Simuler que 'tree' est trouvé
        mock_which.return_value = '/usr/bin/tree'

        # Configuration du mock pour simuler la sortie des commandes externes
        mock_run_command.side_effect = [
            "Fake lscpu output",
            "Fake free -h output",
            "Fake df -h output",
            "M audit/audit_poc.py",
            "abcdef (John Doe, 1 day ago): feat: new feature",
            "Fake tree output", # Sortie de la commande 'tree'
            "package1==1.0.0\\npackage2==2.1.3"
        ]

        # Appel de la fonction à tester
        info_string = get_system_info()

        # Vérifications
        self.assertIsInstance(info_string, str)
        self.assertIn("--- Arborescence du Projet ---", info_string)
        self.assertIn("Fake tree output", info_string)
        self.assertNotIn("Utilisation de 'ls -laR'", info_string) # Vérifie que ls n'est pas utilisé

        # Vérifie que 'tree' a été appelé
        mock_run_command.assert_any_call("tree -L 3 -a")

    @patch('audit.audit_poc.run_command')
    @patch('shutil.which')
    def test_get_system_info_structure_without_tree(self, mock_which, mock_run_command):
        """
        Vérifie que la fonction get_system_info utilise 'ls' lorsque 'tree'
        n'est pas disponible.
        """
        # Simuler que 'tree' n'est pas trouvé
        mock_which.return_value = None

        mock_run_command.side_effect = [
            "Fake lscpu output",
            "Fake free -h output",
            "Fake df -h output",
            "M audit/audit_poc.py",
            "abcdef (John Doe, 1 day ago): feat: new feature",
            "Fake ls -laR output", # Sortie de la commande 'ls'
            "package1==1.0.0\\npackage2==2.1.3"
        ]

        info_string = get_system_info()

        self.assertIn("--- Arborescence du Projet ---", info_string)
        self.assertIn("Commande 'tree' non trouvée.", info_string)
        self.assertIn("Fake ls -laR output", info_string)

        # Vérifie que 'ls -laR' a été appelé
        mock_run_command.assert_any_call("ls -laR")

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
