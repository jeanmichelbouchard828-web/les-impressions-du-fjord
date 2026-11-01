"""Safety tests for owner-only Bambu printing through OctoEverywhere."""
import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch
from flask import Flask, render_template_string
from fjord_printer import (
    _safe_virtual_path, _printer_files, _status, _connection, _api, _upload,
    verify_sliced_bambu_3mf, PrinterError, register_printer_admin,
)

def make_3mf(sliced=True):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("3D/3dmodel.model","<model>test</model>")
        if sliced:
            z.writestr("Metadata/plate_1.gcode","; Bambu Studio sliced\nG28\nG1 X1 Y1 E1\n"*20)
    return stream.getvalue()

def fake_api(path,method="GET",payload=None,timeout=9):
    if path=="/status":
        return {"Features":32,"JobStatus":{"State":"idle","CurrentPrint":{}}}
    if path=="/files/list":
        return {"Root":[{"Type":"folder","Name":"gcode","Children":[
            {"Type":"file","Name":"X2D_test.3mf","VirtualPath":"gcode/X2D_test.3mf","SizeBytes":1401},
            {"Type":"file","Name":"model.stl","VirtualPath":"gcode/model.stl"}]}]}
    if path=="/start" and method=="POST":
        return {"VirtualPath":payload["Path"]}
    raise AssertionError(f"Unexpected printer operation: {method} {path}")

class RemotePrintTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__)
        app.secret_key="testing-only"
        app.config["TESTING"]=True
        register_printer_admin(app,lambda f:f,lambda:None,
                               lambda:'<input name="csrf" value="test">',
                               lambda name,html,**kw:render_template_string(html,**kw))
        self.client=app.test_client()

    def test_plain_object_3mf_rejected_because_not_sliced(self):
        with self.assertRaisesRegex(PrinterError,"aucune plaque tranchée"):
            verify_sliced_bambu_3mf(make_3mf(sliced=False))

    def test_valid_sliced_bambu_3mf_plate(self):
        self.assertEqual(verify_sliced_bambu_3mf(make_3mf()),[1])

    def test_corrupted_and_zip_traversal_are_rejected(self):
        with self.assertRaises(PrinterError):
            verify_sliced_bambu_3mf(b"not a 3mf"*30)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w") as z:
            z.writestr("3D/3dmodel.model","model")
            z.writestr("Metadata/plate_1.gcode","G1"*300)
            z.writestr("../outside","bad")
        with self.assertRaisesRegex(PrinterError,"dangereux"):
            verify_sliced_bambu_3mf(stream.getvalue())

    def test_path_validation(self):
        assert _safe_virtual_path("gcode/fjord_123.3mf")
        for p in ["gcode/foo.gcode","gcode/../p.3mf","config/foo.3mf",
                  "gcode/folder//t.3mf","https://example.com/t.3mf","gcode/a.3mf?x=1"]:
            self.assertFalse(_safe_virtual_path(p),p)

    def test_filename_list_filters_non3mf_and_unsafe_paths(self):
        files=_printer_files({"Root":[{"Type":"folder","Children":[
            {"Type":"file","VirtualPath":"gcode/part.3mf","Name":"Part"},
            {"Type":"file","VirtualPath":"gcode/part.gcode","Name":"Hidden"},
            {"Type":"file","VirtualPath":"gcode/../bad.3mf","Name":"Danger"}]}]})
        self.assertEqual([x["path"] for x in files],["gcode/part.3mf"])

    def test_connection_rejects_ssrf(self):
        for url in ["http://printer.lan","https://localhost",
                    "https://foo.octoeverywhere.com.evil.net",
                    "https://user:pass@abc.octoeverywhere.com",
                    "https://abc.octoeverywhere.com:443",
                    "https://abc.octoeverywhere.com/path"]:
            with patch.dict(os.environ,{"OCTOEVERYWHERE_CONNECTION_URL":url}):
                with self.assertRaises(PrinterError): _connection()

    def test_no_redirect_follows_for_secret_auth(self):
        # Transport must use explicit no-redirect opener.
        import fjord_printer
        class FakeOpener:
            def open(self, req, timeout):
                raise IOError("offline")
        with patch.dict(os.environ,{"OCTOEVERYWHERE_CONNECTION_URL":"https://abc.octoeverywhere.com"}):
            with patch.object(fjord_printer.urllib.request,"build_opener",return_value=FakeOpener()) as opener:
                with self.assertRaises(PrinterError): _api("/status")
                self.assertTrue(any(arg is fjord_printer._NoRedirect for arg in opener.call_args.args))

    def test_no_auth_admin_pages_are_not_published(self):
        # Verify production path semantics for registration decorator.
        app=Flask("auth-test")
        app.secret_key="test"
        def deny(f):
            def wrapper(*a,**kw):return "Unauthorized",401
            wrapper.__name__=f.__name__
            return wrapper
        register_printer_admin(app,deny,lambda:None,lambda:"",
                               lambda title,html,**kw:render_template_string(html,**kw))
        client=app.test_client()
        self.assertEqual(client.get("/admin/atelier-imprimer").status_code,401)
        self.assertEqual(client.post("/admin/atelier-imprimer/demarrer").status_code,401)
        self.assertEqual(client.post("/admin/atelier-imprimer/envoyer").status_code,401)

    def test_page_shows_printer_ready_and_sliced_upload_only(self):
        with patch("fjord_printer._api",side_effect=fake_api):
            r=self.client.get("/admin/atelier-imprimer")
            self.assertEqual(r.status_code,200)
            text=r.data.decode("utf-8")
            self.assertIn("gcode/X2D_test.3mf",text)
            self.assertIn("3MF déjà tranché",text)
            self.assertNotIn("model.stl",text)
            self.assertIn('name="nonce"',text)

    def test_responsive_print_dashboard_sections_and_safety_forms(self):
        with patch("fjord_printer._api",side_effect=fake_api):
            response=self.client.get("/admin/atelier-imprimer")
        self.assertEqual(response.status_code,200)
        html=response.data.decode("utf-8")
        for marker in ('id="fjordPrintPage"', 'id="fjordPrintTitle"',
                       'class="fj-print-layout"', 'id="fjordPrintUpload"',
                       'id="fjordPrintRemote"', 'id="fjordPrintPlate"',
                       'id="fjordPrintFileName"', 'name="verified" value="yes" required',
                       'name="cleared" value="yes" required',
                       'onsubmit="return confirm(', '@media(max-width:540px)',
                       'href="/admin/atelier-3d"', 'href="/admin/profils-bambu"'):
            self.assertIn(marker,html,marker)
        self.assertIn('action="/admin/atelier-imprimer/envoyer"',html)
        self.assertIn('action="/admin/atelier-imprimer/demarrer"',html)
        self.assertIn('gcode/X2D_test.3mf',html)
        self.assertEqual(html.count('id="fjordPrintPage"'),1)
        self.assertNotIn('data-slice-automatically',html)
        self.assertIn('id="fjordAutoSliceCard"',html)
        self.assertIn('Moteur Bambu Studio absent',html)

    def test_dashboard_offline_keeps_send_and_start_disabled(self):
        with patch("fjord_printer._api",side_effect=PrinterError("Connexion absente")):
            html=self.client.get("/admin/atelier-imprimer").data.decode("utf-8")
        self.assertIn('id="fjordPrintPage"',html)
        self.assertIn('Connexion absente',html)
        self.assertIn('📤 Envoyer à la X2D</button>',html)
        self.assertIn('disabled>📤 Envoyer à la X2D',html)
        self.assertNotIn('action="/admin/atelier-imprimer/demarrer"',html)

    def test_explicit_checkboxes_required_and_nonce_one_time(self):
        with patch("fjord_printer._api",side_effect=fake_api) as call:
            self.client.get("/admin/atelier-imprimer")
            with self.client.session_transaction() as sess:
                nonce=sess["fjord_print_nonce"]
            bad=self.client.post("/admin/atelier-imprimer/demarrer",data={
                "path":"gcode/X2D_test.3mf","plate":"1","nonce":nonce})
            self.assertEqual(bad.status_code,400)
            self.assertFalse(any(c.args[0]=="/start" for c in call.call_args_list))
            # nonce is consumed even after failed safety confirmation.
            retry=self.client.post("/admin/atelier-imprimer/demarrer",data={
                "path":"gcode/X2D_test.3mf","plate":"1","nonce":nonce,
                "verified":"yes","cleared":"yes"})
            self.assertEqual(retry.status_code,400)

    def test_busy_printer_must_not_start(self):
        def busy(path,**kw):
            if path=="/status": return {"Features":32,"JobStatus":{"State":"printing"}}
            return fake_api(path,**kw)
        with patch("fjord_printer._api",side_effect=busy) as call:
            self.client.get("/admin/atelier-imprimer")
            with self.client.session_transaction() as sess: nonce=sess["fjord_print_nonce"]
            reply=self.client.post("/admin/atelier-imprimer/demarrer",data={
                "path":"gcode/X2D_test.3mf","plate":"1","nonce":nonce,
                "verified":"yes","cleared":"yes"},follow_redirects=True)
            self.assertEqual(reply.status_code,200)
            self.assertIn(b"occup",reply.data)
            self.assertFalse(any(c.args[0]=="/start" for c in call.call_args_list))

    def test_feature_flag_controls_start(self):
        with patch("fjord_printer._api",return_value={"Features":0,"JobStatus":{"State":"idle"}}):
            self.assertFalse(_status()["can_start"])

    def test_explicit_start_sends_only_selected_printer_file(self):
        with patch("fjord_printer._api",side_effect=fake_api) as call:
            self.client.get("/admin/atelier-imprimer")
            with self.client.session_transaction() as sess: nonce=sess["fjord_print_nonce"]
            r=self.client.post("/admin/atelier-imprimer/demarrer",data={
                "path":"gcode/X2D_test.3mf","plate":"1","nonce":nonce,
                "verified":"yes","cleared":"yes","ams":"yes"})
            self.assertEqual(r.status_code,302)
            starts=[c for c in call.call_args_list if c.args[0]=="/start"]
            self.assertEqual(len(starts),1)
            self.assertEqual(starts[0].kwargs["payload"],{
                "Path":"gcode/X2D_test.3mf","Plate":1,"UseAms":True})

    def test_upload_never_starts_printer_automatically(self):
        with patch("fjord_printer._api",side_effect=fake_api) as call:
            with patch("fjord_printer._upload",return_value={"VirtualPath":"gcode/x.3mf"}) as upload:
                r=self.client.post("/admin/atelier-imprimer/envoyer",data={
                    "sliced_file":(io.BytesIO(make_3mf()),"sliced_bambu.3mf")
                },content_type="multipart/form-data")
            self.assertEqual(r.status_code,302)
            self.assertEqual(upload.call_count,1)
            self.assertFalse(any(c.args[0]=="/start" for c in call.call_args_list))

if __name__=="__main__": unittest.main()
