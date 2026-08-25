"""Canlı gösterge - eğitilmiş model + UDP mimarisi (2026-08-25).

NE GÖSTERİYOR:
  YÜRÜYOR / DURUYOR   <- EĞİTİLMİŞ MODEL, %92.9 faz doğruluğu
  oturuyor / ayakta   <- geçişlerden TAKİP ediliyor, ölçülmüyor (aşağıya bak)
  nefes + nabız

--- YÜRÜME: eğitilmiş model ---
train_walking_model.py, 8 etiketli oturumdan 2288 pencereyle eğitildi.
Doğrulama Leave-One-SESSION-Out (model o oturumu hiç görmedi):
    faz bazında %92.9  |  yumuşatılmış pencere %86.9  |  tek pencere %85.1
Model SADECE ölçekten bağımsız özellikler kullanıyor (spektrumun şekli,
sinyal/gürültü oranı) - mutlak genlik kullanmıyor, çünkü o oturumdan
oturuma kayıyor ve bu projedeki bütün büyük başarısızlıkların kaynağı oydu.

ÖNCEKİ SÜRÜMÜN HATASI (2026-08-25, canlıda yaşandı): eşik tek seferlik
kalibrasyondan geliyordu; kalibrasyon anı sakin değilse taban şişiyor
(1.49 ölçüldü, gerçeği 0.56-0.98) ve sistem hiçbir şey algılamıyordu.
Bu sürümde tek seferlik kalibrasyon YOK - model kararı veriden veriyor,
geçiş eşikleri de sürekli güncellenen yüzdeliklerden geliyor.

--- OTUR/AYAKTA: neden ölçülmüyor ---
Bu donanımda ALTI ayrı yöntem denendi ve hepsi tekrarda çöktü (postural
sway p=0.92; mutlak desen %40-46; kayma ölçüsü kartlar çelişti; faz-arası
seviye adımı tutarsız; geçiş dalga şekli veri artınca yön değiştirdi;
dar-pencere önce/sonra farkı bir oturumda %100 verip ertesinde %56'ya
düşüp işaret değiştirdi). Sebep fiziksel: duruş farkı SABİT bir seviye
farkı, sabit farklar donanım sürüklenmesiyle aynı yerde yaşıyor.
Bu yüzden duruş TAKİP ediliyor: kısa hareket patlaması = geçiş, durumu çevir;
yürüyüş bitti = AYAKTA (bu kesin - yürüyüş her zaman ayakta biter, yani her
yürüyüş durum makinesini sıfırlıyor). Kayarsa arayüzden elle düzeltilir.

Kullanım:
    python live_server_udp.py                # http://localhost:5050
    python live_server_udp.py --start oturuyor
"""
import argparse
import pathlib
import threading
import time
from collections import deque

import joblib
import numpy as np
from flask import Flask, jsonify, render_template_string

from activity_features import (VALID_SUBCARRIERS, parse_amplitude_matrix,
                               movement_energy_bandpass, walking_features)
from bpm_pipeline import estimate_bpm_fft, BREATHING_BAND, HEART_RATE_BAND
from csi_udp_server import CsiUdpServer

MODEL_PATH = pathlib.Path(__file__).parent / "models/walking_model.joblib"

UPDATE_SEC = 0.5
BREATH_WINDOW_SEC = 20.0
HEART_WINDOW_SEC = 12.0
MIN_PACKETS = 80

WALK_PROB_ENTER = 0.55    # histerezis: yürümeye girmek için
WALK_PROB_EXIT = 0.40     # yürümeden çıkmak için (arada karar korunur)

# Geçiş tespiti eşikleri artık SÜREKLİ GÜNCELLENEN yüzdeliklerden geliyor;
# tek seferlik kalibrasyon yok (önceki sürümü bozan buydu).
ADAPT_WINDOW = 160        # ~80 sn'lik geçmiş
MOVE_PCTL, MOVE_MULT = 70, 1.6
STEP_PCTL = 88
MIN_BURST_SEC, MAX_BURST_SEC = 0.5, 4.0
REFRACTORY_SEC = 4.0
LEVEL_PRE, LEVEL_POST = (-3.5, -0.5), (1.0, 4.0)

POSTURES = ("oturuyor", "ayakta")

state = {"activity": "baslatiliyor", "posture": "ayakta", "walking": False,
         "walk_prob": None, "movement": None, "move_thr": None,
         "step_thr": None, "breath": None, "heart": None,
         "vitals_reliable": True, "boards": {}, "connected": False,
         "last_event": "başlatılıyor"}
state_lock = threading.Lock()


def board_level(amp):
    v = amp[:, VALID_SUBCARRIERS] if amp.shape[1] > max(VALID_SUBCARRIERS) else amp
    return float(np.median(v.mean(axis=1)))


def sample(srv, roles, model, win_sec):
    """Her kart için (yürüme olasılığı, hareket enerjisi, seviye, paket)."""
    probs, energies, levels, counts = {}, {}, {}, {}
    for r in roles:
        lines = srv.recent(r, win_sec)
        counts[r] = len(lines)
        if len(lines) < MIN_PACKETS:
            continue
        amp = parse_amplitude_matrix("\n".join(lines))
        if amp.shape[0] < MIN_PACKETS:
            continue
        fs = amp.shape[0] / win_sec
        # Eğitimle BİREBİR aynı fonksiyon (activity_features.walking_features)
        probs[r] = float(model.predict_proba(
            walking_features(amp, fs).reshape(1, -1))[0, 1])
        energies[r] = movement_energy_bandpass(amp, fs)
        levels[r] = board_level(amp)
    return probs, energies, levels, counts


def level_step(hist, pre, post):
    """Kartlar arasında EN BÜYÜK |seviye sonrası - seviye öncesi|.

    Yönü kullanmıyoruz: 2026-08-25'te işaretin oturumdan oturuma döndüğü
    ölçüldü (slow1'de kalkma yukarı, slow2'de aşağı). Sadece "belirgin bir
    değişim oldu mu" sorusunu soruyoruz.
    """
    roles = {r for _, lv in hist for r in lv}
    best = 0.0
    for role in roles:
        a = [lv[role] for ts, lv in hist if pre[0] <= ts <= pre[1] and role in lv]
        b = [lv[role] for ts, lv in hist if post[0] <= ts <= post[1] and role in lv]
        if len(a) >= 2 and len(b) >= 2:
            best = max(best, abs(float(np.median(b) - np.median(a))))
    return best


def vitals(srv, roles):
    """⚠️ HAREKET VARKEN GÜVENİLMEZ - arayüz soluklaştırıp uyarıyor.
    Yürüyüş temposu ~2 Hz, tam nabız bandına (0.8-2.0) düşüyor. Nefes bandı
    kendi verimizle doğrulandı; nabız bandı bu donanımda HİÇ doğrulanmadı."""
    out = {"breath": None, "heart": None}
    if not roles:
        return out
    best = max(roles, key=lambda r: len(srv.recent(r, BREATH_WINDOW_SEC)))
    for key, win_sec, band, lo, hi, need in (
            ("breath", BREATH_WINDOW_SEC, BREATHING_BAND, 5, 35, 200),
            ("heart", HEART_WINDOW_SEC, HEART_RATE_BAND, 45, 130, 150)):
        lines = srv.recent(best, win_sec)
        if len(lines) <= need:
            continue
        amp = parse_amplitude_matrix("\n".join(lines))
        if amp.shape[0] <= need:
            continue
        try:
            v = estimate_bpm_fft(amp.mean(axis=1), amp.shape[0] / win_sec, band)
        except Exception:
            continue
        if v and lo <= v <= hi:
            out[key] = round(v, 1)
    return out


def processing_loop(srv, bundle, start_posture):
    model = bundle["model"]
    win_sec = bundle.get("win_sec", 3.0)
    smooth_k = bundle.get("smooth_k", 5)

    prob_hist = deque(maxlen=smooth_k)
    energy_hist = deque(maxlen=ADAPT_WINDOW)
    step_hist = deque(maxlen=ADAPT_WINDOW)
    level_hist = deque(maxlen=240)

    posture, walking, moving = start_posture, False, False
    move_start, last_toggle, pending = None, 0.0, None
    last_event = "hazır"

    while True:
        time.sleep(UPDATE_SEC)
        now = time.time()

        with state_lock:
            ov = state.pop("_override", None)
        if ov:
            posture, walking, pending = ov, False, None
            last_toggle = now
            last_event = f"elle ayarlandı -> {posture}"

        roles = sorted(srv.status())
        if not roles:
            with state_lock:
                state.update(connected=False, activity="kart yok")
            continue

        probs, energies, levels, counts = sample(srv, roles, model, win_sec)
        if not probs:
            with state_lock:
                state.update(connected=True, activity="veri bekleniyor",
                             boards=counts)
            continue

        level_hist.append((now, levels))
        prob_hist.append(sum(probs.values()) / len(probs))
        walk_p = float(np.mean(prob_hist))
        energy = sum(energies.values()) / len(energies)
        energy_hist.append(energy)

        # --- YÜRÜME: model + histerezis ---
        was_walking = walking
        if walking and walk_p < WALK_PROB_EXIT:
            walking = False
        elif not walking and walk_p > WALK_PROB_ENTER:
            walking = True
        if walking and not was_walking:
            last_event = f"model: yürüyor (olasılık {walk_p:.2f})"
            pending = None
        elif was_walking and not walking:
            # Yürüyüş her zaman AYAKTA biter - durum makinesini sıfırlıyor,
            # kaçmış geçişlerin hatası burada temizleniyor.
            posture = "ayakta"
            last_event = f"yürüyüş bitti -> ayakta (olasılık {walk_p:.2f})"

        # --- GEÇİŞ: sürekli güncellenen eşiklerle ---
        move_thr = step_thr = None
        if len(energy_hist) >= 20:
            move_thr = float(np.percentile(energy_hist, MOVE_PCTL)) * MOVE_MULT
            was_moving = moving
            moving = energy > move_thr
            if moving and not was_moving:
                move_start = now
            elif was_moving and not moving and not walking:
                dur = now - (move_start or now)
                if MIN_BURST_SEC <= dur <= MAX_BURST_SEC:
                    pending = {"start": move_start, "end": now, "dur": dur}
                move_start = None

        if len(step_hist) >= 20:
            step_thr = float(np.percentile(step_hist, STEP_PCTL))

        # sessiz anlarda seviye sıçramasını sürekli örnekle (eşiğin tabanı)
        if not moving and not walking:
            s = level_step(level_hist, (now + LEVEL_PRE[0], now + LEVEL_PRE[1]),
                           (now + LEVEL_POST[0] - 5, now + LEVEL_POST[1] - 5))
            if s > 0:
                step_hist.append(s)

        if pending and now >= pending["end"] + LEVEL_POST[1]:
            s = level_step(
                level_hist,
                (pending["start"] + LEVEL_PRE[0], pending["start"] + LEVEL_PRE[1]),
                (pending["end"] + LEVEL_POST[0], pending["end"] + LEVEL_POST[1]))
            ok = step_thr is not None and s >= step_thr
            if ok and (now - last_toggle) >= REFRACTORY_SEC:
                posture = POSTURES[1 - POSTURES.index(posture)] \
                    if posture in POSTURES else "ayakta"
                last_toggle = now
                last_event = (f"geçiş: patlama {pending['dur']:.1f} sn, "
                              f"seviye {s:.2f} -> {posture}")
            else:
                last_event = (f"geçiş reddedildi (seviye {s:.2f} < "
                              f"{step_thr:.2f})" if step_thr else
                              "geçiş: eşik henüz öğreniliyor")
            pending = None

        v = vitals(srv, roles)
        with state_lock:
            state.update(
                connected=True, walking=walking, posture=posture,
                activity="yuruyor" if walking else posture,
                walk_prob=round(walk_p, 2), movement=round(energy, 2),
                move_thr=round(move_thr, 2) if move_thr else None,
                step_thr=round(step_thr, 2) if step_thr else None,
                breath=v["breath"], heart=v["heart"],
                vitals_reliable=not walking, last_event=last_event,
                boards={r: {"paket": counts.get(r, 0),
                            "olasilik": round(p, 2)} for r, p in probs.items()})


app = Flask(__name__)

HTML = """
<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WiFi CSI Canlı Gösterge</title><style>
 *{box-sizing:border-box}
 body{background:#0f1117;color:#e8e8e8;font-family:-apple-system,BlinkMacSystemFont,sans-serif;
      display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;
      transition:background .4s;padding:1.5rem}
 .card{text-align:center;width:100%;max-width:440px}
 .label{font-size:.78rem;letter-spacing:.18em;opacity:.45;margin-bottom:.35rem}
 .value{font-size:3.3rem;font-weight:700;line-height:1.1}
 .yuruyor{color:#ffa94d} .ayakta{color:#4dabf7} .oturuyor{color:#51cf66}
 .tag{font-size:.66rem;opacity:.5;margin:.3rem 0 .7rem;height:1em}
 .breath{color:#51cf66} .heart{color:#ff6b6b}
 .breath,.heart{font-size:2.2rem;font-weight:700;line-height:1.1}
 .vitals{display:flex;gap:2.5rem;justify-content:center;margin-top:1.5rem;transition:opacity .3s}
 .vitals.unreliable{opacity:.28}
 .warn{font-size:.66rem;color:#ffa94d;margin-top:.6rem;min-height:2.2em;line-height:1.5}
 .unit{font-size:.58rem;opacity:.35;margin-top:.25rem}
 .bar{height:10px;background:#20232e;border-radius:5px;margin:.7rem auto 1rem;
      width:100%;max-width:310px;overflow:hidden;position:relative}
 .fill{height:100%;background:#ffa94d;transition:width .25s}
 .mark{position:absolute;top:-3px;width:2px;height:16px;background:#e8e8e8;opacity:.65}
 .sub{font-size:.73rem;opacity:.42}
 .ev{font-size:.66rem;opacity:.45;margin-top:.9rem;min-height:2.4em;line-height:1.5;
     font-family:ui-monospace,Menlo,monospace}
 .boards{font-size:.68rem;opacity:.32;margin-top:.9rem;line-height:1.6}
 .fix{margin-top:1.2rem;display:flex;gap:.5rem;justify-content:center}
 .fix button{background:#20232e;color:#c9c9c9;border:1px solid #333;border-radius:6px;
             padding:.45rem .85rem;font-size:.7rem;cursor:pointer;font-family:inherit}
 .fix button:hover{background:#2a2e3d;color:#fff}
 .fixnote{font-size:.6rem;opacity:.3;margin-top:.5rem;line-height:1.5}
</style></head><body><div class="card">
 <div class="label">DURUM</div>
 <div class="value" id="act">-</div>
 <div class="tag" id="tag"></div>
 <div class="label">YÜRÜME OLASILIĞI (model)</div>
 <div class="bar"><div class="fill" id="fill" style="width:0"></div>
   <div class="mark" id="mark" style="left:55%"></div></div>
 <div class="sub" id="detail"></div>
 <div class="vitals" id="vitals">
   <div><div class="label">NEFES</div><div class="breath" id="breath">—</div>
        <div class="unit">nefes/dk</div></div>
   <div><div class="label">NABIZ</div><div class="heart" id="heart">—</div>
        <div class="unit">atış/dk · doğrulanmadı</div></div>
 </div>
 <div class="warn" id="warn"></div>
 <div class="ev" id="ev"></div>
 <div class="boards" id="boards"></div>
 <div class="fix">
   <button onclick="setp('oturuyor')">şu an oturuyorum</button>
   <button onclick="setp('ayakta')">şu an ayaktayım</button>
 </div>
 <div class="fixnote">yürüme MODELLE ölçülüyor (%92.9 faz doğruluğu) ·
   otur/ayakta geçişlerden takip ediliyor, kayarsa yukarıdan düzelt</div>
</div><script>
const TR={yuruyor:"YÜRÜYOR",ayakta:"AYAKTA",oturuyor:"OTURUYOR",
          baslatiliyor:"...","kart yok":"KART YOK","veri bekleniyor":"VERİ BEKLENİYOR"};
async function setp(p){await fetch('/posture/'+p,{method:'POST'});u();}
async function u(){
 try{
  const d=await (await fetch('/status')).json();
  const e=document.getElementById('act');
  e.textContent=TR[d.activity]||d.activity; e.className='value '+d.activity;
  document.getElementById('tag').textContent=
    d.activity==='yuruyor'?'model ölçüyor':
    (d.activity==='oturuyor'||d.activity==='ayakta')?'geçişlerden takip ediliyor':'';
  document.getElementById('fill').style.width=((d.walk_prob||0)*100)+'%';
  document.getElementById('detail').textContent=
    d.walk_prob!=null?('olasılık '+d.walk_prob+'  ·  hareket '+d.movement
      +(d.move_thr?('/'+d.move_thr):'')):'';
  document.getElementById('breath').textContent=d.breath??'—';
  document.getElementById('heart').textContent=d.heart??'—';
  const ok=d.vitals_reliable!==false;
  document.getElementById('vitals').className='vitals'+(ok?'':' unreliable');
  document.getElementById('warn').textContent=ok?'':
    'yürüme var — bu değerler güvenilmez (adım temposu nabız bandına düşüyor)';
  document.getElementById('ev').textContent=d.last_event||'';
  document.getElementById('boards').innerHTML=
    Object.entries(d.boards||{}).map(([k,v])=>
      k+': '+(v.paket||0)+' paket, yürüme olasılığı '+(v.olasilik??'-')).join('<br>')
    +(d.connected?'':'<br>BAĞLANTI YOK');
  document.body.style.background=d.activity==='yuruyor'?'#3a2414':'#0f1117';
 }catch(err){document.getElementById('boards').textContent='Sunucuya erişilemiyor';}
}
setInterval(u,600);u();
</script></body></html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/status")
def status():
    with state_lock:
        return jsonify({k: v for k, v in state.items() if not k.startswith("_")})


@app.route("/posture/<p>", methods=["POST"])
def set_posture(p):
    if p not in POSTURES:
        return jsonify({"ok": False}), 400
    with state_lock:
        state["_override"] = p
        state.update(posture=p, walking=False, activity=p)
    return jsonify({"ok": True})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", choices=POSTURES, default="ayakta")
    args = ap.parse_args()

    if not MODEL_PATH.exists():
        raise SystemExit(f"Model yok: {MODEL_PATH}\n"
                         f"Önce çalıştır: python train_walking_model.py")
    bundle = joblib.load(MODEL_PATH)
    print(f"Model yüklendi: {MODEL_PATH.name} "
          f"({len(bundle['features'])} özellik, pencere {bundle['win_sec']} sn)")

    srv = CsiUdpServer(keep_sec=BREATH_WINDOW_SEC + 10).start()
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

    with state_lock:
        state.update(posture=args.start, activity=args.start)
    threading.Thread(target=processing_loop, args=(srv, bundle, args.start),
                     daemon=True).start()
    print("\nKALİBRASYON YOK - model hazır, ekran hemen çalışıyor.")
    print("Canlı gösterge: http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)
