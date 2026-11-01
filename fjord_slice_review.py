"""Preview actual Bambu G-code and temporarily stage a sliced 3MF.

The file is local to the Railway worker, expires after 20 minutes, is tied to
an unpredictable session nonce and is never sent to the printer by preview.
"""
from __future__ import annotations

import io
import math
import os
import re
import secrets
import tempfile
import time
import zipfile
from pathlib import Path

from flask import session

TTL_SECONDS = 20 * 60
MAX_GCODE = 48 * 1024 * 1024
MAX_LINE = 300
MAX_LAYERS = 900
MAX_SEGMENTS_PER_LAYER = 800
MAX_SEGMENTS_TOTAL = 50000
STAGING_DIRECTORY = Path(tempfile.gettempdir()) / "fjord_bambu_review"
TOKEN_PATTERN = re.compile(r"^[a-f0-9]{40}$")
POSITION = re.compile(r"(?<![A-Z])([XYZE])\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", re.I)


class SliceReviewError(ValueError):
    pass


def _path(token: str) -> Path:
    if not TOKEN_PATTERN.fullmatch(token or ""):
        raise SliceReviewError("Identifiant de tranchage invalide.")
    return STAGING_DIRECTORY / (token + ".3mf")


def _cleanup_stale():
    STAGING_DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    now = time.time()
    for path in STAGING_DIRECTORY.glob("*.3mf"):
        try:
            if now - path.stat().st_mtime > TTL_SECONDS:
                path.unlink(missing_ok=True)
        except OSError:
            pass


def preview_toolpath(sliced: bytes) -> dict:
    """Real G1 extrusion segments sampled from Metadata/plate_1.gcode.

    Sampled lines are for visual inspection only, not for firmware estimates
    or modification of the verified 3MF. No generic/simulated slicing involved.
    """
    layers = {}
    x = y = z = e = 0.0
    relative_extrusion = False
    relative_xyz = False
    total_segments = 0
    scanned_lines = 0
    with zipfile.ZipFile(io.BytesIO(sliced)) as archive:
        info = archive.getinfo("Metadata/plate_1.gcode")
        if not 100 <= info.file_size <= MAX_GCODE:
            raise SliceReviewError("Le G-code est trop volumineux pour l’aperçu. Aucun envoi effectué.")
        with archive.open(info) as stream:
            for raw in stream:
                scanned_lines += 1
                if scanned_lines > 1600000:
                    raise SliceReviewError("G-code trop détaillé pour un aperçu sûr.")
                if len(raw) > MAX_LINE:
                    continue
                command = raw.split(b";", 1)[0].decode("ascii", "ignore").strip().upper()
                if not command:
                    continue
                op = command.split(None, 1)[0]
                if op == "M82":
                    relative_extrusion = False
                    continue
                if op == "M83":
                    relative_extrusion = True
                    continue
                if op == "G90":
                    relative_xyz = False
                    continue
                if op == "G91":
                    relative_xyz = True
                    continue
                if op not in ("G0", "G1", "G92"):
                    continue
                args = {}
                for key, value in POSITION.findall(command):
                    try:
                        number = float(value)
                        if math.isfinite(number):
                            args[key.upper()] = number
                    except ValueError:
                        continue
                if op == "G92":
                    x = args.get("X", x)
                    y = args.get("Y", y)
                    z = args.get("Z", z)
                    e = args.get("E", e)
                    continue
                nx = x + args["X"] if relative_xyz and "X" in args else args.get("X", x)
                ny = y + args["Y"] if relative_xyz and "Y" in args else args.get("Y", y)
                nz = z + args["Z"] if relative_xyz and "Z" in args else args.get("Z", z)
                ne = e + args["E"] if relative_extrusion and "E" in args else args.get("E", e)
                extruding = "E" in args and ne > e + 1e-7
                if extruding and (abs(nx-x) > .001 or abs(ny-y) > .001):
                    # Skip purge lines and implausible coordinates outside physical bed.
                    if all(-2 <= q <= 260 for q in (x,y,nx,ny)) and -1 <= nz <= 265:
                        layer_key = round(nz, 3)
                        if layer_key not in layers:
                            if len(layers) >= MAX_LAYERS:
                                raise SliceReviewError("Trop de couches pour l’aperçu.")
                            layers[layer_key] = {"z":layer_key,"segments":[],"moves":0}
                        layer = layers[layer_key]
                        layer["moves"] += 1
                        total_segments += 1
                        # Bounded deterministic sampling. Preserve first 800
                        # moves per layer to avoid fabricated motion.
                        if len(layer["segments"]) < MAX_SEGMENTS_PER_LAYER and sum(
                            len(v["segments"]) for v in layers.values()) < MAX_SEGMENTS_TOTAL:
                            layer["segments"].append([round(x,2),round(y,2),round(nx,2),round(ny,2)])
                x,y,z,e = nx,ny,nz,ne
    if total_segments == 0:
        raise SliceReviewError("Aucune trajectoire d’extrusion reconnue : aperçu et envoi bloqués.")
    ordered = [layers[k] for k in sorted(layers)]
    return {"source":"G-code réel du 3MF Bambu Studio","layers":ordered,
            "layer_count":len(ordered),"total_moves":total_segments,
            "sampled":sum(len(layer["segments"]) for layer in ordered)<total_segments,
            "plate":1}


def stage_slice(sliced: bytes, verifier) -> tuple[str, dict]:
    verifier(sliced)
    preview = preview_toolpath(sliced)
    _cleanup_stale()
    previous = session.get("fjord_slice_review")
    if isinstance(previous, dict):
        try:
            _path(previous.get("token","")).unlink(missing_ok=True)
        except (OSError, SliceReviewError):
            pass
    token = secrets.token_hex(20)
    target = _path(token)
    fd = os.open(target, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as dest:
            dest.write(sliced)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    session["fjord_slice_review"] = {"token":token,"at":time.time()}
    return token, preview


def get_staged(token: str) -> bytes:
    pending = session.get("fjord_slice_review")
    if (not isinstance(pending,dict) or not TOKEN_PATTERN.fullmatch(token or "")
        or not secrets.compare_digest(pending.get("token",""),token)
        or time.time()-float(pending.get("at",0))>TTL_SECONDS):
        raise SliceReviewError("Aperçu expiré ou non autorisé. Tranche de nouveau la pièce.")
    try:
        return _path(token).read_bytes()
    except OSError as exc:
        raise SliceReviewError("Fichier temporaire indisponible. Tranche de nouveau la pièce.") from exc


def consume_staged(token: str) -> None:
    # Only call after confirmed upload.
    pending = session.get("fjord_slice_review")
    if isinstance(pending,dict) and pending.get("token")==token:
        session.pop("fjord_slice_review",None)
        _path(token).unlink(missing_ok=True)
