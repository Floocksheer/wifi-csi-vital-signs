"""Geçiş anı (otur<->kalk) tespit modelini eğitir (2026-08-26).

NEDEN BU MODEL VAR:
Duruşun KENDİSİ bu donanımda ölçülemiyor - yedi ayrı yöntem denendi, hepsi
tekrarda çöktü (bkz. PROJE_DURUM_VE_KARARLAR.md Bölüm 3.9). Ama duruş sırayla
değişiyor: oturuyorsan sonraki geçiş seni kaldırır, ayaktaysan oturtur. Yani
YÖN bilgisine ihtiyaç yok, sadece "şu anda bir geçiş oldu" demeyi güvenilir
yapmak yeterli. Yön, yürüme çıpasından geliyor (yürüyüş her zaman ayakta biter).

NEDEN ESKİ EŞİK YETMİYOR:
Canlı sistemin yüzdelik eşiği ölçüldü: 49 geçişin 4'ünü yakalıyor (%8), durum
zamanın %44.6'sında doğru - yazı turadan kötü. Oysa sinyal orada: geçiş/sakin
enerji oranı 8 oturumda 1.58-2.79x, AUC 0.83-1.00. Yani sorun sinyalde değil
eşikte. Model bu boşluğu kapatmak için.

ÖLÇEKTEN BAĞIMSIZLIK: mutlak enerji oturumdan oturuma kayıyor (bu projedeki
bütün büyük başarısızlıkların kaynağı). Bu yüzden model mutlak enerjiyi DEĞİL,
enerjinin kendi yuvarlanan tabanına ORANINI görüyor - canlı sistemde de aynen
böyle hesaplanabilen bir büyüklük.

Kullanım:
    python train_transition_model.py     -> models/transition_model.joblib
"""
import json
import pathlib
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut

from activity_features import (parse_amplitude_matrix, movement_energy_bandpass,
                               walking_features, WALKING_FEATURE_NAMES)

ROOT = pathlib.Path(__file__).resolve().parent.parent
WIN, STEP, MINPKT = 2.0, 0.5, 40
BASE_N, BASE_PCTL = 120, 40        # 60 sn'lik yuvarlanan taban
# Pencere [t-WIN, t] oldugu icin, komut aninin pencerenin ICINDE kalmasi
# gerekiyor. Tepki suresi ~0-2 sn: pozitif bant komuttan 1.0-4.0 sn sonrasi.
# ARADAKI 1.5 sn'lik bant BELIRSIZ sayilip egitime hic alinmiyor - yoksa
# gecis kuyrugu negatif diye ogretiliyor.
POS_LO, POS_HI = 1.0, 4.0
GUARD_LO, GUARD_HI = -1.5, 5.5
OTUR = ("otur", "yavaşça otur")
AYAK = ("ayakta", "yavaşça kalk")

SESSIONS = [
    "data/posture_v3/tur1_P1_orta",
    "data/posture_v3/tur2_P2_kart_yakin",
    "data/posture_v3/tur3_P3_diger_kart_yakin",
    "data/posture_v3/tur3b_P3_diger_kart_yakin",
    "data/posture_v3/tur4_P4_hat_disi_yakin",
    "data/posture_v3/tur5_karisik_demo",
    "data/posture_v2/s1_P1",
    "data/posture_v2/slow1",
    "data/posture_v2/slow2",
]

FEATURE_NAMES = (["oran_ort", "oran_max", "oran_min", "oran_yukselis",
                  "oran_onceki"] + [f"spek_{n}" for n in WALKING_FEATURE_NAMES])


def posture_of(cue):
    c = cue.strip()
    if c in OTUR: return "otur"
    if c in AYAK: return "ayakta"
    return "yürü" if c.startswith("yürü") else c


def transitions(phases):
    """Sadece GERÇEK duruş değişimleri. 'yürü'den sonraki 'ayakta' bir duruş
    geçişi DEĞİL (durma), 'ayakta'dan 'yürü'ye geçiş de değil."""
    out, prev = [], posture_of(phases[0]["posture"])
    for p in phases[1:]:
        cur = posture_of(p["posture"])
        if {prev, cur} == {"otur", "ayakta"}:
            out.append(p["recv_ts_start"])
        prev = cur
    return out


def card_series(fp, t0, t1):
    ts, rows = [], []
    with open(fp) as f:
        next(f)
        for line in f:
            if line.startswith("CSI_DATA"):
                try: t = float(line.rstrip().rsplit(",", 1)[-1])
                except ValueError: continue
                ts.append(t); rows.append(line)
    ts = np.array(ts)
    grid, ener, spec = [], [], []
    t = t0 + WIN
    while t <= t1:
        sel = (ts >= t - WIN) & (ts < t)
        if sel.sum() >= MINPKT:
            amp = parse_amplitude_matrix("".join(rows[i] for i in np.flatnonzero(sel)))
            if amp.shape[0] >= MINPKT:
                fs = amp.shape[0] / WIN
                grid.append(t)
                ener.append(float(movement_energy_bandpass(amp, fs)))
                spec.append(walking_features(amp, fs))
        t += STEP
    return np.array(grid), np.array(ener), np.array(spec)


def rolling_ratio(e):
    """Enerjinin kendi geçmişine oranı. Canlı sistemde birebir aynı hesaplanır."""
    out = np.ones(len(e))
    for i in range(len(e)):
        h = e[max(0, i - BASE_N):i + 1]
        if len(h) >= 8:
            b = np.percentile(h, BASE_PCTL)
            out[i] = e[i] / (b + 1e-9)
    return out


def label_at(t, tr):
    """1 = gecis, 0 = gecis degil, None = belirsiz (egitime alinmaz)."""
    for c in tr:
        if POS_LO <= t - c <= POS_HI:
            return 1
    for c in tr:
        if GUARD_LO <= t - c <= GUARD_HI:
            return None
    return 0


def build(base):
    meta = json.loads((ROOT / (base + ".json")).read_text())
    ph = meta["phases"]
    t0, t1 = ph[0]["recv_ts_start"], ph[-1]["recv_ts_end"]
    per = {}
    for role, path in meta["files"].items():
        fp = ROOT / "data" / pathlib.Path(path).parent.name / pathlib.Path(path).name
        if fp.exists():
            g, e, s = card_series(fp, t0, t1)
            if len(g) > 30:
                per[role] = (g, rolling_ratio(e), s)
    if len(per) < 1:
        return None
    ref = min(per.values(), key=lambda v: len(v[0]))[0]
    ratios = np.stack([np.interp(ref, g, r) for g, r, _ in per.values()])
    specs = np.mean([np.stack([np.interp(ref, g, s[:, k]) for k in range(s.shape[1])], 1)
                     for g, _, s in per.values()], axis=0)
    tr = transitions(ph)
    X, y, T = [], [], []
    for i, t in enumerate(ref):
        col = ratios[:, i]
        rise = col.mean() - ratios[:, max(0, i - 1)].mean()
        prev = ratios[:, max(0, i - 2)].mean()
        lab = label_at(t, tr)
        if lab is None:
            continue                    # belirsiz bölge - eğitime alma
        X.append(np.concatenate([[col.mean(), col.max(), col.min(), rise, prev], specs[i]]))
        y.append(lab)
        T.append(t)
    return np.array(X), np.array(y), np.array(T), tr


ENTER, EXIT = 0.60, 0.40      # histerezis
REFRAC = 4.0                  # ayni gecis iki kez sayilmasin
SMOOTH = 3                    # olasilik yumusatma (3 x 0.5 sn)
HIT_LO, HIT_HI = -1.0, 6.0    # komut etrafinda "yakalandi" sayilan aralik


def detect(T, prob):
    """Olasiliktan olay uret: yumusat, histerezis, suskunluk."""
    pr = np.convolve(prob, np.ones(SMOOTH) / SMOOTH, mode="same")
    ev, on, last = [], False, -1e9
    for t, p in zip(T, pr):
        if not on and p > ENTER:
            on = True
            if t - last >= REFRAC:
                ev.append(t); last = t
        elif on and p < EXIT:
            on = False
    return ev


def state_accuracy(T, events, phases, tr):
    """Durum makinesi simulasyonu: dogru durumdan basla, her olayda cevir.
    Yuruyus sonrasi capa YOK - en kotu durum olcumu (sadece gecislerle)."""
    def truth(t):
        for ph in phases:
            if ph["recv_ts_start"] <= t < ph["recv_ts_end"]:
                return posture_of(ph["posture"])
        return None
    st = truth(T[0])
    if st not in ("otur", "ayakta"):
        st = "ayakta"
    ei, ok, tot = 0, 0.0, 0.0
    for t in T:
        while ei < len(events) and events[ei] <= t:
            st = "ayakta" if st == "otur" else "otur"; ei += 1
        g = truth(t)
        if g not in ("otur", "ayakta"):
            continue
        if any(-1.0 <= t - c <= 6.0 for c in tr):
            continue                      # gecis bolgesi - sayma
        tot += STEP
        if g == st:
            ok += STEP
    return (ok / tot * 100) if tot else float("nan")


def main():
    data, metas = [], []
    for gi, s in enumerate(SESSIONS):
        r = build(s)
        if r is None:
            print(f"  ATLANDI: {s}"); continue
        X, y, T, tr = r
        data.append((X, y, T, tr, gi))
        metas.append(json.loads((ROOT / (s + ".json")).read_text()))
        print(f"  {s.split('/')[-1]:32s} {len(y):4d} pencere | "
              f"gecis {int(y.sum()):3d} | degil {int((y==0).sum()):4d} | "
              f"gercek gecis {len(tr)}")

    X = np.vstack([d[0] for d in data])
    y = np.concatenate([d[1] for d in data])
    g = np.concatenate([np.full(len(d[1]), d[4]) for d in data])
    print(f"\nToplam {len(y)} pencere | gecis {int(y.sum())} | "
          f"degil {int((y == 0).sum())} | {X.shape[1]} ozellik")
    print(f"Sans seviyesi (cogunluk sinifi): {max(y.mean(), 1-y.mean())*100:.1f}%")

    print(f"\n{'oturum':30s} {'pencere':>8s} {'yakalanan':>10s} {'yanlis/dk':>10s} "
          f"{'DURUM DOGRU':>12s}")
    print("-" * 74)
    accs, hits_t, tru_t, fa_t, mins_t, sacc = [], 0, 0, 0, 0.0, []
    for X_te, y_te, T_te, tr, gi in data:
        m = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                   min_samples_leaf=2, random_state=0, n_jobs=-1)
        sel = g != gi
        m.fit(X[sel], y[sel])
        pw = m.predict(X_te)
        acc = (pw == y_te).mean(); accs.append(acc)
        prob = m.predict_proba(X_te)[:, 1]
        ev = detect(T_te, prob)
        used, hits = set(), 0
        for c in tr:
            cand = [k for k, e in enumerate(ev)
                    if k not in used and c + HIT_LO <= e <= c + HIT_HI]
            if cand: used.add(cand[0]); hits += 1
        fa = len(ev) - len(used)
        mins = (T_te[-1] - T_te[0]) / 60.0
        sa = state_accuracy(T_te, ev, metas[len(sacc)]["phases"], tr)
        hits_t += hits; tru_t += len(tr); fa_t += fa; mins_t += mins; sacc.append(sa)
        print(f"{SESSIONS[gi].split('/')[-1][:30]:30s} {acc*100:7.1f}% "
              f"{hits:4d}/{len(tr):<5d} {fa/mins:9.1f} {sa:11.1f}%")
    print("-" * 74)
    print(f"{'TOPLAM':30s} {np.mean(accs)*100:7.1f}% {hits_t:4d}/{tru_t:<5d} "
          f"{fa_t/mins_t:9.1f} {np.mean(sacc):11.1f}%")
    print(f"\nOlay yakalama orani: {hits_t}/{tru_t} = {hits_t/tru_t*100:.0f}%"
          f"  (eski esik: 4/49 = 8%)")
    print(f"Durum dogrulugu    : {np.mean(sacc):.1f}%   (eski esik: 44.6%)")

    final = RandomForestClassifier(n_estimators=400, class_weight="balanced",
                                   min_samples_leaf=2, random_state=0, n_jobs=-1)
    final.fit(X, y)
    imp = sorted(zip(FEATURE_NAMES, final.feature_importances_),
                 key=lambda kv: -kv[1])[:6]
    print("\nEn onemli ozellikler: " + ", ".join(f"{n} {v:.3f}" for n, v in imp))

    out = ROOT / "analysis/models/transition_model.joblib"
    joblib.dump({"model": final, "win_sec": WIN, "step_sec": STEP,
                 "base_n": BASE_N, "base_pctl": BASE_PCTL, "enter": ENTER,
                 "exit": EXIT, "smooth": SMOOTH, "refrac": REFRAC,
                 "features": FEATURE_NAMES}, out)
    print(f"\nKaydedildi: {out}")


if __name__ == "__main__":
    main()
