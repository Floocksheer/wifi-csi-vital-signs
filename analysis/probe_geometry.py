"""Kart YÜKSEKLİĞİNİ ölçerek seçmek için hızlı tarama aracı (2026-08-25).

NEDEN VAR: Otur/ayakta ayrımı 2026-08-24'te çöktü (%40-46, şans altı). Kök
neden 2026-08-25'te sayısallaştırıldı - kartlar masa hizasındayken:

    duruşlar arası fark   : 0.30 / 0.40
    aynı duruşun konumdan konuma yayılımı : 2.68 / 0.88   <-- fark bunun içinde kayboluyor

Yani sorun algoritmada değil, GEOMETRİDE: masa hizasında gövde her iki
duruşta da hattı aynı şekilde kesiyor. Kartlar omuz hizasına çıkarılırsa
ayakta omuz/boyun hattı keser, otururken baş hattın ALTINDA kalır - fark
fiziksel olarak zorunlu hale gelir.

Doğru yükseklik teoriden güvenilir hesaplanamaz (2.4 GHz'de birinci Fresnel
bölgesi ~±40 cm, oturan baş ile ayakta omuz bu payın içinde kalabiliyor).
Bu yüzden ÖLÇEREK seçiyoruz: bu script bir yükseklikte ~80 saniyede tek bir
sayı üretir, sen 2-3 yükseklik dene, en iyisini seç.

ÖLÇTÜĞÜ SAYI - "ayrım gücü" (Cohen's d):

    d = |ortalama(ayakta) - ortalama(otur)| / duruş-içi standart sapma

    d < 1.0  -> fark gürültünün içinde, bu yükseklik İŞE YARAMAZ
    d 1.0-2.0 -> sınırda, umut var
    d > 2.0  -> fark gürültüden büyük, sınıflandırma mümkün  ✓

⚠️ Bu bir TARAMA aracı, kanıt değil: sınıf başına 3 faz var, standart sapma
kaba. Amacı "hangi yükseklik" sorusunu ucuza cevaplamak. Asıl doğrulama
konum-değişken protokolle yapılır (bkz. docs/PROJE_DURUM_VE_KARARLAR.md).

⚠️ Bu testte kişi TEK BİR NOKTADA durur. Burada çıkan yüksek skor "otur/ayakta
çözüldü" demek DEĞİLDİR - sabit konumda alınan sonuç yanıltıcıdır (projenin en
pahalı dersi). Burada sadece yükseklikleri BİRBİRİYLE kıyaslıyoruz.

Kullanım:
    python probe_geometry.py --height 145
    python probe_geometry.py --height 160
    # -> en yüksek d hangisindeyse o yüksekliği seç, sonra asıl veri toplamaya geç
"""
import argparse
import json
import pathlib
import time

import numpy as np

from csi_udp_server import CsiUdpServer
from voice import speak
from evaluate_udp_session import parse_udp_csv, phase_windows, logo_accuracy
from activity_features import VALID_SUBCARRIERS, extract_features

SETTLE_MARGIN_SEC = 4.0   # komuttan sonra geçiş hareketi bitsin diye atılan pay
TAIL_MARGIN_SEC = 0.5


def level_series(amp):
    """Paket başına geçerli alt-taşıyıcı ortalaması = 'sinyal seviyesi'."""
    v = amp[:, VALID_SUBCARRIERS] if amp.shape[1] > max(VALID_SUBCARRIERS) else amp
    return v.mean(axis=1)


def capture(args, cues):
    total = len(cues) * args.phase_sec
    srv = CsiUdpServer(keep_sec=total + args.settle_sec + 30).start()

    print("Kartlar aranıyor...")
    deadline = time.time() + args.settle_sec
    while time.time() < deadline:
        time.sleep(1)
    st = srv.status()
    if not st:
        srv.stop()
        raise SystemExit(
            "HATA: kart bulunamadı.\n"
            "  1) Kartlar güçte mi?\n"
            "  2) 'ipconfig getifaddr en0' -> laptop kartlarla aynı /28 ağda mı?\n"
            "     (macOS sessizce kurumsal WiFi'ye kayabiliyor - bilinen tuzak)")
    print("Bulundu: " + ", ".join(f"{r} ({i['ip']})" for r, i in st.items()))

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
            phases.append({"phase": i, "posture": cue,
                           "label": 0 if cue == "otur" else 1,
                           "recv_ts_start": now})
            print(f"  faz {i}: {cue}")
        while time.time() < t0 + total:
            time.sleep(0.01)
        speak("Bitti")
    finally:
        end_ts = time.time()
        time.sleep(0.5)
        written = srv.save(args.output)
        srv.stop()

    for i, p in enumerate(phases):
        p["recv_ts_end"] = (phases[i + 1]["recv_ts_start"]
                            if i + 1 < len(phases) else end_ts)

    meta = {"phase_sec": args.phase_sec, "cues": cues,
            "postures": ["otur", "ayakta"], "phases": phases,
            "files": written,
            "height_cm": args.height, "position": args.position,
            "note": "geometri tarama kaydı - kişi TEK noktada durdu"}
    with open(pathlib.Path(args.output).with_suffix(".json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


def analyse(meta):
    print(f"\n{'='*66}\nSONUÇ - kart yüksekliği {meta['height_cm']} cm\n{'='*66}")
    results = {}

    for role, path in sorted(meta["files"].items()):
        t, a = parse_udp_csv(path)
        if len(t) == 0:
            print(f"  {role}: VERİ YOK")
            continue
        fs = len(t) / (t[-1] - t[0])

        # --- faz başına kararlı seviye ---
        per_posture = {"otur": [], "ayakta": []}
        for p in meta["phases"]:
            sel = np.where((t >= p["recv_ts_start"] + SETTLE_MARGIN_SEC) &
                           (t < p["recv_ts_end"] - TAIL_MARGIN_SEC))[0]
            if len(sel) < 50:
                continue
            per_posture[p["posture"]].append(float(np.median(level_series(a[sel]))))

        sit, stand = per_posture["otur"], per_posture["ayakta"]
        if len(sit) < 2 or len(stand) < 2:
            print(f"  {role}: yeterli faz yok")
            continue

        pooled = np.sqrt((np.var(sit, ddof=1) + np.var(stand, ddof=1)) / 2)
        d = abs(np.mean(stand) - np.mean(sit)) / pooled if pooled > 0 else 0.0

        print(f"\n  {role}  ({len(t)} paket, {fs:.0f} Hz)")
        print(f"    otur   : " + " ".join(f"{v:6.2f}" for v in sit)
              + f"   ort={np.mean(sit):6.2f}")
        print(f"    ayakta : " + " ".join(f"{v:6.2f}" for v in stand)
              + f"   ort={np.mean(stand):6.2f}")
        print(f"    fark={abs(np.mean(stand)-np.mean(sit)):.2f}  "
              f"duruş-içi sapma={pooled:.2f}")
        print(f"    AYRIM GÜCÜ d = {d:.2f}   "
              f"{'✓ iyi' if d > 2 else ('~ sınırda' if d > 1 else '✗ yetersiz')}")

        # --- pencere seviyesinde sınıflandırma (fazlar = gruplar) ---
        wins = phase_windows(t, a, meta["phases"], 2.0)
        if len(wins) >= 6:
            X = np.array([extract_features(w) for w, _, _, _, _ in wins])
            y = np.array([lbl for _, lbl, _, _, _ in wins])
            g = np.array([ph for _, _, ph, _, _ in wins])
            if len(set(y)) == 2:
                acc, sd = logo_accuracy(X, y, g)
                print(f"    (aynı noktada LOGO doğruluk: {acc:.0%} ±{sd:.0%} "
                      f"- şans %50, KONUM SABİT olduğu için yanıltıcı olabilir)")
        results[role] = d

    if results:
        best = max(results.values())
        print(f"\n  >>> Bu yükseklikte en iyi kart d = {best:.2f}")
        print("  Not: bunu diğer yüksekliklerle kıyasla, en büyük d'yi seç.")
        if best < 1.0:
            print("  ⚠️ d<1 - bu yükseklik işe yaramıyor, belirgin şekilde "
                  "farklı bir yükseklik dene (±20 cm).")
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Kart yüksekliği tarama aracı (otur/ayakta ayrım gücü)")
    ap.add_argument("--height", type=float, required=True,
                    help="Kartların YERDEN yüksekliği (cm) - kayda not düşülür")
    ap.add_argument("--position", default="merkez",
                    help="Kişinin durduğu nokta (bu testte sabit)")
    ap.add_argument("--phases", type=int, default=6)
    ap.add_argument("--phase-sec", type=float, default=12)
    ap.add_argument("--settle-sec", type=float, default=6)
    ap.add_argument("--output", default=None)
    ap.add_argument("--analyse-only", default=None,
                    help="Kayıt yapma, mevcut bir taramayı yeniden değerlendir")
    args = ap.parse_args()

    if args.analyse_only:
        analyse(json.load(open(args.analyse_only + ".json")))
        return

    if args.output is None:
        args.output = f"../data/geometry_probe/h{int(args.height)}"

    cues = ["otur" if i % 2 == 0 else "ayakta" for i in range(args.phases)]
    print(f"GEOMETRİ TARAMASI - kart yüksekliği {args.height:.0f} cm")
    print(f"{args.phases} faz x {args.phase_sec:.0f} sn = "
          f"{args.phases * args.phase_sec:.0f} sn")
    print("Kişi TEK bir noktada dursun (kartların tam arasında, hattın üstünde).")
    print("Komut gelince hemen oturup/kalkıp SONRA sabit kal.\n")

    analyse(capture(args, cues))


if __name__ == "__main__":
    main()
