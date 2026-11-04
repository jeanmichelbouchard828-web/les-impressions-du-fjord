"""Unit tests for the isolated Render migration preview safety gate."""
import os
import unittest
from unittest.mock import patch

from flask import Flask
from fjord_preview_guard import install_preview_guard


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

    def test_production_mode_unaffected(self):
        with patch.dict(os.environ, {"FJORD_PREVIEW_MODE": "0"}):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/payer/stripe/token").status_code, 200)
            self.assertEqual(self.client.post("/api/impression/start").status_code, 200)
            self.assertNotIn("X-Robots-Tag", self.client.get("/").headers)


if __name__ == "__main__":
    unittest.main()
