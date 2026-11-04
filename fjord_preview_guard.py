"""Preview-only safety lock for the Render migration.

Enable with FJORD_PREVIEW_MODE=1 on a SEPARATE preview database.
Never enable on the production Railway service. The lock is fail-closed for
write methods, payment links, administration and machine APIs; /health remains
available for the hosting health check.
"""
import os

from flask import jsonify, request


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
            or path == "/api"
            or path.startswith("/api/")
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
