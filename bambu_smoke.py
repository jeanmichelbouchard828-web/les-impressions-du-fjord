"""Production build smoke test: slice a small cube with the real pinned Bambu CLI.

This is an offline build check only. No printer connection, file transfer,
credentials or command to begin an actual print is involved.
"""
import struct

from bambu_auto import slice_x2d
from bambu_stock_profiles import original_preset
from fjord_printer import verify_sliced_bambu_3mf


def cube_stl(size=8.0):
    v = [
        (0, 0, 0), (size, 0, 0), (size, size, 0), (0, size, 0),
        (0, 0, size), (size, 0, size), (size, size, size), (0, size, size),
    ]
    faces = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    body = b"".join(
        struct.pack("<12fH", *(0.0, 0.0, 0.0, *v[a], *v[b], *v[c], 0))
        for a, b, c in faces
    )
    return b"Fjord X2D official-profile slicer smoke check".ljust(80, b" ") + struct.pack("<I", len(faces)) + body


if __name__ == "__main__":
    presets = {
        "Imprimante": original_preset("Imprimante", "stock:machine:x2d04"),
        "Impression": original_preset("Impression", "stock:process:020"),
        "Filament": original_preset("Filament", "stock:filament:PETG"),
    }
    sliced = slice_x2d(cube_stl(), presets, verify_sliced_bambu_3mf,
                       bed_type="Textured PEI Plate")
    print("Bambu Studio real PETG X2D slice: VALID 3MF (%d bytes)" % len(sliced), flush=True)
