"""Yürüme sınıflandırıcısını etiketli oturumlarımızdan eğitir (2026-08-25).

NEDEN MODEL, NEDEN ELLE EŞİK DEĞİL:
Elle eşik (live_server_udp'nin ilk hali) kalibrasyona bağımlıydı ve
kalibrasyon anında ortam sakin değilse taban şişip sistem çalışmıyordu
(2026-08-25'te canlıda yaşandı: taban 1.49 ölçüldü, gerçek değer 0.56-0.98).
Model, kararı veriden öğrenir ve tek bir ölçüme bağlı kalmaz.

NE ÖĞRENİYOR: yürüyor mu / yürümüyor mu. SADECE bu.
Otur/ayakta ayrımı bu donanımda ALTI ayrı yöntemle denendi ve hepsi
tekrarda çöktü - bkz. docs/PROJE_DURUM_VE_KARARLAR.md. Model o soruya
girmiyor.

DOĞRULAMA - Leave-One-SESSION-Out:
Model bir oturumu HİÇ görmeden o oturumda test ediliyor. Bunun altındaki
hiçbir doğrulama (pencere bazlı, faz bazlı) güvenilir değil: aynı oturumun
başka bir penceresi eğitimde kalırsa model ortamı ezberleyip şişik skor
verir. Bölüm 3.7'nin dersi tam olarak buydu.

Kullanım:
    python train_walking_model.py
    -> models/walking_model.joblib
"""
import json
import pathlib
import re
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut

from activity_features import walking_features, WALKING_FEATURE_NAMES

BRACKET_RE = re.compile(r"\[([\d\s-]+)\]")
WIN_SEC = 3.0          # canlı sistemle AYNI olmalı
STEP_SEC = 0.5
PHASE_MARGIN = 3.0     # faz başındaki geçiş hareketini dışarıda bırak
MIN_PKT = 80
SMOOTH_K = 5           # canlı sistemin yumuşatma penceresi (5 x 0.5 sn adım)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SESSIONS = [
    ROOT / "data/udp_session/20260824_hareket_teshis",
    ROOT / "data/udp_session/20260824_hareket_turu",
    ROOT / "data/udp_session/20260824_hareket_turu_02",
    ROOT / "data/udp_session/20260824_durus_konum_degisken",
    ROOT / "data/posture_v2/coupling_test",
    ROOT / "data/posture_v2/s1_P1",
    ROOT / "data/posture_v2/slow1",
    ROOT / "data/posture_v2/slow2",
    # --- 2026-08-26 eklendi: posture_v3 ---
    # Besi dogrudan "bu yurume DEGIL" ornegi (saf otur/kalk), biri yurume
    # iceriyor. Amac: otur/kalk gecislerinin yurume sanilmasini azaltmak.
    ROOT / "data/posture_v3/tur1_P1_orta",
    ROOT / "data/posture_v3/tur2_P2_kart_yakin",
    ROOT / "data/posture_v3/tur3_P3_diger_kart_yakin",
    ROOT / "data/posture_v3/tur3b_P3_diger_kart_yakin",
    ROOT / "data/posture_v3/tur4_P4_hat_disi_yakin",
    ROOT / "data/posture_v3/tur5_karisik_demo",
]


def parse(path):
    times, rows = [], []
    with open(path) as f:
        next(f)
        for line in f:
            if not line.startswith("CSI_DATA"):
                continue
            m = BRACKET_RE.search(line)
            if not m:
                continue
            try:
                recv = float(line[m.end():].strip().lstrip(",").split(",")[0])
            except (ValueError, IndexError):
                continue
            nums = np.array([int(x) for x in re.findall(r"-?\d+", m.group(1))])
            if len(nums) < 4:
                continue
            p = nums[: len(nums) // 2 * 2].reshape(-1, 2).astype(float)
            rows.append(np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2))
            times.append(recv)
    if not rows:
        return np.array([]), np.empty((0, 0))
    L = [len(r) for r in rows]
    c = max(set(L), key=L.count)
    k = [i for i, r in enumerate(rows) if len(r) == c]
    return np.array([times[i] for i in k]), np.stack([rows[i] for i in k])


def resolve(base, stored):
    """JSON'daki yol analysis/ göreliydi; dosya adından yeniden kur."""
    p = pathlib.Path(stored)
    cand = base.parent / p.name
    return cand if cand.exists() else p


def main():
    X, y, groups, meta_rows = [], [], [], []

    for si, base in enumerate(SESSIONS):
        meta = json.load(open(str(base) + ".json"))
        name = base.name
        n_before = len(y)
        for role, stored in sorted(meta["files"].items()):
            path = resolve(base, stored)
            if not path.exists():
                print(f"  ! bulunamadı: {path}")
                continue
            t, a = parse(path)
            if len(t) == 0:
                continue
            for ph in meta["phases"]:
                label = 1 if ph["posture"].strip() == "yürü" else 0
                w = ph["recv_ts_start"] + PHASE_MARGIN
                end = ph["recv_ts_end"] - 0.2
                while w + WIN_SEC <= end:
                    sel = np.where((t >= w) & (t < w + WIN_SEC))[0]
                    if len(sel) >= MIN_PKT:
                        fs = len(sel) / WIN_SEC
                        X.append(walking_features(a[sel], fs))
                        y.append(label)
                        groups.append(si)
                        meta_rows.append((name, role, w, ph["phase"]))
                    w += STEP_SEC
        print(f"  {name:<34} +{len(y)-n_before:>5} pencere")

    X = np.array(X)
    y = np.array(y)
    groups = np.array(groups)
    print(f"\nToplam {len(y)} pencere | yürüyor {int(y.sum())} | "
          f"yürümüyor {int((1-y).sum())} | {X.shape[1]} özellik")
    print(f"Şans seviyesi (çoğunluk sınıfı): {max(y.mean(), 1-y.mean()):.1%}\n")

    # Canlı sistem tek pencereye bakmıyor, arka arkaya gelen pencerelerin
    # olasılığını yumuşatıyor. Gerçek performans o, bu yüzden ikisi de ölçülüyor.
    def smooth_per_card(idx, proba, k=SMOOTH_K):
        """Aynı karttan gelen ardışık pencerelerin olasılığını yumuşatır."""
        out = np.array(proba, dtype=float)
        by_card = {}
        for j, i in enumerate(idx):
            by_card.setdefault(meta_rows[i][1], []).append((meta_rows[i][2], j))
        for rows in by_card.values():
            rows.sort()
            js = [j for _, j in rows]
            vals = np.array([proba[j] for j in js])
            csum = np.concatenate([[0.0], np.cumsum(vals)])
            for pos, j in enumerate(js):
                lo = max(0, pos - k + 1)
                out[j] = (csum[pos + 1] - csum[lo]) / (pos + 1 - lo)
        return out

    print("--- Leave-One-SESSION-Out (model o oturumu hiç görmedi) ---")
    print(f"{'oturum':<34} {'tek pencere':>12} {'yumuşatılmış':>13}   detay")
    accs, sm_accs, weights = [], [], []
    phase_accs, phase_w = [], []
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        sess = SESSIONS[groups[te][0]].name
        if len(set(y[tr])) < 2:
            continue
        clf = RandomForestClassifier(n_estimators=400, min_samples_leaf=4,
                                     random_state=42, n_jobs=-1,
                                     class_weight="balanced")
        clf.fit(X[tr], y[tr])
        proba = clf.predict_proba(X[te])[:, 1]
        pred = (proba >= 0.5).astype(int)
        sm = (smooth_per_card(te, proba) >= 0.5).astype(int)

        acc = float((pred == y[te]).mean())
        sacc = float((sm == y[te]).mean())
        pos = int(y[te].sum())
        if pos and pos < len(y[te]):
            rec = float((sm[y[te] == 1] == 1).mean())
            spec = float((sm[y[te] == 0] == 0).mean())
            detail = f"yürüme yakalama {rec:.0%} | durma yakalama {spec:.0%}"
        else:
            detail = "tek sınıf (hepsi yürümüyor)" if not pos else "tek sınıf"
        # FAZ BAZINDA: demo'da önemli olan bu - "yürüdüğüm 15 saniye boyunca
        # ekran çoğunlukla doğru şeyi yazdı mı". Tek pencere yanılsa da faz
        # doğruysa kullanıcı doğru sonucu görür.
        ph_ok = ph_tot = 0
        seen = {}
        for pos, i in enumerate(te):
            key = (meta_rows[i][1], meta_rows[i][3])
            seen.setdefault(key, []).append((sm[pos], y[te][pos]))
        for vals in seen.values():
            maj = 1 if sum(v for v, _ in vals) * 2 > len(vals) else 0
            ph_ok += int(maj == vals[0][1]); ph_tot += 1
        phase_accs.append(ph_ok / ph_tot); phase_w.append(ph_tot)
        print(f"{sess:<34} {acc:>12.1%} {sacc:>13.1%} {ph_ok}/{ph_tot} faz   {detail}")
        accs.append(acc)
        sm_accs.append(sacc)
        weights.append(len(te))

    print(f"\n  FAZ BAZINDA DOĞRULUK: "
          f"{np.average(phase_accs, weights=phase_w):.1%}  "
          f"<-- ekranda görülecek olan bu")
    print(f"  AĞIRLIKLI ORTALAMA: tek pencere "
          f"{np.average(accs, weights=weights):.1%}  ->  yumuşatılmış "
          f"{np.average(sm_accs, weights=weights):.1%}")

    # nihai model: tüm veri
    clf = RandomForestClassifier(n_estimators=400, min_samples_leaf=4,
                                 random_state=42, n_jobs=-1,
                                 class_weight="balanced")
    clf.fit(X, y)
    print("\n--- Özellik önemleri ---")
    for n, imp in sorted(zip(WALKING_FEATURE_NAMES, clf.feature_importances_),
                         key=lambda kv: -kv[1])[:6]:
        print(f"  {n:<26} {imp:.3f}")

    out = pathlib.Path(__file__).parent / "models/walking_model.joblib"
    out.parent.mkdir(exist_ok=True)
    import joblib
    joblib.dump({"model": clf, "win_sec": WIN_SEC, "step_sec": STEP_SEC,
                 "smooth_k": SMOOTH_K,
                 "features": WALKING_FEATURE_NAMES}, out)
    print(f"\nKaydedildi -> {out}")


if __name__ == "__main__":
    sys.exit(main())
