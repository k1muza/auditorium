// Generates the document drawing set (SVG, true-scale in mm) from model/model.json + model/properties.json.
// Usage (Node 18+): see HANDOFF.md §6. fonts = { r: base64 woff2, m: base64 woff2 }
function generate(model, props, fonts, opt){
  const O = model.objects; const by = {}; O.forEach(o=>by[o.n]=o);
  const sel = re => O.filter(o=>re.test(o.n));
  const scene = props['SC:CA3000_Concept'];
  const GX = scene.x_lines, GY = scene.y_lines;
  const C = Object.assign({ink:'#1d1d1b', grey:'#6e747b', mid:'#9aa1a8', light:'#c8ccd0', tone:'#e7e5df', paper:'#ffffff', accent:'#9a6a3f'}, opt.colors||{});
  const LW = {cut:0.5, heavy:0.35, med:0.25, thin:0.18, hair:0.13};
  const f2 = v => (Math.round(v*100)/100).toString();
  const pts3 = o => o.v || (()=>{const a=[]; for(const x of [o.mn[0],o.mx[0]]) for(const y of [o.mn[1],o.mx[1]]) for(const z of [o.mn[2],o.mx[2]]) a.push([x,y,z]); return a;})();
  const hull = P => { P = P.map(p=>[+p[0].toFixed(3),+p[1].toFixed(3)]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]); if(P.length<3) return P; const cr=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]); const lo=[],up=[]; for(const p of P){while(lo.length>=2&&cr(lo[lo.length-2],lo[lo.length-1],p)<=0)lo.pop(); lo.push(p);} for(let i=P.length-1;i>=0;i--){const p=P[i]; while(up.length>=2&&cr(up[up.length-2],up[up.length-1],p)<=0)up.pop(); up.push(p);} return lo.slice(0,-1).concat(up.slice(0,-1)); };
  const attrs = a => Object.entries(a||{}).map(([k,v])=>`${k}="${v}"`).join(' ');
  const poly = (P,a) => `<polygon points="${P.map(p=>f2(p[0])+','+f2(p[1])).join(' ')}" ${attrs(a)}/>`;
  const pline = (P,a) => `<polyline points="${P.map(p=>f2(p[0])+','+f2(p[1])).join(' ')}" fill="none" ${attrs(a)}/>`;
  const line = (a,b,at) => `<line x1="${f2(a[0])}" y1="${f2(a[1])}" x2="${f2(b[0])}" y2="${f2(b[1])}" ${attrs(at)}/>`;
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
  const text = (x,y,s,a) => { a=Object.assign({},a||{}); const cl=(a.class||'').split(' '); delete a.class; const at={'font-family':"IBM Plex Mono, Menlo, Consolas, monospace",'font-size':cl.includes('s')?1.8:(cl.includes('l')?2.6:2.2),fill:C.ink}; if(cl.includes('b')) at['font-weight']=500; if(cl.includes('c')){at['text-anchor']='middle'; at['dominant-baseline']='central';} if(cl.includes('m')) at['text-anchor']='middle'; if(cl.includes('e')) at['text-anchor']='end'; if(cl.includes('h')){at['paint-order']='stroke'; at.stroke=C.paper; at['stroke-width']=0.7; at['stroke-linejoin']='round';} if(a.style){ const m=/fill:([^;]+)/.exec(a.style); if(m) at.fill=m[1]; delete a.style;} return `<text x="${f2(x)}" y="${f2(y)}" ${attrs(Object.assign(at,a))}>${esc(s)}</text>`; };
  const circle = (x,y,r,a) => `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(r)}" ${attrs(a)}/>`;
  const stroke = (c,w,extra) => Object.assign({stroke:c, 'stroke-width':w, fill:'none'}, extra||{});
  const DASH = {grid:'5 1.2 0.6 1.2', hidden:'1.4 0.9', assumed:'1.4 0.9', unresolved:'0.4 0.8'};
  const head = (w,h,bg) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f2(w)} ${f2(h)}" width="${f2(w)}mm" height="${f2(h)}mm"><rect width="100%" height="100%" fill="${bg||C.paper}"/>`;
  function view(proj, k, b, pad){ const p = pad||[0,0,0,0]; const P = q => { const [u,v]=proj(q); return [(u-b[0])*k+p[3], (v-b[1])*k+p[0]]; }; return {P, w:(b[2]-b[0])*k+p[1]+p[3], h:(b[3]-b[1])*k+p[0]+p[2], k}; }
  const dPath = (V,list) => list.map(o=>{const H=hull(pts3(o).map(V.P)); return 'M'+H.map(p=>f2(p[0])+' '+f2(p[1])).join('L')+'Z';}).join('');
  const shapes = (V,list,a) => list.length?`<path d="${dPath(V,list)}" ${attrs(a)}/>`:'';
  const shape = (V,o,a) => poly(hull(pts3(o).map(V.P)), a);
  const bubble = (x,y,s,r) => circle(x,y,r||3.2,{fill:C.paper,stroke:C.ink,'stroke-width':LW.thin}) + text(x,y+0.05,s,{class:'c l'});
  function dimH(pts, y, yFrom, opt2){ opt2=opt2||{}; let s=''; const xs=pts.map(p=>p[0]); s+=line([Math.min(...xs)-1.5,y],[Math.max(...xs)+1.5,y],stroke(C.ink,LW.hair));
    pts.forEach(p=>{ if(yFrom!=null) s+=line([p[0], yFrom + (yFrom<y?1:-1)*1.2],[p[0], y+(yFrom<y?1.2:-1.2)],stroke(C.ink,LW.hair)); s+=line([p[0]-0.8,y+0.8],[p[0]+0.8,y-0.8],stroke(C.ink,LW.med)); });
    for(let i=0;i<pts.length-1;i++){ const a=pts[i],b=pts[i+1]; const val=Math.round(Math.abs(b[1]-a[1])*1000); if(Math.abs(b[0]-a[0])<3.5 && !opt2.force) continue; s+=text((a[0]+b[0])/2, y-0.9, val, {class:'m s'}); }
    return s; }
  function dimV(pts, x, xFrom){ let s=''; const ys=pts.map(p=>p[0]); s+=line([x,Math.min(...ys)-1.5],[x,Math.max(...ys)+1.5],stroke(C.ink,LW.hair));
    pts.forEach(p=>{ if(xFrom!=null) s+=line([xFrom+(xFrom<x?1:-1)*1.2,p[0]],[x+(xFrom<x?1.2:-1.2),p[0]],stroke(C.ink,LW.hair)); s+=line([x-0.8,p[0]+0.8],[x+0.8,p[0]-0.8],stroke(C.ink,LW.med)); });
    for(let i=0;i<pts.length-1;i++){ const a=pts[i],b=pts[i+1]; const val=Math.round(Math.abs(b[1]-a[1])*1000); if(Math.abs(b[0]-a[0])<3.5) continue; const cy=(a[0]+b[0])/2; s+=text(x-0.9,cy,val,{class:'m s',transform:`rotate(-90 ${f2(x-0.9)} ${f2(cy)})`}); }
    return s; }
  function level(x,y,label,w,side){ side=side||1; let s=''; s+=poly([[x,y],[x-1.2*side*0,y],[x-1.1,y-1.6],[x+1.1,y-1.6]],{fill:C.paper,stroke:C.ink,'stroke-width':LW.thin}); s+=poly([[x,y],[x-1.1,y-1.6],[x,y-1.6]],{fill:C.ink}); s+=text(x+2*side,y-0.6,label,{class:side>0?'s':'s e'}); return s; }
  function scaleBar(x,y,k,steps){ let s=''; const tot=steps[steps.length-1]; for(let i=0;i<steps.length-1;i++){ s+=`<rect x="${f2(x+steps[i]*k)}" y="${f2(y)}" width="${f2((steps[i+1]-steps[i])*k)}" height="1.2" fill="${i%2?C.paper:C.ink}" stroke="${C.ink}" stroke-width="${LW.hair}"/>`; } steps.forEach(v=>s+=text(x+v*k,y+4,v,{class:'m s'})); s+=text(x+tot*k+2,y+4,'m',{class:'s'}); return s; }
  function north(x,y,ang){ const r=5; let s=circle(x,y,r,stroke(C.ink,LW.thin)); const rad=ang*Math.PI/180; const tip=[x+Math.sin(rad)*r*1.25,y-Math.cos(rad)*r*1.25]; const l=[x+Math.sin(rad+2.6)*r*0.6,y-Math.cos(rad+2.6)*r*0.6], rr=[x+Math.sin(rad-2.6)*r*0.6,y-Math.cos(rad-2.6)*r*0.6]; s+=poly([tip,l,[x,y],rr],{fill:C.ink}); s+=text(x,y+r+3,'MODEL +Y',{class:'m s'}); s+=text(x,y+r+5.4,'TRUE N TBC',{class:'m s'}); return s; }
  const files = {};
  const isCut = re => re;

  // ---------- PLAN L00 (rotated) ----------
  function planL00(k, name){
    const b = [-4.6, -3.6, 89.0, 62.6]; // u=y, v=x
    const pad = [24, 3, 3, 24];
    const V = view(q=>[q[1], q[0]], k, b, pad); let s='';
    const groundSp = sel(/^SPC-SP-/).filter(o=>o.mn[2]<1);
    groundSp.forEach(o=>s+=shape(V,o,{fill:o.n==='SPC-SP-01'?C.paper:C.tone, stroke:'none'}));
    sel(/^ARC-SLAB-/).filter(o=>o.mn[2]<1.2).forEach(o=>s+=shape(V,o,stroke(C.mid,LW.hair)));
    // grids
    Object.entries(GY).forEach(([n,y])=>{ const a=V.P([b[3]+0.6,y]), t=V.P([b[1],y]); s+=line([a[0],a[1]],[t[0],pad[0]-6],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); });
    Object.entries(GX).forEach(([n,x])=>{ const a=V.P([x,b[2]+0.4]), t=V.P([x,b[0]]); s+=line([a[0],a[1]],[pad[3]-6,t[1]],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); });
    s+=shapes(V,sel(/^SEAT-C/),{fill:C.light}); s+=shapes(V,sel(/^SEAT-H/),{fill:C.mid});
    s+=shapes(V,sel(/^SEAT-K/),stroke(C.grey,LW.hair));
    s+=shapes(V,sel(/^ACC-(WCS|REFUGE)/).filter(o=>o.mn[2]<4),stroke(C.accent,LW.thin));
    sel(/^(ARC-STAIR|ARC-RAMP)/).forEach(o=>{ s+=shape(V,o,{fill:C.paper,stroke:C.ink,'stroke-width':LW.thin}); });
    sel(/^ARC-STAIR/).forEach(o=>{ const st=props['OB:'+o.n]||{}; const n=st.Risers||6; const P0=V.P(o.mn), P1=V.P(o.mx); const horiz = Math.abs(P1[0]-P0[0]) > Math.abs(P1[1]-P0[1]); const L = (o.mx[1]-o.mn[1])>(o.mx[0]-o.mn[0]); for(let i=1;i<Math.min(n,28);i++){ const t=i/Math.min(n,28); if(L){ const y=o.mn[1]+(o.mx[1]-o.mn[1])*t; s+=line(V.P([o.mn[0],y]),V.P([o.mx[0],y]),stroke(C.grey,0.09)); } else { const x=o.mn[0]+(o.mx[0]-o.mn[0])*t; s+=line(V.P([x,o.mn[1]]),V.P([x,o.mx[1]]),stroke(C.grey,0.09)); } } });
    s+=shape(V,by['ARC-PLATFORM'],{fill:C.paper,stroke:C.ink,'stroke-width':LW.med});
    s+=shape(V,by['ARC-PULPIT'],{fill:C.ink});
    sel(/^ARC-WALL-/).filter(o=>o.mn[2]<1).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    sel(/^ENV-WALL-/).filter(o=>o.mn[2]<1).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    sel(/^STR-COL-/).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    s+=shape(V,by['ENV-CANOPY-ENTRANCE'],stroke(C.ink,LW.hair,{'stroke-dasharray':DASH.hidden}));
    const doors = sel(/^DR-/).filter(o=>o.mn[2]<1.5);
    doors.forEach(o=>s+=shape(V,o,{fill:C.paper,stroke:C.ink,'stroke-width':LW.hair}));
    const ext = sel(/^DR-EXT-/).sort((a,b)=>a.n.localeCompare(b.n)); const cx=29.5, cy=44;
    ext.forEach((o,i)=>{ const mx=(o.mn[0]+o.mx[0])/2, my=(o.mn[1]+o.mx[1])/2; const p=V.P([mx,my]); let dx=mx-cx, dy=my-cy; const pdx=dy, pdy=dx; const L=Math.hypot(pdx,pdy)||1; const q=[p[0]+pdx/L*5.5, p[1]+pdy/L*5.5]; s+=line(p,[p[0]+pdx/L*3.2,p[1]+pdy/L*3.2],stroke(C.accent,LW.thin)); s+=text(q[0],q[1],'X'+String(i+1).padStart(2,'0'),{class:'c s b h',style:`fill:${C.accent}`}); });
    groundSp.forEach(o=>{ const c=V.P([(o.mn[0]+o.mx[0])/2,(o.mn[1]+o.mx[1])/2]); const code=o.n.replace('SPC-SP-','SP-'); const big=(o.mx[0]-o.mn[0])*(o.mx[1]-o.mn[1])>60; let at=c; if(o.n==='SPC-SP-01') at=V.P([29.5,50.5]); if(o.n==='SPC-SP-02') at=V.P([29.5,70.5]); s+=text(at[0],at[1],code,{class:(big?'':'s ')+'c b h'}); });
    s+=text(...V.P([29.5,67.2]), 'PLATFORM +0.900', {class:'c s h'});
    // bubbles + dims
    const ys=Object.entries(GY), xs=Object.entries(GX);
    ys.forEach(([n,y])=>{ const p=V.P([b[1],y]); s+=bubble(p[0], pad[0]-9.5, n); });
    xs.forEach(([n,x])=>{ const p=V.P([x,b[0]]); s+=bubble(pad[3]-9.5, p[1], n); });
    const yl=ys.map(([n,y])=>[V.P([0,y])[0], y]); s+=dimH(yl, pad[0]-1.5, null); s+=dimH([yl[0],yl[yl.length-1]], pad[0]-5, null, {force:1});
    const xl=xs.map(([n,x])=>[V.P([x,0])[1], x]); s+=dimV(xl, pad[3]-1.5, null); s+=dimV([xl[0],xl[xl.length-1]], pad[3]-5, null);
    // section markers
    const secA = (x, lab) => { const p1=V.P([x,b[1]]), p2=V.P([x,b[3]]); return ''; };
    const yA = V.P([29.5,0])[1]; const xR = V.w-2;
    s+=line([pad[3]-2, yA],[pad[3]+3.5,yA],stroke(C.ink,LW.heavy)); s+=line([V.w-7,yA],[V.w-1.5,yA],stroke(C.ink,LW.heavy));
    const xB = V.P([0,38.5])[0]; s+=line([xB,V.h-6],[xB,V.h-0.5],stroke(C.ink,LW.heavy));
    files[name] = head(V.w,V.h)+s+'</svg>';
    return {w:V.w,h:V.h};
  }
  const planInfo = planL00(1000/300, 'A-100_plan_L00.svg');

  // ---------- SEATING (unrotated, hall crop) ----------
  function seating(k, name){
    const b=[-1.5,-83,60.5,-13.5]; const pad=[12,3,3,12]; const V=view(q=>[q[0],-q[1]],k,b,pad); let s='';
    s+=shape(V,by['SPC-SP-01'],{fill:C.paper,stroke:'none'});
    ['SPC-SP-02','SPC-SP-03','SPC-SP-04','SPC-SP-02B','SPC-SP-AMB-E','SPC-SP-AMB-W'].forEach(n=>s+=shape(V,by[n],{fill:C.tone}));
    s+=shape(V,by['ARC-SLAB-CROSS-AISLE'],{fill:'#f3f1ec',stroke:C.mid,'stroke-width':LW.hair});
    s+=shape(V,by['ARC-SLAB-REAR-PLATFORM'],{fill:'#f3f1ec',stroke:C.mid,'stroke-width':LW.hair});
    Object.entries(GX).forEach(([n,x])=>{ s+=line([V.P([x,0])[0],pad[0]-6],[V.P([x,0])[0],V.h-2],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(V.P([x,0])[0],pad[0]-9,n,2.8); });
    Object.entries(GY).filter(([n,y])=>y>=14&&y<=82).forEach(([n,y])=>{ const yy=V.P([0,y])[1]; s+=line([pad[3]-6,yy],[V.w-2,yy],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(pad[3]-9,yy,n,2.8); });
    const clipId='hallclip'; const hall=by['SPC-SP-01']; const h0=V.P([hall.mn[0],hall.mx[1]]), h1=V.P([hall.mx[0],hall.mn[1]]);
    s+=`<clipPath id="${clipId}"><rect x="${f2(h0[0])}" y="${f2(h0[1])}" width="${f2(h1[0]-h0[0])}" height="${f2(h1[1]-h0[1])}"/></clipPath>`;
    const cen=V.P([29.5,64]); let arcs=`<g clip-path="url(#${clipId})">`;
    [10,20,30,40].forEach(r=>arcs+=circle(cen[0],cen[1],r*k,stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.unresolved})));
    arcs+=circle(cen[0],cen[1],scene.max_viewing_distance_to_platform_edge*k,stroke(C.accent,LW.thin,{'stroke-dasharray':'1.2 0.8'}));
    arcs+='</g>'; s+=arcs;
    const blocks={}; const fillB=['#8e98a3','#b8bfc6'];
    sel(/^SEAT-C/).forEach(o=>{ const bl=+o.n.match(/-B(\d)-/)[1]; (blocks[bl]=blocks[bl]||[]).push(o); });
    Object.entries(blocks).forEach(([bl,arr])=>s+=shapes(V,arr,{fill:fillB[bl%2]}));
    s+=shapes(V,sel(/^SEAT-H/),{fill:C.grey});
    s+=shapes(V,sel(/^SEAT-K/),{fill:C.paper,stroke:C.ink,'stroke-width':0.1});
    s+=shapes(V,sel(/^ACC-WCS/),{fill:C.paper,stroke:C.accent,'stroke-width':LW.thin});
    s+=shape(V,by['ARC-PLATFORM'],{fill:C.paper,stroke:C.ink,'stroke-width':LW.med}); s+=shape(V,by['ARC-PULPIT'],{fill:C.ink});
    sel(/^ENV-WALL-(HALL|STAGE|GABLE)/).filter(o=>o.mn[2]<1).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    sel(/^STR-COL-/).filter(o=>o.mn[1]>14&&o.mx[1]<82).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    Object.entries(blocks).forEach(([bl,arr0])=>{ const arr=arr0.filter(o=>/-R(2[4-6])-/.test(o.n)); if(!arr.length) return; const mx=arr.reduce((a,o)=>a+(o.mn[0]+o.mx[0])/2,0)/arr.length, my=arr.reduce((a,o)=>a+(o.mn[1]+o.mx[1])/2,0)/arr.length; const p=V.P([mx,my]); s+=text(p[0],p[1],'B'+bl,{class:'c l b h'}); });
    const rows={}; sel(/^SEAT-C/).forEach(o=>{const r=+o.n.match(/-R(\d+)-/)[1]; const y=(o.mn[1]+o.mx[1])/2; const x=o.mn[0]; if(!rows[r]||x<rows[r].x) rows[r]={x,y};});
    [1,10,20,30,41].forEach(r=>{ const p=V.P([rows[r].x,rows[r].y]); s+=text(p[0]-1.2,p[1]+0.6,'R'+String(r).padStart(2,'0'),{class:'s e h'}); });
    [10,20,30,40].forEach(r=>{ const p=[cen[0]+r*k*Math.sin(0.38), cen[1]+r*k*Math.cos(0.38)]; s+=text(p[0],p[1],r+' m',{class:'s c h',style:`fill:${C.grey}`}); });
    const pm=[cen[0]-scene.max_viewing_distance_to_platform_edge*k*Math.sin(0.12), cen[1]+scene.max_viewing_distance_to_platform_edge*k*Math.cos(0.12)];
    s+=text(pm[0],pm[1]-1.6,'45.45 m max.',{class:'s c h',style:`fill:${C.accent}`});
    s+=circle(cen[0],cen[1],0.7,{fill:C.accent}); s+=text(cen[0]+1.5,cen[1]-1.2,'SO',{class:'s b h',style:`fill:${C.accent}`});
    s+=text(...V.P([29.5,69]),'PLATFORM',{class:'c s b h'});
    s+=text(...V.P([12,73]),'CHOIR W',{class:'c s h'}); s+=text(...V.P([47,73]),'CHOIR E',{class:'c s h'});
    s+=text(...V.P([29.5,41]),'CROSS AISLE +1.150',{class:'c s h'});
    s+=text(...V.P([29.5,17.15]),'REAR PLATFORM +4.600',{class:'c s h'});
    files[name]=head(V.w,V.h)+s+'</svg>'; return {w:V.w,h:V.h};
  }
  const seatInfo = seating(2, 'A-110_seating.svg');

  // ---------- ROOF FRAMING (rotated) ----------
  function roof(k,name){
    const b=[-4.6,-1.2,89.0,60.2]; const pad=[22,3,3,22]; const V=view(q=>[q[1],q[0]],k,b,pad); let s='';
    sel(/^ENV-ROOF/).forEach(o=>s+=shape(V,o,{fill:o.n.includes('HALL')?C.paper:C.tone,stroke:C.mid,'stroke-width':LW.hair}));
    Object.entries(GY).forEach(([n,y])=>{ const x=V.P([0,y])[0]; s+=line([x,pad[0]-6],[x,V.h-2],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(x,pad[0]-9.5,n); });
    Object.entries(GX).forEach(([n,xx])=>{ const y=V.P([xx,0])[1]; s+=line([pad[3]-6,y],[V.w-2,y],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(pad[3]-9.5,y,n); });
    const L=(o,c,w,ex)=>line(V.P(o.a),V.P(o.b),stroke(c,w,ex));
    sel(/^STR-BRACE-ROOF/).forEach(o=>s+=L(o,C.accent,LW.thin));
    sel(/^STR-PURLIN/).forEach(o=>s+=L(o,C.grey,LW.thin));
    sel(/^STR-BEAM/).forEach(o=>s+=L(o,C.ink,LW.med));
    sel(/^STR-TRUSS-T\d+-TC/).forEach(o=>s+=L(o,C.ink,LW.heavy+0.15));
    sel(/^SRV-GUTTER/).forEach(o=>s+=shape(V,o,stroke(C.ink,LW.hair,{'stroke-dasharray':DASH.hidden})));
    sel(/^SRV-DOWNPIPE/).forEach(o=>{const p=V.P([(o.mn[0]+o.mx[0])/2,(o.mn[1]+o.mx[1])/2]); s+=circle(p[0],p[1],0.7,{fill:C.paper,stroke:C.ink,'stroke-width':LW.hair});});
    sel(/^STR-COL-/).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    const tr={}; sel(/^STR-TRUSS-T\d+-TC/).forEach(o=>{const t=o.n.split('-')[2]; tr[t]=o.a[1];});
    Object.entries(tr).forEach(([t,y])=>{ const p=V.P([29.5,y]); s+=`<rect x="${f2(p[0]-3.2)}" y="${f2(p[1]-1.6)}" width="6.4" height="3.2" fill="${C.paper}" stroke="${C.ink}" stroke-width="${LW.thin}"/>`+text(p[0],p[1]+0.05,t,{class:'c s b'}); });
    const yl=Object.entries(GY).map(([n,y])=>[V.P([0,y])[0],y]); s+=dimH(yl,pad[0]-2,null);
    const xl=Object.entries(GX).map(([n,x])=>[V.P([x,0])[1],x]); s+=dimV(xl,pad[3]-2,null);
    files[name]=head(V.w,V.h)+s+'</svg>'; return {w:V.w,h:V.h};
  }
  const roofInfo=roof(2.5,'S-200_roof_framing.svg');

  // ---------- TRANSVERSE SECTION through T6 ----------
  function transverse(k,name,yCut){
    const b=[-4,-19.2,63,1.8]; const pad=[6,26,14,4]; const V=view(q=>[q[0],-q[2]],k,b,pad); let s='';
    const lv=Object.fromEntries(Object.entries({L00:0,L01:1.15,L02:4.6,L03:4.3,L04:7.65,L05:13.6}));
    s+=shape(V,by['ENV-WALL-GABLE-STAGE'],stroke(C.mid,LW.hair));
    sel(/^SRV-AV-SCREEN-MAIN/).forEach(o=>s+=shape(V,o,stroke(C.mid,LW.hair)));
    s+=shape(V,by['ARC-PLATFORM'],stroke(C.mid,LW.hair));
    const cutAt=o=>o.mn[1]<=yCut+0.5&&o.mx[1]>=yCut-0.5;
    sel(/^ENV-ROOF/).filter(cutAt).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    sel(/^ENV-WALL/).filter(cutAt).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    sel(/^ARC-RAKE-R\d+-(TREAD|AISLE)/).filter(o=>o.mn[1]<=yCut&&o.mx[1]>=yCut).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    sel(/^ARC-SLAB/).filter(cutAt).forEach(o=>s+=shape(V,o,{fill:C.ink}));
    const t='T'+Object.entries(GY).find(([n,y])=>y===yCut)[0];
    sel(new RegExp('^STR-FTG-[A-H]'+t.slice(1)+'$')).forEach(o=>s+=shape(V,o,stroke(C.ink,LW.thin,{'stroke-dasharray':DASH.assumed})));
    sel(new RegExp('^STR-COL-[A-H]'+t.slice(1)+'$')).forEach(o=>s+=shape(V,o,{fill:C.light,stroke:C.ink,'stroke-width':LW.thin}));
    sel(new RegExp('^STR-KNEE-[BG]'+t.slice(1)+'$')).forEach(o=>s+=line(V.P(o.a),V.P(o.b),stroke(C.ink,LW.heavy)));
    sel(new RegExp('^STR-BEAM-.*-'+t.slice(1)+'-')).forEach(o=>s+=shape(V,o,{fill:C.grey}));
    sel(new RegExp('^STR-TRUSS-'+t+'-')).forEach(o=>s+=line(V.P(o.a),V.P(o.b),stroke(C.ink,/-(TC|BC)/.test(o.n)?LW.heavy+0.1:LW.thin,{'stroke-linecap':'round'})));
    sel(new RegExp('^STR-PURLIN-'+t.slice(1)+'-')).forEach(o=>{const p=V.P([(o.mn[0]+o.mx[0])/2,0,o.mx[2]]); s+=`<rect x="${f2(p[0]-0.45)}" y="${f2(p[1]-0.45)}" width="0.9" height="0.9" fill="${C.ink}"/>`;});
    const g0=V.P([-4,0,0]), g1=V.P([63,0,0]); s+=line(g0,g1,stroke(C.ink,LW.cut));
    Object.entries(lv).forEach(([n,z])=>{ const p0=V.P([-4,0,z]), p1=V.P([63,0,z]); s+=line(p0,[p1[0]+1,p1[1]],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.hidden})); s+=level(p1[0]+3,p1[1],n+' '+(z>=0?'+':'')+z.toFixed(3)); });
    const rid=V.P([29.5,0,18.4]); s+=level(rid[0],rid[1]-0.2,'RIDGE +18.400'.replace('RIDGE','TOS ROOF'));
    Object.entries(GX).forEach(([n,x])=>{ const p=V.P([x,0,0]); s+=line([p[0],p[1]+1],[p[0],V.h-9],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(p[0],V.h-5.5,n,2.8); });
    const xl=Object.entries(GX).map(([n,x])=>[V.P([x,0,0])[0],x]); s+=dimH(xl,V.P([0,0,-1.5])[1]+3.5,null);
    // member tags
    const tag=(o,lab,dx,dy)=>{ const m=V.P([(o.a[0]+o.b[0])/2,0,(o.a[2]+o.b[2])/2]); const q=[m[0]+dx,m[1]+dy]; return line(m,q,stroke(C.accent,LW.hair))+circle(m[0],m[1],0.45,{fill:C.accent})+text(q[0],q[1]+(dy<0?-0.8:2.2),lab,{class:'s m b',style:`fill:${C.accent}`}); };
    const tg=n=>by['STR-TRUSS-'+t+'-'+n];
    if(tg('TC06')) s+=tag(tg('TC06'),t+'-TC',0,-7);
    if(tg('BC05')) s+=tag(tg('BC05'),t+'-BC',0,6);
    const dd=sel(new RegExp('^STR-TRUSS-'+t+'-D'))[3]; if(dd) s+=tag(dd,t+'-D',-6,6);
    const vv=sel(new RegExp('^STR-TRUSS-'+t+'-V'))[7]; if(vv) s+=tag(vv,t+'-V',5,6);
    files[name]=head(V.w,V.h)+s+'</svg>'; return {w:V.w,h:V.h};
  }
  const trInfo=transverse(1000/300,'S-300_section_T6.svg',38.5);
  const trBig=transverse(4,'S-301_truss_T6_1-250.svg',38.5);
  const trSmall=transverse(2,'A-302_section_BB_1-500.svg',38.5);

  // ---------- LONGITUDINAL SECTION A-A ----------
  function longSection(k,name,xCut){
    const b=[-5.5,-19.2,90,1.8]; const pad=[5,24,12,4]; const V=view(q=>[q[1],-q[2]],k,b,pad); let s='';
    const beyond=O.filter(o=>o.mx[0]<xCut&&o.mn[0]>4&&/^(STR-COL-B|STR-TRUSS-T\d+-(TC|BC)|SRV-AV-SCREEN|ARC-BOOTH|ARC-STAIR-FOYER-W|SEAT-C|SEAT-H|ARC-RAKE)/.test(o.n));
    s+=shape(V,by['ENV-WALL-HALL-W'],stroke(C.mid,LW.hair));
    s+=shapes(V,beyond.filter(o=>o.n.startsWith('SEAT')),{fill:C.light}); s+=shapes(V,beyond.filter(o=>!o.n.startsWith('SEAT')),stroke(C.mid,LW.hair));
    const cut=O.filter(o=>o.mn[0]<=xCut&&o.mx[0]>=xCut&&/^(ENV-|ARC-SLAB|ARC-RAKE|ARC-PLATFORM|ARC-BOOTH|ARC-WALL|STR-TRUSS|STR-BEAM)/.test(o.n));
    cut.forEach(o=>{ const near=(o.v||[]).filter(q=>Math.abs(q[0]-xCut)<0.3); const P=near.length>=3?near:pts3(o); s+=poly(hull(P.map(V.P)),{fill:C.ink}); });
    const g0=V.P([0,-5.5,0]), g1=V.P([0,90,0]); s+=line(g0,g1,stroke(C.ink,LW.cut));
    Object.entries({L00:0,L01:1.15,L02:4.6,L03:4.3,L04:7.65,L05:13.6}).forEach(([n,z])=>{ const p0=V.P([0,-5.5,z]), p1=V.P([0,90,z]); s+=line(p0,[p1[0]+1,p1[1]],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.hidden})); s+=level(p1[0]+3,p1[1]+(n==='L03'?2.2:0),n+' '+(z>=0?'+':'')+z.toFixed(3)); });
    Object.entries(GY).forEach(([n,y])=>{ const p=V.P([0,y,0]); s+=line([p[0],p[1]+1],[p[0],V.h-8.5],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(p[0],V.h-5.2,n,2.6); });
    files[name]=head(V.w,V.h)+s+'</svg>'; return {w:V.w,h:V.h};
  }
  const lsInfo=longSection(2,'A-301_section_AA.svg',29.5);
  const lsBig=longSection(1000/300,'A-302_section_AA_1-300.svg',29.5);

  // ---------- ELEVATIONS ----------
  function elevation(k,name,dir){
    const cfg={S:{proj:q=>[q[0],-q[2]],depth:o=>-o.mn[1],b:[-4,-19.5,63,1]}, N:{proj:q=>[-q[0],-q[2]],depth:o=>o.mx[1],b:[-63,-19.5,4,1]}, E:{proj:q=>[q[1],-q[2]],depth:o=>o.mx[0],b:[-5.5,-19.5,89.5,1]}, W:{proj:q=>[-q[1],-q[2]],depth:o=>-o.mn[0],b:[-89.5,-19.5,5.5,1]}}[dir];
    const pad=[3,3,10,3]; const V=view(cfg.proj,k,cfg.b,pad); let s='';
    const list=O.filter(o=>/^(ENV-|STR-COL-CANOPY|DR-EXT|ARC-STAIR-EXT|ARC-RAMP-EXT|WN-)/.test(o.n));
    list.sort((a,b)=>cfg.depth(b)-cfg.depth(a));
    list.forEach(o=>s+=shape(V,o,{fill:o.n.startsWith('DR-')?C.tone:(o.n.startsWith('ENV-ROOF')?C.light:C.paper),stroke:C.ink,'stroke-width':o.n.startsWith('ENV-WALL-EXT')||o.n.startsWith('ENV-ROOF')?LW.med:LW.thin}));
    const g0=V.P([-6,-6,0]), g1=V.P([66,96,0]); s+=line([Math.min(g0[0],g1[0]),g0[1]],[Math.max(g0[0],g1[0]),g0[1]],stroke(C.ink,LW.cut));
    const grids = (dir==='S'||dir==='N')?Object.entries(GX).map(([n,x])=>[n,[x,0,0]]):Object.entries(GY).map(([n,y])=>[n,[0,y,0]]);
    grids.forEach(([n,q])=>{ const p=V.P(q); s+=line([p[0],p[1]+0.8],[p[0],V.h-6.2],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(p[0],V.h-3.4,n,2.4); });
    files[name]=head(V.w,V.h)+s+'</svg>'; return {w:V.w,h:V.h};
  }
  const elev={S:elevation(2,'A-200_elev_south.svg','S'),N:elevation(2,'A-201_elev_north.svg','N'),E:elevation(2,'A-202_elev_east.svg','E'),W:elevation(2,'A-203_elev_west.svg','W')};

  // ---------- STRUCTURAL AXONOMETRIC ----------
  function axo(k,name,mode){
    const r2=Math.SQRT2, r6=Math.sqrt(6);
    const proj=q=>[(q[0]-q[1])/r2, -(q[0]+q[1]+2*q[2])/r6];
    let bb=[1e9,1e9,-1e9,-1e9]; O.filter(o=>/^(STR|ENV)-/.test(o.n)).forEach(o=>pts3(o).forEach(q=>{const [u,v]=proj(q); bb=[Math.min(bb[0],u),Math.min(bb[1],v),Math.max(bb[2],u),Math.max(bb[3],v)];}));
    const pad=mode==='cover'?[6,6,6,6]:[14,14,14,14]; const V=view(proj,k,bb,pad);
    const depth=q=>q[0]+q[1]-q[2]; const items=[];
    const ink=mode==='cover'?C.coverInk:C.ink, halo=mode==='cover'?C.coverBg:C.paper;
    const addLine=(o,w,c,dash)=>{ const a=V.P(o.a), b=V.P(o.b); const d=(depth(o.a)+depth(o.b))/2; items.push({d, svg: line(a,b,{stroke:halo,'stroke-width':w+0.5,'stroke-linecap':'round'})+line(a,b,stroke(c||ink,w,Object.assign({'stroke-linecap':'round'},dash?{'stroke-dasharray':dash}:{})))}); };
    const addShape=(o,a,dOff)=>{ const P=pts3(o); const d=P.reduce((s,q)=>s+depth(q),0)/P.length+(dOff||0); items.push({d, svg: shape(V,o,a)}); };
    if(mode==='cover'){
      O.filter(o=>/^(ENV-WALL|ENV-ROOF-(AMB|BOH|FOYER)|ENV-CANOPY|ARC-SLAB-(FOYER|BOH|HALL-FRONT|CROSS|REAR|RAKE|UPPER)|ARC-PLATFORM)/.test(o.n)).filter(o=>!(o.n.startsWith('ENV-WALL')&&o.mn[0]>50&&o.mn[1]>15&&o.mx[1]<81)).forEach(o=>addShape(o,{fill:C.coverFill,stroke:ink,'stroke-width':0.16,'stroke-linejoin':'round'}));
      sel(/^ENV-ROOF-HALL-W/).forEach(o=>addShape(o,{fill:C.coverFill,stroke:ink,'stroke-width':0.2}, -30));
      { const rr=sel(/^ARC-RAKE/); const d=rr.reduce((a,o)=>a+o.mn[0]+o.mn[1]-o.mn[2],0)/rr.length+2; items.push({d, svg: shapes(V,rr,{fill:C.coverFill,stroke:ink,'stroke-width':0.08})}); }
      { const ss=sel(/^(SEAT-C|SEAT-H)/); const d=ss.reduce((a,o)=>a+o.mn[0]+o.mn[1]-o.mn[2],0)/ss.length; items.push({d, svg: shapes(V,ss,{fill:C.coverSeat})}); }
    }
    sel(/^STR-FTG/).forEach(o=>{ if(mode!=='cover') addShape(o,{fill:'none',stroke:C.grey,'stroke-width':LW.hair,'stroke-dasharray':DASH.assumed}); });
    sel(/^STR-COL/).forEach(o=>addLine(o,mode==='cover'?0.3:LW.heavy));
    sel(/^STR-TRUSS-T\d+-(TC|BC)/).forEach(o=>addLine(o,mode==='cover'?0.22:LW.med+0.05));
    sel(/^STR-TRUSS-T\d+-(V|D)/).forEach(o=>addLine(o,mode==='cover'?0.1:LW.hair));
    sel(/^STR-PURLIN/).forEach(o=>addLine(o,mode==='cover'?0.1:LW.hair, mode==='cover'?null:C.grey));
    sel(/^STR-BRACE/).forEach(o=>addLine(o,mode==='cover'?0.1:LW.thin, mode==='cover'?C.coverAccent:C.accent));
    sel(/^(STR-BEAM|STR-KNEE|STR-STRUT)/).forEach(o=>addLine(o,mode==='cover'?0.18:LW.thin+0.04));
    items.sort((a,b)=>b.d-a.d);
    let s=items.map(i=>i.svg).join('');
    if(mode!=='cover'){
      Object.entries(GX).forEach(([n,x])=>{ const p=V.P([x,-7,0]); const q=V.P([x,-1.5,0]); s+=line(p,q,stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(p[0],p[1],n,2.4); });
      Object.entries(GY).forEach(([n,y])=>{ const p=V.P([-7,y,0]); const q=V.P([-1.5,y,0]); s+=line(p,q,stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=bubble(p[0],p[1],n,2.4); });
      const mid=o=>[(o.a[0]+o.b[0])/2,(o.a[1]+o.b[1])/2,(o.a[2]+o.b[2])/2];
      const call=[ [1,by['STR-COL-H4'].a.map((v,i)=>i===2?7:v),[12,10]], [2,by['STR-TRUSS-T8-TC10'].b,[-6,-14]], [3,mid(by['STR-PURLIN-9-10-P07']),[10,-12]], [4,mid(by['STR-BRACE-ROOF-10-11-03a']),[-14,-10]], [5,mid(by['STR-KNEE-G7']),[16,-4]], [6,mid(by['STR-FTG-H2']),[10,10]], [7,mid(by['STR-STRUT-GABLE-11-DE']),[-12,-8]], [8,mid(by['STR-BEAM-AMBEDGE-H-6-7']),[14,8]], [9,by['STR-COL-CANOPY-E'].mn.map((v,i)=>i===2?1.5:(by['STR-COL-CANOPY-E'].mn[i]+by['STR-COL-CANOPY-E'].mx[i])/2),[-6,12]] ];
      call.forEach(([n,q,off])=>{ const p=V.P(q); const t=[p[0]+off[0],p[1]+off[1]]; s+=line(p,t,stroke(C.accent,LW.thin)); s+=circle(p[0],p[1],0.55,{fill:C.accent}); s+=circle(t[0],t[1],2.6,{fill:C.paper,stroke:C.accent,'stroke-width':LW.thin}); s+=text(t[0],t[1]+0.05,n,{class:'c b',style:`fill:${C.accent}`}); });
    }
    const bg = mode==='cover'?`<rect width="100%" height="100%" fill="${C.coverBg}"/>`:'';
    files[name]=head(V.w,V.h,mode==='cover'?C.coverBg:C.paper)+s+'</svg>'; return {w:V.w,h:V.h};
  }
  const axoInfo=axo(2.7,'S-100_structural_axo.svg','tech');
  C.coverBg='#1f2022'; C.coverInk='#e9e4da'; C.coverFill='#26282b'; C.coverSeat='#5f7796'; C.coverAccent='#b98a5c';
  const coverInfo=axo(3.2,'X-000_cover_cutaway_axo.svg','cover');
  // ---------- DRAWING LANGUAGE LEGEND ----------
  (function legend(){ let s=''; const W=330,H=150; const col=[6,116,226]; let y;
    const hd=(x,y,t)=>text(x,y,t,{class:'b'})+line([x,y+1.4],[x+100,y+1.4],stroke(C.ink,LW.hair));
    y=8; s+=hd(col[0],y,'LINE HIERARCHY  (mm at print scale)'); [['Cut / profile','cut'],['Primary structure','heavy'],['Secondary / outline','med'],['Tertiary / furniture','thin'],['Grid, dimension, hatch','hair']].forEach(([t,k],i)=>{const yy=y+7+i*6; s+=line([col[0],yy],[col[0]+40,yy],stroke(C.ink,LW[k])); s+=text(col[0]+45,yy+0.7,t,{class:'s'}); s+=text(col[0]+100,yy+0.7,LW[k].toFixed(2),{class:'s e'});});
    y=52; s+=hd(col[0],y,'LINE TYPES  (status of geometry)'); [['Model geometry — solid',null,C.ink],['Assumption / reference only — dashed',DASH.assumed,C.ink],['Unresolved / to be confirmed — dotted',DASH.unresolved,C.ink],['Grid line — chain',DASH.grid,C.grey],['Annotation / callout — accent',null,C.accent]].forEach(([t,d,c],i)=>{const yy=y+7+i*6; s+=line([col[0],yy],[col[0]+40,yy],stroke(c,LW.thin,d?{'stroke-dasharray':d}:{})); s+=text(col[0]+45,yy+0.7,t,{class:'s'});});
    y=96; s+=hd(col[0],y,'FILLS'); [['Cut element (poché)',C.ink],['Seating',C.light],['Space allowance',C.tone],['Choir seating',C.mid]].forEach(([t,c],i)=>{const yy=y+5+i*6; s+=`<rect x="${col[0]}" y="${yy}" width="10" height="4" fill="${c}" stroke="${C.ink}" stroke-width="0.1"/>`; s+=text(col[0]+14,yy+2.8,t,{class:'s'});});
    y=8; s+=hd(col[1],y,'REFERENCE SYMBOLS');
    s+=bubble(col[1]+5,y+10,'B'); s+=text(col[1]+12,y+10.7,'Grid bubble  Ø6.4 · lettered A–H (model X)',{class:'s'});
    s+=bubble(col[1]+5,y+19,'6'); s+=text(col[1]+12,y+19.7,'Grid bubble · numbered 1–12 (model Y)',{class:'s'});
    { const x=col[1]+5, yy=y+30; s+=circle(x,yy,3.6,{fill:C.paper,stroke:C.ink,'stroke-width':LW.thin}); s+=line([x-3.6,yy],[x+3.6,yy],stroke(C.ink,LW.hair)); s+=text(x,yy-1.5,'A',{class:'c s b'}); s+=text(x,yy+1.7,'A-301',{class:'c s'}); s+=poly([[x+3.6,yy-1.6],[x+6.2,yy],[x+3.6,yy+1.6]],{fill:C.ink}); s+=text(col[1]+12,yy+0.7,'Section marker · section / sheet',{class:'s'}); }
    { const x=col[1]+5, yy=y+41; s+=circle(x,yy,3.2,{fill:C.paper,stroke:C.ink,'stroke-width':LW.thin}); s+=poly([[x-1.6,yy-2.7],[x,yy-5.2],[x+1.6,yy-2.7]],{fill:C.ink}); s+=text(x,yy,'A-200',{class:'c s'}); s+=text(col[1]+12,yy+0.7,'Elevation marker · drawing no.',{class:'s'}); }
    { const x=col[1]+5, yy=y+52; s+=circle(x,yy,3.2,{fill:C.paper,stroke:C.ink,'stroke-width':LW.thin}); s+=line([x-3.2,yy],[x+3.2,yy],stroke(C.ink,LW.hair)); s+=text(x,yy-1.4,'3',{class:'c s b'}); s+=text(x,yy+1.6,'S-301',{class:'c s'}); s+=text(col[1]+12,yy+0.7,'Detail reference · detail / sheet',{class:'s'}); }
    s+=level(col[1]+5,y+62,'L02 +4.600'); s+=text(col[1]+40,y+61.5,'Level datum',{class:'s'});
    { const x=col[1]+3, yy=y+70; s+=line([x,yy],[x+8,yy-4],stroke(C.accent,LW.thin)); s+=circle(x,yy,0.55,{fill:C.accent}); s+=circle(x+10.6,yy-4,2.6,{fill:C.paper,stroke:C.accent,'stroke-width':LW.thin}); s+=text(x+10.6,yy-3.95,'4',{class:'c b',style:'fill:'+C.accent}); s+=text(col[1]+18,yy-3.3,'Numbered callout · keyed to page text',{class:'s'}); }
    { const x=col[1]+2, yy=y+80; s+=`<rect x="${x}" y="${yy-1.6}" width="9" height="3.2" fill="${C.paper}" stroke="${C.ink}" stroke-width="${LW.thin}"/>`+text(x+4.5,yy+0.05,'T6',{class:'c s b'}); s+=text(col[1]+14,yy+0.7,'Member identifier · assembly tag',{class:'s'}); }
    { const x=col[1]+2, yy=y+88; s+=line([x,yy],[x+6,yy-4],stroke(C.accent,LW.hair)); s+=circle(x,yy,0.45,{fill:C.accent}); s+=text(x+7,yy-4.8,'T6-TC',{class:'s b',style:'fill:'+C.accent}); s+=text(col[1]+22,yy-3.3,'Member leader · element role',{class:'s'}); }
    y=106; s+=hd(col[1],y,'DIMENSIONS & SCALE'); s+=dimH([[col[1]+4,0],[col[1]+30,8],[col[1]+51,14.5]],y+12,y+20); s+=line([col[1]+4,y+20],[col[1]+51,y+20],stroke(C.grey,LW.hair,{'stroke-dasharray':DASH.grid})); s+=text(col[1]+56,y+12.7,'Millimetres · oblique ticks · text 1.8 mm',{class:'s'});
    s+=scaleBar(col[1]+4,y+28,1.2,[0,5,10,20]); s+=text(col[1]+56,y+29.2,'Scale bar · metres',{class:'s'});
    y=8; s+=hd(col[2],y,'ORIENTATION'); s+=north(col[2]+10,y+14,90); s+=text(col[2]+22,y+12.5,'North arrow points to model +Y.',{class:'s'}); s+=text(col[2]+22,y+15.5,'True north is not defined in the model',{class:'s'}); s+=text(col[2]+22,y+18.5,'and must be set from a site survey.',{class:'s'});
    y=42; s+=hd(col[2],y,'TYPE ON DRAWINGS'); [['Labels, values','2.2 mm · 400'],['Dimension text','1.8 mm · 400'],['Grid bubbles','2.6 mm · 400'],['Identifiers','1.8–2.2 mm · 500']].forEach(([a,b2],i)=>{const yy=y+7+i*5; s+=text(col[2],yy,a,{class:'s'}); s+=text(col[2]+100,yy,b2,{class:'s e'});});
    y=72; s+=hd(col[2],y,'PROVENANCE MARKS'); [['M','Measured from model geometry'],['P','Authored model property'],['E','Derived preliminary estimate'],['C','Requires confirmation'],['X','Excluded']].forEach(([a,b2],i)=>{const yy=y+7+i*5.5; s+=`<rect x="${col[2]}" y="${yy-2.6}" width="3.6" height="3.6" fill="none" stroke="${C.ink}" stroke-width="0.15"/>`+text(col[2]+1.8,yy-0.75,a,{class:'c s b'}); s+=text(col[2]+6,yy,b2,{class:'s'});});
    files['DS-001_drawing_language.svg']=head(W,H)+s+'</svg>'; })();
  return {files, sizes:{plan:planInfo, seating:seatInfo, roof:roofInfo, transverse:trInfo, truss:trBig, long:lsInfo, longBig:lsBig, elev, axo:axoInfo, cover:coverInfo}};
}
if (typeof module !== "undefined") module.exports = { generate };
