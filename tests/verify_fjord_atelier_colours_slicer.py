"""Public Atelier 3D: verify colours, 3MF export and real generic layer preview.

No printer commands, customer data, payments or admin credentials are used.
"""
import asyncio
import os
import zipfile
from pathlib import Path
from playwright.async_api import async_playwright

BASE=os.environ.get("FJORD_TEST_BASE","https://fjord-render-apercu-20261104.onrender.com")
OUT=Path(os.environ.get("FJORD_ATELIER_OUTPUT","/tmp/fjord-atelier-tests"));OUT.mkdir(parents=True,exist_ok=True)

async def run_check(browser,label,width,height):
 context=await browser.new_context(viewport={"width":width,"height":height},accept_downloads=True,
     locale="fr-CA",reduced_motion="reduce")
 page=await context.new_page()
 errors=[]
 page.on("pageerror",lambda e:errors.append(str(e)[:300]))
 try:
  response=await page.goto(BASE+"/atelier-3d",wait_until="domcontentloaded",timeout=45000)
  assert response.status==200,response.status
  await page.wait_for_function("window.__fjordEditorStarted === true",timeout=50000)
  await page.evaluate("document.querySelector('[data-shape=cube]').click()")
  await page.wait_for_timeout(250)
  selection=await page.locator("#sceneList").inner_text()
  assert "cube" in selection.lower(),"Cube did not enter the plate: "+selection[:250]
  print("PASS",label,"cube added")
  # Open the existing painting module and select the red colour.
  await page.evaluate("window.fjordPaint.open()")
  await page.locator('#fjordPaintPanel').wait_for(state="visible",timeout=10000)
  await page.locator('#fjordPaintPresets [data-fjord-color="#F04444"]').click()
  assert (await page.locator("#fjordPaintColor").input_value()).upper()=="#F04444"
  await page.locator("#fjordPaintWhole").click()
  status=await page.locator("#fjordPaintStatus").inner_text()
  assert "✓" in status, "Whole object colour failed: "+status
  print("PASS",label,"whole part colour applied",status[:110])
  async with page.expect_download(timeout=25000) as transfer:
   await page.evaluate("document.getElementById('exportColor3MF').click()")
  file=await transfer.value
  target=OUT/(label+"-color.3mf")
  await file.save_as(target)
  with zipfile.ZipFile(target) as zin:
   model=zin.read("3D/3dmodel.model").decode("utf-8")
   assert "#F04444" in model,"Exported 3MF did not retain chosen red colour"
   assert "<m:colorgroup" in model,"3MF material colours absent"
  print("PASS",label,"3MF export preserved actual selected colour")
  await page.locator('#theme').select_option("light")
  theme=await page.evaluate("getComputedStyle(document.body).backgroundColor")
  assert "light" in (await page.locator("body").get_attribute("class") or ""),"Light theme not applied"
  await page.screenshot(path=str(OUT/(label+"-paint-light.png")),animations="disabled")
  await page.evaluate("window.fjordPaint.close()")
  # Open generic PrusaSlicer preview. This is NOT an X2D print job.
  await page.evaluate("document.getElementById('sliceTop').click()")
  await page.locator("#sliceFloat").wait_for(state="visible",timeout=12000)
  try:
   await page.wait_for_function("""() => {
      const text=document.getElementById("sliceEngineSummary")?.textContent||"";
      return text.includes("couches calculées")||text.includes("Tranchage indisponible");
   }""",timeout=120000)
  except Exception:
   raise AssertionError("Tranchage sans retour : "+(await page.locator("#sliceEngineSummary").inner_text()))
  summary=await page.locator("#sliceEngineSummary").inner_text()
  assert "couches calculées" in summary,"Real preview slice failed: "+summary
  layers=await page.locator("#sliceEngineState").inner_text()
  assert "PrusaSlicer" in layers
  print("PASS",label,"actual generic G-code preview",summary[:150])
  await page.screenshot(path=str(OUT/(label+"-slice-light.png")),animations="disabled")
  assert not errors,"Browser runtime errors: "+str(errors[:3])
 finally:
  await context.close()

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  try:
   await run_check(browser,"desktop",1440,900)
   await run_check(browser,"mobile",390,844)
   print("ALL_ATELIER_COLOUR_AND_SLICER_TESTS_PASSED")
  finally:
   await browser.close()

if __name__=="__main__":asyncio.run(main())
