/* ===================== VIEW AT SCALE — shared by the master app and the client app =====================
   Source: tools/room.js (+ tools/room.css), injected at build time into both apps. Edit here only.
   One wall, a Versailles parquet and Dylan's cane chair as a fixed reference (80 cm high).
   Everything is drawn in real centimetres with one camera: wall at D cm, eye at EYE cm above the floor.
   The work moves left/right and up/down on the wall; the chair moves left/right only.
   Host app sets window.ROOM_HOST = { t(key), lang, base (folder of room-chair.webp / room-parquet.jpg), fileBase(w) }.
   Settings of a view: { wall, artX, artY, chairX } in centimetres (artX/chairX from the centre, artY = height of the
   work's centre above the floor). Static image (roomRender) and interactive view (openRoom) share them. */
const ROOM={ D:500, EYE:140, CHAIR_H:80, CHAIR_Z:30, CHAIR_FRONT:55, FLOOR_MARGIN:7, PANEL:100, STATIC_W:1600, STATIC_H:1200,
  walls:[["pearl","#DAD8D3"],["white","#EEECE7"],["linen","#D8CFC0"],["green","#33503B"]] };
const ROOM_TXT={ fr:{back:"Retour",atScale:"Voir à l’échelle",roomHint:"Déplacez l’œuvre et la chaise du doigt",reset:"Recentrer",saveView:"Enregistrer l’image",
    walls:{pearl:"Gris perle",white:"Blanc galerie",linen:"Lin",green:"Vert Legacy"}},
  en:{back:"Back",atScale:"View at scale",roomHint:"Move the work and the chair with your finger",reset:"Reset",saveView:"Save image",
    walls:{pearl:"Pearl grey",white:"Gallery white",linen:"Linen",green:"Legacy green"}} };
const RH=()=>window.ROOM_HOST||{};
const rt=k=>{ const h=RH(); if(h.t){ const v=h.t(k); if(v!==undefined&&v!==k) return v; } const L=ROOM_TXT[h.lang||"fr"]||ROOM_TXT.fr; return L[k]!==undefined?L[k]:ROOM_TXT.en[k]; };
const resc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const NOT_WALL=/sculpt|furniture|mobili|object|objet|install|design|ceramic|céram/i;
function parseDims(str){
  if(!str) return null;
  const part=String(str).split(/[|·]/)[0].replace(/,/g,".");
  const frac=s=>s.replace(/(\d+)\s+(\d+)\/(\d+)/g,(m,a,b,c)=>String(+a + b/c)).replace(/(\d+)\/(\d+)/g,(m,b,c)=>String(b/c));
  const txt=frac(part);
  const nums=(txt.match(/\d+(\.\d+)?/g)||[]).map(Number).filter(n=>n>0);
  if(nums.length<2) return null;
  const inch=/\b(in|inch|inches)\b|"/i.test(txt)&&!/cm/i.test(txt);
  const k=inch?2.54:(/mm/i.test(txt)&&!/cm/i.test(txt)?0.1:(/\bm\b/i.test(txt)&&!/cm|mm/i.test(txt)?100:1));
  const [h,w,d]=nums.map(n=>n*k);
  return {h,w,d:d||0};
}
function canViewAtScale(w){
  if(!w) return false; if(NOT_WALL.test(w.category||"")) return false;
  const d=parseDims(w.dimensions); if(!d) return false;
  if(d.d>15) return false;                 // a volume, not a work hung on a wall
  return d.h>=3&&d.w>=3&&d.h<=1200&&d.w<=2400;
}
/* volumes (sculptures, objects, furniture): standing on a white plinth beside the chair, or on the parquet for furniture.
   Several parts ("Kaikai: 96.5 x 55.3 x 40 cm · Kiki: 81.1 x 57.6 x 41 cm"): the tallest part gives the scale of the photo. */
function parseDimsAll(str){
  if(!str) return null; const parts=String(str).split(/[·;\n]/).map(x=>parseDims(x)).filter(Boolean);
  if(!parts.length) return null;
  return { h:Math.max(...parts.map(p=>p.h)), w:Math.max(...parts.map(p=>p.w)), d:Math.max(...parts.map(p=>p.d||0)), parts:parts.length };
}
const ON_FLOOR=/furniture|mobili|design/i;
function canStand(w){
  if(!w||canViewAtScale(w)) return false; const d=parseDimsAll(w.dimensions); if(!d) return false;
  if(!(NOT_WALL.test(w.category||"")||d.d>15)) return false;
  return d.h>=5&&d.h<=400; }
const standDims=w=>parseDimsAll(w&&w.dimensions);
const roomAssets={};
function roomImg(src){ if(!src) return Promise.resolve(null); return roomAssets[src]||(roomAssets[src]=new Promise((res)=>{ const i=new Image(); i.onload=()=>res(i); i.onerror=()=>{ delete roomAssets[src]; res(null); }; i.src=src; })); }
const roomAsset=f=>(RH().base||"")+f;
const fmtCm=v=>(Math.round(v*10)/10).toLocaleString((RH().lang||"fr")==="fr"?"fr-FR":"en-GB",{maximumFractionDigits:1});
const R={};   // live state of the open (interactive) view
function chairW(s=R){ return s.chair?ROOM.CHAIR_H*s.chair.width/s.chair.height:66; }
/* size the work occupies on the wall (cm): its dimensions, or the bounding box when it hangs at an angle */
function artBox(s=R){ const {h,w}=s.dims, a=s.cut&&s.cut.angle||0; if(!a) return {w,h};
  const c=Math.abs(Math.cos(a)), n=Math.abs(Math.sin(a)); return {w:w*c+h*n, h:w*n+h*c}; }
/* standing volume: plinth (white, elegant) or parquet for furniture; sizes in cm, depths from the eye */
function standGeom(s=R){
  const o=s.obj, h=s.dims.h, wcm=o?h*o.bw/o.bh:s.dims.w, floor=!!s.onFloor;
  const ph=floor?0:Math.max(12,Math.min(90,105-h*0.9));            // low platform for large pieces, pedestal for small ones
  const margin=floor?0:Math.max(10,wcm*0.12), pw=wcm+2*margin, pd=floor?Math.max(30,s.dims.d||40):Math.max(40,Math.min(100,(s.dims.d||40)+24));
  const zb=ROOM.D-(floor?6:18), zf=zb-pd, zc=(zb+zf)/2;
  return {h,wcm,ph,pw,pd,zb,zf,zc,floor}; }
function roomWallOk(k){ return ROOM.walls.some(v=>v[0]===k)?k:"pearl"; }
/* default composition. portrait: phone held upright → chair beneath the work when it fits */
function roomDefaults(s=R,portrait){
  if(s.stand){ const g=standGeom(s), cw=chairW(s), gap=30, total=cw+gap+g.pw; s.chairX=-total/2+cw/2; s.artX=total/2-g.pw/2; s.artY=0; s.extentW=total; return; }
  const {h,w}=artBox(s), cw=chairW(s), gap=Math.max(25,Math.min(60,w*0.25));
  s.artY=Math.max(150,h/2+25);                     // centre at 150 cm (museum hang), never closer than 25 cm to the floor
  if(portrait&&s.artY-h/2>=ROOM.CHAIR_H+3&&w>=cw+20){
    s.artX=0; s.chairX=-w/2+cw/2+Math.min(15,(w-cw)/4); s.extentW=w;
  } else {
    const total=cw+gap+w;
    s.artX=-total/2+cw+gap+w/2;                    // composition centred: chair on the left, work on the right
    s.chairX=-total/2+cw/2; s.extentW=total;
  }
}
function roomApply(s,set){ if(!set) return false; let ok=false;
  for(const k of ["artX","artY","chairX"]) if(typeof set[k]==="number"&&isFinite(set[k])){ s[k]=set[k]; ok=true; }
  if(ok&&s.stand){ s.extentW=0; return ok; }
  if(ok){ const cw=chairW(s), w=artBox(s).w; s.extentW=2*Math.max(Math.abs(s.artX)+w/2,Math.abs(s.chairX)+cw/2); }
  return ok; }
const roomSettings=(s=R)=>Object.assign({wall:s.wall,artX:+s.artX.toFixed(2),artY:+s.artY.toFixed(2),chairX:+s.chairX.toFixed(2)},s.cutOff?{cut:"off"}:{});
/* layout: px per cm on the wall, wall base line, horizon. fit: frame everything around the composition (static image) */
function roomFit(s,W,H,dpr,fit){
  if(s.stand) return roomFitStand(s,W,H,dpr);
  const {h,w}=artBox(s), cw=chairW(s);
  let ext=s.extentW||cw+w+40;
  if(fit) ext=2*Math.max(Math.abs(s.artX)+w/2,Math.abs(s.chairX)+cw/2);
  const needH=Math.max(240,s.artY+h/2+(fit?30:40));
  const needW=Math.max(ext+2*(fit?24:18), 200);
  // the floor stops a few centimetres below the chair's front feet: the eye stays on the wall and the work
  const footCm=ROOM.EYE*(ROOM.D/(ROOM.D-ROOM.CHAIR_FRONT)-1), floorCm=footCm+ROOM.FLOOR_MARGIN;
  const scale=Math.min(H/(needH+floorCm), W/needW);
  Object.assign(s,{W,H,dpr,scale,baseY:H-scale*floorCm,cx:W/2});
  s.f=scale*ROOM.D; s.horizon=s.baseY-scale*ROOM.EYE;
  roomFloor(s);
}
function roomFitStand(s,W,H,dpr){
  const D=ROOM.D, g=standGeom(s), cw=chairW(s), zch=D-ROOM.CHAIR_Z, kc=D/zch, kf=D/g.zf, kc2=D/g.zc;
  const ext=2*Math.max(Math.abs(s.chairX)*kc+cw/2*kc, Math.abs(s.artX)*kf+g.pw/2*kf);
  const needW=Math.max(ext+48,200);
  const top=ROOM.EYE+(g.ph+g.h-ROOM.EYE)*kc2;                       // highest point, in wall centimetres
  const needH=Math.max(190,top+35);
  const znear=Math.min(D-ROOM.CHAIR_FRONT,g.zf), floorCm=ROOM.EYE*(D/znear-1)+ROOM.FLOOR_MARGIN+(g.floor?0:4);
  const scale=Math.min(H/(needH+floorCm), W/needW);
  Object.assign(s,{W,H,dpr,scale,baseY:H-scale*floorCm,cx:W/2}); s.f=scale*D; s.horizon=s.baseY-scale*ROOM.EYE;
  roomFloor(s); }
const roomP=(s,X,Y,Z)=>[s.cx+X*s.f/Z, s.horizon+(ROOM.EYE-Y)*s.f/Z];
/* screen rectangle of the plinth and the volume (for dragging) */
function standHit(s=R){ const g=standGeom(s); const a=roomP(s,s.artX-g.pw/2,0,g.zf), b=roomP(s,s.artX+g.pw/2,g.ph+g.h,g.zc);
  return {x:Math.min(a[0],b[0]), y:b[1], w:Math.abs(b[0]-a[0])+ (g.pw*s.f/g.zf - g.pw*s.f/g.zc), h:a[1]-b[1]}; }
function drawStand(x,s){
  const g=standGeom(s), X0=s.artX-g.pw/2, X1=s.artX+g.pw/2, P=(X,Y,Z)=>roomP(s,X,Y,Z);
  const poly=(pts,fill)=>{ x.beginPath(); pts.forEach((p,i)=>i?x.lineTo(p[0],p[1]):x.moveTo(p[0],p[1])); x.closePath(); x.fillStyle=fill; x.fill(); };
  // soft shadow of the plinth (or of the furniture) on the parquet
  const foot=[P(X0-3,0,g.zf-2),P(X1+3,0,g.zf-2),P(X1+3,0,g.zb),P(X0-3,0,g.zb)];
  x.save(); x.shadowColor="rgba(0,0,0,.38)"; x.shadowBlur=Math.max(8,(foot[1][0]-foot[0][0])*0.06); x.shadowOffsetX=10000; x.shadowOffsetY=2;
  x.translate(-10000,0); poly(foot,"#000"); x.restore();
  if(!g.floor){
    const fBL=P(X0,0,g.zf), fBR=P(X1,0,g.zf), fTL=P(X0,g.ph,g.zf), fTR=P(X1,g.ph,g.zf), bTL=P(X0,g.ph,g.zb), bTR=P(X1,g.ph,g.zb), bBL=P(X0,0,g.zb), bBR=P(X1,0,g.zb);
    // side seen from the room's centre
    if(X0>0) poly([fBL,fTL,bTL,bBL],"#E4E2DD"); else if(X1<0) poly([fBR,fTR,bTR,bBR],"#E4E2DD");
    if(g.ph<ROOM.EYE) poly([fTL,fTR,bTR,bTL],"#FBFBF9");                  // top, lit from above
    const gr=x.createLinearGradient(0,fTL[1],0,fBL[1]); gr.addColorStop(0,"#F5F4F1"); gr.addColorStop(1,"#E9E7E2");
    poly([fBL,fBR,fTR,fTL],gr);                                             // front
    x.strokeStyle="rgba(0,0,0,.07)"; x.lineWidth=Math.max(0.6,s.f/g.zf*0.25); x.beginPath(); x.moveTo(fTL[0],fTL[1]); x.lineTo(fTR[0],fTR[1]); x.stroke();
  }
  // the volume, standing on the plinth (or the parquet) at its own depth
  const o=s.obj; if(!o) return; const k=s.f/g.zc, hp=g.h*k, wp=g.wcm*k, base=P(s.artX,g.ph,g.zc);
  x.save(); x.translate(base[0],base[1]); x.scale(1,0.12); const sg=x.createRadialGradient(0,0,0,0,0,wp*0.55);
  sg.addColorStop(0,"rgba(0,0,0,.30)"); sg.addColorStop(1,"rgba(0,0,0,0)"); x.fillStyle=sg; x.beginPath(); x.arc(0,0,wp*0.55,0,Math.PI*2); x.fill(); x.restore();
  const sc=hp/o.bh; x.drawImage(o.canvas, base[0]-wp/2-o.pad*sc, base[1]-hp-o.pad*sc, o.canvas.width*sc, o.canvas.height*sc);
}
/* parquet in perspective, computed once per layout (device pixels) */
function roomFloor(s=R){
  const {W,H,dpr,baseY,horizon,f,cx}=s; const D=ROOM.D, E=ROOM.EYE, P=ROOM.PANEL;
  const fw=Math.round(W*dpr), y0=Math.floor(baseY*dpr), fh=Math.round(H*dpr)-y0;
  if(fw<=0||fh<=0||!s.parquet){ s.floor=null; return; }
  if(!s.parquet.__mips){ const mips=[]; let size=s.parquet.width; let src=s.parquet;
    while(size>=16){ const c=document.createElement("canvas"); c.width=c.height=size; const x=c.getContext("2d"); x.imageSmoothingQuality="high"; x.drawImage(src,0,0,size,size);
      mips.push({size,data:x.getImageData(0,0,size,size).data}); src=c; size=size>>1; }
    s.parquet.__mips=mips; }
  const out=new ImageData(fw,fh), o=out.data, mips=s.parquet.__mips, L=mips.length;
  for(let j=0;j<fh;j++){
    let acc=null;
    for(let ss=0;ss<2;ss++){
      const ypx=(y0+j+0.25+ss*0.5)/dpr; const dy=ypx-horizon; if(dy<=0) continue;
      const Z=f*E/dy;                                   // depth of this floor row (cm)
      const cmPerPx=Z/f/dpr;                             // footprint across
      const dzPerPx=Z*Z/(f*E)/dpr;                       // footprint in depth
      const fp=Math.sqrt(cmPerPx*dzPerPx);
      let lv=Math.round(Math.log2(Math.max(1,fp*mips[0].size/P))); lv=Math.max(0,Math.min(L-1,lv));
      const m=mips[lv], sz=m.size, d=m.data, k=sz/P;
      let tz=((D-Z)%P+P)%P; const ty=Math.floor(tz*k)%sz;
      const ao=1-0.28*Math.exp(-(D-Z)/18);              // soft shadow where floor meets wall
      const near=Math.min(1,(Z-ROOM.D*0.55)/(ROOM.D*0.45)); const light=(0.9+0.12*Math.max(0,near))*ao;
      if(!acc) acc=new Float32Array(fw*3);
      for(let i=0;i<fw;i++){
        const X=((i+0.5)/dpr-cx)*Z/f;
        const tx=Math.floor((((X+P*1000)%P))*k)%sz; const q=(ty*sz+tx)*4;
        const vig=1-0.10*Math.pow(Math.abs((i/fw)-0.5)*2,2);
        acc[i*3]+=d[q]*light*vig; acc[i*3+1]+=d[q+1]*light*vig; acc[i*3+2]+=d[q+2]*light*vig;
      }
    }
    if(!acc) continue;
    for(let i=0;i<fw;i++){ const q=(j*fw+i)*4; o[q]=acc[i*3]/2; o[q+1]=acc[i*3+1]/2; o[q+2]=acc[i*3+2]/2; o[q+3]=255; }
  }
  const c=document.createElement("canvas"); c.width=fw; c.height=fh; c.getContext("2d").putImageData(out,0,0);
  s.floor={c,y0};
}
/* ---------- automatic cut-out of the work from its photo ----------
   For a packshot (work photographed on a plain background, even with a light gradient):
   - the background is modelled from the photo's border (a plane per colour channel, robust to the gradient);
   - the work's outline is the minimum-area rectangle around what differs from it → its angle and its sides,
     which are matched to the work's dimensions;
   - openwork (much background inside the outline, e.g. a grid of bars): the background is removed everywhere,
     so the wall shows through; a solid work: only what lies outside the outline is removed (its white stays).
   Anything unclear (no plain background, work touching the edges, outline far from the dimensions) → null: the photo
   is used as before. */
const roomCuts=new WeakMap();
function roomCut(img,dims){
  if(!img||!dims) return null; const key=dims.w.toFixed(2)+"x"+dims.h.toFixed(2);
  let m=roomCuts.get(img); if(m&&key in m){ const r=m[key]; return r&&!r.fail?r:null; } if(!m){ m={}; roomCuts.set(img,m); }
  let r=null; try{ r=roomCutCompute(img,dims); }catch(e){ r=null; } m[key]=r; return r&&!r.fail?r:null; }
/* why a photo was not cut out (for a hint to Dylan): {fail:"edge", sides:[...]} the photo cuts the work,
   {fail:"ratio", ar, dr} the outline's proportions differ from the dimensions; null when cut out or for an ordinary photo */
function roomCutInfo(img,dims){ roomCut(img,dims); if(!img||!dims) return null; const m=roomCuts.get(img); const r=m&&m[dims.w.toFixed(2)+"x"+dims.h.toFixed(2)]; return r&&r.fail?r:null; }
function roomPrep(img){
  const MAX=1600, k0=Math.min(1,MAX/Math.max(img.width,img.height)), W=Math.max(8,Math.round(img.width*k0)), H=Math.max(8,Math.round(img.height*k0));
  const c=document.createElement("canvas"); c.width=W; c.height=H; const x=c.getContext("2d",{willReadFrequently:true});
  x.imageSmoothingEnabled=true; x.imageSmoothingQuality="high"; x.drawImage(img,0,0,W,H);
  const id=x.getImageData(0,0,W,H), d=id.data;
  // 1) background model from a band along the border
  const band=Math.max(2,Math.round(Math.min(W,H)*0.02)), step=Math.max(1,Math.round(Math.min(W,H)/300)), pts=[];
  for(let y=0;y<H;y+=step) for(let xx=0;xx<W;xx+=step){ if(xx>=band&&xx<W-band&&y>=band&&y<H-band) continue; const q=(y*W+xx)*4; pts.push([xx/W,y/H,d[q],d[q+1],d[q+2]]); }
  const fit=(list)=>{ // least squares a + b·x + c·y for each channel
    let n=0,sx=0,sy=0,sxx=0,syy=0,sxy=0; const sv=[0,0,0],sxv=[0,0,0],syv=[0,0,0];
    for(const p of list){ n++; sx+=p[0]; sy+=p[1]; sxx+=p[0]*p[0]; syy+=p[1]*p[1]; sxy+=p[0]*p[1]; for(let ch=0;ch<3;ch++){ sv[ch]+=p[2+ch]; sxv[ch]+=p[0]*p[2+ch]; syv[ch]+=p[1]*p[2+ch]; } }
    const A=[[n,sx,sy],[sx,sxx,sxy],[sy,sxy,syy]]; const det=m=>m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]);
    const D=det(A); if(Math.abs(D)<1e-9) return null;
    return [0,1,2].map(ch=>{ const b=[sv[ch],sxv[ch],syv[ch]]; return [0,1,2].map(j=>det(A.map((row,i)=>row.map((v,jj)=>jj===j?b[i]:v)))/D); }); };
  const res=(m,p)=>Math.max(...[0,1,2].map(ch=>Math.abs(p[2+ch]-(m[ch][0]+m[ch][1]*p[0]+m[ch][2]*p[1]))));
  let model=fit(pts); if(!model) return null;
  const r1=pts.map(p=>res(model,p)).sort((a,b)=>a-b), cut1=Math.max(12,r1[Math.floor(r1.length*0.6)]*3);
  const inl=pts.filter(p=>res(model,p)<=cut1); if(inl.length<pts.length*0.5) return null;   // border mostly not plain: not a packshot
  model=fit(inl)||model;
  const plain=pts.filter(p=>res(model,p)<22).length/pts.length; if(plain<0.5) return null;
  if(model.some(m=>Math.abs(m[1])>45||Math.abs(m[2])>45)) return null;   // a wall's lighting varies gently, not from one colour to another
  // the wall must show on every side of the photo (a work cut by the frame still leaves wall between its parts)
  const sideOk=f=>{ const q=pts.filter(f); return q.length && q.filter(p=>res(model,p)<22).length/q.length>=0.3; };
  const bx=band/W, by=band/H;
  if(!(sideOk(p=>p[1]<by)&&sideOk(p=>p[1]>=1-by)&&sideOk(p=>p[0]<bx)&&sideOk(p=>p[0]>=1-bx))) return null;
  const bgAt=(ch,fx,fy)=>model[ch][0]+model[ch][1]*fx+model[ch][2]*fy;
  return {c,x,id,d,W,H,model,bgAt,step}; }
function roomCutCompute(img,dims){
  const P0=roomPrep(img); if(!P0) return null; const {c,x,id,d,W,H,model,bgAt,step}=P0;
  // 2) difference to the background → alpha
  // α = how much of the pixel is the work: darkening of the background (shadows, dark bars) counts as black over the wall,
  // any other difference (colour, lighter than the wall) counts fully once clear of the photo's noise
  const T0=24, T1=60, alpha=new Uint8ClampedArray(W*H); let fg=0;
  for(let y=0;y<H;y++){ const fy=y/H; for(let xx=0;xx<W;xx++){ const fx=xx/W, q=(y*W+xx)*4;
    const b0=bgAt(0,fx,fy), b1=bgAt(1,fx,fy), b2=bgAt(2,fx,fy), Lb=Math.max(8,0.299*b0+0.587*b1+0.114*b2), L=0.299*d[q]+0.587*d[q+1]+0.114*d[q+2];
    const k=Math.min(1,L/Lb), dark=1-k;
    const dd=Math.max(Math.abs(d[q]-b0*k),Math.abs(d[q+1]-b1*k),Math.abs(d[q+2]-b2*k), L>Lb?Math.abs(L-Lb):0);
    let a=Math.max(Math.min(1,Math.max(0,(dark-0.035)*1.12)), dd<=T0?0:dd>=T1?1:(dd-T0)/(T1-T0));
    if(a<0.05) a=0; a=Math.round(a*255); alpha[y*W+xx]=a; if(a>127) fg++; } }
  if(fg<W*H*0.004) return null;
  // the whole work must be in the photo: a work cut by the frame cannot be measured
  const side=(get,n)=>{ let t=0,c=0; for(let i=1;i<n-1;i+=step){ c++; if(get(i)>127) t++; } return c?t/c:0; };
  const cov={top:side(i=>alpha[i],W), bottom:side(i=>alpha[(H-1)*W+i],W), left:side(i=>alpha[i*W],H), right:side(i=>alpha[i*W+W-1],H)};
  const cutSides=Object.keys(cov).filter(k=>cov[k]>0.04);
  if(cutSides.length){ if(cutSides.length>=3) return null;   // photographed (almost) edge to edge: an ordinary photo, no wall to remove
    return {fail:"edge",sides:cutSides}; }
  // 3) minimum-area rectangle around the work (convex hull + rotating calipers)
  const P=[]; const st=Math.max(1,Math.round(Math.min(W,H)/500));
  for(let y=0;y<H;y+=st) for(let xx=0;xx<W;xx+=st) if(alpha[y*W+xx]>127) P.push([xx+0.5,y+0.5]);
  if(P.length<12) return null;
  P.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
  const cr=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]); const lo=[],up=[];
  for(const p of P){ while(lo.length>=2&&cr(lo[lo.length-2],lo[lo.length-1],p)<=0) lo.pop(); lo.push(p); }
  for(let i=P.length-1;i>=0;i--){ const p=P[i]; while(up.length>=2&&cr(up[up.length-2],up[up.length-1],p)<=0) up.pop(); up.push(p); }
  const hull=lo.slice(0,-1).concat(up.slice(0,-1)); if(hull.length<3) return null;
  let best=null;
  for(let i=0;i<hull.length;i++){ const a=hull[i], b=hull[(i+1)%hull.length]; const L=Math.hypot(b[0]-a[0],b[1]-a[1]); if(L<1e-6) continue;
    const ux=(b[0]-a[0])/L, uy=(b[1]-a[1])/L; let mn1=1e9,mx1=-1e9,mn2=1e9,mx2=-1e9;
    for(const p of hull){ const p1=p[0]*ux+p[1]*uy, p2=-p[0]*uy+p[1]*ux; if(p1<mn1) mn1=p1; if(p1>mx1) mx1=p1; if(p2<mn2) mn2=p2; if(p2>mx2) mx2=p2; }
    const area=(mx1-mn1)*(mx2-mn2); if(!best||area<best.area){ const c1=(mn1+mx1)/2, c2=(mn2+mx2)/2; best={area,ang:Math.atan2(uy,ux),l1:mx1-mn1,l2:mx2-mn2,cx:c1*ux-c2*uy,cy:c1*uy+c2*ux}; } }
  if(!best) return null;
  let ang=best.ang, rw=best.l1, rh=best.l2;
  while(ang>Math.PI/4){ ang-=Math.PI/2; [rw,rh]=[rh,rw]; } while(ang<=-Math.PI/4){ ang+=Math.PI/2; [rw,rh]=[rh,rw]; }
  if(Math.abs(ang)<0.8*Math.PI/180) ang=0;                       // straight enough: simply framed
  // the outline must agree with the dimensions (otherwise the photo is not a plain packshot of this work)
  const ar=rw/rh, dr=dims.w/dims.h; if(Math.abs(Math.log(ar/dr))>Math.log(1.3)) return {fail:"ratio",ar,dr};
  // 4) openwork or solid?
  const ca=Math.cos(ang), sa=Math.sin(ang); let ins=0, insBg=0;
  const inRectPx=(px,py,pad)=>{ const dx=px-best.cx, dy=py-best.cy, u=dx*ca+dy*sa, v=-dx*sa+dy*ca; return [rw/2+pad-Math.abs(u), rh/2+pad-Math.abs(v)]; };
  for(let y=0;y<H;y+=st) for(let xx=0;xx<W;xx+=st){ const [e1,e2]=inRectPx(xx+0.5,y+0.5,-Math.min(rw,rh)*0.04); if(e1>0&&e2>0){ ins++; if(alpha[y*W+xx]<64) insBg++; } }
  const open=ins>0 && insBg/ins>0.35;
  for(let y=0;y<H;y++){ const fy=y/H; for(let xx=0;xx<W;xx++){ const i=y*W+xx, q=i*4;
    const [e1,e2]=inRectPx(xx+0.5,y+0.5,open?1.5:0.5); const edgeA=Math.max(0,Math.min(1,Math.min(e1,e2)));   // anti-aliased outline
    const a=open? alpha[i]*edgeA/255 : edgeA;
    if(open && a>0 && a<1){ // remove the photo's background from half-covered pixels: no white halo, shadows stay shadows on any wall
      const fx=xx/W; for(let ch=0;ch<3;ch++){ const bg=bgAt(ch,fx,fy); d[q+ch]=Math.max(0,Math.min(255,Math.round((d[q+ch]-(1-a)*bg)/Math.max(a,0.04)))); } }
    d[q+3]=Math.round(a*255); } }
  x.putImageData(id,0,0);
  return { canvas:c, angle:ang, rw, rh, cx:best.cx, cy:best.cy, open };
}
/* cut-out of a volume: background (and the photo's floor shadows) reached from the border is removed; everything enclosed
   by the object's outline stays, even if it is white like the backdrop. Small specks are dropped. */
const roomObjs=new WeakMap();
function roomObj(img){ if(!img) return null; if(roomObjs.has(img)){ const r=roomObjs.get(img); return r&&!r.fail?r:null; }
  let r=null; try{ r=roomObjCompute(img); }catch(e){ r=null; } roomObjs.set(img,r); return r&&!r.fail?r:null; }
function roomObjInfo(img){ roomObj(img); const r=img&&roomObjs.get(img); return r&&r.fail?r:(r?null:{fail:"plain"}); }
function roomObjCompute(img){
  const P0=roomPrep(img); if(!P0) return {fail:"plain"}; const {c,x,id,d,W,H,bgAt}=P0;
  const N=W*H, cls=new Uint8Array(N);   // 1 background-like, 2 shadow-like, 0 object
  for(let y=0;y<H;y++){ const fy=y/H; for(let xx=0;xx<W;xx++){ const fx=xx/W, i=y*W+xx, q=i*4;
    const b0=bgAt(0,fx,fy), b1=bgAt(1,fx,fy), b2=bgAt(2,fx,fy), Lb=Math.max(8,0.299*b0+0.587*b1+0.114*b2), L=0.299*d[q]+0.587*d[q+1]+0.114*d[q+2];
    const full=Math.max(Math.abs(d[q]-b0),Math.abs(d[q+1]-b1),Math.abs(d[q+2]-b2));
    const k=Math.min(1,L/Lb), dd2=Math.max(Math.abs(d[q]-b0*k),Math.abs(d[q+1]-b1*k),Math.abs(d[q+2]-b2*k));
    cls[i]=full<18?1:(dd2<14&&1-k<0.45&&L<=Lb+6)?2:0; } }
  // flood from the border through background and shadows
  const reach=new Uint8Array(N), st=[];
  const push=i=>{ if(!reach[i]&&cls[i]){ reach[i]=1; st.push(i); } };
  for(let xx=0;xx<W;xx++){ push(xx); push((H-1)*W+xx); } for(let y=0;y<H;y++){ push(y*W); push(y*W+W-1); }
  while(st.length){ const i=st.pop(), xx=i%W, y=(i-xx)/W; if(xx>0) push(i-1); if(xx<W-1) push(i+1); if(y>0) push(i-W); if(y<H-1) push(i+W); }
  // object = not reached; keep only significant pieces
  const lab=new Int32Array(N).fill(-1), sizes=[];
  for(let i=0;i<N;i++){ if(reach[i]||lab[i]>=0) continue; const id2=sizes.length; let n=0; lab[i]=id2; st.push(i);
    while(st.length){ const j=st.pop(); n++; const xx=j%W, y=(j-xx)/W;
      const nb=[xx>0?j-1:-1, xx<W-1?j+1:-1, y>0?j-W:-1, y<H-1?j+W:-1]; for(const t of nb){ if(t>=0&&!reach[t]&&lab[t]<0){ lab[t]=id2; st.push(t); } } }
    sizes.push(n); }
  if(!sizes.length) return {fail:"plain"};
  const big=Math.max(...sizes), keep=sizes.map(n=>n>=Math.max(40,big*0.01));
  let x0=W,y0=H,x1=-1,y1=-1, area=0;
  for(let y=0;y<H;y++) for(let xx=0;xx<W;xx++){ const i=y*W+xx; if(lab[i]>=0&&keep[lab[i]]){ area++; if(xx<x0)x0=xx; if(xx>x1)x1=xx; if(y<y0)y0=y; if(y>y1)y1=y; } }
  if(area<N*0.01) return {fail:"plain"};
  const sides=[]; if(y0<=1) sides.push("top"); if(y1>=H-2) sides.push("bottom"); if(x0<=1) sides.push("left"); if(x1>=W-2) sides.push("right");
  if(sides.length>=3) return {fail:"plain"}; if(sides.length) return {fail:"edge",sides};
  // alpha with a soft edge (average over a 3×3 neighbourhood of the object mask); remove the backdrop from edge pixels
  const m=new Float32Array(N); for(let i=0;i<N;i++) m[i]=(lab[i]>=0&&keep[lab[i]])?1:0;
  const pad=2, cw=x1-x0+1+2*pad, ch=y1-y0+1+2*pad, out=document.createElement("canvas"); out.width=cw; out.height=ch;
  const ox=out.getContext("2d"), od=ox.createImageData(cw,ch), o=od.data;
  for(let y=0;y<ch;y++){ const sy=y+y0-pad; if(sy<0||sy>=H) continue; for(let xx=0;xx<cw;xx++){ const sx=xx+x0-pad; if(sx<0||sx>=W) continue;
    const i=sy*W+sx; let a=0,n=0; for(let dy=-1;dy<=1;dy++) for(let dx=-1;dx<=1;dx++){ const yy=sy+dy, xq=sx+dx; if(yy<0||yy>=H||xq<0||xq>=W) continue; a+=m[yy*W+xq]; n++; }
    a=m[i]?Math.max(0.5,a/n):a/n*0.5; if(a<0.02) continue; const q=i*4, t=(y*cw+xx)*4;
    for(let c2=0;c2<3;c2++){ let v=d[q+c2]; if(a<1){ const bg=bgAt(c2,sx/W,sy/H); v=(v-(1-a)*bg)/a; } o[t+c2]=Math.max(0,Math.min(255,Math.round(v))); }
    o[t+3]=Math.round(a*255); } }
  ox.putImageData(od,0,0);
  return { canvas:out, bw:x1-x0+1, bh:y1-y0+1, pad };
}
const shade=(hex,k)=>{ const n=parseInt(hex.slice(1),16); const f=v=>Math.max(0,Math.min(255,Math.round(v*k))); return `rgb(${f(n>>16)},${f(n>>8&255)},${f(n&255)})`; };
function artHit(s=R){ const {scale,cx,baseY}=s, {h,w}=artBox(s); return { x:cx+(s.artX-w/2)*scale, y:baseY-(s.artY+h/2)*scale, w:w*scale, h:h*scale }; }
function artRect(s=R){ const {scale,cx,baseY}=s, {h,w}=s.dims; return { x:cx+(s.artX-w/2)*scale, y:baseY-(s.artY+h/2)*scale, w:w*scale, h:h*scale }; }
function chairRect(s=R){ const {f,cx,horizon}=s; const zc=ROOM.D-ROOM.CHAIR_Z, sc=f/zc; const hh=ROOM.CHAIR_H*sc, ww=chairW(s)*sc;
  const foot=horizon+f*ROOM.EYE/(ROOM.D-ROOM.CHAIR_FRONT); return { x:cx+s.chairX*sc-ww/2, y:foot-hh, w:ww, h:hh, s:sc, foot }; }
function roomDraw(cvs,opts,s=R){
  const cv=cvs||document.getElementById("rCv"); if(!cv||!s.W) return; const x=cv.getContext("2d"); const k=cv.width/s.W;
  x.setTransform(k,0,0,k,0,0); x.imageSmoothingEnabled=true; x.imageSmoothingQuality="high";
  const {W,H,baseY}=s; const col=(ROOM.walls.find(v=>v[0]===s.wall)||ROOM.walls[0])[1];
  // wall: soft light from above, a little shade towards the floor and the sides
  let g=x.createLinearGradient(0,0,0,baseY); g.addColorStop(0,shade(col,1.035)); g.addColorStop(0.75,col); g.addColorStop(1,shade(col,0.9));
  x.fillStyle=g; x.fillRect(0,0,W,baseY+1);
  g=x.createLinearGradient(0,0,W,0); g.addColorStop(0,"rgba(0,0,0,.07)"); g.addColorStop(0.25,"rgba(0,0,0,0)"); g.addColorStop(0.75,"rgba(0,0,0,0)"); g.addColorStop(1,"rgba(0,0,0,.07)");
  x.fillStyle=g; x.fillRect(0,0,W,baseY+1);
  // floor
  if(s.floor){ x.drawImage(s.floor.c,0,s.floor.y0/s.dpr,W,s.floor.c.height/s.dpr); } else { x.fillStyle="#6E4E36"; x.fillRect(0,baseY,W,H-baseY); }
  g=x.createLinearGradient(0,baseY-2,0,baseY+3); g.addColorStop(0,"rgba(0,0,0,0)"); g.addColorStop(0.5,"rgba(0,0,0,.18)"); g.addColorStop(1,"rgba(0,0,0,0)");
  x.fillStyle=g; x.fillRect(0,baseY-2,W,5);
  if(s.stand){ drawChair(x,s); drawStand(x,s); }
  else { drawHung(x,s); drawChair(x,s); }
  if(opts&&opts.caption){ x.fillStyle=s.wall==="green"?"rgba(244,240,230,.78)":"rgba(22,36,26,.62)"; x.font=`500 ${Math.max(11,W/90)}px "Hanken Grotesk",-apple-system,sans-serif`; x.textBaseline="bottom"; x.fillText(opts.caption,14,H-10); }
}
function drawHung(x,s){
  // the work, with the shadow of a hung piece
  const a=artRect(s);
  if(s.cut){ // cut out of its photo: drawn at its own angle, the wall showing around it (and through it when open)
    const k=s.cut, ang=k.angle, sx=a.w/k.rw, sy=a.h/k.rh;
    x.save(); x.translate(a.x+a.w/2,a.y+a.h/2); x.rotate(ang); x.scale(sx,sy); x.rotate(-ang); x.translate(-k.cx,-k.cy);
    x.shadowColor=k.open?"rgba(0,0,0,.16)":"rgba(0,0,0,.28)";   // an open work already brings its own shadows from the photo
    x.shadowBlur=k.open?Math.max(2,a.w*0.008):Math.max(6,a.w*0.035); x.shadowOffsetX=k.open?Math.max(1.5,a.w*0.008):Math.max(2,a.w*0.012); x.shadowOffsetY=k.open?Math.max(2,a.w*0.012):Math.max(3,a.w*0.02);
    x.drawImage(k.canvas,0,0); x.restore();
  } else {
    x.save(); x.shadowColor="rgba(0,0,0,.28)"; x.shadowBlur=Math.max(6,a.w*0.035); x.shadowOffsetX=Math.max(2,a.w*0.012); x.shadowOffsetY=Math.max(3,a.w*0.02);
    x.fillStyle="#fff"; x.fillRect(a.x,a.y,a.w,a.h); x.restore();
    if(s.art){ // cover the exact dimensions without distorting the image
      const iw=s.art.width, ih=s.art.height, r=Math.max(a.w/iw,a.h/ih), sw=a.w/r, sh=a.h/r;
      x.drawImage(s.art,(iw-sw)/2,(ih-sh)/2,sw,sh,a.x,a.y,a.w,a.h); } }
}
function drawChair(x,s){
  // chair: contact shadow, then the chair
  const c=chairRect(s); let g;
  x.save(); x.translate(c.x+c.w/2,c.foot-c.h*0.04); x.scale(1,0.16);
  g=x.createRadialGradient(0,0,0,0,0,c.w*0.62); g.addColorStop(0,"rgba(0,0,0,.42)"); g.addColorStop(1,"rgba(0,0,0,0)");
  x.fillStyle=g; x.beginPath(); x.arc(0,0,c.w*0.62,0,Math.PI*2); x.fill(); x.restore();
  if(s.chair) x.drawImage(s.chair,c.x,c.y,c.w,c.h);
}
const roomCaption=(w,dims)=>`${w.artist||""}${w.title?", "+w.title:""}${w.year?", "+w.year:""} · ${dims.parts?`H. ${fmtCm(dims.h)} cm`:`${fmtCm(dims.h)} × ${fmtCm(dims.w)} cm`} · Legacy Shaper`;

/* ---------- static image (the "view at scale" shown among the views, used in PDFs) ---------- */
async function roomRender(w,photo,set,opts){
  const stand=!canViewAtScale(w)&&canStand(w);
  const dims=stand?standDims(w):parseDims(w&&w.dimensions); if(!dims) return null;
  opts=opts||{}; const W=opts.W||ROOM.STATIC_W, H=opts.H||ROOM.STATIC_H;
  const [art,chair,parquet]=await Promise.all([roomImg(photo),roomImg(roomAsset("room-chair.webp")),roomImg(roomAsset("room-parquet.jpg"))]);
  const s={dims,wall:roomWallOk(set&&set.wall),art,chair,parquet};
  if(stand){ s.stand=true; s.onFloor=ON_FLOOR.test(w.category||""); s.obj=roomObj(art); if(!s.obj) return null; }
  else { s.cutOff=!!(set&&set.cut==="off"); s.cut=s.cutOff?null:roomCut(art,dims); }
  roomDefaults(s,false); roomApply(s,set);
  roomFit(s,W,H,1,true);
  const c=document.createElement("canvas"); c.width=W; c.height=H;
  roomDraw(c,opts.caption?{caption:roomCaption(w,dims)}:null,s);
  return c;
}
async function roomRenderURL(w,photo,set,opts){ const c=await roomRender(w,photo,set,opts); return c?c.toDataURL("image/jpeg",0.92):""; }

/* ---------- interactive view (full screen) ----------
   opt: { init:{wall,artX,artY,chairX}, fit:true (frame like the static image), onSave(settings) + saveLabel (replaces "Save image"),
          onClose(settings) } */
async function openRoom(w,photo,opt){
  opt=opt||{};
  const stand=!canViewAtScale(w)&&canStand(w);
  const dims=stand?standDims(w):parseDims(w.dimensions); if(!dims) return;
  if(stand){ const im=await roomImg(photo); if(!roomObj(im)) return; }
  let wall="pearl"; try{ wall=localStorage.getItem("ls-wall")||"pearl"; }catch(e){}
  if(opt.init&&opt.init.wall) wall=opt.init.wall; wall=roomWallOk(wall);
  let el=document.getElementById("room"); if(!el){ el=document.createElement("div"); el.id="room"; document.body.appendChild(el); }
  el.hidden=false; R.prevOverflow=document.body.style.overflow; document.body.style.overflow="hidden";
  el.innerHTML=`<div class="rtop"><button id="rBack">← ${resc(rt("back"))}</button><div class="rt"><b><i>${resc(w.title||"")}</i>${w.year?`, ${resc(w.year)}`:""}</b><span>${resc(w.artist)}</span></div><span style="width:62px"></span></div>
    <div class="rstage" id="rStage"><canvas id="rCv"></canvas><div class="hint" id="rHint">${resc(rt("roomHint"))}</div></div>
    <div class="rbar"><div class="sw">${ROOM.walls.map(([k,c])=>`<button data-wall="${k}" title="${resc(rt("walls")[k])}" aria-label="${resc(rt("walls")[k])}" style="background:${c}" class="${k===wall?"on":""}"></button>`).join("")}</div>
      <span class="dim">${stand?`H. ${resc(fmtCm(dims.h))} cm`:`${resc(fmtCm(dims.h))} × ${resc(fmtCm(dims.w))} cm`}</span><span class="rb"><button class="tb" id="rReset">${resc(rt("reset"))}</button><button class="tb ${opt.onSave?"pri":""}" id="rSave">${resc(opt.saveLabel||rt("saveView"))}</button></span></div>`;
  for(const k of Object.keys(R)) delete R[k];
  Object.assign(R,{ w, dims, wall, art:null, chair:null, parquet:null, floor:null, drag:null, open:true, opt });
  const [art,chair,parquet]=await Promise.all([roomImg(photo),roomImg(roomAsset("room-chair.webp")),roomImg(roomAsset("room-parquet.jpg"))]);
  if(!R.open) return;
  R.art=art; R.chair=chair; R.parquet=parquet;
  if(stand){ R.stand=true; R.onFloor=ON_FLOOR.test(w.category||""); R.obj=roomObj(art); }
  else { R.cutOff=!!(opt.init&&opt.init.cut==="off"); R.cut=R.cutOff?null:roomCut(art,dims); }
  const reset=()=>{ const st=document.getElementById("rStage"); roomDefaults(R,!opt.fit&&st&&st.clientWidth<st.clientHeight*0.85); };
  reset(); if(opt.init) roomApply(R,opt.init);
  roomLayout();
  document.getElementById("rBack").onclick=()=>closeRoom();
  document.getElementById("rReset").onclick=()=>{ reset(); roomLayout(); };
  document.getElementById("rSave").onclick=async()=>{ if(opt.onSave){ const st=roomSettings(); closeRoom(true); await opt.onSave(st); } else roomSave(); };
  el.querySelectorAll("[data-wall]").forEach(b=>b.onclick=()=>{ R.wall=b.dataset.wall; try{ localStorage.setItem("ls-wall",R.wall); }catch(e){}
    el.querySelectorAll("[data-wall]").forEach(x=>x.classList.toggle("on",x===b)); roomDraw(); });
  const cv=document.getElementById("rCv");
  cv.addEventListener("pointerdown",roomDown); cv.addEventListener("pointermove",roomMove);
  cv.addEventListener("pointerup",roomUp); cv.addEventListener("pointercancel",roomUp);
  R.onResize=()=>{ if(R.open) roomLayout(); }; window.addEventListener("resize",R.onResize);
  R.onKey=e=>{ if(e.key==="Escape"&&R.open){ e.stopImmediatePropagation(); closeRoom(); } }; document.addEventListener("keydown",R.onKey,true);
  setTimeout(()=>{ const h=document.getElementById("rHint"); if(h) h.style.opacity="0"; },3200);
}
function closeRoom(saved){
  if(!R.open) return; const st=R.W?roomSettings():null; const opt=R.opt||{};
  R.open=false; const el=document.getElementById("room"); el.hidden=true; el.innerHTML="";
  if(R.onResize) window.removeEventListener("resize",R.onResize); if(R.onKey) document.removeEventListener("keydown",R.onKey,true);
  document.body.style.overflow=R.prevOverflow||"";
  if(!saved&&opt.onClose&&st) opt.onClose(st);
}
function roomLayout(){
  const st=document.getElementById("rStage"), cv=document.getElementById("rCv"); if(!st||!cv) return;
  let W=st.clientWidth, H=st.clientHeight;
  if(R.opt&&R.opt.fit){ // same frame as the static image (4:3), centred in the stage
    const k=Math.min(W/ROOM.STATIC_W,H/ROOM.STATIC_H); const w=Math.round(ROOM.STATIC_W*k), h=Math.round(ROOM.STATIC_H*k);
    cv.style.width=w+"px"; cv.style.height=h+"px"; cv.style.left=Math.round((W-w)/2)+"px"; cv.style.top=Math.round((H-h)/2)+"px"; st.style.background="#1B1D1B"; W=w; H=h; }
  const dpr=Math.min(window.devicePixelRatio||1,3);
  cv.width=Math.round(W*dpr); cv.height=Math.round(H*dpr);
  roomFit(R,W,H,dpr,!!(R.opt&&R.opt.fit)); roomDraw();
}
/* dragging */
function roomPt(e){ const r=document.getElementById("rCv").getBoundingClientRect(); return {x:e.clientX-r.left,y:e.clientY-r.top}; }
const inRect=(p,r,pad)=>p.x>=r.x-pad&&p.x<=r.x+r.w+pad&&p.y>=r.y-pad&&p.y<=r.y+r.h+pad;
function roomDown(e){
  const p=roomPt(e), c=chairRect(), a=R.stand?standHit():artHit();
  const what=inRect(p,c,4)?"chair":inRect(p,a,8)?"art":null; if(!what) return;
  R.drag={what,p0:p,ax:R.artX,ay:R.artY,chx:R.chairX}; e.target.setPointerCapture(e.pointerId); e.target.classList.add("drag");
  const h=document.getElementById("rHint"); if(h) h.style.opacity="0";
}
function roomMove(e){
  if(!R.drag) return; const p=roomPt(e), dx=p.x-R.drag.p0.x, dy=p.y-R.drag.p0.y; const {h,w}=artBox(R);
  const halfW=R.W/2/R.scale;
  if(R.drag.what==="art"&&R.stand){ const g=standGeom(R), lim=R.W/2*g.zc/R.f; R.artX=Math.max(-lim,Math.min(lim,R.drag.ax+dx*g.zc/R.f)); }
  else if(R.drag.what==="art"){
    R.artX=Math.max(-halfW-w/2+w*0.2, Math.min(halfW+w/2-w*0.2, R.drag.ax+dx/R.scale));   // keep at least a fifth of the work in view
    const top=(R.baseY)/R.scale;                                   // visible wall height (cm)
    R.artY=Math.max(h/2+2, Math.min(top-h/2*0.2, R.drag.ay-dy/R.scale));
  } else {
    const s=chairRect().s; const lim=R.W/2/s;
    R.chairX=Math.max(-lim, Math.min(lim, R.drag.chx+dx/s));
  }
  roomDraw();
}
function roomUp(e){ if(!R.drag) return; R.drag=null; try{ e.target.releasePointerCapture(e.pointerId); }catch(x){} e.target.classList.remove("drag"); }
async function roomSave(){
  const w=R.w; const c=document.createElement("canvas"); const k=Math.max(2,R.dpr);
  c.width=Math.round(R.W*k); c.height=Math.round(R.H*k);
  roomDraw(c,{caption:roomCaption(w,R.dims)});
  const fb=RH().fileBase?RH().fileBase(w):[w.artist,w.title,w.year].filter(Boolean).join(" - ").replace(/[\\/:*?"<>|]+/g,"");
  const name=`${fb} - ${rt("atScale")}.jpg`;
  const blob=await new Promise(r=>c.toBlob(r,"image/jpeg",0.92)); if(!blob) return;
  try{ const file=new File([blob],name,{type:"image/jpeg"});
    if(navigator.canShare&&navigator.canShare({files:[file]})&&/iPhone|iPad|Android/.test(navigator.userAgent)){ await navigator.share({files:[file],title:name}); return; } }catch(e){ if(e&&e.name==="AbortError") return; }
  const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url; a.download=name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),4000);
}
/* ===================== end of view at scale ===================== */
