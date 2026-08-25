"""Tek kesintisiz kayıt içinde otur/ayakta ayrımı test eder (2026-08-24).

NEDEN: Ayrı ayrı alınan kayıtlarla (her biri kart resetiyle başlıyor) oturum-arası
doğruluk şans seviyesinde çıktı (%52.9 mutlak, %45.9 dinamik - bkz.
evaluate_ap_feasibility.py). Hipotez: sorun postürü ayırt edememek DEĞİL, her
reset/yeniden-bağlanmanın radyoya kayıt-özel bir imza (AGC kalibrasyonu vb.)
bırakması.

TEST: Kart hiç resetlenmeden, TEK kayıt içinde 15'er saniyelik fazlarla
otur/ayakta/otur/ayakta/otur/ayakta yapıldı. Fazlar arasında reset yok, yeniden
bağlanma yok. Eğer doğruluk burada yükseliyorsa hipotez doğrulanır.

Doğrulama: LeaveOneGroupOut, gruplar = fazlar. Yani model 5 fazla eğitilip
hiç görmediği 6. fazda test edilir.
"""
import re
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut

DATA_PATH = "../data/continuous_session/continuous_alternating_01.csv"
PHASE_SEC = 15
N_PHASES = 6
# Faz sınırlarında kişi ayağa kalkıyor/oturuyor - bu geçiş hareketi ne "otur"
# ne "ayakta". Sınırların iki yanından bu kadar saniye atılıyor.
MARGIN_SEC = 3.0
WINDOW_SEC = 2.0

BRACKET_RE = re.compile(r"\[([\d\s-]+)\]")


def parse_with_timestamps(csv_path):
    """(timestamps, amplitude_matrix) döndürür - ikisi hizalı.

    activity_features.parse_amplitude_matrix zaman damgası döndürmüyor; burada
    faza göre bölmek için zamana ihtiyaç var, o yüzden ayrı bir ayrıştırıcı.
    """
    times, rows = [], []
    with open(csv_path) as f:
        next(f)  # başlık
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
                ts = float(fields[23])  # real_timestamp
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
    print(f"  {len(rows)} paket ayrıştırıldı, {len(keep)} tanesi baskın "
          f"formatta ({common} alt-taşıyıcı)")
    return np.array([times[i] for i in keep]), np.stack([rows[i] for i in keep])


def absolute_features(w):
    return np.concatenate([w.mean(axis=0), w.std(axis=0), w.min(axis=0), w.max(axis=0)])


def dynamic_features(w):
    d = np.diff(w, axis=0)
    return np.concatenate([d.mean(axis=0), d.std(axis=0), np.abs(d).mean(axis=0)])


def movement_energy(w):
    return float(np.abs(np.diff(w, axis=0)).mean()) if len(w) > 1 else 0.0


def build_windows(times, amp):
    """Fazlara böl, geçiş kenarlarını at, 2sn'lik pencereler üret."""
    t0 = times[0]
    rel = times - t0
    windows, labels, groups = [], [], []
    for phase in range(N_PHASES):
        start = phase * PHASE_SEC + MARGIN_SEC
        end = (phase + 1) * PHASE_SEC - MARGIN_SEC
        idx = np.where((rel >= start) & (rel < end))[0]
        if len(idx) < 10:
            continue
        phase_amp = amp[idx]
        phase_t = rel[idx]
        # 2 saniyelik, örtüşmesiz pencereler
        w_start = phase_t[0]
        while w_start + WINDOW_SEC <= phase_t[-1]:
            sel = np.where((phase_t >= w_start) & (phase_t < w_start + WINDOW_SEC))[0]
            if len(sel) >= 20:
                windows.append(phase_amp[sel])
                labels.append(phase % 2)  # 0=otur (çift faz), 1=ayakta (tek faz)
                groups.append(phase)
            w_start += WINDOW_SEC
    return windows, np.array(labels), np.array(groups)


def check_protocol(times, amp):
    """Kullanıcı protokole uydu mu? Faz sınırlarında hareket zirvesi olmalı."""
    print("\n--- Protokol kontrolü: saniye başına hareket enerjisi ---")
    rel = times - times[0]
    print("  (faz sınırları 15,30,45,60,75 sn - buralarda zirve BEKLENİYOR)")
    line = []
    for sec in range(int(rel[-1])):
        idx = np.where((rel >= sec) & (rel < sec + 1))[0]
        e = movement_energy(amp[idx]) if len(idx) > 1 else 0.0
        line.append(e)
    arr = np.array(line)
    boundaries = [15, 30, 45, 60, 75]
    peak_secs = sorted(range(len(arr)), key=lambda i: -arr[i])[:8]
    print(f"  En hareketli 8 saniye: {sorted(peak_secs)}")
    near = sum(1 for p in peak_secs if any(abs(p - b) <= 2 for b in boundaries))
    print(f"  Bunların {near}/8 tanesi bir faz sınırının ±2sn içinde.")
    if near >= 4:
        print("  ✅ Protokole uyulmuş görünüyor (geçişler sınırlarda).")
    else:
        print("  ⚠️  Hareket zirveleri sınırlarla örtüşmüyor - etiketler kaymış olabilir.")


def evaluate(name, feature_fn, windows, labels, groups):
    X = np.array([feature_fn(w) for w in windows])
    print(f"\n=== {name} ({X.shape[0]} pencere, {X.shape[1]} özellik) ===")
    accs = []
    for train_idx, test_idx in LeaveOneGroupOut().split(X, labels, groups):
        clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
        clf.fit(X[train_idx], labels[train_idx])
        acc = clf.score(X[test_idx], labels[test_idx])
        accs.append(acc)
        phase = groups[test_idx][0]
        pos = "otur" if phase % 2 == 0 else "ayakta"
        print(f"  test faz={phase} ({pos:6s}) n={len(test_idx):3d}  doğruluk={acc:.1%}")
    print(f"  ORTALAMA: {np.mean(accs):.1%}  (std={np.std(accs):.1%})")
    return np.mean(accs)


if __name__ == "__main__":
    print(f"Okunuyor: {DATA_PATH}")
    times, amp = parse_with_timestamps(DATA_PATH)
    print(f"  süre={times[-1] - times[0]:.1f} sn, "
          f"ortalama hız={len(times) / (times[-1] - times[0]):.1f} Hz")

    check_protocol(times, amp)

    windows, labels, groups = build_windows(times, amp)
    print(f"\n{len(windows)} pencere üretildi "
          f"(otur={int((labels == 0).sum())}, ayakta={int((labels == 1).sum())})")
    if len(set(groups)) < 2:
        sys.exit("Yeterli faz yok.")

    acc_abs = evaluate("MUTLAK DESEN", absolute_features, windows, labels, groups)
    acc_dyn = evaluate("POSTURAL SWAY (dinamik)", dynamic_features, windows, labels, groups)

    print("\n" + "=" * 55)
    print("TEK KESİNTİSİZ KAYIT (reset yok) sonuçları:")
    print(f"  Mutlak desen : {acc_abs:.1%}")
    print(f"  Postural sway: {acc_dyn:.1%}")
    print("\nKarşılaştırma - AYRI kayıtlar (her biri resetli):")
    print("  Mutlak desen : 52.9%")
    print("  Postural sway: 45.9%")
    print("(şans seviyesi: 50%)")
