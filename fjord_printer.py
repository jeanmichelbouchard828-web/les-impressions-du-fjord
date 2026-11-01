"""Admin-only, opt-in Bambu print launcher through OctoEverywhere Plugin APIs.

No web-generated geometry or generic G-code is submitted to a printer.
Only native 3MF files containing a sliced Bambu plate are accepted for upload.
The administrator must separately select a printer-side file and explicitly
confirm launch. The real printer remains the source of truth for printing.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from flask import abort, flash, get_flashed_messages, redirect, render_template_string, request, session, url_for

MAX_SLICED_3MF = 30 * 1024 * 1024
MAX_ZIP_ENTRIES = 2500
FEATURE_START = 32

class PrinterError(ValueError):
    """Safe user-facing error message without credentials or private URLs."""

def _connection():
    base = os.environ.get("OCTOEVERYWHERE_CONNECTION_URL", "").strip().rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(base)
        hostname, port, username, password = parsed.hostname, parsed.port, parsed.username, parsed.password
    except ValueError as exc:
        raise PrinterError("Connexion OctoEverywhere non configurée ou invalide dans Railway.") from exc
    if (parsed.scheme != "https" or not hostname or
        not hostname.endswith(".octoeverywhere.com") or
        hostname == ".octoeverywhere.com" or
        username or password or port is not None or
        parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise PrinterError("Connexion OctoEverywhere non configurée ou invalide dans Railway.")
    return base

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # Never send printer credentials to redirected domains.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _api(path, *, method="GET", payload=None, timeout=9):
    if path not in ("/status", "/files/list", "/files/upload", "/start"):
        raise PrinterError("Commande d'imprimante non autorisée.")
    base = _connection()
    headers = {"Accept": "application/json", "User-Agent": "Fjord-Atelier-Admin/1"}
    bearer = os.environ.get("OCTOEVERYWHERE_AUTH_BEARER_TOKEN", "").strip()
    basic_user = os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_USER", "").strip()
    basic_pass = os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_PASSWORD", "")
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    elif basic_user and basic_pass:
        credentials = (basic_user + ":" + basic_pass).encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
    data = None
    if method == "POST":
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif method == "PUT":
        if not isinstance(payload, bytes):
            raise PrinterError("Données d'impression invalides.")
        data = payload
        headers["Content-Type"] = "application/octet-stream"
    url = base + "/octoeverywhere-command-api" + path
    if path == "/files/list":
        url += "?root=gcode"
    elif path == "/files/upload":
        virtual_path = payload if isinstance(payload, str) else None
        # Upload path is passed as (str path, bytes)? Keep it explicit through _upload below.
        raise PrinterError("Utiliser l'interface d'envoi sécurisée.")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout) as resp:
            content = resp.read(2 * 1024 * 1024 + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PrinterError("La connexion à l'imprimante n'a pas répondu. Vérifie OctoEverywhere.") from exc
    if len(content) > 2 * 1024 * 1024:
        raise PrinterError("Réponse de l'imprimante trop volumineuse.")
    try:
        envelope = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrinterError("Réponse de l'imprimante illisible.") from exc
    if not isinstance(envelope, dict) or envelope.get("Status") != 200:
        status = envelope.get("Status", "?") if isinstance(envelope, dict) else "?"
        raise PrinterError("OctoEverywhere ne permet pas cette opération (code {}).".format(str(status)[:5]))
    result = envelope.get("Result")
    if not isinstance(result, dict):
        raise PrinterError("Réponse de l'imprimante incomplète.")
    return result

def _upload(virtual_path, raw):
    if not isinstance(raw, bytes) or not _safe_virtual_path(virtual_path):
        raise PrinterError("Chemin ou fichier d'impression invalide.")
    url = (_connection() + "/octoeverywhere-command-api/files/upload?path=" +
           urllib.parse.quote(virtual_path, safe="/"))
    headers = {"Accept": "application/json", "Content-Type": "application/octet-stream",
               "User-Agent": "Fjord-Atelier-Admin/1"}
    token = os.getenv("OCTOEVERYWHERE_AUTH_BEARER_TOKEN", "").strip()
    user = os.getenv("OCTOEVERYWHERE_AUTH_BASIC_USER", "").strip()
    password = os.getenv("OCTOEVERYWHERE_AUTH_BASIC_PASSWORD", "")
    if token: headers["Authorization"] = "Bearer " + token
    elif user and password:
        headers["Authorization"] = "Basic " + base64.b64encode((user + ":" + password).encode()).decode("ascii")
    try:
        req = urllib.request.Request(url, data=raw, headers=headers, method="PUT")
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=50) as resp:
            payload = resp.read(1024 * 1024 + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PrinterError("Envoi refusé ou interrompu par OctoEverywhere. Réessaie depuis Bambu Studio si nécessaire.") from exc
    if len(payload) > 1024 * 1024:
        raise PrinterError("Confirmation de transfert trop volumineuse.")
    try: result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrinterError("Impossible de confirmer le transfert à l'imprimante.") from exc
    if not isinstance(result, dict) or result.get("Status") != 200:
        code = result.get("Status", "?") if isinstance(result, dict) else "?"
        raise PrinterError("La connexion ne prend pas en charge l'envoi de fichiers (code {}).".format(str(code)[:5]))
    remote = result.get("Result") or {}
    if not isinstance(remote, dict) or remote.get("VirtualPath") != virtual_path:
        raise PrinterError("Le chemin du fichier envoyé n'a pas été confirmé par l'imprimante.")
    return remote

def _safe_virtual_path(value):
    if not isinstance(value, str) or len(value) > 230 or not value.startswith("gcode/"):
        return False
    if not value.lower().endswith(".3mf") or "\\" in value or "?" in value or "#" in value:
        return False
    return not any(part in ("", ".", "..") for part in value.split("/"))

def _printer_files(tree):
    result = []
    def visit(node, depth=0):
        if depth > 12 or len(result) >= 300 or not isinstance(node, dict):
            return
        if str(node.get("Type", "")).lower() == "file":
            path = node.get("VirtualPath")
            if _safe_virtual_path(path):
                result.append({"path":path,"name":str(node.get("Name") or path.rsplit("/",1)[-1])[:150],
                               "bytes":node.get("SizeBytes")})
        for child in node.get("Children") or []:
            visit(child, depth+1)
    for root in tree.get("Root") or []:
        visit(root)
    return result

def verify_sliced_bambu_3mf(raw):
    """Reject ordinary 3MF object archives that have no sliced plate G-code."""
    if not isinstance(raw, bytes) or not (100 <= len(raw) <= MAX_SLICED_3MF):
        raise PrinterError("Choisis un 3MF tranché de moins de 30 Mo.")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise PrinterError("Archive 3MF trop complexe.")
            if any(info.flag_bits & 1 for info in entries):
                raise PrinterError("Les projets 3MF chiffrés ne sont pas pris en charge.")
            if sum(info.file_size for info in entries) > 1024 * 1024 * 1024:
                raise PrinterError("Projet 3MF décompressé trop volumineux.")
            names = [name.replace("\\", "/") for name in archive.namelist()]
            if any(name.startswith("/") or ".." in name.split("/") for name in names):
                raise PrinterError("Chemin dangereux détecté dans le fichier 3MF.")
            if "3D/3dmodel.model" not in names:
                raise PrinterError("Projet 3MF non reconnu : géométrie absente.")
            plates = [int(m.group(1)) for n in names
                      if (m := re.fullmatch(r"Metadata/plate_(\d{1,3})\.gcode", n))]
            if not plates:
                raise PrinterError("Ce 3MF contient un modèle, mais aucune plaque tranchée Bambu. Ouvre-le dans Bambu Studio et fais « Trancher » avant l'envoi.")
            if 1 not in plates:
                raise PrinterError("Le fichier n'a pas de plaque 1 tranchée.")
            plate = archive.getinfo("Metadata/plate_1.gcode")
            if plate.file_size < 100:
                raise PrinterError("Le G-code de la plaque 1 est incomplet.")
            return sorted(set(plates))
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, KeyError) as exc:
        raise PrinterError("Archive 3MF illisible ou endommagée.") from exc

def _status():
    result = _api("/status")
    job = result.get("JobStatus") or {}
    features = result.get("Features")
    features = features if type(features) is int else 0
    state = str(job.get("State") or "inconnu").lower()
    current = job.get("CurrentPrint") or {}
    return {"state":state,"progress":current.get("Progress"),
            "file":str(current.get("FileName") or "")[:120],
            "features":features,
            "can_start":bool(features & FEATURE_START) and state in ("idle", "complete", "cancelled")}

def register_printer_admin(app, admin_required, verify, csrfinput, page):
    @app.get("/admin/atelier-imprimer")
    @admin_required
    def fjord_printer_page():
        status = None
        files = []
        error = ""
        try:
            status = _status()
            try:
                files = _printer_files(_api("/files/list"))
            except PrinterError as exc: error = str(exc)
        except PrinterError as exc:
            error = str(exc)
        token = secrets.token_urlsafe(24)
        session["fjord_print_nonce"] = token
        return page("Impression X2D", r"""
<style>
/* Scoped to the private printing console: no changes to public pages. */
.fj-print{--p-border:#34566e;--p-panel:#122b3e;--p-panel-soft:#15364b;
 --p-text:#f2f8fd;--p-sub:#afcddd;--p-accent:#60cee9;--p-green:#57dfa7;
 color:var(--p-text);max-width:1220px;margin:0 auto 32px;min-width:0}
.fj-print *{box-sizing:border-box}
.fj-print a{color:var(--p-accent)}
.fj-print-hero{border:1px solid #3e7e9f;border-radius:20px;padding:clamp(18px,3vw,30px);
 background:linear-gradient(115deg,#14364c 0%,#0c2234 78%);margin-bottom:20px;
 display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap}
.fj-print-kicker{text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:800;color:#8bdeee;margin:0 0 9px}
.fj-print h1{font-size:clamp(24px,3vw,36px);line-height:1.16;margin:0 0 10px;color:#fff}
.fj-print-hero p{font-size:14px;line-height:1.55;color:#d0e4ef;margin:0;max-width:620px}
.fj-print-nav{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
.fj-print-nav a{display:inline-flex;text-decoration:none;border:1px solid #50758c;border-radius:9px;
 align-items:center;justify-content:center;padding:10px 13px;min-height:43px;background:#1c3d52;
 color:#eaf8ff;font-size:13px;font-weight:750}
.fj-print-nav a:hover,.fj-print-nav a:focus-visible{background:#275b78;outline:2px solid #8de1ff;outline-offset:2px}
.fj-print-step-bar{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0 0 19px}
.fj-print-step-bar>div{border:1px solid var(--p-border);border-radius:12px;background:#112c40;
 padding:11px 13px;color:#bed7e3;font-size:13px;display:flex;align-items:center;gap:10px;min-width:0}
.fj-print-step-bar strong,.fj-print-number{width:29px;height:29px;border-radius:50%;flex:0 0 29px;
 display:grid;place-items:center;background:#235978;color:#d8f8ff;font-size:14px;font-weight:850}
.fj-print-notice{border:1px solid #4b8caa;border-radius:10px;padding:12px 16px;margin-bottom:13px;
 background:#163a4b;color:#e9f8ff;line-height:1.45;overflow-wrap:anywhere}
.fj-print-notice.error{background:#422b2e;border-color:#b46d6d;color:#ffe9e9}
.fj-print-card{border:1px solid var(--p-border);border-radius:16px;background:var(--p-panel);
 padding:clamp(15px,2.2vw,24px);min-width:0;box-shadow:0 8px 24px #07152225}
.fj-print-card h2{display:flex;gap:10px;align-items:center;font-size:clamp(17px,2vw,21px);
 color:#f4fbff;margin:0 0 8px;line-height:1.3}
.fj-print-card p{color:var(--p-sub);font-size:13px;line-height:1.55;margin:8px 0 0}
.fj-print-card strong{color:#fff}
.fj-print-layout{display:grid;grid-template-columns:minmax(0,.96fr) minmax(0,1.04fr);gap:17px;align-items:start}
.fj-print-col{display:grid;gap:17px;min-width:0}
.fj-print-status{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center}
.fj-print-status-summary{display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.fj-print-indicator{height:12px;width:12px;border-radius:50%;background:#8899a9;
 box-shadow:0 0 0 4px #8899a91f;flex:none}
.fj-print-indicator.ready{background:var(--p-green);box-shadow:0 0 0 4px #57dfa72c}
.fj-print-status-summary h2{margin:0}
.fj-print-state{display:inline-flex;gap:7px;align-items:center;line-height:1.3;
 background:#24455a;border:1px solid #4d7890;border-radius:50px;padding:6px 11px;
 color:#d1e8f1;font-size:12px;font-weight:800;max-width:100%;overflow-wrap:anywhere}
.fj-print-status .fj-print-refresh{background:#214d68;border:1px solid #5b92ae;
 border-radius:9px;display:inline-flex;align-items:center;justify-content:center;padding:10px 12px;
 text-decoration:none;min-height:41px;font-weight:750;font-size:13px;color:#d6f4ff}
.fj-print-job-name{word-break:break-word}
.fj-print progress{width:100%;max-width:350px;height:11px;display:block;margin-top:10px;accent-color:#49b4e5}
.fj-print-card .fj-print-intro{margin:0 0 16px}
.fj-print-step-title{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.fj-print-step-title h2{margin:0}
.fj-print-step-title .fj-print-number{background:#246285}
.fj-print form{display:grid;gap:13px}
.fj-print label{display:block;color:#d9eef6;font-size:13px;font-weight:750;line-height:1.45}
.fj-print input[type=file],.fj-print select{width:100%;display:block;margin-top:7px;
 border-radius:9px;border:1px solid #52788c;background:#0c2335;color:#eaf6ff;
 padding:11px 12px;font-size:14px;min-height:46px;max-width:100%}
.fj-print input[type=file]::file-selector-button{background:#265671;color:#e6f7ff;border:0;
 padding:9px;border-radius:7px;margin-right:10px;font-weight:750}
.fj-print input:focus-visible,.fj-print select:focus-visible,.fj-print button:focus-visible{
 outline:2px solid #90e3ff;outline-offset:3px}
.fj-print button{border-radius:10px;border:1px solid #469cbb;background:#195171;color:#fff;
 min-height:47px;padding:11px 15px;font-weight:800;font-size:14px;cursor:pointer;
 width:100%;white-space:normal;line-height:1.35}
.fj-print button:hover:not(:disabled){background:#22749b}
.fj-print button:disabled{opacity:.52;cursor:not-allowed}
.fj-print button.fj-print-start{background:linear-gradient(105deg,#158060,#12674e);
 border-color:#59d5a9;color:#f4fff9;font-size:15px;padding:13px}
.fj-print button.fj-print-start:hover:not(:disabled){background:#169674}
.fj-print-card .fj-print-hint{font-size:12px;color:#afcbd8;margin-top:12px}
.fj-print-checks{border:1px solid #3f6177;border-radius:11px;padding:12px;
 background:#0e293c;display:grid;gap:13px}
.fj-print-check{display:flex!important;align-items:flex-start;gap:10px;font-weight:500!important;
 cursor:pointer;line-height:1.45!important}
.fj-print-check input[type=checkbox]{appearance:auto;width:18px;height:18px;min-width:18px;
 margin:2px 0 0;accent-color:#49bda2;cursor:pointer}
.fj-print-check>span{min-width:0;flex:1}
.fj-print-field-pair{display:grid;grid-template-columns:minmax(0,1fr) 118px;gap:12px}
.fj-print-empty{background:#0b2536;border:1px dashed #537b92;border-radius:11px;
 padding:14px 16px;color:#d2e6f2;font-size:13px;line-height:1.5}
.fj-print-guide{background:#142e40;border:1px solid #365c73;border-radius:13px;
 padding:14px 17px;margin-top:17px}
.fj-print-guide h3{margin:0 0 9px;color:#edfaff;font-size:14px}
.fj-print-guide ol{padding-left:21px;margin:0;color:#bddeed;font-size:13px;line-height:1.7}
.fj-print-guide li{padding:2px 0}
.fj-print-chip{background:#26485d;color:#c9e9f6;border:1px solid #56809a;
 border-radius:7px;padding:4px 7px;font-size:11px;font-weight:800;display:inline-flex}
.fj-print-bottom{color:var(--p-sub);font-size:12px;line-height:1.55;margin:17px 1px 0}
body.light .fj-print{--p-panel:#fff;--p-border:#c0d7e5;--p-sub:#3e5970;--p-text:#17344c}
body.light .fj-print-card{background:#fff}
body.light .fj-print-card h2,body.light .fj-print-card strong{color:#163750}
body.light .fj-print-card p{color:#45657a}
body.light .fj-print-step-bar>div{background:#e7f2f8;color:#244a64}
body.light .fj-print-state{background:#eaf3f7;color:#174e64}
body.light .fj-print label{color:#153750}
body.light .fj-print input[type=file],body.light .fj-print select{background:#fff;color:#183c56;border-color:#9abbd0}
body.light .fj-print-checks{background:#eaf3f8;border-color:#b4d1e1}
body.light .fj-print-guide{background:#eef6fa}
body.light .fj-print-guide h3{color:#18374c}
body.light .fj-print-guide ol{color:#36576c}
body.light .fj-print-empty{background:#f0f7fb;color:#2c536c}
body.light .fj-print-hint{color:#496477!important}
@media(max-width:820px){
 .fj-print-layout{grid-template-columns:minmax(0,1fr)}
 .fj-print-status{grid-column:auto}
 .fj-print-step-bar{gap:6px}
 .fj-print-step-bar>div{font-size:12px;padding:9px}
}
@media(max-width:540px){
 .fj-print-hero{padding:18px 15px;border-radius:14px}
 .fj-print-nav{width:100%}
 .fj-print-nav a{flex:1 1 135px}
 .fj-print-step-bar{grid-template-columns:1fr}
 .fj-print-step-bar>div{min-height:40px}
 .fj-print-status{grid-template-columns:1fr}
 .fj-print-status .fj-print-refresh{width:100%}
 .fj-print-field-pair{grid-template-columns:1fr}
 .fj-print-card{border-radius:13px;padding:17px 14px}
}
</style>
<div class="fj-print" id="fjordPrintPage">
  <section class="fj-print-hero" aria-labelledby="fjordPrintTitle">
    <div>
      <div class="fj-print-kicker">Les Impressions du Fjord · Atelier privé</div>
      <h1 id="fjordPrintTitle">🖨️ Imprimer sur ma X2D</h1>
      <p>Une interface simple pour vérifier ton imprimante, transférer une pièce tranchée et lancer ton impression en toute connaissance de cause.</p>
    </div>
    <nav class="fj-print-nav" aria-label="Navigation Atelier 3D">
      <a href="/admin/atelier-3d">← Retour à l’Atelier</a>
      <a href="/admin/profils-bambu">⚙️ Mes profils Bambu</a>
    </nav>
  </section>

  <div class="fj-print-step-bar" aria-label="Étapes d’impression">
    <div><strong aria-hidden="true">1</strong><span>Vérifier la X2D</span></div>
    <div><strong aria-hidden="true">2</strong><span>Envoyer le fichier 3MF</span></div>
    <div><strong aria-hidden="true">3</strong><span>Vérifier et démarrer</span></div>
  </div>

  {% for notice in messages %}
  <div class="fj-print-notice" role="status">{{notice}}</div>
  {% endfor %}
  {% if error %}
  <div class="fj-print-notice error" role="alert"><strong>Connexion :</strong> {{error}}</div>
  {% endif %}

  <div class="fj-print-layout">
    <section class="fj-print-card fj-print-status" aria-label="État actuel de l'imprimante">
      <div>
        <div class="fj-print-status-summary">
          <span class="fj-print-indicator {% if status and status.can_start %}ready{% endif %}" aria-hidden="true"></span>
          <h2>État de la X2D</h2>
          <span class="fj-print-state">
            {% if status %}{{status.state}}{% else %}Connexion indisponible{% endif %}
          </span>
        </div>
        {% if status %}
          {% if status.file %}<p class="fj-print-job-name"><strong>Fichier en cours :</strong> {{status.file}}</p>{% endif %}
          {% if status.progress is number %}
            <progress max="100" value="{{status.progress}}" aria-label="Progression de l’impression">{{status.progress}} %</progress>
            <p>{{status.progress}} % terminé</p>
          {% endif %}
          <p>{% if status.can_start %}La commande de démarrage est disponible.{% else %}La commande de démarrage n’est pas disponible. L’imprimante est peut-être occupée ou la connexion ne prend pas en charge cette fonction.{% endif %}</p>
        {% else %}
          <p>La connexion doit être disponible pour transférer ou démarrer un fichier.</p>
        {% endif %}
      </div>
      <a class="fj-print-refresh" href="/admin/atelier-imprimer">↻ Actualiser</a>
    </section>

    <div class="fj-print-col">
      <section class="fj-print-card" aria-labelledby="fjordUploadTitle">
        <div class="fj-print-step-title">
          <span class="fj-print-number" aria-hidden="true">2</span>
          <h2 id="fjordUploadTitle">Envoyer un fichier tranché</h2>
        </div>
        <p class="fj-print-intro">Choisis un <strong>3MF déjà tranché avec Bambu Studio</strong>. Un simple STL ou le 3MF de modélisation de l’Atelier n’est pas encore prêt pour l’impression.</p>
        <form method="post" action="/admin/atelier-imprimer/envoyer" enctype="multipart/form-data">
          {{csrf_field|safe}}
          <label for="fjordPrintUpload">Mon fichier Bambu Studio (.3mf)
            <input id="fjordPrintUpload" type="file" name="sliced_file" accept=".3mf" required>
          </label>
          <div id="fjordPrintFileName" class="fj-print-chip" role="status">Aucun fichier sélectionné</div>
          <button type="submit" {% if not status %}disabled{% endif %}>📤 Envoyer à la X2D</button>
        </form>
        <p class="fj-print-hint">Maximum 30 Mo. L’envoi ne déclenche jamais automatiquement l’impression.</p>
      </section>
      <aside class="fj-print-guide" aria-labelledby="fjordPrintGuideTitle">
        <h3 id="fjordPrintGuideTitle">Avant de lancer une impression</h3>
        <ol>
          <li>Ouvre la pièce dans Bambu Studio et choisis le bon profil X2D.</li>
          <li>Vérifie matériau, buse, plateau et correspondance AMS.</li>
          <li>Tranche la pièce, puis exporte le fichier 3MF tranché.</li>
          <li>Envoie le fichier ici, vérifie le plateau et confirme le démarrage.</li>
        </ol>
      </aside>
    </div>

    <section class="fj-print-card" aria-labelledby="fjordStartTitle">
      <div class="fj-print-step-title">
        <span class="fj-print-number" aria-hidden="true">3</span>
        <h2 id="fjordStartTitle">Vérifier et démarrer</h2>
      </div>
      <p class="fj-print-intro">Sélectionne le fichier présent sur la X2D, puis valide les contrôles avant l’impression.</p>
      {% if files %}
      <form method="post" action="/admin/atelier-imprimer/demarrer"
        onsubmit="return confirm('Démarrer réellement l’impression sur la X2D ? Vérifie le plateau, la bonne bobine et la plaque tranchée.');">
        {{csrf_field|safe}}
        <input type="hidden" name="nonce" value="{{nonce}}">
        <div class="fj-print-field-pair">
          <label for="fjordPrintRemote">Fichier sur l’imprimante
            <select id="fjordPrintRemote" name="path" required>
              {% for file in files %}
              <option value="{{file.path}}" {% if selected == file.path %}selected{% endif %}>{{file.name}}</option>
              {% endfor %}
            </select>
          </label>
          <label for="fjordPrintPlate">Plateau
            <select id="fjordPrintPlate" name="plate"><option value="1">Plaque 1</option></select>
          </label>
        </div>
        <div class="fj-print-checks" role="group" aria-label="Vérifications avant impression">
          <label class="fj-print-check"><input type="checkbox" name="ams" value="yes" checked>
            <span>Utiliser le système AMS</span></label>
          <label class="fj-print-check"><input type="checkbox" name="verified" value="yes" required>
            <span>J’ai vérifié les matériaux, les bobines AMS, les températures et le tranchage dans Bambu Studio.</span></label>
          <label class="fj-print-check"><input type="checkbox" name="cleared" value="yes" required>
            <span>Le plateau est libre, l’imprimante est prête et je peux surveiller le lancement.</span></label>
        </div>
        <button class="fj-print-start" type="submit"
          {% if not status or not status.can_start %}disabled{% endif %}>
          🖨️ Confirmer et démarrer l’impression
        </button>
      </form>
      {% else %}
      <div class="fj-print-empty">Aucun fichier 3MF trouvé sur l’imprimante, ou impossible de consulter sa bibliothèque. Envoie un fichier compatible, puis clique sur « Actualiser ».</div>
      {% endif %}
      <p class="fj-print-hint">OctoEverywhere doit accepter la commande. Une confirmation d’envoi ne garantit pas que la première couche a commencé.</p>
    </section>
  </div>
  <p class="fj-print-bottom">Important : les profils sauvegardés dans l’Atelier ne sont pas encore un moteur de tranchage Bambu. L’impression directe d’un modèle créé dans l’Atelier nécessitera une intégration de tranchage compatible et vérifiée.</p>
</div>
<script>
(function(){
 const upload=document.getElementById('fjordPrintUpload');
 const label=document.getElementById('fjordPrintFileName');
 if(upload && label){
   upload.addEventListener('change',()=>{
     const file=upload.files && upload.files[0];
     label.textContent=file ? file.name : 'Aucun fichier sélectionné';
   });
 }
})();
</script>
""",csrf_field=csrfinput(),nonce=token,status=status,files=files,error=error,
           selected=request.args.get("selected",""),messages=get_flashed_messages())

    @app.post("/admin/atelier-imprimer/envoyer")
    @admin_required
    def fjord_printer_upload():
        # This endpoint alone may accept larger Bambu 3MF uploads. The rest
        # of the public website retains its global 10 MB request limit.
        request.max_content_length = MAX_SLICED_3MF + 2 * 1024 * 1024
        verify()
        upload = request.files.get("sliced_file")
        if not upload or not upload.filename or not upload.filename.lower().endswith(".3mf"):
            abort(400,"Choisis un 3MF tranché.")
        raw = upload.read(MAX_SLICED_3MF+1)
        try:
            verify_sliced_bambu_3mf(raw)
            # Confirm connected printer before relaying machine-ready payload.
            _status()
            safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", upload.filename.rsplit(".",1)[0])[:44] or "piece"
            virtual_path = "gcode/fjord_" + secrets.token_hex(5) + "_" + safe_name + ".3mf"
            _upload(virtual_path, raw)
            flash("Fichier tranché envoyé. Sélectionne-le dans la liste puis confirme manuellement l'impression.")
            return redirect(url_for("fjord_printer_page", selected=virtual_path))
        except PrinterError as exc:
            flash(str(exc))
            return redirect(url_for("fjord_printer_page"))

    @app.post("/admin/atelier-imprimer/demarrer")
    @admin_required
    def fjord_printer_start():
        verify()
        nonce = request.form.get("nonce","")
        stored = session.pop("fjord_print_nonce",None)
        if not stored or not secrets.compare_digest(stored,nonce):
            abort(400,"Confirmation expirée. Actualise la page.")
        if request.form.get("verified") != "yes" or request.form.get("cleared") != "yes":
            abort(400,"Confirme toutes les vérifications de sécurité avant le démarrage.")
        path = request.form.get("path","")
        if not _safe_virtual_path(path) or request.form.get("plate") != "1":
            abort(400,"Choix de fichier ou de plateau invalide.")
        try:
            status = _status()
            if not status["can_start"]:
                raise PrinterError("Imprimante occupée ou démarrage non pris en charge. Aucune commande envoyée.")
            listed = _printer_files(_api("/files/list"))
            if not any(item["path"] == path for item in listed):
                raise PrinterError("Fichier absent de l'imprimante. Aucune commande envoyée.")
            command = {"Path":path,"Plate":1,"UseAms":request.form.get("ams")=="yes"}
            response = _api("/start",method="POST",payload=command,timeout=15)
            # A transport acknowledgement is not proof the printer is actually printing.
            if response.get("VirtualPath") not in (None,path):
                raise PrinterError("La confirmation du fichier démarré ne correspond pas.")
            flash("Commande de démarrage acceptée. Surveille la X2D et confirme le lancement réel sur l'écran ou la caméra.")
        except PrinterError as exc:
            flash(str(exc))
        return redirect(url_for("fjord_printer_page"))
