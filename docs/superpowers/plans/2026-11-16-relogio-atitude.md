# Relógio de atitude — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o painel "Painéis solares e atitude" do dashboard Python por um relógio de atitude (setpoint em vermelho, posição atual em branco) com legenda.

**Architecture:** A lógica (leitura do 408A2, validação, diferença angular, posição dos ponteiros, textos da legenda) fica num módulo sem Tk (`attitude.py`), testável. O widget `ClockPanel` (Tk Canvas) em `dashboard.py` segue a mesma interface do `XYChart` (`can_ids`, `push`, `redraw`, `clear`), então o `App` só troca o segundo painel.

**Tech Stack:** Python 3 + tkinter + pyserial (sem dependência nova); Node-RED (gerador `nodeRED-rasp/gerar_fluxo_rasp.py`).

**Spec:** `docs/superpowers/specs/2026-11-16-relogio-atitude-design.md`

## Global Constraints

- 408A2: campo 0 `Setpoint_atitude` uint16 BE; 1 `Esforço PID` int16 BE; 2 `Azimute satélite` uint16 BE; 3 `Vel. angular Azim.` int16 BE (°/s).
- Ângulo válido: inteiro de 0 a 359; fora disso → "inválido (N)" e o ponteiro não se move.
- Diferença = alvo − atual pelo caminho mais curto, faixa -180 a +180 (`((alvo − atual + 180) % 360) − 180`).
- Mostrador: marcas de 30° em 30°, rótulo "360°" no alto, sentido horário.
- Vermelho curto = setpoint (`ERR` #f85149); branco longo = posição (`TEXT` #e6edf3).
- Dado parado: sem 408A2 há mais de 5 s → "sem dados há X s", ponteiros em `MUTED`.
- Sem rastro, gráfico de desvio, contador de voltas ou suavização.
- Cabe em 800x436 (modo compacto do Raspberry) e na janela de 1500x880.

## Review Focus

1. 65485 (ou qualquer valor > 359) no azimute/setpoint: legenda "inválido (65485)", ponteiro parado no último válido (ou oculto se nunca houve válido).
2. Antes do primeiro 408A2: legenda "—" e ponteiros ocultos, sem exceção.
3. Alvo 350°, atual 10°: diferença -20° (não +340°).
4. 408A2 parou: após 5 s, "sem dados há 6 s" e ponteiros cinza; volta ao normal quando chega novo quadro.
5. Velocidade negativa: "-3 °/s" (com sinal, nunca 65533).

---

### Task 1: Leitura do 408A2 por campo

**Files:**
- Modify: `can_parser.py` (entrada `0x408A2` de `DECODERS`)
- Test: `test_can_parser.py` (`test_408a2`)

**Interfaces:**
- Produces: `decode(0x408A2, data) -> {"Setpoint_atitude": int, "Esforço PID": int, "Azimute satélite": int, "Vel. angular Azim.": int}`

- [ ] **Step 1: Atualizar o teste**

```python
def test_408a2(self):
    v = decode(0x408A2, bytes.fromhex("012C0002FFCDFFFD"))
    self.assertEqual(v["Setpoint_atitude"], 300)        # uint16
    self.assertEqual(v["Esforço PID"], 2)
    self.assertEqual(v["Azimute satélite"], 65485)      # uint16: inválido, mas cru
    self.assertEqual(v["Vel. angular Azim."], -3)       # int16

def test_408a2_pid_negativo(self):
    self.assertEqual(decode(0x408A2, bytes.fromhex("0000FF8800000000"))["Esforço PID"], -120)
```

- [ ] **Step 2:** `python3 -m unittest test_can_parser` → FAIL (KeyError `Setpoint_atitude`).
- [ ] **Step 3:** Em `DECODERS[0x408A2]`, renomear o campo 0 para `"Setpoint_atitude"` e decodificar com `_u16_be` aplicando `to_int16` só nos campos 1 e 3.
- [ ] **Step 4:** `python3 -m unittest` → todos passam.
- [ ] **Step 5:** Commit `408A2: Setpoint_atitude e azimute sem sinal, PID e velocidade com sinal`.

### Task 2: Lógica do relógio (sem Tk)

**Files:**
- Create: `attitude.py`
- Test: `test_attitude.py`

**Interfaces:**
- Produces:
  - `valid_angle(v: int) -> bool`
  - `angle_diff(target: int, current: int) -> int`
  - `hand_end(cx: float, cy: float, length: float, deg: float) -> tuple[float, float]` (0° = para cima, horário)
  - `class Attitude`: `update(t: float, values: dict) -> None` (recebe o dict do `decode` do 408A2); `last_valid_setpoint`, `last_valid_position` (int | None); `legend(now: float) -> dict` com chaves `"setpoint"`, `"position"`, `"velocity"`, `"diff"`, `"stale"` (str | None); `is_stale(now) -> bool`; `clear() -> None`.
  - Constante `STALE_S = 5`.

- [ ] **Step 1: Testes**

```python
class AngleTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(valid_angle(0)); self.assertTrue(valid_angle(359))
        self.assertFalse(valid_angle(360)); self.assertFalse(valid_angle(65485))
    def test_diff(self):
        self.assertEqual(angle_diff(350, 10), -20)
        self.assertEqual(angle_diff(10, 350), 20)
        self.assertEqual(angle_diff(15, 309), 66)
        self.assertEqual(angle_diff(100, 100), 0)
    def test_hand_end(self):
        for deg, (x, y) in [(0, (0, -10)), (90, (10, 0)), (180, (0, 10)), (270, (-10, 0))]:
            ex, ey = hand_end(0, 0, 10, deg)
            self.assertAlmostEqual(ex, x); self.assertAlmostEqual(ey, y)

class AttitudeTest(unittest.TestCase):
    V = {"Setpoint_atitude": 15, "Esforço PID": 0, "Azimute satélite": 309, "Vel. angular Azim.": 2}
    def test_sem_dados(self):
        a = Attitude()
        self.assertEqual(a.legend(100.0), {"setpoint": "—", "position": "—", "velocity": "—", "diff": "—", "stale": None})
    def test_valores(self):
        a = Attitude(); a.update(100.0, self.V)
        self.assertEqual(a.legend(101.0), {"setpoint": "15°", "position": "309°", "velocity": "+2 °/s", "diff": "+66°", "stale": None})
    def test_invalido_mantem_ultimo_valido(self):
        a = Attitude(); a.update(100.0, self.V)
        a.update(101.0, dict(self.V, **{"Azimute satélite": 65485}))
        leg = a.legend(101.0)
        self.assertEqual(leg["position"], "inválido (65485)")
        self.assertEqual(leg["diff"], "—")
        self.assertEqual(a.last_valid_position, 309)
    def test_velocidade_negativa(self):
        a = Attitude(); a.update(100.0, dict(self.V, **{"Vel. angular Azim.": -3}))
        self.assertEqual(a.legend(100.0)["velocity"], "-3 °/s")
    def test_parado(self):
        a = Attitude(); a.update(100.0, self.V)
        self.assertFalse(a.is_stale(105.0))
        self.assertTrue(a.is_stale(106.0))
        self.assertEqual(a.legend(106.2)["stale"], "sem dados há 6 s")
```

- [ ] **Step 2:** `python3 -m unittest test_attitude` → FAIL (módulo não existe).
- [ ] **Step 3:** Implementar `attitude.py`. `diff` é "—" se setpoint ou posição atual estiver inválido/ausente; formato com sinal `f"{d:+d}°"`. `stale` usa `int(now - last_t)`.
- [ ] **Step 4:** `python3 -m unittest` → todos passam.
- [ ] **Step 5:** Commit `Lógica do relógio de atitude`.

### Task 3: Painel do relógio no dashboard

**Files:**
- Modify: `dashboard.py` (`CHARTS`, nova classe `ClockPanel`, `App.__init__`)
- Test: `test_clock_panel.py`

**Interfaces:**
- Consumes: `Attitude`, `hand_end`, `STALE_S` de `attitude.py`.
- Produces: `class ClockPanel(tk.Frame)`: `__init__(master, compact=False)`, `can_ids() -> {0x408A2}`, `push(can_id, t, values)`, `redraw(now)`, `clear()` — mesma interface do `XYChart`.

- [ ] **Step 1: Teste (com Tk real, pula se não houver display)**

```python
@unittest.skipUnless(os.environ.get("DISPLAY"), "precisa de display")
class ClockPanelTest(unittest.TestCase):
    def test_ponteiros_e_legenda(self):
        root = tk.Tk(); root.geometry("400x400")
        p = ClockPanel(root); p.pack(fill="both", expand=True); root.update()
        p.push(0x408A2, 100.0, {"Setpoint_atitude": 90, "Esforço PID": 0,
                                "Azimute satélite": 0, "Vel. angular Azim.": 2})
        p.redraw(100.5); root.update()
        c = p.canvas
        cx, cy, *_ = p._geom
        tx, ty = c.coords(p._target)[2:]      # ponta do vermelho: à direita (90°)
        self.assertGreater(tx, cx + 10); self.assertAlmostEqual(ty, cy, delta=1)
        px, py = c.coords(p._current)[2:]     # ponta do branco: para cima (0°)
        self.assertLess(py, cy - 10); self.assertAlmostEqual(px, cx, delta=1)
        self.assertEqual(p._labels["setpoint"].cget("text"), "90°")
        p.redraw(106.5); root.update()        # parado
        self.assertEqual(c.itemcget(p._target, "fill"), MUTED)
        root.destroy()
```

- [ ] **Step 2:** `python3 -m unittest test_clock_panel` → FAIL (ClockPanel não existe).
- [ ] **Step 3:** Implementar `ClockPanel`: legenda no topo (4 linhas: Setpoint_atitude, Posição atual, Velocidade angular, Diferença + linha de aviso "sem dados há X s"), Canvas abaixo com o mostrador desenhado em `<Configure>` (círculo, 12 marcas, rótulos `30°`…`360°`); ponteiros como `create_line` (vermelho largura 4, ~55% do raio; branco largura 3, ~85% do raio) movidos com `coords` no `redraw`. `self._geom = (cx, cy, r)`. Ponteiro oculto enquanto não houver ângulo válido.
- [ ] **Step 4:** Em `CHARTS`, remover o 2º painel e a série `RefSpeed Roda Reação`; em `App.__init__`, o painel da direita vira `ClockPanel` com título "Atitude" e subtítulo "vermelho = Setpoint_atitude · branco = posição atual (408A2)"; botão Limpar chama `clear`.
- [ ] **Step 5:** `python3 -m unittest` → todos passam; render em 800x436 (modo compacto) e 1500x880 conferido por captura de tela.
- [ ] **Step 6:** Commit `Relógio de atitude no lugar de "Painéis solares e atitude"`.

### Task 4: Node-RED do Raspberry e entrega

**Files:**
- Modify: `nodeRED-rasp/gerar_fluxo_rasp.py` (FUNC_DECODIFICAR; template da tabela), `nodeRED-rasp/README.md`, `dashboardPython/README.md`

- [ ] **Step 1:** No decodificador, `canId_13`: converter para int16 só `canData_01` e `canData_03` (`canId_5` continua os 4). Na tabela, trocar o rótulo `RefSpeed Roda Reação:` por `Setpoint_atitude:`.
- [ ] **Step 2:** Gerar o fluxo, conferir fios/sintaxe, implantar no Pi; LoRa falso enviando `408A2` com setpoint 300 e azimute variando (inclui 65485 de vez em quando e uma pausa > 5 s); captura de tela do relógio no Pi e da tabela do Node-RED.
- [ ] **Step 3:** READMEs (decodificação do 408A2, relógio); commit no repositório do dashboard; deixar o Pi com `/dev/ttyUSB0` e sem arquivos de teste.
