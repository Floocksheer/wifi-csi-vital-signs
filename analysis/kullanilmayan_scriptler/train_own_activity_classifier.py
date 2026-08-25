"""Kendi topladığımız aktivite verisiyle (sit/stand/fall) küçük bir sınıflandırıcı eğitir.

UT-HAR'daki yöntemin (subcarrier başına mean/std/min/max özellik + Random Forest)
kendi ESP32 donanımımıza uygulanmış hali. Çok az örnekle (14 kayıt, 3 sınıf)
çalıştığı için sonuç istatistiksel olarak güçlü değil — bir kavram kanıtı.
"""
import glob

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneOut

from activity_features import parse_amplitude_matrix_from_file as parse_amplitude_matrix
from activity_features import extract_features

DATA_DIR = "../data"
CLASSES = {"sit": 0, "stand": 1, "fall": 2}
CLASS_NAMES = ["sit", "stand", "fall"]


def main():
    X, y, files = [], [], []
    for label_name, label_id in CLASSES.items():
        paths = sorted(glob.glob(f"{DATA_DIR}/own_activity_{label_name}_*.csv"))
        for p in paths:
            amp_matrix = parse_amplitude_matrix(p)
            X.append(extract_features(amp_matrix))
            y.append(label_id)
            files.append(p)

    X = np.array(X)
    y = np.array(y)
    print(f"Toplam örnek: {len(y)} — sınıf dağılımı: "
          f"{[(name, int((y == cid).sum())) for name, cid in CLASSES.items()]}")

    # Çok az örnek var (14), ayrı bir test seti ayırmak yerine
    # Leave-One-Out cross-validation kullanıyoruz: her seferinde 1 örneği
    # dışarıda bırakıp kalanlarla eğitip o 1'i tahmin ediyoruz.
    loo = LeaveOneOut()
    correct = 0
    print("\nLeave-One-Out sonuçları:")
    for train_idx, test_idx in loo.split(X):
        clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        clf.fit(X[train_idx], y[train_idx])
        pred = clf.predict(X[test_idx])[0]
        true = y[test_idx][0]
        is_correct = pred == true
        correct += is_correct
        mark = "OK" if is_correct else "YANLIŞ"
        print(f"  {files[test_idx[0]].split('/')[-1]:<32} gerçek={CLASS_NAMES[true]:<6} tahmin={CLASS_NAMES[pred]:<6} [{mark}]")

    acc = correct / len(y)
    print(f"\nLeave-One-Out doğruluk: {acc:.2%} ({correct}/{len(y)})")


if __name__ == "__main__":
    main()
