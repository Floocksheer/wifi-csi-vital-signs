"""Canlı gösterge - UDP mimarisi (2026-08-24 akşam).

live_server.py'nin (seri port, tek kart) yerini alır.

NE GÖSTERİYOR ve NEDEN:
  * HAREKET / HAREKETSİZ  - bugün ölçülen tek güvenilir sınıflandırma (%85,
    üç ayrı geometride tutarlı, konumdan bağımsız).
  * NEFES HIZI            - frekans tabanlı olduğu için ortamdan bağımsız.
  * İki kartın MİNİMUMU   - gürültü sıçramaları iki kartta bağımsız; minimum
    alınca birindeki sahte yükselme eleniyor, gerçek hareket ikisini birden
    yükselttiği için kalıyor. Ölçüm: tek kart %76/%83 -> minimum %87.

NE GÖSTERMİYOR: otur/ayakta. 2026-08-24 kontrollü testi bu ayrımın bu
donanımda çalışmadığını kanıtladı (konum değişkenken %40-46, şans %50).
Bkz. docs/PROJE_DURUM_VE_KARARLAR.md "EN KRİTİK BULGU".

Kullanım:
    python live_server_udp.py              # http://localhost:5050
    python live_server_udp.py --calibrate  # ilk 15 sn'yi taban kabul edip
                                           # eşiği kendisi belirler (oda BOŞ
                                           # ya da kişi hareketsiz olmalı)
"""
import argparse
import threading
import time

import numpy as np
from flask import Flask, jsonify, render_template_string

from activity_features import parse_amplitude_matrix, movement_energy_bandpass
from bpm_pipeline import estimate_bpm_fft, BREATHING_BAND, HEART_RATE_BAND
from csi_udp_server import CsiUdpServer

MOVE_WINDOW_SEC = 4.0     # bantgeçiren 0.3 Hz'i görebilmek için (2 sn yetmiyor)
BREATH_WINDOW_SEC = 20.0  # 0.1-0.5 Hz için birkaç periyot lazım
HEART_WINDOW_SEC = 12.0   # 0.8-2.0 Hz daha hızlı, daha kısa pencere yeter
UPDATE_SEC = 1.0
MIN_PACKETS = 40

# ⚠️ SABİT EŞİK GÜVENİLİR DEĞİL. İki tekrarda en iyi eşik 0.98 ve 0.81
# çıktı - oturumdan oturuma kayıyor. Bu yüzden başlangıçta OTOMATİK
# KALİBRASYON yapılıyor; bu değer sadece kalibrasyon yapılamazsa kullanılan
# son çare.
DEFAULT_THRESHOLD = 0.90
VOTE_WINDOW = 3           # ekran titremesin diye son 3 kararın çoğunluğu

state = {"activity": "baslatiliyor", "movement": None, "threshold": None,
         "breath": None, "heart": None, "vitals_reliable": True,
         "boards": {}, "connected": False}
state_lock = threading.Lock()


def processing_loop(srv, threshold):
    votes = []
    while True:
        time.sleep(UPDATE_SEC)
        roles = sorted(srv.status())
        if not roles:
            with state_lock:
                state["connected"] = False
                state["activity"] = "kart yok"
            continue

        energies, counts = {}, {}
        for r in roles:
            lines = srv.recent(r, MOVE_WINDOW_SEC)
            counts[r] = len(lines)
            if len(lines) < MIN_PACKETS:
                continue
            amp = parse_amplitude_matrix("\n".join(lines))
            if amp.shape[0] < MIN_PACKETS:
                continue
            fs = amp.shape[0] / MOVE_WINDOW_SEC
            energies[r] = movement_energy_bandpass(amp, fs)

        if not energies:
            with state_lock:
                state["connected"] = True
                state["activity"] = "veri bekleniyor"
                state["boards"] = counts
            continue

        # İki kartın ORTALAMASI. Minimum da denendi (2026-08-24, iki tekrar):
        # ortalamada ikisi eşit (%90.5) ama minimum oturumdan oturuma çok
        # oynuyor (%95 -> %86), ortalama daha kararlı (%92 -> %89).
        energy = sum(energies.values()) / len(energies)
        # "hareket" - "yürüyor" DEĞİL. 2026-08-24 testi (20260824_hareket_turu):
        # yerinde kıpırdanma ile yürüme enerjide birebir aynı (1.03x / 1.00x),
        # "kayma" ölçüsü de iki kartta TERS yön verdi (1.22x vs 0.77x) = gürültü.
        # Sistem hareketin VARLIĞINI görüyor, TÜRÜNÜ göremiyor.
        raw = "yuruyor" if energy > threshold else "hareketsiz"
        votes.append(raw)
        del votes[:-VOTE_WINDOW]
        activity = max(set(votes), key=votes.count)

        # Nefes ve nabız: en çok paket gelen karttan, HER DURUMDA hesaplanıyor.
        # ⚠️ HAREKET VARKEN GÜVENİLMEZ, arayüz bunu soluk gösterip uyarıyor:
        #   - Yürüyüş temposu (~2 adım/sn = 2 Hz) tam NABIZ bandına (0.8-2.0 Hz)
        #     düşüyor; sistem kalbi değil ayak seslerini ölçmüş olur.
        #   - Gövde hareketi, göğüs hareketinin kat kat üstünde bozulma yaratıp
        #     nefes sinyalini boğuyor.
        # NOT: nefes bandı (0.1-0.5 Hz) kendi verimizle doğrulandı; nabız
        # bandı bu donanımda hiç DOĞRULANMADI.
        breath = heart = None
        best = max(roles, key=lambda r: len(srv.recent(r, BREATH_WINDOW_SEC)))
        if True:  # artık hareket varken de hesaplanıyor (arayüz soluk gösterip uyarıyor)
            blines = srv.recent(best, BREATH_WINDOW_SEC)
            if len(blines) > 200:
                bamp = parse_amplitude_matrix("\n".join(blines))
                if bamp.shape[0] > 200:
                    try:
                        v = estimate_bpm_fft(bamp.mean(axis=1),
                                             bamp.shape[0] / BREATH_WINDOW_SEC,
                                             BREATHING_BAND)
                        if v and 5 <= v <= 35:
                            breath = round(v, 1)
                    except Exception:
                        pass

            hlines = srv.recent(best, HEART_WINDOW_SEC)
            if len(hlines) > 150:
                hamp = parse_amplitude_matrix("\n".join(hlines))
                if hamp.shape[0] > 150:
                    try:
                        v = estimate_bpm_fft(hamp.mean(axis=1),
                                             hamp.shape[0] / HEART_WINDOW_SEC,
                                             HEART_RATE_BAND)
                        if v and 45 <= v <= 130:
                            heart = round(v, 1)
                    except Exception:
                        pass

        with state_lock:
            state["connected"] = True
            state["activity"] = activity
            state["movement"] = round(energy, 2)
            state["threshold"] = round(threshold, 2)
            state["breath"] = breath
            state["heart"] = heart
            state["vitals_reliable"] = (activity == "hareketsiz")
            state["boards"] = {r: {"paket": counts.get(r, 0),
                                   "enerji": round(energies[r], 2)}
                               for r in energies}


app = Flask(__name__)

HTML = """
<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<title>WiFi CSI Canlı Gösterge</title><style>
 body{background:#0f1117;color:#e8e8e8;font-family:-apple-system,BlinkMacSystemFont,sans-serif;
      display:flex;align-items:center;justify-content:center;height:100vh;margin:0;transition:background .4s}
 .card{text-align:center;min-width:340px}
 .label{font-size:.85rem;letter-spacing:.18em;opacity:.45;margin-bottom:.4rem}
 .value{font-size:4rem;font-weight:700;line-height:1.1;margin-bottom:.3rem}
 .yuruyor{color:#ffa94d} .hareketsiz{color:#4dabf7} .belirsiz{color:#868e96}
 .breath{color:#51cf66;font-size:2.6rem;font-weight:700;line-height:1.1}
 .heart{color:#ff6b6b;font-size:2.6rem;font-weight:700;line-height:1.1}
 .vitals{display:flex;gap:3rem;justify-content:center;margin-top:2rem;transition:opacity .3s}
 .vitals.unreliable{opacity:.3}
 .warn{font-size:.7rem;color:#ffa94d;margin-top:.7rem;height:1em}
 .unit{font-size:.65rem;opacity:.35;margin-top:.25rem}
 .bar{height:10px;background:#20232e;border-radius:5px;margin:.9rem auto 1.6rem;width:300px;overflow:hidden;position:relative}
 .fill{height:100%;background:#ffa94d;transition:width .3s}
 .mark{position:absolute;top:-3px;width:2px;height:16px;background:#e8e8e8;opacity:.7}
 .sub{font-size:.8rem;opacity:.4;margin-top:.3rem}
 .boards{font-size:.75rem;opacity:.35;margin-top:1.4rem;line-height:1.6}
</style></head><body><div class="card">
 <div class="label">DURUM</div>
 <div class="value" id="act">-</div>
 <div class="bar"><div class="fill" id="fill" style="width:0"></div><div class="mark" id="mark"></div></div>
 <div class="sub" id="energy"></div>
 <div class="vitals" id="vitals">
   <div><div class="label">NEFES</div><div class="breath" id="breath">—</div>
        <div class="unit">nefes/dk</div></div>
   <div><div class="label">NABIZ</div><div class="heart" id="heart">—</div>
        <div class="unit">atış/dk · doğrulanmadı</div></div>
 </div>
 <div class="warn" id="warn"></div>
 <div class="boards" id="boards"></div>
</div><script>
const TR={yuruyor:"HAREKET VAR",hareketsiz:"HAREKETSİZ",baslatiliyor:"...",
          "kart yok":"KART YOK","veri bekleniyor":"VERİ BEKLENİYOR"};
async function u(){
 try{
  const d=await (await fetch('/status')).json();
  const e=document.getElementById('act');
  e.textContent=TR[d.activity]||d.activity; e.className='value '+d.activity;
  const pct=Math.min(100,(d.movement/(d.threshold*2))*100)||0;
  document.getElementById('fill').style.width=pct+'%';
  document.getElementById('mark').style.left='50%';
  document.getElementById('energy').textContent=
    d.movement!=null?('hareket enerjisi '+d.movement+'  ·  eşik '+d.threshold):'';
  document.getElementById('breath').textContent=d.breath??'—';
  document.getElementById('heart').textContent=d.heart??'—';
  const ok=d.vitals_reliable!==false;
  document.getElementById('vitals').className='vitals'+(ok?'':' unreliable');
  document.getElementById('warn').textContent=ok?'':
    'hareket var — bu değerler güvenilmez (yürüyüş temposu nabız bandına düşüyor)';
  document.getElementById('boards').innerHTML=
    Object.entries(d.boards||{}).map(([k,v])=>
      k+': '+(v.paket||0)+' paket, enerji '+(v.enerji??'-')).join('<br>')
    +(d.connected?'':'<br>BAĞLANTI YOK');
  document.body.style.background=d.activity==='yuruyor'?'#3a2414':'#0f1117';
 }catch(err){document.getElementById('boards').textContent='Sunucuya erişilemiyor';}
}
setInterval(u,700);u();
</script></body></html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/status")
def status():
    with state_lock:
        return jsonify(dict(state))


def auto_calibrate(srv, seconds=15):
    """İlk N saniyeyi 'hareketsiz taban' kabul edip eşiği belirler."""
    print(f"Kalibrasyon: {seconds} sn boyunca HAREKETSİZ kal (ya da odadan çık)...")
    samples = []
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(1)
        vals = []
        for r in sorted(srv.status()):  # kalibrasyon da ortalama kullanmalı
            lines = srv.recent(r, MOVE_WINDOW_SEC)
            if len(lines) < MIN_PACKETS:
                continue
            amp = parse_amplitude_matrix("\n".join(lines))
            if amp.shape[0] >= MIN_PACKETS:
                vals.append(movement_energy_bandpass(amp, amp.shape[0] / MOVE_WINDOW_SEC))
        if vals:
            samples.append(sum(vals) / len(vals))
            print(f"  taban {samples[-1]:.2f}")
    if len(samples) < 4:
        print(f"  yeterli örnek yok, varsayılan eşik kullanılıyor: {DEFAULT_THRESHOLD}")
        return DEFAULT_THRESHOLD
    # Hareketsiz/hareketli oranı ölçülen iki oturumda ~1.4-1.9x. Tabanın
    # 1.3 katı, iki oturumda da en iyi eşiğe yakın düşüyor.
    thr = float(np.percentile(samples, 75) * 1.3)
    print(f"  -> eşik = {thr:.2f}")
    return thr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--no-calibrate", action="store_true",
                    help="Kalibrasyonu atla ve sabit eşik kullan (ÖNERİLMEZ - "
                         "eşik oturumdan oturuma kayıyor)")
    args = ap.parse_args()

    srv = CsiUdpServer(keep_sec=BREATH_WINDOW_SEC + 10).start()
    print("Kartlar aranıyor...")
    for _ in range(10):
        time.sleep(1)
        if srv.status():
            break
    st = srv.status()
    if not st:
        raise SystemExit("Kart bulunamadı. Kartlar açık mı, hotspot'a bağlı mı?")
    print("Bulundu: " + ", ".join(f"{r} ({i['ip']})" for r, i in st.items()))

    if args.threshold:
        thr = args.threshold
    elif args.no_calibrate:
        thr = DEFAULT_THRESHOLD
    else:
        thr = auto_calibrate(srv)

    threading.Thread(target=processing_loop, args=(srv, thr), daemon=True).start()
    print(f"\nCanlı gösterge: http://localhost:5050   (eşik={thr:.2f})")
    app.run(host="0.0.0.0", port=5050, debug=False)
