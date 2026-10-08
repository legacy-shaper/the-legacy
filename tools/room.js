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
const roomAssets={};
function roomImg(src){ if(!src) return Promise.resolve(null); return roomAssets[src]||(roomAssets[src]=new Promise((res)=>{ const i=new Image(); i.onload=()=>res(i); i.onerror=()=>{ delete roomAssets[src]; res(null); }; i.src=src; })); }
const roomAsset=f=>(RH().base||"")+f;
const fmtCm=v=>(Math.round(v*10)/10).toLocaleString((RH().lang||"fr")==="fr"?"fr-FR":"en-GB",{maximumFractionDigits:1});
const R={};   // live state of the open (interactive) view
function chairW(s=R){ return s.chair?ROOM.CHAIR_H*s.chair.width/s.chair.height:66; }
function roomWallOk(k){ return ROOM.walls.some(v=>v[0]===k)?k:"pearl"; }
/* default composition. portrait: phone held upright → chair beneath the work when it fits */
function roomDefaults(s=R,portrait){
  const {h,w}=s.dims, cw=chairW(s), gap=Math.max(25,Math.min(60,w*0.25));
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
  if(ok){ const cw=chairW(s), w=s.dims.w; s.extentW=2*Math.max(Math.abs(s.artX)+w/2,Math.abs(s.chairX)+cw/2); }
  return ok; }
const roomSettings=(s=R)=>({wall:s.wall,artX:+s.artX.toFixed(2),artY:+s.artY.toFixed(2),chairX:+s.chairX.toFixed(2)});
/* layout: px per cm on the wall, wall base line, horizon. fit: frame everything around the composition (static image) */
function roomFit(s,W,H,dpr,fit){
  const {h,w}=s.dims, cw=chairW(s);
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
const shade=(hex,k)=>{ const n=parseInt(hex.slice(1),16); const f=v=>Math.max(0,Math.min(255,Math.round(v*k))); return `rgb(${f(n>>16)},${f(n>>8&255)},${f(n&255)})`; };
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
  // the work, with the shadow of a hung piece
  const a=artRect(s);
  x.save(); x.shadowColor="rgba(0,0,0,.28)"; x.shadowBlur=Math.max(6,a.w*0.035); x.shadowOffsetX=Math.max(2,a.w*0.012); x.shadowOffsetY=Math.max(3,a.w*0.02);
  x.fillStyle="#fff"; x.fillRect(a.x,a.y,a.w,a.h); x.restore();
  if(s.art){ // cover the exact dimensions without distorting the image
    const iw=s.art.width, ih=s.art.height, r=Math.max(a.w/iw,a.h/ih), sw=a.w/r, sh=a.h/r;
    x.drawImage(s.art,(iw-sw)/2,(ih-sh)/2,sw,sh,a.x,a.y,a.w,a.h); }
  // chair: contact shadow, then the chair
  const c=chairRect(s);
  x.save(); x.translate(c.x+c.w/2,c.foot-c.h*0.04); x.scale(1,0.16);
  g=x.createRadialGradient(0,0,0,0,0,c.w*0.62); g.addColorStop(0,"rgba(0,0,0,.42)"); g.addColorStop(1,"rgba(0,0,0,0)");
  x.fillStyle=g; x.beginPath(); x.arc(0,0,c.w*0.62,0,Math.PI*2); x.fill(); x.restore();
  if(s.chair) x.drawImage(s.chair,c.x,c.y,c.w,c.h);
  if(opts&&opts.caption){ x.fillStyle=s.wall==="green"?"rgba(244,240,230,.78)":"rgba(22,36,26,.62)"; x.font=`500 ${Math.max(11,W/90)}px "Hanken Grotesk",-apple-system,sans-serif`; x.textBaseline="bottom"; x.fillText(opts.caption,14,H-10); }
}
const roomCaption=(w,dims)=>`${w.artist||""}${w.title?", "+w.title:""}${w.year?", "+w.year:""} · ${fmtCm(dims.h)} × ${fmtCm(dims.w)} cm · Legacy Shaper`;

/* ---------- static image (the "view at scale" shown among the views, used in PDFs) ---------- */
async function roomRender(w,photo,set,opts){
  const dims=parseDims(w&&w.dimensions); if(!dims) return null;
  opts=opts||{}; const W=opts.W||ROOM.STATIC_W, H=opts.H||ROOM.STATIC_H;
  const [art,chair,parquet]=await Promise.all([roomImg(photo),roomImg(roomAsset("room-chair.webp")),roomImg(roomAsset("room-parquet.jpg"))]);
  const s={dims,wall:roomWallOk(set&&set.wall),art,chair,parquet};
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
  const dims=parseDims(w.dimensions); if(!dims) return;
  let wall="pearl"; try{ wall=localStorage.getItem("ls-wall")||"pearl"; }catch(e){}
  if(opt.init&&opt.init.wall) wall=opt.init.wall; wall=roomWallOk(wall);
  let el=document.getElementById("room"); if(!el){ el=document.createElement("div"); el.id="room"; document.body.appendChild(el); }
  el.hidden=false; R.prevOverflow=document.body.style.overflow; document.body.style.overflow="hidden";
  el.innerHTML=`<div class="rtop"><button id="rBack">← ${resc(rt("back"))}</button><div class="rt"><b><i>${resc(w.title||"")}</i>${w.year?`, ${resc(w.year)}`:""}</b><span>${resc(w.artist)}</span></div><span style="width:62px"></span></div>
    <div class="rstage" id="rStage"><canvas id="rCv"></canvas><div class="hint" id="rHint">${resc(rt("roomHint"))}</div></div>
    <div class="rbar"><div class="sw">${ROOM.walls.map(([k,c])=>`<button data-wall="${k}" title="${resc(rt("walls")[k])}" aria-label="${resc(rt("walls")[k])}" style="background:${c}" class="${k===wall?"on":""}"></button>`).join("")}</div>
      <span class="dim">${resc(fmtCm(dims.h))} × ${resc(fmtCm(dims.w))} cm</span><span class="rb"><button class="tb" id="rReset">${resc(rt("reset"))}</button><button class="tb ${opt.onSave?"pri":""}" id="rSave">${resc(opt.saveLabel||rt("saveView"))}</button></span></div>`;
  for(const k of Object.keys(R)) delete R[k];
  Object.assign(R,{ w, dims, wall, art:null, chair:null, parquet:null, floor:null, drag:null, open:true, opt });
  const [art,chair,parquet]=await Promise.all([roomImg(photo),roomImg(roomAsset("room-chair.webp")),roomImg(roomAsset("room-parquet.jpg"))]);
  if(!R.open) return;
  R.art=art; R.chair=chair; R.parquet=parquet;
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
  const p=roomPt(e), c=chairRect(), a=artRect();
  const what=inRect(p,c,4)?"chair":inRect(p,a,8)?"art":null; if(!what) return;
  R.drag={what,p0:p,ax:R.artX,ay:R.artY,chx:R.chairX}; e.target.setPointerCapture(e.pointerId); e.target.classList.add("drag");
  const h=document.getElementById("rHint"); if(h) h.style.opacity="0";
}
function roomMove(e){
  if(!R.drag) return; const p=roomPt(e), dx=p.x-R.drag.p0.x, dy=p.y-R.drag.p0.y; const {h,w}=R.dims;
  const halfW=R.W/2/R.scale;
  if(R.drag.what==="art"){
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
