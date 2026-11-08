"""Public storefront browser checks: non-destructive GET and local UI interactions only."""
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE = os.getenv("FJORD_TEST_BASE", "https://fjord-render-apercu-20261104.onrender.com").rstrip("/")
OUT = Path(os.getenv("FJORD_TEST_OUTPUT", "/tmp/fjord-browser-check"))
OUT.mkdir(parents=True, exist_ok=True)

PAGES = {
    "home": "/",
    "gallery": "/galerie",
    "quote": "/soumission",
    "contact": "/contact",
    "tracking": "/suivi",
    "live_tracking": "/voir-mon-impression",
    "atelier": "/atelier-3d",
    "support": "/assistance",
    "privacy": "/politique-confidentialite",
    "terms": "/conditions-utilisation",
}

async def check_viewport(browser, label, width, height):
    context=await browser.new_context(viewport={"width":width,"height":height},
                                      device_scale_factor=1,
                                      locale="fr-CA",
                                      reduced_motion="reduce",
                                      ignore_https_errors=False)
    page=await context.new_page()
    results = []
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)[:250]))
    for name, path in PAGES.items():
        url = BASE + path
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(350)
            status = response.status if response else 0
            title = await page.title()
            h1 = (await page.locator("h1").all_text_contents())[:2]
            if name == "atelier":
                await page.wait_for_timeout(1500)
            main = await page.evaluate("""() => ({
              viewport:document.documentElement.clientWidth,
              pageWidth:document.documentElement.scrollWidth,
              h:document.documentElement.scrollHeight,
              canonical:document.querySelector('link[rel=canonical]')?.href||'',
              robots:document.querySelector('meta[name=robots]')?.content||'',
              siteCSS:!!document.querySelector('link[href*="fjord_sitewide.css"]')
            })""")
            result={"page":name,"status":status,"title":title,"headings":h1,
                    "overflow":max(0,main["pageWidth"]-main["viewport"])}
            if status != 200:
                raise AssertionError(f"{name}: unexpected HTTP {status}")
            if name != "atelier" and not main["siteCSS"]:
                raise AssertionError(f"{name}: website styling did not load")
            if name == "quote":
                fields = await page.locator('form.fjm-quote-form [name]').evaluate_all(
                    "(nodes) => nodes.map(x => x.name)"
                )
                for key in ("name","email","description","quantity","color","material","model"):
                    if key not in fields: raise AssertionError(f"Quote missing {key}")
                if await page.locator("form.fjm-quote-form button[type=submit]").is_disabled():
                    result["quote_mode"]="preview-disabled"
                else:
                    result["quote_mode"]="available"
                await page.locator('input[name=quantity]').fill("2")
                await page.locator('select[name=color]').select_option(label="Bleu")
                result["quantity_ui"]=await page.locator('input[name=quantity]').input_value()
            if name == "gallery":
                count = await page.locator(".fjm-project").count()
                result["published_cards"]=count
                if count:
                    first=page.locator(".fjm-project").first
                    title_text=(await first.locator("strong").inner_text()).strip()
                    if title_text:
                        await page.locator("#fjmGallerySearch").fill(title_text)
                        result["search_cards"]=await page.locator(".fjm-project:visible").count()
                        if result["search_cards"] < 1:
                            raise AssertionError("Gallery search doesn't find first title")
                        await page.locator("#fjmGallerySearch").fill("")
            if name=="home":
                cta=page.locator('.fjm-hero a[href="/soumission"]').first
                if not await cta.is_visible():raise AssertionError("Main quote CTA not visible")
                result["cta_visible"]=True
            if name=="atelier":
                result["editor_canvas"]=await page.locator("canvas").count()
                if result["editor_canvas"] == 0:
                    raise AssertionError("3D Studio canvas missing")
            if name in ("home","quote","gallery","contact","tracking"):
                await page.screenshot(path=str(OUT/f"{label}-{name}.png"),full_page=False,
                                      animations="disabled",timeout=20000)
            results.append(result)
            print("PASS",label,json.dumps(result,ensure_ascii=False))
        except Exception as exc:
            print("FAIL",label,name,str(exc)[:450])
            await context.close()
            raise
    if errors:
        # Third-party modules can log nonfatal errors; display for triage.
        print("BROWSER_WARNINGS",label,json.dumps(errors[:25],ensure_ascii=False))
    await context.close()
    return results

async def main():
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        try:
            desktop=await check_viewport(browser,"desktop",1440,900)
            mobile=await check_viewport(browser,"mobile",390,844)
            print("ALL_PUBLIC_BROWSER_CHECKS_PASSED",len(desktop)+len(mobile))
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
