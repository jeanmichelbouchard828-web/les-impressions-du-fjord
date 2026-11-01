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
# Compteur de visiteurs uniques (navigateur, pas nombre de pages vues).
# Aucun nom, adresse IP ou agent utilisateur n'est enregistré.
with db() as c:
 c.execute("CREATE TABLE IF NOT EXISTS site_visitors (visitor_hash TEXT PRIMARY KEY, first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW())")

@app.before_request
def fjord_track_visit():
 if request.method != "GET" or request.path.startswith(("/admin","/api","/static","/atelier","/favicon","/gallery-photo","/galerie/photo")):
  return
 from flask import g
 token=request.cookies.get("fjord_visitor")
 if not token or not re.fullmatch(r"[a-f0-9]{32}",token):
  token=secrets.token_hex(16)
  g.fjord_new_visitor_token=token
 try:
  digest=hashlib.sha256(token.encode()).hexdigest()
  with db() as c:
   c.execute("INSERT INTO site_visitors(visitor_hash) VALUES (%s) ON CONFLICT DO NOTHING",(digest,))
 except Exception:
  app.logger.exception("Compteur de visiteurs indisponible")

@app.after_request
def fjord_set_visitor_cookie(response):
 from flask import g
 token=getattr(g,"fjord_new_visitor_token",None)
 if token:
  response.set_cookie("fjord_visitor",token,max_age=365*24*3600,secure=True,httponly=True,samesite="Lax")
 return response

@app.context_processor
def fjord_visitor_count():
 try:
  with db() as c:
   count=c.execute("SELECT COUNT(*) AS n FROM site_visitors").fetchone()["n"]
  return {"fjord_visitors":count}
 except Exception:
  return {"fjord_visitors":None}

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
header nav a[href="/atelier-3d"]{background:linear-gradient(125deg,#006db8,#159ce1);color:#fff;border:1px solid #65d8ff;box-shadow:0 0 15px #08a9ff44}
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
/* Maquette Fjord : bandeau pleine largeur, navigation latérale et contenu */
header{position:relative;z-index:12;width:100%;box-sizing:border-box}
.fjord-side-nav{position:fixed;z-index:10;left:0;top:118px;bottom:0;width:224px;box-sizing:border-box;padding:18px 10px 20px;background:linear-gradient(180deg,#031225 0%,#061b32 65%,#031020 100%);border-right:1px solid #2574a9;box-shadow:6px 0 25px #0005;display:flex;flex-direction:column;justify-content:space-between;overflow-y:auto}
.fjord-side-menu{display:flex;flex-direction:column;gap:5px}
.fjord-side-menu a{display:flex;align-items:center;gap:13px;padding:11px 13px;border-radius:9px;text-decoration:none;color:#f0f8ff;font-weight:750;font-size:15px;transition:background .16s,box-shadow .16s}
.fjord-side-menu a:hover,.fjord-side-menu a:focus-visible{background:linear-gradient(100deg,#0866a5,#0d8cce);box-shadow:inset 0 0 0 1px #39c5ff}
.fjord-side-menu a[href="/atelier-3d"]{border-left:3px solid #30c6ff}
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
BASE="""<!doctype html><html lang="fr-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{{meta_description}}"><meta property="og:title" content="{{title}} | Les Impressions du Fjord"><meta property="og:description" content="{{meta_description}}"><meta property="og:type" content="website"><title>{{title}} | Les Impressions du Fjord</title>"""+STYLE+GLOBAL_FJORD_THEME+FJORD_SITE_PREMIUM+FJORD_FULL_BRANDING+FJORD_LAYOUT_SIDEBAR+FJORD_FINISHING+FJORD_VISITOR_STYLE+"""<style>
@media(max-width:650px){
 header nav{width:100%;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
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
.public-print-list{display:grid;gap:10px;margin-top:16px}.public-print-job{padding:12px;border-radius:10px;background:#0c1c2caa;display:flex;align-items:center;gap:12px;flex-wrap:wrap}.public-print-job .tracking-progress{flex:1 1 100%;margin:0}.public-print-job span{margin-left:auto}.tracking-billboard{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;margin:10px 0 32px;padding:26px;border:1px solid #4e9cc5;border-radius:18px;background:linear-gradient(120deg,#173a54,#0c2133)}.tracking-billboard h2{margin:8px 0;font-size:clamp(23px,3vw,33px)}.tracking-billboard p{color:#d6e6f1}.tracking-panel{max-width:640px;margin:20px auto}.tracking-result{margin-top:25px;padding:22px;border:1px solid #4e9cc5;border-radius:12px}.tracking-progress{height:16px;border-radius:12px;background:#273b50;overflow:hidden}.tracking-progress span{display:block;height:100%;background:#43b9ec}body.light .tracking-billboard{background:#e5f3fc;color:#173a54}body.light .tracking-billboard p{color:#34536c}</style></head><body><header><a class="brand" href="/"><img src="/identite/logo" alt="Logo Les Impressions du Fjord" style="width:64px;height:64px;object-fit:contain;vertical-align:middle;margin-right:12px" onerror="this.style.display='none'">LES IMPRESSIONS <span class="fjord-brand-blue">DU FJORD</span><small class="fjord-brand-tagline">IMPRESSION 3D SUR MESURE</small></a><nav><a href="/#services">Services</a><a href="/galerie">Galerie</a><a href="/soumission">Soumission</a><a href="/#nous-joindre">Nous joindre</a><a href="/contact">Formulaire</a><a href="/atelier-3d">Atelier 3D</a><a href="/admin">Administration</a></nav><div class="pref-controls"><select id="fjord-lang" aria-label="Langue / Language"><option value="fr">🇨🇦 Français</option><option value="en">🇨🇦 English</option></select><select id="fjord-theme" aria-label="Thème / Theme"><option value="dark">🌙 Sombre</option><option value="light">☀️ Clair</option></select></div></header><aside class="fjord-side-nav" aria-label="Navigation principale"><div class="fjord-side-menu"><a href="/">⌂ <span>Accueil</span></a><a href="/admin">▤ <span>Administration</span></a><a href="/galerie">▧ <span>Galerie</span></a><a href="/atelier-3d">⬡ <span>Atelier 3D</span></a><a href="/#services">⚙ <span>Services</span></a><a href="/soumission">▣ <span>Soumission</span></a><a href="/contact">✉ <span>Contact</span></a><hr><span class="fjord-side-label">Liens utiles</span><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">ⓕ <span>Facebook</span></a><a href="https://maps.app.goo.gl/9Qryi3nbK9nBuXts8?g_st=ac" target="_blank" rel="noopener noreferrer">⌖ <span>Google Maps</span></a></div><div class="fjord-side-deco" aria-hidden="true">LES IMPRESSIONS<br><b>DU FJORD</b><small>IMPRESSION 3D</small></div></aside><main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="alert">{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}<section id="nous-joindre" class="contact-section"><h2>Contactez-nous</h2><p>Une idée de création 3D? Écrivez-nous sur Facebook ou appelez-nous!</p><div class="contact-actions"><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">ⓕ Notre page Facebook</a><a href="https://www.facebook.com/share/19oRAWKxCk/" target="_blank" rel="noopener noreferrer">💬 Nous écrire sur Facebook</a><a href="tel:+15819980831">☎ 581-998-0831</a><a href="https://maps.app.goo.gl/9Qryi3nbK9nBuXts8?g_st=ac" target="_blank" rel="noopener noreferrer">📍 Nous trouver sur Google Maps</a></div><p class="muted small">Pour Messenger, ouvrez notre page Facebook et choisissez « Envoyer un message ».</p></section></main><footer><div>© 2026 Les Impressions du Fjord · Saguenay, Québec</div><div class="referral-footer"><a href="/bons-plans/starlink">🛰️ Notre bon plan Internet : parrainage Starlink</a><span>Un partage personnel, indépendant de nos services d'impression 3D.</span></div><div class="fjord-visitor-counter" aria-label="Nombre de visiteurs uniques">👀 <strong>{{ '{:,}'.format(fjord_visitors).replace(',', ' ') if fjord_visitors is not none else '—' }}</strong> visiteurs uniques</div></footer><script>
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
  return Response(raw,mimetype="image/png",headers={"Cache-Control":"public, max-age=86400","X-Content-Type-Options":"nosniff"})
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
 def norm(v):
  return str(v or "").replace(chr(92),"/").split("/")[-1].rsplit(".",1)[0].strip().casefold()
 expected,actual=norm(configured),norm(reported)
 if not expected or not actual:return False
 if expected==actual:return True
 # Permettre uniquement un préfixe de soumission explicite FJ-00002_.
 # Ne jamais retirer un préfixe arbitraire qui pourrait créer une collision.
 match=re.fullmatch(r"fj-\d{5}_(.+)",expected)
 return bool(match and match.group(1)==actual)

def _sync_octo_progress():
 """Persist a confirmed live OctoEverywhere job against one unambiguous quote."""
 live=_octo_live_status()
 result={"connected":live is not None,"reason":_octo_cache["reason"],
         "state":live["state"] if live else None,"filename":live["filename"] if live else "",
         "matched":False,"number":None,"progress":None,"updated":False}
 if not live or live["state"] not in ("printing","warmingup","resuming","paused","complete"):
  return result
 filename=live["filename"]
 if not filename or (live["progress"] is None and live["state"]!="complete"):
  result["reason"]="OctoEverywhere ne donne pas de nom de travail ou de pourcentage."
  return result
 reported=str(filename).replace(chr(92),"/").split("/")[-1]
 raw=re.sub(r"(?i)(?:\.gcode)?\.(?:3mf|gcode|stl)$","",reported).casefold()
 match=re.match(r"^(fj-[0-9]{1,8})(?:[_\s-]|$)",raw)
 with db() as c:
  quotes=c.execute("""SELECT id,public_number,printer_job_name,production_status,production_progress
                      FROM private_quotes ORDER BY id DESC LIMIT 300""").fetchall()
  candidates=[]
  if match:
   number=match.group(1).upper()
   candidates=[q for q in quotes if (q["public_number"] or "FJ-{:05d}".format(q["id"]))==number]
  else:
   candidates=[q for q in quotes if _octo_job_matches(q["printer_job_name"],filename)]
  if len(candidates)!=1:
   result["reason"]=("Aucune soumission associée au nom du travail de l'imprimante."
                     if not candidates else "Plusieurs soumissions utilisent le même nom de travail.")
   return result
  q=candidates[0]
  number=q["public_number"] or "FJ-{:05d}".format(q["id"])
  progress=100 if live["state"]=="complete" else live["progress"]
  result.update({"matched":True,"id":q["id"],"status":"Terminée" if live["state"]=="complete" else "En production","number":number,
                 "progress":max(progress,int(q["production_progress"] or 0)),
                 "reason":"Progression reçue pour "+number+"."})
  if q["production_status"]!="Terminée":
   changed=c.execute("""UPDATE private_quotes SET
                 production_progress=GREATEST(production_progress,%s),
                 production_status=CASE WHEN %s=100 THEN 'Terminée' ELSE 'En production' END
                 WHERE id=%s AND production_status!='Terminée' RETURNING id""",
                 (progress,progress,q["id"])).fetchone()
   result["updated"]=bool(changed)
 return result

@app.get("/api/production-publique")
def public_production():
 # Uniquement les commandes autorisées; aucun identifiant ou renseignement client.
 with db() as c:
  rows=c.execute("SELECT status,progress FROM requests WHERE kind='Soumission' AND public_progress=TRUE AND status IN ('Demande reçue','Soumission envoyée','En impression','Terminée') ORDER BY id DESC LIMIT 100").fetchall()
 # Soumissions PRO : statut uniquement, sans données client ni montant.
 _sync_octo_progress()
 with db() as c:
  quotes=c.execute("""SELECT q.id,q.public_number,q.production_status,q.production_progress,q.printer_job_name,q.payment_status,
      EXISTS(SELECT 1 FROM fjord_quote_acceptances a WHERE a.quote_id=q.id) AS accepted
      FROM private_quotes q ORDER BY q.id DESC LIMIT 150""").fetchall()
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

@app.get("/")
def home():
 # Seules les impressions expressément autorisées sont affichées, sans identifiants client.
 with db() as c:
  public_jobs=c.execute("SELECT progress FROM requests WHERE kind='Soumission' AND status='En impression' AND public_progress=TRUE ORDER BY id DESC LIMIT 4").fetchall()
 return page("Accueil",'''<div class="hero"><div class="eyebrow">Création · Précision · Innovation</div><h1>Vos idées prennent forme.</h1><p>Impression 3D sur mesure au Saguenay.</p><div class="atelier-feature"><div class="atelier-feature-label">✦ Votre atelier 3D en ligne</div><h2>Imaginez. Créez. Personnalisez.</h2><p>Concevez votre objet en 3D, ajustez ses dimensions et préparez votre création pour une impression sur mesure.</p><a class="btn atelier-cta" href="/atelier-3d">🎨 Créez votre propre création</a><p class="atelier-feature-note">Atelier gratuit · Français / English · Sombre / Clair</p></div><a class="btn secondary-btn" href="/soumission">Demander une soumission</a></div><section class="tracking-billboard fjord-board" aria-label="Tableau interactif de production"><div class="fjord-board-inner"><div class="fjord-board-heading"><strong>LES IMPRESSIONS DU FJORD</strong><span class="fjord-board-badge">Production</span></div><h2>Suivi des impressions 3D</h2><p>Aperçu interactif du tableau de production</p><div id="fjordProductionLive" role="tabpanel" aria-live="polite"><p>Chargement du tableau de production…</p></div><div class="fjord-board-footer"><p class="production-updated" id="fjordProductionUpdated">Mise à jour automatique toutes les 30 secondes.</p><div class="fjord-board-actions"><a class="btn fjord-board-see" href="/voir-mon-impression">👁️ Voir mon impression</a><p class="fjord-board-private">Visionnement privé de votre impression 3D.</p></div></div></div></section><style>
.fjord-board{display:block;padding:24px;background:#0b1725;border-color:#3a6076}.fjord-board-inner{width:100%}.fjord-board-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;font-size:18px}.fjord-board-badge{background:#103c27;color:#50d78a;border-radius:30px;padding:5px 12px;font-size:14px}.fjord-board h2{font-size:clamp(24px,3vw,30px);margin:22px 0 6px}.fjord-board-tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:20px 0}.fjord-board-tab{background:transparent;border:0;border-radius:30px;color:#c4d5e0;font:inherit;font-weight:700;padding:12px 5px;cursor:pointer}.fjord-board-tab.active{background:#304151;color:white}.fjord-board-tab:focus-visible{outline:2px solid #64d9ff;outline-offset:2px}.fjord-board .public-print-list{margin:0}.fjord-board .public-print-job{background:#10283b;display:block}.fjord-board .public-print-job strong{display:block}.fjord-board .public-print-job span{display:block;margin:8px 0}.fjord-board .tracking-progress{height:12px}.fjord-board .tracking-progress span{margin:0;background:#24b46a}.fjord-board-see{display:inline-block;margin-top:12px}.fjord-board-private{font-size:13px;margin:8px 0 0}.fjord-board .production-updated{font-size:13px;margin:14px 0 0}@media(max-width:480px){.fjord-board{padding:16px}.fjord-board-tab{font-size:13px;padding:10px 3px}}
.fjord-board{padding:20px 24px}.fjord-board h2{margin:12px 0 3px}.fjord-board-inner>p{margin:6px 0 12px}.fjord-board-footer{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:12px;flex-wrap:wrap}.fjord-board-actions{display:flex;align-items:center;gap:12px;margin-left:auto}.fjord-board .fjord-board-see{margin:0;padding:10px 16px;font-size:14px;white-space:nowrap}.fjord-board .fjord-board-private{margin:0;max-width:185px;font-size:11px;line-height:1.3;color:#a9c3d4}.fjord-board .production-updated{margin:0}.fjord-public-table{display:grid;gap:5px}.fjord-public-row{display:grid;grid-template-columns:minmax(110px,1fr) minmax(150px,1.5fr) minmax(100px,1fr);gap:12px;align-items:center;padding:8px 12px;border:1px solid #37546a;border-radius:8px}.fjord-public-head{border:0;color:#c5d9e8}.fjord-public-progress{display:grid;gap:5px}.fjord-public-progress .tracking-progress{height:6px}@media(max-width:520px){.fjord-public-row{grid-template-columns:minmax(80px,1fr) minmax(110px,1.4fr) minmax(70px,1fr);gap:7px;padding:7px;font-size:12px}}
@media(max-width:600px){.fjord-board-actions{width:100%;justify-content:flex-end}.fjord-board .fjord-board-private{display:none}}
</style><script>
(function(){
 const root=document.getElementById("fjordProductionLive"),updated=document.getElementById("fjordProductionUpdated");
 let groups={print:[],wait:[],done:[]};
 function render(){
  root.replaceChildren();
  const all=[...groups.print,...groups.wait,...groups.done];
  if(!all.length){const p=document.createElement("p");p.textContent="Aucune soumission à afficher pour le moment.";root.append(p);return;}
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
  reqs=c.execute("SELECT id,kind,name,email,phone,material,description,filename,created,status,progress,live_enabled,live_url,public_progress FROM requests ORDER BY id DESC LIMIT 200").fetchall()
  gallery=c.execute("SELECT id,title,category FROM gallery ORDER BY id DESC").fetchall()
 return page("Administration",'''<h1>Tableau de bord</h1><div class="row"><a class="btn" href="/admin/modeles">📚 Mes modèles 3D</a><a class="btn" href="/admin/profils-bambu">⚙️ Mes profils Bambu</a><a class="btn" href="/admin/soumissions-pro">📄 Soumissions PRO</a><a class="btn" href="/admin/new">Ajouter une réalisation</a><form method="post" action="/admin/logout">{{csrf|safe}}<button>Déconnexion</button></form></div><h2>Demandes et commandes</h2><div class="grid">{% for r in reqs %}<article class="card"><div class="eyebrow">#{{r.id}} · {{r.kind}} · {{r.created.strftime('%Y-%m-%d')}}</div><h3>{{r.name}}</h3><p><a href="mailto:{{r.email}}">{{r.email}}</a> · {{r.phone or ''}}</p><p>Matériau : {{r.material or '—'}}</p><p style="white-space:pre-wrap">{{r.description}}</p>{% if r.filename %}<p><a href="/admin/file/{{r.id}}">Télécharger {{r.filename}}</a></p>{% if r.kind=='Soumission' %}<form method="post" action="/admin/modeles/import-demande/{{r.id}}">{{csrf|safe}}<button>📦 Importer le modèle et créer la soumission</button></form>{% endif %}{% elif r.kind=='Soumission' %}<p><a href="/admin/soumissions-pro?request_id={{r.id}}">📄 Préparer une soumission PRO</a></p>{% endif %}<form method="post" action="/admin/status/{{r.id}}">{{csrf|safe}}<label>Statut<select name="status">{% for s in statuses %}<option {% if s==r.status %}selected{% endif %}>{{s}}</option>{% endfor %}</select></label><label>Progression réelle (%)<input type="number" name="progress" min="0" max="100" value="{{r.progress if r.progress is not none else ''}}" placeholder="Non disponible"></label><label><input type="checkbox" name="public_progress" value="1" {% if r.public_progress %}checked{% endif %}> Afficher anonymement la progression sur l'accueil</label><label>Lien OctoEverywhere temporaire (oe.ink)<input type="url" name="live_url" maxlength="500" placeholder="https://oe.ink/l/..." value="{{r.live_url or ''}}"></label><label><input type="checkbox" name="live_enabled" value="1" {% if r.live_enabled %}checked{% endif %}> Autoriser la diffusion privée (à configurer)</label><button>Enregistrer</button></form></article>{% else %}<p>Aucune demande pour le moment.</p>{% endfor %}</div>''',reqs=reqs,gallery=gallery,statuses=STATUSES,csrf=csrfinput())
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

# Per-quote Stripe Checkout and verified payment notifications.
from fjord_stripe import register_stripe_payments
register_stripe_payments(app,db)

# Secure, admin-only archive of the owner\'s Bambu Studio preset bundles.
from bambu_presets import register_bambu_preset_library
register_bambu_preset_library(app,db,admin_required,verify,csrfinput,page)

# Private X2D print console (OctoEverywhere capabilities verified at runtime).
from fjord_printer import register_printer_admin
register_printer_admin(app,admin_required,verify,csrfinput,page,db=db)
