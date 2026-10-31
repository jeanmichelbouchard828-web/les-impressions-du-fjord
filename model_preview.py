"""Generate a private, automatic isometric thumbnail for an STL or 3MF.

No browser upload to outside services. We store the PNG alongside the model
so it can also appear on the private quote and the customer's quote PDF.
"""
import io
import math
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

from PIL import Image, ImageDraw

MAX_FACES = 200000
MAX_TRIANGLES = 500000
_FLOAT = rb"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_VERTEX = re.compile(rb"\bvertex\s+(" + _FLOAT + rb")\s+(" + _FLOAT +
                     rb")\s+(" + _FLOAT + rb")", re.I)


def _faces(blob):
    """Sample faces from a binary or ASCII STL; never trust triangle counts."""
    if len(blob) >= 84:
        count = struct.unpack_from("<I", blob, 80)[0]
        if 0 < count <= MAX_TRIANGLES and 84 + count * 50 <= len(blob):
            step = max(1, (count + MAX_FACES - 1) // MAX_FACES)
            for index in range(0, count, step):
                data = struct.unpack_from("<12fH", blob, 84 + index * 50)
                yield (data[3:6], data[6:9], data[9:12])
            return

    # Older CAD tools sometimes export ASCII STL.
    vertices = []
    face_count = 0
    for match in _VERTEX.finditer(blob):
        try:
            vertex = tuple(float(part) for part in match.groups())
        except (ValueError, OverflowError):
            continue
        vertices.append(vertex)
        if len(vertices) == 3:
            face_count += 1
            if face_count > MAX_TRIANGLES:
                raise ValueError("Modèle trop complexe pour l'aperçu.")
            # Stop parsing extremely dense ASCII meshes after a safe sample.
            if face_count <= MAX_FACES:
                yield tuple(vertices)
            vertices = []



def _color_from_3mf(blob):
    """Find the dominant declared model material color without executing 3MF content."""
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            models = [info for info in archive.infolist()
                      if info.filename.lower().endswith(".model") and info.file_size <= 12*1024*1024]
            if not models:
                return None
            root = ET.fromstring(archive.read(models[0]))
            resources = {}
            for group in root.iter():
                kind = group.tag.rsplit("}", 1)[-1].lower()
                if kind not in ("basematerials", "colorgroup"):
                    continue
                group_id = group.get("id")
                if not group_id:
                    continue
                values = []
                for child in group:
                    raw = child.get("displaycolor") or child.get("color")
                    if raw and re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", raw):
                        values.append(raw[:7])
                    else:
                        values.append(None)
                resources[group_id] = values
            counts = Counter()
            for obj in root.iter():
                if obj.tag.rsplit("}", 1)[-1].lower() != "object":
                    continue
                obj_pid = obj.get("pid")
                obj_index = obj.get("pindex", "0")
                for tri in obj.iter():
                    if tri.tag.rsplit("}", 1)[-1].lower() != "triangle":
                        continue
                    pid = tri.get("pid", obj_pid)
                    idx = tri.get("p1", obj_index)
                    try:
                        selected = resources[pid][int(idx)]
                    except (KeyError, ValueError, TypeError, IndexError):
                        continue
                    if selected:
                        counts[selected] += 1
            if counts:
                return counts.most_common(1)[0][0]
            # Some 3MFs specify one material on the object without triangle overrides.
            for obj in root.iter():
                if obj.tag.rsplit("}", 1)[-1].lower() == "object":
                    try:
                        selected = resources[obj.get("pid")][int(obj.get("pindex", "0"))]
                        if selected:
                            return selected
                    except (KeyError, ValueError, TypeError, IndexError):
                        pass
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile, RuntimeError):
        return None
    return None


def _colored_faces_from_3mf(blob):
    """Read mesh triangle colors from a simple 3MF, preserving multicolor parts.

    Return None for component/assembly 3MFs: their transforms require the
    established STL fallback rather than rendering misplaced triangles.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            models = [x for x in archive.infolist()
                      if x.filename.lower().endswith(".model")
                      and x.file_size <= 12 * 1024 * 1024]
            if not models:
                return None
            root = ET.fromstring(archive.read(models[0]))
            lname = lambda elem: elem.tag.rsplit("}", 1)[-1].lower()
            if any(lname(x) == "components" for x in root.iter()):
                return None
            materials = {}
            for group in root.iter():
                if lname(group) not in ("basematerials", "colorgroup"):
                    continue
                colors = []
                for child in group:
                    raw = child.get("displaycolor") or child.get("color") or ""
                    colors.append(raw[:7] if re.fullmatch(
                        r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", raw) else None)
                materials[group.get("id")] = colors

            result = []
            for obj in root.iter():
                if lname(obj) != "object":
                    continue
                mesh = next((x for x in obj if lname(x) == "mesh"), None)
                if mesh is None:
                    continue
                vertices_node = next((x for x in mesh if lname(x) == "vertices"), None)
                triangles_node = next((x for x in mesh if lname(x) == "triangles"), None)
                if vertices_node is None or triangles_node is None:
                    continue
                vertices = [tuple(float(v.get(axis)) for axis in ("x", "y", "z"))
                            for v in vertices_node if lname(v) == "vertex"]
                for tri in triangles_node:
                    if lname(tri) != "triangle":
                        continue
                    if len(result) >= MAX_FACES:
                        break
                    points = tuple(vertices[int(tri.get(k))] for k in ("v1", "v2", "v3"))
                    pid = tri.get("pid", obj.get("pid"))
                    index = tri.get("p1", obj.get("pindex", "0"))
                    try:
                        color = materials[pid][int(index)]
                    except (KeyError, IndexError, TypeError, ValueError):
                        color = None
                    result.append((points, color))
            return result or None
    except (ValueError, OSError, KeyError, TypeError, IndexError,
            OverflowError, ET.ParseError, zipfile.BadZipFile):
        return None

def make_model_preview(blob, filename, size=(640, 480), color="#168ac2"):
    """Return ('image/png', bytes), or None for invalid/unsupported geometry."""
    ext = filename.lower().rsplit(".", 1)[-1]
    colored_faces = None
    if ext == "3mf":
        colored_faces = _colored_faces_from_3mf(blob)
        if colored_faces is None:
            color = _color_from_3mf(blob) or color
            from quote_estimator import _stl_from_3mf
            try:
                blob = _stl_from_3mf(blob)
            except (ValueError, OSError, OverflowError, struct.error):
                return None
    elif ext != "stl":
        return None

    if not re.fullmatch(r"#[0-9a-fA-F]{6}",color):
        color="#168ac2"
    rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
    projected = []
    # Fixed 3/4 view shows both the face and the piece's thickness.
    faces = colored_faces if colored_faces is not None else ((tri, None) for tri in _faces(blob))
    for tri, face_hex in faces:
        if not all(math.isfinite(v) and abs(v) < 100000 for p in tri for v in p):
            continue
        a, b, c = tri
        ab = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
        ac = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
        normal = (ab[1]*ac[2]-ab[2]*ac[1],
                  ab[2]*ac[0]-ab[0]*ac[2],
                  ab[0]*ac[1]-ab[1]*ac[0])
        length = math.sqrt(sum(t*t for t in normal))
        if length < 1e-10:
            continue
        shade = abs((normal[0]*.35 - normal[1]*.4 + normal[2]*.85) / length)
        points = []
        for x, y, z in tri:
            u = .8660254*x - .5*y
            v = -.3535534*x - .6123724*y + .7071068*z
            depth = .3535534*x + .6123724*y + .7071068*z
            points.append((u, v, depth))
        face_rgb = tuple(int(face_hex[i:i+2], 16) for i in (1, 3, 5)) if face_hex else rgb
        projected.append((sum(p[2] for p in points)/3, shade, points, face_rgb))

    if not projected:
        return None

    width, height = size
    minx = min(p[0] for _, _, tri, _ in projected for p in tri)
    maxx = max(p[0] for _, _, tri, _ in projected for p in tri)
    miny = min(p[1] for _, _, tri, _ in projected for p in tri)
    maxy = max(p[1] for _, _, tri, _ in projected for p in tri)
    dx, dy = maxx-minx, maxy-miny
    if max(dx, dy) < 1e-8:
        return None

    scale = min((width - 72) / max(dx, 1e-8),
                (height - 64) / max(dy, 1e-8))
    midx, midy = (minx+maxx)/2, (miny+maxy)/2
    img = Image.new("RGB", (width, height), "#f0f7fb")
    draw = ImageDraw.Draw(img)
    # Painter's algorithm: farther triangles are painted first.
    projected.sort(key=lambda face: face[0])
    for _, shade, tri, face_rgb in projected:
        intensity = .46 + .54 * min(1.0, shade)
        face_color = tuple(max(12,min(255,int(channel*(.50+.50*intensity)))) for channel in face_rgb)
        xy = [(round(width/2 + (p[0]-midx)*scale),
               round(height/2 - (p[1]-midy)*scale)) for p in tri]
        draw.polygon(xy, fill=face_color)

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    data = output.getvalue()
    return ("image/png", data) if len(data) <= 4*1024*1024 else None
