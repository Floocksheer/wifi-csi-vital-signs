"""Sesli komutlarla yönlendirilen, tek kesintisiz otur/ayakta kaydı (2026-08-24).

NEDEN GEREKLİ: İlk kesintisiz kayıt denemesinde kullanıcı kendi kronometresini
kullandı; kayıt saati ile kronometre senkron olmadı ve hareket zirveleri
beklenen faz sınırlarına düşmedi -> etiketler güvenilmez oldu.

ÇÖZÜM: Zamanlamayı bilgisayar yönetiyor. macOS `say` ile tam doğru anlarda
sesli komut veriliyor ve her komutun anındaki ESP zaman damgası kaydediliyor.
Böylece etiketler ile veri AYNI saatten geliyor, senkron hatası imkansız.

Çıktılar:
  <output>.csv   - ham CSI (capture_csi.py ile aynı format)
  <output>.json  - faz sınırları (ESP zaman damgası cinsinden) + protokol bilgisi

Kullanım:
    python guided_capture.py --output ../data/continuous_session/guided_01
"""
import argparse
import json
import pathlib
import subprocess
import threading
import time

import serial

from esp_port import detect_port

HEADER = (
    "type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,"
    "aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,"
    "secondary_channel,local_timestamp,ant,sig_len,rx_state,real_time_set,"
    "real_timestamp,len,CSI_DATA\n"
)

POSTURES = ["otur", "ayakta"]


class SerialReader(threading.Thread):
    """Arka planda sürekli okur; son görülen ESP zaman damgasını canlı tutar.

    Komut anında bu damgayı okuyarak faz sınırını ESP'nin kendi saatiyle
    işaretliyoruz - laptop saati ile ESP saati arasında kayma olsa bile
    etiketler veriyle hizalı kalır.
    """

    def __init__(self, ser):
        super().__init__(daemon=True)
        self.ser = ser
        self.lines = []
        self.latest_esp_ts = None
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            line = self.ser.readline()
            if not line:
                continue
            text = line.decode("utf-8", errors="replace").rstrip()
            if not text.startswith("CSI_DATA"):
                continue
            fields = text.split(",")
            if len(fields) < 24:
                continue
            try:
                self.latest_esp_ts = float(fields[23])
            except ValueError:
                continue
            self.lines.append(text)

    def stop(self):
        self._stop.set()


def speak(text):
    """Bloklamadan konuş - konuşma süresi faz zamanlamasını kaydırmasın."""
    subprocess.Popen(["say", "-v", "Yelda", text],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description="Sesli yönlendirmeli CSI kaydı")
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--phases", type=int, default=12, help="Kaç faz (çift sayı olmalı)")
    parser.add_argument("--phase-sec", type=float, default=12, help="Her faz kaç saniye")
    parser.add_argument("--cues", default=None,
                        help="Virgülle ayrılmış özel komut listesi (varsayılan: otur/ayakta "
                             "dönüşümlü). Aynı komut tekrar ederse aynı etiketi alır.")
    parser.add_argument("--output", required=True, help="Uzantısız çıktı yolu")
    args = parser.parse_args()
    args.port = detect_port(args.port)

    if args.cues:
        cues = [c.strip() for c in args.cues.split(",")]
        args.phases = len(cues)
    else:
        cues = [POSTURES[i % 2] for i in range(args.phases)]
    # Aynı metin -> aynı etiket (ör. "dur" iki kez geçerse ikisi de sınıf 0)
    unique = list(dict.fromkeys(cues))
    labels = [unique.index(c) for c in cues]

    out_base = pathlib.Path(args.output)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")

    total = args.phases * args.phase_sec
    print(f"Protokol: {args.phases} faz x {args.phase_sec:.0f} sn = {total:.0f} sn")
    print("Sesli komutları dinle. Komut gelince HEMEN o pozisyona geç, sonra kıpırdama.\n")

    # DİKKAT: --reset YOK. Reset = yeniden bağlanma = kayıt-özel radyo imzası
    # (test etmeye çalıştığımız sorunun ta kendisi).
    ser = serial.Serial(args.port, args.baud, timeout=1)
    reader = SerialReader(ser)
    reader.start()

    # Akışın oturması + kullanıcının hazırlanması için geri sayım
    speak("Hazır ol")
    time.sleep(2)
    for n in (3, 2, 1):
        speak(str(n))
        time.sleep(1)

    phases = []
    t_start = time.time()
    try:
        for i in range(args.phases):
            target = t_start + i * args.phase_sec
            while time.time() < target:
                time.sleep(0.005)
            posture = cues[i]
            esp_ts = reader.latest_esp_ts
            speak(posture)
            phases.append({
                "phase": i,
                "posture": posture,
                "label": labels[i],
                "esp_ts_start": esp_ts,
                "wall_ts_start": time.time(),
            })
            print(f"  faz {i:2d}: {posture:20s} (ESP saati: {esp_ts})")

        while time.time() < t_start + total:
            time.sleep(0.01)
        speak("Bitti")
    finally:
        reader.stop()
        time.sleep(0.3)
        ser.close()

    # Faz bitişleri: bir sonraki fazın başlangıcı, sonuncusu için son paket
    for i, p in enumerate(phases):
        p["esp_ts_end"] = (phases[i + 1]["esp_ts_start"] if i + 1 < len(phases)
                           else reader.latest_esp_ts)

    with open(csv_path, "w") as f:
        f.write(HEADER)
        for line in reader.lines:
            f.write(line + "\n")

    with open(json_path, "w") as f:
        json.dump({
            "phase_sec": args.phase_sec,
            "n_phases": args.phases,
            "postures": unique,
            "phases": phases,
            "note": "esp_ts_* degerleri CSV'deki real_timestamp sutunuyla ayni saat",
        }, f, indent=2)

    n = len(reader.lines)
    print(f"\nBitti. {n} CSI paketi ({n / total:.1f} Hz)")
    print(f"  veri  -> {csv_path}")
    print(f"  fazlar-> {json_path}")


if __name__ == "__main__":
    main()
