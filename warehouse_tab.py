"""
warehouse_tab.py — Aba "Mapa do Armazém" para o dashboard CAMDA Estoque.

Layout físico do armazém:
  Setor A — 6 colunas: C1 | RUA | C2 C3 | RUA | C4 C5 | RUA | C6
  Setor B — 4 colunas: C1 | RUA | C2 | RUA | C3 | RUA | C4
  Cada coluna: 13 posições (P01–P13) × 4 níveis de altura (N1–N4)
  Endereçamento: {Setor}.{Coluna}.{Posição}.{Nível}  ex: A.C1.P07.N2

  Corredor de Carregamento separa visualmente os setores A e B.
"""

import json
import streamlit.components.v1 as components


def init_warehouse_table(conn):
    """Cria tabela warehouse_positions se não existir (idempotente)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warehouse_positions (
            addr       TEXT PRIMARY KEY,
            status     TEXT DEFAULT 'free',
            product    TEXT DEFAULT '',
            qty        TEXT DEFAULT '',
            lot        TEXT DEFAULT '',
            notes      TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.commit()


def _s(v, default="") -> str:
    """Converte valor do libSQL para str seguro para JSON."""
    if v is None:
        return default
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except Exception:
            return default
    return str(v)


def _load_positions(conn) -> dict:
    """Carrega todas as posições do armazém do banco local."""
    try:
        rows = conn.execute(
            "SELECT addr, status, product, qty, lot, notes FROM warehouse_positions"
        ).fetchall()
        result = {}
        for r in rows:
            addr = _s(r[0])
            if not addr:
                continue
            result[addr] = {
                "status":  _s(r[1]) or "free",
                "product": _s(r[2]),
                "qty":     _s(r[3]),
                "lot":     _s(r[4]),
                "notes":   _s(r[5]),
            }
        return result
    except Exception:
        return {}


def _load_products(conn) -> list:
    """Carrega lista de produtos do estoque e do mapa para autocomplete."""
    prods = set()
    try:
        for r in conn.execute(
            "SELECT DISTINCT produto FROM estoque_mestre WHERE produto IS NOT NULL ORDER BY produto"
        ).fetchall():
            v = _s(r[0]).strip()
            if v:
                prods.add(v)
    except Exception:
        pass
    try:
        for r in conn.execute(
            "SELECT DISTINCT product FROM warehouse_positions"
            " WHERE product IS NOT NULL AND product != '' ORDER BY product"
        ).fetchall():
            v = _s(r[0]).strip()
            if v:
                prods.add(v)
    except Exception:
        pass
    return sorted(prods)


def _safe_json(obj) -> str:
    """json.dumps com fallback str() e escape de </script>."""
    return (
        json.dumps(obj, ensure_ascii=False, default=str)
        .replace("</", "<\\/")   # previne fechar tag <script> no HTML
    )


def warehouse_tab(turso_url: str, turso_token: str, conn):
    """Renderiza a aba Mapa do Armazém via st.components.v1.html.

    Dados carregados pelo Python (sem fetch inicial no browser),
    evitando problemas de CORS/latência.
    """
    try:
        http_url = (turso_url or "").replace("libsql://", "https://").rstrip("/")
    except Exception:
        http_url = ""

    positions = _load_positions(conn)
    products  = _load_products(conn)

    # Build productPositions map  {name: [addr, ...]}
    prod_pos: dict = {}
    for addr, data in positions.items():
        p = data.get("product", "")
        if p:
            prod_pos.setdefault(p, []).append(addr)

    html = (
        _HTML_TEMPLATE
        .replace("__TURSO_URL__",        http_url)
        .replace("__TURSO_TOKEN__",      turso_token or "")
        .replace("'__POSITIONS_JSON__'", _safe_json(positions))
        .replace("'__PRODUCTS_JSON__'",  _safe_json(products))
        .replace("'__PROD_POS_JSON__'",  _safe_json(prod_pos))
    )
    components.html(html, height=880, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# HTML / CSS / JS template
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
<style>
:root {
  --bg:      #0a0f1a;
  --surf:    #111827;
  --surf2:   #1a2332;
  --border:  #1e2235;
  --text:    #e0e6ed;
  --muted:   #64748b;
  --green:   #00e5a0;
  --blue:    #0099ff;
  --amber:   #ffaa00;
  --red:     #ff4455;
  --free-bg: #1a3a2a; --free-bd: #00e5a0;
  --occ-bg:  #1a2540; --occ-bd:  #0099ff;
  --res-bg:  #3a2a10; --res-bd:  #ffaa00;
  --dmg-bg:  #3a1020; --dmg-bd:  #ff4455;
  --cw: 26px;
  --ch: 24px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Syne', sans-serif;
  overflow: hidden;
  height: 100%;
}
#app { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

/* ── Stats bar ─────────────────────────────────────────────────────────── */
#stats-bar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #0d1520, #111827);
  border-bottom: 1px solid var(--border);
  padding: 7px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
#stats-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px 10px;
  text-align: center;
  min-width: 58px;
}
.chip-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
  display: block;
}
.chip-lbl {
  font-size: 0.52rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 1px;
}
.chip-free .chip-val { color: var(--green); }
.chip-occ  .chip-val { color: var(--blue); }
.chip-res  .chip-val { color: var(--amber); }
.chip-dmg  .chip-val { color: var(--red); }

#occ-wrap { flex: 1; min-width: 120px; max-width: 180px; }
#occ-pct-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  color: var(--muted);
  margin-bottom: 3px;
}
#occ-track {
  height: 6px;
  background: rgba(255,255,255,0.07);
  border-radius: 3px;
  overflow: hidden;
}
#occ-fill {
  height: 100%;
  width: 0%;
  background: var(--green);
  border-radius: 3px;
  transition: width 0.4s ease, background 0.4s ease;
}

/* ── Filter bar ────────────────────────────────────────────────────────── */
#filter-bar {
  flex-shrink: 0;
  background: rgba(10,15,26,0.9);
  border-bottom: 1px solid var(--border);
  padding: 5px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
#filter-pills { display: flex; gap: 4px; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.09);
  border-radius: 20px;
  color: var(--muted);
  font-size: 0.7rem;
  font-family: 'Syne', sans-serif;
  font-weight: 600;
  padding: 3px 11px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.pill:hover { color: var(--text); background: rgba(255,255,255,0.1); }
.pill.active { background: rgba(0,229,160,0.12); border-color: var(--green); color: var(--green); }

#search-wrap { position: relative; flex: 1; min-width: 140px; max-width: 280px; }
#h-search {
  width: 100%;
  background: var(--surf2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.73rem;
  padding: 5px 10px;
  outline: none;
  transition: border-color 0.15s;
}
#h-search:focus { border-color: var(--green); }

/* ── Autocomplete dropdown ─────────────────────────────────────────────── */
.ac-drop {
  position: absolute;
  top: calc(100% + 3px);
  left: 0;
  right: 0;
  background: var(--surf2);
  border: 1px solid var(--border);
  border-radius: 8px;
  max-height: 210px;
  overflow-y: auto;
  z-index: 300;
  box-shadow: 0 10px 28px rgba(0,0,0,0.5);
}
.ac-drop.hidden { display: none; }
.ac-item {
  padding: 7px 11px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  transition: background 0.1s;
}
.ac-item:hover, .ac-item.kb-focus { background: rgba(0,229,160,0.1); }
.ac-item:last-child { border-bottom: none; }
.ac-name { font-size: 0.78rem; color: var(--text); }
.ac-pos  { font-size: 0.6rem; color: var(--muted); margin-top: 2px; font-family: 'JetBrains Mono', monospace; }

/* ── Map scroll container ──────────────────────────────────────────────── */
#map-outer { flex: 1; overflow: hidden; position: relative; }
#map-scroll {
  width: 100%;
  height: 100%;
  overflow-x: auto;
  overflow-y: auto;
  padding: 10px 14px 20px;
}
#map-inner { width: max-content; }

/* ── Loading indicator ─────────────────────────────────────────────────── */
#loading {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  padding: 36px 16px;
  font-size: 0.85rem;
}
.spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--green);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Sector ────────────────────────────────────────────────────────────── */
.sector-wrap { margin-bottom: 8px; }
.sector-label {
  font-family: 'Syne', sans-serif;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: var(--green);
  margin-bottom: 5px;
  padding-left: 2px;
}
.sector-racks { display: flex; align-items: stretch; gap: 0; }

/* ── Aisle ─────────────────────────────────────────────────────────────── */
.aisle {
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,153,255,0.03);
  border-left: 1px dashed var(--border);
  border-right: 1px dashed var(--border);
  margin: 0 2px;
  flex-shrink: 0;
}
.aisle span {
  writing-mode: vertical-lr;
  text-orientation: mixed;
  transform: rotate(180deg);
  font-size: 7px;
  color: var(--muted);
  letter-spacing: 3px;
  text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}

/* ── Column group ──────────────────────────────────────────────────────── */
.col-group { display: flex; gap: 3px; }

/* ── Rack column ───────────────────────────────────────────────────────── */
.rack-col { display: flex; flex-direction: column; }
.col-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: var(--muted);
  text-align: center;
  margin-bottom: 3px;
  white-space: nowrap;
}
.rack-grid { display: flex; flex-direction: column; gap: 2px; }
.level-row { display: flex; align-items: center; gap: 2px; }
.level-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.48rem;
  color: var(--muted);
  width: 18px;
  text-align: right;
  flex-shrink: 0;
  padding-right: 2px;
}

/* ── Cell ──────────────────────────────────────────────────────────────── */
.cell {
  width: var(--cw);
  height: var(--ch);
  background: var(--free-bg);
  border: 1px solid var(--free-bd);
  border-radius: 2px;
  cursor: pointer;
  transition: filter 0.12s ease, transform 0.1s ease;
  position: relative;
  flex-shrink: 0;
}
.cell:hover { filter: brightness(1.6); transform: scale(1.08); z-index: 20; }
.cell.occupied { background: var(--occ-bg); border-color: var(--occ-bd); }
.cell.reserved  { background: var(--res-bg); border-color: var(--res-bd); }
.cell.damaged   { background: var(--dmg-bg); border-color: var(--dmg-bd);
                  animation: pulse-dmg 2s ease-in-out infinite; }
.cell.dimmed    { opacity: 0.07 !important; pointer-events: none !important; }
.cell.dimmed-search { opacity: 0.06 !important; pointer-events: none !important; }

/* Data dot — top-left green 4px circle */
.cell.has-data::before {
  content: '';
  position: absolute;
  top: 2px; left: 2px;
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--green);
  pointer-events: none;
}

@keyframes pulse-dmg {
  0%, 100% { border-color: var(--dmg-bd); box-shadow: none; }
  50%       { border-color: #ff6677; box-shadow: 0 0 5px rgba(255,68,85,0.45); }
}

.cell.pulse-hl {
  animation: pulse-hl 0.75s ease-in-out 4;
}
@keyframes pulse-hl {
  0%, 100% { transform: scale(1); filter: brightness(1); }
  50%       { transform: scale(1.22); filter: brightness(1.9);
              box-shadow: 0 0 10px var(--green); }
}

/* ── Corredor de carregamento ──────────────────────────────────────────── */
#corredor {
  background: linear-gradient(90deg,
    rgba(0,153,255,0.04),
    rgba(0,153,255,0.14),
    rgba(0,153,255,0.04));
  border: 1px solid rgba(0,153,255,0.32);
  border-radius: 6px;
  text-align: center;
  padding: 11px 20px;
  margin: 10px 0;
  color: #0099ff;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 5px;
  text-transform: uppercase;
  font-family: 'Syne', sans-serif;
}

/* ── Modal ─────────────────────────────────────────────────────────────── */
#modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
}
#modal-overlay.hidden { display: none; }
#modal {
  background: linear-gradient(145deg, #111827, #1a2332);
  border: 1px solid var(--border);
  border-radius: 14px;
  width: 390px;
  max-width: 96vw;
  max-height: 92vh;
  overflow-y: auto;
  box-shadow: 0 20px 56px rgba(0,0,0,0.55);
}
#modal-hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 13px 16px;
  border-bottom: 1px solid var(--border);
}
#modal-addr-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--green);
  background: rgba(0,229,160,0.1);
  border: 1px solid rgba(0,229,160,0.28);
  border-radius: 6px;
  padding: 2px 9px;
}
#modal-close-btn {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 1rem;
  cursor: pointer;
  padding: 2px 7px;
  border-radius: 4px;
  transition: color 0.15s;
  line-height: 1;
}
#modal-close-btn:hover { color: var(--text); }

#modal-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.field-row { display: flex; flex-direction: column; gap: 4px; }
.field-lbl {
  font-size: 0.6rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 1.2px;
  font-weight: 600;
}
.field-row input,
.field-row textarea {
  background: var(--surf);
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  padding: 7px 10px;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  resize: vertical;
}
.field-row input:focus,
.field-row textarea:focus { border-color: var(--green); }

/* Status buttons */
#status-btns { display: flex; gap: 6px; flex-wrap: wrap; }
.st-btn {
  flex: 1;
  min-width: 68px;
  padding: 7px 8px;
  border-radius: 7px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.04);
  color: var(--muted);
  font-size: 0.7rem;
  font-family: 'Syne', sans-serif;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.14s;
  white-space: nowrap;
}
.st-btn:hover { color: var(--text); border-color: var(--muted); }
.st-btn.st-free.active  { background: rgba(0,229,160,0.14);  border-color: var(--green); color: var(--green); }
.st-btn.st-occ.active   { background: rgba(0,153,255,0.14);  border-color: var(--blue);  color: var(--blue);  }
.st-btn.st-res.active   { background: rgba(255,170,0,0.14);  border-color: var(--amber); color: var(--amber); }
.st-btn.st-dmg.active   { background: rgba(255,68,85,0.14);  border-color: var(--red);   color: var(--red);   }

/* Modal autocomplete */
.ac-wrap { position: relative; }

/* Modal footer */
#modal-ftr {
  display: flex;
  gap: 7px;
  padding: 11px 16px;
  border-top: 1px solid var(--border);
  align-items: center;
}
.btn-clear, .btn-cancel, .btn-save {
  padding: 7px 15px;
  border-radius: 8px;
  border: none;
  font-size: 0.75rem;
  font-family: 'Syne', sans-serif;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.14s, transform 0.1s;
}
.btn-clear:hover, .btn-cancel:hover, .btn-save:hover {
  opacity: 0.82;
  transform: scale(1.03);
}
.btn-clear  { background: rgba(255,68,85,0.12);  border: 1px solid var(--red);   color: var(--red);   margin-right: auto; }
.btn-cancel { background: rgba(255,255,255,0.06); border: 1px solid var(--border); color: var(--muted); }
.btn-save   { background: rgba(0,229,160,0.14);  border: 1px solid var(--green); color: var(--green); }
.btn-save:disabled, .btn-clear:disabled { opacity: 0.42; cursor: not-allowed; transform: none; }

/* ── Tooltip ───────────────────────────────────────────────────────────── */
#tip {
  position: fixed;
  background: var(--surf2);
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 6px 10px;
  font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text);
  pointer-events: none;
  z-index: 600;
  max-width: 210px;
  box-shadow: 0 6px 16px rgba(0,0,0,0.45);
  line-height: 1.55;
  display: none;
}
#tip strong { color: var(--green); }

/* ── Toast ─────────────────────────────────────────────────────────────── */
#toast {
  position: fixed;
  bottom: 14px;
  right: 14px;
  padding: 9px 16px;
  border-radius: 8px;
  font-size: 0.78rem;
  font-family: 'Syne', sans-serif;
  font-weight: 600;
  z-index: 700;
  display: none;
  animation: slide-in 0.2s ease;
}
.toast-ok  { background: rgba(0,229,160,0.13);  border: 1px solid var(--green); color: var(--green); }
.toast-err { background: rgba(255,68,85,0.13);  border: 1px solid var(--red);   color: var(--red);   }
@keyframes slide-in {
  from { transform: translateX(110%); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}

/* ── Scrollbar ─────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }
</style>
</head>
<body>
<div id="app">

  <!-- ── Stats bar ────────────────────────────────────────────────────── -->
  <div id="stats-bar">
    <div id="stats-chips">
      <div class="chip chip-total">
        <span class="chip-val" id="s-total">—</span>
        <span class="chip-lbl">Total</span>
      </div>
      <div class="chip chip-free">
        <span class="chip-val" id="s-free">—</span>
        <span class="chip-lbl">Livres</span>
      </div>
      <div class="chip chip-occ">
        <span class="chip-val" id="s-occ">—</span>
        <span class="chip-lbl">Ocupadas</span>
      </div>
      <div class="chip chip-res">
        <span class="chip-val" id="s-res">—</span>
        <span class="chip-lbl">Reservadas</span>
      </div>
      <div class="chip chip-dmg">
        <span class="chip-val" id="s-dmg">—</span>
        <span class="chip-lbl">Avarias</span>
      </div>
    </div>
    <div id="occ-wrap">
      <div id="occ-pct-lbl">Ocupação: 0%</div>
      <div id="occ-track"><div id="occ-fill"></div></div>
    </div>
  </div>

  <!-- ── Filter bar ───────────────────────────────────────────────────── -->
  <div id="filter-bar">
    <div id="filter-pills">
      <button class="pill active" data-f="all">Todos</button>
      <button class="pill" data-f="free">Livres</button>
      <button class="pill" data-f="occupied">Ocupados</button>
      <button class="pill" data-f="reserved">Reservados</button>
      <button class="pill" data-f="damaged">Avarias</button>
    </div>
    <div id="search-wrap">
      <input id="h-search" type="text" placeholder="&#128269; Buscar produto..." autocomplete="off">
      <div id="h-drop" class="ac-drop hidden"></div>
    </div>
  </div>

  <!-- ── Map ──────────────────────────────────────────────────────────── -->
  <div id="map-outer">
    <div id="map-scroll">
      <div id="map-inner">
        <div id="loading">
          <div class="spinner"></div>
          <span>Carregando mapa do armazém...</span>
        </div>
      </div>
    </div>
  </div>

</div><!-- #app -->

<!-- ── Modal overlay ────────────────────────────────────────────────────── -->
<div id="modal-overlay" class="hidden">
  <div id="modal">
    <div id="modal-hdr">
      <div id="modal-addr-badge">—</div>
      <button id="modal-close-btn">✕</button>
    </div>
    <div id="modal-body">
      <div class="field-row">
        <label class="field-lbl">Status</label>
        <div id="status-btns">
          <button class="st-btn st-free active" data-s="free">&#x1F7E2; Livre</button>
          <button class="st-btn st-occ"  data-s="occupied">&#x1F535; Ocupado</button>
          <button class="st-btn st-res"  data-s="reserved">&#x1F7E1; Reservado</button>
          <button class="st-btn st-dmg"  data-s="damaged">&#x1F534; Avaria</button>
        </div>
      </div>
      <div class="field-row">
        <label class="field-lbl">Produto</label>
        <div class="ac-wrap">
          <input id="m-product" type="text" placeholder="Nome do produto..." autocomplete="off">
          <div id="m-drop" class="ac-drop hidden"></div>
        </div>
      </div>
      <div class="field-row">
        <label class="field-lbl">Quantidade</label>
        <input id="m-qty" type="text" placeholder="ex: 48 cx · 3 paletes">
      </div>
      <div class="field-row">
        <label class="field-lbl">Lote / Validade</label>
        <input id="m-lot" type="text" placeholder="ex: LOT-2024-001 / 12/2025">
      </div>
      <div class="field-row">
        <label class="field-lbl">Observações</label>
        <textarea id="m-notes" rows="3" placeholder="Notas adicionais..."></textarea>
      </div>
    </div>
    <div id="modal-ftr">
      <button class="btn-clear" id="btn-clear">&#128465; Limpar</button>
      <button class="btn-cancel" id="btn-cancel">Cancelar</button>
      <button class="btn-save"  id="btn-save">&#128190; Salvar</button>
    </div>
  </div>
</div>

<!-- ── Tooltip ──────────────────────────────────────────────────────────── -->
<div id="tip"></div>

<!-- ── Toast ────────────────────────────────────────────────────────────── -->
<div id="toast"></div>

<script>
/* ────────────────────────────────────────────────────────────────────────
   CONFIG (injected by Python)
──────────────────────────────────────────────────────────────────────── */
const TURSO_URL   = '__TURSO_URL__';
const TURSO_TOKEN = '__TURSO_TOKEN__';

/* ────────────────────────────────────────────────────────────────────────
   WAREHOUSE LAYOUT DEFINITION
──────────────────────────────────────────────────────────────────────── */
const POSITIONS = Array.from({length: 13}, (_, i) => 'P' + String(i + 1).padStart(2, '0'));
const LEVELS    = ['N4', 'N3', 'N2', 'N1'];  // visual: top → bottom

// Each entry in groups = array of column names in that group (between aisles)
const LAYOUT = {
  A: { groups: [['C1'], ['C2', 'C3'], ['C4', 'C5'], ['C6']] },
  B: { groups: [['C1'], ['C2'], ['C3'], ['C4']] }
};

// Pre-compute all valid addresses for stats
const ALL_ADDRS = [];
for (const sector of ['A', 'B']) {
  const cols = sector === 'A'
    ? ['C1','C2','C3','C4','C5','C6']
    : ['C1','C2','C3','C4'];
  for (const col of cols)
    for (const pos of POSITIONS)
      for (const lv of ['N1','N2','N3','N4'])
        ALL_ADDRS.push(`${sector}.${col}.${pos}.${lv}`);
}

/* ────────────────────────────────────────────────────────────────────────
   STATE
──────────────────────────────────────────────────────────────────────── */
let posData  = {};          // addr  → {status, product, qty, lot, notes}
let prodList = [];          // sorted string[]
let prodPositions = {};     // productName → addr[]
let currentFilter = 'all';
let currentSearch = '';
let modalAddr   = null;
let modalStatus = 'free';
let fuseInst    = null;
let acKbIdx     = -1;       // keyboard index for active dropdown
let activeAcId  = null;     // 'h-drop' | 'm-drop'

/* ────────────────────────────────────────────────────────────────────────
   TURSO HTTP API
──────────────────────────────────────────────────────────────────────── */
async function tursoExec(sql, args) {
  const mappedArgs = (args || []).map(v =>
    (v === null || v === undefined) ? {type: 'null'} : {type: 'text', value: String(v)}
  );
  const body = {
    requests: [
      { type: 'execute', stmt: { sql, args: mappedArgs } },
      { type: 'close' }
    ]
  };
  const resp = await fetch(TURSO_URL + '/v2/pipeline', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + TURSO_TOKEN,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  if (!resp.ok) throw new Error('HTTP ' + resp.status);
  const data = await resp.json();
  const res = data.results[0];
  if (res.type === 'error') throw new Error(res.error.message);
  return res.response.result;
}

function parseRows(result) {
  if (!result || !result.cols) return [];
  const cols = result.cols.map(c => c.name);
  return result.rows.map(row =>
    Object.fromEntries(cols.map((c, i) => [c, row[i]]))
  );
}

/* ────────────────────────────────────────────────────────────────────────
   PRELOADED DATA  (injected by Python — no fetch needed on load)
──────────────────────────────────────────────────────────────────────── */
const _PRE_POSITIONS = '__POSITIONS_JSON__';  // {addr: {status,product,qty,lot,notes}}
const _PRE_PRODUCTS  = '__PRODUCTS_JSON__';   // string[]
const _PRE_PROD_POS  = '__PROD_POS_JSON__';   // {name: addr[]}

/* ────────────────────────────────────────────────────────────────────────
   INIT  (synchronous — data already here)
──────────────────────────────────────────────────────────────────────── */
function init() {
  try {
    // Use Python-preloaded data — instant, no CORS issues
    posData       = _PRE_POSITIONS;
    prodList      = _PRE_PRODUCTS;
    prodPositions = _PRE_PROD_POS;

    fuseInst = new Fuse(prodList.map(p => ({name: p})), {
      keys: ['name'], threshold: 0.42, includeScore: true
    });

    renderMap();
    updateStats();

  } catch (err) {
    document.getElementById('loading').innerHTML =
      '<span style="color:var(--red)">&#9888; Erro ao inicializar: ' + err.message + '</span>';
    console.error('Warehouse init error:', err);
  }
}

/* ────────────────────────────────────────────────────────────────────────
   RENDER MAP
──────────────────────────────────────────────────────────────────────── */
function renderMap() {
  const inner = document.getElementById('map-inner');
  let html = '';

  html += buildSector('A', LAYOUT.A.groups);
  html += '<div id="corredor">&#8592; CORREDOR DE CARREGAMENTO &#8594;</div>';
  html += buildSector('B', LAYOUT.B.groups);

  inner.innerHTML = html;

  // Attach events
  inner.querySelectorAll('.cell').forEach(cell => {
    cell.addEventListener('click', () => openModal(cell.dataset.addr));
    cell.addEventListener('mouseenter', e => showTip(e, cell.dataset.addr));
    cell.addEventListener('mouseleave', hideTip);
  });

  applyAllCells();
}

function buildSector(sector, groups) {
  let h = '<div class="sector-wrap">';
  h += '<div class="sector-label">SETOR ' + sector + '</div>';
  h += '<div class="sector-racks">';
  for (let gi = 0; gi < groups.length; gi++) {
    if (gi > 0) h += '<div class="aisle"><span>RUA</span></div>';
    h += '<div class="col-group">';
    for (const col of groups[gi]) h += buildColumn(sector, col);
    h += '</div>';
  }
  h += '</div></div>';
  return h;
}

function buildColumn(sector, col) {
  let h = '<div class="rack-col">';
  h += '<div class="col-label">' + sector + '.' + col + '</div>';
  h += '<div class="rack-grid">';
  for (const lv of LEVELS) {
    h += '<div class="level-row">';
    h += '<div class="level-lbl">' + lv + '</div>';
    for (const pos of POSITIONS) {
      const addr = sector + '.' + col + '.' + pos + '.' + lv;
      h += '<div class="cell" data-addr="' + addr + '"></div>';
    }
    h += '</div>';
  }
  h += '</div></div>';
  return h;
}

/* ────────────────────────────────────────────────────────────────────────
   APPLY CELL VISUAL STATE
──────────────────────────────────────────────────────────────────────── */
function applyAllCells() {
  document.querySelectorAll('.cell').forEach(cell => applyCellState(cell));
  applyFilterAndSearch();
}

function applyCellState(cell) {
  const addr = cell.dataset.addr;
  const d = posData[addr];
  cell.className = 'cell';
  if (d) {
    if      (d.status === 'occupied') cell.classList.add('occupied');
    else if (d.status === 'reserved') cell.classList.add('reserved');
    else if (d.status === 'damaged')  cell.classList.add('damaged');
    if (d.product || d.notes) cell.classList.add('has-data');
  }
}

/* ────────────────────────────────────────────────────────────────────────
   STATS BAR
──────────────────────────────────────────────────────────────────────── */
function updateStats() {
  let free = 0, occupied = 0, reserved = 0, damaged = 0;
  const total = ALL_ADDRS.length;
  for (const addr of ALL_ADDRS) {
    const d = posData[addr];
    const st = d ? d.status : 'free';
    if      (st === 'occupied') occupied++;
    else if (st === 'reserved') reserved++;
    else if (st === 'damaged')  damaged++;
    else                        free++;
  }
  document.getElementById('s-total').textContent = total;
  document.getElementById('s-free').textContent  = free;
  document.getElementById('s-occ').textContent   = occupied;
  document.getElementById('s-res').textContent   = reserved;
  document.getElementById('s-dmg').textContent   = damaged;

  const pct = Math.round((occupied + reserved + damaged) / total * 100);
  document.getElementById('occ-pct-lbl').textContent = 'Ocupação: ' + pct + '%';
  const fill = document.getElementById('occ-fill');
  fill.style.width      = pct + '%';
  fill.style.background = pct <= 50 ? '#00e5a0' : pct <= 80 ? '#ffaa00' : '#ff4455';
}

/* ────────────────────────────────────────────────────────────────────────
   FILTER + SEARCH
──────────────────────────────────────────────────────────────────────── */
function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.pill').forEach(p => {
    p.classList.toggle('active', p.dataset.f === f);
  });
  applyFilterAndSearch();
}

function applyFilterAndSearch() {
  const ql = currentSearch.toLowerCase();
  document.querySelectorAll('.cell').forEach(cell => {
    const addr = cell.dataset.addr;
    const d = posData[addr];
    const st = d ? (d.status || 'free') : 'free';
    const prod = d ? (d.product || '').toLowerCase() : '';

    let visible = true;
    if (currentFilter !== 'all') visible = (st === currentFilter);

    // Remove previous dim classes
    cell.classList.remove('dimmed', 'dimmed-search');

    if (!visible) {
      cell.classList.add('dimmed');
    } else if (ql && !prod.includes(ql)) {
      cell.classList.add('dimmed-search');
    }
  });
}

/* ────────────────────────────────────────────────────────────────────────
   HEADER SEARCH AUTOCOMPLETE
──────────────────────────────────────────────────────────────────────── */
function updateHeaderAC(q) {
  const dd = document.getElementById('h-drop');
  if (!q || !fuseInst) { dd.classList.add('hidden'); return; }
  const results = fuseInst.search(q).slice(0, 8);
  if (!results.length) { dd.classList.add('hidden'); return; }
  renderACDrop(dd, results, name => {
    document.getElementById('h-search').value = name;
    dd.classList.add('hidden');
    currentSearch = name;
    applyFilterAndSearch();
    pulseCells(prodPositions[name] || []);
  });
  acKbIdx = -1;
  activeAcId = 'h-drop';
}

/* ────────────────────────────────────────────────────────────────────────
   MODAL PRODUCT AUTOCOMPLETE
──────────────────────────────────────────────────────────────────────── */
function updateModalAC(q) {
  const dd = document.getElementById('m-drop');
  if (!q || !fuseInst) { dd.classList.add('hidden'); return; }
  const results = fuseInst.search(q).slice(0, 8);
  if (!results.length) { dd.classList.add('hidden'); return; }
  renderACDrop(dd, results, name => {
    document.getElementById('m-product').value = name;
    dd.classList.add('hidden');
    pulseCells(prodPositions[name] || []);
  });
  acKbIdx = -1;
  activeAcId = 'm-drop';
}

function renderACDrop(dd, results, onSelect) {
  dd.innerHTML = results.map((r, idx) => {
    const name  = r.item.name;
    const poses = prodPositions[name] || [];
    const posStr = poses.length
      ? poses.slice(0, 3).join(', ') + (poses.length > 3 ? ' +' + (poses.length - 3) : '')
      : '';
    return '<div class="ac-item" data-idx="' + idx + '" data-name="' +
      name.replace(/"/g, '&quot;') + '">' +
      '<div class="ac-name">' + esc(name) + '</div>' +
      (posStr ? '<div class="ac-pos">' + esc(posStr) + '</div>' : '') +
      '</div>';
  }).join('');

  dd.querySelectorAll('.ac-item').forEach(item => {
    item.addEventListener('mousedown', e => {
      e.preventDefault();
      onSelect(item.dataset.name);
    });
  });
  dd.classList.remove('hidden');
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ── Keyboard navigation for autocomplete ── */
function acKeyNav(e, dropId) {
  const dd = document.getElementById(dropId);
  if (dd.classList.contains('hidden')) return;
  const items = dd.querySelectorAll('.ac-item');
  if (!items.length) return;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    acKbIdx = Math.min(acKbIdx + 1, items.length - 1);
    items.forEach((it, i) => it.classList.toggle('kb-focus', i === acKbIdx));
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    acKbIdx = Math.max(acKbIdx - 1, 0);
    items.forEach((it, i) => it.classList.toggle('kb-focus', i === acKbIdx));
  } else if (e.key === 'Enter' && acKbIdx >= 0) {
    e.preventDefault();
    items[acKbIdx].dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
  } else if (e.key === 'Escape') {
    dd.classList.add('hidden');
    acKbIdx = -1;
  }
}

/* ────────────────────────────────────────────────────────────────────────
   CELL PULSE HIGHLIGHT
──────────────────────────────────────────────────────────────────────── */
function pulseCells(addrs) {
  addrs.forEach(addr => {
    const cell = document.querySelector('.cell[data-addr="' + CSS.escape(addr) + '"]');
    if (!cell) return;
    cell.classList.remove('pulse-hl');
    void cell.offsetWidth; // reflow
    cell.classList.add('pulse-hl');
    setTimeout(() => cell.classList.remove('pulse-hl'), 3200);
  });
}

/* ────────────────────────────────────────────────────────────────────────
   MODAL
──────────────────────────────────────────────────────────────────────── */
function openModal(addr) {
  modalAddr = addr;
  const d = posData[addr] || {};
  document.getElementById('modal-addr-badge').textContent = addr;
  modalStatus = d.status || 'free';
  refreshStatusBtns();
  document.getElementById('m-product').value = d.product || '';
  document.getElementById('m-qty').value     = d.qty     || '';
  document.getElementById('m-lot').value     = d.lot     || '';
  document.getElementById('m-notes').value   = d.notes   || '';
  document.getElementById('m-drop').classList.add('hidden');
  document.getElementById('modal-overlay').classList.remove('hidden');
  setTimeout(() => document.getElementById('m-product').focus(), 60);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('m-drop').classList.add('hidden');
  modalAddr = null;
  acKbIdx = -1;
}

function selectStatus(s) {
  modalStatus = s;
  refreshStatusBtns();
}

function refreshStatusBtns() {
  document.querySelectorAll('.st-btn').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.s === modalStatus)
  );
}

/* ────────────────────────────────────────────────────────────────────────
   SAVE / CLEAR
──────────────────────────────────────────────────────────────────────── */
async function savePosition() {
  if (!modalAddr) return;
  const product = document.getElementById('m-product').value.trim();
  const qty     = document.getElementById('m-qty').value.trim();
  const lot     = document.getElementById('m-lot').value.trim();
  const notes   = document.getElementById('m-notes').value.trim();
  const now     = new Date().toISOString();

  setBtnsDisabled(true);
  try {
    await tursoExec(
      'INSERT INTO warehouse_positions (addr,status,product,qty,lot,notes,updated_at)' +
      ' VALUES(?,?,?,?,?,?,?)' +
      ' ON CONFLICT(addr) DO UPDATE SET' +
      ' status=excluded.status,product=excluded.product,' +
      ' qty=excluded.qty,lot=excluded.lot,' +
      ' notes=excluded.notes,updated_at=excluded.updated_at',
      [modalAddr, modalStatus, product, qty, lot, notes, now]
    );

    // Update local state
    const old = posData[modalAddr] || {};
    posData[modalAddr] = { status: modalStatus, product, qty, lot, notes };

    // Update prodPositions index
    if (old.product && old.product !== product) {
      prodPositions[old.product] = (prodPositions[old.product] || [])
        .filter(a => a !== modalAddr);
    }
    if (product) {
      if (!prodPositions[product]) prodPositions[product] = [];
      if (!prodPositions[product].includes(modalAddr))
        prodPositions[product].push(modalAddr);
      if (!prodList.includes(product)) {
        prodList.push(product);
        prodList.sort();
        fuseInst = new Fuse(prodList.map(p => ({name: p})), {
          keys: ['name'], threshold: 0.42, includeScore: true
        });
      }
    }

    // Refresh cell
    const cell = document.querySelector('.cell[data-addr="' + CSS.escape(modalAddr) + '"]');
    if (cell) applyCellState(cell);

    updateStats();
    applyFilterAndSearch();
    closeModal();
    showToast('&#10003; Posição salva com sucesso!', 'ok');
  } catch (err) {
    showToast('&#10007; Erro ao salvar: ' + err.message, 'err');
    console.error(err);
  } finally {
    setBtnsDisabled(false);
  }
}

async function clearPosition() {
  if (!modalAddr) return;
  setBtnsDisabled(true);
  try {
    await tursoExec('DELETE FROM warehouse_positions WHERE addr=?', [modalAddr]);

    const old = posData[modalAddr] || {};
    delete posData[modalAddr];

    if (old.product) {
      prodPositions[old.product] = (prodPositions[old.product] || [])
        .filter(a => a !== modalAddr);
    }

    const cell = document.querySelector('.cell[data-addr="' + CSS.escape(modalAddr) + '"]');
    if (cell) {
      cell.className = 'cell';
    }

    updateStats();
    applyFilterAndSearch();
    closeModal();
    showToast('&#128465; Posição limpa com sucesso!', 'ok');
  } catch (err) {
    showToast('&#10007; Erro ao limpar: ' + err.message, 'err');
    console.error(err);
  } finally {
    setBtnsDisabled(false);
  }
}

function setBtnsDisabled(v) {
  document.getElementById('btn-save').disabled  = v;
  document.getElementById('btn-clear').disabled = v;
}

/* ────────────────────────────────────────────────────────────────────────
   TOOLTIP
──────────────────────────────────────────────────────────────────────── */
const tip = document.getElementById('tip');

function showTip(e, addr) {
  const d = posData[addr];
  if (!d || !d.product) return;
  tip.innerHTML =
    '<strong>' + esc(addr) + '</strong><br>' + esc(d.product) +
    (d.qty ? '<br><span style="color:var(--muted)">' + esc(d.qty) + '</span>' : '');
  tip.style.display = 'block';
  moveTip(e);
}

function moveTip(e) {
  tip.style.left = (e.clientX + 12) + 'px';
  tip.style.top  = (e.clientY + 12) + 'px';
}

function hideTip() { tip.style.display = 'none'; }

document.addEventListener('mousemove', e => {
  if (tip.style.display !== 'none') moveTip(e);
});

/* ────────────────────────────────────────────────────────────────────────
   TOAST
──────────────────────────────────────────────────────────────────────── */
let toastTimer = null;
function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.innerHTML = msg;
  t.className = type === 'err' ? 'toast-err' : 'toast-ok';
  t.style.display = 'block';
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.style.display = 'none'; }, 3200);
}

/* ────────────────────────────────────────────────────────────────────────
   EVENT WIRING
──────────────────────────────────────────────────────────────────────── */

// Filter pills
document.querySelectorAll('.pill').forEach(pill =>
  pill.addEventListener('click', () => setFilter(pill.dataset.f))
);

// Header search
document.getElementById('h-search').addEventListener('input', function () {
  currentSearch = this.value.trim();
  updateHeaderAC(currentSearch);
  applyFilterAndSearch();
});
document.getElementById('h-search').addEventListener('keydown', e =>
  acKeyNav(e, 'h-drop')
);

// Modal product autocomplete
document.getElementById('m-product').addEventListener('input', function () {
  updateModalAC(this.value.trim());
});
document.getElementById('m-product').addEventListener('keydown', e =>
  acKeyNav(e, 'm-drop')
);

// Status buttons
document.querySelectorAll('.st-btn').forEach(btn =>
  btn.addEventListener('click', () => selectStatus(btn.dataset.s))
);

// Save / Clear / Cancel
document.getElementById('btn-save').addEventListener('click', savePosition);
document.getElementById('btn-clear').addEventListener('click', clearPosition);
document.getElementById('btn-cancel').addEventListener('click', closeModal);
document.getElementById('modal-close-btn').addEventListener('click', closeModal);

// Overlay click → close
document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});

// Global keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    // Close active dropdown first, then modal
    const hd = document.getElementById('h-drop');
    const md = document.getElementById('m-drop');
    if (!hd.classList.contains('hidden'))       { hd.classList.add('hidden'); return; }
    if (!md.classList.contains('hidden'))       { md.classList.add('hidden'); return; }
    if (document.getElementById('modal-overlay').style.display !== 'none'
        && !document.getElementById('modal-overlay').classList.contains('hidden')) {
      closeModal();
    }
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && modalAddr) savePosition();
});

// Close dropdowns on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('#search-wrap'))
    document.getElementById('h-drop').classList.add('hidden');
  if (!e.target.closest('.ac-wrap'))
    document.getElementById('m-drop').classList.add('hidden');
});

/* ────────────────────────────────────────────────────────────────────────
   BOOT
──────────────────────────────────────────────────────────────────────── */
init();
</script>
</body>
</html>"""
