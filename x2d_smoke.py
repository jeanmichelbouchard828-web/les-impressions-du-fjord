"""Offline X2D CLI smoke test during Docker builds.

Slices a synthetic cube with bundled manufacturer X2D/PETG presets, checks
the actual machine-ready 3MF, and never contacts the printer or internet.
"""
from __future__ import annotations

import struct

from bambu_auto import slice_x2d
from bambu_stock_profiles import original_preset
from fjord_printer import verify_sliced_bambu_3mf


def test_cube_stl():
    # 12-triangle watertight rectangular cube; no external files or libraries.
    p = (
        (0., 0., 0.), (14., 0., 0.), (14., 14., 0.), (0., 14., 0.),
        (0., 0., 3.), (14., 0., 3.), (14., 14., 3.), (0., 14., 3.),
    )
    faces = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    )
    payload = bytearray(b"Fjord X2D offline smoke test".ljust(80, b" "))
    payload += struct.pack("<I", len(faces))
    for a, b, c in faces:
        ax, ay, az = p[a]
        bx, by, bz = p[b]
        cx, cy, cz = p[c]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        length = (nx * nx + ny * ny + nz * nz) ** .5
        assert length > 0
        payload += struct.pack("<12fH", nx / length, ny / length, nz / length,
                               *p[a], *p[b], *p[c], 0)
    return bytes(payload)


if __name__ == "__main__":
    presets = {
        "Imprimante": original_preset("Imprimante", "stock:machine:x2d04"),
        "Impression": original_preset("Impression", "stock:process:020"),
        "Filament": original_preset("Filament", "stock:filament:PETG"),
    }
    sliced = slice_x2d(test_cube_stl(), presets, verify_sliced_bambu_3mf,
                       bed_type="Cool Plate SuperTack")
    assert verify_sliced_bambu_3mf(sliced) == [1]
    print("X2D Bambu official PETG SuperTack: real 3MF slice succeeded; no printer contacted.")
