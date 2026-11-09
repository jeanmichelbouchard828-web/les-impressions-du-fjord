"""Curated 3D inspiration examples with credits and verified re-use terms.

Wikimedia photographs show independently made examples, NOT creations or
commercial catalogue items from Les Impressions du Fjord. Their image licenses
do not authorize reproduction of an unrelated third-party STL/design.
"""
import hashlib
import html
from urllib.parse import quote, urlencode

# These source pages were reviewed for reusable image licensing (November 2026).
# Keep source/author/license links directly next to each photograph.
IDEAS = (
    {"title": "Dragon articulé", "english": "Articulated dragon",
     "category":"Décoration et jouets", "en_category":"Decorations and toys",
     "description":"Un exemple de pièce articulée imprimée d’un seul tenant.",
     "file":"Technology_3D_print_dragon.jpg",
     "author":"Jan Helebrant", "license":"CC0 1.0",
     "license_url":"https://creativecommons.org/publicdomain/zero/1.0/"},
    {"title":"Vase décoratif", "english":"Decorative vase",
     "category":"Décoration", "en_category":"Home decor",
     "description":"Formes originales et textures personnalisables.",
     "file":"3D_Printed_Vase.jpg", "author":"D Eaketts",
     "license":"CC BY-SA 4.0",
     "license_url":"https://creativecommons.org/licenses/by-sa/4.0/"},
    {"title":"Cache-pots", "english":"Planters",
     "category":"Maison et jardin", "en_category":"Home and garden",
     "description":"Exemples de pots imprimés en 3D pour la décoration.",
     "file":"3D_printed_flower_pots.jpg", "author":"Aaaatu",
     "license":"CC BY-SA 4.0",
     "license_url":"https://creativecommons.org/licenses/by-sa/4.0/"},
    {"title":"Porte-clés personnalisés", "english":"Custom keyrings",
     "category":"Cadeaux", "en_category":"Gifts",
     "description":"Petits objets cadeaux réalisés par impression 3D.",
     "file":"Stampa_3D_di_portachiavi_03.jpg", "author":"Giacomo Alessandroni",
     "license":"CC BY-SA 4.0",
     "license_url":"https://creativecommons.org/licenses/by-sa/4.0/"},
    {"title":"Mécanismes et engrenages", "english":"Gears and mechanisms",
     "category":"Technique", "en_category":"Engineering",
     "description":"Un exemple de mécanisme géométrique imprimé en 3D.",
     "file":"Triple_Gear.jpg", "author":"Saul Schleimer et Henry Segerman",
     "license":"CC BY-SA 3.0",
     "license_url":"https://creativecommons.org/licenses/by-sa/3.0/"},
)

def _src(file_name: str):
    # Wikimedia's documented thumbnail URLs use the MD5 prefix of the file
    # name; no scraping, visitor API keys or large originals required.
    digest = hashlib.md5(file_name.encode("utf-8")).hexdigest()
    escaped = quote(file_name, safe="_.-")
    return ("https://thumb.wikimedia.org/wikipedia/commons/thumb/"
            f"{digest[0]}/{digest[:2]}/{escaped}/960px-{escaped}")

def html_fragment():
    cards = []
    for i, idea in enumerate(IDEAS):
        title = html.escape(idea["title"])
        image = html.escape(_src(idea["file"]),quote=True)
        source = ("https://commons.wikimedia.org/wiki/File:"
                  + quote(idea["file"], safe="_.-"))
        href = "/soumission?" + urlencode({"projet":idea["title"]})
        cards.append(
            '<article class="fji-card" role="group" aria-label="'
            + html.escape(f"Idée {i+1} sur {len(IDEAS)} : {idea['title']}",quote=True)
            + '">'
            + '<div class="fji-photo"><img src="'+image+'" loading="lazy" '
              'decoding="async" width="480" height="360" referrerpolicy="no-referrer" '
              'alt="Exemple photographié : '+title+'">'
              '<span aria-hidden="true" class="fji-photo-fallback">✦ Idée 3D</span>'
              '</div>'
            + '<div class="fji-card-body"><span class="fji-card-type" data-fjm-en="'
            + html.escape(idea["en_category"],quote=True)+'">'
            + html.escape(idea["category"])+'</span>'
            + '<h3 data-fjm-en="'+html.escape(idea["english"],quote=True)+'">'
            + title+'</h3>'
            + '<p>'+html.escape(idea["description"])+'</p>'
            + '<a class="fji-cta" href="'+html.escape(href,quote=True)
            + '" data-fjm-en="Request a similar creation">Demander un objet semblable</a>'
            + '<small class="fji-credit">Photo : <a href="'
            + html.escape(source,quote=True)
            + '" target="_blank" rel="noopener noreferrer">'
            + html.escape(idea["author"])+'</a> · '
            + '<a href="'+html.escape(idea["license_url"],quote=True)
            + '" target="_blank" rel="noopener noreferrer">'
            + html.escape(idea["license"])+'</a></small>'
            + '</div></article>'
        )
    return (
        '<section id="inspirations-3d" class="fjm-section fji-section" '
        'aria-labelledby="fji-heading">'
        '<div class="fji-heading"><div><span class="fjm-kicker" '
        'data-fjm-en="Ideas from the 3D printing world">Inspirations trouvées sur Internet</span>'
        '<h2 id="fji-heading" data-fjm-en="What could we create for you?">'
        'Et si on fabriquait quelque chose pour vous?</h2>'
        '<p data-fjm-en="Explore 3D-printing examples and ask about your own version.">'
        'Faites défiler des exemples d’objets imprimés en 3D, puis racontez-nous votre idée.</p>'
        '</div><div class="fji-controls" aria-label="Navigation du diaporama">'
        '<button type="button" id="fji-prev" aria-label="Image précédente">‹</button>'
        '<span id="fji-counter" aria-live="off">1 / '+str(len(IDEAS))+'</span>'
        '<button type="button" id="fji-next" aria-label="Image suivante">›</button>'
        '</div></div>'
        '<div class="fji-track" id="fji-track" tabindex="0" '
        'role="region" aria-roledescription="carousel" '
        'aria-label="Exemples d’objets à imaginer en impression 3D">'
        + ''.join(cards) + '</div>'
        '<p class="fji-disclaimer" data-fjm-en="Inspiration photos from Wikimedia Commons, '
        'not products made by our workshop. Availability, pricing and design rights '
        'are confirmed before production.">'
        'Photos d’inspiration provenant de Wikimedia Commons, '
        'non de notre atelier. Faisabilité, prix et droits de reproduction '
        'à confirmer avant toute fabrication.</p>'
        '</section>'
    )
