"""Gera o fluxo do Raspberry (fluxoCubesat-rasp.json) a partir de fluxoCubesatNODE.txt.

O que muda em relação ao fluxo original:
- O módulo LoRa (serial FTDI) substitui o ChirpStack nos dois sentidos:
  * comandos dos botões (atitude e deployer): saem com as mensagens do
    comandos.txt (o mesmo do dashboard Python), uma linha com \\r\\n;
  * telemetria: cada linha CAN recebida ({0001F864:...}) é decodificada pelo
    mesmo CUBESATProtocolParser do codec1.txt e entra no fluxo antigo como se
    viesse do ChirpStack (porta 250); linhas de texto equivalem à porta 251.
- O Node-RED é o dono da serial: cada linha recebida também é repassada ao
  dashboard Python pela porta TCP 5555; pela mesma conexão o dashboard manda os
  comandos (só de 127.0.0.1 e só as mensagens do comandos.txt), que o
  Node-RED põe na serial.
- MQTT (ChirpStack) e envio ao Supabase desativados: nada sai do Raspberry
  (o mapa ADS-B só é carregado da internet se houver rede).
- Grupo "TCC Samuel" removido (não é mais usado), com os nós que só serviam a ele.
- Tela para o display de 800x480 (rolagem vertical, sem rolagem lateral),
  seguindo as imagens de referência do painel antigo (ParaSerVisualizado1/2.png).
- Nós decode/encode (pacote node-red-contrib-crypto-js) viram nós function.

Uso:  python3 gerar_fluxo_rasp.py [--porta /dev/ttyUSB0] [--saida fluxoCubesat-rasp.json]
"""
import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
ORIGINAL = AQUI / "fluxoCubesatNODE.txt"
CODEC = AQUI / "codec1.txt"
COMANDOS_TXT = AQUI.parent / "comandos.txt"   # mensagens dos botões (o mesmo do dashboard)

sys.path.insert(0, str(AQUI.parent))
from commands import NOMES, load_commands  # noqa: E402

PORTA_SERIAL = "/dev/ttyUSB0"
BAUD = "115200"
PORTA_TCP = "5555"
PERIODO_TELA_MS = 2000      # tabela, mostradores e gráficos: no máximo 1 atualização a cada 2 s

# ---- ids do fluxo original
TAB_FLUXO = "9b6df1cc.293a"          # aba do editor "CubeSat"
UI_TAB = "9c001fa0.24b65"            # aba do painel "CubeSat"
G_MAUASAT = "2960ec4d.fdf824"        # grupo "CubeDesign MauáSat"
G_TCC = "eb54476d.d72fc8"            # grupo "Tcc Samuel-J_Socio" (removido)
GRUPO_DIALOGO = "9f8692ce.c265c"     # janela de PIN (pin_insert2)
MQTT_OUT_MAUASAT = "bc2c8974.279618"
CODEC_DECODEDDATA = "708a11ea.8adf3"  # função "DecodedData" do codec1.txt

# ---- ids novos
G_RADIO = "cubesat.grp.radio"
SERIAL_CFG = "cubesat.serialport"
ENVIAR = "cubesat.enviar"
DECODIFICAR = "cubesat.decodificar"
RITMO_TELA = "cubesat.ritmo.tela"
RITMO_ATUALIZADO = "cubesat.ritmo.atualizado"

# cores iguais às do dashboard Python
TEMA = {
    "base-font": "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Oxygen-Sans,Ubuntu,Cantarell,Helvetica Neue,sans-serif",
    "base-color": "#4fa3ff",
    "page-backgroundColor": "#0f1419",
    "page-titlebar-backgroundColor": "#171d24",
    "page-sidebar-backgroundColor": "#171d24",
    "group-backgroundColor": "#171d24",
    "group-textColor": "#4fa3ff",
    "group-borderColor": "#2b3540",
    "widget-textColor": "#e6edf3",
    "widget-backgroundColor": "#1e262f",
}

# Layout do grupo "CubeDesign MauáSat" (14 unidades = 800 px; unidade = 48 px + 6 px).
# Identificação: (tipo, rótulo/título) -> (ordem, largura, altura)
LAYOUT = {
    ("ui_gauge", "ultimo envio"):        (1, 3, 3),
    ("ui_gauge", "atualizado a"):        (2, 3, 3),
    ("ui_button", "LIGA ATITUDE"):       (3, 4, 1),
    ("ui_button", "DESLIGA ATITUDE"):    (4, 4, 1),
    ("ui_button", "ACIONA DEPLOYER"):    (5, 4, 1),
    ("ui_button", "DESLIGA DEPLOYER"):   (6, 4, 1),
    ("ui_text_input", "Send Setpoint_atitude (int 0 a 359°)"): (7, 4, 1),
    ("ui_button", "Update"):             (8, 4, 1),
    ("ui_gauge", "V BATERIA"):           (9, 3, 3),
    ("ui_chart", "Volts"):               (10, 4, 3),
    ("ui_gauge", "Temperatura"):         (11, 3, 3),
    ("ui_chart", "°C"):                  (12, 4, 3),
    ("ui_template", "mensagem"):         (13, 14, 1),   # texto da porta 251
    ("ui_template", "GlobalCelescData Viewer"): (14, 14, 0),
}

FUNC_ENVIAR = r"""// Manda o comando pelo módulo LoRa (serial FTDI), com a mensagem do
// comandos.txt (copiada aqui por gerar_fluxo_rasp.py). Os botões do painel
// ainda montam o JSON do ChirpStack; os bytes dizem qual botão foi:
//   00 05 + setpoint = LIGA ATITUDE      00 04 = DESLIGA ATITUDE
//   00 01 = ACIONA DEPLOYER              00 02 = DESLIGA DEPLOYER
// {SETPOINT} vira o setpoint em hex, 4 dígitos (300 -> 012C).
const COMANDOS = %COMANDOS%;
const BOTOES = {5: 'LIGA_ATITUDE', 4: 'DESLIGA_ATITUDE', 1: 'ACIONA_DEPLOYER', 2: 'DESLIGA_DEPLOYER'};
const texto = String(msg.payload).trim();
if (!texto) return null;
const hora = new Date().toLocaleTimeString('pt-BR');
const nao = (rotulo, motivo) => {
    node.status({fill: 'red', shape: 'ring', text: `${hora} ${rotulo} NÃO enviado`});
    return [null, {payload: `${hora} · ${rotulo} NÃO enviado: ${motivo}`}];
};
let bytes;
try { bytes = Buffer.from(JSON.parse(texto).data || '', 'base64'); }
catch (e) { return nao('comando', 'formato desconhecido'); }
const nome = bytes.length >= 2 && bytes[0] === 0 ? BOTOES[bytes[1]] : undefined;
if (!nome) return nao('comando', 'desconhecido (' + bytes.toString('hex').toUpperCase() + ')');
const rotulo = nome.replace('_', ' ');
let linha = COMANDOS[nome] || '';
if (!linha) return nao(rotulo, 'não configurado no comandos.txt');
let sp = null;
if (linha.includes('{SETPOINT}')) {
    const valido = v => Number.isInteger(v) && v >= 0 && v <= 359;
    if (nome === 'LIGA_ATITUDE') {
        sp = bytes.length >= 4 ? (bytes[2] << 8 | bytes[3]) : NaN;
        // não manda um ângulo qualquer ao satélite
        if (!valido(sp)) return nao(rotulo, 'digite o Setpoint_atitude (0 a 359) e aperte Enter');
    } else {
        const g = global.get("GlobalCubesat.azimute_set");
        sp = (g === undefined || g === null || String(g).trim() === '') ? NaN : Number(g);
        if (!valido(sp)) sp = 16;   // o setpoint não importa aqui (16 = valor dos exemplos)
    }
    linha = linha.split('{SETPOINT}').join(sp.toString(16).toUpperCase().padStart(4, '0'));
}
const resumo = `${rotulo}${sp === null ? '' : ' ' + sp + '°'} · ${linha}`;
node.status({fill: 'green', shape: 'dot', text: `${hora} ${resumo}`});
return [{payload: linha + "\r\n"}, {payload: `${hora} · ${resumo}`}];
"""

FUNC_CMD_DASHBOARD = r"""// Comando do dashboard Python (mesma conexão TCP pela qual ele recebe as
// linhas). Aceito só do próprio Raspberry e só se for exatamente uma das
// mensagens do comandos.txt (com setpoint de 0 a 359); o resto é ignorado.
const COMANDOS = %COMANDOS%;
const locais = ['127.0.0.1', '::1', '::ffff:127.0.0.1'];
const linha = String(msg.payload).trim();
const hora = new Date().toLocaleTimeString('pt-BR');
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
let achado = null;
for (const [nome, modelo] of Object.entries(COMANDOS)) {
    if (!modelo) continue;
    const re = new RegExp('^' + modelo.split('{SETPOINT}').map(esc).join('([0-9A-F]{4})') + '$');
    const m = re.exec(linha);
    if (!m) continue;
    const sps = m.slice(1).map(h => parseInt(h, 16));
    if (sps.some(v => v > 359) || new Set(sps).size > 1) continue;
    achado = {nome, sp: sps.length ? sps[0] : null};
    break;
}
if (!locais.includes(msg.ip) || !achado) {
    if (linha) {
        node.warn(`comando recusado (de ${msg.ip}): ${linha}`);
        node.status({fill: 'red', shape: 'ring', text: `${hora} recusado: ${linha}`});
    }
    return null;
}
const resumo = `${achado.nome.replace('_', ' ')}${achado.sp === null ? '' : ' ' + achado.sp + '°'} ` +
               `(dashboard) · ${linha}`;
node.status({fill: 'green', shape: 'dot', text: `${hora} ${resumo}`});
return [{payload: linha + "\r\n"}, {payload: `${hora} · ${resumo}`}];
"""


def func_enviar(cmds):
    """Código do nó "Enviar pelo LoRa" com as mensagens do comandos.txt."""
    return FUNC_ENVIAR.replace("%COMANDOS%", json.dumps(cmds, ensure_ascii=False))


def func_cmd_dashboard(cmds):
    """Código do nó que aceita os comandos do dashboard Python."""
    return FUNC_CMD_DASHBOARD.replace("%COMANDOS%", json.dumps(cmds, ensure_ascii=False))


FUNC_REPASSE = r"""// Repassa cada linha recebida do LoRa ao dashboard Python (porta TCP).
let linha = Buffer.isBuffer(msg.payload) ? msg.payload.toString('latin1')
                                         : String(msg.payload);
linha = linha.replace(/[\r\n]+$/, '');
if (!linha) return null;
msg.payload = linha + "\n";
return msg;
"""

FUNC_ESTADO = r"""// Estado da serial do LoRa, em português, para o painel.
const s = msg.status || {};
if (s.fill === 'green') msg.payload = 'conectado';
else if (s.fill === 'red') msg.payload = 'desconectado — conecte o USB';
else msg.payload = s.text || '—';
return msg;
"""

FUNC_DECODIFICAR = r"""// Linha recebida do LoRa (serial) -> a mesma mensagem que o fluxo antigo
// recebia do ChirpStack. Saída 1: CAN decodificado (porta 250);
// saída 2: linha de texto, ex. "Mauasat online Compiled on ..." (porta 251).
// O CUBESATProtocolParser abaixo é o do codec1.txt, sem alterações.
%PARSER%

const RE = /\{\s*([0-9A-Fa-f]{1,8})[:\s]\s*((?:[0-9A-Fa-f]{2}\s*){8})\}/;
const DEV = "0005168000136ee4";
let linha = Buffer.isBuffer(msg.payload) ? msg.payload.toString('latin1') : String(msg.payload);
linha = linha.replace(/[\r\n]+$/, '').trim();
if (!linha) return null;
if (!global.get("msg_anterior_cubesat")) {
    global.set("msg_anterior_cubesat", {decodedData: {}, lista: []});
}
const m = linha.match(RE);
if (!m) {
    if (!/[A-Za-z]{3}/.test(linha)) return null;      // ruído / linha cortada
    return [null, {payload: linha, props: {devEui: DEV, port: 251}}];
}
const id = m[1].replace(/^0+(?=.)/, '').toUpperCase();   // 0001F864 -> 1F864
const hex = m[2].replace(/\s+/g, '').toUpperCase();
let dec;
try { dec = CUBESATProtocolParser(JSON.stringify([id + ":" + hex])); }
catch (e) { return null; }
if (!Object.keys(dec).length) return null;               // ID que o painel não usa
// mesma leitura do dashboard Python:
// 1F864: os 4 campos int16 big-endian com sinal;
// 408A2 (ordem do mapa CAN novo): Esforço PID (00), Setpoint_atitude (01) sem
//        sinal (0 a 359°), Azimute satelital (02, -180 a +180°)
//        e velocidade angular (03, °/s); os outros três com sinal
const COM_SINAL = {canId_5: ["canData_00", "canData_01", "canData_02", "canData_03"],
                   canId_13: ["canData_00", "canData_02", "canData_03"]};
for (const [k, campos] of Object.entries(COM_SINAL)) {
    if (!dec[k]) continue;
    for (const c of campos) {
        if (dec[k][c] >= 0x8000) dec[k][c] -= 0x10000;
    }
}
return [{payload: linha, decodedData: dec, props: {devEui: DEV, port: 250}}, null];
"""

# manda no máximo 1 mensagem por período, sempre a mais recente (não perde a última)
FUNC_RITMO = r"""const PERIODO = %MS%;
context.set('ultima', msg);
if (!context.get('timer')) {
    const tick = () => {
        const u = context.get('ultima');
        if (u) {
            context.set('ultima', null);
            node.send(u);
            context.set('timer', setTimeout(tick, PERIODO));
        } else {
            context.set('timer', null);
        }
    };
    tick();
}
return null;
"""
FIM_RITMO = "clearTimeout(context.get('timer'));\ncontext.set('timer', null);\n"


def extrair_parser():
    """CUBESATProtocolParser do nó 'DecodedData' do codec1.txt."""
    codec = {n["id"]: n for n in json.loads(CODEC.read_text())}
    f = codec[CODEC_DECODEDDATA]["func"]
    ini = f.index("function CUBESATProtocolParser")
    fim = f.index("function RFSENSEProtocolParser")
    return f[ini:fim].rstrip()


def podar(nos, remover):
    """Remove os nós em `remover` e, repetidamente, os nós de processamento que
    ficaram sem destino nem origem por causa disso (só serviam aos removidos)."""
    tipos_meio = {"function", "inject", "json", "decode", "encode", "change", "switch"}
    while True:
        vivos = {n["id"] for n in nos if n["id"] not in remover}
        for n in nos:
            n_wires = n.get("wires", [])
            for i, saida in enumerate(n_wires):
                n_wires[i] = [w for w in saida if w in vivos]
        tem_entrada = {w for n in nos if n["id"] in vivos for s in n.get("wires", []) for w in s}
        novos = set()
        for n in nos:
            if n["id"] in remover:
                continue
            sem_saida = not any(n.get("wires", []))
            sem_entrada = n["id"] not in tem_entrada
            if n["type"] in tipos_meio - {"inject"} and (sem_saida or sem_entrada):
                novos.add(n["id"])
            if n["type"] == "inject" and sem_saida:
                novos.add(n["id"])
            if n["type"] in ("mqtt in",) and sem_saida:
                novos.add(n["id"])
            if n["type"] in ("mqtt out",) and n["id"] not in tem_entrada:
                novos.add(n["id"])
        if not novos:
            return [n for n in nos if n["id"] not in remover]
        remover |= novos


def gerar(porta, cmds):
    nos = json.loads(ORIGINAL.read_text())
    por_id = {n["id"]: n for n in nos}

    # ---------------------------------------------------------- limpeza
    # nada sai do Raspberry; o envio ADS-B ao Supabase e o debug ficam desligados
    for n in nos:
        if n["type"] in ("mqtt in", "mqtt out", "http request"):
            n["d"] = True
        if n["type"] == "function" and n.get("name") == "ADBS":
            n["d"] = True
        if n["type"] == "debug":
            n["active"] = False
    # TCC Samuel: grupo, widgets e tudo que só servia a eles
    removidos_antes = {n["id"] for n in nos}
    remover = {G_TCC} | {n["id"] for n in nos if n.get("group") == G_TCC}
    nos = podar(nos, remover)
    removidos = removidos_antes - {n["id"] for n in nos}
    por_id = {n["id"]: n for n in nos}

    # ---------------------------------------------------------- comandos -> serial
    for n in nos:
        for saida in n.get("wires", []):
            if MQTT_OUT_MAUASAT in saida and ENVIAR not in saida:
                saida.append(ENVIAR)

    # janela de PIN: o template original ignorava o primeiro "show" (para não
    # abrir sozinho quando a página recarrega e reenvia a última mensagem). No
    # quiosque a página carrega uma vez, então o 1º toque em Update era perdido.
    pin = next(n for n in nos if n.get("name") == "pin_insert2")
    antes = ('case "show":\n                   if(scope.inited){\n'
             '                        scope.payload = data.payload;\n'
             '                        scope.showDialog();\n                   }\n'
             '                   else\n                        scope.inited = true;\n')
    assert antes in pin["format"], "template do PIN mudou: revisar gerar_fluxo_rasp.py"
    pin["format"] = pin["format"].replace(antes, (
        'case "show":\n'
        '                   // (quiosque) abre sempre: resendOnRefresh desligado\n'
        '                   scope.payload = data.payload;\n'
        '                   scope.showDialog();\n'))
    pin["resendOnRefresh"] = False
    # com o tema escuro, os dígitos do PIN herdavam texto branco sobre o fundo
    # branco da janela (ficavam invisíveis): texto escuro dentro da janela
    assert "</style>" in pin["format"]
    pin["format"] = pin["format"].replace("</style>", (
        "/* (quiosque) tema escuro: texto escuro dentro da janela branca */\n"
        ".dialog_content .number_placeholder { color: #000 !important; }\n"
        "</style>"), 1)

    # ---------------------------------------------------------- telemetria
    sel = next(n for n in nos if n.get("name", "").startswith("Select Device"))
    storage = next(n for n in nos if n.get("name") == "storage")
    porta251 = next(n for n in nos if n.get("name") == "port 251")
    cont_atualizado = next(  # "Contagem Regressiva" que alimenta o mostrador "atualizado a"
        n for n in nos if n.get("name") == "Contagem Regressiva"
        and any(por_id[w].get("title") == "atualizado a" for s in n["wires"] for w in s))

    # Select Device -> "atualizado a": no máximo 1 vez por segundo
    sel["wires"] = [[RITMO_ATUALIZADO if w == cont_atualizado["id"] else w for w in sel["wires"][0]]]
    # storage -> tabela/mostradores/gráficos: no máximo 1 vez a cada PERIODO_TELA_MS
    storage_destinos = [w for w in storage["wires"][0]
                        if por_id[w]["type"] in ("function", "ui_template")
                        and not por_id[w].get("d")]
    storage["wires"] = [[RITMO_TELA]]
    # envio ADS-B ao Supabase: fora do fluxo do Raspberry (os nós ADBS guardam a
    # chave secreta do Supabase em texto puro e não seriam usados)
    tirar = {n["id"] for n in nos if n.get("name") == "ADBS" or n["type"] == "http request"}
    nos = [n for n in nos if n["id"] not in tirar]
    removidos |= tirar
    por_id = {n["id"]: n for n in nos}
    # v_bat/temp: não quebrar enquanto o EPS 5F8B4 ainda não chegou
    for n in nos:
        if n.get("name") in ("v_bat", "temp"):
            n["func"] = n["func"].replace("msg.decodedData.canId_16.canData_0",
                                          "msg.decodedData.canId_16?.canData_0", 1)

    # template da mensagem de texto (porta 251): rótulo para o LAYOUT
    msg_tpl = por_id[porta251["wires"][0][0]]
    msg_tpl["name"] = "mensagem"

    # tabela: sem scripts da internet, cabe em 800 px, mapa só com internet
    tab = next(n for n in nos if n.get("name") == "GlobalCelescData Viewer")
    f = tab["format"]
    for script in ('<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>',
                   '<script src="https://cdn.jsdelivr.net/npm/sockjs-client@1/dist/sockjs.min.js"></script>'):
        assert script in f, script
        f = f.replace(script, "")
    css_antes = "table {\n            font-family: sans-serif;"
    assert css_antes in f
    f = f.replace(css_antes, "table {\n            table-layout: fixed; overflow-wrap: anywhere;\n"
                             "            font-family: sans-serif;")
    f = f.replace("font-size: 14px;", "font-size: 11px;", 1)
    f = f.replace("padding: 6px;", "padding: 3px 2px;", 1)
    img_antes = ('<img src="https://mediaserver.maua.br/cubesat/latestTrajectory" '
                 'style="display: block; margin-left: auto; margin-right: auto; width: 500px; height: auto;" />')
    assert img_antes in f
    f = f.replace(img_antes, (
        '<img class="cubesat-mapa" src="https://mediaserver.maua.br/cubesat/latestTrajectory" '
        'style="display: block; margin: auto; width: 100%; height: auto;" '
        'onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';" '
        'onload="this.style.display=\'block\'; this.nextElementSibling.style.display=\'none\';" />'
        '<div style="display: none; padding: 20px; color: #8b98a5;">'
        'mapa indisponível sem internet</div>'))
    f = f.replace("</table>", """</table>
<script>
// recarrega o mapa a cada 60 s (quando houver internet)
setInterval(function () {
    document.querySelectorAll('img.cubesat-mapa').forEach(function (i) {
        i.src = 'https://mediaserver.maua.br/cubesat/latestTrajectory?t=' + Date.now();
    });
}, 60000);
</script>""", 1)
    # o fluxo base já precisa ter a ordem nova do 408A2 e o "angulo" do 520B6
    # (NovoMapaCANParaAjusteCodigo.png); com o fluxo antigo, pare aqui
    for rotulo in ("Esforço PID: {{msg.decodedData.canId_13.canData_00}}",
                   "Setpoint_atitude: {{msg.decodedData.canId_13.canData_01}}",
                   "angulo: {{msg.decodedData.canId_18.canData_06}}"):
        assert rotulo in f, f"fluxo base desatualizado: falta {rotulo!r}"
    tab["format"] = f

    # ---------------------------------------------------------- tela
    por_id[UI_TAB].update(name="CubeSat", order=1, hidden=False, disabled=False)
    por_id[G_MAUASAT].update(width="14", name="CubeDesign MauáSat")
    por_id[GRUPO_DIALOGO]["tab"] = UI_TAB
    movidos = set()
    for n in nos:
        chave = (n["type"], n.get("title") or n.get("label") or n.get("name"))
        if n["type"] == "ui_chart":
            chave = (n["type"], n.get("name"))
        if chave in LAYOUT and not n.get("d"):
            ordem, w, h = LAYOUT[chave]
            n.update(group=G_MAUASAT, order=ordem, width=str(w), height=str(h))
            movidos.add(chave)
    faltando = set(LAYOUT) - movidos
    assert not faltando, f"widgets não encontrados no fluxo: {faltando}"

    y0 = 1200
    novos = [
        {"id": "cubesat.ui_base", "type": "ui_base",
         "theme": {"name": "theme-dark",
                   "themeState": {k: {"value": v, "edited": True} for k, v in TEMA.items()},
                   "angularTheme": {"primary": "blue", "accents": "blue", "warn": "red",
                                    "background": "grey", "palette": "dark"}},
         "site": {"name": "CubeSat", "hideToolbar": "true", "allowSwipe": "false",
                  "lockMenu": "false", "allowTempTheme": "true",
                  "dateFormat": "DD/MM/YYYY",
                  "sizes": {"sx": 48, "sy": 48, "gx": 6, "gy": 6,
                            "cx": 6, "cy": 6, "px": 0, "py": 0}}},
        {"id": G_RADIO, "type": "ui_group", "name": "Rádio LoRa",
         "tab": UI_TAB, "order": 4, "disp": True, "width": "14", "collapse": False,
         "className": ""},

        # ---- serial do módulo LoRa (FTDI)
        {"id": SERIAL_CFG, "type": "serial-port", "name": "LoRa FTDI",
         "serialport": porta, "serialbaud": BAUD, "databits": 8, "parity": "none",
         "stopbits": 1, "waitfor": "", "dtr": "none", "rts": "none", "cts": "none",
         "dsr": "none", "newline": "\\n", "bin": "false", "out": "char",
         "addchar": "", "responsetimeout": 10000},

        # ---- envio dos comandos
        {"id": ENVIAR, "type": "function", "z": TAB_FLUXO, "name": "Enviar pelo LoRa",
         "func": func_enviar(cmds), "outputs": 2, "noerr": 0, "x": 2420, "y": y0,
         "wires": [["cubesat.serial.out"], ["cubesat.txt.ultimo"]]},
        {"id": "cubesat.serial.out", "type": "serial out", "z": TAB_FLUXO,
         "name": "LoRa (enviar)", "serial": SERIAL_CFG, "x": 2660, "y": y0 - 20,
         "wires": []},
        {"id": "cubesat.txt.ultimo", "type": "ui_text", "z": TAB_FLUXO,
         "group": G_RADIO, "order": 2, "width": "9", "height": "1", "name": "",
         "label": "Último comando", "format": "{{msg.payload}}",
         "layout": "row-spread", "className": "", "style": False,
         "x": 2660, "y": y0 + 20, "wires": []},

        # ---- recepção: decodifica para o painel e repassa ao dashboard Python
        {"id": "cubesat.serial.in", "type": "serial in", "z": TAB_FLUXO,
         "name": "LoRa (receber)", "serial": SERIAL_CFG, "x": 2180, "y": y0 + 100,
         "wires": [["cubesat.repasse", DECODIFICAR]]},
        {"id": "cubesat.repasse", "type": "function", "z": TAB_FLUXO,
         "name": "linha -> dashboard Python", "func": FUNC_REPASSE, "outputs": 1,
         "noerr": 0, "x": 2420, "y": y0 + 100, "wires": [["cubesat.tcp"]]},
        # a porta 5555 é aberta pelo "tcp in" (comandos do dashboard); o "tcp
        # out" em modo reply escreve em todas as conexões dele (sem _session)
        {"id": "cubesat.tcp", "type": "tcp out", "z": TAB_FLUXO,
         "name": f"dashboard Python (porta {PORTA_TCP})", "host": "", "port": "",
         "beserver": "reply", "base64": False, "end": False, "tls": "",
         "x": 2680, "y": y0 + 100, "wires": []},
        {"id": "cubesat.tcp.in", "type": "tcp in", "z": TAB_FLUXO,
         "name": f"comandos do dashboard Python (porta {PORTA_TCP})", "server": "server",
         "host": "", "port": PORTA_TCP, "datamode": "stream", "datatype": "utf8",
         "newline": "\\n", "topic": "", "trim": False, "base64": False, "tls": "",
         "x": 2180, "y": y0 + 40, "wires": [["cubesat.cmd.dashboard"]]},
        {"id": "cubesat.cmd.dashboard", "type": "function", "z": TAB_FLUXO,
         "name": "comando do dashboard (só 2004, só local)", "func": func_cmd_dashboard(cmds),
         "outputs": 2, "noerr": 0, "x": 2440, "y": y0 + 40,
         "wires": [["cubesat.serial.out"], ["cubesat.txt.ultimo"]]},
        {"id": DECODIFICAR, "type": "function", "z": TAB_FLUXO,
         "name": "linha CAN -> decodedData (CUBESATProtocolParser)",
         "func": FUNC_DECODIFICAR.replace("%PARSER%", extrair_parser()),
         "outputs": 2, "noerr": 0, "x": 2440, "y": y0 + 160,
         "wires": [[sel["id"]], [porta251["id"], RITMO_ATUALIZADO]]},
        {"id": RITMO_ATUALIZADO, "type": "function", "z": TAB_FLUXO,
         "name": "no máx. 1/s", "func": FUNC_RITMO.replace("%MS%", "1000"),
         "finalize": FIM_RITMO, "outputs": 1, "noerr": 0, "x": 2700, "y": y0 + 200,
         "wires": [[cont_atualizado["id"]]]},
        {"id": RITMO_TELA, "type": "function", "z": TAB_FLUXO,
         "name": f"no máx. 1 a cada {PERIODO_TELA_MS // 1000} s",
         "func": FUNC_RITMO.replace("%MS%", str(PERIODO_TELA_MS)),
         "finalize": FIM_RITMO, "outputs": 1, "noerr": 0, "x": 2700, "y": y0 + 240,
         "wires": [storage_destinos]},

        # ---- estado da serial no painel
        {"id": "cubesat.estado", "type": "status", "z": TAB_FLUXO,
         "name": "estado da serial", "scope": ["cubesat.serial.in"],
         "x": 2180, "y": y0 + 300, "wires": [["cubesat.estado.fmt"]]},
        {"id": "cubesat.estado.fmt", "type": "function", "z": TAB_FLUXO,
         "name": "estado em português", "func": FUNC_ESTADO, "outputs": 1, "noerr": 0,
         "x": 2420, "y": y0 + 300, "wires": [["cubesat.txt.radio"]]},
        {"id": "cubesat.txt.radio", "type": "ui_text", "z": TAB_FLUXO,
         "group": G_RADIO, "order": 1, "width": "5", "height": "1", "name": "",
         "label": "Rádio", "format": "{{msg.payload}}", "layout": "row-spread",
         "className": "", "style": False, "x": 2640, "y": y0 + 300, "wires": []},
        {"id": "cubesat.comentario", "type": "comment", "z": TAB_FLUXO,
         "name": f"LoRa pela serial FTDI ({porta}, {BAUD}) — gerado por gerar_fluxo_rasp.py",
         "info": "Comandos dos botões e do dashboard Python saem pela serial; "
                 "linhas recebidas são decodificadas para o painel e repassadas "
                 f"ao dashboard Python pela porta TCP {PORTA_TCP}.",
         "x": 2300, "y": y0 - 80, "wires": []},
    ]
    return nos + novos, removidos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--porta", default=PORTA_SERIAL, help="porta serial do LoRa")
    ap.add_argument("--saida", default=str(AQUI / "fluxoCubesat-rasp.json"))
    ap.add_argument("-v", action="store_true", help="lista os nós removidos")
    a = ap.parse_args()
    cmds = load_commands(COMANDOS_TXT)
    nos, removidos = gerar(a.porta, cmds)
    Path(a.saida).write_text(json.dumps(nos, ensure_ascii=False, indent=1))
    print(f"gerado: {a.saida} (serial {a.porta} @ {BAUD}; {len(removidos)} nós removidos)")
    print(f"mensagens dos botões ({COMANDOS_TXT.name}):")
    for nome in NOMES:
        print(f"  {nome:17} {cmds[nome] or '(vazio: botão não envia)'}")
    if a.v:
        orig = {n["id"]: n for n in json.loads(ORIGINAL.read_text())}
        for i in sorted(removidos):
            n = orig[i]
            print("  removido:", n["type"], n.get("name") or n.get("label") or n.get("title") or "")


if __name__ == "__main__":
    main()
