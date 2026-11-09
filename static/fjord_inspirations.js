/* 50 credited and reusable Commons photos; keyboard, touch, and category filters. */
(()=>{
 const track=document.getElementById('fji-track');
 if(!track)return;
 const cards=[...track.querySelectorAll('.fji-card')];
 const chips=[...document.querySelectorAll('.fji-filter')];
 if(!cards.length)return;
 const prev=document.getElementById('fji-prev');
 const next=document.getElementById('fji-next');
 const counter=document.getElementById('fji-counter');
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
 let inView=false,paused=false,manualUntil=0,timer;
 const visible=()=>cards.filter(card=>!card.hidden);
 const gap=()=>parseFloat(getComputedStyle(track).columnGap)||16;
 const step=()=>{const first=visible()[0];return first?first.getBoundingClientRect().width+gap():1};
 const position=()=>{
  const count=visible().length;
  return Math.max(0,Math.min(count-1,Math.round(track.scrollLeft/Math.max(step(),1))));
 };
 function sync(){
  const count=visible().length;
  if(counter)counter.textContent=count?(position()+1)+' / '+count:'0 / 0';
  if(prev)prev.disabled=count<2;
  if(next)next.disabled=count<2;
 }
 function move(delta,manual=false){
  const count=visible().length;
  if(count<2)return;
  if(manual)manualUntil=Date.now()+12000;
  const nextIndex=(position()+delta+count)%count;
  track.scrollTo({left:nextIndex*step(),behavior:reduced.matches?'instant':'smooth'});
  if(reduced.matches)sync();
 }
 function filter(category){
  manualUntil=Date.now()+12000;
  for(const card of cards)
   card.hidden=category!=='all'&&card.getAttribute('data-fji-category')!==category;
  for(const chip of chips)
   chip.setAttribute('aria-pressed',String(chip.getAttribute('data-fji-filter')===category));
  track.scrollTo({left:0,behavior:'instant'});
  // Refresh immediately for screen readers and automated browsers;
  // refresh once more after the browser has completed its layout.
  sync();
  requestAnimationFrame(sync);
 }
 chips.forEach(chip=>chip.addEventListener('click',()=>filter(chip.dataset.fjiFilter||'all')));
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
