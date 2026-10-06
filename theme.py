"""theme.py — paleta clara minimalista do CAMDA Estoque (fonte única).

O CSS global (app_turso.py) publica estes valores como variáveis --c-* no
:root da página; todo HTML renderizado por st.markdown usa ``var(--c-*)``.

Dois lugares NÃO enxergam as variáveis do :root:
- gráficos Plotly e cores calculadas em Python: ``var()`` não vale ali, use
  os hex deste dict;
- iframes (st.iframe): documento separado — ``iframe_compat.html`` anexa
  ``ROOT_CSS`` automaticamente a todo conteúdo que usa ``var(--c-*)``.
  (Mural e Mapa 3D têm paleta clara própria escrita direto no HTML.)

Regra do destaque: o verde-limão (``accent``) é só preenchimento e sempre
com texto preto (``on_accent``) — nunca como cor de texto ou de borda fina.
"""

PALETTE = {
    # Superfícies
    "bg": "#ECECEC",          # fundo da página
    "surface": "#F8F8F8",     # cards (sem borda, raio 20px)
    "surface_2": "#FFFFFF",   # linhas de lista, campos, pílula de busca
    "line": "#E2E2E2",        # divisórias finas / grade de gráfico
    "line_2": "#D0D0D0",      # borda de campo / hover
    # Texto
    "text": "#111111",        # texto principal
    "text_2": "#444444",      # texto secundário (descrições, detalhes)
    "muted": "#6B6B6B",       # texto auxiliar legível (≥4.5:1 sobre #F8F8F8)
    "label": "#8A8A8A",       # rótulos pequenos em maiúsculas (TOTAL, OK…)
    # Destaque
    "accent": "#D7F000",      # verde-limão — só preenchimento
    "on_accent": "#111111",   # texto sobre o limão
    "ink": "#111111",         # pílulas/botões pretos
    "on_ink": "#FFFFFF",
    # Status
    "crit": "#D32F2F",        # falta, avarias
    "warn": "#E08A00",        # sobra (números grandes, preenchimentos)
    "warn_ink": "#9A5B00",    # sobra em texto pequeno (≥4.5:1 sobre branco)
    "ok": "#2E7D32",          # ok
    "info": "#3D63D8",        # repor loja
    "purple": "#7E57C2",
    "teal": "#00897B",
    # Fundos suaves de status (círculos de ícone, chips)
    "crit_soft": "#FDE7EA",   # rosa claro
    "warn_soft": "#FFEBD2",   # laranja claro
    "ok_soft": "#DDF3DF",     # verde claro
    "info_soft": "#E3E9FB",
    "purple_soft": "#EEE7F8",
}

_VAR_NAMES = {
    "bg": "--c-bg", "surface": "--c-surface", "surface_2": "--c-surface-2",
    "line": "--c-line", "line_2": "--c-line-2", "text": "--c-text",
    "text_2": "--c-text-2", "muted": "--c-muted", "label": "--c-label",
    "accent": "--c-accent", "on_accent": "--c-on-accent", "ink": "--c-ink",
    "on_ink": "--c-on-ink", "crit": "--c-crit", "warn": "--c-warn", "warn_ink": "--c-warn-ink",
    "ok": "--c-ok", "info": "--c-info", "purple": "--c-purple",
    "teal": "--c-teal", "crit_soft": "--c-crit-soft",
    "warn_soft": "--c-warn-soft", "ok_soft": "--c-ok-soft",
    "info_soft": "--c-info-soft", "purple_soft": "--c-purple-soft",
}

# Declarações prontas para colar dentro de um bloco :root { ... }
ROOT_VARS = "\n".join(f"{_VAR_NAMES[k]}: {v};" for k, v in PALETTE.items()) + """
--c-faint: #8A8A8A;
--r-card: 20px; --r-row: 12px; --r-pill: 999px;
--f-sans: 'Inter', 'IBM Plex Sans', system-ui, sans-serif;
--f-mono: 'IBM Plex Mono', ui-monospace, monospace;
"""

ROOT_CSS = ":root {\n" + ROOT_VARS + "}\n"

