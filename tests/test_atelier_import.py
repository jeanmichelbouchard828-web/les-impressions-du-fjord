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
        self.assertIn("new Loader3MF().parse(buffer)", self.html)

    def test_private_library_not_exposed_in_public_editor(self):
        public = public_studio(self.html)
        private = admin_studio(self.html, "test-token")
        self.assertNotIn("fjordPrivateImport", public)
        self.assertIn("fjordPrivateImport", private)
        self.assertIn("/admin/modeles/api/liste", private)
        self.assertIn("fjordImportSaved", private)

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
