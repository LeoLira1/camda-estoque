"""
matr480_parser.py
=================
Parser do relatório MATR480 — "Materiais Em Poder de Terceiros" (TOTVS Protheus).

Estrutura esperada do PDF:
  • Cabeçalho de página (título, data, empresa) — ignorado
  • Bloco de produto:
      <codigo>  <descricao>  <armazem>          ← linha de identificação do produto
      (ou: "Cod.Produto : XXXX  Descrição : YYY  Armazém : ZZ")
      (ou: "XXXX / YYY / ZZ")
      ... cabeçalho de colunas (ignorado) ...
      CLIE/FORNEC  <campos...>                  ← linhas de movimentação
      Total do Produto: ...                     ← ignorado
      [Notas Fiscais de Retorno: ...]            ← ignorado
  • Próximo bloco de produto...

Uso:
    from matr480_parser import parse_matr480
    records = parse_matr480("relatorio.pdf")
    # ou
    records = parse_matr480(pdf_bytes)         # bytes ou BytesIO também funcionam
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
    """Converte número no formato BR (1.234,56 ou 1234,56) para float."""
    try:
        return float(str(s).strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _norm(s: str) -> str:
    """Remove espaços duplicados e strip."""
    return re.sub(r"\s+", " ", s).strip()


# ── Padrões de reconhecimento ─────────────────────────────────────────────────

# Linha de movimentação: CLIE ou FORNEC na primeira coluna
_MOVE_FULL = re.compile(
    r"^(CLIE|FORNEC)\s+"       # tipo
    r"(\S+)\s+"                # codigo_parceiro
    r"(\S+)\s+"                # loja
    r"(.+?)\s{2,}"             # razao_social  (termina em 2+ espaços)
    r"(\S+)\s+"                # doc_origin
    r"(\S+)\s+"                # serie
    r"(\d{2}/\d{2}/\d{4})\s+"  # dt_emissao
    r"([\d.,]+)\s+"            # qtd_original
    r"([\d.,]+)\s+"            # qtd_entregue
    r"([\d.,]+)\s+"            # saldo
    r"([\d.,]+)\s+"            # total_nf
    r"([\d.,]+)\s+"            # total_devolvido
    r"([\d.,]+)\s+"            # custo_prod
    r"(E|D)\s+"                # tm  (Entrada / Devolução)
    r"(\d{2}/\d{2}/\d{4})"     # data_lancto
)

# Variante sem custo_prod (alguns relatórios omitem esse campo)
_MOVE_NOCUSTO = re.compile(
    r"^(CLIE|FORNEC)\s+"
    r"(\S+)\s+"
    r"(\S+)\s+"
    r"(.+?)\s{2,}"
    r"(\S+)\s+"
    r"(\S+)\s+"
    r"(\d{2}/\d{2}/\d{4})\s+"
    r"([\d.,]+)\s+"
    r"([\d.,]+)\s+"
    r"([\d.,]+)\s+"
    r"([\d.,]+)\s+"
    r"([\d.,]+)\s+"
    r"(E|D)\s+"
    r"(\d{2}/\d{2}/\d{4})"
)

# Cabeçalho de produto — formato "Produto: X  Descrição: Y  Armazém: Z"
_PROD_LABELED = re.compile(
    r"(?:C[oó]d\.?\s*(?:Produto|Prod\.?)|Produto)[:\s]+(\S+)\s+"
    r"(?:Descri[cç][aã]o?[:\s.]+)?(.+?)\s+"
    r"(?:Armazém?[:\s.]+)(\S+)\s*$",
    re.IGNORECASE,
)

# Cabeçalho de produto — formato "XXXX / DESC / NN"
_PROD_SLASH = re.compile(
    r"^(\S+)\s*/\s*(.+?)\s*/\s*(\S+)\s*$"
)

# Cabeçalho de produto — formato colunar "CODE   LONG DESC   NN" (genérico)
# Valida: primeiro token curto (<= 20 chars), último token parece armazém (2 dígitos ou ≤ 4 chars)
_PROD_COLUMN = re.compile(
    r"^(\S{1,20})\s{2,}(.+?)\s{2,}(\S{1,4})\s*$"
)

# Linhas a ignorar completamente
_SKIP_PATTERNS = (
    re.compile(r"^Total\s+do\s+Produto", re.IGNORECASE),
    re.compile(r"Nota[s]?\s+Fiscal\s+de\s+Retorno", re.IGNORECASE),
    re.compile(r"Materiais\s+Em\s+Poder", re.IGNORECASE),
    re.compile(r"^Tipo\s+C[oó]d", re.IGNORECASE),
    re.compile(r"^[-=]{5,}"),                          # linhas de traço
    re.compile(r"Data\s+de\s+Emiss[aã]o", re.IGNORECASE),
    re.compile(r"^Empresa[:\s]", re.IGNORECASE),
    re.compile(r"^P[aá]gina[:\s]", re.IGNORECASE),
    re.compile(r"^Hora[:\s]", re.IGNORECASE),
    re.compile(r"Qtd\.?\s*Orig", re.IGNORECASE),       # linha de subtotais
)

# Palavras que NUNCA aparecem em cabeçalhos de produto
_NOT_PRODUCT_WORDS = {
    "TIPO", "COD.", "LOJA", "RAZAO", "DOC.", "SERIE", "EMISSAO",
    "TOTAL", "CUSTO", "DATA", "LANCTO", "SALDO",
}


def _is_skip(line: str) -> bool:
    return any(p.search(line) for p in _SKIP_PATTERNS)


def _try_product_header(line: str) -> dict | None:
    """
    Tenta interpretar uma linha como cabeçalho de produto.
    Retorna {'codigo', 'descricao', 'armazem'} ou None.
    """
    # Rejeita linhas de movimentação
    if line.startswith(("CLIE", "FORNEC")):
        return None

    # Formato com rótulos
    m = _PROD_LABELED.match(line)
    if m:
        return {
            "codigo": m.group(1).strip(),
            "descricao": _norm(m.group(2)),
            "armazem": m.group(3).strip(),
        }

    # Formato com barras
    m = _PROD_SLASH.match(line)
    if m:
        return {
            "codigo": m.group(1).strip(),
            "descricao": _norm(m.group(2)),
            "armazem": m.group(3).strip(),
        }

    # Formato colunar genérico
    m = _PROD_COLUMN.match(line)
    if m:
        first = m.group(1).upper()
        # Rejeita se o primeiro token é uma palavra de cabeçalho de coluna
        if first in _NOT_PRODUCT_WORDS:
            return None
        last = m.group(3)
        # Armazem deve ser numérico ou muito curto
        if re.match(r"^\d{1,4}$", last):
            return {
                "codigo": m.group(1).strip(),
                "descricao": _norm(m.group(2)),
                "armazem": last,
            }

    return None


def _parse_movement(line: str) -> dict | None:
    """
    Tenta interpretar linha como movimentação CLIE/FORNEC.
    Retorna dict com campos ou None se não corresponder.
    """
    # Tentativa 1: com custo_prod
    m = _MOVE_FULL.match(line)
    if m:
        return {
            "tipo": m.group(1),
            "codigo_parceiro": m.group(2),
            "loja": m.group(3),
            "razao_social": _norm(m.group(4)),
            "doc_origin": m.group(5),
            "serie": m.group(6),
            "dt_emissao": m.group(7),
            "qtd_original": _br_float(m.group(8)),
            "qtd_entregue": _br_float(m.group(9)),
            "saldo": _br_float(m.group(10)),
            "total_nf": _br_float(m.group(11)),
            "total_devolvido": _br_float(m.group(12)),
            "custo_prod": _br_float(m.group(13)),
            "tm": m.group(14),
            "data_lancto": m.group(15),
        }

    # Tentativa 2: sem custo_prod
    m = _MOVE_NOCUSTO.match(line)
    if m:
        return {
            "tipo": m.group(1),
            "codigo_parceiro": m.group(2),
            "loja": m.group(3),
            "razao_social": _norm(m.group(4)),
            "doc_origin": m.group(5),
            "serie": m.group(6),
            "dt_emissao": m.group(7),
            "qtd_original": _br_float(m.group(8)),
            "qtd_entregue": _br_float(m.group(9)),
            "saldo": _br_float(m.group(10)),
            "total_nf": _br_float(m.group(11)),
            "total_devolvido": _br_float(m.group(12)),
            "custo_prod": 0.0,
            "tm": m.group(13),
            "data_lancto": m.group(14),
        }

    return None


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
        Caminho para o PDF, bytes do PDF, ou objeto BytesIO.
    data_referencia : str, opcional
        Data de referência do relatório (YYYY-MM-DD). Se omitido, usa hoje.
    debug : bool
        Se True, retorna linhas que não puderam ser interpretadas nos warnings.

    Retorna
    -------
    (records, warnings)
        records  : lista de dicts com todos os campos de cada movimentação
        warnings : lista de strings com avisos de parse (linhas não reconhecidas)
    """
    if data_referencia is None:
        data_referencia = datetime.now().strftime("%Y-%m-%d")

    if isinstance(source, bytes):
        source = BytesIO(source)

    records: list[dict] = []
    warnings: list[str] = []
    current_product: dict | None = None
    skip_section: bool = False  # True enquanto estiver no bloco NF Retorno

    with pdfplumber.open(source) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            lines = text.splitlines()

            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue

                # Detectar início de seção NF Retorno → ignorar até próximo produto
                if re.search(r"Nota[s]?\s+Fiscal\s+de\s+Retorno", line, re.IGNORECASE):
                    skip_section = True
                    continue

                # Linhas a pular incondicionalmente
                if _is_skip(line):
                    continue

                # Linha de movimentação (CLIE / FORNEC)
                if line.startswith(("CLIE", "FORNEC")):
                    skip_section = False  # saímos de qualquer seção especial
                    if current_product is None:
                        if debug:
                            warnings.append(
                                f"[p.{page_num}] Movimentação sem produto: {line[:80]}"
                            )
                        continue

                    mv = _parse_movement(line)
                    if mv:
                        mv.update(
                            codigo_produto=current_product["codigo"],
                            descricao=current_product["descricao"],
                            armazem=current_product["armazem"],
                            data_referencia=data_referencia,
                        )
                        records.append(mv)
                    else:
                        warnings.append(
                            f"[p.{page_num}] Linha não parseada: {line[:120]}"
                        )
                    continue

                # Fora de seção especial: tentar cabeçalho de produto
                if not skip_section:
                    ph = _try_product_header(line)
                    if ph:
                        current_product = ph

    return records, warnings
