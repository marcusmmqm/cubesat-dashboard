import argparse
import collections
import queue
import sys
import threading
import time
import tkinter as tk

import serial
from serial.tools import list_ports

from can_parser import decode, parse_line, to_int16

# ----------------------------------------------------------------- layout
# Cada gráfico: título, faixa do eixo y, se converte para int16 com sinal,
# quantas entradas por linha na legenda, e as séries (can_id, campo, rótulo, cor).
CHARTS = [
    dict(
        title="Velocidades da roda de reação",
        y=(-2000, 2000, 500),
        signed=True,
        legend_cols=2,
        series=[
            (0x1F864, "MeasuredSpeed", "MeasuredSpeed", "#4fa3ff"),
            (0x1F864, "RefSpeed", "RefSpeed", "#f0883e"),
            (0x408A2, "RefSpeed Roda Reação", "RefSpeed Roda Reação", "#3fb950"),
            (0x408A2, "Esforço PID", "Esforço PID", "#db61a2"),
        ],
    ),
    dict(
        title="Painéis solares e atitude",
        y=(0, 400, 50),
        signed=False,
        legend_cols=3,
        series=[
            (0x520B6, "v_solar_bottom", "v_solar_bottom", "#4fa3ff"),
            (0x520B6, "v_solar_Yminus", "v_solar_Yminus", "#f0883e"),
            (0x520B6, "v_solar_Y", "v_solar_Y", "#3fb950"),
            (0x520B6, "v_solar_Xminus", "v_solar_Xminus", "#db61a2"),
            (0x520B6, "v_solar_X", "v_solar_X", "#a371f7"),
            (0x520B6, "v_solar_top", "v_solar_top", "#e3b341"),
            (0x520B6, "v_solar_vout", "v_solar_vout", "#39c5cf"),
            (0x408A2, "Azimute satélite", "Azimute satélite", "#ff7b72"),
            (0x408A2, "Vel. angular Azim.", "Vel. angular Azim.", "#e6edf3"),
        ],
    ),
]

# ----------------------------------------------------------------- cores
BG = "#0f1419"
PANEL = "#171d24"
TILE = "#1e262f"
BORDER = "#2b3540"
TEXT = "#e6edf3"
MUTED = "#8b98a5"
ACCENT = "#4fa3ff"
OK = "#3fb950"
WARN = "#d29922"
ERR = "#f85149"

if sys.platform == "win32":
    FONT, MONO = "Segoe UI", "Consolas"
else:
    FONT, MONO = "DejaVu Sans", "DejaVu Sans Mono"

FTDI_VID = 0x0403   # adaptador USB-serial do receptor LoRa (FT231X)


def choose_port(ports):
    """Escolhe a porta do receptor: FTDI primeiro, depois qualquer porta USB.
    Portas sem USB (COM1, /dev/ttyS*) são ignoradas."""
    usb = [p for p in ports if p.vid is not None]
    for p in usb:
        if p.vid == FTDI_VID:
            return p.device
    return usb[0].device if usb else None


# ----------------------------------------------------------------- serial
class SerialReader(threading.Thread):
    """Lê a serial numa thread e põe (t, can_id, data) na fila."""

    def __init__(self, port, baud, out):
        super().__init__(daemon=True)
        self.port, self.baud, self.out = port, baud, out
        self.status = ("conectando…", WARN)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            # sem --port: procura o receptor a cada tentativa (no Windows o
            # número da COM pode mudar ao trocar de porta USB)
            port = self.port or choose_port(list_ports.comports())
            if port is None:
                self.status = ("receptor não encontrado — conecte o USB", WARN)
                self._stop.wait(2.0)
                continue
            try:
                with serial.Serial(port, self.baud, timeout=0.5) as s:
                    self.status = (f"{port} @ {self.baud}", OK)
                    while not self._stop.is_set():
                        line = s.readline()
                        if not line:
                            continue
                        msg = parse_line(line)
                        if msg:
                            self.out.put((time.time(),) + msg)
            except (serial.SerialException, OSError) as e:
                self.status = (f"erro na serial: {e} — tentando de novo", ERR)
                self._stop.wait(2.0)

    def stop(self):
        self._stop.set()


# ----------------------------------------------------------------- gráfico
class XYChart(tk.Frame):
    """Várias séries no mesmo referencial: tempo (x) × valor (y, escala fixa)."""

    ML, MR, MT, MB = 62, 16, 12, 30   # margens do gráfico (px)

    def __init__(self, master, cfg, window_s):
        super().__init__(master, bg=PANEL)
        self.window_s = window_s
        self.y_min, self.y_max, self.y_step = cfg["y"]
        self.signed = cfg["signed"]
        self.series = []   # dicts: can_id, field, color, hist, value_lbl
        legend = tk.Frame(self, bg=PANEL)
        legend.pack(fill="x", pady=(8, 6))
        ncols = cfg["legend_cols"]
        for i, (can_id, field, label, color) in enumerate(cfg["series"]):
            row = tk.Frame(legend, bg=PANEL)
            row.grid(row=i // ncols, column=i % ncols, sticky="w",
                     padx=(0, 18), pady=1)
            tk.Frame(row, bg=color, width=14, height=4).pack(side="left", padx=(0, 6))
            tk.Label(row, text=label, bg=PANEL, fg=MUTED,
                     font=(FONT, 9)).pack(side="left")
            # largura fixa (6 caracteres cabem qualquer int16/uint16):
            # o texto muda, mas a legenda não se mexe
            val = tk.Label(row, text="—", bg=PANEL, fg=TEXT, width=6, anchor="e",
                           font=(MONO, 12, "bold"))
            val.pack(side="left", padx=(8, 0))
            self.series.append(dict(can_id=can_id, field=field, color=color,
                                    hist=collections.deque(), value_lbl=val))
        self.canvas = tk.Canvas(self, bg=TILE, highlightthickness=1,
                                highlightbackground=BORDER)
        self.canvas.pack(fill="both", expand=True)

    def clear(self):
        """Apaga o histórico de todas as séries deste gráfico."""
        for s in self.series:
            s["hist"].clear()
            s["value_lbl"].config(text="—")
        self.canvas.delete("all")

    def can_ids(self):
        return {s["can_id"] for s in self.series}

    def push(self, can_id, t, values):
        for s in self.series:
            if s["can_id"] == can_id:
                v = values[s["field"]]
                s["hist"].append((t, to_int16(v) if self.signed else v))

    def redraw(self, now):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        x0, x1 = self.ML, w - self.MR
        y0, y1 = self.MT, h - self.MB          # y0 = topo (y_max), y1 = base (y_min)
        if x1 <= x0 or y1 <= y0:
            return
        lo, hi = self.y_min, self.y_max
        cut = now - self.window_s

        def px(t):
            return x0 + (t - cut) / self.window_s * (x1 - x0)

        def py(v):
            v = max(lo, min(hi, v))           # fora da escala -> encosta na borda
            return y1 - (v - lo) / (hi - lo) * (y1 - y0)

        # grade e eixo y
        for v in range(lo, hi + 1, self.y_step):
            y = py(v)
            strong = v in (lo, hi) or (v == 0 and lo < 0)
            c.create_line(x0, y, x1, y, fill=MUTED if v == 0 and lo < 0 else BORDER,
                          dash=() if strong else (2, 4))
            txt = f"{v:+d}" if (lo < 0 and v) else f"{v}"
            c.create_text(x0 - 8, y, text=txt, anchor="e", fill=MUTED, font=(MONO, 9))
        # grade e eixo x (segundos atrás)
        step = max(1, self.window_s // 6)
        for s_ago in range(0, self.window_s + 1, step):
            x = px(now - s_ago)
            c.create_line(x, y0, x, y1, fill=BORDER, dash=(2, 4))
            c.create_text(x, y1 + 6, text=f"-{s_ago} s" if s_ago else "agora",
                          anchor="ne" if s_ago == 0 else "n",
                          fill=MUTED, font=(MONO, 9))
        c.create_rectangle(x0, y0, x1, y1, outline=BORDER)

        # séries
        for s in self.series:
            hist = s["hist"]
            while hist and hist[0][0] < cut:
                hist.popleft()
            if not hist:
                continue
            pts = []
            for t, v in hist:
                pts += [px(t), py(v)]
            if len(pts) >= 4:
                c.create_line(*pts, fill=s["color"], width=2)
            c.create_oval(pts[-2] - 3, pts[-1] - 3, pts[-2] + 3, pts[-1] + 3,
                          fill=s["color"], outline="")
            s["value_lbl"].config(text=f"{hist[-1][1]}")


# ----------------------------------------------------------------- app
class App:
    def __init__(self, root, port, baud, window_s):
        self.root = root
        self.q = queue.Queue()
        self.reader = SerialReader(port, baud, self.q)
        self.total = 0

        root.title("CubeSat · Telemetria LoRa")
        root.configure(bg=BG)
        root.geometry("1500x880")

        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(top, text="CubeSat · Telemetria LoRa", bg=BG, fg=TEXT,
                 font=(FONT, 15, "bold")).pack(side="left")
        self.status = tk.Label(top, text="", bg=BG, fg=MUTED, font=(FONT, 10))
        self.status.pack(side="right")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        body.rowconfigure(0, weight=1)

        self.charts = []
        for col, cfg in enumerate(CHARTS):
            p = tk.Frame(body, bg=PANEL, padx=14, pady=10,
                         highlightthickness=1, highlightbackground=BORDER)
            p.grid(row=0, column=col, sticky="nsew", padx=4)
            body.columnconfigure(col, weight=1, uniform="p")
            lo, hi, _ = cfg["y"]
            sub = f"últimos {window_s} s · eixo y fixo de {lo} a {hi}"
            if cfg["signed"]:
                sub += " · int16 com sinal"
            head = tk.Frame(p, bg=PANEL)
            head.pack(fill="x")
            tk.Label(head, text=cfg["title"], bg=PANEL, fg=ACCENT,
                     font=(FONT, 13, "bold"), anchor="w").pack(side="left")
            btn = tk.Button(head, text="Limpar", bg=TILE, fg=TEXT,
                            activebackground=BORDER, activeforeground=TEXT,
                            relief="flat", highlightthickness=1,
                            highlightbackground=BORDER, padx=12, pady=2,
                            font=(FONT, 9), cursor="hand2")
            btn.pack(side="right")
            tk.Label(p, text=sub, bg=PANEL, fg=MUTED, font=(FONT, 8),
                     anchor="w").pack(fill="x")
            chart = XYChart(p, cfg, window_s)
            btn.config(command=chart.clear)
            chart.pack(fill="both", expand=True)
            self.charts.append(chart)

        root.protocol("WM_DELETE_WINDOW", self.close)
        self.reader.start()
        self.poll()
        self.redraw()

    def poll(self):
        try:
            while True:
                t, can_id, data = self.q.get_nowait()
                self.total += 1
                values = decode(can_id, data)
                if values is None:
                    continue
                for chart in self.charts:
                    if can_id in chart.can_ids():
                        chart.push(can_id, t, values)
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def redraw(self):
        now = time.time()
        for chart in self.charts:
            chart.redraw(now)
        text, color = self.reader.status
        self.status.config(text=f"● {text} · {self.total} mensagens", fg=color)
        self.root.after(250, self.redraw)

    def close(self):
        self.reader.stop()
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None,
                    help="ex.: COM5 ou /dev/ttyUSB0 (padrão: detecta o receptor)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--janela", type=int, default=60,
                    help="segundos mostrados nos gráficos (padrão 60)")
    a = ap.parse_args()
    root = tk.Tk()
    App(root, a.port, a.baud, a.janela)
    root.mainloop()


if __name__ == "__main__":
    main()
