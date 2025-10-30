# audit/test_audit_poc.py

import unittest
from unittest.mock import patch, Mock
import subprocess
import platform
import sys
import os

# Ajoute le répertoire parent au path pour permettre l'import du module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from audit.audit_poc import get_system_info

class TestAuditPoc(unittest.TestCase):
    """
    Suite de tests pour le script d'audit.
    """

    @patch('subprocess.check_output')
    def test_get_system_info_structure(self, mock_check_output):
        """
        Vérifie que la fonction get_system_info retourne une chaîne de caractères
        contenant les sections attendues.
        """
        # Configuration du mock pour simuler la sortie de 'pip list'
        mock_check_output.return_value = "package1==1.0.0\\npackage2==2.1.3"

        # Appel de la fonction à tester
        info_string = get_system_info()

        # Vérifications
        self.assertIsInstance(info_string, str)

        # Vérifie la présence des en-têtes et des sections clés
        self.assertIn("RAPPORT D'AUDIT DE SESSION", info_string)
        self.assertIn("Début de la session:", info_string)
        self.assertIn(f"Système d'exploitation: {platform.platform()}", info_string)
        self.assertIn(f"Version de Python:", info_string)
        self.assertIn("--- Paquets Pip Installés ---", info_string)
        self.assertIn("package1==1.0.0", info_string) # Vérifie le contenu mocké
        self.assertIn("--- Variables d'Environnement ---", info_string)

        # Vérifie la présence d'au moins une variable d'environnement (PATH est généralement défini)
        self.assertIn("PATH=", info_string)

    @patch('subprocess.check_output')
    def test_get_system_info_pip_error(self, mock_check_output):
        """
        Vérifie que la fonction gère correctement une erreur lors de l'appel à pip.
        """
        # Configuration du mock pour simuler une erreur
        error_message = "pip command not found"
        mock_check_output.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd="pip list",
            stderr=error_message
        )

        # Appel de la fonction
        info_string = get_system_info()

        # Vérification
        self.assertIn("--- Erreur lors de la récupération des paquets pip ---", info_string)
        self.assertIn(error_message, info_string)
        # S'assure que les autres sections sont toujours présentes
        self.assertIn("RAPPORT D'AUDIT DE SESSION", info_string)
        self.assertIn("--- Variables d'Environnement ---", info_string)


if __name__ == '__main__':
    unittest.main()
