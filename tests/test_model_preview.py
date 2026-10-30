"""Automatic private model thumbnails used by Soumissions PRO."""
import io
import struct
import unittest
import zipfile

from PIL import Image
from model_preview import make_model_preview


def tetra_stl():
    # Four triangular faces so the projection has visible thickness.
    vertices = [(0.,0.,0.), (20.,0.,0.), (0.,15.,0.), (0.,0.,12.)]
    faces = ((0,2,1), (0,1,3), (0,3,2), (1,2,3))
    data = bytearray(b"Fjord test".ljust(80, b" "))
    data.extend(struct.pack("<I", len(faces)))
    for indices in faces:
        coords = [v for idx in indices for v in vertices[idx]]
        data.extend(struct.pack("<12fH", 0,0,0, *coords, 0))
    return bytes(data)


class ModelPreviewTests(unittest.TestCase):
    def assert_png(self, preview):
        self.assertIsNotNone(preview)
        mime, data = preview
        self.assertEqual(mime, "image/png")
        with Image.open(io.BytesIO(data)) as img:
            self.assertEqual(img.size, (640,480))
            self.assertEqual(img.format, "PNG")
            self.assertGreater(len(img.getcolors(640*480) or []), 2)

    def test_binary_stl(self):
        self.assert_png(make_model_preview(tetra_stl(), "piece.stl"))

    def test_ascii_stl(self):
        data = b"""solid tetra
 facet normal 0 0 1
  outer loop
   vertex 0 0 0
   vertex 15 0 0
   vertex 0 15 0
  endloop
 endfacet
 facet normal 1 0 0
  outer loop
   vertex 0 0 0
   vertex 0 15 0
   vertex 0 0 15
  endloop
 endfacet
endsolid tetra
"""
        self.assert_png(make_model_preview(data, "piece.STL"))

    def test_3mf_components(self):
        xml = b"""<?xml version="1.0"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" unit="millimeter">
<resources><object id="1" type="model"><mesh>
<vertices><vertex x="0" y="0" z="0"/><vertex x="20" y="0" z="0"/>
<vertex x="0" y="20" z="0"/><vertex x="0" y="0" z="20"/></vertices>
<triangles><triangle v1="0" v2="1" v3="2"/>
<triangle v1="0" v2="1" v3="3"/><triangle v1="1" v2="2" v3="3"/>
<triangle v1="0" v2="2" v3="3"/></triangles>
</mesh></object></resources>
<build><item objectid="1"/></build></model>"""
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("3D/3dmodel.model", xml)
        self.assert_png(make_model_preview(data.getvalue(), "piece.3mf"))

    def test_invalid_and_unsupported_are_not_rendered(self):
        self.assertIsNone(make_model_preview(b"bad", "test.stl"))
        self.assertIsNone(make_model_preview(b"bad", "test.3mf"))
        self.assertIsNone(make_model_preview(b"{}", "test.json"))


if __name__ == "__main__":
    unittest.main()
