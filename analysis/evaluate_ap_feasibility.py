"""2. ESP32 AP mimarisiyle toplanan yeni veriyle fizibilite testi (2026-08-24).

Bölüm 5'teki iki soruyu cevaplar (docs/PROJE_DURUM_VE_KARARLAR.md):
  1. Yüksek hız (80-100 Hz), eski (mutlak desen - mean/std/min/max) yöntemin
     oturum-arası genellemesini düzeltiyor mu?
  2. Postural sway hipotezi: DİNAMİK özellikler (ardışık paket farkları) ile
     otur/ayakta ayrımı yapılabiliyor mu, ve bu daha mı tutarlı?

Doğrulama yöntemi: LeaveOneGroupOut, her kayıt dosyası kendi grubu. Bu, 5 ayrı
oturma + 5 ayrı ayakta kaydını (her biri bağımsız bir seri bağlantı/reset ile
alındı - küçük çaplı "oturumlar arası" testi) rastgele karıştırmadan, gerçekçi
şekilde değerlendirir.
"""
import glob

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut

from activity_features import parse_amplitude_matrix_from_file, sliding_windows

DATA_DIR = "../data"
POSTURE_CLASSES = {"sit": 0, "stand": 1}
WINDOW_SEC = 2
RECORDING_SEC = 18


def absolute_features(amp_matrix):
    """Eski yöntem: mutlak genlik deseni (mean/std/min/max)."""
    return np.concatenate([
        amp_matrix.mean(axis=0),
        amp_matrix.std(axis=0),
        amp_matrix.min(axis=0),
        amp_matrix.max(axis=0),
    ])


def dynamic_features(amp_matrix):
    """Yeni hipotez: postural sway - ardışık paketler arası DEĞİŞİM deseni.

    Mutlak seviyeye değil, sinyalin ne kadar/nasıl salındığına bakıyor ->
    teoride ortam kaymasından (sabit bir kayma, fark alınca sadeleşir) daha az
    etkilenmeli.
    """
    diffs = np.diff(amp_matrix, axis=0)
    return np.concatenate([
        diffs.mean(axis=0),
        diffs.std(axis=0),
        np.abs(diffs).mean(axis=0),
    ])


def build_dataset(feature_fn):
    X, y, groups = [], [], []
    for label_name, label_id in POSTURE_CLASSES.items():
        files = sorted(glob.glob(f"{DATA_DIR}/own_activity_{label_name}_*.csv"))
        for group_id, p in enumerate(files):
            amp = parse_amplitude_matrix_from_file(p)
            for window in sliding_windows(amp, WINDOW_SEC, total_sec=RECORDING_SEC):
                X.append(feature_fn(window))
                y.append(label_id)
                groups.append(f"{label_name}_{group_id}")
    return np.array(X), np.array(y), np.array(groups)


def evaluate(name, feature_fn):
    X, y, groups = build_dataset(feature_fn)
    logo = LeaveOneGroupOut()
    accs = []
    print(f"\n=== {name} ({X.shape[0]} pencere, {X.shape[1]} özellik) ===")
    for train_idx, test_idx in logo.split(X, y, groups):
        clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
        clf.fit(X[train_idx], y[train_idx])
        acc = clf.score(X[test_idx], y[test_idx])
        accs.append(acc)
        held_out = groups[test_idx][0]
        print(f"  test grubu={held_out:12s} n={len(test_idx):3d}  doğruluk={acc:.1%}")
    print(f"  ORTALAMA (LeaveOneGroupOut): {np.mean(accs):.1%}  (std={np.std(accs):.1%})")
    return np.mean(accs)


if __name__ == "__main__":
    acc_abs = evaluate("MUTLAK DESEN (eski yöntem)", absolute_features)
    acc_dyn = evaluate("POSTURAL SWAY (dinamik, yeni hipotez)", dynamic_features)

    print("\n" + "=" * 50)
    print(f"Mutlak desen ortalama : {acc_abs:.1%}")
    print(f"Postural sway ortalama: {acc_dyn:.1%}")
    print("(Rastgele tahmin/şans seviyesi: 50%)")
