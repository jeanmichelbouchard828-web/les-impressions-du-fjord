"""Real FFF toolpath preview powered by PrusaSlicer CLI.

IMPORTANT: G-code uses a generic preview-only machine profile. The G-code is
NEVER offered for machine download or sent to a Bambu printer. It is parsed
server-side to show actual slicer-generated paths and calculate material usage.
"""
import math
import os
import re
import shutil
import subprocess
import tempfile
from flask import Blueprint, jsonify, request

slicer_bp = Blueprint("real_slicer", __name__)
DENSITIES = {"PLA": 1.24, "PETG": 1.27, "ASA": 1.07, "TPU": 1.20}
TOOL = shutil.which("prusa-slicer")
ARG = re.compile(r"([XYZEFS])([-+]?(?:\\d+\\.?\\d*|\\.\\d+))")
FLOAT = r"([-+]?(?:\\d+\\.?\\d*|\\.\\d+))"
MAX_SAMPLES = 80000
MAX_UPLOAD = 8 * 1024 * 1024


def parse_gcode(filename, density):
    """Read real G0/G1 travel/extrusion paths, with bounded memory use.

    Output previews contain sampled path segments from actual G-code, not
    fabricated toolpaths. Layer heights come from actual slicer annotations.
    """
    layers = []
    layer = None
    x = y = z = e = 0.0
    feed = 3600.0
    e_relative = False
    xy_relative = False
    filament_mm = 0.0
    time_seconds = 0.0
    samples = 0
    stride = 1
    seen = 0
    total_extrusions = 0
    total_travels = 0
    file_filament = None
    file_time = None
    skipped = False
    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith(";LAYER_CHANGE") or line.startswith("; layer change"):
                layer = {"z": round(z, 4), "moves": []}
                layers.append(layer)
                continue
            if line.startswith(";Z:") and layer is not None:
                try:
                    layer["z"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
                continue
            if line.startswith(";") and "filament used [mm]" in line:
                try:
                    file_filament = float(line.split("=", 1)[1].strip())
                except (ValueError, IndexError):
                    pass
                continue
            if line.startswith(";") and "estimated printing time (normal mode)" in line:
                try:
                    clock = line.split("=", 1)[1]
                    file_time = sum(float(v) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
                                    for v, unit in re.findall(r"([0-9.]+)\\s*([dhms])", clock))
                except (ValueError, IndexError):
                    pass
                continue
            cmd = line.split(";", 1)[0].strip()
            if cmd in ("M82", "M82 "):
                e_relative = False
                continue
            if cmd in ("M83", "M83 "):
                e_relative = True
                continue
            if cmd == "G90":
                xy_relative = False
                continue
            if cmd == "G91":
                xy_relative = True
                continue
            if cmd.startswith("G92 "):
                args = dict((key, float(value)) for key, value in ARG.findall(cmd))
                x = args.get("X", x)
                y = args.get("Y", y)
                z = args.get("Z", z)
                e = args.get("E", e)
                continue
            if not re.match(r"^G0?1?0?\\s|^G0?1\\s", cmd):
                continue
            args = dict((key, float(value)) for key, value in ARG.findall(cmd))
            nx = x + args.get("X", 0) if xy_relative else args.get("X", x)
            ny = y + args.get("Y", 0) if xy_relative else args.get("Y", y)
            nz = z + args.get("Z", 0) if xy_relative else args.get("Z", z)
            ne = e + args.get("E", 0) if e_relative else args.get("E", e)
            nf = args.get("F", feed)
            delta_e = ne - e
            distance = math.dist((x, y, z), (nx, ny, nz))
            if distance and nf > 0:
                time_seconds += distance / (nf / 60)
            if delta_e > 0 and distance > 0:
                filament_mm += delta_e
            if distance > 1e-6 and (abs(nx-x) > 1e-6 or abs(ny-y) > 1e-6):
                extruding = delta_e > 0
                if extruding:
                    total_extrusions += 1
                else:
                    total_travels += 1
                if layer is None and extruding:
                    layer = {"z": round(max(nz, .01), 4), "moves": []}
                    layers.append(layer)
                if layer is not None:
                    seen += 1
                    if seen % stride == 0 and samples < MAX_SAMPLES:
                        layer["moves"].append([round(x, 3), round(y, 3),
                                               round(nx, 3), round(ny, 3),
                                               1 if extruding else 0])
                        samples += 1
                    elif samples >= MAX_SAMPLES:
                        skipped = True
                        stride *= 2
                        samples = 0
                        for prior in layers:
                            prior["moves"] = prior["moves"][::2]
                            samples += len(prior["moves"])
                        seen = 0
            x, y, z, e, feed = nx, ny, nz, ne, nf

    if not layers or total_extrusions == 0:
        raise ValueError("Le moteur n'a produit aucun trajet d'extrusion.")
    used_mm = file_filament if file_filament is not None and file_filament > 0 else filament_mm
    grams = used_mm * (math.pi * (1.75 / 2) ** 2) / 1000 * density
    seconds = file_time if file_time is not None and file_time > 0 else time_seconds
    return {
        "engine": "PrusaSlicer (real G-code toolpaths)",
        "machine_profile": "Profil FFF générique, buse 0,4 mm — NON compatible X2D pour impression",
        "not_printer_ready": True,
        "layers": layers,
        "layer_count": len(layers),
        "filament_mm": round(used_mm, 2),
        "filament_grams": round(grams, 2),
        "estimated_seconds": round(seconds, 2),
        "time_source": "slicer" if file_time is not None else "G-code feed estimate (without acceleration)",
        "sampled_moves": samples,
        "preview_sampled": skipped or stride > 1,
        "extrusion_moves": total_extrusions,
        "travel_moves": total_travels,
    }


@slicer_bp.post("/api/slice/real")
def slice_real():
    if not TOOL:
        return jsonify(error="Le moteur PrusaSlicer n'est pas installé sur le serveur."), 503
    file = request.files.get("stl")
    if file is None or not (file.filename or "").lower().endswith(".stl"):
        return jsonify(error="Un modèle STL est requis."), 400
    material = request.form.get("material", "PETG").upper()
    if material not in DENSITIES:
        return jsonify(error="Matériau non pris en charge."), 400
    try:
        height = float(request.form.get("layer_height", "0.2"))
    except ValueError:
        return jsonify(error="Hauteur de couche invalide."), 400
    if height not in (.08, .12, .2, .28):
        return jsonify(error="Hauteur de couche non prise en charge."), 400
    blob = file.read(MAX_UPLOAD + 1)
    if len(blob) < 84 or len(blob) > MAX_UPLOAD:
        return jsonify(error="STL vide ou supérieur à 8 Mo."), 413
    # Generic preview only. Never expose this G-code as printable X2D machine code.
    with tempfile.TemporaryDirectory(prefix="fjord_slicer_") as tmp:
        model = os.path.join(tmp, "model.stl")
        gcode = os.path.join(tmp, "result.gcode")
        with open(model, "wb") as out:
            out.write(blob)
        command = ["xvfb-run", "-a", TOOL, "--export-gcode", "--output", gcode,
                   "--center", "128,128", "--bed-shape", "0x0,256x0,256x256,0x256",
                   "--max-print-height", "256", "--layer-height", str(height),
                   "--first-layer-height", str(height), "--nozzle-diameter", "0.4",
                   "--filament-diameter", "1.75", "--fill-density", "18%",
                   "--perimeters", "3", "--gcode-flavor", "marlin",
                   "--temperature", str({"PLA": 210, "PETG": 230, "ASA": 250, "TPU": 220}[material]),
                   "--first-layer-temperature", str({"PLA": 210, "PETG": 230, "ASA": 250, "TPU": 220}[material]),
                   "--bed-temperature", str({"PLA": 60, "PETG": 75, "ASA": 100, "TPU": 50}[material]),
                   "--first-layer-bed-temperature", str({"PLA": 60, "PETG": 75, "ASA": 100, "TPU": 50}[material]),
                   model]
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=115,
                                 cwd=tmp, env={**os.environ, "HOME": tmp})
        except subprocess.TimeoutExpired:
            return jsonify(error="Le tranchage a dépassé 115 secondes. Réduis la complexité du STL."), 504
        except OSError:
            return jsonify(error="PrusaSlicer ne peut pas démarrer sur ce serveur."), 503
        if run.returncode != 0 or not os.path.isfile(gcode):
            detail = (run.stderr or run.stdout or "")[-350:]
            return jsonify(error="Échec du vrai tranchage.", detail=detail), 422
        if os.stat(gcode).st_size > 100 * 1024 * 1024:
            return jsonify(error="G-code trop volumineux pour l'aperçu en ligne."), 413
        try:
            data = parse_gcode(gcode, DENSITIES[material])
            data.update(material=material, layer_height=height)
            return jsonify(data)
        except (ValueError, OverflowError) as exc:
            return jsonify(error=str(exc)), 422
