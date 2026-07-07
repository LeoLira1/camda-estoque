"""
iframe_compat.py — ponte st.components.v1.html → st.iframe
============================================================

``st.components.v1.html`` foi deprecado no Streamlit 1.56 e será removido
após 2026-06-01. O substituto oficial é ``st.iframe`` (disponível a partir
do 1.58), que aceita HTML bruto diretamente como ``src``.

Este módulo expõe ``html()`` com a MESMA assinatura da API antiga, para que
os pontos de chamada troquem apenas o import::

    import iframe_compat as _stc
    _stc.html("<script>...</script>", height=0)

Diferenças da nova API tratadas aqui:

- ``st.iframe`` rejeita ``height <= 0``. Os injetores invisíveis de script
  usavam ``height=0``; aqui viram ``height=1`` e recebem um script de
  auto-colapso que zera o próprio iframe e os containers pai (mesmo padrão
  já usado nos injetores do app via ``window.frameElement``). O script
  também marca o iframe com ``data-camda-collapse``, que o CSS global de
  app_turso.py usa como seletor de reforço. Nota: diferente da API antiga,
  o iframe novo NÃO recebe atributo ``height`` nem style inline — o
  tamanho vem de classes CSS geradas —, então seletores como
  ``iframe[height="0"]`` não funcionam com ele.

- ``st.iframe`` sempre ativa scrolling no iframe. Para reproduzir o antigo
  ``scrolling=False``, injeta-se ``overflow:hidden`` no documento embutido.
  O <style> é anexado ao FINAL do conteúdo para não deslocar o <!DOCTYPE>
  de documentos completos (o parser HTML move o nó para dentro do <body>).

- O ``title`` do iframe no DOM muda de "streamlit_components.v1.html.html"
  para "st.iframe" — seletores CSS/JS que dependem disso estão atualizados
  no app.

Em versões antigas do Streamlit (< 1.58, sem ``st.iframe``) o módulo cai de
volta para ``st.components.v1.html`` automaticamente.
"""

from __future__ import annotations

import streamlit as st

_HAS_ST_IFRAME = hasattr(st, "iframe")

# Reproduz o comportamento de scrolling=False da API antiga (overflow oculto
# no elemento iframe): esconde qualquer estouro do documento embutido.
_NO_SCROLL_STYLE = "<style>html,body{overflow:hidden !important;}</style>"

# Auto-colapso para injetores invisíveis (equivalente ao antigo height=0):
# zera o iframe hospedeiro e até 3 containers pai, parando nos blocos de
# layout do Streamlit — mesmo padrão dos injetores já existentes no app.
_COLLAPSE_SCRIPT = """<script>
(function() {
  try {
    var _fe = window.frameElement;
    if (_fe) {
      _fe.setAttribute('data-camda-collapse', '1');
      _fe.style.cssText = 'display:none!important;height:0!important;width:0!important;border:none!important;position:absolute!important;';
      var _p = _fe.parentElement;
      var _STOP = /stVerticalBlock|stMain|stApp|block-container|stAppView/;
      for (var _i = 0; _i < 3; _i++) {
        if (!_p || _p === document.body) break;
        var _tid = (_p.getAttribute && _p.getAttribute('data-testid')) || '';
        var _cls = _p.className || '';
        if (_STOP.test(_tid) || _STOP.test(_cls)) break;
        _p.style.height = '0';
        _p.style.minHeight = '0';
        _p.style.margin = '0';
        _p.style.padding = '0';
        _p.style.overflow = 'hidden';
        _p.style.lineHeight = '0';
        _p = _p.parentElement;
      }
    }
  } catch (_e) {}
})();
</script>"""


def html(
    content: str,
    width: int | None = None,
    height: int | None = None,
    scrolling: bool = False,
) -> None:
    """Renderiza HTML bruto num iframe — assinatura de st.components.v1.html.

    content   : string HTML (fragmento ou documento completo).
    width     : largura fixa em px; None = ocupa a largura do container.
    height    : altura fixa em px; None = 150 (default da API antiga);
                0 = injetor invisível (vira 1px, colapsado via CSS global).
    scrolling : False (default) esconde overflow, como na API antiga.
    """
    if not _HAS_ST_IFRAME:
        import streamlit.components.v1 as _components_v1

        _components_v1.html(content, width=width, height=height, scrolling=scrolling)
        return

    if height is None:
        height = 150  # default histórico de st.components.v1.html
    height = int(height)

    if not scrolling:
        # Anexado ao FINAL: o parser move o nó para o <body> sem afetar o
        # <!DOCTYPE> de documentos completos (evita quirks mode).
        content = content + _NO_SCROLL_STYLE

    if height <= 0:
        # Injetor invisível: st.iframe exige height >= 1; o script de
        # auto-colapso elimina o pixel restante e o espaçamento do container.
        content = content + _COLLAPSE_SCRIPT
        height = 1

    st.iframe(content, width=width if width is not None else "stretch", height=height)
