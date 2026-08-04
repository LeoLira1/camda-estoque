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
def _bloco_qr(codigo: str) -> str:
    """Bloco `<div class="etq-qr">` com o SVG do QR do código (texto puro).

    error='q' (25% de tolerância a dano) e border=4 (margem branca exigida
    pela norma) não são estética: são o que decide se lê com poeira, vinco e
    rasgo. micro=False força QR padrão — Micro QR não é lido pelo ML Kit do
    app. O segno pode promover o nível de correção para além de Q quando
    couber no mesmo tamanho; 'q' é o piso.

    O `viewBox` é acrescentado à mão: o segno emite só width/height, e sem
    viewBox o CSS que estica o QR para 7 cm apenas amplia a *viewport* — o
    desenho continua no tamanho original e a folha sai com um pedaço do
    canto do código em vez do símbolo inteiro.

    A largura sai calculada em `em` a partir do número de módulos, para o
    SÍMBOLO ficar sempre em `_QR_SIMBOLO_EM` independentemente da versão do
    QR (um código mais longo usa mais módulos e um SVG proporcionalmente
    maior). Em `em` a prévia da tela reduz junto com o resto do texto.
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


def _montar_documento(blocos: list, titulo: str) -> str:
    """Documento HTML completo e autocontido (SVGs embutidos, zero rede)."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc.escape(titulo)}</title>\n"
        f"<style>{_CSS_ETIQUETA}</style>\n</head>\n<body>\n"
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

    # ── Critério de lote ─────────────────────────────────────────────────────
    criterio = st.radio(
        "Qual lote imprimir na etiqueta?",
        [CRIT_FEFO, CRIT_TODOS, CRIT_MANUAL, CRIT_SEM],
        key="etq_criterio",
        horizontal=True,
    )
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

    hoje = date.today()
    n_sem_lote = sum(1 for _, l in pares if not l)
    n_vencidos = sum(
        1 for _, l in pares
        if l and l.get("vencimento") and l["vencimento"] < hoje
    )

    st.markdown(f"""
    <div class="etq-kpi-row">
      <div class="etq-kpi"><div class="etq-kpi-v">{len(selecionados)}</div>
        <div class="etq-kpi-l">Produtos</div></div>
      <div class="etq-kpi"><div class="etq-kpi-v blue">{len(pares)}</div>
        <div class="etq-kpi-l">Folhas A4</div></div>
      <div class="etq-kpi"><div class="etq-kpi-v amber">{n_sem_lote}</div>
        <div class="etq-kpi-l">Sem lote</div></div>
      <div class="etq-kpi"><div class="etq-kpi-v amber">{n_vencidos}</div>
        <div class="etq-kpi-l">Lote vencido</div></div>
    </div>
    """, unsafe_allow_html=True)

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

    if len(pares) > _MAX_ETIQUETAS:
        st.error(
            f"❌ {len(pares)} folhas é mais do que o gerador entrega de uma vez "
            f"(limite {_MAX_ETIQUETAS}). Filtre por rack ou categoria — o uso "
            "normal é reimprimir um rack de cada vez."
        )
        return

    # ── Prévia da primeira etiqueta ──────────────────────────────────────────
    st.markdown('<div class="etq-section">👁️ Prévia da primeira folha</div>',
                unsafe_allow_html=True)
    item_prev, lote_prev = pares[0]
    st.markdown(
        f'<div class="etq-preview">{_bloco_etiqueta(item_prev, lote_prev)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f'QR contém o texto puro `{item_prev["codigo_qr"]}` — sem URL, sem '
        "encurtador. O app resolve o código no banco por conta própria."
    )

    # ── Download ─────────────────────────────────────────────────────────────
    st.markdown('<div class="etq-section">⬇️ Gerar folhas</div>', unsafe_allow_html=True)
    st.caption(
        "Baixe o arquivo, abra no navegador e imprima com Ctrl+P (A4, retrato, "
        "sem redimensionar). O arquivo é autocontido — os QR codes estão dentro "
        "dele, não dependem de internet na hora de imprimir."
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

    documento = _montar_documento(
        [_bloco_etiqueta(i, l) for i, l in pares], titulo
    )
    st.download_button(
        f"🏷️ Baixar {len(pares)} folha(s) A4 (HTML para impressão)",
        data=documento.encode("utf-8"),
        file_name=f"etiquetas_{sufixo}.html",
        mime="text/html",
        key="etq_download",
        type="primary",
    )
