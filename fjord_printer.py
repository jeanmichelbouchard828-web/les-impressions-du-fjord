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
import math
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from flask import Response, abort, flash, get_flashed_messages, jsonify, redirect, render_template_string, request, send_file, session, url_for

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
        raise PrinterError("Connexion OctoEverywhere non configurée ou invalide dans Render.") from exc
    if (parsed.scheme != "https" or not hostname or
        not hostname.endswith(".octoeverywhere.com") or
        hostname == ".octoeverywhere.com" or
        username or password or port is not None or
        parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise PrinterError("Connexion OctoEverywhere non configurée ou invalide dans Render.")
    return base

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # Never send printer credentials to redirected domains.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _api(path, *, method="GET", payload=None, timeout=9):
    if path not in ("/status", "/status?IncludeMaterialSystem=true", "/files/list", "/files/upload", "/start"):
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

def _categorize_plugin_log(log_text):
    """Turn potentially sensitive OctoEverywhere logs into one fixed, safe hint.

    Never return even a substring of raw logs to a user, including hostnames,
    printer serial numbers, paths, LAN IPs, usernames or authentication data.
    """
    if not isinstance(log_text, str) or not log_text:
        return None
    # Explicit firmware authorization errors are a distinct failure mode from
    # FTPS upload failures. Never reveal private raw MQTT logs to the browser.
    recent = [line.lower() for line in log_text.splitlines()[-180:]]
    for line in reversed(recent):
        if "84033543" in line or (
            "mqtt" in line and ("verification failed" in line or
                               "verify failed" in line or
                               "signature invalid" in line)):
            return ("Le journal contient un échec de vérification MQTT sur une commande. "
                    "Le firmware peut refuser le démarrage à distance : vérifie "
                    "les messages sur l'écran de la X2D. Aucun départ confirmé.")
    relevant = []
    for line in log_text.splitlines()[-180:]:
        lower = line.lower()
        if any(word in lower for word in ("ftps", "ftp ", "ftp:", "file upload",
                                         "uploadfile", "storbinary", "stor ", "files/upload")):
            if any(word in lower for word in ("fail", "error", "except", "timeout",
                                             "denied", "abort", "reset", "550", "530",
                                             "425", "426", "storage", "disconnect",
                                             "no space", "not found", "shutdown")):
                relevant.append(lower)
    if not relevant:
        return None
    # The most recent error takes precedence, not an arbitrary older line.
    context = relevant[-1]
    if any(word in context for word in ("no usb", "no sd card", "not mounted", "no storage", "storage missing")):
        return "Les journaux évoquent un stockage USB absent ou non monté. Vérifie la clé USB sur la X2D."
    if any(word in context for word in ("no space", "disk full", "storage full", "out of space", "quota")):
        return "Les journaux évoquent un stockage plein. Vérifie l’espace libre de la clé USB."
    if any(word in context for word in ("permission denied", "read-only", "write protected",
                                       "file or directory was not found", " 550 ")):
        return "Les journaux évoquent un refus d’écriture ou un chemin inaccessible sur le stockage de la X2D."
    if any(word in context for word in ("authentication failed", " 530 ", "login failed",
                                       "incorrect password", "bad credentials")):
        return "Les journaux évoquent une authentification FTPS refusée. Vérifie le code d’accès stocké dans OctoEverywhere."
    if any(word in context for word in (" 425 ", " 426 ", "passive", "data channel",
                                       "data connection", "ssl", "tls", "timed out",
                                       "timeout", "connection reset", "broken pipe")):
        return "Les journaux évoquent un problème de canal de transfert FTPS (TLS, réseau ou délai). Vérifie le réseau local du conteneur."
    return "Le journal signale une erreur FTPS d’écriture, sans raison assez précise pour la corriger automatiquement."


def _plugin_log_hint():
    """Read-only remote log-tail check; send only a generic category to admin."""
    base = _connection()
    url = base + "/octoeverywhere-command-api/get-plugin-logs?tailLines=140"
    headers = {"Accept": "text/plain", "User-Agent": "Fjord-Atelier-Diagnostic/1"}
    bearer = os.getenv("OCTOEVERYWHERE_AUTH_BEARER_TOKEN", "").strip()
    username = os.getenv("OCTOEVERYWHERE_AUTH_BASIC_USER", "").strip()
    password = os.getenv("OCTOEVERYWHERE_AUTH_BASIC_PASSWORD", "")
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    elif username and password:
        headers["Authorization"] = "Basic " + base64.b64encode(
            (username + ":" + password).encode("utf-8")).decode("ascii")
    try:
        request_log = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.build_opener(_NoRedirect).open(request_log, timeout=8) as response:
            # The remote plugin may have no log or more than our strict cap.
            content = response.read(256 * 1024 + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None
    if len(content) > 256 * 1024 or not content:
        return None
    return _categorize_plugin_log(content.decode("utf-8", "replace"))


def _upload_error_hint(envelope):
    """Classify the *actual failed upload response*, without exposing details.

    OctoEverywhere normally includes the FTPS exception in its JSON Error
    envelope even when the plugin does not write that exception to its log.
    Return only fixed, safe French hints: never leak the full response,
    IP/hostnames, serial numbers, credentials or filenames.
    """
    if not isinstance(envelope, dict):
        return " Le serveur n'a pas transmis de diagnostic de transfert exploitable."
    messages = []
    for value in (envelope.get("Error"), envelope.get("Message"),
                  (envelope.get("Result") or {}).get("Error")
                  if isinstance(envelope.get("Result"), dict) else None):
        if isinstance(value, str):
            messages.append(value[:600].lower())
    error = " ".join(messages)
    if any(word in error for word in ("no usb", "not mounted", "no storage",
                                      "storage missing", "no sd card")):
        return " Le transfert signale un stockage USB absent ou non monté."
    if any(word in error for word in ("no space", "disk full", "storage full",
                                      "out of space", "quota exceeded")) or re.search(r"(?<!\\d)552(?!\\d)",error):
        return " Le transfert signale un stockage plein (FTP 552). Vérifie l'espace libre."
    if any(word in error for word in ("permission denied", "read only", "read-only",
                                      "access denied", "not permitted", "permission error",
                                      "not found", "invalid path", "failed to create")) or re.search(r"(?<!\\d)(550|553)(?!\\d)",error):
        return " Le transfert signale un chemin inaccessible ou un refus d'écriture (FTP 550/553)."
    if any(word in error for word in ("authentication failed", "login failed",
                                      "incorrect password", "bad credentials",
                                      "not logged in")) or re.search(r"(?<!\\d)530(?!\\d)",error):
        return " Le transfert signale une authentification FTPS refusée (FTP 530). Vérifie le code d'accès."
    if any(word in error for word in ("ssl", "tls", "handshake", "certificate",
                                      "unexpected eof", "end of file", "eof occurred")):
        return " Le transfert signale une erreur de négociation ou de fermeture TLS sur le canal FTPS."
    if any(word in error for word in ("timeout", "timed out", "unreachable", "connection refused",
                                      "connection failed", "connection reset", "broken pipe",
                                      "passive", "data channel", "data connection")) or re.search(r"(?<!\\d)(425|426)(?!\\d)",error):
        return " Le transfert signale une erreur de canal de données FTP ou une interruption réseau."
    if "ftp" in error or "storbinary" in error or "stor " in error:
        return " Le transfert échoue dans la commande d'écriture FTPS STOR, sans code d'erreur plus précis."
    return " OctoEverywhere a retourné 752, mais sans raison FTPS exploitable dans sa réponse."



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
        if code == 752:
            raise PrinterError(
                "Échec du transfert OctoEverywhere (752). "
                "Ton 3MF est tranché, mais il n'est pas confirmé sur la X2D."
                + _upload_error_hint(result) +
                " Utilise « Télécharger le 3MF tranché » plus haut, "
                "ou lance le diagnostic en lecture seule ci-dessous. "
                "Aucune impression n'a démarré."
            )
        if code == 788:
            raise PrinterError("L'envoi de fichiers n'est pas pris en charge sur cette connexion OctoEverywhere (code 788).")
        raise PrinterError("OctoEverywhere a refusé le transfert du fichier (code {}).".format(str(code)[:5]))
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
            # BambuStudio --min-save outputs a valid sliced package without
            # model geometry; the native plate G-code is the required payload.
            plates = [int(m.group(1)) for n in names
                      if (m := re.fullmatch(r"Metadata/plate_(\d{1,3})\.gcode", n))]
            if not plates:
                raise PrinterError("Ce 3MF ne contient aucune plaque Bambu tranchée. Ouvre-le dans Bambu Studio, fais « Trancher », puis exporte le fichier tranché.")
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
    error = str(job.get("Error") or "")[:160]
    # Bambu firmware reports a user-cancelled task as an error. Treat only this
    # exact cancellation message as idle-ready; other printer errors stay blocked.
    if state == "error" and error.strip().casefold() == "error: the task was canceled.":
        state = "cancelled"
    current = job.get("CurrentPrint") or {}
    def bounded_number(value, maximum):
        return (value if type(value) in (int, float) and math.isfinite(value) and
                0 <= value <= maximum else None)
    progress = bounded_number(current.get("Progress"), 100)
    temps = current.get("Temps") if isinstance(current.get("Temps"), dict) else {}
    return {"state":state, "progress":progress,
            "file":str(current.get("FileName") or "")[:120],
            "substate":str(job.get("SubState") or "")[:120],
            "error":error,
            "time_left_sec":bounded_number(current.get("TimeLeftSec"), 31_536_000),
            "elapsed_sec":bounded_number(current.get("DurationSec"), 31_536_000),
            "hotend_actual":bounded_number(temps.get("HotendActual"), 500),
            "hotend_target":bounded_number(temps.get("HotendTarget"), 500),
            "bed_actual":bounded_number(temps.get("BedActual"), 200),
            "bed_target":bounded_number(temps.get("BedTarget"), 200),
            "current_layer":bounded_number(current.get("CurrentLayer"), 1_000_000),
            "total_layers":bounded_number(current.get("TotalLayers"), 1_000_000),
            "features":features,
            "can_start":bool(features & FEATURE_START) and state in ("idle", "complete", "cancelled")}

def _atelier_remote_start_outcome(status, previous, age):
    """Read-only assessment; never infer a successful physical print from an API 200.

    A Bambu firmware may report a freshly named job as 'complete' without ever
    heating, moving or extruding. This is a possible rejected command, not success.
    """
    if not isinstance(previous, dict) or not isinstance(age, (int, float)) or age < 0:
        return "none"
    path = previous.get("path")
    if not _safe_virtual_path(path):
        return "none"
    expected = path.rsplit("/", 1)[-1].lower()
    reported = str(status.get("file") or "").lower()
    matches = bool(reported and (expected in reported or expected[:-4] in reported))
    state = str(status.get("state") or "").lower()
    # Bambu Connect handoff waits for an explicit confirmation in the desktop app.
    # An unrelated old printer error is not evidence that this handoff failed.
    if previous.get("start_ack") == "bambu_connect_handoff" and not matches:
        return "handoff_pending"
    if matches and state in ("printing", "warmingup", "resuming", "paused"):
        return "active"
    if age < 20:
        return "pending"
    if matches and state == "complete":
        elapsed = status.get("elapsed_sec")
        layer = status.get("current_layer")
        hotend = status.get("hotend_target")
        bed = status.get("bed_target")
        no_duration = elapsed is None or elapsed < 2
        no_layers = layer is None or layer == 0
        no_heat = all(value is None or value <= 0 for value in (hotend, bed))
        if no_duration and no_layers and no_heat:
            return "instant_finish"
        return "unverified_finish"
    if state == "error":
        return "printer_error"
    if not matches and age >= 30:
        return "not_started"
    return "pending"


def _available_ams_sources():
    """Read-only, native AMS mapping numbers; do not infer tray indexes."""
    status = _api("/status?IncludeMaterialSystem=true", timeout=10)
    material_system = ((status.get("JobStatus") or {}).get("MaterialSystem") or {})
    if not isinstance(material_system, dict):
        return []
    units = {str(u.get("Id")): str(u.get("Name") or "")[:60]
             for u in (material_system.get("Units") or [])[:8] if isinstance(u, dict)}
    sources = []
    seen = set()
    for item in (material_system.get("Sources") or [])[:64]:
        if not isinstance(item, dict) or item.get("IsEmpty") is True:
            continue
        value = item.get("PrintMappingValue")
        if type(value) is not int or not 0 <= value <= 255 or value in seen:
            continue
        spool = item.get("Material") or {}
        if not isinstance(spool, dict):
            continue
        color = str(spool.get("ColorHex") or "").strip().lstrip("#")
        material = str(spool.get("Type") or "").upper().strip()[:32]
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", color) or not material:
            continue
        name = str(item.get("Name") or "Emplacement")[:65]
        unit = units.get(str(item.get("UnitId")))
        if unit and not name.lower().startswith(unit.lower()):
            name = unit + " · " + name
        sources.append({"mapping": value, "slot": name, "color": "#" + color.upper(),
                        "material": material, "name": str(spool.get("Name") or material)[:65]})
        seen.add(value)
    return sources


def _verify_native_start_reply(reply):
    """An upstream 200 is only transport success; reject explicit Bambu failures.

    Some firmware rejects a privileged MQTT command asynchronously, so absence
    of an error here is NOT proof the printer physically started printing.
    """
    native = reply.get("PrinterResponse") if isinstance(reply, dict) else None
    if not isinstance(native, dict):
        return
    message = native.get("print") if isinstance(native.get("print"), dict) else native
    result = str(message.get("result") or "").strip().lower()
    code = message.get("err_code")
    # Firmware may return the verification code without a 'result: failed'
    # string, or serialize it as a number-as-text. Do not accept that as OK.
    code_text = str(code).strip() if code is not None else ""
    try:
        code_number = int(code_text, 0) if code_text.startswith(("0x", "0X")) else int(code_text)
    except (ValueError, TypeError):
        code_number = 0
    if code_number in (84033543, 84033545, 84033546):
        raise PrinterError(
            "La X2D a refusé une commande MQTT nécessitant une vérification "
            "(code {}). Le relais a bien répondu, mais aucun départ n'est confirmé. "
            "Lance le 3MF déjà transféré sur l'écran de la X2D; "
            "ne renvoie pas la commande en boucle.".format(code_number)
        )
    if result not in ("fail", "failed", "error", "rejected") and not code_number:
        return
    if code_number or result in ("fail", "failed", "error", "rejected"):
        raise PrinterError(
            "La réponse native de la X2D indique que le démarrage a été refusé. "
            "Vérifie les messages sur l'écran de l'imprimante."
        )


def register_printer_admin(app, admin_required, verify, csrfinput, page, db=None):
    # Private, read-only camera snapshots proxied through the server so printer
    # credentials never reach the browser. OctoEverywhere supports Bambu webcams.
    def webcam_snapshot():
        base = _connection()
        headers = {"Accept": "image/jpeg", "User-Agent": "Fjord-Atelier-Admin/1"}
        bearer = os.environ.get("OCTOEVERYWHERE_AUTH_BEARER_TOKEN", "").strip()
        basic_user = os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_USER", "").strip()
        basic_pass = os.environ.get("OCTOEVERYWHERE_AUTH_BASIC_PASSWORD", "")
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        elif basic_user and basic_pass:
            credentials = (basic_user + ":" + basic_pass).encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
        req = urllib.request.Request(
            base + "/octoeverywhere-command-api/webcam/snapshot",
            headers=headers, method="GET")
        try:
            with urllib.request.build_opener(_NoRedirect).open(req, timeout=12) as resp:
                content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "image/jpeg":
                    raise PrinterError("La caméra n'a pas retourné d'image JPEG.")
                image = resp.read(5 * 1024 * 1024 + 1)
        except PrinterError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PrinterError("La caméra X2D ne répond pas par OctoEverywhere.") from exc
        if not image or len(image) > 5 * 1024 * 1024:
            raise PrinterError("L'image de la caméra est vide ou trop volumineuse.")
        return image

    @app.get("/admin/imprimante-camera")
    @admin_required
    def admin_printer_camera():
        return page("Caméra X2D", """
        <section class="card" style="max-width:1000px;margin:auto">
          <p><a href="/admin">← Retour à l’administration</a></p>
          <h1>📷 Caméra de l’imprimante X2D</h1>
          <p>Vue à distance via OctoEverywhere. L’image se rafraîchit automatiquement environ toutes les 2 secondes.</p>
          <div id="fjord-camera-status" role="status" style="padding:10px;border-radius:10px;background:#263746;margin:12px 0">Connexion à la caméra…</div>
          <div style="background:#05090d;border-radius:12px;overflow:hidden;text-align:center;min-height:240px;display:grid;place-items:center">
            <img id="fjord-camera-image" src="/admin/imprimante-camera/snapshot" alt="Vue en direct de l’imprimante X2D" style="display:block;width:100%;height:auto;max-height:75vh;object-fit:contain">
          </div>
          <p style="opacity:.8">Si l’image reste noire ou ne se charge pas, vérifie que le PC/pont OctoEverywhere et la caméra de la X2D sont en ligne.</p>
        </section>
        <script>
        (() => {
          const img = document.getElementById("fjord-camera-image");
          const status = document.getElementById("fjord-camera-status");
          const update = () => { img.src = "/admin/imprimante-camera/snapshot?t=" + Date.now(); };
          img.onload = () => { status.textContent = "✅ Caméra connectée · actualisation automatique"; status.style.background = "#14513e"; };
          img.onerror = () => { status.textContent = "⚠️ Image indisponible · nouvelle tentative automatique"; status.style.background = "#6a3b26"; };
          window.setInterval(update, 2200);
        })();
        </script>
        """)

    @app.get("/admin/imprimante-camera/snapshot")
    @admin_required
    def admin_printer_camera_snapshot():
        try:
            image = webcam_snapshot()
        except PrinterError as exc:
            return Response(str(exc), status=503, content_type="text/plain; charset=utf-8",
                            headers={"Cache-Control": "no-store"})
        return Response(image, status=200, content_type="image/jpeg",
                        headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

    # The schema lives with the normal app migrations in app.py.
    # Admin-only start metadata is shared, but never the one-use nonce.

    def latest_start():
        previous = session.get("fjord_atelier_recent_start")
        if not isinstance(previous, dict):
            previous = None
        if db is not None:
            try:
                with db() as conn:
                    row = conn.execute(
                        "SELECT file_path,start_ack,sent_at FROM fjord_printer_recent_start WHERE slot=1"
                    ).fetchone()
                if row is not None:
                    shared = {"path": row["file_path"], "start_ack": row["start_ack"],
                              "time": float(row["sent_at"])}
                    if _safe_virtual_path(shared["path"]) and (
                        previous is None or shared["time"] >= float(previous.get("time", 0))
                    ):
                        previous = shared
            except (ValueError, TypeError, OverflowError):
                pass
            except Exception:
                # Printing status must remain readable even if DB sync is down.
                app.logger.warning("Suivi X2D partagé momentanément indisponible.")
        return previous

    def remember_start(path, ack):
        record = {"time": time.time(), "path": path, "start_ack": ack}
        session["fjord_atelier_recent_start"] = record
        if db is not None:
            try:
                with db() as conn:
                    conn.execute(
                        """INSERT INTO fjord_printer_recent_start(slot,file_path,start_ack,sent_at)
                           VALUES(1,%s,%s,%s)
                           ON CONFLICT (slot) DO UPDATE SET
                           file_path=EXCLUDED.file_path,
                           start_ack=EXCLUDED.start_ack,
                           sent_at=EXCLUDED.sent_at""",
                        (path, ack, record["time"]))
            except Exception:
                # An already relayed command must never be retried just because
                # a separate tracking database write failed.
                app.logger.warning("Commande X2D relayée; synchronisation multiécran indisponible.")

    # Parsed user presets are intentionally not assumed to be machine-ready.
    def available_presets():
        from bambu_stock_profiles import available_original_presets
        result = available_original_presets()
        if db is None:
            return result
        from bambu_auto import full_preset, AutoSliceError
        with db() as conn:
            rows = conn.execute(
                "SELECT id,name,category,settings FROM bambu_user_presets ORDER BY category,name LIMIT 1000"
            ).fetchall()
        for row in rows:
            category = row["category"]
            if category not in result:
                continue
            try:
                data = full_preset(row["settings"], category)
            except (AutoSliceError, TypeError, ValueError):
                continue
            # Hide archived machine presets for other printers from the X2D launcher.
            # Keep originals in the archive for recovery; never silently delete data.
            if category == "Imprimante":
                model = data.get("printer_model", "")
                model = model[0] if isinstance(model, list) and model else model
                if not isinstance(model, str) or "X2D" not in model.upper():
                    continue
            elif category == "Filament":
                kind = data.get("filament_type", "")
                kind = kind[0] if isinstance(kind, list) and kind else kind
                normalized = re.sub(r"[^A-Z0-9]", "", str(kind).upper())
                if normalized not in {"PLA", "PETG", "PETGCF", "ASA", "TPU"}:
                    continue
            # Only non-sensitive profile metadata is sent to the administrator.
            def plain(key):
                value = data.get(key)
                if isinstance(value, list):
                    value = value[0] if value else ""
                return str(value or "")[:65]
            entry = {"id": row["id"], "name": row["name"]}
            if category == "Imprimante":
                entry["nozzle"] = plain("nozzle_diameter")
                entry["model"] = plain("printer_model")
            elif category == "Filament":
                entry["material"] = plain("filament_type").upper()
            else:
                entry["layer"] = plain("layer_height")
            result[category].append(entry)
        return result

    @app.get("/api/admin/atelier/impression-profils")
    @admin_required
    def fjord_print_profiles():
        from bambu_auto import cli_location
        response = jsonify({
            "engine_ready": bool(cli_location()),
            "profiles": available_presets(),
            "message": ("Bambu Studio disponible" if cli_location() else
                        "Moteur Bambu Studio à installer et valider sur Render"),
        })
        response.headers["Cache-Control"] = "no-store"
        return response

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
        from bambu_auto import cli_location
        auto_engine_ready = bool(cli_location())
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
/* Compact mobile-first console: retain all explicit safety confirmations. */
.fj-print-hero{padding:16px 18px;margin-bottom:12px;align-items:center}
.fj-print-hero p{margin-top:3px}
.fj-print-nav a{min-height:40px}
.fj-print-step-bar{margin-bottom:12px}
.fj-print-step-bar>div{padding:8px 10px}
.fj-print-card{padding:16px}
.fj-print-layout,.fj-print-col{gap:12px}
.fj-print-guide{margin-top:0}
.fj-print-guide ol{line-height:1.5}
@media(max-width:540px){
 .fj-print-hero{padding:13px 14px}
 .fj-print h1{font-size:24px;margin-bottom:4px}
 .fj-print-kicker{font-size:10px;margin-bottom:5px}
 .fj-print-nav{gap:6px}
 .fj-print-nav a{font-size:12px;padding:8px;flex:1}
 .fj-print-step-bar{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}
 .fj-print-step-bar>div{padding:7px 5px;font-size:11px;gap:5px;min-height:38px}
 .fj-print-step-bar strong{width:22px;height:22px;flex-basis:22px;font-size:12px}
 .fj-print-card{padding:13px}
 .fj-print-card h2{font-size:17px}
 .fj-print-guide{display:none}
 .fj-print-bottom{font-size:11px}
}
</style>
<div class="fj-print" id="fjordPrintPage">
  <section class="fj-print-hero" aria-labelledby="fjordPrintTitle">
    <div>
      <div class="fj-print-kicker">Les Impressions du Fjord · Atelier privé</div>
      <h1 id="fjordPrintTitle">🖨️ Imprimer sur ma X2D</h1>
      <p>Choisis ton fichier, vérifie la X2D et démarre.</p>
    </div>
    <nav class="fj-print-nav" aria-label="Navigation Atelier 3D">
      <a href="/admin/atelier-3d">← Retour à l’Atelier</a>
      <a href="/admin/profils-bambu">⚙️ Mes profils Bambu</a>
      <a href="/api/admin/atelier/impression-diagnostic" target="_blank" rel="noopener">🔎 Diagnostic X2D</a>
      <a href="/admin/atelier-pont">🔗 Pont Bambu Connect</a>
      <a href="/admin/imprimante-camera">📷 Caméra X2D en direct</a>
    </nav>
  </section>

  <section class="fj-print-card" id="fjordAutoSliceCard" style="margin-bottom:18px" aria-labelledby="fjordAutoSliceTitle">
    <div class="fj-print-step-title"><span class="fj-print-number" aria-hidden="true">★</span>
      <h2 id="fjordAutoSliceTitle">Préparer une pièce dans l’Atelier</h2></div>
    <p>Pour un STL ou une création 3D, ouvre l’Atelier et choisis « Préparer sur ma X2D ». Pour un 3MF Bambu déjà tranché, envoie-le directement ci-dessous.</p>
    {% if auto_engine_ready %}
      <div class="fj-print-notice" role="status">Bambu Studio disponible pour préparer tes modèles.</div>
    {% else %}
      <div class="fj-print-notice error" role="status">Moteur Bambu Studio absent sur ce déploiement Render : tranchage automatique désactivé jusqu’à son installation et à la validation de profils complets. Tu peux toujours envoyer un 3MF déjà tranché.</div>
    {% endif %}
    <a class="fj-print-refresh" style="display:inline-block;margin-top:12px" href="/admin/atelier-3d">Ouvrir l’Atelier 3D</a>
  </section>
  <div class="fj-print-step-bar" aria-label="Étapes d’impression">
    <div><strong aria-hidden="true">1</strong><span>Préparer</span></div>
    <div><strong aria-hidden="true">2</strong><span>Envoyer</span></div>
    <div><strong aria-hidden="true">3</strong><span>Démarrer</span></div>
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
      <div id="fjordStartMonitor" hidden role="status" aria-live="polite" style="grid-column:1/-1;padding:13px 15px;border:1px solid #4b8caa;border-radius:11px;background:#163a4b;color:#e9f8ff;line-height:1.5">
        <strong id="fjordStartMonitorTitle">Vérification du démarrage</strong>
        <p id="fjordStartMonitorMessage" style="margin:5px 0 0;color:inherit"></p>
        <progress id="fjordStartMonitorProgress" max="100" value="0" hidden style="width:100%;max-width:none;height:10px;accent-color:#49bda2"></progress>
        <small id="fjordStartMonitorDetails" style="display:block;margin-top:5px"></small>
      </div>
      <a class="fj-print-refresh" href="/admin/atelier-imprimer">↻ Actualiser</a>
    </section>

    <div class="fj-print-col">
      <section class="fj-print-card" aria-labelledby="fjordUploadTitle">
        <div class="fj-print-step-title">
          <span class="fj-print-number" aria-hidden="true">2</span>
          <h2 id="fjordUploadTitle">1 · Envoyer mon 3MF</h2>
        </div>
        <p class="fj-print-intro">Fichier 3MF tranché avec Bambu Studio seulement.</p>
        <form method="post" action="/admin/atelier-imprimer/envoyer" enctype="multipart/form-data">
          {{csrf_field|safe}}
          <label for="fjordPrintUpload">Mon fichier Bambu Studio (.3mf)
            <input id="fjordPrintUpload" type="file" name="sliced_file" accept=".3mf" required>
          </label>
          <div id="fjordPrintFileName" class="fj-print-chip" role="status">Aucun fichier sélectionné</div>
          <div id="fjordUploadProgress" hidden aria-live="polite" style="display:grid;gap:7px">
            <progress max="100" value="0" style="width:100%;height:12px;accent-color:#49bda2"></progress>
            <div id="fjordUploadStatus" class="fj-print-notice" role="status" style="margin:0">Prêt à envoyer.</div>
          </div>
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
        <h2 id="fjordStartTitle">2 · Démarrer l’impression</h2>
      </div>
      <p class="fj-print-intro">Choisis ton fichier, confirme que le plateau est libre, puis démarre.</p>
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
            <span>J’ai vérifié le matériau, l’AMS et le tranchage.</span></label>
          <label class="fj-print-check"><input type="checkbox" name="cleared" value="yes" required>
            <span>Le plateau est libre et je peux surveiller le lancement.</span></label>
        </div>
        <button class="fj-print-start" type="submit"
          {% if not status or not status.can_start %}disabled{% endif %}>
          ▶ Démarrer sur ma X2D
        </button>
      </form>
      {% else %}
      <div class="fj-print-empty">Aucun fichier 3MF trouvé sur l’imprimante, ou impossible de consulter sa bibliothèque. Envoie un fichier compatible, puis clique sur « Actualiser ».</div>
      {% endif %}
      <p class="fj-print-hint">Si le pont Windows est connecté, le fichier sera remis à Bambu Connect : confirme l’imprimante et le lancement dans l’application. Sinon, le site utilisera le relais OctoEverywhere. Dans les deux cas, vérifie l’état réel de la X2D.</p>
    </section>
  </div>
  <p class="fj-print-bottom">Important : les profils sauvegardés dans l’Atelier ne sont pas encore un moteur de tranchage Bambu. L’impression directe d’un modèle créé dans l’Atelier nécessitera une intégration de tranchage compatible et vérifiée.</p>
</div>
<script>
(function(){
 const upload=document.getElementById('fjordPrintUpload');
 const label=document.getElementById('fjordPrintFileName');
 const form=upload?.form,progressBox=document.getElementById('fjordUploadProgress');
 const progress=progressBox?.querySelector('progress'),status=document.getElementById('fjordUploadStatus');
 const submit=form?.querySelector('button[type="submit"]');
 if(upload && label){
   upload.addEventListener('change',()=>{
     const file=upload.files && upload.files[0];
     label.textContent=file ? file.name+' · '+(file.size/1048576).toFixed(1)+' Mo' : 'Aucun fichier sélectionné';
   });
 }
 if(!form||!upload||!progressBox||!progress||!status)return;
 form.addEventListener('submit',event=>{
   event.preventDefault();
   if(!upload.files?.length)return;
   progressBox.hidden=false;progress.value=0;status.classList.remove('error');
   status.textContent='Envoi du fichier au site : 0 %';
   if(submit){submit.disabled=true;submit.textContent='⏳ Envoi en cours…'}
   const xhr=new XMLHttpRequest();xhr.open('POST',form.action,true);
   xhr.setRequestHeader('Accept','application/json');
   xhr.upload.addEventListener('progress',event=>{
     if(!event.lengthComputable)return;
     const percent=Math.min(100,Math.round(event.loaded/event.total*100));
     progress.value=percent;
     status.textContent=percent<100?'Envoi du fichier au site : '+percent+' %':'Fichier reçu. Vérification du 3MF et transfert vers la X2D en cours…';
   });
   xhr.addEventListener('load',()=>{
     let result={};try{result=JSON.parse(xhr.responseText||'{}')}catch(_){}
     if(xhr.status>=200&&xhr.status<300&&result.ok&&result.next){
       progress.value=100;status.textContent='✓ Fichier transféré. Ouverture de l’écran de confirmation…';
       window.location.assign(result.next);return;
     }
     status.classList.add('error');
     status.textContent=result.error||'Le transfert a échoué (HTTP '+xhr.status+'). Aucun démarrage n’a été confirmé.';
     if(submit){submit.disabled=false;submit.textContent='↻ Réessayer l’envoi'}
   });
   xhr.addEventListener('error',()=>{
     status.classList.add('error');status.textContent='Connexion interrompue. Actualise l’état de la X2D avant de réessayer.';
     if(submit){submit.disabled=false;submit.textContent='↻ Réessayer l’envoi'}
   });
   xhr.addEventListener('timeout',()=>{
     status.classList.add('error');status.textContent='Le délai d’envoi est dépassé. Actualise l’état de la X2D avant de réessayer.';
     if(submit){submit.disabled=false;submit.textContent='↻ Réessayer l’envoi'}
   });
   xhr.timeout=120000;xhr.send(new FormData(form));
 });
})();
</script>
<script>
(() => {
 const box=document.getElementById('fjordStartMonitor');
 const title=document.getElementById('fjordStartMonitorTitle');
 const message=document.getElementById('fjordStartMonitorMessage');
 const details=document.getElementById('fjordStartMonitorDetails');
 const bar=document.getElementById('fjordStartMonitorProgress');
 if(!box||!title||!message||!details||!bar)return;
 let busy=false,stopped=false;
 const labels={
  handoff_pending:['En attente de Bambu Connect','Le fichier a été remis au PC, mais la X2D ne confirme pas encore son démarrage. Dans Bambu Connect, termine l’importation, sélectionne la X2D et confirme l’impression.'],
  pending:['Vérification du départ en cours','La commande a été envoyée. Le démarrage réel n’est pas encore confirmé par la X2D.'],
  active:['Impression confirmée sur la X2D','La X2D signale maintenant ce fichier comme tâche active.'],
  instant_finish:['Départ non confirmé','La X2D affiche la tâche comme terminée sans durée, couche ni chauffe suffisante. Le démarrage n’est pas confirmé.'],
  unverified_finish:['État final à vérifier','La tâche n’est plus active, mais les données de la X2D ne permettent pas de confirmer clairement le résultat.'],
  printer_error:['Erreur signalée par la X2D','La X2D signale une erreur. Consulte son écran avant de renvoyer une commande.'],
  not_started:['Impression non démarrée','Aucun démarrage correspondant n’a été observé sur la X2D.'],
  none:['Aucun nouveau départ à vérifier','Aucune commande récente n’est en cours de vérification.']
 };
 const stop=()=>{stopped=true};
 async function refresh(){
  if(busy||stopped)return;
  busy=true;
  try{
   const response=await fetch('/api/admin/atelier/impression-etat?live='+Date.now(),{cache:'no-store',credentials:'same-origin'});
   if(!response.ok)throw new Error('État indisponible');
   const data=await response.json();
   const age=Number(data.start_command_age_sec);
   if(!data.ok||!data.shared_job||!Number.isFinite(age)||age>600){
    box.hidden=true;stop();return;
   }
   box.hidden=false;
   const outcome=data.start_outcome||'pending';
   const copy=labels[outcome]||labels.pending;
   title.textContent=copy[0];message.textContent=copy[1];
   const file=String(data.shared_job.file||'').split('/').pop();
   const progress=data.progress;
   bar.hidden=outcome!=='active'||typeof progress!=='number'||!Number.isFinite(progress);
   if(!bar.hidden)bar.value=Math.max(0,Math.min(100,progress));
   const layer=Number.isFinite(Number(data.current_layer))&&Number(data.current_layer)>0
    ?' · Couche '+data.current_layer+(Number(data.total_layers)>0?' / '+data.total_layers:''):'';
   details.textContent=(file?'Fichier : '+file:'')+(outcome==='active'&&Number.isFinite(progress)?' · '+Math.round(progress)+' %':'')+layer;
   if(outcome==='printer_error'&&data.printer_error)details.textContent+=' · '+String(data.printer_error).slice(0,180);
  }catch(error){
   box.hidden=false;title.textContent='État en direct indisponible';
   message.textContent='Je n’ai pas pu relire la X2D. Clique sur « Actualiser » pour vérifier à nouveau.';
  }finally{busy=false}
 }
 refresh();
 const timer=window.setInterval(()=>{if(document.visibilityState==='visible')refresh()},8000);
 window.setTimeout(()=>{window.clearInterval(timer)},600000);
})();
</script>
""",csrf_field=csrfinput(),nonce=token,status=status,files=files,error=error,
           selected=request.args.get("selected",""),messages=get_flashed_messages(),
           auto_engine_ready=auto_engine_ready)

    @app.post("/admin/atelier-imprimer/preparer")
    @admin_required
    def fjord_print_auto_prepare():
        """Slice official Bambu 3MF and stage for owner review; never upload here."""
        from bambu_auto import cli_location, full_preset, slice_x2d, AutoSliceError, MAX_STL, BED_TYPES, SUPPORT_MODES
        from fjord_slice_review import stage_slice, SliceReviewError
        request.max_content_length = MAX_STL + 2 * 1024 * 1024
        verify()
        try:
            if not cli_location():
                raise AutoSliceError("Moteur Bambu Studio absent sur Render. Aucun fichier envoyé.")
            upload = request.files.get("stl")
            if upload is None or not str(upload.filename or "").lower().endswith(".stl"):
                raise AutoSliceError("Fichier STL invalide.")
            raw = upload.stream.read(MAX_STL + 1)
            bed_type = request.form.get("bed_type", "")
            if bed_type not in BED_TYPES:
                raise AutoSliceError("Choisis le type de plaque réellement installé sur ta X2D.")
            # Stock presets are bundled with Bambu Studio and don't depend on
            # a user's imported profile archive/database.
            from bambu_stock_profiles import STOCK_NAMES, original_preset
            choices = {}
            for category, field in (("Imprimante","machine"),("Impression","process"),
                                    ("Filament","filament")):
                value = request.form.get(field, "")
                if value in STOCK_NAMES[category]:
                    choices[category] = ("stock", value)
                elif value.isdecimal() and 0 < int(value) < 10000000:
                    choices[category] = ("user", int(value))
                else:
                    raise AutoSliceError("Choisis un profil d'origine Bambu ou un profil complet valide.")
            presets = {}
            for category, (kind, selected) in choices.items():
                if kind == "stock":
                    presets[category] = original_preset(category, selected)
            own_ids = [selected for kind, selected in choices.values() if kind == "user"]
            if own_ids:
                if db is None:
                    raise AutoSliceError("Bibliothèque de profils personnalisés indisponible.")
                with db() as conn:
                    rows = conn.execute(
                        "SELECT id,name,category,settings FROM bambu_user_presets "
                        "WHERE id = ANY(%s)", (own_ids,)
                    ).fetchall()
                for row in rows:
                    cat = row["category"]
                    selection = choices.get(cat)
                    if selection == ("user", row["id"]):
                        presets[cat] = full_preset(row["settings"], cat)
            if len(presets) != 3:
                raise AutoSliceError("Les trois profils choisis ne sont pas complets ou disponibles.")
            # Never silently swap PLA/PETG/ASA/TPU for a different material.
            expected_material = str(request.form.get("material", "")).strip().upper()
            if expected_material not in ("PLA", "PETG", "PETG-CF", "ASA", "TPU"):
                raise AutoSliceError("Choisis explicitement le matériau PLA, PETG, PETG-CF, ASA ou TPU dans l'Atelier.")
            actual = full_preset(presets["Filament"], "Filament")["filament_type"]
            if isinstance(actual, list):
                actual = actual[0] if actual else ""
            if str(actual).strip().upper() != expected_material:
                raise AutoSliceError("Profil filament incompatible avec le matériau de l'Atelier : aucun transfert.")
            # Only supported process overrides can reach the official Bambu CLI.
            support_mode = request.form.get('support_mode', 'off')
            plate_only_value = request.form.get('support_plate_only', '0')
            if support_mode not in SUPPORT_MODES or plate_only_value not in ('0', '1'):
                raise AutoSliceError('Réglages de supports automatiques invalides.')
            support_plate_only = plate_only_value == '1'
            # Stage only: do not contact OctoEverywhere until explicit review.
            sliced = slice_x2d(raw, presets, verify_sliced_bambu_3mf,
                               bed_type=bed_type, support_mode=support_mode,
                               support_plate_only=support_plate_only)
            token, preview = stage_slice(sliced, verify_sliced_bambu_3mf)
            success = "Tranchage Bambu terminé. Examine les couches avant d’envoyer à la X2D."
            if request.accept_mimetypes.best == "application/json":
                response = jsonify(ok=True, stage=token, preview=preview, message=success,
                                   support_mode=support_mode,
                                   support_plate_only=support_plate_only)
                response.headers["Cache-Control"] = "no-store"
                return response
            flash("3MF prêt pour l’aperçu dans l’Atelier administrateur. Aucun fichier envoyé.")
            return redirect(url_for("fjord_printer_page"))
        except (AutoSliceError, SliceReviewError, PrinterError) as exc:
            if request.accept_mimetypes.best == "application/json":
                return jsonify(ok=False, error=str(exc)), 422
            flash(str(exc))
            return redirect(url_for("fjord_printer_page"))

    @app.post("/admin/atelier-imprimer/telecharger-3mf")
    @admin_required
    def fjord_download_reviewed_3mf():
        """Download the session-bound, verified slicer output; no printer contact."""
        from fjord_slice_review import get_staged, SliceReviewError
        request.max_content_length = 128 * 1024
        verify()
        try:
            raw = get_staged(str(request.form.get("stage", "")))
            verify_sliced_bambu_3mf(raw)
        except (PrinterError, SliceReviewError) as exc:
            return jsonify(ok=False, error=str(exc)), 422
        response = send_file(
            io.BytesIO(raw), as_attachment=True, download_name="Creation-du-Fjord-X2D-tranche.gcode.3mf",
            mimetype="model/3mf", max_age=0
        )
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post("/admin/atelier-imprimer/transmettre")
    @admin_required
    def fjord_print_review_transfer():
        """Second explicit action: upload a reviewed 3MF, never start printer."""
        from fjord_slice_review import get_staged, consume_staged, SliceReviewError
        request.max_content_length = 128 * 1024
        verify()
        try:
            token = str(request.form.get("stage",""))
            staged = get_staged(token)
            verify_sliced_bambu_3mf(staged)
            printer = _status()
            if not printer["can_start"]:
                raise PrinterError("X2D occupée ou indisponible : aucune transmission.")
            virtual_path = "gcode/fjord_auto_" + secrets.token_hex(6) + ".3mf"
            _upload(virtual_path, staged)
            bridge_job_id = ""
            if db is not None:
                bridge_job_id = secrets.token_urlsafe(24)
                try:
                    from fjord_bambu_connect import store_file
                    store_file(db, bridge_job_id, virtual_path,
                               virtual_path.rsplit("/", 1)[-1],
                               str(request.form.get("material", "")).strip().upper()[:32],
                               staged)
                except Exception as exc:
                    app.logger.exception("Préparation du pont Bambu Connect indisponible.")
                    raise PrinterError("Le 3MF est transféré, mais le pont Bambu Connect n'a pas pu préparer le fichier. Vérifie le pont puis réessaie.") from exc
            session.pop("fjord_last_upload_diagnostic", None)
            consume_staged(token)
            # Trust only the exact uploaded path returned by the printer.
            # Token is session-bound, short-lived and consumed by start.
            start_nonce = secrets.token_urlsafe(32)
            session["fjord_atelier_start"] = {
                "path": virtual_path, "nonce": start_nonce, "time": time.time(),
                "material": str(request.form.get("material", "")).strip().upper()[:32],
                "bridge_job_id": bridge_job_id
            }
            message = "3MF tranché envoyé. Vérifie les matériaux et le plateau avant le démarrage."
            next_page = url_for("fjord_printer_page", selected=virtual_path)
            if request.accept_mimetypes.best == "application/json":
                response = jsonify(ok=True, file=virtual_path, nonce=start_nonce,
                                   next=next_page, message=message)
                response.headers["Cache-Control"] = "no-store"
                return response
            flash(message)
            return redirect(next_page)
        except (PrinterError, SliceReviewError) as exc:
            # Preserve only the sanitized status returned to the admin browser.
            # Never retain raw FTPS logs, credentials, URLs or exception data.
            if isinstance(exc, PrinterError) and "OctoEverywhere (752)" in str(exc):
                session["fjord_last_upload_diagnostic"] = {
                    "at": time.time(), "hint": str(exc)[:420]
                }
            if request.accept_mimetypes.best == "application/json":
                return jsonify(ok=False, error=str(exc)), 422
            flash(str(exc))
            return redirect(url_for("fjord_printer_page"))

    @app.get("/api/admin/atelier/impression-diagnostic")
    @admin_required
    def fjord_printer_atelier_diagnostic():
        """Read-only checks: OctoEverywhere status and Bambu gcode file listing.

        Never upload a test file or send printer movement/start commands.
        Admin-only, short timeout, no private connection URLs or filenames.
        """
        checks = {"status": False, "files": False}
        details = []
        previous_start = latest_start()
        last_path = previous_start.get("path") if isinstance(previous_start, dict) else None
        if not _safe_virtual_path(last_path):
            last_path = None
        recent_start_age = None
        if isinstance(previous_start, dict):
            try:
                age = time.time() - float(previous_start.get("time", 0))
                if 0 <= age <= 24 * 3600:
                    recent_start_age = round(age)
            except (TypeError, ValueError, OverflowError):
                pass
        printer_state = None
        printer_error = ""
        printer_file = ""
        printer_elapsed = None
        printer_layer = None
        printer_targets = {}
        printer_substate = ""
        file_present = None
        for key, operation in (
            ("status", lambda: _api("/status", timeout=8)),
            ("files", lambda: _api("/files/list", timeout=12)),
        ):
            try:
                result = operation()
                if key == "status":
                    job = result.get("JobStatus")
                    checks[key] = isinstance(job, dict)
                    if checks[key]:
                        printer_state = str(job.get("State") or "inconnu").lower()[:36]
                        printer_error = str(job.get("Error") or "")[:120]
                        current_print = job.get("CurrentPrint") or {}
                        printer_file = str(current_print.get("FileName") or "")[:120]
                        printer_substate = str(job.get("SubState") or "")[:70]
                        elapsed = current_print.get("DurationSec")
                        printer_elapsed = elapsed if type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= 31_536_000 else None
                        layer = current_print.get("CurrentLayer")
                        printer_layer = layer if type(layer) is int and 0 <= layer <= 1_000_000 else None
                        targets = current_print.get("Temps") or {}
                        if isinstance(targets, dict):
                            for temp_key in ("BedTarget", "HotendTarget"):
                                value = targets.get(temp_key)
                                if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 500:
                                    printer_targets[temp_key] = round(value, 1)
                else:
                    checks[key] = isinstance(result.get("Root"), list)
                    if checks[key] and last_path and recent_start_age is not None:
                        file_present = any(row["path"] == last_path
                                           for row in _printer_files(result))
                if not checks[key]:
                    details.append(("État" if key == "status" else "Fichiers")
                                   + " : réponse incomplète.")
            except PrinterError as exc:
                details.append(("État" if key == "status" else "Fichiers")
                               + " : " + str(exc)[:150])
        # Inspect only a tail of remote plugin logs; never send raw log text.
        log_hint = _plugin_log_hint()
        if checks["status"] and checks["files"]:
            if file_present is True:
                # A fresh verified file listing is stronger than generic FTPS
                # troubleshooting. Focus on the native print-start command.
                diagnosis = (
                    "La X2D répond et le 3MF récemment envoyé est présent dans ses fichiers. "
                    "Le transfert a réussi; il reste à confirmer l'exécution du démarrage. "
                    + (log_hint or
                       "Aucune erreur exploitable dans les dernières lignes du journal. "
                       "Si la machine refuse le départ, consulte l'écran de la X2D "
                       "pour un éventuel code de vérification MQTT.")
                )
            else:
                diagnosis = (
                    "La connexion d'état et la consultation des fichiers répondent. "
                    "Une réponse de lecture ne prouve pas que la dernière commande de départ a été exécutée. "
                    + (log_hint or
                       "Aucun détail exploitable dans les dernières lignes du journal. "
                       "Sur la X2D, vérifie d'abord la présence d'une clé USB lisible "
                       "et son espace libre, puis les journaux du conteneur.")
                )
        elif checks["status"]:
            diagnosis = (
                "La connexion d'état répond, mais l'accès aux fichiers de la X2D échoue. "
                "Vérifie la connexion FTP/FTPS locale, le code d'accès et la configuration "
                "du conteneur OctoEverywhere."
            )
        else:
            diagnosis = (
                "La connexion OctoEverywhere ne répond pas complètement. "
                "Vérifie que le conteneur et la X2D sont connectés."
            )
        job_matches_start = None
        if recent_start_age is not None and isinstance(previous_start, dict):
            acknowledgement = previous_start.get("start_ack")
            if acknowledgement == "relay_only":
                diagnosis += (
                    " La commande a obtenu une réponse 200 du relais, mais aucune "
                    "confirmation native de démarrage n'a été transmise."
                )
            elif acknowledgement == "bambu_connect_handoff":
                diagnosis += (
                    " Le 3MF a été remis au pont Windows. Confirme son envoi dans "
                    "Bambu Connect. L'état d'une ancienne tâche X2D ne permet pas "
                    "de conclure que ce nouveau fichier a échoué."
                )
            elif acknowledgement == "native_ok":
                diagnosis += (
                    " La réponse native était OK, sans preuve d'une impression physique."
                )
        if recent_start_age is not None and last_path:
            expected_name = last_path.rsplit("/", 1)[-1].lower()
            observed_name = printer_file.lower()
            job_matches_start = bool(
                expected_name and observed_name and
                (expected_name in observed_name or
                 expected_name.rsplit(".", 1)[0] in observed_name)
            )
            if job_matches_start and printer_state in ("printing", "warmingup", "resuming"):
                diagnosis += " La X2D rapporte une impression active correspondant au fichier transmis."
            elif job_matches_start and printer_state == "complete":
                diagnosis += " La X2D rapporte ce fichier comme terminé."
            elif recent_start_age >= 20 and not job_matches_start:
                if printer_state == "complete" and printer_file:
                    diagnosis += (
                        " ATTENTION : la X2D annonce 100 % sur un ANCIEN travail ("
                        + printer_file + "), différent du 3MF récemment envoyé. "
                        "La nouvelle impression n'est PAS confirmée. Vérifie l'écran "
                        "de la X2D et les refus éventuels de commande MQTT."
                    )
                elif printer_state in ("idle", "cancelled", "error"):
                    if acknowledgement == "bambu_connect_handoff":
                        diagnosis += (
                            " L'état « " + printer_state + " » concerne une tâche X2D "
                            "qui ne correspond pas au 3MF remis au PC; il est ignoré. "
                            "En attente de la confirmation dans Bambu Connect."
                        )
                    else:
                        diagnosis += (
                            " La commande reçue par le relais n'a pas déclenché de nouveau "
                            "travail confirmé : le départ réel n'est pas confirmé. "
                            "État X2D « " + printer_state + " »."
                        )
                else:
                    diagnosis += (
                        " La X2D ne signale pas de travail correspondant au fichier "
                        "envoyé. Ne confonds pas la progression d'une autre tâche avec "
                        "cette impression."
                    )
            elif not job_matches_start:
                diagnosis += " Départ du nouveau fichier encore non observé."
            if file_present is True:
                diagnosis += " Le dernier 3MF envoyé apparaît bien dans la liste des fichiers de la X2D."
            elif file_present is False:
                diagnosis += " Le dernier fichier envoyé n'est plus présent dans la liste de la X2D."
            # A named job that goes immediately to 'complete' without time,
            # layer or heat is a failed/unverified remote launch, not a success.
            if job_matches_start and printer_state == "complete":
                if ((printer_elapsed is None or printer_elapsed < 2)
                    and (printer_layer is None or printer_layer == 0)
                    and not any(value > 0 for value in printer_targets.values())):
                    diagnosis += (
                        " ALERTE : ce 3MF est signalé « terminé » sans durée, "
                        "couche ni chauffe détectable. Le démarrage distant "
                        "est probablement rejeté ou abandonné immédiatement. "
                        "Le fichier peut être lancé localement sur la X2D. "
                        "Les firmwares Bambu récents peuvent exiger une autorisation "
                        "MQTT signée pour les commandes distantes."
                    )
            handoff_waiting = (acknowledgement == "bambu_connect_handoff"
                               and not job_matches_start)
            if not handoff_waiting:
                if printer_elapsed is not None:
                    diagnosis += " Durée rapportée par la X2D : " + str(round(printer_elapsed)) + " s."
                if printer_layer is not None:
                    diagnosis += " Couche rapportée : " + str(printer_layer) + "."
                if printer_targets:
                    diagnosis += " Températures cibles rapportées : " + ", ".join(
                        label + " " + str(printer_targets[key]) + " °C"
                        for key, label in (("HotendTarget", "buse"), ("BedTarget", "plateau"))
                        if key in printer_targets
                    ) + "."
                if printer_substate:
                    diagnosis += " Sous-état : " + printer_substate
                if printer_error:
                    diagnosis += " Erreur rapportée par l'imprimante : " + printer_error
        prior = session.get("fjord_last_upload_diagnostic")
        previous_hint = ""
        if (isinstance(prior, dict) and
            0 <= time.time() - float(prior.get("at", 0)) < 3600):
            previous_hint = str(prior.get("hint", ""))[:420]
        ignore_stale_error = (
            isinstance(previous_start, dict)
            and previous_start.get("start_ack") == "bambu_connect_handoff"
            and job_matches_start is False
        )
        response = jsonify(ok=True, status_ok=checks["status"], files_ok=checks["files"],
                           diagnosis=diagnosis, details=details,
                           last_upload=previous_hint,
                           printer_state=printer_state,
                           printer_error=None if ignore_stale_error else printer_error,
                           recent_start_age_sec=recent_start_age,
                           start_ack=(previous_start.get("start_ack")
                                      if isinstance(previous_start, dict) else None),
                           recent_job_matches_start=job_matches_start,
                           reported_job_name=printer_file if recent_start_age is not None else None,
                           last_job_file_present=file_present)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/api/admin/atelier/ams-assignation")
    @admin_required
    def fjord_printer_ams_assignment():
        """Admin-only live AMS choices, without printer IDs or network credentials."""
        try:
            sources = _available_ams_sources()
            result = jsonify(ok=True, sources=sources,
                            note="Emplacements déclarés par la X2D. Les valeurs sont relues avant démarrage.")
        except PrinterError as exc:
            result = jsonify(ok=False, sources=[], error=str(exc))
            result.status_code = 503
        result.headers["Cache-Control"] = "private, no-store"
        return result

    @app.get("/api/admin/atelier/impression-etat")
    @admin_required
    def fjord_printer_atelier_status():
        """Read-only status used by Atelier while reviewing or starting prints."""
        try:
            status = _status()
            response = jsonify(ok=True, **{
                "state": status["state"],
                "progress": status["progress"],
                "file": status["file"],
                "can_start": status["can_start"],
                "time_left_sec": status.get("time_left_sec"),
                "elapsed_sec": status.get("elapsed_sec"),
                "hotend_actual": status.get("hotend_actual"),
                "hotend_target": status.get("hotend_target"),
                "bed_actual": status.get("bed_actual"),
                "bed_target": status.get("bed_target"),
                "current_layer": status.get("current_layer"),
                "total_layers": status.get("total_layers"),
                "substate": status.get("substate"),
                "printer_error": status.get("error")
            })
            previous = latest_start()
            if isinstance(previous, dict):
                age = time.time() - float(previous.get("time", 0))
                if 0 <= age <= 24 * 3600:
                    payload = response.get_json()
                    payload["start_command_age_sec"] = round(age)
                    payload["shared_job"] = {
                        "file": previous["path"], "age_sec": round(age),
                        "start_ack": previous.get("start_ack")
                    }
                    result_file = str(status["file"] or "").lower()
                    expected_name = str(previous.get("path", "")).rsplit("/", 1)[-1].lower()
                    payload["job_matches_start"] = bool(
                        expected_name and result_file and
                        (expected_name in result_file or
                         expected_name.rsplit(".", 1)[0] in result_file))
                    payload["start_ack"] = (previous.get("start_ack")
                                             if previous.get("start_ack") in ("native_ok", "relay_only", "bambu_connect_handoff")
                                             else None)
                    payload["start_outcome"] = _atelier_remote_start_outcome(status, previous, age)
                    if (previous.get("start_ack") == "bambu_connect_handoff"
                        and payload["job_matches_start"] is not True):
                        payload["printer_error"] = None
                    response = jsonify(payload)
        except PrinterError as exc:
            response = jsonify(ok=False, error=str(exc))
            response.status_code = 503
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/admin/atelier-imprimer/demarrer-atelier")
    @admin_required
    def fjord_printer_start_in_atelier():
        """Explicit launch of *only* the 3MF transferred in this admin session."""
        request.max_content_length = 128 * 1024
        verify()
        pending = session.pop("fjord_atelier_start", None)
        if (not isinstance(pending, dict)
            or not isinstance(request.form.get("nonce"), str)
            or not secrets.compare_digest(str(pending.get("nonce", "")), request.form["nonce"])
            or time.time() - float(pending.get("time", 0)) > 30 * 60):
            return jsonify(ok=False, error="Confirmation expirée : renvoie le 3MF depuis l’Atelier."), 422
        if request.form.get("verified") != "yes" or request.form.get("cleared") != "yes":
            return jsonify(ok=False, error="Confirme le filament, le plateau et la surveillance avant le départ."), 422
        path = pending.get("path")
        if not _safe_virtual_path(path):
            return jsonify(ok=False, error="Fichier à démarrer invalide."), 422
        try:
            status = _status()
            if not status["can_start"]:
                raise PrinterError("La X2D est occupée ou ne permet pas le démarrage.")
            listed = _printer_files(_api("/files/list"))
            if not any(item["path"] == path for item in listed):
                raise PrinterError("Le fichier préparé n’est pas présent sur la X2D.")
            use_ams = request.form.get("ams") == "yes"
            command = {"Path": path, "Plate": 1, "UseAms": use_ams}
            mapping_text = request.form.get("ams_mapping", "").strip()
            if mapping_text:
                if not use_ams or not re.fullmatch(r"\d{1,3}", mapping_text):
                    raise PrinterError("Assignation AMS invalide : aucune commande envoyée.")
                chosen_slot = int(mapping_text)
                if chosen_slot not in range(256):
                    raise PrinterError("Emplacement AMS invalide.")
                candidates = _available_ams_sources()
                selected = next((source for source in candidates
                                 if source["mapping"] == chosen_slot), None)
                if selected is None:
                    raise PrinterError("La bobine AMS n'est plus disponible : actualise les emplacements.")
                requested_material = str(pending.get("material") or "").strip().upper()
                if requested_material and selected["material"] != requested_material:
                    raise PrinterError("Le matériau de la bobine AMS ne correspond plus au fichier tranché.")
                command["AmsMapping"] = [chosen_slot]
            if db is not None:
                from fjord_bambu_connect import bridge_state, queue_file
                bridge = bridge_state(db)
                if bridge["paired"]:
                    if not bridge["online"]:
                        raise PrinterError("Le PC Bambu Connect est hors ligne. Ouvre le pont Windows avant de lancer.")
                    bridge_job_id = str(pending.get("bridge_job_id") or "")
                    if not bridge_job_id or not queue_file(db, bridge_job_id):
                        raise PrinterError("Le fichier n'est plus en attente pour Bambu Connect. Renvoie le 3MF depuis l'Atelier.")
                    remember_start(path, "bambu_connect_handoff")
                    result = jsonify(
                        ok=True,
                        message="Fichier remis au PC. Bambu Connect va s'ouvrir : confirme la X2D et le lancement dans l'application.",
                        start_ack="bambu_connect_handoff",
                        file=path
                    )
                    result.headers["Cache-Control"] = "no-store"
                    return result
            response = _api("/start", method="POST", payload=command, timeout=15)
            if response.get("VirtualPath") not in (None, path):
                raise PrinterError("La réponse de démarrage ne correspond pas au fichier préparé.")
            _verify_native_start_reply(response)
            native_reply = response.get("PrinterResponse")
            native_info = (native_reply.get("print")
                           if isinstance(native_reply, dict) and isinstance(native_reply.get("print"), dict)
                           else native_reply)
            native_result = (str(native_info.get("result") or "").lower().strip()
                             if isinstance(native_info, dict) else "")
            ack_kind = "native_ok" if native_result == "ok" else "relay_only"
            # Keep only a classification, not raw MQTT/native packets.
            remember_start(path, ack_kind)
            result = jsonify(
                ok=True,
                message=("Réponse native reçue : OK. La X2D doit encore confirmer le démarrage réel."
                         if ack_kind == "native_ok" else
                         "Commande reçue par le relais SANS confirmation native. "
                         "Aucun démarrage réel confirmé."),
                start_ack=ack_kind,
                file=path
            )
            result.headers["Cache-Control"] = "no-store"
            return result
        except PrinterError as exc:
            return jsonify(ok=False, error=str(exc)), 422

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
            bridge_job_id = ""
            if db is not None:
                bridge_job_id = secrets.token_urlsafe(24)
                from fjord_bambu_connect import store_file
                store_file(db, bridge_job_id, virtual_path,
                           virtual_path.rsplit("/", 1)[-1], "", raw)
                pending_jobs = session.get("fjord_print_bridge_jobs", {})
                if not isinstance(pending_jobs, dict):
                    pending_jobs = {}
                pending_jobs[virtual_path] = bridge_job_id
                session["fjord_print_bridge_jobs"] = dict(list(pending_jobs.items())[-12:])
            message = "Fichier tranché envoyé. Sélectionne-le puis confirme le démarrage. Si le pont Windows est connecté, Bambu Connect s’ouvrira sur son PC."
            next_page = url_for("fjord_printer_page", selected=virtual_path)
            if request.accept_mimetypes.best == "application/json":
                response = jsonify(ok=True, file=virtual_path, next=next_page, message=message)
                response.headers["Cache-Control"] = "no-store"
                return response
            flash(message)
            return redirect(next_page)
        except PrinterError as exc:
            if request.accept_mimetypes.best == "application/json":
                return jsonify(ok=False, error=str(exc)), 422
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
            if db is not None:
                from fjord_bambu_connect import bridge_state, queue_file
                bridge = bridge_state(db)
                if bridge["paired"]:
                    if not bridge["online"]:
                        raise PrinterError("Le PC Bambu Connect est associé, mais hors ligne. Ouvre le pont Windows avant de démarrer.")
                    pending_jobs = session.get("fjord_print_bridge_jobs", {})
                    bridge_job_id = (pending_jobs.get(path) if isinstance(pending_jobs, dict) else None)
                    if not bridge_job_id:
                        raise PrinterError("Pour démarrer ce fichier depuis le site avec Bambu Connect, renvoie d’abord son 3MF depuis cet écran.")
                    if not queue_file(db, str(bridge_job_id)):
                        raise PrinterError("Le fichier n’est plus en attente pour Bambu Connect. Renvoie le 3MF depuis cet écran.")
                    pending_jobs.pop(path, None)
                    session["fjord_print_bridge_jobs"] = pending_jobs
                    remember_start(path, "bambu_connect_handoff")
                    flash("✓ Fichier remis au PC connecté. Bambu Connect va s’ouvrir : confirme la X2D et le lancement dans l’application.")
                    return redirect(url_for("fjord_printer_page", selected=path))
            response = _api("/start",method="POST",payload=command,timeout=15)
            # A transport acknowledgement is not proof the printer is actually printing.
            if response.get("VirtualPath") not in (None,path):
                raise PrinterError("La confirmation du fichier démarré ne correspond pas.")
            flash("Commande remise au relais. Surveille la X2D : une réponse du relais ne confirme pas le démarrage réel.")
        except PrinterError as exc:
            flash(str(exc))
        return redirect(url_for("fjord_printer_page"))
