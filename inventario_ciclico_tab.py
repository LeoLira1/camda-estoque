"""Aba de Inventário Cíclico — conferência contínua com grade de cards clicáveis."""
import re as _re
from datetime import datetime, timedelta, timezone

import streamlit as st

_BRT = timezone(timedelta(hours=-3))
_COLS = 5  # cards por linha

# Categorias agro-químicas — ficam no FIM do mapa; todo o resto (loja/ferramentas/outros) vem primeiro
_CICLO_LAST = frozenset({
    "HERBICIDAS", "HERBICIDA",
    "FUNGICIDAS", "FUNGICIDA",
    "INSETICIDAS", "INSETICIDA",
    "NEMATICIDAS", "NEMATICIDA",
    "ADUBOS FOLIARES", "ADUBOS FOLIARES E QUÍMICOS", "ADUBOS QUÍMICOS",
    "ADUBOS CORRETIVOS", "ADUBO FOLIAR",
    "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO", "ADJUVANTE",
    "ÓLEOS", "ÓLEOS MINERAIS E VEGETAIS",
    "SEMENTES", "SEMENTE",
    "MATURADORES",
    "BIOLOGICOS E INOCULANTES", "INOCULANTES", "INOCULANTES P/ SILAGEM",
    "SUPLEMENTO MINERAL",
})


def _sort_ciclo(cats: list) -> list:
    """Não-agro primeiro (alfabético), agro-químico por último (alfabético)."""
    first = sorted(c for c in cats if c.upper() not in _CICLO_LAST)
    last  = sorted(c for c in cats if c.upper() in _CICLO_LAST)
    return first + last


def _safe_id(codigo: str) -> str:
    return "cic-" + _re.sub(r"[^a-zA-Z0-9]", "-", str(codigo))


def _status_colors(status_c: str) -> tuple:
    """(border_color, card_bg)"""
    if status_c == "ok":
        return "#00d68f", "rgba(0,214,143,0.10)"
    if status_c == "divergencia":
        return "#ff4757", "rgba(255,71,87,0.15)"
    return "#ffa502", "rgba(255,165,2,0.07)"


# ── CRUD ──────────────────────────────────────────────────────────────────────

def _marcar_ciclo_ok(codigo: str, get_db, sync_db) -> bool:
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute(
            "SELECT qtd_sistema FROM estoque_mestre WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not row:
            return False
        qtd_atual = row[0]
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo = 'ok',
                qtd_contada_ciclo = ?,
                qtd_sistema_na_contagem = ?,
                contado_ciclo_em = ?
            WHERE codigo = ?
        """, (qtd_atual, qtd_atual, now, codigo))
        conn.commit()
        sync_db()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao marcar OK: {e}")
        return False


def _marcar_ciclo_divergencia(codigo: str, qtd_real: int, get_db, sync_db) -> bool:
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute(
            "SELECT qtd_sistema FROM estoque_mestre WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not row:
            return False
        qtd_atual = row[0]
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo = 'divergencia',
                qtd_contada_ciclo = ?,
                qtd_sistema_na_contagem = ?,
                contado_ciclo_em = ?
            WHERE codigo = ?
        """, (qtd_real, qtd_atual, now, codigo))
        conn.commit()
        sync_db()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao marcar divergência: {e}")
        return False


def _desfazer_conferencia(codigo: str, get_db, sync_db) -> bool:
    try:
        conn = get_db()
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo = '',
                qtd_contada_ciclo = NULL,
                qtd_sistema_na_contagem = NULL,
                contado_ciclo_em = ''
            WHERE codigo = ?
        """, (codigo,))
        conn.commit()
        sync_db()
        return True
    except Exception:
        return False


def _get_progresso_ciclo(get_db) -> dict:
    try:
        conn = get_db()
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status_ciclo = 'ok'         THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN status_ciclo = 'divergencia' THEN 1 ELSE 0 END) as div,
                SUM(CASE WHEN status_ciclo = '' OR status_ciclo IS NULL THEN 1 ELSE 0 END) as pendente
            FROM estoque_mestre
        """).fetchone()
        return {
            "total":       row[0] or 0,
            "ok":          row[1] or 0,
            "divergencia": row[2] or 0,
            "pendente":    row[3] or 0,
        }
    except Exception:
        return {"total": 0, "ok": 0, "divergencia": 0, "pendente": 0}


# ── Main tab ──────────────────────────────────────────────────────────────────

def build_inventario_ciclico_tab(
    get_db, _using_cloud, sync_db,
    build_css_treemap, sort_categorias, get_current_stock,
    short_name=None,
):
    if short_name is None:
        short_name = lambda x: x  # noqa: E731

    df = get_current_stock()
    progresso = _get_progresso_ciclo(get_db)

    conferidos = progresso["ok"] + progresso["divergencia"]
    pct = (conferidos / max(progresso["total"], 1)) * 100

    # ── Stat cards ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card">
            <div class="stat-value amber">{progresso['pendente']}</div>
            <div class="stat-label">Pendentes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{progresso['ok']}</div>
            <div class="stat-label">OK</div>
        </div>
        <div class="stat-card">
            <div class="stat-value red">{progresso['divergencia']}</div>
            <div class="stat-label">Divergência</div>
        </div>
        <div class="stat-card">
            <div class="stat-value blue">{pct:.1f}%</div>
            <div class="stat-label">Cobertura</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='display:flex;gap:16px;font-size:0.7rem;margin:6px 0 10px 0;
                color:#64748b;font-family:JetBrains Mono,monospace;'>
        <span>🟡 Aguardando — clique para conferir</span>
        <span>🟢 Conferido OK</span>
        <span>🔴 Divergência</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Filtro de categoria ───────────────────────────────────────────────────
    all_cats = _sort_ciclo(df["categoria"].unique().tolist())
    filtro_cat = st.selectbox(
        "Filtrar categoria",
        ["TODOS"] + all_cats,
        key="inv_ciclico_filtro_cat",
    )

    # ── Painel de conferência (aparece quando um card é clicado) ──────────────
    sel_codigo = st.session_state.get("ciclo_sel")
    if sel_codigo:
        sel_rows = df[df["codigo"] == sel_codigo]
        if not sel_rows.empty:
            produto_row = sel_rows.iloc[0]
            with st.container(border=True):
                col_info, col_close = st.columns([6, 1])
                col_info.markdown(f"**{produto_row['produto']}**")
                col_info.caption(
                    f"Categoria: {produto_row['categoria']} · "
                    f"Sistema: **{produto_row['qtd_sistema']}** unidades"
                )
                if col_close.button("✖", key="ciclo_fechar", help="Fechar painel"):
                    st.session_state.pop("ciclo_sel", None)
                    st.rerun()

                col1, col2 = st.columns(2)
                if col1.button(
                    "✅ Confirmar OK",
                    use_container_width=True,
                    type="primary",
                    key="inv_ciclico_btn_ok",
                ):
                    if _marcar_ciclo_ok(sel_codigo, get_db, sync_db):
                        st.session_state.pop("ciclo_sel", None)
                        st.toast(f"✅ {produto_row['produto']} confirmado OK", icon="🟢")
                        st.cache_data.clear()
                        st.rerun()

                with col2.popover("⚠️ Divergência", use_container_width=True):
                    qtd_real = st.number_input(
                        "Quantidade física real",
                        min_value=0,
                        value=int(produto_row["qtd_sistema"]),
                        key="inv_ciclico_qtd_real",
                    )
                    st.caption(f"Sistema diz: {produto_row['qtd_sistema']}")
                    if st.button(
                        "Salvar divergência",
                        key="inv_ciclico_salvar_div",
                        type="primary",
                        use_container_width=True,
                    ):
                        if _marcar_ciclo_divergencia(sel_codigo, int(qtd_real), get_db, sync_db):
                            st.session_state.pop("ciclo_sel", None)
                            st.toast(
                                f"⚠️ {produto_row['produto']}: divergência registrada",
                                icon="🔴",
                            )
                            st.cache_data.clear()
                            st.rerun()
        else:
            # Código inexistente (e.g. produto removido) — limpa seleção silenciosamente
            st.session_state.pop("ciclo_sel", None)

    # ── Desfazer conferência ──────────────────────────────────────────────────
    with st.expander("🔧 Desfazer conferência (caso tenha marcado errado)"):
        conferidos_df = df[df["status_ciclo"].isin(["ok", "divergencia"])].copy()
        if not conferidos_df.empty:
            conferidos_df = conferidos_df.sort_values("contado_ciclo_em", ascending=False)
            conferidos_df["_lbl"] = conferidos_df.apply(
                lambda r: (
                    f"[{r['status_ciclo'].upper()}] {r['produto']} "
                    f"— {r.get('contado_ciclo_em', '')}"
                ),
                axis=1,
            )
            opts_desfazer: dict = {"": None}
            for _, r in conferidos_df.head(30).iterrows():
                opts_desfazer[r["_lbl"]] = r["codigo"]

            escolha_desfazer = st.selectbox(
                "Últimos conferidos",
                options=list(opts_desfazer.keys()),
                key="inv_ciclico_desfazer_sel",
            )
            if escolha_desfazer and st.button("Desfazer", key="inv_ciclico_btn_desfazer"):
                if _desfazer_conferencia(opts_desfazer[escolha_desfazer], get_db, sync_db):
                    st.toast("🔄 Conferência desfeita", icon="↩️")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.caption("Nenhum produto conferido ainda.")

    st.divider()

    # ── Grade de cards clicáveis ──────────────────────────────────────────────
    # Determina quais categorias exibir
    cats_to_show = (
        [c for c in all_cats if c == filtro_cat]
        if filtro_cat != "TODOS"
        else all_cats
    )
    df_grid = df[df["categoria"].isin(cats_to_show)].copy()

    if df_grid.empty:
        st.info("Nenhum produto para exibir.")
        return

    # CSS único para todos os cards (gerado de uma vez, não por card)
    sel_codigo = st.session_state.get("ciclo_sel")  # relê após possível rerun
    css_rules: list[str] = ["<style>"]
    for _, prod in df_grid.iterrows():
        status_c = str(prod.get("status_ciclo", "") or "")
        border_color, card_bg = _status_colors(status_c)
        sid = _safe_id(prod["codigo"])
        ring = (
            "outline:2px solid #ffffff;outline-offset:2px;"
            if sel_codigo == prod["codigo"]
            else ""
        )
        css_rules.append(f"""
        [data-testid="stColumn"]:has(#{sid}) [data-testid="stButton"] button,
        [data-testid="stVerticalBlock"]:has(> div > #{sid}) > div[data-testid="stButton"] button {{
            background:{card_bg}!important;
            border:none!important;
            border-left:3px solid {border_color}!important;
            border-radius:10px!important;
            padding:10px 8px!important;
            text-align:left!important;
            min-height:70px!important;
            width:100%!important;
            color:#e8eaf0!important;
            font-family:'JetBrains Mono',monospace!important;
            font-size:0.65rem!important;
            line-height:1.35!important;
            white-space:normal!important;
            word-break:break-word!important;
            {ring}
            transition:opacity .15s,transform .1s!important;
        }}
        [data-testid="stColumn"]:has(#{sid}) [data-testid="stButton"] button:hover,
        [data-testid="stVerticalBlock"]:has(> div > #{sid}) > div[data-testid="stButton"] button:hover {{
            opacity:.8!important;transform:scale(1.025)!important;
        }}""")
    css_rules.append("</style>")
    st.markdown("".join(css_rules), unsafe_allow_html=True)

    # Renderiza categoria por categoria
    for cat in cats_to_show:
        cat_df = df_grid[df_grid["categoria"] == cat].sort_values("produto")
        if cat_df.empty:
            continue

        st.markdown(
            f'<div style="font-size:.75rem;color:#64748b;font-weight:700;'
            f'text-transform:uppercase;border-bottom:1px solid #1e293b;'
            f'padding-bottom:4px;margin:12px 0 6px 0;">'
            f'{cat}'
            f'<span style="font-size:.6rem;color:#4a5568;font-weight:400;margin-left:6px;">'
            f'({len(cat_df)})</span></div>',
            unsafe_allow_html=True,
        )

        for row_start in range(0, len(cat_df), _COLS):
            chunk = cat_df.iloc[row_start : row_start + _COLS]
            cols = st.columns(_COLS)
            for i, (_, prod) in enumerate(chunk.iterrows()):
                sid = _safe_id(prod["codigo"])
                label = f"{short_name(str(prod['produto']))}\n{prod['qtd_sistema']}"
                with cols[i]:
                    st.markdown(
                        f'<div id="{sid}" style="display:none"></div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(label, key=f"cic_card_{prod['codigo']}"):
                        cur = st.session_state.get("ciclo_sel")
                        if cur == prod["codigo"]:
                            st.session_state.pop("ciclo_sel", None)
                        else:
                            st.session_state["ciclo_sel"] = prod["codigo"]
                        st.rerun()
