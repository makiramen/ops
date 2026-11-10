// Shared renderer for the 5-layer EA drawings (CJ1_2, CJ2_2, CJ3_2). Data comes from window.EA.
(function(){
const D=window.EA;
const stages=D.stages, ux=D.ux, proc=D.proc, contracts=D.contracts, sys=D.sys, pinks=D.pinks, api=D.api, infra=D.infra, apiMap=D.apiMap||null;
const LW=170, CW=265, X0=LW+10, N=stages.length;
const W=X0+N*CW+40;
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")}
function wrap(t,n){const w=t.split(" "),l=[];let c="";for(const x of w){if((c+" "+x).trim().length>n){l.push(c.trim());c=x}else c+=" "+x}if(c.trim())l.push(c.trim());return l}
const sysRows=Math.max(...sys.map(s=>s.length));
if(api) api.forEach(a=>{a[2]=a[2].flatMap(l=>wrap(l,118));});
const maxL=api?Math.max(...api.map(a=>a[2].length)):0;
const API_H=api?(43+maxL*11+16):0;
// endpoint map block height: title 16 + rows*24 + 8
const mapRows=apiMap?Math.max(...apiMap.map(s=>s.length)):0;
const MAP_H=apiMap?(16+mapRows*24+12):0;
const lanes=[["UX Workflow","lane 5 · screens",120],["Business Processes",D.procSub||"lane 4 · Channels and Customer Relationship",D.procH||230],["Service Contracts",D.contractSub||"lane 3 · NONE YET · candidates",D.contractH||300],["System","lane 2 · vendor systems / components · Kobas API v3 endpoints mapped to the layer 3 methods · integration surfaces",8+sysRows*27+12+MAP_H+API_H],["Infrastructure","lane 1 · domain independent",70]];
const laneFill=["#f3f3f1","#ece8f6","#e2f2e4","#fbeadb","#e3eef9"];
let o=[], links=[], y=40;
const cbox={}; // Se id -> {x,y,w,h}
stages.forEach((s,i)=>o.push(`<text class="col" x="${X0+i*CW+CW/2}" y="26" text-anchor="middle">${esc(s)}</text>`));
const laneY=[];
lanes.forEach((L,li)=>{
  const h=L[2]; laneY.push(y);
  o.push(`<rect class="lane" x="0" y="${y}" width="${W}" height="${h}" fill="${laneFill[li]}"/><rect class="lab" x="0" y="${y}" width="${LW}" height="${h}"/>`);
  o.push(`<text class="lt" x="12" y="${y+22}">${L[0]}</text>`); wrap(L[1],28).forEach((t,k)=>o.push(`<text class="ls" x="12" y="${y+38+k*12}">${esc(t)}</text>`));
  for(let i=0;i<N;i++){ const x=X0+i*CW; o.push(`<line x1="${x}" y1="${y}" x2="${x}" y2="${y+h}" stroke="#c8c8c8"/>`);
    if(li==0){ ux[i].forEach((u,k)=>{ const bx=x+8+(k%2)*125, by=y+10+Math.floor(k/2)*36; o.push(`<rect class="scr" x="${bx}" y="${by}" width="118" height="28" rx="3"/><text class="scr-t" x="${bx+59}" y="${by+17}" text-anchor="middle">${esc(u)}</text>`);});}
    if(li==1){ proc[i].forEach((p,k)=>{ const cx=x+CW/2, cy=y+30+k*42; o.push(`<ellipse class="st" cx="${cx}" cy="${cy}" rx="118" ry="17"/><text class="st-i" x="${cx}" y="${cy-3}" text-anchor="middle">${p[0]}</text><text class="st-t" x="${cx}" y="${cy+9}" text-anchor="middle">${esc(p[1])}</text>`);});}
    if(li==2){ let cy=y+10; contracts[i].forEach(c=>{ const hh=18+c[1].length*11+6; const id=c[0].split(" ")[0]; cbox[id]={x:x+8,y:cy,w:CW-16,h:hh}; o.push(`<rect class="sc" x="${x+8}" y="${cy}" width="${CW-16}" height="${hh}" rx="2"/><text class="sc-t" x="${x+14}" y="${cy+13}">«contract» ${esc(c[0])}  (candidate)</text>`); c[1].forEach((op,k)=>o.push(`<text class="sc-o" x="${x+18}" y="${cy+26+k*11}">+ ${esc(op)}</text>`)); cy+=hh+6; });}
    if(li==3){ sys[i].forEach((c,k)=>{ const by=y+8+k*27; const m=c.match(/^(Co\d+|site|Bank)\s(.*)$/); o.push(`<rect class="co" x="${x+8}" y="${by}" width="${CW-16}" height="22" rx="2"/>`); if(m) o.push(`<text class="co-t" x="${x+14}" y="${by+15}">«${m[1]}»</text><text class="co-s" x="${x+52}" y="${by+15}">${esc(m[2])}</text>`); else o.push(`<text class="co-s" x="${x+14}" y="${by+15}">${esc(c)}</text>`);});
      if(apiMap){ const my=y+8+sysRows*27+6; const rows=apiMap[i];
        o.push(`<rect class="map" x="${x+8}" y="${my}" width="${CW-16}" height="${MAP_H-8}" rx="2"/><text class="map-h" x="${x+14}" y="${my+12}">«Co7 API» Kobas API v3 → layer 3 method</text>`);
        rows.forEach((r,k)=>{ const ry=my+16+k*24;
          if(r.none){ o.push(`<text class="map-none" x="${x+14}" y="${ry+10}">${esc(r.none)}</text>`); if(r.note) o.push(`<text class="map-none" x="${x+14}" y="${ry+20}">${esc(r.note)}</text>`); return; }
          o.push(`<text class="map-ep" x="${x+14}" y="${ry+10}">${esc(r.m+" "+r.p)}</text><text class="map-op" x="${x+22}" y="${ry+20}">→ ${esc(r.to+"."+r.op)}</text>`);
          const cb=cbox[r.to]; if(cb){ const sx=x+12, sy=ry+2; const ex=cb.x+10+(k%4)*12, ey=cb.y+cb.h; const midy=(sy+ey)/2;
            links.push(`<path class="maplink" d="M${sx} ${sy} C${sx} ${midy}, ${ex} ${midy}, ${ex} ${ey+2}" marker-end="url(#m)"/>`);} });
      }
    }
  }
  if(li==3 && api){
    const ay=y+8+sysRows*27+8+MAP_H; const aw=(N*CW-24)/api.length;
    o.push(`<text class="api-h" x="${X0+10}" y="${ay+10}">INTEGRATION SURFACES (layer 2 interfaces exposed by the vendor systems; what layer 3 domain services can be built on)</text>`);
    api.forEach((a,k)=>{ const ax=X0+8+k*(aw+4); o.push(`<rect class="api" x="${ax}" y="${ay+16}" width="${aw-4}" height="${API_H-22}" rx="3"/><text class="api-t" x="${ax+8}" y="${ay+30}">«${a[0]}» ${esc(a[1])}</text>`); a[2].forEach((l,j)=>o.push(`<text class="api-s" x="${ax+8}" y="${ay+43+j*11}">${esc(l)}</text>`)); o.push(`<text class="api-u" x="${ax+8}" y="${ay+43+maxL*11+4}">${esc(a[3])}</text>`);});
  }
  if(li==4){ o.push(`<rect class="inf" x="${X0+8}" y="${y+16}" width="${(N-1)*CW-16}" height="34" rx="3"/><text class="inf-t" x="${X0+18}" y="${y+37}">${esc(infra[0])}</text>`);
    o.push(`<rect class="inf" x="${X0+(N-1)*CW+4}" y="${y+16}" width="${CW-12}" height="34" rx="3"/><text class="inf-t" x="${X0+(N-1)*CW+14}" y="${y+37}">${esc(infra[1])}</text>`);}
  y+=h;
});
pinks.forEach((ps,i)=>{ ps.forEach((p,k)=>{ const x=X0+i*CW+8, by=laneY[1]+lanes[1][2]-18-(ps.length-k)*17; o.push(`<rect class="pink" x="${x}" y="${by}" width="${CW-16}" height="15"/><text class="pink-t" x="${x+5}" y="${by+11}">${esc(p)}</text>`);});});
o.push(`<path class="flow" d="M${X0+20} ${laneY[1]+30} H${X0+(N-1)*CW+CW/2-120}" marker-end="url(#a)"/>`);
const svg=document.getElementById("b"); svg.setAttribute("width",W); svg.setAttribute("height",y+10);
svg.innerHTML=`<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10z" fill="#333"/></marker><marker id="m" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8z" fill="#b5651d"/></marker></defs>`+o.join("")+links.join("");
})();
