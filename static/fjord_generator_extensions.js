// Les Impressions du Fjord — supplemental printable parametric generators.
// All dimensions are millimetres. Generated STL solids must be checked before mechanical use.
const F=(id,fr,en,v,min,max,step=.1,unit='mm')=>[id,fr,en,v,min,max,step,unit];
const G=(id,fr,en,fields)=>({id,fr,en,fields});
export const extraGeneratorKinds=[
 G('ramp','Rampe droite','Straight ramp',[F('length','Longueur','Length',65,8,240),F('width','Largeur','Width',40,8,200),F('height','Hauteur','Height',20,2,120)]),
 G('curved_ramp','Rampe courbe','Curved ramp',[F('length','Longueur','Length',75,15,220),F('width','Largeur','Width',45,8,200),F('height','Hauteur','Height',22,2,100),F('curve','Courbure','Curve',1.8,.4,4)]),
 G('hinge_pin','Charnière à axe','Pin hinge',[F('width','Longueur totale','Total length',55,15,180),F('length','Largeur feuille','Leaf width',24,8,80),F('thickness','Épaisseur','Thickness',3,1,12),F('diameter','Diamètre axe','Pin diameter',5,2,18)]),
 G('hinge_leaf','Charnière à feuilles','Leaf hinge',[F('width','Longueur','Length',60,12,180),F('length','Largeur feuille','Leaf width',24,8,90),F('thickness','Épaisseur','Thickness',3,1,15),F('diameter','Diamètre axe','Pin diameter',5,2,18)]),
 G('hinge_articulated','Charnière articulée','Articulated hinge',[F('width','Longueur','Length',65,18,160),F('length','Largeur des feuilles','Leaf width',28,10,80),F('thickness','Épaisseur','Thickness',3,1,10),F('diameter','Diamètre de l’axe','Pin diameter',5,2,14)]),
 G('bearing','Roulement à billes (maquette)','Ball bearing (model)',[F('diameter','Diamètre externe','Outside diameter',55,20,140),F('bore','Alésage','Bore diameter',24,5,100),F('thickness','Épaisseur','Thickness',12,4,35),F('teeth','Nombre de billes','Ball count',10,6,30,1,'')]),
 G('pivot','Pivot cylindrique','Cylindrical pivot',[F('diameter','Diamètre axe','Shaft diameter',15,4,70),F('length','Longueur axe','Shaft length',48,10,150),F('diameter2','Diamètre de bride','Flange diameter',35,10,120),F('thickness','Épaisseur bride','Flange thickness',5,2,25)]),
 G('tee','Connecteur en T','T connector',[F('diameter','Diamètre principal','Main diameter',48,10,120),F('diameter2','Diamètre branche','Branch diameter',35,8,100),F('length','Longueur totale','Total length',120,30,240),F('wall','Épaisseur paroi','Wall thickness',3,1,12)]),
 G('sculpture','Sculpture torsadée','Twisted sculpture',[F('diameter','Diamètre','Diameter',40,8,90),F('height','Hauteur','Height',85,15,180),F('turns','Tours','Twists',2,.25,7,.25,'')]),
 G('organic','Sculpture organique','Organic sculpture',[F('diameter','Largeur','Width',50,10,120),F('height','Hauteur','Height',75,10,200),F('waves','Ondulations','Ripples',5,2,14,1,'')]),
 G('voronoi','Structure ajourée organique','Open lattice sculpture',[F('diameter','Diamètre','Diameter',65,20,140),F('height','Hauteur','Height',85,20,200),F('thickness','Diamètre tiges','Strut diameter',2.8,1,10),F('teeth','Divisions','Divisions',10,5,20,1,'')]),
 G('pulley','Poulie à gorge','Groove pulley',[F('diameter','Diamètre externe','Outside diameter',55,12,130),F('bore','Alésage','Bore',12,3,70),F('thickness','Largeur','Width',18,6,55),F('groove','Profondeur gorge','Groove depth',4,1,14)]),
 G('nut','Écrou hexagonal','Hex nut',[F('diameter','Largeur sur plats','Across flats',17,6,75),F('bore','Trou central','Central bore',8,2,55),F('thickness','Épaisseur','Thickness',7,2,35)]),
 G('tap','Douille taraudée indicative','Threaded sleeve prototype',[F('diameter','Diamètre extérieur','Outside diameter',26,10,100),F('bore','Diamètre intérieur','Inner diameter',12,3,85),F('length','Longueur','Length',30,5,125),F('pitch','Pas nominal','Thread pitch',1.5,.6,5)]),
 G('washer','Rondelle','Washer',[F('diameter','Diamètre externe','Outside diameter',30,6,150),F('bore','Trou','Hole diameter',9,2,120),F('thickness','Épaisseur','Thickness',3,.8,20)]),
 G('torsion_spring','Ressort à torsion (2 pattes)','Torsion spring (2 legs)',[
  F('diameter','Diamètre moyen de l’enroulement','Mean coil diameter',30,8,115,.5),
  F('thickness','Diamètre du fil','Wire diameter',2.5,.8,10,.1),
  F('turns','Nombre de spires complètes','Full coil turns',5,2,12,1,''),
  F('pitch','Pas axial des spires','Axial coil pitch',2.9,1,16,.1),
  F('arm1','Longueur de la patte 1','First leg length',35,5,120,.5),
  F('arm2','Longueur de la patte 2','Second leg length',35,5,120,.5),
  F('opening','Angle entre les pattes (°)','Angle between legs (°)',90,0,180,5,'°'),
  F('hand','Sens (0=droite, 1=gauche)','Handedness (0=right, 1=left)',0,0,1,1,'')
 ]),
 G('spring','Ressort hélicoïdal','Coil spring',[F('diameter','Diamètre moyen','Mean diameter',28,8,90),F('thickness','Diamètre fil','Wire diameter',3,1,9),F('pitch','Espacement spires','Coil pitch',9,4,22),F('turns','Nombre de spires','Turns',6,2,15,1,'')]),
 G('turbine','Hélice / turbine','Propeller / turbine',[F('diameter','Diamètre hors tout','Outside diameter',100,30,220),F('bore','Alésage moyeu','Hub bore',8,3,35),F('thickness','Épaisseur pales','Blade thickness',4,2,12),F('teeth','Nombre de pales','Blade count',5,2,10,1,'')]),
 G('coupler','Raccord de tuyaux','Pipe coupling',[F('diameter','Diamètre extérieur','Outside diameter',45,10,135),F('bore','Alésage','Inside bore',33,6,120),F('length','Longueur','Length',48,10,140),F('thickness','Épaisseur collerette','Rim thickness',3,1,12)]),
 G('funnel','Entonnoir','Funnel',[F('diameter','Diamètre entonnoir','Bowl diameter',90,25,200),F('diameter2','Diamètre sortie','Outlet diameter',17,6,70),F('length','Hauteur','Height',70,20,160),F('wall','Épaisseur paroi','Wall thickness',2.3,1,8)]),
 G('grommet','Passe-câble','Cable grommet',[F('diameter','Diamètre collerette','Flange diameter',35,10,90),F('bore','Trou pour câble','Cable hole',12,3,60),F('length','Longueur','Length',18,5,60),F('thickness','Paroi','Wall',3,1,10)]),
 G('spoon','Cuillère doseuse','Measuring scoop',[F('diameter','Diamètre coupe','Cup diameter',36,15,90),F('length','Longueur poignée','Handle length',65,20,160),F('height','Profondeur','Depth',20,8,45),F('wall','Paroi','Wall',2.3,1,6)]),
 G('keychain','Porte-clés','Keychain tag',[F('width','Largeur','Width',56,18,140),F('length','Hauteur','Height',25,12,75),F('thickness','Épaisseur','Thickness',4,2,15),F('bore','Trou anneau','Ring hole',5,3,12)]),
 G('stamp','Tampon / emporte-pièce simple','Stamp / simple cutter',[F('width','Largeur','Width',55,12,140),F('length','Longueur','Length',40,12,140),F('height','Hauteur','Height',16,6,55),F('wall','Paroi','Wall',2,1,8)]),
 G('clamp','Bride de fixation','Mounting clamp',[F('diameter','Diamètre tube','Tube diameter',34,8,90),F('width','Largeur bride','Clamp width',18,7,60),F('thickness','Paroi','Wall',5,2,14),F('bore','Trous fixation','Screw holes',5,2,15)]),
 G('grill','Grille / résille','Lattice panel',[F('width','Largeur','Width',95,20,200),F('length','Longueur','Length',95,20,200),F('thickness','Épaisseur','Thickness',3,1,10),F('pitch','Espacement','Spacing',14,6,30)]),
 G('roller','Rouleau en relief','Embossed roller',[F('diameter','Diamètre','Diameter',35,12,90),F('length','Longueur','Length',75,20,180),F('bore','Trou axe','Axle hole',8,3,50),F('teeth','Reliefs','Raised ribs',12,4,36,1,'')]),
 G('pawn','Pion de jeu','Game pawn',[F('diameter','Diamètre socle','Base diameter',24,10,60),F('height','Hauteur','Height',40,15,100)]),
 G('clock','Cadran d’horloge','Clock dial',[F('diameter','Diamètre','Diameter',145,60,245),F('thickness','Épaisseur','Thickness',5,2,16),F('bore','Trou centre','Center hole',8,3,20)]),
 G('stand','Support universel','Universal holder',[F('width','Largeur base','Base width',80,25,170),F('length','Profondeur base','Base depth',60,25,140),F('height','Hauteur butée','Backstop height',40,15,130),F('thickness','Épaisseur','Thickness',5,2,14)]),
 G('box','Boîte et couvercle','Box and lid',[F('width','Largeur','Width',105,30,190),F('length','Profondeur','Depth',75,30,190),F('height','Hauteur','Height',50,15,150),F('wall','Paroi','Wall',3,1.5,9)]),
 G('mold','Moule ouvert','Open mold',[F('width','Largeur','Width',90,30,180),F('length','Profondeur','Depth',72,30,180),F('height','Hauteur','Height',25,10,80),F('wall','Paroi','Wall',4,2,12)]),
 G('corrugated','Surface ondulée','Corrugated panel',[F('width','Largeur','Width',90,25,200),F('length','Longueur','Length',120,25,200),F('height','Amplitude','Amplitude',8,1,25),F('thickness','Épaisseur','Thickness',3,1,9),F('waves','Nombre d’ondes','Wave count',7,2,22,1,'')]),
 G('tower','Tour miniature','Miniature tower',[F('diameter','Diamètre base','Base diameter',58,18,130),F('height','Hauteur','Height',145,30,235),F('teeth','Niveaux','Levels',5,2,12,1,'')]),
 G('city','Quartier 3D miniature','Miniature city block',[F('width','Largeur quartier','District width',160,60,240),F('length','Longueur quartier','District depth',160,60,240),F('height','Hauteur maximale','Maximum height',75,20,170),F('teeth','Bâtiments par rangée','Buildings per row',4,2,7,1,'')])
];
// Merge non-boolean printable solids; each primitive is itself closed.
// These are prototypes and may contain contacting/intersecting shells.
const join=(T,geoms)=>{
 const vertices=[],v=new T.Vector3();
 for(const g of geoms){
  if(!g)continue;
  const pos=g.getAttribute('position'),idx=g.getIndex();
  for(let i=0;i<(idx?idx.count:pos.count);i++){
   v.fromBufferAttribute(pos,idx?idx.getX(i):i);
   vertices.push(v.x,v.y,v.z);
  }
  g.dispose();
 }
 if(vertices.length>1800000)throw Error('Modèle trop détaillé pour le navigateur.');
 const out=new T.BufferGeometry();
 out.setAttribute('position',new T.Float32BufferAttribute(vertices,3));
 out.computeVertexNormals();out.computeBoundingBox();return out;
};
const box=(T,w,d,h,x=0,y=0,z=0)=>{const g=new T.BoxGeometry(w,d,h);g.translate(x,y,z+h/2);return g};
const cyl=(T,r,h,x=0,y=0,z=0,n=64)=>{const g=new T.CylinderGeometry(r,r,h,n);g.rotateX(Math.PI/2);g.translate(x,y,z+h/2);return g};
const ring=(T,outer,inner,height,z=0)=>{
 if(inner<=0)return cyl(T,outer,height,0,0,z);
 if(inner>=outer)throw Error('Diamètre intérieur trop grand.');
 const sh=new T.Shape();sh.absarc(0,0,outer,0,Math.PI*2,false);
 const hole=new T.Path();hole.absarc(0,0,inner,0,Math.PI*2,true);
 sh.holes.push(hole);
 const g=new T.ExtrudeGeometry(sh,{depth:height,bevelEnabled:false,curveSegments:60,steps:1});
 g.translate(0,0,z);return g;
};
const loft=(T,defs,sides=64,solid=false)=>{
 const tris=[],rings=[];
 for(const d of defs){
  let row=[];
  for(let i=0;i<=sides;i++){
   const angle=2*Math.PI*i/sides;
   const ro=typeof d.outer==='function'?d.outer(angle):d.outer;
   const ri=typeof d.inner==='function'?d.inner(angle):d.inner;
   row.push({a:[ro*Math.cos(angle),ro*Math.sin(angle),d.z],
     b:[ri*Math.cos(angle),ri*Math.sin(angle),d.z]});
  }
  rings.push(row);
 }
 const tri=(a,b,c)=>tris.push(...a,...b,...c);
 const quad=(a,b,c,d)=>{tri(a,b,c);tri(a,c,d)};
 for(let k=0;k<rings.length-1;k++)for(let i=0;i<sides;i++){
  const a=rings[k][i],b=rings[k][i+1],c=rings[k+1][i],d=rings[k+1][i+1];
  quad(a.a,b.a,d.a,c.a);
  if(!solid)quad(a.b,c.b,d.b,b.b);
 }
 for(let i=0;i<sides;i++){
  const a=rings[0][i],b=rings[0][i+1],c=rings.at(-1)[i],d=rings.at(-1)[i+1];
  if(solid){const axis=[0,0,rings[0][i].a[2]],axisEnd=[0,0,c.a[2]];
   tri(axis,b.a,a.a);tri(axisEnd,c.a,d.a);
  }else{quad(a.a,a.b,b.b,b.a);quad(c.a,d.a,d.b,c.b)}
 }
 const g=new T.BufferGeometry();
 g.setAttribute('position',new T.Float32BufferAttribute(tris,3));
 g.computeVertexNormals();g.computeBoundingBox();return g;
};
export const makeHeightField=(T,w,d,nx,ny,top,bottom=0)=>{
 const vertices=[],points=[];
 nx=Math.max(2,Math.min(130,Math.ceil(nx)));ny=Math.max(2,Math.min(130,Math.ceil(ny)));
 for(let j=0;j<=ny;j++){let row=[];for(let i=0;i<=nx;i++){
  const x=w*(i/nx-.5),y=d*(j/ny-.5),z=top(i/nx,j/ny);
  if(!Number.isFinite(z))throw Error('Surface invalide.');
  row.push([x,y,Math.max(bottom+.05,z)]);
 }points.push(row)}
 const tri=(a,b,c)=>vertices.push(...a,...b,...c);
 const quad=(a,b,c,d)=>{tri(a,b,c);tri(a,c,d)};
 for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
  const a=points[j][i],b=points[j][i+1],c=points[j+1][i],d=points[j+1][i+1];
  quad(a,b,d,c);quad([a[0],a[1],bottom],[c[0],c[1],bottom],[d[0],d[1],bottom],[b[0],b[1],bottom]);
 }
 for(let i=0;i<nx;i++){
  let a=points[0][i],b=points[0][i+1];quad([a[0],a[1],bottom],[b[0],b[1],bottom],b,a);
  a=points[ny][i];b=points[ny][i+1];quad(a,b,[b[0],b[1],bottom],[a[0],a[1],bottom]);
 }
 for(let j=0;j<ny;j++){
  let a=points[j][0],b=points[j+1][0];quad(b,a,[a[0],a[1],bottom],[b[0],b[1],bottom]);
  a=points[j][nx];b=points[j+1][nx];quad(a,b,[b[0],b[1],bottom],[a[0],a[1],bottom]);
 }
 return join(T,[new T.BufferGeometry().setAttribute('position',new T.Float32BufferAttribute(vertices,3))]);
};
const torus=(T,r,t,x=0,y=0,z=0)=>{
 const g=new T.TorusGeometry(r,t,10,50);g.translate(x,y,z);return g;
};
const tubePath=(T,points,radius,segments=90)=>{
 const curve=new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p)));
 return new T.TubeGeometry(curve,segments,radius,9,false);
};
const oval=(T,w,d,h)=>{
 const g=new T.SphereGeometry(1,40,24);g.scale(w/2,d/2,h/2);g.translate(0,0,h/2);return g;
};
const sideBox=(T,w,d,h,x,y,z)=>box(T,w,d,h,x,y,z);
export function generateExtraGeometry(T,kind,p){
 const g=[],pi=Math.PI;
 const add=(...v)=>g.push(...v);
 const r=p.diameter/2;
 const normal=(v,min,max)=>Math.max(min,Math.min(max,v));
 switch(kind){
 case 'ramp':return makeHeightField(T,p.length,p.width,55,9,(x)=>p.height*Math.pow(x,1),0);
 case 'curved_ramp':return makeHeightField(T,p.length,p.width,65,12,(x)=>p.height*Math.pow(x,p.curve),0);
 case 'hinge_pin':case 'hinge_leaf':case 'hinge_articulated':{
  const w=p.width,l=p.length,t=p.thickness,shaft=p.diameter/2;
  const count=kind==='hinge_articulated'?7:5;
  add(box(T,l-2*shaft,w,t,-(l/2+shaft),0),box(T,l-2*shaft,w,t,l/2+shaft,0));
  for(let i=0;i<count;i++){
   const z=i*w/count;
   const left=i%2===0;
   const barrel=ring(T,shaft+t*.55,shaft+.28,w/count-.4,z+.2);
   barrel.rotateX(pi/2);barrel.translate(0,0,shaft+t*.55);
   // Barrel's axis runs along Y, wings remain on print bed.
   barrel.translate(left?-shaft:shaft,0,0);add(barrel);
  }
  add(cyl(T,shaft-.5,w*.92,0,0,t));
  return join(T,g);
 }
 case 'bearing':{
  if(p.bore+4>=p.diameter)throw Error('Roulement : diamètre extérieur insuffisant.');
  const race=(p.diameter-p.bore)/4;
  add(ring(T,p.diameter/2,race/2+p.bore/2,p.thickness));
  add(ring(T,p.bore/2+race*.7,p.bore/2,p.thickness));
  const orbit=p.bore/2+race*1.1;
  for(let i=0;i<p.teeth;i++){
   const a=2*pi*i/p.teeth;
   const b=new T.SphereGeometry(race*.32,14,10);
   b.translate(orbit*Math.cos(a),orbit*Math.sin(a),p.thickness/2);add(b);
  }
  return join(T,g);
 }
 case 'pivot':
  if(p.diameter2<=p.diameter)throw Error('La bride doit dépasser l’axe.');
  return join(T,[cyl(T,p.diameter2/2,p.thickness),cyl(T,r,p.length,0,0,p.thickness)]);
 case 'tee':{
  if(p.wall*2>=Math.min(p.diameter,p.diameter2))throw Error('Paroi trop épaisse.');
  const stem=ring(T,r,r-p.wall,p.length);
  const arm=ring(T,p.diameter2/2,p.diameter2/2-p.wall,p.length*.60);
  arm.rotateY(pi/2);arm.translate(-p.length*.3,0,p.length*.5);
  return join(T,[stem,arm]);
 }
 case 'sculpture':
  return loft(T,Array.from({length:95},(_,i)=>{
   const z=p.height*i/94;
   const phase=2*pi*p.turns*i/94;
   return {z,outer:a=>p.diameter/2*(.7+.18*Math.sin(5*(a+phase))+.12*Math.sin(3*(a-phase))),inner:0};
  }),80,true);
 case 'organic':
  return loft(T,Array.from({length:91},(_,i)=>{
   const x=i/90,z=x*p.height;
   const envelope=Math.max(.06,Math.sin(pi*x)*.92);
   return {z,outer:a=>p.diameter*.5*envelope*(1+.16*Math.sin(a*p.waves+x*18)+.09*Math.cos(a*3-x*14)),inner:0};
  }),80,true);
 case 'voronoi':{
  // Printable open organic lattice: diagonal lattice with closed struts.
  const rows=Math.max(4,Math.min(14,p.teeth)),n=Math.max(8,Math.min(24,p.teeth));
  const radius=p.diameter/2;
  const pos=(i,j)=>[radius*Math.cos(2*pi*i/n),radius*Math.sin(2*pi*i/n),p.height*j/rows];
  const strut=(a,b)=>{
   const A=new T.Vector3(...a),B=new T.Vector3(...b),dir=B.clone().sub(A);
   const geom=new T.CylinderGeometry(p.thickness/2,p.thickness/2,dir.length(),6);
   geom.applyQuaternion(new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0),dir.normalize()));
   geom.translate(...A.add(B).multiplyScalar(.5).toArray());return geom;
  };
  for(let j=0;j<rows;j++)for(let i=0;i<n;i++){
   add(strut(pos(i,j),pos(i+1,j+1)),strut(pos(i+1,j),pos(i,j+1)));
  }
  for(let j of [0,rows])for(let i=0;i<n;i++)add(strut(pos(i,j),pos(i+1,j)));
  return join(T,g);
 }
 case 'pulley':
  if(p.bore>=p.diameter-2*p.groove)throw Error('La gorge traverse l’alésage.');
  return loft(T,[{z:0,outer:r,inner:p.bore/2},
   {z:p.thickness*.26,outer:r,inner:p.bore/2},
   {z:p.thickness*.5,outer:r-p.groove,inner:p.bore/2},
   {z:p.thickness*.74,outer:r,inner:p.bore/2},
   {z:p.thickness,outer:r,inner:p.bore/2}]);
 case 'nut':{
  if(p.bore>=p.diameter*.8)throw Error('Trou trop large pour l’écrou.');
  const circ=theta=>p.diameter/2/Math.cos((((theta+pi/6)%(pi/3))+(pi/3))%(pi/3)-pi/6);
  return loft(T,[{z:0,outer:circ,inner:p.bore/2},{z:p.thickness,outer:circ,inner:p.bore/2}],72);
 }
 case 'tap':{
  if(p.bore>=p.diameter-3)throw Error('Paroi trop mince.');
  // Pilot diameter prototype; not a standardized or dimensionally verified tap.
  const steps=Math.max(24,Math.ceil(p.length/p.pitch)*4);
  return loft(T,Array.from({length:steps+1},(_,i)=>{
   const z=p.length*i/steps;
   return {z,outer:r,inner:angle=>p.bore/2+.2*p.pitch*Math.sin(angle-z*2*pi/p.pitch)};
  }),56);
 }
 case 'washer':
  return ring(T,r,p.bore/2,p.thickness);
 case 'torsion_spring':{
  // Geometry in mm. A single continuously swept and end-capped round wire,
  // with two tangent arms. The fractional winding phase enforces the specified
  // arm-to-arm angle; the integer count is the number of FULL spires.
  const wire=p.thickness,r=p.diameter/2,hand=p.hand===1?-1:1;
  if(r<=wire*1.1)throw Error('Le diamètre moyen doit dépasser 2,2 × le diamètre du fil.');
  if(p.pitch<wire+.08)throw Error('Le pas des spires doit être supérieur au diamètre du fil (jeu minimal 0,08 mm).');
  if(!Number.isInteger(p.turns)||!Number.isInteger(p.hand))
   throw Error('Nombre de spires et sens d’enroulement invalides.');
  const rotations=p.turns+(180-p.opening)/360;
  const pts=[],center0=new T.Vector3(r,0,wire/2);
  const extend0=new T.Vector3(0,-hand,0);
  const legSteps=Math.max(6,Math.ceil(p.arm1/3));
  for(let i=0;i<legSteps;i++){
   const d=p.arm1*(1-i/legSteps);
   pts.push(center0.clone().addScaledVector(extend0,d));
  }
  const coilSamples=Math.max(80,Math.ceil(rotations*36));
  for(let i=0;i<=coilSamples;i++){
   const u=i/coilSamples,angle=hand*2*pi*rotations*u;
   pts.push(new T.Vector3(r*Math.cos(angle),r*Math.sin(angle),wire/2+p.pitch*rotations*u));
  }
  const endAngle=hand*2*pi*rotations;
  const end=new T.Vector3(r*Math.cos(endAngle),r*Math.sin(endAngle),wire/2+p.pitch*rotations);
  const extend1=new T.Vector3(-hand*Math.sin(endAngle),hand*Math.cos(endAngle),0);
  const endSteps=Math.max(6,Math.ceil(p.arm2/3));
  for(let i=1;i<=endSteps;i++)pts.push(end.clone().addScaledVector(extend1,p.arm2*i/endSteps));
  const path=new T.CatmullRomCurve3(pts,false,'centripetal');
  const axialSteps=Math.max(120,Math.min(650,Math.ceil(rotations*55+(p.arm1+p.arm2)/2)));
  const sides=12;
  const tube=new T.TubeGeometry(path,axialSteps,wire/2,sides,false);
  const pos=tube.getAttribute('position'),indices=tube.getIndex();
  const triangles=[];
  for(let i=0;i<indices.count;i++){
   const j=indices.getX(i);
   triangles.push(pos.getX(j),pos.getY(j),pos.getZ(j));
  }
  const caps=(ring,center,outward)=>{
   const vec=new T.Vector3(),a=new T.Vector3(),b=new T.Vector3();
   for(let j=0;j<sides;j++){
    a.fromBufferAttribute(pos,ring*(sides+1)+j);
    b.fromBufferAttribute(pos,ring*(sides+1)+j+1);
    const normal=vec.copy(a).sub(center).cross(new T.Vector3().copy(b).sub(center));
    const v=normal.dot(outward)>=0?[a,b]:[b,a];
    triangles.push(center.x,center.y,center.z,
       v[0].x,v[0].y,v[0].z,v[1].x,v[1].y,v[1].z);
   }
  };
  caps(0,path.getPointAt(0),path.getTangentAt(0).negate());
  caps(axialSteps,path.getPointAt(1),path.getTangentAt(1));
  tube.dispose();
  const geometry=new T.BufferGeometry();
  geometry.setAttribute('position',new T.Float32BufferAttribute(triangles,3));
  geometry.computeVertexNormals();geometry.computeBoundingBox();
  return geometry;
 }
 case 'spring':{
  if(p.pitch<=p.thickness*1.05)throw Error('Espacement des spires trop petit.');
  const pts=[],turn=p.turns,segments=turn*25;
  for(let i=0;i<=segments;i++){
   const t=i/segments,angle=2*pi*turn*t;
   pts.push([r*Math.cos(angle),r*Math.sin(angle),p.pitch*turn*t+p.thickness/2]);
  }
  return tubePath(T,pts,p.thickness/2,segments);
 }
 case 'turbine':{
  if(p.bore>=p.diameter*.2)throw Error('Trou trop large pour le moyeu.');
  add(ring(T,r*.20,p.bore/2,p.thickness*2));
  for(let i=0;i<p.teeth;i++){
   const blade=new T.BoxGeometry(r*.85,r*.23,p.thickness);
   blade.rotateY(.25);blade.translate(r*.48,0,p.thickness*1.2);
   blade.rotateZ(2*pi*i/p.teeth);add(blade);
  }
  return join(T,g);
 }
 case 'coupler':
  if(p.bore>=p.diameter-3)throw Error('Paroi trop mince.');
  return loft(T,[{z:0,outer:r,inner:p.bore/2},
   {z:p.thickness,outer:r+p.thickness*.5,inner:p.bore/2},
   {z:p.length-p.thickness,outer:r+p.thickness*.5,inner:p.bore/2},
   {z:p.length,outer:r,inner:p.bore/2}]);
 case 'funnel':{
  if(p.diameter2>=p.diameter || p.wall*2>=p.diameter2)throw Error('Diamètres incompatibles.');
  return loft(T,[{z:0,outer:p.diameter2/2,inner:p.diameter2/2-p.wall},
   {z:p.length*.25,outer:p.diameter2/2,inner:p.diameter2/2-p.wall},
   {z:p.length,outer:r,inner:r-p.wall}],80);
 }
 case 'grommet':
  if(p.bore>=p.diameter-3 || p.thickness*2>=p.diameter-p.bore)throw Error('Paroi trop fine.');
  return loft(T,[{z:0,outer:r,inner:p.bore/2},
   {z:p.length*.25,outer:r-p.thickness,inner:p.bore/2},
   {z:p.length*.82,outer:r-p.thickness,inner:p.bore/2},
   {z:p.length,outer:r,inner:p.bore/2}]);
 case 'spoon':{
  if(p.wall*2>=p.diameter)throw Error('Paroi trop épaisse.');
  const cup=loft(T,[{z:0,outer:1.0,inner:0},
    {z:p.wall,outer:r,inner:r-p.wall},
    {z:p.height,outer:r,inner:r-p.wall}],64);
  const handle=box(T,p.length,p.wall*2,p.wall,0,r+p.length/2-8,p.height-p.wall);
  return join(T,[cup,handle]);
 }
 case 'keychain':{
  if(p.bore>p.length*.5)throw Error('Trou trop gros.');
  const sh=new T.Shape();
  sh.absarc(0,0,Math.min(p.width,p.length)*.40,0,2*pi,false);
  const plate=new T.Shape();
  plate.moveTo(-p.width/2,-p.length/2);plate.lineTo(p.width/2,-p.length/2);
  plate.lineTo(p.width/2,p.length/2);plate.lineTo(-p.width/2,p.length/2);plate.closePath();
  const hole=new T.Path();hole.absarc(-p.width/2+p.bore*1.5,0,p.bore/2,0,2*pi,true);
  plate.holes.push(hole);
  return new T.ExtrudeGeometry(plate,{depth:p.thickness,bevelEnabled:false});
 }
 case 'stamp':{
  if(p.wall*2>=Math.min(p.width,p.length))throw Error('Paroi trop épaisse.');
  const w=p.width,l=p.length,t=p.wall;
  return join(T,[box(T,w,l,t),box(T,t,l,p.height-t,-w/2+t/2,0,t),box(T,t,l,p.height-t,w/2-t/2,0,t),
   box(T,w-2*t,t,p.height-t,0,-l/2+t/2,t),box(T,w-2*t,t,p.height-t,0,l/2-t/2,t)]);
 }
 case 'clamp':{
  if(p.thickness>=p.diameter*.6)throw Error('Paroi trop épaisse.');
  const outer=r+p.thickness;
  const rform=ring(T,outer,r,p.width);
  const bolts=[-1,1].map(sign=>{
   const ear=box(T,p.thickness*2,p.thickness*3,p.width,sign*(outer+p.thickness*.7),0,0);
   return ear;
  });
  return join(T,[rform,...bolts]);
 }
 case 'grill':{
  const thickness=p.thickness,nx=Math.ceil(p.width/p.pitch),ny=Math.ceil(p.length/p.pitch);
  add(box(T,p.width,thickness,thickness,0,-p.length/2+thickness/2),
      box(T,p.width,thickness,thickness,0,p.length/2-thickness/2),
      box(T,thickness,p.length,thickness,-p.width/2+thickness/2,0),
      box(T,thickness,p.length,thickness,p.width/2-thickness/2,0));
  for(let i=1;i<nx;i++)add(box(T,thickness,p.length,thickness,p.width*(i/nx-.5),0));
  for(let j=1;j<ny;j++)add(box(T,p.width,thickness,thickness,0,p.length*(j/ny-.5)));
  return join(T,g);
 }
 case 'roller':{
  if(p.bore>=p.diameter-4)throw Error('Paroi trop mince.');
  const outer=a=>r+1.3*Math.max(0,Math.cos(a*p.teeth));
  return loft(T,[{z:0,outer,inner:p.bore/2},{z:p.length,outer,inner:p.bore/2}],Math.max(96,p.teeth*10));
 }
 case 'pawn':
  return loft(T,[{z:0,outer:r,inner:0},{z:p.height*.12,outer:r,inner:0},
   {z:p.height*.17,outer:r*.55,inner:0},{z:p.height*.70,outer:r*.35,inner:0},
   {z:p.height*.78,outer:r*.56,inner:0},{z:p.height*.90,outer:r*.51,inner:0},
   {z:p.height,outer:r*.12,inner:0}],72,true);
 case 'clock':{
  if(p.bore>=p.diameter*.3)throw Error('Trou central trop grand.');
  add(ring(T,r,p.bore/2,p.thickness));
  for(let i=0;i<12;i++){const a=2*pi*i/12;const tick=box(T,p.diameter*.035,p.diameter*.09,1.2,0,r*.83,p.thickness);
   tick.rotateZ(-a);add(tick);}
  return join(T,g);
 }
 case 'stand':
  return join(T,[box(T,p.width,p.length,p.thickness),
   box(T,p.width,p.thickness,p.height,0,p.length/2-p.thickness/2,0),
   box(T,p.width,p.thickness,p.thickness*2,0,-p.length/2+p.thickness/2,0)]);
 case 'box':{
  const w=p.width,l=p.length,h=p.height,t=p.wall;
  if(t*3>=Math.min(w,l,h))throw Error('Paroi trop épaisse.');
  const offset=-(w+8)/2;
  add(box(T,w,l,t,offset),box(T,t,l,h-t,offset-w/2+t/2,0,t),box(T,t,l,h-t,offset+w/2-t/2,0,t),
    box(T,w-2*t,t,h-t,offset,-l/2+t/2,t),box(T,w-2*t,t,h-t,offset,l/2-t/2,t));
  add(box(T,w,l,t,(w+8)/2,0,0)); // Separate lid beside box, both centred on the plate.
  return join(T,g);
 }
 case 'mold':{
  const w=p.width,l=p.length,h=p.height,t=p.wall;
  if(t*3>=Math.min(w,l))throw Error('Paroi trop épaisse.');
  return join(T,[box(T,w,l,t),box(T,t,l,h-t,-w/2+t/2,0,t),box(T,t,l,h-t,w/2-t/2,0,t),
   box(T,w-2*t,t,h-t,0,-l/2+t/2,t),box(T,w-2*t,t,h-t,0,l/2-t/2,t)]);
 }
 case 'corrugated':
  return makeHeightField(T,p.width,p.length,90,50,(x,y)=>p.thickness+p.height*(1+Math.sin(2*pi*x*p.waves))/2,0);
 case 'tower':{
  add(cyl(T,r,p.height));
  for(let i=0;i<=p.teeth;i++)add(cyl(T,r*(i%p.teeth===0?1.12:1.06),2,0,0,p.height*i/p.teeth));
  add(cyl(T,r*1.15,5));
  return join(T,g);
 }
 case 'city':{
  const n=p.teeth,cellx=p.width/n,celly=p.length/n;
  add(box(T,p.width,p.length,3));
  for(let i=0;i<n;i++)for(let j=0;j<n;j++){
   const seed=((i*17+j*29+i*j*7)%13)/12;
   const h=p.height*(.25+.7*seed);
   add(box(T,cellx*.65,celly*.66,h,(i+.5-n/2)*cellx,(j+.5-n/2)*celly,3));
  }
  return join(T,g);
 }
 default:throw Error('Générateur non pris en charge : '+kind);
 }
}
