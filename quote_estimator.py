"""Estimation interne des soumissions à partir du vrai tranchage (pas de G-code machine)."""
import io
import math
import os
import posixpath
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from real_slicer import parse_gcode

MAX_MODEL = 8 * 1024 * 1024
MAX_XML = 80 * 1024 * 1024
MAX_TRIANGLES = 500000
DENSITIES = {"PLA": 1.24, "PETG": 1.27, "PETG-CF": 1.28, "ASA": 1.07, "TPU": 1.20}
TEMPERATURES = {"PLA": (210, 60), "PETG": (230, 75),
                "PETG-CF": (245, 65), "ASA": (250, 100), "TPU": (220, 50)}
UNITS = {"micron": .001, "millimeter": 1, "centimeter": 10,
         "meter": 1000, "inch": 25.4, "foot": 304.8}
IDENTITY = ((1., 0., 0., 0.), (0., 1., 0., 0.),
            (0., 0., 1., 0.), (0., 0., 0., 1.))


class EstimationError(ValueError):
    pass


def _children(element, name):
    return [] if element is None else [x for x in element if x.tag.split("}")[-1] == name]


def _first(element, name):
    return next(iter(_children(element, name)), None)


def _attr(element, name, default=""):
    if element is None:
        return default
    return next((v for k, v in element.attrib.items() if k.split("}")[-1] == name), default)


def _transform(raw):
    if not raw:
        return IDENTITY
    try:
        v = [float(x) for x in raw.split()]
    except ValueError as exc:
        raise EstimationError("Transformation 3MF invalide.") from exc
    if len(v) != 12 or not all(math.isfinite(x) for x in v):
        raise EstimationError("Transformation 3MF invalide.")
    return ((v[0], v[3], v[6], v[9]),
            (v[1], v[4], v[7], v[10]),
            (v[2], v[5], v[8], v[11]), (0., 0., 0., 1.))


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4))
                       for j in range(4)) for i in range(4))


def _point(matrix, xyz, scale):
    p = [sum(matrix[i][j] * xyz[j] for j in range(3)) +
         matrix[i][3] for i in range(3)]
    p = [x * scale for x in p]
    if not all(math.isfinite(x) and abs(x) < 100000 for x in p):
        raise EstimationError("Coordonnées 3MF hors limites.")
    return p


def _stl_from_3mf(blob):
    """Extraire la géométrie 3MF, y compris les composants et leurs positions."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except (OSError, zipfile.BadZipFile) as exc:
        raise EstimationError("Fichier 3MF ZIP invalide.") from exc
    with archive as z:
        entries = [x for x in z.infolist() if x.filename.lower().endswith(".model")]
        if not entries or len(entries) > 100:
            raise EstimationError("Aucune géométrie 3D utilisable dans le 3MF.")
        if sum(x.file_size for x in entries) > MAX_XML:
            raise EstimationError("Projet 3MF trop volumineux après décompression.")
        paths = {posixpath.normpath(x.filename.lstrip("/")).lower(): x for x in entries}
        root_path = next((p for p in paths if p.endswith("/3dmodel.model")),
                         next(iter(paths)))
        xml_cache = {}
        seen = set()
        output = io.BytesIO()
        output.write(b"Les Impressions du Fjord - geometrie 3MF".ljust(80, b" "))
        output.write(struct.pack("<I", 0))
        count = 0

        def resolve(path, current):
            if not path:
                return current
            raw = path.replace("\\", "/")
            candidates = [posixpath.normpath(raw.lstrip("/")).lower(),
                          posixpath.normpath(posixpath.join(
                              posixpath.dirname(current), raw)).lower()]
            return next((p for p in candidates if p in paths),
                        None)

        def load(path):
            if path not in xml_cache:
                try:
                    data = z.read(paths[path])
                    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                        raise EstimationError("Métadonnées XML 3MF non permises.")
                    tree = ET.fromstring(data)
                except (ET.ParseError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise EstimationError("Géométrie 3MF illisible.") from exc
                if tree.tag.split("}")[-1] != "model":
                    raise EstimationError("Fichier 3MF sans élément model.")
                scale = UNITS.get(tree.get("unit", "millimeter"), 1)
                objects = {obj.get("id"): obj for obj in
                           _children(_first(tree, "resources"), "object")}
                xml_cache[path] = (tree, objects, scale)
            return xml_cache[path]

        def visit(path, object_id, matrix, depth=0):
            nonlocal count
            if depth > 20 or (path, object_id) in seen:
                raise EstimationError("Composants 3MF circulaires ou trop imbriqués.")
            tree, objects, scale = load(path)
            obj = objects.get(str(object_id))
            if obj is None:
                raise EstimationError("Objet 3MF référencé introuvable.")
            seen.add((path, object_id))
            try:
                mesh = _first(obj, "mesh")
                if mesh is not None:
                    verts = _children(_first(mesh, "vertices"), "vertex")
                    tris = _children(_first(mesh, "triangles"), "triangle")
                    if count + len(tris) > MAX_TRIANGLES:
                        raise EstimationError("Modèle 3MF trop complexe.")
                    points = []
                    for vertex in verts:
                        try:
                            p = [float(vertex.get(k)) for k in ("x", "y", "z")]
                        except (TypeError, ValueError) as exc:
                            raise EstimationError("Sommet 3MF invalide.") from exc
                        points.append(_point(matrix, p, scale))
                    for tri in tris:
                        try:
                            ids = [int(tri.get(k)) for k in ("v1", "v2", "v3")]
                            a, b, c = (points[i] for i in ids)
                            if any(i < 0 for i in ids):
                                raise IndexError()
                        except (IndexError, TypeError, ValueError) as exc:
                            raise EstimationError("Triangle 3MF invalide.") from exc
                        output.write(struct.pack("<12fH", 0, 0, 0, *a, *b, *c, 0))
                        count += 1
                for component in _children(_first(obj, "components"), "component"):
                    target = resolve(_attr(component, "path"), path)
                    if target is None:
                        raise EstimationError("Composant 3MF absent de l'archive.")
                    visit(target, component.get("objectid"),
                          _matmul(matrix, _transform(component.get("transform"))), depth + 1)
            finally:
                seen.remove((path, object_id))

        root, _, _ = load(root_path)
        for item in _children(_first(root, "build"), "item"):
            target = resolve(_attr(item, "path"), root_path)
            if target is None:
                raise EstimationError("Pièce 3MF absente de l'archive.")
            visit(target, item.get("objectid"), _transform(item.get("transform")))
        if count == 0:
            raise EstimationError("Le 3MF ne contient aucun triangle.")
        output.seek(80)
        output.write(struct.pack("<I", count))
        return output.getvalue()


def estimate_model(blob, filename, material="PETG", layer_height=.2, infill=18):
    """Retourne matière et heures estimées à partir d'un G-code FFF générique."""
    if not blob or len(blob) > MAX_MODEL:
        raise EstimationError("Fichier absent ou supérieur à 8 Mo.")
    if material not in DENSITIES:
        raise EstimationError("Matériau non disponible pour l'estimation.")
    if layer_height not in (.08, .12, .2, .28):
        raise EstimationError("Hauteur de couche non prise en charge.")
    if infill not in (10, 15, 18, 20, 30, 40, 50, 75, 100):
        raise EstimationError("Remplissage non pris en charge.")
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".3mf":
        blob = _stl_from_3mf(blob)
    elif ext != ".stl":
        raise EstimationError("Estimation réservée aux fichiers STL et 3MF.")
    if len(blob) < 84:
        raise EstimationError("Géométrie 3D invalide.")
    tool = shutil.which("prusa-slicer")
    if not tool:
        raise EstimationError("Moteur de tranchage indisponible sur le serveur.")
    temp, bed = TEMPERATURES[material]
    with tempfile.TemporaryDirectory(prefix="fjord_quote_") as tmp:
        model = os.path.join(tmp, "piece.stl")
        gcode = os.path.join(tmp, "preview.gcode")
        with open(model, "wb") as handle:
            handle.write(blob)
        command = ["xvfb-run", "-a", tool, "--export-gcode", "--output", gcode,
                   "--center", "128,128", "--bed-shape", "0x0,256x0,256x256,0x256",
                   "--max-print-height", "256", "--layer-height", str(layer_height),
                   "--first-layer-height", str(layer_height), "--nozzle-diameter", "0.4",
                   "--filament-diameter", "1.75", "--fill-density", str(infill) + "%",
                   "--perimeters", "3", "--gcode-flavor", "marlin",
                   "--temperature", str(temp), "--first-layer-temperature", str(temp),
                   "--bed-temperature", str(bed), "--first-layer-bed-temperature", str(bed),
                   model]
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=115,
                                 cwd=tmp, env={**os.environ, "HOME": tmp})
        except subprocess.TimeoutExpired as exc:
            raise EstimationError("Tranchage trop long : simplifie le modèle.") from exc
        except OSError as exc:
            raise EstimationError("Le moteur de tranchage n'a pas pu démarrer.") from exc
        if run.returncode or not os.path.isfile(gcode):
            raise EstimationError("Tranchage impossible pour ce modèle (géométrie ou dimensions).")
        if os.stat(gcode).st_size > 100 * 1024 * 1024:
            raise EstimationError("Résultat de tranchage trop volumineux.")
        try:
            result = parse_gcode(gcode, DENSITIES[material])
        except (ValueError, OverflowError) as exc:
            raise EstimationError("Aucun filament calculable pour cette pièce.") from exc
        grams = result["filament_grams"]
        hours = result["estimated_seconds"] / 3600
        if not math.isfinite(grams) or not math.isfinite(hours) or grams <= 0 or hours <= 0:
            raise EstimationError("Résultat de tranchage invalide.")
        return {"grams": round(grams, 2), "hours": round(hours, 2),
                "layer_height": layer_height, "infill": infill,
                "time_source": result["time_source"],
                "note": "Tranchage FFF générique, buse 0,4 mm : prix indicatif, non calibré sur X2D."}
