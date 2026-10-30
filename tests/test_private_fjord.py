import datetime
import base64
import io
from PIL import Image
import unittest

from flask import Flask, render_template_string
from private_fjord import admin_studio, public_studio, register_private_fjord


class DummyConnection:
    def __init__(self):
        self.query = ""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, query, params=()):
        self.query = query
        return self
    def fetchall(self):
        return []
    def fetchone(self):
        if "SELECT * FROM private_quotes" in self.query:
            return {"id": 1, "created": datetime.datetime(2026, 10, 30),
                    "customer": "Client de test", "email": "test@example.com",
                    "phone": "", "title": "Support 3D", "description": "PLA bleu",
                    "material": "PLA", "quantity": 2, "unit_price": 20.0,
                    "shipping": 0.0, "apply_taxes": False, "preview": None}
        return None


class PrivateFjordTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "unit-tests-only"
        register_private_fjord(self.app, DummyConnection,
                               lambda f: f, lambda: None,
                               lambda: '<input type="hidden" name="csrf" value="test">',
                               lambda: "test",
                               lambda title, body, **kwargs: render_template_string(body, **kwargs))
        self.client = self.app.test_client()

    def test_default_logo_is_a_valid_jpeg(self):
        with open("static/fjord_logo.b64", encoding="ascii") as f:
            content=base64.b64decode(f.read().strip(), validate=True)
        img=Image.open(io.BytesIO(content))
        img.load()
        self.assertEqual(img.format, "JPEG")
        self.assertGreater(img.width, 90)

    def test_private_library_api(self):
        r = self.client.get("/admin/modeles/api/liste")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, {"ok": True, "models": []})

    def test_library_import_button_in_admin_atelier(self):
        raw = ('<html><head></head><body><button id="export" data-i18n="export">'
               '</button><script type="module">/* End parametric generators */</script></body></html>')
        edited = admin_studio(raw, "token")
        self.assertIn('id="fjordPrivateImport"', edited)
        self.assertIn("/admin/modeles/api/liste", edited)
        self.assertIn("importModelFile", edited)
        self.assertNotIn("Importer de ma bibliothèque", raw)

    def test_library_page_links_to_atelier_for_3mf(self):
        class ModelConnection(DummyConnection):
            def fetchall(self):
                if "FROM private_models" in self.query:
                    return [{"id": 5, "name": "Pièce 3MF", "filename": "piece.3mf",
                             "bytes": 1024, "has_preview": False,
                             "created": datetime.datetime(2026, 10, 30)}]
                return []
        app = Flask(__name__)
        app.secret_key = "tests"
        register_private_fjord(app, ModelConnection, lambda f:f, lambda: None,
                               lambda: '<input name="csrf" value="token">',
                               lambda: "token",
                               lambda title,body,**kwargs:render_template_string(body,**kwargs))
        response=app.test_client().get("/admin/modeles")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"/admin/atelier-3d?model_id=5",response.data)

    def test_private_library_page(self):
        r = self.client.get("/admin/modeles")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"biblioth", r.data.lower())

    def test_quote_page(self):
        r = self.client.get("/admin/soumissions-pro")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Soumissions PRO", r.data)
        self.assertIn(b"Majoration", r.data)
        self.assertIn(b'id="fjUpload"', r.data)
        self.assertIn(b'/admin/soumissions-pro/estimer', r.data)
        self.assertIn(b'PETG-CF', r.data)

    def test_interac_payment_configuration_is_admin_only(self):
        r = self.client.get("/admin/soumissions-pro")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Courriel pour recevoir les virements Interac', r.data)
        self.assertIn(b'/admin/soumissions-pro/paiement', r.data)
        invalid = self.client.post("/admin/soumissions-pro/paiement",
                                   data={"interac_email": "incorrect", "csrf": "test"})
        self.assertEqual(invalid.status_code, 400)

    def test_public_payment_link_shows_only_payment_details(self):
        class PaymentConnection(DummyConnection):
            def fetchone(self):
                if "WHERE payment_token=%s" in self.query:
                    return {"id": 42, "quantity": 2, "unit_price": 20.00,
                            "shipping": 5.00, "apply_taxes": True}
                if "fjord_interac_email" in self.query:
                    return {"value": "virements@example.ca"}
                return None
        app = Flask(__name__)
        app.secret_key = "payment-tests"
        register_private_fjord(app, PaymentConnection, lambda f:f,lambda:None,
                               lambda: '<input name="csrf" value="test">',
                               lambda: "test",
                               lambda title,body,**kwargs:render_template_string(body,**kwargs))
        token = "a" * 43
        page_result = app.test_client().get("/payer/" + token)
        self.assertEqual(page_result.status_code,200)
        self.assertEqual(page_result.headers["X-Robots-Tag"],"noindex, nofollow, noarchive")
        self.assertIn(b"virements@example.ca", page_result.data)
        self.assertIn(b"FJ-00042", page_result.data)
        self.assertIn(b"51,74", page_result.data)  # 45 $ + 5 % TPS + 9,975 % TVQ
        self.assertNotIn(b"Client de test", page_result.data)
        self.assertEqual(app.test_client().get("/payer/short").status_code,404)

    def test_public_payment_link_disabled_without_interac_address(self):
        self.assertEqual(self.client.get("/payer/" + "a" * 43).status_code, 404)

    def test_pdf(self):
        r = self.client.get("/admin/soumissions-pro/1/pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF"))

    def test_models_missing_returns_404(self):
        r = self.client.get("/admin/modeles/fichier/999")
        self.assertEqual(r.status_code, 404)

    def test_admin_studio_adds_save_button_only_when_used(self):
        raw = '<button id="export" data-i18n="export"></button><script type="module">/* End parametric generators */</script>'
        edited = admin_studio(raw, "csrf-example")
        self.assertIn('id="fjordPrivateSave"', edited)
        self.assertIn("csrf-example", edited)
        self.assertNotIn('id="fjordPrivateSave"', raw)

    def test_public_studio_hides_cost_details(self):
        html = '<html><head></head><body></body></html>'
        edited = public_studio(html)
        self.assertIn("#estimateBreakdown", edited)
        self.assertIn("</head>", edited)


if __name__ == "__main__":
    unittest.main()
