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
        '<style>.fjmw-section{margin-top:32px}.fjmw-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-bottom:12px}.fjmw-toolbar button{min-width:42px;min-height:42px;border:1px solid #29455c;border-radius:50%;background:#102638;color:#fff;font-size:22px;cursor:pointer}.fjmw-toolbar button:disabled{opacity:.4;cursor:default}.fjmw-track{display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;overscroll-behavior-x:contain}.fjmw-track::-webkit-scrollbar{display:none}.fjmw-card{flex:0 0 min(320px,84vw);overflow:hidden;scroll-snap-align:start;border:1px solid #29455c;border-radius:18px;background:#101f2d}.fjmw-image{display:block;aspect-ratio:4/3;background:#09131d}.fjmw-image img{width:100%;height:100%;object-fit:cover}.fjmw-card>div{display:grid;gap:8px;padding:16px}.fjmw-card h3{margin:0}.fjmw-card span{color:#58c9e8;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}.fjmw-link,.fjmw-quote{font-weight:700}.fjmw-quote{display:inline-block;width:max-content;padding:9px 13px;border-radius:999px;background:#1a9c89;color:#fff;text-decoration:none}.fjmw-track:focus-visible{outline:2px solid #58c9e8;outline-offset:4px}</style>'
        '<div class="fjm-heading"><span class="fjm-kicker">Modèles de MakerWorld</span>'
        '<h2 id="fjmw-title">Des modèles à découvrir</h2>'
        '<p>Photos et fichiers 3D importés dans le diaporama.</p></div>'
        '<div class="fjmw-toolbar" aria-label="Navigation des modèles MakerWorld">'
        '<button type="button" id="fjmwPrev" aria-label="Modèle précédent">‹</button>'
        '<button type="button" id="fjmwNext" aria-label="Modèle suivant">›</button></div>'
        '<div class="fjmw-track" id="fjmwTrack" tabindex="0" role="region" aria-roledescription="carrousel" aria-label="Modèles MakerWorld">'
        +''.join(cards)+'</div>'
        '<script>(function(){const track=document.getElementById("fjmwTrack");if(!track)return;'
        'const cards=[...track.querySelectorAll(".fjmw-card")],prev=document.getElementById("fjmwPrev"),next=document.getElementById("fjmwNext");'
        'const step=()=>cards[0]?cards[0].getBoundingClientRect().width+16:1;'
        'function sync(){const max=Math.max(0,track.scrollWidth-track.clientWidth-2);prev.disabled=track.scrollLeft<=2;next.disabled=track.scrollLeft>=max;}'
        'prev.addEventListener("click",()=>track.scrollBy({left:-step(),behavior:"smooth"}));'
        'next.addEventListener("click",()=>track.scrollBy({left:step(),behavior:"smooth"}));'
        'track.addEventListener("scroll",sync,{passive:true});window.addEventListener("resize",sync);sync();})();</script></section>'
    )
