# Outil d'Audit pour le POC BMCU_C-to-Klipper

Cet outil a pour but de faciliter le débogage et l'analyse lors de la phase de Preuve de Concept (POC) en enregistrant une session terminal complète, en collectant des informations sur l'environnement, et en assurant un nettoyage complet à la fin.

## Fonctionnalités

- **Enregistrement de session :** Capture toutes les commandes entrées et leurs sorties dans un pseudo-terminal.
- **Collecte d'informations :** Récupère en début de session des informations cruciales pour le débogage (OS, Python, paquets `pip`, variables d'environnement).
- **Nettoyage automatique :** À la fin de la session, le script sauvegarde le rapport d'audit en dehors du répertoire du projet, puis supprime entièrement ce dernier pour garantir un environnement propre pour les tests futurs.

## Utilisation

### 1. Lancement du script

Pour démarrer la session d'audit, placez-vous à la racine du projet `BMCU_C-to-Klipper` et exécutez la commande suivante :

```bash
python3 audit/audit_poc.py
```

Un message vous confirmera le début de l'enregistrement. Vous serez alors dans un nouveau shell interactif.

### 2. Déroulement de la session

Utilisez le terminal comme vous le feriez normalement pour effectuer vos tests, lancer des scripts, etc. Toutes vos actions seront enregistrées.

### 3. Arrêt de la session et nettoyage

Pour terminer la session, tapez la commande spéciale suivante et appuyez sur `Entrée` :

```bash
exit-audit
```

Le script effectuera les actions suivantes :
1.  Il arrêtera l'enregistrement.
2.  Il créera un fichier de rapport nommé `audit_report_YYYY-MM-DD_HH-MM-SS.txt` dans le répertoire parent (au même niveau que le dossier `BMCU_C-to-Klipper`).
3.  **Il supprimera définitivement le répertoire `BMCU_C-to-Klipper` et tout son contenu.**

Assurez-vous d'avoir sauvegardé toute information importante en dehors de ce répertoire avant de terminer la session.
