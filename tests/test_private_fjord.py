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

    def test_private_library_page(self):
        r = self.client.get("/admin/modeles")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"biblioth", r.data.lower())

    def test_quote_page(self):
        r = self.client.get("/admin/soumissions-pro")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Soumissions PRO", r.data)
        self.assertIn(b"Majoration", r.data)

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
