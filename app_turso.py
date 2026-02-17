import streamlit as st
import pandas as pd
import libsql
import re
import os
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CAMDA Estoque Mestre",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session State ────────────────────────────────────────────────────────────
if "processed_file" not in st.session_state:
    st.session_state.processed_file = None
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;500;700;900&display=swap');
    .stApp { background: #0a0f1a; color: #e0e6ed; font-family: 'Outfit', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 0.5rem 0.8rem !important; max-width: 100% !important; }
    .main-title {
        font-family: 'Outfit', sans-serif; font-weight: 900; font-size: 1.6rem;
        background: linear-gradient(135deg, #00d68f, #00b887);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin: 0.3rem 0;
    }
    .sub-title {
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
        color: #4a5568; text-align: center; margin-bottom: 0.5rem;
    }
    .sync-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.55rem;
        color: #3b82f6; text-align: center; margin-bottom: 0.5rem; opacity: 0.8;
    }
    .stat-row { display: flex; gap: 6px; margin-bottom: 0.5rem; }
    .stat-card {
        flex: 1; background: linear-gradient(135deg, #111827, #1a2332);
        border: 1px solid #1e293b; border-radius: 10px;
        padding: 8px 10px; text-align: center;
    }
    .stat-value {
        font-family: 'JetBrains Mono', monospace; font-size: 1.15rem;
        font-weight: 700; color: #00d68f;
    }
    .stat-value.red { color: #ff4757; }
    .stat-value.amber { color: #ffa502; }
    .stat-value.purple { color: #a55eea; }
    .stat-value.blue { color: #3b82f6; }
    .stat-label {
        font-size: 0.6rem; color: #64748b;
        text-transform: uppercase; letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# REGEX PRÉ-COMPILADO (compila 1x no import, não 1x por produto)
# ══════════════════════════════════════════════════════════════════════════════
_RE_FALTA = re.compile(r"falt(?:a|ando|am|ou|aram|\.?)(?:\s+(?:de|do|da))?\s+(\d+)\s*(.*)")
_RE_FALTA_SHORT = re.compile(r"^f\.?\s+(\d+)\s*(.*)")
_RE_SOBRA = re.compile(r"(?:sobr(?:a|ando|am|ou|aram|\.?)|pass(?:a|ando|aram|ou|\.?))\s+(\d+)\s*(.*)")
_RE_SOBRA_SHORT = re.compile(r"^s\.?\s+(\d+)\s*(.*)")
_RE_FALTA_MID = re.compile(r"falt\w*\s+(?:de\s+)?(\d+)")
_RE_SOBRA_MID = re.compile(r"(?:sobr|pass)\w*\s+(\d+)")
_RE_ONLY_NUMBER = re.compile(r"^\d+([.,]\d+)?$")
_RE_COD_PROD = re.compile(r"^(\d+)\s*-\s*(.+)$")
_RE_SPACES = re.compile(r"\s+")
_RE_DIGITS = re.compile(r"\d+")
_RE_ALPHA = re.compile(r"[a-zA-Z]")
_RE_NON_ALNUM = re.compile(r"[^A-Z0-9]")

_KEYWORDS_DANIFICADO = frozenset([
    "danificad", "avaria", "avariado", "quebrad", "defeito",
    "vencid", "impropri", "vazand", "estraga", "molhad",
    "rasgad", "furad", "amassd", "amassad", "contaminad",
])


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE — conexão + init de tabelas UMA VEZ SÓ
# ══════════════════════════════════════════════════════════════════════════════

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.environ.get(key, "")


TURSO_DATABASE_URL = _get_secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _get_secret("TURSO_AUTH_TOKEN")
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camda_local.db")
_using_cloud = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)


@st.cache_resource
def _get_connection():
    """Cria conexão UMA VEZ e já inicializa tabelas + migrações."""
    if _using_cloud:
        conn = libsql.connect(
            LOCAL_DB_PATH,
            sync_url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN,
        )
        conn.sync()
    else:
        conn = libsql.connect(LOCAL_DB_PATH)

    # ── Criar tabelas (roda 1x, não a cada get_db()) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estoque_mestre (
            codigo TEXT PRIMARY KEY,
            produto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            qtd_sistema INTEGER NOT NULL DEFAULT 0,
            qtd_fisica INTEGER DEFAULT 0,
            diferenca INTEGER DEFAULT 0,
            nota TEXT DEFAULT '',
            status TEXT DEFAULT 'ok',
            ultima_contagem TEXT DEFAULT '',
            criado_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historico_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL,
            arquivo TEXT DEFAULT '',
            total_produtos_lote INTEGER DEFAULT 0,
            novos INTEGER DEFAULT 0,
            atualizados INTEGER DEFAULT 0,
            divergentes INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS principios_ativos (
            produto TEXT NOT NULL,
            principio_ativo TEXT NOT NULL,
            categoria TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reposicao_loja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            qtd_vendida INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            reposto INTEGER DEFAULT 0,
            reposto_em TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vendas_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            grupo TEXT NOT NULL,
            qtd_vendida INTEGER NOT NULL DEFAULT 0,
            qtd_estoque INTEGER NOT NULL DEFAULT 0,
            data_upload TEXT NOT NULL
        )
    """)
    conn.commit()

    # ── Migrações (roda 1x) ──
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(reposicao_loja)").fetchall()}
        for col, definition in [
            ("qtd_vendida", "INTEGER NOT NULL DEFAULT 0"),
            ("reposto", "INTEGER DEFAULT 0"),
            ("reposto_em", "TEXT DEFAULT ''"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE reposicao_loja ADD COLUMN {col} {definition}")
        conn.commit()
    except Exception:
        pass

    return conn


def get_db():
    """Retorna conexão pronta (tabelas já criadas no cache)."""
    conn = _get_connection()
    if _using_cloud and not st.session_state.get("_synced"):
        try:
            conn.sync()
            st.session_state["_synced"] = True
        except Exception:
            pass
    return conn


def sync_db():
    """Sync com Turso (chamar UMA VEZ após todas as escritas)."""
    if _using_cloud:
        try:
            _get_connection().sync()
        except Exception as e:
            st.warning(f"⚠️ Sync falhou: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# BLACKLIST DE REPOSIÇÃO
# ══════════════════════════════════════════════════════════════════════════════
CATEGORIAS_EXCLUIDAS_REPOSICAO = frozenset({
    # Defensivos / campo
    "HERBICIDAS", "FUNGICIDAS", "INSETICIDAS", "NEMATICIDAS", "ÓLEOS",
    "ADUBOS FOLIARES", "ADUBOS QUÍMICOS", "ADUBOS CORRETIVOS",
    "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO", "SUPLEMENTO MINERAL",
    # Sementes
    "SEMENTES",
    # Veterinários / medicamentos (todos os grupos do BI)
    "MEDICAMENTOS", "MEDICAMENTOS VETERINÁRIOS", "MEDICAMENTOS VETERINARIOS",
    "VACINA AFTOSA", "VACINAS DIVERSAS/SOROS",
    "ANTIBIOTICOS/ANTI-INFLAMATORIO",
    "ANESTESICO/ANALGESICO/DIURETIC",
    "ANTITOXICOS",
    "VERMIFUGOS",
    "MOSQUICIDA/CARRAPATICIDA/BERNI",
    "UNGUENTOS/POMADAS",
    "HOMEOPATICO",
    "HORMONIOS LEITEIROS",
    "TONICO MINERAL/VITAMINAS",
    "REPRODUCAO ANIMAL",
    "REPRODUTORES",
    "IDENTIFICACAO ANIMAL",
    "INOCULANTES P/ SILAGEM",
    "DIETA ANIMAL",
    "RATICIDAS",
})

CATEGORIA_PRIORITY = [
    "HERBICIDAS", "FUNGICIDAS", "INSETICIDAS", "NEMATICIDAS",
    "ADUBOS FOLIARES", "ADUBOS QUÍMICOS", "ADUBOS CORRETIVOS",
    "ADJUVANTES", "ÓLEOS", "SEMENTES", "MEDICAMENTOS",
]
_CAT_PRIORITY_MAP = {cat: i for i, cat in enumerate(CATEGORIA_PRIORITY)}


# ══════════════════════════════════════════════════════════════════════════════
# LEITURAS DO BANCO — simples e diretas
# ══════════════════════════════════════════════════════════════════════════════
_STOCK_COLS = ["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica",
               "diferenca", "nota", "status", "ultima_contagem", "criado_em"]


def get_current_stock() -> pd.DataFrame:
    try:
        rows = get_db().execute("SELECT * FROM estoque_mestre ORDER BY categoria, produto").fetchall()
        return pd.DataFrame(rows, columns=_STOCK_COLS)
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar estoque: {e}")
        return pd.DataFrame(columns=_STOCK_COLS)


def get_stock_count() -> int:
    try:
        row = get_db().execute("SELECT COUNT(*) FROM estoque_mestre").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def get_reposicao_pendente() -> pd.DataFrame:
    cols = ["id", "codigo", "produto", "categoria", "qtd_vendida", "criado_em"]
    try:
        conn = get_db()
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        excl = list(CATEGORIAS_EXCLUIDAS_REPOSICAO)
        ph = ",".join(["?" for _ in excl])
        rows = conn.execute(f"""
            SELECT id, codigo, produto, categoria, qtd_vendida, criado_em
            FROM reposicao_loja
            WHERE reposto = 0 AND criado_em >= ? AND qtd_vendida > 0
              AND UPPER(categoria) NOT IN ({ph})
            ORDER BY criado_em DESC
        """, [cutoff] + excl).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar reposição: {e}")
        return pd.DataFrame(columns=cols)


def get_historico_uploads() -> pd.DataFrame:
    cols = ["data", "tipo", "arquivo", "total_produtos_lote", "novos", "atualizados", "divergentes"]
    try:
        rows = get_db().execute(
            "SELECT data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes "
            "FROM historico_uploads ORDER BY id DESC LIMIT 20"
        ).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)


# ══════════════════════════════════════════════════════════════════════════════
# PRINCÍPIOS ATIVOS — mapeamento produto ↔ princípio ativo
# ══════════════════════════════════════════════════════════════════════════════

_PA_COLS = ["produto", "principio_ativo", "categoria"]


def load_principios_ativos_from_excel(filepath: str) -> list:
    """Lê o Excel de princípios ativos e retorna lista de dicts."""
    try:
        df = pd.read_excel(filepath, header=0)
        col_prod = col_pa = col_cat = None
        for c in df.columns:
            cu = str(c).strip().upper()
            if cu == "PRODUTO":
                col_prod = c
            elif "PRINC" in cu or "ATIVO" in cu:
                col_pa = c
            elif "CATEG" in cu:
                col_cat = c
        if not col_prod or not col_pa:
            return []
        records = []
        for _, row in df.iterrows():
            prod = str(row.get(col_prod, "")).strip()
            pa = str(row.get(col_pa, "")).strip()
            cat = str(row.get(col_cat, "")).strip() if col_cat else ""
            if prod and pa and prod.upper() not in ("NAN", "NONE") and pa.upper() not in ("NAN", "NONE"):
                records.append({"produto": prod, "principio_ativo": pa, "categoria": cat})
        return records
    except Exception:
        return []


def sync_principios_ativos(records: list):
    """Sincroniza tabela de princípios ativos no banco."""
    if not records:
        return
    try:
        conn = get_db()
        conn.execute("DELETE FROM principios_ativos")
        conn.executemany(
            "INSERT INTO principios_ativos (produto, principio_ativo, categoria) VALUES (?, ?, ?)",
            [(r["produto"], r["principio_ativo"], r["categoria"]) for r in records]
        )
        conn.commit()
        sync_db()
    except Exception:
        pass


def get_principios_ativos() -> pd.DataFrame:
    """Retorna DataFrame com mapeamento produto ↔ princípio ativo."""
    try:
        rows = get_db().execute("SELECT produto, principio_ativo, categoria FROM principios_ativos").fetchall()
        return pd.DataFrame(rows, columns=_PA_COLS)
    except Exception:
        return pd.DataFrame(columns=_PA_COLS)


def get_pa_count() -> int:
    try:
        row = get_db().execute("SELECT COUNT(*) FROM principios_ativos").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def search_by_principio_ativo(search_term: str, df_pa: pd.DataFrame) -> set:
    """Retorna set de nomes de produtos que contêm o princípio ativo buscado."""
    if df_pa.empty:
        return set()
    mask = df_pa["principio_ativo"].str.contains(search_term, case=False, na=False)
    return set(df_pa.loc[mask, "produto"].str.upper())


def reset_db():
    try:
        conn = get_db()
        conn.execute("DELETE FROM estoque_mestre")
        conn.execute("DELETE FROM historico_uploads")
        conn.execute("DELETE FROM reposicao_loja")
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao limpar banco: {e}")


def marcar_reposto(item_id: int):
    try:
        conn = get_db()
        conn.execute(
            "UPDATE reposicao_loja SET reposto = 1, reposto_em = ? WHERE id = ?",
            [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id]
        )
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao marcar reposto: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO E PARSING — otimizados
# ══════════════════════════════════════════════════════════════════════════════

_CLASSIFY_RULES = [
    ("HERBICIDAS", ("HERBICIDA",)),
    ("FUNGICIDAS", ("FUNGICIDA",)),
    ("INSETICIDAS", ("INSETICIDA",)),
    ("NEMATICIDAS", ("NEMATICIDA",)),
    ("ADUBOS FOLIARES", ("ADUBO FOLIAR",)),
    ("ADUBOS QUÍMICOS", ("ADUBO Q",)),
    ("ADUBOS CORRETIVOS", ("ADUBO CORRETIVO", "CALCARIO", "CALCÁRIO")),
    ("ÓLEOS", ("OLEO", "ÓLEO")),
    ("SEMENTES", ("SEMENTE",)),
    ("ADJUVANTES", ("ADJUVANTE", "ESPALHANTE")),
    ("MEDICAMENTOS", ("MEDICAMENTO", "VERMIFUGO", "VERMÍFUGO", "VACINA", "ANTIBIOTICO", "ANTIBIÓTICO")),
]

_GRUPO_MAP = {
    "ADUBOS FOLIARES": "ADUBOS FOLIARES",
    "ADUBOS QUIMICOS": "ADUBOS QUÍMICOS",
    "ADUBOS CORRETIVOS": "ADUBOS CORRETIVOS",
    "HERBICIDAS": "HERBICIDAS", "FUNGICIDAS": "FUNGICIDAS",
    "INSETICIDAS": "INSETICIDAS", "NEMATICIDAS": "NEMATICIDAS",
    "OLEO MINERAL E VEGETAL": "ÓLEOS", "ADJUVANTES": "ADJUVANTES",
    "SEMENTES": "SEMENTES",
    # Veterinários — normaliza para o nome exato da blacklist
    "MEDICAMENTOS": "MEDICAMENTOS",
    "MEDICAMENTOS VETERINÁRIOS": "MEDICAMENTOS",
    "MEDICAMENTOS VETERINARIOS": "MEDICAMENTOS",
    "VACINA AFTOSA": "VACINA AFTOSA",
    "VACINAS DIVERSAS/SOROS": "VACINAS DIVERSAS/SOROS",
    "ANTIBIOTICOS/ANTI-INFLAMATORIO": "ANTIBIOTICOS/ANTI-INFLAMATORIO",
    "ANESTESICO/ANALGESICO/DIURETIC": "ANESTESICO/ANALGESICO/DIURETIC",
    "ANTITOXICOS": "ANTITOXICOS",
    "VERMIFUGOS": "VERMIFUGOS",
    "MOSQUICIDA/CARRAPATICIDA/BERNI": "MOSQUICIDA/CARRAPATICIDA/BERNI",
    "UNGUENTOS/POMADAS": "UNGUENTOS/POMADAS",
    "HOMEOPATICO": "HOMEOPATICO",
    "HORMONIOS LEITEIROS": "HORMONIOS LEITEIROS",
    "TONICO MINERAL/VITAMINAS": "TONICO MINERAL/VITAMINAS",
    "REPRODUCAO ANIMAL": "REPRODUCAO ANIMAL",
    "REPRODUTORES": "REPRODUTORES",
    "IDENTIFICACAO ANIMAL": "IDENTIFICACAO ANIMAL",
    "INOCULANTES P/ SILAGEM": "INOCULANTES P/ SILAGEM",
    "DIETA ANIMAL": "DIETA ANIMAL",
    "RATICIDAS": "RATICIDAS",
}

_SHORT_PREFIXES = [
    "HERBICIDA ", "FUNGICIDA ", "INSETICIDA ", "NEMATICIDA ",
    "ADUBO FOLIAR ", "ADUBO Q.", "OLEO VEGETAL ", "OLEO MINERAL ",
    "ÓLEO VEGETAL ", "ÓLEO MINERAL ", "ADJUVANTE ", "SEMENTE ",
    "MEDICAMENTO ",
]


def classify_product(name: str) -> str:
    n = name.upper()
    for cat, keywords in _CLASSIFY_RULES:
        for kw in keywords:
            if kw in n:
                return cat
    return "OUTROS"


def normalize_grupo(grupo: str) -> str:
    return _GRUPO_MAP.get(grupo.strip().upper(), grupo.strip().upper())


def short_name(prod: str) -> str:
    up = prod.upper()
    for p in _SHORT_PREFIXES:
        if up.startswith(p):
            return prod[len(p):].strip()
    return prod


def parse_annotation(nota: str, qtd_sistema: int) -> tuple:
    """Retorna: (qtd_fisica, diferenca, observacao, status_type)"""
    if not nota:
        return (qtd_sistema, 0, "", "ok")
    text = nota.strip()
    if not text or text.lower() in ("nan", "none"):
        return (qtd_sistema, 0, "", "ok")

    tl = _RE_SPACES.sub(" ", text.lower()).strip()

    # FALTA
    m = _RE_FALTA.match(tl)
    if m:
        f = int(m.group(1))
        return (qtd_sistema - f, -f, m.group(2).strip(), "falta")
    m = _RE_FALTA_SHORT.match(tl)
    if m:
        f = int(m.group(1))
        return (qtd_sistema - f, -f, m.group(2).strip(), "falta")

    # SOBRA
    m = _RE_SOBRA.match(tl)
    if m:
        s = int(m.group(1))
        return (qtd_sistema + s, s, m.group(2).strip(), "sobra")
    m = _RE_SOBRA_SHORT.match(tl)
    if m:
        s = int(m.group(1))
        return (qtd_sistema + s, s, m.group(2).strip(), "sobra")

    # DANIFICADOS
    if any(k in tl for k in _KEYWORDS_DANIFICADO):
        return (qtd_sistema, 0, text, "danificado")

    # Fallback
    m = _RE_FALTA_MID.search(tl)
    if m:
        f = int(m.group(1))
        return (qtd_sistema - f, -f, text, "falta")
    m = _RE_SOBRA_MID.search(tl)
    if m:
        s = int(m.group(1))
        return (qtd_sistema + s, s, text, "sobra")

    return (qtd_sistema, 0, text, "ok")


# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO E PARSING DE PLANILHAS
# ══════════════════════════════════════════════════════════════════════════════

def detect_format(df_raw: pd.DataFrame) -> str:
    for i in range(min(10, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        row_text = " ".join(vals)
        if any(x in row_text for x in ("QTDD - VENDIDA", "QTDD ESTOQUE", "GRUPO DE PRODUTO")):
            return "vendas"
        if "PRODUTO" in vals and any("QUANTIDADE" in v or v == "QTD" for v in vals):
            return "estoque"
    return "desconhecido"


def _find_header(df_raw, check_fn, max_rows=15):
    for i in range(min(max_rows, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        if check_fn(vals):
            return i
    return None


def parse_estoque_format(df_raw: pd.DataFrame) -> tuple:
    header_idx = _find_header(df_raw, lambda vals: "PRODUTO" in vals and any("QUANTIDADE" in v or v == "QTD" for v in vals))
    if header_idx is None:
        return (False, "Cabeçalho não encontrado. Preciso de 'Produto' e 'Quantidade'.")

    df = df_raw.iloc[header_idx + 1:].copy()
    raw_cols = df_raw.iloc[header_idx].tolist()
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_cols)]

    col_map = {}
    for c in df.columns:
        cu = c.upper().strip()
        if cu == "PRODUTO" and "produto" not in col_map:
            col_map["produto"] = c
        elif ("QUANTIDADE" in cu or cu == "QTD") and "qtd" not in col_map:
            col_map["qtd"] = c
        elif cu in ("CÓDIGO", "CODIGO", "COD") and "codigo" not in col_map:
            col_map["codigo"] = c
        elif ("OBS" in cu or "NOTA" in cu or "DIFEREN" in cu or "ANOTA" in cu) and "nota" not in col_map:
            col_map["nota"] = c

    if "produto" not in col_map or "qtd" not in col_map:
        return (False, f"Colunas: {list(df.columns)} — falta 'Produto' ou 'Quantidade'.")

    # Procura coluna de nota em colunas restantes
    if "nota" not in col_map:
        used = set(col_map.values())
        for c in df.columns:
            if c not in used:
                sample = df[c].dropna().astype(str).head(20)
                if sample.apply(lambda x: bool(_RE_ALPHA.search(x)) and x.upper() not in ("NAN", "NONE", "")).any():
                    col_map["nota"] = c
                    break

    records = []
    col_prod = col_map["produto"]
    col_qtd = col_map["qtd"]
    col_cod = col_map.get("codigo")
    col_nota = col_map.get("nota")

    for _, row in df.iterrows():
        produto = str(row.get(col_prod, "")).strip()
        if not produto or produto.upper() in ("NAN", "NONE", "TOTAL", "PRODUTO", "ROLLUP"):
            continue

        try:
            raw_val = row.get(col_qtd)
            if pd.isna(raw_val):
                continue
            qtd_sistema = int(float(raw_val))
            if qtd_sistema <= 0:
                continue
        except (ValueError, TypeError):
            continue

        codigo = ""
        if col_cod:
            codigo = str(row.get(col_cod, "")).strip()
            if codigo.upper() in ("NAN", "NONE", ""):
                codigo = ""
        if not codigo:
            codigo = "AUTO_" + _RE_NON_ALNUM.sub("", produto.upper())[:20]

        nota_raw = ""
        if col_nota:
            nota_raw = str(row.get(col_nota, "")).strip()
            if nota_raw.upper() in ("NAN", "NONE"):
                nota_raw = ""
            if _RE_ONLY_NUMBER.match(nota_raw):
                nota_raw = ""

        categoria = classify_product(produto)
        qtd_fisica, diferenca, obs, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo, "produto": produto, "categoria": categoria,
            "qtd_sistema": qtd_sistema, "qtd_fisica": qtd_fisica,
            "diferenca": diferenca, "nota": obs, "status": status,
        })

    return (True, records) if records else (False, "Nenhum dado válido na planilha de estoque.")


def parse_vendas_format(df_raw: pd.DataFrame) -> tuple:
    header_idx = _find_header(
        df_raw,
        lambda vals: "PRODUTO" in vals and ("QTDD" in " ".join(vals) or "VENDIDA" in " ".join(vals))
    )
    if header_idx is None:
        return (False, "Cabeçalho não encontrado no formato vendas.")

    df = df_raw.iloc[header_idx + 1:].copy()
    raw_cols = df_raw.iloc[header_idx].tolist()
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_cols)]

    col_grupo = col_produto = col_qtd_vendida = col_qtd_estoque = col_nota = None

    for c in df.columns:
        cu = c.upper().strip()
        if "GRUPO" in cu and not col_grupo:
            col_grupo = c
        elif cu == "PRODUTO" and not col_produto:
            col_produto = c
        elif "VENDIDA" in cu and not col_qtd_vendida:
            col_qtd_vendida = c
        elif "ESTOQUE" in cu and not col_qtd_estoque:
            col_qtd_estoque = c
        elif ("OBS" in cu or "NOTA" in cu or "ANOTA" in cu) and not col_nota:
            col_nota = c

    if not col_nota:
        for c in df.columns:
            if "CUSTO" in c.upper().strip():
                col_nota = c
                break

    if not col_produto:
        return (False, f"Coluna 'PRODUTO' não encontrada. Colunas: {list(df.columns)}")
    if not col_qtd_estoque and not col_qtd_vendida:
        return (False, "Nenhuma coluna de quantidade encontrada.")

    records = []
    zerados = []
    current_grupo = "OUTROS"

    for _, row in df.iterrows():
        if col_grupo:
            g = str(row.get(col_grupo, "")).strip()
            if g and g.upper() not in ("NAN", "NONE", ""):
                current_grupo = g

        raw_prod = str(row.get(col_produto, "")).strip()
        if not raw_prod or raw_prod.upper() in ("NAN", "NONE", "ROLLUP"):
            continue

        m = _RE_COD_PROD.match(raw_prod)
        if m:
            codigo, produto = m.group(1).strip(), m.group(2).strip()
        else:
            codigo = "AUTO_" + _RE_NON_ALNUM.sub("", raw_prod.upper())[:20]
            produto = raw_prod

        qtd_sistema = qtd_vendida_val = 0
        if col_qtd_estoque:
            try:
                val = row.get(col_qtd_estoque)
                if pd.notna(val):
                    qtd_sistema = int(float(val))
            except (ValueError, TypeError):
                pass
        if col_qtd_vendida:
            try:
                val = row.get(col_qtd_vendida)
                if pd.notna(val):
                    qtd_vendida_val = int(float(val))
            except (ValueError, TypeError):
                pass

        if qtd_sistema <= 0:
            if qtd_vendida_val > 0:
                zerados.append({
                    "codigo": codigo, "produto": produto,
                    "grupo": normalize_grupo(current_grupo),
                    "qtd_vendida": qtd_vendida_val, "qtd_estoque": 0,
                })
            continue

        nota_raw = ""
        if col_nota:
            nv = str(row.get(col_nota, "")).strip()
            if nv.upper() not in ("NAN", "NONE", "") and not _RE_ONLY_NUMBER.match(nv):
                nota_raw = nv

        categoria = normalize_grupo(current_grupo)
        if categoria in ("OUTROS", ""):
            categoria = classify_product(produto)

        qtd_fisica, diferenca, obs, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo, "produto": produto, "categoria": categoria,
            "qtd_sistema": qtd_sistema, "qtd_fisica": qtd_fisica,
            "diferenca": diferenca, "nota": obs, "status": status,
            "qtd_vendida": qtd_vendida_val,
        })

    return (True, records, zerados) if records else (False, "Nenhum dado válido na planilha de vendas.", [])


def read_excel_to_records(uploaded_file) -> tuple:
    try:
        df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    except Exception as e:
        return (False, f"Erro ao ler arquivo: {e}", [])

    fmt = detect_format(df_raw)
    if fmt == "vendas":
        return parse_vendas_format(df_raw)
    elif fmt == "estoque":
        ok, result = parse_estoque_format(df_raw)
        return (ok, result, [])
    else:
        ok, result = parse_estoque_format(df_raw)
        if ok:
            return (ok, result, [])
        ok2, result2, zerados2 = parse_vendas_format(df_raw)
        if ok2:
            return (ok2, result2, zerados2)
        return (False, "Formato não reconhecido.", [])


# ══════════════════════════════════════════════════════════════════════════════
# UPLOADS — batch inserts + sync único no final
# ══════════════════════════════════════════════════════════════════════════════

def upload_mestre(records: list) -> tuple:
    """Recebe records já parseados (sem re-parsear o arquivo)."""
    try:
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("DELETE FROM estoque_mestre")

        # BATCH INSERT via executemany
        conn.executemany("""
            INSERT INTO estoque_mestre
                (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (r["codigo"], r["produto"], r["categoria"],
             r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
             r["nota"], r["status"], now, now)
            for r in records
        ])

        n_div = sum(1 for r in records if r["status"] != "ok")
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "MESTRE", "", len(records), len(records), 0, n_div])

        conn.commit()
        sync_db()  # Sync UMA VEZ no final
        return (True, f"✅ Mestre: {len(records)} produtos ({n_div} divergências)")
    except Exception as e:
        return (False, f"❌ Erro: {e}")


def upload_parcial(records: list, zerados: list = None) -> tuple:
    """Recebe records já parseados e lista opcional de códigos com estoque zerado."""
    try:
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Buscar códigos existentes (1 query)
        existing = {row[0] for row in conn.execute("SELECT codigo FROM estoque_mestre").fetchall()}

        # Remover produtos que zeraram o estoque
        if zerados:
            codigos_zerados = [z["codigo"] if isinstance(z, dict) else z for z in zerados]
            codigos_remover = [c for c in codigos_zerados if c in existing]
            if codigos_remover:
                ph = ",".join(["?" for _ in codigos_remover])
                conn.execute(f"DELETE FROM estoque_mestre WHERE codigo IN ({ph})", codigos_remover)

        novos_data, update_data = [], []
        for r in records:
            row_data = (
                r["produto"], r["categoria"], r["qtd_sistema"], r["qtd_fisica"],
                r["diferenca"], r["nota"], r["status"], now, r["codigo"]
            )
            if r["codigo"] in existing:
                update_data.append(row_data)
            else:
                novos_data.append((
                    r["codigo"], r["produto"], r["categoria"],
                    r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                    r["nota"], r["status"], now, now
                ))

        # BATCH updates e inserts
        if update_data:
            conn.executemany("""
                UPDATE estoque_mestre SET
                    produto=?, categoria=?, qtd_sistema=?, qtd_fisica=?,
                    diferenca=?, nota=?, status=?, ultima_contagem=?
                WHERE codigo=?
            """, update_data)

        if novos_data:
            conn.executemany("""
                INSERT INTO estoque_mestre
                    (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, novos_data)

        # Reposição loja
        n_repo = _detectar_reposicao_batch(records, conn, now)

        n_div = sum(1 for r in records if r["status"] != "ok")
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "PARCIAL", "", len(records), len(novos_data), len(update_data), n_div])

        conn.commit()
        sync_db()  # Sync UMA VEZ no final

        parts = [f"✅ Parcial: {len(records)} produtos"]
        if update_data:
            parts.append(f"{len(update_data)} atualizados")
        if novos_data:
            parts.append(f"{len(novos_data)} novos")
        if n_div:
            parts.append(f"{n_div} divergências")
        if n_repo:
            parts.append(f"🏪 {n_repo} para repor na loja")
        return (True, " · ".join(parts))
    except Exception as e:
        return (False, f"❌ Erro: {e}")


def _detectar_reposicao_batch(records: list, conn, now: str) -> int:
    """Detecta reposição em batch."""
    pending = {row[0] for row in conn.execute("SELECT codigo FROM reposicao_loja WHERE reposto = 0").fetchall()}
    to_insert = []

    for r in records:
        qtd_v = r.get("qtd_vendida", 0)
        if qtd_v <= 0:
            continue
        cat = str(r.get("categoria", "")).strip().upper()
        if cat in CATEGORIAS_EXCLUIDAS_REPOSICAO:
            continue
        if r["codigo"] in pending:
            continue
        to_insert.append((r["codigo"], r["produto"], r["categoria"], qtd_v, now))
        pending.add(r["codigo"])

    if to_insert:
        conn.executemany("""
            INSERT INTO reposicao_loja (codigo, produto, categoria, qtd_vendida, criado_em)
            VALUES (?, ?, ?, ?, ?)
        """, to_insert)

    return len(to_insert)


# ══════════════════════════════════════════════════════════════════════════════
# TREEMAP — otimizado com list join em vez de concatenação
# ══════════════════════════════════════════════════════════════════════════════

def sort_categorias(cats):
    mx = len(CATEGORIA_PRIORITY)
    return sorted(cats, key=lambda c: (_CAT_PRIORITY_MAP.get(c, mx), c))


def build_css_treemap(df: pd.DataFrame, filter_cat: str = "TODOS") -> str:
    if df.empty:
        return '<div style="color:#64748b;text-align:center;padding:40px;">Nenhum produto para exibir</div>'

    if filter_cat != "TODOS":
        df = df[df["categoria"] == filter_cat]
    if df.empty:
        return '<div style="color:#64748b;text-align:center;padding:40px;">Nenhum produto nesta categoria</div>'

    # Agrupar por categoria
    categories = {}
    for _, row in df.iterrows():
        categories.setdefault(row["categoria"], []).append(row)

    parts = []
    for cat in sort_categorias(list(categories.keys())):
        rows = categories[cat]
        prods = []

        for r in sorted(rows, key=lambda x: str(x["produto"])):
            qs = int(r["qtd_sistema"])
            qf = int(r["qtd_fisica"]) if pd.notnull(r.get("qtd_fisica")) else qs
            diff = int(r["diferenca"]) if pd.notnull(r.get("diferenca")) else 0
            stat = str(r.get("status", "ok"))
            note = str(r.get("nota", "")) if pd.notnull(r.get("nota")) else ""

            if stat == "danificado":
                bg, txt = "#a55eea", "#fff"
                nums = _RE_DIGITS.findall(note)
                info = f"{qs} · AV:{nums[0]}" if nums else f"{qs} · AVARIA"
            elif diff == 0:
                bg, txt = "#00d68f", "#0a2e1a"
                info = str(qs)
            elif diff < 0:
                bg, txt = "#ff4757", "#fff"
                info = f"{qf} (F {abs(diff)})"
            else:
                bg, txt = "#ffa502", "#fff"
                info = f"{qf} (S {diff})"

            contagem = str(r.get("ultima_contagem", ""))
            border = "border:2px dashed #64748b!important;opacity:0.6;" if not contagem or contagem in ("", "nan", "None") else ""

            prods.append(
                f'<div style="width:110px;height:60px;background:{bg};color:{txt};'
                f'border-radius:4px;padding:4px;margin:2px;display:flex;flex-direction:column;'
                f'justify-content:center;align-items:center;overflow:hidden;'
                f'border:1px solid rgba(0,0,0,0.1);{border}">'
                f'<div style="font-size:0.55rem;font-weight:700;text-align:center;width:100%;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{short_name(r["produto"])}</div>'
                f'<div style="font-size:0.65rem;opacity:0.9;font-family:monospace;font-weight:bold;margin-top:2px;">{info}</div>'
                f'</div>'
            )

        parts.append(
            f'<div style="width:100%;background:#111827;border-radius:8px;padding:8px;'
            f'margin-bottom:8px;border:1px solid #1e293b;">'
            f'<div style="font-size:0.75rem;color:#64748b;font-weight:700;text-transform:uppercase;'
            f'margin-bottom:6px;border-bottom:1px solid #1e293b;padding-bottom:4px;">'
            f'{cat} <span style="font-size:0.6rem;color:#4a5568;font-weight:400;">({len(rows)})</span></div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:2px;">{"".join(prods)}</div></div>'
        )

    return f'<div style="display:flex;flex-direction:column;min-height:450px;">{"".join(parts)}</div>'


# ══════════════════════════════════════════════════════════════════════════════
# VENDAS — salvar/carregar dados de vendas para gráficos
# ══════════════════════════════════════════════════════════════════════════════

def save_vendas_historico(records: list, grupo_map: dict, zerados: list = None):
    """Salva dados de vendas no histórico para gráficos (inclui zerados)."""
    try:
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Limpar anterior do mesmo dia
        hoje = datetime.now().strftime("%Y-%m-%d")
        conn.execute("DELETE FROM vendas_historico WHERE data_upload LIKE ?", [f"{hoje}%"])
        rows = []
        for r in records:
            qtd_v = r.get("qtd_vendida", 0)
            qtd_e = r.get("qtd_sistema", 0)
            grupo = r.get("categoria", "OUTROS")
            rows.append((r["codigo"], r["produto"], grupo, qtd_v, qtd_e, now))
        # Incluir zerados
        if zerados:
            for z in zerados:
                if isinstance(z, dict):
                    rows.append((z["codigo"], z["produto"], z.get("grupo", "OUTROS"), z.get("qtd_vendida", 0), 0, now))
        if rows:
            conn.executemany("""
                INSERT INTO vendas_historico (codigo, produto, grupo, qtd_vendida, qtd_estoque, data_upload)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            sync_db()
    except Exception:
        pass


def get_vendas_historico() -> pd.DataFrame:
    try:
        rows = get_db().execute(
            "SELECT codigo, produto, grupo, qtd_vendida, qtd_estoque, data_upload FROM vendas_historico ORDER BY qtd_vendida DESC"
        ).fetchall()
        if rows:
            return pd.DataFrame(rows, columns=["codigo", "produto", "grupo", "qtd_vendida", "qtd_estoque", "data_upload"])
    except Exception:
        pass
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY — tema dark consistente com o dashboard
# ══════════════════════════════════════════════════════════════════════════════

_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Outfit, sans-serif", color="#e0e6ed", size=11),
    margin=dict(l=10, r=10, t=40, b=10),
)

_DEFAULT_LEGEND = dict(
    bgcolor="rgba(17,24,39,0.8)", bordercolor="#1e293b", borderwidth=1,
    font=dict(size=10, color="#94a3b8"),
)

_GROUP_COLORS = {
    "HERBICIDAS": "#3b82f6", "INSETICIDAS": "#00d68f",
    "ADUBOS FOLIARES": "#a55eea", "ADUBOS QUÍMICOS": "#8b5cf6",
    "FUNGICIDAS": "#ffa502", "MATURADORES": "#06b6d4",
    "BIOLOGICOS E INOCULANTES": "#10b981", "SEMENTES DE MILHO": "#f59e0b",
    "SUPLEMENTO MINERAL": "#ec4899", "LONAS": "#6366f1",
    "ANTIBIOTICOS/ANTI-INFLAMATORIO": "#f472b6",
    "ACESSORIOS DE CERCA ELETRICA": "#818cf8",
    "ADJUVANTES/ESPALHANTES ADESIVO": "#2dd4bf",
}


def _get_color(grupo: str) -> str:
    return _GROUP_COLORS.get(grupo, "#64748b")


def build_vendas_tab(df_vendas: pd.DataFrame):
    """Renderiza a aba completa de gráficos de vendas."""
    if df_vendas.empty:
        st.info("📊 Nenhum dado de vendas carregado ainda. Faça upload de uma planilha de vendas para ativar os gráficos.")
        return

    # ── Dados agregados por grupo ────────────────────────────────────────
    df_grupo = df_vendas.groupby("grupo", as_index=False).agg(
        qtd_vendida=("qtd_vendida", "sum"),
        qtd_estoque=("qtd_estoque", "sum"),
        produtos=("codigo", "nunique"),
    ).sort_values("qtd_vendida", ascending=False)

    total_vendido = int(df_grupo["qtd_vendida"].sum())
    total_estoque = int(df_grupo["qtd_estoque"].sum())
    total_skus = int(df_vendas["codigo"].nunique())
    n_zerados = int((df_vendas["qtd_estoque"] <= 0).sum())
    pct_ruptura = round((n_zerados / max(total_skus, 1)) * 100)

    # ── KPIs ─────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="stat-value">{total_vendido:,}</div><div class="stat-label">Vendidos</div></div>
        <div class="stat-card"><div class="stat-value blue">{total_skus}</div><div class="stat-label">Produtos</div></div>
        <div class="stat-card"><div class="stat-value red">{n_zerados}</div><div class="stat-label">Zerados</div></div>
        <div class="stat-card"><div class="stat-value amber">{pct_ruptura}%</div><div class="stat-label">Ruptura</div></div>
    </div>
    """.replace(",", "."), unsafe_allow_html=True)

    # ── Sub-tabs de gráficos ─────────────────────────────────────────────
    vt1, vt2, vt3, vt4 = st.tabs(["📊 Por Grupo", "🚨 Estoque Crítico", "🔥 Taxa de Giro", "🏆 Top Produtos"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — VENDAS POR GRUPO
    # ══════════════════════════════════════════════════════════════════════
    with vt1:
        top_n = min(14, len(df_grupo))
        df_top = df_grupo.head(top_n)

        # Bar chart horizontal — vendas por grupo
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_top["grupo"], x=df_top["qtd_vendida"],
            orientation="h",
            marker=dict(
                color=[_get_color(g) for g in df_top["grupo"]],
                line=dict(width=0),
                cornerradius=4,
            ),
            text=df_top["qtd_vendida"].apply(lambda v: f"{v:,.0f}".replace(",", ".")),
            textposition="outside", textfont=dict(size=10, color="#94a3b8"),
            hovertemplate="<b>%{y}</b><br>Vendido: %{x:,.0f}<extra></extra>",
        ))
        fig_bar.update_layout(
            **_PLOTLY_LAYOUT,
            title=dict(text="Quantidade Vendida por Grupo", font=dict(size=14, color="#e0e6ed")),
            height=max(350, top_n * 32),
            yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="#1e293b", title=None),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        # Dois gráficos lado a lado
        c1, c2 = st.columns(2)

        with c1:
            # Donut — distribuição %
            fig_pie = go.Figure(go.Pie(
                labels=df_top["grupo"].head(8),
                values=df_top["qtd_vendida"].head(8),
                hole=0.55,
                marker=dict(colors=[_get_color(g) for g in df_top["grupo"].head(8)]),
                textinfo="percent",
                textfont=dict(size=10, color="#e0e6ed"),
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} un<br>%{percent}<extra></extra>",
            ))
            fig_pie.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Distribuição % Vendas", font=dict(size=13, color="#94a3b8")),
                height=320, showlegend=True,
                legend=dict(font=dict(size=9), orientation="h", y=-0.15),
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

        with c2:
            # Grouped bar — vendido vs estoque
            fig_vs = go.Figure()
            df8 = df_top.head(8)
            fig_vs.add_trace(go.Bar(
                name="Vendido", x=df8["grupo"], y=df8["qtd_vendida"],
                marker=dict(color="#00d68f", cornerradius=3, opacity=0.85),
            ))
            fig_vs.add_trace(go.Bar(
                name="Estoque", x=df8["grupo"], y=df8["qtd_estoque"],
                marker=dict(color="#3b82f6", cornerradius=3, opacity=0.5),
            ))
            fig_vs.update_layout(
                **_PLOTLY_LAYOUT, barmode="group",
                title=dict(text="Vendido vs Estoque", font=dict(size=13, color="#94a3b8")),
                height=320,
                xaxis=dict(tickangle=-35, tickfont=dict(size=8), gridcolor="rgba(0,0,0,0)"),
                legend=dict(orientation="h", y=1.12, font=dict(size=10)),
            )
            st.plotly_chart(fig_vs, use_container_width=True, config={"displayModeBar": False})

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — ESTOQUE CRÍTICO
    # ══════════════════════════════════════════════════════════════════════
    with vt2:
        # Produtos com estoque zerado que venderam
        df_zero = df_vendas[(df_vendas["qtd_estoque"] <= 0) & (df_vendas["qtd_vendida"] > 0)].sort_values("qtd_vendida", ascending=False)
        # Produtos com estoque < 50% do vendido
        df_crit = df_vendas[
            (df_vendas["qtd_estoque"] > 0) &
            (df_vendas["qtd_estoque"] < df_vendas["qtd_vendida"] * 0.5) &
            (df_vendas["qtd_vendida"] > 10)
        ].sort_values("qtd_vendida", ascending=False)

        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            st.markdown(f"""<div class="stat-card"><div class="stat-value red">{len(df_zero)}</div>
            <div class="stat-label">💀 Zerados c/ vendas</div></div>""", unsafe_allow_html=True)
        with kc2:
            st.markdown(f"""<div class="stat-card"><div class="stat-value amber">{len(df_crit)}</div>
            <div class="stat-label">🔥 Crítico &lt;50%</div></div>""", unsafe_allow_html=True)
        with kc3:
            total_alert = len(df_zero) + len(df_crit)
            st.markdown(f"""<div class="stat-card"><div class="stat-value purple">{total_alert}</div>
            <div class="stat-label">⚡ Total Alertas</div></div>""", unsafe_allow_html=True)

        # Combinar e mostrar top 20
        df_alerta = pd.concat([
            df_zero.head(15).assign(nivel="ZERADO"),
            df_crit.head(10).assign(nivel="CRÍTICO"),
        ]).sort_values("qtd_vendida", ascending=False).head(20)

        if not df_alerta.empty:
            # Bar chart horizontal com cores de severidade
            colors = ["#ff4757" if n == "ZERADO" else "#ffa502" for n in df_alerta["nivel"]]
            nomes = df_alerta["produto"].apply(lambda p: p[:35] + "…" if len(p) > 35 else p)

            fig_alert = go.Figure()
            fig_alert.add_trace(go.Bar(
                y=nomes, x=df_alerta["qtd_vendida"], orientation="h",
                marker=dict(color=colors, cornerradius=3),
                text=df_alerta.apply(lambda r: f"Est: {int(r['qtd_estoque'])}", axis=1),
                textposition="outside", textfont=dict(size=9, color="#94a3b8"),
                hovertemplate="<b>%{y}</b><br>Vendido: %{x:,.0f}<br>%{text}<extra></extra>",
            ))
            fig_alert.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="🚨 Produtos com Estoque Crítico vs Vendas", font=dict(size=13)),
                height=max(400, len(df_alerta) * 28),
                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9)),
                xaxis=dict(title="Qtd Vendida", gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_alert, use_container_width=True, config={"displayModeBar": False})

            # Tabela detalhada
            with st.expander("📋 Tabela Detalhada — Críticos", expanded=False):
                df_show = df_alerta[["codigo", "produto", "grupo", "qtd_vendida", "qtd_estoque", "nivel"]].copy()
                df_show.columns = ["Código", "Produto", "Grupo", "Vendido", "Estoque", "Nível"]
                st.dataframe(df_show, hide_index=True, use_container_width=True)
        else:
            st.success("Nenhum produto em situação crítica! 🎉")

        # Lista completa de zerados
        if not df_zero.empty:
            with st.expander(f"💀 Lista Completa — Estoque Zerado ({len(df_zero)} produtos)", expanded=False):
                df_zero_show = df_zero[["codigo", "produto", "grupo", "qtd_vendida"]].copy()
                df_zero_show.columns = ["Código", "Produto", "Grupo", "Vendido"]
                df_zero_show = df_zero_show.reset_index(drop=True)
                st.dataframe(df_zero_show, hide_index=True, use_container_width=True, height=400)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — TAXA DE GIRO (BURN RATE)
    # ══════════════════════════════════════════════════════════════════════
    with vt3:
        st.caption("Estimativa de dias até zerar estoque no ritmo atual (baseado nos últimos 47 dias de vendas)")

        df_burn = df_grupo[df_grupo["qtd_vendida"] > 0].copy()
        df_burn["dias_estoque"] = (df_burn["qtd_estoque"] / df_burn["qtd_vendida"] * 47).round(0).astype(int)
        df_burn = df_burn.sort_values("dias_estoque").head(12)

        if not df_burn.empty:
            colors_burn = [
                "#ff4757" if d < 15 else "#ffa502" if d < 30 else "#00d68f"
                for d in df_burn["dias_estoque"]
            ]

            fig_burn = go.Figure()
            fig_burn.add_trace(go.Bar(
                y=df_burn["grupo"], x=df_burn["dias_estoque"], orientation="h",
                marker=dict(color=colors_burn, cornerradius=4),
                text=df_burn["dias_estoque"].apply(lambda d: f"{d}d"),
                textposition="outside", textfont=dict(size=10, color="#94a3b8"),
                hovertemplate="<b>%{y}</b><br>Dias restantes: %{x}<br><extra></extra>",
            ))
            # Linhas de referência
            fig_burn.add_shape(
                type="line", x0=15, x1=15, y0=-0.5, y1=len(df_burn)-0.5,
                line=dict(dash="dash", color="#ff4757", width=1), yref="y",
            )
            fig_burn.add_annotation(x=15, y=-0.5, text="Urgente", showarrow=False,
                font=dict(size=9, color="#ff4757"), yshift=-12)
            fig_burn.add_shape(
                type="line", x0=30, x1=30, y0=-0.5, y1=len(df_burn)-0.5,
                line=dict(dash="dash", color="#ffa502", width=1), yref="y",
            )
            fig_burn.add_annotation(x=30, y=-0.5, text="Atenção", showarrow=False,
                font=dict(size=9, color="#ffa502"), yshift=-12)
            fig_burn.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="🔥 Dias de Estoque Restante por Grupo", font=dict(size=14)),
                height=max(350, len(df_burn) * 35),
                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
                xaxis=dict(title="Dias", gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_burn, use_container_width=True, config={"displayModeBar": False})

            # Info box
            urgentes = df_burn[df_burn["dias_estoque"] < 15]["grupo"].tolist()
            if urgentes:
                st.error(f"⚡ **Reposição urgente** (<15 dias): {', '.join(urgentes)}")

            atencao = df_burn[(df_burn["dias_estoque"] >= 15) & (df_burn["dias_estoque"] < 30)]["grupo"].tolist()
            if atencao:
                st.warning(f"⚠️ **Atenção** (15-30 dias): {', '.join(atencao)}")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4 — TOP PRODUTOS
    # ══════════════════════════════════════════════════════════════════════
    with vt4:
        col_filter, _ = st.columns([1, 2])
        with col_filter:
            grupos_disp = ["TODOS"] + sorted(df_vendas["grupo"].unique().tolist())
            grupo_sel = st.selectbox("Filtrar por grupo:", grupos_disp, key="vendas_filtro_grupo")

        df_prod = df_vendas.copy()
        if grupo_sel != "TODOS":
            df_prod = df_prod[df_prod["grupo"] == grupo_sel]

        df_top_prod = df_prod.nlargest(15, "qtd_vendida")

        if not df_top_prod.empty:
            nomes = df_top_prod["produto"].apply(lambda p: p[:40] + "…" if len(p) > 40 else p)
            fig_top = go.Figure()
            fig_top.add_trace(go.Bar(
                y=nomes, x=df_top_prod["qtd_vendida"], orientation="h",
                marker=dict(
                    color=[_get_color(g) for g in df_top_prod["grupo"]],
                    cornerradius=4,
                ),
                text=df_top_prod["qtd_vendida"].apply(lambda v: f"{v:,.0f}".replace(",", ".")),
                textposition="outside", textfont=dict(size=9, color="#94a3b8"),
                hovertemplate="<b>%{y}</b><br>Vendido: %{x:,.0f}<br><extra></extra>",
            ))
            fig_top.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text=f"🏆 Top 15 Produtos — {grupo_sel}", font=dict(size=14)),
                height=max(380, len(df_top_prod) * 30),
                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9)),
                xaxis=dict(title="Qtd Vendida", gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_top, use_container_width=True, config={"displayModeBar": False})

            # Scatter vendido vs estoque
            st.markdown("---")
            fig_scatter = go.Figure()
            for g in df_prod["grupo"].unique():
                dg = df_prod[df_prod["grupo"] == g]
                fig_scatter.add_trace(go.Scatter(
                    x=dg["qtd_vendida"], y=dg["qtd_estoque"],
                    mode="markers", name=g[:15],
                    marker=dict(
                        color=_get_color(g), size=8, opacity=0.7,
                        line=dict(width=1, color="#0a0f1a"),
                    ),
                    hovertemplate="<b>%{text}</b><br>Vendido: %{x}<br>Estoque: %{y}<extra></extra>",
                    text=df_prod.loc[dg.index, "produto"].apply(lambda p: p[:30]),
                ))
            # Linha de equilíbrio
            max_val = max(df_prod["qtd_vendida"].max(), df_prod["qtd_estoque"].max(), 100)
            fig_scatter.add_trace(go.Scatter(
                x=[0, max_val], y=[0, max_val],
                mode="lines", line=dict(dash="dash", color="#64748b", width=1),
                name="Equilíbrio", showlegend=True,
            ))
            fig_scatter.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Vendido × Estoque (abaixo da linha = estoque menor que vendas)", font=dict(size=12, color="#94a3b8")),
                height=380,
                xaxis=dict(title="Qtd Vendida", gridcolor="#1e293b"),
                yaxis=dict(title="Qtd Estoque", gridcolor="#1e293b"),
                legend=dict(font=dict(size=8), orientation="h", y=-0.2),
            )
            st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Nenhum produto encontrado para o filtro selecionado.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="main-title">CAMDA ESTOQUE</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ESTOQUE MESTRE · QUIRINÓPOLIS</div>', unsafe_allow_html=True)

if _using_cloud:
    st.markdown('<div class="sync-badge">☁️ CONECTADO AO TURSO · BANCO COMPARTILHADO</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sync-badge">⚠️ MODO LOCAL · Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN para compartilhar</div>', unsafe_allow_html=True)

stock_count = get_stock_count()
has_mestre = stock_count > 0

# ── Upload Section ───────────────────────────────────────────────────────────
with st.expander("📤 Upload de Planilha", expanded=not has_mestre):

    if not has_mestre:
        st.info("👋 Nenhum estoque cadastrado. Faça o upload da planilha mestre para começar.")

    opcao_mestre = "MESTRE (carga completa)" if not has_mestre else "MESTRE (substituir tudo)"
    opcao_parcial = "PARCIAL (atualizar contagem do dia)"
    upload_mode = st.radio(
        "Tipo de Upload",
        [opcao_mestre, opcao_parcial],
        index=0 if not has_mestre else 1,
        horizontal=True,
        label_visibility="collapsed",
    )
    is_mestre_upload = "MESTRE" in upload_mode

    if is_mestre_upload:
        st.caption("Substitui todo o estoque. Use para carga inicial ou recomeçar do zero.")
    else:
        st.caption("Atualiza apenas os produtos da planilha. Os demais permanecem inalterados.")

    uploaded = st.file_uploader("Planilha XLSX", type=["xlsx", "xls"], label_visibility="collapsed", key="upload_main")

    if uploaded:
        # Parseia UMA VEZ e guarda no session_state
        file_id = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.processed_file != file_id:
            ok, result, zerados = read_excel_to_records(uploaded)
            st.session_state["_parsed_ok"] = ok
            st.session_state["_parsed_result"] = result
            st.session_state["_parsed_zerados"] = zerados
            st.session_state.processed_file = file_id

        ok = st.session_state.get("_parsed_ok", False)
        result = st.session_state.get("_parsed_result")
        zerados = st.session_state.get("_parsed_zerados", [])

        if ok:
            records = result
            with st.expander("👁️ Preview", expanded=False):
                df_preview = pd.DataFrame(records)
                n_div = sum(1 for r in records if r["status"] != "ok")
                st.caption(f"{len(records)} produtos encontrados")
                if n_div:
                    st.warning(f"⚠️ {n_div} divergência(s)")
                if zerados:
                    st.info(f"🗑️ {len(zerados)} produto(s) com estoque zerado serão removidos do mestre")
                st.dataframe(
                    df_preview[["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica", "diferenca", "nota", "status"]],
                    hide_index=True, use_container_width=True, height=250,
                )

            if st.button("🚀 Processar", type="primary"):
                with st.spinner("Processando..."):
                    if is_mestre_upload:
                        ok_up, msg = upload_mestre(records)
                    else:
                        ok_up, msg = upload_parcial(records, zerados)

                if ok_up:
                    st.success(msg)
                    # Salvar dados de vendas para gráficos
                    save_vendas_historico(records, _GRUPO_MAP, zerados)
                    if _using_cloud:
                        st.info("☁️ Sincronizado.")
                    st.session_state.processed_file = None
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.error(result)

    # Admin
    if has_mestre:
        st.markdown("---")

        # Upload de Princípios Ativos
        st.markdown("##### 🧬 Base de Princípios Ativos")
        pa_count = get_pa_count()
        if pa_count > 0:
            st.caption(f"✅ {pa_count} registros de princípios ativos carregados. A busca por princípio ativo está ativa.")
        else:
            st.caption("Carregue a planilha de princípios ativos para habilitar a busca por P.A.")

        uploaded_pa = st.file_uploader(
            "Planilha de Princípios Ativos", type=["xlsx", "xls"],
            label_visibility="collapsed", key="upload_pa"
        )
        if uploaded_pa:
            pa_records = load_principios_ativos_from_excel(uploaded_pa)
            if pa_records:
                if st.button("🧬 Carregar Princípios Ativos", type="primary"):
                    sync_principios_ativos(pa_records)
                    st.success(f"✅ {len(pa_records)} registros de princípios ativos carregados!")
                    st.rerun()
            else:
                st.error("Não foi possível ler a planilha. Verifique se tem colunas 'Produto' e 'Princípio Ativo'.")

        st.markdown("---")
        _, col_sync, col_reset = st.columns([2, 1, 1])
        with col_sync:
            if _using_cloud and st.button("🔄 Sincronizar"):
                sync_db()
                st.rerun()
        with col_reset:
            if st.session_state.confirm_reset:
                st.warning("Tem certeza?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Sim, limpar"):
                        reset_db()
                        st.session_state.confirm_reset = False
                        st.rerun()
                with c2:
                    if st.button("Cancelar"):
                        st.session_state.confirm_reset = False
                        st.rerun()
            else:
                if st.button("🗑️ Limpar BD"):
                    st.session_state.confirm_reset = True
                    st.rerun()


# ── Dashboard ────────────────────────────────────────────────────────────────
if has_mestre:
    df_mestre = get_current_stock()
    df_pa = get_principios_ativos()
    has_pa = not df_pa.empty

    search_placeholder = "Nome, Código ou Princípio Ativo..." if has_pa else "Nome ou Código..."
    search_term = st.text_input("🔍 Buscar no Mestre", placeholder=search_placeholder, label_visibility="collapsed")

    df_view = df_mestre
    pa_match_info = ""
    if search_term:
        # Busca padrão por nome/código
        mask_nome_cod = (
            df_view["produto"].str.contains(search_term, case=False, na=False)
            | df_view["codigo"].str.contains(search_term, case=False, na=False)
        )

        # Busca por princípio ativo
        if has_pa:
            pa_produtos = search_by_principio_ativo(search_term, df_pa)
            if pa_produtos:
                mask_pa = df_view["produto"].str.upper().isin(pa_produtos)
                mask = mask_nome_cod | mask_pa
                n_pa = mask_pa.sum()
                if n_pa > 0 and not mask_nome_cod.any():
                    # Busca encontrou apenas por P.A. — mostrar qual P.A. foi encontrado
                    pa_found = df_pa[df_pa["principio_ativo"].str.contains(search_term, case=False, na=False)]["principio_ativo"].unique()
                    pa_match_info = f"🧬 Princípio ativo: **{', '.join(pa_found[:3])}** → {n_pa} produto(s)"
                elif n_pa > 0:
                    pa_match_info = f"🧬 Inclui {n_pa} produto(s) por princípio ativo"
            else:
                mask = mask_nome_cod
        else:
            mask = mask_nome_cod

        df_view = df_view[mask]

        if pa_match_info:
            st.caption(pa_match_info)

    n_ok = (df_view["status"] == "ok").sum()
    n_falta = (df_view["status"] == "falta").sum()
    n_sobra = (df_view["status"] == "sobra").sum()
    n_danificado = (df_view["status"] == "danificado").sum()

    df_reposicao = get_reposicao_pendente()
    n_repor = len(df_reposicao)

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="stat-value">{len(df_view)}</div><div class="stat-label">Total</div></div>
        <div class="stat-card"><div class="stat-value">{n_ok}</div><div class="stat-label">OK</div></div>
        <div class="stat-card"><div class="stat-value red">{n_falta}</div><div class="stat-label">Faltas</div></div>
        <div class="stat-card"><div class="stat-value amber">{n_sobra}</div><div class="stat-label">Sobras</div></div>
        <div class="stat-card"><div class="stat-value purple">{n_danificado}</div><div class="stat-label">Danificados</div></div>
        <div class="stat-card"><div class="stat-value blue">{n_repor}</div><div class="stat-label">Repor Loja</div></div>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6 = st.tabs(["🗺️ Mapa Estoque", "⚠️ Divergências", "💔 Danificados", "🏪 Repor na Loja", "📈 Vendas", "📝 Log"])

    with t1:
        st.markdown(build_css_treemap(df_view, "TODOS"), unsafe_allow_html=True)

    with t2:
        df_div = df_view[df_view["status"].isin(("falta", "sobra"))]
        if df_div.empty:
            st.info("Nenhuma divergência.")
        else:
            st.dataframe(
                df_div[["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica", "diferenca", "nota", "ultima_contagem"]],
                hide_index=True, use_container_width=True,
            )

    with t3:
        df_dan = df_view[df_view["status"] == "danificado"]
        if df_dan.empty:
            st.info("Nenhum produto danificado.")
        else:
            st.dataframe(df_dan[["codigo", "produto", "qtd_sistema", "nota", "ultima_contagem"]], hide_index=True, use_container_width=True)

    with t4:
        if df_reposicao.empty:
            st.success("Nenhum produto pendente de reposição! 🎉")
        else:
            st.caption(f"{n_repor} produto(s) para repor. Itens somem após 7 dias ou quando marcados.")
            for _, item in df_reposicao.iterrows():
                try:
                    dias = (datetime.now() - datetime.strptime(item["criado_em"], "%Y-%m-%d %H:%M:%S")).days
                except (ValueError, TypeError):
                    dias = 0
                tempo = "hoje" if dias == 0 else ("ontem" if dias == 1 else f"{dias}d atrás")
                qtd_v = int(item["qtd_vendida"]) if pd.notnull(item["qtd_vendida"]) else 0

                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f'<div style="background:#111827;border:1px solid #1e293b;border-radius:8px;padding:10px 14px;margin-bottom:4px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span style="color:#e0e6ed;font-weight:700;font-size:0.85rem;">{item["produto"]}</span>'
                        f'<span style="color:#3b82f6;font-size:0.6rem;font-family:monospace;">{tempo}</span></div>'
                        f'<div style="margin-top:4px;display:flex;gap:12px;">'
                        f'<span style="color:#64748b;font-size:0.65rem;">Cod: <b style="color:#94a3b8;">{item["codigo"]}</b></span>'
                        f'<span style="color:#64748b;font-size:0.65rem;">{item["categoria"]}</span>'
                        f'<span style="color:#ffa502;font-size:0.65rem;font-weight:700;">Vendido: {qtd_v} → Repor: {qtd_v}</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("✅", key=f"repor_{item['id']}", help="Marcar como reposto"):
                        marcar_reposto(int(item["id"]))
                        st.rerun()

    with t5:
        df_vendas = get_vendas_historico()
        build_vendas_tab(df_vendas)

    with t6:
        df_hist = get_historico_uploads()
        if df_hist.empty:
            st.info("Nenhum upload registrado.")
        else:
            st.dataframe(df_hist, hide_index=True, use_container_width=True)

else:
    st.markdown(
        '<div style="text-align:center;color:#64748b;padding:60px 20px;font-size:1rem;">'
        "Faça o upload da planilha mestre acima para começar ☝️</div>",
        unsafe_allow_html=True,
    )
