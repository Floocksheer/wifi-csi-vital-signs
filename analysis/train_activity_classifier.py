"""UT-HAR dataset'i ile aktivite sınıflandırma modeli (Faz 3.5, ilk adım).

X şekli: (örnek, 250 zaman-adımı, 90 özellik=30 subcarrier x 3 anten)
y: 0-6 arası, 7 sınıf (bed, fall, pickup, run, sitdown, standup, walk)

Yaklaşım: ham (250, 90) zaman serisini, her subcarrier için özet istatistiklere
(mean/std/min/max, zaman ekseninde) indirgeyip klasik bir Random Forest ile
sınıflandırıyoruz. Bu basit ama makul bir ilk kavram kanıtı (proof of concept) -
gelecekte 1D-CNN/LSTM gibi zaman serisini doğrudan kullanan modellerle
karşılaştırılabilir.
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

ACTIVITY_NAMES = ["bed", "fall", "pickup", "run", "sitdown", "standup", "walk"]


def extract_features(X):
    """(örnek, zaman, subcarrier) -> (örnek, subcarrier*4) özet istatistikler."""
    mean = X.mean(axis=1)
    std = X.std(axis=1)
    mn = X.min(axis=1)
    mx = X.max(axis=1)
    return np.concatenate([mean, std, mn, mx], axis=1)


def main():
    data_dir = "../data/ut_har_activity"
    X_train = np.load(f"{data_dir}/data/X_train.csv")
    y_train = np.load(f"{data_dir}/label/y_train.csv")
    X_val = np.load(f"{data_dir}/data/X_val.csv")
    y_val = np.load(f"{data_dir}/label/y_val.csv")
    X_test = np.load(f"{data_dir}/data/X_test.csv")
    y_test = np.load(f"{data_dir}/label/y_test.csv")

    print("Özellik çıkarımı yapılıyor...")
    Xf_train = extract_features(X_train)
    Xf_val = extract_features(X_val)
    Xf_test = extract_features(X_test)
    print(f"Özellik boyutu: {Xf_train.shape[1]} (90 subcarrier x 4 istatistik)")

    clf = RandomForestClassifier(n_estimators=300, max_depth=None, random_state=42, n_jobs=-1)
    clf.fit(Xf_train, y_train)

    for name, Xf, y in [("VAL", Xf_val, y_val), ("TEST", Xf_test, y_test)]:
        preds = clf.predict(Xf)
        acc = accuracy_score(y, preds)
        print(f"\n=== {name} — Doğruluk: {acc:.3f} ===")
        print(classification_report(y, preds, target_names=ACTIVITY_NAMES, zero_division=0))


if __name__ == "__main__":
    main()
