"""
weather_animation.py
Animação de clima para o dashboard CAMDA.

Como usar no seu app principal:
    from weather_animation import render_weather_animation
    render_weather_animation(weather_code, container=st.container())

Requer: streamlit, time (stdlib)
"""

import streamlit as st
import time
import math
import random

# ── Mapeamento de weathercode → tipo de animação ─────────────────────────────
def get_animation_type(code: int) -> str:
    """Retorna 'clear', 'cloudy', 'rain', 'storm', 'fog', 'drizzle' ou 'wind'."""
    if code == 0:
        return "clear"
    elif code in (1, 2):
        return "wind"        # poucas nuvens + vento leve
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


# ── Paletas e configs por tipo ────────────────────────────────────────────────
CONFIGS = {
    "clear": {
        "bg": "linear-gradient(180deg, #0a1628 0%, #1a2a4a 100%)",
        "label": "☀️ Céu limpo",
    },
    "wind": {
        "bg": "linear-gradient(180deg, #0d1f3c 0%, #1e3a5f 100%)",
        "label": "🌤️ Vento",
    },
    "cloudy": {
        "bg": "linear-gradient(180deg, #1a1a2e 0%, #2d2d44 100%)",
        "label": "☁️ Nublado",
    },
    "fog": {
        "bg": "linear-gradient(180deg, #1a1e2e 0%, #2a2e3e 100%)",
        "label": "🌫️ Névoa",
    },
    "drizzle": {
        "bg": "linear-gradient(180deg, #0f1a2e 0%, #1a2a3e 100%)",
        "label": "🌦️ Chuvisco",
    },
    "rain": {
        "bg": "linear-gradient(180deg, #080e1a 0%, #0f1a2a 100%)",
        "label": "🌧️ Chuva",
    },
    "storm": {
        "bg": "linear-gradient(180deg, #05080f 0%, #0a0f1a 100%)",
        "label": "⛈️ Tempestade",
    },
}


# ── Geradores de partículas ───────────────────────────────────────────────────

def _rain_particles(n: int, angle: int = 15, speed_mult: float = 1.0) -> str:
    """Gera gotas de chuva como elementos CSS absolutos."""
    drops = []
    for i in range(n):
        x = random.uniform(0, 100)
        delay = random.uniform(0, 1.5)
        dur = random.uniform(0.4, 0.9) / speed_mult
        h = random.uniform(12, 24)
        opacity = random.uniform(0.5, 0.9)
        drops.append(
            f'<div style="position:absolute;left:{x}%;top:-5%;'
            f'width:1.5px;height:{h}px;'
            f'background:rgba(160,210,255,{opacity});'
            f'border-radius:0 0 2px 2px;'
            f'animation:fall {dur:.2f}s linear {delay:.2f}s infinite;'
            f'transform:rotate({angle}deg);"></div>'
        )
    return "".join(drops)


def _cloud_elements(n: int, speed: float = 25.0, opacity: float = 0.7) -> str:
    """Gera nuvens que drifam horizontalmente."""
    clouds = []
    sizes = [(120, 50), (90, 40), (150, 60), (80, 35), (110, 45)]
    for i in range(n):
        w, h = random.choice(sizes)
        y = random.uniform(5, 50)
        delay = random.uniform(0, speed)
        dur = random.uniform(speed * 0.7, speed * 1.3)
        blur = random.uniform(8, 18)
        op = random.uniform(opacity * 0.6, opacity)
        clouds.append(
            f'<div style="position:absolute;left:-20%;top:{y}%;'
            f'width:{w}px;height:{h}px;'
            f'background:rgba(200,210,230,{op:.2f});'
            f'border-radius:50%;'
            f'filter:blur({blur:.0f}px);'
            f'animation:drift {dur:.1f}s linear {delay:.1f}s infinite;"></div>'
        )
    return "".join(clouds)


def _wind_streaks(n: int) -> str:
    """Linhas horizontais de vento."""
    streaks = []
    for i in range(n):
        y = random.uniform(10, 90)
        delay = random.uniform(0, 2)
        dur = random.uniform(1.2, 2.5)
        w = random.randint(40, 100)
        opacity = random.uniform(0.15, 0.4)
        streaks.append(
            f'<div style="position:absolute;left:-20%;top:{y}%;'
            f'width:{w}px;height:1px;'
            f'background:rgba(180,200,220,{opacity});'
            f'border-radius:2px;'
            f'animation:streak {dur:.2f}s ease-in {delay:.2f}s infinite;"></div>'
        )
    return "".join(streaks)


def _fog_layers(n: int) -> str:
    """Camadas de névoa."""
    layers = []
    for i in range(n):
        y = random.uniform(20, 80)
        delay = random.uniform(0, 4)
        dur = random.uniform(8, 16)
        h = random.randint(30, 80)
        opacity = random.uniform(0.08, 0.2)
        layers.append(
            f'<div style="position:absolute;left:-10%;top:{y}%;'
            f'width:130%;height:{h}px;'
            f'background:rgba(200,210,220,{opacity});'
            f'filter:blur(20px);'
            f'animation:fog_move {dur:.1f}s ease-in-out {delay:.1f}s infinite alternate;"></div>'
        )
    return "".join(layers)


def _lightning_flash() -> str:
    """Flash de relâmpago ocasional."""
    return (
        '<div style="position:absolute;top:0;left:0;width:100%;height:100%;'
        'background:rgba(200,220,255,0.05);'
        'animation:lightning 4s ease-in-out 0s infinite;pointer-events:none;"></div>'
    )


# ── Builder principal de HTML ─────────────────────────────────────────────────

def build_animation_html(anim_type: str, width: int = 400, height: int = 180) -> str:
    cfg = CONFIGS.get(anim_type, CONFIGS["clear"])
    bg = cfg["bg"]

    # Partículas por tipo
    particles = ""
    extra_keyframes = ""

    if anim_type == "rain":
        particles += _cloud_elements(6, speed=30, opacity=0.5)
        particles += _rain_particles(60, angle=10, speed_mult=1.0)

    elif anim_type == "drizzle":
        particles += _cloud_elements(5, speed=35, opacity=0.4)
        particles += _rain_particles(25, angle=5, speed_mult=0.6)

    elif anim_type == "storm":
        particles += _cloud_elements(8, speed=15, opacity=0.85)
        particles += _rain_particles(90, angle=20, speed_mult=1.5)
        particles += _lightning_flash()

    elif anim_type == "cloudy":
        particles += _cloud_elements(8, speed=40, opacity=0.65)

    elif anim_type == "wind":
        particles += _cloud_elements(4, speed=20, opacity=0.3)
        particles += _wind_streaks(20)

    elif anim_type == "fog":
        particles += _cloud_elements(4, speed=50, opacity=0.25)
        particles += _fog_layers(6)

    elif anim_type == "clear":
        # estrelas piscando + gradiente suave
        for _ in range(30):
            sx = random.uniform(2, 98)
            sy = random.uniform(2, 85)
            sd = random.uniform(1.5, 3.5)
            sop = random.uniform(0.4, 1.0)
            particles += (
                f'<div style="position:absolute;left:{sx:.1f}%;top:{sy:.1f}%;'
                f'width:2px;height:2px;border-radius:50%;'
                f'background:rgba(255,255,255,{sop:.2f});'
                f'animation:twinkle {sd:.1f}s ease-in-out {random.uniform(0,2):.1f}s infinite alternate;"></div>'
            )

    html = f"""
    <div style="
        position:relative;
        width:{width}px;
        height:{height}px;
        background:{bg};
        border-radius:16px;
        overflow:hidden;
        border:1px solid rgba(255,255,255,0.08);
        box-shadow:0 4px 24px rgba(0,0,0,0.5);
    ">
      {particles}
      <div style="
        position:absolute;bottom:12px;left:50%;transform:translateX(-50%);
        font-family:'Outfit',sans-serif;
        font-size:13px;color:rgba(200,220,255,0.75);
        letter-spacing:0.08em;
        pointer-events:none;
      ">{cfg['label']}</div>
    </div>

    <style>
    @keyframes fall {{
        0%   {{ transform: translateY(-10px) rotate({15}deg); opacity:0; }}
        10%  {{ opacity:1; }}
        90%  {{ opacity:1; }}
        100% {{ transform: translateY({height + 20}px) rotate({15}deg); opacity:0; }}
    }}
    @keyframes drift {{
        0%   {{ transform: translateX(0); }}
        100% {{ transform: translateX(calc({width}px + 200px)); }}
    }}
    @keyframes streak {{
        0%   {{ transform: translateX(0); opacity:0; }}
        20%  {{ opacity:1; }}
        100% {{ transform: translateX(calc({width}px + 150px)); opacity:0; }}
    }}
    @keyframes fog_move {{
        0%   {{ transform: translateX(-5%); }}
        100% {{ transform: translateX(8%); }}
    }}
    @keyframes twinkle {{
        0%   {{ opacity:0.2; transform:scale(0.8); }}
        100% {{ opacity:1;   transform:scale(1.4); }}
    }}
    @keyframes lightning {{
        0%, 88%, 92%, 100% {{ opacity:0; }}
        89%, 91%            {{ opacity:1; }}
    }}
    </style>
    """
    return html


# ── Interface pública ─────────────────────────────────────────────────────────

def render_weather_animation(weather_code: int, container=None, width: int = 400, height: int = 180):
    """
    Renderiza a animação de clima dentro de um container Streamlit.

    Parâmetros
    ----------
    weather_code : int
        Código WMO retornado pelo open-meteo (mesmo que você já usa).
    container : st.container ou None
        Se None, usa st diretamente.
    width, height : int
        Dimensões do painel de animação em pixels.
    """
    anim_type = get_animation_type(weather_code)
    html = build_animation_html(anim_type, width=width, height=height)

    target = container if container is not None else st
    target.components.v1.html(html, height=height + 10)
