"""guided_capture.py çıktısını değerlendirir: otur/ayakta ayrımı yapılabiliyor mu?

Faz sınırları kullanıcının kronometresinden değil, komut anındaki ESP zaman
damgasından (yan dosya .json) geliyor -> senkron hatası yok.

İki soru:
  1. Protokole uyuldu mu? (komuttan hemen sonra hareket zirvesi olmalı)
  2. Fazlar-arası (LeaveOneGroupOut) otur/ayakta ayrımı şans seviyesinin
     üstünde mi - mutlak desen mi yoksa dinamik (postural sway) mı çalışıyor?

Kullanım:
    python evaluate_guided_session.py ../data/continuous_session/guided_01
"""
import json
import re
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut, cross_val_score

# Komut duyulduktan sonra kişi pozisyona geçerken hareket ediyor - bu süre atılır
TRANSITION_MARGIN_SEC = 3.0
WINDOW_SEC = 2.0

BRACKET_RE = re.compile(r"\[([\d\s-]+)\]")


def parse_with_timestamps(csv_path):
    times, rows = [], []
    with open(csv_path) as f:
        next(f)
        for line in f:
            if not line.startswith("CSI_DATA"):
                continue
            match = BRACKET_RE.search(line)
            if not match:
                continue
            fields = line.split(",")
            if len(fields) < 24:
                continue
            try:
                ts = float(fields[23])
            except ValueError:
                continue
            nums = np.array([int(x) for x in re.findall(r"-?\d+", match.group(1))])
            if len(nums) < 4:
                continue
            pairs = nums[: len(nums) // 2 * 2].reshape(-1, 2).astype(float)
            rows.append(np.sqrt(pairs[:, 0] ** 2 + pairs[:, 1] ** 2))
            times.append(ts)

    lengths = [len(r) for r in rows]
    common = max(set(lengths), key=lengths.count)
    keep = [i for i, r in enumerate(rows) if len(r) == common]
    print(f"  {len(rows)} paket, {len(keep)} tanesi baskın formatta "
          f"({common} alt-taşıyıcı)")
    return np.array([times[i] for i in keep]), np.stack([rows[i] for i in keep])


def movement_energy(w):
    return float(np.abs(np.diff(w, axis=0)).mean()) if len(w) > 1 else 0.0


def absolute_features(w):
    return np.concatenate([w.mean(axis=0), w.std(axis=0), w.min(axis=0), w.max(axis=0)])


def dynamic_features(w):
    d = np.diff(w, axis=0)
    return np.concatenate([d.mean(axis=0), d.std(axis=0), np.abs(d).mean(axis=0)])


def check_protocol(times, amp, phases):
    """Her komuttan sonraki 2 sn'de hareket, fazın sakin kısmından yüksek olmalı."""
    print("\n--- Protokol kontrolü ---")
    print("  faz | komut  | gecis aninda | sakin kisim | gecis daha hareketli mi?")
    ok = 0
    for p in phases:
        t0 = p["esp_ts_start"]
        trans = np.where((times >= t0) & (times < t0 + 2.0))[0]
        calm = np.where((times >= t0 + TRANSITION_MARGIN_SEC)
                        & (times < p["esp_ts_end"]))[0]
        if len(trans) < 5 or len(calm) < 5:
            continue
        e_trans, e_calm = movement_energy(amp[trans]), movement_energy(amp[calm])
        good = e_trans > e_calm * 1.3
        ok += good
        print(f"  {p['phase']:3d} | {p['posture']:6s} | {e_trans:11.2f}  | "
              f"{e_calm:10.2f}  | {'EVET' if good else 'hayir'}")
    print(f"  -> {ok}/{len(phases)} fazda geçiş hareketi net görülüyor.")
    if ok >= len(phases) * 0.6:
        print("  ✅ Protokole uyulmuş, etiketler güvenilir.")
    else:
        print("  ⚠️  Geçişler zayıf - etiketler şüpheli, sonuçlara dikkat.")
    return ok


def build_windows(times, amp, phases):
    windows, labels, groups = [], [], []
    for p in phases:
        start = p["esp_ts_start"] + TRANSITION_MARGIN_SEC
        end = p["esp_ts_end"] - 0.5
        w_start = start
        while w_start + WINDOW_SEC <= end:
            sel = np.where((times >= w_start) & (times < w_start + WINDOW_SEC))[0]
            if len(sel) >= 30:
                windows.append(amp[sel])
                labels.append(p["label"])
                groups.append(p["phase"])
            w_start += WINDOW_SEC
    return windows, np.array(labels), np.array(groups)


def evaluate(name, feature_fn, windows, labels, groups):
    X = np.array([feature_fn(w) for w in windows])
    print(f"\n=== {name} ({X.shape[0]} pencere, {X.shape[1]} özellik) ===")

    accs = []
    for train_idx, test_idx in LeaveOneGroupOut().split(X, labels, groups):
        clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
        clf.fit(X[train_idx], labels[train_idx])
        accs.append(clf.score(X[test_idx], labels[test_idx]))
    logo = np.mean(accs)

    # Karşılaştırma: pencereleri rastgele karıştıran (yanıltıcı) doğrulama.
    # Aynı fazın pencereleri hem eğitimde hem testte olur -> şişik sonuç verir.
    clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    naive = cross_val_score(clf, X, labels, cv=5).mean()

    print(f"  Fazlar-arası (LeaveOneGroupOut) : {logo:.1%}  (std={np.std(accs):.1%})  <- GERÇEK")
    print(f"  Rastgele karıştırılmış 5-kat CV : {naive:.1%}  <- yanıltıcı, kıyas için")
    return logo


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "../data/continuous_session/guided_01"
    print(f"Okunuyor: {base}")
    times, amp = parse_with_timestamps(base + ".csv")
    with open(base + ".json") as f:
        meta = json.load(f)
    phases = meta["phases"]
    print(f"  süre={times[-1] - times[0]:.1f} sn, "
          f"hız={len(times) / (times[-1] - times[0]):.1f} Hz, {len(phases)} faz")

    check_protocol(times, amp, phases)

    windows, labels, groups = build_windows(times, amp, phases)
    print(f"\n{len(windows)} pencere (otur={int((labels == 0).sum())}, "
          f"ayakta={int((labels == 1).sum())}), {len(set(groups))} faz grubu")

    acc_abs = evaluate("MUTLAK DESEN", absolute_features, windows, labels, groups)
    acc_dyn = evaluate("POSTURAL SWAY (dinamik)", dynamic_features, windows, labels, groups)

    print("\n" + "=" * 58)
    print("SONUÇ (fazlar-arası, senkron hatası olmadan):")
    print(f"  Mutlak desen : {acc_abs:.1%}")
    print(f"  Postural sway: {acc_dyn:.1%}")
    print("  (şans seviyesi: 50%)")
