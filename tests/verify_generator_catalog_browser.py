"""Vérifie les vrais générateurs de catalogue dans Chrome avec export et sauvegarde."""
import io
import json
import pathlib
import subprocess
import sys
import time
import urllib.request
import wave
import math

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8777
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
        page=browser.new_page(viewport={"width":1380,"height":860},accept_downloads=True)
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto(BASE+"/atelier3d.html",wait_until="domcontentloaded")
        page.wait_for_function("window.__fjordEditorStarted === true",timeout=60000)
        print("Editor ready",flush=True)
        options=page.locator("#generatorKind option").evaluate_all("nodes=>nodes.map(n=>n.value)")
        expected=["ramp","curved_ramp","hinge_pin","hinge_leaf","hinge_articulated",
            "bearing","pivot","tee","sculpture","organic","voronoi","pulley","nut",
            "tap","washer","spring","turbine","coupler","funnel","grommet",
            "spoon","keychain","stamp","clamp","grill","roller","pawn","clock",
            "stand","box","mold","corrugated","tower","city"]
        page.on("dialog",lambda d:d.accept())
        for kind in expected:
            assert kind in options,kind
            page.select_option("#generatorKind",kind)
            page.locator("#generatorAdd").evaluate("el=>el.click()")
            page.wait_for_function("""kind=>document.querySelector("#sceneList").innerText.toLowerCase().includes(
              ({ramp:"rampe",hinge_pin:"charnière",hinge_leaf:"charnière",
              hinge_articulated:"charnière",bearing:"roulement",city:"quartier"}[kind]||"")
            ) && document.querySelectorAll("#sceneList input[type=checkbox]").length>0""",arg=kind,timeout=18000)
            message=page.locator("#generatorMessage").inner_text()
            assert "invalide" not in message.lower() and "erreur" not in message.lower(),(kind,message)
            with page.expect_download() as dl:
                page.locator("#save").evaluate("el=>el.click()")
            saved=json.loads(pathlib.Path(dl.value.path()).read_text(encoding="utf-8"))
            assert len(saved["objects"])>=1,kind
            assert saved["objects"][-1]["type"]=="imported",kind
            assert len(saved["objects"][-1]["vertices"])>=9,kind
            page.locator("#resetProject").evaluate("el=>el.click()")
            page.wait_for_function("document.querySelectorAll('#sceneList input[type=checkbox]').length===0",timeout=5000)
            print("OK",kind,flush=True)
        # Real image relief using uploaded pixels, not a placeholder shape.
        image=Image.new("RGB",(34,24),(175,55,30));buf=io.BytesIO();image.save(buf,"PNG")
        for kind in ("lithophane","image_relief","portrait_relief"):
            page.select_option("#generatorKind",kind)
            page.locator("#generatorImageFile").set_input_files({
              "name":"photo.png","mimeType":"image/png","buffer":buf.getvalue()})
            page.wait_for_function("document.querySelector('#generatorAssetStatus').innerText.includes('prête')",timeout=10000)
            page.locator("#generatorAdd").evaluate("el=>el.click()")
            page.wait_for_function("document.querySelectorAll('#sceneList input[type=checkbox]').length===1",timeout=12000)
            page.locator("#resetProject").evaluate("el=>el.click()")
            print("OK",kind,flush=True)
        page.select_option("#generatorKind","braille")
        page.locator("#generatorAdd").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelectorAll('#sceneList input[type=checkbox]').length===1",timeout=10000)
        page.locator("#resetProject").evaluate("el=>el.click()")
        print("OK braille",flush=True)
        # Provide a genuine WAV waveform for the audio-to-relief generator.
        wav=io.BytesIO()
        with wave.open(wav,"wb") as sound:
            sound.setnchannels(1);sound.setsampwidth(2);sound.setframerate(8000)
            samples=bytearray()
            for i in range(4000):
                sample=int(24000*math.sin(2*math.pi*440*i/8000))
                samples.extend(sample.to_bytes(2,"little",signed=True))
            sound.writeframes(bytes(samples))
        page.select_option("#generatorKind","waveform")
        page.locator("#generatorAudioFile").set_input_files({
         "name":"voix.wav","mimeType":"audio/wav","buffer":wav.getvalue()})
        page.wait_for_function("document.querySelector('#generatorAssetStatus').innerText.includes('prête')",timeout=12000)
        page.locator("#generatorAdd").evaluate("el=>el.click()")
        page.wait_for_function("document.querySelectorAll('#sceneList input[type=checkbox]').length===1",timeout=10000)
        print("OK waveform",flush=True)
        assert not errors,errors
        browser.close()
        print("All generator catalogue browser checks succeeded",flush=True)
finally:
    server.terminate()
    server.wait(timeout=5)
