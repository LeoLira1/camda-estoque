"""Aba de Histórico de Contagem — lista por dia das contagens realizadas."""
from datetime import datetime, timedelta, timezone, date

import streamlit as st

_NOMES_INVALIDOS_COOP = {
    "faltando", "falta", "sobra", "sobrando", "ok", "none", "nan",
    "", "sem cooperado", "sem vínculo", "sem vinculo",
}

_BRT = timezone(timedelta(hours=-3))

_CSS = """<style>
.hc-title{font-size:1.05rem;font-weight:700;color:#e0e6ed;margin-bottom:12px;}
.hc-kpi-row{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;}
.hc-kpi{flex:1;min-width:80px;background:linear-gradient(135deg,#111827,#1a2332);
         border:1px solid #1e293b;border-radius:10px;padding:8px 10px;text-align:center;}
.hc-kpi-v{font-family:'JetBrains Mono',monospace;font-size:1.1rem;font-weight:700;color:#22c55e;}
.hc-kpi-v.red{color:#ff4757;}
.hc-kpi-v.blue{color:#3b82f6;}
.hc-kpi-l{font-size:0.58rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:2px;}
.hc-row{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);
         border-radius:8px;padding:7px 12px;margin-bottom:3px;
         display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.hc-row.ok{border-left:3px solid #00d68f;}
.hc-row.div{border-left:3px solid #ff4757;}
.hc-prod{font-weight:600;font-size:0.83rem;color:#e0e6ed;flex:1;min-width:160px;}
.hc-cod{font-family:'JetBrains Mono',monospace;font-size:0.70rem;color:#3b82f6;min-width:75px;}
.hc-qtd{font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:#94a3b8;min-width:80px;text-align:right;}
.hc-delta{font-family:'JetBrains Mono',monospace;font-size:0.85rem;font-weight:700;min-width:60px;text-align:right;}
.hc-delta.ok{color:#00d68f;}
.hc-delta.neg{color:#ff4757;}
.hc-delta.pos{color:#ffa502;}
.hc-hora{font-size:0.65rem;color:#64748b;min-width:75px;text-align:right;}
.hc-badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.63rem;font-weight:700;min-width:60px;text-align:center;}
.hc-badge.ok{background:rgba(0,214,143,.12);color:#00d68f;border:1px solid rgba(0,214,143,.3);}
.hc-badge.div{background:rgba(255,71,87,.12);color:#ff4757;border:1px solid rgba(255,71,87,.3);}
.hc-empty{text-align:center;padding:40px 20px;color:#475569;font-size:0.85rem;}
.hc-section{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
             color:#64748b;margin:14px 0 6px;padding-bottom:4px;border-bottom:1px solid #1e293b;}
/* Destaque nos dias com contagem no calendário */
.hc-cal-legend{display:flex;gap:16px;font-size:0.7rem;color:#64748b;
               margin:4px 0 10px;font-family:'JetBrains Mono',monospace;}
</style>"""


def _get_divergencias_abertas_sem_cooperado(conn) -> list[dict]:
    """Retorna divergências Sobrando/Faltando sem cooperado real ainda em aberto."""
    nomes_lista = list(_NOMES_INVALIDOS_COOP)
    ph = ",".join(["?"] * len(nomes_lista))
    try:
        rows = conn.execute(f"""
            SELECT d.codigo, d.produto, d.categoria, d.delta, d.status, d.criado_em
            FROM divergencias d
            WHERE LOWER(TRIM(COALESCE(d.cooperado, ''))) IN ({ph})
            ORDER BY d.criado_em DESC
        """, nomes_lista).fetchall()
        return [
            {
                "codigo": r[0], "produto": r[1],
                "categoria": r[2] or "Sem categoria",
                "delta": r[3], "status": r[4], "criado_em": r[5],
            }
            for r in rows
        ]
    except Exception:
        return []


def _get_dias_com_contagem(conn) -> list[str]:
    """Dias com contagem: une inventario_cicli (histórico) + contagem_itens por confirmado_em."""
    dias = set()
    try:
        rows = conn.execute(
            "SELECT DISTINCT data_contagem FROM inventario_cicli"
        ).fetchall()
        for r in rows:
            dias.add(r[0])
    except Exception:
        pass
    try:
        # Dias com itens confirmados no contagem_itens, agrupados por data de confirmação
        rows = conn.execute("""
            SELECT DISTINCT date(COALESCE(NULLIF(confirmado_em,''), registrado_em))
            FROM contagem_itens
            WHERE status IN ('certa', 'divergencia')
        """).fetchall()
        for r in rows:
            if r[0]:
                dias.add(r[0])
    except Exception:
        pass
    return sorted(dias, reverse=True)


def _get_contagem_do_dia(conn, data: str) -> list[dict]:
    """
    Lê itens confirmados de contagem_itens filtrando por data de confirmação (confirmado_em).
    Complementa com inventario_cicli para itens do Inv. Cíclico do mesmo dia.
    """
    items = []
    codigos_vistos = set()

    # 1. contagem_itens — filtra pelo DIA DE CONFIRMAÇÃO
    try:
        rows = conn.execute("""
            SELECT ci.codigo, ci.produto, ci.categoria,
                   ci.qtd_estoque,
                   CASE ci.status
                       WHEN 'certa' THEN CAST(ci.qtd_estoque AS REAL)
                       ELSE CAST(COALESCE(em.qtd_fisica, ci.qtd_estoque) AS REAL)
                   END AS qtd_contada,
                   CASE ci.status
                       WHEN 'certa' THEN 0.0
                       ELSE CAST(COALESCE(em.qtd_fisica, ci.qtd_estoque) AS REAL) - CAST(ci.qtd_estoque AS REAL)
                   END AS divergencia,
                   COALESCE(NULLIF(ci.confirmado_em,''), ci.registrado_em)
            FROM contagem_itens ci
            LEFT JOIN estoque_mestre em ON em.codigo = ci.codigo
            WHERE ci.status IN ('certa', 'divergencia')
              AND date(COALESCE(NULLIF(ci.confirmado_em,''), ci.registrado_em)) = ?
            ORDER BY COALESCE(NULLIF(ci.confirmado_em,''), ci.registrado_em) DESC
        """, (data,)).fetchall()
        for r in rows:
            items.append({
                "codigo": r[0], "produto": r[1],
                "categoria": r[2] or "Sem categoria",
                "qtd_sistema": r[3], "qtd_contada": r[4],
                "divergencia": r[5], "contado_em": r[6],
            })
            codigos_vistos.add(r[0])
    except Exception:
        pass

    # 2. inventario_cicli — itens do Inv. Cíclico (sem duplicar códigos já lidos)
    try:
        rows = conn.execute("""
            SELECT produto_id, produto_nome, categoria_label,
                   qtd_sistema, qtd_contada, divergencia, contado_em
            FROM inventario_cicli
            WHERE data_contagem = ?
            ORDER BY contado_em DESC
        """, (data,)).fetchall()
        for r in rows:
            if r[0] not in codigos_vistos:
                items.append({
                    "codigo": r[0], "produto": r[1],
                    "categoria": r[2] or "Sem categoria",
                    "qtd_sistema": r[3], "qtd_contada": r[4],
                    "divergencia": r[5], "contado_em": r[6],
                })
    except Exception:
        pass

    return items


def _fmt_hora(contado_em: str) -> str:
    if not contado_em:
        return ""
    try:
        dt = datetime.strptime(contado_em, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M")
    except Exception:
        return contado_em[:5] if len(contado_em) >= 5 else contado_em


def _fmt_data_br(data_iso: str) -> str:
    try:
        d = date.fromisoformat(data_iso)
        dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        return f"{dias[d.weekday()]}, {d.strftime('%d/%m/%Y')}"
    except Exception:
        return data_iso


def build_historico_contagem_tab(get_db):
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="hc-title">📅 Histórico de Contagem</div>', unsafe_allow_html=True)

    conn = get_db()
    dias = _get_dias_com_contagem(conn)

    if not dias:
        st.markdown(
            '<div class="hc-empty">Nenhuma contagem registrada ainda.<br>'
            'Realize contagens na aba <b>🔄 Inv. Cíclico</b> para ver o histórico aqui.</div>',
            unsafe_allow_html=True,
        )
        return

    dias_set = set(dias)
    datas_disponiveis = sorted([date.fromisoformat(d) for d in dias], reverse=True)
    data_mais_recente = datas_disponiveis[0]
    data_mais_antiga  = datas_disponiveis[-1]

    # ── Seletor de data (calendário) ─────────────────────────────────────────
    col_cal, col_filtros = st.columns([1, 2])

    with col_cal:
        data_sel = st.date_input(
            "Selecione o dia",
            value=data_mais_recente,
            min_value=data_mais_antiga,
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="hc_data_cal",
        )

    dia_selecionado = data_sel.isoformat() if data_sel else dias[0]

    # Aviso se o dia selecionado não tem contagem
    sem_contagem = dia_selecionado not in dias_set

    # ── Itens do dia ─────────────────────────────────────────────────────────
    items = [] if sem_contagem else _get_contagem_do_dia(conn, dia_selecionado)

    # ── Seletor de categoria ──────────────────────────────────────────────────
    cats_disponiveis = sorted({i["categoria"] for i in items if i["categoria"]})

    with col_filtros:
        col_cat, col_status = st.columns(2)
        with col_cat:
            filtro_cat = st.selectbox(
                "Categoria",
                ["Todas"] + cats_disponiveis,
                key="hc_filtro_cat",
                disabled=not items,
            )
        with col_status:
            filtro_status = st.radio(
                "Status",
                ["Todos", "✅ OK", "⚠️ Divergência"],
                horizontal=True,
                key="hc_filtro_status",
            )

    # ── Aplica filtros ────────────────────────────────────────────────────────
    if filtro_cat != "Todas":
        items = [i for i in items if i["categoria"] == filtro_cat]

    if filtro_status == "✅ OK":
        items = [i for i in items if i["divergencia"] is not None and abs(float(i["divergencia"])) < 0.01]
    elif filtro_status == "⚠️ Divergência":
        items = [i for i in items if i["divergencia"] is not None and abs(float(i["divergencia"])) >= 0.01]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total = len(items)
    n_ok  = sum(1 for i in items if i["divergencia"] is not None and abs(float(i["divergencia"])) < 0.01)
    n_div = total - n_ok

    if sem_contagem:
        st.info(f"Nenhuma contagem registrada em {_fmt_data_br(dia_selecionado)}. Escolha outro dia no calendário.")
        # Mostra os dias disponíveis mais próximos
        proximos = [d for d in datas_disponiveis if d <= data_sel][:3]
        if proximos:
            st.caption("Dias com contagem mais próximos: " + " · ".join(_fmt_data_br(d.isoformat()) for d in proximos))
        return

    st.markdown(f"""
    <div class="hc-kpi-row">
        <div class="hc-kpi"><div class="hc-kpi-v blue">{total}</div><div class="hc-kpi-l">Contados</div></div>
        <div class="hc-kpi"><div class="hc-kpi-v">{n_ok}</div><div class="hc-kpi-l">OK</div></div>
        <div class="hc-kpi"><div class="hc-kpi-v red">{n_div}</div><div class="hc-kpi-l">Divergência</div></div>
    </div>""", unsafe_allow_html=True)

    if not items:
        st.markdown('<div class="hc-empty">Nenhum item para os filtros selecionados.</div>', unsafe_allow_html=True)
        return

    # ── Lista de produtos ─────────────────────────────────────────────────────
    items_div = [i for i in items if i["divergencia"] is not None and abs(float(i["divergencia"])) >= 0.01]
    items_ok  = [i for i in items if i not in items_div]

    def _render_section(section_items, label):
        if not section_items:
            return
        if label:
            st.markdown(f'<div class="hc-section">{label}</div>', unsafe_allow_html=True)
        rows_html = ""
        for item in section_items:
            div = item["divergencia"]
            is_ok = div is not None and abs(float(div)) < 0.01
            row_cls   = "ok" if is_ok else "div"
            badge_cls = "ok" if is_ok else "div"
            badge_txt = "OK" if is_ok else "Divergência"

            qtd_s = f"{item['qtd_sistema']:.0f}" if item["qtd_sistema"] is not None else "—"
            qtd_c = f"{item['qtd_contada']:.0f}" if item["qtd_contada"] is not None else "—"
            hora  = _fmt_hora(item["contado_em"])
            cat   = item["categoria"]

            if div is None:
                delta_html = '<span class="hc-delta">—</span>'
            elif is_ok:
                delta_html = '<span class="hc-delta ok">±0</span>'
            else:
                dv = float(div)
                delta_cls = "neg" if dv < 0 else "pos"
                delta_html = f'<span class="hc-delta {delta_cls}">{dv:+.0f}</span>'

            rows_html += f"""
            <div class="hc-row {row_cls}">
                <span class="hc-badge {badge_cls}">{badge_txt}</span>
                <span class="hc-prod">{item['produto'] or item['codigo']}</span>
                <span class="hc-cod">{item['codigo']}</span>
                <span style="font-size:0.65rem;color:#475569;flex:0 0 auto;">{cat}</span>
                <span class="hc-qtd" title="Sistema / Contado">Sis:{qtd_s} · Cnt:{qtd_c}</span>
                {delta_html}
                <span class="hc-hora">{hora}</span>
            </div>"""
        st.markdown(rows_html, unsafe_allow_html=True)

    if filtro_status == "Todos":
        _render_section(items_div, f"⚠️ Divergências ({len(items_div)})")
        _render_section(items_ok,  f"✅ Conferidos OK ({len(items_ok)})")
    else:
        _render_section(items, label="")

    # ── Divergências em aberto: Sobrando / Faltando (sem cooperado) ──────────
    divs_abertas = _get_divergencias_abertas_sem_cooperado(conn)
    if divs_abertas:
        st.markdown(
            '<div class="hc-section">📋 Divergências em aberto — Sobrando / Faltando</div>',
            unsafe_allow_html=True,
        )
        st.caption("Itens com divergência sem cooperado vinculado. Somem desta lista ao serem contados como certos.")
        rows_html = ""
        for item in divs_abertas:
            delta = item["delta"]
            is_sobra = item["status"] == "sobra"
            badge_txt = "Sobrando" if is_sobra else "Faltando"
            badge_cls = "pos" if is_sobra else "neg"
            delta_cls  = "pos" if is_sobra else "neg"
            delta_html = f'<span class="hc-delta {delta_cls}">{delta:+d}</span>'
            try:
                dt = datetime.strptime(item["criado_em"][:16], "%Y-%m-%d %H:%M")
                data_fmt = dt.strftime("%d/%m %H:%M")
            except Exception:
                data_fmt = (item["criado_em"] or "")[:10]
            rows_html += f"""
            <div class="hc-row div">
                <span class="hc-badge div">{badge_txt}</span>
                <span class="hc-prod">{item['produto'] or item['codigo']}</span>
                <span class="hc-cod">{item['codigo']}</span>
                <span style="font-size:0.65rem;color:#475569;flex:0 0 auto;">{item['categoria']}</span>
                {delta_html}
                <span class="hc-hora">{data_fmt}</span>
            </div>"""
        st.markdown(rows_html, unsafe_allow_html=True)
