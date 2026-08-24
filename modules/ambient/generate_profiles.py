#!/usr/bin/env python3
"""Synthesize placeholder ambient WAV profiles for the Ambient Layer.

Why synthesize?
---------------
Shipping real restaurant/office recordings needs licenses. These placeholders
are band-filtered, gently modulated noise beds that approximate the *spectral*
feel of each environment so AmbientMixer works end-to-end without external assets.

Replace restaurant.wav / office.wav with royalty-free recordings for demos you
show publicly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
SAMPLE_RATE = 48_000
DURATION_SEC = 12.0  # long enough that loops don't feel obvious too quickly


def _bandlimited_noise(
    n: int,
    low_hz: float,
    high_hz: float,
    sample_rate: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """White noise → FFT band-pass → real signal."""
    noise = rng.standard_normal(n).astype(np.float64)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    spectrum[~mask] = 0.0
    filtered = np.fft.irfft(spectrum, n=n)
    # Normalize to ~[-1, 1] peak
    peak = np.max(np.abs(filtered)) or 1.0
    return (filtered / peak).astype(np.float32)


def _slow_amplitude_modulation(
    signal: np.ndarray,
    sample_rate: int,
    rate_hz: float,
    depth: float,
) -> np.ndarray:
    """Gentle volume swell so the bed feels less static than pure noise."""
    t = np.arange(len(signal), dtype=np.float32) / sample_rate
    envelope = 1.0 - depth + depth * (0.5 + 0.5 * np.sin(2.0 * np.pi * rate_hz * t))
    return signal * envelope.astype(np.float32)


def generate_restaurant(sample_rate: int = SAMPLE_RATE, duration: float = DURATION_SEC) -> np.ndarray:
    """Mid-band energy + soft modulation ≈ distant chatter / clatter bed."""
    rng = np.random.default_rng(42)
    n = int(sample_rate * duration)
    bed = _bandlimited_noise(n, low_hz=200.0, high_hz=4500.0, sample_rate=sample_rate, rng=rng)
    # Sparse brighter clicks (cutlery-ish impulses), very quiet
    clicks = np.zeros(n, dtype=np.float32)
    for _ in range(int(duration * 3)):
        idx = int(rng.integers(0, n - int(0.01 * sample_rate)))
        length = int(0.008 * sample_rate)
        click = rng.standard_normal(length).astype(np.float32) * 0.15
        # Highpass-ish by differencing
        click = np.diff(click, prepend=click[0])
        clicks[idx : idx + length] += click
    mixed = 0.75 * bed + 0.25 * clicks
    mixed = _slow_amplitude_modulation(mixed, sample_rate, rate_hz=0.15, depth=0.25)
    peak = np.max(np.abs(mixed)) or 1.0
    return (mixed / peak * 0.35).astype(np.float32)  # keep headroom for TTS


def generate_office(sample_rate: int = SAMPLE_RATE, duration: float = DURATION_SEC) -> np.ndarray:
    """Low HVAC hum + faint mid murmur ≈ open-plan office."""
    rng = np.random.default_rng(7)
    n = int(sample_rate * duration)
    hum = _bandlimited_noise(n, low_hz=40.0, high_hz=400.0, sample_rate=sample_rate, rng=rng)
    murmur = _bandlimited_noise(n, low_hz=300.0, high_hz=2500.0, sample_rate=sample_rate, rng=rng)
    mixed = 0.7 * hum + 0.3 * murmur
    mixed = _slow_amplitude_modulation(mixed, sample_rate, rate_hz=0.07, depth=0.15)
    peak = np.max(np.abs(mixed)) or 1.0
    return (mixed / peak * 0.28).astype(np.float32)


def main() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    restaurant = generate_restaurant()
    office = generate_office()

    restaurant_path = PROFILES_DIR / "restaurant.wav"
    office_path = PROFILES_DIR / "office.wav"

    sf.write(str(restaurant_path), restaurant, SAMPLE_RATE, subtype="PCM_16")
    sf.write(str(office_path), office, SAMPLE_RATE, subtype="PCM_16")

    print(f"Wrote {restaurant_path} ({len(restaurant) / SAMPLE_RATE:.1f}s @ {SAMPLE_RATE} Hz)")
    print(f"Wrote {office_path} ({len(office) / SAMPLE_RATE:.1f}s @ {SAMPLE_RATE} Hz)")


if __name__ == "__main__":
    main()
