"""Search-friendly public routes and metadata for the Fjord website."""
import datetime
import os
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape
from flask import Response, request


# Only factual public contact data already displayed on this website.
BUSINESS_SCHEMA = """{"@context":"https://schema.org","@type":"ProfessionalService",
"name":"Les Impressions du Fjord",
"description":"Impression 3D sur mesure, conception de pièces et prototypage au Saguenay, Québec.",
"url":"https://fjord-render-apercu-20261104.onrender.com",
"logo":"https://fjord-render-apercu-20261104.onrender.com/identite/logo",
"telephone":"+1-581-998-0831",
"email":"lesimpressionsdufjord@gmail.com",
"areaServed":{"@type":"Place","name":"Saguenay, Québec, Canada"},
"knowsAbout":["Impression 3D","Prototypage","STL","3MF","PLA","PETG","ASA","TPU"]}"""

DEFAULT_ORIGIN = "https://fjord-render-apercu-20261104.onrender.com"
PUBLIC_ORIGIN = (os.environ.get("FJORD_PUBLIC_URL") or DEFAULT_ORIGIN).strip().rstrip("/")
if not PUBLIC_ORIGIN.startswith("https://"):
    PUBLIC_ORIGIN = DEFAULT_ORIGIN
# Keep schema.org URLs in sync when the real domain replaces the temporary Render hostname.
BUSINESS_SCHEMA = BUSINESS_SCHEMA.replace(DEFAULT_ORIGIN, PUBLIC_ORIGIN)

INDEXABLE = {"/", "/galerie", "/soumission", "/contact", "/atelier-3d",
             "/assistance", "/politique-confidentialite", "/conditions-utilisation"}
PRIVATE_PREFIXES = ("/admin", "/api", "/payer", "/stripe", "/suivi",
                    "/voir-mon-impression", "/live", "/gallery/cover",
                    "/identite", "/health")


def safe_canonical_path(path):
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if path in INDEXABLE or path.startswith("/galerie/") and path[9:].isdigit():
        return path
    return "/"


def seo_metadata():
    path = request.path.rstrip("/") or "/"
    gallery_item = path.startswith("/galerie/") and path[9:].isdigit()
    noindex = bool(os.environ.get("FJORD_PREVIEW_MODE") == "1"
                   or path.startswith(PRIVATE_PREFIXES)
                   or (path not in INDEXABLE and not gallery_item))
    return {"canonical_url": PUBLIC_ORIGIN + safe_canonical_path(path),
            "meta_robots": "noindex, nofollow" if noindex else "index, follow",
            "public_origin": PUBLIC_ORIGIN}


def register_seo_routes(app, db):
    @app.get("/robots.txt")
    def fjord_robots():
        lines = ["User-agent: *"]
        if os.environ.get("FJORD_PREVIEW_MODE") == "1":
            lines.append("Disallow: /")
        else:
            lines += ["Disallow: /admin", "Disallow: /api", "Disallow: /payer",
                      "Disallow: /stripe", "Disallow: /suivi",
                      "Disallow: /voir-mon-impression", "Disallow: /identite/",
                      "Disallow: /health", "Sitemap: " + PUBLIC_ORIGIN + "/sitemap.xml"]
        return Response("\n".join(lines) + "\n", mimetype="text/plain",
                        headers={"Cache-Control":"public, max-age=3600"})

    @app.get("/sitemap.xml")
    def fjord_sitemap():
        if os.environ.get("FJORD_PREVIEW_MODE") == "1":
            return Response("Site de prévisualisation non indexable.", status=503,
                            mimetype="text/plain")
        paths=["/", "/galerie", "/soumission", "/contact", "/atelier-3d"]
        with db() as c:
            items=c.execute("SELECT id FROM gallery ORDER BY id DESC LIMIT 500").fetchall()
        paths += ["/galerie/" + str(item["id"]) for item in items]
        urls=[]
        for path in paths:
            loc=xml_escape(PUBLIC_ORIGIN+path)
            priority="1.0" if path=="/" else "0.8" if path in ("/galerie","/soumission") else "0.6"
            urls.append(f"<url><loc>{loc}</loc><changefreq>weekly</changefreq><priority>{priority}</priority></url>")
        xml='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+"".join(urls)+"</urlset>"
        return Response(xml, mimetype="application/xml",
                        headers={"Cache-Control":"public, max-age=3600"})

    @app.after_request
    def fjord_private_index_headers(response):
        path=request.path.rstrip("/") or "/"
        if path.startswith(PRIVATE_PREFIXES):
            response.headers["X-Robots-Tag"]="noindex, nofollow"
        return response
