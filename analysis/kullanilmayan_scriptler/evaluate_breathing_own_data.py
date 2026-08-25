"""Kendi ESP32 verimizle nefes (breathing) BPM pipeline'ını değerlendirir.

CSI_DATA sütunu, ESP32-CSI-Tool'un ham int8 I/Q dizisi (256 değer = 128 subcarrier x 2).
Paketler arası zaman aralığı düzensiz olduğu için (~9-10 paket/sn ortalama), gerçek
local_timestamp'e göre uniform bir zaman eksenine yeniden örnekliyoruz.
"""
import sys

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from bpm_pipeline import estimate_bpm_zero_crossing, estimate_bpm_fft, BREATHING_BAND

RESAMPLE_FS = 10.0  # uniform yeniden örnekleme hızı (Hz)


def parse_csi_amplitude(csi_str):
    """'[110 96 6 0 ...]' -> ortalama subcarrier genliği (skaler)."""
    nums = np.array([int(x) for x in csi_str.strip("[]").split()])
    pairs = nums[: len(nums) // 2 * 2].reshape(-1, 2)  # (subcarrier, [imag, real])
    amplitude = np.sqrt(pairs[:, 0].astype(float) ** 2 + pairs[:, 1].astype(float) ** 2)
    return amplitude.mean()


def main(csv_path, true_bpm=None):
    df = pd.read_csv(csv_path)
    print(f"Toplam paket: {len(df)}")

    df["amplitude"] = df["CSI_DATA"].apply(parse_csi_amplitude)
    t = (df["local_timestamp"] - df["local_timestamp"].iloc[0]) / 1e6  # saniyeye çevir

    duration = t.iloc[-1]
    avg_fs = len(df) / duration
    print(f"Süre: {duration:.1f}s, ortalama örnekleme hızı: {avg_fs:.2f} Hz")

    # Uniform zaman eksenine yeniden örnekle (düzensiz paket aralıkları için)
    t_uniform = np.arange(0, duration, 1 / RESAMPLE_FS)
    interp_fn = interp1d(t, df["amplitude"].values, kind="linear", fill_value="extrapolate")
    amp_uniform = interp_fn(t_uniform)

    est_zc = estimate_bpm_zero_crossing(amp_uniform, RESAMPLE_FS, BREATHING_BAND)
    est_fft = estimate_bpm_fft(amp_uniform, RESAMPLE_FS, BREATHING_BAND)

    print()
    print(f"Tahmin (zero-crossing): {est_zc:.2f} BPM")
    print(f"Tahmin (FFT peak):      {est_fft:.2f} BPM")
    if true_bpm is not None:
        print()
        print(f"GERÇEK (elle sayım):    {true_bpm:.2f} BPM")
        print(f"Hata (zero-crossing):   {abs(est_zc - true_bpm):.2f} BPM")
        print(f"Hata (FFT):             {abs(est_fft - true_bpm):.2f} BPM")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "../data/own_breathing_normal.csv"
    true_bpm = float(sys.argv[2]) if len(sys.argv) > 2 else None
    main(path, true_bpm)
