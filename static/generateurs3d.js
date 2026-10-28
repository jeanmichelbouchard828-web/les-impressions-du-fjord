// Parametric 3D part generators for Atelier 3D du Fjord.
// Units: mm. Geometry is approximate and should be checked before mechanical use.
export const generatorKinds = [
 {id:'pipe',fr:'Tuyau droit',en:'Straight pipe',fields:[
  ['diameter','Diamètre extérieur','Outside diameter',60,2,400,.1],
  ['wall','Épaisseur de paroi','Wall thickness',3,.5,40,.1],
  ['length','Longueur','Length',100,2,600,.1]]},
 {id:'adapter',fr:'Adaptateur / réduction',en:'Reducer / adapter',fields:[
  ['diameter','Grand diamètre extérieur','Large outside diameter',75,2,400,.1],
  ['diameter2','Petit diamètre extérieur','Small outside diameter',60,2,400,.1],
  ['wall','Épaisseur de paroi','Wall thickness',3,.5,40,.1],
  ['length','Longueur','Length',55,3,400,.1]]},
 {id:'elbow',fr:'Coude de conduit',en:'Duct elbow',fields:[
  ['diameter','Diamètre extérieur','Outside diameter',60,2,250,.1],
  ['wall','Épaisseur de paroi','Wall thickness',3,.5,30,.1],
  ['bendRadius','Rayon du coude (axe)','Bend centre radius',75,5,250,.1],
  ['bendAngle','Angle de courbure (°)','Bend angle (°)',90,15,180,1]]},
 {id:'sleeve',fr:'Bague / douille',en:'Bushing / sleeve',fields:[
  ['diameter','Diamètre extérieur','Outside diameter',28,2,200,.1],
  ['bore','Alésage intérieur','Inside bore',12,1,190,.1],
  ['length','Longueur','Length',18,1,200,.1]]},
 {id:'gear',fr:'Engrenage droit (simplifié)',en:'Spur gear (approximate)',fields:[
  ['teeth','Nombre de dents','Number of teeth',26,8,120,1],
  ['module','Module (mm)','Module (mm)',2,.5,8,.1],
  ['bore','Diamètre d’alésage','Bore diameter',8,1,100,.1],
  ['thickness','Épaisseur','Thickness',8,1,80,.1]]},
 {id:'screw',fr:'Vis à tête hexagonale',en:'Hex-head screw',fields:[
  ['diameter','Diamètre nominal','Nominal diameter',8,2,30,.1],
  ['pitch','Pas du filetage','Thread pitch',1.25,.5,6,.05],
  ['length','Longueur sous tête','Length under head',30,4,120,.1],
  ['headWidth','Tête : largeur sur plats','Head across flats',13,3,60,.1],
  ['headHeight','Hauteur de tête','Head height',5,2,30,.1]]}
];

export function defaultParams(kind) {
 const config=generatorKinds.find(x=>x.id===kind);
 if(!config)throw new Error('Unknown generator');
 return Object.fromEntries(config.fields.map(f=>[f[0],f[3]]));
}
function validate(kind,p) {
 const cfg=generatorKinds.find(x=>x.id===kind);
 if(!cfg)throw Error('Unknown generator');
 for(const [name,, , ,min,max] of cfg.fields){
  const value=Number(p[name]);
  if(!Number.isFinite(value)||value<min||value>max)throw Error('Vérifie les dimensions / Check dimensions');
 }
 if(kind==='gear' && p.teeth!==Math.round(p.teeth))throw Error('Nombre de dents entier / Whole number of teeth required');
 if(['pipe','elbow','adapter'].includes(kind) && p.wall*2 >= Math.min(p.diameter,p.diameter2||p.diameter))throw Error('Paroi trop épaisse / Wall too thick');
 if(kind==='sleeve' && p.bore >= p.diameter)throw Error('Alésage trop grand / Bore too large');
 if(kind==='elbow' && p.bendRadius<=p.diameter*.55)throw Error('Rayon trop court pour le diamètre / Bend radius is too small');
 if(kind==='gear' && p.bore/2 >= (p.teeth*p.module/2 - 1.25*p.module))throw Error('Alésage trop large / Bore too large');
 if(kind==='screw' && p.headWidth <= p.diameter*1.05)throw Error('La tête doit dépasser la tige / Head must be wider');
}
const vec=(T,x,y,z)=>new T.Vector3(x,y,z);
function buildTriangles(T,triangles){
 const g=new T.BufferGeometry();
 g.setAttribute('position',new T.Float32BufferAttribute(triangles,3));
 g.computeVertexNormals();g.computeBoundingBox();return g;
}
function makeBuilder(){
 const positions=[];
 const tri=(a,b,c)=>{positions.push(a.x,a.y,a.z,b.x,b.y,b.z,c.x,c.y,c.z);};
 const quad=(a,b,c,d)=>{tri(a,b,c);tri(a,c,d);};
 return {positions,tri,quad};
}
// Cross-sectional loft: outer skin, inner skin, annular caps, all watertight.
// Each ring uses centre, orthonormal u/v vectors and radii varying with angle.
function hollowLoft(T,rings,n=96){
 const {positions,tri,quad}=makeBuilder(), outer=[],inner=[];
 for(const ring of rings){
  const o=[],i=[];
  for(let j=0;j<=n;j++){
   const theta=j*2*Math.PI/n,cos=Math.cos(theta),sin=Math.sin(theta);
   const radial=ring.u.clone().multiplyScalar(cos).addScaledVector(ring.v,sin);
   o.push(ring.center.clone().addScaledVector(radial,ring.outer(theta)));
   i.push(ring.center.clone().addScaledVector(radial,ring.inner(theta)));
  }
  outer.push(o);inner.push(i);
 }
 for(let k=0;k<rings.length-1;k++)for(let j=0;j<n;j++){
  // outer orientation points outwards, inner towards the hollow bore
  quad(outer[k][j],outer[k][j+1],outer[k+1][j+1],outer[k+1][j]);
  quad(inner[k][j],inner[k+1][j],inner[k+1][j+1],inner[k][j+1]);
 }
 const bottom=rings.length-1;
 for(let j=0;j<n;j++){
  quad(outer[0][j],inner[0][j],inner[0][j+1],outer[0][j+1]);
  quad(outer[bottom][j],outer[bottom][j+1],inner[bottom][j+1],inner[bottom][j]);
 }
 return buildTriangles(T,positions);
}
function solidLoft(T,rings,n=72){
 const {positions,tri,quad}=makeBuilder(), sections=[];
 for(const ring of rings){
  const vertices=[];
  for(let j=0;j<=n;j++){
   const theta=j*2*Math.PI/n,radius=ring.radius(theta);
   vertices.push(vec(T,radius*Math.cos(theta),radius*Math.sin(theta),ring.z));
  }
  sections.push(vertices);
 }
 for(let k=0;k<rings.length-1;k++)for(let j=0;j<n;j++){
  quad(sections[k][j],sections[k][j+1],sections[k+1][j+1],sections[k+1][j]);
 }
 const start=vec(T,0,0,rings[0].z),end=vec(T,0,0,rings[rings.length-1].z);
 for(let j=0;j<n;j++){
  tri(start,sections[0][j+1],sections[0][j]);
  tri(end,sections[sections.length-1][j],sections[sections.length-1][j+1]);
 }
 return buildTriangles(T,positions);
}
const planarRings=(T,defs)=>defs.map(({z,outer,inner})=>({
 center:vec(T,0,0,z),u:vec(T,1,0,0),v:vec(T,0,1,0),
 outer:typeof outer==='function'?outer:()=>outer,
 inner:typeof inner==='function'?inner:()=>inner
}));
function gearRadius(theta,p){
 const root=p.module*(p.teeth/2-1.25),tip=p.module*(p.teeth/2+1);
 // Visual trapezoidal spur teeth. Not an involute or a validated gear standard.
 const phase=((theta*p.teeth/(2*Math.PI)+.5)%1+1)%1-.5;
 const d=Math.abs(phase);
 const proportion=d<=.15?1:d>=.4?0:(.4-d)/.25;
 return root+(tip-root)*proportion;
}
function threadRadius(theta,z,p){
 // Single-start approximation with eased root/crest. Pitch drives helix advance.
 const phase=((theta/(2*Math.PI)-z/p.pitch)%1+1)%1;
 const d=Math.min(phase,1-phase);
 const crest=d<.12?1:d>.42?0:(.42-d)/.30;
 const depth=Math.min(.6134*p.pitch,p.diameter*.16);
 return p.diameter/2-depth*(1-crest);
}
function hexRadius(theta,flat){
 const a=Math.PI/6,period=Math.PI/3;
 const delta=(((theta+a)%period)+period)%period-a;
 return flat/2/Math.cos(delta);
}
export function generateGeometry(T,kind,raw){
 const p=Object.fromEntries(Object.entries(raw).map(([k,v])=>[k,Number(v)]));
 validate(kind,p);
 const d=p.diameter||0;
 if(kind==='pipe')return hollowLoft(T,planarRings(T,[
  {z:0,outer:d/2,inner:d/2-p.wall},
  {z:p.length,outer:d/2,inner:d/2-p.wall}
 ]));
 if(kind==='sleeve')return hollowLoft(T,planarRings(T,[
  {z:0,outer:d/2,inner:p.bore/2},
  {z:p.length,outer:d/2,inner:p.bore/2}
 ]));
 if(kind==='adapter'){
  const segments=32,defs=[];
  for(let j=0;j<=segments;j++){
   const z=p.length*j/segments;
   const outside=(p.diameter+(p.diameter2-p.diameter)*j/segments)/2;
   defs.push({z,outer:outside,inner:outside-p.wall});
  }
  return hollowLoft(T,planarRings(T,defs));
 }
 if(kind==='elbow'){
  const steps=Math.max(28,Math.ceil(p.bendAngle/3)),rings=[],r=p.bendRadius;
  for(let j=0;j<=steps;j++){
   const angle=p.bendAngle*Math.PI/180*j/steps;
   rings.push({center:vec(T,r*(1-Math.cos(angle)),0,r*Math.sin(angle)),
    u:vec(T,Math.cos(angle),0,-Math.sin(angle)),v:vec(T,0,1,0),
    outer:()=>d/2,inner:()=>d/2-p.wall});
  }
  return hollowLoft(T,rings,80);
 }
 if(kind==='gear'){
  const r=theta=>gearRadius(theta,p);
  const rings=planarRings(T,[
   {z:0,outer:r,inner:p.bore/2},
   {z:p.thickness,outer:r,inner:p.bore/2}
  ]);
  return hollowLoft(T,rings,Math.max(96,p.teeth*12));
 }
 if(kind==='screw'){
  const steps=Math.min(600,Math.max(36,Math.ceil(p.length/p.pitch*8)));
  const rings=[];
  for(let j=0;j<=steps;j++){
   const z=p.length*j/steps;
   rings.push({z,radius:(theta)=>threadRadius(theta,z,p)});
  }
  // Underside of the hex head (flat annular shoulder), then the hex itself.
  rings.push({z:p.length,radius:theta=>hexRadius(theta,p.headWidth)});
  rings.push({z:p.length+p.headHeight,radius:theta=>hexRadius(theta,p.headWidth)});
  return solidLoft(T,rings,72);
 }
 throw Error('Unknown generator');
}
