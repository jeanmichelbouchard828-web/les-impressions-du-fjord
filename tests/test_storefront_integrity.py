"""Non-destructive sitewide regression tests. No live DB, payments or printers."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from flask import Flask, render_template_string
from fjord_marketing import MARKETING_GALLERY, MARKETING_HOME_START, MARKETING_HOME_END
from fjord_seo import seo_metadata, register_seo_routes, safe_canonical_path

ROOT = Path(__file__).resolve().parents[1]


class FakeCursor:
    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return [{"id": 11}, {"id": 12}]


class FakeDB:
    def __enter__(self):
        return FakeCursor()

    def __exit__(self, *args):
        return False


class StorefrontIntegrityTests(unittest.TestCase):
    def test_all_python_sources_compile(self):
        for file in ROOT.glob("*.py"):
            with self.subTest(source=file.name):
                ast.parse(file.read_text(encoding="utf-8"), filename=str(file))

    def test_public_gallery_template_escapes_user_supplied_titles(self):
        app=Flask(__name__)
        with app.app_context():
            result=render_template_string(
                MARKETING_GALLERY,
                items=[{"id":11,"title":"Exemple <script>alert(1)</script>",
                        "category":"Accessoires","description":"Petite pièce","has_photo":True}]
            )
        self.assertIn("/gallery/thumb/11",result)
        self.assertIn("/galerie/11",result)
        self.assertNotIn("<script>alert(1)</script>",result)
        self.assertIn("&lt;script&gt;",result)
        self.assertIn("fjmGallerySearch",result)

    def test_home_template_uses_real_gallery_and_tracked_production_only(self):
        app=Flask(__name__)
        with app.app_context():
            result=render_template_string(
                MARKETING_HOME_START+"<div>Tableau privé préservé</div>"+MARKETING_HOME_END,
                featured=[{"id":12,"title":"Exemple","category":"Pièce","has_photo":False}]
            )
        self.assertIn("/gallery/thumb/12", result)
        self.assertIn("Tableau privé préservé",result)
        self.assertIn("/soumission",result)
        self.assertIn("/atelier-3d",result)

    def test_quote_form_has_accessible_input_and_preview_disable(self):
        module=ast.parse((ROOT/"app.py").read_text(encoding="utf-8"))
        form=next(node.value.value for node in module.body
                  if isinstance(node,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=="FORM" for t in node.targets))
        app=Flask(__name__)
        with app.app_context():
            page=render_template_string(form,csrf="<input type='hidden' name='csrf' value='test'>",
               heading="Soumission",intro="Description",quote=True,
               marketing_help="",materials=["PLA","PETG"],colors=["Noir","Blanc"],
               prefill="",preview=False)
            demo=render_template_string(form,csrf="",heading="Contact",intro="",quote=False,
               marketing_help="",materials=[],colors=[],prefill="",preview=True)
        for expected in ['name="quantity"','name="color"','name="material"',
                         'name="model"','name="description"','name="email"']:
            self.assertIn(expected,page)
        self.assertNotIn('name="quantity"',demo)
        self.assertIn('disabled aria-disabled="true"',demo)

    def test_canonical_and_robots_exclude_private_routes_not_media(self):
        app=Flask(__name__)
        register_seo_routes(app,FakeDB)
        with patch.dict(os.environ,{"FJORD_PREVIEW_MODE":"0"}):
            with app.test_request_context("/galerie/11"):
                meta=seo_metadata()
                self.assertTrue(meta["canonical_url"].endswith("/galerie/11"))
                self.assertEqual(meta["meta_robots"],"index, follow")
            with app.test_request_context("/admin"):
                self.assertEqual(seo_metadata()["meta_robots"],"noindex, nofollow")
            client=app.test_client()
            robots=client.get("/robots.txt")
            self.assertEqual(robots.status_code,200)
            self.assertIn("Disallow: /admin", robots.text)
            self.assertNotIn("Disallow: /photo/", robots.text)
            self.assertNotIn("Disallow: /gallery/", robots.text)
            sitemap=client.get("/sitemap.xml")
            self.assertEqual(sitemap.status_code,200)
            xml=ElementTree.fromstring(sitemap.data)
            locs=[x.text for x in xml.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
            self.assertTrue(any(x.endswith("/galerie/11") for x in locs))
            self.assertTrue(any(x.endswith("/galerie/12") for x in locs))
            self.assertFalse(any("/admin" in x for x in locs))
        self.assertEqual(safe_canonical_path("/galerie/11"),"/galerie/11")

    def test_preview_is_not_indexed(self):
        app=Flask(__name__)
        register_seo_routes(app,FakeDB)
        with patch.dict(os.environ,{"FJORD_PREVIEW_MODE":"1"}):
            with app.test_request_context("/"):
                self.assertEqual(seo_metadata()["meta_robots"],"noindex, nofollow")
            client=app.test_client()
            self.assertIn("Disallow: /",client.get("/robots.txt").text)
            self.assertEqual(client.get("/sitemap.xml").status_code,503)

    def test_sitewide_scripts_and_gallery_image_endpoints_exist(self):
        app_source=(ROOT/"app.py").read_text(encoding="utf-8")
        stylesheet=(ROOT/"static/fjord_sitewide.css").read_text(encoding="utf-8")
        script=(ROOT/"static/fjord_sitewide.js").read_text(encoding="utf-8")
        self.assertNotIn('body.light .tracking-billboard p{color:#34536c}<style>',app_source)
        self.assertIn('@app.get("/gallery/thumb/<int:id>")',app_source)
        self.assertIn('@app.get("/health/ready")',app_source)
        self.assertIn('/static/fjord_sitewide.css',app_source)
        self.assertIn('/static/fjord_sitewide.js',app_source)
        self.assertIn('.fjord-preview-notice',stylesheet)
        self.assertIn('fjord-mobile-actions',script)


if __name__=="__main__":
    unittest.main()
