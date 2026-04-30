"""Aba Visão Geral — mapa de bolhas animado do estoque."""
import json
import streamlit as st
import pandas as pd


def _build_payload(df: pd.DataFrame) -> str:
    """Converte DataFrame em JSON compacto para o canvas. Cache feito pelo chamador."""
    if df.empty:
        return "[]"
    rows = []
    for _, r in df.iterrows():
        raw_status = str(r.get("status") or "").lower().strip()
        contada = bool(r.get("ultima_contagem"))
        if raw_status in ("falta", "sobra"):
            vis_status = "divergencia"
        elif raw_status == "ok" and contada:
            vis_status = "ok"
        else:
            vis_status = ""  # pendente
        rows.append({
            "cod": str(r.get("codigo") or ""),
            "nome": str(r.get("produto") or ""),
            "cat": str(r.get("categoria") or ""),
            "qtd": int(r.get("qtd_sistema") or 0),
            "status": vis_status,
        })
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def build_visao_geral_tab(df_mestre: pd.DataFrame):
    payload_json = _build_payload(df_mestre)

    html = f"""
<div id="vg-root" style="position:relative;width:100%;height:680px;border-radius:16px;overflow:hidden;border:1px solid rgba(255,255,255,0.07);">
  <div style="position:absolute;top:12px;left:12px;display:flex;gap:8px;flex-wrap:wrap;z-index:2;">
    <span style="display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);color:#dfe7f2;font-size:11px;font-family:system-ui,sans-serif;"><span style="width:7px;height:7px;border-radius:50%;background:#00d68f;flex-shrink:0;"></span>OK</span>
    <span style="display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);color:#dfe7f2;font-size:11px;font-family:system-ui,sans-serif;"><span style="width:7px;height:7px;border-radius:50%;background:#ff4757;flex-shrink:0;"></span>Divergência</span>
    <span style="display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);color:#dfe7f2;font-size:11px;font-family:system-ui,sans-serif;"><span style="width:7px;height:7px;border-radius:50%;background:rgba(120,138,160,0.6);flex-shrink:0;"></span>Pendente</span>
  </div>
  <div style="position:absolute;top:10px;right:14px;display:flex;gap:14px;z-index:2;">
    <div style="text-align:center;"><div style="font-size:17px;font-weight:700;color:#00d68f;font-family:system-ui,sans-serif;" id="vg-cnt-ok">—</div><div style="font-size:10px;color:#8ea0b7;font-family:system-ui,sans-serif;">OK</div></div>
    <div style="text-align:center;"><div style="font-size:17px;font-weight:700;color:#ff4757;font-family:system-ui,sans-serif;" id="vg-cnt-div">—</div><div style="font-size:10px;color:#8ea0b7;font-family:system-ui,sans-serif;">Diverg.</div></div>
    <div style="text-align:center;"><div style="font-size:17px;font-weight:700;color:#93a4b8;font-family:system-ui,sans-serif;" id="vg-cnt-pend">—</div><div style="font-size:10px;color:#8ea0b7;font-family:system-ui,sans-serif;">Pendente</div></div>
    <div style="text-align:center;"><div style="font-size:17px;font-weight:700;color:#c8d6e8;font-family:system-ui,sans-serif;" id="vg-cnt-total">—</div><div style="font-size:10px;color:#8ea0b7;font-family:system-ui,sans-serif;">Total</div></div>
  </div>
  <canvas id="vg-scene"></canvas>
  <div id="vg-tip" style="position:absolute;pointer-events:none;opacity:0;transition:opacity .1s;min-width:185px;padding:10px 12px;border-radius:11px;background:rgba(5,9,16,0.96);border:1px solid rgba(255,255,255,0.1);color:#eef4fb;z-index:5;font-family:system-ui,sans-serif;font-size:11px;"></div>
</div>
<script>
(function(){{
  const ITEMS = {payload_json};
  const BG = "#0c111c";
  const colorMap = {{ok:"#00d68f", divergencia:"#ff4757", "":"rgba(100,120,148,0.5)"}};

  const okN   = ITEMS.filter(x=>x.status==="ok").length;
  const divN  = ITEMS.filter(x=>x.status==="divergencia").length;
  const pendN = ITEMS.filter(x=>x.status==="").length;
  document.getElementById("vg-cnt-ok").textContent    = okN;
  document.getElementById("vg-cnt-div").textContent   = divN;
  document.getElementById("vg-cnt-pend").textContent  = pendN;
  document.getElementById("vg-cnt-total").textContent = ITEMS.length;

  const root   = document.getElementById("vg-root");
  const canvas = document.getElementById("vg-scene");
  const ctx    = canvas.getContext("2d");
  const tip    = document.getElementById("vg-tip");

  let W=0, H=0, bubbles=[], mouse={{x:-9999,y:-9999}}, hovered=null, lastHovered=null, rafId=null;
  const DPR = Math.min(1.5, window.devicePixelRatio||1);

  function resize(){{
    const rect = root.getBoundingClientRect();
    W = rect.width; H = rect.height;
    canvas.width  = Math.floor(W*DPR);
    canvas.height = Math.floor(H*DPR);
    canvas.style.width    = W+"px";
    canvas.style.height   = H+"px";
    canvas.style.position = "absolute";
    canvas.style.top      = "0";
    canvas.style.left     = "0";
    ctx.setTransform(DPR,0,0,DPR,0,0);
    build();
  }}

  function build(){{
    const n = ITEMS.length;
    if(!n) return;
    const padX=28, padTop=72, padBot=20;
    const uw = W - padX*2;
    const uh = H - padTop - padBot;
    const rMax = Math.sqrt((uw*uh)/(n*5.5));
    const r    = Math.max(3, Math.min(7, rMax));
    const cols = Math.max(10, Math.ceil(Math.sqrt(n*(uw/uh))));
    const rows = Math.ceil(n/cols);
    const sx   = uw/cols;
    const sy   = uh/Math.max(1,rows);
    const amp  = Math.max(0.8, r*0.28);
    bubbles = ITEMS.map((item,i)=>{{
      const row=Math.floor(i/cols), col=i%cols;
      const ox=(row%2)*(sx*0.5);
      return {{
        ...item, r, amp,
        bx: padX + col*sx + ox + sx*0.5,
        by: padTop + row*sy + sy*0.5,
        phase: (i*0.618033)%(Math.PI*2),
        speed: 0.38+((i%11)*0.04),
        x:0, y:0
      }};
    }});
  }}

  function render(t){{
    const time = t*0.001;
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle = BG;
    ctx.fillRect(0,0,W,H);
    hovered = null;
    const mx=mouse.x, my=mouse.y;
    for(const b of bubbles){{
      b.x = b.bx + Math.sin(time*b.speed+b.phase)*b.amp;
      b.y = b.by + Math.cos(time*b.speed*0.82+b.phase+2.1)*b.amp*0.75;
      const dx=mx-b.x, dy=my-b.y, hit=b.r+10;
      const over=(dx*dx+dy*dy)<hit*hit;
      if(over && !hovered) hovered=b;
      ctx.beginPath();
      ctx.arc(b.x, b.y, over ? b.r*1.4 : b.r, 0, Math.PI*2);
      ctx.fillStyle = colorMap[b.status]||colorMap[""];
      ctx.fill();
    }}
    if(hovered){{
      ctx.beginPath();
      ctx.arc(hovered.x, hovered.y, hovered.r*1.4, 0, Math.PI*2);
      ctx.fillStyle   = hovered.status==="ok"?"#00ff9f":hovered.status==="divergencia"?"#ff6070":"rgba(160,175,195,0.8)";
      ctx.shadowColor = hovered.status==="ok"?"rgba(0,214,143,0.6)":hovered.status==="divergencia"?"rgba(255,71,87,0.6)":"rgba(140,160,185,0.3)";
      ctx.shadowBlur  = 10;
      ctx.fill();
      ctx.shadowBlur  = 0;
    }}
    showTip();
    rafId = requestAnimationFrame(render);
  }}

  function showTip(){{
    if(!hovered){{ tip.style.opacity="0"; return; }}
    if(hovered!==lastHovered){{
      lastHovered=hovered;
      const sc=hovered.status==="ok"?"#00d68f":hovered.status==="divergencia"?"#ff4757":"#93a4b8";
      const sl=hovered.status==="ok"?"OK":hovered.status==="divergencia"?"Divergência":"Pendente";
      tip.innerHTML=`<div style="color:#8fb7ff;font-weight:700;margin-bottom:3px;">${{hovered.cod}}</div>`+
        `<div style="font-size:12px;font-weight:700;margin-bottom:5px;color:#eef4fb;">${{hovered.nome}}</div>`+
        `<div style="color:#b7c3d4;">Categoria: ${{hovered.cat}}</div>`+
        `<div style="color:#b7c3d4;margin-bottom:6px;">Qtd: ${{hovered.qtd.toLocaleString("pt-BR")}}</div>`+
        `<div style="display:flex;align-items:center;gap:6px;font-weight:700;">`+
        `<span style="width:7px;height:7px;border-radius:50%;background:${{sc}};display:inline-block;"></span>`+
        `<span style="color:${{sc}};">${{sl}}</span></div>`;
    }}
    tip.style.opacity="1";
    const margin=10;
    let x=mouse.x+14, y=mouse.y+14;
    if(x+205>W-margin) x=mouse.x-215;
    if(y+125>H-margin) y=mouse.y-135;
    tip.style.left = Math.max(margin,x)+"px";
    tip.style.top  = Math.max(margin,y)+"px";
  }}

  canvas.addEventListener("mousemove", e=>{{
    const rc=canvas.getBoundingClientRect();
    mouse.x=e.clientX-rc.left; mouse.y=e.clientY-rc.top;
  }});
  canvas.addEventListener("mouseleave", ()=>{{ mouse.x=-9999; mouse.y=-9999; hovered=null; lastHovered=null; }});
  window.addEventListener("resize", resize);

  document.addEventListener("visibilitychange", ()=>{{
    if(document.hidden){{
      if(rafId!=null){{ cancelAnimationFrame(rafId); rafId=null; }}
    }} else {{
      if(rafId==null) rafId=requestAnimationFrame(render);
    }}
  }});

  resize();
  rafId = requestAnimationFrame(render);
}})();
</script>
"""
    st.components.v1.html(html, height=700, scrolling=False)
