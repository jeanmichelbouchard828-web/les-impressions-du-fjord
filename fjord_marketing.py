"""Vitrine commerciale Les Impressions du Fjord, sans modifier le flux des commandes."""
MARKETING_CSS = r"""<style>
/* Vitrine : lisibilite, confiance et conversion, sans bibliotheques externes. */
.fjm-home{overflow:clip}
.fjm-hero{position:relative;isolation:isolate;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(245px,.65fr);align-items:center;gap:clamp(22px,4vw,60px);padding:clamp(27px,5vw,66px)!important;margin-bottom:16px;min-height:430px;background:radial-gradient(circle at 80% 18%,#1579ab75,transparent 41%),linear-gradient(120deg,#0d304e,#071a30 70%)!important;border:1px solid #368bb5;border-radius:24px;box-shadow:0 20px 55px #0004}
.fjm-kicker{display:block;font-weight:850;letter-spacing:.13em;text-transform:uppercase;color:#80e2ff;font-size:12px}
.fjm-hero h1{font-size:clamp(36px,5.5vw,70px)!important;line-height:1.04!important;letter-spacing:-.055em;margin:16px 0 18px;max-width:930px}
.fjm-accent{color:#6cddff}
.fjm-hero-lead{max-width:650px;font-size:clamp(16px,1.8vw,21px);line-height:1.6;color:#d3e8f5}
.fjm-hero-actions{display:flex;flex-wrap:wrap;gap:11px;margin-top:25px;align-items:center}
.fjm-hero-actions .btn{min-height:52px;padding:13px 22px;text-align:center;white-space:normal}
.fjm-hero-actions .fjm-outline{background:#0e2b42!important;border-color:#59c6ea!important;color:#effaff!important}
.fjm-points{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 0;padding:0;list-style:none}
.fjm-points li{padding:8px 12px;border:1px solid #347593;border-radius:99px;background:#0e334bbb;color:#d5f2ff;font-size:12px;font-weight:750}
.fjm-hero-panel{padding:23px;border-radius:21px;border:1px solid #4285a8;background:#061b2bdc;box-shadow:0 15px 45px #0003}
.fjm-hero-panel img{width:89px;height:89px;object-fit:cover;border-radius:18px;box-shadow:0 0 24px #0abdf555}
.fjm-hero-panel h2{color:#f1fbff;margin:15px 0 8px;font-size:clamp(22px,2.4vw,29px)}
.fjm-hero-panel p{margin:0 0 18px;color:#c6dfec;font-size:15px}
.fjm-hero-panel a{font-weight:800;text-decoration:underline;text-underline-offset:4px}
.fjm-section{margin:clamp(37px,5.5vw,74px) 0}
.fjm-heading{max-width:800px;margin-bottom:23px}
.fjm-heading h2{margin:8px 0 10px;font-size:clamp(27px,3.5vw,40px)}
.fjm-heading p{margin:0}
.fjm-services{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.fjm-service{display:flex;flex-direction:column;gap:9px;padding:23px;border:1px solid #2f7098;border-radius:19px;background:linear-gradient(150deg,#15364d,#0c2235)}
.fjm-service .fjm-icon{display:grid;place-items:center;width:51px;height:51px;border-radius:14px;background:#16577a;font-size:24px}
.fjm-service h3{font-size:19px;margin:8px 0 0;color:#edfbff}.fjm-service p{font-size:14px;line-height:1.6;margin:0}
.fjm-service a{margin-top:auto;padding-top:11px;font-weight:850;text-decoration:underline;text-underline-offset:4px}
.fjm-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.fjm-step{padding:23px;border:1px solid #306f91;border-radius:18px;background:#0d273c}
.fjm-step-number{display:grid;place-items:center;width:37px;height:37px;border:1px solid #50bde9;border-radius:12px;color:#90e9ff;font-weight:900}
.fjm-step h3{font-size:18px;color:#ebfaff;margin:14px 0 8px}
.fjm-step p{margin:0;font-size:14px}
.fjm-gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}
.fjm-project{display:flex;flex-direction:column;min-width:0;overflow:hidden;border:1px solid #2c7396;border-radius:18px;background:#102e43;color:#eefaff!important;text-decoration:none!important;transition:border-color .15s,transform .15s}
.fjm-project:hover{border-color:#69d6f6;transform:translateY(-2px)}
.fjm-project img{display:block;width:100%;height:210px;object-fit:cover;background:#16344a}
.fjm-project .fjm-project-noimage{display:grid;place-items:center;height:210px;background:linear-gradient(135deg,#1d5275,#0b273c);font-size:48px}
.fjm-project-content{padding:17px}.fjm-project-content span{display:block;color:#80d8f4;font-size:11px;text-transform:uppercase;letter-spacing:.1em;font-weight:750}
.fjm-project-content strong{display:block;margin:7px 0;font-size:17px;overflow-wrap:anywhere}
.fjm-project-content small{font-size:13px;color:#c3dce9;font-weight:750}
.fjm-section-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}
.fjm-faq{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}
.fjm-faq details{padding:17px 19px;border:1px solid #326f8b;border-radius:14px;background:#0d293d}
.fjm-faq summary{cursor:pointer;font-size:15px;font-weight:800;color:#e5f8ff}
.fjm-faq details p{margin:12px 0 0;font-size:14px}
.fjm-final{padding:clamp(22px,4vw,46px);margin:58px 0 0;border:1px solid #3c9fc6;border-radius:23px;background:linear-gradient(115deg,#105077,#0a263d);display:flex;justify-content:space-between;align-items:center;gap:26px}
.fjm-final h2{margin:0 0 8px;color:#f2fbff}.fjm-final p{margin:0}.fjm-final .btn{flex-shrink:0;white-space:normal;text-align:center}
.fjm-gallery-controls{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px;align-items:center}
.fjm-gallery-controls input{max-width:360px;min-width:200px;margin:0}
.fjm-filter{min-height:42px;padding:9px 14px;border:1px solid #4285a5;border-radius:99px;background:#0e3249;color:#e8f9ff;font:inherit;font-size:14px;cursor:pointer}
.fjm-filter[aria-pressed=true]{background:#097cae;color:white;border-color:#88dafa}
.fjm-gallery-empty{padding:20px;border:1px solid #346481;border-radius:15px;margin-top:15px}
.fjm-quote-helper{max-width:690px;padding:16px 18px;border:1px solid #347d9f;border-radius:14px;background:#0b2a42;margin:18px 0 24px}
.fjm-quote-helper strong{color:#d8f5ff}.fjm-quote-helper p{margin:6px 0 0;font-size:14px}
.fjm-quote-helper ul{margin:8px 0 0;padding-left:20px;color:#c6dce9;font-size:14px}
.fjm-quote-form{padding:clamp(18px,3vw,30px);max-width:700px;border:1px solid #32779d;border-radius:18px;background:#0c273c}
.fjm-quote-form .fjm-form-submit{width:100%;min-height:52px}
.fjm-quote-note{font-size:13px;margin:10px 0 0}
body.light .fjm-hero{background:linear-gradient(130deg,#e6f7ff,#c1e9fd)!important;border-color:#80bee0}
body.light .fjm-hero h1,body.light .fjm-hero-panel h2,body.light .fjm-step h3,body.light .fjm-service h3,body.light .fjm-final h2{color:#14394f!important}
body.light .fjm-accent{color:#077fae}
body.light .fjm-hero-lead,body.light .fjm-hero-panel p{color:#315b73}
body.light .fjm-kicker{color:#056997}
body.light .fjm-hero-panel,body.light .fjm-service,body.light .fjm-step,body.light .fjm-faq details,body.light .fjm-quote-helper,body.light .fjm-quote-form{background:#fff;border-color:#b4d8e9}
body.light .fjm-points li{background:#e5f5fd;border-color:#a5d0e4;color:#265c78}
body.light .fjm-service .fjm-icon{background:#d7effa}
body.light .fjm-project{background:#fff;color:#17425b!important}
body.light .fjm-project-content small{color:#376b82}
body.light .fjm-faq summary,body.light .fjm-quote-helper strong{color:#164863}
body.light .fjm-filter{background:#fff;color:#1b4c67}
body.light .fjm-filter[aria-pressed=true]{background:#087cae;color:#fff}
body.light .fjm-final{background:linear-gradient(110deg,#dbf2ff,#b3e4fb)}
@media(max-width:1050px){.fjm-services{grid-template-columns:repeat(2,minmax(0,1fr))}.fjm-hero{grid-template-columns:1fr}.fjm-hero-panel{display:grid;grid-template-columns:90px 1fr;column-gap:17px;align-items:center}.fjm-hero-panel img{grid-row:1/4}.fjm-hero-panel h2{margin:0 0 5px}}
@media(max-width:690px){.fjm-hero{padding:25px 18px!important;min-height:0}.fjm-hero h1{font-size:clamp(35px,9vw,53px)!important}.fjm-hero-actions{display:grid;grid-template-columns:1fr}.fjm-hero-actions a{width:100%}.fjm-hero-panel{padding:16px}.fjm-steps,.fjm-gallery{grid-template-columns:1fr 1fr}.fjm-project img,.fjm-project .fjm-project-noimage{height:155px}.fjm-faq{grid-template-columns:1fr}.fjm-final{display:block}.fjm-final .btn{margin-top:18px;width:100%}}
@media(max-width:460px){.fjm-services,.fjm-steps,.fjm-gallery{grid-template-columns:1fr}.fjm-project img,.fjm-project .fjm-project-noimage{height:230px}.fjm-service{padding:19px}.fjm-hero-panel{grid-template-columns:65px 1fr}.fjm-hero-panel img{width:60px;height:60px}.fjm-gallery-controls input{width:100%;max-width:100%;min-width:0}}
@media(prefers-reduced-motion:reduce){.fjm-project{transition:none}}
</style>"""

MARKETING_HOME_START = """<div class="fjm-home">
<section class="fjm-hero" aria-labelledby="fjm-hero-title">
 <div><span class="fjm-kicker" data-fjm-en="Custom 3D printing in Saguenay, Québec">Impression 3D sur mesure · Saguenay, Québec</span>
 <h1 id="fjm-hero-title">Votre idée mérite de <span class="fjm-accent">prendre forme.</span></h1>
 <p class="fjm-hero-lead" data-fjm-en="Custom parts, useful accessories, unique gifts and prototypes. Tell us what you have in mind: we turn your project into a real 3D print.">Pièces sur mesure, accessoires pratiques, cadeaux uniques et prototypes. Décrivez-nous votre idée : nous la transformons en objet concret grâce à l'impression 3D.</p>
 <div class="fjm-hero-actions"><a class="btn" href="/soumission" data-fjm-en="Get my free quote">Obtenir ma soumission gratuite</a><a class="btn fjm-outline" href="/galerie" data-fjm-en="Explore our projects">Découvrir nos réalisations</a></div>
 <p class="fjm-hero-sub" data-fjm-en="No obligation to order · STL and 3MF models accepted">Sans obligation d'achat · Modèles STL et 3MF acceptés</p>
 <ul class="fjm-points"><li data-fjm-en="📍 Made in Saguenay">📍 Fabriqué au Saguenay</li><li data-fjm-en="🧩 Custom projects">🧩 Projets personnalisés</li><li data-fjm-en="💬 Real human support">💬 Contact humain</li></ul>
 </div>
 <aside class="fjm-hero-panel"><img src="/identite/logo" width="89" height="89" alt="Logo Les Impressions du Fjord" loading="eager"><h2 data-fjm-en="From idea to object">De l'idée à l'objet</h2><p data-fjm-en="No 3D file? No problem. Describe your needs and we can discuss a solution together.">Pas de fichier 3D? Aucun problème. Expliquez-nous votre besoin et discutons d'une solution.</p><a href="/atelier-3d" data-fjm-en="Try our online 3D Studio">Essayer notre Atelier 3D en ligne</a></aside>
</section>
<section class="fjm-section" id="services">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="What we create">Ce qu'on réalise</span><h2 data-fjm-en="3D printing solutions for all your ideas">L'impression 3D pour toutes vos idées</h2><p data-fjm-en="One part, a gift, a prototype or a small production run: every project starts with a conversation.">Une pièce, un cadeau, un prototype ou une petite série : chaque projet commence par une conversation.</p></div>
 <div class="fjm-services">
  <article class="fjm-service"><span class="fjm-icon" aria-hidden="true">🧰</span><h3 data-fjm-en="Useful custom parts">Pièces pratiques sur mesure</h3><p data-fjm-en="Brackets, adapters, organizers and hard-to-find parts, designed around your needs.">Supports, adaptateurs, rangements et pièces difficiles à trouver, adaptés à vos besoins.</p><a href="/soumission" data-fjm-en="Request a price">Demander un prix</a></article>
  <article class="fjm-service"><span class="fjm-icon" aria-hidden="true">🎁</span><h3 data-fjm-en="Gifts and personalization">Cadeaux et personnalisation</h3><p data-fjm-en="Personalized creations, decorative pieces and unique objects for every occasion.">Créations personnalisées, décorations et objets uniques pour toutes les occasions.</p><a href="/galerie" data-fjm-en="Browse ideas">Voir des idées</a></article>
  <article class="fjm-service"><span class="fjm-icon" aria-hidden="true">⚙️</span><h3 data-fjm-en="Prototyping">Prototypage</h3><p data-fjm-en="Visualize, test and refine an idea with a tangible physical part.">Visualisez, testez et améliorez une idée avec une pièce physique.</p><a href="/soumission" data-fjm-en="Discuss my project">Parler de mon projet</a></article>
  <article class="fjm-service"><span class="fjm-icon" aria-hidden="true">🎨</span><h3 data-fjm-en="Interactive 3D Studio">Atelier 3D interactif</h3><p data-fjm-en="Import an STL or 3MF file or explore the online modeling tools.">Importez un fichier STL ou 3MF et explorez nos outils de création en ligne.</p><a href="/atelier-3d" data-fjm-en="Open the Studio">Ouvrir l'Atelier</a></article>
 </div>
</section>
<section class="fjm-section" id="fonctionnement">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Simple as 1, 2, 3">Simple comme 1, 2, 3</span><h2 data-fjm-en="How to place an order">Comment commander?</h2></div>
 <div class="fjm-steps"><article class="fjm-step"><span class="fjm-step-number">01</span><h3 data-fjm-en="Tell us your idea">Décrivez votre idée</h3><p data-fjm-en="Send us your needs, a picture, or your STL/3MF model through our quote form.">Envoyez vos besoins et, si vous en avez un, votre fichier STL/3MF avec le formulaire.</p></article>
 <article class="fjm-step"><span class="fjm-step-number">02</span><h3 data-fjm-en="Get a quote">Recevez une soumission</h3><p data-fjm-en="We discuss materials, finish, pricing and available options before any commitment.">On discute du matériau, de la finition, du prix et des options avant tout engagement.</p></article>
 <article class="fjm-step"><span class="fjm-step-number">03</span><h3 data-fjm-en="We make your part">On fabrique votre projet</h3><p data-fjm-en="Once approved, your project moves into production. You can follow its progress online.">Après votre approbation, votre projet passe en fabrication. Vous pouvez suivre son avancement en ligne.</p></article></div>
</section>
<section class="fjm-section" id="realisations">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="From our workshop">Directement de notre atelier</span><h2 data-fjm-en="Discover our latest projects">Découvrez nos dernières réalisations</h2><p data-fjm-en="Real work from our gallery, not stock images.">Des projets provenant de notre véritable galerie, pas des images génériques.</p></div>
 <div class="fjm-gallery">
 {% for item in featured %}<a class="fjm-project" href="/galerie/{{item.id}}" aria-label="Voir {{item.title}}">{% if item.has_photo %}<img src="/photo/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250">{% else %}<img src="/gallery/cover/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'fjm-project-noimage',textContent:'🧩'}))">{% endif %}<div class="fjm-project-content"><span>{{item.category}}</span><strong>{{item.title}}</strong><small data-fjm-en="See this project →">Voir cette réalisation →</small></div></a>
 {% else %}<div class="card"><h3 data-fjm-en="Projects coming soon">Nos créations arrivent bientôt</h3><p data-fjm-en="In the meantime, tell us about your project.">En attendant, parlez-nous de votre projet.</p><a class="btn" href="/soumission" data-fjm-en="Request a quote">Demander une soumission</a></div>{% endfor %}
 </div><div class="fjm-section-actions"><a class="btn fjm-outline" href="/galerie" data-fjm-en="See the full gallery">Voir toute la galerie</a></div>
</section>
<section class="fjm-section" id="questions">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Good to know">Bon à savoir</span><h2 data-fjm-en="Frequently asked questions">Questions fréquentes</h2></div>
 <div class="fjm-faq"><details><summary data-fjm-en="Do I need an STL or 3MF file?">Faut-il avoir un fichier STL ou 3MF?</summary><p data-fjm-en="Not necessarily. Tell us about your project and we can discuss the available options.">Pas nécessairement. Décrivez-nous votre projet et nous pourrons discuter des options possibles.</p></details>
 <details><summary data-fjm-en="Can I request a one-off part?">Est-ce possible de commander une seule pièce?</summary><p data-fjm-en="Yes. We take requests for individual parts and discuss small runs based on your needs.">Oui. Nous acceptons les demandes pour une pièce unique et discutons aussi des petites séries selon vos besoins.</p></details>
 <details><summary data-fjm-en="Which materials do you offer?">Quels matériaux offrez-vous?</summary><p data-fjm-en="Depending on the project, we can discuss PLA, PETG, ASA, TPU and other compatible options.">Selon le projet, nous pouvons discuter des options comme le PLA, PETG, ASA, TPU et d'autres matériaux compatibles.</p></details>
 <details><summary data-fjm-en="What are the price and delivery time?">Quel est le prix et quel est le délai?</summary><p data-fjm-en="Each project is different. We confirm price, material, turnaround and pickup/shipping options with your quote.">Chaque projet est différent. Nous confirmons le prix, le matériau, le délai et les options de remise ou d'expédition lors de la soumission.</p></details></div>
</section>"""

MARKETING_HOME_END = """
<section class="fjm-final" aria-label="Commencer un projet"><div><span class="fjm-kicker" data-fjm-en="Ready to get started?">Prêt à créer quelque chose?</span><h2 data-fjm-en="Let's bring your idea to life.">On donne vie à votre idée.</h2><p data-fjm-en="Tell us what you need. Your quote request comes with no obligation.">Expliquez-nous votre besoin. Une demande de soumission ne vous engage à rien.</p></div><a href="/soumission" class="btn" data-fjm-en="Request my free quote">Demander ma soumission gratuite</a></section>
</div>"""

MARKETING_GALLERY = """<section class="fjm-section" style="margin-top:0"><div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Our portfolio">Nos réalisations</span><h1 data-fjm-en="Ideas that took shape">Des idées devenues réalité</h1><p data-fjm-en="Browse our workshop creations, then request your own custom project.">Explorez les créations de notre atelier, puis demandez votre projet personnalisé.</p></div>
<div class="fjm-gallery-controls"><input type="search" id="fjmGallerySearch" placeholder="Rechercher une création…" aria-label="Rechercher dans la galerie" autocomplete="off"><button class="fjm-filter" id="fjmGalleryAll" type="button" aria-pressed="true" data-fjm-en="All creations">Toutes les créations</button></div>
<div class="fjm-gallery" id="fjmGalleryItems">{% for item in items %}<a class="fjm-project" href="/galerie/{{item.id}}" data-search="{{(item.title ~ ' ' ~ item.category ~ ' ' ~ item.description)|lower}}" aria-label="{{item.title}}">{% if item.has_photo %}<img src="/photo/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250">{% else %}<img src="/gallery/cover/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'fjm-project-noimage',textContent:'🧩'}))">{% endif %}<div class="fjm-project-content"><span>{{item.category}}</span><strong>{{item.title}}</strong><small data-fjm-en="View project →">Voir le projet →</small></div></a>{% else %}<p data-fjm-en="No projects published yet.">Aucune réalisation publiée pour le moment.</p>{% endfor %}</div>
<p id="fjmGalleryNoMatch" class="fjm-gallery-empty" hidden data-fjm-en="No projects match your search.">Aucune réalisation ne correspond à la recherche.</p><div class="fjm-section-actions"><a class="btn" href="/soumission" data-fjm-en="Request my custom project">Demander une création personnalisée</a></div></section>
<script>(function(){const input=document.getElementById('fjmGallerySearch'),root=document.getElementById('fjmGalleryItems'),empty=document.getElementById('fjmGalleryNoMatch'),all=document.getElementById('fjmGalleryAll');if(!input||!root)return;const cards=[...root.querySelectorAll('.fjm-project')];function filter(){const q=input.value.trim().toLocaleLowerCase();let count=0;for(const card of cards){const show=(card.getAttribute('data-search')||'').includes(q);card.hidden=!show;if(show)count++;}empty.hidden=count>0||cards.length===0;}input.addEventListener('input',filter);all.addEventListener('click',()=>{input.value='';filter();input.focus()});})();</script>"""

MARKETING_FORM_HELP = """<div class="fjm-quote-helper"><strong data-fjm-en="A clear quote with no obligation">Une soumission claire, sans obligation d'achat</strong><p data-fjm-en="To help us evaluate your project, please include:">Pour bien évaluer votre projet, indiquez idéalement :</p><ul><li data-fjm-en="The part's intended use and approximate size">L'utilisation de la pièce et ses dimensions approximatives</li><li data-fjm-en="Desired quantity and preferred colour/material">La quantité, la couleur et le matériau souhaités</li><li data-fjm-en="An STL or 3MF model, if available">Un fichier STL ou 3MF, si vous en avez un</li></ul></div>"""

MARKETING_SCRIPT = """<script>(function(){const nodes=[...document.querySelectorAll('[data-fjm-en]')];if(!nodes.length)return;for(const n of nodes)n.dataset.fjmFr=n.textContent;function apply(){let lang='fr';try{lang=localStorage.getItem('fjord-lang')==='en'?'en':'fr'}catch(e){}for(const n of nodes)n.textContent=lang==='en'?n.dataset.fjmEn:n.dataset.fjmFr;const search=document.getElementById('fjmGallerySearch');if(search)search.placeholder=lang==='en'?'Search projects…':'Rechercher une création…';}const sel=document.getElementById('fjord-lang');if(sel)sel.addEventListener('change',()=>setTimeout(apply,0));apply();})();</script>"""
