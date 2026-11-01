"""Stripe Checkout for individual Fjord quotes; no Stripe credentials in source."""
import os
import re
import time
import hmac
import json
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from decimal import Decimal, ROUND_HALF_UP
from flask import request, abort, redirect, jsonify, make_response
from private_fjord import _quote_amounts

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,90}$")

def register_stripe_payments(app, db):
    with db() as c:
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS stripe_payment_intent TEXT")
        c.execute("ALTER TABLE private_quotes ADD COLUMN IF NOT EXISTS stripe_session_id TEXT")
        c.execute("""CREATE TABLE IF NOT EXISTS fjord_stripe_events(
            event_id TEXT PRIMARY KEY, received_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")

    @app.get("/payer/stripe/<token>")
    def fjord_stripe_checkout(token):
        if not TOKEN_PATTERN.fullmatch(token):
            abort(404)
        secret = os.environ.get("STRIPE_SECRET_KEY", "")
        if not secret.startswith(("sk_live_", "rk_live_", "sk_test_", "rk_test_")):
            return "Paiement par carte temporairement indisponible.", 503
        with db() as c:
            q = c.execute("SELECT * FROM private_quotes WHERE payment_token=%s", (token,)).fetchone()
        if not q:
            abort(404)
        if q["payment_status"] == "Payée":
            return "Cette soumission est déjà payée.", 409
        amount = int((Decimal(str(_quote_amounts(q)[3])) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if amount < 50:
            return "Montant non admissible au paiement en ligne.", 422
        reference = q.get("public_number") or "FJ-{:05d}".format(q["id"])
        origin = request.host_url.rstrip("/")
        params = {
            "mode": "payment",
            "success_url": origin + "/payer/" + token + "?stripe=retour",
            "cancel_url": origin + "/payer/" + token,
            "client_reference_id": str(q["id"]),
            "metadata[quote_id]": str(q["id"]),
            "metadata[quote_reference]": reference,
            "line_items[0][price_data][currency]": "cad",
            "line_items[0][price_data][unit_amount]": str(amount),
            "line_items[0][price_data][product_data][name]": "Soumission " + reference,
            "line_items[0][quantity]": "1",
        }
        if q.get("email"):
            params["customer_email"] = q["email"]
        payload = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request("https://api.stripe.com/v1/checkout/sessions", data=payload,
            headers={"Authorization": "Bearer " + secret, "Content-Type": "application/x-www-form-urlencoded",
                     "Idempotency-Key": "fjord-quote-" + str(q["id"]) + "-" + str(amount) + "-" + str(int(time.time() // 600))},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                session = json.load(resp)
        except (urllib.error.URLError, ValueError):
            app.logger.exception("Stripe Checkout session failed")
            return "Paiement momentanément indisponible. Réessayez plus tard.", 503
        url = session.get("url", "")
        if not url.startswith("https://checkout.stripe.com/"):
            return "Réponse de paiement invalide.", 502
        response = redirect(url, code=303)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.post("/stripe/webhook")
    def fjord_stripe_webhook():
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        header = request.headers.get("Stripe-Signature", "")
        body = request.get_data(cache=False)
        if not secret.startswith("whsec_") or len(body) > 262144:
            abort(400)
        fields = {}
        for part in header.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                fields.setdefault(k.strip(), []).append(v.strip())
        try:
            timestamp = int(fields["t"][0])
            if abs(time.time() - timestamp) > 300:
                abort(400)
            signature = hmac.new(secret.encode(), (str(timestamp) + ".").encode() + body, hashlib.sha256).hexdigest()
            if not any(hmac.compare_digest(signature, v) for v in fields.get("v1", [])):
                abort(400)
            event = json.loads(body)
        except (KeyError, ValueError, TypeError):
            abort(400)
        event_id = event.get("id")
        event_type = event.get("type")
        obj = (event.get("data") or {}).get("object") or {}
        if not isinstance(event_id, str) or not event_id.startswith("evt_"):
            abort(400)
        with db() as c:
            exists = c.execute("SELECT 1 FROM fjord_stripe_events WHERE event_id=%s", (event_id,)).fetchone()
            if exists:
                return jsonify({"received": True})
            if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
                if obj.get("payment_status") == "paid" and obj.get("mode") == "payment":
                    meta = obj.get("metadata") or {}
                    try:
                        quote_id = int(meta["quote_id"])
                        cents = int(obj["amount_total"])
                    except (KeyError, ValueError, TypeError):
                        abort(400)
                    q = c.execute("SELECT * FROM private_quotes WHERE id=%s FOR UPDATE", (quote_id,)).fetchone()
                    if not q:
                        abort(400)
                    expected = int((Decimal(str(_quote_amounts(q)[3])) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    if (cents != expected or obj.get("currency", "").lower() != "cad"
                            or str(obj.get("client_reference_id")) != str(quote_id)):
                        app.logger.warning("Stripe webhook amount/reference mismatch for quote %s", quote_id)
                        abort(400)
                    c.execute("""UPDATE private_quotes SET payment_status='Payée',
                        paid_at=COALESCE(paid_at,NOW()), stripe_session_id=%s,
                        stripe_payment_intent=%s WHERE id=%s""",
                        (obj.get("id"), obj.get("payment_intent"), quote_id))
            c.execute("INSERT INTO fjord_stripe_events(event_id) VALUES(%s)", (event_id,))
        return jsonify({"received": True})
