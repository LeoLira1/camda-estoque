"""Aba de Inventário Cíclico — seleciona 15 produtos/dia por score e registra contagens."""
import json
import os
import random
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

_BRT = timezone(timedelta(hours=-3))
_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "camda_cats_full.json")
_PRODUTOS_POR_DIA = 15


# ─── Catálogo ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _load_catalogo() -> list:
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ─── Score ─────────────────────────────────────────────────────────────────────

def _calc_score(prioridade: int, dias_sem_contar: int, venda_recente: bool) -> float:
    base = 100 if prioridade == 1 else (50 if prioridade == 2 else 10)
    return base + min(dias_sem_contar, 60) + (30 if venda_recente else 0)


# ─── Seleção diária ────────────────────────────────────────────────────────────

def selecionar_produtos_dia(data_str: str, contagens_recentes: dict | None = None) -> list:
    """Retorna lista de produtos selecionados para o dia (com metadados de categoria)."""
    catalogo = _load_catalogo()
    contagens_recentes = contagens_recentes or {}

    todos: list[dict] = []
    for cat in catalogo:
        for prod in cat["produtos"]:
            dias = prod["dias_sem_contar"]
            pid = str(prod["id"])
            if pid in contagens_recentes:
                try:
                    ultima = datetime.fromisoformat(contagens_recentes[pid]).date()
                    hoje = datetime.now(_BRT).date()
                    dias = max(0, (hoje - ultima).days)
                except Exception:
                    pass

            score = _calc_score(cat["prioridade"], dias, prod.get("venda_recente", False))
            todos.append({
                "produto_id": pid,
                "produto_nome": prod["nome"],
                "categoria_id": cat["id"],
                "categoria_label": cat["label"],
                "categoria_cor": cat["cor"],
                "qtd_sistema": prod["qtd_sistema"],
                "score": score,
                "prioridade": cat["prioridade"],
                "venda_recente": prod.get("venda_recente", False),
                "dias_sem_contar": dias,
            })

    seed = int(data_str.replace("-", ""))
    rng = random.Random(seed)
    todos.sort(key=lambda x: (-x["score"], rng.random()))
    return todos[:_PRODUTOS_POR_DIA]


# ─── DB helpers ────────────────────────────────────────────────────────────────

def get_contagens_recentes(conn) -> dict:
    rows = conn.execute(
        "SELECT produto_id, MAX(data_contagem) as ultima FROM inventario_ciclico "
        "WHERE qtd_contada IS NOT NULL GROUP BY produto_id"
    ).fetchall()
    return {str(r[0]): r[1] for r in rows}


def get_sessao_do_dia(conn, data_str: str) -> pd.DataFrame:
    rows = conn.execute(
        "SELECT * FROM inventario_ciclico WHERE data_contagem = ? ORDER BY id",
        (data_str,),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    cols = [d[0] for d in conn.execute("SELECT * FROM inventario_ciclico LIMIT 0").description]
    return pd.DataFrame(rows, columns=cols)


def inicializar_sessao(conn, data_str: str, _using_cloud: bool = False) -> None:
    recentes = get_contagens_recentes(conn)
    selecionados = selecionar_produtos_dia(data_str, recentes)
    for p in selecionados:
        conn.execute(
            """
            INSERT OR IGNORE INTO inventario_ciclico
                (data_contagem, produto_id, produto_nome, categoria_id,
                 categoria_label, categoria_cor, qtd_sistema, score)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                data_str,
                p["produto_id"],
                p["produto_nome"],
                p["categoria_id"],
                p["categoria_label"],
                p["categoria_cor"],
                p["qtd_sistema"],
                p["score"],
            ),
        )
    conn.commit()
    if _using_cloud:
        try:
            conn.sync()
        except Exception:
            pass


def salvar_contagem(
    conn,
    data_str: str,
    produto_id: str,
    qtd_contada: float,
    observacao: str,
    _using_cloud: bool = False,
) -> float:
    row = conn.execute(
        "SELECT qtd_sistema FROM inventario_ciclico WHERE data_contagem=? AND produto_id=?",
        (data_str, produto_id),
    ).fetchone()
    qtd_sistema = float(row[0]) if row else 0.0
    divergencia = qtd_contada - qtd_sistema
    contado_em = datetime.now(_BRT).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        UPDATE inventario_ciclico
        SET qtd_contada=?, divergencia=?, contado_em=?, observacao=?
        WHERE data_contagem=? AND produto_id=?
        """,
        (qtd_contada, divergencia, contado_em, observacao, data_str, produto_id),
    )
    conn.commit()
    if _using_cloud:
        try:
            conn.sync()
        except Exception:
            pass
    return divergencia


def salvar_divergencias_no_mestre(conn, data_str: str, _using_cloud: bool = False) -> int:
    rows = conn.execute(
        """
        SELECT produto_id, produto_nome, categoria_label, divergencia
        FROM inventario_ciclico
        WHERE data_contagem=? AND divergencia IS NOT NULL AND divergencia != 0
        """,
        (data_str,),
    ).fetchall()
    criado_em = datetime.now(_BRT).strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    for pid, nome, cat, delta in rows:
        conn.execute(
            """
            INSERT INTO divergencias (codigo, produto, categoria, delta, status, cooperado, criado_em)
            VALUES (?,?,?,?,?,?,?)
            """,
            (pid, nome, cat, int(delta), "aberta", "Inventário Cíclico", criado_em),
        )
        count += 1
    if count:
        conn.commit()
        if _using_cloud:
            try:
                conn.sync()
            except Exception:
                pass
    return count


def get_historico_ciclico(conn, dias: int = 30) -> pd.DataFrame:
    desde = (datetime.now(_BRT) - timedelta(days=dias)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM inventario_ciclico WHERE data_contagem >= ? ORDER BY data_contagem DESC, id",
        (desde,),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    cols = [d[0] for d in conn.execute("SELECT * FROM inventario_ciclico LIMIT 0").description]
    return pd.DataFrame(rows, columns=cols)


# ─── Status helper ─────────────────────────────────────────────────────────────

def _status_of(row: pd.Series | None) -> str:
    if row is None or pd.isna(row.get("qtd_contada")):
        return "pend"
    if float(row["divergencia"] or 0) != 0:
        return "div"
    return "ok"


# ─── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&display=swap');
.cic-prod-name { font-family:'IBM Plex Mono',monospace; font-size:15px; font-weight:600; color:#E6EDF3; margin-bottom:2px; }
.cic-prod-cat  { font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:1px; }
</style>
"""

# ─── Main tab ──────────────────────────────────────────────────────────────────

def build_inventario_ciclico_tab(get_db, _using_cloud: bool = False):
    st.markdown(_CSS, unsafe_allow_html=True)

    conn = get_db()
    hoje = datetime.now(_BRT).strftime("%Y-%m-%d")

    tab_contagem, tab_historico = st.tabs(["Contagem", "Histórico"])

    # ── Contagem ───────────────────────────────────────────────────────────────
    with tab_contagem:
        df_sessao = get_sessao_do_dia(conn, hoje)
        if df_sessao.empty:
            with st.spinner("Selecionando produtos…"):
                inicializar_sessao(conn, hoje, _using_cloud)
            df_sessao = get_sessao_do_dia(conn, hoje)
            conn = get_db()

        if df_sessao.empty:
            st.error("Não foi possível inicializar a sessão.")
            return

        total = len(df_sessao)
        contados = int((df_sessao["qtd_contada"].notna()).sum())
        pct = int(contados / total * 100) if total else 0

        # Barra de progresso fina
        bar_color = "#56D364" if pct == 100 else "#388BFD"
        st.markdown(
            f'<div style="background:#21262D;border-radius:2px;height:4px;margin-bottom:24px;">'
            f'<div style="height:4px;border-radius:2px;width:{pct}%;background:{bar_color};"></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Grade de bolinhas ──────────────────────────────────────────────────
        COLS = 5
        prod_sel_id = st.session_state.get("ciclico_prod_sel")

        for row_start in range(0, total, COLS):
            chunk = df_sessao.iloc[row_start : row_start + COLS]
            grid_cols = st.columns(COLS)

            for i, (_, prow) in enumerate(chunk.iterrows()):
                pid = str(prow["produto_id"])
                status = _status_of(prow)
                color = "#56D364" if status == "ok" else "#F85149" if status == "div" else "#F0B429"
                is_sel = str(prod_sel_id) == pid if prod_sel_id is not None else False
                ring = "outline:3px solid #FFFFFF;outline-offset:3px;" if is_sel else ""
                marker = f"cm-{pid}"

                with grid_cols[i]:
                    # CSS individual por bolinha — cobre os diferentes data-testids
                    # do Streamlit entre versões (stColumn, column, stVerticalBlock)
                    st.markdown(
                        f"""<style>
                        [data-testid="stVerticalBlock"]:has(> div > #{marker}) > div[data-testid="stButton"] button,
                        [data-testid="stVerticalBlock"]:has(#{marker}) > [data-testid="stButton"] button,
                        [data-testid="stColumn"]:has(#{marker}) [data-testid="stButton"] button,
                        [data-testid="column"]:has(#{marker}) [data-testid="stButton"] button {{
                            background:{color}!important;
                            border:none!important;
                            border-radius:50%!important;
                            width:48px!important;
                            max-width:48px!important;
                            height:48px!important;
                            min-height:48px!important;
                            padding:0!important;
                            color:transparent!important;
                            font-size:1px!important;
                            line-height:1!important;
                            transition:transform .15s,opacity .15s!important;
                            {ring}
                        }}
                        [data-testid="stVerticalBlock"]:has(#{marker}) > [data-testid="stButton"] button:hover,
                        [data-testid="stColumn"]:has(#{marker}) [data-testid="stButton"] button:hover,
                        [data-testid="column"]:has(#{marker}) [data-testid="stButton"] button:hover {{
                            opacity:.75!important;
                            transform:scale(1.16)!important;
                        }}
                        </style><div id="{marker}" style="display:none"></div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button("\u00b7", key=f"dot_{pid}"):
                        if is_sel:
                            st.session_state.pop("ciclico_prod_sel", None)
                        else:
                            st.session_state["ciclico_prod_sel"] = pid
                        st.session_state.pop("ciclico_show_div", None)
                        st.rerun()

        # ── Painel do produto selecionado ──────────────────────────────────────
        if prod_sel_id is not None:
            mask = df_sessao["produto_id"].astype(str) == str(prod_sel_id)
            if mask.any():
                prow_sel = df_sessao[mask].iloc[0]
                status_sel = _status_of(prow_sel)

                st.markdown("---")

                col_name, col_qty = st.columns([3, 1])
                with col_name:
                    cat_cor = prow_sel.get("categoria_cor", "#8B949E")
                    st.markdown(
                        f'<div class="cic-prod-name">{prow_sel["produto_nome"]}</div>'
                        f'<div class="cic-prod-cat" style="color:{cat_cor};">'
                        f'{prow_sel["categoria_label"].upper()}</div>',
                        unsafe_allow_html=True,
                    )
                with col_qty:
                    st.metric("estoque", int(prow_sel["qtd_sistema"]))

                # Status atual (se já contado)
                if status_sel != "pend":
                    if status_sel == "ok":
                        st.success(f"✅ OK — contado: {int(prow_sel['qtd_contada'])}")
                    else:
                        dv = float(prow_sel["divergencia"])
                        s = "+" if dv > 0 else ""
                        st.error(
                            f"⚠️ Divergência: {s}{int(dv)}  (contado: {int(prow_sel['qtd_contada'])})"
                        )

                # Botões de ação
                show_div = st.session_state.get("ciclico_show_div", False)
                c_ok, c_div = st.columns(2)

                with c_ok:
                    if st.button("✅  OK", key="btn_ok_sel", use_container_width=True, type="primary"):
                        conn = get_db()
                        salvar_contagem(
                            conn, hoje, prod_sel_id,
                            float(prow_sel["qtd_sistema"]), "", _using_cloud,
                        )
                        st.session_state.pop("ciclico_prod_sel", None)
                        st.session_state.pop("ciclico_show_div", None)
                        st.cache_data.clear()
                        st.rerun()

                with c_div:
                    if st.button("⚠️  Divergência", key="btn_div_toggle", use_container_width=True):
                        st.session_state["ciclico_show_div"] = not show_div
                        st.rerun()

                # Formulário de divergência
                if show_div:
                    default_qtd = (
                        float(prow_sel["qtd_contada"])
                        if pd.notna(prow_sel.get("qtd_contada"))
                        else float(prow_sel["qtd_sistema"])
                    )
                    qtd_in = st.number_input(
                        "Qtd contada",
                        min_value=0.0,
                        step=1.0,
                        value=default_qtd,
                        format="%.0f",
                        key="qtd_div_in",
                    )
                    if st.button("Confirmar divergência", key="btn_div_confirm", use_container_width=True):
                        conn = get_db()
                        salvar_contagem(conn, hoje, prod_sel_id, qtd_in, "", _using_cloud)
                        st.session_state.pop("ciclico_prod_sel", None)
                        st.session_state.pop("ciclico_show_div", None)
                        st.cache_data.clear()
                        st.rerun()

        # Botão exportar (só se houver contagens)
        if contados > 0:
            st.markdown("---")
            if st.button("📤 Exportar Divergências", key="btn_export_divs"):
                conn = get_db()
                n = salvar_divergencias_no_mestre(conn, hoje, _using_cloud)
                if n > 0:
                    st.success(f"{n} divergência(s) exportada(s).")
                else:
                    st.info("Nenhuma divergência para exportar.")

    # ── Histórico ──────────────────────────────────────────────────────────────
    with tab_historico:
        st.markdown("**Histórico — últimos 30 dias**")
        conn = get_db()
        df_hist = get_historico_ciclico(conn, dias=30)

        if df_hist.empty:
            st.info("Nenhuma contagem registrada ainda.")
            return

        df_contados = df_hist[df_hist["qtd_contada"].notna()].copy()
        if not df_contados.empty:
            resumo = (
                df_contados.groupby("data_contagem")
                .agg(
                    contados=("produto_id", "count"),
                    divergencias=("divergencia", lambda x: (x != 0).sum()),
                )
                .reset_index()
                .sort_values("data_contagem", ascending=False)
            )
            resumo.columns = ["Data", "Contados", "Divergências"]
            st.dataframe(resumo, use_container_width=True, hide_index=True)

        st.markdown("---")
        df_show = df_hist.rename(columns={
            "data_contagem": "Data",
            "produto_nome": "Produto",
            "categoria_label": "Categoria",
            "qtd_sistema": "Qtd Sistema",
            "qtd_contada": "Qtd Contada",
            "divergencia": "Divergência",
            "contado_em": "Registrado Em",
            "observacao": "Obs",
        })
        cols_show = [
            c for c in
            ["Data", "Produto", "Categoria", "Qtd Sistema", "Qtd Contada", "Divergência", "Registrado Em", "Obs"]
            if c in df_show.columns
        ]
        st.dataframe(df_show[cols_show], use_container_width=True, hide_index=True)
