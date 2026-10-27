import os,io,re,hmac,time,uuid,hashlib,secrets,datetime,smtplib
from email.message import EmailMessage
from functools import wraps
from flask import Flask,request,redirect,render_template_string,session,abort,send_file,flash,url_for
import psycopg
from psycopg.rows import dict_row
from werkzeug.utils import secure_filename
app=Flask(__name__)
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
init()
STYLE="""<style>*{box-sizing:border-box}body{margin:0;background:#071321;color:#f2faff;font:16px system-ui,Arial}header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 5%;border-bottom:1px solid #2a4a62;background:#091a2b;flex-wrap:wrap}nav{display:flex;gap:15px;flex-wrap:wrap}a{color:#7fe4ff;text-decoration:none}.brand{font-weight:900;letter-spacing:.6px}main{max-width:1100px;margin:auto;padding:28px 20px 70px}.hero{padding:70px 0 90px;background:radial-gradient(ellipse at 80% 10%,#15618a77,transparent 60%)}h1{font-size:clamp(38px,7vw,78px);line-height:1.06;margin:15px 0}h2{font-size:30px}p{color:#c6d7e7;line-height:1.65}.eyebrow{color:#80dfff;letter-spacing:3px;text-transform:uppercase;font-size:13px;font-weight:bold}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}.card{background:#10283b;border:1px solid #2d526d;padding:22px;border-radius:16px;overflow:hidden}.card img{width:100%;height:220px;object-fit:cover;border-radius:10px}input,textarea,select{display:block;width:100%;padding:12px;margin:7px 0 17px;background:#081827;color:white;border:1px solid #47718b;border-radius:9px;font:inherit}label{display:block;font-weight:600}textarea{min-height:110px}button,.btn{display:inline-block;padding:13px 20px;border:0;border-radius:9px;background:#5ad7f5;color:#061b2a;font-weight:800;cursor:pointer;font:inherit;text-decoration:none}form{max-width:650px}.muted{color:#a9c3d3}.alert{padding:14px;background:#163e50;border-radius:9px;margin:15px 0}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.row form{display:inline}.small{font-size:13px}footer{padding:25px 5%;border-top:1px solid #294b62;color:#a9c3d3}@media(max-width:600px){.hero{padding:40px 0}header{align-items:flex-start}nav{font-size:14px}}</style>"""
BASE="""<!doctype html><html lang="fr-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Les Impressions du Fjord — impression 3D sur mesure au Saguenay."><title>{{title}} | Les Impressions du Fjord</title>"""+STYLE+"""</head><body><header><a class="brand" href="/">LES IMPRESSIONS DU FJORD</a><nav><a href="/#services">Services</a><a href="/#galerie">Galerie</a><a href="/soumission">Soumission</a><a href="/contact">Contact</a><a href="/admin">Administration</a></nav></header><main>{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="alert">{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}</main><footer>© 2026 Les Impressions du Fjord · Saguenay, Québec</footer></body></html>"""
def page(title,body,**kwargs):
 from flask import render_template_string
 return render_template_string(BASE,title=title,body=render_template_string(body,**kwargs))
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
@app.get("/")
def home():
 with db() as c:gallery=c.execute("SELECT id,title,category,description,photo IS NOT NULL AS has_photo FROM gallery ORDER BY id DESC LIMIT 12").fetchall()
 return page("Accueil",'''<div class="hero"><div class="eyebrow">Création · Précision · Innovation</div><h1>Vos idées prennent forme.</h1><p>Impression 3D sur mesure au Saguenay. Pièces pratiques, prototypes et créations uniques avec une finition soignée.</p><a class="btn" href="/soumission">Demander une soumission</a></div><section id="services"><div class="eyebrow">Notre savoir-faire</div><h2>Nos services</h2><div class="grid"><div class="card"><h3>Pièces personnalisées</h3><p>Supports, adaptateurs et accessoires sur mesure.</p></div><div class="card"><h3>Prototypage</h3><p>Transformez vos idées en objets concrets.</p></div><div class="card"><h3>Objets et cadeaux</h3><p>Créations uniques et personnalisées.</p></div></div></section><section id="galerie"><h2>Nos réalisations</h2><div class="grid">{% for item in gallery %}<article class="card">{% if item.has_photo %}<img loading="lazy" src="/photo/{{item.id}}" alt="{{item.title}}">{% endif %}<h3>{{item.title}}</h3><div class="eyebrow">{{item.category}}</div><p>{{item.description}}</p></article>{% else %}<p>De nouvelles réalisations seront bientôt présentées ici.</p>{% endfor %}</div></section>''',gallery=gallery)
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
  reqs=c.execute("SELECT id,kind,name,email,phone,material,description,filename,created,status FROM requests ORDER BY id DESC LIMIT 200").fetchall()
  gallery=c.execute("SELECT id,title,category FROM gallery ORDER BY id DESC").fetchall()
 return page("Administration",'''<h1>Tableau de bord</h1><div class="row"><a class="btn" href="/admin/new">Ajouter une réalisation</a><form method="post" action="/admin/logout">{{csrf|safe}}<button>Déconnexion</button></form></div><h2>Demandes et commandes</h2><div class="grid">{% for r in reqs %}<article class="card"><div class="eyebrow">#{{r.id}} · {{r.kind}} · {{r.created.strftime('%Y-%m-%d')}}</div><h3>{{r.name}}</h3><p><a href="mailto:{{r.email}}">{{r.email}}</a> · {{r.phone or ''}}</p><p>Matériau : {{r.material or '—'}}</p><p style="white-space:pre-wrap">{{r.description}}</p>{% if r.filename %}<p><a href="/admin/file/{{r.id}}">Télécharger {{r.filename}}</a></p>{% endif %}<form method="post" action="/admin/status/{{r.id}}">{{csrf|safe}}<label>Statut<select name="status">{% for s in statuses %}<option {% if s==r.status %}selected{% endif %}>{{s}}</option>{% endfor %}</select></label><button>Enregistrer</button></form></article>{% else %}<p>Aucune demande pour le moment.</p>{% endfor %}</div><h2>Galerie</h2><div class="grid">{% for g in gallery %}<div class="card"><strong>{{g.title}}</strong><p>{{g.category}}</p><form method="post" action="/admin/delete/{{g.id}}" onsubmit="return confirm('Supprimer cette réalisation?')">{{csrf|safe}}<button>Supprimer</button></form></div>{% endfor %}</div>''',reqs=reqs,gallery=gallery,statuses=STATUSES,csrf=csrfinput())
@app.post("/admin/status/<int:id>")
@admin_required
def status(id):
 verify();value=request.form.get("status")
 if value not in STATUSES:abort(400)
 with db() as c:c.execute("UPDATE requests SET status=%s WHERE id=%s",(value,id))
 return redirect("/admin")
@app.get("/admin/file/<int:id>")
@admin_required
def file(id):
 with db() as c:r=c.execute("SELECT filename,filedata FROM requests WHERE id=%s",(id,)).fetchone()
 if not r or not r["filedata"]:abort(404)
 return send_file(io.BytesIO(r["filedata"]),as_attachment=True,download_name=r["filename"],mimetype="application/octet-stream")
@app.route("/admin/new",methods=["GET","POST"])
@admin_required
def new():
 if request.method=="POST":
  verify()
  title=request.form.get("title","").strip();category=request.form.get("category","").strip();description=request.form.get("description","").strip()
  if not title or not category or not description or max(len(title),len(category))>120 or len(description)>2000:abort(400)
  photo=request.files.get("photo");data=None;mime=None
  if photo and photo.filename:
   data=photo.read(5*1024*1024+1)
   if len(data)>5*1024*1024:abort(413)
   if data.startswith(b"\xff\xd8\xff"):mime="image/jpeg"
   elif data.startswith(b"\x89PNG\r\n\x1a\n"):mime="image/png"
   elif data.startswith(b"RIFF") and data[8:12]==b"WEBP":mime="image/webp"
   else:abort(400)
  with db() as c:c.execute("INSERT INTO gallery(title,category,description,photo,mime) VALUES(%s,%s,%s,%s,%s)",(title,category,description,data,mime))
  return redirect("/admin")
 return page("Ajouter une réalisation",'''<h1>Nouvelle réalisation</h1><form method="post" enctype="multipart/form-data">{{csrf|safe}}<label>Titre<input name="title" maxlength="120" required></label><label>Catégorie<input name="category" maxlength="120" required></label><label>Description<textarea name="description" maxlength="2000" required></textarea></label><label>Photo JPG, PNG ou WebP (maximum 5 Mo)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp"></label><button>Publier</button></form>''',csrf=csrfinput())
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
