"""
weather_animation.py
Animação de clima para o dashboard CAMDA.
"""

import streamlit.components.v1 as components
import random


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


CONFIGS = {
    "clear":   {"bg": "linear-gradient(180deg,#0a1628 0%,#1a2a4a 100%)", "label": "☀️ Céu limpo"},
    "wind":    {"bg": "linear-gradient(180deg,#0d1f3c 0%,#1e3a5f 100%)", "label": "🌤️ Vento"},
    "cloudy":  {"bg": "linear-gradient(180deg,#1a1a2e 0%,#2d2d44 100%)", "label": "☁️ Nublado"},
    "fog":     {"bg": "linear-gradient(180deg,#1a1e2e 0%,#2a2e3e 100%)", "label": "🌫️ Névoa"},
    "drizzle": {"bg": "linear-gradient(180deg,#0f1a2e 0%,#1a2a3e 100%)", "label": "🌦️ Chuvisco"},
    "rain":    {"bg": "linear-gradient(180deg,#080e1a 0%,#0f1a2a 100%)", "label": "🌧️ Chuva"},
    "storm":   {"bg": "linear-gradient(180deg,#05080f 0%,#0a0f1a 100%)", "label": "⛈️ Tempestade"},
}


def _rain_particles(n, angle=15, speed_mult=1.0):
    drops = []
    for _ in range(n):
        x     = random.uniform(0, 100)
        delay = random.uniform(0, 1.5)
        dur   = random.uniform(0.4, 0.9) / speed_mult
        h     = random.uniform(12, 24)
        op    = random.uniform(0.5, 0.9)
        drops.append(
            f'<div style="position:absolute;left:{x:.1f}%;top:-5%;'
            f'width:1.5px;height:{h:.0f}px;background:rgba(160,210,255,{op:.2f});'
            f'border-radius:0 0 2px 2px;transform:rotate({angle}deg);'
            f'animation:fall {dur:.2f}s linear {delay:.2f}s infinite;"></div>'
        )
    return "".join(drops)


def _cloud_elements(n, speed=25.0, opacity=0.7, width=400):
    clouds = []
    sizes  = [(120,50),(90,40),(150,60),(80,35),(110,45)]
    for _ in range(n):
        w, h  = random.choice(sizes)
        y     = random.uniform(5, 50)
        delay = random.uniform(0, speed)
        dur   = random.uniform(speed*0.7, speed*1.3)
        blur  = random.uniform(8, 18)
        op    = random.uniform(opacity*0.6, opacity)
        clouds.append(
            f'<div style="position:absolute;left:-20%;top:{y:.1f}%;'
            f'width:{w}px;height:{h}px;background:rgba(200,210,230,{op:.2f});'
            f'border-radius:50%;filter:blur({blur:.0f}px);'
            f'animation:drift {dur:.1f}s linear {delay:.1f}s infinite;"></div>'
        )
    return "".join(clouds)


def _wind_streaks(n):
    streaks = []
    for _ in range(n):
        y     = random.uniform(10, 90)
        delay = random.uniform(0, 2)
        dur   = random.uniform(1.2, 2.5)
        w     = random.randint(40, 100)
        op    = random.uniform(0.15, 0.4)
        streaks.append(
            f'<div style="position:absolute;left:-20%;top:{y:.1f}%;'
            f'width:{w}px;height:1px;background:rgba(180,200,220,{op:.2f});'
            f'border-radius:2px;'
            f'animation:streak {dur:.2f}s ease-in {delay:.2f}s infinite;"></div>'
        )
    return "".join(streaks)


def _fog_layers(n):
    layers = []
    for _ in range(n):
        y     = random.uniform(20, 80)
        delay = random.uniform(0, 4)
        dur   = random.uniform(8, 16)
        h     = random.randint(30, 80)
        op    = random.uniform(0.08, 0.2)
        layers.append(
            f'<div style="position:absolute;left:-10%;top:{y:.1f}%;'
            f'width:130%;height:{h}px;background:rgba(200,210,220,{op:.2f});'
            f'filter:blur(20px);'
            f'animation:fog_move {dur:.1f}s ease-in-out {delay:.1f}s infinite alternate;"></div>'
        )
    return "".join(layers)


def _lightning_flash():
    return (
        '<div style="position:absolute;top:0;left:0;width:100%;height:100%;'
        'background:rgba(200,220,255,0.05);'
        'animation:lightning 4s ease-in-out 0s infinite;pointer-events:none;"></div>'
    )


def _stars(n):
    stars = []
    for _ in range(n):
        sx  = random.uniform(2, 98)
        sy  = random.uniform(2, 85)
        sd  = random.uniform(1.5, 3.5)
        sop = random.uniform(0.4, 1.0)
        dl  = random.uniform(0, 2)
        stars.append(
            f'<div style="position:absolute;left:{sx:.1f}%;top:{sy:.1f}%;'
            f'width:2px;height:2px;border-radius:50%;'
            f'background:rgba(255,255,255,{sop:.2f});'
            f'animation:twinkle {sd:.1f}s ease-in-out {dl:.1f}s infinite alternate;"></div>'
        )
    return "".join(stars)


def render_weather_animation(weather_code: int, container=None, width: int = 400, height: int = 180):
    anim_type = get_animation_type(weather_code)
    cfg       = CONFIGS.get(anim_type, CONFIGS["clear"])
    bg        = cfg["bg"]
    label     = cfg["label"]

    particles = ""
    if anim_type == "rain":
        particles += _cloud_elements(6, speed=30, opacity=0.5, width=width)
        particles += _rain_particles(60, angle=10, speed_mult=1.0)
    elif anim_type == "drizzle":
        particles += _cloud_elements(5, speed=35, opacity=0.4, width=width)
        particles += _rain_particles(25, angle=5, speed_mult=0.6)
    elif anim_type == "storm":
        particles += _cloud_elements(8, speed=15, opacity=0.85, width=width)
        particles += _rain_particles(90, angle=20, speed_mult=1.5)
        particles += _lightning_flash()
    elif anim_type == "cloudy":
        particles += _cloud_elements(8, speed=40, opacity=0.65, width=width)
    elif anim_type == "wind":
        particles += _cloud_elements(4, speed=20, opacity=0.3, width=width)
        particles += _wind_streaks(20)
    elif anim_type == "fog":
        particles += _cloud_elements(4, speed=50, opacity=0.25, width=width)
        particles += _fog_layers(6)
    elif anim_type == "clear":
        particles += _stars(30)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:transparent; overflow:hidden; }}
  .box {{
    position:relative;
    width:{width}px;
    height:{height}px;
    background:{bg};
    border-radius:16px;
    overflow:hidden;
    border:1px solid rgba(255,255,255,0.08);
    box-shadow:0 4px 24px rgba(0,0,0,0.5);
  }}
  .lbl {{
    position:absolute;
    bottom:12px;
    left:50%;
    transform:translateX(-50%);
    font-family:sans-serif;
    font-size:13px;
    color:rgba(200,220,255,0.85);
    letter-spacing:0.08em;
    white-space:nowrap;
    pointer-events:none;
  }}
  @keyframes fall {{
    0%   {{ transform:translateY(-10px) rotate({15}deg); opacity:0; }}
    10%  {{ opacity:1; }}
    90%  {{ opacity:1; }}
    100% {{ transform:translateY({height+20}px) rotate({15}deg); opacity:0; }}
  }}
  @keyframes drift {{
    0%   {{ transform:translateX(0); }}
    100% {{ transform:translateX({width+200}px); }}
  }}
  @keyframes streak {{
    0%   {{ transform:translateX(0); opacity:0; }}
    20%  {{ opacity:1; }}
    100% {{ transform:translateX({width+150}px); opacity:0; }}
  }}
  @keyframes fog_move {{
    0%   {{ transform:translateX(-5%); }}
    100% {{ transform:translateX(8%); }}
  }}
  @keyframes twinkle {{
    0%   {{ opacity:0.2; transform:scale(0.8); }}
    100% {{ opacity:1;   transform:scale(1.4); }}
  }}
  @keyframes lightning {{
    0%,88%,92%,100% {{ opacity:0; }}
    89%,91%         {{ opacity:1; }}
  }}
</style>
</head>
<body>
<div class="box">
  {particles}
  <div class="lbl">{label}</div>
</div>
</body>
</html>"""

    components.html(html, height=height + 4, scrolling=False)
