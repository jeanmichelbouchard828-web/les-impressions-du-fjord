"""Locked-down X2D slicing adapter: official Bambu Studio CLI, full profiles only.

The preview-only PrusaSlicer engine must never feed this path. Slicing may
prepare/upload a machine-ready 3MF, but it NEVER starts the printer.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

MAX_STL = 8 * 1024 * 1024
MAX_3MF = 30 * 1024 * 1024
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
            input_file, output_file = root / "atelier.stl", root / "x2d_tranche.3mf"
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
                cli, "--debug", "2", "--arrange", "1",
                "--load-settings", "{};{}".format(files[0], files[1]),
                "--load-filaments", str(files[2]),
                "--slice", "0",
                "--export-3mf", str(output_file),
                str(input_file),
            ]
            try:
                result = subprocess.run(
                    args, cwd=work, timeout=95, check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env={**os.environ, "HOME": work},
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise AutoSliceError("Le moteur Bambu Studio n'a pas terminé le tranchage.") from exc
            if result.returncode != 0 or not output_file.is_file():
                raise AutoSliceError(
                    "Le tranchage Bambu Studio a échoué. Vérifie que les trois profils sont complets et compatibles."
                )
            if output_file.stat().st_size > MAX_3MF:
                raise AutoSliceError("Le fichier tranché dépasse 30 Mo.")
            finished = output_file.read_bytes()
            verifier(finished)
            return finished
    finally:
        _SLICING_SLOT.release()
