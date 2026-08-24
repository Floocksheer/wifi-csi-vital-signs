"""guided_capture_udp.py çıktısını değerlendirir (2026-08-24 akşam).

İki kart da aynı olayı farklı bir yoldan görüyor. Bu modül üç şeyi ölçüyor:
  1. Her kart TEK BAŞINA ne kadar iyi ayırt ediyor
  2. İKİSİ BİRLEŞTİRİLİNCE ne kadar iyi (uzamsal çeşitliliğin kazancı)
  3. Hareket (yürüme) kapısı çalışıyor mu

Zaman ekseni: laptobun saati (CSV'nin son sütunu recv_time). İki kartın kendi
saatleri bağımsız olduğu için ortak eksen bu olmak zorunda.

Kullanım:
    python evaluate_udp_session.py ../data/udp_session/test
"""
import json
import re
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut

from activity_features import extract_features, movement_energy_bandpass

TRANSITION_MARGIN_SEC = 3.0
POSTURE_WINDOW_SEC = 2.0
MOVE_WINDOW_SEC = 4.0
STEP_SEC = 1.0
BRACKET_RE = re.compile(r"\[([\d\s-]+)\]")


def parse_udp_csv(path):
    """(recv_times, amp_matrix) - laptop saatiyle hizalı."""
    times, rows = [], []
    with open(path) as f:
        next(f)
        for line in f:
            if not line.startswith("CSI_DATA"):
                continue
            m = BRACKET_RE.search(line)
            if not m:
                continue
            tail = line[m.end():].strip().lstrip(",")
            try:
                recv = float(tail.split(",")[0])
            except (ValueError, IndexError):
                continue
            nums = np.array([int(x) for x in re.findall(r"-?\d+", m.group(1))])
            if len(nums) < 4:
                continue
            pairs = nums[: len(nums) // 2 * 2].reshape(-1, 2).astype(float)
            rows.append(np.sqrt(pairs[:, 0] ** 2 + pairs[:, 1] ** 2))
            times.append(recv)

    if not rows:
        return np.array([]), np.empty((0, 0))
    lengths = [len(r) for r in rows]
    common = max(set(lengths), key=lengths.count)
    keep = [i for i, r in enumerate(rows) if len(r) == common]
    return (np.array([times[i] for i in keep]),
            np.stack([rows[i] for i in keep]))


def phase_windows(times, amp, phases, win_sec, step_sec=STEP_SEC, min_pkt=25):
    """(pencere, etiket, faz, pencere_baslangici) listesi."""
    out = []
    for p in phases:
        start = p["recv_ts_start"] + TRANSITION_MARGIN_SEC
        end = p["recv_ts_end"] - 0.3
        w = start
        while w + win_sec <= end:
            sel = np.where((times >= w) & (times < w + win_sec))[0]
            if len(sel) >= min_pkt:
                out.append((amp[sel], p["label"], p["phase"], w, p["posture"]))
            w += step_sec
    return out


def logo_accuracy(X, y, groups, n_estimators=300):
    accs = []
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        clf = RandomForestClassifier(n_estimators=n_estimators, random_state=42,
                                     n_jobs=-1)
        clf.fit(X[tr], y[tr])
        accs.append(clf.score(X[te], y[te]))
    return float(np.mean(accs)), float(np.std(accs))


def main(base):
    with open(base + ".json") as f:
        meta = json.load(f)
    phases = meta["phases"]
    files = meta["files"]
    print(f"Oturum: {base}")
    print(f"  {len(phases)} faz, komutlar: {' -> '.join(meta['cues'])}")

    data = {}
    for role, path in sorted(files.items()):
        t, a = parse_udp_csv(path)
        if len(t) == 0:
            print(f"  {role}: VERİ YOK")
            continue
        fs = len(t) / (t[-1] - t[0])
        data[role] = (t, a, fs)
        print(f"  {role}: {len(t)} paket, {fs:.1f} Hz, {a.shape[1]} alt-taşıyıcı")

    if not data:
        raise SystemExit("Hiç veri yok.")

    # --- 1. Hareket kapısı (sınıflar arası enerji farkı) ---
    print("\n--- Hareket kapısı (bantgeçiren 0.3-3 Hz, 4 sn pencere) ---")
    for role, (t, a, fs) in data.items():
        wins = phase_windows(t, a, phases, MOVE_WINDOW_SEC)
        if not wins:
            continue
        by_cue = {}
        for w, lbl, ph, ws, posture in wins:
            by_cue.setdefault(posture, []).append(movement_energy_bandpass(w, fs))
        parts = [f"{c}={np.mean(v):.2f}" for c, v in sorted(by_cue.items())]
        print(f"  {role}: " + "  ".join(parts))
        if len(by_cue) == 2:
            (c1, v1), (c2, v2) = sorted(by_cue.items(), key=lambda kv: np.mean(kv[1]))
            print(f"      oran ({c2}/{c1}) = {np.mean(v2) / np.mean(v1):.2f}x")

    # --- 2. Sınıflandırma: tek kart vs birleşik ---
    print("\n--- Sınıflandırma (LeaveOneGroupOut, gruplar = fazlar) ---")
    per_board = {}
    for role, (t, a, fs) in data.items():
        wins = phase_windows(t, a, phases, POSTURE_WINDOW_SEC)
        if len(wins) < 6:
            continue
        X = np.array([extract_features(w) for w, _, _, _, _ in wins])
        y = np.array([lbl for _, lbl, _, _, _ in wins])
        g = np.array([ph for _, _, ph, _, _ in wins])
        starts = np.array([ws for _, _, _, ws, _ in wins])
        per_board[role] = (X, y, g, starts)
        if len(set(y)) < 2:
            continue
        acc, sd = logo_accuracy(X, y, g)
        print(f"  {role} tek başına : {acc:.1%} (std={sd:.1%}, {len(y)} pencere)")

    # Birleştirme: aynı pencere başlangıcına sahip satırları eşle
    if len(per_board) == 2:
        (rA, (XA, yA, gA, sA)), (rB, (XB, yB, gB, sB)) = sorted(per_board.items())
        common = sorted(set(np.round(sA, 2)) & set(np.round(sB, 2)))
        if len(common) >= 6:
            ia = {round(v, 2): i for i, v in enumerate(sA)}
            ib = {round(v, 2): i for i, v in enumerate(sB)}
            idxA = [ia[c] for c in common]
            idxB = [ib[c] for c in common]
            Xc = np.hstack([XA[idxA], XB[idxB]])
            yc, gc = yA[idxA], gA[idxA]
            if len(set(yc)) >= 2:
                acc, sd = logo_accuracy(Xc, yc, gc)
                print(f"  İKİSİ BİRLİKTE   : {acc:.1%} (std={sd:.1%}, "
                      f"{len(yc)} pencere, {Xc.shape[1]} özellik)")
        else:
            print("  (birleştirme için yeterli ortak pencere yok)")

    print("\n  (şans seviyesi: %50)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../data/udp_session/test")
