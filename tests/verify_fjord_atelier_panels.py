"""Browser checks for separate Fjord Studio side panels without printer access."""
import asyncio
import os
from playwright.async_api import async_playwright

BASE=os.environ.get("FJORD_TEST_BASE","https://fjord-render-apercu-20261104.onrender.com").rstrip("/")

async def desktop(browser):
    context=await browser.new_context(viewport={"width":1440,"height":900},locale="fr-CA",reduced_motion="reduce")
    page=await context.new_page()
    try:
        response=await page.goto(BASE+"/atelier-3d",wait_until="domcontentloaded",timeout=45000)
        assert response.status==200
        await page.wait_for_function("window.__fjordEditorStarted===true",timeout=55000)
        nav=page.locator("#toolsPanel .fjord-workspace-nav")
        async def pick(name):
            await nav.locator('[data-fjord-panel="'+name+'"]').click()
        await pick("projects")
        assert await page.locator('#toolsPanel [data-tool-panel="projects"]').is_visible()
        assert not await page.locator('#toolsPanel [data-tool-panel="parts"]').is_visible()
        assert await page.locator('[data-fjord-project-action="save"]').is_visible()
        print("PASS desktop independent Projets actions")
        await pick("parts")
        assert await page.locator('#toolsPanel [data-tool-panel="parts"] #sceneList').is_visible()
        assert not await page.locator('#toolsPanel [data-tool-panel="projects"]').is_visible()
        print("PASS desktop independent Pièces")
        await pick("measure")
        assert await page.locator('#toolsPanel [data-tool-panel="measure"] #fjordMeasureWorkspace').is_visible()
        assert not await page.locator('#toolsPanel [data-tool-panel="edit"] #move').is_visible()
        assert await page.locator('#toolsPanel [data-tool-panel="measure"] #measure').count()==1
        print("PASS desktop dedicated Mesure controls")
        await page.evaluate("document.getElementById('fjordWorkspace').classList.add('fjord-hide-right')")
        await pick("properties")
        assert await page.locator("#propertiesPanel #name").is_visible()
        assert "fjord-hide-right" not in await page.locator("#fjordWorkspace").get_attribute("class")
        assert "fjord-properties-focused" in await page.locator("#fjordWorkspace").get_attribute("class")
        print("PASS desktop Propriétés opens right drawer")
        await pick("profiles")
        assert await page.locator('#toolsPanel [data-tool-panel="profiles"] .fjord-profile-admin-link').is_visible()
        assert not await page.locator('[data-tool-panel="projects"]').is_visible()
        print("PASS desktop X2D configuration tab")
    finally:
        await context.close()

async def mobile(browser):
    context=await browser.new_context(viewport={"width":390,"height":844},locale="fr-CA",is_mobile=True,has_touch=True)
    page=await context.new_page()
    try:
        response=await page.goto(BASE+"/atelier-3d",wait_until="domcontentloaded",timeout=45000)
        assert response.status==200
        await page.wait_for_function("window.__fjordEditorStarted===true",timeout=55000)
        async def open_menu(name,selector):
            await page.locator('#mobileIconBar [data-open-tools="'+name+'"]').click()
            assert await page.locator("#mobileMenuDrawer").is_visible()
            assert await page.locator("#mobileMenuContent "+selector).is_visible()
            await page.locator("#mobileMenuClose").click()
        await open_menu("projects",'[data-tool-panel="projects"] [data-fjord-project-action="save"]')
        await open_menu("parts",'[data-tool-panel="parts"] #sceneList')
        await open_menu("measure",'[data-tool-panel="measure"] #fjordMeasureMode')
        await open_menu("properties",'[data-tool-panel="properties"] #name')
        await open_menu("profiles",'[data-tool-panel="profiles"] .fjord-profile-admin-link')
        print("PASS mobile distinct projects, parts, measurement, properties and X2D tabs")
    finally:
        await context.close()

async def main():
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        try:
            await desktop(browser)
            await mobile(browser)
            print("ALL_ATELIER_SIDEBAR_TESTS_PASSED")
        finally:
            await browser.close()

if __name__=="__main__":
    asyncio.run(main())
