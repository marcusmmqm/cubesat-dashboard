"""Barra de troca de telas do quiosque CubeSat (topo da tela do Raspberry).

Botões grandes para alternar entre o dashboard Python e o painel do Node-RED,
e um botão para desligar o Raspberry com segurança. As janelas são trocadas
pelo compositor (labwc) com o `wlrctl`; os dois programas ficam abertos o tempo
todo, então a troca é instantânea e os gráficos não perdem o histórico.
"""
import subprocess
import time
import tkinter as tk

ALTURA = 44            # tem que bater com <margin top="..."> no labwc/rc.xml
PRIMEIROS_S = 90       # no boot, segura o dashboard na frente até alguém tocar

BG = "#0f1419"
TILE = "#1e262f"
BORDER = "#2b3540"
TEXT = "#e6edf3"
MUTED = "#8b98a5"
ACCENT = "#4fa3ff"
ERR = "#f85149"
FONT = "DejaVu Sans"


def _lora(app_id, title):
    return "Telemetria LoRa" in title


def _nodered(app_id, title):
    return app_id.lower().startswith("chrom")


TELAS = [
    ("lora", "Telemetria LoRa", _lora),
    ("nodered", "Node-RED", _nodered),
]


def janelas():
    """Lista (app_id, título) das janelas abertas, via wlrctl."""
    try:
        out = subprocess.run(["wlrctl", "toplevel", "list"], capture_output=True,
                             text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    res = []
    for linha in out.splitlines():
        app_id, _, title = linha.partition(": ")
        res.append((app_id.strip(), title.strip()))
    return res


def achar(teste):
    for app_id, title in janelas():
        if teste(app_id, title):
            return app_id, title
    return None


def focar(app_id, title):
    cmd = ["wlrctl", "toplevel", "focus", f"app_id:{app_id}"]
    if title:
        cmd.append(f"title:{title}")
    try:
        return subprocess.run(cmd, capture_output=True, timeout=2).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def em_foco():
    """Qual das telas está em foco agora (ou None)."""
    for chave, _, teste in TELAS:
        j = achar(teste)
        if j is None:
            continue
        cmd = ["wlrctl", "toplevel", "find", f"app_id:{j[0]}", "state:focused"]
        if j[1]:
            cmd.append(f"title:{j[1]}")
        try:
            if subprocess.run(cmd, capture_output=True, timeout=2).returncode == 0:
                return chave
        except (OSError, subprocess.SubprocessError):
            pass
    return None


class Barra:
    def __init__(self, root):
        self.root = root
        self.inicio = time.monotonic()
        self.usuario_escolheu = False
        self.atual = None

        root.title("CubeSat · barra")
        root.configure(bg=BG)
        root.geometry(f"{root.winfo_screenwidth()}x{ALTURA}+0+0")

        self.botoes = {}
        for chave, rotulo, _ in TELAS:
            b = tk.Button(root, text=rotulo, font=(FONT, 12, "bold"),
                          bg=TILE, fg=MUTED, activebackground=BORDER,
                          activeforeground=TEXT, relief="flat", bd=0,
                          highlightthickness=0, padx=18,
                          command=lambda c=chave: self.mostrar(c, manual=True))
            b.pack(side="left", fill="y", padx=(6, 0), pady=5)
            self.botoes[chave] = b

        self.msg = tk.Label(root, text="", bg=BG, fg=MUTED, font=(FONT, 10))
        self.msg.pack(side="left", padx=12)

        # desligar: primeiro toque pede confirmação, segundo desliga
        self.desl = tk.Button(root, text="Desligar", font=(FONT, 11),
                              bg=TILE, fg=MUTED, activebackground=BORDER,
                              activeforeground=TEXT, relief="flat", bd=0,
                              highlightthickness=0, padx=14,
                              command=self.pedir_desligar)
        self.desl.pack(side="right", fill="y", padx=6, pady=5)
        self.cancel = tk.Button(root, text="Cancelar", font=(FONT, 11),
                                bg=TILE, fg=TEXT, activebackground=BORDER,
                                relief="flat", bd=0, highlightthickness=0, padx=14,
                                command=self.cancelar_desligar)
        self._timer_desl = None

        self.realcar(None)
        self.root.after(1000, self.vigiar)

    # ------------------------------------------------------------ telas
    def mostrar(self, chave, manual=False):
        if manual:
            self.usuario_escolheu = True
        teste = dict((c, t) for c, _, t in TELAS)[chave]
        j = achar(teste)
        if j is None or not focar(*j):
            self.msg.config(text="abrindo…" if j is None else "não consegui trocar",
                            fg=MUTED)
            return
        self.msg.config(text="")
        self.realcar(chave)

    def realcar(self, chave):
        self.atual = chave
        for c, b in self.botoes.items():
            if c == chave:
                b.config(bg=ACCENT, fg=BG, activebackground=ACCENT, activeforeground=BG)
            else:
                b.config(bg=TILE, fg=MUTED, activebackground=BORDER, activeforeground=TEXT)

    def vigiar(self):
        """A cada segundo: acompanha qual tela está na frente e, logo após o
        boot, mantém o dashboard na frente (o Chromium abre depois e roubaria
        o foco)."""
        foco = em_foco()
        no_boot = time.monotonic() - self.inicio < PRIMEIROS_S
        if no_boot and not self.usuario_escolheu and foco != "lora":
            if achar(_lora):
                self.mostrar("lora")
        elif foco is not None and foco != self.atual:
            self.realcar(foco)
        self.root.after(1000, self.vigiar)

    # ---------------------------------------------------------- desligar
    def pedir_desligar(self):
        if self._timer_desl is None:
            self.desl.config(text="Confirmar desligar", bg=ERR, fg=TEXT,
                             activebackground=ERR)
            self.cancel.pack(side="right", fill="y", pady=5)
            self._timer_desl = self.root.after(6000, self.cancelar_desligar)
            return
        self.msg.config(text="desligando…", fg=ERR)
        self.root.update_idletasks()
        r = subprocess.run(["systemctl", "poweroff"], capture_output=True, text=True)
        if r.returncode != 0:
            self.msg.config(text="não foi possível desligar", fg=ERR)
        self.cancelar_desligar()

    def cancelar_desligar(self):
        if self._timer_desl is not None:
            self.root.after_cancel(self._timer_desl)
            self._timer_desl = None
        self.cancel.pack_forget()
        self.desl.config(text="Desligar", bg=TILE, fg=MUTED, activebackground=BORDER)


def main():
    root = tk.Tk(className="cubesat-barra")
    Barra(root)
    root.mainloop()


if __name__ == "__main__":
    main()
