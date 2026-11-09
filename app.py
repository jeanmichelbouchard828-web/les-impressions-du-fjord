Warning: truncated output (original token count: 59641)
Total output lines: 2717

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
from fjord_makerworld import html_fragment as fjord_makerworld_html
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
  c.execute("""CREATE TABLE IF NOT EXISTS fjord_makerworld_slides(id BIGSERIAL PRIMARY KEY,title TEXT NOT NULL,source_url TEXT NOT NULL,image BYTEA NOT NULL,image_mime TEXT NOT NULL,model_filename TEXT NOT NULL,model_data BYTEA NOT NULL,rights_confirmed BOOLEAN NOT NULL DEFAULT FALSE,created TIMESTAMPTZ DEFAULT NOW())""")
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
.site-header nav a.nav-ready-cta{background:linear-gradient(110deg,#0b4a6d,#087fab);border-color:#4ec8ee;color:#f3fcff;font-weight:900;box-shadow:0 4px 14px #007cae33}
.site-header nav a.nav-ready-cta:hover,.site-header nav a.nav-ready-cta[aria-current=page]{background:linear-gradient(110deg,#10658d,#12a0ce);border-color:#9deeff;color:#fff}
.site-header nav a.nav-atelier-cta{background:linear-gradient(110deg,#79e7ff,#28bce6);border-color:#9cf0ff;color:#05293d;font-weight:900;box-shadow:0 5px 18px #00ace344}
.site-header nav a.nav-atelier-cta:hover,.site-header nav a.nav-atelier-cta[aria-current=page]{background:linear-gradient(110deg,#a0efff,#51c9eb);border-color:#fff;color:#05293d}

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
body.light .site-header nav a.nav-atelier-cta{background:linear-gradient(110deg,#079acb,#087eaf);border-color:#087eaf;color:#fff}body.light .site-header nav a.nav-atelier-cta:hover,body.light .site-header nav a.nav-atelier-cta[aria-current=page]{background:linear-gradient(110deg,#17add8,#087eaf);border-color:#066487;color:#fff}
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
</style><link rel="stylesheet" href="/static/fjord_sitewide.css?v=20261109-quote-fit2">{% if request.path == '/' %}<link rel="stylesheet" href="/static/fjord_inspirations.css?v=20261108-ideas50">{% endif %}</head><body class="{{ 'fjord-admin' if request.path.startswith('/admin') else 'fjord-public' }}{{ ' fjord-preview' if fjord_is_preview else '' }}"><header class="site-header"><a class="brand" href="/" aria-label="Les Impressions du Fjord, accueil"><img src="/identite/logo" alt="" style="width:52px;height:52px;object-fit:cover" onerror="this.style.display='none'"><span class="brand-main">LES IMPRESSIONS</span><span class="fjord-brand-blue brand-blue">DU FJORD</span><small class="fjord-brand-tagline">IMPRESSION 3D SUR MESURE</small></a><button class="site-nav-toggle" type="button" id="fjordNavToggle" aria-controls="fjordPrimaryNav" aria-expanded="false" aria-label="Ouvrir le menu">☰ <span>Menu</span></button>{% if request.path.startswith('/admin') and session.get('admin_token') %}
<nav id="fjordPrimaryNav" class="admin-primary-nav" aria-label="Navigation administrateur"><a href="/admin">🏠 Tableau de bord</a><a href="/admin/soumissions-pro">📄 Soumissions</a><a href="/admin/demandes">📥 Demandes</a><a href="/admin/atelier-imprimer">🖨️ Imprimer</a><a href="/admin/atelier-3d">🧊 Atelier 3D</a><a href="/admin/modeles">📚 Modèles</a></nav>
{% else %}
<nav id="fjordPrimaryNav" aria-label="Navigation principale"><a class="nav-ready-cta" href="/galerie?prets=1">Prêts à imprimer</a><a href="/galerie">Galerie</a><a href="/#services">Services</a><a href="/soumission">Soumission</a><a href="/voir-mon-impression">Suivi client</a><a href="/contact">Contact</a><a class="nav-atelier-cta" href="/atelier-3d" data-fjm-en="3D Workshop">🧊 Atelier 3D</a>{% if session.get('admin_token') %}<a href="/admin">Administration</a>{% endif %}</nav>
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
 image=meta["public_origin"]+custom_image if isinstance(custom_im…29641 tokens truncated… les créations, établir les soumissions, traiter les commandes, fournir l'assistance et tenir les dossiers nécessaires aux activités de l'entreprise.</p>
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


@app.post("/admin/inspirations/makerworld")
@admin_required
def fjord_admin_add_makerworld_slide():
 verify()
 title=request.form.get("title","").strip()
 source_url=request.form.get("source_url","").strip()
 try:
  parsed=urlparse(source_url)
  if not title or len(title)>120 or parsed.scheme!="https" or parsed.hostname not in ("makerworld.com","www.makerworld.com") or not parsed.path.startswith(("/en/models/","/fr/models/","/models/")) or parsed.username:
   raise ValueError
  source_url=parsed._replace(fragment="",query="").geturl()
 except (TypeError,ValueError):
  abort(400,description="Vérifie le nom et le lien public MakerWorld.")
 if request.form.get("rights_ok")!="yes":abort(400,description="Confirmation des droits requise.")
 images=image_uploads([request.files.get("image")])
 if not images:abort(400,description="Ajoute la photo du modèle.")
 filename,model_data=fjord_gallery_model_upload(request.files.get("model"))
 if not filename or not filename.lower().endswith(".3mf"):abort(400,description="Le fichier MakerWorld doit être un 3MF.")
 image_data,image_mime=images[0]
 with db() as c:
  c.execute("""INSERT INTO fjord_makerworld_slides(title,source_url,image,image_mime,model_filename,model_data,rights_confirmed)
               VALUES(%s,%s,%s,%s,%s,%s,TRUE)""",(title,source_url,image_data,image_mime,filename,model_data))
 return redirect("/admin/inspirations")

@app.get("/inspirations/makerworld/<int:slide_id>/photo")
def fjord_makerworld_slide_photo(slide_id):
 with db() as c:slide=c.execute("SELECT image,image_mime FROM fjord_makerworld_slides WHERE id=%s",(slide_id,)).fetchone()
 if not slide:abort(404)
 return send_file(io.BytesIO(slide["image"]),mimetype=slide["image_mime"],max_age=3600)

@app.get("/inspirations/makerworld/<int:slide_id>/modele")
def fjord_public_makerworld_model(slide_id):
 with db() as c:
  slide=c.execute("""SELECT model_filename,model_data FROM fjord_makerworld_slides
    WHERE id=%s AND rights_confirmed=TRUE AND octet_length(model_data)>0""",(slide_id,)).fetchone()
 if not slide:abort(404)
 return send_file(io.BytesIO(slide["model_data"]),mimetype="application/octet-stream",
                  as_attachment=True,download_name=slide["model_filename"],
                  max_age=0,conditional=False),200,{
                   "Cache-Control":"no-store",
                   "X-Robots-Tag":"noindex, nofollow",
                   "X-Content-Type-Options":"nosniff",
                   "X-Fjord-Model-Name":slide["model_filename"]}

@app.get("/admin/inspirations/makerworld/<int:slide_id>/modele")
@admin_required
def fjord_admin_makerworld_model(slide_id):
 with db() as c:slide=c.execute("SELECT model_filename,model_data FROM fjord_makerworld_slides WHERE id=%s",(slide_id,)).fetchone()
 if not slide:abort(404)
 return send_file(io.BytesIO(slide["model_data"]),mimetype="application/octet-stream",as_attachment=True,download_name=slide["model_filename"],max_age=0,conditional=False)

@app.post("/admin/inspirations/makerworld/<int:slide_id>/supprimer")
@admin_required
def fjord_admin_delete_makerworld_slide(slide_id):
 verify()
 with db() as c:c.execute("DELETE FROM fjord_makerworld_slides WHERE id=%s",(slide_id,))
 return redirect("/admin/inspirations")

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
