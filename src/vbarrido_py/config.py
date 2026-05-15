from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChannelConfig:
    channel: str = "mso/1"
    coupling: str = "DC"
    trigger_hysteresis_v: float = 0.01
    trigger_reference: str = "mso/1"
    trigger_slope: str = "Rising"
    trigger_level_v: float = 0.0
    probe_attenuation: str = "1x"


@dataclass(frozen=True)
class SweepConfig:
    start_hz: float = 100.0
    stop_hz: float = 1_000_000.0
    points: int = 80
    amplitude_v: float = 1.0
    dc_offset_v: float = 0.0
    settle_s: float = 0.05
    min_gain_db: float = -30.0
    sample_rate_multiplier: float = 10.0
    cycles: int = 30
    averages: int = 1
    sweep_mode: str = "Por décadas"
    min_sample_rate_hz: float = 20_000.0
    max_sample_rate_hz: float = 20_000_000.0
    resource: str = "SIMULATED"
    ch_response: str = "mso/1"
    ch_reference: str = "mso/2"
    ch1: ChannelConfig = field(default_factory=lambda: ChannelConfig(channel="mso/1", trigger_reference="mso/1"))
    ch2: ChannelConfig = field(default_factory=lambda: ChannelConfig(channel="mso/2", trigger_reference="mso/2"))
