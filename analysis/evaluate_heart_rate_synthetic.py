"""synthetic_vital_signs dataset'i üzerinde bpm_pipeline.py'yi değerlendirir."""
import numpy as np
import pyarrow.parquet as pq

from bpm_pipeline import estimate_bpm_zero_crossing, estimate_bpm_fft, HEART_RATE_BAND

FS = 200.0  # 17.28M satır / 86400 saniye = 200 Hz varsayımı
WINDOW_SEC = 10
WINDOW_SAMPLES = int(FS * WINDOW_SEC)
N_WINDOWS = 20

AMP_COLS = [f"amp_{i}" for i in range(15)]


def main():
    pf = pq.ParquetFile("../data/synthetic_vital_signs/synthetic_csi_data_1440min.parquet")
    table = pf.read_row_group(0, columns=AMP_COLS + ["heart_rate_bpm", "occupancy"])
    df = table.to_pandas()

    errs_zc, errs_fft = [], []
    for w in range(N_WINDOWS):
        start = w * WINDOW_SAMPLES
        end = start + WINDOW_SAMPLES
        seg = df.iloc[start:end]
        if len(seg) < WINDOW_SAMPLES or seg["occupancy"].min() == 0:
            continue

        true_bpm = seg["heart_rate_bpm"].mean()
        raw_signal = seg[AMP_COLS].mean(axis=1).values

        est_zc = estimate_bpm_zero_crossing(raw_signal, FS, HEART_RATE_BAND)
        est_fft = estimate_bpm_fft(raw_signal, FS, HEART_RATE_BAND)

        errs_zc.append(abs(est_zc - true_bpm))
        errs_fft.append(abs(est_fft - true_bpm))
        print(f"Pencere {w}: gerçek={true_bpm:6.2f}  zc={est_zc:6.2f} (hata {abs(est_zc-true_bpm):5.2f})  fft={est_fft:6.2f} (hata {abs(est_fft-true_bpm):5.2f})")

    print()
    print(f"Ortalama mutlak hata (zero-crossing): {np.mean(errs_zc):.2f} BPM  (n={len(errs_zc)})")
    print(f"Ortalama mutlak hata (FFT):            {np.mean(errs_fft):.2f} BPM  (n={len(errs_fft)})")


if __name__ == "__main__":
    main()
