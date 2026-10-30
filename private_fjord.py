"""Fonctions privées de Les Impressions du Fjord.
Les données de coûts et les fichiers ne sont jamais exposés par les routes publiques.
"""
import base64
import datetime
import io
import json
import math
import re

from flask import abort, flash, redirect, render_template_string, request, send_file, url_for
from werkzeug.utils import secure_filename

MATERIALS = ("PLA", "PETG", "ASA", "TPU", "Autre")
MODEL_EXT = (".stl", ".3mf", ".json")
MAX_MODEL = 8 * 1024 * 1024
MAX_IMAGE = 4 * 1024 * 1024

def _image(upload):
    if not upload or not upload.filename:
        return None
    data = upload.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        abort(413)
    if data.startswith(bytes.fromhex("ffd8ff")):
        return ("image/jpeg", data)
    if data.startswith(bytes.fromhex("89504e470d0a1a0a")):
        return ("image/png", data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ("image/webp", data)
    abort(400, "Image JPEG, PNG ou WebP requise.")

def _money(n):
    return "{:,.2f} $".format(n).replace(",", " ").replace(".", ",")

def _number(field, default=0, low=0, high=100000):
    raw = request.form.get(field, "")
    try:
        n = float(raw if raw != "" else default)
    except (ValueError, TypeError):
        abort(400, "Nombre invalide : " + field)
    if not math.isfinite(n) or not low <= n <= high:
        abort(400, "Valeur hors limites : " + field)
    return n

def admin_studio(html, csrf_token):
    """Le bouton d'enregistrement est ajouté UNIQUEMENT à l'atelier authentifié."""
    button = '<button type="button" class="primary" id="fjordPrivateSave">💾 Mes modèles (privé)</button><a href="/admin/modeles">📚 Bibliothèque</a>'
    html = html.replace('<button id="export" data-i18n="export">', button + '<button id="export" data-i18n="export">', 1)
    injection = r"""
// Sauvegarde serveur des modèles du propriétaire; cet extrait n'est jamais servi au public.
const privateSaveBtn=document.getElementById("fjordPrivateSave");
if(privateSaveBtn)privateSaveBtn.addEventListener("click", async ()=>{
 if(!models.length){alert("Ajoute une pièce avant de sauvegarder.");return;}
 const suggested=models.length===1?models[0].name:"Projet 3D du Fjord";
 const name=prompt("Nom du modèle à sauvegarder dans ta bibliothèque :",suggested);
 if(!name || !name.trim())return;
 privateSaveBtn.disabled=true;privateSaveBtn.textContent="Enregistrement…";
 try{
   const group=new THREE.Group();
   models.forEach(m=>{const clone=m.clone();clone.geometry=m.geometry;clone.material=m.material;group.add(clone)});
   const binary=new STLExporter().parse(group,{binary:true});
   const blob=new Blob([binary],{type:"application/octet-stream"});
   if(blob.size>8*1024*1024)throw new Error("Modèle de plus de 8 Mo.");
   // Capture le rendu actuel sans les aides de l'atelier.
   const oldGrid=grid.visible,oldBorder=border.visible,oldHelp=transform.getHelper().visible;
   grid.visible=false;border.visible=false;transform.getHelper().visible=false;
   let imageData;
   try{renderer.render(scene,camera);imageData=renderer.domElement.toDataURL("image/png")}
   finally{grid.visible=oldGrid;border.visible=oldBorder;transform.getHelper().visible=oldHelp}
   const form=new FormData();
   form.append("csrf", __FJORD_CSRF__);
   form.append("name",name.trim().slice(0,120));
   form.append("model",blob,"Creation-du-Fjord.stl");
   if(imageData&&imageData.startsWith("data:image/png;base64,")){
     const image=await (await fetch(imageData)).blob();
     if(image.size<4*1024*1024)form.append("preview",image,"apercu.png");
   }
   const response=await fetch("/admin/modeles/api/save",{method:"POST",body:form,credentials:"same-origin"});
   const result=await response.json();
   if(!response.ok)throw new Error(result.error||"Sauvegarde impossible");
   if(confirm("Modèle enregistré! Veux-tu préparer la soumission maintenant?"))
      location.href="/admin/soumissions-pro?model_id="+encodeURIComponent(result.id);
   else location.href="/admin/modeles";
 }catch(e){alert("Erreur : "+String(e.message||e))}
 finally{privateSaveBtn.disabled=false;privateSaveBtn.textContent="💾 Mes modèles (privé)"}
});
""".replace("__FJORD_CSRF__", json.dumps(csrf_token))
    return html.replace("/* End parametric generators */", injection + "\n/* End parametric generators */", 1)

def register_private_fjord(app, db, admin_required, verify, csrfinput, csrf, page):
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS private_models (
          id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, filename TEXT NOT NULL,
          filedata BYTEA NOT NULL, preview BYTEA, preview_mime TEXT,
          created TIMESTAMPTZ DEFAULT NOW())""")
        c.execute("""CREATE TABLE IF NOT EXISTS private_quotes (
          id BIGSERIAL PRIMARY KEY, customer TEXT NOT NULL, email TEXT, phone TEXT,
          title TEXT NOT NULL, description TEXT, material TEXT NOT NULL,
          quantity INTEGER NOT NULL, unit_price NUMERIC(12,2) NOT NULL,
          shipping NUMERIC(12,2) NOT NULL DEFAULT 0, apply_taxes BOOLEAN NOT NULL DEFAULT FALSE,
          model_id BIGINT REFERENCES private_models(id) ON DELETE SET NULL,
          preview BYTEA, preview_mime TEXT,
          grams DOUBLE PRECISION, hours DOUBLE PRECISION, filament_kg DOUBLE PRECISION,
          machine_hour DOUBLE PRECISION, setup_cost DOUBLE PRECISION,
          markup DOUBLE PRECISION, created TIMESTAMPTZ DEFAULT NOW())""")

    def _save_model():
        name = request.form.get("name", "").strip()[:120]
        upload = request.files.get("model")
        if not name or not upload or not upload.filename:
            abort(400, "Nom et modèle requis.")
        filename = secure_filename(upload.filename)
        if not filename.lower().endswith(MODEL_EXT):
            abort(400, "STL, 3MF ou projet JSON requis.")
        data = upload.read(MAX_MODEL + 1)
        if not data or len(data) > MAX_MODEL:
            abort(413)
        if filename.lower().endswith(".3mf") and not data.startswith(b"PK"):
            abort(400, "Fichier 3MF invalide.")
        if filename.lower().endswith(".stl") and not (len(data) >= 84 or data[:5].lower() == b"solid"):
            abort(400, "Fichier STL invalide.")
        if filename.lower().endswith(".json"):
            try:
                obj = json.loads(data)
                if not isinstance(obj, dict) or not isinstance(obj.get("objects"), list):
                    abort(400, "Projet JSON invalide.")
            except (ValueError, UnicodeDecodeError):
                abort(400, "Projet JSON invalide.")
        preview = _image(request.files.get("preview"))
        with db() as c:
            row = c.execute("""INSERT INTO private_models(name,filename,filedata,preview,preview_mime)
                VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (name, filename, data, preview[1] if preview else None,
                 preview[0] if preview else None)).fetchone()
        return row["id"]

    @app.get("/admin/modeles")
    @admin_required
    def fjord_models():
        with db() as c:
            models = c.execute("""SELECT id,name,filename,octet_length(filedata) AS bytes,
                  preview IS NOT NULL AS has_preview,created
                  FROM private_models ORDER BY created DESC LIMIT 300""").fetchall()
        return page("Mes modèles 3D", r"""
<style>
.fjord-actions{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.fjord-file{display:grid;grid-template-columns:110px 1fr;gap:14px;align-items:center}
.fjord-file img{width:110px;height:100px;object-fit:contain;background:#061422;border-radius:9px}
.fjord-file .muted{word-break:break-word}.fjord-file form{margin-top:9px}
@media(max-width:550px){.fjord-file{grid-template-columns:1fr}.fjord-file img{width:100%;height:170px}}
</style>
<div class="eyebrow">Administration privée</div><h1>Ma bibliothèque 3D</h1>
<p>Tes modèles sont conservés dans la base de données du site. Retrouve-les sur ton ordinateur ou ton téléphone, télécharge leur STL/3MF ou démarre une soumission.</p>
<div class="fjord-actions"><a class="btn" href="/admin/atelier-3d">✦ Ouvrir mon Atelier 3D</a><a class="btn" href="/admin/soumissions-pro">📄 Soumissions PRO</a><a href="/admin">← Administration</a></div>
<div class="card"><h2>Importer un modèle existant</h2><p class="muted small">STL, 3MF ou projet JSON de l'Atelier (8 Mo maximum). Ajoute une image pour voir la pièce dans tes soumissions.</p>
<form method="post" action="/admin/modeles/upload" enctype="multipart/form-data">{{csrf|safe}}
<label>Nom du modèle<input name="name" maxlength="120" required placeholder="Ex. Support de téléphone RAM"></label>
<label>Fichier 3D<input type="file" name="model" accept=".stl,.3mf,.json" required></label>
<label>Photo ou capture 3D (facultatif)<input type="file" name="preview" accept="image/png,image/jpeg,image/webp"></label>
<button>Enregistrer dans ma bibliothèque</button></form></div>
<h2>Modèles enregistrés ({{models|length}})</h2>
<div class="grid">{% for m in models %}<article class="card fjord-file">
{% if m.has_preview %}<img loading="lazy" src="/admin/modeles/apercu/{{m.id}}" alt="Aperçu {{m.name}}">
{% else %}<div class="card" style="text-align:center;font-size:38px">🧊</div>{% endif %}
<div><strong>{{m.name}}</strong><p class="muted small">{{m.filename}} · {{(m.bytes/1024)|round|int}} Ko · {{m.created.strftime('%d-%m-%Y')}}</p>
<div class="fjord-actions"><a href="/admin/modeles/fichier/{{m.id}}">⬇ Télécharger</a><a href="/admin/soumissions-pro?model_id={{m.id}}">Créer la soumission</a></div>
<form method="post" action="/admin/modeles/supprimer/{{m.id}}" onsubmit="return confirm('Supprimer ce modèle de la bibliothèque?')">{{csrf|safe}}<button type="submit">Supprimer</button></form></div></article>
{% else %}<p>Aucun modèle pour le moment. Importe ton premier STL ou enregistre une création depuis ton Atelier privé.</p>{% endfor %}</div>
""",models=models,csrf=csrfinput())

    @app.post("/admin/modeles/upload")
    @admin_required
    def fjord_model_upload():
        verify()
        _save_model()
        flash("Modèle conservé dans ta bibliothèque privée.")
        return redirect("/admin/modeles")

    @app.post("/admin/modeles/api/save")
    @admin_required
    def fjord_model_api_save():
        verify()
        try:
            model_id=_save_model()
        except Exception as exc:
            # The browser receives an error status without a private traceback.
            from werkzeug.exceptions import HTTPException
            if isinstance(exc, HTTPException):
                return {"error":exc.description},exc.code
            raise
        return {"ok":True,"id":model_id}

    @app.get("/admin/modeles/fichier/<int:model_id>")
    @admin_required
    def fjord_model_download(model_id):
        with db() as c:
            model=c.execute("SELECT filename,filedata FROM private_models WHERE id=%s",
                            (model_id,)).fetchone()
        if not model:abort(404)
        return send_file(io.BytesIO(model["filedata"]),as_attachment=True,
                         download_name=model["filename"],mimetype="application/octet-stream")

    @app.get("/admin/modeles/apercu/<int:model_id>")
    @admin_required
    def fjord_model_preview(model_id):
        with db() as c:
            model=c.execute("SELECT preview,preview_mime FROM private_models WHERE id=%s",
                            (model_id,)).fetchone()
        if not model or not model["preview"]:abort(404)
        return send_file(io.BytesIO(model["preview"]),mimetype=model["preview_mime"],
                         max_age=0)

    @app.post("/admin/modeles/supprimer/<int:model_id>")
    @admin_required
    def fjord_model_delete(model_id):
        verify()
        with db() as c:c.execute("DELETE FROM private_models WHERE id=%s",(model_id,))
        flash("Modèle supprimé de la bibliothèque.")
        return redirect("/admin/modeles")

    @app.get("/admin/soumissions-pro")
    @admin_required
    def fjord_quotes():
        with db() as c:
            models=c.execute("SELECT id,name,preview IS NOT NULL AS has_preview FROM private_models ORDER BY created DESC LIMIT 300").fetchall()
            quotes=c.execute("""SELECT id,customer,title,quantity,unit_price,shipping,
                     apply_taxes,created FROM private_quotes ORDER BY id DESC LIMIT 150""").fetchall()
        chosen=request.args.get("model_id","",type=str)
        return page("Soumissions PRO",r"""
<style>
.fj-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.fj-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.fj-two label{min-width:0}.fj-two input,.fj-two select{max-width:100%}
.fj-help{font-size:13px;color:#b4d1e1}
.fj-summary{background:#132e43;border:1px solid #58bce8;border-radius:12px;padding:20px}
.fj-summary strong{display:block;font-size:30px;color:#7ee7ff}
.fj-summary p{margin:5px 0}.fj-card{margin:18px 0}
.fj-model-photo{display:block;width:240px;height:150px;object-fit:contain;border-radius:11px;background:#061421;margin:10px 0}
@media(max-width:700px){.fj-two{grid-template-columns:1fr}}
</style>
<div class="eyebrow">Visible uniquement par l'administrateur</div>
<div class="fj-head"><h1>Soumissions PRO</h1><a href="/admin/modeles">📚 Mes modèles 3D</a><a href="/admin">← Administration</a></div>
<p>Les coûts, taux machine et majorations sont privés. Le PDF remis au client indique seulement la pièce, le prix et les taxes applicables.</p>
<div class="card fj-card"><h2>Nouvelle soumission</h2>
<form method="post" action="/admin/soumissions-pro/creer" enctype="multipart/form-data" style="max-width:none" id="fjQuote">{{csrf|safe}}
<div class="fj-two">
<label>Nom du client<input name="customer" maxlength="120" required></label>
<label>Adresse courriel<input type="email" name="email" maxlength="180"></label>
<label>Téléphone<input name="phone" maxlength="40"></label>
<label>Objet / nom de la pièce<input name="title" maxlength="160" required></label>
<label>Modèle de ma bibliothèque<select name="model_id" id="fjModel"><option value="">Aucun / soumission manuelle</option>{% for m in models %}<option value="{{m.id}}" data-preview="{{'/admin/modeles/apercu/' ~ m.id if m.has_preview else ''}}" {% if chosen==m.id|string %}selected{% endif %}>{{m.name}}</option>{% endfor %}</select></label>
<label>Matériau<select name="material" id="fjMaterial">{% for m in materials %}<option value="{{m}}" {% if m=='PETG' %}selected{% endif %}>{{m}}</option>{% endfor %}</select></label>
</div><img id="fjPreview" class="fj-model-photo" alt="Aperçu de la pièce" hidden>
<label>Ou ajouter une photo 3D personnalisée<input type="file" name="preview" accept="image/jpeg,image/png,image/webp"></label>
<label>Description du travail<textarea name="description" maxlength="2500" placeholder="Couleur, finition, dimensions, inclusions…"></textarea></label>
<div class="fj-two">
<label>Quantité<input type="number" name="quantity" min="1" max="10000" step="1" value="1" required></label>
<label>Poids prévu par unité (g)<input type="number" name="grams" min="0" max="100000" step="0.1" value="50"></label>
<label>Durée d'impression par unité (h)<input type="number" name="hours" min="0" max="1000" step="0.1" value="3"></label>
<label>Coût filament ($ CA/kg)<input type="number" name="filament_kg" min="0" max="10000" step="0.01" value="32"></label>
<label>Coût machine ($ CA/h)<input type="number" name="machine_hour" min="0" max="10000" step="0.01" value="3"></label>
<label>Préparation par unité ($ CA)<input type="number" name="setup_cost" min="0" max="10000" step="0.01" value="8"></label>
<label>Majoration sur les coûts (%)<input type="number" name="markup" min="0" max="500" step="0.1" value="25"></label>
<label>Prix de vente par unité ($ CA) — facultatif<input type="number" name="override_price" min="0" max="100000" step="0.01" placeholder="Calcul automatique"></label>
<label>Livraison / frais fixes ($ CA)<input type="number" name="shipping" min="0" max="100000" step="0.01" value="0"></label>
</div>
<label><input style="display:inline;width:auto;margin-right:8px" type="checkbox" name="apply_taxes" value="yes">Appliquer TPS (5 %) et TVQ (9,975 %) — seulement si l'entreprise doit les percevoir</label>
<div class="fj-summary"><span>Prix final prévu, taxes incluses si sélectionnées</span><strong id="fjTotal">—</strong><p id="fjBreakdown" class="fj-help"></p></div>
<p class="fj-help">Le calcul est indicatif tant que le poids et la durée ne sont pas validés dans le trancheur. Aucun taux privé n'est ajouté au PDF du client.</p>
<button type="submit">Enregistrer la soumission</button></form></div>
<h2>Soumissions enregistrées</h2><div class="grid">{% for q in quotes %}<div class="card"><div class="eyebrow">FJ-{{'%05d'|format(q.id)}} · {{q.created.strftime('%d-%m-%Y')}}</div><h3>{{q.customer}}</h3><p>{{q.title}} · {{q.quantity}} exemplaire(s)</p>
<p>Prix unitaire : {{money(q.unit_price|float)}} · Livraison : {{money(q.shipping|float)}}</p>
<a class="btn" href="/admin/soumissions-pro/{{q.id}}/pdf">⬇ Soumission PDF</a></div>
{% else %}<p>Aucune soumission enregistrée.</p>{% endfor %}</div>
<script>
(function(){
 const f=document.getElementById("fjQuote"),o=document.getElementById("fjTotal"),d=document.getElementById("fjBreakdown");
 const currency=n=>new Intl.NumberFormat("fr-CA",{style:"currency",currency:"CAD"}).format(n);
 function n(key){const el=f.elements.namedItem(key);return Number(el&&el.value||0)}
 function update(){
  const c=(n("grams")/1000*n("filament_kg")*1.1+n("hours")*n("machine_hour")+n("setup_cost"));
  const generated=c*(1+n("markup")/100);
  const override=f.elements.namedItem("override_price");
  const unit=override.value.trim()===""?generated:Number(override.value);
  const subtotal=unit*n("quantity")+n("shipping");
  const tax=f.elements.namedItem("apply_taxes").checked ?subtotal*(.05+.09975):0;
  o.textContent=currency(subtotal+tax);
  d.textContent="Coût de base : "+currency(c)+" · Prix unitaire : "+currency(unit)+" · Sous-total : "+currency(subtotal)+" · Taxes : "+currency(tax);
 }
 f.addEventListener("input",update);f.addEventListener("change",update);
 const selector=document.getElementById("fjModel"),image=document.getElementById("fjPreview");
 function updateImage(){const src=selector.selectedOptions[0]?.dataset.preview||"";image.hidden=!src;if(src)image.src=src}
 selector.addEventListener("change",updateImage);updateImage();update();
})();
</script>""",models=models,quotes=quotes,chosen=chosen,materials=MATERIALS,
          money=_money,csrf=csrfinput())

    @app.post("/admin/soumissions-pro/creer")
    @admin_required
    def fjord_quote_create():
        verify()
        customer=request.form.get("customer","").strip()[:120]
        title=request.form.get("title","").strip()[:160]
        email=request.form.get("email","").strip()[:180]
        phone=request.form.get("phone","").strip()[:40]
        description=request.form.get("description","").strip()[:2500]
        material=request.form.get("material","PETG")
        if not customer or not title or material not in MATERIALS:
            abort(400)
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email):
            abort(400)
        quantity=_number("quantity",1,1,10000)
        if not quantity.is_integer():abort(400)
        grams=_number("grams",50,0,100000)
        hours=_number("hours",3,0,1000)
        filament_kg=_number("filament_kg",32,0,10000)
        machine_hour=_number("machine_hour",3,0,10000)
        setup_cost=_number("setup_cost",8,0,10000)
        markup=_number("markup",25,0,500)
        shipping=round(_number("shipping",0,0,100000),2)
        base=(grams/1000*filament_kg*1.10)+(hours*machine_hour)+setup_cost
        calculated=base*(1+markup/100)
        override=request.form.get("override_price","").strip()
        unit=round(_number("override_price",0,0,100000) if override else calculated,2)
        if unit>100000:abort(400)
        taxes=request.form.get("apply_taxes")=="yes"
        model_input=request.form.get("model_id","").strip()
        try:model_id=int(model_input) if model_input else None
        except ValueError:abort(400)
        preview=_image(request.files.get("preview"))
        with db() as c:
            if model_id:
                model=c.execute("SELECT preview,preview_mime FROM private_models WHERE id=%s",(model_id,)).fetchone()
                if not model:abort(400,"Modèle introuvable")
                if not preview and model["preview"]:
                    preview=(model["preview_mime"],model["preview"])
            result=c.execute("""INSERT INTO private_quotes
               (customer,email,phone,title,description,material,quantity,unit_price,
                shipping,apply_taxes,model_id,preview,preview_mime,grams,hours,filament_kg,
                machine_hour,setup_cost,markup)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",(customer,email,phone,title,description,material,
               int(quantity),unit,shipping,taxes,model_id,
               preview[1] if preview else None,preview[0] if preview else None,
               grams,hours,filament_kg,machine_hour,setup_cost,markup)).fetchone()
        flash("Soumission créée. Tu peux maintenant télécharger le PDF.")
        return redirect("/admin/soumissions-pro/"+str(result["id"])+"/pdf")

    @app.get("/admin/soumissions-pro/<int:quote_id>/pdf")
    @admin_required
    def fjord_quote_pdf(quote_id):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader, simpleSplit
        from reportlab.pdfgen import canvas
        with db() as c:
            q=c.execute("SELECT * FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            setting=c.execute("SELECT value FROM settings WHERE key='fjord_quote_logo'").fetchone()
        if not q:abort(404)
        logo=None
        if setting:
            try:logo=base64.b64decode(setting["value"],validate=True)
            except Exception:logo=None
        buffer=io.BytesIO()
        pdf=canvas.Canvas(buffer,pagesize=letter)
        w,h=letter
        navy=colors.HexColor("#071D31")
        cyan=colors.HexColor("#0697CE")
        gray=colors.HexColor("#44546B")
        pdf.setTitle("Soumission FJ-{:05d} - Les Impressions du Fjord".format(q["id"]))
        pdf.setFillColor(navy);pdf.rect(0,h-154,w,154,stroke=0,fill=1)
        if logo:
            try:pdf.drawImage(ImageReader(io.BytesIO(logo)),39,h-134,105,105,mask="auto",preserveAspectRatio=True,anchor="c")
            except Exception:pass
        pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",19)
        pdf.drawString(156,h-71,"LES IMPRESSIONS DU FJORD")
        pdf.setFont("Helvetica",10)
        pdf.drawString(157,h-92,"Impression 3D personnalisée  |  Saguenay, Québec")
        pdf.drawString(157,h-110,"Téléphone : 581-998-0831")
        pdf.setFillColor(cyan);pdf.rect(0,h-159,w,5,stroke=0,fill=1)
        def line(text,x,y,font="Helvetica",size=11,color=gray,max_width=520):
            pdf.setFillColor(color);pdf.setFont(font,size)
            clean=str(text or "").replace("\n"," ").encode("cp1252","replace").decode("cp1252")
            for fragment in simpleSplit(clean,font,size,max_width)[:9]:
                pdf.drawString(x,y,fragment);y-=size+5
            return y
        y=h-198
        y=line("SOUMISSION  FJ-{:05d}".format(q["id"]),38,y,"Helvetica-Bold",19,navy)
        y-=5
        y=line("Date : "+q["created"].strftime("%d-%m-%Y")+"    |    Validité : 30 jours",39,y,size=10)
        y-=17
        y=line("PRÉPARÉE POUR",39,y,"Helvetica-Bold",10,cyan)
        y=line(q["customer"],39,y,"Helvetica-Bold",13,navy)
        if q["email"]:y=line(q["email"],39,y,size=10)
        if q["phone"]:y=line(q["phone"],39,y,size=10)
        y-=21
        y=line("VOTRE PROJET",39,y,"Helvetica-Bold",10,cyan)
        y=line(q["title"],39,y,"Helvetica-Bold",14,navy)
        y=line("Matériau : "+q["material"]+"    |    Quantité : "+str(q["quantity"]),39,y)
        if q["description"]:
            y-=7
            y=line(q["description"],39,y,size=10,max_width=490)
        if q["preview"] and y>310:
            try:
                reader=ImageReader(io.BytesIO(q["preview"]))
                iw,ih=reader.getSize()
                factor=min(235/max(iw,1),145/max(ih,1))
                pw,ph=iw*factor,ih*factor
                pdf.setFillColor(colors.HexColor("#EDF7FC"))
                pdf.roundRect(37,y-162,539,165,10,stroke=0,fill=1)
                pdf.drawImage(reader, (w-pw)/2, y-154+(145-ph)/2,pw,ph,mask="auto")
                y-=178
            except Exception:pass
        y=min(y-14,250)
        subtotal=round(float(q["unit_price"])*q["quantity"]+float(q["shipping"]),2)
        gst=round(subtotal*0.05,2) if q["apply_taxes"] else 0
        qst=round(subtotal*0.09975,2) if q["apply_taxes"] else 0
        total=subtotal+gst+qst
        def totalrow(label,amount,y,bold=False):
            pdf.setFont("Helvetica-Bold" if bold else "Helvetica",11 if not bold else 15)
            pdf.setFillColor(navy)
            pdf.drawString(40,y,label)
            pdf.drawRightString(w-39,y,_money(amount).encode("cp1252","replace").decode("cp1252"))
            return y-25
        y=totalrow("Prix unitaire x "+str(q["quantity"]),float(q["unit_price"])*q["quantity"],y)
        if float(q["shipping"]):y=totalrow("Livraison / frais fixes",float(q["shipping"]),y)
        if q["apply_taxes"]:
            y=totalrow("TPS (5 %)",gst,y)
            y=totalrow("TVQ (9,975 %)",qst,y)
        pdf.setStrokeColor(cyan);pdf.line(38,y+12,w-39,y+12)
        y=totalrow("TOTAL CAD",total,y-8,True)
        pdf.setFont("Helvetica",9);pdf.setFillColor(gray)
        pdf.drawString(39,62,"Merci de faire confiance aux Impressions du Fjord.")
        pdf.drawString(39,46,"Toute modification du modèle ou des spécifications peut entraîner une révision du prix.")
        pdf.save();buffer.seek(0)
        return send_file(buffer,mimetype="application/pdf",as_attachment=True,
                  download_name="Soumission-FJ-{:05d}.pdf".format(q["id"]))

    @app.post("/admin/soumissions-pro/logo")
    @admin_required
    def fjord_logo_upload():
        verify()
        image=_image(request.files.get("logo"))
        if not image:abort(400)
        # Conserver l'image en base64 texte dans les paramètres privés.
        with db() as c:
            c.execute("""INSERT INTO settings(key,value) VALUES('fjord_quote_logo',%s)
             ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value""",
             (base64.b64encode(image[1]).decode("ascii"),))
        flash("Logo mis à jour pour les nouvelles impressions PDF.")
        return redirect("/admin/soumissions-pro")
