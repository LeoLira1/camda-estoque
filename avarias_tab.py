"""
CAMDA Estoque Mestre — Aba Avarias
Grid de cards com botões nativos Streamlit (seleção e exclusão funcionais)
"""

import streamlit as st
from datetime import datetime, date


def _card_html(produto: str, tempo_label: str, cor_borda: str,
               cor_status_bg: str, cor_status_txt: str, cor_status_border: str,
               n_fotos: int, selected: bool) -> str:
    ring = "box-shadow:0 0 0 2px #60a5fa;" if selected else ""
    cam = (
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.5">'
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<circle cx="8.5" cy="8.5" r="1.5"/>'
        '<path d="m21 15-5-5L5 21"/></svg>'
    )
    if n_fotos > 0:
        thumbs = "".join(
            f'<div style="flex:1;aspect-ratio:1/1;max-height:34px;background:#1a1d27;'
            f'border-radius:4px;border:0.5px solid #2a2a3a;display:flex;'
            f'flex-direction:column;align-items:center;justify-content:center;'
            f'font-size:8px;color:#555;gap:1px;">{cam}<span>{i+1}</span></div>'
            for i in range(min(n_fotos, 3))
        )
    else:
        thumbs = (
            '<div style="flex:1;display:flex;align-items:center;'
            'justify-content:center;font-size:9px;color:#2a2a3a;">sem fotos</div>'
        )

    return f"""
    <div style="
        background:#0e1117;
        border-radius:10px 10px 0 0;
        border:0.5px solid #2a2a3a;
        border-top:2.5px solid {cor_borda};
        display:flex;flex-direction:column;
        padding:9px 10px 0;
        min-height:110px;
        {ring}
    ">
      <div style="display:flex;align-items:center;gap:5px;margin-bottom:5px;">
        <span style="
          display:inline-flex;align-items:center;gap:3px;
          font-size:9px;font-weight:600;padding:2px 6px;
          border-radius:99px;border:0.5px solid {cor_status_border};
          background:{cor_status_bg};color:{cor_status_txt};
        ">&#9888; ABERTA</span>
        <span style="font-size:9px;color:#555;">{tempo_label}</span>
      </div>
      <div style="
        font-size:11px;font-weight:600;color:#ddd;line-height:1.35;
        flex:1;overflow:hidden;display:-webkit-box;
        -webkit-line-clamp:3;-webkit-box-orient:vertical;
        margin-bottom:6px;
      ">{produto}</div>
      <div style="display:flex;gap:4px;padding-bottom:8px;">{thumbs}</div>
    </div>
    """


def render_avarias_cards(df_avarias, deletar_fn=None):
    """
    Renderiza avarias abertas em grid de cards com botões nativos.

    Colunas esperadas em df_avarias:
        - id, produto, status, data_registro (ou registrado_em), fotos

    deletar_fn: callable(av_id) para executar a exclusão.
                Se None, o botão ✕ não aparece.

    Seleção via st.session_state["av_sel"] (int | None).
    """

    hoje = date.today()

    if hasattr(df_avarias, "to_dict"):
        todos = df_avarias.to_dict("records")
    else:
        todos = list(df_avarias)

    def _is_aberta(r):
        return str(r.get("status", "")).lower() in ("aberta", "aberto", "open")

    registros = [r for r in todos if _is_aberta(r)]
    total = len(registros)

    st.markdown(
        f"<p style='font-size:12px;color:#aaa;margin-bottom:10px;'>"
        f"Avarias abertas &nbsp;"
        f"<span style='color:#e24b4a;font-weight:600;'>{total}</span></p>",
        unsafe_allow_html=True,
    )

    if total == 0:
        st.info("Nenhuma avaria aberta no momento.")
        return

    _sel = st.session_state.get("av_sel")

    N = 4
    for row_start in range(0, total, N):
        chunk = registros[row_start: row_start + N]
        cols = st.columns(N)

        for col_i, r in enumerate(chunk):
            av_id = int(r.get("id", 0))
            data_reg = r.get("data_registro") or r.get("registrado_em")

            if isinstance(data_reg, str):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        data_reg = datetime.strptime(data_reg, fmt).date()
                        break
                    except ValueError:
                        pass
                else:
                    data_reg = hoje
            elif isinstance(data_reg, datetime):
                data_reg = data_reg.date()

            dias = (hoje - data_reg).days if isinstance(data_reg, date) else 0

            if dias <= 7:
                tempo_label = "hoje" if dias == 0 else f"{dias}d atrás"
                cor_borda, cor_bg, cor_txt, cor_border = "#e24b4a", "#FCEBEB", "#A32D2D", "#F09595"
            elif dias <= 20:
                tempo_label = f"{dias}d atrás"
                cor_borda, cor_bg, cor_txt, cor_border = "#EF9F27", "#FAEEDA", "#854F0B", "#FAC775"
            else:
                tempo_label = f"{dias}d atrás"
                cor_borda, cor_bg, cor_txt, cor_border = "#BA7517", "#FAEEDA", "#854F0B", "#FAC775"

            fotos = r.get("fotos", [])
            n_fotos = len(fotos) if isinstance(fotos, (list, tuple)) else (1 if fotos else 0)
            selected = av_id == _sel

            with cols[col_i]:
                st.markdown(
                    _card_html(r.get("produto", "—"), tempo_label,
                               cor_borda, cor_bg, cor_txt, cor_border,
                               n_fotos, selected),
                    unsafe_allow_html=True,
                )
                # Botões nativos alinhados com o card
                _b1, _b2 = st.columns([4, 1])
                with _b1:
                    if st.button(
                        "Ver detalhes" if not selected else "✓ Selecionado",
                        key=f"av_open_{av_id}",
                        use_container_width=True,
                        type="primary" if selected else "secondary",
                    ):
                        if selected:
                            st.session_state.pop("av_sel", None)
                        else:
                            st.session_state["av_sel"] = av_id
                        st.rerun()
                with _b2:
                    if deletar_fn and st.button(
                        "✕", key=f"av_xbtn_{av_id}",
                        use_container_width=True,
                        help="Excluir avaria",
                    ):
                        st.session_state[f"av_del_confirm_{av_id}"] = True
                        st.rerun()

                if st.session_state.get(f"av_del_confirm_{av_id}"):
                    st.warning(f"Excluir **{r.get('produto','?')}**?")
                    _ok, _cancel = st.columns(2)
                    with _ok:
                        if st.button("Confirmar", key=f"av_del_ok_{av_id}",
                                     type="primary", use_container_width=True):
                            deletar_fn(av_id)
                            st.session_state.pop(f"av_del_confirm_{av_id}", None)
                            if st.session_state.get("av_sel") == av_id:
                                st.session_state.pop("av_sel", None)
                            st.rerun()
                    with _cancel:
                        if st.button("Cancelar", key=f"av_del_cancel_{av_id}",
                                     use_container_width=True):
                            st.session_state.pop(f"av_del_confirm_{av_id}", None)
                            st.rerun()

        # Preenche colunas vazias da última linha
        for col_i in range(len(chunk), N):
            with cols[col_i]:
                st.markdown(
                    "<div style='border:0.5px dashed #1a1a2a;border-radius:10px;"
                    "min-height:110px;margin-bottom:4px;'></div>",
                    unsafe_allow_html=True,
                )
