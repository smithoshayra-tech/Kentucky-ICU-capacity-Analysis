"""
04_build_dashboard.py  - writes dashboard/index.html, one self-contained file (data and Chart.js inlined).
Open it by double-clicking; no server or internet needed.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
STATES = ["KY", "IL", "IN", "MO", "OH", "TN", "VA", "WV"]
PEERS = STATES[1:]
WAVES = {"Winter 2020-21": ("2020-10-18", "2021-02-28"), "Delta 2021": ("2021-07-25", "2021-11-14"),
         "Omicron 2021-22": ("2021-12-12", "2022-03-06")}

sw = pd.read_csv(OUT / "state_week_occupancy.csv", parse_dates=["week"])
weeks = sorted(sw["week"].unique())
wk = [pd.Timestamp(w).strftime("%Y-%m-%d") for w in weeks]


def series(df, col, state):
    s = df[df.state == state].set_index("week")[col].reindex(weeks)
    return [None if pd.isna(v) else round(float(v), 4) for v in s]

icu = {s: series(sw, "icu_occ", s) for s in STATES}
stf = pd.read_csv(ROOT / "tableau_extracts" / "state_week_staffing.csv", parse_dates=["week"])
stf["share"] = stf["staff_short_share"].rolling(1).mean()
staff = {s: series(stf.rename(columns={"staff_short_share": "x"}), "x", s) for s in STATES}

ks = pd.read_csv(OUT / "ky_side_week.csv", parse_dates=["week"])
side = {}
for sd in ["Lexington-side", "Louisville-side"]:
    t = ks[ks.ky_side == sd].set_index("week")["icu_occ"].reindex(weeks)
    side[sd] = [None if pd.isna(v) else round(float(v), 4) for v in t]
hw = pd.read_csv(OUT / "ky_headroom_week.csv", parse_dates=["week"]).set_index("week").reindex(weeks)
head = {"strained": [int(v) if pd.notna(v) else 0 for v in hw["strained"]],
        "stranded": [int(v) if pd.notna(v) else 0 for v in hw["stranded"]]}

# hospital-level share of weeks at 90%+ by state for every range option
h = pd.read_csv(ROOT / "data_clean" / "hospital_week_clean.csv.gz", low_memory=False, parse_dates=["collection_week"])
h = h[h["stable_reporter"] & h["icu_occ"].notna() & (h["icu_beds"] > 0)]
rng_opts = {"All weeks": (None, None), **WAVES}
share = {}
for name, (a, b) in rng_opts.items():
    d = h if a is None else h[(h.collection_week >= a) & (h.collection_week <= b)]
    minw = 52 if a is None else 8
    t = d.groupby(["state", "hospital_pk"])["icu_occ"].agg(n="count", s=lambda x: (x >= 0.90).mean()).reset_index()
    t = t[t.n >= minw]
    share[name] = {s: {"mean": round(float(t[t.state == s]["s"].mean()), 4), "n": int((t.state == s).sum())} for s in STATES}
    pool = t[t.state != "KY"]["s"]
    share[name]["PEERS"] = {"mean": round(float(pool.mean()), 4), "n": int(len(pool))}

data = dict(weeks=wk, icu=icu, staff=staff, side=side, head=head, share=share,
            waves={k: list(v) for k, v in WAVES.items()})
chart_js = (ROOT / "dashboard" / "_chart.umd.js").read_text()

html = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kentucky Hospital Capacity</title>
<style>
:root{--bg:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#7a7974;--line:#e4e3de;--blue:#2a78d6;--orange:#eb6834;--gray:#6d6c67;--lblue:#9ec5f4;--grid:#ecebe6;--wave:rgba(120,118,108,.10)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1a1a19;--card:#232321;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9b9a92;--line:#3a3a37;--blue:#3987e5;--orange:#d95926;--gray:#a9a8a2;--lblue:#3b6aa8;--grid:#33332f;--wave:rgba(255,255,255,.06)}}
:root[data-theme="dark"]{--bg:#1a1a19;--card:#232321;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9b9a92;--line:#3a3a37;--blue:#3987e5;--orange:#d95926;--gray:#a9a8a2;--lblue:#3b6aa8;--grid:#33332f;--wave:rgba(255,255,255,.06)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,"Segoe UI",Carlito,Calibri,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 40px}
h1{font-size:23px;margin:0 0 4px}.sub{color:var(--ink2);margin:0 0 16px;max-width:860px}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 16px}
.seg{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--card)}
.seg button{border:0;background:none;color:var(--ink2);padding:8px 12px;font:inherit;cursor:pointer;border-right:1px solid var(--line)}
.seg button:last-child{border-right:0}.seg button.on{background:var(--blue);color:#fff}
select,.tbtn{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 10px;border-radius:8px;font:inherit;cursor:pointer}
label.lab{color:var(--muted);font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile .v{font-size:27px;font-weight:700;line-height:1.1}.tile .l{color:var(--ink2);font-size:13px;margin-top:4px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 14px 10px}
.grid>*{min-width:0}.card.wide{grid-column:1/-1}.card h2{font-size:15.5px;margin:0 0 2px}.card p{margin:0 0 8px;color:var(--ink2);font-size:13px}
.cv{position:relative;height:300px}.cv.tall{height:340px}
.key{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--ink2);margin:2px 0 4px}.key i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:-1px}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}th:first-child,td:first-child{text-align:left}
.note{color:var(--muted);font-size:12.5px;margin-top:16px;max-width:900px}
@media(max-width:820px){.tiles{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>Kentucky hospital capacity, 2020 to 2024</h1>
<p class="sub">How full Kentucky's adult ICUs were compared with its seven border states, whether strained hospitals had open beds nearby, and how staffing shortages moved with the surges. Weekly data, Aug 2020 to Apr 2024.</p>
<div class="bar">
 <div class="seg" id="range"></div>
 <label class="lab">Compare Kentucky with <select id="cmp"></select></label>
 <button class="tbtn" id="tbl">Show table</button>
</div>
<div class="tiles" id="tiles"></div>
<div class="grid">
 <div class="card wide"><h2>Adult ICU use over time</h2><p>Share of staffed adult ICU beds in use. The dotted line marks 90% full.</p>
  <div class="key"><span><i style="background:var(--blue)"></i>Kentucky</span><span><i style="background:var(--gray)"></i><span id="cmpname">Border-state median</span></span></div>
  <div class="cv tall"><canvas id="c1"></canvas></div></div>
 <div class="card"><h2>How often hospitals hit 90%+ ICU use</h2><p>Average share of weeks, across hospitals, in the selected period.</p><div class="cv"><canvas id="c2"></canvas></div></div>
 <div class="card"><h2>Lexington side vs Louisville side</h2><p>Kentucky hospitals grouped by the nearer city (my assumption, not the official RMOCC boundary).</p>
  <div class="key"><span><i style="background:var(--blue)"></i>Lexington side</span><span><i style="background:var(--orange)"></i>Louisville side</span></div><div class="cv"><canvas id="c3"></canvas></div></div>
 <div class="card"><h2>Strained hospitals with no open beds nearby</h2><p>Kentucky hospitals at 90%+ ICU use, and those with fewer than 2 open ICU beds at hospitals within 60 miles that were under 80% full.</p>
  <div class="key"><span><i style="background:var(--lblue)"></i>At 90%+</span><span><i style="background:var(--orange)"></i>No open beds within 60 miles</span></div><div class="cv"><canvas id="c4"></canvas></div></div>
 <div class="card"><h2>Hospitals reporting a critical staffing shortage</h2><p>Share of reporting hospitals saying they had one that day, averaged by week.</p>
  <div class="key"><span><i style="background:var(--blue)"></i>Kentucky</span><span><i style="background:var(--gray)"></i><span id="cmpname2">Border-state median</span></span></div><div class="cv"><canvas id="c5"></canvas></div></div>
 <div class="card wide" id="tcard" style="display:none"><h2>Table: share of weeks at 90%+ ICU use</h2><p id="tp"></p><div id="tbody" style="overflow-x:auto"></div></div>
</div>
<p class="note">Sources: HHS COVID-19 Reported Patient Impact and Hospital Capacity by Facility and by State Timeseries; CMS Hospital General Information. Hospital-level figures use hospitals with at least 52 valid ICU weeks overall, or at least 8 within a single wave. Open beds nearby are staffed adult ICU beds not in use; the data contains no patient transfers, so this shows room that existed, not transfers that happened. Facility reporting ended in April 2024.</p>
</div>
<script>__CHARTJS__</script>
<script>
const D=__DATA__;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const W=D.weeks, N=W.length, STATES=Object.keys(D.icu), PEERS=STATES.filter(s=>s!=='KY');
const RANGES={'All weeks':[W[0],W[N-1]]}; for(const k in D.waves) RANGES[k]=D.waves[k];
let cur='All weeks', cmp='MEDIAN', charts={}, showT=false, SPAN=999;
const idx=()=>{const[a,b]=RANGES[cur];const i=W.findIndex(w=>w>=a);let j=N-1;while(j>0&&W[j]>b)j--;return[Math.max(i,0),j]};
const med=a=>{const v=a.filter(x=>x!=null).sort((x,y)=>x-y);if(!v.length)return null;const m=v.length>>1;return v.length%2?v[m]:(v[m-1]+v[m])/2};
const medSeries=src=>W.map((_,i)=>med(PEERS.map(s=>src[s][i])));
const MED_ICU=medSeries(D.icu), MED_ST=medSeries(D.staff);
const pc=v=>v==null?'–':(v*100).toFixed(0)+'%';
const sl=(a,i,j)=>a.slice(i,j+1);
const wavePlugin={id:'waves',beforeDatasetsDraw(c){if(c.config.type==='bar'&&c.config.options.indexAxis==='y')return;const x=c.scales.x;if(!x)return;const ctx=c.ctx,a=c.chartArea;ctx.save();ctx.fillStyle=css('--wave');
 const labels=c.data.labels;for(const k in D.waves){const[s,e]=D.waves[k];let i=labels.findIndex(l=>l>=s),j=labels.length-1;while(j>0&&labels[j]>e)j--;if(i<0||j<i)continue;const x0=x.getPixelForValue(i),x1=x.getPixelForValue(j);ctx.fillRect(x0,a.top,Math.max(x1-x0,2),a.bottom-a.top)}ctx.restore()}};
const lineBase=()=>({responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},animation:false,
 plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.dataset.label+': '+(c.dataset._cnt?c.parsed.y:pc(c.parsed.y))}}},
 scales:{x:{grid:{display:false},ticks:{color:css('--muted'),maxTicksLimit:7,maxRotation:0,callback:function(v){const l=this.getLabelForValue(v);const d=new Date(l+'T00:00:00');return d.toLocaleDateString('en-US',SPAN>400?{month:'short',year:'numeric'}:{month:'short',day:'numeric'})}}},
 y:{grid:{color:css('--grid')},ticks:{color:css('--muted'),callback:v=>(v*100).toFixed(0)+'%'}}}});
function mk(id,cfg){if(charts[id])charts[id].destroy();charts[id]=new Chart(document.getElementById(id),cfg)}
function ds(label,data,color,w=2){return{label,data,borderColor:color,backgroundColor:color,borderWidth:w,pointRadius:0,pointHoverRadius:4,tension:.15,spanGaps:true}}
function render(){
 const[i,j]=idx(), L=sl(W,i,j);SPAN=(new Date(W[j])-new Date(W[i]))/864e5;
 const cmpICU=cmp==='MEDIAN'?MED_ICU:D.icu[cmp], cmpST=cmp==='MEDIAN'?MED_ST:D.staff[cmp];
 const nm=cmp==='MEDIAN'?'Border-state median':cmp;
 document.getElementById('cmpname').textContent=nm;document.getElementById('cmpname2').textContent=nm;
 // c1
 let o=lineBase();o.scales.y.min=.4;o.scales.y.max=1;
 const ninety={id:'n90',afterDatasetsDraw(c){const y=c.scales.y.getPixelForValue(.9),a=c.chartArea,x=c.ctx;x.save();x.strokeStyle=css('--ink2');x.setLineDash([2,4]);x.lineWidth=1;x.beginPath();x.moveTo(a.left,y);x.lineTo(a.right,y);x.stroke();x.restore()}};
 mk('c1',{type:'line',data:{labels:L,datasets:[ds(nm,sl(cmpICU,i,j),css('--gray'),1.8),ds('Kentucky',sl(D.icu.KY,i,j),css('--blue'),2.6)]},options:o,plugins:[wavePlugin,ninety]});
 // c2
 const S=D_share(),rows=STATES.map(s=>({s,v:S[s].mean,n:S[s].n})).sort((a,b)=>b.v-a.v);
 mk('c2',{type:'bar',data:{labels:rows.map(r=>r.s+'  (n='+r.n+')'),datasets:[{data:rows.map(r=>r.v),backgroundColor:rows.map(r=>r.s==='KY'?css('--blue'):css('--gray')),borderRadius:4,barThickness:18}]},
  options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>pc(c.parsed.x)+' of weeks at 90%+'}}},
  scales:{x:{grid:{color:css('--grid')},min:0,ticks:{color:css('--muted'),callback:v=>(v*100).toFixed(0)+'%'}},y:{grid:{display:false},ticks:{color:css('--ink2')}}}}});
 // c3
 o=lineBase();o.scales.y.min=.4;o.scales.y.max=1;
 mk('c3',{type:'line',data:{labels:L,datasets:[ds('Lexington side',sl(D.side['Lexington-side'],i,j),css('--blue')),ds('Louisville side',sl(D.side['Louisville-side'],i,j),css('--orange'))]},options:o,plugins:[wavePlugin,ninety]});
 // c4
 o=lineBase();o.plugins.tooltip.callbacks.label=c=>c.dataset.label+': '+c.parsed.y;o.scales.y.ticks.callback=v=>v;o.scales.x.stacked=false;
 mk('c4',{type:'bar',data:{labels:L,datasets:[{label:'At 90%+ ICU use',data:sl(D.head.strained,i,j),backgroundColor:css('--lblue'),barPercentage:1,categoryPercentage:1,grouped:false,order:2},
  {label:'No open beds within 60 miles',data:sl(D.head.stranded,i,j),backgroundColor:css('--orange'),barPercentage:1,categoryPercentage:1,grouped:false,order:1}]},options:o,plugins:[wavePlugin]});
 // c5
 o=lineBase();o.scales.y.min=0;
 mk('c5',{type:'line',data:{labels:L,datasets:[ds(nm,sl(cmpST,i,j),css('--gray'),1.8),ds('Kentucky',sl(D.staff.KY,i,j),css('--blue'),2.4)]},options:o,plugins:[wavePlugin]});
 tiles(i,j,S);table(S);
}
function D_share(){return D.share[cur]}
function tiles(i,j,S){
 const peak=a=>Math.max(...sl(a,i,j).filter(x=>x!=null));
 const ranks=STATES.map(s=>[s,peak(D.icu[s])]).sort((a,b)=>b[1]-a[1]);const r=ranks.findIndex(x=>x[0]==='KY')+1;
 const st=sl(D.head.strained,i,j).reduce((a,b)=>a+b,0),sd=sl(D.head.stranded,i,j).reduce((a,b)=>a+b,0);
 const T=[[pc(S.KY.mean)+' vs '+pc(S.PEERS.mean),'Share of weeks at 90%+ ICU use: Kentucky vs border states'],
  [pc(peak(D.icu.KY)),'Kentucky peak ICU use in this period, ranked '+r+' of 8 states'],
  [st?Math.round(sd/st*100)+'%':'–','Strained hospital-weeks with no open ICU beds within 60 miles ('+sd+' of '+st+')'],
  [pc(peak(D.staff.KY))+' vs '+pc(peak(MED_ST)),'Peak share of hospitals reporting a critical staffing shortage: Kentucky vs border-state median']];
 document.getElementById('tiles').innerHTML=T.map(t=>'<div class="tile"><div class="v">'+t[0]+'</div><div class="l">'+t[1]+'</div></div>').join('');
}
function table(S){
 document.getElementById('tcard').style.display=showT?'block':'none';if(!showT)return;
 document.getElementById('tp').textContent='Period: '+cur+'. Hospitals with a valid ICU in the period.';
 const rows=[...STATES,'PEERS'].map(s=>'<tr><td>'+(s==='PEERS'?'All 7 border states':s)+'</td><td>'+pc(S[s].mean)+'</td><td>'+S[s].n+'</td></tr>').join('');
 document.getElementById('tbody').innerHTML='<table><tr><th>State</th><th>Share of weeks at 90%+</th><th>Hospitals</th></tr>'+rows+'</table>';
}
document.getElementById('range').innerHTML=Object.keys(RANGES).map(k=>'<button data-k="'+k+'" class="'+(k===cur?'on':'')+'">'+k+'</button>').join('');
document.getElementById('range').onclick=e=>{const k=e.target.dataset.k;if(!k)return;cur=k;[...e.currentTarget.children].forEach(b=>b.classList.toggle('on',b.dataset.k===k));render()};
document.getElementById('cmp').innerHTML='<option value="MEDIAN">Border-state median</option>'+PEERS.map(s=>'<option>'+s+'</option>').join('');
document.getElementById('cmp').onchange=e=>{cmp=e.target.value;render()};
document.getElementById('tbl').onclick=e=>{showT=!showT;e.target.textContent=showT?'Hide table':'Show table';render()};
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
render();
</script></body></html>
"""
html = html.replace("__CHARTJS__", chart_js).replace("__DATA__", json.dumps(data, separators=(",", ":")))
(ROOT / "dashboard").mkdir(exist_ok=True)
(ROOT / "dashboard" / "index.html").write_text(html)
print(len(html) // 1024, "KB")
