"""Sesli yönlendirmeli kayıt - UDP mimarisi için (2026-08-24 akşam).

guided_capture.py'nin (seri port) UDP karşılığı. Fark:

  * İKİ karttan aynı anda veri geliyor, her biri ayrı dosyaya yazılıyor.
  * Faz sınırları artık ESP saatiyle DEĞİL, laptobun saatiyle işaretleniyor.
    Sebep: iki kartın saatleri bağımsız (her biri kendi açılışından beri
    sayıyor), ortak bir zaman ekseni gerekiyor. Sunucu her satırın geliş
    anını zaten kaydediyor; ağ gecikmesi yerel WiFi'da birkaç milisaniye,
    3 saniyelik geçiş paylarımızın yanında önemsiz.

Kullanım:
    python guided_capture_udp.py --cues "kıpırdama,yürü,kıpırdama,yürü" \
        --phase-sec 10 --output ../data/udp_session/test
"""
import argparse
import json
import pathlib
import time

from csi_udp_server import CsiUdpServer
from guided_capture import speak

POSTURES = ["otur", "ayakta"]


def main():
    ap = argparse.ArgumentParser(description="Sesli yönlendirmeli UDP CSI kaydı")
    ap.add_argument("--phases", type=int, default=12)
    ap.add_argument("--phase-sec", type=float, default=12)
    ap.add_argument("--cues", default=None,
                    help="Virgülle ayrılmış komutlar (varsayılan otur/ayakta dönüşümlü)")
    ap.add_argument("--output", required=True, help="Uzantısız çıktı yolu")
    ap.add_argument("--settle-sec", type=float, default=6,
                    help="Kayda başlamadan önce kartların bulunması için beklenecek süre")
    args = ap.parse_args()

    if args.cues:
        cues = [c.strip() for c in args.cues.split(",")]
        args.phases = len(cues)
    else:
        cues = [POSTURES[i % 2] for i in range(args.phases)]
    unique = list(dict.fromkeys(cues))
    labels = [unique.index(c) for c in cues]

    total = args.phases * args.phase_sec
    print(f"Protokol: {args.phases} faz x {args.phase_sec:.0f} sn = {total:.0f} sn")
    print(f"Komutlar: {' -> '.join(cues)}\n")

    # keep_sec: tüm kayıt + pay. Kısa tutulursa başlangıç silinir.
    srv = CsiUdpServer(keep_sec=total + args.settle_sec + 30).start()

    print("Kartlar aranıyor...")
    deadline = time.time() + args.settle_sec
    while time.time() < deadline:
        time.sleep(1)
    st = srv.status()
    if not st:
        srv.stop()
        raise SystemExit("HATA: hiçbir kart bulunamadı. Kartlar açık mı, "
                         "hotspot'a bağlı mı, laptop aynı ağda mı?")
    print("Bulunan kartlar: " + ", ".join(
        f"{role} ({info['ip']})" for role, info in st.items()))

    speak("Hazır ol")
    time.sleep(2)
    for n in (3, 2, 1):
        speak(str(n))
        time.sleep(1)

    phases = []
    t0 = time.time()
    try:
        for i, cue in enumerate(cues):
            while time.time() < t0 + i * args.phase_sec:
                time.sleep(0.005)
            now = time.time()
            speak(cue)
            phases.append({"phase": i, "posture": cue, "label": labels[i],
                           "recv_ts_start": now})
            print(f"  faz {i:2d}: {cue}")
        while time.time() < t0 + total:
            time.sleep(0.01)
        speak("Bitti")
    finally:
        end_ts = time.time()
        time.sleep(0.5)   # son paketler gelsin
        written = srv.save(args.output)
        srv.stop()

    for i, p in enumerate(phases):
        p["recv_ts_end"] = (phases[i + 1]["recv_ts_start"]
                            if i + 1 < len(phases) else end_ts)

    meta_path = pathlib.Path(args.output).with_suffix(".json")
    with open(meta_path, "w") as f:
        json.dump({"phase_sec": args.phase_sec, "cues": cues,
                   "postures": unique, "phases": phases,
                   "files": written,
                   "note": "recv_ts_* laptop saati; CSV'nin son sutunu recv_time ayni saat"},
                  f, indent=2)

    print()
    for role, info in srv.status().items():
        print(f"  {role}: {info['paket']} paket ({info['paket'] / total:.1f} Hz)"
              f" -> {written.get(role)}")
    print(f"  fazlar -> {meta_path}")


if __name__ == "__main__":
    main()
