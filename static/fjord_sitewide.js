/* Les Impressions du Fjord — enhancements without external analytics or cookies. */
(function () {
  "use strict";
  function init() {
    const path=window.location.pathname;
    const body=document.body;
    if (!body) return;

    // A discreet, useful mobile ordering shortcut on public storefront pages.
    if (["/","/galerie","/contact"].includes(path) || /^\\/galerie\\/\\d+$/.test(path)) {
      const wrap=document.createElement("nav");
      wrap.className="fjord-mobile-actions";
      wrap.setAttribute("aria-label","Actions rapides");
      const quote=document.createElement("a");
      quote.className="fjord-mobile-main";
      quote.href="/soumission";
      quote.textContent="✦ Demander une soumission";
      const call=document.createElement("a");
      call.href="tel:+15819980831";
      call.textContent="☎ Nous appeler";
      wrap.append(quote,call);
      body.append(wrap);
      body.classList.add("fjord-has-mobile-bar");
    }

    // A lightweight real-category filter, based on published gallery records.
    const gallery=document.getElementById("fjmGalleryItems");
    const controls=document.querySelector(".fjm-gallery-controls");
    if (gallery && controls) {
      const cards=Array.from(gallery.querySelectorAll(".fjm-project"));
      const search=document.getElementById("fjmGallerySearch");
      const empty=document.getElementById("fjmGalleryNoMatch");
      const all=document.getElementById("fjmGalleryAll");
      let category="";
      const simplify=value=>String(value||"").normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").toLocaleLowerCase("fr-CA");
      const categories=Array.from(new Set(cards.map(c=>c.querySelector(".fjm-project-content span")?.textContent.trim()).filter(Boolean))).sort((a,b)=>a.localeCompare(b,"fr-CA"));
      const chips=[];
      const apply=()=>{
        const query=simplify(search?.value.trim()||"");
        let visible=0;
        cards.forEach(c=>{
          const cat=c.querySelector(".fjm-project-content span")?.textContent.trim()||"";
          const matches=(category===""||cat===category)&&simplify(c.dataset.search||c.textContent).includes(query);
          c.hidden=!matches;
          if(matches) visible++;
        });
        if(empty)empty.hidden=visible!==0||cards.length===0;
        if(all)all.setAttribute("aria-pressed", String(!category));
        chips.forEach(({button,name})=>button.setAttribute("aria-pressed",String(category===name)));
      };
      if (categories.length>1 && categories.length<=16) {
        categories.forEach(name=>{
          const button=document.createElement("button");
          button.type="button";
          button.className="fjm-filter";
          button.textContent=name;
          button.setAttribute("aria-pressed","false");
          button.addEventListener("click",()=>{category=category===name?"":name;apply()});
          controls.append(button);
          chips.push({button,name});
        });
      }
      search?.addEventListener("input",apply);
      all?.addEventListener("click",()=>{category="";apply()});
      apply();
    }

    // Files are still checked server-side; this gives quick, clear user feedback.
    const quoteForm=document.querySelector("form.fjm-quote-form");
    if (quoteForm) {
      const file=quoteForm.querySelector('input[name="model"]');
      if (file) {
        const info=document.createElement("p");
        info.className="fjord-file-state";
        info.id="fjordFileState";
        info.setAttribute("role","status");
        info.setAttribute("aria-live","polite");
        info.textContent="STL ou 3MF · Maximum 8 Mo";
        file.closest("label")?.after(info);
        file.addEventListener("change",()=>{
          const selected=file.files&&file.files[0];
          if(!selected){info.textContent="STL ou 3MF · Maximum 8 Mo";info.removeAttribute("data-status");file.setCustomValidity("");return;}
          const size=(selected.size/(1024*1024)).toLocaleString("fr-CA",{maximumFractionDigits:1});
          const allowed=/\\.(stl|3mf)$/i.test(selected.name);
          const valid=allowed&&selected.size<=8*1024*1024;
          info.textContent=valid?"✓ "+selected.name+" ("+size+" Mo)":"Fichier non accepté. Choisissez un STL ou 3MF de 8 Mo maximum.";
          info.dataset.status=valid?"ready":"error";
          file.setCustomValidity(valid?"":"Fichier invalide ou trop volumineux (maximum 8 Mo).");
        });
      }
      const button=quoteForm.querySelector('button[type="submit"]');
      quoteForm.addEventListener("submit",()=>{
        if(!quoteForm.checkValidity())return;
        if(button){button.disabled=true;button.textContent="Envoi en cours…";}
      });
    }

    // Highlight a quote request link in galleries without interrupting preview controls.
    document.querySelectorAll('.gallery-detail a[href^="/soumission?projet="]').forEach(a=>{
      a.setAttribute("aria-label","Demander une soumission pour un projet similaire");
    });

    // Use the current copy, avoid manufactured testimonials or fake scarcity.
    const lang=document.getElementById("fjord-lang");
    const mobile=document.querySelector(".fjord-mobile-actions");
    function translateMobile(){
      if(!mobile)return;
      const english=lang?.value==="en";
      const links=mobile.querySelectorAll("a");
      if(links.length===2){
        links[0].textContent=english?"✦ Get a free quote":"✦ Demander une soumission";
        links[1].textContent=english?"☎ Call us":"☎ Nous appeler";
      }
    }
    lang?.addEventListener("change",translateMobile);
    translateMobile();
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",init);
  else init();
})();