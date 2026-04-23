"""Ajustes globais de layout para o app Streamlit."""

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
html, body, .stApp,
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

.camda-header {
    margin-top: -3.5rem !important;
}

/* Ajuste fino: seletor mais específico para vencer patches antigos e puxar o header ao topo. */
html body .stApp .camda-header {
    margin-top: -5rem !important;
}

div[data-testid="stElementContainer"]:has(.camda-header) {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

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

@media (max-width: 768px) {
    .camda-header {
        margin-top: -3.25rem !important;
    }

    html body .stApp .camda-header {
        margin-top: -4.5rem !important;
    }
}
</style>
"""

    def markdown_with_top_gap_fix(body, *args, **kwargs):
        if not injected["done"] and isinstance(body, str):
            injected["done"] = True
            original_markdown(top_gap_fix_css, unsafe_allow_html=True)
        return original_markdown(body, *args, **kwargs)

    st.markdown = markdown_with_top_gap_fix
    st._camda_top_gap_fix_installed = True


_install_streamlit_top_gap_fix()
