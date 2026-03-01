"""
CAMDA Dashboard — Banner Inteligente com 5 Tipos de Slide
Carrossel com imagens locais em base64, dados de clima, notícias RSS e preços CEPEA.
"""

import base64
import random
from pathlib import Path

import streamlit as st

# ── Diretório de imagens ──────────────────────────────────────────────────────
BANNER_DIR = Path("assets/banner")

# ── Catálogo: mapeamento tipo → imagens e estilos ────────────────────────────
CATALOGO = {
    "noticias": {
        "imagens": ["Imagem1.jpg", "Imagem5.jpg", "Imagem11.jpg"],
        "tag":     "📰 Agro Goiás",
        "cor_tag": "#0a84ff",
        "bg_tag":  "rgba(10,132,255,0.2)",
        "border":  "rgba(10,132,255,0.35)",
    },
    "clima": {
        "imagens": ["Imagem6.jpg", "Imagem8.jpg", "Imagem9.jpg"],
        "tag":     "🌤 Clima Hoje",
        "cor_tag": "#64b5ff",
        "bg_tag":  "rgba(10,132,255,0.2)",
        "border":  "rgba(10,132,255,0.35)",
    },
    "precos": {
        "imagens": ["Imagem4.jpg", "Imagem12.jpg", "Imagem13.jpg"],
        "tag":     "💰 Preços CEPEA",
        "cor_tag": "#2dff7a",
        "bg_tag":  "rgba(45,255,122,0.15)",
        "border":  "rgba(45,255,122,0.3)",
    },
    "alerta": {
        "imagens": ["Imagem2.jpg", "Imagem3.jpg", "Imagem7.jpg"],
        "tag":     "⚠️ Alerta Fitossanitário",
        "cor_tag": "#ff9f0a",
        "bg_tag":  "rgba(255,159,10,0.2)",
        "border":  "rgba(255,159,10,0.35)",
    },
    "manejo": {
        "imagens": ["Imagem10.jpg", "Imagem8.jpg", "Imagem11.jpg"],
        "tag":     "🌱 Boas Práticas",
        "cor_tag": "#2dff7a",
        "bg_tag":  "rgba(45,255,122,0.15)",
        "border":  "rgba(45,255,122,0.3)",
    },
}


# ── Utilitários ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def img_b64(nome: str) -> str:
    """Carrega imagem da pasta assets/banner/ e retorna em base64."""
    try:
        caminho = BANNER_DIR / nome
        if caminho.exists():
            return base64.b64encode(caminho.read_bytes()).decode()
        # fallback: usa qualquer imagem disponível
        for f in sorted(BANNER_DIR.glob("*.jpg")):
            return base64.b64encode(f.read_bytes()).decode()
        return ""
    except Exception:
        return ""


def _banner_dir_tem_imagens() -> bool:
    """Verifica se a pasta assets/banner/ existe e contém pelo menos uma imagem."""
    if not BANNER_DIR.exists():
        return False
    return any(BANNER_DIR.glob("*.jpg"))


# ── Funções de dados ──────────────────────────────────────────────────────────

def _wcode_desc(code: int) -> str:
    """Converte código WMO para descrição em português."""
    if code == 0:             return "Céu limpo"
    if code in (1, 2):        return "Poucas nuvens"
    if code == 3:             return "Nublado"
    if code in (45, 48):      return "Névoa"
    if code in (51, 53, 55):  return "Chuvisco"
    if code in (61, 63, 65):  return "Chuva"
    if code in (80, 81, 82):  return "Pancadas de chuva"
    if code in (95, 96, 99):  return "Tempestade"
    if code in (71, 73, 75):  return "Neve"
    return "Parcialmente nublado"


@st.cache_data(ttl=600)
def buscar_clima() -> dict:
    """Busca clima atual de Quirinópolis via Open-Meteo (gratuito, sem chave)."""
    try:
        import urllib.request, json
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=-18.45&longitude=-50.45"
            "&current=temperature_2m,weathercode,relative_humidity_2m,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=America%2FSao_Paulo"
            "&forecast_days=1"
        )
        with urllib.request.urlopen(url, timeout=5) as r:
            d = json.loads(r.read())
        cur  = d["current"]
        code = int(cur["weathercode"])
        return {
            "temp":    round(cur["temperature_2m"]),
            "desc":    _wcode_desc(code),
            "umidade": round(cur.get("relative_humidity_2m", 65)),
            "vento":   round(cur.get("wind_speed_10m", 8)),
            "min":     round(d["daily"]["temperature_2m_min"][0]),
            "max":     round(d["daily"]["temperature_2m_max"][0]),
        }
    except Exception:
        return {
            "temp": 29, "desc": "Parcialmente nublado",
            "umidade": 65, "vento": 8, "min": 22, "max": 33,
        }


@st.cache_data(ttl=1800)
def buscar_noticias() -> list:
    """Busca notícias agrícolas via feeds RSS. Sempre retorna fallbacks mockados se RSS falhar."""
    try:
        import feedparser
    except ImportError:
        feedparser = None

    feeds = [
        ("noticias", "https://www.noticiasagricolas.com.br/rss/noticias"),
        ("noticias", "https://www.canalrural.com.br/feed/"),
        ("alerta",   "https://www.embrapa.br/rss/noticias"),
        ("manejo",   "https://www.canalrural.com.br/feed/"),
    ]
    palavras = {
        "noticias": ["soja", "milho", "cana", "gado", "goiás", "cerrado",
                     "agro", "safra", "colheita", "defensivo", "produção"],
        "alerta":   ["praga", "lagarta", "ferrugem", "fungo", "doença",
                     "mosca", "percevejo", "nematóide", "alerta"],
        "manejo":   ["manejo", "solo", "irrigação", "adubação", "plantio",
                     "rotação", "cobertura", "boas práticas", "nutrição"],
    }
    resultado = []

    if feedparser is not None:
        for tipo, url in feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    titulo = entry.get("title", "")
                    link   = entry.get("link", "#")
                    kws    = palavras.get(tipo, [])
                    if any(p in titulo.lower() for p in kws):
                        resultado.append({
                            "tipo":   tipo,
                            "titulo": titulo,
                            "link":   link,
                            "fonte":  feed.feed.get("title", ""),
                        })
            except Exception:
                continue

    # fallbacks obrigatórios se RSS falhar ou não retornar resultados
    if not any(r["tipo"] == "noticias" for r in resultado):
        resultado.append({
            "tipo":   "noticias",
            "titulo": "Safra de soja em Goiás deve bater recorde em 2026",
            "link":   "https://www.noticiasagricolas.com.br",
            "fonte":  "Notícias Agrícolas",
        })
    if not any(r["tipo"] == "alerta" for r in resultado):
        resultado.append({
            "tipo":   "alerta",
            "titulo": "Lagarta-do-cartucho em alta no milho safrinha do CO",
            "link":   "https://www.embrapa.br/soja",
            "fonte":  "Embrapa",
        })
    if not any(r["tipo"] == "manejo" for r in resultado):
        resultado.append({
            "tipo":   "manejo",
            "titulo": "Rotação de culturas melhora saúde do solo no Cerrado",
            "link":   "https://www.embrapa.br",
            "fonte":  "Embrapa Cerrados",
        })
    return resultado


@st.cache_data(ttl=3600)
def buscar_precos() -> dict:
    """Retorna preços CEPEA (mock — expansível com scraping)."""
    return {
        "soja":  {"valor": "R$ 148,50", "var": "+1,2%", "up": True},
        "milho": {"valor": "R$  62,80", "var": "-0,4%", "up": False},
    }


# ── Montagem dos slides ───────────────────────────────────────────────────────

def montar_slides(clima: dict, noticias: list, precos: dict) -> list:
    """Monta a lista de dicts de slides a partir dos dados recebidos."""
    slides = []
    cat = CATALOGO

    # --- SLIDE CLIMA ---
    img = random.choice(cat["clima"]["imagens"])
    slides.append({
        "tipo":          "clima",
        "b64":           img_b64(img),
        "tag":           cat["clima"]["tag"],
        "cor":           cat["clima"]["cor_tag"],
        "bg":            cat["clima"]["bg_tag"],
        "border":        cat["clima"]["border"],
        "titulo":        f"Quirinópolis — {clima['temp']}°C",
        "sub":           f"{clima['desc']} · Umidade {clima['umidade']}% · Vento {clima['vento']} km/h",
        "extra":         f"Mín {clima['min']}° · Máx {clima['max']}°",
        "link":          "#",
        "clima_temp":    clima["temp"],
        "clima_desc":    clima["desc"],
        "clima_umidade": clima["umidade"],
        "clima_vento":   clima["vento"],
        "clima_min":     clima["min"],
        "clima_max":     clima["max"],
    })

    # --- SLIDE PREÇOS ---
    img = random.choice(cat["precos"]["imagens"])
    soja_var_cor  = "#2dff7a" if precos["soja"]["up"]  else "#ff3b3b"
    milho_var_cor = "#2dff7a" if precos["milho"]["up"] else "#ff3b3b"
    slides.append({
        "tipo":      "precos",
        "b64":       img_b64(img),
        "tag":       cat["precos"]["tag"],
        "cor":       cat["precos"]["cor_tag"],
        "bg":        cat["precos"]["bg_tag"],
        "border":    cat["precos"]["border"],
        "titulo":    "Cotações do Dia",
        "sub":       "Mercado físico Goiás · CEPEA/ESALQ",
        "link":      "https://www.cepea.esalq.usp.br/br/indicador/soja.aspx",
        "soja_val":  precos["soja"]["valor"],
        "soja_var":  precos["soja"]["var"],
        "soja_cor":  soja_var_cor,
        "milho_val": precos["milho"]["valor"],
        "milho_var": precos["milho"]["var"],
        "milho_cor": milho_var_cor,
    })

    # --- SLIDES DE NOTÍCIAS (até 2) ---
    nots = [n for n in noticias if n["tipo"] == "noticias"][:2]
    for n in nots:
        img = random.choice(cat["noticias"]["imagens"])
        slides.append({
            "tipo":   "noticias",
            "b64":    img_b64(img),
            "tag":    cat["noticias"]["tag"],
            "cor":    cat["noticias"]["cor_tag"],
            "bg":     cat["noticias"]["bg_tag"],
            "border": cat["noticias"]["border"],
            "titulo": n["titulo"],
            "sub":    n["fonte"],
            "link":   n["link"],
        })

    # --- SLIDE ALERTA ---
    alertas = [n for n in noticias if n["tipo"] == "alerta"]
    if alertas:
        n   = alertas[0]
        img = random.choice(cat["alerta"]["imagens"])
        slides.append({
            "tipo":   "alerta",
            "b64":    img_b64(img),
            "tag":    cat["alerta"]["tag"],
            "cor":    cat["alerta"]["cor_tag"],
            "bg":     cat["alerta"]["bg_tag"],
            "border": cat["alerta"]["border"],
            "titulo": n["titulo"],
            "sub":    n["fonte"],
            "link":   n["link"],
        })

    # --- SLIDE BOAS PRÁTICAS ---
    manejos = [n for n in noticias if n["tipo"] == "manejo"]
    if manejos:
        n   = manejos[0]
        img = random.choice(cat["manejo"]["imagens"])
        slides.append({
            "tipo":   "manejo",
            "b64":    img_b64(img),
            "tag":    cat["manejo"]["tag"],
            "cor":    cat["manejo"]["cor_tag"],
            "bg":     cat["manejo"]["bg_tag"],
            "border": cat["manejo"]["border"],
            "titulo": n["titulo"],
            "sub":    n["fonte"],
            "link":   n["link"],
        })

    return slides


# ── Geração do HTML do carrossel ──────────────────────────────────────────────

def gerar_html_banner(slides: list) -> str:
    """Gera o HTML completo do carrossel com todos os slides."""
    if not slides:
        return ""

    n = len(slides)
    slides_html = ""
    dots_html   = ""

    for i, s in enumerate(slides):
        ativo    = "active" if i == 0 else ""
        clicavel = "cursor:pointer;" if s["link"] != "#" else ""
        onclick  = f"window.open('{s['link']}','_blank')" if s["link"] != "#" else ""

        # Card especial para clima
        card_extra = ""
        if s["tipo"] == "clima":
            card_extra = f"""
            <div class="clima-card">
              <div style="font-size:28px;line-height:1">☀️</div>
              <div class="clima-big">{s['clima_temp']}°</div>
              <div class="clima-desc">{s['clima_desc']}</div>
              <div class="clima-row">
                <span>💧 {s['clima_umidade']}%</span>
                <span>💨 {s['clima_vento']}km/h</span>
              </div>
              <div class="clima-row" style="margin-top:3px">
                <span>↓{s['clima_min']}°</span>
                <span>↑{s['clima_max']}°</span>
              </div>
            </div>"""

        # Card especial para preços
        if s["tipo"] == "precos":
            card_extra = f"""
            <div class="preco-cards">
              <div class="preco-pill">
                <div class="preco-nome">Soja SC 60kg</div>
                <div class="preco-val">{s['soja_val']}</div>
                <div class="preco-var" style="color:{s['soja_cor']}">{s['soja_var']}</div>
              </div>
              <div class="preco-pill">
                <div class="preco-nome">Milho SC 60kg</div>
                <div class="preco-val">{s['milho_val']}</div>
                <div class="preco-var" style="color:{s['milho_cor']}">{s['milho_var']}</div>
              </div>
            </div>"""

        link_text = ""
        if s["tipo"] == "noticias":
            link_text = "↗ Ler matéria completa"
        elif s["tipo"] == "alerta":
            link_text = "↗ Ver recomendações técnicas"
        elif s["tipo"] == "precos":
            link_text = "↗ Acessar CEPEA"
        elif s["tipo"] == "manejo":
            link_text = "↗ Leia mais"

        link_html = (
            f'<div class="slide-link" style="color:{s["cor"]}">{link_text}</div>'
            if link_text else ""
        )

        img_tag = (
            f'<img src="data:image/jpeg;base64,{s["b64"]}" alt="">'
            if s["b64"] else
            '<div style="width:100%;height:230px;background:linear-gradient(135deg,#1a3a2a,#0d2b1a)"></div>'
        )

        slides_html += f"""
        <div class="slide {ativo}" style="{clicavel}" onclick="{onclick}">
          {img_tag}
          <div class="overlay"></div>
          {card_extra}
          <div class="slide-content">
            <div class="slide-tag" style="color:{s['cor']};background:{s['bg']};border:1px solid {s['border']}">{s['tag']}</div>
            <div class="slide-title">{s['titulo']}</div>
            <div class="slide-sub">{s['sub']}</div>
            {link_html}
          </div>
        </div>"""
        dots_html += f'<div class="dot {"active" if i == 0 else ""}"></div>'

    return f"""
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  .camda-banner{{position:relative;overflow:hidden;border-radius:16px;height:230px;margin-bottom:8px}}
  .slide{{position:absolute;inset:0;opacity:0;transition:opacity 1.3s ease;will-change:opacity}}
  .slide.active{{opacity:1;position:relative;height:230px}}
  .slide img{{width:100%;height:230px;object-fit:cover;display:block}}
  .slide.active img{{animation:kb 6s ease-out both}}
  @keyframes kb{{from{{transform:scale(1.07)}}to{{transform:scale(1)}}}}
  .overlay{{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.88) 0%,rgba(0,0,0,.2) 55%,rgba(0,0,0,.05) 100%)}}
  .slide-content{{position:absolute;bottom:0;left:0;right:0;padding:14px 16px 18px}}
  .slide-tag{{display:inline-block;font-family:'DM Sans',sans-serif;font-size:9px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;border-radius:100px;padding:3px 8px;margin-bottom:6px;opacity:0;transform:translateY(6px);transition:opacity .5s .35s ease,transform .5s .35s ease}}
  .slide-title{{font-family:'Syne',sans-serif;font-size:19px;font-weight:800;line-height:1.15;letter-spacing:-.3px;color:#fff;opacity:0;transform:translateY(10px);transition:opacity .5s .5s ease,transform .5s .5s ease}}
  .slide-sub{{font-family:'DM Sans',sans-serif;font-size:11px;color:rgba(255,255,255,.6);margin-top:4px;opacity:0;transform:translateY(6px);transition:opacity .5s .65s ease,transform .5s .65s ease}}
  .slide-link{{font-size:10px;font-weight:600;margin-top:5px;opacity:0;transform:translateY(6px);transition:opacity .5s .78s ease,transform .5s .78s ease}}
  .slide.active .slide-tag,.slide.active .slide-title,.slide.active .slide-sub,.slide.active .slide-link{{opacity:1;transform:translateY(0)}}
  .clima-card{{position:absolute;top:14px;right:14px;background:rgba(0,0,0,.5);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:10px 13px;text-align:right;opacity:0;transform:translateY(-8px);transition:opacity .6s .4s ease,transform .6s .4s ease}}
  .slide.active .clima-card{{opacity:1;transform:translateY(0)}}
  .clima-big{{font-family:'Syne',sans-serif;font-size:34px;font-weight:800;line-height:1;color:#fff}}
  .clima-desc{{font-size:10px;color:rgba(255,255,255,.6);margin-top:2px}}
  .clima-row{{display:flex;gap:8px;margin-top:4px;font-size:9px;color:rgba(255,255,255,.5)}}
  .preco-cards{{position:absolute;top:14px;right:14px;display:flex;flex-direction:column;gap:5px;opacity:0;transform:translateX(10px);transition:opacity .6s .4s ease,transform .6s .4s ease}}
  .slide.active .preco-cards{{opacity:1;transform:translateX(0)}}
  .preco-pill{{background:rgba(0,0,0,.55);backdrop-filter:blur(12px);border:1px solid rgba(45,255,122,.2);border-radius:10px;padding:7px 11px;text-align:right}}
  .preco-nome{{font-size:9px;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.5px}}
  .preco-val{{font-family:'Syne',sans-serif;font-size:17px;font-weight:800;color:#2dff7a;line-height:1.1}}
  .preco-var{{font-size:9px;font-weight:600}}
  .camda-dots{{position:absolute;bottom:10px;right:12px;display:flex;gap:4px;z-index:10}}
  .dot{{width:5px;height:5px;border-radius:50%;background:rgba(255,255,255,.3);transition:all .4s ease}}
  .dot.active{{width:18px;border-radius:3px;background:#2dff7a;box-shadow:0 0 8px rgba(45,255,122,.7)}}
  .camda-pbar{{position:absolute;bottom:0;left:0;height:3px;background:linear-gradient(90deg,#2dff7a,#0a84ff);width:0%;z-index:10;border-radius:0 3px 3px 0;box-shadow:0 0 8px rgba(45,255,122,.4)}}
</style>

<div class="camda-banner">
  {slides_html}
  <div class="camda-dots">{dots_html}</div>
  <div class="camda-pbar" id="camda_pb"></div>
</div>

<script>
(function(){{
  const slides=[...document.querySelectorAll('.slide')];
  const dots=[...document.querySelectorAll('.dot')];
  const pb=document.getElementById('camda_pb');
  let cur=0,st,raf,dur=5500;
  function goTo(n){{
    slides[cur].classList.remove('active');
    dots[cur].classList.remove('active');
    cur=(n+{n})%{n};
    slides[cur].classList.add('active');
    dots[cur].classList.add('active');
    run();
  }}
  function run(){{
    cancelAnimationFrame(raf);
    pb.style.transition='none';pb.style.width='0%';
    st=performance.now();
    (function tick(now){{
      const p=Math.min((now-st)/dur,1);
      pb.style.width=(p*100)+'%';
      if(p<1)raf=requestAnimationFrame(tick);
      else goTo(cur+1);
    }})(performance.now());
  }}
  run();
}})();
</script>
"""


# ── Função principal de renderização ─────────────────────────────────────────

def render_banner() -> None:
    """
    Ponto de entrada único para renderizar o carrossel no dashboard Streamlit.
    Se a pasta assets/banner/ não existir ou estiver vazia, não exibe nada (sem erro).
    """
    if not _banner_dir_tem_imagens():
        return

    clima    = buscar_clima()
    noticias = buscar_noticias()
    precos   = buscar_precos()

    slides = montar_slides(clima, noticias, precos)
    html   = gerar_html_banner(slides)

    if html:
        st.markdown(html, unsafe_allow_html=True)
