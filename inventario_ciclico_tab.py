"""Aba de Inventário Cíclico — conferência contínua com treemap visual."""
from datetime import datetime, timedelta, timezone

import streamlit as st

_BRT = timezone(timedelta(hours=-3))


# ── CRUD — Inventário Cíclico ─────────────────────────────────────────────────

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
                SUM(CASE WHEN status_ciclo = 'ok' THEN 1 ELSE 0 END) as ok,
                SUM(CASE WHEN status_ciclo = 'divergencia' THEN 1 ELSE 0 END) as div,
                SUM(CASE WHEN status_ciclo = '' OR status_ciclo IS NULL THEN 1 ELSE 0 END) as pendente
            FROM estoque_mestre
        """).fetchone()
        return {
            "total":      row[0] or 0,
            "ok":         row[1] or 0,
            "divergencia": row[2] or 0,
            "pendente":   row[3] or 0,
        }
    except Exception:
        return {"total": 0, "ok": 0, "divergencia": 0, "pendente": 0}


# ── Main tab ──────────────────────────────────────────────────────────────────

def build_inventario_ciclico_tab(get_db, _using_cloud, sync_db, build_css_treemap, sort_categorias, get_current_stock):
    df = get_current_stock()
    progresso = _get_progresso_ciclo(get_db)

    conferidos = progresso["ok"] + progresso["divergencia"]
    pct = (conferidos / max(progresso["total"], 1)) * 100

    # Stat cards
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
        <span>🟡 Aguardando</span>
        <span>🟢 Conferido OK</span>
        <span>🔴 Divergência</span>
    </div>
    """, unsafe_allow_html=True)

    # Filtro de categoria
    categorias = ["TODOS"] + sort_categorias(df["categoria"].unique().tolist())
    filtro_cat = st.selectbox(
        "Filtrar categoria",
        categorias,
        key="inv_ciclico_filtro_cat",
    )

    # Selectbox de conferência (apenas pendentes)
    pendentes_df = df[df["status_ciclo"].fillna("").eq("")].copy()
    if filtro_cat != "TODOS":
        pendentes_df = pendentes_df[pendentes_df["categoria"] == filtro_cat]

    if not pendentes_df.empty:
        pendentes_df = pendentes_df.sort_values(["categoria", "produto"])
        pendentes_df["label"] = pendentes_df.apply(
            lambda r: f"{r['produto']} — sist: {r['qtd_sistema']}", axis=1
        )
        opts: dict = {"": None}
        for _, r in pendentes_df.iterrows():
            opts[r["label"]] = r["codigo"]

        escolha = st.selectbox(
            f"🔍 Conferir produto ({len(pendentes_df)} pendentes nesta categoria)",
            options=list(opts.keys()),
            key="inv_ciclico_busca",
        )

        if escolha:
            codigo = opts[escolha]
            produto_row = df[df["codigo"] == codigo].iloc[0]

            with st.container(border=True):
                st.markdown(f"**{produto_row['produto']}**")
                st.caption(
                    f"Categoria: {produto_row['categoria']} · "
                    f"Sistema: **{produto_row['qtd_sistema']}** unidades"
                )

                col1, col2 = st.columns(2)

                if col1.button(
                    "✅ Confirmar OK",
                    use_container_width=True,
                    type="primary",
                    key="inv_ciclico_btn_ok",
                ):
                    if _marcar_ciclo_ok(codigo, get_db, sync_db):
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
                        if _marcar_ciclo_divergencia(codigo, int(qtd_real), get_db, sync_db):
                            st.toast(
                                f"⚠️ {produto_row['produto']}: divergência registrada",
                                icon="🔴",
                            )
                            st.cache_data.clear()
                            st.rerun()
    else:
        if filtro_cat == "TODOS":
            st.success("🎉 Todos os produtos conferidos neste ciclo!")
        else:
            st.info(f"✅ Nenhum produto pendente na categoria {filtro_cat}")

    # Desfazer conferência
    with st.expander("🔧 Desfazer conferência (caso tenha marcado errado)"):
        conferidos_df = df[df["status_ciclo"].isin(["ok", "divergencia"])].copy()
        if not conferidos_df.empty:
            conferidos_df = conferidos_df.sort_values("contado_ciclo_em", ascending=False)
            conferidos_df["label_desfazer"] = conferidos_df.apply(
                lambda r: (
                    f"[{r['status_ciclo'].upper()}] {r['produto']} "
                    f"— {r.get('contado_ciclo_em', '')}"
                ),
                axis=1,
            )
            opts_desfazer: dict = {"": None}
            for _, r in conferidos_df.head(30).iterrows():
                opts_desfazer[r["label_desfazer"]] = r["codigo"]

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

    # Treemap com color_mode cíclico
    html_mapa = build_css_treemap(
        df,
        filter_cat=filtro_cat,
        avarias_map=None,
        color_mode="ciclico",
    )
    st.markdown(html_mapa, unsafe_allow_html=True)
