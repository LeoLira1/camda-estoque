"""
mural_tab.py — Aba "Mural" para o dashboard CAMDA Estoque.

Renderiza o mural de post-its via st.components.v1.html.
Os dados são carregados do Python (Turso/libSQL) na montagem inicial e
as mutações (add/delete) são feitas diretamente pelo JavaScript via
Turso HTTP API — mesmo padrão do warehouse_tab.py.
"""

import json as _json
import streamlit.components.v1 as _components

# ---------------------------------------------------------------------------
# HTML / CSS / JS template
# ---------------------------------------------------------------------------
_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
  background: transparent;
  padding: 4px 2px 16px;
}

/* TOPBAR */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 18px;
}

.topbar-title {
  font-size: 28px;
  font-weight: 700;
  color: #e0e6ed;
  letter-spacing: -0.5px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.count-pill {
  font-size: 12px;
  color: #94a3b8;
  background: rgba(255,255,255,0.08);
  border-radius: 999px;
  padding: 5px 14px;
}

.add-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #3b82f6;
  border: none;
  color: #fff;
  font-size: 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: transform 0.15s, background 0.15s;
  flex-shrink: 0;
}
.add-btn:hover { transform: scale(1.1); background: #2563eb; }

/* FILTERS */
.filters {
  display: flex;
  gap: 6px;
  padding: 0 0 20px;
  flex-wrap: wrap;
}

.ftag {
  font-size: 11px;
  padding: 5px 14px;
  border-radius: 999px;
  border: 1.5px solid rgba(255,255,255,0.15);
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.12s;
  font-family: inherit;
}
.ftag:hover, .ftag.on {
  background: #e0e6ed;
  color: #0a0f1a;
  border-color: #e0e6ed;
}

/* GRID */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

/* CARD */
.card {
  border-radius: 20px;
  padding: 20px 18px 16px;
  min-height: 190px;
  display: flex;
  flex-direction: column;
  position: relative;
  cursor: default;
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1), box-shadow 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.18);
  animation: popIn 0.28s cubic-bezier(.34,1.56,.64,1) both;
}
.card:hover {
  transform: translateY(-6px) rotate(-0.7deg);
  box-shadow: 0 14px 36px rgba(0,0,0,0.28);
  z-index: 3;
}
@keyframes popIn {
  from { opacity: 0; transform: scale(0.88) translateY(10px); }
  to   { opacity: 1; transform: scale(1)    translateY(0);    }
}

.card-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.9px;
  text-transform: uppercase;
  opacity: 0.5;
  margin-bottom: 10px;
}
.card-text {
  font-size: 14px;
  line-height: 1.65;
  flex: 1;
  word-break: break-word;
}
.card-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-top: 16px;
  gap: 4px;
}
.card-author {
  font-size: 11px;
  font-weight: 700;
  opacity: 0.5;
}
.card-time {
  font-size: 10px;
  opacity: 0.35;
  white-space: nowrap;
}
.card-del {
  position: absolute;
  top: 12px;
  right: 14px;
  background: rgba(0,0,0,0.12);
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  font-size: 11px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  color: inherit;
}
.card:hover .card-del { opacity: 1; }
.card-del:hover { background: rgba(0,0,0,0.26) !important; }
.card.loading { opacity: 0.45; pointer-events: none; }

/* COLOR CLASSES */
.cy { background: #F9E784; color: #3a3200; }
.co { background: #F4A86A; color: #3d1f00; }
.cg { background: #AEDBA4; color: #1a3a16; }
.cb { background: #A8D4F5; color: #0d2640; }
.cp { background: #E8B4D8; color: #3a1030; }
.cm { background: #F5F5F0; color: #2a2a28; outline: 1.5px solid rgba(0,0,0,0.08); }

/* EMPTY */
.empty {
  grid-column: 1/-1;
  text-align: center;
  padding: 56px 16px;
  color: #475569;
  font-size: 14px;
}

/* MODAL */
.modal-bg {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(10,15,26,0.72);
  z-index: 100;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(3px);
}
.modal-bg.open { display: flex; }

.modal {
  background: #1e2536;
  border-radius: 24px;
  padding: 28px;
  width: 320px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 24px 72px rgba(0,0,0,0.55);
  animation: popIn 0.22s cubic-bezier(.34,1.56,.64,1) both;
  border: 1px solid rgba(255,255,255,0.08);
}
.modal-title {
  font-size: 20px;
  font-weight: 700;
  color: #e0e6ed;
  margin-bottom: 2px;
}
.modal input,
.modal textarea,
.modal select {
  width: 100%;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1.5px solid rgba(255,255,255,0.12);
  font-size: 13px;
  font-family: inherit;
  background: rgba(255,255,255,0.06);
  color: #e0e6ed;
  resize: none;
  outline: none;
  transition: border-color 0.12s;
}
.modal input::placeholder,
.modal textarea::placeholder { color: #475569; }
.modal input:focus,
.modal textarea:focus,
.modal select:focus { border-color: #3b82f6; }
.modal select option { background: #1e2536; }
.modal textarea { height: 90px; line-height: 1.6; }

.label-sm {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #64748b;
  text-transform: uppercase;
  margin-bottom: -4px;
}

.color-row { display: flex; gap: 10px; }
.cswatch {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  cursor: pointer;
  border: 2.5px solid transparent;
  transition: transform 0.12s, border-color 0.12s;
  flex-shrink: 0;
}
.cswatch:hover { transform: scale(1.18); }
.cswatch.on { border-color: #e0e6ed; transform: scale(1.12); }

.modal-actions { display: flex; gap: 8px; margin-top: 4px; }
.btn-cancel {
  flex: 1;
  padding: 10px;
  border-radius: 12px;
  border: 1.5px solid rgba(255,255,255,0.12);
  background: transparent;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  color: #94a3b8;
  transition: background 0.1s;
}
.btn-cancel:hover { background: rgba(255,255,255,0.06); }
.btn-save {
  flex: 2;
  padding: 10px;
  border-radius: 12px;
  border: none;
  background: #3b82f6;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.12s;
}
.btn-save:hover { background: #2563eb; }
.btn-save:disabled { opacity: 0.5; cursor: default; background: #3b82f6; }

/* TOAST */
.toast {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(80px);
  background: #1e293b;
  color: #e0e6ed;
  padding: 9px 20px;
  border-radius: 999px;
  font-size: 13px;
  border: 1px solid rgba(255,255,255,0.1);
  transition: transform 0.3s ease, opacity 0.3s ease;
  z-index: 200;
  pointer-events: none;
  opacity: 0;
  white-space: nowrap;
}
.toast.show {
  transform: translateX(-50%) translateY(0);
  opacity: 1;
}
</style>
</head>
<body>

<div id="app">
  <div class="topbar">
    <div class="topbar-title">Mural</div>
    <div class="topbar-right">
      <span class="count-pill" id="count"></span>
      <button class="add-btn" onclick="openModal()" title="Novo recado">+</button>
    </div>
  </div>

  <div class="filters">
    <button class="ftag on" onclick="setFilter('all',this)">Todos</button>
    <button class="ftag" onclick="setFilter('aviso',this)">Aviso</button>
    <button class="ftag" onclick="setFilter('urgente',this)">Urgente</button>
    <button class="ftag" onclick="setFilter('lembrete',this)">Lembrete</button>
    <button class="ftag" onclick="setFilter('info',this)">Info</button>
  </div>

  <div class="grid" id="grid"></div>
</div>

<!-- Modal: novo recado -->
<div class="modal-bg" id="modal-bg">
  <div class="modal">
    <div class="modal-title">Novo recado</div>
    <input  id="f-author" placeholder="Seu nome" maxlength="24" />
    <textarea id="f-text" placeholder="Escreva sua mensagem…"></textarea>
    <div class="label-sm">Categoria</div>
    <select id="f-tag">
      <option value="aviso">Aviso</option>
      <option value="urgente">Urgente</option>
      <option value="lembrete">Lembrete</option>
      <option value="info">Info</option>
    </select>
    <div class="label-sm">Cor do post-it</div>
    <div class="color-row" id="color-row"></div>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeModal()">Cancelar</button>
      <button class="btn-save" id="btn-save" onclick="saveNote()">📌 Publicar</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
/* ── CONFIG ─────────────────────────────────────────────────── */
var TURSO_URL   = '__TURSO_URL__';
var TURSO_TOKEN = '__TURSO_TOKEN__';

var COLORS = [
  { key:'cy', hex:'#F9E784' },
  { key:'co', hex:'#F4A86A' },
  { key:'cg', hex:'#AEDBA4' },
  { key:'cb', hex:'#A8D4F5' },
  { key:'cp', hex:'#E8B4D8' },
  { key:'cm', hex:'#F5F5F0' },
];

var selColor    = 0;
var activeFilter = 'all';
var notes = __NOTES_JSON__;   /* injected by Python */

/* ── TURSO HTTP ─────────────────────────────────────────────── */
async function tursoExec(sql, args) {
  var mapped = (args || []).map(function(v) {
    return (v === null || v === undefined)
      ? { type: 'null' }
      : { type: 'text', value: String(v) };
  });
  var resp = await fetch(TURSO_URL + '/v2/pipeline', {
    method:  'POST',
    headers: {
      'Authorization': 'Bearer ' + TURSO_TOKEN,
      'Content-Type':  'application/json',
    },
    body: JSON.stringify({
      requests: [
        { type: 'execute', stmt: { sql: sql, args: mapped } },
        { type: 'close' },
      ],
    }),
  });
  if (!resp.ok) throw new Error('HTTP ' + resp.status);
  var d = await resp.json();
  if (d.results[0].type === 'error')
    throw new Error(d.results[0].error.message);
  return d.results[0].response.result;
}

/* ── HELPERS ─────────────────────────────────────────────────── */
function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

var _toastTimer = null;
function showToast(msg, ms) {
  var el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(function () { el.classList.remove('show'); }, ms || 2200);
}

/* ── RENDER ─────────────────────────────────────────────────── */
function renderSwatches() {
  document.getElementById('color-row').innerHTML = COLORS.map(function(c, i) {
    return '<div class="cswatch' + (i === selColor ? ' on' : '') +
           '" style="background:' + c.hex + '" onclick="pickColor(' + i + ')"></div>';
  }).join('');
}

function pickColor(i) { selColor = i; renderSwatches(); }

function renderGrid() {
  var grid = document.getElementById('grid');
  var filtered = (activeFilter === 'all')
    ? notes
    : notes.filter(function(n) { return n.tag === activeFilter; });

  var total = notes.length;
  document.getElementById('count').textContent =
    total + ' recado' + (total !== 1 ? 's' : '');

  if (!filtered.length) {
    grid.innerHTML = '<div class="empty">Nenhum recado aqui ainda 🌿</div>';
    return;
  }

  grid.innerHTML = filtered.map(function(n, idx) {
    var cKey = COLORS[n.cor % COLORS.length].key;
    return (
      '<div class="card ' + cKey + '" id="card-' + n.id + '"' +
      ' style="animation-delay:' + (idx * 0.04) + 's">' +
      '<button class="card-del" onclick="delNote(' + n.id + ')" title="Apagar recado">✕</button>' +
      '<div class="card-tag">'    + esc(n.tag)   + '</div>' +
      '<div class="card-text">'   + esc(n.texto) + '</div>' +
      '<div class="card-footer">' +
        '<span class="card-author">' + esc(n.autor) + '</span>' +
        '<span class="card-time">'   + esc(n.tempo) + '</span>' +
      '</div>' +
      '</div>'
    );
  }).join('');
}

/* ── FILTER ─────────────────────────────────────────────────── */
function setFilter(tag, btn) {
  activeFilter = tag;
  document.querySelectorAll('.ftag').forEach(function(b) {
    b.classList.remove('on');
  });
  btn.classList.add('on');
  renderGrid();
}

/* ── MODAL ─────────────────────────────────────────────────── */
function openModal() {
  document.getElementById('modal-bg').classList.add('open');
  renderSwatches();
  setTimeout(function() {
    document.getElementById('f-author').focus();
  }, 60);
}

function closeModal() {
  document.getElementById('modal-bg').classList.remove('open');
}

/* ── SAVE NOTE ─────────────────────────────────────────────── */
async function saveNote() {
  var autor = (document.getElementById('f-author').value || '').trim() || 'Anônimo';
  var texto = (document.getElementById('f-text').value  || '').trim();
  var tag   =  document.getElementById('f-tag').value;

  if (!texto) {
    document.getElementById('f-text').focus();
    return;
  }

  var btn = document.getElementById('btn-save');
  btn.disabled    = true;
  btn.textContent = 'Salvando…';

  try {
    var result = await tursoExec(
      'INSERT INTO mural_recados (autor, texto, tag, cor) VALUES (?, ?, ?, ?)',
      [autor, texto, tag, selColor]
    );
    var newId = parseInt(result.last_insert_rowid || Date.now(), 10);
    notes.unshift({
      id:    newId,
      autor: autor,
      texto: texto,
      tag:   tag,
      cor:   selColor,
      tempo: 'agora',
    });
    document.getElementById('f-text').value   = '';
    document.getElementById('f-author').value = '';
    selColor = 0;
    closeModal();
    renderGrid();
    showToast('📌 Recado publicado!');
  } catch (e) {
    showToast('Erro ao salvar: ' + e.message, 3500);
  } finally {
    btn.disabled    = false;
    btn.textContent = '📌 Publicar';
  }
}

/* ── DELETE NOTE ─────────────────────────────────────────────── */
async function delNote(id) {
  var card = document.getElementById('card-' + id);
  if (card) card.classList.add('loading');
  try {
    await tursoExec('DELETE FROM mural_recados WHERE id=?', [id]);
    notes = notes.filter(function(n) { return n.id !== id; });
    renderGrid();
    showToast('🗑️ Recado removido.');
  } catch (e) {
    if (card) card.classList.remove('loading');
    showToast('Erro ao apagar: ' + e.message, 3500);
  }
}

/* ── CLOSE MODAL ON BG CLICK ─────────────────────────────────── */
document.getElementById('modal-bg').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

/* ── INIT ─────────────────────────────────────────────────────── */
renderGrid();
</script>
</body>
</html>
"""


def _safe_json(obj) -> str:
    return _json.dumps(obj, ensure_ascii=False, default=str)


def _fmt_tempo(dt_str: str) -> str:
    """Converte datetime armazenado para string relativa (ex.: 'há 2h')."""
    if not dt_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.strptime(str(dt_str)[:19], "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - dt
        mins = int(diff.total_seconds() / 60)
        if mins < 2:
            return "agora"
        if mins < 60:
            return f"há {mins}min"
        hours = mins // 60
        if hours < 24:
            return f"há {hours}h"
        days = hours // 24
        if days == 1:
            return "ontem"
        if days < 7:
            return f"há {days} dias"
        return dt.strftime("%d/%m/%y")
    except Exception:
        return str(dt_str)[:10]


def mural_tab(turso_url: str, turso_token: str, rows: list) -> None:
    """Renderiza a aba Mural.

    Args:
        turso_url:   URL do banco Turso (libsql://...).
        turso_token: Token de autenticação Turso.
        rows:        Lista de tuplas (id, autor, texto, tag, cor, criado_em)
                     carregadas pelo Python antes da renderização.
    """
    http_url = (turso_url or "").replace("libsql://", "https://").rstrip("/")

    notes = [
        {
            "id":    int(r[0]),
            "autor": str(r[1] or "Anônimo"),
            "texto": str(r[2] or ""),
            "tag":   str(r[3] or "aviso"),
            "cor":   int(r[4] or 0),
            "tempo": _fmt_tempo(str(r[5] or "")),
        }
        for r in rows
    ]

    html = (
        _HTML
        .replace("__NOTES_JSON__",  _safe_json(notes))
        .replace("__TURSO_URL__",   http_url)
        .replace("__TURSO_TOKEN__", turso_token or "")
    )

    _components.html(html, height=760, scrolling=True)
