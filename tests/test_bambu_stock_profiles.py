"""Factory X2D profile inheritance and admin-only stock slicing tests."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import bambu_stock_profiles as stock
from bambu_auto import AutoSliceError
from fjord_printer import register_printer_admin


def write(root, category, name, values):
    target = root / category / (name + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"name": name, **values}), encoding="utf-8")


class StockTests(unittest.TestCase):
    def test_inheritance_includes_real_x2d_start_gcode(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            root = home / "BBL"
            source = home / "path"
            source.write_text(str(root))
            gcode = "M620 M\n" + "G28 X\n" * 550
            write(root, "machine", "machine_base", {
                "printer_model": "Bambu Lab X2D",
                "nozzle_diameter": ["0.4"],
                "machine_start_gcode": "GENERIC START",
                "machine_end_gcode": "M104 S0"
            })
            write(root, "machine", stock.MACHINE_NAME, {
                "inherits": "machine_base",
                "include": ["X2D real machine start"],
                "printer_model": "Bambu Lab X2D",
                "nozzle_diameter": ["0.4"]
            })
            write(root, "machine", "X2D real machine start", {
                "machine_start_gcode": gcode
            })
            write(root, "process", "process_base", {
                "layer_height": "0.2",
                "wall_loops": "3",
                "sparse_infill_density": "15%"
            })
            write(root, "process", stock.PROCESS_NAME, {
                "inherits": "process_base",
                "compatible_printers": [stock.MACHINE_NAME]
            })
            write(root, "filament", "filament_base", {
                "filament_type": ["PETG"],
                "nozzle_temperature": ["240"],
                "filament_flow_ratio": ["0.95"]
            })
            write(root, "filament", stock.STOCK_NAMES["Filament"]["stock:filament:PETG"], {
                "inherits": "filament_base",
                "compatible_printers": [stock.MACHINE_NAME]
            })
            with patch.object(stock, "SYSTEM_PROFILE_ROOT", source):
                machine = stock.original_preset("Imprimante", "stock:machine:x2d04")
                process = stock.original_preset("Impression", "stock:process:020")
                filament = stock.original_preset("Filament", "stock:filament:PETG")
                self.assertEqual(machine["machine_start_gcode"], gcode)
                self.assertEqual(machine["machine_end_gcode"], "M104 S0")
                self.assertEqual(process["wall_loops"], "3")
                self.assertEqual(filament["filament_type"], ["PETG"])
                self.assertEqual(stock.available_original_presets()["Filament"][0]["material"], "PETG")
                with self.assertRaisesRegex(AutoSliceError, "inconnue"):
                    stock.original_preset("Imprimante", "../../secret")
            stock._index.cache_clear()

    def test_refuse_generic_machine_start_and_wrong_filament(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "BBL"
            file = base / "path"
            file.write_text(str(root))
            write(root, "machine", stock.MACHINE_NAME, {
                "printer_model": "Bambu Lab X2D", "nozzle_diameter": ["0.4"],
                "machine_start_gcode": "G28", "machine_end_gcode": "M104 S0"
            })
            (root / "process").mkdir(exist_ok=True)
            (root / "filament").mkdir(exist_ok=True)
            with patch.object(stock, "SYSTEM_PROFILE_ROOT", file):
                with self.assertRaisesRegex(AutoSliceError, "G-code de démarrage"):
                    stock.original_preset("Imprimante", "stock:machine:x2d04")
            stock._index.cache_clear()

    def test_api_lists_factory_and_stock_post_without_touching_custom(self):
        app=Flask("stock-test")
        app.secret_key = "test-secret"
        app.config["TESTING"] = True
        register_printer_admin(app, lambda fn: fn, lambda: None, lambda: "", lambda *a, **k:"ok")
        client=app.test_client()
        stock_values={
            "Imprimante": {"printer_model":"Bambu Lab X2D", "nozzle_diameter":["0.4"],
                "machine_start_gcode":"M620 M\n"+"G28 X\n"*600, "machine_end_gcode":"M104 S0"},
            "Impression": {"layer_height":"0.2", "wall_loops":"3", "sparse_infill_density":"15%"},
            "Filament": {"filament_type":["PETG"],"nozzle_temperature":["240"],
                "filament_flow_ratio":["0.95"]},
        }
        listed={
            "Imprimante":[{"id":"stock:machine:x2d04","name":"Bambu d'origine · X2D","official":True,
                           "model":"Bambu Lab X2D","nozzle":"0.4"}],
            "Impression":[{"id":"stock:process:020","name":"Bambu d'origine · Standard","official":True,
                           "layer":"0.2"}],
            "Filament":[{"id":"stock:filament:PETG","name":"Bambu d'origine · Generic PETG",
                         "official":True,"material":"PETG"}]
        }
        with patch("bambu_stock_profiles.available_original_presets",return_value=listed), \
             patch("bambu_stock_profiles.original_preset",
                   side_effect=lambda cat, choice: stock_values[cat]) as loader, \
             patch("bambu_auto.cli_location",return_value="/opt/bin/bambu-studio"), \
             patch("bambu_auto.slice_x2d",side_effect=AutoSliceError("Simulated test: no slicing")) as slicer:
            response=client.get("/api/admin/atelier/impression-profils")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["profiles"]["Imprimante"][0]["id"],
                             "stock:machine:x2d04")
            # Selected stock IDs do not require the user's old SQL archive.
            mock_stl=bytes(80)+(1).to_bytes(4,"little")+bytes(50)
            values={"stl":(io.BytesIO(mock_stl),"cube.stl"),
                "machine":"stock:machine:x2d04",
                "process":"stock:process:020",
                "filament":"stock:filament:PETG","material":"PETG","bed_type":"Textured PEI Plate"}
            result=client.post("/admin/atelier-imprimer/preparer",data=values,
                               headers={"Accept":"application/json"})
            self.assertEqual(result.status_code,422)
            self.assertIn("Simulated test",result.json["error"])
            self.assertEqual(loader.call_count,3)
            self.assertEqual(slicer.call_count,1)
            invalid=client.post("/admin/atelier-imprimer/preparer",data={
                "stl":(io.BytesIO(mock_stl),"cube.stl"),
                "machine":"stock:machine:not-real",
                "process":"stock:process:020",
                "filament":"stock:filament:PETG","material":"PETG","bed_type":"Textured PEI Plate"},
                headers={"Accept":"application/json"})
            self.assertEqual(invalid.status_code,422)
            self.assertEqual(slicer.call_count,1)


if __name__=="__main__":
    unittest.main()
