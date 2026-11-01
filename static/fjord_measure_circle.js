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
 window.fjordFitCircle3D=fitCircle;
})();