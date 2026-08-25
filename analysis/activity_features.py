"""CSI ham verisinden aktivite sınıflandırma özellik çıkarımı.

train_own_activity_classifier.py ve live_server.py tarafından ortak kullanılıyor.
"""
import re

import numpy as np

BRACKET_RE = re.compile(r"\[([\d\s-]+)\]")

# ESP32 LLTF çıktısı 64 alt-taşıyıcı veriyor ama hepsi kullanılabilir değil
# (2026-08-24'te ölçüldü):
#   index 0     -> sabit 146 (CSI değil, başlık değeri; hiç değişmiyor)
#   index 1-5   -> sabit/sıfır (kenar guard bandı)
#   index 32    -> sıfır (DC alt-taşıyıcısı, hiç veri taşımaz)
#   index 59-63 -> sıfır (diğer kenar guard bandı)
# Bunlar özelliklere sıfır bilgi katıyor ama hareket enerjisi ortalamasını
# sulandırıyordu: aynı veride tümü=1.46, sadece geçerliler=1.76.
VALID_SUBCARRIERS = list(range(6, 32)) + list(range(33, 59))


def valid_only(amp_matrix):
    """Sadece bilgi taşıyan alt-taşıyıcıları döndürür (bkz. VALID_SUBCARRIERS)."""
    if amp_matrix.ndim != 2 or amp_matrix.shape[1] <= max(VALID_SUBCARRIERS):
        return amp_matrix  # beklenmedik format - dokunma
    return amp_matrix[:, VALID_SUBCARRIERS]


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
    """(paket, alt-taşıyıcı) -> özet istatistik: mean/std/min/max her subcarrier için.

    Sadece geçerli alt-taşıyıcılar kullanılır (52 adet) - sabit/boş olanlar
    modele bilgi katmıyor.
    """
    amp_matrix = valid_only(amp_matrix)
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
    return float(np.abs(np.diff(valid_only(amp_matrix), axis=0)).mean())


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

# --- Hareket tespiti: bantgeçiren yöntem (2026-08-24 akşam) ---
# NEDEN: Kartlar odanın iki ucuna taşınınca (RSSI -59 -> -71) her paketin CSI
# kestirimi çok gürültülendi; hareketsizken bile ardışık-fark enerjisi 1.4'ten
# 6.5'e çıktı ve yürüme bu gürültünün içinde kayboldu (oran 1.11x, eşik
# doğruluğu %69).
# ÇÖZÜM: Ölçüm gürültüsü BEYAZ (tüm frekanslara yayılı), yürümenin ürettiği
# Doppler ise 0.3-3 Hz bandında. O bandı süzünce gürültünün çoğu atılıyor.
# ÖLÇÜM (aynı veri, 4 sn pencere): oran 1.56x, eşik doğruluğu %93.
MOVEMENT_BAND = (0.3, 3.0)
MOVEMENT_WINDOW_SEC = 4.0   # 0.3 Hz'in periyodu 3.3 sn - 2 sn'lik pencereye sığmaz


# --- Yürüme sınıflandırması için özellikler (2026-08-25) ---
# TASARIM KURALI: SADECE ÖLÇEKTEN BAĞIMSIZ ÖZELLİK.
# Bu projedeki tüm büyük başarısızlıkların kaynağı mutlak genlik kullanmaktı:
# oturumdan oturuma donanım sürüklenmesi (otomatik kazanç, sıcaklık, verici
# gücü) sınıf farkından 5 kat büyük kayma üretiyor (bkz. Bölüm 3.7).
# Buradaki özelliklerin hepsi ORAN ya da ŞEKİL - genel seviye 2 katına çıksa
# bile değişmezler.
#
# Fizik: ölçüm gürültüsü BEYAZ (tüm frekanslara yayılı), hareketin ürettiği
# Doppler ise 0.3-3 Hz'de toplanıyor. Spektrumun ŞEKLİ bu yüzden hareketi
# ele veriyor ve şekil, mutlak güçten bağımsız.
FEATURE_BANDS = [(0.2, 0.6), (0.6, 1.5), (1.5, 3.0),
                 (3.0, 6.0), (6.0, 12.0), (12.0, 25.0)]
WALKING_FEATURE_NAMES = (
    [f"bant_{lo}_{hi}" for lo, hi in FEATURE_BANDS]
    + ["log_sinyal_gurultu", "spektral_merkez", "degisim_katsayisi",
       "lag1_otokorelasyon", "aktif_altttasiyici_orani"])


def walking_features(amp_matrix, fs):
    """(paket, alt-taşıyıcı) + örnekleme hızı -> ölçekten bağımsız özellik vektörü.

    EĞİTİM ve CANLI SİSTEM AYNI FONKSİYONU KULLANMALI - ayrışırlarsa model
    canlıda sessizce yanlış çalışır. Bu yüzden burada, ortak dosyada duruyor.
    """
    x = valid_only(amp_matrix).astype(float)
    n = x.shape[0]
    if n < 16 or fs <= 0:
        return np.zeros(len(WALKING_FEATURE_NAMES))

    per_pkt = x.mean(axis=1)
    x = x - x.mean(axis=0)                      # her alt-taşıyıcıyı ortala

    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    power = (np.abs(np.fft.rfft(x, axis=0)) ** 2).mean(axis=1)

    band_e = []
    for lo, hi in FEATURE_BANDS:
        sel = (freqs >= lo) & (freqs < hi)
        band_e.append(float(power[sel].sum()) if sel.any() else 0.0)
    band_e = np.array(band_e)
    total = band_e.sum() + 1e-12
    band_frac = band_e / total                  # spektrumun ŞEKLİ (toplamı 1)

    # sinyal/gürültü: hareket bandı (0.3-3) / beyaz gürültü bandı (8-25)
    lo_sel = (freqs >= 0.3) & (freqs < 3.0)
    hi_sel = (freqs >= 8.0) & (freqs < 25.0)
    lo_e = float(power[lo_sel].sum()) if lo_sel.any() else 0.0
    hi_e = float(power[hi_sel].sum()) if hi_sel.any() else 0.0
    snr = np.log10((lo_e + 1e-12) / (hi_e + 1e-12))

    centroid = float((freqs * power).sum() / (power.sum() + 1e-12))

    mean_lv = float(per_pkt.mean())
    cv = float(per_pkt.std() / (abs(mean_lv) + 1e-12))   # ölçekten bağımsız

    d = per_pkt - per_pkt.mean()
    denom = float((d * d).sum()) + 1e-12
    lag1 = float((d[:-1] * d[1:]).sum() / denom)

    var = x.var(axis=0)
    active = float((var > np.median(var)).mean()) if len(var) else 0.0

    return np.concatenate([band_frac, [snr, centroid, cv, lag1, active]])


def movement_energy_bandpass(amp_matrix, fs, band=MOVEMENT_BAND):
    """Hareket şiddeti: sadece 0.3-3 Hz bandındaki değişimin gücü.

    fs: pencerenin gerçek örnekleme hızı (paket sayısı / süre). Paket hızı
    dalgalandığı için sabit varsayılamaz, çağıran taraf ölçüp vermeli.
    Filtre uygulanamazsa (çok kısa pencere / çok düşük hız) ardışık-fark
    yöntemine düşer.
    """
    x = valid_only(amp_matrix)
    lo, hi = band
    nyq = fs / 2.0
    if len(x) < 30 or hi >= nyq:
        return movement_energy(amp_matrix)
    try:
        from scipy.signal import butter, filtfilt
        b, a = butter(3, [lo / nyq, hi / nyq], btype="band")
        return float(np.abs(filtfilt(b, a, x, axis=0)).mean())
    except Exception:
        return movement_energy(amp_matrix)
