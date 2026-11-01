"""Chrome end-to-end torsion spring and obvious paint entry tests."""
import collections
import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8788
BASE=f"http://127.0.0.1:{PORT}"
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
                        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE+"/atelier3d.html",timeout=1)
            break
        except Exception: time.sleep(.2)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=[
            "--enable-webgl","--use-gl=angle","--use-angle=swiftshader",
            "--disable-dev-shm-usage","--no-sandbox"])
        page=browser.new_page(viewport={"width":1400,"height":880},accept_downloads=True)
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.route("**/api/atelier/filaments",lambda route:route.fulfill(
            status=200,content_type="application/json",
            body='{"connected":false,"available":false,"sources":[]}'))
        page.goto(BASE+"/atelier3d.html",wait_until="domcontentloaded")
        page.wait_for_function("window.__fjordEditorStarted === true",timeout=60000)
        assert page.locator('[data-generator-pick="torsion_spring"]').count()==1
        assert "Peindre" in page.locator("#fjordPaintToggle").inner_text()
        # Delete is the first item in the right-click part menu; compact menu excludes redundant shortcuts.
        menu=page.locator("#contextMenu [data-context-action]")
        assert menu.first.get_attribute("data-context-action")=="remove", "Supprimer doit être en premier"
        for removed in ("growSelected","scaleCustom","rotX90","rotY90","rotZ90","half","double"):
            assert page.locator('#contextMenu [data-context-action="'+removed+'"]').count()==0,removed
        assert page.locator('#contextMenu [data-context-action="move"]').count()==1
        assert page.locator('#contextMenu [data-context-action="scale"]').count()==1
        # The empty-plate context menu is compact and opens the real primitive submenu.
        canvas=page.locator("#stage canvas")
        bounds=canvas.bounding_box()
        assert bounds
        blank_x=blank_y=None
        for u,v in ((.55,.58),(.65,.65),(.40,.56),(.7,.70),(.55,.76)):
            x=bounds["x"]+bounds["width"]*u
            y=bounds["y"]+bounds["height"]*v
            on_canvas=page.evaluate("""p=>document.elementFromPoint(p.x,p.y)===document.querySelector('#stage canvas')""",{"x":x,"y":y})
            if not on_canvas:continue
            page.mouse.click(x,y,button="right")
            if page.locator("#contextMenu .fjord-plate-context").is_visible():
                blank_x,blank_y=x,y
                break
        assert blank_x is not None, page.evaluate("""() => ({
            menuHidden:document.querySelector('#contextMenu').hidden,
            plateHidden:document.querySelector('#contextMenu .fjord-plate-context').hidden,
            canvasSize:document.querySelector('#stage canvas').getBoundingClientRect().toJSON()
        })""")
        assert page.locator('#contextMenu [data-context-action="selectAll"]').is_visible()
        assert page.locator('#contextMenu [data-context-action="deleteAll"]').is_disabled()
        page.locator("#contextMenu .fjord-primitive-submenu summary").click()
        assert page.locator('#contextMenu [data-context-action="shape-cube"]').is_visible()
        page.keyboard.press("Escape")
        page.mouse.click(blank_x,blank_y,button="left")
        assert page.locator("#contextMenu").is_hidden()
        # Entry points must all launch the same working painting palette.
        page.locator("#fjordPaintLaunch").evaluate("el=>el.click()")
        assert page.locator("#fjordPaintPanel").is_visible()
        page.locator("#fjordPaintClose").evaluate("el=>el.click()")
        page.locator("#fjordPaintOpenAms").evaluate("el=>el.click()")
        assert page.locator("#fjordPaintPanel").is_visible()
        page.locator("#fjordPaintClose").evaluate("el=>el.click()")
        page.locator('[data-fjord-panel="generators"]').evaluate("el=>el.click()")
        # Search should match French/English names and diacritics, and narrow the picker.
        search=page.locator("#fjordGeneratorSearch")
        assert search.count()==1
        search.fill("TORSÍON")
        assert page.locator('[data-generator-pick="torsion_spring"]').is_visible()
        assert page.locator('[data-generator-pick="spring"]').is_hidden()
        assert "correspondant" in page.locator("#fjordGeneratorSearchStatus").inner_text()
        assert page.locator("#generatorKind option").count()<=3
        search.press("Enter")
        assert page.locator("#generatorKind").input_value()=="torsion_spring"
        search.fill("")
        assert page.locator('[data-generator-pick="spring"]').count()==1
        page.locator('[data-generator-pick="torsion_spring"]').evaluate("el=>el.click()")
        assert page.locator("#generatorKind").input_value()=="torsion_spring"
        assert page.locator("#generator-arm1").input_value()=="35"
        assert page.locator("#generator-opening").input_value()=="90"
        page.locator("#generatorShow").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelector('#generatorMessage').textContent.includes('Aperçu')",timeout=8000)
        page.locator("#generatorAdd").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelector('#sceneList').textContent.includes('Ressort à torsion')",timeout=10000)
        with page.expect_download() as down:
            page.locator("#save").evaluate("el=>el.click()")
        saved=json.loads(pathlib.Path(down.value.path()).read_text(encoding="utf-8"))
        mesh=saved["objects"][0]
        assert mesh["type"]=="imported"
        vertices=mesh["vertices"]
        assert len(vertices)>1000 and len(vertices)%9==0
        # Check all mesh triangle edges share exactly two triangles => closed continuous wire solid.
        def edge(a,b):
            return tuple(sorted((a,b)))
        def point(i):
            return tuple(round(v,3) for v in vertices[i:i+3])
        edges=collections.Counter()
        for i in range(0,len(vertices),9):
            a,b,c=point(i),point(i+3),point(i+6)
            assert a!=b and a!=c and b!=c,"Degenerate triangle"
            edges.update((edge(a,b),edge(b,c),edge(c,a)))
        unmatched={k:v for k,v in edges.items() if v!=2}
        assert not unmatched, f"Nonmanifold or open mesh, {len(unmatched)} unmatched edges: {list(unmatched.items())[:5]}"
        base_max_y=max(vertices[1::3]);base_min_y=min(vertices[1::3])
        assert base_max_y-base_min_y>40,"Expected independent straight leg geometry"
        # Parameters must actually alter geometry, not just labels.
        page.locator("#generator-arm1").fill("55")
        page.locator("#generator-opening").fill("150")
        page.locator("#generator-hand").fill("1")
        page.locator("#generatorAdd").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===2",timeout=10000)
        with page.expect_download() as more:
            page.locator("#save").evaluate("el=>el.click()")
        items=json.loads(pathlib.Path(more.value.path()).read_text(encoding="utf-8"))["objects"]
        assert items[1]["vertices"]!=items[0]["vertices"]
        # Impossible pitch must have a clear error and leave the bed intact.
        page.locator("#generator-pitch").fill("1")
        page.locator("#generatorAdd").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelector('#generatorMessage').innerText.includes('pas des spires')",timeout=10000)
        assert page.locator("#sceneList .scene-item").count()==2
        # The STL export button must still work.
        with page.expect_download() as exported:
            page.locator("#export").evaluate("el=>el.click()")
        assert exported.value.suggested_filename.endswith(".stl")
        assert not errors,errors
        print("Torsion spring: real closed wire geometry, parameters, preview, export, and paint access PASS")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=5)
