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
<h1>🖨️ Imprimer depuis l'Atelier administrateur</h1>
<p><a class="btn" href="/admin/atelier-3d">← Retour à mon Atelier 3D</a> ·
<a href="/admin/profils-bambu">⚙️ Mes profils Bambu</a></p>
<p>Pour imprimer sur ta X2D, <strong>tranche d'abord la pièce dans Bambu Studio</strong> avec les bons profils et exporte le <strong>3MF tranché</strong>. Le 3MF couleurs du Fjord et les STL seuls ne contiennent pas encore de tranchage compatible.</p>
{% for notice in messages %}<p class="card" role="status">{{notice}}</p>{% endfor %}
{% if error %}<p class="card" role="alert">Connexion : {{error}}</p>{% endif %}
<section class="card">
<h2>État de l'imprimante</h2>
{% if status %}
<p><strong>{{status.state}}</strong>{% if status.file %} · {{status.file}}{% endif %}{% if status.progress is number %} · {{status.progress}} %{% endif %}</p>
<p>{% if status.can_start %}L'imprimante accepte la commande de démarrage.{% else %}Le démarrage est indisponible (imprimante occupée ou fonctionnalité non prise en charge).{% endif %}</p>
{% else %}<p>La connexion doit être disponible pour envoyer et lancer une impression.</p>{% endif %}
<p><a href="/admin/atelier-imprimer">↻ Actualiser l'état et les fichiers</a></p>
</section>
<section class="card">
<h2>1. Envoyer un 3MF déjà tranché</h2>
<form method="post" action="/admin/atelier-imprimer/envoyer" enctype="multipart/form-data">
{{csrf_field|safe}}
<label>Fichier exporté depuis Bambu Studio
<input type="file" name="sliced_file" accept=".3mf" required></label>
<button type="submit" {% if not status %}disabled{% endif %}>📤 Envoyer à l'imprimante (sans démarrer)</button>
</form>
<p class="muted small">Jusqu'à 30 Mo. Le transfert conserve le fichier sur l'imprimante et ne démarre aucune impression.</p>
</section>
<section class="card">
<h2>2. Choisir un fichier de l'imprimante</h2>
{% if files %}
<form method="post" action="/admin/atelier-imprimer/demarrer"
onsubmit="return confirm('Démarrer réellement l’impression sur la X2D ? Vérifie le plateau, la bonne bobine et la plaque tranchée.');">
{{csrf_field|safe}}
<input type="hidden" name="nonce" value="{{nonce}}">
<label>Fichier sur l'imprimante<select name="path" required>
{% for file in files %}
<option value="{{file.path}}" {% if selected == file.path %}selected{% endif %}>{{file.name}}</option>
{% endfor %}
</select></label>
<label>Plateau dans le fichier<select name="plate"><option value="1">Plaque 1</option></select></label>
<label><input type="checkbox" name="ams" value="yes" checked> Utiliser le système AMS</label>
<label><input type="checkbox" name="verified" value="yes" required>
J'ai vérifié les matériaux, les bobines AMS, les températures et le tranchage dans Bambu Studio.</label>
<label><input type="checkbox" name="cleared" value="yes" required>
J'ai vérifié que le plateau est libre, que l'imprimante est prête et que je peux la surveiller.</label>
<button class="primary" type="submit" {% if not status or not status.can_start %}disabled{% endif %}>🖨️ Confirmer et démarrer l'impression</button>
</form>
{% else %}<p>Aucun fichier 3MF disponible ou impossible de consulter les fichiers de l'imprimante.</p>{% endif %}
<p class="muted small">OctoEverywhere doit confirmer la commande. Une réponse « acceptée » ne garantit pas que la première couche a commencé. Surveille la caméra et l'imprimante.</p>
</section>
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
