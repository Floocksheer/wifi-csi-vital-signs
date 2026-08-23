"""CSI ham verisinden aktivite sınıflandırma özellik çıkarımı.

train_own_activity_classifier.py ve live_server.py tarafından ortak kullanılıyor.
"""
import re

import numpy as np

BRACKET_RE = re.compile(r"\[([\d\s-]+)\]")


def parse_amplitude_matrix(text):
    """Ham CSV metni -> (paket, 128) genlik matrisi.

    pandas.read_csv KULLANMIYORUZ: bazı kayıtlarda seri okuma sırasında satır
    sonu karakterleri kaybolup birden fazla paket tek satırda birleşiyor, bu da
    pandas'ın sütun hizalamasını bozuyor. Regex ile "[...]" bloklarını satır
    sınırından bağımsız buluyoruz - hem bozuk hem sağlam satırlarda çalışır.
    """
    rows = []
    for match in BRACKET_RE.finditer(text):
        nums = np.array([int(x) for x in re.findall(r"-?\d+", match.group(1))])
        if len(nums) < 4:
            continue
        pairs = nums[: len(nums) // 2 * 2].reshape(-1, 2).astype(float)
        amplitude = np.sqrt(pairs[:, 0] ** 2 + pairs[:, 1] ** 2)
        rows.append(amplitude)

    if not rows:
        return np.empty((0, 0))

    lengths = [len(r) for r in rows]
    common_len = max(set(lengths), key=lengths.count)
    rows = [r for r in rows if len(r) == common_len]
    return np.stack(rows)


def parse_amplitude_matrix_from_file(csv_path):
    with open(csv_path) as f:
        return parse_amplitude_matrix(f.read())


def extract_features(amp_matrix):
    """(paket, 128) -> (512,) özet istatistik: mean/std/min/max her subcarrier için."""
    return np.concatenate([
        amp_matrix.mean(axis=0),
        amp_matrix.std(axis=0),
        amp_matrix.min(axis=0),
        amp_matrix.max(axis=0),
    ])


def movement_energy(amp_matrix):
    """Ardışık paketler arası ortalama mutlak değişim = "ne kadar kıpırdıyor".

    Ölçülen dağılım (2sn'lik pencereler, 2026-08-19):
      statik (otur/ayakta): ortalama ~2.1, 95. yüzdelik 3.28
      ani hareket anları:   medyan ~3.2, max 8.3
    İki dağılım örtüşüyor çünkü "ani hareket" kayıtlarının çoğu pencere aslında
    sessiz (hareket 8 saniyenin sadece ~1 saniyesinde oluyor).
    """
    if len(amp_matrix) < 2:
        return 0.0
    return float(np.abs(np.diff(amp_matrix, axis=0)).mean())


def sliding_windows(amp_matrix, win_sec, total_sec=8, overlap=0.5):
    """8 saniyelik kaydı daha kısa, örtüşmeli pencerelere böler (veri artırma).

    Kısa pencere hem canlı gecikmeyi azaltıyor hem de eğitim örneği sayısını
    artırdığı için doğruluğu yükseltiyor (2026-08-19 ölçümü: 8sn/18 örnek %77.8,
    2sn/126 örnek %83.3).
    """
    n = len(amp_matrix)
    pkt = max(4, int(n * win_sec / total_sec))
    step = max(1, int(pkt * (1 - overlap)))
    for s in range(0, n - pkt + 1, step):
        yield amp_matrix[s:s + pkt]
