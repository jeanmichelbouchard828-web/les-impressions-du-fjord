"""Diffusion vidéo de commandes: accès par lien temporaire, sans accès réseau aux imprimantes."""
import datetime
import re
import secrets
from urllib.parse import parse_qs, urlsplit

from flask import abort, flash, make_response, redirect, render_template_string, request, url_for


def _source_url(raw):
    """Accepte uniquement les liens publics de visionnement connus, jamais une IP LAN."""
    url = (raw or "").strip()
    if not url or len(url) > 700:
        raise ValueError("Entre un lien OctoEverywhere ou YouTube Live valide.")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or parsed.port is not None or parsed.fragment):
            raise ValueError()
    except ValueError as exc:
        raise ValueError("Utilise une adresse HTTPS de visionnement, sans identifiants.") from exc
    path = parsed.path
    if host == "oe.ink":
        if not re.fullmatch(r"/l/[A-Za-z0-9_-]{3,100}/?", path) or parsed.query:
            raise ValueError("Lien OctoEverywhere (oe.ink/l/...) invalide.")
        return url, None
    if host in ("octoeverywhere.com", "www.octoeverywhere.com"):
        if not re.fullmatch(r"/live/[A-Za-z0-9_-]{2,100}/?", path) or parsed.query:
            raise ValueError("Lien OctoEverywhere Live invalide.")
        return url, None
    video_id = None
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if path == "/watch":
            params = parse_qs(parsed.query)
            video_id = params.get("v", [None])[0]
        elif re.fullmatch(r"/(live|embed)/[A-Za-z0-9_-]{11}/?", path):
            video_id = path.rstrip("/").split("/")[-1]
    elif host == "youtu.be":
        video_id = path.strip("/") if not parsed.query else None
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return url, "https://www.youtube-nocookie.com/embed/" + video_id
    raise ValueError("Lien non reconnu : utilise OctoEverywhere Live ou YouTube Live.")


def register_live_print(app, db, admin_required, verify, page):
    with db() as connection:
        connection.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS live_token TEXT")
        connection.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS live_url TEXT")
        connection.execute("""ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS
                           live_enabled BOOLEAN NOT NULL DEFAULT FALSE""")
        connection.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS live_expires TIMESTAMPTZ")
        connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS private_quotes_live_token_idx
                              ON private_quotes(live_token)""")

    @app.post("/admin/soumissions-pro/<int:quote_id>/diffusion")
    @admin_required
    def fjord_live_config(quote_id):
        verify()
        action = request.form.get("live_action", "")
        if action not in ("enable", "disable"):
            abort(400, "Action de diffusion invalide.")
        if action == "disable":
            with db() as connection:
                result = connection.execute("""UPDATE private_quotes SET
                    live_enabled=FALSE, live_url=NULL, live_token=NULL, live_expires=NULL
                    WHERE id=%s RETURNING id""", (quote_id,)).fetchone()
            if not result:
                abort(404)
            flash("Diffusion arrêtée : l'ancien lien client est révoqué.")
            return redirect("/admin/soumissions-pro#soumissions-enregistrees")

        try:
            source, _ = _source_url(request.form.get("live_url", ""))
        except ValueError as exc:
            abort(400, str(exc))
        try:
            hours = int(request.form.get("live_hours", "24"))
        except (ValueError, TypeError):
            abort(400, "Durée invalide.")
        if hours not in (12, 24, 48, 72, 168):
            abort(400, "Durée invalide.")
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
        # Chaque activation remplace le lien précédent, même si la caméra reste en ligne.
        token = secrets.token_urlsafe(32)
        with db() as connection:
            result = connection.execute("""UPDATE private_quotes
                SET live_url=%s,live_token=%s,live_enabled=TRUE,live_expires=%s
                WHERE id=%s RETURNING id""", (source, token, expires, quote_id)).fetchone()
        if not result:
            abort(404)
        flash("Suivi en direct activé pour {} h. Partage uniquement le lien de suivi avec ton client.".format(hours))
        return redirect("/admin/soumissions-pro#soumissions-enregistrees")

    @app.get("/suivi-impression/<token>")
    def fjord_live_view(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{40,90}", token):
            abort(404)
        with db() as connection:
            q = connection.execute("""SELECT id,public_number,live_url FROM private_quotes
                WHERE live_token=%s AND live_enabled=TRUE AND live_expires>NOW()""",
                (token,)).fetchone()
        if not q or not q["live_url"]:
            abort(404)
        try:
            source, embed = _source_url(q["live_url"])
        except ValueError:
            abort(404)
        result = make_response(page("Suivre mon impression 3D", r"""
<style>
.fj-watch{max-width:800px;margin:22px auto 38px}
.fj-watch h1{font-size:clamp(28px,5vw,44px)}
.fj-watch-media{aspect-ratio:16/9;width:100%;margin:20px 0;border-radius:14px;
 overflow:hidden;background:#0b101a;display:grid;place-items:center;border:1px solid #3b5970}
.fj-watch-media iframe{display:block;width:100%;height:100%;border:0}
.fj-watch .btn{max-width:100%;white-space:normal;text-align:center}
.fj-watch small{color:#b9d0de;line-height:1.6}
body.light .fj-watch small{color:#39566c}
</style>
<div class="fj-watch">
<div class="eyebrow">Les Impressions du Fjord · Suivi client</div>
<h1>📹 Votre impression en direct</h1>
<p>Soumission <strong>{{display_number}}</strong>. Si la diffusion est active chez notre fournisseur vidéo,
vous pouvez regarder la fabrication de votre pièce.</p>
{% if embed %}
<div class="fj-watch-media"><iframe src="{{embed}}" title="Vidéo de votre impression 3D"
 loading="lazy" referrerpolicy="no-referrer" allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
 allowfullscreen></iframe></div>
<a class="btn" href="{{viewer_url}}" target="_blank" rel="noopener noreferrer">↗ Ouvrir la vidéo dans un nouvel onglet</a>
{% else %}
<div class="fj-watch-media"><div style="text-align:center;padding:20px">
<div style="font-size:55px">📹</div><p>La vidéo est diffusée sur OctoEverywhere.</p>
<a class="btn" href="{{viewer_url}}" target="_blank" rel="noopener noreferrer">▶ Regarder mon impression en direct</a>
</div></div>
{% endif %}
<p><small>Le lien de suivi est temporaire. La caméra et les informations diffusées sont fournies
par un service externe; ce suivi ne permet pas de commander l'imprimante. Le lien
vidéo peut être partagé par son destinataire, alors évitez de le publier.</small></p>
</div>""", display_number=q["public_number"] or "FJ-{:05d}".format(q["id"]), viewer_url=source, embed=embed))
        result.headers["Cache-Control"] = "no-store"
        result.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        result.headers["Referrer-Policy"] = "no-referrer"
        result.headers["Content-Security-Policy"] = "frame-src https://www.youtube-nocookie.com"
        return result
