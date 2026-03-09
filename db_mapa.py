"""
db_mapa.py — Funções de banco para o Mapa Visual do Armazém CAMDA.

Estrutura física:
  - 6 ruas (R1..R6), 2 faces (A=frente, B=fundo)
  - 13 colunas por rack, 4 níveis (N1=chão, N4=topo)
  - pos_key: "{RUA}-{FACE}-C{COL}-N{NIVEL}"  ex: R1-A-C1-N1
"""

import uuid
from datetime import datetime, timezone, timedelta

_BRT = timezone(timedelta(hours=-3))

# ── Paleta de cores padrão para novos produtos ────────────────────────────────
_CORES = [
    "#4ade80", "#60a5fa", "#f59e0b", "#f87171",
    "#a78bfa", "#34d399", "#fb923c", "#e879f9",
    "#22d3ee", "#facc15", "#6ee7b7", "#fda4af",
]


def ensure_mapa_tables(conn):
    """Cria tabelas do mapa se não existirem (idempotente)."""
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
    conn.commit()


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
    Retorna {(rua, face): (ocupadas, total)} para todas as ruas e faces.
    Total fixo = 13 colunas × 4 níveis = 52 células por rack.
    """
    ensure_mapa_tables(conn)
    TOTAL = 52
    result = {}
    for rua in ["R1", "R2", "R3", "R4", "R5", "R6"]:
        for face in ["A", "B"]:
            ocupadas = conn.execute(
                "SELECT COUNT(*) FROM mapa_posicoes WHERE rua=? AND face=? AND produto_id IS NOT NULL",
                (rua, face),
            ).fetchone()[0]
            result[(rua, face)] = (ocupadas, TOTAL)
    return result


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
