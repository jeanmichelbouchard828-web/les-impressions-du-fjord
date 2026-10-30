"""Fonctions privées de Les Impressions du Fjord.
Les données de coûts et les fichiers ne sont jamais exposés par les routes publiques.
"""
import base64
import datetime
import io
import json
import math
import re
import secrets

from flask import abort, flash, make_response, redirect, render_template_string, request, send_file, url_for
from werkzeug.utils import secure_filename

MATERIALS = ("PLA", "PETG", "PETG-CF", "ASA", "TPU", "Autre")
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

def _quote_amounts(q):
    """Même calcul des taxes pour le PDF et la page de paiement."""
    subtotal = round(float(q["unit_price"]) * int(q["quantity"]) + float(q["shipping"]), 2)
    gst = round(subtotal * 0.05, 2) if q["apply_taxes"] else 0.0
    qst = round(subtotal * 0.09975, 2) if q["apply_taxes"] else 0.0
    return subtotal, gst, qst, round(subtotal + gst + qst, 2)


def _quote_payment_token(db, q):
    """Émet un lien non prédictible une seule fois; fonctionne aussi pour les anciennes soumissions."""
    existing = q.get("payment_token")
    if existing:
        return existing
    with db() as c:
        row = c.execute("""UPDATE private_quotes SET payment_token=%s
            WHERE id=%s AND payment_token IS NULL RETURNING payment_token""",
            (secrets.token_urlsafe(32), q["id"])).fetchone()
        if row:
            return row["payment_token"]
        row = c.execute("SELECT payment_token FROM private_quotes WHERE id=%s",
                        (q["id"],)).fetchone()
        return row["payment_token"] if row else None


def admin_studio(html, csrf_token):
    """Le bouton d'enregistrement est ajouté UNIQUEMENT à l'atelier authentifié."""
    button = '<button type="button" id="fjordPrivateImport">📚 Importer de ma bibliothèque</button><button type="button" class="primary" id="fjordPrivateSave">💾 Enregistrer dans ma bibliothèque</button><a href="/admin/modeles">Voir mes modèles</a>'
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
    open_model = r"""
// Bibliothèque privée consultable sans quitter le plateau.
const fjordImportButton=document.getElementById('fjordPrivateImport');
const fjordDialog=document.createElement('dialog');
fjordDialog.id='fjordModelChooser';
fjordDialog.setAttribute('aria-label','Importer un modèle de ma bibliothèque');
fjordDialog.innerHTML='<div class="fjord-dialog-head"><strong>📚 Mes modèles 3D</strong><button type="button" id="fjordDialogClose">✕ Fermer</button></div>'+
 '<p>Choisis une pièce : elle sera ajoutée au plateau sans supprimer les autres.</p>'+
 '<input id="fjordModelSearch" type="search" placeholder="Rechercher un modèle…" aria-label="Rechercher dans les modèles">'+
 '<div id="fjordModelItems" class="fjord-model-items" aria-live="polite"></div>';
document.body.appendChild(fjordDialog);
const fjordClose=document.getElementById('fjordDialogClose');
const fjordSearch=document.getElementById('fjordModelSearch');
const fjordItems=document.getElementById('fjordModelItems');
let fjordModelList=[];
fjordClose.addEventListener('click',()=>fjordDialog.close());
fjordDialog.addEventListener('click',e=>{if(e.target===fjordDialog)fjordDialog.close()});
function fjordRenderModelList(){
 const term=fjordSearch.value.trim().toLocaleLowerCase('fr');
 fjordItems.replaceChildren();
 const found=fjordModelList.filter(x=>(x.name+' '+x.filename).toLocaleLowerCase('fr').includes(term));
 if(!found.length){const p=document.createElement('p');p.textContent='Aucun modèle trouvé.';fjordItems.append(p);return}
 for(const item of found){
   const row=document.createElement('div');row.className='fjord-library-item';
   if(item.has_preview){
     const img=document.createElement('img');img.loading='lazy';img.alt='';
     img.src='/admin/modeles/apercu/'+item.id;row.append(img);
   }else{const placeholder=document.createElement('span');placeholder.textContent='🧊';row.append(placeholder)}
   const info=document.createElement('div');info.style.minWidth='0';
   const title=document.createElement('strong');title.textContent=item.name;
   const meta=document.createElement('small');meta.textContent=item.filename;
   info.append(title,meta);row.append(info);
   const btn=document.createElement('button');btn.type='button';btn.textContent='Ajouter';
   btn.addEventListener('click',async()=>{
     btn.disabled=true;btn.textContent='Importation…';
     try{
       await fjordImportSaved(item);
       fjordDialog.close();
     }catch(err){alert('Importation impossible : '+String(err.message||err))}
     finally{btn.disabled=false;btn.textContent='Ajouter'}
   });
   row.append(btn);fjordItems.append(row);
 }
}
fjordSearch.addEventListener('input',fjordRenderModelList);
async function fjordImportSaved(item){
 const resp=await fetch('/admin/modeles/fichier/'+item.id,{credentials:'same-origin'});
 if(!resp.ok)throw Error('Accès au fichier refusé (HTTP '+resp.status+'). Reconnecte-toi à l’administration.');
 const blob=await resp.blob();
 const file=new File([blob],item.filename,{type:'application/octet-stream'});
 return importModelFile(file,item.name);
}
if(fjordImportButton)fjordImportButton.addEventListener('click',async()=>{
 fjordImportButton.disabled=true;fjordItems.textContent='Chargement des modèles…';
 try{
   const resp=await fetch('/admin/modeles/api/liste',{credentials:'same-origin',headers:{'Accept':'application/json'}});
   if(!resp.ok||!(resp.headers.get('content-type')||'').includes('application/json'))
       throw Error('La session administrateur a expiré.');
   const data=await resp.json();
   if(!data.ok||!Array.isArray(data.models))throw Error('Réponse invalide de la bibliothèque');
   fjordModelList=data.models;fjordSearch.value='';fjordRenderModelList();
   fjordDialog.showModal();fjordSearch.focus();
 }catch(err){alert('Bibliothèque indisponible : '+String(err.message||err))}
 finally{fjordImportButton.disabled=false}
});
const savedModelId=new URLSearchParams(location.search).get("model_id");
if(savedModelId && /^[0-9]+$/.test(savedModelId)){
 (async()=>{
   try{
     const response=await fetch('/admin/modeles/api/info/'+savedModelId,{credentials:'same-origin'});
     if(!response.ok)throw Error('Modèle introuvable');
     const info=await response.json();
     if(!info.ok)throw Error('Modèle introuvable');
     await fjordImportSaved({id:savedModelId,name:info.name,filename:info.filename});
   }catch(err){alert('Impossible d’importer le modèle : '+String(err.message||err))}
 })();
}
"""
    styles = """
<style>
#fjordModelChooser{max-width:min(680px,94vw);width:94vw;max-height:85dvh;overflow:auto;
 background:#10283b;color:#eef9ff;border:1px solid #51bfe5;border-radius:16px;padding:18px;box-shadow:0 25px 75px #0009}
#fjordModelChooser::backdrop{background:#000b}
#fjordModelChooser .fjord-dialog-head{display:flex;gap:12px;justify-content:space-between;align-items:center}
#fjordModelChooser .fjord-dialog-head strong{font-size:19px}
#fjordModelChooser input{width:100%;margin:10px 0 14px;min-height:44px}
#fjordModelChooser .fjord-model-items{display:grid;gap:9px}
#fjordModelChooser .fjord-library-item{display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:10px;align-items:center;
 padding:10px;border-radius:11px;background:#173650;border:1px solid #3c607b}
#fjordModelChooser img{width:64px;height:57px;object-fit:contain;background:#0b1d2f;border-radius:7px}
#fjordModelChooser .fjord-library-item>span{display:grid;place-items:center;font-size:30px}
#fjordModelChooser small{display:block;color:#b7cddb;overflow-wrap:anywhere}
#fjordModelChooser .fjord-library-item button{min-height:43px}
@media(max-width:420px){
 #fjordModelChooser{padding:12px}
 #fjordModelChooser .fjord-library-item{grid-template-columns:46px minmax(0,1fr);gap:7px}
 #fjordModelChooser img{width:46px;height:45px}
 #fjordModelChooser .fjord-library-item button{grid-column:2;justify-self:start}
}
</style>
"""
    html = html.replace("</head>", styles + "</head>", 1)
    return html.replace("/* End parametric generators */", injection + "\n" + open_model + "\n/* End parametric generators */", 1)


def public_studio(html):
    """Ne pas afficher les réglages de coût dans l'Atelier des visiteurs."""
    style = """<style>
    #estimatePanel details:has(#estimateKg), #estimateBreakdown,
    #sliceMaterialCostValue, #sliceMachineCostValue, #sliceSetupMarkupValue,
    .slice-metrics>span:has(+ #sliceMaterialCostValue),
    .slice-metrics>span:has(+ #sliceMachineCostValue),
    .slice-metrics>span:has(+ #sliceSetupMarkupValue) {
      display:none!important;
    }
    </style>"""
    return html.replace("</head>",style+"</head>",1)

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
          markup DOUBLE PRECISION, payment_token TEXT UNIQUE,
          created TIMESTAMPTZ DEFAULT NOW())""")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS payment_token TEXT")
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS private_quotes_payment_token_idx
                     ON private_quotes(payment_token)""")

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

    @app.post("/admin/modeles/import-demande/<int:request_id>")
    @admin_required
    def fjord_import_request_model(request_id):
        verify()
        with db() as c:
            source=c.execute("""SELECT kind,name,filename,filedata FROM requests
                                 WHERE id=%s""",(request_id,)).fetchone()
            if not source or source["kind"]!="Soumission" or not source["filedata"]:
                abort(404)
            if len(source["filedata"])>MAX_MODEL:abort(413)
            result=c.execute("""INSERT INTO private_models(name,filename,filedata)
                VALUES(%s,%s,%s) RETURNING id""",
                ("Demande #"+str(request_id)+" - "+source["name"],
                 source["filename"],source["filedata"])).fetchone()
        return redirect("/admin/soumissions-pro?model_id="+str(result["id"])+
                        "&request_id="+str(request_id))

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
<div class="fjord-actions"><a href="/admin/modeles/fichier/{{m.id}}">⬇ Télécharger</a><a href="/admin/soumissions-pro?model_id={{m.id}}">Créer la soumission</a><a href="/admin/atelier-3d?model_id={{m.id}}">➕ Importer dans l’Atelier</a></div>
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

    @app.get("/admin/modeles/api/liste")
    @admin_required
    def fjord_model_list_json():
        with db() as c:
            rows=c.execute("""SELECT id,name,filename,preview IS NOT NULL AS has_preview
                               FROM private_models ORDER BY created DESC LIMIT 500""").fetchall()
        return {"ok":True,"models":[{"id":m["id"],"name":m["name"],
                  "filename":m["filename"],"has_preview":m["has_preview"]}
                  for m in rows]}

    @app.get("/admin/modeles/api/info/<int:model_id>")
    @admin_required
    def fjord_model_info(model_id):
        with db() as c:
            item=c.execute("SELECT name,filename FROM private_models WHERE id=%s",
                           (model_id,)).fetchone()
        if not item:abort(404)
        return {"ok":True,"name":item["name"],"filename":item["filename"]}

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
            payment_setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        interac_email=payment_setting["value"] if payment_setting else ""
        chosen=request.args.get("model_id","",type=str)
        request_id=request.args.get("request_id",type=int)
        incoming=None
        if request_id:
            with db() as c:
                incoming=c.execute("""SELECT id,kind,name,email,phone,material,description
                    FROM requests WHERE id=%s""",(request_id,)).fetchone()
            if incoming and incoming["kind"]!="Soumission":
                incoming=None
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
.fj-import-panel{background:#102b40;border:1px solid #426c83;border-radius:11px;padding:16px;margin:10px 0 18px}
.fj-import-panel label{margin-bottom:8px}
.fj-import-panel .fj-help{margin:7px 0 0}
.fj-import-panel [role=status]{min-height:24px;white-space:normal;overflow-wrap:anywhere}
body.light .fj-import-panel{background:#ecf7fd;border-color:#a7cfdf}
body.light .fj-import-panel .fj-help{color:#30556a}
@media(max-width:700px){.fj-two{grid-template-columns:1fr}}
</style>
<div class="eyebrow">Visible uniquement par l'administrateur</div>
<div class="fj-head"><h1>Soumissions PRO</h1><a href="/admin/modeles">📚 Mes modèles 3D</a><a href="/admin">← Administration</a></div>
<p>Les coûts, taux machine et majorations sont privés. Le PDF remis au client indique seulement la pièce, le prix et les taxes applicables.</p>
<div class="card fj-card"><h2>Nouvelle soumission</h2>
<form method="post" action="/admin/soumissions-pro/creer" enctype="multipart/form-data" style="max-width:none" id="fjQuote">{{csrf|safe}}
<div class="fj-two">
<label>Nom du client<input name="customer" maxlength="120" value="{{incoming.name if incoming else ''}}" required></label>
<label>Adresse courriel<input type="email" name="email" maxlength="180" value="{{incoming.email if incoming else ''}}"></label>
<label>Téléphone<input name="phone" maxlength="40" value="{{incoming.phone if incoming else ''}}"></label>
<label>Objet / nom de la pièce<input name="title" maxlength="160" value="{{'Impression 3D - demande #' ~ incoming.id if incoming else ''}}" required></label>
<label>Modèle de ma bibliothèque<select name="model_id" id="fjModel"><option value="">Aucun / soumission manuelle</option>{% for m in models %}<option value="{{m.id}}" data-preview="{{'/admin/modeles/apercu/' ~ m.id if m.has_preview else ''}}" {% if chosen==m.id|string %}selected{% endif %}>{{m.name}}</option>{% endfor %}</select></label>
<label>Matériau<select name="material" id="fjMaterial">{% for m in materials %}<option value="{{m}}" {% if m==(incoming.material if incoming and incoming.material in materials else 'PETG') %}selected{% endif %}>{{m}}</option>{% endfor %}</select></label>
</div>
<div class="fj-import-panel">
<h3>🧊 Importer un modèle et calculer son prix</h3>
<label>Choisir un fichier STL ou 3MF déjà créé<input type="file" id="fjUpload" accept=".stl,.3mf"></label>
<div class="fj-two">
<label>Hauteur de couche<select id="fjLayer"><option value="0.08">0,08 mm — très fin</option><option value="0.12">0,12 mm — qualité</option><option value="0.2" selected>0,20 mm — standard</option><option value="0.28">0,28 mm — rapide</option></select></label>
<label>Remplissage<select id="fjInfill"><option value="10">10 %</option><option value="15">15 %</option><option value="18" selected>18 %</option><option value="20">20 %</option><option value="30">30 %</option><option value="40">40 %</option><option value="50">50 %</option><option value="75">75 %</option><option value="100">100 %</option></select></label>
</div>
<p role="status" id="fjEstimateStatus" class="fj-help">Sélectionne un modèle ou importe un fichier pour estimer le poids, le temps et le prix automatiquement.</p>
<p class="fj-help">Le modèle importé est conservé dans ta bibliothèque privée. Le tranchage est une estimation générique (buse 0,4 mm), pas un profil d'impression X2D. Vérifie le prix avec Bambu Studio avant de l'envoyer.</p>
</div>
<img id="fjPreview" class="fj-model-photo" alt="Aperçu de la pièce" hidden>
<label>Ou ajouter une photo 3D personnalisée<input type="file" name="preview" accept="image/jpeg,image/png,image/webp"></label>
<label>Description du travail<textarea name="description" maxlength="2500" placeholder="Couleur, finition, dimensions, inclusions…">{{incoming.description if incoming else ''}}</textarea></label>
<div class="fj-two">
<label>Quantité<input type="number" name="quantity" min="1" max="10000" step="1" value="1" required></label>
<label>Poids prévu par unité (g)<input type="number" name="grams" min="0" max="100000" step="0.01" value="50" required></label>
<label>Durée d'impression par unité (h)<input type="number" name="hours" min="0" max="1000" step="0.01" value="3" required></label>
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
<button type="submit" id="fjSaveQuote">Enregistrer la soumission</button></form></div>

<div class="card fj-card"><h2>💸 Paiement par virement Interac</h2>
<p>Ajoute l'adresse courriel associée à tes virements Interac. Une fois configurée, chaque PDF contiendra un bouton et un code QR menant à une page de paiement avec le montant exact et le numéro de soumission.</p>
<form method="post" action="/admin/soumissions-pro/paiement">{{csrf|safe}}
<label>Courriel pour recevoir les virements Interac
<input type="email" name="interac_email" maxlength="180" value="{{interac_email}}" placeholder="Adresse liée à ton dépôt automatique"></label>
<p class="fj-help">Laisse ce champ vide pour masquer le paiement Interac. Assure-toi que cette adresse accepte les virements; idéalement, active le dépôt automatique auprès de ta banque. Le paiement reste à effectuer par le client dans son application bancaire, et le site ne confirme pas sa réception.</p>
<button type="submit">Enregistrer les paramètres Interac</button></form>
</div>
<div class="card fj-card"><h2>Logo sur les soumissions</h2>
<p>Le logo officiel des Impressions du Fjord sera utilisé sur chaque PDF.</p>
<form method="post" action="/admin/soumissions-pro/logo" enctype="multipart/form-data">{{csrf|safe}}
<label>Remplacer le logo (PNG ou JPG)<input type="file" name="logo" accept="image/png,image/jpeg,image/webp" required></label>
<button type="submit">Mettre à jour le logo PDF</button></form></div>
<h2>Soumissions enregistrées</h2><div class="grid">{% for q in quotes %}<div class="card"><div class="eyebrow">FJ-{{'%05d'|format(q.id)}} · {{q.created.strftime('%d-%m-%Y')}}</div><h3>{{q.customer}}</h3><p>{{q.title}} · {{q.quantity}} exemplaire(s)</p>
<p>Prix unitaire : {{money(q.unit_price|float)}} · Livraison : {{money(q.shipping|float)}}</p>
<a class="btn" href="/admin/soumissions-pro/{{q.id}}/pdf">⬇ Soumission PDF</a>
{% if interac_email %}<a href="/admin/soumissions-pro/{{q.id}}/paiement">💸 Ouvrir le lien de paiement</a>{% endif %}</div>
{% else %}<p>Aucune soumission enregistrée.</p>{% endfor %}</div>
<script>
(function(){
 const f=document.getElementById("fjQuote"),o=document.getElementById("fjTotal"),d=document.getElementById("fjBreakdown");
 const selector=document.getElementById("fjModel"),image=document.getElementById("fjPreview");
 const status=document.getElementById("fjEstimateStatus"),fileInput=document.getElementById("fjUpload");
 const save=document.getElementById("fjSaveQuote");
 const grams=f.elements.namedItem("grams"),hours=f.elements.namedItem("hours");
 const material=f.elements.namedItem("material"),csrf=f.elements.namedItem("csrf");
 const layer=document.getElementById("fjLayer"),infill=document.getElementById("fjInfill");
 let requestNumber=0;
 const currency=n=>new Intl.NumberFormat("fr-CA",{style:"currency",currency:"CAD"}).format(n);
 function n(key){const el=f.elements.namedItem(key);return Number(el&&el.value||0)}
 function update(){
  if(grams.value===""||hours.value===""){o.textContent="Estimation en attente";d.textContent="Poids et durée nécessaires pour établir le prix.";return}
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
 function message(text){status.textContent=text}
 function busy(value){save.disabled=value;save.textContent=value?"Calcul en cours…":"Enregistrer la soumission"}
 function updateImage(){const src=selector.selectedOptions[0]?.dataset.preview||"";image.hidden=!src;if(src)image.src=src}
 async function estimate(){
  const id=selector.value,serial=++requestNumber;
  updateImage();
  if(!id){
   busy(false);message("Soumission manuelle : entre le poids et la durée de ta pièce.");return;
  }
  grams.value="";hours.value="";update();busy(true);
  if(material.value==="Autre"){
   busy(false);message("Matériau « Autre » : indique manuellement le poids et la durée.");return;
  }
  message("Tranchage du modèle en cours : estimation du filament et du temps d'impression…");
  const body=new FormData();
  body.append("csrf",csrf.value);body.append("model_id",id);
  body.append("material",material.value);body.append("layer_height",layer.value);
  body.append("infill",infill.value);
  try{
   const response=await fetch("/admin/soumissions-pro/estimer",
                              {method:"POST",body,credentials:"same-origin"});
   const result=await response.json();
   if(serial!==requestNumber)return;
   if(!response.ok||!result.ok)throw Error(result.error||"Calcul indisponible.");
   grams.value=result.grams;hours.value=result.hours;
   message("✓ "+result.grams+" g de filament · "+result.hours+
           " h d'impression estimées · remplissage "+result.infill+
           " % · couche "+result.layer_height+" mm. Vérifie avec ton profil Bambu Studio.");
   update();
  }catch(err){
   if(serial!==requestNumber)return;
   message("⚠ "+err.message+" Entre manuellement le poids et la durée pour continuer.");
  }finally{if(serial===requestNumber)busy(false)}
 }
 selector.addEventListener("change",estimate);
 material.addEventListener("change",()=>{if(selector.value)estimate()});
 layer.addEventListener("change",()=>{if(selector.value)estimate()});
 infill.addEventListener("change",()=>{if(selector.value)estimate()});
 fileInput.addEventListener("change",async()=>{
  const file=fileInput.files[0];
  if(!file)return;
  if(!/\.(stl|3mf)$/i.test(file.name)||file.size>8*1024*1024){
   message("Sélectionne un fichier STL ou 3MF d'au plus 8 Mo.");fileInput.value="";return;
  }
  const serial=++requestNumber;busy(true);
  message("Importation de « "+file.name+" » dans ta bibliothèque privée…");
  const body=new FormData();
  body.append("csrf",csrf.value);
  body.append("name",file.name.replace(/\.(stl|3mf)$/i,"").slice(0,120)||"Modèle importé");
  body.append("model",file,file.name);
  try{
   const response=await fetch("/admin/modeles/api/save",
                              {method:"POST",body,credentials:"same-origin"});
   const result=await response.json();
   if(!response.ok||!result.ok)throw Error(result.error||"Importation impossible.");
   if(serial!==requestNumber)return;
   const opt=new Option(file.name,result.id,true,true);
   opt.dataset.preview="";selector.add(opt);selector.value=String(result.id);
   const title=f.elements.namedItem("title");
   if(!title.value.trim())title.value=file.name.replace(/\.(stl|3mf)$/i,"");
   fileInput.value="";await estimate();
  }catch(err){
   if(serial!==requestNumber)return;
   message("⚠ "+err.message);
  }finally{if(serial===requestNumber)busy(false)}
 });
 updateImage();update();
 if(selector.value)estimate();
})();
</script>""",models=models,quotes=quotes,chosen=chosen,materials=MATERIALS,
          money=_money,csrf=csrfinput(),incoming=incoming,interac_email=interac_email)

    @app.post("/admin/soumissions-pro/paiement")
    @admin_required
    def fjord_interac_setup():
        verify()
        address=request.form.get("interac_email","").strip().lower()[:180]
        if address and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",address):
            abort(400,"Adresse Interac invalide.")
        with db() as c:
            c.execute("""INSERT INTO settings(key,value) VALUES('fjord_interac_email',%s)
              ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value""",(address,))
        flash("Paramètres Interac enregistrés. " +
              ("Les liens de paiement sont actifs." if address else "Le paiement Interac est désactivé."))
        return redirect("/admin/soumissions-pro")

    @app.post("/admin/soumissions-pro/estimer")
    @admin_required
    def fjord_quote_estimate():
        verify()
        from quote_estimator import estimate_model, EstimationError
        try:
            model_id=int(request.form.get("model_id",""))
            if model_id < 1:raise ValueError()
            layer=float(request.form.get("layer_height","0.2"))
            infill=int(request.form.get("infill","18"))
            material=request.form.get("material","PETG")
        except (TypeError, ValueError):
            return {"ok":False,"error":"Paramètres du modèle invalides."},400
        with db() as c:
            model=c.execute("SELECT filename,filedata FROM private_models WHERE id=%s",
                            (model_id,)).fetchone()
        if not model:return {"ok":False,"error":"Modèle introuvable."},404
        try:
            result=estimate_model(model["filedata"],model["filename"],material,layer,infill)
        except EstimationError as exc:
            return {"ok":False,"error":str(exc)},422
        return {"ok":True,**result}

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
                machine_hour,setup_cost,markup,payment_token)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",(customer,email,phone,title,description,material,
               int(quantity),unit,shipping,taxes,model_id,
               preview[1] if preview else None,preview[0] if preview else None,
               grams,hours,filament_kg,machine_hour,setup_cost,markup,
               secrets.token_urlsafe(32))).fetchone()
        flash("Soumission créée. Tu peux maintenant télécharger le PDF.")
        return redirect("/admin/soumissions-pro/"+str(result["id"])+"/pdf")

    @app.get("/admin/soumissions-pro/<int:quote_id>/paiement")
    @admin_required
    def fjord_admin_payment_link(quote_id):
        with db() as c:
            q=c.execute("SELECT id,payment_token FROM private_quotes WHERE id=%s",
                        (quote_id,)).fetchone()
            setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        if not q:abort(404)
        if not setting or not setting["value"]:
            flash("Configure d'abord ton adresse Interac.")
            return redirect("/admin/soumissions-pro")
        token=_quote_payment_token(db,q)
        if not token:abort(500)
        return redirect(url_for("fjord_payment_page",token=token))


    @app.get("/payer/<token>")
    def fjord_payment_page(token):
        # La page ne dévoile ni l'identité du client ni les paramètres internes.
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,90}",token):
            abort(404)
        with db() as c:
            q=c.execute("""SELECT id,quantity,unit_price,shipping,apply_taxes
                             FROM private_quotes WHERE payment_token=%s""",(token,)).fetchone()
            setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        if not q or not setting or not setting["value"]:
            abort(404)
        recipient=setting["value"]
        subtotal,gst,qst,total=_quote_amounts(q)
        reference="FJ-{:05d}".format(q["id"])
        response=make_response(page("Paiement Interac",r"""
<style>
.payment-wrap{max-width:660px;margin:30px auto}
.payment-wrap h1{font-size:clamp(28px,5vw,43px)}
.payment-total{font-size:clamp(30px,6vw,46px);font-weight:900;color:#7ee7ff;margin:7px 0 18px}
.payment-detail{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:15px 0}
.payment-detail strong{font-size:17px;overflow-wrap:anywhere}
.payment-detail button{font-size:14px;padding:9px 12px}
.payment-wrap .notice{font-size:13px;color:#b6d1e3}
body.light .payment-total{color:#076d9d}
</style>
<div class="payment-wrap"><div class="eyebrow">Les Impressions du Fjord</div>
<h1>💸 Payer par virement Interac</h1>
<p>Voici les informations pour payer ta soumission. Le paiement s'effectue dans l'application ou le site de ta banque, et non sur cette page.</p>
<section class="card">
<div>Montant total de la soumission, taxes comprises si applicables</div>
<div class="payment-total">{{amount}}</div>
<p>Ajoute Les Impressions du Fjord comme destinataire Interac dans ton application bancaire, puis effectue ton virement avec les renseignements suivants :</p>
<div class="payment-detail"><div>📧 Courriel du destinataire<br><strong id="payEmail">{{recipient}}</strong></div>
<button type="button" onclick="fjordCopy('payEmail',this)">Copier</button></div>
<div class="payment-detail"><div>🔖 Référence à inscrire dans le message<br><strong id="payRef">{{reference}}</strong></div>
<button type="button" onclick="fjordCopy('payRef',this)">Copier</button></div>
<div class="payment-detail"><div>💰 Montant du virement<br><strong id="payAmount">{{amount}}</strong></div>
<button type="button" onclick="fjordCopy('payAmount',this)">Copier</button></div>
<p class="notice">Vérifie le nom et le courriel du destinataire avant l'envoi. Une fois le virement envoyé, conserve ta confirmation bancaire. Ce site ne reçoit pas le paiement et ne peut pas confirmer automatiquement qu'il a été reçu.</p>
</section>
<p>Besoin d'aide? Communique avec Les Impressions du Fjord et mentionne {{reference}}.</p>
</div>
<script>
async function fjordCopy(id,button){
 const value=document.getElementById(id).textContent.trim();
 try{await navigator.clipboard.writeText(value);button.textContent="Copié ✓"}
 catch(e){button.textContent="Copie manuelle nécessaire"}
 setTimeout(()=>button.textContent="Copier",2200);
}
</script>""",amount=_money(total),reference=reference,recipient=recipient))
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Robots-Tag"]="noindex, nofollow, noarchive"
        response.headers["Referrer-Policy"]="no-referrer"
        return response


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
            interac_setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        if not q:abort(404)
        payment_url=None
        if interac_setting and interac_setting["value"]:
            token=_quote_payment_token(db,q)
            if token:
                payment_url=url_for("fjord_payment_page",token=token,_external=True)
        logo=None
        if setting:
            try:logo=base64.b64decode(setting["value"],validate=True)
            except Exception:logo=None
        if not logo:
            try:
                with open("static/fjord_logo.b64",encoding="ascii") as f:
                    logo=base64.b64decode(f.read().strip(),validate=True)
            except (OSError,ValueError):pass
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
        y=min(y-14,285 if payment_url else 250)
        rows=2+(1 if float(q["shipping"]) else 0)+(2 if q["apply_taxes"] else 0)
        if y-rows*25<(172 if payment_url else 115):
            pdf.showPage()
            y=710
        subtotal,gst,qst,total=_quote_amounts(q)
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
        if payment_url:
            # Lien web vérifiable : aucune demande Interac n'est envoyée par le site.
            if y<200:
                pdf.showPage()
                y=710
            top=y-5
            bottom=top-96
            pdf.setFillColor(colors.HexColor("#EBF7FE"))
            pdf.roundRect(39,bottom,w-78,96,10,stroke=0,fill=1)
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold",12)
            pdf.drawString(52,top-24,"PAYER PAR VIREMENT INTERAC")
            pdf.setFont("Helvetica",10)
            pdf.drawString(52,top-42,"Montant à transférer : "+_money(total).replace(" $"," CAD"))
            pdf.drawString(52,top-58,"Référence : FJ-{:05d}".format(q["id"]))
            pdf.setFillColor(cyan)
            pdf.roundRect(52,bottom+10,340,23,6,stroke=0,fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold",10)
            pdf.drawCentredString(222,bottom+18,"CLIQUEZ POUR LES INSTRUCTIONS DE PAIEMENT")
            pdf.linkURL(payment_url,(52,bottom+10,392,bottom+33),relative=0)
            try:
                from reportlab.graphics.barcode import qr
                from reportlab.graphics.shapes import Drawing
                from reportlab.graphics import renderPDF
                widget=qr.QrCodeWidget(payment_url)
                x1,y1,x2,y2=widget.getBounds()
                size=78
                graphic=Drawing(size,size,transform=[size/(x2-x1),0,0,size/(y2-y1),0,0])
                graphic.add(widget)
                renderPDF.draw(graphic,pdf,w-131,bottom+9)
            except Exception:
                # Le bouton PDF demeure utilisable même si le rendu QR est indisponible.
                pass
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
