"""Aba de Inventário Cíclico — conferência contínua com cards clicáveis."""
import re as _re
from datetime import datetime, timedelta, timezone

import streamlit as st

_BRT = timezone(timedelta(hours=-3))
_COLS = 4  # cards por linha na grade de categoria

# Categorias agro-químicas ficam no FIM; loja/ferramentas/outros vêm PRIMEIRO
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

# CSS dos card-botões — 4 regras estáticas por prefixo de status
_CSS_CARDS = """<style>
[data-testid="stColumn"]:has([id^="cic-pend-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-pend-"]) [data-testid="stButton"] button {
    background:linear-gradient(135deg,rgba(255,165,2,0.38),rgba(180,100,0,0.28))!important;
    border:2px solid rgba(255,165,2,0.72)!important;
    border-radius:10px!important; padding:10px 8px!important;
    text-align:left!important; min-height:72px!important;
    width:100%!important; color:#fff!important;
    font-family:'JetBrains Mono',monospace!important;
    font-size:0.63rem!important; line-height:1.35!important;
    white-space:normal!important; word-break:break-word!important;
    transition:opacity .12s,transform .1s!important;
}
[data-testid="stColumn"]:has([id^="cic-ok-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-ok-"]) [data-testid="stButton"] button {
    background:linear-gradient(135deg,rgba(0,214,143,0.42),rgba(0,130,75,0.32))!important;
    border:2px solid rgba(0,214,143,0.75)!important;
    border-radius:10px!important; padding:10px 8px!important;
    text-align:left!important; min-height:72px!important;
    width:100%!important; color:#fff!important;
    font-family:'JetBrains Mono',monospace!important;
    font-size:0.63rem!important; line-height:1.35!important;
    white-space:normal!important; word-break:break-word!important;
    transition:opacity .12s,transform .1s!important;
}
[data-testid="stColumn"]:has([id^="cic-div-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-div-"]) [data-testid="stButton"] button {
    background:linear-gradient(135deg,rgba(255,71,87,0.48),rgba(160,20,30,0.38))!important;
    border:2px solid rgba(255,71,87,0.80)!important;
    border-radius:10px!important; padding:10px 8px!important;
    text-align:left!important; min-height:72px!important;
    width:100%!important; color:#fff!important;
    font-family:'JetBrains Mono',monospace!important;
    font-size:0.63rem!important; line-height:1.35!important;
    white-space:normal!important; word-break:break-word!important;
    transition:opacity .12s,transform .1s!important;
}
[data-testid="stColumn"]:has([id^="cic-sel-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-sel-"]) [data-testid="stButton"] button {
    outline:3px solid #ffffff!important; outline-offset:2px!important;
}
[data-testid="stColumn"]:has([id^="cic-pend-"]) [data-testid="stButton"] button:hover,
[data-testid="stColumn"]:has([id^="cic-ok-"]) [data-testid="stButton"] button:hover,
[data-testid="stColumn"]:has([id^="cic-div-"]) [data-testid="stButton"] button:hover {
    opacity:.80!important; transform:scale(1.03)!important;
}
</style>"""


def _sort_ciclo(cats: list) -> list:
    first = sorted(c for c in cats if c.upper() not in _CICLO_LAST)
    last  = sorted(c for c in cats if c.upper() in _CICLO_LAST)
    return first + last


def _safe(codigo: str) -> str:
    return _re.sub(r"[^a-zA-Z0-9]", "-", str(codigo))


def _status_prefix(status_c: str) -> str:
    if status_c == "ok":          return "cic-ok-"
    if status_c == "divergencia": return "cic-div-"
    return "cic-pend-"


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
        q = row[0]
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo='ok', qtd_contada_ciclo=?, qtd_sistema_na_contagem=?, contado_ciclo_em=?
            WHERE codigo=?
        """, (q, q, now, codigo))
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
        q = row[0]
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo='divergencia', qtd_contada_ciclo=?, qtd_sistema_na_contagem=?, contado_ciclo_em=?
            WHERE codigo=?
        """, (qtd_real, q, now, codigo))
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
            SET status_ciclo='', qtd_contada_ciclo=NULL, qtd_sistema_na_contagem=NULL, contado_ciclo_em=''
            WHERE codigo=?
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
            SELECT COUNT(*),
                SUM(CASE WHEN status_ciclo='ok'          THEN 1 ELSE 0 END),
                SUM(CASE WHEN status_ciclo='divergencia' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status_ciclo='' OR status_ciclo IS NULL THEN 1 ELSE 0 END)
            FROM estoque_mestre
        """).fetchone()
        return {"total": row[0] or 0, "ok": row[1] or 0, "divergencia": row[2] or 0, "pendente": row[3] or 0}
    except Exception:
        return {"total": 0, "ok": 0, "divergencia": 0, "pendente": 0}


# ── Painel de conferência ──────────────────────────────────────────────────────

def _render_painel(produto_row, get_db, sync_db):
    sel_codigo = str(produto_row["codigo"])
    with st.container(border=True):
        col_info, col_close = st.columns([6, 1])
        col_info.markdown(f"**{produto_row['produto']}**")
        col_info.caption(
            f"Categoria: {produto_row['categoria']} · "
            f"Sistema: **{produto_row['qtd_sistema']}** unidades"
        )
        if col_close.button("✖", key="cic_fechar"):
            st.session_state.pop("ciclo_sel", None)
            st.rerun()

        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar OK", use_container_width=True, type="primary", key="cic_ok"):
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
                key="cic_qtd",
            )
            st.caption(f"Sistema diz: {produto_row['qtd_sistema']}")
            if st.button("Salvar divergência", key="cic_salvar", type="primary", use_container_width=True):
                if _marcar_ciclo_divergencia(sel_codigo, int(qtd_real), get_db, sync_db):
                    st.session_state.pop("ciclo_sel", None)
                    st.toast(f"⚠️ {produto_row['produto']}: divergência registrada", icon="🔴")
                    st.cache_data.clear()
                    st.rerun()


# ── Grid de cards por categoria ────────────────────────────────────────────────

def _render_grid(cat_df, df, sel_codigo, short_name, get_db, sync_db):
    """Renderiza o grid de cards clicáveis para uma categoria."""
    st.markdown(_CSS_CARDS, unsafe_allow_html=True)

    # Painel de conferência aparece ACIMA dos cards quando algo está selecionado
    if sel_codigo:
        sel_rows = df[df["codigo"].astype(str) == sel_codigo]
        if not sel_rows.empty:
            _render_painel(sel_rows.iloc[0], get_db, sync_db)

    for row_start in range(0, len(cat_df), _COLS):
        chunk = cat_df.iloc[row_start : row_start + _COLS]
        cols = st.columns(_COLS)
        for i, (_, prod) in enumerate(chunk.iterrows()):
            status_c = str(prod.get("status_ciclo", "") or "")
            prefix = _status_prefix(status_c)
            safe = _safe(str(prod["codigo"]))
            is_sel = sel_codigo == str(prod["codigo"])
            label = f"{short_name(str(prod['produto']))}\n{prod['qtd_sistema']}"

            with cols[i]:
                marker = f'<div id="{prefix}{safe}" style="display:none"></div>'
                if is_sel:
                    marker += f'<div id="cic-sel-{safe}" style="display:none"></div>'
                st.markdown(marker, unsafe_allow_html=True)

                if st.button(label, key=f"cic_{prod['codigo']}"):
                    if is_sel:
                        st.session_state.pop("ciclo_sel", None)
                    else:
                        st.session_state["ciclo_sel"] = str(prod["codigo"])
                    st.rerun()


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
        <div class="stat-card"><div class="stat-value amber">{progresso['pendente']}</div><div class="stat-label">Pendentes</div></div>
        <div class="stat-card"><div class="stat-value">{progresso['ok']}</div><div class="stat-label">OK</div></div>
        <div class="stat-card"><div class="stat-value red">{progresso['divergencia']}</div><div class="stat-label">Divergência</div></div>
        <div class="stat-card"><div class="stat-value blue">{pct:.1f}%</div><div class="stat-label">Cobertura</div></div>
    </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div style='display:flex;gap:16px;font-size:0.7rem;margin:6px 0 10px 0;
                color:#64748b;font-family:JetBrains Mono,monospace;'>
        <span>🟡 Aguardando</span><span>🟢 Conferido OK</span><span>🔴 Divergência</span>
    </div>""", unsafe_allow_html=True)

    # ── Filtro de categoria ───────────────────────────────────────────────────
    all_cats = _sort_ciclo(df["categoria"].unique().tolist())
    filtro_cat = st.selectbox(
        "Categoria para conferir",
        ["TODOS"] + all_cats,
        key="inv_ciclico_filtro_cat",
    )

    sel_codigo = st.session_state.get("ciclo_sel")

    # ── TODOS: busca por nome ─────────────────────────────────────────────────
    if filtro_cat == "TODOS":
        busca = st.text_input(
            "🔍 Buscar produto para conferir",
            key="cic_busca_todos",
            placeholder="Digite parte do nome...",
        )
        if busca and len(busca) >= 2:
            matches = df[df["produto"].str.contains(busca, case=False, na=False)].head(30)
            if not matches.empty:
                def _lbl(r):
                    sc = str(r.get("status_ciclo", "") or "")
                    em = "🟢" if sc == "ok" else "🔴" if sc == "divergencia" else "🟡"
                    return f"{em} {r['produto']}  ({r['categoria']}) — {r['qtd_sistema']}"

                opts: dict = {"": None}
                for _, r in matches.iterrows():
                    opts[_lbl(r)] = str(r["codigo"])

                escolha = st.selectbox("", list(opts.keys()), key="cic_sel_todos")
                if escolha and opts[escolha]:
                    sel_codigo = opts[escolha]
                    st.session_state["ciclo_sel"] = sel_codigo

            else:
                st.caption("Nenhum produto encontrado.")

        # Painel de conferência para produto buscado
        if sel_codigo:
            sel_rows = df[df["codigo"].astype(str) == sel_codigo]
            if not sel_rows.empty:
                _render_painel(sel_rows.iloc[0], get_db, sync_db)
            else:
                st.session_state.pop("ciclo_sel", None)

    # ── Categoria específica: grid de cards ───────────────────────────────────
    else:
        cat_df = df[df["categoria"] == filtro_cat].sort_values("produto").reset_index(drop=True)

        if cat_df.empty:
            st.info(f"Nenhum produto na categoria {filtro_cat}.")
        else:
            # Limpa seleção se pertence a outra categoria
            if sel_codigo and sel_codigo not in set(cat_df["codigo"].astype(str)):
                st.session_state.pop("ciclo_sel", None)
                sel_codigo = None

            _render_grid(cat_df, df, sel_codigo, short_name, get_db, sync_db)

    # ── Desfazer conferência ──────────────────────────────────────────────────
    with st.expander("🔧 Desfazer conferência (caso tenha marcado errado)"):
        conferidos_df = df[df["status_ciclo"].isin(["ok", "divergencia"])].copy()
        if not conferidos_df.empty:
            conferidos_df = conferidos_df.sort_values("contado_ciclo_em", ascending=False)
            conferidos_df["_lbl"] = conferidos_df.apply(
                lambda r: f"[{r['status_ciclo'].upper()}] {r['produto']} — {r.get('contado_ciclo_em', '')}",
                axis=1,
            )
            opts_def: dict = {"": None}
            for _, r in conferidos_df.head(30).iterrows():
                opts_def[r["_lbl"]] = r["codigo"]
            escolha_def = st.selectbox("Últimos conferidos", list(opts_def.keys()), key="cic_desfazer_sel")
            if escolha_def and st.button("Desfazer", key="cic_btn_desfazer"):
                if _desfazer_conferencia(opts_def[escolha_def], get_db, sync_db):
                    st.toast("🔄 Conferência desfeita", icon="↩️")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.caption("Nenhum produto conferido ainda.")

    st.divider()

    # ── Treemap visual (visão geral — somente leitura) ────────────────────────
    st.markdown(
        '<div style="font-size:.7rem;color:#64748b;margin-bottom:4px;">'
        '🗺️ Mapa visual — para conferir, use o filtro de categoria ou a busca acima</div>',
        unsafe_allow_html=True,
    )
    html_mapa = build_css_treemap(
        df,
        filter_cat=filtro_cat,
        avarias_map=None,
        color_mode="ciclico",
    )
    st.markdown(html_mapa, unsafe_allow_html=True)
