"""Catch missing application modules in the Railway Docker image before deployment."""
import pathlib
import re
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]


class DockerBundleTest(unittest.TestCase):
    def test_all_root_python_modules_are_included(self):
        lines=(ROOT/"Dockerfile").read_text(encoding="utf-8").splitlines()
        copied=set()
        for line in lines:
            line=line.strip()
            if not line.startswith("COPY "):
                continue
            parts=line.split()[1:-1]
            for part in parts:
                if part == "*.py":
                    copied.update(p.name for p in ROOT.glob("*.py"))
                elif part.endswith(".py"):
                    copied.add(pathlib.Path(part).name)
        expected={p.name for p in ROOT.glob("*.py")}
        self.assertTrue(expected.issubset(copied),
                        "Python modules omitted from Dockerfile: "+", ".join(sorted(expected-copied)))
        self.assertIn("live_print.py",copied)


if __name__=="__main__":
    unittest.main()
