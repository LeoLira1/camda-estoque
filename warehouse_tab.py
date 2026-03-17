"""
warehouse_tab.py — Aba "Mapa do Armazém" para o dashboard CAMDA Estoque.

Layout físico do armazém:
  Setor A — 6 colunas: C1 | RUA | C2 C3 | RUA | C4 C5 | RUA | C6
  Setor B — 4 colunas: C1 | RUA | C2 | RUA | C3 | RUA | C4
  Cada coluna: 13 posições (P01-P13) × 4 níveis de altura (N1-N4)
  Endereçamento: {Setor}.{Coluna}.{Posição}.{Nível}  ex: A.C1.P07.N2

  Corredor de Carregamento separa visualmente os setores A e B.
  Orientação das células: posições empilhadas verticalmente (P13 topo,
  P1 base), níveis N1-N4 lado a lado em cada linha de posição.
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
        .replace("</", "<\\/")
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
    components.html(html, height=900, scrolling=True)


# -----------------------------------------------------------------------------
# HTML / CSS / JS template
# Layout: posições empilhadas VERTICALMENTE (P13 topo, P1 base via
# column-reverse), 4 níveis LADO A LADO em cada linha de posição.
# Baseado no design aprovado pelo usuário.
# -----------------------------------------------------------------------------

_HTML_TEMPLATE = (
"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
<style>
:root{
  --bg:#0d0f14;--surf:#141720;--surf2:#1c2030;--border:#2a2f45;
  --accent:#00e5a0;--blue:#0099ff;--warn:#ffaa00;--danger:#ff4455;
  --text:#e8eaf0;--text2:#7a80a0;
  --free:#1a3a2a;--free-bd:#00e5a0;
  --occ:#1a2540; --occ-bd:#0099ff;
  --res:#3a2a10; --res-bd:#ffaa00;
  --dmg:#3a1020; --dmg-bd:#ff4455;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;min-height:100%;}
body{overflow-x:auto;}

header{display:flex;align-items:center;justify-content:space-between;padding:12px 20px;
  border-bottom:1px solid var(--border);background:var(--surf);
  position:sticky;top:0;z-index:100;flex-wrap:wrap;gap:8px;}
.logo{font-family:'Syne',sans-serif;font-weight:800;font-size:16px;
  letter-spacing:.08em;color:var(--accent);}
.logo span{color:var(--text2);font-weight:400;margin-left:8px;font-size:11px;}
.stats{display:flex;gap:16px;font-size:10px;color:var(--text2);flex-wrap:wrap;}
.stat-item strong{display:block;font-size:13px;}

.legend{display:flex;gap:12px;padding:8px 20px;background:var(--surf);
  border-bottom:1px solid var(--border);flex-wrap:wrap;align-items:center;}
.leg-item{display:flex;align-items:center;gap:5px;font-size:10px;color:var(--text2);}
.leg-dot{width:10px;height:10px;border-radius:2px;border:1px solid;flex-shrink:0;}
.hint{margin-left:auto;font-size:10px;color:var(--text2);}

main{padding:16px 20px;}

.filters{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;align-items:center;}
.filter-btn{padding:4px 12px;border-radius:20px;border:1px solid var(--border);
  background:transparent;color:var(--text2);
  font-family:'JetBrains Mono',monospace;font-size:10px;cursor:pointer;transition:all .15s;}
.filter-btn:hover,.filter-btn.active{background:var(--surf2);color:var(--text);border-color:var(--accent);}
.search-wrap{margin-left:auto;position:relative;}
.search-box{background:var(--surf);border:1px solid var(--border);border-radius:20px;
  padding:5px 14px;color:var(--text);font-family:'JetBrains Mono',monospace;
  font-size:10px;outline:none;width:180px;transition:border-color .15s;}
.search-box:focus{border-color:var(--accent);}
.search-box::placeholder{color:var(--text2);}

.ac-drop{position:absolute;top:calc(100% + 4px);right:0;left:0;background:var(--surf2);
  border:1px solid var(--border);border-radius:8px;max-height:200px;overflow-y:auto;
  z-index:200;box-shadow:0 10px 28px rgba(0,0,0,.5);display:none;}
.ac-drop.open{display:block;}
.ac-item{padding:7px 12px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,.04);
  font-size:10px;transition:background .1s;}
.ac-item:hover,.ac-item.kbf{background:rgba(0,229,160,.1);}
.ac-item:last-child{border-bottom:none;}
.ac-name{color:var(--text);}
.ac-pos{color:var(--text2);font-size:9px;margin-top:2px;}

.warehouse{display:flex;flex-direction:column;gap:8px;width:fit-content;}

.sector-label{font-family:'Syne',sans-serif;font-size:10px;font-weight:700;
  letter-spacing:.18em;color:var(--accent);text-transform:uppercase;margin-bottom:6px;
  border-left:2px solid var(--accent);padding-left:8px;}

.sector-row{display:flex;flex-direction:row;gap:0;align-items:flex-start;}

.aisle{display:flex;align-items:center;justify-content:center;
  width:26px;min-width:26px;background:transparent;
  border:1px dashed #2a2f45;border-radius:3px;font-size:6px;color:#2a3050;
  letter-spacing:.08em;writing-mode:vertical-rl;text-orientation:mixed;
  user-select:none;align-self:stretch;margin:0 3px;}

.rack-block{display:flex;flex-direction:column;gap:0;align-items:center;margin:0 2px;}
.rack-block-label{font-size:9px;color:var(--text2);letter-spacing:.06em;
  padding-bottom:3px;text-align:center;}

/* column-reverse: append P1..P13, P13 appears at visual top */
.rack-col{display:flex;flex-direction:column-reverse;gap:2px;}

/* Each position row = 4 level-cells side by side */
.pos-row{display:flex;flex-direction:row;gap:2px;}

.cell{width:28px;height:26px;border-radius:3px;border:1px solid var(--free-bd);
  background:var(--free);cursor:pointer;position:relative;
  transition:all .1s ease;flex-shrink:0;overflow:hidden;}
.cell:hover{filter:brightness(1.6);transform:scale(1.08);z-index:10;}
.cell.occupied{background:var(--occ);border-color:var(--occ-bd);}
.cell.reserved{background:var(--res);border-color:var(--res-bd);}
.cell.damaged {background:var(--dmg);border-color:var(--dmg-bd);
  animation:blink 2s ease-in-out infinite;}
.cell.dimmed  {opacity:.07!important;pointer-events:none!important;}
.cell.hl      {animation:pulse-hl .7s ease-in-out 4;}

@keyframes blink{
  0%,100%{border-color:var(--dmg-bd);}
  50%{border-color:#ff6677;box-shadow:0 0 5px rgba(255,68,85,.45);}
}
@keyframes pulse-hl{
  0%,100%{transform:scale(1);}
  50%{transform:scale(1.22);box-shadow:0 0 9px var(--accent);filter:brightness(1.9);}
}

.cell-lbl{font-size:5.5px;color:rgba(255,255,255,.18);position:absolute;
  bottom:1px;right:2px;pointer-events:none;line-height:1;}
.cell-dot{position:absolute;top:2px;left:2px;width:4px;height:4px;
  border-radius:50%;background:var(--accent);pointer-events:none;}

.corridor{display:flex;align-items:center;justify-content:center;height:38px;
  background:#0a1520;border:1px solid var(--border);
  border-left:3px solid var(--blue);border-radius:4px;margin:10px 0;
  font-size:9px;color:var(--text2);letter-spacing:.15em;
  text-transform:uppercase;padding:0 20px;gap:10px;}
.corridor::before,.corridor::after{content:'\\25B6';color:var(--blue);opacity:.4;font-size:7px;}

#tip{position:fixed;background:var(--surf2);border:1px solid var(--border);
  border-radius:6px;padding:6px 10px;font-size:10px;color:var(--text);
  pointer-events:none;z-index:600;max-width:200px;
  box-shadow:0 6px 16px rgba(0,0,0,.45);display:none;line-height:1.55;}
#tip strong{color:var(--accent);}

.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);
  z-index:300;backdrop-filter:blur(4px);align-items:center;justify-content:center;}
.overlay.active{display:flex;}
.modal{background:var(--surf);border:1px solid var(--border);border-radius:12px;
  width:400px;max-width:95vw;max-height:92vh;overflow-y:auto;
  box-shadow:0 32px 80px rgba(0,0,0,.6);animation:slideUp .18s ease;}
@keyframes slideUp{from{transform:translateY(14px);opacity:0;}to{transform:translateY(0);opacity:1;}}
.modal-hdr{padding:16px 20px 12px;border-bottom:1px solid var(--border);
  display:flex;align-items:flex-start;justify-content:space-between;}
.modal-addr{font-family:'Syne',sans-serif;font-size:17px;font-weight:800;
  color:var(--accent);letter-spacing:.03em;word-break:break-all;}
.modal-sub{font-size:9px;color:var(--text2);margin-top:3px;}
.modal-x{background:none;border:none;color:var(--text2);font-size:17px;
  cursor:pointer;padding:0 4px;transition:color .12s;}
.modal-x:hover{color:var(--text);}
.modal-body{padding:16px 20px;display:flex;flex-direction:column;gap:12px;}
.st-group{display:flex;gap:5px;flex-wrap:wrap;}
.st-btn{flex:1;min-width:72px;padding:7px 4px;border-radius:6px;
  border:1px solid var(--border);background:transparent;color:var(--text2);
  font-family:'JetBrains Mono',monospace;font-size:10px;
  cursor:pointer;transition:all .12s;text-align:center;white-space:nowrap;}
.st-btn:hover{background:var(--surf2);}
.st-btn.a-free{background:var(--free);border-color:var(--free-bd);color:var(--accent);}
.st-btn.a-occ {background:var(--occ); border-color:var(--occ-bd); color:var(--blue);}
.st-btn.a-res {background:var(--res); border-color:var(--res-bd); color:var(--warn);}
.st-btn.a-dmg {background:var(--dmg); border-color:var(--dmg-bd); color:var(--danger);}
.field{display:flex;flex-direction:column;gap:5px;}
.field label{font-size:9px;color:var(--text2);letter-spacing:.1em;text-transform:uppercase;}
.field input,.field textarea{background:var(--surf2);border:1px solid var(--border);
  border-radius:6px;color:var(--text);font-family:'JetBrains Mono',monospace;
  font-size:13px;padding:9px 11px;width:100%;outline:none;resize:none;
  transition:border-color .12s;}
.field input:focus,.field textarea:focus{border-color:var(--accent);}
.field textarea{height:62px;}
.ac-wrap{position:relative;}
.modal-ftr{padding:12px 20px;border-top:1px solid var(--border);
  display:flex;gap:7px;justify-content:flex-end;}
.btn{padding:8px 16px;border-radius:6px;border:none;
  font-family:'JetBrains Mono',monospace;font-size:10px;
  cursor:pointer;transition:all .12s;font-weight:700;}
.btn-sec{background:var(--surf2);color:var(--text2);border:1px solid var(--border);}
.btn-sec:hover{color:var(--text);}
.btn-ok{background:var(--accent);color:#000;}
.btn-ok:hover{filter:brightness(1.1);}
.btn-del{background:var(--dmg);color:var(--danger);
  border:1px solid var(--dmg-bd);margin-right:auto;}
.btn-del:hover{filter:brightness(1.2);}
.btn:disabled{opacity:.45;cursor:not-allowed;}

#toast{position:fixed;bottom:18px;right:18px;background:var(--surf);
  border-radius:8px;padding:10px 16px;font-size:11px;z-index:400;
  transform:translateY(60px);opacity:0;transition:all .22s ease;pointer-events:none;}
.t-ok {border:1px solid var(--accent);color:var(--accent);}
.t-err{border:1px solid var(--danger);color:var(--danger);}

::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
</style>
</head>
<body>

<header>
  <div class="logo">CAMDA <span>/ Mapa do Arm&eacute;m</span></div>
  <div class="stats">
    <div class="stat-item"><strong id="s-total">520</strong>posi&ccedil;&otilde;es</div>
    <div class="stat-item"><strong id="s-free" style="color:var(--accent)">520</strong>livres</div>
    <div class="stat-item"><strong id="s-occ"  style="color:var(--blue)">0</strong>ocupadas</div>
    <div class="stat-item"><strong id="s-res"  style="color:var(--warn)">0</strong>reservadas</div>
    <div class="stat-item"><strong id="s-dmg"  style="color:var(--danger)">0</strong>avarias</div>
  </div>
</header>

<div class="legend">
  <div class="leg-item">
    <div class="leg-dot" style="background:var(--free);border-color:var(--free-bd)"></div>Livre
  </div>
  <div class="leg-item">
    <div class="leg-dot" style="background:var(--occ);border-color:var(--occ-bd)"></div>Ocupado
  </div>
  <div class="leg-item">
    <div class="leg-dot" style="background:var(--res);border-color:var(--res-bd)"></div>Reservado
  </div>
  <div class="leg-item">
    <div class="leg-dot" style="background:var(--dmg);border-color:var(--dmg-bd)"></div>Avaria
  </div>
  <div class="hint">Clique para editar &middot; Ctrl+Enter salva &middot; Esc fecha</div>
</div>

<main>
  <div class="filters">
    <button class="filter-btn active" data-f="all">Todos</button>
    <button class="filter-btn" data-f="free">Livres</button>
    <button class="filter-btn" data-f="occupied">Ocupados</button>
    <button class="filter-btn" data-f="reserved">Reservados</button>
    <button class="filter-btn" data-f="damaged">Avarias</button>
    <div class="search-wrap">
      <input class="search-box" type="text" id="h-search"
             placeholder="buscar produto..." autocomplete="off">
      <div class="ac-drop" id="h-drop"></div>
    </div>
  </div>
  <div class="warehouse" id="warehouse"></div>
</main>

<div class="overlay" id="overlay">
  <div class="modal">
    <div class="modal-hdr">
      <div>
        <div class="modal-addr" id="m-addr">--</div>
        <div class="modal-sub"  id="m-sub">--</div>
      </div>
      <button class="modal-x" id="modal-x">x</button>
    </div>
    <div class="modal-body">
      <div class="field">
        <label>Status</label>
        <div class="st-group">
          <button class="st-btn" data-s="free">Livre</button>
          <button class="st-btn" data-s="occupied">Ocupado</button>
          <button class="st-btn" data-s="reserved">Reservado</button>
          <button class="st-btn" data-s="damaged">Avaria</button>
        </div>
      </div>
      <div class="field">
        <label>Produto / SKU</label>
        <div class="ac-wrap">
          <input type="text" id="m-product"
                 placeholder="Ex: Roundup WG 750g" autocomplete="off">
          <div class="ac-drop" id="m-drop"></div>
        </div>
      </div>
      <div class="field">
        <label>Quantidade</label>
        <input type="text" id="m-qty" placeholder="Ex: 48 cx - 3 paletes">
      </div>
      <div class="field">
        <label>Lote / Validade</label>
        <input type="text" id="m-lot" placeholder="Ex: L240815 - Val: 08/2026">
      </div>
      <div class="field">
        <label>Observacoes</label>
        <textarea id="m-notes" placeholder="Anotacoes livres..."></textarea>
      </div>
    </div>
    <div class="modal-ftr">
      <button class="btn btn-del"  id="btn-del">Limpar</button>
      <button class="btn btn-sec"  id="btn-cancel">Cancelar</button>
      <button class="btn btn-ok"   id="btn-save">Salvar</button>
    </div>
  </div>
</div>

<div id="tip"></div>
<div id="toast"></div>

<script>
var TURSO_URL   = '__TURSO_URL__';
var TURSO_TOKEN = '__TURSO_TOKEN__';
var posData  = '__POSITIONS_JSON__';
var prodList = '__PRODUCTS_JSON__';
var prodPos  = '__PROD_POS_JSON__';

var LAYOUT_A = [
  {t:'rack',col:1},{t:'aisle'},
  {t:'rack',col:2},{t:'rack',col:3},{t:'aisle'},
  {t:'rack',col:4},{t:'rack',col:5},{t:'aisle'},
  {t:'rack',col:6}
];
var LAYOUT_B = [
  {t:'rack',col:1},{t:'aisle'},
  {t:'rack',col:2},{t:'aisle'},
  {t:'rack',col:3},{t:'aisle'},
  {t:'rack',col:4}
];

var curAddr   = null;
var curStatus = 'free';
var curFilter = 'all';
var fuseInst  = null;
var acKbIdx   = -1;
var toastTmr  = null;

/* ── TURSO HTTP ─────────────────────────────────────────────── */
async function tursoExec(sql, args) {
  var mapped = (args || []).map(function(v) {
    return (v === null || v === undefined)
      ? {type:'null'}
      : {type:'text', value:String(v)};
  });
  var resp = await fetch(TURSO_URL + '/v2/pipeline', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + TURSO_TOKEN,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      requests: [
        {type:'execute', stmt:{sql:sql, args:mapped}},
        {type:'close'}
      ]
    })
  });
  if (!resp.ok) throw new Error('HTTP ' + resp.status);
  var d = await resp.json();
  if (d.results[0].type === 'error') throw new Error(d.results[0].error.message);
  return d.results[0].response.result;
}

/* ── RENDER ─────────────────────────────────────────────────── */
function buildSector(sKey, layout) {
  var wrap = document.createElement('div');

  var lbl = document.createElement('div');
  lbl.className = 'sector-label';
  lbl.textContent = 'SETOR ' + sKey;
  wrap.appendChild(lbl);

  var row = document.createElement('div');
  row.className = 'sector-row';

  for (var i = 0; i < layout.length; i++) {
    var item = layout[i];
    if (item.t === 'aisle') {
      var a = document.createElement('div');
      a.className = 'aisle';
      a.textContent = 'RUA';
      row.appendChild(a);
      continue;
    }
    var colName = 'C' + item.col;
    var block = document.createElement('div');
    block.className = 'rack-block';

    var bLbl = document.createElement('div');
    bLbl.className = 'rack-block-label';
    bLbl.textContent = colName;
    block.appendChild(bLbl);

    var col = document.createElement('div');
    col.className = 'rack-col';  /* column-reverse -> P13 at visual top */

    for (var pos = 1; pos <= 13; pos++) {
      var pRow = document.createElement('div');
      pRow.className = 'pos-row';

      for (var lvl = 1; lvl <= 4; lvl++) {
        var posStr = pos < 10 ? '0' + pos : String(pos);
        var addr = sKey + '.' + colName + '.P' + posStr + '.N' + lvl;

        var cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.addr = addr;
        applyCellState(cell);

        var lblEl = document.createElement('span');
        lblEl.className = 'cell-lbl';
        lblEl.textContent = pos + '.' + lvl;
        cell.appendChild(lblEl);

        (function(a) {
          cell.addEventListener('click', function() { openModal(a); });
          cell.addEventListener('mouseenter', function(e) { showTip(e, a); });
          cell.addEventListener('mouseleave', hideTip);
        })(addr);

        pRow.appendChild(cell);
      }
      col.appendChild(pRow);
    }
    block.appendChild(col);
    row.appendChild(block);
  }
  wrap.appendChild(row);
  return wrap;
}

function applyCellState(cell) {
  var addr = cell.dataset.addr;
  var d = posData[addr];
  var lblEl = cell.querySelector('.cell-lbl');
  var dotEl = cell.querySelector('.cell-dot');
  if (dotEl) dotEl.remove();
  cell.className = 'cell';
  if (d) {
    if      (d.status === 'occupied') cell.classList.add('occupied');
    else if (d.status === 'reserved') cell.classList.add('reserved');
    else if (d.status === 'damaged')  cell.classList.add('damaged');
    if (d.product || d.notes) {
      var dot = document.createElement('span');
      dot.className = 'cell-dot';
      cell.prepend(dot);
    }
  }
  if (lblEl) cell.appendChild(lblEl);
}

function renderMap() {
  var wh = document.getElementById('warehouse');
  wh.innerHTML = '';
  wh.appendChild(buildSector('A', LAYOUT_A));
  var cor = document.createElement('div');
  cor.className = 'corridor';
  cor.textContent = 'CORREDOR DE CARREGAMENTO';
  wh.appendChild(cor);
  wh.appendChild(buildSector('B', LAYOUT_B));
}

/* ── STATS ──────────────────────────────────────────────────── */
var ALL_ADDRS = (function() {
  var a = [];
  var sectors = [
    {s:'A', cols:[1,2,3,4,5,6]},
    {s:'B', cols:[1,2,3,4]}
  ];
  for (var si = 0; si < sectors.length; si++) {
    var s = sectors[si].s;
    var cols = sectors[si].cols;
    for (var ci = 0; ci < cols.length; ci++) {
      for (var p = 1; p <= 13; p++) {
        for (var l = 1; l <= 4; l++) {
          var ps = p < 10 ? '0' + p : String(p);
          a.push(s + '.C' + cols[ci] + '.P' + ps + '.N' + l);
        }
      }
    }
  }
  return a;
})();

function updateStats() {
  var free = 0, occ = 0, res = 0, dmg = 0;
  for (var i = 0; i < ALL_ADDRS.length; i++) {
    var st = (posData[ALL_ADDRS[i]] || {}).status || 'free';
    if      (st === 'occupied') occ++;
    else if (st === 'reserved') res++;
    else if (st === 'damaged')  dmg++;
    else                        free++;
  }
  document.getElementById('s-total').textContent = ALL_ADDRS.length;
  document.getElementById('s-free').textContent  = free;
  document.getElementById('s-occ').textContent   = occ;
  document.getElementById('s-res').textContent   = res;
  document.getElementById('s-dmg').textContent   = dmg;
}

/* ── FILTER ─────────────────────────────────────────────────── */
function applyFilter() {
  var ql = document.getElementById('h-search').value.trim().toLowerCase();
  document.querySelectorAll('.cell').forEach(function(c) {
    var d = posData[c.dataset.addr];
    var st = (d || {}).status || 'free';
    var prod = ((d || {}).product || '').toLowerCase();
    var show = (curFilter === 'all' || st === curFilter);
    if (show && ql && !prod.includes(ql)) show = false;
    c.classList.toggle('dimmed', !show);
  });
}

document.querySelectorAll('.filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    curFilter = btn.dataset.f;
    document.querySelectorAll('.filter-btn').forEach(function(b) {
      b.classList.remove('active');
    });
    btn.classList.add('active');
    applyFilter();
  });
});

/* ── HEADER SEARCH ──────────────────────────────────────────── */
var hSearch = document.getElementById('h-search');
var hDrop   = document.getElementById('h-drop');

hSearch.addEventListener('input', function() {
  applyFilter();
  updateAcDrop(this.value.trim(), hDrop, function(name) {
    hSearch.value = name;
    hDrop.classList.remove('open');
    applyFilter();
    pulseCells(prodPos[name] || []);
  });
});
hSearch.addEventListener('keydown', function(e) { acNav(e, hDrop); });

/* ── AUTOCOMPLETE ───────────────────────────────────────────── */
function initFuse() {
  fuseInst = new Fuse(
    prodList.map(function(p) { return {name: p}; }),
    {keys: ['name'], threshold: 0.42, includeScore: true}
  );
}

function updateAcDrop(q, dd, onSelect) {
  if (!q || !fuseInst) { dd.classList.remove('open'); return; }
  var res = fuseInst.search(q).slice(0, 8);
  if (!res.length) { dd.classList.remove('open'); return; }
  dd.innerHTML = res.map(function(r, i) {
    var nm = r.item.name;
    var ps = prodPos[nm] || [];
    var ps3 = ps.slice(0,3).join(', ') + (ps.length > 3 ? ' +' + (ps.length - 3) : '');
    return '<div class="ac-item" data-idx="' + i + '" data-name="' +
      nm.replace(/"/g, '&quot;') + '">' +
      '<div class="ac-name">' + esc(nm) + '</div>' +
      (ps.length ? '<div class="ac-pos">' + esc(ps3) + '</div>' : '') +
      '</div>';
  }).join('');
  dd.querySelectorAll('.ac-item').forEach(function(el) {
    el.addEventListener('mousedown', function(e) {
      e.preventDefault();
      onSelect(el.dataset.name);
    });
  });
  acKbIdx = -1;
  dd.classList.add('open');
}

function acNav(e, dd) {
  if (!dd.classList.contains('open')) return;
  var items = dd.querySelectorAll('.ac-item');
  if (!items.length) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    acKbIdx = Math.min(acKbIdx + 1, items.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    acKbIdx = Math.max(acKbIdx - 1, 0);
  } else if (e.key === 'Enter' && acKbIdx >= 0) {
    e.preventDefault();
    items[acKbIdx].dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
    return;
  } else if (e.key === 'Escape') {
    dd.classList.remove('open'); acKbIdx = -1; return;
  }
  items.forEach(function(it, i) { it.classList.toggle('kbf', i === acKbIdx); });
}

function pulseCells(addrs) {
  addrs.forEach(function(addr) {
    var c = document.querySelector('.cell[data-addr="' + CSS.escape(addr) + '"]');
    if (!c) return;
    c.classList.remove('hl');
    void c.offsetWidth;
    c.classList.add('hl');
    setTimeout(function() { c.classList.remove('hl'); }, 3200);
  });
}

/* ── MODAL ──────────────────────────────────────────────────── */
function openModal(addr) {
  curAddr = addr;
  var d = posData[addr] || {};
  var parts = addr.split('.');
  document.getElementById('m-addr').textContent = addr;
  document.getElementById('m-sub').textContent =
    'Setor ' + parts[0] + ' - ' + parts[1] +
    ' - Posicao ' + parseInt(parts[2].replace('P','')) +
    ' - Nivel ' + parts[3].replace('N','');
  curStatus = d.status || 'free';
  refreshStBtns();
  document.getElementById('m-product').value = d.product || '';
  document.getElementById('m-qty').value     = d.qty     || '';
  document.getElementById('m-lot').value     = d.lot     || '';
  document.getElementById('m-notes').value   = d.notes   || '';
  document.getElementById('m-drop').classList.remove('open');
  document.getElementById('overlay').classList.add('active');
  setTimeout(function() { document.getElementById('m-product').focus(); }, 60);
}

function closeModal() {
  document.getElementById('overlay').classList.remove('active');
  document.getElementById('m-drop').classList.remove('open');
  curAddr = null; acKbIdx = -1;
}

function refreshStBtns() {
  var map = {free:'a-free', occupied:'a-occ', reserved:'a-res', damaged:'a-dmg'};
  document.querySelectorAll('.st-btn').forEach(function(b) {
    b.className = 'st-btn';
    if (b.dataset.s === curStatus) b.classList.add(map[curStatus]);
  });
}

document.querySelectorAll('.st-btn').forEach(function(b) {
  b.addEventListener('click', function() { curStatus = b.dataset.s; refreshStBtns(); });
});
document.getElementById('modal-x').addEventListener('click', closeModal);
document.getElementById('btn-cancel').addEventListener('click', closeModal);
document.getElementById('overlay').addEventListener('click', function(e) {
  if (e.target === document.getElementById('overlay')) closeModal();
});

var mProduct = document.getElementById('m-product');
var mDrop    = document.getElementById('m-drop');
mProduct.addEventListener('input', function() {
  updateAcDrop(this.value.trim(), mDrop, function(name) {
    mProduct.value = name;
    mDrop.classList.remove('open');
    pulseCells(prodPos[name] || []);
  });
});
mProduct.addEventListener('keydown', function(e) { acNav(e, mDrop); });

/* ── SAVE ───────────────────────────────────────────────────── */
document.getElementById('btn-save').addEventListener('click', async function() {
  if (!curAddr) return;
  var product = mProduct.value.trim();
  var qty     = document.getElementById('m-qty').value.trim();
  var lot     = document.getElementById('m-lot').value.trim();
  var notes   = document.getElementById('m-notes').value.trim();
  var now     = new Date().toISOString();
  setBtns(true);
  try {
    await tursoExec(
      'INSERT INTO warehouse_positions(addr,status,product,qty,lot,notes,updated_at)' +
      'VALUES(?,?,?,?,?,?,?)' +
      ' ON CONFLICT(addr)DO UPDATE SET status=excluded.status,' +
      'product=excluded.product,qty=excluded.qty,lot=excluded.lot,' +
      'notes=excluded.notes,updated_at=excluded.updated_at',
      [curAddr, curStatus, product, qty, lot, notes, now]
    );
    var old = posData[curAddr] || {};
    posData[curAddr] = {status:curStatus, product:product, qty:qty, lot:lot, notes:notes};
    if (old.product && old.product !== product) {
      prodPos[old.product] = (prodPos[old.product] || []).filter(function(a) { return a !== curAddr; });
    }
    if (product) {
      if (!prodPos[product]) prodPos[product] = [];
      if (!prodPos[product].includes(curAddr)) prodPos[product].push(curAddr);
      if (!prodList.includes(product)) {
        prodList.push(product); prodList.sort(); initFuse();
      }
    }
    var c = document.querySelector('.cell[data-addr="' + CSS.escape(curAddr) + '"]');
    if (c) applyCellState(c);
    updateStats(); applyFilter(); closeModal();
    showToast(curAddr + ' salvo', 'ok');
  } catch(e) {
    showToast('Erro: ' + e.message, 'err'); console.error(e);
  } finally { setBtns(false); }
});

/* ── CLEAR ──────────────────────────────────────────────────── */
document.getElementById('btn-del').addEventListener('click', async function() {
  if (!curAddr) return;
  setBtns(true);
  try {
    await tursoExec('DELETE FROM warehouse_positions WHERE addr=?', [curAddr]);
    var old = posData[curAddr] || {};
    delete posData[curAddr];
    if (old.product) {
      prodPos[old.product] = (prodPos[old.product] || []).filter(function(a) { return a !== curAddr; });
    }
    var c = document.querySelector('.cell[data-addr="' + CSS.escape(curAddr) + '"]');
    if (c) applyCellState(c);
    updateStats(); applyFilter(); closeModal();
    showToast('Posicao limpa', 'ok');
  } catch(e) {
    showToast('Erro: ' + e.message, 'err'); console.error(e);
  } finally { setBtns(false); }
});

function setBtns(v) {
  document.getElementById('btn-save').disabled = v;
  document.getElementById('btn-del').disabled  = v;
}

/* ── TOOLTIP ────────────────────────────────────────────────── */
var tipEl = document.getElementById('tip');
function showTip(e, addr) {
  var d = posData[addr];
  if (!d || !d.product) return;
  tipEl.innerHTML = '<strong>' + esc(addr) + '</strong><br>' + esc(d.product) +
    (d.qty ? '<br><span style="color:var(--text2)">' + esc(d.qty) + '</span>' : '');
  tipEl.style.display = 'block';
  moveTip(e);
}
function moveTip(e) {
  tipEl.style.left = (e.clientX + 12) + 'px';
  tipEl.style.top  = (e.clientY + 12) + 'px';
}
function hideTip() { tipEl.style.display = 'none'; }
document.addEventListener('mousemove', function(e) {
  if (tipEl.style.display !== 'none') moveTip(e);
});

/* ── TOAST ──────────────────────────────────────────────────── */
function showToast(msg, type) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = (type === 'err') ? 't-err' : 't-ok';
  t.style.transform = 'translateY(0)'; t.style.opacity = '1';
  if (toastTmr) clearTimeout(toastTmr);
  toastTmr = setTimeout(function() {
    t.style.transform = 'translateY(60px)'; t.style.opacity = '0';
  }, 3200);
}

/* ── UTILS ──────────────────────────────────────────────────── */
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.search-wrap')) hDrop.classList.remove('open');
  if (!e.target.closest('.ac-wrap'))     mDrop.classList.remove('open');
});

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    if (hDrop.classList.contains('open')) { hDrop.classList.remove('open'); return; }
    if (mDrop.classList.contains('open')) { mDrop.classList.remove('open'); return; }
    if (document.getElementById('overlay').classList.contains('active')) closeModal();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && curAddr) {
    document.getElementById('btn-save').click();
  }
});

/* ── BOOT ───────────────────────────────────────────────────── */
initFuse();
renderMap();
updateStats();
</script>
</body>
</html>"""
)
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
<style>
:root {
  --bg:#0d0f14; --surf:#141720; --surf2:#1c2030; --border:#2a2f45;
  --accent:#00e5a0; --blue:#0099ff; --warn:#ffaa00; --danger:#ff4455;
  --text:#e8eaf0; --text2:#7a80a0;
  --free:#1a3a2a;     --free-bd:#00e5a0;
  --occ:#1a2540;      --occ-bd:#0099ff;
  --res:#3a2a10;      --res-bd:#ffaa00;
  --dmg:#3a1020;      --dmg-bd:#ff4455;
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;min-height:100%;overflow-x:auto;}

/* ── HEADER ── */
header{display:flex;align-items:center;justify-content:space-between;padding:12px 20px;
  border-bottom:1px solid var(--border);background:var(--surf);position:sticky;top:0;z-index:100;
  flex-wrap:wrap;gap:8px;}
.logo{font-family:'Syne',sans-serif;font-weight:800;font-size:16px;letter-spacing:.08em;color:var(--accent);}
.logo span{color:var(--text2);font-weight:400;margin-left:8px;font-size:11px;}
.stats{display:flex;gap:16px;font-size:10px;color:var(--text2);flex-wrap:wrap;}
.stat-item strong{display:block;font-size:13px;}

/* ── LEGEND ── */
.legend{display:flex;gap:12px;padding:8px 20px;background:var(--surf);
  border-bottom:1px solid var(--border);flex-wrap:wrap;align-items:center;}
.leg-item{display:flex;align-items:center;gap:5px;font-size:10px;color:var(--text2);}
.leg-dot{width:10px;height:10px;border-radius:2px;border:1px solid;flex-shrink:0;}
.hint{margin-left:auto;font-size:10px;color:var(--text2);}

/* ── MAIN ── */
main{padding:16px 20px;}

/* ── FILTERS ── */
.filters{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;align-items:center;position:relative;}
.filter-btn{padding:4px 12px;border-radius:20px;border:1px solid var(--border);
  background:transparent;color:var(--text2);font-family:'JetBrains Mono',monospace;
  font-size:10px;cursor:pointer;transition:all .15s;}
.filter-btn:hover,.filter-btn.active{background:var(--surf2);color:var(--text);border-color:var(--accent);}
.search-wrap{position:relative;margin-left:6px;}
.search-box{background:var(--surf);border:1px solid var(--border);border-radius:20px;
  padding:5px 14px;color:var(--text);font-family:'JetBrains Mono',monospace;font-size:10px;
  outline:none;width:180px;transition:border-color .15s;}
.search-box:focus{border-color:var(--accent);}
.search-box::placeholder{color:var(--text2);}

/* ── AUTOCOMPLETE DROP ── */
.ac-drop{position:absolute;top:calc(100% + 4px);right:0;left:0;background:var(--surf2);
  border:1px solid var(--border);border-radius:8px;max-height:200px;overflow-y:auto;
  z-index:200;box-shadow:0 10px 28px rgba(0,0,0,.5);display:none;}
.ac-drop.open{display:block;}
.ac-item{padding:7px 12px;cursor:pointer;border-bottom:1px solid rgba(255,255,255,.04);
  font-size:10px;transition:background .1s;}
.ac-item:hover,.ac-item.kbf{background:rgba(0,229,160,.1);}
.ac-item:last-child{border-bottom:none;}
.ac-name{color:var(--text);}
.ac-pos{color:var(--text2);font-size:9px;margin-top:2px;}

/* ── WAREHOUSE ── */
.warehouse{display:flex;flex-direction:column;gap:8px;width:fit-content;}

.sector-label{font-family:'Syne',sans-serif;font-size:10px;font-weight:700;
  letter-spacing:.18em;color:var(--accent);text-transform:uppercase;margin-bottom:6px;
  border-left:2px solid var(--accent);padding-left:8px;}

.sector-row{display:flex;flex-direction:row;gap:0;align-items:flex-start;}

.aisle{display:flex;align-items:center;justify-content:center;width:26px;min-width:26px;
  background:transparent;border:1px dashed #2a2f45;border-radius:3px;font-size:6px;
  color:#2a3050;letter-spacing:.08em;writing-mode:vertical-rl;text-orientation:mixed;
  user-select:none;align-self:stretch;margin:0 3px;}

.rack-block{display:flex;flex-direction:column;gap:0;align-items:center;margin:0 2px;}
.rack-block-label{font-size:9px;color:var(--text2);letter-spacing:.06em;
  padding-bottom:3px;text-align:center;}

/* column-reverse: append P1..P13, P13 appears at top visually */
.rack-col{display:flex;flex-direction:column-reverse;gap:2px;}

/* Each position row = 4 level cells side by side */
.pos-row{display:flex;flex-direction:row;gap:2px;}

/* Single cell */
.cell{width:28px;height:26px;border-radius:3px;border:1px solid var(--free-bd);
  background:var(--free);cursor:pointer;position:relative;transition:all .1s ease;
  flex-shrink:0;overflow:hidden;}
.cell:hover{filter:brightness(1.6);transform:scale(1.08);z-index:10;}
.cell.occupied{background:var(--occ);border-color:var(--occ-bd);}
.cell.reserved{background:var(--res);border-color:var(--res-bd);}
.cell.damaged {background:var(--dmg);border-color:var(--dmg-bd);animation:blink 2s ease-in-out infinite;}
.cell.dimmed  {opacity:.07!important;pointer-events:none!important;}
.cell.hl      {animation:pulse-hl .7s ease-in-out 4;}

@keyframes blink{0%,100%{border-color:var(--dmg-bd);}50%{border-color:#ff6677;box-shadow:0 0 5px rgba(255,68,85,.45);}}
@keyframes pulse-hl{0%,100%{transform:scale(1);}50%{transform:scale(1.22);box-shadow:0 0 9px var(--accent);filter:brightness(1.9);}}

/* Tiny label: "pos.lvl" */
.cell-lbl{font-size:5.5px;color:rgba(255,255,255,.18);position:absolute;bottom:1px;right:2px;pointer-events:none;line-height:1;}

/* Data dot */
.cell-dot{position:absolute;top:2px;left:2px;width:4px;height:4px;border-radius:50%;background:var(--accent);pointer-events:none;}

/* ── CORRIDOR ── */
.corridor{display:flex;align-items:center;justify-content:center;height:38px;
  background:#0a1520;border:1px solid var(--border);border-left:3px solid var(--blue);
  border-radius:4px;margin:10px 0;font-size:9px;color:var(--text2);
  letter-spacing:.15em;text-transform:uppercase;padding:0 20px;gap:10px;}
.corridor::before,.corridor::after{content:'▶';color:var(--blue);opacity:.4;font-size:7px;}

/* ── TOOLTIP ── */
#tip{position:fixed;background:var(--surf2);border:1px solid var(--border);border-radius:6px;
  padding:6px 10px;font-size:10px;color:var(--text);pointer-events:none;z-index:600;
  max-width:200px;box-shadow:0 6px 16px rgba(0,0,0,.45);display:none;line-height:1.55;}
#tip strong{color:var(--accent);}

/* ── MODAL ── */
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:300;
  backdrop-filter:blur(4px);align-items:center;justify-content:center;}
.overlay.active{display:flex;}
.modal{background:var(--surf);border:1px solid var(--border);border-radius:12px;
  width:400px;max-width:95vw;max-height:92vh;overflow-y:auto;
  box-shadow:0 32px 80px rgba(0,0,0,.6);animation:slideUp .18s ease;}
@keyframes slideUp{from{transform:translateY(14px);opacity:0;}to{transform:translateY(0);opacity:1;}}
.modal-hdr{padding:16px 20px 12px;border-bottom:1px solid var(--border);
  display:flex;align-items:flex-start;justify-content:space-between;}
.modal-addr{font-family:'Syne',sans-serif;font-size:17px;font-weight:800;
  color:var(--accent);letter-spacing:.03em;word-break:break-all;}
.modal-sub{font-size:9px;color:var(--text2);margin-top:3px;}
.modal-x{background:none;border:none;color:var(--text2);font-size:17px;
  cursor:pointer;padding:0 4px;transition:color .12s;}
.modal-x:hover{color:var(--text);}
.modal-body{padding:16px 20px;display:flex;flex-direction:column;gap:12px;}
.st-group{display:flex;gap:5px;flex-wrap:wrap;}
.st-btn{flex:1;min-width:72px;padding:7px 4px;border-radius:6px;border:1px solid var(--border);
  background:transparent;color:var(--text2);font-family:'JetBrains Mono',monospace;
  font-size:10px;cursor:pointer;transition:all .12s;text-align:center;white-space:nowrap;}
.st-btn:hover{background:var(--surf2);}
.st-btn.a-free{background:var(--free);border-color:var(--free-bd);color:var(--accent);}
.st-btn.a-occ {background:var(--occ); border-color:var(--occ-bd); color:var(--blue);}
.st-btn.a-res {background:var(--res); border-color:var(--res-bd); color:var(--warn);}
.st-btn.a-dmg {background:var(--dmg); border-color:var(--dmg-bd); color:var(--danger);}
.field{display:flex;flex-direction:column;gap:5px;}
.field label{font-size:9px;color:var(--text2);letter-spacing:.1em;text-transform:uppercase;}
.field input,.field textarea{background:var(--surf2);border:1px solid var(--border);
  border-radius:6px;color:var(--text);font-family:'JetBrains Mono',monospace;
  font-size:13px;padding:9px 11px;width:100%;outline:none;resize:none;transition:border-color .12s;}
.field input:focus,.field textarea:focus{border-color:var(--accent);}
.field textarea{height:62px;}
.ac-wrap{position:relative;}
.modal-ftr{padding:12px 20px;border-top:1px solid var(--border);
  display:flex;gap:7px;justify-content:flex-end;}
.btn{padding:8px 16px;border-radius:6px;border:none;font-family:'JetBrains Mono',monospace;
  font-size:10px;cursor:pointer;transition:all .12s;font-weight:700;}
.btn-sec{background:var(--surf2);color:var(--text2);border:1px solid var(--border);}
.btn-sec:hover{color:var(--text);}
.btn-ok{background:var(--accent);color:#000;}
.btn-ok:hover{filter:brightness(1.1);}
.btn-del{background:var(--dmg);color:var(--danger);border:1px solid var(--dmg-bd);margin-right:auto;}
.btn-del:hover{filter:brightness(1.2);}
.btn:disabled{opacity:.45;cursor:not-allowed;}

/* ── TOAST ── */
#toast{position:fixed;bottom:18px;right:18px;background:var(--surf);
  border-radius:8px;padding:10px 16px;font-size:11px;z-index:400;
  transform:translateY(60px);opacity:0;transition:all .22s ease;pointer-events:none;}
.t-ok {border:1px solid var(--accent);color:var(--accent);}
.t-err{border:1px solid var(--danger);color:var(--danger);}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
</style>
</head>
<body>

<!-- HEADER -->
<header>
  <div class="logo">CAMDA <span>/ Mapa do Armazém</span></div>
  <div class="stats">
    <div class="stat-item"><strong id="s-total">520</strong>posições</div>
    <div class="stat-item"><strong id="s-free" style="color:var(--accent)">520</strong>livres</div>
    <div class="stat-item"><strong id="s-occ"  style="color:var(--blue)">0</strong>ocupadas</div>
    <div class="stat-item"><strong id="s-res"  style="color:var(--warn)">0</strong>reservadas</div>
    <div class="stat-item"><strong id="s-dmg"  style="color:var(--danger)">0</strong>avarias</div>
    <div class="stat-item" style="border-left:1px solid var(--border);padding-left:16px;">
      <strong id="s-pct" style="color:var(--warn);font-size:15px;">0%</strong>
      <span style="font-size:9px;">ocupado</span>
      <div id="occ-bar" style="height:4px;background:var(--border);border-radius:2px;margin-top:3px;min-width:80px;position:relative;">
        <div id="occ-fill" style="height:100%;width:0%;background:linear-gradient(90deg,var(--blue),var(--warn));border-radius:2px;transition:width .5s;"></div>
      </div>
    </div>
  </div>
</header>

<!-- LEGEND -->
<div class="legend">
  <div class="leg-item"><div class="leg-dot" style="background:var(--free);border-color:var(--free-bd)"></div>Livre</div>
  <div class="leg-item"><div class="leg-dot" style="background:#0d2a1a;border-color:#4ade80"></div><span>Ocupado</span></div>
  <div class="leg-item"><div class="leg-dot" style="background:#0d1a35;border-color:#60a5fa"></div></div>
  <div class="leg-item"><div class="leg-dot" style="background:#2a1a08;border-color:#f59e0b"></div><span style="color:var(--text2);font-size:9px;">&#8592; cor por produto</span></div>
  <div class="leg-item" style="margin-left:6px;"><div class="leg-dot" style="background:var(--res);border-color:var(--res-bd)"></div>Reservado</div>
  <div class="leg-item"><div class="leg-dot" style="background:var(--dmg);border-color:var(--dmg-bd)"></div>Avaria</div>
  <div class="hint">&#128161; Clique para editar &middot; Ctrl+Enter salva &middot; Esc fecha</div>
</div>

<!-- MAIN -->
<main>
  <div class="filters">
    <button class="filter-btn active" data-f="all">Todos</button>
    <button class="filter-btn" data-f="free">Livres</button>
    <button class="filter-btn" data-f="occupied">Ocupados</button>
    <button class="filter-btn" data-f="reserved">Reservados</button>
    <button class="filter-btn" data-f="damaged">Avarias</button>
    <div class="search-wrap">
      <input class="search-box" type="text" id="h-search" placeholder="&#128269; buscar produto..." autocomplete="off">
      <div class="ac-drop" id="h-drop"></div>
    </div>
  </div>
  <div class="warehouse" id="warehouse"></div>
</main>

<!-- MODAL -->
<div class="overlay" id="overlay">
  <div class="modal">
    <div class="modal-hdr">
      <div>
        <div class="modal-addr" id="m-addr">—</div>
        <div class="modal-sub"  id="m-sub">—</div>
      </div>
      <button class="modal-x" id="modal-x">&#10005;</button>
    </div>
    <div class="modal-body">
      <div class="field">
        <label>Status</label>
        <div class="st-group">
          <button class="st-btn" data-s="free">&#x1F7E9; Livre</button>
          <button class="st-btn" data-s="occupied">&#x1F7E6; Ocupado</button>
          <button class="st-btn" data-s="reserved">&#x1F7E8; Reservado</button>
          <button class="st-btn" data-s="damaged">&#x1F7E5; Avaria</button>
        </div>
      </div>
      <div class="field">
        <label>Produto / SKU</label>
        <div class="ac-wrap">
          <input type="text" id="m-product" placeholder="Ex: Roundup WG 750g" autocomplete="off">
          <div class="ac-drop" id="m-drop"></div>
        </div>
      </div>
      <div class="field">
        <label>Quantidade</label>
        <input type="text" id="m-qty" placeholder="Ex: 48 cx &middot; 3 paletes">
      </div>
      <div class="field">
        <label>Lote / Validade</label>
        <input type="text" id="m-lot" placeholder="Ex: L240815 &middot; Val: 08/2026">
      </div>
      <div class="field">
        <label>Observações</label>
        <textarea id="m-notes" placeholder="Anotações livres..."></textarea>
      </div>
    </div>
    <div class="modal-ftr">
      <button class="btn btn-del" id="btn-del">&#128465; Limpar</button>
      <button class="btn btn-sec" id="btn-cancel">Cancelar</button>
      <button class="btn btn-ok"  id="btn-save">&#128190; Salvar</button>
    </div>
  </div>
</div>

<div id="tip"></div>
<div id="toast"></div>

<script>
/* ── INJECTED BY PYTHON ──────────────────────────────────── */
const TURSO_URL   = '__TURSO_URL__';
const TURSO_TOKEN = '__TURSO_TOKEN__';
let posData       = '__POSITIONS_JSON__';
let prodList      = '__PRODUCTS_JSON__';
let prodPos       = '__PROD_POS_JSON__';

/* ── LAYOUT ──────────────────────────────────────────────── */
const LAYOUT_A = [
  {t:'rack',col:1},{t:'aisle'},
  {t:'rack',col:2},{t:'rack',col:3},{t:'aisle'},
  {t:'rack',col:4},{t:'rack',col:5},{t:'aisle'},
  {t:'rack',col:6}
];
const LAYOUT_B = [
  {t:'rack',col:1},{t:'aisle'},
  {t:'rack',col:2},{t:'aisle'},
  {t:'rack',col:3},{t:'aisle'},
  {t:'rack',col:4}
];

/* ── PRODUCT COLORS ──────────────────────────────────────── */
const PROD_COLORS=[
  {bg:'#0d2a1a',bd:'#4ade80'},{bg:'#0d1a35',bd:'#60a5fa'},
  {bg:'#2a1a08',bd:'#f59e0b'},{bg:'#2a0d10',bd:'#f87171'},
  {bg:'#1a0d2a',bd:'#a78bfa'},{bg:'#0d2218',bd:'#34d399'},
  {bg:'#2a1808',bd:'#fb923c'},{bg:'#2a0d22',bd:'#e879f9'},
  {bg:'#0d2228',bd:'#22d3ee'},{bg:'#2a2208',bd:'#facc15'},
  {bg:'#0d2020',bd:'#6ee7b7'},{bg:'#2a1018',bd:'#fda4af'},
  {bg:'#1a2008',bd:'#bef264'},{bg:'#081a2a',bd:'#38bdf8'},
  {bg:'#2a1a20',bd:'#fb7185'},{bg:'#0d1a20',bd:'#93c5fd'},
];
function prodColorIdx(name){
  let h=0;
  for(let i=0;i<name.length;i++) h=(Math.imul(h,31)+name.charCodeAt(i))>>>0;
  return h%PROD_COLORS.length;
}
function getProdColor(name){return PROD_COLORS[prodColorIdx(name)];}

/* ── STATE ───────────────────────────────────────────────── */
let curAddr   = null;
let curStatus = 'free';
let curFilter = 'all';
let fuseInst  = null;
let acKbIdx   = -1;

/* ── TURSO HTTP ──────────────────────────────────────────── */
async function tursoExec(sql, args) {
  const mapped = (args||[]).map(v=>
    (v===null||v===undefined)?{type:'null'}:{type:'text',value:String(v)}
  );
  const r = await fetch(TURSO_URL+'/v2/pipeline',{
    method:'POST',
    headers:{'Authorization':'Bearer '+TURSO_TOKEN,'Content-Type':'application/json'},
    body:JSON.stringify({requests:[{type:'execute',stmt:{sql,args:mapped}},{type:'close'}]})
  });
  if(!r.ok) throw new Error('HTTP '+r.status);
  const d = await r.json();
  if(d.results[0].type==='error') throw new Error(d.results[0].error.message);
  return d.results[0].response.result;
}

/* ── RENDER ──────────────────────────────────────────────── */
function buildSector(sKey, layout) {
  const wrap = document.createElement('div');

  const lbl = document.createElement('div');
  lbl.className = 'sector-label';
  lbl.textContent = 'SETOR '+sKey;
  wrap.appendChild(lbl);

  const row = document.createElement('div');
  row.className = 'sector-row';

  for(const item of layout){
    if(item.t==='aisle'){
      const a = document.createElement('div');
      a.className='aisle'; a.textContent='RUA';
      row.appendChild(a);
      continue;
    }
    const colName = 'C'+item.col;
    const block = document.createElement('div');
    block.className='rack-block';

    const bLbl = document.createElement('div');
    bLbl.className='rack-block-label';
    bLbl.textContent = colName;
    block.appendChild(bLbl);

    const col = document.createElement('div');
    col.className='rack-col'; /* column-reverse → P13 at visual top */

    for(let pos=1;pos<=13;pos++){
      const pRow = document.createElement('div');
      pRow.className='pos-row';
      for(let lvl=1;lvl<=4;lvl++){
        const posStr = String(pos).padStart(2,'0');
        const addr = `${sKey}.${colName}.P${posStr}.N${lvl}`;
        const cell = document.createElement('div');
        cell.className='cell';
        cell.dataset.addr=addr;
        applyCellState(cell);

        const lbl2=document.createElement('span');
        lbl2.className='cell-lbl';
        lbl2.textContent=`${pos}.${lvl}`;
        cell.appendChild(lbl2);

        cell.addEventListener('click',()=>openModal(addr));
        cell.addEventListener('mouseenter',e=>showTip(e,addr));
        cell.addEventListener('mouseleave',hideTip);
        pRow.appendChild(cell);
      }
      col.appendChild(pRow);
    }
    block.appendChild(col);
    row.appendChild(block);
  }
  wrap.appendChild(row);
  return wrap;
}

function applyCellState(cell){
  const addr = cell.dataset.addr;
  const d = posData[addr];
  /* keep cell-lbl child if present */
  const lblEl = cell.querySelector('.cell-lbl');
  const dotEl = cell.querySelector('.cell-dot');
  if(dotEl) dotEl.remove();
  cell.className='cell';
  cell.style.background='';
  cell.style.borderColor='';
  if(d){
    if(d.status==='occupied'){
      cell.classList.add('occupied');
      if(d.product){
        const col=getProdColor(d.product);
        cell.style.background=col.bg;
        cell.style.borderColor=col.bd;
      }
    } else if(d.status==='reserved'){
      cell.classList.add('reserved');
    } else if(d.status==='damaged'){
      cell.classList.add('damaged');
    }
    if(d.product||d.notes){
      const dot=document.createElement('span');
      dot.className='cell-dot';
      if(d.product&&d.status==='occupied'){
        dot.style.background=getProdColor(d.product).bd;
      }
      cell.prepend(dot);
    }
  }
  if(lblEl) cell.appendChild(lblEl);
}

function renderMap(){
  const wh = document.getElementById('warehouse');
  wh.innerHTML='';
  wh.appendChild(buildSector('A',LAYOUT_A));
  const cor=document.createElement('div');
  cor.className='corridor'; cor.textContent='CORREDOR DE CARREGAMENTO';
  wh.appendChild(cor);
  wh.appendChild(buildSector('B',LAYOUT_B));
}

/* ── STATS ───────────────────────────────────────────────── */
const ALL_ADDRS=(()=>{
  const a=[];
  for(const s of['A','B']){
    const cols=s==='A'?[1,2,3,4,5,6]:[1,2,3,4];
    for(const c of cols)
      for(let p=1;p<=13;p++)
        for(let l=1;l<=4;l++)
          a.push(`${s}.C${c}.P${String(p).padStart(2,'0')}.N${l}`);
  }
  return a;
})();

function updateStats(){
  let free=0,occ=0,res=0,dmg=0;
  for(const addr of ALL_ADDRS){
    const st=(posData[addr]||{}).status||'free';
    if(st==='occupied')occ++;
    else if(st==='reserved')res++;
    else if(st==='damaged')dmg++;
    else free++;
  }
  const total=ALL_ADDRS.length;
  const usadas=occ+res;
  const pct=total>0?Math.round(usadas/total*100):0;
  document.getElementById('s-total').textContent=total;
  document.getElementById('s-free').textContent=free;
  document.getElementById('s-occ').textContent=occ;
  document.getElementById('s-res').textContent=res;
  document.getElementById('s-dmg').textContent=dmg;
  document.getElementById('s-pct').textContent=pct+'%';
  const fill=document.getElementById('occ-fill');
  if(fill){fill.style.width=pct+'%';}
}

/* ── FILTER ──────────────────────────────────────────────── */
function applyFilter(){
  const ql=document.getElementById('h-search').value.trim().toLowerCase();
  document.querySelectorAll('.cell').forEach(c=>{
    const d=posData[c.dataset.addr];
    const st=(d||{}).status||'free';
    const prod=((d||{}).product||'').toLowerCase();
    let show=curFilter==='all'||st===curFilter;
    if(show&&ql&&!prod.includes(ql)) show=false;
    c.classList.toggle('dimmed',!show);
  });
}

document.querySelectorAll('.filter-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    curFilter=btn.dataset.f;
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    applyFilter();
  });
});

/* ── HEADER SEARCH ───────────────────────────────────────── */
const hSearch=document.getElementById('h-search');
const hDrop=document.getElementById('h-drop');

hSearch.addEventListener('input',function(){
  applyFilter();
  updateAcDrop(this.value.trim(),hDrop,name=>{
    hSearch.value=name; hDrop.classList.remove('open');
    applyFilter(); pulseCells(prodPos[name]||[]);
  });
});
hSearch.addEventListener('keydown',e=>acNav(e,hDrop));

/* ── FUSE / AUTOCOMPLETE ─────────────────────────────────── */
function initFuse(){
  fuseInst=new Fuse(prodList.map(p=>({name:p})),{keys:['name'],threshold:.42,includeScore:true});
}

function updateAcDrop(q,dd,onSelect){
  if(!q||!fuseInst){dd.classList.remove('open');return;}
  const res=fuseInst.search(q).slice(0,8);
  if(!res.length){dd.classList.remove('open');return;}
  dd.innerHTML=res.map((r,i)=>{
    const nm=r.item.name;
    const ps=(prodPos[nm]||[]);
    const ps3=ps.slice(0,3).join(', ')+(ps.length>3?' +'+(ps.length-3):'');
    return `<div class="ac-item" data-idx="${i}" data-name="${nm.replace(/"/g,'&quot;')}">
      <div class="ac-name">${esc(nm)}</div>
      ${ps.length?`<div class="ac-pos">${esc(ps3)}</div>`:''}
    </div>`;
  }).join('');
  dd.querySelectorAll('.ac-item').forEach(el=>{
    el.addEventListener('mousedown',e=>{e.preventDefault();onSelect(el.dataset.name);});
  });
  acKbIdx=-1;
  dd.classList.add('open');
}

function acNav(e,dd){
  if(!dd.classList.contains('open'))return;
  const items=dd.querySelectorAll('.ac-item');
  if(!items.length)return;
  if(e.key==='ArrowDown'){e.preventDefault();acKbIdx=Math.min(acKbIdx+1,items.length-1);}
  else if(e.key==='ArrowUp'){e.preventDefault();acKbIdx=Math.max(acKbIdx-1,0);}
  else if(e.key==='Enter'&&acKbIdx>=0){e.preventDefault();items[acKbIdx].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));return;}
  else if(e.key==='Escape'){dd.classList.remove('open');acKbIdx=-1;return;}
  items.forEach((it,i)=>it.classList.toggle('kbf',i===acKbIdx));
}

function pulseCells(addrs){
  addrs.forEach(addr=>{
    const c=document.querySelector(`.cell[data-addr="${CSS.escape(addr)}"]`);
    if(!c)return; c.classList.remove('hl'); void c.offsetWidth; c.classList.add('hl');
    setTimeout(()=>c.classList.remove('hl'),3200);
  });
}

/* ── MODAL ───────────────────────────────────────────────── */
function openModal(addr){
  curAddr=addr;
  const d=posData[addr]||{};
  const parts=addr.split('.');
  document.getElementById('m-addr').textContent=addr;
  document.getElementById('m-sub').textContent=
    `Setor ${parts[0]} · ${parts[1]} · Posição ${parseInt(parts[2].replace('P',''))} · Nível ${parts[3].replace('N','')}`;
  curStatus=d.status||'free'; refreshStBtns();
  document.getElementById('m-product').value=d.product||'';
  document.getElementById('m-qty').value=d.qty||'';
  document.getElementById('m-lot').value=d.lot||'';
  document.getElementById('m-notes').value=d.notes||'';
  document.getElementById('m-drop').classList.remove('open');
  document.getElementById('overlay').classList.add('active');
  setTimeout(()=>document.getElementById('m-product').focus(),60);
}

function closeModal(){
  document.getElementById('overlay').classList.remove('active');
  document.getElementById('m-drop').classList.remove('open');
  curAddr=null; acKbIdx=-1;
}

function refreshStBtns(){
  document.querySelectorAll('.st-btn').forEach(b=>{
    b.className='st-btn';
    if(b.dataset.s===curStatus) b.classList.add('a-'+{'free':'free','occupied':'occ','reserved':'res','damaged':'dmg'}[curStatus]);
  });
}

document.querySelectorAll('.st-btn').forEach(b=>
  b.addEventListener('click',()=>{curStatus=b.dataset.s;refreshStBtns();})
);
document.getElementById('modal-x').addEventListener('click',closeModal);
document.getElementById('btn-cancel').addEventListener('click',closeModal);
document.getElementById('overlay').addEventListener('click',e=>{if(e.target===document.getElementById('overlay'))closeModal();});

/* Modal product autocomplete */
const mProduct=document.getElementById('m-product');
const mDrop=document.getElementById('m-drop');
mProduct.addEventListener('input',function(){
  updateAcDrop(this.value.trim(),mDrop,name=>{
    mProduct.value=name; mDrop.classList.remove('open');
    pulseCells(prodPos[name]||[]);
  });
});
mProduct.addEventListener('keydown',e=>acNav(e,mDrop));

/* ── SAVE ────────────────────────────────────────────────── */
document.getElementById('btn-save').addEventListener('click',async()=>{
  if(!curAddr)return;
  const product=mProduct.value.trim();
  const qty=document.getElementById('m-qty').value.trim();
  const lot=document.getElementById('m-lot').value.trim();
  const notes=document.getElementById('m-notes').value.trim();
  const now=new Date().toISOString();
  setBtns(true);
  try{
    await tursoExec(
      'INSERT INTO warehouse_positions(addr,status,product,qty,lot,notes,updated_at)VALUES(?,?,?,?,?,?,?)'+
      ' ON CONFLICT(addr)DO UPDATE SET status=excluded.status,product=excluded.product,'+
      'qty=excluded.qty,lot=excluded.lot,notes=excluded.notes,updated_at=excluded.updated_at',
      [curAddr,curStatus,product,qty,lot,notes,now]
    );
    /* update local */
    const old=posData[curAddr]||{};
    posData[curAddr]={status:curStatus,product,qty,lot,notes};
    /* update prodPos index */
    if(old.product&&old.product!==product){
      prodPos[old.product]=(prodPos[old.product]||[]).filter(a=>a!==curAddr);
    }
    if(product){
      if(!prodPos[product])prodPos[product]=[];
      if(!prodPos[product].includes(curAddr))prodPos[product].push(curAddr);
      if(!prodList.includes(product)){prodList.push(product);prodList.sort();initFuse();}
    }
    /* refresh cell */
    const c=document.querySelector(`.cell[data-addr="${CSS.escape(curAddr)}"]`);
    if(c)applyCellState(c);
    updateStats(); applyFilter(); closeModal();
    showToast('&#10003; '+curAddr+' salvo','ok');
  }catch(e){showToast('&#10007; Erro: '+e.message,'err');console.error(e);}
  finally{setBtns(false);}
});

/* ── CLEAR ───────────────────────────────────────────────── */
document.getElementById('btn-del').addEventListener('click',async()=>{
  if(!curAddr)return;
  setBtns(true);
  try{
    await tursoExec('DELETE FROM warehouse_positions WHERE addr=?',[curAddr]);
    const old=posData[curAddr]||{};
    delete posData[curAddr];
    if(old.product)prodPos[old.product]=(prodPos[old.product]||[]).filter(a=>a!==curAddr);
    const c=document.querySelector(`.cell[data-addr="${CSS.escape(curAddr)}"]`);
    if(c)applyCellState(c);
    updateStats(); applyFilter(); closeModal();
    showToast('&#128465; Posição limpa','ok');
  }catch(e){showToast('&#10007; Erro: '+e.message,'err');console.error(e);}
  finally{setBtns(false);}
});

function setBtns(v){
  document.getElementById('btn-save').disabled=v;
  document.getElementById('btn-del').disabled=v;
}

/* ── TOOLTIP ─────────────────────────────────────────────── */
const tipEl=document.getElementById('tip');
function showTip(e,addr){
  const d=posData[addr];
  if(!d||!d.product)return;
  tipEl.innerHTML=`<strong>${esc(addr)}</strong><br>${esc(d.product)}`+
    (d.qty?`<br><span style="color:var(--text2)">${esc(d.qty)}</span>`:'');
  tipEl.style.display='block'; moveTip(e);
}
function moveTip(e){tipEl.style.left=(e.clientX+12)+'px';tipEl.style.top=(e.clientY+12)+'px';}
function hideTip(){tipEl.style.display='none';}
document.addEventListener('mousemove',e=>{if(tipEl.style.display!=='none')moveTip(e);});

/* ── TOAST ───────────────────────────────────────────────── */
let toastTmr=null;
function showToast(msg,type){
  const t=document.getElementById('toast');
  t.innerHTML=msg; t.className=type==='err'?'t-err':'t-ok';
  t.style.transform='translateY(0)'; t.style.opacity='1';
  if(toastTmr)clearTimeout(toastTmr);
  toastTmr=setTimeout(()=>{t.style.transform='translateY(60px)';t.style.opacity='0';},3200);
}

/* ── UTILS ───────────────────────────────────────────────── */
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

/* close dropdowns on outside click */
document.addEventListener('click',e=>{
  if(!e.target.closest('.search-wrap'))hDrop.classList.remove('open');
  if(!e.target.closest('.ac-wrap'))mDrop.classList.remove('open');
});

/* global keys */
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    if(hDrop.classList.contains('open')){hDrop.classList.remove('open');return;}
    if(mDrop.classList.contains('open')){mDrop.classList.remove('open');return;}
    if(document.getElementById('overlay').classList.contains('active'))closeModal();
  }
  if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&curAddr)
    document.getElementById('btn-save').click();
});

/* ── BOOT ────────────────────────────────────────────────── */
initFuse();
renderMap();
updateStats();
</script>
</body>
</html>"""
