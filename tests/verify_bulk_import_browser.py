"""Real-browser verification of bulk local STL/3MF selection and upload."""
import json
import pathlib
import sys
import tempfile

from flask import Flask, render_template_string
from playwright.sync_api import sync_playwright

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from private_fjord import register_private_fjord


class Database:
    def __enter__(self):return self
    def __exit__(self,*_):return None
    def execute(self,sql,params=()):
        self.sql=sql
        return self
    def fetchall(self):return []
    def fetchone(self):return None


app=Flask(__name__)
app.secret_key="bulk-import-browser-test"
register_private_fjord(
    app,Database,lambda fn:fn,lambda:None,
    lambda:'<input type="hidden" name="csrf" value="test">',
    lambda:"test",
    lambda title,body,**kwargs:render_template_string(body,**kwargs))
html=app.test_client().get("/admin/modeles").data.decode("utf-8")
assert 'id="fjordBulkFolder"' in html and 'webkitdirectory' in html


with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,args=["--no-sandbox"])
    for width in (1280,390):
        page=browser.new_page(viewport={"width":width,"height":800})
        errors=[]
        uploads=[]
        page.on("pageerror",lambda exc:errors.append(str(exc)))

        def on_upload(route):
            req=route.request
            assert req.method=="POST"
            payload=req.post_data or ""
            assert "skip_duplicates" in payload
            assert "model" in payload
            uploads.append(payload)
            duplicate=(len(uploads)%2==0)
            route.fulfill(status=200,content_type="application/json",body=json.dumps(
                {"ok":True,"id":len(uploads),"duplicate":duplicate}))

        page.route("https://fjord.example/admin/modeles/api/save",on_upload)
        page.route("https://fjord.example/admin/modeles",lambda route:
                   route.fulfill(status=200,content_type="text/html",body=html))
        page.goto("https://fjord.example/admin/modeles",wait_until="load")
        assert page.locator("#fjordBulkStart").is_disabled()
        assert page.locator("#fjordBulkFolder").get_attribute("webkitdirectory") is not None

        files=[
            {"name":"pieceA.stl","mimeType":"application/octet-stream","buffer":b"solid first"},
            {"name":"pieceB.3mf","mimeType":"application/octet-stream","buffer":b"PK sample"},
        ]
        page.locator("#fjordBulkFiles").set_input_files(files)
        assert "2 fichier(s)" in page.locator("#fjordBulkStatus").inner_text()
        assert page.locator("#fjordBulkStart").is_enabled()
        page.locator("#fjordBulkStart").click()
        page.wait_for_function("document.getElementById('fjordBulkStatus').textContent.startsWith('Terminé')",timeout=15000)
        result=page.locator("#fjordBulkStatus").inner_text()
        assert "1 ajouté(s)" in result and "1 doublon(s)" in result, result
        assert len(uploads)==2
        assert page.locator("#fjordBulkProgress").evaluate("(el)=>el.value")==2
        assert page.locator("#fjordBulkRefresh").is_visible()
        assert not errors,errors

        # Browser's native directory picker can include mixed file types and subfolders.
        with tempfile.TemporaryDirectory() as path:
            folder=pathlib.Path(path)
            (folder/"subfolder").mkdir()
            (folder/"pieceC.stl").write_bytes(b"solid third")
            (folder/"subfolder"/"pieceD.3mf").write_bytes(b"PK demo")
            (folder/"notes.txt").write_text("Not a model")
            page.locator("#fjordBulkFolder").set_input_files(str(folder))
            label=page.locator("#fjordBulkStatus").inner_text()
            assert "2 fichier(s)" in label,label
            assert "1 autre(s) ignoré(s)" in label,label
            assert page.locator("#fjordBulkFiles").input_value()==""
            page.locator("#fjordBulkStart").click()
            page.wait_for_function("document.getElementById('fjordBulkStatus').textContent.startsWith('Terminé')",timeout=15000)
        assert len(uploads)==4
        assert not errors,errors
        print(f"Bulk STL/3MF files and nested folder passed at {width}px",flush=True)
        page.close()
    browser.close()
