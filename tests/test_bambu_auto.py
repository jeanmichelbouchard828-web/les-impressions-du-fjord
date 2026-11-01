"""Fail-closed tests for X2D automation and official Bambu Studio CLI integration."""
import io
import os
import json
import subprocess
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from flask import Flask, render_template_string

from bambu_auto import full_preset, cli_location, slice_x2d, AutoSliceError, cli_preset
from fjord_printer import register_printer_admin, verify_sliced_bambu_3mf


MACHINE = {
 "printer_model": "Bambu Lab X2D", "nozzle_diameter":["0.4"],
 "machine_start_gcode":"G28\n", "machine_end_gcode":"M104 S0\n",
}
PROCESS = {"layer_height":"0.2", "wall_loops":"3", "sparse_infill_density":"15%"}
FILAMENT = {"filament_type":["PLA"],"nozzle_temperature":["215"],
            "filament_flow_ratio":["0.95"]}
PRESETS = {"Imprimante":json.dumps(MACHINE),"Impression":json.dumps(PROCESS),
           "Filament":json.dumps(FILAMENT)}


def stl():
    # One flat triangle with the 50-byte STL triangle record.
    import struct
    return bytes(80)+struct.pack("<I",1)+struct.pack("<12fH",0,0,1,0,0,0,10,0,0,0,10,0,0)


def sliced_3mf():
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("3D/3dmodel.model","<model>test</model>")
        z.writestr("Metadata/plate_1.gcode","; sliced by Bambu Studio\nG28\n"*20)
    return output.getvalue()


class AutoTests(unittest.TestCase):
    def test_no_engine_means_no_printer_or_slicer_call(self):
        with patch("bambu_auto.cli_location",return_value=None):
            with patch("bambu_auto.subprocess.run") as called:
                with self.assertRaisesRegex(AutoSliceError,"non installé"):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)
                called.assert_not_called()

    def test_reject_inherited_partial_wrong_machine_and_invalid_stl(self):
        with self.assertRaisesRegex(AutoSliceError,"partiel"):
            full_preset({"inherits":"Default","printer_model":"X2D"},"Imprimante")
        with self.assertRaisesRegex(AutoSliceError,"X2D"):
            full_preset({**MACHINE,"printer_model":"P1S"},"Imprimante")
        with patch("bambu_auto.cli_location",return_value="/bin/true"):
            for bad in [b"x", stl()[:-1], stl()+bytes(1)]:
                with self.assertRaises(AutoSliceError):
                    slice_x2d(bad,PRESETS,verify_sliced_bambu_3mf)

    def test_stock_source_metadata_is_normalized_without_changing_machine_gcode(self):
        original = {**MACHINE, "from": "System", "type": "machine"}
        fixed = cli_preset(original, "Imprimante")
        self.assertEqual(fixed["from"], "system")
        self.assertEqual(fixed["type"], "machine")
        self.assertEqual(fixed["machine_start_gcode"], original["machine_start_gcode"])
        self.assertEqual(original["from"], "System")
        self.assertEqual(cli_preset({**PROCESS, "from": "System"}, "Impression")["type"], "process")
        self.assertEqual(cli_preset({**FILAMENT, "from": "System"}, "Filament")["type"], "filament")
        with self.assertRaisesRegex(AutoSliceError, "inconnue"):
            cli_preset({**FILAMENT, "from": "Untrusted"}, "Filament")

    def test_cli_arguments_and_archive_verification(self):
        def run(args, **kwargs):
            self.assertIn("--load-settings",args)
            self.assertIn("--load-filaments",args)
            self.assertEqual(args[args.index("--slice")+1],"0")
            self.assertTrue(args[-1].endswith(".stl"))
            self.assertEqual(args[args.index("--arrange")+1],"1")
            self.assertNotIn("--curr-bed-type",args)  # Unsupported by official Bambu CLI
            machine_path = Path(args[args.index("--load-settings")+1].split(";")[0])
            process_path = Path(args[args.index("--load-settings")+1].split(";")[1])
            filament_path = Path(args[args.index("--load-filaments")+1])
            self.assertEqual(json.loads(machine_path.read_text())["type"],"machine")
            self.assertEqual(json.loads(process_path.read_text())["curr_bed_type"],"Textured PEI Plate")
            self.assertEqual(json.loads(filament_path.read_text())["type"],"filament")
            self.assertNotIn("--orient",args)  # Keep original oriented part
            self.assertIn("--outputdir",args)
            destination=Path(args[args.index("--outputdir")+1])
            self.assertTrue(destination.is_dir())
            filename=args[args.index("--export-3mf")+1]
            self.assertEqual(filename,"x2d_tranche.gcode.3mf")
            self.assertNotIn("/",filename)  # Bambu expects a relative output name.
            (destination/filename).write_bytes(sliced_3mf())
            return subprocess.CompletedProcess(args,0,b"success")
        with patch("bambu_auto.cli_location",return_value="/opt/bambu-studio"):
            with patch("bambu_auto.subprocess.run",side_effect=run):
                result=slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)
                self.assertEqual(verify_sliced_bambu_3mf(result),[1])

    def test_plate_names_match_bambu_enum_and_zero_temperature_is_rejected(self):
        from bambu_auto import BED_TYPES
        self.assertEqual(BED_TYPES["Cool Plate SuperTack"][0],"Supertack Plate")
        self.assertEqual(BED_TYPES["Smooth PEI Plate / High Temp Plate"][0],"High Temp Plate")
        petg={**FILAMENT,"filament_type":["PETG"],
              "cool_plate_temp":["0"],"supertack_plate_temp":["70"]}
        with patch("bambu_auto.cli_location",return_value="/bin/true"):
            with patch("bambu_auto.subprocess.run") as called:
                with self.assertRaisesRegex(AutoSliceError,"ne permet pas"):
                    slice_x2d(stl(),{**PRESETS,"Filament":petg},
                              verify_sliced_bambu_3mf,bed_type="Cool Plate")
                called.assert_not_called()

    def test_unknown_bed_type_rejected_before_slicer_or_printer(self):
        with patch("bambu_auto.subprocess.run") as called:
            with self.assertRaisesRegex(AutoSliceError, "plateau X2D inconnu"):
                slice_x2d(stl(), PRESETS, verify_sliced_bambu_3mf, bed_type="Unknown")
            called.assert_not_called()

    def test_unverified_3mf_never_accepted(self):
        with patch("bambu_auto.cli_location",return_value="/opt/bambu-studio"):
            def run(args,**kwargs):
                Path(args[args.index("--export-3mf")+1]).write_bytes(b"bad zip")
                return subprocess.CompletedProcess(args,0,b"fake success")
            with patch("bambu_auto.subprocess.run",side_effect=run):
                with self.assertRaises(ValueError):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)

    def test_failure_diagnostics_distinguish_missing_output_and_bad_profiles(self):
        with patch("bambu_auto.cli_location",return_value="/opt/bambu-studio"):
            with patch("bambu_auto.subprocess.run",return_value=subprocess.CompletedProcess([],0,b"finished")):
                with self.assertRaisesRegex(AutoSliceError,"sans produire le 3MF"):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)
            failed=subprocess.CompletedProcess([],3,b"Error loading filament preset: /tmp/secret path")
            with patch("bambu_auto.subprocess.run",return_value=failed):
                with self.assertRaisesRegex(AutoSliceError,"profils choisis"):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)
            missing=subprocess.CompletedProcess([],127,
                b"error while loading shared libraries: libwebkit2gtk-4.1.so.0: cannot open shared object file")
            with patch("bambu_auto.subprocess.run",return_value=missing):
                with self.assertRaisesRegex(AutoSliceError,"libwebkit2gtk-4.1.so.0"):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)
            crashed=subprocess.CompletedProcess([],-11,b"segmentation fault")
            with patch("bambu_auto.subprocess.run",return_value=crashed):
                with self.assertRaisesRegex(AutoSliceError,"signal 11"):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)

    def test_profile_summary_avoids_leaking_slicer_machine_gcode(self):
        class FakeDb:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def execute(self,query,args=None):
                if "SELECT id,name,category,settings" in query:
                    return self
                raise AssertionError(query)
            def fetchall(self):
                return [
                    {"id":11,"name":"X2D P0.4","category":"Imprimante",
                     "settings":json.dumps(MACHINE)},
                    {"id":12,"name":"0.20 mm","category":"Impression",
                     "settings":json.dumps(PROCESS)},
                    {"id":13,"name":"PLA 215","category":"Filament",
                     "settings":json.dumps(FILAMENT)},
                    {"id":14,"name":"partial","category":"Filament",
                     "settings":'{"inherits":"Generic PLA"}'},
                ]
        app=Flask("x2d-summary")
        app.secret_key="test"
        register_printer_admin(app,lambda fn:fn,lambda:None,lambda:"",
                               lambda title,html,**kw:render_template_string(html,**kw),
                               db=FakeDb)
        with patch("bambu_auto.cli_location",return_value="/opt/bambu"):
            result=app.test_client().get("/api/admin/atelier/impression-profils")
        self.assertEqual(result.status_code,200)
        info=result.json
        self.assertEqual(len(info["profiles"]["Filament"]),1)
        self.assertEqual(info["profiles"]["Filament"][0]["material"],"PLA")
        self.assertEqual(info["profiles"]["Imprimante"][0]["nozzle"],"0.4")
        self.assertEqual(info["profiles"]["Impression"][0]["layer"],"0.2")
        self.assertNotIn("machine_start_gcode",result.get_data(as_text=True))

    def test_filament_mismatch_never_slices_or_uploads(self):
        class FakeDb:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def execute(self,query,args=None):
                assert "WHERE id = ANY" in query
                return self
            def fetchall(self):
                return [
                    {"id":11,"name":"X2D","category":"Imprimante",
                     "settings":json.dumps(MACHINE)},
                    {"id":12,"name":"Process","category":"Impression",
                     "settings":json.dumps(PROCESS)},
                    {"id":13,"name":"PETG","category":"Filament",
                     "settings":json.dumps({**FILAMENT,"filament_type":["PETG"]})},
                ]
        app=Flask("x2d-material-guard")
        app.secret_key="test"
        app.config["TESTING"]=True
        register_printer_admin(app,lambda fn:fn,lambda:None,lambda:"",
                               lambda title,html,**kw:render_template_string(html,**kw),
                               db=FakeDb)
        with patch("bambu_auto.cli_location",return_value="/opt/bambu"), \
             patch("fjord_printer._upload") as upload, \
             patch("fjord_printer._status") as printer_status, \
             patch("fjord_printer.slice_x2d",create=True) as slice_mock:
            response=app.test_client().post("/admin/atelier-imprimer/preparer",
                data={"stl":(io.BytesIO(stl()),"creation.stl"),"machine":"11",
                      "process":"12","filament":"13","material":"PLA","bed_type":"Textured PEI Plate"},
                headers={"Accept":"application/json"},content_type="multipart/form-data")
            self.assertEqual(response.status_code,422,response.get_data(as_text=True))
            self.assertFalse(response.json["ok"])
            self.assertIn("incompatible",response.json["error"])
            upload.assert_not_called()
            printer_status.assert_not_called()
            slice_mock.assert_not_called()

    def test_admin_auto_endpoint_only_when_engine_ready(self):
        app=Flask("x2d-auto")
        app.secret_key="test"
        app.config["TESTING"]=True
        register_printer_admin(app,lambda fn:fn,lambda:None,lambda:"<input name=csrf>",
                               lambda title,html,**kw:render_template_string(html,**kw))
        client=app.test_client()
        with patch("bambu_auto.cli_location",return_value=None):
            res=client.get("/api/admin/atelier/impression-profils")
            self.assertEqual(res.status_code,200)
            self.assertFalse(res.json["engine_ready"])
            with patch("fjord_printer._upload") as upload:
                response=client.post("/admin/atelier-imprimer/preparer",data={
                    "stl":(io.BytesIO(stl()),"creation.stl"),"machine":"1",
                    "process":"2","filament":"3"
                },content_type="multipart/form-data")
                self.assertEqual(response.status_code,302)
                upload.assert_not_called()
        with patch("fjord_printer._api",side_effect=ValueError("offline")):
            pass


if __name__=="__main__":
    unittest.main()
