"""Browser check: quote reset must clear unsaved edits without deleting saved data."""
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
        pass

    def execute(self, statement, params=()):
        self.statement = statement
        return self

    def fetchall(self):
        if "FROM private_models" in self.statement:
            return [{"id": 11, "name": "Pièce test", "has_preview": True}]
        return []

    def fetchone(self):
        return None


def quote_html():
    app = Flask(__name__)
    app.secret_key = "reset-test"
    register_private_fjord(
        app, ReadOnlyConnection, lambda function: function, lambda: None,
        lambda: '<input type="hidden" name="csrf" value="example">',
        lambda: "example",
        lambda title, body, **kwargs: render_template_string(body, **kwargs),
    )
    response = app.test_client().get("/admin/soumissions-pro")
    assert response.status_code == 200
    return response.data.decode("utf-8")


def run():
    document = quote_html()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        for width in (1200, 390):
            page = browser.new_page(viewport={"width": width, "height": 850})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.set_content(document, wait_until="load")
            assert page.locator("#fjResetQuote").count() == 1
            page.locator(".fj-top-panel").first.locator("summary").click()
            assert page.locator('input[name="customer"]').is_visible()

            # Cancel first: the user's work must still be there.
            page.locator('input[name="customer"]').fill("Client en cours")
            page.once("dialog", lambda dialog: dialog.dismiss())
            page.locator("#fjResetQuote").click()
            assert page.locator('input[name="customer"]').input_value() == "Client en cours"

            page.locator('input[name="title"]').fill("Support personnalisé")
            page.locator('input[name="quantity"]').fill("5")
            page.locator('input[name="grams"]').fill("87")
            page.locator('input[name="hours"]').fill("4")
            page.locator('input[name="override_price"]').fill("99")
            page.locator('input[name="apply_taxes"]').check()
            page.locator("#fjMaterial").select_option("ASA")
            page.locator("#fjLayer").select_option("0.12")
            page.locator("#fjInfill").select_option("40")
            # Simulate a model option inserted after import (already saved server-side).
            page.evaluate("""() => {
                const model = document.querySelector('#fjModel');
                const option = new Option('Pièce temporaire', '99', true, true);
                option.dataset.imported = '1';
                model.add(option);
                document.querySelector('#fjPreviewBox').hidden = false;
            }""")

            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#fjResetQuote").click()
            assert page.locator('input[name="customer"]').input_value() == ""
            assert page.locator('input[name="title"]').input_value() == ""
            assert page.locator('input[name="quantity"]').input_value() == "1"
            assert page.locator('input[name="grams"]').input_value() == "50"
            assert page.locator('input[name="hours"]').input_value() == "3"
            assert page.locator('input[name="override_price"]').input_value() == ""
            assert not page.locator('input[name="apply_taxes"]').is_checked()
            assert page.locator("#fjMaterial").input_value() == "PETG"
            assert page.locator("#fjLayer").input_value() == "0.2"
            assert page.locator("#fjInfill").input_value() == "18"
            assert page.locator("#fjModel").input_value() == ""
            assert page.locator("#fjModel option[data-imported='1']").count() == 0
            assert page.locator("#fjPreviewBox").is_hidden()
            assert page.locator("#fjSaveQuote").is_enabled()
            assert "Formulaire réinitialisé" in page.locator("#fjEstimateStatus").inner_text()
            assert page.locator("#fjTotal").inner_text() != "—"
            assert not errors, errors
            print(f"Soumissions PRO reset OK - {width}px", flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    run()
