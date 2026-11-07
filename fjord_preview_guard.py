"""Preview-only safety lock for the Render migration.

Enable with FJORD_PREVIEW_MODE=1 on a SEPARATE preview database.
Never enable on the production Railway service. The lock is fail-closed for
write methods, payment links, administration and machine APIs; /health remains
available for the hosting health check.
"""
import os
from urllib.parse import unquote, urlsplit

from flask import jsonify, request


def assert_preview_isolated(database_url: str):
    """Reject Railway/prod and suspicious credentials before app.py creates tables.

    The preview *must* use its own temporary Render PostgreSQL database.
    No production Stripe, printer, or owner setup credentials are allowed.
    """
    if os.environ.get("FJORD_PREVIEW_MODE") != "1":
        return
    parsed = urlsplit(database_url)
    dbname = unquote(parsed.path.lstrip("/")).lower()
    host = (parsed.hostname or "").lower()
    # Render private DNS for this disposable, isolated Postgres instance.
    # Explicit allow-list avoids silently accepting Railway or SNIC databases.
    private_preview_host = "dpg-dblt2em417fc73bfjd70-a"
    trusted_preview_host = (host == private_preview_host or host.endswith(".render.com"))
    if (parsed.scheme not in ("postgres", "postgresql")
            or not trusted_preview_host
            or not dbname.startswith("fjord_render_apercu")):
        raise RuntimeError("PREVIEW REFUSED: isolated Render PostgreSQL required.")
    forbidden = (
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
        "OCTOEVERYWHERE_CONNECTION_URL",
        "OCTOEVERYWHERE_AUTH_BEARER_TOKEN",
        "OCTOEVERYWHERE_AUTH_BASIC_PASSWORD",
        "ADMIN_SETUP_TOKEN",
    )
    if any(os.environ.get(name) for name in forbidden):
        raise RuntimeError("PREVIEW REFUSED: production credentials present.")


def install_preview_guard(app):
    @app.before_request
    def fjord_render_preview_guard():
        if os.environ.get("FJORD_PREVIEW_MODE") != "1":
            return None
        path = request.path.rstrip("/") or "/"
        blocked_path = (
            path == "/payer"
            or path.startswith("/payer/")
            or path == "/admin"
            or path.startswith("/admin/")
            or (path == "/api" or path.startswith("/api/")) and path != "/api/public/visitors"
            or path == "/stripe"
            or path.startswith("/stripe/")
        )
        if request.method not in ("GET", "HEAD", "OPTIONS") or blocked_path:
            response = jsonify(
                preview=True,
                error="Site de test : commandes, paiements et impression desactives.",
            )
            response.status_code = 503
            response.headers["Cache-Control"] = "no-store"
            return response
        return None

    @app.after_request
    def fjord_render_preview_headers(response):
        if os.environ.get("FJORD_PREVIEW_MODE") == "1":
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            response.headers["Cache-Control"] = "no-store"
        return response
