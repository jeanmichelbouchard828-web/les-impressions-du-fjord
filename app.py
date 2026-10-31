import os,io,re,hmac,time,uuid,hashlib,secrets,datetime,smtplib
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlparse
from flask import Flask,request,redirect,render_template_string,session,abort,send_file,flash,url_for,jsonify
import psycopg
from psycopg.rows import dict_row
from werkzeug.utils import secure_filename
app=Flask(__name__)
# Actual server-side slicing / layer toolpaths. The resulting generic G-code
# is NOT downloadable or intended for direct use on a Bambu X2D printer.
from real_slicer import slicer_bp
app.register_blueprint(slicer_bp)
app.secret_key=os.environ.get("SECRET_KEY",secrets.token_hex(32))
app.config.update(MAX_CONTENT_LENGTH=10*1024*1024,SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax")
DB=os.environ["DATABASE_URL"]
STATUSES=["Demande reçue","Soumission envoyée","En impression","Terminée"]
MATERIALS=["À déterminer","PLA","PETG","ASA","TPU","Autre"]
def db():
 return psycopg.connect(DB,row_factory=dict_row)
def init():
 with db() as c:
  c.execute("""CREATE TABLE IF NOT EXISTS requests(id BIGSERIAL PRIMARY KEY,kind TEXT NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT,material TEXT,description TEXT NOT NULL,filename TEXT,filedata BYTEA,created TIMESTAMPTZ DEFAULT NOW(),status TEXT DEFAULT 'Demande reçue')""")
  c.execute("""CREATE TABLE IF NOT EXISTS gallery(id BIGSERIAL PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,photo BYTEA,mime TEXT,created TIMESTAMPTZ DEFAULT NOW())""")
  c.execute("""CREATE TABLE IF NOT EXISTS sessions(tokenhash TEXT PRIMARY KEY,expires TIMESTAMPTZ NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS gallery_photos(id BIGSERIAL PRIMARY KEY,gallery_id BIGINT REFERENCES gallery(id) ON DELETE CASCADE,photo BYTEA NOT NULL,mime TEXT NOT NULL)""")
init()
# Migration additive : progression renseignée par l'administrateur, jamais simulée.
with db() as c:
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS progress INTEGER")
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS live_enabled BOOLEAN NOT NULL DEFAULT FALSE")
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS live_url TEXT")
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS public_progress BOOLEAN NOT NULL DEFAULT FALSE")
STYLE="""<style>*{box-sizing:border-box}body{margin:0;background:#071321;color:#f2faff;font:16px system-ui,Arial}header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 5%;border-bottom:1px solid #2a4a62;background:#091a2b;flex-wrap:wrap}nav{display:flex;gap:15px;flex-wrap:wrap}a{color:#7fe4ff;text-decoration:none}.brand{font-weight:900;letter-spacing:.6px}main{max-width:1100px;margin:auto;padding:28px 20px 70px}.hero{padding:70px 0 90px;background:radial-gradient(ellipse at 80% 10%,#15618a77,transparent 60%)}h1{font-size:clamp(38px,7vw,78px);line-height:1.06;margin:15px 0}h2{font-size:30px}p{color:#c6d7e7;line-height:1.65}.eyebrow{color:#80dfff;letter-spacing:3px;text-transform:uppercase;font-size:13px;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}.card{background:#10283b;border:1px solid #2d526d;padding:22px;border-radius:16px;overflow:hidden}.card img{width:100%;height:220px;object-fit:cover;border-radius:10px}.gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:14px}.gallery-grid img{width:100%;height:145px;object-fit:cover;border-radius:9px}.gallery-tile{background:#10283b;padding:12px;border-radius:12px}.gallery-tile h3{font-size:15px}.zoom{background:#071321;color:white;border:0;max-width:96vw;max-height:95vh}.zoom::backdrop{background:#000d}.zoom img{max-width:90vw;max-height:78vh;object-fit:contain}.gallery-detail h1{font-size:clamp(26px,4vw,42px);line-height:1.15;overflow-wrap:anywhere;max-width:850px}.gallery-detail .gallery-grid{margin-top:22px}.gallery-photo-link{display:block;cursor:zoom-in}.gallery-photo-link img{display:block;width:100%;height:160px;object-fit:cover;border-radius:10px}.zoom[open]{display:block;position:fixed;inset:0;margin:auto;padding:12px;box-shadow:0 20px 80px #000b}.zoom .row{justify-content:center;margin-bottom:10px}.zoom img{display:block;margin:auto;max-width:min(90vw,1100px);max-height:75vh}@media(max-width:600px){.gallery-detail h1{font-size:clamp(24px,7vw,32px)}.gallery-detail .gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}input,textarea,select{display:block;width:100%;padding:12px;margin:7px 0 17px;background:#081827;color:white;border:1px solid #47718b;border-radius:9px;font:inherit}label{display:block;font-weight:600}textarea{min-height:110px}button,.btn{display:inline-block;padding:13px 20px;border:0;border-radius:9px;background:#5ad7f5;color:#061b2a;font-weight:800;cursor:pointer;font:inherit;text-decoration:none}form{max-width:650px}.muted{color:#a9c3d3}.alert{padding:14px;background:#163e50;border-radius:9px;margin:15px 0}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.row form{display:inline}.small{font-size:13px}.contact-actions{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 28px}.contact-actions a{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:13px 18px;border-radius:10px;background:#163e59;border:1px solid #4a91b6;color:#f2faff;font-weight:750}.contact-actions a:hover{background:#215b7d}.contact-actions a:focus-visible{outline:3px solid #7fe4ff;outline-offset:3px}footer{padding:25px 5%;border-top:1px solid #294b62;color:#a9c3d3}@media(max-width:600px){.hero{padding:40px 0}header{align-items:flex-start}nav{font-size:14px}}</style>"""
BASE="""<!doctype html><html lang="fr-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{{meta_description}}"><meta property="og:title" content="{{title}} | Les Impressions du Fjord"><meta property="og:description" content="{{meta_description}}"><meta property="og:type" content="website"><title>{{title}} | Les Impressions du Fjord</title>"""+STYLE+"""<style>
body.light{background:#f4f8fc;color:#14283c}
body.light header{background:#fff;border-color:#ccdae8}
body.light footer{border-color:#ccdae8;color:#466073}
body.light p,body.light .muted{color:#42566b}
body.light .card,body.light .gallery-tile{background:#fff;border-color:#c7d8e7}
body.light input,body.light textarea,body.light select{background:#fff;color:#14283c;border-color:#8da8c0}
body.light .zoom{background:#fff;color:#14283c}
body.light .hero{background:radial-gradient(ellipse at 80% 10%,#a6dfff88,transparent 60%)}
body.light a{color:#075f90}body.light .btn,body.light button{color:#06283d}
body.light .contact-actions a{background:#e3f3fc;color:#153c58}
.pref-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pref-controls select{display:inline-block;width:auto;min-width:100px;margin:0;padding:8px;font-size:14px}
.atelier-nav{display:inline-flex;align-items:center;background:#1a8bc0;color:#fff;font-weight:850;border:1px solid #72dfff;border-radius:10px;padding:9px 12px;box-shadow:0 0 0 1px #15374d55}
.atelier-nav:hover,.atelier-nav:focus-visible{background:#0872a6;color:#fff;outline:2px solid #b4efff;outline-offset:2px}
.atelier-feature{margin:25px 0 10px;padding:26px 28px;max-width:870px;border-radius:20px;border:1px solid #5abce7;background:linear-gradient(125deg,#154263,#0a243c);box-shadow:0 16px 48px #020b1840}
.atelier-feature-label{color:#a4ebff;text-transform:uppercase;letter-spacing:1.5px;font-size:12px;font-weight:800}
.atelier-feature h2{font-size:clamp(24px,3vw,35px);margin:12px 0 8px}
.atelier-feature p{margin:8px 0;color:#d0e8f8}
.atelier-feature .atelier-cta{display:inline-flex;align-items:center;justify-content:center;text-align:center;background:#67daf6;color:#092033;box-shadow:0 8px 30px #0006;font-size:clamp(16px,2vw,20px);font-weight:850;margin-top:17px;max-width:100%;white-space:normal}
.atelier-feature .atelier-cta:hover,.atelier-feature .atelier-cta:focus-visible{background:#a9efff}
.atelier-feature .atelier-feature-note{font-size:12px;color:#b4dbea;margin-top:12px}
.secondary-btn{background:transparent;color:#a6e8fb;border:1px solid #5abce7}
body.light .atelier-nav{color:#fff;background:#076a9e}
body.light .atelier-feature{background:linear-gradient(125deg,#e9f8ff,#d4eafd);border-color:#7bbcdc}
body.light .atelier-feature h2{color:#173c55}
body.light .atelier-feature p,body.light .atelier-feature .atelier-feature-note{color:#345a72}
body.light .atelier-feature-label{color:#136b92}
body.light .atelier-feature .atelier-cta{background:#087cae;color:#fff}
body.light .secondary-btn{color:#075f90;border-color:#3c8eb5}
@media(max-width:600px){.atelier-feature{padding:18px}.atelier-feature .atelier-cta{width:100%}}
.referral-footer{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 14px;margin-top:14px;padding-top:14px;border-top:1px solid #294b62;font-size:13px}
.referral-footer a{color:#addbea;text-decoration:underline;text-decoration-color:#557489;text-underline-offset:3px}
.referral-footer span{color:#9bb6c9}
.referral-page{max-width:820px;margin:26px auto 55px}
.referral-page h1{font-size:clamp(35px,5vw,56px)}
.referral-page .referral-card{padding:25px;margin-top:24px}
.referral-page .referral-cta{max-width:100%;white-space:normal;text-align:center;overflow-wrap:anywhere}
.referral-page .referral-disclosure{border-top:1px solid #2d526d;padding-top:15px;margin-top:26px}
body.light .referral-footer{border-color:#ccdae8}
body.light .referral-footer a{color:#075f90}
body.light .referral-footer span{color:#466073}
body.light .referral-page .referral-disclosure{border-color:#c7d8e7}
@media(max-width:600px){.referral-page .referral-card{padding:18px}.referral-page .referral-cta{width:100%}}
.public-print-list{display:grid;gap:10px;margin-top:16px}.public-print-job{padding:12px;border-radius:10px;background:#0c1c2caa;display:flex;align-items:center;gap:12px;flex-wrap:wrap}.public-print-job .tracking-progress{flex:1 1 100%;margin:0}.public-print-job span{margin-left:auto}.tracking-billboard{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;margin:10px 0 32px;padding:26px;border:1px solid #4e9cc5;border-radius:18px;background:linear-gradient(120deg,#173a54,#0c2133)}.tracking-billboard h2{margin:8px 0;font-size:clamp(23px,3vw,33px)}.tracking-billboard p{color:#d6e6f1}.tracking-panel{max-width:640px;margin:20px auto}.tracking-result{margin-top:25px;padding:22px;border:1px solid #4e9cc5;border-radius:12px}.tracking-progress{height:16px;border-radius:12px;background:#273b50;overflow:hidden}.tracking-progress span{display:block;height:100%;background:#43b9ec}body.light .tracking-billboard{background:#e5f3fc;color:#173a54}body.light .tracking-billboard p{color:#34536c}</style></head><body><header><a class="brand" href="/"><img src="/identite/logo" alt="Logo Les Impressions du Fjord" style="width:64px;height:64px;object-fit:contain;vertical-align:middle;margin-right:12px" onerror="this.style.display='none'">LES IMPRESSIONS DU FJORD</a><nav><a href="/#services">Services</a><a href="/galerie">Galerie</a><a href="/soumission">Soumission</a><a href="/#nous-joindre">Nous joindre</a><a href="/contact">Formulaire</a><a href="/atelier-3d">Atelier 3D</a><a href="/admin">Administration</a></nav><div class="pref-controls"><select id="fjord-lang" aria-label="Langue / Language"><option value="fr">🇨🇦 Français</option><option value="en">🇨🇦 English</option></select><select id="fjord-theme" aria-label="Thème / Theme"><option value="dark">🌙 Sombre</option><option value="light">☀️ Clair</option></select></div></header><main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="alert">{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}<section id="nous-joindre" class="contact-section"><h2>Contactez-nous</h2><p>Une idée de création 3D? Écrivez-nous sur Facebook ou appelez-nous!</p><div class="contact-actions"><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">ⓕ Notre page Facebook</a><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">💬 Nous écrire sur Facebook</a><a href="tel:+15819980831">☎ 581-998-0831</a><a href="https://maps.app.goo.gl/9Qryi3nbK9nBuXts8?g_st=ac" target="_blank" rel="noopener noreferrer">📍 Nous trouver sur Google Maps</a></div><p class="muted small">Pour Messenger, ouvrez notre page Facebook et choisissez « Envoyer un message ».</p></section></main><footer><div>© 2026 Les Impressions du Fjord · Saguenay, Québec</div><div class="referral-footer"><a href="/bons-plans/starlink">🛰️ Notre bon plan Internet : parrainage Starlink</a><span>Un partage personnel, indépendant de nos services d'impression 3D.</span></div></footer><script>
(function(){
const translations={
"Services":"Services","Galerie":"Gallery","Soumission":"Quote","Nous joindre":"Contact us","Formulaire":"Contact form","Administration":"Administration",
"Créez votre propre création":"Create your own design","🎨 Créez votre propre création":"🎨 Create your own design","✦ Votre atelier 3D en ligne":"✦ Your online 3D studio","Imaginez. Créez. Personnalisez.":"Imagine. Create. Customize.","Concevez votre objet en 3D, ajustez ses dimensions et préparez votre création pour une impression sur mesure.":"Design your own 3D object, adjust its dimensions, and prepare your model for custom printing.","Atelier gratuit · Français / English · Sombre / Clair":"Free studio · Français / English · Dark / Light","Atelier 3D":"3D Studio","Atelier 3D 🔒":"3D Studio 🔒","Création · Précision · Innovation":"Creation · Precision · Innovation",
"Vos idées prennent forme.":"Your ideas take shape.","Impression 3D sur mesure au Saguenay.":"Custom 3D printing in Saguenay.",
"Demander une soumission":"Request a quote","Nos services":"Our services","Impression 3D personnalisée":"Custom 3D printing",
"Pièces et accessoires sur mesure.":"Custom parts and accessories.","Prototypage":"Prototyping",
"Conception et essais de pièces.":"Part design and testing.","Créations décoratives":"Decorative creations",
"Objets et cadeaux personnalisés.":"Personalized objects and gifts.","Voir nos réalisations":"View our creations",
"Contactez-nous":"Contact us","Une idée de création 3D? Écrivez-nous sur Facebook ou appelez-nous!":"Have a 3D idea? Message us on Facebook or call us!",
"ⓕ Notre page Facebook":"ⓕ Our Facebook page","💬 Nous écrire sur Facebook":"💬 Message us on Facebook",
"📍 Nous trouver sur Google Maps":"📍 Find us on Google Maps",
"Pour Messenger, ouvrez notre page Facebook et choisissez « Envoyer un message ».":"For Messenger, open our Facebook page and select “Send message”.",
"Galerie de réalisations":"Our creations","Appuyez sur une création pour agrandir ses photos.":"Select a creation to view its photos.",
"Demande reçue":"Request received","Soumission envoyée":"Quote sent","En impression":"Printing","Terminée":"Completed",
"Votre nom":"Your name","Courriel":"Email","Téléphone (facultatif)":"Phone (optional)","Description de votre projet":"Describe your project",
"Description de votre message":"Your message","Envoyer la demande":"Send request",
"Nous contacter":"Contact us","Envoyez-nous votre message directement depuis ce formulaire.":"Send your message directly from this form.",
"Décrivez votre projet et joignez votre modèle 3D si vous en avez un.":"Describe your project and attach your 3D model if available.",
"Matériau souhaité":"Preferred material","Fichier STL ou 3MF (facultatif, maximum 8 Mo)":"STL or 3MF file (optional, 8 MB maximum)",
"Votre demande a bien été enregistrée. Nous vous répondrons dès que possible.":"Your request has been received. We will reply as soon as possible.",
"Retour à l’accueil":"Back to home","Merci!":"Thank you!",
"🛰️ Notre bon plan Internet : parrainage Starlink":"🛰️ Our Internet tip: Starlink referral",
"Un partage personnel, indépendant de nos services d'impression 3D.":"A personal referral, independent of our 3D printing services.",
"Bon plan partagé":"A tip worth sharing",
"Parrainage Starlink":"Starlink referral",
"Vous envisagez de vous abonner à Starlink au Canada? Voici un lien de parrainage personnel à consulter si cela vous intéresse.":"Considering Starlink in Canada? Here is a personal referral link to explore if you're interested.",
"Découvrir Starlink":"Discover Starlink",
"Les nouveaux abonnés admissibles peuvent recevoir une récompense selon les conditions de parrainage en vigueur. La personne qui partage ce lien peut également recevoir une récompense.":"Eligible new subscribers may receive a reward subject to the current referral program terms. The person sharing this link may also receive a reward.",
"Consulter mon lien de parrainage":"View my referral link",
"Lien de parrainage personnel. Les Impressions du Fjord ne vendent pas de services Starlink et ne sont pas affiliées à Starlink. Vérifiez la disponibilité, les tarifs et les conditions directement sur le site Starlink.":"Personal referral link. Les Impressions du Fjord does not sell Starlink services and is not affiliated with Starlink. Verify availability, pricing and terms directly on Starlink's website.",
"← Retour à l'accueil":"← Back to home"
};
const originals=new WeakMap();
function apply(){
const lang=localStorage.getItem('fjord-lang')==='en'?'en':'fr';
const theme=localStorage.getItem('fjord-theme')==='light'?'light':'dark';
document.body.classList.toggle('light',theme==='light');document.documentElement.lang=lang==='en'?'en-CA':'fr-CA';
document.getElementById('fjord-lang').value=lang;document.getElementById('fjord-theme').value=theme;
const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
while(walker.nextNode()){const n=walker.currentNode;if(n.parentElement&&/^(SCRIPT|STYLE|TEXTAREA|OPTION)$/i.test(n.parentElement.tagName))continue;
if(!originals.has(n))originals.set(n,n.textContent);
const original=originals.get(n);const trimmed=original.trim();
if(translations[trimmed])n.textContent=lang==='en'?original.replace(trimmed,translations[trimmed]):original;
}
}
document.getElementById('fjord-lang').addEventListener('change',e=>{localStorage.setItem('fjord-lang',e.target.value);apply()});
document.getElementById('fjord-theme').addEventListener('change',e=>{localStorage.setItem('fjord-theme',e.target.value);apply()});
apply();
})();
</script></body></html>"""
def page(title,body,**kwargs):
 from flask import render_template_string
 return render_template_string(BASE,title=title,meta_description=("Découvrez un lien de parrainage Starlink pour les nouveaux abonnés admissibles au Canada. Parrainage personnel et transparent." if title=="Parrainage Starlink" else "Les Impressions du Fjord — impression 3D sur mesure au Saguenay."),body=render_template_string(body,**kwargs))
def csrf():
 if "csrf" not in session:session["csrf"]=secrets.token_urlsafe(24)
 return session["csrf"]
def verify():
 if not hmac.compare_digest(request.form.get("csrf",""),csrf()):abort(400)
def csrfinput():return '<input type="hidden" name="csrf" value="'+csrf()+'">'
def admin_required(f):
 @wraps(f)
 def inner(*a,**kw):
  token=session.get("admin_token","")
  if not token:return redirect("/admin/login")
  with db() as c:r=c.execute("SELECT 1 FROM sessions WHERE tokenhash=%s AND expires>NOW()",(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
  if not r:return redirect("/admin/login")
  return f(*a,**kw)
 return inner
def rate_limit():
 # Persistent per-email throttling: maximum 4 submissions per email in an hour.
 email=request.form.get("email","").strip().lower()
 with db() as c:
  n=c.execute("SELECT count(*) AS n FROM requests WHERE lower(email)=%s AND created>NOW()-INTERVAL '1 hour'",(email,)).fetchone()["n"]
 return n<4
def notify(kind,name,email):
 host=os.getenv("SMTP_HOST")
 if not host:return
 try:
  msg=EmailMessage();msg["Subject"]="Nouvelle demande - "+kind;msg["From"]=os.environ["SMTP_FROM"];msg["To"]=os.environ["NOTIFY_EMAIL"]
  msg.set_content("Nouvelle demande reçue de "+name+" ("+email+"). Consultez l'administration du site.")
  with smtplib.SMTP(host,int(os.getenv("SMTP_PORT","587")),timeout=10) as s:
   s.starttls();s.login(os.environ["SMTP_USER"],os.environ["SMTP_PASSWORD"]);s.send_message(msg)
 except Exception:app.logger.exception("Notification email failed")
@app.get("/identite/logo")
def fjord_public_logo():
 try:
  import base64
  from flask import Response
  with open("static/fjord_logo.b64",encoding="ascii") as f:
   raw=base64.b64decode(f.read().strip(),validate=True)
  return Response(raw,mimetype="image/png",headers={"Cache-Control":"public, max-age=86400","X-Content-Type-Options":"nosniff"})
 except (OSError,ValueError):
  abort(404)

@app.route("/suivi",methods=["GET","POST"])
def suivi_client():
 result=None
 if request.method=="POST":
  verify()
  ident=request.form.get("numero","").strip()
  email=request.form.get("email","").strip().casefold()
  if ident.isdigit() and email and len(email)<=200:
   with db() as c:
    result=c.execute("SELECT id,status,progress,live_enabled,live_url FROM requests WHERE id=%s AND kind='Soumission' AND LOWER(email)=%s",(int(ident),email)).fetchone()
  if result is None:
   flash("Aucune commande trouvée. Vérifiez votre numéro et votre courriel.")
 return page("Suivre mon impression",'''<section class="tracking-panel"><div class="eyebrow">Les Impressions du Fjord</div><h1>Suivre mon impression</h1><p>Entrez le numéro de votre demande et le courriel utilisé pour la soumission.</p><form method="post">{{csrf|safe}}<label>Numéro de demande<input name="numero" inputmode="numeric" required maxlength="12"></label><label>Courriel<input type="email" name="email" required maxlength="200"></label><button class="btn">Afficher mon suivi</button></form>{% if result %}<div class="tracking-result"><h2>Commande #{{result.id}}</h2><p><strong>{{result.status}}</strong></p>{% if result.status=="En impression" and result.progress is not none %}<div class="tracking-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{{result.progress}}"><span style="width:{{result.progress}}%"></span></div><p>{{result.progress}} % terminé</p>{% elif result.status=="En impression" %}<p>Progression en attente de mise à jour.</p>{% endif %}{% if result.status=="En impression" and result.live_enabled %}<p>{% if result.live_url %}<a class="btn" href="{{result.live_url}}" target="_blank" rel="noopener noreferrer nofollow">🎥 Regarder mon impression en direct</a><p><strong>📹 Pour voir votre impression en direct :</strong> après avoir ouvert le lien, sélectionnez <strong>« Alternative Cam »</strong> et non « Bambu Cam ».</p><p>Le lien externe OctoEverywhere est accessible à toute personne qui le possède. Ne le partagez pas.</p>{% else %}La caméra n'est pas disponible pour cette commande.{% endif %}</p>{% endif %}</div>{% endif %}</section>''',result=result,csrf=csrfinput())
@app.get("/api/production-publique")
def public_production():
 # Uniquement les commandes autorisées; aucun identifiant ou renseignement client.
 with db() as c:
  rows=c.execute("SELECT status,progress FROM requests WHERE kind='Soumission' AND public_progress=TRUE AND status IN ('Demande reçue','Soumission envoyée','En impression','Terminée') ORDER BY id DESC LIMIT 100").fetchall()
 groups={"print":[],"wait":[],"done":[]}
 for r in rows:
  key="print" if r["status"]=="En impression" else ("done" if r["status"]=="Terminée" else "wait")
  if len(groups[key])<4:
   groups[key].append({"progress":r["progress"] if key=="print" else None,"status":r["status"]})
 response=jsonify({"groups":groups})
 response.headers["Cache-Control"]="no-store, max-age=0"
 return response

@app.get("/")
def home():
 # Seules les impressions expressément autorisées sont affichées, sans identifiants client.
 with db() as c:
  public_jobs=c.execute("SELECT progress FROM requests WHERE kind='Soumission' AND status='En impression' AND public_progress=TRUE ORDER BY id DESC LIMIT 4").fetchall()
 return page("Accueil",'''<div class="hero"><div class="eyebrow">Création · Précision · Innovation</div><h1>Vos idées prennent forme.</h1><p>Impression 3D sur mesure au Saguenay.</p><div class="atelier-feature"><div class="atelier-feature-label">✦ Votre atelier 3D en ligne</div><h2>Imaginez. Créez. Personnalisez.</h2><p>Concevez votre objet en 3D, ajustez ses dimensions et préparez votre création pour une impression sur mesure.</p><a class="btn atelier-cta" href="/atelier-3d">🎨 Créez votre propre création</a><p class="atelier-feature-note">Atelier gratuit · Français / English · Sombre / Clair</p></div><a class="btn secondary-btn" href="/soumission">Demander une soumission</a></div><section class="tracking-billboard fjord-board" aria-label="Tableau interactif de production"><div class="fjord-board-inner"><div class="fjord-board-heading"><strong>LES IMPRESSIONS DU FJORD</strong><span class="fjord-board-badge">Production</span></div><h2>Suivi des impressions 3D</h2><p>Aperçu interactif du tableau de production</p><div class="fjord-board-tabs" role="tablist" aria-label="Statut des impressions"><button type="button" class="fjord-board-tab active" data-status="print" role="tab" aria-selected="true">En impression</button><button type="button" class="fjord-board-tab" data-status="wait" role="tab" aria-selected="false">En attente</button><button type="button" class="fjord-board-tab" data-status="done" role="tab" aria-selected="false">Terminées</button></div><div id="fjordProductionLive" role="tabpanel" aria-live="polite"><p>Chargement du tableau de production…</p></div><p class="production-updated" id="fjordProductionUpdated">Mise à jour automatique toutes les 30 secondes.</p><a class="btn fjord-board-see" href="/suivi">👁️ Voir mon impression</a><p class="fjord-board-private">Suivi privé avec votre numéro de demande et votre courriel.</p></div></section><style>
.fjord-board{display:block;padding:24px;background:#0b1725;border-color:#3a6076}.fjord-board-inner{width:100%}.fjord-board-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;font-size:18px}.fjord-board-badge{background:#103c27;color:#50d78a;border-radius:30px;padding:5px 12px;font-size:14px}.fjord-board h2{font-size:clamp(24px,3vw,30px);margin:22px 0 6px}.fjord-board-tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:20px 0}.fjord-board-tab{background:transparent;border:0;border-radius:30px;color:#c4d5e0;font:inherit;font-weight:700;padding:12px 5px;cursor:pointer}.fjord-board-tab.active{background:#304151;color:white}.fjord-board-tab:focus-visible{outline:2px solid #64d9ff;outline-offset:2px}.fjord-board .public-print-list{margin:0}.fjord-board .public-print-job{background:#10283b;display:block}.fjord-board .public-print-job strong{display:block}.fjord-board .public-print-job span{display:block;margin:8px 0}.fjord-board .tracking-progress{height:12px}.fjord-board .tracking-progress span{margin:0;background:#24b46a}.fjord-board-see{display:inline-block;margin-top:12px}.fjord-board-private{font-size:13px;margin:8px 0 0}.fjord-board .production-updated{font-size:13px;margin:14px 0 0}@media(max-width:480px){.fjord-board{padding:16px}.fjord-board-tab{font-size:13px;padding:10px 3px}}
</style><script>
(function(){
 const root=document.getElementById("fjordProductionLive"),updated=document.getElementById("fjordProductionUpdated");
 const tabs=Array.from(document.querySelectorAll(".fjord-board-tab"));
 let active="print",groups={print:[],wait:[],done:[]};
 const titles={print:"Impression en cours",wait:"Commande en attente",done:"Impression terminée"};
 const empty={print:"Aucune impression publique en cours pour le moment.",wait:"Aucune commande en attente rendue publique.",done:"Aucune impression terminée rendue publique."};
 function render(){
  root.replaceChildren();
  const jobs=groups[active]||[];
  if(!jobs.length){const p=document.createElement("p");p.textContent=empty[active];root.append(p);return;}
  const list=document.createElement("div");list.className="public-print-list";
  jobs.forEach(job=>{
   const card=document.createElement("div");card.className="public-print-job";
   const title=document.createElement("strong");title.textContent="🖨️ "+titles[active];card.append(title);
   if(active==="print"){
    const progress=job.progress;
    if(Number.isInteger(progress)&&progress>=0&&progress<=100){
     const value=document.createElement("span");value.textContent=progress+" %";card.append(value);
     const bar=document.createElement("div");bar.className="tracking-progress";bar.setAttribute("role","progressbar");bar.setAttribute("aria-label","Progression de l'impression");bar.setAttribute("aria-valuemin","0");bar.setAttribute("aria-valuemax","100");bar.setAttribute("aria-valuenow",String(progress));
     const fill=document.createElement("span");fill.style.width=progress+"%";bar.append(fill);card.append(bar);
    }else{const p=document.createElement("p");p.textContent="Progression non disponible";card.append(p);}
   }else if(active==="wait"){const p=document.createElement("p");p.textContent=job.status==="Soumission envoyée"?"Soumission envoyée":"Demande reçue";card.append(p);}
   list.append(card);
  });
  root.append(list);
 }
 tabs.forEach(tab=>tab.addEventListener("click",()=>{
  active=tab.dataset.status;tabs.forEach(t=>{const chosen=t===tab;t.classList.toggle("active",chosen);t.setAttribute("aria-selected",String(chosen));});render();
 }));
 async function refresh(){
  if(document.hidden)return;
  try{
   const response=await fetch("/api/production-publique",{cache:"no-store",credentials:"same-origin"});
   if(!response.ok)throw Error("Indisponible");
   const data=await response.json();
   if(!data.groups||!["print","wait","done"].every(k=>Array.isArray(data.groups[k])))throw Error("Données invalides");
   groups=data.groups;render();updated.textContent="Tableau actualisé automatiquement.";
  }catch(e){updated.textContent="Mise à jour temporairement indisponible.";}
 }
 refresh();setInterval(refresh,30000);document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
})();
</script><section id="services"><h2>Nos services</h2><div class="grid"><div class="card"><h3>Impression 3D personnalisée</h3><p>Pièces et accessoires sur mesure.</p></div><div class="card"><h3>Prototypage</h3><p>Conception et essais de pièces.</p></div><div class="card"><h3>Créations décoratives</h3><p>Objets et cadeaux personnalisés.</p></div></div></section><p><a class="btn" href="/galerie">Voir nos réalisations</a></p>''',public_jobs=public_jobs)
@app.get("/bons-plans/starlink")
def starlink_referral():
 return page("Parrainage Starlink",'''<section class="referral-page"><div class="eyebrow">Bon plan partagé</div><h1>Parrainage Starlink</h1><p>Vous envisagez de vous abonner à Starlink au Canada? Voici un lien de parrainage personnel à consulter si cela vous intéresse.</p><div class="card referral-card"><h2>Découvrir Starlink</h2><p>Les nouveaux abonnés admissibles peuvent recevoir une récompense selon les conditions de parrainage en vigueur. La personne qui partage ce lien peut également recevoir une récompense.</p><a class="btn referral-cta" href="https://starlink.com/?referral=RC-4635519-65017-67&amp;app_source=share" target="_blank" rel="nofollow sponsored noopener noreferrer">Consulter mon lien de parrainage</a><p class="small muted referral-disclosure">Lien de parrainage personnel. Les Impressions du Fjord ne vendent pas de services Starlink et ne sont pas affiliées à Starlink. Vérifiez la disponibilité, les tarifs et les conditions directement sur le site Starlink.</p></div><p class="small"><a href="/">← Retour à l'accueil</a></p></section>''')

@app.get("/galerie")
def gallery_page():
 with db() as c:items=c.execute("SELECT id,title,category,description,photo IS NOT NULL AS has_photo FROM gallery ORDER BY id DESC").fetchall()
 return page("Galerie",'''<h1>Galerie de réalisations</h1><p>Appuyez sur une création pour agrandir ses photos.</p><div class="gallery-grid">{% for i in items %}<a class="gallery-tile" href="/galerie/{{i.id}}"><img src="{{'/photo/' ~ i.id if i.has_photo else '/gallery/cover/' ~ i.id}}" alt="{{i.title}}" onerror="this.style.display='none'"><h3>{{i.title}}</h3><div class="eyebrow">{{i.category}}</div></a>{% else %}<p>Réalisations à venir.</p>{% endfor %}</div>''',items=items)
@app.get("/gallery/cover/<int:id>")
def cover(id):
 with db() as c:r=c.execute("SELECT photo,mime FROM gallery_photos WHERE gallery_id=%s ORDER BY id LIMIT 1",(id,)).fetchone()
 if not r:abort(404)
 return send_file(io.BytesIO(r["photo"]),mimetype=r["mime"])
@app.get("/gallery/image/<int:id>")
def gallery_image(id):
 with db() as c:r=c.execute("SELECT photo,mime FROM gallery_photos WHERE id=%s",(id,)).fetchone()
 if not r:abort(404)
 return send_file(io.BytesIO(r["photo"]),mimetype=r["mime"])
@app.get("/galerie/<int:id>")
def gallery_item(id):
 with db() as c:
  item=c.execute("SELECT id,title,category,description,photo IS NOT NULL AS has_photo FROM gallery WHERE id=%s",(id,)).fetchone()
  if not item:abort(404)
  photos=c.execute("SELECT id FROM gallery_photos WHERE gallery_id=%s ORDER BY id",(id,)).fetchall()
 urls=(["/photo/"+str(id)] if item["has_photo"] else [])+["/gallery/image/"+str(p["id"]) for p in photos]
 return page(item["title"],'''<div class="gallery-detail"><a href="/galerie">← Galerie</a><h1>{{item.title}}</h1><div class="eyebrow">{{item.category}}</div><p>{{item.description}}</p><p class="muted">Touchez une photo pour l’agrandir.</p><div class="gallery-grid">{% for url in urls %}<a href="{{url}}" class="gallery-photo-link" data-photo-index="{{loop.index0}}" aria-label="Agrandir la photo {{loop.index}}"><img loading="lazy" src="{{url}}" alt="{{item.title}} — photo {{loop.index}}"></a>{% endfor %}</div><dialog id="viewer" class="zoom" aria-label="Photo agrandie"><div class="row"><button type="button" id="previousPhoto" aria-label="Photo précédente">❮</button><span id="photoCounter"></span><button type="button" id="nextPhoto" aria-label="Photo suivante">❯</button><button type="button" id="closeViewer">Fermer ✕</button></div><img id="largePhoto" alt="{{item.title}}"></dialog><script>(function(){const links=Array.from(document.querySelectorAll(".gallery-photo-link"));const viewer=document.getElementById("viewer");const large=document.getElementById("largePhoto");const counter=document.getElementById("photoCounter");let position=0;function update(){large.src=links[position].href;counter.textContent=(position+1)+" / "+links.length}function change(delta){position=(position+delta+links.length)%links.length;update()}links.forEach((link,i)=>link.addEventListener("click",function(event){if(typeof viewer.showModal!=="function")return;event.preventDefault();position=i;update();viewer.showModal()}));document.getElementById("previousPhoto").addEventListener("click",()=>change(-1));document.getElementById("nextPhoto").addEventListener("click",()=>change(1));document.getElementById("closeViewer").addEventListener("click",()=>viewer.close());viewer.addEventListener("click",e=>{if(e.target===viewer)viewer.close()});document.addEventListener("keydown",e=>{if(!viewer.open)return;if(e.key==="ArrowRight")change(1);if(e.key==="ArrowLeft")change(-1)})})();</script></div>''',item=item,urls=urls)

FORM='''<div class="eyebrow">Parlons de votre projet</div><h1>{{heading}}</h1><p>{{intro}}</p><form method="post" enctype="multipart/form-data">{{csrf|safe}}<label>Votre nom<input name="name" maxlength="120" required></label><label>Courriel<input type="email" name="email" maxlength="200" required></label><label>Téléphone (facultatif)<input name="phone" maxlength="40"></label>{% if quote %}<label>Matériau souhaité<select name="material">{% for m in materials %}<option>{{m}}</option>{% endfor %}</select></label>{% endif %}<label>Description de votre {{'projet' if quote else 'message'}}<textarea name="description" maxlength="5000" required></textarea></label>{% if quote %}<label>Fichier STL ou 3MF (facultatif, maximum 8 Mo)<input type="file" name="model" accept=".stl,.3mf"></label>{% endif %}<button type="submit">Envoyer la demande</button></form>'''
def submission(kind):
 if request.method=="GET":
  return page(kind,FORM,heading="Demander une soumission" if kind=="Soumission" else "Nous contacter",intro="Décrivez votre projet et joignez votre modèle 3D si vous en avez un." if kind=="Soumission" else "Envoyez-nous votre message directement depuis ce formulaire.",quote=kind=="Soumission",materials=MATERIALS,csrf=csrfinput())
 verify()
 name=request.form.get("name","").strip();email=request.form.get("email","").strip().lower();description=request.form.get("description","").strip();phone=request.form.get("phone","").strip()[:40]
 if not name or len(name)>120 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or len(email)>200 or not description or len(description)>5000:abort(400)
 if not rate_limit():abort(429)
 material=request.form.get("material","À déterminer") if kind=="Soumission" else None
 if material and material not in MATERIALS:abort(400)
 f=request.files.get("model");filename=None;data=None
 if f and f.filename:
  filename=secure_filename(f.filename)
  if not filename.lower().endswith((".stl",".3mf")):abort(400)
  data=f.read(8*1024*1024+1)
  if len(data)>8*1024*1024:abort(413)
  if filename.lower().endswith(".3mf") and not data.startswith(b"PK"):abort(400)
  if filename.lower().endswith(".stl") and len(data)<84:abort(400)
 with db() as c:c.execute("INSERT INTO requests(kind,name,email,phone,material,description,filename,filedata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(kind,name,email,phone,material,description,filename,data))
 notify(kind,name,email)
 return page("Merci",'<h1>Merci!</h1><p>Votre demande a bien été enregistrée. Nous vous répondrons dès que possible.</p><a class="btn" href="/">Retour à l’accueil</a>')
@app.route("/soumission",methods=["GET","POST"])
def quote():return submission("Soumission")
@app.route("/contact",methods=["GET","POST"])
def contact():return submission("Contact")
@app.route("/admin/setup",methods=["GET","POST"])
def setup():
 # Requires a one-time secret configured by the owner in Railway, never shown publicly.
 setup_token=os.getenv("ADMIN_SETUP_TOKEN","")
 with db() as c:already=c.execute("SELECT 1 FROM settings WHERE key='admin_password_hash'").fetchone()
 if already or os.getenv("ADMIN_PASSWORD_HASH"):abort(404)
 if len(setup_token)<24:return page("Configuration",'<h1>Configuration indisponible</h1><p>Configurez ADMIN_SETUP_TOKEN (au moins 24 caractères) dans les variables Railway du service site-web avant de continuer.</p>')
 if request.method=="POST":
  verify()
  token=request.form.get("token","")
  password=request.form.get("password","")
  confirm=request.form.get("confirm","")
  if not hmac.compare_digest(token,setup_token):
   flash("Code de configuration incorrect.")
  elif len(password)<12 or len(password)>256 or password!=confirm:
   flash("Utilisez un mot de passe de 12 caractères minimum, identique dans les deux champs.")
  else:
   salt=secrets.token_bytes(16)
   hashed=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,350000).hex()
   value=salt.hex()+"$"+hashed
   with db() as c:
    # One-time, atomic insertion; never overwrites an existing password.
    result=c.execute("INSERT INTO settings(key,value) VALUES('admin_password_hash',%s) ON CONFLICT (key) DO NOTHING RETURNING key",(value,)).fetchone()
   if result:
    flash("Mot de passe créé! Connectez-vous.")
    return redirect("/admin/login")
   abort(409)
 return page("Première configuration",'''<h1>Créer mon accès administrateur</h1><p>Cette page fonctionne une seule fois. Votre code de configuration est celui que vous avez choisi dans Railway.</p><form method="post">{{csrf|safe}}<label>Code de configuration<input name="token" type="password" minlength="24" required autocomplete="off"></label><label>Nouveau mot de passe administrateur<input name="password" type="password" minlength="12" required autocomplete="new-password"></label><label>Confirmer le mot de passe<input name="confirm" type="password" minlength="12" required autocomplete="new-password"></label><button>Créer mon compte administrateur</button></form>''',csrf=csrfinput())
@app.route("/admin/login",methods=["GET","POST"])
def login():
 with db() as c:
  setting=c.execute("SELECT value FROM settings WHERE key='admin_password_hash'").fetchone()
 configured=setting["value"] if setting else os.getenv("ADMIN_PASSWORD_HASH","")
 if not configured:
  return page("Administration",'<h1>Administration non activée</h1><p>Pour créer votre accès sur téléphone, configurez ADMIN_SETUP_TOKEN dans Railway puis ouvrez <a href="/admin/setup">la configuration initiale</a>.</p>')
 if request.method=="POST":
  verify()
  entered=request.form.get("password","")
  try:
   salt,hashval=configured.split("$",1)
   actual=hashlib.pbkdf2_hmac("sha256",entered.encode(),bytes.fromhex(salt),350000).hex()
   valid=hmac.compare_digest(actual,hashval)
  except Exception:valid=False
  if valid:
   token=secrets.token_urlsafe(32)
   with db() as c:c.execute("INSERT INTO sessions(tokenhash,expires) VALUES(%s,NOW()+INTERVAL '12 hours')",(hashlib.sha256(token.encode()).hexdigest(),))
   session.clear();session["admin_token"]=token;return redirect("/admin")
  flash("Connexion refusée.")
 return page("Connexion",'<h1>Administration privée</h1><form method="post">{{csrf|safe}}<label>Mot de passe<input type="password" name="password" required autocomplete="current-password"></label><button>Se connecter</button></form>',csrf=csrfinput())
@app.get("/admin")
@admin_required
def admin():
 with db() as c:
  reqs=c.execute("SELECT id,kind,name,email,phone,material,description,filename,created,status,progress,live_enabled,live_url,public_progress FROM requests ORDER BY id DESC LIMIT 200").fetchall()
  gallery=c.execute("SELECT id,title,category FROM gallery ORDER BY id DESC").fetchall()
 return page("Administration",'''<h1>Tableau de bord</h1><div class="row"><a class="btn" href="/admin/modeles">📚 Mes modèles 3D</a><a class="btn" href="/admin/soumissions-pro">📄 Soumissions PRO</a><a class="btn" href="/admin/new">Ajouter une réalisation</a><form method="post" action="/admin/logout">{{csrf|safe}}<button>Déconnexion</button></form></div><h2>Demandes et commandes</h2><div class="grid">{% for r in reqs %}<article class="card"><div class="eyebrow">#{{r.id}} · {{r.kind}} · {{r.created.strftime('%Y-%m-%d')}}</div><h3>{{r.name}}</h3><p><a href="mailto:{{r.email}}">{{r.email}}</a> · {{r.phone or ''}}</p><p>Matériau : {{r.material or '—'}}</p><p style="white-space:pre-wrap">{{r.description}}</p>{% if r.filename %}<p><a href="/admin/file/{{r.id}}">Télécharger {{r.filename}}</a></p>{% if r.kind=='Soumission' %}<form method="post" action="/admin/modeles/import-demande/{{r.id}}">{{csrf|safe}}<button>📦 Importer le modèle et créer la soumission</button></form>{% endif %}{% elif r.kind=='Soumission' %}<p><a href="/admin/soumissions-pro?request_id={{r.id}}">📄 Préparer une soumission PRO</a></p>{% endif %}<form method="post" action="/admin/status/{{r.id}}">{{csrf|safe}}<label>Statut<select name="status">{% for s in statuses %}<option {% if s==r.status %}selected{% endif %}>{{s}}</option>{% endfor %}</select></label><label>Progression réelle (%)<input type="number" name="progress" min="0" max="100" value="{{r.progress if r.progress is not none else ''}}" placeholder="Non disponible"></label><label><input type="checkbox" name="public_progress" value="1" {% if r.public_progress %}checked{% endif %}> Afficher anonymement la progression sur l'accueil</label><label>Lien OctoEverywhere temporaire (oe.ink)<input type="url" name="live_url" maxlength="500" placeholder="https://oe.ink/l/..." value="{{r.live_url or ''}}"></label><label><input type="checkbox" name="live_enabled" value="1" {% if r.live_enabled %}checked{% endif %}> Autoriser la diffusion privée (à configurer)</label><button>Enregistrer</button></form></article>{% else %}<p>Aucune demande pour le moment.</p>{% endfor %}</div><h2>Galerie</h2><div class="grid">{% for g in gallery %}<div class="card"><strong>{{g.title}}</strong><p>{{g.category}}</p><a href="/admin/edit/{{g.id}}">Modifier / Photos</a><form method="post" action="/admin/delete/{{g.id}}" onsubmit="return confirm('Supprimer cette réalisation?')">{{csrf|safe}}<button>Supprimer</button></form></div>{% endfor %}</div>''',reqs=reqs,gallery=gallery,statuses=STATUSES,csrf=csrfinput())
@app.post("/admin/status/<int:id>")
@admin_required
def status(id):
 verify();value=request.form.get("status")
 if value not in STATUSES:abort(400)
 progress=request.form.get("progress","").strip()
 if progress and (not progress.isdigit() or not 0<=int(progress)<=100):abort(400)
 pct=int(progress) if progress else None
 live=request.form.get("live_enabled")=="1"
 public_progress=request.form.get("public_progress")=="1"
 live_url=request.form.get("live_url","").strip()
 if live_url:
  parsed=urlparse(live_url)
  if parsed.scheme!="https" or parsed.hostname not in ("oe.ink","www.oe.ink") or not parsed.path.startswith("/l/") or parsed.username or parsed.password or len(live_url)>500:abort(400)
 with db() as c:c.execute("UPDATE requests SET status=%s,progress=%s,live_enabled=%s,live_url=%s,public_progress=%s WHERE id=%s",(value,pct,live,live_url or None,public_progress,id))
 return redirect("/admin")
@app.get("/admin/file/<int:id>")
@admin_required
def file(id):
 with db() as c:r=c.execute("SELECT filename,filedata FROM requests WHERE id=%s",(id,)).fetchone()
 if not r or not r["filedata"]:abort(404)
 return send_file(io.BytesIO(r["filedata"]),as_attachment=True,download_name=r["filename"],mimetype="application/octet-stream")
def image_uploads(files):
 images=[]
 for f in files:
  if not f or not f.filename:continue
  data=f.read(5*1024*1024+1)
  if len(data)>5*1024*1024:abort(413)
  mime="image/jpeg" if data.startswith(bytes.fromhex("ffd8ff")) else "image/png" if data.startswith(bytes.fromhex("89504e470d0a1a0a")) else "image/webp" if data.startswith(b"RIFF") and data[8:12]==b"WEBP" else None
  if not mime:abort(400)
  images.append((data,mime))
 return images
GALLERY_FORM='''<h1>{{heading}}</h1><form method="post" enctype="multipart/form-data">{{csrf|safe}}<label>Titre<input name="title" value="{{item.title if item else ''}}" maxlength="120" required></label><label>Catégorie<input name="category" value="{{item.category if item else ''}}" maxlength="120" required></label><label>Description<textarea name="description" maxlength="2000" required>{{item.description if item else ''}}</textarea></label><label>Ajouter des photos (6 à la fois, 5 Mo chacune)<input type="file" name="photos" multiple accept="image/jpeg,image/png,image/webp"></label><button>Enregistrer</button></form>{% for p in photos %}<div class="row"><img src="/gallery/image/{{p.id}}" width="85"><form method="post" action="/admin/photo/delete/{{p.id}}">{{csrf|safe}}<button>Supprimer cette photo</button></form></div>{% endfor %}'''
@app.route("/admin/new",methods=["GET","POST"])
@admin_required
def new():return gallery_edit(None)
@app.route("/admin/edit/<int:id>",methods=["GET","POST"])
@admin_required
def edit(id):return gallery_edit(id)
def gallery_edit(id):
 with db() as c:
  item=c.execute("SELECT id,title,category,description FROM gallery WHERE id=%s",(id,)).fetchone() if id else None
  if id and not item:abort(404)
  if request.method=="POST":
   verify()
   title=request.form.get("title","").strip();category=request.form.get("category","").strip();description=request.form.get("description","").strip()
   if not title or not category or not description or max(len(title),len(category))>120 or len(description)>2000:abort(400)
   files=request.files.getlist("photos")
   if len(files)>6:abort(400)
   images=image_uploads(files)
   if id:c.execute("UPDATE gallery SET title=%s,category=%s,description=%s WHERE id=%s",(title,category,description,id))
   else:id=c.execute("INSERT INTO gallery(title,category,description) VALUES(%s,%s,%s) RETURNING id",(title,category,description)).fetchone()["id"]
   for data,mime in images:c.execute("INSERT INTO gallery_photos(gallery_id,photo,mime) VALUES(%s,%s,%s)",(id,data,mime))
   return redirect("/admin/edit/"+str(id))
  photos=c.execute("SELECT id FROM gallery_photos WHERE gallery_id=%s ORDER BY id",(id,)).fetchall() if id else []
 return page("Galerie",GALLERY_FORM,heading="Modifier la réalisation" if id else "Nouvelle réalisation",item=item,photos=photos,csrf=csrfinput())
@app.post("/admin/photo/delete/<int:id>")
@admin_required
def remove_photo(id):
 verify()
 with db() as c:r=c.execute("DELETE FROM gallery_photos WHERE id=%s RETURNING gallery_id",(id,)).fetchone()
 if not r:abort(404)
 return redirect("/admin/edit/"+str(r["gallery_id"]))
@app.get("/photo/<int:id>")
def photo(id):
 with db() as c:r=c.execute("SELECT photo,mime FROM gallery WHERE id=%s",(id,)).fetchone()
 if not r or not r["photo"]:abort(404)
 return send_file(io.BytesIO(r["photo"]),mimetype=r["mime"],max_age=3600)
@app.post("/admin/delete/<int:id>")
@admin_required
def delete(id):
 verify()
 with db() as c:c.execute("DELETE FROM gallery WHERE id=%s",(id,))
 return redirect("/admin")
@app.post("/admin/logout")
@admin_required
def logout():
 verify();token=session.get("admin_token")
 with db() as c:c.execute("DELETE FROM sessions WHERE tokenhash=%s",(hashlib.sha256(token.encode()).hexdigest(),))
 session.clear();return redirect("/")
@app.get("/health")
def health():return {"ok":True}

@app.get("/admin/atelier-3d")
@admin_required
def atelier_3d():
 from private_fjord import admin_studio
 with open("atelier3d.html",encoding="utf-8") as source:
  html=admin_studio(source.read(),csrf())
 return app.response_class(html,mimetype="text/html",headers={"Cache-Control":"no-store"})

@app.get("/atelier-3d")
def atelier_3d_public():
 from private_fjord import public_studio
 with open("atelier3d.html",encoding="utf-8") as source:
  html=public_studio(source.read())
 return app.response_class(html,mimetype="text/html")

# Register admin-only model library and professional quotations.
from private_fjord import register_private_fjord
register_private_fjord(app,db,admin_required,verify,csrfinput,csrf,page)
