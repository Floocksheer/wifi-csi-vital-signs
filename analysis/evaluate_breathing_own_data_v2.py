"""Nefes pipeline'ının iyileştirilmiş versiyonu — amplitude + faz + otokorelasyon
yöntemlerini kendi 3 gerçek kaydımızla karşılaştırır.

NOT: Sentetik/UT-HAR dataset'lerinde nefes etiketi yok, bu yüzden bu değerlendirme
sadece kendi elle-sayılmış 3 kayıtla yapılabiliyor (own_breathing_normal/slow/fast.csv).
"""
import numpy as np
import pandas as pd
from scipy import signal
from scipy.interpolate import interp1d

from bpm_pipeline import BREATHING_BAND

RESAMPLE_FS = 10.0

RECORDINGS = [
    ("../data/own_breathing_normal.csv", 24.0, "Normal"),
    ("../data/own_breathing_slow.csv", 15.0, "Yavaş/Derin"),
    ("../data/own_breathing_fast.csv", 43.5, "Hızlı/Sığ"),
]


def parse_packet(csi_str):
    """'[110 96 6 0 ...]' -> (amplitude[128], phase[128]) per subcarrier."""
    nums = np.array([int(x) for x in csi_str.strip("[]").split()])
    pairs = nums[: len(nums) // 2 * 2].reshape(-1, 2).astype(float)
    amplitude = np.sqrt(pairs[:, 0] ** 2 + pairs[:, 1] ** 2)
    phase = np.arctan2(pairs[:, 0], pairs[:, 1])
    return amplitude, phase


def bpm_zero_crossing(sig, fs, band):
    sos = signal.butter(4, band, btype="bandpass", fs=fs, output="sos")
    filtered = signal.sosfiltfilt(sos, sig)
    zc = np.where(np.diff(np.sign(filtered)))[0]
    return (len(zc) / 2 / (len(sig) / fs)) * 60, filtered


def bpm_autocorrelation(sig, fs, band):
    sos = signal.butter(4, band, btype="bandpass", fs=fs, output="sos")
    filtered = signal.sosfiltfilt(sos, sig)
    autocorr = np.correlate(filtered, filtered, mode="full")
    autocorr = autocorr[len(autocorr) // 2:]  # sadece pozitif lag'ler

    min_lag = int(fs * 60 / (band[1] * 60))  # bandın en yüksek frekansına karşılık gelen min lag
    max_lag = int(fs * 60 / (band[0] * 60))  # bandın en düşük frekansına karşılık gelen max lag
    max_lag = min(max_lag, len(autocorr) - 1)
    if min_lag >= max_lag:
        return np.nan
    search = autocorr[min_lag:max_lag]
    peak_lag = min_lag + np.argmax(search)
    period_sec = peak_lag / fs
    return 60 / period_sec if period_sec > 0 else np.nan


def process_recording(path):
    df = pd.read_csv(path)
    parsed = df["CSI_DATA"].apply(parse_packet)
    amp_matrix = np.stack(parsed.apply(lambda x: x[0]).values)   # (paket, 128)
    phase_matrix = np.stack(parsed.apply(lambda x: x[1]).values)  # (paket, 128)

    t = (df["local_timestamp"] - df["local_timestamp"].iloc[0]) / 1e6
    duration = t.iloc[-1]
    t_uniform = np.arange(0, duration, 1 / RESAMPLE_FS)

    # Amplitude: subcarrier ortalaması, sonra uniform ızgaraya yeniden örnekle
    amp_signal_raw = amp_matrix.mean(axis=1)
    amp_signal = interp1d(t, amp_signal_raw, kind="linear", fill_value="extrapolate")(t_uniform)

    # Faz: her subcarrier ayrı unwrap edilir, sonra ortalanır, sonra yeniden örneklenir
    phase_unwrapped = np.unwrap(phase_matrix, axis=0)
    phase_signal_raw = phase_unwrapped.mean(axis=1)
    phase_signal = interp1d(t, phase_signal_raw, kind="linear", fill_value="extrapolate")(t_uniform)

    return amp_signal, phase_signal


def main():
    print(f"{'Kayıt':<14}{'Gerçek':>8}{'Amp-ZC':>10}{'Faz-ZC':>10}{'Amp-Autocorr':>14}{'Faz-Autocorr':>14}")
    errs = {"amp_zc": [], "phase_zc": [], "amp_ac": [], "phase_ac": []}

    for path, true_bpm, label in RECORDINGS:
        amp_signal, phase_signal = process_recording(path)

        est_amp_zc, _ = bpm_zero_crossing(amp_signal, RESAMPLE_FS, BREATHING_BAND)
        est_phase_zc, _ = bpm_zero_crossing(phase_signal, RESAMPLE_FS, BREATHING_BAND)
        est_amp_ac = bpm_autocorrelation(amp_signal, RESAMPLE_FS, BREATHING_BAND)
        est_phase_ac = bpm_autocorrelation(phase_signal, RESAMPLE_FS, BREATHING_BAND)

        errs["amp_zc"].append(abs(est_amp_zc - true_bpm))
        errs["phase_zc"].append(abs(est_phase_zc - true_bpm))
        errs["amp_ac"].append(abs(est_amp_ac - true_bpm))
        errs["phase_ac"].append(abs(est_phase_ac - true_bpm))

        print(f"{label:<14}{true_bpm:>8.1f}{est_amp_zc:>10.1f}{est_phase_zc:>10.1f}{est_amp_ac:>14.1f}{est_phase_ac:>14.1f}")

    print()
    print("Ortalama mutlak hata:")
    for k, v in errs.items():
        print(f"  {k:<14}: {np.mean(v):.2f} BPM")


if __name__ == "__main__":
    main()
