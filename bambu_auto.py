"""Locked-down X2D slicing adapter: official Bambu Studio CLI, full profiles only.

The preview-only PrusaSlicer engine must never feed this path. Slicing may
prepare/upload a machine-ready 3MF, but it NEVER starts the printer.
"""
from __future__ import annotations

import json
import io
import hashlib
import math
import struct
import zlib
import zipfile
import xml.etree.ElementTree as ET
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

LOG = logging.getLogger('fjord.bambu_slicer')

MAX_STL = 20 * 1024 * 1024
MAX_3MF = 30 * 1024 * 1024
# Intentional whitelist: never accept arbitrary slicer configuration from a client.
SUPPORT_MODES = ('off', 'tree(auto)', 'normal(auto)')
OUTPUT_NAME = 'x2d_tranche.gcode.3mf'
# UI plate names map to the values of the Bambu Studio curr_bed_type enum.
# The actual CLI has NO --curr-bed-type flag; choose the bed via process JSON.
# See BambuStudio src/libslic3r/PrintConfig.cpp s_keys_map_BedType.
BED_TYPES = {
    'Textured PEI Plate': ('Textured PEI Plate', 'textured_plate_temp'),
    'Smooth PEI Plate / High Temp Plate': ('High Temp Plate', 'hot_plate_temp'),
    'Engineering Plate': ('Engineering Plate', 'eng_plate_temp'),
    'Cool Plate SuperTack': ('Supertack Plate', 'supertack_plate_temp'),
    'Cool Plate': ('Cool Plate', 'cool_plate_temp'),
}
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



def cli_preset(raw: dict, category: str) -> dict:
    """Convert trusted, fully expanded presets to Bambu CLI metadata.

    Stock BBL JSONs label their source "System", but CLI accepts only
    lowercase "system" or "User"/"user". This changes metadata, never
    temperatures, nozzle size, startup G-code or other machine settings.
    """
    preset = dict(full_preset(raw, category))
    source = str(preset.get("from") or "User")
    if source.lower() == "system":
        source = "system"
    elif source.lower() == "user":
        source = "User"
    else:
        raise AutoSliceError("Origine du profil Bambu inconnue : impression bloquée.")
    preset["from"] = source
    preset["type"] = {"Imprimante": "machine", "Impression": "process",
                      "Filament": "filament"}[category]
    return preset


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
        return ("Bambu Studio ne peut pas démarrer sur Render : bibliothèque Linux "
                "manquante ({}). Les profils ne sont pas en cause.".format(missing_lib.group(1)[:90]))
    if exit_code < 0:
        return "Le moteur Bambu Studio s’est arrêté anormalement (signal {}).".format(-exit_code)
    if exit_code == 0 and not output_exists:
        return "Bambu Studio a terminé sans produire le 3MF tranché attendu."
    if any(term in message for term in ("unknown option", "unrecognized option", "unrecognised option")):
        return "Bambu Studio a refusé un paramètre de commande."
    if "does not support filament" in message or "not compatible with the plate type" in message:
        return "Plateau et filament incompatibles : choisis le type de plaque réellement installé sur la X2D."
    if any(term in message for term in ("preset", "filament", "config", "machine settings", "process settings")):
        return "Bambu Studio a signalé un problème de compatibilité ou de contenu des profils choisis."
    if exit_code != 0:
        return "Le moteur Bambu Studio a interrompu le tranchage (code {}).".format(exit_code)
    if not output_exists:
        return "Bambu Studio a terminé sans produire le 3MF tranché attendu."
    return "Le tranchage Bambu Studio n’a pas produit un résultat exploitable."


def _log_failure(output: bytes, exit_code: int, output_exists: bool):
    """Record minimal, scrubbed diagnostics in Render logs only."""
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


def prepare_connect_archive(raw: bytes) -> bytes:
    """Complete native CLI plate metadata without changing printable bytes/settings.

    Headless CLI output can omit thumbnail/bbox keys used by Connect's importer.
    Missing images use an explicitly empty transparent PNG, never a fake model.
    Do not pad filament/extruder arrays or substitute another printer profile.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zin:
            infos = zin.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or sum(i.file_size for i in infos) > 100 * 1024 * 1024:
                raise AutoSliceError("Archive 3MF ambiguë ou trop volumineuse.")
            data = {i.filename: zin.read(i) for i in infos}
        settings = json.loads(data["Metadata/project_settings.config"])
        if not re.search(r"\bX2D\b", str(settings.get("printer_model", "")), re.I):
            raise AutoSliceError("Le 3MF ne déclare pas une X2D.")
        model = ET.fromstring(data["Metadata/model_settings.config"])
        slices = ET.fromstring(data["Metadata/slice_info.config"])
        plates = model.findall("plate")
        if not plates:
            raise AutoSliceError("Le 3MF ne contient aucun plateau.")
        changed = False
        def png_chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
        empty_png = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
                     + png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")) + png_chunk(b"IEND", b""))
        for plate in plates:
            meta = {e.get("key"): e for e in plate.findall("metadata")}
            number = meta.get("plater_id")
            number = number.get("value", "") if number is not None else ""
            if not number.isdigit():
                raise AutoSliceError("Identifiant de plateau 3MF invalide.")
            gcode_node = meta.get("gcode_file")
            path = gcode_node.get("value", "") if gcode_node is not None else ""
            gcode = data[path]
            if not gcode or hashlib.md5(gcode).hexdigest().upper() != data[path + ".md5"].decode().strip().upper():
                raise AutoSliceError("Le contrôle d'intégrité du G-code a échoué.")
            bbox = "Metadata/plate_" + number + ".json"
            json.loads(data[bbox])
            refs = {
                "thumbnail_file": "Metadata/plate_" + number + ".png",
                "thumbnail_no_light_file": "Metadata/plate_no_light_" + number + ".png",
                "top_file": "Metadata/top_" + number + ".png",
                "pick_file": "Metadata/pick_" + number + ".png",
                "pattern_bbox_file": bbox,
            }
            for key, target in refs.items():
                node = meta.get(key)
                if node is None:
                    node = ET.SubElement(plate, "metadata", key=key, value=target)
                    changed = True
                elif not node.get("value"):
                    node.set("value", target)
                    changed = True
                target = node.get("value")
                if target.endswith(".png") and target not in data:
                    data[target] = empty_png
                    changed = True
                elif target not in data:
                    raise AutoSliceError("Référence du plateau absente du 3MF.")
            small = "Metadata/plate_" + number + "_small.png"
            if small not in data:
                data[small] = empty_png
                changed = True
        for plate in slices.findall("plate"):
            meta = {e.get("key"): e for e in plate.findall("metadata")}
            first = meta.get("first_layer_time")
            total = meta.get("prediction")
            if first is not None and total is not None:
                duration = float(first.get("value", "nan"))
                prediction = float(total.get("value", "0"))
                if not math.isfinite(duration) or duration < 0 or duration > prediction:
                    # Zero is the native plate JSON's unavailable-duration value.
                    first.set("value", "0")
                    changed = True
        if not changed:
            return raw
        data["Metadata/model_settings.config"] = ET.tostring(model, encoding="utf-8", xml_declaration=True)
        data["Metadata/slice_info.config"] = ET.tostring(slices, encoding="utf-8", xml_declaration=True)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, payload in data.items():
                zout.writestr(name, payload)
        result = out.getvalue()
        if len(result) > MAX_3MF:
            raise AutoSliceError("Le 3MF préparé dépasse 30 Mo.")
        return result
    except AutoSliceError:
        raise
    except (KeyError, ValueError, TypeError, UnicodeError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise AutoSliceError("Métadonnées du 3MF illisibles ou incomplètes : import annulé.") from exc


def slice_x2d(stl: bytes, presets: dict, verifier, *, bed_type: str = 'Textured PEI Plate',
              support_mode: str = 'off', support_plate_only: bool = False) -> bytes:
    """Return verified native sliced 3MF; fail closed before any network transfer.

    verifier validates the actual sliced Bambu archive used by manual uploads.
    """
    if bed_type not in BED_TYPES:
        raise AutoSliceError("Type de plateau X2D inconnu : tranchage bloqué.")
    if support_mode not in SUPPORT_MODES or type(support_plate_only) is not bool:
        raise AutoSliceError("Configuration des supports automatiques invalide.")
    if not isinstance(stl, bytes) or not 84 <= len(stl) <= MAX_STL:
        raise AutoSliceError("STL vide ou trop volumineux (maximum 20 Mo).")
    # Binary STL: 80-byte header + uint32 triangle count + 50 bytes per triangle.
    if len(stl) < 134:
        raise AutoSliceError("STL binaire incomplet.")
    n = int.from_bytes(stl[80:84], "little")
    if not 0 < n <= 400000 or len(stl) != 84 + 50 * n:
        raise AutoSliceError("Maillage STL binaire invalide.")
    if not _SLICING_SLOT.acquire(blocking=False):
        raise AutoSliceError("Un tranchage est déjà en cours. Réessaie après sa fin.")
    try:
        cli = cli_location()
        if not cli:
            raise AutoSliceError(
                "Moteur Bambu Studio non installé sur Render. Impression automatique désactivée."
            )
        machine = cli_preset(presets.get("Imprimante"), "Imprimante")
        process = cli_preset(presets.get("Impression"), "Impression")
        filament = cli_preset(presets.get("Filament"), "Filament")
        # Bambu Studio loads these process JSON settings before slicing, so
        # actual support G-code is generated and included in the sliced 3MF.
        # Match the string-valued Boolean representation of Bambu presets.
        process["enable_support"] = "0" if support_mode == "off" else "1"
        if support_mode != "off":
            process["support_type"] = support_mode
            process["support_on_build_plate_only"] = "1" if support_plate_only else "0"
        # A bare STL has no stored build-plate choice. Use the exact enum
        # token within the process JSON loaded by Bambu Studio.
        native_bed, temperature_key = BED_TYPES[bed_type]
        process["curr_bed_type"] = native_bed
        # A zero stock plate temperature means the selected filament cannot
        # be printed on that plate. Reject before generating any printer file.
        plate_temperatures = filament.get(temperature_key, [])
        if not isinstance(plate_temperatures, list):
            plate_temperatures = [plate_temperatures]
        if plate_temperatures:
            try:
                compatible = any(float(value) > 0 for value in plate_temperatures)
            except (ValueError, TypeError, OverflowError) as exc:
                raise AutoSliceError(
                    "Température de plaque illisible dans le profil filament."
                ) from exc
            if not compatible:
                raise AutoSliceError(
                    "Le profil filament ne permet pas l'impression sur cette plaque : "
                    + bed_type + ". Sélectionne une plaque compatible réellement installée."
                )
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
                "--min-save",
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
                raise AutoSliceError("Le moteur Bambu Studio n'a pas pu être lancé sur Render.") from exc
            if result.returncode != 0 or not output_file.is_file():
                _log_failure(result.stdout, result.returncode, output_file.is_file())
                raise AutoSliceError(
                    _safe_cli_diagnostic(result.stdout, result.returncode, output_file.is_file())
                )
            if output_file.stat().st_size > MAX_3MF:
                raise AutoSliceError("Le fichier tranché dépasse 30 Mo.")
            finished = prepare_connect_archive(output_file.read_bytes())
            verifier(finished)
            return finished
    finally:
        _SLICING_SLOT.release()

