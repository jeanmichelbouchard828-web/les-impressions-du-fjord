"""End-to-end AMS palette: real swatch data, model color, saved metadata, fallback."""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8781
BASE=f"http://127.0.0.1:{PORT}"
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
    cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(30):
        try:
            urllib.request.urlopen(BASE+"/atelier3d.html",timeout=1)
            break
        except Exception:time.sleep(.25)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,args=[
            "--enable-webgl","--use-gl=angle","--use-angle=swiftshader",
            "--disable-dev-shm-usage","--no-sandbox"])
        page=browser.new_page(viewport={"width":1350,"height":830},accept_downloads=True)
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        palette={"connected":True,"available":True,"sources":[
            {"slot":"AMS 1 · Slot 1","color":"#FF6600","material":"PLA",
             "name":"PLA Basic","remaining":73},
            {"slot":"AMS 1 · Slot 2","color":"#0A8AFF","material":"PETG",
             "name":"PETG Basic"}]}
        def AMS(route):
            route.fulfill(status=200,content_type="application/json",body=json.dumps(palette))
        page.route("**/api/atelier/filaments",AMS)
        page.goto(BASE+"/atelier3d.html",wait_until="domcontentloaded")
        page.wait_for_function("window.__fjordEditorStarted === true",timeout=60000)
        page.wait_for_function("document.querySelectorAll('#fjordAmsSlots button').length===2",timeout=15000)
        # Shape and swatch controls work even if the floating drawer begins closed.
        page.locator('[data-shape="cube"]').evaluate("el=>el.click()")
        page.wait_for_function("document.querySelectorAll('#sceneList input[type=checkbox]').length===1")
        page.locator("#fjordAmsSlots button").first.evaluate("el=>el.click()")
        assert "appliquée" in page.locator("#fjordAmsStatus").inner_text()
        with page.expect_download() as first_download:
            page.locator("#save").evaluate("el=>el.click()")
        saved=json.loads(pathlib.Path(first_download.value.path()).read_text(encoding="utf-8"))
        cube=saved["objects"][0]
        assert cube["color"]==0xff6600,cube
        assert cube["filament"]["slot"]=="AMS 1 · Slot 1",cube
        assert cube["filament"]["material"]=="PLA",cube
        # Undo + redo must preserve both the color and AMS assignment.
        page.locator("#undo").evaluate("el=>el.click()")
        page.locator("#redo").evaluate("el=>el.click()")
        with page.expect_download() as second_download:
            page.locator("#save").evaluate("el=>el.click()")
        reloaded=json.loads(pathlib.Path(second_download.value.path()).read_text(encoding="utf-8"))
        assert reloaded["objects"][0]["color"]==0xff6600
        assert reloaded["objects"][0]["filament"]["slot"]=="AMS 1 · Slot 1"
        # Deliberately unavailable AMS must not fabricate an inventory.
        palette.update({"connected":False,"available":False,"sources":[]})
        page.locator("#fjordAmsRefresh").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelector('#fjordAmsStatus').innerText.includes('non connecté')",timeout=10000)
        assert page.locator("#fjordAmsSlots button").count()==0
        # Undo/redo restore intentionally clears the active object selection.
        page.locator("#sceneList .scene-item").first.evaluate("el=>el.click()")
        page.locator("#fjordManualColor").evaluate("el=>{el.value='#35AE73';el.dispatchEvent(new Event('change',{bubbles:true}));}")
        page.locator("#fjordApplyColor").evaluate("el=>el.click()")
        with page.expect_download() as third_download:
            page.locator("#save").evaluate("el=>el.click()")
        manual=json.loads(pathlib.Path(third_download.value.path()).read_text(encoding="utf-8"))
        assert manual["objects"][0]["color"]==0x35AE73,manual
        assert manual["objects"][0]["filament"] is None,manual
        assert not errors,errors
        print("AMS palette, 3D colour, project save, undo/redo, and offline fallback PASSED")
        browser.close()
finally:
    server.terminate()
    server.wait(timeout=5)
