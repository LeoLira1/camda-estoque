"""Aba de Etiquetas — folhas A4 com QR code para colar nos racks do galpão.

A etiqueta é lida pelo app Flutter (repositório `scanner`), que resolve o
código em `mapa_produtos`/`mapa_produtos_codigos` e mostra o saldo somado de
todos os códigos do produto.

Decisões que valem a pena registrar aqui:

1. **Uma etiqueta por PRODUTO, não por linha de estoque_mestre.** Um produto
   da CAMDA pode ter mais de um código ativo ('254185' e 'US254185'), cada um
   com sua linha e seu saldo. Gerar uma folha por linha colocaria duas
   etiquetas do mesmo produto no mesmo rack — alguém conta o produto duas
   vezes no inventário. O agrupamento usa `get_produtos_mapa` (db_mapa), que
   devolve o conjunto completo de códigos por `produto_id`.

   Por que `get_produtos_mapa` e não `get_codigos_produto`: as duas têm
   semântica idêntica (principal + secundários, normalizados), mas
   `get_codigos_produto` roda 2 queries por produto e chama
   `ensure_mapa_tables`, que faz DDL + COMMIT. Esta aba é somente leitura e
   percorre centenas de produtos — `get_produtos_mapa` resolve tudo em 2
   queries, sem escrever nada.

2. **O QR carrega só o código, como texto puro.** Sem URL e sem encurtador:
   o app consulta o banco por conta própria (funciona sem internet), nenhum
   domínio pode expirar e derrubar as etiquetas do galpão inteiro, e o
   conteúdo curto gera um símbolo de 21×21 módulos — quadrados grandes, lê
   de longe e tolera sujeira.

3. **`micro=False` é obrigatório.** Para entrada numérica curta o segno
   escolheria um Micro QR (M4), que o `mobile_scanner`/ML Kit usado pelo app
   NÃO lê. O símbolo tem que ser QR padrão.

4. **O nome impresso vem de `estoque_mestre.produto` do código que vai no
   QR.** O app (`consulta.dart::montarResultado`) exibe justamente a linha do
   código lido — puxar o nome da mesma linha garante que a folha e a tela
   nunca divergem. `mapa_produtos.nome` só entra quando o código não tem
   linha em estoque_mestre.

5. **Impressão via download de HTML, não `st.components.v1.html`.** O
   componente renderiza num iframe: Ctrl+P imprimiria a página do Streamlit
   inteira (menu, sidebar). O usuário baixa o arquivo, abre no navegador e
   imprime exatamente o que viu.

6. **Tamanho da etiqueta é um preset, não campos numéricos soltos.** Ver
   `_PRESETS`: cada entrada descreve uma folha inteira, e o renderizador de
   grade deriva as medidas da célula da aritmética da folha. Uma folha
   gerada tem sempre UM tamanho só — o preset é escolhido antes de gerar e
   vale para o documento inteiro, então não existe mistura de tamanhos na
   mesma página.
"""

import hashlib
import html as _esc
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime

import pandas as pd
import streamlit as st

from db_mapa import _norm_codigo, get_produtos_mapa

try:
    import segno
    _SEGNO_ERRO = ""
except ImportError as _exc:  # pragma: no cover - ambiente sem a dependência
    segno = None
    _SEGNO_ERRO = str(_exc)


# ── Critérios de lote ─────────────────────────────────────────────────────────
CRIT_FEFO = "Lote de vencimento mais próximo (FEFO)"
CRIT_TODOS = "Uma etiqueta por lote"
CRIT_MANUAL = "Digitar o lote à mão"
CRIT_SEM = "Sem lote (só produto + QR)"

_MAX_ETIQUETAS = 400  # trava de segurança: acima disso é engano de filtro

# ── Presets de tamanho ────────────────────────────────────────────────────────
# Adicionar um tamanho novo = acrescentar UMA entrada aqui, com `modo="grade"`.
# Nada da renderização precisa mudar: `_medidas_grade` deriva a célula da
# aritmética da folha ((folha − 2×margem − gaps) / n) e `_css_grade` emite o CSS
# a partir dela — não há medida escrita à mão em nenhum dos dois. Ex.: um preset
# de 5×5 cm com 12 por folha é colunas=3, linhas=4, qr_mm=50.
#
# Campos:
#   modo           "folha" → uma etiqueta por página, com lote (renderizador
#                            original, `_bloco_etiqueta`)
#                  "grade" → N por página, só QR + nome (`_folhas_grade`)
#   com_lote       se o seletor de critério de lote se aplica a este preset
#   copias         se o campo "cópias por produto" aparece
#   max_etiquetas  trava de segurança (engano de filtro)
#   arquivo        prefixo do nome do arquivo baixado
#   descricao      texto da UI
# Só o modo "grade" usa os campos de medida:
#   folha_mm       (largura, altura) da página em mm — (210, 297) é A4 retrato
#   colunas/linhas, margem_mm, gap_mm, nome_pt
#   qr_mm          lado do QR IMPRESSO, **incluindo** a zona de silêncio de 4
#                  módulos que a norma exige (é o que se mede na folha com a
#                  régua). Numa etiqueta de 30 mm o símbolo em si fica com
#                  ~21,7 mm — módulos de ~1,0 mm, de sobra para leitura de
#                  perto. Não vale reduzir o `border=4` para engordar o
#                  símbolo: a margem branca é o que faz o leitor achar o
#                  código. Se `qr_mm` não couber na célula, é reduzido para a
#                  largura da célula em vez de estourar a folha.
_PRESET_GRANDE = "Etiqueta grande (1 por folha)"
_PRESET_PEQUENA = "Etiqueta pequena (30 por folha)"

_PRESETS = {
    _PRESET_GRANDE: {
        "modo": "folha",
        "com_lote": True,
        "copias": False,
        "max_etiquetas": _MAX_ETIQUETAS,
        "arquivo": "etiquetas",
        "descricao": (
            "Uma folha A4 por etiqueta, com nome, código, validade e o lote em "
            "número grande. QR de ~6,5 cm, para ler de longe no corredor."
        ),
    },
    _PRESET_PEQUENA: {
        "modo": "grade",
        "com_lote": False,
        "copias": True,
        # 30 por folha: 400 etiquetas seriam só 14 folhas, o que tornaria a
        # trava de 400 inútil como proteção contra engano de filtro. O que
        # custa caro aqui é folha impressa, então o teto é ~40 folhas.
        "max_etiquetas": 1200,
        "arquivo": "etiquetas_pequenas",
        "folha_mm": (210, 297),
        "colunas": 5,
        "linhas": 6,
        "margem_mm": 10,
        "gap_mm": 6,
        "qr_mm": 30,
        "nome_pt": 7,
        "descricao": (
            "Grade de 5 × 6 = 30 etiquetas por folha A4 retrato, cada uma com "
            "QR de 30 mm e o nome do produto embaixo. Sem lote e sem validade."
        ),
    },
}

# A coluna PRODUTO da planilha SIG traz o CÓDIGO junto do nome
# ("254185 - HERBICIDA BORAL 500 SC 20L"), e o upload grava a string inteira
# em validade_lotes.produto; estoque_mestre guarda só o nome. Este regex
# captura as duas partes — o resto do app (app_turso._RE_VAL_PREFIX) só
# aproveita o nome, mas o código ali é o que permite casar de forma exata.
_RE_VAL_COD_NOME = re.compile(r"^\s*([A-Z0-9\-]{3,20})\s*[-–]\s*(.+)$", re.IGNORECASE)


def _sem_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _split_produto_validade(produto):
    """'254185 - HERBICIDA BORAL 20L' → ('254185', 'HERBICIDA BORAL 20L').

    Sem prefixo de código devolve (None, texto). A classe de caracteres não
    atravessa espaço, então nome sem código ('ADJUVANTE 2-4D 20L') não é
    confundido com prefixo.
    """
    s = str(produto or "").strip()
    m = _RE_VAL_COD_NOME.match(s)
    if not m:
        return None, s
    return _norm_codigo(m.group(1)), m.group(2).strip()


def _nome_key(nome) -> str:
    """Chave de match validade_lotes ↔ estoque_mestre (sem prefixo/acentos)."""
    return _sem_acentos(_split_produto_validade(nome)[1].upper())


def _parse_data(valor):
    """'2029-05-30' → date. Retorna None para vazio/inválido — nunca inventa."""
    txt = str(valor or "").strip()
    if not txt:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(txt[: len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    return None


def _br(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


# ── Carga de dados (somente SELECT) ───────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _carregar_produtos(_conn) -> list:
    """Monta o universo de etiquetas: um item por PRODUTO.

    Universo = produtos do mapa (agrupando todos os seus códigos) ∪ linhas de
    estoque_mestre cujo código não está vinculado a nenhum produto do mapa —
    para essas vale a linha única mesmo, não existe grupo de códigos.

    Cada item: {chave, nome, codigo_qr, codigos_extras, categoria, qtd,
                racks, posicoes, no_mapa}
    """
    try:
        estoque_rows = _conn.execute(
            "SELECT codigo, produto, categoria, qtd_sistema FROM estoque_mestre"
        ).fetchall()
    except Exception:
        estoque_rows = []

    estoque_por_cod = {}
    for cod, produto, categoria, qtd in estoque_rows:
        c = _norm_codigo(cod)
        if not c:
            continue
        estoque_por_cod[c] = {
            "produto": str(produto or "").strip(),
            "categoria": str(categoria or "").strip(),
            "qtd": qtd or 0,
        }

    try:
        mapa = get_produtos_mapa(_conn)
    except Exception:
        mapa = []

    try:
        pos_rows = _conn.execute(
            "SELECT produto_id, rua, pos_key FROM mapa_posicoes "
            "WHERE produto_id IS NOT NULL ORDER BY rua, pos_key"
        ).fetchall()
    except Exception:
        pos_rows = []
    pos_por_pid = defaultdict(list)
    for pid, rua, pos_key in pos_rows:
        pos_por_pid[pid].append((rua, pos_key))

    itens = []
    vinculados = set()
    sem_codigo = []

    for p in mapa:
        cods = [c for c in (p.get("codigos") or []) if c]
        vinculados.update(cods)
        if not cods:
            # Sem código não há o que codificar no QR nem o que digitar no
            # campo manual do app. Reportado na tela em vez de ignorado.
            sem_codigo.append(p.get("nome") or p.get("produto_id"))
            continue

        principal = _norm_codigo(p.get("codigo"))
        ordenados = ([principal] if principal in cods else []) + [
            c for c in cods if c != principal
        ]
        # O código do QR precisa ser um que tenha linha em estoque_mestre:
        # é dele que sai o nome que o app mostra ao ler a etiqueta.
        com_saldo = [c for c in ordenados if c in estoque_por_cod]
        codigo_qr = com_saldo[0] if com_saldo else ordenados[0]

        linha = estoque_por_cod.get(codigo_qr)
        nome = (linha or {}).get("produto") or str(p.get("nome") or "").strip()
        categoria = (linha or {}).get("categoria", "")
        qtd = sum(estoque_por_cod[c]["qtd"] for c in ordenados if c in estoque_por_cod)

        posicoes = pos_por_pid.get(p["produto_id"], [])
        itens.append({
            "chave": f"pid:{p['produto_id']}",
            "nome": nome,
            "codigo_qr": codigo_qr,
            "codigos_extras": [c for c in ordenados if c != codigo_qr],
            "categoria": categoria,
            "qtd": qtd,
            "racks": sorted({r for r, _ in posicoes}),
            "posicoes": [pk for _, pk in posicoes],
            "no_mapa": True,
        })

    for cod, linha in estoque_por_cod.items():
        if cod in vinculados:
            continue
        itens.append({
            "chave": f"cod:{cod}",
            "nome": linha["produto"],
            "codigo_qr": cod,
            "codigos_extras": [],
            "categoria": linha["categoria"],
            "qtd": linha["qtd"],
            "racks": [],
            "posicoes": [],
            "no_mapa": False,
        })

    itens.sort(key=lambda i: (i["nome"] or "", i["codigo_qr"]))
    return itens, sorted(set(sem_codigo))


def _ordem_fefo(lotes: list) -> list:
    """Ordena por vencimento crescente — FEFO. Sem data vai para o fim, para
    nunca ser escolhido por engano como "o mais próximo"."""
    return sorted(
        lotes,
        key=lambda l: (l["vencimento"] is None, l["vencimento"] or date.max, l["lote"]),
    )


@st.cache_data(ttl=300, show_spinner=False)
def _carregar_lotes(_conn) -> dict:
    """Lotes indexados por código E por nome: {"por_codigo": {...}, "por_nome": {...}}.

    O índice por código é o que vale: a planilha SIG traz o código na coluna
    PRODUTO ("254185 - HERBICIDA BORAL 500 SC 20L") e casar por ele é exato.
    Casar por nome depende da grafia bater entre o BI e estoque_mestre — um
    espaço a mais ou um acento faz o lote sumir da etiqueta sem aviso, e aí
    alguém digita à mão um lote que já estava no banco.

    O índice por nome continua como fallback, para as linhas da planilha que
    vierem sem o prefixo de código.

    Um prefixo que não corresponda a nenhum código real é inofensivo: a
    consulta só usa os códigos que o produto tem de fato, então essa entrada
    do índice nunca é procurada.
    """
    try:
        rows = _conn.execute(
            "SELECT produto, lote, vencimento, quantidade FROM validade_lotes"
        ).fetchall()
    except Exception:
        rows = []

    por_codigo = defaultdict(list)
    por_nome = defaultdict(list)
    for produto, lote, vencimento, quantidade in rows:
        nome_lote = str(lote or "").strip()
        if not nome_lote:
            continue
        registro = {
            "lote": nome_lote,
            "vencimento": _parse_data(vencimento),
            "quantidade": quantidade or 0,
        }
        codigo, _ = _split_produto_validade(produto)
        if codigo:
            por_codigo[codigo].append(registro)
        por_nome[_nome_key(produto)].append(registro)

    return {
        "por_codigo": {k: _ordem_fefo(v) for k, v in por_codigo.items()},
        "por_nome": {k: _ordem_fefo(v) for k, v in por_nome.items()},
    }


# ── QR + HTML da etiqueta ─────────────────────────────────────────────────────

# Lado do SÍMBOLO impresso, em `em` da etiqueta (base 10mm ⇒ 6.5em = 65mm).
# A faixa útil é 6–8 cm: a distância de leitura fica em torno de 10× o lado.
# Medido no símbolo, não no SVG inteiro — o SVG inclui os 4 módulos de margem
# branca de cada lado, que num QR de versão 1 são 8/29 da imagem (28%).
_QR_SIMBOLO_EM = 6.5


@st.cache_data(ttl=3600, show_spinner=False)
def _svg_qr(codigo: str) -> tuple:
    """`(svg_inline, largura, altura, modulos_do_simbolo)` — medidas em módulos.

    error='q' (25% de tolerância a dano) e border=4 (margem branca exigida
    pela norma) não são estética: são o que decide se lê com poeira, vinco e
    rasgo. micro=False força QR padrão — Micro QR não é lido pelo ML Kit do
    app. O segno pode promover o nível de correção para além de Q quando
    couber no mesmo tamanho; 'q' é o piso.

    O `viewBox` é acrescentado à mão: o segno emite só width/height, e sem
    viewBox o CSS que estica o QR apenas amplia a *viewport* — o desenho
    continua no tamanho original e a folha sai com um pedaço do canto do
    código em vez do símbolo inteiro.

    As medidas voltam em módulos (não em mm/em) porque cada preset escala o
    mesmo SVG de um jeito diferente: a etiqueta grande dimensiona o SÍMBOLO em
    `em`, a grade dimensiona o SVG INTEIRO em mm. Quem escala é o chamador.
    """
    qr = segno.make(codigo, error="q", micro=False)
    modulos_simbolo = qr.symbol_size(scale=1, border=0)[0]
    largura, altura = qr.symbol_size(scale=1, border=4)
    svg = qr.svg_inline(scale=1, border=4).replace(
        "<svg ",
        f'<svg viewBox="0 0 {largura} {altura}" '
        'preserveAspectRatio="xMidYMid meet" shape-rendering="crispEdges" ',
        1,
    )
    return svg, largura, altura, modulos_simbolo


@st.cache_data(ttl=3600, show_spinner=False)
def _bloco_qr(codigo: str) -> str:
    """Bloco `<div class="etq-qr">` do QR — etiqueta GRANDE (1 por folha).

    A largura sai calculada em `em` a partir do número de módulos, para o
    SÍMBOLO ficar sempre em `_QR_SIMBOLO_EM` independentemente da versão do
    QR (um código mais longo usa mais módulos e um SVG proporcionalmente
    maior). Em `em` a prévia da tela reduz junto com o resto do texto.
    """
    svg, largura, _altura, modulos_simbolo = _svg_qr(codigo)
    largura_em = _QR_SIMBOLO_EM * largura / modulos_simbolo
    return f'<div class="etq-qr" style="width:{largura_em:.3f}em">{svg}</div>'


_CSS_ETIQUETA = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #fff;
  color: #000;
  font-family: Helvetica, Arial, "Liberation Sans", sans-serif;
}
.etiqueta {
  page-break-after: always;
  break-after: page;
  text-align: center;
  font-size: 10mm;          /* base: todo o resto é em em */
  line-height: 1.15;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 273mm;        /* A4 (297mm) menos as margens de 12mm */
}
.etiqueta:last-child { page-break-after: auto; break-after: auto; }
.etq-nome {
  font-size: 1.7em;
  font-weight: 700;
  line-height: 1.08;
  text-transform: uppercase;
  word-break: break-word;
}
.etq-cod {
  font-size: 0.78em;
  font-weight: 600;
  margin-top: 0.45em;
  font-family: "Courier New", monospace;
}
.etq-validade {
  font-size: 0.8em;
  font-weight: 700;
  color: #cc0000;
  margin-top: 0.35em;
}
.etq-rule {
  border: none;
  border-top: 0.06em solid #000;
  width: 60%;
  margin: 0.4em auto;
}
.etq-lote {
  font-size: 1.5em;
  font-weight: 700;
  font-family: "Courier New", monospace;
  letter-spacing: -0.01em;
  word-break: break-all;
}
.etq-lote-label {
  font-size: 0.5em;
  font-weight: 700;
  letter-spacing: 0.3em;
  margin-top: 0.1em;
}
/* A largura do bloco vem inline, calculada por número de módulos. */
.etq-qr { margin-top: 0.6em; line-height: 0; max-width: 100%; }
.etq-qr svg { width: 100%; height: auto; display: block; }
.etq-rodape {
  font-size: 0.34em;
  margin-top: 0.7em;
  color: #444;
  font-family: "Courier New", monospace;
  word-break: break-word;
}
@media screen {
  body { background: #e5e7eb; padding: 8mm; }
  .etiqueta {
    background: #fff;
    box-shadow: 0 2px 10px rgba(0,0,0,.2);
    margin: 0 auto 8mm;
    width: 186mm;
    padding: 6mm;
  }
}
"""


def _bloco_etiqueta(item: dict, lote) -> str:
    """HTML de UMA etiqueta.

    Sem lote cadastrado as linhas de validade e lote são **omitidas** — nunca
    impressas vazias nem com 'None'.
    """
    partes = [
        f'<div class="etq-nome">{_esc.escape(item["nome"] or item["codigo_qr"])}</div>',
        f'<div class="etq-cod">Cód. {_esc.escape(item["codigo_qr"])}</div>',
    ]

    if lote:
        venc = _br(lote.get("vencimento"))
        if venc:
            partes.append(f'<div class="etq-validade">Validade: {venc}</div>')
        partes.append('<hr class="etq-rule">')
        partes.append(f'<div class="etq-lote">{_esc.escape(lote["lote"])}</div>')
        partes.append('<div class="etq-lote-label">LOTE</div>')

    partes.append(_bloco_qr(item["codigo_qr"]))

    rodape = []
    if item["codigos_extras"]:
        rodape.append("também: " + " · ".join(item["codigos_extras"]))
    if item["posicoes"]:
        rodape.append(" · ".join(item["posicoes"][:6]))
    if rodape:
        partes.append(
            f'<div class="etq-rodape">{_esc.escape(" — ".join(rodape))}</div>'
        )

    return '<section class="etiqueta">' + "".join(partes) + "</section>"


# ── Etiqueta em grade (N por folha) ───────────────────────────────────────────

def _medidas_grade(cfg: dict) -> dict:
    """Medidas da célula, derivadas da folha. Nenhum número escrito à mão.

    Com o preset pequeno: (210 − 2×10 − 4×6)/5 = 33,2 mm de largura e
    (297 − 2×10 − 5×6)/6 = 41,167 mm de altura por célula.

    `qr_mm` é limitado à largura da célula: um preset futuro com QR maior do
    que a célula sairia com a grade estourando a margem da folha e etiquetas
    cortadas na impressão, em vez de um erro visível.
    """
    largura, altura = cfg["folha_mm"]
    colunas, linhas = cfg["colunas"], cfg["linhas"]
    margem, gap = cfg["margem_mm"], cfg["gap_mm"]
    celula_l = (largura - 2 * margem - gap * (colunas - 1)) / colunas
    celula_a = (altura - 2 * margem - gap * (linhas - 1)) / linhas
    return {
        "celula_l": celula_l,
        "celula_a": celula_a,
        "util_l": largura - 2 * margem,
        "qr_mm": min(cfg["qr_mm"], celula_l),
    }


def _css_grade(cfg: dict, *, documento: bool) -> str:
    """CSS da grade a partir do preset.

    `documento=False` devolve só as regras da grade e da célula, para a prévia
    dentro do Streamlit — as regras de `@page`/`body` não podem entrar na
    página do app, senão reformatam o dashboard inteiro. `documento=True`
    acrescenta essas regras, para o arquivo baixado.

    O nome é truncado com reticências pelo próprio navegador
    (`text-overflow: ellipsis`) em vez de por contagem de caracteres: quem
    sabe quantos caracteres cabem em 33,2 mm é o motor de texto que vai
    imprimir, com a fonte e o kerning reais.
    """
    med = _medidas_grade(cfg)
    largura, altura = cfg["folha_mm"]

    regras = f"""
.etq-folha {{
  display: grid;
  grid-template-columns: repeat({cfg['colunas']}, {med['celula_l']:.3f}mm);
  grid-auto-rows: {med['celula_a']:.3f}mm;
  gap: {cfg['gap_mm']}mm;
  justify-content: start;
  align-content: start;
  width: {med['util_l']:.3f}mm;
  /* Repetido aqui (o `body` do documento já traz) para a prévia dentro do
     Streamlit não herdar a fonte e a cor do tema escuro do dashboard. */
  font-family: Helvetica, Arial, "Liberation Sans", sans-serif;
  color: #000;
}}
.etq-mini {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
  text-align: center;
}}
.etq-mini-qr {{ width: {med['qr_mm']:.3f}mm; line-height: 0; }}
.etq-mini-qr svg {{ width: 100%; height: auto; display: block; }}
.etq-mini-nome {{
  font-size: {cfg['nome_pt']}pt;
  font-weight: 600;
  line-height: 1.1;
  margin-top: 0.8mm;
  /* Ocupa a célula inteira (mais largo que o QR, para caber mais nome), menos
     0,8 mm de cada lado: sem esse respiro o texto encosta na linha de corte e
     a tesoura come as letras da ponta. `box-sizing` explícito porque o
     padding tem que entrar PARA DENTRO dos 33,2 mm — a prévia no Streamlit
     não herda o `* {{ box-sizing: border-box }}` do documento. */
  box-sizing: border-box;
  width: 100%;
  padding: 0 0.8mm;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
"""
    if not documento:
        return regras

    return f"""
@page {{ size: {largura}mm {altura}mm; margin: {cfg['margem_mm']}mm; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: #fff;
  color: #000;
  font-family: Helvetica, Arial, "Liberation Sans", sans-serif;
}}
.etq-folha {{ page-break-after: always; break-after: page; }}
.etq-folha:last-child {{ page-break-after: auto; break-after: auto; }}
{regras}
@media screen {{
  body {{ background: #e5e7eb; padding: 8mm; }}
  .etq-folha {{
    background: #fff;
    box-shadow: 0 2px 10px rgba(0,0,0,.2);
    margin: 0 auto 8mm;
    padding: {cfg['margem_mm']}mm;
    width: {largura}mm;
  }}
}}
"""


def _bloco_etiqueta_mini(item: dict) -> str:
    """UMA célula da grade: QR + nome. Sem lote, sem validade, sem rodapé.

    O QR carrega o mesmo conteúdo da etiqueta grande — só o código do produto,
    texto puro. Como esse conteúdo não varia por lote, uma etiqueta por
    produto é tudo o que existe para gerar aqui.
    """
    nome = item["nome"] or item["codigo_qr"]
    return (
        '<div class="etq-mini">'
        f'<div class="etq-mini-qr">{_svg_qr(item["codigo_qr"])[0]}</div>'
        f'<div class="etq-mini-nome" title="{_esc.escape(nome)}">'
        f"{_esc.escape(nome)}</div>"
        "</div>"
    )


def _folhas_grade(itens: list, cfg: dict) -> list:
    """Fatia os itens em folhas de `colunas × linhas`. A última fica parcial.

    Uma folha = um `<div class="etq-folha">` com quebra de página depois, e não
    uma grade só que o navegador quebra sozinho: com grade contínua o Chrome
    corta linhas no meio da altura da página.
    """
    por_folha = cfg["colunas"] * cfg["linhas"]
    return [
        '<div class="etq-folha">'
        + "".join(_bloco_etiqueta_mini(i) for i in itens[inicio:inicio + por_folha])
        + "</div>"
        for inicio in range(0, len(itens), por_folha)
    ]


# Aviso de impressão, visível na TELA e ausente na folha.
#
# O navegador imprime data, título e a URL `file:///home/.../etiquetas_x.html`
# nas bordas quando "Cabeçalhos e rodapés" está marcado, e não existe CSS que
# desligue isso — a decisão é do diálogo de impressão. Medido no Chromium com
# a opção ligada: o cabeçalho termina a 8,6 mm do topo e o rodapé começa a
# 8,2 mm da borda de baixo, então com as margens deste CSS (10 mm na grade,
# 12 mm na etiqueta grande) ele NÃO alcança o QR nem invade a zona de
# silêncio. Só que a folga no topo da grade é de 1,4 mm, e some se a pessoa
# trocar "Margens" para "Nenhuma" no diálogo — aí a grade inteira sai
# deslocada, não só o cabeçalho. Por isso o aviso fica no arquivo, onde quem
# imprime está olhando, e não só na aba do Streamlit.
_AVISO_IMPRESSAO = """<div class="etq-aviso">
  <b>Para imprimir:</b> Ctrl+P → <b>A4</b>, <b>retrato</b>, escala
  <b>100%</b> (não use "Ajustar à página") e <b>Margens: Padrão</b>.
  Desmarque <b>“Cabeçalhos e rodapés”</b> para a data e o endereço do arquivo
  não saírem impressos na borda da folha.
  <span>Esta faixa não é impressa.</span>
</div>"""

_CSS_AVISO = """
.etq-aviso {
  font-family: Helvetica, Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #111;
  background: #fff8c4;
  border: 1px solid #d9c257;
  border-radius: 6px;
  padding: 10px 14px;
  margin: 0 auto 8mm;
  max-width: 186mm;
}
.etq-aviso span { display: block; font-size: 9pt; color: #6b6b4a; margin-top: 4px; }
@media print { .etq-aviso { display: none !important; } }
"""


def _montar_documento(blocos: list, titulo: str, css: str = _CSS_ETIQUETA) -> str:
    """Documento HTML completo e autocontido (SVGs embutidos, zero rede)."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc.escape(titulo)}</title>\n"
        f"<style>{css}{_CSS_AVISO}</style>\n</head>\n<body>\n"
        + _AVISO_IMPRESSAO
        + "\n"
        + "\n".join(blocos)
        + "\n</body>\n</html>\n"
    )


def _lotes_do_item(item: dict, lotes: dict) -> list:
    """Todos os lotes do produto, em ordem FEFO.

    Procura pelo **grupo de códigos** do produto — o do QR mais os
    secundários. Lotes do BORAL lançados sob '254185' e sob 'US254185' são o
    mesmo produto e entram na mesma etiqueta, com o FEFO considerando os dois.

    Só cai no match por nome quando nenhum código encontrou nada: é a saída
    para linhas da planilha sem o prefixo de código.
    """
    por_codigo = lotes.get("por_codigo", {})
    achados = []
    vistos = set()
    for cod in [item["codigo_qr"], *item["codigos_extras"]]:
        for registro in por_codigo.get(cod, []):
            assinatura = (registro["lote"], registro["vencimento"])
            if assinatura in vistos:
                continue
            vistos.add(assinatura)
            achados.append(registro)
    if achados:
        return _ordem_fefo(achados)
    return lotes.get("por_nome", {}).get(_nome_key(item["nome"]), [])


def _lote_fefo(item: dict, lotes: dict):
    """Lote de vencimento mais próximo do produto, ou None se não há lote."""
    disponiveis = _lotes_do_item(item, lotes)
    return disponiveis[0] if disponiveis else None


def _etiquetas_do_item(item: dict, lotes: dict, criterio: str,
                       manuais: dict = None) -> list:
    """Lista de (item, lote|None) a imprimir para um produto.

    `manuais` é o mapa {chave_do_item: lote} vindo da digitação à mão; só é
    consultado no critério CRIT_MANUAL. Lote em branco vira None — a etiqueta
    sai sem as linhas de validade e lote, nunca com campo vazio.
    """
    if criterio == CRIT_SEM:
        return [(item, None)]
    if criterio == CRIT_MANUAL:
        return [(item, (manuais or {}).get(item["chave"]))]
    disponiveis = _lotes_do_item(item, lotes)
    if not disponiveis:
        return [(item, None)]
    if criterio == CRIT_TODOS:
        return [(item, l) for l in disponiveis]
    return [(item, disponiveis[0])]  # FEFO: já ordenado por vencimento


# ── Aba ───────────────────────────────────────────────────────────────────────

_CSS_TAB = """<style>
.etq-title{font-size:1.05rem;font-weight:700;color:#e0e6ed;margin-bottom:4px;}
.etq-sub{font-size:0.78rem;color:#64748b;margin-bottom:12px;}
.etq-crit{background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);
          border-radius:8px;padding:8px 12px;font-size:0.78rem;color:#93c5fd;
          margin:8px 0 12px;}
.etq-kpi-row{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;}
.etq-kpi{flex:1;min-width:90px;background:linear-gradient(135deg,#111827,#1a2332);
         border:1px solid #1e293b;border-radius:10px;padding:8px 10px;text-align:center;}
.etq-kpi-v{font-family:'JetBrains Mono',monospace;font-size:1.15rem;font-weight:700;color:#22c55e;}
.etq-kpi-v.amber{color:#ffa502;}
.etq-kpi-v.blue{color:#3b82f6;}
.etq-kpi-l{font-size:0.58rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:2px;}
.etq-section{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
             color:#64748b;margin:14px 0 6px;padding-bottom:4px;border-bottom:1px solid #1e293b;}
.etq-empty{text-align:center;padding:36px 20px;color:#475569;font-size:0.85rem;}
.etq-falta-row{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);
               border-radius:8px;padding:6px 10px;margin-bottom:3px;
               display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.etq-falta-cod{font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:#3b82f6;
               min-width:80px;}
.etq-falta-prod{font-size:0.82rem;color:#e0e6ed;flex:1;min-width:160px;}
.etq-falta-extra{font-family:'JetBrains Mono',monospace;font-size:0.66rem;color:#64748b;}
/* Prévia: mesma marcação da folha, só com a base tipográfica menor. */
.etq-preview{background:#e5e7eb;border-radius:10px;padding:14px;overflow-x:auto;}
.etq-preview .etiqueta{background:#fff;color:#000;border-radius:6px;padding:10px 12px;
                       width:100%;max-width:420px;margin:0 auto;min-height:0;
                       font-size:4.4mm;line-height:1.15;text-align:center;
                       font-family:Helvetica,Arial,sans-serif;
                       display:flex;flex-direction:column;align-items:center;}
.etq-preview .etq-nome{font-size:1.7em;font-weight:700;line-height:1.08;
                       text-transform:uppercase;word-break:break-word;}
.etq-preview .etq-cod{font-size:0.78em;font-weight:600;margin-top:0.45em;
                      font-family:'Courier New',monospace;}
.etq-preview .etq-validade{font-size:0.8em;font-weight:700;color:#cc0000;margin-top:0.35em;}
.etq-preview .etq-rule{border:none;border-top:0.06em solid #000;width:60%;margin:0.4em auto;}
.etq-preview .etq-lote{font-size:1.5em;font-weight:700;font-family:'Courier New',monospace;
                       word-break:break-all;}
.etq-preview .etq-lote-label{font-size:0.5em;font-weight:700;letter-spacing:0.3em;margin-top:0.1em;}
.etq-preview .etq-qr{margin-top:0.6em;line-height:0;max-width:100%;}
.etq-preview .etq-qr svg{width:100%;height:auto;display:block;}
.etq-preview .etq-rodape{font-size:0.34em;margin-top:0.7em;color:#444;
                         font-family:'Courier New',monospace;word-break:break-word;}
/* Prévia da grade: a folha branca. As medidas da grade e da célula vêm de
   `_css_grade(documento=False)`, injetado junto da prévia — aqui só o papel.
   As células ficam em mm, então a folha tem a largura real e a prévia rola na
   horizontal em tela estreita em vez de comprimir as etiquetas.
   `box-sizing:content-box` é o que faz o padding somar POR FORA da largura:
   com border-box (o padrão do Streamlit) o miolo cairia para 190−16 mm e as
   colunas, que somam 190 mm exatos, vazariam para fora da folha. */
.etq-preview .etq-folha{background:#fff;border-radius:6px;padding:8mm;
                        margin:0 auto;box-shadow:0 2px 10px rgba(0,0,0,.2);
                        box-sizing:content-box;}
</style>"""


def _editor_lotes(selecionados: list, lotes: dict) -> dict:
    """Tabela para digitar lote e validade à mão. Retorna {chave: lote}.

    Nem todo produto tem lote na tabela `validade_lotes` (a planilha do BI não
    cobre tudo, e lote novo só entra no próximo upload). Aqui o lote é digitado
    na hora, direto na folha que vai ser impressa. Pré-preenche com o lote
    FEFO quando existe, para não redigitar o que o banco já sabe.

    **Nada é gravado**: a aba é somente leitura; o valor digitado vive no
    widget e vale só para o arquivo gerado nesta tela.
    """
    st.markdown('<div class="etq-section">✍️ Lote e validade — digitados à mão</div>',
                unsafe_allow_html=True)
    st.caption(
        "Deixe o lote em branco para a folha sair sem as linhas de validade e "
        "lote. O que for digitado aqui não altera o banco — vale só para estas "
        "folhas."
    )
    if len(selecionados) > 100:
        st.warning(
            f"⚠️ {len(selecionados)} produtos selecionados — digitar lote de todos "
            "é inviável. Filtre por rack ou produto antes."
        )

    base = pd.DataFrame({
        "Produto": [i["nome"] for i in selecionados],
        "Código": [i["codigo_qr"] for i in selecionados],
        "Lote": [(_lote_fefo(i, lotes) or {}).get("lote", "") for i in selecionados],
        "Validade": pd.to_datetime(
            [(_lote_fefo(i, lotes) or {}).get("vencimento") for i in selecionados]
        ),
    })

    # A chave carrega a assinatura da seleção: mudou o filtro, o editor
    # reinicia em vez de aplicar o que foi digitado às linhas de outro produto.
    assinatura = hashlib.md5(
        "|".join(i["chave"] for i in selecionados).encode()
    ).hexdigest()[:10]

    editado = st.data_editor(
        base,
        key=f"etq_lotes_manual_{assinatura}",
        hide_index=True,
        use_container_width=True,
        disabled=["Produto", "Código"],
        column_config={
            "Lote": st.column_config.TextColumn(
                "Lote", help="Número do lote impresso em destaque na folha."
            ),
            "Validade": st.column_config.DateColumn(
                "Validade", format="DD/MM/YYYY",
                help="Sai em vermelho na folha. Em branco, a linha é omitida.",
            ),
        },
    )

    manuais = {}
    for item, (_, linha) in zip(selecionados, editado.iterrows()):
        texto = str(linha["Lote"] or "").strip()
        if not texto or texto.lower() == "nan":
            manuais[item["chave"]] = None
            continue
        venc = linha["Validade"]
        manuais[item["chave"]] = {
            "lote": texto,
            "vencimento": venc.date() if pd.notna(venc) else None,
            "quantidade": 0,
        }
    return manuais


def build_etiquetas_tab(get_db):
    """Renderiza a aba 🏷️ Etiquetas. Somente leitura: nenhuma escrita no banco."""
    st.markdown(_CSS_TAB, unsafe_allow_html=True)
    st.markdown('<div class="etq-title">🏷️ Etiquetas de Rack</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="etq-sub">Folhas A4 com QR code para colar na prateleira. '
        'O app de galpão lê o QR e mostra o saldo do produto — o código também vai '
        'impresso, para digitar à mão quando a etiqueta estiver danificada.</div>',
        unsafe_allow_html=True,
    )

    if segno is None:
        st.error(
            "❌ A biblioteca **segno** não está instalada — sem ela não há como "
            f"gerar o QR code. Instale com `pip install segno`. Detalhe: {_SEGNO_ERRO}"
        )
        return

    conn = get_db()
    itens, sem_codigo = _carregar_produtos(conn)
    lotes = _carregar_lotes(conn)

    if not itens:
        st.markdown(
            '<div class="etq-empty">Nenhum produto disponível para etiqueta.<br>'
            'Carregue o estoque mestre em <b>📤 Upload de Planilha</b>.</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Tamanho da etiqueta ──────────────────────────────────────────────────
    # O preset vale para o documento inteiro: uma folha gerada tem sempre um
    # tamanho só, nunca uma mistura.
    preset_nome = st.radio(
        "Tamanho da etiqueta",
        list(_PRESETS.keys()),
        key="etq_preset",
        horizontal=True,
    )
    cfg = _PRESETS[preset_nome]
    st.caption(cfg["descricao"])

    # ── Critério de lote ─────────────────────────────────────────────────────
    # Desabilitado (em vez de escondido) nos presets sem lote: o widget continua
    # montado, então a escolha do usuário sobrevive à ida e volta entre presets,
    # e a UI mostra por que ele não se aplica em vez de a opção desaparecer.
    criterio = st.radio(
        "Qual lote imprimir na etiqueta?",
        [CRIT_FEFO, CRIT_TODOS, CRIT_MANUAL, CRIT_SEM],
        key="etq_criterio",
        horizontal=True,
        disabled=not cfg["com_lote"],
    )
    if cfg["com_lote"]:
        _explicacao = {
            CRIT_FEFO: (
                "Cada produto sai em <b>uma folha</b>, com o lote de vencimento mais "
                "próximo — é o que deve ser retirado primeiro."
            ),
            CRIT_TODOS: (
                "Cada produto sai em <b>uma folha por lote cadastrado</b>. Produtos com "
                "muitos lotes geram muitas folhas."
            ),
            CRIT_MANUAL: (
                "Você digita o lote e a validade de cada produto na tabela abaixo — "
                "vem pré-preenchida com o lote FEFO quando existe cadastro. "
                "<b>Nada é gravado no banco</b>: o que você digita vale só para "
                "estas folhas."
            ),
            CRIT_SEM: (
                "Apenas nome, código e QR. Sem validade e sem lote — a etiqueta não "
                "precisa ser trocada quando o lote virar."
            ),
        }[criterio]
        st.markdown(
            f'<div class="etq-crit">📌 Critério: {_explicacao} '
            "Produtos <b>sem lote cadastrado</b> saem sem as linhas de validade e lote.</div>",
            unsafe_allow_html=True,
        )
    else:
        # Não é só a UI: o pipeline abaixo roda como CRIT_SEM, então
        # `_etiquetas_do_item` devolve uma etiqueta por produto e o editor de
        # lote manual não é montado.
        criterio = CRIT_SEM
        st.markdown(
            '<div class="etq-crit">🔒 O critério de lote acima <b>só se aplica '
            "à etiqueta grande</b> — por isso está desabilitado. A etiqueta "
            "pequena sai sempre <b>sem lote</b>: uma por produto, só QR + nome. "
            "Motivo: o QR carrega apenas o código do produto, que é o mesmo em "
            "todos os lotes — gerar por lote produziria etiquetas idênticas "
            "duplicadas.</div>",
            unsafe_allow_html=True,
        )

    # ── Cópias por produto ───────────────────────────────────────────────────
    copias = 1
    if cfg["copias"]:
        _col_copias, _ = st.columns([1, 3])
        with _col_copias:
            copias = int(st.number_input(
                "Cópias por produto",
                min_value=1, max_value=50, value=1, step=1,
                key="etq_copias",
                help="Repete cada etiqueta na grade, uma ao lado da outra — "
                     "para colar o mesmo produto em mais de uma posição.",
            ))

    # ── Filtros ──────────────────────────────────────────────────────────────
    racks_disp = sorted({r for i in itens for r in i["racks"]},
                        key=lambda r: (len(r), r))
    cats_disp = sorted({i["categoria"] for i in itens if i["categoria"]})

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        busca = st.text_input(
            "Buscar produto", key="etq_busca",
            placeholder="Nome ou código…", label_visibility="collapsed",
        )
    with c2:
        rack_sel = st.selectbox(
            "Rack", ["Todos os racks"] + racks_disp + ["Sem posição no mapa"],
            key="etq_rack", label_visibility="collapsed",
        )
    with c3:
        cat_sel = st.selectbox(
            "Categoria", ["Todas as categorias"] + cats_disp,
            key="etq_cat", label_visibility="collapsed",
        )

    filtrados = itens
    if rack_sel == "Sem posição no mapa":
        filtrados = [i for i in filtrados if not i["racks"]]
    elif rack_sel != "Todos os racks":
        filtrados = [i for i in filtrados if rack_sel in i["racks"]]
    if cat_sel != "Todas as categorias":
        filtrados = [i for i in filtrados if i["categoria"] == cat_sel]
    if busca.strip():
        termo = busca.strip().lower()
        filtrados = [
            i for i in filtrados
            if termo in (i["nome"] or "").lower()
            or termo in i["codigo_qr"].lower()
            or any(termo in c.lower() for c in i["codigos_extras"])
        ]

    if not filtrados:
        st.warning("Nenhum produto bate com os filtros.")
        return

    # ── Refino manual (vazio = todos os filtrados) ───────────────────────────
    rotulos = {f'{i["codigo_qr"]} — {i["nome"]}': i for i in filtrados}
    escolhidos = st.multiselect(
        "Refinar seleção (deixe vazio para gerar todos os filtrados)",
        list(rotulos.keys()), key="etq_produtos",
    )
    selecionados = [rotulos[r] for r in escolhidos] if escolhidos else filtrados

    # ── Digitação do lote à mão ──────────────────────────────────────────────
    manuais = _editor_lotes(selecionados, lotes) if criterio == CRIT_MANUAL else None

    # ── Etiquetas a gerar ────────────────────────────────────────────────────
    pares = []
    for item in selecionados:
        pares.extend(_etiquetas_do_item(item, lotes, criterio, manuais))
    if copias > 1:
        # Cópias adjacentes, não a lista repetida no fim: na folha as etiquetas
        # iguais saem lado a lado, que é como se corta e se leva para o rack.
        pares = [par for par in pares for _ in range(copias)]

    # No modo "folha" cada etiqueta É uma folha; no modo "grade" cabem
    # colunas × linhas por folha e a última fica parcialmente preenchida.
    por_folha = cfg["colunas"] * cfg["linhas"] if cfg["modo"] == "grade" else 1
    n_folhas = -(-len(pares) // por_folha)  # ceil sem importar math

    hoje = date.today()
    n_sem_lote = sum(1 for _, l in pares if not l)
    n_vencidos = sum(
        1 for _, l in pares
        if l and l.get("vencimento") and l["vencimento"] < hoje
    )

    # Sem lote nenhum, os KPIs de lote seriam sempre 0 e "Sem lote" marcaria o
    # total — ruído. Entram no lugar deles a contagem de etiquetas (que com
    # cópias > 1 não é o número de produtos) e a densidade da folha.
    if cfg["com_lote"]:
        _kpis = [
            (len(selecionados), "Produtos", ""),
            (n_folhas, "Folhas A4", "blue"),
            (n_sem_lote, "Sem lote", "amber"),
            (n_vencidos, "Lote vencido", "amber"),
        ]
    else:
        _kpis = [
            (len(selecionados), "Produtos", ""),
            (len(pares), "Etiquetas", ""),
            (n_folhas, "Folhas A4", "blue"),
            (f"{por_folha}/folha", "Densidade", "blue"),
        ]
    st.markdown(
        '<div class="etq-kpi-row">'
        + "".join(
            f'<div class="etq-kpi"><div class="etq-kpi-v {classe}">{valor}</div>'
            f'<div class="etq-kpi-l">{rotulo}</div></div>'
            for valor, rotulo, classe in _kpis
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if n_vencidos:
        st.warning(
            f"⚠️ {n_vencidos} etiqueta(s) trazem um lote **já vencido** — é o lote "
            "mais próximo do vencimento que existe cadastrado para o produto. "
            "Confira a aba 📅 Validade antes de colar na prateleira."
        )

    # Sem esta lista a falha de match fica silenciosa: a etiqueta sai sem lote
    # e ninguém sabe se é porque a planilha não tem, ou porque o casamento
    # errou. Com o código à mostra dá para conferir na planilha.
    if n_sem_lote and criterio != CRIT_SEM:
        faltantes = [i for i, l in pares if not l]
        with st.expander(f"🔎 {n_sem_lote} produto(s) sem lote — ver quais"):
            st.caption(
                "Os lotes vêm da planilha SIG enviada em **📅 Validade** "
                "(tabela `validade_lotes`), casados pelo código do produto. "
                "Se um destes está na planilha, o código abaixo é o que "
                "procurar nela."
            )
            # Lista em HTML como o resto do módulo — st.dataframe serializa
            # para Arrow e derruba o processo neste app (crash nativo, sem
            # traceback; ver CLAUDE.md, armadilha 1).
            linhas = []
            for i in faltantes:
                extras = (
                    f'<span class="etq-falta-extra">também '
                    f'{_esc.escape(", ".join(i["codigos_extras"]))}</span>'
                    if i["codigos_extras"] else ""
                )
                linhas.append(
                    f'<div class="etq-falta-row">'
                    f'<span class="etq-falta-cod">{_esc.escape(i["codigo_qr"])}</span>'
                    f'<span class="etq-falta-prod">{_esc.escape(i["nome"] or "")}</span>'
                    f'{extras}</div>'
                )
            st.markdown("".join(linhas), unsafe_allow_html=True)
    if sem_codigo:
        st.info(
            f"ℹ️ {len(sem_codigo)} produto(s) do mapa não têm código vinculado e "
            "por isso não geram etiqueta (sem código não há QR nem digitação "
            f"manual): {', '.join(sem_codigo[:5])}"
            + ("…" if len(sem_codigo) > 5 else "")
        )

    if len(pares) > cfg["max_etiquetas"]:
        st.error(
            f"❌ {len(pares)} etiquetas ({n_folhas} folhas) é mais do que o "
            f"gerador entrega de uma vez (limite {cfg['max_etiquetas']} "
            "etiquetas neste tamanho). Filtre por rack ou categoria — o uso "
            "normal é reimprimir um rack de cada vez."
        )
        return

    # ── Prévia da primeira folha ─────────────────────────────────────────────
    st.markdown('<div class="etq-section">👁️ Prévia da primeira folha</div>',
                unsafe_allow_html=True)
    item_prev = pares[0][0]
    if cfg["modo"] == "grade":
        # A prévia é a folha de verdade: mesma marcação e mesmas medidas em mm
        # do arquivo baixado, só sem as regras de `@page`/`body`.
        _med = _medidas_grade(cfg)
        st.markdown(
            f"<style>{_css_grade(cfg, documento=False)}</style>"
            '<div class="etq-preview">'
            f'{_folhas_grade([i for i, _ in pares[:por_folha]], cfg)[0]}'
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f'QR contém o texto puro `{item_prev["codigo_qr"]}` — sem URL, sem '
            "encurtador. Célula de "
            f"{_med['celula_l']:.1f} × {_med['celula_a']:.1f} mm, QR de "
            f"{_med['qr_mm']:.0f} mm incluindo a margem branca da norma "
            "(símbolo de ~"
            f"{_med['qr_mm'] * _svg_qr(item_prev['codigo_qr'])[3] / _svg_qr(item_prev['codigo_qr'])[1]:.0f}"
            " mm). Nome truncado com reticências quando não cabe na linha."
        )
    else:
        st.markdown(
            f'<div class="etq-preview">{_bloco_etiqueta(*pares[0])}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f'QR contém o texto puro `{item_prev["codigo_qr"]}` — sem URL, sem '
            "encurtador. O app resolve o código no banco por conta própria."
        )

    # ── Download ─────────────────────────────────────────────────────────────
    st.markdown('<div class="etq-section">⬇️ Gerar folhas</div>', unsafe_allow_html=True)
    st.caption(
        "Baixe o arquivo, abra no navegador e imprima com Ctrl+P: **A4**, "
        "**retrato**, escala **100%** e **Margens: Padrão**. Desmarque "
        "**“Cabeçalhos e rodapés”** — senão o navegador imprime a data e o "
        "caminho do arquivo (`file:///...`) na borda da folha. O arquivo é "
        "autocontido: os QR codes estão dentro dele, não dependem de internet "
        "na hora de imprimir."
    )

    if rack_sel not in ("Todos os racks", "Sem posição no mapa"):
        sufixo = f"rack_{rack_sel.lower()}"
        titulo = f"Etiquetas — rack {rack_sel}"
    elif len(selecionados) == 1:
        sufixo = selecionados[0]["codigo_qr"].lower()
        titulo = f'Etiqueta — {selecionados[0]["nome"]}'
    else:
        sufixo = "geral"
        titulo = "Etiquetas de rack — CAMDA"

    if cfg["modo"] == "grade":
        documento = _montar_documento(
            _folhas_grade([i for i, _ in pares], cfg),
            f"{titulo} ({por_folha} por folha)",
            _css_grade(cfg, documento=True),
        )
        rotulo_botao = (
            f"🏷️ Baixar {n_folhas} folha(s) A4 · {len(pares)} etiquetas "
            "(HTML para impressão)"
        )
    else:
        documento = _montar_documento(
            [_bloco_etiqueta(i, l) for i, l in pares], titulo
        )
        rotulo_botao = f"🏷️ Baixar {len(pares)} folha(s) A4 (HTML para impressão)"

    st.download_button(
        rotulo_botao,
        data=documento.encode("utf-8"),
        file_name=f"{cfg['arquivo']}_{sufixo}.html",
        mime="text/html",
        key="etq_download",
        type="primary",
    )
