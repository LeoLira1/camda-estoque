"""Ajustes globais de layout para o app Streamlit.

Este módulo é carregado automaticamente pelo Python quando está no PYTHONPATH.
Ele injeta um pequeno CSS extra no primeiro st.markdown do app para remover
wrappers invisíveis que o Streamlit pode deixar acima do header customizado.
"""

from __future__ import annotations


def _install_streamlit_top_gap_fix() -> None:
    try:
        import streamlit as st
    except Exception:
        return

    if getattr(st, "_camda_top_gap_fix_installed", False):
        return

    original_markdown = st.markdown
    injected = {"done": False}

    top_gap_fix_css = """
<style id="camda-top-gap-fix">
/* Remove espaço fantasma acima do header CAMDA em versões recentes do Streamlit */
html, body, .stApp {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

section[data-testid="stMain"],
[data-testid="stMain"],
div[data-testid="stMainBlockContainer"],
div[data-testid="stAppViewBlockContainer"],
.block-container {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

.block-container > div:first-child,
div[data-testid="stVerticalBlock"] > div:first-child,
div[data-testid="stElementContainer"]:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* Esconde wrappers vazios ou wrappers usados apenas para carregar <style>. */
div[data-testid="stMarkdownContainer"]:empty,
div[data-testid="stElementContainer"]:has(style),
div[data-testid="stElementContainer"]:has(> div[data-testid="stMarkdownContainer"] style) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* Quando o header aparece, força o wrapper dele a encostar no topo do app. */
div[data-testid="stElementContainer"]:has(.camda-header) {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

@media (max-width: 768px) {
    .block-container {
        padding-top: 0 !important;
    }
}
</style>
"""

    def markdown_with_top_gap_fix(body, *args, **kwargs):
        if not injected["done"] and isinstance(body, str):
            injected["done"] = True
            body = top_gap_fix_css + "\n" + body
        return original_markdown(body, *args, **kwargs)

    st.markdown = markdown_with_top_gap_fix
    st._camda_top_gap_fix_installed = True


_install_streamlit_top_gap_fix()
