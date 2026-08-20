"""Bandpass filtre + zero-crossing ile CSI'dan nefes/kalp atışı BPM tahmini.

RuView'in dokümante ettiği yönteme dayanıyor:
  Nefes:      0.1-0.5 Hz bandpass
  Kalp atışı: 0.8-2.0 Hz bandpass

synthetic_vital_signs dataset'i üzerinde test edildi (2026-08-18, 20 pencere):
  10 saniyelik pencerelerle zero-crossing yöntemi ortalama 8.62 BPM hata verdi
  (FFT-peak yöntemi 12.56 BPM ile daha kötü performans gösterdi, kısa pencerede
  frekans çözünürlüğü yetersiz kalıyor). Detay: evaluate_heart_rate_synthetic.py
"""
import numpy as np
from scipy import signal

BREATHING_BAND = (0.1, 0.5)
HEART_RATE_BAND = (0.8, 2.0)


def estimate_bpm_zero_crossing(raw_signal, fs, band=HEART_RATE_BAND):
    """Ham (tek boyutlu) sinyalden bandpass filtre + zero-crossing ile BPM tahmini."""
    sos = signal.butter(4, band, btype="bandpass", fs=fs, output="sos")
    filtered = signal.sosfiltfilt(sos, raw_signal)

    duration_sec = len(raw_signal) / fs
    zero_crossings = np.where(np.diff(np.sign(filtered)))[0]
    num_cycles = len(zero_crossings) / 2
    return (num_cycles / duration_sec) * 60


def combine_phase_subcarriers(phase_matrix):
    """(zaman, subcarrier) faz matrisini -> tek boyutlu ortalama faz sinyaline indirger.

    Faz her subcarrier için ayrı ayrı unwrap edilir (zaman ekseninde), sonra ortalanır.
    synthetic_vital_signs testinde amplitude ortalamasından daha iyi sonuç verdi
    (2026-08-19: 7.32 BPM hata, amplitude ortalamasıyla 8.62 BPM'e karşı).
    """
    unwrapped = np.unwrap(phase_matrix, axis=0)
    return unwrapped.mean(axis=1)


def estimate_bpm_fft(raw_signal, fs, band=HEART_RATE_BAND):
    """Ham sinyalden bandpass filtre + FFT tepe frekansı ile BPM tahmini."""
    sos = signal.butter(4, band, btype="bandpass", fs=fs, output="sos")
    filtered = signal.sosfiltfilt(sos, raw_signal)

    fft_vals = np.abs(np.fft.rfft(filtered))
    fft_freqs = np.fft.rfftfreq(len(filtered), d=1 / fs)
    band_mask = (fft_freqs >= band[0]) & (fft_freqs <= band[1])
    peak_freq = fft_freqs[band_mask][np.argmax(fft_vals[band_mask])]
    return peak_freq * 60
