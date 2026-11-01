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

from bambu_auto import full_preset, cli_location, slice_x2d, AutoSliceError
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

    def test_cli_arguments_and_archive_verification(self):
        def run(args, **kwargs):
            self.assertIn("--load-settings",args)
            self.assertIn("--load-filaments",args)
            self.assertEqual(args[args.index("--slice")+1],"0")
            self.assertTrue(args[-1].endswith(".stl"))
            self.assertEqual(args[args.index("--arrange")+1],"1")
            self.assertNotIn("--orient",args)  # Keep original oriented part
            Path(args[args.index("--export-3mf")+1]).write_bytes(sliced_3mf())
            return subprocess.CompletedProcess(args,0,b"success")
        with patch("bambu_auto.cli_location",return_value="/opt/bambu-studio"):
            with patch("bambu_auto.subprocess.run",side_effect=run):
                result=slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)
                self.assertEqual(verify_sliced_bambu_3mf(result),[1])

    def test_unverified_3mf_never_accepted(self):
        with patch("bambu_auto.cli_location",return_value="/opt/bambu-studio"):
            def run(args,**kwargs):
                Path(args[args.index("--export-3mf")+1]).write_bytes(b"bad zip")
                return subprocess.CompletedProcess(args,0,b"fake success")
            with patch("bambu_auto.subprocess.run",side_effect=run):
                with self.assertRaises(ValueError):
                    slice_x2d(stl(),PRESETS,verify_sliced_bambu_3mf)

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
