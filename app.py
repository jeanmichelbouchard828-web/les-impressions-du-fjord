import os,io,re,hmac,time,uuid,hashlib,secrets,datetime,smtplib
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlparse
from flask import Flask,request,redirect,render_template_string,session,abort,send_file,flash,url_for,jsonify
import psycopg
from psycopg.rows import dict_row
from werkzeug.utils import secure_filename
app=Flask(__name__)
from fjord_marketing import (MARKETING_CSS, MARKETING_HOME_START, MARKETING_HOME_END, MARKETING_GALLERY, MARKETING_FORM_HELP, MARKETING_SCRIPT)
from fjord_inspirations import html_fragment as fjord_inspiration_html, IDEAS as FJORD_INSPIRATIONS
from fjord_gallery_pairing import unique_photo_match
from fjord_seo import seo_metadata, register_seo_routes, BUSINESS_SCHEMA
from fjord_preview_guard import install_preview_guard
install_preview_guard(app)
# Actual server-side slicing / layer toolpaths. The resulting generic G-code
# is NOT downloadable or intended for direct use on a Bambu X2D printer.
from real_slicer import slicer_bp
app.register_blueprint(slicer_bp)
app.secret_key=os.environ.get("SECRET_KEY",secrets.token_hex(32))
app.config.update(MAX_CONTENT_LENGTH=24*1024*1024,SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax")
from fjord_preview_guard import assert_preview_isolated
DB=os.environ["DATABASE_URL"]
assert_preview_isolated(DB)
STATUSES=["Demande reçue","Soumission envoyée","En impression","Terminée"]
MATERIALS=["À déterminer","PLA","PETG","PETG-CF","ASA","TPU","Autre"]
COLORS=["À déterminer","Noir","Blanc","Gris","Rouge","Bleu","Autre / à discuter"]
PROJECT_TYPES=["À déterminer","Pièce de remplacement","Support ou accessoire","Prototype","Cadeau personnalisé","Décoration","Autre projet"]
REMISE_OPTIONS=["À discuter","Ramassage local au Saguenay (à confirmer)","Expédition (prix et disponibilité à confirmer)"]
DELAI_OPTIONS=["Flexible","Dès que possible (selon disponibilité)","Dans les 2 prochaines semaines","À une date précise (indiquer en description)"]
def db():
 return psycopg.connect(DB,row_factory=dict_row)
def init():
 with db() as c:
  c.execute("""CREATE TABLE IF NOT EXISTS requests(id BIGSERIAL PRIMARY KEY,kind TEXT NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT,material TEXT,description TEXT NOT NULL,filename TEXT,filedata BYTEA,created TIMESTAMPTZ DEFAULT NOW(),status TEXT DEFAULT 'Demande reçue')""")
  # Additive, nullable customer reference image fields (existing orders remain unchanged).
  c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS reference_filename TEXT")
  c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS reference_photo BYTEA")
  c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS reference_mime TEXT")
  c.execute("""CREATE TABLE IF NOT EXISTS gallery(id BIGSERIAL PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,photo BYTEA,mime TEXT,created TIMESTAMPTZ DEFAULT NOW())""")
  c.execute("""CREATE TABLE IF NOT EXISTS sessions(tokenhash TEXT PRIMARY KEY,expires TIMESTAMPTZ NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS fjord_printer_recent_start (
      slot SMALLINT PRIMARY KEY CHECK (slot = 1),
      file_path TEXT NOT NULL,
      start_ack TEXT NOT NULL,
      sent_at DOUBLE PRECISION NOT NULL
  )""")
  c.execute("""CREATE TABLE IF NOT EXISTS gallery_photos(id BIGSERIAL PRIMARY KEY,gallery_id BIGINT REFERENCES gallery(id) ON DELETE CASCADE,photo BYTEA NOT NULL,mime TEXT NOT NULL)""")
  # A published photograph can have its own original STL/3MF; the project
  # default is used only when the photo doesn't have a dedicated model.
  # Historical photographs and customer orders are preserved as-is.
  c.execute("ALTER TABLE gallery ADD COLUMN IF NOT EXISTS model_filename TEXT")
  c.execute("ALTER TABLE gallery ADD COLUMN IF NOT EXISTS is_real_photo BOOLEAN NOT NULL DEFAULT FALSE")
  # Photos de pièces imprimées vérifiées visuellement dans la galerie actuelle.
  c.execute("UPDATE gallery SET is_real_photo=TRUE WHERE id IN (3,8)")
  c.execute("ALTER TABLE gallery ADD COLUMN IF NOT EXISTS model_data BYTEA")
  c.execute("ALTER TABLE gallery_photos ADD COLUMN IF NOT EXISTS model_filename TEXT")
  c.execute("ALTER TABLE gallery_photos ADD COLUMN IF NOT EXISTS model_data BYTEA")
  c.execute("ALTER TABLE gallery_photos ADD COLUMN IF NOT EXISTS original_filename TEXT")
  c.execute("""CREATE TABLE IF NOT EXISTS fjord_inspiration_models(
       source TEXT PRIMARY KEY, model_filename TEXT NOT NULL, model_data BYTEA NOT NULL,
       rights_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
       updated TIMESTAMPTZ DEFAULT NOW())""")
init()
# Compteur historique conservé; présence estimée dans une fenêtre de 5 min.
# Seul un hachage de cookie aléatoire est conservé, pas l'adresse IP.
from fjord_visitors import initialize as initialize_visitors, observe as observe_visitor, site_stats
initialize_visitors(db)

@app.before_request
def fjord_track_visit():
 if os.environ.get("FJORD_PREVIEW_MODE") == "1":
  return
 if request.method != "GET" or request.path.startswith(("/admin","/api","/static","/favicon","/gallery-photo","/galerie/photo","/health")):
  return
 from flask import g
 token=request.cookies.get("fjord_visitor")
 if not token or not re.fullmatch(r"[a-f0-9]{32}",token):
  token=secrets.token_hex(16)
  g.fjord_new_visitor_token=token
 try:
  observe_visitor(db,token)
 except Exception:
  app.logger.exception("Compteur de visiteurs indisponible")

@app.after_request
def fjord_set_visitor_cookie(response):
 from flask import g
 token=getattr(g,"fjord_new_visitor_token",None)
 if token:
  response.set_cookie("fjord_visitor",token,max_age=365*24*3600,secure=True,httponly=True,samesite="Lax")
 return response

@app.get("/api/public/visitors")
def fjord_visitors_public_stats():
 """Expose aggregated totals only, never cookie hashes or timestamps."""
 if os.environ.get("FJORD_PREVIEW_MODE") != "1":
  token=request.cookies.get("fjord_visitor")
  if token:
   try:
    observe_visitor(db,token)
   except Exception:
    app.logger.exception("Actualisation présence indisponible")
 try:
  snapshot=site_stats(db)
 except Exception:
  app.logger.exception("Statistiques de visites indisponibles")
  snapshot=None
 if snapshot is None:
  return jsonify(error="Statistiques temporairement indisponibles"),503,{"Cache-Control":"no-store"}
 return jsonify(snapshot),200,{"Cache-Control":"no-store"}

@app.context_processor
def fjord_visitor_count():
 try:
  snapshot=site_stats(db)
 except Exception:
  snapshot=None
 return {"fjord_visitors":snapshot["total"] if snapshot else None,
         "fjord_online_visitors":snapshot["online"] if snapshot else None}

# Migration additive : progression renseignée par l'administrateur, jamais simulée.
with db() as c:
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS progress INTEGER")
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS live_enabled BOOLEAN NOT NULL DEFAULT FALSE")
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS live_url TEXT")
 c.execute("ALTER TABLE requests ADD COLUMN IF NOT EXISTS public_progress BOOLEAN NOT NULL DEFAULT FALSE")
STYLE="""<style>*{box-sizing:border-box}body{margin:0;background:#071321;color:#f2faff;font:16px system-ui,Arial}header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 5%;border-bottom:1px solid #2a4a62;background:#091a2b;flex-wrap:wrap}nav{display:flex;gap:15px;flex-wrap:wrap}a{color:#7fe4ff;text-decoration:none}.brand{font-weight:900;letter-spacing:.6px}main{max-width:1100px;margin:auto;padding:28px 20px 70px}.hero{padding:70px 0 90px;background:radial-gradient(ellipse at 80% 10%,#15618a77,transparent 60%)}h1{font-size:clamp(38px,7vw,78px);line-height:1.06;margin:15px 0}h2{font-size:30px}p{color:#c6d7e7;line-height:1.65}.eyebrow{color:#80dfff;letter-spacing:3px;text-transform:uppercase;font-size:13px;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}.card{background:#10283b;border:1px solid #2d526d;padding:22px;border-radius:16px;overflow:hidden}.card img{width:100%;height:220px;object-fit:cover;border-radius:10px}.gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:14px}.gallery-grid img{width:100%;height:145px;object-fit:cover;border-radius:9px}.gallery-tile{background:#10283b;padding:12px;border-radius:12px}.gallery-tile h3{font-size:15px}.zoom{background:#071321;color:white;border:0;max-width:96vw;max-height:95vh}.zoom::backdrop{background:#000d}.zoom img{max-width:90vw;max-height:78vh;object-fit:contain}.gallery-detail h1{font-size:clamp(26px,4vw,42px);line-height:1.15;overflow-wrap:anywhere;max-width:850px}.gallery-detail .gallery-grid{margin-top:22px}.gallery-photo-link{display:block;cursor:zoom-in}.gallery-photo-link img{display:block;width:100%;height:160px;object-fit:cover;border-radius:10px}.zoom[open]{display:block;position:fixed;inset:0;margin:auto;padding:12px;box-shadow:0 20px 80px #000b}.zoom .row{justify-content:center;margin-bottom:10px}.zoom img{display:block;margin:auto;max-width:min(90vw,1100px);max-height:75vh}@media(max-width:600px){.gallery-detail h1{font-size:clamp(24px,7vw,32px)}.gallery-detail .gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}input,textarea,select{display:block;width:100%;padding:12px;margin:7px 0 17px;background:#081827;color:white;border:1px solid #47718b;border-radius:9px;font:inherit}label{display:block;font-weight:600}textarea{min-height:110px}button,.btn{display:inline-block;padding:13px 20px;border:0;border-radius:9px;background:#5ad7f5;color:#061b2a;font-weight:800;cursor:pointer;font:inherit;text-decoration:none}form{max-width:650px}.muted{color:#a9c3d3}.alert{padding:14px;background:#163e50;border-radius:9px;margin:15px 0}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.row form{display:inline}.small{font-size:13px}.contact-actions{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 28px}.contact-actions a{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:13px 18px;border-radius:10px;background:#163e59;border:1px solid #4a91b6;color:#f2faff;font-weight:750}.contact-actions a:hover{background:#215b7d}.contact-actions a:focus-visible{outline:3px solid #7fe4ff;outline-offset:3px}footer{padding:25px 5%;border-top:1px solid #294b62;color:#a9c3d3}@media(max-width:600px){.hero{padding:40px 0}header{align-items:flex-start}nav{font-size:14px}}</style>"""
GLOBAL_FJORD_THEME="""<style>
:root{--fjord-electric:#35c4ff;--fjord-border:#2b719e;--fjord-deep:#071321}
body{background:linear-gradient(155deg,#06111f,#091f35 55%,#061321);background-attachment:fixed}
header{background:linear-gradient(105deg,#06172a,#0b3656);border-bottom:2px solid #168ac5;box-shadow:0 5px 25px #0005}
header .brand{color:#e7f8ff;text-shadow:0 0 14px #0caeff55}
nav a{transition:color .15s}nav a:hover{color:#fff}
main{max-width:1220px}
.card,.gallery-tile{border-color:var(--fjord-border);background:linear-gradient(145deg,#122e49,#0b2237);box-shadow:0 8px 22px #0002}
.card{border-radius:17px}
.btn,button{border-radius:10px}
.btn:hover,button:hover{filter:brightness(1.09)}
.hero{background:radial-gradient(ellipse at 85% 15%,#09699a55,transparent 62%)}
input:focus-visible,select:focus-visible,textarea:focus-visible,a:focus-visible,button:focus-visible{outline:2px solid #56d5ff;outline-offset:2px}
body.light .card,body.light .gallery-tile{background:#f2f9ff;border-color:#b0d7ea}
@media(max-width:650px){header{padding:13px 4%}main{padding:20px 13px 55px}.card{padding:16px}}
</style>"""
FJORD_SITE_PREMIUM="""<style>
/* Identité Fjord 2026 : présentation commune aux pages publiques et administratives */
:root{--fjord-neon:#29bcff;--fjord-edge:#267fba}
body:not(.light){background:radial-gradient(ellipse at 85% 0%,#10517a40,transparent 48%),linear-gradient(160deg,#040e1c 0%,#071a30 52%,#040f1f 100%)}
header{position:relative;isolation:isolate;min-height:105px;padding:15px clamp(16px,3vw,50px);border-bottom:2px solid #128de2;background:linear-gradient(110deg,#030e1e 0%,#082b4b 60%,#041326 100%);box-shadow:0 9px 26px #0008}
header:before{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;opacity:.7;background:linear-gradient(133deg,transparent 0%,transparent 65%,#1177c033 66%,transparent 74%,#098ce02b 80%,transparent 89%)}
header .brand{display:flex;align-items:center;gap:14px;max-width:100%;font-size:clamp(16px,2vw,25px);font-weight:950;font-style:italic;letter-spacing:.035em;color:#f4fbff;text-shadow:0 2px 1px #00101f,0 0 18px #138ad555}
header .brand img{width:78px!important;height:78px!important;margin-right:0!important;filter:drop-shadow(0 0 9px #0db9ff66)}
header nav{align-items:center;gap:8px 14px}
header nav a{padding:9px 8px;border-radius:8px;font-weight:700;color:#c6eaff}
header nav a:hover{background:#0c4774;color:#fff}
header nav a[href="/atelier-3d"][aria-current="page"]{background:linear-gradient(125deg,#006db8,#159ce1);color:#fff;border:1px solid #65d8ff;box-shadow:0 0 15px #08a9ff44}
.pref-controls select{border-color:#317aa8;background:#0a2139;color:#e5f8ff}
main{max-width:1320px}
.hero{padding:70px clamp(12px,3vw,35px);border-radius:20px;border:1px solid #1b6190;background:radial-gradient(ellipse at 80% 12%,#087ec65c,transparent 55%),linear-gradient(120deg,#071b32,#0a3150);box-shadow:0 16px 38px #0005}
.hero h1{color:#fff;text-shadow:0 3px 18px #0008}
.card,.gallery-tile,.tracking-billboard,.atelier-feature{border:1px solid #2783b7;box-shadow:0 10px 26px #0003}
.card h2,.card h3{color:#eaf9ff}
.btn{background:linear-gradient(115deg,#0879bf,#25c0f4);color:#fff;border:1px solid #70d9ff;box-shadow:0 4px 14px #006ca544;font-weight:800}
.btn:hover{background:linear-gradient(115deg,#1195df,#5bd5fa)}
.contact-section{padding:22px;border-radius:18px;border:1px solid #21577c;background:linear-gradient(120deg,#0c2339,#0c2c45)}
footer{background:#050f1e}
body.light header{background:linear-gradient(110deg,#e7f5ff,#c8eaff);border-bottom-color:#2589bd}
body.light header .brand{color:#10314c;text-shadow:none}
body.light header nav a{color:#154d70}
body.light header nav a:hover{color:#fff}
body.light .hero{background:linear-gradient(120deg,#e9f8ff,#b8e7ff);border-color:#77bce3}
body.light .hero h1,body.light .card h2,body.light .card h3{color:#14354c;text-shadow:none}
body.light .contact-section{background:#f1faff;border-color:#add6ec}
@media(max-width:850px){header{min-height:0;gap:12px}header .brand{flex:1 1 100%}header nav{order:3;width:100%;justify-content:flex-start}header .brand img{width:57px!important;height:57px!important}.pref-controls{margin-left:auto}.hero{padding:32px 18px}}
@media(max-width:480px){header nav{gap:3px 5px}header nav a{font-size:13px;padding:7px}header .brand{font-size:18px}.pref-controls select{min-width:0;max-width:115px}.contact-section{padding:15px}}
</style>"""
FJORD_FULL_BRANDING="""<style>
/* Identité commune du site : maquette Fjord, sans toucher aux actions */
header{min-height:118px;background:linear-gradient(110deg,#03101f 0%,#082f52 55%,#04162c 100%);border-bottom:2px solid #21a9f4;box-shadow:0 8px 28px #0009}
header:after{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;opacity:.52;background:linear-gradient(138deg,transparent 62%,#139cdd44 62.5%,transparent 65%),linear-gradient(24deg,transparent 73%,#31c5ff33 74%,transparent 76%);background-position:right center;background-repeat:no-repeat}
header .brand{display:grid;grid-template-columns:78px auto;grid-template-rows:auto auto auto;column-gap:14px;align-items:center;font-size:clamp(18px,2vw,27px);font-style:italic;line-height:1.05}
header .brand img{grid-row:1/4;grid-column:1;width:76px!important;height:76px!important;margin:0!important}
header .brand .fjord-brand-blue{grid-row:2;grid-column:2;color:#3bc7ff;font-weight:950;text-shadow:0 0 14px #10a9ff77}
header .brand .fjord-brand-tagline{grid-row:3;grid-column:2;color:#c7eaff;font-size:10px;font-weight:650;font-style:normal;letter-spacing:.24em;margin-top:5px;text-shadow:none}
header nav a{border:1px solid transparent}
header nav a:hover{border-color:#36b4e8;background:#12537b}
main h1,main h2{letter-spacing:-.025em}
.card,.gallery-tile{border-radius:16px;transition:border-color .18s,box-shadow .18s}
.card:hover,.gallery-tile:hover{border-color:#45baf4;box-shadow:0 12px 28px #0004}
main input,main textarea,main select{border-radius:9px}
main input:focus,main textarea:focus,main select:focus{border-color:#39c7ff}
footer{border-top:1px solid #175a8b}
body.light header .brand{color:#153b57;text-shadow:none}
body.light header .brand .fjord-brand-blue{color:#087fb9;text-shadow:none}
body.light header .brand .fjord-brand-tagline{color:#285e7b}
@media(max-width:850px){header{min-height:0}header .brand{grid-template-columns:60px auto;font-size:20px}header .brand img{width:58px!important;height:58px!important}header nav{width:100%;overflow-x:auto;scrollbar-width:thin;padding-bottom:5px}header nav a{white-space:nowrap}}
@media(max-width:480px){header .brand{grid-template-columns:49px auto;font-size:17px;column-gap:9px}header .brand img{width:48px!important;height:48px!important}header .brand .fjord-brand-tagline{font-size:8px;letter-spacing:.12em}}
</style>"""
FJORD_LAYOUT_SIDEBAR="""<style>
footer .fjord-footer-legal{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:10px 20px;width:100%;padding:12px 8px}footer .fjord-footer-legal a{color:#a9e6ff;text-decoration:underline;text-underline-offset:3px;font-weight:650;min-height:40px;display:inline-flex;align-items:center}footer .fjord-footer-legal a:hover,footer .fjord-footer-legal a:focus-visible{color:#fff}
/* Maquette Fjord : bandeau pleine largeur, navigation latérale et contenu */
header{position:relative;z-index:12;width:100%;box-sizing:border-box}
.fjord-side-nav{position:fixed;z-index:10;left:0;top:118px;bottom:0;width:224px;box-sizing:border-box;padding:18px 10px 20px;background:linear-gradient(180deg,#031225 0%,#061b32 65%,#031020 100%);border-right:1px solid #2574a9;box-shadow:6px 0 25px #0005;display:flex;flex-direction:column;justify-content:space-between;overflow-y:auto}
.fjord-side-menu{display:flex;flex-direction:column;gap:5px}
.fjord-side-menu a{display:flex;align-items:center;gap:13px;padding:11px 13px;border-radius:9px;text-decoration:none;color:#f0f8ff;font-weight:750;font-size:15px;transition:background .16s,box-shadow .16s}
.fjord-side-menu a:hover,.fjord-side-menu a:focus-visible{background:linear-gradient(100deg,#0866a5,#0d8cce);box-shadow:inset 0 0 0 1px #39c5ff}
.fjord-side-menu a[aria-current="page"]{border-left:3px solid #30c6ff;background:linear-gradient(100deg,#0866a5,#0d8cce)}
.fjord-side-menu hr{width:100%;border:0;border-top:1px solid #2c638c;margin:14px 0}
.fjord-side-label{font-size:12px;color:#a8c8e2;margin:0 12px 6px}
.fjord-side-deco{margin:28px 4px 8px;padding:18px 7px;text-align:center;font-size:12px;line-height:1.3;font-weight:850;font-style:italic;color:#fff;border-top:2px solid #21bfff;border-bottom:2px solid #21bfff;background:radial-gradient(ellipse at center,#11679a88,transparent 75%);text-shadow:0 0 9px #15bfff}
.fjord-side-deco b{display:block;font-size:23px;color:#4bcfff}
.fjord-side-deco small{display:block;letter-spacing:.15em;font-size:9px;font-style:normal}
body>main{margin-left:224px;max-width:none;width:calc(100% - 224px);box-sizing:border-box;padding-left:clamp(16px,2.5vw,38px);padding-right:clamp(16px,2.5vw,38px)}
body>footer{margin-left:224px}
header nav{gap:8px}
body.light .fjord-side-nav{background:linear-gradient(#e8f6ff,#d6ebfa);border-right-color:#8bc1e4}
body.light .fjord-side-menu a{color:#17425e}
body.light .fjord-side-menu a:hover{color:#fff}
body.light .fjord-side-deco{color:#154568}
@media(max-width:1100px){.fjord-side-nav{top:0;position:relative;width:100%;height:auto;padding:8px 12px;overflow-x:auto;overflow-y:hidden;border-right:0;border-bottom:1px solid #2584b6}.fjord-side-menu{flex-direction:row;gap:4px;width:max-content}.fjord-side-menu a{font-size:13px;padding:8px 11px;white-space:nowrap}.fjord-side-menu hr,.fjord-side-label,.fjord-side-deco{display:none}body>main{margin-left:0;width:100%}body>footer{margin-left:0}header nav{display:none}}
@media(max-width:600px){.fjord-side-menu a{padding:8px 10px}.fjord-side-nav{padding:6px 8px}body>main{padding:16px 12px}}
</style>"""
FJORD_FINISHING="""<style>
/* Finition globale : mêmes contrastes, contrôles et panneaux partout */
:root{--fjord-accent:#21c4ff;--fjord-accent-soft:#8be8ff;--fjord-card:#0a2139;--fjord-line:#2782bb}
body:not(.light) main{color:#e8f5ff}
body:not(.light) main :is(section,article,fieldset){border-color:#2a729f}
body:not(.light) main :is(input,textarea,select){background-color:#071a2d;color:#f2fbff;border:1px solid #31739e}
body:not(.light) main :is(input,textarea,select):focus{outline:2px solid #38c9ff;outline-offset:1px}
body:not(.light) main :is(table){border-collapse:separate;border-spacing:0;width:100%;border:1px solid #267eb4;border-radius:12px;overflow:hidden}
body:not(.light) main th{background:#0c3d64;color:#dcf7ff}
body:not(.light) main td{border-bottom:1px solid #244f70}
body:not(.light) main tr:last-child td{border-bottom:0}
body:not(.light) main :is(details){border-color:#2d7dad;border-radius:12px}
body:not(.light) main summary{cursor:pointer}
body:not(.light) main :is(a.btn,button.btn,input[type=submit]){background:linear-gradient(115deg,#0765a5,#08a4e5);border:1px solid #50cfff;color:#fff;box-shadow:0 4px 15px #078fd444}
body:not(.light) main :is(a.btn,button.btn,input[type=submit]):hover{filter:brightness(1.12)}
body:not(.light) main :is(.muted,.small){color:#b2d1e6}
body:not(.light) main :is(h1,h2,h3){text-shadow:0 2px 14px #0006}
.fjord-side-menu a:focus-visible{outline:2px solid #54d7ff;outline-offset:1px}
body.light main :is(input,textarea,select){border-color:#8dbdd7}
body.light main th{background:#d8efff;color:#103a56}
@media(prefers-reduced-motion:reduce){.fjord-side-menu a,.card,.gallery-tile,.btn{transition:none!important}}
@media(max-width:650px){main table{display:block;overflow-x:auto}main :is(input,select,textarea){max-width:100%;box-sizing:border-box}}
</style>"""
FJORD_VISITOR_STYLE="""<style>.fjord-visitor-counter{display:inline-flex;gap:7px;align-items:center;padding:9px 14px;border:1px solid #247eae;border-radius:30px;background:#0c2b44;color:#c5edff;font-size:13px;margin:12px 0}.fjord-visitor-counter strong{color:#58d5ff;font-size:16px}body.light .fjord-visitor-counter{background:#e7f6ff;color:#154b6b}</style>"""
FJORD_DONATION_STYLE="""<style>.fjord-donation-link{display:inline-flex;align-items:center;justify-content:center;padding:10px 17px;margin:12px 8px 12px 0;border:1px solid #62d6ff;border-radius:28px;background:linear-gradient(110deg,#07558a,#099ed3);color:#fff!important;font-weight:800;box-shadow:0 4px 18px #0397da55}.fjord-donation-link:hover{filter:brightness(1.12)}.fjord-support-panel{max-width:660px;margin:25px auto;padding:28px;border:1px solid #2b9bd1;border-radius:20px;background:linear-gradient(140deg,#102e49,#081c30);text-align:center}.fjord-support-panel h1{font-size:clamp(30px,5vw,48px)}.fjord-support-panel p{color:#d1eafb}.fjord-support-panel .fjord-donation-link{font-size:18px;margin-top:16px}</style>"""
FJORD_PRO_REDESIGN="""<style>
:root{--fjord-bg:#071321;--fjord-surface:#0d2135;--fjord-surface-2:#112c45;--fjord-text:#eef7ff;--fjord-muted:#b7c9d8;--fjord-line:#284b65;--fjord-accent:#29b8eb;--fjord-accent-2:#70def7;--fjord-radius:16px}
html{scroll-behavior:smooth;scroll-padding-top:20px}
body{min-height:100vh;background:radial-gradient(ellipse at 84% -8%,#17507844,transparent 42%),linear-gradient(160deg,#071321,#091b2d 60%,#071321);color:var(--fjord-text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;line-height:1.55}
.site-header{position:sticky;top:0;z-index:100;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:clamp(10px,2vw,24px);width:100%;min-height:80px;padding:10px clamp(14px,3vw,42px);background:#07182bef;border-bottom:1px solid #20587a;box-shadow:0 8px 24px #00101f66;backdrop-filter:blur(16px)}
.site-header .brand{display:grid;grid-template-columns:54px auto;grid-template-rows:auto auto auto;column-gap:11px;align-items:center;min-width:0;color:#f1f9ff;text-decoration:none;font-size:clamp(14px,1.5vw,19px);font-weight:850;letter-spacing:.015em;line-height:1.05}
.site-header .brand img{grid-column:1;grid-row:1/4;width:52px!important;height:52px!important;margin:0!important;border-radius:12px;object-fit:cover}
.site-header .brand-main{grid-column:2;grid-row:1}.site-header .brand-blue{grid-column:2;grid-row:2;color:#42c8f2;font-weight:950}
.site-header .fjord-brand-tagline{grid-column:2;grid-row:3;margin-top:4px;color:#b6d2e2;font-size:8px;font-weight:700;letter-spacing:.17em}
.site-header nav{display:flex;align-items:center;justify-content:center;gap:4px;min-width:0}
.site-header nav a{display:inline-flex;align-items:center;min-height:40px;padding:8px 10px;border:1px solid transparent;border-radius:10px;color:#c4d8e7;font-size:13px;font-weight:700;text-decoration:none;white-space:nowrap}
.site-header nav a:hover,.site-header nav a[aria-current=page]{background:#123954;border-color:#2b7194;color:#fff}
.site-header .pref-controls{display:flex;align-items:center;gap:7px}.site-header .pref-controls select{width:auto;min-width:92px;max-width:130px;min-height:39px;margin:0;padding:7px 9px;border:1px solid #315f7c;border-radius:10px;background:#0b2238;color:#e6f4ff;font-size:12px}
.site-nav-toggle{display:none;align-items:center;justify-content:center;gap:7px;min-height:42px;padding:9px 12px;border:1px solid #347b9d;border-radius:11px;background:#102e47;color:#f1fbff;font-size:14px;font-weight:800;cursor:pointer}
body>main{width:min(100%,1440px)!important;max-width:1440px!important;margin:0 auto!important;padding:clamp(22px,4vw,52px) clamp(14px,3.5vw,50px) clamp(48px,7vw,84px)!important}
body>footer{margin:0!important;padding:26px clamp(14px,4vw,54px);border-top:1px solid #244760;background:#06111f;color:#a9bfce}
main h1{font-size:clamp(30px,5vw,56px);line-height:1.08;letter-spacing:-.04em;color:#f4fbff}main h2{font-size:clamp(22px,3vw,31px);line-height:1.2;letter-spacing:-.025em}
main p{color:var(--fjord-muted);line-height:1.65}
main :is(section,article,fieldset){scroll-margin-top:95px}
main .hero{border:1px solid #286a8c;border-radius:22px;background:radial-gradient(ellipse at 78% 10%,#1279a640,transparent 55%),linear-gradient(135deg,#102c45,#0a1d31);box-shadow:0 22px 54px #0003}
main .card,main .gallery-tile,main .tracking-result{border:1px solid var(--fjord-line);border-radius:var(--fjord-radius);background:linear-gradient(150deg,#10283c,#0a1d30);box-shadow:0 8px 24px #0002}
main .card:hover,main .gallery-tile:hover{border-color:#3b9dc4;box-shadow:0 12px 32px #0003}
main :is(input,textarea,select){max-width:100%;min-height:46px;border:1px solid #345f7b;border-radius:10px;background:#081a2a;color:#f1f8ff;font:inherit}
main :is(input,textarea,select):focus-visible{border-color:#49c9f2;outline:3px solid #31b9e833;outline-offset:1px}
main button,main .btn,main input[type=submit]{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:10px 16px;border:1px solid #55c8ec;border-radius:11px;background:linear-gradient(120deg,#087ab3,#18a3d0);color:#fff;font:inherit;font-weight:780;text-decoration:none;cursor:pointer}
main button:hover,main .btn:hover,main input[type=submit]:hover{filter:brightness(1.08);box-shadow:0 8px 22px #00121f55;transform:translateY(-1px)}
main .btn.secondary-btn{background:#102d45;color:#d8f1ff}
main a{color:#79dcf5}
main :is(a,button,input,textarea,select):focus-visible,.site-header :is(a,button,select):focus-visible{outline:3px solid #72e3ff;outline-offset:2px}
.alert{padding:13px 16px;border:1px solid #2978a0;border-radius:12px;background:#103550;color:#effaff}
.contact-section{margin:30px 0 0;padding:clamp(18px,3vw,30px);border:1px solid #27688b;border-radius:18px;background:linear-gradient(140deg,#0d2940,#0a1e32)}
.contact-section h2{margin-top:0}.contact-actions{display:flex;flex-wrap:wrap;gap:9px}
.contact-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 14px;border:1px solid #346d8c;border-radius:11px;background:#12354e;color:#e8f8ff;font-weight:700;overflow-wrap:anywhere}
.referral-footer{display:flex;flex-wrap:wrap;gap:7px 12px;margin-top:12px;padding-top:12px;border-top:1px solid #263f54}
.fjord-footer-legal{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 18px;width:100%}.fjord-footer-legal a{display:inline-flex;align-items:center;min-height:40px;color:#b6e4f4;text-decoration:underline;text-underline-offset:3px}
body.light{background:#f3f8fc;color:#173047}body.light .site-header{background:#f9fcffef;border-color:#d0e0eb}
body.light .site-header .brand{color:#153a54}body.light .site-header .brand-blue{color:#087fae}body.light .site-header .fjord-brand-tagline{color:#42657a}
body.light .site-header nav a{color:#31566d}body.light .site-header nav a:hover,body.light .site-header nav a[aria-current=page]{background:#e2f3fb;border-color:#acd5e6;color:#124261}
body.light .site-header .pref-controls select{background:#fff;color:#173047;border-color:#b5cedc}
body.light>footer{background:#eaf3f8;color:#35566b;border-color:#d2e1eb}body.light main h1{color:#153047}body.light main p{color:#405b70}
body.light main .card,body.light main .gallery-tile,body.light main .tracking-result{background:#fff;border-color:#cedee8;box-shadow:0 7px 22px #22445b12}
body.light main :is(input,textarea,select){background:#fff;color:#173047;border-color:#a8c0d0}
body.light .contact-section{background:#edf7fb;border-color:#c4dce9}body.light .contact-actions a{background:#fff;color:#184b67;border-color:#c0dbe8}
@media(max-width:1120px){.site-header{grid-template-columns:minmax(0,1fr) auto}.site-header nav{display:none!important;grid-column:1/-1;justify-content:flex-start;flex-wrap:wrap;padding:4px 0 8px}.site-header.menu-open nav{display:flex!important}.site-header .pref-controls{grid-column:1/-1;justify-content:flex-end}.site-nav-toggle{display:inline-flex}.site-header .brand{grid-column:1}.site-header .pref-controls{grid-row:2}}
@media(max-width:640px){.site-header{gap:8px;padding:9px 12px}.site-header .brand{grid-template-columns:45px auto;column-gap:8px;font-size:14px}.site-header .brand img{width:44px!important;height:44px!important}.site-header .fjord-brand-tagline{font-size:7px;letter-spacing:.12em}.site-header nav{display:none!important;grid-template-columns:1fr 1fr;gap:6px}.site-header.menu-open nav{display:grid!important}.site-header nav a{min-height:42px;white-space:normal}.site-header .pref-controls{grid-column:1/-1;grid-row:2;justify-content:flex-end}.site-header .pref-controls select{min-width:0;max-width:125px}.site-nav-toggle{min-height:40px;padding:8px 10px}body>main{padding:20px 12px 44px!important}.hero{padding:32px 16px!important}main .card{padding:16px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
</style>"""
BASE="""<!doctype html><html lang="fr-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{{meta_description}}"><meta property="og:title" content="{{title}} | Les Impressions du Fjord"><meta property="og:description" content="{{meta_description}}"><meta property="og:type" content="website"><meta property="og:url" content="{{canonical_url}}"><meta property="og:locale" content="fr_CA"><meta property="og:site_name" content="Les Impressions du Fjord"><meta property="og:image" content="{{og_image}}"><meta property="og:image:alt" content="{{title}} — Les Impressions du Fjord"><meta name="twitter:card" content="summary_large_image"><meta name="robots" content="{{meta_robots}}"><link rel="canonical" href="{{canonical_url}}"><link rel="icon" type="image/jpeg" href="/identite/logo"><title>{{title}} | Les Impressions du Fjord</title><script type="application/ld+json">{{business_schema|safe}}</script>{% if gallery_schema %}<script type="application/ld+json">{{gallery_schema|tojson}}</script>{% endif %}"""+STYLE+GLOBAL_FJORD_THEME+FJORD_SITE_PREMIUM+FJORD_FULL_BRANDING+FJORD_LAYOUT_SIDEBAR+FJORD_FINISHING+FJORD_VISITOR_STYLE+FJORD_DONATION_STYLE+FJORD_PRO_REDESIGN+MARKETING_CSS+"""<style>
@media(max-width:650px){
 header nav{width:100%;display:none;flex-wrap:wrap;gap:8px;align-items:center}
 header nav a{padding:8px 9px;min-height:40px;display:inline-flex;align-items:center}
 main{padding:18px 12px 60px}
 .fj-quote-card{min-width:0}
 .fj-quote-card input,.fj-quote-card select,.fj-quote-card button{max-width:100%}
 .fj-quote-card .fj-live-form,.fj-card{min-width:0;overflow-wrap:anywhere}
}
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
.public-print-list{display:grid;gap:10px;margin-top:16px}.public-print-job{padding:12px;border-radius:10px;background:#0c1c2caa;display:flex;align-items:center;gap:12px;flex-wrap:wrap}.public-print-job .tracking-progress{flex:1 1 100%;margin:0}.public-print-job span{margin-left:auto}.tracking-billboard{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;margin:10px 0 32px;padding:26px;border:1px solid #4e9cc5;border-radius:18px;background:linear-gradient(120deg,#173a54,#0c2133)}.tracking-billboard h2{margin:8px 0;font-size:clamp(23px,3vw,33px)}.tracking-billboard p{color:#d6e6f1}.tracking-panel{max-width:640px;margin:20px auto}.tracking-result{margin-top:25px;padding:22px;border:1px solid #4e9cc5;border-radius:12px}.tracking-progress{height:16px;border-radius:12px;background:#273b50;overflow:hidden}.tracking-progress span{display:block;height:100%;background:#43b9ec}body.light .tracking-billboard{background:#e5f3fc;color:#173a54}body.light .tracking-billboard p{color:#34536c}
/* Finition commune : hiérarchie visuelle, lisibilité et confort mobile */
:root{--fjord-ink:#eaf6ff;--fjord-muted:#b7ccdc;--fjord-panel:#10283b;--fjord-border:#2d668a;--fjord-glow:#27baff}
html{scroll-behavior:smooth;scroll-padding-top:18px}
body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;line-height:1.55}
header{gap:16px}
header .brand{min-height:52px;text-decoration:none;line-height:1.15}
header .brand img{object-fit:cover;border-radius:12px}
header nav a{transition:background .18s,color .18s,border-color .18s,transform .18s}
main{padding-top:clamp(24px,4vw,44px);padding-bottom:clamp(48px,7vw,82px)}
main h1{font-size:clamp(32px,5.5vw,62px);line-height:1.08;letter-spacing:-.04em;text-wrap:balance}
main h2{font-size:clamp(23px,3vw,32px);line-height:1.2;letter-spacing:-.025em;text-wrap:balance}
main h3{line-height:1.25}
main p{max-width:78ch}
.card,.gallery-tile,.tracking-result,.tracking-billboard,.contact-section{border-radius:18px}
.card{padding:clamp(18px,2.3vw,26px)}
button,.btn,input[type=submit]{min-height:44px;font-weight:750;transition:transform .16s,filter .16s,box-shadow .16s}
button:hover,.btn:hover,input[type=submit]:hover{transform:translateY(-1px);filter:brightness(1.06);box-shadow:0 8px 20px #00111f55}
button:active,.btn:active,input[type=submit]:active{transform:translateY(0)}
input,textarea,select{min-height:46px}
textarea{line-height:1.5}
.alert{border:1px solid #3d91b8;background:linear-gradient(120deg,#123a55,#102a40);color:#ecf9ff}
.contact-section{margin-top:32px;padding:clamp(18px,3vw,30px);border:1px solid #2679a7;background:linear-gradient(135deg,#0e2941,#0a2035)}
.contact-section h2{margin-top:0}
.contact-actions{gap:10px}
.contact-actions a{min-height:50px;line-height:1.3;overflow-wrap:anywhere;transition:transform .16s,background .16s}
.contact-actions a:hover{transform:translateY(-1px)}
footer{display:flex;flex-wrap:wrap;align-items:center;gap:8px 20px;padding:28px clamp(16px,5vw,64px);line-height:1.5}
footer>div:first-child{font-weight:650}
.fjord-visitor-counter{margin:0}
.fjord-side-menu a{transition:background .16s,box-shadow .16s,transform .16s}
.fjord-side-menu a:hover{transform:translateX(2px)}
@media(max-width:1100px){
 header{align-items:center}
 header nav{display:none!important}
 .fjord-side-nav{background:linear-gradient(100deg,#071a2b,#0a2942);box-shadow:0 5px 18px #0003}
 .fjord-side-menu{gap:7px}
 .fjord-side-menu a{border:1px solid #245778;background:#0b2439;border-radius:999px}
 .fjord-side-menu a[aria-current="page"]{border:1px solid #4bcfff;border-left:1px solid #4bcfff}
}
@media(max-width:650px){
 header{padding:11px 13px;gap:9px}
 header .brand{font-size:16px;grid-template-columns:48px auto;column-gap:9px}
 header .brand img{width:46px!important;height:46px!important}
 .pref-controls{width:100%;justify-content:flex-end}
 .pref-controls select{min-height:42px}
 .fjord-side-nav{padding:8px 10px}
 .fjord-side-menu a{min-height:40px;padding:7px 12px}
 main{padding:20px 13px 42px}
 main h1{font-size:clamp(30px,9vw,44px)}
 .card{padding:17px}
 .contact-section{margin-top:24px;padding:18px}
 .contact-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr))}
 .contact-actions a{min-width:0;padding:12px 13px}
 footer{padding:22px 15px;gap:10px}
 .referral-footer{width:100%}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}button,.btn,input[type=submit],a{transition:none!important}}
.admin-primary-nav a{font-weight:750}.admin-primary-nav a[aria-current=page]{background:#0c638a!important;border-color:#72ddfa!important;color:#fff!important}body.light .admin-primary-nav a[aria-current=page]{background:#087dab!important;color:#fff!important}
</style><link rel="stylesheet" href="/static/fjord_sitewide.css?v=20261108-gallery3d1">{% if request.path == '/' %}<link rel="stylesheet" href="/static/fjord_inspirations.css?v=20261108-ideas50">{% endif %}</head><body class="{{ 'fjord-admin' if request.path.startswith('/admin') else 'fjord-public' }}{{ ' fjord-preview' if fjord_is_preview else '' }}"><header class="site-header"><a class="brand" href="/" aria-label="Les Impressions du Fjord, accueil"><img src="/identite/logo" alt="" style="width:52px;height:52px;object-fit:cover" onerror="this.style.display='none'"><span class="brand-main">LES IMPRESSIONS</span><span class="fjord-brand-blue brand-blue">DU FJORD</span><small class="fjord-brand-tagline">IMPRESSION 3D SUR MESURE</small></a><button class="site-nav-toggle" type="button" id="fjordNavToggle" aria-controls="fjordPrimaryNav" aria-expanded="false" aria-label="Ouvrir le menu">☰ <span>Menu</span></button>{% if request.path.startswith('/admin') and session.get('admin_token') %}
<nav id="fjordPrimaryNav" class="admin-primary-nav" aria-label="Navigation administrateur"><a href="/admin">🏠 Tableau de bord</a><a href="/admin/soumissions-pro">📄 Soumissions</a><a href="/admin/demandes">📥 Demandes</a><a href="/admin/atelier-imprimer">🖨️ Imprimer</a><a href="/admin/atelier-3d">🧊 Atelier 3D</a><a href="/admin/modeles">📚 Modèles</a></nav>
{% else %}
<nav id="fjordPrimaryNav" aria-label="Navigation principale"><a href="/#realisations">Prêts à imprimer</a><a href="/galerie">Galerie</a><a href="/soumission">Soumission</a><a href="/voir-mon-impression">Suivi client</a><a href="/contact">Contact</a><a href="/atelier-3d">Conception 3D</a>{% if session.get('admin_token') %}<a href="/admin">Administration</a>{% endif %}</nav>
{% endif %}<div class="pref-controls"><select id="fjord-lang" aria-label="Langue / Language"><option value="fr">🇨🇦 Français</option><option value="en">🇨🇦 English</option></select><select id="fjord-theme" aria-label="Thème / Theme"><option value="dark">🌙 Sombre</option><option value="light">☀️ Clair</option></select></div></header><main>{% if fjord_is_preview %}<div class="alert fjord-preview-notice" role="alert"><strong>Mode aperçu Render — site de démonstration.</strong> Les demandes, commandes, paiements et impressions ne sont pas disponibles sur cette version. Pour nous joindre, utilisez le courriel ou le téléphone dans la section Contact.</div>{% endif %}{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="alert">{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}{% if not request.path.startswith('/admin') and request.path!='/contact' and request.path!='/' %}<section id="nous-joindre" class="contact-section"><h2>Contactez-nous</h2><p>Une idée de création 3D? Écrivez-nous par courriel, sur Facebook ou appelez-nous!</p><div class="contact-actions"><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">💬 Nous écrire sur Facebook</a><a href="mailto:lesimpressionsdufjord@gmail.com">✉ lesimpressionsdufjord@gmail.com</a><a href="tel:+15819980831">☎ 581-998-0831</a><a href="https://maps.app.goo.gl/9Qryi3nbK9nBuXts8?g_st=ac" target="_blank" rel="noopener noreferrer">📍 Nous trouver sur Google Maps</a></div><p class="muted small">Pour Messenger, ouvrez notre page Facebook et choisissez « Envoyer un message ».</p></section>{% endif %}</main><footer><div>© 2026 Les Impressions du Fjord · Saguenay, Québec</div>{% if not request.path.startswith('/admin') %}<div class="referral-footer"><a href="/bons-plans/starlink">🛰️ Notre bon plan Internet : parrainage Starlink</a><span>Un partage personnel, indépendant de nos services d'impression 3D.</span></div><a class="fjord-donation-link" href="/soutenir">❤️ Soutenir notre atelier</a>{% endif %}<nav class="fjord-footer-legal" aria-label="Informations légales et assistance"><a href="/assistance">Assistance</a><a href="/politique-confidentialite">Confidentialité</a><a href="/conditions-utilisation">Conditions d’utilisation</a><a href="mailto:lesimpressionsdufjord@gmail.com">Nous écrire</a></nav>{% if not request.path.startswith('/admin') %}<div class="fjord-visitor-counter" aria-label="Nombre de visiteurs uniques">👀 <strong>{{ '{:,}'.format(fjord_visitors).replace(',', ' ') if fjord_visitors is not none else '—' }}</strong> visiteurs uniques · 🟢 <strong>{{ fjord_online_visitors if fjord_online_visitors is not none else '—' }}</strong> en ligne (5 min)</div>{% endif %}</footer><script>
(function(){
 const path=location.pathname.replace(/\\/$/,'')||'/';
 document.querySelectorAll('header nav a').forEach(link=>{
  const href=link.getAttribute('href');
  if(!href||!href.startsWith('/')||href.includes('#'))return;
  const target=href.replace(/\\/$/,'')||'/';
  if(target===path)link.setAttribute('aria-current','page');
 });
 const header=document.querySelector('.site-header');
 const button=document.getElementById('fjordNavToggle');
 const nav=document.getElementById('fjordPrimaryNav');
 if(!header||!button||!nav)return;
 const close=()=>{header.classList.remove('menu-open');button.setAttribute('aria-expanded','false');button.setAttribute('aria-label','Ouvrir le menu')};
 button.addEventListener('click',()=>{const open=!header.classList.contains('menu-open');header.classList.toggle('menu-open',open);button.setAttribute('aria-expanded',String(open));button.setAttribute('aria-label',open?'Fermer le menu':'Ouvrir le menu')});
 nav.addEventListener('click',event=>{if(event.target.closest('a'))close()});
 document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
 document.addEventListener('pointerdown',event=>{if(!header.contains(event.target))close()});
})();
</script><script>
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
"Description de votre message":"Your message","Envoyer la demande":"Send request","Envoyer ma demande de soumission gratuite":"Send my free quote request",
"Nous contacter":"Contact us","Envoyez-nous votre message directement depuis ce formulaire.":"Send your message directly from this form.",
"Décrivez votre projet et joignez votre modèle 3D si vous en avez un.":"Describe your project and attach your 3D model if available.",
"Matériau souhaité":"Preferred material","Fichier STL ou 3MF (facultatif, maximum 8 Mo)":"STL or 3MF file (optional, 16 MB maximum)",
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
"Cette page est introuvable":"This page cannot be found",
"Oups, on ne trouve pas cette page.":"Oops, we couldn't find that page.",
"Le lien a peut-être changé ou la page n’existe plus.":"The link may have changed or this page no longer exists.",
"Fichier trop volumineux":"File too large",
"Votre pièce jointe dépasse la limite.":"Your attachment is over the limit.",
"La demande accepte un modèle STL/3MF de 16 Mo maximum et une photo de 4 Mo. Réduisez le fichier, puis renvoyez votre demande.":"Quote requests accept an STL/3MF model up to 16 MB and a photo up to 4 MB. Reduce the file and resend your request.",
"Réduisez le fichier, puis réessayez. La limite dépend de l’outil utilisé.":"Reduce the file and try again. The file limit depends on the tool.",
"Demande temporairement limitée":"Request temporarily limited",
"Un instant avant de réessayer.":"Please wait before trying again.",
"Plusieurs demandes ont été envoyées en peu de temps. Attendez un moment, puis réessayez ou écrivez-nous.":"Several requests were sent in a short time. Wait a moment, then try again or contact us.",
"Vérifiez votre demande":"Check your request",
"Un renseignement ou fichier doit être corrigé.":"One of the details or files needs to be corrected.",
"Vérifiez les champs et les formats de fichiers, puis renvoyez le formulaire. Si le problème continue, écrivez-nous.":"Check the form fields and file formats, then resubmit. If the problem continues, contact us.",
"La demande n’a pas pu être traitée. Vérifiez les informations, puis réessayez.":"The request could not be processed. Check the information and try again.",
"Une erreur est survenue":"Something went wrong",
"Un petit pépin est survenu.":"A small hiccup occurred.",
"La page n’a pas pu se charger. Réessaie dans un instant; si le problème continue, écris-nous.":"The page could not load. Try again in a moment; if the problem continues, contact us.",
"↻ Réessayer":"↻ Try again",
"✉ Demander une soumission":"✉ Request a quote",
"Nous écrire":"Contact us",
"← Retour à l'accueil":"← Back to home",
"Type de projet":"Project type",
"Dimensions approximatives (facultatif)":"Approximate dimensions (optional)",
"Longueur × largeur × hauteur, idéalement en millimètres.":"Length × width × height, ideally in millimetres.",
"Remise souhaitée":"Preferred delivery",
"Ramassage local au Saguenay (à confirmer)":"Local pickup in Saguenay (to be confirmed)",
"Expédition (prix et disponibilité à confirmer)":"Shipping (price and availability to be confirmed)",
"Délai souhaité":"Preferred timeframe",
"Dès que possible (selon disponibilité)":"As soon as possible (subject to availability)",
"Dans les 2 prochaines semaines":"Within the next 2 weeks",
"À une date précise (indiquer en description)":"On a specific date (add details in the description)",
"La disponibilité et les frais éventuels seront confirmés dans la soumission.":"Availability and any applicable fees will be confirmed in the quote.",
"Quantité souhaitée":"Quantity",
"Indiquez le nombre de pièces désirées.":"Enter the number of parts requested.",
"Couleur souhaitée":"Preferred colour",
"Autre / à discuter":"Other / to discuss",
"📷 Photo ou croquis de référence (facultatif)":"📷 Reference photo or sketch (optional)",
"Vous n'avez pas de modèle 3D? Envoyez simplement une photo, une capture d'écran ou un croquis (JPG, PNG ou WebP, maximum 4 Mo).":"Don't have a 3D model? Send a photo, screenshot or sketch (JPG, PNG or WebP, up to 4 MB).",
"📦 Fichier STL ou 3MF (facultatif, maximum 16 Mo)":"📦 STL or 3MF file (optional, up to 16 MB)",
"Vous pouvez joindre une photo, un fichier 3D, les deux ou seulement votre description.":"You can attach a photo, a 3D file, both, or just your description.",
"Vos coordonnées servent uniquement à répondre à votre demande.":"Your contact information will only be used to respond to your request."
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
</script><script src="/static/fjord_sitewide.js?v=20261109-sales-bundle6" defer></script>{% if request.path == '/' %}<script src="/static/fjord_inspirations.js?v=20261108-ideas51" defer></script>{% endif %}</body></html>"""
def page(title,body,**kwargs):
 from flask import render_template_string
 # SEO parameters are reserved and never leaked into the individual body template.
 custom_description=kwargs.pop("seo_description",None)
 custom_image=kwargs.pop("seo_image",None)
 gallery_schema=kwargs.pop("seo_gallery_schema",None)
 description={
  "Accueil":"Impression 3D sur mesure au Saguenay : pièces personnalisées, prototypes, cadeaux et créations uniques. Demandez une soumission gratuite aux Impressions du Fjord.",
  "Galerie":"Photos de pièces imprimées et aperçus 3D au Saguenay. Choisissez une réalisation avec fichier STL ou 3MF associé et demandez une soumission.",
  "Soumission":"Demandez une soumission gratuite pour votre impression 3D au Saguenay. Décrivez votre idée ou transmettez un fichier STL ou 3MF.",
  "Contact":"Contactez Les Impressions du Fjord au Saguenay pour vos projets d'impression 3D sur mesure.",
  "Parrainage Starlink":"Découvrez un lien de parrainage Starlink pour les nouveaux abonnés admissibles au Canada. Parrainage personnel et transparent."
 }.get(title,"Les Impressions du Fjord — impression 3D sur mesure au Saguenay.")
 meta=seo_metadata()
 # Only same-site image paths can be used in public social metadata.
 image=meta["public_origin"]+custom_image if isinstance(custom_image,str) and custom_image.startswith("/") and not custom_image.startswith("//") else meta["public_origin"]+"/identite/logo"
 return render_template_string(
  BASE,title=title,meta_description=(str(custom_description or description)[:230]),
  og_image=image,gallery_schema=gallery_schema,
  body=render_template_string(body,**kwargs),business_schema=BUSINESS_SCHEMA,
  fjord_is_preview=os.environ.get("FJORD_PREVIEW_MODE")=="1",**meta)

def _fjord_error_page(code):
 if code==404:
  title="Cette page est introuvable"
  heading="Oups, on ne trouve pas cette page."
  message="Le lien a peut-être changé ou la page n’existe plus."
 elif code==413:
  title="Fichier trop volumineux"
  heading="Votre pièce jointe dépasse la limite."
  if request.path=="/soumission":
   message="La demande accepte un modèle STL/3MF de 16 Mo maximum et une photo de 4 Mo. Réduisez le fichier, puis renvoyez votre demande."
  else:
   message="Réduisez le fichier, puis réessayez. La limite dépend de l’outil utilisé."
 elif code==429:
  title="Demande temporairement limitée"
  heading="Un instant avant de réessayer."
  message="Plusieurs demandes ont été envoyées en peu de temps. Attendez un moment, puis réessayez ou écrivez-nous."
 elif code==400:
  title="Vérifiez votre demande"
  heading="Un renseignement ou fichier doit être corrigé."
  if request.path=="/soumission":
   message="Vérifiez les champs et les formats de fichiers, puis renvoyez le formulaire. Si le problème continue, écrivez-nous."
  else:
   message="La demande n’a pas pu être traitée. Vérifiez les informations, puis réessayez."
 else:
  title="Une erreur est survenue"
  heading="Un petit pépin est survenu."
  message="La page n’a pas pu se charger. Réessaie dans un instant; si le problème continue, écris-nous."
 body="""<style>
.fjord-error{max-width:760px;margin:clamp(30px,8vh,90px) auto;padding:clamp(22px,5vw,42px);border:1px solid #2e84ad;border-radius:22px;background:linear-gradient(145deg,#102f49,#081b2d);box-shadow:0 18px 55px #00101d88;color:#eef8ff;text-align:center}
.fjord-error-mark{display:grid;place-items:center;width:66px;height:66px;margin:0 auto 18px;border:1px solid #55c8ed;border-radius:20px;background:#0a4564;font-size:32px}
.fjord-error h1{margin:0 0 12px;color:#b4edff;font-size:clamp(25px,5vw,38px);line-height:1.15}
.fjord-error p{max-width:560px;margin:0 auto 24px;color:#c8dce9;font-size:16px;line-height:1.65}
.fjord-error-code{display:block;margin:0 0 22px;color:#8fb8ce;font-size:12px;letter-spacing:.08em}
.fjord-error-actions{display:flex;justify-content:center;gap:12px;flex-wrap:wrap}
.fjord-error-actions a,.fjord-error-actions button{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 18px;border:1px solid #53c7eb;border-radius:11px;background:#0875a5;color:#fff;font:inherit;font-weight:750;text-decoration:none;cursor:pointer}
.fjord-error-actions .fjord-error-home{background:#132d43;border-color:#527c96}
@media(max-width:560px){.fjord-error{margin:20px 10px;padding:24px 18px}.fjord-error-actions{display:grid;grid-template-columns:1fr}.fjord-error-actions a,.fjord-error-actions button{width:100%;box-sizing:border-box}}
</style>
<main class="fjord-error" role="alert">
 <div class="fjord-error-mark" aria-hidden="true">🏔️</div>
 <span class="fjord-error-code">LES IMPRESSIONS DU FJORD · CODE {{error_code}}</span>
 <h1>{{heading}}</h1>
 <p>{{message}}</p>
 <div class="fjord-error-actions">
  <button type="button" onclick="window.location.reload()">↻ Réessayer</button>
  <a class="fjord-error-home" href="/">⌂ Retour à l’accueil</a>
  <a href="/soumission">✉ Demander une soumission</a>
  <a class="fjord-error-home" href="mailto:lesimpressionsdufjord@gmail.com">Nous écrire</a>
 </div>
</main>"""
 return page(title,body,error_code=code,heading=heading,message=message),code

@app.errorhandler(400)
def fjord_bad_request(_error):
 return _fjord_error_page(400)

@app.errorhandler(404)
def fjord_not_found(_error):
 return _fjord_error_page(404)

@app.errorhandler(413)
def fjord_file_too_large(_error):
 return _fjord_error_page(413)

@app.errorhandler(429)
def fjord_rate_limited(_error):
 return _fjord_error_page(429)

@app.errorhandler(500)
def fjord_server_error(_error):
 return _fjord_error_page(500)

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
  if not token:return redirect(url_for("login",next=request.path))
  with db() as c:r=c.execute("SELECT 1 FROM sessions WHERE tokenhash=%s AND expires>NOW()",(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
  if not r:return redirect(url_for("login",next=request.path))
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
  return Response(raw,mimetype="image/jpeg",headers={"Cache-Control":"public, max-age=86400","X-Content-Type-Options":"nosniff"})
 except (OSError,ValueError):
  abort(404)

@app.route("/voir-mon-impression",methods=["GET","POST"])
def voir_mon_impression():
 # Soumissions PRO et leur numero public FJ, jamais l'ancienne table requests.
 result=None
 if request.method=="POST":
  verify()
  submitted=request.form.get("numero","").strip().upper()
  prenom=request.form.get("prenom","").strip().casefold()
  number=submitted if submitted.startswith("FJ-") else "FJ-"+submitted
  if re.fullmatch(r"FJ-[0-9]{1,8}",number) and 0<len(prenom)<=100:
   remote=(request.headers.get("X-Forwarded-For","").split(",")[0].strip() or request.remote_addr or "unknown")[:128]
   fingerprint=hashlib.sha256((str(app.secret_key)+remote).encode()).hexdigest()
   with db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS live_lookup_attempts (fingerprint TEXT PRIMARY KEY, count INTEGER NOT NULL, window_start TIMESTAMPTZ NOT NULL DEFAULT NOW())")
    c.execute("""INSERT INTO live_lookup_attempts(fingerprint,count,window_start) VALUES(%s,1,NOW())
      ON CONFLICT(fingerprint) DO UPDATE SET
      count=CASE WHEN live_lookup_attempts.window_start < NOW()-INTERVAL '15 minutes' THEN 1 ELSE live_lookup_attempts.count+1 END,
      window_start=CASE WHEN live_lookup_attempts.window_start < NOW()-INTERVAL '15 minutes' THEN NOW() ELSE live_lookup_attempts.window_start END""",(fingerprint,))
    attempts=c.execute("SELECT count FROM live_lookup_attempts WHERE fingerprint=%s",(fingerprint,)).fetchone()["count"]
    row=None
    if attempts<=5:
     row=c.execute("""SELECT id,public_number,customer,production_status,production_progress,live_token,
       live_enabled,live_expires FROM private_quotes
       WHERE public_number=%s OR (public_number IS NULL AND id=%s)
       LIMIT 1""",(number,int(number[3:]))).fetchone()
   if row and row["customer"].strip().split()[0].casefold()==prenom:
    result=row
  if result is None:flash("Impossible de verifier cette soumission. Verifiez votre numero FJ et votre prenom.")
 return page("Voir mon impression",'''<section class="tracking-panel"><div class="eyebrow">Les Impressions du Fjord</div><h1>🎥 Voir mon impression</h1><p>Consultez votre soumission et accédez à votre impression lorsque le visionnement est autorisé.</p><form method="post">{{csrf|safe}}<label>Numéro de soumission<input name="numero" placeholder="FJ-00011" required maxlength="18" autocomplete="off"></label><label>Prénom du client<input name="prenom" placeholder="Votre prénom" required maxlength="100" autocomplete="given-name"></label><button class="btn">🎥 Voir mon impression</button></form>{% if result %}<div class="tracking-result"><h2>Soumission {{result.public_number or ('FJ-%05d'|format(result.id))}}</h2><div id="fjord-client-liveprogress" data-number="{{result.public_number or ('FJ-%05d'|format(result.id))}}"><p>État de fabrication : <strong id="fjord-client-state">{{result.production_status}}</strong></p><p>Progression : <strong id="fjord-client-percent">{{result.production_progress or 0}} %</strong></p></div>{% if result.live_enabled and result.live_token and result.live_expires and result.live_expires > now %}<p>Votre lien privé est actif.</p><a class="btn" href="{{url_for('fjord_live_view',token=result.live_token)}}">🎥 Ouvrir mon impression en direct</a>{% else %}<p>La caméra n'est pas encore disponible, ou le lien de visionnement a expiré.</p>{% endif %}</div>{% endif %}<p><a href="/">← Retour à l'accueil</a></p></section>
<script>
(function(){
 const box=document.getElementById('fjord-client-liveprogress');
 if(!box)return;
 const number=box.dataset.number;
 async function reload(){
  if(document.hidden)return;
  try{
   const response=await fetch('/api/production-publique',{cache:'no-store'});
   if(!response.ok)return;
   const data=await response.json();
   const all=[...(data.groups.print||[]),...(data.groups.wait||[]),...(data.groups.done||[])];
   const job=all.find(item=>item.number===number);
   if(!job)return;
   document.getElementById('fjord-client-state').textContent=job.status;
   const percent=document.getElementById('fjord-client-percent');
   percent.textContent=Number.isInteger(job.progress)?job.progress+' %':'Non disponible';
  }catch(error){}
 }
 reload();setInterval(reload,30000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)reload()});
})();
</script>''',result=result,csrf=csrfinput(),now=datetime.datetime.now(datetime.timezone.utc))

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
_octo_cache={"at":0,"data":None,"reason":"En attente de connexion"}
def _octo_live_status():
 import json as j
 import math
 import urllib.request as u
 import urllib.error as ue
 from urllib.parse import urlparse
 now=time.monotonic()
 if now-_octo_cache["at"]<20:return _octo_cache["data"]
 _octo_cache.update({"at":now,"data":None,"reason":"Connexion indisponible"})
 base=os.environ.get("OCTOEVERYWHERE_CONNECTION_URL","").strip().rstrip("/")
 if not base:
  _octo_cache["reason"]="Adresse de connexion OctoEverywhere absente dans Railway."
  return None
 try:
  p=urlparse(base)
  valid=(p.scheme=="https" and p.hostname and p.hostname.endswith(".octoeverywhere.com")
         and not p.username and not p.password and p.port is None
         and p.path in ("","/") and not p.query and not p.fragment)
 except ValueError:
  valid=False
 if not valid:
  _octo_cache["reason"]="Adresse OctoEverywhere invalide : utiliser l'URL de connexion HTTPS sans chemin."
  return None
 try:
  headers={"Accept":"application/json"}
  bearer=os.environ.get("OCTOEVERYWHERE_AUTH_BEARER_TOKEN","").strip()
  basic_user=os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_USER","").strip()
  basic_pass=os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_PASSWORD","")
  if bearer:
   headers["Authorization"]="Bearer "+bearer
  elif basic_user and basic_pass:
   import base64
   headers["Authorization"]="Basic "+base64.b64encode((basic_user+":"+basic_pass).encode()).decode("ascii")
  with u.urlopen(u.Request(base+"/octoeverywhere-command-api/status",headers=headers),timeout=6) as resp:
   data=j.load(resp)
  if data.get("Status")!=200:
   _octo_cache["reason"]="OctoEverywhere refuse la connexion (code {}).".format(str(data.get("Status"))[:4])
   return None
  job=(data.get("Result") or {}).get("JobStatus") or {}
  current=job.get("CurrentPrint") or {}
  progress=current.get("Progress")
  if not isinstance(progress,(int,float)) or not math.isfinite(progress) or not 0<=progress<=100:
   progress=None
  state=str(job.get("State") or "inconnu").lower()
  _octo_cache["data"]={"state":state,"progress":round(progress) if progress is not None else None,
                       "filename":str(current.get("FileName") or "")[:240]}
  _octo_cache["reason"]="Connexion OctoEverywhere active."
  return _octo_cache["data"]
 except ue.HTTPError as exc:
  _octo_cache["reason"]="Connexion refusée (HTTP {}). Vérifier le lien et son autorisation.".format(exc.code)
 except (ue.URLError,TimeoutError,ConnectionError,OSError):
  _octo_cache["reason"]="L'imprimante ou la connexion OctoEverywhere ne répond pas."
 except (ValueError,TypeError,j.JSONDecodeError):
  _octo_cache["reason"]="Réponse OctoEverywhere invalide."
 return None

# Read-only AMS colour palette; never forward printer access credentials to browsers.
_ams_palette_cache={"at":0,"data":{"connected":False,"available":False,"sources":[]}}
def _octo_ams_palette():
 import json as j
 import urllib.request as urlrequest
 from urllib.parse import urlparse
 now=time.monotonic()
 if now-_ams_palette_cache["at"]<45:
  return _ams_palette_cache["data"]
 fallback={"connected":False,"available":False,"sources":[]}
 _ams_palette_cache.update({"at":now,"data":fallback})
 base=os.environ.get("OCTOEVERYWHERE_CONNECTION_URL","").strip().rstrip("/")
 if not base:return fallback
 try:
  parsed=urlparse(base)
  if (parsed.scheme!="https" or not parsed.hostname or
      not parsed.hostname.endswith(".octoeverywhere.com") or
      parsed.username or parsed.password or parsed.port is not None or
      parsed.path not in ("","/") or parsed.query or parsed.fragment):return fallback
  headers={"Accept":"application/json"}
  bearer=os.environ.get("OCTOEVERYWHERE_AUTH_BEARER_TOKEN","").strip()
  basic_user=os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_USER","").strip()
  basic_pass=os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_PASSWORD","")
  if bearer:headers["Authorization"]="Bearer "+bearer
  elif basic_user and basic_pass:
   import base64
   headers["Authorization"]="Basic "+base64.b64encode((basic_user+":"+basic_pass).encode()).decode("ascii")
  req=urlrequest.Request(base+"/octoeverywhere-command-api/status?IncludeMaterialSystem=true",headers=headers)
  with urlrequest.urlopen(req,timeout=6) as resp:
   raw=resp.read(1024*1024+1)
  if len(raw)>1024*1024:return fallback
  payload=j.loads(raw)
  if payload.get("Status")!=200:return fallback
  job=((payload.get("Result") or {}).get("JobStatus") or {})
  material=job.get("MaterialSystem")
  result={"connected":True,"available":isinstance(material,dict),"sources":[]}
  if isinstance(material,dict):
   names={str(unit.get("Id")):str(unit.get("Name") or "")[:60]
          for unit in (material.get("Units") or [])[:8] if isinstance(unit,dict)}
   sources=[]
   for src in (material.get("Sources") or [])[:64]:
    if not isinstance(src,dict) or src.get("IsEmpty") is True:continue
    spool=src.get("Material") or {}
    if not isinstance(spool,dict):continue
    hexcolor=str(spool.get("ColorHex") or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}",hexcolor):continue
    type_name=str(spool.get("Type") or "")[:36]
    filament_name=str(spool.get("Name") or type_name or "Filament")[:65]
    slot=str(src.get("Name") or "Bobine")[:70]
    unit=names.get(str(src.get("UnitId")))
    if unit and not slot.lower().startswith(unit.lower()):slot=unit+" · "+slot
    entry={"slot":slot,"color":"#"+hexcolor.upper(),"material":type_name,
           "name":filament_name}
    remainder=spool.get("RemainingPercent")
    if isinstance(remainder,(int,float)) and 0<=remainder<=100:
     entry["remaining"]=round(remainder)
    sources.append(entry)
   result["sources"]=sources
  _ams_palette_cache["data"]=result
  return result
 except (OSError,TimeoutError,ValueError,TypeError,j.JSONDecodeError):
  return fallback

@app.get("/api/atelier/filaments")
def atelier_ams_filaments():
 # Only selected slot names, material and colours are public; no printer state,
 # identifiers, tokens, control commands, or internal network data.
 response=jsonify(_octo_ams_palette())
 response.headers["Cache-Control"]="no-store"
 return response

def _octo_job_matches(configured,reported):
 def norm(value):
  name=str(value or "").replace(chr(92),"/").split("/")[-1].strip().casefold()
  # Bambu et Octo peuvent rapporter un fichier avec plusieurs suffixes.
  for suffix in (".gcode.3mf",".bgcode.3mf",".gcode",".bgcode",".3mf",".stl"):
   if name.endswith(suffix):
    name=name[:-len(suffix)]
    break
  return name.strip()
 expected,actual=norm(configured),norm(reported)
 if not expected or not actual:return False
 if expected==actual:return True
 # Autorise seulement un préfixe public explicite « FJ-00002_ ».
 match=re.fullmatch(r"fj-\d{5}_(.+)",expected)
 return bool(match and match.group(1)==actual)

def _sync_octo_progress():
 """Relie sans ambiguïté le travail OctoEverywhere à une soumission."""
 live=_octo_live_status()
 result={"connected":live is not None,"reason":_octo_cache["reason"],
         "state":live["state"] if live else None,"filename":live["filename"] if live else "",
         "matched":False,"number":None,"progress":None,"updated":False}
 if not live or live["state"] not in ("printing","warmingup","resuming","paused","complete"):
  return result
 filename=live.get("filename") or ""
 if not filename:
  result["reason"]="OctoEverywhere ne donne pas le nom du travail actif."
  return result
 reported=str(filename).replace(chr(92),"/").split("/")[-1]
 raw=re.sub(r"(?i)\.gcode\.3mf$|\.bgcode\.3mf$|\.(?:3mf|gcode|bgcode|stl)$","",reported)
 number_match=re.match(r"^(fj-[0-9]{1,8})(?:[_\s-]|$)",raw.casefold())
 with db() as c:
  quotes=c.execute("""SELECT id,public_number,printer_job_name,production_status,production_progress
                      FROM private_quotes ORDER BY id DESC LIMIT 300""").fetchall()
  # Une association manuelle est la source prioritaire, y compris pour les
  # noms de fichiers génériques de Bambu Studio.
  candidates=[q for q in quotes if _octo_job_matches(q["printer_job_name"],filename)]
  if not candidates and number_match:
   number=number_match.group(1).upper()
   candidates=[q for q in quotes if (q["public_number"] or "FJ-{:05d}".format(q["id"]))==number]
  if len(candidates)!=1:
   result["reason"]=("Aucune soumission associée au nom du travail de l'imprimante."
                     if not candidates else "Plusieurs soumissions utilisent le même nom de travail.")
   return result
  q=candidates[0]
  number=q["public_number"] or "FJ-{:05d}".format(q["id"])
  progress=100 if live["state"]=="complete" else live.get("progress")
  status="Terminée" if live["state"]=="complete" else "En production"
  existing=int(q["production_progress"] or 0)
  result.update({"matched":True,"id":q["id"],"status":status,"number":number,
                 "progress":max(int(progress),existing) if progress is not None else existing})
  if progress is None:
   result["reason"]="Impression associée à "+number+"; progression en attente."
   return result
  result["reason"]="Progression reçue pour "+number+"."
  if q["production_status"]!="Terminée":
   changed=c.execute("""UPDATE private_quotes SET
                 production_progress=GREATEST(production_progress,%s),
                 production_status=CASE WHEN %s=100 THEN 'Terminée' ELSE 'En production' END
                 WHERE id=%s AND production_status!='Terminée' RETURNING id""",
                 (progress,progress,q["id"])).fetchone()
   result["updated"]=bool(changed)
 return result

# Horodatage persistant de fin de production : ne supprime jamais les commandes.
def _fjord_install_completion_tracking():
 with db() as c:
  for table,column in (("requests","status"),("private_quotes","production_status")):
   c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ")
   c.execute(f"""UPDATE {table} SET completed_at=NOW()
                WHERE {column}='Terminée' AND completed_at IS NULL""")
   c.execute(f"""CREATE OR REPLACE FUNCTION fjord_track_completion_{table}()
    RETURNS trigger LANGUAGE plpgsql AS $tag$
    BEGIN
      IF NEW.{column}='Terminée' AND (OLD.{column} IS DISTINCT FROM 'Terminée') THEN
        NEW.completed_at=NOW();
      ELSIF NEW.{column} IS DISTINCT FROM 'Terminée' THEN
        NEW.completed_at=NULL;
      END IF;
      RETURN NEW;
    END $tag$""")
   c.execute(f"DROP TRIGGER IF EXISTS fjord_completion_{table} ON {table}")
   c.execute(f"""CREATE TRIGGER fjord_completion_{table}
     BEFORE UPDATE OF {column} ON {table}
     FOR EACH ROW EXECUTE FUNCTION fjord_track_completion_{table}()""")

@app.get("/api/production-publique")
def public_production():
 # Uniquement les commandes autorisées; aucun identifiant ou renseignement client.
 with db() as c:
  rows=c.execute("SELECT status,progress FROM requests WHERE (status!='Terminée' OR completed_at > NOW() - INTERVAL '1 hour') AND kind='Soumission' AND public_progress=TRUE AND status IN ('Demande reçue','Soumission envoyée','En impression','Terminée') ORDER BY id DESC LIMIT 100").fetchall()
 # Soumissions PRO : statut uniquement, sans données client ni montant.
 _sync_octo_progress()
 with db() as c:
  quotes=c.execute("""SELECT q.id,q.public_number,q.production_status,q.production_progress,q.printer_job_name,q.payment_status,
      EXISTS(SELECT 1 FROM fjord_quote_acceptances a WHERE a.quote_id=q.id) AS accepted
      FROM private_quotes q WHERE (q.production_status!='Terminée' OR q.completed_at > NOW() - INTERVAL '1 hour') ORDER BY q.id DESC LIMIT 150""").fetchall()
 groups={"print":[],"wait":[],"done":[]}
 for q in quotes:
  status=q["production_status"]
  if status=="Terminée":
   key,label="done","Terminée"
  elif status=="En production":
   key,label="print","En impression"
  elif q["payment_status"]=="Payée":
   key,label="wait","Payée · en attente de production"
  elif q["accepted"]:
   key,label="wait","Acceptée · en attente de production"
  else:
   key,label="wait","Soumission en attente"
  progress=100 if key=="done" else int(q["production_progress"] or 0)
  groups[key].append({"number":q["public_number"] or "FJ-{:05d}".format(q["id"]),"status":label,"progress":progress})
 for r in rows:
  key="print" if r["status"]=="En impression" else ("done" if r["status"]=="Terminée" else "wait")
  if len(groups[key])<100:
   groups[key].append({"progress":r["progress"] if key=="print" else None,"status":r["status"]})
 response=jsonify({"groups":groups})
 response.headers["Cache-Control"]="no-store, max-age=0"
 return response

@app.get("/soutenir")
def fjord_support():
 # Les dons peuvent être faits par Stripe ou par virement Interac.
 link=os.environ.get("STRIPE_DONATION_URL","").strip()
 valid=bool(re.fullmatch(r"https://(?:buy|donate)\.stripe\.com/[A-Za-z0-9_/?=&-]+",link))
 with db() as c:
  setting=c.execute("SELECT value FROM settings WHERE key='fjord_interac_email'").fetchone()
 recipient=(setting["value"].strip() if setting and setting["value"] else "")
 body="""<section class="fjord-support-panel"><div class="eyebrow">Un petit geste, un grand merci</div><h1>❤️ Soutenir Les Impressions du Fjord</h1><p>Vous aimez nos créations et souhaitez encourager notre atelier d'impression 3D? Votre soutien volontaire nous aide à développer de nouveaux projets.</p>
 {% if recipient %}<details class="fjord-donation-interac" style="background:#172334;color:#f5f7fb;border:1px solid #34485f;border-radius:14px;padding:12px 16px;margin:18px 0"><summary style="cursor:pointer;font-weight:800;color:#ffd447"><svg aria-hidden="true" focusable="false" width="38" height="27" viewBox="0 0 38 27" style="vertical-align:middle;margin-right:9px"><rect x="1" y="1" width="36" height="25" rx="4" fill="#26394f" stroke="#ffd447" stroke-width="2"/><rect x="1" y="7" width="36" height="5" fill="#ffd447"/><rect x="6" y="16" width="8" height="6" rx="1" fill="#d6deea"/><path d="M20 18h11M20 21h7" stroke="#d6deea" stroke-width="1.5" stroke-linecap="round"/></svg>Virement Interac — afficher les instructions</summary><p style="color:#edf2f7">Envoyez le montant de votre choix à <strong>{{recipient}}</strong> et inscrivez « Don atelier Fjord » en note.</p><p class="small" style="color:#c5d0dd">La marche à suivre varie selon la banque. <a style="color:#ffd447" href="https://www.interac.ca/fr/comment-utiliser/virement-interac/comment-envoyer-des-fonds-avec-virement-interac/" target="_blank" rel="noopener noreferrer">Instructions officielles ↗</a></p></details>{% endif %}
 {% if valid %}<a class="fjord-donation-link" href="{{link}}" target="_blank" rel="noopener noreferrer">❤️ Faire un don sécurisé avec Stripe ↗</a><p class="small">Paiement traité par Stripe. Les dons sont indépendants des commandes et ne constituent pas des reçus officiels de dons de bienfaisance.</p>{% endif %}
 {% if not valid and not recipient %}<p class="alert">Les dons en ligne seront disponibles prochainement. Merci pour votre soutien! 💙</p>{% endif %}
 <p><a href="/">← Retour à l'accueil</a></p></section>"""
 return page("Soutenir notre atelier",body,valid=valid,link=link,recipient=recipient)

@app.get("/")
def home():
 # Les donnees publiques viennent de la galerie reelle et des commandes autorisees.
 with db() as c:
  public_jobs=c.execute("SELECT progress FROM requests WHERE kind='Soumission' AND status='En impression' AND public_progress=TRUE ORDER BY id DESC LIMIT 4").fetchall()
  featured=c.execute("""SELECT g.id,g.title,g.category,g.is_real_photo,
       (g.photo IS NOT NULL OR p.id IS NOT NULL) AS has_photo,
       CASE WHEN g.photo IS NOT NULL THEN 0 ELSE COALESCE(p.id,0) END AS quote_photo_id,
       CASE WHEN g.photo IS NOT NULL THEN (g.model_data IS NOT NULL)
            ELSE (g.model_data IS NOT NULL OR COALESCE(p.model_data IS NOT NULL,FALSE))
       END AS has_model
       FROM gallery g
       LEFT JOIN LATERAL (
         SELECT id,model_data FROM gallery_photos
         WHERE gallery_id=g.id ORDER BY (model_data IS NOT NULL) DESC,id LIMIT 1
       ) p ON TRUE
       WHERE (g.photo IS NOT NULL OR p.id IS NOT NULL)
         AND ((g.photo IS NOT NULL AND g.model_data IS NOT NULL)
              OR (g.photo IS NULL AND p.id IS NOT NULL
                  AND (g.model_data IS NOT NULL OR p.model_data IS NOT NULL)))
       ORDER BY g.is_real_photo DESC,g.id DESC LIMIT 6""").fetchall()
  inspiration_rows=c.execute("""SELECT source FROM fjord_inspiration_models
       WHERE rights_confirmed=TRUE AND octet_length(model_data)>0""").fetchall()
  public_inspirations=fjord_inspiration_html({row["source"] for row in inspiration_rows})
 return page("Accueil",MARKETING_HOME_START.replace(
  '<section class="fjm-section" id="fonctionnement">',
  public_inspirations + '<section class="fjm-section" id="fonctionnement">', 1)
  + '''<section class="tracking-billboard fjord-board" aria-label="Tableau interactif de production" hidden><div class="fjord-board-inner"><div class="fjord-board-heading"><strong>LES IMPRESSIONS DU FJORD</strong><span class="fjord-board-badge">Production</span></div><h2>Suivi des impressions 3D</h2><p>Aperçu interactif du tableau de production</p><div id="fjordProductionLive" role="tabpanel" aria-live="polite"><p>Chargement du tableau de production…</p></div><div class="fjord-board-footer"><p class="production-updated" id="fjordProductionUpdated">Mise à jour automatique toutes les 30 secondes.</p><div class="fjord-board-actions"><a class="btn fjord-board-see" href="/voir-mon-impression">👁️ Voir mon impression</a><p class="fjord-board-private">Visionnement privé de votre impression 3D.</p></div></div></div></section><style>
.fjord-board[hidden]{display:none!important}.fjord-board{display:block;padding:24px;background:#0b1725;border-color:#3a6076}.fjord-board-inner{width:100%}.fjord-board-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;font-size:18px}.fjord-board-badge{background:#103c27;color:#50d78a;border-radius:30px;padding:5px 12px;font-size:14px}.fjord-board h2{font-size:clamp(24px,3vw,30px);margin:22px 0 6px}.fjord-board-tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:20px 0}.fjord-board-tab{background:transparent;border:0;border-radius:30px;color:#c4d5e0;font:inherit;font-weight:700;padding:12px 5px;cursor:pointer}.fjord-board-tab.active{background:#304151;color:white}.fjord-board-tab:focus-visible{outline:2px solid #64d9ff;outline-offset:2px}.fjord-board .public-print-list{margin:0}.fjord-board .public-print-job{background:#10283b;display:block}.fjord-board .public-print-job strong{display:block}.fjord-board .public-print-job span{display:block;margin:8px 0}.fjord-board .tracking-progress{height:12px}.fjord-board .tracking-progress span{margin:0;background:#24b46a}.fjord-board-see{display:inline-block;margin-top:12px}.fjord-board-private{font-size:13px;margin:8px 0 0}.fjord-board .production-updated{font-size:13px;margin:14px 0 0}@media(max-width:480px){.fjord-board{padding:16px}.fjord-board-tab{font-size:13px;padding:10px 3px}}
.fjord-board{padding:20px 24px}.fjord-board h2{margin:12px 0 3px}.fjord-board-inner>p{margin:6px 0 12px}.fjord-board-footer{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:12px;flex-wrap:wrap}.fjord-board-actions{display:flex;align-items:center;gap:12px;margin-left:auto}.fjord-board .fjord-board-see{margin:0;padding:10px 16px;font-size:14px;white-space:nowrap}.fjord-board .fjord-board-private{margin:0;max-width:185px;font-size:11px;line-height:1.3;color:#a9c3d4}.fjord-board .production-updated{margin:0}.fjord-public-table{display:grid;gap:5px}.fjord-public-row{display:grid;grid-template-columns:minmax(110px,1fr) minmax(150px,1.5fr) minmax(100px,1fr);gap:12px;align-items:center;padding:8px 12px;border:1px solid #37546a;border-radius:8px}.fjord-public-head{border:0;color:#c5d9e8}.fjord-public-progress{display:grid;gap:5px}.fjord-public-progress .tracking-progress{height:6px}@media(max-width:520px){.fjord-public-row{grid-template-columns:minmax(80px,1fr) minmax(110px,1.4fr) minmax(70px,1fr);gap:7px;padding:7px;font-size:12px}}
@media(max-width:600px){.fjord-board-actions{width:100%;justify-content:flex-end}.fjord-board .fjord-board-private{display:none}}
</style><script>
(function(){
 const root=document.getElementById("fjordProductionLive"),updated=document.getElementById("fjordProductionUpdated");
 let groups={print:[],wait:[],done:[]};
 function render(){
  const board=root.closest(".fjord-board");
  root.replaceChildren();
  const all=[...groups.print,...groups.wait,...groups.done];
  if(!all.length){if(board)board.hidden=true;return;}
  if(board)board.hidden=false;
  const table=document.createElement("div");table.className="fjord-public-table";
  const head=document.createElement("div");head.className="fjord-public-row fjord-public-head";
  for(const label of ["Soumission","État","Progression"]){const cell=document.createElement("strong");cell.textContent=label;head.append(cell);}
  table.append(head);
  for(const key of ["print","wait","done"]){
   for(const job of groups[key]){
    const line=document.createElement("div");line.className="fjord-public-row";
    const number=document.createElement("strong");number.textContent=job.number||"Commande";line.append(number);
    const state=document.createElement("span");state.textContent=job.status||({print:"En impression",wait:"En attente",done:"Terminée"}[key]);line.append(state);
    const progress=document.createElement("div");progress.className="fjord-public-progress";
    if(Number.isInteger(job.progress)&&job.progress>=0&&job.progress<=100){
     const pct=document.createElement("span");pct.textContent=job.progress+" %";progress.append(pct);
     const bar=document.createElement("div");bar.className="tracking-progress";
     const fill=document.createElement("span");fill.style.width=job.progress+"%";bar.append(fill);progress.append(bar);
    }else{progress.textContent="—";}
    line.append(progress);table.append(line);
   }
  }
  root.append(table);
 }
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
</script>''' + MARKETING_HOME_END + MARKETING_SCRIPT,public_jobs=public_jobs,featured=featured,seo_image="/gallery/thumb/3")
@app.get("/bons-plans/starlink")
def starlink_referral():
 return page("Parrainage Starlink",'''<section class="referral-page"><div class="eyebrow">Bon plan partagé</div><h1>Parrainage Starlink</h1><p>Vous envisagez de vous abonner à Starlink au Canada? Voici un lien de parrainage personnel à consulter si cela vous intéresse.</p><div class="card referral-card"><h2>Découvrir Starlink</h2><p>Les nouveaux abonnés admissibles peuvent recevoir une récompense selon les conditions de parrainage en vigueur. La personne qui partage ce lien peut également recevoir une récompense.</p><a class="btn referral-cta" href="https://starlink.com/?referral=RC-4635519-65017-67&amp;app_source=share" target="_blank" rel="nofollow sponsored noopener noreferrer">Consulter mon lien de parrainage</a><p class="small muted referral-disclosure">Lien de parrainage personnel. Les Impressions du Fjord ne vendent pas de services Starlink et ne sont pas affiliées à Starlink. Vérifiez la disponibilité, les tarifs et les conditions directement sur le site Starlink.</p></div><p class="small"><a href="/">← Retour à l'accueil</a></p></section>''')

@app.get("/galerie")
def gallery_page():
 with db() as c:
  items=c.execute("""SELECT g.id,g.title,g.category,g.description,g.is_real_photo,g.photo IS NOT NULL AS has_photo,
      (g.model_data IS NOT NULL OR p.model_data IS NOT NULL) AS has_model,
      CASE WHEN g.photo IS NOT NULL AND g.model_data IS NOT NULL THEN 0
           WHEN p.id IS NOT NULL AND p.model_data IS NOT NULL THEN p.id
           WHEN g.photo IS NOT NULL THEN 0 ELSE COALESCE(p.id,0) END AS quote_photo_id
      FROM gallery g
      LEFT JOIN LATERAL (SELECT id,model_data FROM gallery_photos
                         WHERE gallery_id=g.id
                         ORDER BY (model_data IS NOT NULL) DESC,id LIMIT 1) p ON TRUE
      ORDER BY g.is_real_photo DESC,g.id DESC""").fetchall()
 return page("Galerie",MARKETING_GALLERY + MARKETING_SCRIPT,items=items)
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
@app.get("/gallery/thumb/<int:id>")
def fjord_gallery_thumbnail(id):
 """Optimized WebP thumbnail for explicitly public gallery images only."""
 from PIL import Image,ImageOps,UnidentifiedImageError
 with db() as conn:
  item=conn.execute("SELECT photo FROM gallery WHERE id=%s",(id,)).fetchone()
  if not item:
   abort(404)
  photo=item["photo"]
  if not photo:
   first=conn.execute("SELECT photo FROM gallery_photos WHERE gallery_id=%s ORDER BY id LIMIT 1",(id,)).fetchone()
   photo=first["photo"] if first else None
 if not photo:
  abort(404)
 try:
  with Image.open(io.BytesIO(photo)) as source:
   if source.width*source.height>32_000_000:
    abort(413)
   image=ImageOps.exif_transpose(source).convert("RGB")
  image.thumbnail((900,650),Image.Resampling.LANCZOS)
  output=io.BytesIO()
  image.save(output,format="WEBP",quality=79,method=4)
  output.seek(0)
 except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):
  app.logger.warning("Invalid public gallery thumbnail for item %s",id)
  abort(404)
 return send_file(output,mimetype="image/webp",max_age=3600)

def fjord_gallery_model_upload(upload):
 """Limit and validate a private, owner-provided gallery STL/3MF."""
 if not upload or not upload.filename:return None,None
 filename=secure_filename(upload.filename)[:150]
 if not filename or not filename.lower().endswith((".stl",".3mf")):
  abort(400,description="Fichier galerie : seulement STL ou 3MF.")
 data=upload.read(20*1024*1024+1)
 if not data or len(data)>20*1024*1024:abort(413,description="Modèle vide ou de plus de 20 Mo.")
 if filename.lower().endswith(".3mf"):
  from zipfile import is_zipfile
  if not is_zipfile(io.BytesIO(data)):abort(400,description="Le fichier 3MF est endommagé.")
 elif len(data)<84:
  abort(400,description="Fichier STL trop court.")
 return filename,data

def fjord_gallery_library_candidates(conn):
 """Candidate metadata only; never read the 3D bytes until a unique match."""
 return conn.execute("""SELECT id,name,filename FROM private_models
   WHERE (lower(filename) LIKE '%%.stl' OR lower(filename) LIKE '%%.3mf')
     AND octet_length(filedata) <= %s
   ORDER BY id DESC LIMIT 1500""",(20*1024*1024,)).fetchall()

def fjord_gallery_model_for_photo(conn,photo_name,uploads,library):
 """Unique uploaded basename wins; otherwise unique private library basename.

 Returns (filename,bytes,source), or None when ambiguous/not found.
 No semantic/visual guessing, no invented 3D geometry.
 """
 direct=unique_photo_match(photo_name,uploads)
 if direct:
  return direct["filename"],direct["data"],"upload"
 model=unique_photo_match(photo_name,library)
 if not model:return None
 row=conn.execute("SELECT filename,filedata FROM private_models WHERE id=%s",(model["id"],)).fetchone()
 if not row or not row["filedata"]:return None
 return row["filename"],row["filedata"],"bibliothèque"

def fjord_gallery_fill_missing_links(conn,gallery_id,uploads=()):
 """Link only previously unlinked photos when their source filename is known."""
 candidates=fjord_gallery_library_candidates(conn)
 existing=conn.execute("""SELECT id,original_filename FROM gallery_photos
     WHERE gallery_id=%s AND model_data IS NULL AND original_filename IS NOT NULL
     ORDER BY id""",(gallery_id,)).fetchall()
 linked=0
 for photo in existing:
  found=fjord_gallery_model_for_photo(conn,photo["original_filename"],uploads,candidates)
  if not found:continue
  filename,blob,_=found
  conn.execute("""UPDATE gallery_photos SET model_filename=%s,model_data=%s
     WHERE id=%s AND model_data IS NULL""",(filename,blob,photo["id"]))
  linked+=1
 return linked,len(existing)

def fjord_gallery_asset(conn,gallery_id,photo_id=0,with_photo=False):
 """Return only data from a real, matching gallery image. Never trust a file name from a URL."""
 item=conn.execute("""SELECT id,title,description,photo,mime,model_filename,model_data
                       FROM gallery WHERE id=%s""",(gallery_id,)).fetchone()
 if not item:return None
 image=item["photo"]
 mime=item["mime"]
 model_name=item["model_filename"]
 model_data=item["model_data"]
 if photo_id:
  image_row=conn.execute("""SELECT photo,mime,model_filename,model_data
                             FROM gallery_photos WHERE id=%s AND gallery_id=%s""",
                         (photo_id,gallery_id)).fetchone()
  if not image_row:return None
  image=image_row["photo"]
  mime=image_row["mime"]
  if image_row["model_data"]:
   model_name=image_row["model_filename"]
   model_data=image_row["model_data"]
 elif image is None:
  # Older galleries may only use the gallery_photos table. Photo=0 is not a
  # real photograph for those galleries: require the exact photo id.
  return None
 return dict(id=item["id"],title=item["title"],description=item["description"],
             photo=image if with_photo else None,mime=mime,
             model_filename=model_name,model_data=model_data)

def fjord_gallery_quote_image(photo,mime):
 """Store a clean, scaled reference copy; never reveal gallery original EXIF."""
 from PIL import Image,ImageOps,UnidentifiedImageError
 try:
  with Image.open(io.BytesIO(photo)) as raw:
   if raw.format not in ("JPEG","PNG","WEBP") or raw.width*raw.height>25_000_000:
    abort(400,description="Image de galerie non valide.")
   raw.load()
   image=ImageOps.exif_transpose(raw).convert("RGB")
   image.thumbnail((1600,1600),Image.Resampling.LANCZOS)
   output=io.BytesIO()
   image.save(output,format="JPEG",quality=80,optimize=True)
   result=output.getvalue()
   if not result or len(result)>4*1024*1024:
    abort(413,description="Photo de galerie trop volumineuse.")
   return result
 except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):
  abort(400,description="Photo de galerie illisible.")

def fjord_inspiration_by_index(index):
 """Resolve a fixed source in the curated, license-attributed inspiration manifest."""
 if not isinstance(index,int) or index<0 or index>=len(FJORD_INSPIRATIONS):return None
 return FJORD_INSPIRATIONS[index]

def fjord_inspiration_model(conn,idea):
 if not idea:return None
 return conn.execute("""SELECT model_filename,model_data,rights_confirmed
                        FROM fjord_inspiration_models WHERE source=%s""",
                     (idea["source"],)).fetchone()

def fjord_inspiration_image_copy(idea):
 """Best-effort safe reference copy, limited to pre-verified Wikimedia media hosts."""
 import urllib.request as req
 from urllib.parse import urlsplit
 from werkzeug.exceptions import HTTPException
 url=idea["image"]
 parsed=urlsplit(url)
 if parsed.scheme!="https" or parsed.hostname not in ("upload.wikimedia.org","thumb.wikimedia.org") or parsed.username or parsed.password:
  return None
 try:
  request_obj=req.Request(url,headers={"User-Agent":"Fjord-Quote-Reference/1.0","Accept":"image/jpeg,image/png,image/webp"})
  with req.urlopen(request_obj,timeout=4) as resp:
   dest=urlsplit(resp.geturl())
   if dest.scheme!="https" or dest.hostname not in ("upload.wikimedia.org","thumb.wikimedia.org"):
    return None
   photo=resp.read(4*1024*1024+1)
  if not photo or len(photo)>4*1024*1024:return None
  return fjord_gallery_quote_image(photo,"image/jpeg")
 except (OSError,ValueError,HTTPException):
  return None

@app.get("/galerie/<int:id>")
def gallery_item(id):
 with db() as c:
  item=c.execute("""SELECT id,title,category,description,photo IS NOT NULL AS has_photo,
                            model_data IS NOT NULL AS has_model
                     FROM gallery WHERE id=%s""",(id,)).fetchone()
  if not item:abort(404)
  photos=c.execute("""SELECT id,model_data IS NOT NULL AS has_model
                      FROM gallery_photos WHERE gallery_id=%s ORDER BY id""",
                   (id,)).fetchall()
 assets=([{"photo_id":0,"url":"/photo/"+str(id),"has_model":item["has_model"]}]
         if item["has_photo"] else [])
 assets.extend({"photo_id":int(p["id"]),"url":"/gallery/image/"+str(p["id"]),
                "has_model":p["has_model"] or item["has_model"]} for p in photos)
 urls=[asset["url"] for asset in assets]
 default_photo=assets[0]["photo_id"] if assets else 0
 atelier_photo=next((asset["photo_id"] for asset in assets if asset["has_model"]),None)
 item=dict(item)
 item["title"]=item["title"][:1].upper()+item["title"][1:]
 description=(item["description"] or "").strip()
 summary=(item["title"]+" — "+(description or "Réalisation d'impression 3D sur mesure")+" | Les Impressions du Fjord, Saguenay.")[:195]
 origin=seo_metadata()["public_origin"]
 social_image="/gallery/thumb/"+str(id) if urls else "/identite/logo"
 gallery_schema={"@context":"https://schema.org","@type":"CreativeWork",
  "name":item["title"],"description":description[:1200] or "Création 3D sur mesure",
  "genre":item["category"] or "Impression 3D",
  "creator":{"@type":"Organization","name":"Les Impressions du Fjord"},
  "url":origin+"/galerie/"+str(id),
  "image":[origin+u for u in urls[:15]] if urls else [origin+"/identite/logo"]}
 return page(item["title"],'''<div class="gallery-detail"><a href="/galerie">← Galerie</a><h1>{{item.title}}</h1>
 <div class="eyebrow">{{item.category}}</div><p>{{item.description}}</p>
 <div class="fjord-gallery-detail-cta">
 <a class="btn" href="/soumission?galerie={{item.id}}&photo={{default_photo}}">Demander une soumission pour cette réalisation</a>
 {% if atelier_photo is not none %}<a class="btn secondary-btn" href="/atelier-3d?galerie={{item.id}}&amp;photo={{atelier_photo}}">Ouvrir l’Atelier 3D</a>{% endif %}
 <button type="button" class="fjord-share-project" data-fjord-share-title="{{item.title}}" aria-describedby="fjordShareResult">Partager cette réalisation</button>
 <span class="fjord-share-result" id="fjordShareResult" role="status" aria-live="polite"></span></div>
 <p class="muted">Choisissez une photo pour demander précisément la pièce montrée. Un modèle STL/3MF est joint à la demande lorsqu'il a été associé par l'atelier.</p>
 <div class="gallery-grid fjord-gallery-linked">{% for asset in assets %}
 <div class="fjord-gallery-linked-item">
 <a href="{{asset.url}}" class="gallery-photo-link" data-photo-index="{{loop.index0}}" aria-label="Agrandir la photo {{loop.index}}">
 <img loading="lazy" src="{{asset.url}}" alt="{{item.title}} — photo {{loop.index}}"></a>
 <p class="fjord-gallery-linked-state">{{'✓ Fichier 3D associé' if asset.has_model else 'Photo de référence'}}</p>
 <a class="fjord-gallery-linked-quote" href="/soumission?galerie={{item.id}}&photo={{asset.photo_id}}">Demander cette pièce</a>
 </div>{% endfor %}</div>
 <dialog id="viewer" class="zoom" aria-label="Photo agrandie">
 <div class="row"><button type="button" id="previousPhoto" aria-label="Photo précédente">❮</button>
 <span id="photoCounter"></span><button type="button" id="nextPhoto" aria-label="Photo suivante">❯</button>
 <button type="button" id="closeViewer">Fermer ✕</button></div>
 <img id="largePhoto" alt="{{item.title}}">
 <p><a class="btn" id="quoteThisGalleryPhoto" href="/soumission?galerie={{item.id}}&photo={{default_photo}}">Demander une soumission pour cette photo</a></p>
 </dialog>
 <script>(function(){
 const links=Array.from(document.querySelectorAll(".gallery-photo-link"));
 const viewer=document.getElementById("viewer"),large=document.getElementById("largePhoto");
 const counter=document.getElementById("photoCounter"),quote=document.getElementById("quoteThisGalleryPhoto");
 if(!links.length||!viewer)return;
 let position=0;
 function update(){
  large.src=links[position].href;
  counter.textContent=(position+1)+" / "+links.length;
  quote.href=links[position].closest(".fjord-gallery-linked-item").querySelector(".fjord-gallery-linked-quote").href;
 }
 function change(delta){position=(position+delta+links.length)%links.length;update()}
 links.forEach((link,i)=>link.addEventListener("click",function(event){
  if(typeof viewer.showModal!=="function")return;
  event.preventDefault();position=i;update();viewer.showModal()
 }));
 document.getElementById("previousPhoto").addEventListener("click",()=>change(-1));
 document.getElementById("nextPhoto").addEventListener("click",()=>change(1));
 document.getElementById("closeViewer").addEventListener("click",()=>viewer.close());
 viewer.addEventListener("click",e=>{if(e.target===viewer)viewer.close()});
 document.addEventListener("keydown",e=>{
  if(!viewer.open)return;
  if(e.key==="ArrowRight")change(1);
  if(e.key==="ArrowLeft")change(-1)
 });
 })();</script></div>''',item=item,assets=assets,urls=urls,
 default_photo=default_photo,atelier_photo=atelier_photo,seo_description=summary,seo_image=social_image,seo_gallery_schema=gallery_schema)


FORM='''<div class="eyebrow">Parlons de votre projet</div><h1>{{heading}}</h1><p>{{intro}}</p>{% if quote %}{{marketing_help|safe}}{% if gallery_selected %}
<section class="fjord-quote-gallery-ref" aria-label="Photo choisie dans la galerie" data-gallery-title="{{gallery_selected.title}}">
 <img src="{{gallery_photo_url}}" loading="eager" alt="Photo de la réalisation {{gallery_selected.title}}">
 <div><strong><span data-fjm-en="Selected project:">Votre réalisation :</span> {{gallery_selected.title}}</strong>
 {% if gallery_selected.model_filename %}<p data-fjm-en="The photo and its associated 3D model are already included in your quote request. No need to upload the same file again. Add another STL/3MF only if you want us to review a different version.">La photo et son modèle 3D associé sont déjà joints à votre demande. Pas besoin de téléverser le même fichier. Ajoutez un autre STL/3MF seulement si vous voulez faire évaluer une version différente.</p>{% else %}<p data-fjm-en="This photo will be included with your quote request. No 3D file is linked yet; add your STL/3MF below if you have one.">Cette photo sera jointe à votre demande. Aucun fichier 3D n'est encore associé; ajoutez votre STL/3MF ci-dessous si vous en avez un.</p>{% endif %}
 <p class="small">Vous pouvez également ajouter votre propre photo ou un autre modèle STL/3MF ci-dessous.</p><p class="small"><a class="fjord-other-ready-models" href="/galerie?prets=1" data-fjm-en="Browse other ready-to-print models">Choisir un autre modèle prêt à imprimer</a></p>
 </div>
 <input type="hidden" name="gallery_id" value="{{gallery_selected.id}}" form="fjordQuoteForm">
 <input type="hidden" name="gallery_photo_id" value="{{gallery_photo_id}}" form="fjordQuoteForm">
</section>{% endif %}
{% if inspiration_selected %}
<section class="fjord-quote-gallery-ref" aria-label="Inspiration du diaporama sélectionnée">
<img src="{{inspiration_selected.image}}" loading="eager" alt="Inspiration : {{inspiration_selected.title}}" referrerpolicy="no-referrer">
<div><strong>Inspiration #{{inspiration_index+1}} : {{inspiration_selected.title}}</strong>
<p>Cette photo sera identifiée dans la demande avec son lien et ses crédits. Une copie est jointe lorsque la source est accessible.{% if inspiration_has_model %} Un STL/3MF autorisé est également associé et sera joint automatiquement.{% else %} Aucun STL/3MF n'est disponible pour imprimer directement cet exemple.{% endif %}</p>
<p class="small">Photo : <a target="_blank" rel="noopener noreferrer" href="{{inspiration_selected.source}}">{{inspiration_selected.author}}</a> · {{inspiration_selected.license}}. Les droits de reproduction du modèle sont à vérifier séparément.</p></div>
<input type="hidden" name="inspiration_id" value="{{inspiration_index}}" form="fjordQuoteForm">
</section>{% endif %}{% else %}<div class="fjord-client-contact" aria-label="Nous joindre"><a href="mailto:lesimpressionsdufjord@gmail.com">✉ Courriel<small>lesimpressionsdufjord@gmail.com</small></a><a href="tel:+15819980831">☎ Téléphone<small>581-998-0831</small></a><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">💬 Facebook<small>Nous écrire sur notre page</small></a></div>{% endif %}<form id="fjordQuoteForm" class="fjm-quote-form" method="post" enctype="multipart/form-data">{{csrf|safe}}<label>Votre nom<input name="name" maxlength="120" required></label><label>Courriel<input type="email" name="email" maxlength="200" required></label><label>Téléphone (facultatif)<input name="phone" maxlength="40"></label>{% if quote %}<section class="fjord-brief" aria-labelledby="fjordBriefTitle"><h2 id="fjordBriefTitle">Parlez-nous de votre création</h2><p>Quelques détails suffisent pour préparer une soumission plus précise. Si vous hésitez, choisissez « À déterminer ».</p>
<div class="fjord-brief-grid">
<label>Type de projet<select name="project_type">{% for p in project_types %}<option value="{{p}}">{{p}}</option>{% endfor %}</select></label>
<label>Dimensions approximatives (facultatif)<input name="dimensions" maxlength="120" placeholder="Ex. 120 × 80 × 30 mm" autocomplete="off"><small class="fjord-field-help">Longueur × largeur × hauteur, idéalement en millimètres.</small></label>
<label>Remise souhaitée<select name="remise">{% for option in remise_options %}<option value="{{option}}">{{option}}</option>{% endfor %}</select></label>
<label>Délai souhaité<select name="delai">{% for option in delai_options %}<option value="{{option}}">{{option}}</option>{% endfor %}</select><small class="fjord-field-help">La disponibilité et les frais éventuels seront confirmés dans la soumission.</small></label>
</div></section><label>Matériau souhaité<select name="material">{% for m in materials %}<option value="{{m}}">{{m}}</option>{% endfor %}</select></label><label>Quantité souhaitée<input type="number" name="quantity" min="1" max="1000" step="1" inputmode="numeric" value="1" required><small class="fjord-field-help" data-fjm-en="Enter the total number of parts, including for a small batch.">Indiquez le nombre total de pièces, y compris pour une petite série.</small></label><label>Couleur souhaitée<select name="color">{% for col in colors %}<option value="{{col}}">{{col}}</option>{% endfor %}</select></label>{% endif %}<label>Description de votre {{'projet' if quote else 'message'}}<textarea name="description" maxlength="5000" placeholder="{{'Décrivez votre idée, ses dimensions et la quantité souhaitée…' if quote else 'Écrivez votre message ici…'}}" required>{{prefill}}</textarea></label>{% if quote %}<div class="fjm-files">
<label>📷 Photo ou croquis de référence (facultatif)<input type="file" name="reference_photo" accept="image/jpeg,image/png,image/webp" aria-describedby="fjordReferenceHelp"><small id="fjordReferenceHelp" class="fjord-field-help">Vous n'avez pas de modèle 3D? Envoyez simplement une photo, une capture d'écran ou un croquis (JPG, PNG ou WebP, maximum 4 Mo).</small></label>
<div id="fjordReferencePreview" class="fjord-reference-preview" hidden><img alt="Aperçu de votre photo de référence" id="fjordReferenceImage"><span id="fjordReferenceFilename"></span><button type="button" id="fjordReferenceRemove">Retirer la photo</button></div>
<label>📦 Fichier STL ou 3MF (facultatif, maximum 16 Mo)<input type="file" name="model" accept=".stl,.3mf"></label><small id="fjordStudioFileStatus" class="fjord-file-state" role="status" aria-live="polite"></small>
<p class="fjord-field-help">Vous pouvez joindre une photo, un fichier 3D, les deux ou seulement votre description.</p></div>{% endif %}<button type="submit" class="fjm-form-submit" {% if preview %}disabled aria-disabled="true" title="Envoi désactivé sur cette préproduction"{% endif %}>{{'Envoi indisponible en mode aperçu' if preview else ('Envoyer ma demande de soumission gratuite' if quote else 'Envoyer ma demande')}}</button><p class="fjm-quote-note">Vos coordonnées servent uniquement à répondre à votre demande. <a href="/politique-confidentialite">Confidentialité</a>.</p>{% if quote %}<script>
(function(){
 const params=new URLSearchParams(location.search);
 if(params.get("atelier")!=="1"||!window.opener)return;
 const origin=location.origin,input=document.querySelector('#fjordQuoteForm input[name="model"]');
 const state=document.getElementById("fjordStudioFileStatus");
 if(!input)return;
 window.addEventListener("message",event=>{
  if(event.origin!==origin||event.source!==window.opener||event.data?.type!=="fjord-atelier-stl"||!(event.data.blob instanceof Blob))return;
  const blob=event.data.blob,name=String(event.data.filename||"Creation-du-Fjord.stl");
  if(!blob.size||blob.size>16*1024*1024){if(state){state.dataset.status="error";state.textContent="Le modèle dépasse la limite de 16 Mo."}return}
  try{
   const transfer=new DataTransfer();
   transfer.items.add(new File([blob],name,{type:"model/stl"}));
   input.files=transfer.files;
   input.dispatchEvent(new Event("change",{bubbles:true}));
   if(state){state.dataset.status="ready";state.textContent="✓ Le modèle créé dans l’Atelier est joint à cette demande."}
   window.opener.postMessage({type:"fjord-atelier-attached"},origin);
  }catch(error){if(state){state.dataset.status="error";state.textContent="Ajoutez le fichier STL téléchargé manuellement."}}
 });
 window.opener.postMessage({type:"fjord-quote-ready"},origin);
})();
</script>{% endif %}</form>'''
def fjord_reference_image(upload):
 """Validate, orient, reduce and scrub metadata from a customer reference image."""
 from PIL import Image,ImageOps,UnidentifiedImageError
 from flask import abort
 if not upload or not upload.filename:
  return None,None,None
 name=secure_filename(upload.filename)[:140]
 if not name or not name.lower().endswith((".jpg",".jpeg",".png",".webp")):
  abort(400,description="Format de photo non accepté.")
 raw=upload.read(4*1024*1024+1)
 if len(raw)>4*1024*1024:abort(413,description="La photo dépasse 4 Mo.")
 if len(raw)<20:abort(400,description="Photo invalide.")
 try:
  with Image.open(io.BytesIO(raw)) as source:
   if source.format not in ("JPEG","PNG","WEBP") or source.width*source.height>20_000_000:
    abort(400,description="Dimensions ou format d'image non accepté.")
   source.load()
   img=ImageOps.exif_transpose(source)
   if img.mode in ("RGBA","LA") or "transparency" in img.info:
    rgba=img.convert("RGBA")
    canvas=Image.new("RGB",rgba.size,(255,255,255))
    canvas.paste(rgba,mask=rgba.getchannel("A"))
    img=canvas
   else:
    img=img.convert("RGB")
   img.thumbnail((1600,1600),Image.Resampling.LANCZOS)
   output=io.BytesIO()
   img.save(output,format="JPEG",quality=82,optimize=True)
   data=output.getvalue()
 except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError):
  abort(400,description="Impossible de lire cette image.")
 if not data or len(data)>4*1024*1024:
  abort(413,description="Photo trop volumineuse.")
 return name,data,"image/jpeg"

def submission(kind):
 if request.method=="GET":
  chosen=None
  chosen_photo_id=0
  chosen_photo_url=""
  if kind=="Soumission" and request.args.get("galerie"):
   raw=request.args.get("galerie","")
   pic=request.args.get("photo","0")
   if not raw.isdigit() or not pic.isdigit() or len(raw)>18 or len(pic)>18:abort(400)
   chosen_photo_id=int(pic)
   with db() as c:chosen=fjord_gallery_asset(c,int(raw),chosen_photo_id)
   if not chosen:abort(404)
   chosen_photo_url=("/photo/"+str(chosen["id"]) if chosen_photo_id==0
                     else "/gallery/image/"+str(chosen_photo_id))
  inspiration_selected=None
  inspiration_index=0
  inspiration_has_model=False
  if kind=="Soumission" and request.args.get("inspiration") is not None:
   raw=request.args.get("inspiration","")
   if not raw.isdigit() or len(raw)>3:abort(400)
   inspiration_index=int(raw)
   inspiration_selected=fjord_inspiration_by_index(inspiration_index)
   if inspiration_selected is None:abort(404)
   with db() as c:
    row=fjord_inspiration_model(c,inspiration_selected)
    inspiration_has_model=bool(row and row["rights_confirmed"])
  return page(kind,FORM + MARKETING_SCRIPT,gallery_selected=chosen,
              gallery_photo_id=chosen_photo_id,gallery_photo_url=chosen_photo_url,
              inspiration_selected=inspiration_selected,inspiration_index=inspiration_index,
              inspiration_has_model=inspiration_has_model,heading="Demander une soumission" if kind=="Soumission" else "Nous contacter",intro="Décrivez votre projet et joignez votre modèle 3D si vous en avez un." if kind=="Soumission" else "Envoyez-nous votre message directement depuis ce formulaire.",quote=kind=="Soumission",materials=MATERIALS,csrf=csrfinput(),marketing_help=MARKETING_FORM_HELP,colors=COLORS,project_types=PROJECT_TYPES,remise_options=REMISE_OPTIONS,delai_options=DELAI_OPTIONS,preview=os.environ.get("FJORD_PREVIEW_MODE")=="1",prefill=("Je souhaite une création semblable à « "+chosen["title"][:120]+" » (photo de la galerie). "
 if chosen else ("Je voudrais discuter d'une création inspirée de « "+inspiration_selected["title"][:120]+" ». "
 if inspiration_selected else ("Je souhaite une création similaire à « "+request.args.get("projet","")[:160]+" ». "
 if kind=="Soumission" and request.args.get("projet") else ""))))
 verify()
 name=request.form.get("name","").strip();email=request.form.get("email","").strip().lower();description=request.form.get("description","").strip();phone=request.form.get("phone","").strip()[:40]
 if not name or len(name)>120 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or len(email)>200 or not description or len(description)>5000:abort(400)
 if not rate_limit():abort(429)
 if kind=="Soumission":
  raw_quantity=request.form.get("quantity","1").strip()
  if not raw_quantity.isdigit() or not 1<=int(raw_quantity)<=1000:abort(400)
  selected_color=request.form.get("color","À déterminer")
  if selected_color not in COLORS:abort(400)
  project_type=request.form.get("project_type","À déterminer").strip()
  remise=request.form.get("remise","À discuter").strip()
  delai=request.form.get("delai","Flexible").strip()
  dimensions=request.form.get("dimensions","").strip()
  if project_type not in PROJECT_TYPES or remise not in REMISE_OPTIONS or delai not in DELAI_OPTIONS:abort(400)
  if len(dimensions)>120 or any(ord(ch)<32 for ch in dimensions):abort(400)
  description=("Type de projet : "+project_type+"\n"
               "Dimensions approximatives : "+(dimensions or "Non précisées")+"\n"
               "Remise souhaitée : "+remise+"\n"
               "Délai souhaité : "+delai+"\n"
               "Quantité demandée : "+raw_quantity+"\n"
               "Couleur souhaitée : "+selected_color+"\n\n"+description)
 material=request.form.get("material","À déterminer") if kind=="Soumission" else None
 if material and material not in MATERIALS:abort(400)
 f=request.files.get("model");filename=None;data=None
 if f and f.filename:
  filename=secure_filename(f.filename)
  if not filename.lower().endswith((".stl",".3mf")):abort(400)
  data=f.read(16*1024*1024+1)
  if len(data)>16*1024*1024:abort(413)
  if filename.lower().endswith(".3mf"):
   from zipfile import is_zipfile
   if not is_zipfile(io.BytesIO(data)):abort(400)
  if filename.lower().endswith(".stl") and len(data)<84:abort(400)
 ref_name,ref_photo,ref_mime=fjord_reference_image(request.files.get("reference_photo")) if kind=="Soumission" else (None,None,None)
 if kind=="Soumission" and request.form.get("gallery_id") and request.form.get("inspiration_id") is not None:
  abort(400,description="Choisissez une seule réalisation ou inspiration.")
 if kind=="Soumission" and request.form.get("gallery_id"):
  raw=request.form.get("gallery_id","")
  pic=request.form.get("gallery_photo_id","0")
  if not raw.isdigit() or not pic.isdigit() or len(raw)>18 or len(pic)>18:abort(400)
  with db() as c:
   gallery_ref=fjord_gallery_asset(c,int(raw),int(pic),with_photo=True)
  if not gallery_ref:abort(400,description="La photo sélectionnée n'appartient pas à cette réalisation.")
  if not ref_photo and gallery_ref["photo"]:
   ref_photo=fjord_gallery_quote_image(gallery_ref["photo"],gallery_ref["mime"])
   ref_name="realisation-"+str(gallery_ref["id"])+"-photo-"+str(pic)+".jpg"
   ref_mime="image/jpeg"
  if not data and gallery_ref["model_data"]:
   data=gallery_ref["model_data"]
   filename=gallery_ref["model_filename"]
  description=("Référence galerie #"+str(gallery_ref["id"])+
               ", photo #"+str(pic)+" — "+gallery_ref["title"][:120]+"\n\n"+description)
 if kind=="Soumission" and request.form.get("inspiration_id") is not None:
  raw=request.form.get("inspiration_id","")
  if not raw.isdigit() or len(raw)>3:abort(400)
  idea_index=int(raw)
  idea=fjord_inspiration_by_index(idea_index)
  if idea is None:abort(400,description="Inspiration inconnue.")
  with db() as c:linked=fjord_inspiration_model(c,idea)
  if not data and linked and linked["rights_confirmed"]:
   filename=linked["model_filename"]
   data=linked["model_data"]
  if not ref_photo:
   picture=fjord_inspiration_image_copy(idea)
   if picture:
    ref_photo=picture
    ref_name="inspiration-"+str(idea_index+1)+".jpg"
    ref_mime="image/jpeg"
  description=("Inspiration du diaporama #"+str(idea_index+1)+
               " — "+idea["title"][:120]+"\n"+
               "Photo de référence : "+idea["image"]+"\n"+
               "Source : "+idea["source"]+"\n"+
               "Crédit photo : "+idea["author"]+" — "+idea["license"]+
               " ("+idea["license_url"]+")\n"+
               "Modèle 3D associé : "+("oui (fichier lié)" if linked and linked["rights_confirmed"] else "non")+
               "\n\n"+description)
 with db() as c:
  request_id=c.execute("""INSERT INTO requests(kind,name,email,phone,material,description,filename,filedata,reference_filename,reference_photo,reference_mime)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",(kind,name,email,phone,material,description,filename,data,ref_name,ref_photo,ref_mime)).fetchone()["id"]
 notify(kind,name,email)
 return page("Merci",'''<section class="fjord-thanks"><span class="fjord-thanks-symbol" aria-hidden="true">✓</span><p class="fjord-steps-tag">Message reçu</p><h1>Merci pour votre demande!</h1><p>Votre message a été enregistré. Nous vous répondrons dès que possible.</p><p>Votre numéro de référence : <strong>#{{request_id}}</strong></p>{% if is_quote %}<p class="fjord-source-verified">Conservez ce numéro et le courriel utilisé pour retrouver votre suivi après la prise en charge.</p>{% endif %}<div class="fjm-hero-actions"><a class="btn" href="/">Retour à l’accueil</a>{% if is_quote %}<a class="btn secondary-btn" href="/suivi">Suivre ma demande</a>{% endif %}</div></section>''',request_id=request_id,is_quote=kind=="Soumission")
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
   session.clear();session["admin_token"]=token
   destination=request.args.get("next","")
   if not (destination.startswith("/admin") and not destination.startswith("//") and "\\\\" not in destination):
    destination="/admin"
   return redirect(destination)
  flash("Connexion refusée.")
 return page("Connexion",'<h1>Administration privée</h1><form method="post">{{csrf|safe}}<label>Mot de passe<input type="password" name="password" required autocomplete="current-password"></label><button>Se connecter</button></form>',csrf=csrfinput())
@app.get("/admin")
@admin_required
def admin():
 with db() as c:
  reqs=c.execute("SELECT id,kind,name,email,phone,material,description,filename,reference_filename,created,status,progress,live_enabled,live_url,public_progress FROM requests ORDER BY id DESC LIMIT 12").fetchall()
  reqs_count=c.execute("SELECT COUNT(*) AS total FROM requests").fetchone()["total"]
  commercial=c.execute("""SELECT
      COUNT(*) FILTER (WHERE kind='Soumission' AND created >= NOW() - INTERVAL '30 days') AS quotations_30d,
      COUNT(*) FILTER (WHERE kind='Contact' AND created >= NOW() - INTERVAL '30 days') AS contacts_30d,
      COUNT(*) FILTER (WHERE kind='Soumission') AS quotations_all
      FROM requests""").fetchone()
  gallery=c.execute("SELECT id,title,category FROM gallery ORDER BY id DESC").fetchall()
  quotes_stats=c.execute("""SELECT COUNT(*) FILTER (WHERE payment_status <> 'Payée' AND deleted_at IS NULL) AS unpaid,
      COUNT(*) FILTER (WHERE payment_status = 'Payée' AND deleted_at IS NULL) AS paid FROM private_quotes""").fetchone()
 from fjord_bambu_connect import bridge_state as _bridge_state
 bridge=_bridge_state(db)
 return page("Administration",'''<style>
.admin-dashboard{max-width:1500px;margin:0 auto;padding:clamp(12px,2.4vw,30px)}
.admin-dashboard *{box-sizing:border-box}
.admin-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:0 0 24px}
.admin-hero .eyebrow{color:#82d8f5;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.admin-hero h1{font-size:clamp(30px,4vw,48px);line-height:1.05;margin:7px 0}
.admin-hero p{max-width:690px;margin:0;color:#b7cad9}
.admin-clock{color:#b5d7e7;font-size:13px}
.admin-control-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:22px 0}
.admin-control-card{display:flex;flex-direction:column;min-width:0;min-height:226px;padding:19px;border:1px solid #286488;border-radius:16px;background:linear-gradient(155deg,#123550,#0a2238);box-shadow:0 10px 26px #00132430}
.admin-card-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
.admin-control-card h2{font-size:16px;line-height:1.3;margin:0;color:#eff8ff}
.admin-icon{display:grid;place-items:center;flex:0 0 38px;height:38px;border:1px solid #397b9b;border-radius:11px;background:#0d2c45;font-size:19px}
.admin-control-card p{margin:6px 0;color:#bdd1df;line-height:1.5}
.admin-metric{font-size:34px;line-height:1.1;font-weight:850;color:#76e2ff;margin:2px 0}
.admin-metric-label{color:#b7cad9;font-size:13px}
.admin-mini-metric{font-size:15px;color:#e5f4ff;margin-top:12px}
.admin-card-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto;padding-top:15px}
.admin-card-actions a,.admin-shortcuts a{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:9px 12px;border:1px solid #377e9f;border-radius:10px;background:#123c59;color:#dff7ff;text-decoration:none;font-weight:750;font-size:13px}
.admin-card-actions a:hover,.admin-shortcuts a:hover{background:#175477;border-color:#65ceee}
.admin-card-actions a.primary{background:#0d82b8;border-color:#5ed6f7;color:#fff}
.admin-status{display:inline-flex;align-items:center;gap:7px;padding:5px 9px;border-radius:999px;background:#102a3d;border:1px solid #3a6075;color:#c4d8e3;font-size:12px;font-weight:800}
.admin-shortcut-panel{margin:20px 0 30px;padding:17px;border:1px solid #284c64;border-radius:16px;background:#0c2438}
.admin-shortcut-panel h2{margin:0 0 12px;font-size:16px}
.admin-shortcuts{display:flex;gap:9px;flex-wrap:wrap}
.admin-shortcuts form{margin:0}
.admin-shortcuts button{min-height:40px;padding:9px 13px;border:1px solid #5297b4;border-radius:10px;background:#173a53;color:#eefaff;font-weight:750;cursor:pointer}
.admin-shortcuts button:hover{background:#204f6c}
.admin-requests-section{margin-top:28px}
.admin-section-head{display:flex;align-items:end;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:13px}
.admin-section-head h2{font-size:24px;margin:0}
.admin-section-head p{font-size:13px;color:#b6cbd9;margin:4px 0 0}
.admin-request-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.admin-request-card{min-width:0;margin:0;padding:18px;border:1px solid #284e68;border-radius:15px;background:linear-gradient(155deg,#102c43,#0b2135)}
.admin-request-card h3{margin:6px 0;font-size:18px;overflow-wrap:anywhere}
.admin-request-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:#a9c7d8;font-size:12px}
.admin-request-card p{line-height:1.5;overflow-wrap:anywhere}
.admin-request-card form{margin:14px 0 0}
.admin-request-card form label{font-size:13px}
.admin-request-card select,.admin-request-card input{max-width:100%}
.admin-empty{padding:24px;border:1px dashed #37617a;border-radius:14px;background:#0c2438;color:#bdd1df}
@media(max-width:1050px){.admin-control-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.admin-dashboard{padding:10px}.admin-hero{margin-bottom:16px}.admin-hero h1{font-size:32px}.admin-control-grid{grid-template-columns:1fr;gap:10px;margin:14px 0}.admin-control-card{min-height:0;padding:16px}.admin-card-actions a{flex:1 1 auto}.admin-shortcut-panel{padding:14px}.admin-shortcuts{display:grid;grid-template-columns:1fr 1fr}.admin-shortcuts a,.admin-shortcuts form,.admin-shortcuts button{width:100%;text-align:center}.admin-shortcuts form{grid-column:1/-1}.admin-request-grid{grid-template-columns:1fr;gap:10px}.admin-request-card{padding:14px}.admin-section-head h2{font-size:21px}}
</style>
<main class="admin-dashboard">
<style>
.admin-dashboard{max-width:1320px;margin:0 auto;padding:clamp(14px,2.5vw,32px)}.admin-dashboard *{box-sizing:border-box}
.admin-hero{display:flex;align-items:end;justify-content:space-between;gap:18px;flex-wrap:wrap;margin:0 0 20px;padding:24px clamp(18px,3vw,32px);border:1px solid #347e9f;border-radius:20px;background:radial-gradient(circle at 88% 10%,#1378a055,transparent 34%),linear-gradient(120deg,#123852,#0a2237);box-shadow:0 14px 40px #00101f50}
.admin-hero .eyebrow{color:#82d8f5;font-size:12px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.admin-hero h1{font-size:clamp(30px,4vw,46px);line-height:1.05;margin:7px 0}.admin-hero p{margin:0;color:#c1d6e2}.admin-hero-side{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.admin-clock{color:#b5d7e7;font-size:13px}.admin-logout{margin:0}.admin-logout button{padding:9px 14px;border:1px solid #4382a0;border-radius:10px;background:#102d43;color:#eefaff;font-weight:750}
.admin-overview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0 28px}.admin-overview article{padding:14px 17px;border:1px solid #2e6480;border-radius:13px;background:#102c42}.admin-overview strong{display:block;font-size:27px;line-height:1.1;color:#80e2ff}.admin-overview small{display:block;margin-top:5px;color:#c0d4df;font-size:12px}
.admin-task-section{margin:28px 0}.admin-task-head{display:flex;align-items:end;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}.admin-task-head h2{font-size:23px;margin:0}.admin-task-head p{margin:3px 0 0;color:#afc7d6;font-size:13px}
.admin-task-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.admin-task-grid.catalogue{grid-template-columns:repeat(4,minmax(0,1fr))}
.admin-task-card{display:flex;flex-direction:column;gap:8px;min-width:0;min-height:162px;padding:17px;border:1px solid #2e6988;border-radius:15px;background:linear-gradient(155deg,#123750,#0a2438);color:#effaff!important;text-decoration:none!important;transition:border-color .16s,transform .16s}.admin-task-card:hover{transform:translateY(-2px);border-color:#72d9f5}.admin-task-card:focus-visible{outline:3px solid #a5efff;outline-offset:3px}.admin-task-card .task-icon{display:grid;place-items:center;width:39px;height:39px;border:1px solid #397d9e;border-radius:12px;background:#0c2d45;font-size:20px}.admin-task-card strong{font-size:16px;line-height:1.25}.admin-task-card span{color:#b9d2df;font-size:13px;line-height:1.45}.admin-task-card .task-count{margin-top:auto;color:#7ee3ff;font-size:13px;font-weight:850}.admin-task-card.primary-task{border-color:#4ba9c8;background:linear-gradient(145deg,#124a67,#0b2b40)}.admin-printer-state{min-height:38px;color:#b9d2df;font-size:13px;line-height:1.45}
.admin-dashboard-foot{margin-top:30px;padding:13px 15px;border:1px solid #294d65;border-radius:12px;background:#0b2438;color:#afc7d6;font-size:13px}
body.light .admin-hero{background:linear-gradient(120deg,#e7f7ff,#d0eefb);border-color:#acd4e5}body.light .admin-hero h1{color:#173c55}body.light .admin-hero p,body.light .admin-clock{color:#355e73}body.light .admin-overview article,body.light .admin-task-card,body.light .admin-dashboard-foot{background:#fff;border-color:#c4dce8;color:#19465f!important}body.light .admin-overview small,body.light .admin-task-head p,body.light .admin-task-card span,body.light .admin-dashboard-foot{color:#3b6277}body.light .admin-task-card .task-icon{background:#e3f5fc}body.light .admin-task-card .task-count{color:#087dab}
@media(max-width:920px){.admin-task-grid.catalogue{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.admin-dashboard{padding:12px}.admin-hero{padding:18px;margin-bottom:14px}.admin-hero h1{font-size:32px}.admin-overview{gap:8px;margin:12px 0 22px}.admin-overview article{padding:12px}.admin-overview strong{font-size:23px}.admin-task-grid,.admin-task-grid.catalogue{grid-template-columns:1fr 1fr;gap:9px}.admin-task-card{min-height:150px;padding:14px}.admin-hero-side{width:100%;justify-content:space-between}}
@media(max-width:450px){.admin-overview{grid-template-columns:1fr 1fr}.admin-overview article:last-child{grid-column:1/-1}.admin-task-grid,.admin-task-grid.catalogue{grid-template-columns:1fr}.admin-task-card{min-height:0}.admin-task-head h2{font-size:20px}}
</style>
<header class="admin-hero"><div><div class="eyebrow">Administration · Les Impressions du Fjord</div><h1>Que veux-tu faire?</h1><p>Tout est regroupé par tâche : commandes, production et catalogue.</p></div><div class="admin-hero-side"><div class="admin-clock" id="adminLocalClock" aria-live="off"></div><form class="admin-logout" method="post" action="/admin/logout">{{csrf|safe}}<button>↪ Déconnexion</button></form></div></header>
<section class="admin-overview" aria-label="Activité commerciale"><article><strong>{{commercial.quotations_30d}}</strong><small>Soumissions reçues · 30 derniers jours</small></article><article><strong>{{commercial.contacts_30d}}</strong><small>Messages contact · 30 derniers jours</small></article><article><strong>{{commercial.quotations_all}}</strong><small>Soumissions reçues depuis le début</small></article></section>
<section class="admin-task-section" aria-labelledby="admin-orders-title"><div class="admin-task-head"><div><h2 id="admin-orders-title">1 · Commandes et clients</h2><p>Ouvre le tableau approprié selon ce que tu dois traiter.</p></div></div><div class="admin-task-grid">
<a class="admin-task-card primary-task" href="/admin/soumissions-pro"><span class="task-icon">📄</span><strong>Tableau des soumissions</strong><span>Prix, paiement, production et historique des soumissions PRO.</span><span class="task-count">{{quotes_stats.unpaid}} à traiter ou à payer · {{quotes_stats.paid}} payée(s)</span></a>
<a class="admin-task-card" href="/admin/demandes"><span class="task-icon">📥</span><strong>Demandes reçues</strong><span>Lire, rechercher et préparer les demandes des clients.</span><span class="task-count">{{reqs_count}} demande(s) au total</span></a>
<a class="admin-task-card" href="/voir-mon-impression"><span class="task-icon">🔎</span><strong>Suivi client</strong><span>Voir le tableau que les clients utilisent pour suivre leurs commandes.</span><span class="task-count">Ouvrir le suivi public →</span></a>
</div></section>
<section class="admin-task-section" aria-labelledby="admin-production-title"><div class="admin-task-head"><div><h2 id="admin-production-title">2 · Production et imprimante</h2><p>Prépare une pièce, vérifie la X2D ou ouvre l’Atelier.</p></div></div><div class="admin-task-grid">
<a class="admin-task-card primary-task" href="/admin/atelier-imprimer"><span class="task-icon">🖨️</span><strong>Imprimer sur ma X2D</strong><span class="admin-printer-state" id="fjord-admin-printer-status">Lecture de l’état de l’imprimante…</span><span class="task-count">Ouvrir le contrôle d’impression →</span></a>
<a class="admin-task-card" href="/admin/atelier-3d"><span class="task-icon">🧊</span><strong>Atelier 3D privé</strong><span>Importer, modifier, trancher ou préparer une pièce à partir d’ici.</span><span class="task-count">Ouvrir l’Atelier →</span></a>
<a class="admin-task-card" href="/admin/atelier-pont"><span class="task-icon">🔌</span><strong>Connexion Bambu Connect</strong><span>État du PC relais : {% if bridge.online %}en ligne{% elif bridge.paired %}hors ligne{% else %}à associer{% endif %}.</span><span class="task-count">Gérer la connexion →</span></a>
</div></section>
<section class="admin-task-section" aria-labelledby="admin-catalogue-title"><div class="admin-task-head"><div><h2 id="admin-catalogue-title">3 · Catalogue et réglages</h2><p>Gère les modèles, les photos et les fichiers prêts à imprimer.</p></div></div><div class="admin-task-grid catalogue">
<a class="admin-task-card" href="/admin/modeles"><span class="task-icon">📚</span><strong>Bibliothèque 3D</strong><span>Retrouver les STL, 3MF et projets enregistrés.</span><span class="task-count">Ouvrir →</span></a>
<a class="admin-task-card" href="/admin/new"><span class="task-icon">🖼️</span><strong>Ajouter une réalisation</strong><span>Publier les photos et associer le modèle 3D au projet.</span><span class="task-count">Gérer le catalogue →</span></a>
<a class="admin-task-card" href="/admin/inspirations"><span class="task-icon">✨</span><strong>Diaporama d’inspiration</strong><span>Gérer les idées et les modèles affichés sur l’accueil.</span><span class="task-count">Gérer le diaporama →</span></a>
<a class="admin-task-card" href="/admin/profils-bambu"><span class="task-icon">⚙️</span><strong>Profils Bambu</strong><span>Retrouver les paramètres d’impression de l’atelier.</span><span class="task-count">Ouvrir les profils →</span></a>
</div></section>
<div class="admin-dashboard-foot">Le tableau des soumissions et le suivi client restent accessibles en haut de chaque page.</div>
</main><script>
(async function(){const box=document.getElementById('fjord-admin-printer-status');if(!box)return;try{const r=await fetch('/api/admin/atelier/impression-etat?live='+Date.now(),{credentials:'same-origin',cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();if(!s.ok)throw Error();const state=String(s.state||'inconnu').replace(/_/g,' ');const parts=[({'printing':'En impression','paused':'En pause','idle':'Prête','finished':'Terminée','failed':'Erreur'}[s.state]||state),s.file?'Fichier : '+s.file:'Aucun fichier en cours'];if(typeof s.progress==='number')parts.push(Math.round(s.progress)+' %');box.textContent=parts.join(' · ');}catch(_){box.textContent='État non disponible. Ouvre le contrôle X2D pour actualiser.'}})();
(function(){const el=document.getElementById('adminLocalClock');if(!el)return;const update=()=>{el.textContent=new Intl.DateTimeFormat('fr-CA',{dateStyle:'full',timeStyle:'short'}).format(new Date())};update();setInterval(update,60000)})();
</script>''',reqs=reqs,reqs_count=reqs_count,gallery=gallery,statuses=STATUSES,csrf=csrfinput(),bridge=bridge,quotes_stats=quotes_stats,commercial=commercial)
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
@app.get("/admin/demandes")
@admin_required
def fjord_admin_demandes():
 """Searchable full archive, admin only; latest-12 dashboard remains compact."""
 from urllib.parse import urlencode
 query=request.args.get("q","").strip()[:100]
 kind=request.args.get("type","").strip()
 status=request.args.get("statut","").strip()
 if kind not in ("Soumission","Contact"):kind=""
 if status not in STATUSES:status=""
 try:
  page_num=max(1,min(1000,int(request.args.get("page","1"))))
 except (TypeError,ValueError):
  page_num=1
 clauses=[]
 params=[]
 if query:
  clauses.append("(name ILIKE %s OR email ILIKE %s OR CAST(id AS TEXT) LIKE %s)")
  params.extend(["%"+query+"%","%"+query+"%","%"+query+"%"])
 if kind:
  clauses.append("kind=%s")
  params.append(kind)
 if status:
  clauses.append("status=%s")
  params.append(status)
 where=" WHERE "+" AND ".join(clauses) if clauses else ""
 with db() as c:
  total=c.execute("SELECT COUNT(*) AS count FROM requests"+where,tuple(params)).fetchone()["count"]
  last=max(1,(total+24)//25)
  page_num=min(page_num,last)
  rows=c.execute("""SELECT id,kind,name,email,phone,material,description,
       filename,reference_filename,created,status
       FROM requests"""+where+" ORDER BY id DESC LIMIT %s OFFSET %s",
       tuple(params+[25,(page_num-1)*25])).fetchall()
 def url(num):
  return "/admin/demandes?"+urlencode({"q":query,"type":kind,"statut":status,"page":num})
 return page("Historique des demandes",'''<section class="fjord-demandes-history">
 <p><a href="/admin">← Retour à l'administration</a></p>
 <h1>Historique des demandes</h1>
 <p>Recherchez une soumission ou un message par nom, courriel ou numéro de demande.</p>
 <form class="fjord-history-filters" method="get" action="/admin/demandes">
 <label>Rechercher<input name="q" type="search" value="{{query}}" maxlength="100" placeholder="Nom, courriel ou #123" autocomplete="off"></label>
 <label>Type<select name="type"><option value="">Tous</option>{% for value in kinds %}<option value="{{value}}" {% if value==kind %}selected{% endif %}>{{value}}</option>{% endfor %}</select></label>
 <label>Statut<select name="statut"><option value="">Tous</option>{% for value in statuses %}<option value="{{value}}" {% if value==status %}selected{% endif %}>{{value}}</option>{% endfor %}</select></label>
 <button type="submit">Rechercher</button><a href="/admin/demandes">Effacer les filtres</a></form>
 <p class="fjord-history-summary">{{total}} demande(s) trouvée(s) · Page {{page_num}} sur {{last}}</p>
 <div class="fjord-history-results">{% for r in rows %}
 <article class="fjord-history-card"><div class="admin-request-meta"><strong>#{{r.id}}</strong> · {{r.kind}} · {{r.created.strftime('%Y-%m-%d')}} · {{r.status}}</div>
 <h2>{{r.name}}</h2><p><a href="mailto:{{r.email}}">{{r.email}}</a>{% if r.phone %} · {{r.phone}}{% endif %}</p>
 <p>Matériau : {{r.material or '—'}}</p>
 <details><summary>Voir la description</summary><p style="white-space:pre-wrap">{{r.description}}</p></details>
 <div class="fjord-history-actions">
 {% if r.reference_filename %}<a href="/admin/reference-photo/{{r.id}}" target="_blank" rel="noopener noreferrer">📷 Photo de référence</a>{% endif %}
 {% if r.filename %}<a href="/admin/file/{{r.id}}">⬇ Télécharger le modèle 3D</a>
 <a href="/admin/atelier-3d?demande={{r.id}}&amp;preparer=1">⚡ Préparer sur la X2D</a>{% endif %}
 {% if r.kind=='Soumission' %}<a href="/admin/soumissions-pro?request_id={{r.id}}">📄 Soumission PRO</a>{% endif %}
 </div></article>{% else %}<p class="admin-empty">Aucune demande ne correspond à ces critères.</p>{% endfor %}</div>
 <nav class="fjord-history-pages" aria-label="Pages de l'historique">
 {% if page_num>1 %}<a href="{{previous}}">← Précédente</a>{% endif %}
 <span>Page {{page_num}} / {{last}}</span>
 {% if page_num<last %}<a href="{{following}}">Suivante →</a>{% endif %}
 </nav></section>''',
 query=query,kind=kind,status=status,statuses=STATUSES,kinds=("Soumission","Contact"),
 rows=rows,total=total,page_num=page_num,last=last,
 previous=url(page_num-1),following=url(page_num+1))

@app.get("/admin/reference-photo/<int:id>")
@admin_required
def fjord_admin_reference_photo(id):
 """Private only: customers' reference images must never appear in public galleries."""
 with db() as c:
  row=c.execute("SELECT reference_photo,reference_mime FROM requests WHERE id=%s",(id,)).fetchone()
 if not row or not row["reference_photo"]:abort(404)
 return send_file(io.BytesIO(row["reference_photo"]),mimetype="image/jpeg",
                  as_attachment=False,download_name="reference-client.jpg",
                  max_age=0,conditional=False),200,{"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff","X-Robots-Tag":"noindex, nofollow"}

@app.get("/admin/demandes/model/<int:id>")
@admin_required
def fjord_private_request_model_for_atelier(id):
 """Return the exact customer STL/3MF, never by an untrusted filename."""
 with db() as c:
  model=c.execute("""SELECT filename,filedata FROM requests
                     WHERE id=%s AND kind='Soumission'""",(id,)).fetchone()
 if not model or not model["filedata"] or not model["filename"]:abort(404)
 if not model["filename"].lower().endswith((".stl",".3mf")):abort(400)
 return send_file(io.BytesIO(model["filedata"]),
                  as_attachment=True,download_name=model["filename"],
                  mimetype="application/octet-stream",max_age=0,conditional=False),200,{
                   "Cache-Control":"no-store, private",
                   "X-Robots-Tag":"noindex, nofollow",
                   "X-Content-Type-Options":"nosniff",
                   "X-Fjord-Model-Name":model["filename"]}

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
GALLERY_FORM='''<section class="fjord-gallery-manage"><h1>{{heading}}</h1>
 <p>Chaque photo peut être liée à un STL/3MF. Associez un modèle commun à toute la réalisation, ou remplacez-le par un modèle propre à une photo.</p>
 <form method="post" enctype="multipart/form-data">
 {{csrf|safe}}
 <label>Titre<input name="title" value="{{item.title if item else ''}}" maxlength="120" required></label>
 <label>Catégorie<input name="category" value="{{item.category if item else ''}}" maxlength="120" required></label>
 <label>Description<textarea name="description" maxlength="2000" required>{{item.description if item else ''}}</textarea></label>
 <label class="fjord-real-photo-toggle" style="display:flex;align-items:center;gap:10px;padding:12px;border:1px solid #347593;border-radius:10px"><input type="checkbox" name="is_real_photo" style="display:inline-block;width:20px;min-width:20px;height:20px;margin:0" {% if item and item.is_real_photo %}checked{% endif %}> Photo réelle d’une pièce imprimée (à afficher en priorité)</label>
 <label>Modèle STL/3MF commun à cette réalisation (20 Mo maximum)
 <input type="file" name="default_model" accept=".stl,.3mf"></label>
 {% if item and item.model_filename %}
 <p class="fjord-gallery-model-ready">✓ Modèle commun associé : <strong>{{item.model_filename}}</strong>
 <a href="/admin/gallery/model/{{item.id}}">Télécharger</a>
 <a href="/admin/atelier-3d?galerie={{item.id}}&photo={{main_photo}}">Ouvrir dans l'Atelier 3D</a></p>
 {% endif %}
 <label>Associer automatiquement des fichiers STL/3MF (même nom que la photo)
<input type="file" name="models" multiple accept=".stl,.3mf">
<small>Exemple : support_photo_1.jpg et support.3mf. Si un fichier existe déjà dans ta bibliothèque, le site essaie aussi de le retrouver. Un nom ambigu n'est jamais associé au hasard.</small></label>
<label>Ajouter des photos (6 à la fois, 5 Mo chacune)
 <input type="file" name="photos" multiple accept="image/jpeg,image/png,image/webp"></label>
 <button type="submit">Enregistrer et associer automatiquement</button>
 </form>
 {% if item %}
 <form method="post" action="/admin/galerie/{{item.id}}/associer-automatiquement" class="fjord-gallery-auto-form">
 {{csrf|safe}}
 <button type="submit">⚡ Associer les photos existantes à ma bibliothèque</button>
 <small>Compare les noms exacts des fichiers. Rien n'est supprimé ni remplacé.</small>
 </form>
 <h2>Photos et modèles de cette réalisation</h2>
 <p>Les modèles associés restent privés. Le client peut sélectionner une photo, et sa soumission reprendra la photo et le fichier 3D correspondant.</p>
 {% if item.has_photo %}<article class="fjord-gallery-photo-model">
 <img src="/photo/{{item.id}}" width="120" alt="Photo principale">
 <div><strong>Photo principale</strong><p>{{'✓ Modèle associé : '+item.model_filename if item.model_filename else '⚠ Aucun STL/3MF associé'}}</p>
 <a href="/soumission?galerie={{item.id}}&photo=0">Tester la soumission</a></div></article>{% endif %}
 {% for p in photos %}
 <article class="fjord-gallery-photo-model">
 <img src="/gallery/image/{{p.id}}" width="120" alt="Photo de galerie {{loop.index}}">
 <div class="fjord-gallery-photo-content"><strong>Photo {{loop.index}}</strong>
 {% if p.model_filename %}<p>✓ Modèle propre à cette photo : {{p.model_filename}}</p>
 {% elif item.model_filename %}<p>✓ Modèle commun de la réalisation : {{item.model_filename}}</p>
 {% else %}<p>⚠ Pas encore de STL/3MF associé</p>{% endif %}
 <div class="fjord-gallery-photo-actions">
 <a href="/soumission?galerie={{item.id}}&photo={{p.id}}">Tester la soumission</a>
 {% if p.model_filename or item.model_filename %}
 <a href="/admin/gallery/model/{{item.id}}?photo={{p.id}}">Télécharger le modèle</a>
 <a href="/admin/atelier-3d?galerie={{item.id}}&photo={{p.id}}">🖨️ Ouvrir dans l'Atelier</a>{% endif %}</div>
 <form method="post" enctype="multipart/form-data" action="/admin/galerie/photo/{{p.id}}/modele">
 {{csrf|safe}}
 <label>STL/3MF pour cette photo <input type="file" name="model" accept=".stl,.3mf" required></label>
 <button type="submit">Associer / remplacer le modèle</button></form>
 </div>
 <form method="post" action="/admin/photo/delete/{{p.id}}">{{csrf|safe}}
 <button type="submit" class="secondary-btn">Supprimer la photo</button></form>
 </article>{% endfor %}
 {% endif %}</section>'''

@app.route("/admin/new",methods=["GET","POST"])
@admin_required
def new():return gallery_edit(None)
@app.route("/admin/edit/<int:id>",methods=["GET","POST"])
@admin_required
def edit(id):return gallery_edit(id)
def gallery_edit(id):
 with db() as c:
  item=c.execute("SELECT id,title,category,description,photo IS NOT NULL AS has_photo,model_filename,is_real_photo FROM gallery WHERE id=%s",(id,)).fetchone() if id else None
  if id and not item:abort(404)
  if request.method=="POST":
   verify()
   title=request.form.get("title","").strip();category=request.form.get("category","").strip();description=request.form.get("description","").strip();is_real_photo=request.form.get("is_real_photo")=="on"
   if not title or not category or not description or max(len(title),len(category))>120 or len(description)>2000:abort(400)
   files=request.files.getlist("photos")
   if len(files)>6:abort(400)
   images=image_uploads(files)
   photo_inputs=[f for f in files if f and f.filename]
   if len(photo_inputs)!=len(images):abort(400)
   multi=request.files.getlist("models")
   if len(multi)>8:abort(400,description="Maximum 8 modèles par lot.")
   uploads=[]
   for f in multi:
    name,blob=fjord_gallery_model_upload(f)
    if blob:uploads.append({"name":name,"filename":name,"data":blob})
   model_name,model_data=fjord_gallery_model_upload(request.files.get("default_model"))
   if id:
    if model_data:
     c.execute("""UPDATE gallery SET title=%s,category=%s,description=%s,
                        model_filename=%s,model_data=%s,is_real_photo=%s WHERE id=%s""",
               (title,category,description,model_name,model_data,is_real_photo,id))
    else:
     c.execute("UPDATE gallery SET title=%s,category=%s,description=%s,is_real_photo=%s WHERE id=%s",
               (title,category,description,is_real_photo,id))
   else:
    id=c.execute("""INSERT INTO gallery(title,category,description,model_filename,model_data,is_real_photo)
                    VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                 (title,category,description,model_name,model_data,is_real_photo)).fetchone()["id"]
   library=fjord_gallery_library_candidates(c)
   auto_count=0
   for uploaded,(data,mime) in zip(photo_inputs,images):
    linked=fjord_gallery_model_for_photo(c,uploaded.filename,uploads,library)
    photo_model,photo_blob=(linked[0],linked[1]) if linked else (None,None)
    c.execute("""INSERT INTO gallery_photos
       (gallery_id,photo,mime,original_filename,model_filename,model_data)
       VALUES(%s,%s,%s,%s,%s,%s)""",
       (id,data,mime,secure_filename(uploaded.filename)[:150],photo_model,photo_blob))
    if linked:auto_count+=1
   extra,total=fjord_gallery_fill_missing_links(c,id,uploads)
   auto_count+=extra
   if len(images)>0 or uploads:
    flash("⚡ "+str(auto_count)+" photo(s) associée(s) automatiquement à un modèle. Les autres restent à vérifier.")
   return redirect("/admin/edit/"+str(id))
  photos=c.execute("""SELECT id,model_filename FROM gallery_photos
                       WHERE gallery_id=%s ORDER BY id""",(id,)).fetchall() if id else []
  if id: item=c.execute("""SELECT id,title,category,description,photo IS NOT NULL AS has_photo,
                                  model_filename FROM gallery WHERE id=%s""",(id,)).fetchone()
 return page("Galerie",GALLERY_FORM,heading="Modifier la réalisation" if id else "Nouvelle réalisation",
             item=item,photos=photos,csrf=csrfinput(),
             main_photo=0 if item and item["has_photo"] else (photos[0]["id"] if photos else 0))
@app.post("/admin/galerie/<int:gallery_id>/associer-automatiquement")
@admin_required
def fjord_auto_associate_gallery(gallery_id):
 verify()
 with db() as c:
  exists=c.execute("SELECT 1 FROM gallery WHERE id=%s",(gallery_id,)).fetchone()
  if not exists:abort(404)
  count,total=fjord_gallery_fill_missing_links(c,gallery_id)
 flash("⚡ "+str(count)+" association(s) trouvée(s) sur "+str(total)+" photo(s) sans modèle. Les autres nécessitent un choix manuel.")
 return redirect("/admin/edit/"+str(gallery_id))

@app.post("/admin/photo/delete/<int:id>")
@admin_required
def remove_photo(id):
 verify()
 with db() as c:r=c.execute("DELETE FROM gallery_photos WHERE id=%s RETURNING gallery_id",(id,)).fetchone()
 if not r:abort(404)
 return redirect("/admin/edit/"+str(r["gallery_id"]))
@app.post("/admin/galerie/photo/<int:photo_id>/modele")
@admin_required
def fjord_assign_model_to_photo(photo_id):
 verify()
 filename,data=fjord_gallery_model_upload(request.files.get("model"))
 if not data:abort(400,description="Choisissez un STL ou 3MF.")
 with db() as c:
  row=c.execute("""UPDATE gallery_photos SET model_filename=%s,model_data=%s
                   WHERE id=%s RETURNING gallery_id""",
                (filename,data,photo_id)).fetchone()
 if not row:abort(404)
 return redirect("/admin/edit/"+str(row["gallery_id"]))

@app.get("/admin/gallery/model/<int:gallery_id>")
@admin_required
def fjord_private_gallery_model(gallery_id):
 raw=request.args.get("photo","0")
 if not raw.isdigit() or len(raw)>18:abort(400)
 with db() as c:asset=fjord_gallery_asset(c,gallery_id,int(raw))
 if not asset or not asset["model_data"]:abort(404)
 return send_file(io.BytesIO(asset["model_data"]),mimetype="application/octet-stream",
                  as_attachment=True,download_name=asset["model_filename"],
                  max_age=0,conditional=False),200,{
                   "Cache-Control":"no-store, private",
                   "X-Robots-Tag":"noindex, nofollow",
                   "X-Content-Type-Options":"nosniff",
                   "X-Fjord-Model-Name":asset["model_filename"]}

@app.get("/galerie/<int:gallery_id>/modele")
def fjord_public_gallery_model(gallery_id):
 raw=request.args.get("photo","0")
 if not raw.isdigit() or len(raw)>18:abort(400)
 with db() as c:asset=fjord_gallery_asset(c,gallery_id,int(raw))
 if not asset or not asset["model_data"]:abort(404)
 return send_file(io.BytesIO(asset["model_data"]),mimetype="application/octet-stream",
                  as_attachment=True,download_name=asset["model_filename"],
                  max_age=0,conditional=False),200,{
                   "Cache-Control":"no-store",
                   "X-Robots-Tag":"noindex, nofollow",
                   "X-Content-Type-Options":"nosniff",
                   "X-Fjord-Model-Name":asset["model_filename"]}

@app.route("/admin/inspirations",methods=["GET"])
@admin_required
def fjord_admin_inspirations():
 with db() as c:
  rows=c.execute("SELECT source,model_filename,rights_confirmed FROM fjord_inspiration_models").fetchall()
 linked={row["source"]:row for row in rows}
 items=[{"index":i,**idea,"model":linked.get(idea["source"])}
        for i,idea in enumerate(FJORD_INSPIRATIONS)]
 return page("Modèles du diaporama",'''<section class="fjord-inspiration-admin">
 <p><a href="/admin">← Retour à l'administration</a></p>
 <h1>Les 50 inspirations et leurs modèles 3D</h1>
 <p>Associez uniquement des STL/3MF que vous êtes autorisé à reproduire. Les photos Wikimedia sont des références visuelles et leurs licences ne donnent pas automatiquement les droits sur les pièces.</p>
 <p>{{linked_count}} modèle(s) associé(s) sur {{items|length}} inspirations.</p>
 <div class="fjord-inspiration-admin-grid">{% for item in items %}
 <article><img src="{{item.image}}" loading="lazy" alt="{{item.title}}" referrerpolicy="no-referrer">
 <h2>#{{item.index+1}} {{item.title}}</h2><p>Photo : <a href="{{item.source}}" target="_blank" rel="noopener noreferrer">{{item.author}}</a> · {{item.license}}</p>
 {% if item.model %}<p>✓ {{item.model.model_filename}}</p>
 <a href="/admin/inspirations/{{item.index}}/modele">Télécharger le modèle</a> ·
 <a href="/admin/atelier-3d?inspiration={{item.index}}">🖨️ Ouvrir dans l'Atelier</a>
 {% else %}<p>⚠ Aucun fichier STL/3MF associé.</p>{% endif %}
 <form method="post" enctype="multipart/form-data" action="/admin/inspirations/{{item.index}}/modele">
 {{csrf|safe}}<label>Modèle STL/3MF<input type="file" name="model" accept=".stl,.3mf" required></label>
 <label class="fjord-rights-check"><input type="checkbox" name="rights_ok" value="yes" required> Je confirme avoir les droits nécessaires pour utiliser et reproduire ce modèle.</label>
 <button type="submit">{{'Remplacer le modèle' if item.model else 'Associer le modèle'}}</button></form>
 </article>{% endfor %}</div>
 </section>''',items=items,linked_count=len(linked),csrf=csrfinput())

@app.route("/admin/inspirations/<int:index>/modele",methods=["GET","POST"])
@admin_required
def fjord_admin_inspiration_model(index):
 idea=fjord_inspiration_by_index(index)
 if not idea:abort(404)
 if request.method=="POST":
  verify()
  if request.form.get("rights_ok")!="yes":abort(400,description="Confirmation des droits requise.")
  name,data=fjord_gallery_model_upload(request.files.get("model"))
  if not data:abort(400)
  with db() as c:
   c.execute("""INSERT INTO fjord_inspiration_models(source,model_filename,model_data,rights_confirmed)
                VALUES(%s,%s,%s,TRUE)
                ON CONFLICT(source) DO UPDATE SET
                model_filename=EXCLUDED.model_filename,model_data=EXCLUDED.model_data,
                rights_confirmed=TRUE,updated=NOW()""",(idea["source"],name,data))
  return redirect("/admin/inspirations")
 with db() as c:row=fjord_inspiration_model(c,idea)
 if not row or not row["rights_confirmed"]:abort(404)
 return send_file(io.BytesIO(row["model_data"]),mimetype="application/octet-stream",
                  as_attachment=True,download_name=row["model_filename"],
                  max_age=0,conditional=False),200,{
                   "Cache-Control":"no-store, private",
                   "X-Robots-Tag":"noindex, nofollow",
                   "X-Content-Type-Options":"nosniff",
                   "X-Fjord-Model-Name":row["model_filename"]}

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
# Public business-information pages for payment-provider onboarding.
# Describe actual site contact and ordering workflows; do not promise an
# unsupported refund or data-deletion process.
@app.get("/assistance")
def fjord_customer_support():
 return page("Assistance clientèle", """<section class="card" style="max-width:850px;margin:24px auto;padding:24px">
 <h1>Service à la clientèle</h1><p>Les Impressions du Fjord — impression 3D sur mesure à Saguenay, Québec.</p>
 <p>Pour toute question concernant une soumission, une commande, un paiement, une livraison ou une demande de remboursement, communiquez avec nous :</p>
 <p><a href="mailto:lesimpressionsdufjord@gmail.com">lesimpressionsdufjord@gmail.com</a> · <a href="/contact">Formulaire de contact</a></p>
 <p>Veuillez indiquer votre numéro de soumission ou de commande si vous en avez un. Ne transmettez jamais votre numéro complet de carte bancaire dans un message.</p>
 </section>""")

@app.get("/politique-confidentialite")
def fjord_privacy_policy():
 return page("Politique de confidentialité", """<section class="card" style="max-width:850px;margin:24px auto;padding:24px">
 <h1>Politique de confidentialité</h1><p><strong>Les Impressions du Fjord</strong> — mise à jour : 1er novembre 2026.</p>
 <h2>Renseignements recueillis</h2><p>Lorsque vous nous contactez, demandez une soumission ou passez une commande, nous pouvons recueillir votre nom, vos coordonnées, votre demande, les fichiers 3D ou images que vous transmettez, ainsi que les informations nécessaires au suivi de votre commande et de votre paiement.</p>
 <h2>Utilisation</h2><p>Ces renseignements servent à répondre aux demandes, évaluer et fabriquer les créations, établir les soumissions, traiter les commandes, fournir l'assistance et tenir les dossiers nécessaires aux activités de l'entreprise.</p>
 <h2>Partage et paiement</h2><p>Les informations nécessaires au paiement peuvent être transmises au prestataire de paiement, notamment Stripe. Les renseignements peuvent également être communiqués à nos fournisseurs techniques d'hébergement et de messagerie dans la mesure nécessaire au fonctionnement du service, ou lorsque la loi l'exige. Les données de carte sont saisies sur les interfaces sécurisées du prestataire de paiement plutôt que dans notre formulaire de soumission.</p>
 <h2>Protection et conservation</h2><p>Nous limitons l'accès aux informations de gestion aux personnes autorisées et utilisons des connexions HTTPS pour le site. Nous conservons les renseignements pendant la durée nécessaire à la gestion des demandes et commandes et aux obligations légales applicables. Aucun système informatique ne garantit une sécurité absolue.</p>
 <h2>Vos demandes</h2><p>Pour demander l'accès à vos renseignements, leur correction ou leur suppression lorsque permise par la loi, écrivez à <a href="mailto:lesimpressionsdufjord@gmail.com">lesimpressionsdufjord@gmail.com</a>, utilisez notre <a href="/contact">formulaire de contact</a>.</p>
 <p>Cette politique concerne le site et les services de Les Impressions du Fjord. Pour les paiements, consultez également les politiques de confidentialité du prestataire de paiement.</p>
 </section>""")

@app.get("/conditions-utilisation")
def fjord_terms():
 return page("Conditions d’utilisation", """<section class="card" style="max-width:850px;margin:24px auto;padding:24px">
 <h1>Conditions d'utilisation</h1><p><strong>Les Impressions du Fjord</strong> — mise à jour : 1er novembre 2026.</p>
 <h2>Services et soumissions</h2><p>Nous proposons la conception et l'impression 3D sur mesure. Les prix, matériaux, dimensions, délais et modalités de livraison sont précisés dans la soumission ou lors de la confirmation de commande. Une estimation en ligne ne constitue pas une commande acceptée.</p>
 <h2>Fichiers et créations</h2><p>En transmettant un modèle ou une image, vous confirmez avoir le droit de nous demander de le reproduire ou de le modifier. Nous pouvons refuser les projets incompatibles avec nos capacités ou nos obligations légales.</p>
 <h2>Fabrication et variations</h2><p>L'impression 3D peut présenter de légères variations d'aspect, de texture et de dimensions selon le matériau et le procédé. Les usages critiques pour la sécurité doivent être expressément discutés et validés avant commande.</p>
 <h2>Paiement, annulation et remboursement</h2><p>Les modalités de paiement sont communiquées lors de la commande. Pour annuler ou demander un remboursement, contactez-nous rapidement. Chaque demande est examinée selon l'avancement de la fabrication, la nature personnalisée du produit et les droits prévus par les lois applicables du Québec. Aucune disposition ne limite vos droits légaux.</p>
 <h2>Livraison et assistance</h2><p>Les modalités de remise, d'expédition et les frais applicables sont confirmés avec le client. Pour une question ou une réclamation, écrivez à <a href="mailto:lesimpressionsdufjord@gmail.com">lesimpressionsdufjord@gmail.com</a> ou consultez notre <a href="/assistance">page d'assistance</a>.</p>
 </section>""")

@app.after_request
def fjord_public_security_headers(response):
 """Protect customer forms without breaking the existing Atelier 3D scripts."""
 response.headers.setdefault("X-Content-Type-Options","nosniff")
 response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
 response.headers.setdefault("X-Frame-Options","SAMEORIGIN")
 path=request.path.rstrip("/") or "/"
 sensitive=("/soumission","/contact","/suivi","/voir-mon-impression")
 if path in sensitive or path.startswith(("/admin","/payer","/stripe","/api/")):
  response.headers["Cache-Control"]="no-store, private"
 return response

@app.get("/favicon.ico")
def fjord_favicon():
 return redirect("/identite/logo",code=302)

@app.get("/health")
def health():return {"ok":True}

@app.get("/health/ready")
def fjord_health_ready():
 """Read-only DB check, no connection string, secrets or customer data disclosed."""
 try:
  with db() as connection:
   row=connection.execute("SELECT 1 AS ready").fetchone()
  if not row or row["ready"]!=1:
   raise RuntimeError("Database not ready")
 except Exception:
  app.logger.warning("Fjord readiness: database unavailable")
  return jsonify(ok=False,service="Les Impressions du Fjord",database="unavailable"),503,{"Cache-Control":"no-store"}
 preview=os.environ.get("FJORD_PREVIEW_MODE")=="1"
 from urllib.parse import urlsplit
 database_name=urlsplit(DB).path.lstrip("/").lower()
 return jsonify(ok=True,service="Les Impressions du Fjord",
                mode="preview" if preview else "production",
                temporary_preview_database=database_name.startswith("fjord_render_apercu")),200,{"Cache-Control":"no-store"}

register_seo_routes(app,db)

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
_fjord_install_completion_tracking()

# Per-quote Stripe Checkout and verified payment notifications.
from fjord_stripe import register_stripe_payments
register_stripe_payments(app,db)

# Secure, admin-only archive of the owner\'s Bambu Studio preset bundles.
from bambu_presets import register_bambu_preset_library
register_bambu_preset_library(app,db,admin_required,verify,csrfinput,page)

# Private X2D print console (OctoEverywhere capabilities verified at runtime).
from fjord_printer import register_printer_admin
register_printer_admin(app,admin_required,verify,csrfinput,page,db=db)
from fjord_bambu_connect import register_bridge as register_bambu_connect_bridge
register_bambu_connect_bridge(app,db,admin_required,verify,csrfinput,page)
