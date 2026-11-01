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
  auto=page.evaluate("""() => {
    const makeGeometry=coords=>{
      const a={count:coords.length/3,getX:i=>coords[3*i],getY:i=>coords[3*i+1],
        getZ:i=>coords[3*i+2]};
      return {index:null,getAttribute:name=>name==='position'?a:null};
    };
    function disc(radius,steps,sideways=false){
      const coords=[];
      const push=(x,y,z)=>coords.push(x,y,z);
      for(let i=0;i<steps;i++){
        const a=i*2*Math.PI/steps,b=(i+1)*2*Math.PI/steps;
        if(sideways){
          push(0,2,0);push(radius*Math.cos(a),2,radius*Math.sin(a));
          push(radius*Math.cos(b),2,radius*Math.sin(b));
        }else{
          push(0,0,0);push(radius*Math.cos(a),radius*Math.sin(a),0);
          push(radius*Math.cos(b),radius*Math.sin(b),0);
        }
      }
      return makeGeometry(coords);
    }
    function ring(inner,outer,steps){
      const a=[];
      const push=(r,t)=>a.push(r*Math.cos(t),r*Math.sin(t),0);
      for(let i=0;i<steps;i++){
        const x=i*2*Math.PI/steps,y=(i+1)*2*Math.PI/steps;
        push(inner,x);push(outer,x);push(outer,y);
        push(inner,x);push(outer,y);push(inner,y);
      }
      return makeGeometry(a);
    }
    const flat=disc(10,64);
    const inner=window.fjordDetectCircularEdge(ring(10,20,64),0,[10,0,0]);
    const outer=window.fjordDetectCircularEdge(ring(10,20,64),0,[20,0,0]);
    const turned=window.fjordDetectCircularEdge(disc(10,64,true),0,[10,2,0]);
    return {
      disk:window.fjordDetectCircularEdge(flat,0,[10,0,0]),
      far:window.fjordDetectCircularEdge(flat,0,[0,0,0]),
      inner,outer,turned,
      invalidFace:window.fjordDetectCircularEdge(flat,-1,[10,0,0]),
      noMesh:window.fjordDetectCircularEdge(null,0,[10,0,0])
    };
  }""")
  assert abs(auto["disk"]["radius"]-10)<.01,auto
  assert auto["disk"]["method"]=="planar-contour",auto
  assert abs(auto["inner"]["diameter"]-20)<.01,auto
  assert abs(auto["outer"]["diameter"]-40)<.01,auto
  assert abs(auto["turned"]["radius"]-10)<.01,auto
  assert auto["far"] is None and auto["invalidFace"] is None and auto["noMesh"] is None,auto
  assert page.locator("#fjordMeasureMode").count()==1
  assert page.locator("#fjordMeasureCircleQuick").count()==1
  assert "3 points" in page.locator('#fjordMeasureMode option[value="circle"]').inner_text()
  assert "1 clic" in page.locator('#fjordMeasureMode option[value="auto"]').inner_text()
  page.locator("#fjordMeasureCircleQuick").evaluate("el=>el.click()")
  state=page.evaluate("window.fjordMeasureDebug()")
  assert state["active"] and state["mode"]=="auto" and state["points"]==0,state
  assert "bord" in page.locator("#measureHint").inner_text()
  page.locator("#fjordMeasureMode").select_option("distance")
  state=page.evaluate("window.fjordMeasureDebug()")
  assert state["active"] and state["mode"]=="distance",state
  page.locator("#fjordMeasureClear").evaluate("el=>el.click()")
  assert page.locator("#fjordMeasureResults").is_hidden()
  page.locator("#measure").evaluate("el=>el.click()")
  assert not page.evaluate("window.fjordMeasureDebug().active")
  assert not errors,errors
  browser.close()
 print("OK: Bambu-style one-click circle contours, hole selection, 3D geometry, fallback and UI")
finally:
 server.terminate()
 try: server.wait(timeout=5)
 except Exception:server.kill()
