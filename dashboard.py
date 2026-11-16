import argparse
import collections
import math
import queue
import socket
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
        y=(-3000, 3000, 500),
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
        y=(-400, 400, 50),
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
FRAME_MS = 40       # intervalo entre quadros da tela (40 ms = 25 quadros/s)


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


class TcpReader(threading.Thread):
    """Recebe as linhas do LoRa repassadas pelo Node-RED (conexão TCP local) e
    põe (t, can_id, data) na fila. Usado no Raspberry, onde o Node-RED é o dono
    da serial (para também poder enviar comandos)."""

    def __init__(self, host, port, out):
        super().__init__(daemon=True)
        self.host, self.port, self.out = host, port, out
        self.status = ("conectando ao Node-RED…", WARN)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=2) as s:
                    s.settimeout(0.5)
                    self.status = (f"via Node-RED ({self.host}:{self.port})", OK)
                    buf = b""
                    while not self._stop.is_set():
                        try:
                            chunk = s.recv(4096)
                        except socket.timeout:
                            continue
                        if not chunk:
                            raise ConnectionError("Node-RED fechou a conexão")
                        buf += chunk
                        *lines, buf = buf.split(b"\n")
                        for line in lines:
                            msg = parse_line(line)
                            if msg:
                                self.out.put((time.time(),) + msg)
            except OSError as e:
                self.status = (f"sem conexão com o Node-RED ({e}) — tentando de novo", ERR)
                self._stop.wait(2.0)

    def stop(self):
        self._stop.set()


def parse_hostport(text):
    """'localhost:5555' -> ('localhost', 5555)."""
    host, _, port = text.rpartition(":")
    return host or "localhost", int(port)


# ----------------------------------------------------------------- gráfico
class XYChart(tk.Frame):
    """Várias séries no mesmo referencial: tempo (x) × valor (y, escala fixa)."""

    ML, MR, MT, MB = 62, 16, 12, 30   # margens do gráfico (px)

    def __init__(self, master, cfg, window_s, compact=False):
        super().__init__(master, bg=PANEL)
        self.window_s = window_s
        self.y_min, self.y_max, self.y_step = cfg["y"]
        self.signed = cfg["signed"]
        self.series = []   # dicts: can_id, field, color, hist, value_lbl
        legend = tk.Frame(self, bg=PANEL)
        legend.pack(fill="x", pady=(8, 6))
        ncols = min(cfg["legend_cols"], 2) if compact else cfg["legend_cols"]
        value_font = (MONO, 9 if compact else 12, "bold")
        for i, (can_id, field, label, color) in enumerate(cfg["series"]):
            row = tk.Frame(legend, bg=PANEL)
            row.grid(row=i // ncols, column=i % ncols, sticky="w",
                     padx=(0, 8 if compact else 18), pady=1)
            tk.Frame(row, bg=color, width=14, height=4).pack(side="left", padx=(0, 6))
            tk.Label(row, text=label, bg=PANEL, fg=MUTED,
                     font=(FONT, 8 if compact else 9)).pack(side="left")
            # largura fixa (6 caracteres cabem qualquer int16/uint16):
            # o texto muda, mas a legenda não se mexe
            val = tk.Label(row, text="—", bg=PANEL, fg=TEXT, width=6, anchor="e",
                           font=value_font)
            val.pack(side="left", padx=(2 if compact else 8, 0))
            self.series.append(dict(can_id=can_id, field=field, color=color,
                                    hist=collections.deque(), value_lbl=val,
                                    shown="—", line=None, dot=None))
        self.canvas = tk.Canvas(self, bg=TILE, highlightthickness=1,
                                highlightbackground=BORDER)
        self.canvas.pack(fill="both", expand=True)
        self._box = None                      # (x0, x1, y0, y1) da área de plotagem
        self.canvas.bind("<Configure>", self._layout)

    def _layout(self, event=None):
        """Desenha grade e eixos (fixos) e cria uma linha + ponto por série.
        Só roda quando o canvas muda de tamanho; a cada quadro, redraw() apenas
        move as linhas existentes."""
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        x0, x1 = self.ML, w - self.MR
        y0, y1 = self.MT, h - self.MB          # y0 = topo (y_max), y1 = base (y_min)
        c.delete("all")
        if x1 <= x0 or y1 <= y0:
            self._box = None
            return
        self._box = (x0, x1, y0, y1)
        lo, hi = self.y_min, self.y_max

        # grade e eixo y; em tela baixa, rotula só uma linha a cada k
        # (sempre incluindo o 0) para os números não se sobreporem
        px_por_passo = (y1 - y0) * self.y_step / (hi - lo)
        k = max(1, math.ceil(16 / px_por_passo))
        for v in range(lo, hi + 1, self.y_step):
            y = y1 - (v - lo) / (hi - lo) * (y1 - y0)
            strong = v in (lo, hi) or (v == 0 and lo < 0)
            c.create_line(x0, y, x1, y, fill=MUTED if v == 0 and lo < 0 else BORDER,
                          dash=() if strong else (2, 4))
            if (v // self.y_step) % k:
                continue
            txt = f"{v:+d}" if (lo < 0 and v) else f"{v}"
            c.create_text(x0 - 8, y, text=txt, anchor="e", fill=MUTED, font=(MONO, 9))
        # grade e eixo x (segundos atrás: posições fixas na tela)
        step = max(1, self.window_s // 6)
        for s_ago in range(0, self.window_s + 1, step):
            x = x1 - s_ago / self.window_s * (x1 - x0)
            c.create_line(x, y0, x, y1, fill=BORDER, dash=(2, 4))
            c.create_text(x, y1 + 6, text=f"-{s_ago} s" if s_ago else "agora",
                          anchor="ne" if s_ago == 0 else "n",
                          fill=MUTED, font=(MONO, 9))
        c.create_rectangle(x0, y0, x1, y1, outline=BORDER)

        # séries: linhas primeiro, pontos depois (pontos ficam por cima)
        for s in self.series:
            s["line"] = c.create_line(0, 0, 0, 0, fill=s["color"], width=2,
                                      state="hidden")
        for s in self.series:
            s["dot"] = c.create_oval(0, 0, 0, 0, fill=s["color"], outline="",
                                     state="hidden")

    def clear(self):
        """Apaga o histórico de todas as séries deste gráfico."""
        for s in self.series:
            s["hist"].clear()
            s["shown"] = "—"
            s["value_lbl"].config(text="—")
            if s["line"] is not None:
                self.canvas.itemconfigure(s["line"], state="hidden")
                self.canvas.itemconfigure(s["dot"], state="hidden")

    def can_ids(self):
        return {s["can_id"] for s in self.series}

    def push(self, can_id, t, values):
        for s in self.series:
            if s["can_id"] == can_id:
                v = values[s["field"]]
                s["hist"].append((t, to_int16(v) if self.signed else v))

    def redraw(self, now):
        """Move as linhas das séries para a posição atual (sem recriar nada)."""
        if self._box is None:
            return
        c = self.canvas
        x0, x1, y0, y1 = self._box
        lo, hi = self.y_min, self.y_max
        cut = now - self.window_s
        kx = (x1 - x0) / self.window_s
        ky = (y1 - y0) / (hi - lo)

        for s in self.series:
            hist = s["hist"]
            while hist and hist[0][0] < cut:
                hist.popleft()
            if not hist:
                c.itemconfigure(s["line"], state="hidden")
                c.itemconfigure(s["dot"], state="hidden")
                continue
            pts = []
            for t, v in hist:
                v = lo if v < lo else hi if v > hi else v   # fora da escala -> borda
                pts.append(x0 + (t - cut) * kx)
                pts.append(y1 - (v - lo) * ky)
            if len(hist) >= 2:
                c.coords(s["line"], pts)
                c.itemconfigure(s["line"], state="normal")
            else:
                c.itemconfigure(s["line"], state="hidden")
            px, py = pts[-2], pts[-1]
            c.coords(s["dot"], px - 3, py - 3, px + 3, py + 3)
            c.itemconfigure(s["dot"], state="normal")
            txt = f"{hist[-1][1]}"
            if txt != s["shown"]:                 # só mexe no rótulo se mudou
                s["shown"] = txt
                s["value_lbl"].config(text=txt)


# ----------------------------------------------------------------- app
class App:
    def __init__(self, root, port, baud, window_s, fullscreen=False, tcp=None):
        self.root = root
        self.q = queue.Queue()
        if tcp:
            self.reader = TcpReader(*parse_hostport(tcp), self.q)
        else:
            self.reader = SerialReader(port, baud, self.q)
        self.total = 0

        root.title("CubeSat · Telemetria LoRa")
        root.configure(bg=BG)
        if fullscreen:   # ocupa a tela toda (ex.: display do Raspberry, sem gerenciador de janelas)
            root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
        else:
            root.geometry("1500x880")
        # tela pequena (ex.: display de 800x480 do Raspberry): legenda mais enxuta
        compact = fullscreen and root.winfo_screenwidth() < 1200

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
            chart = XYChart(p, cfg, window_s, compact)
            btn.config(command=chart.clear)
            chart.pack(fill="both", expand=True)
            self.charts.append(chart)

        root.protocol("WM_DELETE_WINDOW", self.close)
        self._status_shown = None
        self.reader.start()
        self.tick()

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

    def redraw(self):
        now = time.time()
        for chart in self.charts:
            chart.redraw(now)
        text, color = self.reader.status
        status = (f"● {text} · {self.total} mensagens", color)
        if status != self._status_shown:
            self._status_shown = status
            self.status.config(text=status[0], fg=status[1])

    def tick(self):
        """Um quadro: lê o que chegou da serial e redesenha (FRAME_MS)."""
        self.poll()
        self.redraw()
        self.root.after(FRAME_MS, self.tick)

    def close(self):
        self.reader.stop()
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None,
                    help="ex.: COM5 ou /dev/ttyUSB0 (padrão: detecta o receptor)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--janela", type=int, default=60,
                    help="segundos mostrados nos gráficos (padrão 60)")
    ap.add_argument("--tela-cheia", action="store_true",
                    help="janela do tamanho da tela (ex.: display do Raspberry)")
    ap.add_argument("--tcp", metavar="HOST:PORTA", default=None,
                    help="recebe as linhas do Node-RED em vez de abrir a serial "
                         "(no Raspberry: localhost:5555)")
    a = ap.parse_args()
    root = tk.Tk()
    App(root, a.port, a.baud, a.janela, fullscreen=a.tela_cheia, tcp=a.tcp)
    root.mainloop()


if __name__ == "__main__":
    main()
