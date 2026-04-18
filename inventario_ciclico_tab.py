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
            # Se contado recentemente, recalcula dias_sem_contar dinamicamente
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

    # Ordena por score desc; desempata com hash determinístico baseado na data
    seed = int(data_str.replace("-", ""))
    rng = random.Random(seed)
    todos.sort(key=lambda x: (-x["score"], rng.random()))
    return todos[:_PRODUTOS_POR_DIA]


# ─── DB helpers ────────────────────────────────────────────────────────────────

def get_contagens_recentes(conn) -> dict:
    """Retorna {produto_id: última data de contagem (str)}."""
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
    """Insere os 15 produtos do dia se ainda não existirem."""
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
    """Salva contagem e retorna divergência (contada - sistema)."""
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
    """Copia divergências não-zero do inventário cíclico para a tabela divergencias."""
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


# ─── UI helpers ────────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&display=swap');
.ciclico-root {
    font-family: 'IBM Plex Mono', monospace;
    background: #0D1117;
    border-radius: 8px;
    padding: 20px;
    color: #C9D1D9;
}
.ciclico-header { font-size: 11px; color: #58A6FF; letter-spacing: 2px; margin-bottom: 4px; }
.ciclico-title  { font-size: 22px; font-weight: 600; color: #E6EDF3; margin-bottom: 2px; }
.ciclico-sub    { font-size: 11px; color: #6E7681; margin-bottom: 20px; }
.ciclico-stat-box {
    background: #161B22; border: 1px solid #21262D; border-radius: 6px;
    padding: 12px 16px; text-align: center;
}
.ciclico-stat-num { font-size: 32px; font-weight: 300; }
.ciclico-stat-lbl { font-size: 10px; color: #8B949E; letter-spacing: 1px; }
.ciclico-progress-bar-bg {
    background: #21262D; border-radius: 2px; height: 4px; margin: 8px 0 16px 0;
}
.ciclico-progress-bar-fg {
    height: 4px; border-radius: 2px; transition: width .4s;
}
.ciclico-cat-row {
    background: #161B22; border: 1px solid #21262D; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 6px; cursor: pointer;
}
.ciclico-cat-row:hover { border-color: #388BFD; }
.ciclico-cat-row.selected { border-color: #388BFD; background: #1C2128; }
.ciclico-cat-label { font-size: 11px; font-weight: 600; letter-spacing: 1px; }
.ciclico-dots { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 6px; }
.ciclico-dot {
    width: 10px; height: 10px; border-radius: 50%;
    display: inline-block;
}
.ciclico-prod-row {
    background: #161B22; border: 1px solid #21262D; border-radius: 4px;
    padding: 8px 12px; margin-bottom: 4px; font-size: 12px; cursor: pointer;
}
.ciclico-prod-row:hover { border-color: #388BFD; }
.ciclico-prod-row.selected { border-color: #F0B429; background: #1C2128; }
.ciclico-badge {
    display: inline-block; border-radius: 3px; padding: 1px 6px;
    font-size: 10px; font-weight: 600; letter-spacing: 1px;
}
.badge-ok   { background: #1a3a2f; color: #56D364; border: 1px solid #2D6A4F; }
.badge-div  { background: #3a1a1a; color: #F85149; border: 1px solid #7A1E1E; }
.badge-pend { background: #21262D; color: #8B949E; border: 1px solid #30363D; }
</style>
"""


def _dot_html(color: str, status: str | None, size: int = 10) -> str:
    if status == "ok":
        bg = "#56D364"
    elif status == "div":
        bg = "#F85149"
    else:
        bg = "#30363D"
    return f'<span class="ciclico-dot" style="background:{bg};width:{size}px;height:{size}px;"></span>'


def _status_of(row: pd.Series | None) -> str:
    if row is None or pd.isna(row.get("qtd_contada")):
        return "pend"
    if float(row["divergencia"] or 0) != 0:
        return "div"
    return "ok"


# ─── Main tab ──────────────────────────────────────────────────────────────────

def build_inventario_ciclico_tab(get_db, _using_cloud: bool = False):
    st.markdown(_CSS, unsafe_allow_html=True)

    conn = get_db()
    hoje = datetime.now(_BRT).strftime("%Y-%m-%d")

    tab_contagem, tab_historico = st.tabs(["📋 Contagem do Dia", "📈 Histórico"])

    # ── Contagem do dia ────────────────────────────────────────────────────────
    with tab_contagem:
        # Inicializa sessão se necessário
        df_sessao = get_sessao_do_dia(conn, hoje)
        if df_sessao.empty:
            with st.spinner("Selecionando produtos para hoje…"):
                inicializar_sessao(conn, hoje, _using_cloud)
            df_sessao = get_sessao_do_dia(conn, hoje)
            conn = get_db()

        if df_sessao.empty:
            st.error("Não foi possível inicializar a sessão de hoje.")
            return

        total = len(df_sessao)
        contados = int((df_sessao["qtd_contada"].notna()).sum())
        divergentes = int(
            (df_sessao["divergencia"].notna() & (df_sessao["divergencia"] != 0)).sum()
        )
        pct = int(contados / total * 100) if total else 0

        # Header
        st.markdown(
            f"""
            <div class="ciclico-root">
              <div class="ciclico-header">◈ CAMDA AGROPECUÁRIA</div>
              <div class="ciclico-title">Inventário Cíclico</div>
              <div class="ciclico-sub">{hoje} &nbsp;·&nbsp; {total} produtos selecionados por score</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Stats row
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                f'<div class="ciclico-stat-box"><div class="ciclico-stat-num" style="color:#58A6FF">{total}</div>'
                f'<div class="ciclico-stat-lbl">TOTAL HOJE</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<div class="ciclico-stat-box"><div class="ciclico-stat-num" style="color:#56D364">{contados}</div>'
                f'<div class="ciclico-stat-lbl">CONTADOS</div></div>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<div class="ciclico-stat-box"><div class="ciclico-stat-num" style="color:#F85149">{divergentes}</div>'
                f'<div class="ciclico-stat-lbl">DIVERGÊNCIAS</div></div>',
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f'<div class="ciclico-stat-box"><div class="ciclico-stat-num" style="color:#F0B429">{pct}%</div>'
                f'<div class="ciclico-stat-lbl">PROGRESSO</div></div>',
                unsafe_allow_html=True,
            )

        # Progress bar
        bar_color = "#56D364" if pct == 100 else "#388BFD"
        st.markdown(
            f'<div class="ciclico-progress-bar-bg">'
            f'<div class="ciclico-progress-bar-fg" style="width:{pct}%;background:{bar_color};"></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Botão exportar divergências (só aparece se houver contagens finalizadas)
        if contados > 0:
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("📤 Exportar Divergências", key="btn_export_divs"):
                    n = salvar_divergencias_no_mestre(conn, hoje, _using_cloud)
                    if n > 0:
                        st.success(f"{n} divergência(s) salva(s) na aba Divergências.")
                    else:
                        st.info("Nenhuma divergência encontrada para exportar.")

        st.markdown("---")

        # Layout: esquerda = categorias, direita = produtos + formulário
        col_cats, col_prods = st.columns([2, 3], gap="medium")

        cats_no_dia = df_sessao["categoria_id"].unique().tolist()

        with col_cats:
            st.markdown("**Categorias no inventário de hoje**")

            if "ciclico_cat_sel" not in st.session_state:
                st.session_state["ciclico_cat_sel"] = cats_no_dia[0] if cats_no_dia else None

            for cat_id in cats_no_dia:
                df_cat = df_sessao[df_sessao["categoria_id"] == cat_id]
                cat_label = df_cat.iloc[0]["categoria_label"]
                cat_cor = df_cat.iloc[0]["categoria_cor"]
                n_cat = len(df_cat)
                n_ok = int((df_cat["qtd_contada"].notna()).sum())

                # Dots
                dots_html = ""
                for _, prow in df_cat.iterrows():
                    st_code = _status_of(prow)
                    dots_html += _dot_html(cat_cor, st_code)

                is_sel = st.session_state["ciclico_cat_sel"] == cat_id
                sel_class = "selected" if is_sel else ""

                st.markdown(
                    f"""<div class="ciclico-cat-row {sel_class}" style="border-left: 3px solid {cat_cor};">
                        <div class="ciclico-cat-label" style="color:{cat_cor}">{cat_label.upper()}</div>
                        <div style="font-size:10px;color:#6E7681;margin:2px 0;">{n_ok}/{n_cat} contados</div>
                        <div class="ciclico-dots">{dots_html}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"Selecionar {cat_label}",
                    key=f"btn_cat_{cat_id}",
                    use_container_width=True,
                ):
                    st.session_state["ciclico_cat_sel"] = cat_id
                    st.session_state.pop("ciclico_prod_sel", None)
                    st.rerun()

        with col_prods:
            cat_atual = st.session_state.get("ciclico_cat_sel")
            if not cat_atual:
                st.info("Selecione uma categoria à esquerda.")
                return

            df_cat_view = df_sessao[df_sessao["categoria_id"] == cat_atual]
            cat_label_atual = df_cat_view.iloc[0]["categoria_label"] if not df_cat_view.empty else cat_atual

            st.markdown(f"**{cat_label_atual}** — produtos selecionados hoje")

            if "ciclico_prod_sel" not in st.session_state:
                st.session_state["ciclico_prod_sel"] = None

            for _, prow in df_cat_view.iterrows():
                st_code = _status_of(prow)
                if st_code == "ok":
                    badge = '<span class="ciclico-badge badge-ok">OK</span>'
                elif st_code == "div":
                    badge = '<span class="ciclico-badge badge-div">DIV</span>'
                else:
                    badge = '<span class="ciclico-badge badge-pend">PENDENTE</span>'

                is_sel_prod = st.session_state.get("ciclico_prod_sel") == prow["produto_id"]
                sel_cls = "selected" if is_sel_prod else ""

                qtd_info = ""
                if st_code != "pend":
                    qtd_info = f" &nbsp;·&nbsp; contado: <b>{prow['qtd_contada']}</b> (sistema: {prow['qtd_sistema']})"

                st.markdown(
                    f"""<div class="ciclico-prod-row {sel_cls}">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:11px;flex:1;">{prow['produto_nome']}</span>
                            {badge}
                        </div>
                        <div style="font-size:10px;color:#6E7681;margin-top:3px;">
                            ID: {prow['produto_id']}{qtd_info}
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"Registrar contagem",
                    key=f"btn_prod_{prow['produto_id']}",
                    use_container_width=True,
                ):
                    st.session_state["ciclico_prod_sel"] = prow["produto_id"]
                    st.rerun()

            # Formulário de contagem
            prod_sel_id = st.session_state.get("ciclico_prod_sel")
            if prod_sel_id and prod_sel_id in df_cat_view["produto_id"].values:
                prow_sel = df_cat_view[df_cat_view["produto_id"] == prod_sel_id].iloc[0]

                st.markdown("---")
                st.markdown(f"**Registrar contagem** — `{prow_sel['produto_nome']}`")

                col_sys, col_in = st.columns(2)
                with col_sys:
                    st.metric("Qtd. Sistema", prow_sel["qtd_sistema"])

                with st.form(key=f"form_contagem_{prod_sel_id}"):
                    qtd_atual = prow_sel["qtd_contada"] if pd.notna(prow_sel.get("qtd_contada")) else 0.0
                    qtd_input = st.number_input(
                        "Qtd. Contada",
                        min_value=0.0,
                        step=1.0,
                        value=float(qtd_atual),
                        format="%.0f",
                    )
                    obs_atual = prow_sel.get("observacao") or ""
                    obs_input = st.text_input("Observação (opcional)", value=obs_atual)
                    submitted = st.form_submit_button("✅ Confirmar Contagem", use_container_width=True)

                if submitted:
                    conn = get_db()
                    div = salvar_contagem(
                        conn,
                        hoje,
                        prod_sel_id,
                        qtd_input,
                        obs_input,
                        _using_cloud,
                    )
                    if div == 0:
                        st.success(f"Contagem confirmada — sem divergência.")
                    else:
                        sinal = "+" if div > 0 else ""
                        st.warning(f"Contagem confirmada — divergência: **{sinal}{div:.0f}** unidades.")
                    st.session_state.pop("ciclico_prod_sel", None)
                    st.cache_data.clear()
                    st.rerun()

    # ── Histórico ──────────────────────────────────────────────────────────────
    with tab_historico:
        st.markdown("**Histórico de contagens — últimos 30 dias**")
        conn = get_db()
        df_hist = get_historico_ciclico(conn, dias=30)

        if df_hist.empty:
            st.info("Nenhuma contagem registrada ainda.")
            return

        # Resumo por data
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
        st.markdown("**Detalhes**")

        df_show = df_hist.copy()
        df_show = df_show.rename(columns={
            "data_contagem": "Data",
            "produto_nome": "Produto",
            "categoria_label": "Categoria",
            "qtd_sistema": "Qtd Sistema",
            "qtd_contada": "Qtd Contada",
            "divergencia": "Divergência",
            "contado_em": "Registrado Em",
            "observacao": "Obs",
        })
        cols_show = ["Data", "Produto", "Categoria", "Qtd Sistema", "Qtd Contada", "Divergência", "Registrado Em", "Obs"]
        cols_show = [c for c in cols_show if c in df_show.columns]
        st.dataframe(df_show[cols_show], use_container_width=True, hide_index=True)
