"""Read *original*, pinned BambuStudio X2D presets from its installed bundle.

The Bambu CLI requires a fully expanded machine/process/filament JSON, while
the stock system files contain "inherits" and (for the X2D) essential "include"
G-code templates. Missing files or unexpanded templates fail closed.

We do not fetch remote profiles, alter their settings, or write user presets.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from bambu_auto import AutoSliceError, full_preset

SYSTEM_PROFILE_ROOT = Path("/opt/bambu/bbl-stock-profiles-path")
MACHINE_NAME = "Bambu Lab X2D 0.4 nozzle"
PROCESS_NAME = "0.20mm Standard @BBL X2D"
STOCK_FILAMENTS = ("PETG", "PLA", "ASA", "TPU")
STOCK_NAMES = {
    "Imprimante": {"stock:machine:x2d04": MACHINE_NAME},
    "Impression": {"stock:process:020": PROCESS_NAME},
    "Filament": {
        "stock:filament:" + kind: "Generic {} @BBL X2D 0.4 nozzle".format(kind)
        for kind in STOCK_FILAMENTS
    },
}
DIRECTORIES = {"Imprimante": "machine", "Impression": "process", "Filament": "filament"}


def system_root() -> Path:
    if not SYSTEM_PROFILE_ROOT.is_file():
        raise AutoSliceError("Profils système Bambu absents sur Railway.")
    root = Path(SYSTEM_PROFILE_ROOT.read_text(encoding="utf-8").strip()).resolve()
    if not (root / "machine").is_dir() or not (root / "filament").is_dir() or not (root / "process").is_dir():
        raise AutoSliceError("Bibliothèque de profils Bambu Studio incomplète.")
    return root


@lru_cache(maxsize=4)
def _index(root_string: str, directory: str) -> dict:
    base = Path(root_string) / directory
    entries = {}
    if not base.is_dir():
        raise AutoSliceError("Dossier des profils Bambu Studio introuvable.")
    for file in sorted(base.rglob("*.json")):
        # Only trusted files from the pinned AppImage, no remote/user directory.
        if not file.resolve().is_relative_to(base.resolve()):
            continue
        if file.stat().st_size > 768 * 1024:
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            continue
        if isinstance(data, dict):
            name = data.get("name") or file.stem
            if isinstance(name, str) and name:
                entries.setdefault(name, data)
    return entries


def _expanded(name: str, entries: dict, seen: frozenset, depth: int = 0) -> dict:
    if depth > 24 or name in seen:
        raise AutoSliceError("Hiérarchie des profils Bambu Studio circulaire/incomplète.")
    data = entries.get(name)
    if data is None:
        raise AutoSliceError("Fichier d'origine Bambu Studio manquant : {}.".format(name[:95]))
    visited = seen | {name}
    merged = {}
    parent = data.get("inherits")
    if isinstance(parent, str) and parent.strip():
        merged.update(_expanded(parent.strip(), entries, visited, depth + 1))
    includes = data.get("include") or []
    if isinstance(includes, str):
        includes = [includes]
    if not isinstance(includes, list) or len(includes) > 30:
        raise AutoSliceError("Liste d'inclusions de profils Bambu invalide.")
    for item in includes:
        if not isinstance(item, str) or not item.strip():
            raise AutoSliceError("Référence de profil Bambu invalide.")
        merged.update(_expanded(item, entries, visited, depth + 1))
    merged.update({key: value for key, value in data.items()
                   if key not in ("inherits", "include")})
    return merged


def original_preset(category: str, stock_id: str) -> dict:
    name = STOCK_NAMES.get(category, {}).get(stock_id)
    if name is None:
        raise AutoSliceError("Sélection de profil Bambu d'origine inconnue.")
    root = system_root()
    merged = _expanded(name, _index(str(root), DIRECTORIES[category]), frozenset())
    if merged.get("name") != name:
        raise AutoSliceError("Profil original Bambu différent du modèle attendu.")
    full_preset(merged, category)
    if category == "Imprimante":
        # The X2D stock start G-code does not live on the inheritance chain:
        # it is a machine-specific include. A generic fallback would skip AMS
        # setup / preflight safety steps. Never send that to a physical machine.
        start = merged["machine_start_gcode"]
        if not isinstance(start, str) or len(start) < 3000 or "M620" not in start:
            raise AutoSliceError("G-code de démarrage original X2D incomplet : impression bloquée.")
        if "M620" not in str(merged.get("machine_change_filament_gcode", "")) and \
           "M620" not in str(merged.get("change_filament_gcode", "")):
            # The main startup template is still mandatory; some releases
            # rename the change tool key, so avoid requiring both independently.
            pass
    if category == "Filament":
        material = stock_id.split(":")[-1]
        actual = merged["filament_type"]
        if isinstance(actual, list):
            actual = actual[0] if actual else ""
        if str(actual).upper() != material:
            raise AutoSliceError("Le filament Bambu d'origine ne correspond pas au matériau.")
        compatible = merged.get("compatible_printers") or []
        if compatible and MACHINE_NAME not in compatible:
            raise AutoSliceError("Le filament Bambu d'origine n'est pas prévu pour la buse X2D 0,4 mm.")
    if category == "Impression":
        value = merged["layer_height"]
        if isinstance(value, list):
            value = value[0] if value else "0"
        if abs(float(value) - .2) > .005:
            raise AutoSliceError("Hauteur de couche officielle inattendue.")
    return merged


def available_original_presets() -> dict:
    result = {"Imprimante": [], "Impression": [], "Filament": []}
    for category, choices in STOCK_NAMES.items():
        for stock_id, name in choices.items():
            try:
                values = original_preset(category, stock_id)
            except (AutoSliceError, OSError, ValueError, TypeError):
                continue
            item = {"id": stock_id, "name": "Bambu d'origine · " + name,
                    "official": True}
            if category == "Imprimante":
                item.update(model="Bambu Lab X2D", nozzle="0.4")
            elif category == "Impression":
                item["layer"] = "0.2"
            else:
                item["material"] = stock_id.split(":")[-1]
            result[category].append(item)
    return result
