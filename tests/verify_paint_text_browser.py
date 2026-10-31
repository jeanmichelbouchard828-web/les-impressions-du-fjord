"""Regression browser tests: editable 3D text, paint palette and blank click tool reset."""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8787
BASE=f"http://127.0.0.1:{PORT}"
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
                        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE+"/atelier3d.html",timeout=1)
            break
        except Exception:time.sleep(.25)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--enable-webgl","--use-gl=angle",
            "--use-angle=swiftshader","--disable-dev-shm-usage","--no-sandbox"])
        page=browser.new_page(viewport={"width":1400,"height":900},accept_downloads=True)
        errors=[]
        page.on("pageerror",lambda err:errors.append(str(err)))
        page.route("**/api/atelier/filaments",lambda route:route.fulfill(status=200,
            content_type="application/json",body='{"connected":false,"available":false,"sources":[]}'))
        page.goto(BASE+"/atelier3d.html",wait_until="domcontentloaded")
        page.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
        # Typing into the real 3D text panel creates printable geometry and retains edit metadata.
        page.locator("#fjordTextInput").evaluate("(el)=>el.value='BLACK LABEL'")
        page.locator("#fjordTextCreate").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelector('#fjordTextStatus').innerText.includes('créé')",timeout=20000)
        assert "BLACK LABEL" in page.locator("#sceneList").inner_text()
        with page.expect_download() as dl:
            page.locator("#save").evaluate("el=>el.click()")
        saved=json.loads(pathlib.Path(dl.value.path()).read_text(encoding="utf-8"))
        assert saved["objects"][0]["textSpec"]["value"]=="BLACK LABEL"
        assert len(saved["objects"][0]["vertices"])>12
        page.locator("#fjordTextInput").evaluate("(el)=>el.value='FJORD'")
        page.locator("#fjordTextUpdate").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelector('#fjordTextStatus').innerText.includes('créé')",timeout=12000)
        with page.expect_download() as dl2:
            page.locator("#save").evaluate("el=>el.click()")
        edited=json.loads(pathlib.Path(dl2.value.path()).read_text(encoding="utf-8"))
        assert edited["objects"][0]["textSpec"]["value"]=="FJORD",edited["objects"][0]["textSpec"]
        # Paint opens, selects tools and palette; clicking blank plate exits paint mode.
        page.locator("#fjordPaintToggle").evaluate("el=>el.click()")
        assert page.locator("#fjordPaintPanel").is_visible()
        page.locator('[data-fjord-paint-tool="triangle"]').evaluate("el=>el.click()")
        assert page.locator('[data-fjord-paint-tool="triangle"]').get_attribute("aria-pressed")=="true"
        page.locator("#fjordPaintColor").evaluate("""el=>{el.value='#EE44AA';el.dispatchEvent(new Event('input',{bubbles:true}))}""")
        assert "#EE44AA" in page.locator("#fjordPaintColorLabel").inner_text()
        rect=page.locator("#stage canvas").first.bounding_box()
        assert rect, "WebGL canvas unavailable"
        # Far bottom-left is unoccupied; clicking it must close painting.
        page.mouse.click(rect["x"]+12,rect["y"]+rect["height"]-15)
        page.wait_for_function("window.fjordPaint.isActive()===false",timeout=5000)
        # The move gizmo must similarly turn off after a blank click.
        page.locator("#move").evaluate("el=>el.click()")
        assert page.locator("#move").get_attribute("aria-pressed")=="true"
        page.mouse.click(rect["x"]+12,rect["y"]+rect["height"]-15)
        page.wait_for_function("document.querySelector('#move').getAttribute('aria-pressed')==='false'",timeout=5000)
        assert not errors,errors
        print("3D text creation/editing, paint panel, palette and blank click reset PASSED")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=5)
