"""3 nefes kaydı için ham/filtrelenmiş sinyal + FFT spektrumu grafiklerini üretir."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal
from scipy.interpolate import interp1d

from evaluate_breathing_own_data import parse_csi_amplitude, RESAMPLE_FS
from bpm_pipeline import BREATHING_BAND

RECORDINGS = [
    ("../data/own_breathing_normal.csv", "Normal Tempo (gerçek: 24 BPM)"),
    ("../data/own_breathing_slow.csv", "Yavaş/Derin Tempo (gerçek: 15 BPM)"),
    ("../data/own_breathing_fast.csv", "Hızlı/Sığ Tempo (gerçek: 43.5 BPM)"),
]


def process(csv_path):
    df = pd.read_csv(csv_path)
    df["amplitude"] = df["CSI_DATA"].apply(parse_csi_amplitude)
    t = (df["local_timestamp"] - df["local_timestamp"].iloc[0]) / 1e6
    duration = t.iloc[-1]

    t_uniform = np.arange(0, duration, 1 / RESAMPLE_FS)
    interp_fn = interp1d(t, df["amplitude"].values, kind="linear", fill_value="extrapolate")
    amp_uniform = interp_fn(t_uniform)

    sos = signal.butter(4, BREATHING_BAND, btype="bandpass", fs=RESAMPLE_FS, output="sos")
    filtered = signal.sosfiltfilt(sos, amp_uniform)

    fft_vals = np.abs(np.fft.rfft(amp_uniform - amp_uniform.mean()))
    fft_freqs = np.fft.rfftfreq(len(amp_uniform), d=1 / RESAMPLE_FS)

    return t_uniform, amp_uniform, filtered, fft_freqs, fft_vals


def main():
    fig, axes = plt.subplots(len(RECORDINGS), 3, figsize=(15, 10))

    for row, (path, title) in enumerate(RECORDINGS):
        t, raw, filtered, freqs, fft_vals = process(path)

        ax = axes[row, 0]
        ax.plot(t, raw, linewidth=0.8, color="tab:blue")
        ax.set_title(f"{title}\nHam Genlik Sinyali")
        ax.set_xlabel("Zaman (s)")
        ax.set_ylabel("Genlik")

        ax = axes[row, 1]
        ax.plot(t, filtered, linewidth=1, color="tab:green")
        ax.axhline(0, color="gray", linewidth=0.5)
        ax.set_title("Filtrelenmiş Sinyal (0.1-0.5 Hz)")
        ax.set_xlabel("Zaman (s)")

        ax = axes[row, 2]
        mask = freqs <= 1.5
        ax.plot(freqs[mask], fft_vals[mask], color="tab:orange")
        ax.axvspan(BREATHING_BAND[0], BREATHING_BAND[1], color="green", alpha=0.15, label="Nefes bandı")
        ax.set_title("FFT Spektrumu")
        ax.set_xlabel("Frekans (Hz)")
        ax.legend(fontsize=7)

    plt.tight_layout()
    out_path = "plots/breathing_signals.png"
    import os
    os.makedirs("plots", exist_ok=True)
    plt.savefig(out_path, dpi=120)
    print(f"Kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
