"""Private model associations in public gallery and attributed inspiration slideshow.

All writes go ONLY to the disposable CI PostgreSQL (never production).
No printer, user order, payment provider, or external image request is made.
"""
import hashlib
import io
import os
import re
import sys
import zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
from urllib.parse import urlsplit
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
parsed=urlsplit(os.environ.get("DATABASE_URL",""))
if parsed.hostname not in ("127.0.0.1","localhost") or parsed.path!="/fjord_ci_test":
    raise RuntimeError("Safety guard: only local, disposable fjord_ci_test allowed")
from app import app,db,FJORD_INSPIRATIONS

BASE="https://localhost"

def get_csrf(body):
    token=re.search(r'<input[^>]+name="csrf"[^>]+value="([^"]+)"',body)
    if not token:raise AssertionError("CSRF token not rendered")
    return token.group(1)

def jpeg(rgb=(50,100,150)):
    im=Image.new("RGB",(140,110),rgb)
    raw=io.BytesIO()
    im.save(raw,format="JPEG",quality=84)
    return raw.getvalue()

def stl():
    # Binary STL header and a single real triangle.
    import struct
    return b"Fjord gallery test"+bytes(80-18)+struct.pack("<I",1)+(
        struct.pack("<12fH",0,0,1, 0,0,0, 30,0,0, 0,30,0, 0))

def zip3mf():
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("3D/3dmodel.model",'<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"/>')
    return data.getvalue()

class GalleryModelTests(TestCase):
    def setUp(self):
        self.client=app.test_client()

    def get(self,path):
        return self.client.get(path,base_url=BASE)

    def post(self,path,data):
        return self.client.post(path,data=data,base_url=BASE)

    def owner(self):
        token="fjord-ci-gallery-archive-login"
        digest=hashlib.sha256(token.encode()).hexdigest()
        with db() as c:
            c.execute("""INSERT INTO sessions(tokenhash,expires) VALUES(%s,%s)
                      ON CONFLICT(tokenhash) DO UPDATE SET expires=EXCLUDED.expires""",
                      (digest,datetime.now(timezone.utc)+timedelta(hours=1)))
        with self.client.session_transaction() as sess:
            sess["admin_token"]=token

    def quote(self,data):
        csrf=get_csrf(self.get("/soumission").get_data(as_text=True))
        default={"csrf":csrf,"name":"Test image client","email":"fjord-gallery-ci@example.invalid",
                 "description":"Je veux une pièce identique à celle de la photo.",
                 "quantity":"1","color":"Noir","material":"PETG"}
        return self.post("/soumission",{**default,**data})

    def test_each_gallery_photo_attaches_its_own_model_and_reference(self):
        model1=stl()
        model2=zip3mf()
        with db() as c:
            gallery=c.execute("""INSERT INTO gallery(title,category,description,
                 model_filename,model_data) VALUES(%s,%s,%s,%s,%s) RETURNING id""",
                 ("Galerie CI","Supports","Trois photos de référence","parent.3mf",model2)).fetchone()["id"]
            first=c.execute("""INSERT INTO gallery_photos(gallery_id,photo,mime,model_filename,model_data)
                       VALUES(%s,%s,%s,%s,%s) RETURNING id""",
                 (gallery,jpeg(),"image/jpeg","piece-unique.stl",model1)).fetchone()["id"]
            second=c.execute("""INSERT INTO gallery_photos(gallery_id,photo,mime)
                       VALUES(%s,%s,%s) RETURNING id""",
                 (gallery,jpeg((100,120,20)),"image/jpeg")).fetchone()["id"]
        page=self.get(f"/galerie/{gallery}")
        self.assertEqual(page.status_code,200)
        self.assertIn(f"/soumission?galerie={gallery}&photo={first}",
                      [__import__('html').unescape(link) for link in
                       re.findall(r'href="([^"]+)"',page.get_data(as_text=True))])
        self.assertIn(f"/soumission?galerie={gallery}&photo={second}",
                      [__import__('html').unescape(link) for link in
                       re.findall(r'href="([^"]+)"',page.get_data(as_text=True))])
        self.assertNotIn("piece-unique.stl",page.get_data(as_text=True))
        view=self.get(f"/soumission?galerie={gallery}&photo={first}")
        self.assertEqual(view.status_code,200)
        self.assertIn('name="gallery_photo_id"',view.get_data(as_text=True))
        response=self.quote({"gallery_id":str(gallery),"gallery_photo_id":str(first)})
        self.assertEqual(response.status_code,200,response.get_data(as_text=True)[:500])
        with db() as c:
            row=c.execute("""SELECT filename,filedata,reference_photo,reference_mime,description
                  FROM requests WHERE email=%s ORDER BY id DESC LIMIT 1""",
                  ("fjord-gallery-ci@example.invalid",)).fetchone()
        self.assertEqual(row["filename"],"piece-unique.stl")
        self.assertEqual(row["filedata"],model1)
        self.assertTrue(row["reference_photo"].startswith(bytes.fromhex("ffd8ff")))
        self.assertEqual(row["reference_mime"],"image/jpeg")
        self.assertIn(f"photo #{first}",row["description"])
        response=self.quote({"gallery_id":str(gallery),"gallery_photo_id":str(second),
                             "email":"fjord-gallery-second@example.invalid"})
        self.assertEqual(response.status_code,200)
        with db() as c:
            row2=c.execute("""SELECT filename,filedata FROM requests WHERE email=%s
                          ORDER BY id DESC LIMIT 1""",
                          ("fjord-gallery-second@example.invalid",)).fetchone()
        self.assertEqual(row2["filename"],"parent.3mf")
        self.assertEqual(row2["filedata"],model2)
        self.assertEqual(self.get(f"/admin/gallery/model/{gallery}?photo={first}").status_code,302)

    def test_customer_request_one_click_preparation_stays_private_and_non_printing(self):
        request_result=self.quote({"email":"fjord-quick-prep@example.invalid",
            "model":(io.BytesIO(stl()),"photo-linked.stl")})
        self.assertEqual(request_result.status_code,200)
        with db() as conn:
            record=conn.execute("SELECT id,filename,filedata FROM requests WHERE email=%s",
                                ("fjord-quick-prep@example.invalid",)).fetchone()
        self.assertEqual(record["filename"],"photo-linked.stl")
        path=f"/admin/demandes/model/{record['id']}"
        self.assertEqual(self.get(path).status_code,302)
        self.owner()
        file_response=self.get(path)
        self.assertEqual(file_response.status_code,200)
        self.assertEqual(file_response.data,stl())
        self.assertEqual(file_response.headers.get("X-Fjord-Model-Name"),"photo-linked.stl")
        self.assertIn("no-store",file_response.headers.get("Cache-Control",""))
        admin=self.get("/admin")
        self.assertIn(f"/admin/atelier-3d?demande={record['id']}",admin.get_data(as_text=True))
        atelier=self.get(f"/admin/atelier-3d?demande={record['id']}")
        self.assertEqual(atelier.status_code,200)
        self.assertIn("'/admin/demandes/model/'",atelier.get_data(as_text=True))

    def test_owner_can_assign_models_per_photo_and_open_in_atelier(self):
        self.owner()
        with db() as c:
            gid=c.execute("""INSERT INTO gallery(title,category,description)
                    VALUES('Galerie modèle test','Supports','Test du modèle')
                    RETURNING id""").fetchone()["id"]
            pid=c.execute("""INSERT INTO gallery_photos(gallery_id,photo,mime)
                       VALUES(%s,%s,'image/jpeg') RETURNING id""",
                       (gid,jpeg())).fetchone()["id"]
        view=self.get(f"/admin/edit/{gid}")
        self.assertEqual(view.status_code,200)
        self.assertIn(f"/admin/galerie/photo/{pid}/modele",view.get_data(as_text=True))
        result=self.post(f"/admin/galerie/photo/{pid}/modele",{
            "csrf":get_csrf(view.get_data(as_text=True)),
            "model":(io.BytesIO(stl()),"support.stl")})
        self.assertEqual(result.status_code,302)
        with db() as c:
            linked=c.execute("SELECT model_filename FROM gallery_photos WHERE id=%s",(pid,)).fetchone()
        self.assertEqual(linked["model_filename"],"support.stl")
        download=self.get(f"/admin/gallery/model/{gid}?photo={pid}")
        self.assertEqual(download.status_code,200)
        self.assertEqual(download.headers["X-Fjord-Model-Name"],"support.stl")
        self.assertEqual(download.headers["Cache-Control"],"no-store, private")
        self.assertEqual(download.data,stl())
        editor=self.get(f"/admin/atelier-3d?galerie={gid}&photo={pid}")
        self.assertEqual(editor.status_code,200)
        self.assertIn("fjordImportGalleryModelFile",editor.get_data(as_text=True))
        self.assertIn("'/admin/gallery/model/'",editor.get_data(as_text=True))

    def test_one_upload_links_named_3mf_to_correct_photo_and_library_file(self):
        self.owner()
        manual=stl()
        with db() as conn:
            conn.execute("""INSERT INTO private_models(name,filename,filedata)
                VALUES(%s,%s,%s)""",("Support manette","support_manette.stl",manual))
        page=self.get("/admin/new")
        self.assertEqual(page.status_code,200)
        self.assertIn('name="models"',page.get_data(as_text=True))
        body={
            "csrf":get_csrf(page.get_data(as_text=True)),
            "title":"Supports pour atelier",
            "category":"Accessoires",
            "description":"Support 3D avec les photos exactes",
            "photos":[
                (io.BytesIO(jpeg((20,30,100))),"Support manette photo 1.jpg"),
                (io.BytesIO(jpeg((120,30,70))),"boitier-axe-photo-2.jpg"),
                (io.BytesIO(jpeg((90,40,50))),"inconnu.jpg")
            ],
            "models":[(io.BytesIO(zip3mf()),"boitier_axe.3mf")]
        }
        response=self.post("/admin/new",body)
        self.assertEqual(response.status_code,302,response.get_data(as_text=True)[:350])
        gid=int(response.location.rsplit("/",1)[-1])
        with db() as conn:
            photos=conn.execute("""SELECT original_filename,model_filename,model_data
                       FROM gallery_photos WHERE gallery_id=%s ORDER BY id""",(gid,)).fetchall()
        self.assertEqual(len(photos),3)
        self.assertEqual(photos[0]["model_filename"],"support_manette.stl")
        self.assertEqual(photos[0]["model_data"],manual)
        self.assertEqual(photos[1]["model_filename"],"boitier_axe.3mf")
        self.assertEqual(photos[1]["model_data"],zip3mf())
        self.assertIsNone(photos[2]["model_data"])

    def test_auto_pair_existing_images_only_when_unique_filename(self):
        self.owner()
        with db() as conn:
            gid=conn.execute("""INSERT INTO gallery(title,category,description)
                VALUES('Auto test','Utilitaire','Double vérification') RETURNING id""").fetchone()["id"]
            pid=conn.execute("""INSERT INTO gallery_photos(gallery_id,photo,mime,original_filename)
                VALUES(%s,%s,'image/jpeg','unique-support_photo_1.jpg')
                RETURNING id""",(gid,jpeg())).fetchone()["id"]
            conn.execute("""INSERT INTO private_models(name,filename,filedata)
                VALUES('Unique support','unique-support.stl',%s)""",(stl(),))
        page=self.get(f"/admin/edit/{gid}")
        response=self.post(f"/admin/galerie/{gid}/associer-automatiquement",{
            "csrf":get_csrf(page.get_data(as_text=True))
        })
        self.assertEqual(response.status_code,302)
        with db() as conn:
            row=conn.execute("SELECT model_filename,model_data FROM gallery_photos WHERE id=%s",(pid,)).fetchone()
        self.assertEqual(row["model_filename"],"unique-support.stl")
        self.assertEqual(row["model_data"],stl())

    def test_invalid_cross_gallery_photo_is_refused(self):
        with db() as c:
            a=c.execute("""INSERT INTO gallery(title,category,description)
                 VALUES('Projet A','T','D') RETURNING id""").fetchone()["id"]
            b=c.execute("""INSERT INTO gallery(title,category,description)
                 VALUES('Projet B','T','D') RETURNING id""").fetchone()["id"]
            photo=c.execute("""INSERT INTO gallery_photos(gallery_id,photo,mime)
                 VALUES(%s,%s,'image/jpeg') RETURNING id""",(b,jpeg())).fetchone()["id"]
        self.assertEqual(self.get(f"/soumission?galerie={a}&photo={photo}").status_code,404)
        resp=self.quote({"gallery_id":str(a),"gallery_photo_id":str(photo)})
        self.assertEqual(resp.status_code,400)

    def test_inspiration_models_require_owner_rights_and_are_not_public(self):
        self.assertTrue(FJORD_INSPIRATIONS)
        idea=FJORD_INSPIRATIONS[0]
        self.assertEqual(self.get("/soumission?inspiration=0").status_code,200)
        self.assertIn("inspiration=0",self.get("/").get_data(as_text=True))
        self.assertEqual(self.get("/admin/inspirations/0/modele").status_code,302)
        self.owner()
        admin=self.get("/admin/inspirations")
        self.assertEqual(admin.status_code,200)
        self.assertIn("Je confirme avoir les droits",admin.get_data(as_text=True))
        no_rights=self.post("/admin/inspirations/0/modele",{
            "csrf":get_csrf(admin.get_data(as_text=True)),
            "model":(io.BytesIO(stl()),"gift.stl")})
        self.assertEqual(no_rights.status_code,400)
        admin=self.get("/admin/inspirations")
        upload=self.post("/admin/inspirations/0/modele",{
            "csrf":get_csrf(admin.get_data(as_text=True)),
            "rights_ok":"yes","model":(io.BytesIO(stl()),"gift.stl")})
        self.assertEqual(upload.status_code,302)
        stored=self.get("/admin/inspirations/0/modele")
        self.assertEqual(stored.status_code,200)
        self.assertEqual(stored.data,stl())
        self.assertIn("no-store",stored.headers["Cache-Control"])
        # No live Wikimedia network request in the test suite.
        with patch("app.fjord_inspiration_image_copy",return_value=jpeg()):
            response=self.quote({"inspiration_id":"0",
                "email":"fjord-inspiration-ci@example.invalid"})
        self.assertEqual(response.status_code,200)
        with db() as c:
            saved=c.execute("""SELECT filename,filedata,reference_photo,description
               FROM requests WHERE email=%s ORDER BY id DESC LIMIT 1""",
               ("fjord-inspiration-ci@example.invalid",)).fetchone()
        self.assertEqual(saved["filename"],"gift.stl")
        self.assertEqual(saved["filedata"],stl())
        self.assertTrue(saved["reference_photo"])
        self.assertIn(idea["source"],saved["description"])
        self.assertIn(idea["author"],saved["description"])
        self.assertIn("Modèle 3D associé : oui",saved["description"])
        atelier=self.get("/admin/atelier-3d?inspiration=0")
        self.assertEqual(atelier.status_code,200)
        self.assertIn("'/admin/inspirations/'",atelier.get_data(as_text=True))

if __name__=="__main__":
    main(verbosity=2)
