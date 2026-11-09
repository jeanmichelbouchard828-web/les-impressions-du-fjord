"""Public MakerWorld slideshow cards with owner-uploaded image and print file."""
import html

def html_fragment(items):
    if not items:
        return ""
    cards=[]
    for item in items:
        title=html.escape(str(item["title"]))
        source=html.escape(str(item["source_url"]),quote=True)
        image="/inspirations/makerworld/"+str(int(item["id"]))+"/photo"
        cards.append(
            '<article class="fjmw-card"><a class="fjmw-image" href="'+source+
            '" target="_blank" rel="noopener noreferrer"><img src="'+image+
            '" loading="lazy" alt="'+title+'"></a><div><span>MakerWorld</span><h3>'+
            title+'</h3><a class="fjmw-link" href="'+source+
            '" target="_blank" rel="noopener noreferrer">Voir le modèle sur MakerWorld ↗</a>'
            '<a class="fjmw-quote" href="/soumission">Demander une soumission</a></div></article>'
        )
    return (
        '<section class="fjm-section fjmw-section" aria-labelledby="fjmw-title">'
        '<style>.fjmw-section{margin-top:32px}.fjmw-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:16px}.fjmw-card{overflow:hidden;border:1px solid #29455c;border-radius:18px;background:#101f2d}.fjmw-image{display:block;aspect-ratio:4/3;background:#09131d}.fjmw-image img{width:100%;height:100%;object-fit:cover}.fjmw-card>div{display:grid;gap:8px;padding:16px}.fjmw-card h3{margin:0}.fjmw-card span{color:#58c9e8;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}.fjmw-link,.fjmw-quote{font-weight:700}.fjmw-quote{display:inline-block;width:max-content;padding:9px 13px;border-radius:999px;background:#1a9c89;color:#fff;text-decoration:none}</style>'
        '<div class="fjm-heading"><span class="fjm-kicker">Modèles de MakerWorld</span>'
        '<h2 id="fjmw-title">Des modèles à découvrir</h2>'
        '<p>Photos et fichiers 3D importés dans le diaporama.</p></div>'
        '<div class="fjmw-list">'+''.join(cards)+'</div></section>'
    )
