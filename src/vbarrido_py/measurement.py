from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ToneResult:
    frequency_hz: float
    amplitude_v: float
    phase_deg: float


def measure_tone(samples: np.ndarray, sample_rate_hz: float, expected_hz: float) -> ToneResult:
    samples = np.asarray(samples, dtype=float)
    samples = samples - np.mean(samples)
    n = samples.size
    if n < 8:
        raise ValueError("not enough samples")

    t = np.arange(n) / sample_rate_hz
    w = 2.0 * math.pi * expected_hz
    sin_ref = np.sin(w * t)
    cos_ref = np.cos(w * t)

    a = 2.0 / n * float(np.dot(samples, sin_ref))
    b = 2.0 / n * float(np.dot(samples, cos_ref))
    amplitude = math.hypot(a, b)
    phase = math.degrees(math.atan2(b, a))
    return ToneResult(expected_hz, amplitude, phase)


def gain_db(response_amp: float, reference_amp: float) -> float:
    if response_amp <= 0 or reference_amp <= 0:
        return float("-inf")
    return 20.0 * math.log10(response_amp / reference_amp)


def phase_delta_deg(response_phase: float, reference_phase: float) -> float:
    delta = response_phase - reference_phase
    while delta <= -180.0:
        delta += 360.0
    while delta > 180.0:
        delta -= 360.0
    return delta
