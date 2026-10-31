"""Generate a private, automatic isometric thumbnail for an STL or 3MF.

No browser upload to outside services. We store the PNG alongside the model
so it can also appear on the private quote and the customer's quote PDF.
"""
import io
import math
import re
import struct

from PIL import Image, ImageDraw

MAX_FACES = 16000
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


def make_model_preview(blob, filename, size=(640, 480), color="#168ac2"):
    """Return ('image/png', bytes), or None for invalid/unsupported geometry."""
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "3mf":
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
    for tri in _faces(blob):
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
        projected.append((sum(p[2] for p in points)/3, shade, points))

    if not projected:
        return None

    width, height = size
    minx = min(p[0] for _, _, tri in projected for p in tri)
    maxx = max(p[0] for _, _, tri in projected for p in tri)
    miny = min(p[1] for _, _, tri in projected for p in tri)
    maxy = max(p[1] for _, _, tri in projected for p in tri)
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
    for _, shade, tri in projected:
        intensity = .46 + .54 * min(1.0, shade)
        face_color = tuple(max(12,min(255,int(channel*(.50+.50*intensity)))) for channel in rgb)
        xy = [(round(width/2 + (p[0]-midx)*scale),
               round(height/2 - (p[1]-midy)*scale)) for p in tri]
        draw.polygon(xy, fill=face_color)

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    data = output.getvalue()
    return ("image/png", data) if len(data) <= 4*1024*1024 else None
