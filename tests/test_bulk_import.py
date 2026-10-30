"""Regression tests for bulk STL / 3MF import into the private library."""
import hashlib
import io
import unittest
from flask import Flask, render_template_string
from private_fjord import register_private_fjord


class ModelDB:
    records = []
    next_id = 1
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def execute(self, sql, params=()):
        self.sql, self.params = sql, params
        return self
    def fetchall(self):
        return []
    def fetchone(self):
        if "SELECT id FROM private_models" in self.sql:
            if "content_sha256=%s" in self.sql:
                for row in self.records:
                    if row["sha"] == self.params[0]:
                        return {"id": row["id"]}
            elif "filedata=%s" in self.sql:
                for row in self.records:
                    if row["sha"] is None and len(row["blob"]) == self.params[0] and row["blob"] == self.params[1]:
                        return {"id": row["id"]}
            return None
        if "INSERT INTO private_models" in self.sql:
            model = {"id": self.next_id, "name": self.params[0],
                     "filename": self.params[1], "blob": self.params[2],
                     "sha": self.params[5], "preview": self.params[3]}
            self.records.append(model)
            self.next_id += 1
            return {"id": model["id"]}
        return None


class BulkImportTests(unittest.TestCase):
    def setUp(self):
        ModelDB.records=[]
        ModelDB.next_id=1
        self.app=Flask(__name__)
        self.app.secret_key="private-test"
        register_private_fjord(
            self.app, ModelDB, lambda fn:fn, lambda:None,
            lambda:'<input type="hidden" name="csrf" value="token">',
            lambda:"token",
            lambda title,body,**kwargs:render_template_string(body,**kwargs))
        self.client=self.app.test_client()

    def upload(self, name, data, skip=True):
        fields={"csrf":"token", "name":name.rsplit(".",1)[0],
                "model":(io.BytesIO(data),name)}
        if skip:fields["skip_duplicates"]="yes"
        return self.client.post("/admin/modeles/api/save",data=fields)

    def test_bulk_picker_is_present_and_private(self):
        response=self.client.get("/admin/modeles")
        self.assertEqual(response.status_code,200)
        html=response.data.decode("utf-8")
        self.assertIn('id="fjordBulkFiles"',html)
        self.assertIn('id="fjordBulkFolder"',html)
        self.assertIn('webkitdirectory',html)
        self.assertIn('multiple',html)
        self.assertIn('id="fjordBulkStart"',html)
        self.assertIn('id="fjordBulkProgress"',html)
        self.assertIn('skip_duplicates',html)
        self.assertIn('/admin/modeles/api/save',html)

    def test_multiple_direct_uploads_preserve_original_bytes_and_skip_duplicates(self):
        first=b"solid first\\nendsolid first\\n"
        second=b"solid second\\nendsolid second\\n"
        x=self.upload("first.stl",first)
        self.assertEqual(x.status_code,200)
        self.assertEqual(x.json,{"ok":True,"id":1,"duplicate":False})
        y=self.upload("second.STL",second)
        self.assertEqual(y.status_code,200)
        self.assertEqual(y.json,{"ok":True,"id":2,"duplicate":False})
        self.assertEqual([r["blob"] for r in ModelDB.records],[first,second])
        self.assertEqual(ModelDB.records[0]["sha"],hashlib.sha256(first).hexdigest())
        duplicate=self.upload("first.stl",first)
        self.assertEqual(duplicate.json,{"ok":True,"id":1,"duplicate":True})
        self.assertEqual(len(ModelDB.records),2)

    def test_legacy_model_is_recognized_as_duplicate(self):
        old=b"solid old\\nendsolid old"
        ModelDB.records=[{"id":77,"name":"Ancien","filename":"old.stl","blob":old,"sha":None}]
        ModelDB.next_id=78
        r=self.upload("old.stl",old)
        self.assertEqual(r.json,{"ok":True,"id":77,"duplicate":True})
        self.assertEqual(len(ModelDB.records),1)

    def test_import_may_explicitly_allow_another_copy(self):
        data=b"solid another\\nendsolid another"
        self.assertEqual(self.upload("a.stl",data).json["id"],1)
        result=self.upload("b.stl",data,skip=False)
        self.assertEqual(result.status_code,200)
        self.assertFalse(result.json["duplicate"])
        self.assertEqual(len(ModelDB.records),2)

    def test_invalid_extension_rejected(self):
        r=self.upload("script.exe",b"solid anything")
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(ModelDB.records),0)


if __name__=="__main__":
    unittest.main()
