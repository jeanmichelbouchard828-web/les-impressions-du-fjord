"""50 attributed Wikimedia Commons inspiration photos for the Fjord storefront.

The versioned JSON manifest contains verified credits and allowed licenses.
Photos are only examples, never represented as Fjord products or licensed STL files.
"""
import html
import json
import logging
from pathlib import Path
from urllib.parse import urlencode, urlsplit

MANIFEST = Path(__file__).with_name("fjord_inspirations_manifest.json")
CATEGORIES = (
    ("Animaux", "Animals"),
    ("Objets utiles", "Useful items"),
    ("Maison & déco", "Home and decor"),
    ("Cadeaux & figurines", "Gifts and figurines"),
    ("Technique", "Engineering"),
    ("Bijoux & design", "Jewelry and design"),
)

def _safe_url(value, hosts):
    try:
        u=urlsplit(str(value))
        if u.scheme=="https" and u.hostname in hosts and not u.username:
            return str(value)
    except (TypeError,ValueError):
        pass
    return ""

def _load_ideas():
    try:
        items=json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
        good=[]
        for idea in items:
            if not isinstance(idea,dict) or not all(idea.get(k) for k in
                ("title","english","category","author","license","license_url","image","source")):
                continue
            if not _safe_url(idea["image"],("upload.wikimedia.org","thumb.wikimedia.org")):
                continue
            if not _safe_url(idea["source"],("commons.wikimedia.org",)):
                continue
            if not _safe_url(idea["license_url"],("creativecommons.org","commons.wikimedia.org")):
                continue
            good.append(idea)
        return tuple(good[:50])
    except (OSError,KeyError,TypeError,ValueError) as exc:
        logging.getLogger(__name__).warning("Fjord inspiration manifest not available: %s",exc)
        return ()

IDEAS = _load_ideas()

def html_fragment():
    if not IDEAS:
        return ""
    categories={name:en for name,en in CATEGORIES}
    chips=[
        '<button type="button" class="fji-filter" data-fji-filter="all" '
        'aria-pressed="true" data-fjm-en="All 50 ideas">Toutes les 50 idées</button>'
    ]
    for category,en in CATEGORIES:
        count=sum(x["category"]==category for x in IDEAS)
        if count:
            chips.append(
                '<button type="button" class="fji-filter" data-fji-filter="'
                +html.escape(category,quote=True)+'" aria-pressed="false"'
                ' data-fjm-en="'+html.escape(en,quote=True)+'">'
                +html.escape(category)+' <span aria-hidden="true">('+str(count)+')</span>'
                '</button>')
    cards=[]
    for i,idea in enumerate(IDEAS):
        title=html.escape(idea["title"])
        image=html.escape(idea["image"],quote=True)
        author=html.escape(idea["author"])
        source=html.escape(idea["source"],quote=True)
        license_url=html.escape(idea["license_url"],quote=True)
        license_name=html.escape(idea["license"])
        category=html.escape(idea["category"])
        quote_url=html.escape("/soumission?"+urlencode({"projet":idea["title"]}),quote=True)
        cards.append(
            '<article class="fji-card" data-fji-category="'
            +html.escape(idea["category"],quote=True)+'" role="group" aria-label="'
            +html.escape(f"Idée {i+1} sur {len(IDEAS)} : {idea['title']}",quote=True)+'">'
            '<div class="fji-photo"><img src="'+image+'" loading="lazy" decoding="async" '
            'fetchpriority="low" referrerpolicy="no-referrer" width="480" height="360" '
            'alt="Inspiration 3D : '+title+'"><span class="fji-photo-fallback" '
            'aria-hidden="true">✦ Idée 3D</span></div>'
            '<div class="fji-card-body"><span class="fji-card-type" data-fjm-en="'
            +html.escape(categories.get(idea["category"],idea["category"]),quote=True)+'">'
            +category+'</span>'
            '<h3 data-fjm-en="'+html.escape(idea["english"],quote=True)+'">'+title+'</h3>'
            '<a class="fji-cta" href="'+quote_url+'" '
            'data-fjm-en="Request a similar creation">Demander un objet semblable</a>'
            '<small class="fji-credit">Photo : <a href="'+source
            +'" target="_blank" rel="noopener noreferrer">'+author+'</a> · '
            '<a href="'+license_url+'" target="_blank" rel="noopener noreferrer">'
            +license_name+'</a></small></div></article>'
        )
    return (
        '<section id="inspirations-3d" class="fjm-section fji-section" '
        'aria-labelledby="fji-heading">'
        '<div class="fji-heading"><div><span class="fjm-kicker" '
        'data-fjm-en="Ideas from the 3D printing world">Inspirations trouvées sur Internet</span>'
        '<h2 id="fji-heading" data-fjm-en="What could we create for you?">'
        'Et si on fabriquait quelque chose pour vous?</h2>'
        '<p data-fjm-en="Explore 50 examples and ask about your own version.">'
        'Explorez 50 idées d’objets 3D. Faites défiler, puis demandez votre version personnalisée.</p>'
        '</div><div class="fji-controls" aria-label="Navigation du diaporama">'
        '<button type="button" id="fji-prev" aria-label="Image précédente">‹</button>'
        '<span id="fji-counter" aria-live="off">1 / '+str(len(IDEAS))+'</span>'
        '<button type="button" id="fji-next" aria-label="Image suivante">›</button>'
        '</div></div>'
        '<div class="fji-filters" role="group" aria-label="Catégories d’inspirations">'
        +''.join(chips)+'</div>'
        '<div class="fji-track" id="fji-track" tabindex="0" '
        'role="region" aria-roledescription="carousel" '
        'aria-label="50 inspirations d’objets fabriqués par impression 3D">'
        +''.join(cards)+'</div>'
        '<p class="fji-disclaimer" data-fjm-en="50 photos from Wikimedia Commons, '
        'showing work by other creators, not items sold or made by our workshop. '
        'Photo licenses do not grant rights to copy the underlying designs. '
        'Feasibility and design rights are checked before production.">'
        '50 photos provenant de Wikimedia Commons et d’autres créateurs : '
        'ce ne sont pas des réalisations de notre atelier. '
        'Les licences photo ne donnent pas automatiquement le droit '
        'de reproduire les modèles 3D. Faisabilité et droits du modèle à confirmer '
        'avant fabrication.</p></section>'
    )
