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

    def test_admin_shortcut_is_visible_only_in_private_atelier(self):
        # The admin-only transformer injects a permanent link outside the
        # collapsible project menu, visible on both desktop and mobile.
        raw = ('<html><head></head><body><header><div class="top-preferences">'
               '<select id="language"></select></div></header>'
               '<div class="top-actions"><button id="export" data-i18n="export">'
               '</button></div>'
               '<script type="module">/* End parametric generators */</script>'
               '</body></html>')
        edited = admin_studio(raw, "token")
        self.assertEqual(edited.count('id="fjordAdminShortcut"'), 1)
        self.assertIn('id="fjordAdminShortcut" href="/admin"', edited)
        self.assertLess(edited.index('id="fjordAdminShortcut"'),
                        edited.index('id="language"'))
        self.assertNotIn('fjordAdminShortcut', raw)
        self.assertIn('Retour au tableau de bord administrateur', edited)

    def test_public_atelier_has_admin_login_shortcut(self):
        raw = ('<html><head></head><body><header><div class="top-preferences">'
               '<select id="theme"></select></div></header>'
               '<button id="export" data-i18n="export"></button></body></html>')
        public = public_studio(raw)
        self.assertIn('id="fjordAdminAccess" href="/admin/atelier-3d"', public)
        self.assertNotIn('fjordPrivateSave', public)
        self.assertNotIn('fjordAdminShortcut', public)
        self.assertLess(public.index('fjordAdminAccess'), public.index('id="theme"'))
        self.assertEqual(public.count('fjordAdminAccess'), 1)

    def test_admin_header_is_compact_and_keeps_all_original_controls(self):
        with open("atelier3d.html", encoding="utf-8") as source:
            original = source.read()
        admin = admin_studio(original, "testtoken")
        public = public_studio(original)
        self.assertIn('class="fjord-admin-header"', admin)
        self.assertIn('class="fjord-admin-core"', admin)
        self.assertIn('class="fjord-admin-more"', admin)
        self.assertIn('/static/atelier_admin_header.css', admin)
        self.assertIn('class="fjord-admin-links"', admin)
        for control in (
            "projectMenuButton", "new", "open", "import", "save",
            "export", "exportColor3MF", "sliceTop", "estimateToggle",
            "quote", "fjordPrivateImport", "fjordPrivateSave",
            "fjordPrintShortcut", "fjordAdminShortcut"
        ):
            self.assertEqual(admin.count('id="' + control + '"'), 1, control)
        for ref in ("/admin/modeles", "/admin/profils-bambu"):
            self.assertIn('href="' + ref + '"', admin)
        self.assertLess(admin.index('id="fjordPrintShortcut"'),
                        admin.index('id="fjordAdminShortcut"'))
        self.assertNotIn('fjord-admin-header', public)
        self.assertNotIn('fjord-admin-core', public)
        self.assertNotIn('fjordPrintShortcut', public)

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
        self.assertIn(b'id="fjPickLibrary"', r.data)
        self.assertIn(b'id="fjLibraryDialog"', r.data)
        self.assertIn(b'id="fjLibrarySearch"', r.data)
        self.assertIn(b'/admin/modeles/api/liste', r.data)
        self.assertIn('Choisir cette pièce'.encode('utf-8'), r.data)
        self.assertIn(b'libraryDialog.close()', r.data)
        self.assertIn("/suivi-impression/<token>", [rule.rule for rule in self.app.url_map.iter_rules()])
        self.assertIn("/admin/soumissions-pro/<int:quote_id>/diffusion",
                      [rule.rule for rule in self.app.url_map.iter_rules()])

    def test_quote_reset_button_is_safe_and_admin_only(self):
        html = self.client.get("/admin/soumissions-pro").data.decode("utf-8")
        self.assertIn('id="fjResetQuote"', html)
        self.assertIn('type="button" id="fjResetQuote"', html)
        self.assertIn('Réinitialiser le formulaire', html)
        self.assertIn('resetQuote.addEventListener("click"', html)
        self.assertIn('++requestNumber', html)
        self.assertIn('selector.value=""', html)
        self.assertIn('f.reset()', html)
        self.assertIn('previewBox.hidden=true', html)
        self.assertIn('Les soumissions déjà enregistrées ne seront pas touchées', html)
        # A client cannot erase saved quotes by submitting the reset control.
        self.assertNotIn('name="reset_quote"', html)

    def test_interac_payment_configuration_is_admin_only(self):
        r = self.client.get("/admin/soumissions-pro")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Courriel pour recevoir les virements Interac', r.data)
        self.assertIn(b'/admin/soumissions-pro/enregistrer-tout', r.data)
        invalid = self.client.post("/admin/soumissions-pro/paiement",
                                   data={"interac_email": "incorrect", "csrf": "test"})
        self.assertEqual(invalid.status_code, 400)

    def test_global_save_accepts_normal_interac_email_and_mobile_json(self):
        """Regression: saving a valid Interac address must not return Bad Request."""
        class QuoteConnection(DummyConnection):
            calls=[]
            def execute(self, query, params=()):
                self.query=query
                self.params=params
                self.calls.append((query, params))
                return self
            def fetchall(self):
                if "SELECT id,model_id FROM private_quotes" in self.query:
                    return [{"id":11,"model_id":None}]
                return []
            def fetchone(self):
                return None
        app=Flask(__name__)
        app.secret_key="mobile-save-tests"
        register_private_fjord(app, QuoteConnection, lambda f:f,lambda:None,
                               lambda:'<input name="csrf" value="test">',
                               lambda:"test",
                               lambda title,body,**kwargs:render_template_string(body,**kwargs))
        client=app.test_client()
        save=client.post("/admin/soumissions-pro/enregistrer-tout",data={
            "csrf":"test",
            "interac_email":"soumissions@example.ca",
            "public_number_11":"FJ-00011",
            "printer_job_name_11":"FJ-00011_test-object",
            "production_status_11":"En production",
            "production_progress_11":"57",
            "payment_status_11":"Payée",
        },headers={"Accept":"application/json"})
        self.assertEqual(save.status_code,200,save.data)
        self.assertEqual(save.json["ok"],True)
        self.assertTrue(any("UPDATE private_quotes SET public_number" in sql
                            for sql,_ in QuoteConnection.calls))
        self.assertTrue(any("INSERT INTO settings(key,value)" in sql and params==("soumissions@example.ca",)
                            for sql,params in QuoteConnection.calls))
        invalid=client.post("/admin/soumissions-pro/enregistrer-tout",
                            data={"csrf":"test","interac_email":"not-an-email"},
                            headers={"Accept":"application/json"})
        self.assertEqual(invalid.status_code,400)
        self.assertIn("Interac",invalid.json["error"])
        page=client.get("/admin/soumissions-pro")
        self.assertIn(b'id="fjord-save-feedback"',page.data)
        self.assertIn(b"'Accept':'application/json'",page.data)

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

    def test_saved_quotes_include_payment_dropdown(self):
        class PaidQuotesConnection(DummyConnection):
            def fetchall(self):
                if "FROM private_quotes" in self.query:
                    return [{"id": 8, "customer": "Client payé",
                             "title": "Pièce imprimée", "quantity": 2,
                             "unit_price": 12.50, "shipping": 0,
                             "apply_taxes": False, "payment_status": "Payée",
                             "paid_at": datetime.datetime(2026, 10, 30),
                             "created": datetime.datetime(2026, 10, 29)}]
                return []
        app = Flask(__name__)
        app.secret_key = "test-payment"
        register_private_fjord(app, PaidQuotesConnection, lambda f: f, lambda: None,
                               lambda: '<input name="csrf" value="test">',
                               lambda: "test",
                               lambda title, body, **kwargs: render_template_string(body, **kwargs))
        html = app.test_client().get("/admin/soumissions-pro").data.decode("utf-8")
        self.assertIn('/admin/soumissions-pro/enregistrer-tout', html)
        self.assertIn('/admin/soumissions-pro/8/diffusion', html)
        self.assertIn('Activer un nouveau lien', html)
        self.assertIn('option value="Payée" selected', html)
        self.assertIn('Paiement confirmé manuellement le 30-10-2026', html)
        self.assertIn('Paiement partiel', html)

    def test_saved_quote_payment_status_is_validated_and_persisted(self):
        class PaymentStatusConnection(DummyConnection):
            def __init__(self):
                super().__init__()
                self.params = ()
            def execute(self, query, params=()):
                self.query = query
                self.params = params
                return self
            def fetchone(self):
                if "UPDATE private_quotes" in self.query:
                    return {"id": 8} if self.params[2] == 8 else None
                return None
        used = []
        def connection():
            instance = PaymentStatusConnection()
            used.append(instance)
            return instance
        app = Flask(__name__)
        app.secret_key = "test-update"
        register_private_fjord(app, connection, lambda f: f, lambda: None,
                               lambda: '<input name="csrf" value="test">',
                               lambda: "test",
                               lambda title, body, **kwargs: render_template_string(body, **kwargs))
        client = app.test_client()
        bad = client.post("/admin/soumissions-pro/8/statut-paiement",
                          data={"payment_status": "Payée automatiquement"})
        self.assertEqual(bad.status_code, 400)
        for selected in ("En attente", "Paiement partiel", "Payée"):
            response = client.post("/admin/soumissions-pro/8/statut-paiement",
                                   data={"payment_status": selected})
            self.assertEqual(response.status_code, 302)
            self.assertIn("#soumissions-enregistrees", response.headers["Location"])
            self.assertEqual(used[-1].params, (selected, selected, 8))
        missing = client.post("/admin/soumissions-pro/99/statut-paiement",
                              data={"payment_status": "Payée"})
        self.assertEqual(missing.status_code, 404)

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
