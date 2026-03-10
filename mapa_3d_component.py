"""
mapa_3d_component.py — Componente 3D do Mapa Visual do Armazém CAMDA.

Renderiza um rack 3D usando Three.js via st.components.v1.html().
Não requer build step — funciona direto no Streamlit Cloud.

Comunicação com Streamlit:
  - Click numa célula → injeta pos_key num input oculto (placeholder __rack_3d_click__)
  - Hover → tooltip inline no iframe (sem comunicação com Python)
"""

import json
import streamlit.components.v1 as components


def render_rack_3d(
    paletes: dict,
    produtos: list,
    rack_id: str,
    face: str,
    height: int = 580,
    highlight_keys=None,
) -> None:
    """
    Renderiza o rack 3D via st.components.v1.html().

    paletes        : {pos_key: {produto, quantidade, unidade, cor / cor_hex}}
    produtos       : [{nome, unidade_pad, cor_hex}]  (não usado na renderização, reservado)
    rack_id        : ex. "R1"
    face           : "A" ou "B"
    height         : altura do componente em pixels
    highlight_keys : iterable de pos_keys a iluminar (busca)
    """
    hl_list = list(highlight_keys or [])

    # Normaliza chave de cor (campo pode ser 'cor' ou 'cor_hex')
    paletes_norm: dict = {}
    for k, v in paletes.items():
        paletes_norm[k] = {
            "produto":    v.get("produto", ""),
            "quantidade": v.get("quantidade"),
            "unidade":    v.get("unidade", ""),
            "cor_hex":    v.get("cor_hex") or v.get("cor") or "#4ade80",
        }

    html_str = _build_html(paletes_norm, rack_id, face, hl_list, height)
    components.html(html_str, height=height + 40, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# HTML + Three.js builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(
    paletes: dict,
    rack_id: str,
    face: str,
    hl_keys: list,
    height: int,
) -> str:
    p_json  = json.dumps(paletes,  ensure_ascii=False)
    hl_json = json.dumps(hl_keys,  ensure_ascii=False)

    # CSS for the container and tooltip
    css = f"""
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0f172a; overflow: hidden; }}
#rc {{
  width: 100%;
  height: {height}px;
  position: relative;
  overflow: hidden;
  background: #0f172a;
}}
canvas {{
  display: block;
  width: 100% !important;
  height: {height}px !important;
}}
#tt {{
  position: absolute;
  display: none;
  background: rgba(15,23,42,0.94);
  border: 1px solid #1d4ed8;
  border-radius: 6px;
  padding: 7px 11px;
  pointer-events: none;
  font-family: 'Courier New', monospace;
  max-width: 220px;
  z-index: 100;
  line-height: 1.5;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}}
#info {{
  position: absolute;
  top: 8px;
  left: 8px;
  color: #475569;
  font-family: monospace;
  font-size: 0.62rem;
  background: rgba(15,23,42,0.75);
  padding: 4px 9px;
  border-radius: 4px;
  pointer-events: none;
  line-height: 1.6;
}}
#label-rack {{
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  color: #334155;
  font-family: monospace;
  font-size: 0.7rem;
  background: rgba(15,23,42,0.7);
  padding: 3px 10px;
  border-radius: 4px;
  pointer-events: none;
  letter-spacing: 0.05em;
}}
</style>
"""

    # The HTML template injects Python-side data, then appends Three.js logic
    html_top = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{css}
</head>
<body>
<div id="rc">
  <canvas id="cvs"></canvas>
  <div id="tt"></div>
  <div id="info">🖱 Arrastar: rotacionar &nbsp;·&nbsp; Scroll: zoom &nbsp;·&nbsp; Toque: rotacionar</div>
  <div id="label-rack">Rack {rack_id} &mdash; Face {face}</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
/* ── Dados injetados pelo Python ─────────────────────────────── */
const PALETES        = {p_json};
const RACK_ID        = "{rack_id}";
const FACE           = "{face}";
const COLUNAS        = 13;
const NIVEIS         = 4;
const HIGHLIGHT_KEYS = {hl_json};
const HEIGHT_PX      = {height};
</script>
<script>
"""

    html_bottom = """
</script>
</body>
</html>
"""

    return html_top + _THREE_JS_CODE + html_bottom


# ─────────────────────────────────────────────────────────────────────────────
# Three.js vanilla JS — converte toda a lógica 3D do rack
# ─────────────────────────────────────────────────────────────────────────────

_THREE_JS_CODE = r"""
(function () {
  'use strict';

  /* ── Constantes geométricas ──────────────────────────────────── */
  var CELL_W   = 1.40;   // largura de célula (eixo X)
  var CELL_H   = 1.50;   // altura de célula (eixo Y)
  var CELL_D   = 1.20;   // profundidade da célula (eixo Z)
  var POST_W   = 0.068;  // espessura dos postes
  var BEAM_H   = 0.055;  // espessura das travessas
  var PALLET_H = 0.11;   // altura do pallet de madeira
  var BOX_W    = CELL_W * 0.82;
  var BOX_H    = CELL_H * 0.70;
  var BOX_D    = CELL_D * 0.80;
  var RACK_W   = COLUNAS * CELL_W;
  var RACK_H   = NIVEIS  * CELL_H;
  var CX       = RACK_W  / 2;   // centro X do rack
  var CY       = RACK_H  / 2;   // centro Y do rack
  var CZ       = -CELL_D / 2;   // centro Z do rack

  /* ── Renderer ────────────────────────────────────────────────── */
  var container = document.getElementById('rc');
  var canvas    = document.getElementById('cvs');
  var W = container.clientWidth  || 800;
  var H = HEIGHT_PX;

  var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(W, H);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type    = THREE.PCFSoftShadowMap;

  /* ── Cena ────────────────────────────────────────────────────── */
  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0f172a);
  scene.fog = new THREE.FogExp2(0x0f172a, 0.022);

  /* ── Câmera ──────────────────────────────────────────────────── */
  var camera = new THREE.PerspectiveCamera(44, W / H, 0.1, 200);

  /* ── Iluminação ──────────────────────────────────────────────── */
  scene.add(new THREE.AmbientLight(0x405070, 1.1));

  var sun = new THREE.DirectionalLight(0xffffff, 0.95);
  sun.position.set(14, 20, 12);
  sun.castShadow = true;
  sun.shadow.mapSize.width  = 2048;
  sun.shadow.mapSize.height = 2048;
  sun.shadow.camera.near   = 0.5;
  sun.shadow.camera.far    = 80;
  sun.shadow.camera.left   = -25;
  sun.shadow.camera.right  =  25;
  sun.shadow.camera.top    =  20;
  sun.shadow.camera.bottom =  -5;
  sun.shadow.bias          = -0.001;
  scene.add(sun);

  var fill = new THREE.DirectionalLight(0x8090c0, 0.35);
  fill.position.set(-10, 8, -8);
  scene.add(fill);

  /* ── Chão e grid ─────────────────────────────────────────────── */
  var floor = new THREE.Mesh(
    new THREE.PlaneGeometry(80, 50),
    new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.9, metalness: 0.05 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.01;
  floor.receiveShadow = true;
  scene.add(floor);
  scene.add(new THREE.GridHelper(80, 80, 0x1e3a5a, 0x172030));

  /* ── Materiais reutilizáveis ─────────────────────────────────── */
  var matPost   = new THREE.MeshStandardMaterial({ color: 0x9ca3af, metalness: 0.85, roughness: 0.25 });
  var matBeam   = new THREE.MeshStandardMaterial({ color: 0x6b7280, metalness: 0.75, roughness: 0.35 });
  var matPallet = new THREE.MeshStandardMaterial({ color: 0x7c4e1a, roughness: 0.92, metalness: 0.0 });
  var matGhost  = new THREE.MeshStandardMaterial({
    color: 0x1e3a5a, transparent: true, opacity: 0.15, depthWrite: false
  });
  var matWrap   = new THREE.MeshStandardMaterial({
    color: 0xd0e8ff, transparent: true, opacity: 0.065, depthWrite: false
  });

  /* ── Geometrias reutilizáveis ────────────────────────────────── */
  var geoPost   = new THREE.BoxGeometry(POST_W, RACK_H + 0.55, POST_W);
  var geoBeamFB = new THREE.BoxGeometry(RACK_W + POST_W, BEAM_H, POST_W);
  var geoPallet = new THREE.BoxGeometry(BOX_W, PALLET_H, BOX_D);
  var geoBox    = new THREE.BoxGeometry(BOX_W, BOX_H, BOX_D);
  var geoWrap   = new THREE.BoxGeometry(BOX_W * 1.04, BOX_H * 1.05, BOX_D * 1.04);
  var geoGhost  = new THREE.BoxGeometry(BOX_W * 0.70, (BOX_H + PALLET_H) * 0.70, BOX_D * 0.70);

  /* ── Estrutura metálica do rack ──────────────────────────────── */
  // Postes verticais em cada divisão de coluna (frente e fundo)
  for (var c = 0; c <= COLUNAS; c++) {
    var px = c * CELL_W;
    var ph = (RACK_H + 0.55) / 2;
    [[px, ph, 0], [px, ph, -CELL_D]].forEach(function (pos) {
      var m = new THREE.Mesh(geoPost, matPost);
      m.position.set(pos[0], pos[1], pos[2]);
      m.castShadow = true;
      scene.add(m);
    });
  }
  // Travessas horizontais em cada nível (frente e fundo)
  for (var n = 0; n <= NIVEIS; n++) {
    var by = n * CELL_H;
    [[RACK_W / 2, by, 0], [RACK_W / 2, by, -CELL_D]].forEach(function (pos) {
      var m = new THREE.Mesh(geoBeamFB, matBeam);
      m.position.set(pos[0], pos[1], pos[2]);
      scene.add(m);
    });
  }
  // Travessas transversais (lado a lado) nas extremidades — decorativas
  var geoBeamSide = new THREE.BoxGeometry(POST_W, BEAM_H, CELL_D);
  for (var n = 0; n <= NIVEIS; n++) {
    var by = n * CELL_H;
    [0, RACK_W].forEach(function (x) {
      var m = new THREE.Mesh(geoBeamSide, matBeam);
      m.position.set(x, by, -CELL_D / 2);
      scene.add(m);
    });
  }

  /* ── Paletes e caixas ────────────────────────────────────────── */
  var clickables  = [];  // meshes para raycasting
  var meshByKey   = {};  // pos_key → mesh principal

  for (var col = 1; col <= COLUNAS; col++) {
    for (var nivel = 1; nivel <= NIVEIS; nivel++) {
      var pos_key = RACK_ID + '-' + FACE + '-C' + col + '-N' + nivel;
      var cx  = (col - 0.5) * CELL_W;
      var by  = (nivel - 1) * CELL_H;
      var czz = CZ;

      var palete = PALETES[pos_key];
      var isHL   = HIGHLIGHT_KEYS.indexOf(pos_key) !== -1;

      if (palete && palete.produto) {
        /* Pallet de madeira */
        var pm = new THREE.Mesh(geoPallet, matPallet);
        pm.position.set(cx, by + PALLET_H / 2, czz);
        pm.castShadow    = true;
        pm.receiveShadow = true;
        scene.add(pm);

        /* Caixa do produto */
        var hexStr  = (palete.cor_hex || '#4ade80').replace('#', '');
        var hexCol  = parseInt(hexStr, 16);
        var emColor = isHL ? 0xfbbf24 : 0x000000;
        var emInt   = isHL ? 0.65      : 0.0;
        var boxMat  = new THREE.MeshStandardMaterial({
          color:             new THREE.Color(hexCol),
          roughness:         0.60,
          metalness:         0.08,
          emissive:          new THREE.Color(emColor),
          emissiveIntensity: emInt,
        });
        var bm = new THREE.Mesh(geoBox, boxMat);
        bm.position.set(cx, by + PALLET_H + BOX_H / 2, czz);
        bm.castShadow = true;
        bm.userData = {
          pos_key:       pos_key,
          produto:       palete.produto,
          quantidade:    palete.quantidade,
          unidade:       palete.unidade || '',
          isHighlighted: isHL,
          isEmpty:       false,
          origEmissive:  emColor,
          origEmInt:     emInt,
        };
        scene.add(bm);
        clickables.push(bm);
        meshByKey[pos_key] = bm;

        /* Filme plástico semi-transparente */
        var wm = new THREE.Mesh(geoWrap, matWrap);
        wm.position.copy(bm.position);
        scene.add(wm);

      } else {
        /* Placeholder fantasma (célula vazia) */
        var gm = new THREE.Mesh(geoGhost, matGhost.clone());
        gm.position.set(cx, by + (BOX_H + PALLET_H) * 0.35, czz);
        gm.userData = { pos_key: pos_key, isEmpty: true };
        scene.add(gm);
        clickables.push(gm);
        meshByKey[pos_key] = gm;
      }
    }
  }

  /* ── Câmera orbital ──────────────────────────────────────────── */
  var theta  = 0.22;          // ângulo azimutal
  var phi    = 0.50;          // ângulo de elevação
  var radius = 22;            // distância ao alvo
  var target = new THREE.Vector3(CX, CY - 1.0, CZ);

  function syncCamera() {
    camera.position.set(
      target.x + radius * Math.sin(theta) * Math.cos(phi),
      target.y + radius * Math.sin(phi),
      target.z + radius * Math.cos(theta) * Math.cos(phi)
    );
    camera.lookAt(target);
  }
  syncCamera();

  var isDragging = false, lastX = 0, lastY = 0;
  var cvs = renderer.domElement;

  canvas.addEventListener('mousedown', function (e) {
    isDragging = true; lastX = e.clientX; lastY = e.clientY;
    canvas.style.cursor = 'grabbing';
  });
  window.addEventListener('mouseup', function () {
    isDragging = false; canvas.style.cursor = 'default';
  });
  window.addEventListener('mousemove', function (e) {
    if (!isDragging) return;
    theta -= (e.clientX - lastX) * 0.008;
    phi    = Math.max(0.08, Math.min(Math.PI / 2 - 0.04, phi - (e.clientY - lastY) * 0.008));
    lastX  = e.clientX; lastY = e.clientY;
    syncCamera();
  });
  canvas.addEventListener('wheel', function (e) {
    radius = Math.max(6, Math.min(55, radius + e.deltaY * 0.025));
    syncCamera();
    e.preventDefault();
  }, { passive: false });

  // Suporte a toque (mobile)
  var lastTX = 0, lastTY = 0;
  canvas.addEventListener('touchstart', function (e) {
    lastTX = e.touches[0].clientX; lastTY = e.touches[0].clientY;
    e.preventDefault();
  }, { passive: false });
  canvas.addEventListener('touchmove', function (e) {
    theta -= (e.touches[0].clientX - lastTX) * 0.008;
    phi    = Math.max(0.08, Math.min(Math.PI / 2 - 0.04, phi - (e.touches[0].clientY - lastTY) * 0.008));
    lastTX = e.touches[0].clientX; lastTY = e.touches[0].clientY;
    syncCamera();
    e.preventDefault();
  }, { passive: false });

  /* ── Raycasting (hover + click) ──────────────────────────────── */
  var raycaster    = new THREE.Raycaster();
  var mouse2d      = new THREE.Vector2();
  var tooltip      = document.getElementById('tt');
  var hoveredMesh  = null;
  var selectedMesh = null;

  function toNDC(e) {
    var r  = canvas.getBoundingClientRect();
    mouse2d.x =  ((e.clientX - r.left) / r.width)  * 2 - 1;
    mouse2d.y = -((e.clientY - r.top)  / r.height) * 2 + 1;
  }

  function resetHoverGlow(mesh) {
    if (!mesh) return;
    if (mesh.userData.isEmpty) {
      mesh.material.opacity = 0.15;
    } else if (mesh !== selectedMesh) {
      mesh.material.emissive.setHex(mesh.userData.origEmissive || 0x000000);
      mesh.material.emissiveIntensity = mesh.userData.origEmInt || 0.0;
    }
  }

  canvas.addEventListener('mousemove', function (e) {
    if (isDragging) { tooltip.style.display = 'none'; return; }
    toNDC(e);
    raycaster.setFromCamera(mouse2d, camera);
    var hits = raycaster.intersectObjects(clickables);

    resetHoverGlow(hoveredMesh);
    hoveredMesh = null;

    if (hits.length > 0) {
      hoveredMesh = hits[0].object;
      var ud = hoveredMesh.userData;
      canvas.style.cursor = 'pointer';

      if (!ud.isEmpty && hoveredMesh !== selectedMesh) {
        hoveredMesh.material.emissive.setHex(0x223355);
        hoveredMesh.material.emissiveIntensity = 0.55;
      } else if (ud.isEmpty) {
        hoveredMesh.material.opacity = 0.32;
      }

      // Tooltip
      var qty = (ud.quantidade !== null && ud.quantidade !== undefined)
        ? String(ud.quantidade) + ' ' + (ud.unidade || '') : '';
      if (ud.isEmpty) {
        tooltip.innerHTML =
          '<span style="color:#60a5fa;font-size:0.75rem;font-weight:700">' + ud.pos_key + '</span>' +
          '<br><span style="color:#475569;font-size:0.7rem">Vazio</span>';
      } else {
        tooltip.innerHTML =
          '<span style="color:#60a5fa;font-size:0.78rem;font-weight:700">' + ud.pos_key + '</span>' +
          '<br><span style="color:#e2e8f0;font-size:0.8rem">' + ud.produto + '</span>' +
          (qty.trim() ? '<br><span style="color:#94a3b8;font-size:0.72rem">' + qty.trim() + '</span>' : '');
      }
      var r = canvas.getBoundingClientRect();
      var tx = e.clientX - r.left + 14;
      var ty = e.clientY - r.top  - 10;
      // Keep tooltip inside canvas
      tooltip.style.display = 'block';
      var ttW = tooltip.offsetWidth  || 180;
      var ttH = tooltip.offsetHeight || 60;
      if (tx + ttW > W - 10) tx = tx - ttW - 28;
      if (ty + ttH > H - 10) ty = H - ttH - 10;
      tooltip.style.left = Math.max(4, tx) + 'px';
      tooltip.style.top  = Math.max(4, ty) + 'px';

    } else {
      canvas.style.cursor = 'default';
      tooltip.style.display = 'none';
    }
  });

  canvas.addEventListener('mouseleave', function () {
    tooltip.style.display = 'none';
    resetHoverGlow(hoveredMesh);
    hoveredMesh = null;
  });

  canvas.addEventListener('click', function (e) {
    if (isDragging) return;
    toNDC(e);
    raycaster.setFromCamera(mouse2d, camera);
    var hits = raycaster.intersectObjects(clickables);

    // Limpar seleção anterior
    if (selectedMesh && !selectedMesh.userData.isEmpty) {
      selectedMesh.material.emissive.setHex(selectedMesh.userData.origEmissive || 0x000000);
      selectedMesh.material.emissiveIntensity = selectedMesh.userData.origEmInt || 0.0;
    }

    if (hits.length > 0) {
      selectedMesh = hits[0].object;
      if (!selectedMesh.userData.isEmpty) {
        selectedMesh.material.emissive.setHex(0x304080);
        selectedMesh.material.emissiveIntensity = 0.85;
      }

      // Enviar pos_key ao Streamlit via input oculto (mesmo padrão do DnD)
      try {
        var inp = window.parent.document.querySelector('input[placeholder="__rack_3d_click__"]');
        if (inp) {
          var setter = Object.getOwnPropertyDescriptor(
            window.parent.HTMLInputElement.prototype, 'value'
          ).set;
          setter.call(inp, selectedMesh.userData.pos_key);
          inp.dispatchEvent(new Event('input', { bubbles: true }));
        }
      } catch (err) {
        console.warn('rack3d click signal:', err);
      }
    } else {
      selectedMesh = null;
    }
  });

  /* ── Loop de animação ────────────────────────────────────────── */
  function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
  }
  animate();

  /* ── Redimensionamento ────────────────────────────────────────── */
  window.addEventListener('resize', function () {
    var w = container.clientWidth;
    renderer.setSize(w, H);
    camera.aspect = w / H;
    camera.updateProjectionMatrix();
  });

})();
"""
