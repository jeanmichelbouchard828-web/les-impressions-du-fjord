"""Browser checks for the private Soumissions PRO model library picker."""
import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from flask import Flask, render_template_string
from playwright.sync_api import sync_playwright

from private_fjord import register_private_fjord


class ReadOnlyConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=()):
        self.statement = statement
        return self

    def fetchall(self):
        if "FROM private_models" in self.statement:
            return [
                {"id": 11, "name": "Support téléphone", "filename": "support.stl", "has_preview": True},
                {"id": 12, "name": "Engrenage 26 dents", "filename": "engrenage.3mf", "has_preview": True},
            ]
        return []

    def fetchone(self):
        return None


def quote_html():
    app = Flask(__name__)
    app.secret_key = "library-picker-test"
    register_private_fjord(
        app, ReadOnlyConnection, lambda fn: fn, lambda: None,
        lambda: '<input type="hidden" name="csrf" value="test">',
        lambda: "test",
        lambda title, body, **kwargs: render_template_string(body, **kwargs),
    )
    response = app.test_client().get("/admin/soumissions-pro")
    assert response.status_code == 200
    return response.data.decode("utf-8")


def run():
    document = quote_html()
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRk0AAAAASUVORK5CYII="
    )
    models = [
        {"id": 11, "name": "Support téléphone", "filename": "support.stl", "has_preview": True},
        {"id": 12, "name": "Engrenage 26 dents", "filename": "engrenage.3mf", "has_preview": True},
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        for width in (1250, 390):
            page = browser.new_page(viewport={"width": width, "height": 850})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route(
                "https://fjord.test/admin/soumissions-pro",
                lambda route: route.fulfill(status=200, content_type="text/html", body=document),
            )
            page.route(
                "https://fjord.test/admin/modeles/api/liste",
                lambda route: route.fulfill(status=200, content_type="application/json",
                                            body=json.dumps({"ok": True, "models": models})),
            )
            page.route(
                "https://fjord.test/admin/modeles/apercu/*",
                lambda route: route.fulfill(status=200, content_type="image/png", body=image),
            )
            page.route(
                "https://fjord.test/admin/soumissions-pro/estimer",
                lambda route: route.fulfill(status=200, content_type="application/json",
                                            body=json.dumps({"ok": True, "grams": 78.5,
                                                             "hours": 3.25, "infill": 18,
                                                             "layer_height": 0.2})),
            )
            page.goto("https://fjord.test/admin/soumissions-pro", wait_until="load")
            assert page.locator("#fjPickLibrary").is_visible()
            assert page.locator("#fjLibraryDialog").is_hidden()
            page.locator("#fjPickLibrary").click()
            assert page.locator("#fjLibraryDialog").is_visible()
            page.locator(".fj-library-item").first.wait_for(timeout=10000)
            assert page.locator(".fj-library-item").count() == 2
            page.locator("#fjLibrarySearch").fill("engrenage")
            assert page.locator(".fj-library-item").count() == 1
            assert "Engrenage 26 dents" in page.locator(".fj-library-item").inner_text()
            page.locator(".fj-library-item button").click()
            assert page.locator("#fjLibraryDialog").is_hidden()
            assert page.locator("#fjModel").input_value() == "12"
            assert page.locator('input[name="title"]').input_value() == "Engrenage 26 dents"
            page.wait_for_function("document.querySelector('[name=grams]').value === '78.5'")
            assert page.locator('input[name="hours"]').input_value() == "3.25"
            assert page.locator("#fjPreviewBox").is_visible()
            assert page.locator("#fjTotal").inner_text() != "—"
            assert page.locator("#fjSaveQuote").is_enabled()
            assert not errors, errors
            print(f"Soumissions PRO library picker OK - {width}px", flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    run()
