let scenes=[],idx=0;
const $=id=>document.getElementById(id);
async function init(){scenes=await fetch('/api/scenes').then(r=>r.json()); const sel=$('sceneSelect'); scenes.forEach((s,i)=>{let o=document.createElement('option');o.value=s.id;o.textContent=`Scene ${String(i+1).padStart(2,'0')} · ${s.id}`;sel.appendChild(o)}); sel.onchange=()=>loadScene(sel.selectedIndex); $('prev').onclick=()=>loadScene((idx-1+scenes.length)%scenes.length); $('next').onclick=()=>loadScene((idx+1)%scenes.length); $('predict').onclick=async()=>{let r=await fetch('/api/predict').then(x=>x.json());$('riskScore').textContent=r.score+'%';$('riskLevel').textContent=r.level}; loadScene(0)}
async function loadScene(i){idx=i; $('sceneSelect').selectedIndex=i; const s=scenes[i];$('sceneTitle').textContent=`SCENE ${String(i+1).padStart(2,'0')} · ${s.id}`;$('sceneDate').textContent=` · ${s.date}`;$('status').textContent='Loading terrain…'; try{const d=await fetch('/api/scene/'+encodeURIComponent(s.id)).then(r=>r.json());if(d.error)throw Error(d.error);$('sat').src=d.image;$('overlay').src=d.reference_overlay;$('maskTag').textContent='Reference label';$('status').textContent='Terrain loaded';let m=d.metrics;$('elev').textContent=m.mean_elevation.toFixed(0)+' m';$('slope').textContent=m.mean_slope.toFixed(1)+'°';$('delta').textContent=m.elevation_difference.toFixed(0)+' m';$('area').textContent=(m.area_m2/1e6).toFixed(3)+' km²';$('bpPixels').textContent=d.blueprint.mask_pixels;$('bpDims').textContent=`Footprint: ${d.blueprint.width_px} × ${d.blueprint.length_px} px`;renderTerrain(d.terrain,m.mean_elevation); renderFootprint(d.terrain,d.blueprint)}catch(e){$('status').textContent='DEM unavailable';$('status').style.background='#3a201f';$('status').style.color='#ffb4aa';$('overlay').src='';$('plot').innerHTML=`<div style="padding:35px;color:#a7b8bd">${e.message}<br><br><b>For offline demo:</b> place the matching Copernicus GLO-30 tile inside <code>dem/</code>.</div>`}}
function renderTerrain(t,mean){
  let z=t.z.map(r=>r.map(v=>v===null?null:v));
  let terrain={x:t.x,y:t.y,z,type:'surface',colorscale:[[0,'#071820'],[.45,'#17636b'],[.72,'#71b1a0'],[1,'#d9e7d8']],showscale:false,opacity:.96,contours:{z:{show:true,usecolormap:true}},name:'Copernicus terrain',hoverinfo:'skip'};

  // Highlight the actual lake footprint directly on the DEM.  The lake_z
  // grid contains terrain elevation only where the reference lake mask is 1,
  // so this is a real mask-driven overlay rather than a decorative shape.
  const lake={x:t.x,y:t.y,z:t.lake_z,type:'surface',
    colorscale:[[0,'#00a9ff'],[0.45,'#00cfff'],[1,'#5df6ff']],
    showscale:false,opacity:.72,connectgaps:false,
    name:'Lake footprint',hoverinfo:'skip',
    contours:{z:{show:false}}};

  Plotly.react('plot',[terrain,lake],{paper_bgcolor:'#071218',plot_bgcolor:'#071218',margin:{l:0,r:0,t:5,b:0},
    scene:{xaxis:{title:'Local X',color:'#7e9ba2',gridcolor:'#17323a'},
      yaxis:{title:'Local Y',color:'#7e9ba2',gridcolor:'#17323a'},
      zaxis:{title:'Elevation (m)',color:'#7e9ba2',gridcolor:'#17323a'},
      camera:{eye:{x:1.35,y:1.35,z:.9}},bgcolor:'#071218'},
    legend:{font:{color:'#a9c2c7'},bgcolor:'rgba(7,18,24,.75)',x:.02,y:.98},
    font:{color:'#a9c2c7'}},{responsive:true,displaylogo:false});
}
function renderFootprint(t,bp){
  const outline=t.lake_outline||[];
  const x=outline.map(p=>p[0]), y=outline.map(p=>p[1]), z=outline.map(p=>p[2]);
  // Slightly lift the outline so it remains clearly visible above the terrain mesh.
  const finite=t.z.flat().filter(v=>v!==null && Number.isFinite(v));
  const lift=Math.max(2,(finite.length?Math.max(...finite)-Math.min(...finite):100)*0.004);
  const line={x,y,z:z.map(v=>v+lift),type:'scatter3d',mode:'lines',line:{color:'#68ffff',width:7},name:'Lake footprint',hoverinfo:'skip'};
  const fill={x:t.x,y:t.y,z:t.lake_z,type:'surface',colorscale:[[0,'#00b9c7'],[1,'#68ffff']],showscale:false,opacity:.12,hoverinfo:'skip',name:'Lake area'};
  Plotly.react('footprintPlot',[fill,line],{paper_bgcolor:'#071218',plot_bgcolor:'#071218',margin:{l:0,r:0,t:5,b:0},scene:{xaxis:{title:'Local X',color:'#7e9ba2',gridcolor:'#17323a'},yaxis:{title:'Local Y',color:'#7e9ba2',gridcolor:'#17323a'},zaxis:{title:'Elevation',color:'#7e9ba2',gridcolor:'#17323a'},camera:{eye:{x:1.45,y:1.45,z:.78}},bgcolor:'#071218',aspectmode:'auto'},font:{color:'#a9c2c7'}},{responsive:true,displaylogo:false});
  $('bpPixels').textContent=bp.mask_pixels;
  $('bpDims').textContent=`${bp.width_px} × ${bp.length_px} px`;
}
init();
