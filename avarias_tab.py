"""
CAMDA Estoque Mestre — Aba Avarias
Layout: Cards quadrados lado a lado
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, date
import json


def render_avarias_cards(df_avarias):
    """
    Renderiza as avarias abertas em layout de cards quadrados.

    Colunas esperadas em df_avarias (DataFrame ou lista de dicts):
        - produto       : str  — nome do produto
        - status        : str  — 'ABERTA' | 'FECHADA'  (ou 'aberto')
        - data_registro : date/datetime/str — data de abertura
        - fotos         : list — lista de paths/urls (pode ser vazia)
    """

    hoje = date.today()

    if hasattr(df_avarias, "to_dict"):
        todos = df_avarias.to_dict("records")
    else:
        todos = list(df_avarias)

    def _is_aberta(r):
        s = str(r.get("status", "")).lower()
        return s in ("aberta", "aberto", "open")

    registros = [r for r in todos if _is_aberta(r)]
    total_abertas = len(registros)

    st.markdown(
        f"<p style='font-size:12px; color:#aaa; margin-bottom:10px;'>"
        f"Avarias abertas &nbsp;"
        f"<span style='color:#e24b4a; font-weight:600;'>{total_abertas}</span></p>",
        unsafe_allow_html=True,
    )

    if total_abertas == 0:
        st.info("Nenhuma avaria aberta no momento.")
        return

    cards_data = []
    for r in registros:
        data_reg = r.get("data_registro")

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
            cor_borda = "#e24b4a"
            cor_status_bg = "#FCEBEB"
            cor_status_txt = "#A32D2D"
            cor_status_border = "#F09595"
        elif dias <= 20:
            tempo_label = f"{dias}d atrás"
            cor_borda = "#EF9F27"
            cor_status_bg = "#FAEEDA"
            cor_status_txt = "#854F0B"
            cor_status_border = "#FAC775"
        else:
            tempo_label = f"{dias}d atrás"
            cor_borda = "#BA7517"
            cor_status_bg = "#FAEEDA"
            cor_status_txt = "#854F0B"
            cor_status_border = "#FAC775"

        fotos = r.get("fotos", [])
        n_fotos = len(fotos) if isinstance(fotos, (list, tuple)) else (1 if fotos else 0)

        cards_data.append({
            "produto": r.get("produto", "—"),
            "tempo_label": tempo_label,
            "cor_borda": cor_borda,
            "cor_status_bg": cor_status_bg,
            "cor_status_txt": cor_status_txt,
            "cor_status_border": cor_status_border,
            "n_fotos": n_fotos,
        })

    cards_json = json.dumps(cards_data, ensure_ascii=False)

    html = f"""
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}

      .avarias-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
        gap: 10px;
        font-family: 'Source Sans Pro', sans-serif;
      }}

      .av-card {{
        background: #0e1117;
        border-radius: 10px;
        border: 0.5px solid #2a2a3a;
        border-top-width: 2.5px;
        aspect-ratio: 1 / 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        cursor: pointer;
        transition: border-color 0.15s, transform 0.1s;
      }}
      .av-card:hover {{
        transform: translateY(-1px);
        border-color: #444;
      }}

      .card-top {{
        padding: 9px 10px 6px;
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }}

      .card-status-row {{
        display: flex;
        align-items: center;
        gap: 5px;
      }}

      .card-status {{
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 9px;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 99px;
        border-width: 0.5px;
        border-style: solid;
      }}

      .card-time {{
        font-size: 9px;
        color: #666;
      }}

      .card-product {{
        font-size: 11px;
        font-weight: 600;
        color: #ddd;
        line-height: 1.35;
        flex: 1;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}

      .card-photos {{
        display: flex;
        gap: 4px;
        padding: 6px 10px 10px;
      }}

      .photo-thumb {{
        flex: 1;
        aspect-ratio: 1 / 1;
        max-height: 40px;
        background: #1a1d27;
        border-radius: 5px;
        border: 0.5px solid #2a2a3a;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-size: 9px;
        color: #555;
        gap: 2px;
      }}

      .no-foto {{
        flex: 1;
        max-height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 9px;
        color: #333;
      }}

      .add-card {{
        background: #0e1117;
        border-radius: 10px;
        border: 0.5px dashed #2a2a3a;
        aspect-ratio: 1 / 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 5px;
        cursor: pointer;
        font-size: 11px;
        color: #444;
        transition: border-color 0.15s;
      }}
      .add-card:hover {{
        border-color: #555;
        color: #777;
      }}
    </style>

    <div class="avarias-grid" id="avarias-grid"></div>

    <script>
      const cards = {cards_json};

      const camIcon = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <path d="m21 15-5-5L5 21"/>
      </svg>`;

      const plusIcon = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="1.5" opacity="0.4">
        <circle cx="12" cy="12" r="9"/>
        <path d="M12 8v8M8 12h8"/>
      </svg>`;

      const grid = document.getElementById('avarias-grid');

      cards.forEach(c => {{
        let fotosHtml = '';
        if (c.n_fotos > 0) {{
          fotosHtml = Array.from({{length: Math.min(c.n_fotos, 3)}}, (_, i) =>
            `<div class="photo-thumb">${{camIcon}}<span>${{i+1}}</span></div>`
          ).join('');
        }} else {{
          fotosHtml = `<div class="no-foto">sem fotos</div>`;
        }}

        const card = document.createElement('div');
        card.className = 'av-card';
        card.style.borderTopColor = c.cor_borda;
        card.innerHTML = `
          <div class="card-top">
            <div class="card-status-row">
              <span class="card-status" style="
                background:${{c.cor_status_bg}};
                color:${{c.cor_status_txt}};
                border-color:${{c.cor_status_border}};">
                &#9888; ABERTA
              </span>
              <span class="card-time">${{c.tempo_label}}</span>
            </div>
            <div class="card-product">${{c.produto}}</div>
          </div>
          <div class="card-photos">${{fotosHtml}}</div>
        `;
        grid.appendChild(card);
      }});

      const addCard = document.createElement('div');
      addCard.className = 'add-card';
      addCard.innerHTML = `${{plusIcon}}<span>registrar avaria</span>`;
      grid.appendChild(addCard);
    </script>
    """

    linhas = max(1, -(-len(registros) // 4))
    altura = linhas * 175 + 40

    components.html(html, height=altura, scrolling=False)
