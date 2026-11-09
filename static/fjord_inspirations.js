/* Lightweight carousel: 5 curated Wikimedia photos, no visitor tracking. */
(()=>{
 const track=document.getElementById('fji-track');
 if(!track)return;
 const cards=[...track.querySelectorAll('.fji-card')];
 if(!cards.length)return;
 const prev=document.getElementById('fji-prev'),next=document.getElementById('fji-next');
 const count=document.getElementById('fji-counter');
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
 let inView=false,paused=false,manualUntil=0,timer;
 const gap=()=>parseFloat(getComputedStyle(track).columnGap)||16;
 const step=()=>cards[0].getBoundingClientRect().width+gap();
 const position=()=>Math.max(0,Math.min(cards.length-1,Math.round(track.scrollLeft/Math.max(step(),1))));
 function sync(){if(count)count.textContent=(position()+1)+' / '+cards.length;}
 function move(delta,manual=false){
  if(manual)manualUntil=Date.now()+12000;
  const nextIndex=(position()+delta+cards.length)%cards.length;
  track.scrollTo({left:nextIndex*step(),behavior:reduced.matches?'instant':'smooth'});
  if(reduced.matches)sync();
 }
 prev?.addEventListener('click',()=>move(-1,true));
 next?.addEventListener('click',()=>move(1,true));
 track.addEventListener('keydown',event=>{
  if(event.target.closest('a,button,input,select,textarea'))return;
  if(event.key==='ArrowRight'||event.key==='ArrowLeft'){
   event.preventDefault();move(event.key==='ArrowRight'?1:-1,true);
  }
 });
 track.addEventListener('pointerdown',()=>{manualUntil=Date.now()+15000;},{passive:true});
 track.addEventListener('scroll',sync,{passive:true});
 track.addEventListener('mouseenter',()=>{paused=true});
 track.addEventListener('mouseleave',()=>{paused=false});
 track.addEventListener('focusin',()=>{paused=true});
 track.addEventListener('focusout',()=>{paused=track.contains(document.activeElement)});
 document.querySelectorAll('.fji-card img').forEach(img=>{
  img.addEventListener('error',()=>{img.hidden=true});
 });
 if('IntersectionObserver' in window){
  const observer=new IntersectionObserver(items=>{
   inView=items.some(item=>item.isIntersecting);
  },{threshold:.12});
  observer.observe(track);
 }else{inView=true}
 timer=window.setInterval(()=>{
  if(!inView||paused||document.hidden||reduced.matches||Date.now()<manualUntil)return;
  move(1,false);
 },6200);
 window.addEventListener('pagehide',()=>window.clearInterval(timer),{once:true});
 sync();
})();
