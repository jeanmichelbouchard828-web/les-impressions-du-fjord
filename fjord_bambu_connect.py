"""Secure queue and one-PC handoff to the official Bambu Connect app.

The Render service cannot launch a Windows desktop application. A paired
Windows helper polls this queue, downloads an already-reviewed 3MF, and opens
Bambu Connect's documented import URL. The final printer selection/start stays
in Bambu Connect; no printer credentials or Bambu signing keys are handled.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import time
import zipfile

from flask import abort, jsonify, redirect, request, send_file, session

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,48}$")
_MAX_3MF = 30 * 1024 * 1024


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def initialize(db):
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS fjord_connect_pairings (
            code_hash TEXT PRIMARY KEY,
            expires_at DOUBLE PRECISION NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS fjord_connect_tokens (
            token_hash TEXT PRIMARY KEY,
            device_name TEXT NOT NULL,
            paired_at DOUBLE PRECISION NOT NULL,
            last_seen DOUBLE PRECISION,
            revoked BOOLEAN NOT NULL DEFAULT FALSE
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS fjord_connect_jobs (
            id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            material TEXT,
            file_data BYTEA NOT NULL,
            state TEXT NOT NULL DEFAULT 'staged',
            created_at DOUBLE PRECISION NOT NULL,
            queued_at DOUBLE PRECISION,
            claimed_at DOUBLE PRECISION,
            handed_at DOUBLE PRECISION
        )""")
        conn.execute("ALTER TABLE fjord_connect_jobs ADD COLUMN IF NOT EXISTS claimed_at DOUBLE PRECISION")


def store_file(db, job_id, file_path, file_name, material, raw):
    if not isinstance(job_id, str) or not _ID_RE.fullmatch(job_id):
        raise ValueError("Identifiant de transfert invalide.")
    if not isinstance(raw, bytes) or not (100 <= len(raw) <= _MAX_3MF):
        raise ValueError("Le 3MF dépasse la taille autorisée.")
    safe_name = re.sub(r"[^A-Za-z0-9_. -]", "_", str(file_name or "piece.3mf"))[:120]
    if not safe_name.lower().endswith(".3mf"):
        safe_name += ".3mf"
    with db() as conn:
        conn.execute("DELETE FROM fjord_connect_jobs WHERE created_at < %s",
                     (time.time() - 7 * 86400,))
        conn.execute("""INSERT INTO fjord_connect_jobs
            (id,file_path,file_name,material,file_data,state,created_at)
            VALUES(%s,%s,%s,%s,%s,'staged',%s)
            ON CONFLICT(id) DO NOTHING""",
            (job_id, file_path, safe_name, str(material or "")[:32], raw, time.time()))


def queue_file(db, job_id):
    if not isinstance(job_id, str) or not _ID_RE.fullmatch(job_id):
        return False
    with db() as conn:
        row = conn.execute("""UPDATE fjord_connect_jobs SET state='queued',queued_at=%s
            WHERE id=%s AND state='staged' RETURNING id""", (time.time(), job_id)).fetchone()
    return bool(row)


def bridge_state(db):
    with db() as conn:
        row = conn.execute("""SELECT last_seen FROM fjord_connect_tokens
            WHERE revoked=FALSE ORDER BY last_seen DESC NULLS LAST LIMIT 1""").fetchone()
    if not row or row["last_seen"] is None:
        return {"paired": bool(row), "online": False, "age": None}
    age = max(0, int(time.time() - float(row["last_seen"])))
    return {"paired": True, "online": age <= 25, "age": age}


def register_bridge(app, db, admin_required, verify, csrfinput, page):
    initialize(db)

    def authenticate():
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401)
        token = header[7:].strip()
        if not (32 <= len(token) <= 100):
            abort(401)
        token_hash = _digest(token)
        with db() as conn:
            row = conn.execute("""UPDATE fjord_connect_tokens SET last_seen=%s
                WHERE token_hash=%s AND revoked=FALSE RETURNING token_hash""",
                (time.time(), token_hash)).fetchone()
        if not row:
            abort(401)
        return token_hash

    @app.get("/admin/atelier-pont")
    @admin_required
    def fjord_connect_bridge_page():
        state = bridge_state(db)
        code = session.pop("fjord_connect_pair_code", "")
        return page("Pont Bambu Connect", r"""
<section class="card" style="max-width:850px;margin:auto">
 <h1>🖨️ Pont vers Bambu Connect</h1>
 <p>Ce pont permet au site Render de remettre le 3MF au PC Windows. Bambu Connect ouvre ensuite le fichier et garde la confirmation finale d'impression.</p>
 <p><strong>État :</strong> {% if state.online %}PC connecté{% elif state.paired %}PC associé, hors ligne{% else %}aucun PC associé{% endif %}</p>
 {% if state.age is not none %}<p class="small muted">Dernier contact : {{state.age}} s</p>{% endif %}
 <p><a class="btn" href="/admin/atelier-pont/bridge.zip">Télécharger le pont Windows (ZIP)</a></p>
 <form method="post" action="/admin/atelier-pont/code">{{csrf|safe}}<button>Associer ce PC</button></form>
 {% if code %}<div class="alert"><strong>Code à usage unique (10 minutes) :</strong><br><code style="font-size:22px;user-select:all">{{code}}</code><p>Entre ce code dans le script PowerShell téléchargé. Ne le partage pas.</p></div>{% endif %}
 <form method="post" action="/admin/atelier-pont/revoquer" onsubmit="return confirm('Dissocier tous les PC?');">{{csrf|safe}}<button style="background:#9e4545;color:white">Dissocier tous les PC</button></form>
 <ol><li>Télécharge le ZIP et extrais son contenu sur le PC où Bambu Connect est installé.</li><li>Double-clique sur <strong>Lancer_Pont_Bambu_Connect.cmd</strong>, puis colle le code d’association affiché ici.</li><li>Laisse la fenêtre ouverte. Lors d’un lancement depuis le site, Bambu Connect s’ouvrira sur le PC pour confirmer l’imprimante et l’envoi.</li></ol>
 <p class="small muted">Aucun code d’accès imprimante ni clé de signature Bambu n’est stocké sur Render. Ce pont ne démarre jamais seul une impression.</p>
 <p><a href="/admin/atelier-imprimer">← Retour à l’impression X2D</a></p>
</section>""", state=state, code=code, csrf=csrfinput())

    @app.post("/admin/atelier-pont/code")
    @admin_required
    def fjord_connect_pairing_code():
        verify()
        code = secrets.token_urlsafe(18)
        with db() as conn:
            conn.execute("DELETE FROM fjord_connect_pairings WHERE expires_at < %s", (time.time(),))
            conn.execute("INSERT INTO fjord_connect_pairings(code_hash,expires_at) VALUES(%s,%s)",
                         (_digest(code), time.time() + 600))
        session["fjord_connect_pair_code"] = code
        return redirect("/admin/atelier-pont")

    @app.post("/admin/atelier-pont/revoquer")
    @admin_required
    def fjord_connect_revoke():
        verify()
        with db() as conn:
            conn.execute("UPDATE fjord_connect_tokens SET revoked=TRUE WHERE revoked=FALSE")
        return page("Pont Bambu Connect", "<h1>PC dissocié</h1><p><a href='/admin/atelier-pont'>Retour</a></p>")

    @app.get("/admin/atelier-pont/bridge.ps1")
    @admin_required
    def fjord_connect_bridge_script():
        import os
        return send_file(os.path.join(os.path.dirname(__file__), "fjord_bambu_connect_bridge.ps1"),
                         as_attachment=True, download_name="fjord_bambu_connect_bridge.ps1",
                         mimetype="text/plain", max_age=0)

    @app.get("/admin/atelier-pont/bridge.zip")
    @admin_required
    def fjord_connect_bridge_bundle():
        import os
        archive = io.BytesIO()
        base = os.path.dirname(__file__)
        instructions = (
            "PONT BAMBU CONNECT — INSTALLATION SIMPLE\r\n\r\n"
            "1. Extrais tous les fichiers de ce ZIP dans un dossier.\r\n"
            "2. Dans l’administration du site, ouvre Pont Bambu Connect et clique sur Associer ce PC.\r\n"
            "3. Double-clique sur Lancer_Pont_Bambu_Connect.cmd et colle le code affiché.\r\n"
            "4. Laisse la fenêtre ouverte.\r\n\r\n"
            "Le PC doit avoir Bambu Connect installé. Lorsqu’un fichier arrive, confirme le choix de l’imprimante et l’envoi dans Bambu Connect.\r\n"
        )
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for filename in ("fjord_bambu_connect_bridge.ps1", "Lancer_Pont_Bambu_Connect.cmd"):
                with open(os.path.join(base, filename), "rb") as source:
                    bundle.writestr(filename, source.read())
            bundle.writestr("LISEZ-MOI.txt", instructions.encode("utf-8"))
        archive.seek(0)
        response = send_file(archive, as_attachment=True,
                             download_name="Pont_Bambu_Connect_Windows.zip",
                             mimetype="application/zip", max_age=0)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.post("/api/fjord-print-bridge/pair")
    def fjord_connect_pair():
        if not request.is_json:
            abort(400)
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", ""))
        name = re.sub(r"[^A-Za-z0-9_. -]", "_", str(data.get("device_name", "Windows PC")))[:80]
        if not (20 <= len(code) <= 100):
            abort(401)
        with db() as conn:
            pairing = conn.execute("""DELETE FROM fjord_connect_pairings
                WHERE code_hash=%s AND expires_at >= %s RETURNING code_hash""",
                (_digest(code), time.time())).fetchone()
            if not pairing:
                abort(401)
            token = secrets.token_urlsafe(48)
            conn.execute("UPDATE fjord_connect_tokens SET revoked=TRUE WHERE revoked=FALSE")
            conn.execute("""INSERT INTO fjord_connect_tokens(token_hash,device_name,paired_at,last_seen)
                VALUES(%s,%s,%s,%s)""", (_digest(token), name or "Windows PC", time.time(), time.time()))
        return jsonify(ok=True, token=token, poll_seconds=5)

    @app.get("/api/fjord-print-bridge/next")
    def fjord_connect_next():
        token_hash = authenticate()
        with db() as conn:
            conn.execute("""UPDATE fjord_connect_jobs SET state='queued',claimed_at=NULL
                WHERE state='claimed' AND claimed_at < %s""", (time.time() - 90,))
            job = conn.execute("""SELECT id,file_name,material,created_at FROM fjord_connect_jobs
                WHERE state='queued' ORDER BY queued_at,id LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
            if job:
                claimed = conn.execute("""UPDATE fjord_connect_jobs SET state='claimed',claimed_at=%s
                    WHERE id=%s AND state='queued' RETURNING id""", (time.time(), job["id"])).fetchone()
                if not claimed:
                    job = None
        response = jsonify(ok=True, job=job)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/fjord-print-bridge/file/<job_id>")
    def fjord_connect_file(job_id):
        authenticate()
        if not _ID_RE.fullmatch(job_id):
            abort(404)
        with db() as conn:
            job = conn.execute("SELECT file_name,file_data,state FROM fjord_connect_jobs WHERE id=%s",
                               (job_id,)).fetchone()
        if not job or job["state"] not in ("claimed", "queued"):
            abort(404)
        response = send_file(io.BytesIO(bytes(job["file_data"])), as_attachment=True,
                             download_name=job["file_name"], mimetype="model/3mf", max_age=0)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post("/api/fjord-print-bridge/ack/<job_id>")
    def fjord_connect_ack(job_id):
        authenticate()
        if not _ID_RE.fullmatch(job_id):
            abort(404)
        with db() as conn:
            row = conn.execute("""UPDATE fjord_connect_jobs SET state='handed_to_connect',handed_at=%s
                WHERE id=%s AND state='claimed' RETURNING id""", (time.time(), job_id)).fetchone()
        if not row:
            abort(409)
        return jsonify(ok=True)

