"""
db_mapa.py — Funções de banco para o Mapa Visual do Armazém CAMDA.

Estrutura física:
  - 10 racks (R1..R10), 2 faces (A=frente, B=fundo)
  - 13 colunas por rack, 4 níveis (N1=chão, N4=topo)
  - pos_key: "{RACK}-{FACE}-C{COL}-N{NIVEL}"  ex: R1-A-C1-N1
  - Total de posições: 10 × 2 × 13 × 4 = 1.040 células

Renomear racks: UPDATE racks SET nome='Nome Real' WHERE rack_id='R1'
O pos_key no banco NÃO muda, apenas o campo nome.
"""

import uuid
from datetime import datetime, timezone, timedelta

_BRT = timezone(timedelta(hours=-3))


def _install_camda_header_spacing_patch():
    """Aplica CSS do topo via st.markdown em todo render do app.

    app_turso.py importa este módulo antes de renderizar o dashboard. Por isso,
    este patch é mais confiável que sitecustomize no Streamlit Cloud.
    """
    try:
        import streamlit as st
    except Exception:
        return

    if getattr(st, "_camda_header_spacing_patch_installed", False):
        return

    original_markdown = st.markdown
    css = """
<style id="camda-header-spacing-patch">
html, body, .stApp,
section[data-testid="stMain"],
[data-testid="stMain"],
div[data-testid="stMainBlockContainer"],
div[data-testid="stAppViewBlockContainer"],
.block-container {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

.block-container > div:first-child,
div[data-testid="stVerticalBlock"] > div:first-child,
div[data-testid="stElementContainer"]:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

.camda-header {
    margin-top: -3.5rem !important;
}

div[data-testid="stElementContainer"]:has(.camda-header) {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

@media (max-width: 768px) {
    .camda-header {
        margin-top: -3.25rem !important;
    }
}
</style>
"""

    def markdown_with_camda_spacing_patch(body, *args, **kwargs):
        if isinstance(body, str) and "camda-header-spacing-patch" not in body:
            body = css + "\n" + body
        return original_markdown(body, *args, **kwargs)

    st.markdown = markdown_with_camda_spacing_patch
    st._camda_header_spacing_patch_installed = True


_install_camda_header_spacing_patch()

# ── Paleta de cores padrão para novos produtos ────────────────────────────────
_CORES = [
    "#4ade80", "#60a5fa", "#f59e0b", "#f87171",
    "#a78bfa", "#34d399", "#fb923c", "#e879f9",
    "#22d3ee", "#facc15", "#6ee7b7", "#fda4af",
]


def ensure_mapa_tables(conn):
    """Cria tabelas do mapa se não existirem (idempotente)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS racks (
            rack_id    TEXT PRIMARY KEY,
            nome       TEXT NOT NULL,
            fileira    INTEGER NOT NULL,
            posicao    INTEGER NOT NULL,
            tem_face_b INTEGER DEFAULT 1,
            ativo      INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mapa_posicoes (
            pos_key    TEXT PRIMARY KEY,
            rua        TEXT NOT NULL,
            face       TEXT NOT NULL,
            coluna     INTEGER NOT NULL,
            nivel      INTEGER NOT NULL,
            produto_id TEXT,
            quantidade REAL,
            unidade    TEXT,
            atualizado TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mapa_produtos (
            produto_id   TEXT PRIMARY KEY,
            nome         TEXT NOT NULL UNIQUE,
            unidade_pad  TEXT NOT NULL DEFAULT 'L',
            cor_hex      TEXT
        )
    """)
    # Seed inicial dos racks (INSERT OR IGNORE = idempotente)
    conn.execute("""
        INSERT OR IGNORE INTO racks VALUES
            ('R1',  'R1',  1, 1, 1, 1),
            ('R2',  'R2',  1, 2, 1, 1),
            ('R3',  'R3',  1, 3, 1, 1),
            ('R4',  'R4',  1, 4, 1, 1),
            ('R5',  'R5',  1, 5, 1, 1),
            ('R6',  'R6',  1, 6, 1, 1),
            ('R7',  'R7',  2, 1, 1, 1),
            ('R8',  'R8',  2, 2, 1, 1),
            ('R9',  'R9',  2, 3, 1, 1),
            ('R10', 'R10', 2, 4, 1, 1)
    """)
    conn.commit()


# Alias para compatibilidade com a interface descrita no schema
init_mapa_tables = ensure_mapa_tables


def _get_rack_list(conn) -> list:
    """Retorna lista de rack_ids ativos ordenados por fileira e posição."""
    try:
        rows = conn.execute(
            "SELECT rack_id FROM racks WHERE ativo=1 ORDER BY fileira, posicao"
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
    except Exception:
        pass
    return [f"R{i}" for i in range(1, 11)]


def _parse_pos_key(pos_key: str):
    """Decompõe 'R1-A-C3-N2' → (rua, face, coluna, nivel)."""
    parts = pos_key.split("-")
    rua   = parts[0]
    face  = parts[1]
    coluna = int(parts[2][1:])
    nivel  = int(parts[3][1:])
    return rua, face, coluna, nivel


# ── Leitura ───────────────────────────────────────────────────────────────────

def get_paletes_rack(conn, rua: str, face: str) -> dict:
    """
    Retorna dict {pos_key: {produto, quantidade, unidade, cor}}
    para todas as células ocupadas de um rack (rua × face).
    """
    ensure_mapa_tables(conn)
    rows = conn.execute(
        """
        SELECT p.pos_key, mp.nome, p.quantidade, p.unidade, mp.cor_hex
        FROM   mapa_posicoes p
        LEFT JOIN mapa_produtos mp ON mp.produto_id = p.produto_id
        WHERE  p.rua = ? AND p.face = ? AND p.produto_id IS NOT NULL
        """,
        (rua, face),
    ).fetchall()
    return {
        r[0]: {
            "produto":    r[1] or "",
            "quantidade": r[2],
            "unidade":    r[3] or "",
            "cor":        r[4] or "#4ade80",
        }
        for r in rows
    }


def get_todos_paletes(conn) -> dict:
    """Retorna todos os paletes do armazém (todas as ruas/faces)."""
    ensure_mapa_tables(conn)
    rows = conn.execute(
        """
        SELECT p.pos_key, p.rua, p.face, mp.nome, p.quantidade, p.unidade, mp.cor_hex
        FROM   mapa_posicoes p
        LEFT JOIN mapa_produtos mp ON mp.produto_id = p.produto_id
        WHERE  p.produto_id IS NOT NULL
        """
    ).fetchall()
    return {
        r[0]: {
            "rua":        r[1],
            "face":       r[2],
            "produto":    r[3] or "",
            "quantidade": r[4],
            "unidade":    r[5] or "",
            "cor":        r[6] or "#4ade80",
        }
        for r in rows
    }


def get_produtos_mapa(conn) -> list:
    """Retorna lista de {produto_id, nome, unidade_pad, cor_hex} ordenada por nome."""
    ensure_mapa_tables(conn)
    rows = conn.execute(
        "SELECT produto_id, nome, unidade_pad, cor_hex FROM mapa_produtos ORDER BY nome"
    ).fetchall()
    return [
        {"produto_id": r[0], "nome": r[1], "unidade_pad": r[2], "cor_hex": r[3]}
        for r in rows
    ]


def buscar_produto_no_mapa(conn, nome_parcial: str) -> list:
    """Retorna lista de pos_keys que contêm o produto (busca por substring)."""
    ensure_mapa_tables(conn)
    rows = conn.execute(
        """
        SELECT p.pos_key
        FROM   mapa_posicoes p
        JOIN   mapa_produtos mp ON mp.produto_id = p.produto_id
        WHERE  LOWER(mp.nome) LIKE ?
        """,
        (f"%{nome_parcial.lower()}%",),
    ).fetchall()
    return [r[0] for r in rows]


def buscar_produto_todas_ruas(conn, nome_parcial: str) -> list:
    """
    Busca produto em TODOS os racks e retorna lista de localizações completas.
    Retorna [{pos_key, rua, face, coluna, nivel, produto, quantidade, unidade}]
    """
    ensure_mapa_tables(conn)
    rows = conn.execute(
        """
        SELECT p.pos_key, p.rua, p.face, p.coluna, p.nivel,
               mp.nome, p.quantidade, p.unidade
        FROM   mapa_posicoes p
        JOIN   mapa_produtos mp ON mp.produto_id = p.produto_id
        WHERE  LOWER(mp.nome) LIKE ?
        ORDER BY p.rua, p.face, p.coluna, p.nivel
        """,
        (f"%{nome_parcial.lower()}%",),
    ).fetchall()
    return [
        {
            "pos_key":    r[0], "rua":       r[1], "face":      r[2],
            "coluna":     r[3], "nivel":     r[4],
            "produto":    r[5], "quantidade": r[6], "unidade":  r[7],
        }
        for r in rows
    ]


def get_ocupacao_geral(conn) -> dict:
    """
    Retorna {(rack_id, face): (ocupadas, total)} para todos os racks ativos.
    Total fixo = 13 colunas × 4 níveis = 52 células por rack.
    """
    ensure_mapa_tables(conn)
    TOTAL = 52
    # Uma única query GROUP BY substitui 20 queries individuais
    rows = conn.execute(
        "SELECT rua, face, COUNT(*) FROM mapa_posicoes WHERE produto_id IS NOT NULL GROUP BY rua, face"
    ).fetchall()
    ocupacao_map = {(r[0], r[1]): r[2] for r in rows}
    result = {}
    for rua in _get_rack_list(conn):
        for face in ["A", "B"]:
            result[(rua, face)] = (ocupacao_map.get((rua, face), 0), TOTAL)
    return result


def get_posicoes_vazias(conn) -> list:
    """
    Retorna lista de pos_key de todas as posições vazias do armazém,
    em ordem lógica (R1→R10, A→B, C1→C13, N1→N4).
    """
    ensure_mapa_tables(conn)
    ocupadas = {
        r[0]
        for r in conn.execute(
            "SELECT pos_key FROM mapa_posicoes WHERE produto_id IS NOT NULL"
        ).fetchall()
    }
    vazias = []
    for rua in _get_rack_list(conn):
        for face in ["A", "B"]:
            for col in range(1, 14):
                for niv in range(1, 5):
                    pk = f"{rua}-{face}-C{col}-N{niv}"
                    if pk not in ocupadas:
                        vazias.append(pk)
    return vazias


# ── Escrita ───────────────────────────────────────────────────────────────────

def upsert_palete(conn, pos_key: str, produto_id: str, quantidade: float, unidade: str):
    """Insere ou atualiza um palete numa posição."""
    ensure_mapa_tables(conn)
    rua, face, coluna, nivel = _parse_pos_key(pos_key)
    now = datetime.now(tz=_BRT).isoformat()
    conn.execute(
        """
        INSERT INTO mapa_posicoes (pos_key, rua, face, coluna, nivel, produto_id, quantidade, unidade, atualizado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pos_key) DO UPDATE SET
            produto_id = excluded.produto_id,
            quantidade = excluded.quantidade,
            unidade    = excluded.unidade,
            atualizado = excluded.atualizado
        """,
        (pos_key, rua, face, coluna, nivel, produto_id, quantidade, unidade, now),
    )
    conn.commit()


def delete_palete(conn, pos_key: str):
    """Remove o palete de uma posição (esvazia a célula)."""
    ensure_mapa_tables(conn)
    conn.execute("DELETE FROM mapa_posicoes WHERE pos_key = ?", (pos_key,))
    conn.commit()


def mover_palete(conn, pos_key_origem: str, pos_key_destino: str):
    """
    Move palete de origem para destino.
    Se destino estiver ocupado, faz swap (troca).
    Operação atômica via transação explícita.
    """
    ensure_mapa_tables(conn)

    origem_row = conn.execute(
        "SELECT produto_id, quantidade, unidade FROM mapa_posicoes WHERE pos_key = ?",
        (pos_key_origem,),
    ).fetchone()
    if not origem_row or not origem_row[0]:
        raise ValueError(f"Posição origem '{pos_key_origem}' está vazia.")

    destino_row = conn.execute(
        "SELECT produto_id, quantidade, unidade FROM mapa_posicoes WHERE pos_key = ?",
        (pos_key_destino,),
    ).fetchone()

    now = datetime.now(tz=_BRT).isoformat()
    rua_d, face_d, col_d, niv_d = _parse_pos_key(pos_key_destino)
    rua_o, face_o, col_o, niv_o = _parse_pos_key(pos_key_origem)

    _UPSERT = """
        INSERT INTO mapa_posicoes
            (pos_key, rua, face, coluna, nivel, produto_id, quantidade, unidade, atualizado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pos_key) DO UPDATE SET
            produto_id = excluded.produto_id,
            quantidade = excluded.quantidade,
            unidade    = excluded.unidade,
            atualizado = excluded.atualizado
    """

    try:
        if destino_row and destino_row[0]:
            # Swap: colocar produto do destino na origem
            conn.execute(
                _UPSERT,
                (pos_key_origem, rua_o, face_o, col_o, niv_o,
                 destino_row[0], destino_row[1], destino_row[2], now),
            )
        else:
            # Esvaziar origem
            conn.execute("DELETE FROM mapa_posicoes WHERE pos_key = ?", (pos_key_origem,))

        # Mover produto da origem para destino
        conn.execute(
            _UPSERT,
            (pos_key_destino, rua_d, face_d, col_d, niv_d,
             origem_row[0], origem_row[1], origem_row[2], now),
        )
        conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise


def add_produto_mapa(conn, nome: str, unidade: str) -> str:
    """
    Cria produto no mapa e retorna produto_id.
    Se já existir com o mesmo nome, retorna o id existente.
    """
    ensure_mapa_tables(conn)
    nome = nome.strip()
    existing = conn.execute(
        "SELECT produto_id FROM mapa_produtos WHERE LOWER(nome) = LOWER(?)", (nome,)
    ).fetchone()
    if existing:
        return existing[0]

    pid = str(uuid.uuid4())[:8]
    count = conn.execute("SELECT COUNT(*) FROM mapa_produtos").fetchone()[0]
    cor = _CORES[count % len(_CORES)]

    conn.execute(
        "INSERT OR IGNORE INTO mapa_produtos (produto_id, nome, unidade_pad, cor_hex) VALUES (?, ?, ?, ?)",
        (pid, nome, unidade, cor),
    )
    conn.commit()

    row = conn.execute("SELECT produto_id FROM mapa_produtos WHERE LOWER(nome) = LOWER(?)", (nome,)).fetchone()
    return row[0] if row else pid


def delete_produto_mapa(conn, produto_id: str):
    """Remove produto do catálogo (e limpa todas as posições que o usam)."""
    ensure_mapa_tables(conn)
    conn.execute("DELETE FROM mapa_posicoes WHERE produto_id = ?", (produto_id,))
    conn.execute("DELETE FROM mapa_produtos WHERE produto_id = ?", (produto_id,))
    conn.commit()


def _distribuir_proporcional(total: float, qtd_atuais: list) -> list:
    """
    Distribui `total` entre N posições proporcionalmente às quantidades
    atuais de cada posição.  Se todas estiverem zeradas/None, divide
    igualmente.  A soma dos valores retornados é sempre igual a `total`
    (ajuste no maior palete).
    """
    n = len(qtd_atuais)
    pesos = [max(float(q or 0), 0) for q in qtd_atuais]
    soma_pesos = sum(pesos)

    if soma_pesos == 0:
        # Divisão igualitária
        base   = int(total) // n
        resto  = int(total) % n
        result = [float(base + (1 if i < resto else 0)) for i in range(n)]
    else:
        proporcoes = [p / soma_pesos for p in pesos]
        result     = [round(total * prop, 2) for prop in proporcoes]
        # Corrige arredondamento para manter soma exata
        diff = round(total - sum(result), 2)
        if diff:
            idx_max = result.index(max(result))
            result[idx_max] = round(result[idx_max] + diff, 2)

    return result


def sync_quantidades_from_estoque(conn) -> dict:
    """
    Atualiza a quantidade de cada posição do mapa com o valor de
    estoque_mestre.qtd_sistema, casando pelo nome do produto
    (case-insensitive).

    Produtos em múltiplas posições têm sua quantidade distribuída
    proporcionalmente às quantidades já registradas em cada posição
    (ou igualmente se todas estiverem zeradas).

    Retorna:
        {
            "atualizadas": int,   # posições atualizadas com sucesso
            "sem_match":   list,  # nomes sem correspondência no estoque
        }
    """
    ensure_mapa_tables(conn)

    # 1. Busca todos os produtos do mapa com suas posições e quantidades atuais
    mapa_rows = conn.execute(
        """
        SELECT mp.produto_id, mp.nome, p.pos_key, p.quantidade
        FROM   mapa_produtos mp
        JOIN   mapa_posicoes p ON p.produto_id = mp.produto_id
        WHERE  p.produto_id IS NOT NULL
        ORDER  BY mp.produto_id, p.pos_key
        """
    ).fetchall()

    if not mapa_rows:
        return {"atualizadas": 0, "sem_match": []}

    # 2. Busca quantidades do estoque_mestre indexadas por nome em lowercase
    estoque_rows = conn.execute(
        "SELECT produto, qtd_sistema FROM estoque_mestre WHERE produto IS NOT NULL"
    ).fetchall()
    estoque_map = {r[0].strip().lower(): (r[1] or 0) for r in estoque_rows if r[0]}

    # 3. Agrupa posições e quantidades por produto_id
    from collections import defaultdict
    posicoes_por_produto: dict  = defaultdict(list)   # pid → [(pos_key, qtd_atual)]
    nome_por_produto:     dict  = {}
    for pid, nome, pos_key, qtd in mapa_rows:
        posicoes_por_produto[pid].append((pos_key, qtd))
        nome_por_produto[pid] = nome

    atualizadas = 0
    sem_match:   list = []
    now = datetime.now(tz=_BRT).isoformat()

    for pid, posicoes in posicoes_por_produto.items():
        nome        = nome_por_produto[pid]
        qtd_estoque = estoque_map.get(nome.strip().lower())

        if qtd_estoque is None:
            sem_match.append(nome)
            continue

        pos_keys   = [p[0] for p in posicoes]
        qtd_atuais = [p[1] for p in posicoes]

        novas_qtds = _distribuir_proporcional(qtd_estoque, qtd_atuais)

        for pos_key, nova_qtd in zip(pos_keys, novas_qtds):
            conn.execute(
                "UPDATE mapa_posicoes SET quantidade = ?, atualizado = ? WHERE pos_key = ?",
                (nova_qtd, now, pos_key),
            )
            atualizadas += 1

    conn.commit()
    return {"atualizadas": atualizadas, "sem_match": []}
