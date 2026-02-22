"""
agrofit_client.py
─────────────────────────────────────────────────────────────────────────────
Módulo de integração com a API AGROFIT da Embrapa.
Base URL: https://api.cnptia.embrapa.br/agrofit/v1

Endpoints utilizados:
  GET /produtos-formulados          → listagem paginada de produtos
  GET /produtos-formulados/{id}     → detalhe de um produto pelo ID interno
  GET /produtos-formulados/busca    → busca por marca comercial (nome)
  GET /ingredientes-ativos          → listagem de ingredientes ativos
  GET /ingredientes-ativos/{id}     → detalhe de um ingrediente ativo

Autenticação:
  Bearer token obtido no portal https://www.agroapi.cnptia.embrapa.br/store
  Guarde o token em st.secrets["AGROFIT_TOKEN"] ou na env var AGROFIT_TOKEN.

Uso básico:
    from agrofit_client import AgroFitClient
    client = AgroFitClient(token="seu_token_aqui")
    resultado = client.buscar_produto("Roundup")
    # → lista de dicts com marca, ingrediente ativo, classificação, etc.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import re
import time
import requests
import pandas as pd
import streamlit as st
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BASE_URL = "https://api.cnptia.embrapa.br/agrofit/v1"
_DEFAULT_TIMEOUT = 10        # segundos
_RETRY_WAIT = 1.5            # segundos entre tentativas
_MAX_RETRIES = 3
_PAGE_SIZE = 100             # máximo de registros por página na listagem

# Cache TTL no Streamlit (12 horas — o AGROFIT é relativamente estático)
_CACHE_TTL = 43_200


# ══════════════════════════════════════════════════════════════════════════════
# CLIENTE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class AgroFitClient:
    """
    Cliente HTTP para a API AGROFIT v1 da Embrapa.

    Exemplo de uso:
        client = AgroFitClient()          # lê token de st.secrets ou env
        df = client.enriquecer_estoque(df_estoque)
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or _get_token()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        })

    # ─── primitivos HTTP ──────────────────────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> dict | list | None:
        """GET com retry simples. Retorna JSON ou None em caso de erro."""
        url = f"{BASE_URL}{path}"
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 401:
                    raise ValueError("❌ Token AGROFIT inválido ou expirado. Atualize AGROFIT_TOKEN.")
                elif resp.status_code == 429:
                    time.sleep(_RETRY_WAIT * attempt)
                    continue
                else:
                    return None
            except requests.RequestException:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_WAIT)
        return None

    # ─── endpoints ────────────────────────────────────────────────────────────

    def buscar_produto(self, nome: str, max_results: int = 5) -> list[dict]:
        """
        Busca produtos formulados pelo nome da marca comercial.
        Retorna lista de dicts com os campos relevantes normalizados.
        """
        data = self._get("/produtos-formulados/busca", params={
            "marcaComercial": nome,
            "page": 0,
            "size": max_results,
        })
        if not data:
            return []
        # A API retorna {"content": [...], "totalElements": N, ...}
        items = data.get("content", data) if isinstance(data, dict) else data
        return [_normalizar_produto(p) for p in items]

    def detalhe_produto(self, produto_id: int) -> dict | None:
        """Retorna os detalhes completos de um produto formulado pelo ID."""
        data = self._get(f"/produtos-formulados/{produto_id}")
        return _normalizar_produto(data) if data else None

    def listar_ingredientes_ativos(self) -> list[dict]:
        """
        Retorna TODOS os ingredientes ativos cadastrados no AGROFIT.
        Pagina automaticamente até esgotar os resultados.
        """
        resultados = []
        page = 0
        while True:
            data = self._get("/ingredientes-ativos", params={"page": page, "size": _PAGE_SIZE})
            if not data:
                break
            items = data.get("content", []) if isinstance(data, dict) else data
            if not items:
                break
            resultados.extend(items)
            # Verifica se há próxima página
            total = data.get("totalElements", 0) if isinstance(data, dict) else 0
            if len(resultados) >= total or len(items) < _PAGE_SIZE:
                break
            page += 1
        return resultados

    def buscar_ingrediente_ativo(self, nome: str) -> list[dict]:
        """Busca ingredientes ativos pelo nome (busca parcial)."""
        data = self._get("/ingredientes-ativos", params={
            "nomeComum": nome,
            "page": 0,
            "size": 20,
        })
        if not data:
            return []
        items = data.get("content", data) if isinstance(data, dict) else data
        return items

    def buscar_por_praga(self, nome_praga: str, max_results: int = 30) -> list[dict]:
        """
        Busca produtos formulados registrados para uma praga pelo nome comum.
        Usa o endpoint /search/produtos-formulados com filtro praga_nome_comum.
        """
        data = self._get("/search/produtos-formulados", params={
            "praga_nome_comum": nome_praga,
            "page": 0,
            "size": max_results,
        })
        if not data:
            return []
        items = data.get("content", data) if isinstance(data, dict) else data
        return [_normalizar_produto(p) for p in items]

    def buscar_pragas_comuns(self, nome: str, max_results: int = 10) -> list[str]:
        """
        Busca nomes comuns de pragas que correspondem ao termo informado.
        Útil para autocompletar/sugerir ao usuário.
        """
        data = self._get("/search/pragas-nomes-comuns", params={
            "q": nome,
            "page": 0,
            "size": max_results,
        })
        if not data:
            return []
        items = data.get("content", data) if isinstance(data, dict) else data
        if items and isinstance(items[0], dict):
            return [i.get("nome", i.get("nomeComum", str(i))) for i in items]
        return [str(i) for i in items]

    # ─── enriquecimento em lote ───────────────────────────────────────────────

    def enriquecer_estoque(
        self,
        df: pd.DataFrame,
        col_produto: str = "produto",
        col_categoria: str = "categoria",
        progresso_callback=None,
    ) -> pd.DataFrame:
        """
        Recebe um DataFrame de estoque e adiciona colunas AGROFIT:
          - agrofit_id           : ID interno do produto na API
          - agrofit_marca        : nome da marca comercial conforme MAPA
          - agrofit_ingrediente  : ingrediente(s) ativo(s)
          - agrofit_classe       : classe agronômica (herbicida, fungicida...)
          - agrofit_classificacao_tox : classificação toxicológica (I, II, III...)
          - agrofit_classificacao_amb : classificação ambiental
          - agrofit_bioinsumo    : True/False
          - agrofit_nr_registro  : número de registro no MAPA
          - agrofit_confianca    : score de similaridade da busca (0–1)
        
        Apenas produtos das categorias de defensivos são consultados.
        """
        CATEGORIAS_DEFENSIVOS = {
            "HERBICIDAS", "FUNGICIDAS", "INSETICIDAS", "NEMATICIDAS",
            "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO", "ÓLEOS",
            "ADUBOS FOLIARES",
        }

        # Colunas a adicionar
        novas_colunas = [
            "agrofit_id", "agrofit_marca", "agrofit_ingrediente",
            "agrofit_classe", "agrofit_classificacao_tox",
            "agrofit_classificacao_amb", "agrofit_bioinsumo",
            "agrofit_nr_registro", "agrofit_confianca",
        ]
        for col in novas_colunas:
            if col not in df.columns:
                df[col] = None

        total = len(df)
        for i, (idx, row) in enumerate(df.iterrows()):
            if progresso_callback:
                progresso_callback(i, total, str(row.get(col_produto, "")))

            categoria = str(row.get(col_categoria, "")).upper().strip()
            if categoria not in CATEGORIAS_DEFENSIVOS:
                continue  # pula produtos não-defensivos

            nome_produto = str(row.get(col_produto, "")).strip()
            if not nome_produto:
                continue

            # Tenta buscar na API
            resultados = self.buscar_produto(nome_produto, max_results=3)
            if not resultados:
                continue

            # Seleciona o melhor resultado por similaridade de nome
            melhor = _melhor_match(nome_produto, resultados)
            if not melhor or melhor["_confianca"] < 0.45:
                continue

            df.at[idx, "agrofit_id"]                = melhor.get("id")
            df.at[idx, "agrofit_marca"]             = melhor.get("marca_comercial")
            df.at[idx, "agrofit_ingrediente"]       = melhor.get("ingrediente_ativo")
            df.at[idx, "agrofit_classe"]            = melhor.get("classe_agronomica")
            df.at[idx, "agrofit_classificacao_tox"] = melhor.get("classificacao_toxicologica")
            df.at[idx, "agrofit_classificacao_amb"] = melhor.get("classificacao_ambiental")
            df.at[idx, "agrofit_bioinsumo"]         = melhor.get("bioinsumo")
            df.at[idx, "agrofit_nr_registro"]       = melhor.get("nr_registro")
            df.at[idx, "agrofit_confianca"]         = melhor["_confianca"]

            # Pequena pausa para não estourar rate limit (100k req/mês gratuito)
            time.sleep(0.05)

        return df


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════════════════════

def _get_token() -> str:
    """Lê o token AGROFIT de st.secrets ou variável de ambiente."""
    try:
        return st.secrets["AGROFIT_TOKEN"]
    except (KeyError, FileNotFoundError, AttributeError):
        token = os.environ.get("AGROFIT_TOKEN", "")
        if not token:
            raise ValueError(
                "Token AGROFIT não encontrado. "
                "Adicione AGROFIT_TOKEN em st.secrets ou como variável de ambiente. "
                "Obtenha o token em: https://www.agroapi.cnptia.embrapa.br/store"
            )
        return token


def _normalizar_produto(p: dict) -> dict:
    """
    Normaliza os campos da resposta da API para um dict padronizado.
    A API pode retornar objetos aninhados; isso os achata.
    """
    if not isinstance(p, dict):
        return {}

    # Ingrediente ativo pode ser lista de objetos ou string
    ing_raw = p.get("ingredienteAtivo") or p.get("ingredientesAtivos") or []
    if isinstance(ing_raw, list):
        ingrediente = "; ".join(
            i.get("nomeComum", i.get("nome", str(i))) if isinstance(i, dict) else str(i)
            for i in ing_raw
        )
    elif isinstance(ing_raw, dict):
        ingrediente = ing_raw.get("nomeComum", ing_raw.get("nome", ""))
    else:
        ingrediente = str(ing_raw)

    # Classe agronômica
    classe_raw = p.get("classeAgronomica") or p.get("classe") or {}
    classe = classe_raw.get("descricao", classe_raw) if isinstance(classe_raw, dict) else str(classe_raw or "")

    # Titular do registro
    titular_raw = p.get("titularRegistro") or p.get("titular") or {}
    titular = titular_raw.get("razaoSocial", titular_raw) if isinstance(titular_raw, dict) else str(titular_raw or "")

    # Classificação toxicológica
    tox_raw = p.get("classificacaoToxicologica") or {}
    tox = tox_raw.get("descricao", tox_raw) if isinstance(tox_raw, dict) else str(tox_raw or "")

    # Classificação ambiental
    amb_raw = p.get("classificacaoAmbiental") or {}
    amb = amb_raw.get("descricao", amb_raw) if isinstance(amb_raw, dict) else str(amb_raw or "")

    return {
        "id":                        p.get("id"),
        "nr_registro":               p.get("numeroRegistro") or p.get("nrRegistro"),
        "marca_comercial":           p.get("marcaComercial") or p.get("marca"),
        "titular":                   titular,
        "ingrediente_ativo":         ingrediente,
        "classe_agronomica":         classe,
        "classificacao_toxicologica": tox,
        "classificacao_ambiental":   amb,
        "bioinsumo":                 bool(p.get("bioinsumo") or p.get("origemBiologica")),
        "formulacao":                (p.get("formulacao") or {}).get("sigla", ""),
        "_raw":                      p,           # campo oculto com resposta completa
        "_confianca":                0.0,         # preenchido por _melhor_match
    }


def _similaridade(a: str, b: str) -> float:
    """Score de similaridade entre dois nomes de produto (0–1)."""
    a = re.sub(r"[^A-Z0-9 ]", "", a.upper())
    b = re.sub(r"[^A-Z0-9 ]", "", b.upper())
    # Penaliza diferença de tokens (palavras)
    return SequenceMatcher(None, a, b).ratio()


def _melhor_match(nome_buscado: str, candidatos: list[dict]) -> dict | None:
    """Retorna o candidato com maior similaridade ao nome buscado."""
    if not candidatos:
        return None
    melhor = None
    melhor_score = -1.0
    for c in candidatos:
        marca = c.get("marca_comercial") or ""
        score = _similaridade(nome_buscado, marca)
        if score > melhor_score:
            melhor_score = score
            melhor = c
    if melhor:
        melhor = dict(melhor)
        melhor["_confianca"] = round(melhor_score, 3)
    return melhor


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES STREAMLIT — widgets prontos para usar no app
# ══════════════════════════════════════════════════════════════════════════════

def widget_busca_agrofit(token: Optional[str] = None):
    """
    Widget de busca avulsa no AGROFIT.
    Cole `widget_busca_agrofit()` em qualquer aba do seu app.
    """
    st.markdown("#### 🌿 Consulta AGROFIT (MAPA)")
    col1, col2 = st.columns([3, 1])
    with col1:
        nome = st.text_input("Nome do produto / marca comercial", key="agrofit_busca_input")
    with col2:
        buscar = st.button("🔍 Buscar", key="agrofit_busca_btn")

    if buscar and nome:
        try:
            client = AgroFitClient(token=token)
            with st.spinner("Consultando AGROFIT..."):
                resultados = client.buscar_produto(nome, max_results=8)
            if not resultados:
                st.warning("Nenhum produto encontrado com este nome.")
            else:
                df_res = pd.DataFrame([
                    {
                        "Marca": r.get("marca_comercial", ""),
                        "Ingrediente Ativo": r.get("ingrediente_ativo", ""),
                        "Classe": r.get("classe_agronomica", ""),
                        "Tox.": r.get("classificacao_toxicologica", ""),
                        "Amb.": r.get("classificacao_ambiental", ""),
                        "Bioinsumo": "✅" if r.get("bioinsumo") else "",
                        "Nº Registro": r.get("nr_registro", ""),
                        "Titular": r.get("titular", ""),
                    }
                    for r in resultados
                ])
                st.dataframe(df_res, use_container_width=True, hide_index=True)
        except ValueError as e:
            st.error(str(e))
            st.info("Configure AGROFIT_TOKEN em st.secrets ou como variável de ambiente.")


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def enriquecer_estoque_cached(
    df_json: str,       # DataFrame serializado em JSON para ser hashável pelo cache
    token: str,
) -> str:
    """
    Versão cacheável de enriquecer_estoque (recebe/retorna JSON).
    O cache evita reconsultar a API nas próximas 12h para o mesmo estoque.
    """
    df = pd.read_json(df_json)
    client = AgroFitClient(token=token)
    df_enriquecido = client.enriquecer_estoque(df)
    return df_enriquecido.to_json()


def botao_enriquecer_estoque(df_estoque: pd.DataFrame, token: Optional[str] = None):
    """
    Botão + lógica completa para enriquecer o estoque com dados do AGROFIT.
    Retorna o DataFrame enriquecido ou None se não foi executado.

    Exemplo de uso em qualquer aba:
        df_enriquecido = botao_enriquecer_estoque(df_estoque)
        if df_enriquecido is not None:
            st.dataframe(df_enriquecido)
    """
    st.markdown("#### 🌿 Enriquecer estoque com dados AGROFIT")
    st.caption(
        "Consulta a API do MAPA (via Embrapa) para adicionar ingrediente ativo, "
        "classificação toxicológica e ambiental a cada defensivo do estoque. "
        "Apenas herbicidas, fungicidas, inseticidas, nematicidas, adjuvantes e óleos são consultados."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Enriquecer estoque com AGROFIT", key="btn_agrofit_enrich"):
            _tok = token or _try_get_token_silent()
            if not _tok:
                st.error(
                    "Token AGROFIT não configurado. "
                    "Adicione AGROFIT_TOKEN em st.secrets ou como variável de ambiente. "
                    "Obtenha gratuitamente em: https://www.agroapi.cnptia.embrapa.br/store"
                )
                return None

            # Filtra só defensivos para não desperdiçar requisições
            CATS = {"HERBICIDAS","FUNGICIDAS","INSETICIDAS","NEMATICIDAS",
                    "ADJUVANTES","ÓLEOS","ADUBOS FOLIARES","ADJUVANTES/ESPALHANTES ADESIVO"}
            df_def = df_estoque[df_estoque["categoria"].str.upper().isin(CATS)].copy()
            total = len(df_def)

            if total == 0:
                st.warning("Nenhum produto de categoria defensivo encontrado no estoque.")
                return None

            # Barra de progresso
            prog = st.progress(0, text="Iniciando consulta AGROFIT...")
            status_txt = st.empty()
            resultados_parciais = []

            client = AgroFitClient(token=_tok)
            for i, (_, row) in enumerate(df_def.iterrows()):
                prog.progress((i + 1) / total, text=f"Consultando {i+1}/{total}...")
                status_txt.caption(f"🔍 `{row['produto']}`")

                nome = str(row.get("produto", "")).strip()
                resultados = client.buscar_produto(nome, max_results=3) if nome else []
                melhor = _melhor_match(nome, resultados) if resultados else None

                resultados_parciais.append({
                    "codigo":      row.get("codigo", ""),
                    "produto":     row.get("produto", ""),
                    "categoria":   row.get("categoria", ""),
                    "ingrediente": melhor.get("ingrediente_ativo", "") if melhor else "",
                    "classe":      melhor.get("classe_agronomica", "") if melhor else "",
                    "tox":         melhor.get("classificacao_toxicologica", "") if melhor else "",
                    "amb":         melhor.get("classificacao_ambiental", "") if melhor else "",
                    "bioinsumo":   melhor.get("bioinsumo", False) if melhor else False,
                    "nr_registro": melhor.get("nr_registro", "") if melhor else "",
                    "confianca":   melhor.get("_confianca", 0.0) if melhor else 0.0,
                })
                time.sleep(0.05)

            prog.empty()
            status_txt.empty()

            df_resultado = pd.DataFrame(resultados_parciais)
            st.success(f"✅ {len(df_resultado)} produtos consultados no AGROFIT!")
            st.session_state["agrofit_resultado"] = df_resultado
            return df_resultado

    # Mostra resultado se já existir no session_state
    if "agrofit_resultado" in st.session_state:
        with col2:
            df_r = st.session_state["agrofit_resultado"]
            encontrados = df_r[df_r["ingrediente"] != ""].shape[0]
            st.metric("Encontrados", encontrados, f"de {len(df_r)}")

        _render_tabela_agrofit(df_r)
        return df_r

    return None


def _render_tabela_agrofit(df: pd.DataFrame):
    """Renderiza tabela de resultados AGROFIT com filtros."""
    st.markdown("##### Resultado AGROFIT")

    # Filtro por confiança
    min_conf = st.slider(
        "Confiança mínima na identificação",
        min_value=0.0, max_value=1.0, value=0.5, step=0.05,
        key="agrofit_conf_slider"
    )
    df_filtrado = df[df["confianca"] >= min_conf].copy()

    # Formatação visual da confiança
    def fmt_conf(v):
        if v >= 0.8:  return f"🟢 {v:.0%}"
        if v >= 0.5:  return f"🟡 {v:.0%}"
        if v > 0:     return f"🔴 {v:.0%}"
        return "—"

    df_display = df_filtrado.copy()
    df_display["confianca"] = df_display["confianca"].apply(fmt_conf)
    df_display["bioinsumo"] = df_display["bioinsumo"].apply(lambda x: "✅" if x else "")

    df_display.columns = [
        "Código", "Produto", "Categoria", "Ingrediente Ativo",
        "Classe", "Tox.", "Amb.", "Bioinsumo", "Nº Registro", "Confiança"
    ]
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Download CSV
    csv = df_filtrado.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar CSV (AGROFIT)",
        data=csv,
        file_name=f"agrofit_estoque_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="agrofit_download_btn"
    )


def _try_get_token_silent() -> str:
    """Tenta obter token sem lançar exceção."""
    try:
        return _get_token()
    except ValueError:
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_marcas_por_praga_cached(nome_praga: str, token: str) -> list[str]:
    """
    Busca no Agrofit as marcas comerciais registradas para uma praga (com cache de 1h).
    Tenta primeiro busca direta; se retornar zero resultados, normaliza o nome via
    buscar_pragas_comuns e tenta novamente para cada nome normalizado.
    Retorna lista de nomes de marca comercial únicos.
    """
    import traceback
    try:
        print(f"[Agrofit] buscar_marcas_por_praga_cached: iniciando para '{nome_praga}'")
        client = AgroFitClient(token=token)

        todas_marcas: list[str] = []

        # --- Tentativa 1: busca direta pelo termo informado ---
        resultados_diretos = client.buscar_por_praga(nome_praga, max_results=50)
        print(f"[Agrofit] buscar_por_praga('{nome_praga}') direto → {len(resultados_diretos)} produto(s)")
        marcas_diretas = [r.get("marca_comercial", "") for r in resultados_diretos if r.get("marca_comercial")]
        print(f"[Agrofit] Marcas (direto): {marcas_diretas[:10]}")
        todas_marcas.extend(marcas_diretas)

        # --- Tentativa 2: normalizar via buscar_pragas_comuns ---
        pragas_norm = client.buscar_pragas_comuns(nome_praga, max_results=10)
        print(f"[Agrofit] buscar_pragas_comuns('{nome_praga}') → {pragas_norm}")
        for praga_norm in pragas_norm:
            nome_norm_upper = praga_norm.strip().upper()
            if nome_norm_upper == nome_praga.strip().upper():
                continue  # já tentamos esse termo
            res2 = client.buscar_por_praga(praga_norm, max_results=50)
            print(f"[Agrofit] buscar_por_praga('{praga_norm}') normalizado → {len(res2)} produto(s)")
            marcas2 = [r.get("marca_comercial", "") for r in res2 if r.get("marca_comercial")]
            print(f"[Agrofit] Marcas ('{praga_norm}'): {marcas2[:5]}")
            todas_marcas.extend(marcas2)

        # Remove duplicatas preservando ordem
        marcas_unicas = list(dict.fromkeys(m.strip() for m in todas_marcas if m.strip()))
        print(f"[Agrofit] Total marcas únicas para '{nome_praga}': {len(marcas_unicas)}")
        return marcas_unicas

    except Exception as e:
        print(f"[Agrofit] ERRO em buscar_marcas_por_praga_cached('{nome_praga}'): {e}")
        print(traceback.format_exc())
        return []


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO DE SINCRONIZAÇÃO COM A TABELA principios_ativos
# ══════════════════════════════════════════════════════════════════════════════

def salvar_resultado_agrofit_no_banco(df_resultado: pd.DataFrame, conn) -> int:
    """
    Recebe o DataFrame de resultado AGROFIT e persiste na tabela
    `principios_ativos` do banco existente com source='agrofit'.

    Retorna o número de registros inseridos/atualizados.
    """
    if df_resultado.empty:
        return 0

    registros = [
        (row["produto"], row["ingrediente"], row["categoria"])
        for _, row in df_resultado.iterrows()
        if row.get("ingrediente")
    ]
    if not registros:
        return 0

    try:
        # Usa INSERT OR REPLACE para upsert (requer UNIQUE constraint em produto+principio_ativo)
        conn.executemany(
            """
            INSERT OR REPLACE INTO principios_ativos (produto, principio_ativo, categoria, source)
            VALUES (?, ?, ?, 'agrofit')
            """,
            registros,
        )
        conn.commit()
        return len(registros)
    except Exception as e:
        st.error(f"❌ Erro ao salvar dados AGROFIT no banco: {e}")
        return 0
