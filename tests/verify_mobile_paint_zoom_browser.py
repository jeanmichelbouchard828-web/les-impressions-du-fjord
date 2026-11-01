"""Actual mobile Chromium touch regression: pinch zoom, brush tap, palette fold."""
import pathlib
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8858
URL=f"http://127.0.0.1:{PORT}/atelier3d.html"
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
                        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

try:
 for _ in range(60):
  try:
   urllib.request.urlopen(URL,timeout=1)
   break
  except Exception:time.sleep(.2)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=[
      "--enable-webgl","--use-gl=angle","--use-angle=swiftshader",
      "--disable-dev-shm-usage","--no-sandbox"])
  page=browser.new_page(viewport={"width":390,"height":844},
      is_mobile=True,has_touch=True,device_scale_factor=1)
  errors=[]
  page.on("pageerror",lambda exc:errors.append(str(exc)))
  page.route("**/api/atelier/filaments",lambda route:route.fulfill(
     status=200,content_type="application/json",
     body='{"connected":false,"available":false,"sources":[]}'))
  page.goto(URL,wait_until="domcontentloaded")
  page.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
  page.locator('[data-shape="cube"]').evaluate("el=>el.click()")
  page.wait_for_function("document.querySelectorAll('#sceneList .scene-item').length===1")
  page.locator("#mobilePaintBtn").evaluate("el=>el.click()")
  assert page.locator("#fjordPaintPanel").is_visible(),"mobile paint panel should open"
  assert page.locator("#mobilePaintBtn").get_attribute("aria-pressed")=="true"
  assert page.locator("#fjordPaintMobileFold").is_visible()
  assert page.locator("#fjordPaintPanel").evaluate("el=>el.classList.contains('mobile-collapsed')")
  assert page.locator("#fjordPaintQuickOrbit").count()==0,"No floating rotation button"
  assert page.evaluate("window.fjordPaint.isActive()")
  assert page.evaluate("window.fjordPaint.cameraState()")
  page.locator("#fjordPaintMobileFold").click()  # Open tools, otherwise canvas stays large.
  page.locator('[data-fjord-paint-tool="triangle"]').evaluate("el=>el.click()")
  page.locator("#fjordPaintMobileFold").click()  # Fold tools again to paint.
  assert page.locator("#fjordPaintPanel").evaluate(
    "el=>el.classList.contains('mobile-collapsed')")
  assert page.locator("#fjordPaintMobileFold").get_attribute("aria-expanded")=="false"
  assert page.locator("#fjordPaintOrbit").is_hidden()
  # Fold does not close the paint tool.
  assert page.evaluate("window.fjordPaint.isActive()")

  box=page.locator("#stage canvas").bounding_box()
  assert box, "Canvas must be visible"
  x=box["x"]+box["width"]*.50
  y=box["y"]+box["height"]*.50
  assert page.evaluate("({x,y})=>document.elementFromPoint(x,y)?.tagName==='CANVAS'",
    {"x":x,"y":y}),"Collapsed painting palette must not cover canvas centre"

  cdp=page.context.new_cdp_session(page)
  def pinch(outward=True):
   def points(dx):
    return [{"id":1,"x":x-dx,"y":y},{"id":2,"x":x+dx,"y":y}]
   cdp.send("Input.dispatchTouchEvent",{"type":"touchStart","touchPoints":points(28)})
   for dx in [37,49,62,75,88,103] if outward else [90,75,60,50,40,27]:
    cdp.send("Input.dispatchTouchEvent",{"type":"touchMove","touchPoints":points(dx)})
    page.wait_for_timeout(35)
   cdp.send("Input.dispatchTouchEvent",{"type":"touchEnd","touchPoints":[]})
   page.wait_for_timeout(230)
  def dist():
   state=page.evaluate("window.fjordPaint.cameraState()")
   return sum((a-b)**2 for a,b in zip(state["position"],state["target"]))**.5

  before=dist()
  pinch()
  after=dist()
  assert after < before*.94,("Pinch spread must zoom in",before,after)
  assert "facette(s)" not in page.locator("#fjordPaintStatus").inner_text(),(
    "Pinching must not accidentally paint")
  # A one-finger tap paints a face while the paint tool remains enabled.
  page.touchscreen.tap(x,y)
  page.wait_for_function(
    "document.querySelector('#fjordPaintStatus').innerText.includes('facette(s)')",
    timeout=10000)
  assert page.evaluate("window.fjordPaint.isActive()"),"Painting must remain active after tap"
  # Two fingers traveling together orbit the view while staying in paint mode.
  # Pinch apart still zooms because paint mode uses DOLLY_ROTATE.
  painted=page.locator("#fjordPaintStatus").inner_text()
  assert page.evaluate("window.fjordPaint.isActive()")
  assert not page.evaluate("window.fjordPaint.isOrbiting()"),"No toggle needed"
  start=page.evaluate("window.fjordPaint.cameraState().position")
  def rotpoints(dx):
   return [{"id":3,"x":x-35+dx,"y":y-15+dx*.2},
           {"id":4,"x":x+35+dx,"y":y+15+dx*.2}]
  cdp.send("Input.dispatchTouchEvent",{"type":"touchStart","touchPoints":rotpoints(0)})
  for dx in [10,22,34,48,63,80]:
   cdp.send("Input.dispatchTouchEvent",{"type":"touchMove","touchPoints":rotpoints(dx)})
   page.wait_for_timeout(55)
  cdp.send("Input.dispatchTouchEvent",{"type":"touchEnd","touchPoints":[]})
  page.wait_for_timeout(280)
  end=page.evaluate("window.fjordPaint.cameraState().position")
  assert any(abs(a-b)>1 for a,b in zip(start,end)),("Two-finger orbit failed",start,end)
  assert page.locator("#fjordPaintStatus").inner_text()==painted,"Two-finger orbit should never paint"
  assert page.evaluate("window.fjordPaint.isActive()"),"Orbit keeps painting enabled"
  page.locator("#mobilePaintBtn").evaluate("el=>el.click()")
  assert not page.evaluate("window.fjordPaint.isActive()")
  # Standard touch zoom must remain available after leaving paint mode.
  page.locator("[data-camera-action='zoom-in']").evaluate("el=>el.click()")
  assert dist() < after*1.15, "Zoom controls still work outside paint"
  assert not errors,errors
  browser.close()
 print("PASS mobile paint, automatic fold, one-finger painting, two-finger rotate and pinch without buttons")
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except Exception:server.kill()
