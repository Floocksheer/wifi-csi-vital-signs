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
import random
import time

from csi_udp_server import CsiUdpServer
from voice import speak

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
    # --- kayıt koşulları (2026-08-25) ---
    # Konum etiketi OLMADAN doğru doğrulama yapılamıyor: doğrulama gruplarını
    # fazlara göre ayırınca aynı konumun başka bir fazı eğitimde kalıyor, model
    # duruş yerine konumu ezberleyip test fazında onu kullanabiliyor -> doğruluk
    # şişiyor. Doğru doğrulama Leave-One-POSITION-Out, o da bu etikete muhtaç.
    # Bkz. docs/OTUR_AYAKTA_VERI_TOPLAMA_PLANI.md Bölüm 8.1
    ap.add_argument("--position", default=None,
                    help="Kişinin durduğu nokta (ör. P1) - doğrulama bunu grup olarak kullanır")
    ap.add_argument("--height", type=float, default=None,
                    help="Kartların yerden yüksekliği (cm). Geometri değişirse "
                         "veriler BİRLİKTE eğitilemez - bu yüzden kayda yazılıyor.")
    ap.add_argument("--session", default=None,
                    help="Oturum kimliği (ör. tur1) - oturumlar arası kaymayı ayırmak için")
    # --- faz süresi rastgeleliği (2026-08-25) ---
    # NEDEN: sabit faz süresinde kişi bir sonraki komutun NE ZAMAN geleceğini
    # öğreniyor ve ona hazırlanıyor. h115 kaydında ölçüldü: "otur" komutunda
    # zirve 0.15-0.25 sn sonra, "ayakta" komutunda 2.5-3.75 sn sonra. Bu FİZİK
    # değil TEPKİ SÜRESİ farkı - eğitim verisinde mükemmel ayırır, gerçekte
    # çöker. Süre rastgele olunca kişi anticipe edemiyor.
    ap.add_argument("--jitter", type=float, default=0.0,
                    help="Faz süresine +/- bu kadar saniye rastgelelik kat "
                         "(tepki süresi ezberini kırar; geçiş verisinde ÖNERİLİR)")
    ap.add_argument("--seed", type=int, default=None,
                    help="Rastgelelik tohumu (tekrarlanabilirlik için)")
    args = ap.parse_args()

    if args.cues:
        cues = [c.strip() for c in args.cues.split(",")]
        args.phases = len(cues)
    else:
        cues = [POSTURES[i % 2] for i in range(args.phases)]
    unique = list(dict.fromkeys(cues))
    labels = [unique.index(c) for c in cues]

    # Faz süreleri önceden belirleniyor: jitter varsa her faz farklı uzunlukta.
    # Zamanlama kümülatif (sabit phase_sec varsayımı kalktı).
    rng = random.Random(args.seed)
    durs = [args.phase_sec + (rng.uniform(-args.jitter, args.jitter)
                              if args.jitter else 0.0)
            for _ in cues]
    offsets, acc = [], 0.0
    for d in durs:
        offsets.append(acc)
        acc += d
    total = acc

    print(f"Protokol: {args.phases} faz x {args.phase_sec:.0f} sn"
          + (f" (±{args.jitter:.0f} sn rastgele)" if args.jitter else "")
          + f" = {total:.0f} sn")
    print(f"Komutlar: {' -> '.join(cues)}")
    if args.position or args.height or args.session:
        print(f"Koşullar: konum={args.position}  yükseklik={args.height}  "
              f"oturum={args.session}")
    else:
        print("⚠️  --position verilmedi: bu kayıt Leave-One-Position-Out "
              "doğrulamasında KULLANILAMAZ.")
    print()

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
            while time.time() < t0 + offsets[i]:
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
                   "position": args.position, "height_cm": args.height,
                   "session": args.session,
                   "jitter": args.jitter, "durations": durs,
                   "note": "recv_ts_* laptop saati; CSV'nin son sutunu recv_time ayni saat"},
                  f, indent=2)

    print()
    for role, info in srv.status().items():
        print(f"  {role}: {info['paket']} paket ({info['paket'] / total:.1f} Hz)"
              f" -> {written.get(role)}")
    print(f"  fazlar -> {meta_path}")


if __name__ == "__main__":
    main()
