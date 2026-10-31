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
        # Click unoccupied canvas positions, away from the bottom toolbar and other overlays.
        blank_points=[(.18,.42),(.2,.60),(.80,.52),(.1,.3),(.70,.72)]
        def click_blank_canvas():
            for fx,fy in blank_points:
                point=page.evaluate("""coords=>{
                   const canvas=document.querySelector('#stage canvas');
                   const r=canvas.getBoundingClientRect();
                   const x=r.x+r.width*coords[0],y=r.y+r.height*coords[1];
                   return {x,y,canvasTarget:document.elementFromPoint(x,y)===canvas};
                }""",[fx,fy])
                if point["canvasTarget"]:
                    page.mouse.click(point["x"],point["y"])
                    return
            raise AssertionError("Could not find unoccluded blank point on 3D canvas")
        click_blank_canvas()
        page.wait_for_function("window.fjordPaint.isActive()===false",timeout=5000)
        # The move gizmo must similarly turn off after a blank click.
        page.locator("#move").evaluate("el=>el.click()")
        assert page.locator("#move").get_attribute("aria-pressed")=="true"
        click_blank_canvas()
        page.wait_for_function("document.querySelector('#move').getAttribute('aria-pressed')==='false'",timeout=5000)
        # Paint a visible face of a cube and ensure real per-triangle data survives a save.
        page.on("dialog",lambda dialog:dialog.accept())
        page.locator("#resetProject").evaluate("el=>el.click()")
        page.locator('[data-shape="cube"]').evaluate("el=>el.click()")
        page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
        page.locator("#fjordPaintToggle").evaluate("el=>el.click()")
        page.locator('[data-fjord-paint-tool="triangle"]').evaluate("el=>el.click()")
        page.mouse.click(rect["x"]+rect["width"]/2,rect["y"]+rect["height"]/2)
        page.wait_for_function("document.querySelector('#fjordPaintStatus').innerText.includes('facette(s)')",timeout=6000)
        with page.expect_download() as painted_dl:
            page.locator("#save").evaluate("el=>el.click()")
        painted=json.loads(pathlib.Path(painted_dl.value.path()).read_text(encoding="utf-8"))
        assert len(painted["objects"][0]["paintFaces"])>0,painted["objects"][0]
        page.locator("#undo").evaluate("el=>el.click()")
        page.locator("#redo").evaluate("el=>el.click()")
        with page.expect_download() as restored_dl:
            page.locator("#save").evaluate("el=>el.click()")
        restored=json.loads(pathlib.Path(restored_dl.value.path()).read_text(encoding="utf-8"))
        assert restored["objects"][0]["paintFaces"],restored["objects"][0]
        assert not errors,errors
        print("3D text creation/editing, actual face painting, palette, undo/redo and blank click reset PASSED")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=5)
