"""Browser regression: right-click a generated part, edit it in-place and round-trip its settings."""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8814
BASE=f"http://127.0.0.1:{PORT}"
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
 cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(60):
  try:
   urllib.request.urlopen(BASE+"/atelier3d.html",timeout=1)
   break
  except Exception: time.sleep(.2)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,args=["--enable-webgl","--use-gl=angle",
   "--use-angle=swiftshader","--disable-dev-shm-usage","--no-sandbox"])
  page=browser.new_page(viewport={"width":1400,"height":900},accept_downloads=True)
  errors=[]
  page.on("pageerror",lambda e:errors.append(str(e)))
  page.route("**/api/atelier/filaments",lambda route:route.fulfill(status=200,
   content_type="application/json",body='{"connected":false,"available":false,"sources":[]}'))
  page.goto(BASE+"/atelier3d.html",wait_until="domcontentloaded")
  page.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)

  def save():
   with page.expect_download() as result:
    page.locator("#save").evaluate("el=>el.click()")
   return json.loads(pathlib.Path(result.value.path()).read_text(encoding="utf-8"))

  page.locator("#generatorKind").evaluate("""el=>{
   el.value='pipe';el.dispatchEvent(new Event('change',{bubbles:true}));
  }""")
  page.locator("#generator-diameter").evaluate("""el=>{
   el.value='72';el.dispatchEvent(new Event('input',{bubbles:true}));
  }""")
  page.locator("#generatorAdd").evaluate("el=>el.click()")
  page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1",timeout=12000)
  original=save()["objects"][0]
  assert original["generator"]["kind"]=="pipe",original
  assert original["generator"]["params"]["diameter"]==72,original["generator"]
  assert original["type"]=="imported" and len(original["vertices"])>500

  # A right-click hits the actual rendered solid, not just a list item.
  rect=page.locator("#stage canvas").first.bounding_box()
  assert rect
  opened=False
  for fx,fy in [(.50,.50),(.50,.47),(.52,.52),(.48,.47),(.50,.55),(.46,.50)]:
   page.mouse.click(rect["x"]+rect["width"]*fx,rect["y"]+rect["height"]*fy,button="right")
   if page.locator('#contextMenu [data-context-action="editGenerator"]').is_visible():
    opened=True
    break
  assert opened,"The generated object's right-click menu must offer Edit Generator"
  page.locator('#contextMenu [data-context-action="editGenerator"]').evaluate("el=>el.click()")
  assert page.locator("#generatorKind").input_value()=="pipe"
  assert page.locator("#generatorKind").is_disabled()
  assert page.locator("#generator-diameter").input_value()=="72"
  assert page.locator("#generatorCancelEdit").is_visible()
  assert "Appliquer" in page.locator("#generatorAdd").inner_text()

  # Cancel without modifying must retain one exact object.
  page.locator("#generator-diameter").evaluate("""el=>{
   el.value='84';el.dispatchEvent(new Event('input',{bubbles:true}));
  }""")
  page.locator("#generatorCancelEdit").evaluate("el=>el.click()")
  assert save()["objects"][0]["generator"]["params"]["diameter"]==72
  # Reopen the editor via menu, apply to the same mesh, preserve part name and position.
  for fx,fy in [(.50,.50),(.50,.47),(.52,.52),(.48,.47),(.50,.55),(.46,.50)]:
   page.mouse.click(rect["x"]+rect["width"]*fx,rect["y"]+rect["height"]*fy,button="right")
   if page.locator('#contextMenu [data-context-action="editGenerator"]').is_visible():
    break
  assert page.locator('#contextMenu [data-context-action="editGenerator"]').is_visible()
  page.locator('#contextMenu [data-context-action="editGenerator"]').evaluate("el=>el.click()")
  page.locator("#generator-diameter").evaluate("""el=>{
   el.value='96';el.dispatchEvent(new Event('input',{bubbles:true}));
  }""")
  page.locator("#generatorAdd").evaluate("el=>el.click()")
  page.wait_for_function("document.querySelector('#generatorMessage').innerText.includes('Pièce modifiée')",timeout=10000)
  edited=save()["objects"]
  assert len(edited)==1,edited
  assert edited[0]["name"]==original["name"]
  assert edited[0]["generator"]["params"]["diameter"]==96
  assert edited[0]["vertices"]!=original["vertices"]

  page.locator("#undo").evaluate("el=>el.click()")
  assert save()["objects"][0]["generator"]["params"]["diameter"]==72
  page.locator("#redo").evaluate("el=>el.click()")
  assert save()["objects"][0]["generator"]["params"]["diameter"]==96

  # Undo/redo restores the geometry but clears the selection; reselect it.
  page.locator("#sceneList .scene-item").first.evaluate("el=>el.click()")
  page.locator("#duplicate").evaluate("el=>el.click()")
  duplicated=save()["objects"]
  assert len(duplicated)==2
  assert duplicated[1]["generator"]["params"]["diameter"]==96
  with page.expect_download() as exported:
   page.locator("#save").evaluate("el=>el.click()")
  path=pathlib.Path(exported.value.path())
  page.locator("#resetProject").evaluate("el=>el.click()")
  page.locator("#projectFile").set_input_files({"name":"ProjetFjord.json",
   "mimeType":"application/json","buffer":path.read_bytes()})
  page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===2",timeout=10000)
  restored=save()["objects"]
  assert len(restored)==2 and all(o["generator"]["params"]["diameter"]==96 for o in restored)

  # An ordinary primitive has no source generator to modify.
  page.locator("#resetProject").evaluate("el=>el.click()")
  page.locator('[data-shape="cube"]').evaluate("el=>el.click()")
  page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
  for fx,fy in [(.50,.50),(.52,.52),(.48,.47),(.50,.55)]:
   page.mouse.click(rect["x"]+rect["width"]*fx,rect["y"]+rect["height"]*fy,button="right")
   if page.locator("#contextMenu").is_visible():
    break
  assert page.locator('#contextMenu [data-context-action="editGenerator"]').is_hidden()
  assert not errors,errors
  browser.close()
 print("OK generator right-click edit, cancel, undo/redo, duplicate, project save/reopen and primitive protection")
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except Exception:server.kill()
