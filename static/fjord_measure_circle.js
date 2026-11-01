/* Measurer for STL/tessellated geometry. This is a fitted 3-point circumcircle,
 * not automatic recognition of exact CAD circular edges. No network calls. */
(function(){
 'use strict';
 function vec(p){
  if(Array.isArray(p)&&p.length===3) return p.map(Number);
  if(p&&typeof p==='object') return [Number(p.x),Number(p.y),Number(p.z)];
  return [NaN,NaN,NaN];
 }
 const add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]];
 const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
 const mul=(a,k)=>[a[0]*k,a[1]*k,a[2]*k];
 const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 const norm=a=>Math.sqrt(dot(a,a));
 function fitCircle(a,b,c){
  const p=vec(a),q=vec(b),r=vec(c);
  if(![...p,...q,...r].every(Number.isFinite))return null;
  const u=sub(q,p),v=sub(r,p),w=cross(u,v);
  const u2=dot(u,u),v2=dot(v,v),w2=dot(w,w);
  if(u2<1e-10||v2<1e-10||w2<1e-18)return null;
  // Degenerate/nearly collinear points cause huge and misleading radii.
  if(Math.sqrt(w2/u2/v2)<0.035)return null;
  const delta=mul(add(mul(cross(v,w),u2),mul(cross(w,u),v2)),1/(2*w2));
  const center=add(p,delta),radius=norm(delta),normal=mul(w,1/Math.sqrt(w2));
  if(!isFinite(radius)||radius<=0||![...center,...normal].every(Number.isFinite))return null;
  return {center,normal,radius,diameter:radius*2};
 }

 // Detect circular boundaries of a planar patch from the actual mesh triangles.
 // Works on regular tessellated STL caps/holes; does not invent circles on
 // curved surfaces or treat arbitrary mesh edges as exact CAD geometry.
 function findCircularEdge(geometry,faceIndex,point){
  const pos=geometry?.getAttribute?.('position');
  const index=geometry?.index;
  const count=Math.floor((index?index.count:pos?.count||0)/3);
  const target=vec(point);
  if(!pos||!Number.isInteger(faceIndex)||faceIndex<0||faceIndex>=count||
     count>90000||!target.every(Number.isFinite))return null;
  const vertex=i=>[pos.getX(i),pos.getY(i),pos.getZ(i)];
  const faceVertex=(face,k)=>vertex(index?index.getX(face*3+k):face*3+k);
  const a=faceVertex(faceIndex,0),b=faceVertex(faceIndex,1),c=faceVertex(faceIndex,2);
  const n=cross(sub(b,a),sub(c,a)),nl=norm(n);
  if(nl<1e-10)return null;
  const normal=mul(n,1/nl),planeTol=0.075,quant=0.002;
  const key=p=>p.map(v=>Math.round(v/quant)).join(',');
  const edges=new Map(),points=new Map();
  let planar=0;
  function edge(p,q){
   const ka=key(p),kb=key(q);
   if(ka===kb)return;
   points.set(ka,p);points.set(kb,q);
   const id=ka<kb?ka+'|'+kb:kb+'|'+ka;
   if(edges.has(id))edges.delete(id);else edges.set(id,[ka,kb]);
  }
  for(let i=0;i<count;i++){
   const p=faceVertex(i,0),q=faceVertex(i,1),r=faceVertex(i,2);
   // Only faces lying in the selected flat patch; folded side faces excluded.
   if(Math.abs(dot(normal,sub(p,a)))>planeTol||
      Math.abs(dot(normal,sub(q,a)))>planeTol||
      Math.abs(dot(normal,sub(r,a)))>planeTol)continue;
   const fn=cross(sub(q,p),sub(r,p)),flen=norm(fn);
   if(flen<1e-10||dot(fn,normal)/flen<.9848)continue;
   planar++;
   if(planar>50000)return null;
   edge(p,q);edge(q,r);edge(r,p);
  }
  if(edges.size<12||edges.size>65000)return null;
  const adj=new Map();
  for(const [ka,kb] of edges.values()){
   if(!adj.has(ka))adj.set(ka,[]);
   if(!adj.has(kb))adj.set(kb,[]);
   adj.get(ka).push(kb);adj.get(kb).push(ka);
  }
  const used=new Set();
  let best=null;
  const dSegment=(p,a,b)=>{
   const v=sub(b,a),w=sub(p,a),d=dot(v,v);
   const t=d<1e-12?0:Math.max(0,Math.min(1,dot(w,v)/d));
   const closest=add(a,mul(v,t));
   return {distance:norm(sub(p,closest)),closest};
  };
  for(const first of adj.keys()){
   if(used.has(first)||adj.get(first).length!==2)continue;
   const loop=[],seen=new Set();
   let prev=null,curr=first,closed=false;
   for(let j=0;j<adj.size+1;j++){
    if(seen.has(curr)){closed=curr===first;break;}
    seen.add(curr);loop.push(points.get(curr));
    const next=adj.get(curr)?.find(v=>v!==prev);
    if(!next||adj.get(curr).length!==2)break;
    prev=curr;curr=next;
   }
   for(const s of seen)used.add(s);
   if(!closed||loop.length<12)continue;
   const fit=fitCircle(loop[0],loop[Math.floor(loop.length/3)],loop[Math.floor(loop.length*2/3)]);
   if(!fit||fit.radius<.25||fit.radius>2000)continue;
   const tolerance=Math.max(.055,fit.radius*.008);
   let error=0,valid=true;
   for(const p of loop){
    const off=sub(p,fit.center);
    const planarError=Math.abs(dot(off,fit.normal));
    const radialError=Math.abs(norm(off)-fit.radius);
    if(planarError>tolerance||radialError>tolerance*2.5){valid=false;break;}
    error+=radialError;
   }
   if(!valid||error/loop.length>tolerance)continue;
   let nearest={distance:Infinity,closest:null};
   for(let i=0;i<loop.length;i++){
    const item=dSegment(target,loop[i],loop[(i+1)%loop.length]);
    if(item.distance<nearest.distance)nearest=item;
   }
   // A click near the rim selects the *nearest* circular boundary, not
   // automatically every circle in a complex part.
   const hitTolerance=Math.max(1.2,Math.min(4,fit.radius*.08));
   if(nearest.distance>hitTolerance)continue;
   if(!best||nearest.distance<best.edge_distance)
    best={...fit,point:nearest.closest,edge_distance:nearest.distance,
          vertices:loop.length,method:'planar-contour'};
  }
  return best;
 }
 window.fjordDetectCircularEdge=findCircularEdge;

 window.fjordFitCircle3D=fitCircle;
})();