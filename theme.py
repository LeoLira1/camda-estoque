"""theme.py — paleta escura minimalista do CAMDA Estoque (fonte única).

O CSS global (app_turso.py) publica estes valores como variáveis --c-* no
:root da página; todo HTML renderizado por st.markdown usa ``var(--c-*)``.

Dois lugares NÃO enxergam as variáveis do :root:
- gráficos Plotly e cores calculadas em Python: ``var()`` não vale ali, use
  os hex deste dict;
- iframes (st.iframe): documento separado — ``iframe_compat.html`` anexa
  ``ROOT_CSS`` automaticamente a todo conteúdo que usa ``var(--c-*)``.
  (Mural e Mapa 3D têm paleta escura própria escrita direto no HTML.)

Regra do destaque: o verde-limão (``accent``) é só preenchimento e sempre
com texto preto (``on_accent``) — nunca como cor de texto ou de borda fina.
"""

PALETTE = {
    # Superfícies
    "bg": "#111214",          # fundo da página
    "surface": "#1C1D21",     # cards (sem borda, raio 20px), pílula de busca
    "surface_2": "#24262B",   # linhas de lista (falta/sobra), campos
    "line": "#2E3036",        # divisórias finas / grade de gráfico
    "line_2": "#3A3C43",      # borda de campo / hover
    # Texto
    "text": "#F2F2F2",        # texto principal
    "text_2": "#C8C9CC",      # texto secundário (descrições, abas inativas)
    "muted": "#A3A5AB",       # texto auxiliar legível (≥6:1 sobre #1C1D21)
    "label": "#8E9096",       # rótulos pequenos em maiúsculas (TOTAL, OK…)
    # Destaque
    "accent": "#D7F000",      # verde-limão — só preenchimento
    "on_accent": "#111111",   # texto sobre o limão
    "ink": "#D7F000",         # pílulas/botões/aba ativa: limão
    "on_ink": "#111111",      # …com texto preto
    # Status (tons vivos para leitura no escuro)
    "crit": "#FF5A5A",        # falta, avarias
    "warn": "#FFB020",        # sobra
    "warn_ink": "#FFB020",    # sobra em texto pequeno (≥9:1 sobre #1C1D21)
    "ok": "#4CC38A",          # ok
    "info": "#7B9BFF",        # repor loja
    "purple": "#B69CFF",
    "teal": "#3CCFBF",
    # Fundos de status escuros e translúcidos (círculos de ícone, chips)
    "crit_soft": "rgba(255,90,90,0.16)",     # rosa
    "warn_soft": "rgba(255,176,32,0.16)",    # laranja
    "ok_soft": "rgba(76,195,138,0.16)",      # verde
    "info_soft": "rgba(123,155,255,0.16)",
    "purple_soft": "rgba(182,156,255,0.18)", # roxo
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
--c-faint: #8E9096;
--r-card: 20px; --r-row: 12px; --r-pill: 999px;
--f-sans: 'Inter', 'IBM Plex Sans', system-ui, sans-serif;
--f-mono: 'IBM Plex Mono', ui-monospace, monospace;
"""

ROOT_CSS = ":root {\n" + ROOT_VARS + "}\n"

