"""Aba de Inventário Cíclico — conferência contínua com cards clicáveis."""
import re as _re
from datetime import datetime, timedelta, timezone

import streamlit as st

_BRT = timezone(timedelta(hours=-3))
_COLS = 5  # cards por linha na grade

# Categorias agro-químicas ficam no FIM; tudo mais (loja/ferramentas/outros) vem PRIMEIRO
_CICLO_LAST = frozenset({
    "HERBICIDAS", "HERBICIDA",
    "FUNGICIDAS", "FUNGICIDA",
    "INSETICIDAS", "INSETICIDA",
    "NEMATICIDAS", "NEMATICIDA",
    "ADUBOS", "ADUBO",
    "ADUBOS FOLIARES", "ADUBOS FOLIARES E QUÍMICOS", "ADUBOS QUÍMICOS",
    "ADUBOS CORRETIVOS", "ADUBOS ORGANICOS", "ADUBOS ORGÂNICOS",
    "ADUBO FOLIAR", "ADUBO ORGANICO", "ADUBO ORGÂNICO",
    "FERTILIZANTES", "FERTILIZANTE",
    "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO", "ADJUVANTE",
    "ÓLEOS", "ÓLEOS MINERAIS E VEGETAIS", "OLEOS", "OLEOS MINERAIS E VEGETAIS",
    "SEMENTES", "SEMENTE",
    "MATURADORES", "MATURADOR",
    "REGULADORES DE CRESCIMENTO", "REGULADOR DE CRESCIMENTO",
    "DEFENSIVOS", "DEFENSIVOS AGRICOLAS", "DEFENSIVOS AGRÍCOLAS",
    "BIOLOGICOS E INOCULANTES", "BIOLÓGICOS E INOCULANTES",
    "INOCULANTES", "INOCULANTES P/ SILAGEM",
    "BIOLOGICOS", "BIOLÓGICOS",
    "SUPLEMENTO MINERAL", "SUPLEMENTOS MINERAIS",
    "RAÇÃO", "RACAO", "RACOES", "RAÇÕES",
})

# 4 CSS rules estáticos (não crescem com o nº de produtos) — IDs com prefixo de status
_CSS_CARDS = """<style>
[data-testid="stColumn"]:has([id^="cic-pend-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-pend-"]) [data-testid="stButton"] button {
    background:rgba(255,165,2,0.20)!important;
    border:none!important; border-left:3px solid #ffa502!important;
    border-radius:10px!important; padding:10px 8px!important;
    text-align:left!important; min-height:68px!important;
    width:100%!important; color:#e8eaf0!important;
    font-family:'JetBrains Mono',monospace!important;
    font-size:0.75rem!important; line-height:1.35!important;
    white-space:normal!important; word-break:break-word!important;
    transition:opacity .12s,transform .1s!important;
}
[data-testid="stColumn"]:has([id^="cic-ok-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-ok-"]) [data-testid="stButton"] button {
    background:rgba(0,214,143,0.72)!important;
    border:2px solid #00d68f!important;
    border-radius:10px!important; padding:10px 8px!important;
    text-align:left!important; min-height:68px!important;
    width:100%!important; color:#ffffff!important;
    font-family:'JetBrains Mono',monospace!important;
    font-size:0.75rem!important; line-height:1.35!important;
    white-space:normal!important; word-break:break-word!important;
    transition:opacity .12s,transform .1s!important;
}
[data-testid="stColumn"]:has([id^="cic-div-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-div-"]) [data-testid="stButton"] button {
    background:rgba(255,71,87,0.72)!important;
    border:2px solid #ff4757!important;
    border-radius:10px!important; padding:10px 8px!important;
    text-align:left!important; min-height:68px!important;
    width:100%!important; color:#ffffff!important;
    font-family:'JetBrains Mono',monospace!important;
    font-size:0.75rem!important; line-height:1.35!important;
    white-space:normal!important; word-break:break-word!important;
    transition:opacity .12s,transform .1s!important;
}
/* Anel branco no card selecionado */
[data-testid="stColumn"]:has([id^="cic-sel-"]) [data-testid="stButton"] button,
[data-testid="stVerticalBlock"]:has([id^="cic-sel-"]) [data-testid="stButton"] button {
    outline:2px solid #ffffff!important; outline-offset:2px!important;
}
/* Hover para qualquer card cíclico */
[data-testid="stColumn"]:has([id^="cic-pend-"]) [data-testid="stButton"] button:hover,
[data-testid="stColumn"]:has([id^="cic-ok-"]) [data-testid="stButton"] button:hover,
[data-testid="stColumn"]:has([id^="cic-div-"]) [data-testid="stButton"] button:hover {
    opacity:.82!important; transform:scale(1.025)!important;
}
</style>"""

# JS: injeta CSS no <head> do pai + oculta controles via MutationObserver
_JS_HIDE_CONFERENCIA = """
<script>
(function () {
    var p = window.parent;
    var pd = p.document;
    var _t;

    /* CSS persistente injetado no <head> — sobrevive a re-renders do Streamlit */
    if (!pd.getElementById('_ciclo_hide_css')) {
        var s = pd.createElement('style');
        s.id = '_ciclo_hide_css';
        var RULE = 'display:none!important;height:0!important;min-height:0!important;' +
                   'margin:0!important;padding:0!important;overflow:hidden!important;';
        s.textContent =
            /* campo de busca — pelo placeholder único */
            '[data-testid="element-container"]:has(input[placeholder="ciclo-search-input"]){' + RULE + '}' +
            'input[placeholder="ciclo-search-input"]{' + RULE + '}';
        (pd.head || pd.documentElement).appendChild(s);
    }

    var Z = 'display:none!important;height:0!important;min-height:0!important;' +
            'margin:0!important;padding:0!important;overflow:hidden!important;';

    function collapse(el) {
        /* sobe até o element-container do Streamlit e colapsa ele + o widget */
        var c = el.closest('[data-testid="element-container"]') ||
                el.closest('.stElementContainer') ||
                el.parentElement;
        if (c) c.setAttribute('style', Z);
        el.setAttribute('style', Z);
    }

    function run() {
        /* Selectbox "Categoria para conferir" */
        pd.querySelectorAll('[data-testid="stSelectbox"]').forEach(function (el) {
            var lbl = el.querySelector('label');
            if (lbl && lbl.textContent.trim() === 'Categoria para conferir') collapse(el);
        });
        /* Captions de instrução */
        pd.querySelectorAll('[data-testid="stCaptionContainer"]').forEach(function (el) {
            var t = el.textContent || '';
            if (t.includes('Selecione uma categoria') || t.includes('Clique em qualquer card')) collapse(el);
        });
        /* Expander "Desfazer conferência" */
        pd.querySelectorAll('[data-testid="stExpander"]').forEach(function (el) {
            if ((el.textContent || '').includes('Desfazer conferência')) collapse(el);
        });
        /* Campo de busca (backup ao CSS) */
        pd.querySelectorAll('input[placeholder="ciclo-search-input"]').forEach(function (inp) {
            collapse(inp);
        });
        /* Divisor — somente dentro do painel que contém o treemap cíclico */
        var inp = pd.querySelector('input[placeholder="ciclo-search-input"]');
        if (inp) {
            var panel = inp.closest('[data-testid="stTabPanel"]') ||
                        inp.closest('[data-testid="stVerticalBlock"]');
            if (panel) {
                panel.querySelectorAll('[data-testid="stDivider"]').forEach(function (el) {
                    collapse(el);
                });
            }
        }
    }

    run();
    new p.MutationObserver(function () {
        clearTimeout(_t);
        _t = setTimeout(run, 50);
    }).observe(pd.body, { childList: true, subtree: true });
})();
</script>
"""

# JS injetado no iframe para tornar os cards do treemap clicáveis
_JS_TREEMAP_CLICK = """
<script>
(function () {
    var PLACEHOLDER = "ciclo-search-input";
    var p = window.parent;
    var pd = p.document;
    var _timer;

    function findInput() {
        return pd.querySelector('input[placeholder="' + PLACEHOLDER + '"]');
    }

    function setReactValue(inp, val) {
        try {
            var setter = Object.getOwnPropertyDescriptor(
                p.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(inp, val);
            inp.dispatchEvent(new Event('input', { bubbles: true }));
        } catch (e) { /* cross-origin blocked — no-op */ }
    }

    function attachClicks() {
        var tiles = pd.querySelectorAll('.tm-tile[data-codigo]:not([data-ctx="mapa"])');
        if (!tiles.length) { setTimeout(attachClicks, 600); return; }
        tiles.forEach(function (t) {
            if (t._cicloReady) return;
            t._cicloReady = true;
            t.style.cursor = 'pointer';
            t.addEventListener('click', function (e) {
                e.stopPropagation();
                var cod = this.getAttribute('data-codigo');
                if (!cod) return;
                var inp = findInput();
                if (inp) setReactValue(inp, cod);
            });
        });
    }

    attachClicks();

    // Re-attacha após re-renders do Streamlit
    new p.MutationObserver(function () {
        clearTimeout(_timer);
        _timer = setTimeout(attachClicks, 400);
    }).observe(pd.body, { childList: true, subtree: true });
})();
</script>
"""

# Placeholder único que o JS usa para localizar o input
_SEARCH_PLACEHOLDER = "ciclo-search-input"


def _sort_ciclo(cats: list) -> list:
    first = sorted(c for c in cats if c.upper() not in _CICLO_LAST)
    last  = sorted(c for c in cats if c.upper() in _CICLO_LAST)
    return first + last


def _safe(codigo: str) -> str:
    return _re.sub(r"[^a-zA-Z0-9]", "-", str(codigo))


def _status_prefix(status_c: str) -> str:
    if status_c == "ok":
        return "cic-ok-"
    if status_c == "divergencia":
        return "cic-div-"
    return "cic-pend-"


# ── Callback do input de busca ──────────────────────────────────────────────────

def _on_busca_treemap():
    """Chamado ao alterar o input de busca (digitação ou clique JS no treemap)."""
    val = st.session_state.get("ciclo_busca_treemap", "").strip()
    if val:
        st.session_state["_ciclo_code_clicked"] = val
    # Limpa input para que o mesmo código possa ser clicado novamente
    st.session_state["ciclo_busca_treemap"] = ""


# ── CRUD ──────────────────────────────────────────────────────────────────────

def _ensure_inventario_cicli(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventario_cicli (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            data_contagem   TEXT NOT NULL,
            produto_id      TEXT NOT NULL,
            produto_nome    TEXT NOT NULL DEFAULT '',
            categoria_id    TEXT NOT NULL DEFAULT '',
            categoria_label TEXT NOT NULL DEFAULT '',
            categoria_cor   TEXT NOT NULL DEFAULT '#888888',
            qtd_sistema     REAL NOT NULL DEFAULT 0,
            qtd_contada     REAL,
            divergencia     REAL,
            score           REAL NOT NULL DEFAULT 0,
            contado_em      TEXT DEFAULT '',
            observacao      TEXT DEFAULT ''
        )
    """)


def _upsert_inventario_cicli(
    conn,
    data_contagem: str,
    produto_id: str,
    produto_nome: str,
    categoria: str,
    qtd_sistema: float,
    qtd_contada: float,
    contado_em: str,
    observacao: str = "",
) -> None:
    _ensure_inventario_cicli(conn)
    divergencia = float(qtd_contada) - float(qtd_sistema)
    existing = conn.execute(
        "SELECT id FROM inventario_cicli WHERE data_contagem = ? AND produto_id = ?",
        (data_contagem, produto_id),
    ).fetchone()
    if existing:
        conn.execute("""
            UPDATE inventario_cicli
            SET qtd_contada=?, divergencia=?, contado_em=?, observacao=?,
                produto_nome=?, qtd_sistema=?
            WHERE data_contagem=? AND produto_id=?
        """, (qtd_contada, divergencia, contado_em, observacao,
              produto_nome, qtd_sistema, data_contagem, produto_id))
    else:
        conn.execute("""
            INSERT INTO inventario_cicli
                (data_contagem, produto_id, produto_nome, categoria_id, categoria_label,
                 categoria_cor, qtd_sistema, qtd_contada, divergencia, contado_em, observacao)
            VALUES (?, ?, ?, ?, ?, '#888888', ?, ?, ?, ?, ?)
        """, (data_contagem, produto_id, produto_nome, categoria, categoria,
              qtd_sistema, qtd_contada, divergencia, contado_em, observacao))


def _marcar_ciclo_ok(codigo: str, get_db, sync_db) -> bool:
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute(
            "SELECT qtd_sistema, produto, categoria FROM estoque_mestre WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        if not row:
            return False
        qtd_sistema, produto_nome, categoria = row[0], row[1], row[2]
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo='ok', qtd_contada_ciclo=?, qtd_sistema_na_contagem=?, contado_ciclo_em=?
            WHERE codigo=?
        """, (qtd_sistema, qtd_sistema, now, codigo))
        data_hoje = datetime.now(tz=_BRT).strftime("%Y-%m-%d")
        _upsert_inventario_cicli(
            conn, data_hoje, codigo, produto_nome, categoria,
            qtd_sistema, qtd_sistema, now,
        )
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
            "SELECT qtd_sistema, produto, categoria FROM estoque_mestre WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        if not row:
            return False
        qtd_sistema, produto_nome, categoria = row[0], row[1], row[2]
        conn.execute("""
            UPDATE estoque_mestre
            SET status_ciclo='divergencia', qtd_contada_ciclo=?, qtd_sistema_na_contagem=?, contado_ciclo_em=?
            WHERE codigo=?
        """, (qtd_real, qtd_sistema, now, codigo))
        data_hoje = datetime.now(tz=_BRT).strftime("%Y-%m-%d")
        _upsert_inventario_cicli(
            conn, data_hoje, codigo, produto_nome, categoria,
            qtd_sistema, float(qtd_real), now,
        )
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
        data_hoje = datetime.now(tz=_BRT).strftime("%Y-%m-%d")
        try:
            conn.execute(
                "DELETE FROM inventario_cicli WHERE data_contagem=? AND produto_id=?",
                (data_hoje, codigo),
            )
        except Exception:
            pass
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


# ── Modal de conferência ──────────────────────────────────────────────────────

@st.dialog("Conferência de Estoque", width="small")
def _dialog_conferencia(produto_row, get_db, sync_db):
    """Modal para confirmar quantidade OK ou registrar divergência."""
    sel_codigo = str(produto_row["codigo"])
    qtd_sistema = int(produto_row["qtd_sistema"])

    st.markdown(f"**{produto_row['produto']}**")
    st.caption(f"Categoria: {produto_row['categoria']} · Código: {sel_codigo}")
    st.divider()

    col_lbl, col_val = st.columns([3, 1])
    col_lbl.markdown("Quantidade no sistema")
    col_val.markdown(f"**{qtd_sistema}**")

    qtd_real = st.number_input(
        "Quantidade física contada",
        min_value=0,
        value=qtd_sistema,
        key="cic_qtd_real",
    )

    diferenca = int(qtd_real) - qtd_sistema
    if diferenca == 0:
        st.markdown(
            "<span style='color:#00d68f;font-size:0.85rem'>✓ Sem diferença</span>",
            unsafe_allow_html=True,
        )
    else:
        cor = "#ff4757" if diferenca < 0 else "#ffa502"
        st.markdown(
            f"<span style='color:{cor};font-size:0.85rem'>Diferença: {diferenca:+d} unidades</span>",
            unsafe_allow_html=True,
        )

    st.divider()
    col1, col2 = st.columns(2)

    if col1.button("✅ Quantidade OK", use_container_width=True, type="primary", key="cic_dialog_ok"):
        if _marcar_ciclo_ok(sel_codigo, get_db, sync_db):
            st.session_state.pop("ciclo_sel", None)
            st.toast(f"✅ {produto_row['produto']} confirmado OK", icon="🟢")
            st.session_state["_ciclo_cache_clear_needed"] = True
            st.rerun()

    if col2.button("⚠️ Divergência", use_container_width=True, key="cic_dialog_div"):
        if _marcar_ciclo_divergencia(sel_codigo, int(qtd_real), get_db, sync_db):
            st.session_state.pop("ciclo_sel", None)
            st.toast(f"⚠️ {produto_row['produto']}: divergência registrada", icon="🔴")
            st.session_state["_ciclo_cache_clear_needed"] = True
            st.rerun()


# ── Main tab ──────────────────────────────────────────────────────────────────

def build_inventario_ciclico_tab(
    get_db, _using_cloud, sync_db,
    build_css_treemap, sort_categorias, get_current_stock,
    short_name=None,
    get_divergencias=None,
    get_historico_divergencias=None,
):
    if short_name is None:
        short_name = lambda x: x  # noqa: E731

    df = get_current_stock()
    progresso = _get_progresso_ciclo(get_db)

    # ── Processa clique no treemap (via JS → input → callback) ───────────────
    # O callback _on_busca_treemap roda ANTES do corpo do script e seta esta chave.
    # Usamos pop() para garantir comportamento one-shot: ao fechar o modal com X,
    # a chave não existe mais e o modal não reabre.
    _clicked = st.session_state.pop("_ciclo_code_clicked", None)
    if _clicked:
        _m = df[df["codigo"].astype(str) == str(_clicked).strip()]
        if not _m.empty:
            st.session_state["ciclo_sel"] = str(_m.iloc[0]["codigo"])
            st.session_state["ciclo_dialog_open"] = True
        else:
            st.toast(f"⚠️ Código '{_clicked}' não encontrado.", icon="⚠️")

    # ── Drena flag de clear de caches setado pelo dialog ────────────────────
    if st.session_state.pop("_ciclo_cache_clear_needed", False):
        get_current_stock.clear()
        if get_divergencias is not None:
            get_divergencias.clear()
        if get_historico_divergencias is not None:
            get_historico_divergencias.clear()

    # ── Abre modal (one-shot: pop antes de chamar evita reabrir após X) ───────
    if st.session_state.pop("ciclo_dialog_open", False):
        _sc = st.session_state.get("ciclo_sel")
        if _sc:
            _sr = df[df["codigo"].astype(str) == str(_sc)]
            if not _sr.empty:
                _dialog_conferencia(_sr.iloc[0], get_db, sync_db)

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

    # ── Grade interativa (apenas quando categoria selecionada) ────────────────
    sel_codigo = st.session_state.get("ciclo_sel")

    if filtro_cat == "TODOS":
        st.caption("Selecione uma categoria acima para conferir produtos clicando nos cards, ou clique diretamente no mapa abaixo.")
    else:
        cat_df = df[df["categoria"] == filtro_cat].sort_values("produto").reset_index(drop=True)

        if cat_df.empty:
            st.info(f"Nenhum produto na categoria {filtro_cat}.")
        else:
            # Se produto selecionado não pertence a esta categoria, limpa seleção
            if sel_codigo and sel_codigo not in set(cat_df["codigo"].astype(str)):
                st.session_state.pop("ciclo_sel", None)
                sel_codigo = None

            # CSS estático (4 regras) — injetado 1x por categoria
            st.markdown(_CSS_CARDS, unsafe_allow_html=True)

            for row_start in range(0, len(cat_df), _COLS):
                chunk = cat_df.iloc[row_start : row_start + _COLS]
                cols = st.columns(_COLS)

                for i, (_, prod) in enumerate(chunk.iterrows()):
                    status_c = str(prod.get("status_ciclo", "") or "")
                    prefix = _status_prefix(status_c)
                    safe = _safe(str(prod["codigo"]))
                    is_sel = sel_codigo == str(prod["codigo"])
                    label = f"{prod['codigo']}\n{prod['qtd_sistema']}"

                    with cols[i]:
                        marker_html = f'<div id="{prefix}{safe}" style="display:none"></div>'
                        if is_sel:
                            marker_html += f'<div id="cic-sel-{safe}" style="display:none"></div>'
                        st.markdown(marker_html, unsafe_allow_html=True)

                        if st.button(label, key=f"cic_{prod['codigo']}"):
                            st.session_state["ciclo_sel"] = str(prod["codigo"])
                            st.session_state["ciclo_dialog_open"] = True
                            st.rerun()

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
                    st.session_state["_ciclo_cache_clear_needed"] = True
                    st.rerun()
        else:
            st.caption("Nenhum produto conferido ainda.")

    st.divider()

    # ── Treemap visual — cards clicáveis ──────────────────────────────────────

    # Highlight do card selecionado no treemap
    sel_codigo = st.session_state.get("ciclo_sel")
    highlight_css = ""
    if sel_codigo:
        highlight_css = (
            f'<style>.tm-tile[data-codigo="{sel_codigo}"]'
            f'{{outline:3px solid rgba(255,255,255,0.85)!important;'
            f'outline-offset:3px!important;}}</style>'
        )
    # Cursor pointer em todos os cards do treemap
    highlight_css += "<style>.tm-tile{cursor:pointer!important;}</style>"
    st.markdown(highlight_css, unsafe_allow_html=True)

    st.caption("👆 Clique em qualquer card do mapa para conferir, ou digite o código:")
    st.text_input(
        "Busca",
        key="ciclo_busca_treemap",
        placeholder=_SEARCH_PLACEHOLDER,
        on_change=_on_busca_treemap,
        label_visibility="collapsed",
    )

    html_mapa = build_css_treemap(
        df,
        filter_cat=filtro_cat,
        avarias_map=None,
        color_mode="ciclico",
        sort_fn=_sort_ciclo,
    )
    st.markdown(html_mapa, unsafe_allow_html=True)

    # JS que faz os cards do treemap dispararem o input de busca ao serem clicados
    st.components.v1.html(_JS_TREEMAP_CLICK, height=0)
    # JS que oculta visualmente os controles de conferência
    st.components.v1.html(_JS_HIDE_CONFERENCIA, height=0)
