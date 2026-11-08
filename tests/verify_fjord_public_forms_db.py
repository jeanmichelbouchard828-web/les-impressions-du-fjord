"""Isolated PostgreSQL end-to-end tests for the public business flow.

This file intentionally REFUSES to run against any non-local database.
No actual payment, email or printer command is sent.
"""
import io
import os
import re
from urllib.parse import urlsplit
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

db_url=os.environ.get("DATABASE_URL","")
parsed=urlsplit(db_url)
if parsed.hostname not in {"localhost","127.0.0.1"} or parsed.path!="/fjord_ci_test":
    raise RuntimeError("This test requires the disposable localhost /fjord_ci_test database.")
if os.environ.get("FJORD_PREVIEW_MODE")=="1":
    raise RuntimeError("CI form tests need their isolated local non-preview mode.")
for key in ("SMTP_HOST","STRIPE_SECRET_KEY","STRIPE_WEBHOOK_SECRET","OCTOEVERYWHERE_CONNECTION_URL"):
    if os.environ.get(key):
        raise RuntimeError("Forbidden external integration during isolated form tests: "+key)

from PIL import Image
from app import app,db

BASE="https://localhost"

def csrf_from(html):
    found=re.search(r'<input[^>]+name="csrf"[^>]+value="([^"]+)"',html)
    if not found:
        raise AssertionError("CSRF input missing")
    return found.group(1)

class IsolatedBusinessFlow(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()

    def get(self,path):
        return self.client.get(path,base_url=BASE)

    def post(self,path,values):
        return self.client.post(path,base_url=BASE,data=values)

    def test_legacy_bambu_preset_reset_snapshot_and_one_time_only(self):
        """Runs ONLY on disposable localhost fjord_ci_test, never a real library."""
        from flask import Flask
        from bambu_presets import register_bambu_preset_library
        reset_id="reinitialisation-bbcfg-nouveaux-profils-20261108-v1"
        old_sig="a"*64
        new_sig="b"*64
        def register():
            sandbox=Flask("fjord-ci-bambu-reset-"+str(__import__('secrets').token_hex(4)))
            register_bambu_preset_library(
                sandbox,db,lambda fn:fn,lambda:None,lambda:"",
                lambda *args,**kwargs:"test")
        with db() as conn:
            conn.execute("DELETE FROM bambu_user_presets_reset_events WHERE reset_id=%s",
                         (reset_id,))
            conn.execute("DELETE FROM bambu_user_presets WHERE signature IN (%s,%s)",
                         (old_sig,new_sig))
            conn.execute("""INSERT INTO bambu_user_presets
                 (name,category,source_file,internal_path,settings,signature)
                 VALUES(%s,%s,%s,%s,%s,%s)""",
                 ("OLD ci profile","Filament","old.bbscfg","filament/old.json",
                  '{"name":"OLD ci profile","filament_type":["PLA"]}',old_sig))
        register()
        with db() as conn:
            self.assertIsNone(conn.execute(
                "SELECT id FROM bambu_user_presets WHERE signature=%s",
                (old_sig,)).fetchone())
            saved=conn.execute("""SELECT original_id FROM bambu_user_presets_reset_backup
                 WHERE reset_id=%s AND signature=%s""",
                 (reset_id,old_sig)).fetchone()
            self.assertIsNotNone(saved)
            conn.execute("""INSERT INTO bambu_user_presets
                 (name,category,source_file,internal_path,settings,signature)
                 VALUES(%s,%s,%s,%s,%s,%s)""",
                 ("NEW ci BBCFG","Filament","new.bbscfg","filament/new.json",
                  '{"name":"NEW ci BBCFG","filament_type":["PETG"]}',new_sig))
        register()
        with db() as conn:
            self.assertIsNotNone(conn.execute(
                "SELECT id FROM bambu_user_presets WHERE signature=%s",
                (new_sig,)).fetchone())
            row=conn.execute(
                "SELECT COUNT(*) AS n FROM bambu_user_presets_reset_events WHERE reset_id=%s",
                (reset_id,)).fetchone()
            self.assertEqual(row["n"],1)

    def test_private_atelier_exposes_three_bambu_profile_selectors(self):
        import hashlib
        import datetime
        token="fjord-ci-private-atelier-profiles"
        digest=hashlib.sha256(token.encode()).hexdigest()
        with db() as conn:
            conn.execute("""INSERT INTO sessions(tokenhash,expires) VALUES(%s,%s)
             ON CONFLICT (tokenhash) DO NOTHING""",
                (digest,datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)))
        with self.client.session_transaction() as session:
            session["admin_token"]=token
        response=self.get("/admin/atelier-3d")
        self.assertEqual(response.status_code,200)
        text=response.get_data(as_text=True)
        for expected in ('id="fjordBambuProfileBar"','id="fjordProfileMachine"',
                         'id="fjordProfileProcess"','id="fjordProfileFilament"',
                         '/static/fjord_profile_toolbar.css'):
            self.assertIn(expected,text)
        self.assertIn("fjord-x2d-profile-preferences-v2",text)
        self.assertNotIn("fjord-x2d-profile-preferences-v1",text)
        public=self.get("/atelier-3d").get_data(as_text=True)
        self.assertNotIn('id="fjordBambuProfileBar"',public)

    def test_quote_submission_and_private_tracking(self):
        page=self.get("/soumission")
        self.assertEqual(page.status_code,200)
        token=csrf_from(page.get_data(as_text=True))
        valid={"csrf":token,"name":"Test Client","email":"fjord-ci-quote@example.invalid",
               "phone":"","description":"Pièce de fixation de test, 72 mm, 2 exemplaires.",
               "material":"PETG-CF","quantity":"2","color":"Bleu"}
        response=self.post("/soumission",valid)
        self.assertEqual(response.status_code,200,response.get_data(as_text=True)[:650])
        self.assertIn("Merci pour votre demande",response.get_data(as_text=True))
        with db() as conn:
            record=conn.execute("""SELECT id,kind,name,email,material,description,status
                FROM requests WHERE email=%s ORDER BY id DESC LIMIT 1""",
                (valid["email"],)).fetchone()
        self.assertIsNotNone(record)
        self.assertEqual(record["kind"],"Soumission")
        self.assertEqual(record["material"],"PETG-CF")
        self.assertIn("Quantité demandée : 2",record["description"])
        self.assertIn("Couleur souhaitée : Bleu",record["description"])
        self.assertEqual(record["status"],"Demande reçue")
        self.assertIn(f"#{record['id']}",response.get_data(as_text=True))
        tracker=self.get("/suivi")
        self.assertEqual(tracker.status_code,200)
        track_response=self.post("/suivi",{
            "csrf":csrf_from(tracker.get_data(as_text=True)),
            "numero":str(record["id"]),"email":valid["email"]})
        self.assertEqual(track_response.status_code,200)
        self.assertIn("Demande reçue",track_response.get_data(as_text=True))

    def test_project_brief_is_validated_and_retained(self):
        response=self.get("/soumission")
        page=response.get_data(as_text=True)
        for name in ("project_type","dimensions","remise","delai"):
            self.assertIn('name="'+name+'"',page)
        token=csrf_from(page)
        values={"csrf":token,"name":"Client avec mesures","email":"fjord-ci-brief@example.invalid",
                "description":"Un support fonctionnel pour un appareil.","quantity":"3","color":"Bleu",
                "material":"PETG","project_type":"Prototype","dimensions":"120 x 80 x 30 mm",
                "remise":"À discuter","delai":"Flexible"}
        result=self.post("/soumission",values)
        self.assertEqual(result.status_code,200)
        with db() as conn:
            row=conn.execute("SELECT description FROM requests WHERE email=%s",(values["email"],)).fetchone()
        self.assertIn("Type de projet : Prototype",row["description"])
        self.assertIn("Dimensions approximatives : 120 x 80 x 30 mm",row["description"])
        self.assertIn("Quantité demandée : 3",row["description"])
        self.assertIn("Remise souhaitée : À discuter",row["description"])
        for patch in ({"project_type":"Choix invalide"},
                      {"remise":"livraison gratuite garantie"},
                      {"delai":"demain absolument"},
                      {"dimensions":"test\nligne"}):
            invalid=self.post("/soumission",dict(values,**patch))
            with self.subTest(invalid=patch):
                self.assertEqual(invalid.status_code,400)

    def test_contact_message_is_stored(self):
        view=self.get("/contact")
        self.assertEqual(view.status_code,200)
        token=csrf_from(view.get_data(as_text=True))
        response=self.post("/contact",{
            "csrf":token,"name":"Test Contact","email":"fjord-ci-contact@example.invalid",
            "description":"Bonjour, question sur les possibilités d'impression."})
        self.assertEqual(response.status_code,200)
        with db() as conn:
            row=conn.execute("SELECT kind,material FROM requests WHERE email=%s",
                         ("fjord-ci-contact@example.invalid",)).fetchone()
        self.assertEqual(row["kind"],"Contact")
        self.assertIsNone(row["material"])

    def test_invalid_quotes_and_bad_csrf_are_refused(self):
        self.assertEqual(self.post("/contact",{"name":"X","email":"x@example.invalid",
                                           "description":"No CSRF"}).status_code,400)
        valid_page=self.get("/soumission")
        token=csrf_from(valid_page.get_data(as_text=True))
        common={"csrf":token,"name":"Test","email":"invalid-quote@example.invalid",
                "description":"Test de validation","material":"PLA"}
        for overrides in ({"quantity":"0","color":"Bleu"},
                          {"quantity":"1","color":"<unexpected>"},
                          {"quantity":"1001","color":"Noir"}):
            data=dict(common,**overrides)
            with self.subTest(values=overrides):
                self.assertEqual(self.post("/soumission",data).status_code,400)

    def test_reference_photo_is_private_scrubbed_and_shown_in_admin(self):
        import hashlib
        import datetime
        from PIL import Image as PillowImage
        reference=PillowImage.new("RGB",(2400,1800),color=(20,80,150))
        stream=io.BytesIO()
        exif=PillowImage.Exif()
        exif[270]="PRIVATE CAMERA NOTE MUST NOT BE STORED"
        reference.save(stream,format="JPEG",quality=90,exif=exif)
        stream.seek(0)
        view=self.get("/soumission")
        token=csrf_from(view.get_data(as_text=True))
        response=self.post("/soumission",{
            "csrf":token,"name":"Client photo","email":"fjord-photo@example.invalid",
            "description":"Une pièce semblable au croquis.","quantity":"1","color":"Noir",
            "material":"PLA","reference_photo":(stream,"croquis-de-client.jpg")})
        self.assertEqual(response.status_code,200)
        with db() as conn:
            record=conn.execute("""SELECT id,reference_filename,reference_photo,reference_mime
                 FROM requests WHERE email=%s ORDER BY id DESC LIMIT 1""",
                 ("fjord-photo@example.invalid",)).fetchone()
        self.assertIsNotNone(record)
        self.assertEqual(record["reference_filename"],"croquis-de-client.jpg")
        self.assertEqual(record["reference_mime"],"image/jpeg")
        self.assertNotIn(b"PRIVATE CAMERA NOTE",record["reference_photo"])
        with PillowImage.open(io.BytesIO(record["reference_photo"])) as saved:
            self.assertLessEqual(max(saved.size),1600)
            self.assertEqual(saved.format,"JPEG")
        route=f"/admin/reference-photo/{record['id']}"
        self.assertIn(self.get(route).status_code,(302,303))
        token="fjord-ci-admin-photo-session"
        digest=hashlib.sha256(token.encode()).hexdigest()
        with db() as conn:
            conn.execute("INSERT INTO sessions(tokenhash,expires) VALUES(%s,%s)",
                         (digest,datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)))
        with self.client.session_transaction() as session:
            session["admin_token"]=token
        admin=self.get("/admin")
        self.assertEqual(admin.status_code,200)
        self.assertIn(route,admin.get_data(as_text=True))
        history=self.get("/admin/demandes?q=fjord-photo%40example.invalid&type=Soumission")
        self.assertEqual(history.status_code,200)
        self.assertIn("Client photo",history.get_data(as_text=True))
        self.assertIn(route,history.get_data(as_text=True))
        no_match=self.get("/admin/demandes?q=definitely-not-a-customer")
        self.assertEqual(no_match.status_code,200)
        self.assertIn("Aucune demande",no_match.get_data(as_text=True))
        self.assertEqual(self.get("/admin/demandes?page=999999").status_code,200)
        stored=self.get(route)
        self.assertEqual(stored.status_code,200)
        self.assertEqual(stored.mimetype,"image/jpeg")
        self.assertEqual(stored.headers.get("Cache-Control"),"no-store, private")
        self.assertIn("noindex",stored.headers.get("X-Robots-Tag",""))
        self.assertTrue(stored.data.startswith(bytes.fromhex("ffd8ff")))

    def test_reference_rejects_mislabeled_or_oversized_images(self):
        token=csrf_from(self.get("/soumission").get_data(as_text=True))
        common={"csrf":token,"name":"Test invalid photo","email":"fjord-invalid-photo@example.invalid",
                "description":"Test", "quantity":"1","color":"Noir","material":"PLA"}
        malformed=self.post("/soumission",dict(common,reference_photo=(
            io.BytesIO(b"not an actual jpeg and should fail"),"photo.jpg")))
        self.assertEqual(malformed.status_code,400)
        too_large=self.post("/soumission",dict(common,reference_photo=(
            io.BytesIO(b"x"*(4*1024*1024+50)),"too-large.jpg")))
        self.assertEqual(too_large.status_code,413)

    def test_3mf_upload_validation_rejects_corrupt_archives(self):
        import zipfile
        page=self.get("/soumission")
        token=csrf_from(page.get_data(as_text=True))
        common={"csrf":token,"name":"Test 3MF","email":"fjord-ci-3mf@example.invalid",
                "description":"Test de fichier 3MF","material":"PLA",
                "quantity":"1","color":"Noir"}
        broken=self.post("/soumission",dict(common,model=(io.BytesIO(b"PKnot-a-real-zip"),"broken.3mf")))
        self.assertEqual(broken.status_code,400)
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            zf.writestr("3D/3dmodel.model",'<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"/>')
        archive.seek(0)
        valid=self.post("/soumission",dict(common,model=(archive,"part.3mf")))
        self.assertEqual(valid.status_code,200)
        with db() as conn:
            uploaded=conn.execute("SELECT filename,octet_length(filedata) AS size FROM requests WHERE email=%s",
                                  (common["email"],)).fetchone()
        self.assertEqual(uploaded["filename"],"part.3mf")
        self.assertGreater(uploaded["size"],80)

    def test_gallery_images_metadata_and_index_safety(self):
        image=Image.new("RGB",(60,55),color=(12,92,147))
        payload=io.BytesIO()
        image.save(payload,format="PNG")
        with db() as conn:
            row=conn.execute("""INSERT INTO gallery(title,category,description,photo,mime)
                VALUES(%s,%s,%s,%s,%s) RETURNING id""",
                ("Plaque <script>alert(1)</script>","Accessoires","Un exemple réel de test 3D",payload.getvalue(),"image/png")).fetchone()
        item_id=row["id"]
        detail=self.get(f"/galerie/{item_id}")
        self.assertEqual(detail.status_code,200)
        html=detail.get_data(as_text=True)
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("Plaque <script>alert(1)</script>",html)
        self.assertIn(f'/gallery/thumb/{item_id}',html)
        self.assertIn('"CreativeWork"',html)
        self.assertIn('property="og:image"',html)
        thumbnail=self.get(f"/gallery/thumb/{item_id}")
        self.assertEqual(thumbnail.status_code,200)
        self.assertEqual(thumbnail.mimetype,"image/webp")
        self.assertGreater(len(thumbnail.data),0)
        with Image.open(io.BytesIO(thumbnail.data)) as compressed:
            self.assertEqual(compressed.format,"WEBP")
            self.assertEqual(compressed.size,(60,55))
        notfound=self.get("/does-not-exist-123456")
        self.assertEqual(notfound.status_code,404)
        self.assertIn('name="robots" content="noindex, nofollow"',
                      notfound.get_data(as_text=True))

    def test_read_only_services_and_private_access(self):
        ready=self.get("/health/ready")
        self.assertEqual(ready.status_code,200)
        self.assertEqual(ready.get_json()["ok"],True)
        self.assertEqual(self.get("/sitemap.xml").status_code,200)
        self.assertEqual(self.get("/robots.txt").status_code,200)
        quote=self.get("/soumission")
        self.assertEqual(quote.headers.get("Cache-Control"),"no-store, private")
        self.assertEqual(quote.headers.get("X-Content-Type-Options"),"nosniff")
        self.assertEqual(quote.headers.get("X-Frame-Options"),"SAMEORIGIN")
        self.assertEqual(self.get("/favicon.ico").status_code,302)
        logo=self.get("/identite/logo")
        self.assertEqual(logo.status_code,200)
        self.assertEqual(logo.mimetype,"image/jpeg")
        self.assertTrue(logo.data.startswith(bytes.fromhex("ffd8ff")))
        self.assertIn(self.get("/admin").status_code,(302,303))

if __name__=="__main__":
    unittest.main(verbosity=2)
