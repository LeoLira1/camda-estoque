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

:root {
  --text-main: #e5edf7;
  --text-muted: #94a3b8;
  --ink-dark: rgba(15, 23, 42, 0.86);
  --line-soft: rgba(255,255,255,0.13);
  --surface-soft: rgba(255,255,255,0.055);
  --surface-strong: rgba(255,255,255,0.095);
  --brand: #3b82f6;
  --brand-strong: #2563eb;
}

body {
  font-family: Inter, ui-sans-serif, -apple-system, 'Segoe UI', system-ui, sans-serif;
  background: transparent;
  padding: 4px 2px 18px;
}

button, input, textarea, select { font: inherit; }
button { -webkit-tap-highlight-color: transparent; }

/* TOPBAR */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 0 18px;
}

.topbar-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.topbar-title {
  font-size: clamp(26px, 3vw, 34px);
  font-weight: 850;
  color: var(--text-main);
  letter-spacing: -0.8px;
  line-height: 1.05;
}

.topbar-subtitle {
  color: #64748b;
  font-size: 12px;
  letter-spacing: 0.2px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.count-pill {
  font-size: 12px;
  color: #cbd5e1;
  background: linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.06));
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  padding: 6px 14px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.09), 0 10px 24px rgba(0,0,0,0.12);
}

.add-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: radial-gradient(circle at 32% 22%, #7db3ff 0, var(--brand) 45%, var(--brand-strong) 100%);
  border: 1px solid rgba(255,255,255,0.18);
  color: #fff;
  font-size: 25px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: transform 0.16s ease, filter 0.16s ease, box-shadow 0.16s ease;
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.34), inset 0 1px 0 rgba(255,255,255,0.28);
  flex-shrink: 0;
}
.add-btn:hover {
  transform: translateY(-2px) scale(1.06) rotate(4deg);
  filter: brightness(1.08);
  box-shadow: 0 18px 34px rgba(37, 99, 235, 0.42), inset 0 1px 0 rgba(255,255,255,0.30);
}
.add-btn:active { transform: translateY(0) scale(0.98); }

/* FILTERS */
.filters-wrap {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 0 0 22px;
}

.filters {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}

.ftag {
  font-size: 11px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: rgba(15,23,42,0.20);
  color: var(--text-muted);
  cursor: pointer;
  transition: transform 0.13s ease, background 0.13s ease, color 0.13s ease, border-color 0.13s ease, box-shadow 0.13s ease;
}
.ftag:hover {
  transform: translateY(-1px);
  color: #dbeafe;
  background: rgba(255,255,255,0.075);
  border-color: rgba(255,255,255,0.22);
}
.ftag.on {
  background: #e5edf7;
  color: #0a0f1a;
  border-color: #e5edf7;
  box-shadow: 0 12px 28px rgba(148,163,184,0.18);
}

/* GRID */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
  gap: 18px;
  align-items: stretch;
  perspective: 1100px;
}

/* CARD */
.card {
  border-radius: 23px 23px 28px 23px;
  padding: 24px 19px 17px;
  min-height: 190px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  cursor: default;
  isolation: isolate;
  transform-origin: 50% 45%;
  transition: transform 0.22s cubic-bezier(.34,1.56,.64,1), box-shadow 0.22s ease, filter 0.22s ease;
  box-shadow:
    0 22px 44px rgba(0,0,0,0.25),
    0 3px 8px rgba(0,0,0,0.18),
    inset 0 1px 0 rgba(255,255,255,0.36);
  animation: popIn 0.34s cubic-bezier(.34,1.56,.64,1) both;
}

.card::before {
  content: '';
  position: absolute;
  top: 8px;
  left: 50%;
  width: 64px;
  height: 18px;
  border-radius: 4px;
  transform: translateX(-50%) rotate(-2deg);
  background: linear-gradient(90deg, rgba(255,255,255,0.36), rgba(255,255,255,0.18));
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  mix-blend-mode: soft-light;
  pointer-events: none;
  z-index: 2;
}

.card::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: 0;
  width: 54px;
  height: 54px;
  border-top-left-radius: 22px;
  background: linear-gradient(135deg, rgba(255,255,255,0.36), rgba(0,0,0,0.10));
  clip-path: polygon(100% 0, 100% 100%, 0 100%);
  opacity: 0.42;
  pointer-events: none;
}

.card:hover {
  transform: translateY(-7px) rotate(-0.7deg) scale(1.012);
  filter: saturate(1.04);
  box-shadow:
    0 28px 58px rgba(0,0,0,0.34),
    0 8px 20px rgba(0,0,0,0.16),
    inset 0 1px 0 rgba(255,255,255,0.38);
  z-index: 3;
}

@keyframes popIn {
  from { opacity: 0; transform: scale(0.88) rotate(-1.6deg) translateY(14px); }
  to   { opacity: 1; transform: scale(1) rotate(0deg) translateY(0); }
}

.card-tag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 11px;
  min-height: 18px;
}

.card-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1px;
  text-transform: uppercase;
  opacity: 0.62;
}

.card-tag-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.55;
}

.card-text {
  font-size: 14px;
  line-height: 1.63;
  flex: 1;
  word-break: break-word;
  white-space: pre-wrap;
  letter-spacing: -0.05px;
}

.card-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-top: 18px;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.card-author-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.avatar {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.13);
  border: 1px solid rgba(255,255,255,0.18);
  font-size: 11px;
  font-weight: 900;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.20);
}

.card-author {
  font-size: 11px;
  font-weight: 800;
  opacity: 0.56;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-time {
  font-size: 10px;
  opacity: 0.38;
  white-space: nowrap;
}
.card-time.old { opacity: 0.58; font-weight: 750; }

.card-del {
  position: absolute;
  top: 13px;
  right: 14px;
  background: rgba(0,0,0,0.12);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 50%;
  width: 26px;
  height: 26px;
  font-size: 11px;
  cursor: pointer;
  opacity: 0;
  transform: scale(0.92);
  transition: opacity 0.15s ease, transform 0.15s ease, background 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  color: inherit;
  z-index: 4;
}
.card:hover .card-del { opacity: 1; transform: scale(1); }
.card-del:hover { background: rgba(0,0,0,0.26) !important; }
.card.loading { opacity: 0.45; pointer-events: none; }

/* IMAGEM no card */
.card-img {
  display: block;
  width: calc(100% + 38px);
  margin: 12px -19px 0;
  max-height: 220px;
  object-fit: cover;
  cursor: zoom-in;
}

/* Botão + / × discreto no rodapé do card */
.card-img-btn {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid rgba(0,0,0,0.22);
  background: rgba(255,255,255,0.5);
  color: rgba(0,0,0,0.55);
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.12s ease, color 0.12s ease, transform 0.12s ease;
}
.card-img-btn:hover {
  background: rgba(255,255,255,0.85);
  color: rgba(0,0,0,0.8);
  transform: scale(1.10);
}
.card-img-btn input[type="file"] { display: none; }

.card-time-wrap {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
}

/* Lightbox simples */
.lightbox {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.86);
  z-index: 150;
  align-items: center;
  justify-content: center;
  padding: 24px;
  cursor: zoom-out;
}
.lightbox.open { display: flex; }
.lightbox img {
  max-width: 95%;
  max-height: 95%;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);
}

/* Preview no modal */
.modal-img-preview {
  width: 100%;
  max-height: 160px;
  object-fit: cover;
  border-radius: 12px;
  display: none;
}
.modal-img-preview.show { display: block; }

.btn-attach {
  padding: 9px 12px;
  border-radius: 12px;
  border: 1px dashed rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
}
.btn-attach:hover {
  background: rgba(255,255,255,0.08);
  color: #cbd5e1;
  border-color: rgba(255,255,255,0.26);
}
.btn-attach input[type="file"] { display: none; }

.card.urgent-note {
  box-shadow:
    0 24px 50px rgba(244, 168, 106, 0.18),
    0 22px 44px rgba(0,0,0,0.25),
    inset 0 1px 0 rgba(255,255,255,0.36);
}
.card.urgent-note .card-tag { opacity: 0.82; }

/* COLOR CLASSES */
.cy { background: linear-gradient(145deg, #FFF2A1 0%, #F9E784 52%, #F1D764 100%); color: #3a3200; }
.co { background: linear-gradient(145deg, #FFC184 0%, #F4A86A 54%, #E58F48 100%); color: #3d1f00; }
.cg { background: linear-gradient(145deg, #C8F0BD 0%, #AEDBA4 56%, #8ECF85 100%); color: #163915; }
.cb { background: linear-gradient(145deg, #C5E6FF 0%, #A8D4F5 56%, #86BFEA 100%); color: #0d2640; }
.cp { background: linear-gradient(145deg, #F7CBEA 0%, #E8B4D8 56%, #D895C8 100%); color: #3a1030; }
.cm { background: linear-gradient(145deg, #FFFFFF 0%, #F5F5F0 55%, #E4E4DC 100%); color: #2a2a28; outline: 1px solid rgba(0,0,0,0.08); }

/* EMPTY */
.empty {
  grid-column: 1/-1;
  text-align: center;
  padding: 58px 18px;
  color: #64748b;
  font-size: 14px;
  border: 1px dashed rgba(148,163,184,0.24);
  border-radius: 22px;
  background: rgba(255,255,255,0.025);
}
.empty strong { color: #cbd5e1; }

/* MODAL */
.modal-bg {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(10,15,26,0.74);
  z-index: 100;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(7px);
}
.modal-bg.open { display: flex; }

.modal {
  background: linear-gradient(180deg, rgba(31,41,59,0.97), rgba(15,23,42,0.98));
  border-radius: 26px;
  padding: 28px;
  width: 340px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 28px 86px rgba(0,0,0,0.58), inset 0 1px 0 rgba(255,255,255,0.08);
  animation: modalIn 0.24s cubic-bezier(.34,1.56,.64,1) both;
  border: 1px solid rgba(255,255,255,0.10);
}
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.92) translateY(12px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
.modal-title {
  font-size: 21px;
  font-weight: 850;
  color: var(--text-main);
  letter-spacing: -0.4px;
  margin-bottom: 2px;
}
.modal input,
.modal textarea,
.modal select {
  width: 100%;
  padding: 11px 14px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.13);
  font-size: 13px;
  background: rgba(255,255,255,0.065);
  color: var(--text-main);
  resize: none;
  outline: none;
  transition: border-color 0.12s ease, background 0.12s ease, box-shadow 0.12s ease;
}
.modal input::placeholder,
.modal textarea::placeholder { color: #64748b; }
.modal input:focus,
.modal textarea:focus,
.modal select:focus {
  border-color: rgba(59,130,246,0.78);
  background: rgba(255,255,255,0.085);
  box-shadow: 0 0 0 4px rgba(59,130,246,0.12);
}
.modal select option { background: #1e2536; }
.modal textarea { height: 98px; line-height: 1.55; }

.label-sm {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.7px;
  color: #64748b;
  text-transform: uppercase;
  margin-bottom: -4px;
}

.color-row { display: flex; gap: 10px; flex-wrap: wrap; }
.cswatch {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.38), 0 8px 16px rgba(0,0,0,0.16);
}
.cswatch:hover { transform: translateY(-2px) scale(1.10); }
.cswatch.on { border-color: #e0e6ed; transform: scale(1.10); box-shadow: 0 0 0 4px rgba(255,255,255,0.10), inset 0 1px 0 rgba(255,255,255,0.42); }

.modal-actions { display: flex; gap: 9px; margin-top: 4px; }
.btn-cancel {
  flex: 1;
  padding: 11px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.13);
  background: transparent;
  font-size: 13px;
  cursor: pointer;
  color: #94a3b8;
  transition: background 0.1s ease, transform 0.1s ease;
}
.btn-cancel:hover { background: rgba(255,255,255,0.06); transform: translateY(-1px); }
.btn-save {
  flex: 2;
  padding: 11px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(180deg, #4f94ff, var(--brand-strong));
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: filter 0.12s ease, transform 0.12s ease, box-shadow 0.12s ease;
  box-shadow: 0 14px 24px rgba(37,99,235,0.26), inset 0 1px 0 rgba(255,255,255,0.20);
}
.btn-save:hover { filter: brightness(1.07); transform: translateY(-1px); }
.btn-save:disabled { opacity: 0.56; cursor: default; transform: none; filter: none; }

/* TOAST */
.toast {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(80px);
  background: rgba(15,23,42,0.94);
  color: var(--text-main);
  padding: 10px 20px;
  border-radius: 999px;
  font-size: 13px;
  border: 1px solid rgba(255,255,255,0.12);
  transition: transform 0.3s ease, opacity 0.3s ease;
  z-index: 200;
  pointer-events: none;
  opacity: 0;
  white-space: nowrap;
  box-shadow: 0 14px 36px rgba(0,0,0,0.30);
}
.toast.show {
  transform: translateX(-50%) translateY(0);
  opacity: 1;
}

@media (max-width: 640px) {
  .topbar { align-items: flex-start; }
  .topbar-subtitle { display: none; }
  .count-pill { display: none; }
  .grid { grid-template-columns: 1fr; gap: 14px; }
  .card { min-height: 168px; }
}
</style>
</head>
<body>

<div id="app">
  <div class="topbar">
    <div class="topbar-title-wrap">
      <div class="topbar-title">Mural</div>
      <div class="topbar-subtitle">Recados rápidos da equipe, com prioridade visual.</div>
    </div>
    <div class="topbar-right">
      <span class="count-pill" id="count"></span>
      <button class="add-btn" onclick="openModal()" title="Novo recado">+</button>
    </div>
  </div>

  <div class="filters-wrap">
    <div class="filters">
      <button class="ftag on" onclick="setFilter('all',this)">Todos</button>
      <button class="ftag" onclick="setFilter('aviso',this)">Aviso</button>
      <button class="ftag" onclick="setFilter('urgente',this)">Urgente</button>
      <button class="ftag" onclick="setFilter('lembrete',this)">Lembrete</button>
      <button class="ftag" onclick="setFilter('info',this)">Info</button>
    </div>
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
    <img class="modal-img-preview" id="f-img-preview" alt="" />
    <label class="btn-attach" id="f-img-label">
      📎 Anexar foto (opcional)
      <input type="file" id="f-img" accept="image/*" onchange="onModalImagePicked(event)" />
    </label>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeModal()">Cancelar</button>
      <button class="btn-save" id="btn-save" onclick="saveNote()">📌 Publicar</button>
    </div>
  </div>
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()"><img id="lightbox-img" alt="" /></div>

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

var TAG_META = {
  aviso:    { label: 'Aviso',    icon: '●' },
  urgente:  { label: 'Urgente',  icon: '●' },
  lembrete: { label: 'Lembrete', icon: '●' },
  info:     { label: 'Info',     icon: '●' },
};

var selColor     = 0;
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
  if (d.results[0].type === 'error') {
    throw new Error(d.results[0].error.message);
  }
  return d.results[0].response.result;
}

/* ── HELPERS ─────────────────────────────────────────────────── */
function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/\"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function authorInitial(name) {
  var clean = String(name || 'A').trim();
  return (clean[0] || 'A').toUpperCase();
}

function isOldTimeLabel(label) {
  return /^há\s+\d+\s+dias$/.test(label || '') || /^\d{2}\/\d{2}/.test(label || '') || label === 'ontem';
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
           '" style="background:' + c.hex + '" onclick="pickColor(' + i + ')" title="Cor ' + (i + 1) + '"></div>';
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
    grid.innerHTML = '<div class="empty"><strong>Nenhum recado por aqui.</strong><br>Use o botão + para fixar o próximo lembrete 🌿</div>';
    return;
  }

  grid.innerHTML = filtered.map(function(n, idx) {
    var cKey = COLORS[Math.abs(Number(n.cor || 0)) % COLORS.length].key;
    var meta = TAG_META[n.tag] || { label: n.tag || 'Aviso', icon: '●' };
    var urgentClass = n.tag === 'urgente' ? ' urgent-note' : '';
    var timeClass = isOldTimeLabel(n.tempo) ? ' old' : '';
    var hasImg = !!n.imagem;
    var imgHtml = hasImg
      ? '<img class="card-img" src="data:image/jpeg;base64,' + n.imagem + '" onclick="openLightbox(\'' + n.id + '\')" alt="" />'
      : '';
    var imgBtn = hasImg
      ? '<button class="card-img-btn" onclick="removeImage(' + n.id + ')" title="Remover foto">×</button>'
      : '<label class="card-img-btn" title="Adicionar foto">+' +
          '<input type="file" accept="image/*" onchange="uploadImage(event,' + n.id + ')" />' +
        '</label>';
    return (
      '<div class="card ' + cKey + urgentClass + '" id="card-' + n.id + '" data-tag="' + esc(n.tag) + '"' +
      ' style="animation-delay:' + (idx * 0.045) + 's">' +
      '<button class="card-del" onclick="delNote(' + n.id + ')" title="Apagar recado">✕</button>' +
      '<div class="card-tag-row">' +
        '<div class="card-tag"><span class="card-tag-dot"></span>' + esc(meta.label) + '</div>' +
      '</div>' +
      '<div class="card-text">'   + esc(n.texto) + '</div>' +
      imgHtml +
      '<div class="card-footer">' +
        '<div class="card-author-wrap">' +
          '<span class="avatar">' + esc(authorInitial(n.autor)) + '</span>' +
          '<span class="card-author">' + esc(n.autor) + '</span>' +
        '</div>' +
        '<span class="card-time-wrap">' +
          '<span class="card-time' + timeClass + '">' + esc(n.tempo) + '</span>' +
          imgBtn +
        '</span>' +
      '</div>' +
      '</div>'
    );
  }).join('');
}

/* ── IMAGE COMPRESSION (browser, via Canvas) ─────────────────── */
function compressImageFile(file, maxSize, quality) {
  maxSize = maxSize || 800;
  quality = quality || 0.6;
  return new Promise(function(resolve, reject) {
    if (!file) return resolve(null);
    var reader = new FileReader();
    reader.onerror = function() { reject(new Error('Falha ao ler arquivo')); };
    reader.onload = function(e) {
      var img = new Image();
      img.onerror = function() { reject(new Error('Imagem inválida')); };
      img.onload = function() {
        var w = img.width, h = img.height;
        if (w > h && w > maxSize) { h = Math.round(h * maxSize / w); w = maxSize; }
        else if (h > maxSize)     { w = Math.round(w * maxSize / h); h = maxSize; }
        var canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        var dataUrl = canvas.toDataURL('image/jpeg', quality);
        resolve(dataUrl.split(',')[1] || '');
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

/* ── UPLOAD / REMOVE IMAGE ───────────────────────────────────── */
async function uploadImage(ev, id) {
  var file = ev.target.files && ev.target.files[0];
  if (!file) return;
  var card = document.getElementById('card-' + id);
  if (card) card.classList.add('loading');
  try {
    var b64 = await compressImageFile(file, 800, 0.6);
    await tursoExec('UPDATE mural_recados SET imagem=? WHERE id=?', [b64, id]);
    var n = notes.find(function(x) { return x.id === id; });
    if (n) n.imagem = b64;
    renderGrid();
    showToast('🖼️ Foto anexada!');
  } catch (e) {
    if (card) card.classList.remove('loading');
    showToast('Erro ao anexar: ' + e.message, 3500);
  }
}

async function removeImage(id) {
  var card = document.getElementById('card-' + id);
  if (card) card.classList.add('loading');
  try {
    await tursoExec('UPDATE mural_recados SET imagem=NULL WHERE id=?', [id]);
    var n = notes.find(function(x) { return x.id === id; });
    if (n) n.imagem = null;
    renderGrid();
    showToast('🗑️ Foto removida.');
  } catch (e) {
    if (card) card.classList.remove('loading');
    showToast('Erro ao remover foto: ' + e.message, 3500);
  }
}

/* ── LIGHTBOX ───────────────────────────────────────────────── */
function openLightbox(id) {
  var n = notes.find(function(x) { return x.id === Number(id); });
  if (!n || !n.imagem) return;
  document.getElementById('lightbox-img').src = 'data:image/jpeg;base64,' + n.imagem;
  document.getElementById('lightbox').classList.add('open');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
}

/* ── MODAL: preview da imagem antes de publicar ──────────────── */
var _modalImgB64 = null;
async function onModalImagePicked(ev) {
  var file = ev.target.files && ev.target.files[0];
  if (!file) { _modalImgB64 = null; return; }
  try {
    _modalImgB64 = await compressImageFile(file, 800, 0.6);
    var preview = document.getElementById('f-img-preview');
    preview.src = 'data:image/jpeg;base64,' + _modalImgB64;
    preview.classList.add('show');
    document.getElementById('f-img-label').textContent = '✓ Foto anexada (clique para trocar)';
    var input = document.createElement('input');
    input.type = 'file'; input.id = 'f-img'; input.accept = 'image/*';
    input.onchange = onModalImagePicked;
    document.getElementById('f-img-label').appendChild(input);
  } catch (e) {
    showToast('Erro ao processar imagem: ' + e.message, 3500);
  }
}
function resetModalImage() {
  _modalImgB64 = null;
  var preview = document.getElementById('f-img-preview');
  preview.src = ''; preview.classList.remove('show');
  document.getElementById('f-img-label').innerHTML =
    '📎 Anexar foto (opcional)<input type="file" id="f-img" accept="image/*" onchange="onModalImagePicked(event)" />';
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
  resetModalImage();
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
      'INSERT INTO mural_recados (autor, texto, tag, cor, imagem) VALUES (?, ?, ?, ?, ?)',
      [autor, texto, tag, selColor, _modalImgB64]
    );
    var newId = parseInt(result.last_insert_rowid || Date.now(), 10);
    notes.unshift({
      id:     newId,
      autor:  autor,
      texto:  texto,
      tag:    tag,
      cor:    selColor,
      tempo:  'agora',
      imagem: _modalImgB64,
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

/* ── CLOSE MODAL ON BG CLICK / ESC ───────────────────────────── */
document.getElementById('modal-bg').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') { closeModal(); closeLightbox(); }
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
            "id":     int(r[0]),
            "autor":  str(r[1] or "Anônimo"),
            "texto":  str(r[2] or ""),
            "tag":    str(r[3] or "aviso"),
            "cor":    int(r[4] or 0),
            "tempo":  _fmt_tempo(str(r[5] or "")),
            "imagem": (r[6] if len(r) > 6 and r[6] else None),
        }
        for r in rows
    ]

    html = (
        _HTML
        .replace("__NOTES_JSON__",  _safe_json(notes))
        .replace("__TURSO_URL__",   http_url)
        .replace("__TURSO_TOKEN__", turso_token or "")
    )

    _components.html(html, height=820, scrolling=True)
