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
    """Cliente HTTP para a API AGROFIT v1 da Embrapa."""

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
                    print(f"[Agrofit._get] HTTP {resp.status_code} para {url} params={params} | body={resp.text[:300]}")
                    return None
            except requests.RequestException as exc:
                print(f"[Agrofit._get] RequestException tentativa {attempt}/{_MAX_RETRIES}: {exc}")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_WAIT)
        return None

    # ─── endpoints ────────────────────────────────────────────────────────────

    def buscar_produto(self, nome: str, max_results: int = 5) -> list[dict]:
        data = self._get("/produtos-formulados/busca", params={
            "marcaComercial": nome,
            "page": 0,
            "size": max_results,
        })
        if not data:
            return []
        items = data.get("content", data) if isinstance(data, dict) else data
        return [_normalizar_produto(p) for p in items]

    def detalhe_produto(self, produto_id: int) -> dict | None:
        data = self._get(f"/produtos-formulados/{produto_id}")
        return _normalizar_produto(data) if data else None

    def listar_ingredientes_ativos(self) -> list[dict]:
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
            total = data.get("totalElements", 0) if isinstance(data, dict) else 0
            if len(resultados) >= total or len(items) < _PAGE_SIZE:
                break
            page += 1
        return resultados

    def buscar_ingrediente_ativo(self, nome: str) -> list[dict]:
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
        data = self._get("/search/produtos-formulados", params={
            "praga_nome_comum": nome_praga,
            "page": 1,
            "size": max_results,
        })
        if not data:
            return []
        items = data.get("content", data) if isinstance(data, dict) else data
        return [_normalizar_produto(p) for p in items]

    def buscar_pragas_comuns(self, nome: str, max_results: int = 10) -> list[str]:
        data = self._get("/search/pragas-nomes-comuns", params={
            "q": nome,
            "page": 1,
            "size": max_results,
        })
        if not data:
            return []
        items = data.get("content", data) if isinstance(data, dict) else data
        return [
            i.get("nome", i.get("nomeComum", str(i))) if isinstance(i, dict) else str(i)
            for i in items
        ]

    # ─── enriquecimento em lote ───────────────────────────────────────────────

    def enriquecer_estoque(
        self,
        df: pd.DataFrame,
        col_produto: str = "produto",
        col_categoria: str = "categoria",
        progresso_callback=None,
    ) -> pd.DataFrame:
        CATEGORIAS_DEFENSIVOS = {
            "HERBICIDAS", "FUNGICIDAS", "INSETICIDAS", "NEMATICIDAS",
            "ADJUVANTES", "ADJUVANTES/ESPALHANTES ADESIVO", "ÓLEOS",
            "ADUBOS FOLIARES",
        }

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
                continue

            nome_produto = str(row.get(col_produto, "")).strip()
            if not nome_produto:
                continue

            resultados = self.buscar_produto(nome_produto, max_results=3)
            if not resultados:
                continue

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

            time.sleep(0.05)

        return df


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════════════════════

def _get_token() -> str:
    try:
        return st.secrets["AGROFIT_TOKEN"]
    except (KeyError, FileNotFoundError, AttributeError):
        token = os.environ.get("AGROFIT_TOKEN", "")
        if not token:
            raise ValueError(
                "Token AGROFIT não encontrado. "
                "Adicione AGROFIT_TOKEN em st.secrets ou como variável de ambiente."
            )
        return token


def _normalizar_produto(p: dict) -> dict:
    if not isinstance(p, dict):
        return {}

    # Ingrediente ativo
    ing_raw = p.get("ingredienteAtivo") or p.get("ingrediente_ativo") or p.get("ingredientesAtivos") or []
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
    classe_raw = p.get("classeAgronomica") or p.get("classe_categoria_agronomica") or p.get("classe") or {}
    if isinstance(classe_raw, list): classe_raw = classe_raw[0] if classe_raw else {}
    classe = classe_raw.get("descricao", classe_raw) if isinstance(classe_raw, dict) else str(classe_raw or "")

    # Titular do registro
    titular_raw = p.get("titularRegistro") or p.get("titular_registro") or p.get("titular") or {}
    if isinstance(titular_raw, list): titular_raw = titular_raw[0] if titular_raw else {}
    titular = titular_raw.get("razaoSocial", titular_raw) if isinstance(titular_raw, dict) else str(titular_raw or "")

    # Tox
    tox_raw = p.get("classificacaoToxicologica") or p.get("classificacao_toxicologica") or {}
    if isinstance(tox_raw, list): tox_raw = tox_raw[0] if tox_raw else {}
    tox = tox_raw.get("descricao", tox_raw) if isinstance(tox_raw, dict) else str(tox_raw or "")

    # Amb
    amb_raw = p.get("classificacaoAmbiental") or p.get("classificacao_ambiental") or {}
    if isinstance(amb_raw, list): amb_raw = amb_raw[0] if amb_raw else {}
    amb = amb_raw.get("descricao", amb_raw) if isinstance(amb_raw, dict) else str(amb_raw or "")

    # Formulação
    formulacao_raw = p.get("formulacao") or {}
    if isinstance(formulacao_raw, list): formulacao_raw = formulacao_raw[0] if formulacao_raw else {}
    formulacao = formulacao_raw.get("sigla", formulacao_raw) if isinstance(formulacao_raw, dict) else str(formulacao_raw or "")

    # Marca comercial (Corrige o problema das marcas vindo em listas)
    marca_raw = p.get("marcaComercial") or p.get("marca_comercial") or p.get("marca")
    if isinstance(marca_raw, list):
        marca = str(marca_raw[0]) if marca_raw else ""
    else:
        marca = str(marca_raw or "")

    # Número de registro
    nr_raw = p.get("numeroRegistro") or p.get("numero_registro") or p.get("nrRegistro")
    if isinstance(nr_raw, list):
        nr = str(nr_raw[0]) if nr_raw else ""
    else:
        nr = str(nr_raw or "")

    return {
        "id":                        p.get("id"),
        "nr_registro":               nr,
        "marca_comercial":           marca.strip(),
        "titular":                   titular,
        "ingrediente_ativo":         ingrediente,
        "classe_agronomica":         classe,
        "classificacao_toxicologica": tox,
        "classificacao_ambiental":   amb,
        "bioinsumo":                 bool(p.get("bioinsumo") or p.get("origemBiologica") or p.get("produto_biologico")),
        "formulacao":                formulacao,
        "_raw":                      p,           # campo oculto com resposta completa
        "_confianca":                0.0,         # preenchido por _melhor_match
    }


def _similaridade(a: str, b: str) -> float:
    a = re.sub(r"[^A-Z0-9 ]", "", a.upper())
    b = re.sub(r"[^A-Z0-9 ]", "", b.upper())
    return SequenceMatcher(None, a, b).ratio()


def _melhor_match(nome_buscado: str, candidatos: list[dict]) -> dict | None:
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
# FUNÇÕES STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════

def widget_busca_agrofit(token: Optional[str] = None):
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
                st.dataframe(df_res, width='stretch', hide_index=True)
        except ValueError as e:
            st.error(str(e))
            st.info("Configure AGROFIT_TOKEN em st.secrets ou como variável de ambiente.")


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def enriquecer_estoque_cached(df_json: str, token: str) -> str:
    df = pd.read_json(df_json)
    client = AgroFitClient(token=token)
    df_enriquecido = client.enriquecer_estoque(df)
    return df_enriquecido.to_json()


def botao_enriquecer_estoque(df_estoque: pd.DataFrame, token: Optional[str] = None):
    st.markdown("#### 🌿 Enriquecer estoque com dados AGROFIT")
    st.caption("Consulta a API do MAPA (via Embrapa) para adicionar dados aos defensivos.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Enriquecer estoque com AGROFIT", key="btn_agrofit_enrich"):
            _tok = token or _try_get_token_silent()
            if not _tok:
                st.error("Token AGROFIT não configurado.")
                return None

            CATS = {"HERBICIDAS","FUNGICIDAS","INSETICIDAS","NEMATICIDAS",
                    "ADJUVANTES","ÓLEOS","ADUBOS FOLIARES","ADJUVANTES/ESPALHANTES ADESIVO"}
            df_def = df_estoque[df_estoque["categoria"].str.upper().isin(CATS)].copy()
            total = len(df_def)

            if total == 0:
                st.warning("Nenhum produto de categoria defensivo encontrado.")
                return None

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

    if "agrofit_resultado" in st.session_state:
        with col2:
            df_r = st.session_state["agrofit_resultado"]
            encontrados = df_r[df_r["ingrediente"] != ""].shape[0]
            st.metric("Encontrados", encontrados, f"de {len(df_r)}")

        _render_tabela_agrofit(df_r)
        return df_r
    return None


def _render_tabela_agrofit(df: pd.DataFrame):
    st.markdown("##### Resultado AGROFIT")
    min_conf = st.slider("Confiança mínima", 0.0, 1.0, 0.5, 0.05, key="agrofit_conf_slider")
    df_filtrado = df[df["confianca"] >= min_conf].copy()

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
    st.dataframe(df_display, width='stretch', hide_index=True)

    csv = df_filtrado.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar CSV", csv, f"agrofit_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        "text/csv", key="agrofit_dl_btn"
    )


def _try_get_token_silent() -> str:
    try:
        return _get_token()
    except ValueError:
        return ""


def debug_busca_praga(nome_praga: str, token: str) -> dict:
    result: dict = {
        "praga_buscada": nome_praga,
        "pragas_comuns_encontradas": [],
        "produtos_direto": 0,
        "marcas_direto": [],
        "raw_keys_exemplo": [],
        "por_praga_norm": [],
        "erro": None,
    }
    try:
        client = AgroFitClient(token=token)
        _raw_data = client._get("/search/produtos-formulados", params={"praga_nome_comum": nome_praga, "page": 1, "size": 3})
        if _raw_data:
            _items_raw = _raw_data.get("content", _raw_data) if isinstance(_raw_data, dict) else _raw_data
            if _items_raw and isinstance(_items_raw, list) and len(_items_raw) > 0:
                first = _items_raw[0]
                result["raw_keys_exemplo"] = list(first.keys()) if isinstance(first, dict) else [str(first)]

        r_direto = client.buscar_por_praga(nome_praga, max_results=5)
        result["produtos_direto"] = len(r_direto)
        result["marcas_direto"] = [p.get("marca_comercial", "") for p in r_direto]

        pragas_comuns = client.buscar_pragas_comuns(nome_praga, max_results=10)
        result["pragas_comuns_encontradas"] = pragas_comuns

        for pn in pragas_comuns[:5]:
            if pn.strip().upper() == nome_praga.strip().upper():
                continue
            r_norm = client.buscar_por_praga(pn, max_results=5)
            result["por_praga_norm"].append({
                "praga": pn,
                "count": len(r_norm),
                "marcas": [p.get("marca_comercial", "") for p in r_norm],
            })
    except Exception as exc:
        result["erro"] = str(exc)
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_marcas_por_praga_cached(nome_praga: str, token: str) -> list[str]:
    import traceback
    try:
        client = AgroFitClient(token=token)
        todas_marcas: list[str] = []

        resultados_diretos = client.buscar_por_praga(nome_praga, max_results=50)
        marcas_diretas = [r.get("marca_comercial", "") for r in resultados_diretos if r.get("marca_comercial")]
        todas_marcas.extend(marcas_diretas)

        pragas_norm = client.buscar_pragas_comuns(nome_praga, max_results=10)
        for praga_norm in pragas_norm:
            if praga_norm.strip().upper() == nome_praga.strip().upper():
                continue
            res2 = client.buscar_por_praga(praga_norm, max_results=50)
            marcas2 = [r.get("marca_comercial", "") for r in res2 if r.get("marca_comercial")]
            todas_marcas.extend(marcas2)

        # Garante que seja tudo string e não listas antes de jogar pro App
        marcas_unicas = []
        for m in todas_marcas:
            if isinstance(m, list):
                if m: m = str(m[0])
                else: continue
            elif not isinstance(m, str):
                m = str(m)
            m_str = m.strip()
            if m_str and m_str not in marcas_unicas:
                marcas_unicas.append(m_str)

        return marcas_unicas

    except Exception as e:
        print(f"[Agrofit] ERRO em buscar_marcas_por_praga_cached('{nome_praga}'): {e}")
        print(traceback.format_exc())
        return []


def salvar_resultado_agrofit_no_banco(df_resultado: pd.DataFrame, conn) -> int:
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
