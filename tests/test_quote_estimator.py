"""Validation de l'import STL/3MF et de l'estimation privée."""
import io
import os
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from quote_estimator import EstimationError, _stl_from_3mf, estimate_model


def sample_stl():
    return b"Fjord STL".ljust(80, b" ") + struct.pack("<I", 1) + struct.pack(
        "<12fH", 0, 0, 1, 0, 0, 0, 25, 0, 0, 0, 25, 0, 0)


def sample_3mf():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
      <resources>
        <object id="1" type="model"><mesh>
          <vertices><vertex x="0" y="0" z="0"/>
          <vertex x="10" y="0" z="0"/><vertex x="0" y="10" z="0"/></vertices>
          <triangles><triangle v1="0" v2="1" v3="2"/></triangles>
        </mesh></object>
        <object id="2" type="model"><components>
          <component objectid="1" transform="1 0 0 0 1 0 0 0 1 20 5 0"/>
        </components></object>
      </resources>
      <build><item objectid="2"/></build>
    </model>"""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("3D/3dmodel.model", xml)
    return stream.getvalue()


class QuoteEstimatorTests(unittest.TestCase):
    def test_converts_3mf_components_and_transforms(self):
        stl = _stl_from_3mf(sample_3mf())
        self.assertEqual(struct.unpack_from("<I", stl, 80)[0], 1)
        tri = struct.unpack_from("<12fH", stl, 84)
        self.assertEqual(tri[3:12], (20., 5., 0., 30., 5., 0., 20., 15., 0.))

    def test_invalid_3mf_rejected(self):
        with self.assertRaises(EstimationError):
            _stl_from_3mf(b"not an archive")

    def test_slicing_estimates_weights_and_hours(self):
        def fake_slicer(command, **kwargs):
            output = command[command.index("--output") + 1]
            with open(output, "w") as f:
                f.write("; fake output")
            with open(command[-1], "rb") as f:
                self.assertEqual(struct.unpack_from("<I", f.read(), 80)[0], 1)
            return type("Result", (), {"returncode": 0})()

        for filename, blob in [("sample.stl", sample_stl()),
                               ("project.3mf", sample_3mf())]:
            with self.subTest(filename=filename):
                with patch("quote_estimator.shutil.which", return_value="/usr/bin/prusa-slicer"), \
                     patch("quote_estimator.subprocess.run", side_effect=fake_slicer), \
                     patch("quote_estimator.parse_gcode", return_value={
                         "filament_grams": 32.5, "estimated_seconds": 7200,
                         "time_source": "slicer"}):
                    result = estimate_model(blob, filename, "PETG", .2, 18)
                    self.assertEqual(result["grams"], 32.5)
                    self.assertEqual(result["hours"], 2.0)

    def test_unsafe_settings_rejected(self):
        with self.assertRaises(EstimationError):
            estimate_model(sample_stl(), "sample.stl", "PETG", .2, 99)


if __name__ == "__main__":
    unittest.main()
