"""
matr480_parser.py
=================
Parser do relatório MATR480 — "Materiais Em Poder de Terceiros" (TOTVS Protheus).

Formato real (observado no SIGA/MATR480/v.12):

  Cabeçalho de página (ignorado):
      SIGA/MATR480/v.12 RELACAO DE MATERIAIS...
      Hora: HH:MM:SS  Emissao: DD/MM/AAAA
      Grupo de Empresa: ...  Folha: N
      Tipo Cli/F  Cliente/Fo  Loj  Razao Social  Doc.Origin  ...   ← cabeçalho colunas

  Bloco de produto (repete por produto):
      Codigo Descricao Armazem             ← label  (sinaliza próxima linha)
      10025267 HERBICIDA BROWSER 5L 01    ← dados do produto

      FORNEC.: 000819 03 BRAVO ARMAZENS...  000079996  2  31/03/2026  80,00000  ...  E  31/03/2026
      CLIE: 23393 13 RICARDO DE ARAUJO...   000000558  3  09/02/2026  20,00000  ...  D  09/02/2026

      TOTAL DESTE PRODUTO/ARMAZEM ------>  ...       ← ignorado

  Rodapé (ignorado):
      Total Geral  /  Hora: HH:MM:SS
"""

from __future__ import annotations

import re
from io import BytesIO
from datetime import datetime
from typing import Union

try:
    import pdfplumber
except ImportError as _e:
    raise ImportError(
        "pdfplumber não está instalado. Execute: pip install pdfplumber"
    ) from _e


# ── Helpers ───────────────────────────────────────────────────────────────────

def _br_float(s: str) -> float:
    """Converte número BR (1.234,56 → 1234.56)."""
    try:
        return float(str(s).strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ── Padrões ───────────────────────────────────────────────────────────────────

# Label que precede a linha de dados do produto
_PROD_LABEL_RE = re.compile(
    r"^Codigo\s+Descricao\s+Armazem\s*$", re.IGNORECASE
)

# Linha de dados do produto: <CODIGO>  <DESCRICAO>  <ARMAZEM(2digits)>
# Ex: "10025267 HERBICIDA BROWSER 5L 01"
# Ex: "US100272852 NEMATICIDA QUARTZO 1KG 01"
_PROD_DATA_RE = re.compile(
    r"^(\S+)\s+(.+?)\s+(\d{2})\s*$"
)

# Linha de movimentação
# CLIE:    <cod> <loj> <razao_social>  <doc_origin>  <serie>  <dt_emissao>
#          <qtd_orig>  <qtd_ent>  <saldo>  <tot_nf>  <tot_dev>  <custo>  <tm>  <dt_lancto>
# FORNEC.: <cod> <loj> <razao_social>  ...
_MOVE_RE = re.compile(
    r"^(CLIE|FORNEC)\.?:?\s+"            # tipo  (CLIE: ou FORNEC.:)
    r"(\S+)\s+"                           # codigo_parceiro
    r"(\d{1,3})\s+"                       # loja
    r"(.+?)\s+"                           # razao_social (non-greedy)
    r"(\d{5,12})\s+"                      # doc_origin  (sequência de 5-12 dígitos)
    r"(\S+)\s+"                           # serie
    r"(\d{2}/\d{2}/\d{4})\s+"            # dt_emissao
    r"([\d.]*\d+,\d+)\s+"                # qtd_original   (formato BR)
    r"([\d.]*\d+,\d+)\s+"                # qtd_entregue
    r"([\d.]*\d+,\d+)\s+"                # saldo
    r"([\d.]*\d+,\d+)\s+"                # total_nf
    r"([\d.]*\d+,\d+)\s+"                # total_devolvido
    r"([\d.]*\d+,\d+)\s+"                # custo_prod
    r"(E|D)\s+"                           # tm  (Entrada / Devolução)
    r"(\d{2}/\d{2}/\d{4})"               # data_lancto
)

# Linhas a ignorar sempre
_SKIP_RES = [
    re.compile(r"^SIGA/MATR",          re.IGNORECASE),
    re.compile(r"^Hora:\s"),
    re.compile(r"^Emissao:\s"),
    re.compile(r"^Grupo\s+de\s+Empresa", re.IGNORECASE),
    re.compile(r"^Pergunta\s+\d+"),
    re.compile(r"^Tipo\s+Cli",         re.IGNORECASE),
    re.compile(r"^TOTAL\s+DESTE\s+PRODUTO", re.IGNORECASE),
    re.compile(r"^Total\s+Geral",      re.IGNORECASE),
    re.compile(r"^[-=]{5,}"),
]


def _is_skip(line: str) -> bool:
    return any(p.match(line) for p in _SKIP_RES)


# ── Função principal ──────────────────────────────────────────────────────────

def parse_matr480(
    source: Union[str, bytes, BytesIO],
    data_referencia: str | None = None,
    debug: bool = False,
) -> tuple[list[dict], list[str]]:
    """
    Faz o parse do PDF MATR480 do TOTVS.

    Parâmetros
    ----------
    source : str | bytes | BytesIO
        Caminho, bytes ou BytesIO do PDF.
    data_referencia : str, opcional
        Data de referência no formato YYYY-MM-DD. Padrão: hoje.
    debug : bool
        Se True, inclui aviso para linhas não reconhecidas.

    Retorna
    -------
    (records, warnings)
    """
    if data_referencia is None:
        data_referencia = datetime.now().strftime("%Y-%m-%d")
    if isinstance(source, bytes):
        source = BytesIO(source)

    records: list[dict] = []
    warnings: list[str] = []
    current_product: dict | None = None
    expect_product_data: bool = False   # True após ver "Codigo Descricao Armazem"

    with pdfplumber.open(source) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                # ── Linhas sempre ignoradas ──────────────────────────────
                if _is_skip(line):
                    expect_product_data = False
                    continue

                # ── Label de produto ─────────────────────────────────────
                if _PROD_LABEL_RE.match(line):
                    expect_product_data = True
                    continue

                # ── Dados do produto (linha imediatamente após a label) ──
                if expect_product_data:
                    expect_product_data = False
                    m = _PROD_DATA_RE.match(line)
                    if m:
                        current_product = {
                            "codigo":    m.group(1).strip(),
                            "descricao": _norm(m.group(2)),
                            "armazem":   m.group(3).strip(),
                        }
                    else:
                        warnings.append(
                            f"[p.{page_num}] Esperava dados de produto: {line[:100]}"
                        )
                    continue

                # ── Linha de movimentação ────────────────────────────────
                if re.match(r"^(CLIE|FORNEC)", line):
                    if current_product is None:
                        warnings.append(
                            f"[p.{page_num}] Movimentação sem produto: {line[:80]}"
                        )
                        continue

                    mv = _MOVE_RE.match(line)
                    if mv:
                        records.append({
                            "codigo_produto":  current_product["codigo"],
                            "descricao":       current_product["descricao"],
                            "armazem":         current_product["armazem"],
                            "tipo":            mv.group(1),
                            "codigo_parceiro": mv.group(2),
                            "loja":            mv.group(3),
                            "razao_social":    _norm(mv.group(4)),
                            "doc_origin":      mv.group(5),
                            "serie":           mv.group(6),
                            "dt_emissao":      mv.group(7),
                            "qtd_original":    _br_float(mv.group(8)),
                            "qtd_entregue":    _br_float(mv.group(9)),
                            "saldo":           _br_float(mv.group(10)),
                            "total_nf":        _br_float(mv.group(11)),
                            "total_devolvido": _br_float(mv.group(12)),
                            "custo_prod":      _br_float(mv.group(13)),
                            "tm":              mv.group(14),
                            "data_lancto":     mv.group(15),
                            "data_referencia": data_referencia,
                        })
                    else:
                        warnings.append(
                            f"[p.{page_num}] Linha CLIE/FORNEC não parseada: {line[:120]}"
                        )
                    continue

                # ── Outras linhas (debug) ────────────────────────────────
                if debug and current_product is not None:
                    warnings.append(f"[p.{page_num}] Linha ignorada: {line[:80]}")

    return records, warnings
