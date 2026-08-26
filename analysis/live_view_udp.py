"""RuView tarzı canlı sahne - insan motifiyle hareket gösterimi (2026-08-25).

live_server_udp.py'ye DOKUNMAZ. Onu import eder ve AYNI karar döngüsünü
(processing_loop) çalıştırır; yani bu ekranla sade ekran asla farklı tahmin
göstermez. Sade ekran B planı olarak port 5050'de durmaya devam edebilir,
bu ekran 5051'de çalışır. İkisi aynı anda açılırsa iki ayrı UDP sunucusu
kartlara aynı anda talip olur - AYNI ANDA ÇALIŞTIRMA.

--- ⚠️ KONUM HAKKINDA DÜRÜSTLÜK NOTU (en önemli kısım) ---
Bu donanım kişinin odadaki YERİNİ ÖLÇEMEZ. Kart başına 1 anten var (yön
bilgisi için en az 3 gerekir), faz CFO/zamanlama kaymalarıyla bozuk
(Bölüm 3.3) ve Bölüm 5.1'de ölçüldü ki kişi kartların tam arasına girdiğinde
enerji TERS yöne gidiyor. Yani "şu koordinattasın" demek uydurma olurdu.

Ekrandaki figürün YATAY yeri bunun yerine gerçekten ölçülen bir şeyden
geliyor: her kartın kendi hareket enerjisinin kendi sakin tabanına oranı.
Hangi hat daha çok bozuluyorsa figür o tarafa kayar. Bu bir KONUM DEĞİL,
"bozulma dengesi" - ekranda da böyle yazıyor. Kaba bir göstergedir ve
kartların yakınında/uzağında olmakla karışabilir.

Gerçekten güvenilir olan tek şey figürün DURUMU:
  YÜRÜYOR   <- eğitilmiş model, Leave-One-Session-Out %92.9
  AYAKTA / OTURUYOR <- ölçülmüyor, geçişlerden takip ediliyor (kayabilir)

Kullanım:
    python live_view_udp.py                  # http://localhost:5051
    python live_view_udp.py --start oturuyor
"""
import argparse
import socket
import threading
import time
from collections import deque

import joblib
import numpy as np
from flask import Flask, jsonify

import live_server_udp as core
from activity_features import (VALID_SUBCARRIERS, movement_energy_bandpass,
                               parse_amplitude_matrix)

PORT = 5051
VIEW_SEC = 3.0            # kart detayı için pencere
VIEW_UPDATE_SEC = 0.5
MIN_PACKETS = 80
BASE_WINDOW = 240         # ~2 dk'lık sakin taban geçmişi

view = {"kartlar": {}, "denge": 0.0}
view_lock = threading.Lock()


def line_rssi(lines):
    """CSV satırlarından RSSI medyanı (4. sütun). Sinyal sağlığı göstergesi."""
    vals = []
    for ln in lines[-200:]:
        parts = ln.split(",", 5)
        if len(parts) > 3:
            try:
                vals.append(int(parts[3]))
            except ValueError:
                pass
    return int(np.median(vals)) if vals else None


def detail_loop(srv):
    """Kart başına canlı bozulma - SADECE görselleştirme için.

    Model çıkarımını tekrarlamaz (o zaten core.processing_loop'ta yapılıyor),
    sadece ucuz olan bantgeçiren enerjiyi hesaplar.
    """
    hist = {}
    while True:
        time.sleep(VIEW_UPDATE_SEC)
        roles = sorted(srv.status())
        out = {}
        for r in roles:
            lines = srv.recent(r, VIEW_SEC)
            if len(lines) < MIN_PACKETS:
                out[r] = {"hz": round(len(lines) / VIEW_SEC, 1), "zayif": True}
                continue
            amp = parse_amplitude_matrix("\n".join(lines))
            if amp.shape[0] < MIN_PACKETS:
                out[r] = {"hz": round(len(lines) / VIEW_SEC, 1), "zayif": True}
                continue
            fs = amp.shape[0] / VIEW_SEC
            e = float(movement_energy_bandpass(amp, fs))
            h = hist.setdefault(r, deque(maxlen=BASE_WINDOW))
            h.append(e)
            # Taban = kendi geçmişinin alt yarısı. Sabit eşik YOK - tek
            # seferlik kalibrasyon bu projede bir kez sistemi tamamen
            # öldürmüştü (Bölüm 6).
            base = float(np.percentile(h, 40)) if len(h) >= 10 else e
            out[r] = {"hz": round(fs, 1), "enerji": round(e, 2),
                      "taban": round(base, 2),
                      "oran": round(e / (base + 1e-9), 2),
                      "rssi": line_rssi(lines), "zayif": False}
        # Denge: -1 = tamamen ilk kart, +1 = tamamen ikinci kart
        rs = [r for r in sorted(out) if not out[r].get("zayif")]
        denge = 0.0
        if len(rs) == 2:
            a = max(out[rs[0]]["oran"] - 1.0, 0.0)
            b = max(out[rs[1]]["oran"] - 1.0, 0.0)
            if a + b > 0.05:
                denge = (b - a) / (a + b)
        with view_lock:
            view["kartlar"] = out
            view["denge"] = round(denge, 3)


app = Flask(__name__)


@app.route("/")
def index():
    return HTML


@app.route("/view")
def view_state():
    with core.state_lock:
        s = {k: v for k, v in core.state.items() if not k.startswith("_")}
    with view_lock:
        s["kartlar"] = dict(view["kartlar"])
        s["denge"] = view["denge"]
    return jsonify(s)


@app.route("/posture/<p>", methods=["POST"])
def set_posture(p):
    if p not in core.POSTURES:
        return jsonify({"ok": False}), 400
    with core.state_lock:
        core.state["_override"] = p
        core.state.update(posture=p, walking=False, activity=p)
    return jsonify({"ok": True})


# Jinja YOK - HTML doğrudan döndürülüyor, JS'teki süslü parantezler
# şablon motoruna yem olmasın diye.
HTML = r"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CSI Gözlem Sahnesi</title><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(ellipse at 50% 0%,#0d1524 0%,#05070d 70%);
 color:#c9d6e8;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
 min-height:100vh;overflow-x:hidden}
.lbl{font-size:.6rem;letter-spacing:.22em;color:#3e5878;text-transform:uppercase}
header{display:flex;align-items:center;justify-content:space-between;
 padding:14px 22px;border-bottom:1px solid #12203a}
h1{font-size:1.05rem;letter-spacing:.08em;color:#eaf2ff;font-weight:600}
h1 span{color:#2f81f7}
.badge{display:flex;align-items:center;gap:7px;font-size:.62rem;letter-spacing:.14em;
 border:1px solid #1d3355;border-radius:999px;padding:5px 12px;color:#7f9dc4}
.dot{width:7px;height:7px;border-radius:50%;background:#2b3a52}
.dot.on{background:#37d67a;box-shadow:0 0 9px #37d67a}
.dot.off{background:#ff5c5c;box-shadow:0 0 9px #ff5c5c}
.wrap{position:relative;max-width:1180px;margin:0 auto;padding:16px}
svg.scene{width:100%;height:auto;display:block}
.panel{position:absolute;background:rgba(8,15,28,.82);border:1px solid #16283f;
 border-radius:9px;padding:13px 15px;backdrop-filter:blur(7px);min-width:172px}
#vitals{left:24px;top:74px}
#signal{right:24px;top:74px;min-width:230px}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:14px;
 padding:4px 0;font-size:.72rem}
.row b{font-weight:600;color:#dce9fb}
.big{font-size:1.75rem;font-weight:700;line-height:1.15}
.sub{font-size:.55rem;color:#3e5878;letter-spacing:.12em}
.nefes{color:#37d67a}.nabiz{color:#ff6b8a}
#vitals.dim{opacity:.3}
.hr{height:1px;background:#16283f;margin:9px 0}
.brd{font-size:.63rem;color:#6d8cb4;letter-spacing:.05em}
.bar{height:4px;background:#12203a;border-radius:2px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#2f81f7,#37d67a);
 width:0;transition:width .25s}
footer{max-width:1180px;margin:0 auto;padding:4px 22px 30px}
.statebar{display:flex;align-items:center;justify-content:space-between;gap:18px;
 border:1px solid #16283f;border-radius:9px;padding:14px 18px;background:rgba(8,15,28,.6)}
#durum{font-size:2rem;font-weight:700;letter-spacing:.06em}
.ayakta{color:#4dabf7}.yuruyor{color:#ffa94d}.oturuyor{color:#51cf66}
.olay{font-size:.63rem;color:#5b78a0;text-align:right;max-width:330px;line-height:1.5}
.btns{display:flex;gap:8px}
button{background:#0e1a2c;border:1px solid #1d3355;color:#8fb0d8;border-radius:6px;
 padding:7px 13px;font-family:inherit;font-size:.63rem;letter-spacing:.1em;cursor:pointer}
button:hover{border-color:#2f81f7;color:#dce9fb}
.note{margin-top:11px;font-size:.6rem;color:#4a688f;line-height:1.7;
 border-left:2px solid #1d3355;padding-left:11px}
.note b{color:#7f9dc4}
@media(max-width:900px){.panel{position:static;margin-bottom:10px}
 .statebar{flex-direction:column;align-items:flex-start}.olay{text-align:left}}
</style></head><body>

<header>
  <h1><span>&#960;</span> CSI GÖZLEM SAHNESİ</h1>
  <div class="badge"><i class="dot" id="dot"></i><span id="conn">bağlanıyor</span></div>
</header>

<div class="wrap">
  <svg class="scene" id="scene" viewBox="0 0 960 470">
    <defs>
      <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="4" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <filter id="soft" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="9"/>
      </filter>
      <radialGradient id="halo"><stop offset="0%" stop-color="#2f81f7" stop-opacity=".30"/>
        <stop offset="100%" stop-color="#2f81f7" stop-opacity="0"/></radialGradient>
    </defs>
    <g id="grid"></g>
    <ellipse id="halo1" cx="150" cy="352" rx="120" ry="42" fill="url(#halo)"/>
    <ellipse id="halo2" cx="810" cy="352" rx="120" ry="42" fill="url(#halo)"/>
    <path id="beam" fill="none" stroke="#2f81f7" stroke-width="1.4" opacity=".75"/>
    <g id="cards"></g>
    <ellipse id="shadow" cx="480" cy="392" rx="40" ry="9" fill="#000" opacity=".45"/>
    <rect id="seat" x="0" y="0" width="56" height="5" rx="2" fill="#26405f" opacity="0"/>
    <g id="fig" filter="url(#glow)" stroke-linecap="round" fill="none"></g>
  </svg>

  <div class="panel" id="vitals">
    <div class="lbl">yaşam bulguları</div><div class="hr"></div>
    <div class="lbl">nefes</div>
    <div class="big nefes"><span id="nefes">--</span></div><div class="sub">BPM</div>
    <div class="hr"></div>
    <div class="lbl">nabız</div>
    <div class="big nabiz"><span id="nabiz">--</span></div><div class="sub">BPM</div>
    <div class="sub" id="vwarn" style="margin-top:9px;color:#ffa94d"></div>
  </div>

  <div class="panel" id="signal">
    <div class="lbl">sinyal</div><div class="hr"></div>
    <div id="brdlist"></div>
    <div class="hr"></div>
    <div class="row"><span class="lbl">yürüme olasılığı</span><b id="wp">--</b></div>
    <div class="bar"><i id="wpbar"></i></div>
    <div class="row" style="margin-top:7px"><span class="lbl">hareket</span><b id="mv">--</b></div>
  </div>
</div>

<footer>
  <div class="statebar">
    <div><div class="lbl">tahmin edilen durum</div><div id="durum">--</div></div>
    <div class="btns">
      <button onclick="setP('oturuyor')">OTURUYOR</button>
      <button onclick="setP('ayakta')">AYAKTA</button>
    </div>
    <div class="olay" id="olay"></div>
  </div>
  <div class="note">
    <b>YÜRÜYOR / DURUYOR</b> eğitilmiş modelden gelir &mdash; 8 oturum, Leave-One-Session-Out
    doğrulamasıyla %92.9. <b>AYAKTA / OTURUYOR</b> ölçülmez, geçişlerden takip edilir;
    kayarsa yukarıdaki düğmeyle düzeltilir.<br>
    <b>&#9888; Figürün yatay konumu odadaki gerçek yeriniz DEĞİLDİR.</b> Bu donanım konum
    ölçemez (kart başına 1 anten, faz bozuk). Gösterilen şey iki hattın canlı
    <b>bozulma dengesi</b>: hangi hat daha çok bozuluyorsa figür o yana kayar.
  </div>
</footer>

<script>
const VP=[480,140], FY0=196, FY1=468, CARD=[[150,352],[810,352]];
function fx(i,y){const t=(y-VP[1])/(FY1-VP[1]);return VP[0]+(480+i*190-VP[0])*t;}
(function(){let s='';
 for(let i=-7;i<=7;i++){s+=`<line x1="${fx(i,FY0)}" y1="${FY0}" x2="${fx(i,FY1)}" y2="${FY1}"
   stroke="#13243c" stroke-width="1"/>`;}
 for(let k=1;k<=11;k++){const y=VP[1]+(FY1-VP[1])*Math.pow(k/11,1.95);
   s+=`<line x1="${fx(-7,y)}" y1="${y}" x2="${fx(7,y)}" y2="${y}"
     stroke="#13243c" stroke-width="1"/>`;}
 document.getElementById('grid').innerHTML=s;
 let c='';CARD.forEach((p,i)=>{c+=`<g><rect x="${p[0]-7}" y="${p[1]-26}" width="14" height="26"
   rx="3" fill="#0d1c31" stroke="#2f81f7" stroke-width="1.2"/>
   <circle cx="${p[0]}" cy="${p[1]-30}" r="3.5" fill="#2f81f7" filter="url(#glow)"/>
   <circle class="ring" data-i="${i}" cx="${p[0]}" cy="${p[1]-30}" r="10" fill="none"
     stroke="#2f81f7" stroke-width="1"/>
   <text x="${p[0]}" y="${p[1]+20}" text-anchor="middle" font-size="10"
     fill="#3e5878" font-family="monospace" id="cn${i}">--</text></g>`;});
 document.getElementById('cards').innerHTML=c;})();

// ---- iskelet ----
const FIG=document.getElementById('fig');
const SEG=['torso','clav','pelv','uarmL','farmL','uarmR','farmR',
             'thighL','shinL','thighR','shinR'];
const W={torso:8,clav:6,pelv:6};
let el={};
FIG.innerHTML=SEG.map(n=>`<line id="s_${n}" stroke-width="${W[n]||5.5}"/>`).join('')
  +`<circle id="s_head" stroke-width="4" fill="#05070d"/>`;
SEG.concat(['head']).forEach(n=>el[n]=document.getElementById('s_'+n));

const L={thigh:34,shin:34,torso:50,uarm:24,farm:23};
let cur={sit:0,walk:0,x:0}, tgt={sit:0,walk:0,x:0}, ph=0, last=performance.now();
const lerp=(a,b,k)=>a+(b-a)*k;
const rad=d=>d*Math.PI/180;

function limb(root,a,bend,l1,l2){
  const k=[root[0]+l1*Math.sin(rad(a)), root[1]-l1*Math.cos(rad(a))];
  const b=a-bend;
  return [k,[k[0]+l2*Math.sin(rad(b)), k[1]-l2*Math.cos(rad(b))]];
}

function pose(sit,gait,amp){
  // y YUKARI pozitif, taban ayak seviyesi. Ayakta ve oturma pozları AYRI
  // hesaplanıp `sit` katsayısıyla karıştırılıyor - geçiş böyle akıcı oluyor.
  // Kalça ve omuzlara YANAL ayrım şart: yoksa bütün uzuvlar x=0'da üst üste
  // biner ve figür tek bir kalın çizgiye döner.
  const A=30*amp*Math.sin(gait), B=30*amp*Math.sin(gait+Math.PI);
  const bA=(14+26*Math.max(0,-Math.sin(gait)))*amp;
  const bB=(14+26*Math.max(0,-Math.sin(gait+Math.PI)))*amp;

  // --- AYAKTA / YÜRÜYOR ---
  const bob=2.2*amp*Math.sin(2*gait);
  const sHip=[0,70+bob], sNeck=[0,sHip[1]+L.torso];
  const sHipL=[-7,sHip[1]], sHipR=[7,sHip[1]];
  const sShL=[-13,sNeck[1]-5], sShR=[13,sNeck[1]-5];
  const sLegL=limb(sHipL,A,bA,L.thigh,L.shin), sLegR=limb(sHipR,B,bB,L.thigh,L.shin);
  const sArmL=limb(sShL,-A*0.7-6,-9,L.uarm,L.farm);
  const sArmR=limb(sShR,-B*0.7+6, 9,L.uarm,L.farm);

  // --- OTURUYOR --- uyluk öne yatay (82°), baldır aşağı (82-84 ≈ dik)
  const tHip=[-15,48], tNeck=[tHip[0]+7,tHip[1]+L.torso-3];
  const tHipL=[tHip[0]-6,tHip[1]], tHipR=[tHip[0]+6,tHip[1]];
  const tShL=[tNeck[0]-13,tNeck[1]-5], tShR=[tNeck[0]+13,tNeck[1]-5];
  const tLegL=limb(tHipL,80,82,L.thigh,L.shin), tLegR=limb(tHipR,84,86,L.thigh,L.shin);
  // kol: üst kol neredeyse dik aşağı (14°), ön kol öne yatay (bend -62 => 76°)
  // -> eller kucakta. Yoksa kollar öne fırlıyor ve oturma "öne eğilme" gibi duruyor.
  const tArmL=limb(tShL,14,-62,L.uarm,L.farm), tArmR=limb(tShR,16,-60,L.uarm,L.farm);

  const m=(a,b)=>[lerp(a[0],b[0],sit), lerp(a[1],b[1],sit)];
  const neck=m(sNeck,tNeck);
  return{
    hip:m(sHip,tHip), neck:neck, head:[neck[0]+lerp(0,3,sit), neck[1]+15],
    hipL:m(sHipL,tHipL), hipR:m(sHipR,tHipR),
    shL:m(sShL,tShL),   shR:m(sShR,tShR),
    kneeL:m(sLegL[0],tLegL[0]), footL:m(sLegL[1],tLegL[1]),
    kneeR:m(sLegR[0],tLegR[0]), footR:m(sLegR[1],tLegR[1]),
    elbL:m(sArmL[0],tArmL[0]),  hndL:m(sArmL[1],tArmL[1]),
    elbR:m(sArmR[0],tArmR[0]),  hndR:m(sArmR[1],tArmR[1])};
}

function draw(p,bx,by,col){
  const X=v=>bx+v[0], Y=v=>by-v[1];
  const set=(n,a,b)=>{const e=el[n];
    e.setAttribute('x1',X(a));e.setAttribute('y1',Y(a));
    e.setAttribute('x2',X(b));e.setAttribute('y2',Y(b));e.setAttribute('stroke',col);};
  set('torso',p.hip,p.neck); set('clav',p.shL,p.shR); set('pelv',p.hipL,p.hipR);
  set('uarmL',p.shL,p.elbL); set('farmL',p.elbL,p.hndL);
  set('uarmR',p.shR,p.elbR); set('farmR',p.elbR,p.hndR);
  set('thighL',p.hipL,p.kneeL); set('shinL',p.kneeL,p.footL);
  set('thighR',p.hipR,p.kneeR); set('shinR',p.kneeR,p.footR);
  el.head.setAttribute('cx',X(p.head));el.head.setAttribute('cy',Y(p.head));
  el.head.setAttribute('r',11.5);el.head.setAttribute('stroke',col);
}

let live={durum:'ayakta',mv:0,denge:0,oran:[1,1]};
const COL={ayakta:'#4dabf7',yuruyor:'#ffa94d',oturuyor:'#51cf66'};
const beamEl=document.getElementById('beam'), shadow=document.getElementById('shadow'),
      seat=document.getElementById('seat');

function frame(now){
  const dt=Math.min((now-last)/1000,.05); last=now;
  tgt.sit = live.durum==='oturuyor'?1:0;
  tgt.walk= live.durum==='yuruyor'?1:0;
  tgt.x   = live.denge*225;
  const k=1-Math.pow(0.004,dt);
  cur.sit=lerp(cur.sit,tgt.sit,k); cur.walk=lerp(cur.walk,tgt.walk,k);
  cur.x=lerp(cur.x,tgt.x,1-Math.pow(0.15,dt));
  ph += dt*(2.0+5.4*cur.walk);
  const amp=0.10+0.90*cur.walk;
  const bx=480+cur.x, by=392;
  const col=COL[live.durum]||'#4dabf7';
  draw(pose(cur.sit,ph,amp),bx,by,col);
  shadow.setAttribute('cx',bx);
  shadow.setAttribute('rx',34+10*cur.walk);
  seat.setAttribute('opacity',(cur.sit*0.85).toFixed(2));
  seat.setAttribute('x',bx-34); seat.setAttribute('y',by-44);
  // hat: kişinin bulunduğu yerde daha çok titriyor (gerçek hareket enerjisiyle)
  const w=Math.min(live.mv/2.2,1.6), pts=[];
  for(let i=0;i<=70;i++){const t=i/70, x=CARD[0][0]+(CARD[1][0]-CARD[0][0])*t;
    const g=Math.exp(-Math.pow((x-bx)/150,2));
    pts.push(x+','+(CARD[0][1]-30+Math.sin(i*0.55+now/130)*13*w*g).toFixed(1));}
  beamEl.setAttribute('d','M'+pts.join('L'));
  beamEl.setAttribute('stroke',col); beamEl.setAttribute('opacity',(0.35+0.4*w).toFixed(2));
  document.querySelectorAll('.ring').forEach(r=>{const i=+r.dataset.i;
    const o=live.oran[i]||1, s=(now/900+i*0.5)%1;
    r.setAttribute('r',(9+s*26*Math.min(o,3)).toFixed(1));
    r.setAttribute('opacity',((1-s)*0.5*Math.min(o,3)).toFixed(2));});
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

function setP(p){fetch('/posture/'+p,{method:'POST'});}
async function poll(){
  try{
    const d=await (await fetch('/view')).json();
    document.getElementById('dot').className='dot '+(d.connected?'on':'off');
    document.getElementById('conn').textContent=d.connected?'canlı':'kart yok';
    const act=d.activity in COL?d.activity:'ayakta';
    live.durum=act; live.mv=d.movement||0; live.denge=d.denge||0;
    const du=document.getElementById('durum');
    du.textContent={ayakta:'AYAKTA',yuruyor:'YÜRÜYOR',oturuyor:'OTURUYOR'}[act]||'--';
    du.className=act;
    document.getElementById('olay').textContent=d.last_event||'';
    document.getElementById('nefes').textContent=d.breath??'--';
    document.getElementById('nabiz').textContent=d.heart??'--';
    document.getElementById('vitals').className='panel'+(d.vitals_reliable?'':' dim');
    document.getElementById('vwarn').textContent=d.vitals_reliable?'':
      'hareket var - ölçüm güvenilmez';
    document.getElementById('wp').textContent=(d.walk_prob??'--');
    document.getElementById('wpbar').style.width=((d.walk_prob||0)*100)+'%';
    document.getElementById('mv').textContent=(d.movement??'--');
    const ks=Object.keys(d.kartlar||{}).sort(); let h=''; live.oran=[1,1];
    ks.forEach((r,i)=>{const b=d.kartlar[r];
      if(i<2){live.oran[i]=b.oran||1;
        const c=document.getElementById('cn'+i); if(c)c.textContent=r;}
      h+=`<div class="row"><span class="brd">${r}</span><b>${b.hz??'--'} Hz</b></div>`
       +`<div class="row"><span class="lbl">rssi / bozulma</span>`
       +`<b>${b.rssi??'--'} dBm &middot; ${b.zayif?'zayıf':(b.oran??'--')+'x'}</b></div>`;});
    document.getElementById('brdlist').innerHTML=h||'<div class="brd">kart yok</div>';
  }catch(e){document.getElementById('dot').className='dot off';}
}
poll(); setInterval(poll,450);
</script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="RuView tarzı canlı CSI sahnesi")
    ap.add_argument("--start", choices=core.POSTURES, default="ayakta")
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()

    if not core.MODEL_PATH.exists():
        raise SystemExit(f"Model yok: {core.MODEL_PATH}\n"
                         f"Önce çalıştır: python train_walking_model.py")
    bundle = joblib.load(core.MODEL_PATH)
    print(f"Model yüklendi: {core.MODEL_PATH.name} "
          f"({len(bundle['features'])} özellik, pencere {bundle['win_sec']} sn)")

    # İki arayüz aynı anda çalışamaz: ikisi de UDP 2223'e bağlanmaya çalışır.
    # Çıplak OSError yerine ne yapması gerektiğini söyleyelim.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("", 2223))
    except OSError:
        raise SystemExit(
            "UDP 2223 meşgul - büyük ihtimalle sade arayüz (live_server_udp.py) "
            "zaten çalışıyor.\nİkisi aynı anda çalışamaz, ikisi de kartlara "
            "talip olur. Önce onu durdur:\n    pkill -f live_server_udp.py")
    finally:
        probe.close()

    srv = core.CsiUdpServer(keep_sec=core.BREATH_WINDOW_SEC + 10).start()
    print("Kartlar aranıyor...")
    for _ in range(12):
        time.sleep(1)
        if srv.status():
            break
    st = srv.status()
    if not st:
        raise SystemExit("Kart bulunamadı. Kartlar güçte mi? "
                         "'ipconfig getifaddr en0' ile aynı ağda mısın?")
    print("Bulundu: " + ", ".join(f"{r} ({i['ip']})" for r, i in st.items()))

    with core.state_lock:
        core.state.update(posture=args.start, activity=args.start)
    # Karar döngüsü live_server_udp'nin KENDİSİ - iki ekran aynı beyni kullanıyor.
    threading.Thread(target=core.processing_loop, args=(srv, bundle, args.start),
                     daemon=True).start()
    threading.Thread(target=detail_loop, args=(srv,), daemon=True).start()
    print(f"\nSahne: http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)
