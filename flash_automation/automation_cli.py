#!/usr/bin/env python3
"""Interface d'automatisation inspirée de KIAUH pour le BMCU-C.

Ce script propose un menu interactif permettant de chaîner les scripts
existants de ce dépôt (compilation, flash local ou distant, etc.).
Chaque exécution génère un fichier de log horodaté dans ``logs/`` et se
termine par un tableau de synthèse des vérifications critiques afin de
faciliter le diagnostic.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from stat import S_IMODE
from typing import Any, Callable, Dict, Iterable, Optional

from stop_utils import StopController, StopRequested, cleanup_repository

FLASH_DIR = Path(__file__).resolve().parent
REPO_ROOT = FLASH_DIR.parent
LOGS_DIR = (REPO_ROOT / "logs").resolve()
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_PERMISSION_CACHE_FILE = Path(
    os.environ.get(
        "BMCU_PERMISSION_CACHE_FILE",
        Path.home() / ".cache" / "bmcu_permissions.json",
    )
)


def _get_permission_cache_ttl() -> int:
    value = os.environ.get("BMCU_PERMISSION_CACHE_TTL", "3600")
    try:
        ttl = int(value)
    except (TypeError, ValueError):
        return 0
    return max(ttl, 0)


@dataclass(frozen=True)
class PermissionCache:
    checked_at: datetime
    remaining_seconds: float
    status: str
    origin: Optional[str]
    raw: Dict[str, Any]


def _parse_timestamp(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _load_permission_cache(now: Optional[datetime] = None) -> Optional[PermissionCache]:
    ttl = _get_permission_cache_ttl()
    if ttl <= 0:
        return None
    if not _PERMISSION_CACHE_FILE.exists():
        return None
    try:
        raw = json.loads(_PERMISSION_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    status = raw.get("status")
    if status != "ok":
        return None

    checked_at_raw = raw.get("checked_at")
    if not isinstance(checked_at_raw, str):
        return None

    checked_at = _parse_timestamp(checked_at_raw)
    if checked_at is None:
        return None

    now = now or datetime.now(timezone.utc)
    age = (now - checked_at).total_seconds()
    if age < 0:
        age = 0
    if age >= ttl:
        return None

    remaining = float(ttl) - age
    origin = raw.get("origin")
    return PermissionCache(
        checked_at=checked_at,
        remaining_seconds=remaining,
        status=status,
        origin=origin if isinstance(origin, str) else None,
        raw=raw,
    )


def _format_duration(seconds: float) -> str:
    seconds_int = max(int(round(seconds)), 0)
    hours, rem = divmod(seconds_int, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _describe_cache(cache: PermissionCache) -> str:
    ttl = _get_permission_cache_ttl()
    age = float(ttl) - cache.remaining_seconds
    return (
        "cache valide (vérifié il y a "
        f"{_format_duration(age)}; expiration dans {_format_duration(cache.remaining_seconds)})"
    )


def _write_permission_cache(status: str, origin: str, payload: Dict[str, Any]) -> None:
    ttl = _get_permission_cache_ttl()
    if ttl <= 0:
        return
    now = datetime.now(timezone.utc)
    data: Dict[str, Any] = {
        "status": status,
        "checked_at": now.isoformat(),
        "origin": origin,
        "ttl_seconds": ttl,
    }
    data.update(payload)
    cache_dir = _PERMISSION_CACHE_FILE.parent
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    tmp_path = cache_dir / f"{_PERMISSION_CACHE_FILE.name}.tmp"
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(_PERMISSION_CACHE_FILE)
    except OSError:
        tmp_path.unlink(missing_ok=True)


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_requirements_hash(path: Path) -> Optional[str]:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return content or None


def _update_lock_file(context: "AutomationContext", lock_file: Path) -> None:
    quoted_python = shlex.quote(str(sys.executable))
    quoted_lock = shlex.quote(str(lock_file))
    context.run_command(
        [
            "/bin/sh",
            "-c",
            f"{quoted_python} -m pip freeze > {quoted_lock}",
        ],
        cwd=FLASH_DIR,
        description="Verrouillage des dépendances (pip freeze)",
    )


class AutomationError(RuntimeError):
    """Erreur générique pour les opérations d'automatisation."""


@dataclass(frozen=True)
class MenuAction:
    """Représente une action disponible dans le menu interactif."""

    key: str
    label: str
    handler: Callable[["AutomationContext"], None]
    report_key: Optional[str] = None


@dataclass
class ReportEntry:
    """État d'une vérification clé pour la synthèse de fin d'exécution."""

    key: str
    label: str
    status: str = "pending"
    details: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "details": self.details or None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AutomationReport:
    """Gestion centralisée des vérifications affichées en synthèse."""

    STATUS_LABELS = {
        "pending": "EN ATTENTE",
        "running": "EN COURS",
        "ok": "OK",
        "warning": "AVERTISSEMENT",
        "error": "ÉCHEC",
        "skipped": "IGNORÉ",
    }

    STATUS_ICONS = {
        "pending": "…",
        "running": "…",
        "ok": "✔",
        "warning": "⚠",
        "error": "✖",
        "skipped": "⏭",
    }

    STATUS_COLORS = {
        "pending": "\033[90m",
        "running": "\033[96m",
        "ok": "\033[92m",
        "warning": "\033[93m",
        "error": "\033[91m",
        "skipped": "\033[94m",
    }

    RESET_COLOR = "\033[0m"

    def __init__(self) -> None:
        self._entries: Dict[str, ReportEntry] = {
            "permissions": ReportEntry(key="permissions", label="Permissions des scripts"),
            "dependencies": ReportEntry(key="dependencies", label="Dépendances Python"),
            "compile": ReportEntry(key="compile", label="Compilation du firmware"),
        }
        self._order = ["permissions", "dependencies", "compile"]
        self.created_at = datetime.now(timezone.utc)

    def mark_running(self, key: str) -> None:
        entry = self._entries.get(key)
        if not entry:
            return
        entry.status = "running"
        entry.started_at = datetime.now(timezone.utc)
        entry.completed_at = None

    def update(self, key: str, status: str, details: str | None = None) -> None:
        entry = self._entries.get(key)
        if not entry:
            return
        entry.status = status
        if details is not None:
            entry.details = details
        entry.completed_at = datetime.now(timezone.utc)

    def mark_error(self, key: str, message: str) -> None:
        entry = self._entries.get(key)
        if not entry:
            return
        entry.status = "error"
        entry.details = message
        entry.completed_at = datetime.now(timezone.utc)

    def finalize_success(self, key: str, default_message: Optional[str] = None) -> None:
        entry = self._entries.get(key)
        if not entry:
            return
        if entry.status in {"pending", "running"}:
            entry.status = "ok"
            if default_message is not None:
                entry.details = default_message
            entry.completed_at = datetime.now(timezone.utc)

    @staticmethod
    def _supports_color() -> bool:
        return sys.stdout.isatty()

    @classmethod
    def _format_status(cls, status: str, width: int, enable_color: bool) -> str:
        label = cls.STATUS_LABELS.get(status, status.upper())
        icon = cls.STATUS_ICONS.get(status, "")
        text = f"{icon} {label}".strip()
        padded = text.ljust(width)
        if enable_color:
            color = cls.STATUS_COLORS.get(status)
            if color:
                return f"{color}{padded}{cls.RESET_COLOR}"
        return padded

    def render_console_table(self, *, enable_color: Optional[bool] = None) -> str:
        entries = [self._entries[key] for key in self._order]
        enable_color = self._supports_color() if enable_color is None else enable_color

        headers = ("Vérification", "Statut", "Détails")
        raw_status_texts = [
            f"{self.STATUS_ICONS.get(entry.status, '')} {self.STATUS_LABELS.get(entry.status, entry.status.upper())}".strip()
            for entry in entries
        ]
        col_widths = [
            max(len(headers[0]), max((len(entry.label) for entry in entries), default=0)),
            max(len(headers[1]), max((len(text) for text in raw_status_texts), default=0)),
            max(len(headers[2]), max((len(entry.details) if entry.details else 1 for entry in entries), default=0)),
        ]

        separator = "+-" + "-+-".join("-" * width for width in col_widths) + "-+"
        lines = [separator]
        header_line = "| " + " | ".join(
            header.ljust(width) for header, width in zip(headers, col_widths)
        ) + " |"
        lines.append(header_line)
        lines.append(separator)

        for entry in entries:
            status_cell = self._format_status(entry.status, col_widths[1], enable_color)
            detail_text = (entry.details or "-").ljust(col_widths[2])
            line = "| " + " | ".join(
                [
                    entry.label.ljust(col_widths[0]),
                    status_cell,
                    detail_text,
                ]
            ) + " |"
            lines.append(line)

        lines.append(separator)
        return "\n".join(lines)

    def to_json(self, *, log_file: Path) -> Dict[str, Any]:
        return {
            "generated_at": self.created_at.isoformat(),
            "log_file": str(log_file),
            "checks": [self._entries[key].to_dict() for key in self._order],
        }

    def export_json(self, destination: Path, *, log_file: Path) -> None:
        payload = self.to_json(log_file=log_file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class AutomationContext:
    """État partagé entre les actions."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        stop_controller: StopController,
        log_dir: Path,
        log_file: Path,
        report: Optional[AutomationReport] = None,
    ):
        self.dry_run = dry_run
        self.stop_controller = stop_controller
        self.log_dir = log_dir
        self.log_file = log_file
        self.report = report or AutomationReport()
        self.logger = logging.getLogger("automation")

    def run_command(
        self,
        command: Iterable[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Exécute une commande tout en la journalisant proprement."""

        cmd_list = list(command)
        printable = shlex.join(cmd_list)
        if description:
            self.logger.info("%s", description)
        self.logger.info("Commande: %s", printable)

        self.stop_controller.raise_if_requested()

        if self.dry_run:
            self.logger.warning("Mode --dry-run actif, la commande n'est pas exécutée")
            return

        process = subprocess.Popen(
            cmd_list,
            cwd=str(cwd) if cwd else None,
            env={**os.environ, **env} if env else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        self.stop_controller.register_process(process)

        try:
            assert process.stdout is not None  # pour mypy/pyright
            for line in process.stdout:
                cleaned = line.rstrip()
                if cleaned:
                    self.logger.info("[sortie] %s", cleaned)
                if self.stop_controller.stop_requested:
                    break

            return_code = process.wait()
        except KeyboardInterrupt:
            if not self.stop_controller.stop_requested:
                self.stop_controller.request_stop(reason="interruption clavier")
            raise StopRequested()
        finally:
            self.stop_controller.unregister_process(process)

        if self.stop_controller.stop_requested:
            raise StopRequested()

        if return_code != 0:
            raise AutomationError(f"La commande '{printable}' a échoué avec le code {return_code}")


# ---------------------------------------------------------------------------
# Initialisation du logging
# ---------------------------------------------------------------------------


def _build_log_file(now: Optional[datetime] = None) -> Path:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    return LOGS_DIR / f"automation-{timestamp}.log"


def configure_logging(now: Optional[datetime] = None) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _build_log_file(now)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    return log_file


# ---------------------------------------------------------------------------
# Actions disponibles
# ---------------------------------------------------------------------------

def ensure_permissions(context: AutomationContext) -> None:
    """Rend exécutables les scripts shell nécessaires."""

    context.stop_controller.raise_if_requested()
    cache = _load_permission_cache()
    if cache is not None:
        context.logger.info(
            "Vérification des permissions sautée : %s.", _describe_cache(cache)
        )
        details = _describe_cache(cache)
        context.report.update("permissions", "ok", details)
        return

    context.logger.info("Vérification des permissions d'exécution")
    results: list[Dict[str, Any]] = []
    missing_scripts: list[str] = []
    updated_scripts: list[str] = []
    for script in ("build.sh", "flash_automation.sh"):
        target = FLASH_DIR / script
        entry: Dict[str, Any] = {"path": str(target)}
        if not target.exists():
            context.logger.warning("Le script %s est introuvable", target)
            entry["status"] = "missing"
            results.append(entry)
            missing_scripts.append(script)
            continue

        current_mode = S_IMODE(target.stat().st_mode)
        desired_mode = current_mode | 0o111
        already_executable = current_mode == desired_mode
        entry.update(
            {
                "status": "updated" if not already_executable else "ok",
                "previous_mode": oct(current_mode),
                "final_mode": oct(desired_mode),
            }
        )

        if already_executable:
            context.logger.debug("Les permissions sont déjà correctes pour %s", target)
        else:
            context.logger.debug("Application du mode exécutable sur %s", target)
            if context.dry_run:
                context.logger.warning("Mode --dry-run : chmod ignoré pour %s", target)
            else:
                target.chmod(desired_mode)
            updated_scripts.append(script)

        results.append(entry)

    context.logger.info("Permissions vérifiées")

    detail_parts: list[str] = []
    status = "ok"
    if missing_scripts:
        status = "error"
        detail_parts.append(
            f"{len(missing_scripts)} script(s) introuvable(s)"
        )
    elif updated_scripts and context.dry_run:
        status = "warning"
        detail_parts.append(
            f"{len(updated_scripts)} script(s) nécessitent un chmod (dry-run)"
        )
    elif updated_scripts:
        detail_parts.append(
            f"Permissions ajustées sur {len(updated_scripts)} script(s)"
        )
    else:
        detail_parts.append("Permissions déjà conformes")

    if context.dry_run:
        context.logger.warning("Mode --dry-run : cache des permissions laissé inchangé")
        detail_parts.append("Cache des permissions conservé (--dry-run)")
        if status == "ok":
            status = "warning"
        context.report.update("permissions", status, "; ".join(detail_parts))
        return

    _write_permission_cache(
        status="ok",
        origin="automation_cli.ensure_permissions",
        payload={"scripts": results},
    )
    ttl = _get_permission_cache_ttl()
    if ttl > 0:
        context.logger.info(
            "Cache des permissions mis à jour (expiration dans %s).",
            _format_duration(float(ttl)),
        )
        detail_parts.append(
            f"Cache mis à jour (expiration dans {_format_duration(float(ttl))})"
        )
    else:
        detail_parts.append("Cache mis à jour")
    context.report.update("permissions", status, "; ".join(detail_parts))


def install_python_dependencies(context: AutomationContext) -> None:
    """Installe les dépendances Python listées dans requirements.txt."""

    context.stop_controller.raise_if_requested()
    requirements = FLASH_DIR / "requirements.txt"
    if not requirements.exists():
        raise AutomationError("Le fichier requirements.txt est introuvable")

    venv_dir = FLASH_DIR / ".venv"
    lock_file = venv_dir / "requirements.lock"
    hash_file = venv_dir / "requirements.sha256"
    venv_dir.mkdir(parents=True, exist_ok=True)

    current_hash = _compute_sha256(requirements)
    stored_hash = _read_requirements_hash(hash_file)

    if stored_hash == current_hash and lock_file.exists():
        context.logger.info(
            "Installation des dépendances sautée : requirements.txt inchangé (hash %s).",
            current_hash[:12],
        )
        context.report.update(
            "dependencies",
            "ok",
            f"Dépendances déjà installées (hash {current_hash[:12]})",
        )
        return

    if stored_hash == current_hash and not lock_file.exists():
        context.logger.info(
            "Création du verrou de dépendances manquant (requirements.lock).",
        )
        if context.dry_run:
            context.logger.warning(
                "Mode --dry-run : verrou de dépendances non généré"
            )
            context.report.update(
                "dependencies",
                "warning",
                "requirements.lock absent; génération simulée (--dry-run)",
            )
            return
        _update_lock_file(context, lock_file)
        hash_file.write_text(current_hash + "\n", encoding="utf-8")
        context.logger.info("Verrou de dépendances enregistré dans %s", lock_file)
        context.report.update(
            "dependencies",
            "ok",
            f"Verrou de dépendances régénéré (hash {current_hash[:12]})",
        )
        return

    if stored_hash:
        context.logger.info(
            "Mise à jour des dépendances : hash modifié (%s → %s).",
            stored_hash[:12],
            current_hash[:12],
        )
    else:
        context.logger.info(
            "Installation des dépendances requise : aucun verrou existant détecté."
        )

    context.run_command(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
        cwd=FLASH_DIR,
        description="Installation des dépendances Python",
    )

    if context.dry_run:
        context.logger.warning("Mode --dry-run : verrou de dépendances non généré")
        context.report.update(
            "dependencies",
            "warning",
            "Installation simulée (--dry-run); verrou non mis à jour",
        )
        return

    _update_lock_file(context, lock_file)
    hash_file.write_text(current_hash + "\n", encoding="utf-8")
    context.logger.info("Verrou de dépendances mis à jour dans %s", lock_file)
    context.report.update(
        "dependencies",
        "ok",
        f"Dépendances installées (hash {current_hash[:12]})",
    )


def build_firmware(context: AutomationContext) -> None:
    """Lance la compilation du firmware via build.sh."""

    context.stop_controller.raise_if_requested()
    simulated = context.dry_run
    context.run_command(["./build.sh"], cwd=FLASH_DIR, description="Compilation du firmware Klipper")
    if simulated:
        context.report.update("compile", "warning", "Compilation simulée (--dry-run)")
    else:
        context.report.update("compile", "ok", "Firmware compilé via build.sh")


def flash_interactive(context: AutomationContext) -> None:
    """Démarre le flash interactif (python3 flash.py)."""

    context.stop_controller.raise_if_requested()
    context.run_command([sys.executable, "flash.py"], cwd=FLASH_DIR, description="Flash interactif du BMCU-C")


def flash_cli(context: AutomationContext) -> None:
    """Flash minimal via le script shell."""

    context.stop_controller.raise_if_requested()
    context.run_command(["./flash_automation.sh"], cwd=FLASH_DIR, description="Flash minimal en ligne de commande")


def remote_orchestration(context: AutomationContext) -> None:
    """Collecte les paramètres et exécute l'automatisation distante."""

    context.stop_controller.raise_if_requested()
    firmware_path = input("Chemin local du firmware à transférer : ").strip()
    if not firmware_path:
        raise AutomationError("Un chemin de firmware est requis")
    context.stop_controller.raise_if_requested()
    bmc_host = input("Adresse IP / hôte du BMC : ").strip()
    if not bmc_host:
        raise AutomationError("L'hôte du BMC est requis")
    context.stop_controller.raise_if_requested()
    bmc_user = input("Utilisateur SSH/IPMI [root] : ").strip() or "root"
    bmc_password = getpass.getpass("Mot de passe SSH/IPMI : ")
    if not bmc_password:
        raise AutomationError("Le mot de passe est requis")
    context.stop_controller.raise_if_requested()
    remote_path = input("Chemin distant du firmware [/tmp/klipper_firmware.bin] : ").strip() or \
        "/tmp/klipper_firmware.bin"
    wait_reboot = input("Attendre le redémarrage après flash ? [o/N] : ").strip().lower().startswith("o")
    context.stop_controller.raise_if_requested()

    command = [
        sys.executable,
        "flashBMCtoKlipper_automation.py",
        "--bmc-host",
        bmc_host,
        "--bmc-password",
        bmc_password,
        "--firmware-file",
        firmware_path,
        "--remote-firmware-path",
        remote_path,
    ]
    if bmc_user:
        command.extend(["--bmc-user", bmc_user])
    if wait_reboot:
        command.append("--wait-for-reboot")

    context.run_command(command, cwd=FLASH_DIR, description="Automatisation distante du flash")


def clean_build_artifacts(context: AutomationContext) -> None:
    """Propose un nettoyage des artefacts de compilation."""

    context.stop_controller.raise_if_requested()
    cache_dir = FLASH_DIR / ".cache" / "klipper"
    if not cache_dir.exists():
        context.logger.warning("Le répertoire %s est introuvable, rien à nettoyer", cache_dir)
        return

    makefile = cache_dir / "Makefile"
    out_dir = cache_dir / "out"

    if makefile.exists():
        try:
            context.run_command(["make", "clean"], cwd=cache_dir, description="Nettoyage via make clean")
            return
        except AutomationError as exc:
            context.logger.error("make clean a échoué : %s", exc)
            if not out_dir.exists():
                return
            context.logger.info("Suppression manuelle du dossier out/")

    if out_dir.exists():
        if context.dry_run:
            context.logger.warning("Mode --dry-run : suppression de %s ignorée", out_dir)
        else:
            shutil.rmtree(out_dir)
        context.logger.info("Répertoire out/ supprimé")
    else:
        context.logger.info("Aucun artefact de compilation à supprimer")


def handle_manual_stop(context: AutomationContext) -> None:
    """Nettoyage global lors d'une interruption manuelle."""

    context.logger.warning("Arrêt manuel détecté. Nettoyage en cours...")
    logging.shutdown()
    print(f"Journaux disponibles dans : {context.log_file}")
    cleanup_repository()


ACTIONS = (
    MenuAction("1", "Vérifier les permissions des scripts", ensure_permissions, "permissions"),
    MenuAction("2", "Installer les dépendances Python", install_python_dependencies, "dependencies"),
    MenuAction("3", "Compiler le firmware", build_firmware, "compile"),
    MenuAction("4", "Flash interactif (flash.py)", flash_interactive),
    MenuAction("5", "Flash minimal (flash_automation.sh)", flash_cli),
    MenuAction("6", "Automatisation distante", remote_orchestration),
    MenuAction("7", "Nettoyer les artefacts de compilation", clean_build_artifacts),
)
ACTION_MAP = {action.key: action for action in ACTIONS}


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------


def execute_action(action: MenuAction, context: AutomationContext) -> None:
    report_key = action.report_key
    if report_key:
        context.report.mark_running(report_key)
    try:
        action.handler(context)
    except AutomationError as error:
        if report_key:
            context.report.mark_error(report_key, str(error))
        raise
    except StopRequested:
        if report_key:
            context.report.mark_error(report_key, "Arrêt manuel demandé")
        raise
    except KeyboardInterrupt:
        if report_key:
            context.report.mark_error(report_key, "Interruption clavier")
        raise
    except Exception as unexpected:
        if report_key:
            context.report.mark_error(report_key, f"Erreur inattendue : {unexpected}")
        raise
    else:
        if report_key:
            context.report.finalize_success(
                report_key,
                default_message="Action exécutée",
            )

def display_banner() -> None:
    banner = (FLASH_DIR / "banner.txt")
    if banner.exists():
        try:
            content = banner.read_text(encoding="utf-8").rstrip()
        except OSError as exc:
            logging.getLogger("automation").warning("Impossible de lire la bannière : %s", exc)
        else:
            if content:
                print(content)
                print()


def interactive_menu(context: AutomationContext) -> None:
    display_banner()
    context.logger.info("Menu d'automatisation prêt. Sélectionnez une option.")

    while True:
        context.stop_controller.raise_if_requested()
        print("\n=== Gestionnaire BMCU-C ===")
        for action in ACTIONS:
            print(f" {action.key}. {action.label}")
        print(" X. Quitter")

        choice = input("Votre choix : ").strip().upper()
        if choice in {"X", "Q"}:
            context.logger.info("Fermeture du gestionnaire sur demande utilisateur")
            break
        action = ACTION_MAP.get(choice)
        if not action:
            context.logger.error("Choix '%s' invalide", choice)
            continue
        try:
            execute_action(action, context)
            context.logger.info("Action '%s' terminée", action.label)
        except AutomationError as error:
            context.logger.error("Action '%s' interrompue : %s", action.label, error)
        except StopRequested:
            raise
        except KeyboardInterrupt:
            context.logger.warning("Action '%s' interrompue par l'utilisateur", action.label)
            raise StopRequested()
        except Exception as unexpected:
            context.logger.exception("Erreur inattendue lors de l'action '%s'", action.label)


def parse_arguments(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatisation du BMCU-C inspirée de KIAUH",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=[action.key for action in ACTIONS],
        help="Exécute une action précise sans lancer le menu interactif",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les commandes sans les exécuter",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Exporte le rapport de vérifications au format JSON",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    log_file = configure_logging()
    stop_controller = StopController(enable_input_listener=False)
    stop_controller.start()

    report = AutomationReport()
    logger = logging.getLogger("automation")
    logger.info("Bouton stop : pressez Ctrl+C pour interrompre proprement.")
    logger.info("Les journaux sont enregistrés dans %s", log_file)

    args = parse_arguments(argv)
    context = AutomationContext(
        dry_run=args.dry_run,
        stop_controller=stop_controller,
        log_dir=LOGS_DIR,
        log_file=log_file,
        report=report,
    )

    exit_code = 0
    try:
        if args.action:
            action = ACTION_MAP[args.action]
            try:
                execute_action(action, context)
            except AutomationError as error:
                context.logger.error("Action '%s' interrompue : %s", action.label, error)
                exit_code = 1
            else:
                exit_code = 0
        else:
            interactive_menu(context)
            exit_code = 0
    except StopRequested:
        handle_manual_stop(context)
        exit_code = 130
    except KeyboardInterrupt:
        if not stop_controller.stop_requested:
            stop_controller.request_stop(reason="interruption clavier")
        handle_manual_stop(context)
        exit_code = 130
    finally:
        print()
        print("=== Synthèse des vérifications ===")
        print(report.render_console_table())
        if args.report_json:
            try:
                report.export_json(args.report_json, log_file=log_file)
                logger.info("Rapport JSON exporté dans %s", args.report_json)
            except OSError as exc:
                logger.error("Impossible d'écrire le rapport JSON : %s", exc)
                if exit_code == 0:
                    exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
