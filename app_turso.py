import streamlit as st
import pandas as pd
import libsql
import re
import os
import base64
import io
import unicodedata
from difflib import get_close_matches as _gcm, SequenceMatcher as _SM
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date, timezone
from PIL import Image
from db_mapa import (
    ensure_mapa_tables,
    get_paletes_rack,
    get_todos_paletes,
    get_produtos_mapa,
    buscar_produto_no_mapa,
    buscar_produto_todas_ruas,
    get_ocupacao_geral,
    upsert_palete,
    delete_palete,
    mover_palete,
    add_produto_mapa,
    delete_produto_mapa,
)

# Fuso horário de Brasília (UTC-3) — usado em todo o sistema
_BRT = timezone(timedelta(hours=-3))

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CAMDA Estoque Mestre",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── Weather Widget ───────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_weather_quirinopolis():
    try:
        import urllib.request, json
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=-18.45&longitude=-50.45"
            "&current=temperature_2m,weathercode"
            "&timezone=America%2FSao_Paulo"
        )
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.loads(r.read())
        temp = round(data["current"]["temperature_2m"])
        code = data["current"]["weathercode"]
        if code == 0:              emoji, desc = "☀️", "Céu limpo"
        elif code in (1, 2):       emoji, desc = "🌤️", "Poucas nuvens"
        elif code == 3:            emoji, desc = "☁️", "Nublado"
        elif code in (45, 48):     emoji, desc = "🌫️", "Névoa"
        elif code in (51,53,55):   emoji, desc = "🌦️", "Chuvisco"
        elif code in (61,63,65):   emoji, desc = "🌧️", "Chuva"
        elif code in (80,81,82):   emoji, desc = "🌧️", "Pancadas"
        elif code in (95,96,99):   emoji, desc = "⛈️", "Tempestade"
        else:                      emoji, desc = "🌡️", ""
        return temp, emoji, desc
    except Exception:
        return None, "🌡️", ""


@st.cache_data(ttl=1800)
def get_weather_forecast_quirinopolis():
    """Retorna previsão completa de 6 dias para Quirinópolis."""
    try:
        import urllib.request, json
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=-18.45&longitude=-50.45"
            "&current=temperature_2m,weathercode,relative_humidity_2m,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min,weathercode"
            ",sunrise,sunset,precipitation_probability_max"
            "&timezone=America%2FSao_Paulo"
            "&forecast_days=6"
        )
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── Session State ────────────────────────────────────────────────────────────
if "processed_file" not in st.session_state:
    st.session_state.processed_file = None
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "login_error" not in st.session_state:
    st.session_state.login_error = False
if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False

# ── Weather gradient helper (usada na tela de login e no dashboard) ───────────
def _wcode_bg_gradient(code, alpha=1.0):
    if code is None:
        r = "30,60,114"; g = "42,82,152"
    elif int(code) == 0:
        r = "15,32,39"; g = "44,83,100"
    elif int(code) in (1, 2):
        r = "21,101,192"; g = "94,146,200"
    elif int(code) == 3:
        r = "44,62,80"; g = "74,98,116"
    elif int(code) in (45, 48):
        r = "74,85,104"; g = "143,163,177"
    elif int(code) in (51,53,55,61,63,65,80,81,82):
        r = "13,27,62"; g = "30,87,153"
    elif int(code) in (95,96,99):
        r = "15,12,41"; g = "36,36,62"
    elif int(code) in (71,73,75,77):
        r = "44,62,80"; g = "107,143,166"
    else:
        r = "30,60,114"; g = "42,82,152"
    if alpha < 1.0:
        return f"linear-gradient(160deg,rgba({r},{alpha}) 0%,rgba({g},{alpha}) 100%)"
    return f"linear-gradient(160deg,rgb({r}) 0%,rgb({g}) 100%)"

# ── Login Screen ─────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    _DIAS_PT_FULL = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    _DIAS_PT      = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    def _wcode_emoji_login(code):
        if code is None: return "🌡️"
        code = int(code)
        if code == 0:               return "☀️"
        elif code in (1, 2):        return "🌤️"
        elif code == 3:             return "☁️"
        elif code in (45, 48):      return "🌫️"
        elif code in (51,53,55):    return "🌦️"
        elif code in (61,63,65,80,81,82): return "🌧️"
        elif code in (95,96,99):    return "⛈️"
        elif code in (71,73,75,77): return "❄️"
        else:                       return "🌡️"

    def _wcode_desc_login(code):
        if code is None: return ""
        code = int(code)
        if code == 0:               return "Céu limpo"
        elif code in (1, 2):        return "Poucas nuvens"
        elif code == 3:             return "Nublado"
        elif code in (45, 48):      return "Névoa"
        elif code in (51,53,55):    return "Chuvisco"
        elif code in (61,63,65):    return "Chuva"
        elif code in (80,81,82):    return "Pancadas"
        elif code in (95,96,99):    return "Tempestade"
        else:                       return ""


    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700;900&display=swap');
    .stApp {
        background:
            linear-gradient(160deg,rgba(10,15,26,0.55) 0%,rgba(10,15,26,0.45) 100%),
            url('https://raw.githubusercontent.com/LeoLira1/camda-estoque/main/Cerrado.jpg')
            center center / cover no-repeat fixed;
        font-family:'Outfit',sans-serif;
    }
    #MainMenu,footer,header{visibility:hidden;}
    .block-container{padding:1.5rem 1rem !important;max-width:100% !important;}
    .stTextInput>div>div>input{
        background:rgba(255,255,255,0.1) !important;
        border:1px solid rgba(255,255,255,0.22) !important;
        border-radius:30px !important;
        color:white !important;
        padding:12px 20px !important;
        font-size:1rem !important;
        text-align:center;
        font-family:'Outfit',sans-serif !important;
        letter-spacing:1px;
    }
    .stTextInput>div>div>input::placeholder{color:rgba(255,255,255,0.4) !important;}
    .stTextInput label{display:none !important;}
    .stForm{border:none !important;padding:0 !important;}
    .stFormSubmitButton>button{
        background:rgba(255,255,255,0.12) !important;
        border:1px solid rgba(255,255,255,0.28) !important;
        border-radius:30px !important;
        color:white !important;
        font-size:0.95rem !important;
        font-weight:600 !important;
        letter-spacing:1.5px !important;
        padding:10px !important;
        font-family:'Outfit',sans-serif !important;
        transition:background .2s !important;
        width:100%;
    }
    .stFormSubmitButton>button:hover{background:rgba(255,255,255,0.22) !important;}
    @media(max-width:640px){.block-container{padding:0.8rem 0.5rem !important;}}
    </style>
    """, unsafe_allow_html=True)

    wd = get_weather_forecast_quirinopolis()
    _now = datetime.now(tz=timezone(timedelta(hours=-3)))
    _hora = _now.strftime("%H:%M")
    _dia_nome = _DIAS_PT_FULL[_now.weekday()]
    _data_fmt  = _now.strftime("%d/%m/%Y")

    if wd:
        cur   = wd["current"]
        daily = wd["daily"]

        temp_cur  = round(cur["temperature_2m"])
        wcode_cur = int(cur["weathercode"])
        humid     = round(cur.get("relative_humidity_2m", 0))
        vento     = round(cur.get("wind_speed_10m", 0))
        emoji_cur = _wcode_emoji_login(wcode_cur)
        desc_cur  = _wcode_desc_login(wcode_cur)

        sunrise_raw = daily["sunrise"][0]
        sunset_raw  = daily["sunset"][0]
        sunrise_t   = sunrise_raw.split("T")[1][:5] if "T" in sunrise_raw else sunrise_raw
        sunset_t    = sunset_raw.split("T")[1][:5]  if "T" in sunset_raw  else sunset_raw
        try:
            sr_h, sr_m = map(int, sunrise_t.split(":"))
            ss_h, ss_m = map(int, sunset_t.split(":"))
            dur_min = (ss_h * 60 + ss_m) - (sr_h * 60 + sr_m)
            dur_str = f"{dur_min // 60}h {dur_min % 60}m"
        except Exception:
            dur_str = ""

        chuva_pct = int(daily["precipitation_probability_max"][0] or 0)

        dias_cards_html = ""
        for i in range(6):
            date_str = daily["time"][i]
            dt_d = datetime.strptime(date_str, "%Y-%m-%d")
            nome_d = "Hoje" if i == 0 else _DIAS_PT[dt_d.weekday()]
            em_d   = _wcode_emoji_login(daily["weathercode"][i])
            tmax   = round(daily["temperature_2m_max"][i])
            tmin   = round(daily["temperature_2m_min"][i])
            bg_d   = "rgba(255,255,255,0.18)" if i == 0 else "rgba(0,0,0,0.18)"
            bd_d   = "border:1px solid rgba(255,255,255,0.28);" if i == 0 else "border:1px solid rgba(255,255,255,0.06);"
            fw_d   = "700" if i == 0 else "400"
            dias_cards_html += (
                f'<div style="flex:1;background:{bg_d};border-radius:14px;padding:9px 2px;'
                f'text-align:center;{bd_d}">'
                f'<div style="font-size:0.55rem;color:rgba(255,255,255,0.6);'
                f'margin-bottom:4px;font-weight:{fw_d};text-transform:uppercase;letter-spacing:0.3px;">{nome_d}</div>'
                f'<div style="font-size:1.1rem;margin:3px 0;'
                f'filter:drop-shadow(0 2px 6px rgba(255,255,255,0.2));">{em_d}</div>'
                f'<div style="font-size:0.78rem;font-weight:700;color:#fff;margin-top:2px;">{tmax}°</div>'
                f'<div style="font-size:0.58rem;color:rgba(255,255,255,0.4);">{tmin}°</div>'
                f'</div>'
            )

        _bg_grad = _wcode_bg_gradient(wcode_cur)
        card_weather = f"""
<div style="
    background:{_bg_grad};
    border-radius:28px;padding:26px 20px 18px;
    color:#fff;font-family:'Outfit',sans-serif;
    box-shadow:0 24px 64px rgba(0,0,0,0.55),inset 0 1px 0 rgba(255,255,255,0.12);
    position:relative;overflow:hidden;margin-bottom:12px;">
  <div style="position:absolute;top:-55px;right:-55px;width:210px;height:210px;
              border-radius:50%;background:rgba(255,255,255,0.055);pointer-events:none;"></div>
  <div style="position:absolute;bottom:-75px;left:-65px;width:260px;height:260px;
              border-radius:50%;background:rgba(255,255,255,0.035);pointer-events:none;"></div>
  <div style="font-size:0.75rem;color:rgba(255,255,255,0.55);letter-spacing:0.5px;
              margin-bottom:20px;position:relative;">
    {_dia_nome} &nbsp;·&nbsp; {_data_fmt} &nbsp;·&nbsp; {_hora}
  </div>
  <div style="text-align:center;padding:4px 0 18px;position:relative;">
    <div style="font-size:5rem;line-height:1;margin-bottom:10px;
                filter:drop-shadow(0 6px 16px rgba(255,255,255,0.25));">{emoji_cur}</div>
    <div style="font-size:4.2rem;font-weight:700;line-height:1;letter-spacing:-2px;
                text-shadow:0 4px 24px rgba(0,0,0,0.3);">{temp_cur}°</div>
    <div style="font-size:1rem;font-weight:500;color:rgba(255,255,255,0.85);margin-top:10px;">{desc_cur}</div>
    <div style="font-size:0.75rem;color:rgba(255,255,255,0.5);margin-top:5px;">📍 Quirinópolis, GO</div>
  </div>
  <div style="display:flex;background:rgba(0,0,0,0.22);border-radius:18px;
              padding:14px 6px;margin-bottom:12px;position:relative;">
    <div style="flex:1;text-align:center;border-right:1px solid rgba(255,255,255,0.1);">
      <div style="font-size:1.3rem;margin-bottom:3px;">💧</div>
      <div style="font-size:1.05rem;font-weight:700;">{humid}%</div>
      <div style="font-size:0.6rem;color:rgba(255,255,255,0.48);margin-top:2px;">Umidade</div>
    </div>
    <div style="flex:1;text-align:center;border-right:1px solid rgba(255,255,255,0.1);">
      <div style="font-size:1.3rem;margin-bottom:3px;">💨</div>
      <div style="font-size:1.05rem;font-weight:700;">{vento} km/h</div>
      <div style="font-size:0.6rem;color:rgba(255,255,255,0.48);margin-top:2px;">Vento</div>
    </div>
    <div style="flex:1;text-align:center;">
      <div style="font-size:1.3rem;margin-bottom:3px;">🌧️</div>
      <div style="font-size:1.05rem;font-weight:700;">{chuva_pct}%</div>
      <div style="font-size:0.6rem;color:rgba(255,255,255,0.48);margin-top:2px;">Chuva</div>
    </div>
  </div>
  <div style="background:rgba(0,0,0,0.18);border-radius:30px;padding:7px 16px;
              display:flex;justify-content:space-between;align-items:center;
              font-size:0.7rem;margin-bottom:14px;position:relative;">
    <span>🌅 {sunrise_t}</span>
    <span style="color:rgba(255,255,255,0.3);font-size:0.58rem;">── {dur_str} ──</span>
    <span>🌇 {sunset_t}</span>
  </div>
  <div style="display:flex;gap:4px;position:relative;">{dias_cards_html}</div>
</div>"""
    else:
        card_weather = f"""
<div style="
    background:linear-gradient(160deg,#1e3c72 0%,#2a5298 100%);
    border-radius:28px;padding:32px 20px;
    color:#fff;font-family:'Outfit',sans-serif;
    box-shadow:0 24px 64px rgba(0,0,0,0.5);
    text-align:center;margin-bottom:12px;">
  <div style="font-size:0.75rem;color:rgba(255,255,255,0.5);margin-bottom:20px;">
    {_dia_nome} &nbsp;·&nbsp; {_data_fmt} &nbsp;·&nbsp; {_hora}</div>
  <div style="font-size:3.5rem;margin:14px 0;
              filter:drop-shadow(0 4px 12px rgba(255,255,255,0.2));">🌡️</div>
  <div style="font-size:0.9rem;color:rgba(255,255,255,0.5);">Clima indisponível</div>
  <div style="font-size:0.72rem;color:rgba(255,255,255,0.3);margin-top:6px;">📍 Quirinópolis, GO</div>
</div>"""

    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown(card_weather, unsafe_allow_html=True)
        with st.form("form_login"):
            senha_input = st.text_input(
                "senha", type="password",
                placeholder="🔑 Senha de acesso",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("ENTRAR", use_container_width=True)
            if submitted:
                if senha_input == "força":
                    st.session_state.authenticated = True
                    st.session_state.login_error = False
                    st.rerun()
                else:
                    st.session_state.login_error = True
                    st.rerun()

        if st.session_state.login_error:
            st.markdown(
                '<div style="background:rgba(255,71,87,0.15);border:1px solid rgba(255,71,87,0.3);'
                'border-radius:12px;padding:8px 16px;color:#ff6b7a;text-align:center;'
                'font-size:0.85rem;margin-top:6px;">❌ Senha incorreta</div>',
                unsafe_allow_html=True
            )

    st.stop()


# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;500;700;900&family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');
    .stApp { background: #0a0f1a; color: #e0e6ed; font-family: 'DM Sans', 'Outfit', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 0.5rem 0.8rem !important; max-width: 100% !important; }
    .main-title {
        font-family: 'Outfit', sans-serif; font-weight: 900; font-size: 1.6rem;
        background: linear-gradient(135deg, #00d68f, #00b887);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin: 0.3rem 0;
    }
    .sub-title {
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
        color: #4a5568; text-align: center; margin-bottom: 0.5rem;
    }
    .sync-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.55rem;
        color: #3b82f6; text-align: center; margin-bottom: 0.5rem; opacity: 0.8;
    }
    .stat-row { display: flex; gap: 6px; margin-bottom: 0.5rem; }
    .stat-card {
        flex: 1; background: linear-gradient(135deg, #111827, #1a2332);
        border: 1px solid #1e293b; border-radius: 10px;
        padding: 8px 10px; text-align: center;
    }
    .stat-value {
        font-family: 'JetBrains Mono', monospace; font-size: 1.15rem;
        font-weight: 700; color: #00d68f;
    }
    .stat-value.red { color: #ff4757; }
    .stat-value.amber { color: #ffa502; }
    .stat-value.purple { color: #a55eea; }
    .stat-value.blue { color: #3b82f6; }
    .stat-label {
        font-size: 0.6rem; color: #64748b;
        text-transform: uppercase; letter-spacing: 1px;
    }
    /* ── Treemap tiles ─────────────────────────────────────────────────── */
    .tm-wrap { display: flex; flex-wrap: wrap; gap: 2px; }
    .tm-tile {
        width: 110px; height: 60px;
        border-radius: 4px; padding: 4px; margin: 2px;
        display: flex; flex-direction: column;
        justify-content: center; align-items: center;
        overflow: visible; box-sizing: border-box;
        position: relative; cursor: pointer; outline: none;
    }
    .tm-name {
        font-size: 0.55rem; font-weight: 700; text-align: center; width: 100%;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .tm-info {
        font-size: 0.65rem; opacity: 0.9;
        font-family: 'JetBrains Mono', monospace;
        font-weight: bold; margin-top: 2px;
    }
    .tm-av { font-size: 0.5rem; font-weight: 700; margin-top: 2px; }
    .tm-tile[data-diff]::after {
        content: attr(data-diff);
        position: absolute; bottom: 2px; right: 3px;
        font-size: 0.42rem; font-weight: 700; opacity: 0.8;
    }
    /* ── Streamlit tabs: sempre scrollável ─────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        flex-wrap: nowrap !important;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px !important; padding: 4px 4px 0 4px !important; }
    .stTabs [data-baseweb="tab"] {
        color: #7bafd4 !important;
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        padding: 6px 14px !important;
        font-weight: 500 !important;
        transition: background 0.2s, border-color 0.2s !important;
        margin-bottom: 0 !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #cde8f8 !important;
        background: rgba(123,175,212,0.16) !important;
        border: 1px solid rgba(123,175,212,0.35) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }
    /* ── Mobile (≤640px) ───────────────────────────────────────────────── */
    @media (max-width: 640px) {
        .block-container { padding: 0.3rem 0.3rem !important; }
        .main-title { font-size: 1.2rem; }
        .stat-row { flex-wrap: wrap; gap: 4px; }
        .stat-card { flex: 1 1 calc(33% - 4px); min-width: 0; padding: 6px 4px; }
        .stat-value { font-size: 0.85rem; }
        .stat-label { font-size: 0.48rem; letter-spacing: 0.5px; }
        .stTabs [data-baseweb="tab"] {
            padding: 5px 8px !important;
            font-size: 0.65rem !important;
            border-radius: 6px !important;
        }
        .tm-tile { width: calc(33.33% - 6px); min-width: 90px; height: 58px; }
    }
    /* ── Syne em números grandes ──────────────────────────────────────── */
    .stat-value {
        font-family: 'Syne', 'JetBrains Mono', monospace !important;
    }
    /* ── cardPop — entrada cascata nos tiles do Mapa Estoque ─────────── */
    @keyframes cardPop {
        from { opacity: 0; transform: scale(0.85) translateY(10px); }
        to   { opacity: 1; transform: scale(1) translateY(0); }
    }
    .tm-tile {
        animation: cardPop 0.4s ease both;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .tm-tile:hover {
        transform: translateY(-4px) scale(1.02) !important;
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        z-index: 1;
    }
    .tm-cod {
        display: none;
        font-size: 0.5rem; opacity: 0.75;
        margin-top: 2px; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap;
    }
    .tm-tile:hover .tm-cod { display: block; }
    /* ── Popup nome completo ao clicar/focar no tile (CSS puro, sem JS) ── */
    .tm-tile:focus { z-index: 100; box-shadow: 0 0 0 2px rgba(255,255,255,0.6), 0 8px 30px rgba(0,0,0,0.5) !important; }
    .tm-popup {
        display: none;
        position: absolute;
        top: calc(100% + 8px);
        left: 50%; transform: translateX(-50%);
        background: rgba(15,23,42,0.97);
        color: #e2e8f0;
        padding: 8px 14px;
        border-radius: 10px;
        font-size: 0.8rem; font-weight: 600;
        line-height: 1.4; text-align: center;
        white-space: normal;
        min-width: 180px; max-width: 260px;
        z-index: 9999;
        box-shadow: 0 6px 24px rgba(0,0,0,0.6);
        border: 1px solid rgba(100,116,139,0.5);
        pointer-events: none;
    }
    .tm-popup-code {
        font-size: 0.62rem; color: #94a3b8;
        font-family: 'JetBrains Mono', monospace;
        margin-bottom: 4px; letter-spacing: 0.5px;
    }
    .tm-tile:focus .tm-popup { display: block; }
    .tm-tile:nth-child(1)  { animation-delay: 0.03s; }
    .tm-tile:nth-child(2)  { animation-delay: 0.06s; }
    .tm-tile:nth-child(3)  { animation-delay: 0.09s; }
    .tm-tile:nth-child(4)  { animation-delay: 0.12s; }
    .tm-tile:nth-child(5)  { animation-delay: 0.15s; }
    .tm-tile:nth-child(6)  { animation-delay: 0.18s; }
    .tm-tile:nth-child(7)  { animation-delay: 0.21s; }
    .tm-tile:nth-child(8)  { animation-delay: 0.24s; }
    .tm-tile:nth-child(9)  { animation-delay: 0.27s; }
    .tm-tile:nth-child(10) { animation-delay: 0.30s; }
    .tm-tile:nth-child(11) { animation-delay: 0.33s; }
    .tm-tile:nth-child(12) { animation-delay: 0.36s; }
    .tm-tile:nth-child(13) { animation-delay: 0.39s; }
    .tm-tile:nth-child(14) { animation-delay: 0.42s; }
    .tm-tile:nth-child(15) { animation-delay: 0.45s; }
    .tm-tile:nth-child(16) { animation-delay: 0.48s; }
    .tm-tile:nth-child(17) { animation-delay: 0.51s; }
    .tm-tile:nth-child(18) { animation-delay: 0.54s; }
    .tm-tile:nth-child(19) { animation-delay: 0.57s; }
    .tm-tile:nth-child(20) { animation-delay: 0.60s; }
    /* ── Transição suave entre abas ───────────────────────────────────── */
    @keyframes tabFadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    [data-baseweb="tab-panel"] {
        animation: tabFadeIn 0.3s ease both;
    }
    /* ── Search input glow ao focar ───────────────────────────────────── */
    .stTextInput input:focus {
        border-color: rgba(45,255,122,0.5) !important;
        box-shadow: 0 0 0 3px rgba(45,255,122,0.1) !important;
        transition: all 0.2s ease;
    }
    /* ── Hover nos cards stat-card ────────────────────────────────────── */
    .stat-card {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    /* ── Hover nos itens Repor na Loja ────────────────────────────────── */
    .repor-item {
        transition: background 0.2s ease, transform 0.15s ease;
    }
    .repor-item:hover {
        background: #1a2438 !important;
        transform: translateX(4px);
    }
    /* ── Glow pulsante no header banner ──────────────────────────────── */
    @keyframes glowPulse {
        0%, 100% { box-shadow: 0 0 20px rgba(45,255,122,0.15); }
        50%       { box-shadow: 0 0 40px rgba(45,255,122,0.40); }
    }
    .camda-header {
        animation: glowPulse 3s ease-in-out infinite;
    }
    /* ── Respeitar prefers-reduced-motion ─────────────────────────────── */
    @media (prefers-reduced-motion: reduce) {
        * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
    }
    /* ── Fix mobile: impede que toque em gráfico Plotly abra teclado ───── */
    .stPlotlyChart input,
    .js-plotly-plot input,
    .plotly input {
        display: none !important;
        pointer-events: none !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Injetar JS: contadores animados nos KPI metrics ──────────────────────────
st.markdown("""
<script>
(function() {
  function animateCounters() {
    var metrics = document.querySelectorAll('[data-testid="metric-value"]');
    metrics.forEach(function(el) {
      var raw = el.textContent.trim();
      var num = parseInt(raw.replace(/\\D/g, ''), 10);
      if (isNaN(num) || num === 0) return;
      var duration = 1200;
      var start = performance.now();
      var suffix = raw.replace(/[\\d,\\.]/g, '').trim();
      function step(now) {
        var progress = Math.min((now - start) / duration, 1);
        var ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        el.textContent = Math.round(ease * num) + (suffix ? ' ' + suffix : '');
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = raw;
      }
      requestAnimationFrame(step);
    });
  }
  var observer = new MutationObserver(function() {
    if (document.querySelector('[data-testid="metric-value"]')) {
      observer.disconnect();
      animateCounters();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
</script>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# REGEX PRÉ-COMPILADO (compila 1x no import, não 1x por produto)
# ══════════════════════════════════════════════════════════════════════════════
_RE_FALTA = re.compile(r"falt(?:a|ando|am|ou|aram|\.?)(?:\s+(?:de|do|da))?\s+(\d+)\s*(.*)")
_RE_FALTA_SHORT = re.compile(r"^f\.?\s+(\d+)\s*(.*)")
_RE_SOBRA = re.compile(r"(?:sobr(?:a|ando|am|ou|aram|\.?)|pass(?:a|ando|aram|ou|\.?))\s+(\d+)\s*(.*)")
_RE_SOBRA_SHORT = re.compile(r"^s\.?\s+(\d+)\s*(.*)")
_RE_FALTA_MID = re.compile(r"falt\w*\s+(?:de\s+)?(\d+)")
_RE_SOBRA_MID = re.compile(r"(?:sobr|pass)\w*\s+(\d+)")
_RE_ONLY_NUMBER = re.compile(r"^\d+([.,]\d+)?$")
_RE_COD_PROD = re.compile(r"^([A-Za-z]{0,2}\d+)\s*-\s*(.+)$")
_RE_SPACES = re.compile(r"\s+")
_RE_DIGITS = re.compile(r"\d+")
_RE_ALPHA = re.compile(r"[a-zA-Z]")
_RE_NON_ALNUM = re.compile(r"[^A-Z0-9]")
_RE_PA_SIZE = re.compile(
    r'\b\d+[\.,]?\d*\s*'
    r'(?:L|ML|KG|G|GR|SC|T|MG|WG|WP|SL|EC|CS|GD|OD|SE|FS|EW|ME|TG|WDG|ZC|DC|ULV)\b',
    re.IGNORECASE,
)


def _pacc(s: str) -> str:
    """Remove diacríticos: Ó→O, Ã→A, Ç→C, etc."""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _pnorm(s: str) -> str:
    """Upper + strip + sem acentos."""
    return _pacc(s.strip().upper())


def _pstrip(s: str) -> str:
    """Remove sufixos de tamanho/formulação e espaços extras."""
    return re.sub(r'\s+', ' ', _RE_PA_SIZE.sub('', s)).strip()


def _build_pa_lookup(mapa: dict) -> tuple:
    """Constrói índices para busca multi-etapa de princípio ativo por nome de produto."""
    cat_n = {_pnorm(k): v for k, v in mapa.items()}
    cat_ns = {_pstrip(_pnorm(k)): v for k, v in mapa.items()}
    cat_n_keys = sorted(cat_n.keys(), key=len, reverse=True)
    cat_ns_keys = sorted(cat_ns.keys(), key=len, reverse=True)
    return mapa, cat_n, cat_ns, cat_n_keys, cat_ns_keys


def _lookup_pa_from_index(nome: str, mapa: dict, cat_n: dict, cat_ns: dict,
                          cat_n_keys: list, cat_ns_keys: list) -> str:
    """Retorna o princípio ativo para um nome de produto usando match multi-etapa."""
    chave = nome.strip().upper()
    chave_n = _pnorm(chave)
    chave_s = _pstrip(chave_n)
    if chave in mapa:
        return mapa[chave]
    if chave_n in cat_n:
        return cat_n[chave_n]
    for ck in cat_n_keys:
        if ck in chave_n:
            return cat_n[ck]
    if chave_s in cat_ns:
        return cat_ns[chave_s]
    for ck in cat_ns_keys:
        if ck in chave_s:
            return cat_ns[ck]
    if len(chave_s) >= 5:
        for ck in cat_n_keys:
            if chave_n in ck:
                return cat_n[ck]
        for ck in cat_ns_keys:
            if chave_s in ck:
                return cat_ns[ck]
    m = _gcm(chave_s, list(cat_ns.keys()), n=1, cutoff=0.72)
    if m:
        return cat_ns[m[0]]
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE — conexão + init de tabelas UMA VEZ SÓ
# ══════════════════════════════════════════════════════════════════════════════

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.environ.get(key, "")


TURSO_DATABASE_URL = _get_secret("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = _get_secret("TURSO_AUTH_TOKEN")
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camda_local.db")
_using_cloud = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

# Senha para liberar a área de edição do estoque (upload, ajuste, exclusão)
# Configure via st.secrets["CAMDA_EDIT_PASSWORD"] ou variável de ambiente CAMDA_EDIT_PASSWORD
EDIT_PASSWORD = _get_secret("CAMDA_EDIT_PASSWORD") or "camda@edit"


@st.cache_resource
def _get_connection():
    """Cria conexão UMA VEZ e já inicializa tabelas + migrações."""
    if _using_cloud:
        conn = libsql.connect(
            LOCAL_DB_PATH,
            sync_url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN,
        )
        conn.sync()
    else:
        conn = libsql.connect(LOCAL_DB_PATH)

    # ── Criar tabelas (roda 1x, não a cada get_db()) ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS estoque_mestre (
            codigo TEXT PRIMARY KEY,
            produto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            qtd_sistema INTEGER NOT NULL DEFAULT 0,
            qtd_fisica INTEGER DEFAULT 0,
            diferenca INTEGER DEFAULT 0,
            nota TEXT DEFAULT '',
            status TEXT DEFAULT 'ok',
            ultima_contagem TEXT DEFAULT '',
            criado_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historico_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL,
            arquivo TEXT DEFAULT '',
            total_produtos_lote INTEGER DEFAULT 0,
            novos INTEGER DEFAULT 0,
            atualizados INTEGER DEFAULT 0,
            divergentes INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS principios_ativos (
            produto TEXT NOT NULL,
            principio_ativo TEXT NOT NULL,
            categoria TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reposicao_loja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            qtd_vendida INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            reposto INTEGER DEFAULT 0,
            reposto_em TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vendas_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            grupo TEXT NOT NULL,
            qtd_vendida INTEGER NOT NULL DEFAULT 0,
            qtd_estoque INTEGER NOT NULL DEFAULT 0,
            data_upload TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pendencias_entrega (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            foto_base64 TEXT NOT NULL,
            data_registro TEXT NOT NULL,
            observacao TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS avarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            qtd_avariada INTEGER NOT NULL DEFAULT 1,
            motivo TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'aberto',
            registrado_em TEXT NOT NULL,
            resolvido_em TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contagem_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER NOT NULL DEFAULT 0,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            qtd_estoque INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendente',
            motivo TEXT DEFAULT '',
            qtd_divergencia INTEGER DEFAULT 0,
            registrado_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS validade_lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filial TEXT DEFAULT '',
            grupo TEXT NOT NULL,
            produto TEXT NOT NULL,
            lote TEXT NOT NULL,
            fabricacao TEXT DEFAULT '',
            vencimento TEXT NOT NULL,
            quantidade INTEGER DEFAULT 0,
            valor REAL DEFAULT 0,
            uploaded_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alertas_disparados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            ref_chave TEXT NOT NULL,
            data_disparo TEXT NOT NULL,
            UNIQUE(tipo, ref_chave)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos_manuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            produto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 1,
            motivo TEXT DEFAULT '',
            registrado_em TEXT NOT NULL
        )
    """)
    conn.commit()

    # ── Migrações (roda 1x) ──
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(reposicao_loja)").fetchall()}
        for col, definition in [
            ("qtd_vendida", "INTEGER NOT NULL DEFAULT 0"),
            ("reposto", "INTEGER DEFAULT 0"),
            ("reposto_em", "TEXT DEFAULT ''"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE reposicao_loja ADD COLUMN {col} {definition}")
        conn.commit()
    except Exception:
        pass

    try:
        pend_cols = {row[1] for row in conn.execute("PRAGMA table_info(pendencias_entrega)").fetchall()}
        if "observacao" not in pend_cols:
            conn.execute("ALTER TABLE pendencias_entrega ADD COLUMN observacao TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    # migração alertas_disparados já é criada no CREATE TABLE IF NOT EXISTS acima
    # mas garante que a constraint UNIQUE existe para DBs antigos sem ela
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alertas_disparados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                ref_chave TEXT NOT NULL,
                data_disparo TEXT NOT NULL,
                UNIQUE(tipo, ref_chave)
            )
        """)
        conn.commit()
    except Exception:
        pass

    # ── Tabelas do Mapa Visual ──
    try:
        ensure_mapa_tables(conn)
    except Exception:
        pass

    return conn


def get_db():
    """Retorna conexão pronta (tabelas já criadas no cache)."""
    conn = _get_connection()
    if _using_cloud and not st.session_state.get("_synced"):
        try:
            conn.sync()
            st.session_state["_synced"] = True
        except Exception:
            pass
    return conn


def sync_db():
    """Sync com Turso (chamar UMA VEZ após todas as escritas)."""
    if _using_cloud:
        try:
            _get_connection().sync()
        except Exception as e:
            st.warning(f"⚠️ Sync falhou: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LANÇAMENTOS MANUAIS — funções CRUD
# ══════════════════════════════════════════════════════════════════════════════

def inserir_lancamento(codigo: str, produto: str, categoria: str,
                       tipo: str, quantidade: int, motivo: str) -> bool:
    """Insere um lançamento manual e sincroniza. Retorna True se ok."""
    try:
        conn = get_db()
        agora = datetime.now(tz=_BRT).isoformat()
        conn.execute(
            """INSERT INTO lancamentos_manuais
               (codigo, produto, categoria, tipo, quantidade, motivo, registrado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (codigo, produto, categoria, tipo, int(quantidade), motivo.strip(), agora),
        )
        conn.execute("COMMIT")
        sync_db()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar lançamento: {e}")
        return False


def listar_lancamentos(limit: int = 200) -> pd.DataFrame:
    """Retorna os últimos lançamentos manuais em ordem decrescente."""
    try:
        conn = get_db()
        rows = conn.execute(
            """SELECT id, codigo, produto, categoria, tipo, quantidade, motivo, registrado_em
               FROM lancamentos_manuais
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        cols = ["id", "codigo", "produto", "categoria", "tipo", "quantidade", "motivo", "registrado_em"]
        return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    except Exception:
        return pd.DataFrame(columns=["id", "codigo", "produto", "categoria", "tipo", "quantidade", "motivo", "registrado_em"])


def excluir_lancamento(lancamento_id: int) -> bool:
    """Remove um lançamento manual pelo id."""
    try:
        conn = get_db()
        conn.execute("DELETE FROM lancamentos_manuais WHERE id = ?", (lancamento_id,))
        conn.execute("COMMIT")
        sync_db()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao excluir lançamento: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# PENDÊNCIAS DE ENTREGA — funções CRUD
# ══════════════════════════════════════════════════════════════════════════════

def inserir_pendencia(foto_bytes: bytes, observacao: str = ""):
    img = Image.open(io.BytesIO(foto_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70, optimize=True)
    foto_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    data_hoje = datetime.now(tz=_BRT).date().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO pendencias_entrega (foto_base64, data_registro, observacao) VALUES (?, ?, ?)",
        (foto_b64, data_hoje, observacao.strip())
    )
    conn.commit()
    sync_db()


def listar_pendencias() -> list:
    try:
        rows = get_db().execute(
            "SELECT id, foto_base64, data_registro, observacao FROM pendencias_entrega ORDER BY data_registro ASC"
        ).fetchall()
        return rows
    except Exception:
        return []


def deletar_pendencia(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM pendencias_entrega WHERE id = ?", (pid,))
    conn.commit()
    sync_db()


def _dias_desde(data_str: str) -> int:
    try:
        return (datetime.now(tz=_BRT).date() - date.fromisoformat(data_str)).days
    except Exception:
        return 0


def checar_e_registrar_alertas() -> dict:
    """
    Verifica condições de alerta, registra primeira detecção no banco e
    retorna alertas ainda dentro da janela de 2 dias de exibição.
    """
    from datetime import timedelta
    hoje = datetime.now(tz=_BRT).date()
    conn = get_db()
    result = {"validade_30d": [], "pendencia_5d": []}
    houve_escrita = False

    # ── Lotes com validade ≤ 30 dias ──────────────────────────────────────
    try:
        lotes = conn.execute(
            "SELECT produto, lote, vencimento FROM validade_lotes"
        ).fetchall()
        for produto, lote, venc_str in lotes:
            try:
                venc = date.fromisoformat(str(venc_str)[:10])
                dias_rest = (venc - hoje).days
                if 0 <= dias_rest <= 30:
                    chave = f"{produto}|{lote}"
                    rec = conn.execute(
                        "SELECT data_disparo FROM alertas_disparados WHERE tipo=? AND ref_chave=?",
                        ("validade_30d", chave),
                    ).fetchone()
                    if rec is None:
                        conn.execute(
                            "INSERT OR IGNORE INTO alertas_disparados (tipo, ref_chave, data_disparo) VALUES (?,?,?)",
                            ("validade_30d", chave, hoje.isoformat()),
                        )
                        houve_escrita = True
                        data_disparo = hoje
                    else:
                        data_disparo = date.fromisoformat(rec[0])
                    if (hoje - data_disparo).days <= 1:
                        nome_curto = produto.split(" - ")[-1][:40] if " - " in produto else produto[:40]
                        result["validade_30d"].append({
                            "produto": nome_curto,
                            "lote": lote,
                            "dias_restantes": dias_rest,
                        })
            except Exception:
                continue
    except Exception:
        pass

    # ── Pendências com mais de 5 dias ─────────────────────────────────────
    try:
        pendencias = listar_pendencias()
        for pid, _, data_reg, _obs in pendencias:
            dias_pend = _dias_desde(data_reg)
            if dias_pend > 5:
                chave = str(pid)
                rec = conn.execute(
                    "SELECT data_disparo FROM alertas_disparados WHERE tipo=? AND ref_chave=?",
                    ("pendencia_5d", chave),
                ).fetchone()
                if rec is None:
                    conn.execute(
                        "INSERT OR IGNORE INTO alertas_disparados (tipo, ref_chave, data_disparo) VALUES (?,?,?)",
                        ("pendencia_5d", chave, hoje.isoformat()),
                    )
                    houve_escrita = True
                    data_disparo = hoje
                else:
                    data_disparo = date.fromisoformat(rec[0])
                if (hoje - data_disparo).days <= 1:
                    result["pendencia_5d"].append({
                        "pid": pid,
                        "dias": dias_pend,
                        "data_reg": data_reg,
                    })
    except Exception:
        pass

    # ── Limpeza de registros com mais de 5 dias ───────────────────────────
    try:
        cutoff = (hoje - timedelta(days=5)).isoformat()
        conn.execute("DELETE FROM alertas_disparados WHERE data_disparo < ?", (cutoff,))
        houve_escrita = True
    except Exception:
        pass

    if houve_escrita:
        try:
            conn.commit()
            sync_db()
        except Exception:
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
# AVARIAS — funções CRUD
# ══════════════════════════════════════════════════════════════════════════════

def registrar_avaria(codigo: str, produto: str, qtd: int, motivo: str):
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT INTO avarias (codigo, produto, qtd_avariada, motivo, status, registrado_em)
               VALUES (?, ?, ?, ?, 'aberto', ?)""",
            (codigo, produto, qtd, motivo, now)
        )
        conn.commit()
        sync_db()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao registrar avaria: {e}")
        return False


def listar_avarias(apenas_abertas: bool = False) -> pd.DataFrame:
    cols = ["id", "codigo", "produto", "qtd_avariada", "motivo", "status", "registrado_em", "resolvido_em"]
    try:
        query = "SELECT id, codigo, produto, qtd_avariada, motivo, status, registrado_em, resolvido_em FROM avarias"
        if apenas_abertas:
            query += " WHERE status = 'aberto'"
        query += " ORDER BY registrado_em DESC"
        rows = get_db().execute(query).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)


def resolver_avaria(avaria_id: int):
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE avarias SET status = 'resolvido', resolvido_em = ? WHERE id = ?",
            (now, avaria_id)
        )
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao resolver avaria: {e}")


def deletar_avaria(avaria_id: int):
    try:
        conn = get_db()
        conn.execute("DELETE FROM avarias WHERE id = ?", (avaria_id,))
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao deletar avaria: {e}")


def ajustar_qtd_manual(codigo: str, nova_qtd: int) -> tuple:
    """Atualiza qtd_sistema de um produto manualmente, recalculando diferenca/status."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT produto, qtd_fisica, nota, status FROM estoque_mestre WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not row:
            return (False, f"Código '{codigo}' não encontrado no mestre.")
        produto, qtd_fisica, nota, status_atual = row
        qtd_fisica = qtd_fisica if qtd_fisica is not None else nova_qtd
        diferenca = qtd_fisica - nova_qtd
        if diferenca < 0:
            novo_status = "falta"
        elif diferenca > 0:
            novo_status = "sobra"
        else:
            novo_status = "ok"
        conn.execute(
            "UPDATE estoque_mestre SET qtd_sistema = ?, diferenca = ?, status = ? WHERE codigo = ?",
            (nova_qtd, diferenca, novo_status, codigo),
        )
        conn.commit()
        sync_db()
        return (True, f"✅ {produto} ({codigo}) → {nova_qtd} un. salvo.")
    except Exception as e:
        return (False, f"❌ Erro ao ajustar: {e}")


def excluir_produto_mestre(codigo: str) -> tuple:
    """
    Remove um produto do estoque mestre pelo código exato.
    Não afeta nenhuma outra tabela (vendas, lançamentos, etc.).
    """
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT produto, qtd_sistema FROM estoque_mestre WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not row:
            return (False, f"Código '{codigo}' não encontrado no mestre.")
        conn.execute("DELETE FROM estoque_mestre WHERE codigo = ?", (codigo,))
        conn.commit()
        sync_db()
        return (True, f"✅ Registro '{codigo} — {row[0]}' ({row[1]} un.) removido do mestre.")
    except Exception as e:
        return (False, f"❌ Erro ao excluir: {e}")


def get_avarias_count_abertas() -> int:
    try:
        row = get_db().execute("SELECT COUNT(*) FROM avarias WHERE status = 'aberto'").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# BLACKLIST DE REPOSIÇÃO
# ══════════════════════════════════════════════════════════════════════════════
CATEGORIAS_EXCLUIDAS_REPOSICAO = frozenset({
    # Defensivos / campo
    "HERBICIDAS", "FUNGICIDAS", "INSETICIDAS", "NEMATICIDAS", "ÓLEOS",
    "ADUBOS FOLIARES", "ADUBOS QUÍMICOS", "ADUBOS CORRETIVOS",
    "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO", "SUPLEMENTO MINERAL",
    # Sementes
    "SEMENTES",
    # Veterinários / medicamentos (todos os grupos do BI)
    "MEDICAMENTOS", "MEDICAMENTOS VETERINÁRIOS", "MEDICAMENTOS VETERINARIOS",
    "VACINA AFTOSA", "VACINAS DIVERSAS/SOROS",
    "ANTIBIOTICOS/ANTI-INFLAMATORIO",
    "ANESTESICO/ANALGESICO/DIURETIC",
    "ANTITOXICOS",
    "VERMIFUGOS",
    "MOSQUICIDA/CARRAPATICIDA/BERNI",
    "UNGUENTOS/POMADAS",
    "HOMEOPATICO",
    "HORMONIOS LEITEIROS",
    "TONICO MINERAL/VITAMINAS",
    "REPRODUCAO ANIMAL",
    "REPRODUTORES",
    "IDENTIFICACAO ANIMAL",
    "INOCULANTES P/ SILAGEM",
    "DIETA ANIMAL",
    "RATICIDAS",
})

# Categorias exibidas na aba Contagem
CATEGORIAS_CONTAGEM = frozenset({
    "HERBICIDAS", "INSETICIDAS", "FUNGICIDAS",
    "ÓLEOS", "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO",
    "SUPLEMENTO MINERAL", "MATURADORES",
})

CATEGORIA_PRIORITY = [
    "HERBICIDAS", "FUNGICIDAS", "INSETICIDAS", "NEMATICIDAS",
    "ADUBOS FOLIARES", "ADUBOS QUÍMICOS", "ADUBOS CORRETIVOS",
    "ADJUVANTES", "ÓLEOS", "SEMENTES", "MEDICAMENTOS",
]
_CAT_PRIORITY_MAP = {cat: i for i, cat in enumerate(CATEGORIA_PRIORITY)}


# ══════════════════════════════════════════════════════════════════════════════
# LEITURAS DO BANCO — simples e diretas
# ══════════════════════════════════════════════════════════════════════════════
_STOCK_COLS = ["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica",
               "diferenca", "nota", "status", "ultima_contagem", "criado_em"]


def get_current_stock() -> pd.DataFrame:
    try:
        rows = get_db().execute("SELECT * FROM estoque_mestre ORDER BY categoria, produto").fetchall()
        return pd.DataFrame(rows, columns=_STOCK_COLS)
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar estoque: {e}")
        return pd.DataFrame(columns=_STOCK_COLS)


def get_stock_count() -> int:
    try:
        row = get_db().execute("SELECT COUNT(*) FROM estoque_mestre").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def get_reposicao_pendente() -> pd.DataFrame:
    cols = ["id", "codigo", "produto", "categoria", "qtd_vendida", "qtd_estoque", "criado_em"]
    try:
        conn = get_db()
        excl = list(CATEGORIAS_EXCLUIDAS_REPOSICAO)
        ph = ",".join(["?" for _ in excl])
        rows = conn.execute(f"""
            SELECT r.id, r.codigo, r.produto, r.categoria, r.qtd_vendida,
                   COALESCE(e.qtd_sistema, 0) AS qtd_estoque, r.criado_em
            FROM reposicao_loja r
            LEFT JOIN estoque_mestre e ON r.codigo = e.codigo
            WHERE r.reposto = 0 AND r.qtd_vendida > 0
              AND UPPER(r.categoria) NOT IN ({ph})
            ORDER BY r.criado_em DESC
        """, excl).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar reposição: {e}")
        return pd.DataFrame(columns=cols)


def get_historico_uploads() -> pd.DataFrame:
    cols = ["data", "tipo", "arquivo", "total_produtos_lote", "novos", "atualizados", "divergentes"]
    try:
        rows = get_db().execute(
            "SELECT data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes "
            "FROM historico_uploads ORDER BY id DESC LIMIT 20"
        ).fetchall()
        return pd.DataFrame(rows, columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)


# ══════════════════════════════════════════════════════════════════════════════
# PRINCÍPIOS ATIVOS — mapeamento produto ↔ princípio ativo
# ══════════════════════════════════════════════════════════════════════════════

_PA_COLS = ["produto", "principio_ativo", "categoria"]


def load_principios_ativos_from_excel(filepath) -> list:
    """
    Lê o Excel de princípios ativos e retorna lista de dicts.
    Suporta dois formatos:
      - Formato simples (única aba): colunas Produto, Princípio Ativo[, Categoria]
      - Formato produtos_CAMDA.xlsx (3 abas): Herbicidas / Inseticidas e Acaricidas / Fungicidas
    """
    try:
        xls = pd.ExcelFile(filepath)
        abas_camda = {"Herbicidas", "Inseticidas e Acaricidas", "Fungicidas"}
        abas_presentes = set(xls.sheet_names)

        # ── Formato multi-aba (produtos_CAMDA.xlsx) ──────────────────────────
        if abas_camda & abas_presentes:
            records = []
            for aba in ["Herbicidas", "Inseticidas e Acaricidas", "Fungicidas"]:
                if aba not in abas_presentes:
                    continue
                df = pd.read_excel(xls, sheet_name=aba)
                col_prod = col_pa = col_cat = None
                for c in df.columns:
                    cu = str(c).strip().upper()
                    if cu == "PRODUTO":
                        col_prod = c
                    elif "PRINC" in cu or "ATIVO" in cu:
                        col_pa = c
                    elif "CATEG" in cu:
                        col_cat = c
                if not col_prod or not col_pa:
                    continue
                for _, row in df.iterrows():
                    prod = str(row.get(col_prod, "")).strip()
                    pa = str(row.get(col_pa, "")).strip()
                    cat = str(row.get(col_cat, "")).strip() if col_cat else aba
                    if prod and pa and prod.upper() not in ("NAN", "NONE") and pa.upper() not in ("NAN", "NONE"):
                        records.append({"produto": prod, "principio_ativo": pa, "categoria": cat})
            return records

        # ── Formato simples (aba única) ──────────────────────────────────────
        df = pd.read_excel(xls, header=0)
        col_prod = col_pa = col_cat = None
        for c in df.columns:
            cu = str(c).strip().upper()
            if cu == "PRODUTO":
                col_prod = c
            elif "PRINC" in cu or "ATIVO" in cu:
                col_pa = c
            elif "CATEG" in cu:
                col_cat = c
        if not col_prod or not col_pa:
            return []
        records = []
        for _, row in df.iterrows():
            prod = str(row.get(col_prod, "")).strip()
            pa = str(row.get(col_pa, "")).strip()
            cat = str(row.get(col_cat, "")).strip() if col_cat else ""
            if prod and pa and prod.upper() not in ("NAN", "NONE") and pa.upper() not in ("NAN", "NONE"):
                records.append({"produto": prod, "principio_ativo": pa, "categoria": cat})
        return records
    except Exception:
        return []


def sync_principios_ativos(records: list):
    """Sincroniza tabela de princípios ativos no banco."""
    if not records:
        return
    try:
        conn = get_db()
        conn.execute("DELETE FROM principios_ativos")
        conn.executemany(
            "INSERT INTO principios_ativos (produto, principio_ativo, categoria) VALUES (?, ?, ?)",
            [(r["produto"], r["principio_ativo"], r["categoria"]) for r in records]
        )
        conn.commit()
        sync_db()
    except Exception:
        pass


def upsert_principio_ativo(produto: str, principio_ativo: str, categoria: str = "") -> bool:
    """Insere ou atualiza o mapeamento de um único produto."""
    try:
        conn = get_db()
        prod_key = produto.strip().upper()
        conn.execute("DELETE FROM principios_ativos WHERE produto = ?", (prod_key,))
        conn.execute(
            "INSERT INTO principios_ativos (produto, principio_ativo, categoria) VALUES (?, ?, ?)",
            (prod_key, principio_ativo.strip(), categoria.strip()),
        )
        conn.commit()
        sync_db()
        return True
    except Exception:
        return False


def _auto_cache_principios_ativos(produtos: list, conn) -> int:
    """Busca automaticamente o princípio ativo de cada produto via lookup fuzzy e
    persiste no banco caso ainda não exista registro exato para aquele nome.

    Garante que um produto que volta ao estoque (após ter esgotado) já encontre
    seu P.A. salvo sem precisar redigitar.

    Args:
        produtos: lista de nomes de produtos (strings) a verificar.
        conn: conexão com o banco de dados aberta.

    Returns:
        Número de novos mapeamentos salvos.
    """
    if not produtos:
        return 0
    try:
        # Nomes já persistidos no banco (chaves exatas — uppercase)
        rows = conn.execute(
            "SELECT produto, principio_ativo, categoria FROM principios_ativos"
        ).fetchall()
        pa_db: dict[str, tuple] = {
            str(r[0]).strip().upper(): (str(r[1]).strip(), str(r[2]).strip())
            for r in rows
        }

        # Mapa combinado: Excel (catálogo) + banco (prioridade ao banco)
        mapa_excel = carregar_mapa_produtos_camda()
        mapa_combinado: dict[str, str] = {**mapa_excel}
        for k, (pa, _) in pa_db.items():
            mapa_combinado[k] = pa

        if not mapa_combinado:
            return 0

        _idx = _build_pa_lookup(mapa_combinado)

        inserir: list[tuple] = []
        for produto in produtos:
            nome_u = str(produto).strip().upper()
            if not nome_u or nome_u in ("NAN", "NONE"):
                continue
            # Já existe registro exato → não sobrescrever
            if nome_u in pa_db:
                continue
            pa = _lookup_pa_from_index(produto, *_idx)
            if pa:
                inserir.append((nome_u, pa, ""))

        if inserir:
            conn.executemany(
                "INSERT INTO principios_ativos (produto, principio_ativo, categoria) VALUES (?, ?, ?)",
                inserir,
            )
        return len(inserir)
    except Exception:
        return 0


def get_principios_ativos() -> pd.DataFrame:
    """Retorna DataFrame com mapeamento produto ↔ princípio ativo."""
    try:
        rows = get_db().execute("SELECT produto, principio_ativo, categoria FROM principios_ativos").fetchall()
        return pd.DataFrame(rows, columns=_PA_COLS)
    except Exception:
        return pd.DataFrame(columns=_PA_COLS)


def get_pa_count() -> int:
    try:
        row = get_db().execute("SELECT COUNT(*) FROM principios_ativos").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def search_by_principio_ativo(search_term: str, df_pa: pd.DataFrame) -> set:
    """Retorna set de nomes de produtos que contêm o princípio ativo buscado."""
    if df_pa.empty:
        return set()
    mask = df_pa["principio_ativo"].str.contains(search_term, case=False, na=False, regex=False)
    return set(df_pa.loc[mask, "produto"].str.upper())


def carregar_mapa_produtos_camda() -> dict:
    """
    Lê produtos_CAMDA.xlsx (abas Herbicidas, Inseticidas e Acaricidas, Fungicidas)
    e retorna dict {NOME_PRODUTO_UPPER: principio_ativo}.
    """
    caminho = "produtos_CAMDA.xlsx"
    if not os.path.exists(caminho):
        return {}
    try:
        xls = pd.ExcelFile(caminho)
        frames = []
        for aba in ["Herbicidas", "Inseticidas e Acaricidas", "Fungicidas"]:
            if aba not in xls.sheet_names:
                continue
            df = pd.read_excel(xls, sheet_name=aba)
            col_prod, col_pa = None, None
            for c in df.columns:
                cu = str(c).strip().upper()
                if cu == "PRODUTO":
                    col_prod = c
                elif "PRINC" in cu or "ATIVO" in cu:
                    col_pa = c
            if col_prod and col_pa:
                frames.append(
                    df[[col_prod, col_pa]].rename(
                        columns={col_prod: "Produto", col_pa: "Principio_Ativo"}
                    )
                )
        if not frames:
            return {}
        catalogo = pd.concat(frames, ignore_index=True)
        return {
            str(r["Produto"]).strip().upper(): str(r["Principio_Ativo"]).strip()
            for _, r in catalogo.iterrows()
            if str(r["Produto"]).strip().upper() not in ("NAN", "NONE", "")
            and str(r["Principio_Ativo"]).strip().upper() not in ("NAN", "NONE", "")
        }
    except Exception:
        return {}


_PA_PALETTE = [
    "#00E5A0", "#00C4FF", "#FF6B35", "#FFD166", "#A78BFA",
    "#F472B6", "#34D399", "#FB923C", "#60A5FA", "#E879F9",
    "#FBBF24", "#2DD4BF",
]


def extrair_litros(nome_produto: str):
    """Extrai o volume em litros a partir do nome do produto.

    Suporta padrões como: 5L, 20L, 200L, 1L, 500ML, 250ML, 1,5L, etc.
    Retorna float com o volume em litros, ou None se não encontrado.
    """
    nome = str(nome_produto).upper()
    ml = re.search(r'(\d+(?:[.,]\d+)?)\s*ML\b', nome)
    if ml:
        return float(ml.group(1).replace(',', '.')) / 1000
    litros = re.search(r'(\d+(?:[.,]\d+)?)\s*L\b', nome)
    if litros:
        return float(litros.group(1).replace(',', '.'))
    return None


def extrair_kg(nome_produto: str):
    """Extrai o peso em kg a partir do nome do produto.

    Suporta padrões como: 5KG, 20KG, 500G, 1,5KG, etc.
    Retorna float com o peso em kg, ou None se não encontrado.
    """
    nome = str(nome_produto).upper()
    kg_m = re.search(r'(\d+(?:[.,]\d+)?)\s*KG\b', nome)
    if kg_m:
        return float(kg_m.group(1).replace(',', '.'))
    g_m = re.search(r'(\d+(?:[.,]\d+)?)\s*G\b', nome)
    if g_m:
        return float(g_m.group(1).replace(',', '.')) / 1000
    return None


def _fmt_volume(total_litros, total_kg, total_units) -> str:
    """Formata o volume combinado de um P.A.: '8060L + 190kg', '8060L', '190kg' ou '38 un.*'."""
    parts = []
    if pd.notna(total_litros) and total_litros > 0:
        parts.append(f"{int(total_litros):,} L".replace(",", "."))
    if pd.notna(total_kg) and total_kg > 0:
        kg_val = total_kg
        parts.append(f"{int(kg_val):,} kg".replace(",", ".") if kg_val >= 1 else f"{kg_val:.1f} kg")
    return " + ".join(parts) if parts else f"{int(total_units)} un.*"


def build_principios_ativos_tab(df_mestre: pd.DataFrame, df_pa: pd.DataFrame):
    """Constrói a aba Princípios Ativos — visual fiel ao componente React."""
    if df_mestre.empty:
        st.info("Carregue o estoque mestre para visualizar os dados por princípio ativo.")
        return

    # ── 1. Montar mapa produto → principio_ativo ────────────────────────────
    mapa_db: dict = {}
    if not df_pa.empty:
        for _, row in df_pa.iterrows():
            mapa_db[str(row["produto"]).strip().upper()] = str(row["principio_ativo"]).strip()

    mapa_excel = carregar_mapa_produtos_camda()
    mapa_combinado = {**mapa_excel, **mapa_db}

    if not mapa_combinado:
        st.warning(
            "Nenhum mapeamento de princípios ativos encontrado. "
            "Coloque **produtos_CAMDA.xlsx** na raiz do projeto "
            "ou faça upload via '🧬 Base de Princípios Ativos' no painel lateral."
        )
        return

    # ── 2. Enriquecer estoque com P.A. (match multi-etapa) ──────────────────
    _idx = _build_pa_lookup(mapa_combinado)
    _cat_n, _cat_ns, _cat_n_keys, _cat_ns_keys = _idx[1], _idx[2], _idx[3], _idx[4]

    def _lookup_pa(nome: str) -> str:
        pa = _lookup_pa_from_index(nome, *_idx)
        return pa if pa else "Não identificado"

    registros = []
    for _, row in df_mestre.iterrows():
        pa = _lookup_pa(str(row["produto"]))
        qtd = max(float(row.get("qtd_sistema", 0) or 0), 0)
        litros_emb = extrair_litros(str(row["produto"]))
        kg_emb = extrair_kg(str(row["produto"])) if litros_emb is None else None
        vol_litros = qtd * litros_emb if litros_emb is not None else None
        vol_kg = qtd * kg_emb if kg_emb is not None else None
        registros.append({
            "produto": row["produto"],
            "principio_ativo": pa,
            "quantidade": qtd,
            "litros_emb": litros_emb,
            "volume_litros": vol_litros,
            "kg_emb": kg_emb,
            "volume_kg": vol_kg,
            "has_vol": litros_emb is not None or kg_emb is not None,
            "categoria": row.get("categoria", ""),
        })

    df_enr = pd.DataFrame(registros)

    # ── 3. Agregar por P.A. ─────────────────────────────────────────────────
    df_agg = (
        df_enr.groupby("principio_ativo")
        .agg(
            total=("quantidade", "sum"),
            total_litros=("volume_litros", lambda x: x.sum(min_count=1)),
            total_kg=("volume_kg", lambda x: x.sum(min_count=1)),
            n_produtos=("produto", "count"),
            n_sem_vol=("has_vol", lambda x: (~x).sum()),
        )
        .reset_index()
    )
    # Chave de ordenação unificada: usa litros se disponível, senão kg, senão unidades
    # — garante que produtos só-kg entrem no ranking entre os de litros equivalente
    df_agg["_sort_key"] = df_agg.apply(
        lambda r: r["total_litros"] if pd.notna(r["total_litros"]) and r["total_litros"] > 0
                  else (r["total_kg"] if pd.notna(r["total_kg"]) and r["total_kg"] > 0 else r["total"]),
        axis=1,
    )
    df_agg = df_agg.sort_values("_sort_key", ascending=False).drop(columns=["_sort_key"])

    df_id = df_agg[df_agg["principio_ativo"] != "Não identificado"]
    n_nao_id = int((df_enr["principio_ativo"] == "Não identificado").sum())

    total_pa    = int(df_id.shape[0])
    total_prods = int(df_enr["produto"].nunique())
    total_vol   = float(df_id["total"].sum())
    total_litros_geral = float(df_id["total_litros"].sum(skipna=True))
    total_kg_geral = float(df_id["total_kg"].sum(skipna=True))

    maior_vol_row  = df_id.sort_values(["total_litros", "total_kg", "total"], ascending=[False, False, False], na_position="last").head(1)
    mais_marcas_row = df_id.sort_values("n_produtos", ascending=False).head(1)
    maior_vol_txt = (
        _fmt_volume(
            maior_vol_row["total_litros"].iloc[0],
            maior_vol_row["total_kg"].iloc[0],
            maior_vol_row["total"].iloc[0],
        ) if not maior_vol_row.empty else "—"
    )
    maior_vol_pa   = maior_vol_row["principio_ativo"].iloc[0]      if not maior_vol_row.empty  else "—"
    mais_marcas_txt = f"{int(mais_marcas_row['n_produtos'].iloc[0])} prod." if not mais_marcas_row.empty else "—"
    mais_marcas_pa  = mais_marcas_row["principio_ativo"].iloc[0]   if not mais_marcas_row.empty else "—"

    # ── 4. Header ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">
      <div style="width:6px;height:36px;border-radius:3px;
                  background:linear-gradient(180deg,#00E5A0,#00C4FF);flex-shrink:0"></div>
      <div>
        <div style="font-size:20px;font-weight:800;letter-spacing:-0.5px;color:#F9FAFB">
          Princípios Ativos em Estoque
        </div>
        <div style="font-size:12px;color:#6B7280;margin-top:2px">
          {total_pa} princípios · {total_prods} produtos comerciais · {_fmt_volume(total_litros_geral if total_litros_geral > 0 else None, total_kg_geral if total_kg_geral > 0 else None, total_vol)} total
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 5. KPI cards ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
      <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:14px 18px">
        <div style="font-size:11px;color:#6B7280;margin-bottom:6px">Princípios Ativos</div>
        <div style="font-size:22px;font-weight:800;color:#00E5A0">{total_pa}</div>
      </div>
      <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:14px 18px">
        <div style="font-size:11px;color:#6B7280;margin-bottom:6px">Produtos Comerciais</div>
        <div style="font-size:22px;font-weight:800;color:#00C4FF">{total_prods}</div>
      </div>
      <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:14px 18px">
        <div style="font-size:11px;color:#6B7280;margin-bottom:6px">Maior Volume</div>
        <div style="font-size:18px;font-weight:800;color:#FFD166">{maior_vol_txt}</div>
        <div style="font-size:10px;color:#6B7280;margin-top:2px;overflow:hidden;
                    text-overflow:ellipsis;white-space:nowrap" title="{maior_vol_pa}">{maior_vol_pa}</div>
      </div>
      <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:14px 18px">
        <div style="font-size:11px;color:#6B7280;margin-bottom:6px">Mais Marcas</div>
        <div style="font-size:18px;font-weight:800;color:#A78BFA">{mais_marcas_txt}</div>
        <div style="font-size:10px;color:#6B7280;margin-top:2px;overflow:hidden;
                    text-overflow:ellipsis;white-space:nowrap" title="{mais_marcas_pa}">{mais_marcas_pa}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 6. Controles ─────────────────────────────────────────────────────────
    col_type, _ = st.columns([2, 4])
    with col_type:
        chart_type = st.radio(
            "Tipo", ["⬛ Barras", "🔵 Pizza"],
            key="pa_chart_type", horizontal=True, label_visibility="collapsed",
        )
    top_n = 20

    # ── 7. Preparar dados do gráfico ─────────────────────────────────────────
    df_plot = df_id.head(top_n).copy()

    if df_plot.empty:
        st.warning(
            f"Nenhum produto do estoque foi reconhecido no catálogo de P.A. "
            f"({n_nao_id} produto(s) sem correspondência)."
        )
        with st.expander("🔍 Diagnóstico — produtos do estoque sem P.A. mapeado", expanded=True):
            df_nao_id_diag = (
                df_enr[df_enr["principio_ativo"] == "Não identificado"]
                [["produto", "categoria", "quantidade"]]
                .sort_values("produto")
            )
            st.caption(
                f"Mapa carregado: **{len(mapa_combinado)} produto(s)** do catálogo. "
                "Verifique se os nomes abaixo coincidem com os da planilha **produtos_CAMDA.xlsx**."
            )
            st.dataframe(
                df_nao_id_diag.rename(columns={
                    "produto": "Produto no Estoque", "categoria": "Categoria", "quantidade": "Qtd"
                }),
                hide_index=True, use_container_width=True,
            )
            if mapa_combinado:
                st.caption(f"Exemplos no catálogo: `{'` · `'.join(sorted(mapa_combinado.keys())[:10])}`")
                nomes_est = sorted(df_enr["produto"].str.upper().unique())[:10]
                st.caption(f"Exemplos no estoque:  `{'` · `'.join(nomes_est)}`")
        return

    # ── 8. Estado de seleção ──────────────────────────────────────────────────
    if "pa_selected" not in st.session_state:
        st.session_state["pa_selected"] = None
    # pa_chart_ver: muda a key do widget para forçar reset da seleção interna
    if "pa_chart_ver" not in st.session_state:
        st.session_state["pa_chart_ver"] = 0
    pa_sel = st.session_state["pa_selected"]
    # Reset apenas se o PA não existe mais nos dados — não pelo limite top_n
    if pa_sel and pa_sel not in df_id["principio_ativo"].values:
        st.session_state["pa_selected"] = None
        pa_sel = None

    # ── 9. Montar gráfico Plotly ──────────────────────────────────────────────
    cores = [_PA_PALETTE[i % len(_PA_PALETTE)] for i in range(len(df_plot))]
    pa_list = df_plot["principio_ativo"].tolist()

    def _rgba(hex_color: str, alpha: float) -> str:
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        return f"rgba({r},{g},{b},{alpha})"

    if "Barras" in chart_type:
        bar_colors = [
            "#FFD166" if pa == pa_sel else (c if pa_sel is None else _rgba(c, 0.35))
            for pa, c in zip(pa_list, cores)
        ]
        _y_vals = [
            v if pd.notna(v) and v > 0 else (k if pd.notna(k) and k > 0 else 0)
            for v, k in zip(df_plot["total_litros"], df_plot["total_kg"])
        ]
        _text_vals = [
            _fmt_volume(v, k, u)
            for v, k, u in zip(df_plot["total_litros"], df_plot["total_kg"], df_plot["total"])
        ]
        _hover_custom = list(zip(
            df_plot["n_produtos"].tolist(),
            _text_vals,
        ))
        fig = go.Figure(go.Bar(
            x=pa_list,
            y=_y_vals,
            marker_color=bar_colors,
            marker_line_width=0,
            text=_text_vals,
            textposition="outside",
            textfont=dict(size=10, color="#F9FAFB"),
            hovertemplate="<b>%{x}</b><br>Volume: %{customdata[1]}<br>Produtos: %{customdata[0]}<extra></extra>",
            customdata=_hover_custom,
        ))
        fig.update_layout(
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            font=dict(color="#F9FAFB", size=11),
            height=380,
            margin=dict(l=10, r=20, t=30, b=100),
            xaxis=dict(
                gridcolor="#1F2937", showgrid=False, showline=False,
                tickangle=-35, tickfont=dict(size=10, color="#6B7280"),
            ),
            yaxis=dict(
                gridcolor="#1F2937", showgrid=True, gridwidth=1,
                tickfont=dict(size=11, color="#6B7280"),
                title=dict(text="Volume (L / kg)", font=dict(size=11, color="#6B7280")),
            ),
            showlegend=False,
            bargap=0.3,
            clickmode="event+select",
        )
    else:  # Pizza / donut
        pie_line_colors = ["#FFD166" if pa == pa_sel else "rgba(0,0,0,0)" for pa in pa_list]
        pie_line_widths = [3 if pa == pa_sel else 0 for pa in pa_list]
        pie_opacities   = [1.0 if pa_sel is None or pa == pa_sel else 0.3 for pa in pa_list]
        _pie_vals = [
            v if pd.notna(v) else (k if pd.notna(k) else u)
            for v, k, u in zip(df_plot["total_litros"], df_plot["total_kg"], df_plot["total"])
        ]
        _pie_hover = [
            _fmt_volume(v, k, u)
            for v, k, u in zip(df_plot["total_litros"], df_plot["total_kg"], df_plot["total"])
        ]
        fig = go.Figure(go.Pie(
            labels=pa_list,
            values=_pie_vals,
            marker=dict(
                colors=[_rgba(c, o) for c, o in zip(cores, pie_opacities)],
                line=dict(color=pie_line_colors, width=pie_line_widths),
            ),
            textinfo="label+percent",
            textfont=dict(size=10),
            hovertemplate="<b>%{label}</b><br>%{customdata} (%{percent})<extra></extra>",
            customdata=_pie_hover,
            hole=0.35,
            sort=False,
        ))
        fig.update_layout(
            paper_bgcolor="#111827",
            font=dict(color="#F9FAFB", size=11),
            height=420,
            margin=dict(l=10, r=10, t=30, b=30),
            legend=dict(bgcolor="#111827", bordercolor="#1F2937", font=dict(size=10, color="#6B7280")),
            clickmode="event+select",
        )

    # ── 10. Renderizar gráfico (com suporte a click via on_select) ────────────
    st.caption("Clique em uma barra para ver os detalhes por produto comercial")
    _chart_key = f"pa_main_chart_v{st.session_state['pa_chart_ver']}"
    try:
        event = st.plotly_chart(
            fig, use_container_width=True,
            config={"displayModeBar": False},
            on_select="rerun",
            key=_chart_key,
        )
        if event and event.selection and event.selection.points:
            pt = event.selection.points[0]
            clicked_pa = pt.get("x") or pt.get("label")
            if clicked_pa:
                novo = None if clicked_pa == st.session_state["pa_selected"] else clicked_pa
                st.session_state["pa_selected"] = novo
                # Incrementa versão → nova key no próximo rerun → reset da seleção
                # do widget, evitando que o "ghost click" dispare o toggle infinito
                st.session_state["pa_chart_ver"] += 1
                st.rerun()
    except TypeError:
        # Streamlit < 1.35 — sem on_select
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

    _n_fallback = int(df_plot["n_sem_vol"].sum())
    if _n_fallback > 0:
        st.caption(
            f"\\* {_n_fallback} produto(s) sem volume identificável no nome — "
            "exibido em unidades. Inclua o tamanho da embalagem no nome (ex: 5L, 20L, 500ML, 5KG)."
        )

    # ── 11. Selectbox de drill-down (complementar ao click) ───────────────────
    # Usa key dinâmica (pa_chart_ver) para que o widget redefina seu valor
    # sempre que o gráfico muda pa_sel via click — evita dessincronia.
    opcoes_pa = ["— selecione —"] + sorted(df_id["principio_ativo"].tolist())
    idx_atual = opcoes_pa.index(pa_sel) if pa_sel in opcoes_pa else 0
    pa_sel_box = st.selectbox(
        "Ou selecione um princípio ativo:",
        opcoes_pa,
        index=idx_atual,
        key=f"pa_drilldown_sel_{st.session_state['pa_chart_ver']}",
    )
    if pa_sel_box != "— selecione —" and pa_sel_box != pa_sel:
        st.session_state["pa_selected"] = pa_sel_box
        st.session_state["pa_chart_ver"] += 1  # reset chart para limpar seleção visual
        st.rerun()
    elif pa_sel_box == "— selecione —" and pa_sel is not None:
        st.session_state["pa_selected"] = None
        st.session_state["pa_chart_ver"] += 1
        st.rerun()

    pa_sel = st.session_state["pa_selected"]

    # ── 12. Painel de detalhe com mini-barras ─────────────────────────────────
    if pa_sel:
        df_drill = df_enr[df_enr["principio_ativo"] == pa_sel].sort_values("quantidade", ascending=False)
        if not df_drill.empty:
            total_drill = float(df_drill["quantidade"].sum())
            total_drill_litros = float(df_drill["volume_litros"].sum(skipna=True))
            total_drill_kg = float(df_drill["volume_kg"].sum(skipna=True))
            mini_bars = ""
            for i, (_, r) in enumerate(df_drill.iterrows()):
                pct = (r["quantidade"] / total_drill * 100) if total_drill > 0 else 0
                cor = _PA_PALETTE[i % len(_PA_PALETTE)]
                _lit_emb = r.get("litros_emb")
                _vol_l = r.get("volume_litros")
                _kg_emb = r.get("kg_emb")
                _vol_k = r.get("volume_kg")
                if pd.notna(_vol_l) and _vol_l is not None:
                    _lit_fmt = str(int(_lit_emb)) if _lit_emb == int(_lit_emb) else f"{_lit_emb:.3f}".rstrip("0")
                    _vol_fmt = f"{int(_vol_l):,}".replace(",", ".")
                    _vol_str = f"{int(r['quantidade'])} un × {_lit_fmt}L = {_vol_fmt}L"
                elif pd.notna(_vol_k) and _vol_k is not None:
                    _kg_fmt = str(int(_kg_emb)) if _kg_emb == int(_kg_emb) else f"{_kg_emb:.3f}".rstrip("0")
                    _vk_fmt = f"{int(_vol_k):,}".replace(",", ".") if _vol_k >= 1 else f"{_vol_k:.1f}"
                    _vol_str = f"{int(r['quantidade'])} un × {_kg_fmt}kg = {_vk_fmt}kg"
                else:
                    _vol_str = f"{int(r['quantidade'])} un.*"
                # Sem indentação: Markdown trata 4+ espaços como bloco de código
                mini_bars += (
                    f'<div style="margin-bottom:10px">'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">'
                    f'<span style="color:#F9FAFB">{r["produto"]}</span>'
                    f'<span style="color:{cor};font-weight:700">{_vol_str}</span>'
                    f'</div>'
                    f'<div style="background:#1F2937;border-radius:4px;height:8px;overflow:hidden">'
                    f'<div style="width:{pct:.1f}%;height:100%;background:{cor};'
                    f'border-radius:4px;transition:width 0.5s ease"></div>'
                    f'</div>'
                    f'</div>'
                )

            n_d = len(df_drill)
            plural = "s" if n_d != 1 else ""
            _total_txt = _fmt_volume(
                total_drill_litros if total_drill_litros > 0 else None,
                total_drill_kg if total_drill_kg > 0 else None,
                total_drill,
            )
            html_painel = (
                '<div style="background:#111827;border:1px solid #00E5A0;border-radius:16px;'
                'padding:20px;margin-top:8px;animation:_paFadeIn 0.25s ease">'
                '<div style="display:flex;align-items:flex-start;'
                'justify-content:space-between;margin-bottom:16px">'
                '<div>'
                f'<div style="font-size:15px;font-weight:700;color:#00E5A0">🧬 {pa_sel}</div>'
                f'<div style="font-size:12px;color:#6B7280;margin-top:2px">'
                f'{n_d} produto{plural} comerci{"ais" if n_d != 1 else "al"}'
                '</div>'
                '</div>'
                '</div>'
                + mini_bars +
                '<div style="display:flex;justify-content:flex-end;padding-top:12px;'
                'border-top:1px solid #1F2937;font-size:14px;font-weight:700">'
                '<span style="color:#6B7280;margin-right:8px">Total:</span>'
                f'<span style="color:#FFD166">{_total_txt}</span>'
                '</div>'
                '</div>'
                '<style>'
                '@keyframes _paFadeIn{'
                'from{opacity:0;transform:translateY(8px)}'
                'to{opacity:1;transform:translateY(0)}'
                '}'
                '</style>'
            )
            st.markdown(html_painel, unsafe_allow_html=True)

            if st.button("✕ Fechar detalhe", key="pa_close_btn"):
                st.session_state["pa_selected"] = None
                st.session_state["pa_chart_ver"] += 1
                st.rerun()

    # ── 13. Produtos sem P.A. mapeado ─────────────────────────────────────────
    if n_nao_id > 0:
        st.caption(
            f"ℹ️ {n_nao_id} produto(s) sem mapeamento de P.A. "
            "Carregue **produtos_CAMDA.xlsx** via 'Base de Princípios Ativos' no painel lateral."
        )
        with st.expander(f"🔍 Mapear / corrigir P.A. ({n_nao_id} sem mapeamento)", expanded=False):
            # Todos os produtos do estoque (não só os não mapeados)
            df_todos = (
                df_enr[["produto", "categoria", "quantidade", "principio_ativo"]]
                .sort_values("produto")
                .drop_duplicates("produto")
                .reset_index(drop=True)
            )
            nomes_todos = df_todos["produto"].tolist()

            # P.A. disponíveis para sugestão (do catálogo + banco)
            pa_opcoes = sorted(set(mapa_combinado.values()))

            # Sugestão automática via fuzzy
            _cat_diag = list(_cat_ns.keys())
            def _sugerir_pa(nome: str) -> str:
                s = _pstrip(_pnorm(str(nome)))
                m = _gcm(s, _cat_diag, n=1, cutoff=0.0)
                return _cat_ns[m[0]] if m else ""

            st.caption(
                "Busque **qualquer produto** — inclusive os já mapeados para corrigir. "
                f"**{n_nao_id}** ainda sem P.A."
            )

            # ── Seleção do produto ──────────────────────────────────────────
            prod_map_sel = st.selectbox(
                "Produto",
                options=nomes_todos,
                index=0,
                key="pa_map_prod_sel",
                placeholder="Digite para filtrar…",
            )

            # Dados do produto selecionado
            _row_sel = df_todos[df_todos["produto"] == prod_map_sel]
            _qtd_sel = int(_row_sel["quantidade"].iloc[0]) if not _row_sel.empty else 0
            _cat_sel = str(_row_sel["categoria"].iloc[0]) if not _row_sel.empty else ""
            _pa_atual = str(_row_sel["principio_ativo"].iloc[0]) if not _row_sel.empty else ""
            _ja_mapeado = _pa_atual and _pa_atual != "Não identificado"
            if _ja_mapeado:
                st.caption(
                    f"Qtd: **{_qtd_sel} un.** — "
                    f"P.A. atual: ✅ *{_pa_atual}* — clique Salvar para corrigir."
                )
            else:
                st.caption(f"Qtd: **{_qtd_sel} un.** — Sem P.A. mapeado.")

            # ── Princípio Ativo ─────────────────────────────────────────────
            # Pré-seleciona: P.A. atual se já mapeado, senão melhor sugestão fuzzy
            _default_pa = _pa_atual if _ja_mapeado else _sugerir_pa(prod_map_sel or "")

            _PA_NOVO = "➕ Digitar novo P.A…"
            pa_lista = (
                [_default_pa] + [p for p in pa_opcoes if p != _default_pa] + [_PA_NOVO]
                if _default_pa else pa_opcoes + [_PA_NOVO]
            )
            pa_map_sel = st.selectbox(
                "Princípio Ativo",
                options=pa_lista,
                index=0,
                key=f"pa_map_pa_sel_{prod_map_sel}",
                help="Escolha da lista ou selecione '➕ Digitar novo' para informar um P.A. inédito.",
            )

            pa_final = pa_map_sel
            if pa_map_sel == _PA_NOVO:
                pa_final = st.text_input(
                    "Novo Princípio Ativo",
                    placeholder="Ex.: Glifosato + Diquat",
                    key="pa_map_pa_novo",
                )

            # ── Botão salvar ────────────────────────────────────────────────
            if st.button("💾 Salvar mapeamento", type="primary", use_container_width=True):
                if prod_map_sel and pa_final and pa_final.strip() and pa_final != _PA_NOVO:
                    if upsert_principio_ativo(prod_map_sel, pa_final.strip(), _cat_sel):
                        st.success(f"✅ **{prod_map_sel}** → *{pa_final.strip()}*")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar. Tente novamente.")
                else:
                    st.warning("Selecione um produto e informe o Princípio Ativo antes de salvar.")



def reset_db():
    try:
        conn = get_db()
        conn.execute("DELETE FROM estoque_mestre")
        conn.execute("DELETE FROM historico_uploads")
        conn.execute("DELETE FROM reposicao_loja")
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao limpar banco: {e}")


def marcar_reposto(item_id: int):
    try:
        conn = get_db()
        conn.execute(
            "UPDATE reposicao_loja SET reposto = 1, reposto_em = ? WHERE id = ?",
            [datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S"), item_id]
        )
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao marcar reposto: {e}")


def registrar_divergencia_manual(codigo: str, delta: int) -> tuple:
    """Registra divergência (sobra/falta) sem alterar qtd_sistema.
    delta > 0 = sobrando, delta < 0 = faltando.
    """
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT produto, qtd_sistema FROM estoque_mestre WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not row:
            return (False, f"Código '{codigo}' não encontrado.")
        produto, qtd_sistema = row
        qtd_fisica = qtd_sistema + delta
        diferenca = delta  # qtd_fisica - qtd_sistema
        status = "sobra" if delta > 0 else "falta"
        conn.execute(
            "UPDATE estoque_mestre SET qtd_fisica = ?, diferenca = ?, status = ? WHERE codigo = ?",
            (qtd_fisica, diferenca, status, codigo),
        )
        conn.commit()
        sync_db()
        sinal = "+" if delta > 0 else ""
        return (True, f"✅ {produto} ({codigo}) → {status} de {sinal}{delta} un. registrada.")
    except Exception as e:
        return (False, f"❌ Erro: {e}")


def resolver_divergencia(codigo: str):
    """Remove manualmente um produto da lista de divergências (seta status para 'ok')."""
    try:
        conn = get_db()
        conn.execute(
            "UPDATE estoque_mestre SET status = 'ok', diferenca = 0 WHERE codigo = ?",
            [codigo]
        )
        conn.commit()
        sync_db()
    except Exception as e:
        st.error(f"❌ Erro ao resolver divergência: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO E PARSING — otimizados
# ══════════════════════════════════════════════════════════════════════════════

_CLASSIFY_RULES = [
    ("HERBICIDAS", ("HERBICIDA",)),
    ("FUNGICIDAS", ("FUNGICIDA",)),
    ("INSETICIDAS", ("INSETICIDA",)),
    ("NEMATICIDAS", ("NEMATICIDA",)),
    ("ADUBOS FOLIARES", ("ADUBO FOLIAR",)),
    ("ADUBOS QUÍMICOS", ("ADUBO Q",)),
    ("ADUBOS CORRETIVOS", ("ADUBO CORRETIVO", "CALCARIO", "CALCÁRIO")),
    ("ÓLEOS", ("OLEO", "ÓLEO")),
    ("SEMENTES", ("SEMENTE",)),
    ("ADJUVANTES", ("ADJUVANTE", "ESPALHANTE")),
    ("MEDICAMENTOS", ("MEDICAMENTO", "VERMIFUGO", "VERMÍFUGO", "VACINA", "ANTIBIOTICO", "ANTIBIÓTICO")),
]

_GRUPO_MAP = {
    "ADUBOS FOLIARES": "ADUBOS FOLIARES",
    "ADUBOS QUIMICOS": "ADUBOS QUÍMICOS",
    "ADUBOS CORRETIVOS": "ADUBOS CORRETIVOS",
    "HERBICIDAS": "HERBICIDAS", "FUNGICIDAS": "FUNGICIDAS",
    "INSETICIDAS": "INSETICIDAS", "NEMATICIDAS": "NEMATICIDAS",
    "OLEO MINERAL E VEGETAL": "ÓLEOS", "ADJUVANTES": "ADJUVANTES",
    "SEMENTES": "SEMENTES",
    # Veterinários — normaliza para o nome exato da blacklist
    "MEDICAMENTOS": "MEDICAMENTOS",
    "MEDICAMENTOS VETERINÁRIOS": "MEDICAMENTOS",
    "MEDICAMENTOS VETERINARIOS": "MEDICAMENTOS",
    "VACINA AFTOSA": "VACINA AFTOSA",
    "VACINAS DIVERSAS/SOROS": "VACINAS DIVERSAS/SOROS",
    "ANTIBIOTICOS/ANTI-INFLAMATORIO": "ANTIBIOTICOS/ANTI-INFLAMATORIO",
    "ANESTESICO/ANALGESICO/DIURETIC": "ANESTESICO/ANALGESICO/DIURETIC",
    "ANTITOXICOS": "ANTITOXICOS",
    "VERMIFUGOS": "VERMIFUGOS",
    "MOSQUICIDA/CARRAPATICIDA/BERNI": "MOSQUICIDA/CARRAPATICIDA/BERNI",
    "UNGUENTOS/POMADAS": "UNGUENTOS/POMADAS",
    "HOMEOPATICO": "HOMEOPATICO",
    "HORMONIOS LEITEIROS": "HORMONIOS LEITEIROS",
    "TONICO MINERAL/VITAMINAS": "TONICO MINERAL/VITAMINAS",
    "REPRODUCAO ANIMAL": "REPRODUCAO ANIMAL",
    "REPRODUTORES": "REPRODUTORES",
    "IDENTIFICACAO ANIMAL": "IDENTIFICACAO ANIMAL",
    "INOCULANTES P/ SILAGEM": "INOCULANTES P/ SILAGEM",
    "DIETA ANIMAL": "DIETA ANIMAL",
    "RATICIDAS": "RATICIDAS",
}

_SHORT_PREFIXES = [
    "HERBICIDA ", "FUNGICIDA ", "INSETICIDA ", "NEMATICIDA ",
    "ADUBO FOLIAR ", "ADUBO Q.", "OLEO VEGETAL ", "OLEO MINERAL ",
    "ÓLEO VEGETAL ", "ÓLEO MINERAL ", "ADJUVANTE ", "SEMENTE ",
    "MEDICAMENTO ",
]


def classify_product(name: str) -> str:
    n = name.upper()
    for cat, keywords in _CLASSIFY_RULES:
        for kw in keywords:
            if kw in n:
                return cat
    return "OUTROS"


def normalize_grupo(grupo: str) -> str:
    return _GRUPO_MAP.get(grupo.strip().upper(), grupo.strip().upper())


def short_name(prod: str) -> str:
    up = prod.upper()
    for p in _SHORT_PREFIXES:
        if up.startswith(p):
            return prod[len(p):].strip()
    return prod


def parse_annotation(nota: str, qtd_sistema: int) -> tuple:
    """Retorna: (qtd_fisica, diferenca, observacao, status_type)"""
    if not nota:
        return (qtd_sistema, 0, "", "ok")
    text = nota.strip()
    if not text or text.lower() in ("nan", "none"):
        return (qtd_sistema, 0, "", "ok")

    tl = _RE_SPACES.sub(" ", text.lower()).strip()

    # FALTA
    m = _RE_FALTA.match(tl)
    if m:
        f = int(m.group(1))
        return (qtd_sistema - f, -f, m.group(2).strip(), "falta")
    m = _RE_FALTA_SHORT.match(tl)
    if m:
        f = int(m.group(1))
        return (qtd_sistema - f, -f, m.group(2).strip(), "falta")

    # SOBRA
    m = _RE_SOBRA.match(tl)
    if m:
        s = int(m.group(1))
        return (qtd_sistema + s, s, m.group(2).strip(), "sobra")
    m = _RE_SOBRA_SHORT.match(tl)
    if m:
        s = int(m.group(1))
        return (qtd_sistema + s, s, m.group(2).strip(), "sobra")

    # Fallback
    m = _RE_FALTA_MID.search(tl)
    if m:
        f = int(m.group(1))
        return (qtd_sistema - f, -f, text, "falta")
    m = _RE_SOBRA_MID.search(tl)
    if m:
        s = int(m.group(1))
        return (qtd_sistema + s, s, text, "sobra")

    return (qtd_sistema, 0, text, "ok")


# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO E PARSING DE PLANILHAS
# ══════════════════════════════════════════════════════════════════════════════

def detect_format(df_raw: pd.DataFrame) -> str:
    for i in range(min(10, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        row_text = " ".join(vals)
        if any(x in row_text for x in ("QTDD - VENDIDA", "QTDD ESTOQUE", "GRUPO DE PRODUTO")):
            return "vendas"
        if "PRODUTO" in vals and any("QUANTIDADE" in v or v == "QTD" for v in vals):
            return "estoque"
    return "desconhecido"


def _find_header(df_raw, check_fn, max_rows=15):
    for i in range(min(max_rows, len(df_raw))):
        vals = [str(v).strip().upper() for v in df_raw.iloc[i].tolist()]
        if check_fn(vals):
            return i
    return None


def parse_estoque_format(df_raw: pd.DataFrame) -> tuple:
    header_idx = _find_header(df_raw, lambda vals: "PRODUTO" in vals and any("QUANTIDADE" in v or v == "QTD" for v in vals))
    if header_idx is None:
        return (False, "Cabeçalho não encontrado. Preciso de 'Produto' e 'Quantidade'.")

    df = df_raw.iloc[header_idx + 1:].copy()
    raw_cols = df_raw.iloc[header_idx].tolist()
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_cols)]

    col_map = {}
    for c in df.columns:
        cu = c.upper().strip()
        if cu == "PRODUTO" and "produto" not in col_map:
            col_map["produto"] = c
        elif ("QUANTIDADE" in cu or cu == "QTD") and "qtd" not in col_map:
            col_map["qtd"] = c
        elif cu in ("CÓDIGO", "CODIGO", "COD") and "codigo" not in col_map:
            col_map["codigo"] = c
        elif ("OBS" in cu or "NOTA" in cu or "DIFEREN" in cu or "ANOTA" in cu) and "nota" not in col_map:
            col_map["nota"] = c

    if "produto" not in col_map or "qtd" not in col_map:
        return (False, f"Colunas: {list(df.columns)} — falta 'Produto' ou 'Quantidade'.")

    # Procura coluna de nota em colunas restantes
    if "nota" not in col_map:
        used = set(col_map.values())
        for c in df.columns:
            if c not in used:
                sample = df[c].dropna().astype(str).head(20)
                if sample.apply(lambda x: bool(_RE_ALPHA.search(x)) and x.upper() not in ("NAN", "NONE", "")).any():
                    col_map["nota"] = c
                    break

    records = []
    col_prod = col_map["produto"]
    col_qtd = col_map["qtd"]
    col_cod = col_map.get("codigo")
    col_nota = col_map.get("nota")

    for _, row in df.iterrows():
        produto = str(row.get(col_prod, "")).strip()
        if not produto or produto.upper() in ("NAN", "NONE", "TOTAL", "PRODUTO", "ROLLUP"):
            continue

        try:
            raw_val = row.get(col_qtd)
            if pd.isna(raw_val):
                continue
            qtd_sistema = int(float(raw_val))
            if qtd_sistema <= 0:
                continue
        except (ValueError, TypeError):
            continue

        codigo = ""
        if col_cod:
            codigo = str(row.get(col_cod, "")).strip()
            if codigo.upper() in ("NAN", "NONE", ""):
                codigo = ""
        if not codigo:
            codigo = "AUTO_" + _RE_NON_ALNUM.sub("", produto.upper())[:20]

        nota_raw = ""
        if col_nota:
            nota_raw = str(row.get(col_nota, "")).strip()
            if nota_raw.upper() in ("NAN", "NONE"):
                nota_raw = ""
            if _RE_ONLY_NUMBER.match(nota_raw):
                nota_raw = ""

        categoria = classify_product(produto)
        qtd_fisica, diferenca, obs, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo, "produto": produto, "categoria": categoria,
            "qtd_sistema": qtd_sistema, "qtd_fisica": qtd_fisica,
            "diferenca": diferenca, "nota": obs, "status": status,
        })

    return (True, records) if records else (False, "Nenhum dado válido na planilha de estoque.")


def parse_vendas_format(df_raw: pd.DataFrame) -> tuple:
    header_idx = _find_header(
        df_raw,
        lambda vals: "PRODUTO" in vals and ("QTDD" in " ".join(vals) or "VENDIDA" in " ".join(vals))
    )
    if header_idx is None:
        return (False, "Cabeçalho não encontrado no formato vendas.")

    df = df_raw.iloc[header_idx + 1:].copy()
    raw_cols = df_raw.iloc[header_idx].tolist()
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_cols)]

    col_grupo = col_produto = col_qtd_vendida = col_qtd_estoque = col_nota = None

    for c in df.columns:
        cu = c.upper().strip()
        if "GRUPO" in cu and not col_grupo:
            col_grupo = c
        elif cu == "PRODUTO" and not col_produto:
            col_produto = c
        elif "VENDIDA" in cu and not col_qtd_vendida:
            col_qtd_vendida = c
        elif "ESTOQUE" in cu and not col_qtd_estoque:
            col_qtd_estoque = c
        elif ("OBS" in cu or "NOTA" in cu or "ANOTA" in cu) and not col_nota:
            col_nota = c

    if not col_nota:
        for c in df.columns:
            if "CUSTO" in c.upper().strip():
                col_nota = c
                break

    if not col_produto:
        return (False, f"Coluna 'PRODUTO' não encontrada. Colunas: {list(df.columns)}")
    if not col_qtd_estoque and not col_qtd_vendida:
        return (False, "Nenhuma coluna de quantidade encontrada.")

    records = []
    zerados = []
    current_grupo = "OUTROS"

    for _, row in df.iterrows():
        if col_grupo:
            g = str(row.get(col_grupo, "")).strip()
            if g and g.upper() not in ("NAN", "NONE", ""):
                current_grupo = g

        raw_prod = str(row.get(col_produto, "")).strip()
        if not raw_prod or raw_prod.upper() in ("NAN", "NONE", "ROLLUP"):
            continue

        m = _RE_COD_PROD.match(raw_prod)
        if m:
            codigo, produto = m.group(1).strip(), m.group(2).strip()
        else:
            codigo = "AUTO_" + _RE_NON_ALNUM.sub("", raw_prod.upper())[:20]
            produto = raw_prod

        qtd_sistema = qtd_vendida_val = 0
        if col_qtd_estoque:
            try:
                val = row.get(col_qtd_estoque)
                if pd.notna(val):
                    qtd_sistema = int(float(val))
            except (ValueError, TypeError):
                pass
        if col_qtd_vendida:
            try:
                val = row.get(col_qtd_vendida)
                if pd.notna(val):
                    qtd_vendida_val = int(float(val))
            except (ValueError, TypeError):
                pass

        if qtd_sistema <= 0:
            if qtd_vendida_val > 0:
                zerados.append({
                    "codigo": codigo, "produto": produto,
                    "grupo": normalize_grupo(current_grupo),
                    "qtd_vendida": qtd_vendida_val, "qtd_estoque": 0,
                })
            continue

        nota_raw = ""
        if col_nota:
            nv = str(row.get(col_nota, "")).strip()
            if nv.upper() not in ("NAN", "NONE", "") and not _RE_ONLY_NUMBER.match(nv):
                nota_raw = nv

        categoria = normalize_grupo(current_grupo)
        if categoria in ("OUTROS", ""):
            categoria = classify_product(produto)

        qtd_fisica, diferenca, obs, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo, "produto": produto, "categoria": categoria,
            "qtd_sistema": qtd_sistema, "qtd_fisica": qtd_fisica,
            "diferenca": diferenca, "nota": obs, "status": status,
            "qtd_vendida": qtd_vendida_val,
        })

    return (True, records, zerados) if records else (False, "Nenhum dado válido na planilha de vendas.", [])


def parse_parcial_estoque(df_raw: pd.DataFrame) -> tuple:
    """Parser para planilha de estoque parcial do TOTVS BI (mini mestre).
    Atualiza apenas qtd_sistema dos produtos presentes. Não mexe em vendas."""
    header_idx = _find_header(
        df_raw,
        lambda vals: "PRODUTO" in vals and any("QUANTIDADE" in v for v in vals),
    )
    if header_idx is None:
        return (False, "Cabeçalho não encontrado. Preciso de colunas 'Produto' e 'QUANTIDADE'.")

    df = df_raw.iloc[header_idx + 1:].copy()
    raw_cols = df_raw.iloc[header_idx].tolist()
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(raw_cols)]

    col_map = {}
    for c in df.columns:
        cu = c.upper().strip()
        if cu in ("CÓDIGO", "CODIGO", "COD", "CÓDIGO") and "codigo" not in col_map:
            col_map["codigo"] = c
        elif cu == "PRODUTO" and "produto" not in col_map:
            col_map["produto"] = c
        elif "QUANTIDADE" in cu and "qtd" not in col_map:
            col_map["qtd"] = c
        elif "CUSTO" in cu and "nota" not in col_map:
            col_map["nota"] = c

    if "produto" not in col_map or "qtd" not in col_map:
        return (False, f"Colunas: {list(df.columns)} — falta 'Produto' ou 'QUANTIDADE'.")

    col_cod = col_map.get("codigo")
    col_prod = col_map["produto"]
    col_qtd = col_map["qtd"]
    col_nota = col_map.get("nota")

    records = []
    for _, row in df.iterrows():
        produto = str(row.get(col_prod, "")).strip()
        if not produto or produto.upper() in ("NAN", "NONE", "SUM", "ROLLUP", "TOTAL", "PRODUTO"):
            continue

        try:
            raw_val = row.get(col_qtd)
            if pd.isna(raw_val):
                continue
            qtd_sistema = int(float(raw_val))
            if qtd_sistema < 0:
                continue
        except (ValueError, TypeError):
            continue

        codigo = ""
        if col_cod:
            codigo = str(row.get(col_cod, "")).strip()
            if codigo.upper() in ("NAN", "NONE", ""):
                codigo = ""
        if not codigo:
            codigo = "AUTO_" + _RE_NON_ALNUM.sub("", produto.upper())[:20]

        nota_raw = ""
        if col_nota:
            nv = str(row.get(col_nota, "")).strip()
            if nv.upper() not in ("NAN", "NONE", "") and not _RE_ONLY_NUMBER.match(nv):
                nota_raw = nv

        categoria = classify_product(produto)
        qtd_fisica, diferenca, obs, status = parse_annotation(nota_raw, qtd_sistema)

        records.append({
            "codigo": codigo,
            "produto": produto,
            "categoria": categoria,
            "qtd_sistema": qtd_sistema,
            "qtd_fisica": qtd_fisica,
            "diferenca": diferenca,
            "nota": obs,
            "status": status,
        })

    return (True, records) if records else (False, "Nenhum dado válido na planilha de estoque parcial.")


def read_excel_to_records(uploaded_file) -> tuple:
    try:
        df_raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    except Exception as e:
        return (False, f"Erro ao ler arquivo: {e}", [])

    fmt = detect_format(df_raw)
    if fmt == "vendas":
        return parse_vendas_format(df_raw)
    elif fmt == "estoque":
        ok, result = parse_estoque_format(df_raw)
        return (ok, result, [])
    else:
        ok, result = parse_estoque_format(df_raw)
        if ok:
            return (ok, result, [])
        ok2, result2, zerados2 = parse_vendas_format(df_raw)
        if ok2:
            return (ok2, result2, zerados2)
        return (False, "Formato não reconhecido.", [])


# ══════════════════════════════════════════════════════════════════════════════
# UPLOADS — batch inserts + sync único no final
# ══════════════════════════════════════════════════════════════════════════════

def upload_mestre(records: list) -> tuple:
    """Recebe records já parseados (sem re-parsear o arquivo)."""
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")

        # Preservar divergências existentes antes de limpar o banco
        # Salva status E diferenca para recalcular qtd_fisica após o INSERT
        existing_div = {row[0]: (row[1], row[2]) for row in conn.execute(
            "SELECT codigo, status, diferenca FROM estoque_mestre WHERE status IN ('falta', 'sobra')"
        ).fetchall()}

        conn.execute("DELETE FROM estoque_mestre")

        # BATCH INSERT via executemany
        conn.executemany("""
            INSERT INTO estoque_mestre
                (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (r["codigo"], r["produto"], r["categoria"],
             r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
             r["nota"], r["status"], now, now)
            for r in records
        ])

        # Restaurar status e diferenca de divergência para produtos que já estavam divergentes.
        # qtd_fisica é recalculado como qtd_sistema + diferenca preservada.
        # (só sobrescreve se o novo upload não trouxe uma nova divergência)
        if existing_div:
            conn.executemany(
                """UPDATE estoque_mestre
                   SET status = ?,
                       diferenca = ?,
                       qtd_fisica = qtd_sistema + ?
                   WHERE codigo = ? AND status = 'ok'""",
                [(status, dif, dif, codigo) for codigo, (status, dif) in existing_div.items()]
            )

        n_div = conn.execute(
            "SELECT COUNT(*) FROM estoque_mestre WHERE status IN ('falta', 'sobra')"
        ).fetchone()[0]
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "MESTRE", "", len(records), len(records), 0, n_div])

        # Auto-cachear princípios ativos para todos os produtos do mestre
        _auto_cache_principios_ativos([r["produto"] for r in records], conn)

        conn.commit()
        sync_db()  # Sync UMA VEZ no final
        return (True, f"✅ Mestre: {len(records)} produtos ({n_div} divergências)")
    except Exception as e:
        return (False, f"❌ Erro: {e}")


def upload_parcial(records: list, zerados: list = None) -> tuple:
    """Recebe records já parseados e lista opcional de códigos com estoque zerado."""
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")

        # Buscar códigos existentes (1 query)
        existing = {row[0] for row in conn.execute("SELECT codigo FROM estoque_mestre").fetchall()}

        # Remover produtos que zeraram o estoque
        if zerados:
            codigos_zerados = [z["codigo"] if isinstance(z, dict) else z for z in zerados]
            codigos_remover = [c for c in codigos_zerados if c in existing]
            if codigos_remover:
                ph = ",".join(["?" for _ in codigos_remover])
                conn.execute(f"DELETE FROM estoque_mestre WHERE codigo IN ({ph})", codigos_remover)

        novos_data, update_data = [], []
        for r in records:
            # qtd_sistema aparece duas vezes: uma para atualizar, outra para o CASE de qtd_fisica
            row_data = (
                r["produto"], r["categoria"], r["qtd_sistema"],
                r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                r["nota"], r["status"], now, r["codigo"]
            )
            if r["codigo"] in existing:
                update_data.append(row_data)
            else:
                novos_data.append((
                    r["codigo"], r["produto"], r["categoria"],
                    r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                    r["nota"], r["status"], now, now
                ))

        # BATCH updates e inserts
        # Preserva status, diferenca e qtd_fisica para produtos com divergência existente.
        # qtd_fisica é recalculado como novo qtd_sistema + diferenca preservada, mantendo
        # a quantidade de falta/sobra anotada independente de novos uploads.
        if update_data:
            conn.executemany("""
                UPDATE estoque_mestre SET
                    produto=?, categoria=?, qtd_sistema=?,
                    qtd_fisica = CASE WHEN status IN ('falta', 'sobra') THEN ? + diferenca ELSE ? END,
                    diferenca = CASE WHEN status IN ('falta', 'sobra') THEN diferenca ELSE ? END,
                    nota=?,
                    status = CASE WHEN status IN ('falta', 'sobra') THEN status ELSE ? END,
                    ultima_contagem=?
                WHERE codigo=?
            """, update_data)

        if novos_data:
            conn.executemany("""
                INSERT INTO estoque_mestre
                    (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, novos_data)
            # Auto-cachear P.A. para produtos que entraram ou voltaram ao estoque
            _auto_cache_principios_ativos([r[1] for r in novos_data], conn)

        # Reposição loja
        n_repo = _detectar_reposicao_batch(records, conn, now)

        n_div = sum(1 for r in records if r["status"] != "ok")
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "PARCIAL", "", len(records), len(novos_data), len(update_data), n_div])
        upload_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        popular_contagem(records, upload_id, conn)

        conn.commit()
        sync_db()  # Sync UMA VEZ no final

        parts = [f"✅ Parcial: {len(records)} produtos"]
        if update_data:
            parts.append(f"{len(update_data)} atualizados")
        if novos_data:
            parts.append(f"{len(novos_data)} novos")
        if n_div:
            parts.append(f"{n_div} divergências")
        if n_repo:
            parts.append(f"🏪 {n_repo} para repor na loja")
        return (True, " · ".join(parts))
    except Exception as e:
        return (False, f"❌ Erro: {e}")


def upload_parcial_estoque(records: list) -> tuple:
    """Mini mestre — atualiza apenas quantidades dos produtos da planilha.
    Não mexe em vendas, reposição, nem remove produtos ausentes."""
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")

        existing = {row[0] for row in conn.execute("SELECT codigo FROM estoque_mestre").fetchall()}

        novos_data, update_data, update_nota_data = [], [], []
        for r in records:
            if r["codigo"] in existing:
                if r["nota"]:
                    # Tem anotação explícita: aplica nova divergência (sobrescreve)
                    update_nota_data.append((
                        r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                        r["nota"], r["status"], now, r["codigo"],
                    ))
                else:
                    # Sem anotação: preserva diferenca/qtd_fisica existentes se há divergência
                    # qtd_sistema aparece duas vezes: atualiza e serve para recalcular qtd_fisica
                    update_data.append((
                        r["qtd_sistema"], r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                        r["status"], now, r["codigo"],
                    ))
            else:
                novos_data.append((
                    r["codigo"], r["produto"], r["categoria"],
                    r["qtd_sistema"], r["qtd_fisica"], r["diferenca"],
                    r["nota"], r["status"], now, now,
                ))

        if update_data:
            conn.executemany("""
                UPDATE estoque_mestre SET
                    qtd_sistema=?,
                    qtd_fisica = CASE WHEN status IN ('falta', 'sobra') THEN ? + diferenca ELSE ? END,
                    diferenca = CASE WHEN status IN ('falta', 'sobra') THEN diferenca ELSE ? END,
                    status = CASE WHEN status IN ('falta', 'sobra') THEN status ELSE ? END,
                    ultima_contagem=?
                WHERE codigo=?
            """, update_data)

        if update_nota_data:
            conn.executemany("""
                UPDATE estoque_mestre SET
                    qtd_sistema=?, qtd_fisica=?, diferenca=?, nota=?,
                    status = CASE WHEN status IN ('falta', 'sobra') THEN status ELSE ? END,
                    ultima_contagem=?
                WHERE codigo=?
            """, update_nota_data)

        if novos_data:
            conn.executemany("""
                INSERT INTO estoque_mestre
                    (codigo, produto, categoria, qtd_sistema, qtd_fisica, diferenca, nota, status, ultima_contagem, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, novos_data)
            # Auto-cachear P.A. para produtos que entraram ou voltaram ao estoque
            _auto_cache_principios_ativos([r[1] for r in novos_data], conn)

        n_atualizados = len(update_data) + len(update_nota_data)
        n_div = sum(1 for r in records if r["status"] != "ok")
        conn.execute("""
            INSERT INTO historico_uploads (data, tipo, arquivo, total_produtos_lote, novos, atualizados, divergentes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [now, "PARCIAL_ESTOQUE", "", len(records), len(novos_data), n_atualizados, n_div])

        conn.commit()
        sync_db()

        parts = [f"✅ Parcial Estoque: {len(records)} produtos"]
        if n_atualizados:
            parts.append(f"{n_atualizados} atualizados")
        if novos_data:
            parts.append(f"{len(novos_data)} novos")
        if n_div:
            parts.append(f"{n_div} divergências")
        return (True, " · ".join(parts))
    except Exception as e:
        return (False, f"❌ Erro: {e}")


def popular_contagem(records: list, upload_id: int, conn) -> None:
    """Mantém itens pendentes anteriores e atualiza/insere itens do upload filtrados por categoria.

    - Se o produto já existe na lista (mesmo código): atualiza com dados mais recentes e volta para 'pendente'.
    - Se é produto novo: insere normalmente.
    - Itens pendentes não presentes no novo upload permanecem até serem confirmados.
    """
    now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
    itens_novos = [
        (upload_id, r["codigo"], r["produto"], r["categoria"],
         r["qtd_sistema"], "pendente", "", 0, now)
        for r in records
        if r["categoria"] in CATEGORIAS_CONTAGEM
    ]
    for item in itens_novos:
        uid, codigo, produto, categoria, qtd_estoque, status, motivo, qtd_div, reg_em = item
        existing = conn.execute(
            "SELECT id FROM contagem_itens WHERE codigo = ?", (codigo,)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE contagem_itens
                SET upload_id = ?, produto = ?, categoria = ?, qtd_estoque = ?,
                    status = 'pendente', motivo = '', qtd_divergencia = 0, registrado_em = ?
                WHERE codigo = ?
            """, (uid, produto, categoria, qtd_estoque, reg_em, codigo))
        else:
            conn.execute("""
                INSERT INTO contagem_itens
                    (upload_id, codigo, produto, categoria, qtd_estoque, status, motivo, qtd_divergencia, registrado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, item)


def get_contagem_itens() -> "pd.DataFrame":
    conn = get_db()
    rows = conn.execute("""
        SELECT id, upload_id, codigo, produto, categoria, qtd_estoque,
               status, motivo, qtd_divergencia, registrado_em
        FROM contagem_itens
        ORDER BY categoria, produto
    """).fetchall()
    cols = ["id", "upload_id", "codigo", "produto", "categoria", "qtd_estoque",
            "status", "motivo", "qtd_divergencia", "registrado_em"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def atualizar_item_contagem(
    item_id: int, status: str, motivo: str = "",
    qtd_divergencia: int = 0, codigo: str = "", qtd_sistema: int = 0,
    tipo_div: str = "falta"
) -> bool:
    """Atualiza item da contagem e reflete em estoque_mestre. Retorna True se atualizou estoque."""
    conn = get_db()
    now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
    rows_afetadas = 0

    conn.execute(
        "UPDATE contagem_itens SET status=?, motivo=?, qtd_divergencia=? WHERE id=?",
        [status, motivo, qtd_divergencia, item_id]
    )

    if codigo:
        if status == "divergencia":
            if tipo_div == "sobra":
                qtd_fisica = qtd_sistema + qtd_divergencia
                diferenca = qtd_divergencia
                status_estoque = "sobra"
            else:
                qtd_fisica = max(0, qtd_sistema - qtd_divergencia)
                diferenca = qtd_fisica - qtd_sistema
                status_estoque = "falta"
            cur = conn.execute("""
                UPDATE estoque_mestre SET
                    status = ?,
                    qtd_fisica = ?,
                    diferenca = ?,
                    nota = ?,
                    ultima_contagem = ?
                WHERE codigo = ?
            """, [status_estoque, qtd_fisica, diferenca, motivo, now, codigo])
            rows_afetadas = getattr(cur, "rowcount", -1)

        elif status == "certa":
            conn.execute("""
                UPDATE estoque_mestre SET
                    status = 'ok',
                    qtd_fisica = qtd_sistema,
                    diferenca = 0,
                    nota = '',
                    ultima_contagem = ?
                WHERE codigo = ? AND status IN ('falta', 'sobra')
            """, [now, codigo])

    # Só commit local — não chama sync_db() aqui para evitar que o pull
    # do Turso sobrescreva o write antes de ele ser confirmado no remoto.
    conn.commit()
    return rows_afetadas != 0


def limpar_contagem() -> None:
    """Apaga todos os itens da contagem atual."""
    conn = get_db()
    conn.execute("DELETE FROM contagem_itens")
    conn.commit()
    sync_db()


def _detectar_reposicao_batch(records: list, conn, now: str) -> int:
    """Detecta reposição em batch."""
    pending = {row[0] for row in conn.execute("SELECT codigo FROM reposicao_loja WHERE reposto = 0").fetchall()}
    to_insert = []

    for r in records:
        qtd_v = r.get("qtd_vendida", 0)
        if qtd_v <= 0:
            continue
        cat = str(r.get("categoria", "")).strip().upper()
        if cat in CATEGORIAS_EXCLUIDAS_REPOSICAO:
            continue
        if r["codigo"] in pending:
            continue
        to_insert.append((r["codigo"], r["produto"], r["categoria"], qtd_v, now))
        pending.add(r["codigo"])

    if to_insert:
        conn.executemany("""
            INSERT INTO reposicao_loja (codigo, produto, categoria, qtd_vendida, criado_em)
            VALUES (?, ?, ?, ?, ?)
        """, to_insert)

    return len(to_insert)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDADE — salvar/carregar lotes no banco
# ══════════════════════════════════════════════════════════════════════════════

def save_validade_lotes(df: pd.DataFrame) -> bool:
    """Substitui todos os lotes de validade no banco pela nova planilha."""
    try:
        conn = get_db()
        now = datetime.now(tz=_BRT).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("DELETE FROM validade_lotes")
        rows = []
        for _, r in df.iterrows():
            fab = r["FABRICACAO"].strftime("%Y-%m-%d") if pd.notna(r["FABRICACAO"]) else ""
            venc = r["VENCIMENTO"].strftime("%Y-%m-%d") if pd.notna(r["VENCIMENTO"]) else ""
            rows.append((
                str(r.get("FILIAL", "")),
                str(r["GRUPO"]),
                str(r["PRODUTO"]),
                str(r["LOTE"]),
                fab,
                venc,
                int(r["QUANTIDADE"]),
                float(r["VALOR"]),
                now,
            ))
        conn.executemany("""
            INSERT INTO validade_lotes
                (filial, grupo, produto, lote, fabricacao, vencimento, quantidade, valor, uploaded_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
        sync_db()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar validade: {e}")
        return False


def get_validade_lotes() -> pd.DataFrame:
    """Carrega todos os lotes de validade do banco."""
    cols = ["id", "filial", "grupo", "produto", "lote", "fabricacao", "vencimento",
            "quantidade", "valor", "uploaded_em"]
    try:
        rows = get_db().execute(
            "SELECT id, filial, grupo, produto, lote, fabricacao, vencimento, "
            "quantidade, valor, uploaded_em FROM validade_lotes"
        ).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=cols)
        df.columns = ["ID", "FILIAL", "GRUPO", "PRODUTO", "LOTE", "FABRICACAO",
                      "VENCIMENTO", "QUANTIDADE", "VALOR", "UPLOADED_EM"]
        df["FABRICACAO"] = pd.to_datetime(df["FABRICACAO"], errors="coerce")
        df["VENCIMENTO"] = pd.to_datetime(df["VENCIMENTO"], errors="coerce")
        df["QUANTIDADE"] = pd.to_numeric(df["QUANTIDADE"], errors="coerce").fillna(0).astype(int)
        df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce").fillna(0.0)
        return df
    except Exception:
        return pd.DataFrame()


def get_validade_upload_date() -> str:
    """Retorna a data do último upload de validade, ou string vazia."""
    try:
        row = get_db().execute(
            "SELECT uploaded_em FROM validade_lotes ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else ""
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# TREEMAP — otimizado com list join em vez de concatenação
# ══════════════════════════════════════════════════════════════════════════════

def sort_categorias(cats):
    mx = len(CATEGORIA_PRIORITY)
    return sorted(cats, key=lambda c: (_CAT_PRIORITY_MAP.get(c, mx), c))


# ══════════════════════════════════════════════════════════════════════════════
# MAPA VISUAL DO ARMAZÉM
# ══════════════════════════════════════════════════════════════════════════════

def _rack_html(paletes: dict, rua: str, face: str, highlight_keys: set = None) -> str:
    """
    Retorna HTML do grid de um rack com drag-and-drop.
    Ao soltar, injeta 'from|to' num st.text_input escondido no DOM pai
    via React nativeInputValueSetter (funciona com allow-same-origin).
    """
    COLUNAS = 13
    NIVEIS  = 4
    hl = highlight_keys or set()

    col_heads = '<div class="mr-row"><div class="mr-lvl"></div>'
    for c in range(1, COLUNAS + 1):
        col_heads += f'<div class="mr-chd">C{c}</div>'
    col_heads += '</div>'

    rows_html = ""
    for nivel in range(NIVEIS, 0, -1):
        rows_html += '<div class="mr-row">'
        rows_html += f'<div class="mr-lvl">N{nivel}</div>'
        for col in range(1, COLUNAS + 1):
            pk = f"{rua}-{face}-C{col}-N{nivel}"
            pk_j = pk.replace("'", "\\'")
            if pk in paletes:
                info    = paletes[pk]
                produto = info.get("produto", "")
                qtd     = info.get("quantidade", "")
                unidade = info.get("unidade", "")
                cor     = info.get("cor", "#4ade80")
                bg      = "#fbbf24" if pk in hl else cor
                short   = (produto[:9] + "…") if len(produto) > 10 else produto
                qty_str = f"{qtd} {unidade}".strip() if qtd is not None else ""
                rows_html += (
                    f'<div class="mr-cell occ" draggable="true"'
                    f' style="background:{bg};color:#0f172a;"'
                    f' title="↕ Arraste · {produto} — {qty_str}"'
                    f' ondragstart="dStart(event,\'{pk_j}\')"'
                    f' ondragover="event.preventDefault()"'
                    f' ondrop="dDrop(event,\'{pk_j}\')">'
                    f'<span class="mr-pname">{short}</span>'
                    f'<span class="mr-qty">{qty_str}</span>'
                    f'</div>'
                )
            else:
                rows_html += (
                    f'<div class="mr-cell emp" title="{pk}"'
                    f' ondragover="dOver(event,this)"'
                    f' ondragleave="dLeave(this)"'
                    f' ondrop="dDrop(event,\'{pk_j}\')">'
                    f'·</div>'
                )
        rows_html += '</div>'

    js = """<script>
function dStart(e,pk){
  e.dataTransfer.setData('text/plain',pk);
  e.dataTransfer.effectAllowed='move';
  e.currentTarget.style.opacity='0.4';
  setTimeout(()=>e.currentTarget.style.opacity='1',0);
}
function dOver(e,el){e.preventDefault();el.classList.add('dt');}
function dLeave(el){el.classList.remove('dt');}
function dDrop(e,tgt){
  e.preventDefault();
  document.querySelectorAll('.dt').forEach(c=>c.classList.remove('dt'));
  var src=e.dataTransfer.getData('text/plain');
  if(!src||src===tgt)return;
  try{
    var inp=window.parent.document.querySelector('input[placeholder="__rack_dnd__"]');
    if(inp){
      var setter=Object.getOwnPropertyDescriptor(
        window.parent.HTMLInputElement.prototype,'value').set;
      setter.call(inp,src+'|'+tgt);
      inp.dispatchEvent(new Event('input',{bubbles:true}));
    }
  }catch(err){console.warn('dnd signal:',err);}
}
</script>"""
    css = """<style>
body{margin:0;background:#0f172a;}
.mr-wrap{background:#0f172a;border-radius:10px;padding:12px 14px;overflow-x:auto;font-family:monospace;}
.mr-row{display:flex;gap:3px;margin-bottom:3px;align-items:center;}
.mr-lvl{width:22px;color:#475569;font-size:0.6rem;font-weight:700;text-align:right;flex-shrink:0;padding-right:4px;}
.mr-chd{width:54px;color:#334155;font-size:0.55rem;text-align:center;flex-shrink:0;}
.mr-cell{width:54px;height:48px;border-radius:5px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;flex-shrink:0;
  border:1px solid rgba(255,255,255,0.07);}
.mr-cell.emp{background:#1e293b;color:#334155;border-style:dashed;font-size:1rem;cursor:default;}
.mr-cell.occ{cursor:grab;transition:filter .15s,opacity .15s;}
.mr-cell.occ:hover{filter:brightness(1.2);}
.mr-cell.occ:active{cursor:grabbing;}
.mr-cell.dt{background:#1d4ed8!important;color:#fff!important;border:2px dashed #60a5fa!important;}
.mr-pname{font-size:0.48rem;font-weight:700;text-align:center;line-height:1.2;
  word-break:break-word;padding:0 2px;max-width:52px;overflow:hidden;}
.mr-qty{font-size:0.42rem;opacity:.75;margin-top:1px;}
</style>"""
    return f'{css}{js}<div class="mr-wrap">{col_heads}{rows_html}</div>'


def render_mapa_visual(conn):
    st.subheader("🏭 Mapa Visual do Armazém")

    # ── Seletores de rua e face ───────────────────────────────────────────────
    col_r, col_f = st.columns([2, 3])
    with col_r:
        rua = st.selectbox("Rua", ["R1", "R2", "R3", "R4", "R5", "R6"], key="mv_rua")
    with col_f:
        face_label = st.radio(
            "Face", ["A — Frente", "B — Fundo"],
            horizontal=True, key="mv_face",
        )
        face = face_label[0]   # "A" ou "B"

    # ── Busca inteligente (todas as ruas) ─────────────────────────────────────
    _est_rows = conn.execute(
        "SELECT produto FROM estoque_mestre ORDER BY produto"
    ).fetchall()
    est_prod_names = [r[0] for r in _est_rows if r[0]]

    search_prod = st.selectbox(
        "🔍 Buscar produto no armazém (todas as ruas)",
        options=est_prod_names,
        index=None,
        key="mv_search",
        placeholder="Digite o nome do produto…",
    )

    if search_prod:
        resultados = buscar_produto_todas_ruas(conn, search_prod)
        if resultados:
            st.success(
                f"**{len(resultados)}** posição(ões) encontrada(s) para *{search_prod}*:"
            )
            for loc in resultados:
                face_label_r = "Frente" if loc["face"] == "A" else "Fundo"
                qty_str = f"{loc['quantidade']} {loc['unidade']}".strip() if loc["quantidade"] is not None else ""
                st.markdown(
                    f'<div style="background:#1e293b;border:1px solid #1d4ed8;border-radius:8px;'
                    f'padding:8px 14px;margin-bottom:4px;display:flex;gap:16px;align-items:center;">'
                    f'<span style="color:#60a5fa;font-weight:700;font-size:0.85rem;">🏷 {loc["rua"]}-{loc["face"]}</span>'
                    f'<span style="color:#94a3b8;font-size:0.75rem;">{face_label_r}</span>'
                    f'<span style="color:#e0e6ed;font-size:0.8rem;">📍 Coluna {loc["coluna"]}, Nível {loc["nivel"]}</span>'
                    f'<span style="color:#64748b;font-size:0.75rem;">{qty_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.warning(f"Nenhuma posição encontrada para *{search_prod}* no armazém.")

    # ── Carrega paletes e produtos ────────────────────────────────────────────
    paletes  = get_paletes_rack(conn, rua, face)
    produtos = get_produtos_mapa(conn)

    # Destaca células do produto buscado no rack atual
    hl_keys: set = set()
    if search_prod:
        hl_keys = {
            loc["pos_key"]
            for loc in buscar_produto_todas_ruas(conn, search_prod)
            if loc["rua"] == rua and loc["face"] == face
        }

    # ── Grid interativo do rack (clique para mover) ────────────────────────
    picked = st.session_state.get("rack_picked_pk")
    n_occ  = len(paletes)

    # ── Grid visual do rack (HTML) ────────────────────────────────────────────
    n_occ = len(paletes)
    st.markdown(
        f"**Rack {rua}-{face}** — {n_occ} de 52 posições ocupadas "
        f"({round(n_occ / 52 * 100)}%)"
    )
    import streamlit.components.v1 as _stc
    _stc.html(_rack_html(paletes, rua, face, hl_keys), height=295, scrolling=False)

    # ── Mover palete ──────────────────────────────────────────────────────────
    _ocp_this = sorted(
        [f"{k} — {v['produto']}" for k, v in paletes.items()]
    )
    _ocp_all = sorted(
        [f"{k} — {v['produto']}" for k, v in get_todos_paletes(conn).items()]
    )
    with st.expander("↔️ Mover palete", expanded=False):
        _use_all = st.checkbox("Mostrar paletes de todos os racks", key="mv_all_racks",
                               value=not bool(_ocp_this))
        _opts = _ocp_all if (_use_all or not _ocp_this) else _ocp_this
        mv1, mv2, mv3, mv4, mv5 = st.columns([3, 2, 2, 2, 2])
        with mv1:
            _orig_sel = st.selectbox("De (origem)", _opts, key="qmv_orig",
                                     help="Posição atual do palete")
        _orig_pk = _orig_sel.split(" — ")[0].strip() if _orig_sel else ""
        _all_ruas  = ["R1","R2","R3","R4","R5","R6"]
        _all_faces = ["A","B"]
        with mv2:
            _dest_rua  = st.selectbox("Rua destino",  _all_ruas,  key="qmv_rua",
                                      index=_all_ruas.index(rua))
        with mv3:
            _dest_face = st.selectbox("Face destino", _all_faces, key="qmv_face",
                                      index=_all_faces.index(face))
        with mv4:
            _dest_col  = st.selectbox("Coluna", list(range(1, 14)), key="qmv_col")
        with mv5:
            _dest_niv  = st.selectbox("Nível", [4,3,2,1], key="qmv_niv",
                                      format_func=lambda n: f"N{n}")
        _dest_pk   = f"{_dest_rua}-{_dest_face}-C{_dest_col}-N{_dest_niv}"
        _dest_info = get_todos_paletes(conn).get(_dest_pk)
        if _dest_info:
            st.warning(f"Destino **{_dest_pk}** ocupado por *{_dest_info['produto']}* → será feito **swap**.")
        else:
            st.caption(f"Destino **{_dest_pk}** — vazio.")
        if st.button("↔️ Confirmar movimentação", key="qmv_btn",
                     disabled=(not _orig_pk or _orig_pk == _dest_pk)):
            try:
                mover_palete(conn, _orig_pk, _dest_pk)
                sync_db()
                st.success(f"✅ Palete movido: **{_orig_pk}** → **{_dest_pk}**.")
                st.rerun()
            except Exception as _e:
                st.error(str(_e))

    st.markdown("---")

    # ── Ações CRUD ────────────────────────────────────────────────────────────
    action_tab_add, action_tab_edit, action_tab_move, action_tab_del, action_tab_prod = st.tabs([
        "➕ Adicionar palete",
        "✏️ Editar palete",
        "↔️ Mover palete",
        "🗑️ Remover palete",
        "📦 Gerenciar produtos",
    ])

    # ── Adicionar ─────────────────────────────────────────────────────────────
    with action_tab_add:
        with st.expander("➕ Alocar produto em uma posição", expanded=False):
            ac1, ac2 = st.columns([2, 2])
            with ac1:
                col_add = st.selectbox("Coluna", list(range(1, 14)), key="add_col")
            with ac2:
                niv_add = st.selectbox("Nível", [4, 3, 2, 1], key="add_niv",
                                       format_func=lambda n: f"N{n} ({'topo' if n==4 else 'chão' if n==1 else str(n)})")

            prod_sel = st.selectbox(
                "Produto",
                options=est_prod_names,
                index=None,
                key="add_prod",
                placeholder="Digite o nome do produto…",
            )

            ac3, ac4 = st.columns([2, 2])
            with ac3:
                unid_default = prod_map.get(prod_sel, {}).get("unidade_pad", "L") if prod_sel else "L"
                qtd_add = st.number_input("Quantidade", min_value=0.0, step=1.0, value=1.0, key="add_qtd")
            with ac4:
                unid_add = st.selectbox("Unidade", ["L", "kg", "un", "cx", "sc", "fardo", "m³"],
                                        index=["L","kg","un","cx","sc","fardo","m³"].index(unid_default)
                                        if unid_default in ["L","kg","un","cx","sc","fardo","m³"] else 0,
                                        key="add_unid")

            pk_add = f"{rua}-{face}-C{col_add}-N{niv_add}"
            if pk_add in paletes:
                st.warning(f"⚠️ Posição **{pk_add}** já está ocupada por *{paletes[pk_add]['produto']}*. "
                           "Use **Editar palete** para substituir.")
            else:
                st.caption(f"Posição selecionada: **{pk_add}** (vazia)")

            if st.button("✅ Salvar palete", key="btn_add", disabled=(not prod_sel)):
                pid = add_produto_mapa(conn, prod_sel, unid_add)
                upsert_palete(conn, pk_add, pid, qtd_add, unid_add)
                sync_db()
                st.success(f"Palete alocado em **{pk_add}**.")
                st.rerun()

    # ── Editar ────────────────────────────────────────────────────────────────
    with action_tab_edit:
        st.markdown("##### Editar palete existente")
        if not paletes:
            st.info("Nenhum palete neste rack.")
        else:
            pos_opts = sorted(paletes.keys())
            pk_edit = st.selectbox("Posição", pos_opts, key="edit_pos",
                                   format_func=lambda k: f"{k} — {paletes[k]['produto']}")
            info_edit = paletes[pk_edit]
            cur_idx_edit = est_prod_names.index(info_edit["produto"]) if info_edit["produto"] in est_prod_names else None
            new_prod = st.selectbox(
                "Produto",
                options=est_prod_names,
                index=cur_idx_edit,
                key="edit_prod",
                placeholder="Digite o nome do produto…",
            )
            ec2, ec3 = st.columns([2, 2])
            with ec2:
                new_qtd = st.number_input("Quantidade", min_value=0.0, step=1.0,
                                          value=float(info_edit["quantidade"] or 1), key="edit_qtd")
            with ec3:
                _unid_opts = ["L", "kg", "un", "cx", "sc", "fardo", "m³"]
                _cur_unid = info_edit["unidade"] or "L"
                new_unid = st.selectbox("Unidade", _unid_opts,
                                        index=_unid_opts.index(_cur_unid) if _cur_unid in _unid_opts else 0,
                                        key="edit_unid")

            if st.button("💾 Salvar alterações", key="btn_edit", disabled=(not new_prod)):
                pid = add_produto_mapa(conn, new_prod, new_unid)
                upsert_palete(conn, pk_edit, pid, new_qtd, new_unid)
                sync_db()
                st.success(f"Palete **{pk_edit}** atualizado.")
                st.rerun()

    # ── Mover ─────────────────────────────────────────────────────────────────
    with action_tab_move:
        st.markdown("##### Mover ou trocar palete")
        if not paletes:
            st.info("Nenhum palete neste rack para mover.")
        else:
            mc1, mc2 = st.columns(2)
            with mc1:
                st.markdown("**Origem** (posição atual)")
                pos_opts = sorted(paletes.keys())
                pk_orig = st.selectbox("Posição de origem", pos_opts, key="move_orig",
                                       format_func=lambda k: f"{k} — {paletes[k]['produto']}")
                all_ruas   = ["R1", "R2", "R3", "R4", "R5", "R6"]
                all_faces  = ["A", "B"]
            with mc2:
                st.markdown("**Destino**")
                rua_dest  = st.selectbox("Rua destino",  all_ruas,  index=all_ruas.index(rua),  key="move_rua_d")
                face_dest = st.selectbox("Face destino", all_faces, index=all_faces.index(face), key="move_face_d")
                col_dest  = st.selectbox("Coluna destino", list(range(1, 14)), key="move_col_d")
                niv_dest  = st.selectbox("Nível destino", [4, 3, 2, 1], key="move_niv_d",
                                         format_func=lambda n: f"N{n}")

            pk_dest = f"{rua_dest}-{face_dest}-C{col_dest}-N{niv_dest}"
            todos_paletes = get_todos_paletes(conn)
            if pk_dest in todos_paletes:
                st.warning(f"Destino **{pk_dest}** está ocupado por *{todos_paletes[pk_dest]['produto']}* — será feito um **swap**.")
            else:
                st.info(f"Destino **{pk_dest}** está vazio.")

            if st.button("↔️ Confirmar movimentação", key="btn_move", disabled=(pk_orig == pk_dest)):
                try:
                    mover_palete(conn, pk_orig, pk_dest)
                    sync_db()
                    st.success(f"Palete movido: **{pk_orig}** → **{pk_dest}**.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # ── Remover ───────────────────────────────────────────────────────────────
    with action_tab_del:
        st.markdown("##### Remover palete de uma posição")
        if not paletes:
            st.info("Nenhum palete neste rack.")
        else:
            pos_opts = sorted(paletes.keys())
            pk_del = st.selectbox("Posição", pos_opts, key="del_pos",
                                  format_func=lambda k: f"{k} — {paletes[k]['produto']}")
            info_del = paletes[pk_del]
            st.markdown(
                f'<div style="background:#1e293b;border:1px solid #ef444444;border-radius:8px;padding:10px 14px;">'
                f'<b style="color:#f87171;">{pk_del}</b> · {info_del["produto"]} · '
                f'{info_del["quantidade"]} {info_del["unidade"]}</div>',
                unsafe_allow_html=True,
            )
            if st.button("🗑️ Confirmar remoção", key="btn_del", type="secondary"):
                delete_palete(conn, pk_del)
                sync_db()
                st.success(f"Posição **{pk_del}** esvaziada.")
                st.rerun()

    # ── Gerenciar produtos ────────────────────────────────────────────────────
    with action_tab_prod:
        st.markdown("##### Cadastro de produtos do mapa")

        pc1, pc2 = st.columns([4, 2])
        with pc1:
            novo_nome = st.text_input("Nome do produto", key="prod_nome")
        with pc2:
            nova_unid = st.selectbox("Unidade padrão", ["L", "kg", "un", "cx", "sc", "fardo", "m³"],
                                     key="prod_unid")
        if st.button("➕ Cadastrar produto", key="btn_add_prod", disabled=not novo_nome.strip()):
            pid = add_produto_mapa(conn, novo_nome.strip(), nova_unid)
            sync_db()
            st.success(f"Produto cadastrado (id: {pid}).")
            st.rerun()

        st.markdown("---")
        if produtos:
            st.markdown("**Produtos cadastrados:**")
            for p in produtos:
                pcol_name, pcol_cor, pcol_del = st.columns([5, 1, 1])
                with pcol_name:
                    st.markdown(
                        f'<span style="display:inline-block;width:12px;height:12px;border-radius:3px;'
                        f'background:{p["cor_hex"] or "#4ade80"};margin-right:6px;vertical-align:middle;"></span>'
                        f'<b>{p["nome"]}</b> <span style="color:#64748b;font-size:0.8rem;">({p["unidade_pad"]})</span>',
                        unsafe_allow_html=True,
                    )
                with pcol_del:
                    if st.button("🗑️", key=f"del_prod_{p['produto_id']}", help=f"Remover {p['nome']}"):
                        delete_produto_mapa(conn, p["produto_id"])
                        sync_db()
                        st.rerun()
        else:
            st.info("Nenhum produto cadastrado ainda.")

    # ── Heatmap de ocupação geral ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("##### Ocupação Geral do Armazém")

    ocupacao = get_ocupacao_geral(conn)
    total_ocp = sum(v[0] for v in ocupacao.values())
    total_pos = sum(v[1] for v in ocupacao.values())
    st.caption(f"Total: **{total_ocp}** paletes alocados de **{total_pos}** posições ({round(total_ocp/total_pos*100) if total_pos else 0}%)")

    ruas_hm  = ["R1", "R2", "R3", "R4", "R5", "R6"]
    faces_hm = ["A — Frente", "B — Fundo"]
    z_data   = []
    z_text   = []
    for r in ruas_hm:
        row_z, row_t = [], []
        for f in ["A", "B"]:
            ocp, tot = ocupacao.get((r, f), (0, 52))
            pct = round(ocp / tot * 100) if tot else 0
            row_z.append(pct)
            row_t.append(f"{pct}%\n({ocp}/{tot})")
        z_data.append(row_z)
        z_text.append(row_t)

    fig_hm = go.Figure(
        data=go.Heatmap(
            z=z_data,
            x=faces_hm,
            y=ruas_hm,
            colorscale=[[0, "#1e293b"], [0.4, "#854d0e"], [0.75, "#f59e0b"], [1, "#22c55e"]],
            zmin=0, zmax=100,
            text=z_text,
            texttemplate="%{text}",
            showscale=True,
            colorbar=dict(
                title=dict(text="% ocup.", font=dict(color="#94a3b8")),
                ticksuffix="%",
                len=0.85,
                tickfont=dict(color="#94a3b8"),
            ),
        )
    )
    fig_hm.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#94a3b8", size=12),
        margin=dict(l=50, r=60, t=30, b=20),
        height=310,
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig_hm, use_container_width=True)


def build_css_treemap(df: pd.DataFrame, filter_cat: str = "TODOS", avarias_map: dict = None) -> str:
    if df.empty:
        return '<div style="color:#64748b;text-align:center;padding:40px;">Nenhum produto para exibir</div>'

    if filter_cat != "TODOS":
        df = df[df["categoria"] == filter_cat]
    if df.empty:
        return '<div style="color:#64748b;text-align:center;padding:40px;">Nenhum produto nesta categoria</div>'

    if avarias_map is None:
        avarias_map = {}

    # Agrupar por categoria
    categories = {}
    for _, row in df.iterrows():
        categories.setdefault(row["categoria"], []).append(row)

    parts = []
    for cat in sort_categorias(list(categories.keys())):
        rows = categories[cat]
        prods = []

        for r in sorted(rows, key=lambda x: str(x["produto"])):
            qs = int(r["qtd_sistema"])
            qf = int(r["qtd_fisica"]) if pd.notnull(r.get("qtd_fisica")) else qs
            diff = int(r["diferenca"]) if pd.notnull(r.get("diferenca")) else 0

            if diff == 0:
                bg, txt = "#00d68f", "#0a2e1a"
                data_diff = ""
            elif diff < 0:
                bg, txt = "#ff4757", "#fff"
                data_diff = f'data-diff="▼{abs(diff)}"'
            else:
                bg, txt = "#ffa502", "#fff"
                data_diff = f'data-diff="▲{diff}"'
            info = str(qs)

            contagem = str(r.get("ultima_contagem", ""))
            border = "border:2px dashed #64748b!important;opacity:0.6;" if not contagem or contagem in ("", "nan", "None") else ""

            # Aviso de avarias abertas
            qtd_av = avarias_map.get(str(r["codigo"]), 0)
            if qtd_av > 0:
                bg, txt = "#a55eea", "#fff"
                av_html = f'<div class="tm-av">⚠ {qtd_av} av.</div>'
            else:
                av_html = ""

            prods.append(
                f'<div class="tm-tile" tabindex="0" {data_diff} style="background:{bg};color:{txt};'
                f'border:1px solid rgba(0,0,0,0.1);{border}" title="{r["codigo"]} — {r["produto"]}">'
                f'<div class="tm-name">{short_name(r["produto"])}</div>'
                f'<div class="tm-info">{info}</div>'
                f'<div class="tm-cod">{r["codigo"]}</div>'
                f'{av_html}'
                f'<div class="tm-popup"><div class="tm-popup-code">{r["codigo"]}</div>{r["produto"]}</div>'
                f'</div>'
            )

        parts.append(
            f'<div style="width:100%;background:#111827;border-radius:8px;padding:8px;'
            f'margin-bottom:8px;border:1px solid #1e293b;">'
            f'<div style="font-size:0.75rem;color:#64748b;font-weight:700;text-transform:uppercase;'
            f'margin-bottom:6px;border-bottom:1px solid #1e293b;padding-bottom:4px;">'
            f'{cat} <span style="font-size:0.6rem;color:#4a5568;font-weight:400;">({len(rows)})</span></div>'
            f'<div class="tm-wrap">{"".join(prods)}</div></div>'
        )

    return f'<div style="display:flex;flex-direction:column;min-height:450px;">{"".join(parts)}</div>'


# ══════════════════════════════════════════════════════════════════════════════
# VENDAS — salvar/carregar dados de vendas para gráficos
# ══════════════════════════════════════════════════════════════════════════════

def save_vendas_historico(records: list, grupo_map: dict, zerados: list = None, is_mestre: bool = False, data_ref: str = None):
    """Salva dados de vendas no histórico para gráficos.
    - MESTRE: substitui tudo (carga completa)
    - PARCIAL: SUBSTITUI por dia — cada dia gera uma linha separada por produto.
      Se já existe registro para (codigo, data_ref) substitui qtd_vendida pelo valor mais recente.
    - data_ref: data no formato "YYYY-MM-DD". Se None, usa a data atual (horário Brasília).
    """
    try:
        conn = get_db()
        hoje = data_ref if data_ref else datetime.now(tz=_BRT).date().isoformat()  # "YYYY-MM-DD" — chave do dia

        if is_mestre:
            conn.execute("DELETE FROM vendas_historico")
            rows = []
            for r in records:
                rows.append((r["codigo"], r["produto"],
                             r.get("categoria", "OUTROS"),
                             r.get("qtd_vendida", 0),
                             r.get("qtd_sistema", 0), hoje))
            if zerados:
                for z in zerados:
                    if isinstance(z, dict):
                        rows.append((z["codigo"], z["produto"],
                                     z.get("grupo", "OUTROS"),
                                     z.get("qtd_vendida", 0), 0, hoje))
            if rows:
                conn.executemany("""
                    INSERT INTO vendas_historico
                        (codigo, produto, grupo, qtd_vendida, qtd_estoque, data_upload)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, rows)
        else:
            # ── PARCIAL: substitui dia a dia ─────────────────────────────
            # Descobre quais códigos já têm registro HOJE
            todos_records = list(records or []) + [z for z in (zerados or []) if isinstance(z, dict)]
            if not todos_records:
                conn.commit()
                sync_db()
                return

            codigos_hoje_rows = conn.execute(
                "SELECT codigo FROM vendas_historico WHERE data_upload = ?", (hoje,)
            ).fetchall()
            codigos_hoje = {r[0] for r in codigos_hoje_rows}

            updates, inserts = [], []
            for r in todos_records:
                cod  = r["codigo"]
                prod = r.get("produto", cod)
                grp  = r.get("categoria") or r.get("grupo", "OUTROS")
                qtdv = r.get("qtd_vendida", 0)
                qtde = r.get("qtd_sistema", 0)
                if cod in codigos_hoje:
                    updates.append((qtdv, qtde, cod, hoje))
                else:
                    inserts.append((cod, prod, grp, qtdv, qtde, hoje))
                    codigos_hoje.add(cod)   # evita duplicar na mesma chamada

            if updates:
                conn.executemany("""
                    UPDATE vendas_historico
                       SET qtd_vendida = ?,
                           qtd_estoque = ?
                     WHERE codigo = ? AND data_upload = ?
                """, updates)
            if inserts:
                conn.executemany("""
                    INSERT INTO vendas_historico
                        (codigo, produto, grupo, qtd_vendida, qtd_estoque, data_upload)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, inserts)

        conn.commit()
        sync_db()
    except Exception:
        pass


def get_vendas_historico() -> pd.DataFrame:
    """Retorna vendas ACUMULADAS por produto (soma de todos os dias)."""
    try:
        rows = get_db().execute("""
            SELECT v.codigo, v.produto, v.grupo,
                   SUM(v.qtd_vendida)  AS qtd_vendida,
                   COALESCE(
                       (SELECT em.qtd_sistema FROM estoque_mestre em WHERE em.codigo = v.codigo),
                       (SELECT v2.qtd_estoque
                          FROM vendas_historico v2
                         WHERE v2.codigo = v.codigo
                         ORDER BY v2.data_upload DESC
                         LIMIT 1)
                   )                   AS qtd_estoque,
                   MAX(v.data_upload)  AS data_upload
              FROM vendas_historico v
             GROUP BY v.codigo
             ORDER BY SUM(v.qtd_vendida) DESC
        """).fetchall()
        if rows:
            return pd.DataFrame(rows, columns=["codigo", "produto", "grupo", "qtd_vendida", "qtd_estoque", "data_upload"])
    except Exception:
        pass
    return pd.DataFrame()


def get_periodo_vendas() -> int:
    """Retorna o número de dias distintos com vendas registradas."""
    try:
        row = get_db().execute(
            "SELECT COUNT(DISTINCT data_upload) FROM vendas_historico"
        ).fetchone()
        if row and row[0]:
            return max(int(row[0]), 1)
    except Exception:
        pass
    return 1


def get_vendas_por_dia() -> pd.DataFrame:
    """Retorna total de unidades vendidas por dia (para o gráfico de histórico).

    Lonas/filmes com dimensões no nome são convertidos de m² para unidades
    antes de somar por dia.
    """
    try:
        rows = get_db().execute("""
            SELECT data_upload AS dia,
                   codigo,
                   produto,
                   grupo,
                   SUM(qtd_vendida) AS qtd_vendida
              FROM vendas_historico
             GROUP BY data_upload, codigo
             ORDER BY data_upload ASC
        """).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["dia", "codigo", "produto", "grupo", "qtd_vendida"])

            def _conv(r):
                if r["grupo"] == "LONAS":
                    m = _RE_LONA_DIM.search(str(r["produto"]))
                    if m:
                        area = (float(m.group(1).replace(",", "."))
                                * float(m.group(2).replace(",", ".")))
                        if area > 0:
                            return max(1, round(r["qtd_vendida"] / area))
                return r["qtd_vendida"]

            df["qtd_vendida"] = df.apply(_conv, axis=1)
            df_dia = df.groupby("dia", as_index=False).agg(
                total_vendido=("qtd_vendida", "sum"),
                produtos_vendidos=("codigo", "nunique"),
            )
            df_dia["dia"] = pd.to_datetime(df_dia["dia"]).dt.date
            return df_dia
    except Exception:
        pass
    return pd.DataFrame()


_RE_LONA_DIM = re.compile(r'(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)')


def get_top_produtos_historico(top_n: int = 15) -> pd.DataFrame:
    """Retorna os top N produtos mais vendidos no período acumulado.

    Para lonas/filmes agrícolas cujo nome contém dimensões (ex: 10x50),
    o total em m² é convertido para unidades (rolos) dividindo pela área.
    Lonas sem dimensões no nome permanecem com contagem por unidade.
    """
    try:
        rows = get_db().execute("""
            SELECT produto, grupo, SUM(qtd_vendida) AS total
              FROM vendas_historico
             GROUP BY codigo
             ORDER BY total DESC
        """).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["produto", "grupo", "total"])

            def _ajustar_lona(r):
                if r["grupo"] == "LONAS":
                    m = _RE_LONA_DIM.search(r["produto"])
                    if m:
                        area = (float(m.group(1).replace(",", "."))
                                * float(m.group(2).replace(",", ".")))
                        if area > 0:
                            return max(1, round(r["total"] / area))
                return r["total"]

            df["total"] = df.apply(_ajustar_lona, axis=1)
            return df.nlargest(top_n, "total").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# INFOGRÁFICOS — funções de dados
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_datas_vendas_range() -> tuple:
    """Retorna (data_min, data_max) das vendas registradas."""
    try:
        row = get_db().execute(
            "SELECT MIN(data_upload), MAX(data_upload) FROM vendas_historico"
        ).fetchone()
        if row and row[0] and row[1]:
            return date.fromisoformat(row[0]), date.fromisoformat(row[1])
    except Exception:
        pass
    hoje = datetime.now(tz=_BRT).date()
    return hoje - timedelta(days=30), hoje


@st.cache_data(ttl=600)
def get_grupos_vendas() -> list:
    """Retorna lista de grupos únicos na tabela de vendas."""
    try:
        rows = get_db().execute(
            "SELECT DISTINCT grupo FROM vendas_historico ORDER BY grupo"
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_vendas_heatmap(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Retorna vendas por produto e dia da semana para o heatmap."""
    try:
        rows = get_db().execute("""
            SELECT codigo, produto, grupo, SUM(qtd_vendida) AS qtd_vendida, data_upload
            FROM vendas_historico
            WHERE data_upload >= ? AND data_upload <= ?
            GROUP BY codigo, data_upload
        """, (data_inicio, data_fim)).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["codigo", "produto", "grupo", "qtd_vendida", "data_upload"])
            df["data_upload"] = pd.to_datetime(df["data_upload"])
            df["dia_semana"] = df["data_upload"].dt.dayofweek  # 0=Seg, 6=Dom
            # Normaliza filmes agrícolas de m² para unidades (rolos)
            areas = df["produto"].apply(_area_filme)
            df["qtd_vendida"] = (df["qtd_vendida"] / areas).round().astype(int)
            top20_codigos = df.groupby("codigo")["qtd_vendida"].sum().nlargest(20).index
            df = df[df["codigo"].isin(top20_codigos)]
            return df.groupby(["produto", "dia_semana"], as_index=False)["qtd_vendida"].sum()
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=300)
def get_mais_menos_movimentados(data_inicio: str, data_fim: str, grupo: str = "Todos") -> pd.DataFrame:
    """Retorna produtos ordenados por volume de vendas no período (excluindo zerados)."""
    try:
        if grupo != "Todos":
            rows = get_db().execute("""
                SELECT codigo, produto, grupo, SUM(qtd_vendida) AS total_vendido
                FROM vendas_historico
                WHERE data_upload >= ? AND data_upload <= ?
                  AND grupo = ?
                GROUP BY codigo
                HAVING total_vendido > 0
                ORDER BY total_vendido DESC
            """, (data_inicio, data_fim, grupo)).fetchall()
        else:
            rows = get_db().execute("""
                SELECT codigo, produto, grupo, SUM(qtd_vendida) AS total_vendido
                FROM vendas_historico
                WHERE data_upload >= ? AND data_upload <= ?
                GROUP BY codigo
                HAVING total_vendido > 0
                ORDER BY total_vendido DESC
            """, (data_inicio, data_fim)).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["codigo", "produto", "grupo", "total_vendido"])
            df = _normalizar_qtd_filme(df)
            df = df[df["total_vendido"] > 0].sort_values("total_vendido", ascending=False)
            return df.reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=300)
def get_produtos_parados(dias_min: int) -> pd.DataFrame:
    """Retorna produtos sem movimentação de vendas há mais de X dias."""
    try:
        hoje = datetime.now(tz=_BRT).date()
        rows = get_db().execute("""
            SELECT
                e.codigo,
                e.produto,
                e.categoria AS grupo,
                e.qtd_sistema AS qtd_estoque,
                COALESCE(MAX(v.data_upload), '') AS ultima_venda
            FROM estoque_mestre e
            LEFT JOIN vendas_historico v ON v.codigo = e.codigo
            WHERE e.qtd_sistema > 0
            GROUP BY e.codigo
        """).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["codigo", "produto", "grupo", "qtd_estoque", "ultima_venda"])

        # Valor imobilizado via validade_lotes (best-effort join)
        try:
            vl_rows = get_db().execute(
                "SELECT produto, SUM(valor) FROM validade_lotes GROUP BY produto"
            ).fetchall()
            vl_map = {r[0].strip().upper(): float(r[1] or 0) for r in vl_rows if r[0]}
        except Exception:
            vl_map = {}

        df["valor_imobilizado"] = df["produto"].apply(lambda p: vl_map.get(str(p).strip().upper(), 0.0))

        def _dias(ultima: str) -> int:
            if not ultima:
                return 9999
            try:
                return (hoje - date.fromisoformat(ultima)).days
            except Exception:
                return 9999

        df["dias_parado"] = df["ultima_venda"].apply(_dias)
        df = df[df["dias_parado"] >= dias_min].copy()

        def _fmt_data(s: str) -> str:
            if not s:
                return "Nunca"
            try:
                return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                return s

        df["ultima_venda_fmt"] = df["ultima_venda"].apply(_fmt_data)
        return df.sort_values("valor_imobilizado", ascending=False).reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=300)
def get_giro_ruptura_grupos(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Retorna taxa de giro e % de ruptura por grupo de produtos."""
    try:
        rows = get_db().execute("""
            SELECT
                grupo,
                SUM(qtd_vendida) AS total_vendido,
                AVG(CASE WHEN qtd_estoque <= 0 THEN 1.0 ELSE 0.0 END) AS pct_ruptura_raw
            FROM vendas_historico
            WHERE data_upload >= ? AND data_upload <= ?
            GROUP BY grupo
        """, (data_inicio, data_fim)).fetchall()

        stock_rows = get_db().execute("""
            SELECT categoria AS grupo, SUM(qtd_sistema) AS qtd_estoque
            FROM estoque_mestre
            GROUP BY categoria
        """).fetchall()
        stock_map = {r[0]: (r[1] or 0) for r in stock_rows}

        try:
            valor_rows = get_db().execute(
                "SELECT grupo, SUM(valor) FROM validade_lotes GROUP BY grupo"
            ).fetchall()
            valor_map = {r[0]: float(r[1] or 0) for r in valor_rows if r[0]}
        except Exception:
            valor_map = {}

        if rows:
            records = []
            for grupo, total_vendido, pct_ruptura_raw in rows:
                qtd_estoque = max(stock_map.get(grupo, 0), 1)
                taxa_giro = round(float(total_vendido) / qtd_estoque, 3)
                pct_ruptura = round(float(pct_ruptura_raw or 0) * 100, 1)
                valor = valor_map.get(grupo, 0) or float(stock_map.get(grupo, 0))
                records.append({
                    "grupo": grupo,
                    "taxa_giro": taxa_giro,
                    "pct_ruptura": pct_ruptura,
                    "total_vendido": int(total_vendido),
                    "qtd_estoque": qtd_estoque,
                    "valor_estoque": valor,
                })
            return pd.DataFrame(records)
    except Exception:
        pass
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS — normalização de quantidades
# ══════════════════════════════════════════════════════════════════════════════

def _area_filme(produto: str) -> int:
    """Retorna a área (m²) de um rolo de filme a partir do nome do produto.
    Ex: 'FILME AGRICOLA 200MICR 12X50M' → 600.
    Retorna 1 para produtos que não são filmes com dimensão no nome."""
    if "FILME" not in produto.upper():
        return 1
    m = re.search(r"(\d+)[Xx](\d+)M", produto)
    if m:
        area = int(m.group(1)) * int(m.group(2))
        return area if area > 0 else 1
    return 1


def _normalizar_qtd_filme(df: pd.DataFrame, col_produto: str = "produto", col_qtd: str = "total_vendido") -> pd.DataFrame:
    """Divide qtd_vendida pela área do rolo para obter unidades reais de filme agrícola."""
    if df.empty:
        return df
    df = df.copy()
    areas = df[col_produto].apply(_area_filme)
    df[col_qtd] = (df[col_qtd] / areas).round().astype(int)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY — tema dark consistente com o dashboard
# ══════════════════════════════════════════════════════════════════════════════

_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans, Outfit, sans-serif", color="#e0e6ed", size=11),
    margin=dict(l=10, r=10, t=40, b=10),
    transition=dict(duration=800, easing="cubic-in-out"),
)

_DEFAULT_LEGEND = dict(
    bgcolor="rgba(17,24,39,0.8)", bordercolor="#1e293b", borderwidth=1,
    font=dict(size=10, color="#94a3b8"),
)

_GROUP_COLORS = {
    "HERBICIDAS": "#3b82f6", "INSETICIDAS": "#00d68f",
    "ADUBOS FOLIARES": "#a55eea", "ADUBOS QUÍMICOS": "#8b5cf6",
    "FUNGICIDAS": "#ffa502", "MATURADORES": "#06b6d4",
    "BIOLOGICOS E INOCULANTES": "#10b981", "SEMENTES DE MILHO": "#f59e0b",
    "SUPLEMENTO MINERAL": "#ec4899", "LONAS": "#6366f1",
    "ANTIBIOTICOS/ANTI-INFLAMATORIO": "#f472b6",
    "ACESSORIOS DE CERCA ELETRICA": "#818cf8",
    "ADJUVANTES/ESPALHANTES ADESIVO": "#2dd4bf",
}


def _get_color(grupo: str) -> str:
    return _GROUP_COLORS.get(grupo, "#64748b")


def build_vendas_tab(df_vendas: pd.DataFrame):
    """Renderiza a aba completa de gráficos de vendas."""
    if df_vendas.empty:
        st.info("📊 Nenhum dado de vendas carregado ainda. Faça upload de uma planilha de vendas para ativar os gráficos.")
        return

    _periodo_vendas = get_periodo_vendas()

    # ── Converter lonas com dimensões de m² → unidades antes de agregar ──
    df_vendas = df_vendas.copy()

    def _conv_lona(r):
        if r["grupo"] == "LONAS":
            m = _RE_LONA_DIM.search(str(r["produto"]))
            if m:
                area = (float(m.group(1).replace(",", "."))
                        * float(m.group(2).replace(",", ".")))
                if area > 0:
                    return max(1, round(r["qtd_vendida"] / area))
        return r["qtd_vendida"]

    df_vendas["qtd_vendida"] = df_vendas.apply(_conv_lona, axis=1)

    # ── Dados agregados por grupo ────────────────────────────────────────
    df_grupo = df_vendas.groupby("grupo", as_index=False).agg(
        qtd_vendida=("qtd_vendida", "sum"),
        qtd_estoque=("qtd_estoque", "sum"),
        produtos=("codigo", "nunique"),
    ).sort_values("qtd_vendida", ascending=False)

    total_vendido = int(df_grupo["qtd_vendida"].sum())
    total_estoque = int(df_grupo["qtd_estoque"].sum())
    total_skus = int(df_vendas["codigo"].nunique())
    n_zerados = int((df_vendas["qtd_estoque"] <= 0).sum())
    pct_ruptura = round((n_zerados / max(total_skus, 1)) * 100)

    # ── KPIs ─────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="stat-value">{total_vendido:,}</div><div class="stat-label">Vendidos</div></div>
        <div class="stat-card"><div class="stat-value blue">{total_skus}</div><div class="stat-label">Produtos</div></div>
        <div class="stat-card"><div class="stat-value red">{n_zerados}</div><div class="stat-label">Zerados</div></div>
        <div class="stat-card"><div class="stat-value amber">{pct_ruptura}%</div><div class="stat-label">Ruptura</div></div>
    </div>
    """.replace(",", "."), unsafe_allow_html=True)

    # ── Sub-tabs de gráficos ─────────────────────────────────────────────
    vt1, vt2, vt3, vt4 = st.tabs(["📊 Por Grupo", "🚨 Estoque Crítico", "🔥 Taxa de Giro", "🏆 Top Produtos"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — VENDAS POR GRUPO
    # ══════════════════════════════════════════════════════════════════════
    with vt1:
        top_n = min(14, len(df_grupo))
        df_top = df_grupo.head(top_n)

        # Bar chart horizontal — vendas por grupo
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=df_top["grupo"], x=df_top["qtd_vendida"],
            orientation="h",
            marker=dict(
                color=[_get_color(g) for g in df_top["grupo"]],
                line=dict(width=0),
                cornerradius=4,
            ),
            text=df_top["qtd_vendida"].apply(lambda v: f"{v:,.0f}".replace(",", ".")),
            textposition="outside", textfont=dict(size=10, color="#94a3b8"),
            hovertemplate="<b>%{y}</b><br>Vendido: %{x:,.0f}<extra></extra>",
        ))
        fig_bar.update_layout(
            **_PLOTLY_LAYOUT,
            title=dict(text="Quantidade Vendida por Grupo", font=dict(size=14, color="#e0e6ed")),
            height=max(350, top_n * 32),
            yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="#1e293b", title=None),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

        # Dois gráficos lado a lado
        c1, c2 = st.columns(2)

        with c1:
            # Donut — distribuição %
            fig_pie = go.Figure(go.Pie(
                labels=df_top["grupo"].head(8),
                values=df_top["qtd_vendida"].head(8),
                hole=0.55,
                marker=dict(colors=[_get_color(g) for g in df_top["grupo"].head(8)]),
                textinfo="percent",
                textfont=dict(size=10, color="#e0e6ed"),
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} un<br>%{percent}<extra></extra>",
            ))
            fig_pie.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Distribuição % Vendas", font=dict(size=13, color="#94a3b8")),
                height=320, showlegend=True,
                legend=dict(font=dict(size=9), orientation="h", y=-0.15),
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

        with c2:
            # Grouped bar — vendido vs estoque
            fig_vs = go.Figure()
            df8 = df_top.head(8)
            fig_vs.add_trace(go.Bar(
                name="Vendido", x=df8["grupo"], y=df8["qtd_vendida"],
                marker=dict(color="#00d68f", cornerradius=3, opacity=0.85),
            ))
            fig_vs.add_trace(go.Bar(
                name="Estoque", x=df8["grupo"], y=df8["qtd_estoque"],
                marker=dict(color="#3b82f6", cornerradius=3, opacity=0.5),
            ))
            fig_vs.update_layout(
                **_PLOTLY_LAYOUT, barmode="group",
                title=dict(text="Vendido vs Estoque", font=dict(size=13, color="#94a3b8")),
                height=320,
                xaxis=dict(tickangle=-35, tickfont=dict(size=8), gridcolor="rgba(0,0,0,0)"),
                legend=dict(orientation="h", y=1.12, font=dict(size=10)),
            )
            st.plotly_chart(fig_vs, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — ESTOQUE CRÍTICO
    # ══════════════════════════════════════════════════════════════════════
    with vt2:
        # Produtos com estoque zerado que venderam
        df_zero = df_vendas[(df_vendas["qtd_estoque"] <= 0) & (df_vendas["qtd_vendida"] > 0)].sort_values("qtd_vendida", ascending=False)

        # Remover duplicatas: produtos zerados que têm equivalente com estoque
        # (mesmo produto cadastrado com código diferente que ainda tem estoque)
        _PREFIXOS_CATEGORIA = {
            "HERBICIDA", "FUNGICIDA", "INSETICIDA", "ACARICIDA", "NEMATICIDA",
            "ADJUVANTE", "FERTILIZANTE", "REGULADOR", "ESTIMULANTE", "INOCULANTE",
            "SEMENTE", "SEM", "BIOLOGICO", "BIOLÓGICO", "ADUBO", "DEFENSIVO",
            "MICRONUTRIENTE", "ENXOFRE", "CALCARIO", "CALCÁRIO",
        }

        def _core_nome(nome: str) -> str:
            palavras = nome.upper().strip().split()
            while palavras and palavras[0] in _PREFIXOS_CATEGORIA:
                palavras = palavras[1:]
            return " ".join(palavras)

        try:
            _em_rows = get_db().execute(
                "SELECT produto FROM estoque_mestre WHERE qtd_sistema > 0"
            ).fetchall()
            _em_cores = {_core_nome(r[0]) for r in _em_rows if r[0]}
            if _em_cores:
                def _tem_duplicata_com_estoque(nome: str) -> bool:
                    core = _core_nome(nome)
                    if not core or len(core) < 6:
                        return False
                    if core in _em_cores:
                        return True
                    for em_core in _em_cores:
                        if len(em_core) >= 6 and (core in em_core or em_core in core):
                            return True
                    return False
                df_zero = df_zero[~df_zero["produto"].apply(_tem_duplicata_com_estoque)]
        except Exception:
            pass
        # Produtos com estoque < 50% do vendido
        df_crit = df_vendas[
            (df_vendas["qtd_estoque"] > 0) &
            (df_vendas["qtd_estoque"] < df_vendas["qtd_vendida"] * 0.5) &
            (df_vendas["qtd_vendida"] > 10)
        ].copy()
        # Ordenar por dias de cobertura (menor = mais urgente)
        df_crit["dias_cobertura"] = df_crit["qtd_estoque"] / (df_crit["qtd_vendida"] / 30)
        df_crit = df_crit.sort_values("dias_cobertura", ascending=True)

        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            st.markdown(f"""<div class="stat-card"><div class="stat-value red">{len(df_zero)}</div>
            <div class="stat-label">💀 Zerados c/ vendas</div></div>""", unsafe_allow_html=True)
        with kc2:
            st.markdown(f"""<div class="stat-card"><div class="stat-value amber">{len(df_crit)}</div>
            <div class="stat-label">🔥 Crítico &lt;50%</div></div>""", unsafe_allow_html=True)
        with kc3:
            total_alert = len(df_zero) + len(df_crit)
            st.markdown(f"""<div class="stat-card"><div class="stat-value purple">{total_alert}</div>
            <div class="stat-label">⚡ Total Alertas</div></div>""", unsafe_allow_html=True)

        # Combinar e mostrar top 25 (zerados top 15 + críticos top 15, ordenado por urgência)
        df_alerta = pd.concat([
            df_zero.head(15).assign(nivel="ZERADO", dias_cobertura=0.0),
            df_crit.head(15).assign(nivel="CRÍTICO"),
        ]).sort_values(
            ["nivel", "dias_cobertura"],
            ascending=[True, True],  # ZERADO primeiro, depois menor cobertura
            key=lambda col: col.map({"ZERADO": 0, "CRÍTICO": 1}) if col.name == "nivel" else col
        ).head(25)

        if not df_alerta.empty:
            # Bar chart horizontal com cores de severidade
            colors = ["#ff4757" if n == "ZERADO" else "#ffa502" for n in df_alerta["nivel"]]
            nomes = df_alerta["produto"].apply(lambda p: p[:35] + "…" if len(p) > 35 else p)

            fig_alert = go.Figure()
            fig_alert.add_trace(go.Bar(
                y=nomes, x=df_alerta["qtd_vendida"], orientation="h",
                marker=dict(color=colors, cornerradius=3),
                text=df_alerta.apply(lambda r: f"Est: {int(r['qtd_estoque'])}", axis=1),
                textposition="outside", textfont=dict(size=9, color="#94a3b8"),
                customdata=df_alerta["dias_cobertura"].fillna(0).round(1),
                hovertemplate="<b>%{y}</b><br>Vendido: %{x:,.0f}<br>%{text}<br>Cobertura: %{customdata}d<extra></extra>",

            ))
            fig_alert.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="🚨 Produtos com Estoque Crítico vs Vendas", font=dict(size=13)),
                height=max(400, len(df_alerta) * 28),
                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9)),
                xaxis=dict(title="Qtd Vendida", gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_alert, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

            # Tabela detalhada
            with st.expander("📋 Tabela Detalhada — Críticos", expanded=False):
                df_show = df_alerta[["codigo", "produto", "grupo", "qtd_vendida", "qtd_estoque", "nivel"]].copy()
                df_show.columns = ["Código", "Produto", "Grupo", "Vendido", "Estoque", "Nível"]
                st.dataframe(df_show, hide_index=True, use_container_width=True)
        else:
            st.success("Nenhum produto em situação crítica! 🎉")

        # Lista completa de zerados
        if not df_zero.empty:
            with st.expander(f"💀 Lista Completa — Estoque Zerado ({len(df_zero)} produtos)", expanded=False):
                df_zero_show = df_zero[["codigo", "produto", "grupo", "qtd_vendida"]].copy()
                df_zero_show.columns = ["Código", "Produto", "Grupo", "Vendido"]
                df_zero_show = df_zero_show.reset_index(drop=True)
                st.dataframe(df_zero_show, hide_index=True, use_container_width=True, height=400)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — TAXA DE GIRO (BURN RATE)
    # ══════════════════════════════════════════════════════════════════════
    with vt3:
        st.caption(f"Estimativa de dias até zerar estoque no ritmo atual (baseado nos últimos **{_periodo_vendas} dia{'s' if _periodo_vendas != 1 else ''}** de vendas acumuladas)")

        df_burn = df_grupo[df_grupo["qtd_vendida"] > 0].copy()
        df_burn["dias_estoque"] = (df_burn["qtd_estoque"] / df_burn["qtd_vendida"] * _periodo_vendas).round(0).astype(int)
        df_burn = df_burn.sort_values("dias_estoque").head(12)

        if not df_burn.empty:
            colors_burn = [
                "#ff4757" if d < 15 else "#ffa502" if d < 30 else "#00d68f"
                for d in df_burn["dias_estoque"]
            ]

            fig_burn = go.Figure()
            fig_burn.add_trace(go.Bar(
                y=df_burn["grupo"], x=df_burn["dias_estoque"], orientation="h",
                marker=dict(color=colors_burn, cornerradius=4),
                text=df_burn["dias_estoque"].apply(lambda d: f"{d}d"),
                textposition="outside", textfont=dict(size=10, color="#94a3b8"),
                hovertemplate="<b>%{y}</b><br>Dias restantes: %{x}<br><extra></extra>",
            ))
            # Linhas de referência
            fig_burn.add_shape(
                type="line", x0=15, x1=15, y0=-0.5, y1=len(df_burn)-0.5,
                line=dict(dash="dash", color="#ff4757", width=1), yref="y",
            )
            fig_burn.add_annotation(x=15, y=-0.5, text="Urgente", showarrow=False,
                font=dict(size=9, color="#ff4757"), yshift=-12)
            fig_burn.add_shape(
                type="line", x0=30, x1=30, y0=-0.5, y1=len(df_burn)-0.5,
                line=dict(dash="dash", color="#ffa502", width=1), yref="y",
            )
            fig_burn.add_annotation(x=30, y=-0.5, text="Atenção", showarrow=False,
                font=dict(size=9, color="#ffa502"), yshift=-12)
            fig_burn.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="🔥 Dias de Estoque Restante por Grupo", font=dict(size=14)),
                height=max(350, len(df_burn) * 35),
                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
                xaxis=dict(title="Dias", gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_burn, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

            # Info box
            urgentes = df_burn[df_burn["dias_estoque"] < 15]["grupo"].tolist()
            if urgentes:
                st.error(f"⚡ **Reposição urgente** (<15 dias): {', '.join(urgentes)}")

            atencao = df_burn[(df_burn["dias_estoque"] >= 15) & (df_burn["dias_estoque"] < 30)]["grupo"].tolist()
            if atencao:
                st.warning(f"⚠️ **Atenção** (15-30 dias): {', '.join(atencao)}")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4 — TOP PRODUTOS
    # ══════════════════════════════════════════════════════════════════════
    with vt4:
        col_filter, _ = st.columns([1, 2])
        with col_filter:
            grupos_disp = ["TODOS"] + sorted(df_vendas["grupo"].unique().tolist())
            grupo_sel = st.selectbox("Filtrar por grupo:", grupos_disp, key="vendas_filtro_grupo")

        df_prod = df_vendas.copy()
        if grupo_sel != "TODOS":
            df_prod = df_prod[df_prod["grupo"] == grupo_sel]

        df_top_prod = df_prod.nlargest(15, "qtd_vendida")

        if not df_top_prod.empty:
            nomes = df_top_prod["produto"].apply(lambda p: p[:40] + "…" if len(p) > 40 else p)
            fig_top = go.Figure()
            fig_top.add_trace(go.Bar(
                y=nomes, x=df_top_prod["qtd_vendida"], orientation="h",
                marker=dict(
                    color=[_get_color(g) for g in df_top_prod["grupo"]],
                    cornerradius=4,
                ),
                text=df_top_prod["qtd_vendida"].apply(lambda v: f"{v:,.0f}".replace(",", ".")),
                textposition="outside", textfont=dict(size=9, color="#94a3b8"),
                hovertemplate="<b>%{y}</b><br>Vendido: %{x:,.0f}<br><extra></extra>",
            ))
            fig_top.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text=f"🏆 Top 15 Produtos — {grupo_sel}", font=dict(size=14)),
                height=max(380, len(df_top_prod) * 30),
                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9)),
                xaxis=dict(title="Qtd Vendida", gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_top, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

            # Scatter vendido vs estoque
            fig_scatter = go.Figure()
            for g in df_prod["grupo"].unique():
                dg = df_prod[df_prod["grupo"] == g]
                fig_scatter.add_trace(go.Scatter(
                    x=dg["qtd_vendida"], y=dg["qtd_estoque"],
                    mode="markers", name=g[:15],
                    marker=dict(
                        color=_get_color(g), size=8, opacity=0.7,
                        line=dict(width=1, color="#0a0f1a"),
                    ),
                    hovertemplate="<b>%{text}</b><br>Vendido: %{x}<br>Estoque: %{y}<extra></extra>",
                    text=df_prod.loc[dg.index, "produto"].apply(lambda p: p[:30]),
                ))
            # Linha de equilíbrio
            max_val = max(df_prod["qtd_vendida"].max(), df_prod["qtd_estoque"].max(), 100)
            fig_scatter.add_trace(go.Scatter(
                x=[0, max_val], y=[0, max_val],
                mode="lines", line=dict(dash="dash", color="#64748b", width=1),
                name="Equilíbrio", showlegend=True,
            ))
            fig_scatter.update_layout(
                **_PLOTLY_LAYOUT,
                title=dict(text="Vendido × Estoque (abaixo da linha = estoque menor que vendas)", font=dict(size=12, color="#94a3b8")),
                height=380,
                xaxis=dict(title="Qtd Vendida", gridcolor="#1e293b"),
                yaxis=dict(title="Qtd Estoque", gridcolor="#1e293b"),
                legend=dict(font=dict(size=8), orientation="h", y=-0.2),
            )
            st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})
        else:
            st.info("Nenhum produto encontrado para o filtro selecionado.")


# ══════════════════════════════════════════════════════════════════════════════
# INFOGRÁFICOS — aba principal
# ══════════════════════════════════════════════════════════════════════════════

def build_infograficos_tab():
    """Renderiza a aba de infográficos analíticos."""
    try:
        count = get_db().execute("SELECT COUNT(*) FROM vendas_historico").fetchone()[0]
    except Exception:
        count = 0

    if count == 0:
        st.info("📊 Nenhum dado de vendas disponível. Faça upload de uma planilha de vendas para ativar os infográficos.")
        return

    # ── Seletor de período ───────────────────────────────────────────────
    data_min, data_max = get_datas_vendas_range()

    col_di, col_df, col_atalhos = st.columns([2, 2, 3])

    with col_di:
        data_inicio = st.date_input(
            "Data início", value=max(data_min, data_max - timedelta(days=30)),
            min_value=data_min, max_value=data_max, key="inf_data_inicio",
        )
    with col_df:
        data_fim = st.date_input(
            "Data fim", value=data_max,
            min_value=data_min, max_value=data_max, key="inf_data_fim",
        )

    with col_atalhos:
        st.markdown("<div style='padding-top:6px;font-size:0.75rem;color:#64748b;margin-bottom:2px;'>Atalhos rápidos</div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)

        def _set_periodo(dias):
            st.session_state["inf_data_inicio"] = max(data_min, data_max - timedelta(days=dias))
            st.session_state["inf_data_fim"] = data_max

        for col_btn, dias, label in [(c1, 7, "7d"), (c2, 15, "15d"), (c3, 30, "30d"), (c4, 60, "60d")]:
            with col_btn:
                st.button(label, key=f"inf_atalho_{dias}", use_container_width=True,
                          on_click=_set_periodo, args=(dias,))

    if data_inicio > data_fim:
        st.warning("⚠️ Data início maior que data fim.")
        return

    data_inicio_str = data_inicio.isoformat()
    data_fim_str = data_fim.isoformat()

    # ── Seletor de infográfico (lido antes do render, exibido após o gráfico) ─
    _INF_OPTS = [
        "🔥 Mapa de Calor de Vendas",
        "📊 Mais vs Menos Movimentados",
        "💤 Produtos Parados",
        "⚖️ Giro vs Ruptura por Grupo",
    ]
    infografico = st.session_state.get("inf_selector", _INF_OPTS[0])

    def _render_seletor_inf():
        st.markdown("<hr style='margin:8px 0 4px;border-color:#1e293b'>", unsafe_allow_html=True)
        st.selectbox("Infográfico", _INF_OPTS, key="inf_selector", label_visibility="collapsed")

    # ════════════════════════════════════════════════════════════════════════
    # INFOGRÁFICO 1 — MAPA DE CALOR
    # ════════════════════════════════════════════════════════════════════════
    if infografico == "🔥 Mapa de Calor de Vendas":
        st.markdown("### 🔥 Mapa de Calor de Vendas por Dia da Semana")
        df_heat = get_vendas_heatmap(data_inicio_str, data_fim_str)

        if df_heat.empty:
            st.info("Nenhuma venda encontrada no período selecionado.")
            _render_seletor_inf()
            return

        dias_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

        pivot = df_heat.pivot_table(
            index="produto", columns="dia_semana",
            values="qtd_vendida", aggfunc="sum", fill_value=0,
        )
        for d in range(7):
            if d not in pivot.columns:
                pivot[d] = 0
        pivot = pivot[[0, 1, 2, 3, 4, 5, 6]]
        pivot.columns = dias_labels
        pivot["_total"] = pivot.sum(axis=1)
        pivot = pivot.sort_values("_total", ascending=False).head(20).drop(columns=["_total"])
        pivot.index = [n[:42] + "…" if len(n) > 42 else n for n in pivot.index]

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=dias_labels,
            y=pivot.index.tolist(),
            colorscale=[
                [0.0, "#0d1b2a"],
                [0.25, "#00d68f"],
                [0.65, "#ffa502"],
                [1.0, "#ef4444"],
            ],
            hoverongaps=False,
            hovertemplate="<b>%{y}</b><br>%{x}: <b>%{z} un.</b><extra></extra>",
            colorbar=dict(
                title=dict(text="Qtd", font=dict(color="#94a3b8")),
                tickfont=dict(color="#94a3b8"),
            ),
        ))
        fig.update_layout(**_PLOTLY_LAYOUT)
        fig.update_layout(
            height=max(420, len(pivot) * 30 + 90),
            xaxis=dict(side="top", tickfont=dict(color="#e0e6ed")),
            yaxis=dict(autorange="reversed", tickfont=dict(size=10, color="#e0e6ed")),
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})
        st.caption(
            f"Top 20 produtos por volume · Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        )

    # ════════════════════════════════════════════════════════════════════════
    # INFOGRÁFICO 2 — MAIS vs MENOS MOVIMENTADOS
    # ════════════════════════════════════════════════════════════════════════
    elif infografico == "📊 Mais vs Menos Movimentados":
        st.markdown("### 📊 Produtos Mais vs Menos Movimentados")

        grupos_disp = ["Todos"] + get_grupos_vendas()
        grupo_sel = st.selectbox("Filtrar por grupo", grupos_disp, key="inf_grupo_sel")

        df_mv = get_mais_menos_movimentados(
            data_inicio_str, data_fim_str,
            grupo_sel if grupo_sel != "Todos" else "Todos",
        )

        if df_mv.empty:
            st.info("Nenhuma venda encontrada no período selecionado.")
            _render_seletor_inf()
            return

        def _short(s: str, n: int = 35) -> str:
            return s[:n] + "…" if len(s) > n else s

        top10_mais = df_mv.head(10).copy()
        _produtos_mais = set(top10_mais["produto"])
        top10_menos = (
            df_mv[df_mv["total_vendido"] > 0][~df_mv["produto"].isin(_produtos_mais)]
            .tail(10)
            .sort_values("total_vendido")
            .copy()
        )

        fig = go.Figure()

        fig.add_trace(go.Bar(
            y=[_short(p) for p in top10_mais["produto"]],
            x=top10_mais["total_vendido"],
            orientation="h",
            name="Mais vendidos",
            marker_color="#00d68f",
            hovertemplate="<b>%{y}</b><br>Vendido: <b>%{x} un.</b><extra></extra>",
            text=top10_mais["total_vendido"].astype(str),
            textposition="outside",
            textfont=dict(color="#00d68f", size=10),
        ))

        fig.add_trace(go.Bar(
            y=[_short(p) for p in top10_menos["produto"]],
            x=-top10_menos["total_vendido"],
            orientation="h",
            name="Menos vendidos",
            marker_color="#ffa502",
            customdata=top10_menos["total_vendido"].values,
            hovertemplate="<b>%{y}</b><br>Vendido: <b>%{customdata} un.</b><extra></extra>",
            text=top10_menos["total_vendido"].astype(str),
            textposition="outside",
            textfont=dict(color="#ffa502", size=10),
        ))

        _max_mais = int(top10_mais["total_vendido"].max()) if not top10_mais.empty else 1
        _max_menos = int(top10_menos["total_vendido"].max()) if not top10_menos.empty else 1
        max_val = max(_max_mais, _max_menos) * 1.35

        fig.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="overlay",
            height=max(520, max(len(top10_mais), len(top10_menos)) * 32 + 130),
            xaxis=dict(
                range=[-max_val, max_val],
                gridcolor="#1e293b",
                title="← Menos vendidos   |   Mais vendidos →",
                tickvals=[int(-max_val * f) for f in [1, 0.75, 0.5, 0.25, 0, -0.25, -0.5, -0.75, -1] if abs(f) <= 1],
                ticktext=[str(abs(int(-max_val * f))) for f in [1, 0.75, 0.5, 0.25, 0, -0.25, -0.5, -0.75, -1] if abs(f) <= 1],
            ),
            yaxis=dict(tickfont=dict(size=9)),
            legend=dict(**_DEFAULT_LEGEND, orientation="h", y=1.05),
            shapes=[dict(
                type="line", x0=0, x1=0,
                y0=-0.5, y1=max(len(top10_mais), len(top10_menos)) - 0.5,
                line=dict(color="#64748b", width=1.5),
            )],
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})
        st.caption(
            f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} · Excluindo produtos sem vendas"
        )

    # ════════════════════════════════════════════════════════════════════════
    # INFOGRÁFICO 3 — PRODUTOS PARADOS
    # ════════════════════════════════════════════════════════════════════════
    elif infografico == "💤 Produtos Parados":
        st.markdown("### 💤 Produtos Parados")

        dias_parado = st.slider(
            "Parado há mais de X dias",
            min_value=7, max_value=180, value=30, step=7,
            format="%d dias", key="inf_dias_parado",
        )

        df_parado = get_produtos_parados(dias_parado)

        if df_parado.empty:
            st.success(f"✅ Nenhum produto parado há mais de {dias_parado} dias com estoque positivo!")
            _render_seletor_inf()
            return

        total_parados = len(df_parado)
        valor_total = df_parado["valor_imobilizado"].sum()

        st.markdown(
            f'<div class="stat-row">'
            f'<div class="stat-card"><div class="stat-value red">{total_parados}</div>'
            f'<div class="stat-label">Produtos parados</div></div>'
            f'<div class="stat-card"><div class="stat-value amber">'
            f'R$ {valor_total:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") +
            f'</div><div class="stat-label">Valor imobilizado</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

        df_display = df_parado[[
            "produto", "grupo", "ultima_venda_fmt", "dias_parado", "qtd_estoque", "valor_imobilizado",
        ]].copy()
        df_display.columns = [
            "Produto", "Grupo", "Último movimento", "Dias parado", "Qtd em estoque", "Valor imobilizado (R$)",
        ]
        df_display["Valor imobilizado (R$)"] = df_display["Valor imobilizado (R$)"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        def _style_parado(row):
            bg = "background-color: rgba(239,68,68,0.15);" if row["Dias parado"] > 90 else ""
            return [bg] * len(row)

        styled = df_display.style.apply(_style_parado, axis=1)
        st.dataframe(
            styled, use_container_width=True, hide_index=True,
            height=min(600, len(df_display) * 38 + 55),
        )
        st.caption(
            f"{total_parados} produto(s) sem movimentação há mais de {dias_parado} dias · "
            "Linhas em vermelho = parados há mais de 90 dias"
        )

    # ════════════════════════════════════════════════════════════════════════
    # INFOGRÁFICO 4 — GIRO vs RUPTURA POR GRUPO
    # ════════════════════════════════════════════════════════════════════════
    elif infografico == "⚖️ Giro vs Ruptura por Grupo":
        st.markdown("### ⚖️ Giro vs Ruptura por Grupo de Produto")

        df_gr = get_giro_ruptura_grupos(data_inicio_str, data_fim_str)

        if df_gr.empty:
            st.info("Nenhum dado disponível para o período selecionado.")
            _render_seletor_inf()
            return

        med_giro = df_gr["taxa_giro"].median()
        med_ruptura = df_gr["pct_ruptura"].median()

        max_valor_est = df_gr["valor_estoque"].max() or 1
        df_gr["bubble_size"] = (df_gr["valor_estoque"] / max_valor_est * 55 + 10).round(1)

        fig = go.Figure()
        for _, row in df_gr.iterrows():
            cor = _get_color(row["grupo"])
            fig.add_trace(go.Scatter(
                x=[row["taxa_giro"]],
                y=[row["pct_ruptura"]],
                mode="markers+text",
                marker=dict(
                    size=row["bubble_size"],
                    color=cor,
                    opacity=0.78,
                    line=dict(width=1.5, color="rgba(255,255,255,0.25)"),
                ),
                text=[row["grupo"][:22]],
                textposition="top center",
                textfont=dict(size=9, color="#e0e6ed"),
                name=row["grupo"],
                customdata=[[
                    row["grupo"], row["taxa_giro"],
                    row["pct_ruptura"], row["valor_estoque"],
                ]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Taxa de Giro: <b>%{customdata[1]:.3f}</b><br>"
                    "% Ruptura: <b>%{customdata[2]:.1f}%</b><br>"
                    "Valor em Estoque: <b>R$ %{customdata[3]:,.0f}</b>"
                    "<extra></extra>"
                ),
            ))

        max_giro = max(df_gr["taxa_giro"].max() * 1.2, 0.1)
        max_rupt = max(df_gr["pct_ruptura"].max() * 1.2, 5.0)

        fig.add_shape(
            type="line", x0=med_giro, x1=med_giro, y0=0, y1=max_rupt,
            line=dict(color="#475569", width=1.5, dash="dash"),
        )
        fig.add_shape(
            type="line", x0=0, x1=max_giro, y0=med_ruptura, y1=med_ruptura,
            line=dict(color="#475569", width=1.5, dash="dash"),
        )

        for txt, x_f, y_f, color in [
            ("⭐ Ideal",    (med_giro + max_giro) / 2, med_ruptura / 2,          "#00d68f"),
            ("🚨 Problema", med_giro / 2,              (med_ruptura + max_rupt) / 2, "#ef4444"),
            ("📦 Excesso",  (med_giro + max_giro) / 2, (med_ruptura + max_rupt) / 2, "#ffa502"),
            ("💤 Parado",   med_giro / 2,              med_ruptura / 2,          "#94a3b8"),
        ]:
            fig.add_annotation(
                x=x_f, y=y_f, text=txt,
                showarrow=False,
                font=dict(size=14, color=color),
                opacity=0.45,
            )

        fig.update_layout(**_PLOTLY_LAYOUT)
        fig.update_layout(
            height=540,
            showlegend=False,
            xaxis=dict(
                title="Taxa de Giro (vendas / estoque)",
                gridcolor="#1e293b",
                range=[0, max_giro],
                zeroline=False,
            ),
            yaxis=dict(
                title="% Ruptura (dias sem estoque)",
                gridcolor="#1e293b",
                range=[0, max_rupt],
                zeroline=False,
            ),
            margin=dict(l=20, r=20, t=40, b=60),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})
        st.caption(
            f"Mediana giro: {med_giro:.3f} · Mediana ruptura: {med_ruptura:.1f}% · "
            f"Tamanho proporcional ao valor em estoque · "
            f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        )

    # ── Seletor de infográfico (posicionado após o gráfico) ───────────────
    _render_seletor_inf()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

# ── Header banner + clima ──────────────────────────────────────────────────
_wd_dash = get_weather_forecast_quirinopolis()
_now_dash = datetime.now(tz=_BRT)
_dia_abr_dash = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"][_now_dash.weekday()]
_hora_dash = _now_dash.strftime("%H:%M")

if _wd_dash:
    _cur_d = _wd_dash["current"]
    _wtemp_d = round(_cur_d["temperature_2m"])
    _wcode_d = int(_cur_d["weathercode"])
    _humid_d = round(_cur_d.get("relative_humidity_2m", 0))
    _vento_d = round(_cur_d.get("wind_speed_10m", 0))
    _c = _wcode_d
    if _c == 0:                      _wemoji_d, _wdesc_d = "☀️", "Céu limpo"
    elif _c in (1,2):                _wemoji_d, _wdesc_d = "🌤️", "Poucas nuvens"
    elif _c == 3:                    _wemoji_d, _wdesc_d = "☁️", "Nublado"
    elif _c in (45,48):              _wemoji_d, _wdesc_d = "🌫️", "Névoa"
    elif _c in (51,53,55):           _wemoji_d, _wdesc_d = "🌦️", "Chuvisco"
    elif _c in (61,63,65,80,81,82):  _wemoji_d, _wdesc_d = "🌧️", "Chuva"
    elif _c in (95,96,99):           _wemoji_d, _wdesc_d = "⛈️", "Tempestade"
    elif _c in (71,73,75,77):        _wemoji_d, _wdesc_d = "❄️", "Neve"
    else:                            _wemoji_d, _wdesc_d = "🌡️", ""
    _whtml = f"""<div class="wco">
  <div style="font-size:0.58rem;color:rgba(255,255,255,0.55);margin-bottom:6px;letter-spacing:0.3px;">{_dia_abr_dash} · {_hora_dash}</div>
  <div style="font-size:2.4rem;line-height:1;filter:drop-shadow(0 4px 10px rgba(0,0,0,0.4));">{_wemoji_d}</div>
  <div style="font-size:2.1rem;font-weight:700;line-height:1.1;letter-spacing:-1px;margin-top:5px;text-shadow:0 2px 8px rgba(0,0,0,0.5);">{_wtemp_d}°</div>
  <div style="font-size:0.7rem;color:rgba(255,255,255,0.9);margin-top:5px;font-weight:500;text-shadow:0 1px 4px rgba(0,0,0,0.5);">{_wdesc_d}</div>
  <div style="font-size:0.58rem;color:rgba(255,255,255,0.6);margin-top:2px;text-shadow:0 1px 4px rgba(0,0,0,0.4);">Quirinópolis, GO</div>
  <div style="display:flex;justify-content:center;gap:7px;font-size:0.6rem;color:rgba(255,255,255,0.8);
              margin-top:8px;background:rgba(0,0,0,0.18);border-radius:10px;padding:5px 8px;">
    <span>💧 {_humid_d}%</span><span style="opacity:0.3;">|</span><span>💨 {_vento_d}km/h</span>
  </div>
</div>"""
else:
    _whtml = ""

st.markdown(f'''
<style>
.camda-header-wrap {{ position: relative; width: 100%; margin-bottom: 0.8rem; }}
.camda-header {{
    width: 100%; height: 220px;
    background-image: url(https://raw.githubusercontent.com/LeoLira1/camda-estoque/main/banner.jpg?v=20260228);
    background-size: cover;
    background-position: center;
    border-radius: 14px;
    overflow: hidden;
}}
.wco {{
    position: absolute; top: 12px; right: 16px;
    color: #fff; font-family: Outfit,sans-serif;
    border-radius: 18px; padding: 12px 15px 11px;
    background: transparent;
    border: none;
    box-shadow: none;
    text-align: center; min-width: 128px;
}}
@media (max-width: 640px) {{
    .camda-header {{ height: 140px; }}
    .wco {{ top: 6px; right: 6px; padding: 8px 10px 8px; border-radius: 14px; min-width: 100px; }}
    .wco > div:nth-child(2) {{ font-size: 1.6rem !important; }}
    .wco > div:nth-child(3) {{ font-size: 1.4rem !important; }}
}}
</style>
<div class="camda-header-wrap">
  <div class="camda-header"></div>
  {_whtml}
</div>

''', unsafe_allow_html=True)

# ── Alertas automáticos (abaixo do clima) ────────────────────────────────────
if "alertas_cache" not in st.session_state or st.session_state.get("alertas_cache_date") != datetime.now(tz=_BRT).date().isoformat():
    st.session_state["alertas_cache"] = checar_e_registrar_alertas()
    st.session_state["alertas_cache_date"] = datetime.now(tz=_BRT).date().isoformat()

_alertas = st.session_state["alertas_cache"]
_al_val  = _alertas.get("validade_30d", [])
_al_pend = _alertas.get("pendencia_5d", [])

if _al_val or _al_pend:
    _pills = []
    if _al_pend:
        n = len(_al_pend)
        _pills.append(
            f'<div class="al-pill al-pend">🔴 <b>{n} pendência{"s" if n > 1 else ""}</b>'
            f' sem entrega há mais de 5 dias</div>'
        )
    if _al_val:
        _urgentes = [a for a in _al_val if a["dias_restantes"] <= 7]
        _normais  = [a for a in _al_val if a["dias_restantes"] > 7]
        if _urgentes:
            _nomes = ", ".join(dict.fromkeys(a["produto"] for a in _urgentes[:3]))
            if len(_urgentes) > 3:
                _nomes += f" +{len(_urgentes) - 3}"
            _pills.append(
                f'<div class="al-pill al-urgente">🟠 <b>{len(_urgentes)} lote{"s" if len(_urgentes) > 1 else ""}'
                f' ≤7 dias:</b> {_nomes}</div>'
            )
        if _normais:
            _pills.append(
                f'<div class="al-pill al-aviso">🟡 <b>{len(_normais)} lote{"s" if len(_normais) > 1 else ""}'
                f'</b> vence em até 30 dias</div>'
            )
    st.markdown(
        """
        <style>
        .al-wrap{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 14px 0;}
        .al-pill{padding:6px 14px;border-radius:20px;font-size:0.82rem;font-family:Outfit,sans-serif;line-height:1.4;}
        .al-pend{background:rgba(255,71,87,0.12);color:#ff4757;border:1px solid rgba(255,71,87,0.35);}
        .al-urgente{background:rgba(255,140,0,0.12);color:#ff8c00;border:1px solid rgba(255,140,0,0.4);}
        .al-aviso{background:rgba(255,193,7,0.12);color:#ffc107;border:1px solid rgba(255,193,7,0.35);}
        </style>
        """ + f'<div class="al-wrap">{"".join(_pills)}</div>',
        unsafe_allow_html=True,
    )

stock_count = get_stock_count()
has_mestre = stock_count > 0

# ── Dashboard ────────────────────────────────────────────────────────────────
if has_mestre:
    df_mestre = get_current_stock()
    df_pa = get_principios_ativos()

    # Combina dados de P.A. do banco com o catálogo Excel (mesma lógica da aba 🧬)
    _mapa_excel_search = carregar_mapa_produtos_camda()
    _mapa_db_search: dict = {}
    for _, _r in df_pa.iterrows():
        _mapa_db_search[str(_r["produto"]).strip().upper()] = str(_r["principio_ativo"]).strip()
    _mapa_pa_search = {**_mapa_excel_search, **_mapa_db_search}
    has_pa = bool(_mapa_pa_search)

    search_placeholder = "Nome, Código ou Princípio Ativo..." if has_pa else "Nome ou Código..."
    search_term = st.text_input("🔍 Buscar no Mestre", placeholder=search_placeholder, label_visibility="collapsed", key="search_mestre")
    st.markdown("""<script>
    (function() {
        function disableAutocomplete() {
            var inputs = document.querySelectorAll('input[type="text"]');
            inputs.forEach(function(el) {
                el.setAttribute('autocomplete', 'off');
            });
        }
        setTimeout(disableAutocomplete, 100);
        setTimeout(disableAutocomplete, 500);
    })();
    </script>""", unsafe_allow_html=True)

    df_view = df_mestre
    pa_match_info = ""
    if search_term:
        # Busca padrão por nome/código (contém), excluindo registros AUTO_
        # AUTO_ são artefatos de import mal-parseado e não devem poluir a busca
        mask_nome_cod = (
            df_view["produto"].str.contains(search_term, case=False, na=False, regex=False)
            | df_view["codigo"].str.contains(search_term, case=False, na=False, regex=False)
        ) & ~df_view["codigo"].str.startswith("AUTO_")

        # Busca por princípio ativo usando o mesmo match multi-etapa da aba 🧬
        mask_pa = pd.Series([False] * len(df_view), index=df_view.index)
        if has_pa:
            _idx_search = _build_pa_lookup(_mapa_pa_search)
            _term_up = search_term.upper()
            mask_pa = df_view["produto"].apply(
                lambda x: _term_up in _lookup_pa_from_index(str(x), *_idx_search).upper()
            )

        mask = mask_nome_cod | mask_pa
        n_pa = int((mask_pa & ~mask_nome_cod).sum())
        if n_pa > 0 and not mask_nome_cod.any():
            # Busca encontrou apenas por P.A. — mostrar qual P.A. foi encontrado
            pa_found = sorted({
                _lookup_pa_from_index(str(x), *_idx_search)
                for x in df_view.loc[mask_pa, "produto"]
                if _term_up in _lookup_pa_from_index(str(x), *_idx_search).upper()
            })
            pa_match_info = f"🧬 Princípio ativo: **{', '.join(pa_found[:3])}** → {n_pa} produto(s)"
        elif n_pa > 0:
            pa_match_info = f"🧬 Inclui {n_pa} produto(s) por princípio ativo"

        df_view = df_view[mask]

        if pa_match_info:
            st.caption(pa_match_info)

    n_ok = (df_view["status"] == "ok").sum()
    n_falta = (df_view["status"] == "falta").sum()
    n_sobra = (df_view["status"] == "sobra").sum()

    df_reposicao = get_reposicao_pendente()
    n_repor = len(df_reposicao)
    n_avarias = get_avarias_count_abertas()

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="stat-value">{len(df_view)}</div><div class="stat-label">Total</div></div>
        <div class="stat-card"><div class="stat-value">{n_ok}</div><div class="stat-label">OK</div></div>
        <div class="stat-card"><div class="stat-value red">{n_falta}</div><div class="stat-label">Faltas</div></div>
        <div class="stat-card"><div class="stat-value amber">{n_sobra}</div><div class="stat-label">Sobras</div></div>
        <div class="stat-card"><div class="stat-value blue">{n_repor}</div><div class="stat-label">Repor Loja</div></div>
        <div class="stat-card"><div class="stat-value red">{n_avarias}</div><div class="stat-label">Avarias</div></div>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3, t4, t6, t7, t8, t9, t10, t11, t12, t13, t_mapa = st.tabs(["🗺️ Mapa Estoque", "⚠️ Divergências", "🏪 Repor na Loja", "📈 Vendas", "📦 Pendências", "🔴 Avarias", "📅 Agenda", "📋 Contagem", "📅 Validade", "📊 Histórico", "🧬 P. Ativos", "📊 Infográficos", "🏭 Mapa Visual"])

    with t1:
        # Monta dict codigo -> qtd_avariada (avarias abertas)
        df_av_mapa = listar_avarias(apenas_abertas=True)
        av_map = df_av_mapa.groupby("codigo")["qtd_avariada"].sum().to_dict() if not df_av_mapa.empty else {}
        st.markdown(build_css_treemap(df_view, "TODOS", avarias_map=av_map), unsafe_allow_html=True)

    with t2:
        df_div = df_view[df_view["status"].isin(("falta", "sobra"))]
        if df_div.empty:
            st.info("Nenhuma divergência.")
        else:
            st.caption(f"{len(df_div)} divergência(s) · Itens saem apenas quando desmarcados manualmente.")
            for _, item in df_div.iterrows():
                status_cor = "#ef4444" if item["status"] == "falta" else "#f59e0b"
                status_label = "⬇️ FALTA" if item["status"] == "falta" else "⬆️ SOBRA"
                diferenca = int(item["diferenca"]) if pd.notnull(item["diferenca"]) else 0
                qtd_s = int(item["qtd_sistema"]) if pd.notnull(item["qtd_sistema"]) else 0
                qtd_f = int(item["qtd_fisica"]) if pd.notnull(item["qtd_fisica"]) else 0
                nota = str(item["nota"]) if pd.notnull(item["nota"]) and str(item["nota"]).strip() else ""

                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f'<div style="background:#111827;border:1px solid {status_cor}44;border-radius:8px;padding:10px 14px;margin-bottom:4px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span style="color:#e0e6ed;font-weight:700;font-size:0.85rem;">{item["produto"]}</span>'
                        f'<span style="color:{status_cor};font-size:0.7rem;font-weight:700;">{status_label} {abs(diferenca)}</span></div>'
                        f'<div style="margin-top:4px;display:flex;gap:12px;flex-wrap:wrap;">'
                        f'<span style="color:#64748b;font-size:0.65rem;">Cod: <b style="color:#94a3b8;">{item["codigo"]}</b></span>'
                        f'<span style="color:#64748b;font-size:0.65rem;">{item["categoria"]}</span>'
                        f'<span style="color:#64748b;font-size:0.65rem;">Sistema: <b style="color:#94a3b8;">{qtd_s}</b> · Físico: <b style="color:#94a3b8;">{qtd_f}</b></span>'
                        + (f'<span style="color:#64748b;font-size:0.65rem;">Obs: <i style="color:#94a3b8;">{nota}</i></span>' if nota else '')
                        + f'</div></div>',
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("✅", key=f"div_{item['codigo']}", help="Resolver divergência manualmente"):
                        resolver_divergencia(str(item["codigo"]))
                        st.rerun()

    with t3:
        if df_reposicao.empty:  # Repor na Loja
            st.success("Nenhum produto pendente de reposição! 🎉")
        else:
            st.caption(f"{n_repor} produto(s) para repor. Itens saem apenas quando desmarcados.")
            for _, item in df_reposicao.iterrows():
                try:
                    dias = (datetime.now(tz=_BRT).replace(tzinfo=None) - datetime.strptime(item["criado_em"], "%Y-%m-%d %H:%M:%S")).days
                except (ValueError, TypeError):
                    dias = 0
                tempo = "hoje" if dias == 0 else ("ontem" if dias == 1 else f"{dias}d atrás")
                qtd_v = int(item["qtd_vendida"]) if pd.notnull(item["qtd_vendida"]) else 0
                qtd_e = int(item["qtd_estoque"]) if pd.notnull(item.get("qtd_estoque")) else 0

                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f'<div class="repor-item" style="background:#111827;border:1px solid #1e293b;border-radius:8px;padding:10px 14px;margin-bottom:4px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span style="color:#e0e6ed;font-weight:700;font-size:0.85rem;">{item["produto"]}</span>'
                        f'<span style="color:#3b82f6;font-size:0.6rem;font-family:monospace;">{tempo}</span></div>'
                        f'<div style="margin-top:4px;display:flex;gap:12px;">'
                        f'<span style="color:#64748b;font-size:0.65rem;">Cod: <b style="color:#94a3b8;">{item["codigo"]}</b></span>'
                        f'<span style="color:#64748b;font-size:0.65rem;">{item["categoria"]}</span>'
                        f'<span style="color:#ffa502;font-size:0.65rem;font-weight:700;">Estoque: {qtd_e} → Repor: {qtd_v}</span>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("✅", key=f"repor_{item['id']}", help="Marcar como reposto"):
                        marcar_reposto(int(item["id"]))
                        st.rerun()

        # ── Registrar divergência manual ─────────────────────────────────────
        st.markdown("---")
        with st.expander("⚠️ Registrar divergência de contagem", expanded=False):
            df_est_corr = get_current_stock()
            if df_est_corr.empty:
                st.info("Carregue o estoque mestre para usar esta função.")
            else:
                senha_div = st.text_input(
                    "🔑 Senha para edição",
                    type="password",
                    key="repor_manual_senha",
                    placeholder="Digite a senha…",
                )
                if senha_div and senha_div != "camda@edit":
                    st.error("Senha incorreta.")

                if senha_div == "camda@edit":

                    st.caption(
                        "Selecione o produto e informe **quantos estão sobrando** (+) "
                        "ou **faltando** (−) em relação ao que o sistema mostra. "
                        "O valor do sistema **não é alterado** — apenas a divergência é registrada."
                    )
                    opcoes_corr = [
                        f"{r['codigo']} — {r['produto']}"
                        for _, r in df_est_corr.iterrows()
                    ]
                    sel_corr = st.selectbox(
                        "Produto",
                        options=opcoes_corr,
                        index=0,
                        key="repor_manual_prod_sel",
                        placeholder="Digite código ou nome do produto…",
                    )
                    if sel_corr:
                        cod_corr = sel_corr.split(" — ")[0].strip()
                        row_corr = df_est_corr[df_est_corr["codigo"] == cod_corr]
                        if not row_corr.empty:
                            qtd_atual = int(row_corr["qtd_sistema"].iloc[0])
                            cat_corr  = str(row_corr["categoria"].iloc[0])
                            status_atual = str(row_corr["status"].iloc[0])
                            div_atual = int(row_corr["diferenca"].iloc[0]) if pd.notnull(row_corr["diferenca"].iloc[0]) else 0

                            _cor_status = {"sobra": "#22c55e", "falta": "#f87171"}.get(status_atual, "#64748b")
                            _label_status = {"sobra": "sobra", "falta": "falta"}.get(status_atual, "ok")
                            st.markdown(
                                f'<div style="background:#111827;border:1px solid #1e293b;'
                                f'border-radius:8px;padding:10px 14px;margin:6px 0;">'
                                f'<span style="color:#94a3b8;font-size:0.75rem;">Sistema: </span>'
                                f'<span style="color:#e0e6ed;font-weight:700;">{qtd_atual} un.</span>'
                                f'&nbsp;&nbsp;'
                                f'<span style="color:{_cor_status};font-size:0.7rem;font-weight:600;">{_label_status}'
                                f'{f" ({div_atual:+d})" if div_atual != 0 else ""}</span>'
                                f'&nbsp;&nbsp;<span style="color:#64748b;font-size:0.7rem;">{cat_corr}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                            delta_corr = st.number_input(
                                "Diferença (+sobrando / −faltando)",
                                min_value=-9999,
                                max_value=9999,
                                value=0,
                                step=1,
                                key="repor_manual_delta",
                                help="Ex: sistema diz 11, físico tem 12 → digite +1. "
                                     "Sistema diz 11, físico tem 9 → digite −2.",
                            )

                            if delta_corr != 0:
                                cor = "#22c55e" if delta_corr > 0 else "#f87171"
                                tipo = "sobra" if delta_corr > 0 else "falta"
                                sinal = "+" if delta_corr > 0 else ""
                                st.markdown(
                                    f'<div style="color:{cor};font-size:0.8rem;margin-top:4px;">'
                                    f'Será registrada <b>{tipo}</b> de <b>{sinal}{delta_corr} un.</b> '
                                    f'(físico: {qtd_atual + delta_corr} un. · sistema: {qtd_atual} un.)</div>',
                                    unsafe_allow_html=True,
                                )

                            if st.button(
                                "⚠️ Registrar divergência",
                                type="primary",
                                use_container_width=True,
                                key="repor_manual_btn",
                                disabled=(delta_corr == 0),
                            ):
                                ok, msg = registrar_divergencia_manual(cod_corr, int(delta_corr))
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

    with t4:
        df_vendas = get_vendas_historico()
        build_vendas_tab(df_vendas)

    with t6:
        # ── CSS da aba ──
        st.markdown("""
        <style>
        .pend-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:16px;margin-bottom:16px;}
        .pend-card.alerta-amarelo{border-color:rgba(255,193,7,0.5);background:rgba(255,193,7,0.06);}
        .pend-card.alerta-vermelho{border-color:rgba(255,71,87,0.6);background:rgba(255,71,87,0.08);animation:pulse-red 2s infinite;}
        @keyframes pulse-red{0%{box-shadow:0 0 0 0 rgba(255,71,87,0.3)}70%{box-shadow:0 0 0 8px rgba(255,71,87,0)}100%{box-shadow:0 0 0 0 rgba(255,71,87,0)}}
        .badge-dias{display:inline-block;padding:4px 14px;border-radius:20px;font-size:0.8rem;font-weight:700;letter-spacing:.5px;margin-bottom:10px;}
        .badge-verde{background:rgba(0,214,143,0.15);color:#00d68f;border:1px solid #00d68f44;}
        .badge-amarelo{background:rgba(255,193,7,0.15);color:#ffc107;border:1px solid #ffc10744;}
        .badge-vermelho{background:rgba(255,71,87,0.15);color:#ff4757;border:1px solid #ff475744;}
        .pend-data{font-size:0.7rem;color:rgba(255,255,255,0.4);font-family:'JetBrains Mono',monospace;margin-bottom:8px;}
        .pend-obs{background:rgba(255,255,255,0.06);border-left:3px solid rgba(100,180,255,0.5);border-radius:0 8px 8px 0;padding:8px 12px;margin:10px 0 4px 0;font-size:0.85rem;color:rgba(255,255,255,0.75);white-space:pre-wrap;}
        </style>
        """, unsafe_allow_html=True)

        # ── Registrar nova pendência ──
        with st.expander("➕  Registrar nova pendência", expanded=False):
            st.markdown("**📸 Fotografe ou selecione a via cega do pedido:**")
            foto = st.file_uploader(
                "Foto da via cega",
                type=["jpg", "jpeg", "png", "webp"],
                label_visibility="collapsed",
                key="pend_foto_upload",
            )
            obs_nova = st.text_area(
                "📝 Observação (opcional)",
                placeholder="Ex: Investigar endereço, cliente solicitou reagendar, aguardar contato...",
                key="pend_obs_input",
                height=80,
            )
            if foto is not None:
                img_bytes = foto.read()
                st.image(img_bytes, caption="Prévia — confirme antes de salvar", use_container_width=True)
                col_ok, col_cancel = st.columns(2)
                with col_ok:
                    if st.button("✅ Salvar pendência", use_container_width=True, type="primary", key="pend_salvar"):
                        inserir_pendencia(img_bytes, obs_nova)
                        st.success("Pendência registrada! ✔")
                        st.rerun()
                with col_cancel:
                    if st.button("✖ Cancelar", use_container_width=True, key="pend_cancelar"):
                        st.rerun()

        # ── Listar pendências ──
        pendencias = listar_pendencias()

        if not pendencias:
            st.markdown("""
            <div style="text-align:center;padding:40px 20px;color:rgba(255,255,255,0.3);">
                <div style="font-size:2.5rem;">✅</div>
                <div>Nenhuma pendência no momento</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            total_p = len(pendencias)
            vencidas_p = sum(1 for _, _, d, *_ in pendencias if _dias_desde(d) >= 3)
            c1, c2 = st.columns(2)
            c1.metric("Total pendente", total_p)
            c2.metric("⚠️ Vencidas (3d+)", vencidas_p)

            for pid, foto_b64, data_reg, obs in pendencias:
                dias = _dias_desde(data_reg)
                if dias <= 1:
                    card_class, badge_class = "pend-card", "badge-verde"
                    badge_txt = "Hoje" if dias == 0 else "1 dia"
                elif dias == 2:
                    card_class, badge_class = "pend-card alerta-amarelo", "badge-amarelo"
                    badge_txt = "⚠️ 2 dias — entregar hoje!"
                else:
                    card_class, badge_class = "pend-card alerta-vermelho", "badge-vermelho"
                    badge_txt = f"🚨 {dias} dias — VENCIDO!"

                st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
                obs_html = f'<div class="pend-obs">📝 {obs}</div>' if obs else ""
                st.markdown(
                    f'<span class="badge-dias {badge_class}">{badge_txt}</span>'
                    f'<div class="pend-data">Registrado em: {data_reg}</div>'
                    f'{obs_html}',
                    unsafe_allow_html=True
                )
                try:
                    st.image(base64.b64decode(foto_b64), use_container_width=True)
                except Exception:
                    st.warning("Erro ao carregar imagem.")
                if st.button(f"✅ Entregue — remover", key=f"pend_del_{pid}", use_container_width=True):
                    deletar_pendencia(pid)
                    st.success("Pendência removida.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    with t7:
        st.markdown("""
        <style>
        .av-card{background:rgba(165,94,234,0.06);border:1px solid rgba(165,94,234,0.25);border-radius:14px;padding:14px 16px;margin-bottom:10px;}
        .av-card.resolvido{background:rgba(0,214,143,0.04);border-color:rgba(0,214,143,0.2);opacity:0.6;}
        .av-badge{display:inline-block;padding:3px 12px;border-radius:20px;font-size:0.7rem;font-weight:700;letter-spacing:.5px;margin-bottom:8px;}
        .av-aberto{background:rgba(255,71,87,0.15);color:#ff4757;border:1px solid #ff475744;}
        .av-resolvido{background:rgba(0,214,143,0.15);color:#00d68f;border:1px solid #00d68f44;}
        </style>
        """, unsafe_allow_html=True)

        # ── Registrar nova avaria ──
        with st.expander("➕ Registrar nova avaria", expanded=False):
            df_estoque_av = get_current_stock()
            if df_estoque_av.empty:
                st.info("Nenhum produto no estoque para selecionar.")
            else:
                # Busca de produto
                busca_av = st.text_input("🔍 Buscar produto", placeholder="Nome ou código...", key="av_busca")
                df_filtrado_av = df_estoque_av
                if busca_av:
                    df_filtrado_av = df_estoque_av[
                        df_estoque_av["produto"].str.contains(busca_av, case=False, na=False, regex=False)
                        | df_estoque_av["codigo"].str.contains(busca_av, case=False, na=False, regex=False)
                    ]

                if df_filtrado_av.empty:
                    st.warning("Nenhum produto encontrado.")
                else:
                    opcoes = [f"{r['codigo']} — {r['produto']}" for _, r in df_filtrado_av.iterrows()]
                    sel = st.selectbox("Produto avariado", opcoes, key="av_produto_sel")

                    # Recupera linha selecionada
                    idx_sel = opcoes.index(sel)
                    row_sel = df_filtrado_av.iloc[idx_sel]

                    qtd_av = st.number_input(
                            "Qtd avariada", min_value=1,
                            max_value=int(row_sel["qtd_sistema"]) if int(row_sel["qtd_sistema"]) > 0 else 9999,
                            value=1, step=1, key="av_qtd"
                        )

                    motivo_av = st.text_area(
                        "Motivo / descrição", placeholder="Ex: embalagem rasgada, produto vencido, vazamento...",
                        key="av_motivo", height=80
                    )

                    if st.button("🔴 Registrar Avaria", type="primary", key="av_registrar"):
                        if not motivo_av.strip():
                            st.error("Descreva o motivo da avaria.")
                        else:
                            ok_av = registrar_avaria(
                                row_sel["codigo"], row_sel["produto"],
                                int(qtd_av), motivo_av.strip()
                            )
                            if ok_av:
                                st.success(f"✅ Avaria registrada: {row_sel['produto']} ({int(qtd_av)} un)")
                                st.rerun()

        # ── Filtro de visualização ──
        col_f1, col_f2 = st.columns([2, 1])
        with col_f2:
            mostrar_resolvidas = st.toggle("Mostrar resolvidas", value=False, key="av_mostrar_resolvidas")

        df_av = listar_avarias(apenas_abertas=not mostrar_resolvidas)

        if df_av.empty:
            st.markdown("""
            <div style="text-align:center;padding:40px 20px;color:rgba(255,255,255,0.3);">
                <div style="font-size:2.5rem;">✅</div>
                <div>Nenhuma avaria registrada</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            n_abertas = (df_av["status"] == "aberto").sum()
            n_resolvidas = (df_av["status"] == "resolvido").sum()
            m1, m2, m3 = st.columns(3)
            m1.metric("Total", len(df_av))
            m2.metric("🔴 Abertas", n_abertas)
            m3.metric("✅ Resolvidas", n_resolvidas)

            for _, av in df_av.iterrows():
                is_aberta = av["status"] == "aberto"
                card_cls = "av-card" if is_aberta else "av-card resolvido"
                badge_cls = "av-aberto" if is_aberta else "av-resolvido"
                badge_txt = "🔴 ABERTA" if is_aberta else "✅ RESOLVIDA"

                # Data formatada
                try:
                    dt_reg = datetime.strptime(av["registrado_em"], "%Y-%m-%d %H:%M:%S")
                    dias_av = (datetime.now(tz=_BRT).replace(tzinfo=None) - dt_reg).days
                    tempo_av = "hoje" if dias_av == 0 else ("ontem" if dias_av == 1 else f"{dias_av}d atrás")
                except Exception:
                    tempo_av = av["registrado_em"]

                st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
                st.markdown(
                    f'<span class="av-badge {badge_cls}">{badge_txt}</span>',
                    unsafe_allow_html=True
                )

                col_info_av, col_btns_av = st.columns([5, 1])
                with col_info_av:
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                        f'<div>'
                        f'<div style="color:#e0e6ed;font-weight:700;font-size:0.9rem;">{av["produto"]}</div>'
                        f'<div style="margin-top:4px;display:flex;gap:12px;flex-wrap:wrap;">'
                        f'<span style="color:#64748b;font-size:0.65rem;">Cod: <b style="color:#94a3b8;">{av["codigo"]}</b></span>'
                        f'<span style="color:#ff4757;font-size:0.7rem;font-weight:700;">Qtd: {int(av["qtd_avariada"])}</span>'
                        f'</div>'
                        f'<div style="margin-top:6px;color:#94a3b8;font-size:0.75rem;">📋 {av["motivo"]}</div>'
                        f'</div>'
                        f'<span style="color:#3b82f6;font-size:0.6rem;font-family:monospace;white-space:nowrap;">{tempo_av}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    if not is_aberta and av["resolvido_em"]:
                        st.markdown(
                            f'<div style="margin-top:4px;color:#00d68f;font-size:0.65rem;">✅ Resolvido em: {av["resolvido_em"]}</div>',
                            unsafe_allow_html=True
                        )

                with col_btns_av:
                    if is_aberta:
                        if st.button("✅", key=f"av_res_{av['id']}", help="Marcar como resolvida"):
                            resolver_avaria(int(av["id"]))
                            st.rerun()
                    if st.button("🗑️", key=f"av_del_{av['id']}", help="Excluir registro"):
                        deletar_avaria(int(av["id"]))
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

    with t8:
        import streamlit.components.v1 as components
        import calendar as _cal
        import json as _json

        # ── Coleta de eventos do próprio banco ──────────────────────────────
        hoje = datetime.now(tz=_BRT)
        ano, mes = hoje.year, hoje.month

        _MESES = ["", "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

        eventos = {}  # dia (int) -> list of (label, tipo)

        def _add_ev(dia, label, tipo="ok"):
            if 1 <= dia <= 31:
                eventos.setdefault(dia, []).append((label, tipo))

        hoje_date = hoje.date()  # usado para bloquear dias futuros

        # Avarias abertas
        try:
            df_av_ag = listar_avarias(apenas_abertas=True)
            for _, av in df_av_ag.iterrows():
                try:
                    dt = datetime.strptime(av["registrado_em"], "%Y-%m-%d %H:%M:%S")
                    if dt.year == ano and dt.month == mes and dt.date() <= hoje_date:
                        _add_ev(dt.day, f"Avaria: {av['produto']}", "alerta")
                except Exception:
                    pass
        except Exception:
            pass

        # Reposições pendentes
        try:
            for _, rep in df_reposicao.iterrows():
                try:
                    dt = datetime.strptime(rep["criado_em"], "%Y-%m-%d %H:%M:%S")
                    if dt.year == ano and dt.month == mes and dt.date() <= hoje_date:
                        _add_ev(dt.day, f"Repor: {rep['produto']}", "aviso")
                except Exception:
                    pass
        except Exception:
            pass

        # Histórico de uploads
        try:
            df_hist_ag = get_historico_uploads()
            for _, h in df_hist_ag.iterrows():
                try:
                    dt = datetime.strptime(h["data"], "%Y-%m-%d %H:%M:%S")
                    if dt.year == ano and dt.month == mes and dt.date() <= hoje_date:
                        _add_ev(dt.day, f"Upload: {h['arquivo']}", "info")
                except Exception:
                    pass
        except Exception:
            pass

        # Divergências
        if n_falta > 0 or n_sobra > 0:
            _add_ev(hoje.day, f"{n_falta} faltas / {n_sobra} sobras", "alerta" if n_falta > 0 else "aviso")

        # ── Serializar eventos para JSON (para o JS) ─────────────────────────
        eventos_js = {}
        for dia, evs in eventos.items():
            eventos_js[str(dia)] = [{"label": label, "tipo": tipo} for label, tipo in evs]
        eventos_json = _json.dumps(eventos_js)

        # ── Dados do calendário ──────────────────────────────────────────────
        primeiro_dia_semana, total_dias = _cal.monthrange(ano, mes)
        primeiro_dia_semana = (primeiro_dia_semana + 1) % 7  # Sunday=0
        nome_mes = _MESES[mes]
        hoje_dia = hoje.day

        # ── Estado: dia selecionado ──────────────────────────────────────────
        if "agenda_dia_sel" not in st.session_state:
            st.session_state["agenda_dia_sel"] = hoje_dia

        # ── Componente HTML interativo ───────────────────────────────────────
        cal_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;500;700;900&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    font-family: 'Outfit', sans-serif;
    color: #e0e6ed;
  }}
  .wrap {{
    display: flex;
    gap: 20px;
    align-items: flex-start;
    flex-wrap: wrap;
    padding: 4px 2px 8px 2px;
  }}
  /* ── Calendário ── */
  .cal-glass {{
    background: rgba(30,41,59,0.55);
    backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 20px 18px 16px 18px;
    min-width: 290px;
    max-width: 320px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }}
  .cal-header {{
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 14px;
  }}
  .cal-month {{
    font-weight: 700;
    font-size: 1.05rem;
    color: #e0e6ed;
    letter-spacing: .5px;
  }}
  .cal-grid {{
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
    text-align: center;
  }}
  .cal-dow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem;
    color: rgba(148,163,184,0.55);
    text-transform: uppercase;
    letter-spacing: 1px;
    padding-bottom: 7px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    margin-bottom: 3px;
  }}
  .cal-day {{
    font-size: 0.82rem;
    color: #cbd5e1;
    padding: 5px 2px;
    border-radius: 50%;
    cursor: pointer;
    position: relative;
    transition: background .15s, color .15s, transform .1s;
    line-height: 1.2;
    user-select: none;
    width: 32px;
    height: 32px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin: 0 auto;
  }}
  .cal-day:not(.empty):hover {{
    background: rgba(0,214,143,0.15);
    color: #00d68f;
    transform: scale(1.12);
  }}
  .cal-day.empty {{ color: transparent; cursor: default; pointer-events: none; }}
  .cal-day.today {{
    background: #e0e6ed;
    color: #0a0f1a;
    font-weight: 900;
  }}
  .cal-day.today:hover {{
    background: #c8d5e2;
    color: #0a0f1a;
  }}
  .cal-day.selected {{
    background: rgba(0,214,143,0.25);
    color: #00d68f;
    border: 1.5px solid #00d68f;
    font-weight: 700;
  }}
  .cal-day.today.selected {{
    background: #00d68f;
    color: #0a0f1a;
    border: none;
  }}
  .cal-day.weekend {{ color: rgba(148,163,184,0.4); }}
  .cal-day.weekend:hover {{ color: #00d68f; }}
  /* pontos de evento */
  .dot {{
    width: 4px;
    height: 4px;
    border-radius: 50%;
    margin-top: 2px;
  }}
  .dot-ok    {{ background: #00d68f; }}
  .dot-aviso {{ background: #ffa502; }}
  .dot-alerta{{ background: #ff4757; }}
  .dot-info  {{ background: #3b82f6; }}

  /* ── Lista de Eventos ── */
  .ev-list {{
    flex: 1;
    min-width: 220px;
    max-width: 500px;
    display: flex;
    flex-direction: column;
  }}
  .ev-title {{
    font-weight: 700;
    font-size: 0.8rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 10px;
    flex-shrink: 0;
  }}
  .ev-scroll {{
    overflow-y: auto;
    max-height: 340px;
    padding-right: 6px;
    scrollbar-width: thin;
    scrollbar-color: rgba(0,214,143,0.3) transparent;
  }}
  .ev-scroll::-webkit-scrollbar {{ width: 4px; }}
  .ev-scroll::-webkit-scrollbar-track {{ background: transparent; }}
  .ev-scroll::-webkit-scrollbar-thumb {{ background: rgba(0,214,143,0.35); border-radius: 4px; }}
  .ev-empty {{
    color: #4a5568;
    font-size: 0.78rem;
    padding: 10px 0;
  }}
  .ev-item {{
    background: rgba(30,41,59,0.6);
    border-left: 3px solid #00d68f;
    border-radius: 0 10px 10px 0;
    padding: 8px 12px;
    margin-bottom: 7px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    animation: fadeIn .2s ease;
  }}
  @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(4px) }} to {{ opacity:1; transform:translateY(0) }} }}
  .ev-item.alerta {{ border-left-color: #ff4757; }}
  .ev-item.aviso  {{ border-left-color: #ffa502; }}
  .ev-item.info   {{ border-left-color: #3b82f6; }}
  .ev-item-title  {{ font-size: 0.78rem; color: #e0e6ed; font-weight: 600; white-space: normal; word-break: break-word; }}
  .ev-item-sub    {{ font-size: 0.62rem; color: #64748b; font-family: 'JetBrains Mono', monospace; }}
</style>
</head>
<body>
<div class="wrap">
  <!-- Calendário -->
  <div class="cal-glass">
    <div class="cal-header">
      <span class="cal-month">{nome_mes} {ano}</span>
    </div>
    <div class="cal-grid" id="cal-grid">
      <!-- gerado por JS -->
    </div>
  </div>

  <!-- Lista de eventos -->
  <div class="ev-list">
    <div class="ev-title" id="ev-title">Eventos do mês</div>
    <div class="ev-scroll" id="ev-body"><!-- gerado por JS --></div>
  </div>
</div>

<script>
  const EVENTOS = {eventos_json};
  const TOTAL_DIAS = {total_dias};
  const PRIMEIRO_DIA = {primeiro_dia_semana};
  const HOJE = {hoje_dia};
  const MES = {mes};
  const ANO = {ano};
  const MESES_PT = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];

  let diaSel = HOJE;

  function tipoMaisPrioritario(tipos) {{
    if (tipos.includes('alerta')) return 'alerta';
    if (tipos.includes('aviso'))  return 'aviso';
    if (tipos.includes('info'))   return 'info';
    return 'ok';
  }}

  function renderCalendario() {{
    const grid = document.getElementById('cal-grid');
    grid.innerHTML = '';

    // Cabeçalho dias
    ['D','S','T','Q','Q','S','S'].forEach(d => {{
      const el = document.createElement('div');
      el.className = 'cal-dow';
      el.textContent = d;
      grid.appendChild(el);
    }});

    // Células vazias
    for (let i = 0; i < PRIMEIRO_DIA; i++) {{
      const el = document.createElement('div');
      el.className = 'cal-day empty';
      grid.appendChild(el);
    }}

    // Dias
    for (let d = 1; d <= TOTAL_DIAS; d++) {{
      const el = document.createElement('div');
      const evs = EVENTOS[String(d)] || [];
      const tipos = evs.map(e => e.tipo);
      const diaSemana = (PRIMEIRO_DIA + d - 1) % 7;

      let cls = 'cal-day';
      if (d === HOJE)   cls += ' today';
      else if (diaSemana === 0 || diaSemana === 6) cls += ' weekend';
      if (d === diaSel) cls += ' selected';

      el.className = cls;

      // Número
      const num = document.createElement('span');
      num.textContent = d;
      el.appendChild(num);

      // Ponto de evento
      if (evs.length > 0) {{
        const tip = tipoMaisPrioritario(tipos);
        const dot = document.createElement('div');
        dot.className = 'dot dot-' + tip;
        el.appendChild(dot);
      }}

      el.addEventListener('click', () => {{
        diaSel = d;
        renderCalendario();
        renderEventos();
      }});

      grid.appendChild(el);
    }}
  }}

  function renderEventos() {{
    const body = document.getElementById('ev-body');
    const title = document.getElementById('ev-title');

    const evsDia = EVENTOS[String(diaSel)] || [];
    const todosMes = [];
    Object.keys(EVENTOS).sort((a,b)=>parseInt(a)-parseInt(b)).forEach(dia => {{
      EVENTOS[dia].forEach(ev => todosMes.push({{dia: parseInt(dia), ...ev}}));
    }});

    // Se há dia selecionado, mostra só os eventos daquele dia (ou vazio)
    // Sem dia selecionado, mostra resumo do mês
    let lista;
    if (diaSel !== null) {{
      lista = evsDia.map(ev => ({{dia: diaSel, ...ev}}));
      title.textContent = evsDia.length > 0
        ? `Dia ${{String(diaSel).padStart(2,'0')}}/${{String(MES).padStart(2,'0')}}/${{ANO}}`
        : `Sem eventos em ${{String(diaSel).padStart(2,'0')}}/${{String(MES).padStart(2,'0')}}`;
    }} else {{
      lista = todosMes.slice(0, 12);
      title.textContent = 'Eventos do mês';
    }}

    body.innerHTML = '';

    if (lista.length === 0) {{
      const msg = diaSel !== null
        ? 'Nenhum evento neste dia.'
        : 'Nenhum evento registrado este mês.';
      body.innerHTML = `<div class="ev-empty">${{msg}}</div>`;
      return;
    }}

    lista.forEach(ev => {{
      const item = document.createElement('div');
      item.className = 'ev-item ' + (ev.tipo !== 'ok' ? ev.tipo : '');
      item.innerHTML = `
        <span class="ev-item-title">${{ev.label}}</span>
        <span class="ev-item-sub">${{String(ev.dia).padStart(2,'0')}}/${{String(MES).padStart(2,'0')}}/${{ANO}}</span>
      `;
      body.appendChild(item);
    }});
  }}

  renderCalendario();
  renderEventos();
</script>
</body>
</html>
"""

        components.html(cal_html, height=480, scrolling=False)

        # ── Legenda ──────────────────────────────────────────────────────────
        st.markdown(
            '<div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:6px;padding-left:2px;">'
            '<span style="font-size:0.65rem;color:#64748b;">🟢 Upload &nbsp; 🟡 Reposição &nbsp; 🔴 Avaria &nbsp; 🔵 Info</span>'
            '</div>',
            unsafe_allow_html=True
        )

    with t9:
        st.markdown("""
        <style>
        .ct-card{background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.18);border-radius:12px;padding:10px 14px;margin-bottom:6px;}
        .ct-card.certa{background:rgba(0,214,143,0.06);border-color:rgba(0,214,143,0.25);}
        .ct-card.divergencia{background:rgba(239,68,68,0.06);border-color:rgba(239,68,68,0.25);}
        .ct-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:0.68rem;font-weight:700;letter-spacing:.5px;}
        .ct-certa{background:rgba(0,214,143,0.15);color:#00d68f;border:1px solid #00d68f44;}
        .ct-divergencia{background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid #ef444444;}
        .ct-pendente{background:rgba(100,116,139,0.15);color:#94a3b8;border:1px solid #64748b44;}
        .ct-cat-header{font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#64748b;margin:12px 0 4px;padding:0 2px;}
        .ct-nome{font-weight:600;font-size:0.88rem;color:#e0e6ed;}
        .ct-qty{font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:#3b82f6;margin-left:8px;}
        .ct-motivo{font-size:0.7rem;color:#94a3b8;margin-top:3px;}
        </style>
        """, unsafe_allow_html=True)

        df_ct = get_contagem_itens()

        if df_ct.empty:
            st.info("Nenhuma contagem disponível. Faça o upload de uma planilha PARCIAL para iniciar a contagem.")
        else:
            n_total = len(df_ct)
            n_certas = int((df_ct["status"] == "certa").sum())
            n_divs = int((df_ct["status"] == "divergencia").sum())
            n_pend = int((df_ct["status"] == "pendente").sum())

            hdr_col, btn_col = st.columns([5, 1])
            with hdr_col:
                st.markdown(f"""
                <div class="stat-row">
                    <div class="stat-card"><div class="stat-value">{n_total}</div><div class="stat-label">Total</div></div>
                    <div class="stat-card"><div class="stat-value">{n_certas}</div><div class="stat-label">Certas</div></div>
                    <div class="stat-card"><div class="stat-value red">{n_divs}</div><div class="stat-label">Divergências</div></div>
                    <div class="stat-card"><div class="stat-value amber">{n_pend}</div><div class="stat-label">Pendentes</div></div>
                </div>
                """, unsafe_allow_html=True)
            with btn_col:
                if st.button("🗑️ Limpar lista", key="ct_limpar", help="Apaga toda a contagem atual"):
                    limpar_contagem()
                    st.rerun()

            # Banner de conclusão quando tudo foi revisado
            if n_pend == 0 and n_total > 0:
                st.success(f"✅ Contagem concluída! {n_certas} certa(s) · {n_divs} divergência(s). Clique em 'Limpar lista' para encerrar.")

            if "contagem_div_open" not in st.session_state:
                st.session_state.contagem_div_open = set()

            cats = sorted(df_ct["categoria"].unique())
            for cat in cats:
                df_cat = df_ct[df_ct["categoria"] == cat]
                # Exibe apenas itens pendentes (confirmados somem da lista, igual ao repor loja)
                df_cat_pend = df_cat[df_cat["status"] == "pendente"]
                if df_cat_pend.empty:
                    continue
                n_cat_pend = len(df_cat_pend)
                n_cat_total = len(df_cat)
                st.markdown(
                    f'<div class="ct-cat-header">{cat} '
                    f'({n_cat_pend} pendente{"s" if n_cat_pend != 1 else ""}'
                    f'{f" de {n_cat_total}" if n_cat_total != n_cat_pend else ""})</div>',
                    unsafe_allow_html=True,
                )

                for _, item in df_cat_pend.iterrows():
                    item_id = int(item["id"])
                    prod = str(item["produto"])
                    qty = int(item["qtd_estoque"])
                    _cod = str(item["codigo"])
                    _qtd_sis = qty

                    col_info, col_b1, col_b2 = st.columns([5, 1.2, 1.2])

                    with col_info:
                        info_html = (
                            f'<span class="ct-nome">{prod}</span>'
                            f'<span class="ct-cod" style="color:#94a3b8;font-size:0.78em;margin-left:8px;font-weight:400;">#{_cod}</span>'
                            f'<span class="ct-qty">{qty} un</span>'
                        )
                        st.markdown(f'<div class="ct-card pendente">{info_html}</div>', unsafe_allow_html=True)

                    with col_b1:
                        if st.button("✅ Certa", key=f"ct_ok_{item_id}", use_container_width=True):
                            atualizar_item_contagem(item_id, "certa", codigo=_cod, qtd_sistema=_qtd_sis)
                            st.session_state.contagem_div_open.discard(item_id)
                            st.rerun()

                    with col_b2:
                        if item_id not in st.session_state.contagem_div_open:
                            if st.button("❌ Divergência", key=f"ct_divbtn_{item_id}", use_container_width=True):
                                st.session_state.contagem_div_open.add(item_id)
                                st.rerun()
                        else:
                            if st.button("Cancelar", key=f"ct_cancel_open_{item_id}", use_container_width=True):
                                st.session_state.contagem_div_open.discard(item_id)
                                st.rerun()

                    if item_id in st.session_state.contagem_div_open:
                        fc1, fc2, fc3 = st.columns([3, 1.5, 1])
                        with fc1:
                            motivo_val = st.text_input(
                                "Motivo da divergência",
                                key=f"ct_motivo_{item_id}",
                                placeholder="Ex: produto vencido, faltando, danificado..."
                            )
                        with fc2:
                            qty_val = st.number_input(
                                "Qtd divergindo (− falta / + sobra)",
                                min_value=-9999, max_value=9999, value=0, step=1,
                                key=f"ct_qtd_{item_id}"
                            )
                        with fc3:
                            st.markdown("<div style='margin-top:26px'>", unsafe_allow_html=True)
                            if st.button("Confirmar", key=f"ct_conf_{item_id}", type="primary", use_container_width=True):
                                tipo_div_str = "sobra" if qty_val >= 0 else "falta"
                                ok = atualizar_item_contagem(
                                    item_id, "divergencia",
                                    motivo_val.strip(), abs(int(qty_val)),
                                    codigo=_cod, qtd_sistema=_qtd_sis,
                                    tipo_div=tipo_div_str
                                )
                                if not ok:
                                    st.warning(f"⚠️ Divergência salva na contagem, mas não refletiu no estoque (código: {_cod}). Reporte ao suporte.")
                                st.session_state.contagem_div_open.discard(item_id)
                                st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

    with t10:
        # ── CSS da aba ──────────────────────────────────────────────────────────
        st.markdown("""
        <style>
        .val-kpi-row{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;}
        .val-kpi{flex:1;min-width:80px;background:linear-gradient(135deg,#111827,#1a2332);
                 border:1px solid #1e293b;border-radius:10px;padding:8px 10px;text-align:center;}
        .val-kpi-v{font-family:'JetBrains Mono',monospace;font-size:1.1rem;font-weight:700;color:#00d68f;}
        .val-kpi-v.red{color:#ff4757;} .val-kpi-v.amber{color:#ffa502;} .val-kpi-v.yellow{color:#ffd32a;}
        .val-kpi-l{font-size:0.58rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;}
        .val-badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:0.68rem;font-weight:700;}
        .val-vencido{background:rgba(239,68,68,.15);color:#ef4444;border:1px solid #ef444455;}
        .val-30{background:rgba(255,71,87,.12);color:#ff4757;border:1px solid #ff475755;}
        .val-60{background:rgba(255,165,2,.12);color:#ffa502;border:1px solid #ffa50255;}
        .val-90{background:rgba(255,211,42,.10);color:#ffd32a;border:1px solid #ffd32a55;}
        .val-ok{background:rgba(0,214,143,.10);color:#00d68f;border:1px solid #00d68f55;}
        .val-section{font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
                     color:#64748b;margin:14px 0 4px;padding:0 2px;}
        .val-row{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);
                 border-radius:8px;padding:8px 10px;margin-bottom:4px;}
        .val-prod{font-weight:600;font-size:0.85rem;color:#e0e6ed;}
        .val-meta{font-size:0.68rem;color:#64748b;margin-top:2px;}
        .val-lote{font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:#3b82f6;}
        </style>
        """, unsafe_allow_html=True)

        # ── Upload — substitui os dados no banco ─────────────────────────────
        with st.expander("📤 Enviar nova planilha de validade", expanded=False):
            uploaded_val = st.file_uploader(
                "Planilha SIG de validade (.xlsx)",
                type=["xlsx"],
                key="val_upload",
                help="Planilha SIG — relatório de produtos com lote, fabricação e vencimento",
                label_visibility="collapsed",
            )
            if uploaded_val is not None:
                try:
                    df_raw = pd.read_excel(uploaded_val, header=3, engine="openpyxl")
                    df_raw.columns = ["FILIAL", "GRUPO", "PRODUTO", "LOTE", "FABRICACAO", "VENCIMENTO", "QUANTIDADE", "VALOR"]
                    df_raw["FILIAL"]   = df_raw["FILIAL"].ffill()
                    df_raw["GRUPO"]    = df_raw["GRUPO"].ffill()
                    df_raw["PRODUTO"]  = df_raw["PRODUTO"].ffill()
                    df_parsed = df_raw[
                        df_raw["LOTE"].notna() &
                        (df_raw["LOTE"].astype(str).str.strip() != "Sum") &
                        (df_raw["LOTE"].astype(str).str.strip() != "")
                    ].copy()
                    df_parsed["VENCIMENTO"] = pd.to_datetime(df_parsed["VENCIMENTO"], errors="coerce")
                    df_parsed["FABRICACAO"] = pd.to_datetime(df_parsed["FABRICACAO"], errors="coerce")
                    df_parsed["QUANTIDADE"] = pd.to_numeric(df_parsed["QUANTIDADE"], errors="coerce").fillna(0).astype(int)
                    df_parsed["VALOR"]      = pd.to_numeric(df_parsed["VALOR"],      errors="coerce").fillna(0)

                    st.caption(f"✅ {len(df_parsed)} lotes encontrados na planilha.")
                    if st.button("💾 Salvar no banco", type="primary", key="val_salvar"):
                        if save_validade_lotes(df_parsed):
                            st.success(f"✅ {len(df_parsed)} lotes salvos no banco com sucesso!")
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao processar planilha: {e}")
                    st.info("Verifique se é a planilha SIG de validade com as colunas: FILIAL, GRUPO, PRODUTO, LOTE, FABRICAÇÃO, VENCIMENTO, QUANTIDADE, VALOR")

        # ── Carrega dados do banco ────────────────────────────────────────────
        df_val_db = get_validade_lotes()

        if df_val_db.empty:
            st.markdown("""
            <div style="text-align:center;padding:40px 20px;color:#64748b;">
                <div style="font-size:2.5rem;margin-bottom:12px;">📋</div>
                <div style="font-size:0.9rem;margin-bottom:6px;">Nenhuma planilha carregada ainda</div>
                <div style="font-size:0.75rem;">Use o botão acima para enviar a planilha SIG de validade</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            upload_date = get_validade_upload_date()
            try:
                upload_date_fmt = datetime.strptime(upload_date, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
            except Exception:
                upload_date_fmt = upload_date
            st.caption(f"☁️ Dados carregados do banco · Última atualização: **{upload_date_fmt}** · {len(df_val_db)} lotes")

            hoje = pd.Timestamp.now().normalize()
            df_val_db["DIAS"]   = (df_val_db["VENCIMENTO"] - hoje).dt.days
            df_val_db["STATUS"] = df_val_db["DIAS"].apply(
                lambda d: "VENCIDO" if d < 0
                else "≤30 dias"  if d <= 30
                else "≤60 dias"  if d <= 60
                else "≤90 dias"  if d <= 90
                else "OK"
            )

            # ── KPIs ──────────────────────────────────────────────────────────
            n_vencidos = int((df_val_db["STATUS"] == "VENCIDO").sum())
            n_30       = int((df_val_db["STATUS"] == "≤30 dias").sum())
            n_60       = int((df_val_db["STATUS"] == "≤60 dias").sum())
            n_90       = int((df_val_db["STATUS"] == "≤90 dias").sum())
            n_ok       = int((df_val_db["STATUS"] == "OK").sum())
            val_risco  = df_val_db[df_val_db["STATUS"].isin(["VENCIDO","≤30 dias","≤60 dias"])]["VALOR"].sum()

            st.markdown(f"""
            <div class="val-kpi-row">
                <div class="val-kpi"><div class="val-kpi-v red">{n_vencidos}</div><div class="val-kpi-l">Vencidos</div></div>
                <div class="val-kpi"><div class="val-kpi-v red">{n_30}</div><div class="val-kpi-l">≤30 dias</div></div>
                <div class="val-kpi"><div class="val-kpi-v amber">{n_60}</div><div class="val-kpi-l">≤60 dias</div></div>
                <div class="val-kpi"><div class="val-kpi-v yellow">{n_90}</div><div class="val-kpi-l">≤90 dias</div></div>
                <div class="val-kpi"><div class="val-kpi-v">{n_ok}</div><div class="val-kpi-l">OK</div></div>
                <div class="val-kpi"><div class="val-kpi-v red">R$ {val_risco:,.0f}</div><div class="val-kpi-l">Valor em risco</div></div>
            </div>
            """, unsafe_allow_html=True)

            # ── Filtros ────────────────────────────────────────────────────────
            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                grupos = ["Todos"] + sorted(df_val_db["GRUPO"].dropna().unique().tolist())
                grupo_sel = st.selectbox("Grupo", grupos, key="val_grupo")
            with fc2:
                status_opts = ["Todos", "VENCIDO", "≤30 dias", "≤60 dias", "≤90 dias", "OK"]
                status_sel = st.selectbox("Status", status_opts, key="val_status", index=0)
            with fc3:
                mostrar_ok = st.checkbox("Mostrar OK", value=False, key="val_show_ok")

            df_show = df_val_db.copy()
            if grupo_sel != "Todos":
                df_show = df_show[df_show["GRUPO"] == grupo_sel]
            if status_sel != "Todos":
                df_show = df_show[df_show["STATUS"] == status_sel]
            elif not mostrar_ok:
                df_show = df_show[df_show["STATUS"] != "OK"]
            df_show = df_show.sort_values("DIAS")

            # ── Gráfico por grupo (valor em risco) ────────────────────────────
            df_risco_grp = (
                df_val_db[df_val_db["STATUS"].isin(["VENCIDO","≤30 dias","≤60 dias","≤90 dias"])]
                .groupby("GRUPO")["VALOR"].sum()
                .sort_values(ascending=True)
                .reset_index()
            )
            if not df_risco_grp.empty:
                fig_bar = go.Figure(go.Bar(
                    x=df_risco_grp["VALOR"],
                    y=df_risco_grp["GRUPO"],
                    orientation="h",
                    marker_color="#ff4757",
                    text=df_risco_grp["VALOR"].apply(lambda v: f"R$ {v:,.0f}"),
                    textposition="outside",
                ))
                fig_bar.update_layout(
                    title="💰 Valor em risco por grupo (≤90 dias + vencidos)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8", size=11),
                    height=max(200, len(df_risco_grp)*32 + 60),
                    margin=dict(l=10, r=80, t=40, b=10),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(tickfont=dict(size=10)),
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False, "editable": False, "scrollZoom": False})

            # ── Lista de lotes ─────────────────────────────────────────────────
            badge_map = {
                "VENCIDO":   '<span class="val-badge val-vencido">🔴 VENCIDO</span>',
                "≤30 dias":  '<span class="val-badge val-30">🟠 ≤30 dias</span>',
                "≤60 dias":  '<span class="val-badge val-60">🟡 ≤60 dias</span>',
                "≤90 dias":  '<span class="val-badge val-90">⚪ ≤90 dias</span>',
                "OK":        '<span class="val-badge val-ok">🟢 OK</span>',
            }

            st.markdown(f'<div class="val-section">{len(df_show)} lote(s) encontrado(s)</div>', unsafe_allow_html=True)

            for _, row in df_show.iterrows():
                prod_nome = str(row["PRODUTO"]).split(" - ", 1)[-1] if " - " in str(row["PRODUTO"]) else str(row["PRODUTO"])
                lote      = str(row["LOTE"])
                grp_nome  = str(row["GRUPO"])
                venc_str  = row["VENCIMENTO"].strftime("%d/%m/%Y") if pd.notna(row["VENCIMENTO"]) else "?"
                dias_str  = f"{abs(int(row['DIAS']))} dias {'atrás' if row['DIAS'] < 0 else 'restantes'}" if pd.notna(row["DIAS"]) else ""
                qtd       = int(row["QUANTIDADE"])
                valor     = float(row["VALOR"])
                badge_html = badge_map.get(row["STATUS"], row["STATUS"])

                st.markdown(f"""
                <div class="val-row">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:4px;">
                        <span class="val-prod">{prod_nome}</span>
                        {badge_html}
                    </div>
                    <div class="val-meta">
                        <span class="val-lote">Lote: {lote}</span>
                        &nbsp;·&nbsp; Grupo: {grp_nome}
                        &nbsp;·&nbsp; Vencimento: {venc_str}
                        &nbsp;·&nbsp; {dias_str}
                        &nbsp;·&nbsp; Qtd: {qtd} un
                        &nbsp;·&nbsp; Valor: R$ {valor:,.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # ── Download CSV ───────────────────────────────────────────────────
            st.markdown("---")
            csv_val = df_show[["GRUPO","PRODUTO","LOTE","FABRICACAO","VENCIMENTO","QUANTIDADE","VALOR","STATUS","DIAS"]].copy()
            csv_val["FABRICACAO"] = csv_val["FABRICACAO"].dt.strftime("%d/%m/%Y")
            csv_val["VENCIMENTO"] = csv_val["VENCIMENTO"].dt.strftime("%d/%m/%Y")
            csv_bytes = csv_val.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Exportar lista filtrada (.csv)",
                data=csv_bytes,
                file_name=f"validade_{datetime.now(tz=_BRT).strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key="val_download"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 11 — HISTÓRICO DE VENDAS
    # ══════════════════════════════════════════════════════════════════════════
    with t11:
        df_dia   = get_vendas_por_dia()
        df_top   = get_top_produtos_historico(top_n=20)
        periodo  = get_periodo_vendas()

        if df_dia.empty:
            st.markdown("""
            <div style="text-align:center;padding:40px 20px;color:rgba(255,255,255,0.3);">
                <div style="font-size:2.5rem;">📊</div>
                <div>Nenhum histórico ainda. Comece a enviar as planilhas diárias de vendas.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # ── KPIs do período ──────────────────────────────────────────
            total_unidades = int(df_dia["total_vendido"].sum())
            media_dia      = round(df_dia["total_vendido"].mean(), 1)
            melhor_dia_row = df_dia.loc[df_dia["total_vendido"].idxmax()]
            melhor_dia     = str(melhor_dia_row["dia"])
            melhor_qtd     = int(melhor_dia_row["total_vendido"])

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("📅 Dias com dados", periodo)
            k2.metric("📦 Total vendido", f"{total_unidades:,}".replace(",", "."))
            k3.metric("📈 Média/dia", f"{media_dia:.0f} un.")
            k4.metric("🏆 Melhor dia", f"{melhor_qtd} un.", melhor_dia)

            # ── Gráfico de linha: unidades vendidas por dia ───────────────
            st.markdown("##### Unidades vendidas por dia")
            dias_label = [str(d) for d in df_dia["dia"]]

            fig_linha = go.Figure()
            fig_linha.add_trace(go.Scatter(
                x=dias_label,
                y=df_dia["total_vendido"],
                mode="lines+markers",
                line=dict(color="#00d68f", width=2),
                marker=dict(size=5, color="#00d68f"),
                fill="tozeroy",
                fillcolor="rgba(0,214,143,0.08)",
                hovertemplate="<b>%{x}</b><br>%{y} unidades<extra></extra>",
            ))
            fig_linha.update_layout(
                **_PLOTLY_LAYOUT,
                height=280,
                xaxis=dict(
                    gridcolor="#1e293b",
                    tickangle=-45,
                    tickfont=dict(size=9),
                ),
                yaxis=dict(gridcolor="#1e293b", title="Unidades"),
                showlegend=False,
            )
            st.plotly_chart(fig_linha, use_container_width=True,
                            config={"displayModeBar": False, "editable": False, "scrollZoom": False})

            # ── Gráfico de barras: top produtos ───────────────────────────
            if not df_top.empty:
                st.markdown("##### Top 20 produtos mais vendidos no período")

                # nome curto para caber no gráfico
                df_top["nome_curto"] = df_top["produto"].apply(
                    lambda p: (p.split(" - ")[-1] if " - " in p else p)[:35]
                )
                cores_top = [_get_color(g) for g in df_top["grupo"]]

                fig_top_h = go.Figure()
                fig_top_h.add_trace(go.Bar(
                    y=df_top["nome_curto"][::-1],
                    x=df_top["total"][::-1],
                    orientation="h",
                    marker=dict(color=cores_top[::-1], cornerradius=4),
                    text=df_top["total"][::-1].apply(lambda v: f"{int(v):,}".replace(",", ".")),
                    textposition="outside",
                    textfont=dict(size=9, color="#94a3b8"),
                    hovertemplate="<b>%{y}</b><br>%{x} unidades<extra></extra>",
                ))
                fig_top_h.update_layout(
                    **_PLOTLY_LAYOUT,
                    height=max(400, len(df_top) * 28),
                    xaxis=dict(gridcolor="#1e293b", title="Unidades vendidas"),
                    yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9)),
                    showlegend=False,
                )
                st.plotly_chart(fig_top_h, use_container_width=True,
                                config={"displayModeBar": False, "editable": False, "scrollZoom": False})

            # ── Botão para zerar histórico ────────────────────────────────
            if st.button("🗑️ Zerar histórico de vendas", key="hist_zerar", type="secondary"):
                st.session_state["hist_confirmar_zerar"] = True

            if st.session_state.get("hist_confirmar_zerar"):
                st.warning("Tem certeza? Isso apaga todo o histórico acumulado de vendas.")
                col_sim, col_nao = st.columns(2)
                with col_sim:
                    if st.button("✅ Sim, zerar", key="hist_zerar_sim", type="primary", use_container_width=True):
                        get_db().execute("DELETE FROM vendas_historico")
                        get_db().execute("COMMIT")
                        sync_db()
                        st.session_state.pop("hist_confirmar_zerar", None)
                        st.session_state.pop("alertas_cache", None)
                        st.success("Histórico zerado. Comece a enviar as planilhas do novo período.")
                        st.rerun()
                with col_nao:
                    if st.button("✖ Cancelar", key="hist_zerar_nao", use_container_width=True):
                        st.session_state.pop("hist_confirmar_zerar", None)
                        st.rerun()


    # ══════════════════════════════════════════════════════════════════════════
    # TAB 12 — ESTOQUE POR PRINCÍPIO ATIVO
    # ══════════════════════════════════════════════════════════════════════════
    with t12:
        build_principios_ativos_tab(df_mestre, df_pa)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 13 — INFOGRÁFICOS
    # ══════════════════════════════════════════════════════════════════════════
    with t13:
        build_infograficos_tab()

    with t_mapa:
        render_mapa_visual(get_db())


# ── Upload Section ───────────────────────────────────────────────────────────
with st.expander("📤 Upload de Planilha", expanded=not has_mestre):

    if not st.session_state.admin_unlocked:
        # ── Portão de senha ──────────────────────────────────────────────
        st.markdown(
            '<div style="text-align:center;padding:20px 16px 12px;">'
            '<div style="font-size:2.2rem;margin-bottom:6px;">🔒</div>'
            '<div style="font-size:1rem;font-weight:600;color:#e0e6ed;margin-bottom:4px;">Área Protegida</div>'
            '<div style="font-size:0.8rem;color:#64748b;">'
            'Digite a senha de edição para fazer uploads ou alterar o estoque.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        _col_pwd, _col_btn = st.columns([3, 1])
        with _col_pwd:
            _edit_pwd = st.text_input(
                "Senha edição", type="password",
                placeholder="🔑 Senha de edição",
                label_visibility="collapsed",
                key="edit_pwd_input",
            )
        with _col_btn:
            if st.button("🔓 Entrar", type="primary", key="btn_edit_unlock", use_container_width=True):
                if _edit_pwd == EDIT_PASSWORD:
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta")
    else:
        # ── Botão para bloquear novamente ────────────────────────────────
        _col_relock, _ = st.columns([1, 5])
        with _col_relock:
            if st.button("🔒 Bloquear", key="btn_relock"):
                st.session_state.admin_unlocked = False
                st.rerun()

        if not has_mestre:
            st.info("👋 Nenhum estoque cadastrado. Faça o upload da planilha mestre para começar.")

        opcao_mestre = "MESTRE (carga completa)" if not has_mestre else "MESTRE (substituir tudo)"
        opcao_parcial_vendas = "Parcial (vendas)"
        opcao_parcial_estoque = "Parcial (estoque)"
        upload_mode = st.radio(
            "Tipo de Upload",
            [opcao_mestre, opcao_parcial_vendas, opcao_parcial_estoque],
            index=0 if not has_mestre else 1,
            horizontal=True,
            label_visibility="collapsed",
        )
        is_mestre_upload = "MESTRE" in upload_mode
        is_parcial_estoque = upload_mode == opcao_parcial_estoque

        if is_mestre_upload:
            st.warning("⚠️ Este upload **substitui todo o estoque**. Use para carga inicial ou recomeçar do zero.")
            data_planilha = datetime.now(tz=_BRT).date()
        elif is_parcial_estoque:
            st.info("Atualiza apenas a quantidade dos produtos da planilha. Não mexe em vendas, observações nem reposição.")
            data_planilha = datetime.now(tz=_BRT).date()
        else:
            st.caption("Atualiza apenas os produtos da planilha. Os demais permanecem inalterados.")
            data_planilha = st.date_input(
                "📅 Data da planilha",
                value=datetime.now(tz=_BRT).date(),
                max_value=datetime.now(tz=_BRT).date(),
                help="Selecione a data a que esta planilha se refere. Use quando a planilha é de um dia anterior ao de hoje.",
            )

        uploaded = st.file_uploader("Planilha XLSX", type=["xlsx", "xls"], label_visibility="collapsed", key="upload_main")

        if uploaded:
            # Parseia UMA VEZ e guarda no session_state
            # Inclui upload_mode no file_id para re-parsear se o tipo mudar
            file_id = f"{uploaded.name}_{uploaded.size}_{upload_mode}"
            if st.session_state.processed_file != file_id:
                if is_parcial_estoque:
                    try:
                        df_raw = pd.read_excel(uploaded, sheet_name=0, header=None)
                        ok, result = parse_parcial_estoque(df_raw)
                        zerados = []
                    except Exception as e:
                        ok, result, zerados = False, f"Erro ao ler arquivo: {e}", []
                else:
                    ok, result, zerados = read_excel_to_records(uploaded)
                st.session_state["_parsed_ok"] = ok
                st.session_state["_parsed_result"] = result
                st.session_state["_parsed_zerados"] = zerados
                st.session_state.processed_file = file_id

            ok = st.session_state.get("_parsed_ok", False)
            result = st.session_state.get("_parsed_result")
            zerados = st.session_state.get("_parsed_zerados", [])

            if ok:
                records = result
                with st.expander("👁️ Preview", expanded=False):
                    df_preview = pd.DataFrame(records)
                    n_div = sum(1 for r in records if r["status"] != "ok")
                    st.caption(f"{len(records)} produtos encontrados")
                    if n_div:
                        st.warning(f"⚠️ {n_div} divergência(s)")
                    if zerados:
                        st.info(f"🗑️ {len(zerados)} produto(s) com estoque zerado serão removidos do mestre")
                    st.dataframe(
                        df_preview[["codigo", "produto", "categoria", "qtd_sistema", "qtd_fisica", "diferenca", "nota", "status"]],
                        hide_index=True, use_container_width=True, height=250,
                    )

                if st.button("🚀 Processar", type="primary"):
                    with st.spinner("Processando..."):
                        if is_mestre_upload:
                            ok_up, msg = upload_mestre(records)
                        elif is_parcial_estoque:
                            ok_up, msg = upload_parcial_estoque(records)
                        else:
                            ok_up, msg = upload_parcial(records, zerados)

                    if ok_up:
                        st.success(msg)
                        # Salvar dados de vendas para gráficos (apenas Mestre e Parcial vendas)
                        if not is_parcial_estoque:
                            save_vendas_historico(records, _GRUPO_MAP, zerados, is_mestre=is_mestre_upload, data_ref=data_planilha.isoformat())
                        if _using_cloud:
                            st.info("☁️ Sincronizado.")
                        st.session_state.processed_file = None
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.error(result)

        # Admin
        if has_mestre:
            st.markdown("---")

            # Upload de Princípios Ativos
            st.markdown("##### 🧬 Base de Princípios Ativos")
            pa_count = get_pa_count()
            if pa_count > 0:
                st.caption(f"✅ {pa_count} registros de princípios ativos carregados. A busca por princípio ativo está ativa.")
            else:
                st.caption("Carregue a planilha de princípios ativos para habilitar a busca por P.A. e a aba 🧬 P. Ativos.")

            uploaded_pa = st.file_uploader(
                "Planilha de Princípios Ativos (produtos_CAMDA.xlsx ou formato simples)",
                type=["xlsx", "xls"],
                label_visibility="collapsed", key="upload_pa"
            )
            if uploaded_pa:
                pa_records = load_principios_ativos_from_excel(uploaded_pa)
                if pa_records:
                    if st.button("🧬 Carregar Princípios Ativos", type="primary"):
                        sync_principios_ativos(pa_records)
                        st.success(f"✅ {len(pa_records)} registros de princípios ativos carregados!")
                        st.rerun()
                else:
                    st.error("Não foi possível ler a planilha. Esperado: colunas 'Produto' e 'Princípio Ativo' (ou arquivo produtos_CAMDA.xlsx com 3 abas).")

            # ── Ajuste Manual de Quantidade ───────────────────────────────
            st.markdown("---")
            st.markdown("##### ✏️ Ajuste Manual de Quantidade")
            st.caption("Pesquise o código, informe a quantidade real e salve. As vendas continuam descontando normalmente.")

            cod_ajuste = st.text_input(
                "Código do produto", placeholder="Ex: US227579", key="input_ajuste_codigo"
            ).strip()

            if cod_ajuste:
                row_aj = get_db().execute(
                    "SELECT produto, qtd_sistema, qtd_fisica FROM estoque_mestre WHERE codigo = ?",
                    (cod_ajuste,),
                ).fetchone()
                if row_aj:
                    st.info(f"**{row_aj[0]}** · código `{cod_ajuste}` · quantidade atual: **{row_aj[1]} un.**")
                    nova_qtd = st.number_input(
                        "Nova quantidade", min_value=0, value=int(row_aj[1]), step=1, key="input_nova_qtd"
                    )
                    if st.button("💾 Salvar quantidade", type="primary", key="btn_salvar_qtd"):
                        ok, msg = ajustar_qtd_manual(cod_ajuste, int(nova_qtd))
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun()
                else:
                    st.warning(f"Código `{cod_ajuste}` não encontrado no mestre.")

            # ── Excluir registro do mestre ────────────────────────────────
            st.markdown("---")
            st.markdown("##### 🗑️ Excluir Registro do Mestre")
            st.caption(
                "Use quando um código foi importado errado e precisa ser removido. "
                "Não afeta vendas, lançamentos nem nenhuma outra tabela."
            )

            cod_excluir = st.text_input(
                "Código a excluir", placeholder="Ex: 227579", key="input_excluir_codigo"
            ).strip()

            if cod_excluir:
                row_exc = get_db().execute(
                    "SELECT produto, qtd_sistema FROM estoque_mestre WHERE codigo = ?",
                    (cod_excluir,),
                ).fetchone()
                if row_exc:
                    st.warning(
                        f"Encontrado: **{row_exc[0]}** · código `{cod_excluir}` · {row_exc[1]} un.  \n"
                        "Essa ação remove apenas este registro do mestre. Nenhum dado de venda ou lançamento é alterado."
                    )
                    if "confirm_excluir" not in st.session_state:
                        st.session_state.confirm_excluir = False

                    if not st.session_state.confirm_excluir:
                        if st.button("🗑️ Excluir este registro", type="primary", key="btn_excluir"):
                            st.session_state.confirm_excluir = True
                            st.rerun()
                    else:
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Sim, excluir", type="primary", key="btn_confirm_excluir"):
                                ok, msg = excluir_produto_mestre(cod_excluir)
                                st.session_state.confirm_excluir = False
                                if ok:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                st.rerun()
                        with c2:
                            if st.button("Cancelar", key="btn_cancel_excluir"):
                                st.session_state.confirm_excluir = False
                                st.rerun()
                else:
                    st.info(f"Código `{cod_excluir}` não encontrado no mestre.")

            st.markdown("---")
            _, col_sync, col_reset = st.columns([2, 1, 1])
            with col_sync:
                if _using_cloud and st.button("🔄 Sincronizar"):
                    sync_db()
                    st.rerun()
            with col_reset:
                if st.session_state.confirm_reset:
                    st.warning("Tem certeza?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Sim, limpar"):
                            reset_db()
                            st.session_state.confirm_reset = False
                            st.rerun()
                    with c2:
                        if st.button("Cancelar"):
                            st.session_state.confirm_reset = False
                            st.rerun()
                else:
                    if st.button("🗑️ Limpar BD"):
                        st.session_state.confirm_reset = True
                        st.rerun()


# ── Rodapé ──────────────────────────────────────────────────────────────────
st.markdown("---")
if _using_cloud:
    st.markdown('<div class="sync-badge">☁️ CONECTADO AO TURSO · BANCO COMPARTILHADO</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sync-badge">⚠️ MODO LOCAL · Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN para compartilhar</div>', unsafe_allow_html=True)

# ── Tela sem dados ───────────────────────────────────────────────────────────
if not has_mestre:
    st.markdown(
        '<div style="text-align:center;color:#64748b;padding:60px 20px;font-size:1rem;">'
        "Faça o upload da planilha mestre abaixo para começar 👇</div>",
        unsafe_allow_html=True,
    )
