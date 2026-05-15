from __future__ import annotations

import time
from ctypes import byref, c_bool, c_double, c_int32, c_size_t, c_wchar_p
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .config import ChannelConfig, SweepConfig


@dataclass(frozen=True)
class Acquisition:
    sample_rate_hz: float
    reference: np.ndarray
    response: np.ndarray


class InstrumentBackend(Protocol):
    def close(self) -> None: ...
    def acquire_at(self, frequency_hz: float, config: SweepConfig) -> Acquisition: ...


def clamp_sample_rate(sample_rate_hz: float, config: SweepConfig) -> float:
    return min(max(sample_rate_hz, config.min_sample_rate_hz), config.max_sample_rate_hz)


def discover_virtualbench_resource(candidates: list[str] | None = None) -> str:
    names = []
    if candidates:
        names.extend(candidates)
    names.extend(["VB8012-30DF172"])

    seen: set[str] = set()
    errors: list[str] = []
    for name in names:
        device_name = name.strip()
        if not device_name or device_name.upper() == "SIMULATED" or device_name in seen:
            continue
        seen.add(device_name)
        try:
            backend = VirtualBenchPyBackend(device_name)
            backend.close()
            return device_name
        except Exception as exc:
            errors.append(f"{device_name}: {exc}")
    detail = "; ".join(errors) if errors else "sin candidatos"
    raise RuntimeError(f"No se pudo detectar VirtualBench automaticamente ({detail}).")


class SimulatedBackend:
    def __init__(self, rc_hz: float = 1_000.0) -> None:
        self.rc_hz = rc_hz

    def close(self) -> None:
        return None

    def acquire_at(self, frequency_hz: float, config: SweepConfig) -> Acquisition:
        sample_rate = clamp_sample_rate(config.sample_rate_multiplier * frequency_hz, config)
        n = max(int(max(config.cycles, 1) * sample_rate / frequency_hz), 512)
        t = np.arange(n) / sample_rate
        reference = config.amplitude_v * np.sin(2 * np.pi * frequency_hz * t)

        ratio = frequency_hz / self.rc_hz
        mag = 1.0 / np.sqrt(1.0 + ratio * ratio)
        phase = -np.arctan(ratio)
        response = config.amplitude_v * mag * np.sin(2 * np.pi * frequency_hz * t + phase)
        return Acquisition(sample_rate, reference, response)


class VirtualBenchPyBackend:
    """Thin adapter around NI/third-party pyvirtualbench packages.

    The public Python API differs between VirtualBench package builds, so this
    backend keeps the hardware calls in one place and fails with actionable
    messages when an installed package exposes different method names.
    """

    def __init__(self, resource: str) -> None:
        self.resource = resource
        try:
            from pyvirtualbench import PyVirtualBench  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "No se encontro pyvirtualbench. Instala el driver/API de NI VirtualBench y el paquete "
                "Python correspondiente, o usa el modo simulacion."
            ) from exc

        self._vb = PyVirtualBench("" if resource.upper() == "SIMULATED" else resource)
        self._device = self._vb
        self._fgen = self._open_module(("acquire_function_generator", "get_function_generator", "fgen"))
        self._mso = self._open_module(("acquire_mixed_signal_oscilloscope", "get_mixed_signal_oscilloscope", "mso"))

    def _open_module(self, names: tuple[str, ...]):
        for name in names:
            candidate = getattr(self._device, name, None)
            if candidate is None:
                continue
            return candidate() if callable(candidate) else candidate
        raise RuntimeError(
            "El objeto pyvirtualbench no expone los modulos esperados FGEN/MSO. "
            "Revisa la version del paquete pyvirtualbench instalada."
        )

    def close(self) -> None:
        for obj in (getattr(self, "_fgen", None), getattr(self, "_mso", None), getattr(self, "_device", None)):
            close = getattr(obj, "close", None) or getattr(obj, "release", None)
            if callable(close):
                close()

    def acquire_at(self, frequency_hz: float, config: SweepConfig) -> Acquisition:
        sample_rate = clamp_sample_rate(config.sample_rate_multiplier * frequency_hz, config)
        sample_count = max(int(max(config.cycles, 1) * sample_rate / frequency_hz), 512)

        self._stop_if_running(self._mso)
        self._configure_fgen(frequency_hz, config)
        self._configure_mso(sample_rate, sample_count, config)
        if config.settle_s > 0:
            time.sleep(config.settle_s)
        reference, response = self._read_mso(sample_count, config)
        return Acquisition(sample_rate, reference, response)

    def _stop_if_running(self, obj: object) -> None:
        stop = getattr(obj, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass

    def _configure_fgen(self, frequency_hz: float, config: SweepConfig) -> None:
        for name in ("configure_standard_waveform", "configure_standard_waveform_fgen"):
            method = getattr(self._fgen, name, None)
            if not callable(method):
                continue
            try:
                from pyvirtualbench.pyvirtualbench import Waveform  # type: ignore

                method(Waveform.SINE, config.amplitude_v, config.dc_offset_v, frequency_hz, 50.0)
            except TypeError:
                method(waveform="sine", amplitude=config.amplitude_v, dc_offset=config.dc_offset_v, frequency=frequency_hz)
            break
        else:
            raise RuntimeError("FGEN no tiene un metodo compatible para configurar onda senoidal.")

        run = getattr(self._fgen, "run", None) or getattr(self._fgen, "start", None)
        if callable(run):
            run()

    def _configure_mso(self, sample_rate_hz: float, sample_count: int, config: SweepConfig) -> None:
        configure_channel = getattr(self._mso, "configure_analog_channel", None)
        if callable(configure_channel):
            from pyvirtualbench.pyvirtualbench import MsoCoupling, MsoProbeAttenuation  # type: ignore

            for channel_config in (config.ch1, config.ch2):
                try:
                    configure_channel(
                        channel_config.channel,
                        True,
                        10.0,
                        0.0,
                        self._probe_attenuation_enum(MsoProbeAttenuation, channel_config.probe_attenuation),
                        self._coupling_enum(MsoCoupling, channel_config.coupling),
                    )
                except TypeError:
                    configure_channel(channel=channel_config.channel, enabled=True, range=10.0, offset=0.0)

        for name in ("configure_timing", "configure_sample_clock_timing"):
            method = getattr(self._mso, name, None)
            if not callable(method):
                continue
            try:
                from pyvirtualbench.pyvirtualbench import MsoSamplingMode  # type: ignore

                method(sample_rate_hz, sample_count / sample_rate_hz, 1e-6, MsoSamplingMode.SAMPLE)
            except TypeError:
                method(sample_rate=sample_rate_hz, sample_count=sample_count)
            break

        trigger = getattr(self._mso, "configure_analog_edge_trigger", None)
        if callable(trigger):
            trigger_config = self._trigger_channel_config(config)
            try:
                from pyvirtualbench.pyvirtualbench import Edge, MsoTriggerInstance  # type: ignore

                trigger(
                    trigger_config.trigger_reference,
                    self._trigger_edge_enum(Edge, trigger_config.trigger_slope),
                    trigger_config.trigger_level_v,
                    trigger_config.trigger_hysteresis_v,
                    MsoTriggerInstance.A,
                )
            except TypeError:
                trigger(
                    channel=trigger_config.trigger_reference,
                    level=trigger_config.trigger_level_v,
                    slope=trigger_config.trigger_slope.lower(),
                )

    def _trigger_channel_config(self, config: SweepConfig) -> ChannelConfig:
        for channel_config in (config.ch1, config.ch2):
            if channel_config.channel == config.ch_reference:
                return channel_config
        return config.ch1

    def _coupling_enum(self, enum_type: object, value: str) -> object:
        name = value.strip().upper()
        return getattr(enum_type, name, getattr(enum_type, "DC"))

    def _probe_attenuation_enum(self, enum_type: object, value: str) -> object:
        normalized = value.strip().lower().replace("x", "X")
        names = {
            "1X": ("ATTENUATION_1X", "X1", "ONE_X"),
            "10X": ("ATTENUATION_10X", "X10", "TEN_X"),
        }.get(normalized.upper(), ("ATTENUATION_1X", "X1", "ONE_X"))
        for name in names:
            candidate = getattr(enum_type, name, None)
            if candidate is not None:
                return candidate
        return getattr(enum_type, "ATTENUATION_1X")

    def _trigger_edge_enum(self, enum_type: object, value: str) -> object:
        normalized = value.strip().upper()
        names = {
            "RISING": ("RISING", "RISE"),
            "FALLING": ("FALLING", "FALL"),
            "EITHER": ("EITHER", "ANY"),
        }.get(normalized, ("RISING", "RISE"))
        for name in names:
            candidate = getattr(enum_type, name, None)
            if candidate is not None:
                return candidate
        return getattr(enum_type, "RISING")

    def _read_mso(self, sample_count: int, config: SweepConfig) -> tuple[np.ndarray, np.ndarray]:
        run = getattr(self._mso, "run", None)
        if callable(run):
            try:
                run(True)
            except TypeError:
                run()

        if all(hasattr(self._mso, name) for name in ("nilcicapi", "instrument_handle", "library_handle")):
            return self._read_armstrap_mso(sample_count)

        read = getattr(self._mso, "read_analog", None) or getattr(self._mso, "read", None)
        if not callable(read):
            raise RuntimeError("MSO no tiene un metodo compatible para leer canales analogicos.")
        data = read(sample_count * 2)
        if isinstance(data, (list, tuple)) and len(data) >= 2:
            return np.asarray(data[0], dtype=float), np.asarray(data[1], dtype=float)
        raise RuntimeError("Formato de lectura MSO no reconocido por el backend pyvirtualbench.")

    def _read_armstrap_mso(self, sample_count: int) -> tuple[np.ndarray, np.ndarray]:
        from pyvirtualbench.pyvirtualbench import MsoTriggerReason, PyVirtualBenchException, Status, Timestamp  # type: ignore

        channel_count = 2
        data_size = sample_count * channel_count * 4
        raw = (c_double * data_size)()
        data_size_out = c_size_t(0)
        data_stride = c_size_t(0)
        initial_timestamp = Timestamp(0, 0, 0, 0)
        trigger_timestamp = Timestamp(0, 0, 0, 0)
        trigger_reason = c_int32(0)
        status = self._mso.nilcicapi.niVB_MSO_ReadAnalog(
            self._mso.instrument_handle,
            byref(raw),
            c_size_t(data_size),
            byref(data_size_out),
            byref(data_stride),
            byref(initial_timestamp),
            byref(trigger_timestamp),
            byref(trigger_reason),
        )
        if status != Status.SUCCESS:
            raise PyVirtualBenchException(status, self._mso.nilcicapi, self._mso.library_handle)

        reason = MsoTriggerReason(trigger_reason.value)
        if reason.name == "FORCED":
            raise RuntimeError("MSO no detecto trigger normal; revisa conexion/senal.")

        stride = max(int(data_stride.value), channel_count)
        values = np.ctypeslib.as_array(raw)[: int(data_size_out.value)]
        if values.size < channel_count:
            raise RuntimeError("MSO devolvio muy pocas muestras.")
        return values[0::stride][:sample_count].copy(), values[1::stride][:sample_count].copy()


VirtualBenchVisaBackend = VirtualBenchPyBackend


def configure_power_supply_voltage(
    resource: str,
    channel: str = "ps/+25V",
    voltage_v: float = 10.0,
    current_limit_a: float = 0.1,
    enable_outputs: bool = True,
) -> tuple[float, float]:
    try:
        from pyvirtualbench import PyVirtualBench  # type: ignore
    except ImportError as exc:
        raise RuntimeError("No se encontro pyvirtualbench.") from exc

    vb = PyVirtualBench(resource)
    ps = vb.acquire_power_supply()
    try:
        ps.configure_voltage_output(c_wchar_p(channel), voltage_v, current_limit_a)
        ps.enable_all_outputs(enable_outputs)
        actual_v, actual_i, _state = ps.read_output(c_wchar_p(channel))
        return actual_v, actual_i
    finally:
        ps.release()
        vb.release()


def configure_power_supply_rails(
    resource: str,
    positive_voltage_v: float = 10.0,
    negative_voltage_v: float = -10.0,
    current_limit_a: float = 0.1,
    six_voltage_v: float = 0.0,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    try:
        from pyvirtualbench import PyVirtualBench  # type: ignore
    except ImportError as exc:
        raise RuntimeError("No se encontro pyvirtualbench.") from exc

    vb = PyVirtualBench(resource)
    ps = vb.acquire_power_supply()
    try:
        ps.configure_voltage_output(c_wchar_p("ps/+25V"), positive_voltage_v, current_limit_a)
        ps.configure_voltage_output(c_wchar_p("ps/-25V"), negative_voltage_v, current_limit_a)
        ps.configure_voltage_output(c_wchar_p("ps/+6V"), six_voltage_v, min(max(current_limit_a, 0.01), 1.0))
        ps.enable_all_outputs(True)
        pos_v, pos_i, _pos_state = ps.read_output(c_wchar_p("ps/+25V"))
        neg_v, neg_i, _neg_state = ps.read_output(c_wchar_p("ps/-25V"))
        six_v, six_i, _six_state = ps.read_output(c_wchar_p("ps/+6V"))
        return (pos_v, pos_i), (neg_v, neg_i), (six_v, six_i)
    finally:
        ps.release()
        vb.release()


def disable_power_supply_outputs(resource: str) -> None:
    try:
        from pyvirtualbench import PyVirtualBench  # type: ignore
    except ImportError as exc:
        raise RuntimeError("No se encontro pyvirtualbench.") from exc

    vb = PyVirtualBench(resource)
    ps = vb.acquire_power_supply()
    try:
        ps.enable_all_outputs(False)
    finally:
        ps.release()
        vb.release()
