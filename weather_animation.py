"""
weather_animation.py
Animação de clima sobreposta ao banner CAMDA.

COMO USAR no app principal (depois do st.markdown do banner):
    from weather_animation import render_weather_overlay
    render_weather_overlay(weather_code, banner_height=220)

Usa components.html() para contornar a sanitização de CSS animations
do Streamlit, e margin-top negativo para sobrepor ao banner.

Requer: streamlit
"""

import streamlit as st
import streamlit.components.v1 as components
import random


# ── Mapeamento de weathercode WMO → tipo de animação ────────────────────────
def get_animation_type(code: int) -> str:
    if code == 0:
        return "clear"
    elif code in (1, 2):
        return "wind"
    elif code == 3:
        return "cloudy"
    elif code in (45, 48):
        return "fog"
    elif code in (51, 53, 55):
        return "drizzle"
    elif code in (61, 63, 65, 80, 81, 82):
        return "rain"
    elif code in (95, 96, 99):
        return "storm"
    else:
        return "clear"


# ── Paletas ──────────────────────────────────────────────────────────────────
CONFIGS = {
    "clear":   {"bg": "transparent", "label": "☀️ Céu limpo"},
    "wind":    {"bg": "rgba(13,31,60,0.25)", "label": "🌤️ Vento"},
    "cloudy":  {"bg": "rgba(26,26,46,0.35)", "label": "☁️ Nublado"},
    "fog":     {"bg": "rgba(26,30,46,0.4)", "label": "🌫️ Névoa"},
    "drizzle": {"bg": "rgba(15,26,46,0.3)", "label": "🌦️ Chuvisco"},
    "rain":    {"bg": "rgba(8,14,26,0.4)", "label": "🌧️ Chuva"},
    "storm":   {"bg": "rgba(5,8,15,0.5)", "label": "⛈️ Tempestade"},
}


# ── Geradores de partículas (retornam strings HTML) ─────────────────────────

def _rain_particles(n, angle=15, speed_mult=1.0):
    drops = []
    for _ in range(n):
        x = random.uniform(0, 100)
        delay = random.uniform(0, 1.5)
        dur = random.uniform(0.4, 0.9) / speed_mult
        h = random.uniform(12, 24)
        opacity = random.uniform(0.4, 0.8)
        drops.append(
            f'<div class="drop" style="left:{x}%;'
            f'height:{h:.0f}px;'
            f'opacity:{opacity:.2f};'
            f'animation-duration:{dur:.2f}s;'
            f'animation-delay:{delay:.2f}s;'
            f'transform:rotate({angle}deg);"></div>'
        )
    return "".join(drops)


def _cloud_elements(n, speed=25.0, opacity=0.7):
    clouds = []
    sizes = [(120, 50), (90, 40), (150, 60), (80, 35), (110, 45)]
    for _ in range(n):
        w, h = random.choice(sizes)
        y = random.uniform(5, 50)
        delay = random.uniform(0, speed)
        dur = random.uniform(speed * 0.7, speed * 1.3)
        blur = random.uniform(8, 18)
        op = random.uniform(opacity * 0.6, opacity)
        clouds.append(
            f'<div class="cloud" style="top:{y}%;'
            f'width:{w}px;height:{h}px;'
            f'opacity:{op:.2f};'
            f'filter:blur({blur:.0f}px);'
            f'animation-duration:{dur:.1f}s;'
            f'animation-delay:{delay:.1f}s;"></div>'
        )
    return "".join(clouds)


def _wind_streaks(n):
    streaks = []
    for _ in range(n):
        y = random.uniform(10, 90)
        delay = random.uniform(0, 2)
        dur = random.uniform(1.2, 2.5)
        w = random.randint(40, 100)
        opacity = random.uniform(0.15, 0.4)
        streaks.append(
            f'<div class="streak" style="top:{y}%;'
            f'width:{w}px;'
            f'opacity:{opacity:.2f};'
            f'animation-duration:{dur:.2f}s;'
            f'animation-delay:{delay:.2f}s;"></div>'
        )
    return "".join(streaks)


def _fog_layers(n):
    layers = []
    for _ in range(n):
        y = random.uniform(20, 80)
        delay = random.uniform(0, 4)
        dur = random.uniform(8, 16)
        h = random.randint(30, 80)
        opacity = random.uniform(0.08, 0.2)
        layers.append(
            f'<div class="fog-layer" style="top:{y}%;'
            f'height:{h}px;'
            f'opacity:{opacity:.2f};'
            f'animation-duration:{dur:.1f}s;'
            f'animation-delay:{delay:.1f}s;"></div>'
        )
    return "".join(layers)


def _stars(n):
    stars = []
    for _ in range(n):
        x = random.uniform(2, 98)
        y = random.uniform(2, 85)
        dur = random.uniform(1.5, 3.5)
        op = random.uniform(0.4, 1.0)
        delay = random.uniform(0, 2)
        stars.append(
            f'<div class="star" style="left:{x:.1f}%;top:{y:.1f}%;'
            f'opacity:{op:.2f};'
            f'animation-duration:{dur:.1f}s;'
            f'animation-delay:{delay:.1f}s;"></div>'
        )
    return "".join(stars)


# ── Builder do HTML completo (standalone, roda no iframe) ────────────────────

def build_overlay_html(anim_type: str, height: int = 220) -> str:
    cfg = CONFIGS.get(anim_type, CONFIGS["clear"])
    bg = cfg["bg"]
    label = cfg["label"]

    # Montar partículas
    particles = ""
    if anim_type == "rain":
        particles += _cloud_elements(6, speed=30, opacity=0.5)
        particles += _rain_particles(60, angle=10, speed_mult=1.0)
    elif anim_type == "drizzle":
        particles += _cloud_elements(5, speed=35, opacity=0.4)
        particles += _rain_particles(25, angle=5, speed_mult=0.6)
    elif anim_type == "storm":
        particles += _cloud_elements(8, speed=15, opacity=0.85)
        particles += _rain_particles(90, angle=20, speed_mult=1.5)
        particles += '<div class="lightning"></div>'
    elif anim_type == "cloudy":
        particles += _cloud_elements(8, speed=40, opacity=0.65)
    elif anim_type == "wind":
        particles += _cloud_elements(4, speed=20, opacity=0.3)
        particles += _wind_streaks(20)
    elif anim_type == "fog":
        particles += _cloud_elements(4, speed=50, opacity=0.25)
        particles += _fog_layers(6)
    elif anim_type == "clear":
        particles += _stars(30)

    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{
    width: 100%;
    height: {height}px;
    overflow: hidden;
    background: {bg};
    font-family: 'Outfit', 'Segoe UI', sans-serif;
  }}
  .scene {{
    position: relative;
    width: 100%;
    height: {height}px;
    overflow: hidden;
  }}

  /* ── Label ── */
  .weather-label {{
    position: absolute;
    bottom: 10px;
    right: 16px;
    background: rgba(0,0,0,0.4);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    color: rgba(220,235,255,0.9);
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.12);
    letter-spacing: 0.06em;
    pointer-events: none;
    z-index: 10;
  }}

  /* ── Drops (rain/drizzle/storm) ── */
  .drop {{
    position: absolute;
    top: -5%;
    width: 1.5px;
    background: rgba(160,210,255,0.7);
    border-radius: 0 0 2px 2px;
    animation: fall linear infinite;
  }}
  @keyframes fall {{
    0%   {{ transform: translateY(-10px); opacity:0; }}
    10%  {{ opacity:1; }}
    90%  {{ opacity:1; }}
    100% {{ transform: translateY({height + 20}px); opacity:0; }}
  }}

  /* ── Clouds ── */
  .cloud {{
    position: absolute;
    left: -20%;
    background: rgba(200,210,230,0.6);
    border-radius: 50%;
    animation: drift linear infinite;
  }}
  @keyframes drift {{
    0%   {{ transform: translateX(0); }}
    100% {{ transform: translateX(calc(100vw + 200px)); }}
  }}

  /* ── Wind streaks ── */
  .streak {{
    position: absolute;
    left: -20%;
    height: 1px;
    background: rgba(180,200,220,0.4);
    border-radius: 2px;
    animation: streakMove ease-in infinite;
  }}
  @keyframes streakMove {{
    0%   {{ transform: translateX(0); opacity:0; }}
    20%  {{ opacity:1; }}
    100% {{ transform: translateX(calc(100vw + 150px)); opacity:0; }}
  }}

  /* ── Fog ── */
  .fog-layer {{
    position: absolute;
    left: -10%;
    width: 130%;
    background: rgba(200,210,220,0.15);
    filter: blur(20px);
    animation: fogMove ease-in-out infinite alternate;
  }}
  @keyframes fogMove {{
    0%   {{ transform: translateX(-5%); }}
    100% {{ transform: translateX(8%); }}
  }}

  /* ── Stars (clear) ── */
  .star {{
    position: absolute;
    width: 2px;
    height: 2px;
    border-radius: 50%;
    background: rgba(255,255,255,0.8);
    animation: twinkle ease-in-out infinite alternate;
  }}
  @keyframes twinkle {{
    0%   {{ opacity:0.2; transform:scale(0.8); }}
    100% {{ opacity:1;   transform:scale(1.4); }}
  }}

  /* ── Lightning (storm) ── */
  .lightning {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(200,220,255,0.06);
    animation: flash 4s ease-in-out infinite;
    pointer-events: none;
  }}
  @keyframes flash {{
    0%, 88%, 92%, 100% {{ opacity:0; }}
    89%, 91%           {{ opacity:1; }}
  }}
</style>
</head>
<body>
  <div class="scene">
    {particles}
    <div class="weather-label">{label}</div>
  </div>
</body>
</html>"""


# ── Interface pública ────────────────────────────────────────────────────────

def render_weather_overlay(weather_code: int, banner_height: int = 220):
    """
    Renderiza a animação de clima SOBREPOSTA ao banner.
    
    Chame LOGO APÓS o st.markdown() que renderiza o banner CAMDA.
    O iframe será posicionado com margin-top negativo para sobrepor.

    Parâmetros
    ----------
    weather_code : int
        Código WMO do open-meteo.
    banner_height : int
        Altura do banner em pixels (padrão: 220).
    """
    anim_type = get_animation_type(weather_code)
    html = build_overlay_html(anim_type, height=banner_height)

    # Injeta o iframe com margin-top negativo para sobrepor ao banner
    # O wrapper esconde o overflow e arredonda as bordas para combinar
    wrapper_css = f"""
    <style>
        .weather-overlay-wrapper iframe {{
            border: none !important;
            border-radius: 12px;
        }}
        .weather-overlay-wrapper {{
            margin-top: -{banner_height}px;
            margin-bottom: 0px;
            pointer-events: none;
            position: relative;
            z-index: 2;
            border-radius: 12px;
            overflow: hidden;
        }}
    </style>
    """
    st.markdown(wrapper_css, unsafe_allow_html=True)

    # Abrir div wrapper, renderizar componente, fechar div
    st.markdown('<div class="weather-overlay-wrapper">', unsafe_allow_html=True)
    components.html(html, height=banner_height, scrolling=False)
    st.markdown('</div>', unsafe_allow_html=True)
