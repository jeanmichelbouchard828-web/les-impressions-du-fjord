"""Live browser smoke check: file input must import STL and 3MF on a real Three.js canvas."""
import io
from PIL import Image, ImageChops
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
import zipfile

from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:8765"

stl="""solid tetra
facet normal 0 0 -1
outer loop
vertex 0 0 0
vertex 30 0 0
vertex 0 30 0
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 0 0 0
vertex 0 0 30
vertex 30 0 0
endloop
endfacet
facet normal -1 0 0
outer loop
vertex 0 0 0
vertex 0 30 0
vertex 0 0 30
endloop
endfacet
facet normal 1 1 1
outer loop
vertex 30 0 0
vertex 0 0 30
vertex 0 30 0
endloop
endfacet
endsolid tetra
"""
model='''<?xml version="1.0" encoding="utf-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
<resources><object id="1" type="model" name="Tiny Tetra"><mesh>
<vertices><vertex x="0" y="0" z="0"/><vertex x="30" y="0" z="0"/>
<vertex x="0" y="30" z="0"/><vertex x="0" y="0" z="30"/></vertices>
<triangles><triangle v1="0" v2="2" v3="1"/><triangle v1="0" v2="1" v3="3"/>
<triangle v1="0" v2="3" v3="2"/><triangle v1="1" v2="2" v3="3"/></triangles>
</mesh></object></resources><build><item objectid="1"/></build></model>'''
rels='''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model"/>
</Relationships>'''
def three_mf():
    io_out=io.BytesIO()
    with zipfile.ZipFile(io_out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("3D/3dmodel.model",model)
        z.writestr("_rels/.rels",rels)
    return io_out.getvalue()

server=subprocess.Popen([sys.executable,"-m","http.server","8765","--bind","127.0.0.1"],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(30):
        try:
            urllib.request.urlopen(BASE+"/atelier3d.html",timeout=1)
            break
        except Exception:time.sleep(.2)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,args=["--enable-webgl","--use-gl=angle","--use-angle=swiftshader","--disable-dev-shm-usage","--no-sandbox"])
        page=browser.new_page(viewport={"width":1360,"height":850})
        errors=[]
        page.on("console",lambda msg: errors.append("console: "+msg.text) if msg.type=="error" else None)
        page.on("pageerror",lambda exc: errors.append("pageerror: "+str(exc)))
        page.goto(BASE+"/atelier3d.html",wait_until="domcontentloaded")
        page.wait_for_function("window.__fjordEditorStarted === true",timeout=60000)
        print("editor started",flush=True)
        page.locator("#stlFile").set_input_files({"name":"test.stl","mimeType":"model/stl","buffer":stl.encode()})
        page.wait_for_function("document.querySelectorAll('#sceneList .scene-row,#sceneList .scene-item,#sceneList button').length>0",timeout=12000)
        assert not page.locator("#fjordImportNotice:visible").count(), "STL import error"
        print("STL loaded",page.locator("#sceneList").inner_text()[:200],flush=True)
        page.locator("#stlFile").set_input_files({"name":"test.3mf","mimeType":"application/octet-stream","buffer":three_mf()})
        page.wait_for_timeout(3000)
        print("3MF state",page.locator("#sceneList").inner_text()[:400],flush=True)
        if page.locator("#fjordImportNotice:visible").count():
            raise AssertionError(page.locator("#fjordImportNotice").inner_text())
        assert len(page.locator("#sceneList").inner_text())>len("test.stl"),"Nothing shown after 3MF"
        # Right-click should open tools, but holding right + dragging should
        # pan the camera (and not open the menu or move the model).
        canvas=page.locator("#stage canvas")
        rect=canvas.bounding_box()
        assert rect, "3D canvas missing"
        px=rect["x"]+rect["width"]*0.55
        py=rect["y"]+rect["height"]*0.58
        page.mouse.click(px,py,button="right")
        assert page.locator("#contextMenu").is_visible(), "Right-click tools menu unavailable"
        page.mouse.click(px,py,button="left")
        assert page.locator("#contextMenu").is_hidden()
        page.wait_for_timeout(250)
        frame_before=Image.open(io.BytesIO(canvas.screenshot())).convert("RGB")
        part_list_before=page.locator("#sceneList").inner_text()
        page.mouse.move(px,py)
        page.mouse.down(button="right")
        page.mouse.move(px+120,py+50,steps=12)
        page.mouse.up(button="right")
        page.wait_for_timeout(450)  # OrbitControls damping
        assert page.locator("#contextMenu").is_hidden(), "Right-drag opened the tools menu"
        frame_after=Image.open(io.BytesIO(canvas.screenshot())).convert("RGB")
        assert ImageChops.difference(frame_before,frame_after).getbbox(), "Right-drag did not pan the view"
        assert page.locator("#sceneList").inner_text()==part_list_before, "Right-drag changed model list"
        print("Right-drag camera pan and short right-click menu OK",flush=True)
        # Multiple selection / Merge / real size change / split — Bambu semantics.
        # Selecting the parts through their checkboxes works on PC and mobile.
        checkboxes=page.locator("#sceneList input[type=checkbox]")
        assert checkboxes.count()==2, "Two independent imported parts expected"
        checkboxes.nth(0).check()
        checkboxes.nth(1).check()
        assert page.locator("#sceneList input[type=checkbox]:checked").count()==2
        page.evaluate("""() => {
          const menu=document.getElementById('contextMenu');
          menu.hidden=false;
          menu.querySelector('[data-context-action="mergeAll"]').click();
        }""")
        assert page.locator("#sceneList input[type=checkbox]").count()==1, "Merge should create one grouped object"
        assert "2 pièces" in page.locator("#sceneList").inner_text(), "The original parts must remain"
        start_size=float(page.locator("#sx").input_value())
        page.evaluate("""() => document.querySelector('[data-context-action="growSelected"]').click()""")
        resized=float(page.locator("#sx").input_value())
        assert abs(resized/start_size-1.1)<.005, f"Scale must change actual model size by 10%: {start_size} -> {resized}"
        import json
        with page.expect_download() as download_info:
            page.locator("#save").evaluate("(button) => button.click()")
        saved=json.loads(pathlib.Path(download_info.value.path()).read_text(encoding="utf-8"))
        assert len(saved["objects"])==1
        assert len(saved["objects"][0]["parts"])==2
        assert saved["objects"][0]["vertices"], "Merged geometry was not saved"
        # Split should recreate both independently selectable pieces.
        page.evaluate("""() => document.querySelector('[data-context-action="splitMerged"]').click()""")
        assert page.locator("#sceneList input[type=checkbox]").count()==2
        # Reopen the saved merged object: parts and scale must survive reload.
        page.locator("#projectFile").set_input_files({
            "name":"merged-fjord.json","mimeType":"application/json",
            "buffer":json.dumps(saved).encode("utf-8"),
        })
        page.wait_for_function("""() => document.querySelectorAll("#sceneList input[type=checkbox]").length===1 && document.getElementById("sceneList").innerText.includes("2 pièces")""",timeout=10000)
        print("Merge, per-part preservation, real scale, split and project reload OK",flush=True)
        browser.close()
        print("PASSED browser import; JS errors:",errors,flush=True)
finally:
    server.terminate()
    server.wait(timeout=5)
