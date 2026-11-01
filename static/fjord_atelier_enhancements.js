/* Les Impressions du Fjord - 3D text and surface painting.
   Paint data belongs to the editable Fjord JSON, not printable STL/G-code.
   The UI never claims Bambu-compatible multicolor toolpaths. */
export function installFjordEnhancements(api){
 const {THREE,renderer,stage}=api;
 const $=id=>document.getElementById(id);
 const notice=(text)=>{const el=$('fjordPaintStatus');if(el)el.textContent=text;};
 let fontPromise=null,paintOn=false,paintTool='brush',paintHex='#f04c55',brushSize=7,strokePointer=null;
 const validHex=v=>typeof v==='string'&&/^#[0-9a-fA-F]{6}$/.test(v);
 function getFont(){
  if(!fontPromise)fontPromise=Promise.all([
   import('three/addons/loaders/FontLoader.js'),
   import('three/addons/geometries/TextGeometry.js'),
   fetch('/static/fjord_helvetiker_regular.json').then(r=>{if(!r.ok)throw Error('Police 3D indisponible');return r.json()})
  ]).then(([fl,tg,data])=>({font:new fl.FontLoader().parse(data),TextGeometry:tg.TextGeometry}))
   .catch(e=>{fontPromise=null;throw e});
  return fontPromise;
 }
 async function textGeometry(spec){
  const {font,TextGeometry}=await getFont();
  const geometry=new TextGeometry(spec.value,{font,size:spec.size,depth:spec.depth,curveSegments:10,bevelEnabled:false});
  geometry.computeBoundingBox();
  if(!geometry.boundingBox||geometry.getAttribute('position').count===0){geometry.dispose();throw Error('Ce texte ne contient aucun contour imprimable.');}
  const b=geometry.boundingBox;
  geometry.translate(-(b.min.x+b.max.x)/2,-(b.min.y+b.max.y)/2,-b.min.z);
  geometry.computeVertexNormals();geometry.computeBoundingBox();
  return geometry;
 }
 async function editText(update){
  const status=$('fjordTextStatus'),button=$(update?'fjordTextUpdate':'fjordTextCreate');
  let value=$('fjordTextInput').value.replace(/\s+/g,' ').trim();
  const size=Number($('fjordTextSize').value),depth=Number($('fjordTextDepth').value);
  if(!value||value.length>60||!Number.isFinite(size)||size<2||size>100||!Number.isFinite(depth)||depth<.6||depth>30){
   status.textContent='Inscription obligatoire (60 caractères max), hauteur de 2 à 100 mm, épaisseur de 0,6 à 30 mm.';return;
  }
  const target=api.selected();
  if(update&&(!target||!target.userData.fjordText)){status.textContent='Sélectionne une inscription créée dans cet atelier avant de la modifier.';return;}
  button.disabled=true;
  try{
   const spec={value,size,depth};
   const geometry=await textGeometry(spec);
   if(geometry.getAttribute('position').count>600000){geometry.dispose();throw Error('Inscription trop complexe pour cet appareil.');}
   api.remember();
   if(update){
    const originalColor=target.userData.fjordPaintBase;
    api.removeSelectionTint(target);
    const prev=target.geometry;target.geometry=geometry;prev.dispose();
    delete target.userData.fjordPaintFaces;delete target.userData.fjordPaintBase;
    target.material.vertexColors=false;
    if(Number.isInteger(originalColor))target.material.color.setHex(originalColor);
    target.material.needsUpdate=true;
    api.addSelectionTint(target);
    target.userData.fjordText=spec;
    api.snapPartToBed(target);api.pick(target);
   }else{
    const mesh=api.makeMesh(geometry,'imported',value.slice(0,60));
    mesh.userData.fjordText=spec;
    mesh.position.set(0,0,0);
    api.pick(mesh);
   }
   api.sync();
   status.textContent='✓ Texte 3D créé et modifiable. Tu peux ensuite le déplacer, le peindre ou le grouper avec une pièce.';
  }catch(error){status.textContent='Impossible de créer le texte : '+String(error.message||error);}
  finally{button.disabled=false;}
 }
 $('fjordTextCreate')?.addEventListener('click',()=>editText(false));
 $('fjordTextUpdate')?.addEventListener('click',()=>editText(true));
 // Load form values from selected text on part selection.
 function syncText(){
  const label=$('fjordPaintModelLabel');
  if(label)label.textContent=api.selected()?.name||'Aucune pièce sélectionnée';
  const data=api.selected()?.userData?.fjordText;
  if(data&&document.activeElement?.id!=='fjordTextInput'){
   $('fjordTextInput').value=data.value;
   $('fjordTextSize').value=data.size;
   $('fjordTextDepth').value=data.depth;
  }
 }
 function paintGeom(mesh){
  if(mesh.userData.mergedParts){notice('Sépare le groupe Merge avant de peindre ses faces.');return false;}
  if(mesh.geometry.index){
   const original=mesh.geometry;
   mesh.geometry=original.toNonIndexed();original.dispose();
  }
  if(!mesh.userData.fjordPaintFaces||typeof mesh.userData.fjordPaintFaces!=='object')
    mesh.userData.fjordPaintFaces={};
  if(!Number.isInteger(mesh.userData.fjordPaintBase))
    mesh.userData.fjordPaintBase=api.getBaseColor(mesh);
  const geometry=mesh.geometry,pos=geometry.getAttribute('position');
  if(!pos||pos.count%3!==0||pos.count/3>500000){notice('Cette pièce est trop complexe pour la peinture en direct.');return false;}
  let colors=geometry.getAttribute('color');
  if(!colors||colors.count!==pos.count){
   const base=new THREE.Color(mesh.userData.fjordPaintBase);
   const raw=new Float32Array(pos.count*3);
   for(let i=0;i<pos.count;i++){raw[i*3]=base.r;raw[i*3+1]=base.g;raw[i*3+2]=base.b;}
   colors=new THREE.BufferAttribute(raw,3);geometry.setAttribute('color',colors);
  }
  for(const [key,value] of Object.entries(mesh.userData.fjordPaintFaces)){
   const i=Number(key),color=new THREE.Color(value);
   if(Number.isInteger(i)&&i>=0&&i<pos.count/3&&validHex(value))
    for(let j=i*3;j<i*3+3;j++)colors.setXYZ(j,color.r,color.g,color.b);
  }
  api.removeSelectionTint(mesh);
  mesh.material.color.set(0xffffff);mesh.material.vertexColors=true;mesh.material.needsUpdate=true;
  if(api.selected()===mesh)api.addSelectionTint(mesh);
  colors.needsUpdate=true;
  return true;
 }
 function setTriangle(mesh,index,color){
  const geom=mesh.geometry,attr=geom.getAttribute('color'),faceCount=geom.getAttribute('position').count/3;
  if(!Number.isInteger(index)||index<0||index>=faceCount||!attr)return;
  const base='#'+mesh.userData.fjordPaintBase.toString(16).padStart(6,'0');
  if(color.toLowerCase()===base.toLowerCase())delete mesh.userData.fjordPaintFaces[index];
  else mesh.userData.fjordPaintFaces[index]=color.toUpperCase();
  const rgb=new THREE.Color(color);
  for(let i=index*3;i<index*3+3;i++)attr.setXYZ(i,rgb.r,rgb.g,rgb.b);
  attr.needsUpdate=true;
 }
 function faceNormal(mesh,i){
  const pos=mesh.geometry.getAttribute('position'),a=new THREE.Vector3().fromBufferAttribute(pos,i*3),
    b=new THREE.Vector3().fromBufferAttribute(pos,i*3+1),c=new THREE.Vector3().fromBufferAttribute(pos,i*3+2);
  return b.sub(a).cross(c.sub(a)).normalize();
 }
 function faceCenter(mesh,i){
  const pos=mesh.geometry.getAttribute('position'),c=new THREE.Vector3();
  for(let j=0;j<3;j++)c.add(new THREE.Vector3().fromBufferAttribute(pos,i*3+j));
  return mesh.localToWorld(c.multiplyScalar(1/3));
 }
 function regionFaces(mesh,seed){
  const p=mesh.geometry.getAttribute('position'),count=p.count/3;
  if(count>85000){notice('Remplissage régional limité à 85 000 triangles : utilise le pinceau ou les facettes.');return [seed];}
  const norm=faceNormal(mesh,seed),edgeMap=new Map(),neighbors=Array.from({length:count},()=>[]);
  const key=i=>[p.getX(i),p.getY(i),p.getZ(i)].map(n=>Math.round(n*1000)).join(',');
  for(let i=0;i<count;i++){
   const pts=[key(i*3),key(i*3+1),key(i*3+2)];
   for(let j=0;j<3;j++){
    const a=pts[j],b=pts[(j+1)%3],k=a<b?a+'|'+b:b+'|'+a;
    if(!edgeMap.has(k))edgeMap.set(k,[]);
    edgeMap.get(k).push(i);
   }
  }
  for(const ids of edgeMap.values())if(ids.length>1&&ids.length<12)
   for(const a of ids)for(const b of ids)if(a!==b)neighbors[a].push(b);
  const seen=new Set([seed]),queue=[seed],max=15000;
  for(let x=0;x<queue.length&&queue.length<max;x++){
   for(const j of neighbors[queue[x]])if(!seen.has(j)){
    seen.add(j);
    if(faceNormal(mesh,j).dot(norm)>Math.cos(Math.PI/6))queue.push(j);
   }
  }
  if(queue.length>=max)notice('Région limitée à 15 000 facettes pour protéger les performances.');
  return queue;
 }
 function hitPaint(e){
  const hit=api.findHit(e);
  return hit&&hit.faceIndex!==undefined?hit:null;
 }
 function drawHit(hit){
  if(!hit||!api.models().includes(hit.object))return false;
  const mesh=hit.object;
  if(!paintGeom(mesh))return false;
  mesh.updateMatrixWorld(true);
  const count=mesh.geometry.getAttribute('position').count/3,seed=hit.faceIndex;
  if(!Number.isInteger(seed)||seed<0||seed>=count)return false;
  const color=paintTool==='eraser'?'#'+mesh.userData.fjordPaintBase.toString(16).padStart(6,'0'):paintHex;
  let targets;
  if(paintTool==='triangle')targets=[seed];
  else if(paintTool==='fill')targets=regionFaces(mesh,seed);
  else {
   // Brush/eraser: local painting. Sphere: nearby faces through the mesh.
   // Height: a complete horizontal Z band through this object, like a layer painting tool.
   const center=hit.point,normal=faceNormal(mesh,seed);
   const radius=brushSize;
   targets=[];
   if(count>120000){targets=[seed];notice('Pièce très détaillée : utilise le mode facette pour conserver la fluidité.');}
   else for(let i=0;i<count;i++){
    const position=faceCenter(mesh,i);
    const selected=paintTool==='height'
      ? Math.abs(position.z-center.z)<=radius/2
      : position.distanceToSquared(center)<=radius*radius &&
        (paintTool==='sphere'||faceNormal(mesh,i).dot(normal)>.65);
    if(selected)targets.push(i);
   }
  }
  for(const i of targets)setTriangle(mesh,i,color);
  notice('✓ '+targets.length+' facette(s) modifiée(s). Peinture conservée dans le projet JSON du Fjord.');
  return true;
 }
 function chooseColor(hex){
  if(!validHex(hex))return;
  paintHex=hex.toUpperCase();
  $('fjordPaintColor').value=hex;
  $('fjordPaintColorLabel').textContent=paintHex;
  document.querySelectorAll('#fjordPaintPanel [data-fjord-color]').forEach(button=>{
   button.setAttribute('aria-pressed',String(button.dataset.fjordColor?.toUpperCase()===paintHex));
  });
 }
 function paintToolChoose(value){
  if(!['brush','sphere','triangle','fill','height','eraser'].includes(value))return;
  paintTool=value;
  document.querySelectorAll('[data-fjord-paint-tool]').forEach(b=>{
   const active=b.dataset.fjordPaintTool===paintTool;b.classList.toggle('active',active);
   b.setAttribute('aria-pressed',String(active));
  });
 }
 function close(){
  if(strokePointer!==null){strokePointer=null;api.orbit.enabled=true;}
  paintOn=false;$('fjordPaintPanel').hidden=true;
  $('fjordPaintToggle')?.setAttribute('aria-pressed','false');
  $('fjordPaintToggle')?.classList.remove('active');
  $('fjordPaintFast')?.setAttribute('aria-pressed','false');
  $('fjordPaintFast')?.classList.remove('active');
  $('mobilePaintBtn')?.setAttribute('aria-pressed','false');
  renderer.domElement.style.cursor='';
 }
 function open(){
  if(!api.models().length){notice('Importe ou crée une pièce pour commencer.');}
  api.disableCurrentTools();
  paintOn=true;$('fjordPaintPanel').hidden=false;
  $('fjordPaintToggle')?.setAttribute('aria-pressed','true');
  $('fjordPaintToggle')?.classList.add('active');
  $('fjordPaintFast')?.setAttribute('aria-pressed','true');
  $('fjordPaintFast')?.classList.add('active');
  $('mobilePaintBtn')?.setAttribute('aria-pressed','true');
  renderer.domElement.style.cursor='crosshair';
  paintToolChoose(paintTool);
  syncText();
  notice('Mode peinture actif : choisis un pinceau et une couleur AMS ou personnalisée, puis peins directement sur la pièce.');
 }
 function toggle(){paintOn?close():open();}
 $('fjordPaintToggle')?.addEventListener('click',toggle);
 $('fjordPaintFast')?.addEventListener('click',toggle);
 $('mobilePaintBtn')?.addEventListener('click',toggle);
 $('fjordPaintClose')?.addEventListener('click',close);
 document.querySelectorAll('[data-fjord-paint-tool]').forEach(btn=>btn.addEventListener('click',()=>paintToolChoose(btn.dataset.fjordPaintTool)));
 // Display real detected AMS spools in the painting toolbar instead of asking
 // users to navigate back to whole-part Properties. Empty/offline AMS is explicit.
 const paintAms=$('fjordPaintAmsPalette'),amsSource=$('fjordAmsSlots');
 function renderPaintAms(){
  if(!paintAms||!amsSource)return;
  const buttons=[...amsSource.querySelectorAll('button')].filter(button=>button.querySelector('.fjord-ams-swatch'));
  paintAms.replaceChildren();
  for(const source of buttons){
   const swatch=source.querySelector('.fjord-ams-swatch');
   const color=new THREE.Color(swatch.style.backgroundColor);
   const hex='#'+color.getHexString().toUpperCase();
   const button=document.createElement('button');
   button.type='button';
   button.className='fjord-paint-swatch';
   button.style.setProperty('--swatch',hex);
   button.dataset.fjordColor=hex;
   button.setAttribute('aria-label','Peindre avec '+(source.getAttribute('aria-label')||hex));
   button.title=source.title||hex;
   const detail=document.createElement('small');
   detail.textContent=(source.querySelector('strong')?.textContent||'AMS').slice(0,15);
   button.append(detail);
   button.addEventListener('click',()=>chooseColor(hex));
   paintAms.append(button);
  }
  $('fjordPaintAmsMessage').textContent=paintAms.childElementCount
   ?paintAms.childElementCount+' bobine(s) disponible(s). Une couleur choisie ici peint les faces, pas toute la pièce.'
   :($('fjordAmsStatus')?.textContent||'Aucune couleur AMS disponible. Utilise la palette personnalisée.');
  chooseColor(paintHex);
 }
 if(amsSource){
  const observer=new MutationObserver(renderPaintAms);
  observer.observe(amsSource,{childList:true});
  renderPaintAms();
 }
 $('fjordPaintRefreshAms')?.addEventListener('click',()=>{
  $('fjordAmsRefresh')?.click();
  $('fjordPaintAmsMessage').textContent='Actualisation des bobines en cours…';
 });
 $('fjordPaintPresets')?.addEventListener('click',event=>{
  const color=event.target.closest('[data-fjord-color]')?.dataset.fjordColor;
  if(color)chooseColor(color);
 });
 $('fjordPaintColor')?.addEventListener('input',event=>chooseColor(event.target.value));
 $('fjordPaintSize')?.addEventListener('input',event=>{
  brushSize=Number(event.target.value)||7;$('fjordPaintSizeLabel').textContent=brushSize+' mm';
 });
 $('fjordPaintEraseAll')?.addEventListener('click',()=>{
  const model=api.selected();
  if(!model){notice('Sélectionne une pièce.');return;}
  if(!model.userData.fjordPaintFaces){notice('Aucune peinture sur cette pièce.');return;}
  api.remember();
  const originalColor=model.userData.fjordPaintBase;
  api.removeSelectionTint(model);
  delete model.userData.fjordPaintFaces;
  delete model.userData.fjordPaintBase;
  model.geometry.deleteAttribute('color');
  model.material.vertexColors=false;
  model.material.color.setHex(Number.isInteger(originalColor)?originalColor:0x5bc6eb);
  api.addSelectionTint(model);
  model.material.needsUpdate=true;api.sync();
  notice('✓ Peinture de la pièce effacée. Annuler reste disponible.');
 });
 // Existing AMS palette selects the paint color instead of recoloring the whole object while painting.
 $('fjordAmsSlots')?.addEventListener('click',event=>{
  if(!paintOn)return;
  const button=event.target.closest('button'),swatch=button?.querySelector('.fjord-ams-swatch');
  if(!swatch)return;
  const color=new THREE.Color(swatch.style.backgroundColor);
  chooseColor('#'+color.getHexString());
  event.preventDefault();event.stopImmediatePropagation();notice('Couleur AMS choisie : '+paintHex);
 },true);
 $('fjordApplyColor')?.addEventListener('click',event=>{
  if(!paintOn)return;
  chooseColor($('fjordManualColor').value);
  event.preventDefault();event.stopImmediatePropagation();notice('Couleur de peinture choisie : '+paintHex);
 },true);
 function onPointerDown(e){
  if(!paintOn||e.button!==0||e.ctrlKey||e.metaKey||e.shiftKey)return false;
  const hit=hitPaint(e);
  if(!hit){close();api.clearSelectionOnBlank();e.preventDefault();e.stopImmediatePropagation();return true;}
  if(hit.object!==api.selected())api.pick(hit.object);
  api.remember();
  if(!drawHit(hit))return true;
  strokePointer=e.pointerId;
  api.orbit.enabled=false;
  try{renderer.domElement.setPointerCapture(e.pointerId);}catch{}
  e.preventDefault();e.stopImmediatePropagation();
  return true;
 }
 function onPointerMove(e){
  if(strokePointer===null||strokePointer!==e.pointerId)return false;
  if(['brush','sphere','eraser'].includes(paintTool))drawHit(hitPaint(e));
  e.preventDefault();e.stopImmediatePropagation();return true;
 }
 function onPointerUp(e){
  if(strokePointer===null||strokePointer!==e.pointerId)return false;
  strokePointer=null;api.orbit.enabled=true;
  try{renderer.domElement.releasePointerCapture(e.pointerId);}catch{}
  e.preventDefault();e.stopImmediatePropagation();return true;
 }
 function restoreMesh(mesh,entry){
  const data=entry?.paintFaces;
  if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).length>150000)return;
  mesh.userData.fjordPaintFaces={};
  for(const [key,value] of Object.entries(data))
   if(/^\d{1,8}$/.test(key)&&validHex(value))mesh.userData.fjordPaintFaces[key]=value;
  mesh.userData.fjordPaintBase=Number.isInteger(entry.paintBase)&&entry.paintBase>=0&&entry.paintBase<=0xffffff?entry.paintBase:api.getBaseColor(mesh);
  paintGeom(mesh);
 }
 function resetForWholeColor(mesh){
  if(!mesh.userData.fjordPaintFaces)return;
  delete mesh.userData.fjordPaintFaces;delete mesh.userData.fjordPaintBase;
  mesh.geometry.deleteAttribute('color');
  mesh.material.vertexColors=false;mesh.material.needsUpdate=true;
 }
 function serializeMesh(mesh){
  return {
   paintFaces:mesh.userData.fjordPaintFaces?{...mesh.userData.fjordPaintFaces}:null,
   paintBase:Number.isInteger(mesh.userData.fjordPaintBase)?mesh.userData.fjordPaintBase:null,
   textSpec:mesh.userData.fjordText?{...mesh.userData.fjordText}:null
  };
 }
 // Expose only the actions the core studio must coordinate.
 return {toggle,open,close,onPointerDown,onPointerMove,onPointerUp,restoreMesh,serializeMesh,resetForWholeColor,
  closeOnBlank:()=>{if(paintOn)close();},syncText,isActive:()=>paintOn};
}
