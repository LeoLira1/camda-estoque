import streamlit as st
import pandas as pd
import libsql
import re
import os
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
    .update-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.6rem;
        color: #00d68f; text-align: center; margin-bottom: 0.5rem;
        opacity: 0.7;
    }
    .sync-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.55rem;
        color: #3b82f6; text-align: center; margin-bottom: 0.5rem;
        opacity: 0.8;
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

    .stRadio > div {
        flex-direction: row !important; gap: 4px !important;
        flex-wrap: wrap; justify-content: center;
    }
    .stRadio > div > label {
        background: #111827 !important; border: 1px solid #1e293b !important;
        border-radius: 20px !important; padding: 4px 14px !important;
        font-size: 0.75rem !important; color: #94a3b8 !important;
    }

    .stPlotlyChart { border-radius: 12px; overflow: hidden; }

    .mode-indicator {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 1px; margin-left: 6px;
    }
    .mode-mestre { background: #1e40af; color: #93c5fd; }
    .mode-parcial { background: #065f46; color: #6ee7b7; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE — TURSO (libSQL na nuvem) com Embedded Replica local
# ══════════════════════════════════════════════════════════════════════════════

# Tenta carregar do .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Tenta pegar dos Streamlit Secrets (para deploy no Streamlit Cloud)
def _get_secret(key: str) -> str:
    """Busca em st.secrets primeiro, depois em os.environ."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.environ.get(key, "")


TURSO_DATABASE_URL = _get_secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _get_secret("TURSO_AUTH_TOKEN")

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camda_local.db")

# Flag para saber se estamos conectados à nuvem
_using_cloud = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)


@st.cache_resource
def _get_connection():
    """
    Retorna uma conexão libSQL.
    - Se tem credenciais Turso → Embedded Replica (local + sync com nuvem)
    - Se não tem → SQLite local puro (fallback para desenvolvimento)
    """
    if _using_cloud:
        conn = libsql.connect(
            LOCAL_DB_PATH,
            sync_url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN,
        )
        conn.sync()  # Sincroniza na inicialização
    else:
        conn = libsql.connect(LOCAL_DB_PATH)
    return conn


def get_db():
    """Retorna conexão e garante que as tabelas existem."""
    conn = _get_connection()

    # Sync antes de ler (pega alterações de outros colegas)
    if _using_cloud:
        try:
            conn.sync()
        except Exception:
            pass  # Se falhar o sync, usa o cache local

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
    conn.commit()

    # ── Migrações: adiciona colunas que podem faltar em bancos antigos ──
    try:
        cols_reposicao = [
            row[1] for row in conn.execute("PRAGMA table_info(reposicao_loja)").fetchall()
        ]
        if "qtd_vendida" not in cols_reposicao:
            conn.execute("ALTER TABLE reposicao_loja ADD COLUMN qtd_vendida INTEGER NOT NULL DEFAULT 0")
            conn.commit()
        if "reposto" not in cols_reposicao:
            conn.execute("ALTER TABLE reposicao_loja ADD COLUMN reposto INTEGER DEFAULT 0")
            conn.commit()
        if "reposto_em" not in cols_reposicao:
            conn.execute("ALTER TABLE reposicao_loja ADD COLUMN reposto_em TEXT DEFAULT ''")
            conn.commit()
    except Exception:
        pass  # Se PRAGMA não funcionar no libsql, ignora silenciosamente

    return conn


# Categorias que VÃO para reposição na loja (whitelist)
CATEGORIAS_REPOSICAO_LOJA = {
    "LUBRIFICANTES",
    "EPI",
    "ACESSORIOS DE FAZENDA",
}


def sync_db():
    """Força sincronização com o Turso (chamar após escritas)."""
    if _using_cloud:
        try:
            conn = _get_connection()
            conn.sync()
        except Exception as e:
            st.warning(f"⚠️ Sync falhou: {e}. Os dados foram salvos localmente e serão sincronizados depois.")


# ══════════════════════════════════════════════════════════════════════════════
# LEITURAS DO BANCO — todas com try/except + fallback para DataFrame vazio
# ══════════════════════════════════════════════════════════════════════════════

def get_current_stock() -> pd.DataFrame:
    """Retorna todo o estoque mestre. Fallback para DF vazio se houver erro."""
    cols = ["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica",
            "diferenca", "nota", "status", "ultima_contagem", "criado_em"]
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM estoque_mestre ORDER BY categoria, produto").fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar estoque: {e}")
        return pd.DataFrame(columns=cols)


def get_stock_count() -> int:
    """Retorna quantidade de produtos no estoque. Fallback para 0 se houver erro."""
    try:
        conn = get_db()
        row = conn.execute("SELECT COUNT(*) FROM estoque_mestre").fetchone()
        return row[0] if row else 0
    except Exception as e:
        st.warning(f"⚠️ Erro ao contar estoque: {e}")
        return 0


def get_reposicao_pendente() -> pd.DataFrame:
    """Retorna itens de reposição pendentes (não repostos E com menos de 7 dias).
    Usa qtd_sistema do estoque_mestre como fallback quando qtd_vendida = 0.
    Fallback para DF vazio se houver erro."""
    cols = ["id", "codigo", "produto", "categoria", "qtd_repor", "criado_em"]
    try:
        conn = get_db()
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute("""
            SELECT
                r.id, r.codigo, r.produto, r.categoria,
                CASE
                    WHEN r.qtd_vendida > 0 THEN r.qtd_vendida
                    WHEN e.qtd_sistema IS NOT NULL THEN e.qtd_sistema
                    ELSE 0
                END AS qtd_repor,
                r.criado_em
            FROM reposicao_loja r
            LEFT JOIN estoque_mestre e ON r.codigo = e.codigo
            WHERE r.reposto = 0 AND r.criado_em >= ?
            ORDER BY r.criado_em DESC
        """, [cutoff]).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar reposição: {e}")
        return pd.DataFrame(columns=cols)


def get_historico_uploads() -> pd.DataFrame:
    """Retorna histórico de uploads. Fallback para DF vazio se houver erro."""
    cols = ["data", "tipo", "arquivo", "total_produtos_lote", "novos", "atualizados", "divergentes"]
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes "
            "FROM historico_uploads ORDER BY id DESC LIMIT 20"
        ).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar histórico: {e}")
        return pd.DataFrame(columns=cols)


def reset_db():
    """Limpa todas as tabelas. Com try/except para não quebrar o app."""
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
    """Marca um item como reposto na loja."""
    try:
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE reposicao_loja SET reposto = 1, reposto_em = ? WHERE id = ?",
            [now, item_id]
        )
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao marcar reposto: {e}")


def detectar_reposicao_loja(records: list, conn, now: str):
    """
    Detecta produtos de categorias de loja (whitelist) e adiciona à lista de reposição.
    Usa qtd_vendida se disponível, senão usa qtd_sistema.
    Só adiciona se o produto não estiver já pendente (não reposto) na tabela.
    """
    count = 0
    for r in records:
        cat_upper = r["categoria"].upper().strip()
        if cat_upper not in CATEGORIAS_REPOSICAO_LOJA:
            continue

        try:
            existing = conn.execute(
                "SELECT id FROM reposicao_loja WHERE codigo = ? AND reposto = 0",
                [r["codigo"]]
            ).fetchone()

            if not existing:
                qtd_v = r.get("qtd_vendida", r["qtd_sistema"])
                conn.execute("""
                    INSERT INTO reposicao_loja (codigo, produto, categoria, qtd_vendida, criado_em)
                    VALUES (?, ?, ?, ?, ?)
                """, [r["codigo"], r["produto"], r["categoria"], qtd_v, now])
                count += 1
        except Exception:
            continue

    return count


# ── Classificação e Parsing ──────────────────────────────────────────────────

def classify_product(name: str) -> str:
    n = str(name).upper()
    rules = [
        ("HERBICIDAS", ["HERBICIDA"]),
        ("FUNGICIDAS", ["FUNGICIDA"]),
        ("INSETICIDAS", ["INSETICIDA"]),
        ("NEMATICIDAS", ["NEMATICIDA"]),
        ("ADUBOS FOLIARES", ["ADUBO FOLIAR"]),
        ("ADUBOS QUÍMICOS", ["ADUBO Q"]),
        ("ADUBOS CORRETIVOS", ["ADUBO CORRETIVO", "CALCARIO", "CALCÁRIO"]),
        ("ÓLEOS", ["OLEO", "ÓLEO"]),
        ("SEMENTES", ["SEMENTE"]),
        ("ADJUVANTES", ["ADJUVANTE", "ESPALHANTE"]),
    ]
    for cat, keywords in rules:
        if any(kw in n for kw in keywords):
            return cat
    return "OUTROS"


def normalize_grupo(grupo: str) -> str:
    g = str(grupo).strip().upper()
    mapping = {
        "ADUBOS FOLIARES": "ADUBOS FOLIARES",
        "ADUBOS QUIMICOS": "ADUBOS QUÍMICOS",
        "ADUBOS CORRETIVOS": "ADUBOS CORRETIVOS",
        "HERBICIDAS": "HERBICIDAS",
        "FUNGICIDAS": "FUNGICIDAS",
        "INSETICIDAS": "INSETICIDAS",
        "NEMATICIDAS": "NEMATICIDAS",
        "OLEO MINERAL E VEGETAL": "ÓLEOS",
        "ADJUVANTES": "ADJUVANTES",
        "SEMENTES": "SEMENTES",
    }
    return mapping.get(g, g)


def short_name(prod: str) -> str:
    prefixes = [
        "HERBICIDA ", "FUNGICIDA ", "INSETICIDA ", "NEMATICIDA ",
        "ADUBO FOLIAR ", "ADUBO Q.", "OLEO VEGETAL ", "OLEO MINERAL ",
        "ÓLEO VEGETAL ", "ÓLEO MINERAL ", "ADJUVANTE ", "SEMENTE ",
    ]
    up = str(prod).upper()
    for p in prefixes:
        if up.startswith(p):
            return str(prod)[len(p):].strip()
    return str(prod)


# ══════════════════════════════════════════════════════════════════════════════
# CORREÇÃO 1: parse_annotation com regex abrangente
# ══════════════════════════════════════════════════════════════════════════════

def parse_annotation(nota: str, qtd_sistema: int) -> tuple:
    """Retorna: (qtd_fisica, diferenca, observacao, status_type)"""
    if not nota or str(nota).strip().lower() in ["", "nan", "none"]:
        return (qtd_sistema, 0, "", "ok")

    text = str(nota).strip()
    text_lower = text.lower()
    text_lower = re.sub(r"\s+", " ", text_lower).strip()

    # ── FALTA ──
    m = re.match(
        r"falt(?:a|ando|am|ou|aram|\.?)(?:\s+(?:de|do|da))?\s+(\d+)\s*(.*)",
        text_lower,
    )
    if m:
        falta = int(m.group(1))
        return (qtd_sistema - falta, -falta, m.group(2).strip(), "falta")

    m = re.match(r"^f\.?\s+(\d+)\s*(.*)", text_lower)
    if m:
        falta = int(m.group(1))
        return (qtd_sistema - falta, -falta, m.group(2).strip(), "falta")

    # ── SOBRA ──
    m = re.match(
        r"(?:sobr(?:a|ando|am|ou|aram|\.?)|pass(?:a|ando|aram|ou|\.?))\s+(\d+)\s*(.*)",
        text_lower,
    )
    if m:
        sobra = int(m.group(1))
        return (qtd_sistema + sobra, +sobra, m.group(2).strip(), "sobra")

    m = re.match(r"^s\.?\s+(\d+)\s*(.*)", text_lower)
    if m:
        sobra = int(m.group(1))
        return (qtd_sistema + sobra, +sobra, m.group(2).strip(), "sobra")

    # ── DANIFICADOS ──
    keywords_danificado = [
        "danificad", "avaria", "avariado", "quebrad", "defeito",
        "vencid", "impropri", "vazand", "estraga", "molhad",
        "rasgad", "furad", "amassd", "amassad", "contaminad",
    ]
    if any(k in text_lower for k in keywords_danificado):
        return (qtd_sistema, 0, text.strip(), "danificado")

    # ── Fallback: busca no meio do texto ──
    m = re.search(r"falt\w*\s+(?:de\s+)?(\d+)", text_lower)
    if m:
        falta = int(m.group(1))
        return (qtd_sistema - falta, -falta, text.strip(), "falta")

    m = re.search(r"(?:sobr|pass)\w*\s+(\d+)", text_lower)
    if m:
        sobra = int(m.group(1))
        return (qtd_sistema + sobra, +sobra, text.strip(), "sobra")

    return (qtd_sistema, 0, text.strip(), "ok")


# ── Detecção de Formato ─────────────────────────────────────────────────────

def detect_format(df_raw: pd.DataFrame) -> str:
    for i in range(min(10, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        row_text = " ".join(vals)

        if any(x in row_text for x in ["QTDD - VENDIDA", "QTDD ESTOQUE", "GRUPO DE PRODUTO"]):
            return "vendas"

        has_produto = any("PRODUTO" == v for v in vals)
        has_qtd = any("QUANTIDADE" in v or v == "QTD" for v in vals)
        if has_produto and has_qtd:
            return "estoque"

    return "desconhecido"


# ── Parser: Formato Estoque (Mestre) ─────────────────────────────────────────

def parse_estoque_format(df_raw: pd.DataFrame) -> tuple:
    header_idx = None
    for i in range(min(15, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        has_produto = any("PRODUTO" == v for v in vals)
        has_qtd = any("QUANTIDADE" in v or v == "QTD" for v in vals)
        if has_produto and has_qtd:
            header_idx = i
            break

    if header_idx is None:
        return (False, "Cabeçalho não encontrado no formato estoque. Preciso de 'Produto' e 'Quantidade'.")

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
        elif ("CÓDIGO" in cu or "CODIGO" in cu or cu == "COD" or cu == "CÓDIGO") and "codigo" not in col_map:
            col_map["codigo"] = c
        elif cu == "LOCAL" and "local" not in col_map:
            col_map["local"] = c
        elif ("OBS" in cu or "NOTA" in cu or "DIFEREN" in cu or "ANOTA" in cu) and "nota" not in col_map:
            col_map["nota"] = c

    if "produto" not in col_map or "qtd" not in col_map:
        return (False, f"Colunas detectadas: {list(df.columns)} — falta 'Produto' ou 'Quantidade'.")

    # Se não achou coluna de nota, procura em colunas restantes
    if "nota" not in col_map:
        used_cols = set(col_map.values())
        for c in df.columns:
            if c not in used_cols:
                sample = df[c].dropna().astype(str).head(20)
                has_text = sample.apply(
                    lambda x: bool(re.search(r"[a-zA-Z]", str(x))) and str(x).upper() not in ["NAN", "NONE", ""]
                ).any()
                if has_text:
                    col_map["nota"] = c
                    break

    records = []
    for _, row in df.iterrows():
        produto = str(row.get(col_map["produto"], "")).strip()
        if produto.upper() in ["", "NAN", "NONE", "TOTAL", "PRODUTO", "ROLLUP"]:
            continue

        try:
            raw_val = row.get(col_map["qtd"])
            if pd.isna(raw_val):
                continue
            qtd_sistema = int(float(raw_val))
            if qtd_sistema <= 0:
                continue
        except (ValueError, TypeError):
            continue

        codigo = ""
        if "codigo" in col_map:
            codigo = str(row.get(col_map["codigo"], "")).strip()
            if codigo.upper() in ["NAN", "NONE", ""]:
                codigo = ""
        if not codigo:
            codigo = "AUTO_" + re.sub(r"[^A-Z0-9]", "", produto.upper())[:20]

        nota_raw = ""
        if "nota" in col_map:
            nota_raw = str(row.get(col_map["nota"], "")).strip()
            if nota_raw.upper() in ["NAN", "NONE"]:
                nota_raw = ""
            if re.match(r"^\d+([.,]\d+)?$", nota_raw):
                nota_raw = ""

        categoria = classify_product(produto)
        qtd_fisica, diferenca, observacao, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo, "produto": produto, "categoria": categoria,
            "qtd_sistema": qtd_sistema, "qtd_fisica": qtd_fisica,
            "diferenca": diferenca, "nota": observacao, "status": status,
        })

    if not records:
        return (False, "Nenhum dado válido encontrado na planilha de estoque.")
    return (True, records)


# ── Parser: Formato Vendas (Parcial) ─────────────────────────────────────────

def parse_vendas_format(df_raw: pd.DataFrame) -> tuple:
    header_idx = None
    for i in range(min(15, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        row_text = " ".join(vals)
        if "PRODUTO" in vals and ("QTDD" in row_text or "VENDIDA" in row_text):
            header_idx = i
            break

    if header_idx is None:
        return (False, "Cabeçalho não encontrado no formato vendas.")

    df = df_raw.iloc[header_idx + 1:].copy()
    raw_cols = df_raw.iloc[header_idx].tolist()
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_cols)]

    col_grupo = col_produto = col_qtd_vendida = col_qtd_estoque = col_nota = None

    for c in df.columns:
        cu = c.upper().strip()
        if "GRUPO" in cu and col_grupo is None:
            col_grupo = c
        elif cu == "PRODUTO" and col_produto is None:
            col_produto = c
        elif "VENDIDA" in cu and col_qtd_vendida is None:
            col_qtd_vendida = c
        elif "ESTOQUE" in cu and col_qtd_estoque is None:
            col_qtd_estoque = c
        elif ("OBS" in cu or "NOTA" in cu or "ANOTA" in cu) and col_nota is None:
            col_nota = c

    if col_nota is None:
        for c in df.columns:
            cu = c.upper().strip()
            if "CUSTO" in cu:
                col_nota = c
                break

    if col_produto is None:
        return (False, f"Coluna 'PRODUTO' não encontrada. Colunas: {list(df.columns)}")
    if col_qtd_estoque is None and col_qtd_vendida is None:
        return (False, "Nenhuma coluna de quantidade encontrada.")

    records = []
    current_grupo = "OUTROS"

    for _, row in df.iterrows():
        if col_grupo:
            g = str(row.get(col_grupo, "")).strip()
            if g and g.upper() not in ["NAN", "NONE", ""]:
                current_grupo = g

        raw_prod = str(row.get(col_produto, "")).strip()
        if raw_prod.upper() in ["", "NAN", "NONE", "ROLLUP"]:
            continue

        m = re.match(r"^(\d+)\s*-\s*(.+)$", raw_prod)
        if m:
            codigo = m.group(1).strip()
            produto = m.group(2).strip()
        else:
            codigo = "AUTO_" + re.sub(r"[^A-Z0-9]", "", raw_prod.upper())[:20]
            produto = raw_prod

        qtd_sistema = 0
        qtd_vendida_val = 0
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
        if qtd_sistema <= 0 and qtd_vendida_val > 0:
            qtd_sistema = qtd_vendida_val
        if qtd_sistema <= 0:
            continue

        nota_raw = ""
        if col_nota:
            nota_val = str(row.get(col_nota, "")).strip()
            if nota_val.upper() not in ["NAN", "NONE", ""]:
                if not re.match(r"^\d+([.,]\d+)?$", nota_val):
                    nota_raw = nota_val

        categoria = normalize_grupo(current_grupo)
        if categoria in ["OUTROS", ""]:
            categoria = classify_product(produto)

        qtd_fisica, diferenca, observacao, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo, "produto": produto, "categoria": categoria,
            "qtd_sistema": qtd_sistema, "qtd_fisica": qtd_fisica,
            "diferenca": diferenca, "nota": observacao, "status": status,
            "qtd_vendida": qtd_vendida_val,
        })

    if not records:
        return (False, "Nenhum dado válido encontrado na planilha de vendas.")
    return (True, records)


# ── Leitura Unificada ────────────────────────────────────────────────────────

def read_excel_to_records(uploaded_file) -> tuple:
    try:
        df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    except Exception as e:
        return (False, f"Erro ao ler arquivo: {e}")

    fmt = detect_format(df_raw)

    if fmt == "vendas":
        return parse_vendas_format(df_raw)
    elif fmt == "estoque":
        return parse_estoque_format(df_raw)
    else:
        ok, result = parse_estoque_format(df_raw)
        if ok:
            return (ok, result)
        ok2, result2 = parse_vendas_format(df_raw)
        if ok2:
            return (ok2, result2)
        return (False, "Formato não reconhecido. Colunas esperadas:\n"
                       "• Estoque: 'Produto' + 'Quantidade'\n"
                       "• Vendas: 'PRODUTO' + 'QTDD ESTOQUE' ou 'QTDD - VENDIDA'")


# ── Upload Mestre ────────────────────────────────────────────────────────────

def upload_mestre(uploaded_file) -> tuple:
    ok, result = read_excel_to_records(uploaded_file)
    if not ok:
        return (False, result)

    records = result
    try:
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("DELETE FROM estoque_mestre")

        for r in records:
            conn.execute("""
                INSERT INTO estoque_mestre
                    (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                r["codigo"], r["produto"], r["categoria"],
                r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                r["nota"], r["status"], now, now,
            ])

        n_div = sum(1 for r in records if r["status"] != "ok")
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "MESTRE", uploaded_file.name, len(records), len(records), 0, n_div])

        conn.commit()
        sync_db()
        return (True, f"✅ Mestre carregado: {len(records)} produtos ({n_div} divergências)")
    except Exception as e:
        return (False, f"❌ Erro ao salvar mestre: {e}")


# ── Upload Parcial ───────────────────────────────────────────────────────────

def upload_parcial(uploaded_file) -> tuple:
    ok, result = read_excel_to_records(uploaded_file)
    if not ok:
        return (False, result)

    records = result
    try:
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        novos = 0
        atualizados = 0

        for r in records:
            existing = conn.execute(
                "SELECT codigo FROM estoque_mestre WHERE codigo = ?", [r["codigo"]]
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE estoque_mestre SET
                        produto = ?, categoria = ?, qtd_sistema = ?, qtd_fisica = ?,
                        diferenca = ?, nota = ?, status = ?, ultima_contagem = ?
                    WHERE codigo = ?
                """, [
                    r["produto"], r["categoria"],
                    r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                    r["nota"], r["status"], now, r["codigo"],
                ])
                atualizados += 1
            else:
                conn.execute("""
                    INSERT INTO estoque_mestre
                        (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    r["codigo"], r["produto"], r["categoria"],
                    r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                    r["nota"], r["status"], now, now,
                ])
                novos += 1

        n_div = sum(1 for r in records if r["status"] != "ok")
        n_repo = detectar_reposicao_loja(records, conn, now)
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "PARCIAL", uploaded_file.name, len(records), novos, atualizados, n_div])

        conn.commit()
        sync_db()

        msg = f"✅ Parcial processada: {len(records)} produtos"
        if atualizados:
            msg += f" · {atualizados} atualizados"
        if novos:
            msg += f" · {novos} novos"
        if n_div:
            msg += f" · {n_div} divergências"
        if n_repo:
            msg += f" · 🏪 {n_repo} para repor na loja"
        return (True, msg)
    except Exception as e:
        return (False, f"❌ Erro ao salvar parcial: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CORREÇÃO 2: Treemap — cards de danificado mostram qtd do sistema
# ══════════════════════════════════════════════════════════════════════════════

def build_css_treemap(df: pd.DataFrame, filter_cat: str = "TODOS") -> str:
    if df.empty:
        return '<div style="color:#64748b; text-align:center; padding:40px;">Nenhum produto para exibir</div>'

    if filter_cat != "TODOS":
        df = df[df["categoria"] == filter_cat]
    if df.empty:
        return '<div style="color:#64748b; text-align:center; padding:40px;">Nenhum produto nesta categoria</div>'

    df = df.copy()
    df["qtd_sistema"] = pd.to_numeric(df["qtd_sistema"], errors="coerce").fillna(0)

    categories = {}
    for _, row in df.iterrows():
        cat = row["categoria"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(row)

    sorted_cats = sorted(
        categories.keys(),
        key=lambda c: sum(int(r["qtd_sistema"]) for r in categories[c]),
        reverse=True,
    )
    blocks_html = ""

    for cat in sorted_cats:
        rows = categories[cat]
        products_html = ""

        for r in sorted(rows, key=lambda x: str(x["produto"])):
            qs = int(r["qtd_sistema"])
            qf = int(r["qtd_fisica"]) if pd.notnull(r.get("qtd_fisica")) else qs
            diff = int(r["diferenca"]) if pd.notnull(r.get("diferenca")) else 0
            stat = str(r.get("status", "ok"))
            note = str(r.get("nota", "")) if pd.notnull(r.get("nota")) else ""
            cod = str(r.get("codigo", ""))

            # ── CORREÇÃO: Danificado mostra qtd do sistema + info da avaria ──
            if stat == "danificado":
                bg, txt = "#a55eea", "#fff"
                nums = re.findall(r"\d+", note)
                qtd_bad = nums[0] if nums else ""
                if qtd_bad:
                    info = f"{qs} · AV:{qtd_bad}"
                else:
                    info = f"{qs} · AVARIA"
            elif diff == 0:
                bg, txt = "#00d68f", "#0a2e1a"
                info = f"{qs}"
            elif diff < 0:
                bg, txt = "#ff4757", "#fff"
                info = f"{qf} (F {abs(diff)})"
            else:
                bg, txt = "#ffa502", "#fff"
                info = f"{qf} (S {diff})"

            contagem = str(r.get("ultima_contagem", ""))
            border_extra = ""
            if not contagem or contagem in ["", "nan", "None"]:
                border_extra = "border: 2px dashed #64748b !important; opacity: 0.6;"

            tooltip = f"{r['produto']} | Cod: {cod} | Sist: {qs} | Fis: {qf}"
            if note:
                tooltip += f" | Obs: {note}"

            products_html += f"""
            <div style="width: 110px; height: 60px; background: {bg}; color: {txt};
                 border-radius: 4px; padding: 4px; margin: 2px;
                 display: flex; flex-direction: column; justify-content: center; align-items: center;
                 overflow: hidden; border: 1px solid rgba(0,0,0,0.1); {border_extra}"
                 title="{tooltip}">
                <div style="font-size: 0.55rem; font-weight: 700; text-align: center; width: 100%;
                     white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    {short_name(r['produto'])}
                </div>
                <div style="font-size: 0.65rem; opacity: 0.9; font-family: monospace;
                     font-weight: bold; margin-top: 2px;">
                    {info}
                </div>
            </div>"""

        blocks_html += f"""
        <div style="width: 100%; background: #111827; border-radius: 8px; padding: 8px;
             margin-bottom: 8px; border: 1px solid #1e293b; display: flex; flex-direction: column;">
            <div style="font-size: 0.75rem; color: #64748b; font-weight: 700;
                 text-transform: uppercase; margin-bottom: 6px;
                 border-bottom: 1px solid #1e293b; padding-bottom: 4px;">
                {cat} <span style="font-size:0.6rem; color:#4a5568; font-weight:400;">({len(rows)})</span>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 2px;">{products_html}</div>
        </div>"""

    return f'<div style="display: flex; flex-direction: column; min-height: 450px;">{blocks_html}</div>'


# ── MAIN APP ─────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">CAMDA ESTOQUE</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ESTOQUE MESTRE · QUIRINÓPOLIS</div>', unsafe_allow_html=True)

# Indicador de conexão
if _using_cloud:
    st.markdown(
        '<div class="sync-badge">☁️ CONECTADO AO TURSO · BANCO COMPARTILHADO</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="sync-badge">⚠️ MODO LOCAL · Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN para compartilhar</div>',
        unsafe_allow_html=True,
    )

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
        st.caption("O upload mestre substitui todo o estoque. Use para carga inicial ou recomeçar do zero.")
    else:
        st.caption("O upload parcial atualiza apenas os produtos presentes na planilha. Os demais permanecem inalterados.")

    uploaded = st.file_uploader(
        "Planilha XLSX",
        type=["xlsx", "xls"],
        label_visibility="collapsed",
        key="upload_main",
    )

    if uploaded:
        with st.expander("👁️ Preview do arquivo", expanded=False):
            try:
                ok_preview, result_preview = read_excel_to_records(uploaded)
                uploaded.seek(0)
                if ok_preview:
                    df_preview = pd.DataFrame(result_preview)
                    st.caption(f"Formato detectado · {len(result_preview)} produtos encontrados")
                    n_div_preview = sum(1 for r in result_preview if r["status"] != "ok")
                    if n_div_preview:
                        st.warning(f"⚠️ {n_div_preview} divergência(s) detectada(s)")
                    st.dataframe(
                        df_preview[["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica", "diferenca", "nota", "status"]],
                        hide_index=True, use_container_width=True, height=250,
                    )
                else:
                    st.error(result_preview)
            except Exception as e:
                st.error(f"Erro no preview: {e}")

        if st.button("🚀 Processar", type="primary"):
            with st.spinner("Processando e sincronizando..."):
                if is_mestre_upload:
                    ok, msg = upload_mestre(uploaded)
                else:
                    ok, msg = upload_parcial(uploaded)

            if ok:
                st.success(msg)
                if _using_cloud:
                    st.info("☁️ Dados sincronizados — seu colega verá as alterações ao recarregar a página.")
                st.rerun()
            else:
                st.error(msg)

    # Área de administração
    if has_mestre:
        st.markdown("---")
        col_adm1, col_adm2, col_adm3 = st.columns([2, 1, 1])
        with col_adm2:
            if _using_cloud:
                if st.button("🔄 Sincronizar"):
                    sync_db()
                    st.rerun()
        with col_adm3:
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

    search_term = st.text_input(
        "🔍 Buscar no Mestre",
        placeholder="Nome ou Código...",
        label_visibility="collapsed",
    )

    df_view = df_mestre.copy()
    if search_term:
        mask = (
            df_view["produto"].astype(str).str.contains(search_term, case=False, na=False)
            | df_view["codigo"].astype(str).str.contains(search_term, case=False, na=False)
        )
        df_view = df_view[mask]

    n_ok = len(df_view[df_view["status"] == "ok"])
    n_falta = len(df_view[df_view["status"] == "falta"])
    n_sobra = len(df_view[df_view["status"] == "sobra"])
    n_danificado = len(df_view[df_view["status"] == "danificado"])

    n_sem_contagem = len(
        df_view[
            (df_view["ultima_contagem"].isna())
            | (df_view["ultima_contagem"].astype(str).isin(["", "nan", "None"]))
        ]
    )

    df_reposicao = get_reposicao_pendente()
    n_repor = len(df_reposicao)

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card">
            <div class="stat-value">{len(df_view)}</div>
            <div class="stat-label">Total</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{n_ok}</div>
            <div class="stat-label">OK</div>
        </div>
        <div class="stat-card">
            <div class="stat-value red">{n_falta}</div>
            <div class="stat-label">Faltas</div>
        </div>
        <div class="stat-card">
            <div class="stat-value amber">{n_sobra}</div>
            <div class="stat-label">Sobras</div>
        </div>
        <div class="stat-card">
            <div class="stat-value purple">{n_danificado}</div>
            <div class="stat-label">Danificados</div>
        </div>
        <div class="stat-card">
            <div class="stat-value blue">{n_repor}</div>
            <div class="stat-label">Repor Loja</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    cats = ["TODOS"] + sorted(df_view["categoria"].unique().tolist())
    f_cat = st.radio("🏷️ Categoria", cats, horizontal=True, label_visibility="collapsed")

    t1, t2, t3, t4, t5 = st.tabs([
        "🗺️ Mapa Estoque",
        "⚠️ Divergências",
        "💔 Danificados",
        "🏪 Repor na Loja",
        "📝 Log de Uploads",
    ])

    with t1:
        st.markdown(build_css_treemap(df_view, f_cat), unsafe_allow_html=True)

    with t2:
        df_div = df_view[(df_view["status"] == "falta") | (df_view["status"] == "sobra")]
        if df_div.empty:
            st.info("Nenhuma divergência encontrada.")
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
            st.dataframe(
                df_dan[["codigo", "produto", "qtd_sistema", "nota", "ultima_contagem"]],
                hide_index=True, use_container_width=True,
            )

    with t4:
        if df_reposicao.empty:
            st.success("Nenhum produto pendente de reposição na loja! 🎉")
        else:
            st.caption(
                f"{n_repor} produto(s) para levar/repor na loja. "
                "Itens somem após 7 dias ou quando marcados como repostos."
            )
            for _, item in df_reposicao.iterrows():
                try:
                    dias_atras = (datetime.now() - datetime.strptime(item["criado_em"], "%Y-%m-%d %H:%M:%S")).days
                except (ValueError, TypeError):
                    dias_atras = 0

                if dias_atras == 0:
                    tempo = "hoje"
                elif dias_atras == 1:
                    tempo = "ontem"
                else:
                    tempo = f"{dias_atras}d atrás"

                qtd_v = int(item["qtd_repor"]) if pd.notnull(item["qtd_repor"]) else 0

                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f'<div style="background:#111827; border:1px solid #1e293b; border-radius:8px; '
                        f'padding:10px 14px; margin-bottom:4px;">'
                        f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                        f'<span style="color:#e0e6ed; font-weight:700; font-size:0.85rem;">{item["produto"]}</span>'
                        f'<span style="color:#3b82f6; font-size:0.6rem; font-family:monospace;">{tempo}</span>'
                        f'</div>'
                        f'<div style="margin-top:4px; display:flex; gap:12px;">'
                        f'<span style="color:#64748b; font-size:0.65rem;">Cod: <b style="color:#94a3b8;">{item["codigo"]}</b></span>'
                        f'<span style="color:#64748b; font-size:0.65rem;">{item["categoria"]}</span>'
                        f'<span style="color:#ffa502; font-size:0.65rem; font-weight:700;">Repor: {qtd_v}</span>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("✅", key=f"repor_{item['id']}", help="Marcar como reposto"):
                        marcar_reposto(int(item["id"]))
                        st.rerun()

    with t5:
        df_hist = get_historico_uploads()
        if df_hist.empty:
            st.info("Nenhum upload registrado.")
        else:
            st.dataframe(df_hist, hide_index=True, use_container_width=True)

else:
    st.markdown(
        '<div style="text-align:center; color:#64748b; padding:60px 20px; font-size:1rem;">'
        "Faça o upload da planilha mestre acima para começar ☝️"
        "</div>",
        unsafe_allow_html=True,
    )
