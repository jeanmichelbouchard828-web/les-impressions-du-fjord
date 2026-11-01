"""Verify 3D circumcircle math and the Atelier's measurement mode controls."""
import pathlib
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=pathlib.Path(__file__).resolve().parents[1]
PORT=8809
server=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],
 cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(50):
  try:
   urllib.request.urlopen(f"http://127.0.0.1:{PORT}/atelier3d.html", timeout=1)
   break
  except Exception:time.sleep(.2)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=["--enable-webgl","--use-gl=angle",
   "--use-angle=swiftshader","--disable-dev-shm-usage","--no-sandbox"])
  page=browser.new_page(viewport={"width":1366,"height":900})
  errors=[]
  page.on("pageerror",lambda err:errors.append(str(err)))
  page.route("**/api/atelier/filaments",lambda route:route.fulfill(status=200,
   content_type="application/json",body='{"connected":false,"available":false,"sources":[]}'))
  page.goto(f"http://127.0.0.1:{PORT}/atelier3d.html",wait_until="domcontentloaded")
  page.wait_for_function("window.__fjordEditorStarted===true",timeout=60000)
  check=page.evaluate("""() => {
    let a=window.fjordFitCircle3D([10,0,0],[0,10,0],[-10,0,0]);
    let b=window.fjordFitCircle3D([10,1,3],[0,11,3],[-10,1,3]);
    let bad=window.fjordFitCircle3D([0,0,0],[5,0,0],[10,0,0]);
    let almost=window.fjordFitCircle3D([0,0,0],[5,0,0],[10,0.01,0]);
    let skew=window.fjordFitCircle3D([0,0,0],[4,0,0],[0,0,4]);
    return {a,b,bad,almost,skew};
  }""")
  assert abs(check["a"]["diameter"]-20)<.0001,check
  assert abs(check["b"]["center"][0])<.0001 and abs(check["b"]["center"][1]-1)<.0001
  assert abs(check["skew"]["radius"]-(2**.5*2))<.0001
  assert check["bad"] is None and check["almost"] is None,check
  assert page.locator("#fjordMeasureMode").count()==1
  assert page.locator("#fjordMeasureCircleQuick").count()==1
  assert "3 points" in page.locator('#fjordMeasureMode option[value="circle"]').inner_text()
  page.locator("#fjordMeasureCircleQuick").evaluate("el=>el.click()")
  state=page.evaluate("window.fjordMeasureDebug()")
  assert state["active"] and state["mode"]=="circle" and state["points"]==0,state
  assert "3 points" in page.locator("#measureHint").inner_text()
  page.locator("#fjordMeasureMode").select_option("distance")
  state=page.evaluate("window.fjordMeasureDebug()")
  assert state["active"] and state["mode"]=="distance",state
  page.locator("#fjordMeasureClear").evaluate("el=>el.click()")
  assert page.locator("#fjordMeasureResults").is_hidden()
  page.locator("#measure").evaluate("el=>el.click()")
  assert not page.evaluate("window.fjordMeasureDebug().active")
  assert not errors,errors
  browser.close()
 print("OK: radius diameter geometry, degenerate guard, tool, reset and distance mode")
finally:
 server.terminate()
 try: server.wait(timeout=5)
 except Exception:server.kill()
