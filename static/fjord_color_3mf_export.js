/* Standard 3MF surface-color export.
   Produces a standards-based 3MF with material color groups. This is NOT a
   Bambu Studio native project or a sliced print; slicers may remap colors. */
const encoder=new TextEncoder();
const crcTable=new Uint32Array(256);
for(let n=0;n<256;n++){
 let c=n;
 for(let k=0;k<8;k++)c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1);
 crcTable[n]=c>>>0;
}
function crc32(data){
 let c=0xFFFFFFFF;
 for(const byte of data)c=crcTable[(c^byte)&255]^(c>>>8);
 return (c^0xFFFFFFFF)>>>0;
}
function zipStore(entries){
 const files=[],directory=[];
 let offset=0;
 for(const [name,contents] of entries){
  const fileName=encoder.encode(name),data=encoder.encode(contents),crc=crc32(data);
  const local=new Uint8Array(30+fileName.length);
  const h=new DataView(local.buffer);
  h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);
  h.setUint16(8,0,true);h.setUint32(14,crc,true);
  h.setUint32(18,data.length,true);h.setUint32(22,data.length,true);
  h.setUint16(26,fileName.length,true);local.set(fileName,30);
  files.push(local,data);
  const central=new Uint8Array(46+fileName.length),d=new DataView(central.buffer);
  d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);
  d.setUint32(16,crc,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);
  d.setUint16(28,fileName.length,true);d.setUint32(42,offset,true);
  central.set(fileName,46);directory.push(central);
  offset+=local.length+data.length;
 }
 const dirSize=directory.reduce((n,b)=>n+b.length,0);
 const end=new Uint8Array(22),e=new DataView(end.buffer);
 e.setUint32(0,0x06054b50,true);e.setUint16(8,entries.length,true);
 e.setUint16(10,entries.length,true);e.setUint32(12,dirSize,true);e.setUint32(16,offset,true);
 return new Blob([...files,...directory,end],{type:'model/3mf'});
}
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const colorHex=v=>typeof v==='string'&&/^#[A-Fa-f0-9]{6}$/.test(v)?v.toUpperCase():'#5BC6EB';
const hexFromInt=n=>'#'+(n&0xFFFFFF).toString(16).padStart(6,'0').toUpperCase();
function finite(v){
 if(!Number.isFinite(v)||Math.abs(v)>1000000)throw Error('Coordonnée de modèle invalide.');
 return Number(v.toFixed(5)).toString();
}
export function makeColored3MF(THREE,models){
 if(!models.length)throw Error('Ajoute une pièce au plateau avant d’exporter.');
 if(models.length>100)throw Error('Limite : 100 pièces par export.');
 let allTriangles=0,allColors=new Set(),parts=[];
 for(const model of models){
  const geo=model.geometry,position=geo?.getAttribute('position'),index=geo?.getIndex();
  if(!position)throw Error('Pièce sans géométrie.');
  const count=index?index.count:position.count;
  if(count<12||count%3!==0)throw Error('La pièce doit contenir des faces triangulaires.');
  const triangles=count/3;allTriangles+=triangles;
  if(allTriangles>150000)throw Error('Modèle trop complexe : maximum 150 000 triangles par export 3MF.');
  model.updateMatrixWorld(true);
  const det=model.matrixWorld.determinant();
  if(!Number.isFinite(det)||Math.abs(det)<1e-15)throw Error('Une pièce est écrasée à zéro : vérifie ses dimensions.');
  const invert=det<0,base=Number.isInteger(model.userData?.fjordPaintBase)
   ?hexFromInt(model.userData.fjordPaintBase)
   :hexFromInt(model.userData?.selectionOriginalColor??model.material?.color?.getHex?.()??0x5bc6eb);
  const faces=model.userData?.fjordPaintFaces||{};
  const merged=model.userData?.mergedParts;
  const sectionColors=[];
  if(Array.isArray(merged))for(const piece of merged){
   if(!Number.isInteger(piece.start)||!Number.isInteger(piece.count))continue;
   sectionColors.push({first:piece.start/3,last:(piece.start+piece.count)/3,color:hexFromInt(piece.color)});
  }
  const outVertices=[],outFaces=[];
  const vector=new THREE.Vector3();
  for(let t=0;t<triangles;t++){
   const coordinates=[];
   for(let j=0;j<3;j++){
    const source=index?index.getX(t*3+j):t*3+j;
    vector.fromBufferAttribute(position,source).applyMatrix4(model.matrixWorld);
    coordinates.push([finite(vector.x),finite(vector.y),finite(vector.z)]);
   }
   const swap=invert?[0,2,1]:[0,1,2];
   const verts=swap.map(j=>coordinates[j]);
   const vstart=outVertices.length;
   for(const [x,y,z] of verts)outVertices.push('<vertex x="'+x+'" y="'+y+'" z="'+z+'"/>');
   let color=base;
   const group=sectionColors.find(g=>t>=g.first&&t<g.last);
   if(group)color=group.color;
   if(Object.prototype.hasOwnProperty.call(faces,String(t)))color=colorHex(faces[t]);
   allColors.add(color);
   outFaces.push({start:vstart,color});
  }
  parts.push({name:String(model.name||'Pièce 3D').slice(0,100),vertices:outVertices,faces:outFaces});
 }
 if(allColors.size>64)throw Error('Palette trop grande : maximum 64 couleurs.');
 const palette=[...allColors].sort(),mapping=new Map(palette.map((c,i)=>[c,i]));
 const colorGroup=palette.map(c=>'<m:color color="'+c+'FF"/>').join('');
 const objects=parts.map((part,i)=>{
  const faces=part.faces.map(t=>'<triangle v1="'+t.start+'" v2="'+(t.start+1)+'" v3="'+(t.start+2)+
    '" pid="1" p1="'+mapping.get(t.color)+'"/>').join('');
  return '<object id="'+(i+2)+'" type="model" name="'+esc(part.name)+'"><mesh><vertices>'+
    part.vertices.join('')+'</vertices><triangles>'+faces+'</triangles></mesh></object>';
 }).join('');
 const build=parts.map((_,i)=>'<item objectid="'+(i+2)+'"/>').join('');
 const model='<?xml version="1.0" encoding="UTF-8"?>'+
  '<model unit="millimeter" xml:lang="fr-CA" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '+
  'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">'+
  '<metadata name="Application">Les Impressions du Fjord</metadata><resources>'+
  '<m:colorgroup id="1">'+colorGroup+'</m:colorgroup>'+
  objects+'</resources><build>'+build+'</build></model>';
 const types='<?xml version="1.0" encoding="UTF-8"?>'+
  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'+
  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'+
  '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'+
  '</Types>';
 const relationships='<?xml version="1.0" encoding="UTF-8"?>'+
  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+
  '<Relationship Target="/3D/3dmodel.model" Id="rel0" '+
  'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>';
 return {blob:zipStore([
  ['[Content_Types].xml',types],['_rels/.rels',relationships],['3D/3dmodel.model',model]
 ]),colorCount:palette.length,triangleCount:allTriangles};
}
