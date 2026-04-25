"""Estilo global adicional para abas do Streamlit."""

from __future__ import annotations


def _install_camda_active_tab_style() -> None:
    try:
        import streamlit as st
    except Exception:
        return

    if getattr(st, "_camda_active_tab_style_installed", False):
        return

    original_tabs = st.tabs

    active_tab_css = """
<style id="camda-active-tab-style">
div[data-testid="stTabs"] [role="tablist"],
div[data-testid="stTabs"] div[data-baseweb="tab-list"] {
    overflow: visible !important;
}

div[data-testid="stTabs"] button[role="tab"],
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    position: relative !important;
    overflow: visible !important;
    transition: color .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease !important;
}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"],
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    color: #ecffd6 !important;
    border-color: rgba(190,255,95,.28) !important;
    background: linear-gradient(180deg, rgba(190,255,95,.075), rgba(190,255,95,.025)) !important;
    box-shadow: inset 0 0 0 1px rgba(190,255,95,.10), 0 8px 22px rgba(190,255,95,.07) !important;
}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]::after,
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]::after {
    content: "";
    position: absolute;
    left: 18%;
    right: 18%;
    bottom: -6px;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, transparent 0%, rgba(198,255,84,.92) 45%, rgba(198,255,84,.92) 55%, transparent 100%);
    box-shadow: 0 0 10px rgba(198,255,84,.42), 0 0 18px rgba(198,255,84,.18);
    pointer-events: none;
}

div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background: transparent !important;
}
</style>
"""

    def tabs_with_active_style(*args, **kwargs):
        try:
            if not st.session_state.get("_camda_active_tab_css_done", False):
                st.session_state["_camda_active_tab_css_done"] = True
                st.markdown(active_tab_css, unsafe_allow_html=True)
        except Exception:
            pass
        return original_tabs(*args, **kwargs)

    st.tabs = tabs_with_active_style
    st._camda_active_tab_style_installed = True


_install_camda_active_tab_style()
