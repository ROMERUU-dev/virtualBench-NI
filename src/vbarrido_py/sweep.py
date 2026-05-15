from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .config import SweepConfig
from .instrument import Acquisition, InstrumentBackend
from .measurement import gain_db, measure_tone, phase_delta_deg


@dataclass(frozen=True)
class SweepPoint:
    frequency_hz: float
    gain_v: float
    gain_db: float
    phase_deg: float
    reference_amp_v: float
    response_amp_v: float


ProgressCallback = Callable[[SweepPoint, int, int], None]
TraceCallback = Callable[[Acquisition, float], None]


def _frequencies(config: SweepConfig) -> np.ndarray:
    mode = config.sweep_mode.strip().lower()
    if mode.startswith("lin"):
        return np.linspace(config.start_hz, config.stop_hz, config.points)
    return np.geomspace(config.start_hz, config.stop_hz, config.points)


def run_sweep(
    config: SweepConfig,
    backend: InstrumentBackend,
    progress: ProgressCallback | None = None,
    trace: TraceCallback | None = None,
    stop_on_min_gain: bool = True,
) -> list[SweepPoint]:
    frequencies = _frequencies(config)
    points: list[SweepPoint] = []

    for index, frequency in enumerate(frequencies, start=1):
        reference_amps: list[float] = []
        response_amps: list[float] = []
        phases: list[float] = []
        acquisition: Acquisition | None = None

        for _average_index in range(max(config.averages, 1)):
            acquisition = backend.acquire_at(float(frequency), config)
            ref = measure_tone(acquisition.reference, acquisition.sample_rate_hz, float(frequency))
            rsp = measure_tone(acquisition.response, acquisition.sample_rate_hz, float(frequency))
            reference_amps.append(ref.amplitude_v)
            response_amps.append(rsp.amplitude_v)
            phases.append(phase_delta_deg(rsp.phase_deg, ref.phase_deg))

        if acquisition is not None and trace is not None:
            trace(acquisition, float(frequency))

        reference_amp = float(np.mean(reference_amps))
        response_amp = float(np.mean(response_amps))
        phase_vector = np.mean(np.exp(1j * np.deg2rad(phases)))
        phase = float(np.rad2deg(np.angle(phase_vector)))
        g_v = response_amp / reference_amp if reference_amp > 0 else 0.0
        g_db = gain_db(response_amp, reference_amp)
        point = SweepPoint(float(frequency), g_v, g_db, phase, reference_amp, response_amp)
        points.append(point)
        if progress is not None:
            progress(point, index, len(frequencies))
        if stop_on_min_gain and g_db < config.min_gain_db:
            break

    return points


def write_csv(path: str | Path, points: list[SweepPoint]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frequency_hz", "gain_v", "gain_db", "phase_deg", "reference_amp_v", "response_amp_v"])
        for p in points:
            writer.writerow([p.frequency_hz, p.gain_v, p.gain_db, p.phase_deg, p.reference_amp_v, p.response_amp_v])
