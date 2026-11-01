"""X2D admin flow: choose once, remember only after success, then one-click prepare."""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from private_fjord import admin_studio
PORT=8876
BASE=f"http://127.0.0.1:{PORT}"
TEST_HTML=ROOT/"atelier3d_auto_print_e2e.html"
TEST_HTML.write_text(admin_studio((ROOT/"atelier3d.html").read_text(encoding="utf-8"),
                                 "test_csrf_token"),encoding="utf-8")
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
                        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(50):
  try:
   urllib.request.urlopen(BASE+"/"+TEST_HTML.name,timeout=1)
   break
  except Exception:time.sleep(.25)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,args=["--enable-webgl","--use-gl=angle",
    "--use-angle=swiftshader","--disable-dev-shm-usage","--no-sandbox"])
  page=browser.new_page(viewport={"width":1440,"height":900})
  errors=[]
  page.on("pageerror",lambda e:errors.append(str(e)))
  inventory={"engine_ready":True,"profiles":{
     "Imprimante":[{"id":1,"name":"X2D 0.4","model":"Bambu Lab X2D","nozzle":"0.4"}],
     "Impression":[{"id":2,"name":"0.20 standard","layer":"0.2"}],
     "Filament":[{"id":3,"name":"PETG bleu","material":"PETG"}]}}
  slices=[];transfers=[]
  review={"source":"G-code réel du 3MF Bambu Studio","layer_count":2,"total_moves":4,
          "sampled":False,"layers":[
           {"z":0.2,"moves":2,"segments":[[100,100,120,100],[120,100,120,120]]},
           {"z":0.4,"moves":2,"segments":[[100,100,125,100],[125,100,125,125]]}]}
  page.route("**/admin/atelier-imprimer/preparer",lambda route:(
    slices.append(route.request.post_data_buffer),
    route.fulfill(status=200,content_type="application/json",
      body=json.dumps({"ok":True,"stage":"a"*40,"preview":review}))))
  def transfer(route):
   transfers.append(route.request.post_data)
   route.fulfill(status=200,content_type="application/json",
     body=json.dumps({"ok":True,"file":"gcode/fjord_auto_test.3mf",
       "next":"/admin/atelier-imprimer?selected=gcode/fjord_auto_test.3mf"}))
  page.route("**/admin/atelier-imprimer/transmettre",transfer)
  page.route("**/admin/atelier-imprimer?selected=*",lambda route:route.fulfill(
    status=200,content_type="text/html",body="<h1>Étape 3 : Confirmer et démarrer</h1>"))
  page.on("dialog",lambda dialog:dialog.accept())
  def prepare_scene():
   page.goto(BASE+"/"+TEST_HTML.name,wait_until="domcontentloaded")
   page.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
   page.locator('[data-shape="cube"]').evaluate("el=>el.click()")
   page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
  prepare_scene()
  assert page.locator("#fjordAutoPrintLauncher").count()==1
  page.locator("#fjordPrintShortcut").evaluate("el=>el.click()")
  assert page.locator("#fjordAutoPrintDialog").is_visible()
  page.wait_for_function("document.querySelector('#fjordAutoForm [name=machine]').value==='1'",timeout=15000)
  assert page.locator('[name="machine"]').input_value()=="1"
  assert page.locator('[name="process"]').input_value()=="2"
  assert page.locator('[name="filament"]').input_value()=="3"
  assert len(slices)==0 and len(transfers)==0,"No automatic transmission at initial selection"
  page.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  page.wait_for_function("!document.querySelector('#fjordSliceReview').hidden",timeout=30000)
  assert len(slices)==1 and len(transfers)==0,"Slice must never auto-upload"
  assert page.locator("#fjordReviewCanvas").is_visible()
  assert page.locator("#fjordReviewLayer").get_attribute("max")=="1"
  page.locator("#fjordReviewLayer").evaluate("""el=>{
    el.value='0';el.dispatchEvent(new Event('input',{bubbles:true}));}""")
  assert "Z 0.20 mm" in page.locator("#fjordReviewLabel").inner_text()
  assert "G-code" in page.locator("#fjordSliceReview").inner_text()
  assert page.evaluate("localStorage.getItem('fjord-x2d-profile-preferences-v1')") is None
  page.locator("#fjordReviewTransfer").evaluate("el=>el.click()")
  page.wait_for_url("**/admin/atelier-imprimer?selected=**",wait_until="commit",timeout=12000)
  assert len(transfers)==1 and len(slices)==1
  saved=page.evaluate("JSON.parse(localStorage.getItem('fjord-x2d-profile-preferences-v1'))")
  assert saved["PETG|0.2"]=={"machine":"1","process":"2","filament":"3"},saved
  # Previously remembered settings auto-slice but still require preview approval.
  prepare_scene()
  page.locator("#fjordPrintShortcut").evaluate("el=>el.click()")
  page.wait_for_function("!document.querySelector('#fjordSliceReview').hidden",timeout=30000)
  assert len(slices)==2 and len(transfers)==1,"Even remembered profiles must wait for approval"
  page.locator("#fjordReviewTransfer").evaluate("el=>el.click()")
  page.wait_for_url("**/admin/atelier-imprimer?selected=**",wait_until="commit",timeout=12000)
  assert len(transfers)==2
  assert all(b'name="material"' in (chunk or b"") for chunk in slices)
  assert not errors,errors
  browser.close()
 print("OK: verified toolpath review before explicit upload; remembered profiles still require approval")
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except Exception:server.kill()
 TEST_HTML.unlink(missing_ok=True)
