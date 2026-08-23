"""Canlı sistemin kullanacağı DURUŞ (otur/ayakta) modelini eğitip diske kaydeder.

İki aşamalı mimari (2026-08-19):
  1. Hareket kapısı: hareket enerjisi eşiği aşarsa "HAREKET" -> model çalıştırılmaz
  2. Kişi hareketsizse: bu model otur/ayakta ayrımını yapar

Bu yüzden model SADECE otur/ayakta verisiyle eğitiliyor; "ani hareket" sınıfı
modele değil, eşiğe bırakıldı (eşik bu işi zaten güvenilir yapıyor).

Eğitim, 8 saniyelik kayıtları 2 saniyelik örtüşmeli pencerelere bölerek yapılıyor
- hem canlı sistemle aynı pencere boyutu (tutarlılık) hem de 7 kat daha fazla örnek.
"""
import glob
import os

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from activity_features import (
    parse_amplitude_matrix_from_file,
    extract_features,
    sliding_windows,
)

DATA_DIR = "../data"
POSTURE_CLASSES = {"sit": 0, "stand": 1}
POSTURE_NAMES = ["sit", "stand"]
WINDOW_SEC = 2
MODEL_PATH = "models/activity_classifier.joblib"


def main():
    X, y = [], []
    for label_name, label_id in POSTURE_CLASSES.items():
        for p in sorted(glob.glob(f"{DATA_DIR}/own_activity_{label_name}_*.csv")):
            amp = parse_amplitude_matrix_from_file(p)
            for window in sliding_windows(amp, WINDOW_SEC):
                X.append(extract_features(window))
                y.append(label_id)

    X, y = np.array(X), np.array(y)
    clf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    clf.fit(X, y)

    os.makedirs("models", exist_ok=True)
    joblib.dump(
        {"model": clf, "class_names": POSTURE_NAMES, "window_sec": WINDOW_SEC},
        MODEL_PATH,
    )
    print(f"Duruş modeli kaydedildi -> {MODEL_PATH}")
    print(f"  {len(y)} pencere ile eğitildi (otur={int((y==0).sum())}, ayakta={int((y==1).sum())})")


if __name__ == "__main__":
    main()
