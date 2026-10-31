import pathlib
import re
import shutil
import subprocess
import unittest

from private_fjord import admin_studio, public_studio

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AtelierImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "atelier3d.html").read_text(encoding="utf-8")

    def test_file_picker_supports_stl_3mf_json(self):
        self.assertIn('accept=".stl,.3mf,.json" multiple', self.html)
        self.assertIn("async function importModelFile(file, displayName)", self.html)
        self.assertIn("parse3MFProduction(buffer,title)", self.html)

    def test_private_library_not_exposed_in_public_editor(self):
        public = public_studio(self.html)
        private = admin_studio(self.html, "test-token")
        self.assertNotIn("fjordPrivateImport", public)
        self.assertIn("fjordPrivateImport", private)
        self.assertIn("/admin/modeles/api/liste", private)
        self.assertIn("fjordImportSaved", private)

    def test_fast3d_menu_and_drawer_directives_are_preserved(self):
        for menu in ("Fichier", "Exporter", "Média", "Affichage", "Options", "Aide"):
            self.assertIn("<summary>"+menu+"</summary>", self.html)
        self.assertIn("event.pointerType==='mouse'&&mouse.matches", self.html)
        self.assertIn("menu.addEventListener('pointerleave'", self.html)
        self.assertIn("window.fjordToggleCategoryDrawer", self.html)
        self.assertIn("id=\"fjordDrawerLeft\"", self.html)
        self.assertIn("id=\"fjordDrawerRight\"", self.html)
        self.assertIn("data-fjord-panel=\"generators\"", self.html)
        self.assertIn('src="/identite/logo"', self.html)
        self.assertIn("fjord-plate-mark.svg", self.html)
        self.assertIn("observeToolPanels.observe", self.html)
        # Preserve the current 3D toolbox while refining its display.
        for element in ('id="contextMenu"', 'id="generatorKind"', 'id="cutFloat"',
                        'id="fjordBedTabs"', 'id="slicePreview"'):
            self.assertIn(element, self.html)

    def test_scale_is_not_camera_zoom_and_merge_preserves_parts(self):
        self.assertIn('data-context-action="growSelected"',self.html)
        self.assertIn('rescaleSelected(1.1)',self.html)
        self.assertIn('data-context-action="scaleCustom"',self.html)
        self.assertNotIn('data-context-action="zoomSelected"',self.html)
        self.assertIn('Ctrl + clic',self.html)
        self.assertIn('multiSelectionPointer',self.html)
        self.assertIn('selectedSet=new Set()',self.html)
        self.assertIn('items=models.filter(m=>selectedSet.has(m))',self.html)
        self.assertIn("merged.userData.mergedParts=parts",self.html)
        self.assertIn('fjordSplitMerged()',self.html)
        self.assertIn("m.userData.mergedParts=parts",self.html)
        self.assertIn('colors.push(color.r,color.g,color.b)',self.html)

    @unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
    def test_classic_script_syntax(self):
        scripts = re.findall(r'<script>(.*?)</script>', self.html, re.S)
        self.assertGreaterEqual(len(scripts), 5)
        for index, script in enumerate(scripts):
            result = subprocess.run(["node", "--check"], input=script,
                                    encoding="utf-8", capture_output=True,
                                    timeout=15, check=False)
            self.assertEqual(result.returncode, 0, f"script {index}: {result.stderr}")

    @unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
    def test_module_javascript_syntax_public_and_admin(self):
        for name, page in [("public", public_studio(self.html)),
                           ("admin", admin_studio(self.html, "test-token"))]:
            scripts = re.findall(r'<script type="module">(.*?)</script>', page, re.S)
            self.assertEqual(len(scripts), 1, name)
            result = subprocess.run(
                ["node", "--input-type=module", "--check"],
                input=scripts[0], encoding="utf-8",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=25, check=False)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
