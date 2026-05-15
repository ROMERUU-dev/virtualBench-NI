from __future__ import annotations

import math
import queue
import threading
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .config import ChannelConfig, SweepConfig
from .instrument import (
    Acquisition,
    VirtualBenchPyBackend,
    configure_power_supply_rails,
    disable_power_supply_outputs,
    discover_virtualbench_resource,
)
from .sweep import SweepPoint, run_sweep, write_csv

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - Tk can still run without the optional image preview.
    Image = None
    ImageTk = None


CHANNELS = ("mso/1", "mso/2")
COUPLINGS = ("AC", "DC")
TRIGGER_REFERENCES = ("browse...", "mso/1", "mso/2", "refresh")
TRIGGER_SLOPES = ("Rising", "Falling", "Either")
PROBE_ATTENUATIONS = ("1x", "10x")
SWEEP_MODES = ("Por décadas", "Lineal")
SIDE_TAB_WIDTH_CHARS = 24

THEMES = {
    "Oscuro": {
        "bg": "#050814",
        "panel": "#0b1220",
        "panel_alt": "#111827",
        "plot": "#0b1220",
        "grid": "#2f3b52",
        "text": "#f8fafc",
        "muted": "#94a3b8",
        "subtle": "#cbd5e1",
        "tab": "#0b1220",
        "tab_active": "#1f2937",
        "table": "#0b1220",
        "table_heading": "#111827",
        "scroll_trough": "#020617",
        "scroll": "#111827",
        "accent": "#38bdf8",
        "accent_soft": "#93c5fd",
        "accent_2": "#f97316",
        "accent_2_soft": "#fdba74",
        "ok": "#22c55e",
        "warn": "#f59e0b",
        "error": "#ef4444",
    },
    "Claro": {
        "bg": "#f4f7fb",
        "panel": "#ffffff",
        "panel_alt": "#e8eef7",
        "plot": "#ffffff",
        "grid": "#d7dee9",
        "text": "#0f172a",
        "muted": "#64748b",
        "subtle": "#334155",
        "tab": "#e8eef7",
        "tab_active": "#ffffff",
        "table": "#ffffff",
        "table_heading": "#e2e8f0",
        "scroll_trough": "#dbe3ef",
        "scroll": "#94a3b8",
        "accent": "#2563eb",
        "accent_soft": "#60a5fa",
        "accent_2": "#ea580c",
        "accent_2_soft": "#fb923c",
        "ok": "#16a34a",
        "warn": "#d97706",
        "error": "#dc2626",
    },
}

PRESETS = {
    "Barrido rápido": {
        "start": "100",
        "stop": "1000000",
        "points": "40",
        "cycles": "10",
        "averages": "1",
        "sweep_mode": "Por décadas",
        "settle": "0.02",
    },
    "Barrido preciso": {
        "start": "100",
        "stop": "1000000",
        "points": "160",
        "cycles": "50",
        "averages": "4",
        "sweep_mode": "Por décadas",
        "settle": "0.08",
    },
    "Filtro RC": {
        "start": "10",
        "stop": "100000",
        "points": "100",
        "cycles": "30",
        "averages": "2",
        "sweep_mode": "Por décadas",
        "settle": "0.05",
    },
    "Amplificador": {
        "start": "20",
        "stop": "1000000",
        "points": "120",
        "cycles": "30",
        "averages": "2",
        "sweep_mode": "Por décadas",
        "settle": "0.05",
    },
    "Audio 20 Hz-20 kHz": {
        "start": "20",
        "stop": "20000",
        "points": "120",
        "cycles": "40",
        "averages": "2",
        "sweep_mode": "Por décadas",
        "settle": "0.05",
    },
    "Diagnóstico amplio": {
        "start": "1",
        "stop": "10000000",
        "points": "90",
        "cycles": "20",
        "averages": "1",
        "sweep_mode": "Por décadas",
        "settle": "0.03",
    },
    "Resonancia estrecha": {
        "start": "100",
        "stop": "10000",
        "points": "240",
        "cycles": "60",
        "averages": "4",
        "sweep_mode": "Lineal",
        "settle": "0.08",
    },
    "Alta frecuencia": {
        "start": "10000",
        "stop": "10000000",
        "points": "140",
        "cycles": "25",
        "averages": "2",
        "sweep_mode": "Por décadas",
        "settle": "0.03",
    },
    "Personalizado": {},
}

PRESET_HINTS = {
    "Barrido rápido": "Exploración inicial para ubicar la forma general de la respuesta con el menor tiempo posible.",
    "Barrido preciso": "Más puntos, más ciclos y promedios para una curva más estable cuando ya conoces el rango útil.",
    "Filtro RC": "Perfil equilibrado para filtros pasivos de primer orden y pruebas de corte en varias décadas.",
    "Amplificador": "Cobertura amplia para revisar ganancia y fase de etapas activas sin volver el barrido demasiado lento.",
    "Audio 20 Hz-20 kHz": "Preset centrado en banda audible; útil para amplificadores, filtros y cadenas de audio.",
    "Diagnóstico amplio": "Busca comportamiento global desde muy baja hasta muy alta frecuencia antes de afinar el rango.",
    "Resonancia estrecha": "Usa barrido lineal denso para ver con más detalle picos o valles concentrados en una banda reducida.",
    "Alta frecuencia": "Pensado para circuitos rápidos donde interesa priorizar el extremo superior del rango del MSO.",
    "Personalizado": "No cambia los valores actuales; sirve para partir de una configuración ajustada manualmente.",
}


def _software_version() -> str:
    try:
        return version("vbarrido-py")
    except PackageNotFoundError:
        return "0.1.0"


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _show(self, _event: tk.Event[tk.Misc]) -> None:
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self._tip,
            text=self.text,
            justify="left",
            background="#f8fafc",
            foreground="#111827",
            borderwidth=1,
            relief="solid",
            padx=8,
            pady=6,
            wraplength=320,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


class MenuFrame(ttk.Frame):
    def __init__(self, master: tk.Widget, padding: tuple[int, int] = (12, 12)) -> None:
        super().__init__(master, style="Panel.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.content = ttk.Frame(self, padding=padding, style="Panel.TFrame")
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.columnconfigure(1, weight=1)

    def apply_palette(self, palette: dict[str, str]) -> None:
        _ = palette


class VoltageGauge(tk.Canvas):
    def __init__(self, master: tk.Widget, title: str, limit_v: float, color: str) -> None:
        super().__init__(master, width=116, height=128, highlightthickness=0, background="#050814")
        self.title = title
        self.limit_v = limit_v
        self.color = color
        self.background_color = "#050814"
        self.panel_color = "#0b1220"
        self.grid_color = "#2f3b52"
        self.text_color = "#f8fafc"
        self.subtle_color = "#cbd5e1"
        self.muted_color = "#94a3b8"
        self.value_v = 0.0
        self.draw(0.0)

    def _arc_line(self, fraction: float, color: str, width: int, offset_y: int = 0) -> None:
        cx, cy, radius = 58, 64 + offset_y, 40
        start_deg = 220
        sweep_deg = 280 * fraction
        if sweep_deg <= 0:
            return
        points: list[float] = []
        steps = max(int(sweep_deg / 3), 2)
        for i in range(steps + 1):
            angle = math.radians(start_deg - (sweep_deg * i / steps))
            points.extend([cx + math.cos(angle) * radius, cy + math.sin(angle) * radius])
        self.create_line(points, fill=color, width=width, smooth=True, capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def draw(self, value_v: float) -> None:
        self.value_v = value_v
        self.delete("all")
        fraction = min(abs(value_v) / self.limit_v, 1.0)

        self.create_oval(15, 21, 101, 107, fill=self.panel_color, outline=self.grid_color, width=1)
        self._arc_line(1.0, self.grid_color, 13)
        self._arc_line(fraction, "#0b1020", 15, offset_y=2)
        self._arc_line(fraction, self.color, 13)
        if fraction > 0:
            self._arc_line(max(fraction - 0.03, 0), "#ffffff", 3)

        self.create_text(58, 15, text=self.title, fill=self.text_color, font=("Segoe UI", 9, "bold"))
        self.create_text(58, 63, text=f"{value_v:+.2f}", fill=self.text_color, font=("Segoe UI", 15, "bold"))
        self.create_text(58, 82, text="V", fill=self.subtle_color, font=("Segoe UI", 9, "bold"))
        self.create_text(58, 119, text=f"{abs(value_v) / self.limit_v * 100:4.0f}%", fill=self.muted_color, font=("Segoe UI", 8))

    def apply_palette(self, palette: dict[str, str], color: str) -> None:
        self.background_color = palette["bg"]
        self.panel_color = palette["panel"]
        self.grid_color = palette["grid"]
        self.text_color = palette["text"]
        self.subtle_color = palette["subtle"]
        self.muted_color = palette["muted"]
        self.color = color
        self.configure(background=self.background_color)
        self.draw(self.value_v)


class TimeTracePanel(ttk.Frame):
    def __init__(self, master: tk.Widget, palette: dict[str, str]) -> None:
        super().__init__(master, padding=(0, 8, 0, 0), style="Body.TFrame")
        self.palette = palette
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Voltaje vs tiempo", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.figure = Figure(figsize=(7.2, 2.1), dpi=125)
        self.figure.patch.set_facecolor(self.palette["bg"])
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        self._reference_line = None
        self._response_line = None
        self._layout_ready = False
        self._draw_empty()

    def _style_axis(self) -> None:
        self.ax.set_facecolor(self.palette["plot"])
        self.ax.tick_params(colors=self.palette["subtle"])
        for spine in self.ax.spines.values():
            spine.set_color(self.palette["grid"])
        self.ax.title.set_color(self.palette["text"])
        self.ax.xaxis.label.set_color(self.palette["subtle"])
        self.ax.yaxis.label.set_color(self.palette["subtle"])
        self.ax.grid(True, color=self.palette["grid"], linewidth=0.8, alpha=0.75)

    def _draw_empty(self) -> None:
        self.ax.clear()
        self._style_axis()
        self.ax.set_title("MSO/1 y MSO/2 vs Time", loc="left", fontsize=11)
        self.ax.set_xlabel("Tiempo (ms)")
        self.ax.set_ylabel("Voltaje (V)")
        (self._reference_line,) = self.ax.plot(
            [],
            [],
            color=self.palette["accent"],
            linewidth=1.25,
            antialiased=True,
            label="MSO/1 vs Time",
        )
        (self._response_line,) = self.ax.plot(
            [],
            [],
            color=self.palette["accent_2"],
            linewidth=1.25,
            antialiased=True,
            label="MSO/2 vs Time",
        )
        legend = self.ax.legend(loc="upper right", frameon=True, facecolor=self.palette["bg"], edgecolor=self.palette["grid"])
        for text in legend.get_texts():
            text.set_color(self.palette["text"])
        if not self._layout_ready:
            self.figure.tight_layout()
            self._layout_ready = True
        self.canvas.draw_idle()

    def apply_palette(self, palette: dict[str, str]) -> None:
        self.palette = palette
        self.figure.patch.set_facecolor(self.palette["bg"])
        self._draw_empty()

    def update_trace(self, payload: tuple[float, Acquisition, str, str]) -> None:
        frequency_hz, acquisition, reference_label, response_label = payload
        sample_count = len(acquisition.reference)
        if sample_count <= 0:
            return
        step = max(sample_count // 5000, 1)
        time_ms = [index / acquisition.sample_rate_hz * 1000.0 for index in range(0, sample_count, step)]
        reference = acquisition.reference[::step]
        response = acquisition.response[::step]

        if self._reference_line is None or self._response_line is None:
            self._draw_empty()
        self.ax.set_title(f"MSO temporal - {frequency_hz:.6g} Hz", loc="left", fontsize=11)
        self._reference_line.set_label(f"{reference_label.upper()} vs Time")
        self._response_line.set_label(f"{response_label.upper()} vs Time")
        self._reference_line.set_data(time_ms, reference)
        self._response_line.set_data(time_ms, response)
        self.ax.relim()
        self.ax.autoscale_view()
        legend = self.ax.get_legend()
        if legend is not None:
            legend_texts = legend.get_texts()
            if len(legend_texts) >= 2:
                legend_texts[0].set_text(f"{reference_label.upper()} vs Time")
                legend_texts[1].set_text(f"{response_label.upper()} vs Time")
        self.canvas.draw_idle()


class VBarridoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("VirtualBench Bode Workbench")
        self.geometry("1320x820")
        self.minsize(1120, 720)

        self.palette = THEMES["Claro"]
        self.defaults = SweepConfig()
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._detect_worker: threading.Thread | None = None
        self._points: list[SweepPoint] = []
        self._stop_requested = False
        self._last_trace_payload: tuple[float, Acquisition, str, str] | None = None
        self._pending_trace_payload: tuple[float, Acquisition, str, str] | None = None
        self._plot_redraw_after_id: str | None = None
        self._trace_redraw_after_id: str | None = None
        self._plot_layout_ready = False
        self.time_trace: TimeTracePanel | None = None
        self._info_image_original: object | None = None
        self._info_image_photo: object | None = None
        self._info_image_label: tk.Label | None = None
        self._info_image_width = 0
        self._menu_frames: list[MenuFrame] = []
        self._theme_widgets: list[tk.Widget] = []
        self.controls_notebook: ttk.Notebook | None = None
        self.tabs: dict[str, ttk.Frame] = {}
        self.progress_bar: ttk.Progressbar | None = None
        self._run_started_at = 0.0
        self._run_total_points = 0
        self._last_validation_errors: list[str] = []

        self._build_variables()
        self._build_style()
        self._build_ui()
        self._redraw_plot()
        self.after(100, self._poll_worker)
        self._detect_device()

    def _build_variables(self) -> None:
        self.theme_var = tk.StringVar(value="Claro")
        self.ui_mode_var = tk.StringVar(value="Experto")
        self.preset_var = tk.StringVar(value="Personalizado")
        self.preset_hint_var = tk.StringVar(value=PRESET_HINTS["Personalizado"])
        self.resource_var = tk.StringVar(value="")
        self.device_status_var = tk.StringVar(value="Detectando VirtualBench...")
        self.connection_step_var = tk.StringVar(value="1. Conexión: pendiente de detectar instrumento")
        self.signal_step_var = tk.StringVar(value="2. Señal: revise canales y amplitud")
        self.config_step_var = tk.StringVar(value="3. Configuración: complete los campos básicos")
        self.measure_step_var = tk.StringVar(value="4. Medición: lista cuando no haya errores")
        self.export_step_var = tk.StringVar(value="5. Exportación: disponible al terminar")
        self.summary_var = tk.StringVar(value="")
        self.validation_var = tk.StringVar(value="Revisando configuración...")
        self.progress_var = tk.StringVar(value="Progreso: 0%")
        self.response_var = tk.StringVar(value=self.defaults.ch_response)
        self.reference_var = tk.StringVar(value=self.defaults.ch_reference)
        self.start_var = tk.StringVar(value=f"{self.defaults.start_hz:g}")
        self.stop_var = tk.StringVar(value=f"{self.defaults.stop_hz:g}")
        self.points_var = tk.StringVar(value=f"{self.defaults.points:d}")
        self.cycles_var = tk.StringVar(value=f"{self.defaults.cycles:d}")
        self.sweep_mode_var = tk.StringVar(value=self.defaults.sweep_mode)
        self.averages_var = tk.StringVar(value=f"{self.defaults.averages:d}")
        self.amplitude_var = tk.StringVar(value=f"{self.defaults.amplitude_v:g}")
        self.offset_var = tk.StringVar(value=f"{self.defaults.dc_offset_v:g}")
        self.settle_var = tk.StringVar(value=f"{self.defaults.settle_s:g}")
        self.min_gain_var = tk.StringVar(value=f"{self.defaults.min_gain_db:g}")
        self.sample_mult_var = tk.StringVar(value=f"{self.defaults.sample_rate_multiplier:g}")
        self.status_var = tk.StringVar(value="Listo")
        self.last_point_var = tk.StringVar(value="Sin mediciones")
        self.export_csv_var = tk.BooleanVar(value=True)
        self.export_svg_var = tk.BooleanVar(value=False)
        self.target_gain_var = tk.StringVar(value="-3")
        self.mag_tolerance_var = tk.StringVar(value="1")
        self.phase_tolerance_var = tk.StringVar(value="5")
        self.ps_output_enabled_var = tk.BooleanVar(value=False)
        self.ps_pos_voltage_var = tk.StringVar(value="10.0")
        self.ps_neg_voltage_var = tk.StringVar(value="-10.0")
        self.ps_current_var = tk.StringVar(value="0.1")
        self.ps_six_enabled_var = tk.BooleanVar(value=False)
        self.ps_high_power_guard_var = tk.BooleanVar(value=True)
        self.stop_attenuation_var = tk.BooleanVar(value=False)
        self.channel_vars: dict[str, dict[str, tk.Variable]] = {
            "ch1": self._channel_variables(self.defaults.ch1),
            "ch2": self._channel_variables(self.defaults.ch2),
        }

    def _channel_variables(self, config: ChannelConfig) -> dict[str, tk.Variable]:
        return {
            "coupling": tk.StringVar(value=config.coupling),
            "trigger_hysteresis": tk.StringVar(value=f"{config.trigger_hysteresis_v:g}"),
            "trigger_reference": tk.StringVar(value=config.trigger_reference),
            "trigger_slope": tk.StringVar(value=config.trigger_slope),
            "trigger_level": tk.StringVar(value=f"{config.trigger_level_v:g}"),
            "probe_attenuation": tk.StringVar(value=config.probe_attenuation),
        }

    def _build_style(self) -> None:
        style = ttk.Style(self)
        p = self.palette
        self.configure(background=p["bg"])
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TFrame", background=p["bg"])
        style.configure("HeaderTitle.TLabel", background=p["bg"], foreground=p["text"], font=("Segoe UI", 15, "bold"))
        style.configure("HeaderStatus.TLabel", background=p["bg"], foreground=p["subtle"], font=("Segoe UI", 10))
        style.configure("Body.TFrame", background=p["bg"])
        style.configure("Panel.TFrame", background=p["bg"])
        style.configure("Card.TFrame", background=p["panel"])
        style.configure("Section.TLabel", background=p["bg"], foreground=p["text"], font=("Segoe UI", 10, "bold"))
        style.configure("CardTitle.TLabel", background=p["panel"], foreground=p["text"], font=("Segoe UI", 10, "bold"))
        style.configure("Card.TLabel", background=p["panel"], foreground=p["subtle"])
        style.configure("Hint.TLabel", background=p["bg"], foreground=p["muted"], font=("Segoe UI", 9))
        style.configure("Dark.TLabel", background=p["bg"], foreground=p["subtle"])
        style.configure("Good.TLabel", background=p["bg"], foreground=p["ok"], font=("Segoe UI", 9, "bold"))
        style.configure("Warn.TLabel", background=p["bg"], foreground=p["warn"], font=("Segoe UI", 9, "bold"))
        style.configure("Error.TLabel", background=p["bg"], foreground=p["error"], font=("Segoe UI", 9, "bold"))
        style.configure("Dark.TCheckbutton", background=p["bg"], foreground=p["subtle"])
        style.map("Dark.TCheckbutton", background=[("active", p["bg"])], foreground=[("active", p["text"])])
        style.configure("Treeview", background=p["table"], foreground=p["text"], fieldbackground=p["table"], rowheight=25)
        style.configure("Treeview.Heading", background=p["table_heading"], foreground=p["text"], font=("Segoe UI", 9, "bold"))
        style.configure("Run.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", background=p["tab"], foreground=p["muted"], padding=(12, 8), font=("Segoe UI", 9))
        style.map(
            "TNotebook.Tab",
            background=[("selected", p["tab_active"]), ("active", p["panel_alt"])],
            foreground=[("selected", p["text"]), ("active", p["text"])],
        )
        style.configure("Side.TNotebook", background=p["bg"], borderwidth=0, tabposition="wn", tabmargins=(0, 0, 8, 0))
        style.configure(
            "Side.TNotebook.Tab",
            background=p["tab"],
            foreground=p["subtle"],
            padding=(12, 11),
            font=("Segoe UI", 9),
            width=SIDE_TAB_WIDTH_CHARS,
            anchor="center",
        )
        style.map(
            "Side.TNotebook.Tab",
            background=[("selected", p["tab_active"]), ("active", p["panel_alt"])],
            foreground=[("selected", p["text"]), ("active", p["text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=p["scroll"],
            troughcolor=p["scroll_trough"],
            bordercolor=p["scroll_trough"],
            arrowcolor=p["subtle"],
            darkcolor=p["scroll"],
            lightcolor=p["panel_alt"],
            relief="flat",
            width=13,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", p["panel_alt"]), ("pressed", p["grid"])],
            arrowcolor=[("active", p["text"])],
        )
        style.configure("TEntry", fieldbackground="#f8fafc")
        style.configure("TCombobox", fieldbackground="#f8fafc")
        style.configure("Horizontal.TProgressbar", troughcolor=p["panel_alt"], background=p["accent"], bordercolor=p["bg"])

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(14, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="VirtualBench Bode Workbench", style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.device_status_var, style="HeaderStatus.TLabel").grid(row=0, column=1, sticky="e", padx=10)

        body = ttk.Frame(self, padding=10, style="Body.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        controls = ttk.Frame(body, padding=(0, 0, 10, 0), width=470, style="Panel.TFrame")
        controls.grid(row=0, column=0, sticky="ns")
        controls.grid_propagate(False)
        controls.columnconfigure(0, weight=1)
        controls.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(controls, style="Side.TNotebook")
        self.controls_notebook = notebook
        notebook.grid(row=0, column=0, sticky="nsew")
        self.tabs["start"] = self._build_start_tab(notebook)
        self.tabs["basic"] = self._build_basic_tab(notebook)
        self.tabs["advanced"] = self._build_advanced_tab(notebook)
        self.tabs["graph"] = self._build_graph_data_tab(notebook)
        self.tabs["power"] = self._build_power_tab(notebook)
        self.tabs["info"] = self._build_info_tab(notebook)
        self.tabs["preferences"] = self._build_preferences_tab(notebook)
        notebook.add(self.tabs["start"], text="Inicio")
        notebook.add(self.tabs["basic"], text="Configuración Básica")
        notebook.add(self.tabs["advanced"], text="Configuración Avanzada")
        notebook.add(self.tabs["graph"], text="Datos de las gráficas")
        notebook.add(self.tabs["power"], text="Fuente DC")
        notebook.add(self.tabs["info"], text="Información")
        notebook.add(self.tabs["preferences"], text="Preferencias")
        self._apply_ui_mode()

        self.ps_pos_voltage_var.trace_add("write", self._update_power_gauges)
        self.ps_neg_voltage_var.trace_add("write", self._update_power_gauges)
        self._update_power_gauges()

        main = ttk.Frame(body, style="Body.TFrame")
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=4)
        main.rowconfigure(2, weight=2)
        main.rowconfigure(3, weight=2)

        action_bar = ttk.Frame(main, padding=(0, 0, 0, 8), style="Body.TFrame")
        action_bar.grid(row=0, column=0, sticky="ew")
        action_bar.columnconfigure(7, weight=1)
        self.start_button = ttk.Button(action_bar, text="Iniciar barrido", style="Run.TButton", command=self._start_sweep, state="disabled")
        self.start_button.grid(row=0, column=0, padx=(0, 6))
        self.stop_button = ttk.Button(action_bar, text="Detener", command=self._request_stop, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 6))
        ttk.Button(action_bar, text="Exportar seleccionado", command=self._export_selected).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(action_bar, text="Guardar CSV", command=self._save_csv).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(action_bar, text="Reconectar", command=self._detect_device).grid(row=0, column=4, padx=(0, 6))
        ttk.Label(action_bar, textvariable=self.last_point_var, justify="right", style="Hint.TLabel").grid(row=0, column=7, sticky="e")
        self.progress_bar = ttk.Progressbar(action_bar, mode="determinate", maximum=100)
        self.progress_bar.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        ttk.Label(action_bar, textvariable=self.progress_var, style="Hint.TLabel").grid(row=1, column=7, sticky="e", pady=(8, 0))

        self.figure = Figure(figsize=(7.8, 4.8), dpi=125)
        self.figure.patch.set_facecolor(self.palette["bg"])
        self.gain_ax = self.figure.add_subplot(211)
        self.phase_ax = self.figure.add_subplot(212, sharex=self.gain_ax)
        self.canvas = FigureCanvasTkAgg(self.figure, master=main)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.time_trace = TimeTracePanel(main, self.palette)
        self.time_trace.grid(row=2, column=0, sticky="nsew")

        columns = ("freq", "gain_v", "gain_db", "phase", "ref", "resp")
        table_frame = ttk.Frame(main, style="Body.TFrame")
        table_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings")
        headings = {
            "freq": "Frecuencia (Hz)",
            "gain_v": "Ganancia (V/V)",
            "gain_db": "Ganancia (dB)",
            "phase": "Fase (°)",
            "ref": "Referencia (V)",
            "resp": "Respuesta (V)",
        }
        for col, label in headings.items():
            self.table.heading(col, text=label, anchor="center")
            self.table.column(col, anchor="center", width=130)
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)

        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 5), style="Dark.TLabel")
        status.grid(row=2, column=0, sticky="ew")
        self._register_live_validation()
        self._update_live_validation()

    def _menu_frame(self, notebook: ttk.Notebook) -> MenuFrame:
        tab = MenuFrame(notebook)
        tab.apply_palette(self.palette)
        self._menu_frames.append(tab)
        return tab

    def _build_start_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        row = 0
        row = self._section(parent, "Inicio rápido", row)
        ttk.Label(parent, text="Preset", style="Dark.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        preset_combo = ttk.Combobox(parent, textvariable=self.preset_var, values=tuple(PRESETS.keys()), state="readonly", width=14)
        preset_combo.grid(row=row, column=1, sticky="ew", pady=4)
        preset_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_preset_hint())
        ToolTip(preset_combo, "Selecciona una configuración inicial segura.")
        row += 1
        ttk.Label(parent, textvariable=self.preset_hint_var, wraplength=340, justify="left", style="Hint.TLabel").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 8),
        )
        row += 1
        ttk.Button(parent, text="Aplicar preset", command=self._apply_preset).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        row += 1
        row = self._entry(parent, "Inicio (Hz)", self.start_var, row, "Frecuencia inicial del barrido.")
        row = self._entry(parent, "Final (Hz)", self.stop_var, row, "Frecuencia final del barrido.")
        row = self._entry(parent, "Amplitud (Vpp)", self.amplitude_var, row, "Empieza con 1 Vpp si no conoces el circuito.")
        row = self._entry(parent, "Offset (V)", self.offset_var, row, "Usa 0 V para comenzar.")
        row = self._section(parent, "Guía de medición", row, pady=(14, 6))
        self.step_labels = []
        for variable in (
            self.connection_step_var,
            self.signal_step_var,
            self.config_step_var,
            self.measure_step_var,
            self.export_step_var,
        ):
            label = ttk.Label(parent, textvariable=variable, wraplength=330, justify="left", style="Hint.TLabel")
            label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
            self.step_labels.append(label)
            row += 1
        ttk.Button(parent, text="Ver conexión", command=self._show_info_tab).grid(row=row, column=0, sticky="ew", pady=(10, 0), padx=(0, 4))
        ttk.Button(parent, text="Iniciar barrido", command=self._start_sweep).grid(row=row, column=1, sticky="ew", pady=(10, 0), padx=(4, 0))
        row += 1
        row = self._section(parent, "Resumen antes de iniciar", row, pady=(16, 6))
        ttk.Label(parent, textvariable=self.summary_var, wraplength=340, justify="left", style="Dark.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="ew"
        )
        row += 1
        self.validation_label = ttk.Label(parent, textvariable=self.validation_var, wraplength=340, justify="left", style="Warn.TLabel")
        self.validation_label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        return tab

    def _build_basic_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        row = 0
        row = self._section(parent, "Instrumento", row)
        row = self._entry(parent, "Recurso", self.resource_var, row, "Nombre NI VirtualBench detectado o escrito manualmente.")
        row = self._combo(parent, "Canal referencia", self.reference_var, CHANNELS, row, "Canal usado como señal de entrada.")
        row = self._combo(parent, "Canal respuesta", self.response_var, CHANNELS, row, "Canal conectado a la salida del circuito bajo prueba.")

        row = self._section(parent, "Barrido", row, pady=(14, 6))
        row = self._entry(parent, "Frecuencia inicial (Hz)", self.start_var, row, "Default 100 Hz. Debe ser menor que la frecuencia final.")
        row = self._entry(parent, "Frecuencia final (Hz)", self.stop_var, row, "Default 1 MHz. Use un valor compatible con el circuito y el MSO.")
        row = self._entry(parent, "Puntos de barrido", self.points_var, row, "Se conserva para compatibilidad con la lógica actual.")
        row = self._entry(parent, "Número de periodos", self.cycles_var, row, "Periodos capturados por frecuencia. Default 30.")
        row = self._combo(parent, "Tipo de barrido", self.sweep_mode_var, SWEEP_MODES, row, "Por décadas usa escala logaritmica; Lineal usa pasos uniformes.")
        row = self._entry(parent, "Promedios", self.averages_var, row, "Adquisiciones promediadas por frecuencia. Default 1.")

        row = self._section(parent, "Señal de entrada", row, pady=(14, 6))
        row = self._entry(parent, "Amplitud entrada (Vpp)", self.amplitude_var, row, "Default 1 Vpp. Mantenga margen frente al offset.")
        row = self._entry(parent, "Voltaje offset (V)", self.offset_var, row, "Default 0 V. La suma offset +/- amplitud/2 debe quedar en rango seguro.")

        row = self._section(parent, "Adquisición", row, pady=(14, 6))
        row = self._entry(parent, "Espera entre puntos (s)", self.settle_var, row, "Tiempo para estabilizar el circuito antes de leer.")
        row = self._entry(parent, "Muestras x frecuencia", self.sample_mult_var, row, "Multiplicador de frecuencia de muestreo objetivo.")
        row = self._entry(parent, "Paro por ganancia (dB)", self.min_gain_var, row, "Se conserva el paro por atenuación actual.")
        ttk.Checkbutton(
            parent,
            text="Detener por atenuación",
            variable=self.stop_attenuation_var,
            style="Dark.TCheckbutton",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 0))
        return tab

    def _build_advanced_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(notebook, style="Panel.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        nested = ttk.Notebook(frame)
        nested.grid(row=0, column=0, sticky="nsew")
        nested.add(self._build_channel_tab(nested, "ch1", "mso/1"), text="Canal 1")
        nested.add(self._build_channel_tab(nested, "ch2", "mso/2"), text="Canal 2")
        return frame

    def _build_channel_tab(self, notebook: ttk.Notebook, key: str, channel: str) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        vars_for_channel = self.channel_vars[key]
        row = 0
        row = self._section(parent, f"{channel.upper()} - ajuste vertical y trigger", row)
        row = self._combo(parent, "Acoplamiento vertical", vars_for_channel["coupling"], COUPLINGS, row, "DC conserva offset; AC bloquea componente continua.")
        row = self._entry(
            parent,
            "Histeresis trigger (V)",
            vars_for_channel["trigger_hysteresis"],
            row,
            "Default 0.01 V. Rango validado: 0 a 5 V.",
        )
        row = self._combo(
            parent,
            "Referencia del trigger",
            vars_for_channel["trigger_reference"],
            TRIGGER_REFERENCES,
            row,
            "Use mso/1 o mso/2. Browse permite escribir otro nombre compatible; refresh vuelve al canal del tab.",
            command=lambda _event, k=key, ch=channel: self._handle_trigger_reference_choice(k, ch),
        )
        row = self._combo(parent, "Pendiente del trigger", vars_for_channel["trigger_slope"], TRIGGER_SLOPES, row, "Rising, Falling o Either.")
        row = self._entry(
            parent,
            "Nivel del trigger (V)",
            vars_for_channel["trigger_level"],
            row,
            "Default 0 V. Rango validado: -10 V a +10 V.",
        )
        row = self._combo(parent, "Atenuación de la punta", vars_for_channel["probe_attenuation"], PROBE_ATTENUATIONS, row, "Seleccione 1x o 10x segun la punta fisica.")

        ttk.Label(
            parent,
            text=(
                "Recomendación: use DC y trigger Rising a 0 V para senoidales centradas. "
                "Si la señal tiene mucho offset, ajuste el nivel hacia el cruce estable de la onda."
            ),
            wraplength=320,
            justify="left",
            style="Hint.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        return tab

    def _build_graph_data_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        row = 0
        row = self._section(parent, "Exportación", row)
        ttk.Checkbutton(parent, text="Exportar CSV", variable=self.export_csv_var, style="Dark.TCheckbutton").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1
        ttk.Checkbutton(parent, text="Exportar SVG", variable=self.export_svg_var, style="Dark.TCheckbutton").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1
        ttk.Button(parent, text="Exportar seleccionado", command=self._export_selected).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        row += 1

        row = self._section(parent, "Búsqueda de valores", row, pady=(16, 6))
        row = self._entry(parent, "Frecuencia a (dB)", self.target_gain_var, row, "Default -3 dB. El programa marca la referencia visual en la grafica.")
        row = self._entry(parent, "Tolerancia Magnitud (dB)", self.mag_tolerance_var, row, "Default 1 dB.")
        row = self._entry(parent, "Tolerancia Fase (°)", self.phase_tolerance_var, row, "Default 5°.")
        help_button = ttk.Button(parent, text="?", width=3, command=self._show_graph_help)
        help_button.grid(row=row, column=0, sticky="w", pady=(10, 0))
        ttk.Label(parent, text="Ayuda contextual", style="Hint.TLabel").grid(row=row, column=1, sticky="w", pady=(10, 0))
        ToolTip(help_button, "Explica como se usan Frecuencia a, Tolerancia Magnitud y Tolerancia Fase.")
        return tab

    def _build_power_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        row = 0
        row = self._section(parent, "Fuente de poder DC", row)
        gauge_frame = ttk.Frame(parent, style="Panel.TFrame")
        gauge_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        gauge_frame.columnconfigure((0, 1), weight=1)
        self.pos_gauge = VoltageGauge(gauge_frame, "+25V", 25.0, self.palette["accent"])
        self.pos_gauge.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.neg_gauge = VoltageGauge(gauge_frame, "-25V", 25.0, self.palette["accent_2"])
        self.neg_gauge.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        row += 1
        ttk.Checkbutton(parent, text="Habilitar salida", variable=self.ps_output_enabled_var, style="Dark.TCheckbutton").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1
        row = self._entry(parent, "+25V set (V)", self.ps_pos_voltage_var, row, "Rango seguro validado: 0 a 25 V.")
        row = self._entry(parent, "-25V set (V)", self.ps_neg_voltage_var, row, "Rango seguro validado: -25 a 0 V.")
        row = self._entry(parent, "Corriente límite (A)", self.ps_current_var, row, "Rango validado: 0.001 a 1 A.")
        ttk.Checkbutton(parent, text="+6V habilitado", variable=self.ps_six_enabled_var, style="Dark.TCheckbutton").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1
        ttk.Checkbutton(parent, text="Confirmar tensiones/corrientes altas", variable=self.ps_high_power_guard_var, style="Dark.TCheckbutton").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4
        )
        row += 1
        ttk.Button(parent, text="Aplicar fuente", command=self._apply_power_supply).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        row += 1
        ttk.Button(parent, text="Apagar fuentes", command=self._disable_power_supply).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        row += 1
        ttk.Label(
            parent,
            text="La salida queda deshabilitada por defecto. El límite de corriente se aplica antes de activar los rieles.",
            wraplength=320,
            justify="left",
            style="Hint.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        return tab

    def _build_info_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        row = 0
        row = self._section(parent, "Conexión recomendada", row)
        image_path = Path(__file__).resolve().parents[2] / "info.png"
        if image_path.exists() and Image is not None and ImageTk is not None:
            with Image.open(image_path) as image:
                self._info_image_original = image.copy()
            self._info_image_label = tk.Label(parent, background=self.palette["bg"], borderwidth=0)
            self._info_image_label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            self._info_image_label.bind("<Configure>", self._resize_info_image)
        elif image_path.exists():
            photo = tk.PhotoImage(file=str(image_path))
            self._info_image_photo = photo
            tk.Label(parent, image=photo, background=self.palette["bg"], borderwidth=0).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)
            )
        else:
            ttk.Label(parent, text="No se encontró info.png en la raíz del proyecto.", style="Hint.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)
            )
        row += 1
        info = (
            "1. Conecte la salida del Generador de Funciones al CH1/MSO1 para medir la señal de entrada.\n"
            "2. Conecte la misma señal al circuito bajo prueba.\n"
            "3. Conecte la salida del circuito al CH2/MSO2 para medir la respuesta.\n"
            "4. Mantenga tierra común entre generador, circuito y osciloscopio.\n"
            "5. Verifique que las puntas esten configuradas en la misma atenuación fisica y en software.\n"
            "6. Empiece con 1 Vpp y offset 0 V; suba amplitud solo si la señal queda limpia y dentro de rango.\n"
            "7. Para mediciones estables, use cables cortos, evite la saturación y permita tiempo de asentamiento."
        )
        ttk.Label(parent, text=info, wraplength=330, justify="left", style="Dark.TLabel").grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1
        row = self._section(parent, "Qué mide cada canal", row, pady=(16, 6))
        channel_info = (
            "CH1/MSO1 normalmente mide la referencia o entrada del circuito. "
            "CH2/MSO2 mide la respuesta o salida. La ganancia se calcula como respuesta/referencia y la fase como diferencia relativa."
        )
        ttk.Label(parent, text=channel_info, wraplength=330, justify="left", style="Dark.TLabel").grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1
        row = self._section(parent, "Software y hardware", row, pady=(16, 6))
        metadata = (
            f"Versión del software: {_software_version()}\n"
            "Autor/desarrollador: vbarrido-py, réplica Python local de VBarrido/LabVIEW.\n"
            "Compatibilidad de hardware: NI VirtualBench con FGEN, MSO y fuente DC mediante pyvirtualbench.\n"
            "Compatibilidad MSO: conserva canales mso/1 y mso/2, trigger configurable y lectura analogica dual."
        )
        ttk.Label(parent, text=metadata, wraplength=330, justify="left", style="Dark.TLabel").grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1
        row = self._section(parent, "Funcionamiento del barrido", row, pady=(16, 6))
        sweep_info = (
            "El FGEN genera una senoidal por cada frecuencia configurada. El MSO captura ambas señales, "
            "el programa estima amplitud y fase del tono principal, y con esos datos construye la respuesta en frecuencia."
        )
        ttk.Label(parent, text=sweep_info, wraplength=330, justify="left", style="Dark.TLabel").grid(row=row, column=0, columnspan=2, sticky="ew")
        return tab

    def _build_preferences_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        tab = self._menu_frame(notebook)
        parent = tab.content
        row = 0
        row = self._section(parent, "Interfaz", row)
        ttk.Label(parent, text="Modo", style="Dark.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        mode_combo = ttk.Combobox(parent, textvariable=self.ui_mode_var, values=("Básico", "Experto"), state="readonly", width=14)
        mode_combo.grid(row=row, column=1, sticky="ew", pady=4)
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_ui_mode())
        ToolTip(mode_combo, "Básico simplifica la navegación; Experto muestra además los ajustes avanzados y de gráficas.")
        row += 1

        ttk.Label(parent, text="Tema", style="Dark.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        theme_combo = ttk.Combobox(parent, textvariable=self.theme_var, values=("Claro", "Oscuro"), state="readonly", width=14)
        theme_combo.grid(row=row, column=1, sticky="ew", pady=4)
        theme_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_theme())
        ToolTip(theme_combo, "El tema claro es el valor predeterminado de inicio.")
        row += 1

        row = self._section(parent, "Valores por defecto", row, pady=(16, 6))
        ttk.Label(
            parent,
            text="Restaura la configuración de medición, las opciones de exportación, las fuentes DC y las preferencias de interfaz.",
            wraplength=330,
            justify="left",
            style="Hint.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="ew")
        row += 1
        reset_button = ttk.Button(parent, text="Restaurar valores por defecto", command=self._reset_defaults)
        reset_button.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ToolTip(reset_button, "Devuelve la aplicación al estado inicial: modo experto y tema claro incluidos.")
        return tab

    def _resize_info_image(self, event: tk.Event[tk.Misc]) -> None:
        if self._info_image_original is None or self._info_image_label is None or Image is None or ImageTk is None:
            return
        original = self._info_image_original
        width = max(event.width, 220)
        original_width, original_height = original.size
        target_width = min(width, original_width)
        if abs(target_width - self._info_image_width) < 16:
            return
        self._info_image_width = target_width
        target_height = max(int(original_height * target_width / original_width), 120)
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        resized = original.resize((target_width, target_height), resampling)
        self._info_image_photo = ImageTk.PhotoImage(resized)
        self._info_image_label.configure(image=self._info_image_photo)

    def _draw_connection_diagram(self, event: tk.Event[tk.Misc]) -> None:
        canvas = event.widget
        if not isinstance(canvas, tk.Canvas):
            return
        canvas.delete("all")
        width = max(event.width, 320)
        box_fill = "#172033"
        box_outline = "#334155"
        text_fill = "#e5e7eb"
        line_fill = "#38bdf8"
        left = 16
        mid = width // 2 - 54
        right = width - 118
        canvas.create_rectangle(left, 20, left + 92, 72, fill=box_fill, outline=box_outline)
        canvas.create_text(left + 46, 46, text="FGEN", fill=text_fill, font=("Segoe UI", 10, "bold"))
        canvas.create_rectangle(mid, 20, mid + 108, 72, fill=box_fill, outline=box_outline)
        canvas.create_text(mid + 54, 46, text="Circuito", fill=text_fill, font=("Segoe UI", 10, "bold"))
        canvas.create_rectangle(right, 20, right + 102, 124, fill=box_fill, outline=box_outline)
        canvas.create_text(right + 51, 46, text="MSO CH1", fill=text_fill, font=("Segoe UI", 9, "bold"))
        canvas.create_text(right + 51, 94, text="MSO CH2", fill=text_fill, font=("Segoe UI", 9, "bold"))
        canvas.create_line(left + 92, 46, mid, 46, fill=line_fill, width=2, arrow=tk.LAST)
        canvas.create_line(left + 92, 46, right, 46, fill="#a3e635", width=2, arrow=tk.LAST)
        canvas.create_line(mid + 108, 46, right, 94, fill="#f97316", width=2, arrow=tk.LAST)
        canvas.create_text(width // 2, 136, text="Tierra común entre todos los equipos", fill="#94a3b8", font=("Segoe UI", 9))

    def _section(self, parent: ttk.Frame, text: str, row: int, pady: tuple[int, int] = (0, 6)) -> int:
        ttk.Label(parent, text=text, style="Section.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=pady)
        return row + 1

    def _entry(self, parent: ttk.Frame, label: str, variable: tk.Variable, row: int, tooltip: str | None = None) -> int:
        ttk.Label(parent, text=label, style="Dark.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=16)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        if tooltip:
            ToolTip(entry, tooltip)
        return row + 1

    def _combo(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.Variable,
        values: tuple[str, ...],
        row: int,
        tooltip: str | None = None,
        command: object | None = None,
    ) -> int:
        ttk.Label(parent, text=label, style="Dark.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=14)
        combo.grid(row=row, column=1, sticky="ew", pady=4)
        if command is not None:
            combo.bind("<<ComboboxSelected>>", command)
        if tooltip:
            ToolTip(combo, tooltip)
        return row + 1

    def _handle_trigger_reference_choice(self, key: str, channel: str) -> None:
        var = self.channel_vars[key]["trigger_reference"]
        choice = str(var.get())
        if choice == "refresh":
            var.set(channel)
            self.status_var.set("Referencia del trigger actualizada.")
        elif choice == "browse...":
            value = simpledialog.askstring(
                "Referencia del trigger",
                "Escriba una referencia valida del MSO (por ejemplo mso/1 o mso/2):",
                parent=self,
                initialvalue=channel,
            )
            var.set(value.strip() if value else channel)

    def _show_info_tab(self) -> None:
        if self.controls_notebook is not None and "info" in self.tabs:
            self.controls_notebook.tab(self.tabs["info"], state="normal")
            self.controls_notebook.select(self.tabs["info"])

    def _apply_preset(self) -> None:
        preset = PRESETS.get(self.preset_var.get(), {})
        self._update_preset_hint()
        if not preset:
            self.status_var.set("Preset personalizado: se conservan los valores actuales.")
            return
        self.start_var.set(preset["start"])
        self.stop_var.set(preset["stop"])
        self.points_var.set(preset["points"])
        self.cycles_var.set(preset["cycles"])
        self.averages_var.set(preset["averages"])
        self.sweep_mode_var.set(preset["sweep_mode"])
        self.settle_var.set(preset["settle"])
        self.status_var.set(f"Preset aplicado: {self.preset_var.get()}")

    def _update_preset_hint(self) -> None:
        self.preset_hint_var.set(PRESET_HINTS.get(self.preset_var.get(), PRESET_HINTS["Personalizado"]))

    def _apply_ui_mode(self) -> None:
        if self.controls_notebook is None:
            return
        expert_tabs = ("advanced", "graph")
        is_expert = self.ui_mode_var.get() == "Experto"
        for name in expert_tabs:
            if name in self.tabs:
                self.controls_notebook.tab(self.tabs[name], state="normal" if is_expert else "hidden")
        if not is_expert and self.controls_notebook.select() in [str(self.tabs[name]) for name in expert_tabs if name in self.tabs]:
            self.controls_notebook.select(self.tabs["start"])
        self.status_var.set("Modo experto activado." if is_expert else "Modo básico activado.")

    def _apply_theme(self) -> None:
        self.palette = THEMES.get(self.theme_var.get(), THEMES["Claro"])
        self._build_style()
        for frame in self._menu_frames:
            frame.apply_palette(self.palette)
        if self.time_trace is not None:
            self.time_trace.apply_palette(self.palette)
            if self._last_trace_payload is not None:
                self.time_trace.update_trace(self._last_trace_payload)
        if self._info_image_label is not None:
            self._info_image_label.configure(background=self.palette["bg"])
            self._info_image_width = 0
        if hasattr(self, "pos_gauge"):
            self.pos_gauge.apply_palette(self.palette, self.palette["accent"])
            try:
                self.pos_gauge.draw(float(self.ps_pos_voltage_var.get() or 0))
            except ValueError:
                self.pos_gauge.draw(0.0)
        if hasattr(self, "neg_gauge"):
            self.neg_gauge.apply_palette(self.palette, self.palette["accent_2"])
            try:
                self.neg_gauge.draw(float(self.ps_neg_voltage_var.get() or 0))
            except ValueError:
                self.neg_gauge.draw(0.0)
        self.figure.patch.set_facecolor(self.palette["bg"])
        self._plot_layout_ready = False
        self._redraw_plot()
        self.status_var.set(f"Tema aplicado: {self.theme_var.get()}")

    def _register_live_validation(self) -> None:
        variables: list[tk.Variable] = [
            self.resource_var,
            self.reference_var,
            self.response_var,
            self.start_var,
            self.stop_var,
            self.points_var,
            self.cycles_var,
            self.sweep_mode_var,
            self.averages_var,
            self.amplitude_var,
            self.offset_var,
            self.settle_var,
            self.sample_mult_var,
            self.min_gain_var,
            self.target_gain_var,
            self.mag_tolerance_var,
            self.phase_tolerance_var,
        ]
        for channel in self.channel_vars.values():
            variables.extend(channel.values())
        for variable in variables:
            variable.trace_add("write", lambda *_args: self._update_live_validation())

    def _number_or_error(self, variable: tk.StringVar, label: str, errors: list[str]) -> float | None:
        try:
            return float(variable.get())
        except ValueError:
            errors.append(f"{label} debe ser un número.")
            return None

    def _int_or_error(self, variable: tk.StringVar, label: str, errors: list[str]) -> int | None:
        try:
            return int(variable.get())
        except ValueError:
            errors.append(f"{label} debe ser entero.")
            return None

    def _soft_validate(self) -> list[str]:
        errors: list[str] = []
        start = self._number_or_error(self.start_var, "Frecuencia inicial", errors)
        stop = self._number_or_error(self.stop_var, "Frecuencia final", errors)
        points = self._int_or_error(self.points_var, "Puntos", errors)
        cycles = self._int_or_error(self.cycles_var, "Número de periodos", errors)
        averages = self._int_or_error(self.averages_var, "Promedios", errors)
        amplitude = self._number_or_error(self.amplitude_var, "Amplitud", errors)
        offset = self._number_or_error(self.offset_var, "Offset", errors)
        settle = self._number_or_error(self.settle_var, "Espera", errors)
        sample_multiplier = self._number_or_error(self.sample_mult_var, "Muestras x frecuencia", errors)

        if start is not None and not 0.1 <= start <= 10_000_000:
            errors.append("Frecuencia inicial fuera del rango 0.1 Hz a 10 MHz.")
        if stop is not None and not 0.1 <= stop <= 10_000_000:
            errors.append("Frecuencia final fuera del rango 0.1 Hz a 10 MHz.")
        if start is not None and stop is not None and stop <= start:
            errors.append("La frecuencia final debe ser mayor que la inicial.")
        if points is not None and not 2 <= points <= 5000:
            errors.append("Puntos debe estar entre 2 y 5000.")
        if cycles is not None and not 1 <= cycles <= 1000:
            errors.append("Número de periodos debe estar entre 1 y 1000.")
        if averages is not None and not 1 <= averages <= 128:
            errors.append("Promedios debe estar entre 1 y 128.")
        if amplitude is not None and not 0.001 <= amplitude <= 10:
            errors.append("Amplitud debe estar entre 0.001 y 10 Vpp.")
        if offset is not None and not -10 <= offset <= 10:
            errors.append("Offset debe estar entre -10 y 10 V.")
        if amplitude is not None and offset is not None and abs(offset) + amplitude / 2 > 10:
            errors.append("Offset + amplitud/2 excede +/-10 V.")
        if settle is not None and not 0 <= settle <= 30:
            errors.append("Espera debe estar entre 0 y 30 s.")
        if sample_multiplier is not None and not 2 <= sample_multiplier <= 1000:
            errors.append("Muestras x frecuencia debe estar entre 2 y 1000.")
        if self.reference_var.get() == self.response_var.get():
            errors.append("Referencia y respuesta deben usar canales distintos.")
        return errors

    def _sweep_summary(self) -> str:
        return (
            f"Se medirá de {self.start_var.get()} Hz a {self.stop_var.get()} Hz, "
            f"{self.points_var.get()} puntos, {self.cycles_var.get()} periodos, "
            f"{self.averages_var.get()} promedio(s), {self.amplitude_var.get()} Vpp, "
            f"offset {self.offset_var.get()} V. Referencia: {self.reference_var.get()}, "
            f"respuesta: {self.response_var.get()}."
        )

    def _update_live_validation(self) -> None:
        errors = self._soft_validate()
        self._last_validation_errors = errors
        self.summary_var.set(self._sweep_summary())
        if errors:
            self.validation_var.set("Revisar: " + errors[0])
            if hasattr(self, "validation_label"):
                self.validation_label.configure(style="Error.TLabel")
        elif not self.resource_var.get().strip():
            self.validation_var.set("Configuración lista. Falta detectar o escribir el recurso VirtualBench.")
            if hasattr(self, "validation_label"):
                self.validation_label.configure(style="Warn.TLabel")
        else:
            self.validation_var.set("Configuración lista para iniciar.")
            if hasattr(self, "validation_label"):
                self.validation_label.configure(style="Good.TLabel")
        self._update_steps()
        self._refresh_start_state()

    def _update_steps(self) -> None:
        connected = bool(self.resource_var.get().strip())
        valid = not self._last_validation_errors
        has_data = bool(self._points)
        self.connection_step_var.set("1. Conexión: instrumento listo" if connected else "1. Conexión: conecte VirtualBench o presione Reconectar")
        self.signal_step_var.set(f"2. Señal: {self.amplitude_var.get()} Vpp, offset {self.offset_var.get()} V, tierra común")
        self.config_step_var.set("3. Configuración: sin errores" if valid else "3. Configuración: revise el aviso rojo")
        self.measure_step_var.set("4. Medición: puede iniciar" if connected and valid else "4. Medición: esperando configuración válida")
        self.export_step_var.set("5. Exportación: datos disponibles" if has_data else "5. Exportación: disponible al terminar")

    def _refresh_start_state(self) -> None:
        if not hasattr(self, "start_button"):
            return
        running = self._worker is not None and self._worker.is_alive()
        ready = bool(self.resource_var.get().strip()) and not self._last_validation_errors and not running
        self.start_button.configure(state="normal" if ready else "disabled")

    def _reset_defaults(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showwarning("Barrido en progreso", "Detenga el barrido antes de restablecer la configuración.")
            return
        if not messagebox.askyesno(
            "Restaurar valores por defecto",
            "Se reemplazaran todos los campos configurables por sus valores por defecto. ¿Desea continuar?",
        ):
            return
        self.response_var.set(self.defaults.ch_response)
        self.reference_var.set(self.defaults.ch_reference)
        self.preset_var.set("Personalizado")
        self._update_preset_hint()
        self.start_var.set(f"{self.defaults.start_hz:g}")
        self.stop_var.set(f"{self.defaults.stop_hz:g}")
        self.points_var.set(f"{self.defaults.points:d}")
        self.cycles_var.set(f"{self.defaults.cycles:d}")
        self.sweep_mode_var.set(self.defaults.sweep_mode)
        self.averages_var.set(f"{self.defaults.averages:d}")
        self.amplitude_var.set(f"{self.defaults.amplitude_v:g}")
        self.offset_var.set(f"{self.defaults.dc_offset_v:g}")
        self.settle_var.set(f"{self.defaults.settle_s:g}")
        self.min_gain_var.set(f"{self.defaults.min_gain_db:g}")
        self.sample_mult_var.set(f"{self.defaults.sample_rate_multiplier:g}")
        self.export_csv_var.set(True)
        self.export_svg_var.set(False)
        self.target_gain_var.set("-3")
        self.mag_tolerance_var.set("1")
        self.phase_tolerance_var.set("5")
        self.ps_output_enabled_var.set(False)
        self.ps_pos_voltage_var.set("10.0")
        self.ps_neg_voltage_var.set("-10.0")
        self.ps_current_var.set("0.1")
        self.ps_six_enabled_var.set(False)
        self.ps_high_power_guard_var.set(True)
        self.stop_attenuation_var.set(False)
        self.theme_var.set("Claro")
        self.ui_mode_var.set("Experto")
        self._set_channel_variables("ch1", self.defaults.ch1)
        self._set_channel_variables("ch2", self.defaults.ch2)
        if self.progress_bar is not None:
            self.progress_bar.configure(value=0)
        self.progress_var.set("Progreso: 0%")
        self._apply_theme()
        self._apply_ui_mode()
        self._redraw_plot()
        self._update_live_validation()
        self.status_var.set("Configuración restablecida.")

    def _set_channel_variables(self, key: str, config: ChannelConfig) -> None:
        vars_for_channel = self.channel_vars[key]
        vars_for_channel["coupling"].set(config.coupling)
        vars_for_channel["trigger_hysteresis"].set(f"{config.trigger_hysteresis_v:g}")
        vars_for_channel["trigger_reference"].set(config.trigger_reference)
        vars_for_channel["trigger_slope"].set(config.trigger_slope)
        vars_for_channel["trigger_level"].set(f"{config.trigger_level_v:g}")
        vars_for_channel["probe_attenuation"].set(config.probe_attenuation)

    def _parse_float(self, variable: tk.StringVar, label: str) -> float:
        try:
            return float(variable.get())
        except ValueError as exc:
            raise ValueError(f"{label} debe ser un numero valido.") from exc

    def _parse_int(self, variable: tk.StringVar, label: str) -> int:
        try:
            return int(variable.get())
        except ValueError as exc:
            raise ValueError(f"{label} debe ser un entero valido.") from exc

    def _validate_range(self, value: float, label: str, minimum: float, maximum: float, suggestion: str = "") -> None:
        if not minimum <= value <= maximum:
            detail = f"{label} debe estar entre {minimum:g} y {maximum:g}."
            if suggestion:
                detail += f" Sugerencia: {suggestion}"
            raise ValueError(detail)

    def _channel_config_from_ui(self, key: str, channel: str) -> ChannelConfig:
        vars_for_channel = self.channel_vars[key]
        coupling = str(vars_for_channel["coupling"].get())
        trigger_reference = str(vars_for_channel["trigger_reference"].get())
        trigger_slope = str(vars_for_channel["trigger_slope"].get())
        probe_attenuation = str(vars_for_channel["probe_attenuation"].get())
        hysteresis = self._parse_float(vars_for_channel["trigger_hysteresis"], f"Histeresis trigger {channel}")  # type: ignore[arg-type]
        level = self._parse_float(vars_for_channel["trigger_level"], f"Nivel trigger {channel}")  # type: ignore[arg-type]

        if coupling not in COUPLINGS:
            raise ValueError(f"Acoplamiento de {channel} invalido. Use AC o DC.")
        if trigger_reference not in CHANNELS:
            vars_for_channel["trigger_reference"].set(channel)
            raise ValueError(f"Referencia del trigger de {channel} invalida. Se sugiere {channel}.")
        if trigger_slope not in TRIGGER_SLOPES:
            raise ValueError(f"Pendiente de trigger de {channel} invalida.")
        if probe_attenuation not in PROBE_ATTENUATIONS:
            raise ValueError(f"Atenuación de punta de {channel} invalida. Use 1x o 10x.")
        if not 0.0 <= hysteresis <= 5.0:
            suggested = min(max(hysteresis, 0.0), 5.0)
            vars_for_channel["trigger_hysteresis"].set(f"{suggested:g}")
            raise ValueError(f"Histeresis de {channel} fuera de rango. Se ajusto visualmente a {suggested:g} V.")
        if not -10.0 <= level <= 10.0:
            suggested = min(max(level, -10.0), 10.0)
            vars_for_channel["trigger_level"].set(f"{suggested:g}")
            raise ValueError(f"Nivel de trigger de {channel} fuera de rango. Se ajusto visualmente a {suggested:g} V.")

        return ChannelConfig(
            channel=channel,
            coupling=coupling,
            trigger_hysteresis_v=hysteresis,
            trigger_reference=trigger_reference,
            trigger_slope=trigger_slope,
            trigger_level_v=level,
            probe_attenuation=probe_attenuation,
        )

    def _config_from_ui(self) -> SweepConfig:
        resource = self.resource_var.get().strip()
        if not resource:
            raise ValueError("No hay VirtualBench detectado.")
        start_hz = self._parse_float(self.start_var, "Frecuencia inicial")
        stop_hz = self._parse_float(self.stop_var, "Frecuencia final")
        points = self._parse_int(self.points_var, "Puntos de barrido")
        cycles = self._parse_int(self.cycles_var, "Número de periodos")
        averages = self._parse_int(self.averages_var, "Promedios")
        amplitude_v = self._parse_float(self.amplitude_var, "Amplitud de entrada")
        dc_offset_v = self._parse_float(self.offset_var, "Voltaje offset")
        settle_s = self._parse_float(self.settle_var, "Espera entre puntos")
        min_gain_db = self._parse_float(self.min_gain_var, "Paro por ganancia")
        sample_multiplier = self._parse_float(self.sample_mult_var, "Muestras x frecuencia")
        response_channel = self.response_var.get().strip() or "mso/1"
        reference_channel = self.reference_var.get().strip() or "mso/2"
        ch1 = self._channel_config_from_ui("ch1", "mso/1")
        ch2 = self._channel_config_from_ui("ch2", "mso/2")

        self._validate_range(start_hz, "Frecuencia inicial", 0.1, 10_000_000.0, "100 Hz es un punto seguro.")
        self._validate_range(stop_hz, "Frecuencia final", 0.1, 10_000_000.0, "1 MHz es el default solicitado.")
        if stop_hz <= start_hz:
            raise ValueError("La frecuencia final debe ser mayor que la inicial.")
        self._validate_range(points, "Puntos de barrido", 2, 5000, "80 puntos mantiene buen equilibrio entre tiempo y resolución.")
        self._validate_range(cycles, "Número de periodos", 1, 1000, "30 periodos suele estabilizar amplitud y fase.")
        self._validate_range(averages, "Promedios", 1, 128, "Use 1 para rapidez; suba si hay ruido.")
        self._validate_range(amplitude_v, "Amplitud de entrada", 0.001, 10.0, "1 Vpp es el valor recomendado de inicio.")
        self._validate_range(dc_offset_v, "Voltaje offset", -10.0, 10.0, "0 V evita polarizar accidentalmente el circuito.")
        if abs(dc_offset_v) + amplitude_v / 2.0 > 10.0:
            raise ValueError("Offset y amplitud exceden el margen seguro de +/-10 V. Reduzca amplitud u offset.")
        self._validate_range(settle_s, "Espera entre puntos", 0.0, 30.0)
        self._validate_range(min_gain_db, "Paro por ganancia", -200.0, 200.0)
        self._validate_range(sample_multiplier, "Muestras x frecuencia", 2.0, 1000.0, "10 es el default compatible.")
        if response_channel not in CHANNELS or reference_channel not in CHANNELS:
            raise ValueError("Los canales de referencia/respuesta deben ser mso/1 o mso/2.")
        if response_channel == reference_channel:
            raise ValueError("Referencia y respuesta deben usar canales distintos.")

        return SweepConfig(
            start_hz=start_hz,
            stop_hz=stop_hz,
            points=points,
            amplitude_v=amplitude_v,
            dc_offset_v=dc_offset_v,
            settle_s=settle_s,
            min_gain_db=min_gain_db,
            sample_rate_multiplier=sample_multiplier,
            cycles=cycles,
            averages=averages,
            sweep_mode=self.sweep_mode_var.get(),
            resource=resource,
            ch_response=response_channel,
            ch_reference=reference_channel,
            ch1=ch1,
            ch2=ch2,
        )

    def _validate_graph_config(self) -> None:
        target = self._parse_float(self.target_gain_var, "Frecuencia a")
        mag_tol = self._parse_float(self.mag_tolerance_var, "Tolerancia Magnitud")
        phase_tol = self._parse_float(self.phase_tolerance_var, "Tolerancia Fase")
        self._validate_range(target, "Frecuencia a", -200.0, 200.0, "-3 dB es el valor tipico de corte.")
        self._validate_range(mag_tol, "Tolerancia Magnitud", 0.001, 60.0, "1 dB suele ser suficiente.")
        self._validate_range(phase_tol, "Tolerancia Fase", 0.001, 180.0, "5° es el default recomendado.")

    def _detect_device(self) -> None:
        if self._detect_worker and self._detect_worker.is_alive():
            return
        self.start_button.configure(state="disabled")
        self.device_status_var.set("Detectando VirtualBench...")
        self.status_var.set("Buscando instrumento")
        self._detect_worker = threading.Thread(target=self._detect_worker_main, daemon=True)
        self._detect_worker.start()

    def _detect_worker_main(self) -> None:
        try:
            resource = discover_virtualbench_resource([self.resource_var.get(), "VB8012-30DF172"])
            self._queue.put(("device", resource))
        except Exception as exc:
            self._queue.put(("device_error", str(exc)))

    def _start_sweep(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        try:
            config = self._config_from_ui()
            self._validate_graph_config()
        except ValueError as exc:
            messagebox.showerror("Configuración inválida", str(exc))
            return
        summary = self._sweep_summary()
        if not messagebox.askyesno(
            "Confirmar barrido",
            f"{summary}\n\nVerifique la conexión y confirme que desea iniciar.",
        ):
            return

        self._points = []
        self._stop_requested = False
        self._last_trace_payload = None
        self._pending_trace_payload = None
        self._run_started_at = time.monotonic()
        self._run_total_points = config.points
        self.progress_var.set("Progreso: 0%")
        if self.progress_bar is not None:
            self.progress_bar.configure(maximum=max(config.points, 1), value=0)
        if self._plot_redraw_after_id is not None:
            self.after_cancel(self._plot_redraw_after_id)
            self._plot_redraw_after_id = None
        if self._trace_redraw_after_id is not None:
            self.after_cancel(self._trace_redraw_after_id)
            self._trace_redraw_after_id = None
        for item in self.table.get_children():
            self.table.delete(item)
        self._redraw_plot()
        if self.time_trace is not None:
            self.time_trace._draw_empty()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Barrido en progreso")

        self._worker = threading.Thread(target=self._run_worker, args=(config,), daemon=True)
        self._worker.start()

    def _run_worker(self, config: SweepConfig) -> None:
        backend = None
        try:
            backend = VirtualBenchPyBackend(config.resource)

            def progress(point: SweepPoint, index: int, total: int) -> None:
                if self._stop_requested:
                    raise KeyboardInterrupt
                self._queue.put(("point", point))
                self._queue.put(("progress", (index, total, point.frequency_hz)))
                self._queue.put(("status", f"Midiendo {index}/{total}: {point.frequency_hz:.3g} Hz"))

            def trace(acquisition: Acquisition, frequency_hz: float) -> None:
                self._queue.put(("trace", (frequency_hz, acquisition, config.ch_reference, config.ch_response)))

            points = run_sweep(
                config,
                backend,
                progress=progress,
                trace=trace,
                stop_on_min_gain=self.stop_attenuation_var.get(),
            )
            self._queue.put(("done", points))
        except KeyboardInterrupt:
            self._queue.put(("stopped", None))
        except Exception as exc:
            self._queue.put(("error", str(exc)))
        finally:
            if backend is not None:
                backend.close()

    def _poll_worker(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "device":
                    self.resource_var.set(str(payload))
                    self.device_status_var.set(f"Conectado: {payload}")
                    self.status_var.set("Instrumento listo")
                    self._refresh_start_state()
                elif kind == "device_error":
                    self.resource_var.set("")
                    self.device_status_var.set("VirtualBench no detectado")
                    self.status_var.set(f"No se detectó VirtualBench. Revise USB/alimentación y presione Reconectar. Detalle: {payload}")
                    self.start_button.configure(state="disabled")
                elif kind == "point":
                    self._add_point(payload)  # type: ignore[arg-type]
                elif kind == "trace":
                    self._last_trace_payload = payload  # type: ignore[assignment]
                    self._schedule_trace_update(self._last_trace_payload)
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "progress":
                    index, total, frequency_hz = payload  # type: ignore[misc]
                    self._update_progress(int(index), int(total), float(frequency_hz))
                elif kind == "done":
                    self._finish_run(f"Terminado: {len(payload)} puntos")  # type: ignore[arg-type]
                elif kind == "stopped":
                    self._finish_run(f"Detenido: {len(self._points)} puntos")
                elif kind == "error":
                    self._finish_run("Error")
                    messagebox.showerror("Error de barrido", str(payload))
        except queue.Empty:
            pass
        self.after(50, self._poll_worker)

    def _update_progress(self, index: int, total: int, frequency_hz: float) -> None:
        if self.progress_bar is not None:
            self.progress_bar.configure(maximum=max(total, 1), value=index)
        elapsed = max(time.monotonic() - self._run_started_at, 0.001)
        remaining = max(total - index, 0)
        eta_s = elapsed / max(index, 1) * remaining
        percent = min(index / max(total, 1) * 100.0, 100.0)
        self.progress_var.set(f"Progreso: {percent:4.0f}% | {frequency_hz:.4g} Hz | ETA {eta_s:4.0f} s")

    def _add_point(self, point: SweepPoint) -> None:
        self._points.append(point)
        self.last_point_var.set(
            f"{point.frequency_hz:.6g} Hz\n"
            f"{point.gain_db:.3f} dB\n"
            f"{point.phase_deg:.3f}°"
        )
        self.table.insert(
            "",
            "end",
            values=(
                f"{point.frequency_hz:.6g}",
                f"{point.gain_v:.6g}",
                f"{point.gain_db:.3f}",
                f"{point.phase_deg:.3f}",
                f"{point.reference_amp_v:.6g}",
                f"{point.response_amp_v:.6g}",
            ),
        )
        self._schedule_plot_redraw()

    def _schedule_plot_redraw(self, delay_ms: int = 180) -> None:
        if self._plot_redraw_after_id is not None:
            return
        self._plot_redraw_after_id = self.after(delay_ms, self._flush_plot_redraw)

    def _flush_plot_redraw(self) -> None:
        self._plot_redraw_after_id = None
        self._redraw_plot()

    def _schedule_trace_update(self, payload: tuple[float, Acquisition, str, str], delay_ms: int = 250) -> None:
        self._pending_trace_payload = payload
        if self._trace_redraw_after_id is not None:
            return
        self._trace_redraw_after_id = self.after(delay_ms, self._flush_trace_update)

    def _flush_trace_update(self) -> None:
        self._trace_redraw_after_id = None
        if self.time_trace is not None and self._pending_trace_payload is not None:
            self.time_trace.update_trace(self._pending_trace_payload)
        self._pending_trace_payload = None

    def _style_plot_axis(self, axis: object) -> None:
        axis.set_facecolor(self.palette["plot"])
        axis.tick_params(colors=self.palette["subtle"], labelsize=8)
        for spine in axis.spines.values():
            spine.set_color(self.palette["grid"])
        axis.grid(True, which="both", color=self.palette["grid"], linewidth=0.75, alpha=0.78)

    def _redraw_plot(self) -> None:
        self.gain_ax.clear()
        self.phase_ax.clear()
        for axis in (self.gain_ax, self.phase_ax):
            self._style_plot_axis(axis)
        self.gain_ax.set_title("Respuesta en frecuencia", loc="left", fontsize=11, color=self.palette["text"])
        self.gain_ax.set_ylabel("Ganancia (dB)", color=self.palette["subtle"])
        self.phase_ax.set_ylabel("Fase (°)", color=self.palette["subtle"])
        self.phase_ax.set_xlabel("Frecuencia (Hz)", color=self.palette["subtle"])
        try:
            target = float(self.target_gain_var.get())
            self.gain_ax.axhline(target, color=self.palette["muted"], linewidth=0.9, linestyle="--", alpha=0.75)
        except ValueError:
            pass
        if self._points:
            freq = [p.frequency_hz for p in self._points]
            gain = [p.gain_db for p in self._points]
            phase = [p.phase_deg for p in self._points]
            plot_gain = self.gain_ax.plot if self.sweep_mode_var.get().lower().startswith("lin") else self.gain_ax.semilogx
            plot_phase = self.phase_ax.plot if self.sweep_mode_var.get().lower().startswith("lin") else self.phase_ax.semilogx
            plot_gain(freq, gain, linewidth=1.75, color=self.palette["accent"], antialiased=True, solid_capstyle="round")
            plot_phase(freq, phase, linewidth=1.75, color=self.palette["accent_2"], antialiased=True, solid_capstyle="round")
            if len(freq) <= 300:
                self.gain_ax.scatter(freq, gain, s=18, color=self.palette["accent_soft"], edgecolors=self.palette["bg"], linewidths=0.5, zorder=3)
                self.phase_ax.scatter(freq, phase, s=18, color=self.palette["accent_2_soft"], edgecolors=self.palette["bg"], linewidths=0.5, zorder=3)
        if not self._plot_layout_ready:
            self.figure.tight_layout()
            self._plot_layout_ready = True
        self.canvas.draw_idle()

    def _show_time_window(self) -> None:
        if self.time_trace is not None and self._last_trace_payload is not None:
            self.time_trace.update_trace(self._last_trace_payload)
        self.status_var.set("La traza de voltaje vs tiempo esta integrada en el panel principal.")

    def _request_stop(self) -> None:
        self._stop_requested = True
        self.status_var.set("Deteniendo al terminar el punto actual")

    def _power_values_from_ui(self) -> tuple[float, float, float]:
        pos_voltage = self._parse_float(self.ps_pos_voltage_var, "+25V set")
        neg_voltage = self._parse_float(self.ps_neg_voltage_var, "-25V set")
        current_limit = self._parse_float(self.ps_current_var, "Corriente límite")
        self._validate_range(pos_voltage, "+25V set", 0.0, 25.0)
        self._validate_range(neg_voltage, "-25V set", -25.0, 0.0)
        self._validate_range(current_limit, "Corriente límite", 0.001, 1.0, "0.1 A es un inicio seguro.")
        return pos_voltage, neg_voltage, current_limit

    def _apply_power_supply(self) -> None:
        try:
            resource = self.resource_var.get().strip()
            if not resource:
                raise ValueError("No hay VirtualBench detectado.")
            pos_voltage, neg_voltage, current_limit = self._power_values_from_ui()
            if not self.ps_output_enabled_var.get():
                disable_power_supply_outputs(resource)
                self.status_var.set("Fuente DC configurada con salida deshabilitada.")
                self.device_status_var.set(f"Conectado: {resource} | fuentes apagadas")
                self.pos_gauge.draw(0.0)
                self.neg_gauge.draw(0.0)
                return
            if self.ps_high_power_guard_var.get() and (
                abs(pos_voltage) > 15.0 or abs(neg_voltage) > 15.0 or current_limit > 0.5
            ):
                if not messagebox.askyesno(
                    "Confirmar fuente DC",
                    "La configuración supera 15 V o 0.5 A. Confirme que el circuito soporta estos limites.",
                ):
                    return
            six_voltage = 6.0 if self.ps_six_enabled_var.get() else 0.0
            (pos_actual_v, pos_actual_i), (neg_actual_v, neg_actual_i), (six_actual_v, six_actual_i) = configure_power_supply_rails(
                resource,
                pos_voltage,
                neg_voltage,
                current_limit,
                six_voltage,
            )
        except Exception as exc:
            messagebox.showerror("Fuente DC", str(exc))
            return
        self.pos_gauge.draw(pos_voltage)
        self.neg_gauge.draw(neg_voltage)
        six_label = "+6V activo" if self.ps_six_enabled_var.get() else "+6V a 0 V"
        self.status_var.set(
            f"Fuente DC aplicada: +{pos_voltage:.4g} V / {neg_voltage:.4g} V, "
            f"limite {current_limit:.4g} A, {six_label}"
        )
        self.device_status_var.set(
            f"Conectado: {resource} | +25V {pos_actual_v:.4g} V {pos_actual_i:.4g} A | "
            f"-25V {neg_actual_v:.4g} V {neg_actual_i:.4g} A | +6V {six_actual_v:.4g} V {six_actual_i:.4g} A"
        )

    def _disable_power_supply(self) -> None:
        try:
            resource = self.resource_var.get().strip()
            if not resource:
                raise ValueError("No hay VirtualBench detectado.")
            disable_power_supply_outputs(resource)
        except Exception as exc:
            messagebox.showerror("Fuente DC", str(exc))
            return
        self.ps_output_enabled_var.set(False)
        self.status_var.set("Salidas de fuente apagadas")
        self.device_status_var.set(f"Conectado: {resource} | fuentes apagadas")
        self.pos_gauge.draw(0.0)
        self.neg_gauge.draw(0.0)

    def _update_power_gauges(self, *_args: object) -> None:
        try:
            self.pos_gauge.draw(float(self.ps_pos_voltage_var.get()))
        except (ValueError, AttributeError):
            pass
        try:
            self.neg_gauge.draw(float(self.ps_neg_voltage_var.get()))
        except (ValueError, AttributeError):
            pass

    def _finish_run(self, status: str) -> None:
        if self._plot_redraw_after_id is not None:
            self.after_cancel(self._plot_redraw_after_id)
            self._plot_redraw_after_id = None
        if self._trace_redraw_after_id is not None:
            self.after_cancel(self._trace_redraw_after_id)
            self._trace_redraw_after_id = None
        if self._pending_trace_payload is not None and self.time_trace is not None:
            self.time_trace.update_trace(self._pending_trace_payload)
            self._pending_trace_payload = None
        self._redraw_plot()
        if self.progress_bar is not None and self._run_total_points:
            self.progress_bar.configure(value=len(self._points))
        self.progress_var.set(f"Progreso: {len(self._points)}/{self._run_total_points or len(self._points)} puntos")
        self.status_var.set(status)
        self.stop_button.configure(state="disabled")
        self._update_live_validation()

    def _save_csv(self) -> None:
        if not self._points:
            messagebox.showinfo("Sin datos", "No hay puntos para guardar.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar barrido",
            defaultextension=".csv",
            filetypes=(("CSV", "*.csv"), ("Todos", "*.*")),
            initialfile="vbarrido_virtualbench.csv",
        )
        if not path:
            return
        write_csv(Path(path), self._points)
        self.status_var.set(f"CSV guardado: {path}")

    def _save_svg(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Guardar gráfica SVG",
            defaultextension=".svg",
            filetypes=(("SVG", "*.svg"), ("Todos", "*.*")),
            initialfile="vbarrido_respuesta.svg",
        )
        if not path:
            return
        self.figure.savefig(path, format="svg", facecolor=self.figure.get_facecolor(), bbox_inches="tight")
        self.status_var.set(f"SVG guardado: {path}")

    def _export_selected(self) -> None:
        try:
            self._validate_graph_config()
        except ValueError as exc:
            messagebox.showerror("Datos de las gráficas", str(exc))
            return
        if not self.export_csv_var.get() and not self.export_svg_var.get():
            messagebox.showinfo("Exportación", "Seleccione CSV, SVG o ambos.")
            return
        if self.export_csv_var.get():
            self._save_csv()
        if self.export_svg_var.get():
            self._save_svg()

    def _show_graph_help(self) -> None:
        popup = tk.Toplevel(self)
        popup.title("Ayuda - Datos de las gráficas")
        popup.geometry("470x300")
        popup.configure(background=self.palette["bg"])
        popup.transient(self)
        popup.grab_set()
        text = (
            "Frecuencia a:\n"
            "Define el valor objetivo de magnitud, por ejemplo -3 dB. La gráfica marca esa referencia y la búsqueda debe tomar "
            "el punto medido más cercano al objetivo.\n\n"
            "Tolerancia Magnitud:\n"
            "Margen permitido alrededor del objetivo de magnitud. Un valor de 1 dB evita rechazar mediciones con ruido moderado.\n\n"
            "Tolerancia Fase:\n"
            "Error angular permitido para identificar puntos relevantes de fase. Use grados reales; 5° es un buen punto inicial."
        )
        ttk.Label(popup, text=text, wraplength=430, justify="left", style="Dark.TLabel").pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Button(popup, text="Cerrar", command=popup.destroy).pack(pady=(0, 14))


def main() -> None:
    app = VBarridoApp()
    app.mainloop()
