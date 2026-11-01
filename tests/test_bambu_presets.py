"""Safety and compatibility tests for Bambu Studio preset archiving."""
import io
import json
import unittest
import zipfile
from bambu_presets import parse_bambu_presets, PresetImportError

def zip_bundle(data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as z:
        for name,body in data.items():
            z.writestr(name,json.dumps(body).encode("utf8") if isinstance(body,dict) else body)
    return buffer.getvalue()

class BambuPresetTests(unittest.TestCase):
    def test_single_filament_json(self):
        raw=json.dumps({"name":"PETG CF noir","type":"filament","filament_flow_ratio":["0.96"],
                        "nozzle_temperature":["240"],"inherits":"Generic PETG"}).encode()
        profiles,skipped=parse_bambu_presets("petg.json",raw)
        self.assertEqual((len(profiles),skipped),(1,0))
        self.assertEqual(profiles[0]["category"],"Filament")
        self.assertEqual(json.loads(profiles[0]["settings"])["filament_flow_ratio"],["0.96"])
    def test_mixed_zip_types_and_non_preset_skip(self):
        archive=zip_bundle({
            "process/0.12 fine.json":{"name":"Fine","layer_height":["0.12"],"wall_loops":["3"]},
            "filament/blue.json":{"name":"Blue PLA","nozzle_temperature":["215"]},
            "printer/x2d.json":{"name":"X2D profile","nozzle_diameter":["0.4"]},
            "other/manifest.json":{"metadata":"none"},
        })
        profiles,skipped=parse_bambu_presets("complete.bbscfg",archive)
        self.assertEqual(len(profiles),3)
        self.assertEqual(skipped,1)
        self.assertEqual({x["category"] for x in profiles},{"Filament","Impression","Imprimante"})
    def test_filament_bundle(self):
        data=zip_bundle({"filament/one.json":{"name":"TPU","filament_type":["TPU"]}})
        self.assertEqual(parse_bambu_presets("set.bbsflmt",data)[0][0]["category"],"Filament")
    def test_dedup_in_one_bundle(self):
        data=zip_bundle({"filament/a.json":{"name":"A","filament_type":["PLA"]},
                         "filament/b.json":{"name":"A","filament_type":["PLA"]}})
        self.assertEqual(len(parse_bambu_presets("profile.zip",data)[0]),1)
    def test_large_library_bundle_is_accepted(self):
        # Users may upload a combined archive of hundreds of X2D presets.
        entries={
            f"process/custom-{i}.json":{
                "name":f"X2D process {i}",
                "layer_height":[str(0.08+i/100000)],
                "wall_loops":["3"]}
            for i in range(620)
        }
        profiles,skipped=parse_bambu_presets("tous-mes-profils.zip",zip_bundle(entries))
        self.assertEqual(len(profiles),620)
        self.assertEqual(skipped,0)
        self.assertTrue(all(p["category"]=="Impression" for p in profiles))
    def test_invalid_files_rejected(self):
        for name,payload in [
            ("bad.exe",b"script"),("bad.bbscfg",b"not zip"),("bad.json",b"{broken}"),
            ("secret.json",b'{"password":"secret"}'),("empty.zip",zip_bundle({"readme.txt":"text"}))
        ]:
            with self.subTest(filename=name), self.assertRaises(PresetImportError):
                parse_bambu_presets(name,payload)
    def test_zip_bomb_limit(self):
        # The compressed payload is tiny, the advertised uncompressed total huge.
        raw=zip_bundle({"filament/huge.json":" " * (19*1024*1024)})
        with self.assertRaises(PresetImportError):
            parse_bambu_presets("profiles.zip",raw)
    def test_path_traversal_rejected(self):
        raw=zip_bundle({"../filament/wrong.json":{"name":"Bad","filament_type":["PLA"]}})
        with self.assertRaises(PresetImportError):
            parse_bambu_presets("profiles.zip",raw)
    def test_file_type_requires_identifiable_preset(self):
        with self.assertRaises(PresetImportError):
            parse_bambu_presets("anything.json",json.dumps({"name":"Not a filament"}).encode())

if __name__=="__main__":
    unittest.main()
