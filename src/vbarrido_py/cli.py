from __future__ import annotations

import argparse
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from .config import ChannelConfig, SweepConfig
from .instrument import SimulatedBackend, VirtualBenchPyBackend, discover_virtualbench_resource
from .sweep import run_sweep, write_csv


def load_config(path: str | Path) -> SweepConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8-sig"))
    defaults = SweepConfig()
    device = raw.get("device", {})
    channel1 = raw.get("channel1", {})
    channel2 = raw.get("channel2", {})
    return SweepConfig(
        start_hz=float(raw.get("start_hz", defaults.start_hz)),
        stop_hz=float(raw.get("stop_hz", defaults.stop_hz)),
        points=int(raw.get("points", defaults.points)),
        amplitude_v=float(raw.get("amplitude_v", defaults.amplitude_v)),
        dc_offset_v=float(raw.get("dc_offset_v", defaults.dc_offset_v)),
        settle_s=float(raw.get("settle_s", defaults.settle_s)),
        min_gain_db=float(raw.get("min_gain_db", defaults.min_gain_db)),
        sample_rate_multiplier=float(raw.get("sample_rate_multiplier", defaults.sample_rate_multiplier)),
        cycles=int(raw.get("cycles", defaults.cycles)),
        averages=int(raw.get("averages", defaults.averages)),
        sweep_mode=str(raw.get("sweep_mode", defaults.sweep_mode)),
        min_sample_rate_hz=float(raw.get("min_sample_rate_hz", defaults.min_sample_rate_hz)),
        max_sample_rate_hz=float(raw.get("max_sample_rate_hz", defaults.max_sample_rate_hz)),
        resource=str(device.get("resource", "SIMULATED")),
        ch_response=str(device.get("ch_response", "mso/1")),
        ch_reference=str(device.get("ch_reference", "mso/2")),
        ch1=ChannelConfig(
            channel=str(channel1.get("channel", defaults.ch1.channel)),
            coupling=str(channel1.get("coupling", defaults.ch1.coupling)),
            trigger_hysteresis_v=float(channel1.get("trigger_hysteresis_v", defaults.ch1.trigger_hysteresis_v)),
            trigger_reference=str(channel1.get("trigger_reference", defaults.ch1.trigger_reference)),
            trigger_slope=str(channel1.get("trigger_slope", defaults.ch1.trigger_slope)),
            trigger_level_v=float(channel1.get("trigger_level_v", defaults.ch1.trigger_level_v)),
            probe_attenuation=str(channel1.get("probe_attenuation", defaults.ch1.probe_attenuation)),
        ),
        ch2=ChannelConfig(
            channel=str(channel2.get("channel", defaults.ch2.channel)),
            coupling=str(channel2.get("coupling", defaults.ch2.coupling)),
            trigger_hysteresis_v=float(channel2.get("trigger_hysteresis_v", defaults.ch2.trigger_hysteresis_v)),
            trigger_reference=str(channel2.get("trigger_reference", defaults.ch2.trigger_reference)),
            trigger_slope=str(channel2.get("trigger_slope", defaults.ch2.trigger_slope)),
            trigger_level_v=float(channel2.get("trigger_level_v", defaults.ch2.trigger_level_v)),
            probe_attenuation=str(channel2.get("probe_attenuation", defaults.ch2.probe_attenuation)),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Barrido de frecuencia tipo VBarrido")
    parser.add_argument("--config", default="examples/config.toml")
    parser.add_argument("--output", default="sweep.csv")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--gui", action="store_true", help="abre la interfaz grafica")
    args = parser.parse_args()

    if args.gui:
        from .gui import main as gui_main

        gui_main()
        return

    config = load_config(args.config)
    if args.simulate:
        backend = SimulatedBackend()
    else:
        resource = discover_virtualbench_resource([config.resource])
        config = SweepConfig(**{**config.__dict__, "resource": resource})
        backend = VirtualBenchPyBackend(config.resource)
    try:
        points = run_sweep(config, backend)
    finally:
        backend.close()
    write_csv(args.output, points)
    print(f"wrote {len(points)} points to {args.output}")


if __name__ == "__main__":
    main()

