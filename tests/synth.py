"""Synthetic 'speech' for tests: voiced bursts (harmonic tone with a syllable-like envelope) at known word times over a low noise floor. No network, no real audio needed."""
import wave
import numpy as np
SR = 16000
def make_speech(words, total, sr=SR, floor_db=-62.0, level_db=-20.0, seed=1):
    """words = [(start, end), ...] seconds -> float32 mono signal of `total` seconds"""
    rng = np.random.default_rng(seed); n = int(total * sr); x = rng.standard_normal(n).astype(np.float32) * 10 ** (floor_db / 20)
    t = np.arange(n) / sr
    for a, b in words:
        i, j = int(a * sr), min(n, int(b * sr))
        if j <= i: continue
        seg = t[i:j]; f0 = 140 + 30 * np.sin(2 * np.pi * 2 * seg); ph = 2 * np.pi * np.cumsum(f0) / sr
        v = sum(np.sin(k * ph) / k for k in (1, 2, 3, 4)); env = np.minimum(1, np.minimum((seg - a) / 0.02, (b - seg) / 0.03)) * (0.75 + 0.25 * np.sin(2 * np.pi * 4 * seg) ** 2)
        x[i:j] += (v * env * 10 ** (level_db / 20) / 1.6).astype(np.float32)
    return x
def write_wav(path, x, sr=SR):
    with wave.open(path, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
SENTENCES = [  # (word list with (start, end)) for a 2-sentence speech with realistic gaps: words 0.25-0.4 s, 0.08 s between words, 0.7 s between sentences
]
def sentence(t0, n, wlen=0.3, gap=0.08):
    out = []; t = t0
    for _ in range(n): out.append((round(t, 3), round(t + wlen, 3))); t += wlen + gap
    return out, t - gap
