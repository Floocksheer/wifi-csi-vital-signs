"""ESP32'den sürekli CSI okuyup canlı aktivite + kalp atışı tahmini üreten,
basit bir web arayüzünde gösteren sunucu.

Mimari (2026-08-19, canlı test geri bildirimi sonrası):
  1. HAREKET KAPISI - hareket enerjisi eşiği aşarsa "YÜRÜYOR" gösterilir,
     duruş modeli hiç çalıştırılmaz. (Model sadece hareketsiz duruş verisiyle
     eğitildi; kişi hareket ederken ona soru sormak yanlış cevap üretiyordu.)
  2. DURUŞ MODELİ - kişi hareketsizse otur/ayakta ayrımı yapılır.
  3. GÜVEN EŞİĞİ - model %65'ten az eminse "BELİRSİZ" gösterilir.
  4. OYLAMA - son birkaç tahminin çoğunluğu gösterilir (2026-08-24 eklendi;
     tek pencerenin doğruluğu %70 civarı olduğu için ekran titriyordu).

ÖNEMLİ (2026-08-24): calibrate_live.py ile ÖNCE kalibrasyon yap. Otur/ayakta
ayrımı sadece aynı kesintisiz bağlantı içinde çalışıyor - eski bir model
dosyası bugünkü oturumda işe yaramaz. Kalibrasyon ile bu sunucu arasında
kartı RESETLEME.

Kullanım:
    python calibrate_live.py     # önce bu (~90 sn)
    python live_server.py        # sonra bu
    Tarayıcıda: http://localhost:5050
"""
import threading
import time
from collections import deque

import joblib
import numpy as np
import serial
from flask import Flask, jsonify, render_template_string

from esp_port import detect_port
from activity_features import (parse_amplitude_matrix, extract_features,
                               movement_energy_bandpass)
from bpm_pipeline import estimate_bpm_zero_crossing, HEART_RATE_BAND

# Port ismi macOS'ta takılma sırasına göre değişiyor - otomatik bulunuyor.
# Board B (AP) artık güç adaptöründe olduğu için laptopta tek seri port var.
SERIAL_PORT = detect_port()
BAUD = 921600

WINDOW_SEC = 2           # duruş modeliyle aynı pencere (eğitimle tutarlı olmalı)
MOVE_WINDOW_SEC = 4      # hareket kapısı için daha uzun: 0.3 Hz bileşeni 2 sn'ye sığmıyor
UPDATE_INTERVAL_SEC = 1  # her saniye yeni tahmin -> gecikme ~1-2sn
MIN_PACKETS = 8

CONFIDENCE_THRESHOLD = 0.65
VOTE_WINDOW = 3  # son kaç tahmin oylanacak (3 x 1 sn = ~3 sn gecikme)

# Kalp atışı için daha uzun pencere gerekiyor: 0.8-2.0 Hz'lik bir salınımı
# görebilmek için en az birkaç periyot lazım, 2 saniye yetmez.
BPM_WINDOW_SEC = 12

# Kalibre edilmiş model tercih edilir; yoksa eski sabit modele düşer.
# Hareket eşiği de kalibrasyondan gelir - ortama/konuma göre değişiyor,
# sabit 3.3 değeri her kurulumda doğru değil (2026-08-24 ölçümü).
try:
    model_data = joblib.load("models/live_calibration.joblib")
    MOVEMENT_THRESHOLD = model_data["movement_threshold"]
    MOVE_WINDOW_SEC = model_data.get("movement_window_sec", MOVE_WINDOW_SEC)
    _acc = model_data.get("calibration_accuracy")
    print(f"Kalibre model yüklendi (eşik={MOVEMENT_THRESHOLD:.2f}"
          + (f", kalibrasyon doğruluğu={_acc:.0%})" if _acc else ")"))
except FileNotFoundError:
    model_data = joblib.load("models/activity_classifier.joblib")
    MOVEMENT_THRESHOLD = 3.3
    print("UYARI: kalibrasyon yok, eski model kullanılıyor. "
          "Doğru sonuç için önce: python calibrate_live.py")

clf = model_data["model"]
posture_names = model_data["class_names"]
recent_votes = deque(maxlen=VOTE_WINDOW)

buffer = deque()  # [(zaman, "CSI_DATA,...[...]"), ...]
buffer_lock = threading.Lock()

state = {
    "activity": "baslatiliyor",
    "confidence": None,
    "movement": None,
    "bpm": None,
    "packet_count": 0,
    "connected": False,
}
state_lock = threading.Lock()


def serial_reader():
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
        except Exception:
            with state_lock:
                state["connected"] = False
            time.sleep(2)
            continue

        with state_lock:
            state["connected"] = True

        try:
            while True:
                line = ser.readline()
                if not line:
                    continue
                text = line.decode("utf-8", errors="replace").rstrip()
                if text.startswith("CSI_DATA"):
                    now = time.time()
                    with buffer_lock:
                        buffer.append((now, text))
                        cutoff = now - BPM_WINDOW_SEC  # en uzun ihtiyaç kadar tut
                        while buffer and buffer[0][0] < cutoff:
                            buffer.popleft()
        except Exception:
            with state_lock:
                state["connected"] = False
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(1)


def processing_loop():
    while True:
        time.sleep(UPDATE_INTERVAL_SEC)
        now = time.time()
        with buffer_lock:
            recent = [t for ts, t in buffer if ts >= now - WINDOW_SEC]
            move_raw = [t for ts, t in buffer if ts >= now - MOVE_WINDOW_SEC]
            bpm_window = [t for ts, t in buffer if ts >= now - BPM_WINDOW_SEC]

        if len(recent) < MIN_PACKETS:
            continue

        amp = parse_amplitude_matrix("\n".join(recent))
        if amp.shape[0] < MIN_PACKETS:
            continue

        # Hareket, duruştan DAHA UZUN pencerede ölçülüyor (bantgeçiren filtre
        # 0.3 Hz'i görebilsin diye). fs sabit varsayılamaz - paket hızı
        # dalgalanıyor, o yüzden pencereden ölçülüyor.
        amp_move = parse_amplitude_matrix("\n".join(move_raw))
        if amp_move.shape[0] >= MIN_PACKETS:
            energy = movement_energy_bandpass(amp_move,
                                              len(amp_move) / MOVE_WINDOW_SEC)
        else:
            energy = movement_energy_bandpass(amp, len(amp) / WINDOW_SEC)

        # 1. Hareket kapısı
        if energy > MOVEMENT_THRESHOLD:
            raw, confidence = "yuruyor", None
        else:
            # 2. Duruş modeli + 3. güven eşiği
            proba = clf.predict_proba(extract_features(amp).reshape(1, -1))[0]
            best = int(proba.argmax())
            confidence = float(proba[best])
            raw = posture_names[best] if confidence >= CONFIDENCE_THRESHOLD else "belirsiz"

        # 4. Oylama: tek pencere ~%70 doğru olduğu için ham tahmin titriyor.
        # Yürümede oylama yok - hareket anında tepki gecikmemeli.
        recent_votes.append(raw)
        if raw == "yuruyor":
            activity = raw
        else:
            votes = [v for v in recent_votes if v != "yuruyor"]
            activity = max(set(votes), key=votes.count) if votes else raw

        # Kalp atışı: daha uzun pencereden, ortalama paket hızıyla
        bpm = None
        if len(bpm_window) >= 40:
            amp_long = parse_amplitude_matrix("\n".join(bpm_window))
            if amp_long.shape[0] >= 40:
                approx_fs = len(amp_long) / BPM_WINDOW_SEC
                try:
                    bpm = estimate_bpm_zero_crossing(
                        amp_long.mean(axis=1), approx_fs, HEART_RATE_BAND
                    )
                except Exception:
                    bpm = None

        with state_lock:
            state["activity"] = activity
            state["confidence"] = round(confidence, 2) if confidence is not None else None
            state["movement"] = round(energy, 2)
            state["bpm"] = round(bpm, 1) if bpm else None
            state["packet_count"] = len(recent)


app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>WiFi CSI Canlı Gösterge</title>
<style>
  body { background: #0f1117; color: #e8e8e8;
         font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; transition: background 0.4s; }
  .card { text-align: center; }
  .label { font-size: 1rem; letter-spacing: 0.15em; opacity: 0.5; margin-bottom: 0.4rem; }
  .value { font-size: 4.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 0.4rem; }
  .sub { font-size: 0.95rem; opacity: 0.45; margin-bottom: 2.5rem; }
  .bpm { color: #ff6b6b; font-size: 3rem; }
  .otur, .sit { color: #4dabf7; } .ayakta, .stand { color: #51cf66; }
  .yuruyor { color: #ffa94d; } .belirsiz { color: #868e96; }
  .status { font-size: 0.8rem; opacity: 0.35; margin-top: 1.5rem; }
</style>
</head>
<body>
  <div class="card">
    <div class="label">AKTİVİTE</div>
    <div class="value" id="activity">-</div>
    <div class="sub" id="activitySub"></div>
    <div class="label">KALP ATIŞI</div>
    <div class="value bpm" id="bpm">-</div>
    <div class="status" id="status"></div>
  </div>
<script>
const TR = {otur:"OTURUYOR", ayakta:"AYAKTA", yuruyor:"YÜRÜYOR",
            sit:"OTURUYOR", stand:"AYAKTA",
            belirsiz:"BELİRSİZ", baslatiliyor:"..."};
async function update() {
  try {
    const d = await (await fetch('/status')).json();
    const el = document.getElementById('activity');
    el.textContent = TR[d.activity] || d.activity;
    el.className = 'value ' + d.activity;
    document.getElementById('activitySub').textContent =
      d.confidence !== null ? ('güven: %' + Math.round(d.confidence*100)) : '';
    document.getElementById('bpm').textContent = d.bpm ? d.bpm + ' BPM' : '...';
    document.getElementById('status').textContent =
      (d.connected ? 'Bağlı' : 'BAĞLANTI YOK') +
      ' — hareket enerjisi: ' + d.movement + ' — ' + d.packet_count + ' paket';
    document.body.style.background = d.activity === 'yuruyor' ? '#3a2414' : '#0f1117';
  } catch (e) {
    document.getElementById('status').textContent = 'Sunucuya erişilemiyor';
  }
}
setInterval(update, 700);
update();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/status")
def status():
    with state_lock:
        return jsonify(dict(state))


if __name__ == "__main__":
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=processing_loop, daemon=True).start()
    print("Canlı gösterge: http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)
