"""Regression browser tests: editable 3D text, paint palette and blank click tool reset."""
import json
import zipfile
import xml.etree.ElementTree as ET
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
            content_type="application/json",body='{"connected":true,"available":true,"sources":[{"slot":"AMS A1","material":"PLA","name":"Rouge","color":"#E63838"},{"slot":"AMS A2","material":"PETG","name":"Bleu","color":"#2458E8"}]}'))
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
        # Legacy AMS colors are no longer a visible Properties panel.
        assert page.locator("#fjordAmsColors").is_hidden()
        assert page.locator("#fjordPaintOpenAms").count()==0
        assert page.locator("#fjordAmsSlots").is_hidden()
        assert page.locator("#fjordPaintFast").count()==1
        page.locator("#fjordPaintFast").evaluate("el=>el.click()")
        assert page.locator("#fjordPaintPanel").is_visible()
        assert page.locator("#fjordPaintFast").get_attribute("aria-pressed")=="true"
        page.wait_for_function("document.querySelectorAll('#fjordPaintAmsPalette button').length===2",timeout=8000)
        page.locator('#fjordPaintAmsPalette [data-fjord-color="#E63838"]').click()
        assert "#E63838" in page.locator("#fjordPaintColorLabel").inner_text()
        page.locator('#fjordPaintPresets [data-fjord-color="#25A3EB"]').click()
        assert "#25A3EB" in page.locator("#fjordPaintColorLabel").inner_text()
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
        # Paint mode must allow real camera orbiting, without repainting.
        camera_before=page.evaluate("window.fjordPaint.cameraState()")
        assert page.locator("#fjordPaintOrbit").count()==1
        assert page.locator("#fjordPaintOrbit").get_attribute("aria-pressed")=="false"
        cx=rect["x"]+rect["width"]*.50
        cy=rect["y"]+rect["height"]*.50
        # Right mouse rotates while the brush mode is still selected.
        page.mouse.move(cx,cy)
        page.mouse.down(button="right")
        page.mouse.move(cx+110,cy+45,steps=12)
        page.mouse.up(button="right")
        page.wait_for_timeout(500)
        camera_after_right=page.evaluate("window.fjordPaint.cameraState()")
        assert any(abs(a-b)>1e-3 for a,b in zip(camera_before["position"],camera_after_right["position"])), (camera_before,camera_after_right)
        assert page.locator("#fjordPaintPanel").is_visible()
        assert page.locator("#contextMenu").is_hidden()
        assert camera_after_right["rightButton"]==0, "Paint mode should map right drag to OrbitControls ROTATE"
        # Dedicated navigation toggle allows touch users to orbit using a single finger.
        page.locator("#fjordPaintOrbit").evaluate("el=>el.click()")
        assert page.locator("#fjordPaintOrbit").get_attribute("aria-pressed")=="true"
        page.mouse.move(cx,cy)
        page.mouse.down(button="left")
        page.mouse.move(cx-80,cy+35,steps=10)
        page.mouse.up(button="left")
        page.wait_for_timeout(300)
        camera_after_left=page.evaluate("window.fjordPaint.cameraState()")
        assert any(abs(a-b)>1e-3 for a,b in zip(camera_after_right["position"],camera_after_left["position"])), (camera_after_right,camera_after_left)
        assert page.locator("#fjordPaintPanel").is_visible()
        page.locator("#fjordPaintOrbit").evaluate("el=>el.click()")
        assert page.locator("#fjordPaintOrbit").get_attribute("aria-pressed")=="false"
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
        # The beta 3MF file is a real ZIP OPC package with per-face material colors.
        page.locator("#sceneList .scene-item").first.evaluate("el=>el.click()")
        with page.expect_download() as color_dl:
            page.locator("#exportColor3MF").evaluate("el=>el.click()")
        archive=pathlib.Path(color_dl.value.path())
        assert zipfile.is_zipfile(archive),"3MF must be a valid ZIP archive"
        with zipfile.ZipFile(archive) as z:
            assert set(z.namelist())=={"[Content_Types].xml","_rels/.rels","3D/3dmodel.model"}
            root=ET.fromstring(z.read("3D/3dmodel.model"))
            ns={"core":"http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
                "mat":"http://schemas.microsoft.com/3dmanufacturing/material/2015/02"}
            color_group=root.find("core:resources/mat:colorgroup",ns)
            assert color_group is not None
            palette=[c.get("color") for c in color_group]
            assert len(palette)>=2,palette
            triangles=root.findall(".//core:triangle",ns)
            assert len(triangles)>0
            labels={t.get("p1") for t in triangles}
            assert len(labels)>=2,labels
            assert all(t.get("pid")=="1" for t in triangles)
        print("Standard 3MF ZIP, coloured triangles and metadata PASSED")
        assert not errors,errors
        print("3D text creation/editing, actual face painting, palette, undo/redo and blank click reset PASSED")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=5)
