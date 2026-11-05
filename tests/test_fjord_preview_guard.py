"""Unit tests for the isolated Render migration preview safety gate."""
import os
import unittest
from unittest.mock import patch

from flask import Flask
from fjord_preview_guard import assert_preview_isolated, install_preview_guard


class PreviewSafetyTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        install_preview_guard(self.app)
        self.app.add_url_rule("/", "index", lambda: "PUBLIC")
        self.app.add_url_rule("/health", "health", lambda: "OK")
        self.app.add_url_rule("/atelier-3d", "atelier", lambda: "PUBLIC PREVIEW")
        self.app.add_url_rule("/api/impression/start", "printer", lambda: "NOT SAFE", methods=["GET", "POST"])
        self.app.add_url_rule("/payer/stripe/token", "pay", lambda: "NOT SAFE")
        self.app.add_url_rule("/stripe/webhook", "stripe", lambda: "NOT SAFE", methods=["POST"])
        self.client = self.app.test_client()

    def test_preview_readonly_public_pages(self):
        with patch.dict(os.environ, {"FJORD_PREVIEW_MODE": "1"}):
            for path in ("/", "/health", "/atelier-3d"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("noindex", response.headers["X-Robots-Tag"])
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_preview_blocks_every_write_and_private_routes(self):
        with patch.dict(os.environ, {"FJORD_PREVIEW_MODE": "1"}):
            for path, method in (
                ("/", "post"),
                ("/contact", "post"),
                ("/admin", "get"),
                ("/admin/atelier-3d", "get"),
                ("/api/impression/start", "get"),
                ("/api/impression/start", "post"),
                ("/payer/stripe/token", "get"),
                ("/stripe/webhook", "post"),
            ):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 503, (path, method))
                self.assertEqual(response.json["preview"], True)

    def test_preview_database_must_be_isolated_render_database(self):
        valid = "postgresql://fjord_user:demo@dpg-example.oregon-postgres.render.com/fjord_render_apercu"
        private_valid = "postgresql://fjord_user:demo@dpg-dblt2em417fc73bfjd70-a/fjord_render_apercu_db_20261104"
        with patch.dict(os.environ, {"FJORD_PREVIEW_MODE": "1"}, clear=True):
            assert_preview_isolated(valid)
            assert_preview_isolated(private_valid)
            for unsafe in (
                "postgresql://user:pass@postgres.railway.internal/railway",
                "postgresql://user:pass@proxy.rlwy.net/railway",
                "postgresql://user:pass@dpg-example.oregon-postgres.render.com/production",
                "postgresql://user:pass@evilrender.com/fjord_render_apercu",
                "postgresql://user:pass@dpg-dblmo8hsrm7s73f34530-a/fjord_render_apercu",
            ):
                with self.subTest(unsafe=unsafe):
                    with self.assertRaises(RuntimeError):
                        assert_preview_isolated(unsafe)

    def test_preview_refuses_live_integrations(self):
        valid = "postgresql://fjord_user:demo@dpg-example.oregon-postgres.render.com/fjord_render_apercu"
        for secret in (
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "OCTOEVERYWHERE_CONNECTION_URL",
            "OCTOEVERYWHERE_AUTH_BEARER_TOKEN",
            "OCTOEVERYWHERE_AUTH_BASIC_PASSWORD",
            "ADMIN_SETUP_TOKEN",
        ):
            with self.subTest(secret=secret):
                with patch.dict(os.environ, {"FJORD_PREVIEW_MODE": "1", secret: "demo"}, clear=True):
                    with self.assertRaises(RuntimeError):
                        assert_preview_isolated(valid)

    def test_production_mode_unaffected(self):
        with patch.dict(os.environ, {"FJORD_PREVIEW_MODE": "0"}):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/payer/stripe/token").status_code, 200)
            self.assertEqual(self.client.post("/api/impression/start").status_code, 200)
            self.assertNotIn("X-Robots-Tag", self.client.get("/").headers)


if __name__ == "__main__":
    unittest.main()
