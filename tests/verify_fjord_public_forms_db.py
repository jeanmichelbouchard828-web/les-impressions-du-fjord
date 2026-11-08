"""Isolated PostgreSQL end-to-end tests for the public business flow.

This file intentionally REFUSES to run against any non-local database.
No actual payment, email or printer command is sent.
"""
import io
import os
import re
from urllib.parse import urlsplit
import unittest

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
        self.assertIn(self.get("/admin").status_code,(302,303))

if __name__=="__main__":
    unittest.main(verbosity=2)
