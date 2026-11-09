/* Les Impressions du Fjord — enhancements without external analytics or cookies. */
(function () {
  "use strict";
  function init() {
    const path=window.location.pathname;
    const body=document.body;
    if (!body) return;

    // A discreet, useful mobile ordering shortcut on public storefront pages.
    if (["/","/galerie","/contact"].includes(path) || /^\/galerie\/\d+$/.test(path)) {
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
      const ready=document.getElementById("fjmGalleryReady");
      let category="",readyOnly=false;
      const simplify=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("fr-CA");
      const categories=Array.from(new Set(cards.map(c=>c.querySelector(".fjm-project-content span")?.textContent.trim()).filter(Boolean))).sort((a,b)=>a.localeCompare(b,"fr-CA"));
      const chips=[];
      const apply=()=>{
        const query=simplify(search?.value.trim()||"");
        let visible=0;
        cards.forEach(c=>{
          const cat=c.querySelector(".fjm-project-content span")?.textContent.trim()||"";
          const matches=(category===""||cat===category)&&(!readyOnly||c.dataset.ready==="1")&&simplify(c.dataset.search||c.textContent).includes(query);
          c.hidden=!matches;
          if(matches) visible++;
        });
        if(empty)empty.hidden=visible!==0||cards.length===0;
        if(all)all.setAttribute("aria-pressed", String(!category&&!readyOnly));
        if(ready)ready.setAttribute("aria-pressed",String(readyOnly));
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
      all?.addEventListener("click",()=>{category="";readyOnly=false;apply()});
      ready?.addEventListener("click",()=>{readyOnly=!readyOnly;apply()});
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
        const fileEnglish=()=>document.getElementById("fjord-lang")?.value==="en";
        const updateFileState=()=>{
          const selected=file.files&&file.files[0],english=fileEnglish();
          if(!selected){
            info.textContent=english?"STL or 3MF · 16 MB maximum":"STL ou 3MF · Maximum 16 Mo";
            info.removeAttribute("data-status");file.setCustomValidity("");return;
          }
          const size=(selected.size/(1024*1024)).toLocaleString(english?"en-CA":"fr-CA",{maximumFractionDigits:1});
          const allowed=/\.(stl|3mf)$/i.test(selected.name);
          const valid=allowed&&selected.size<=16*1024*1024;
          info.textContent=valid?"✓ "+selected.name+" ("+size+(english?" MB)":" Mo)"):(english?"File not accepted. Choose an STL or 3MF up to 16 MB.":"Fichier refusé. Choisissez un STL ou 3MF de 16 Mo maximum.");
          info.dataset.status=valid?"ready":"error";
          file.setCustomValidity(valid?"":(english?"Invalid file or too large (16 MB maximum).":"Fichier invalide ou trop volumineux (maximum 16 Mo)."));
        };
        info.textContent="STL ou 3MF · Maximum 16 Mo";
        file.closest("label")?.after(info);
        file.addEventListener("change",updateFileState);
        document.getElementById("fjord-lang")?.addEventListener("change",updateFileState);
      }
      // Instant private preview; the photo stays local until the user submits the form.
      const photo=quoteForm.querySelector('input[name="reference_photo"]');
      const preview=document.getElementById("fjordReferencePreview");
      const photoImage=document.getElementById("fjordReferenceImage");
      const photoLabel=document.getElementById("fjordReferenceFilename");
      const photoRemove=document.getElementById("fjordReferenceRemove");
      let photoUrl=null;
      function clearPhoto(){
        if(photoUrl){URL.revokeObjectURL(photoUrl);photoUrl=null;}
        if(photo)photo.value="";
        if(photo)photo.setCustomValidity("");
        if(photoImage)photoImage.removeAttribute("src");
        if(preview)preview.hidden=true;
      }
      if(photo&&preview&&photoImage){
        const updatePhotoPreview=()=>{
          if(photoUrl){URL.revokeObjectURL(photoUrl);photoUrl=null;}
          const file=photo.files?.[0],english=document.getElementById("fjord-lang")?.value==="en";
          if(!file){clearPhoto();return;}
          const types=["image/jpeg","image/png","image/webp"];
          const valid=types.includes(file.type)&&file.size<=4*1024*1024&&file.size>0;
          photo.setCustomValidity(valid?"":(english?"Choose a JPG, PNG or WebP image up to 4 MB.":"Choisissez une image JPG, PNG ou WebP de 4 Mo maximum."));
          if(!valid){if(photoLabel)photoLabel.textContent=english?"Photo format or size not accepted":"Format ou taille de photo non acceptés";photoImage.removeAttribute("src");preview.hidden=false;return;}
          photoUrl=URL.createObjectURL(file);
          photoImage.src=photoUrl;
          if(photoLabel)photoLabel.textContent=file.name+" · "+(file.size/(1024*1024)).toLocaleString(english?"en-CA":"fr-CA",{maximumFractionDigits:1})+(english?" MB":" Mo");
          preview.hidden=false;
        };
        photo.addEventListener("change",updatePhotoPreview);
        document.getElementById("fjord-lang")?.addEventListener("change",()=>{if(photo.files?.[0])updatePhotoPreview();});
        photoRemove?.addEventListener("click",clearPhoto);
        window.addEventListener("pagehide",()=>{if(photoUrl)URL.revokeObjectURL(photoUrl);});
      }
      const button=quoteForm.querySelector('button[type="submit"]');
      quoteForm.addEventListener("submit",()=>{
        if(!quoteForm.checkValidity())return;
        if(button){button.disabled=true;button.textContent=document.getElementById("fjord-lang")?.value==="en"?"Sending…":"Envoi en cours…";}
      });
    }

    // Native share sheet on mobile; safe copy-link fallback on desktop.
    const share=document.querySelector(".fjord-share-project");
    if(share){
      share.addEventListener("click",async ()=>{
        const url=window.location.href.split("#")[0];
        const title=share.getAttribute("data-fjord-share-title")||"Les Impressions du Fjord";
        const output=document.getElementById("fjordShareResult");
        const note=message=>{if(output)output.textContent=message;};
        if(navigator.share){
          try{await navigator.share({url,title});note("Réalisation partagée.");return;}
          catch(error){if(error?.name==="AbortError")return;}
        }
        try{
          if(!navigator.clipboard?.writeText)throw Error("Clipboard unavailable");
          await navigator.clipboard.writeText(url);
          note("Lien de la réalisation copié.");
        }catch(error){
          note("Copiez l'adresse de cette page pour la partager.");
        }
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