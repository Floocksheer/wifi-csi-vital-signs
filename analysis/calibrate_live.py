"""Canlı sistem için sesli yönlendirmeli kalibrasyon: kaydet + eğit + kaydet.

NEDEN BÖYLE: 2026-08-24 fizibilite testi gösterdi ki otur/ayakta ayrımı ancak
AYNI kesintisiz bağlantı içinde çalışıyor (%70.5, p=0.032); ayrı oturumlar arası
şans seviyesinde (%52.9). Bu yüzden model önceden eğitilip saklanamaz - canlı
kullanımdan hemen önce, aynı oturumda kalibre edilmeli.

MİMARİ (live_server.py ile aynı olmalı):
  1. Hareket kapısı - eşiği aşarsa "yürüyor/hareket". Eşik SABİT DEĞİL, bu
     kalibrasyonun kendi verisinden hesaplanıyor (ortamdan ortama değişiyor).
  2. Hareketsizse duruş modeli - otur/ayakta.

Kullanım:
    python calibrate_live.py
    (bittiğinde models/live_calibration.joblib yazılır, sonra live_server.py çalıştır)
"""
import argparse
import json
import pathlib
import time

import joblib
import numpy as np
import serial
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut

from esp_port import detect_port
from activity_features import (extract_features, movement_energy_bandpass,
                               MOVEMENT_WINDOW_SEC)
from guided_capture import SerialReader, speak, HEADER
from evaluate_guided_session import parse_with_timestamps

WINDOW_SEC = 2.0
WINDOW_STEP_SEC = 1.0   # %50 örtüşme -> daha çok eğitim örneği
TRANSITION_MARGIN_SEC = 3.0
MODEL_PATH = "models/live_calibration.joblib"

# Sırayla söylenecek komutlar. Her sınıf 3 kez geçiyor: 2 tekrarla yapılan ilk
# denemede (2026-08-24) model duruşu değil ZAMANI öğrendi - genlik kayıt boyunca
# sürekli kaydığı için "erken faz / geç faz" ayrımını sınıf sandı ve ayakta ile
# yürüme tamamen yer değiştirdi (3-sınıf doğruluk %30, şans %33). 3 tekrar,
# LeaveOneGroupOut'ta her sınıftan 2 faz eğitimde bırakır.
CUES = ["otur", "ayakta", "yürü"] * 3
STILL_CUES = {"otur", "ayakta"}


def record(port, baud, phase_sec, out_base):
    ser = serial.Serial(port, baud, timeout=1)
    reader = SerialReader(ser)
    reader.start()

    speak("Kalibrasyon başlıyor")
    time.sleep(2)
    for n in (3, 2, 1):
        speak(str(n))
        time.sleep(1)

    phases = []
    t_start = time.time()
    try:
        for i, cue in enumerate(CUES):
            while time.time() < t_start + i * phase_sec:
                time.sleep(0.005)
            esp_ts = reader.latest_esp_ts
            speak(cue)
            phases.append({"phase": i, "posture": cue, "esp_ts_start": esp_ts})
            print(f"  faz {i}: {cue}")
        while time.time() < t_start + len(CUES) * phase_sec:
            time.sleep(0.01)
        speak("Bitti")
    finally:
        reader.stop()
        time.sleep(0.3)
        ser.close()

    for i, p in enumerate(phases):
        p["esp_ts_end"] = (phases[i + 1]["esp_ts_start"] if i + 1 < len(phases)
                           else reader.latest_esp_ts)

    csv_path = pathlib.Path(out_base).with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w") as f:
        f.write(HEADER)
        for line in reader.lines:
            f.write(line + "\n")
    with open(pathlib.Path(out_base).with_suffix(".json"), "w") as f:
        json.dump({"phases": phases, "cues": CUES}, f, indent=2)

    n = len(reader.lines)
    print(f"\n{n} paket ({n / (len(CUES) * phase_sec):.1f} Hz) -> {csv_path}")
    return str(csv_path), phases


def windows_from_phases(times, amp, phases, win_sec=WINDOW_SEC,
                        step_sec=WINDOW_STEP_SEC):
    """Her fazın geçiş kısmını atıp örtüşmeli pencereler üretir.

    Pencere boyutu iki amaç için farklı: duruş modeli 2 sn (canlı gecikme az
    olsun), hareket kapısı 4 sn (0.3 Hz'lik bileşeni görebilmek için).
    """
    out = []
    for p in phases:
        start = p["esp_ts_start"] + TRANSITION_MARGIN_SEC
        end = p["esp_ts_end"] - 0.3
        w = start
        while w + win_sec <= end:
            sel = np.where((times >= w) & (times < w + win_sec))[0]
            if len(sel) >= 20:
                out.append((amp[sel], p["posture"], p["phase"]))
            w += step_sec
    return out


def main():
    ap = argparse.ArgumentParser(description="Canlı sistem kalibrasyonu")
    ap.add_argument("--port", default=None)
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--phase-sec", type=float, default=12)
    ap.add_argument("--output", default="../data/continuous_session/calibration")
    args = ap.parse_args()
    args.port = detect_port(args.port)

    print(f"Protokol: {' -> '.join(CUES)}  ({args.phase_sec:.0f} sn/faz, "
          f"toplam {len(CUES) * args.phase_sec:.0f} sn)")
    print("Komutu duyunca hemen o pozisyona geç. 'yürü' derse kayıt boyunca yürü.\n")

    csv_path, phases = record(args.port, args.baud, args.phase_sec, args.output)
    times, amp = parse_with_timestamps(csv_path)
    fs = len(times) / (times[-1] - times[0])
    print(f"ortalama paket hızı: {fs:.1f} Hz")

    # Hareket kapısı: uzun pencere + bantgeçiren (ölçüm gürültüsünü ayıklamak
    # için - bkz. activity_features.movement_energy_bandpass)
    move_wins = windows_from_phases(times, amp, phases, MOVEMENT_WINDOW_SEC, 1.0)
    energies = np.array([movement_energy_bandpass(w, fs) for w, _, _ in move_wins])
    is_still = np.array([c in STILL_CUES for _, c, _ in move_wins])

    still_e, walk_e = energies[is_still], energies[~is_still]

    print(f"\n--- Hareket kapısı ---")
    print(f"  hareketsiz (otur+ayakta): ort={still_e.mean():.2f} "
          f"p90={np.percentile(still_e, 90):.2f}")
    print(f"  yürüme                  : ort={walk_e.mean():.2f} "
          f"p10={np.percentile(walk_e, 10):.2f}")

    if walk_e.mean() <= still_e.mean():
        # 2026-08-24'te bu oldu: kişi kartların TAM ARASINDA dururken vücut
        # kanalı domine ediyor; yürüyüp bölgeden çıkınca yol temizlenip sinyal
        # SAKİNLEŞİYOR. Yani "hareket = daha çok dalgalanma" varsayımı bozuluyor.
        # Böyle bir durumda eşiği ikisinin arasına koymak sürekli yanlış alarm
        # verir; sadece olağandışı hareketde tetiklenecek şekilde yükseltiyoruz.
        threshold = float(np.percentile(still_e, 98))
        print(f"  ⚠️  YÜRÜME, HAREKETSİZDEN DAHA SAKİN ÇIKTI - geometri sorunu.")
        print(f"     Kişi kartların tam arasındaysa bu beklenir; ön çaprazda")
        print(f"     durmayı dene. Eşik güvenli tarafa (hareketsiz p98) çekildi.")
        print(f"  -> eşik = {threshold:.2f} (yürüme tespiti bu kurulumda çalışmaz)")
    else:
        threshold = float((np.percentile(still_e, 90) + np.percentile(walk_e, 10)) / 2)
        print(f"  -> eşik = {threshold:.2f}")
        print(f"  yürüme doğru yakalanan  : {(walk_e > threshold).mean() * 100:.0f}%")
        print(f"  hareketsizken yanlış alarm: {(still_e > threshold).mean() * 100:.0f}%")

    # Duruş modeli SADECE hareketsiz pencerelerle eğitilir - yürüme pencereleri
    # modele hiç girmez, onları hareket kapısı zaten yakalıyor.
    post_wins = windows_from_phases(times, amp, phases)
    still_wins = [(w, c, g) for (w, c, g) in post_wins if c in STILL_CUES]
    X = np.array([extract_features(w) for w, _, _ in still_wins])
    y = np.array([0 if c == "otur" else 1 for _, c, _ in still_wins])
    groups = np.array([g for _, _, g in still_wins])

    accs = []
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        c = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
        c.fit(X[tr], y[tr])
        accs.append(c.score(X[te], y[te]))
    print(f"\n--- Duruş modeli (otur/ayakta) ---")
    print(f"  {len(y)} pencere (otur={int((y == 0).sum())}, ayakta={int((y == 1).sum())})")
    print(f"  fazlar-arası doğruluk: {np.mean(accs):.1%}")
    if np.mean(accs) < 0.6:
        print("  ⚠️  DÜŞÜK - duruş ayrımı bu konumda güvenilir olmayacak.")
        print("     Kartları yükseltip (ayakta göğüs hizası) tekrar dene.")

    clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    clf.fit(X, y)

    pathlib.Path("models").mkdir(exist_ok=True)
    joblib.dump({
        "model": clf,
        "class_names": ["otur", "ayakta"],
        "window_sec": WINDOW_SEC,
        "movement_window_sec": MOVEMENT_WINDOW_SEC,
        "movement_threshold": threshold,
        "calibration_fs": float(fs),
        "calibration_accuracy": float(np.mean(accs)),
        "calibrated_at": time.time(),
    }, MODEL_PATH)
    print(f"\nKaydedildi -> {MODEL_PATH}")
    print("Şimdi çalıştır: python live_server.py   (kartı RESETLEME!)")


if __name__ == "__main__":
    main()
