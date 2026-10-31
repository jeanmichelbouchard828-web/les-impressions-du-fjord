// Les Impressions du Fjord — image, audio, text and true QR relief generators.
// Photos are 2.5D heightmaps, NOT facial-depth reconstruction or a 3D scan.
import {makeHeightField} from './fjord_generator_extensions.js';
const F=(id,fr,en,v,min,max,step=.1,unit='mm')=>[id,fr,en,v,min,max,step,unit];
export const artGeneratorKinds=[
 {id:'lithophane',fr:'Lithophanie (image)',en:'Lithophane (image)',needs:'image',
  fields:[F('width','Largeur','Width',110,35,220),F('height','Hauteur relief','Height',90,35,220),F('thickness','Épaisseur maximale','Max thickness',3.5,2,8)]},
 {id:'image_relief',fr:'Image en bas-relief',en:'Image bas-relief',needs:'image',
  fields:[F('width','Largeur','Width',105,30,220),F('height','Hauteur image','Image height',80,30,220),F('thickness','Relief','Relief depth',6,1.5,22)]},
 {id:'braille',fr:'Plaque Braille',en:'Braille plate',
  fields:[F('width','Largeur du support','Plate width',125,40,220),F('thickness','Épaisseur','Thickness',3,2,12),
   F('diameter','Diamètre des points','Dot diameter',1.5,1.1,3.2),
   F('text','Texte Braille','Braille text','FJORD',0,60,1,'text')]},
 {id:'waveform',fr:'Onde audio en relief',en:'Audio waveform relief',needs:'audio',
  fields:[F('width','Longueur','Length',145,40,220),F('height','Largeur','Width',38,16,95),F('thickness','Hauteur de la vague','Wave height',8,2,25)]},
 {id:'portrait_relief',fr:'Portrait en relief (caméra, bêta)',en:'Photo-relief portrait (camera, beta)',needs:'image',
  fields:[F('width','Largeur','Width',100,35,190),F('height','Hauteur','Height',125,40,210),F('thickness','Profondeur du relief','Relief depth',6,2,18)]},
 {id:'qrcode',fr:'QR code imprimable',en:'Printable QR code',
  fields:[F('width','Largeur','Width',85,35,190),F('thickness','Relief des carrés','Square height',1.8,.8,4),
   F('text','Lien ou texte','URL or text','https://example.ca',0,140,1,'text')]}
];
const combine=(T,parts)=>{
 const arr=[],point=new T.Vector3();
 for(const mesh of parts){
  const geometry=mesh.geometry,position=geometry.getAttribute('position'),index=geometry.getIndex();
  mesh.updateMatrix();
  for(let i=0;i<(index?index.count:position.count);i++){
   point.fromBufferAttribute(position,index?index.getX(i):i).applyMatrix4(mesh.matrix);
   arr.push(point.x,point.y,point.z);
  }
  geometry.dispose();
 }
 if(arr.length>1800000)throw Error('Géométrie trop lourde.');
 const out=new T.BufferGeometry();
 out.setAttribute('position',new T.Float32BufferAttribute(arr,3));
 out.computeVertexNormals();out.computeBoundingBox();return out;
};
const cube=(T,w,d,h,x,y,z)=>{
 const mesh=new T.Mesh(new T.BoxGeometry(w,d,h));
 mesh.position.set(x,y,z+h/2);return mesh;
};
function imageHeightmap(T,p,assets,invert){
 const image=assets.image;
 if(!image||!image.values||!image.width||!image.height)
  throw Error('Choisis une image JPG/PNG ou capture une photo pour activer ce générateur.');
 const nx=Math.max(12,Math.min(90,image.width)),ny=Math.max(12,Math.min(90,image.height));
 const pixel=(x,y)=>{
  const i=Math.min(image.width-1,Math.round(x*(image.width-1)));
  const j=Math.min(image.height-1,Math.round((1-y)*(image.height-1)));
  return image.values[j*image.width+i];
 };
 const min=invert?.75:1.4;
 return makeHeightField(T,p.width,p.height,nx,ny,(x,y)=>{
  const light=pixel(x,y);
  return min+(p.thickness-min)*(invert?1-light:light);
 });
}
function braille(T,p){
 const value=String(p.text||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().slice(0,60);
 if(!value.trim())throw Error('Entre du texte pour le Braille.');
 const dots={a:1,b:3,c:9,d:25,e:17,f:11,g:27,h:19,i:10,j:26,
 k:5,l:7,m:13,n:29,o:21,p:15,q:31,r:23,s:14,t:30,
 u:37,v:39,w:58,x:45,y:61,z:53,' ':0};
 const cols=22,rowcount=Math.ceil(value.length/cols);
 const spacing=p.diameter*1.6,cellW=spacing*3.6,cellH=spacing*5;
 const plateW=Math.max(p.width,cols>value.length?value.length*cellW+10:cols*cellW+10);
 const plateH=Math.max(22,rowcount*cellH+10);
 if(plateW>256||plateH>256)throw Error('Texte trop long pour le plateau X2D. Réduis le texte ou la taille des points.');
 const dots3d=[cube(T,plateW,plateH,p.thickness,0,0,0)];
 for(let n=0;n<value.length;n++){
  const mask=dots[value[n]]??0;
  const x=(n%cols)*cellW-plateW/2+cellW*.8;
  const y=plateH/2-(Math.floor(n/cols)+1)*cellH+cellH*.7;
  for(let k=0;k<6;k++)if(mask&(1<<k)){
   const cx=x+(k>=3?spacing:0),cy=y-(k%3)*spacing;
   const mesh=new T.Mesh(new T.SphereGeometry(p.diameter/2,12,8));
   mesh.position.set(cx,cy,p.thickness+p.diameter*.22);
   dots3d.push(mesh);
  }
 }
 return combine(T,dots3d);
}
function soundwave(T,p,assets){
 const values=assets.audio;
 if(!values||!values.length)throw Error('Choisis un fichier audio pour générer une onde vocale réelle.');
 const bins=Math.min(128,values.length);
 // Raised solid ribbon: thickness + amplitude along Z.
 return makeHeightField(T,p.width,p.height,bins,10,(u,v)=>{
  const k=Math.min(values.length-1,Math.floor(u*(values.length-1)));
  const amplitude=Math.max(0,Math.min(1,values[k]));
  const taper=Math.max(0,1-Math.pow(Math.abs(v*2-1),1.2));
  return 1.5 + p.thickness*amplitude*taper;
 });
}
function printableQr(T,p){
 const value=String(p.text||'').trim();
 if(!value || value.length>140)throw Error('Saisis un lien ou un texte de 1 à 140 caractères.');
 const factory=globalThis.qrcode;
 if(typeof factory!=='function')throw Error('Bibliothèque QR indisponible : vérifie ta connexion et réessaie.');
 const qr=factory(0,'M');
 qr.addData(value);
 qr.make();
 const cells=qr.getModuleCount();
 const size=cells+8, pitch=p.width/size;
 if(pitch<.9)throw Error('QR trop dense pour cette largeur. Augmente la taille de la plaque.');
 const geom=[cube(T,p.width,p.width,1.8,0,0,0)];
 // Quiet zone: 4 white modules on each side, do not put a frame inside it.
 for(let j=0;j<cells;j++)for(let i=0;i<cells;i++){
  if(!qr.isDark(j,i))continue;
  const x=(i+4+.5-size/2)*pitch,y=(size/2-j-4-.5)*pitch;
  geom.push(cube(T,pitch,pitch,p.thickness,x,y,1.8));
 }
 return combine(T,geom);
}
export function generateArtGeometry(T,kind,p,assets){
 const cfg=artGeneratorKinds.find(c=>c.id===kind);
 if(!cfg)throw Error('Générateur artistique inconnu.');
 for(const [id,,,initial,min,max,step,unit] of cfg.fields){
  if(unit==='text')continue;
  const v=Number(p[id]);
  if(!Number.isFinite(v)||v<min||v>max)throw Error('Valeur invalide : '+id);
 }
 if(kind==='lithophane')return imageHeightmap(T,p,assets,true);
 if(kind==='image_relief'||kind==='portrait_relief')return imageHeightmap(T,p,assets,false);
 if(kind==='braille')return braille(T,p);
 if(kind==='waveform')return soundwave(T,p,assets);
 if(kind==='qrcode')return printableQr(T,p);
 throw Error('Ce générateur artistique ne peut pas être créé.');
}
