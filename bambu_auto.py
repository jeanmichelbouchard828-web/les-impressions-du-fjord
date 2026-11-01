"""Locked-down X2D slicing adapter: official Bambu Studio CLI, full profiles only.

The preview-only PrusaSlicer engine must never feed this path. Slicing may
prepare/upload a machine-ready 3MF, but it NEVER starts the printer.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

LOG = logging.getLogger('fjord.bambu_slicer')

MAX_STL = 8 * 1024 * 1024
MAX_3MF = 30 * 1024 * 1024
OUTPUT_NAME = 'x2d_tranche.gcode.3mf'
_SLICING_SLOT = threading.BoundedSemaphore(1)


class AutoSliceError(ValueError):
    pass


def cli_location():
    """Only a server-installed binary can be used; never a client-supplied path."""
    path = os.environ.get("BAMBU_STUDIO_CLI", "").strip()
    if not path:
        path = shutil.which("bambu-studio") or ""
    if not path:
        return None
    resolved = shutil.which(path) if os.path.basename(path) == path else path
    return resolved if resolved and os.path.isfile(resolved) and os.access(resolved, os.X_OK) else None


def full_preset(raw, category):
    """A partial archived preset is not a machine profile for live printing.

    Bambu CLI requires fully-expanded JSON, not an 'inherits'-only profile.
    The exact material pairing and physical hardware must still be confirmed.
    """
    if category not in ("Imprimante", "Impression", "Filament"):
        raise AutoSliceError("Catégorie de profil invalide.")
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError) as exc:
        raise AutoSliceError("Fichier de profil illisible.") from exc
    if not isinstance(data, dict):
        raise AutoSliceError("Profil JSON invalide.")
    keys = {
        "Imprimante": ("printer_model", "nozzle_diameter", "machine_start_gcode", "machine_end_gcode"),
        "Impression": ("layer_height", "wall_loops", "sparse_infill_density"),
        "Filament": ("filament_type", "nozzle_temperature", "filament_flow_ratio"),
    }[category]
    if any(key not in data or data[key] in (None, "", []) for key in keys):
        raise AutoSliceError(
            "Profil {} partiel : exporte un préréglage complet et validé depuis Bambu Studio.".format(category.lower())
        )
    if category == "Imprimante":
        model = data["printer_model"]
        if isinstance(model, list):
            model = " ".join(str(x) for x in model)
        if not re.search(r"\bX2D\b", str(model), re.I):
            raise AutoSliceError("Le profil imprimante sélectionné n'est pas explicitement destiné à la X2D.")
    return data



def _safe_cli_diagnostic(output: bytes, exit_code: int, output_exists: bool) -> str:
    """Classify CLI failures without exposing raw output or secrets in the UI."""
    message = output.decode("utf-8", "replace")[-16000:].lower()
    # Missing ELF shared libraries return 127. Diagnose the dependency,
    # not incorrectly the user's filament or slicing process profiles.
    missing_lib = re.search(
        r"error while loading shared libraries:\s*([\w.+-]+\.so(?:\.\d+)*)",
        message, re.I
    )
    if missing_lib:
        return ("Bambu Studio ne peut pas démarrer sur Railway : bibliothèque Linux "
                "manquante ({}). Les profils ne sont pas en cause.".format(missing_lib.group(1)[:90]))
    if exit_code < 0:
        return "Le moteur Bambu Studio s’est arrêté anormalement (signal {}).".format(-exit_code)
    if exit_code == 0 and not output_exists:
        return "Bambu Studio a terminé sans produire le 3MF tranché attendu."
    if any(term in message for term in ("unknown option", "unrecognized option", "unrecognised option")):
        return "Bambu Studio a refusé un paramètre de commande."
    if any(term in message for term in ("preset", "filament", "config", "machine settings", "process settings")):
        return "Bambu Studio a signalé un problème de compatibilité ou de contenu des profils choisis."
    if exit_code != 0:
        return "Le moteur Bambu Studio a interrompu le tranchage (code {}).".format(exit_code)
    if not output_exists:
        return "Bambu Studio a terminé sans produire le 3MF tranché attendu."
    return "Le tranchage Bambu Studio n’a pas produit un résultat exploitable."


def _log_failure(output: bytes, exit_code: int, output_exists: bool):
    """Record minimal, scrubbed diagnostics in Railway logs only."""
    lines = output.decode("utf-8", "replace")[-16000:].splitlines()
    important = [line for line in lines if any(
        word in line.lower() for word in ("error", "failed", "fatal", "invalid",
                                          "config", "preset", "filament", "not found",
                                          "could not", "unable", "exit")
    )]
    summary = " | ".join(important[-8:] if important else lines[-5:])
    summary = re.sub(r"https?://\S+", "[url]", summary)
    summary = re.sub(r"(?:(?:/tmp|/app|/opt|/home)/[^\s;,]+)", "[chemin]", summary)
    summary = re.sub(r"(?i)(token|bearer|password|secret|authorization)\s*[:=]\s*\S+", "[masqué]", summary)
    LOG.warning("Bambu slicing failed: exit=%s, file_written=%s, diagnostics=%s",
                exit_code, bool(output_exists), summary[:1300])

def slice_x2d(stl: bytes, presets: dict, verifier) -> bytes:
    """Return verified native sliced 3MF; fail closed before any network transfer.

    verifier validates the actual sliced Bambu archive used by manual uploads.
    """
    if not isinstance(stl, bytes) or not 84 <= len(stl) <= MAX_STL:
        raise AutoSliceError("STL vide ou trop volumineux (maximum 8 Mo).")
    # Binary STL: 80-byte header + uint32 triangle count + 50 bytes per triangle.
    if len(stl) < 134:
        raise AutoSliceError("STL binaire incomplet.")
    n = int.from_bytes(stl[80:84], "little")
    if not 0 < n <= 160000 or len(stl) != 84 + 50 * n:
        raise AutoSliceError("Maillage STL binaire invalide.")
    if not _SLICING_SLOT.acquire(blocking=False):
        raise AutoSliceError("Un tranchage est déjà en cours. Réessaie après sa fin.")
    try:
        cli = cli_location()
        if not cli:
            raise AutoSliceError(
                "Moteur Bambu Studio non installé sur Railway. Impression automatique désactivée."
            )
        machine = full_preset(presets.get("Imprimante"), "Imprimante")
        process = full_preset(presets.get("Impression"), "Impression")
        filament = full_preset(presets.get("Filament"), "Filament")
        with tempfile.TemporaryDirectory(prefix="fjord_x2d_") as work:
            root = Path(work)
            input_file = root / "atelier.stl"
            output_dir = root / "resultats"
            output_dir.mkdir(mode=0o700)
            output_file = output_dir / OUTPUT_NAME
            input_file.write_bytes(stl)
            files = []
            for category, name, preset in (
                ("Imprimante", "machine.json", machine),
                ("Impression", "process.json", process),
                ("Filament", "filament.json", filament),
            ):
                target = root / name
                target.write_text(json.dumps(preset, ensure_ascii=False), encoding="utf-8")
                files.append(target)
            args = [
                cli, "--debug", "3", "--arrange", "1",
                "--load-settings", "{};{}".format(files[0], files[1]),
                "--load-filaments", str(files[2]),
                "--slice", "0",
                "--outputdir", str(output_dir),
                "--export-3mf", OUTPUT_NAME,
                str(input_file),
            ]
            try:
                result = subprocess.run(
                    args, cwd=work, timeout=95, check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env={**os.environ, "HOME": work},
                )
            except subprocess.TimeoutExpired as exc:
                LOG.warning("Bambu CLI slicing timed out after 95 seconds")
                raise AutoSliceError("Le tranchage a dépassé 95 secondes. Essaie une pièce plus simple.") from exc
            except OSError as exc:
                LOG.warning("Bambu CLI launch error: %s", type(exc).__name__)
                raise AutoSliceError("Le moteur Bambu Studio n'a pas pu être lancé sur Railway.") from exc
            if result.returncode != 0 or not output_file.is_file():
                _log_failure(result.stdout, result.returncode, output_file.is_file())
                raise AutoSliceError(
                    _safe_cli_diagnostic(result.stdout, result.returncode, output_file.is_file())
                )
            if output_file.stat().st_size > MAX_3MF:
                raise AutoSliceError("Le fichier tranché dépasse 30 Mo.")
            finished = output_file.read_bytes()
            verifier(finished)
            return finished
    finally:
        _SLICING_SLOT.release()
