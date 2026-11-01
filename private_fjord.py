"""Fonctions privées de Les Impressions du Fjord.
Les données de coûts et les fichiers ne sont jamais exposés par les routes publiques.
"""
import base64
import datetime
import hashlib
import io
import json
import math
import re
import secrets
from decimal import Decimal, ROUND_HALF_UP

from flask import abort, flash, make_response, redirect, render_template_string, request, send_file, url_for
from werkzeug.utils import secure_filename
from model_preview import make_model_preview

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

def _quote_military_discount(q):
    """Rabais militaire facultatif de 5 % sur les articles, hors livraison et taxes."""
    merchandise = round(float(q["unit_price"]) * int(q["quantity"]), 2)
    if not q.get("military_discount"):
        return 0.0
    amount = (Decimal(str(merchandise)) * Decimal("0.05")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(amount)


def _quote_amounts(q):
    """Calcul unique du prix net, des taxes et du total partout sur le site."""
    merchandise = round(float(q["unit_price"]) * int(q["quantity"]), 2)
    subtotal = round(merchandise - _quote_military_discount(q) + float(q["shipping"]), 2)
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
    button = '<button type="button" id="fjordPrivateImport">📚 Importer de ma bibliothèque</button><button type="button" class="primary" id="fjordPrivateSave">💾 Enregistrer dans ma bibliothèque</button><a href="/admin/modeles">Voir mes modèles</a><a href="/admin/profils-bambu" title="Importer ou consulter les paramètres Bambu Studio">⚙️ Mes profils Bambu</a>'
    html = html.replace('<button id="export" data-i18n="export">', button + '<button id="export" data-i18n="export">', 1)
    # Always-visible shortcut on desktop AND mobile, independent of the
    # collapsible "Projet" menu. This HTML is served only to authenticated admins.
    admin_shortcut = (
        '<a id="fjordAdminShortcut" href="/admin" '
        'title="Retour au tableau de bord administrateur" '
        'style="display:inline-flex;align-items:center;justify-content:center;'
        'min-height:40px;padding:8px 12px;border-radius:9px;'
        'border:1px solid #67b0d9;background:#11577e;color:#fff;'
        'font-size:13px;font-weight:750;white-space:nowrap;text-decoration:none">'
        '⚙️ Administration</a>'
    )
    html = html.replace('<div class="top-preferences">', '<div class="top-preferences">' + admin_shortcut, 1)
    print_shortcut = (
        '<a id="fjordPrintShortcut" href="/admin/atelier-imprimer" '
        'title="Envoyer un fichier 3MF tranché et imprimer sur ma X2D" '
        'style="display:inline-flex;align-items:center;justify-content:center;'
        'min-height:40px;padding:8px 12px;border-radius:9px;'
        'border:1px solid #68c4a4;background:#115f4e;color:#fff;'
        'font-size:13px;font-weight:750;white-space:nowrap;text-decoration:none">'
        '🖨️ Imprimer sur ma X2D</a>'
    )
    html = html.replace('<div class="top-preferences">', '<div class="top-preferences">' + print_shortcut, 1)
    # Shorten the two long library labels without changing their IDs/actions.
    html = html.replace('📚 Importer de ma bibliothèque</button>',
                        '📚 Importer bibliothèque</button>', 1)
    html = html.replace('💾 Enregistrer dans ma bibliothèque</button>',
                        '💾 Sauver bibliothèque</button>', 1)
    # Reorganize only the private Atelier header; keep every original button
    # and its ID so all existing actions and keyboard shortcuts remain intact.
    import re as _re
    menu = _re.search(
        r'(<div id="projectMenu" class="project-menu"><button[^>]*id="projectMenuButton"[^>]*>.*?</button><div class="top-actions">)(.*?)(</div></div>)',
        html, _re.S
    )
    if menu:
        controls = _re.findall(r'<(?:button|a)\b[^>]*>.*?</(?:button|a)>',
                               menu.group(2), _re.S)
        by_id = {}
        for control in controls:
            mid = _re.search(r'\bid="([^"]+)"', control)
            href = _re.search(r'\bhref="([^"]+)"', control)
            key = mid.group(1) if mid else (href.group(1) if href else None)
            if key:
                by_id[key] = control
        def take(ids):
            return ''.join(by_id.pop(key, '') for key in ids)

        primary = take(("new", "import", "save", "fjordPrivateImport",
                        "fjordPrivateSave", "sliceTop", "quote"))
        secondary = take(("open", "export", "exportColor3MF", "estimateToggle",
                          "/admin/modeles", "/admin/profils-bambu", "/"))
        secondary += '<a id="fjordPublicAtelierShortcut" href="/atelier-3d" title="Ouvrir la version publique sans les outils privés">👁 Voir le mode public</a>'
        secondary += ''.join(by_id.values())
        compact = (
            '<div class="fjord-admin-core" role="group" aria-label="Actions principales">' +
            primary + '</div>' +
            '<details class="fjord-admin-more"><summary>⋯ Plus</summary>' +
            '<div class="fjord-admin-more-menu">' + secondary + '</div></details>'
        )
        html = html[:menu.start(2)] + compact + html[menu.end(2):]
        html = html.replace('<button id="quote" class="primary" data-i18n="quote">Faire imprimer</button>',
                            '<button id="quote" class="primary" title="Créer une soumission depuis le plateau">💰 Soumission PRO</button>', 1)
        html = html.replace(print_shortcut, '', 1).replace(admin_shortcut, '', 1)
        html = html.replace('<div class="top-preferences">',
                            '<div class="fjord-admin-links" aria-label="Accès privé">' +
                            admin_shortcut +
                            '</div><div class="top-preferences">', 1)
        # Print controls belong to the Slice panel, not the crowded header.
        slice_entry = (
            '<div class="fjord-slice-print-entry" role="group" aria-label="Impression X2D">'
            + print_shortcut
            + '<button type="button" id="fjordQuoteFromSlice" class="fjord-quote-from-slice">💰 Créer une soumission PRO</button>'
            + '<button type="button" hidden id="fjordAutoPrintLauncher" '
              'title="Préparer le tranchage Bambu Studio sur ma X2D"></button>'
            + '<p>Aperçu du plateau ci-dessus : estimation. '
              'Pour préparer le vrai G-code Bambu, clique sur Imprimer sur ma X2D, '
              'examine les couches et confirme l’envoi avant le démarrage.</p>'
            + '</div>'
        )
        slice_location = '</div>\n</section>\n<div id="cutFloat"'
        if slice_location not in html:
            raise ValueError('Emplacement du bouton X2D dans le tranchage introuvable')
        html = html.replace(slice_location, '</div>\n' + slice_entry +
                            '\n</section>\n<div id="cutFloat"', 1)
        html = html.replace('<header>\n<div><div class="brand">🏔️ Atelier 3D du Fjord',
                            '<header class="fjord-admin-header">\n<div class="fjord-admin-brand">'
                            '<div class="brand">🏔️ Atelier 3D du Fjord', 1)
        html = html.replace(
            '<div class="brand">🏔️ Atelier 3D du Fjord</div>',
            '<div class="brand">🏔️ Atelier 3D du Fjord</div>'
            '<span id="fjordAdminModeBanner" role="status" class="fjord-admin-mode-badge" '
            'aria-label="Mode administrateur actif">🔒 ADMINISTRATEUR</span>', 1)
        html = html.replace('</head>',
                            '<link rel="stylesheet" href="/static/atelier_admin_header.css">'
                            '</head>', 1)
        html = html.replace('</body>', """<script>
(function(){
  const menu=document.querySelector('.fjord-admin-more');
  if(!menu)return;
  document.addEventListener('pointerdown',event=>{
    if(!menu.contains(event.target))menu.open=false;
  });
  menu.querySelector('.fjord-admin-more-menu')?.addEventListener('click',event=>{
    if(event.target.closest('button,a'))menu.open=false;
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape')menu.open=false;
  });
})();
</script></body>""", 1)
    injection = r"""
// Sauvegarde privee et creation directe de soumissions depuis l'Atelier.
const privateSaveBtn=document.getElementById("fjordPrivateSave");
const fjordQuoteButton=document.getElementById("quote");
const fjordSliceQuoteButton=document.getElementById("fjordQuoteFromSlice");
let fjordSavingQuote=false;
async function fjordSaveStudioModel(forQuote,button){
 if(fjordSavingQuote)return;
 if(!models.length){alert("Ajoute au moins une piece au plateau.");return;}
 const suggestion=models.length===1?models[0].name:"Projet 3D du Fjord";
 const name=prompt(forQuote?"Nom de la creation pour la soumission :":"Nom du modele a sauvegarder :",suggestion)?.trim().slice(0,120);
 if(!name)return;
 fjordSavingQuote=true;
 const buttons=[privateSaveBtn,fjordQuoteButton,fjordSliceQuoteButton].filter(Boolean);
 const oldNames=buttons.map(b=>b.textContent);
 buttons.forEach(b=>b.disabled=true);
 if(button)button.textContent="Preparation du modele…";
 try{
  let blob=null,filename="Creation-du-Fjord.stl",colored=false;
  if(forQuote){
   try{
    const result=makeColored3MF(THREE,models);
    if(result.blob.size<=8*1024*1024){blob=result.blob;filename="Creation-du-Fjord-couleurs.3mf";colored=true}
    else if(!confirm("Le 3MF avec couleurs depasse 8 Mo. Continuer avec STL (sans couleurs AMS, mais photo conservee)?"))return;
   }catch(error){
    if(!confirm("Le 3MF en couleurs ne peut pas etre produit : "+String(error?.message||error)+
      ". Continuer avec STL (sans couleurs AMS, mais photo conservee)?"))return;
   }
  }
  if(!blob){
   const group=new THREE.Group();
   models.forEach(m=>{const c=m.clone();c.geometry=m.geometry;c.material=m.material;group.add(c)});
   blob=new Blob([new STLExporter().parse(group,{binary:true})],{type:"model/stl"});
  }
  if(!blob.size||blob.size>8*1024*1024)throw Error("Fichier trop volumineux (maximum 8 Mo).");
  // Image professionnelle : seulement les pieces et les lumieres.
  // Le plateau, le logo sous la piece, les guides et la selection sont caches.
  const hidden=[];
  for(const item of scene.children){
   if(models.includes(item)||item.isLight||!item.visible)continue;
   hidden.push(item);item.visible=false;
  }
  const selectedGlow=[...selectedSet].filter(m=>m.userData.selectionOriginalColor!==undefined);
  selectedGlow.forEach(removeSelectionTint);
  const oldCamera=camera.position.clone(),oldTarget=orbit.target.clone();
  const oldBackground=scene.background.clone();
  let imageData;
  try{
   const bounds=new THREE.Box3();
   models.forEach(model=>bounds.expandByObject(model));
   const center=bounds.getCenter(new THREE.Vector3());
   const span=bounds.getSize(new THREE.Vector3()).length();
   const direction=oldCamera.clone().sub(oldTarget).normalize();
   if(Number.isFinite(span)&&span>0&&direction.lengthSq()>.001){
    camera.position.copy(center).addScaledVector(direction,Math.max(70,span*1.8));
    orbit.target.copy(center);camera.lookAt(center);
   }
   scene.background.set(0x172333);
   renderer.render(scene,camera);
   imageData=renderer.domElement.toDataURL("image/png");
  }catch(error){console.warn("Photo du modele 3D indisponible",error)}
  finally{
   camera.position.copy(oldCamera);orbit.target.copy(oldTarget);
   camera.lookAt(oldTarget);scene.background.copy(oldBackground);
   hidden.forEach(item=>item.visible=true);
   selectedGlow.forEach(addSelectionTint);
   renderer.render(scene,camera);
  }
  const form=new FormData();
  form.append("csrf",__FJORD_CSRF__);form.append("name",name);
  form.append("model",blob,filename);
  if(forQuote)form.append("skip_duplicates","yes");
  if(imageData?.startsWith("data:image/png;base64,")){
   try{
    const image=await(await fetch(imageData)).blob();
    if(image.size<4*1024*1024)form.append("preview",image,"apercu-atelier.png");
   }catch(error){console.warn("Photo indisponible",error)}
  }
  if(button)button.textContent="Enregistrement…";
  const response=await fetch("/admin/modeles/api/save",{method:"POST",body:form,
     credentials:"same-origin",headers:{"Accept":"application/json"}});
  if(!(response.headers.get("content-type")||"").includes("application/json"))
   throw Error("Reconnecte-toi : la session administrateur a expire.");
  const result=await response.json();
  if(!response.ok||!result.ok||!Number.isSafeInteger(Number(result.id))||Number(result.id)<1)
   throw Error(result.error||"Enregistrement impossible.");
  if(forQuote){
   const params=new URLSearchParams({model_id:String(result.id),atelier:"1",colors:colored?"3mf":"stl"});
   const material=document.getElementById("sliceMaterial")?.value||
     document.getElementById("estimateMaterial")?.value||"PETG";
   const layer=document.getElementById("sliceLayerHeight")?.value||"0.2";
   if(["PLA","PETG","PETG-CF","ASA","TPU","Autre"].includes(material))params.set("material",material);
   if(["0.08","0.12","0.2","0.28"].includes(layer))params.set("layer",layer);
   location.assign("/admin/soumissions-pro?"+params+"#fjQuote");
  }else if(confirm("Modele enregistre! Preparer une soumission maintenant?")){
   location.assign("/admin/soumissions-pro?model_id="+encodeURIComponent(result.id)+"#fjQuote");
  }else location.assign("/admin/modeles");
 }catch(error){alert("Erreur : "+String(error.message||error))}
 finally{fjordSavingQuote=false;buttons.forEach((b,i)=>{b.disabled=false;b.textContent=oldNames[i]})}
}
privateSaveBtn?.addEventListener("click",()=>fjordSaveStudioModel(false,privateSaveBtn));
// Le bouton public Faire imprimer existe deja : interception avant son action.
fjordQuoteButton?.addEventListener("click",event=>{
 event.preventDefault();event.stopImmediatePropagation();fjordSaveStudioModel(true,fjordQuoteButton);
},true);
fjordSliceQuoteButton?.addEventListener("click",()=>fjordSaveStudioModel(true,fjordSliceQuoteButton));
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

    auto_print_launcher = r"""
// Impression privée de la création visible du plateau, uniquement en PLA/PETG
// ou autre filament unique. Pas de conversion trompeuse des couleurs AMS en STL.
const fjordAutoButton=document.getElementById('fjordAutoPrintLauncher');
if(fjordAutoButton){
 const green=document.getElementById('fjordPrintShortcut');
 green?.addEventListener('click',event=>{
  if(!models.length)return; // Empty bed: keep the beloved manual print page.
  event.preventDefault();fjordAutoButton.click();
 });
 const panel=document.createElement('dialog');
 panel.id='fjordAutoPrintDialog';
 panel.setAttribute('aria-label','Préparer l’impression X2D depuis l’Atelier');
 panel.innerHTML='<div class="fjord-dialog-head"><strong>🖨️ Ma X2D · Préparation automatique</strong><button type="button" id="fjordAutoClose">✕</button></div>'+
 '<p class="fjord-auto-intro">Pour ce premier essai, utilise les profils d’origine Bambu Studio. Tes profils CHATOU personnalisés restent disponibles dans les listes.</p>'+
 '<p class="fjord-auto-stock-note">✓ X2D 0,4 mm · 0,20 mm Standard · Generic PETG (ou autre matériau sélectionné). Confirme ta plaque et ta bobine avant d’imprimer.</p>'+
 '<p id="fjordAutoState" role="status" aria-live="polite">Vérification de la configuration…</p>'+
 '<form id="fjordAutoForm"><label>Imprimante X2D<select name="machine" required></select></label>'+
 '<label>Profil d’impression<select name="process" required></select></label>'+
 '<label>Filament<select name="filament" required></select></label>'+
 '<label>Type de plaque installé sur la X2D<select name="bed_type" required>'+
 '<option value="">— Choisir la plaque réelle —</option>'+
 '<option value="Textured PEI Plate">PEI texturé</option>'+
 '<option value="Smooth PEI Plate / High Temp Plate">PEI lisse / haute température</option>'+
 '<option value="Engineering Plate">Engineering Plate</option>'+
 '<option value="Cool Plate SuperTack">Cool Plate SuperTack</option>'+
 '<option value="Cool Plate">Cool Plate (certains filaments incompatibles)</option>'+
 '</select></label>'+
 '<section id="fjordMonoApproval" class="fjord-mono-approval" hidden>'+
 '<strong>🎨 Plusieurs couleurs détectées sur ta création.</strong>'+
 '<p>Le STL ne conserve pas la peinture AMS. Pour vérifier le tranchage, tu peux envoyer seulement la géométrie en <b>une couleur PETG</b>. Ta création peinte restera inchangée dans l’Atelier.</p>'+
 '<label class="fjord-auto-remember"><input type="checkbox" id="fjordMonoConsent"> Je confirme : pour cet essai, trancher en UNE couleur, sans peinture ni couleurs AMS.</label>'+
 '</section>'+
 '<label class="fjord-auto-remember"><input type="checkbox" id="fjordAutoRemember" checked> Mémoriser ces profils après une préparation réussie</label>'+
 '<button id="fjordAutoSubmit" type="submit" disabled>▥ Trancher et voir les couches</button></form>'+
 '<section id="fjordSliceReview" tabindex="-1" hidden aria-label="Aperçu des couches réellement tranchées">'+
 '<h3>▤ Résultat du tranchage Bambu Studio</h3>'+
 '<p>Examine les trajectoires du G-code du 3MF, couche par couche, avant de l’envoyer à la X2D.</p>'+
 '<div class="fjord-review-preview"><canvas id="fjordReviewCanvas" width="420" height="420" role="img" aria-label="Vue pivotable en 3D du G-code tranché, un doigt pour tourner et deux doigts pour zoomer ou déplacer."></canvas>'+
 '<button type="button" class="fjord-review-mode" id="fjordReview3DToggle" aria-pressed="true">◈ 3D</button>'+
 '<div class="fjord-review-zoom" role="group" aria-label="Zoom de l’aperçu"><button type="button" id="fjordReviewZoomOut" aria-label="Dézoomer">−</button><button type="button" id="fjordReviewFit" aria-label="Recentrer et ajuster le zoom">⌗</button><button type="button" id="fjordReviewZoomIn" aria-label="Agrandir">+</button></div></div>'+
 '<p class="fjord-review-gesture" id="fjordReviewGesture">Un doigt : pivoter · deux doigts : zoomer et déplacer · bouton 3D/2D.</p>'+
 '<label for="fjordReviewLayer">Couche <strong id="fjordReviewLabel">—</strong></label>'+
 '<div class="fjord-review-layerbar"><button type="button" id="fjordReviewPrevious" aria-label="Couche précédente">◀</button><input id="fjordReviewLayer" type="range" min="0" max="0" value="0" step="1"><button type="button" id="fjordReviewNext" aria-label="Couche suivante">▶</button></div>'+
 '<label class="fjord-auto-remember"><input id="fjordReviewAccumulated" type="checkbox"> Afficher les couches précédentes</label>'+
 '<p id="fjordReviewSummary" role="status"></p>'+
 '<div class="fjord-review-facts" aria-label="Résultats réels du tranchage">'+
 '<div><span>Durée Bambu</span><strong id="fjordReviewTime">—</strong></div>'+
 '<div><span>Filament Bambu</span><strong id="fjordReviewWeight">—</strong></div>'+
 '<div><span>Nombre de couches</span><strong id="fjordReviewCount">—</strong></div>'+
 '</div>'+
 '<div class="fjord-review-price"><span>Prix estimé avant taxes <small>(CAD)</small></span><strong id="fjordReviewPrice">—</strong>'+
 '<p id="fjordReviewPriceNote">Calcul à partir des valeurs du véritable 3MF Bambu Studio et des tarifs configurés.</p></div>'+
 '<details class="fjord-review-pricing"><summary>⚙️ Ajuster le calcul du prix</summary>'+
 '<div class="fjord-review-rategrid">'+
 '<label>Filament ($/kg)<input type="number" id="fjordReviewKgRate" min="0" max="1000" step=".5" value="32"></label>'+
 '<label>Machine ($/h)<input type="number" id="fjordReviewHourRate" min="0" max="1000" step=".5" value="3"></label>'+
 '<label>Préparation ($)<input type="number" id="fjordReviewSetupRate" min="0" max="10000" step=".5" value="8"></label>'+
 '<label>Majoration (%)<input type="number" id="fjordReviewMarkup" min="0" max="500" step="1" value="25"></label>'+
 '</div><p id="fjordReviewBreakdown" aria-live="polite"></p></details>'+
 '<p class="fjord-review-note">Aperçu des trajectoires réelles, éventuellement échantillonnées pour la fluidité. Pour les détails critiques, vérifie aussi dans Bambu Studio. Aucun fichier transmis.</p>'+
 '<button type="button" class="fjord-auto-send" id="fjordReviewTransfer">📤 Envoyer le 3MF tranché à ma X2D</button>'+
 '<button type="button" id="fjordReviewDownload">⬇ Télécharger le 3MF tranché (Bambu Studio)</button>'+
 '<button type="button" id="fjordReviewDiagnostic">🔎 Diagnostiquer le transfert X2D (journal FTPS)</button>'+
 '<p id="fjordReviewDiagnosticResult" role="status" aria-live="polite" hidden></p>'+
 '<button type="button" id="fjordReviewRedo">↺ Modifier et retrancher</button></section>'+
 '<section id="fjordStartAtelier" hidden aria-label="Imprimer directement depuis l’Atelier">'+
 '<h3>🖨️ Mon 3MF est sur la X2D</h3><p id="fjordStartFile"></p>'+
 '<div class="fjord-printer-state"><strong>État de ma X2D</strong><span id="fjordLiveState">Connexion…</span>'+
 '<progress id="fjordLiveProgress" value="0" max="100" hidden></progress>'+
 '<button type="button" id="fjordRefreshPrinter">↻ Actualiser l’état</button></div>'+
 '<p>Vérifie les conditions avant de démarrer physiquement ta X2D.</p>'+
 '<label class="fjord-auto-remember"><input type="checkbox" id="fjordStartAMS" checked> Utiliser l’AMS</label>'+
 '<label class="fjord-auto-remember"><input type="checkbox" id="fjordStartVerified"> J’ai vérifié le matériau, les bobines AMS, la plaque et le tranchage.</label>'+
 '<label class="fjord-auto-remember"><input type="checkbox" id="fjordStartCleared"> Le plateau est libre, la X2D est prête et je peux surveiller la première couche.</label>'+
 '<button type="button" id="fjordStartNow" disabled>▶ Démarrer l’impression sur ma X2D</button>'+
 '<p id="fjordStartResult" role="status" aria-live="polite"></p>'+
 '<p class="fjord-review-note">Une commande acceptée ne prouve pas que la première couche a commencé. Vérifie la X2D.</p>'+
 '<button type="button" id="fjordStartAnother">↺ Préparer une autre impression</button></section>'+
 '<p><a href="/admin/profils-bambu">⚙️ Vérifier mes profils</a> · <a href="/admin/atelier-imprimer">Page d’impression classique</a></p>';
 document.body.append(panel);
 const state=panel.querySelector('#fjordAutoState');
 const form=panel.querySelector('#fjordAutoForm');
 const submit=panel.querySelector('#fjordAutoSubmit');
 const remember=panel.querySelector('#fjordAutoRemember');
 const monoWrap=panel.querySelector('#fjordMonoApproval');
 const monoConsent=panel.querySelector('#fjordMonoConsent');
 const names={machine:'Imprimante',process:'Impression',filament:'Filament'};
 const preferenceKey='fjord-x2d-profile-preferences-v1';
 let inventory=null,busy=false,opened=false,prepared=null,transferred=null,printerCanStart=false,printerPoll=null;
 const review=panel.querySelector('#fjordSliceReview');
 const transfer=panel.querySelector('#fjordReviewTransfer');
 const slider=panel.querySelector('#fjordReviewLayer');
 const startScreen=panel.querySelector('#fjordStartAtelier');
 const startNow=panel.querySelector('#fjordStartNow');
 const startMessage=panel.querySelector('#fjordStartResult');
 const liveState=panel.querySelector('#fjordLiveState');
 const liveProgress=panel.querySelector('#fjordLiveProgress');
 const safetyVerified=panel.querySelector('#fjordStartVerified');
 const safetyCleared=panel.querySelector('#fjordStartCleared');
 function refreshStartButton(){
  startNow.disabled=busy||!transferred||!printerCanStart||
    !safetyVerified.checked||!safetyCleared.checked;
 }
 [safetyVerified,safetyCleared].forEach(item=>item.addEventListener('change',refreshStartButton));
 function clearPrintScreen(){
  transferred=null;printerCanStart=false;startScreen.hidden=true;
  panel.classList.remove('fjord-print-ready');
  safetyVerified.checked=false;safetyCleared.checked=false;
  startMessage.textContent='';startNow.disabled=true;
 }
 async function refreshPrinter(){
  // Continue reporting printer state after /start, without re-enabling start.
  if(!transferred&&!startScreen.classList.contains('fjord-start-sent'))return;
  try{
   const response=await fetch('/api/admin/atelier/impression-etat',{
    credentials:'same-origin',cache:'no-store'
   });
   if(!response.ok)throw Error('La X2D ne répond pas.');
   const data=await response.json();
   if(!data.ok)throw Error(data.error||'Statut indisponible.');
   printerCanStart=data.can_start===true;
   const states={idle:'Prête',printing:'Impression en cours',paused:'En pause',
     complete:'Terminée',cancelled:'Annulée'};
   liveState.textContent=(states[data.state]||data.state||'Inconnu')+
       (data.file?' · '+data.file:'');
   const progress=Number(data.progress);
   liveProgress.hidden=!(Number.isFinite(progress)&&data.progress!==null);
   if(!liveProgress.hidden)liveProgress.value=Math.max(0,Math.min(100,progress));
  }catch(error){
   printerCanStart=false;liveState.textContent='⚠ '+String(error.message||error).slice(0,140);
   liveProgress.hidden=true;
  }
  refreshStartButton();
 }
 panel.querySelector('#fjordRefreshPrinter').addEventListener('click',refreshPrinter);
 function stopPrinterPolling(){
  if(printerPoll!==null){clearInterval(printerPoll);printerPoll=null;}
 }
 function beginPrinterPolling(){
  stopPrinterPolling();refreshPrinter();
  printerPoll=setInterval(()=>{if(panel.open)refreshPrinter();},10000);
 }
 panel.querySelector('#fjordStartAnother').addEventListener('click',()=>{
  stopPrinterPolling();clearPrintScreen();invalidatePreview();
  state.textContent='Ajoute une nouvelle pièce ou retranche celle-ci.';
 });
 startNow.addEventListener('click',async()=>{
  if(busy||!transferred||!printerCanStart||!safetyVerified.checked||!safetyCleared.checked)return;
  if(!confirm('DÉMARRER réellement ce 3MF sur ma X2D ? Vérifie le plateau, la bonne bobine et la première couche.'))return;
  const chosen=transferred;busy=true;refreshStartButton();
  startMessage.textContent='Commande de démarrage envoyée à la X2D…';
  try{
   const body=new FormData();
   body.append('csrf',__FJORD_CSRF__);
   body.append('nonce',chosen.nonce);
   body.append('verified','yes');
   body.append('cleared','yes');
   body.append('ams',panel.querySelector('#fjordStartAMS').checked?'yes':'no');
   const response=await fetch('/admin/atelier-imprimer/demarrer-atelier',{
    method:'POST',body,credentials:'same-origin',headers:{Accept:'application/json'}
   });
   if(!(response.headers.get('content-type')||'').includes('application/json'))
    throw Error('Ta session administrateur a expiré.');
   const result=await response.json();
   if(!response.ok||!result.ok)throw Error(result.error||'La X2D a refusé le démarrage.');
   transferred=null;printerCanStart=false;
   startScreen.classList.add('fjord-start-sent');
   startMessage.textContent='✓ '+result.message;
   stopPrinterPolling();beginPrinterPolling();
  }catch(error){
   // The one-use server nonce is consumed regardless of the result.
   transferred=null;printerCanStart=false;stopPrinterPolling();
   startMessage.textContent='⚠ '+String(error.message||error)+
     ' · Vérifie l’imprimante avant de retenter; un nouvel envoi sera nécessaire.';
  }finally{busy=false;refreshStartButton();}
 });
 panel.addEventListener('close',stopPrinterPolling);

 let reviewZoom=1,reviewPanX=0,reviewPanY=0;
 let review3D=true,reviewYaw=-.6,reviewPitch=.7;
 const reviewTouches=new Map();
 const reviewCanvas=panel.querySelector('#fjordReviewCanvas');
 const moneyReview=new Intl.NumberFormat('fr-CA',{style:'currency',currency:'CAD'});
 function invalidatePreview(){
  prepared=null;
  review.hidden=true;
  panel.classList.remove('fjord-preview-active');
  transfer.disabled=true;
  reviewZoom=1;reviewPanX=reviewPanY=0;
 }
 function refreshReviewPrice(){
  if(!prepared)return;
  const p=prepared.preview;
  const secs=Number(p.estimated_seconds),grams=Number(p.filament_grams);
  const validTime=Number.isFinite(secs)&&secs>0;
  const validWeight=Number.isFinite(grams)&&grams>0;
  const duration=validTime?Math.floor(secs/3600)+' h '+Math.round((secs%3600)/60)+' min':'—';
  panel.querySelector('#fjordReviewTime').textContent=duration;
  panel.querySelector('#fjordReviewWeight').textContent=validWeight?grams.toLocaleString('fr-CA',{maximumFractionDigits:1})+' g':'—';
  panel.querySelector('#fjordReviewCount').textContent=String(p.layer_count||p.layers.length);
  const price=panel.querySelector('#fjordReviewPrice');
  const note=panel.querySelector('#fjordReviewPriceNote');
  const breakdown=panel.querySelector('#fjordReviewBreakdown');
  if(!validTime||!validWeight){
   price.textContent='—';
   note.textContent='Durée ou poids non disponible dans le 3MF Bambu. Prix non calculé, pour éviter une estimation trompeuse.';
   breakdown.textContent='Vérifie les informations du 3MF dans Bambu Studio.';
   return;
  }
  const rates=['fjordReviewKgRate','fjordReviewHourRate','fjordReviewSetupRate','fjordReviewMarkup']
     .map(id=>Number(panel.querySelector('#'+id).value));
  if(rates.some(v=>!Number.isFinite(v)||v<0)||rates[3]>500||rates[0]>1000||rates[1]>1000||rates[2]>10000){
   price.textContent='—';note.textContent='Vérifie les tarifs saisis.';breakdown.textContent='';return;
  }
  const materialCost=grams/1000*rates[0]*1.10;
  const machineCost=secs/3600*rates[1];
  const subtotal=materialCost+machineCost+rates[2];
  const total=subtotal*(1+rates[3]/100);
  price.textContent=moneyReview.format(total);
  note.textContent='Avant taxes · indicatif · temps et poids du vrai 3MF Bambu Studio · perte de filament +10 %.';
  breakdown.textContent='Filament et perte : '+moneyReview.format(materialCost)+' · Machine : '+
   moneyReview.format(machineCost)+' · Préparation : '+moneyReview.format(rates[2])+
   ' · Majoration : '+rates[3].toLocaleString('fr-CA')+' %.';
 }
 for(const id of ['fjordReviewKgRate','fjordReviewHourRate','fjordReviewSetupRate','fjordReviewMarkup']){
  panel.querySelector('#'+id).addEventListener('input',refreshReviewPrice);
 }
 function drawBambuReview(){
  if(!prepared)return;
  const layers=prepared.preview.layers;
  const index=Math.min(layers.length-1,Math.max(0,Number(slider.value)||0));
  const canvas=reviewCanvas,ctx=canvas.getContext('2d');
  if(!ctx)return;
  ctx.fillStyle='#101c29';ctx.fillRect(0,0,canvas.width,canvas.height);
  const accumulated=panel.querySelector('#fjordReviewAccumulated').checked;
  const shown=accumulated?layers.slice(0,index+1):[layers[index]];
  if(review3D){
   // Project the real XYZ G-code extrusion paths. This is a 3D toolpath
   // visualization, not a fabricated watertight shaded model.
   let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
   for(const layer of shown)for(const seg of layer.segments||[]){
    minX=Math.min(minX,seg[0],seg[2]);maxX=Math.max(maxX,seg[0],seg[2]);
    minY=Math.min(minY,seg[1],seg[3]);maxY=Math.max(maxY,seg[1],seg[3]);
   }
   if(!Number.isFinite(minX)){minX=105;maxX=120;minY=105;maxY=120;}
   const minZ=Number(shown[0].z)||0,maxZ=Number(shown[shown.length-1].z)||0;
   const centreX=(minX+maxX)/2,centreY=(minY+maxY)/2,centreZ=(minZ+maxZ)/2;
   const span=Math.max(10,maxX-minX,maxY-minY,(maxZ-minZ)*1.4);
   const scale=canvas.width*.59/span*reviewZoom;
   const cy=Math.cos(reviewYaw),sy=Math.sin(reviewYaw);
   const cp=Math.cos(reviewPitch),sp=Math.sin(reviewPitch);
   const project=(x,y,z)=>{
    const dx=x-centreX,dy=y-centreY,dz=z-centreZ;
    const xx=dx*cy-dy*sy,yy=dx*sy+dy*cy;
    return [canvas.width/2+xx*scale+reviewPanX,
      canvas.height/2+(-yy*cp-dz*sp)*scale+reviewPanY];
   };
   const pad=Math.max(3,span*.15);
   ctx.strokeStyle='#38546a';ctx.lineWidth=.65;
   for(let i=0;i<=6;i++){
    const x=minX-pad+(maxX-minX+2*pad)*i/6;
    const y=minY-pad+(maxY-minY+2*pad)*i/6;
    let a=project(x,minY-pad,0),b=project(x,maxY+pad,0);
    ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
    a=project(minX-pad,y,0);b=project(maxX+pad,y,0);
    ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
   }
   for(let i=0;i<shown.length;i++){
    const layer=shown[i],segments=layer.segments||[];
    ctx.strokeStyle=i===shown.length-1?'#ffa857':'#568caa';
    ctx.globalAlpha=i===shown.length-1?1:.65;
    ctx.lineWidth=i===shown.length-1?1.4:1;
    ctx.beginPath();
    const step=Math.max(1,Math.ceil(segments.length/1200));
    for(let j=0;j<segments.length;j+=step){
     const seg=segments[j],a=project(seg[0],seg[1],Number(layer.z)||0),
       b=project(seg[2],seg[3],Number(layer.z)||0);
     ctx.moveTo(...a);ctx.lineTo(...b);
    }
    ctx.stroke();
   }
   ctx.globalAlpha=1;
  }else{
   const side=Math.min(canvas.width,canvas.height)-38;
   const tx=x=>canvas.width/2+(19+(x/256)*side-canvas.width/2)*reviewZoom+reviewPanX;
   const ty=y=>canvas.height/2+(canvas.height-19-(y/256)*side-canvas.height/2)*reviewZoom+reviewPanY;
   ctx.strokeStyle='#365064';ctx.lineWidth=.7;
   for(let mm=0;mm<=256;mm+=32){
    ctx.beginPath();ctx.moveTo(tx(mm),ty(0));ctx.lineTo(tx(mm),ty(256));ctx.stroke();
    ctx.beginPath();ctx.moveTo(tx(0),ty(mm));ctx.lineTo(tx(256),ty(mm));ctx.stroke();
   }
   for(let i=0;i<shown.length;i++){
    const layer=shown[i];
    ctx.strokeStyle=i===shown.length-1?'#ffa857':'#47738d';
    ctx.lineWidth=i===shown.length-1?1.3:.7;
    ctx.beginPath();
    for(const segment of layer.segments||[]){
     ctx.moveTo(tx(segment[0]),ty(segment[1]));
     ctx.lineTo(tx(segment[2]),ty(segment[3]));
    }
    ctx.stroke();
   }
  }
  const active=layers[index];
  panel.querySelector('#fjordReviewLabel').textContent=
   (index+1)+' / '+layers.length+' · Z '+Number(active.z).toFixed(2)+' mm';
  panel.querySelector('#fjordReviewSummary').textContent=
   active.moves.toLocaleString('fr-CA')+' mouvements extrudés sur cette couche · '+
   prepared.preview.total_moves.toLocaleString('fr-CA')+' au total'+
   (prepared.preview.sampled?' · tracé partiellement échantillonné':'');
  refreshReviewPrice();
 }
 slider.addEventListener('input',drawBambuReview);
 for(const [id,direction] of [['fjordReviewPrevious',-1],['fjordReviewNext',1]]){
  panel.querySelector('#'+id).addEventListener('click',()=>{
   if(!prepared)return;
   slider.value=String(Math.max(0,Math.min(Number(slider.max),Number(slider.value)+direction)));
   drawBambuReview();
  });
 }
 panel.querySelector('#fjordReviewAccumulated').addEventListener('change',drawBambuReview);
 function zoomReview(next){
  reviewZoom=Math.min(6,Math.max(.5,next));
  reviewPanX=Math.min(500,Math.max(-500,reviewPanX));
  reviewPanY=Math.min(500,Math.max(-500,reviewPanY));
  drawBambuReview();
 }
 panel.querySelector('#fjordReviewZoomOut').addEventListener('click',()=>zoomReview(reviewZoom/1.4));
 panel.querySelector('#fjordReviewZoomIn').addEventListener('click',()=>zoomReview(reviewZoom*1.4));
 panel.querySelector('#fjordReviewFit').addEventListener('click',()=>{
  reviewZoom=1;reviewPanX=reviewPanY=0;
  reviewYaw=-.6;reviewPitch=.7;drawBambuReview();
 });
 const modeSwitch=panel.querySelector('#fjordReview3DToggle');
 modeSwitch.addEventListener('click',()=>{
  review3D=!review3D;
  modeSwitch.textContent=review3D?'◈ 3D':'▤ 2D';
  modeSwitch.setAttribute('aria-pressed',String(review3D));
  panel.querySelector('#fjordReviewGesture').textContent=review3D
   ?'Un doigt : pivoter · deux doigts : zoomer et déplacer · bouton 3D/2D.'
   :'Glisse pour déplacer · pince à deux doigts pour zoomer · vue du dessus.';
  drawBambuReview();
 });
 let lastTouch={x:0,y:0,d:0},rightDrag=false;
 function touchState(){
  const p=[...reviewTouches.values()];
  if(!p.length)return {x:0,y:0,d:0};
  const x=p.reduce((sum,a)=>sum+a.x,0)/p.length;
  const y=p.reduce((sum,a)=>sum+a.y,0)/p.length;
  const d=p.length>=2?Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y):0;
  return {x,y,d};
 }
 reviewCanvas.addEventListener('contextmenu',event=>event.preventDefault());
 reviewCanvas.addEventListener('pointerdown',event=>{
  if(!prepared)return;
  event.preventDefault();
  reviewTouches.set(event.pointerId,{x:event.clientX,y:event.clientY});
  rightDrag=event.button===2;
  lastTouch=touchState();
  try{reviewCanvas.setPointerCapture(event.pointerId);}catch(_){}
 });
 reviewCanvas.addEventListener('pointermove',event=>{
  if(!prepared||!reviewTouches.has(event.pointerId))return;
  event.preventDefault();
  reviewTouches.set(event.pointerId,{x:event.clientX,y:event.clientY});
  const now=touchState();
  const dx=now.x-lastTouch.x,dy=now.y-lastTouch.y;
  if(reviewTouches.size>=2){
   reviewPanX+=dx;reviewPanY+=dy;
   if(now.d&&lastTouch.d)reviewZoom=Math.min(6,Math.max(.5,reviewZoom*now.d/lastTouch.d));
  }else if(review3D&&!rightDrag){
   reviewYaw+=dx*.012;
   reviewPitch=Math.min(1.48,Math.max(-1.48,reviewPitch+dy*.009));
  }else{reviewPanX+=dx;reviewPanY+=dy;}
  lastTouch=now;
  drawBambuReview();
 });
 function endReviewTouch(event){
  reviewTouches.delete(event.pointerId);
  rightDrag=false;
  lastTouch=touchState();
  try{reviewCanvas.releasePointerCapture(event.pointerId);}catch(_){}
 }
 reviewCanvas.addEventListener('pointerup',endReviewTouch);
 reviewCanvas.addEventListener('pointercancel',endReviewTouch);
 reviewCanvas.addEventListener('wheel',event=>{
  if(!prepared)return;
  event.preventDefault();zoomReview(reviewZoom*(event.deltaY>0?.85:1.15));
 },{passive:false});
  panel.querySelector('#fjordReviewRedo').addEventListener('click',()=>{
  invalidatePreview();
  state.textContent='Aperçu mis de côté. Modifie les profils, puis retranche la pièce.';
 });
 const diagnosticButton=panel.querySelector('#fjordReviewDiagnostic');
 const diagnosticResult=panel.querySelector('#fjordReviewDiagnosticResult');
 diagnosticButton.addEventListener('click',async()=>{
  if(busy)return;
  diagnosticButton.disabled=true;
  diagnosticResult.hidden=false;
  diagnosticResult.textContent='Lecture de la connexion et des fichiers X2D… Aucun envoi ni démarrage.';
  try{
   const response=await fetch('/api/admin/atelier/impression-diagnostic',{
    credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}
   });
   if(!response.ok)throw Error('Diagnostic inaccessible. Vérifie ta session administrateur.');
   const result=await response.json();
   if(!result.ok)throw Error('Impossible de lire le diagnostic.');
   const status=result.status_ok?'État : OK':'État : échec';
   const files=result.files_ok?'Fichiers : OK en lecture':'Fichiers : échec';
   diagnosticResult.textContent=status+' · '+files+'\n'+String(result.diagnosis||'')+
     (result.last_upload?'\nDernier transfert refusé : '+String(result.last_upload).slice(0,420):'');
  }catch(error){
   diagnosticResult.textContent='⚠ '+String(error.message||error).slice(0,220);
  }finally{diagnosticButton.disabled=false;}
 });
 const download3mf=panel.querySelector('#fjordReviewDownload');
 download3mf.addEventListener('click',async()=>{
  if(!prepared||busy)return;
  const original=download3mf.textContent;
  download3mf.disabled=true;
  download3mf.textContent='⬇ Récupération du 3MF tranché…';
  try{
   const body=new FormData();
   body.append('csrf',__FJORD_CSRF__);
   body.append('stage',prepared.stage);
   const response=await fetch('/admin/atelier-imprimer/telecharger-3mf',{
    method:'POST',body,credentials:'same-origin',cache:'no-store'
   });
   if(!response.ok){
    let message='Téléchargement impossible.';
    try{const data=await response.json();message=data.error||message;}catch(_){}
    throw Error(message);
   }
   if(!(response.headers.get('content-type')||'').includes('3mf'))
    throw Error('Fichier inattendu : téléchargement bloqué.');
   const blob=await response.blob();
   if(blob.size<100||blob.size>30*1024*1024)throw Error('3MF incomplet.');
   const url=URL.createObjectURL(blob);
   const link=document.createElement('a');
   link.href=url;link.download='Creation-du-Fjord-X2D-tranche.3mf';
   document.body.appendChild(link);link.click();link.remove();
   setTimeout(()=>URL.revokeObjectURL(url),60000);
   state.textContent='✓ Fichier 3MF tranché téléchargé. Ouvre-le dans Bambu Studio si l’envoi distant échoue.';
  }catch(error){
   state.textContent='⚠ '+String(error.message||error).slice(0,180);
  }finally{
   download3mf.disabled=false;download3mf.textContent=original;
  }
 });
 transfer.addEventListener('click',async()=>{
  if(busy||!prepared)return;
  const approved=prepared;
  if(!confirm('Envoyer ce 3MF tranché à ta X2D ? L’impression ne démarrera PAS encore.'))return;
  busy=true;transfer.disabled=true;submit.disabled=true;
  panel.querySelector('#fjordAutoClose').disabled=true;
  state.textContent='Étape 3/3 · Transfert du 3MF approuvé sur ma X2D…';
  try{
   const body=new FormData();
   body.append('csrf',__FJORD_CSRF__);
   body.append('stage',approved.stage);
   const response=await fetch('/admin/atelier-imprimer/transmettre',{
    method:'POST',body,credentials:'same-origin',headers:{Accept:'application/json'}
   });
   if(!(response.headers.get('content-type')||'').includes('application/json'))
    throw Error('Session administrateur expirée : reconnecte-toi.');
   const result=await response.json();
   if(!response.ok||!result.ok)throw Error(result.error||'Transfert impossible.');
   if(typeof result.file!=='string'||!result.file.startsWith('gcode/')||
      typeof result.nonce!=='string'||result.nonce.length<24)
    throw Error('Confirmation de transfert incomplète : aucun démarrage possible.');
   if(remember.checked){
    try{
     const settings=savedProfiles();
     settings[approved.config]=approved.chosen;
     localStorage.setItem(preferenceKey,JSON.stringify(settings));
    }catch(_){}
   }
   invalidatePreview();
   transferred={file:result.file,nonce:result.nonce};
   startScreen.hidden=false;
   startScreen.classList.remove('fjord-start-sent');
   panel.classList.add('fjord-print-ready');
   panel.querySelector('#fjordStartFile').textContent=result.file;
   safetyVerified.checked=false;safetyCleared.checked=false;
   startMessage.textContent='Fichier transmis. Confirme les vérifications avant le démarrage.';
   state.textContent='✓ 3MF envoyé. Tu peux poursuivre dans l’Atelier.';
   beginPrinterPolling();
   startScreen.scrollIntoView({block:'nearest',behavior:'smooth'});
  }catch(error){
   // Show the whole safe server message; a 240-character truncation previously
   // split sentences and made the transfer warning misleading on mobile.
   const msg=String(error.message||error).slice(0,650);
   state.textContent='⚠ '+msg;
  }finally{
   busy=false;
   panel.querySelector('#fjordAutoClose').disabled=false;
   if(prepared)transfer.disabled=false;
   updateReady();
  }
 });

 const material=()=>String(document.getElementById('sliceMaterial')?.value||'PLA').trim().toUpperCase();
 const layer=()=>String(document.getElementById('sliceLayerHeight')?.value||'0.2');
 const jobKey=()=>material()+'|'+layer();
 function savedProfiles(){
  try{
   const value=JSON.parse(localStorage.getItem(preferenceKey)||'{}');
   return value&&typeof value==='object'&&!Array.isArray(value)?value:{};
  }catch(_){return {}}
 }
 function profilesSelected(){
  return {...Object.fromEntries(Object.keys(names).map(field=>
   [field,form.elements.namedItem(field).value])),
   bed_type:form.elements.namedItem('bed_type').value};
 }
 function eligible(field,item){
  if(field==='machine')return /X2D/i.test(item.model||'')&&
   String(item.nozzle||'').trim()==='0.4';
  if(field==='filament')return String(item.material||'').trim().toUpperCase()===material();
  if(field==='process'){
   const n=parseFloat(item.layer), wanted=parseFloat(layer());
   return Number.isFinite(n)&&Number.isFinite(wanted)&&Math.abs(n-wanted)<.005;
  }
  return false;
 }
 function selectedValid(){
  if(!inventory?.engine_ready||!form.elements.namedItem('bed_type').value)return false;
  return Object.entries(names).every(([field,category])=>{
   const id=form.elements.namedItem(field).value;
   return (inventory.profiles?.[category]||[]).some(item=>
    String(item.id)===id&&eligible(field,item));
  });
 }
 function updateReady(){
  submit.disabled=busy||!selectedValid();
  if(inventory?.engine_ready&&!form.elements.namedItem('bed_type').value&&!busy){
   state.textContent='⚠ Sélectionne le type de plaque réellement installé sur ta X2D avant de trancher.';
  }else if(inventory?.engine_ready&&Object.keys(names).every(field=>form.elements.namedItem(field).value)&&
     !selectedValid()&&!busy){
   state.textContent='⚠ Choisis une X2D avec buse 0,4 mm, un profil à la hauteur de couche demandée et un filament exactement du bon matériau.';
  }
 }
 panel.querySelector('#fjordAutoClose').addEventListener('click',()=>{if(!busy)panel.close()});
 panel.addEventListener('click',event=>{if(event.target===panel&&!busy)panel.close()});
 form.addEventListener('change',event=>{if(event.target?.tagName==='SELECT')invalidatePreview();updateReady();});
 function modelHasColorChanges(mesh){
  // Paint mode may create an empty face map and enable vertex colours even
  // without applying a single paint stroke. That is not multicolour.
  if(Array.isArray(mesh.material))return true;
  if(mesh.userData?.fjordPaintFaces &&
     Object.keys(mesh.userData.fjordPaintFaces).length>0)return true;
  if(!mesh.material?.vertexColors)return false;
  const attr=mesh.geometry?.getAttribute('color');
  if(!attr)return false;
  if(attr.itemSize<3||!attr.count)return true;
  const r=attr.getX(0),g=attr.getY(0),b=attr.getZ(0);
  if(![r,g,b].every(Number.isFinite))return true;
  for(let i=1;i<attr.count;i++)
   if(Math.abs(attr.getX(i)-r)>.002||
      Math.abs(attr.getY(i)-g)>.002||
      Math.abs(attr.getZ(i)-b)>.002)return true;
  return false;
 }
 function actualModelColor(mesh){
  if(mesh.material?.vertexColors){
   const colors=mesh.geometry?.getAttribute('color');
   if(colors?.count)return new THREE.Color().fromBufferAttribute(colors,0).getHex();
  }
  return basePartColor(mesh);
 }
 function hasMultipleSceneColors(){
  const colors=new Set();
  for(const mesh of models){
   if(modelHasColorChanges(mesh))return true;
   colors.add(actualModelColor(mesh));
   if(colors.size>1)return true;
  }
  return false;
 }
 function updateMonoApproval(){
  const multi=hasMultipleSceneColors();
  monoWrap.hidden=!multi;
  if(!multi)monoConsent.checked=false;
  return multi;
 }
 monoConsent.addEventListener('change',()=>{
  state.textContent=monoConsent.checked
   ?'✓ Essai en une couleur : la géométrie sera tranchée sans transférer la peinture AMS.'
   :'⚠ Cette création contient plusieurs couleurs. Coche le mode UNE couleur pour l’essai.';
 });
 function ensureValidScene(){
  if(!models.length)throw Error('Ajoute une pièce au plateau.');
  if(updateMonoApproval()&&!monoConsent.checked)
   throw Error('Plusieurs couleurs détectées : coche « Je confirme : pour cet essai, trancher en UNE couleur » ci-dessous, ou utilise Bambu Studio pour une impression multicolore AMS.');
  const extents=models.reduce((b,m)=>b.union(modelWorldBounds(m)),new THREE.Box3());
  const size=extents.getSize(new THREE.Vector3());
  if([size.x,size.y,size.z].some(n=>!Number.isFinite(n)||n<=0)||
     size.x>256||size.y>256||size.z>260)
   throw Error('La création dépasse le volume X2D indiqué (256 × 256 × 260 mm).');
  if(!['PLA','PETG','ASA','TPU'].includes(material()))
   throw Error('Choisis un matériau PLA, PETG, ASA ou TPU dans le tranchage de l’Atelier.');
 }
 async function prepare(){
  if(busy||!selectedValid())return;
  try{ensureValidScene()}catch(e){state.textContent='⚠ '+e.message;return}
  busy=true;submit.disabled=true;
  panel.querySelector('#fjordAutoClose').disabled=true;
  state.textContent='Étape 1/3 · Export des pièces du plateau…';
  const chosen=profilesSelected(),config=jobKey();
  try{
   const group=new THREE.Group();
   for(const m of models){
    const clone=m.clone();clone.geometry=m.geometry;clone.material=m.material;group.add(clone);
   }
   const binary=new STLExporter().parse(group,{binary:true});
   const blob=new Blob([binary],{type:'application/octet-stream'});
   if(blob.size>8*1024*1024)throw Error('STL trop volumineux (8 Mo).');
   const requestBody=new FormData();
   requestBody.append('csrf',__FJORD_CSRF__);
   requestBody.append('stl',blob,'Creation-du-Fjord.stl');
   requestBody.append('material',material());
   for(const [field,id] of Object.entries(chosen))requestBody.append(field,id);
   invalidatePreview();
   state.textContent='Étape 2/3 · Tranchage Bambu Studio, puis aperçu réel des couches…';
   const response=await fetch('/admin/atelier-imprimer/preparer',{
    method:'POST',body:requestBody,credentials:'same-origin',
    headers:{'Accept':'application/json'},redirect:'follow'
   });
   if(!(response.headers.get('content-type')||'').includes('application/json'))
    throw Error('Le serveur n’a pas retourné de résultat. Vérifie ta session administrateur.');
   const result=await response.json();
   if(!response.ok||!result.ok)throw Error(result.error||'Préparation impossible.');
   if(typeof result.stage!=='string'||!Array.isArray(result.preview?.layers)||!result.preview.layers.length)
    throw Error('Aucun aperçu réel disponible : envoi désactivé.');
   prepared={stage:result.stage,preview:result.preview,chosen,config};
   const review=panel.querySelector('#fjordSliceReview');
   review.hidden=false;
   // Put the actual Bambu toolpath directly after the dialog title.
   // This must remain above the explanatory text and profile controls.
   const heading=panel.querySelector('.fjord-dialog-head');
   if(review.previousElementSibling!==heading)heading.insertAdjacentElement('afterend',review);
   panel.classList.add('fjord-preview-active');
   reviewZoom=1;reviewPanX=reviewPanY=0;
   review3D=true;reviewYaw=-.6;reviewPitch=.7;
   modeSwitch.textContent='◈ 3D';
   modeSwitch.setAttribute('aria-pressed','true');
   panel.querySelector('#fjordReviewAccumulated').checked=true;
   for(const [from,to] of [['estimateKg','fjordReviewKgRate'],
    ['estimateHourRate','fjordReviewHourRate'],['estimateSetup','fjordReviewSetupRate'],
    ['estimateMargin','fjordReviewMarkup']]){
    const source=document.getElementById(from),target=panel.querySelector('#'+to);
    if(source&&source.value!==''&&Number.isFinite(Number(source.value)))target.value=source.value;
   }
   const slider=panel.querySelector('#fjordReviewLayer');
   slider.max=String(result.preview.layers.length-1);
   slider.value=slider.max;
   panel.querySelector('#fjordReviewTransfer').disabled=false;
   state.textContent='✓ Tranchage terminé. Inspecte le résultat avant d’envoyer.';
   drawBambuReview();
   // Move focus away from the hidden submit button directly to the preview.
   review.focus({preventScroll:true});
   panel.scrollTop=0;
   requestAnimationFrame(()=>{if(panel.open&&prepared)panel.scrollTop=0;});
  }catch(error){
   state.textContent='⚠ '+String(error.message||error).slice(0,240)+
    ' Aucune commande de démarrage n’a été envoyée.';
  }finally{
   busy=false;
   panel.querySelector('#fjordAutoClose').disabled=false;
   updateReady();
  }
 }
 form.addEventListener('submit',event=>{event.preventDefault();prepare()});
 fjordAutoButton.addEventListener('click',async()=>{
  if(busy)return;
  const already=opened;opened=true;
  if(!panel.open)panel.showModal();
  state.textContent='Lecture des profils Bambu Studio X2D…';
  submit.disabled=true;
  inventory=null;
  invalidatePreview();
  clearPrintScreen();
  stopPrinterPolling();
  monoConsent.checked=false;
  updateMonoApproval();
  try{
   const response=await fetch('/api/admin/atelier/impression-profils',{
    credentials:'same-origin',cache:'no-store'
   });
   if(!response.ok)throw Error('Connexion à l’administration nécessaire.');
   const data=await response.json();inventory=data;
   const remembered=savedProfiles()[jobKey()]||{};
   let rememberedAll=true;
   for(const [field,category] of Object.entries(names)){
    const select=form.elements.namedItem(field);
    select.replaceChildren(new Option('— Sélectionner —',''));
    const all=data.profiles?.[category]||[];
    const compatible=all.filter(item=>eligible(field,item));
    for(const item of compatible){
     let detail='';
     if(field==='machine')detail=' · buse '+item.nozzle+' mm';
     if(field==='filament')detail=' · '+item.material;
     if(field==='process')detail=' · '+item.layer+' mm';
     select.add(new Option(item.name+detail,String(item.id)));
    }
    // Prefer the genuine bundled Bambu preset for a diagnostic first print.
    // Never erase existing CHATOU choices or the user's saved preferences.
    const saved=compatible.find(item=>String(item.id)===String(remembered[field]||''));
    const official=compatible.find(item=>item.official===true);
    const selected=(saved?.official?saved:null)||official||saved||
      (compatible.length===1?compatible[0]:null);
    if(selected)select.value=String(selected.id);
    if(!saved||String(selected?.id)!==String(saved.id))rememberedAll=false;
   }
   const plate=form.elements.namedItem('bed_type');
   plate.value=[...plate.options].some(option=>option.value===remembered.bed_type)
    ?remembered.bed_type:'';
   if(!plate.value)rememberedAll=false;
   if(!data.engine_ready)state.textContent='⚠ Bambu Studio indisponible sur Railway.';
   else if(!Object.keys(names).every(field=>form.elements.namedItem(field).options.length>1))
    state.textContent='⚠ Il manque un profil complet correspondant : X2D 0,4 mm, '+material()+
      ' et couche '+layer()+' mm. Vérifie les profils importés.';
   else if(rememberedAll&&selectedValid()){
    state.textContent='✓ Profils déjà validés pour '+material()+' et '+layer()+
      ' mm. Préparation automatique…';
   }else if(Object.keys(names).every(field=>form.elements.namedItem(field).selectedOptions[0]?.textContent.includes("Bambu d'origine")))
    state.textContent='✓ Profils Bambu d’origine présélectionnés. Lance le tranchage du cube PETG pour les vérifier.';
   else state.textContent='Choisis tes profils une seule fois : ils seront mémorisés après une préparation réussie.';
   updateReady();
   if(rememberedAll&&selectedValid()&&!already)await prepare();
  }catch(error){
   state.textContent='⚠ '+String(error.message||error).slice(0,180);
  }
  opened=false;
 });
}

""".replace("__FJORD_CSRF__", json.dumps(csrf_token))
    styles = """
<style>
#fjordModelChooser{max-width:min(680px,94vw);width:94vw;max-height:85dvh;overflow:auto;
 background:#10283b;color:#eef9ff;border:1px solid #51bfe5;border-radius:16px;padding:18px;box-shadow:0 25px 75px #0009}
#fjordModelChooser::backdrop{background:#000b}
#fjordAutoPrintLauncher{min-height:40px;padding:8px 12px;background:#166174;border:1px solid #67c7e4;border-radius:9px;color:#fff;font-weight:750;cursor:pointer}
#fjordAutoPrintDialog{width:min(580px,95vw);max-height:84dvh;overflow:auto;padding:18px;border:1px solid #58b9de;background:#112c40;color:#f0f8fd;border-radius:15px}
#fjordAutoPrintDialog::backdrop{background:#000b}
#fjordAutoPrintDialog .fjord-dialog-head{display:flex;justify-content:space-between;gap:12px;align-items:center}
#fjordAutoPrintDialog p{line-height:1.5;color:#d2e5ee}
#fjordAutoPrintDialog form{display:grid;gap:12px;margin:18px 0}
#fjordAutoPrintDialog label{display:grid;gap:4px}
#fjordAutoPrintDialog select{min-height:44px;width:100%;background:#203f54;color:white;border:1px solid #7195ab}
#fjordAutoPrintDialog button{min-height:42px}
#fjordAutoPrintDialog button:disabled{opacity:.5;cursor:not-allowed}
#fjordAutoPrintDialog a{color:#94e5fb}
#fjordSliceReview[hidden]{display:none!important}
#fjordSliceReview{border-top:1px solid #4c7388;margin-top:9px;padding-top:8px}
#fjordSliceReview h3{font-size:15px;margin:4px 0}
.fjord-review-preview{position:relative;width:min(100%,420px);margin:10px auto}
.fjord-review-mode{position:absolute;top:8px;left:8px;min-height:42px;min-width:56px;
 background:#183c53eb;color:#fff;border:1px solid #9cbdd0;border-radius:9px;font-weight:800}
.fjord-review-mode[aria-pressed=true]{border-color:#4de0bd;color:#bcffed}
.fjord-review-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:10px 0}
.fjord-review-facts>div{background:#183c53;border:1px solid #43687b;padding:9px 7px;border-radius:10px}
.fjord-review-facts span{display:block;font-size:11px;color:#b8d3e1}
.fjord-review-facts strong{display:block;font-size:14px;color:#fff;overflow-wrap:anywhere;margin-top:4px}
.fjord-review-price{border:1px solid #49ad96;border-radius:11px;padding:12px;background:#173d40;margin:9px 0}
.fjord-review-price span{display:block;font-weight:700}
.fjord-review-price>strong{display:block;font-size:27px;color:#b8ffe7;margin:4px 0}
.fjord-review-price p{font-size:12px;color:#d0e5dc;margin:5px 0}
.fjord-review-pricing{margin:8px 0;border:1px solid #48677d;padding:9px;border-radius:10px}
.fjord-review-pricing summary{font-weight:700;cursor:pointer}
.fjord-review-rategrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:9px 0}
.fjord-review-rategrid label{font-size:12px;min-width:0}
.fjord-review-rategrid input{width:100%;min-width:0;min-height:43px;padding:6px}
#fjordReviewBreakdown{font-size:12px;color:#c6e3ed}
#fjordReviewDownload{display:block;width:100%;min-height:48px;border:1px solid #6792af;
 border-radius:10px;background:#17344b;color:#e2f5ff;margin:8px 0;padding:9px;font-weight:700}
#fjordReviewDiagnostic{display:block;width:100%;min-height:46px;color:#d5f3fc;
 background:#17344b;border:1px solid #547d99;border-radius:10px;margin:7px 0;padding:8px;font-weight:650}
#fjordReviewDiagnosticResult{white-space:pre-line;overflow-wrap:anywhere;border:1px solid #557f95;
 border-radius:8px;padding:10px;font-size:13px;line-height:1.5;margin:7px 0}
#fjordReviewDiagnosticResult[hidden]{display:none!important}
#fjordAutoPrintDialog #fjordAutoState{white-space:normal;overflow-wrap:anywhere;line-height:1.5}

@media(max-width:390px){.fjord-review-facts strong{font-size:12px}}
#fjordReviewCanvas{width:100%;height:auto;display:block;border:1px solid #527b93;border-radius:10px;background:#101c29;touch-action:none;user-select:none}
.fjord-review-zoom{display:flex;position:absolute;right:8px;bottom:8px;gap:5px}
.fjord-review-zoom button{min-width:45px;min-height:45px;color:#fff;background:#183c53ea;border:1px solid #8eb3c9;border-radius:9px;font-size:22px}
.fjord-review-gesture{font-size:12px;text-align:center;margin:3px 0!important}
.fjord-review-layerbar{display:grid;grid-template-columns:48px minmax(0,1fr) 48px;gap:8px;align-items:center}
.fjord-review-layerbar button{min-height:48px;border-radius:10px}
#fjordReviewLayer{min-width:0}
#fjordAutoPrintDialog .fjord-auto-remember{display:flex;align-items:center;gap:8px}
#fjordAutoPrintDialog .fjord-auto-remember input[type=checkbox]{width:19px;height:19px;flex-shrink:0}
#fjordReviewLayer{width:100%;min-height:38px;accent-color:#51d3fb}
#fjordSliceReview .fjord-review-note{font-size:12px;color:#b9d6e6}
#fjordSliceReview .fjord-auto-send{background:#166c5b;color:#fff;font-weight:800;width:100%;padding:12px}
#fjordSliceReview #fjordReviewRedo{width:100%;margin-top:8px}
#fjordAutoPrintDialog{max-height:90dvh}
#fjordAutoPrintDialog .fjord-auto-stock-note{
 margin:6px 0 10px;border-left:3px solid #55cba6;
 padding:8px 10px;background:#153b43;border-radius:7px;
 color:#d9f4e9;font-size:12px;line-height:1.45
}
#fjordMonoApproval[hidden]{display:none!important}
#fjordMonoApproval{display:grid;gap:8px;padding:11px 12px;margin:9px 0;
 border:1px solid #d49a48;border-radius:10px;background:#392d1c;color:#fff1da}
#fjordMonoApproval strong{font-size:14px}
#fjordMonoApproval p{margin:0;font-size:12px;line-height:1.5}
#fjordMonoApproval label{font-size:13px;line-height:1.5}
#fjordMonoApproval input[type=checkbox]{min-width:23px;min-height:23px}
#fjordAutoPrintDialog.fjord-preview-active #fjordAutoForm{display:none!important}
#fjordAutoPrintDialog.fjord-preview-active .fjord-auto-stock-note{display:none!important}
#fjordAutoPrintDialog.fjord-preview-active .fjord-auto-intro{display:none!important}
#fjordAutoPrintDialog.fjord-preview-active #fjordAutoState{margin:6px 0!important;font-size:12px}
#fjordAutoPrintDialog.fjord-print-ready #fjordAutoForm,#fjordAutoPrintDialog.fjord-print-ready #fjordSliceReview{display:none!important}
 .fjord-slice-print-entry{margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}
 .fjord-slice-print-entry #fjordPrintShortcut{width:100%;display:flex!important;min-height:51px!important;
  border-radius:10px!important;justify-content:center;font-weight:800;font-size:14px!important}
 .fjord-slice-print-entry #fjordAutoPrintLauncher{display:none!important}
 .fjord-slice-print-entry .fjord-quote-from-slice{
  width:100%;display:flex;justify-content:center;align-items:center;min-height:48px;
  margin-top:9px;border:1px solid #6ac5ed;border-radius:10px;
  background:#116b91;color:#fff;font-size:14px;font-weight:800
 }
 .fjord-slice-print-entry .fjord-quote-from-slice:disabled{opacity:.55;cursor:wait}
 .fjord-slice-print-entry p{font-size:11px;line-height:1.45;color:var(--muted);margin:8px 0 0}

#fjordStartAtelier[hidden]{display:none!important}
#fjordStartAtelier{border-top:1px solid #597e93;padding-top:14px;margin-top:12px;display:grid;gap:12px}
#fjordStartAtelier h3{font-size:17px;margin:4px 0}
#fjordStartAtelier>p{overflow-wrap:anywhere}
#fjordStartAtelier .fjord-printer-state{display:grid;gap:8px;border:1px solid #456b83;border-radius:12px;padding:13px}
#fjordLiveProgress{width:100%;height:12px;accent-color:#55cfaa}
#fjordStartAtelier button{min-height:48px;border-radius:11px}
#fjordStartNow{background:#17694e;color:#fff;font-weight:800;border:1px solid #6adaae}
#fjordStartNow:disabled{opacity:.48}
#fjordStartResult{font-weight:650;line-height:1.5}
#fjordStartAtelier .fjord-auto-remember{padding:8px 0;align-items:flex-start!important}
#fjordStartAtelier input[type=checkbox]{min-width:23px;min-height:23px}
@media(max-width:760px){
 #fjordAutoPrintDialog{box-sizing:border-box;width:100vw;max-width:100vw;min-height:100dvh;max-height:100dvh;height:100dvh;margin:0;
  padding:calc(12px + env(safe-area-inset-top,0px)) 14px calc(14px + env(safe-area-inset-bottom,0px));
  border-radius:0;border:none;overflow-y:auto;overscroll-behavior:contain}
 #fjordAutoPrintDialog .fjord-dialog-head{position:sticky;top:calc(-12px - env(safe-area-inset-top,0px));
  background:#112c40;z-index:3;padding:10px 0;border-bottom:1px solid #476e80}
 #fjordAutoPrintDialog .fjord-dialog-head button{min-width:48px;min-height:48px}
 #fjordAutoPrintDialog form{gap:10px}
 #fjordAutoPrintDialog form select,#fjordAutoPrintDialog form button{min-height:50px;font-size:16px}
 #fjordAutoPrintDialog #fjordReviewLayer{height:52px;touch-action:pan-y}
 #fjordAutoPrintDialog .fjord-review-layerbar button{min-width:48px;min-height:52px}
 #fjordAutoPrintDialog .fjord-review-zoom button{min-width:48px;min-height:48px}
 #fjordAutoPrintDialog.fjord-preview-active #fjordAutoForm{display:none}
 #fjordAutoPrintDialog.fjord-print-ready #fjordAutoForm,#fjordAutoPrintDialog.fjord-print-ready #fjordSliceReview{display:none!important}
 #fjordAutoPrintDialog.fjord-print-ready #fjordStartNow{min-height:58px;position:sticky;bottom:0;z-index:2}
 #fjordAutoPrintDialog.fjord-preview-active #fjordSliceReview{padding-top:3px;margin-top:2px;border-top:0}
 #fjordAutoPrintDialog.fjord-preview-active #fjordSliceReview>h3{margin:2px 0 4px}
 #fjordAutoPrintDialog.fjord-preview-active #fjordSliceReview>p:first-of-type{margin:4px 0!important;font-size:12px}
 #fjordAutoPrintDialog.fjord-preview-active .fjord-review-preview{margin:6px auto}
 #fjordReviewTransfer{position:sticky;bottom:0;z-index:2;min-height:56px!important;
  margin:9px 0 3px;box-shadow:0 -7px 14px #112c40c9}
}
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
    return html.replace("/* End parametric generators */", injection + "\n" + open_model + "\n" + auto_print_launcher + "\n/* End parametric generators */", 1)


def public_studio(html):
    """Hide private costs, while offering a sign-in route to the private Atelier."""
    # The shortcut is public, but /admin/atelier-3d itself remains protected by
    # admin_required. Signed-in admins go directly to the private editor; other
    # visitors are sent to /admin/login?next=/admin/atelier-3d.
    shortcut = (
        '<a id="fjordAdminAccess" href="/admin/atelier-3d" '
        'title="Ouvrir l’Atelier administrateur (connexion requise)" '
        'style="display:inline-flex;align-items:center;justify-content:center;'
        'min-height:40px;padding:8px 12px;border-radius:9px;'
        'border:1px solid #67b0d9;background:#11577e;color:#fff;'
        'font-size:13px;font-weight:750;white-space:nowrap;text-decoration:none">'
        '⚙️ Administration</a>'
    )
    html = html.replace('<div class="top-preferences">',
                        '<div class="top-preferences">' + shortcut, 1)
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
        c.execute("ALTER TABLE private_models ADD COLUMN IF NOT EXISTS content_sha256 TEXT")
        c.execute("""CREATE INDEX IF NOT EXISTS private_models_sha256_idx
                     ON private_models(content_sha256)""")
        c.execute("""CREATE TABLE IF NOT EXISTS private_quotes (
          id BIGSERIAL PRIMARY KEY, customer TEXT NOT NULL, email TEXT, phone TEXT,
          title TEXT NOT NULL, description TEXT, material TEXT NOT NULL,
          quantity INTEGER NOT NULL, unit_price NUMERIC(12,2) NOT NULL,
          shipping NUMERIC(12,2) NOT NULL DEFAULT 0, apply_taxes BOOLEAN NOT NULL DEFAULT FALSE,
          military_discount BOOLEAN NOT NULL DEFAULT FALSE,
          atelier_preview BOOLEAN NOT NULL DEFAULT FALSE,
          model_id BIGINT REFERENCES private_models(id) ON DELETE SET NULL,
          preview BYTEA, preview_mime TEXT,
          grams DOUBLE PRECISION, hours DOUBLE PRECISION, filament_kg DOUBLE PRECISION,
          machine_hour DOUBLE PRECISION, setup_cost DOUBLE PRECISION,
          markup DOUBLE PRECISION, payment_token TEXT UNIQUE,
          payment_status TEXT NOT NULL DEFAULT 'En attente',
          paid_at TIMESTAMPTZ,
          created TIMESTAMPTZ DEFAULT NOW())""")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS military_discount BOOLEAN NOT NULL DEFAULT FALSE")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS atelier_preview BOOLEAN NOT NULL DEFAULT FALSE")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS production_status TEXT NOT NULL DEFAULT 'À traiter'")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS production_progress INTEGER NOT NULL DEFAULT 0")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS public_number TEXT")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS printer_job_name TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS private_quotes_public_number_unique ON private_quotes(public_number) WHERE public_number IS NOT NULL")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS payment_token TEXT")
        c.execute("""ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS
                     payment_status TEXT NOT NULL DEFAULT 'En attente'""")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ")
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS private_quotes_payment_token_idx
                     ON private_quotes(payment_token)""")

    def _save_model(deduplicate=False):
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
        checksum = hashlib.sha256(data).hexdigest()
        with db() as c:
            if deduplicate:
                existing = c.execute("""SELECT id FROM private_models
                    WHERE content_sha256=%s LIMIT 1""", (checksum,)).fetchone()
                if existing:
                    return {"id": existing["id"], "duplicate": True}
                # Existing library entries predate the checksum column.
                old = c.execute("""SELECT id FROM private_models
                    WHERE content_sha256 IS NULL AND octet_length(filedata)=%s
                      AND filedata=%s LIMIT 1""", (len(data), data)).fetchone()
                if old:
                    c.execute("""UPDATE private_models SET content_sha256=%s
                                 WHERE id=%s AND content_sha256 IS NULL""",
                              (checksum, old["id"]))
                    return {"id": old["id"], "duplicate": True}
            preview = _image(request.files.get("preview"))
            if not preview and filename.lower().endswith((".stl", ".3mf")):
                try:
                    preview = make_model_preview(data, filename)
                except (ValueError, OverflowError):
                    preview = None  # Keep the model if rendering fails.
            row = c.execute("""INSERT INTO private_models
                (name,filename,filedata,preview,preview_mime,content_sha256)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (name, filename, data, preview[1] if preview else None,
                 preview[0] if preview else None, checksum)).fetchone()
        return {"id": row["id"], "duplicate": False}

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
            try:
                preview = make_model_preview(source["filedata"], source["filename"])
            except (ValueError, OverflowError):
                preview = None
            result=c.execute("""INSERT INTO private_models
                (name,filename,filedata,preview,preview_mime)
                VALUES(%s,%s,%s,%s,%s) RETURNING id""",
                ("Demande #"+str(request_id)+" - "+source["name"],
                 source["filename"],source["filedata"],
                 preview[1] if preview else None,
                 preview[0] if preview else None)).fetchone()
        return redirect("/admin/soumissions-pro?model_id="+str(result["id"])+
                        "&request_id="+str(request_id))

    @app.get("/admin/modeles")
    @admin_required
    def fjord_models():
        with db() as c:
            models = c.execute("""SELECT id,name,filename,octet_length(filedata) AS bytes,
                  (preview IS NOT NULL OR lower(filename) LIKE '%.stl' OR lower(filename) LIKE '%.3mf') AS has_preview,created
                  FROM private_models ORDER BY created DESC LIMIT 1000""").fetchall()
        return page("Mes modèles 3D", r"""
<style>
.fjord-actions{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.fjord-file{display:grid;grid-template-columns:110px 1fr;gap:14px;align-items:center}
.fjord-file img{width:110px;height:100px;object-fit:contain;background:#061422;border-radius:9px}
.fjord-file .muted{word-break:break-word}.fjord-file form{margin-top:9px}
.fj-bulk-pickers{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.fj-bulk-pickers label{min-width:0}
.fj-bulk-pickers input{max-width:100%}
.fj-bulk-actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:12px 0}
.fj-bulk-actions button{width:auto}
.fj-bulk-progress{display:block;width:100%;max-width:670px;height:16px;margin:10px 0}
.fj-bulk-log{white-space:pre-wrap;overflow-wrap:anywhere;max-height:170px;overflow:auto;font-size:13px}
@media(max-width:550px){.fjord-file{grid-template-columns:1fr}.fjord-file img{width:100%;height:170px}.fj-bulk-pickers{grid-template-columns:1fr}.fj-bulk-actions button{width:100%}}
</style>
<div class="eyebrow">Administration privée</div><h1>Ma bibliothèque 3D</h1>
<p>Tes modèles sont conservés dans la base de données du site. Retrouve-les sur ton ordinateur ou ton téléphone, télécharge leur STL/3MF ou démarre une soumission.</p>
<div class="fjord-actions"><a class="btn" href="/admin/atelier-3d">✦ Ouvrir mon Atelier 3D</a><a class="btn" href="/admin/soumissions-pro">📄 Soumissions PRO</a><a href="/admin">← Administration</a></div>
<div class="card"><h2>Importer un modèle existant</h2><p class="muted small">STL, 3MF ou projet JSON de l'Atelier (8 Mo maximum). L'aperçu des STL et 3MF est généré automatiquement; tu peux ajouter une autre image.</p>
<form method="post" action="/admin/modeles/upload" enctype="multipart/form-data">{{csrf|safe}}
<label>Nom du modèle<input name="name" maxlength="120" required placeholder="Ex. Support de téléphone RAM"></label>
<label>Fichier 3D<input type="file" name="model" accept=".stl,.3mf,.json" required></label>
<label>Photo ou capture 3D (facultatif)<input type="file" name="preview" accept="image/png,image/jpeg,image/webp"></label>
<button>Enregistrer dans ma bibliothèque</button></form></div>
<div class="card" id="fjordBulkPanel">
<h2>📚 Importer plusieurs fichiers depuis mon ordinateur</h2>
<p class="muted small">Sélectionne plusieurs fichiers STL/3MF ou un dossier complet de ton ordinateur. Les fichiers des sous-dossiers sont pris en compte. Aucun accès à Bambu Studio requis. Maximum 8 Mo par fichier, envoyés un par un avec leur aperçu automatique.</p>
<form id="fjordBulkImport">{{csrf|safe}}
<div class="fj-bulk-pickers">
<label>Choisir plusieurs fichiers STL ou 3MF<input id="fjordBulkFiles" type="file" accept=".stl,.3mf" multiple></label>
<label>Ou choisir un dossier complet<input id="fjordBulkFolder" type="file" webkitdirectory directory multiple></label>
</div>
<label><input id="fjordBulkSkipDuplicates" type="checkbox" checked style="width:auto;display:inline;margin-right:8px">Ignorer les modèles déjà présents (fichiers identiques)</label>
<div class="fj-bulk-actions">
<button type="button" id="fjordBulkStart" disabled>📥 Importer dans ma bibliothèque</button>
<button type="button" id="fjordBulkStop" hidden>Arrêter après le fichier en cours</button>
<a href="/admin/modeles" id="fjordBulkRefresh" hidden>↻ Afficher les modèles importés</a>
</div>
<p id="fjordBulkStatus" role="status" aria-live="polite" class="muted small">Choisis des fichiers ou un dossier.</p>
<progress id="fjordBulkProgress" class="fj-bulk-progress" max="100" value="0" hidden></progress>
<div id="fjordBulkLog" class="fj-bulk-log" aria-live="polite"></div>
</form></div>
<script>
(function(){
 const form=document.getElementById("fjordBulkImport");
 const fileInput=document.getElementById("fjordBulkFiles");
 const folderInput=document.getElementById("fjordBulkFolder");
 const skip=document.getElementById("fjordBulkSkipDuplicates");
 const start=document.getElementById("fjordBulkStart");
 const stop=document.getElementById("fjordBulkStop");
 const status=document.getElementById("fjordBulkStatus");
 const progress=document.getElementById("fjordBulkProgress");
 const log=document.getElementById("fjordBulkLog");
 const refresh=document.getElementById("fjordBulkRefresh");
 const csrf=form.querySelector('[name="csrf"]');
 let selected=[],ignored=0,running=false,cancel=false;
 form.addEventListener("submit",event=>event.preventDefault());
 function choose(input,other){
   if(running)return;
   other.value="";
   const candidates=Array.from(input.files||[]);
   selected=candidates.filter(f=>/\.(stl|3mf)$/i.test(f.name));
   ignored=candidates.length-selected.length;
   start.disabled=selected.length===0;
   refresh.hidden=true;progress.hidden=true;progress.value=0;log.textContent="";
   status.textContent=selected.length
     ?selected.length+" fichier(s) STL/3MF prêt(s)"+(ignored?" · "+ignored+" autre(s) ignoré(s).":".")
     :"Aucun fichier STL ou 3MF dans cette sélection.";
 }
 fileInput.addEventListener("change",()=>choose(fileInput,folderInput));
 folderInput.addEventListener("change",()=>choose(folderInput,fileInput));
 stop.addEventListener("click",()=>{cancel=true;stop.disabled=true;status.textContent="Arrêt demandé : le fichier en cours se termine.";});
 start.addEventListener("click",async()=>{
   if(running||!selected.length)return;
   running=true;cancel=false;start.disabled=true;stop.hidden=false;stop.disabled=false;
   fileInput.disabled=true;folderInput.disabled=true;skip.disabled=true;
   refresh.hidden=true;
   progress.hidden=false;progress.max=selected.length;progress.value=0;
   const files=selected.slice(),failures=[];
   let added=0,duplicates=0,failed=0,done=0,skipped=0;
   const maxSize=8*1024*1024;
   const skipDuplicates=skip.checked;
   for(const file of files){
     if(cancel)break;
     status.textContent="Importation "+(done+1)+"/"+files.length+" : "+file.name;
     if(!file.size||file.size>maxSize){
       failed++;failures.push(file.name+" : "+(file.size>maxSize?"plus de 8 Mo":"fichier vide"));
     }else{
       const payload=new FormData();
       payload.append("csrf",csrf.value);
       payload.append("name",file.name.replace(/\.(stl|3mf)$/i,"").slice(0,120)||"Modèle 3D");
       payload.append("model",file,file.name);
       if(skipDuplicates)payload.append("skip_duplicates","yes");
       try{
         const response=await fetch("/admin/modeles/api/save",{method:"POST",body:payload,credentials:"same-origin"});
         let result=null;
         try{result=await response.json()}catch(_error){}
         if(!response.ok||!result||!result.ok)throw new Error(result&&result.error||"Erreur HTTP "+response.status);
         if(result.duplicate)duplicates++;else added++;
       }catch(error){failed++;failures.push(file.name+" : "+error.message);}
     }
     done++;progress.value=done;
     status.textContent="Traités : "+done+"/"+files.length+" · Ajoutés : "+added+" · Doublons : "+duplicates+" · Échecs : "+failed;
   }
   skipped=files.length-done;
   running=false;fileInput.disabled=false;folderInput.disabled=false;skip.disabled=false;
   stop.hidden=true;start.disabled=!selected.length;
   status.textContent="Terminé : "+added+" ajouté(s), "+duplicates+" doublon(s), "+failed+" échec(s)"+(skipped?", "+skipped+" non traité(s) (arrêt demandé)":"")+".";
   log.textContent=failures.length?"Fichiers à vérifier :\n"+failures.slice(0,30).join("\n")+(failures.length>30?"\n… et "+(failures.length-30)+" autre(s).":""):"";
   refresh.hidden=added===0;
 });
})();
</script>
<h2>Modèles enregistrés ({{models|length}})</h2>
<form method="post" action="/admin/modeles/apercu/regenerer" onsubmit="return confirm('Actualiser les aperçus de tous les modèles STL et 3MF ? Les fichiers 3D seront conservés.')" style="margin:12px 0">
{{csrf|safe}}
<button type="submit">🎨 Actualiser les aperçus de toute la bibliothèque</button>
<p class="muted small">Régénère les images depuis les modèles originaux, en conservant les couleurs 3MF disponibles.</p>
</form>
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
            saved=_save_model(deduplicate=request.form.get("skip_duplicates")=="yes")
        except Exception as exc:
            # The browser receives an error status without a private traceback.
            from werkzeug.exceptions import HTTPException
            if isinstance(exc, HTTPException):
                return {"error":exc.description},exc.code
            raise
        return {"ok":True, **saved}

    @app.get("/admin/modeles/api/liste")
    @admin_required
    def fjord_model_list_json():
        with db() as c:
            rows=c.execute("""SELECT id,name,filename,(preview IS NOT NULL OR lower(filename) LIKE '%.stl' OR lower(filename) LIKE '%.3mf') AS has_preview
                               FROM private_models ORDER BY created DESC LIMIT 1000""").fetchall()
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
            model=c.execute("""SELECT preview,preview_mime,filename,filedata
                               FROM private_models WHERE id=%s""",
                            (model_id,)).fetchone()
            if not model:abort(404)
            primary=request.args.get("primary","")
            secondary=request.args.get("secondary","")
            custom=bool(re.fullmatch(r"#[0-9a-fA-F]{6}",primary) and re.fullmatch(r"#[0-9a-fA-F]{6}",secondary))
            preview=None if custom else ((model["preview_mime"],model["preview"]) if model["preview"] else None)
            if not preview and model["filename"].lower().endswith((".stl", ".3mf")):
                try:
                    preview = make_model_preview(model["filedata"], model["filename"],
                        color=primary if custom else "#168ac2",
                        secondary_color=secondary if custom else None)
                except (ValueError, OverflowError):
                    preview = None
                if preview:
                    c.execute("""UPDATE private_models SET preview=%s,preview_mime=%s
                                 WHERE id=%s AND preview IS NULL""",
                              (preview[1], preview[0], model_id))
        if not preview:abort(404)
        return send_file(io.BytesIO(preview[1]),mimetype=preview[0],max_age=0)

    @app.post("/admin/modeles/apercu/regenerer")
    @admin_required
    def fjord_refresh_library_previews():
        verify()
        refreshed=0
        with db() as c:
            rows=c.execute("SELECT id,filename,filedata FROM private_models WHERE lower(filename) LIKE '%.3mf' OR lower(filename) LIKE '%.stl'").fetchall()
            for item in rows:
                try:
                    preview=make_model_preview(item["filedata"],item["filename"])
                    if preview:
                        c.execute("UPDATE private_models SET preview=%s,preview_mime=%s WHERE id=%s",(preview[1],preview[0],item["id"]))
                        refreshed+=1
                except (ValueError,OverflowError,MemoryError):
                    continue
        flash(str(refreshed)+" aperçus actualisés dans la bibliothèque.")
        return redirect("/admin/modeles")

    @app.post("/admin/modeles/supprimer/<int:model_id>")
    @admin_required
    def fjord_model_delete(model_id):
        verify()
        with db() as c:c.execute("DELETE FROM private_models WHERE id=%s",(model_id,))
        flash("Modèle supprimé de la bibliothèque.")
        return redirect("/admin/modeles")

    @app.post("/admin/soumissions-pro/<int:quote_id>/supprimer")
    @admin_required
    def fjord_quote_delete(quote_id):
        verify()
        with db() as c:
            deleted=c.execute("DELETE FROM private_quotes WHERE id=%s RETURNING id",(quote_id,)).fetchone()
        if not deleted:abort(404)
        flash("Soumission supprimée.")
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

    @app.post("/admin/api/associer-impression")
    @admin_required
    def fjord_associer_impression():
        verify()
        from app import _octo_live_status, _octo_cache, _sync_octo_progress
        live=_octo_live_status()
        if not live or live["state"] not in ("printing","warmingup","resuming","paused"):
            return {"ok":False,"error":"Aucune impression en cours détectée."},409
        filename=(live.get("filename") or "").strip()
        if not filename or len(filename)>160:
            return {"ok":False,"error":"Nom du fichier d'impression indisponible ou trop long."},409
        try:ident=int(request.form.get("quote_id",""))
        except (ValueError,TypeError):abort(400)
        with db() as c:
            row=c.execute("SELECT id,public_number FROM private_quotes WHERE id=%s",(ident,)).fetchone()
            if not row:abort(404)
            c.execute("SELECT pg_advisory_xact_lock(7342026, 5)")
            c.execute("UPDATE private_quotes SET printer_job_name=NULL WHERE printer_job_name=%s AND id<>%s",(filename,ident))
            c.execute("UPDATE private_quotes SET printer_job_name=%s WHERE id=%s",(filename,ident))
        state=_sync_octo_progress()
        return {"ok":True,"message":"Impression associée à "+(row["public_number"] or "FJ-{:05d}".format(ident))+".","progress":state.get("progress")}

    @app.get("/admin/api/progression-auto")
    @admin_required
    def fjord_progression_auto():
        from app import _sync_octo_progress
        status=_sync_octo_progress()
        return {"ok":True,**status}

    @app.get("/admin/soumissions-pro")
    @admin_required
    def fjord_quotes():
        with db() as c:
            models=c.execute("SELECT id,name,(preview IS NOT NULL OR lower(filename) LIKE '%.stl' OR lower(filename) LIKE '%.3mf') AS has_preview FROM private_models ORDER BY created DESC LIMIT 1000").fetchall()
            quotes=c.execute("""SELECT id,model_id,customer,email,title,quantity,unit_price,shipping,
                     apply_taxes,military_discount,payment_status,paid_at,created,payment_token,production_status,production_progress,public_number,printer_job_name,
                     (SELECT signer FROM fjord_quote_acceptances a WHERE a.quote_id=private_quotes.id) AS accepted_by,
                     (SELECT accepted_at FROM fjord_quote_acceptances a WHERE a.quote_id=private_quotes.id) AS accepted_at,
                     live_url,live_token,live_enabled,live_expires
                     FROM private_quotes ORDER BY id DESC LIMIT 150""").fetchall()
            payment_setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        def quote_stage(q):
            if q["payment_status"]=="Payée":return "payees"
            if q.get("production_status")=="Terminée":return "terminees"
            if q.get("production_status")=="En production":return "production"
            if q["accepted_at"]:return "acceptees"
            return "attente"
        stages={q["id"]:quote_stage(q) for q in quotes}
        counters={k:sum(stage==k for stage in stages.values()) for k in ("attente","acceptees","payees","production","terminees")}
        interac_email=payment_setting["value"] if payment_setting else ""
        quote_totals={q["id"]:_quote_amounts(q)[3] for q in quotes}
        chosen=request.args.get("model_id","",type=str)
        atelier_model=next((m for m in models if str(m["id"])==chosen),None)
        from_atelier=bool(atelier_model and request.args.get("atelier")=="1")
        atelier_material=request.args.get("material","PETG") if from_atelier else "PETG"
        if atelier_material not in MATERIALS:atelier_material="PETG"
        atelier_layer=request.args.get("layer","0.2") if from_atelier else "0.2"
        if atelier_layer not in ("0.08","0.12","0.2","0.28"):atelier_layer="0.2"
        atelier_colors=request.args.get("colors","") if from_atelier else ""
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
.fj-status-board{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px;margin:15px 0 22px}
.fj-status-btn{border:1px solid #548da7;border-radius:12px;background:#16364b;color:#e9faff;padding:13px 10px;text-align:left;cursor:pointer}
.fj-status-btn strong{display:block;font-size:24px;margin-top:5px}
.fj-status-btn.active{outline:2px solid #7ee7ff;background:#21506a}
.fj-quote-card[hidden]{display:none!important}
.fj-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.fj-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.fj-two label{min-width:0}.fj-two input,.fj-two select{max-width:100%}
.fj-help{font-size:13px;color:#b4d1e1}
.fj-summary{background:#132e43;border:1px solid #58bce8;border-radius:12px;padding:20px}
.fj-summary strong{display:block;font-size:30px;color:#7ee7ff}
.fj-summary p{margin:5px 0}.fj-card{margin:18px 0}
.fj-preview-box{max-width:460px;margin:14px 0;padding:12px;background:#eaf4fa;border-radius:12px}
.fj-preview-box[hidden]{display:none!important}
.fj-preview-box .fj-help{color:#32546a!important}
.fj-model-photo{display:block;width:100%;height:auto;max-height:320px;object-fit:contain;border-radius:9px;background:#f0f7fb}
.fj-import-panel{background:#102b40;border:1px solid #426c83;border-radius:11px;padding:16px;margin:10px 0 18px}
.fj-import-panel label{margin-bottom:8px}
.fj-import-panel .fj-help{margin:7px 0 0}
.fj-import-panel [role=status]{min-height:24px;white-space:normal;overflow-wrap:anywhere}
body.light .fj-import-panel{background:#ecf7fd;border-color:#a7cfdf}
body.light .fj-import-panel .fj-help{color:#30556a}
.fj-library-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.fj-library-actions button{min-height:44px}
.fj-library-dialog{width:min(760px,94vw);max-height:85dvh;overflow:auto;padding:20px;
 background:#10283b;color:#eef9ff;border:1px solid #58bce8;border-radius:16px;box-shadow:0 20px 65px #0008}
.fj-library-dialog::backdrop{background:#000a}
.fj-library-header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.fj-library-header h3{margin:0}
.fj-library-search{box-sizing:border-box;width:100%;margin:14px 0;min-height:44px}
.fj-library-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}
.fj-library-item{display:flex;min-width:0;flex-direction:column;gap:8px;padding:10px;border:1px solid #42708b;border-radius:12px;background:#18384f}
.fj-library-item img,.fj-library-fallback{width:100%;height:120px;object-fit:contain;border-radius:8px;background:#eaf4fa}
.fj-library-fallback{display:grid;place-items:center;font-size:34px}
.fj-library-item strong,.fj-library-item small{display:block;overflow-wrap:anywhere}
.fj-library-item small{color:#c2d6e4;font-size:12px}
.fj-library-item button{min-height:44px;margin-top:auto}
.fj-library-dialog .fj-help{color:#c2d6e4}
body.light .fj-library-dialog{background:#fff;color:#15364b}
body.light .fj-library-item{background:#f0f8fc;border-color:#a1c9db}
body.light .fj-library-item small,body.light .fj-library-dialog .fj-help{color:#345970}
@media(max-width:500px){.fj-library-dialog{width:95vw;padding:12px}.fj-library-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.fj-library-item img,.fj-library-fallback{height:95px}.fj-library-item button{padding:9px 5px}}
.fj-quote-actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.fj-reset-button{border:1px solid #57b6db;background:transparent;color:#b6ecff;font-weight:700}
.fj-reset-button:hover,.fj-reset-button:focus-visible{background:#194660;color:#fff}
body.light .fj-reset-button{color:#126185;border-color:#318cb7}
body.light .fj-reset-button:hover,body.light .fj-reset-button:focus-visible{color:#fff}
@media(max-width:540px){.fj-quote-actions button{width:100%}}
.fj-payment-form{max-width:360px;margin:12px 0 6px}
.fj-bmo-details{border:1px solid #5386a1;border-radius:12px;margin:12px 0;padding:12px;overflow-wrap:anywhere}
.fj-bmo-details summary{cursor:pointer;font-weight:700;list-style-position:inside}
.fj-bmo-details .fj-bmo-row{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin:12px 0}
.fj-bmo-details .fj-bmo-row strong{overflow-wrap:anywhere}
.fj-bmo-details button{min-height:44px;padding:8px 14px}
.fj-bmo-details .fj-bmo-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:15px 0}
.fj-bmo-details .fj-bmo-actions a{display:inline-flex;align-items:center;min-height:44px}
.fj-bmo-details [role=status]{min-height:22px}
body.light .fj-bmo-details{border-color:#9bc9df}
.fj-payment-form label{font-size:14px;margin:0}
.fj-payment-form select{margin:6px 0;padding:10px}
.fj-payment-date{font-size:13px;color:#b4d1e1;margin:4px 0}
.fj-live-form{margin:15px 0 12px;padding:14px;border:1px solid #426c83;border-radius:12px}
.fj-live-form h4{margin:0 0 8px}
.fj-live-form label{font-size:14px}
.fj-live-form input,.fj-live-form select{font-size:15px;max-width:100%}
.fj-live-form .row{gap:8px}
.fj-live-form button{font-size:14px}
.fj-live-form .fj-watch-link{display:block;margin:9px 0;overflow-wrap:anywhere}
.fj-live-form .fj-live-copy{width:100%}
.fj-live-form .fj-live-off{background:transparent;color:#b5dcf1;border:1px solid #527c96}
body.light .fj-live-form{border-color:#b0d5e8}
body.light .fj-live-form .fj-live-off{color:#215676}
@media(max-width:700px){.fj-two{grid-template-columns:1fr}}
</style>
<div class="eyebrow">Visible uniquement par l'administrateur</div>
<div class="fj-head"><h1>Soumissions PRO</h1><a href="/admin/modeles">📚 Mes modèles 3D</a><a href="/admin">← Administration</a></div>
<p>Les coûts, taux machine et majorations sont privés. Le PDF remis au client indique seulement la pièce, le prix et les taxes applicables.</p>
<div class="card fj-card"><h2>Nouvelle soumission</h2>
{% if from_atelier %}<p class="fj-help" style="border-left:3px solid #58bce8;padding:10px 13px;background:#153247;border-radius:8px">✓ Création reçue de ton Atelier 3D : <strong>{{atelier_model.name}}</strong>. Le modèle est sélectionné, l'estimation démarre automatiquement et tu peux préparer le client et le PDF.{% if atelier_colors=='3mf' %} Couleurs de surface dans le 3MF : attribution AMS à vérifier avant impression.{% else %} Géométrie STL : la peinture AMS n'est pas dans le fichier, mais la photo est conservée.{% endif %}</p>{% endif %}
<form method="post" action="/admin/soumissions-pro/creer" enctype="multipart/form-data" style="max-width:none" id="fjQuote">{{csrf|safe}}
<input type="hidden" name="use_atelier_preview" value="{{'yes' if from_atelier else 'no'}}">
<div class="fj-two">
<label>Nom du client<input name="customer" maxlength="120" value="{{incoming.name if incoming else ''}}" required></label>
<label>Adresse courriel<input type="email" name="email" maxlength="180" value="{{incoming.email if incoming else ''}}"></label>
<label>Téléphone<input name="phone" maxlength="40" value="{{incoming.phone if incoming else ''}}"></label>
<label>Objet / nom de la pièce<input name="title" maxlength="160" value="{{'Impression 3D - demande #' ~ incoming.id if incoming else (atelier_model.name if from_atelier else '')}}" required></label>
<label>Modèle de ma bibliothèque<select name="model_id" id="fjModel"><option value="">Aucun / soumission manuelle</option>{% for m in models %}<option value="{{m.id}}" data-preview="{{'/admin/modeles/apercu/' ~ m.id if m.has_preview else ''}}" {% if chosen==m.id|string %}selected{% endif %}>{{m.name}}</option>{% endfor %}</select></label>
<label>Couleur principale de l'aperçu<input type="color" name="preview_color" value="#ffcc00" aria-label="Couleur principale"></label>
<label>Couleur des autres pièces (STL multiparties)<input type="color" name="preview_secondary" value="#111111" aria-label="Couleur secondaire"></label>
<label>Matériau<select name="material" id="fjMaterial">{% for m in materials %}<option value="{{m}}" {% if m==(incoming.material if incoming and incoming.material in materials else atelier_material) %}selected{% endif %}>{{m}}</option>{% endfor %}</select></label>
</div>
<div class="fj-import-panel">
<h3>🧊 Importer un modèle et calculer son prix</h3>
<div class="fj-library-actions"><button type="button" id="fjPickLibrary">📚 Choisir dans ma bibliothèque 3D</button>
<span class="fj-help">Utilise un STL ou 3MF déjà enregistré, sans le téléverser à nouveau.</span></div>
<dialog id="fjLibraryDialog" class="fj-library-dialog" aria-labelledby="fjLibraryHeading">
<div class="fj-library-header"><h3 id="fjLibraryHeading">📚 Mes modèles 3D</h3><button type="button" id="fjLibraryClose">✕ Fermer</button></div>
<label for="fjLibrarySearch">Rechercher une pièce par nom ou fichier</label>
<input id="fjLibrarySearch" class="fj-library-search" type="search" placeholder="Ex. support, engrenage, 3MF…" autocomplete="off">
<p id="fjLibraryStatus" role="status" class="fj-help" aria-live="polite"></p>
<div id="fjLibraryGrid" class="fj-library-grid"></div>
</dialog>
<label>Choisir un fichier STL ou 3MF déjà créé<input type="file" id="fjUpload" accept=".stl,.3mf"></label>
<div class="fj-two">
<label>Hauteur de couche<select id="fjLayer"><option value="0.08" {% if atelier_layer=='0.08' %}selected{% endif %}>0,08 mm — très fin</option><option value="0.12" {% if atelier_layer=='0.12' %}selected{% endif %}>0,12 mm — qualité</option><option value="0.2" {% if atelier_layer=='0.2' %}selected{% endif %}>0,20 mm — standard</option><option value="0.28" {% if atelier_layer=='0.28' %}selected{% endif %}>0,28 mm — rapide</option></select></label>
<label>Remplissage<select id="fjInfill"><option value="10">10 %</option><option value="15">15 %</option><option value="18" selected>18 %</option><option value="20">20 %</option><option value="30">30 %</option><option value="40">40 %</option><option value="50">50 %</option><option value="75">75 %</option><option value="100">100 %</option></select></label>
</div>
<p role="status" id="fjEstimateStatus" class="fj-help">Sélectionne un modèle ou importe un fichier pour estimer le poids, le temps et le prix automatiquement.</p>
<div class="fj-preview-box" id="fjPreviewBox" hidden><img id="fjPreview" class="fj-model-photo" alt="Aperçu 3D généré de la pièce"><p class="fj-help">Aperçu automatique de la pièce, également ajouté à la soumission PDF.</p></div>
<p class="fj-help">Le modèle importé est conservé dans ta bibliothèque privée. Le tranchage est une estimation générique (buse 0,4 mm), pas un profil d'impression X2D. Vérifie le prix avec Bambu Studio avant de l'envoyer.</p>
</div>
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
<label class="fj-military-discount"><input style="display:inline;width:auto;margin-right:8px" type="checkbox" name="military_discount" value="yes">🎖️ Rabais militaire — 5 % sur les articles (avant les taxes, hors livraison)</label>
<label><input style="display:inline;width:auto;margin-right:8px" type="checkbox" name="apply_taxes" value="yes">Appliquer TPS (5 %) et TVQ (9,975 %) — seulement si l'entreprise doit les percevoir</label>
<div class="fj-summary"><span>Prix final prévu, taxes incluses si sélectionnées</span><strong id="fjTotal">—</strong><p id="fjBreakdown" class="fj-help"></p></div>
<p class="fj-help">Le calcul est indicatif tant que le poids et la durée ne sont pas validés dans le trancheur. Aucun taux privé n'est ajouté au PDF du client.</p>
<div class="fj-quote-actions"><button type="submit" id="fjSaveQuote">Créer la soumission</button>
<button type="button" id="fjResetQuote" class="fj-reset-button">↺ Réinitialiser le formulaire</button></div></form></div>

<div class="card fj-card"><h2>💸 Paiement par virement Interac</h2>
<p>Ajoute l'adresse courriel associée à tes virements Interac. Une fois configurée, chaque PDF contiendra un bouton et un code QR menant à une page de paiement avec le montant exact et le numéro de soumission.</p>
<div class="fj-interac-settings">
<label>Courriel pour recevoir les virements Interac
<input form="fjord-save-global" type="email" name="interac_email" maxlength="180" value="{{interac_email}}" placeholder="Adresse liée à ton dépôt automatique"></label>
<p class="fj-help">Laisse ce champ vide pour masquer le paiement Interac. Assure-toi que cette adresse accepte les virements; idéalement, active le dépôt automatique auprès de ta banque. Le paiement reste à effectuer par le client dans son application bancaire, et le site ne confirme pas sa réception.</p>
</div>
</div>
<div class="card fj-card"><h2>Logo sur les soumissions</h2>
<p>Le logo officiel des Impressions du Fjord sera utilisé sur chaque PDF.</p>
<form method="post" action="/admin/soumissions-pro/logo" enctype="multipart/form-data">{{csrf|safe}}
<label>Remplacer le logo (PNG ou JPG)<input type="file" name="logo" accept="image/png,image/jpeg,image/webp" required></label>
<button type="submit">Mettre à jour le logo PDF</button></form></div>
<h2 id="soumissions-enregistrees">Tableau de suivi des soumissions</h2>
<p id="fjord-auto-progress" role="status" aria-live="polite" class="fj-help">🖨️ Vérification de la connexion OctoEverywhere…</p>
<div id="fjord-octo-association" class="card" style="display:none;margin:12px 0">
 <h3>🔗 Associer l'impression en cours</h3>
 <p id="fjord-octo-filename" class="fj-help"></p>
 <label>Soumission correspondante
 <select id="fjord-octo-quote"><option value="">Choisir une soumission…</option>
 {% for q in quotes %}<option value="{{q.id}}">{{q.public_number or ('FJ-%05d'|format(q.id))}} — {{q.customer}}</option>{% endfor %}
 </select></label>
 <button type="button" id="fjord-octo-bind">Associer cette impression</button>
 <p id="fjord-octo-bind-result" role="status"></p>
</div>
<form id="fjord-save-global" method="post" action="/admin/soumissions-pro/enregistrer-tout">{{csrf|safe}}<button type="submit" class="primary" style="font-weight:800;padding:14px 24px">💾 Enregistrer</button><span class="fj-help"> Sauvegarder les modifications des soumissions ci-dessous en une seule fois.</span><p id="fjord-save-feedback" role="status" aria-live="polite" class="fj-help"></p></form>
<p class="fj-help">Clique sur une catégorie pour filtrer les soumissions. Actualise la page pour voir les nouvelles acceptations.</p>
<div class="fj-status-board">
<button type="button" class="fj-status-btn active" data-stage="all">Toutes <strong>{{quotes|length}}</strong></button>
<button type="button" class="fj-status-btn" data-stage="attente">⏳ En attente <strong>{{counters.attente}}</strong></button>
<button type="button" class="fj-status-btn" data-stage="acceptees">✓ Acceptées <strong>{{counters.acceptees}}</strong></button>
<button type="button" class="fj-status-btn" data-stage="payees">💳 Payées <strong>{{counters.payees}}</strong></button>
<button type="button" class="fj-status-btn" data-stage="production">🖨️ En production <strong>{{counters.production}}</strong></button>
<button type="button" class="fj-status-btn" data-stage="terminees">📦 Terminées <strong>{{counters.terminees}}</strong></button>
</div>
<div class="grid" id="fj-quotes-grid">{% for q in quotes %}<div class="card fj-quote-card" data-quote-id="{{q.id}}" data-stage="{{stages[q.id]}}"><div class="eyebrow">{{q.public_number or ('FJ-%05d'|format(q.id))}} · {{q.created.strftime('%d-%m-%Y')}}</div><div style="margin:10px 0"><label>Numéro affiché publiquement<input form="fjord-save-global" name="public_number_{{q.id}}" maxlength="32" value="{{q.public_number or ('FJ-%05d'|format(q.id))}}" placeholder="FJ-00002"></label><label>Nom du travail dans Bambu Studio / OctoEverywhere<input form="fjord-save-global" name="printer_job_name_{{q.id}}" maxlength="160" value="{{q.printer_job_name or ''}}" placeholder="FJ-00002_BRP_gas_tank_can_holder"></label></div><h3>{{q.customer}}</h3><p>{{q.title}} · {{q.quantity}} exemplaire(s)</p>
<p>Prix unitaire : {{money(q.unit_price|float)}} · Livraison : {{money(q.shipping|float)}}{% if q.military_discount %} · 🎖️ Rabais militaire 5 % appliqué{% endif %}</p>
<label class="fj-military-discount"><input form="fjord-save-global" type="checkbox" name="military_discount_{{q.id}}" value="yes" {% if q.military_discount %}checked{% endif %} style="display:inline;width:auto;margin-right:8px">🎖️ Appliquer le rabais militaire de 5 % (PDF et paiement Interac)</label><div>
<label>État de fabrication
<select form="fjord-save-global" name="production_status_{{q.id}}">
<option value="À traiter" {% if q.production_status=='À traiter' %}selected{% endif %}>À traiter</option>
<option value="En production" {% if q.production_status=='En production' %}selected{% endif %}>🖨️ En production</option>
<option value="Terminée" {% if q.production_status=='Terminée' %}selected{% endif %}>📦 Terminée</option>
</select></label></div>
<div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap;margin:8px 0 16px"><label>Avancement de fabrication (%)<input form="fjord-save-global" type="number" name="production_progress_{{q.id}}" min="0" max="100" step="1" value="{{q.production_progress}}" style="width:105px"></label><span class="fj-help" data-auto-quote="{{q.id}}"></span></div>
{% if q.accepted_at %}<p><strong>✓ SOUMISSION ACCEPTÉE</strong> par {{q.accepted_by}} le {{q.accepted_at.strftime('%d-%m-%Y %H:%M UTC')}}</p>{% else %}<p>⏳ En attente d'acceptation</p>{% endif %}
{% if q.payment_token %}<p><a href="{{url_for('fjord_accept_quote',token=q.payment_token,_external=True)}}" target="_blank" rel="noopener">Lien d'acceptation à envoyer au client</a></p>{% endif %}
<div class="fj-payment-form">
<label for="fj-payment-{{q.id}}">Statut du paiement</label>
<select id="fj-payment-{{q.id}}" form="fjord-save-global" name="payment_status_{{q.id}}" aria-label="Statut de paiement de la soumission FJ-{{'%05d'|format(q.id)}}">
<option value="En attente" {% if q.payment_status=='En attente' %}selected{% endif %}>En attente</option>
<option value="Paiement partiel" {% if q.payment_status=='Paiement partiel' %}selected{% endif %}>Paiement partiel</option>
<option value="Payée" {% if q.payment_status=='Payée' %}selected{% endif %}>✅ Payée</option>
</select></div>
<section class="fj-live-form" aria-label="Diffusion de la soumission FJ-{{'%05d'|format(q.id)}}">
<h4>📹 Caméra en direct pour le client</h4>
<form method="post" action="/admin/soumissions-pro/{{q.id}}/diffusion">{{csrf|safe}}
<label for="fjord-live-{{q.id}}">Lien de visionnement OctoEverywhere Live ou YouTube Live</label>
<input type="url" id="fjord-live-{{q.id}}" name="live_url" maxlength="700"
  value="{{q.live_url or ''}}" placeholder="https://oe.ink/l/… ou https://youtube.com/live/…">
<label for="fjord-duration-{{q.id}}">Accès client valide pendant</label>
<select id="fjord-duration-{{q.id}}" name="live_hours">
<option value="12">12 heures</option><option value="24" selected>24 heures</option>
<option value="48">48 heures</option><option value="72">3 jours</option>
<option value="168">7 jours</option>
</select>
<p class="fj-help">Le flux se configure chez le fournisseur vidéo. Ne colle jamais l'adresse IP
de ton imprimante ni son code d'accès. Partage uniquement la commande qui s'imprime.</p>
<div class="row">
<button type="submit" name="live_action" value="enable">▶ Activer un nouveau lien</button>
<button type="submit" name="live_action" value="disable" class="fj-live-off">■ Arrêter / révoquer</button>
</div></form>
{% if q.live_enabled and q.live_token %}
<p class="fj-help">Lien privé de suivi :
{% if q.live_expires %}expire le {{q.live_expires.strftime('%d-%m-%Y à %H:%M')}} (heure du serveur).{% endif %}</p>
<input class="fj-live-copy" readonly aria-label="Lien client de la soumission FJ-{{'%05d'|format(q.id)}}" onclick="this.select()"
 value="{{url_for('fjord_live_view',token=q.live_token,_external=True)}}">
<a class="fj-watch-link" href="{{url_for('fjord_live_view',token=q.live_token)}}" target="_blank" rel="noopener noreferrer">↗ Voir la page client</a>
{% else %}
<p class="fj-help">Diffusion inactive : aucun client ne peut voir la caméra depuis cette soumission.</p>
{% endif %}
</section>
{% if q.payment_status=='Payée' and q.paid_at %}<p class="fj-payment-date">Paiement confirmé manuellement le {{q.paid_at.strftime('%d-%m-%Y')}}</p>{% endif %}
<a class="btn" href="/admin/soumissions-pro/{{q.id}}/pdf">⬇ Soumission PDF</a>
{% if q.model_id %}<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:12px">
<label>Corps<input form="fjord-save-global" type="color" name="preview_color_{{q.id}}" value="#ffcc00" aria-label="Couleur principale"></label>
<label>Autres pièces<input form="fjord-save-global" type="color" name="preview_secondary_{{q.id}}" value="#111111" aria-label="Couleur secondaire"></label>
</div>{% endif %}

<form method="post" action="/admin/soumissions-pro/{{q.id}}/supprimer" onsubmit="return confirm('Supprimer définitivement la soumission FJ-{{'%05d'|format(q.id)}} de {{q.customer|e}} ? Cette action est irréversible.');" style="margin-top:12px">{{csrf|safe}}<button type="submit" style="background:#842b35;color:white;border:1px solid #b74752">🗑️ Supprimer cette soumission</button></form>
{% if interac_email %}
<a href="/admin/soumissions-pro/{{q.id}}/paiement" target="_blank" rel="noopener noreferrer">💸 Ouvrir la page de paiement du client</a>
<details class="fj-bmo-details">
<summary>🏦 Préparer une demande de fonds BMO</summary>
<p class="fj-help">Ces renseignements correspondent à la soumission PDF. Les demandes de fonds sont envoyées dans BMO, pas automatiquement par ce site.</p>
<div class="fj-bmo-row"><div>Client<br><strong>{{q.customer}}</strong></div></div>
<div class="fj-bmo-row"><div>Courriel du client<br><strong id="bmoEmail{{q.id}}">{{q.email or 'Non renseigné'}}</strong></div>{% if q.email %}<button type="button" data-copy-id="bmoEmail{{q.id}}">Copier</button>{% endif %}</div>
<div class="fj-bmo-row"><div>Montant exact<br><strong id="bmoAmount{{q.id}}">{{money(quote_totals[q.id])}}</strong></div><button type="button" data-copy-id="bmoAmount{{q.id}}">Copier</button></div>
<div class="fj-bmo-row"><div>Numéro de soumission<br><strong id="bmoRef{{q.id}}">{{q.public_number or ('FJ-%05d'|format(q.id))}}</strong></div><button type="button" data-copy-id="bmoRef{{q.id}}">Copier</button></div>
<div class="fj-bmo-actions"><button type="button" data-bmo-copy="{{q.id}}">📋 Copier les renseignements</button>
<a href="https://www.bmo.com/" target="_blank" rel="noopener noreferrer">↗ Ouvrir BMO (site officiel)</a></div>
<p role="status" aria-live="polite" data-bmo-status="{{q.id}}" class="fj-help"></p>
<p class="fj-help">Dans BMO : Paiements et virements → Demande de fonds → client → montant → référence. Le client autorise ensuite la demande dans sa banque. Vérifie le dépôt avant de sélectionner « Payée ».</p>
</details>
{% endif %}</div>
{% else %}<p>Aucune soumission enregistrée.</p>{% endfor %}</div>
<script>
(function(){
 const f=document.getElementById("fjQuote"),o=document.getElementById("fjTotal"),d=document.getElementById("fjBreakdown");
 const selector=document.getElementById("fjModel"),image=document.getElementById("fjPreview");
 const libraryButton=document.getElementById("fjPickLibrary"),libraryDialog=document.getElementById("fjLibraryDialog");
 const libraryClose=document.getElementById("fjLibraryClose"),librarySearch=document.getElementById("fjLibrarySearch");
 const libraryGrid=document.getElementById("fjLibraryGrid"),libraryStatus=document.getElementById("fjLibraryStatus");
 let libraryModels=[];
 function renderLibrary(){
   const query=librarySearch.value.trim().toLocaleLowerCase("fr");
   const matches=libraryModels.filter(m=>(m.name+" "+m.filename).toLocaleLowerCase("fr").includes(query));
   libraryGrid.replaceChildren();
   libraryStatus.textContent=matches.length+" modèle(s) trouvé(s).";
   if(!matches.length){const p=document.createElement("p");p.textContent="Aucune pièce correspondante.";libraryGrid.append(p);return}
   for(const m of matches){
     const item=document.createElement("article");item.className="fj-library-item";
     if(m.has_preview){
       const img=document.createElement("img");img.loading="lazy";img.alt="Aperçu de "+m.name;
       img.src="/admin/modeles/apercu/"+encodeURIComponent(m.id);item.append(img);
     }else{
       const placeholder=document.createElement("div");placeholder.className="fj-library-fallback";
       placeholder.textContent="🧊";item.append(placeholder);
     }
     const name=document.createElement("strong");name.textContent=m.name;item.append(name);
     const filename=document.createElement("small");filename.textContent=m.filename;item.append(filename);
     const choose=document.createElement("button");choose.type="button";choose.textContent="Choisir cette pièce";
     choose.addEventListener("click",()=>{
       let option=Array.from(selector.options).find(o=>o.value===String(m.id));
       if(!option){
         option=new Option(m.name,String(m.id));option.dataset.preview=m.has_preview?"/admin/modeles/apercu/"+m.id:"";
         selector.add(option);
       }
       selector.value=String(m.id);
       const title=f.elements.namedItem("title");
       if(!title.value.trim())title.value=m.name.slice(0,160);
       libraryDialog.close();
       estimate(); // Réutilise l'aperçu, le tranchage et le calcul déjà en place.
     });
     item.append(choose);libraryGrid.append(item);
   }
 }
 librarySearch.addEventListener("input",renderLibrary);
 libraryClose.addEventListener("click",()=>libraryDialog.close());
 libraryDialog.addEventListener("click",e=>{if(e.target===libraryDialog)libraryDialog.close()});
 libraryButton.addEventListener("click",async()=>{
   libraryButton.disabled=true;
   libraryStatus.textContent="Chargement de la bibliothèque privée…";
   libraryGrid.replaceChildren();
   libraryDialog.showModal();
   try{
     const response=await fetch("/admin/modeles/api/liste",{credentials:"same-origin",headers:{"Accept":"application/json"}});
     if(!response.ok||!(response.headers.get("content-type")||"").includes("application/json"))
       throw Error("Bibliothèque indisponible ou session expirée.");
     const data=await response.json();
     if(!data.ok||!Array.isArray(data.models))throw Error("Réponse invalide de la bibliothèque.");
     libraryModels=data.models;
     librarySearch.value="";
     renderLibrary();
     librarySearch.focus();
   }catch(err){
     libraryStatus.textContent="⚠ "+String(err.message||err);
   }finally{libraryButton.disabled=false}
 });
 const previewBox=document.getElementById("fjPreviewBox");
 image.onload=()=>{previewBox.hidden=!selector.value || !image.getAttribute("src")};
 image.onerror=()=>{previewBox.hidden=true};
 const status=document.getElementById("fjEstimateStatus"),fileInput=document.getElementById("fjUpload");
 const save=document.getElementById("fjSaveQuote"),resetQuote=document.getElementById("fjResetQuote");
 const grams=f.elements.namedItem("grams"),hours=f.elements.namedItem("hours");
 const material=f.elements.namedItem("material"),csrf=f.elements.namedItem("csrf");
 const layer=document.getElementById("fjLayer"),infill=document.getElementById("fjInfill");
 let requestNumber=0;
 resetQuote.addEventListener("click",()=>{
   if(!confirm("Réinitialiser cette nouvelle soumission ? Les informations saisies seront effacées. Les soumissions déjà enregistrées ne seront pas touchées."))return;
   // Ignore any older slicing/import response that finishes after reset.
   ++requestNumber;
   f.reset();
   for(const name of ["customer","email","phone","title","description","override_price"]){
     f.elements.namedItem(name).value="";
   }
   // Keep the library on the server; remove only temporary dropdown options.
   for(const opt of [...selector.options]){
     if(opt.dataset.imported==="1")opt.remove();
   }
   selector.value="";
   material.value="PETG";layer.value="0.2";infill.value="18";
   fileInput.value="";
   f.elements.namedItem("preview").value="";
   image.removeAttribute("src");previewBox.hidden=true;
   busy(false);
   update();
   message("Formulaire réinitialisé. Tu peux préparer une nouvelle soumission. Les modèles déjà importés restent dans ta bibliothèque.");
 });
 const currency=n=>new Intl.NumberFormat("fr-CA",{style:"currency",currency:"CAD"}).format(n);
 function n(key){const el=f.elements.namedItem(key);return Number(el&&el.value||0)}
 function update(){
  if(grams.value===""||hours.value===""){o.textContent="Estimation en attente";d.textContent="Poids et durée nécessaires pour établir le prix.";return}
  const c=(n("grams")/1000*n("filament_kg")*1.1+n("hours")*n("machine_hour")+n("setup_cost"));
  const generated=c*(1+n("markup")/100);
  const override=f.elements.namedItem("override_price");
  const unit=override.value.trim()===""?generated:Number(override.value);
  const merchandise=Math.round(unit*n("quantity")*100)/100;
  const discount=f.elements.namedItem("military_discount").checked?Math.round(merchandise*5)/100:0;
  const subtotal=Math.round((merchandise-discount+n("shipping"))*100)/100;
  const tax=f.elements.namedItem("apply_taxes").checked?
    Math.round(subtotal*.05*100)/100+Math.round(subtotal*.09975*100)/100:0;
  o.textContent=currency(Math.round((subtotal+tax)*100)/100);
  d.textContent="Coût de base : "+currency(c)+" · Prix unitaire : "+currency(unit)+
    (discount?" · Rabais militaire (5 %) : −"+currency(discount):"")+
    " · Sous-total : "+currency(subtotal)+" · Taxes : "+currency(tax);
 }
 f.addEventListener("input",update);f.addEventListener("change",update);
 function message(text){status.textContent=text}
 function busy(value){save.disabled=value;save.textContent=value?"Calcul en cours…":"Créer la soumission"}
 function updateImage(){
   const src=selector.selectedOptions[0]?.dataset.preview||"";
   previewBox.hidden=true;
   if(src){
     if(f.elements.namedItem("use_atelier_preview")?.value==="yes")image.src=src;
     else{
       const primary=f.elements.namedItem("preview_color").value;
       const secondary=f.elements.namedItem("preview_secondary").value;
       image.src=src+"?primary="+encodeURIComponent(primary)+"&secondary="+encodeURIComponent(secondary);
     }
   }else image.removeAttribute("src");
 }
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
 for(const field of ["preview_color","preview_secondary"]){
   f.elements.namedItem(field).addEventListener("input",()=>{
     const original=f.elements.namedItem("use_atelier_preview");
     if(original)original.value="no"; // Custom recoloring requested by owner.
     updateImage();
   });
 }
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
   opt.dataset.preview="/admin/modeles/apercu/"+result.id;
   opt.dataset.imported="1";
   selector.add(opt);selector.value=String(result.id);
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
</script>
<script>
const quoteSave=document.getElementById('fjord-save-global');
const quoteCards=[...document.querySelectorAll('.fj-quote-card')];
for(const card of quoteCards){for(const field of card.querySelectorAll('[form="fjord-save-global"]')){
 field.addEventListener('change',()=>{card.dataset.edited='1'});
 field.addEventListener('input',()=>{card.dataset.edited='1'});
}}
quoteSave?.addEventListener('submit',async event=>{
 event.preventDefault();
 const message=document.getElementById('fjord-save-feedback');
 const button=quoteSave.querySelector('button[type="submit"]');
 const temporarilyDisabled=[];
 if(button?.disabled)return;
 for(const card of quoteCards){
  if(card.dataset.edited==='1')continue;
  for(const field of card.querySelectorAll('[form="fjord-save-global"]')){
   if(!field.disabled){field.disabled=true;temporarilyDisabled.push(field);}
  }
 }
 if(button){button.disabled=true;button.textContent='Enregistrement…';}
 if(message)message.textContent='Enregistrement des modifications…';
 try{
  const response=await fetch(quoteSave.action,{method:'POST',body:new FormData(quoteSave),
   credentials:'same-origin',headers:{'Accept':'application/json'}});
  if(!(response.headers.get('content-type')||'').includes('application/json'))
   throw Error('Session expirée ou réponse inattendue. Reconnecte-toi, puis réessaie.');
  const result=await response.json();
  if(!response.ok || !result.ok)throw Error(result.error||'Impossible de sauvegarder.');
  if(message)message.textContent='✓ '+result.message;
  window.location.assign('/admin/soumissions-pro#soumissions-enregistrees');
 }catch(error){
  if(message)message.textContent='⚠ '+String(error.message||error);
 }finally{
  for(const field of temporarilyDisabled)field.disabled=false;
  if(button){button.disabled=false;button.textContent='💾 Enregistrer';}
 }
});
(function(){
 const label=document.getElementById('fjord-auto-progress');
 let active=false;
 async function checkPrinter(){
  if(document.hidden||active)return;
  active=true;
  try{
   const response=await fetch('/admin/api/progression-auto',{cache:'no-store',credentials:'same-origin'});
   if(!response.ok)throw Error('Connexion indisponible');
   const data=await response.json();
   if(label)label.textContent='🖨️ '+data.reason;
   const bindBox=document.getElementById('fjord-octo-association');
   if(bindBox){
    bindBox.style.display=(data.connected && !data.matched && data.filename)?'block':'none';
    document.getElementById('fjord-octo-filename').textContent=data.filename?'Travail détecté : '+data.filename:'';
   }
   if(data.matched && Number.isInteger(data.id)){
    const card=document.querySelector('.fj-quote-card[data-quote-id="'+data.id+'"]');
    if(card){
     const hint=card.querySelector('[data-auto-quote]');
     if(hint)hint.textContent='↻ Automatique : '+data.progress+' %';
     if(card.dataset.edited!=='1'){
      const progress=card.querySelector('[name="production_progress_'+data.id+'"]');
      const status=card.querySelector('[name="production_status_'+data.id+'"]');
      if(progress)progress.value=String(data.progress);
      if(status)status.value=data.status;
     }
    }
   }
  }catch(error){
   if(label)label.textContent='⚠ Suivi OctoEverywhere temporairement indisponible.';
  }finally{active=false}
 }
 const bind=document.getElementById('fjord-octo-bind');
 bind?.addEventListener('click',async()=>{
  const quote=document.getElementById('fjord-octo-quote').value;
  const feedback=document.getElementById('fjord-octo-bind-result');
  if(!quote){feedback.textContent='Choisis la soumission correspondante.';return;}
  const csrf=document.querySelector('#fjord-save-global [name="csrf"]').value;
  const payload=new FormData();payload.append('csrf',csrf);payload.append('quote_id',quote);
  bind.disabled=true;
  try{
   const resp=await fetch('/admin/api/associer-impression',{method:'POST',body:payload,credentials:'same-origin'});
   const result=await resp.json();
   if(!resp.ok||!result.ok)throw Error(result.error||'Association impossible');
   feedback.textContent='✓ '+result.message;
   await checkPrinter();
  }catch(e){feedback.textContent='⚠ '+String(e.message||e)}
  finally{bind.disabled=false}
 });
 checkPrinter();
 setInterval(checkPrinter,30000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkPrinter()});
})();
document.querySelectorAll('[data-copy-id]').forEach(button=>button.addEventListener('click',async()=>{
 const el=document.getElementById(button.dataset.copyId);
 if(!el)return;
 const card=button.closest('.fj-bmo-details');
 const feedback=card?.querySelector('[role=status]');
 try{await navigator.clipboard.writeText(el.textContent.trim());if(feedback)feedback.textContent='✓ Renseignement copié.';}
 catch(e){if(feedback)feedback.textContent='Copie automatique impossible : sélectionne le renseignement et copie-le.';}
}));
document.querySelectorAll('[data-bmo-copy]').forEach(button=>button.addEventListener('click',async()=>{
 const id=button.dataset.bmoCopy;
 const card=button.closest('.fj-bmo-details');
 const email=document.getElementById('bmoEmail'+id)?.textContent.trim()||'';
 const amount=document.getElementById('bmoAmount'+id)?.textContent.trim()||'';
 const reference=document.getElementById('bmoRef'+id)?.textContent.trim()||'';
 const feedback=card?.querySelector('[role=status]');
 const text=['Demande de fonds Interac — Les Impressions du Fjord',
   'Client : '+(card?.querySelector('.fj-bmo-row strong')?.textContent.trim()||''),
   'Courriel : '+email,'Montant : '+amount,'Référence : '+reference].join('\n');
 try{await navigator.clipboard.writeText(text);if(feedback)feedback.textContent='✓ Informations copiées. Ouvre BMO et crée la demande de fonds.';}
 catch(e){if(feedback)feedback.textContent='Copie automatique indisponible : utilise les boutons Copier de chaque champ.';}
}));
document.querySelectorAll('.fj-status-btn').forEach(button=>button.addEventListener('click',()=>{
 const selected=button.dataset.stage;
 document.querySelectorAll('.fj-status-btn').forEach(b=>b.classList.toggle('active',b===button));
 document.querySelectorAll('.fj-quote-card').forEach(card=>{card.hidden=selected!=='all' && card.dataset.stage!==selected});
}));
</script>""",models=models,quotes=quotes,quote_totals=quote_totals,stages=stages,counters=counters,chosen=chosen,materials=MATERIALS,
          money=_money,csrf=csrfinput(),incoming=incoming,interac_email=interac_email,
          from_atelier=from_atelier,atelier_model=atelier_model,atelier_material=atelier_material,
          atelier_layer=atelier_layer,atelier_colors=atelier_colors)



    @app.errorhandler(400)
    def fjord_quote_bad_save(error):
        if request.path!="/admin/soumissions-pro/enregistrer-tout":
            return error
        message=error.description
        if message=="The browser (or proxy) sent a request that this server could not understand.":
            message="Les informations de sauvegarde ne sont plus valides. Recharge la page, reconnecte-toi si nécessaire, puis réessaie."
        if request.accept_mimetypes.best=="application/json":
            return {"ok":False,"error":message},400
        return page("Soumission non enregistrée", """
        <section class="card"><h1>Soumission non enregistrée</h1>
        <p>{{message}}</p><p>Aucune modification n'a été sauvegardée.</p>
        <a class="btn" href="/admin/soumissions-pro">Retour aux soumissions PRO</a></section>""",
        message=message),400

    @app.post("/admin/soumissions-pro/enregistrer-tout")
    @admin_required
    def fjord_quote_save_global():
        verify()
        with db() as c:
            c.execute("SELECT pg_advisory_xact_lock(7342026,4)")
            interac=request.form.get("interac_email","").strip().lower()[:180]
            if interac and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",interac):abort(400,"Adresse Interac invalide : vérifie le courriel.")
            rows=c.execute("SELECT id,model_id FROM private_quotes ORDER BY id DESC LIMIT 150").fetchall()
            changes=[]
            for q in rows:
                suffix="_"+str(q["id"])
                number=request.form.get("public_number"+suffix,"").strip().upper()
                if not number:
                    continue
                job=request.form.get("printer_job_name"+suffix,"").strip()
                production=request.form.get("production_status"+suffix,"")
                payment=request.form.get("payment_status"+suffix,"")
                raw=request.form.get("production_progress"+suffix,"0").strip() or "0"
                if not re.fullmatch(r"FJ-[0-9]{1,8}",number):abort(400,"Numéro invalide : "+str(q["id"]))
                if len(job)>160 or production not in ("À traiter","En production","Terminée"):abort(400,"État de fabrication ou nom du travail invalide.")
                if payment not in ("En attente","Paiement partiel","Payée"):abort(400,"Statut du paiement invalide.")
                if not re.fullmatch(r"(?:100|[0-9]|[1-9][0-9])",raw):abort(400,"Progression invalide : entre 0 et 100 %.")
                progress=int(raw)
                if production=="Terminée":progress=100
                elif production=="À traiter":progress=0
                elif progress==100:production="Terminée"
                primary=request.form.get("preview_color"+suffix,"")
                secondary=request.form.get("preview_secondary"+suffix,"")
                preview=None
                if q.get("model_id") and primary and secondary:
                    if not all(re.fullmatch(r"#[0-9a-fA-F]{6}",x) for x in (primary,secondary)):abort(400)
                    model=c.execute("SELECT filename,filedata FROM private_models WHERE id=%s",(q["model_id"],)).fetchone()
                    if model and model["filename"].lower().endswith((".stl",".3mf")):
                        preview=make_model_preview(model["filedata"],model["filename"],color=primary,secondary_color=secondary)
                military_discount=request.form.get("military_discount"+suffix)=="yes"
                changes.append((q["id"],number,job,production,progress,payment,preview,military_discount))
            numbers=[x[1] for x in changes]
            if len(numbers)!=len(set(numbers)):abort(409,"Numéros FJ en double.")
            for ident,number,*_ in changes:
                duplicate=c.execute("SELECT id FROM private_quotes WHERE public_number=%s AND id<>%s",(number,ident)).fetchone()
                if duplicate and all(v[0]!=duplicate["id"] for v in changes):
                    abort(409,"Numéro FJ déjà utilisé.")
            c.execute("""INSERT INTO settings(key,value) VALUES('fjord_interac_email',%s)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value""",(interac,))
            # Two-phase numbering allows swapping two numbers without a unique-index collision.
            for ident,*_ in changes:
                c.execute("UPDATE private_quotes SET public_number=NULL WHERE id=%s",(ident,))
            for ident,number,job,production,progress,payment,preview,military_discount in changes:
                c.execute("""UPDATE private_quotes SET public_number=%s,printer_job_name=%s,
                  production_status=%s,production_progress=%s,payment_status=%s,
                  military_discount=%s,
                  paid_at=CASE WHEN %s='Payée' THEN COALESCE(paid_at,NOW()) ELSE NULL END
                  WHERE id=%s""",(number,job or None,production,progress,payment,military_discount,payment,ident))
                if preview:
                    c.execute("UPDATE private_quotes SET preview_mime=%s,preview=%s WHERE id=%s",
                              (preview[0],preview[1],ident))
        message=str(len(changes))+" soumission(s) enregistrée(s)."
        if request.accept_mimetypes.best=="application/json":return {"ok":True,"message":message}
        flash(message)
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

    @app.post("/admin/soumissions-pro/<int:quote_id>/enregistrer")
    @admin_required
    def fjord_quote_save_all(quote_id):
        verify()
        number=request.form.get("public_number","").strip().upper()
        job=request.form.get("printer_job_name","").strip()
        production=request.form.get("production_status","")
        payment=request.form.get("payment_status","")
        progress_text=request.form.get("production_progress","")
        primary=request.form.get("preview_color","")
        secondary=request.form.get("preview_secondary","")
        if not re.fullmatch(r"FJ-[0-9]{1,8}",number):abort(400,"Numéro de soumission invalide")
        if len(job)>160 or production not in ("À traiter","En production","Terminée"):abort(400)
        if payment not in ("En attente","Paiement partiel","Payée"):abort(400)
        if not re.fullmatch(r"(?:100|[0-9]|[1-9][0-9])",progress_text):abort(400)
        progress=int(progress_text)
        if production=="Terminée":progress=100
        elif production=="À traiter":progress=0
        elif progress==100:production="Terminée"
        with db() as c:
            c.execute("SELECT pg_advisory_xact_lock(7342026, 4)")
            existing=c.execute("SELECT id FROM private_quotes WHERE public_number=%s AND id<>%s",(number,quote_id)).fetchone()
            if existing:abort(409,"Numéro déjà utilisé")
            q=c.execute("SELECT model_id FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            if not q:abort(404)
            preview=None
            if q.get("model_id") and primary and secondary:
                if not all(re.fullmatch(r"#[0-9a-fA-F]{6}",color) for color in (primary,secondary)):abort(400)
                model=c.execute("SELECT filename,filedata FROM private_models WHERE id=%s",(q["model_id"],)).fetchone()
                if model and model["filename"].lower().endswith((".stl",".3mf")):
                    preview=make_model_preview(model["filedata"],model["filename"],color=primary,secondary_color=secondary)
            c.execute("""UPDATE private_quotes SET public_number=%s,printer_job_name=%s,
                production_status=%s,production_progress=%s,payment_status=%s,
                paid_at=CASE WHEN %s='Payée' THEN COALESCE(paid_at,NOW()) ELSE NULL END
                WHERE id=%s""",(number,job or None,production,progress,payment,payment,quote_id))
            if preview:
                c.execute("UPDATE private_quotes SET preview_mime=%s,preview=%s WHERE id=%s",
                          (preview[0],preview[1],quote_id))
        flash("Toutes les informations de la soumission ont été enregistrées.")
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

    @app.post("/admin/soumissions-pro/<int:quote_id>/identification")
    @admin_required
    def fjord_quote_identification(quote_id):
        verify()
        number=request.form.get("public_number","").strip().upper()
        job=request.form.get("printer_job_name","").strip()
        if not re.fullmatch(r"FJ-[0-9]{1,8}",number):abort(400,"Numéro attendu : FJ-00002")
        if len(job)>160:abort(400)
        with db() as c:
            existing=c.execute("SELECT id FROM private_quotes WHERE public_number=%s AND id<>%s",(number,quote_id)).fetchone()
            if existing:abort(409,"Numéro déjà utilisé.")
            row=c.execute("SELECT id FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            if not row:abort(404)
            c.execute("UPDATE private_quotes SET public_number=%s,printer_job_name=%s WHERE id=%s",(number,job or None,quote_id))
        flash("Numéro public et nom du travail enregistrés.")
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

    @app.post("/admin/soumissions-pro/<int:quote_id>/progression")
    @admin_required
    def fjord_production_progress(quote_id):
        verify()
        raw=request.form.get("production_progress","")
        if not re.fullmatch(r"(?:100|[0-9]|[1-9][0-9])",raw):abort(400)
        with db() as c:
            q=c.execute("SELECT id,production_status FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            if not q:abort(404)
            progress=int(raw)
            status="Terminée" if progress==100 else ("En production" if progress>0 else q["production_status"])
            c.execute("UPDATE private_quotes SET production_progress=%s,production_status=%s WHERE id=%s",(progress,status,quote_id))
        flash("Progression de fabrication enregistrée.")
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

    @app.post("/admin/soumissions-pro/<int:quote_id>/production")
    @admin_required
    def fjord_production_status(quote_id):
        verify()
        status=request.form.get("production_status","")
        if status not in ("À traiter","En production","Terminée"):abort(400)
        with db() as c:
            row=c.execute("SELECT id FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            if not row:abort(404)
            c.execute("UPDATE private_quotes SET production_status=%s, production_progress=CASE WHEN %s='Terminée' THEN 100 WHEN %s='À traiter' THEN 0 ELSE LEAST(production_progress,99) END WHERE id=%s",(status,status,status,quote_id))
        flash("État de fabrication mis à jour.")
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

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

    @app.post("/admin/soumissions-pro/<int:quote_id>/statut-paiement")
    @admin_required
    def fjord_quote_payment_status(quote_id):
        verify()
        status=request.form.get("payment_status","")
        if status not in ("En attente","Paiement partiel","Payée"):
            abort(400,"Statut de paiement invalide.")
        with db() as c:
            result=c.execute("""UPDATE private_quotes
                SET payment_status=%s,
                    paid_at=CASE WHEN %s='Payée'
                                 THEN COALESCE(paid_at,NOW()) ELSE NULL END
                WHERE id=%s RETURNING id""",(status,status,quote_id)).fetchone()
        if not result:abort(404)
        flash("Soumission FJ-{:05d} : statut de paiement « {} » enregistré.".format(quote_id,status))
        return redirect(url_for("fjord_quotes")+"#soumissions-enregistrees")


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
        preview_color=request.form.get("preview_color","#168ac2")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}",preview_color):abort(400)
        preview_secondary=request.form.get("preview_secondary","#111111")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}",preview_secondary):abort(400)
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
        military_discount=request.form.get("military_discount")=="yes"
        want_atelier_preview=request.form.get("use_atelier_preview")=="yes"
        atelier_preview=False
        model_input=request.form.get("model_id","").strip()
        try:model_id=int(model_input) if model_input else None
        except ValueError:abort(400)
        preview=_image(request.files.get("preview"))
        with db() as c:
            if model_id:
                model=c.execute("""SELECT preview,preview_mime,filename,filedata
                                   FROM private_models WHERE id=%s""",(model_id,)).fetchone()
                if not model:abort(400,"Modèle introuvable")
                if not preview and want_atelier_preview and model["preview"] and model["preview_mime"] in ("image/png","image/jpeg","image/webp"):
                    preview=(model["preview_mime"],model["preview"])
                    atelier_preview=True
                if not preview and model["filename"].lower().endswith((".stl", ".3mf")):
                    try:preview=make_model_preview(model["filedata"],model["filename"],color=preview_color,secondary_color=preview_secondary)
                    except (ValueError, OverflowError):preview=None
                if not preview:
                    if model["preview"]:
                        preview=(model["preview_mime"],model["preview"])
                    elif model["filename"].lower().endswith((".stl", ".3mf")):
                        try:
                            preview=make_model_preview(model["filedata"],model["filename"])
                        except (ValueError, OverflowError):
                            preview=None
                        if preview:
                            c.execute("""UPDATE private_models SET preview=%s,preview_mime=%s
                                         WHERE id=%s AND preview IS NULL""",
                                      (preview[1],preview[0],model_id))
            c.execute("SELECT pg_advisory_xact_lock(7342026, 4)")
            last=c.execute("""SELECT GREATEST(
                COALESCE(MAX(CASE WHEN public_number ~ '^FJ-[0-9]+$'
                    THEN substring(public_number from 4)::bigint END),0),
                COALESCE(MAX(id),0)
            ) AS n FROM private_quotes""").fetchone()
            last=last["n"] if last else 0
            next_number="FJ-{:05d}".format(last+1)
            result=c.execute("""INSERT INTO private_quotes
               (customer,email,phone,title,description,material,quantity,unit_price,
                shipping,apply_taxes,military_discount,atelier_preview,model_id,preview,preview_mime,grams,hours,filament_kg,
                machine_hour,setup_cost,markup,payment_token,public_number)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",(customer,email,phone,title,description,material,
               int(quantity),unit,shipping,taxes,military_discount,atelier_preview,model_id,
               preview[1] if preview else None,preview[0] if preview else None,
               grams,hours,filament_kg,machine_hour,setup_cost,markup,
               secrets.token_urlsafe(32),next_number)).fetchone()
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


    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS fjord_quote_acceptances (
          quote_id BIGINT PRIMARY KEY REFERENCES private_quotes(id) ON DELETE CASCADE,
          accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          signer TEXT NOT NULL, quote_snapshot TEXT NOT NULL,
          quote_hash TEXT NOT NULL, terms_version TEXT NOT NULL,
          ip_hash TEXT, user_agent TEXT)""")

    def quote_snapshot(q):
        fields=("id","customer","email","title","description","material","quantity","unit_price","shipping","apply_taxes")
        snapshot={k:str(q[k]) if q[k] is not None else None for k in fields}
        # Ne pas invalider les acceptations historiques sans rabais.
        if q.get("military_discount"):
            snapshot["military_discount"]="True"
        return json.dumps(snapshot,ensure_ascii=False,sort_keys=True)

    @app.get("/apercu-soumission/<token>/image")
    def fjord_client_quote_image(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,90}",token):abort(404)
        with db() as c:
            q=c.execute("SELECT preview,preview_mime FROM private_quotes WHERE payment_token=%s",(token,)).fetchone()
        if not q or not q["preview"] or q["preview_mime"] not in ("image/png","image/jpeg","image/webp"):abort(404)
        response=send_file(io.BytesIO(q["preview"]),mimetype=q["preview_mime"])
        response.headers["Cache-Control"]="private, no-store"
        response.headers["X-Robots-Tag"]="noindex, nofollow"
        return response

    @app.get("/apercu-soumission/<token>/modele.stl")
    def fjord_client_quote_mesh(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,90}",token):abort(404)
        with db() as c:
            model=c.execute("""SELECT m.filename,m.filedata FROM private_quotes q
                JOIN private_models m ON m.id=q.model_id WHERE q.payment_token=%s""",(token,)).fetchone()
        if not model or not model["filename"].lower().endswith((".stl",".3mf")):abort(404)
        data=bytes(model["filedata"])
        if len(data)>MAX_MODEL:abort(413)
        if model["filename"].lower().endswith(".3mf"):
            from quote_estimator import _stl_from_3mf, EstimationError
            try:data=_stl_from_3mf(data)
            except (EstimationError,ValueError,OverflowError):abort(422)
        response=send_file(io.BytesIO(data),mimetype="model/stl",download_name="apercu.stl")
        response.headers["Cache-Control"]="private, no-store"
        response.headers["X-Robots-Tag"]="noindex, nofollow"
        response.headers["Content-Disposition"]="inline"
        return response

    @app.route("/accepter-soumission/<token>",methods=["GET","POST"])
    def fjord_accept_quote(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,90}",token):abort(404)
        with db() as c:
            q=c.execute("SELECT * FROM private_quotes WHERE payment_token=%s",(token,)).fetchone()
            accepted=c.execute("SELECT signer,accepted_at,quote_hash FROM fjord_quote_acceptances WHERE quote_id=%s",(q["id"],)).fetchone() if q else None
        if not q:abort(404)
        snapshot=quote_snapshot(q)
        digest=hashlib.sha256(snapshot.encode()).hexdigest()
        changed=bool(accepted and accepted["quote_hash"]!=digest)
        if request.method=="POST" and not accepted:
            verify()
            signer=request.form.get("signer","").strip()
            checked=request.form.get("agree")=="yes" and request.form.get("final_sale")=="yes"
            if not (2<=len(signer)<=150 and checked):
                flash("Indiquez votre nom et cochez les deux confirmations.")
            elif request.form.get("quote_hash")!=digest:
                flash("La soumission a changé. Veuillez la relire.")
            else:
                ip=request.remote_addr or ""
                iphash=hashlib.sha256((str(app.secret_key)+ip).encode()).hexdigest()
                with db() as c:
                    c.execute("""INSERT INTO fjord_quote_acceptances
                     (quote_id,signer,quote_snapshot,quote_hash,terms_version,ip_hash,user_agent)
                     VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(quote_id) DO NOTHING""",
                     (q["id"],signer,snapshot,digest,"QC-2026-10",iphash,(request.user_agent.string or "")[:350]))
                return redirect(url_for("fjord_accept_quote",token=token))
        subtotal,gst,qst,total=_quote_amounts(q)
        response=make_response(page("Acceptation de soumission",'''<section class="tracking-panel">
<h1 style="font-size:clamp(1.5rem,4vw,2.5rem);overflow-wrap:anywhere">Acceptation de la soumission {{q.public_number or ('FJ-%05d'|format(q.id))}}</h1>
<p><strong>Projet :</strong> {{q.title}}</p><p>{{q.description}}</p>
<p><strong>Matériau :</strong> {{q.material}} · <strong>Quantité :</strong> {{q.quantity}}</p>
{% if q.military_discount %}<p><strong>🎖️ Rabais militaire de 5 % inclus</strong> (avant taxes, sur les articles).</p>{% endif %}
<p><strong>Prix total :</strong> {{total}}</p>
{% if q.model_id or q.preview %}
<section class="card" style="margin:20px 0;padding:16px">
<h2>Votre création 3D</h2>
{% if q.model_id %}
<div id="fjordQuote3D" style="height:340px;max-width:100%;background:#102235;border-radius:12px;position:relative;overflow:hidden" role="img" aria-label="Aperçu 3D interactif de votre pièce">
{% if q.preview %}<img id="fjordQuoteFallback" src="{{url_for('fjord_client_quote_image',token=token)}}" alt="Aperçu de votre objet" style="width:100%;height:100%;object-fit:contain">{% endif %}
</div>
<p style="font-size:13px">Tournez la pièce avec le doigt ou la souris. Utilisez la molette ou deux doigts pour agrandir.</p>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js';
import {STLLoader} from 'https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/loaders/STLLoader.js';
import {OrbitControls} from 'https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/controls/OrbitControls.js';
const host=document.getElementById('fjordQuote3D');
if(host){try{
const res=await fetch({{model_url|tojson}},{credentials:'same-origin'});
if(!res.ok)throw Error('Modèle non disponible');
const geometry=new STLLoader().parse(await res.arrayBuffer());
geometry.computeVertexNormals();geometry.computeBoundingBox();
const bounds=geometry.boundingBox;
const size=new THREE.Vector3();bounds.getSize(size);
if(!Number.isFinite(size.length())||size.length()===0)throw Error('Modèle vide');
const center=new THREE.Vector3();bounds.getCenter(center);geometry.translate(-center.x,-center.y,-center.z);
const scene=new THREE.Scene();scene.background=new THREE.Color('#102235');
const camera=new THREE.PerspectiveCamera(40,1,.01,100000);
const distance=Math.max(size.length()*1.5,10);
camera.position.set(distance*.8,distance*.65,distance);
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
host.replaceChildren(renderer.domElement);
renderer.domElement.style.width='100%';renderer.domElement.style.height='100%';
scene.add(new THREE.HemisphereLight(0xffffff,0x52718d,2.1));
const light=new THREE.DirectionalLight(0xffffff,2.2);light.position.set(2,3,5);scene.add(light);
const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x42a9d7,metalness:.12,roughness:.62,side:THREE.DoubleSide}));
scene.add(mesh);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
controls.target.set(0,0,0);controls.update();
function resize(){const w=host.clientWidth,h=host.clientHeight;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false)}
new ResizeObserver(resize).observe(host);resize();
let active=true;const observer=new IntersectionObserver(entries=>{active=entries[0].isIntersecting});observer.observe(host);
function animate(){requestAnimationFrame(animate);if(active){controls.update();renderer.render(scene,camera)}}animate();
}catch(err){if(!host.querySelector('img'))host.textContent='Aperçu 3D indisponible pour ce modèle.';}}
</script>
{% elif q.preview %}
<img src="{{url_for('fjord_client_quote_image',token=token)}}" alt="Aperçu de votre objet" style="max-width:100%;max-height:350px;object-fit:contain">
{% endif %}
<p style="font-size:12px">Aperçu indicatif : les caractéristiques convenues dans la soumission font foi.</p>
</section>
{% endif %}
<p>Veuillez consulter le PDF de soumission et ses conditions transmis par Les Impressions du Fjord avant d’accepter.</p>
{% if changed %}<p>Cette soumission a été modifiée depuis son acceptation. Une nouvelle acceptation est nécessaire : communiquez avec Les Impressions du Fjord.</p>
{% elif accepted %}<div class="card"><h2>✓ Acceptation enregistrée</h2><p>Signataire : {{accepted.signer}}</p><p>Date : {{accepted.accepted_at.strftime('%Y-%m-%d %H:%M UTC')}}</p><p>Référence de preuve : {{accepted.quote_hash[:16]}}</p></div>
{% else %}<form method="post">{{csrf|safe}}<input type="hidden" name="quote_hash" value="{{digest}}">
<label>Nom complet du client<input name="signer" maxlength="150" required autocomplete="name"></label>
<label style="display:flex;gap:10px;align-items:flex-start"><input type="checkbox" name="agree" value="yes" required style="width:auto;margin-top:5px"><span>J'ai pris connaissance de la soumission, des conditions de vente et des garanties légales applicables. J'accepte le prix et les spécifications et j'autorise la fabrication selon cette soumission.</span></label>
<div class="card" style="margin:16px 0;border-color:#68c6e7"><strong>VENTE FINALE – FABRICATION PERSONNALISÉE</strong><p>Le client confirme avoir vérifié et approuvé les caractéristiques convenues du produit, notamment le modèle, les dimensions, le matériau, la couleur et la quantité. Une fois la fabrication commencée, aucune annulation ou modification pour simple changement d'avis n'est garantie, sous réserve des droits prévus par la loi. Les garanties légales et les recours applicables demeurent pleinement en vigueur.</p><label style="display:flex;gap:10px;align-items:flex-start"><input type="checkbox" name="final_sale" value="yes" required style="width:auto;margin-top:5px"><span>Je reconnais avoir lu et compris les conditions de vente finale pour cet article personnalisé, sous réserve de mes droits légaux.</span></label></div>
<button class="btn" type="submit">✓ J'accepte la soumission et j'autorise la fabrication</button></form>{% endif %}
<p>Les garanties légales applicables demeurent en vigueur.</p></section>''',q=q,total=_money(total),accepted=accepted,changed=changed,digest=digest,csrf=csrfinput(),token=token,model_url=url_for("fjord_client_quote_mesh",token=token)))
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Robots-Tag"]="noindex, nofollow"
        response.headers["Referrer-Policy"]="no-referrer"
        return response

    @app.get("/payer/<token>")
    def fjord_payment_page(token):
        # La page ne dévoile ni l'identité du client ni les paramètres internes.
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,90}",token):
            abort(404)
        with db() as c:
            q=c.execute("""SELECT id,public_number,quantity,unit_price,shipping,apply_taxes,military_discount
                             FROM private_quotes WHERE payment_token=%s""",(token,)).fetchone()
            setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        if not q or not setting or not setting["value"]:
            abort(404)
        recipient=setting["value"]
        subtotal,gst,qst,total=_quote_amounts(q)
        reference=q.get("public_number") or "FJ-{:05d}".format(q["id"])
        response=make_response(page("Paiement Interac",r"""
<style>
.payment-wrap{max-width:660px;margin:25px auto}
.payment-wrap *{box-sizing:border-box}
.payment-steps{margin:12px 0 22px;padding-left:22px}
.payment-steps li{padding:5px 0}
.payment-primary{width:100%;min-height:52px;font-weight:800;margin:5px 0 12px}
.payment-copy-all{min-height:48px}
.payment-feedback{min-height:24px;font-weight:700}
.payment-wrap .payment-detail{padding:10px 0;border-bottom:1px solid #496a7c}
.payment-wrap .payment-detail>div{flex:1 1 220px;min-width:0}
.payment-wrap .payment-detail button{min-height:44px}
body.light .payment-wrap .payment-detail{border-color:#c1dbe8}
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
<p>Votre soumission <strong>{{reference}}</strong> est prête à payer. Aucun mot de passe bancaire n'est demandé ici.</p>
<section class="card">
<div>Montant exact à transférer (taxes comprises si applicables)</div>
<div class="payment-total">{{amount}}</div>
<button type="button" class="payment-primary" onclick="fjordCopy('payEmail',this)">📧 Copier l’adresse Interac pour payer</button>
<ol class="payment-steps">
<li>Ouvrez votre application bancaire habituelle (ou son site officiel).</li>
<li>Choisissez <strong>Virement Interac → Envoyer</strong> et collez l'adresse courriel copiée.</li>
<li>Entrez le montant et la référence ci-dessous; vérifiez les détails avant de confirmer le virement.</li>
</ol>
<p class="notice">Si vous avez déjà reçu une demande officielle de fonds Interac pour cette soumission, acceptez cette demande dans votre banque <strong>au lieu d'envoyer un deuxième virement</strong>.</p>
<h2 style="font-size:20px;margin:20px 0 5px">Renseignements à copier</h2>
<div class="payment-detail"><div>📧 Courriel du destinataire<br><strong id="payEmail">{{recipient}}</strong></div>
<button type="button" onclick="fjordCopy('payEmail',this)">Copier</button></div>
<div class="payment-detail"><div>🔖 Référence à inscrire dans le message<br><strong id="payRef">{{reference}}</strong></div>
<button type="button" onclick="fjordCopy('payRef',this)">Copier</button></div>
<div class="payment-detail"><div>💰 Montant du virement<br><strong id="payAmount">{{amount}}</strong></div>
<button type="button" onclick="fjordCopy('payAmount',this)">Copier</button></div>
<button type="button" class="payment-copy-all" onclick="fjordCopyAll(this)">📋 Copier tous les renseignements</button>
<p class="payment-feedback" id="fjordPaymentFeedback" role="status" aria-live="polite"></p>
<p class="notice">Vérifiez le destinataire dans votre banque avant de confirmer. Conservez votre preuve de virement. Ce site ne débite pas votre compte et ne peut pas confirmer automatiquement la réception du paiement.</p>
</section>
<p>Besoin d'aide? Communique avec Les Impressions du Fjord et mentionne {{reference}}.</p>
</div>
<script>
async function fjordCopyText(text,button){
 const feedback=document.getElementById('fjordPaymentFeedback');
 try{
  await navigator.clipboard.writeText(text);
  if(feedback)feedback.textContent='✓ Copié. Ouvrez votre application bancaire pour poursuivre.';
  const label=button.textContent;button.textContent='✓ Copié';
  setTimeout(()=>button.textContent=label,2200);
 }catch(e){
  if(feedback)feedback.textContent='Copie automatique indisponible. Sélectionnez le texte ci-dessous et copiez-le.';
 }
}
function fjordCopy(id,button){
 const el=document.getElementById(id);
 if(el)fjordCopyText(el.textContent.trim(),button);
}
function fjordCopyAll(button){
 const email=document.getElementById('payEmail').textContent.trim();
 const amount=document.getElementById('payAmount').textContent.trim();
 const reference=document.getElementById('payRef').textContent.trim();
 fjordCopyText('Les Impressions du Fjord\\nCourriel Interac : '+email+'\\nMontant : '+amount+'\\nRéférence : '+reference,button);
}
</script>""",amount=_money(total),reference=reference,recipient=recipient))
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Robots-Tag"]="noindex, nofollow, noarchive"
        response.headers["Referrer-Policy"]="no-referrer"
        return response



    @app.post("/admin/soumissions-pro/<int:quote_id>/couleurs")
    @admin_required
    def fjord_quote_recolor(quote_id):
        verify()
        primary=request.form.get("preview_color","")
        secondary=request.form.get("preview_secondary","")
        if not all(re.fullmatch(r"#[0-9a-fA-F]{6}",c) for c in (primary,secondary)):
            abort(400)
        with db() as c:
            quote=c.execute("SELECT model_id FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            if not quote:abort(404)
            if not quote.get("model_id"):abort(400,"Aucun modèle 3D associé.")
            model=c.execute("SELECT filename,filedata FROM private_models WHERE id=%s",
                            (quote["model_id"],)).fetchone()
            if not model:abort(404)
            generated=make_model_preview(model["filedata"],model["filename"],
                                          color=primary,secondary_color=secondary)
            if not generated:abort(422,"Aperçu 3D indisponible.")
            c.execute("UPDATE private_quotes SET preview_mime=%s,preview=%s WHERE id=%s",
                      (generated[0],generated[1],quote_id))
        flash("Aperçu actualisé. Le PDF utilisera les nouvelles couleurs.")
        return redirect("/admin/soumissions-pro")

    @app.get("/admin/soumissions-pro/<int:quote_id>/pdf")
    @admin_required
    def fjord_quote_pdf(quote_id):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, legal
        from reportlab.lib.utils import ImageReader, simpleSplit
        from reportlab.pdfgen import canvas
        with db() as c:
            q=c.execute("SELECT * FROM private_quotes WHERE id=%s",(quote_id,)).fetchone()
            setting=c.execute("SELECT value FROM settings WHERE key='fjord_quote_logo'").fetchone()
            interac_setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
        if not q:abort(404)
        display_number=q.get("public_number") or "FJ-{:05d}".format(q["id"])
        token=_quote_payment_token(db,q)
        accept_url=url_for("fjord_accept_quote",token=token,_external=True) if token else None
        payment_url=url_for("fjord_payment_page",token=token,_external=True) if token and interac_setting and interac_setting["value"] else None
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
        pdf.setPageSize(legal)
        pdf.saveState()
        pdf.translate(61,305)
        pdf.scale(0.80,0.80)
        navy=colors.HexColor("#071D31")
        cyan=colors.HexColor("#0697CE")
        gray=colors.HexColor("#44546B")
        pdf.setTitle("Soumission {} - Les Impressions du Fjord".format(display_number))
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
        y=line("SOUMISSION  {}".format(display_number),38,y,"Helvetica-Bold",19,navy)
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
        # Régénérer les anciens aperçus automatiques à partir du modèle 3D.
        # Conserver les photos personnalisées et les rendus propres à la soumission.
        quote_preview=q["preview"]
        if q.get("model_id"):
            with db() as c:
                source=c.execute("SELECT filename,filedata,preview FROM private_models WHERE id=%s",(q["model_id"],)).fetchone()
            if source and source["filename"].lower().endswith((".stl",".3mf")):
                old_preview=source["preview"]
                if not quote_preview or (not q.get("atelier_preview") and old_preview and bytes(quote_preview)==bytes(old_preview)):
                    try:
                        fresh=make_model_preview(source["filedata"],source["filename"],size=(900,675))
                        if fresh:quote_preview=fresh[1]
                    except (ValueError,OverflowError,MemoryError):
                        pass
        if quote_preview and y>310:
            try:
                reader=ImageReader(io.BytesIO(quote_preview))
                iw,ih=reader.getSize()
                factor=min(235/max(iw,1),145/max(ih,1))
                pw,ph=iw*factor,ih*factor
                pdf.setFillColor(colors.HexColor("#EDF7FC"))
                pdf.roundRect(37,y-162,539,165,10,stroke=0,fill=1)
                pdf.drawImage(reader, (w-pw)/2, y-154+(145-ph)/2,pw,ph,mask="auto")
                y-=178
            except Exception:pass
        y=min(y-14,285 if payment_url else 250)
        rows=2+(1 if q.get("military_discount") else 0)+(1 if float(q["shipping"]) else 0)+(2 if q["apply_taxes"] else 0)
        if y-rows*25<(172 if payment_url else 115):
            y=285
        subtotal,gst,qst,total=_quote_amounts(q)
        def totalrow(label,amount,y,bold=False):
            pdf.setFont("Helvetica-Bold" if bold else "Helvetica",11 if not bold else 15)
            pdf.setFillColor(navy)
            pdf.drawString(40,y,label)
            pdf.drawRightString(w-39,y,_money(amount).encode("cp1252","replace").decode("cp1252"))
            return y-25
        y=totalrow("Prix unitaire x "+str(q["quantity"]),float(q["unit_price"])*q["quantity"],y)
        discount=_quote_military_discount(q)
        if discount:y=totalrow("Rabais militaire (5 %)",-discount,y)
        if float(q["shipping"]):y=totalrow("Livraison / frais fixes",float(q["shipping"]),y)
        if q["apply_taxes"]:
            y=totalrow("TPS (5 %)",gst,y)
            y=totalrow("TVQ (9,975 %)",qst,y)
        pdf.setStrokeColor(cyan);pdf.line(38,y+12,w-39,y+12)
        y=totalrow("TOTAL CAD",total,y-8,True)
        if payment_url:
            # Lien web vérifiable : aucune demande Interac n'est envoyée par le site.
            if y<200:
                y=200
            top=y-5
            bottom=top-96
            pdf.setFillColor(colors.HexColor("#EBF7FE"))
            pdf.roundRect(39,bottom,w-78,96,10,stroke=0,fill=1)
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold",12)
            pdf.drawString(52,top-24,"PAYER PAR VIREMENT INTERAC")
            pdf.setFont("Helvetica",10)
            pdf.drawString(52,top-42,"Montant à transférer : "+_money(total).replace(" $"," CAD"))
            pdf.drawString(52,top-58,"Référence : {}".format(display_number))
            pdf.setFillColor(cyan)
            pdf.roundRect(52,bottom+10,340,23,6,stroke=0,fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold",10)
            pdf.drawCentredString(222,bottom+18,"CLIQUEZ POUR LES INSTRUCTIONS DE PAIEMENT")
            pdf.linkURL(payment_url,(52,bottom+10,392,bottom+33),relative=1)
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
        if accept_url:
            # L'aperçu de la pièce reste dans le PDF sous forme d'image.
            # Ne pas créer de lien "voir en 3D" qui change de page.
            pdf.setFillColor(cyan)
            pdf.roundRect(39,14,315,27,6,stroke=0,fill=1)
            pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",10)
            pdf.drawCentredString(196,23,"ACCEPTER CETTE SOUMISSION")
            pdf.linkURL(accept_url,(39,14,354,41),relative=1)
        pdf.restoreState()
        w,h=legal
        pdf.setStrokeColor(cyan);pdf.line(30,282,w-30,282)
        pdf.setFillColor(navy);pdf.setFont("Helvetica-Bold",10)
        pdf.drawString(30,267,"VENTE FINALE - GARANTIES ET CONDITIONS DE VENTE")
        clauses=[
         ("1. Garanties légales", "Les garanties légales prévues par les lois applicables, notamment la Loi sur la protection du consommateur et le Code civil du Québec, demeurent pleinement applicables. Le bien doit être conforme à sa description, convenir à son usage normal et avoir une durée raisonnable."),
         ("2. Fabrication personnalisée", "La fabrication suit les dimensions, le matériau, la couleur et les spécifications convenus avec le client. Toute modification demandée après acceptation peut entraîner une nouvelle estimation et un nouveau délai, sous réserve des droits prévus par la loi."),
         ("3. Tolérances et apparence", "L'impression 3D peut présenter des lignes de couches et de légères variations de surface ou de teinte. Les caractéristiques et tolérances essentielles doivent être précisées et acceptées avant la production. Cette clause ne limite pas les garanties légales."),
         ("4. Fichiers fournis par le client", "Le client confirme disposer des droits nécessaires pour faire reproduire le modèle fourni. Les limites techniques ou risques de conception identifiés sont communiqués avant fabrication. Les obligations légales du fabricant demeurent applicables."),
         ("5. Usage prévu et sécurité", "Le client est invité à préciser tout usage mécanique, alimentaire, électrique, médical ou de sécurité. Un objet n'est pas présenté comme certifié pour ces usages sans validation explicite. Les consignes d'utilisation et les garanties légales restent applicables."),
         ("6. Prix et approbation", "La soumission est valable 30 jours à compter de sa date, sauf indication contraire. Le prix, les taxes applicables, la livraison et les modalités de paiement sont ceux indiqués à la soumission acceptée."),
         ("7. Livraison et réclamations", "Les délais sont estimatifs sauf engagement précis. Le client peut signaler un défaut ou une non-conformité afin de permettre l'examen du problème. Aucun délai de réclamation contractuel ne réduit les droits prévus par la loi."),
         ("8. Vente finale - fabrication personnalisée", "Le client confirme les spécifications convenues. Une fois la fabrication commencée, une annulation ou une modification pour simple changement d'avis n'est pas garantie, sous réserve des droits prévus par la loi. Les garanties légales demeurent pleinement applicables."),
         ("9. Recours et droits du consommateur", "Aucune disposition des présentes conditions ne supprime ou ne limite les recours impératifs du consommateur. Selon les circonstances, une réparation, un remplacement, un remboursement ou d'autres recours légaux peuvent s'appliquer.")
        ]

        y=253
        for heading,paragraph in clauses:
            heading=heading.encode("cp1252","replace").decode("cp1252")
            fragments=simpleSplit(paragraph.encode("cp1252","replace").decode("cp1252"),"Helvetica",6.3,w-60)
            pdf.setFillColor(cyan);pdf.setFont("Helvetica-Bold",6.7)
            pdf.drawString(30,y,heading);y-=8
            pdf.setFillColor(gray);pdf.setFont("Helvetica",6.3)
            for fragment in fragments:
                pdf.drawString(30,y,fragment);y-=7
            y-=3
        pdf.setFont("Helvetica",9);pdf.setFillColor(gray)
        pdf.drawString(30,18,"Les garanties légales et les recours du consommateur demeurent applicables.")

        pdf.save();buffer.seek(0)
        return send_file(buffer,mimetype="application/pdf",as_attachment=True,
                  download_name="Soumission-{}.pdf".format(display_number))

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

    from live_print import register_live_print
    register_live_print(app, db, admin_required, verify, page)
