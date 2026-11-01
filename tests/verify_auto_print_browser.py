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
  page.route("**/api/admin/atelier/impression-profils",lambda route:route.fulfill(
    status=200,content_type="application/json",body=json.dumps(inventory)))
  page.route("**/api/atelier/filaments",lambda route:route.fulfill(
    status=200,content_type="application/json",body='{"connected":false,"available":false,"sources":[]}'))
  slices=[];transfers=[];starts=[]
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
       "nonce":"one-use-confirmation-token-0123456789",
       "next":"/admin/atelier-imprimer?selected=gcode/fjord_auto_test.3mf"}))
  page.route("**/admin/atelier-imprimer/transmettre",transfer)
  page.route("**/api/admin/atelier/impression-etat",lambda route:route.fulfill(
    status=200,content_type="application/json",
    body=json.dumps({"ok":True,"state":"idle","progress":0,"file":"",
                     "can_start":True})))
  def start(route):
   starts.append(route.request.post_data)
   route.fulfill(status=200,content_type="application/json",
       body=json.dumps({"ok":True,"message":"Commande de démarrage acceptée."}))
  page.route("**/admin/atelier-imprimer/demarrer-atelier",start)
  page.on("dialog",lambda dialog:dialog.accept())
  def prepare_scene():
   page.goto(BASE+"/"+TEST_HTML.name,wait_until="domcontentloaded")
   page.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
   page.locator('[data-shape="cube"]').evaluate("el=>el.click()")
   page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
  prepare_scene()
  assert page.locator("#fjordAutoPrintLauncher").count()==1
  assert page.locator("#fjordPrintShortcut").count()==1
  assert page.locator("header #fjordPrintShortcut").count()==0,"Print CTA should not crowd header"
  page.locator("#sliceTop").evaluate("el=>el.click()")
  assert page.locator("#sliceFloat #fjordPrintShortcut").is_visible(),"Print belongs in Trancher"
  # Key estimated slice results must be above the profile/settings controls.
  assert page.evaluate("""() => {
    const slice=document.querySelector('#sliceFloat');
    const result=slice.querySelector('.slice-results-top');
    const settings=slice.querySelector('.slice-settings');
    const details=slice.querySelector('.slice-more-details');
    return result&&settings&&details&&
      !!(result.compareDocumentPosition(settings)&Node.DOCUMENT_POSITION_FOLLOWING) &&
      details.querySelector('#sliceDimensionsValue')!==null;
  }"""),"Summary must precede settings, and detailed metrics remain accessible"
  assert page.locator("#sliceFloat #slicePrice").is_visible()
  page.locator("#fjordPrintShortcut").click()
  assert page.locator("#fjordAutoPrintDialog").is_visible()
  try:
   page.wait_for_function("document.querySelector('#fjordAutoForm [name=machine]').value==='1'",timeout=8000)
  except Exception:
   print("X2D UI DEBUG",page.evaluate("""() => ({
      ready:!!window.__fjordEditorStarted,
      dialog:document.querySelector('#fjordAutoPrintDialog')?.open,
      state:document.querySelector('#fjordAutoState')?.innerText,
      machine:document.querySelector('#fjordAutoForm [name=machine]')?.value,
      selects:[...document.querySelectorAll('#fjordAutoForm select')].map(el=>el.outerHTML.slice(0,350)),
      preview:document.querySelector('#fjordSliceReview')?.outerHTML.slice(0,280)
     })"""),"JS ERRORS",errors)
   raise
  assert page.locator('[name="machine"]').input_value()=="1"
  assert page.locator('[name="process"]').input_value()=="2"
  assert page.locator('[name="filament"]').input_value()=="3"
  assert len(slices)==0 and len(transfers)==0,"No automatic transmission at initial selection"
  page.locator('#fjordAutoForm [name=bed_type]').select_option('Textured PEI Plate')
  page.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  page.wait_for_function("!document.querySelector('#fjordSliceReview').hidden",timeout=30000)
  assert len(slices)==1 and len(transfers)==0,"Slice must never auto-upload"
  assert page.locator("#fjordReviewCanvas").is_visible()
  assert page.evaluate("""() => {
    const review=document.querySelector('#fjordSliceReview');
    return review.previousElementSibling?.classList.contains('fjord-dialog-head');
  }"""),"True Bambu preview must appear immediately under the dialog title"
  assert page.locator("#fjordReviewLayer").get_attribute("max")=="1"
  page.locator("#fjordReviewLayer").evaluate("""el=>{
    el.value='0';el.dispatchEvent(new Event('input',{bubbles:true}));}""")
  assert "Z 0.20 mm" in page.locator("#fjordReviewLabel").inner_text()
  assert "G-code" in page.locator("#fjordSliceReview").inner_text()
  assert page.evaluate("localStorage.getItem('fjord-x2d-profile-preferences-v1')") is None
  page.locator("#fjordReviewTransfer").evaluate("el=>el.click()")
  page.wait_for_function("!document.querySelector('#fjordStartAtelier').hidden",timeout=12000)
  assert "/atelier3d_auto_print_e2e.html" in page.url, "Must not leave Atelier"
  assert len(transfers)==1 and len(slices)==1 and not starts
  page.wait_for_function("document.querySelector('#fjordLiveState').textContent.includes('Prête')")
  assert page.locator("#fjordStartNow").is_disabled()
  page.locator("#fjordStartVerified").evaluate("el=>el.click()")
  page.locator("#fjordStartCleared").evaluate("el=>el.click()")
  assert page.locator("#fjordStartNow").is_enabled()
  page.locator("#fjordStartNow").evaluate("el=>el.click()")
  page.wait_for_function("document.querySelector('#fjordStartResult').textContent.includes('acceptée')",timeout=12000)
  assert len(starts)==1,starts
  assert page.locator("#fjordStartNow").is_disabled()
  assert page.locator("#fjordStartAtelier").is_visible()
  saved=page.evaluate("JSON.parse(localStorage.getItem('fjord-x2d-profile-preferences-v1'))")
  assert saved["PETG|0.2"]=={"machine":"1","process":"2","filament":"3","bed_type":"Textured PEI Plate"},saved
  # Previously remembered settings auto-slice but still require preview approval.
  prepare_scene()
  page.locator("#fjordPrintShortcut").evaluate("el=>el.click()")
  page.wait_for_function("!document.querySelector('#fjordSliceReview').hidden",timeout=30000)
  assert len(slices)==2 and len(transfers)==1 and len(starts)==1,"Remembered profiles must await review"
  page.locator("#fjordReviewTransfer").evaluate("el=>el.click()")
  page.wait_for_function("!document.querySelector('#fjordStartAtelier').hidden",timeout=12000)
  assert len(transfers)==2 and len(starts)==1,"Transferring must not automatically start"
  assert page.locator("#fjordStartNow").is_disabled()
  assert all(b'name="material"' in (chunk or b"") for chunk in slices)
  assert not errors,errors

  # Mobile review uses a true full-height sheet, accessible layer controls,
  # and finger-friendly zoom without uploading before approval.
  mobile=browser.new_page(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
  mobile_errors=[]
  mobile.on("pageerror",lambda e:mobile_errors.append(str(e)))
  mobile.route("**/api/admin/atelier/impression-profils",lambda route:route.fulfill(
    status=200,content_type="application/json",body=json.dumps(inventory)))
  mobile.route("**/api/atelier/filaments",lambda route:route.fulfill(
    status=200,content_type="application/json",body='{"connected":false,"available":false,"sources":[]}'))
  mobile.route("**/admin/atelier-imprimer/preparer",lambda route:route.fulfill(
    status=200,content_type="application/json",
    body=json.dumps({"ok":True,"stage":"b"*40,"preview":review})))
  mobile.route("**/admin/atelier-imprimer/transmettre",lambda route:route.fulfill(
    status=200,content_type="application/json",
    body=json.dumps({"ok":True,"file":"gcode/fjord_mobile_demo.3mf",
       "nonce":"mobile-confirmation-0123456789abcdefghijk"})))
  mobile.route("**/api/admin/atelier/impression-etat",lambda route:route.fulfill(
    status=200,content_type="application/json",
    body=json.dumps({"ok":True,"state":"idle","can_start":True,
                     "progress":0,"file":""})))
  mobile.on("dialog",lambda dialog:dialog.accept())
  mobile.goto(BASE+"/"+TEST_HTML.name,wait_until="domcontentloaded")
  mobile.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
  mobile.locator('[data-shape="cube"]').evaluate("el=>el.click()")
  mobile.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
  mobile.wait_for_function("document.documentElement.scrollWidth <= window.innerWidth+2")
  # Editing maximises 3D plate without losing any file/admin/mobile tools.
  assert mobile.evaluate("""() => {
    const hdr=document.querySelector('header.fjord-admin-header');
    const stage=document.querySelector('#stage');
    return hdr.getBoundingClientRect().height<=56 &&
      stage.getBoundingClientRect().height >= window.innerHeight-150 &&
      getComputedStyle(document.querySelector('.fjord-menubar')).display==='none' &&
      getComputedStyle(document.querySelector('.quickbar')).display==='none' &&
      document.querySelector('#projectMenuButton')!==null &&
      document.querySelector('#fjordAdminShortcut')!==null;
  }"""),"Full-height phone plate with compact accessible header"
  mobile.locator("#mobileSliceBtn").evaluate("el=>el.click()")
  assert mobile.evaluate("document.body.classList.contains('fjord-mobile-slicing')"),"Slicer must enter fullscreen"
  assert mobile.evaluate("""() => {
   const pane=document.querySelector('#sliceFloat').getBoundingClientRect();
   const stage=document.querySelector('#stage').getBoundingClientRect();
   const footer=document.querySelector('.fjord-slice-print-entry').getBoundingClientRect();
   return pane.left>=-2&&pane.right<=innerWidth+2&&
     Math.abs(pane.bottom-innerHeight)<2 &&
     pane.height>=innerHeight*.5 &&
     stage.width>=innerWidth-2 &&
     footer.bottom<=innerHeight+2 && footer.top>=pane.top &&
     !document.querySelector('.fjord-slice-print-entry').parentElement.classList.contains('fjord-slice-scroll');
  }"""),"Fullscreen slice with fixed print footer and live build plate"
  mobile.locator("#sliceBuildTab").evaluate("el=>el.click()")
  assert mobile.locator("#sliceBuildPanel").is_visible(),"Construction tab must remain accessible"
  assert mobile.locator("#sliceHeadSlider").count()==1
  assert mobile.locator("#slicePlayPause").count()==1
  mobile.locator("#fjordSliceContents").evaluate("el=>el.scrollTop=el.scrollHeight")
  assert mobile.locator("#fjordPrintShortcut").is_visible(),"Printer must stay visible after scroll"
  mobile.locator("#sliceViewSize").evaluate("el=>el.click()")
  assert mobile.evaluate("document.body.classList.contains('fjord-slice-model-focus')")
  assert mobile.evaluate("document.querySelector('#sliceFloat').getBoundingClientRect().height<innerHeight*.45")
  mobile.locator("#sliceViewSize").evaluate("el=>el.click()")
  assert not mobile.evaluate("document.body.classList.contains('fjord-slice-model-focus')")
  mobile.locator("#sliceLayersTab").evaluate("el=>el.click()")
  assert mobile.locator("#sliceLayersPanel").is_visible()
  mobile.locator("#fjordSliceContents").evaluate("el=>el.scrollTop=0")
  assert mobile.locator("#sliceFloat").is_visible(),"Mobile slice drawer should open"
  assert mobile.locator("#sliceFloat #fjordPrintShortcut").is_visible()
  assert mobile.locator("#sliceFloat .fjord-slice-scroll").is_visible()
  assert mobile.locator("#sliceFloat .slice-results-top").is_visible()
  assert mobile.evaluate("""() => {
    const result=document.querySelector('#sliceFloat .slice-results-top');
    const settings=document.querySelector('#sliceFloat .slice-settings');
    return result.getBoundingClientRect().top < settings.getBoundingClientRect().top;
  }"""),"Slice results should be the first information block on mobile"
  layout=mobile.evaluate("""() => {
    const ids=['#fjordWorkspace .stage','#sliceFloat','#fjordPrintShortcut','#fjordAdminShortcut'];
    return ids.map(id=>{
      const box=document.querySelector(id)?.getBoundingClientRect();
      return {id,left:box?.left,right:box?.right,width:box?.width};
    });
  }""")
  assert all(q["left"]>=-2 and q["right"]<=392 for q in layout),layout
  mobile.locator("#fjordPrintShortcut").click()
  mobile.wait_for_function("document.querySelector('#fjordAutoForm [name=machine]').value==='1'",timeout=15000)
  mobile.locator('#fjordAutoForm [name=bed_type]').select_option('Textured PEI Plate')
  mobile.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  mobile.wait_for_function("!document.querySelector('#fjordSliceReview').hidden",timeout=20000)
  mobile.wait_for_function("document.querySelector('#fjordAutoPrintDialog').scrollTop <= 2",timeout=5000)
  assert mobile.evaluate("""() => {
    const dlg=document.querySelector('#fjordAutoPrintDialog');
    const review=dlg.querySelector('#fjordSliceReview');
    const header=dlg.querySelector('.fjord-dialog-head');
    const canvas=dlg.querySelector('#fjordReviewCanvas');
    return review.previousElementSibling===header &&
      getComputedStyle(dlg.querySelector('.fjord-auto-intro')).display==='none' &&
      canvas.getBoundingClientRect().top < window.innerHeight*.65;
  }"""),"Mobile Bambu result must be visible high in the dialog without scrolling"
  rect=mobile.locator("#fjordAutoPrintDialog").bounding_box()
  assert rect and rect["width"] >= 380,rect
  assert mobile.locator("#fjordReviewLayer").is_visible()
  assert mobile.locator("#fjordReviewTransfer").is_visible()
  assert not mobile.locator("#fjordAutoForm").is_visible(),"Profiles should yield room to layer preview on mobile"
  canvas=mobile.locator("#fjordReviewCanvas")
  original=canvas.evaluate("el=>el.toDataURL()")
  mobile.locator("#fjordReviewZoomIn").evaluate("el=>el.click()")
  zoomed=canvas.evaluate("el=>el.toDataURL()")
  assert original!=zoomed,"Mobile preview zoom should visually alter the toolpath canvas"
  mobile.locator("#fjordReviewPrevious").evaluate("el=>el.click()")
  assert "1 / 2" in mobile.locator("#fjordReviewLabel").inner_text()
  mobile.locator("#fjordReviewNext").evaluate("el=>el.click()")
  assert "2 / 2" in mobile.locator("#fjordReviewLabel").inner_text()
  # Verify the final printer controls stay inside the mobile Atelier.
  mobile.locator("#fjordReviewTransfer").evaluate("el=>el.click()")
  mobile.wait_for_function("!document.querySelector('#fjordStartAtelier').hidden",timeout=12000)
  mobile.wait_for_function("document.querySelector('#fjordLiveState').textContent.includes('Prête')",timeout=12000)
  assert mobile.locator("#fjordStartNow").is_disabled()
  assert mobile.locator("#fjordStartVerified").is_visible()
  assert mobile.locator("#fjordStartCleared").is_visible()
  mobile.locator("#fjordStartVerified").evaluate("el=>el.click()")
  mobile.locator("#fjordStartCleared").evaluate("el=>el.click()")
  assert mobile.locator("#fjordStartNow").is_enabled()
  assert "atelier3d_auto_print_e2e.html" in mobile.url
  mobile.locator("#fjordStartAnother").evaluate("el=>el.click()")
  assert mobile.locator("#fjordStartAtelier").is_hidden()
  assert mobile.locator("#fjordAutoForm").is_visible()
  # A fresh slice remains available without requiring a page change.
  mobile.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  mobile.wait_for_function("!document.querySelector('#fjordSliceReview').hidden",timeout=20000)
  mobile.locator("#fjordReviewRedo").evaluate("el=>el.click()")
  assert mobile.locator("#fjordSliceReview").is_hidden()
  assert mobile.locator("#fjordAutoForm").is_visible(),"Edit and re-slice must restore accessible profiles"
  # Closing the preview must return the compact editor, not trap the phone
  # in a blank full-screen overlay.
  mobile.locator("#fjordAutoClose").evaluate("el=>el.click()")
  mobile.locator("#sliceClose").evaluate("el=>el.click()")
  assert not mobile.evaluate("document.body.classList.contains('fjord-mobile-slicing')")
  assert mobile.locator("#mobileIconBar").is_visible()
  assert not mobile_errors,mobile_errors
  mobile.close()
  # New X2D factory profiles must be selected first even if a previous
  # CHATOU custom choice is remembered. Custom options are never deleted.
  factory=browser.new_page(viewport={"width":400,"height":830},is_mobile=True,has_touch=True)
  official={"engine_ready":True,"profiles":{
    "Imprimante":[
      {"id":"stock:machine:x2d04","name":"Bambu d'origine · X2D","official":True,
       "model":"Bambu Lab X2D","nozzle":"0.4"},
      {"id":1,"name":"CHATOU X2D","model":"Bambu Lab X2D","nozzle":"0.4"}],
    "Impression":[
      {"id":"stock:process:020","name":"Bambu d'origine · 0.20 mm","official":True,"layer":"0.2"},
      {"id":2,"name":"CHATOU Quotidien","layer":"0.2"}],
    "Filament":[
      {"id":"stock:filament:PETG","name":"Bambu d'origine · Generic PETG",
       "official":True,"material":"PETG"},
      {"id":3,"name":"CHATOU PETG Frostbite","material":"PETG"}]
  }}
  factory.route("**/api/admin/atelier/impression-profils",lambda route:route.fulfill(
    status=200,content_type="application/json",body=json.dumps(official)))
  factory.route("**/api/atelier/filaments",lambda route:route.fulfill(
    status=200,content_type="application/json",
    body='{"connected":false,"available":false,"sources":[]}'))
  factory.goto(BASE+"/"+TEST_HTML.name,wait_until="domcontentloaded")
  factory.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
  factory.evaluate("""() => localStorage.setItem(
    'fjord-x2d-profile-preferences-v1',
    JSON.stringify({'PETG|0.2':{'machine':'1','process':'2','filament':'3'}}))""")
  factory.locator('[data-shape="cube"]').evaluate("el=>el.click()")
  factory.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
  factory.locator("#fjordAutoPrintLauncher").evaluate("el=>el.click()")
  factory.wait_for_function(
    "document.querySelector('#fjordAutoForm [name=machine]')?.value==='stock:machine:x2d04'",
    timeout=15000)
  assert factory.locator('[name=process]').input_value()=="stock:process:020"
  assert factory.locator('[name=filament]').input_value()=="stock:filament:PETG"
  assert factory.locator('[name=filament] option').count()==3, "The original and CHATOU must both remain"
  assert factory.locator("#fjordAutoSubmit").is_disabled(), "Plate must be selected explicitly"
  factory.locator('#fjordAutoForm [name=bed_type]').select_option('Textured PEI Plate')
  assert factory.locator("#fjordAutoSubmit").is_enabled()
  # Regression for a simple piece that merely entered Paint mode: the mode
  # creates vertexColors + an empty face map, which is NOT a multicolor piece.
  sent_mono=[]
  def simulated_failure(route):
   sent_mono.append(route.request.post_data_buffer)
   route.fulfill(status=422,content_type="application/json",
     body=json.dumps({"ok":False,"error":"Erreur simulée, aucun envoi"}))
  factory.route("**/admin/atelier-imprimer/preparer",simulated_failure)
  factory.locator("#fjordAutoClose").evaluate("el=>el.click()")
  project={"version":1,"objects":[{
    "type":"cube","name":"Cube PETG essai","position":[0,0,12.5],
    "rotation":[0,0,0],"scale":[1,1,1],"color":0x5bc6eb,
    "paintBase":0x5bc6eb,"paintFaces":{}
  }]}
  def import_project(doc):
   factory.locator("#projectFile").set_input_files([])
   factory.locator("#projectFile").set_input_files({
     "name":"fjord_color_test.json","mimeType":"application/json",
     "buffer":json.dumps(doc).encode("utf-8")})
   factory.wait_for_function("document.querySelector('#sceneList')?.textContent.includes('Cube PETG essai')")
  import_project(project)
  factory.locator("#fjordAutoPrintLauncher").evaluate("el=>el.click()")
  factory.wait_for_function("document.querySelector('#fjordAutoForm [name=machine]').value==='stock:machine:x2d04'")
  factory.locator('#fjordAutoForm [name=bed_type]').select_option('Textured PEI Plate')
  assert factory.locator("#fjordMonoApproval").is_hidden(), \
    "An untouched paint buffer must not block a monochrome cube"
  factory.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  factory.wait_for_function("document.querySelector('#fjordAutoState').textContent.includes('Erreur simulée')",timeout=15000)
  assert len(sent_mono)==1,"Untouched paint mode must allow slicing"

  # Actually colored face cannot be silently stripped. Make the explicit
  # single-color consent visible, then allow a *staged*, not physical, attempt.
  factory.locator("#fjordAutoClose").evaluate("el=>el.click()")
  project["objects"][0]["paintFaces"]={"0":"#E73B3B"}
  import_project(project)
  factory.locator("#fjordAutoPrintLauncher").evaluate("el=>el.click()")
  factory.wait_for_function("document.querySelector('#fjordMonoApproval')?.hidden===false")
  factory.locator('#fjordAutoForm [name=bed_type]').select_option('Textured PEI Plate')
  assert factory.locator("#fjordMonoConsent").is_visible()
  assert not factory.locator("#fjordMonoConsent").is_checked()
  factory.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  assert len(sent_mono)==1,"A multicolor model cannot auto-strip AMS colors"
  assert "coche" in factory.locator("#fjordAutoState").inner_text()
  factory.locator("#fjordMonoConsent").evaluate("el=>el.click()")
  factory.locator("#fjordAutoSubmit").evaluate("el=>el.click()")
  factory.wait_for_function("document.querySelector('#fjordAutoState').textContent.includes('Erreur simulée')",timeout=15000)
  assert len(sent_mono)==2,"Consent should authorize a single-color slicing attempt only"
  factory.close()
  browser.close()
 print("OK: verified toolpath review before explicit upload; remembered profiles still require approval")
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except Exception:server.kill()
 TEST_HTML.unlink(missing_ok=True)
